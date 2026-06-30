"""
PDF processing utilities for FinAI.

Handles both searchable (text) and scanned (image) PDFs.
"""

import logging
from io import BytesIO
from typing import List, Tuple

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file) -> str:
    """
    Attempt to extract text from a searchable PDF using pypdf.

    Args:
        file: File-like object (Streamlit UploadedFile or BytesIO).

    Returns:
        Extracted text string, or empty string if none found.
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(file)
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())
        return "\n\n".join(pages_text)
    except Exception as e:
        logger.warning(f"pypdf text extraction failed: {e}")
        return ""


def pdf_to_images(file) -> List[BytesIO]:
    """
    Convert each PDF page to a preprocessed JPEG BytesIO buffer.
    Used for scanned PDFs.

    Args:
        file: File-like object.

    Returns:
        List of BytesIO JPEG buffers (one per page).
    """
    try:
        import fitz  # PyMuPDF
        from utils.image_utils import preprocess_image
        from PIL import Image

        file_bytes = file.read() if hasattr(file, "read") else file
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        buffers = []
        for page in doc:
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for clarity
            pix = page.get_pixmap(matrix=mat)
            img_bytes = BytesIO(pix.tobytes("jpeg"))
            _, compressed = preprocess_image(img_bytes)
            buffers.append(compressed)
        return buffers
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed. Cannot convert scanned PDF pages.")
        return []
    except Exception as e:
        logger.error(f"pdf_to_images failed: {e}")
        return []


def is_searchable_pdf(file) -> Tuple[bool, str]:
    """
    Determine whether the PDF has extractable text.

    Returns:
        (is_searchable, extracted_text)
    """
    if hasattr(file, "seek"):
        file.seek(0)
    text = extract_text_from_pdf(file)
    if hasattr(file, "seek"):
        file.seek(0)
    has_text = bool(text.strip())
    return has_text, text


def process_pdf(file) -> Tuple[str, List[BytesIO]]:
    """
    Unified PDF processing entry point.

    Returns:
        (text, image_buffers)
        - For searchable PDFs: text is populated, image_buffers is empty.
        - For scanned PDFs: text is empty, image_buffers has page images.
    """
    searchable, text = is_searchable_pdf(file)
    if searchable:
        logger.info("PDF is searchable — using text extraction.")
        return text, []
    logger.info("PDF appears scanned — converting pages to images.")
    if hasattr(file, "seek"):
        file.seek(0)
    images = pdf_to_images(file)
    return "", images
