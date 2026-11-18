#!/usr/bin/env node
// 把 docs/wow/capycraft 的 9710 篇数据文档渲染成静态 HTML，直接写进 Docusaurus 产物目录。
//
// 为什么要绕开 Docusaurus
// ------------------------
// Docusaurus 会把全部 MDX 塞进一个 webpack 模块图，再在单进程里做全量 SSG。
// 9711 篇 wow 文档让 Node 堆涨到 4 GB 以上（Cloudflare Workers Builds 只有 8 GB 内存 /
// 20 分钟），实测 12 分钟就 OOM。而这些文档是**独立分区**：11497 个内部链接里
// 没有一个指向 capycraft 子树之外，且不含 frontmatter / MDX / 公式 / 嵌套列表。
// 于是主站用 SKIP_WOW=1 编译（63 页），这 9710 篇逐文件流式渲染，内存恒定在 ~100 MB。
//
// 用法
// ----
//     node scripts/render_wow.mjs [产物目录]      # 默认 build
//
// 必须在 Docusaurus 构建之后运行：产物目录里要有 index.html 和 assets/css/styles.*.css。
// 本脚本是幂等的（sitemap 追加前会去重），重复运行只会覆盖同名 HTML。
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { marked } from 'marked';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '..');
const SRC = path.join(repo, 'docs', 'wow', 'capycraft');
const OUT = path.resolve(process.argv[2] || path.join(repo, 'build'));
const BASE = '/wiki/wow/capycraft';

marked.setOptions({ gfm: true, breaks: false });

const escapeHtml = (s) =>
  s.replace(/&(?!(?:#\d+|#x[0-9a-f]+|[a-z][a-z0-9]+);)/gi, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

function siteUrl() {
  const cfg = fs.readFileSync(path.join(repo, 'docusaurus.config.js'), 'utf8');
  const m = /\burl:\s*'([^']+)'/.exec(cfg);
  return (m ? m[1] : 'https://zh.chinapedia.org').replace(/\/$/, '');
}
const SITE_URL = siteUrl();
const pageUrl = (rel) => `${SITE_URL}${encodeURI(`${BASE}/${rel.slice(0, -3)}`)}`;

// 从主站 <head> 里只取样式表，其余一概不复用：
// - Docusaurus 的 JS 会让这些页面 hydration 失败白屏（路由清单里没有它们）；
// - 首页的 title / canonical / og:* 元信息对 wow 页面全是错的。
function buildHead() {
  const base = [
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<style>',
    '.wow-static-header{padding:12px 24px;border-bottom:1px solid var(--ifm-color-emphasis-300,#ddd);font-size:14px}',
    '.wow-static-header a{text-decoration:none}',
    '.wow-static-main{max-width:900px;margin:0 auto;padding:24px}',
    '</style>',
  ].join('\n');
  const indexPath = path.join(OUT, 'index.html');
  if (!fs.existsSync(indexPath)) {
    console.warn('[render_wow] 未找到 index.html，跳过主站样式表复用');
    return base;
  }
  const html = fs.readFileSync(indexPath, 'utf8');
  const m = /<head[^>]*>([\s\S]*?)<\/head>/i.exec(html);
  if (!m) return base;
  const styles = [...m[1].matchAll(/<link\b[^>]*rel="stylesheet"[^>]*>/gi)].map((x) => x[0]);
  return [base, ...styles].join('\n');
}

function cssHref() {
  const cssDir = path.join(OUT, 'assets', 'css');
  if (!fs.existsSync(cssDir)) return '';
  const hit = fs.readdirSync(cssDir).find((f) => /^styles\..*\.css$/.test(f));
  return hit ? `/assets/css/${hit}` : '';
}

if (!fs.existsSync(SRC)) {
  console.error(`[render_wow] 找不到 ${SRC}；先跑 git submodule update --init docs/wow/capycraft`);
  process.exit(1);
}
if (!fs.existsSync(OUT)) {
  console.error(`[render_wow] 找不到产物目录 ${OUT}；必须先跑 Docusaurus 构建`);
  process.exit(1);
}

const head = buildHead();
const css = cssHref();
if (!css && !/rel="stylesheet"/.test(head)) {
  console.warn('[render_wow] 产物里没有主站 CSS，生成的页面将无样式');
}

const started = Date.now();
const allFiles = [];
(function walk(dir, rel) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === '.git' || e.name === '.gitignore') continue;
    const r = rel ? `${rel}/${e.name}` : e.name;
    if (e.isDirectory()) walk(path.join(dir, e.name), r);
    else allFiles.push(r);
  }
})(SRC, '');

const mdRels = allFiles.filter((r) => r.endsWith('.md'));
if (mdRels.length === 0) {
  console.error('[render_wow] docs/wow/capycraft 下没有 .md 文件');
  process.exit(1);
}
const mdSet = new Set(mdRels.map((r) => r.slice(0, -3)));
const otherRels = allFiles.filter((r) => !r.endsWith('.md'));

let rewritten = 0;
let broken = 0;
let escaping = 0;
let dirLinks = 0;
const brokenSamples = [];

function rewriteLinks(md, rel) {
  const dir = path.posix.dirname(rel);
  return md.replace(/(!?\[[^\]]*\])\(([^)\s]+)((?:\s+"[^"]*")?)\)/g, (m, label, target, title) => {
    if (/^(https?:|mailto:|#|\/)/.test(target)) return m;
    if (target.endsWith('/')) {
      dirLinks++;
      return m; // README 里的目录链接，不是文档页
    }
    const hashAt = target.indexOf('#');
    const raw = hashAt < 0 ? target : target.slice(0, hashAt);
    const anchor = hashAt < 0 ? '' : target.slice(hashAt);
    const resolved = path.posix.normalize(path.posix.join(dir, raw));
    if (resolved === '..' || resolved.startsWith('../')) {
      escaping++;
      return m;
    }
    let id = resolved;
    if (id.endsWith('.md')) {
      id = id.slice(0, -3);
      if (!mdSet.has(id)) {
        broken++;
        if (brokenSamples.length < 5) brokenSamples.push(`${rel} -> ${raw}`);
      }
    }
    rewritten++;
    return `${label}(${encodeURI(`${BASE}/${id}`)}${anchor}${title})`;
  });
}

function pageHtml(md, rel) {
  const titleMatch = /^#\s+(.+)$/m.exec(md);
  const title = titleMatch ? titleMatch[1].trim() : path.basename(rel, '.md');
  const body = marked.parse(rewriteLinks(md, rel));
  return `<!doctype html>
<html lang="zh-Hans">
<head>
${head}
<title>${escapeHtml(title)} - 中国百科</title>
<link rel="canonical" href="${pageUrl(rel)}">
</head>
<body>
<header class="wow-static-header"><a href="/">中国百科</a> / <a href="/wiki/intro">条目</a> / wow</header>
<main class="wow-static-main"><article class="theme-doc-markdown markdown">${body}</article></main>
</body>
</html>
`;
}

// 一次性建好所有目标目录，避免每篇都 recursive mkdir（Windows 上是主要开销）。
const targets = [
  ...mdRels.map((rel) => [rel, path.join(OUT, BASE, `${rel.slice(0, -3)}.html`)]),
  ...otherRels.map((rel) => [rel, path.join(OUT, BASE, rel)]),
];
for (const d of new Set(targets.map(([, dest]) => path.dirname(dest)))) {
  fs.mkdirSync(d, { recursive: true });
}
for (const [rel, dest] of targets.slice(0, mdRels.length)) {
  fs.writeFileSync(dest, pageHtml(fs.readFileSync(path.join(SRC, rel), 'utf8'), rel));
}
for (const [rel, dest] of targets.slice(mdRels.length)) {
  fs.copyFileSync(path.join(SRC, rel), dest);
}

// sitemap 追加（幂等）。Docusaurus 只知道自己编译的 63 页。
let sitemapAdded = 0;
const sitemapPath = path.join(OUT, 'sitemap.xml');
if (fs.existsSync(sitemapPath)) {
  const xml = fs.readFileSync(sitemapPath, 'utf8');
  const existing = new Set([...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]));
  const additions = [];
  for (const rel of mdRels) {
    const loc = pageUrl(rel);
    if (!existing.has(loc)) {
      existing.add(loc);
      additions.push(`<url><loc>${loc}</loc><changefreq>monthly</changefreq><priority>0.3</priority></url>`);
    }
  }
  if (additions.length && xml.includes('</urlset>')) {
    fs.writeFileSync(sitemapPath, xml.replace('</urlset>', `${additions.join('')}</urlset>`));
    sitemapAdded = additions.length;
  }
} else {
  console.warn('[render_wow] 产物里没有 sitemap.xml，跳过 sitemap 追加');
}

const secs = ((Date.now() - started) / 1000).toFixed(1);
console.log(`[render_wow] ${mdRels.length} 篇 + ${otherRels.length} 个资源 -> ${OUT}`);
console.log(
  `[render_wow] 链接 ${rewritten} 条（死链 ${broken}，逃出子树 ${escaping}，目录链接 ${dirLinks}）` +
    ` | sitemap +${sitemapAdded} | ${secs}s | 峰值 RSS ${Math.round(process.resourceUsage().maxRSS / 1024)} MB`,
);
if (brokenSamples.length) {
  console.warn(`[render_wow] 死链样例: ${brokenSamples.join(', ')}`);
}
console.log(`[render_wow] 主站 CSS: ${css || '(复用 <head> 中的样式表)'}`);
