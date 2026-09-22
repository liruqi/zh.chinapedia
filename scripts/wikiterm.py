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
  1. en.wikipedia.org 的 `prop=langlinks&lllang=zh` → 中文条目名（最可靠）
  2. 查不到再走 Wikidata 的中文标签与别名 —— **质量明显差一档**，
     Wikidata 的 zh 标签不少是机翻/生造的（Andrew Granville → 安德鲁·关维、
     János Pintz → 平茨·亚诺什），人名尤其容易翻车。
     要严格就加 `--no-wikidata`，只认真正存在中文维基条目的译名。
  3. 都没有 → None。**中文维基没条目的不要生造译名**，保留英文原文更诚实。
     （踩过：Tikao Tatsuzawa 中/日文维基都没有，猜「立川」是错的——
      立川读 Tachikawa/Tatsukawa，不是 Tatsuzawa。）

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
# 人名子集：只收「en.wikipedia 确实有中文 langlink」的人名，见 verify_people()
PEOPLE_CACHE_NAME = "wiki-zh-terms-people.json"

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


def _forward_map(query):
    """normalized + redirects → {请求时的名字: 最终页面标题}。

    注意方向：API 给的是 from→to（请求名 → 最终名），早先这里做成了反查
    （最终名 → 请求名），结果是**两个请求名跳到同一页面时会互相覆盖**
    ——「Carl Siegel」和「Carl Ludwig Siegel」都指向 Carl Ludwig Siegel 条目，
    反查表里最终名只留下最后一个请求名，另一个请求名就永远查不到 langlink，
    被误判成「没有中文条目」。必须正向映射，再逐个请求名去找最终标题。
    """
    forward = {}
    for item in query.get("normalized", []):
        forward[item["from"]] = item["to"]
    for item in query.get("redirects", []):
        forward[item["from"]] = item["to"]
    return forward


def _final_title(forward, title, depth=8):
    """沿 normalized → redirects 链展开到最终标题（防环）。"""
    seen = set()
    while title in forward and title not in seen and depth > 0:
        seen.add(title)
        title = forward[title]
        depth -= 1
    return title


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
        forward = _forward_map(query)
        zh_by_page = {}
        for page in query.get("pages", []):
            ll = page.get("langlinks") or []
            zh = ll[0].get("title") if ll else None
            if zh:
                zh_by_page[page["title"]] = zh
        for t in batch:
            zh = zh_by_page.get(_final_title(forward, t))
            if zh:
                out[t] = zh
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
        forward = _forward_map(query)
        qid_by_page = {}
        for page in query.get("pages", []):
            qid = (page.get("pageprops") or {}).get("wikibase_item")
            if qid:
                qid_by_page[page["title"]] = qid
        for t in batch:
            qid = qid_by_page.get(_final_title(forward, t))
            if qid:
                qids[t] = qid
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


def resolve(titles, cache=None, verbose=True, use_wikidata=True):
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
    if not missing:
        return out
    if not use_wikidata:
        return out
    if verbose:
        print("  langlinks 查不到，走 Wikidata 兜底: %d 条" % len(missing),
              file=sys.stderr)
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


def verify_people(cache, verbose=True):
    """挑出缓存里的人名条目，逐条回查 en.wikipedia 的 langlinks，只留真有中文条目的。

    背景：缓存是 langlinks（可靠）和 Wikidata 中文标签（机翻多）混在一起的，
    没有记录来源。人名译名里的间隔号「·」在 md2zh.load_terms() 里默认会被过滤掉，
    结果连「Helmut Hasse → 赫尔穆特·哈斯」这种中文维基真有条目的也被一起丢了。
    这里用 langlinks 重查一遍当作「来源证明」：查得到 = 中文维基确实有这个条目，
    译名可信，可以放行；查不到 = 当年是 Wikidata 兜底出来的，继续过滤。

    返回 {英文名: 中文名}，同时把命中的中文名重做一次简繁转换（顺带修缓存）。
    """
    people = {k: v for k, v in cache.items() if "\u00b7" in (v or "")}
    if not people:
        return {}
    if verbose:
        print("回查人名条目: %d 条" % len(people), file=sys.stderr)
    found = langlinks(list(people))
    if not found:
        return {}
    keys = [k for k in people if k in found]
    simple = to_simplified([found[k] for k in keys])
    out = {}
    for k, zh in zip(keys, simple):
        # langlinks 返回的是中文维基**源标题**（可能繁体），简繁转换偶尔漏，兜底用缓存值
        out[k] = zh if zh else people[k]
    if verbose:
        dropped = len(people) - len(out)
        print("人名条目保留 %d 条，丢弃 %d 条（无中文维基条目）"
              % (len(out), dropped), file=sys.stderr)
    return out


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
    ap.add_argument("--verify-people", action="store_true",
                    help="回查缓存里带「·」的人名条目，把确有中文维基条目的写进 "
                         + PEOPLE_CACHE_NAME + "（md2zh 靠它决定放行哪些人名）")
    ap.add_argument("--no-wikidata", action="store_true",
                    help="不走 Wikidata 兜底，只认有中文维基条目的译名（更严格）")
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

    if args.verify_people:
        people = verify_people(cache)
        people_path = os.path.join(here, PEOPLE_CACHE_NAME)
        save_cache(people_path, people)
        print("已写入 %s（%d 条）" % (people_path, len(people)), file=sys.stderr)
        # 顺带把修正后的译名同步回主缓存
        if people:
            new = dict(cache)
            new.update(people)
            if new != cache:
                save_cache(cache_path, new)
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
    result = resolve(ordered, cache=cache, use_wikidata=not args.no_wikidata)
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
