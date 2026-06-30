"""
HuggingFace Inference API client for FinAI.

Supports multiple vision-language models. Set MODEL_ID to switch.
Image message format is built per-model since different models require
different prompt structures (e.g. Gemma-3 requires an "<image>" placeholder
token in the text, while Qwen accepts image and text as separate parts).

Supported models (tested):
  - google/gemma-3-27b-it        (requires <image> placeholder in text)
  - Qwen/Qwen2.5-VL-72B-Instruct (image and text as separate chunks)
  - Qwen/Qwen3-VL-8B-Instruct
"""

import os
import json
import base64
import logging
from io import BytesIO
from typing import Optional, Any

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from huggingface_hub.inference._generated.types.chat_completion import (
    ChatCompletionInputResponseFormatJSONSchema,
    ChatCompletionInputJSONSchema,
    ChatCompletionInputMessageChunk,
    ChatCompletionInputURL,
)

from utils.prompts import RECEIPT_SYSTEM_INSTRUCTION, build_user_prompt
from utils.schema import ReceiptExtraction

load_dotenv()
logger = logging.getLogger(__name__)

# ── Model configuration ─────────────────────────────────────────────────────
# Qwen2.5-VL-7B: best free vision model on HF — fast, accurate, no approval needed.
# provider="auto" lets the HF SDK pick whichever backend currently has the model
# loaded (deepinfra, together, etc.) so you never get "model not supported" errors.
MODEL_ID   = "Qwen/Qwen2.5-VL-7B-Instruct"
HF_PROVIDER = "hyperbolic"


# ── Schema cleaning ──────────────────────────────────────────────────────────

def _clean_schema(schema: Any) -> Any:
    """
    Recursively strip 'default' and 'title' keys, and unwrap
    anyOf: [{"type": X}, {"type": "null"}]  →  {"type": X}.
    This is required because HuggingFace's structured output endpoint
    rejects schemas that contain the 'default' keyword.
    """
    if not isinstance(schema, dict):
        return schema

    result = {}
    for k, v in schema.items():
        if k in ("default", "title"):
            continue
        if k == "anyOf" and isinstance(v, list):
            non_null = [i for i in v if i != {"type": "null"}]
            if len(non_null) == 1:
                result.update(_clean_schema(non_null[0]))
                continue
        result[k] = _clean_schema(v)
    return result


def _build_receipt_schema() -> dict:
    """
    Build a clean JSON schema dict from the ReceiptExtraction Pydantic model,
    with all $refs inlined and no forbidden keywords.
    """
    raw = ReceiptExtraction.model_json_schema()
    cleaned = _clean_schema(raw)

    # Inline $defs so the schema is self-contained
    defs = cleaned.pop("$defs", {})
    schema_str = json.dumps(cleaned)
    for name, def_schema in defs.items():
        inlined = json.dumps(_clean_schema(def_schema))[1:-1]  # strip outer {}
        schema_str = schema_str.replace(f'"$ref": "#/$defs/{name}"', inlined)

    return json.loads(schema_str)


RECEIPT_JSON_SCHEMA = _build_receipt_schema()


# ── Response format ──────────────────────────────────────────────────────────

def _json_response_format() -> ChatCompletionInputResponseFormatJSONSchema:
    return ChatCompletionInputResponseFormatJSONSchema(
        type="json_schema",
        json_schema=ChatCompletionInputJSONSchema(
            name="ReceiptExtraction",
            description="Structured receipt/invoice extraction",
            schema=RECEIPT_JSON_SCHEMA,
            strict=False,
        ),
    )


# ── Client factory ───────────────────────────────────────────────────────────

def _get_client() -> InferenceClient:
    token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not token:
        raise EnvironmentError("HUGGINGFACEHUB_API_TOKEN not set in .env")
    return InferenceClient(
        model=MODEL_ID,
        provider=HF_PROVIDER,   # "auto" — SDK picks deepinfra/together/etc dynamically
        token=token,
        timeout=45,             # Qwen2.5-VL-7B on GPU responds in <20s typically
    )


# ── Model-aware image message builder ───────────────────────────────────────

def _requires_image_placeholder(model_id: str) -> bool:
    """
    Gemma-3 (and other models using the same processor) require the text
    prompt to contain exactly one "<image>" token per image sent.
    Qwen-VL and similar models do NOT use this — they accept image_url
    and text as separate content chunks with no placeholder needed.
    """
    model_lower = model_id.lower()
    # Gemma-3 needs "<image>" in the text prompt.
    # Qwen-VL models do NOT — they use image_url as a separate content chunk.
    return "gemma" in model_lower


def _build_image_messages(data_url: str, prompt: str) -> list:
    """
    Build the messages list for a vision request, adapting to MODEL_ID.

    Gemma-3 format:
        user content = [image_url chunk, text chunk with "<image>\n\n{prompt}"]

    Qwen / default format:
        user content = [image_url chunk, text chunk with just the prompt]
    """
    image_chunk = ChatCompletionInputMessageChunk(
        type="image_url",
        image_url=ChatCompletionInputURL(url=data_url),
    )

    if _requires_image_placeholder(MODEL_ID):
        # Gemma-3: text must contain exactly one "<image>" marker
        text_chunk = ChatCompletionInputMessageChunk(
            type="text",
            text=f"<image>\n\n{prompt}",
        )
    else:
        # Qwen and others: plain text, no placeholder needed
        text_chunk = ChatCompletionInputMessageChunk(
            type="text",
            text=prompt,
        )

    return [
        {"role": "system", "content": RECEIPT_SYSTEM_INSTRUCTION},
        {"role": "user", "content": [image_chunk, text_chunk]},
    ]


# ── Response parsing ─────────────────────────────────────────────────────────

def _repair_truncated_json(text: str) -> str:
    """
    Repair JSON truncated mid-stream by max_tokens.

    Three-stage approach:
    1. Try to find the longest valid JSON prefix using raw_decode.
    2. Walk back to the last complete OBJECT boundary (closing brace/bracket
       that is NOT inside an incomplete parent object with a dangling key).
    3. Close any remaining unclosed braces/brackets.
    """
    import re

    # Stage 1: find longest prefix that raw_decode accepts
    decoder = json.JSONDecoder()
    best = None
    # Try progressively shorter versions by stripping from the right
    # at each potential boundary character
    boundaries = []
    in_str = False
    i = 0
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '\\' and i+1 < len(text):
                i += 2
                continue
            if c == '"':
                in_str = False
                boundaries.append(i+1)
        else:
            if c == '"':
                in_str = True
            elif c in ('}', ']'):
                boundaries.append(i+1)
        i += 1

    for pos in reversed(boundaries):
        candidate = text[:pos].rstrip().rstrip(',')
        # Close open structures
        d_brace   = candidate.count('{') - candidate.count('}')
        d_bracket = candidate.count('[') - candidate.count(']')
        closed = candidate + (']' * max(0,d_bracket)) + ('}' * max(0,d_brace))
        try:
            json.loads(closed)
            return closed
        except json.JSONDecodeError:
            continue

    # Stage 2 fallback: strip everything after last top-level comma or colon issue
    # Find last } or ] at depth 1 (direct child of root object/array)
    depth = 0
    in_str2 = False
    last_good = 0
    i = 0
    while i < len(text):
        c = text[i]
        if in_str2:
            if c == '\\' and i+1 < len(text):
                i += 2
                continue
            if c == '"':
                in_str2 = False
        else:
            if c == '"':
                in_str2 = True
            elif c in ('{','['):
                depth += 1
            elif c in ('}',']'):
                depth -= 1
                if depth == 1:
                    last_good = i + 1
        i += 1

    if last_good > 0:
        candidate = text[:last_good].rstrip().rstrip(',')
        d_brace   = candidate.count('{') - candidate.count('}')
        d_bracket = candidate.count('[') - candidate.count(']')
        closed = candidate + (']' * max(0,d_bracket)) + ('}' * max(0,d_brace))
        try:
            json.loads(closed)
            return closed
        except json.JSONDecodeError:
            pass

    return '{}'  # total fallback — empty object


def _parse_response(content: str) -> ReceiptExtraction:
    """Parse the model JSON into a validated ReceiptExtraction with auto-corrections."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    # Try clean parse first; if it fails, attempt truncation repair
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed ({e}), attempting truncation repair...")
        try:
            repaired = _repair_truncated_json(text)
            data = json.loads(repaired)
            logger.info("Truncation repair succeeded.")
        except json.JSONDecodeError:
            raise ValueError(
                f"Model returned invalid JSON that could not be repaired. "
                f"Raw content (first 300 chars): {text[:300]!r}"
            )

    # Safe fallbacks
    data.setdefault("line_items", [])
    data.setdefault("tax_breakdown", [])
    data.setdefault("confidence_score", 0.0)

    # Discount must always be stored as a positive number
    discount = data.get("discount_amount")
    if discount is not None and discount < 0:
        data["discount_amount"] = abs(discount)

    # Auto-sum tax_amount from breakdown components if missing
    if data.get("tax_amount") is None and data.get("tax_breakdown"):
        total_tax = sum(
            t.get("amount") or 0.0
            for t in data["tax_breakdown"]
            if isinstance(t, dict)
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

def extract_from_image(
    image_buffer: BytesIO,
    extra_context: str = "",
) -> ReceiptExtraction:
    """
    Send a preprocessed JPEG image to the configured vision model.
    Image is encoded as a base64 data URL. Message format is built
    per-model (e.g. Gemma-3 needs an <image> placeholder in the text).
    """
    try:
        client = _get_client()
        prompt = build_user_prompt(extra_context)

        # Encode image as base64 data URL
        image_bytes = image_buffer.read()
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64}"

        messages = _build_image_messages(data_url, prompt)

        response = client.chat_completion(
            messages=messages,
            response_format=_json_response_format(),
            max_tokens=8192,
            temperature=0.1,
        )

        choice = response.choices[0]
        content = choice.message.content
        if not content:
            raise ValueError("Model returned empty content.")
        finish = getattr(choice, "finish_reason", None)
        if finish == "length":
            logger.warning(
                "Model hit max_tokens — response was truncated. "
                "Attempting JSON repair..."
            )
        return _parse_response(content)

    except Exception as e:
        logger.error(f"extract_from_image failed: {e}")
        raise


def extract_from_text(
    text: str,
    extra_context: str = "",
) -> ReceiptExtraction:
    """
    Send plain receipt text to Qwen3-VL and return a validated ReceiptExtraction.
    """
    try:
        client = _get_client()
        prompt = build_user_prompt(extra_context)
        full_prompt = f"{prompt}\n\nReceipt text:\n{text}"

        messages = [
            {"role": "system", "content": RECEIPT_SYSTEM_INSTRUCTION},
            {"role": "user", "content": full_prompt},
        ]

        response = client.chat_completion(
            messages=messages,
            response_format=_json_response_format(),
            max_tokens=8192,
            temperature=0.1,
        )

        choice = response.choices[0]
        content = choice.message.content
        if not content:
            raise ValueError("Model returned empty content.")
        finish = getattr(choice, "finish_reason", None)
        if finish == "length":
            logger.warning(
                "Model hit max_tokens — response was truncated. "
                "Attempting JSON repair..."
            )
        return _parse_response(content)

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
    """Ping the model with a simple text prompt to verify connectivity."""
    try:
        client = _get_client()
        response = client.chat_completion(
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=10,
        )
        reply = response.choices[0].message.content.strip()
        return {
            "ok": True,
            "model": MODEL_ID,
            "message": f"Connected. Model replied: {reply}",
        }
    except Exception as e:
        return {"ok": False, "model": MODEL_ID, "message": str(e)}