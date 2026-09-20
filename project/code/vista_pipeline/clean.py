"""Step 2 — clean + deduplicate the phase-one dataset (clean layer).

Per source:
  structured CSVs (Full_Medical_Data_Lake + healthcare_dataset)
    - trim/collapse whitespace in text columns, normalise header names
    - parse date columns, coerce numeric columns
    - drop fully-empty rows and exact-duplicate rows
    - normalise ID casing (e.g. adm0001 -> ADM0001)
  text documents (unstructured notes + mtsamples + medical_data_lake_bundle)
    - unicode normalisation, whitespace collapse, control-char removal
    - exact dedupe on normalised text, near-dedupe on (first 400 chars, length bucket)
    - drop empty/placeholder texts

Outputs land in outputs/pipeline/clean/*.parquet, with a manifest of what was
removed at each step. The manifest is written to MinIO in step 4.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

from . import PREFIXES, RAW_DIR, WORK_DIR, get_logger

log = get_logger("clean")

CLEAN_DIR = WORK_DIR / "clean"

_WS_RE = re.compile(r"\s+")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

STRUCTURED_DIR = RAW_DIR / "Full_Medical_Data_Lake"
HEALTHCARE_CSV = RAW_DIR / "healthcare_dataset.csv"
NOTES_DIR = STRUCTURED_DIR / "unstructured_notes"
BUNDLE_CSV = RAW_DIR / "medical_data_lake_bundle" / "combined_dataset.csv"
MTSAMPLES_DIR = RAW_DIR / "mtsamples.csv" / "output"

# Columns that hold identifiers in the structured lake -> uppercase-normalised.
ID_COLUMNS = {"AdmissionID", "PatientID", "DoctorID", "DiseaseID", "DepartmentID",
              "BillingID", "NoteID", "LabID", "PrescriptionID", "patient_id"}


def _is_string_dtype(col: pd.Series) -> bool:
    # pandas 3.0 uses `str` dtype for string columns; `object` on older versions.
    return pd.api.types.is_string_dtype(col) or col.dtype == object


def _normalise_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_WS_RE.sub(" ", str(c)).strip() for c in df.columns]
    return df


def _normalise_text_value(v) -> object:
    if not isinstance(v, str):
        return v
    v = unicodedata.normalize("NFKC", v)
    v = _CTRL_RE.sub(" ", v)
    v = _WS_RE.sub(" ", v).strip()
    return v or None


def _normalise_ids(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if col in ID_COLUMNS and _is_string_dtype(df[col]):
            df[col] = df[col].str.upper().str.strip()
    return df


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if col.lower().endswith(("date",)) and _is_string_dtype(df[col]):
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue  # already numeric
        if col in ID_COLUMNS or col.lower().endswith("id"):
            continue
        num = pd.to_numeric(df[col], errors="coerce")
        # Convert only when nearly all non-null values are numeric
        # (guards phone numbers, ICD codes and other mixed columns).
        non_null = int(df[col].notna().sum())
        if non_null and num.notna().sum() / non_null > 0.95:
            df[col] = num
    return df


def clean_structured_csv(path: Path) -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=["", "NA", "N/A", "null", "NULL"])
    stats = {"rows_raw": len(raw)}

    df = _normalise_headers(raw)
    for col in df.columns:
        if _is_string_dtype(df[col]):
            df[col] = df[col].map(_normalise_text_value)

    df = _normalise_ids(df)
    df = _parse_dates(df)
    df = _coerce_numeric(df)

    before = len(df)
    df = df.dropna(how="all")
    stats["rows_empty_dropped"] = before - len(df)

    before = len(df)
    df = df.drop_duplicates()
    stats["rows_exact_dupes_removed"] = before - len(df)
    stats["rows_clean"] = len(df)
    return df, stats


def normalise_note_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text))
    text = _CTRL_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def clean_text_documents(df: pd.DataFrame, text_col: str, source_name: str) -> tuple[pd.DataFrame, dict]:
    stats = {"rows_raw": len(df)}
    df = df.copy()

    df[text_col] = df[text_col].map(normalise_note_text)

    before = len(df)
    df = df[df[text_col].str.len() > 0]
    stats["rows_empty_dropped"] = before - len(df)

    before = len(df)
    df = df.drop_duplicates(subset=[text_col])
    stats["rows_exact_dupes_removed"] = before - len(df)

    # Near-dedupe: same start-of-text + similar length => keep the longest.
    df["_len_bucket"] = (df[text_col].str.len() // 50) * 50
    df["_fingerprint"] = df[text_col].str[:400]
    before = len(df)
    df = (
        df.sort_values(text_col, key=lambda s: s.str.len(), ascending=False)
          .drop_duplicates(subset=["_fingerprint", "_len_bucket"])
          .drop(columns=["_fingerprint", "_len_bucket"])
    )
    stats["rows_near_dupes_removed"] = before - len(df)
    stats["rows_clean"] = len(df)

    log.info("%s: raw=%d clean=%d (exact=%d, near=%d, empty=%d)",
             source_name, stats["rows_raw"], stats["rows_clean"],
             stats["rows_exact_dupes_removed"], stats.get("rows_near_dupes_removed", 0),
             stats["rows_empty_dropped"])
    return df, stats


def clean_unstructured_notes() -> tuple[pd.DataFrame, dict]:
    records = []
    for path in sorted(NOTES_DIR.glob("*.txt")):
        try:
            records.append({"note_id": path.stem, "text": path.read_text(encoding="utf-8", errors="replace")})
        except OSError as exc:
            log.warning("unreadable note %s: %s", path.name, exc)
    df = pd.DataFrame(records, columns=["note_id", "text"])
    df["source"] = "unstructured_notes"
    return clean_text_documents(df, "text", "unstructured_notes")


def clean_bundle() -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(BUNDLE_CSV)
    df = df.rename(columns={"doc_id": "doc_id", "source": "bundle_source", "category": "category",
                            "title": "title", "text": "text"})
    df["source"] = "medical_data_lake_bundle"
    return clean_text_documents(df, "text", "medical_data_lake_bundle")


def clean_mtsamples_pdfs() -> tuple[pd.DataFrame, dict]:
    """Extract text from the per-specialty mtsamples PDFs via PyMuPDF."""
    try:
        import pymupdf  # PyMuPDF
    except ImportError:
        log.warning("PyMuPDF not installed - skipping mtsamples PDF extraction")
        return pd.DataFrame(columns=["note_id", "text", "source"]), {"rows_raw": 0, "rows_clean": 0}

    records, bad = [], 0
    for pdf in sorted(MTSAMPLES_DIR.rglob("*.pdf")):
        try:
            with pymupdf.open(pdf) as doc:
                text = "\n".join(page.get_text() for page in doc)
            records.append({"note_id": pdf.stem, "category": pdf.parent.name,
                            "text": text, "source": "mtsamples_pdf"})
        except Exception:
            bad += 1
    if bad:
        log.warning("mtsamples: %d unreadable PDFs skipped", bad)
    df = pd.DataFrame(records, columns=["note_id", "category", "text", "source"])
    return clean_text_documents(df, "text", "mtsamples_pdf")


def run() -> dict:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}

    # --- structured CSVs -------------------------------------------------
    csv_sources = sorted(STRUCTURED_DIR.glob("*.csv")) + ([HEALTHCARE_CSV] if HEALTHCARE_CSV.exists() else [])
    for path in csv_sources:
        name = path.stem.lower()
        df, stats = clean_structured_csv(path)
        out = CLEAN_DIR / f"{name}.parquet"
        df.to_parquet(out, index=False)
        manifest[name] = {**stats, "object": f"{PREFIXES['clean']}/{out.name}",
                          "rows_raw": stats["rows_raw"], "rows_clean": stats["rows_clean"]}
        log.info("%-14s raw=%9d clean=%9d dupes=%7d empty=%6d", name,
                 stats["rows_raw"], stats["rows_clean"],
                 stats["rows_exact_dupes_removed"], stats["rows_empty_dropped"])

    # --- text documents ---------------------------------------------------
    for name, (df, stats) in {
        "unstructured_notes": clean_unstructured_notes(),
        "medical_data_lake_bundle": clean_bundle(),
        "mtsamples_pdf": clean_mtsamples_pdfs(),
    }.items():
        out = CLEAN_DIR / f"{name}.parquet"
        df.to_parquet(out, index=False)
        manifest[name] = {**stats, "object": f"{PREFIXES['clean']}/{out.name}"}

    (CLEAN_DIR / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    run()
