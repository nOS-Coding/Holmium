"""Session management — create, get, close, list sessions with inactivity cleanup."""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .logger import get_logger

logger = get_logger("sessions")

_SESSIONS_DIR = Path("/var/holmium/sessions")
_MAX_MESSAGES = 50


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Session:
    session_id: str
    start_time: str
    client_type: str
    last_activity: str
    messages: list = field(default_factory=list)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def create_session(self, client_type: str) -> Session:
        session_id = uuid.uuid4().hex[:16]
        now = _now_iso()
        session = Session(
            session_id=session_id,
            start_time=now,
            client_type=client_type,
            last_activity=now,
            messages=[],
        )
        self._sessions[session_id] = session
        logger.info("Session created: %s (%s)", session_id[:8], client_type)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session:
            session.last_activity = _now_iso()
        return session

    def close_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            logger.warning("Session not found: %s", session_id)
            return

        try:
            session_dir = _SESSIONS_DIR
            session_dir.mkdir(parents=True, exist_ok=True)
            filepath = session_dir / f"{session_id}.json"
            data = asdict(session)
            filepath.write_text(json.dumps(data, indent=2))
            logger.info("Session saved: %s (%d turns)", session_id[:8], len(session.messages))
        except OSError as exc:
            logger.error("Failed to save session %s: %s", session_id, exc)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get_session(session_id)
        if session is None:
            return
        session.messages.append({"role": role, "content": content, "timestamp": _now_iso()})
        if len(session.messages) > _MAX_MESSAGES:
            session.messages = session.messages[-_MAX_MESSAGES:]
        session.last_activity = _now_iso()

    def get_recent_messages(self, n: int = 20) -> list[dict]:
        all_messages: list[dict] = []
        for session in self._sessions.values():
            for msg in session.messages:
                all_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "session_id": session.session_id,
                    "client_type": session.client_type,
                    "timestamp": msg.get("timestamp", ""),
                })
        all_messages.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
        return all_messages[:n]

    def session_list(self, n: int = 20) -> list[dict]:
        active: list[dict] = []
        for session in self._sessions.values():
            active.append({
                "session_id": session.session_id,
                "start_time": session.start_time,
                "client_type": session.client_type,
                "last_activity": session.last_activity,
                "message_count": len(session.messages),
            })
        active.sort(key=lambda s: s["last_activity"], reverse=True)

        archived: list[dict] = []
        try:
            for f in sorted(_SESSIONS_DIR.glob("*.json"), reverse=True):
                try:
                    data = json.loads(f.read_text())
                    archived.append({
                        "session_id": data.get("session_id", f.stem),
                        "start_time": data.get("start_time", ""),
                        "client_type": data.get("client_type", ""),
                        "last_activity": data.get("last_activity", ""),
                        "message_count": len(data.get("messages", [])),
                    })
                except (json.JSONDecodeError, OSError):
                    continue
        except OSError:
            pass

        combined = active + archived
        combined.sort(key=lambda s: s.get("last_activity", ""), reverse=True)
        return combined[:n]

    def session_get(self, session_id: str) -> Optional[dict]:
        session = self._sessions.get(session_id)
        if session:
            return asdict(session)

        filepath = _SESSIONS_DIR / f"{session_id}.json"
        if filepath.exists():
            try:
                return json.loads(filepath.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        return None

    def cleanup_inactive(self, timeout_minutes: int = 30) -> int:
        now = datetime.now(timezone.utc)
        cleaned = 0
        inactive_ids: list[str] = []
        for sid, session in self._sessions.items():
            try:
                last = datetime.fromisoformat(session.last_activity)
                if (now - last).total_seconds() > timeout_minutes * 60:
                    inactive_ids.append(sid)
            except (ValueError, TypeError):
                inactive_ids.append(sid)

        for sid in inactive_ids:
            self.close_session(sid)
            cleaned += 1

        if cleaned:
            logger.info("Cleaned up %d inactive sessions", cleaned)
        return cleaned
