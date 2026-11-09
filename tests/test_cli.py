"""Exercise the installed command outside the repository with the real tagger."""

import csv
import shutil
import subprocess
import sysconfig

import pytest


@pytest.mark.parametrize("explicit_lexicon_dir", [False, True])
def test_installed_command_from_another_directory(
    tmp_path, monkeypatch, explicit_lexicon_dir
):
    command = shutil.which("greek-correct", path=sysconfig.get_path("scripts"))
    assert command is not None, "Install the command first with uv sync --locked"
    monkeypatch.delenv("LEXICON_INPUT_DIR", raising=False)
    work_dir = tmp_path / "work"
    input_dir = work_dir / "input"
    input_dir.mkdir(parents=True)
    lexicon_dir = tmp_path / "wordlists" if explicit_lexicon_dir else work_dir / "lexicons"
    lexicon_dir.mkdir()
    (lexicon_dir / "el.txt").write_text("καλημέρα 100\n", encoding="utf-8")
    (lexicon_dir / "el.known.txt").write_text("καλημέρα\n", encoding="utf-8")
    damaged = "καλημέρα".encode("iso8859_7").decode("cp1252")
    original = f"--- page 1 ---\r\n{damaged}\r\n".encode("utf-8")
    source = input_dir / "sample.txt"
    source.write_bytes(original)

    args = [command]
    if explicit_lexicon_dir:
        args.extend(["--lexicon-dir", str(lexicon_dir)])
    result = subprocess.run(
        args, cwd=work_dir, capture_output=True, encoding="utf-8", timeout=60
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert source.read_bytes() == original
    corrected = work_dir / "lexicon_filtered" / source.name
    assert corrected.read_bytes() == "--- page 1 ---\r\nκαλημέρα\r\n".encode("utf-8")
    with (work_dir / "lexicon_corrections.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        corrections = list(csv.DictReader(handle))
    assert len(corrections) == 1
    assert corrections[0]["original"] == damaged
    assert corrections[0]["replacement"] == "καλημέρα"
    assert corrections[0]["page"] == "1"
