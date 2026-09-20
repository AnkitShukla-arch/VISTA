"""PaddleOCR engine for VISTA.

Extracts text from images and PDFs using PaddleOCR (PP-OCRv5). PDF pages are
rendered to high-resolution images first (pypdfium2 ships with paddleocr), so
both digital and scanned PDFs go through the same OCR path. If a PDF carries
an embedded text layer, PyMuPDF is used as a cheap fallback instead of OCR.

The predictor is lazy-initialised and cached at module level: Paddle downloads
its models on first use and loading is expensive, so we only pay for it once
per process.
"""

from __future__ import annotations

import io
from pathlib import Path

_LOGGED = False
_predictor = None


def _get_predictor():
    """Build (once) and return the cached PaddleOCR predictor."""
    global _predictor, _LOGGED
    if _predictor is None:
        import os

        from paddleocr import PaddleOCR

        if not _LOGGED:
            print("Initialising PaddleOCR (PP-OCRv5, first call downloads models)...")
            _LOGGED = True
        # enable_mkldnn=False: Paddle 3.3 on Windows crashes inside the oneDNN
        # PIR executor (ConvertPirAttribute2RuntimeAttribute) for these models.
        # Textline orientation is off by default: our documents are upright and
        # the extra classifier roughly doubles CPU inference time.
        _predictor = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=os.getenv("PADDLE_TEXTLINE_ORIENT", "0") == "1",
            enable_mkldnn=os.getenv("PADDLE_ENABLE_MKLDNN", "0") == "1",
        )
    return _predictor


def extract_text_from_image_paddle(image) -> str:
    """OCR a single image (PIL Image, bytes or file path) with Paddle."""
    from PIL import Image

    if isinstance(image, (str, Path)):
        image = Image.open(image)
    elif isinstance(image, bytes):
        image = Image.open(io.BytesIO(image))
    if not isinstance(image, Image.Image):
        raise TypeError(f"Unsupported image input: {type(image)!r}")

    import numpy as np

    result = _get_predictor().predict(np.asarray(image.convert("RGB")))
    return _result_to_text(result)


def _result_to_text(result) -> str:
    """Flatten a PaddleOCR 3.x result object into plain text."""
    lines: list[str] = []
    for page in result:
        texts = None
        if isinstance(page, dict):  # 3.x dict-style result
            texts = page.get("rec_texts")
        else:  # 3.x OCRResult object style
            texts = getattr(page, "rec_texts", None) or page.get("rec_texts", None)
        if texts:
            lines.extend(t for t in texts if t)
    return "\n".join(lines).strip()


def extract_from_scanned_pdf_paddle(pdf_bytes: bytes, dpi: int = 200) -> str:
    """Render every PDF page and OCR it with Paddle. Page breaks separated."""
    import pymupdf
    from PIL import Image

    pages_text: list[str] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            mode = "RGBA" if pix.alpha else "RGB"
            image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
            text = extract_text_from_image_paddle(image)
            pages_text.append(text)
    return "\n--- PAGE BREAK ---\n".join(p.strip() for p in pages_text).strip()


def extract_from_pdf_paddle(pdf_bytes: bytes, dpi: int = 200) -> str:
    """PDF extraction: embedded text layer first (PyMuPDF), Paddle OCR fallback.

    Digital PDFs keep their original text; scanned PDFs are rendered page by
    page and run through PaddleOCR.
    """
    import pymupdf

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        embedded = "\n".join(page.get_text() for page in doc).strip()

    if embedded:
        return embedded
    return extract_from_scanned_pdf_paddle(pdf_bytes, dpi=dpi)

