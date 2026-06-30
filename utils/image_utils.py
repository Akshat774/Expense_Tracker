"""
Utility functions for preprocessing receipt images before
sending them to Gemini for multimodal extraction.
"""

from io import BytesIO
from PIL import Image, ImageOps

# Maximum dimension for width or height
MAX_DIMENSION = 2048

# JPEG quality after compression
JPEG_QUALITY = 90

# Allowed formats
SUPPORTED_FORMATS = {
    "PNG",
    "JPEG",
    "JPG",
    "WEBP"
}


def load_image(file) -> Image.Image:
    """
    Open an uploaded Streamlit file as a Pillow Image.
    Automatically fixes EXIF orientation.
    """
    image = Image.open(file)
    image = ImageOps.exif_transpose(image)
    return image


def convert_to_rgb(image: Image.Image) -> Image.Image:
    """
    Convert images with alpha channels or palettes to RGB.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def resize_if_needed(image: Image.Image) -> Image.Image:
    """
    Resize large images while preserving aspect ratio.
    """
    width, height = image.size

    if max(width, height) <= MAX_DIMENSION:
        return image

    image.thumbnail(
        (MAX_DIMENSION, MAX_DIMENSION),
        Image.Resampling.LANCZOS
    )

    return image


def compress_image(image: Image.Image) -> BytesIO:
    """
    Compress image into an in-memory JPEG buffer.
    """
    buffer = BytesIO()

    image.save(
        buffer,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True
    )

    buffer.seek(0)

    return buffer


def preprocess_image(file):
    """
    Complete preprocessing pipeline.

    Returns:
        processed_image (PIL.Image.Image)
        compressed_buffer (BytesIO)
    """

    image = load_image(file)

    image = convert_to_rgb(image)

    image = resize_if_needed(image)

    compressed = compress_image(image)

    return image, compressed


def get_image_metadata(image: Image.Image) -> dict:
    """
    Return useful metadata for UI display.
    """

    return {
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "format": image.format,
    }