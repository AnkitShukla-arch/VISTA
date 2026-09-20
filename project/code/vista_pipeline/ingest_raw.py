"""Step 1 — upload the phase-one dataset to MinIO unchanged (raw layer).

Everything under data/processed/phase1_dataset is mirrored into
s3://vista-lake/raw/, preserving relative paths. Text-ish files are uploaded
as-is in streaming mode so the 400 MB CSVs never sit in memory.
"""

from __future__ import annotations

import hashlib
import os

from . import BUCKET, PREFIXES, RAW_DIR, get_logger, get_minio

log = get_logger("ingest")

# File extensions we treat as data files (everything else is skipped).
DATA_EXTS = {".csv", ".txt", ".pdf", ".docx", ".json", ".md"}


def iter_source_files():
    for path in sorted(RAW_DIR.rglob("*")):
        if path.is_file() and path.suffix.lower() in DATA_EXTS:
            yield path


def file_md5(path, chunk_size=1 << 20) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def run(dry_run: bool = False) -> dict:
    client = get_minio()
    log.info("Scanning %s ...", RAW_DIR)

    stats = {"files": 0, "bytes": 0, "skipped_existing": 0}
    for path in iter_source_files():
        rel = path.relative_to(RAW_DIR).as_posix()
        key = f"{PREFIXES['raw']}/{rel}"
        size = path.stat().st_size
        stats["files"] += 1
        stats["bytes"] += size

        if dry_run:
            continue

        # Skip files already uploaded with identical content (idempotent re-runs).
        try:
            st = client.stat_object(BUCKET, key)
            if st.size == size and st.etag.strip('"') == file_md5(path):
                stats["skipped_existing"] += 1
                continue
        except Exception:
            pass  # not present -> upload

        ctype = "text/csv" if path.suffix == ".csv" else "application/octet-stream"
        with open(path, "rb") as fh:
            client.put_object(BUCKET, key, fh, size, content_type=ctype)
        if stats["files"] % 500 == 0:
            log.info("  uploaded %d files ...", stats["files"])

    log.info(
        "Raw layer: %d files, %.1f MB (%d already present, skipped)",
        stats["files"], stats["bytes"] / 1e6, stats["skipped_existing"],
    )
    return stats


if __name__ == "__main__":
    run()
