#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把英文维基词条名解析成中文正式译名（= 中文维基条目名）。

为什么需要这一步
----------------
翻译时 LLM 经常把专有名词处理得四不像：

    Riemann's xi function  → 黎曼的 xi 函数   （正确：黎曼ξ函数）
    Mellin transform       → Mellin 型积分      （正确：梅林变换）
    Theta function         → Theta 函数         （正确：Θ函数）
    Siegel–Tatsuzawa       → 西格尔–Tatsuzawa   （正确：西格尔–立川）

中文维基的条目名就是现成的标准译名，直接查 API 比让模型猜可靠得多。
查到之后有两种用法：塞进翻译提示词当术语表，或者事后批量回填。

三级兜底
--------
  1. en.wikipedia.org 的 `prop=langlinks&lllang=zh` → 中文条目名
  2. 查不到再走 Wikidata 的 zh / zh-cn / zh-hans 标签与别名
     （有些条目没有中文版，但 Wikidata 上有中文标签，例如 Hadamard product）
  3. 都没有 → None，这种只能留给 LLM 音译

简繁转换
--------
langlinks 给的是中文维基的**源标题**，可能是繁体（「黎曼ξ函數」「Θ函數」）。
用 zh.wikipedia.org 的 `action=parse&variant=zh-cn` 做一次变体转换。
（`converttitles` 靠不住：标题里没有需要转换的词时它干脆不返回 converted 字段，
 而「函數 → 函数」这种纯字形转换它经常不认。）

用法
----
    python scripts/wikiterm.py "Riemann xi function" "Mellin transform"
    python scripts/wikiterm.py --scan docs/math/黎曼ζ函数.md
    python scripts/wikiterm.py --scan docs/math/ --glossary   # 输出术语表
    python scripts/wikiterm.py --scan docs/math/ --json       # 输出 JSON

结果缓存在 scripts/wiki-zh-terms.json（会提交，重跑不发请求）。
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

EN_API = "https://en.wikipedia.org/w/api.php"
ZH_API = "https://zh.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"
CACHE_NAME = "wiki-zh-terms.json"

# 不是词条、不该进术语表的命名空间
SKIP_NS = re.compile(
    r"^(Special|File|Image|Category|Help|Talk|Wikipedia|WP|Template|Portal|"
    r"Draft|Module|MediaWiki|Book|TimedText|User):", re.I)
# 链接里这些查询/锚点要剥掉
WIKI_LINK_RE = re.compile(
    r"https?://en\.wikipedia\.org/wiki/(?P<title>[^)\s\"'<>\]#?]+)")

BATCH = 40          # titles= 一次最多 50，留点余量
MAX_TERM_LEN = 120  # 太长的多半是恶意/异常链接，跳过


# --------------------------------------------------------------------------- HTTP
_last_call = [0.0]
MIN_INTERVAL = 1.2  # 匿名调用维基 API 会被限流，两次请求之间至少隔这么久


def api(host, params, tries=5, timeout=45):
    """这台机器网络会随机 RST，维基还会 429 限流，两样都要退避。"""
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    url = "%s?%s" % (host, urllib.parse.urlencode(params))
    last = None
    for i in range(tries):
        # 限速：距上次请求不足 MIN_INTERVAL 就先等
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            _last_call[0] = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:
                # 429 要按 Retry-After 退避，硬重试只会继续被拒
                try:
                    delay = float(exc.headers.get("Retry-After") or 0)
                except ValueError:
                    delay = 0
                time.sleep(max(delay, 20) * (i + 1))
            elif i + 1 < tries:
                time.sleep(1.5 * (i + 1))
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i + 1 < tries:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError("API 请求失败 %s: %s" % (host, last))


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# --------------------------------------------------------------------------- 查询
def langlinks(titles):
    """en 词条 → 中文条目名（可能繁体）。查不到就不出现在结果里。"""
    out = {}
    for batch in _chunks(list(titles), BATCH):
        data = api(EN_API, {
            "action": "query", "prop": "langlinks", "lllang": "zh",
            "lllimit": "500", "titles": "|".join(batch), "redirects": "1",
        })
        query = data.get("query", {})
        # redirects / normalized：把「请求时的名字」映射回调用方给的原名
        alias = {}
        for item in query.get("normalized", []):
            alias[item["to"]] = item["from"]
        for item in query.get("redirects", []):
            alias[item["to"]] = item["from"]
        for page in query.get("pages", []):
            ll = page.get("langlinks") or []
            if not ll:
                continue
            zh = ll[0].get("title")
            if not zh:
                continue
            key = alias.get(page["title"], page["title"])
            out[key] = zh
    return out


def wikidata_zh(titles):
    """兜底：走 Wikidata 的中文标签 / 别名。"""
    qids = {}
    for batch in _chunks(list(titles), BATCH):
        data = api(EN_API, {
            "action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
            "titles": "|".join(batch), "redirects": "1",
        })
        query = data.get("query", {})
        alias = {}
        for item in query.get("normalized", []):
            alias[item["to"]] = item["from"]
        for item in query.get("redirects", []):
            alias[item["to"]] = item["from"]
        for page in query.get("pages", []):
            qid = (page.get("pageprops") or {}).get("wikibase_item")
            if qid:
                qids[alias.get(page["title"], page["title"])] = qid
    if not qids:
        return {}

    out = {}
    for batch in _chunks(sorted(set(qids.values())), BATCH):
        data = api(WD_API, {
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "labels|aliases", "languages": "zh-cn|zh-hans|zh|zh-hant",
        })
        for qid, ent in (data.get("entities") or {}).items():
            # 优先级：zh-cn > zh-hans > zh > zh-hant > 别名
            cand = []
            labels = ent.get("labels") or {}
            for lang in ("zh-cn", "zh-hans", "zh", "zh-hant"):
                if lang in labels:
                    cand.append(labels[lang]["value"])
            for lang in ("zh-cn", "zh-hans", "zh", "zh-hant"):
                for al in (ent.get("aliases") or {}).get(lang, []):
                    cand.append(al["value"])
            if not cand:
                continue
            for title, q in qids.items():
                if q == qid and title not in out:
                    out[title] = cand[0]
    return out


def to_simplified(strings):
    """繁体 → 简体（zh-cn 变体）。输入输出一一对应，失败时原样返回。

    必须分批：一次塞几百行进去，wikitext 解析出来的行数经常对不上（有的条目名
    本身带 wiki 标记，会被解析成标签），一判 mismatch 就整批退回原文，
    繁体一个都转不掉。分批后坏掉的只是那一小批。
    """
    if not strings:
        return []
    out = []
    for batch in _chunks(list(strings), 40):
        out.extend(_to_simplified_batch(batch))
    return out


def _to_simplified_batch(strings):
    try:
        data = api(ZH_API, {
            "action": "parse", "text": "\n".join(strings),
            "contentmodel": "wikitext", "variant": "zh-cn", "prop": "text",
        })
        html = data["parse"]["text"]
        text = re.sub(r"<[^>]+>", "", html)
        lines = [ln.strip() for ln in text.split("\n")]
        lines = [ln for ln in lines if ln]
        if len(lines) == len(strings):
            return lines
    except Exception:  # noqa: BLE001
        pass
    # 转换失败不影响主流程，退回原文（繁体也比没有强）
    return list(strings)


def resolve(titles, cache=None, verbose=True):
    """返回 {英文词条: 中文译名}。查不到的键不出现在结果里。"""
    titles = [t for t in titles if t]
    out = {}
    todo = []
    for t in titles:
        if cache and t in cache:
            out[t] = cache[t]
        else:
            todo.append(t)
    if not todo:
        return out

    found = langlinks(todo)
    missing = [t for t in todo if t not in found]
    if missing and verbose:
        print("  langlinks 查不到，走 Wikidata 兜底: %d 条" % len(missing),
              file=sys.stderr)
    if missing:
        found.update(wikidata_zh(missing))

    if found:
        keys = list(found.keys())
        simple = to_simplified([found[k] for k in keys])
        for k, v in zip(keys, simple):
            out[k] = v
    return out


# --------------------------------------------------------------------------- 扫描
def scan_titles(paths):
    """从 .md 里的 en.wikipedia.org 链接抽出英文词条名。"""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for n in names:
                    if n.endswith(".md"):
                        files.append(os.path.join(root, n))
        elif p.endswith(".md"):
            files.append(p)
    titles = []
    seen = set()
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for m in WIKI_LINK_RE.finditer(text):
            raw = urllib.parse.unquote(m.group("title"))
            raw = raw.replace("_", " ").strip()
            if not raw or len(raw) > MAX_TERM_LEN:
                continue
            if SKIP_NS.match(raw):
                continue
            if raw in seen:
                continue
            seen.add(raw)
            titles.append(raw)
    return titles


def normalize_cache(data):
    """整理缓存：键按小写去重，值再过一次简繁转换。

    维基标题只有首字母大小写有区别，「Riemann Xi function」和「Riemann xi function」
    是同一条目，扫描时会被当成两个词。另外大批量转换偶尔会漏（parse 返回的行数和
    输入对不上就退回原文），所以这里再补一刀 —— 转换对已经是简体的文本是幂等的。
    """
    # 同一条目的大小写变体里，留「句子式大小写」那个（小写字母最多的），
    # 术语表是给人看的，全小写/首字母大写乱跳不好读
    def rank(s):
        return (-sum(1 for c in s if c.islower()), len(s), s)

    dedup = {}
    for k in sorted(data, key=rank):
        lk = k.lower()
        if lk not in dedup:
            dedup[lk] = k
    out = {dedup[lk]: data[dedup[lk]] for lk in dedup}
    keys = list(out)
    vals = to_simplified([out[k] for k in keys])
    for k, v in zip(keys, vals):
        out[k] = v
    return out


def load_cache(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_cache(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


# --------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="把英文维基词条名解析成中文正式译名")
    ap.add_argument("titles", nargs="*", help="英文词条名（可多个）")
    ap.add_argument("--scan", nargs="*", default=[],
                    help="扫描 .md / 目录，抽出里面的 en.wikipedia.org 链接")
    ap.add_argument("--glossary", action="store_true",
                    help="输出 Markdown 术语表（两列表格）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--no-cache", action="store_true", help="忽略缓存，重新查")
    ap.add_argument("--cache", default=None, help="缓存文件路径")
    ap.add_argument("--fix-cache", action="store_true",
                    help="只整理缓存：键按小写去重、值重做简繁转换，不发新查询")
    args = ap.parse_args(argv)

    here = os.path.dirname(os.path.abspath(__file__))
    cache_path = args.cache or os.path.join(here, CACHE_NAME)
    cache = {} if args.no_cache else load_cache(cache_path)

    if args.fix_cache:
        old = load_cache(cache_path)
        new = normalize_cache(old)
        save_cache(cache_path, new)
        print("缓存整理: %d → %d 条（去重 %d）"
              % (len(old), len(new), len(old) - len(new)), file=sys.stderr)
        return 0

    wanted = list(args.titles)
    for p in args.scan:
        wanted.extend(scan_titles([p]))
    # 去重保序
    seen, ordered = set(), []
    for t in wanted:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    if not ordered:
        ap.error("没给词条名，也没扫到任何 en.wikipedia.org 链接")

    print("待解析词条: %d（缓存命中 %d）"
          % (len(ordered), sum(1 for t in ordered if t in cache)),
          file=sys.stderr)
    result = resolve(ordered, cache=cache)
    print("解析成功: %d，查不到: %d"
          % (len(result), len(ordered) - len(result)), file=sys.stderr)

    # 写回缓存（查不到的不写，下次还会重试）
    if not args.no_cache:
        new = dict(cache)
        new.update(result)
        if new != cache:
            save_cache(cache_path, new)
            print("缓存已更新: %s（%d 条）" % (cache_path, len(new)),
                  file=sys.stderr)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.glossary:
        print("| 英文 | 中文 |")
        print("| --- | --- |")
        for k in ordered:
            print("| %s | %s |" % (k, result.get(k, "（无中文条目）")))
    else:
        for k in ordered:
            print("%-45s → %s" % (k, result.get(k, "（无中文条目）")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
