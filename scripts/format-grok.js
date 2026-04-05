#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const rawFile = '/Users/server/Documents/zh.chinapedia/docs/ai/product/grok.md';
const outFile = '/Users/server/Documents/zh.chinapedia/docs/ai/product/grok-clean.md';

const raw = fs.readFileSync(rawFile, 'utf-8');

// Parse YAML-like output: find content: and sources: blocks
let content = '';
let sources = '';

// Extract content block after 'content: >-'
const contentMatch = raw.match(/content:\s*>-?\s*([\s\S]*?)\s*sources:/);
if (contentMatch) {
  content = contentMatch[1].trim();
} else {
  // fallback: try to get text after first 'content:'
  const idx = raw.indexOf('content:');
  if (idx !== -1) {
    const after = raw.substring(idx);
    const end = after.indexOf('sources:');
    if (end !== -1) {
      content = after.slice(8, end).trim(); // 8 is length of 'content:'
    }
  }
}

// Extract sources block after 'sources: >-'
const sourcesMatch = raw.match(/sources:\s*>-?\s*([\s\S]*)/);
if (sourcesMatch) {
  sources = sourcesMatch[1].trim();
}

// Clean sources lines: split by \n and filter out navigation ones
const blocked = [
  '无障碍功能帮助', '地图', '航班', 'Google Play', 'Apple App Store',
  'YouTube', 'Wikipedia', 'My Activity', 'Privacy', 'Terms'
];
const sourceLines = sources.split('\n')
  .map(l => l.trim())
  .filter(l => l && !blocked.some(b => l.startsWith(b)))
  .map((l, i) => {
    // try to split text and url
    const parts = l.split(': ');
    if (parts.length >= 2) {
      const text = parts.slice(0, -1).join(': ');
      const url = parts[parts.length - 1];
      return `${i + 1}. **${text}**: ${url}`;
    }
    return l;
  });

const output = `# Grok AI 概述

> 来源：Google AI Overview (TestFlight 链接分享)

${content}

## 参考来源

${sourceLines.length > 0 ? sourceLines.join('\n') : '暂无来源'}

---

*本文档自动生成于 ${new Date().toISOString()}，使用 OpenCLAI google ai-mode 提取器*
`;

fs.writeFileSync(outFile, output, 'utf-8');
console.log('✅ Clean file generated:', outFile);
console.log('📄 Content length:', content.length);
console.log('🔗 Clean sources:', sourceLines.length);
