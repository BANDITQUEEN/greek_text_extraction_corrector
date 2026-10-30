"""Find which (wrong-decode, right-decode) pair recovers real Greek words.

Legacy Greek arrives already decoded with the wrong table: encode it back to
the bytes that produced it, then decode with the table that was meant. A pair
is credible only if what comes out is in the dictionary.
"""
import re, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import lexicon_filter as LF

# what the bytes were WRONGLY read as
WRONG = ["cp1252", "latin_1", "mac_roman", "cp437", "cp850", "cp865", "mac_latin2"]
# what they SHOULD have been read as
RIGHT = ["iso8859_7", "cp1253", "cp869", "mac_greek"]

known = LF._known_surfaces(LF.LEXICON_DIR / "el.known.txt")
def greek_word(w):
    n = unicodedata.normalize("NFC", w)
    return n in known or n.lower() in known

# harvest suspicious tokens: letters, but not Greek and not plain ASCII
TOK = re.compile(r"\S+")
susp = Counter()
for p in LF.INPUT_DIR.glob("*.txt"):
    for t in TOK.findall(p.read_text(encoding="utf-8")):
        core = t.strip(".,;:()[]«»\"'!?·-–—")
        if len(core) < 4 or LF.GREEK_RE.search(core) or core.isascii():
            continue
        if any(ch.isalpha() or unicodedata.category(ch).startswith("S") for ch in core):
            susp[core] += 1
print(f"candidate mis-decoded tokens: {sum(susp.values()):,} ({len(susp):,} distinct)\n")
print("  most common:", ", ".join(t for t, _ in susp.most_common(6)), "\n")

results = []
sample = susp.most_common(4000)
for w in WRONG:
    for r in RIGHT:
        ok = rows = 0
        ex = []
        for tok, n in sample:
            try:
                back = tok.encode(w, errors="strict").decode(r, errors="strict")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if greek_word(back):
                ok += 1; rows += n
                if len(ex) < 4: ex.append(f"{tok} -> {back}")
        if ok:
            results.append((rows, ok, w, r, ex))

results.sort(reverse=True)
print(f"{'wrong decode':12s} {'true encoding':13s} {'distinct':>9s} {'tokens':>9s}   examples")
for rows, ok, w, r, ex in results[:10]:
    print(f"{w:12s} {r:13s} {ok:>9,} {rows:>9,}   {' | '.join(ex[:2])}")
if results:
    rows, ok, w, r, ex = results[0]
    print(f"\nbest pair: text was decoded as {w} but is really {r}")
    for e in ex: print("   ", e)
