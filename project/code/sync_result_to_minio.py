"""Sync RESULT/clean_data -> MinIO (finishes the phase-1 upload).

The ETL run (run_phase1.py) uploaded the clean layer built from the structured
sources, but RESULT/clean_data is the authoritative phase-2 input: it also
contains `reports_ocr.parquet`, the PaddleOCR texts under `ocr_text/`, and the
final manifest + summary. This script mirrors that folder into the lake:

  RESULT/clean_data/*.parquet          -> s3://vista-lake/clean/<name>.parquet
  RESULT/clean_data/ocr_text/*.txt     -> s3://vista-lake/clean/ocr_text/<name>.txt
  RESULT/clean_data/_manifest.json     -> s3://vista-lake/clean/_manifest.json
  RESULT/clean_data/phase1_clean_summary.md
                                       -> s3://vista-lake/summaries/phase1_clean_summary.md

Uploads are idempotent: objects whose size + md5 etag already match are skipped,
so re-runs are cheap and never corrupt existing data (the bucket is versioned).

Usage (from the VISTA root, MinIO stack running):
    .venv/Scripts/python project/code/sync_result_to_minio.py
    .venv/Scripts/python project/code/sync_result_to_minio.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "project" / "code"))

from vista_pipeline import BUCKET, PREFIXES, RESULT_DIR, get_logger, get_minio  # noqa: E402

log = get_logger("sync-result")

CLEAN_DATA_DIR = RESULT_DIR / "clean_data"
OCR_TEXT_DIR = CLEAN_DATA_DIR / "ocr_text"

CONTENT_TYPES = {
    ".parquet": "application/x-parquet",
    ".json": "application/json",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def file_md5(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_if_changed(client, local: Path, key: str) -> str:
    """Upload local file to key unless an identical object already exists."""
    size = local.stat().st_size
    try:
        st = client.stat_object(BUCKET, key)
        if st.size == size and st.etag.strip('"') == file_md5(local):
            return "skipped"
    except Exception:
        pass  # not present -> upload

    ctype = CONTENT_TYPES.get(local.suffix.lower(), "application/octet-stream")
    with open(local, "rb") as fh:
        client.put_object(BUCKET, key, fh, size, content_type=ctype)
    return "uploaded"


def run(dry_run: bool = False) -> dict:
    client = get_minio() if not dry_run else None
    stats = {"uploaded": 0, "skipped": 0, "bytes": 0}

    def do(local: Path, key: str) -> None:
        stats["bytes"] += local.stat().st_size
        if dry_run:
            action = "would-upload"
        else:
            action = upload_if_changed(client, local, key)
        stats["uploaded" if action == "uploaded" else "skipped"] += 1
        log.info("  %-58s %s (%.1f KB)", key, action, local.stat().st_size / 1e3)

    log.info("=== clean parquets ===")
    for pq in sorted(CLEAN_DATA_DIR.glob("*.parquet")):
        do(pq, f"{PREFIXES['clean']}/{pq.name}")

    log.info("=== ocr_text ===")
    for txt in sorted(OCR_TEXT_DIR.glob("*.txt")):
        do(txt, f"{PREFIXES['clean']}/ocr_text/{txt.name}")

    log.info("=== manifest + summary ===")
    manifest = CLEAN_DATA_DIR / "_manifest.json"
    do(manifest, f"{PREFIXES['clean']}/_manifest.json")

    summary = CLEAN_DATA_DIR / "phase1_clean_summary.md"
    if summary.exists():
        # Keep the ETL phase1_summary.md; add the RESULT roll-up next to it.
        do(summary, f"{PREFIXES['summaries']}/phase1_clean_summary.md")

    verb = "would upload" if dry_run else "uploaded"
    log.info("Done: %d %s, %d skipped, %.1f MB total",
             stats["uploaded"], verb, stats["skipped"], stats["bytes"] / 1e6)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync RESULT/clean_data to MinIO")
    parser.add_argument("--dry-run", action="store_true", help="list actions only")
    args = parser.parse_args()
    raise SystemExit(0 if run(dry_run=args.dry_run) is not None else 1)
