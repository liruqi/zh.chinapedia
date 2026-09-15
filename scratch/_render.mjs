// Render one doc through the same pipeline Docusaurus uses
// (remark-gfm + remark-math 6 + rehype-katex 7) and report what actually
// lands in the output tree. Much faster than a full `npm run build`.
// (No HTML stringifier is installed, so we inspect the hast tree directly.)
// Usage: node scratch/_render.mjs docs/math/黎曼猜想.md
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

const tree = await unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkMath)
  .use(remarkRehype)
  .use(rehypeKatex)
  .run(unified().use(remarkParse).use(remarkGfm).use(remarkMath).parse(src));

const cls = (n) => (n.properties && n.properties.className) || [];
let katex = 0, display = 0, refLinks = 0, fnItems = 0, tables = 0;
let rawText = '';
visit(tree, (n) => {
  if (n.type !== 'element') {
    if (n.type === 'text') rawText += n.value + '\n';
    return;
  }
  const c = cls(n).join(' ');
  if (c.includes('katex-display')) display++;
  else if (c.includes('katex')) katex++;
  if (n.tagName === 'a' && ('dataFootnoteRef' in n.properties || 'data-footnote-ref' in n.properties)) refLinks++;
  if (n.tagName === 'li' && /^user-content-fn-\d+$/.test(String(n.properties.id || ''))) fnItems++;
  if (n.tagName === 'table') tables++;
});

const rawDollar = (rawText.match(/\$\$/g) || []).length;
const strayRef = (rawText.match(/\[\^\d+\]/g) || []).length;

console.log('file                 :', FILE);
console.log('katex elements       :', katex);
console.log('katex-display        :', display);
console.log('footnote ref links   :', refLinks);
console.log('footnote list items  :', fnItems);
console.log('tables               :', tables);
console.log('unrendered [^n] text :', strayRef);
console.log('raw $$ in text       :', rawDollar);
