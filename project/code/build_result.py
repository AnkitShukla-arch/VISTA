"""Build the RESULT clean-data folder for Phase 2.

This script finishes the phase-1 pipeline: it takes the raw phase-one dataset,
runs everything through the ETL cleaning logic and — for every PDF — through
the integrated PaddleOCR engine, then writes the final clean corpus to
RESULT/clean_data/ at the project root.

Sources
  1. Structured CSVs   -> vista_pipeline.clean.clean_structured_csv
  2. Text documents    -> vista_pipeline.clean.clean_text_documents
  3. PDFs              -> PaddleOCR (project/code/vista_ocr), page-by-page,
                          then the same text cleaning/dedupe as the corpus
  4. DOCX              -> text extracted via zipfile (word/document.xml)

Outputs (RESULT/clean_data/)
  *.parquet                    one typed, deduplicated dataset per source
  ocr_text/*.txt               full PaddleOCR text per parsed PDF
  _manifest.json               per-source cleaning + OCR stats
  phase1_clean_summary.md      human-readable roll-up
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "project" / "code"))
sys.path.insert(0, str(PROJECT_ROOT / "project" / "code" / "vista_ocr"))

from vista_pipeline import RAW_DIR, WORK_DIR, get_logger  # noqa: E402
from vista_pipeline.clean import (  # noqa: E402
    HEALTHCARE_CSV,
    MTSAMPLES_DIR,
    NOTES_DIR,
    STRUCTURED_DIR,
    BUNDLE_CSV,
    clean_structured_csv,
    clean_text_documents,
    normalise_note_text,
)
from vista_ocr.preprocessing.paddle_engine import (  # noqa: E402
    extract_from_scanned_pdf_paddle,
)

log = get_logger("result")

RESULT_DIR = PROJECT_ROOT / "RESULT"
CLEAN_DATA_DIR = RESULT_DIR / "clean_data"
OCR_TEXT_DIR = CLEAN_DATA_DIR / "ocr_text"

REPORTS_DIR = RAW_DIR / "Reports"
ETL_CLEAN_DIR = WORK_DIR / "clean"          # outputs/pipeline/clean (ETL run output)
ETL_MANIFEST = ETL_CLEAN_DIR / "_manifest.json"


# --------------------------------------------------------------------------
# Extractors
# --------------------------------------------------------------------------

def extract_docx_text(path: Path) -> str:
    """Pull visible paragraph text out of a .docx via its word/document.xml."""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        paras = []
        for p in root.iter(f"{{{ns['w']}}}p"):
            text = "".join(t.text or "" for t in p.iter(f"{{{ns['w']}}}t"))
            if text.strip():
                paras.append(text.strip())
        return "\n".join(paras)
    except Exception as exc:
        log.warning("docx unreadable %s: %s", path.name, exc)
        return ""


def ocr_pdf(path: Path) -> tuple[str, dict]:
    """PaddleOCR a PDF via the cached ocr_text output when available.

    The heavy Paddle pass is done by ocr_reports.py (resumable, cache-first).
    If a PDF's cached text is missing, we run Paddle in-process as fallback.
    """
    cache = OCR_TEXT_DIR / f"{path.stem}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8"), {"ocr_seconds": 0.0, "used_ocr": True}

    t0 = time.perf_counter()
    try:
        text = extract_from_scanned_pdf_paddle(path.read_bytes(), dpi=150)
        used_ocr = True
    except Exception as exc:
        log.warning("Paddle OCR failed for %s: %s", path.name, exc)
        text, used_ocr = "", True
    return text, {"ocr_seconds": round(time.perf_counter() - t0, 1), "used_ocr": used_ocr}

# --------------------------------------------------------------------------
# Source builders
# --------------------------------------------------------------------------

def build_structured_sources(manifest: dict) -> None:
    """Copy the ETL-run clean parquets when present, else recompute from raw."""
    csv_sources = sorted(STRUCTURED_DIR.glob("*.csv")) + ([HEALTHCARE_CSV] if HEALTHCARE_CSV.exists() else [])
    for path in csv_sources:
        name = path.stem.lower()
        cached = ETL_CLEAN_DIR / f"{name}.parquet"
        if cached.exists():
            shutil.copyfile(cached, CLEAN_DATA_DIR / cached.name)
            stats = _etl_stats_for(name)
            manifest[name] = {"kind": "structured", "source": "etl_clean_layer", **stats}
            log.info("%-28s rows=%d (copied from ETL clean layer)", name, stats.get("rows_clean", "?"))
            continue
        df, stats = clean_structured_csv(path)
        df.to_parquet(CLEAN_DATA_DIR / f"{name}.parquet", index=False)
        manifest[name] = {"kind": "structured", "source": "recomputed", **stats}
        log.info("%-28s rows=%d (recomputed)", name, len(df))


def _etl_stats_for(name: str) -> dict:
    """Pull per-source stats out of the ETL clean manifest, when available."""
    try:
        etl = json.loads(ETL_MANIFEST.read_text(encoding="utf-8"))
        info = etl.get(name, {})
        return {k: info[k] for k in ("rows_raw", "rows_clean", "rows_exact_dupes_removed",
                                     "rows_near_dupes_removed", "rows_empty_dropped") if k in info}
    except Exception:
        return {}


def build_text_sources(manifest: dict) -> None:
    """Text sources: prefer the ETL-run clean parquets, else recompute."""
    text_sources = [
        ("unstructured_notes", NOTES_DIR is not None),
        ("medical_data_lake_bundle", BUNDLE_CSV.exists()),
        ("mtsamples_pdf", MTSAMPLES_DIR.exists()),
    ]
    for name, available in text_sources:
        cached = ETL_CLEAN_DIR / f"{name}.parquet"
        if cached.exists():
            shutil.copyfile(cached, CLEAN_DATA_DIR / cached.name)
            stats = _etl_stats_for(name)
            manifest[name] = {"kind": "text", "source": "etl_clean_layer", **stats}
            log.info("%-28s rows=%d (copied from ETL clean layer)", name, stats.get("rows_clean", "?"))
        elif available:
            _recompute_text_source(name, manifest)
        else:
            log.warning("source %s unavailable and no ETL clean parquet cached", name)


def _recompute_text_source(name: str, manifest: dict) -> None:
    """Recompute one text source from raw data (ETL clean layer missing)."""
    if name == "unstructured_notes":
        records = []
        for p in sorted(NOTES_DIR.glob("*.txt")):
            try:
                records.append({"note_id": p.stem, "text": p.read_text(encoding="utf-8", errors="replace")})
            except OSError as exc:
                log.warning("unreadable note %s: %s", p.name, exc)
        df = pd.DataFrame(records, columns=["note_id", "text"])
        df["source"] = "unstructured_notes"
    elif name == "medical_data_lake_bundle":
        df = pd.read_csv(BUNDLE_CSV)
        df["source"] = "medical_data_lake_bundle"
    else:  # mtsamples_pdf
        import pymupdf
        recs = []
        for pdf in sorted(MTSAMPLES_DIR.rglob("*.pdf")):
            try:
                with pymupdf.open(pdf) as doc:
                    text = "\n".join(page.get_text() for page in doc)
                recs.append({"note_id": pdf.stem, "category": pdf.parent.name,
                             "text": text, "source": "mtsamples_pdf"})
            except Exception:
                pass
        df = pd.DataFrame(recs, columns=["note_id", "category", "text", "source"])

    df, stats = clean_text_documents(df, "text", name)
    df.to_parquet(CLEAN_DATA_DIR / f"{name}.parquet", index=False)
    manifest[name] = {"kind": "text", "source": "recomputed", **stats}


def build_ocr_sources(manifest: dict) -> None:
    """Paddle-parsed report PDFs + DOCX reports -> reports_ocr source."""
    OCR_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    records = []

    pdfs = sorted(REPORTS_DIR.glob("*.pdf"))
    log.info("PaddleOCR text for %d report PDFs ...", len(pdfs))
    for pdf in pdfs:
        text, ocr_stats = ocr_pdf(pdf)
        (OCR_TEXT_DIR / f"{pdf.stem}.txt").write_text(text, encoding="utf-8")
        records.append({"doc_id": pdf.stem, "category": "report", "text": text,
                        "source": "reports_pdf_paddleocr", **ocr_stats})
        log.info("  %-42s chars=%6d (ocr=%s)",
                 pdf.name, len(text), ocr_stats["used_ocr"])

    docxs = sorted(REPORTS_DIR.glob("*.docx"))
    log.info("Extracting %d DOCX reports ...", len(docxs))
    for doc in docxs:
        text = normalise_note_text(extract_docx_text(doc))
        # '__docx' suffix avoids clobbering the Paddle OCR .txt when a DOCX
        # shares its stem with a parsed PDF (e.g. Priya_Mehta_...pdf/.docx);
        # spaces are replaced so filenames stay shell/URL friendly.
        doc_id = f"{doc.stem.replace(' ', '_')}__docx"
        (OCR_TEXT_DIR / f"{doc_id}.txt").write_text(text, encoding="utf-8")
        records.append({"doc_id": doc_id, "category": "report", "text": text,
                        "source": "reports_docx", "ocr_seconds": 0.0, "used_ocr": False})

    df = pd.DataFrame(records, columns=["doc_id", "category", "text", "source",
                                        "ocr_seconds", "used_ocr"])
    df, stats = clean_text_documents(df, "text", "reports_ocr")
    df.to_parquet(CLEAN_DATA_DIR / "reports_ocr.parquet", index=False)
    manifest["reports_ocr"] = {"kind": "text_ocr", **stats}


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

def write_summary(manifest: dict) -> None:
    lines = ["# VISTA RESULT — Clean Data (Phase 2 input)", ""]
    total_raw = total_clean = 0
    for info in manifest.values():
        total_raw += info.get("rows_raw", 0)
        total_clean += info.get("rows_clean", 0)
    lines += [
        f"**Sources:** {len(manifest)}  |  **Rows raw:** {total_raw:,}  |  "
        f"**Rows clean:** {total_clean:,}  |  **Removed:** {total_raw - total_clean:,}",
        "",
        "| source | kind | raw | clean | removed |",
        "|---|---|---:|---:|---:|",
    ]
    for name, info in manifest.items():
        removed = info.get("rows_raw", 0) - info.get("rows_clean", 0)
        lines.append(f"| {name} | {info.get('kind', '?')} | "
                     f"{info.get('rows_raw', 0):,} | {info.get('rows_clean', 0):,} | {removed:,} |")
    lines += [
        "",
        "OCR text for each parsed report lives in `ocr_text/`; the matching "
        "deduplicated records are in `reports_ocr.parquet`.",
    ]
    (CLEAN_DATA_DIR / "phase1_clean_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    import pandas as pd  # local import: needed by build_text_sources

    globals()["pd"] = pd

    CLEAN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {}

    t0 = time.perf_counter()
    log.info("=== structured CSV sources ===")
    build_structured_sources(manifest)

    log.info("=== text document sources ===")
    build_text_sources(manifest)

    log.info("=== PaddleOCR sources (Reports) ===")
    build_ocr_sources(manifest)

    (CLEAN_DATA_DIR / "_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    write_summary(manifest)

    log.info("RESULT/clean_data ready in %.1fs -> %s", time.perf_counter() - t0, CLEAN_DATA_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
