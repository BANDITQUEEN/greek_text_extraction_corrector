"""Small public regression cases; no corpus, word-list downloads, or models."""

import re

import pytest

import lexicon_filter as LF


def lexicon(*words, known=None):
    return LF.build_candidate_lexicon(
        [(word, 100) for word in words],
        "el",
        known_surfaces=frozenset(words if known is None else known),
    )


def correct(monkeypatch, text, dictionary, *, names=(), ancient=False):
    """Exercise correction decisions with explicit, model-independent tokens."""
    tokens = [
        LF.Tagged(match.group(), match.start(), match.group() in names)
        for match in re.finditer(r"\S+", text)
    ]

    class Tagger:
        name = "fixture"

        def pages(self, chunks):
            yield tokens

    monkeypatch.setattr(LF, "make_tagger", Tagger)
    protected, replacements, unresolved = [[]], [[]], [[]]
    LF.protect_with_modern_model(
        [text],
        [LF.build_page_routing(text)],
        [ancient],
        dictionary,
        protected,
        replacements,
        unresolved,
    )
    return LF.filter_chunk(text, replacements[0]), replacements[0], unresolved[0]


@pytest.mark.parametrize(
    ("wrong", "right"), [("mac_roman", "mac_greek"), ("cp1252", "iso8859_7")]
)
def test_encoding_repair_requires_a_known_word(wrong, right):
    original = "καλημέρα"
    damaged = original.encode(right).decode(wrong)

    assert LF.recover_encoding(damaged, lexicon(original)) == original
    assert LF.recover_encoding(damaged, lexicon("κόσμος")) is None


@pytest.mark.parametrize("text", ["•••", "καλημέρα", "English", "1234"])
def test_encoding_does_not_rewrite_undamaged_or_short_tokens(text):
    assert LF.recover_encoding(text, lexicon("καλημέρα", "κόσμος")) is None


def test_known_surface_is_preserved_even_when_another_surface_is_preferred(monkeypatch):
    dictionary = lexicon("αφορά", known={"άφορά"})

    result, replacements, unresolved = correct(monkeypatch, "άφορά", dictionary)

    assert result == "άφορά"
    assert replacements == []
    assert unresolved == []


def test_named_entity_is_protected_from_a_plausible_correction(monkeypatch):
    dictionary = lexicon("μαρίνα")
    # Without entity protection this is a close enough candidate to be accepted.
    assert LF.find_correction("Μαρία", "el", dictionary, {})[0] == "Μαρίνα"

    result, replacements, unresolved = correct(
        monkeypatch, "Μαρία", dictionary, names={"Μαρία"}
    )

    assert result == "Μαρία"
    assert replacements == []
    assert unresolved == []


def test_unknown_word_survives_next_to_a_valid_repair(monkeypatch):
    result, replacements, unresolved = correct(
        monkeypatch, "κόομος ζζζζζ 123 English", lexicon("κόσμος")
    )

    assert result == "κόσμος ζζζζζ 123 English"
    assert len(replacements) == 1
    assert [(entry[2], entry[4]) for entry in unresolved] == [("ζζζζζ", "no-candidate")]


@pytest.mark.parametrize(
    ("source", "candidates"),
    [
        ("κόσμο", ("κόσμος", "κόσμη")),  # runner-up exactly at the minimum score
        ("μόνο", ("μόνος", "μόνη")),  # runner-up just below the minimum score
        ("κόσμοα", ("κόσμος", "κόσμου")),  # equal scores above the minimum
    ],
)
def test_ambiguous_candidates_are_declined(source, candidates):
    assert LF.find_correction(source, "el", lexicon(*candidates), {}) is None


def test_single_candidate_still_requires_minimum_similarity():
    assert LF.find_correction("μέτα", "el", lexicon("μέρα"), {}) is None


def test_cached_correction_preserves_each_tokens_case():
    dictionary = lexicon("είναι")
    cache = {}

    assert LF.find_correction("ΕΪΝΑΙ", "el", dictionary, cache)[0] == "ΕΙΝΑΙ"
    assert LF.find_correction("εϊναι", "el", dictionary, cache)[0] == "είναι"
    assert LF.find_correction("Εϊναι", "el", dictionary, cache)[0] == "Είναι"


def test_genuine_second_accent_is_preserved_before_an_enclitic(monkeypatch):
    text = "υπερβατικότητά του"
    result, replacements, unresolved = correct(
        monkeypatch, text, lexicon("υπερβατικότητα", known={"υπερβατικότητα", "του"})
    )

    assert result == text
    assert replacements == []
    assert unresolved == []


def test_second_accent_requires_an_enclitic_and_a_known_base():
    assert not LF.is_enclitic_doubling(
        "υπερβατικότητά", "σήμερα", lexicon("υπερβατικότητα")
    )
    assert not LF.is_enclitic_doubling("υπερβατικότητά", "του", lexicon("κόσμος"))


def test_enclitic_lookup_skips_a_line_break_and_preserves_final_sigma():
    tokens = [
        LF.Tagged("εξώφυλλά", 0, False),
        LF.Tagged("\r\n", 8, False),
        LF.Tagged("τους", 10, False),
    ]

    assert LF.next_word_after(tokens, 0) == "τους"


def test_ancient_file_keeps_monotonic_words_that_look_misspelled(monkeypatch):
    dictionary = lexicon("γίνονται")
    assert LF.find_correction("γίγνονται", "el", dictionary, {}) is not None

    result, replacements, unresolved = correct(
        monkeypatch, "γίγνονται", dictionary, ancient=True
    )

    assert result == "γίγνονται"
    assert replacements == []
    assert unresolved[0][4] == "ancient-file"


def test_polytonic_line_is_preserved_while_modern_line_is_repaired(monkeypatch):
    result, replacements, _ = correct(
        monkeypatch, "κόομος ἀνθρώπου\r\nκόομος", lexicon("κόσμος")
    )

    assert result == "κόομος ἀνθρώπου\r\nκόσμος"
    assert len(replacements) == 1


def test_filter_preserves_every_character_outside_the_replacement():
    text = "--- page 12 ---\r\n  (κόομος),\tEnglish!\r\n\r\nτέλος\r\n"
    start = text.index("κόομος")

    assert LF.filter_chunk(text, []) == text
    assert LF.filter_chunk(text, [(start, start + len("κόομος"), "κόσμος")]) == (
        "--- page 12 ---\r\n  (κόσμος),\tEnglish!\r\n\r\nτέλος\r\n"
    )
