# greek_text_extraction_corrector

Repairs Modern Greek text that came out of a PDF wrong.

It reads extracted `.txt`, fixes what it can prove is wrong, and leaves
everything else byte-identical. It is a standalone tool, not a pipeline stage:
point `--input-dir` at any directory of UTF-8 text.

**It never deletes a word.** A token it cannot place is passed through
untouched and written to an unresolved log with the reason it was declined, so
the population it did not fix stays visible instead of disappearing. Across
the 7.7M word tokens it was built on, the number deleted is 0. An earlier
version deleted whatever it failed to recognise and lost 493,665 words, two
and a half times the number it corrected, most of them not garbage.

## How it decides

Two kinds of damage arrive, and they need different treatment. A **wrong
decoding** is Greek bytes read with the wrong table — `συγχρηματοδοτείται`
arrives as `Û˘Á¯ÚËÌ·ÙÔ‰ÔÙÂ›Ù·È` — so re-decoding it is arithmetic, not a guess.
A **wrong glyph** is a scan or font error and has to be guessed, so it is
guessed conservatively: one edit, against a real dictionary.

Each token takes the first branch that applies:

1. re-decode a mis-encoded token — exact
2. leave a token the dictionary already knows — no repair needed
3. leave a real second accent (`υπερβατικότητά του`) — grammar, not damage
4. leave everything in an Ancient Greek file — a Modern Greek lexicon has no
   authority there
5. correct within one edit — a guess, and the last resort

Every branch that changes anything ends at the dictionary, because looking
like Greek proves nothing: `•••` re-decodes into `ΞΞΞ` quite happily.

## Install

Python 3.10 or newer and [uv](https://docs.astral.sh/uv/) are required.
From the cloned repository:

```
uv sync --locked
```

This installs `greek-correct` in `.venv` with the dependencies from `uv.lock`,
including the Greek spaCy model.

To install a standalone command that you can run from other directories:

```
uv tool install .
greek-correct --help
```

If uv reports that its tools directory is missing from PATH, run
`uv tool update-shell` and open a new terminal. The standalone installation
uses the package's dependency requirements; `uv sync --locked` uses the exact
versions in this repository's lockfile.

Then fetch the word lists into `lexicons/`. They are not in the repository:
they come as one 12 MB zip from this repository's `lexicons-v1` release, and
the zip is checked against a SHA-256 before anything is unpacked:

```
uv run python scripts/fetch_lexicons.py
```

`el.txt` and `el.known.txt` are the GSoC 2019 Greek morphological dictionary
from eellak. `el.txt` supplies the correction candidates and their
frequencies; the larger `el.known.txt` is the gate that decides what is
already correct. The gate is worth its size: its extra million entries are
accent-stripped all-capitals forms that cannot be derived from the others,
since `'είναι'.upper()` is `'ΕΊΝΑΙ'`, not the `'ΕΙΝΑΙ'` an OCR'd heading
actually contains.

The other three lists protect proper nouns from correction: given names and
surnames from Wiktionary, and Greek place names from GeoNames.

## Run

Point the tool at a directory of UTF-8 `.txt`:

```
uv run greek-correct --input-dir path/to/text
```

With the standalone installation, use `greek-correct` without `uv run`.
The original `uv run python lexicon_filter.py` command also works.

Relative paths resolve from the current working directory, including the
default `input/`, `lexicons/`, and output files. When running elsewhere, point
to your word lists with `--lexicon-dir path/to/lexicons`.

The corpus is never part of this repository. `LEXICON_INPUT_DIR` can set the
input directory for a whole shell session.

| flag | |
|---|---|
| `--input-dir <dir>` | directory of UTF-8 `.txt` to correct (default `./input`) |
| `--lexicon-dir <dir>` | directory of word lists and optional name lists (default `./lexicons`) |
| `--files-from <list>` | only the file names listed, one per line |
| `--run-name <name>` | write to `lexicon_*__<name>` so a trial never overwrites a real run |
| `--tagger {spacy,stanza}` | spaCy by default, and you want the default |

Outputs: the corrected text in `lexicon_filtered/`, every substitution in
`lexicon_corrections.csv`, and every token left alone in
`lexicon_unresolved.csv` with its reason.

A finished pass saves a compressed checkpoint, reused only when the inputs,
the tuning constants and the word lists all still match.

## Layout

```
lexicon_filter.py              the corrector
pyproject.toml                 dependencies; uv.lock pins them exactly
lexicons/                      word lists, fetched (not tracked)
scripts/fetch_lexicons.py      download the word lists
scripts/build_gazetteer.py     rebuild the toponym list from GeoNames
scripts/check_no_deletion.py   run the corrector on real text, check no word is lost
tests/                         regression tests on small synthetic word lists
```

## Development

To install developer tools and check a change:

```sh
uv sync --locked
uv run pytest
uv run ruff check .
```

The tests use small synthetic word lists. Most use predetermined tokens; the
command-line tests use the installed spaCy model. They verify code behavior,
not accuracy on real documents with the full dictionaries.
Ruff checks the corrector, tests and scripts for common code errors.

To check the no-deletion guarantee on real text with the full word lists:

```sh
uv run python scripts/check_no_deletion.py --input-dir path/to/text --limit 6
```

These checks also run on GitHub for pushes and pull requests. When contributing
a correction rule, include a small failing example as a regression test and
describe why the proposed repair is safe. Keep corpus files out of commits.

## Licensing

The code is GPL-3.0; see `LICENSE`.

The word lists are data, distributed in the `lexicons-v1` release rather than
the repository, and keep their own licenses:

| | |
|---|---|
| eellak `gsoc2019-greek-morpho` dictionaries | CC BY-SA 3.0 |
| Wiktionary given names and surnames | CC BY-SA |
| GeoNames toponyms | CC BY 4.0 |
