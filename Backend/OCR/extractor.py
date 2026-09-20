"""
Document Extraction Pipeline (PDF / DOCX / Image OCR).
"""
from pathlib import Path
from typing import Optional


class DocumentExtractor:
    """Extracts raw text content from multi-format medical reports."""

    @staticmethod
    def extract_from_docx(file_path: Path) -> str:
        """Extract text paragraphs from a .docx file."""
        try:
            import docx

            doc = docx.Document(file_path)
            full_text = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n".join(full_text)
        except ImportError:
            raise ImportError(
                "python-docx is required for docx extraction. Install via: pip install python-docx"
            )

    @staticmethod
    def extract_from_pdf(file_path: Path) -> str:
        """Extract text from a digital PDF file."""
        try:
            import pypdf

            reader = pypdf.PdfReader(file_path)
            pages_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            return "\n".join(pages_text)
        except ImportError:
            raise ImportError(
                "pypdf is required for pdf extraction. Install via: pip install pypdf"
            )

    @classmethod
    def extract(cls, file_path: Path) -> str:
        """Auto-detect format and extract text."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix == ".docx":
            return cls.extract_from_docx(file_path)
        elif suffix == ".pdf":
            return cls.extract_from_pdf(file_path)
        elif suffix in (".txt", ".text"):
            return file_path.read_text(encoding="utf-8", errors="ignore")
        else:
            raise ValueError(f"Unsupported file format for extraction: {suffix}")
