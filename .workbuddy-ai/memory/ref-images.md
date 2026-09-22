# 参考：图片搬运、figure 化与尺寸

> 本文件是 `.workbuddy-ai/memory/MEMORY.md` 的细节补充。碰图片 / 插图布局时读它。

## 必须搬到 Cloudflare R2（chped 桶）

`[[File:X|thumb|cap]]` 机械转换出来是 `…/wiki/File:X`（文件描述页 HTML，必裂图）；
thumb.wikimedia.org 还反盗链。`scripts/wikiimg2r2.py` 一键做完：Commons API 查真实地址 →
下载 → AWS SigV4 PUT → 改写成
`https://pub-275e30003c354ac0862cc9839e0f952a.r2.dev/docs/math/X.png`。

- 凭证 `scripts/r2.local.json`（**gitignore 不提交**）；prod 用环境变量
  `R2_ENDPOINT / R2_BUCKET / R2_PUBLIC_BASE / R2_ACCESS_KEY / R2_SECRET_KEY`。
- 脚本**不依赖 boto3**，自实现 SigV4。映射缓存 `scripts/wikiimg-map.json` 会提交。
- 坑：主机名 `commons.wikimedia.org`；**SVG/PDF 取 `thumburl`**（渲染好的 PNG），
  **GIF 反过来取原图**；R2 路径风格 + region `auto` + canonical URI 不做归一化；
  网络随机 RST，上传/校验都要重试，**校验用 GET 比字节数，别信单次 HEAD**。
- `wikitext2md.file_url()` 已改成 `Special:FilePath/<name>?width=1000`，没跑 R2 也能显示。

## img2figure.py

把 markdown 图片改写成 `<figure>` + `<img>` + `<figcaption>`（图注只躺在 alt 里看不见，
且连续图片会被合并进同一段落）。**MDX 要求 JSX 块子内容用空行隔开**才会当 markdown 解析，
所以 figure/figcaption 内侧留空行；alt 用 LaTeX→Unicode 降级后的纯文本。

## 插图尺寸：R2 原图经常超高，必须限高

维基把图放右侧窄栏（260/210px），搬进整栏（~750px）就爆（`Riemann-Zeta-Detail.png`
1280×2959 → 铺开 1734px 高，吃两屏）。查尺寸不用下全图：PNG 读 IHDR `d[16:24]`；
JPEG 扫 `FFC0/FFC1/FFC2`（偏移 +5 大端 `height,width`）；GIF `d[6:10]` 小端。带浏览器 UA。
批量探测用 `scripts/check_r2_images.py`（`SUPER_TALL` ratio>1.5 / `TALL` ratio>1.0，
`--docs` `--limit` `--tall-only`）。

`src/css/custom.css`：

- `.markdown figure img { max-height: 420px; width: auto }` —— 全局兜底（限高时宽度按比例收缩不变形）。
- `.figure-row` —— 多图并排（flex+wrap，`> figure { flex:1 1 240px; max-width:340px }`，
  行内限高 380px），窄屏自动回退。用法：几个 `<figure>` 包进 `<div className="figure-row">`。
- `figure className="figure-tall"` —— 逃生口，限高 620px。竖版大图（论文首页扫描件 500×833）用。

容器类名是 `theme-doc-markdown markdown`（`grep 'class="markdown"'` 会漏，要 grep 全串）。

## wikitext 显示宽度要保留（以前被丢掉，图片按整栏铺开）

- `wikitext2md.extract_display_width()` 把宽度编码成 markdown 图片 title `"w250"`；
  `FILE_OPTION_RE` 要能匹配 `NxMpx`，否则尺寸参数漏进图注。
- `img2figure.py` 解析 `wN` → `<figure style={{"maxWidth": "Npx"}}>`。
  **MDX 里 `style="字符串"` 会在 SSR 报 `The style prop expects a mapping…`，必须传对象。**
- 已转好的文章用 `img2figure.py --from-wikitext <wikitext 文件或 URL>` 回填
  （幂等，已有 `style=` 跳过），靠 `wikiimg-map.json` 把 R2 URL 反查回 File 名。
- **裸 `thumb` / 裸 `upright` 不加约束**：折算 220px 反而更小，交给 max-height 兜底。
- 取 `[[File:…]]` 必须**括号配对扫描**，不能用 `\|[^\[\]]*`：图注里常带 `[[domain coloring]]`、
  `{{cite web|url=…}}`，正则被内部 `[` 卡住，整条匹配不上（实测漏掉 `Cplot zeta.svg` 的 250px）。
