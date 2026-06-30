from __future__ import annotations

import logging
import threading
import time
import traceback
from typing import Any

from tools.registry import registry

logger = logging.getLogger("holmium.tools.monitor")

_active_monitors: dict[str, _MonitorInstance] = {}
_monitors_lock = threading.Lock()


class _MonitorInstance:
    def __init__(
        self,
        name: str,
        condition: str,
        interval: float,
    ) -> None:
        self.name = name
        self.condition = condition
        self.interval = interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._last_eval: bool | None = None
        self._last_error: str | None = None
        self._triggered: bool = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name=f"monitor-{self.name}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    @property
    def triggered(self) -> bool:
        return self._triggered

    def info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "condition": self.condition,
            "interval": self.interval,
            "running": self._running,
            "triggered": self._triggered,
            "last_eval": self._last_eval,
            "last_error": self._last_error,
        }

    def _loop(self) -> None:
        namespace: dict[str, Any] = {}
        try:
            import psutil  # noqa: F401

            namespace["psutil"] = psutil
        except ImportError:
            pass
        try:
            import os

            namespace["os"] = os
        except ImportError:
            pass
        namespace["__builtins__"] = __builtins__

        while not self._stop_event.wait(self.interval):
            try:
                result = eval(self.condition, namespace)
                self._last_eval = bool(result)
                self._last_error = None
                if self._last_eval:
                    self._triggered = True
                    logger.warning(
                        "Monitor '%s' condition triggered: %s",
                        self.name,
                        self.condition,
                    )
            except Exception:
                self._last_error = traceback.format_exc()
                self._last_eval = None
                logger.error(
                    "Monitor '%s' error evaluating condition: %s",
                    self.name,
                    self._last_error,
                )


def monitor_start(name: str, condition: str, interval: float = 10.0) -> bool:
    with _monitors_lock:
        if name in _active_monitors:
            _active_monitors[name].stop()
        instance = _MonitorInstance(name, condition, interval)
        instance.start()
        _active_monitors[name] = instance
    logger.info("Started monitor '%s': %s (every %ss)", name, condition, interval)
    return True


def monitor_stop(name: str) -> bool:
    with _monitors_lock:
        instance = _active_monitors.pop(name, None)
        if instance is None:
            return False
        instance.stop()
    logger.info("Stopped monitor '%s'", name)
    return True


def monitor_list() -> list[dict[str, Any]]:
    with _monitors_lock:
        return [inst.info() for inst in _active_monitors.values()]


def register_monitor_tools() -> None:
    registry.register(
        "monitor_start",
        "Start a background monitor that evaluates a Python expression periodically. When truthy, the monitor is marked as triggered.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Unique name for this monitor"},
                "condition": {
                    "type": "string",
                    "description": "Python expression to evaluate (e.g. 'psutil.cpu_percent() > 90')",
                },
                "interval": {
                    "type": "number",
                    "description": "Check interval in seconds (default 10)",
                    "default": 10.0,
                },
            },
            "required": ["name", "condition"],
        },
        monitor_start,
    )
    registry.register(
        "monitor_stop",
        "Stop and remove a running monitor by name.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the monitor to stop"},
            },
            "required": ["name"],
        },
        monitor_stop,
    )
    registry.register(
        "monitor_list",
        "List all active monitors with their status, condition, and interval.",
        {
            "type": "object",
            "properties": {},
            "required": [],
        },
        monitor_list,
    )


register_monitor_tools()
