"""
MinIO Object Storage Client Wrapper.
"""
from pathlib import Path
from typing import Optional


class MinIOStorageManager:
    """Manages raw medical document storage in MinIO."""

    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        secure: bool = False,
        bucket_name: str = "medical-reports",
    ):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.bucket_name = bucket_name
        self._client = None

    @property
    def client(self):
        """Lazy loader for MinIO client."""
        if self._client is None:
            try:
                from minio import Minio

                self._client = Minio(
                    self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=self.secure,
                )
                if not self._client.bucket_exists(self.bucket_name):
                    self._client.make_bucket(self.bucket_name)
            except ImportError:
                raise ImportError("minio package is required. Install via: pip install minio")
        return self._client

    def upload_file(self, file_path: Path, object_name: Optional[str] = None) -> str:
        """Upload a local report file to MinIO."""
        file_path = Path(file_path)
        obj_name = object_name or file_path.name
        self.client.fput_object(self.bucket_name, obj_name, str(file_path))
        return obj_name

    def download_file(self, object_name: str, target_path: Path) -> Path:
        """Download an object from MinIO to a local path."""
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.fget_object(self.bucket_name, object_name, str(target_path))
        return target_path
