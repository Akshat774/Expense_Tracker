"""
Image preprocessing utilities for FinAI receipt images.

Orientation strategy (applied in order):
  1. EXIF transpose  — fixes metadata-encoded rotation from most phones
  2. Portrait enforcement — receipts are always taller than wide; if the
     image is landscape after EXIF, rotate 90° CW to make it portrait
  3. Manual override  — upload.py exposes rotation buttons so the user can
     correct any remaining orientation issues before extraction
"""

from io import BytesIO
from PIL import Image, ImageOps
import logging

logger = logging.getLogger(__name__)

MAX_DIMENSION = 2048
JPEG_QUALITY  = 90

SUPPORTED_FORMATS = {"PNG", "JPEG", "JPG", "WEBP"}


def load_image(file) -> Image.Image:
    """Open a Streamlit UploadedFile/BytesIO as a Pillow Image."""
    image = Image.open(file)
    return image


def apply_exif_rotation(image: Image.Image) -> Image.Image:
    """Apply EXIF orientation tag so the image displays correctly."""
    try:
        image = ImageOps.exif_transpose(image)
    except Exception as e:
        logger.debug(f"exif_transpose skipped: {e}")
    return image


def enforce_portrait(image: Image.Image) -> Image.Image:
    """
    Rotate landscape images 90° CW to make them portrait.

    Receipts are always printed in portrait orientation (taller than wide).
    If the image is wider than tall after EXIF correction, the phone was
    held sideways — rotate it upright.
    """
    w, h = image.size
    if w > h:
        logger.debug(f"Portrait enforcement: rotating {w}×{h} → CW 90°")
        image = image.rotate(-90, expand=True)
    return image


def convert_to_rgb(image: Image.Image) -> Image.Image:
    """Convert RGBA, palette, or other modes to plain RGB."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def rotate_image(image: Image.Image, degrees: int) -> Image.Image:
    """
    Rotate image by the given degrees (positive = CCW, negative = CW).
    Used by the manual rotation buttons in the upload UI.
    """
    return image.rotate(degrees, expand=True)


def resize_if_needed(image: Image.Image) -> Image.Image:
    """Resize so neither dimension exceeds MAX_DIMENSION, preserving ratio."""
    if max(image.size) > MAX_DIMENSION:
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
    return image


def compress_image(image: Image.Image) -> BytesIO:
    """Compress to an in-memory JPEG buffer."""
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    buffer.seek(0)
    return buffer


def auto_orient(file) -> Image.Image:
    """
    Full auto-orientation pipeline for preview and sending to Gemini:
      load → EXIF → portrait enforcement → RGB
    Returns a PIL Image ready for display or further processing.
    """
    image = load_image(file)
    image = apply_exif_rotation(image)
    image = enforce_portrait(image)
    image = convert_to_rgb(image)
    return image


def preprocess_image(file):
    """
    Full preprocessing pipeline for sending to Gemini.
    Returns (PIL.Image, BytesIO compressed buffer).
    """
    image = auto_orient(file)
    image = resize_if_needed(image)
    compressed = compress_image(image)
    return image, compressed


def image_to_buffer(image: Image.Image) -> BytesIO:
    """Convert a PIL Image to a compressed JPEG BytesIO buffer."""
    return compress_image(image)


def get_image_metadata(image: Image.Image) -> dict:
    return {
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "format": getattr(image, "format", None),
    }