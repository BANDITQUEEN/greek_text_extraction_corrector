"""Download the word lists the corrector uses into lexicons/.

All five lists ship as one zip attached to this repository's GitHub release
lexicons-v1, together with a README naming each list's source and license.
The zip is checked against a SHA-256 before anything is unpacked.

    uv run python scripts/fetch_lexicons.py

A list that already matches the release is left as it is. One that differs,
such as a toponym list you rebuilt, is kept unless you pass --force.

To publish new lists: zip them with the README into lexicons-vN.zip, attach
it to a release named lexicons-vN, then update RELEASE and SHA256 below.
"""

import argparse
import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

RELEASE = "lexicons-v1"
URL = (
    "https://github.com/BANDITQUEEN/greek_text_extraction_corrector"
    f"/releases/download/{RELEASE}/{RELEASE}.zip"
)
SHA256 = "397641735676d2ab61ad0ba714e44bd3eac2fc150b8eeb2b549ecf10828c7298"


def download(url, expected_sha256):
    """Return the zip at url, refusing it unless its SHA-256 matches."""
    print(f"downloading {url}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise SystemExit(
            f"checksum mismatch: expected {expected_sha256}, got {actual}. "
            "Nothing was written."
        )
    print(f"verified {len(data) / 1e6:.1f} MB", flush=True)
    return data


def unpack(data, lexicon_dir, force):
    """Write each list into lexicon_dir. Return the names kept because they differ."""
    lexicon_dir.mkdir(parents=True, exist_ok=True)
    kept = []
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        for name in bundle.namelist():
            content = bundle.read(name)
            target = lexicon_dir / Path(name).name
            if target.exists():
                if target.read_bytes() == content:
                    print(f"{target.name}: up to date")
                    continue
                if not force:
                    print(f"{target.name}: differs from the release; kept "
                          "(rerun with --force to replace it)")
                    kept.append(target.name)
                    continue
            partial = target.with_name(target.name + ".part")
            partial.write_bytes(content)
            partial.replace(target)
            print(f"{target.name}: installed")
    return kept


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lexicon-dir", type=Path, default=Path("lexicons"),
                        help="where to put the word lists (default: ./lexicons)")
    parser.add_argument("--force", action="store_true",
                        help="replace lists that differ from the release")
    args = parser.parse_args()

    if unpack(download(URL, SHA256), args.lexicon_dir, args.force):
        sys.exit(1)


if __name__ == "__main__":
    main()
