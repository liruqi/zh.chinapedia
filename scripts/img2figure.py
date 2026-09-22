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
import json
import os
import re
import sys
import urllib.parse
import urllib.request

# 整行只有一张图片：![alt](url)  或  ![alt](url "title")
# title 里 "w250" 表示来自 wikitext 的显示宽度，会被转写成 figure 的 max-width
IMG_LINE_RE = re.compile(r'^!\[(?P<alt>.*)\]\((?P<url>\S+?)(?:\s+"(?P<title>[^"]*)")?\)\s*$')

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

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


# --------------------------------------------------- 回填 wikitext 里的显示宽度
# 已经转成 <figure> 的文章拿不到宽度（`250px` 在转换时被丢掉了），
# 用这个模式回 wikitext 里查一遍，给裸 <figure> 补上 maxWidth。
FILE_NS_RE = re.compile(r"\[\[\s*(?:File|Image)\s*:", re.I)
SIZE_RE = re.compile(r"^\s*(\d+)\s*(?:x\s*\d+)?\s*px\s*$", re.I)
UPRIGHT_RE = re.compile(r"^\s*upright\s*(?:=\s*([\d.]+))?\s*$", re.I)
DEFAULT_THUMB = 220   # 维基缩略图默认宽度，upright=N 按它折算


def split_top_level(inner):
    """按顶层 | 切分 [[File:…]] 的内部内容。

    不能用正则 `\\|[^\\[\\]]*` 硬切：图注里常带 `[[domain coloring]]` 和
    `{{cite web|url=…}}`，正则会被内部的 `[` 卡住，整条 `[[File:…]]` 都匹配不上
    （实测因此漏掉了 Cplot zeta.svg 的 250px）。这里只在 depth 0 处切，
    depth 由 `[[` / `{{` 计数。
    """
    parts, cur, depth, i = [], [], 0, 0
    while i < len(inner):
        if inner.startswith("[[", i) or inner.startswith("{{", i):
            depth += 1
            cur.append(inner[i:i + 2])
            i += 2
            continue
        if inner.startswith("]]", i) or inner.startswith("}}", i):
            depth -= 1
            cur.append(inner[i:i + 2])
            i += 2
            continue
        if inner[i] == "|" and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(inner[i])
        i += 1
    parts.append("".join(cur))
    return parts


def iter_wiki_files(text):
    """逐个产出 (文件名, [参数…])。用括号配对扫描，能扛住嵌套的 [[ ]] / {{ }}。"""
    for m in FILE_NS_RE.finditer(text):
        depth, j = 0, m.start()
        while j < len(text):
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
            continue
        parts = split_top_level(text[m.start() + 2:j - 2])
        if parts and parts[0].strip():
            name = re.sub(r"^\s*(?:File|Image)\s*:\s*", "", parts[0], flags=re.I)
            yield name.strip(), parts[1:]


def wikitext_widths(text):
    """{wiki 文件名: 显示宽度 px}。只收**显式**给了尺寸的（`250px` / `upright=1.4`）。

    没给尺寸的（裸 `thumb`、裸 `upright`）不写进去 —— 那样会被固定成 220px，
    反而比现在更小；交给 custom.css 的 max-height 兜底就好。
    """
    out = {}
    for name, args in iter_wiki_files(text):
        width = None
        for raw in args:
            part = raw.strip()
            sm = SIZE_RE.match(part)
            if sm:
                width = int(sm.group(1))
                break
            um = UPRIGHT_RE.match(part)
            # 裸 `upright`（没给倍数）不算显式尺寸：它只是「按默认缩略图宽度」，
            # 折算成 220px 会把竖版大图（论文首页扫描件）压得看不清字。
            if um and um.group(1):
                width = round(DEFAULT_THUMB * float(um.group(1)))
                break
        if width and name not in out:
            out[name] = width
    return out


def load_url_to_file(path=None):
    """wikiimg-map.json 反向表：R2 图片 URL → wikitext 里的 File 名。

    映射的键形如 "docs/math|1000|Cplot zeta.svg"，值里带 'url'。
    """
    path = path or os.path.join(SCRIPTS_DIR, "wikiimg-map.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = {}
    for k, v in data.items():
        if not isinstance(v, dict) or not v.get("url"):
            continue
        parts = k.split("|")
        if len(parts) >= 3:
            out[v["url"]] = "|".join(parts[2:])
    return out


def fetch_wikitext_raw(url):
    """从 en/zh.wikipedia 取原始 wikitext（不依赖 wiki2md，少一层耦合）。"""
    parsed = urllib.parse.urlparse(url)
    lang = (parsed.netloc or "en.wikipedia.org").split(".")[0]
    title = urllib.parse.unquote(parsed.path.rsplit("/wiki/", 1)[-1]).replace("_", " ")
    api = ("https://%s.wikipedia.org/w/api.php?action=parse&prop=wikitext"
           "&redirects=1&format=json&formatversion=2&page=%s"
           % (lang, urllib.parse.quote(title)))
    req = urllib.request.Request(api, headers={
        "User-Agent": "zh.chinapedia-img2figure/1.0 (+https://github.com/liruqi/zh.chinapedia)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return (data.get("parse") or {}).get("wikitext") or ""


def load_wikitext(src):
    """src 可以是本地文件路径，也可以是 wikipedia 条目 URL。"""
    if re.match(r"^https?://", src):
        return fetch_wikitext_raw(src)
    with open(src, encoding="utf-8", errors="replace") as fh:
        return fh.read()


FIG_OPEN_RE = re.compile(r'^<figure(\s+className="(?P<cls>[^"]*)")?\s*>$')


def apply_widths(text, widths, url2file):
    """给已有的裸 <figure> 补 maxWidth。幂等：已经有 style 的跳过。"""
    lines = text.replace("\r\n", "\n").split("\n")
    changed = 0
    for i, line in enumerate(lines):
        m = FIG_OPEN_RE.match(line.strip())
        if not m:
            continue
        url = None
        for j in range(i + 1, min(i + 12, len(lines))):
            if lines[j].strip().startswith("</figure"):
                break
            im = IMG_LINE_RE.match(lines[j].strip())
            if im:
                url = im.group("url")
                break
        if not url:
            continue
        fname = url2file.get(url)
        width = widths.get(fname) if fname else None
        if not width:
            continue
        cls = ' className="%s"' % m.group("cls") if m.group("cls") else ""
        lines[i] = '<figure%s style={{"maxWidth": "%dpx"}}>' % (cls, width)
        changed += 1
    return "\n".join(lines), changed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="要处理的 .md 文件")
    ap.add_argument("--dry-run", action="store_true", help="只报告不写盘")
    ap.add_argument("--refresh-alt", action="store_true",
                    help="只按 figcaption 重算已有 <figure> 的 alt（不重新转换）")
    ap.add_argument("--from-wikitext", default=None, metavar="PATH_OR_URL",
                    help="wikitext 文件或 wikipedia 条目 URL：给已有 <figure> "
                         "回填 wikitext 里写的显示宽度（maxWidth）")
    args = ap.parse_args()

    widths, url2file = {}, {}
    if args.from_wikitext:
        wt = load_wikitext(args.from_wikitext)
        widths = wikitext_widths(wt)
        url2file = load_url_to_file()
        print("wikitext 里带显式尺寸的图: %d 张，R2 映射表: %d 条"
              % (len(widths), len(url2file)), file=sys.stderr)

    for p in args.paths:
        with open(p, "rb") as fh:
            raw = fh.read()
        # 统一成 \n 再处理，写盘时再转回 CRLF（仓库是 core.autocrlf=true）
        text = raw.decode("utf-8").replace("\r\n", "\n")
        if args.from_wikitext:
            new, n_img = apply_widths(text, widths, url2file)
            label = "个 <figure> 补上 maxWidth"
        elif args.refresh_alt:
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
