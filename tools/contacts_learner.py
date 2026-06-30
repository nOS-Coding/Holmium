"""Learns contacts from email sender info — called after email_fetch_inbox."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

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


@register_tool(
    "learn_from_email",
    "Extract sender info from an email and upsert into contacts.",
    params_schema={
        "type": "object",
        "properties": {
            "sender_name": {
                "type": "string",
                "description": "Display name of the email sender",
            },
            "sender_email": {
                "type": "string",
                "description": "Email address of the sender",
            },
        },
        "required": ["sender_name", "sender_email"],
    },
)
def learn_from_email(sender_name: str, sender_email: str) -> Optional[int]:
    """Upsert a contact from email sender info. Returns contact ID or None."""
    if not sender_email:
        return None

    conn = _get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM contacts WHERE email = ?", (sender_email,)
        ).fetchone()

        if existing:
            if sender_name and sender_name != existing["name"]:
                conn.execute(
                    "UPDATE contacts SET name = ?, notes = COALESCE(notes, '') || ' | Auto-learned from email' WHERE id = ?",
                    (sender_name, existing["id"]),
                )
                conn.commit()
            return existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO contacts (name, email, notes) VALUES (?, ?, 'Auto-learned from email')",
                (sender_name or sender_email, sender_email),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()
