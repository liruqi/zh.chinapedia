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
    // 目录页（/wiki/wow/、/wiki/wow/capycraft/ 及各分区）用到的样式
    '.wow-static-main--wide{max-width:1200px}',
    '.wow-dir-grid{display:flex;flex-wrap:wrap;gap:12px;padding:0;margin:16px 0 28px;list-style:none}',
    '.wow-dir-grid li{border:1px solid var(--ifm-color-emphasis-300,#ddd);border-radius:8px;padding:10px 14px;min-width:150px}',
    '.wow-dir-grid a{font-weight:600;text-decoration:none}',
    '.wow-dir-grid span{color:var(--ifm-color-emphasis-600,#666);font-size:12px;margin-left:6px}',
    '.wow-doc-list{columns:4;column-gap:24px;padding:0;margin:12px 0;font-size:14px}',
    '.wow-doc-list li{break-inside:avoid;list-style:none;margin:0 0 6px}',
    '.wow-doc-list a{text-decoration:none}',
    '.wow-count{color:var(--ifm-color-emphasis-600,#666);font-size:14px;font-weight:400}',
    '@media(max-width:900px){.wow-doc-list{columns:2}}',
    '@media(max-width:600px){.wow-doc-list{columns:1}}',
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
// 所有真实存在的目录（含各级父目录），用于改写 README 里的 `./xxx/` 目录链接。
const dirSet = new Set(['']);
for (const id of mdSet) {
  const d = path.posix.dirname(id);
  if (d === '.') continue;
  const parts = d.split('/');
  for (let i = 1; i <= parts.length; i++) dirSet.add(parts.slice(0, i).join('/'));
}
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
      // 目录链接：`./dungeon/` -> /wiki/wow/capycraft/dungeon/。
      // 数据源 README 里写的是 `./capycraft/dungeon/`（多了一层目录名），
      // 解析出来是 capycraft/dungeon，去掉冗余前缀后能对上真实目录。
      const hashAt = target.indexOf('#');
      const raw = hashAt < 0 ? target : target.slice(0, hashAt);
      const anchor = hashAt < 0 ? '' : target.slice(hashAt);
      const hrefTarget = (raw.split('?')[0] || '').replace(/\/+$/, '/');
      let resolved = path.posix.normalize(path.posix.join(dir, hrefTarget));
      if (resolved === '.' || resolved === './') resolved = '';
      const alt = resolved.replace(/^capycraft\//, '');
      if (!dirSet.has(resolved) && dirSet.has(alt)) resolved = alt;
      if (!dirSet.has(resolved)) return m; // 目录不存在，保留原样
      const url = resolved ? `${BASE}/${resolved}/` : `${BASE}/`;
      return `${label}(${encodeURI(url)}${anchor}${title})`;
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

function pageHtml(md, rel, title) {
  const body = marked.parse(rewriteLinks(md, rel));
  return `<!doctype html>
<html lang="zh-Hans">
<head>
${head}
<title>${escapeHtml(title)} - 中国百科</title>
<link rel="canonical" href="${pageUrl(rel)}">
</head>
<body>
<header class="wow-static-header"><a href="/">中国百科</a> / <a href="/wiki/intro">条目</a> / <a href="/wiki/wow/">魔兽世界</a></header>
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

// 抽出每篇的标题（H1），目录页要用；顺带避免目录页再读一遍 9710 个文件。
const titles = new Map(); // id（去掉 .md） -> 标题
for (const [rel, dest] of targets.slice(0, mdRels.length)) {
  const md = fs.readFileSync(path.join(SRC, rel), 'utf8');
  const m = /^#\s+(.+)$/m.exec(md);
  const title = m ? m[1].trim() : path.posix.basename(rel, '.md');
  titles.set(rel.slice(0, -3), title);
  fs.writeFileSync(dest, pageHtml(md, rel, title));
}
for (const [rel, dest] of targets.slice(mdRels.length)) {
  fs.copyFileSync(path.join(SRC, rel), dest);
}

// ---------------------------------------------------------------------------
// 目录页 / 分区落地页
// ---------------------------------------------------------------------------
// Docusaurus 的 docs 配了 `exclude: ['wow/**']`，于是它连 docs/wow/_category_.json
// 声明的 generated-index（slug `wow`）也不再生成。只写 `xxx.html` 的结果是：
// /wiki/wow/ 与 /wiki/wow/capycraft/ 全是 404，导航里也找不到这个分区。
// 这里按真实目录结构补出 index.html，并把 docs/wow 下 capycraft 之外的 md
//（目前是 turtle.md 乌龟服）一起渲染。
const DIR_LABELS = {
  '': '水豚乐园',
  item: '物品',
  npc: 'NPC',
  quest: '任务',
  set: '套装',
  dungeon: '副本',
  'dungeon/ent': '副本入口',
  worldboss: '世界首领',
  transport: '交通',
};
const dirLabel = (d) => DIR_LABELS[d] || path.posix.basename(d) || '水豚乐园';

const byDir = new Map();
for (const id of titles.keys()) {
  const d = path.posix.dirname(id);
  const dir = d === '.' ? '' : d;
  if (!byDir.has(dir)) byDir.set(dir, []);
  byDir.get(dir).push(id);
}

const collator = new Intl.Collator('en');
function sortIds(a, b) {
  const na = path.posix.basename(a);
  const nb = path.posix.basename(b);
  const ia = /^\d+$/.test(na);
  const ib = /^\d+$/.test(nb);
  if (ia && ib) return Number(na) - Number(nb);
  if (ia !== ib) return ia ? -1 : 1;
  return collator.compare(na, nb);
}

function childDirs(dir) {
  const out = [];
  for (const d of dirSet) {
    if (!d || d === dir) continue;
    const parent = path.posix.dirname(d);
    if ((parent === '.' ? '' : parent) === dir) out.push(d);
  }
  return out.sort();
}

function dirGrid(dirs) {
  let s = '<ul class="wow-dir-grid">';
  for (const sub of dirs) {
    s += `<li><a href="${encodeURI(`${BASE}/${sub}/`)}">${escapeHtml(dirLabel(sub))}</a><span>${(byDir.get(sub) || []).length} 条</span></li>`;
  }
  return `${s}</ul>`;
}

function staticPage(title, canonical, crumbs, body, wide) {
  return `<!doctype html>
<html lang="zh-Hans">
<head>
${head}
<title>${escapeHtml(title)} - 中国百科</title>
<link rel="canonical" href="${canonical}">
</head>
<body>
<header class="wow-static-header">${crumbs.join(' / ')}</header>
<main class="wow-static-main${wide ? ' wow-static-main--wide' : ''}">${body}</main>
</body>
</html>
`;
}

const CRUMB_HOME = '<a href="/">中国百科</a>';
const CRUMB_WIKI = '<a href="/wiki/intro">条目</a>';
const CRUMB_WOW = '<a href="/wiki/wow/">魔兽世界</a>';

const dirPages = [];
for (const dir of dirSet) {
  const ids = (byDir.get(dir) || []).slice().sort(sortIds);
  const subs = childDirs(dir);
  let body;
  if (dir === '') {
    // 根目录：README 自带介绍与「快速入口」，直接复用（链接已被 rewriteLinks 改写）
    body = marked.parse(
      rewriteLinks(fs.readFileSync(path.join(SRC, 'README.md'), 'utf8'), 'README.md'),
    );
    if (subs.length) body += `\n<h2>分区</h2>\n${dirGrid(subs)}`;
  } else {
    body = `<h1>${escapeHtml(dirLabel(dir))}</h1>\n<p class="wow-count">共 ${ids.length} 条</p>`;
    if (subs.length) body += dirGrid(subs);
    body += '<ul class="wow-doc-list">';
    for (const id of ids) {
      body += `<li><a href="${encodeURI(`${BASE}/${id}`)}">${escapeHtml(titles.get(id) || path.posix.basename(id))}</a></li>`;
    }
    body += '</ul>';
  }
  const canonical = `${SITE_URL}${encodeURI(dir ? `${BASE}/${dir}/` : `${BASE}/`)}`;
  const crumbs = [CRUMB_HOME, CRUMB_WIKI, CRUMB_WOW];
  if (dir) crumbs.push(`<span>${escapeHtml(dirLabel(dir))}</span>`);
  const dest = dir ? path.join(OUT, BASE, dir, 'index.html') : path.join(OUT, BASE, 'index.html');
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(
    dest,
    staticPage(dir === '' ? '水豚乐园资料库' : `${dirLabel(dir)} - 魔兽世界`, canonical, crumbs, body, true),
  );
  dirPages.push(canonical);
}

// docs/wow 下 capycraft 之外的 md（目前是 turtle.md 乌龟服），同样被 exclude 掉了。
const WOW_DIR = path.join(repo, 'docs', 'wow');
const extraDocs = [];
if (fs.existsSync(WOW_DIR)) {
  for (const e of fs.readdirSync(WOW_DIR, { withFileTypes: true })) {
    if (!e.isFile() || !e.name.endsWith('.md')) continue;
    const id = e.name.slice(0, -3);
    const md = fs.readFileSync(path.join(WOW_DIR, e.name), 'utf8');
    const m = /^#\s+(.+)$/m.exec(md);
    const title = m ? m[1].trim() : id;
    const canonical = `${SITE_URL}/wiki/wow/${encodeURI(id)}`;
    const dest = path.join(OUT, 'wiki', 'wow', `${id}.html`);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(
      dest,
      staticPage(
        title,
        canonical,
        [CRUMB_HOME, CRUMB_WIKI, CRUMB_WOW],
        `<article class="theme-doc-markdown markdown">${marked.parse(md)}</article>`,
        false,
      ),
    );
    extraDocs.push({ id, title, canonical });
  }
}

// /wiki/wow/ 落地页：原来由 docs/wow/_category_.json 的 generated-index 生成。
const wowBody = `<h1>魔兽世界</h1>
<p class="wow-count">游戏数据与资料</p>
<ul class="wow-dir-grid">
${extraDocs.map((d) => `<li><a href="/wiki/wow/${encodeURI(d.id)}">${escapeHtml(d.title)}</a></li>`).join('\n')}
<li><a href="${BASE}/">水豚乐园资料库</a><span>${mdRels.length} 条</span></li>
</ul>`;
fs.mkdirSync(path.join(OUT, 'wiki', 'wow'), { recursive: true });
fs.writeFileSync(
  path.join(OUT, 'wiki', 'wow', 'index.html'),
  staticPage('魔兽世界', `${SITE_URL}/wiki/wow/`, [CRUMB_HOME, CRUMB_WIKI, '<span>魔兽世界</span>'], wowBody, false),
);

// sitemap 追加（幂等）。Docusaurus 只知道自己编译的 63 页。
let sitemapAdded = 0;
const sitemapPath = path.join(OUT, 'sitemap.xml');
if (fs.existsSync(sitemapPath)) {
  const xml = fs.readFileSync(sitemapPath, 'utf8');
  const existing = new Set([...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]));
  const additions = [];
  const locs = [
    ...mdRels.map(pageUrl),
    ...dirPages,
    `${SITE_URL}/wiki/wow/`,
    ...extraDocs.map((d) => d.canonical),
  ];
  for (const loc of locs) {
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
