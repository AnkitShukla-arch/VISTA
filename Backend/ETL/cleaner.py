"""
Clinical Text Cleaning and Normalization Pipeline.
"""
import re
import hashlib
from typing import List, Dict, Any, Optional


class MedicalTextCleaner:
    """Utilities for cleaning, deduplicating, and formatting medical text reports."""

    @staticmethod
    def compute_hash(text: str) -> str:
        """Compute MD5 hash of normalized text for deduplication."""
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean medical clinical text:
        - Removes redundant formatting artifacts
        - Normalizes whitespace and line breaks
        - Preserves clinical abbreviations and measurements
        """
        if not text or not isinstance(text, str):
            return ""

        # Normalize special unicode spaces and dashes
        text = text.replace("\xa0", " ").replace("–", "-").replace("—", "-")
        # Remove repetitive separator lines like '-----' or '====='
        text = re.sub(r"[-=_]{3,}", " ", text)
        # Collapse multiple spaces and excessive newlines
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    @staticmethod
    def deduplicate_records(
        records: List[Dict[str, Any]], text_key: str = "text"
    ) -> List[Dict[str, Any]]:
        """Deduplicate records based on content hash."""
        seen_hashes = set()
        deduped = []

        for record in records:
            content = record.get(text_key, "")
            h = MedicalTextCleaner.compute_hash(content)
            if h not in seen_hashes:
                seen_hashes.add(h)
                deduped.append(record)

        return deduped
