#!/usr/bin/env python3
"""把 Markdown 里的维基图片搬到 Cloudflare R2（chped 桶），并把引用改写到公网地址。

为什么需要这一步
----------------
`[[File:Cplot zeta.svg|thumb|caption]]` 机械转换出来是

    ![caption](https://commons.wikimedia.org/wiki/File:Cplot_zeta.svg)

那个 URL 是**文件描述页**（一个 HTML 页面），不是图片本身，浏览器里必然裂图。
而 thumb.wikimedia.org 又做了反盗链，直接外链也靠不住。

所以本脚本做三件事：
  1. 用 Commons API 查出图片的真实地址（缩略图，SVG/PDF 会拿到渲染好的 PNG）；
  2. 下载后用 **AWS SigV4 直接 PUT** 到 R2 的 chped 桶（纯标准库，不装 boto3）；
  3. 把 .md 里的链接换成 `https://pub-….r2.dev/<key>`。

用法
----
    python scripts/wikiimg2r2.py docs/math/黎曼ζ函数.md
    python scripts/wikiimg2r2.py docs/math/            # 整个目录
    python scripts/wikiimg2r2.py docs --width 1000 --dry-run

凭证放在 `scripts/r2.local.json`（已在 .gitignore，不提交）：

    {"endpoint": "https://….r2.cloudflarestorage.com", "bucket": "chped",
     "public_base": "https://pub-….r2.dev", "region": "auto",
     "access_key": "…", "secret_key": "…"}

也可以用环境变量 R2_ENDPOINT / R2_BUCKET / R2_PUBLIC_BASE / R2_ACCESS_KEY /
R2_SECRET_KEY 覆盖，方便 CI 里换 prod 凭证。
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MAP_NAME = "wikiimg-map.json"

IMAGE_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
             ".pdf": "application/pdf"}


# --------------------------------------------------------------------------- 凭证
def load_config(path):
    cfg = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    env = {
        "endpoint": os.environ.get("R2_ENDPOINT"),
        "bucket": os.environ.get("R2_BUCKET"),
        "public_base": os.environ.get("R2_PUBLIC_BASE"),
        "access_key": os.environ.get("R2_ACCESS_KEY"),
        "secret_key": os.environ.get("R2_SECRET_KEY"),
        "region": os.environ.get("R2_REGION"),
    }
    for k, v in env.items():
        if v:
            cfg[k] = v
    cfg.setdefault("region", "auto")
    missing = [k for k in ("endpoint", "bucket", "public_base",
                           "access_key", "secret_key") if not cfg.get(k)]
    if missing:
        sys.exit("× R2 配置缺字段：%s（写进 %s 或用环境变量）" % (", ".join(missing), path))
    return cfg


# --------------------------------------------------------------------------- SigV4
def _hmac(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _canonical_uri(path):
    """S3 的 canonical URI：按段编码、保留 `/`，不做路径归一化。"""
    return urllib.parse.quote(path, safe="/~")


def sigv4_auth(method, canonical_uri, amzdate, datestamp, headers, payload_hash,
               access, secret, region, service="s3"):
    canon_headers = "".join("%s:%s\n" % (k.lower(), str(v).strip())
                            for k, v in sorted(headers.items(), key=lambda x: x[0].lower()))
    signed = ";".join(sorted(k.lower() for k in headers))
    canon_req = "\n".join([method, canonical_uri, "", canon_headers, signed, payload_hash])
    scope = "%s/%s/%s/aws4_request" % (datestamp, region, service)
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amzdate, scope,
                         hashlib.sha256(canon_req.encode("utf-8")).hexdigest()])
    key = _hmac(("AWS4" + secret).encode("utf-8"), datestamp)
    key = _hmac(key, region)
    key = _hmac(key, service)
    key = _hmac(key, "aws4_request")
    sig = hmac.new(key, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return ("AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s"
            % (access, scope, signed, sig))


def r2_put(cfg, key, data, content_type, timeout=180, tries=4):
    """用 SigV4 把对象 PUT 到 R2。R2 用路径风格：<endpoint>/<bucket>/<key>。

    这边的网络会随机 RST（WinError 10054），所以带重试。
    """
    last = None
    for i in range(tries):
        try:
            return _r2_put_once(cfg, key, data, content_type, timeout)
        except Exception as exc:                         # noqa: BLE001
            last = exc
            if i + 1 < tries:
                print("    … 第 %d 次失败（%s），重试" % (i + 1, exc))
    raise last


def _r2_put_once(cfg, key, data, content_type, timeout=180):
    bucket = cfg["bucket"]
    canonical_uri = _canonical_uri("/%s/%s" % (bucket, key))
    url = cfg["endpoint"].rstrip("/") + canonical_uri
    host = urllib.parse.urlparse(url).netloc

    now = datetime.now(timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(data).hexdigest()

    headers = {
        "Host": host,
        "Content-Type": content_type,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amzdate,
    }
    headers["Authorization"] = sigv4_auth(
        "PUT", canonical_uri, amzdate, datestamp, headers, payload_hash,
        cfg["access_key"], cfg["secret_key"], cfg["region"])

    req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()
    return cfg["public_base"].rstrip("/") + "/" + urllib.parse.quote(key, safe="/")


def http_head_ok(url, timeout=30, tries=3):
    """探测对象是否已存在。这台机器的网络会随机 RST，所以带重试。"""
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return 200 <= resp.status < 300
        except Exception:                                # noqa: BLE001
            continue
    return False


# --------------------------------------------------------------------------- Commons
def commons_imageinfo(title, width, lang="en"):
    """查图片真实地址。先找 Commons，找不到再试本地维基。"""
    bases = [COMMONS_API, "https://%s.wikipedia.org/w/api.php" % lang]
    for base in bases:
        q = urllib.parse.urlencode({
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url|mime|size", "iiurlwidth": width, "titles": title,
        })
        try:
            req = urllib.request.Request(base + "?" + q, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:                                # noqa: BLE001
            continue
        for page in (data.get("query") or {}).get("pages", {}).values():
            info = page.get("imageinfo")
            if info:
                return info[0]
    return None


def download(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def pick_source(info, width):
    """挑一个真正能当 <img src> 用的地址。

    SVG / PDF 的 thumburl 是 Wikimedia 替我们渲染好的 PNG，必须走这条路；
    GIF 反过来——缩略图会退化成静止的第一帧，所以用原图。
    """
    mime = (info.get("mime") or "").lower()
    if mime == "image/gif":
        return info.get("url")
    return info.get("thumburl") or info.get("url")


# --------------------------------------------------------------------------- Markdown
def iter_images(text):
    """扫出所有 ![alt](url)，alt 里允许嵌套 [..]。返回 (start, end, alt, url)。"""
    out, i, n = [], 0, len(text)
    while i < n:
        s = text.find("![", i)
        if s < 0:
            break
        depth, j = 0, s + 1
        while j < n:
            ch = text[j]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0 or not text.startswith("](", j):
            i = s + 2
            continue
        k = text.find(")", j + 2)
        if k < 0:
            break
        url = text[j + 2:k].strip()
        m = re.match(r'^(\S+)\s+"[^"]*"$', url)          # 去掉可选的 title
        if m:
            url = m.group(1)
        out.append((s, k + 1, text[s + 2:j], url))
        i = k + 1
    return out


# 注意主机名是 commons.wikimedia.org（不是 wikipedia.org），en 站才是 xx.wikipedia.org
_WIKI_HOST = r"(?:[\w-]+\.(?:wikimedia|wikipedia)\.org)"
FILE_PAGE_RE = re.compile(
    r"^https?://" + _WIKI_HOST + r"/wiki/(?:File|Image):(.+)$", re.I)
SPECIAL_FILEPATH_RE = re.compile(
    r"^https?://" + _WIKI_HOST + r"/wiki/Special:FilePath/(.+)$", re.I)


def wikimedia_file_title(url):
    """从描述页 / Special:FilePath / upload.wikimedia.org 的 URL 里取文件名。"""
    m = FILE_PAGE_RE.match(url) or SPECIAL_FILEPATH_RE.match(url)
    if m:
        name = m.group(1).split("?")[0]
        return urllib.parse.unquote(name).replace("_", " ")
    if "upload.wikimedia.org" in url:
        return None                                      # 已经是真实文件，直接下
    return None


def find_root(path):
    """往上找仓库根（有 .git 或 docusaurus.config.js 的那层），用来算 key 前缀。"""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(d, ".git")) or \
           os.path.exists(os.path.join(d, "docusaurus.config.js")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def collect(files):
    out = []
    for f in files:
        if os.path.isdir(f):
            for dirpath, dirnames, filenames in os.walk(f):
                dirnames[:] = [d for d in dirnames
                               if d not in ("node_modules", ".git", "build", ".docusaurus")]
                out.extend(os.path.join(dirpath, x) for x in filenames
                           if x.lower().endswith(".md"))
        else:
            out.append(f)
    return out


# --------------------------------------------------------------------------- 主流程
def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="维基图片 → Cloudflare R2")
    ap.add_argument("paths", nargs="+", help=".md 文件或目录")
    ap.add_argument("--config", default=os.path.join(here, "r2.local.json"))
    ap.add_argument("--map", default=os.path.join(here, MAP_NAME))
    ap.add_argument("--width", type=int, default=1000, help="缩略图宽度，默认 1000")
    ap.add_argument("--lang", default="en", help="找不到时回退到哪个维基，默认 en")
    ap.add_argument("--prefix", help="强制指定 R2 里的目录前缀，默认按 md 所在目录")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不上传不改写")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    mapping = {}
    if os.path.exists(args.map):
        try:
            with open(args.map, encoding="utf-8") as fh:
                mapping = json.load(fh)
        except Exception:                                # noqa: BLE001
            mapping = {}

    files = collect(args.paths)
    total = fixed = 0
    for path in files:
        with open(path, "rb") as fh:
            raw = fh.read().decode("utf-8")
        crlf = "\r\n" in raw
        body = raw.replace("\r\n", "\n")

        images = iter_images(body)
        if not images:
            continue
        root = find_root(path) or os.path.dirname(os.path.abspath(path))
        prefix = args.prefix
        if prefix is None:
            rel = os.path.relpath(os.path.abspath(path), root)
            prefix = os.path.dirname(rel).replace("\\", "/") or "docs"
        prefix = prefix.strip("/")

        edits = []
        for start, end, alt, url in images:
            total += 1
            if url.startswith(cfg["public_base"]):
                continue
            if not re.match(r"^https?://", url):
                continue
            title = wikimedia_file_title(url)
            if title is None and "upload.wikimedia.org" not in url:
                continue

            cache_key = "%s|%d|%s" % (prefix, args.width, title or url)
            hit = mapping.get(cache_key)
            if hit:
                edits.append((start, end, url, hit["url"]))
                fixed += 1
                print("  = 缓存 %s" % hit["key"])
                continue

            if title:
                info = commons_imageinfo("File:" + title, args.width, args.lang)
                if not info:
                    print("  × 查不到图片：%s" % title, file=sys.stderr)
                    continue
                src = pick_source(info, args.width)
            else:
                src = url
            if not src:
                print("  × 没有可用地址：%s" % url, file=sys.stderr)
                continue

            data = download(src)
            ext = os.path.splitext(urllib.parse.urlparse(src).path)[1].lower()
            if title:
                stem, orig_ext = os.path.splitext(title.replace(" ", "_"))
                key_name = title.replace(" ", "_") + (ext if ext and ext != orig_ext else "")
            else:
                key_name = os.path.basename(urllib.parse.urlparse(src).path) or "image" + ext
            key = "%s/%s" % (prefix, key_name)
            ctype = IMAGE_EXT.get(ext, "application/octet-stream")
            public = cfg["public_base"].rstrip("/") + "/" + urllib.parse.quote(key, safe="/")

            print("  ↓ %s  %d 字节" % (key, len(data)))
            if args.dry_run:
                continue
            if not http_head_ok(public):
                try:
                    public = r2_put(cfg, key, data, ctype)
                    print("    ↑ 已上传")
                except Exception as exc:                 # noqa: BLE001
                    print("  × 上传失败 %s：%s" % (key, exc), file=sys.stderr)
                    continue
            else:
                print("    · 桶里已有，跳过上传")
            mapping[cache_key] = {"key": key, "url": public, "bytes": len(data)}
            edits.append((start, end, url, public))
            fixed += 1

        if edits and not args.dry_run:
            for start, end, old, new in reversed(edits):
                body = body[:start] + body[start:end].replace(old, new) + body[end:]
            text = body.replace("\n", "\r\n") if crlf else body
            with open(path, "wb") as fh:
                fh.write(text.encode("utf-8"))
            print("✓ %s（改写 %d 处）" % (path, len(edits)))

    if not args.dry_run:
        with open(args.map, "w", encoding="utf-8") as fh:
            json.dump(mapping, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print("→ 图片 %d 处，处理 %d 处，映射 %d 条" % (total, fixed, len(mapping)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
