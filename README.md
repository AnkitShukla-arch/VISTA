# VISTA

VISTA is a healthcare NLP and medical reporting project.

## Project layout

- `project/code/vista_pipeline/` - layered ETL pipeline (ASTRA-style, MinIO-backed)
- `project/code/vista_ocr/` - OCR module (integrated from VISTA repo, PaddleOCR engine)
- `project/code/run_phase1.py` - phase-1 ETL orchestrator (ingest -> clean -> summarize -> upload)
- `project/code/ocr_reports.py` - resumable PaddleOCR runner for report PDFs
- `project/code/build_result.py` - assembles `RESULT/clean_data/` (phase-2 input)
- `project/notebooks/` - exploratory analysis and model notebooks
- `data/raw/dataset/` - original source datasets
- `data/processed/phase1_dataset/` - the phase-one selection used by the pipeline
- `outputs/pipeline/` - ETL working dir (clean parquets, summaries, run report)
- `RESULT/clean_data/` - **final clean corpus for phase 2** (parquet + OCR text + manifest)
- `docs/`, `assets/` - documentation and graphics

## Storage (MinIO)

```text
bash manage_vista.sh up          # start MinIO + create vista-lake bucket
```

Layered layout in `s3://vista-lake/`:
- `raw/` - original phase-one files, uploaded unchanged (18,826 objects)
- `clean/` - the full RESULT corpus: 10 clean parquets, `ocr_text/*.txt`, `_manifest.json`
- `summaries/` - per-source profiles + `phase1_summary.md` + `phase1_clean_summary.md`
- `reports/` - pipeline run reports

Phase 2 can read everything straight from `s3://vista-lake/clean/` - no local
RESULT folder required.

## Phase-one run

```text
# 1. ETL: raw -> clean -> summaries -> MinIO
.venv/Scripts/python project/code/run_phase1.py

# 2. PaddleOCR over the report PDFs (resumable; cached in RESULT/clean_data/ocr_text/)
cd project/code && ../.venv/Scripts/python -m ocr_reports

# 3. Assemble the RESULT folder for phase 2
.venv/Scripts/python project/code/build_result.py

# 4. Sync the finished RESULT corpus back into the MinIO clean layer
.venv/Scripts/python project/code/sync_result_to_minio.py
```

## RESULT folder (phase-2 input)

`RESULT/clean_data/` contains every cleaned source produced by the pipeline:

- `*.parquet` - one typed, deduplicated dataset per source
- `ocr_text/*.txt` - full PaddleOCR text per parsed report PDF/DOCX
- `_manifest.json` - per-source cleaning + OCR statistics
- `phase1_clean_summary.md` - human-readable roll-up

## OCR engine

`project/code/vista_ocr` uses **PaddleOCR (PP-OCRv5/v6 models)** for images and
scanned PDFs; digital PDFs use the embedded text layer via PyMuPDF. Tesseract,
FastAPI/Kafka plumbing and other service code from the original module were
removed — only the OCR core (readers, Paddle engine, cleaning, schemas) is kept.
