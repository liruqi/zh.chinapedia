# zh.chinapedia 项目约定

## 条目生成

- `scripts/wiki2md.py`：抓非中文维基 wikitext → LLM 翻译 → `docs/{分类}/{条目名}.md`。
- `scripts/wikitext2md.py`：**纯机械** wikitext → Markdown，不翻译、不调 LLM。用于英文镜像站
  `D:\SRC\Z\en.chinapedia\`，或作翻译前的干净中间产物。支持表格/图库/脚注/60+ 模板，`--report` 列未识别模板。
- `scripts/md2zh.py`：只做英→中翻译（不碰 wikitext）。切块后公式块/脚注定义/图片/表格原样照抄。
  默认 `reasoning_effort=none`、`--jobs 4`、`--state` 断点续译，Riemann zeta（220 块）约 10 分钟。
- 公式风格**默认 KaTeX**（`$…$` / `$$…$$`）；`--no-katex` 才退回行内代码。KaTeX 模式自动做
  GitHub 兼容后处理 `escape_dollar_in_urls()` + `fix_github_math()`。

## 链接与脚注

- **维基链接保持行内**；**其他外链改成 GFM 脚注**（正文 `[^1] [^2]`，文末 `[^n]: [https://host](url)`，
  同一 URL 复用同一编号）。批量用 `scripts/md2footnotes.py`（幂等、保 CRLF；默认跳过"注释/参考文献
  /外部链接"这类本身是链接清单的章节，`--all` 关掉）。
- 正文里 `<ref>` 残留的 `[[7]](url)` 也是外链，同样转脚注——这类往往比 `[文字](url)` 更多。
- 脚注标记后紧跟 `[` 或 `$` 要补空格，否则 `[^1]$x$` GitHub 不渲染。
- `remark-gfm` 不用配：`@docusaurus/mdx-loader` 默认启用。
- **`<ref>` → `［n］` 是纯文本点不动**。wiki2md/人工翻译会把 `<ref>` 整理成文末 `## 注释` 编号列表，
  正文留全角 `［1］`。用 `scripts/notes2footnotes.py` 接成真脚注：删 `## 注释` 整节 → `［n］`→`[^n]`
  → 文末补定义（已有定义整体顺延编号）。编号顺序与 wikitext `<ref>` 一致。
- **未被引用的脚注定义不渲染**。冗余一条无害；但若整节来源列表全靠它撑着（grok.md 的 `## 参考来源`），
  **整节会在页面上凭空消失**。`npm run check` 能扫出。
- 中文稿里出现字面 `[^n]`（LLM 翻译残留）要删：页面上原样显示且不可点。

## 中文条目文风

- 开头：`**词条名**（英语：English name），也称为**别名1**、**别名2**，是指……`。
- 不直译只在英文语境成立的句子；**长从句拆散重排**，不留 "whose … and whose …" 连环定语。
- **正文里的外文原文引文（德/法/拉丁）一律删，只留中文译文**；参考文献里的外文标题/刊名保留不译。

## 站点栈与坑

- Docusaurus 3.10 + MDX 3，配 `remark-math` + `rehype-katex`。
- remark-math 6 下**一行式 `$$x$$` 会被解析成 inlineMath**（不居中）。独立公式必须三行：
  `$$` 独占一行 → 公式 → `$$` 独占一行。（肉眼和 MDX 编译都不报错，只有看 AST 才发现。）
- KaTeX CSS 由 `docusaurus.config.js` 的 `stylesheets` 从 jsDelivr 引入，**版本必须与
  rehype-katex 实际用的 katex 一致**（以 package-lock 里 `node_modules/katex` 为准，当前 0.16.47）。
  换版本时 SRI `integrity` 要重算：`urllib` 取文件 → `hashlib.sha384` → base64。
- MDX 硬性约束：正文不得出现未转义的 `< >` `{}`；禁止 `<https://…>` 自动链接（`fix_autolinks` 转 `[原文](url)`）。
- **最大的坑：`{expr}` 在 `compile()` 阶段不报错，只在页面运行时炸**。正文残留未包进 `$…$` 的 LaTeX
  （如 `\operatorname{li}`）→ 页面 `ReferenceError: li is not defined` + 白屏。
  → 「MDX COMPILE OK」**不能**作为通过标准，必须运行时 eval。`wiki2md.escape_mdx_braces()` 是兜底。

### 标题里的裸 `<` / `>` 会让整站构建失败

真凶是「标题内的数学公式」。`toHeadingHTMLValue()` 只显式处理 text/heading/inlineCode/emphasis 等，
**`inlineMath` 落到 `default: return toString(node)`，不转义**；TOC 再走 `dangerouslySetInnerHTML`
→ `html-minifier-terser` Parse Error → **整站构建失败**。实测（`scratch/_tocangle.mjs`）：

| 标题 | TOC 输出 | 危险 |
|---|---|---|
| `## …*D* \< 0` | `… <em>D</em> &lt; 0` | 否 |
| `## 裸尖括号 D < 0` | `裸尖括号 D &lt; 0` | 否 |
| `## 公式 $D < 0$` | `公式 D < 0` | **是** |
| `## 已转义 \< 与 \>` | `已转义 &lt; 与 &gt;` | 否 |

修法：写成 `$D \lt 0$` / `$x \gt 0$`。`prebuild_check.mjs` 放行 `\<` `\>`，裸 `<>` 继续报。

## 自托管 Qwen（`https://lms.thaiwen.com/v1`，LM Studio）必开两个设置

模型 `qwen/qwen3.5-9b` 强制思维链，一句话要想 150s+ 且零输出。两条一起加才有救（`wiki2md.llm_chat` 已内置）：

1. **`stream: true`** —— 前面挂 Cloudflare，源站 ~100s 不出首字节返回 **524**。流式 2s 就吐 SSE，跑多久都不超时。
2. **`reasoning_effort: "none"`** —— 唯一能关掉思维链的参数。实测 2.0s 出首字、13.2s 出全文。

**无效（都试过）**：`chat_template_kwargs:{enable_thinking:false}`（静默忽略）、`thinking:{type:"disabled"}`、
`reasoning:{enabled:false}`、顶层 `enable_thinking`（反而顶到 1255 token）、`/no_think`（卡死 524）、
`<arg_key:6124c78e>`、`reasoning_effort:"minimal"/"low"`。只有 `"none"` 是开关。

另两个坑：**必须带浏览器 UA**（urllib 默认 UA 被 Cloudflare 403）；**并发 3–4 路快 3 倍**。

## md2zh.py：LLM 翻译的四个必防错误

1. URL 里 `_` 被改成空格 → 送译前把 URL 换成 `§U0§` 占位符，译完还原。
2. 把行内链接改写成脚注还自己编号（撞号）→ 脚注标记换成 `§F3§`；译完 `fix_footnotes()` 逐行对账；
   译文里凭空出现的 `[^n]:` 定义整行丢。占位符用 `§…§` **不要**用 `\x01`（传输中被吃掉，模型会写成 `[^F2^]`）。
3. 改标题层级 → 以原文 `#` 个数为准强行纠正。
4. **最严重：标题单独成块 → 整节内容全是编的。** 空行被当 verbatim 块，所以标题行自己就是一个 chunk，
   模型会"补全"出 27–57 行虚构内容，还自带编造的 `[^1]: 此处为脚注占位符…`。对策：单行为标题走
   `HEADING_SYSTEM` 只取一行；**输出行数必须等于输入行数**（不等就重试，最终逐行兜底）；
   缓存命中也要求行数严格相等（写 `>=` 会把幻觉当有效缓存）；收尾：`[^n]:` 定义行非逐字复制的一律丢，
   多出来的行里 `[^n]:` / `#` 开头判为幻觉。
   → **「输入行数 vs 输出行数」是最有效的幻觉探测器**，比看长度比准得多。

`_chat_stream` 必须有总时限：`urlopen(timeout=)` 只管单次 recv，心跳块能把连接挂几小时（实测 7.5h）。
已加 `deadline = time.time() + timeout`。

## 图片：必须搬到 Cloudflare R2（chped 桶）

`[[File:X|thumb|caption]]` 机械转换出来是 `…/wiki/File:X`，那是**文件描述页**（HTML）必裂图；
thumb.wikimedia.org 还有反盗链。`scripts/wikiimg2r2.py` 一键做完：Commons API 查真实地址 → 下载 →
AWS SigV4 PUT → 改写成 `https://pub-275e30003c354ac0862cc9839e0f952a.r2.dev/docs/math/X.png`。

- 凭证 `scripts/r2.local.json`（**gitignore 不提交**）；prod 用环境变量
  `R2_ENDPOINT / R2_BUCKET / R2_PUBLIC_BASE / R2_ACCESS_KEY / R2_SECRET_KEY`。
- 脚本**不依赖 boto3**，自己实现 SigV4（装 boto3 要十几分钟）。映射缓存 `scripts/wikiimg-map.json` 会提交。
- 坑：主机名 `commons.wikimedia.org`；**SVG/PDF 必须取 `thumburl`**（渲染好的 PNG），
  **GIF 反过来取原图**（缩略图会变静止帧）；R2 路径风格 + region `auto` + canonical URI 不做归一化；
  网络会随机 RST，上传/校验都要重试，**校验用 GET 比字节数，别信单次 HEAD**。
- `wikitext2md.py` 的 `file_url()` 已改成 `Special:FilePath/<name>?width=1000`，没跑 R2 也能显示。

搬完还要走 **`scripts/img2figure.py`**：图注只躺在 alt 里看不见，且连续图片会被合并进同一段落。
脚本改写成 `<figure>` + `<img>` + `<figcaption>`。**MDX 要求 JSX 块的子内容用空行隔开才会当 markdown
解析**，所以 figure/figcaption 内侧留空行；alt 用 LaTeX→Unicode 降级后的纯文本。

## 插图尺寸：R2 原图经常超高，必须限高

维基把图放**右侧窄栏**（260/210px），搬进整栏（~750px）就爆。实测 `Riemann-Zeta-Detail.png` 是
**1280×2959**，铺开 1734px 高，一张图吃掉两屏。查尺寸不用下全图：PNG 读 IHDR `d[16:24]`；
JPEG 扫 `FFC0/FFC1/FFC2` 段（偏移 +5 是大端 `height,width`）。带浏览器 UA。

`src/css/custom.css` 三个约定：

- `.markdown figure img { max-height: 420px; width: auto }` —— 全局兜底，替换元素限高时宽度按原比例收缩不变形。
- `.figure-row` —— 多图并排（flex+wrap，`> figure { flex:1 1 240px; max-width:340px }`，行内限高 380px），
  窄屏自动回退上下排列。用法：把几个 `<figure>` 包进 `<div className="figure-row">`。
- `figure className="figure-tall"` —— 逃生口，限高放宽到 620px。竖版大图（论文首页扫描件 500×833）用。

**wikitext 里的显示宽度要保留**：`[[File:X|thumb|250px|…]]` 的 `250px`（以及 `upright=1.4`
按 220px 基准折算）以前在转换时被丢掉，图片按整栏铺开。现在：

- `wikitext2md.py` 的 `extract_display_width()` 把宽度编码成 markdown 图片 title `"w250"`；
  `FILE_OPTION_RE` 也要能匹配 `NxMpx`，否则尺寸参数会漏进图注。
- `img2figure.py` 解析 `wN` 并写成 `<figure style={{"maxWidth": "Npx"}}>`。
  **MDX 里 `style="字符串"` 会在 SSR 报 `The style prop expects a mapping…`，必须传对象。**
- 已经转好的文章用 `img2figure.py --from-wikitext <wikitext 文件或 wikipedia URL>`
  回填（幂等，已有 `style=` 的跳过）。它靠 `wikiimg-map.json` 把 R2 URL 反查回 File 名。
- **裸 `thumb` / 裸 `upright` 不加约束**：折算成 220px 反而比现在更小，交给 max-height 兜底。
- 取 `[[File:…]]` 必须用**括号配对扫描**，不能用 `\|[^\[\]]*` 这类正则：图注里常带
  `[[domain coloring]]`、`{{cite web|url=…}}`，正则会被内部的 `[` 卡住，整条都匹配不上
  （实测漏掉 `Cplot zeta.svg` 的 250px）。

容器的类名是 `theme-doc-markdown markdown`（`grep 'class="markdown"'` 会漏，要 grep 全串）。

## 翻译带图的条目：先搬图再翻译

`wiki2md.py` 翻译阶段会把 `[[File:…]]` **连同图注一起丢掉**（中文黎曼猜想.md 因此 0 图，英文源 6 张）。
正确顺序：`wikitext2md` → `wikiimg2r2.py` → `img2figure.py` → 再翻译。
译完 `grep -c '^<figure>'` 对一遍中英两版，数量必须相等。中英词条的**脚注编号一致**。

## KaTeX 缺 MediaWiki 扩展的宏

维基大量用 `\C \R \N \Z \Q \F \sgn` —— 这是 **MediaWiki 自己 MathJax 配置里扩展的宏**，KaTeX 不认，
渲染成红色 parse error（GitHub 的 MathJax 也不认）。两处补：`docusaurus.config.js` 给 rehype-katex 配
`macros`（兜底新导入条目），现存 .md 换成 `\mathbb{C}` 这类标准写法。
排查用 `scratch/_macroscan.mjs`，**要按 display/inline 分别传 `displayMode`**，否则 `\begin{align}` 误报。

**KaTeX 报错没有 `katex-error` 类**：不抛异常，只把源码原样渲成红色 `color:#cc0000`。
基于 hast 的校验要认这个颜色；`_macroscan.mjs` 用 `throwOnError: true` 直接试渲染。

## 专有名词译名：查中文维基条目名，不要猜

权威译名 = 中文维基条目名。用 `scripts/wikiterm.py` 抓（en.wikipedia `prop=langlinks&lllang=zh`
→ `scripts/wiki-zh-terms.json`，已提交）：

    python scripts/wikiterm.py "Riemann xi function"
    python scripts/wikiterm.py --scan docs/math/ --glossary   # 抽 .md 里所有维基链接
    python scripts/wikiterm.py --no-wikidata                  # 严格模式
    python scripts/wikiterm.py --fix-cache                    # 去重 + 重做简繁转换

`md2zh.py --terms` 按 chunk 注入命中词条（标题/小节/正文三条路径），匹配做了归一化。

**三级兜底，质量递减**：langlinks（可靠）> Wikidata 中文标签（机翻多：`Andrew Granville → 安德鲁·关维`）
> 没有。**查不到就保留英文，绝不生造**（踩过 `Tikao Tatsuzawa` 猜"立川"是错的，已回退）。
**人名走白名单，不再一刀切过滤**：中文间隔号「·」是音译人名标志，术语名不会带。
原先 `load_terms()` 把带「·」的条目**全丢**，理由是 Wikidata 兜底的人名质量差
（`Andrew Granville → 安德鲁·关维`）。但 langlinks 来源的人名是权威译名，一起丢会让
正文留下没译的 `Helmut Hasse`（中文维基有条目「赫尔穆特·哈斯」）。

现在：`python scripts/wikiterm.py --verify-people` 把缓存里带「·」的条目**回查一遍**
en.wikipedia 的 langlinks，确有中文条目的写进 `scripts/wiki-zh-terms-people.json`；
`md2zh.load_terms()` 只放行这份白名单里的人名。实测 56 条保留 32 条。
新增人名条目后记得重跑 `--verify-people`。

坑：`langlinks()` / `wikidata_zh()` 早期把 `normalized`+`redirects` 做成了**反查表**
（最终标题 → 请求名），**两个请求名跳到同一页面时会互相覆盖**
（`Carl Siegel` 与 `Carl Ludwig Siegel` 都指向同一 en 条目），其中一个就永远查不到
langlink，被误判成「没有中文条目」。必须**正向映射**（请求名 → 最终标题）再沿链展开。

坑：
- **简繁转换用 `zh.wikipedia.org` 的 `action=parse&variant=zh-cn`，必须分批（40 条）**，
  一次几百行会整批退回原文。`converttitles` 靠不住。
- **维基 API 会 429**：限速 ≥1.2s/次 + 按 `Retry-After` 退避。
- **别在 `npm run build` 期间查**：网络同时跑构建必 RST（WinError 10054）。
- 缓存键**按小写去重**（维基标题大小写等价）；变体里留"句子式大小写"那个。
- 改完用中英混排正则扫残留：`[\u4e00-\u9fff]\s?([A-Za-z][A-Za-z\-']{2,})\s?[\u4e00-\u9fff]`

## 人工翻译长条目：§ 标记两阶段流水线

1. `scratch/prep_*.py` 把 wikitext 压成中间表示，链接/公式/引用/脚注换成标记：
   `§L{Target|显示}§`、`§M{行内公式}§`、`§D{块公式}§`、`§H{作者|年}§`、`§S{作者|年|页}§`、`§REF{n}§`、`§X{OEIS id}§`。
   人工只译纯散文。
2. `scratch/build_*.py` 展开回 Markdown，复用 `wiki2md.escape_dollar_in_urls()` + `fix_github_math()`。

复用过的坑：
- **wikitext 标题层级**：`== X ==` → `## X`（`"#" * len(m.group(1))`，**不要 +1**）。
- **`{{harvs}}` 取参**：先剥外层 `{{ }}`，再**只在深度 0** 按 `|` 切分；深度只由 `{`/`}` 计数
  （早期把 `|` 也算进深度 → 引用全渲染成空）。
- 列表用 `1.` 不用 `#`（行首 `#` 会被当 H1）。
- 中文引号：ASCII `"` 前后是中文时批量换成 `“”`。
- `（英语：X）` 前先占位保护再补中英文空格，否则 CJK 空格规则会插进括号里。
- 链接显示文字不要以 `$…$` 开头，改成 `§L{Target|L 函数}§`。

## 校验

- **首选 `npm run check`（= `scripts/prebuild_check.mjs`）**：一次扫掉标题裸 `<>`（整站构建失败）、
  MDX 裸 `{expr}`（运行时白屏）、KaTeX 未定义宏、图还在裸链维基、脚注定义/引用对不上、裸 URL。
  默认扫 `docs/` 跳过 `wow/`，`--wow` 扫全部，有问题退出码 1。改完任何 .md 先跑它。
  - 判据别写错：脚注**引用**后可能紧跟冒号（中文「…[^23]：」），不能用 `(?!:)` 区分定义与引用，
    要先整段抠掉「定义行 + 缩进续行」；裸 URL 要加 `(?!\()`，否则 `[url](url)` 合法脚注定义被误报。
  - **传路径必须传目录，不能传文件**：传文件会在 `readdirSync` 抛 ENOTDIR 后被静默吞掉，
    输出「预检文件数: 0 / √ 全部通过」——看着像通过，其实一个都没扫。
- 三件套在 `C:\Users\liruqi\.workbuddy-ai\binaries\node\workspace`：
  `katexcheck.mjs`、`mdxtest.mjs`、`mathnodes.mjs`（remark-math AST：inlineMath/math 计数，查一行式 `$$`）。
- **必跑第四件套 `r_mdxrun.mjs`**：真正 eval 编译产物（stub jsx，不用装 react），抓 `ReferenceError`。
  前三件套全绿但这个炸的情况真实发生过。用法：`node r_mdxrun.mjs <绝对路径.md>`。
- **更快的一环：`scratch/_render.mjs`**（项目根跑）。remark-parse → gfm → math → rehype → katex，
  再遍历 hast 统计 katex/katex-display/脚注引用/脚注项/table/残留 `[^n]`。**项目没装 rehype-stringify**，
  不要 stringify。几秒出结果，日常先跑它。
- **验证 figure/图片块必须走真 MDX 管线**：`_render.mjs` 用纯 remark，**裸 HTML 会被丢掉**
  （remark-rehype 没开 `allowDangerousHtml`），验 `<figure>` 会得到 figure=0 的假阴性。
  要用 `scratch/_figcheck.mjs`：`@mdx-js/mdx` compile + eval，stub jsx 工厂后遍历真实元素树。
- `r_bisect.mjs`：二分定位 MDX 编译失败的行（COMPILE ERROR 只说 acorn 报错不给行号）。

## 跑构建的完整配方

先 `export PATH="/c/Users/liruqi/.workbuddy-ai/binaries/node/versions/22.22.2-2:$PATH"`。

1. `npm.cmd install --no-audit --no-fund --registry=https://registry.npmmirror.com`
   （默认 registry 极慢，47 分钟装不完；镜像约 32 分钟。不改 package-lock.json）
2. 构建**必须** `dangerouslyDisableSandbox`，否则写 `.docusaurus/` 会 EPERM。
3. **`docs/wow/` 是 9711 篇，占全站 9729 篇的 99.8%**。不要手工改 config，用现成脚本：
   - `npm run build:slim` = `SKIP_WOW=1` → exclude `wow/**`，产物写 **`build-slim/`**（不覆盖正式 `build/`）。
     改正文/样式用这个，一两分钟出结果。Windows cmd 不吃 `VAR=1 cmd` 前缀，用 Git Bash 或 `set SKIP_WOW=1&& …`。
   - `npm run build:big` = `NODE_OPTIONS=--max-old-space-size=8192 docusaurus build`（正式全量）。
     崩溃栈是 `v8::FatalProcessOutOfMemory` + `Runtime_MapGrow` 而非 EMFILE 时就是堆不够——裸 `npm run build` 必挂。
4. 全量：client ~24m + server ~7m + 9711 页落盘；不带 wow 约 12 分钟（有持久化缓存后 server 1.5m + client 9.5m）。
5. **堆上限直接从 GC 日志读**：`Mark-Compact (reduce) 3870.7 (4099.5) MB` 括号里的数就是上限；
   `3870.7 -> 3870.7` 表示一轮 GC 什么都没回收（真的不够，不是泄漏）。**4096 不够，8192 才够**，
   数字别超过物理内存。
6. `npm run build:faster`（需装 `@docusaurus/faster`）：Rspack + SWC。开关 `process.env.FASTER === '1'`，
   没装包时默认关闭不影响现有构建。
   - 键名是 **`future.faster`**；老名字 `experimental_faster` 会报"has been renamed"。
   - **别写 `faster: true`**：它会把 `ssgWorkerThreads` 一起打开，而该项要求
     `v4.removeLegacyPostBuildHeadAttribute === true`，否则直接 throw。要显式列项并跳过它和 `gitEagerVcs`。
7. **`outDir` 不是 config 字段**，只能走 CLI `docusaurus build --out-dir <dir>`。
   写进 `docusaurus.config.js` 会报 `These field(s) ("outDir",) are not recognized`。
8. **改完 `docusaurus.config.js` 必须真校验**，`node --check` 不够（语法对但字段不认识照样挂）。
   一秒出结果：`require('@docusaurus/core/lib/server/config.js').loadSiteConfig({siteDir: process.cwd()})`，
   顺便打印 `docs.exclude` / `future.faster` 确认 env 分支生效。
9. 产物在 `build/wiki/<分类>/<条目>.html`（**不是目录**）。
10. `exclude` 会**覆盖**插件默认值，config 里写成 `['wow/**', ...DEFAULT_EXCLUDE]`；
    顶层已有 `onBrokenLinks: 'log'`，别再在 docs 插件里设 `'throw'`（会把 log 变中断）。
11. **`docusaurus serve` 没有 `--out-dir` 选项**（3.10.1 实测 `unknown option`）。
    预览产物直接用 `python -m http.server <port> --bind 127.0.0.1` 在输出目录下起服务，baseUrl 是 `/` 所以绝对路径 OK。
12. 站点**没有 CI**：仓库无 `.github/workflows`，README 写的是 `yarn deploy`，push 不会自动部署。
    "改了 CSS 线上没变化"先查 `build/` 的 mtime 是不是比源码旧。

## GitHub 渲染公式的坑（.md 在 GitHub 上直接看）

- **行内公式起始 `$` 前必须是空白或行首**。紧跟中文标点（`，。、：（）`）GitHub 不渲染，会原样显示源码。
  结尾 `$` 后接中文标点没问题。→ 起始 `$` 前补一个空格。
- 正文里非分隔符的裸 `$` 也要处理；URL 含 `$` 写成 `%24`。
- 不要用 GitHub 专用的 `$`…`$` 写法——remark-math 不认，站点渲染失败。
- 块公式 `$$` 独占行即可；`.md` 里若 `$$` 与前文同行需行尾加 `\` 换行。
