# zh.chinapedia 项目约定

## 条目生成

- `scripts/wiki2md.py`：抓非中文维基 wikitext → LLM 翻译 → 写 `docs/{分类}/{条目名}.md`。
- `scripts/wikitext2md.py`：**纯机械** wikitext → Markdown，**不翻译、不调 LLM**。
  用于「英文原文镜像站」`D:\SRC\Z\en.chinapedia\`（如 `docs/math/riemann_hypothesis.md`），
  或作为翻译前的干净中间产物。支持表格/图库/脚注/60+ 模板，`--report` 列未识别模板。
- 公式风格：**默认 KaTeX**（`$…$` / `$$…$$`，只输出一份 `{条目名}.md`）；
  加 `--no-katex` 才退回行内代码 / 代码块（SYSTEM_PROMPT 第 6 条 `RULE6_KATEX` / `RULE6_CODE`）。
- KaTeX 模式下脚本会自动做 GitHub 兼容后处理：`escape_dollar_in_urls()` + `fix_github_math()`。

## 链接与脚注

- **维基链接保持行内**（`[文字](https://xx.wikipedia.org/…)`）；**其他外部链接改成 GFM 脚注**，
  写法照 `docs/ai/product/openclaw.md`：正文 `…。 [^1] [^2] [^3]`，文末
  `[^n]: [https://host](url)`。同一 URL 复用同一编号。
- 用 `scripts/md2footnotes.py` 批量转换（幂等、保 CRLF）。默认只改正文，跳过
  「注释/参考文献/外部链接/科普读物」这类本身就是链接清单的章节（`--all` 可关掉）。
- 正文里 wikitext `<ref>` 残留的 `[[7]](url)` 标记也是外链，同样要转成脚注——
  这类标记往往比 `[文字](url)` 更多。
- 脚注标记后面紧跟 `[` 或 `$` 时要补空格，否则 `[^1]$x$` 在 GitHub 上不渲染。
- `remark-gfm` 不用手动配：`@docusaurus/mdx-loader` 默认依赖并启用它。
- **`<ref>` → `［n］` 是纯文本，点不动**。wiki2md / 人工翻译会把 wikitext `<ref>` 整理成
  文末 `## 注释` 的编号列表，正文留全角 `［1］`。用 `scripts/notes2footnotes.py` 接成
  真脚注：删掉 `## 注释` 整节 → 正文 `［n］`→`[^n]` → 文末补定义；
  已有脚注定义会整体顺延编号避免冲突。编号与 wikitext `<ref>` 出现顺序一致。
- 未被引用的脚注定义 remark-gfm 不渲染。**只有「多写了一条冗余定义」时才无害**；
  如果整节来源列表都靠它撑着（如 grok.md 的 `## 参考来源` 三条全没引用），
  **整节内容会在页面上凭空消失**。用 `npm run check` 能扫出来。
- **翻译残留的字面占位符**：中文稿里出现过 5 处 `[^n]`（英文原文 0 处），页面上原样
  显示成 `[^n]` 且不可点。LLM 翻译时会把没接上的引用写成这个样子，见到就删。

## 中文条目文风

- 开头用**中文百科式**写法：`**词条名**（英语：English name），也称为**别名1**、**别名2**，是指……`。
- 不要直译英文语境里才成立的句子（如「有时『孪生素数』一词也用来指一对孪生素数，它的另一个名称是
  prime twin 或 prime pair」这类），改成中文读者习惯的「（英语：…）+ 中文别名」表达。
- **长从句要拆散、按中文习惯重排**，不要保留 "whose … and whose …" 式的连环定语。
  例：「其自变量可以取 1 以外的任意复数，函数值也是复数」
  →「是一个复值函数，其自变量 $s$ 可取复平面上除 $1$ 以外的任意值」。
- **正文里的外文原文引文（德文、法文、拉丁文）一律删掉，只留中文译文**——中文读者看不懂。
  已删：黎曼 1859 年那段德文原文（"es ist sehr wahrscheinlich, dass alle Wurzeln reell sind…"）。
  参考文献里的外文**标题/刊名照旧保留**，不要译。

## 站点栈与坑

- Docusaurus 3.10 + MDX 3，已配 `remark-math` + `rehype-katex`（见 docusaurus.config.js）。
- **坑**：remark-math 6 下，写成一行的 `$$x$$` 会被解析成 **inlineMath**（行内样式，不居中）。
  独立公式必须写成三行：`$$` 单独一行 → 公式 → `$$` 单独一行。
  （用 micromark/remark-math AST 才看得出来，肉眼和 MDX 编译都不报错。）
- KaTeX 的 CSS 由 `docusaurus.config.js` 的 `stylesheets` 从 CDN 引入（jsdelivr）。
  **坑**：CDN 上的 katex 版本必须和 rehype-katex 实际用的 katex 版本一致，否则公式排版会错。
  rehype-katex 7 拉的是 katex 0.16.x，以 `package-lock.json` 里 `node_modules/katex` 为准
  （当前 0.16.47）。改版本时 SRI `integrity` 要一起换：
  `python -c "urllib.request.urlopen(url) -> hashlib.sha384 -> base64"` 现算。
  曾因 CDN 停留在 0.13.24（Docusaurus 官方文档里的旧示例）而版本不匹配。
- MDX 硬性约束：正文不得出现未转义的 `< >` 与 `{}`；禁止 `<https://…>` 自动链接
  （wiki2md.py 的 `fix_autolinks` 会转成 `[原文](url)`）。
  **但"`<` 在 `$…$` 里是安全的"只对 MDX 编译成立** —— 见下面「标题里的裸 `<`」。
- **最大的坑：MDX 的 `{expr}` 在 `compile()` 阶段不报错，只在页面运行时炸。**
  只要正文残留没包进 `$…$` 的 LaTeX（如参考文献里的 `\operatorname{li}`），编译产物里
  就是一个裸标识符，访问页面直接 `ReferenceError: li is not defined` + 白屏。
  → 所以「MDX COMPILE OK」**不能**作为通过标准，必须跑运行时渲染。
  → `wiki2md.py` 已有兜底 `escape_mdx_braces()`：把数学环境与行内代码之外的 `{}`
  转义成 `\{ \}`，裸 `<`（后不跟 `[A-Za-z/!?]`）转义成 `\<`；`<blockquote>`/`<br />`/
  `<!-- -->`/`<url>` 不受影响。

## 自托管 Qwen 接口（`https://lms.thaiwen.com/v1`，LM Studio）的两个必开设置

**不开就完全没法用**：模型 `qwen/qwen3.5-9b` 强制走思维链，译一句话要想 150s+ 且
一个字都不吐。两条一起加才有救（`wiki2md.llm_chat` 已内置）：

1. **`stream: true`** —— 接口前面挂 Cloudflare，源站约 100s 不出首字节就返回
   **HTTP 524**。非流式请求必然超时；流式 2s 就开始吐 SSE，跑多久都不超时。
2. **`reasoning_effort: "none"`** —— 唯一真能关掉思维链的参数。
   实测一句话：默认 150s 截断、reasoning 8377 字符、**0 输出**；
   加 `none` 后 **2.0s 出首个字、13.2s 出全文、reasoning 0**，译文质量无可见下降。

**无效的那些（都试过，别再试了）**：`chat_template_kwargs:{enable_thinking:false}`
（静默忽略）、`thinking:{type:"disabled"}`、`reasoning:{enabled:false}`、
`enable_thinking` 放顶层（反而把 reasoning 顶到 1255 token）、提示词加 `/no_think`
（直接把模型卡死到 524）、`<arg_key:6124c78e>`（无效）、`reasoning_effort:"minimal"/"low"`
（照想不误，420s 都没出字）。只有 `"none"` 是开关，`minimal`/`low` 不是。

另外两个坑：
- **必须带浏览器 User-Agent**：urllib 默认的 `Python-urllib/3.x` 会被 Cloudflare
  直接 **403**（curl 一直正常，就是这个差别）。
- 并发 3–4 路能再快 3 倍（17 块 48s vs 串行更久），Cloudflare 不拦。

## 英→中翻译：`scripts/md2zh.py`

`wikitext2md.py` 出英文稿 → `md2zh.py` 只做翻译（不碰 wikitext）。切块时公式块、
脚注定义、图片、表格原样照抄，只译散文；默认 `reasoning_effort=none`、`--jobs 4`、
有 `--state` 断点续译。Riemann zeta function（74k 字符 / 220 块）约 10 分钟。

**模型会犯的三个错，脚本里都有兜底**：
- URL 里的 `_` 被改成空格（`analytic_number_theory` → `analytic_number theory`）
  → 送译前把 URL 换成 `§U0§` 占位符，译完还原。
- 把行内链接改写成脚注、还自己编号（跟真脚注撞号，真脚注被顶掉）
  → 脚注标记也换成 `§F3§`；译完 `fix_footnotes()` 逐行对账：多的删、少的补；
  译文里凭空出现的 `[^n]:` 定义整行丢掉。占位符用 `§…§` 不要用 `\x01`，
  控制字符在传输里会被吃掉，模型会把 `§F2§` 写成 `[^F2^]`。
- 改标题层级（`##` → `#`）→ 以原文 `#` 个数为准强行纠正。

**第四个错（最严重）：标题单独成块 → 整节内容全是编的。**
空行被当成 verbatim 块，所以每个 chunk 实际就是一个段落，**标题行自己就是一个 chunk**。
模型收到 `## Euler's product formula` 一行，会「补全」出 27~57 行的虚构内容，
还自带编造的 `[^1]: 此处为脚注占位符，原封不动照抄。`（把 system prompt 原文都吐出来）。
对策：
- 单行为标题 → 走 `HEADING_SYSTEM` 专用提示词，只取一行；
- **输出行数必须等于输入行数**，不等就重试，最终逐行兜底（`translate_line`）；
- 缓存命中也要求行数严格相等（写 `>=` 会把幻觉当有效缓存）；
- 收尾兜底：`[^n]:` 定义行若不是原文逐字复制，一律丢；多出来的行里
  `[^n]:` / `#` 开头的一律判为幻觉。
→ **「输入行数 vs 输出行数」是最有效的幻觉探测器**，比看长度比准得多。
排查脚本套路：按 chunk 比行数 + 查输出里有没有中日韩字符（无中文 = 漏译）。

**`_chat_stream` 必须有总时限**：`urlopen(timeout=)` 只管单次 recv，
服务端隔一会儿发个心跳块就能把连接挂几小时（实测 7.5 小时）。
已加 `deadline = time.time() + timeout`，读流时超时即抛。

## 图片：必须搬到 Cloudflare R2（chped 桶），不能直接外链维基

`[[File:X|thumb|caption]]` 机械转换出来是 `![caption](…/wiki/File:X)`，
那是**文件描述页**（HTML），不是图片，必裂图；thumb.wikimedia.org 还有反盗链。

流程（`scripts/wikiimg2r2.py` 一键做完）：
Commons API 查真实地址 → 下载 → AWS SigV4 PUT 到 R2 → 改写成
`https://pub-275e30003c354ac0862cc9839e0f952a.r2.dev/<key>`（key 形如 `docs/math/X.png`）。

- 凭证在 `scripts/r2.local.json`（**已 gitignore，不提交**）；prod 换凭证用环境变量
  `R2_ENDPOINT / R2_BUCKET / R2_PUBLIC_BASE / R2_ACCESS_KEY / R2_SECRET_KEY`。
- 脚本**不依赖 boto3**，自己实现 SigV4（装 boto3 在这台机器上要十几分钟）。
- 映射缓存 `scripts/wikiimg-map.json` 会提交，重跑同一张图不会重复上传。
- 坑：主机名是 `commons.wikimedia.org`（不是 wikipedia.org）；
  SVG/PDF 必须取 `thumburl`（渲染好的 PNG），GIF 反过来要取原图（缩略图会变静止帧）；
  R2 是路径风格 + region `auto` + canonical URI 不做路径归一化；
  这边的网络会随机 RST，上传/校验都要重试，**校验用 GET 比字节数，别信单次 HEAD**。
- `wikitext2md.py` 的 `file_url()` 已改成 `Special:FilePath/<name>?width=1000`，
  即使没跑 R2 那一步，图也是真能显示的。

搬完还要走 **`scripts/img2figure.py`**：`![图注](url)` 的图注只躺在 alt 属性里、
肉眼看不见，且连续图片行会被合并进同一段落并排显示。脚本把它们改写成
`<figure>` + `<img>` + `<figcaption>图注</figcaption>`（维基百科的原生结构）。
MDX 要求 **JSX 块的子内容要用空行隔开才会当 markdown 解析**，所以 figure /
figcaption 内侧都留空行；alt 用 LaTeX→Unicode 降级后的纯文本
（直接去掉 `$` 会露出 `\zeta` 这种裸 LaTeX）。

## KaTeX 缺 MediaWiki 扩展的宏

维基原文大量用 `\C \R \N \Z \Q \F \sgn` —— 这是 **MediaWiki 在自己 MathJax 配置里
扩展的宏**，KaTeX 完全不认，页面会渲染成红色 parse error（GitHub 的 MathJax 也不认）。
两处都要补：`docusaurus.config.js` 里给 rehype-katex 配 `macros`（兜底新导入的条目），
现存 .md 里换成 `\mathbb{C}` 这类标准写法。
排查用 `scratch/_macroscan.mjs`（逐个公式试渲染），**要按 display / inline 分别传
`displayMode`**，否则 `\begin{align}` 会被误报。

## 验证 figure / 图片块必须走真 MDX 管线

`scratch/_render.mjs` 用的是纯 remark（remark-parse + remark-rehype），
**裸 HTML 会被直接丢掉**（remark-rehype 没开 `allowDangerousHtml`），
所以拿它验 `<figure>` 会得到 figure=0 的假阴性，而 `<figure>` 里的 img 反而还在
（因为空行把它切成了独立段落）。
→ 验证 JSX/HTML 结构要用 `scratch/_figcheck.mjs`：`@mdx-js/mdx` compile + eval，
stub 掉 jsx 工厂后遍历真实元素树。

## 翻译带图的条目：先搬图再翻译，译完核图的数量

`wiki2md.py` 翻译阶段会把 `[[File:…]]` **连同图注一起丢掉**（中文黎曼猜想.md 因此
一张图都没有，英文源有 6 张）。正确顺序是：
`wikitext2md` → `wikiimg2r2.py`（搬到 R2）→ `img2figure.py`（figure 块）→ 再翻译。
译完用 `grep -c '^<figure>'` 对一遍中英两版，数量必须相等。
中英同一词条的**脚注编号一致**，英文图注里的 `[^n]` 可以直接搬到中文图注。

## 标题里的裸 `<` / `>` 会让整站构建失败（真凶是「标题内数学公式」）

实测（调 `toHeadingHTMLValue()` 本身，见 `scratch/_tocangle.mjs`）四种标题：

| 标题 | TOC 输出 | 漏裸 `<` |
|---|---|---|
| `## …*D* \< 0`（Markdown 转义） | `… <em>D</em> &lt; 0` | 否 ✅ |
| `## 裸尖括号 D < 0`（普通文本） | `裸尖括号 D &lt; 0` | 否 ✅ |
| `## 公式 $D < 0$` | `公式 D < 0` | **是 ⚠** |
| `## 已转义 \< 与 \>` | `已转义 &lt; 与 &gt;` | 否 ✅ |

机制（之前猜的「KaTeX annotation 原样插入」是错的）：
`@docusaurus/mdx-loader/src/remark/toc/utils.ts` 的 `toHeadingHTMLValue()` 只显式处理
`text / heading / inlineCode / emphasis / …`，`inlineMath` 落到 `default: return toString(node)`，
mdast-util-to-string 原样返回 `D < 0`（连 `$` 都剥掉）、**不转义**；
TOC 再走 `dangerouslySetInnerHTML` → `html-minifier-terser` Parse Error → **整站构建失败**。

所以：**普通文本和 `\<` 转义都是安全的，只有「标题里的 `$…$` 含裸尖括号」会炸。**
修法：写成 `$D \lt 0$` / `$x \gt 0$`（渲染一样，源码无裸尖括号）。
`prebuild_check.mjs` 放行 `\<` `\>`，但裸 `<>` 继续报——正好覆盖公式这一种。

## KaTeX 报错没有 katex-error 类

KaTeX 渲染失败时**不抛异常、也不加 `katex-error` 类**，而是把源码原样渲成红色
`color:#cc0000` / `mathcolor="#cc0000"`。基于 hast 的校验要认这个颜色，
数 `katex-error` 永远是 0。`_macroscan.mjs` 用 `throwOnError: true` 直接试渲染，不受影响。

## 专有名词译名：查中文维基条目名，不要猜

LLM 译专有名词很不稳：`Riemann's xi function` →「黎曼的 xi 函数」（应为**黎曼ξ函数**），
`Mellin transform` 留下「Mellin」，`Theta function` 留下「Theta」。

**权威译名 = 中文维基条目名**。用 `scripts/wikiterm.py` 抓：
`en.wikipedia.org` 的 `prop=langlinks&lllang=zh`（→ `scripts/wiki-zh-terms.json`，已提交）。

    python scripts/wikiterm.py "Riemann xi function"
    python scripts/wikiterm.py --scan docs/math/ --glossary   # 抽 .md 里所有维基链接
    python scripts/wikiterm.py --no-wikidata                  # 严格模式
    python scripts/wikiterm.py --fix-cache                    # 去重 + 重做简繁转换

`scripts/md2zh.py --terms` 会按 chunk 把命中的词条塞进提示词（标题/小节/正文三条路径都注入），
匹配做了归一化，所以 `Riemann's xi function` 能对上术语表的 `Riemann xi function`。

**三级兜底，质量递减**：langlinks（可靠）> Wikidata 中文标签（机翻/生造多，
`Andrew Granville → 安德鲁·关维`、`János Pintz → 平茨·亚诺什`）> 没有。
→ `--no-wikidata` 只要第一级。
→ **查不到就保留英文原文，绝不生造译名**。踩过：`Tikao Tatsuzawa` 中/日文维基都没条目，
猜「立川」是错的（立川读 Tachikawa/Tatsukawa，不是 Tatsuzawa），已回退。

**人名默认不进术语表**（`--terms-people` 才保留）：中文译名里的间隔号「·」
是音译人名的标志，术语名不会带；且项目约定第 7 条允许人名留原文。
人名（Conrey / Voronin / Hasse / Granville…）和缩写（GRH / GUE）现在都保留原文。

坑：
- **简繁转换用 `zh.wikipedia.org` 的 `action=parse&variant=zh-cn`，且必须分批（40 条）**。
  一次塞几百行，parse 返回行数一对不上就整批退回原文，繁体一个都转不掉。
  `converttitles` 靠不住（不需转换时干脆不返回 converted）。
- **维基 API 会 429**：批量查询要限速（≥1.2s/次）+ 按 `Retry-After` 退避。
- **别在 `npm run build` 期间查**：本机网络同时跑构建必 RST（WinError 10054），
  实测 76 个词条 31 分钟只成功 5 个。
- 缓存键要**按小写去重**（维基标题大小写等价，扫描会当成两个词）；
  变体里留「句子式大小写」那个（小写字母最多的）。
- 改完用「中英混排」正则扫一遍残留：
  `[\u4e00-\u9fff]\s?([A-Za-z][A-Za-z\-']{2,})\s?[\u4e00-\u9fff]`

## 人工翻译长条目：§ 标记两阶段流水线

LLM 翻译长条目（>3 万字）很慢且质量不稳，可用「机械解析 + 人工翻译」两阶段：

1. `scratch/prep_*.py` 把 wikitext 压成中间表示，链接/公式/引用/脚注全部换成标记：
   `§L{Target|显示}§`、`§M{行内公式}§`、`§D{块公式}§`、`§H{作者|年}§`、`§S{作者|年|页}§`、
   `§REF{n}§`、`§X{OEIS id}§`。人工只译纯散文，不碰标记（标记内是英文原文，不会被误译）。
2. `scratch/build_*.py` 把标记展开回 Markdown，并复用
   `wiki2md.escape_dollar_in_urls()` + `wiki2md.fix_github_math()`，保证与脚本产出风格一致。

复用过的坑：

- **wikitext 标题层级**：`== X ==` → `## X`（用 `"#" * len(m.group(1))`，**不要 +1**）。
- **`{{harvs}}` 等模板取参**：先剥掉外层 `{{ }}`，再**只在深度 0 处**按 `|` 切分；
  深度只由 `{`/`}` 计数（早期版本把 `|` 也算进深度 → 所有引用渲染成空）。
- 列表用 `1.` 而不是 `#`，否则行首 `#` 被当成 H1。
- 中文引号：ASCII `"` 前后是中文时批量换成 `“”`。
- `（英语：X）` 前先占位保护，再补中英文之间的空格，否则 CJK 空格规则会插进括号里。
- 链接显示文字不要以 `$…$` 开头（`[$L$ 函数]` 很难看），改成 `§L{Target|L 函数}§`。

## 校验

- **首选：`npm run check`（= `scripts/prebuild_check.mjs`）**。一次扫掉下面所有已知故障类：
  标题裸 `<` `>`（整站构建失败）、MDX 裸 `{expr}`（运行时白屏）、KaTeX 未定义宏、
  图还在裸链维基、脚注定义/引用对不上、裸 URL `[https://…]`。
  默认扫 `docs/` 跳过 `wow/`，`--wow` 可扫全部，有问题退出码 1。
  改完任何 .md 先跑它，比逐个人肉脚本快得多。
  - 脚本自己的两个判据别写错：脚注**引用**后面可能紧跟冒号（中文「…[^23]：」），
    不能用 `(?!:)` 区分定义和引用，要先整段抠掉「定义行 + 缩进续行」；
    裸 URL 要加 `(?!\()`，否则 `[url](url)` 这种合法脚注定义会被误报。
  - **传路径必须传目录，不能传文件**：传文件会在 `readdirSync` 抛 ENOTDIR 后被静默吞掉，
    输出「预检文件数: 0 / √ 全部通过」——看着像通过，其实一个都没扫。
- 校验脚本在 `C:\Users\liruqi\.workbuddy-ai\binaries\node\workspace`：
  `katexcheck.mjs`（KaTeX 能否渲染）、`mdxtest.mjs`（MDX 编译）、`mathnodes.mjs`（remark-math
  AST：inlineMath / math 计数，查一行式 `$$`）。新条目改完跑这三件套 + 查 CRLF。
- **必跑第四件套 `r_mdxrun.mjs`**：真正 `eval` 编译产物（stub jsx，不用装 react），
  抓 `ReferenceError: xxx is not defined`。前三件套全绿但这个炸的情况真实发生过。
  用法：`node r_mdxrun.mjs <绝对路径.md>`。
- Docusaurus 默认已启用 remark-gfm（`@docusaurus/mdx-loader` 的依赖），**脚注和 GFM 表格
  都能直接用**，不用改 `remarkPlugins`。已用真实构建产物验证过。
- **更快的一环：`scratch/_render.mjs`**（项目根跑，能用到项目 node_modules）。
  走 remark-parse → remark-gfm → remark-math → remark-rehype → rehype-katex，
  再遍历 hast 树统计 katex / katex-display / 脚注引用 / 脚注列表项 / table / 残留 `[^n]`。
  项目里**没装 rehype-stringify**，所以不要 stringify，直接数节点。几秒钟出结果，
  日常改动先跑它，只有要验线上产物时才跑 12 分钟的 `npm run build`。
- `r_bisect.mjs`：二分定位 MDX 编译失败的行（COMPILE ERROR 只说 acorn 报错，不给行号）。
- **跑构建的完整配方**（node/npm 不在 PATH，先
  `export PATH="/c/Users/liruqi/.workbuddy-ai/binaries/node/versions/22.22.2-2:$PATH"`）：
  1. `npm.cmd install --no-audit --no-fund --registry=https://registry.npmmirror.com`
     （默认 registry 在国内极慢，47 分钟都装不完；镜像约 32 分钟。不改动 package-lock.json）
  2. 构建**必须** `dangerouslyDisableSandbox`，否则写 `.docusaurus/` 会 EPERM
  3. 全量构建会因 `docs/wow/`（9711 篇魔兽物品页）报 `EMFILE: too many open files`。
     验证时临时给 docs 插件加 `exclude: ['wow/**']`，跑完务必删掉
  4. `NODE_OPTIONS=--max-old-space-size=4096`；client 8.3m + server 4.0m，共约 12 分钟
  5. 产物在 `build/wiki/<分类>/<条目>.html`（不是目录）

## GitHub 渲染公式的坑（.md 在 GitHub 上直接看）

- **行内公式起始 `$` 前必须是空白或行首**。紧跟中文标点（`，。、：（）`）时 GitHub 不渲染，
  会原样显示 `$…$` 源码。结尾 `$` 后接中文标点没问题。→ 起始 `$` 前补一个空格即可。
- 正文里非分隔符的裸 `$` 也必须处理（官方文档要求）。URL 含 `$` 时写成 `%24`（等价且不影响链接文字）。
- 不要用 GitHub 专用的 `$`…`$` 写法 —— remark-math 不认，站点会渲染失败。
- 块公式用 `$$` 单独占行即可，GitHub 支持；`.md` 里若 `$$` 与前文同行需行尾加 `\` 换行。
