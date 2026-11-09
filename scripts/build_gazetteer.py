"""Build lexicons/geonames_toponyms_withendings.txt from GeoNames.

    curl -LO https://download.geonames.org/export/dump/GR.zip
    uv run python scripts/build_gazetteer.py GR.zip lexicons/geonames_toponyms_withendings.txt

GeoNames records the nominative, running text uses the oblique cases -- the
corpus writes Νοφαλιά where GeoNames has Νοφαλιάς -- and a few regular Greek
endings cover the gap. These forms enter the gate only, never the candidate
pool, so an over-generated one costs a missed correction, never a wrong one.

GeoNames data is CC BY 4.0.
"""

import argparse
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

GREEK_ONLY = re.compile(r"^[Ͱ-Ͽἀ-῿]+$")
# Geographic features only; S (buildings) and R (roads) are noisy bilinguals.
KEEP_CLASS = {"P", "A", "T", "H", "L"}
ENDINGS = (
    ("ας", ("α",)), ("ος", ("ου", "ο", "ε")), ("ης", ("η",)),
    ("ής", ("ή",)), ("άς", ("ά",)), ("ές", ("έ",)),
    ("α", ("ας",)), ("η", ("ης",)), ("ο", ("ου",)), ("ι", ("ιού",)),
    ("ά", ("άς",)), ("ή", ("ής",)), ("ό", ("ού",)),
)


def cases(word):
    """Nominative plus the regular oblique forms for common Greek endings."""
    forms = {word}
    for ending, replacements in ENDINGS:
        if word.endswith(ending) and len(word) > len(ending) + 1:
            stem = word[: -len(ending)]
            forms |= {stem + replacement for replacement in replacements}
    return forms


def read_toponyms(geonames_zip):
    """Map each Greek place name in GR.txt to its set of case forms."""
    toponyms = {}
    with zipfile.ZipFile(geonames_zip) as archive, archive.open("GR.txt") as rows:
        for raw in rows:
            fields = raw.decode("utf-8").rstrip("\n").split("\t")
            if len(fields) < 8 or fields[6] not in KEEP_CLASS:
                continue
            name, alternates = fields[1], fields[3]
            for candidate in [name] + (alternates.split(",") if alternates else []):
                for word in candidate.replace("-", " ").split():
                    word = unicodedata.normalize("NFC", word.strip("()«»,.;:"))
                    if len(word) >= 4 and GREEK_ONLY.match(word):
                        toponyms.setdefault(word, cases(word))
    return toponyms


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("geonames_zip", type=Path, help="GR.zip from GeoNames")
    parser.add_argument("output", type=Path, help="toponym list to write")
    args = parser.parse_args()

    toponyms = read_toponyms(args.geonames_zip)
    with args.output.open("w", encoding="utf-8", newline="\n") as out:
        out.write("# Greek toponyms from GeoNames (CC BY 4.0), with regular case forms\n")
        for head in sorted(toponyms):
            out.write("\t".join([head] + sorted(toponyms[head] - {head})) + "\n")
    total = sum(len(forms) for forms in toponyms.values())
    print(f"{len(toponyms):,} toponyms -> {total:,} surface forms -> {args.output}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
