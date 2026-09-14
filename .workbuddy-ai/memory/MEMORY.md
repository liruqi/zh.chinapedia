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
- KaTeX 的 CSS 由 `docusaurus.config.js` 的 `stylesheets` 从 CDN 引入（jsdelivr）。
  **坑**：CDN 上的 katex 版本必须和 rehype-katex 实际用的 katex 版本一致，否则公式排版会错。
  rehype-katex 7 拉的是 katex 0.16.x，以 `package-lock.json` 里 `node_modules/katex` 为准
  （当前 0.16.47）。改版本时 SRI `integrity` 要一起换：
  `python -c "urllib.request.urlopen(url) -> hashlib.sha384 -> base64"` 现算。
  曾因 CDN 停留在 0.13.24（Docusaurus 官方文档里的旧示例）而版本不匹配。
- MDX 硬性约束：正文不得出现未转义的 `< >` 与 `{}`；禁止 `<https://…>` 自动链接
  （wiki2md.py 的 `fix_autolinks` 会转成 `[原文](url)`）。`<` 出现在 `$…$` 公式内部是安全的。
