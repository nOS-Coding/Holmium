"""Task scheduler — cron/ISO scheduling with JSON persistence."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .logger import get_logger

logger = get_logger("scheduler")

_SCHEDULER_FILE = Path("/var/holmium/scheduler.json")

try:
    from croniter import croniter
except ImportError:
    croniter = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskScheduler:
    def __init__(self, scheduler_file: Optional[Path] = None) -> None:
        self._file = scheduler_file or _SCHEDULER_FILE
        self._tasks: list[dict] = []
        self._load()

    def add_task(
        self,
        task_description: str,
        tool_calls: list,
        schedule: str,
        repeat: bool = False,
    ) -> str:
        task_id = uuid.uuid4().hex[:12]
        task: dict[str, Any] = {
            "id": task_id,
            "description": task_description,
            "tool_calls": tool_calls,
            "schedule": schedule,
            "repeat": repeat,
            "created_at": _now_iso(),
            "last_run": None,
            "next_run": self._compute_next(schedule),
            "enabled": True,
        }
        self._tasks.append(task)
        self._save()
        logger.info("Task added: %s — %s", task_id, task_description[:60])
        return task_id

    def list_tasks(self) -> list[dict]:
        return list(self._tasks)

    def cancel_task(self, task_id: str) -> bool:
        for task in self._tasks:
            if task["id"] == task_id:
                task["enabled"] = False
                self._save()
                logger.info("Task cancelled: %s", task_id)
                return True
        logger.warning("Task not found: %s", task_id)
        return False

    def get_due_tasks(self) -> list[dict]:
        now = _now_iso()
        due: list[dict] = []
        for task in self._tasks:
            if not task.get("enabled", True):
                continue
            next_run = task.get("next_run")
            if next_run and next_run <= now:
                due.append(task)
        return due

    def mark_run(self, task_id: str) -> None:
        for task in self._tasks:
            if task["id"] == task_id:
                task["last_run"] = _now_iso()
                if task.get("repeat"):
                    task["next_run"] = self._compute_next(task["schedule"])
                else:
                    task["enabled"] = False
                self._save()
                return

    def detect_scheduling_intent(self, message: str) -> Optional[dict]:
        import httpx
        from ..memory.sqlite_store import SQLiteStore

        sqlite_store = SQLiteStore()
        config = None
        try:
            from .config import HolmiumConfig
            config = HolmiumConfig.load()
        except Exception:
            pass

        socket_path = getattr(config, "vllm_socket", "/run/holmium/vllm.sock") if config else "/run/holmium/vllm.sock"

        prompt = f"""Analyze the following user message and determine if they want to schedule a task.
If yes, return JSON with "intent": "schedule", "description": "...", "schedule": "..." (cron or ISO datetime)
If no, return {{"intent": "none"}}

Message: {message}

Return ONLY valid JSON, nothing else."""

        try:
            transport = httpx.HTTPTransport(uds=socket_path)
            with httpx.Client(transport=transport, timeout=30) as client:
                resp = client.post(
                    "http://localhost/v1/chat/completions",
                    json={
                        "model": "default",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 256,
                        "temperature": 0.0,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data["choices"][0]["message"]["content"].strip()
                result = json.loads(raw)
                if result.get("intent") == "schedule":
                    return result
                return None
        except Exception as exc:
            logger.warning("Scheduling intent detection failed: %s", exc)
            return None

    def _compute_next(self, schedule: str) -> str:
        if croniter is not None and "/" in schedule or len(schedule.split()) >= 5:
            try:
                base = datetime.now(timezone.utc)
                it = croniter(schedule, base)
                return it.get_next(datetime).isoformat()
            except (ValueError, KeyError) as exc:
                logger.warning("Invalid cron expression '%s': %s", schedule, exc)
                return _now_iso()
        try:
            dt = datetime.fromisoformat(schedule)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            logger.warning("Invalid schedule format '%s', treating as immediate", schedule)
            return _now_iso()

    def _load(self) -> None:
        try:
            if self._file.exists():
                self._tasks = json.loads(self._file.read_text())
                logger.debug("Loaded %d tasks from %s", len(self._tasks), self._file)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load scheduler file: %s", exc)
            self._tasks = []

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(self._tasks, indent=2))
