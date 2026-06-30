"""Notes and todos CRUD tools — SQLite-backed."""

import sqlite3
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
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            tags TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            due_date TEXT,
            priority TEXT DEFAULT 'medium',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        )
    """)
    conn.commit()
    return conn


@register_tool(
    "note_add",
    "Add a new note with title, content, and optional tags.",
    params_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Note title"},
            "content": {"type": "string", "description": "Note body content"},
            "tags": {"type": "string", "description": "Comma-separated tags"},
        },
        "required": ["title"],
    },
)
def note_add(title: str, content: str = "", tags: str = "") -> int:
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO notes (title, content, tags) VALUES (?, ?, ?)",
            (title, content, tags or None),
        )
        conn.commit()
        return cur.lastrowid or 0
    finally:
        conn.close()


@register_tool(
    "note_get",
    "Get a note by ID.",
    params_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Note ID"},
        },
        "required": ["id"],
    },
)
def note_get(id: int) -> Dict[str, Any]:
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (id,)).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


@register_tool(
    "note_list",
    "List all notes.",
)
def note_list() -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM notes ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@register_tool(
    "note_update",
    "Update a note's title, content, or tags.",
    params_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Note ID"},
            "title": {"type": "string"},
            "content": {"type": "string"},
            "tags": {"type": "string"},
        },
        "required": ["id"],
    },
)
def note_update(id: int, **kwargs: Any) -> bool:
    allowed = {"title", "content", "tags"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return False
    conn = _get_connection()
    try:
        fields["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [id]
        conn.execute(f"UPDATE notes SET {sets} WHERE id = ?", values)
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


@register_tool(
    "note_delete",
    "Delete a note by ID.",
    params_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Note ID"},
        },
        "required": ["id"],
    },
)
def note_delete(id: int) -> bool:
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM notes WHERE id = ?", (id,))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


@register_tool(
    "note_search",
    "Search notes by title and content.",
    params_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term"},
        },
        "required": ["query"],
    },
)
def note_search(query: str) -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        pattern = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC",
            (pattern, pattern),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@register_tool(
    "todo_add",
    "Add a new todo item with optional due date and priority.",
    params_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Todo title"},
            "due_date": {"type": "string", "description": "Due date (ISO 8601 or YYYY-MM-DD)"},
            "priority": {"type": "string", "description": "Priority: low, medium, high", "enum": ["low", "medium", "high"]},
        },
        "required": ["title"],
    },
)
def todo_add(title: str, due_date: str = "", priority: str = "medium") -> int:
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO todos (title, due_date, priority) VALUES (?, ?, ?)",
            (title, due_date or None, priority),
        )
        conn.commit()
        return cur.lastrowid or 0
    finally:
        conn.close()


@register_tool(
    "todo_list",
    "List todos, optionally filtered by done status.",
    params_schema={
        "type": "object",
        "properties": {
            "done": {
                "type": "boolean",
                "description": "Filter by done status (null = all)",
            },
        },
        "required": [],
    },
)
def todo_list(done: Optional[bool] = None) -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        if done is not None:
            rows = conn.execute(
                "SELECT * FROM todos WHERE done = ? ORDER BY created_at DESC",
                (1 if done else 0,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM todos ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@register_tool(
    "todo_done",
    "Mark a todo as completed.",
    params_schema={
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "Todo ID"},
        },
        "required": ["id"],
    },
)
def todo_done(id: int) -> bool:
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE todos SET done = 1, completed_at = ? WHERE id = ?",
            (datetime.now().isoformat(), id),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


@register_tool(
    "todo_overdue",
    "List all overdue todos (past due date and not done).",
)
def todo_overdue() -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT * FROM todos WHERE done = 0 AND due_date IS NOT NULL AND due_date < ? ORDER BY due_date",
            (today,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
