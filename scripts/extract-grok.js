#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

function extractAIFallback() {
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
      .map(f => ({
        name: f,
        mtime: fs.statSync(path.join(htmlDir, f)).mtimeMs
      }))
      .sort((a, b) => b.mtime - a.mtime);
  } catch (e) {
    throw new Error('No HTML in ' + htmlDir);
  }
  if (files.length === 0) throw new Error('Empty ' + htmlDir);

  const htmlContent = fs.readFileSync(path.join(htmlDir, files[0].name), 'utf-8');

  // Find ZFcyjd container
  const containerStart = htmlContent.indexOf('class="ZFcyjd"');
  if (containerStart === -1) {
    throw new Error('AI Overview container (ZFcyjd) not found');
  }

  // Navigate to after the opening tag
  let i = containerStart;
  while (i < htmlContent.length && htmlContent[i] !== '>') i++;
  if (i >= htmlContent.length) throw new Error('Invalid ZFcyjd tag');
  i++;
  const contentStart = i;

  // Find matching closing </div> by counting nested divs
  let depth = 0;
  while (i < htmlContent.length) {
    if (htmlContent.substring(i, i + 5) === '<div ') {
      depth++;
      i += 5;
    } else if (htmlContent.substring(i, i + 6) === '</div>') {
      if (depth === 0) {
        const containerHtml = htmlContent.substring(contentStart, i);
        return processContainer(containerHtml);
      }
      depth--;
      i += 6;
    } else {
      i++;
    }
  }
  throw new Error('Could not find closing tag for ZFcyjd');
}

function processContainer(containerHtml) {
  // Remove script/style tags
  let text = containerHtml.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
                          .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '');

  // Replace block tags with newlines
  text = text.replace(/<\/(div|p|h1|h2|h3|h4|h5|h6|ul|ol|li|section|article)>\s*/gi, '\n')
             .replace(/<br\s*\/?>\s*/gi, '\n');

  // Remove all remaining HTML tags
  text = text.replace(/<[^>]+>/g, ' ');

  // Decode HTML entities
  text = text.replace(/&nbsp;/g, ' ')
             .replace(/&amp;/g, '&')
             .replace(/&lt;/g, '<')
             .replace(/&gt;/g, '>')
             .replace(/&quot;/g, '"')
             .replace(/&#39;/g, "'");

  // Collapse whitespace
  text = text.replace(/\s+\n/g, '\n')
             .replace(/\n\s+/g, '\n')
             .replace(/\n{3,}/g, '\n\n')
             .trim();

  const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);

  // Keep lines that:
  // - Contain Chinese characters
  // - Are reasonably long (more than 5 chars)
  // - Are not pure navigation/button text
  const meaningful = [];
  const skipPatterns = [
    /^来源[：:]/i,
    /^参考[：:]/i,
    /^查看全部$/i,
    /^全部显示$/i,
    /^复制$/i,
    /^分享$/i,
    /^反馈$/i,
    /^提交$/, /^关闭$/i,
    /^无障碍/, /^跳到主要/, /^翻译此页/,
    /^展开/, /^收起/,
    /^My Activity/, /^YouTube/, /^Wikipedia/,
    /^Copilot/, /^Perplexity/, /^ChatGPT/, /^Bing/,
    /^百度/, /^搜狗/, /^必应/,
    /^\d+$/, /^[\+\-\*]?\d+(\.\d+)?$/
  ];

  for (const line of lines) {
    // Skip if matches any skip pattern
    if (skipPatterns.some(p => p.test(line))) continue;
    // Skip if too short and doesn't contain Chinese
    if (line.length < 3 && !/[\u4e00-\u9fff]/.test(line)) continue;
    // Skip if only URL
    if (line.startsWith('http') && line.length < 80) continue;
    // Skip if all uppercase and short (likely button text)
    if (line.length < 20 && line === line.toUpperCase() && /^[A-Z\s]+$/.test(line)) continue;
    meaningful.push(line);
  }

  // Find title - should be early and short
  let title = 'Grok AI 概述';
  let contentStartIdx = 0;
  if (meaningful.length > 0 && meaningful[0].length < 60 && /[\u4e00-\u9fff]/.test(meaningful[0])) {
    title = meaningful[0];
    contentStartIdx = 1;
  }

  // Build content string
  let content = meaningful.slice(contentStartIdx).join('\n');
  if (!content.trim()) {
    // Fallback: use all meaningful lines even if short
    content = meaningful.join('\n');
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
        let url = hrefMatch[1]
          .replace(/&amp;/g, '&')
          .replace(/%3A/g, ':')
          .replace(/%2F/g, '/');
        const text = textMatch[1].trim();
        if (text.length > 1 && url.startsWith('http')) {
          sources.push(text + ': ' + url);
        }
      }
    }
  }

  return {
    content: '# ' + title + '\n\n' + content,
    sources: [...new Set(sources)].slice(0, 10)
  };
}

try {
  const result = extractAIFallback();
  const output = `# Grok AI 概述

> 来源：Google AI Overview (TestFlight 链接分享)

${result.content}

## 参考来源

${result.sources.length > 0 ? result.sources.join('\n') : '暂无来源'}

---

*本文档自动生成于 ${new Date().toISOString()}，使用 OpenClaw google ai-mode FLX 提取器*
`;

  const outputFile = process.argv[2] || path.join(
    process.env.HOME || '/Users/server',
    'Documents/zh.chinapedia/docs/ai/product/grok.md'
  );

  const outputDir = path.dirname(outputFile);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  fs.writeFileSync(outputFile, output, 'utf-8');
  console.log('✅ Successfully saved to: ' + outputFile);
  console.log('📄 Content length: ' + result.content.length + ' characters');
  console.log('🔗 Sources: ' + result.sources.length);
  process.exit(0);
} catch (error) {
  console.error('❌ Error:', error.message);
  process.exit(1);
}
