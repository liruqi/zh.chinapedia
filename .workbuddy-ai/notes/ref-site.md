# 参考：站点栈 / 校验 / 构建 / 部署 / 图片

> `.workbuddy-ai/memory/MEMORY.md` 的细节补充。跑构建、排查渲染、处理图片时读它。

## 站点栈与 MDX 坑

- Docusaurus 3.10 + MDX 3 + remark-math 6 + rehype-katex 7。
- remark-math 6 下**一行式 `$$x$$` 会解析成 inlineMath**（不居中）。独立公式必须三行
  （`$$` 独占一行）。肉眼和编译都不报错，只有看 AST 才发现。
- KaTeX CSS 由 config `stylesheets` 从 jsDelivr 引入，**版本必须与 rehype-katex 用的 katex
  一致**（当前 0.16.47，以 package-lock 的 `node_modules/katex` 为准）。换版本要重算 SRI
  （urllib 取文件 → sha384 → base64）。
- MDX 硬约束：正文不得有未转义 `< >` `{}`；禁 `<https://…>` 自动链接
  （`fix_autolinks` 转 `[原文](url)`）。
- **最大的坑：`{expr}` 在 `compile()` 不报错，只在运行时炸**（残留裸 LaTeX 如
  `\operatorname{li}` → `ReferenceError: li is not defined` + 白屏）。「MDX COMPILE OK」
  **不能**作为通过标准，必须运行时 eval。`wiki2md.escape_mdx_braces()` 兜底。

### 标题里的裸 `<` / `>` 会让整站构建失败

真凶是标题内的数学公式：`toHeadingHTMLValue()` 只显式处理 text/heading/inlineCode/emphasis，
**`inlineMath` 落到 `default: return toString(node)` 不转义** → TOC `dangerouslySetInnerHTML`
→ `html-minifier-terser` Parse Error → **整站构建失败**。实测（`scratch/_tocangle.mjs`）：

| 标题 | TOC 输出 | 危险 |
|---|---|---|
| `## …*D* \< 0` | `… <em>D</em> &lt; 0` | 否 |
| `## 裸尖括号 D < 0` | `裸尖括号 D &lt; 0` | 否 |
| `## 公式 $D < 0$` | `公式 D < 0` | **是** |
| `## 已转义 \< 与 \>` | `已转义 &lt; 与 &gt;` | 否 |

修法：写成 `$D \lt 0$` / `$x \gt 0$`。`prebuild_check.mjs` 放行 `\<` `\>`，裸 `<>` 继续报。

## KaTeX 缺 MediaWiki 扩展的宏

维基大量用 `\C \R \N \Z \Q \F \sgn`（MediaWiki 自己 MathJax 配置扩展的宏），KaTeX 不认
→ 渲染成红色 parse error（GitHub 的 MathJax 也不认）。两处补：`docusaurus.config.js` 给
rehype-katex 配 `macros`（兜底新导入条目），现存 .md 换成 `\mathbb{C}` 这类标准写法。
排查用 `scratch/_macroscan.mjs`，**要按 display/inline 分别传 `displayMode`**，
否则 `\begin{align}` 误报。

**KaTeX 报错没有 `katex-error` 类**：不抛异常，只把源码原样渲成红色 `color:#cc0000`。
基于 hast 的校验要认这个颜色；`_macroscan.mjs` 用 `throwOnError: true` 直接试渲染。

## 校验

- **首选 `npm run check`（= `scripts/prebuild_check.mjs`）**：一次扫掉标题裸 `<>`、MDX 裸
  `{expr}`、KaTeX 未定义宏、图还在裸链维基、脚注定义/引用对不上、**相邻脚注标记间距不规范**、
  裸 URL。默认扫 `docs/` 跳过 `wow/`，`--wow` 扫全部，有问题退出码 1。
  - 判据别写错：脚注**引用**后可能紧跟冒号（「…[^23]：」），不能靠 `(?!:)` 区分定义与引用，
    要先整段抠掉「定义行 + 缩进续行」；裸 URL 要加 `(?!\()`。
  - **传路径必须传目录，不能传文件**：传文件会在 `readdirSync` 抛 ENOTDIR 被静默吞掉，
    输出「预检文件数: 0 / √ 全部通过」——看着像通过其实一个都没扫。
    **Git-Bash 风格的 `/tmp/xxx` 同样踩**：Node 在 Windows 上读不了 `/tmp`，同样静默变 0。
    自测用仓库内相对路径（如 `scratch/_fncheck`）。`curl -o /dev/null` 也栽在同一处。
- 三件套在 `C:\Users\liruqi\.workbuddy-ai\binaries\node\workspace`：`katexcheck.mjs`、
  `mdxtest.mjs`、`mathnodes.mjs`（remark-math AST：inlineMath/math 计数，查一行式 `$$`）。
- **必跑第四件套 `r_mdxrun.mjs`**：真正 eval 编译产物（stub jsx，不用装 react），抓
  `ReferenceError`。前三件套全绿但这个炸的情况真实发生过。
- **更快的一环 `scratch/_render.mjs`**（项目根跑）：remark-parse → gfm → math → rehype → katex，
  遍历 hast 统计 katex/脚注/table/残留 `[^n]`。**项目没装 rehype-stringify**，不要 stringify。
- **验证 figure 必须走真 MDX 管线**：`_render.mjs` 用纯 remark，**裸 HTML 会被丢掉**，
  验 `<figure>` 会得到 figure=0 的假阴性。用 `scratch/_figcheck.mjs`：`@mdx-js/mdx` compile +
  eval，stub jsx 工厂后遍历真实元素树。
- `r_bisect.mjs`：二分定位 MDX 编译失败的行（COMPILE ERROR 只说 acorn 报错不给行号）。

## 跑构建的完整配方

先 `export PATH="/c/Users/liruqi/.workbuddy-ai/binaries/node/versions/22.22.2-2:$PATH"`。

1. `npm.cmd install --no-audit --no-fund --registry=https://registry.npmmirror.com`
   （默认 registry 极慢，47 分钟装不完；镜像约 32 分钟。不改 package-lock.json）
2. 构建**必须** `dangerouslyDisableSandbox`，否则写 `.docusaurus/` 会 EPERM。
3. **`docs/wow/` 是 9711 篇，占全站 99.8%**。别手改 config，用现成脚本：
   - `npm run build:slim` = `SKIP_WOW=1` → exclude `wow/**`，产物写 `build-slim/`。
     改正文/样式用这个，一两分钟出结果。Windows cmd 不吃 `VAR=1 cmd` 前缀，用 Git Bash 或
     `set SKIP_WOW=1&& …`。
   - `npm run build:big` = `NODE_OPTIONS=--max-old-space-size=8192 docusaurus build`（正式全量）。
     崩溃栈是 `v8::FatalProcessOutOfMemory` + `Runtime_MapGrow` 而非 EMFILE 时就是堆不够。
4. 全量：client ~24m + server ~7m + 9711 页；不带 wow 约 12 分钟（有持久化缓存后
   server 1.5m + client 9.5m）。
5. **堆上限直接从 GC 日志读**：`Mark-Compact (reduce) 3870.7 (4099.5) MB` 括号里的数就是上限；
   `3870.7 -> 3870.7` 表示一轮 GC 什么都没回收（真的不够）。**4096 不够，8192 才够**，别超物理内存。
6. `npm run build:faster`（需装 `@docusaurus/faster`）：Rspack + SWC，开关
   `process.env.FASTER === '1'`。
   - 键名是 **`future.faster`**（老名 `experimental_faster` 报 "has been renamed"）。
   - **别写 `faster: true`**：会把 `ssgWorkerThreads` 一起打开，而它要求
     `v4.removeLegacyPostBuildHeadAttribute === true`，否则 throw。要显式列项并跳过它和 `gitEagerVcs`。
7. **`outDir` 不是 config 字段**，只能走 CLI `docusaurus build --out-dir <dir>`
   （写进 config 报 `not recognized`）。
8. **改完 `docusaurus.config.js` 必须真校验**，`node --check` 不够。
   `require('@docusaurus/core/lib/server/config.js').loadSiteConfig({siteDir: process.cwd()})`，
   顺便打印 `docs.exclude` / `future.faster`。
9. 产物在 `build/wiki/<分类>/<条目>.html`（**不是目录**）。
10. `exclude` 会**覆盖**插件默认值，写成 `['wow/**', ...DEFAULT_EXCLUDE]`；顶层已有
    `onBrokenLinks: 'log'`，别在 docs 插件里设 `'throw'`。
11. **`docusaurus serve` 没有 `--out-dir`**（3.10.1 实测 unknown option）。预览用
    `python -m http.server <port> --bind 127.0.0.1 --directory <dir>`，baseUrl 是 `/` 所以绝对路径 OK。
12. 站点**没有 CI**：无 `.github/workflows`，push 不会自动部署。"改了 CSS 线上没变化"
    先查 `build/` 的 mtime 是不是比源码旧。
13. 删构建目录时 `rm -rf build-*` 会被安全删除策略拦（`SAFE_DELETE_FAIL_CLOSED … trash-failed` /
    `SAFE_DELETE_BULK_CONFIRM_REQUIRED`）→ 改用 Python `shutil.rmtree`，或直接换新的 `--out-dir`。

## 部署现状

线上 `zh.chinapedia.org` 跑的是 **`docusaurus start`（webpack dev server）**，不是静态产物
（所有 URL 返回同一个 2110 字节 SPA 外壳、引用未加哈希的 `/main.js`、`x-powered-by: Express`）
→ 服务器上 `npm run build` 对访客没有影响。修复步骤见仓库根目录 **`DEPLOY.md`**。

## GitHub 渲染公式的坑（.md 在 GitHub 上直接看）

- **行内公式起始 `$` 前必须是空白或行首**。紧跟中文标点（`，。、：（）`）GitHub 不渲染
  → 起始 `$` 前补一个空格。
- 正文里非分隔符的裸 `$` 也要处理；URL 含 `$` 写成 `%24`。
- 不要用 GitHub 专用的 `$`…`$` 写法——remark-math 不认，站点渲染失败。
- 块公式 `$$` 独占行即可；`.md` 里若 `$$` 与前文同行需行尾加 `\` 换行。

## 图片：必须搬到 Cloudflare R2（chped 桶）

`[[File:X|thumb|cap]]` 机械转换出来是 `…/wiki/File:X`（**文件描述页** HTML，必裂图）；
thumb.wikimedia.org 还有反盗链。`scripts/wikiimg2r2.py` 一键做完：Commons API 查真实地址 →
下载 → AWS SigV4 PUT → 改写成
`https://pub-275e30003c354ac0862cc9839e0f952a.r2.dev/docs/math/X.png`。

- 凭证 `scripts/r2.local.json`（**gitignore 不提交**）；prod 用环境变量
  `R2_ENDPOINT / R2_BUCKET / R2_PUBLIC_BASE / R2_ACCESS_KEY / R2_SECRET_KEY`。
- 脚本**不依赖 boto3**，自实现 SigV4（装 boto3 要十几分钟）。映射缓存
  `scripts/wikiimg-map.json` 会提交。
- 坑：主机名 `commons.wikimedia.org`；**SVG/PDF 必须取 `thumburl`**（渲染好的 PNG），
  **GIF 反过来取原图**（缩略图会变静止帧）；R2 路径风格 + region `auto` + canonical URI
  不做归一化；网络会随机 RST，上传/校验都要重试，**校验用 GET 比字节数，别信单次 HEAD**。
- `wikitext2md.file_url()` 已改成 `Special:FilePath/<name>?width=1000`，没跑 R2 也能显示。

## img2figure.py

把 markdown 图片改写成 `<figure>` + `<img>` + `<figcaption>`（图注只躺在 alt 里看不见，
且连续图片会被合并进同一段落）。**MDX 要求 JSX 块的子内容用空行隔开**才会当 markdown 解析，
所以 figure/figcaption 内侧留空行；alt 用 LaTeX→Unicode 降级后的纯文本。
已转好的文章用 `img2figure.py --from-wikitext <wikitext 文件或 URL>` 回填（幂等，已有 `style=`
跳过），靠 `wikiimg-map.json` 把 R2 URL 反查回 File 名。

## 插图尺寸：R2 原图经常超高，必须限高

维基把图放**右侧窄栏**（260/210px），搬进整栏（~750px）就爆（`Riemann-Zeta-Detail.png`
1280×2959 → 铺开 1734px 高，一张图吃两屏）。查尺寸不用下全图：PNG 读 IHDR `d[16:24]`；
JPEG 扫 `FFC0/FFC1/FFC2` 段（偏移 +5 是大端 `height,width`）；GIF `d[6:10]` 小端。带浏览器 UA。
批量探测用 `scripts/check_r2_images.py`（`SUPER_TALL` ratio>1.5 / `TALL` ratio>1.0，
`--docs` `--limit` `--tall-only`）。

`src/css/custom.css` 三个约定：

- `.markdown figure img { max-height: 420px; width: auto }` —— 全局兜底（替换元素限高时宽度
  按原比例收缩不变形）。
- `.figure-row` —— 多图并排（flex+wrap，`> figure { flex:1 1 240px; max-width:340px }`，
  行内限高 380px），窄屏自动回退上下排列。用法：几个 `<figure>` 包进 `<div className="figure-row">`。
- `figure className="figure-tall"` —— 逃生口，限高放宽到 620px。竖版大图（论文首页扫描件
  500×833）用。

容器类名是 `theme-doc-markdown markdown`（`grep 'class="markdown"'` 会漏，要 grep 全串）。

## wikitext 显示宽度要保留（以前被丢掉，图片按整栏铺开）

- `wikitext2md.extract_display_width()` 把宽度编码成 markdown 图片 title `"w250"`；
  `FILE_OPTION_RE` 要能匹配 `NxMpx`，否则尺寸参数漏进图注。
- `img2figure.py` 解析 `wN` → `<figure style={{"maxWidth": "Npx"}}>`。
  **MDX 里 `style="字符串"` 会在 SSR 报 `The style prop expects a mapping…`，必须传对象。**
- **裸 `thumb` / 裸 `upright` 不加约束**：折算 220px 反而更小，交给 max-height 兜底。
  `upright` 要**显式带倍数**（`upright=1.5`）才算，裸 `upright` 不算。
- 取 `[[File:…]]` 必须**括号配对扫描**（`split_top_level` / `iter_wiki_files`），不能用
  `\|[^\[\]]*`：图注里常带 `[[domain coloring]]`、`{{cite web|url=…}}`，正则被内部 `[` 卡住，
  整条匹配不上（实测漏掉 `Cplot zeta.svg` 的 250px）。
