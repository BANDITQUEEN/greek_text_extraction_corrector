"""Can unrecoverable OCR garbage be told apart from legitimate unknown words?"""
import csv, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")

U=[r for r in csv.DictReader(open("lexicon_unresolved__p30.csv",encoding="utf-8-sig"))]
nc=[r for r in U if r["reason"]=="no-candidate"]
print(f"no-candidate tokens kept: {len(nc):,}\n")

def caps_inside(t):
    return any(c.isupper() for c in t[1:])
def diacritic_density(t):
    d=unicodedata.normalize("NFD",t)
    marks=sum(1 for c in d if unicodedata.combining(c))
    letters=sum(1 for c in d if not unicodedata.combining(c))
    return marks/max(letters,1)
def dialytika(t):
    return sum(1 for c in t if c in "ϊϋΐΰΪΫ")

tests={
 "uppercase letter after the first": lambda t: caps_inside(t) and not t.isupper(),
 "diacritics on >60% of letters":    lambda t: diacritic_density(t)>0.6,
 "2+ dialytika":                     lambda t: dialytika(t)>=2,
 "any of the three":                 lambda t: (caps_inside(t) and not t.isupper()) or diacritic_density(t)>0.6 or dialytika(t)>=2,
}
for name,fn in tests.items():
    hits=[r for r in nc if fn(r["token"])]
    uniq=Counter(r["token"] for r in hits)
    print(f"{name:34s} {len(hits):>7,} rows ({len(hits)/len(nc):5.1%})  {len(uniq):,} distinct")
    print(f"{'':34s} e.g. {', '.join(list(uniq)[:8])}")

print("\n--- what the 'any of the three' rule would NOT catch (top kept tokens) ---")
flagged={r["token"] for r in nc if tests["any of the three"](r["token"])}
rest=Counter(r["token"] for r in nc if r["token"] not in flagged)
for t,n in rest.most_common(18): print(f"    {t:20s} x{n:,}")
