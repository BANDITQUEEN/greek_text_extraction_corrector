"""The word-list download: verify before writing, never overwrite local edits."""

import hashlib
import io
import zipfile

import pytest

from scripts import fetch_lexicons


def make_bundle(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)
    return buffer.getvalue()


def publish(tmp_path, data):
    """Serve a bundle from a file:// URL; return the URL and its SHA-256."""
    path = tmp_path / "bundle.zip"
    path.write_bytes(data)
    return path.as_uri(), hashlib.sha256(data).hexdigest()


def test_verified_bundle_installs_every_list(tmp_path):
    files = {"el.txt": b"a 100\n", "el.known.txt": b"a\n"}
    url, sha256 = publish(tmp_path, make_bundle(files))
    lexicon_dir = tmp_path / "lexicons"

    kept = fetch_lexicons.unpack(fetch_lexicons.download(url, sha256), lexicon_dir, False)

    assert kept == []
    assert {p.name: p.read_bytes() for p in lexicon_dir.iterdir()} == files


def test_checksum_mismatch_is_refused(tmp_path):
    url, _ = publish(tmp_path, make_bundle({"el.txt": b"a 100\n"}))
    with pytest.raises(SystemExit, match="checksum mismatch"):
        fetch_lexicons.download(url, "0" * 64)


def test_default_destination_is_the_user_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    expected = tmp_path / "greek-correct" / "lexicons"
    assert fetch_lexicons.parse_args([]).lexicon_dir == expected


def test_local_edit_is_kept_unless_forced(tmp_path):
    lexicon_dir = tmp_path / "lexicons"
    lexicon_dir.mkdir()
    (lexicon_dir / "el.txt").write_bytes(b"edited\n")
    data = make_bundle({"el.txt": b"released\n"})

    assert fetch_lexicons.unpack(data, lexicon_dir, force=False) == ["el.txt"]
    assert (lexicon_dir / "el.txt").read_bytes() == b"edited\n"

    assert fetch_lexicons.unpack(data, lexicon_dir, force=True) == []
    assert (lexicon_dir / "el.txt").read_bytes() == b"released\n"
