"""Distinct punctuation KINDS inside a token, not the count."""
import re, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import lexicon_filter as LF

TOK=re.compile(r"\S+")
def is_p(c): return unicodedata.category(c).startswith(("P","S"))
def inner(t):
    core=t.strip("".join(c for c in t if is_p(c)))
    return [c for c in core if is_p(c)]
# a dotted acronym or a hyphenated compound uses one kind of mark, repeatedly
def kinds(t): return len({c for c in inner(t)} - {".", "-", "\u2010", "/"})

files=list(LF.INPUT_DIR.glob("*.txt"))
kill=Counter(); keep_acr=Counter(); total=0
for p in files:
    for t in TOK.findall(p.read_text(encoding="utf-8")):
        total+=1
        if kinds(t)>=2: kill[t]+=1
        elif len(inner(t))>2: keep_acr[t]+=1

print(f"rule: >=2 DISTINCT punctuation kinds inside the token (periods, hyphens and slashes excluded)")
print(f"  deletes {sum(kill.values()):,} of {total:,} tokens ({sum(kill.values())/total:.4%})\n")
print("  most-deleted:")
for t,n in kill.most_common(20): print(f"     {t!r:40s} x{n:,}")
print(f"\n  now SAFE that the count-based rule would have deleted ({sum(keep_acr.values()):,}):")
for t,n in keep_acr.most_common(12): print(f"     {t!r:40s} x{n:,}")

print("\n  your examples:")
for t in ["α(λ.α]θΙ","ντο»νια^ά","<χ\κ<χρί","0Λ)(λ.αλά","α|λ.α.]θέ","τ\ο»^","νΐϊώΐΑί",
          "Ε.Σ.Α.μεΑ.","Ο.Α.Ε.Δ.","1.1.2.Β.","απο-κλειστικές","21/3/2007","e-mail:"]:
    print(f"     {t!r:24s} kinds={kinds(t)}  -> {'DELETE' if kinds(t)>=2 else 'keep'}")
