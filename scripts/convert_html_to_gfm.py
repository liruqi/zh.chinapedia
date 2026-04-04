#!/usr/bin/env python3
"""Convert HTML file to GFM Markdown with frontmatter."""

import sys
import re
from pathlib import Path

def html_to_markdown(html: str) -> str:
    """Basic HTML to Markdown conversion."""
    # Remove scripts, styles, and hidden elements
    html = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<link[^>]*>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<svg[^>]*>.*?</svg>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<path[^>]*>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<div[^>]*style="display:\s*none"[^>]*>.*?</div>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<div[^>]*style="visibility:\s*hidden"[^>]*>.*?</div>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<div[^>]*class="[^"]*\bnone\b[^"]*"[^>]*>.*?</div>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Extract text by removing most tags
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<h[1-6][^>]*>', '\n\n#', text, flags=re.IGNORECASE)
    text = re.sub(r'</h[1-6]>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<strong[^>]*>', '**', text, flags=re.IGNORECASE)
    text = re.sub(r'</strong>', '**', text, flags=re.IGNORECASE)
    text = re.sub(r'<b[^>]*>', '**', text, flags=re.IGNORECASE)
    text = re.sub(r'</b>', '**', text, flags=re.IGNORECASE)
    text = re.sub(r'<em[^>]*>', '*', text, flags=re.IGNORECASE)
    text = re.sub(r'</em>', '*', text, flags=re.IGNORECASE)
    text = re.sub(r'<i[^>]*>', '*', text, flags=re.IGNORECASE)
    text = re.sub(r'</i>', '*', text, flags=re.IGNORECASE)
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>', '[\1](', text, flags=re.IGNORECASE)
    text = re.sub(r'</a>', ')', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '- ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<ul[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</ul>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<ol[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</ol>', '', text, flags=re.IGNORECASE)

    # Remove remaining tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    text = text.replace('&#x2019;', "'").replace('&#x201C;', '"').replace('&#x201D;', '"')
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')

    # Clean up whitespace
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text

def main():
    html_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else html_file.with_suffix('.md')

    html = html_file.read_text(encoding='utf-8')

    # Extract title from <title> or from Claude Code heading
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    title = "Claude Code Overview" if not title_match else re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

    # Extract description
    desc_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.IGNORECASE)
    description = "Google AI Overview search result for Claude Code" if not desc_match else desc_match.group(1).strip()

    # Convert to Markdown
    content = html_to_markdown(html)

    # Build GFM with frontmatter
    frontmatter = f"""---
title: {title}
description: {description}
date: {Path(__file__).stat().st_mtime}
source: Google AI Overview
---

"""
    markdown = frontmatter + content

    output_file.write_text(markdown, encoding='utf-8')
    print(f"✓ Converted: {output_file} ({len(content)} chars)")

if __name__ == '__main__':
    main()
