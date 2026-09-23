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

### 2. 正式构建

```bash
# 先确认 node 在 PATH
export PATH="/opt/homebrew/bin:$PATH"  # 或你的 node 路径

# 构建（Mac Mini 需要 8192 MB 堆；4096 会 OOM）
npm run build:big
```

构建成功后产物在 `build/` 目录。

> 全量约 9711 页，client ~24m + server ~7m。若只想验证正文改动，
> 用 `npm run build:slim` 先把 `build-slim/` 跑出来（跳过 `docs/wow/`）。

`build` / `build:slim` / `build:big` / `build:faster` 都走 `scripts/build.mjs`，
由 Node 设好环境变量再启动 docusaurus —— 因为 npm 在 Windows 上用 cmd.exe 跑 scripts，
`SKIP_WOW=1 docusaurus build` 这种 POSIX 前缀会被 cmd 当成命令名而直接失败。
`build:big` 只是**追加** `--max-old-space-size=8192`，你自己设了 `NODE_OPTIONS` 就尊重你的。

> `build:faster` 需要先装 `@docusaurus/faster`（Rspack + SWC），没装会直接报错退出。

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

## 背景：站点没有 CI

仓库无 `.github/workflows`，push 不会自动部署。所以"改了 CSS 线上没变化"时，
先查 `build/` 的 mtime 是不是比源码旧——而不是怀疑缓存。
