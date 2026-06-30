"""Proactive intelligence — background checks and context-aware suggestions."""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from .logger import get_logger
from ..memory.sqlite_store import SQLiteStore

logger = get_logger("proactive")

_CHECK_INTERVAL = 900  # 15 minutes


class ProactiveEngine:
    """Background engine that runs periodic checks and surfaces proactive context.

    Integrated into the scheduler runner — runs every 15 minutes.
    """

    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self._store = store or SQLiteStore()
        self._last_checks: dict[str, str] = {}
        self._findings: list[str] = []

    async def run_cycle(self) -> list[str]:
        """Run one proactive check cycle. Returns new findings since last check."""
        self._findings = []
        await self._check_overdue_todos()
        await self._check_completed_plans()
        await self._check_patterns()
        if self._findings:
            asyncio.create_task(self._speak_findings())
        return self._findings

    async def _speak_findings(self) -> None:
        """Synthesize findings as speech and send to phone via ntfy."""
        try:
            from ..tts.piper_tts import PiperTTS
            from ..notifications.ntfy_push import send_audio_notification
            text = ". ".join(self._findings)
            tts = PiperTTS()
            wav = tts.synthesize(text)
            if wav and len(wav) > 44:
                send_audio_notification(
                    title="Holmium",
                    body=text[:200],
                    audio_bytes=wav,
                )
                logger.info("Sent proactive TTS to phone (%d bytes)", len(wav))
        except Exception as exc:
            logger.warning("Failed to send proactive TTS: %s", exc)

    async def _check_overdue_todos(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        todolist = self._store.todos_list(include_done=False)
        overdue = [t for t in todolist if t.get("due_date") and t["due_date"] < now]
        if overdue and self._has_new("overdue_todos", str(len(overdue))):
            count = len(overdue)
            titles = ", ".join(t["title"][:40] for t in overdue[:3])
            finding = f"You have {count} overdue todo(s): {titles}"
            self._findings.append(finding)
            logger.info("Proactive: %s", finding)

    async def _check_completed_plans(self) -> None:
        count = self._store.plan_completed_count()
        if count > 0 and self._has_new("completed_plans", str(count)):
            finding = f"You've completed {count} plans since I started tracking. Want a summary?"
            self._findings.append(finding)
            logger.info("Proactive: %s", finding)

    async def _check_patterns(self) -> None:
        facts = self._store.fact_list()
        fact_keys = {f["key"]: f["value"] for f in facts}
        user_name = fact_keys.get("user_name", "there")

        if "morning_greeting" not in self._last_checks:
            hour = datetime.now(timezone.utc).hour
            if 6 <= hour < 9:
                self._findings.append(
                    f"Good morning, {user_name}. I've been monitoring all night — "
                    "nothing unusual to report."
                )
                self._last_checks["morning_greeting"] = "done"
                logger.info("Proactive: morning greeting for %s", user_name)

    def _has_new(self, check_name: str, value: str) -> bool:
        if self._last_checks.get(check_name) != value:
            self._last_checks[check_name] = value
            return True
        return False

    def get_proactive_context(self) -> str:
        if not self._findings:
            return ""
        return "### Holmium's Observations\n" + "\n".join(f"- {f}" for f in self._findings[-3:])
