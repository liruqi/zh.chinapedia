import re, sys, io

def audit(path):
    raw = open(path, "rb").read()
    crlf = raw.count(b"\r\n"); lf = raw.count(b"\n")
    txt = raw.decode("utf-8")
    defs = re.findall(r"^\[\^(\d+)\]:\s*(.*)$", txt, re.M)
    refs = set(re.findall(r"\[\^(\d+)\](?!:)", txt))
    empty = [n for n, b in defs if not b.strip()]
    nourl = [(n, b.strip()[:80]) for n, b in defs if not re.search(r"https?://|doi\.org|arxiv", b)]
    print("== %s" % path)
    print("   bytes=%d  CRLF=%d  LF=%d" % (len(raw), crlf, lf))
    print("   footnote defs=%d  refs=%d  empty=%d  no-url=%d" % (len(defs), len(refs), len(empty), len(nourl)))
    for n, b in nourl:
        print("      [^%s] %s" % (n, b))
    missing = sorted(set(int(x) for x in refs) - set(int(n) for n, _ in defs))
    if missing: print("   !! refs without def: %s" % missing)
    print()

for p in sys.argv[1:]:
    audit(p)
