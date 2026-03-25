import re
import sys
import os

def convert_citations(content):
    # 1. Convert reference list at the bottom: [n] content -> [^n]: content
    # Look for lines starting with [n] followed by a space or tab
    content = re.sub(r'(?m)^\[(\d+)\]\s+(.*)', r'[^\1]: \2', content)

    # 2. Convert in-text citations: [1, 2, 3] -> [^1][^2][^3]
    # We need to be careful not to match the footnote definitions we just created.
    # We'll use a regex that looks for [n] or [n, m, ...] BUT NOT preceded by ^ (start of line)
    # Actually, a better way is to find all [n, m] patterns and replace them if they aren't part of a link or footnote definition.
    
    def replace_citation(match):
        citations = match.group(1).split(',')
        return ' '.join([f'[^{c.strip()}]' for c in citations])

    # Pattern: [ followed by digits and commas, followed by ]
    # Ensure it's not a footnote definition (which now starts with [^n]:)
    # And not a link title [link](url)
    content = re.sub(r'(?<!\^|\[)\[(\d+(?:\s*,\s*\d+)*)\](?!\()', replace_citation, content)

    return content

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = convert_citations(content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Processed: {filepath}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_citations.py <file1> <file2> ...")
        sys.exit(1)
    
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            process_file(arg)
        elif os.path.isdir(arg):
            for root, dirs, files in os.walk(arg):
                for file in files:
                    if file.endswith(".md") or file.endswith(".mdx"):
                        process_file(os.path.join(root, file))
