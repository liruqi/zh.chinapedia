# zh.chinapedia 项目约定

## 条目生成

- `scripts/wiki2md.py`：抓非中文维基 wikitext → LLM 翻译 → 写 `docs/{分类}/{条目名}.md`。
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

## 中文条目文风

- 开头用**中文百科式**写法：`**词条名**（英语：English name），也称为**别名1**、**别名2**，是指……`。
- 不要直译英文语境里才成立的句子（如「有时『孪生素数』一词也用来指一对孪生素数，它的另一个名称是
  prime twin 或 prime pair」这类），改成中文读者习惯的「（英语：…）+ 中文别名」表达。

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
- **从未跑过 `npm install` / `npm run build`**（node_modules 未安装）。若 Docusaurus 未默认开
  remark-gfm，正文里的 GFM 表格需要在 `docusaurus.config.js` 的 `remarkPlugins` 加 `remark-gfm`。

## GitHub 渲染公式的坑（.md 在 GitHub 上直接看）

- **行内公式起始 `$` 前必须是空白或行首**。紧跟中文标点（`，。、：（）`）时 GitHub 不渲染，
  会原样显示 `$…$` 源码。结尾 `$` 后接中文标点没问题。→ 起始 `$` 前补一个空格即可。
- 正文里非分隔符的裸 `$` 也必须处理（官方文档要求）。URL 含 `$` 时写成 `%24`（等价且不影响链接文字）。
- 不要用 GitHub 专用的 `$`…`$` 写法 —— remark-math 不认，站点会渲染失败。
- 块公式用 `$$` 单独占行即可，GitHub 支持；`.md` 里若 `$$` 与前文同行需行尾加 `\` 换行。
