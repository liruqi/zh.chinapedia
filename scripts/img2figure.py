r"""把独立的图片行改写成 <figure> + <figcaption>，让图注真正显示出来。

背景
----
wikitext 里的 `[[File:X|thumb|图注]]` 在维基页面上渲染成

    <figure><img src=...><figcaption>图注</figcaption></figure>

而机械转换出来的 markdown 只有 `![图注](url)` —— 图注被塞进了 alt 属性，
**肉眼完全看不见**，只剩一张没说明的图。而且连续几行图片会被合并进同一个
段落，变成并排显示而不是各自成块。

这个脚本把「整行只有一张图片」的行改写成

    <figure>

    ![图注纯文本](url)

    <figcaption>

    图注（可以是 markdown：链接 / $公式$ / 脚注）

    </figcaption>

    </figure>

MDX 要求：JSX 块的子内容要用空行隔开才会被当作 markdown 解析，
所以 figure / figcaption 的内侧都留空行。alt 用去掉 markdown 语法的
纯文本版本（alt 里出现 `[文字](url)`、`$x$`、`[^1]` 都是噪音）。

用法
----
    python scripts/img2figure.py docs/math/黎曼ζ函数.md [更多文件…]
    python scripts/img2figure.py --dry-run docs/math/*.md

幂等：已经包在 <figure> 里的图片行不会被重复处理。
"""
import argparse
import os
import re
import sys

# 整行只有一张图片：![alt](url)  或  ![alt](url "title")
# title 里 "w250" 表示来自 wikitext 的显示宽度，会被转写成 figure 的 max-width
IMG_LINE_RE = re.compile(r'^!\[(?P<alt>.*)\]\((?P<url>\S+?)(?:\s+"(?P<title>[^"]*)")?\)\s*$')

# alt 是纯文本，公式要降级成能读的字符。直接去掉 $ 会露出 \zeta 这种裸 LaTeX。
SYMBOL = {
    # 希腊字母
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "θ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
    "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    # 常用符号
    "infty": "∞", "leq": "≤", "geq": "≥", "neq": "≠", "pm": "±", "mp": "∓",
    "times": "×", "cdot": "·", "cdots": "…", "ldots": "…", "dots": "…",
    "approx": "≈", "sim": "∼", "equiv": "≡", "to": "→", "rightarrow": "→",
    "leftarrow": "←", "Rightarrow": "⇒", "in": "∈", "notin": "∉",
    "subset": "⊂", "cup": "∪", "cap": "∩", "sum": "∑", "prod": "∏",
    "int": "∫", "partial": "∂", "nabla": "∇", "forall": "∀", "exists": "∃",
    "emptyset": "∅", "hbar": "ℏ", "ell": "ℓ", "Re": "Re", "Im": "Im",
    "log": "log", "sin": "sin", "cos": "cos", "tan": "tan", "exp": "exp",
    "lim": "lim", "max": "max", "min": "min", "sup": "sup", "inf": "inf",
}
# \mathbb{R} → ℝ
BB = {"R": "ℝ", "C": "ℂ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "F": "𝔽", "H": "ℍ"}


def _tex2plain(s):
    """把一段公式尽量降级成可读纯文本（alt 用）。"""
    s = re.sub(r"\\mathbb\{([A-Z])\}", lambda m: BB.get(m.group(1), m.group(1)), s)
    s = re.sub(r"\\operatorname\*?\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:text|mathrm|mbox)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√\1", s)
    s = re.sub(r"\\([A-Za-z]+)", lambda m: SYMBOL.get(m.group(1), m.group(1)), s)
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\\[,;:! ]", " ", s)          # \, \; 这类间距控制
    s = s.replace("\\", "")
    s = re.sub(r"\^|_", "", s)                 # 上标下标标记
    return s


def strip_md(text):
    """把 markdown 降级成纯文本，用于 <img alt>。

    [文字](url) → 文字      $x$ → 可读文本      [^1] → （删掉）      **粗** → 粗
    """
    s = text
    s = re.sub(r"\[\^[^\]]+\]", "", s)              # 脚注标记
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)  # 嵌套图片
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)   # 链接

    def math_sub(m):
        return _tex2plain(m.group(1))
    s = re.sub(r"\$\$?([\s\S]*?)\$\$?", math_sub, s)  # 公式

    s = s.replace("**", "").replace("*", "")
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)                     # 残留的 HTML 标签
    s = _tex2plain(s)                                 # 兜底：没被 $ 包住的裸 LaTeX
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_inside_figure(lines, i):
    """往上找，判断第 i 行是否已经在某个 <figure> … </figure> 里。"""
    depth = 0
    for j in range(i - 1, -1, -1):
        t = lines[j].strip()
        if t.startswith("</figure"):
            depth += 1
        elif t.startswith("<figure"):
            if depth == 0:
                return True
            depth -= 1
    return False


def convert(text):
    """返回 (新文本, 改动的图片数)。"""
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    changed = 0
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = IMG_LINE_RE.match(line.strip())
        if not m or is_inside_figure(lines, i):
            out.append(line)
            i += 1
            continue

        alt_md = m.group("alt")
        url = m.group("url")
        title = m.group("title")
        plain = strip_md(alt_md)
        if not plain:
            plain = os.path.splitext(os.path.basename(url.split("?")[0]))[0]

        width = None
        if title:
            wm = re.match(r'^w(\d+)$', title)
            if wm:
                width = int(wm.group(1))

        # MDX/JSX 里 style 必须传对象，不能传字符串
        style = ' style={{"maxWidth": "%dpx"}}' % width if width else ''
        block = ["<figure%s>" % style, "", "![%s](%s)" % (plain, url), ""]
        if alt_md.strip():
            block += ["<figcaption>", "", alt_md.strip(), "", "</figcaption>", ""]
        block.append("</figure>")
        out.extend(block)
        changed += 1
        i += 1

    new = "\n".join(out)
    # 连续两张图会生成两个紧挨着的 <figure>，中间补个空行，读起来 / 解析都更稳
    new = re.sub(r"</figure>\n(?=<figure>)", "</figure>\n\n", new)
    return new, changed


# 已有的 <figure> 块：<img> 行 + 可选的 <figcaption> 段
FIG_BLOCK_RE = re.compile(
    r"<figure>\n\n"
    # alt 里可以有 ]（比如 "[x,y,z] = [Re(ζ), Im(ζ), t]"），所以取值时不能禁用 ]
    r"(?P<img>!\[(?P<alt>.*?)\]\((?P<url>\S+?)(?:\s+\"[^\"]*\")?\))\n\n"
    r"(?:<figcaption>\n\n(?P<cap>[\s\S]*?)\n\n</figcaption>\n\n)?"
    r"</figure>")


def refresh_alt(text):
    """改了 strip_md（比如补了 LaTeX→Unicode 映射）之后，用它把已有 figure 的
    alt 按 figcaption 的原文重算一遍，不用重新转换整篇文章。"""
    n = 0

    def sub(m):
        nonlocal n
        src_md = m.group("cap") if m.group("cap") else m.group("alt")
        plain = strip_md(src_md) or m.group("alt")
        n += 1
        return (m.group(0).replace(m.group("img"),
                                   "![%s](%s)" % (plain, m.group("url"))))
    return FIG_BLOCK_RE.sub(sub, text), n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="要处理的 .md 文件")
    ap.add_argument("--dry-run", action="store_true", help="只报告不写盘")
    ap.add_argument("--refresh-alt", action="store_true",
                    help="只按 figcaption 重算已有 <figure> 的 alt（不重新转换）")
    args = ap.parse_args()

    for p in args.paths:
        with open(p, "rb") as fh:
            raw = fh.read()
        # 统一成 \n 再处理，写盘时再转回 CRLF（仓库是 core.autocrlf=true）
        text = raw.decode("utf-8").replace("\r\n", "\n")
        if args.refresh_alt:
            new, n_img = refresh_alt(text)
            label = "重算 alt"
        else:
            new, n_img = convert(text)
            label = "张图 → <figure>"
        if n_img == 0:
            print("= (无改动) %s" % p)
            continue
        print("%s %s：%d %s" % ("(dry)" if args.dry_run else "√", p, n_img, label))
        if args.dry_run:
            continue
        data = new.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
        with open(p, "wb") as fh:
            fh.write(data)


if __name__ == "__main__":
    sys.exit(main())
