"""Contacts CRUD tool — SQLite-backed."""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.registry import register_tool

DB_PATH = Path("/var/holmium/memory/facts.db")


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


@register_tool(
    "contact_add",
    "Add a new contact to the address book.",
    params_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Contact name"},
            "email": {"type": "string", "description": "Email address"},
            "phone": {"type": "string", "description": "Phone number"},
            "notes": {"type": "string", "description": "Notes about the contact"},
        },
        "required": ["name"],
    },
)
def contact_add(
    name: str,
    email: str = "",
    phone: str = "",
    notes: str = "",
) -> int:
    """Add a contact and return the new ID."""
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO contacts (name, email, phone, notes) VALUES (?, ?, ?, ?)",
            (name, email or None, phone or None, notes or None),
        )
        conn.commit()
        return cur.lastrowid or 0
    finally:
        conn.close()


@register_tool(
    "contact_get",
    "Get a contact by ID.",
    params_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Contact ID"},
        },
        "required": ["id"],
    },
)
def contact_get(id: int) -> Dict[str, Any]:
    """Retrieve a single contact by ID."""
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM contacts WHERE id = ?", (id,)).fetchone()
        return _row_to_dict(row) if row else {}
    finally:
        conn.close()


@register_tool(
    "contact_list",
    "List all contacts.",
)
def contact_list() -> List[Dict[str, Any]]:
    """Return all contacts."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM contacts ORDER BY name").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


@register_tool(
    "contact_update",
    "Update fields on an existing contact.",
    params_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Contact ID to update"},
            "name": {"type": "string", "description": "New name"},
            "email": {"type": "string", "description": "New email"},
            "phone": {"type": "string", "description": "New phone"},
            "notes": {"type": "string", "description": "New notes"},
        },
        "required": ["id"],
    },
)
def contact_update(id: int, **kwargs: Any) -> bool:
    """Update a contact's fields. Only provided keyword args are updated."""
    allowed = {"name", "email", "phone", "notes"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return False

    conn = _get_connection()
    try:
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [id]
        conn.execute(f"UPDATE contacts SET {sets} WHERE id = ?", values)
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


@register_tool(
    "contact_delete",
    "Delete a contact by ID.",
    params_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Contact ID to delete"},
        },
        "required": ["id"],
    },
)
def contact_delete(id: int) -> bool:
    """Remove a contact by ID."""
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM contacts WHERE id = ?", (id,))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


@register_tool(
    "contact_search",
    "Search contacts by name, email, phone, or notes.",
    params_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term"},
        },
        "required": ["query"],
    },
)
def contact_search(query: str) -> List[Dict[str, Any]]:
    """Search contacts with LIKE on name, email, phone, notes."""
    conn = _get_connection()
    try:
        pattern = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM contacts WHERE name LIKE ? OR email LIKE ? OR phone LIKE ? OR notes LIKE ? ORDER BY name",
            (pattern, pattern, pattern, pattern),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
