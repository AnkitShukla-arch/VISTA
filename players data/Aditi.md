# Aditi — OCR and report text extraction

## Contribution

Aditi owns OCR for reports whose contents are stored as page images rather than searchable text. The OCR flow renders PDF pages to images, runs PaddleOCR, joins recognized text into a report string, and saves extracted text for later fingerprinting and search.

## Workflow

1. Find report PDFs in the selected Phase 1 data.
2. Render each page at a selected DPI using PyMuPDF.
3. Convert pages to RGB images and run them through a cached PaddleOCR predictor.
4. Flatten recognized lines into text and separate pages.
5. Save a `.txt` file per PDF plus completion markers and progress data so interrupted batch runs can resume.

The reusable PDF helper can use an embedded text layer when available and fall back to OCR for scanned PDFs. The standalone batch script deliberately forces the OCR path for its selected report-PDF batch.

## Technologies

PaddleOCR (PP-OCRv5/PaddleOCR 3.x result format), PyMuPDF, Pillow, NumPy, and Python file/progress handling.

## Source code

- `project/code/vista_ocr/preprocessing/paddle_engine.py` — PaddleOCR initialization, image recognition, PDF rendering, and text extraction.
- `project/code/ocr_reports.py` — resumable report-PDF batch runner and progress tracking.
- `Backend/OCR/extractor.py` — basic digital-PDF and DOCX extraction adapter.
- `project/code/build_result.py` — assembles structured, text, and OCR outputs into the Phase 2 clean corpus.

## Representative code excerpts

The OCR engine renders PDF pages and sends each image to PaddleOCR, then separates the extracted page text:

```python
def extract_from_scanned_pdf_paddle(pdf_bytes: bytes, dpi: int = 200) -> str:
    import pymupdf
    from PIL import Image

    pages_text = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            mode = "RGBA" if pix.alpha else "RGB"
            image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
            text = extract_text_from_image_paddle(image)
            pages_text.append(text)
    return "\n--- PAGE BREAK ---\n".join(p.strip() for p in pages_text).strip()
```

The batch runner skips a PDF only when its text output and completion marker both exist:

```python
if out_txt.exists() and (MARKERS_DIR / f"{pdf.stem}.done").exists():
    log.info("[%d/%d] cached, skipping %s", i, len(pdfs), pdf.name)
    continue

text = extract_from_scanned_pdf_paddle(pdf.read_bytes(), dpi=150)
out_txt.write_text(text, encoding="utf-8")
(MARKERS_DIR / f"{pdf.stem}.done").write_text("ok", encoding="utf-8")
```

## Output and handoff

## Detailed implementation walkthrough

### OCR engine lifecycle

- The OCR predictor is initialized lazily the first time text recognition is requested.
- A module-level cache reuses the predictor for subsequent pages and documents.
- Lazy initialization avoids paying model-load cost when OCR is not needed.
- The first invocation may download model files and take longer than later calls.
- The configured OCR language is English.
- Document orientation classification is disabled by default for this upright report collection.
- Document unwarping is disabled by default to avoid extra work on already-readable pages.
- Text-line orientation can be enabled through `PADDLE_TEXTLINE_ORIENT`.
- MKL-DNN can be enabled through `PADDLE_ENABLE_MKLDNN`.
- The code defaults both options off because the project encountered Windows/Paddle compatibility and latency concerns.
- The predictor accepts RGB image arrays.
- The image helper accepts a Pillow image, image bytes, or a file path.
- Non-image inputs are rejected with an explicit type error.
- Each image is converted to RGB before recognition.
- NumPy converts the Pillow image into the array expected by PaddleOCR.

### PaddleOCR result conversion

- PaddleOCR 3.x results can be dict-like or result-object-like.
- The result conversion helper reads recognized text from `rec_texts`.
- Empty OCR strings are filtered out.
- Recognized line strings are joined in their returned order.
- The final text is trimmed before returning to the caller.
- Page geometry and confidence are not included in the flattened `.txt` output.
- The raw recognized words are retained as text for later clinical parsing.
- The text conversion layer is intentionally separate from patient fingerprint extraction.
- A OCR result is not itself a diagnosis; it is machine-readable transcription.

### PDF page rendering

- `extract_from_scanned_pdf_paddle()` opens PDF bytes through PyMuPDF.
- It iterates through every page in the PDF.
- `get_pixmap(dpi=...)` renders a page to raster pixels.
- Rendered pixels are labeled RGB or RGBA depending on the alpha channel.
- Pillow reconstructs an image from pixel bytes and page dimensions.
- Each page image is sent to the shared image OCR helper.
- Per-page recognized text is accumulated in a list.
- A page-break marker separates page text in the returned report.
- The default library helper uses 200 DPI.
- The standalone Phase 1 report runner sets its OCR pass to 150 DPI.
- DPI is a speed/legibility trade-off: higher resolution can help small print but costs time and memory.
- Every page is processed, so a long PDF takes proportionally more work.
- The current helper processes pages sequentially within a document.

### Text-native versus scanned PDF handling

- `extract_from_pdf_paddle()` first asks PyMuPDF for embedded text.
- If the embedded layer is nonempty, it returns that text directly.
- If no embedded text is available, it falls back to rendered-page PaddleOCR.
- This avoids OCR compute for digital PDFs in the reusable helper.
- The separate `ocr_reports.py` batch intentionally calls the scanned-PDF OCR function directly.
- That batch behavior forces the OCR route even if the PDF has an embedded text layer.
- This distinction matters when explaining why the same PDF may be processed differently by different entry points.
- `Backend/OCR/extractor.py` separately supports DOCX paragraphs and digital PDF extraction through `pypdf`.
- The file extractor and Paddle OCR engine are compatible pieces but are not the same function.

### Resumable report batch

- The batch script discovers `.pdf` files in the report directory and sorts them.
- OCR output is placed under `RESULT/clean_data/ocr_text/`.
- Completion markers are stored in an adjacent `.progress` directory.
- A PDF is considered cached only when both its `.txt` and `.done` marker exist.
- If either is missing, the script reprocesses the PDF.
- The runner catches an exception for one PDF and logs the failure with a traceback.
- On failure, it writes an empty output string and a completion marker in the current implementation.
- The per-file progress JSON includes count completed, total count, last file stem, and elapsed seconds.
- A status log reports extracted character count and time per file.
- Existing completed files can be skipped on a later run.
- This makes an interrupted corpus run resumable without repeating all successful files.
- The marker convention records that processing was attempted; inspect logs when OCR failure matters.
- The output naming convention uses the PDF stem, connecting OCR text to its source filename.

### Integration sequence

- Aashita’s raw ETL stage preserves source files and cleans supported datasets.
- Aditi’s OCR stage handles image-based pages that need visual text recognition.
- `build_result.py` assembles OCR text with the structured and text-cleaned sources.
- The resulting report text is passed to clinical section parsing and fingerprint creation.
- Embedding code receives the diagnostic summary, not PaddleOCR’s raw model objects.
- Document search uses indexed metadata/text generated downstream.
- The UI preview displays extracted text associated with the report record.
- Report names and page markers help operators trace content back to source PDFs.
- OCR does not itself decide semantic boxes or retrieve reports.
- Search relevance is evaluated by later embedding, similarity, clustering, and retrieval components.

## Inputs and outputs

| Item | Description |
|---|---|
| PDF input | Source bytes for a multi-page clinical report |
| Page renderer | PyMuPDF raster output at the selected DPI |
| Image input to Paddle | RGB NumPy image derived from Pillow |
| OCR model | Cached PaddleOCR English predictor |
| Page output | Recognized text lines in their returned sequence |
| Joined report | UTF-8 string with page separators |
| Batch output | One `.txt` per report PDF |
| Resume state | Per-file `.done` markers and `.progress.json` |
| Downstream consumer | Clinical parser, fingerprint builder, embedding pipeline |

## Reliability and quality considerations

- First-run model download and initialization should be distinguished from steady-state OCR speed.
- PDF size alone does not predict processing time; page count and rendered resolution matter.
- OCR output can contain recognition errors, missing characters, or misplaced table columns.
- The flattened output does not preserve bounding boxes or confidence values.
- A completion marker does not guarantee that extracted text is nonempty.
- Logs should be reviewed for failed PDFs and character counts.
- The Phase 2 importer should retain source filename metadata for traceability.
- A scanned PDF needs OCR; a digital PDF may be read faster from its embedded text layer.
- The selected DPI should be documented when comparing OCR quality or throughput.
- OCR text should be reviewed before being presented as a verified clinical value.
- OCR transcription is not clinical interpretation or medical advice.
- If another language is introduced, the Paddle model language setting must be revisited.
- If pages can be rotated, orientation handling may need to be enabled.
- Very large PDFs may need page-level batching or resource limits in future deployment.
- The cache key currently follows filename stem; filenames should be unique within the report folder.

## Suggested local run and review procedure

- Start from the VISTA repository root and confirm the selected report directory exists.
- Confirm PaddleOCR, PyMuPDF, Pillow, and NumPy are installed in the active environment.
- Run `python -m ocr_reports` from `project/code` so module imports resolve.
- Check the log for the number of PDFs queued.
- Check per-file logs for success, extracted character count, and elapsed seconds.
- Inspect the `.progress.json` file while a batch is running.
- Open a generated `.txt` and compare its content with the source PDF.
- Confirm multi-page reports retain page separators.
- Re-run the batch and confirm completed files are reported as cached.
- If a file has an empty output, inspect the failure log before treating it as a valid extraction.

## Contribution summary for a project report

Aditi implemented VISTA’s report OCR path using PaddleOCR and PDF page rendering. The system lazily initializes and reuses the OCR model, processes each page as an image, converts recognized lines into plain text, and writes per-report text files. The batch runner tracks progress and supports resuming completed work. These extracted text files make scanned clinical reports available to the downstream fingerprinting, embedding, and semantic retrieval stages.

## Suggested demonstration points

- Show a scanned PDF page and the corresponding OCR text file.
- Explain page rendering before PaddleOCR inference.
- Show the lazy cached predictor and why it avoids repeated model initialization.
- Compare the 200-DPI reusable helper with the 150-DPI batch setting.
- Show page separators in a multi-page OCR output.
- Demonstrate a cached report being skipped on a later batch run.
- Show the progress JSON and per-file timing log.
- Explain how OCR output is joined to the report by its source filename.
- Explain the difference between embedded-PDF text extraction and scanned-page OCR.
- Point out why OCR output still needs clinical parsing and review.

## Questions the contribution should answer

- Which component renders PDF pages into images?
- Which library performs text recognition?
- How does the engine avoid reinitializing the model for every page?
- Where are extracted text files saved?
- How does the batch process resume after interruption?
- What is the difference between the reusable PDF helper and the forced-OCR batch runner?
- What information is lost when OCR output is flattened to plain text?
- What should be checked when a completion marker exists but output is empty?
- Which team member owns OCR, and which members own fingerprinting and search?

The runner writes UTF-8 text files under `RESULT/clean_data/ocr_text/`, with progress markers alongside them. The extracted text becomes input to clinical parsing, fingerprinting, embeddings, and report search.
