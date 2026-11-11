"""Shared fixtures: restore the corrector's settings, and tag without spaCy."""

import re
from types import SimpleNamespace

import pytest

import lexicon_filter as LF


@pytest.fixture
def isolated_globals(monkeypatch):
    """main() configures module globals. Restore them after each test."""
    for name in (
        "INPUT_DIR",
        "LEXICON_DIR",
        "OUTPUT_ROOT",
        "TAGGER",
        "RUN_NAME",
        "OUTPUT_DIR",
        "CHECKPOINT_PATH",
        "CORRECTIONS_LOG",
        "UNRESOLVED_LOG",
    ):
        monkeypatch.setattr(LF, name, getattr(LF, name))


@pytest.fixture
def word_tagger(monkeypatch):
    """Tag each whitespace-separated word, none of them a name: no model loads."""

    def pages(chunks):
        for chunk in chunks:
            yield [
                LF.Tagged(m.group(), m.start(), False)
                for m in re.finditer(r"\S+", chunk)
            ]

    monkeypatch.setattr(
        LF, "make_tagger", lambda: SimpleNamespace(name="spacy", pages=pages)
    )
