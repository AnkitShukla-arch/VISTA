"""
MinIO Object Storage Adapter
Responsible for persisting and retrieving raw unstructured medical reports (PDF/DOCX/TXT).
"""
from Database.MinIO.client import MinIOStorageManager

__all__ = ["MinIOStorageManager"]
