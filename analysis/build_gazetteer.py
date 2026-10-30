"""Build a Greek toponym gazetteer from GeoNames, in the tab-paradigm format.

GeoNames records the nominative, running text uses the oblique cases -- the
corpus writes Νοφαλιά where GeoNames has Νοφαλιάς -- and a few regular Greek
endings cover the gap. These forms enter the gate only, never the candidate
pool, so an over-generated one costs a missed correction, never a wrong one.
"""
import re, sys, unicodedata, zipfile
sys.stdout.reconfigure(encoding="utf-8")

SRC = sys.argv[1]
OUT = sys.argv[2]
GREEK_ONLY = re.compile(r"^[\u0370-\u03ff\u1f00-\u1fff]+$")
# geographic features only; S (buildings) and R (roads) are noisy bilinguals
KEEP_CLASS = {"P", "A", "T", "H", "L"}

def cases(word):
    """Nominative plus the regular oblique forms for common Greek endings."""
    out = {word}
    for end, adds in (
        ("ας", ("α",)), ("ος", ("ου", "ο", "ε")), ("ης", ("η",)),
        ("ής", ("ή",)), ("άς", ("ά",)), ("ές", ("έ",)),
        ("α", ("ας",)), ("η", ("ης",)), ("ο", ("ου",)), ("ι", ("ιού",)),
        ("ά", ("άς",)), ("ή", ("ής",)), ("ό", ("ού",)),
    ):
        if word.endswith(end) and len(word) > len(end) + 1:
            stem = word[: -len(end)]
            out |= {stem + a for a in adds}
    return out

names = {}
with zipfile.ZipFile(SRC) as z, z.open("GR.txt") as fh:
    for raw in fh:
        p = raw.decode("utf-8").rstrip("\n").split("\t")
        if len(p) < 8 or p[6] not in KEEP_CLASS:
            continue
        for cand in [p[1]] + (p[3].split(",") if p[3] else []):
            for word in cand.replace("-", " ").split():
                w = unicodedata.normalize("NFC", word.strip("()«»,.;:"))
                if len(w) >= 4 and GREEK_ONLY.match(w):
                    names.setdefault(w, cases(w))

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("# Greek toponyms from GeoNames (CC BY 4.0), with regular case forms\n")
    for head in sorted(names):
        fh.write("\t".join([head] + sorted(names[head] - {head})) + "\n")
total = sum(len(v) for v in names.values())
print(f"{len(names):,} toponyms -> {total:,} surface forms  ->  {OUT}")
