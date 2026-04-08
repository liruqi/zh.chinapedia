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

function formattedLabel(entry) {
  const idx = entry.indexOf(': ');
  if (idx !== -1 && idx < entry.length - 2) {
    const label = entry.slice(0, idx);
    const url = entry.slice(idx + 2);
    return `**${label}**: ${url}`;
  }
  return entry;
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
    let afterColon = line.substring(line.indexOf(':') + 1).trim();
    if (afterColon.startsWith('"') && afterColon.endsWith('"')) {
      afterColon = afterColon.slice(1, -1);
    }
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

// 1) Split into lines
let contentLinesArr = content.split('\n').map(l => l.trim());

// 2) Remove pure-English lines (no Chinese chars) unless they contain citation numbers
contentLinesArr = contentLinesArr.filter(l => {
  if (!l) return false;
  // Keep if contains Chinese
  if (/[\u4e00-\u9fff]/.test(l)) return true;
  // Keep citation markers like [24, 10]
  if (/^\[\d+,\s*\d+\]$/.test(l) || /^\[\d+\]$/.test(l)) return true;
  // Otherwise drop (pure English/non-Chinese)
  return false;
});

// 3) Remove known noise patterns
contentLinesArr = contentLinesArr.filter(l => {
  if (l.includes('来自网络的快速搜索结果') || l.includes('个网站') || l.includes('分钟前') ||
      l.includes('搜索结果') || l.includes('几秒钟前') || l.includes('仅显示') ||
      l.includes('My Activity') || l.includes('Copy')) return false;
  // Drop lines that are only App Store/Google Play titles (shorter than 40 chars)
  if ((/App Store/.test(l) || /Google Play/.test(l)) && l.length < 40) return false;
  return true;
});

// 4) Deduplicate adjacent similar lines (fuzzy: 80% overlap or exact)
const deduped = [];
for (let i = 0; i < contentLinesArr.length; i++) {
  const cur = contentLinesArr[i];
  const prev = deduped[deduped.length - 1];
  if (prev) {
    // Exact duplicate
    if (cur === prev) continue;
    // High overlap (>80% and length similar)
    const len = Math.max(cur.length, prev.length);
    if (len > 0) {
      // Simple character overlap
      let overlap = 0;
      const minLen = Math.min(cur.length, prev.length);
      for (let j = 0; j < minLen; j++) {
        if (cur[j] === prev[j]) overlap++;
      }
      if (overlap / len > 0.8 && Math.abs(cur.length - prev.length) < 10) continue;
    }
  }
  deduped.push(cur);
}

const filteredContent = deduped.join('\n');

// Parse sources
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

const validDomains = ['x.ai', 'grok.com', 'play.google.com', 'apps.apple.com', 'elastic.co', 'github.com', 'stepfun.com', 'step.fun'];
const sourceEntries = mergedSources.filter(l => {
  if (!l.includes('http')) return false;
  if (l.includes('support.google.com') || l.includes('maps.google.com') || l.includes('travel.google.com')) return false;
  return validDomains.some(d => l.toLowerCase().includes(d));
});

const footnotes = sourceEntries.map((entry, idx) => `[^${idx + 1}]: ${formattedLabel(entry)}`);

const title = query.charAt(0).toUpperCase() + query.slice(1);

const output = `# ${title}

${filteredContent}

## 参考来源

${footnotes.length > 0 ? footnotes.join('\n') : '暂无来源'}

---

*本文档基于 Google AI Overview 自动生成，原始数据来源见上方脚注。*
`;

fs.writeFileSync(outputFile, output, 'utf-8');
console.log('✅ Clean file generated:', outputFile);
console.log('📄 Content length:', filteredContent.length);
console.log('🔗 Num sources:', footnotes.length);
