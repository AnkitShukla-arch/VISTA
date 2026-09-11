"""
MinIO Object Storage Adapter (Owner: Ankit Shukla)
Responsible for persisting and retrieving raw unstructured medical reports (PDF/DOCX/TXT).
"""
from Database.MinIO.client import MinIOStorageManager

__all__ = ["MinIOStorageManager"]
