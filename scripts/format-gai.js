#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

// Usage: node format-gai.js <input-tmp-file> <output-markdown-file> [query]
const [, , inputFile, outputFile, query = 'AI'] = process.argv;

if (!inputFile || !outputFile) {
  console.log('Usage: node format-gai.js <input-tmp-file> <output-markdown-file> [query]');
  console.log('  input-tmp-file: OpenCLI raw output (e.g., grok.tmp)');
  console.log('  output-markdown-file: final markdown path');
  console.log('  query: optional, for title, default "AI"');
  process.exit(0);
}

const raw = fs.readFileSync(inputFile, 'utf-8');

// Parse YAML-like output
let content = '';
let sources = '';
const lines = raw.split('\n');
let inContent = false, inSources = false;
const contentLines = [], sourceLines = [];

for (const lineRaw of lines) {
  const line = lineRaw.trimEnd();
  const clean = line.trim();

  if (clean.startsWith('content:')) {
    inContent = true;
    // Extract content after colon; handle quoted string with \n escapes
    let afterColon = line.substring(line.indexOf(':') + 1).trim();
    if (afterColon.startsWith('"') && afterColon.endsWith('"')) {
      afterColon = afterColon.slice(1, -1);
    }
    // Replace escaped newlines with actual newlines
    afterColon = afterColon.replace(/\\n/g, '\n');
    if (afterColon) {
      contentLines.push(afterColon);
    }
    continue;
  }
  if (inContent && clean.startsWith('sources:')) {
    inContent = false;
    inSources = true;
    continue;
  }
  if (inContent) {
    contentLines.push(line);
    continue;
  }
  if (inSources) {
    if (clean === '' || clean.startsWith('-') || clean.startsWith('Update available:')) break;
    sourceLines.push(line);
  }
}

content = contentLines.join('\n').trim();
sources = sourceLines.join('\n').trim();

// Filter content: keep Chinese lines and citations, remove UI noise
const filteredContent = content
  .split('\n')
  .map(l => l.trim())
  .filter(l => {
    if (!l) return false;
    // Drop UI noise
    if (l.includes('来自网络的快速搜索结果') || l.includes('个网站') || l.includes('分钟前') ||
        l.includes('搜索结果') || l.includes('几秒钟前') || l.includes('仅显示') ||
        l.includes('My Activity') || l.includes('Copy')) return false;
    // Keep Chinese lines (len>=2) and citation markers
    if (/[\u4e00-\u9fff]/.test(l) && l.length >= 2) return true;
    if (/^\[\d+,\s*\d+\]$/.test(l) || /^\[\d+\]$/.test(l)) return true;
    return false;
  })
  .join('\n');

// Parse sources: split on literal \n and merge broken pairs
const rawSourceItems = sources.split('\\n').map(s => s.trim()).filter(Boolean);
const mergedSources = [];
for (let i = 0; i < rawSourceItems.length; i++) {
  let cur = rawSourceItems[i];
  if (cur.endsWith(':') && i + 1 < rawSourceItems.length && rawSourceItems[i+1].startsWith('http')) {
    cur = cur + ' ' + rawSourceItems[i+1];
    i++;
  }
  mergedSources.push(cur);
}

// Keep only valid domains
const validDomains = ['x.ai', 'grok.com', 'play.google.com', 'apps.apple.com', 'elastic.co', 'github.com', 'stepfun.com', 'step.fun'];
const sourceEntries = mergedSources.filter(l => {
  if (!l.includes('http')) return false;
  if (l.includes('support.google.com') || l.includes('maps.google.com') || l.includes('travel.google.com')) return false;
  return validDomains.some(d => l.toLowerCase().includes(d));
});

// Format each source
const formattedSources = sourceEntries.map(entry => {
  const idx = entry.indexOf(': ');
  if (idx !== -1 && idx < entry.length - 2) {
    const label = entry.slice(0, idx);
    const url = entry.slice(idx + 2);
    return `**${label}**: ${url}`;
  }
  return entry;
});

// Build title from query
const title = query.charAt(0).toUpperCase() + query.slice(1);

const output = `# ${title}

${filteredContent}

## 参考来源

${formattedSources.length > 0 ? formattedSources.join('\n') : '暂无来源'}

---

*本文档自动生成于 ${new Date().toISOString()}，使用 OpenCLI google ai-mode 提取器*
`;

fs.writeFileSync(outputFile, output, 'utf-8');
console.log('✅ Clean file generated:', outputFile);
console.log('📄 Content length:', filteredContent.length);
console.log('🔗 Clean sources:', formattedSources.length);
