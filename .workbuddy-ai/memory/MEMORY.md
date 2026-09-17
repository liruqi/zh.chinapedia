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
- 未被引用的脚注定义 remark-gfm 不渲染，留着无害。

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
  （wiki2md.py 的 `fix_autolinks` 会转成 `[原文](url)`）。`<` 出现在 `$…$` 公式内部是安全的。
- **最大的坑：MDX 的 `{expr}` 在 `compile()` 阶段不报错，只在页面运行时炸。**
  只要正文残留没包进 `$…$` 的 LaTeX（如参考文献里的 `\operatorname{li}`），编译产物里
  就是一个裸标识符，访问页面直接 `ReferenceError: li is not defined` + 白屏。
  → 所以「MDX COMPILE OK」**不能**作为通过标准，必须跑运行时渲染。
  → `wiki2md.py` 已有兜底 `escape_mdx_braces()`：把数学环境与行内代码之外的 `{}`
  转义成 `\{ \}`，裸 `<`（后不跟 `[A-Za-z/!?]`）转义成 `\<`；`<blockquote>`/`<br />`/
  `<!-- -->`/`<url>` 不受影响。

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
