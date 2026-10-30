# Analysis scripts

Throwaway measurement scripts written while diagnosing `lexicon_filter.py`.
Run them from the project root:

    .venv\Scripts\python.exe analysis\<name>.py

| script | what it answers |
|---|---|
| `extract.py` | Write corrections/unresolved CSVs from a checkpoint without finishing the run |
| `cmp.py` | Diff the correction sets of two or more runs (old vs p30 vs s30) |
| `bench.py` | Stanza vs spaCy PROPN tagging on capitalised corrections — **biased sample, see note** |
| `speed.py` | Throughput of spaCy pipe vs Stanza single vs Stanza bulk_process |
| `diag.py` | Look up specific tokens in the corrections CSV and the dictionary |
| `diag2.py` | Margin-guard emptiness, target-frequency distribution, ending-only changes |
| `ctx2.py` | What POS/entity a token gets in its real page context |
| `frag.py` | Show the source text around a correction, to see if the token is a fragment |
| `verify.py` | Assert `filter_chunk` never deletes anything |

## Note on `bench.py`

Its sample is selected *because* the tokens are capitalised, so it over-states
Stanza's advantage: almost none of the lowercase damaged tokens, where
Stanza's PROPN-by-default protects mojibake from repair. `cmp.py` is the
trustworthy measurement. Kept as a record of how the wrong conclusion was
reached.
