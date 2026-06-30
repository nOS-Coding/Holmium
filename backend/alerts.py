"""Proactive alert system — ntfy push + macOS notification + file log."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger("alerts")

_ALERTS_LOG = Path("/var/log/holmium/alerts.log")


async def send_alert(title: str, body: str) -> None:
    _ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = f"[{timestamp}] {title}: {body}\n"
    try:
        with open(str(_ALERTS_LOG), "a") as f:
            f.write(log_entry)
    except OSError as exc:
        logger.error("Failed to write alert log: %s", exc)

    ntfy_error: Optional[str] = None
    mac_error: Optional[str] = None

    try:
        from ..tools.ntfy_push import send_notification as ntfy_send
        await ntfy_send(title=title, message=body)
        logger.debug("Alert sent via ntfy: %s", title)
    except ImportError:
        ntfy_error = "ntfy_push not available"
    except Exception as exc:
        ntfy_error = str(exc)
        logger.warning("ntfy alert failed: %s", exc)

    try:
        from ..tools.mac_notify import send_mac_notification as mac_send
        await mac_send(title=title, message=body)
        logger.debug("Alert sent via macOS notification: %s", title)
    except ImportError:
        mac_error = "mac_notify not available"
    except Exception as exc:
        mac_error = str(exc)
        logger.warning("macOS notification failed: %s", exc)

    if ntfy_error and mac_error:
        logger.warning("All alert transports failed: ntfy=%s, mac=%s", ntfy_error, mac_error)


def get_alert_history(n: int = 50) -> list[dict]:
    if not _ALERTS_LOG.exists():
        return []

    alerts: list[dict] = []
    try:
        with open(str(_ALERTS_LOG), "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("[") and "] " in line:
                    bracket_end = line.index("] ")
                    timestamp = line[1:bracket_end]
                    rest = line[bracket_end + 2:]
                    if ": " in rest:
                        sep = rest.index(": ")
                        title = rest[:sep]
                        body = rest[sep + 2:]
                    else:
                        title = rest
                        body = ""
                    alerts.append({
                        "timestamp": timestamp,
                        "title": title,
                        "body": body,
                    })
    except OSError as exc:
        logger.error("Failed to read alert history: %s", exc)
        return []

    return alerts[-n:]
