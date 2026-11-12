"""Download the word lists into data/lexicons, and announce when they change.

Started by hand. fetch_lexicons.py runs with the corrector's own Python, so
Airflow never imports spaCy. Only when a list changed does the word_lists
asset get an event; correct_corpus will be scheduled on that asset.
"""

import hashlib
import subprocess
from pathlib import Path

from airflow.sdk import Asset, dag, task

CORRECTOR_PYTHON = "/opt/corrector/.venv/bin/python"
FETCH_LEXICONS = "/opt/corrector/scripts/fetch_lexicons.py"
LEXICON_DIR = Path("/opt/airflow/data/lexicons")

WORD_LISTS = Asset(name="word_lists")


def fingerprint(folder: Path) -> dict[str, str]:
    """The SHA-256 of every file in the folder, by name."""
    if not folder.is_dir():
        return {}
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.iterdir())
        if path.is_file()
    }


@dag(schedule=None, tags=["corrector"], is_paused_upon_creation=False)
def word_lists():
    @task.short_circuit
    def fetch() -> bool:
        """Download and verify the lists. Carry on only if one changed."""
        before = fingerprint(LEXICON_DIR)
        result = subprocess.run(
            [CORRECTOR_PYTHON, FETCH_LEXICONS, "--lexicon-dir", str(LEXICON_DIR)],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            raise RuntimeError(f"fetch_lexicons.py failed:\n{result.stderr}")
        changed = fingerprint(LEXICON_DIR) != before
        print("word lists changed" if changed else "word lists unchanged")
        return changed

    @task(outlets=[WORD_LISTS])
    def announce():
        """Succeeding is the announcement: it adds an event to the asset."""

    fetch() >> announce()


word_lists()
