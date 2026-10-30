"""A caption extracted mid-sentence splits a word. Can the halves be rejoined?

    ...να βγάζει τα συΑφίσα        <- 'συ' fused to the caption's first word
    του 1955 ... Θεατρικό Λεξικό)  <- the caption
                                    <- blank line ends it
    μπεράσματά του, ...            <- the rest of the word

Split the fused token at its internal capital, take the first word after the
next blank line, ask the dictionary whether the halves make a word.
"""
import re, sys, unicodedata
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import lexicon_filter as LF

lex = LF.make_correction_lexicon(LF.ROUTE)
# lowercase Greek run, then an uppercase Greek letter, then more Greek
FUSED = re.compile(r"\b([α-ωάέήίόύώϊϋΐΰς]{1,8})([Α-ΩΆΈΉΊΌΎΏ][α-ωάέήίόύώϊϋΐΰς]+)")
AFTER_BLANK = re.compile(r"\n[ \t]*\n[ \t]*([^\W\d_]+)")

def known_with_enclitic(w):
    if lex.knows(w):
        return True
    d = unicodedata.normalize("NFD", w)
    return bool(d) and d[-1] in LF.ACCENT_MARKS and lex.knows(
        unicodedata.normalize("NFC", d[:-1]))

joined = Counter(); failed = 0; fused_total = 0
for path in sorted(LF.INPUT_DIR.glob("*.txt")):
    text = path.read_text(encoding="utf-8")
    for m in FUSED.finditer(text):
        head, cap = m.group(1), m.group(2)
        fused_total += 1
        nxt = AFTER_BLANK.search(text, m.end())
        if not nxt:
            failed += 1
            continue
        tail = nxt.group(1)
        if known_with_enclitic(head + tail):
            joined[(head, cap, tail, head + tail)] += 1
        else:
            failed += 1

print(f"\nfused tokens (lowercase run + internal capital): {fused_total:,}")
print(f"  head+tail makes a dictionary word : {sum(joined.values()):,}")
print(f"  does not                          : {failed:,}\n")
print("--- recoverable splits ---")
for (h, c, t, j), n in joined.most_common(20):
    print(f"   {h}|{c} ... {t}   ->  {j}   x{n}")
