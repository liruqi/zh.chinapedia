# 参考：专有名词译名（wikiterm.py）

> 本文件是 `.workbuddy-ai/memory/MEMORY.md` 的细节补充。翻译新条目、补译人名时读它。

## 原则

权威译名 = 中文维基条目名。**查不到就保留英文，绝不生造**
（`Tikao Tatsuzawa` 猜"立川"是错的，已回退）。

`scripts/wikiterm.py`（en.wikipedia `prop=langlinks&lllang=zh` → `scripts/wiki-zh-terms.json`，已提交）：

```
python scripts/wikiterm.py "Riemann xi function"
python scripts/wikiterm.py --scan docs/math/ --glossary   # 抽 .md 里所有维基链接
python scripts/wikiterm.py --no-wikidata                  # 严格模式
python scripts/wikiterm.py --fix-cache                    # 去重 + 重做简繁转换
python scripts/wikiterm.py --verify-people                # 回查人名白名单
```

`md2zh.py --terms` 按 chunk 注入命中词条（标题/小节/正文三条路径，匹配做了归一化）。

**三级兜底，质量递减**：langlinks（可靠）> Wikidata 中文标签（机翻多：
`Andrew Granville → 安德鲁·关维`）> 没有。

## 人名白名单

中文间隔号「·」是音译人名标志，术语名不会带。原先 `load_terms()` 把带「·」的**全丢**，
连权威译名一起丢（正文留下没译的 `Helmut Hasse`，中文维基有条目「赫尔穆特·哈斯」）。

现在：`--verify-people` 把带「·」的回查 langlinks，确有中文条目的写进
`scripts/wiki-zh-terms-people.json`（56 条保留 32 条），`md2zh.load_terms()` 只放行白名单。
**新增人名条目后记得重跑 `--verify-people`。**

## 坑

- `langlinks()` / `wikidata_zh()` 早期把 `normalized`+`redirects` 做成**反查表**
  （最终标题 → 请求名），两个请求名跳到同一页面时互相覆盖（`Carl Siegel` / `Carl Ludwig Siegel`
  都指向同一 en 条目），其中一个永远查不到 → 误判「没有中文条目」。
  必须**正向映射**（请求名 → 最终标题）再沿链展开。
- **简繁转换用 `zh.wikipedia.org` 的 `action=parse&variant=zh-cn`，必须分批（40 条）**，
  一次几百行整批退回原文。`converttitles` 靠不住。
- **维基 API 会 429**：限速 ≥1.2s/次 + 按 `Retry-After` 退避。
- **别在 `npm run build` 期间查**：网络同时跑构建必 RST（WinError 10054）。
- 缓存键**按小写去重**（维基标题大小写等价）；变体里留"句子式大小写"那个。
- 改完用中英混排正则扫残留：`[\u4e00-\u9fff]\s?([A-Za-z][A-Za-z\-']{2,})\s?[\u4e00-\u9fff]`
