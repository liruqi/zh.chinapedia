#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Markdown 里的外部链接改成 GFM 脚注（*.wikipedia.org 的链接保持行内）。

用法::

    python scripts/md2footnotes.py docs/math/*.md            # 只改正文
    python scripts/md2footnotes.py --all docs/math/*.md      # 连参考文献也改
    python scripts/md2footnotes.py --dry-run docs/math/黎曼猜想.md

规则
----
* ``[文字](url)``  → ``文字 [^n]``，文末追加 ``[^n]: [https://host](url)``
* ``[[7]](url)``   → `` [^n] ``（维基 <ref> 形式的引用标记）
* 域名以 ``wikipedia.org`` 结尾的链接原样保留行内。
* 同一 URL 复用同一个脚注编号（与 docs/ai/product/openclaw.md 一致）。
* 默认跳过「注释 / 参考文献 / 外部链接 / 科普读物 / 延伸阅读」这类本身就是
  链接清单的章节，只对正文生效；加 ``--all`` 可关闭该行为。
* 文末若有 ``---`` + 许可声明引用块，脚注插在它前面。
* 保持原文件的 CRLF/LF 行尾；重复执行不会产生第二个脚注块。
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_footnote_spacing import fix_spacing  # noqa: E402

# [文字](url) 或 [文字](url "title")
LINK_RE = re.compile(r'\[([^\]\n]*)\]\((https?://[^)\s]+)(?:\s+"[^"]*")?\)')
# [[7]](url) —— wikitext <ref> 留下的引用标记
REF_LINK_RE = re.compile(r'\[\[([^\]\n]+)\]\]\((https?://[^)\s]+)\)')
# 已有脚注定义
FOOTNOTE_DEF_RE = re.compile(r'^\[\^([^\]]+)\]:', re.M)
# 本身就是链接清单的章节 —— 默认跳过
LIST_SECTION_RE = re.compile(
    r'^(注释|参考文献|参考资料|外部链接|延伸阅读|科普读物|脚注|'
    r'Notes|References|External links|Further reading|Sources)')
CJK = r'\u4e00-\u9fff'


def is_wikipedia(url: str) -> bool:
    m = re.match(r'https?://([^/]+)', url)
    if not m:
        return False
    host = m.group(1).lower().split(':')[0]
    return host == 'wikipedia.org' or host.endswith('.wikipedia.org')


def display_of(url: str) -> str:
    m = re.match(r'(https?://[^/]+)', url)
    return m.group(1) if m else url


def split_sections(lines):
    out, cur, cur_lines = [], None, []
    for i, ln in enumerate(lines):
        if ln.startswith('#'):
            out.append((cur, cur_lines))
            cur, cur_lines = ln, []
        else:
            cur_lines.append(i)
    out.append((cur, cur_lines))
    return out


# 后面接这些字符时不补空格（中文标点 / 英文标点 / 空白 / 右括号）
_NO_SPACE_AFTER = ' \t\u3000，。、；：！？（）「」『』【】《》…—,.;:!?)]'


def _spacing(m):
    """脚注标记前后补空格。

    标记前若不是空白就补一个（中文正文里标记总是紧跟在前一个字符后面）；
    标记后若紧跟 ``[`` 或 ``$`` 也必须补空格——否则 ``[^1]$x$`` 会让 GitHub
    认定行内公式的起始 ``$`` 前面不是空白而不渲染。
    """
    s = m.string
    pre = '' if (m.start() == 0 or s[m.start() - 1].isspace()) else ' '
    nxt = s[m.end():m.end() + 1]
    post = '' if (not nxt or nxt in _NO_SPACE_AFTER) else ' '
    return pre, post


def _insert_pos(lines):
    """脚注块插入位置：文末，或文末许可声明块之前。"""
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


def convert(text: str, all_sections: bool = False):
    nl = '\r\n' if '\r\n' in text else '\n'
    lines = text.split(nl)

    used = set(FOOTNOTE_DEF_RE.findall(text))
    next_n = 1
    while str(next_n) in used:
        next_n += 1

    url_to_ref, defs = {}, []
    changed = skipped = 0

    def ref_for(url):
        nonlocal next_n
        if url in url_to_ref:
            return url_to_ref[url], False
        ref = str(next_n)
        next_n += 1
        used.add(ref)
        url_to_ref[url] = ref
        defs.append((ref, url))
        return ref, True

    for heading, idxs in split_sections(lines):
        skip = False
        if heading is not None and not all_sections:
            if LIST_SECTION_RE.match(heading.lstrip('#').strip()):
                skip = True

        for i in idxs:
            ln = lines[i]
            if ln.startswith('[^'):          # 脚注定义行不动
                continue
            if skip:
                skipped += len(LINK_RE.findall(ln)) + len(REF_LINK_RE.findall(ln))
                continue

            def repl_link(m):
                nonlocal changed, skipped
                label, url = m.group(1).strip(), m.group(2)
                if is_wikipedia(url):
                    skipped += 1
                    return m.group(0)
                ref, new = ref_for(url)
                changed += 1
                return ('%s [^%s]' % (label, ref)) if label else ' [^%s] ' % ref

            def repl_ref(m):
                nonlocal changed, skipped
                url = m.group(2)
                if is_wikipedia(url):
                    skipped += 1
                    return m.group(0)
                ref, new = ref_for(url)
                changed += 1
                pre, post = _spacing(m)
                return '%s[^%s]%s' % (pre, ref, post)

            ln = REF_LINK_RE.sub(repl_ref, ln)
            ln = LINK_RE.sub(repl_link, ln)
            # 连续脚注之间恰好一个空格。
            # 别用 `\s*\[\^([^\]]+)\]\s*\[\^` 这种成对正则——链式标记
            # `[^55][^56][^57]` 只会被拆开前两个，留下 `[^56][^57]` 不修。
            ln = fix_spacing(ln)
            lines[i] = ln

    if not defs:
        return text, 0, skipped

    lines = [re.sub(r'[ \t]+$', '', ln) for ln in lines]
    pos = _insert_pos(lines)
    while pos > 0 and not lines[pos - 1].strip():
        pos -= 1
    block = [''] + ['[^%s]: [%s](%s)' % (r, display_of(u), u) for r, u in defs]
    lines[pos:pos] = block
    # 去掉被挤到中间的连续空行
    out = []
    for ln in lines:
        if not ln.strip() and out and not out[-1].strip():
            continue
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return nl.join(out) + nl, changed, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description='把外部链接改成 GFM 脚注')
    ap.add_argument('files', nargs='+')
    ap.add_argument('--all', action='store_true',
                    help='连参考文献/注释/外部链接等章节也一起改')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args(argv)

    for p in args.files:
        raw = open(p, 'rb').read().decode('utf-8')
        new, changed, skipped = convert(raw, args.all)
        name = os.path.basename(p)
        if changed == 0:
            print('%-40s 无改动（保留 %d 个行内链接）' % (name, skipped))
            continue
        if args.dry_run:
            print('%-40s 将改 %d 个链接为脚注，保留行内 %d 个' % (name, changed, skipped))
            continue
        open(p, 'wb').write(new.encode('utf-8'))
        print('%-40s 改 %d 个链接为脚注，保留行内 %d 个' % (name, changed, skipped))
    return 0


if __name__ == '__main__':
    sys.exit(main())
