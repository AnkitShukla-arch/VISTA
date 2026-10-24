# Aashita — ETL pipeline

## Contribution

Aashita owns Phase 1 data preparation. The ETL stage preserves source files in a raw layer, normalizes structured and unstructured data, drops empty and duplicate records, writes clean Parquet datasets, and produces source-level quality summaries. The cleaned layer is the handoff for OCR and later clinical processing.

## Workflow

1. Scan `data/processed/phase1_dataset` for CSV, TXT, PDF, DOCX, JSON, and Markdown files.
2. Upload originals to MinIO while preserving their relative paths. Compare size and content hash to skip unchanged files on repeat runs.
3. Clean structured CSVs: normalize headers and text, standardize identifier columns, parse date fields, coerce consistently numeric columns, and remove empty and exact duplicate rows.
4. Clean text sources: normalize Unicode and whitespace, remove control characters, drop empty and exact duplicate text, and reduce near duplicates with a prefix and length-bucket fingerprint.
5. Save clean datasets as Parquet and record per-source cleaning statistics in a manifest.
6. Summarize sources, upload clean and summary artifacts to MinIO, and write a run report.

## Technologies

Python, pandas, Parquet, MinIO (S3-compatible storage), `hashlib`, regular expressions, and PyMuPDF for digital text extraction in the MTSamples PDF collection.

## Source code

- `project/code/vista_pipeline/ingest_raw.py` — file discovery, chunked MD5 hashing, idempotent raw upload.
- `project/code/vista_pipeline/clean.py` — structured CSV and text cleaning/deduplication.
- `project/code/vista_pipeline/summarize.py` — source profiling and Markdown report generation.
- `project/code/vista_pipeline/upload_processed.py` — uploads Parquet, manifest, and summaries.
- `project/code/run_phase1.py` — runs ETL steps and records run status.
- `Backend/ETL/cleaner.py` — reusable clinical text normalization and content-hash deduplication helper.

## Representative code excerpts

Raw-file identity is calculated in chunks, avoiding reading an entire large file into memory at once:

```python
def file_md5(path, chunk_size=1 << 20) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()
```

Structured inputs are read as strings first to avoid changing IDs or mixed-format values before normalization. The cleaner then removes blank and exact-duplicate rows:

```python
raw = pd.read_csv(path, dtype=str, keep_default_na=False,
                  na_values=["", "NA", "N/A", "null", "NULL"])
df = _normalise_headers(raw)
for col in df.columns:
    if _is_string_dtype(df[col]):
        df[col] = df[col].map(_normalise_text_value)

df = _normalise_ids(df)
df = _parse_dates(df)
df = _coerce_numeric(df)
df = df.dropna(how="all").drop_duplicates()
```

Text near-deduplication uses the first 400 characters and a 50-character length bucket, keeping the longest version:

```python
df[text_col] = df[text_col].map(normalise_note_text)
df = df[df[text_col].str.len() > 0]
df = df.drop_duplicates(subset=[text_col])
df["_len_bucket"] = (df[text_col].str.len() // 50) * 50
df["_fingerprint"] = df[text_col].str[:400]
df = (df.sort_values(text_col, key=lambda s: s.str.len(), ascending=False)
        .drop_duplicates(subset=["_fingerprint", "_len_bucket"])
        .drop(columns=["_fingerprint", "_len_bucket"]))
```

The Phase 1 orchestrator invokes the stages in order:

```python
STEPS = [
    ("ingest_raw", step_ingest),
    ("clean", step_clean),
    ("summarize", step_summarize),
    ("upload_processed", step_upload),
]
```

## Handoff and boundaries

## Detailed task breakdown

### Source discovery

- Start from the configured Phase 1 root directory.
- Walk its subdirectories recursively.
- Ignore directory entries and unsupported file extensions.
- Sort candidate paths so the same tree is visited in a stable order.
- Treat file names and relative paths as provenance metadata.
- Convert relative paths to POSIX form before creating object keys.
- Keep the original relative folder hierarchy after the `raw/` prefix.
- Count files and bytes even when a dry run disables upload.
- Report the number of objects already present with matching content.
- Do not transform bytes in the raw-copy stage.

### Raw object storage

- Open each source file in binary mode.
- Calculate MD5 in one-megabyte chunks.
- Ask MinIO whether the corresponding object already exists.
- Compare object size with the local file size.
- Compare the object ETag with the local content hash.
- Skip upload only when both checks agree.
- Treat a missing object as a first-time upload.
- Treat a failed object inspection as a reason to attempt upload.
- Stream the file handle to MinIO instead of duplicating its full content in memory.
- Use a CSV content type for CSV files.
- Use a generic binary content type for other raw inputs.
- Log progress periodically while scanning large source directories.
- Return raw-stage counts to the orchestrator.
- Preserve source files as the audit and recovery copy.

### Structured CSV processing

- Read every cell as text at the start of cleaning.
- Map blank strings and known null spellings into missing values.
- Trim header whitespace and collapse repeated spaces in headers.
- Normalize Unicode in text values using NFKC.
- Remove control characters that can break downstream parsers.
- Collapse whitespace inside text cells.
- Convert empty normalized text values to null.
- Uppercase known identifier fields such as patient and admission IDs.
- Avoid converting ID-like values into numeric types.
- Parse columns with names ending in `date` using tolerant date parsing.
- Convert numeric-looking text only when over 95 percent of non-null entries parse.
- Preserve mixed columns as text rather than forcing lossy conversion.
- Count source rows before applying removals.
- Drop rows whose every field is null.
- Drop exact duplicate rows after normalization.
- Record the number of empty rows removed.
- Record the number of duplicates removed.
- Record the final row count.
- Write each cleaned table as a source-named Parquet file.
- Keep source-level statistics alongside the Parquet object location.

### Unstructured text processing

- Load notes using stable file stems as note identifiers.
- Load bundled text records with their category and source metadata.
- Extract digital text from MTSamples PDFs where PyMuPDF is available.
- Process PDFs in sorted order to keep runs deterministic.
- Catch unreadable PDF failures and increment a failure counter.
- Normalize all text with a shared routine before deduplication.
- Remove control characters from extracted text.
- Collapse tabs, spaces, and line breaks into a normalized whitespace form.
- Remove records that are empty after normalization.
- Remove exact duplicates using the complete normalized text.
- Compute a 400-character text prefix for near-duplicate grouping.
- Bucket record lengths in intervals of 50 characters.
- Sort each candidate group by descending text length.
- Keep the longest record in each prefix-and-length group.
- Drop internal fingerprint columns before saving.
- Include empty, exact-duplicate, and near-duplicate counts in source statistics.
- Log per-source raw and final counts for review.
- Preserve category and source columns when they exist.

### Data profiling

- Read the clean manifest to discover the sources and row counts.
- Open each Parquet source for profiling.
- Distinguish structured tables from text sources by available columns.
- Report table row count and column count.
- Report each column’s physical type.
- Report null counts for all columns.
- Report distinct counts for all columns.
- Include min, max, and mean for numeric columns.
- Include frequent values for categorical or text columns.
- Report text document counts.
- Calculate average and median document lengths.
- Estimate token count through whitespace tokenization.
- Estimate vocabulary on a deterministic sample for very large collections.
- Keep source-specific JSON profiles for machine inspection.
- Generate one Markdown roll-up for a person to inspect quickly.
- Report total raw rows, cleaned rows, and removed rows in the roll-up.

### Upload and run tracking

- Upload each clean Parquet file to the clean prefix.
- Upload the clean manifest as JSON.
- Upload each source profile as JSON.
- Upload the combined Phase 1 summary as UTF-8 text.
- Track uploaded clean keys and summary keys in the stage return value.
- Run steps sequentially so a failed prerequisite stops dependent stages.
- Capture timing for each stage.
- Save completed step names and failed step name in a run report.
- Persist the run report locally for debugging.
- Attempt a MinIO copy of the run report after successful/non-dry execution.
- Return a nonzero process status after a stage failure.
- Allow an operator to run only one stage during investigation.
- Allow previously uploaded raw data to be reused with `--skip-raw`.
- Allow file discovery to be checked with `--dry-run`.

## Decisions and rationale

- Raw storage is immutable evidence; cleaning should create another layer rather than overwrite it.
- Parquet is used for clean tabular data because it retains data types and supports efficient column reads.
- Conservative numeric conversion protects patient identifiers and mixed clinical fields.
- Unicode normalization makes visually equivalent text more consistent for matching.
- Exact duplicate removal reduces storage and repeated downstream compute.
- Near-duplicate removal addresses report variants that differ in trailing content or formatting.
- Keeping the longest candidate tends to retain more context than keeping the shortest.
- Manifests turn cleaning into an auditable transformation rather than an opaque script.
- Deterministic file ordering makes logs and run outputs easier to compare.
- Chunked hashing limits memory overhead for large files.
- Size plus ETag checks make raw uploads cheaper to repeat.
- A failed stage should be visible; later outputs should not imply it succeeded.

## Acceptance checklist

- Raw source object exists at its expected relative key.
- Re-running ingestion does not re-upload an unchanged object.
- The clean output can be opened as Parquet.
- Identifier columns retain their leading characters and case convention.
- Empty rows and duplicate rows are reflected in manifest counts.
- Text output has no empty records after normalization.
- Text source statistics show exact and near-duplicate counts separately.
- The summary names each source that produced a clean artifact.
- The run report lists completed stages in the actual run order.
- Failure details are available in logs and the local run report.
- No OCR accuracy claim is derived from the ETL row-count report.
- Downstream consumers can identify source and category metadata.

## Example explanation for a presentation

“Aashita’s ETL pipeline creates VISTA’s clean-data foundation. It first preserves uploaded sources in MinIO, then handles structured and unstructured inputs with separate cleaning rules. It protects IDs, standardizes dates and text, removes empty and duplicate records, and writes Parquet outputs. Each source gets a manifest and summary so the team can see how much data changed before it reaches OCR and clinical search.”

## Terms used in this contribution

- **ETL:** Extract, transform, and load.
- **Raw layer:** Original source files stored without transformation.
- **Clean layer:** Normalized and deduplicated data prepared for downstream use.
- **Summary layer:** Per-source profile and run overview.
- **Idempotent:** Repeating the same operation does not create redundant copies.
- **Content hash:** A digest used to identify identical file content.
- **Exact duplicate:** A row or text value identical after normalization.
- **Near duplicate:** Similar text grouped by a prefix and approximate length.
- **Parquet:** A typed, column-oriented data format.
- **Manifest:** Machine-readable record of source processing and statistics.
- **NFKC:** Unicode normalization that standardizes compatibility forms.
- **Data provenance:** Information about where a record came from.
- **MinIO:** S3-compatible object storage used by the project.
- **Downstream stage:** A later pipeline component consuming clean output.
- **Dry run:** Discovery/statistics execution without uploading raw objects.

Outputs include cleaned Parquet files, a per-source manifest, profile summaries, and a run report. The source originals remain in the raw storage layer. PaddleOCR on scanned reports is Aditi’s area; DuckDB priority analysis is Anant’s area. The standalone OCR runner is separate from Aashita’s Phase 1 ETL orchestrator.
