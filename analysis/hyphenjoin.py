"""Which hyphen-at-line-break splits are really one word, and can we prove it?"""
import re, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import lexicon_filter as LF

SPLIT = re.compile(r"([^\W\d_]+)-[ \t]*\n[ \t]*([^\W\d_]+)")
lex = LF.make_correction_lexicon(LF.ROUTE)

def joins_to_word(a, b):
    """The joined form, if the dictionary confirms it (allowing a second tonos)."""
    joined = a + b
    if lex.knows(joined):
        return joined
    # the tail may carry an enclitic-triggered accent the dictionary lacks
    d = unicodedata.normalize("NFD", joined)
    if d and d[-1] in LF.ACCENT_MARKS:
        base = unicodedata.normalize("NFC", d[:-1])
        if lex.knows(base):
            return joined
    return None

true_join = Counter(); false_join = Counter()
a_is_word = 0
for path in sorted(LF.INPUT_DIR.glob("*.txt")):
    text = path.read_text(encoding="utf-8")
    for m in SPLIT.finditer(text):
        a, b = m.group(1), m.group(2)
        if not (LF.GREEK_RE.search(a) and LF.GREEK_RE.search(b)):
            continue
        j = joins_to_word(a, b)
        if j:
            true_join[(a, b, j)] += 1
            if lex.knows(a):
                a_is_word += 1
        else:
            false_join[(a, b)] += 1

nt = sum(true_join.values()); nf = sum(false_join.values())
print(f"\nsplits examined            : {nt+nf:,}")
print(f"  join to a real word      : {nt:,}   <- rejoin these")
print(f"  do not                   : {nf:,}   <- leave alone (real dashes)")
print(f"  of the true joins, first half was itself already a word: {a_is_word:,}")
print("\n--- true joins (one word broken across a line) ---")
for (a, b, j), n in true_join.most_common(18):
    print(f"   {a}- + {b}   ->  {j}   x{n}")
print("\n--- correctly rejected (dash between two whole words) ---")
for (a, b), n in false_join.most_common(6):
    print(f"   {a}- + {b}   x{n}")
