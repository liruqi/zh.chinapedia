/**
 * Google AI Overview Mode via browser interaction.
 */

import { cli, Strategy } from '../../registry.js';
import { CliError } from '../../errors.js';
import { JSDOM } from 'jsdom';
import * as fs from 'fs';
import * as path from 'path';

interface FileInfo {
  name: string;
  mtime: number;
}

cli({
  site: 'google',
  name: 'ai-mode',
  description: 'Get Google AI Overview summary',
  domain: 'google.com',
  strategy: Strategy.PUBLIC,
  browser: true,
  args: [
    { name: 'keyword', positional: true, required: true, help: 'Search query' },
    { name: 'lang', default: 'zh-CN', help: 'Language code' },
  ],
  columns: ['type', 'content', 'sources'],
  func: async (page, args) => {
    const keyword = encodeURIComponent(args.keyword);
    const lang = encodeURIComponent(args.lang);
    const searchUrl = `https://www.google.com/search?q=${keyword}&hl=${lang}`;

    await page.goto(searchUrl);
    await page.wait(3);

    try {
      await page.click('text=AI 模式');
      await page.wait(5);
    } catch (e) {
      // AI mode button may not exist or already active
    }

    // Try clipboard copy
    const copySelectors = [
      'button[aria-label*="复制"]',
      'button[aria-label*="COPY"]',
      'text=COPY',
      'text=复制'
    ];
    for (const sel of copySelectors) {
      try {
        await page.click(sel);
        await page.wait(1);
        // @ts-ignore
        const clipboardText = await page.evaluate(async () => {
          try {
            return await navigator.clipboard.readText();
          } catch {
            return null;
          }
        }) as unknown as string | null;
        if (clipboardText && clipboardText.trim().length > 0) {
          return [{ type: 'copied', content: clipboardText, sources: '' }];
        }
      } catch (e) {
        // continue
      }
    }

    // Fallback: parse latest saved HTML from FLX directories
    const downloadsBase = '/Users/server/Downloads';
    let latestDir: string | null = null;
    let latestMtime = 0;
    try {
      const entries = fs.readdirSync(downloadsBase, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isDirectory() && entry.name.startsWith('FLX')) {
          const dirPath = path.join(downloadsBase, entry.name);
          const stats = fs.statSync(dirPath);
          if (stats.mtimeMs > latestMtime) {
            latestMtime = stats.mtimeMs;
            latestDir = dirPath;
          }
        }
      }
    } catch (e) {
      throw new CliError('NOT_FOUND', 'Cannot scan downloads for FLX folders', '');
    }

    if (!latestDir) {
      throw new CliError('NOT_FOUND', 'No FLX* folders found in downloads', '');
    }

    const htmlDir = path.join(latestDir, 'www.google.com');
    let files: FileInfo[] = [];
    try {
      if (!fs.existsSync(htmlDir)) {
        throw new Error('HTML dir missing');
      }
      const list = fs.readdirSync(htmlDir);
      files = list
        .filter(f => f.endsWith('.html'))
        .map(f => ({
          name: f,
          mtime: fs.statSync(path.join(htmlDir, f)).mtimeMs
        }))
        .sort((a, b) => b.mtime - a.mtime);
    } catch (e) {
      throw new CliError('NOT_FOUND', `No HTML files in ${htmlDir}`, '');
    }

    if (files.length === 0) {
      throw new CliError('NOT_FOUND', `Empty HTML dir: ${htmlDir}`, '');
    }

    const html = fs.readFileSync(path.join(htmlDir, files[0].name), 'utf-8');

    // Parse with JSDOM → GFM
    const dom = new JSDOM(html);
    const doc = dom.window.document;

    const trim = (node: Element | Node) =>
      (node.textContent || '').trim().replace(/\s+/g, ' ');

    const main = doc.querySelector('main') || doc.body;
    const heading = main.querySelector('h2, [role="heading"][aria-level="2"]');
    const summary = heading ? trim(heading) : '';

    const sections: { title: string; content: string }[] = [];
    const container = heading?.closest('div') || main;
    const sectionHeadings = container.querySelectorAll('h3, [role="heading"][aria-level="3"]');
    sectionHeadings.forEach((h: Element) => {
      const title = trim(h);
      const content: string[] = [];
      let sib = h.nextElementSibling;
      while (sib && !(sib.tagName === 'H2' || sib.tagName === 'H3' || (sib.getAttribute?.('role') === 'heading'))) {
        if (['UL', 'OL'].includes(sib.tagName)) {
          sib.querySelectorAll('li').forEach(li => content.push(trim(li)));
        } else if (sib.tagName === 'P') {
          content.push(trim(sib));
        } else if (sib.tagName === 'DIV') {
          const lis = sib.querySelectorAll('li');
          if (lis.length) {
            lis.forEach(li => content.push(trim(li)));
          }
        }
        sib = sib.nextElementSibling;
      }
      if (title || content.length) {
        sections.push({ title, content: content.join('\n') });
      }
    });

    const sources: string[] = [];
    container.querySelectorAll('a[href]').forEach((link: Element) => {
      const href = link.getAttribute('href') ?? '';
      const txt = link.textContent.trim();
      if (href.startsWith('http') && txt) {
        sources.push(`${txt}: ${href}`);
      }
    });

    let md = '';
    if (summary) md += '# ' + summary + '\n\n';
    sections.forEach(sec => {
      if (sec.title) md += '## ' + sec.title + '\n\n';
      md += sec.content + '\n\n';
    });
    if (sources.length) {
      md += '## Sources\n\n' + [...new Set(sources)].join('\n') + '\n';
    }

    return [{ type: 'fallback', content: md, sources: '' }];
  },
});
