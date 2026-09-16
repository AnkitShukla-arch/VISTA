"""Step 4 — upload clean + summaries layers to MinIO.

  s3://vista-lake/clean/<name>.parquet        deduplicated, typed datasets
  s3://vista-lake/clean/_manifest.json        per-source cleaning stats
  s3://vista-lake/summaries/<name>.json       per-source profile summaries
  s3://vista-lake/summaries/phase1_summary.md human-readable roll-up
"""

from __future__ import annotations

import json

from . import PREFIXES, WORK_DIR, get_logger, get_minio, put_json, put_parquet, put_text

log = get_logger("upload")


def run() -> dict:
    client = get_minio()
    clean_dir = WORK_DIR / "clean"
    summary_dir = WORK_DIR / "summaries"

    uploaded = {"clean": [], "summaries": []}

    manifest = {}
    manifest_path = clean_dir / "_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for parquet in sorted(clean_dir.glob("*.parquet")):
        key = f"{PREFIXES['clean']}/{parquet.name}"
        df = __import__("pandas").read_parquet(parquet)
        put_parquet(client, key, df)
        uploaded["clean"].append(key)
        log.info("clean/%s  (%d rows)", parquet.name, len(df))

    if manifest:
        put_json(client, f"{PREFIXES['clean']}/_manifest.json", manifest)

    for jf in sorted(summary_dir.glob("*.json")):
        key = f"{PREFIXES['summaries']}/{jf.name}"
        put_json(client, key, json.loads(jf.read_text(encoding="utf-8")))
        uploaded["summaries"].append(key)

    md = summary_dir / "phase1_summary.md"
    if md.exists():
        put_text(client, f"{PREFIXES['summaries']}/phase1_summary.md", md.read_text(encoding="utf-8"))
        uploaded["summaries"].append(f"{PREFIXES['summaries']}/phase1_summary.md")

    log.info("Uploaded %d clean objects + %d summary objects",
             len(uploaded["clean"]), len(uploaded["summaries"]))
    return uploaded


if __name__ == "__main__":
    run()
