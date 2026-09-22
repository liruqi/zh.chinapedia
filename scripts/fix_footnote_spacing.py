#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""相邻脚注标记之间补一个空格：``[^16][^17]`` → ``[^16] [^17]``。

为什么需要
----------
``[^16][^17]`` 渲染出来是 ``[16][17]``，两个上标挤在一起看不清；而且同一类问题
还有 ``[^1]$x$``（GitHub 认为行内公式的起始 ``$`` 前不是空白，直接不渲染）。

只处理「标记 + 标记」，且**不跨行**：用 ``[ \\t]*`` 而不是 ``\\s*``，
否则会把相邻两行（很可能是脚注定义）粘到一起。
脚注定义行形如 ``[^n]: https://…``，``]`` 后面跟的是 ``:``，天然不会命中。

链式标记（``[^1][^2][^3]``）用**前瞻**处理，一次扫描全部拆开——
``md2footnotes.py`` 里原来的 ``\\s*\\[\\^([^\\]]+)\\]\\s*\\[\\^`` 只能拆开成对的前两个，
三连会留下 ``[^2][^3]`` 不修（实测 黎曼ζ函数.md 的 ``[^55][^56][^57]``）。

用法::

    python scripts/fix_footnote_spacing.py docs              # 就地修
    python scripts/fix_footnote_spacing.py docs --dry-run    # 只列出将要改的位置
    python scripts/fix_footnote_spacing.py docs --check      # 有需要修的返回 1（给 CI 用）

幂等：跑第二遍不会有任何改动。
保持原文件的 CRLF / LF 行尾（按字节读、按字节写，正则不碰换行符）。
"""

from __future__ import annotations

import argparse
import os
import re
import sys

# 脚注标记：[^16]、[^note]、[^a-b]
MARK = r'\[\^[^\[\]]+\]'
# 标记 + 若干水平空白 + 前瞻到下一个标记（前瞻保证链式标记能逐个命中）
PAIR_RE = re.compile(r'(' + MARK + r')[ \t]*(?=' + MARK + r')')
# 同上，但把「空白」也捕获下来，用来判断间距是否已经规范
NEED_FIX_RE = re.compile(r'(' + MARK + r')([ \t]*)(?=' + MARK + r')')


def fix_spacing(text: str) -> str:
    """把相邻脚注标记之间的空白规范成一个空格。幂等。"""
    return PAIR_RE.sub(lambda m: m.group(1) + ' ', text)


def count_offenders(text: str) -> int:
    """需要修的处数（间距不等于一个空格的相邻标记）。"""
    return sum(1 for m in NEED_FIX_RE.finditer(text) if m.group(2) != ' ')


def find_offenders(text: str):
    """返回 [(行号, 原片段, 修正后片段)]，行号从 1 开始。每行只报第一处。"""
    out = []
    for i, line in enumerate(text.split('\n'), 1):
        fixed = fix_spacing(line)
        if fixed == line:
            continue
        j = 0
        while j < min(len(line), len(fixed)) and line[j] == fixed[j]:
            j += 1
        start = max(0, j - 14)
        out.append((i, line[start:j + 16], fixed[start:j + 16]))
    return out


def iter_md(paths):
    for p in paths:
        if os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                for fn in sorted(filenames):
                    if fn.endswith('.md'):
                        yield os.path.join(dirpath, fn)
        else:
            yield p


def main(argv=None):
    ap = argparse.ArgumentParser(description='相邻脚注标记之间补空格')
    ap.add_argument('paths', nargs='+', help='文件或目录')
    ap.add_argument('--dry-run', action='store_true', help='只列出，不写盘')
    ap.add_argument('--check', action='store_true',
                    help='有需要修的就返回 1（不写盘），给 CI / 预检用')
    args = ap.parse_args(argv)

    total_files = total_hits = 0
    for p in iter_md(args.paths):
        raw = open(p, 'rb').read()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            print('跳过（非 UTF-8）:', p)
            continue
        hits = count_offenders(text)
        if not hits:
            continue
        total_files += 1
        total_hits += hits
        rel = p.replace('\\', '/')
        if args.check or args.dry_run:
            offenders = find_offenders(text)
            print('%s  (%d 处，分布在 %d 行)' % (rel, hits, len(offenders)))
            for ln, before, after in offenders[:5]:
                print('    L%-5d %s   →   %s' % (ln, before, after))
            if len(offenders) > 5:
                print('    … 另有 %d 行' % (len(offenders) - 5))
            continue
        open(p, 'wb').write(fix_spacing(text).encode('utf-8'))
        print('%-58s 修 %d 处' % (rel, hits))

    if args.check:
        if total_files:
            print('\n× %d 个文件、%d 处相邻脚注标记缺空格' % (total_files, total_hits))
            print('  修：python scripts/fix_footnote_spacing.py docs')
            return 1
        print('√ 脚注标记间距全部规范')
        return 0

    verb = '将修' if args.dry_run else '已修'
    print('\n%s %d 个文件、%d 处' % (verb, total_files, total_hits))
    return 0


if __name__ == '__main__':
    sys.exit(main())
