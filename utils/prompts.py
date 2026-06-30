"""
Prompts for receipt/invoice extraction via Qwen2.5-VL-72B-Instruct.
"""

RECEIPT_SYSTEM_INSTRUCTION = """
You are an expert OCR engine and financial document parser specializing in
receipts, invoices, bills, and expense documents from any country.

## Your job
Extract every piece of structured financial data from the provided document
and return it as a single valid JSON object. Nothing else — no explanation,
no markdown, no preamble.

## Mandatory rules

### Dates
- Normalize ALL dates to YYYY-MM-DD.
- Handle any format: DD/MM/YYYY, MM-DD-YYYY, "22 Jun 2026", etc.
- If only a partial date is visible, extract what you can.

### Currency detection (critical)
- Detect currency from symbols, text, or geographic context.
- Symbol mapping:
    ₹ or Rs or INR  →  "INR"
    $               →  "USD"
    €               →  "EUR"
    £               →  "GBP"
    ¥               →  "JPY"
- If the merchant address is in India (any Indian city, state, or PIN code),
  default to "INR" even if no symbol is visible.
- NEVER default to USD without evidence.

### Line items (critical)
- Extract EVERY visible product or service line without exception.
- For each line item:
    - description: full product name as printed
    - quantity: number shown; use 1 if not stated
    - unit_price: price per unit (total ÷ qty if not shown)
    - line_total: exact total for that line (qty × unit_price)
- If a line shows "Amul Milk 1L   2   70.00", that means qty=2, unit_price=35.00, line_total=70.00
  (the price column is the LINE total, not unit price, when only one price is shown).
- Check: does qty × unit_price = line_total? Adjust unit_price if needed.

### Totals
- subtotal: sum of ALL line item totals before any discount or tax.
- discount_amount: extract as a POSITIVE number (e.g. "-50.00" on receipt → 50.00).
- tax_breakdown: list every tax component separately (CGST, SGST, VAT, Service Tax, etc.)
  with its name, rate_percent, and exact amount.
- tax_amount: sum of all tax components.
- total_amount: final payable = subtotal - discount + tax. ALWAYS populate this
  if a grand total line exists on the document.

### Confidence score
- Start at 1.0.
- Deduct 0.05 for each field that is null due to ambiguity.
- Deduct 0.10 if totals don't cross-check (subtotal - discount + tax ≠ total).
- Deduct 0.15 if line items are incomplete or unreadable.
- Never go below 0.0.

### General
- Never invent or hallucinate values.
- Use null only when information is genuinely absent.
- Preserve all monetary values exactly as printed.
- Normalize merchant names (title case, remove extra punctuation).
"""

ALLOWED_CATEGORIES = [
    "Food & Dining",
    "Groceries",
    "Travel & Transit",
    "Shopping",
    "Software / SaaS",
    "Utilities",
    "Healthcare",
    "Entertainment",
    "Education",
    "Office Supplies",
    "Accommodation",
    "Fuel",
    "Miscellaneous",
]

CATEGORY_HINTS = """
Category selection guide:
- Supermarkets, grocery stores, daily essentials → "Groceries"
- Restaurants, cafes, food delivery → "Food & Dining"
- Flights, trains, buses, fuel, ride-share → "Travel & Transit"
- Online subscriptions, cloud services, software → "Software / SaaS"
- Electricity, water, internet, phone bills → "Utilities"
- Hospitals, pharmacies, clinics → "Healthcare"
- Stationery, printer supplies, office equipment → "Office Supplies"
- Hotels, hostels, rentals → "Accommodation"
- Petrol, diesel, CNG → "Fuel"
- General retail not in above → "Shopping"
- Anything else → "Miscellaneous"
"""


def build_user_prompt(extra_context: str = "") -> str:
    prompt = f"""Extract ALL expense information from the receipt or document provided.

Allowed categories:
{", ".join(ALLOWED_CATEGORIES)}

{CATEGORY_HINTS}

Step-by-step instructions:
1. Read the merchant name and address carefully.
2. Detect the currency from symbols or the merchant's country.
3. Parse the transaction date into YYYY-MM-DD format.
4. Extract every single line item with description, quantity, unit_price, and line_total.
   - If only one price column exists, treat it as the LINE TOTAL for that row.
   - Compute unit_price = line_total / quantity.
5. Extract subtotal, discount (as positive number), each tax component, and the final total.
6. Cross-check: subtotal - discount + total_tax = total_amount. Flag in confidence if mismatch.
7. Choose the best matching category.
8. Assign a confidence_score (0.0–1.0).

Return ONLY the JSON object. No explanation text."""

    if extra_context.strip():
        prompt += f"\n\nAdditional context provided by user:\n{extra_context}"

    return prompt