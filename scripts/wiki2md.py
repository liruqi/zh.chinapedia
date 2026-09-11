#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wiki2md.py —— 把非中文维基百科词条翻译成简体中文 Markdown 条目（zh.chinapedia）

用法
----
    # provider 自动选择：有 DEEPSEEK_API_KEY 用 DeepSeek，其次 OpenAI，否则用本地 LM Studio
    DEEPSEEK_API_KEY=sk-xxx python3 scripts/wiki2md.py https://en.wikipedia.org/wiki/Twin_prime

    # 指定 OpenAI
    OPENAI_API_KEY=sk-xxx python3 scripts/wiki2md.py \
        https://en.wikipedia.org/wiki/Prime_gap --provider openai --model gpt-4o

    # 本地 LM Studio（OpenAI 兼容接口，默认 http://localhost:1234/v1）
    python3 scripts/wiki2md.py https://en.wikipedia.org/wiki/Prime_gap \
        --provider lmstudio --model qwen2.5-32b-instruct

    # 指定输出路径 / 只预览不落盘 / 顺带生成 _category_.json
    python3 scripts/wiki2md.py https://en.wikipedia.org/wiki/Sexy_prime \
        -o docs/math/六素数.md --dry-run --create-category

输出路径
--------
未指定 -o 时按 `docs/{一级分类}/{中文条目名}.md` 生成。一级分类优先取 --category，
否则由模型判断（如 数学 / 物理 / 人物 / 计算机）。

流程
----
1. 解析链接 → (语言代码, 词条名)
2. 抓取源维基 wikitext
3. 查 langlinks：中文维基若已有对应条目，直接采用其简体标题作为条目名
4. 抽取正文内部链接并批量查询中文维基，构建「源条目名 → 简体中文条目名」术语表
   （中文维基没有对应条目的专有名词，提示模型保留源语言原名）
5. 交给 LLM 翻译为 Markdown，保留全部引用与链接
6. 写出 Markdown 文件（超长词条按章节分段翻译）

依赖：仅 Python 3.8+ 标准库，无需 pip 安装。
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "zh.chinapedia-wiki2md/1.0 (+https://github.com/liruqi/zh.chinapedia)"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".wiki2md-cache.json")
MISSING = object()

PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "base_url_env": "OPENAI_BASE_URL",
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4o",
        "need_key": True,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "default_model": "deepseek-chat",
        "need_key": True,
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "base_url_env": "LMSTUDIO_BASE_URL",
        "key_env": "LMSTUDIO_API_KEY",
        "model_env": "LMSTUDIO_MODEL",
        "default_model": "local-model",
        "need_key": False,
    },
}

ZH_VARIANTS = {"zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk", "zh-mo", "zh-sg", "zh-my"}
SKIP_NS = re.compile(
    r"^(File|Image|Category|Wikipedia|Help|Template|Portal|Special|Draft|Module|Talk|"
    r"User|User talk|MediaWiki|WP|MOS|Book|TimedText)\s*:",
    re.I,
)
LINK_RE = re.compile(r"\[\[([^\[\]|#<>]+)(?:#[^\[\]|<>]*)?(?:\|[^\[\]]*)?\]\]")
BAD_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
META_RE = re.compile(r"===\s*META\s*===(.*?)===\s*CONTENT\s*===", re.S | re.I)
AUTOLINK_RE = re.compile(r"<((?:https?|ftp)://[^<>\s]+)>")


def log(msg, quiet=False):
    if not quiet:
        print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- HTTP

def _http(url, body, headers, timeout, tries):
    hdrs = {"User-Agent": UA}
    hdrs.update(headers or {})
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(url, data=body, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
            raise SystemExit("HTTP %s: %s" % (exc.code, detail or exc.reason))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < tries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise SystemExit("网络错误: %s" % exc)
    raise SystemExit("请求失败: %s" % last)


def http_get(url, headers=None, timeout=60, tries=5):
    return _http(url, None, headers, timeout, tries)


def http_post_json(url, payload, headers=None, timeout=600, tries=3):
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    body = json.dumps(payload).encode("utf-8")
    return _http(url, body, hdrs, timeout, tries)


def wiki_api(lang, params):
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    url = "https://%s.wikipedia.org/w/api.php?%s" % (lang, urllib.parse.urlencode(params))
    return json.loads(http_get(url))


# --------------------------------------------------------------------------- cache

class Cache:
    """本地缓存，避免重复请求维基接口（也用于降低 429 风险）。"""

    def __init__(self, enabled=True, path=None):
        self.enabled = enabled
        self.path = path or CACHE_FILE
        self.data = {}
        if enabled and os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as fh:
                    self.data = json.load(fh)
            except Exception:
                self.data = {}

    def get(self, key, default=MISSING):
        if self.enabled and key in self.data:
            return self.data[key]
        return default

    def set(self, key, value):
        if self.enabled:
            self.data[key] = value

    def save(self):
        if not self.enabled:
            return
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=0)
        except Exception:
            pass


# --------------------------------------------------------------------------- wiki

def parse_wiki_url(url):
    parsed = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    host = (parsed.netloc or "").lower()
    m = re.match(r"^(?:([a-z0-9-]+)\.)?(?:m\.)?wikipedia\.org$", host)
    if not m:
        raise SystemExit("不是维基百科链接: %s" % url)
    lang = m.group(1) or "en"
    if lang in ZH_VARIANTS or parsed.path.startswith("/zh"):
        raise SystemExit("输入需为非中文维基百科词条，例如 en.wikipedia.org/wiki/Twin_prime")
    if parsed.path.startswith("/wiki/"):
        title = urllib.parse.unquote(parsed.path[len("/wiki/"):])
    else:
        title = urllib.parse.unquote((urllib.parse.parse_qs(parsed.query).get("title") or [""])[0])
    title = title.replace("_", " ").strip()
    if not title:
        raise SystemExit("无法从链接中解析词条名: %s" % url)
    return lang, title


def fetch_wikitext(lang, title, cache):
    key = "wikitext:%s:%s" % (lang, title)
    hit = cache.get(key)
    if hit is not MISSING:
        return hit["title"], hit["text"]
    data = wiki_api(lang, {
        "action": "query", "redirects": "1", "prop": "revisions",
        "rvprop": "content", "rvslots": "main", "titles": title,
    })
    pages = data.get("query", {}).get("pages") or []
    page = pages[0] if pages else None
    if not page or page.get("missing"):
        raise SystemExit("源维基上找不到词条: %s" % title)
    text = page["revisions"][0]["slots"]["main"]["content"]
    out = {"title": page["title"], "text": text}
    cache.set(key, out)
    return out["title"], text


def to_simplified(zh_title, cache):
    """把中文维基条目名转成简体（借 zh-hans 变体转换）。"""
    if not zh_title:
        return None
    key = "simp:%s" % zh_title
    hit = cache.get(key)
    if hit is not MISSING:
        return hit
    try:
        data = wiki_api("zh", {"action": "parse", "page": zh_title,
                               "prop": "displaytitle", "variant": "zh-hans"})
        raw = (data.get("parse") or {}).get("displaytitle") or zh_title
        text = re.sub(r"<[^>]+>", "", raw).strip() or zh_title
    except SystemExit:
        text = zh_title
    cache.set(key, text)
    return text


def langlink_title(entry):
    """兼容 formatversion=1（"*"）与 formatversion=2（"title"）的 langlinks 结构。"""
    return entry.get("*") or entry.get("title") or ""


def zh_title_for(lang, title, cache):
    """源词条在中文维基的对应条目名（简体），没有则返回 None。"""
    key = "zh:%s:%s" % (lang, title)
    hit = cache.get(key)
    if hit is not MISSING:
        return hit
    data = wiki_api(lang, {"action": "query", "redirects": "1",
                           "prop": "langlinks", "lllang": "zh", "titles": title})
    zh = None
    for page in data.get("query", {}).get("pages", []):
        ll = page.get("langlinks")
        if ll:
            zh = langlink_title(ll[0])
            break
    result = to_simplified(zh, cache) if zh else None
    cache.set(key, result)
    return result


def extract_link_targets(wikitext):
    out, seen = [], set()
    for m in LINK_RE.finditer(wikitext):
        t = m.group(1).strip()
        if not t or t.startswith(":") or SKIP_NS.match(t):
            continue
        t = t.replace("_", " ").strip()
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
    return out


def build_glossary(lang, targets, cache, limit, quiet=False):
    """源语言条目名 → 简体中文维基条目名（仅保留中文维基确有条目的）。"""
    glossary = {}
    targets = targets[:limit]
    for i in range(0, len(targets), 40):
        batch = targets[i:i + 40]
        data = wiki_api(lang, {"action": "query", "redirects": "1",
                               "prop": "langlinks", "lllang": "zh", "titles": "|".join(batch)})
        for page in data.get("query", {}).get("pages", []):
            ll = page.get("langlinks")
            if not ll:
                continue
            simp = to_simplified(langlink_title(ll[0]), cache)
            if simp:
                glossary[page["title"]] = simp
        if i + 40 < len(targets):
            time.sleep(0.5)
    cache.save()
    log("  · 术语表: %d 条" % len(glossary), quiet)
    return glossary


def split_wikitext(text, max_chars):
    """超长词条按一级章节切分，避免单次请求超出模型上下文。"""
    if len(text) <= max_chars:
        return [text]
    sections, cur, cur_len = [], [], 0
    for line in text.split("\n"):
        if re.match(r"^==\s*[^=].*==\s*$", line.strip()) and cur_len > max_chars * 0.5:
            sections.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(line)
        cur_len += len(line) + 1
    if cur:
        sections.append("\n".join(cur))
    out, buf = [], ""
    for sec in sections:
        if len(sec) > max_chars:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(sec[i:i + max_chars] for i in range(0, len(sec), max_chars))
        elif len(buf) + len(sec) > max_chars:
            out.append(buf)
            buf = sec
        else:
            buf += sec
    if buf:
        out.append(buf)
    return out


# --------------------------------------------------------------------------- LLM

SYSTEM_PROMPT = """你是「中国百科」（zh.chinapedia）的资深中文编辑，负责把外文维基百科词条完整转写为简体中文条目。

硬性要求：
1. 完整翻译，不得省略、概括、合并或增删章节，章节顺序与原文一致。
2. 若提供了术语表，「源语言条目名 → 简体中文条目名」的对应必须优先采用。
3. 专有名词（定理名、猜想名、人名、项目名、组织名等）若中文维基有对应条目，使用其简体中文条目名；
   若中文维基没有对应条目，保留源语言原名，不要自行生造中文译名。
   普通词汇使用通行中文术语即可，不受此限。
4. 保留全部引用与链接：wikitext 的 [[条目]] 转成 Markdown 链接并指向源语言维基的完整 URL；
   [url 文本] 转成 [文本](url)；<ref> 内容整理为文末「参考文献」编号列表，并保留其中的 URL。
5. wikitext 标记转成标准 Markdown：'''粗体'''、''斜体''、== 标题 ==、列表、表格等；
   删除 {{Short description}}、{{Infobox}} 等信息框模板与页脚导航模板，但保留其中有价值的正文信息。
6. 站点用 MDX 解析：数学公式请用行内代码（反引号）或代码块表示；
   正文中不得出现未转义的 < > 与花括号；尤其禁止 <https://…> 形式的自动链接，一律写成 [文本](url)。
7. 不要添加原文没有的内容，也不要写「本文翻译自……」之类的说明文字。
8. 输出必须严格遵循以下格式，不要有任何前言后语：

===META===
TITLE: <简体中文条目名>
CATEGORY: <一级分类，2-4 个汉字，如 数学 / 物理 / 化学 / 生物 / 人物 / 历史 / 计算机 / 经济>
===CONTENT===
<Markdown 正文，从首段开始；不要写 YAML front matter，不要重复 title>"""


def build_user_prompt(lang, title, zh_title, category, glossary, chunk, part, total, tail):
    lines = ["源词条：%s（%s.wikipedia.org）" % (title, lang)]
    if zh_title:
        lines.append("中文维基已有对应条目，TITLE 必须使用：%s" % zh_title)
    else:
        lines.append("中文维基没有对应条目，TITLE 由你根据词条内容确定简体中文名。")
    if category:
        lines.append("CATEGORY 固定为：%s" % category)
    if glossary:
        lines.append("术语表（源语言条目名 → 简体中文条目名），必须优先采用：")
        for src, dst in glossary.items():
            lines.append("  %s → %s" % (src, dst))
    if total > 1:
        lines.append("注意：这是同一条目的第 %d/%d 部分。" % (part, total))
        if part > 1:
            lines.append("只输出 ===CONTENT=== 之后的正文续写，不要再次输出 ===META=== 块，不要重复前文。")
            if tail:
                lines.append("上一部分结尾（仅供衔接，不要重复）：\n%s" % tail)
    lines.append("")
    lines.append("-----BEGIN WIKITEXT-----")
    lines.append(chunk)
    lines.append("-----END WIKITEXT-----")
    return "\n".join(lines)


def llm_chat(cfg, messages, temperature=0.2, timeout=600):
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    headers = {}
    if cfg.get("api_key"):
        headers["Authorization"] = "Bearer %s" % cfg["api_key"]
    raw = http_post_json(url, payload, headers, timeout=timeout, tries=3)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit("模型返回非 JSON：%s" % raw[:300])
    if not data.get("choices"):
        raise SystemExit("模型调用失败：%s" % str(data.get("error") or data)[:300])
    return data["choices"][0]["message"]["content"]


def parse_meta(text):
    m = META_RE.search(text)
    if not m:
        return None, None, strip_frontmatter(text).strip()
    meta = m.group(1)
    content = text[m.end():].strip()
    return _meta_field(meta, "TITLE"), _meta_field(meta, "CATEGORY"), content


def _meta_field(meta, name):
    m = re.search(r"^\s*%s\s*[:：]\s*(.+?)\s*$" % name, meta, re.M | re.I)
    return m.group(1).strip() if m else None


def strip_frontmatter(text):
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n", text, re.S)
    if m and re.search(r"^\s*title\s*:", m.group(1), re.M):
        return text[m.end():]
    return text


def fix_autolinks(text):
    """把 <url> 形式的自动链接转成 Markdown 链接。

    MDX 会把 <https://…> 当成 JSX 解析（https: 被视作命名空间），
    抛出 `Unexpected character "/" before local name` 导致 docusaurus 构建失败。
    """
    return AUTOLINK_RE.sub(lambda m: "[原文](%s)" % m.group(1), text)


def safe_filename(name):
    cleaned = BAD_FILENAME.sub("", (name or "").strip()).strip().strip(".")
    return cleaned or "未命名"


def find_repo_root(explicit=None, docs_root="docs"):
    if explicit:
        return os.path.abspath(explicit)
    cur = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(cur, ".git")) or os.path.isdir(os.path.join(cur, docs_root)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.getcwd()


def resolve_provider(args):
    name = args.provider
    if name == "auto":
        if os.environ.get("DEEPSEEK_API_KEY"):
            name = "deepseek"
        elif os.environ.get("OPENAI_API_KEY"):
            name = "openai"
        else:
            name = "lmstudio"
    cfg = dict(PROVIDERS[name])
    cfg["name"] = name
    cfg["base_url"] = (args.base_url or os.environ.get(cfg["base_url_env"]) or cfg["base_url"])
    cfg["model"] = (args.model or os.environ.get(cfg["model_env"]) or cfg["default_model"])
    cfg["api_key"] = args.api_key or os.environ.get(cfg["key_env"]) or ""
    if cfg["need_key"] and not cfg["api_key"]:
        raise SystemExit("缺少 API key：请设置环境变量 %s，或传入 --api-key" % cfg["key_env"])
    if not cfg["api_key"]:
        cfg["api_key"] = "lm-studio"
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="wiki2md.py",
        description="把非中文维基百科词条翻译为简体中文 Markdown 条目",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("provider 与环境变量：\n"
                "  openai    OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL（默认 gpt-4o）\n"
                "  deepseek  DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL（默认 deepseek-chat）\n"
                "  lmstudio  LMSTUDIO_BASE_URL / LMSTUDIO_MODEL / LMSTUDIO_API_KEY（本地，默认 http://localhost:1234/v1）\n"),
    )
    ap.add_argument("url", help="非中文维基百科词条链接")
    ap.add_argument("-o", "--output", help="输出文件路径（默认 docs/{一级分类}/{条目名}.md）")
    ap.add_argument("-c", "--category", help="一级分类，覆盖模型判断")
    ap.add_argument("-p", "--provider", choices=["auto"] + sorted(PROVIDERS), default="auto")
    ap.add_argument("-m", "--model", help="模型名，覆盖各 provider 默认值")
    ap.add_argument("--base-url", help="OpenAI 兼容接口地址")
    ap.add_argument("--api-key", help="API key，覆盖环境变量")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--max-chars", type=int, default=60000, help="单次翻译的字符上限，超出按章节分段")
    ap.add_argument("--glossary-limit", type=int, default=80, help="术语表最多查询的内部链接条数，0 关闭")
    ap.add_argument("--docs-root", default="docs", help="默认输出根目录（默认 docs）")
    ap.add_argument("--repo-root", help="仓库根目录，默认自动向上查找")
    ap.add_argument("--create-category", action="store_true", help="目录下缺少 _category_.json 时自动生成")
    ap.add_argument("--dry-run", action="store_true", help="只输出结果，不写文件")
    ap.add_argument("--no-cache", action="store_true", help="不使用本地接口缓存")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    lang, title = parse_wiki_url(args.url)
    log("→ 源词条: %s:%s" % (lang, title), args.quiet)

    cache = Cache(enabled=not args.no_cache)
    real_title, wikitext = fetch_wikitext(lang, title, cache)
    log("  · wikitext %d 字符" % len(wikitext), args.quiet)

    zh_title = zh_title_for(lang, real_title, cache)
    log("  · 中文维基对应条目: %s" % (zh_title or "（无）"), args.quiet)

    glossary = {}
    if args.glossary_limit > 0:
        glossary = build_glossary(lang, extract_link_targets(wikitext),
                                  cache, args.glossary_limit, args.quiet)

    chunks = split_wikitext(wikitext, args.max_chars)
    if len(chunks) > 1:
        log("  · 词条较长，分 %d 段翻译" % len(chunks), args.quiet)

    cfg = resolve_provider(args)
    log("  · 模型: %s / %s" % (cfg["name"], cfg["model"]), args.quiet)

    doc_title, doc_cat, parts, tail = None, args.category, [], ""
    for idx, chunk in enumerate(chunks, 1):
        user = build_user_prompt(lang, real_title, zh_title, args.category,
                                 glossary, chunk, idx, len(chunks), tail)
        reply = llm_chat(cfg, [{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "user", "content": user}], args.temperature)
        t, c, content = parse_meta(reply)
        if t and not doc_title:
            doc_title = t
        if c and not doc_cat:
            doc_cat = c
        parts.append(content)
        tail = reply[-1500:]
        log("  · 第 %d/%d 段完成（输出 %d 字符）" % (idx, len(chunks), len(reply)), args.quiet)

    doc_title = doc_title or zh_title or real_title
    doc_cat = (args.category or doc_cat or "其他").strip()
    body = "\n\n".join(p.strip() for p in parts if p.strip())
    body = fix_autolinks(body)
    if not body:
        raise SystemExit("模型没有返回正文，已中止")

    hazards = []
    if re.search(r"[{}]", body):
        hazards.append("花括号 {}")
    if re.search(r"<[A-Za-z/]", body):
        hazards.append("疑似 HTML/JSX 标签")
    if hazards:
        log("  ! MDX 风险提示：正文含 %s，建议检查" % "、".join(hazards), args.quiet)

    if args.dry_run:
        print("--- title: %s | category: %s ---" % (doc_title, doc_cat))
        print(body)
        return 0

    if args.output:
        out_path = os.path.abspath(args.output)
    else:
        root = find_repo_root(args.repo_root, args.docs_root)
        out_path = os.path.join(root, args.docs_root,
                                safe_filename(doc_cat), safe_filename(doc_title) + ".md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("---\ntitle: %s\n---\n\n%s\n" % (doc_title, body))
    log("✓ 已写入 %s（%d 字符）" % (out_path, len(body)), args.quiet)

    if args.create_category:
        cat_path = os.path.join(os.path.dirname(out_path), "_category_.json")
        if not os.path.exists(cat_path):
            with open(cat_path, "w", encoding="utf-8") as fh:
                json.dump({"label": doc_cat,
                           "link": {"type": "generated-index",
                                    "description": "%s相关条目。" % doc_cat}},
                          fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            log("✓ 已生成 %s" % cat_path, args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
