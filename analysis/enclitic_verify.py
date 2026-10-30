"""Replay the current corrections against the new enclitic gate."""
import csv, re, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import lexicon_filter as LF

lex = LF.make_correction_lexicon(LF.ROUTE)
C = list(csv.DictReader(open("lexicon_corrections.csv", encoding="utf-8-sig")))
LETTER = re.compile(r"[^\W\d_]+")

def next_word(fname, original):
    path = LF.INPUT_DIR / fname
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    idx = text.find(original)
    if idx == -1:
        return ""
    tail = text[idx + len(original): idx + len(original) + 15].lstrip()
    m = LETTER.match(tail)
    # lower(), never casefold(): casefold maps a final sigma to a medial one,
    # so "τους" would arrive as "τουσ" and match no enclitic at all.
    return m.group(0).lower() if m else ""

def would_protect(word, nxt):
    return LF.is_enclitic_doubling(word, nxt, lex)

n_protect = n_leave = 0
examples_protect = Counter()
for r in C:
    nxt = next_word(r["filename"], r["original"])
    if would_protect(r["original"], nxt):
        n_protect += 1
        examples_protect[(r["original"], r["replacement"], nxt)] += 1
    else:
        n_leave += 1

print(f"corrections replayed: {len(C):,}")
print(f"now protected by the enclitic rule: {n_protect:,}")
print(f"still corrected as before          : {n_leave:,}\n")
print("--- newly protected (should be genuine enclitic doubling) ---")
for (o, n, w), c in examples_protect.most_common(25):
    print(f"   {o:20s} (was -> {n:18s})  before '{w}'   x{c}")
