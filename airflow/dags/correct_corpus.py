"""Correct the sample corpus and check the resulting files."""

import subprocess
from hashlib import sha256
from pathlib import Path

from airflow.sdk import dag, task

DATA_DIR = Path("/opt/airflow/data")
INPUT_DIR = Path("/opt/airflow/raw")
LEXICON_DIR = DATA_DIR / "lexicons"
RUNS_DIR = DATA_DIR / "runs"
FILES_FROM = DATA_DIR / "batches" / "raw-smoke.txt"
CORRECTOR_BIN = Path("/opt/corrector/.venv/bin")
CHECK_SCRIPT = "/opt/corrector/scripts/check_no_deletion.py"


def run_command(*args: str) -> None:
    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    print(result.stdout, end="")
    result.check_returncode()


@dag(
    schedule=None,
    tags=["corrector"],
    is_paused_upon_creation=False,
    max_active_runs=1,
)
def correct_corpus():
    @task
    def correct(*, run_id: str) -> str:
        run_key = sha256(run_id.encode("utf-8")).hexdigest()[:16]
        output_dir = RUNS_DIR / run_key
        print(f"Output directory: {output_dir}")

        run_command(
            str(CORRECTOR_BIN / "greek-correct"),
            "--input-dir", str(INPUT_DIR),
            "--files-from", str(FILES_FROM),
            "--lexicon-dir", str(LEXICON_DIR),
            "--output-dir", str(output_dir),
        )
        return str(output_dir / "lexicon_filtered")

    @task
    def check_no_deletion(corrected_dir: str) -> None:
        run_command(
            str(CORRECTOR_BIN / "python"),
            CHECK_SCRIPT,
            "--input-dir", str(INPUT_DIR),
            "--files-from", str(FILES_FROM),
            "--corrected-dir", corrected_dir,
        )

    check_no_deletion(correct())


correct_corpus()