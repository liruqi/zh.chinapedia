#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

function extractAIFallback(query) {
  const base = '/Users/server/Downloads';
  let dir = null;
  let maxMtime = 0;

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
  if (!dir) throw new Error('No FLX* folder found in ' + base);

  const htmlDir = path.join(dir, 'www.google.com');
  let files = [];
  try {
    if (!fs.existsSync(htmlDir)) throw new Error('missing');
    const all = fs.readdirSync(htmlDir);
    files = all
      .filter(f => f.endsWith('.html'))
      .map(f => ({ name: f, mtime: fs.statSync(path.join(htmlDir, f)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime);
  } catch (e) {
    throw new Error('No HTML in ' + htmlDir);
  }
  if (files.length === 0) throw new Error('Empty ' + htmlDir);

  const htmlContent = fs.readFileSync(path.join(htmlDir, files[0].name), 'utf-8');

  // Find all ZFcyjd containers (AI Overview sections)
  const containers = [];
  let searchFrom = 0;
  while (true) {
    const start = htmlContent.indexOf('class="ZFcyjd"', searchFrom);
    if (start === -1) break;
    let i = start;
    while (i < htmlContent.length && htmlContent[i] !== '>') i++;
    if (i >= htmlContent.length) break;
    i++;
    const contentStart = i;
    let depth = 0;
    while (i < htmlContent.length) {
      if (htmlContent.substring(i, i + 5) === '<div ') {
        depth++; i += 5;
      } else if (htmlContent.substring(i, i + 6) === '</div>') {
        if (depth === 0) {
          containers.push(htmlContent.substring(contentStart, i));
          break;
        }
        depth--; i += 6;
      } else {
        i++;
      }
    }
    searchFrom = i;
  }

  if (containers.length === 0) {
    throw new Error('No ZFcyjd containers found');
  }

  // Select container that matches query (case-insensitive)
  let targetContainer = containers[0];
  if (query) {
    const q = query.toLowerCase();
    for (const c of containers) {
      if (c.toLowerCase().includes(q)) {
        targetContainer = c;
        break;
      }
    }
  }

  return processContainer(targetContainer, query);
}

function processContainer(containerHtml, query) {
  // Extract visible text
  let text = containerHtml.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
                          .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '');
  text = text.replace(/<\/(div|p|h1|h2|h3|h4|h5|h6|ul|ol|li|section|article)>\s*/gi, '\n')
             .replace(/<br\s*\/?>\s*/gi, '\n')
             .replace(/<[^>]+>/g, ' ')
             .replace(/&nbsp;/g, ' ')
             .replace(/&amp;/g, '&')
             .replace(/&lt;/g, '<')
             .replace(/&gt;/g, '>')
             .replace(/&quot;/g, '"')
             .replace(/&#39;/g, "'")
             .replace(/\s+\n/g, '\n')
             .replace(/\n\s+/g, '\n')
             .replace(/\n{3,}/g, '\n\n')
             .trim();

  const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);

  // Keep Chinese lines (>=2 chars) or citation numbers
  const meaningful = [];
  for (const line of lines) {
    if (/[\u4e00-\u9fff]/.test(line) && line.length >= 2) meaningful.push(line);
    else if (/^\[\d+\]$/.test(line) || /^\[\d+,\s*\d+\]$/.test(line)) meaningful.push(line);
  }

  // Extract title (first Chinese line or query)
  let title = query ? query.charAt(0).toUpperCase() + query.slice(1) : 'AI Overview';
  if (meaningful.length > 0 && meaningful[0].length < 60 && /[\u4e00-\u9fff]/.test(meaningful[0])) {
    title = meaningful[0];
  }

  // Extract sources
  const sources = [];
  const sourcesRegex = /<ul class="KsbFXc U6u95"[^>]*>([\s\S]*?)<\/ul>/i;
  const sourcesMatch = containerHtml.match(sourcesRegex);
  if (sourcesMatch) {
    const sourcesHtml = sourcesMatch[1];
    const liRegex = /<li[^>]*>([\s\S]*?)<\/li>/gi;
    let liMatch;
    while ((liMatch = liRegex.exec(sourcesHtml)) !== null) {
      const liHtml = liMatch[1];
      const hrefMatch = liHtml.match(/href="([^"]+)"/);
      const textMatch = liHtml.match(/>([^<]+)<\/a>/);
      if (hrefMatch && textMatch) {
        const url = hrefMatch[1].replace(/&amp;/g, '&').replace(/%3A/g, ':').replace(/%2F/g, '/');
        const text = textMatch[1].trim();
        if (text.length > 1 && url.startsWith('http')) {
          sources.push(text + ': ' + url);
        }
      }
    }
  } else {
    // Fallback: extract any <a> links with valid domains
    const anchorRegex = /<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi;
    let aMatch;
    const validDomains = ['stepfun.com', 'step.fun', 'openrouter.ai', 'github.com', 'guancha.cn', 'x.ai', 'grok.com', 'elastic.co'];
    while ((aMatch = anchorRegex.exec(containerHtml)) !== null) {
      const url = aMatch[1].replace(/&amp;/g, '&').replace(/%3A/g, ':').replace(/%2F/g, '/');
      const text = aMatch[2].replace(/<[^>]+>/g, '').trim();
      if (text.length > 1 && url.startsWith('http') && validDomains.some(d => url.toLowerCase().includes(d))) {
        sources.push(text + ': ' + url);
      }
    }
  }

  return {
    content: '# ' + title + '\n\n' + meaningful.slice(1).join('\n'),
    sources: [...new Set(sources)].slice(0, 10)
  };
}

// Main
const [, , query = 'AI', outputPath] = process.argv;
if (!query || query === '-h' || query === '--help') {
  console.log('Usage: node extract-gai.js <query> [output-path]');
  console.log('  query: search query (e.g., Grok, StepFun)');
  console.log('  output-path: optional, default to ~/Documents/zh.chinapedia/docs/ai/product/<query>.md');
  process.exit(0);
}

try {
  const result = extractAIFallback(query);

  const defaultPath = path.join(
    process.env.HOME || '/Users/server',
    'Documents/zh.chinapedia/docs/ai/model',
    query.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]/g, '-') + '.md'
  );
  const outFile = outputPath || defaultPath;

  const outDir = path.dirname(outFile);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const output = `# ${query.charAt(0).toUpperCase() + query.slice(1)} AI 概述

${result.content}

## 参考来源

${result.sources.length > 0 ? result.sources.join('\n') : '暂无来源'}

---

*本文档自动生成于 ${new Date().toISOString()}，使用 OpenCLI google ai-mode FLX 提取器*
`;

  fs.writeFileSync(outFile, output, 'utf-8');
  console.log('✅ Saved to:', outFile);
  console.log('📄 Content length:', result.content.length);
  console.log('🔗 Sources:', result.sources.length);
  process.exit(0);
} catch (error) {
  console.error('❌ Error:', error.message);
  process.exit(1);
}
