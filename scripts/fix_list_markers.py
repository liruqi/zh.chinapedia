#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_list_markers.py —— 给「列表标记后没空格」的行补一个空格

背景
----
CommonMark 要求列表标记后面跟**空白**：`*X` 不是列表项，而是一个普通段落，
行首那个 `*` 会当字面量渲染出来。更糟的是连续多行会被并成**一个**段落——
实测 Navier–Stokes 的 `## See also` 里 7 行 `*[X](url)` 会渲染成 1 个列表项、
正文里挂着 7 个裸 `*`。

`scripts/wikitext2md.py` 已在 2026-10-06 修好（在展开模板前统一补空格），
这个脚本用来修**历史产物**：用旧版转换器生成、还留着 `*X` 的 .md。

怎么判断 `*X` 是「漏了空格的列表项」还是「行首的斜体」？
-------------------------------------------------------
两者在转换后的文本里长得一模一样（`*Mazur, Barry…` vs `*Goldbach's Conjecture* …`），
所以看**上下文**：列表项一定和前后某个 `*` 行相邻（同一次转换里同一段列表一起产出），
而行首斜体是独立段落，前后是空行/标题/正文。

实测 12 个候选（en 仓 7 + zh 仓 5）全部符合这个判据：
  * 真列表项 7 个：prev 或 next 非空行以 `*` 开头（文献表 / 参见 / 外部链接）
  * 行首斜体 5 个：前后都不是 `*` 行，如 `siegel_zero.md` 的
    `*with the possible exception of at most one fundamental discriminant.*`、
    `哥德巴赫猜想.md` 的 `*哥德巴赫猜想* () 是徐迟…的书名。`

用法
----
    python3 scripts/fix_list_markers.py docs/math            # 就地修
    python3 scripts/fix_list_markers.py docs/math --check     # 只报不改（有改动则退出码 1）
    python3 scripts/fix_list_markers.py docs/math --dry-run   # 打印将要改的行

保持 CRLF 与幂等：已经修过的文件再跑不会产生改动。
"""

import argparse
import io
import os
import re
import sys

CAND_RE = re.compile(r"^\*([^ *].*)$")
MARKER_RE = re.compile(r"^\*")


def _neighbour_is_bullet(lines, i):
    """上下最近的非空行里，有以 `*` 开头的就算处于列表上下文。"""
    for j in range(i - 1, -1, -1):
        if lines[j].strip():
            if MARKER_RE.match(lines[j]):
                return True
            break
    for j in range(i + 1, len(lines)):
        if lines[j].strip():
            if MARKER_RE.match(lines[j]):
                return True
            break
    return False


def fix_text(text):
    """返回 (新文本, [(行号, 改前, 改后)])。保留原有换行风格。"""
    crlf = "\r\n" in text
    lines = text.replace("\r\n", "\n").split("\n")
    changes = []
    for i, line in enumerate(lines):
        m = CAND_RE.match(line)
        if not m:
            continue
        if not _neighbour_is_bullet(lines, i):
            continue
        lines[i] = "* " + m.group(1)
        changes.append((i + 1, line, lines[i]))
    new = "\n".join(lines)
    if crlf:
        new = new.replace("\n", "\r\n")
    return new, changes


def iter_md(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in sorted(files):
                    if f.endswith(".md"):
                        yield os.path.join(root, f)
        elif p.endswith(".md"):
            yield p


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="fix_list_markers.py",
        description="给「列表标记后没空格」的 `*X` 行补空格（判断见文件头注释）",
    )
    ap.add_argument("paths", nargs="+", help="要处理的 .md 文件或目录")
    ap.add_argument("--check", action="store_true", help="只检查，有需要改的就退出码 1")
    ap.add_argument("--dry-run", action="store_true", help="打印将要改的行，不落盘")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    total = 0
    touched = 0
    for path in iter_md(args.paths):
        raw = io.open(path, encoding="utf-8", newline="").read()
        new, changes = fix_text(raw)
        if not changes:
            continue
        touched += 1
        total += len(changes)
        rel = os.path.relpath(path).replace("\\", "/")
        print("%s: %d 处" % (rel, len(changes)))
        if not args.quiet:
            for ln, before, after in changes:
                print("    L%-5d %s" % (ln, before[:110]))
        if not args.check and not args.dry_run:
            with io.open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)

    if args.check:
        print("需要修：%d 个文件 / %d 处" % (touched, total))
        return 1 if total else 0
    if args.dry_run:
        print("（dry-run）%d 个文件 / %d 处" % (touched, total))
        return 0
    print("已修：%d 个文件 / %d 处" % (touched, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
