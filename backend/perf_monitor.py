"""Performance monitoring — measure and log operation durations with thresholds."""

import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from .logger import get_logger

logger = get_logger("perf_monitor")

_THRESHOLD_MULTIPLIER = 2.0
_DEFAULT_BASELINE_MS = 1000.0


class PerfMonitor:
    def __init__(self) -> None:
        self._metrics: dict[str, list[float]] = defaultdict(list)
        self._baselines: dict[str, float] = {}

    @contextmanager
    def measure(self, operation: str) -> Generator[None, None, None]:
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            self.log_perf(operation, elapsed_ms)

    def log_perf(self, operation: str, duration_ms: float) -> None:
        self._metrics[operation].append(duration_ms)
        baseline = self._baselines.get(operation, _DEFAULT_BASELINE_MS)
        threshold = baseline * _THRESHOLD_MULTIPLIER

        if duration_ms > threshold:
            logger.warning(
                "Perf warning: %s took %.2fms (threshold: %.2fms)",
                operation, duration_ms, threshold,
            )
        else:
            logger.debug("Perf: %s %.2fms", operation, duration_ms)

        count = len(self._metrics[operation])
        if count >= 5:
            avg = sum(self._metrics[operation][-5:]) / 5
            self._baselines[operation] = avg

    def get_report(self) -> dict:
        report: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operations": {},
        }
        for op, durations in self._metrics.items():
            if not durations:
                continue
            report["operations"][op] = {
                "count": len(durations),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "min_ms": round(min(durations), 2),
                "max_ms": round(max(durations), 2),
                "p95_ms": round(sorted(durations)[int(len(durations) * 0.95)], 2),
                "baseline_ms": round(self._baselines.get(op, _DEFAULT_BASELINE_MS), 2),
            }

        return report

    def reset(self) -> None:
        self._metrics.clear()
        self._baselines.clear()
        logger.debug("PerfMonitor reset")
