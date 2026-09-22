#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整理泰语术语表（一次性 / 可重跑）。

背景：泰语维基数学条目极少，`wikiterm.py --lang th` 的 Wikidata 兜底会把宽泛条目
当成对应译名，直接注进翻译提示词会误导模型。典型坏例（实测）：

    critical line theorem  → สมมติฐานของรีมัน      （那是"黎曼猜想"，不是临界线定理）
    imaginary part         → จำนวนเชิงซ้อน          （那是"复数"）
    real part              → จำนวนเชิงซ้อน
    partial sum            → อนุกรม                 （那是"级数"）
    divergent integral     → อนุกรมลู่ออก            （那是"发散级数"）
    even integer           → ภาวะคู่หรือคี่          （那是"奇偶性"）
    eigenvalue             → ค่าลักษณะเฉพาะและเวกเตอร์ลักษณะเฉพาะ  （把特征向量也塞进来了）

本脚本做三件事，raw 另存备查：
  1. 丢掉 identity 映射（值 == 键）和无意义的非术语项；
  2. 丢掉上面那类"宽泛/错误"映射（DROP 清单）；
  3. 值里带消歧括号的（如 `สังยุค (จำนวนเชิงซ้อน)`）把括号去掉；
  4. 键按小写去重，保留"句子式大小写"那个变体。

用法：
    python scripts/curate_th_terms.py            # 写 scripts/wiki-th-terms.json
    python scripts/curate_th_terms.py --check    # 只报告差异，不写
"""

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TERMS = os.path.join(ROOT, "scripts", "wiki-th-terms.json")
RAW = os.path.join(ROOT, "scripts", "wiki-th-terms.raw.json")

# 宽泛 / 错误映射：泰语维基那个条目比英文词条宽或根本不是一回事
DROP = {
    "critical line theorem",
    "imaginary part",
    "real part",
    "complex infinity",
    "complex variable",
    "divergent integral",
    "partial sum",
    "even integer",
    "fundamental discriminant",
    "twin prime conjecture",
    "gaussian random variable",
    "eigenvalue",
    "us$",
    "1 + 2 + 3 + 4 + ···",
}

DISAMBIG_RE = re.compile(r"\s*[（(][^（()）]*[)）]\s*$")


def curate(d):
    """返回 (新表, 被剔除的原键列表, [(原键, 原值, 新值)])。"""
    out = {}
    removed, changed = [], []
    for k, v in sorted(d.items()):
        kl = k.lower().strip()
        if kl in DROP:
            removed.append(k)
            continue
        val = v.strip()
        if not val or val == k.strip():
            removed.append(k)
            continue
        clean = DISAMBIG_RE.sub("", val).strip()
        if not clean:
            removed.append(k)
            continue
        if clean != val:
            changed.append((k, val, clean))
        prev = out.get(kl)
        if prev is None:
            out[kl] = (k, clean)
        elif k[:1].isupper() and not prev[0][:1].isupper():
            # 小写去重：优先保留首字母大写的"句子式"变体
            removed.append(prev[0])
            out[kl] = (k, clean)
        else:
            removed.append(k)
    return ({k: v for k, (_, v) in out.items()}, removed, changed)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="只报告，不写回")
    args = ap.parse_args(argv)

    src = TERMS if os.path.exists(TERMS) else RAW
    d = json.load(io.open(src, encoding="utf-8"))
    if not os.path.exists(RAW):
        with io.open(RAW, "w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")

    new, removed, changed = curate(d)
    print("原始 %d 条 → 整理后 %d 条（剔除 %d）"
          % (len(d), len(new), len(removed)))
    for k in sorted(removed):
        print("  - %-42s %s" % (k, d[k]))
    for k, a, b in sorted(changed):
        print("  ~ %-42s %s → %s" % (k, a, b))

    if args.check:
        return 0
    with io.open(TERMS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(new, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print("已写入 %s" % TERMS, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
