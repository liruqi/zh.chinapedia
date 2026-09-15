#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 wiki2md 生成的「注释」编号列表 + 全角 ［n］ 标记改成真正的 GFM 脚注。

背景
----
wiki2md.py 翻译维基条目时会把 ``<ref>…</ref>`` 整理成文末的「注释」编号列表，
正文里留下全角标记 ``［1］`` ``［2］``。这些标记在 Docusaurus / GitHub 上只是
普通文字，点不动。本脚本把它们接成 GFM 脚注：

    正文：…由波恩哈德·黎曼提出，［1］并以他的姓氏命名…
      →   …由波恩哈德·黎曼提出， [^1] 并以他的姓氏命名…

    ## 注释             ← 整节删除
    1. Bernhard Riemann（1859）
    2. Connes（2026）

    文末：[^1]: Bernhard Riemann（1859）
          [^2]: Connes（2026）

编号冲突
--------
若文末已经有别的脚注定义（比如 md2footnotes.py 生成的 OEIS 链接脚注），
本脚本会把它们整体顺延到「注释」编号之后，并同步改写正文里的引用，
避免 ``[^1]`` 出现两个定义。

用法::

    python scripts/notes2footnotes.py docs/math/黎曼猜想.md
    python scripts/notes2footnotes.py --dry-run docs/math/*.md

保持原文件 CRLF/LF 行尾；重复执行不会重复添加脚注块。
"""

from __future__ import annotations

import argparse
import re
import sys

# 「注释」「Notes」「脚注」这类章节
NOTES_HEADING_RE = re.compile(r'^#{1,6}\s*(注释|Notes|脚注|注解)\s*$')
ANY_HEADING_RE = re.compile(r'^#{1,6}\s')
# 编号列表项：1. xxx / 1、xxx
NOTE_ITEM_RE = re.compile(r'^(\d+)[.、]\s+(.*)$')
# 全角引用标记 ［1］（也兼容半角 [1] 的 [[1]] 形式）
MARK_RE = re.compile(r'［(\d+)］')
DEF_RE = re.compile(r'^\[\^([^\]]+)\]:\s?(.*)$')

# 与 md2footnotes.py 保持一致：后面接这些字符时不补空格
_NO_SPACE_AFTER = ' \t　，。、；：！？（）「」『』【】《》…—,.;:!?)]'


def _spacing(m):
    s = m.string
    pre = '' if (m.start() == 0 or s[m.start() - 1].isspace()) else ' '
    nxt = s[m.end():m.end() + 1]
    post = '' if (not nxt or nxt in _NO_SPACE_AFTER) else ' '
    return pre, post


def _insert_pos(lines):
    """脚注块插入位置：文末，或文末许可声明块（--- + 引用）之前。"""
    k = len(lines) - 1
    while k >= 0 and not lines[k].strip():
        k -= 1
    if k >= 0 and lines[k].lstrip().startswith('>'):
        i = k - 1
        while i >= 0 and not lines[i].strip():
            i -= 1
        if i >= 0 and lines[i].strip() == '---':
            return i
    return len(lines)


def convert(text: str):
    nl = '\r\n' if '\r\n' in text else '\n'
    lines = text.split(nl)

    # ---- 1. 抽出「注释」章节 -------------------------------------------------
    notes = {}          # 编号 -> 文本
    section = None      # (heading_idx, [line_idx…])
    for i, ln in enumerate(lines):
        if ANY_HEADING_RE.match(ln):
            if section and NOTES_HEADING_RE.match(lines[section[0]]):
                break
            section = (i, [])
            continue
        if section:
            section[1].append(i)

    if not section or not NOTES_HEADING_RE.match(lines[section[0]]):
        return text, 0, 'no-notes-section'

    del_lines = [section[0]]
    for i in section[1]:
        m = NOTE_ITEM_RE.match(lines[i])
        if m:
            notes[int(m.group(1))] = m.group(2).strip()
            del_lines.append(i)
        elif not lines[i].strip():
            # 空行：只有后面还有编号项才算注释节内部
            if any(NOTE_ITEM_RE.match(lines[j]) for j in section[1] if j > i):
                del_lines.append(i)
        else:
            break

    if not notes:
        return text, 0, 'no-notes-section'

    # ---- 2. 文末已有脚注定义：整体顺延 --------------------------------------
    existing = []       # [(old, body)]
    for i, ln in enumerate(lines):
        m = DEF_RE.match(ln)
        if m:
            existing.append((m.group(1), m.group(2)))
    base = max(notes) if notes else 0
    remap = {}
    for off, (old, _body) in enumerate(existing, 1):
        remap[old] = str(base + off)

    # 先改正文引用，再删定义行（删完再改会误伤不到，但顺序反过来更稳）
    for i, ln in enumerate(lines):
        if DEF_RE.match(ln):
            continue
        lines[i] = re.sub(r'\[\^([^\]]+)\](?!:)',
                          lambda m: '[^%s]' % remap.get(m.group(1), m.group(1)), ln)

    for i in sorted(set(del_lines) | {j for j, ln in enumerate(lines) if DEF_RE.match(ln)},
                    reverse=True):
        del lines[i]

    # ---- 3. 全角 ［n］ → [^n] ------------------------------------------------
    body = nl.join(lines)
    hits = 0
    missing = set()

    def repl(m):
        nonlocal hits
        n = int(m.group(1))
        if n not in notes:
            missing.add(n)
            return m.group(0)
        hits += 1
        pre, post = _spacing(m)
        return '%s[^%d]%s' % (pre, n, post)

    body = MARK_RE.sub(repl, body)

    # ---- 4. 文末拼脚注块 ------------------------------------------------------
    lines = body.split(nl)
    lines = [re.sub(r'[ \t]+$', '', ln) for ln in lines]
    pos = _insert_pos(lines)
    while pos > 0 and not lines[pos - 1].strip():
        pos -= 1

    block = ['']
    for n in sorted(notes):
        block.append('[^%d]: %s' % (n, notes[n]))
    for old, _ in existing:
        block.append('[^%s]: %s' % (remap[old],
                                    next(b for o, b in existing if o == old)))
    lines[pos:pos] = block

    out = []
    for ln in lines:
        if not ln.strip() and out and not out[-1].strip():
            continue
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return nl.join(out) + nl, hits, missing


def main(argv=None):
    ap = argparse.ArgumentParser(description='把「注释」编号列表 + ［n］ 标记改成 GFM 脚注')
    ap.add_argument('files', nargs='+')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args(argv)

    for p in args.files:
        raw = open(p, 'rb').read().decode('utf-8')
        new, hits, info = convert(raw)
        name = p.replace('\\', '/').split('/')[-1]
        if info == 'no-notes-section':
            print('%-32s 跳过：没有「注释」编号列表' % name)
            continue
        miss = ('  ! 无对应注释: %s' % sorted(info)) if info else ''
        if args.dry_run:
            print('%-32s 将改 %d 个 ［n］ 为脚注%s' % (name, hits, miss))
            continue
        if new != raw:
            open(p, 'wb').write(new.encode('utf-8'))
        print('%-32s 改 %d 个 ［n］ 为脚注%s' % (name, hits, miss))
    return 0


if __name__ == '__main__':
    sys.exit(main())
