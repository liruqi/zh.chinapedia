/**
 * Google AI Overview Mode via browser interaction.
 */

import { cli, Strategy } from '../../registry.js';
import { CliError } from '../../errors.js';
import * as fs from 'fs';
import * as path from 'path';

cli({
  site: 'google',
  name: 'ai-mode',
  description: 'Get Google AI Overview summary',
  domain: 'google.com',
  strategy: Strategy.COOKIE,
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

    // Click "AI 模式" button
    try {
      await page.evaluate('window.scrollTo(0, 200)');
      await page.wait(1);
      await page.evaluate(`(() => {
        const btn = document.querySelector('a:has(span.R1QWuf)');
        if (btn) { btn.click(); return; }
        const spans = document.querySelectorAll('span.R1QWuf');
        for (const span of spans) {
          if (span.textContent.trim() === 'AI 模式') {
            span.closest('a')?.click();
            return;
          }
        }
      })`);
      await page.wait(8);
      await page.evaluate('window.scrollBy(0, 600)');
      await page.wait(8);
    } catch (e) {}

    try {
      await page.evaluate(`(() => {
        const buttons = Array.from(document.querySelectorAll('button, a[role="button"]'));
        for (const btn of buttons) {
          const txt = (btn.textContent || '').trim().toLowerCase();
          if (txt.includes('copy') || txt.includes('复制') || txt.includes('sources')) {
            btn.click();
            return true;
          }
        }
        return false;
      })`);
      await page.wait(2);
    } catch (e) {}

    // @ts-ignore
    const extracted: any = await page.evaluate(`(() => {
      const allDivs = document.querySelectorAll('div[data-ved]');
      let container = null;
      let h3Texts = [];
      for (const div of allDivs) {
        const h2 = div.querySelector('h2, [role="heading"][aria-level="2"]');
        if (!h2) continue;
        const h2Text = (h2.textContent || '').toLowerCase();
        if (!h2Text.includes('ai') && !h2Text.includes('overview') && !h2Text.includes('概览')) continue;
        const h3s = div.querySelectorAll('h3, [role="heading"][aria-level="3"]');
        if (h3s.length === 0) continue;
        container = div;
        h3s.forEach(h => h3Texts.push((h.textContent || '').trim()));
        break;
      }
      if (!container) return { found: false };

      const fullText = container.innerText.trim();
      const rawLines = fullText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);

      const cleaned = [];
      let prevLine = '';
      const noise = new Set([
        '·', '几秒钟前', '来自网络的快速搜索结果：', '全部显示', '我的 Google 搜索记录',
        '无障碍功能帮助', '跳到主要内容', '翻译此页', '展开', '收起', '查看更多', '显示全部',
        '相关搜索', '用户还搜索了', '网页导航', '页脚链接', 'Grok', 'xAI', 'Wikipedia',
        '提交依法移除要求', '《隐私权政策》', '《服务条款》', '更多结果', '赞助商搜索结果',
        '包含站点链接的网页搜索结果', '搜索结果', 'My Activity', 'Terms', 'Privacy', 'YouTube', 'AI 回答可能包含错误。如需财务建议，请咨询专业人士。 了解详情'
      ]);
      for (const line of rawLines) {
        if (noise.has(line) || line.includes('个网站') || /^\\d+$/.test(line) || /^[+]\\d+$/.test(line) || (line.length < 2 && /[·+]/.test(line))) {
          continue;
        }
        // Citation: _+12, +12, _12, 12 -> attach [12] to previous line
        const m = line.match(/^_?\\+?(\\d+)$/);
        if (m) {
          if (prevLine) {
            const idx = cleaned.lastIndexOf(prevLine);
            if (idx !== -1) {
              cleaned[idx] = prevLine + ' [' + m[1] + ']';
              prevLine = cleaned[idx];
            }
          }
          continue;
        }
        // Heading?
        const isHeading = h3Texts.includes(line);
        cleaned.push((isHeading ? '## ' : '') + line);
        prevLine = cleaned[cleaned.length - 1];
      }

      const sources = [];
      container.querySelectorAll('a[href]').forEach(a => {
        const href = a.getAttribute('href') || '';
        const txt = (a.textContent || '').trim();
        if (href.startsWith('http') && txt && txt.length < 100) {
          sources.push(txt + ': ' + href);
        }
      });
      // Filter out non-citation source entries
      const blocked = ['我的 Google 搜索记录', '隐私权政策', '服务条款', '提交依法移除要求', 'My Activity', 'Terms', 'Privacy', '了解详情'];
      const filteredSources = sources.filter(s => !blocked.some(b => s.includes(b)));
      return { found: true, content: cleaned.join('\\n'), sources: [...new Set(filteredSources)].slice(0, 10) };
    })`);

    if (extracted && extracted.found) {
      return [{ type: 'ai_overview', content: extracted.content, sources: extracted.sources ? extracted.sources.join('\\n') : '' }];
    }

    // Fallback: line-based from main
    // @ts-ignore
    const result: any = await page.evaluate(`(() => {
      const main = document.querySelector('main') || document.body;
      const fullText = main.innerText.trim();
      const lines = fullText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);

      let startIdx = -1;
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const lower = line.toLowerCase();
        if ((lower.includes('ai') && (lower.includes('overview') || lower.includes('概览') || lower.includes('总结') || lower.includes('摘要')))
            || (lower.includes('ai') && line.length < 60 && !line.startsWith('http'))) {
          startIdx = i;
          break;
        }
      }
      if (startIdx === -1) return { found: false, text: fullText };

      let endIdx = lines.length;
      for (let i = startIdx + 1; i < lines.length; i++) {
        const line = lines[i].toLowerCase();
        if (line.includes('web results') || line.includes('搜索结果') || line.includes('相关搜索') || line.includes('赞助商') || line.includes('更多结果')) {
          endIdx = i;
          break;
        }
      }

      const minEnd = startIdx + 20;
      if (endIdx < minEnd) endIdx = Math.min(lines.length, startIdx + 40);

      const snippetLines = lines.slice(startIdx, endIdx);
      const navItems = ['全部', '图片', '视频', '购物', '新闻', '短视频', '更多', '工具', 'AI 模式', '跳过', '取消', '确定', '展开', '收起', '翻译此页'];
      const filtered = snippetLines.filter(line => {
        const clean = line.toLowerCase();
        return !navItems.some(nav => clean.includes(nav.toLowerCase())) && line.length > 1 && !/^[\\d\\.]+$/.test(line);
      });

      const sources = [];
      const allLinks = main.querySelectorAll('a[href]');
      for (const a of allLinks) {
        const href = a.getAttribute('href') || '';
        const txt = (a.textContent || '').trim();
        if (href.startsWith('http') && txt && txt.length < 100) {
          sources.push(txt + ': ' + href);
        }
      }
      const blocked = ['我的 Google 搜索记录', '隐私权政策', '服务条款', '提交依法移除要求', 'My Activity', 'Terms', 'Privacy'];
      const filteredSources = sources.filter(s => !blocked.some(b => s.includes(b)));
      return { found: true, text: filtered.join('\\n'), sources: [...new Set(filteredSources)].slice(0, 10) };
    })`);

    if (result && result.found) {
      return [{ type: 'ai_overview', content: result.text, sources: result.sources ? result.sources.join('\\n') : '' }];
    }

    // Fallback: parse latest FLX saved HTML
    const base = '/Users/server/Downloads';
    let dir: string | null = null;
    let maxMtime = 0;
    try {
      for (const d of fs.readdirSync(base, { withFileTypes: true })) {
        if (d.isDirectory() && d.name.startsWith('FLX')) {
          const p = path.join(base, d.name);
          const s = fs.statSync(p);
          if (s.mtimeMs > maxMtime) {
            maxMtime = s.mtimeMs;
            dir = p;
          }
        }
      }
    } catch (e) {
      throw new CliError('NOT_FOUND', 'Cannot scan FLX folders', '');
    }
    if (!dir) throw new CliError('NOT_FOUND', 'No FLX* folder', '');

    const htmlDir = path.join(dir, 'www.google.com');
    let files: any[] = [];
    try {
      if (!fs.existsSync(htmlDir)) throw new Error('missing');
      const all = fs.readdirSync(htmlDir);
      files = all.filter(f => f.endsWith('.html')).map(f => ({ name: f, mtime: fs.statSync(path.join(htmlDir, f)).mtimeMs })).sort((a,b) => b.mtime - a.mtime);
    } catch (e) {
      throw new CliError('NOT_FOUND', `No HTML in ${htmlDir}`, '');
    }
    if (files.length === 0) throw new CliError('NOT_FOUND', `Empty ${htmlDir}`, '');

    const html = fs.readFileSync(path.join(htmlDir, files[0].name), 'utf-8');
    const m = html.match(/<main[^>]*>([\s\S]*?)<\/main>/i) || html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    if (m) {
      const mainContent = m[1];
      const divMatch = mainContent.match(/<div[^>]*data-ved[^>]*>([\s\S]*?)(<h2[^>]*>.*?(AI|概览|Overview).*?<\/h2>)([\s\S]*?)<\/div>/i);
      if (divMatch) {
        let raw = (divMatch[2] + divMatch[3]).replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
        const lines = raw.split('\n').map(l => l.trim()).filter(l => l);
        const h3Texts = [];
        const h3Regex = /(?:^|\n)(##\s*)?([^\n]+)/g;
        let match;
        while ((match = h3Regex.exec(raw)) !== null) {
          h3Texts.push(match[1] ? match[2] : match[2]);
        }

        // Process lines: filter sources, add heading markers, handle citations
        const cleaned = [];
        let prevLine = '';
        const noise = ['·', '几秒钟前', '来自网络的快速搜索结果：', '全部显示', '我的 Google 搜索记录', '无障碍功能帮助', '跳到主要内容', '翻译此页', '展开', '收起', '查看更多', '显示全部', '相关搜索', '用户还搜索了', '网页导航', '页脚链接', '提交依法移除要求', '隐私权政策', '服务条款', 'Terms', 'Privacy', 'My Activity'];
        let inSourcesSection = false;

        for (const line of lines) {
          const cleanLine = line.trim();
          if (!cleanLine) continue;

          // Detect start of Sources section
          const lower = cleanLine.toLowerCase();
          if (lower.includes('sources') || lower.includes('来源') || lower.includes('参考') || lower.includes('view all')) {
            inSourcesSection = true;
            continue;
          }

          // Skip sources section lines
          if (inSourcesSection) {
            if (cleanLine.includes('http') && cleanLine.length < 80) continue;
            if (cleanLine.length > 50 && !cleanLine.includes('http')) {
              inSourcesSection = false;
            } else {
              continue;
            }
          }

          // Noise filter
          if (noise.some(n => lower.includes(n))) continue;
          if (/^[\d\.]+$/.test(cleanLine)) continue;
          if (cleanLine.length < 2) continue;

          // Citation marker: _+2, +2, _12, 12 -> attach [2] to previous line
          const citeMatch = cleanLine.match(/^_?\+?(\d+)$/);
          if (citeMatch) {
            if (prevLine) {
              const pos: number = cleaned.lastIndexOf(prevLine);
              if (pos !== -1) {
                cleaned[pos] = prevLine + ' [' + citeMatch[1] + ']';
                prevLine = cleaned[pos];
              }
            }
            continue;
          }

          // Heading detection
          const isHeading = h3Texts.some(h => cleanLine.toLowerCase().includes(h.toLowerCase())) || /^[A-Za-z0-9一-鿿].*:$/.test(cleanLine);
          cleaned.push((isHeading ? '## ' : '') + cleanLine);
          prevLine = cleaned[cleaned.length - 1];
        }

        raw = cleaned.join('\n');
        if (raw.length > 50) {
          return [{ type: 'file_fallback', content: raw, sources: '' }];
        }
      }
      const text = mainContent.replace(/<[^>]+>/g, '').trim().replace(/\s+/g, ' ');
      if (text.length > 100) {
        return [{ type: 'file_fallback', content: text, sources: '' }];
      }
    }

    throw new CliError('NOT_FOUND', 'Unable to extract AI Overview', '');
  },
});
