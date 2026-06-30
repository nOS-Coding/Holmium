"""Usage stats tracker — record messages, tool use, sessions, weekly reports."""

import json
from datetime import datetime, timezone
from typing import Optional

from ..memory.sqlite_store import SQLiteStore
from .logger import get_logger

logger = get_logger("usage_stats")


class UsageStats:
    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self._store = store or SQLiteStore()
        self._today: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._session_topics: list[str] = []

    def record_message(self) -> None:
        stats = self._get_or_create_today()
        stats["messages_sent"] = stats.get("messages_sent", 0) + 1
        self._save_today(stats)

    def record_tool_use(self, tool_name: str) -> None:
        stats = self._get_or_create_today()
        tools_used = stats.get("tools_used", "")
        tools = set()
        if tools_used:
            tools = set(json.loads(tools_used))
        tools.add(tool_name)
        stats["tools_used"] = json.dumps(list(tools))
        self._save_today(stats)

    def record_session(self) -> None:
        stats = self._get_or_create_today()
        stats["sessions_count"] = stats.get("sessions_count", 0) + 1
        self._save_today(stats)

    def end_session(self, topics: list[str]) -> None:
        self._session_topics.extend(topics)
        stats = self._get_or_create_today()
        existing_topics = set()
        if stats.get("top_topics"):
            try:
                existing_topics = set(json.loads(stats["top_topics"]))
            except (json.JSONDecodeError, TypeError):
                pass
        existing_topics.update(topics)
        stats["top_topics"] = json.dumps(list(existing_topics)[:20])
        self._save_today(stats)

    def weekly_report(self) -> str:
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = self._store.usage_stats_weekly_report(end)
        if not rows:
            return "No usage data available."

        total_messages = sum(r.get("messages_sent", 0) for r in rows)
        total_sessions = sum(r.get("sessions_count", 0) for r in rows)
        all_tools: set[str] = set()
        all_topics: set[str] = set()
        for r in rows:
            if r.get("tools_used"):
                try:
                    all_tools.update(json.loads(r["tools_used"]))
                except (json.JSONDecodeError, TypeError):
                    pass
            if r.get("top_topics"):
                try:
                    all_topics.update(json.loads(r["top_topics"]))
                except (json.JSONDecodeError, TypeError):
                    pass

        lines = [
            f"Weekly Report ({rows[0]['date']} - {rows[-1]['date']})",
            f"Active Days: {len(rows)}",
            f"Total Messages: {total_messages}",
            f"Total Sessions: {total_sessions}",
        ]
        if all_tools:
            lines.append(f"Tools Used: {', '.join(sorted(all_tools))}")
        if all_topics:
            lines.append(f"Topics: {', '.join(sorted(all_topics)[:10])}")

        return "\n".join(lines)

    def _get_or_create_today(self) -> dict:
        self._today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = self._store.usage_stats_get(self._today)
        if stats is None:
            return {
                "date": self._today,
                "messages_sent": 0,
                "tools_used": json.dumps([]),
                "top_topics": json.dumps([]),
                "sessions_count": 0,
            }
        return stats

    def _save_today(self, stats: dict) -> None:
        self._store.usage_stats_upsert(
            date=self._today,
            messages_sent=stats.get("messages_sent", 0),
            tools_used=stats.get("tools_used", json.dumps([])),
            top_topics=stats.get("top_topics", json.dumps([])),
            sessions_count=stats.get("sessions_count", 0),
        )
