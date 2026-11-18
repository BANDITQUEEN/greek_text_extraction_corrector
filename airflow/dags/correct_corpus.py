"""Correct a corpus in batches and check each batch for word loss."""

import subprocess
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
from airflow.sdk import Param, dag, get_current_context, task, task_group

DATA_DIR = Path("/opt/airflow/data")
INPUT_DIR = Path("/opt/airflow/raw")
LEXICON_DIR = DATA_DIR / "lexicons"
BATCHES_DIR = DATA_DIR / "batches"
RUNS_DIR = DATA_DIR / "runs"
CORRECTOR_BIN = Path("/opt/corrector/.venv/bin")
CHECK_SCRIPT = "/opt/corrector/scripts/check_no_deletion.py"


def run_key(run_id: str) -> str:
    dag_run = get_current_context()["dag_run"]
    local_time = dag_run.run_after.astimezone(ZoneInfo("Europe/Athens"))
    timestamp = local_time.strftime("%Y-%m-%d_%H-%M-%S")
    digest = sha256(run_id.encode("utf-8")).hexdigest()[:16]
    return f"{timestamp}__{digest}"


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
    params={
        "batch_size": Param(2, type="integer", minimum=1),
        "max_files": Param(4, type=["integer", "null"], minimum=1),
    },
)
def correct_corpus():
    @task
    def plan_batches(*, run_id: str, params: dict) -> list[str]:
        if not INPUT_DIR.is_dir():
            raise FileNotFoundError(f"Corpus mount not found: {INPUT_DIR}")

        files = sorted(p.name for p in INPUT_DIR.glob("*.txt") if p.is_file())
        files = files[:params["max_files"]]
        if not files:
            raise ValueError(f"No .txt files found in {INPUT_DIR}")

        batch_size = params["batch_size"]
        folder = BATCHES_DIR / run_key(run_id)
        folder.mkdir(parents=True, exist_ok=True)
        manifests = []
        for index, start in enumerate(range(0, len(files), batch_size), start=1):
            names = files[start:start + batch_size]
            manifest = folder / f"batch-{index:03d}.txt"
            manifest.write_text("\n".join(names) + "\n", encoding="utf-8")
            manifests.append(str(manifest))
            print(f"{manifest.name}: {len(names)} file(s)")
        return manifests

    @task(max_active_tis_per_dag=1)
    def correct(files_from: str, *, run_id: str) -> str:
        output_dir = RUNS_DIR / run_key(run_id) / Path(files_from).stem
        print(f"Output directory: {output_dir}")
        run_command(
            str(CORRECTOR_BIN / "greek-correct"),
            "--input-dir", str(INPUT_DIR),
            "--files-from", files_from,
            "--lexicon-dir", str(LEXICON_DIR),
            "--output-dir", str(output_dir),
        )
        return str(output_dir / "lexicon_filtered")

    @task
    def check_no_deletion(files_from: str, corrected_dir: str) -> None:
        run_command(
            str(CORRECTOR_BIN / "python"),
            CHECK_SCRIPT,
            "--input-dir", str(INPUT_DIR),
            "--files-from", files_from,
            "--corrected-dir", corrected_dir,
        )

    @task_group
    def process_batch(files_from: str):
        check_no_deletion(files_from, correct(files_from))

    process_batch.expand(files_from=plan_batches())


correct_corpus()