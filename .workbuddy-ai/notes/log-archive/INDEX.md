# 历史日志归档

`memory/` 目录**每次会话整体注入**，日志堆多了会把注入预算撑爆、内容被截断。
所以只保留**当天**日志在 `memory/`，历史日志移到这里（**内容一字未改，只是搬家**）。

| 日期 | 内容提要 |
|---|---|
| `2026-09-15.md` | KaTeX 化（`wiki2md.py --katex` 默认 + GitHub 兼容）、`wikitext2md.py` / `notes2footnotes.py` / `md2footnotes.py` 诞生、黎曼猜想页 `li is not defined` 崩溃、`_chat_stream` 缺总时限挂死 7.5h |
| `2026-09-16.md` | 与 pandoc/mediawiki-to-gfm 对比（结论：pandoc 产物在本站构建不了）、`wikitext2md.py` 三个缺陷修复、英文条目参考文献在 `==References==` 的根因、新建中文 `西格尔零点.md` |
| `2026-09-21.md` | 图片搬 R2（`wikiimg2r2.py`、SigV4、thumburl/GIF 反例）、`img2figure.py` 图注可见化、KaTeX 缺 MediaWiki 宏、中文条目丢图、整站构建失败（标题裸尖括号）、blog tags 警告 |
| `2026-09-22.md` | `prebuild_check.mjs`、`wikiterm.py` 术语译名、`md2zh.py --terms` 注入、整站构建 OOM 与 `future.faster`（Rspack）、图片显示宽度 `w250`、相邻脚注补空格、MEMORY.md 瘦身、日志重复的流程教训 |
| `2026-09-23.md` | （仍在 `memory/`，未归档）泰语 orphan 分支完成 |

**查历史时**：先看 `notes/ref-pipeline.md` / `ref-site.md`（沉淀后的结论），
需要过程细节再回这里按日期翻。
