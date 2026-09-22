# 参考：条目生成与翻译流水线

> 本文件是 `.workbuddy-ai/memory/MEMORY.md` 的细节补充。做条目生成 / 翻译相关工作时读它。

## 脚本分工

- `scripts/wiki2md.py`：非中文维基 wikitext → LLM 翻译 → `docs/{分类}/{条目}.md`。
- `scripts/wikitext2md.py`：**纯机械**转换，不调 LLM。用于英文镜像 `D:\SRC\Z\en.chinapedia\`，
  或作翻译前的干净中间产物。`--report` 列未识别模板。
- `scripts/md2zh.py`：只做英→中翻译。默认 `reasoning_effort=none`、`--jobs 4`、`--state` 断点续译
  （Riemann zeta 220 块 ≈ 10 min）。
- 公式默认 KaTeX（`$…$` / `$$…$$`）；`--no-katex` 退回行内代码。KaTeX 模式自动跑
  `escape_dollar_in_urls()` + `fix_github_math()`。

## 链接与脚注

- 维基链接保持行内；**其他外链改 GFM 脚注**（同一 URL 复用同一编号）。批量
  `scripts/md2footnotes.py`（幂等、保 CRLF；默认跳过本身就是链接清单的章节，`--all` 关掉）。
- 正文 `<ref>` 残留的 `[[7]](url)` 也是外链，同样转脚注——往往比 `[文字](url)` 更多。
- 脚注标记后紧跟 `[` 或 `$` 要补空格，否则 `[^1]$x$` GitHub 不渲染。
- **相邻脚注标记之间恰好一个空格**（`[^16][^17]` → `[^16] [^17]`）。统一由
  `scripts/fix_footnote_spacing.py` 负责：`fix_spacing(text)` 供其他脚本 import，
  CLI 支持 `--dry-run` / `--check`（退出码 1，给 CI）。
  - 用**前瞻**正则，链式标记 `[^55][^56][^57]` 才能一次全拆开。成对正则
    （`\s*\[\^([^\]]+)\]\s*\[\^`）只拆前两个，三连会留下 `[^56][^57]` 不修——
    `md2footnotes.py` 原来就是这么写的，已换成 `fix_spacing()`。
  - 空白用 `[ \t]*` 不用 `\s*`：否则会把相邻两行（很可能是脚注定义）粘到一起。
    定义行是 `[^n]:`，`]` 后跟 `:`，天然不命中。
  - **两个空格的来源**：`notes2footnotes.py` 把 `［1］［2］` 转 `[^n]` 时，
    前一个的 post-space 和后一个的 pre-space 各补一次 → `[^1]  [^2]`。
    已在 `body = MARK_RE.sub(repl, body)` 之后加 `fix_spacing(body)` 收敛。
  - **生成端也要挂**，否则重新生成又会出现：`wikitext2md.py` 第 9 步还原脚注标记
    （连续两个 `<ref>` → `[^1][^2]`）之后加了 `fix_spacing(body)`；
    `md2footnotes.py` 原来的成对正则换成 `fix_spacing()`。
  - `prebuild_check.mjs` 已加对应检查项「脚注标记间距不规范」，改完必跑 `npm run check`。
- `remark-gfm` 不用配，`@docusaurus/mdx-loader` 默认启用。
- `<ref>` → `［n］` 是纯文本点不动。用 `scripts/notes2footnotes.py` 接成真脚注
  （删 `## 注释` 节 → `［n］`→`[^n]` → 文末补定义，已有定义顺延编号）。
- **未被引用的脚注定义不渲染**：冗余一条无害，但若整节来源列表全靠它撑着，整节会在页面消失。
  `npm run check` 能扫。
- 中文稿里的字面 `[^n]`（翻译残留）要删。

## 中文条目文风

- 开头：`**词条名**（英语：English name），也称为**别名1**、**别名2**，是指……`
- 不直译只在英文语境成立的句子；长从句拆散重排。
- 正文里的外文原文引文（德/法/拉丁）一律删，只留中文译文；参考文献里的外文标题保留不译。

## 自托管 Qwen（`https://lms.thaiwen.com/v1`，LM Studio）必开两个设置

模型 `qwen/qwen3.5-9b` 强制思维链（一句话想 150s+ 且零输出）。两条一起加才有救
（`wiki2md.llm_chat` 已内置）：

1. **`stream: true`** —— 前面挂 Cloudflare，源站 ~100s 不出首字节返回 524；流式 2s 就吐 SSE。
2. **`reasoning_effort: "none"`** —— 唯一能关思维链的参数（2.0s 出首字，13.2s 出全文）。

**无效（都试过）**：`chat_template_kwargs:{enable_thinking:false}`、`thinking:{type:"disabled"}`、
`reasoning:{enabled:false}`、顶层 `enable_thinking`、`/no_think`、`reasoning_effort:"minimal"/"low"`。
另：**必须带浏览器 UA**（urllib 默认 UA 被 Cloudflare 403）；**并发 3–4 路快 3 倍**。

## md2zh.py：LLM 翻译的四个必防错误

1. URL 里 `_` 被改成空格 → 送译前 URL 换 `§U0§` 占位符。
2. 模型把行内链接改写成脚注还自己编号（撞号）→ 脚注标记换 `§F3§`，译完 `fix_footnotes()`
   逐行对账，译文里凭空出现的 `[^n]:` 整行丢。占位符用 `§…§` **不要** `\x01`（传输中被吃掉）。
3. 改标题层级 → 以原文 `#` 个数为准强行纠正。
4. **最严重：标题单独成块 → 整节内容全是编的。** 空行被当 verbatim 块，标题行自成 chunk，
   模型会"补全" 27–57 行虚构内容。对策：单行标题走 `HEADING_SYSTEM` 只取一行；
   **输出行数必须等于输入行数**（不等重试，最终逐行兜底）；缓存命中同样要求行数严格相等；
   收尾丢弃非逐字复制的 `[^n]:` 定义行。
   → **「输入行数 vs 输出行数」是最有效的幻觉探测器**。

`_chat_stream` 必须有总时限（`urlopen(timeout=)` 只管单次 recv，心跳块能把连接挂 7.5h）：
`deadline = time.time() + timeout`。

## 翻译带图的条目：先搬图再翻译

`wiki2md.py` 翻译阶段会把 `[[File:…]]` 连同图注一起丢掉。正确顺序：`wikitext2md` →
`wikiimg2r2.py` → `img2figure.py` → 再翻译。译完 `grep -c '^<figure>'` 对中英两版，
数量必须相等；中英脚注编号一致。

## 人工翻译长条目：§ 标记两阶段流水线

1. `scratch/prep_*.py` 把 wikitext 压成中间表示，链接/公式/引用/脚注换成标记：
   `§L{Target|显示}§`、`§M{行内公式}§`、`§D{块公式}§`、`§H{作者|年}§`、`§S{作者|年|页}§`、
   `§REF{n}§`、`§X{OEIS id}§`。人工只译纯散文。
2. `scratch/build_*.py` 展开回 Markdown，复用 `wiki2md.escape_dollar_in_urls()` + `fix_github_math()`。

复用过的坑：

- **wikitext 标题层级**：`== X ==` → `## X`（`"#" * len(m.group(1))`，**不要 +1**）。
- **`{{harvs}}` 取参**：先剥外层 `{{ }}`，再**只在深度 0** 按 `|` 切分；深度只由 `{`/`}` 计数
  （早期把 `|` 也算进深度 → 引用全渲染成空）。
- 列表用 `1.` 不用 `#`（行首 `#` 会被当 H1）。
- 中文引号：ASCII `"` 前后是中文时批量换 `“”`。
- `（英语：X）` 前先占位保护再补中英文空格，否则 CJK 空格规则会插进括号里。
- 链接显示文字不要以 `$…$` 开头，改成 `§L{Target|L 函数}§`。
