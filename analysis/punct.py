"""Test the rule: a token carrying more than N punctuation marks is garbage."""
import re, sys, unicodedata
from collections import Counter
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0,".")
import lexicon_filter as LF

TOK=re.compile(r"\S+")
def punct_count(t):
    # marks strictly inside the token; leading/trailing are ordinary sentence
    # punctuation and say nothing about the word itself
    core=t.strip("".join(c for c in t if unicodedata.category(c).startswith(("P","S"))))
    return sum(1 for c in core if unicodedata.category(c).startswith(("P","S")))

files=[p for p in LF.INPUT_DIR.glob("*.txt")]
sample=[LF.INPUT_DIR/"10795_123_123_01_Glossa.txt"]
tokens=Counter()
for p in sample:
    for t in TOK.findall(p.read_text(encoding="utf-8")):
        tokens[t]+=1

print(f"the Glossa file: {sum(tokens.values()):,} whitespace tokens, {len(tokens):,} distinct\n")
buckets=Counter()
examples={}
for t,n in tokens.items():
    k=min(punct_count(t),4)
    buckets[k]+=n
    examples.setdefault(k,[]).append(t)
for k in sorted(buckets):
    lab=f"{k}" if k<4 else "4+"
    print(f"  inner punctuation = {lab}: {buckets[k]:>8,} tokens   e.g. {', '.join(examples[k][:7])}")

print("\n=== what a '>2 inner punctuation -> delete' rule would remove, corpus-wide ===")
kill=keep=0; killex=Counter(); risky=Counter()
for p in files:
    for t in TOK.findall(p.read_text(encoding="utf-8")):
        if punct_count(t)>2:
            kill+=1; killex[t]+=1
            # would we be destroying something with real letters in it?
            letters=sum(1 for c in t if c.isalpha())
            if letters>=4 and any(c.isdigit() for c in t)==False:
                risky[t]+=1
        else:
            keep+=1
print(f"  delete {kill:,} of {kill+keep:,} tokens ({kill/(kill+keep):.3%})")
print(f"\n  most-deleted:")
for t,n in killex.most_common(14): print(f"     {t!r:34s} x{n:,}")
print(f"\n  of those, tokens holding 4+ letters and no digits ({sum(risky.values()):,}) -- check these are really garbage:")
for t,n in risky.most_common(14): print(f"     {t!r:34s} x{n:,}")
