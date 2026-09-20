# VISTA — Phase 1: Data Lake + Cleaning Pipeline

Phase 1 integrates the ASTRA-style pipeline into VISTA and stands up the
storage layer: **MinIO object storage via Docker**, plus an ETL pipeline that
**cleans, deduplicates, and summarizes** the medical data lake.

Architecture reference: `assets/architecture.png`
(Early ETL box "Clean, Deduplicate, Remove Errors" → Raw File Storage (MinIO)).

## What was built

| Layer (MinIO `vista-lake` bucket) | Contents |
|---|---|
| `raw/` | The phase-one dataset, mirrored unchanged (18,826 files, ~1 GB) |
| `clean/` | Deduplicated, typed parquet datasets + `_manifest.json` cleaning stats |
| `summaries/` | Per-source profile JSON + `phase1_summary.md` roll-up |
| `reports/` | `phase1_run_report.json` for each pipeline run |

## Quick start

```bash
# 1. Start MinIO (API :9000, console :9001)
bash manage_vista.sh up

# 2. Run the full pipeline
.venv/Scripts/python project/code/run_phase1.py

# Useful variants
.venv/Scripts/python project/code/run_phase1.py --skip-raw   # reuse raw layer
.venv/Scripts/python project/code/run_phase1.py --only clean # re-run one step
```

Console: http://localhost:9001 (credentials in `.env`).

## Sources processed

| Source | Kind | Notes |
|---|---|---|
| `Full_Medical_Data_Lake/*.csv` | structured | admissions, billing, clinical_notes, departments, diseases, doctors, lab_reports, patients, prescriptions (~33M rows) |
| `healthcare_dataset.csv` | structured | small demo table |
| `Full_Medical_Data_Lake/unstructured_notes/` | text | 18,100 clinical note `.txt` files |
| `medical_data_lake_bundle/combined_dataset.csv` | text | 52,351 docs (50,000 PMC-Patients + 2,351 MTSamples) |
| `mtsamples.csv/output/**/*.pdf` | text (PDF) | per-specialty transcription PDFs, extracted via PyMuPDF |
| `Reports/` | raw only | binary PDF/DOCX clinical reports (cleaning happens in phase 2 OCR/text extraction) |

## Cleaning rules (clean layer)

- Unicode NFKC normalisation, control-char removal, whitespace collapse
- Header normalisation, ID uppercase (e.g. `adm1` → `ADM1`)
- Date parsing, conservative numeric coercion
- Empty-row drop, **exact duplicate drop**, and **near-duplicate drop** for text
  (same first 400 chars + similar length → keep longest)
- Output format: **parquet** (typed, compressed, phase-2 friendly)

## Summaries (summaries layer)

- Structured: rows/columns, nulls, distincts, numeric min/mean/max, top categories
- Text: doc count, avg/median length, token count, vocabulary size (sampled), top categories
- `phase1_summary.md` — one-page human-readable roll-up of the whole lake

## Layout

```
project/code/
├── run_phase1.py                 # orchestrator CLI (ETL steps)
├── ocr_reports.py                # resumable PaddleOCR runner for report PDFs
├── build_result.py               # assembles RESULT/clean_data (phase-2 input)
├── vista_pipeline/               # layered ETL (ASTRA-style)
│   ├── __init__.py               # config + MinIO helpers (versioned bucket)
│   ├── ingest_raw.py             # step 1: raw upload (streaming, idempotent via etag+md5)
│   ├── clean.py                  # step 2: clean + dedupe -> parquet
│   ├── summarize.py              # step 3: profile summaries
│   └── upload_processed.py       # step 4: clean + summaries -> MinIO
└── vista_ocr/                    # OCR module (PaddleOCR engine)
    ├── preprocessing/            # readers + paddle_engine.py
    ├── cleaning/                 # normalize/standardize/dedupe/masking
    ├── models/                   # pydantic schemas
    └── storage/                  # MinIO helpers (boto3)
```

## Why versioning on the bucket

The bucket has versioning enabled, so re-runs never silently overwrite raw
evidence — a previous raw file version stays retrievable from the console.

## Phase 2 preview

The pipeline now finishes with **RESULT/clean_data/** — the single folder to
hand to phase 2:

```bash
# after the ETL run:
cd project/code && ../.venv/Scripts/python -m ocr_reports   # Paddle OCR on Reports/*.pdf
../.venv/Scripts/python build_result.py                    # assemble RESULT/clean_data/
../.venv/Scripts/python sync_result_to_minio.py            # push RESULT corpus -> clean/ layer
```

It contains every clean parquet (ETL layer), the PaddleOCR text of the report
PDFs (`ocr_text/`), and `reports_ocr.parquet` — the parsed report records.
`sync_result_to_minio.py` mirrors the whole corpus back into
`s3://vista-lake/clean/`, so MinIO holds the complete phase-1 result.
Phase 2 (vector conversion) can embed `unstructured_notes`,
`medical_data_lake_bundle`, `mtsamples_pdf`, and `reports_ocr` with Sentence
Transformers, store vectors in pgvector/FAISS, and build the box-clustering on
top — without re-cleaning anything.
