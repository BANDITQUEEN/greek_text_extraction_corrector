"""Is the corrector stripping the second (enclitic-triggered) tonos?"""
import csv, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import lexicon_filter as LF

ACC = {"\u0301", "\u0300", "\u0342"}
ENCLITICS = {"μου","σου","του","της","μας","σας","τους","τις","το","τη","τον"}

def accents(w):
    d = unicodedata.normalize("NFD", w)
    return [i for i,c in enumerate(d) if c in ACC]

C = list(csv.DictReader(open("lexicon_corrections.csv", encoding="utf-8-sig")))
print(f"total corrections: {len(C):,}\n")

cand = []
for r in C:
    o, n = r["original"], r["replacement"]
    ao, an = len(accents(o)), len(accents(n))
    if ao == 2 and an == 1 and len(o) == len(n) + 0 and o[:-1] == n[:-1] == o[:len(n)-0] :
        pass
    # simpler: original has 2 accented vowels, replacement has 1 fewer accent,
    # and stripping the LAST accent of the original reproduces the replacement
    if ao - an != 1:
        continue
    do = unicodedata.normalize("NFD", o)
    dn = unicodedata.normalize("NFD", n)
    # remove the final combining accent from o and renormalize; compare to n
    idx = accents(o)
    if not idx:
        continue
    last = idx[-1]
    stripped = unicodedata.normalize("NFC", do[:last] + do[last+1:])
    if stripped == n:
        cand.append(r)

print(f"corrections that strip exactly the LAST tonos: {len(cand):,}\n")

# how many of these are immediately followed by an enclitic in the source text?
PAGE_CACHE = {}
def page_text(fname, page_start_char):
    pass

byfile = {}
for r in cand:
    byfile.setdefault(r["filename"], []).append(r)

hit = miss = 0
examples_hit = Counter(); examples_miss = Counter()
import re
LETTER = re.compile(r"[^\W\d_]+")
for fname, rows in byfile.items():
    path = LF.INPUT_DIR / fname
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    for r in rows:
        start = int(r["page_char_start"])
        # page_char_start is relative to the PAGE chunk, not the file; instead
        # just search near the original token in the raw text as a proxy
        idx = text.find(r["original"])
        if idx == -1:
            continue
        tail = text[idx+len(r["original"]): idx+len(r["original"])+15]
        nxt = LETTER.match(tail.lstrip())
        nxt_word = nxt.group(0).lower() if nxt else ""
        if nxt_word in ENCLITICS:
            hit += 1
            examples_hit[(r["original"], r["replacement"], nxt_word)] += 1
        else:
            miss += 1
            examples_miss[(r["original"], r["replacement"], nxt_word)] += 1

print(f"followed by an enclitic (μου/σου/του/της/μας/σας/τους...): {hit:,}")
print(f"NOT followed by an enclitic: {miss:,}\n")
print("--- confirmed enclitic-doubling cases wrongly 'corrected' ---")
for (o,n,w),c in examples_hit.most_common(20):
    print(f"   {o:16s} -> {n:16s}   (before '{w}')   x{c}")
print("\n--- same shape, but no enclitic follows (likely genuine typos) ---")
for (o,n,w),c in examples_miss.most_common(10):
    print(f"   {o:16s} -> {n:16s}   (before '{w!r}')   x{c}")
