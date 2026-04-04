/**
 * Google AI Overview Mode via browser interaction.
 */

import { cli, Strategy } from '../../registry.js';
import { CliError } from '../../errors.js';

cli({
  site: 'google',
  name: 'ai-overview',
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

    // Click "AI 模式" if available
    try {
      await page.click('text=AI 模式');
      await page.wait(5);
    } catch (e) {
      // Continue; AI mode may already be displayed or not available
    }

    const result: any = await page.evaluate(`
      (function() {
        const data = { summary: '', sections: [], sources: [] };
        const main = document.querySelector('main');
        if (!main) return null;

        const heading = main.querySelector('h2, [role="heading"][aria-level="2"]');
        if (!heading) return null;
        data.summary = heading.textContent.trim();

        let container = heading.closest('div, generic');
        if (!container) container = main;

        const sectionHeadings = container.querySelectorAll('h3, [role="heading"][aria-level="3"]');
        sectionHeadings.forEach((h) => {
          const title = h.textContent.trim();
          const content = [];
          let sib = h.nextElementSibling;
          while (sib && !(sib.tagName === 'H2' || sib.tagName === 'H3' || (sib.getAttribute && sib.getAttribute('role') === 'heading')) {
            if (sib.tagName === 'UL' || sib.tagName === 'OL') {
              sib.querySelectorAll('li').forEach(li => content.push(li.textContent.trim()));
            } else if (sib.tagName === 'P') {
              content.push(sib.textContent.trim());
            } else if (sib.tagName === 'DIV') {
              const lis = sib.querySelectorAll('li');
              if (lis.length) {
                lis.forEach(li => content.push(li.textContent.trim()));
              }
            }
            sib = sib.nextElementSibling;
          }
          if (title || content.length) {
            data.sections.push({ title, content });
          }
        });

        container.querySelectorAll('a[href]').forEach(link => {
          const href = link.href;
          const txt = link.textContent.trim();
          if (href && txt && href.startsWith('http')) {
            data.sources.push({ title: txt, url: href });
          }
        });

        return data;
      })()
    `);

    if (!result) {
      throw new CliError('NOT_FOUND', 'AI Overview not found', 'Try a different query.');
    }

    const rows = [];
    if (result.summary) rows.push({ type: 'summary', content: result.summary, sources: '' });
    result.sections.forEach((s: any) => {
      rows.push({ type: 'section', content: '## ' + s.title + '\\n\\n' + s.content.join('\\n'), sources: '' });
    });
    if (result.sources.length) {
      rows.push({ type: 'sources', content: 'Sources:', sources: result.sources.map((s: any) => s.title + ': ' + s.url).join('\\n') });
    }

    return rows;
  },
});
