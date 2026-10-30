import sys, re, csv
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import lexicon_filter as LF
raw=(LF.INPUT_DIR/"10795_1013_1013.txt").read_text(encoding="utf-8")
i=raw.find("θαίνει")
print("=== the page-break split you found ===")
print(repr(raw[max(0,i-260):i+40]))

print("\n=== how often does a page end mid-word? ===")
parts=LF.split_pages(raw)
n=dangling=0
for is_sep,c in parts:
    if is_sep: continue
    n+=1
    if re.search(r"[^\W\d_]-\s*$", c): dangling+=1
print(f"  this file: {dangling} of {n} pages end with a hyphenated part-word")

tot=dang=0
for p in sorted(LF.INPUT_DIR.glob("*.txt")):
    for is_sep,c in LF.split_pages(p.read_text(encoding="utf-8")):
        if is_sep: continue
        tot+=1
        if re.search(r"[^\W\d_]-\s*$", c): dang+=1
print(f"  corpus  : {dang:,} of {tot:,} pages ({dang/tot:.1%}) end mid-word")

print("\n=== can the corrector ever see across that boundary? ===")
print("  split_pages() makes each page a separate chunk, and nlp.pipe() receives")
print("  them as independent documents. The two halves are never in the same doc,")
print("  so the fragment is judged entirely on its own.")
