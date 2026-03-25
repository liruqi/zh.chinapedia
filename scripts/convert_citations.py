import re
import sys
import os

def convert_citations(content):
    # Skip if it already looks like it's been converted and has no more patterns to convert
    # Heuristic: If it has footnote definitions but NO old-style references at start of line
    # Actually, let's just do the conversion and check if anything changed.
    
    # 1. Convert reference list at the bottom: [n] content -> [^n]: content
    new_content = re.sub(r'(?m)^\[(\d+)\]\s+(.*)', r'[^\1]: \2', content)

    # 2. Convert in-text citations: [1, 2, 3] -> [^1] [^2] [^3]
    def replace_citation(match):
        citations = match.group(1).split(',')
        return ' '.join([f'[^{c.strip()}]' for c in citations])

    new_content = re.sub(r'(?<!\^|\[)\[(\d+(?:\s*,\s*\d+)*)\](?!\()', replace_citation, new_content)

    return new_content

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content = convert_citations(content)
        
        if new_content == content:
            print(f"Skipped (already converted or no citations): {filepath}")
            return False
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"MODIFIED: {filepath}")
        return True
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_citations.py <file1_or_dir> <file2_or_dir> ...")
        sys.exit(1)
    
    modified_count = 0
    skipped_count = 0
    
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            if process_file(arg):
                modified_count += 1
            else:
                skipped_count += 1
        elif os.path.isdir(arg):
            for root, dirs, files in os.walk(arg):
                for file in files:
                    if file.endswith((".md", ".mdx")):
                        if process_file(os.path.join(root, file)):
                            modified_count += 1
                        else:
                            skipped_count += 1
                            
    print(f"\nSummary: {modified_count} files modified, {skipped_count} files skipped.")
