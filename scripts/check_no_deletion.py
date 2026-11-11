"""Check the corrector's core promise on real text: no word is ever lost.

Runs the full corrector on a directory of .txt files, with every output going
to a temporary directory, then compares each corrected file with its source.
A one-edit repair may remove a character (ταγγελία -> αγγελία), but the number
of word tokens must never fall. Needs the full word lists.

    uv run python scripts/check_no_deletion.py --input-dir path/to/text --limit 6

With --corrected-dir it only compares, against files the corrector already
wrote, and does not run it again:

    uv run python scripts/check_no_deletion.py --input-dir path/to/text \\
        --corrected-dir path/to/output/lexicon_filtered
"""

import argparse
import re
import sys
import tempfile
from pathlib import Path

import lexicon_filter as LF

TOKEN = re.compile(r"\S+")
LETTER = re.compile(r"[^\W\d_]")


def count_words(text):
    """Whitespace-separated tokens that contain at least one letter."""
    return sum(1 for token in TOKEN.findall(text) if LETTER.search(token))


def select_sources(input_dir, files_from=None, limit=None):
    """The .txt files to check: all of them, or the ones named in a list."""
    sources = sorted(input_dir.glob("*.txt"))
    if files_from is not None:
        wanted = {
            line.strip() for line in files_from.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        missing = wanted - {p.name for p in sources}
        if missing:
            sys.exit(f"not found in {input_dir}: {sorted(missing)[:5]}")
        sources = [p for p in sources if p.name in wanted]
    return sources[:limit]


def compare(sources, corrected_dir):
    """Word counts in and out, the files that lost words, and those missing."""
    words_in = words_out = 0
    losses, missing = [], []
    for source in sources:
        before = count_words(source.read_text(encoding="utf-8"))
        words_in += before
        corrected = corrected_dir / source.name
        if not corrected.is_file():
            missing.append(source.name)
            continue
        after = count_words(corrected.read_text(encoding="utf-8"))
        words_out += after
        if after < before:
            losses.append((source.name, before - after))
    return words_in, words_out, losses, missing


def run_corrector(sources, input_dir, lexicon_dir, scratch):
    """Correct the sources into scratch; return the folder of corrected text."""
    file_list = scratch / "files.txt"
    file_list.write_text("\n".join(p.name for p in sources), encoding="utf-8")
    command = [
        "--input-dir", str(input_dir),
        "--files-from", str(file_list),
        "--output-dir", str(scratch),
    ]
    if lexicon_dir is not None:
        command += ["--lexicon-dir", str(lexicon_dir)]
    LF.main(command)
    return LF.OUTPUT_DIR


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="directory of the UTF-8 .txt sources")
    parser.add_argument("--corrected-dir", type=Path, default=None,
                        help="compare with the corrected files in this directory "
                             "instead of running the corrector")
    parser.add_argument("--files-from", type=Path, default=None,
                        help="check only the files named in this list, one per line")
    parser.add_argument("--lexicon-dir", type=Path, default=None,
                        help="word lists for the corrector (default: as greek-correct)")
    parser.add_argument("--limit", type=int, default=None,
                        help="check only the first N files, by name")
    args = parser.parse_args(argv)

    sources = select_sources(args.input_dir, args.files_from, args.limit)
    if not sources:
        sys.exit(f"No .txt files in {args.input_dir}")

    if args.corrected_dir is not None:
        result = compare(sources, args.corrected_dir)
    else:
        with tempfile.TemporaryDirectory() as scratch:
            corrected_dir = run_corrector(
                sources, args.input_dir, args.lexicon_dir, Path(scratch)
            )
            result = compare(sources, corrected_dir)
    words_in, words_out, losses, missing = result

    print(f"\nword tokens: {words_in:,} in, {words_out:,} out ({words_out - words_in:+,})")
    for name in missing:
        print(f"  MISSING {name}: no corrected file")
    for name, lost in losses:
        print(f"  LOST {lost:,} word(s) in {name}")
    if losses:
        sys.exit("FAIL: the corrector deleted words")
    if missing:
        sys.exit(f"FAIL: {len(missing)} corrected file(s) missing")
    print(f"PASS: no word lost in {len(sources)} file(s)")


if __name__ == "__main__":
    main()
