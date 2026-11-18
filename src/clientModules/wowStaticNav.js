// /wiki/wow/** 由 scripts/render_wow.mjs 静态生成，不在 Docusaurus 的路由表里。
//
// 问题：navbar / footer / 正文里的站内链接会被渲染成 React Router 的 <Link>，
// 点击后走客户端路由；路由表里没有 /wiki/wow，于是直接渲染 NotFound 组件，
// 地址栏停在 /wiki/wow、页面却显示「我们找不到您要找的页面」，并不会发出网络请求。
// 只有 Ctrl+R（整页刷新）才会真正请求服务器，由 Cloudflare 返回静态文件。
//
// 解决：在 capture 阶段接管这类点击，改成整页跳转（window.location.assign）。
// 用 capture 是因为 React 的事件监听挂在 root 容器上，document 的捕获阶段先执行；
// preventDefault 之后 React Router 的 click handler 会跳过导航。
const BASE = '/wiki/wow';

const isWowPath = (p) => p === BASE || p.startsWith(`${BASE}/`);

function onClick(event) {
  // 只接管左键、无修饰键的普通点击，别破坏新标签页 / 下载等行为
  if (event.defaultPrevented || event.button !== 0) return;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

  const el = event.target;
  const anchor = el instanceof Element ? el.closest('a[href]') : null;
  if (!anchor) return;

  const href = anchor.getAttribute('href');
  if (!href || !href.startsWith('/') || href.startsWith('//')) return;

  const path = href.split(/[?#]/)[0];
  if (!isWowPath(path)) return;

  event.preventDefault();
  // /wiki/wow -> /wiki/wow/：Cloudflare 的 auto-trailing-slash 直接命中 index.html，
  // 省掉一次 307。
  const normalized = path === BASE ? `${BASE}/` : path;
  window.location.assign(`${normalized}${href.slice(path.length)}`);
}

if (typeof window !== 'undefined') {
  document.addEventListener('click', onClick, true);
}

// Docusaurus client module 若没有导出任何生命周期函数会告警，这里留个空实现。
export function onRouteDidUpdate() {}
