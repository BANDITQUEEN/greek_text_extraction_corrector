"""Run the existing command's processing path with small, public test data."""

import csv
import re
from types import SimpleNamespace

import pytest

import lexicon_filter as LF


@pytest.fixture
def isolated_globals(monkeypatch):
    """main() configures module globals. Restore them after each test."""
    for name in (
        "INPUT_DIR",
        "TAGGER",
        "RUN_NAME",
        "OUTPUT_DIR",
        "CHECKPOINT_PATH",
        "CORRECTIONS_LOG",
        "UNRESOLVED_LOG",
    ):
        monkeypatch.setattr(LF, name, getattr(LF, name))


def test_missing_input_directory_is_an_error(tmp_path, monkeypatch, isolated_globals):
    output_root = tmp_path / "results"
    monkeypatch.setattr(LF, "OUTPUT_ROOT", output_root)
    with pytest.raises(SystemExit, match="Input directory not found"):
        LF.main(["--input-dir", str(tmp_path / "missing")])
    assert not output_root.exists()


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_run_preserves_source_bytes_and_writes_audit_logs(
    tmp_path, monkeypatch, isolated_globals, newline
):
    input_dir = tmp_path / "input"
    lexicon_dir = tmp_path / "lexicons"
    output_root = tmp_path / "results"
    input_dir.mkdir()
    lexicon_dir.mkdir()
    (lexicon_dir / "el.txt").write_text("είναι 100\nΑθήνα 100\n", encoding="utf-8")
    (lexicon_dir / "el.known.txt").write_text("είναι\nΑθήνα\n", encoding="utf-8")
    original = newline.join(["  εϊναι\txyz αβγδεζη", "--- page 2 ---", "Αθήνα", ""])
    source = input_dir / "sample.txt"
    source.write_bytes(original.encode("utf-8"))

    monkeypatch.setattr(LF, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(LF, "LEXICON_DIR", lexicon_dir)

    def pages(chunks):
        for chunk in chunks:
            yield [
                LF.Tagged(m.group(), m.start(), False)
                for m in re.finditer(r"\S+", chunk)
            ]

    monkeypatch.setattr(
        LF, "make_tagger", lambda: SimpleNamespace(name="spacy", pages=pages)
    )
    LF.main(["--input-dir", str(input_dir), "--run-name", "test"])

    result = output_root / "lexicon_filtered__test" / source.name
    assert result.read_bytes() == original.replace("εϊναι", "είναι").encode("utf-8")
    assert source.read_bytes() == original.encode("utf-8")
    with (output_root / "lexicon_corrections__test.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        corrections = list(csv.DictReader(handle))
    assert len(corrections) == 1
    assert corrections[0]["original"] == "εϊναι"
    assert corrections[0]["replacement"] == "είναι"
    with (output_root / "lexicon_unresolved__test.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        unresolved = list(csv.DictReader(handle))
    assert [(row["token"], row["reason"]) for row in unresolved] == [
        ("αβγδεζη", "no-candidate")
    ]
    assert not (output_root / "lexicon_filter_checkpoint__test.pkl.gz").exists()
