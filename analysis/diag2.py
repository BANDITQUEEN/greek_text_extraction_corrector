import csv, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import spacy

C=list(csv.DictReader(open("lexicon_corrections.elpass.csv",encoding="utf-8-sig")))
freq={}
for line in open("lexicons/el.txt",encoding="utf-8"):
    p=line.rstrip("\n").rsplit(" ",1)
    if len(p)==2 and p[1].isdigit(): freq[unicodedata.normalize("NFC",p[0])]=int(p[1])
def f(w):
    n=unicodedata.normalize("NFC",w)
    return max(freq.get(n,0),freq.get(n.lower(),0),freq.get(n.capitalize(),0))

print("=== the margin guard, one pass later ===")
empty=sum(1 for r in C if not r["runner_up"])
print(f"  corrections with NO runner-up: {empty:,} of {len(C):,} ({empty/len(C):.1%})")
print("  -> a lone candidate is still auto-accepted; the guard has never rejected anything\n")

print("=== frequency of the word being corrected TO ===")
b=Counter()
for r in C:
    v=f(r["replacement"])
    b["0 (absent)" if v==0 else "1-49" if v<50 else "50-499" if v<500 else "500-4,999" if v<5000 else "5,000+"]+=1
for k in ["0 (absent)","1-49","50-499","500-4,999","5,000+"]:
    print(f"  {k:12s} {b[k]:>7,} ({b[k]/len(C):5.1%})")

print("\n=== would spaCy have protected the names? ===")
nlp=spacy.load("el_core_news_md")
for s in ["Ο Νεόφρων είναι πουλί.","Η Μελανίντ ήρθε.","Ο Μπέρμπερ μίλησε.","Η Νοφαλιά είναι χωριό."]:
    for t in nlp(s):
        if t.text in {"Νεόφρων","Μελανίντ","Μπέρμπερ","Νοφαλιά"}:
            print(f"  {t.text:12s} pos={t.pos_:6s} ent={t.ent_type_ or '-':8s} -> protected={bool(t.ent_type_ or t.pos_=='PROPN')}")

print("\n=== how many corrections only change the ending? ===")
def endswap(o,r):
    if o==r: return False
    k=0
    while k<min(len(o),len(r)) and o[k]==r[k]: k+=1
    return k>=max(len(o),len(r))-2 and k>=4
n=sum(1 for r in C if endswap(r["original"],r["replacement"]))
print(f"  shared stem, differing only in the last 1-2 characters: {n:,} ({n/len(C):.1%})")
for (o,rp),c in Counter((r["original"],r["replacement"]) for r in C if endswap(r["original"],r["replacement"])).most_common(8):
    print(f"    {o:22s} -> {rp:22s} x{c}")
