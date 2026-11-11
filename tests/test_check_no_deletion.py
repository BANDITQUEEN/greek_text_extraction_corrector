"""The no-deletion check: comparing folders, and running the corrector itself."""

import pytest

from scripts import check_no_deletion as check


def write(folder, name, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(text.encode("utf-8"))


def run(*args):
    check.main([str(arg) for arg in args])


def test_a_one_edit_repair_loses_no_word(tmp_path, capsys):
    write(tmp_path / "raw", "a.txt", "η ταγγελία 2026\n")
    write(tmp_path / "out", "a.txt", "η αγγελία 2026\n")
    run("--input-dir", tmp_path / "raw", "--corrected-dir", tmp_path / "out")
    assert "PASS: no word lost in 1 file(s)" in capsys.readouterr().out


def test_a_lost_word_fails(tmp_path, capsys):
    write(tmp_path / "raw", "a.txt", "ένα δύο τρία\n")
    write(tmp_path / "out", "a.txt", "ένα τρία\n")
    with pytest.raises(SystemExit, match="deleted words"):
        run("--input-dir", tmp_path / "raw", "--corrected-dir", tmp_path / "out")
    assert "LOST 1 word(s) in a.txt" in capsys.readouterr().out


def test_a_missing_corrected_file_fails(tmp_path, capsys):
    write(tmp_path / "raw", "a.txt", "ένα\n")
    write(tmp_path / "raw", "b.txt", "δύο\n")
    write(tmp_path / "out", "a.txt", "ένα\n")
    with pytest.raises(SystemExit, match="1 corrected file"):
        run("--input-dir", tmp_path / "raw", "--corrected-dir", tmp_path / "out")
    assert "MISSING b.txt" in capsys.readouterr().out


def test_files_from_checks_only_the_listed_files(tmp_path, capsys):
    write(tmp_path / "raw", "a.txt", "ένα\n")
    write(tmp_path / "raw", "b.txt", "δύο\n")
    write(tmp_path / "out", "a.txt", "ένα\n")
    write(tmp_path, "batch.txt", "# one batch\na.txt\n")
    run(
        "--input-dir", tmp_path / "raw",
        "--corrected-dir", tmp_path / "out",
        "--files-from", tmp_path / "batch.txt",
    )
    assert "PASS: no word lost in 1 file(s)" in capsys.readouterr().out


def test_an_unknown_name_in_files_from_fails(tmp_path):
    write(tmp_path / "raw", "a.txt", "ένα\n")
    write(tmp_path, "batch.txt", "nope.txt\n")
    with pytest.raises(SystemExit, match="not found"):
        run(
            "--input-dir", tmp_path / "raw",
            "--corrected-dir", tmp_path / "out",
            "--files-from", tmp_path / "batch.txt",
        )


def test_a_full_run_writes_only_to_a_temporary_folder(
    tmp_path, monkeypatch, capsys, isolated_globals, word_tagger
):
    write(tmp_path / "lexicons", "el.txt", "είναι 100\n")
    write(tmp_path / "lexicons", "el.known.txt", "είναι\n")
    write(tmp_path / "raw", "a.txt", "εϊναι καλά\n")
    working_dir = tmp_path / "work"
    monkeypatch.setattr(check.LF, "OUTPUT_ROOT", working_dir)

    run("--input-dir", tmp_path / "raw", "--lexicon-dir", tmp_path / "lexicons")

    assert "PASS: no word lost in 1 file(s)" in capsys.readouterr().out
    assert not working_dir.exists()
