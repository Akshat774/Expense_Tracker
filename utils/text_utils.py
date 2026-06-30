"""
Text file processing utilities for FinAI.
"""

import logging

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 50_000


def extract_text_from_txt(file) -> str:
    """
    Read and decode a plain text file upload.

    Args:
        file: Streamlit UploadedFile or file-like object.

    Returns:
        Decoded string content.
    """
    try:
        raw = file.read()
        text = raw.decode("utf-8", errors="replace")
        if len(text) > MAX_TEXT_LENGTH:
            logger.warning(f"Text file truncated from {len(text)} to {MAX_TEXT_LENGTH} chars.")
            text = text[:MAX_TEXT_LENGTH]
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to read text file: {e}")
        raise
