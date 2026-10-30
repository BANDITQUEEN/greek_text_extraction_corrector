# garbage_corrector

Repairs Modern Greek text that came out of a PDF wrong.

It reads extracted `.txt`, fixes what it can prove is wrong, and leaves
everything else byte-identical. It is a standalone tool, not a pipeline stage:
point `--input-dir` at any directory of UTF-8 text.

**It never deletes a word.** A token it cannot place is passed through
untouched and written to an unresolved log with the reason it was declined, so
the population it did not fix stays visible instead of disappearing. An
earlier version deleted whatever it failed to recognise and lost 493,665
words, two and a half times the number it corrected, most of them not garbage.

## Results

Over 363 documents — 30,731 pages, 7.7M word tokens:

| | |
|---|---|
| corrections made | 33,913 |
| word tokens deleted | 0 |
| runtime | ~22 min |

Everything it declined is logged and counted: 546,637 tokens in Ancient Greek
files, 163,363 with no confident candidate, 91,302 that are not words.

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

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install el_core_news_md
```

Paths here are Windows. On macOS and Linux the interpreter is
`.venv/bin/python`.

Then fetch the word lists (75 MB, not in this repo). They are the GSoC 2019
Greek morphological dictionary from eellak:

```
curl -Lo lexicons/el.txt https://raw.githubusercontent.com/eellak/gsoc2019-greek-morpho/master/data/spell_dict_with_freq.dic
curl -Lo lexicons/el.known.txt https://raw.githubusercontent.com/eellak/gsoc2019-greek-morpho/master/data/spell_dict_with_capitals_no_freq.dic
```

`el.txt` supplies the correction candidates and their frequencies; the larger
`el.known.txt` is the gate that decides what is already correct. The gate is
worth its size: its extra million entries are accent-stripped all-capitals
forms that cannot be derived from the others, since `'είναι'.upper()` is
`'ΕΊΝΑΙ'`, not the `'ΕΙΝΑΙ'` an OCR'd heading actually contains.

The name and toponym lists under `lexicons/` protect proper nouns from
correction. See the handoff for where they come from.

## Run

Put the text you want corrected in `input/`, or point the tool at it:

```
.venv\Scripts\python.exe lexicon_filter.py --input-dir path\to\text
```

The corpus is never part of this repository. `input/` is only the default
location; `LEXICON_INPUT_DIR` sets it for a whole shell session.

| flag | |
|---|---|
| `--input-dir <dir>` | directory of UTF-8 `.txt` to correct (default `./input`) |
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
lexicon_filter.py    the corrector
lexicons/            word lists and name lists (fetched, not tracked)
input/               default corpus location (not tracked)
analysis/            measurement scripts written while diagnosing it
```

## Documentation

- **`LEXICON_FILTER_HANDOFF.md`** — the real record: every design decision and
  why, the traps found the hard way, what was rejected and on what evidence,
  and the open items. Read this before changing anything.
- **`LEXICON_FILTER_ANALYSIS.md`** — a point-in-time analysis of the version
  before the rewrite, kept because its findings are what drove it.
- **`analysis/README.md`** — what each measurement script answers.

## Licensing

The code is GPL-3.0; see `LICENSE`.

The data it depends on is not distributed here and carries its own terms:

| | |
|---|---|
| eellak `gsoc2019-greek-morpho` word lists | CC BY-SA 3.0 |
| GeoNames toponyms | CC BY 4.0 |
| Wiktionary name and surname lists | CC BY-SA |
