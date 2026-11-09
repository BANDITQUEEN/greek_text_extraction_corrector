"""Check the corrector's core promise on real text: no word is ever lost.

Runs the full corrector on a directory of .txt files, with every output going
to a temporary directory, then compares each corrected file with its source.
A one-edit repair may remove a character (ταγγελία -> αγγελία), but the number
of word tokens must never fall. Needs the full word lists in lexicons/.

    uv run python scripts/check_no_deletion.py --input-dir path/to/text --limit 6
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="directory of UTF-8 .txt to correct")
    parser.add_argument("--lexicon-dir", type=Path, default=None,
                        help="word lists (default: ./lexicons)")
    parser.add_argument("--limit", type=int, default=None,
                        help="check only the first N files, by name")
    args = parser.parse_args()

    sources = sorted(args.input_dir.glob("*.txt"))[: args.limit]
    if not sources:
        sys.exit(f"No .txt files in {args.input_dir}")

    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        file_list = scratch / "files.txt"
        file_list.write_text("\n".join(p.name for p in sources), encoding="utf-8")
        LF.OUTPUT_ROOT = scratch
        command = ["--input-dir", str(args.input_dir), "--files-from", str(file_list)]
        if args.lexicon_dir is not None:
            command += ["--lexicon-dir", str(args.lexicon_dir)]
        LF.main(command)

        words_in = words_out = 0
        losses = []
        for source in sources:
            before = count_words(source.read_text(encoding="utf-8"))
            after = count_words((LF.OUTPUT_DIR / source.name).read_text(encoding="utf-8"))
            words_in += before
            words_out += after
            if after < before:
                losses.append((source.name, before - after))

    print(f"\nword tokens: {words_in:,} in, {words_out:,} out ({words_out - words_in:+,})")
    if losses:
        for name, lost in losses:
            print(f"  LOST {lost:,} word(s) in {name}")
        sys.exit("FAIL: the corrector deleted words")
    print(f"PASS: no word lost in {len(sources)} file(s)")


if __name__ == "__main__":
    main()
