import csv, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
B=""
def load(f):
    return list(csv.DictReader(open(B+f,encoding="utf-8-sig")))
old=load("lexicon_corrections.elpass.csv")
p30=load("lexicon_corrections__p30.csv")
s30=load("lexicon_corrections__s30.csv")
files={r["filename"] for r in p30}
old=[r for r in old if r["filename"] in files]
def key(r): return (r["filename"],r["page_char_start"],r["original"])
K=lambda rs:{key(r):r for r in rs}
O,P,S=K(old),K(p30),K(s30)
print(f"on the same 30 files:  old {len(O):,}   p30 {len(P):,}   s30 {len(S):,}\n")

def damaged(t): return "ς" in t[:-1] or any(c in t for c in "ϊϋΐΰ")
def titlecase(w): return len(w)>1 and w[0].isupper() and w[1:].islower()

for label,new,base in [("p30 adds over old", P, O), ("s30 adds over p30", S, P)]:
    add=[new[k] for k in new if k not in base]
    dmg=sum(1 for r in add if damaged(r["original"]))
    cap=sum(1 for r in add if titlecase(r["original"]))
    print(f"--- {label}: {len(add):,} new corrections")
    print(f"      visibly damaged source : {dmg:,} ({dmg/max(len(add),1):5.1%})  <- likely good")
    print(f"      capitalised source     : {cap:,} ({cap/max(len(add),1):5.1%})  <- likely names")
    for (o,r),n in Counter((x["original"],x["replacement"]) for x in add).most_common(8):
        print(f"        {o:20s} -> {r:20s} x{n}")
    print()

lost=[P[k] for k in P if k not in S]
print(f"--- s30 drops {len(lost):,} that p30 made (spaCy NER was gating these)")
for (o,r),n in Counter((x["original"],x["replacement"]) for x in lost).most_common(8):
    print(f"        {o:20s} -> {r:20s} x{n}")

print("\n--- the names you flagged ---")
print(f"{'token':16s} {'old':>10s} {'p30':>10s} {'s30':>10s}")
for w in ["Νοφαλιά","Ντούλκα","Καρπάθικο","Μελανίντ","Νεόφρων","Μπέρμπερ","Πότερον"]:
    c=lambda D: sum(1 for r in D.values() if r["original"]==w)
    print(f"{w:16s} {c(O):>10} {c(P):>10} {c(S):>10}")
