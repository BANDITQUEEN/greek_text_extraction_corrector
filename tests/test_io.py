"""Run the existing command's processing path with small, public test data."""

import csv

import pytest

import lexicon_filter as LF


def write_word_lists(lexicon_dir):
    lexicon_dir.mkdir(parents=True)
    (lexicon_dir / "el.txt").write_text("είναι 100\nΑθήνα 100\n", encoding="utf-8")
    (lexicon_dir / "el.known.txt").write_text("είναι\nΑθήνα\n", encoding="utf-8")


def test_missing_input_directory_is_an_error(tmp_path, monkeypatch, isolated_globals):
    output_root = tmp_path / "results"
    monkeypatch.setattr(LF, "OUTPUT_ROOT", output_root)
    with pytest.raises(SystemExit, match="Input directory not found"):
        LF.main(["--input-dir", str(tmp_path / "missing")])
    assert not output_root.exists()


def test_missing_word_lists_stop_before_any_work(tmp_path, isolated_globals):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "sample.txt").write_bytes("είναι\n".encode("utf-8"))
    empty = tmp_path / "no_lists"
    empty.mkdir()
    output_dir = tmp_path / "results"

    with pytest.raises(SystemExit, match=r"Word lists not found in .*no_lists"):
        LF.main([
            "--input-dir", str(input_dir),
            "--lexicon-dir", str(empty),
            "--output-dir", str(output_dir),
        ])
    assert not output_dir.exists()


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_run_preserves_source_bytes_and_writes_audit_logs(
    tmp_path, monkeypatch, isolated_globals, word_tagger, newline
):
    input_dir = tmp_path / "input"
    lexicon_dir = tmp_path / "lexicons"
    output_root = tmp_path / "results"
    input_dir.mkdir()
    write_word_lists(lexicon_dir)
    original = newline.join(["  εϊναι\txyz αβγδεζη", "--- page 2 ---", "Αθήνα", ""])
    source = input_dir / "sample.txt"
    source.write_bytes(original.encode("utf-8"))

    monkeypatch.setattr(LF, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(LF, "LEXICON_DIR", lexicon_dir)
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


def test_output_dir_receives_every_output(
    tmp_path, monkeypatch, isolated_globals, word_tagger
):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "sample.txt").write_bytes("εϊναι\n".encode("utf-8"))
    write_word_lists(tmp_path / "lexicons")
    working_dir = tmp_path / "work"
    output_dir = tmp_path / "out" / "run1"
    monkeypatch.setattr(LF, "OUTPUT_ROOT", working_dir)

    LF.main([
        "--input-dir", str(input_dir),
        "--lexicon-dir", str(tmp_path / "lexicons"),
        "--output-dir", str(output_dir),
    ])

    corrected = output_dir / "lexicon_filtered" / "sample.txt"
    assert corrected.read_bytes() == "είναι\n".encode("utf-8")
    assert (output_dir / "lexicon_corrections.csv").is_file()
    assert (output_dir / "lexicon_unresolved.csv").is_file()
    assert not (output_dir / "lexicon_filter_checkpoint.pkl.gz").exists()
    assert not working_dir.exists()


def test_a_lexicons_folder_in_the_working_directory_comes_first(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user"))
    user_folder = tmp_path / "user" / "greek-correct" / "lexicons"
    assert LF.default_lexicon_dir(tmp_path) == user_folder

    (tmp_path / "lexicons").mkdir()
    assert LF.default_lexicon_dir(tmp_path) == tmp_path / "lexicons"


@pytest.mark.parametrize(
    "platform, variable, fallback",
    [
        ("win32", "LOCALAPPDATA", ("AppData", "Local")),
        ("linux", "XDG_DATA_HOME", (".local", "share")),
        ("darwin", "XDG_DATA_HOME", (".local", "share")),
    ],
)
def test_user_lexicon_dir_per_platform(tmp_path, monkeypatch, platform, variable, fallback):
    monkeypatch.setenv(variable, str(tmp_path / "data"))
    expected = tmp_path / "data" / "greek-correct" / "lexicons"
    assert LF.user_lexicon_dir(platform) == expected

    monkeypatch.delenv(variable)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    expected = tmp_path.joinpath(*fallback, "greek-correct", "lexicons")
    assert LF.user_lexicon_dir(platform) == expected
