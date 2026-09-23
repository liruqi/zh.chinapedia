# zh.chinapedia 项目约定

中文维基翻译站（Docusaurus 3.10，`docs/` 下 ~9729 篇，其中 `docs/wow/` 9711 篇）。
英文镜像 `D:\SRC\Z\en.chinapedia\`（纯内容仓库，无构建工具链）。
其中 `en.chinapedia/docs/math/` 是**独立 git 仓**（远端 `git@github.com:chinapedia/math.git`）：
`main` = 英文机械转换稿，orphan 分支 `th` = 泰语稿，文件名两版一致（便于 `git diff main..th`）。

## 详细参考（**不自动注入**，做对应工作时先 Read 对应文件，不要凭记忆猜）

| 文件 | 内容 |
|---|---|
| `.workbuddy-ai/notes/ref-pipeline.md` | 脚本分工、链接/脚注（含相邻标记间距）、文风、多语言化、LLM 翻译四错、§ 两阶段人工流水线、译名与人名白名单 |
| `.workbuddy-ai/notes/ref-site.md` | MDX/KaTeX 坑、`npm run check` 校验、完整构建配方、部署现状、图片 R2 与插图限高 |

## 必须时刻记住的硬约束

1. **`{expr}` 在 MDX `compile()` 不报错，只在运行时炸**（白屏 + `ReferenceError`）。
   「MDX COMPILE OK」**不能**作为通过标准，必须运行时 eval（`r_mdxrun.mjs`）。
2. **标题里的裸 `<` / `>` 会让整站构建失败**——真凶是标题内的数学公式（`$D < 0$`）。
   写成 `$D \lt 0$`。`prebuild_check.mjs` 放行 `\<` `\>`。
3. **改完任何 .md 先跑 `npm run check`**（= `scripts/prebuild_check.mjs`）。
   注意：**传路径必须传目录**，传文件会静默输出「预检文件数: 0 / √ 全部通过」。
4. **wikitext 里的显示宽度必须保留**：`[[File:X|thumb|250px|…]]` 的 250px →
   markdown title `"w250"` → `<figure style={{"maxWidth": "250px"}}>`。
   **MDX 里 `style="字符串"` 会在 SSR 报 `The style prop expects a mapping…`，必须传对象。**
   取 `[[File:…]]` 必须**括号配对扫描**，正则 `\|[^\[\]]*` 会被图注里的 `[[…]]` 卡死。
5. **翻译带图的条目必须先搬图再翻译**（`wikitext2md` → `wikiimg2r2.py` → `img2figure.py` → 翻译），
   否则 `[[File:…]]` 连同图注被丢。译完中英两版 `grep -c '^<figure>'` 数量必须相等。
6. **公式必须三行**（`$$` 独占一行），一行式 `$$x$$` 会被 remark-math 6 当 inlineMath。
7. **`docs/wow/` 占 99.8%**，改正文用 `npm run build:slim`（`SKIP_WOW=1` → `build-slim/`）；
   正式全量用 `npm run build:big`（`--max-old-space-size=8192`，4096 不够）。
   构建**必须** `dangerouslyDisableSandbox`。
8. **线上 `zh.chinapedia.org` 跑的是 `docusaurus start`（dev server）**，不是静态产物
   → 服务器上 `npm run build` 对访客没有影响。修复步骤见仓库根 `DEPLOY.md`。
9. **提交约定**：改动认为已完成就直接提交。凭证只放 `scripts/r2.local.json`（gitignore，不提交）。
10. **git commit message 别用 `-m` 带反引号**（会被 shell 当命令替换吃掉内容），用 `git commit -F <file>`。
11. **写日志必须幂等，且绝不和 commit 写进同一条命令**。沙箱升级重试会把整条命令重跑一遍
    （tool 结果里的 `⚠️ Sandbox bypassed`），`>>` 追加会做两次 → 日志重复；`git commit` 会做两次
    → 两条同 message 的提交。已经因此产生过两次「去掉重复粘贴的一段」清理提交。
    → 改文件用 Edit/Write 工具（不走 shell，不会被重试），提交单独一条命令；
    必须用 shell 追加时先 `grep -q '<块标题>' file || cat >> file`。
    → 判断提交是否成功**看 `git log`，不要看退出码**（重试那次会报 `nothing to commit`）。
12. **`memory/` 目录是每次会话整体自动注入的**（不只是 MEMORY.md）。细节笔记一律放
    `.workbuddy-ai/notes/`，**别放回 `memory/`**：放回去会把注入预算撑爆、内容被截断，
    等于白写（踩过一次：MEMORY.md + 4 个 ref-*.md ≈ 16 KB 被截断）。

## 环境

- 先 `export PATH="/c/Users/liruqi/.workbuddy-ai/binaries/node/versions/22.22.2-2:$PATH"`。
- npm 默认 registry 极慢，装包加 `--registry=https://registry.npmmirror.com`。
- 校验三件套 + `r_mdxrun.mjs` 在 `C:\Users\liruqi\.workbuddy-ai\binaries\node\workspace`；
  快速渲染检查用 `scratch/_render.mjs`，验 figure 用 `scratch/_figcheck.mjs`。
