#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""把指向 en.wikipedia.org 的词条链接改写成站内链接。

为什么需要
----------
正文里的 ``[黎曼ζ函数](https://en.wikipedia.org/wiki/Riemann_zeta_function)``
其实本站已经有译好的条目 ``docs/math/黎曼ζ函数.md``。指出去再让读者跳回来是绕路，
站内链接还能吃到 Docusaurus 的客户端路由，也不依赖外网站点存续。

只换 URL，**显示文字一个字不动**——`[黎曼ζ函数]` 还是 `[黎曼ζ函数]`。

映射从哪来（不猜、不联网）
--------------------------
只认「条目自己声明过的英文名」，且**只看开头段**（第一个 ``##`` 之前）：

* ``**词条名**（英语：English name）`` —— 站点文风规定写在开头，最可靠；
* ``**词条名**（English name）`` —— 没有「英语：」字样的写法（如 西格尔零点）。

正文靠后处出现的 ``（英语：polylogarithm）`` 之类**不算**：那是行文里顺手标注的
别名，真拿去建映射会把 ``en.wikipedia.org/wiki/polylogarithm`` 指到本条目自己身上
（黎曼ζ函数.md 里这类误报有十几处）。所以抽取范围严格限制在开头段。

``scripts/wikilink-aliases.json`` 可手工补重定向别名（如 ``twin prime conjecture``），
值写成 ``"math/孪生素数.md"`` 或 ``"math/孪生素数.md#孪生素数猜想"``。

锚点怎么换算
------------
``…/wiki/Riemann_hypothesis#Consequences`` 这种带小节的链接，靠**中英两版标题序列对齐**
换算成中文标题：``en.chinapedia/docs/<同路径>`` 存在时，逐条比对 ``##`` / ``###`` … 标题，
**从第一条层级对不上的地方就停止信任**（黎曼猜想.md 尾部 EN 有 ``## Notes`` 而中文版没有，
正是靠这条避免错位）。换算出的中文标题再用自身 slug 回验；**对不上就保持外链**——
``…/Riemann_hypothesis#CITEREFOdlyzko`` 这类锚点指向的是某条具体参考文献，
降级成条目页首反而更差（英文/泰语镜像里这类 ``#CITEREF*`` 很多）。
要降级成条目链接得显式加 ``--degrade-anchor``。

用法::

    python scripts/wikilink_localize.py docs --dry-run     # 只列出将要改的位置
    python scripts/wikilink_localize.py docs --check       # 有需要改的返回 1（给 CI）
    python scripts/wikilink_localize.py docs               # 就地改
    python scripts/wikilink_localize.py --map              # 打印推导出的映射表

幂等：改完是相对路径、不再是 ``en.wikipedia.org``，跑第二遍没有任何改动。
按字节读、按字节写，保留原文件的 CRLF / LF。
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

DOCS_DEFAULT = 'docs'
EN_DEFAULT = os.path.join('..', 'en.chinapedia', 'docs')
ALIAS_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'wikilink-aliases.json')

WIKI_HOSTS = frozenset(('en.wikipedia.org', 'en.m.wikipedia.org',
                        'www.en.wikipedia.org'))

# 只认 en.wikipedia.org 的 /wiki/<Title>；URL 里不含裸 ')'（数据里括号都是 %28/%29）
LINK_RE = re.compile(r'\[([^\]]*)\]\((https?://en\.wikipedia\.org/wiki/[^)\s]+)\)')

# 脚注定义行 `[^3]: [https://…](https://en.wikipedia.org/wiki/…)` 是**引用来源**，
# 改成站内链接等于「引用自己」，语义就错了。默认不动，--include-footnotes 才碰。
FOOTNOTE_DEF_RE = re.compile(r'^\[\^[^\[\]]+\]:')

# 开头段里声明英文名的两种写法。
# 注意 `(?:英语：|英語：|英文：)?` 里的 `：` 必须在分支**里面**——写成
# `(?:英语|英語|英文)：?` 会先吃掉「英语」、再要求下一个字符是字母，
# 于是 `**黎曼ζ函数**（英语：Riemann zeta function）` 反而匹配不上（踩过）。
BOLD_EN_RE = re.compile(
    r'\*\*([^*\n]{1,40})\*\*（(?:英语：|英語：|英文：)?([A-Za-z][^）\n]{0,60})）')
CJK_NAME_RE = re.compile(r'（(?:英语：|英語：|英文：)([^）\n]+)）')
# `…，简称 AIGC` —— 条目自己声明的缩写，也当成一个英文名
ABBR_RE = re.compile(r'简称\s*([A-Za-z][A-Za-z0-9-]*)')

HEAD_RE = re.compile(r'^(#{2,6})\s+(.+?)\s*$')

# `Artificial Intelligence Generated Content，简称 AIGC` → 只取第一段
_SEG_SPLIT_RE = re.compile(r'[，,；;、]')
# U+2010..U+2015 各种破折号；维基标题里 `Landau–Siegel` 用的是 U+2013
_DASH_RE = re.compile(r'[\u2010-\u2015]')
# 撇号有直/弯两种写法，文件名里通常干脆不写：维基 `Goldbach's_conjecture`
# 对应仓库里的 `goldbachs_conjecture.md`，所以归一化时一律抹掉。
_APOSTROPHE_RE = re.compile(u"['\u2018\u2019\u02bc]")
# github-slugger 删标点/符号，但这两个字符**保留**（实测 `_x_`→`_x_`、`a-b`→`a-b`）
_SLUG_KEEP = frozenset('-_')


# --------------------------------------------------------------------------- #
# 文本小工具
# --------------------------------------------------------------------------- #

def read_text(path):
    raw = open(path, 'rb').read()
    return raw.decode('utf-8'), raw


def normalize(title):
    """维基标题归一化：去百分号编码、下划线当空格、破折号统一、去撇号、小写。

    去撇号是为了对上「文件名把撇号丢掉」的条目：
    维基标题 ``Goldbach's_conjecture`` ↔ ``goldbachs_conjecture.md``。
    """
    t = unquote(title).replace('_', ' ')
    t = _DASH_RE.sub('-', t)
    t = _APOSTROPHE_RE.sub('', t)
    return re.sub(r'\s+', ' ', t).strip().lower()


def anchor_candidates(frag):
    """维基锚点的两种拼法。

    维基用下划线代替空格（``#Riemann's_functional_equation``），而 Docusaurus 的
    github-slugger 产出的是连字符（``riemanns-functional-equation``）。两种都试。
    """
    out = [slugify(frag)]
    alt = slugify(frag.replace('_', ' '))
    if alt not in out:
        out.append(alt)
    return out


def slugify(s):
    """对齐 github-slugger：删标点/符号 → 每个空格换一个连字符 → 小写。不 trim。

    规则不是猜的：读 `node_modules/github-slugger/index.js` 得到
    `string.toLowerCase().replace(regex, '').replace(/ /g, '-')`，
    regex 是 GitHub 自己生成的一张大字符类表（删标点/符号/控制符，
    但**保留** `-` 和 `_`，也保留组合符号）。

    **不能**用 `[^\\w\\s-]` 近似：泰语的元音/声调符号是 Mn 组合字符，`\\w` 不匹配，
    会被当标点删掉——`#สมการเชิงฟังก์ชันของรีมันน` 变成 `#สมการเชงฟงกชนของรมนน`，
    链接跳不到标题，而且肉眼根本看不出（泰语分支实测踩到）。
    """
    out = []
    for ch in s.lower():
        if ch == ' ':
            out.append('-')
        elif ch in _SLUG_KEEP:
            out.append(ch)
        elif unicodedata.category(ch)[0] not in ('P', 'S', 'C'):
            out.append(ch)
    return ''.join(out)


def slug_headings(heads):
    """[(层级, 标题)] → [slug]，并像 github-slugger 那样给重复标题加 -1/-2 后缀。

    Docusaurus 每页一个 slugger 实例，同页里两处 `## 参见` 会得到 `参见` / `参见-1`；
    对齐时若不复现这套后缀，第二处就会对不上。
    """
    seen, out = {}, []
    for _, text in heads:
        base = slugify(text)
        if base in seen:
            seen[base] += 1
            out.append('%s-%d' % (base, seen[base]))
        else:
            seen[base] = 0
            out.append(base)
    return out


def headings(text):
    """[(层级, 标题文本)]，只收 ## 及更深。"""
    out = []
    for line in text.split('\n'):
        m = HEAD_RE.match(line)
        if m:
            out.append((len(m.group(1)), m.group(2)))
    return out


def opening(text, max_lines=400):
    """开头段：第一个 ## 之前。

    这里**不能**只取前几十行：黎曼ζ函数.md 的开篇先是一个 ``<div className="figure-row">``
    图块，词条名的英文名声明落在第 33 行，卡 30 行就会漏掉整条映射。
    上限只是防止畸形文件无限扫描。
    """
    out = []
    for line in text.split('\n')[:max_lines]:
        if HEAD_RE.match(line):
            break
        out.append(line)
    return '\n'.join(out)


def _latinish(s):
    """是不是「英文名」——非空白字符里字母占 60% 以上。"""
    letters = sum(1 for c in s if c.isascii() and c.isalpha())
    nonspace = sum(1 for c in s if not c.isspace())
    return nonspace > 0 and letters >= 0.6 * nonspace


def _first_segment(s):
    return _SEG_SPLIT_RE.split(s)[0].strip()


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


# --------------------------------------------------------------------------- #
# 映射表
# --------------------------------------------------------------------------- #

def article_en_names(op):
    """开头段里**该条目自己**声明过的英文名。

    两条来源，缺一不可：

    * ``**词条名**（英语：X）`` / ``**词条名**（X）`` —— 粗体挂着的，全部收下
      （西格尔零点.md 一条粗体链上声明了三个：Landau–Siegel zero / Siegel zero /
      exceptional zero，都是同一个条目的别名）；
    * ``（英语：X）`` 的**第一处** —— 有些条目没加粗（AIGC、UGC）。

    只取第一处是关键：黎曼ζ函数.md 第 33 行声明 ``（英语：Riemann zeta function）``，
    第 40 行又有 ``莱昂哈德·欧拉（英语：Leonhard Euler）``——若不限制，
    就会把 ``en.wikipedia.org/wiki/Leonhard_Euler`` 指到本条目自己身上。
    """
    names, decls = [], []
    for mm in BOLD_EN_RE.finditer(op):
        decls.append(mm.group(0))
        names.append(mm.group(2))
    m = CJK_NAME_RE.search(op)
    if m:
        decls.append(m.group(0))
        seg = _first_segment(m.group(1))
        if seg:
            names.append(seg)
    for d in decls:                      # `…，简称 AIGC`
        names.extend(ABBR_RE.findall(d))
    # 粗体规则和「第一处」规则会命中同一条声明，去重（保序）
    out, seen = [], set()
    for n in (s.strip() for s in names):
        if n and _latinish(n) and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def derive_map(docs_root, exclude=('wow',), self_titles=False):
    """英文名（归一化）→ (站内相对路径, 该条目声明的英文名)。返回 (map, 冲突列表)。"""
    m, collisions = {}, []
    for path in iter_md([docs_root]):
        rel = os.path.relpath(path, docs_root).replace('\\', '/')
        if rel.split('/')[0] in exclude:
            continue
        try:
            text, _ = read_text(path)
        except (UnicodeDecodeError, OSError):
            continue
        names = article_en_names(opening(text))
        if self_titles:
            names.append(os.path.splitext(os.path.basename(rel))[0])
        for n in names:
            k = normalize(n)
            if not k:
                continue
            if k in m and m[k][0] != rel:
                collisions.append((k, m[k][0], rel))
                continue
            m[k] = (rel, n)
    return m, collisions


def load_aliases(path):
    """别名表：归一化英文名 → (站内相对路径, 锚点或 None)。"""
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    out = {}
    for k, v in (data.get('aliases') or {}).items():
        anchor = None
        if '#' in v:
            v, anchor = v.split('#', 1)
        out[normalize(k)] = (v, anchor or None)
    return out


def split_wiki_url(url):
    """en.wikipedia 词条链接 → (英文标题, 锚点或 None)；不是词条链接返回 None。

    锚点有两种写法：``…#Consequences``（真 fragment），以及 ``…%23Consequences``
    ——**数据里更多是后者**（黎曼猜想.md:51 的 ``Riemann_zeta_function%23Riemann%27s…``），
    它躺在 path 里、``urlsplit`` 的 fragment 是空的。所以先把 path 解码再切 ``#``。
    """
    parts = urlsplit(url)
    if parts.netloc not in WIKI_HOSTS or not parts.path.startswith('/wiki/'):
        return None
    raw = unquote(parts.path[len('/wiki/'):])
    frag = parts.fragment
    if '#' in raw:
        raw, extra = raw.split('#', 1)
        frag = frag or extra
    return raw, (unquote(frag) if frag else None)


class AnchorResolver:
    """英文小节标题 → 中文小节标题；按需读盘并缓存。

    中英两版的**文件名不一样**（英文镜像用 `riemann_hypothesis.md`，中文用
    `黎曼猜想.md`），所以不能按路径配对，得靠映射里记着的英文名去拼英文镜像的路径。
    """

    def __init__(self, docs_root, en_root):
        self.docs_root = docs_root
        self.en_root = en_root
        self.cache = {}

    def _en_path(self, target_rel, en_title):
        if not self.en_root or not en_title:
            return None
        stem = en_title.replace(' ', '_')
        cands = [stem, stem.lower(), en_title]
        for c in cands:
            p = os.path.join(self.en_root, *posixpath.dirname(target_rel).split('/'),
                             c + '.md')
            if os.path.exists(p):
                return p
        return None

    def map_for(self, target_rel, en_title):
        ck = (target_rel, en_title)
        if ck in self.cache:
            return self.cache[ck]
        out = {}
        en_path = self._en_path(target_rel, en_title)
        zh_path = os.path.join(self.docs_root, *target_rel.split('/'))
        if en_path and os.path.exists(zh_path):
            try:
                en_text, _ = read_text(en_path)
                zh_text, _ = read_text(zh_path)
            except (UnicodeDecodeError, OSError):
                en_text = zh_text = ''
            if en_text and zh_text:
                en_h, zh_h = headings(en_text), headings(zh_text)
                en_s, zh_s = slug_headings(en_h), slug_headings(zh_h)
                for (el, _), (zl, _), es, zs in zip(en_h, zh_h, en_s, zh_s):
                    if el != zl:
                        break        # 结构开始漂移，之后不再信任
                    out[es] = zs
        self.cache[ck] = out
        return out


def rel_link(cur_dir, target_rel):
    """从当前文件所在目录指向目标文件的相对链接（沿用站点 `./x.md` / `../a/x.md` 写法）。"""
    r = posixpath.relpath(target_rel, cur_dir or '.')
    return r if r.startswith('.') else './' + r


# --------------------------------------------------------------------------- #
# 给生成流水线用的入口
# --------------------------------------------------------------------------- #

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_ABS = os.path.join(REPO_ROOT, DOCS_DEFAULT)
EN_ABS = os.path.join(os.path.dirname(REPO_ROOT), 'en.chinapedia', 'docs')

_MAP_CACHE = {}


def docs_map(docs_root, self_titles=False):
    """推导并缓存映射表（一次运行只扫一遍 docs 树）。"""
    key = (os.path.abspath(docs_root), self_titles)
    if key not in _MAP_CACHE:
        _MAP_CACHE[key] = derive_map(docs_root, self_titles=self_titles)[0]
    return _MAP_CACHE[key]


def localize_text(text, path, docs_root=None, en_root=None, aliases_path=None,
                  also_self_titles=False, include_footnotes=False,
                  degrade_anchor=False, quiet=False):
    """把 ``text`` 里的 en.wikipedia 词条外链改写成站内链接，返回新文本。

    给 ``md2zh.py`` / ``wiki2md.py`` 在写盘前调用，这样**新生成的条目自动带上站内链接**，
    而不是等人工发现再补。``path`` 是这篇文档自身的路径（用来算相对链接）。
    """
    docs_root = os.path.abspath(docs_root or DOCS_ABS)
    en_root = EN_ABS if en_root is None else en_root
    try:
        rel = os.path.relpath(os.path.abspath(path), docs_root).replace('\\', '/')
    except ValueError:
        return text        # Windows 上跨盘符：relpath 直接抛，别硬算
    if rel.startswith('..'):
        return text                      # 不在 docs 树里，别乱算相对路径
    new, changes, skipped = rewrite_text(
        text, rel, docs_root, docs_map(docs_root, also_self_titles),
        load_aliases(aliases_path or ALIAS_DEFAULT),
        AnchorResolver(docs_root, en_root), include_footnotes, degrade_anchor)
    if changes and not quiet:
        print('→ 站内链接改写 %d 处（en.wikipedia → 本站条目）' % len(changes))
    return new


# --------------------------------------------------------------------------- #
# 改写
# --------------------------------------------------------------------------- #

def rewrite_text(text, rel, docs_root, mapping, aliases, anchors,
                 include_footnotes=False, degrade_anchor=False):
    """返回 (新文本, 改动列表, 未采用列表)。改动列表元素：(行号, 原文, 新文)。"""
    cur_dir = posixpath.dirname(rel)
    changes, skipped = [], []
    out_lines = []

    for i, line in enumerate(text.split('\n'), 1):
        if 'en.wikipedia.org/wiki/' not in line:
            out_lines.append(line)
            continue
        if not include_footnotes and FOOTNOTE_DEF_RE.match(line):
            out_lines.append(line)
            continue

        def sub(m):
            disp, url = m.group(1), m.group(2)
            parsed = split_wiki_url(url)
            if parsed is None:
                return m.group(0)
            title, frag = parsed
            key = normalize(title)

            anchor, en_title = None, None
            if key in aliases:
                target, anchor = aliases[key]
            elif key in mapping:
                target, en_title = mapping[key]
            else:
                return m.group(0)        # 站内没有译好的版本，保持外链

            if not os.path.exists(os.path.join(docs_root, *target.split('/'))):
                skipped.append((i, m.group(0), '站内文件不存在: ' + target))
                return m.group(0)

            if anchor is None and frag:
                hmap = anchors.map_for(target, en_title)
                for cand in anchor_candidates(frag):
                    if cand in hmap:
                        anchor = hmap[cand]
                        break
                if not anchor:
                    # 锚点换算不出来时**默认保持外链**：`…/Riemann_hypothesis#CITEREFOdlyzko`
                    # 这种是指向某条具体参考文献的引用，降级成条目页首反而更差
                    # （英文/泰语镜像里这类 #CITEREF* 很多）。要降级得显式开
                    # --degrade-anchor。
                    if not degrade_anchor:
                        skipped.append((i, m.group(0),
                                        '锚点 %r 无法换算 → 保持外链' % frag))
                        return m.group(0)
                    skipped.append((i, m.group(0),
                                    '锚点 %r 无法换算，已降级为条目链接' % frag))

            new = '[%s](%s%s)' % (disp, rel_link(cur_dir, target),
                                  '#' + anchor if anchor else '')
            changes.append((i, m.group(0), new))
            return new

        out_lines.append(LINK_RE.sub(sub, line))

    return '\n'.join(out_lines), changes, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='把 en.wikipedia.org 词条链接改写成站内链接')
    ap.add_argument('paths', nargs='*', default=[DOCS_DEFAULT],
                    help='文件或目录（默认 docs）')
    ap.add_argument('--docs-root', default=DOCS_DEFAULT,
                    help='文档根目录，用来算相对路径（默认 docs）')
    ap.add_argument('--en-root', default=EN_DEFAULT,
                    help='英文镜像 docs 目录，用来对齐小节标题（默认 ../en.chinapedia/docs）')
    ap.add_argument('--aliases', default=ALIAS_DEFAULT, help='别名表 JSON')
    ap.add_argument('--map', action='store_true', help='只打印映射表')
    ap.add_argument('--also-self-titles', action='store_true',
                    help='把每个条目自己的文件名也当作英文名加进映射（英文/泰语站用）')
    ap.add_argument('--include-footnotes', action='store_true',
                    help='连脚注定义里的引用来源一起改写（默认不动）')
    ap.add_argument('--degrade-anchor', action='store_true',
                    help='锚点换算不出来时降级为条目链接（默认保持外链，'
                         '因为 #CITEREF* 这类引用锚点降级反而更差）')
    ap.add_argument('--dry-run', action='store_true', help='只列出，不写盘')
    ap.add_argument('--check', action='store_true',
                    help='有需要改的就返回 1（不写盘），给 CI / 预检用')
    ap.add_argument('--json', action='store_true',
                    help='按 JSON 输出（不写盘），给 prebuild_check.mjs 用')
    args = ap.parse_args(argv)

    mapping, collisions = derive_map(args.docs_root,
                                     self_titles=args.also_self_titles)
    aliases = load_aliases(args.aliases)

    if args.map:
        print('站内条目英文名 → 路径（%d 条，别名 %d 条）' % (len(mapping),
                                                          len(aliases)))
        for k in sorted(mapping):
            print('  %-46s %s' % (k, mapping[k][0]))
        if aliases:
            print('\n别名:')
            for k in sorted(aliases):
                t, a = aliases[k]
                print('  %-46s %s%s' % (k, t, '#' + a if a else ''))
        if collisions:
            print('\n冲突（同名不同条目，已保留先出现的）:')
            for k, a, b in collisions:
                print('  %-40s %s  /  %s' % (k, a, b))
        return 0

    anchors = AnchorResolver(args.docs_root, args.en_root)
    total_files = total_changes = 0
    json_out = {'files': {}, 'skipped': []}
    for p in iter_md(args.paths):
        try:
            text, raw = read_text(p)
        except (UnicodeDecodeError, OSError) as exc:
            if not args.json:
                print('跳过 %s: %s' % (p, exc))
            continue
        rel = os.path.relpath(p, args.docs_root).replace('\\', '/')
        new, changes, skipped = rewrite_text(
            text, rel, args.docs_root, mapping, aliases, anchors,
            args.include_footnotes, args.degrade_anchor)
        if args.json:
            if changes:
                json_out['files'][rel] = [[ln, b, a] for ln, b, a in changes]
            json_out['skipped'].extend([rel, ln, why] for ln, _, why in skipped)
            continue
        if not changes:
            continue
        total_files += 1
        total_changes += len(changes)
        if args.check or args.dry_run:
            print('%s  (%d 处)' % (rel, len(changes)))
            for ln, before, after in changes:
                print('    L%-5d %s' % (ln, before[:110]))
                print('      →    %s' % after[:110])
        else:
            open(p, 'wb').write(new.encode('utf-8'))
            print('%-52s 改 %d 处' % (rel, len(changes)))
        for ln, link, why in skipped:
            print('    ! L%-5d %s' % (ln, why))

    if args.json:
        json.dump(json_out, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write('\n')
        return 1 if json_out['files'] else 0

    if args.check:
        if total_files:
            print('\n× %d 个文件、%d 处外链可以改站内链接' % (total_files,
                                                       total_changes))
            print('  修：python scripts/wikilink_localize.py %s'
                  % ' '.join(args.paths))
            return 1
        print('√ 没有可改写的 en.wikipedia 词条链接')
        return 0

    verb = '将改' if args.dry_run else '已改'
    print('\n%s %d 个文件、%d 处' % (verb, total_files, total_changes))
    return 0


if __name__ == '__main__':
    sys.exit(main())
