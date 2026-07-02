"""
Gemini AI client for FinAI.
Uses Google AI Studio — Gemini 2.5 Flash via the `google-genai` SDK (v2+).

Key decisions
-------------
- response_schema is passed as a plain dict (no Pydantic class) because the
  SDK cannot serialize Pydantic ModelMetaclass objects. We clean the schema
  (strip 'default', 'title', unwrap anyOf nulls) before passing it.
- Images are sent as inline bytes via types.Part.from_bytes — no base64
  encoding needed, no URL round-trip.
- Response is parsed with json.loads(response.text) into our Pydantic model
  for validation and type safety.
- health_check() sends a lightweight text ping and returns a status dict
  compatible with what settings.py expects.
"""

import os
import json
import logging
from io import BytesIO
from typing import Optional, Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from utils.prompts import RECEIPT_SYSTEM_INSTRUCTION, build_user_prompt
from utils.schema import ReceiptExtraction

load_dotenv()
logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"


# ── Schema builder (clean dict — no 'default' or 'title' fields) ────────────

def _clean(schema: Any) -> Any:
    """Recursively strip 'default'/'title' and unwrap anyOf nullables."""
    if not isinstance(schema, dict):
        return schema
    result = {}
    for k, v in schema.items():
        if k in ("default", "title"):
            continue
        if k == "anyOf" and isinstance(v, list):
            non_null = [i for i in v if i != {"type": "null"}]
            if len(non_null) == 1:
                result.update(_clean(non_null[0]))
                continue
        result[k] = _clean(v)
    return result


def _build_schema() -> dict:
    """Return a clean JSON-schema dict for ReceiptExtraction."""
    raw = ReceiptExtraction.model_json_schema()
    cleaned = _clean(raw)
    defs = cleaned.pop("$defs", {})
    schema_str = json.dumps(cleaned)
    for name, def_schema in defs.items():
        inlined = json.dumps(_clean(def_schema))[1:-1]
        schema_str = schema_str.replace(f'"$ref": "#/$defs/{name}"', inlined)
    return json.loads(schema_str)


RECEIPT_SCHEMA: dict = _build_schema()


# ── Client factory ───────────────────────────────────────────────────────────

def _get_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. "
            "Add it to your .env file: GOOGLE_API_KEY=your_key_here\n"
            "Get a free key at: https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=api_key)


def _make_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=RECEIPT_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=RECEIPT_SCHEMA,
    )


# ── Response parsing ─────────────────────────────────────────────────────────

def _parse(response) -> ReceiptExtraction:
    """Parse Gemini response text into a validated ReceiptExtraction."""
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    data = json.loads(text)

    # Safe fallbacks
    data.setdefault("line_items", [])
    data.setdefault("tax_breakdown", [])
    data.setdefault("confidence_score", 0.0)

    # Discount must always be stored as a positive number
    discount = data.get("discount_amount")
    if discount is not None and discount < 0:
        data["discount_amount"] = abs(discount)

    # Auto-sum tax_amount from breakdown if missing
    if data.get("tax_amount") is None and data.get("tax_breakdown"):
        total_tax = sum(
            t.get("amount") or 0.0
            for t in data["tax_breakdown"] if isinstance(t, dict)
        )
        if total_tax:
            data["tax_amount"] = round(total_tax, 2)

    # Auto-compute total if missing but components are present
    if data.get("total_amount") is None:
        subtotal = data.get("subtotal") or 0.0
        disc = data.get("discount_amount") or 0.0
        tax = data.get("tax_amount") or 0.0
        if subtotal:
            data["total_amount"] = round(subtotal - disc + tax, 2)

    return ReceiptExtraction(**data)


# ── Public API ───────────────────────────────────────────────────────────────

def extract_from_image(image_buffer: BytesIO, extra_context: str = "") -> ReceiptExtraction:
    """
    Send a preprocessed JPEG image to Gemini 2.5 Flash and return a
    validated ReceiptExtraction. Image is sent as inline bytes.
    """
    try:
        client = _get_client()
        prompt = build_user_prompt(extra_context)
        image_bytes = image_buffer.read()

        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=prompt),
            ],
            config=_make_config(),
        )
        return _parse(response)
    except Exception as e:
        logger.error(f"extract_from_image failed: {e}")
        raise


def extract_from_text(text: str, extra_context: str = "") -> ReceiptExtraction:
    """Send plain receipt text to Gemini 2.5 Flash."""
    try:
        client = _get_client()
        prompt = build_user_prompt(extra_context)
        full_prompt = f"{prompt}\n\nReceipt text:\n{text}"

        response = client.models.generate_content(
            model=MODEL,
            contents=full_prompt,
            config=_make_config(),
        )
        return _parse(response)
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


def generate_insights(summary_json: list) -> str:
    """
    Generate financial insights from transaction history.
    Returns the model's markdown-formatted response text.
    """
    try:
        client = _get_client()
        prompt = f"""You are a personal finance advisor.

Analyze the following expense data and provide:
1. Key spending patterns (2-3 bullet points)
2. Any anomalies or concerns  
3. Actionable savings tips (2-3 specific suggestions)

Expense data (most recent 50 transactions):
{json.dumps(summary_json, indent=2)}

Keep the response concise and practical. Use markdown formatting."""

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are a personal finance advisor. Be concise and practical.",
            ),
        )
        return response.text
    except Exception as e:
        logger.error(f"generate_insights failed: {e}")
        raise


def health_check() -> dict:
    """Ping Gemini to verify API key and connectivity."""
    try:
        client = _get_client()
        response = client.models.generate_content(
            model=MODEL,
            contents="Reply with exactly one word: OK",
        )
        reply = response.text.strip()
        return {
            "ok": True,
            "model": MODEL,
            "message": f"🟢 Connected — {MODEL} replied: {reply}",
        }
    except EnvironmentError as e:
        return {"ok": False, "model": MODEL, "message": f"🔴 {e}"}
    except Exception as e:
        return {"ok": False, "model": MODEL, "message": f"🔴 {e}"}