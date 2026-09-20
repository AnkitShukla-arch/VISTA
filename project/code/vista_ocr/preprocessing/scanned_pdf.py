from preprocessing.paddle_engine import extract_from_scanned_pdf_paddle


def extract_from_scanned_pdf(file_bytes):
    """OCR a scanned PDF page-by-page using PaddleOCR."""
    return extract_from_scanned_pdf_paddle(file_bytes)