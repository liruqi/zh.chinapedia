# 参考：条目生成 / 翻译流水线

> `.workbuddy-ai/memory/MEMORY.md` 的细节补充。做条目生成、翻译、脚注、译名时读它。

## 脚本分工

| 脚本 | 作用 |
|---|---|
| `wiki2md.py` | 非中文维基 wikitext → LLM 翻译 → `docs/{分类}/{条目}.md` |
| `wikitext2md.py` | **纯机械**转换，不调 LLM。用于 en.chinapedia，或翻译前的干净中间产物。`--report` 列未识别模板 |
| `md2zh.py` | 只做「英 → 目标语言」翻译（**现在支持 `--to zh\|th`**）。默认 `reasoning_effort=none`、`--jobs 4`、`--state` 断点续译（220 块 ≈ 10 min） |
| `md2footnotes.py` | 批量把外链改 GFM 脚注 |
| `notes2footnotes.py` | `［n］` 纯文本 → 真脚注 |
| `fix_footnote_spacing.py` | 相邻脚注标记间距（见下） |
| `wikiimg2r2.py` / `img2figure.py` | 搬图 / figure 化（见 `ref-site.md`） |
| `wikiterm.py` | 专有名词译名查询（见下） |
| `wikilink_localize.py` | 指向 `en.wikipedia` 的词条外链改走站内相对链接（见下） |
| `check_translation.py` | 整篇译文校验（行数 / `$$` / 脚注 / figure / 表格 / 应译行是否真译），`--lang zh\|th` |
| `test_fix_footnotes.py` / `test_wikilink_localize.py` | 回归用例（后者含对真 github-slugger 的差分测试） |
| `prebuild_check.mjs` | 发布前预检（`npm run check`），7 项 |

公式默认 KaTeX（`$…$` / `$$…$$`），`--no-katex` 退回行内代码；KaTeX 模式自动跑
`escape_dollar_in_urls()` + `fix_github_math()`。

## 新增一篇条目（三语言）的固定流程

以 Goldbach's conjecture（2026-09-23）为例：英文 → 中文 + 泰语。

1. **普查**：拉 wikitext，数图片 / `<ref>` / 章节（照 `scratch/_fetch.py` 写个小脚本）。
2. **英文稿**（机械，不调 LLM）：`wikitext2md.py <url> -o scratch/<x>_en.md`
3. **搬图**：`wikiimg2r2.py scratch/<x>_en.md --prefix docs/math`
   —— `--prefix` **必须显式给**：默认按 md 所在目录推导，稿子在 `scratch/` 下就会
   传成 `scratch/` 而不是 `docs/math/`。
4. **figure 化**：`img2figure.py scratch/<x>_en.md`
   —— **不要**带 `--from-wikitext`：那个模式只给**已有** `<figure>` 回填 maxWidth，
   不新建 figure，会报「(无改动)」让人以为图没问题。
5. **收尾**：删空的 `## References`、把脚注定义的续行并回一行（见上一节）。
6. **英文稿落地**：en 仓 `main`，文件名去掉撇号、下划线分词
   （`Goldbach's conjecture` → `goldbachs_conjecture.md`）。
7. **译中文**：
   `md2zh.py <en 稿> -o docs/math/<中文名>.md --to zh --title <中文名> \
   --base-url https://lms.thaiwen.com/v1 --state scratch/_x_zh.state.json`
8. **译泰语**：en 仓切到 `th` 分支，输出**同名**文件（便于 `git diff main..th`）。
9. **站内链接**：en 仓两次（`main` / `th`）各跑一次
   `wikilink_localize.py . --docs-root . --en-root <英文树> --aliases "" --also-self-titles`
   —— 泰语分支要先把 `main` `git archive` 到临时目录当 `--en-root`（否则拿泰语标题
   对泰语标题，锚点算不出来）；zh 仓用默认 `docs` 与默认别名表。
10. **校验**（顺序由快到慢）：`check_translation.py` → `prebuild_check.mjs` →
    `test_fix_footnotes.py` → `_mdxrun.mjs` → `_figcheck.mjs` → `_macroscan.mjs`。
11. **扫人名一致性**——**别省**：同一实体全篇只能有一种中文/泰文写法。
    本文实测：`Goldbach` 在中文稿里同时是「哥德巴赫 / 高尔达赫 / 高斯」，
    泰语稿里同时是 `ก็อลท์บัค / โกลด์แบค`。术语表被 API 封住时必然出现。
12. **提交**：zh 仓按「工具 / 内容」分 1~2 个 commit；en 仓 `main` 与 `th` 各一个，
    都推。收尾看 `git diff --stat main..th` 的**增删行数对称**（逐行对应，
    本文是 804/804）。

## 链接与脚注

- 维基链接**保持行内**；**其他外链改 GFM 脚注**（同一 URL 复用同一编号）。
  `md2footnotes.py` 幂等、保 CRLF，默认跳过本身就是链接清单的章节（`--all` 关掉）。
- 正文里 `<ref>` 残留的 `[[7]](url)` 也是外链，同样转脚注——往往比 `[文字](url)` 更多。
- 脚注标记后紧跟 `[` 或 `$` 要补空格，否则 `[^1]$x$` GitHub 不渲染。
- `remark-gfm` 不用配，`@docusaurus/mdx-loader` 默认启用。
- `<ref>` → `［n］` 是纯文本点不动。`notes2footnotes.py`：删 `## 注释` 节 → `［n］`→`[^n]`
  → 文末补定义（已有定义顺延编号），编号顺序与 wikitext `<ref>` 一致。
- **未被引用的脚注定义不渲染**：冗余一条无害，但整节来源列表全靠它撑着时会**整节消失**。
- 中文稿里字面 `[^n]`（翻译残留）要删：页面原样显示且不可点。

### 相邻脚注标记恰好一个空格（`[^16] [^17]`）

统一由 `scripts/fix_footnote_spacing.py` 负责：`fix_spacing(text)` 供其他脚本 import；
CLI 支持 `--dry-run` / `--check`（退出码 1，给 CI）。判据：
`(MARK)[ \t]*(?=MARK)` → 替换成 `MARK + ' '`。

- **必须用前瞻正则**：链式 `[^55][^56][^57]` 才能一次全拆开。成对正则
  （`\s*\[\^([^\]]+)\]\s*\[\^`）只拆前两个，三连会留下 `[^56][^57]`——
  `md2footnotes.py` 原来就这么写，已换成 `fix_spacing()`。
- 空白用 `[ \t]*` 不用 `\s*`：否则会把相邻两行（很可能是脚注定义）粘到一起。
  定义行是 `[^n]:`，`]` 后跟 `:`，天然不命中。
- **两个空格的来源**：`notes2footnotes.py` 把 `［1］［2］` 转 `[^n]` 时，前一个的
  post-space 和后一个的 pre-space 各补一次 → `[^1]  [^2]`。已在
  `body = MARK_RE.sub(repl, body)` 之后加 `fix_spacing(body)` 收敛。
- **生成端也要挂**，否则重新生成又出现：`wikitext2md.py` 第 9 步还原脚注标记
  （连续两个 `<ref>` → `[^1][^2]`）之后加 `fix_spacing(body)`；`md2footnotes.py` 换成正则。
- `prebuild_check.mjs` 已加检查项「脚注标记间距不规范」，改完必跑 `npm run check`。
- **判据一致性**由 `scratch/_fncross.mjs` 守着（`node scratch/_fncross.mjs docs`）：把预检的
  JS 正则和修复脚本的 Python 正则跑在同一份语料上，比对**处数**。两边必须一致——预检报错而
  修复脚本认为没问题，那个文件就永远修不好；反之则有漏网。已在 9729 篇（含 wow）+ en 3 篇验证。
- 报告里**「处数」和「行数」要分开说**：多数一处一行，但也有 `[^11][^12][^13]` 一行 2 处的。
  早先 `if hits > 5: print('另有 %d 处' % (hits-5))` 把处数当行数减，6 处 2 行会输出
  「另有 1 处」，读起来像还有第 7 处。

## wikitext2md.py 的收尾残留（每篇新条目都要看一眼）

机械转换出来的稿子有两类残留，`prebuild_check` 抓不到（不违反 MDX 硬约束，只是难看）：

1. **空的 `## References`**：wikitext 的 `==References==` 节里往往只有 `{{Reflist}}`
   （Notes 节同理，只有 `{{Notelist}}`），而 `<ref>` / `{{efn}}` 已被转成脚注定义、
   统一挂在 `## Notes` 下 → 这个标题下面必然是空的。**删掉标题**。
2. **脚注定义的续行没有缩进**：`<ref>` 内容里带换行时，第二行会原样落在 `[^n]:`
   定义行的下一行且不缩进 → GFM 认为定义到此结束，多出一段游离正文。
   仓库约定是**一条定义一行**（三篇基线稿的缩进续行数都是 0）→ 并回上一行，
   别加 4 空格缩进。

另有一个**已知且一致**的残留：`==External links==` 里 `*{{Commons category-inline}}`
会变成一行孤立的 `*`（三篇基线稿都有）→ 保持原样，别单篇"修好"。

## 词条外链改走站内链接（`scripts/wikilink_localize.py`）

站内已有译好的条目时，正文里的 `[黎曼ζ函数](https://en.wikipedia.org/wiki/Riemann_zeta_function)`
应改成 `[黎曼ζ函数](./黎曼ζ函数.md)`。**只换 URL，显示文字一个字不动。**

    python scripts/wikilink_localize.py docs --dry-run   # 只列出
    python scripts/wikilink_localize.py docs --check     # 有需要改的返回 1
    python scripts/wikilink_localize.py docs             # 就地改
    python scripts/wikilink_localize.py --map            # 打印映射表

已挂钩子：`md2zh.py` / `wiki2md.py` 写盘前调 `localize_text()`；
`prebuild_check.mjs` 第 7 项「外链本可走站内」（调 `--json`）拦手工加的。

### 映射表怎么来的（不猜、不联网）

只认条目**开头段**（第一个 `##` 之前）自己声明的英文名：

- `**词条名**（英语：X）` / `**词条名**（X）` —— 粗体挂着的，**全部**收下
  （西格尔零点.md 一条粗体链声明了 `Landau–Siegel zero` / `Siegel zero` / `exceptional zero`）；
- `（英语：X）` —— **只取第一处**；
- `…，简称 AIGC` —— 缩写也算。

**为什么只取第一处**：`（英语：X）` 在正文里会反复出现。黎曼ζ函数.md 有十几处
（`Leonhard Euler`、`polylogarithm`、`critical line theorem`…），全收就会把
`en.wikipedia.org/wiki/Leonhard_Euler` 指到本条目自己身上。

**开头段不能只取前 N 行**：黎曼ζ函数.md 开篇先是 `<div className="figure-row">` 图块，
声明落在第 **33** 行，卡 30 行整条映射就没了。现在的实现只按「第一个 `##`」截断。

`scripts/wikilink-aliases.json` 补重定向别名（值可带锚点）：
`"twin prime conjecture": "math/孪生素数.md#孪生素数猜想"`。

**撇号在归一化时被抹掉**（`_APOSTROPHE_RE`）：维基标题 `Goldbach's_conjecture`
对应文件名 `goldbachs_conjecture.md`（文件名通常不写撇号），不抹掉就永远对不上。
但**重定向写法仍要手补别名**——维基 `Goldbach_conjecture` 去掉撇号后是
`goldbach conjecture`，与条目自己声明的 `Goldbach's conjecture` 不同名，
自动推导看不到它。

**扫外部目录时不能带本仓别名表**：`prebuild_check.mjs` 第 7 项现在会判断——
根目录不是本仓 `docs/` 时，改用该目录自身当 `--docs-root` 且 `--aliases ""`。
否则本仓别名表里的 zh 路径会被套到别的仓上，报出「外链本可走站内」的假阳性。
手动跑的时候同样要带：`--docs-root . --en-root . --aliases "" --also-self-titles`。

### 锚点换算

`…/wiki/Riemann_hypothesis#Consequences` → `./黎曼猜想.md#推论`。靠**中英两版标题序列对齐**：
`en.chinapedia/docs/<英文名>.md` 存在时逐条比对，**从第一条层级对不上的地方停止信任**
（黎曼猜想.md 尾部 EN 有 `## Notes` 而中文版没有，正是靠这条避免错位）。

三个坑：

1. **中英文件名不一样**（`riemann_hypothesis.md` vs `黎曼猜想.md`）→ 不能按路径配对，
   要用映射里记着的英文名去拼英文镜像路径（大小写也试一遍）。
2. **维基锚点有两种写法**：`#Consequences`（真 fragment）和 `%23Consequences`
   （躺在 path 里、`urlsplit` 的 fragment 是空的）。数据里**后者更多**，
   所以先把 path 解码再切 `#`。
3. **维基用下划线代替空格**，github-slugger 产出连字符 → `anchor_candidates()` 两种都试。

**换算不出来时默认保持外链**，不降级：`#CITEREFOdlyzko` 这类指向某条具体参考文献，
改成条目页首反而更差（英文/泰语镜像里各 9/8 处）。要降级得 `--degrade-anchor`。

脚注定义行（`[^3]: [https://…](…)`）是**引用来源**，默认不动——改成站内链接等于「引用自己」。

### 要跟第三方库逐字一致时，别近似（`slugify` 的教训）

`slugify` 原用 `[^\w\s-]` 近似 github-slugger。中文没事，**泰语全错**：
元音/声调符号是 Mn 组合字符、`\w` 不匹配 → 被当标点删掉，
`#สมการเชิงฟังก์ชันของรีมันน` 变成 `#สมการเชงฟงกชนของรมนน`，
链接跳不到标题而且**肉眼完全看不出**。

真规则在 `node_modules/github-slugger/index.js`（v1.5.0）：

    string.toLowerCase().replace(regex, '').replace(/ /g, '-')

`regex` 是 GitHub 生成的一张大字符类表，不能手抄。等价判据：**按 Unicode 类别删 P/S/C，
但保留 `-` 和 `_`**（实测 `_x_`→`_x_`、`--a--`→`--a--`），外加 **不 trim**（`' x '`→`-x-`）、
**不合并空白**（`a  b`→`a--b`）、**只有普通空格 U+0020** 换 `-`。
还要复现同页**重复标题的 `-1`/`-2` 后缀**（Docusaurus 每页一个 slugger 实例）→ `slug_headings()`。

**验证**：拿真 `github-slugger` 对仓库全部真实标题 + 刁钻样本做**差分测试**，
303 条 0 条不一致；该用例已进 `test_wikilink_localize.py`（node 不在就跳过）。

### 用到别的仓时

`chinapedia/math`（`en.chinapedia/docs/math`，英文 `main` + 泰语 `th`）：

    python <zh>/scripts/wikilink_localize.py . --docs-root . --en-root . \
        --aliases "" --also-self-titles

- `--also-self-titles`：文件名即英文名（该仓条目开头没有 `（英语：）`）；
- `--en-root .`：英文稿自身对齐（泰语分支要先把 `main` `git archive` 到临时目录再指过去）；
- `--aliases ""`：别名表里是 zh 的路径，别带过去。

### 未解：文件被外部还原过一次

2026-09-23，`docs/math/孪生素数.md` 改写后（17:59:02）于 **18:05:41** 被还原成 HEAD 版本，
其它三个同批改的文件没动。查过：无 prebuild 钩子、无 stash、reflog 无变化、
`.git/hooks` 只有 sample。重新改写并提交后未再复现。
→ **若再出现，优先怀疑编辑器 / 同步工具（OneDrive 之类）**，别先怀疑脚本。

## 中文条目文风

- 开头：`**词条名**（英语：English name），也称为**别名1**、**别名2**，是指……`
- 不直译只在英文语境成立的句子；长从句拆散重排，不留 "whose … and whose …" 连环定语。
- 正文里的外文原文引文（德/法/拉丁）一律删，只留中文译文；参考文献里的外文标题/刊名保留不译。

## 自托管 Qwen（`https://lms.thaiwen.com/v1`，LM Studio）必开两个设置

模型 `qwen/qwen3.5-9b` 强制思维链（一句话想 150s+ 且零输出）。两条一起加才有救
（`wiki2md.llm_chat` 已内置）：

1. **`stream: true`** —— 前面挂 Cloudflare，源站 ~100s 不出首字节返回 524；流式 2s 就吐 SSE。
2. **`reasoning_effort: "none"`** —— 唯一能关思维链的参数（2.0s 出首字，13.2s 出全文）。

**无效（都试过）**：`chat_template_kwargs:{enable_thinking:false}`、`thinking:{type:"disabled"}`、
`reasoning:{enabled:false}`、顶层 `enable_thinking`、`/no_think`、`reasoning_effort:"minimal"/"low"`。
另：**必须带浏览器 UA**（urllib 默认 UA 被 Cloudflare 403）；**并发 3–4 路快 3 倍**。

## md2zh.py：LLM 翻译的四个必防错误

1. URL 里 `_` 被改成空格 → 送译前 URL 换 `§U0§` 占位符，译完还原。
2. 模型把行内链接改写成脚注还自己编号（撞号）→ 脚注标记换 `§F3§`，译完 `fix_footnotes()`
   逐行对账，译文里凭空出现的 `[^n]:` 整行丢。占位符用 `§…§` **不要** `\x01`（传输中被吃掉，
   模型会写成 `[^F2^]`）。
3. 改标题层级 → 以原文 `#` 个数为准强行纠正。
4. **最严重：标题单独成块 → 整节内容全是编的。** 空行被当 verbatim 块，标题行自成 chunk，
   模型会"补全" 27–57 行虚构内容（还自带编造的 `[^1]: 此处为脚注占位符…`）。对策：单行标题走
   `HEADING_SYSTEM` 只取一行；**输出行数必须等于输入行数**（不等就重试，最终逐行兜底）；
   缓存命中同样要求行数**严格相等**（写 `>=` 会把幻觉当有效缓存）；收尾丢弃非逐字复制的
   `[^n]:` 定义行，多出来的行里 `[^n]:` / `#` 开头判为幻觉。
   → **「输入行数 vs 输出行数」是最有效的幻觉探测器**，比看长度比准得多。

`_chat_stream` 必须有总时限：`urlopen(timeout=)` 只管单次 recv，心跳块能把连接挂 7.5h
（实测过）→ `deadline = time.time() + timeout`。

## 多语言化（`--to zh|th`）

`md2zh.py` / `wikiterm.py` 都有 `LANGS` 注册表，按语言取 prompt / 术语表 / 分支行为：

- `md2zh.py`：`LANGS[lang]` = `label / system / title_system / heading_system / ask_prefix /
  terms_file / people_file / terms_label / people_filter / default_title`；
  `main()` 的 `--to {zh,th}`；`--terms` 默认 `None` → 回落 `L["terms_file"]`。
- `wikiterm.py`：`--lang {zh,th}`；zh 走简繁转换 + 人名白名单，th 都不走。
- **改完必须验证 zh 路径零行为变化**：`ast.parse` + `ast.literal_eval` 逐字对比
  `git show HEAD:scripts/md2zh.py` 里的 `SYSTEM` / `TITLE_SYSTEM` / `HEADING_SYSTEM`
  （注意提取器要同时支持 `"""…"""` 和普通字符串，否则会误报"已改动"）。

**泰语特有**：没有音译人名的间隔号「·」（`people_filter` 必须关掉）；无简繁变体转换；
泰语词间不空格，但**英文单词 / `$…$` 两侧原有空格必须保留**，否则 Markdown 行内元素粘连。
泰语无通行译法的术语**保留英文原文**（实测模型会把 `analytic continuation` 留英文，正确）。

### 实测踩到的坑（泰语首译时暴露）

1. **`state` 缓存不含提示词哈希**，key 只是 chunk 的起始块号 → **改了 prompt 必须删
   `--state` 文件**，否则原样复用旧译文（改了等于没改）。同理，某个 chunk 译坏了也要
   从 state 里删掉那一项再重跑，否则坏译文会被反复复用。
2. **整行 HTML/JSX 标签会送给模型**：单行 `<figcaption>` 被"解释"成
   `**<figcaption>** (caption) คือข้อความที่ใช้อธิบายภาพหรือตาราง` 插进正文。
   `split_blocks` 已加规则：整行匹配 `</?[A-Za-z][^<>]*/?>` → verbatim。
3. **`fix_footnotes` 只认数字标签**，模型凭空补的字面 `[^n]` 漏网（页面上原样显示、
   点不动）。现在标签放宽为任意字符，原文里查不到就删；全站 9729 篇 + en 仓实测
   非数字标签 0 处，所以删是安全的。**反向也要管**：模型整行丢掉标记时那条定义就没人
   引用（未被引用的定义不渲染，整节可能消失）→ 按原文顺序补到行尾。
4. **术语表在链接文字上不生效**：`[complex conjugate](url)` 照留英文，哪怕提示词里
   给了 `complex conjugate → สังยุค`。9B 模型的指令遵循不保证 → 加
   `enforce_terms_in_links()`：显示文字与术语表条目**完全相等**时确定性替换
   （只做整体相等，不做子串；URL 带括号的跳过）。
5. **单行 chunk 的截断回复能骗过行数守卫**：`out.count("\n")+1 == n` 对 1 行输入**恒真**。
   实测一行 124 字符的公式只回来 66 字符（`… li}(x^\`），行数照样"对"。
   症状是 `$` 不配对 → `dollars_balanced()` 逐行比 `$` 奇偶，作为第二个接受条件；
   逐行兜底两次仍不配对就退回原文（半截公式比一句英文糟得多）。
6. **纯公式行别送模型**（`is_math_only()`：抠掉 `$…$` 后没有正文的行 → verbatim）。
7. 模型还会：先**回显英文原文**再给译文（`strip_source_echo()`）、把 `[文字](URL)`
   写成 `文字[URL]` 让链接失效（`repair_bracket_urls()`）、**丢掉标题里的 `\<` 转义**
   （`escape_heading_angles()` —— 标题裸尖括号会让**整站构建失败**）。

### 收尾必跑的校验（由快到慢，前三步必跑）

1. `python scripts/check_translation.py <原稿目录> <译稿目录> --lang th`
   —— 整篇逐项对账（行数 / `$$` / `$` 逐行配对 / 脚注标记与定义 / figure 与
   figcaption / 表格行数 / 相邻脚注间距 / 残留 / 应译行是否真译）
2. `node scripts/prebuild_check.mjs <译稿目录>` —— MDX 裸 `{}` 与标题裸尖括号、
   KaTeX 未定义宏、脚注引用与定义对得上、裸 URL
3. `python scripts/test_fix_footnotes.py` —— 39 条回归用例
4. `node scratch/_mdxrun.mjs <file>` —— **真求值**编译产物，抓 `ReferenceError`
   （静态检查过不了这一关：`{expr}` 只在运行时炸）
5. `node scratch/_figcheck.mjs <file>` —— 真 MDX 树里数 figure / figcaption / img，
   应与原稿相等（纯 remark 管线会把裸 HTML 丢掉，得到假阴性）
6. `node scratch/_macroscan.mjs <目录>` —— 公式总数与 KaTeX 报错数（应为 0）

泰语三篇的实测结果：`_mdxrun` 全 OK、figure 0/6/6 与原稿一致、
`_macroscan` 812 条公式 0 报错。

### 泰语术语表要人工收敛

`wikiterm.py --lang th` 的 Wikidata 兜底会把**宽泛条目**当成译名（泰语维基数学条目极少）：
`critical line theorem → สมมติฐานของรีมัน`（那是"黎曼猜想"）、`imaginary part → จำนวนเชิงซ้อน`
（那是"复数"）、`partial sum → อนุกรม`（那是"级数"）。直接注进提示词会误导模型。
→ `scripts/curate_th_terms.py` 剔掉这类映射 + 去掉译名里的消歧括号 + 小写去重，
   111 条收敛到 91 条；原始表另存 `scripts/wiki-th-terms.raw.json` 备查。

### 译稿核对：`scripts/check_translation.py`

`md2zh` 的行数守卫是按 chunk 比的，整篇要另外核：行数 / `$$` 数 / 脚注标记与定义数 /
figure 与 figcaption 标签数 / 表格行数必须与原稿相等，外加相邻脚注间距、残留
（`<references`、`[[`、`{{`、`<ref`）、以及"应译行里到底有没有目标语言文字"。
`--lang {th,zh}` 切换判据字符集。

## 人工翻译长条目：§ 标记两阶段流水线

1. `scratch/prep_*.py` 把 wikitext 压成中间表示，链接/公式/引用/脚注换成标记：
   `§L{Target|显示}§`、`§M{行内公式}§`、`§D{块公式}§`、`§H{作者|年}§`、`§S{作者|年|页}§`、
   `§REF{n}§`、`§X{OEIS id}§`。人工只译纯散文。
2. `scratch/build_*.py` 展开回 Markdown，复用 `wiki2md.escape_dollar_in_urls()` + `fix_github_math()`。

复用过的坑：

- **wikitext 标题层级**：`== X ==` → `## X`（`"#" * len(m.group(1))`，**不要 +1**）。
- **`{{harvs}}` 取参**：先剥外层 `{{ }}`，再**只在深度 0** 按 `|` 切分；深度只由 `{`/`}` 计数
  （早期把 `|` 也算进深度 → 引用全渲染成空）。
- 列表用 `1.` 不用 `#`（行首 `#` 会被当 H1）。
- 中文引号：ASCII `"` 前后是中文时批量换 `“”`。
- `（英语：X）` 前先占位保护再补中英文空格，否则 CJK 空格规则会插进括号里。
- 链接显示文字不要以 `$…$` 开头，改成 `§L{Target|L 函数}§`。

## 专有名词译名：查中文维基条目名，不要猜

权威译名 = 中文维基条目名。**查不到就保留英文，绝不生造**
（`Tikao Tatsuzawa` 猜"立川"是错的，已回退）。

```
python scripts/wikiterm.py "Riemann xi function"
python scripts/wikiterm.py --scan docs/math/ --glossary   # 抽 .md 里所有维基链接
python scripts/wikiterm.py --no-wikidata                  # 严格模式
python scripts/wikiterm.py --fix-cache                    # 去重 + 重做简繁转换
python scripts/wikiterm.py --verify-people                # 回查人名白名单
python scripts/wikiterm.py --lang th --scan <dir>         # 泰语（en.wikipedia → lllang=th）
```

`md2zh.py --terms` 按 chunk 注入命中词条（标题/小节/正文三条路径，匹配做了归一化）。

**三级兜底，质量递减**：langlinks（可靠）> Wikidata 标签（机翻多：
`Andrew Granville → 安德鲁·关维`）> 没有。

### 人名白名单

中文间隔号「·」是音译人名标志，术语名不会带。原先 `load_terms()` 把带「·」的**全丢**，
连权威译名一起丢（正文留下没译的 `Helmut Hasse`，中文维基有条目「赫尔穆特·哈斯」）。
现在 `--verify-people` 把带「·」的回查 langlinks，确有条目的写进
`scripts/wiki-zh-terms-people.json`（56 条保留 32 条），`md2zh.load_terms()` 只放行白名单。
**新增人名条目后记得重跑 `--verify-people`。**

### 坑

- `langlinks()` / `wikidata_*()` 早期把 `normalized`+`redirects` 做成**反查表**（最终标题 →
  请求名），两个请求名跳到同一页面时互相覆盖（`Carl Siegel` / `Carl Ludwig Siegel` 都指向同一
  en 条目），其中一个永远查不到 → 误判「没有条目」。必须**正向映射**（请求名 → 最终标题）再沿链展开。
- **简繁转换用 `zh.wikipedia.org` 的 `action=parse&variant=zh-cn`，必须分批（40 条）**，
  一次几百行整批退回原文。`converttitles` 靠不住。
- **维基 API 会 429**：限速 ≥1.2s/次 + 按 `Retry-After` 退避。
- **维基 API 还会 403 封 IP**（`Please respect our robot policy`）。2026-09-23 一次
  `wikiterm.py --scan` 要解析 515 个标题（缓存只命中 297）后，**en / zh / wikidata /
  REST 全部主机**都开始 403，持续 1 小时以上未恢复。后果不是"查不到译名"这么轻：
  人名白名单缺条目后，模型会**自己编**——`Christian Goldbach` 被译成「高尔达赫」，
  而 `Goldbach` 单独出现时被译成「**高斯**」（英文原稿里 Gauss 出现 0 次），
  同一篇里同一个人三种写法。
  → 扫描前先把标题量压下来（分批、只扫新条目）；被封了就把该条目的译名核对
  往后放，别指望模型自己扛住。
  → 译完**必须扫人名一致性**：同一实体的中文写法在同一篇里只应有一种。
- **别在 `npm run build` 期间查**：网络同时跑构建必 RST（WinError 10054）。
- 缓存键**按小写去重**（维基标题大小写等价）；变体里留"句子式大小写"那个。
- 改完用中英混排正则扫残留：`[\u4e00-\u9fff]\s?([A-Za-z][A-Za-z\-']{2,})\s?[\u4e00-\u9fff]`
- `wikiterm.py` 里「查不到」的占位文案要跟着 `--lang` 走（别硬编码「（无中文条目）」）。
