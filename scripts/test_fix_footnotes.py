#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2zh 收尾步骤的回归用例：脚注标记对账 + 术语表在链接文字上强制生效。

    python scripts/test_fix_footnotes.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md2zh                                                    # noqa: E402

CASES = [
    # (译文行, 原文行, 期望输出, 说明)
    ("ก $x$" + "[^n]", "It is $x$.", "ก $x$", "幻觉标记 → 删"),
    ("ก " + "[^1]" + " ข", "A" + "[^1]" + " B", "ก " + "[^1]" + " ข", "正常 → 留"),
    ("ก " + "[^1]" + "[^2]" + " ข", "A" + "[^1]" + " B", "ก " + "[^1]" + " ข", "多出来 → 删"),
    ("ก " + "[^1] [^2]" + " ข", "A" + "[^1]" + " B" + "[^2]",
     "ก " + "[^1] [^2]" + " ข", "正常两个 → 留"),
    ("ก " + "[^12]" + " ข " + "[^3]", "A" + "[^12]" + " B" + "[^3]",
     "ก " + "[^12]" + " ข " + "[^3]", "两位数 → 留"),
    ("ก " + "[^note]" + " ข", "A B", "ก  ข", "非数字标签 → 删"),
    ("ก ข", "A" + "[^6]" + " B", "ก ข " + "[^6]", "整行漏掉标记 → 补到行尾"),
    ("ก " + "[^1]", "A" + "[^1]" + " B" + "[^2]", "ก " + "[^1] [^2]", "补的时候留一个空格"),
]

fail = 0
for line, src, want, desc in CASES:
    got = md2zh.fix_footnotes(line, src)
    ok = got == want
    fail += 0 if ok else 1
    print("%s %-16s %r -> %r" % ("✓" if ok else "✗", desc, line, got))
    if not ok:
        print("      期望 %r" % want)

print()

IDX = md2zh.term_index({"complex conjugate": "สังยุค", "roots of unity": "รากของหนึ่ง",
                        "Prime number": "จำนวนเฉพาะ"})
LINK_CASES = [
    ("its [complex conjugate](https://en.wikipedia.org/wiki/complex_conjugate) $x$",
     "its [สังยุค](https://en.wikipedia.org/wiki/complex_conjugate) $x$",
     "完全相等 → 换成译名"),
    ("[Complex Conjugate](https://x/y) 后面", "[สังยุค](https://x/y) 后面",
     "大小写不同也算相等"),
    ("[complex conjugates](https://x/y)", "[complex conjugates](https://x/y)",
     "只多一个字母 → 不动（不做子串替换）"),
    ("[root of unity](https://x/y)", "[root of unity](https://x/y)", "近义但不同 → 不动"),
    ("[จำนวนเฉพาะ](https://x/y)", "[จำนวนเฉพาะ](https://x/y)", "已是译名 → 不动"),
    ("![图](https://x/y.png)", "![图](https://x/y.png)", "图片链接 → 不动"),
    ("[a](https://en.wikipedia.org/wiki/Foo_(bar))", "[a](https://en.wikipedia.org/wiki/Foo_(bar))",
     "URL 带括号 → 跳过不改"),
]
for line, want, desc in LINK_CASES:
    got = md2zh.enforce_terms_in_links(line, IDX)
    ok = got == want
    fail += 0 if ok else 1
    print("%s %-22s %r" % ("✓" if ok else "✗", desc, got))
    if not ok:
        print("      期望 %r" % want)

print()

HEAD_CASES = [
    ('## "ไม่มีจุดซีเกล" สำหรับ *D* < 0', '## "No Siegel zeros" for *D* \\< 0',
     '## "ไม่มีจุดซีเกล" สำหรับ *D* \\< 0', "标题丢转义 → 补回"),
    ("## $D < 0$ 的情况", "## $D < 0$ 的情况", "## $D < 0$ 的情况", "公式里的关系符 → 不动"),
    ("## 正文 a > b 比较", "## Text a \\> b", "## 正文 a \\> b 比较", "裸 > → 转义"),
    ("## 已经是 \\< 的", "## already \\< ok", "## 已经是 \\< 的", "已转义 → 不动"),
    ("正文不是标题 < 0", "body < 0", "正文不是标题 < 0", "非标题行 → 不动"),
    ("## 原文自己就有裸 <", "## bad < src", "## 原文自己就有裸 <", "原文不干净 → 不猜"),
]
for line, src, want, desc in HEAD_CASES:
    got = md2zh.escape_heading_angles(line, src)
    ok = got == want
    fail += 0 if ok else 1
    print("%s %-22s %r" % ("✓" if ok else "✗", desc, got))
    if not ok:
        print("      期望 %r" % want)

print()

SRC425 = ("implies that the zeros of the Riemann zeta function are symmetric about "
          "the real axis. Combining this symmetry with the functional equation")
ECHO_CASES = [
    ("implies that the zeros of the Riemann zeta function are symmetric about the "
     "real axis. → ส่งผลให้ศูนย์ของฟังก์ชันซีตาของรีมันมีความสมมาตรเกี่ยวกับแกนจริง",
     SRC425,
     "ส่งผลให้ศูนย์ของฟังก์ชันซีตาของรีมันมีความสมมาตรเกี่ยวกับแกนจริง",
     "回显原文 + 箭头 → 只留译文"),
    ("ส่งผลให้ศูนย์ของฟังก์ชันซีตาของรีมันสมมาตร", SRC425,
     "ส่งผลให้ศูนย์ของฟังก์ชันซีตาของรีมันสมมาตร", "正常译文 → 不动"),
    ("Edmund Landau", "Edmund Landau", "Edmund Landau", "短专名 → 不动"),
    ("implies that the zeros", SRC425, "implies that the zeros", "回显后没剩东西 → 不动"),
]
for line, src, want, desc in ECHO_CASES:
    got = md2zh.strip_source_echo(line, src)
    ok = got == want
    fail += 0 if ok else 1
    print("%s %-24s %r" % ("✓" if ok else "✗", desc, got[:60]))
    if not ok:
        print("      期望 %r" % want[:60])

print()

TH_SCRIPT = md2zh.LANGS["th"]["script"]
URL_CASES = [
    ("การใช้ **การหาปริพันธ์โดยการแยกส่วน**[https://en.wikipedia.org/wiki/integration_by_parts]",
     "การใช้ [**การหาปริพันธ์โดยการแยกส่วน**](https://en.wikipedia.org/wiki/integration_by_parts)",
     "文字[URL] → [文字](URL)"),
    ("[https://x.com](https://x.com)", "[https://x.com](https://x.com)", "本来就成链接 → 不动"),
    ("Thai text [https://x.com]", "Thai text [https://x.com]", "前面不是泰文 → 不动"),
]
for line, want, desc in URL_CASES:
    got = md2zh.repair_bracket_urls(line, TH_SCRIPT)
    ok = got == want
    fail += 0 if ok else 1
    print("%s %-28s %s" % ("✓" if ok else "✗", desc, got[:70]))
    if not ok:
        print("      期望 %s" % want[:70])

print("\n失败 %d / %d" % (fail, len(CASES) + len(LINK_CASES) + len(HEAD_CASES)
                          + len(ECHO_CASES) + len(URL_CASES)))
sys.exit(1 if fail else 0)
