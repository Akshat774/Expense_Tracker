"""
Gemini SDK layer for FinAI.
Uses the new `google-genai` SDK (v2+).

Key design decision: we do NOT pass the Pydantic model directly as
response_schema because Pydantic emits "default": null for every Optional
field, which Gemini's schema validator rejects with "Unknown field: default".
Instead we build a hand-crafted types.Schema with no default fields, then
parse the returned JSON into the Pydantic model ourselves.
"""

import os
import json
import logging
from io import BytesIO
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

from utils.prompts import RECEIPT_SYSTEM_INSTRUCTION, build_user_prompt
from utils.schema import LineItem, ReceiptExtraction

load_dotenv()
logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash"


# ── Hand-built schema (zero "default" fields) ──────────────────────────────

LINE_ITEM_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "description": types.Schema(type=types.Type.STRING),
        "quantity":    types.Schema(type=types.Type.NUMBER),
        "unit_price":  types.Schema(type=types.Type.NUMBER),
        "line_total":  types.Schema(type=types.Type.NUMBER),
    },
)

RECEIPT_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "merchant_name":    types.Schema(type=types.Type.STRING),
        "merchant_address": types.Schema(type=types.Type.STRING),
        "invoice_number":   types.Schema(type=types.Type.STRING),
        "transaction_date": types.Schema(type=types.Type.STRING),
        "category":         types.Schema(type=types.Type.STRING),
        "currency":         types.Schema(type=types.Type.STRING),
        "payment_method":   types.Schema(type=types.Type.STRING),
        "line_items":       types.Schema(
                                type=types.Type.ARRAY,
                                items=LINE_ITEM_SCHEMA,
                            ),
        "subtotal":         types.Schema(type=types.Type.NUMBER),
        "discount_amount":  types.Schema(type=types.Type.NUMBER),
        "tax_amount":       types.Schema(type=types.Type.NUMBER),
        "total_amount":     types.Schema(type=types.Type.NUMBER),
        "confidence_score": types.Schema(type=types.Type.NUMBER),
    },
)


# ── Client factory ──────────────────────────────────────────────────────────

def _get_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY not set in environment.")
    return genai.Client(api_key=api_key)


# ── Response → Pydantic ─────────────────────────────────────────────────────

def _parse_response(response) -> ReceiptExtraction:
    """Parse the raw Gemini response text into a validated ReceiptExtraction."""
    text = response.text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    data = json.loads(text)
    # Apply safe fallbacks
    data.setdefault("line_items", [])
    data.setdefault("confidence_score", 0.0)
    return ReceiptExtraction(**data)


# ── Generation config ────────────────────────────────────────────────────────

def _make_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=RECEIPT_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=RECEIPT_SCHEMA,
    )


# ── Public API ───────────────────────────────────────────────────────────────

def extract_from_image(
    image_buffer: BytesIO,
    extra_context: str = "",
) -> ReceiptExtraction:
    """
    Send a preprocessed JPEG BytesIO buffer to Gemini Vision and return
    a validated ReceiptExtraction.
    """
    try:
        client = _get_client()
        prompt = build_user_prompt(extra_context)
        image_bytes = image_buffer.read()

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=prompt),
            ],
            config=_make_config(),
        )
        return _parse_response(response)
    except Exception as e:
        logger.error(f"extract_from_image failed: {e}")
        raise


def extract_from_text(
    text: str,
    extra_context: str = "",
) -> ReceiptExtraction:
    """
    Send plain receipt text to Gemini and return a validated ReceiptExtraction.
    """
    try:
        client = _get_client()
        prompt = build_user_prompt(extra_context)
        full_prompt = f"{prompt}\n\nReceipt text:\n{text}"

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=full_prompt,
            config=_make_config(),
        )
        return _parse_response(response)
    except Exception as e:
        logger.error(f"extract_from_text failed: {e}")
        raise


def extract_receipt(
    image_buffer: Optional[BytesIO] = None,
    text: Optional[str] = None,
    extra_context: str = "",
) -> ReceiptExtraction:
    """Unified entry point — routes to image or text extraction."""
    if image_buffer is not None:
        return extract_from_image(image_buffer, extra_context)
    if text is not None:
        return extract_from_text(text, extra_context)
    raise ValueError("Either image_buffer or text must be provided.")


def health_check() -> dict:
    """Ping Gemini to verify connectivity."""
    try:
        client = _get_client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents="Reply with the single word: OK",
        )
        return {
            "ok": True,
            "model": MODEL_NAME,
            "message": f"Connected. Model replied: {response.text.strip()}",
        }
    except Exception as e:
        return {"ok": False, "model": MODEL_NAME, "message": str(e)}