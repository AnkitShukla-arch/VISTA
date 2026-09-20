"""
OCR & Text Extraction Pipeline
Responsible for extracting text from scanned PDF and DOCX medical reports.
"""
from Backend.OCR.extractor import DocumentExtractor

__all__ = ["DocumentExtractor"]
