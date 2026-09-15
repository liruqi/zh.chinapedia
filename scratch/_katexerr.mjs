import fs from 'fs';
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import remarkRehype from 'remark-rehype';
import rehypeKatex from 'rehype-katex';
import { visit } from 'unist-util-visit';
const FILE = process.argv[2];
const src = fs.readFileSync(FILE, 'utf8').replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '');
const tree = await unified().use(remarkParse).use(remarkGfm).use(remarkMath)
  .use(remarkRehype).use(rehypeKatex)
  .run(unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(src));
let errs = [];
visit(tree, (n) => {
  if (n.type !== 'element') return;
  const c = ((n.properties && n.properties.className) || []).join(' ');
  if (c.includes('katex-error')) {
    let s = ''; visit(n, (x) => { if (x.type === 'text') s += x.value; });
    errs.push(s.slice(0, 120));
  }
});
console.log('katex-error:', errs.length);
errs.slice(0, 8).forEach(e => console.log('   ', e.replace(/\s+/g, ' ')));
