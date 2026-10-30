import csv, sys, re, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
C=list(csv.DictReader(open("lexicon_corrections.elpass.csv",encoding="utf-8-sig")))
n=len(C)

def titlecase(w): return len(w)>1 and w[0].isupper() and w[1:].islower()
def allcaps(w):   return len(w)>1 and w.isupper()

cap=[r for r in C if titlecase(r["original"])]
mid=[r for r in cap if int(r["page_char_start"])>3]
print(f"total corrections            : {n:,}")
print(f"  original is Title-Case     : {len(cap):,} ({len(cap)/n:5.1%})   <- proper-noun candidates")
print(f"  ...and not at line start   : {len(mid):,} ({len(mid)/n:5.1%})   <- strongest proxy")
print(f"  original is ALL-CAPS       : {sum(1 for r in C if allcaps(r['original'])):,}")

print("\n--- the mid-line capitalised ones, most frequent ---")
for (o,rp),c in Counter((r["original"],r["replacement"]) for r in mid).most_common(14):
    print(f"    {o:20s} -> {rp:20s} x{c}")

# how many of those look like real damage vs a name?
def damaged(t): return "ς" in t[:-1] or "ϊ" in t or "ϋ" in t or "ΰ" in t or "ΐ" in t
d=sum(1 for r in mid if damaged(r["original"]))
print(f"\n  of {len(mid):,} mid-line capitalised corrections, {d:,} ({d/max(len(mid),1):.1%}) carry")
print( "  visible encoding damage -- those are real repairs a name-gate would wrongly block")
