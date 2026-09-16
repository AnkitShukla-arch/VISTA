from preprocessing.paddle_engine import extract_text_from_image_paddle


def extract_from_image(file_bytes):
    """OCR raw image bytes with PaddleOCR."""
    return extract_text_from_image_paddle(file_bytes)
