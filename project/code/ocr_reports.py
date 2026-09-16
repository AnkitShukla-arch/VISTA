"""Standalone PaddleOCR runner for the phase-1 report PDFs.

Processes every PDF under data/processed/phase1_dataset/Reports with PaddleOCR
(rendered pages -> PP-OCRv5), writing one .txt per PDF into
RESULT/clean_data/ocr_text/ plus a progress marker per finished file.

Cache-first: PDFs whose .txt already exists are skipped, so the script can be
re-run / resumed at any time. Designed to run detached:

    python ocr_reports.py > ../../outputs/ocr_reports.log 2>&1 &

Run as a module from project/code so package imports resolve:
    cd project/code && python -m ocr_reports
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "project" / "code"))
sys.path.insert(0, str(PROJECT_ROOT / "project" / "code" / "vista_ocr"))

from vista_pipeline import RAW_DIR, get_logger  # noqa: E402
from vista_ocr.preprocessing.paddle_engine import (  # noqa: E402
    extract_from_scanned_pdf_paddle,
)

log = get_logger("ocr_reports")

REPORTS_DIR = RAW_DIR / "Reports"
OCR_TEXT_DIR = PROJECT_ROOT / "RESULT" / "clean_data" / "ocr_text"
MARKERS_DIR = OCR_TEXT_DIR / ".progress"


def main() -> int:
    OCR_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    MARKERS_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(REPORTS_DIR.glob("*.pdf"))
    log.info("PaddleOCR: %d report PDFs queued", len(pdfs))

    for i, pdf in enumerate(pdfs, 1):
        out_txt = OCR_TEXT_DIR / f"{pdf.stem}.txt"
        if out_txt.exists() and (MARKERS_DIR / f"{pdf.stem}.done").exists():
            log.info("[%d/%d] cached, skipping %s", i, len(pdfs), pdf.name)
            continue

        t0 = time.perf_counter()
        try:
            # Force the OCR path (user requirement: parse the PDFs with Paddle),
            # not the embedded-text shortcut.
            text = extract_from_scanned_pdf_paddle(pdf.read_bytes(), dpi=150)
        except Exception as exc:
            log.exception("FAILED %s", pdf.name)
            text = ""

        out_txt.write_text(text, encoding="utf-8")
        (MARKERS_DIR / f"{pdf.stem}.done").write_text("ok", encoding="utf-8")
        secs = time.perf_counter() - t0
        log.info("[%d/%d] %s -> %d chars in %.1fs", i, len(pdfs), pdf.name, len(text), secs)

        # Live progress file for the orchestrator to poll.
        (OCR_TEXT_DIR / ".progress.json").write_text(
            json.dumps({"done": i, "total": len(pdfs), "last": pdf.stem,
                        "last_seconds": round(secs, 1)}, indent=2),
            encoding="utf-8",
        )

    log.info("All report PDFs processed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
