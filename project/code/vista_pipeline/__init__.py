"""Shared configuration and helpers for the VISTA phase-1 ETL pipeline.

The pipeline follows the ASTRA layered-storage approach: data lands in MinIO
in immutable layers (raw -> clean -> summaries) so phase 2 can later consume
the clean layer for vector conversion without re-cleaning anything.
"""

from __future__ import annotations

import logging
import os
import sys
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from minio import Minio
from minio.commonconfig import ENABLED
from minio.versioningconfig import VersioningConfig

PROJECT_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = PROJECT_ROOT / "data" / "processed" / "phase1_dataset"
WORK_DIR = PROJECT_ROOT / "outputs" / "pipeline"
RESULT_DIR = PROJECT_ROOT / "RESULT"

BUCKET = os.getenv("MINIO_BUCKET", "vista-lake")
PREFIXES = {
    "raw": "raw",           # original files, uploaded unchanged
    "clean": "clean",       # cleaned + deduplicated parquet outputs
    "summaries": "summaries",  # per-source summary reports + data dictionary
}


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


@lru_cache(maxsize=1)
def get_minio() -> Minio:
    """Build a MinIO client from .env, ensuring the bucket exists and is versioned."""
    load_dotenv(PROJECT_ROOT / ".env")
    client = Minio(
        os.getenv("MINIO_ENDPOINT", "http://localhost:9000").replace("http://", "").replace("https://", ""),
        access_key=os.getenv("MINIO_ROOT_USER", "vistaadmin"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", "vista-secret-1"),
        secure=False,
    )
    if not client.bucket_exists(BUCKET):
        client.make_bucket(BUCKET)
        # Version the bucket so re-runs never silently overwrite raw evidence.
        client.set_bucket_versioning(BUCKET, VersioningConfig(ENABLED))
    return client


def put_json(client: Minio, key: str, payload: dict | list) -> None:
    import json

    data = json.dumps(payload, indent=2, default=str).encode("utf-8")
    client.put_object(BUCKET, key, BytesIO(data), len(data), "application/json")


def put_parquet(client: Minio, key: str, df: pd.DataFrame) -> None:
    buf = BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    client.put_object(BUCKET, key, buf, buf.getbuffer().nbytes, "application/x-parquet")


def put_text(client: Minio, key: str, text: str) -> None:
    data = text.encode("utf-8")
    client.put_object(BUCKET, key, BytesIO(data), len(data), "text/plain; charset=utf-8")
