"""
Centralized Configuration Settings for VISTA.
Loads environment variables from .env file or system environment.
"""
import os
from pathlib import Path

# Base workspace directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Helper function to read simple .env file without external dependencies
def _load_env_file(env_path: Path):
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("\"'")
            if key not in os.environ:
                os.environ[key] = val

# Load .env file
_load_env_file(BASE_DIR / ".env")


class Settings:
    """Application configuration settings."""

    # Project metadata
    PROJECT_NAME: str = "VISTA"
    PROJECT_VERSION: str = "0.1.0"
    BASE_DIR: Path = BASE_DIR

    # MinIO
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() in ("true", "1")
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "medical-reports")

    # Neon PostgreSQL
    NEON_DATABASE_URL: str = os.getenv(
        "NEON_DATABASE_URL",
        "postgresql://localhost:5432/medicaldb",
    )

    # DuckDB
    DUCKDB_PATH: Path = BASE_DIR / os.getenv(
        "DUCKDB_PATH", "Database/DuckDB/data/metadata.duckdb"
    )

    # Embeddings & Sentence Transformers
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))

    # FAISS Clustering & Boxes
    FAISS_INDEX_PATH: Path = BASE_DIR / os.getenv(
        "FAISS_INDEX_PATH", "Backend/Clustering/data/box_index.faiss"
    )
    FAISS_METADATA_PATH: Path = BASE_DIR / os.getenv(
        "FAISS_METADATA_PATH", "Backend/Clustering/data/box_metadata.json"
    )

    # Dataset Paths
    DATASET_ROOT: Path = BASE_DIR / os.getenv(
        "DATASET_ROOT", "phase1_dataset/phase1_dataset"
    )
    REPORTS_DIR: Path = BASE_DIR / os.getenv(
        "REPORTS_DIR", "phase1_dataset/phase1_dataset/Reports"
    )
    MTSAMPLES_CSV: Path = BASE_DIR / os.getenv(
        "MTSAMPLES_CSV",
        "phase1_dataset/phase1_dataset/medical_data_lake_bundle/combined_dataset.csv",
    )
    DATA_LAKE_DIR: Path = BASE_DIR / os.getenv(
        "DATA_LAKE_DIR", "phase1_dataset/phase1_dataset/Full_Medical_Data_Lake"
    )


settings = Settings()
