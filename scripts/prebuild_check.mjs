// 发布前预检：把「MDX 编译能过、局部校验也全绿，但真构建 / 真访问会炸」的那几类
// 问题一次性扫出来。这些坑都是踩过的，不是拍脑袋想的：
//
//   1. 标题里的裸 < >  →  Docusaurus 生成 TOC 时把 TeX 源码原样插进 HTML，
//      产物里出现未转义的 ' < '，html-minifier-terser Parse Error → 整站构建失败
//   2. MDX 里的裸 {expr} → compile() 不报错，页面运行时 ReferenceError → 白屏
//   3. KaTeX 未定义的宏（维基原文爱用 \C \R \sgn）→ 页面上渲成红色源码
//   4. 图还在裸链维基（反盗链，必裂）
//   5. 脚注定义了但没被引用（remark-gfm 不渲染，等于白写）
//
// 用法：
//   node scripts/prebuild_check.mjs                 # 扫 docs/，跳过 wow/
//   node scripts/prebuild_check.mjs docs/math       # 只扫某个目录
//   node scripts/prebuild_check.mjs --wow           # 连 wow/ 一起扫（9711 篇，慢）
//
// 退出码：有问题返回 1，CI 里可以直接用。
import fs from 'fs';
import path from 'path';
import { compile } from '@mdx-js/mdx';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import remarkParse from 'remark-parse';
import remarkRehype from 'remark-rehype';
import rehypeKatex from 'rehype-katex';
import katex from 'katex';
import { visit } from 'unist-util-visit';

// 必须和 docusaurus.config.js 里的 katexMacros 保持一致
const KATEX_MACROS = {
  '\\R': '\\mathbb{R}', '\\C': '\\mathbb{C}', '\\N': '\\mathbb{N}',
  '\\Z': '\\mathbb{Z}', '\\Q': '\\mathbb{Q}', '\\F': '\\mathbb{F}',
  '\\sgn': '\\operatorname{sgn}',
  '\\arccot': '\\operatorname{arccot}',
  '\\arcsec': '\\operatorname{arcsec}',
  '\\arccsc': '\\operatorname{arccsc}',
};

const R2_HOST = 'pub-275e30003c354ac0862cc9839e0f952a.r2.dev';

const args = process.argv.slice(2);
const includeWow = args.includes('--wow');
const roots = args.filter((a) => !a.startsWith('--'));
const ROOTS = roots.length ? roots : ['docs'];

const files = [];
for (const root of ROOTS) {
  (function walk(d) {
    let ents;
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const e of ents) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) {
        if (e.name.startsWith('.')) continue;
        if (e.name === 'wow' && !includeWow) continue;
        walk(p);
      } else if (e.name.endsWith('.md')) {
        files.push(p);
      }
    }
  })(root);
}

const problems = [];
const note = (file, kind, msg) => problems.push({ file, kind, msg });

const MATH_RE = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g;
const IMG_RE = /!\[[^\]]*\]\((\S+?)(?:\s+"[^"]*")?\)/g;
// 裸 URL：`[https://…]` 后面没跟 `(…)` 才是真问题；
// `[https://host](url)` 这种是正常的链接/脚注定义，不算
const BARE_URL_RE = /\[https?:\/\/[^\]]+\](?!\()/g;

for (const f of files) {
  const raw = fs.readFileSync(f);
  const text = raw.toString('utf8');
  const body = text.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '');

  // ---- 1. 标题里的裸 < > ------------------------------------------------
  for (const line of body.split(/\r?\n/)) {
    if (!/^#{1,6}\s/.test(line)) continue;
    // \lt / \gt 是合法写法（TeX 源码里没有裸尖括号），放行
    const probe = line.replace(/\\lt\b/g, '').replace(/\\gt\b/g, '')
      .replace(/\\le\b/g, '').replace(/\\ge\b/g, '')
      .replace(/<[a-zA-Z/!][^>]*>/g, ''); // 真正的 HTML 标签不算
    if (/[<>]/.test(probe)) {
      note(f, '标题裸尖括号', line.trim().slice(0, 60));
    }
  }

  // ---- 2. KaTeX 未定义宏 -------------------------------------------------
  for (const m of body.matchAll(MATH_RE)) {
    const display = m[1] !== undefined;
    const src = (m[1] ?? m[2]).trim();
    try {
      katex.renderToString(src, {
        throwOnError: true, strict: 'ignore',
        displayMode: display, macros: KATEX_MACROS,
      });
    } catch (e) {
      const mm = /Undefined control sequence: (\\[A-Za-z]+)/.exec(e.message);
      note(f, 'KaTeX 未定义宏', (mm ? mm[1] : e.message.split('\n')[0]) + '  ← ' + src.slice(0, 40));
    }
  }

  // ---- 3. 图片宿主 -------------------------------------------------------
  for (const m of body.matchAll(IMG_RE)) {
    const u = m[1];
    if (/^https?:\/\//i.test(u)) {
      if (!u.includes(R2_HOST)) {
        note(f, '图片未走 R2', u.slice(0, 80));
      }
    }
    // 相对路径视为站点自带资源，不报
  }

  // ---- 3b. 裸 URL：[https://…] 后面没有 (…)，会原样显示成字面文本 ---------
  for (const m of body.matchAll(BARE_URL_RE)) {
    note(f, '裸 URL 未成链接', m[0].slice(0, 70));
  }

  // ---- 4. 脚注：定义了却没引用 / 引用了却没定义 ---------------------------
  // 注意：引用标记后面可能紧跟冒号（中文里写「…[^23]：」），所以不能靠 (?!:) 区分
  // 定义和引用，必须先把「定义行 + 它的缩进续行」整段抠掉，剩下的才算引用。
  const defs = new Set();
  const refLines = [];
  let inDef = false;
  for (const line of body.split(/\r?\n/)) {
    const dm = /^\[\^([^\]]+)\]:/.exec(line);
    if (dm) { defs.add(dm[1]); inDef = true; continue; }
    if (inDef && /^[ \t]+\S/.test(line)) continue; // 定义的缩进续行
    inDef = false;
    refLines.push(line);
  }
  const refs = new Set();
  for (const m of refLines.join('\n').matchAll(/\[\^([^\]]+)\]/g)) refs.add(m[1]);
  for (const r of refs) if (!defs.has(r)) note(f, '脚注未定义', '[^' + r + ']');
  for (const d of defs) if (!refs.has(d)) note(f, '脚注未被引用', '[^' + d + ']:');

  // ---- 5. MDX 编译 + 运行时求值（抓裸 {expr}）---------------------------
  let compiled;
  try {
    compiled = String(await compile(body, {
      remarkPlugins: [remarkGfm, remarkMath],
      outputFormat: 'function-body',
    }));
  } catch (e) {
    note(f, 'MDX 编译失败', e.message.split('\n')[0]);
    continue;
  }
  try {
    const h = () => null;
    const Content = new Function(compiled)({ Fragment: 'Fragment', jsx: h, jsxs: h }).default;
    Content({});
  } catch (e) {
    note(f, 'MDX 运行时报错', e.message.split('\n')[0]);
  }

  // ---- 6. KaTeX 在真实渲染管线里报红 ------------------------------------
  try {
    const tree = await unifiedRun(body);
    visit(tree, (n) => {
      if (n.type !== 'element') return;
      const style = String(n.properties?.style || '');
      const mcolor = String(n.properties?.mathcolor || '');
      if (style.includes('#cc0000') || mcolor.includes('#cc0000')) {
        note(f, 'KaTeX 渲染报红', '公式渲染失败（红色文本）');
      }
    });
  } catch { /* 编译阶段已经报过了，这里不再重复 */ }
}

async function unifiedRun(body) {
  const { unified } = await import('unified');
  return unified()
    .use(remarkParse).use(remarkGfm).use(remarkMath).use(remarkRehype)
    .use(rehypeKatex, { macros: KATEX_MACROS })
    .run(unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(body));
}

// ---- 汇总 ---------------------------------------------------------------
const byKind = {};
for (const p of problems) (byKind[p.kind] ||= []).push(p);

console.log('预检文件数:', files.length);
if (!problems.length) {
  console.log('√ 全部通过');
  process.exit(0);
}
console.log('× 发现', problems.length, '个问题：');
for (const [kind, list] of Object.entries(byKind)) {
  console.log('\n[' + kind + '] ' + list.length);
  for (const p of list.slice(0, 20)) console.log('   ', p.file, '→', p.msg);
  if (list.length > 20) console.log('    … 另有', list.length - 20, '条');
}
process.exit(1);
