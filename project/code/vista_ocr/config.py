import os

# ==========================================================
# MinIO Configuration (VISTA project .env / defaults)
# ==========================================================

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")

MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", os.getenv("MINIO_ROOT_USER", "vistaadmin"))

MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", os.getenv("MINIO_ROOT_PASSWORD", "vista-secret-1"))

# Buckets (bronze = raw evidence, silver = OCR output, rejected = quarantined files)
BRONZE_BUCKET = os.getenv("BRONZE_BUCKET", "bronze")
SILVER_BUCKET = os.getenv("SILVER_BUCKET", "silver")
REJECTED_BUCKET = os.getenv("REJECTED_BUCKET", "rejected")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pipeline.db")

MAX_FILE_SIZE = 100 * 1024 * 1024   # 100 MB

SUPPORTED_FILES = [
    ".csv",
    ".json",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg"
]