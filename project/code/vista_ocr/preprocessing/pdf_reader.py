import pdfplumber
import io

from preprocessing.paddle_engine import extract_from_scanned_pdf_paddle


def extract_from_pdf(file_bytes):
    """
    Extract text from a PDF.

    Supports:
    - Digital PDFs (using pdfplumber)
    - Scanned PDFs (using OCR)
    """

    text = ""

    # -----------------------------
    # Try Digital PDF Extraction
    # -----------------------------
    print("Trying digital PDF extraction...")

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:

        for page in pdf.pages:

            extracted = page.extract_text()

            if extracted:
                text += extracted + "\n"

    # -----------------------------
    # If text found, return it
    # -----------------------------
    if text.strip():

        print("Digital PDF detected.")

        return text.strip()

    # -----------------------------
    # Otherwise use OCR
    # -----------------------------
    print("No embedded text found.")
    print("Running OCR on scanned PDF...")

    images = [None]  # placeholder: Paddle path renders pages internally

    ocr_text = ""

    print("Running PaddleOCR on scanned PDF...")

    ocr_text = extract_from_scanned_pdf_paddle(file_bytes)

    print("OCR completed.")

    return ocr_text.strip()