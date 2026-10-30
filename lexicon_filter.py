"""Repair Modern Greek text that came out of a PDF wrong.

Standalone: reads extracted .txt, fixes what it can prove is wrong, leaves
everything else byte-identical. Point --input-dir at any UTF-8 text.

It never deletes. A token it cannot place passes through and is logged with a
reason. An earlier version deleted them and lost 493,665 words, most of which
were not garbage.

Order, most certain first:

    1. re-decode a mis-encoded token       exact
    2. leave a token the dictionary knows  no repair needed
    3. correct within one edit             a guess

Mis-encoding is Greek bytes read with the wrong table -- συγχρηματοδοτείται
arrives as Û˘Á¯ÚËÌ·ÙÔ‰ÔÙÂ›Ù·È -- so re-decoding is arithmetic. A wrong glyph
has to be guessed. Both end at the dictionary: looking like Greek proves
nothing, since ••• re-decodes into ΞΞΞ quite happily.

Not built yet: pre-Unicode font damage, χαρακτηρίζεται -> χαρακτθρίηεται. It
is not a function -- θ stands for both η and ή, σ/ς are swapped -- so it needs
candidate generation plus the same dictionary check.

Left alone: Ancient Greek (judged per file, see MIN_ANCIENT_FILE_SHARE), Latin
script, digits, anything not monotonic Greek.

The word lists in lexicons/ are required, not optional. el.txt supplies
candidates (word, optional tab- or space-separated frequency), el.known.txt
the exact-surface gate. 75 MB, untracked, from the GSoC 2019 Greek morpho
dictionary, eellak, CC BY-SA 3.0. The capitals list earns its size:
'είναι'.upper() is 'ΕΊΝΑΙ', not the 'ΕΙΝΑΙ' an OCR'd heading contains.

    curl -Lo lexicons/el.txt https://raw.githubusercontent.com/eellak/gsoc2019-greek-morpho/master/data/spell_dict_with_freq.dic
    curl -Lo lexicons/el.known.txt https://raw.githubusercontent.com/eellak/gsoc2019-greek-morpho/master/data/spell_dict_with_capitals_no_freq.dic

spaCy supplies tokenization, NER and part of speech; the dictionary decides
every spelling question. Run it with:

    python lexicon_filter.py --input-dir <dir>

Page separators (--- page 12 ---) are preserved verbatim. A finished pass
checkpoints, and the checkpoint is reused only when inputs, tuning constants
and word lists all match. See LEXICON_FILTER_HANDOFF.md for the full record.
"""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import csv
import os
import pickle
import re
import sys
import unicodedata
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import spacy  # noqa: E402
from rapidfuzz import process  # noqa: E402
from rapidfuzz.distance import DamerauLevenshtein  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = PROJECT_ROOT

# The corpus is never part of this project. Drop text into ./input, or point
# --input-dir or LEXICON_INPUT_DIR at wherever it actually lives.
DEFAULT_INPUT_DIR = PROJECT_ROOT / "input"
INPUT_DIR = Path(os.environ.get("LEXICON_INPUT_DIR") or DEFAULT_INPUT_DIR)

# A named run writes beside the real outputs instead of over them. The
# unnamed run owns the canonical paths.
RUN_NAME = ""
OUTPUT_DIR = OUTPUT_ROOT / "lexicon_filtered"
CHECKPOINT_PATH = OUTPUT_ROOT / "lexicon_filter_checkpoint.pkl.gz"
CORRECTIONS_LOG = OUTPUT_ROOT / "lexicon_corrections.csv"
UNRESOLVED_LOG = OUTPUT_ROOT / "lexicon_unresolved.csv"


def apply_run_name(name: str) -> None:
    """Point every output at a run-specific path."""
    global RUN_NAME, OUTPUT_DIR, CHECKPOINT_PATH, CORRECTIONS_LOG, UNRESOLVED_LOG
    RUN_NAME = name
    tag = f"__{name}" if name else ""
    OUTPUT_DIR = OUTPUT_ROOT / f"lexicon_filtered{tag}"
    CHECKPOINT_PATH = OUTPUT_ROOT / f"lexicon_filter_checkpoint{tag}.pkl.gz"
    CORRECTIONS_LOG = OUTPUT_ROOT / f"lexicon_corrections{tag}.csv"
    UNRESOLVED_LOG = OUTPUT_ROOT / f"lexicon_unresolved{tag}.csv"


LEXICON_DIR = PROJECT_ROOT / "lexicons"

# Protected from correction, never offered as a target: a name is something
# to leave alone, not something to rewrite other words into. Tab-separated
# inflection paradigms -- every field on a line is a surface form.
NAME_LISTS = (
    "all_wiktionary_names_withendings.txt",
    "all_wiktionary_surnames_withendings.txt",
    "geonames_toponyms_withendings.txt",
)

CHECKPOINT_VERSION = 5
ONE_MEGABYTE = 1024 * 1024

# Modern Greek only. The English, German and Ancient Greek pipelines each
# cost a full pass over every page; the ancient one served 89 lines in the
# whole corpus. Nothing is deleted now, so their text is left as scanned.
SPACY_MODEL = "el_core_news_md"
STANZA_LANG = "el"
ROUTE = "el"

# Over the same 30 files Stanza blocks 3,958 corrections spaCy makes: an
# unrecognised token draws a PROPN guess, and the guess protects the damage.
TAGGER = "spacy"


SEPARATOR_RE = re.compile(r"(--- page \d+[^\n]*---\n?)")
TOKEN_RE = re.compile(r"\S+")
LETTER_RUN_RE = re.compile(r"[^\W\d_]+")
GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
POLYTONIC_RE = re.compile(r"[\u1f00-\u1fff]")
LATIN_RE = re.compile(r"[A-Za-z\u00c0-\u024f]")

POLYTONIC_COMBINING_MARKS = {"\u0313", "\u0314", "\u0342", "\u0345"}

# OCR renders a breathing as a plain acute and a circumflex as a diaeresis,
# so POLYTONIC_RE never sees ancient text. These marks are what it leaves.
COMBINING_DIAERESIS = "\u0308"
ACCENT_MARKS = {"\u0301", "\u0300", "\u0342"}

# A proparoxytone before one of these takes a genuine second tonos that the
# dictionary lacks, so 149 real accents were being stripped as damage.
ENCLITICS = frozenset(
    "μου σου του της μας σας τους τις το τη τον".split()
)

# A caption inside a text column splits a word and fuses its first half to
# the caption's opening word: "τα συΑφίσα ... μπεράσματά του" is
# "τα συμπεράσματά του". The internal capital is the seam.
CAPTION_FUSED_RE = re.compile(
    r"\b([\u03b1-\u03c9\u03ac\u03ad\u03ae\u03af\u03cc\u03cd\u03ce\u03ca\u03cb\u0390\u03b0\u03c2]{1,10})([\u0391-\u03a9\u0386\u0388\u0389\u038a\u038c\u038e\u038f][\u03b1-\u03c9\u03ac\u03ad\u03ae\u03af\u03cc\u03cd\u03ce\u03ca\u03cb\u0390\u03b0\u03c2]+)"
)
# Every file in this corpus is CRLF, and the chunks reach here undecoded by
# universal newlines, so the blank line between caption and body is "\r\n\r\n".
AFTER_BLANK_RE = re.compile(r"\n[ \t\r]*\n[ \t\r]*([^\W\d_]+)")

# Per file, because these marks occur in ordinary Greek too. Ancient volumes
# run 18-64% of their Greek lines against a median file's 3.6%.
MIN_ANCIENT_FILE_SHARE = 0.15
MIN_ANCIENT_FILE_LINES = 40

# One modern file in a broken font scores 26.2% above and reads as ancient.
# A word-medial final sigma separates them: Greek never writes one, and that
# file is at 24.7% against 0.62% for the next.
MIN_MEDIAL_SIGMA_RATIO = 0.01

# Û˘Á¯ÚËÌ·ÙÔ‰ÔÙÂ›Ù·È is συγχρηματοδοτείται read as Mac Roman instead of Mac
# Greek. Only these two pairs recover anything on this corpus.
ENCODING_PAIRS = (("mac_roman", "mac_greek"), ("cp1252", "iso8859_7"))

MIN_CORRECTION_LENGTH = 4
MAX_CORRECTION_LENGTH = 30
MIN_CORRECTION_SIMILARITY = 0.80
MIN_CORRECTION_MARGIN = 0.10

# One edit, at every length. Two destroyed correctly spelled words merely
# missing from the list -- unhypothetical to hypothetical -- and no
# distance-2 row had a runner-up for the margin to reject it on.
MAX_CORRECTION_DISTANCE = 1

# A rare entry proves a form exists, not that it is worth rewriting another
# token into. Rare forms stay in the gate and out of the candidate pool: at
# 15, Όικεν was rewriting the ancient έοικεν into nonsense.
MIN_CANDIDATE_FREQUENCY = 25



@dataclass(frozen=True, slots=True)
class LineRoute:
    """The Greek route assigned to one line, or ``None`` for no Greek."""

    start: int
    end: int
    greek: str | None

@dataclass(frozen=True, slots=True)
class PageRouting:
    """Line routes with a binary-search lookup by page character offset."""

    starts: tuple[int, ...]
    lines: tuple[LineRoute, ...]

    def at(self, offset: int) -> LineRoute:
        index = bisect_right(self.starts, offset) - 1
        return self.lines[max(index, 0)]


@dataclass(slots=True)
class BKNode:
    """One node in a metric tree keyed by edit distance."""

    term: str
    children: dict[int, "BKNode"]


class BKTree:
    """Exact edit-distance index for fast nearest-word retrieval."""

    __slots__ = ("root",)

    def __init__(self, terms):
        iterator = iter(terms)
        first = next(iterator, None)
        self.root = BKNode(first, {}) if first is not None else None
        for term in iterator:
            self.add(term)

    def add(self, term: str) -> None:
        node = self.root
        if node is None:
            self.root = BKNode(term, {})
            return
        while True:
            distance = DamerauLevenshtein.distance(term, node.term)
            child = node.children.get(distance)
            if child is None:
                node.children[distance] = BKNode(term, {})
                return
            node = child

    def search(self, query: str, max_distance: int) -> list[str]:
        if self.root is None:
            return []
        matches = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            distance = DamerauLevenshtein.distance(query, node.term)
            if distance <= max_distance:
                matches.append(node.term)
            # Triangle inequality: any word within max_distance of the query
            # hangs off an edge whose own distance is within max_distance of
            # this node's. Every other branch can be skipped unexamined.
            for edge, child in node.children.items():
                if distance - max_distance <= edge <= distance + max_distance:
                    stack.append(child)
        return matches


@dataclass(slots=True)
class CandidateLexicon:
    """Normalized candidates grouped by length and indexed on demand."""

    route: str
    surface_by_key: dict[str, str]
    by_length: dict[int, tuple[str, ...]]
    trees: dict[int, BKTree]
    known_surfaces: frozenset[str] = frozenset()

    def knows(self, surface: str) -> bool:
        """Whether this exact surface is already a dictionary word.

        Exact on purpose: a correction_key match would also swallow the
        misaccented OCR renderings this stage exists to repair.
        """
        if not self.known_surfaces:
            return False
        normalized = unicodedata.normalize("NFC", surface)
        return (
            normalized in self.known_surfaces
            or normalized.lower() in self.known_surfaces
        )

    def _tree(self, length: int) -> BKTree:
        tree = self.trees.get(length)
        if tree is not None:
            return tree
        terms = self.by_length.get(length, ())
        print(
            f"  building {self.route} correction index for length {length}: "
            f"{len(terms):,} candidate(s) ...",
            flush=True,
        )
        tree = BKTree(terms)
        self.trees[length] = tree
        return tree

    def nearby(self, source: str, max_distance: int) -> tuple[str, ...]:
        """Every candidate within max_distance of the source word.

        Candidates are bucketed by length, and a word that many edits away
        cannot differ in length by more, so only that band is searched.
        """
        shortest = max(1, len(source) - max_distance)
        longest = len(source) + max_distance
        matches = []
        for length in range(shortest, longest + 1):
            matches.extend(self._tree(length).search(source, max_distance))
        return tuple(matches)


def _strip_marks(text: str) -> str:
    """NFC form of the text with every combining mark removed."""
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return unicodedata.normalize("NFC", without_marks)


def _is_route_word(text: str, route: str) -> bool:
    """Accept a single alphabetic word written only in the route's script."""
    if not text or not text.isalpha():
        return False
    script = "GREEK" if route in {"el", "grc"} else "LATIN"
    base = _strip_marks(text)
    return bool(base) and all(script in unicodedata.name(c, "") for c in base)


def correction_key(text: str, route: str) -> str:
    """Case/diacritic-insensitive key used only for candidate comparison."""
    folded = text.casefold()
    if route in {"el", "grc"}:
        # OCR drops and changes Greek accents. They should not consume the
        # one edit needed for the actual wrong glyph.
        return _strip_marks(folded)
    return unicodedata.normalize("NFC", folded)


def _surface_priority(word: str, frequency: int | None) -> tuple[int, int, int, str]:
    """Rank the surface forms competing for one comparison key.

    Frequency decides first: code point order picks the wrong variant on 62%
    of contested keys -- άφορά (2) over αφορά (150,568), ςτην over στην.
    """
    return (
        -(frequency or 0),           # most frequent first
        0 if word.islower() else 1,  # then lowercase before capitalised
        len(word),                   # then the shorter form
        word,                        # then code point order, to break ties
    )


def build_candidate_lexicon(
    entries,
    route: str,
    known_surfaces: frozenset[str] = frozenset(),
) -> CandidateLexicon:
    """Build a compact, deterministic candidate set from ``(word, frequency)``."""
    surface_by_key: dict[str, str] = {}
    priority_by_key: dict[str, tuple[int, int, int, str]] = {}
    for raw_word, frequency in entries:
        word = unicodedata.normalize("NFC", str(raw_word).strip())
        if not MIN_CORRECTION_LENGTH <= len(word) <= MAX_CORRECTION_LENGTH:
            continue
        if frequency is not None and frequency < MIN_CANDIDATE_FREQUENCY:
            continue
        if not _is_route_word(word, route):
            continue
        key = correction_key(word, route)
        priority = _surface_priority(word, frequency)
        previous = priority_by_key.get(key)
        if previous is None or priority < previous:
            surface_by_key[key] = word
            priority_by_key[key] = priority

    # Around a million four-tuples for Modern Greek; release them before the
    # length buckets rather than holding both at once.
    del priority_by_key

    by_length_lists: dict[int, list[str]] = defaultdict(list)
    for key in surface_by_key:
        by_length_lists[len(key)].append(key)
    by_length = {
        length: tuple(sorted(values))
        for length, values in by_length_lists.items()
    }
    return CandidateLexicon(route, surface_by_key, by_length, {}, known_surfaces)


def normalized_edit_similarity(source: str, candidate: str) -> float:
    """Normalized Damerau-Levenshtein similarity in the range 0..1."""
    if not source or not candidate:
        return 0.0
    distance = DamerauLevenshtein.distance(source, candidate)
    return 1.0 - distance / max(len(source), len(candidate))


def accept_candidate(source: str, best: str, second_best: str | None) -> bool:
    """Accept a close and unambiguous correction candidate."""
    best_score = normalized_edit_similarity(source, best)
    second_score = (
        normalized_edit_similarity(source, second_best)
        if second_best
        else 0.0
    )
    return (
        DamerauLevenshtein.distance(source, best) <= MAX_CORRECTION_DISTANCE
        and best_score >= MIN_CORRECTION_SIMILARITY
        and best_score - second_score >= MIN_CORRECTION_MARGIN
    )


def restore_source_case(source: str, candidate: str, route: str) -> str:
    """Apply the source token's casing to a lexicon surface form."""
    if source.isupper():
        upper = candidate.upper()
        if route in {"el", "grc"}:
            # All-capitals Greek conventionally omits accents and breathings.
            return _strip_marks(upper)
        return upper
    if source.istitle():
        return candidate[:1].upper() + candidate[1:]
    if source.islower():
        return candidate.lower()
    return candidate


def _restore_cached_case(source: str, cached, route: str):
    """Apply this token's casing to a case-neutral cached result."""
    if cached is None:
        return None
    surface, distance, similarity, runner_up, runner_up_score = cached
    return (
        restore_source_case(source, surface, route),
        distance, similarity, runner_up, runner_up_score,
    )


def recover_encoding(token: str, lexicon: CandidateLexicon) -> str | None:
    """Re-decode a token that was read with the wrong Greek table.

    Three guards, each of which was needed:
    - already carries Greek: never mis-decoded, and a real π would "recover"
      into a real Ι that the dictionary then confirms
    - too short: stray • and · recover into Ξ or α, 2,957 false to 763 true
    - result unknown: accented Latin-1 lands in the Greek block by chance
    """
    if len(token) < MIN_CORRECTION_LENGTH or GREEK_RE.search(token):
        return None
    for wrong, right in ENCODING_PAIRS:
        try:
            back = token.encode(wrong, "strict").decode(right, "strict")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if back != token and lexicon.knows(back):
            return back
    return None


def find_correction(
    source: str,
    route: str,
    lexicon: CandidateLexicon,
    cache: dict[str, tuple | None],
):
    """Return correction metadata, or ``None`` when confidence is insufficient."""
    source_key = correction_key(source, route)
    if source_key in cache:
        # Keyed case-insensitively, so it must hold the lexicon's own
        # surface: caching a cased one made lowercase εϊναι return ΕΙΝΑΙ.
        return _restore_cached_case(source, cache[source_key], route)
    if not MIN_CORRECTION_LENGTH <= len(source_key) <= MAX_CORRECTION_LENGTH:
        cache[source_key] = None
        return None

    candidate_pool = lexicon.nearby(source_key, MAX_CORRECTION_DISTANCE)
    matches = process.extract(
        source_key,
        candidate_pool,
        scorer=DamerauLevenshtein.normalized_similarity,
        score_cutoff=MIN_CORRECTION_SIMILARITY,
        limit=2,
    )
    if not matches:
        cache[source_key] = None
        return None

    best_key = matches[0][0]
    second_key = matches[1][0] if len(matches) > 1 else None
    if not accept_candidate(source_key, best_key, second_key):
        cache[source_key] = None
        return None

    best_surface = lexicon.surface_by_key[best_key]
    second_surface = (
        lexicon.surface_by_key[second_key] if second_key is not None else ""
    )
    cached = (
        best_surface,
        DamerauLevenshtein.distance(source_key, best_key),
        normalized_edit_similarity(source_key, best_key),
        second_surface,
        normalized_edit_similarity(source_key, second_key) if second_key else 0.0,
    )
    cache[source_key] = cached
    return _restore_cached_case(source, cached, route)


def has_polytonic_greek(text: str) -> bool:
    """Recognize precomposed or decomposed polytonic Greek orthography."""
    if POLYTONIC_RE.search(text):
        return True
    if not GREEK_RE.search(text):
        return False
    decomposed = unicodedata.normalize("NFD", text)
    return any(char in POLYTONIC_COMBINING_MARKS for char in decomposed)


def has_ancient_orthography(word: str) -> bool:
    """Whether one word is written the way OCR renders polytonic Greek."""
    if POLYTONIC_RE.search(word):
        return True
    decomposed = unicodedata.normalize("NFD", word)
    if any(char in POLYTONIC_COMBINING_MARKS for char in decomposed):
        return True
    if COMBINING_DIAERESIS in decomposed:
        return True
    return sum(1 for char in decomposed if char in ACCENT_MARKS) >= 2


def is_enclitic_doubling(word: str, next_word: str, lexicon: CandidateLexicon) -> bool:
    """Whether an accent on the word's last letter is a real second tonos.

    A proparoxytone before a weak pronoun takes an extra accent the
    dictionary lacks ("υπερβατικότητά του"). Strip it and look again.
    """
    if next_word not in ENCLITICS:
        return False
    decomposed = unicodedata.normalize("NFD", word)
    marks = [i for i, char in enumerate(decomposed) if char in ACCENT_MARKS]
    # Two accents is the signature. Testing the final *letter* misses every
    # word ending in a consonant, where the second accent sits on the vowel
    # before it -- "εκφάνσεών της".
    if len(marks) < 2:
        return False
    last = marks[-1]
    base = unicodedata.normalize("NFC", decomposed[:last] + decomposed[last + 1 :])
    return lexicon.knows(base)


def next_word_after(tokens, index: int) -> str:
    """The next real word after a token, lowercased, or "" if there is none.

    Not tokens[index + 1]: the tagger emits a line break as its own token, so
    "εξώφυλλά\r\nτους" has "\r\n" in between. lower(), never casefold() --
    casefold maps a final sigma to a medial one, so "τους" becomes "τουσ".
    """
    for candidate in tokens[index + 1 : index + 4]:
        if candidate.text.strip() and any(c.isalnum() for c in candidate.text):
            return candidate.text.lower()
    return ""


def rejoin_caption_splits(text: str, lexicon: CandidateLexicon):
    """Yield the two edits that repair a word a mid-column caption broke apart.

    The caption is extracted between the halves of a word, and the first half
    fuses to the caption's opening word::

        ...να βγάζει τα συΑφίσα
        του 1955 ... (Αλέξη Σολομού, Θεατρικό Λεξικό)

        μπεράσματά του, χωρίς να παρασύρεται

    Split at the internal capital, join the head to the first word after the
    blank line, and συμπεράσματά comes back. Both halves must be substantial,
    since short fragments collide into real words. The one place text moves.
    """
    for match in CAPTION_FUSED_RE.finditer(text):
        head = match.group(1)
        following = AFTER_BLANK_RE.search(text, match.end())
        if following is None or len(head) < 2:
            continue
        tail = following.group(1)
        joined = head + tail
        if len(tail) < 3 or len(joined) < 6:
            continue
        base = joined
        decomposed = unicodedata.normalize("NFD", joined)
        if decomposed and decomposed[-1] in ACCENT_MARKS:
            base = unicodedata.normalize("NFC", decomposed[:-1])
        if not (lexicon.knows(joined) or lexicon.knows(base)):
            continue
        yield match.start(), match.start() + len(head), "", head
        yield following.start(1), following.end(1), joined, tail


def apply_caption_repairs(chunks, ancient_pages, lexicon):
    """Rejoin caption-split words in the page text itself, before tagging.

    Left broken, the halves reach the dictionary as words in their own right:
    μπεράσματά became περάσματα. Returns the chunks and a log of what moved.
    """
    repaired, log = [], []
    for page_idx, chunk in enumerate(chunks):
        edits = (
            []
            if ancient_pages[page_idx]
            else sorted(rejoin_caption_splits(chunk, lexicon))
        )
        if not edits:
            repaired.append(chunk)
            log.append([])
            continue
        out, cursor, entries = [], 0, []
        for start, end, new, old in edits:
            if start < cursor:
                continue
            out.append(chunk[cursor:start])
            out.append(new)
            cursor = end
            entries.append(
                (start, end, new, old, ROUTE, 0, 1.0, "caption-split", 0.0)
            )
        out.append(chunk[cursor:])
        repaired.append("".join(out))
        log.append(entries)
    return repaired, log


def score_ancient_files(file_count, flat_chunks, chunk_owner):
    """Mark each page whose file reads as Ancient Greek rather than Modern.

    Per file, never per line: these are facing-text editions, so a line-level
    call would hand half of every page to the wrong language.
    """
    hits = [0] * file_count
    totals = [0] * file_count
    medial_sigma = [0] * file_count
    greek_words = [0] * file_count
    for page_idx, chunk in enumerate(flat_chunks):
        file_idx = chunk_owner[page_idx][0]
        for line in chunk.splitlines():
            if not GREEK_RE.search(line):
                continue
            totals[file_idx] += 1
            marked = False
            for word in LETTER_RUN_RE.findall(line):
                if not GREEK_RE.search(word):
                    continue
                greek_words[file_idx] += 1
                if "ς" in word[:-1]:
                    medial_sigma[file_idx] += 1
                marked = marked or has_ancient_orthography(word)
            if marked:
                hits[file_idx] += 1
    ancient_files = []
    for ancient_lines, greek_lines, medial, words in zip(
        hits, totals, medial_sigma, greek_words
    ):
        if greek_lines < MIN_ANCIENT_FILE_LINES:
            ancient_files.append(False)
            continue
        ancient_share = ancient_lines / greek_lines
        medial_sigma_rate = medial / max(words, 1)
        ancient_files.append(
            ancient_share >= MIN_ANCIENT_FILE_SHARE
            and medial_sigma_rate < MIN_MEDIAL_SIGMA_RATIO
        )

    per_page = tuple(ancient_files[file_idx] for file_idx, _ in chunk_owner)
    return per_page, sum(ancient_files)


def build_page_routing(text: str, allow_ancient: bool = True) -> PageRouting:
    """Mark each line that carries Greek, and whether it may be corrected."""
    starts, routes = [], []
    offset = 0
    source_lines = text.splitlines(keepends=True) or [text]
    for line in source_lines:
        start = offset
        offset += len(line)
        if GREEK_RE.search(line):
            greek_route = "grc" if has_polytonic_greek(line) else "el"
        else:
            greek_route = None
        starts.append(start)
        routes.append(LineRoute(start, offset, greek_route))

    return PageRouting(tuple(starts), tuple(routes))


def split_pages(text: str):
    """Return ``(is_separator, chunk)`` pairs in their original order."""
    parts = SEPARATOR_RE.split(text)
    return [(bool(SEPARATOR_RE.fullmatch(part)), part) for part in parts if part]


def collect_chunks(files):
    """Collect pages, their owners, and a content hash for checkpoint safety."""
    per_file_parts, flat_chunks, chunk_owner = [], [], []
    input_hasher = hashlib.sha256()
    for file_idx, path in enumerate(files):
        raw = path.read_bytes()
        relative_name = path.relative_to(INPUT_DIR).as_posix().encode("utf-8")
        input_hasher.update(len(relative_name).to_bytes(8, "big"))
        input_hasher.update(relative_name)
        input_hasher.update(len(raw).to_bytes(8, "big"))
        input_hasher.update(raw)

        parts = split_pages(raw.decode("utf-8"))
        per_file_parts.append(parts)
        for part_idx, (is_separator, chunk) in enumerate(parts):
            if not is_separator:
                flat_chunks.append(chunk)
                chunk_owner.append((file_idx, part_idx))

    # A changed lexicon invalidates stored spans just as changed input does.
    input_hasher.update(
        (
            f"correction-v4:{MIN_CORRECTION_LENGTH}:"
            f"{MAX_CORRECTION_LENGTH}:{MIN_CORRECTION_SIMILARITY}:"
            f"{MIN_CORRECTION_MARGIN}:{MAX_CORRECTION_DISTANCE}:"
            f"{MIN_CANDIDATE_FREQUENCY}:{TAGGER}:encoding-v1:enclitic-v3:caption-v2:"
            f"{sorted(ENCLITICS)}:"
            f"ancient-v3:{MIN_ANCIENT_FILE_SHARE}:{MIN_ANCIENT_FILE_LINES}:"
            f"{MIN_MEDIAL_SIGMA_RATIO}"
        ).encode("utf-8")
    )

    def hash_file(path: Path) -> None:
        input_hasher.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            while True:
                block = handle.read(ONE_MEGABYTE)
                if not block:
                    break
                input_hasher.update(block)

    for route in ("el", "grc", "en", "de"):
        input_hasher.update(route.encode("ascii"))
        # The gate decides what is never corrected, so it invalidates too.
        for suffix in (".txt", ".known.txt"):
            lexicon_path = LEXICON_DIR / f"{route}{suffix}"
            if lexicon_path.exists():
                hash_file(lexicon_path)
            else:
                input_hasher.update(b"model-derived")
    for name_file in NAME_LISTS:
        name_path = LEXICON_DIR / name_file
        if name_path.exists():
            hash_file(name_path)
    return per_file_parts, flat_chunks, chunk_owner, input_hasher.hexdigest()

def all_model_names():
    """The model order a checkpoint must still agree with to be reused."""
    return [TAGGER]


def load_checkpoint(input_signature: str, page_count: int):
    """Load a compatible checkpoint or return a fresh protected-span list."""
    def empty_pages():
        return [[] for _ in range(page_count)]

    fresh = (empty_pages(), [], empty_pages(), empty_pages())
    if not CHECKPOINT_PATH.exists():
        return fresh

    try:
        with gzip.open(CHECKPOINT_PATH, "rb") as checkpoint_file:
            checkpoint = pickle.load(checkpoint_file)

        completed = checkpoint["completed_models"]
        protected = checkpoint["protected"]
        replacements = checkpoint["replacements"]
        unresolved = checkpoint["unresolved"]
        expected_models = all_model_names()

        if checkpoint.get("version") != CHECKPOINT_VERSION:
            raise ValueError("checkpoint format version has changed")
        if checkpoint.get("input_signature") != input_signature:
            raise ValueError("input files have changed")
        if len(protected) != page_count:
            raise ValueError("page count has changed")
        if len(replacements) != page_count:
            raise ValueError("replacement page count has changed")
        if len(unresolved) != page_count:
            raise ValueError("unresolved page count has changed")
        if expected_models[: len(completed)] != completed:
            raise ValueError("model names or order have changed")

        print(
            f"Resuming checkpoint: completed {completed or 'no models'}",
            flush=True,
        )
        return protected, completed, replacements, unresolved
    except Exception as exc:
        print(
            f"Ignoring incompatible checkpoint ({exc}); starting fresh.",
            flush=True,
        )
        return fresh


def save_checkpoint(
    input_signature: str,
    completed_models,
    protected,
    replacements,
    unresolved,
) -> None:
    """Atomically save completed-model state using fast gzip compression."""
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = CHECKPOINT_PATH.with_suffix(CHECKPOINT_PATH.suffix + ".tmp")
    checkpoint = {
        "version": CHECKPOINT_VERSION,
        "input_signature": input_signature,
        "completed_models": list(completed_models),
        "protected": protected,
        "replacements": replacements,
        "unresolved": unresolved,
    }

    try:
        with temporary_path.open("wb") as raw_file:
            with gzip.GzipFile(
                fileobj=raw_file,
                mode="wb",
                compresslevel=1,
            ) as checkpoint_file:
                pickle.dump(
                    checkpoint,
                    checkpoint_file,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            raw_file.flush()
            os.fsync(raw_file.fileno())
        temporary_path.replace(CHECKPOINT_PATH)
        size_mb = CHECKPOINT_PATH.stat().st_size / (1024 * 1024)
        print(
            f"Checkpoint saved after {completed_models[-1]} "
            f"({size_mb:.1f} MB): {CHECKPOINT_PATH}",
            flush=True,
        )
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        print(f"WARNING: checkpoint could not be saved: {exc}", flush=True)


def clear_checkpoint() -> None:
    """Remove the checkpoint only after every output file is safely written."""
    try:
        CHECKPOINT_PATH.unlink(missing_ok=True)
    except OSError as exc:
        print(f"WARNING: could not remove checkpoint: {exc}", flush=True)


def _wordlist_entries(path: Path):
    """Yield (surface, frequency) pairs from a UTF-8 word-list file.

    Takes a bare word, word<TAB>count or word<SPACE>count. A trailing field
    that is not an integer belongs to the word, so uncounted lists still load.
    """
    with path.open("r", encoding="utf-8-sig") as wordlist_file:
        for line in wordlist_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            head, separator, tail = stripped.rpartition("\t")
            if not separator:
                head, separator, tail = stripped.rpartition(" ")
            # str.isdigit is also true of superscripts and non-ASCII digit
            # forms that int then refuses.
            if separator and head and tail.isascii() and tail.isdigit():
                yield head.strip(), int(tail)
            else:
                yield stripped, None


def _known_surfaces(path: Path) -> frozenset[str]:
    """Load the exact surface forms that mark a token as already correct.

    Unfiltered by length or script, unlike the candidate list: the gate must
    protect every real word, including ones never proposed as a correction.
    """
    surfaces = set()
    with path.open("r", encoding="utf-8-sig") as surface_file:
        for line in surface_file:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                surfaces.add(unicodedata.normalize("NFC", stripped))
    return frozenset(surfaces)


def _paradigm_surfaces(path: Path) -> set[str]:
    """Load every form from a tab-separated inflection paradigm list.

    One line holds a lemma and all its inflections -- Ααρών, Ααρώνος -- so
    every field is a surface. Taking only the first would expose the rest.
    """
    surfaces = set()
    with path.open("r", encoding="utf-8-sig") as paradigm_file:
        for line in paradigm_file:
            if line.startswith("#"):
                continue
            for field in line.rstrip("\n").split("\t"):
                form = field.strip()
                if form:
                    surfaces.add(unicodedata.normalize("NFC", form))
    return surfaces


def make_correction_lexicon(route: str):
    """Load the correction candidates and known-word gate for one route.

    The word lists are required, not optional: the spaCy vector keys they
    replaced are web-scraped, and 36.8% of the Greek ones are not words.
    """
    candidate_path = LEXICON_DIR / f"{route}.txt"
    known_path = LEXICON_DIR / f"{route}.known.txt"
    for required in (candidate_path, known_path):
        if not required.exists():
            raise RuntimeError(
                f"Missing word list {required}. The module docstring has "
                f"the two curl commands that fetch it."
            )

    known_surfaces = set(_known_surfaces(known_path))
    name_forms = 0
    for name_file in NAME_LISTS:
        name_path = LEXICON_DIR / name_file
        if name_path.exists():
            forms = _paradigm_surfaces(name_path)
            name_forms += len(forms - known_surfaces)
            known_surfaces |= forms
    known_surfaces = frozenset(known_surfaces)

    lexicon = build_candidate_lexicon(
        _wordlist_entries(candidate_path), route, known_surfaces
    )
    print(
        f"  correction candidates for {route}: "
        f"{len(lexicon.surface_by_key):,} ({candidate_path.name}); "
        f"known surfaces: {len(known_surfaces):,} "
        f"(+{name_forms:,} name forms)",
        flush=True,
    )
    if not lexicon.surface_by_key:
        raise RuntimeError(f"No correction candidates loaded from {candidate_path}.")
    return lexicon


def report_progress(model_name: str, completed: int, total: int) -> None:
    if completed % 100 == 0 or completed == total:
        print(
            f"  {model_name}: {completed}/{total} page(s)",
            flush=True,
        )


@dataclass(frozen=True, slots=True)
class Tagged:
    """One surface token, reduced to what the protection gate consults."""

    text: str
    start: int
    is_propn: bool


class SpacyTagger:
    """spaCy pipeline. Supplies named entities as well as part of speech."""

    name = "spacy"

    def __init__(self):
        print(f"Loading {SPACY_MODEL} ...", flush=True)
        self.nlp = spacy.load(SPACY_MODEL)

    def pages(self, chunks):
        for doc in self.nlp.pipe(chunks, batch_size=64):
            yield [
                Tagged(t.text, t.idx, bool(t.ent_type_) or t.pos_ == "PROPN")
                for t in doc
            ]


class StanzaTagger:
    """Stanza pipeline, batched. No Greek NER exists, so PROPN stands alone.

    Greek multi-word tokens split one surface into several (στον -> σε, τον).
    Corrections work on the surface, so tokens are reported whole.
    """

    name = "stanza"
    BATCH = 64

    def __init__(self):
        import stanza

        print(f"Loading stanza {STANZA_LANG} ...", flush=True)
        self._doc = stanza.models.common.doc.Document
        self.nlp = stanza.Pipeline(
            STANZA_LANG,
            processors="tokenize,mwt,pos",
            verbose=False,
            use_gpu=False,
        )

    def pages(self, chunks):
        for start in range(0, len(chunks), self.BATCH):
            batch = chunks[start : start + self.BATCH]
            docs = self.nlp.bulk_process([self._doc([], text=c) for c in batch])
            for doc in docs:
                yield [
                    Tagged(
                        token.text,
                        token.start_char,
                        any(w.upos == "PROPN" for w in token.words),
                    )
                    for sentence in doc.sentences
                    for token in sentence.tokens
                ]


def make_tagger():
    """Build the configured tagger."""
    return StanzaTagger() if TAGGER == "stanza" else SpacyTagger()


def protect_with_modern_model(
    flat_chunks,
    page_routings,
    ancient_pages,
    correction_lexicon,
    protected,
    replacements,
    unresolved,
) -> None:
    """Correct confidently misspelled Greek; leave everything else alone."""
    tagger = make_tagger()
    total = len(flat_chunks)
    correction_cache: dict[str, tuple | None] = {}

    for completed, tokens in enumerate(tagger.pages(flat_chunks), start=1):
        page_idx = completed - 1
        page_routing = page_routings[page_idx]

        for i, token in enumerate(tokens):
            token_end = token.start + len(token.text)

            # First, and it ignores the Greek-script gate below: a token read
            # with the wrong table holds no Greek characters yet. Re-decoding
            # is exact, and only a dictionary-confirmed result is accepted.
            recovered = recover_encoding(token.text, correction_lexicon)
            if recovered is not None:
                protected[page_idx].append((token.start, token_end))
                replacements[page_idx].append(
                    (token.start, token_end, recovered, token.text, ROUTE,
                     0, 1.0, "encoding", 0.0)
                )
                continue

            line_route = page_routing.at(token.start)
            # Only monotonic Greek is this stage's business. Latin script,
            # digits and polytonic lines are left exactly as scanned.
            if line_route.greek != ROUTE or not GREEK_RE.search(token.text):
                continue

            if token.is_propn or correction_lexicon.knows(token.text):
                protected[page_idx].append((token.start, token_end))
                continue

            following = next_word_after(tokens, i)
            if is_enclitic_doubling(token.text, following, correction_lexicon):
                protected[page_idx].append((token.start, token_end))
                continue

            # A Modern Greek lexicon has no authority over an Ancient Greek
            # text. Marked orthography is only the visible part: γίγνονται
            # and Πότερον carry no tell and were rewritten anyway.
            if ancient_pages[page_idx]:
                protected[page_idx].append((token.start, token_end))
                unresolved[page_idx].append(
                    (token.start, token_end, token.text, ROUTE, "ancient-file")
                )
                continue

            if not token.text.isalpha() or not _is_route_word(token.text, ROUTE):
                protected[page_idx].append((token.start, token_end))
                unresolved[page_idx].append(
                    (token.start, token_end, token.text, ROUTE, "not-a-word")
                )
                continue

            correction = find_correction(
                token.text, ROUTE, correction_lexicon, correction_cache
            )
            if correction is None:
                # No confident candidate is a reason to leave a token alone,
                # not to delete it. What reaches here includes correctly
                # spelled vocabulary simply absent from the word list.
                protected[page_idx].append((token.start, token_end))
                unresolved[page_idx].append(
                    (token.start, token_end, token.text, ROUTE, "no-candidate")
                )
                continue

            replacement, distance, similarity, runner_up, runner_score = correction
            protected[page_idx].append((token.start, token_end))
            if replacement != token.text:
                replacements[page_idx].append(
                    (token.start, token_end, replacement, token.text, ROUTE,
                     distance, similarity, runner_up, runner_score)
                )
        report_progress(tagger.name, completed, total)


def compute_protected(
    flat_chunks, page_routings, ancient_pages, correction_lexicon, input_signature
):
    """Return replacement and unresolved spans, resuming a finished pass."""
    protected, completed_models, replacements, unresolved = load_checkpoint(
        input_signature,
        len(flat_chunks),
    )

    if TAGGER in completed_models:
        print(f"Skipping completed pass ({TAGGER})", flush=True)
    else:
        protect_with_modern_model(
            flat_chunks,
            page_routings,
            ancient_pages,
            correction_lexicon,
            protected,
            replacements,
            unresolved,
        )
        completed_models.append(TAGGER)
        save_checkpoint(
            input_signature,
            completed_models,
            protected,
            replacements,
            unresolved,
        )
        gc.collect()

    for spans in replacements:
        spans.sort(key=lambda replacement: replacement[0])
    for spans in unresolved:
        spans.sort(key=lambda token: token[0])
    return replacements, unresolved


def filter_chunk(text: str, replacements) -> str:
    """Apply accepted in-token replacements, keeping everything else.

    Nothing is removed. A token this stage cannot place is logged as
    unresolved and passed through untouched.
    """
    if not replacements:
        return text

    out, cursor = [], 0
    for entry in replacements:
        start, end, replacement = entry[:3]
        if start < cursor:
            continue  # overlapping span; the earlier one already won
        out.append(text[cursor:start])
        out.append(replacement)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def _part_page_number(parts, part_idx: int) -> str:
    """Find the page number in the separator immediately before a text part."""
    for previous_idx in range(part_idx - 1, -1, -1):
        is_separator, separator = parts[previous_idx]
        if not is_separator:
            continue
        match = re.search(r"--- page (\d+)", separator)
        return match.group(1) if match else ""
    return ""


def write_corrections_log(files, per_file_parts, chunk_owner, replacements) -> int:
    """Write an auditable CSV containing every automatic substitution."""
    fields = [
        "filename", "page", "language", "original", "replacement",
        "edit_distance", "similarity", "runner_up", "runner_up_similarity",
        "page_char_start", "page_char_end",
    ]
    count = 0
    CORRECTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CORRECTIONS_LOG.open("w", newline="", encoding="utf-8-sig") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=fields)
        writer.writeheader()
        for page_idx, page_replacements in enumerate(replacements):
            file_idx, part_idx = chunk_owner[page_idx]
            page_number = _part_page_number(per_file_parts[file_idx], part_idx)
            for row in page_replacements:
                (start, end, replacement, original, language,
                 distance, similarity, runner_up, runner_score) = row
                writer.writerow({
                    "filename": files[file_idx].name,
                    "page": page_number,
                    "language": language,
                    "original": original,
                    "replacement": replacement,
                    "edit_distance": distance,
                    "similarity": f"{similarity:.4f}",
                    "runner_up": runner_up,
                    "runner_up_similarity": f"{runner_score:.4f}",
                    "page_char_start": start,
                    "page_char_end": end,
                })
                count += 1
    return count


def write_unresolved_log(files, per_file_parts, chunk_owner, unresolved) -> int:
    """Write every token kept verbatim for want of a confident match.

    These are the tokens an earlier version deleted. Logging them keeps that
    population visible, so a deletion rule can be argued from evidence.
    """
    fields = [
        "filename", "page", "language", "token", "reason",
        "page_char_start", "page_char_end",
    ]
    count = 0
    UNRESOLVED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with UNRESOLVED_LOG.open("w", newline="", encoding="utf-8-sig") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=fields)
        writer.writeheader()
        for page_idx, page_tokens in enumerate(unresolved):
            file_idx, part_idx = chunk_owner[page_idx]
            page_number = _part_page_number(per_file_parts[file_idx], part_idx)
            for start, end, token_text, language, reason in page_tokens:
                writer.writerow({
                    "filename": files[file_idx].name,
                    "page": page_number,
                    "language": language,
                    "token": token_text,
                    "reason": reason,
                    "page_char_start": start,
                    "page_char_end": end,
                })
                count += 1
    return count


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tagger", choices=("stanza", "spacy"), default=TAGGER,
        help="which pipeline supplies tokenization and part of speech",
    )
    parser.add_argument(
        "--files-from", type=Path, default=None,
        help="run only the input file names listed in this file, one per line",
    )
    parser.add_argument(
        "--run-name", default="",
        help="write outputs to run-specific paths instead of the canonical ones",
    )
    parser.add_argument(
        "--input-dir", type=Path, default=None,
        help="directory of UTF-8 .txt to correct (default: ./input, or "
             "$LEXICON_INPUT_DIR)",
    )
    return parser.parse_args(argv)


def select_files(files_from: Path | None):
    """All input files, or just the ones named in a list."""
    every = sorted(INPUT_DIR.glob("*.txt"))
    if files_from is None:
        return every
    wanted = {
        line.strip() for line in files_from.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    chosen = [f for f in every if f.name in wanted]
    missing = wanted - {f.name for f in chosen}
    if missing:
        raise SystemExit(f"not found in {INPUT_DIR}: {sorted(missing)[:5]}")
    return chosen


def main(argv=None) -> None:
    global TAGGER, INPUT_DIR
    args = parse_args(argv)
    TAGGER = args.tagger
    if args.input_dir is not None:
        INPUT_DIR = args.input_dir
    apply_run_name(args.run_name)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = select_files(args.files_from)
    print(
        f"{len(files)} file(s) in {INPUT_DIR} | tagger={TAGGER}"
        f"{' | run=' + RUN_NAME if RUN_NAME else ''}",
        flush=True,
    )

    if not files:
        print("Nothing to process.", flush=True)
        return

    per_file_parts, flat_chunks, chunk_owner, input_signature = collect_chunks(files)
    model_names = all_model_names()
    print(
        f"{len(flat_chunks)} page(s) to check against {model_names}",
        flush=True,
    )

    ancient_pages, ancient_file_count = score_ancient_files(
        len(files),
        flat_chunks,
        chunk_owner,
    )
    print(
        f"{ancient_file_count} of {len(files)} file(s) read as Ancient Greek; "
        f"their polytonic tokens are kept as scanned",
        flush=True,
    )

    correction_lexicon = make_correction_lexicon(ROUTE)

    # Repair the text before anything reads it as words: a word a caption cut
    # in half must be whole before the tagger and the dictionary judge it.
    flat_chunks, caption_log = apply_caption_repairs(
        flat_chunks, ancient_pages, correction_lexicon
    )
    caption_count = sum(len(entries) for entries in caption_log)
    print(
        f"rejoined {caption_count // 2} word(s) split across a caption",
        flush=True,
    )

    # Routing reads character offsets, so it must see the repaired text.
    print("Marking Greek lines ...", flush=True)
    page_routings = [build_page_routing(chunk) for chunk in flat_chunks]
    route_counts = {"el": 0, "grc": 0}
    for routing in page_routings:
        for line in routing.lines:
            if line.greek in {"el", "grc"}:
                route_counts[line.greek] += 1
    print(f"Greek lines: {route_counts} (grc left as scanned)", flush=True)

    replacements, unresolved = compute_protected(
        flat_chunks,
        page_routings,
        ancient_pages,
        correction_lexicon,
        input_signature,
    )

    for page_idx, (file_idx, part_idx) in enumerate(chunk_owner):
        per_file_parts[file_idx][part_idx] = (
            False,
            filter_chunk(flat_chunks[page_idx], replacements[page_idx]),
        )

    for file_idx, path in enumerate(files):
        text = "".join(chunk for _, chunk in per_file_parts[file_idx])
        (OUTPUT_DIR / path.name).write_text(text, encoding="utf-8")
        print(f"[{file_idx + 1}/{len(files)}] {path.name}", flush=True)

    # Already in the text; folded in now, after filter_chunk, only so the
    # audit log records them. Offsets refer to the text as extracted.
    for page_idx, entries in enumerate(caption_log):
        replacements[page_idx].extend(entries)

    correction_count = write_corrections_log(
        files,
        per_file_parts,
        chunk_owner,
        replacements,
    )
    unresolved_count = write_unresolved_log(
        files,
        per_file_parts,
        chunk_owner,
        unresolved,
    )
    clear_checkpoint()
    print(
        f"automatic corrections: {correction_count} -> {CORRECTIONS_LOG}",
        flush=True,
    )
    print(
        f"kept unresolved: {unresolved_count} -> {UNRESOLVED_LOG}",
        flush=True,
    )
    print(f"done -> {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
