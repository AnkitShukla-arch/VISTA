"""VISTA Phase 1 orchestrator.

Runs the full ASTRA-style layered pipeline against MinIO:

    1. ingest_raw       - mirror data/processed/phase1_dataset -> s3://vista-lake/raw/
    2. clean            - clean + deduplicate -> outputs/pipeline/clean/*.parquet
    3. summarize        - profile every clean source -> outputs/pipeline/summaries/
    4. upload_processed - push clean + summaries layers to MinIO

Usage (from the VISTA root, with the MinIO stack running):
    .venv/Scripts/python project/code/run_phase1.py                # everything
    .venv/Scripts/python project/code/run_phase1.py --skip-raw     # reuse raw layer
    .venv/Scripts/python project/code/run_phase1.py --only clean   # one step
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vista_pipeline import WORK_DIR, get_logger, get_minio, put_json  # noqa: E402

log = get_logger("phase1")


def step_ingest(args) -> dict:
    from vista_pipeline.ingest_raw import run as ingest_run
    return ingest_run(dry_run=args.dry_run)


def step_clean(args) -> dict:
    from vista_pipeline.clean import run as clean_run
    return clean_run()


def step_summarize(args) -> dict:
    from vista_pipeline.summarize import run as summarize_run
    return summarize_run()


def step_upload(args) -> dict:
    from vista_pipeline.upload_processed import run as upload_run
    return upload_run()


STEPS = [
    ("ingest_raw", step_ingest),
    ("clean", step_clean),
    ("summarize", step_summarize),
    ("upload_processed", step_upload),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="VISTA Phase 1 ETL")
    parser.add_argument("--only", choices=[s for s, _ in STEPS], help="run a single step")
    parser.add_argument("--skip-raw", action="store_true", help="skip raw upload (already done)")
    parser.add_argument("--dry-run", action="store_true", help="ingest: list files only")
    args = parser.parse_args()

    steps = [s for s in STEPS if args.only is None or s[0] == args.only]
    if args.skip_raw:
        steps = [s for s in steps if s[0] != "ingest_raw"]

    results, failed = {}, None
    for name, fn in steps:
        log.info("=== %s ===", name)
        t0 = time.perf_counter()
        try:
            results[name] = fn(args)
        except Exception:
            failed = name
            log.exception("step %s failed", name)
            break
        log.info("=== %s done in %.1fs ===", name, time.perf_counter() - t0)

    run_report = {
        "phase": 1,
        "completed_steps": [s for s, _ in steps if s in results],
        "failed_step": failed,
        "results": results,
    }
    out = WORK_DIR / "phase1_run_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run_report, indent=2, default=str), encoding="utf-8")

    # Persist a run report alongside the data in MinIO.
    if not args.dry_run:
        try:
            put_json(get_minio(), "reports/phase1_run_report.json", run_report)
        except Exception:
            log.warning("could not write run report to MinIO (is the stack up?)")

    log.info("Run report -> %s", out)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
