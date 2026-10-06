// Runtime test: actually *evaluate* the compiled MDX.
// A bare `{li}` in the source COMPILES fine (it becomes a JS expression) but throws
// ReferenceError when the page renders — so `compile()` alone cannot catch it.
// Uses stub jsx factories, so no React install needed.
import fs from 'fs';
import { compile } from '@mdx-js/mdx';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';

const FILE = process.argv[2] || 'D:/SRC/Z/zh.chinapedia/docs/math/黎曼猜想.md';
let src = fs.readFileSync(FILE, 'utf8');
src = src.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '');

// 文件自带 ESM（内嵌 React 动画组件）时：function-body 会把 import 变成顶层
// `await import(...)`，new Function 求值不了；真求值也会因为缺 React renderer
// 报 Invalid hook call。这类文件只做 program 编译检查（与 Docusaurus 同路径）。
const hasEsm = /^(?:import|export)[\s{]/m.test(src);

let compiled;
try {
  compiled = String(await compile(src, {
    remarkPlugins: [remarkGfm, remarkMath],
    outputFormat: hasEsm ? 'program' : 'function-body',
  }));
} catch (e) {
  console.log('COMPILE ERROR:', e.message);
  process.exit(1);
}

if (hasEsm) {
  console.log('PROGRAM COMPILE OK — 含 ESM，跳过运行时求值（无 React renderer）');
  process.exit(0);
}

const missing = (name) => { throw new Error('missing component: ' + name); };
const runtime = { Fragment: 'Fragment', jsx: (...a) => a, jsxs: (...a) => a };

let mod;
try {
  // 编译产物以 `return {default: MDXContent}` 结尾，所以在末尾再拼 return 是无效的
  mod = new Function(compiled);
} catch (e) {
  console.log('SYNTAX ERROR:', e.message);
  process.exit(1);
}

try {
  const Content = mod(runtime).default;
  Content({});
  console.log('RUNTIME OK — 页面渲染时不会有未定义的标识符');
} catch (e) {
  console.log('RUNTIME ERROR:', e.constructor.name + ': ' + e.message);
  process.exit(1);
}
