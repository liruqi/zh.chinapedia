# zh.chinapedia 项目约定

## 条目生成

- `scripts/wiki2md.py`：抓非中文维基 wikitext → LLM 翻译 → 写 `docs/{分类}/{条目名}.md`。
- 两种公式风格：
  - 默认：数学公式用**行内代码 / 代码块**（见 SYSTEM_PROMPT 第 6 条）。
  - `--katex`：公式用 **KaTeX** `$…$` / `$$…$$`，默认输出 `{条目名}.katex.md`。
- 同一条目可同时存在 `X.md` 与 `X.katex.md`（后者是前者的纯公式改写版，正文逐字相同）。

## 站点栈与坑

- Docusaurus 3.10 + MDX 3，已配 `remark-math` + `rehype-katex`（见 docusaurus.config.js）。
- **坑**：remark-math 6 下，写成一行的 `$$x$$` 会被解析成 **inlineMath**（行内样式，不居中）。
  独立公式必须写成三行：`$$` 单独一行 → 公式 → `$$` 单独一行。
  （用 micromark/remark-math AST 才看得出来，肉眼和 MDX 编译都不报错。）
- **待办**：`docusaurus.config.js` 里**没有**引入 katex 的 CSS（既没 `stylesheets` 也没 import
  `katex/dist/katex.min.css`）。没有 CSS，rehype-katex 生成的 HTML 会显示错乱。
  修法二选一：config 加 CDN `stylesheets`，或 `npm i katex` 后在 `src/css/custom.css` 里
  `@import 'katex/dist/katex.min.css';`。
- MDX 硬性约束：正文不得出现未转义的 `< >` 与 `{}`；禁止 `<https://…>` 自动链接
  （wiki2md.py 的 `fix_autolinks` 会转成 `[原文](url)`）。`<` 出现在 `$…$` 公式内部是安全的。
