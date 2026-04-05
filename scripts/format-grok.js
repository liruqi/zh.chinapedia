#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const rawFile = '/Users/server/Documents/zh.chinapedia/docs/ai/product/grok.tmp';
const outFile = '/Users/server/Documents/zh.chinapedia/docs/ai/product/grok.md';

const raw = fs.readFileSync(rawFile, 'utf-8');

// Parse YAML-like output
let content = '';
let sources = '';
const lines = raw.split('\n');
let inContent = false, inSources = false;
const contentLines = [], sourceLines = [];

for (const lineRaw of lines) {
  const line = lineRaw.trimEnd();
  const clean = line.trim();

  if (clean.startsWith('content:')) { inContent = true; continue; }
  if (inContent && clean.startsWith('sources:')) { inContent = false; inSources = true; continue; }
  if (inContent) { contentLines.push(line); continue; }
  if (inSources) {
    if (clean === '' || clean.startsWith('-') || clean.startsWith('Update available:')) break;
    sourceLines.push(line);
  }
}

content = contentLines.join('\n').trim();
sources = sourceLines.join('\n').trim();

// Filter content: keep Chinese lines (>=5 chars) and citation numbers
const filteredContent = content
  .split('\n')
  .map(l => l.trim())
  .filter(l => {
    if (!l) return false;
    // Drop known persistent noise that survived extraction
    if (l.includes('来自网络的快速搜索结果') || l.includes('个网站') || l.includes('分钟前') || l.includes('搜索结果') || l.includes('几秒钟前') || l.includes('仅显示') || l.includes('My Activity')) return false;
    // Keep Chinese lines (len>=2) and citations
    if (/[\u4e00-\u9fff]/.test(l) && l.length >= 2) return true;
    if (/^\[\d+,\s*\d+\]$/.test(l) || /^\[\d+\]$/.test(l)) return true;
    return false;
  })
  .join('\n');

// Parse sources: may contain literal \n; split and keep valid domains
const rawSourceItems = sources.split('\\n').map(s => s.trim()).filter(Boolean);

// Merge split pairs: if a line ends with ':' and next starts with 'http', combine them
const mergedSources = [];
for (let i = 0; i < rawSourceItems.length; i++) {
  let cur = rawSourceItems[i];
  if (cur.endsWith(':') && i + 1 < rawSourceItems.length && rawSourceItems[i+1].startsWith('http')) {
    cur = cur + ' ' + rawSourceItems[i+1];
    i++; // skip the URL line
  }
  mergedSources.push(cur);
}
const validDomains = ['x.ai', 'grok.com', 'play.google.com', 'apps.apple.com', 'elastic.co', 'github.com'];
const sourceEntries = mergedSources.filter(l => {
  if (!l.includes('http')) return false;
  if (l.includes('support.google.com') || l.includes('maps.google.com') || l.includes('travel.google.com')) return false;
  return validDomains.some(d => l.includes(d));
});

// Format each source as **Label**: URL if it contains ': ', else as plain
const formattedSources = sourceEntries.map(entry => {
  const idx = entry.indexOf(': ');
  if (idx !== -1 && idx < entry.length - 2) {
    const label = entry.slice(0, idx);
    const url = entry.slice(idx + 2);
    return `**${label}**: ${url}`;
  }
  return entry;
});

const output = `# Grok AI 概述

${filteredContent}

## 参考来源

${formattedSources.length > 0 ? formattedSources.join('\n') : '暂无来源'}

---

*本文档自动生成于 ${new Date().toISOString()}，使用 OpenCLI google ai-mode 提取器*
`;

fs.writeFileSync(outFile, output, 'utf-8');
console.log('✅ Clean file generated:', outFile);
console.log('📄 Content length:', filteredContent.length);
console.log('🔗 Clean sources:', formattedSources.length);
