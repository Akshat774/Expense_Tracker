from pydantic import BaseModel, Field
from typing import List, Optional


class LineItem(BaseModel):
    description: Optional[str] = None
    """Full item name exactly as printed on the receipt."""

    quantity: Optional[float] = None
    """Number of units purchased. Default to 1.0 if not stated."""

    unit_price: Optional[float] = None
    """Price per single unit before any discount."""

    line_total: Optional[float] = None
    """Total for this line = quantity × unit_price. Extract directly if shown, else compute."""


class TaxBreakdown(BaseModel):
    tax_name: Optional[str] = None
    """Label as printed, e.g. 'CGST', 'SGST', 'VAT', 'GST', 'HST', 'Service Tax'."""

    rate_percent: Optional[float] = None
    """Tax rate as a percentage, e.g. 2.5 for 2.5%."""

    amount: Optional[float] = None
    """Exact monetary amount of this tax component."""


class ReceiptExtraction(BaseModel):
    merchant_name: Optional[str] = None
    """Normalized business name, e.g. 'Fresh Mart Supermarket'."""

    merchant_address: Optional[str] = None
    """Full address as printed, including city, state, pin/zip."""

    invoice_number: Optional[str] = None
    """Invoice, bill, or receipt reference number exactly as printed."""

    transaction_date: Optional[str] = None
    """Date normalized to YYYY-MM-DD. Parse DD/MM/YYYY, MM-DD-YYYY, etc."""

    transaction_time: Optional[str] = None
    """Time as printed, e.g. '18:42'."""

    category: Optional[str] = None
    """One of the allowed expense categories."""

    currency: Optional[str] = None
    """ISO 4217 currency code inferred from symbol or country context.
    '₹' or 'Rs' → 'INR'. '$' → 'USD'. '€' → 'EUR'. '£' → 'GBP'.
    If the merchant is in India, default to INR unless another currency is explicit."""

    payment_method: Optional[str] = None
    """e.g. 'Cash', 'Credit Card', 'UPI', 'Debit Card'. Null if not stated."""

    line_items: Optional[List[LineItem]] = None
    """Every individual product or service line. Must not be empty if items are visible."""

    subtotal: Optional[float] = None
    """Sum of all line item totals before discount and tax."""

    discount_amount: Optional[float] = None
    """Total discount as a positive number, e.g. 50.00 for a -50 discount."""

    tax_breakdown: Optional[List[TaxBreakdown]] = None
    """Each tax component listed separately (CGST, SGST, VAT, etc.)."""

    tax_amount: Optional[float] = None
    """Total tax = sum of all tax_breakdown amounts."""

    total_amount: Optional[float] = None
    """Final amount paid = subtotal - discount + tax. This must always be populated
    if a grand total is visible anywhere on the receipt."""

    confidence_score: Optional[float] = None
    """Float 0.0–1.0. Reduce if totals are inconsistent or fields are ambiguous."""