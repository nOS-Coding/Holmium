"""Background asyncio loop that executes due scheduler tasks every minute."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..tools.executor import execute_tool
from ..memory.sqlite_store import SQLiteStore
from .logger import get_logger
from .scheduler import TaskScheduler
from .proactive import ProactiveEngine
from .alerts import send_alert

logger = get_logger("scheduler_runner")

_PROACTIVE_INTERVAL = 15  # every 15th iteration = every 15 minutes


def _check_reminders() -> None:
    """Send notifications for events that are due for reminder."""
    try:
        store = SQLiteStore()
        now = datetime.now(timezone.utc)
        past = (now - timedelta(hours=1)).isoformat()
        future_24h = (now + timedelta(hours=24)).isoformat()
        events = store.event_list(start_date=past, end_date=future_24h)
        now_ts = now.timestamp()
        for ev in events:
            if ev["status"] != "confirmed":
                continue
            try:
                start_ts = datetime.fromisoformat(ev["start_time"]).timestamp()
            except (ValueError, TypeError):
                continue
            mins_before = ev["reminder_minutes"] or 15
            reminder_ts = start_ts - (mins_before * 60)
            if 0 <= (now_ts - reminder_ts) < 60:
                title = f"Reminder: {ev['title']}"
                asyncio.create_task(send_alert(title, ev.get("description", "") or title))
                logger.info("Sent reminder: %s", ev["title"])
    except Exception as exc:
        logger.exception("Reminder check failed: %s", exc)


class SchedulerRunner:
    def __init__(
        self,
        scheduler: TaskScheduler,
    ) -> None:
        self._scheduler = scheduler
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._proactive = ProactiveEngine()
        self._proactive_countdown = 0

    async def run(self) -> None:
        self._running = True
        logger.info("Scheduler runner started")
        while self._running:
            try:
                due = self._scheduler.get_due_tasks()
                for task in due:
                    logger.info("Executing scheduled task: %s — %s", task["id"], task["description"][:60])
                    for tool_call in task.get("tool_calls", []):
                        try:
                            result = execute_tool(tool_call.get("name", ""), tool_call.get("params", {}))
                            logger.debug("Tool %s returned: %s", tool_call.get("name"), str(result)[:200])
                        except Exception as exc:
                            logger.error("Scheduled tool %s failed: %s", tool_call.get("name"), exc)
                    self._scheduler.mark_run(task["id"])

                _check_reminders()

                self._proactive_countdown += 1
                if self._proactive_countdown >= _PROACTIVE_INTERVAL:
                    self._proactive_countdown = 0
                    findings = await self._proactive.run_cycle()
                    if findings:
                        logger.info("Proactive checks found: %s", "; ".join(findings))
            except Exception as exc:
                logger.exception("Scheduler runner iteration error: %s", exc)
            await asyncio.sleep(60)
        logger.info("Scheduler runner stopped")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler runner stopped")
