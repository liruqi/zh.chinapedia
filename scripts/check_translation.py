#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对译稿：结构必须与原文稿一一对应，正文必须真的译成了目标语言。

md2zh.py 的行数守卫是按 chunk 比的，这里做**整篇**独立核对（不复用它的翻译逻辑，
只复用 split_blocks 来界定"哪些行本该被翻译"）：

  1. 行数 / `$$` 数 / 脚注标记数 / 脚注定义数 / figure 标签数 / 表格行数 —— 必须相等；
  2. 应译行里没出现目标语言文字的 —— 列出来（漏译或模型偷懒）；
  3. 译文行里夹着成串拉丁字母的 —— 列出来（专有名词留英文是允许的，但要人工过一眼）；
  4. 相邻脚注标记间距不是恰好一个空格的 —— 报错（跟 prebuild_check 同一判据）；
  5. 残留 `<references` / 裸 `[[` / `{{` / `<ref` —— 报错。

用法：
    python scripts/check_translation.py <原文目录> <译文目录>
    python scripts/check_translation.py <原文.md> <译文.md>
    python scripts/check_translation.py --lang th <原文.md> <译文.md>
"""

import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import md2zh                                                    # noqa: E402
from fix_footnote_spacing import NEED_FIX_RE                    # noqa: E402

# 目标语言的「文字」正则：命中即认为该行译过了
SCRIPTS = {
    "th": re.compile(r"[\u0e00-\u0e7f]"),
    "zh": re.compile(r"[\u4e00-\u9fff]"),
}
LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z'’\-]{2,}(?:\s+[A-Za-z][A-Za-z'’\-]{2,})*")
FOOT_REF = re.compile(r"\[\^[^\[\]]+\]")
FOOT_DEF = re.compile(r"^\[\^\d+\]:")
BAD_RESIDUE = [
    ("MediaWiki <references", re.compile(r"<references")),
    ("<ref> 残留", re.compile(r"<ref\b")),
]
# 这些在原稿里本来就合法（`<figure style={{"maxWidth": …}}>` 的双花括号、
# 公式里的 `\frac{}{}`），所以只比「有没有变多」，不比绝对值。
COUNT_RESIDUE = [
    ("维基链接 [[", re.compile(r"\[\[")),
    ("双花括号 {{", re.compile(r"\{\{")),
]
# 这些行就算没有目标语言文字也算正常（纯符号 / 数字 / 单位 / 缩写）
IGNORE_LINE = re.compile(r"^[\s\W\d]*$")


def count(pat, lines):
    return sum(1 for ln in lines if pat.search(ln))


def compare(src_path, out_path, lang="th"):
    target = SCRIPTS[lang]
    en = io.open(src_path, encoding="utf-8").read().splitlines()
    th = io.open(out_path, encoding="utf-8").read().splitlines()
    name = os.path.basename(src_path)
    problems, notes = [], []

    def eq(label, a, b):
        if a != b:
            problems.append("%s 不一致：原稿 %d / 译稿 %d" % (label, a, b))

    eq("总行数", len(en), len(th))
    eq("$$ 数", count(re.compile(r"\$\$"), en), count(re.compile(r"\$\$"), th))
    eq("脚注标记数", len(FOOT_REF.findall("\n".join(en))),
       len(FOOT_REF.findall("\n".join(th))))
    eq("脚注定义数", count(FOOT_DEF, en), count(FOOT_DEF, th))
    eq("figure 标签数", count(re.compile(r"^</?figure"), en),
       count(re.compile(r"^</?figure"), th))
    eq("figcaption 标签数", count(re.compile(r"^</?figcaption"), en),
       count(re.compile(r"^</?figcaption"), th))
    eq("表格行数", count(re.compile(r"^\|"), en), count(re.compile(r"^\|"), th))

    # 行内公式的 $ 必须成对。**逐行比奇偶**：奇数个 $ = 没闭合，会把后面一大段吃进
    # 公式里（这是真问题）；只是总数少了几个通常是把 `[ $Z$-function]` 写成
    # `[ฟังก์ชัน Z]` 这种，记一笔即可，不算错。
    odd = []
    for i, (a, b) in enumerate(zip(en, th), 1):
        if a.count("$") % 2 != b.count("$") % 2:
            odd.append("第 %d 行 $ 不配对：原稿 %d 个 / 译稿 %d 个 → %s"
                       % (i, a.count("$"), b.count("$"), b.strip()[:60]))
    problems.extend(odd)
    n_en, n_th = "\n".join(en).count("$"), "\n".join(th).count("$")
    if n_en != n_th and not odd:
        notes.append("$ 总数 %d → %d（逐行奇偶都正常，多半是链接文字里的公式被简化）"
                     % (n_en, n_th))

    # 相邻脚注标记间距
    for i, ln in enumerate(th, 1):
        for m in NEED_FIX_RE.finditer(ln):
            if m.group(2) != " ":
                problems.append("第 %d 行脚注标记间距不规范: %s"
                                % (i, ln.strip()[:60]))

    # 残留
    for label, pat in BAD_RESIDUE:
        for i, ln in enumerate(th, 1):
            if pat.search(ln):
                problems.append("第 %d 行残留 %s: %s" % (i, label, ln.strip()[:60]))
    for label, pat in COUNT_RESIDUE:
        a = len(pat.findall("\n".join(en)))
        b = len(pat.findall("\n".join(th)))
        if b > a:
            first = next((i for i, ln in enumerate(th, 1) if pat.search(ln)), 0)
            problems.append("%s 变多：原稿 %d → 译稿 %d（首次出现在第 %d 行）"
                            % (label, a, b, first))

    # 应译行是否真译了
    blocks = md2zh.split_blocks(en)
    text_lines = set()
    for kind, ls in blocks:
        if kind == "text":
            for ln in ls:
                text_lines.add(ln)
    missing = []
    for ln in th:
        if ln not in text_lines:
            continue
        s = ln.strip()
        if not s or IGNORE_LINE.match(s):
            continue
        if not target.search(s):
            missing.append(s[:70])
    if missing:
        notes.append("应译但无目标语言文字的行 %d 行（原样留下）：" % len(missing))
        for m in missing[:12]:
            notes.append("    " + m)

    # 译文里成串拉丁字母（允许：人名 / 期刊 / 缩写 / 术语留英文）
    latin = []
    for ln in th:
        if not target.search(ln):
            continue
        for m in LATIN_RUN.finditer(ln):
            t = m.group(0)
            if len(t) >= 4:
                latin.append(t)
    if latin:
        from collections import Counter
        top = Counter(latin).most_common(15)
        notes.append("译文行里的拉丁串（前 15）："
                     + ", ".join("%s×%d" % (w, c) for w, c in top))

    print("=== %s ===" % name)
    print("  行数 %d → %d | $$ %d | 脚注标记 %d | 定义 %d | figure %d"
          % (len(en), len(th), count(re.compile(r"\$\$"), th),
             len(FOOT_REF.findall("\n".join(th))), count(FOOT_DEF, th),
             count(re.compile(r"^</?figure"), th)))
    for n in notes:
        print("  · " + n)
    if problems:
        print("  ✗ %d 个问题：" % len(problems))
        for p in problems[:20]:
            print("      " + p)
    else:
        print("  ✓ 结构一致，无残留")
    return len(problems)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", help="原稿 .md 或目录")
    ap.add_argument("out", help="译稿 .md 或目录")
    ap.add_argument("--lang", choices=sorted(SCRIPTS), default="th",
                    help="目标语言（默认 th）")
    args = ap.parse_args(argv)

    a, b = args.src, args.out
    if os.path.isdir(a):
        pairs = [(os.path.join(a, f), os.path.join(b, f))
                 for f in sorted(os.listdir(a)) if f.endswith(".md")]
    else:
        pairs = [(a, b)]
    bad = 0
    for src, out in pairs:
        if not os.path.exists(out):
            print("缺少译稿: %s" % out)
            bad += 1
            continue
        bad += compare(src, out, args.lang)
    print("\n合计问题数: %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
