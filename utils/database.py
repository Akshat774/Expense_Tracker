"""
SQLite database layer for FinAI expense tracker.
"""

import sqlite3
import json
import logging
import csv
import io
from datetime import datetime
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = "expenses.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_name TEXT,
                transaction_date TEXT,
                transaction_time TEXT,
                category TEXT,
                currency TEXT,
                payment_method TEXT,
                subtotal REAL,
                discount_amount REAL,
                tax_amount REAL,
                total_amount REAL,
                confidence_score REAL,
                line_items TEXT,
                tax_breakdown TEXT,
                merchant_address TEXT,
                invoice_number TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    logger.info("Database initialized.")


def insert_expense(data: Dict[str, Any]) -> int:
    """Insert a new expense record. Returns the new row ID."""
    line_items = data.get("line_items", [])
    if not isinstance(line_items, str):
        line_items = json.dumps([
            item if isinstance(item, dict) else item.model_dump()
            for item in line_items
        ])

    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO expenses (
                merchant_name, transaction_date, transaction_time, category, currency,
                payment_method, subtotal, discount_amount, tax_amount,
                total_amount, confidence_score, line_items, tax_breakdown,
                merchant_address, invoice_number
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("merchant_name"),
            data.get("transaction_date"),
            data.get("transaction_time"),
            data.get("category"),
            data.get("currency"),
            data.get("payment_method"),
            data.get("subtotal"),
            data.get("discount_amount"),
            data.get("tax_amount"),
            data.get("total_amount"),
            data.get("confidence_score"),
            line_items,
            json.dumps(data.get("tax_breakdown") or []),
            data.get("merchant_address"),
            data.get("invoice_number"),
        ))
        conn.commit()
        return cursor.lastrowid


def get_all_expenses() -> List[Dict]:
    """Return all expenses as a list of dicts."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses ORDER BY transaction_date DESC, id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_expense_by_id(expense_id: int) -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    return dict(row) if row else None


def update_expense(expense_id: int, data: Dict[str, Any]) -> bool:
    fields = ["merchant_name", "transaction_date", "category", "currency",
              "payment_method", "subtotal", "discount_amount", "tax_amount",
              "total_amount", "confidence_score"]
    updates = {k: data[k] for k in fields if k in data}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [expense_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE expenses SET {set_clause} WHERE id = ?", values)
        conn.commit()
    return True


def delete_expense(expense_id: int) -> bool:
    with get_connection() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
    return True


def search_expenses(query: str) -> List[Dict]:
    q = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM expenses
            WHERE merchant_name LIKE ? OR category LIKE ?
            ORDER BY transaction_date DESC
        """, (q, q)).fetchall()
    return [dict(r) for r in rows]


def filter_expenses(
    categories: Optional[List[str]] = None,
    month: Optional[str] = None,
) -> List[Dict]:
    clauses, params = [], []
    if categories:
        placeholders = ",".join("?" * len(categories))
        clauses.append(f"category IN ({placeholders})")
        params.extend(categories)
    if month:
        clauses.append("strftime('%Y-%m', transaction_date) = ?")
        params.append(month)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM expenses {where} ORDER BY transaction_date DESC",
            params
        ).fetchall()
    return [dict(r) for r in rows]


def export_csv() -> str:
    """Return all expenses as a CSV string."""
    rows = get_all_expenses()
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def reset_database() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM expenses")
        conn.commit()
    logger.warning("Database reset: all expenses deleted.")


def get_database_stats() -> Dict[str, Any]:
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        total = conn.execute("SELECT SUM(total_amount) FROM expenses").fetchone()[0] or 0.0
        earliest = conn.execute("SELECT MIN(transaction_date) FROM expenses").fetchone()[0]
        latest = conn.execute("SELECT MAX(transaction_date) FROM expenses").fetchone()[0]
    return {"count": count, "total": total, "earliest": earliest, "latest": latest}