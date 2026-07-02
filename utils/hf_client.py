"""
HuggingFace Inference API client for FinAI.

Resilience strategy
--------------------
Instead of hardcoding ONE provider (which breaks the moment that provider
doesn't serve the model, is down, or rejects your key), this client tries a
PRIORITY LIST of known-good (model, provider) pairs in order. The first one
that works wins; failures are logged and the next candidate is tried
automatically. If every candidate fails, you get one clear error that lists
exactly what was tried and why each attempt failed — never a bare
"internal server error".

Supported providers per candidate use their OWN api key:
    hf-inference / auto  → HUGGINGFACEHUB_API_TOKEN  (hf_...)
    hyperbolic            → HYPERBOLIC_API_KEY
    deepinfra              → DEEPINFRA_API_KEY
    together                → TOGETHER_API_KEY
    fireworks-ai             → FIREWORKS_API_KEY
Only set the keys for providers you actually have accounts on — missing
keys are skipped silently, not treated as errors, unless ALL candidates
have no usable key (then you get a clear setup message).
"""

import os
import re
import json
import base64
import logging
from io import BytesIO
from typing import Optional, Any

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError
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


# ── Candidate (model, provider) chain ───────────────────────────────────────
#
# Ordered by: speed, reliability, and how widely the provider serves Qwen-VL.
# Add/remove/reorder entries here — nothing else in this file needs to change.
#
CANDIDATES = [
    # (model_id, provider, env_var_for_key)
    ("Qwen/Qwen2.5-VL-7B-Instruct", "hyperbolic", "HYPERBOLIC_API_KEY"),
    ("Qwen/Qwen2.5-VL-7B-Instruct", "together",   "TOGETHER_API_KEY"),
    ("Qwen/Qwen2.5-VL-7B-Instruct", "deepinfra",  "DEEPINFRA_API_KEY"),
    ("Qwen/Qwen2.5-VL-7B-Instruct", "auto",       "HUGGINGFACEHUB_API_TOKEN"),
    ("Qwen/Qwen2.5-VL-7B-Instruct", "hf-inference", "HUGGINGFACEHUB_API_TOKEN"),
]

# Last successful candidate is cached for the rest of the process so we don't
# re-probe dead providers on every single request.
_last_working: Optional[tuple] = None


# ── Schema cleaning (shared across all providers) ───────────────────────────

def _clean_schema(schema: Any) -> Any:
    """
    Strip 'default'/'title' keys and unwrap anyOf:[{type:X},{type:null}] →
    {type:X}. HF structured-output endpoints reject schemas containing
    'default', so this must run on every Pydantic-generated schema.
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
    raw = ReceiptExtraction.model_json_schema()
    cleaned = _clean_schema(raw)
    defs = cleaned.pop("$defs", {})
    schema_str = json.dumps(cleaned)
    for name, def_schema in defs.items():
        inlined = json.dumps(_clean_schema(def_schema))[1:-1]
        schema_str = schema_str.replace(f'"$ref": "#/$defs/{name}"', inlined)
    return json.loads(schema_str)


RECEIPT_JSON_SCHEMA = _build_receipt_schema()


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


# ── Model-aware image message builder ───────────────────────────────────────

def _requires_image_placeholder(model_id: str) -> bool:
    """Gemma-3 needs a literal '<image>' token in the text; Qwen-VL does not."""
    return "gemma" in model_id.lower()


def _build_image_messages(model_id: str, data_url: str, prompt: str) -> list:
    image_chunk = ChatCompletionInputMessageChunk(
        type="image_url",
        image_url=ChatCompletionInputURL(url=data_url),
    )
    text = f"<image>\n\n{prompt}" if _requires_image_placeholder(model_id) else prompt
    text_chunk = ChatCompletionInputMessageChunk(type="text", text=text)
    return [
        {"role": "system", "content": RECEIPT_SYSTEM_INSTRUCTION},
        {"role": "user", "content": [image_chunk, text_chunk]},
    ]


# ── JSON truncation repair ──────────────────────────────────────────────────

def _repair_truncated_json(text: str) -> str:
    """
    Repair JSON truncated mid-stream by max_tokens. Finds the longest valid
    JSON prefix by trying every "safe" boundary (closing quote/brace/bracket)
    from the end backwards, closing remaining open structures, and validating
    with json.loads at each attempt.
    """
    boundaries = []
    in_str = False
    i = 0
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '\\' and i + 1 < len(text):
                i += 2
                continue
            if c == '"':
                in_str = False
                boundaries.append(i + 1)
        else:
            if c == '"':
                in_str = True
            elif c in ('}', ']'):
                boundaries.append(i + 1)
        i += 1

    for pos in reversed(boundaries):
        candidate = text[:pos].rstrip().rstrip(',')
        d_brace = candidate.count('{') - candidate.count('}')
        d_bracket = candidate.count('[') - candidate.count(']')
        closed = candidate + (']' * max(0, d_bracket)) + ('}' * max(0, d_brace))
        try:
            json.loads(closed)
            return closed
        except json.JSONDecodeError:
            continue

    # Fallback: cut at the last depth-1 closing brace/bracket
    depth = 0
    in_str2 = False
    last_good = 0
    i = 0
    while i < len(text):
        c = text[i]
        if in_str2:
            if c == '\\' and i + 1 < len(text):
                i += 2
                continue
            if c == '"':
                in_str2 = False
        else:
            if c == '"':
                in_str2 = True
            elif c in ('{', '['):
                depth += 1
            elif c in ('}', ']'):
                depth -= 1
                if depth == 1:
                    last_good = i + 1
        i += 1

    if last_good > 0:
        candidate = text[:last_good].rstrip().rstrip(',')
        d_brace = candidate.count('{') - candidate.count('}')
        d_bracket = candidate.count('[') - candidate.count(']')
        closed = candidate + (']' * max(0, d_bracket)) + ('}' * max(0, d_brace))
        try:
            json.loads(closed)
            return closed
        except json.JSONDecodeError:
            pass

    return '{}'


def _parse_response(content: str) -> ReceiptExtraction:
    """Parse model JSON into a validated ReceiptExtraction with auto-corrections."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed ({e}), attempting truncation repair...")
        try:
            data = json.loads(_repair_truncated_json(text))
            logger.info("Truncation repair succeeded.")
        except json.JSONDecodeError:
            raise ValueError(
                f"Model returned invalid JSON that could not be repaired. "
                f"Raw content (first 300 chars): {text[:300]!r}"
            )

    data.setdefault("line_items", [])
    data.setdefault("tax_breakdown", [])
    data.setdefault("confidence_score", 0.0)

    discount = data.get("discount_amount")
    if discount is not None and discount < 0:
        data["discount_amount"] = abs(discount)

    if data.get("tax_amount") is None and data.get("tax_breakdown"):
        total_tax = sum(
            t.get("amount") or 0.0 for t in data["tax_breakdown"] if isinstance(t, dict)
        )
        if total_tax:
            data["tax_amount"] = round(total_tax, 2)

    if data.get("total_amount") is None:
        subtotal = data.get("subtotal") or 0.0
        disc = data.get("discount_amount") or 0.0
        tax = data.get("tax_amount") or 0.0
        if subtotal:
            data["total_amount"] = round(subtotal - disc + tax, 2)

    return ReceiptExtraction(**data)


# ── Error classification ────────────────────────────────────────────────────

def _classify_error(exc: Exception) -> str:
    """Turn a raw exception into a short, human-readable reason."""
    msg = str(exc)
    low = msg.lower()
    if isinstance(exc, HfHubHTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 401 or "401" in low:
            return "invalid API key"
        if status == 403 or "403" in low:
            return "access forbidden (key lacks permission for this model)"
        if status == 404 or "not found" in low:
            return "model not found on this provider"
        if status == 422 or "unprocessable" in low:
            return "request rejected (bad schema or unsupported param)"
        if status == 429 or "rate limit" in low:
            return "rate limited"
        if status and status >= 500:
            return f"provider internal server error ({status})"
        return f"HTTP error ({status or '?'})"
    if "timeout" in low or "timed out" in low:
        return "request timed out"
    if "model id" in low and "supported" in low:
        return "model/provider mismatch"
    if "connection" in low:
        return "connection error"
    return msg[:120]


# ── Client factory with fallback chain ──────────────────────────────────────

def _try_candidate(model_id: str, provider: str, env_var: str) -> Optional[InferenceClient]:
    api_key = os.getenv(env_var)
    if not api_key:
        return None
    return InferenceClient(
        model=model_id,
        provider=provider,
        token=api_key,
        timeout=45,
    )


def _call_with_fallback(build_messages_fn) -> tuple:
    """
    Try each candidate in order. build_messages_fn(model_id) -> messages list.
    Returns (response, model_id, provider) from the first candidate that
    succeeds. Raises a single consolidated error if every candidate fails.
    """
    global _last_working

    ordered = list(CANDIDATES)
    # Try the last known-working candidate first to avoid re-probing dead ones
    if _last_working and _last_working in ordered:
        ordered.remove(_last_working)
        ordered.insert(0, _last_working)

    attempts_log = []
    any_key_found = False

    for model_id, provider, env_var in ordered:
        client = _try_candidate(model_id, provider, env_var)
        if client is None:
            attempts_log.append(f"  • {provider} ({model_id}): skipped — {env_var} not set in .env")
            continue

        any_key_found = True
        try:
            messages = build_messages_fn(model_id)
            response = client.chat_completion(
                messages=messages,
                response_format=_json_response_format(),
                max_tokens=8192,
                temperature=0.1,
            )
            _last_working = (model_id, provider, env_var)
            logger.info(f"Extraction succeeded via provider={provider}, model={model_id}")
            return response, model_id, provider

        except Exception as e:
            reason = _classify_error(e)
            attempts_log.append(f"  • {provider} ({model_id}): FAILED — {reason}")
            logger.warning(f"Provider '{provider}' failed: {reason}")
            continue

    if not any_key_found:
        raise EnvironmentError(
            "No API key found for any configured provider.\n"
            "Add at least ONE of these to your .env file:\n"
            "  HYPERBOLIC_API_KEY=...\n"
            "  TOGETHER_API_KEY=...\n"
            "  DEEPINFRA_API_KEY=...\n"
            "  HUGGINGFACEHUB_API_TOKEN=hf_...\n"
        )

    raise RuntimeError(
        "All AI providers failed to respond. Attempts:\n" + "\n".join(attempts_log)
    )


# ── Public API ───────────────────────────────────────────────────────────────

def extract_from_image(image_buffer: BytesIO, extra_context: str = "") -> ReceiptExtraction:
    """
    Send a preprocessed JPEG image to the first working vision provider.
    Tries multiple (model, provider) pairs automatically on failure.
    """
    prompt = build_user_prompt(extra_context)
    image_bytes = image_buffer.read()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"

    def build(model_id: str):
        return _build_image_messages(model_id, data_url, prompt)

    response, model_id, provider = _call_with_fallback(build)

    choice = response.choices[0]
    content = choice.message.content
    if not content:
        raise ValueError(f"Model '{model_id}' on '{provider}' returned empty content.")
    if getattr(choice, "finish_reason", None) == "length":
        logger.warning("Response truncated by max_tokens — attempting JSON repair.")
    return _parse_response(content)


def extract_from_text(text: str, extra_context: str = "") -> ReceiptExtraction:
    """Send plain receipt text to the first working provider."""
    prompt = build_user_prompt(extra_context)
    full_prompt = f"{prompt}\n\nReceipt text:\n{text}"

    def build(model_id: str):
        return [
            {"role": "system", "content": RECEIPT_SYSTEM_INSTRUCTION},
            {"role": "user", "content": full_prompt},
        ]

    response, model_id, provider = _call_with_fallback(build)

    choice = response.choices[0]
    content = choice.message.content
    if not content:
        raise ValueError(f"Model '{model_id}' on '{provider}' returned empty content.")
    if getattr(choice, "finish_reason", None) == "length":
        logger.warning("Response truncated by max_tokens — attempting JSON repair.")
    return _parse_response(content)


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
    """
    Ping each configured provider in order and report which ones are alive.
    Returns ok=True if at least one provider responds.
    """
    results = []
    working_any = False

    for model_id, provider, env_var in CANDIDATES:
        api_key = os.getenv(env_var)
        if not api_key:
            results.append(f"⬜ {provider}: no key ({env_var} not set)")
            continue
        try:
            client = InferenceClient(model=model_id, provider=provider, token=api_key, timeout=20)
            resp = client.chat_completion(
                messages=[{"role": "user", "content": "Reply with the single word: OK"}],
                max_tokens=10,
            )
            reply = resp.choices[0].message.content.strip()
            results.append(f"🟢 {provider} ({model_id}): {reply}")
            working_any = True
        except Exception as e:
            results.append(f"🔴 {provider} ({model_id}): {_classify_error(e)}")

    return {
        "ok": working_any,
        "model": CANDIDATES[0][0],
        "message": "\n".join(results),
    }