# zh.chinapedia 项目约定

## 条目生成

- `scripts/wiki2md.py`：抓非中文维基 wikitext → LLM 翻译 → 写 `docs/{分类}/{条目名}.md`。
- 公式风格：**默认 KaTeX**（`$…$` / `$$…$$`，只输出一份 `{条目名}.md`）；
  加 `--no-katex` 才退回行内代码 / 代码块（SYSTEM_PROMPT 第 6 条 `RULE6_KATEX` / `RULE6_CODE`）。
- KaTeX 模式下脚本会自动做 GitHub 兼容后处理：`escape_dollar_in_urls()` + `fix_github_math()`。

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

## GitHub 渲染公式的坑（.md 在 GitHub 上直接看）

- **行内公式起始 `$` 前必须是空白或行首**。紧跟中文标点（`，。、：（）`）时 GitHub 不渲染，
  会原样显示 `$…$` 源码。结尾 `$` 后接中文标点没问题。→ 起始 `$` 前补一个空格即可。
- 正文里非分隔符的裸 `$` 也必须处理（官方文档要求）。URL 含 `$` 时写成 `%24`（等价且不影响链接文字）。
- 不要用 GitHub 专用的 `$`…`$` 写法 —— remark-math 不认，站点会渲染失败。
- 块公式用 `$$` 单独占行即可，GitHub 支持；`.md` 里若 `$$` 与前文同行需行尾加 `\` 换行。
