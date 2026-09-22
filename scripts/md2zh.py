#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把英文维基 Markdown 条目译成目标语言 Markdown（默认简体中文，支持泰语）。

和 wiki2md.py 的区别：wiki2md 是「wikitext → LLM → 中文 md」一步到位，本脚本
只读已经是 Markdown 的英文稿（通常是 en.chinapedia 里的产物），只做翻译，不再碰
wikitext。这样英文稿可以先用 wikitext2md.py 机械校一遍，再单独调翻译。

用法：
    # 中文（默认）
    python scripts/md2zh.py D:/SRC/Z/en.chinapedia/docs/math/riemann_zeta_function.md \
        -o docs/math/黎曼ζ函数.md --base-url https://lms.thaiwen.com/v1

    # 泰语
    python scripts/md2zh.py D:/SRC/Z/en.chinapedia/docs/math/riemann_zeta_function.md \
        -o .../riemann_zeta_function.md --to th --base-url https://lms.thaiwen.com/v1

要点：
  * 公式（$…$ / $$…$$）、链接、脚注编号、图片、表格结构原样保留，只译散文。
  * 脚注定义（[^n]: …）默认保留英文——参考文献本来就该留原文。
  * 默认 reasoning_effort=none；翻译任务不需要思维链，开了会慢一个数量级。
  * 已译过的 chunk 存在 --state 里，中断后重跑会接着来。

加一门语言只要往 LANGS 里加一项（提示词 + 术语表 + 语言特有约定），
下面的切块/占位符/脚注对账/行数幻觉检测那套流程完全复用。
"""

import argparse
import collections
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wiki2md as W  # noqa: E402  （复用 provider 解析与 llm_chat）


ZH_SYSTEM = """你是资深数学/百科译者，把英文维基百科条目译成简体中文。

硬性规则：
1. 逐句翻译，不要省略、不要概括、不要自己补充内容。
2. 保留 Markdown 结构：标题的 # 层级、列表标记、引用块 >、粗体 **、表格的 | 分隔。
3. 公式原样不动：$…$ 和 $$…$$ 里的 LaTeX 一个字符都不要改，也不要增删 $。
4. 保留 [文字](URL) 链接——URL 不译，链接文字译成中文。
5. 保留 [^n] 脚注标记，编号不要变。
6. 数学术语按中文习惯：analytic continuation→解析延拓，meromorphic→亚纯，
   holomorphic→全纯，critical strip→临界带，trivial zeros→平凡零点，
   Dirichlet series→狄利克雷级数，Euler product→欧拉乘积。
7. 人名、地名、期刊名、书名保留原文或通用中译，不要音译生造。
8. **不要把行内链接改成脚注**：[文字](§U0§) 这样的链接保持原样，只把「文字」译
   成中文；§U0§ 是 URL 占位符，原封不动照抄，不要增删字符。
9. 不要新增、删除或重排脚注标记：§F3§ 是脚注占位符，原封不动照抄。
10. 不要漏译任何一行，包括单独成行的 where / for / if / and 这类短词。

文风规则：
* 词条开头用中文百科式写法：「**词条名**（英语：English name），是指……」。
* 长从句拆散按中文习惯重排，不要保留 "whose … and whose …" 式的连环定语。
* 正文里的外文原文引文（德文、法文、拉丁文）只留中文译文，不要附原文。

只输出译文正文，不要写「以下是译文」之类的开场白，不要包 ``` 代码块。"""


TH_SYSTEM = """你是资深数学/百科译者，把英文维基百科条目译成泰语（ภาษาไทย）。

硬性规则：
1. 逐句翻译，不要省略、不要概括、不要自己补充内容。
2. 保留 Markdown 结构：标题的 # 层级、列表标记、引用块 >、粗体 **、表格的 | 分隔。
3. 公式原样不动：$…$ 和 $$…$$ 里的 LaTeX 一个字符都不要改，也不要增删 $。
4. 保留 [文字](URL) 链接——URL 不译，链接文字按规则 6、7 处理
   （普通名词、概念一律译成泰语，只有人名这类专有名词才留拉丁字母）。
5. 保留 [^n] 脚注标记，编号不要变。
6. 数学术语优先用泰语学术界的通用说法（จำนวนเฉพาะ = prime number、
   ฟังก์ชันซีตา = zeta function、การลู่เข้า = convergence）。
   **只有在泰语里确实找不到通行说法时**才保留英文原文——不要因为「不确定」就整词留
   英文，也不要生造泰语词、不要按发音硬拼成泰文字母。
7. 人名、地名、机构名、期刊名、书名保留拉丁字母原文，不要音译生造。
8. **不要把行内链接改成脚注**：[文字](§U0§) 这样的链接保持原样，只把「文字」译
   成泰语；§U0§ 是 URL 占位符，原封不动照抄，不要增删字符。
9. 不要新增、删除或重排脚注标记：§F3§ 是脚注占位符，原封不动照抄。
10. 不要漏译任何一行，包括单独成行的 where / for / if / and 这类短词。
11. **同一术语在同一篇里必须译法一致**：第一次选定译法后后文一律沿用
    （不要一处 อักขระ、一处 ตัวอักษร）。

文风规则：
* 词条开头用泰语百科式写法：「**ชื่อเรื่อง** (English name) คือ……」。
* 长从句按泰语习惯重排（定语后置、用 ที่ / ซึ่ง 连接），不要保留英文式连环定语。
* 正文里的外文原文引文（德文、法文、拉丁文）只留泰语译文，不要附原文。
* 泰语正文本身不分词、不加空格，但**英文单词与 $…$ 公式两侧原有的空格必须保留**，
  否则 Markdown 行内元素会粘在一起。

只输出译文正文，不要写开场白，不要包 ``` 代码块。"""


ZH_TITLE_SYSTEM = "把英文维基百科条目的标题译成简体中文。只输出一个短标题，不要标点、不要解释。"
TH_TITLE_SYSTEM = "把英文维基百科条目的标题译成泰语。只输出一个短标题，不要标点、不要解释。"

# 单独送一个标题进去，模型会「补全」出整节内容——26~57 行的幻觉，全是无中生有。
# 标题必须用专门的提示词，且只要一行。
ZH_HEADING_SYSTEM = ("把英文维基百科条目的小节标题译成简体中文。"
                     "只输出一行中文标题，前面照抄原文的 # 号个数。"
                     "不要解释，不要补充，不要另起段落。")
TH_HEADING_SYSTEM = ("把英文维基百科条目的小节标题译成泰语。"
                     "只输出一行泰语标题，前面照抄原文的 # 号个数。"
                     "不要解释，不要补充，不要另起段落。")

# 向后兼容：老调用方 import 的仍然是中文那套
SYSTEM = ZH_SYSTEM
TITLE_SYSTEM = ZH_TITLE_SYSTEM
HEADING_SYSTEM = ZH_HEADING_SYSTEM


# --------------------------------------------------------------------------- 术语表
# 模型译专有名词很不稳：Riemann's xi function 会变成「黎曼的 xi 函数」，
# Mellin transform 会留下「Mellin」，Theta function 留下「Theta」。
# 中文维基的条目名就是权威译名，用 scripts/wikiterm.py 抓下来存成 JSON，
# 翻译时按 chunk 挑出命中的词条塞进提示词，让它照着译。
_HERE = os.path.dirname(os.path.abspath(__file__))
ZH_TERMS_FILE = os.path.join(_HERE, "wiki-zh-terms.json")
# 人名子集：只收「en.wikipedia 确实有中文 langlink」的人名（wikiterm.py
# --verify-people 生成）。术语表里带「·」的条目默认全丢，但那样会连
# 「Helmut Hasse → 赫尔穆特·哈斯」这种中文维基真有条目的也一起丢掉，
# 于是正文里就留下没译的 Helmut Hasse。这里改用「来源证明」判断。
ZH_PEOPLE_FILE = os.path.join(_HERE, "wiki-zh-terms-people.json")
# 泰语术语表：同样从 en.wikipedia 的 langlinks 抓，只是 lllang=th
# （wikiterm.py --lang th）。泰语条目名不需要简繁转换那一步。
TH_TERMS_FILE = os.path.join(_HERE, "wiki-th-terms.json")

# 向后兼容
TERMS_FILE = ZH_TERMS_FILE
PEOPLE_FILE = ZH_PEOPLE_FILE

MAX_TERMS = 25  # 提示词里最多塞多少条，多了会把本地模型拖慢


# --------------------------------------------------------------------------- 语言
# 每种目标语言一套：提示词 + 术语表 + 若干语言特有的约定。
# 新增语言只要往这里加一项，不用碰下面的流程代码。
LANGS = {
    "zh": {
        "label": "简体中文",
        "system": ZH_SYSTEM,
        "title_system": ZH_TITLE_SYSTEM,
        "heading_system": ZH_HEADING_SYSTEM,
        "ask_prefix": "翻译成简体中文：\n\n",
        "terms_file": ZH_TERMS_FILE,
        "people_file": ZH_PEOPLE_FILE,
        "terms_label": "中文译名",
        # 「·」人名白名单是中文专有的（音译人名用间隔号）。
        # 泰语的人名译法不用间隔号，套这个过滤只会误删术语。
        "people_filter": True,
        "default_title": "未命名",
    },
    "th": {
        "label": "泰语",
        "system": TH_SYSTEM,
        "title_system": TH_TITLE_SYSTEM,
        "heading_system": TH_HEADING_SYSTEM,
        "ask_prefix": "翻译成泰语：\n\n",
        "terms_file": TH_TERMS_FILE,
        "people_file": None,
        "terms_label": "泰语译名",
        "people_filter": False,
        "default_title": "ไม่มีชื่อ",
    },
}


def load_people(path=None):
    """读人名子集，返回 {英文名} 集合。文件不存在就返回空集（退回全过滤）。"""
    path = path or PEOPLE_FILE
    if not os.path.exists(path):
        return set()
    try:
        with open(path, encoding="utf-8") as fh:
            return set(json.load(fh))
    except Exception:                                    # noqa: BLE001
        return set()


def load_terms(path, quiet=False, people=False, L=None):
    L = L or LANGS["zh"]
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:                             # noqa: BLE001
        print("术语表加载失败（忽略）: %s" % exc)
        return {}
    # 英文名和目标语言名一样的条目没有意义，丢掉
    data = {k: v for k, v in data.items()
            if v and k and v.strip() and v.strip() != k.strip()}
    # 人名（中文译名里带间隔号「·」）默认要过滤：术语表里的人名多半来自
    # Wikidata 兜底，质量很差（Andrew Granville → 安德鲁·关维）。
    # 但「过滤人名」不能一刀切 —— 有中文维基条目的（langlinks 来源）是权威译名，
    # 丢掉只会让正文里留下没译的 Helmut Hasse。所以改成白名单：
    # 只有出现在 wiki-zh-terms-people.json 里的人名才放行。
    # 术语名不会带间隔号（黎曼ξ函数 / 梅林变换 / 互素 / 自然对数）。
    # 这套规则是中文专有的，别的语言用 L["people_filter"] 关掉。
    if not people and L["people_filter"]:
        allowed = load_people(L.get("people_file"))
        data = {k: v for k, v in data.items()
                if "\u00b7" not in v or k in allowed}
    if not quiet:
        extra = ""
        if not people and L["people_filter"]:
            n_people = sum(1 for v in data.values() if "\u00b7" in v)
            extra = "（人名只保留 %d 条有中文条目的）" % n_people
        print("→ 术语表 %s：%d 条%s"
              % (os.path.basename(path), len(data), extra))
    return data


def norm_en(s):
    """归一化英文：小写、去掉所有格、非字母数字都变空格。

    这样 "Riemann's xi function" 和术语表里的 "Riemann xi function" 才能对上。
    """
    s = s.lower().replace("\u2019", "'")
    s = re.sub(r"'s\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " " + " ".join(s.split()) + " "


def _hits(term, norm_text):
    """术语（可能多个词）是否出现在文本里；顺带认单复数。"""
    nt = norm_en(term).strip()
    if not nt:
        return False
    for cand in (nt, nt + "s", nt + "es"):
        if (" " + cand + " ") in norm_text:
            return True
    return False


def pick_terms(text, terms, limit=MAX_TERMS):
    """挑出这段文本里真正出现的术语，长词优先（避免被短词抢掉）。"""
    if not terms:
        return []
    norm_text = norm_en(text)
    hit = [t for t in terms if _hits(t, norm_text)]
    hit.sort(key=len, reverse=True)
    return hit[:limit]


def terms_block(text, terms, L=None):
    """把命中的术语拼成提示词片段。"""
    L = L or LANGS["zh"]
    hit = pick_terms(text, terms)
    if not hit:
        return ""
    rows = "\n".join("- %s → %s" % (t, terms[t]) for t in hit)
    return ("\n\n【术语表】下面这些英文名必须照右边给的%s来译，"
            "不要音译、不要直译、不要自己另起一个译名：\n" % L["terms_label"] + rows)


def system_with(text, terms, base=None, L=None):
    L = L or LANGS["zh"]
    return (base or L["system"]) + terms_block(text, terms, L)


# --------------------------------------------------------------------------- 切块

def split_blocks(lines):
    """把 Markdown 切成 (kind, [lines]) 序列；kind ∈ {verbatim, text}。

    verbatim：原样照抄，不送翻译（公式块、图片、脚注定义、表格、front matter）。
    text    ：要翻译的段落。
    """
    blocks, i, n = [], 0, len(lines)
    in_math = False
    while i < n:
        line = lines[i]
        s = line.strip()

        if s == "$$":                                   # 行间公式：整块原样
            j = i + 1
            while j < n and lines[j].strip() != "$$":
                j += 1
            j = min(j + 1, n)
            blocks.append(("verbatim", lines[i:j]))
            i = j
            continue
        if not in_math and s.startswith("$$"):          # 一行写完的 $$…$$
            blocks.append(("verbatim", [line]))
            i += 1
            continue
        if s.startswith("[^") and re.match(r"^\[\^\d+\]:", s):   # 脚注定义：留英文
            j = i + 1
            while j < n and lines[j].strip() and not re.match(r"^\[\^\d+\]:", lines[j].strip()):
                j += 1                                  # 续行（缩进的补充文字）
            blocks.append(("verbatim", lines[i:j]))
            i = j
            continue
        if s.startswith("![") or s.startswith("|"):     # 图片 / 表格
            j = i + 1
            while j < n and lines[j].strip().startswith("|"):
                j += 1
            blocks.append(("verbatim", lines[i:j]))
            i = j
            continue
        # 整行就是一个 HTML/JSX 标签（<figure …>、<figcaption>、</figure>、
        # <div className="figure-row">、<img … />）→ 原样照抄。
        # 不能交给模型：实测单行 <figcaption> 会被"解释"成
        # `**<figcaption>** (caption) คือข้อความที่ใช้อธิบายภาพหรือตาราง` 这种定义句。
        if re.fullmatch(r"</?[A-Za-z][^<>]*/?>", s):
            blocks.append(("verbatim", [line]))
            i += 1
            continue
        if s == "---" and i < 3:                        # front matter
            j = i + 1
            while j < n and lines[j].strip() != "---":
                j += 1
            j = min(j + 1, n)
            blocks.append(("front", lines[i:j]))
            i = j
            continue
        if not s:
            blocks.append(("verbatim", [line]))
            i += 1
            continue
        blocks.append(("text", [line]))
        i += 1
    return blocks


def pack(blocks, limit):
    """把连续的 text 块攒成不超过 limit 字符的 chunk。"""
    chunks, buf, start = [], [], 0
    for idx, (kind, ls) in enumerate(blocks):
        if kind != "text":
            if buf:
                chunks.append((start, buf))
                buf = []
            continue
        if not buf:
            start = idx
        buf.append((idx, ls))
        if sum(len(x[1][0]) for x in buf) >= limit:
            chunks.append((start, buf))
            buf = []
    if buf:
        chunks.append((start, buf))
    return chunks


# --------------------------------------------------------------------------- 翻译

# 送进模型之前把 URL 和脚注编号换成占位符。模型会把 analytic_number_theory 里的
# 下划线「顺手」改成空格，也会把行内链接改写成脚注、把编号重排——占位符让它没得改。
_URL_RE = re.compile(r"https?://[^\s()<>\[\]|]+")
_FN_RE = re.compile(r"\[\^(\d+)\]")


def protect(text):
    urls = []

    def u(m):
        urls.append(m.group(0))
        return "§U%d§" % (len(urls) - 1)

    text = _URL_RE.sub(u, text)
    text = _FN_RE.sub(lambda m: "§F%s§" % m.group(1), text)
    return text, urls


def restore(text, urls):
    # 模型偶尔把 §F2§ 写成 [^F2^] 之类，先把这些变形救回来
    text = re.sub(r"\[\^?\s*F\s*(\d+)\s*\^?\]", r"§F\1§", text)
    text = re.sub(r"§\s*U\s*(\d+)\s*§",
                  lambda m: urls[int(m.group(1))] if int(m.group(1)) < len(urls) else "",
                  text)
    text = re.sub(r"§\s*F\s*(\d+)\s*§", lambda m: "[^%s]" % m.group(1), text)
    text = re.sub(r"(?<!\^)\^\[(\d+)\](?!\()", r"[^\1]", text)   # ^[2] → [^2]
    return text


def fix_footnotes(line, src):
    """脚注标记以原文为准：多出来的删掉，少了的补上。

    9B 模型会在译文里自己编脚注（编号还跟真脚注撞车，真脚注就被顶掉了），
    所以要逐行对账。

    标签**不限于数字**：实测泰语译文会凭空补一个字面 `[^n]`（页面上原样显示、
    还点不动）。非数字标签在原稿里从来不存在（全站 9729 篇 + en 仓实测 0 处），
    所以 allow 里查不到就必然删除。
    """
    allow = collections.Counter(re.findall(r"\[\^([^\[\]]+)\]", src))
    used = collections.Counter()

    def rep(m):
        n = m.group(1)
        if used[n] < allow.get(n, 0):
            used[n] += 1
            return "[^%s]" % n
        return ""

    return re.sub(r"\[\^([^\[\]]+)\]", rep, line)


_MD_LINK_RE = re.compile(r"(?<!!)\[([^\[\]]+)\]\(([^()\s]+)\)")


def term_index(terms):
    """小写英文名 → 目标语言译名。"""
    return {k.strip().lower(): v for k, v in terms.items()}


def enforce_terms_in_links(line, index):
    """链接显示文字与术语表条目**完全相等**时，强制换成术语表给的译名。

    9B 模型会把 `[complex conjugate](url)` 的显示文字原样留英文——哪怕提示词里
    已经给了「complex conjugate → สังยุค」。这里做一次确定性替换，让术语表真的
    生效。只在整体相等时替换（不做子串替换，避免误伤）；
    URL 里带括号的链接直接跳过（正则抓不完整，宁可不改）。
    """
    if not index:
        return line

    def rep(m):
        text, url = m.group(1), m.group(2)
        hit = index.get(text.strip().lower())
        return "[%s](%s)" % (hit, url) if hit else m.group(0)

    return _MD_LINK_RE.sub(rep, line)


def clean_reply(text):
    """去掉模型偶尔加的 ```markdown 围栏和开场白。"""
    t = text.strip()
    t = re.sub(r"^```(?:markdown|md)?\s*\n", "", t)
    t = re.sub(r"\n```\s*$", "", t)
    t = re.sub(r"^(以下是译文|译文如下|翻译结果)[::]?\s*\n", "", t)
    return t.strip("\n")


# 标题提示词已上移到文件顶部（LANGS 要用），这里不再重复定义。
# 单独送一个标题进去，模型会「补全」出整节内容——26~57 行的幻觉，全是无中生有。
# 标题必须用专门的提示词，且只要一行。


def _ask(cfg, system, text, L=None):
    L = L or LANGS["zh"]
    safe, urls = protect(text)
    reply = W.llm_chat(cfg,
                       [{"role": "system", "content": system},
                        {"role": "user", "content": text_prompt(safe, L)}],
                       temperature=0.2, timeout=900)
    return restore(clean_reply(reply), urls)


def text_prompt(safe, L=None):
    L = L or LANGS["zh"]
    return L["ask_prefix"] + safe


def translate_line(cfg, line, terms=None, L=None):
    """逐行翻译兜底：保证一行进、一行出。"""
    L = L or LANGS["zh"]
    try:
        out = _ask(cfg, system_with(line, terms, L=L), line, L)
    except Exception:                                    # noqa: BLE001
        return line
    first = [l for l in out.split("\n") if l.strip()]
    if not first:
        return line
    return first[0]


def translate_chunk(cfg, text, tries=3, terms=None, L=None):
    L = L or LANGS["zh"]
    lines = text.split("\n")
    n = len(lines)

    # 整块只有一个标题 → 走标题专用提示词，绝不让它自由发挥
    if n == 1 and re.match(r"^#{1,6}\s", lines[0]):
        try:
            out = _ask(cfg, system_with(lines[0], terms,
                                        L["heading_system"], L),
                       "只译这个标题，输出一行：\n\n" + lines[0], L)
        except Exception:                                # noqa: BLE001
            return lines[0]
        got = [l for l in out.split("\n") if l.strip()]
        return got[0] if got else lines[0]

    system = system_with(text, terms, L=L)
    safe, urls = protect(text)
    # 小段落不该花 15 分钟。一次卡死的流式请求会白吃整个 timeout，
    # 所以超时随文本长度走，短句给 240s 就够。
    tmo = 240 if len(text) <= 400 else 900
    last = None
    for i in range(tries):
        try:
            reply = W.llm_chat(
                cfg,
                [{"role": "system", "content": system},
                 {"role": "user", "content": text_prompt(safe, L)}],
                temperature=0.2, timeout=tmo)
            out = restore(clean_reply(reply), urls)
            if out.count("\n") + 1 == n:                 # 行数必须对得上
                return out
            last = out
            if n <= 2 and i >= 1:                        # 短段落重试一次没用，直接逐行
                break
        except Exception as exc:                         # noqa: BLE001
            last = exc
    # 兜底：逐行翻译，宁可慢也要 1:1
    return "\n".join(translate_line(cfg, ln, terms, L) for ln in lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="英文维基 Markdown → 目标语言 Markdown")
    ap.add_argument("input", help="英文 .md 文件")
    ap.add_argument("-o", "--output", required=True, help="输出 .md 路径")
    ap.add_argument("--to", choices=sorted(LANGS), default="zh",
                    help="目标语言（默认 zh=简体中文；th=泰语）")
    ap.add_argument("--title", help="目标语言标题（不给就让模型译）")
    ap.add_argument("-p", "--provider", choices=["auto"] + sorted(W.PROVIDERS), default="auto")
    ap.add_argument("-m", "--model")
    ap.add_argument("--base-url")
    ap.add_argument("--api-key")
    ap.add_argument("--reasoning-effort", default="none",
                    choices=["none", "minimal", "low", "medium", "high"])
    ap.add_argument("--no-stream", action="store_true")
    ap.add_argument("--chunk", type=int, default=1400, help="单块字符上限，默认 1400")
    ap.add_argument("--state", help="断点续译的状态文件")
    ap.add_argument("--jobs", type=int, default=4, help="并发请求数，默认 4")
    ap.add_argument("--terms", default=None,
                    help="术语表 JSON（scripts/wikiterm.py 生成）。"
                         "不给就按 --to 选默认表；给空字符串或 --no-terms 可关掉")
    ap.add_argument("--no-terms", action="store_true", help="不使用术语表")
    ap.add_argument("--terms-people", action="store_true",
                    help="术语表保留人名译名（默认过滤掉，见 load_terms 注释）")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    L = LANGS[args.to]

    with open(args.input, encoding="utf-8") as fh:
        raw = fh.read()
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    state_path = args.state or (args.output + ".state.json")
    done = {}
    if os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as fh:
                done = json.load(fh).get("chunks", {})
        except Exception:                            # noqa: BLE001
            done = {}

    cfg = W.resolve_provider(argparse.Namespace(
        provider=args.provider, base_url=args.base_url, model=args.model,
        api_key=args.api_key, reasoning_effort=args.reasoning_effort,
        no_stream=args.no_stream))
    print("→ %s | model=%s | reasoning_effort=%s | 目标语言=%s"
          % (cfg["name"], cfg["model"], cfg["reasoning_effort"], L["label"]))

    terms_path = args.terms if args.terms is not None else L["terms_file"]
    terms = {} if args.no_terms else load_terms(
        terms_path, quiet=args.quiet, people=args.terms_people, L=L)

    blocks = split_blocks(lines)
    chunks = pack(blocks, args.chunk)
    print("→ %d 行 / %d 块，其中待译 %d 块（已缓存 %d）"
          % (len(lines), len(blocks), len(chunks), len(done)))

    result = [None] * len(blocks)
    for idx, (kind, ls) in enumerate(blocks):
        if kind != "text":
            result[idx] = ls

    todo = []
    for start, items in chunks:
        text = "\n".join(x[1][0] for x in items)
        cached = done.get(str(start))
        # 行数必须严格相等：多了是幻觉（标题被补全成整节），少了是漏译。
        out = cached if cached and cached.count("\n") == text.count("\n") else None
        todo.append((start, items, text, out))

    print("→ 待请求 %d 块，并发 %d" % (sum(1 for t in todo if t[3] is None), args.jobs))
    t0 = time.time()
    n_done = 0

    def work(item):
        start, items, text, cached = item
        if cached is not None:
            return start, cached, False
        return start, translate_chunk(cfg, text, terms=terms, L=L), True

    if args.jobs > 1:
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futs = [ex.submit(work, it) for it in todo]
            for fu in cf.as_completed(futs):
                start, out, fresh = fu.result()
                if fresh:
                    done[str(start)] = out
                n_done += 1
                if fresh and n_done % 10 == 0:
                    with open(state_path, "w", encoding="utf-8") as fh:
                        json.dump({"chunks": done}, fh, ensure_ascii=False)
                if not args.quiet:
                    print("  [%d/%d] %5.1fs" % (n_done, len(todo), time.time() - t0))
                    sys.stdout.flush()
    else:
        for it in todo:
            start, out, fresh = work(it)
            if fresh:
                done[str(start)] = out
                with open(state_path, "w", encoding="utf-8") as fh:
                    json.dump({"chunks": done}, fh, ensure_ascii=False)
            n_done += 1
            if not args.quiet:
                print("  [%d/%d] %5.1fs" % (n_done, len(todo), time.time() - t0))
                sys.stdout.flush()

    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump({"chunks": done}, fh, ensure_ascii=False)

    by_start = {t[0]: (done.get(str(t[0])) or "") for t in todo}
    t_index = term_index(terms)
    for start, items in chunks:
        parts = by_start[start].split("\n")
        for k, (idx, _) in enumerate(items):
            line = parts[k] if k < len(parts) else ""
            src = items[k][1][0]
            m = re.match(r"^(#{1,6})\s", src)        # 标题层级以原文为准
            if m:
                line = re.sub(r"^#{1,6}\s*", m.group(1) + " ", line.strip())
            if re.match(r"^\[\^[^\[\]]+\]:", line) and not re.match(r"^\[\^[^\[\]]+\]:", src):
                line = ""                            # 模型自己编的脚注定义，丢掉
            line = fix_footnotes(line, src)
            line = enforce_terms_in_links(line, t_index)
            result[idx] = [line]
        if len(parts) > len(items):                  # 模型把一段拆成了多段
            # 多出来的行里，脚注定义和标题一定是幻觉（原文根本没有），直接丢；
            # 纯散文才可能是它把长句拆开了，留着。
            keep = [l for l in parts[len(items):]
                    if not re.match(r"^\[\^[^\[\]]+\]:", l) and not re.match(r"^#{1,6}\s", l)]
            result[items[-1][0]] = ([parts[len(items) - 1], "", "\n".join(keep)]
                                    if keep else [parts[len(items) - 1]])

    # front matter 的标题
    out_lines = []
    for ls in result:
        out_lines.extend(ls if ls else [""])

    # 最后一道保险：脚注定义必须逐字来自原文。模型编的（"[^1]: 参见…"、
    # "此处为脚注占位符"）在这里全部清掉。
    src_defs = set(l.strip() for l in lines if re.match(r"^\[\^\d+\]:", l.strip()))
    dropped = 0
    kept = []
    for l in out_lines:
        if re.match(r"^\[\^\d+\]:", l.strip()) and l.strip() not in src_defs:
            dropped += 1
            continue
        kept.append(l)
    if dropped:
        print("→ 丢弃模型自造的脚注定义 %d 条" % dropped)
    out_lines = kept
    body = "\n".join(out_lines)

    if args.title:
        out_title = args.title
    else:
        m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n", raw, re.S)
        en_title = ""
        if m:
            mm = re.search(r"^\s*title\s*:\s*(.+?)\s*$", m.group(1), re.M)
            en_title = mm.group(1) if mm else ""
        out_title = ""
        if en_title:
            out_title = clean_reply(W.llm_chat(
                cfg, [{"role": "system",
                       "content": system_with(en_title, terms,
                                              L["title_system"], L)},
                      {"role": "user", "content": en_title}],
                temperature=0.2, timeout=300)).split("\n")[0].strip()
        print("→ 标题: %s → %s" % (en_title, out_title))

    body = re.sub(r"^\s*---\s*\n(.*?)\n---\s*\n", "", body, count=1, flags=re.S)
    final = "---\ntitle: %s\n---\n\n%s\n" % (out_title or L["default_title"],
                                             body.strip())

    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(final.replace("\n", "\r\n").encode("utf-8"))
    print("✓ 已写入 %s（%d 字符，%.0fs）" % (out_path, len(final), time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
