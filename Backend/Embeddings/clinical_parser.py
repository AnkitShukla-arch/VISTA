"""
Clinical Section Parser and Medical Data Loader.
Owner: Arpit Umrao (Embeddings & Similarity Math Engineer)

Enhancement: Section-aware clinical text extraction that prioritizes high-salience
diagnostic sections (Chief Complaint, Impression, Assessment, Diagnosis) before
embedding generation, preventing loss of vital medical context from 512-token truncation.
"""
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd


class ClinicalSectionParser:
    """
    Parses unstructured and semi-structured medical transcripts (SOAP format,
    discharge summaries, consult notes) into structured clinical sections.
    """

    # Common standardized clinical headers in MTSamples and EHR notes
    SECTION_HEADERS = [
        "CHIEF COMPLAINT",
        "REASON FOR VISIT",
        "HISTORY OF PRESENT ILLNESS",
        "SUBJECTIVE",
        "OBJECTIVE",
        "PAST MEDICAL HISTORY",
        "MEDICATIONS",
        "ALLERGIES",
        "PHYSICAL EXAMINATION",
        "LABORATORY DATA",
        "DIAGNOSTIC STUDIES",
        "IMPRESSION",
        "ASSESSMENT",
        "DIAGNOSIS",
        "DISCHARGE DIAGNOSIS",
        "HOSPITAL COURSE",
        "PLAN",
        "DISCHARGE PLAN",
    ]

    # Pre-compiled regex pattern for header matching
    _HEADER_REGEX = re.compile(
        r"(?i)\b(" + "|".join(re.escape(h) for h in SECTION_HEADERS) + r")\s*[:\-\n]",
        re.MULTILINE,
    )

    @classmethod
    def parse_sections(cls, text: str) -> Dict[str, str]:
        """
        Splits medical report into labeled sections based on standard clinical headers.
        """
        if not text or not isinstance(text, str):
            return {}

        matches = list(cls._HEADER_REGEX.finditer(text))
        if not matches:
            return {"BODY": text.strip()}

        sections: Dict[str, str] = {}

        # Capture preamble before first section header if present
        first_start = matches[0].start()
        if first_start > 0:
            preamble = text[:first_start].strip()
            if preamble:
                sections["PREAMBLE"] = preamble

        for idx, match in enumerate(matches):
            header_name = match.group(1).upper().strip()
            content_start = match.end()
            content_end = (
                matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            )

            content = text[content_start:content_end].strip()
            # Clean up trailing/leading commas or dashes
            content = re.sub(r"^[\s,:\-]+", "", content)
            sections[header_name] = content

        return sections

    @classmethod
    def build_diagnostic_summary(
        cls,
        text: str,
        title: Optional[str] = None,
        category: Optional[str] = None,
        max_chars: int = 1500,
    ) -> str:
        """
        Builds a dense, semantically-rich text string specifically optimized for 
        Sentence Transformer embeddings.

        Priority Order:
        1. Specialty Category & Document Title (Immediate domain anchor)
        2. Diagnosis / Assessment / Impression (Core clinical finding)
        3. Chief Complaint / Reason for Visit (Symptom context)
        4. Hospital Course / Summary Findings
        5. General Body / Subjective History
        """
        sections = cls.parse_sections(text)

        parts = []

        # 1. Header Context
        header_parts = []
        if category:
            header_parts.append(f"Specialty: {category.strip()}")
        if title:
            header_parts.append(f"Clinical Title: {title.strip()}")
        if header_parts:
            parts.append(" | ".join(header_parts))

        # 2. Diagnostic & Outcome Sections (High-priority)
        diag_keys = ["DIAGNOSIS", "DISCHARGE DIAGNOSIS", "IMPRESSION", "ASSESSMENT"]
        for key in diag_keys:
            if key in sections and sections[key]:
                parts.append(f"{key.title()}: {sections[key]}")

        # 3. Chief Complaint / Reason for visit
        complaint_keys = ["CHIEF COMPLAINT", "REASON FOR VISIT", "SUBJECTIVE"]
        for key in complaint_keys:
            if key in sections and sections[key]:
                parts.append(f"{key.title()}: {sections[key]}")

        # 4. Hospital Course / Plan
        course_keys = ["HOSPITAL COURSE", "PLAN", "DISCHARGE PLAN"]
        for key in course_keys:
            if key in sections and sections[key]:
                parts.append(f"{key.title()}: {sections[key]}")

        # 5. If no structured sections matched, fallback to cleaned raw text
        if len(parts) <= 1:
            body = sections.get("BODY", text)
            parts.append(body[:max_chars])

        combined = "\n".join(parts)
        # Truncate cleanly at word boundary if exceeding max_chars
        if len(combined) > max_chars:
            combined = combined[:max_chars].rsplit(" ", 1)[0] + "..."

        return combined


class ClinicalDataLoader:
    """
    Loads, parses, and prepares medical records for embedding generation.
    """

    @staticmethod
    def load_mtsamples_csv(
        csv_path: Path,
        sample_size: Optional[int] = None,
        random_state: int = 42,
    ) -> List[Dict[str, Any]]:
        """
        Loads the MTSamples medical transcriptions from CSV, cleans, and generates
        diagnostic summaries for embedding.

        Returns:
            List of dicts: [
                {
                    'doc_id': str,
                    'category': str,
                    'title': str,
                    'raw_text': str,
                    'diagnostic_summary': str
                }, ...
            ]
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"MTSamples file not found: {csv_path}")

        # Read required columns
        df = pd.read_csv(
            csv_path,
            usecols=["doc_id", "category", "title", "text"],
            dtype=str,
        )

        # Drop rows with null text or category
        df = df.dropna(subset=["text", "category"])
        df = df[df["text"].str.strip() != ""]

        if sample_size and sample_size < len(df):
            df = df.sample(n=sample_size, random_state=random_state)

        records = []
        for _, row in df.iterrows():
            raw_text = str(row["text"]).strip()
            title = str(row.get("title", "")).strip()
            category = str(row.get("category", "")).strip()
            doc_id = str(row["doc_id"]).strip()

            summary = ClinicalSectionParser.build_diagnostic_summary(
                text=raw_text,
                title=title,
                category=category,
            )

            records.append(
                {
                    "doc_id": doc_id,
                    "category": category,
                    "title": title,
                    "raw_text": raw_text,
                    "diagnostic_summary": summary,
                }
            )

        return records

    @staticmethod
    def load_unstructured_notes(
        notes_dir: Path,
        max_notes: Optional[int] = 100,
    ) -> List[Dict[str, Any]]:
        """
        Loads clinical notes from individual text files (e.g. Full_Medical_Data_Lake/unstructured_notes).
        """
        notes_dir = Path(notes_dir)
        if not notes_dir.exists():
            raise FileNotFoundError(f"Notes directory not found: {notes_dir}")

        records = []
        count = 0
        for txt_file in notes_dir.glob("*.txt"):
            if max_notes and count >= max_notes:
                break

            content = txt_file.read_text(encoding="utf-8", errors="ignore").strip()
            if not content:
                continue

            summary = ClinicalSectionParser.build_diagnostic_summary(
                text=content,
                title=txt_file.stem,
            )

            records.append(
                {
                    "doc_id": txt_file.stem,
                    "category": "EHR_Note",
                    "title": txt_file.name,
                    "raw_text": content,
                    "diagnostic_summary": summary,
                }
            )
            count += 1

        return records
