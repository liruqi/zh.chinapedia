# zh.chinapedia 项目约定

中文维基翻译站（Docusaurus 3.10，`docs/` 下 ~9729 篇，其中 `docs/wow/` 9711 篇）。
英文镜像 `D:\SRC\Z\en.chinapedia\`。其中 `en.chinapedia/docs/math/` 是
**独立 git 仓**（远端 `git@github.com:chinapedia/math.git`）：`main` = 英文稿，
orphan 分支 `th` = 泰语稿，两版文件名一致（便于 `git diff main..th`）。

## 详细参考（**不自动注入**，做对应工作前先 Read，别凭记忆猜）

| 文件 | 内容 |
|---|---|
| `.workbuddy-ai/notes/ref-pipeline.md` | 脚本分工、链接/脚注、文风、多语言化、LLM 翻译四错、§ 两阶段流水线、译名白名单、外链改站内 |
| `.workbuddy-ai/notes/ref-site.md` | MDX/KaTeX 坑、`npm run check`、构建配方与环境限制、部署现状、图片 R2 与限高 |
| `.workbuddy-ai/notes/log-archive/INDEX.md` | 历史日志归档索引 |

## 必须时刻记住的硬约束

1. **`{expr}` 在 MDX `compile()` 不报错，只在运行时炸**（白屏 + `ReferenceError`）。
   「MDX COMPILE OK」不能当通过标准，必须运行时 eval（`r_mdxrun.mjs`）。
2. **标题里的裸 `<` / `>` 会让整站构建失败**——真凶是标题内的公式（`$D < 0$`）→ 写 `$D \lt 0$`。
3. **改完任何 .md 先跑 `npm run check`**（`scripts/prebuild_check.mjs`）。
   传路径**必须传目录**，传文件会静默输出「预检文件数: 0 / 全部通过」。
4. **wikitext 显示宽度必须保留**：`250px` → title `"w250"` → `<figure style={{"maxWidth":"250px"}}>`。
   MDX 里 `style="字符串"` SSR 会报错，必须传对象。取 `[[File:…]]` 要**括号配对扫描**。
5. **翻译带图条目必须先搬图再翻译**（`wikitext2md` → `wikiimg2r2.py` → `img2figure.py` → 翻译），
   译完中英两版 `grep -c '^<figure>'` 必须相等。
6. **公式必须三行**（`$$` 独占一行）；一行式 `$$x$$` 会被 remark-math 6 当 inlineMath。
7. **`docs/wow/` 占 99.8%**：改正文用 `npm run build:slim`（→ `build-slim/`），全量用 `build:big`。
   四个构建脚本都走 `scripts/build.mjs`，**别改回 `SKIP_WOW=1 docusaurus build` 的 POSIX
   前缀写法**（Windows 的 cmd 会当成命令名）。构建**必须** `dangerouslyDisableSandbox`；
   本环境 safe-delete shim 会拦对已存在 `build-slim/` 的批量删除 → 先手动删干净或换新 `--out-dir`。
8. **线上 `zh.chinapedia.org` 跑 `docusaurus start`（dev server）**，服务器上 `npm run build`
   对访客无效。修复见 `DEPLOY.md`。
9. **提交约定**：改动认为已完成就直接提交。凭证只放 `scripts/r2.local.json`（gitignore）。
10. **git commit message 别用 `-m` 带反引号**（会被 shell 吃掉），用 `git commit -F <file>`。
11. **写日志要幂等，且绝不和 commit 写进同一条命令**。沙箱升级重试会重跑整条命令：
    `>>` 会追加两次、`git commit` 会提交两次。
    → 改文件用 Edit/Write（不走 shell）；提交单独一条命令；
    必须 shell 追加时先 `grep -q '<块标题>' file || cat >> file`。
    → 判断提交是否成功**看 `git log`，不看退出码**（重试那次会报 `nothing to commit`）。
12. **`memory/` 目录每次会话整体注入，预算约 10 KB**：只放 **MEMORY.md + 当天日志**；
    细节放 `.workbuddy-ai/notes/`；过期日志 `mv` 到 `notes/log-archive/`（搬家不删）。
    超预算会**静默截断**（踩过两次）。写完顺手 `wc -c memory/*.md` 看一眼。
13. **正文里指向 `en.wikipedia.org/wiki/<条目>` 的链接，站内已有译好版本时改走站内相对链接**
    （`./黎曼ζ函数.md`，可带中文锚点）。工具 `scripts/wikilink_localize.py`；`md2zh.py` /
    `wiki2md.py` 已挂钩子，`npm run check` 第 7 项拦手工加的。
14. **要跟第三方库逐字一致时（如锚点 slug）别近似——读源码 + 差分测试。**
    踩过：用 `[^\w\s-]` 近似 github-slugger，**泰语元音/声调符号是 Mn 组合字符被当标点删掉**，
    锚点静默失效。真规则：删 P/S/C 类但保留 `-` `_`、不 trim、不合并空白、只有空格换 `-`。

## 环境

- 先 `export PATH="/c/Users/liruqi/.workbuddy-ai/binaries/node/versions/22.22.2-2:$PATH"`。
- npm 默认 registry 极慢，装包加 `--registry=https://registry.npmmirror.com`。
- 校验脚本在 `C:\Users\liruqi\.workbuddy-ai\binaries\node\workspace`（`r_mdxrun.mjs` 等）；
  快速渲染检查 `scratch/_render.mjs`，验 figure 用 `scratch/_figcheck.mjs`。
- 未解：`docs/math/孪生素数.md` 曾被外部还原成 HEAD（无钩子/stash 痕迹）→ 再出现先怀疑
  编辑器 / 同步工具。
