# 线上部署修复指南

> 本文件随仓库提交，方便在服务器上直接查阅。原先放在 gitignored 的 `scratch/` 里。

## 问题诊断

当前 `zh.chinapedia.org` 跑的是 `docusaurus start`（webpack dev server），
不是正式静态构建产物。证据：

- 所有 URL 返回同一个 2110 字节 SPA 外壳
- HTML 引用的是未加哈希的 `/styles.css`、`/main.js`、`/runtime~main.js`
- 响应头 `x-powered-by: Express`

这意味着服务器上的 `npm run build` 对访客没有影响。

## 修复步骤（在服务器上执行）

### 1. 拉取最新代码

```bash
cd ~/zh.chinapedia  # 或实际路径
git pull origin main
```

### 2. 正式构建（混合构建，默认）

```bash
# 先确认 node 在 PATH
export PATH="/opt/homebrew/bin:$PATH"  # 或你的 node 路径

# 子模块必须存在，否则 render_wow.mjs 会直接报错退出
git submodule update --init docs/wow/capycraft

npm run build
```

产物在 `build/`：主站（约 63 页）+ `build/wiki/wow/capycraft/**.html`（9710 篇）。
两步合计约 5 分钟、峰值内存 ~100 MB，可在 Cloudflare Workers Builds（20 分钟 / 8 GB）内跑完。

**为什么不再全量编译**：Docusaurus 会把 9711 篇 MDX 全塞进一个 webpack 模块图并单进程
SSG，实测 12 分钟就吃掉 4 GB 堆 OOM；全量构建本地约 client 24m + server 7m，
CF 的 20 分钟上限无论如何都不够。混合构建让主站走 `SKIP_WOW=1`，这 9710 篇由
`scripts/render_wow.mjs` 逐文件流式渲染（依赖 `marked`），内存恒定。
这些页面复用主站 `<head>` 里的 CSS，但**不加载 Docusaurus 的 JS**（路由清单里没有它们，
hydration 会白屏），因此没有 navbar / sidebar / 客户端路由 / 搜索。

因为 `docs/wow/**` 被整体排除，Docusaurus 连 `docs/wow/_category_.json` 里的
generated-index（slug `wow`）也不再生成，所以 `render_wow.mjs` 会一并补出目录层：
`/wiki/wow/`、`/wiki/wow/turtle`（capycraft 之外的 `turtle.md`），以及
`/wiki/wow/capycraft/` 和 `item/ npc/ quest/ set/ dungeon/ dungeon/ent/ worldboss/ transport/`
各分区的 `index.html`（按标题列出全部条目，item 的 8421 条单页分栏展示）。
navbar 里的「魔兽世界」用 `href` 指向 `/wiki/wow/`——这些页面不在 Docusaurus 路由表里，
用 `to` 会被客户端路由接管而拿不到静态页。

可用的构建脚本：

| 命令 | 行为 |
|---|---|
| `npm run build` | 混合构建，产物 `build/`，CI 与日常发布都用这个 |
| `npm run build:full` | 纯 Docusaurus 全量构建（会 OOM / 很慢，仅本地排查用） |
| `npm run build:slim` | 只编主站，产物 `build-slim/`，不含 wow 页 |
| `npm run build:big` | 全量构建并追加 `--max-old-space-size=8192`（Mac Mini 需要） |
| `npm run build:faster` | 全量 + Rspack/SWC，需先装 `@docusaurus/faster` |

`build` / `build:full` / `build:slim` / `build:big` / `build:faster` 都走 `scripts/build.mjs`，
由 Node 设好环境变量再启动 docusaurus —— 因为 npm 在 Windows 上用 cmd.exe 跑 scripts，
`SKIP_WOW=1 docusaurus build` 这种 POSIX 前缀会被 cmd 当成命令名而直接失败。
`--skip-wow` 与 `--slim` 的区别是前者输出到默认 `build/`，后者输出到 `build-slim/`。

### Cloudflare Workers Builds

`wrangler.jsonc` 把 `assets.directory` 指向 `./build`，控制台的 Build command 保持
`npm run build`、Deploy command 保持 `npx wrangler deploy` 即可。
`name` 必须与控制台里的 Worker 名一致；`html_handling=auto-trailing-slash` 会把
`/wiki/wow/...` 映射到对应的 `.html` 文件。

### 3. 停止现有的 dev server

找到当前运行的 dev server 进程：

```bash
ps aux | grep docusaurus
# 或
lsof -i :3000  # 如果 dev server 在 3000 端口
```

杀掉它：

```bash
kill -9 <PID>
```

### 4. 用正式静态服务器替换

**方案 A：docusaurus serve（最简单）**

```bash
npx docusaurus serve --port 3000 --host 0.0.0.0
```

> 注意：`docusaurus serve` 3.10 **没有 `--out-dir` 选项**，默认 serve 当前目录的 `build/`。
> 确保你在项目根目录执行。

**方案 B：用 nginx 直接 serve 静态文件（推荐）**

nginx 配置示例：

```nginx
server {
    listen 80;
    server_name zh.chinapedia.org;

    root /path/to/zh.chinapedia/build;
    index index.html;

    location / {
        try_files $uri $uri.html $uri/index.html /index.html;
    }

    # Docusaurus 的静态资源带 hash，可以长期缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

> `try_files $uri $uri.html` 让 `/wiki/math/黎曼ζ函数` 自动匹配
> `build/wiki/math/黎曼ζ函数.html`，不需要客户端 fallback。
> 产物布局是 `build/wiki/<分类>/<条目>.html`（是**文件**，不是目录）。

### 5. 持久化（systemd / pm2）

如果用 **方案 A**（docusaurus serve），建议用 pm2 托管：

```bash
npm install -g pm2
pm2 start "npx docusaurus serve --port 3000 --host 0.0.0.0" --name zh-chinapedia
pm2 save
pm2 startup
```

如果用 **方案 B**（nginx），确保 nginx 随系统启动即可。

## 验证

修复后 curl 应该能看到：

```bash
curl -s https://zh.chinapedia.org/wiki/math/黎曼ζ函数 | grep -o 'figure-row' | wc -l
# 期望输出：1（或更多）

curl -s https://zh.chinapedia.org/wiki/math/黎曼ζ函数 | wc -c
# 期望输出：远大于 2110（包含完整页面内容）
```

CSS 文件名应该带 hash：

```bash
curl -s https://zh.chinapedia.org/ | grep -o 'styles\.[a-z0-9]*\.css'
# 期望输出：styles.xxxxxxxx.css
```

插图的 `max-width` 也应该出现（这是 wikitext 宽度保留链路是否生效的判据）：

```bash
curl -s https://zh.chinapedia.org/wiki/math/黎曼ζ函数 | grep -o 'figure style="max-width:[0-9]*px"' | sort -u
# 期望：250px / 200px / 308px / 300px
```

## 背景：CI 在 Cloudflare 侧

仓库无 `.github/workflows`；Cloudflare Workers Builds 监听 `main`，push 会触发
`npm run build` + `npx wrangler deploy`。所以"改了 CSS 线上没变化"时，
先看 Build history 有没有失败（例如子模块没拉到、堆 OOM），再查 `build/` 的 mtime
是不是比源码旧——而不是怀疑缓存。
