#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wikilink_localize 的回归用例：URL 拆解、标题归一化、锚点换算、端到端改写。

    python scripts/test_wikilink_localize.py

每个用例都是实际踩出来的：``%23`` 形式的锚点、维基锚点用下划线、英文镜像文件名
与中文文件名不一致、`（英语：…）` 在正文里反复出现导致的误映射。
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wikilink_localize as W                                  # noqa: E402

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'docs')
SCRIPTS = os.path.dirname(os.path.abspath(__file__))

fail = 0


def check(desc, got, want):
    global fail
    ok = got == want
    fail += 0 if ok else 1
    print('%s %-44s %r' % ('✓' if ok else '✗', desc, got))
    if not ok:
        print('      期望 %r' % (want,))


print('--- split_wiki_url ---')
U = 'https://en.wikipedia.org/wiki/'
check('普通词条链接', W.split_wiki_url(U + 'Riemann_zeta_function'),
      ('Riemann_zeta_function', None))
check('# 形式锚点', W.split_wiki_url(U + 'Riemann_hypothesis#Consequences'),
      ('Riemann_hypothesis', 'Consequences'))
# 数据里更多是 %23 形式，锚点躺在 path 里、urlsplit 的 fragment 是空的
check('%23 形式锚点', W.split_wiki_url(
    U + 'Riemann_zeta_function%23Riemann%27s_functional_equation'),
    ('Riemann_zeta_function', "Riemann's_functional_equation"))
check('百分号编码标题（返回值已解码）', W.split_wiki_url(U + 'Andr%C3%A9_Weil'),
      ('André_Weil', None))
check('带括号的词条名（返回值已解码）',
      W.split_wiki_url(U + 'James_Maynard_%28mathematician%29'),
      ('James_Maynard_(mathematician)', None))
check('移动版域名也算', W.split_wiki_url(
    'https://en.m.wikipedia.org/wiki/Riemann_hypothesis'),
    ('Riemann_hypothesis', None))
check('别的站点 → None', W.split_wiki_url('https://en.wikipedia.org/wiki-x'),
      None)
check('非 /wiki/ 路径 → None', W.split_wiki_url(
    'https://en.wikipedia.org/w/index.php?title=X'), None)
check('外站 → None', W.split_wiki_url('https://example.org/wiki/X'), None)

print('\n--- normalize ---')
check('下划线当空格', W.normalize('Riemann_zeta_function'),
      'riemann zeta function')
check('大小写等价', W.normalize('Twin_prime'), W.normalize('twin prime'))
# 维基标题里 Landau–Siegel 用的是 U+2013，链接里是 %E2%80%93
check('破折号归一', W.normalize('Landau%E2%80%93Siegel_zero'),
      'landau-siegel zero')
# 文件名常把撇号丢掉：goldbachs_conjecture.md ↔ 维基 Goldbach's_conjecture
check('撇号归一（直引号）', W.normalize("Goldbach's_conjecture"),
      'goldbachs conjecture')
check('撇号归一（弯引号）', W.normalize(u'Goldbach\u2019s_conjecture'),
      'goldbachs conjecture')
check('撇号：维基标题与文件名等价',
      W.normalize("Goldbach's_conjecture"), W.normalize('goldbachs_conjecture'))

print('\n--- slugify（必须与 github-slugger 逐字一致）---')
# 期望值全部来自真 `github-slugger`（node -e "new S().slug(...)"）的实测输出，
# 不是照着自己的实现反推的。规则见 node_modules/github-slugger/index.js：
#   string.toLowerCase().replace(regex, '').replace(/ /g, '-')
# 即「删标点/符号/控制符，但保留 - 和 _」+「每个空格换一个连字符」+「不 trim」。
SLUG_CASES = [
    ("Riemann's functional equation", 'riemanns-functional-equation'),
    ('Lee–Yang theorem', 'leeyang-theorem'),
    ('推论', '推论'),
    ('点a,b', '点ab'),
    ('x: y?', 'x-y'),
    ('1+1 = 2', '11--2'),
    ('a\u2018b', 'ab'),
    (' x ', '-x-'),                 # 不 trim
    ('a  b', 'a--b'),               # 不合并空白：两个空格 → 两个连字符
    ('--a--', '--a--'),
    ('_x_', '_x_'),                 # 下划线保留（不是「删所有标点」）
    ('a-b', 'a-b'),                 # 连字符保留
    ('$D \\lt 0$', 'd-lt-0'),
    # 泰语元音/声调符号是 Mn 组合字符。用 [^\w\s-] 近似会把它们当标点删掉，
    # 锚点跳不到标题还看不出错（泰语分支实测踩到）
    ('สมการเชิงฟังก์ชันของรีมันน', 'สมการเชิงฟังก์ชันของรีมันน'),
    ('จุดไวยากรณ์', 'จุดไวยากรณ์'),
    ('ข้อความคาดการณ์ของเกาส์', 'ข้อความคาดการณ์ของเกาส์'),
]
for text, want in SLUG_CASES:
    check('slug %r' % text[:26], W.slugify(text), want)

print('\n--- slug_headings（重复标题要加 -1 后缀）---')
check('重复标题',
      W.slug_headings([(2, '参见'), (2, '参见'), (2, '参见'), (2, '其他')]),
      ['参见', '参见-1', '参见-2', '其他'])
check('不重复', W.slug_headings([(2, 'A'), (3, 'B')]), ['a', 'b'])

print('\n--- slugify 差分测试（对真 github-slugger）---')
# 上面是「想得到的」用例；这里拿仓库里所有真实标题 + 一批刁钻样本跟真库逐条对比，
# 抓的是「没想到的那种偏离」。找不到 node / github-slugger 就安静跳过。
import glob                                                     # noqa: E402
import json                                                     # noqa: E402
import shutil                                                   # noqa: E402
import subprocess                                               # noqa: E402

NODE = shutil.which('node')
MODULES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'node_modules')
if NODE and os.path.isdir(os.path.join(MODULES, 'github-slugger')):
    heads = []
    for p in glob.glob(os.path.join(DOCS, '**', '*.md'), recursive=True):
        if os.sep + 'wow' + os.sep in p:
            continue
        heads.extend(t for _, t in W.headings(open(p, encoding='utf-8').read()))
    extra = ["Riemann's functional equation", 'Lee–Yang theorem', '点a,b', 'x: y?',
             '1+1 = 2', ' x ', 'a  b', '--a--', '_x_', 'a-b', '$D \\lt 0$',
             'สมการเชิงฟังก์ชันของรีมันน', 'จุดไวยากรณ์', 'ข้อความคาดการณ์ของเกาส์',
             'A_1 & B+2', '50%', '±x', '日本語・中文']
    heads.extend(extra)
    payload = json.dumps([[t, W.slugify(t)] for t in heads], ensure_ascii=False)
    script = (
        "const S=require('github-slugger');"
        "const d=JSON.parse(require('fs').readFileSync(0,'utf8'));"
        "let bad=0;"
        "for(const [t,py] of d){const js=new S().slug(t);"
        "if(js!==py){bad++;console.log(JSON.stringify([t,js,py]));}}"
        "console.log('BAD='+bad);"
    )
    env = dict(os.environ, NODE_PATH=MODULES)
    r = subprocess.run([NODE, '-e', script], input=payload, env=env,
                       capture_output=True, text=True, encoding='utf-8')
    lines = [l for l in r.stdout.splitlines() if l.startswith('BAD=')]
    bad = int(lines[0][4:]) if lines else -1
    if bad < 0:
        print('跳过（node 调用失败）:', (r.stderr or '').splitlines()[:1])
    else:
        check('与 github-slugger 一致（%d 条）' % len(heads), bad, 0)
else:
    print('跳过（没有 node 或 github-slugger）')

print('\n--- anchor_candidates ---')
# 维基用下划线代替空格，github-slugger 产出连字符，两种都得试
check('下划线锚点', 'riemanns-functional-equation' in
      W.anchor_candidates("Riemann's_functional_equation"), True)
check('下划线锚点2', 'gram-points' in W.anchor_candidates('Gram_points'), True)
check('已经是连字符', 'gram-points' in W.anchor_candidates('gram-points'), True)
check('CJK 锚点', W.anchor_candidates('推论'), ['推论'])

print('\n--- rel_link ---')
check('同目录', W.rel_link('math', 'math/黎曼ζ函数.md'), './黎曼ζ函数.md')
check('跨分类', W.rel_link('ai/product', 'person/@steipete.md'),
      '../../person/@steipete.md')
check('子目录', W.rel_link('math', 'math/sub/x.md'), './sub/x.md')

print('\n--- _latinish / article_en_names ---')
check('纯英文名', W._latinish('Riemann zeta function'), True)
check('中文名不算英文名', W._latinish('黎曼ζ函数'), False)
check('粗体 + 英语：', W.article_en_names('**黎曼ζ函数**（英语：Riemann zeta function），或称…'),
      ['Riemann zeta function'])
check('粗体 + 直接括号（西格尔零点写法）',
      W.article_en_names('**西格尔零点**（Siegel zero）'), ['Siegel zero'])
# 一条粗体链上声明多个别名（西格尔零点.md 的 Landau–Siegel zero / Siegel zero /
# exceptional zero）要全部收下
check('粗体链多个别名',
      W.article_en_names('**兰道–西格尔零点**（Landau–Siegel zero），通常简称'
                         '**西格尔零点**（Siegel zero），也称**例外零点**（exceptional zero）'),
      ['Landau–Siegel zero', 'Siegel zero', 'exceptional zero'])
# 关键：只取第一处。黎曼ζ函数.md 第 40 行还有「莱昂哈德·欧拉（英语：Leonhard Euler）」，
# 若全收就会把 Leonhard_Euler 指到本条目自己身上
check('普通括号只取第一处',
      W.article_en_names('**黎曼ζ函数**（英语：Riemann zeta function）…'
                         '莱昂哈德·欧拉（英语：Leonhard Euler）于十八世纪…'),
      ['Riemann zeta function'])
check('简称也算英文名',
      W.article_en_names('人工智能生成内容（英语：Artificial Intelligence '
                         'Generated Content，简称 AIGC），又称…'),
      ['Artificial Intelligence Generated Content', 'AIGC'])
check('中文括号不误收', W.article_en_names('**ζ函数**（即黎曼的函数）'), [])

print('\n--- derive_map（真 docs 目录）---')
if os.path.isdir(DOCS):
    m, collisions = W.derive_map(DOCS)
    want = {
        'riemann zeta function': 'math/黎曼ζ函数.md',
        'riemann hypothesis': 'math/黎曼猜想.md',
        'twin prime': 'math/孪生素数.md',
        'siegel zero': 'math/西格尔零点.md',
        'landau-siegel zero': 'math/西格尔零点.md',
    }
    for k, v in want.items():
        check('映射 %s' % k, m.get(k, (None,))[0], v)
    # 正文里顺手标注的别名不能进映射
    for bad in ('leonhard euler', 'polylogarithm', 'critical line theorem',
                'generalized riemann hypothesis',
                'riemann hypothesis for curves over finite fields'):
        check('不该进映射: %s' % bad, bad in m, False)
    check('无冲突', collisions, [])
else:
    print('跳过（找不到 docs/）')

print('\n--- rewrite_text 端到端 ---')
tmp = tempfile.mkdtemp(prefix='wll-')
for sub in ('math', 'ai/product', 'person'):
    os.makedirs(os.path.join(tmp, 'docs', *sub.split('/')), exist_ok=True)
    os.makedirs(os.path.join(tmp, 'en', *sub.split('/')), exist_ok=True)


def w(rel, text, base='docs'):
    p = os.path.join(tmp, base, *rel.split('/'))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as fh:
        fh.write(text)


# 中英两版标题序列对齐（英文镜像文件名与中文不同，靠映射里记的英文名配对）
w('math/riemann_hypothesis.md',
  '## Riemann zeta function\n\n## Origin\n\n## Consequences\n\n### Gram points\n',
  base='en')
w('math/黎曼猜想.md',
  '## 黎曼ζ函数\n\n## 起源\n\n## 推论\n\n### 格拉姆点\n')
w('math/黎曼ζ函数.md', '## 定义\n')
w('math/孪生素数.md', '## 孪生素数猜想\n')

MAP = {
    'riemann hypothesis': ('math/黎曼猜想.md', 'Riemann hypothesis'),
    'riemann zeta function': ('math/黎曼ζ函数.md', 'Riemann zeta function'),
    'twin prime': ('math/孪生素数.md', 'twin prime'),
}
ALIAS = {'twin prime conjecture': ('math/孪生素数.md', '孪生素数猜想')}
ANCH = W.AnchorResolver(os.path.join(tmp, 'docs'), os.path.join(tmp, 'en'))


def run(text, rel='math/黎曼猜想.md', **kw):
    return W.rewrite_text(text, rel, os.path.join(tmp, 'docs'), MAP, ALIAS,
                          ANCH, **kw)


t, ch, sk = run('[黎曼ζ函数](https://en.wikipedia.org/wiki/Riemann_zeta_function)')
check('外链 → 站内', t, '[黎曼ζ函数](./黎曼ζ函数.md)')
check('显示文字不动', ch[0][1].startswith('[黎曼ζ函数]'), True)

t, _, _ = run('[后果](https://en.wikipedia.org/wiki/Riemann_hypothesis#Consequences)')
check('# 锚点换算', t, '[后果](./黎曼猜想.md#推论)')
t, _, _ = run('[格拉姆点](https://en.wikipedia.org/wiki/Riemann_hypothesis%23Gram_points)')
check('%23 锚点换算', t, '[格拉姆点](./黎曼猜想.md#格拉姆点)')
t, _, _ = run('[孪生素数猜想](https://en.wikipedia.org/wiki/twin_prime_conjecture)')
check('别名带锚点', t, '[孪生素数猜想](./孪生素数.md#孪生素数猜想)')

# 锚点换算不出来时默认保持外链：`#CITEREF*` 这类指向具体参考文献，降级更差
CIT = ('[(Odlyzko)](https://en.wikipedia.org/wiki/'
       'Riemann_hypothesis#CITEREFOdlyzko)')
t, ch, sk = run(CIT)
check('锚点换算不出 → 保持外链', t, CIT)
check('锚点换算不出 → 无改动', ch, [])
t, ch, _ = run(CIT, degrade_anchor=True)
check('--degrade-anchor 才降级', t, '[(Odlyzko)](./黎曼猜想.md)')

# 站内没有译好的版本 → 一个字都不动
EXT = '[戴德金ζ函数](https://en.wikipedia.org/wiki/Dedekind_zeta_function)'
t, ch, sk = run(EXT)
check('无站内版本 → 保持外链', t, EXT)
check('无站内版本 → 无改动', ch, [])
# 前缀相近但不是同一个词条，绝不能误改
NEAR = ('[有限域上曲线的黎曼猜想](https://en.wikipedia.org/wiki/'
        'Riemann_hypothesis_for_curves_over_finite_fields)')
t, ch, _ = run(NEAR)
check('相似标题不误改', t, NEAR)
# 脚注定义是「引用来源」，默认不动
FN = '[^3]: [https://en.wikipedia.org/wiki/Riemann_zeta_function](https://en.wikipedia.org/wiki/Riemann_zeta_function)'
t, ch, _ = run(FN)
check('脚注定义默认不动', t, FN)
t, ch, _ = run(FN, include_footnotes=True)
check('--include-footnotes 才动', ch != [], True)
# 同行多个链接
t, ch, _ = run('[A](https://en.wikipedia.org/wiki/Riemann_zeta_function) 和 '
               '[B](https://en.wikipedia.org/wiki/Siegel_zero)')
check('同行只改认得的', t, '[A](./黎曼ζ函数.md) 和 '
      '[B](https://en.wikipedia.org/wiki/Siegel_zero)')
# 幂等
t, _, _ = run('[黎曼ζ函数](https://en.wikipedia.org/wiki/Riemann_zeta_function)')
t2, ch2, _ = run(t)
check('幂等：第二遍无改动', ch2, [])
# 跨目录
t, _, _ = run('[x](https://en.wikipedia.org/wiki/twin_prime)', rel='ai/product/x.md')
check('跨目录相对路径', t, '[x](../../math/孪生素数.md)')

print('\n--- localize_text（流水线入口）---')
if os.path.isdir(DOCS):
    ZH = os.path.join(DOCS, 'math', '黎曼猜想.md')
    t = W.localize_text('[黎曼ζ函数](https://en.wikipedia.org/wiki/Riemann_zeta_function)',
                        ZH, quiet=True)
    check('流水线入口改写', t, '[黎曼ζ函数](./黎曼ζ函数.md)')
    t = W.localize_text('[X](https://en.wikipedia.org/wiki/Dedekind_zeta_function)',
                        ZH, quiet=True)
    check('流水线入口不误改', t,
          '[X](https://en.wikipedia.org/wiki/Dedekind_zeta_function)')
    # 不在 docs 树里的文件不猜相对路径（宁可不改）
    OUT = os.path.join(tempfile.gettempdir(), 'outside.md')
    t = W.localize_text('[A](https://en.wikipedia.org/wiki/Riemann_zeta_function)',
                        OUT, quiet=True)
    check('docs 树外不动', t,
          '[A](https://en.wikipedia.org/wiki/Riemann_zeta_function)')

    # 生成端必须挂着钩子，否则重新生成条目时外链会复发（脚注间距踩过同样的坑）
    for name in ('md2zh.py', 'wiki2md.py'):
        src = open(os.path.join(SCRIPTS, name), encoding='utf-8').read()
        check('%s 挂了改写钩子' % name,
              'wikilink_localize.localize_text(' in src, True)

print('\n失败 %d' % fail)
sys.exit(1 if fail else 0)
