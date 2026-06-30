import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS facts (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_history (
    action_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    parameters TEXT,
    result_summary TEXT,
    session_id TEXT,
    success INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    tags TEXT
);

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    due_date TEXT,
    priority TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    shares REAL NOT NULL,
    price REAL NOT NULL,
    value REAL NOT NULL,
    gain_loss REAL,
    gain_loss_pct REAL
);

CREATE TABLE IF NOT EXISTS api_keys (
    key_hash TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used TEXT,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS usage_stats (
    date TEXT PRIMARY KEY,
    hours_active REAL NOT NULL DEFAULT 0,
    messages_sent INTEGER NOT NULL DEFAULT 0,
    tools_used TEXT,
    top_topics TEXT,
    sessions_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS active_plans (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    all_day INTEGER NOT NULL DEFAULT 0,
    location TEXT,
    recurrence TEXT,
    reminder_minutes INTEGER DEFAULT 15,
    tag TEXT,
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self, db_path: str = "/var/holmium/memory/facts.db") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA_SQL)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def _executemany(self, sql: str, seq: list[tuple]) -> sqlite3.Cursor:
        return self._conn.executemany(sql, seq)

    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        row = self._conn.execute(sql, params).fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in self._conn.execute(sql, params).description]
        return dict(zip(columns, row))

    def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = self._conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # ── facts ──────────────────────────────────────────────────────────────

    def fact_set(self, key: str, value: str) -> None:
        now = _iso_now()
        with self._lock:
            self._execute(
                """INSERT INTO facts (key, value, created_at, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       value = excluded.value,
                       updated_at = excluded.updated_at""",
                (key, value, now, now),
            )

    def fact_get(self, key: str) -> Optional[dict]:
        return self._fetchone("SELECT * FROM facts WHERE key = ?", (key,))

    def fact_delete(self, key: str) -> bool:
        with self._lock:
            c = self._execute("DELETE FROM facts WHERE key = ?", (key,))
            return c.rowcount > 0

    def fact_list(self) -> list[dict]:
        return self._fetchall("SELECT * FROM facts ORDER BY updated_at DESC")

    def fact_search(self, query: str) -> list[dict]:
        pattern = f"%{query}%"
        return self._fetchall(
            "SELECT * FROM facts WHERE key LIKE ? OR value LIKE ? ORDER BY updated_at DESC",
            (pattern, pattern),
        )

    # ── action_history ─────────────────────────────────────────────────────

    def log_action(
        self,
        action_id: str,
        timestamp: str,
        tool_name: str,
        parameters: Optional[str],
        result_summary: Optional[str],
        session_id: Optional[str],
        success: bool,
    ) -> None:
        with self._lock:
            self._execute(
                """INSERT INTO action_history
                   (action_id, timestamp, tool_name, parameters, result_summary, session_id, success)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (action_id, timestamp, tool_name, parameters, result_summary, session_id, int(success)),
            )

    def get_recent_actions(self, n: int = 50) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM action_history ORDER BY timestamp DESC LIMIT ?", (n,)
        )

    def search_actions(self, query: str) -> list[dict]:
        pattern = f"%{query}%"
        return self._fetchall(
            """SELECT * FROM action_history
               WHERE tool_name LIKE ? OR result_summary LIKE ?
               ORDER BY timestamp DESC""",
            (pattern, pattern),
        )

    # ── notes ──────────────────────────────────────────────────────────────

    def notes_insert(self, title: str, content: str = "", tags: str = "") -> int:
        now = _iso_now()
        with self._lock:
            c = self._execute(
                "INSERT INTO notes (title, content, created_at, updated_at, tags) VALUES (?, ?, ?, ?, ?)",
                (title, content, now, now, tags),
            )
            return c.lastrowid

    def notes_get(self, note_id: int) -> Optional[dict]:
        return self._fetchone("SELECT * FROM notes WHERE id = ?", (note_id,))

    def notes_update(self, note_id: int, title: Optional[str] = None, content: Optional[str] = None, tags: Optional[str] = None) -> bool:
        fields = []
        params: list[Any] = []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if content is not None:
            fields.append("content = ?")
            params.append(content)
        if tags is not None:
            fields.append("tags = ?")
            params.append(tags)
        if not fields:
            return False
        fields.append("updated_at = ?")
        params.append(_iso_now())
        params.append(note_id)
        with self._lock:
            c = self._execute(
                f"UPDATE notes SET {', '.join(fields)} WHERE id = ?", tuple(params)
            )
            return c.rowcount > 0

    def notes_delete(self, note_id: int) -> bool:
        with self._lock:
            c = self._execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return c.rowcount > 0

    def notes_list(self) -> list[dict]:
        return self._fetchall("SELECT * FROM notes ORDER BY updated_at DESC")

    def notes_search(self, query: str) -> list[dict]:
        pattern = f"%{query}%"
        return self._fetchall(
            """SELECT * FROM notes
               WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
               ORDER BY updated_at DESC""",
            (pattern, pattern, pattern),
        )

    # ── todos ──────────────────────────────────────────────────────────────

    def todos_insert(self, title: str, due_date: str = "", priority: str = "medium") -> int:
        now = _iso_now()
        with self._lock:
            c = self._execute(
                "INSERT INTO todos (title, due_date, priority, created_at) VALUES (?, ?, ?, ?)",
                (title, due_date or None, priority, now),
            )
            return c.lastrowid

    def todos_get(self, todo_id: int) -> Optional[dict]:
        return self._fetchone("SELECT * FROM todos WHERE id = ?", (todo_id,))

    def todos_update(self, todo_id: int, **kwargs: Any) -> bool:
        allowed = {"title", "done", "due_date", "priority", "completed_at"}
        fields = []
        params: list[Any] = []
        for k, v in kwargs.items():
            if k in allowed:
                fields.append(f"{k} = ?")
                params.append(v)
        if not fields:
            return False
        params.append(todo_id)
        with self._lock:
            c = self._execute(
                f"UPDATE todos SET {', '.join(fields)} WHERE id = ?", tuple(params)
            )
            return c.rowcount > 0

    def todos_delete(self, todo_id: int) -> bool:
        with self._lock:
            c = self._execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            return c.rowcount > 0

    def todos_list(self, include_done: bool = False) -> list[dict]:
        if include_done:
            return self._fetchall("SELECT * FROM todos ORDER BY created_at DESC")
        return self._fetchall(
            "SELECT * FROM todos WHERE done = 0 ORDER BY created_at DESC"
        )

    def todos_list_overdue(self) -> list[dict]:
        now = _iso_now()
        return self._fetchall(
            """SELECT * FROM todos
               WHERE done = 0 AND due_date IS NOT NULL AND due_date < ?
               ORDER BY due_date ASC""",
            (now,),
        )

    def todos_mark_done(self, todo_id: int) -> bool:
        now = _iso_now()
        with self._lock:
            c = self._execute(
                "UPDATE todos SET done = 1, completed_at = ? WHERE id = ?", (now, todo_id)
            )
            return c.rowcount > 0

    # ── contacts ───────────────────────────────────────────────────────────

    def contacts_insert(self, name: str, email: str = "", phone: str = "", notes: str = "") -> int:
        now = _iso_now()
        with self._lock:
            c = self._execute(
                "INSERT INTO contacts (name, email, phone, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                (name, email or None, phone or None, notes or None, now),
            )
            return c.lastrowid

    def contacts_get(self, contact_id: int) -> Optional[dict]:
        return self._fetchone("SELECT * FROM contacts WHERE id = ?", (contact_id,))

    def contacts_update(self, contact_id: int, **kwargs: Any) -> bool:
        allowed = {"name", "email", "phone", "notes"}
        fields = []
        params: list[Any] = []
        for k, v in kwargs.items():
            if k in allowed:
                fields.append(f"{k} = ?")
                params.append(v)
        if not fields:
            return False
        params.append(contact_id)
        with self._lock:
            c = self._execute(
                f"UPDATE contacts SET {', '.join(fields)} WHERE id = ?", tuple(params)
            )
            return c.rowcount > 0

    def contacts_delete(self, contact_id: int) -> bool:
        with self._lock:
            c = self._execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
            return c.rowcount > 0

    def contacts_list(self) -> list[dict]:
        return self._fetchall("SELECT * FROM contacts ORDER BY name ASC")

    def contacts_search(self, query: str) -> list[dict]:
        pattern = f"%{query}%"
        return self._fetchall(
            """SELECT * FROM contacts
               WHERE name LIKE ? OR email LIKE ? OR phone LIKE ? OR notes LIKE ?
               ORDER BY name ASC""",
            (pattern, pattern, pattern, pattern),
        )

    # ── portfolio_snapshots ────────────────────────────────────────────────

    def portfolio_snapshot_add(
        self,
        snapshot_date: str,
        ticker: str,
        shares: float,
        price: float,
        value: float,
        gain_loss: Optional[float] = None,
        gain_loss_pct: Optional[float] = None,
    ) -> int:
        with self._lock:
            c = self._execute(
                """INSERT INTO portfolio_snapshots
                   (snapshot_date, ticker, shares, price, value, gain_loss, gain_loss_pct)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (snapshot_date, ticker, shares, price, value, gain_loss, gain_loss_pct),
            )
            return c.lastrowid

    def portfolio_snapshot_get(self, snapshot_id: int) -> Optional[dict]:
        return self._fetchone("SELECT * FROM portfolio_snapshots WHERE id = ?", (snapshot_id,))

    def portfolio_snapshot_history(self, ticker: str, n: int = 100) -> list[dict]:
        return self._fetchall(
            """SELECT * FROM portfolio_snapshots
               WHERE ticker = ? ORDER BY snapshot_date DESC LIMIT ?""",
            (ticker, n),
        )

    def portfolio_snapshot_list(self, n: int = 100) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM portfolio_snapshots ORDER BY snapshot_date DESC LIMIT ?", (n,)
        )

    # ── active_plans ───────────────────────────────────────────────────────

    def plan_save(self, plan: dict) -> None:
        with self._lock:
            self._execute(
                """INSERT INTO active_plans (id, description, steps_json, current_step, status, result, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       current_step = excluded.current_step,
                       status = excluded.status,
                       result = excluded.result,
                       updated_at = excluded.updated_at""",
                (
                    plan["id"],
                    plan["description"],
                    plan["steps_json"],
                    plan["current_step"],
                    plan["status"],
                    plan.get("result"),
                    plan["created_at"],
                    plan["updated_at"],
                ),
            )

    def plan_get(self, plan_id: str) -> Optional[dict]:
        return self._fetchone("SELECT * FROM active_plans WHERE id = ?", (plan_id,))

    def plan_get_active(self) -> Optional[dict]:
        return self._fetchone(
            "SELECT * FROM active_plans WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
        )

    def plan_list(self) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM active_plans ORDER BY created_at DESC LIMIT 20"
        )

    def plan_completed_count(self) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) as count FROM active_plans WHERE status = 'completed'"
        )
        return row["count"] if row else 0

    # ── api_keys ───────────────────────────────────────────────────────────

    def api_key_set(self, key_hash: str, label: str) -> None:
        now = _iso_now()
        with self._lock:
            self._execute(
                """INSERT INTO api_keys (key_hash, label, created_at, enabled)
                   VALUES (?, ?, ?, 1)
                   ON CONFLICT(key_hash) DO UPDATE SET
                       label = excluded.label,
                       enabled = 1""",
                (key_hash, label, now),
            )

    def api_key_get(self, key_hash: str) -> Optional[dict]:
        return self._fetchone("SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,))

    def api_key_list(self, only_enabled: bool = True) -> list[dict]:
        if only_enabled:
            return self._fetchall(
                "SELECT * FROM api_keys WHERE enabled = 1 ORDER BY created_at DESC"
            )
        return self._fetchall("SELECT * FROM api_keys ORDER BY created_at DESC")

    def api_key_revoke(self, key_hash: str) -> bool:
        with self._lock:
            c = self._execute(
                "UPDATE api_keys SET enabled = 0 WHERE key_hash = ?", (key_hash,)
            )
            return c.rowcount > 0

    def api_key_touch(self, key_hash: str) -> None:
        now = _iso_now()
        with self._lock:
            self._execute(
                "UPDATE api_keys SET last_used = ? WHERE key_hash = ?", (now, key_hash)
            )

    # ── usage_stats ────────────────────────────────────────────────────────

    def usage_stats_upsert(
        self,
        date: str,
        hours_active: float = 0,
        messages_sent: int = 0,
        tools_used: str = "",
        top_topics: str = "",
        sessions_count: int = 0,
    ) -> None:
        with self._lock:
            self._execute(
                """INSERT INTO usage_stats (date, hours_active, messages_sent, tools_used, top_topics, sessions_count)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                       hours_active = excluded.hours_active,
                       messages_sent = excluded.messages_sent,
                       tools_used = excluded.tools_used,
                       top_topics = excluded.top_topics,
                       sessions_count = excluded.sessions_count""",
                (date, hours_active, messages_sent, tools_used, top_topics, sessions_count),
            )

    def usage_stats_get(self, date: str) -> Optional[dict]:
        return self._fetchone("SELECT * FROM usage_stats WHERE date = ?", (date,))

    def usage_stats_weekly_report(self, end_date: str) -> list[dict]:
        return self._fetchall(
            """SELECT * FROM usage_stats
               WHERE date <= ?
               ORDER BY date DESC LIMIT 7""",
            (end_date,),
        )

    # ── calendar ───────────────────────────────────────────────────────────

    def event_insert(
        self,
        title: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: str = "",
        location: str = "",
        all_day: bool = False,
        recurrence: str = "",
        reminder_minutes: int = 15,
        tag: str = "",
    ) -> int:
        now = _iso_now()
        with self._lock:
            c = self._execute(
                """INSERT INTO calendar_events
                   (title, description, start_time, end_time, all_day, location, recurrence, reminder_minutes, tag, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, description, start_time, end_time, int(all_day), location, recurrence or None, reminder_minutes, tag, now, now),
            )
            return c.lastrowid

    def event_get(self, event_id: int) -> Optional[dict]:
        return self._fetchone("SELECT * FROM calendar_events WHERE id = ?", (event_id,))

    def event_update(self, event_id: int, **kwargs) -> bool:
        allowed = {"title", "description", "start_time", "end_time", "all_day", "location", "recurrence", "reminder_minutes", "tag", "status"}
        fields = []
        params: list = []
        for k, v in kwargs.items():
            if k in allowed:
                fields.append(f"{k} = ?")
                params.append(v)
        if not fields:
            return False
        fields.append("updated_at = ?")
        params.append(_iso_now())
        params.append(event_id)
        with self._lock:
            c = self._execute(
                f"UPDATE calendar_events SET {', '.join(fields)} WHERE id = ?", tuple(params)
            )
            return c.rowcount > 0

    def event_delete(self, event_id: int) -> bool:
        with self._lock:
            c = self._execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
            return c.rowcount > 0

    def event_list(self, start_date: str = "", end_date: str = "") -> list[dict]:
        if start_date and end_date:
            return self._fetchall(
                "SELECT * FROM calendar_events WHERE start_time >= ? AND start_time <= ? ORDER BY start_time ASC",
                (start_date, end_date),
            )
        return self._fetchall(
            "SELECT * FROM calendar_events ORDER BY start_time ASC LIMIT 50"
        )

    def event_search(self, query: str) -> list[dict]:
        pattern = f"%{query}%"
        return self._fetchall(
            """SELECT * FROM calendar_events
               WHERE title LIKE ? OR description LIKE ? OR location LIKE ? OR tag LIKE ?
               ORDER BY start_time ASC""",
            (pattern, pattern, pattern, pattern),
        )

    def event_upcoming(self, n: int = 10) -> list[dict]:
        now = _iso_now()
        return self._fetchall(
            "SELECT * FROM calendar_events WHERE start_time >= ? AND status = 'confirmed' ORDER BY start_time ASC LIMIT ?",
            (now, n),
        )

    def event_due_reminders(self) -> list[dict]:
        now = _iso_now()
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        return self._fetchall(
            """SELECT * FROM calendar_events
               WHERE start_time BETWEEN ? AND ?
               AND status = 'confirmed'
               ORDER BY start_time ASC""",
            (past, now),
        )
