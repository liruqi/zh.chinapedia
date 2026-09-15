#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wikitext2md.py —— 纯机械的 wikitext → Markdown 转换（不翻译、不调用 LLM）

与 wiki2md.py 的分工
--------------------
wiki2md.py     : wikitext --(LLM 翻译)--> 简体中文 Markdown
wikitext2md.py : wikitext --(纯规则)--> 同语言 Markdown（保留英文原文）

典型用途：为 en.chinapedia 这类「英文原文镜像站」生成条目，或作为人工/LLM 翻译前的
干净中间产物。转换是确定性的、可重复的，不依赖任何模型。

用法
----
    # 直接抓维基原文并转换
    python3 scripts/wikitext2md.py https://en.wikipedia.org/wiki/Riemann_hypothesis \
        -o D:/SRC/Z/en.chinapedia/docs/math/riemann_hypothesis.md

    # 转换本地已保存的 wikitext
    python3 scripts/wikitext2md.py --input scratch/rh.wikitext --title "Riemann hypothesis" \
        -o out.md

    # 只预览，不落盘；打印未被识别的模板
    python3 scripts/wikitext2md.py --input scratch/rh.wikitext --dry-run --report

主要处理
--------
* 标题 / 列表 / 表格 / 图库 / 图片 / 粗斜体 / 内部链接 / 外部链接
* <math> → KaTeX（$…$ / 三行 $$…$$），并对齐 GitHub 渲染要求
* <ref> → GFM 脚注（正文 [^n] + 文末 [^n]: …），支持 <ref name=… /> 复用
* 模板：harvtxt / harvnb / sfnp / harv / harvs / citation / nowrap / sfrac / math /
  pi / e / abs / val / gaps / 10^ / sic / lang / isbn / radic / pipe / quote / bquote /
  math theorem / cite arXiv / cite web / cite report …
  导航类、信息框类、页脚类模板一律丢弃
* MDX 安全：转义数学环境之外的 { } 与裸 <

依赖：仅 Python 3.8+ 标准库。
"""

import argparse
import html
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wiki2md import (  # noqa: E402
    Cache,
    escape_dollar_in_urls,
    escape_mdx_braces,
    fetch_wikitext,
    fix_github_math,
    parse_wiki_url,
)

UA = "zh.chinapedia-wikitext2md/1.0 (+https://github.com/liruqi/zh.chinapedia)"


def log(msg, quiet=False):
    if not quiet:
        print(msg, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- 工具

SKIP_LINK_NS = re.compile(
    r"^(File|Image|Category|Wikipedia|Help|Template|Portal|Special|Draft|Module|"
    r"Talk|User|MediaWiki|WP|MOS|Book|TimedText)\s*:",
    re.I,
)
FILE_NS = re.compile(r"^(File|Image)\s*:", re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
MATH_RE = re.compile(r"<math\b([^>]*)>(.*?)</math>", re.S)


def split_args(s):
    """按顶层 | 切分模板参数（忽略 [[ ]] 与 {{ }} 内部的 |）。"""
    parts, cur, depth, i = [], [], 0, 0
    while i < len(s):
        if s.startswith("{{", i) or s.startswith("[[", i):
            depth += 1
            cur.append(s[i:i + 2])
            i += 2
            continue
        if s.startswith("}}", i) or s.startswith("]]", i):
            depth -= 1
            cur.append(s[i:i + 2])
            i += 2
            continue
        if s[i] == "|" and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(s[i])
        i += 1
    parts.append("".join(cur))
    return parts


def parse_args(raw):
    """返回 (位置参数列表, 命名参数字典)。"""
    pos, named = [], {}
    for idx, part in enumerate(split_args(raw), 1):
        m = re.match(r"^\s*([A-Za-z0-9_ \t-]{1,30})\s*=", part)
        if m and "=" in part.split("[[")[0]:
            key = m.group(1).strip().lower().replace(" ", "_")
            named[key] = part[m.end():].strip()
        else:
            pos.append(part)
    return pos, named


def page_url(target, lang="en"):
    page, _, anchor = target.partition("#")
    base = "https://%s.wikipedia.org/wiki/" % lang
    url = base + urllib.parse.quote(page.strip().replace(" ", "_"), safe="/")
    if anchor:
        url += "#" + urllib.parse.quote(anchor.strip().replace(" ", "_"), safe="/")
    return url


def file_url(target):
    name = target.split(":", 1)[-1].strip()
    return "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(
        name.replace(" ", "_"), safe="/")


def clean_ws(s):
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


# --------------------------------------------------------------------------- 模板

DROP_TEMPLATES = {
    "short description", "unsolved", "cs1 config", "millennium problems",
    "reflist", "refbegin", "refend", "reflist-talk", "notelist", "efn",
    "portal", "authority control", "commons category-inline", "commons",
    "sister project links", "l-functions-footer", "bernhard riemann",
    "navbox", "infobox", "hatnote", "see also", "further", "main",
    "mathworld", "eom", "citation needed", "cn", "clarify", "dubious",
    "citation needed span", "fact", "who", "when", "according to whom",
    "clarification needed", "inline cleanup needed", "grammar",
}


def _join_authors(parts):
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "; ".join(parts)


def _author_bits(named):
    out = []
    for i in range(1, 12):
        last = named.get("last%d" % i) or named.get("surname%d" % i) or ""
        first = named.get("first%d" % i) or named.get("given%d" % i) or ""
        if last:
            out.append("%s, %s" % (last, first) if first else last)
    if not out:
        last = named.get("last") or named.get("surname") or ""
        first = named.get("first") or named.get("given") or ""
        if last:
            out.append("%s, %s" % (last, first) if first else last)
    if not out:
        for key in ("vauthors", "author", "authors", "author1"):
            if named.get(key):
                out.append(named[key])
                break
    return out


def _harv_cite(authors, year, extra, paren):
    """paren=True（harvnb/sfnp）→ "(Bombieri 2000)"；
    paren=False（harvtxt/harv）→ "Hardy (1914)"。"""
    if paren:
        core = (authors + " " + year).strip()
        if extra:
            core += ", " + extra
        # 前导空格，避免「mathematics.(Bombieri 2000)」粘在一起
        return " (%s)" % core
    core = authors
    if year:
        core += " (%s)" % year
    if extra:
        core += ", " + extra
    return core


def fmt_citation(pos, named):
    """{{citation}} / {{cite web}} / {{cite arXiv}} / {{cite report}} 等。"""
    authors = _join_authors(_author_bits(named))
    year = named.get("year") or named.get("date") or named.get("publication-date") or ""
    title = named.get("title") or named.get("chapter") or (pos[0] if pos else "")
    journal = named.get("journal") or named.get("work") or named.get("newspaper") or \
        named.get("website") or named.get("publisher") or named.get("institution") or ""
    volume = named.get("volume") or ""
    issue = named.get("issue") or ""
    pages = named.get("pages") or named.get("page") or ""
    doi = named.get("doi") or ""
    arxiv = named.get("arxiv") or named.get("eprint") or ""
    url = named.get("url") or ""
    isbn = named.get("isbn") or ""
    mr = named.get("mr") or ""
    parts = []
    if authors:
        parts.append(authors)
    if year:
        parts.append("(%s)" % year)
    head = " ".join(parts)
    bits = []
    if title:
        bits.append("*%s*" % title.strip("."))
    if journal:
        j = "*%s*" % journal
        if volume:
            j += " **%s**" % volume
            if issue:
                j += "(%s)" % issue
        if pages:
            j += ", %s" % pages
        bits.append(j)
    elif pages:
        bits.append(pages)
    if isbn:
        bits.append("ISBN %s" % isbn)
    if mr:
        bits.append("MR %s" % mr)
    if arxiv:
        bits.append("arXiv:%s" % arxiv)
    if doi:
        d = doi if doi.startswith("10.") else doi
        bits.append("doi:[%s](https://doi.org/%s)" % (d, urllib.parse.quote(d, safe="/.")))
    if url:
        bits.append("[%s](%s)" % (named.get("title") or "link", url))
    body = (head + ". " if head else "") + ". ".join(b for b in bits if b)
    return body.strip() + ("." if body and not body.endswith(".") else "")


def template_sub(name, pos, named, ctx):
    """返回模板展开后的文本；返回 None 表示「未知模板」。"""
    n = name.strip().lower().replace("_", " ")

    if n in DROP_TEMPLATES:
        return ""

    # ---- 短引用（作者-年份） -------------------------------------------------
    if n in ("harvtxt", "harvnb", "harvp", "sfnp", "sfn", "harv", "harvs", "harvcol",
             "harvcolnb", "harvtxtnb"):
        txt_flag = "txt" in [p.strip().lower() for p in pos]
        if n == "harvs" or txt_flag:
            last = named.get("last") or (pos[1] if len(pos) > 1 else "")
            first = named.get("first") or (pos[0] if pos else "")
            year = named.get("year") or ""
            who = ("%s %s" % (first, last)).strip() if last else first
            if txt_flag and not who:
                who = " ".join(p for p in pos if p.strip().lower() != "txt")
            out = "%s (%s)" % (who, year) if year else who
            return out
        # 其余：位置参数 [作者…, 年份, 定位]
        authors = [p.strip() for p in pos if p.strip() and not re.match(r"^\d{3,4}$", p.strip())]
        years = [p.strip() for p in pos if re.match(r"^\d{3,4}[a-z]?$", p.strip())]
        year = years[0] if years else ""
        extra = named.get("p") or named.get("pp") or named.get("loc") or named.get("page") or ""
        who = " & ".join(authors)
        paren = n not in ("harvtxt", "harv")
        return _harv_cite(who, year, extra, paren)

    # ---- 文献条目 -----------------------------------------------------------
    if n.startswith("cite ") or n in ("citation", "cite"):
        return fmt_citation(pos, named)

    # ---- 排版类 -------------------------------------------------------------
    if n == "nowrap":
        if named.get("1"):
            return named["1"]
        return pos[0] if pos else ""
    if n == "nobr":
        return pos[0] if pos else ""
    if n == "sfrac":
        if len(pos) >= 2:
            return "$%s/%s$" % (pos[0].strip(), pos[1].strip())
        return "$1/%s$" % (pos[0].strip() if pos else "2")
    if n == "frac":
        return "$%s/%s$" % (pos[0].strip(), pos[1].strip() if len(pos) > 1 else "1")
    if n == "math":
        body = named.get("1") or (pos[0] if pos else "")
        # 模板里常写 {{math|''q''}} —— 数学环境内没有斜体，去掉 '' / '''
        body = re.sub(r"''+", "", body)
        return "$%s$" % body.strip()
    if n == "mvar":
        return "$%s$" % (pos[0].strip() if pos else "")
    if n == "pi":
        return r"$\pi$"
    if n == "e":
        if pos:
            return "$e^{%s}$" % pos[0].strip()
        return "$e$"
    if n == "abs":
        return "$|%s|$" % (pos[0].strip() if pos else "")
    if n == "radic":
        return r"$\sqrt{%s}$" % (pos[0].strip() if pos else "")
    if n == "val":
        base = pos[0].strip() if pos else ""
        if named.get("e"):
            return r"$%s \times 10^{%s}$" % (base, named["e"])
        if len(pos) > 1:
            return "%s ± %s" % (base, pos[1].strip())
        return base
    if n == "gaps":
        return " ".join(p.strip() for p in pos if p.strip())
    if n == "10^":
        if len(pos) >= 2:
            return r"$%s \times 10^{%s}$" % (pos[1].strip(), pos[0].strip())
        return r"$10^{%s}$" % (pos[0].strip() if pos else "")
    if n == "sic":
        return "".join(p.strip() for p in pos if p.strip())
    if n == "lang":
        return pos[1].strip() if len(pos) > 1 else (pos[0].strip() if pos else "")
    if n == "isbn":
        return "ISBN %s" % (pos[0].strip() if pos else "")
    if n == "pipe":
        return "|"
    if n == "hsp":
        return " "
    if n == "slink":
        if len(pos) >= 2:
            return "[%s](%s)" % (pos[1].strip(), page_url(pos[0].strip() + "#" + pos[1].strip(),
                                                          ctx.get("lang", "en")))
        return "[%s](%s)" % (pos[0].strip(), page_url(pos[0].strip(), ctx.get("lang", "en")))
    if n in ("main", "see also", "further", "hatnote"):
        return ""
    if n in ("'", "′", "prime"):
        return "\u2032"
    if n == "=":
        return "="
    if n == "oeis":
        seq = (pos[0] if pos else "").strip()
        return "[%s](https://oeis.org/%s)" % (seq, urllib.parse.quote(seq, safe=""))
    if n == "mathscinet":
        mid = (named.get("id") or (pos[0] if pos else "")).strip()
        return "[MR %s](https://mathscinet.ams.org/mathscinet-getitem?mr=%s)" % (mid, mid)
    if n == "math theorem":
        thm = named.get("name") or ""
        stmt = named.get("math_statement") or named.get("statement") or ""
        out = ("**%s.** %s" % (thm.strip(), stmt.strip())) if thm else stmt.strip()
        return out
    if n in ("quote", "bquote", "blockquote", "cquote"):
        text = named.get("text") or named.get("1") or (pos[0] if pos else "")
        author = named.get("author") or ""
        src = named.get("title") or named.get("source") or ""
        text = text.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
        lines = ["> " + ln.strip() if ln.strip() else ">" for ln in text.split("\n")]
        tail = ", ".join(x for x in (author, "*%s*" % src if src else "") if x)
        if tail:
            lines.append(">")
            lines.append("> — " + tail)
        # 末尾补一个换行：两条 {{quote}} 相邻时，否则会并成同一个引用块
        return "\n".join(lines) + "\n"

    return None


TEMPLATE_RE = re.compile(r"\{\{")


def find_template(s, start=0):
    """找到从 start 起的第一个 {{…}}，返回 (start, end, name, raw_args) 或 None。"""
    m = TEMPLATE_RE.search(s, start)
    if not m:
        return None
    i = m.start()
    depth, j = 0, i
    while j < len(s):
        if s.startswith("{{", j):
            depth += 1
            j += 2
            continue
        if s.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                break
            continue
        j += 1
    if depth != 0:
        return None
    inner = s[i + 2:j - 2]
    name, _, raw = inner.partition("|")
    if not raw:
        raw = ""
    return i, j, name.strip(), raw


def expand_templates(text, ctx, depth=0):
    """递归展开模板；未知模板整块丢弃并计入 ctx['unknown']。"""
    if depth > 12:
        return text
    out, pos, changed = [], 0, False
    while True:
        found = find_template(text, pos)
        if not found:
            out.append(text[pos:])
            break
        i, j, name, raw = found
        out.append(text[pos:i])
        pos_args, named = parse_args(raw)
        repl = template_sub(name, pos_args, named, ctx)
        if repl is None:
            ctx["unknown"][name.strip().lower()] = ctx["unknown"].get(name.strip().lower(), 0) + 1
            repl = ""
        out.append(repl)
        pos = j
        changed = True
    result = "".join(out)
    if changed and "{{" in result:
        return expand_templates(result, ctx, depth + 1)
    return result


# --------------------------------------------------------------------------- 脚注

REF_RE = re.compile(r"<ref\b([^>]*?)/(?!\w)>|<ref\b([^>]*?)>(.*?)</ref>", re.S | re.I)


class Footnotes:
    def __init__(self):
        self.items = []   # [(num, text)]
        self.by_name = {}

    def add(self, attrs, body):
        name = None
        if attrs:
            m = re.search(r'name\s*=\s*"?([^">/]+)"?', attrs, re.I)
            if m:
                name = m.group(1).strip()
        if name and name in self.by_name:
            return self.by_name[name]
        self.items.append((len(self.items) + 1, body))
        num = len(self.items)
        if name:
            self.by_name[name] = num
        return num


def extract_refs(text, ctx):
    """把 <ref>…</ref> 抽成占位符，返回 (文本, Footnotes)。"""
    notes = Footnotes()

    def repl(m):
        if m.group(1) is not None:      # <ref ... />
            num = notes.add(m.group(1), "")
        else:
            num = notes.add(m.group(2), m.group(3) or "")
        return "\x02REF%d\x03" % num

    return REF_RE.sub(repl, text), notes


# --------------------------------------------------------------------------- 数学

def is_display_math(match, text, attrs):
    """判断 <math> 是行间公式还是行内公式。

    MediaWiki 的约定：
      * <math display="inline">…</math>            → 行内
      * <math display="block"> / <math display>    → 行间
      * 裸 <math>…</math>                          → 独占一行时视为行间，否则行内
    注意不能只看 attrs 里有没有 "display" 字样：display="inline" 是行内。
    """
    a = (attrs or "").strip()
    if re.search(r'display\s*=\s*["\']?\s*inline', a, re.I):
        return False
    if re.search(r"\bdisplay\b", a):
        return True
    # 裸 <math>：按是否独占一行来判定（行首的 : / * / # / ; 是缩进和列表标记，不算内容）
    bol = text.rfind("\n", 0, match.start()) + 1
    eol = text.find("\n", match.end())
    if eol == -1:
        eol = len(text)
    before = re.sub(r"^[\s:;*#-]*", "", text[bol:match.start()])
    after = text[match.end():eol].strip()
    return before == "" and after == ""


def extract_math(text):
    """<math> → 占位符，返回 (文本, [(display, latex)])。"""
    store = []

    def repl(m):
        attrs, body = m.group(1), m.group(2)
        store.append((is_display_math(m, text, attrs), body.strip()))
        return "\x02MATH%d\x03" % (len(store) - 1)

    return MATH_RE.sub(repl, text), store


def render_math(display, latex, block_wrap=False):
    """display=True 时输出三行 $$…$$；block_wrap=True 额外用空行把它独立成段。"""
    latex = latex.strip()
    if display or "\n" in latex:
        body = "$$\n%s\n$$" % latex
        return "\n\n%s\n\n" % body if block_wrap else body
    return "$%s$" % latex


# --------------------------------------------------------------------------- 表格

def strip_cell_attrs(cell):
    """去掉 style="…"| 之类单元格属性，返回纯内容。"""
    head, sep, tail = cell.partition("|")
    if sep and re.match(r"^\s*[a-zA-Z-]+\s*=", head):
        return tail
    return cell


def split_row(s, sep):
    out, cur, depth, i = [], [], 0, 0
    while i < len(s):
        if s.startswith("{{", i) or s.startswith("[[", i):
            depth += 1
            cur.append(s[i:i + 2])
            i += 2
            continue
        if s.startswith("}}", i) or s.startswith("]]", i):
            depth -= 1
            cur.append(s[i:i + 2])
            i += 2
            continue
        if s.startswith(sep, i) and depth == 0:
            out.append("".join(cur))
            cur = []
            i += len(sep)
            continue
        cur.append(s[i])
        i += 1
    out.append("".join(cur))
    return out


def convert_table(block):
    """wikitable → GFM 表格。表头单元格（!）合并成一行。"""
    rows, hdr, cur, i = [], [], [], 1
    lines = block.split("\n")

    def flush():
        if hdr:
            rows.append((True, list(hdr)))
            hdr.clear()
        if cur:
            rows.append((False, list(cur)))
            cur.clear()

    while i < len(lines):
        s = lines[i].strip()
        i += 1
        if s.startswith("|}"):
            break
        if not s:
            continue
        if s.startswith("|-"):
            flush()
            continue
        if s.startswith("!"):
            if cur:                      # 表头出现在数据行之后，先收尾
                rows.append((False, list(cur)))
                cur = []
            hdr.extend(strip_cell_attrs(c) for c in split_row(s[1:], "!!"))
            continue
        if s.startswith("|"):
            cur.extend(strip_cell_attrs(c) for c in split_row(s[1:], "||"))
            continue
        # 单元格的多行续写
        if cur:
            cur[-1] += " " + s
        elif hdr:
            hdr[-1] += " " + s
    flush()

    if not rows:
        return ""
    ncol = max(len(r[1]) for r in rows)
    out = []
    for is_head, cells in rows:
        cells = [clean_ws(c).replace("|", "\\|") or " " for c in cells]
        cells += [" "] * (ncol - len(cells))
        out.append("| " + " | ".join(cells) + " |")
        if is_head:
            out.append("| " + " | ".join(["---"] * ncol) + " |")
    # GFM 要求第一行为表头；原文没有 ! 行时把首行当作表头
    if len(out) >= 2 and not re.match(r"^\|[\s\-|]+\|$", out[1]):
        out.insert(1, "| " + " | ".join(["---"] * ncol) + " |")
    return "\n".join(out)


TABLE_RE = re.compile(r"^\{\|.*?^\|\}", re.S | re.M)


# --------------------------------------------------------------------------- 主转换

EXT_LINK_RE = re.compile(r"\[(https?://[^\s\]]+)\s+([^\[\]]*)\]")
GALLERY_RE = re.compile(r"<gallery\b[^>]*>(.*?)</gallery>", re.S | re.I)
BOLD_ITALIC_RE = re.compile(r"'''''(.+?)'''''", re.S)
BOLD_RE = re.compile(r"'''(.+?)'''", re.S)
ITALIC_RE = re.compile(r"''(.+?)''", re.S)

# [[File:…]] 里需要丢掉的排版参数
FILE_OPTION_RE = re.compile(
    r"^\s*(thumb|thumbnail|frame|frameless|border|left|right|center|none|"
    r"\d*\.?\d*\s*(px|em|%)|upright\s*(=\s*[\d.]+)?|alt\s*=.*|link\s*=.*|"
    r"class\s*=.*|page\s*=\s*\d+|lang\s*=.*)\s*$",
    re.I,
)


def convert_links(text, lang="en", title=None):
    """把 [[…]] 转成 Markdown 链接/图片。用括号配对扫描，标签里允许嵌套 [ ]。"""
    out, i, n = [], 0, len(text)
    while i < n:
        start = text.find("[[", i)
        if start < 0:
            out.append(text[i:])
            break
        depth, j = 0, start
        while j < n:
            if text.startswith("[[", j):
                depth += 1
                j += 2
                continue
            if text.startswith("]]", j):
                depth -= 1
                j += 2
                if depth == 0:
                    break
                continue
            j += 1
        if depth != 0:
            out.append(text[i:])
            break
        out.append(text[i:start])
        out.append(render_wikilink(text[start + 2:j - 2], lang, title))
        i = j
    return "".join(out)


def render_wikilink(inner, lang="en", title=None):
    parts = split_args(inner)
    target = parts[0].strip()
    if not target:
        return ""
    label = parts[-1].strip() if len(parts) > 1 else target
    # [[#章节|文字]]：本页内部锚点
    if target.startswith("#"):
        anchor = target[1:].strip()
        text_bit = clean_ws(convert_links(label, lang, title)) if len(parts) > 1 else anchor
        if not title:
            return text_bit
        return "[%s](%s#%s)" % (text_bit, page_url(title, lang),
                                urllib.parse.quote(anchor.replace(" ", "_"), safe="/"))
    if FILE_NS.match(target):
        caps = [p for p in parts[1:] if p.strip() and not FILE_OPTION_RE.match(p)]
        cap = clean_ws(convert_links(" ".join(caps), lang)) if caps else ""
        return "![%s](%s)" % (cap or target.split(":", 1)[-1], file_url(target))
    if SKIP_LINK_NS.match(target):
        return ""
    label = clean_ws(convert_links(label, lang, title))
    return "[%s](%s)" % (label or target, page_url(target, lang))


def wiki_inline(text, lang="en", title=None):
    """处理链接、粗斜体等行内标记。"""
    text = EXT_LINK_RE.sub(lambda m: "[%s](%s)" % ((m.group(2) or "link").strip(), m.group(1)), text)
    text = convert_links(text, lang, title)
    text = BOLD_ITALIC_RE.sub(r"***\1***", text)
    text = BOLD_RE.sub(r"**\1**", text)
    text = ITALIC_RE.sub(r"*\1*", text)
    return text


def convert(wikitext, lang="en", title=None):
    ctx = {"unknown": {}, "lang": lang, "title": title}
    text = wikitext

    # 0. 去掉注释与分类
    text = COMMENT_RE.sub("", text)
    text = re.sub(r"^\[\[Category:[^\]]*\]\]\s*$", "", text, flags=re.M)

    # 1. 保护数学
    text, maths = extract_math(text)

    # 2. 展开模板
    text = expand_templates(text, ctx)

    # 3. 抽取脚注
    text, notes = extract_refs(text, ctx)

    # 4. 图库
    def gallery_repl(m):
        items = []
        for line in m.group(1).split("\n"):
            line = line.strip()
            if not line:
                continue
            name, _, cap = line.partition("|")
            name = name.strip()
            if not name:
                continue
            cap = clean_ws(wiki_inline(expand_templates(cap, ctx), lang, title))
            items.append("![%s](%s)" % (cap or name, file_url(name)))
        return "\n\n" + "\n\n".join(items) + "\n\n"

    text = GALLERY_RE.sub(gallery_repl, text)

    # 5. 表格（先于行内处理，避免 | 被误伤）
    def table_repl(m):
        return "\x02TABLE%d\x03" % _store(ctx, "tables", convert_table(m.group(0)))

    text = TABLE_RE.sub(table_repl, text)

    # 6. 行内标记
    text = wiki_inline(text, lang, title)

    # 7. 分块处理：标题 / 列表 / 段落
    out_lines = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()

        m = re.match(r"^(={2,6})\s*(.+?)\s*\1\s*$", stripped)
        if m:
            level = min(len(m.group(1)), 6)
            out_lines.append("")
            out_lines.append("#" * level + " " + clean_ws(m.group(2)))
            out_lines.append("")
            continue

        if stripped.startswith(("*", "#", ":", ";")):
            # 标记后必须有空白，否则行首的 **粗体** 会被误判成列表
            m2 = re.match(r"^([#*:;]+)(?:\s+(.*))?$", stripped)
            if m2:
                marks, rest = m2.group(1), (m2.group(2) or "")
                text_bit = clean_ws(rest)
                if marks.endswith("*"):
                    out_lines.append(("  " * (len(marks) - 1) + "* " + text_bit).rstrip())
                elif marks.endswith("#"):
                    out_lines.append(("   " * (len(marks) - 1) + "1. " + text_bit).rstrip())
                elif marks.endswith(":"):
                    out_lines.append(("  " * len(marks) + text_bit).rstrip())
                else:
                    out_lines.append(text_bit)
                continue

        if not stripped:
            out_lines.append("")
            continue

        out_lines.append(clean_ws(stripped))

    body = "\n".join(out_lines)

    # 8. 还原表格（单元格内容同样要过一遍行内标记）
    for idx, tbl in enumerate(ctx.get("tables", [])):
        body = body.replace("\x02TABLE%d\x03" % idx, wiki_inline(tbl, lang, title))

    # 9. 还原脚注标记
    body = re.sub(r"\x02REF(\d+)\x03", lambda m: "[^%s]" % m.group(1), body)

    # 10. 还原数学
    def math_repl(m):
        display, latex = maths[int(m.group(1))]
        return render_math(display, latex, block_wrap=True)

    body = re.sub(r"\x02MATH(\d+)\x03", math_repl, body)

    # 11. 一行的 $$…$$ remark-math 会当成行内公式，统一收成 $…$
    body = re.sub(r"\$\$(?!\n)([^\n$]+)\$\$", r"$\1$", body)

    # 12. <blockquote> → Markdown 引用块
    body = re.sub(
        r"<blockquote\b[^>]*>(.*?)</blockquote>",
        lambda m: "\n".join("> " + ln.strip() if ln.strip() else ">"
                             for ln in m.group(1).strip().split("\n")),
        body, flags=re.S | re.I)

    # 13. HTML 实体与残余标签
    body = html.unescape(body)
    # 注意：这里只删「整块就是标签」的 <big>/<li>/<e>，绝不能写成
    # </?(?:…|e)\b[^>]*>——公式里的 `<e^\gamma` 会被当成标签，吞掉后面一大段正文。
    body = re.sub(r"</?(?:big|li)\b[^>]*>", "", body, flags=re.I)
    body = re.sub(r"<[/]?e\s*>", "", body, flags=re.I)
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body)

    # 12. 脚注定义
    lines = body.rstrip().split("\n")
    # 在 Notes 标题后插入脚注定义
    notes_block = []
    if notes.items:
        for num, txt in notes.items:
            t = clean_ws(wiki_inline(txt, lang, title))
            t = re.sub(r"\x02MATH(\d+)\x03", lambda m: render_math(*maths[int(m.group(1))]), t)
            t = html.unescape(t)
            notes_block.append("[^%d]: %s" % (num, t or "—"))
    notes_text = "\n".join(notes_block)

    # 找 Notes 段
    inserted = False
    for i, ln in enumerate(lines):
        if re.match(r"^#{1,6}\s*Notes\s*$", ln):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            lines[j:j] = ["", notes_text]
            inserted = True
            break
    if not inserted:
        lines += ["", "## Notes", "", notes_text]
    body = "\n".join(lines).strip() + "\n"

    # 13. MDX / GitHub 兼容
    body = escape_dollar_in_urls(body)
    body = fix_github_math(body)
    body = escape_mdx_braces(body)

    if title:
        body = "---\ntitle: %s\n---\n\n%s" % (title, body)
    return body, ctx


def _store(ctx, key, value):
    ctx.setdefault(key, []).append(value)
    return len(ctx[key]) - 1


# --------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="wikitext2md.py",
        description="纯机械地把维基 wikitext 转成 Markdown（保留原文语言，不翻译）",
    )
    ap.add_argument("url", nargs="?", help="维基百科词条链接（与 --input 二选一）")
    ap.add_argument("--input", help="本地 wikitext 文件（与 url 二选一）")
    ap.add_argument("-o", "--output", help="输出 Markdown 路径")
    ap.add_argument("--title", help="front matter 标题（默认取词条名）")
    ap.add_argument("--lang", default="en", help="源语言代码，默认 en")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="只输出到 stdout")
    ap.add_argument("--report", action="store_true", help="打印未识别模板统计")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            wikitext = fh.read()
        title = args.title or os.path.splitext(os.path.basename(args.input))[0].replace("_", " ")
        lang = args.lang
    elif args.url:
        lang, page = parse_wiki_url(args.url)
        cache = Cache(enabled=not args.no_cache)
        real_title, wikitext = fetch_wikitext(lang, page, cache)
        title = args.title or real_title
    else:
        raise SystemExit("需要给出词条链接或 --input")

    log("→ wikitext %d 字符" % len(wikitext), args.quiet)
    body, ctx = convert(wikitext, lang=lang, title=title)
    log("→ Markdown %d 字符" % len(body), args.quiet)

    if args.report and ctx["unknown"]:
        log("! 未识别模板（已丢弃）：", args.quiet)
        for name, cnt in sorted(ctx["unknown"].items(), key=lambda kv: -kv[1]):
            log("    %-32s %d" % (name, cnt), args.quiet)

    if args.dry_run or not args.output:
        sys.stdout.write(body)
        return 0

    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(body.replace("\n", "\r\n").encode("utf-8"))
    log("✓ 已写入 %s" % out_path, args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
