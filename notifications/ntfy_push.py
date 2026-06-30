from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

_NTFY_TOPIC_FILE = Path("/etc/holmium/ntfy_topic.txt")
_HOSTS_FILE = Path.home() / ".netsh" / "hosts.json"


def _load_topic() -> str | None:
    if _NTFY_TOPIC_FILE.is_file():
        return _NTFY_TOPIC_FILE.read_text().strip()
    if _HOSTS_FILE.is_file():
        try:
            data = json.loads(_HOSTS_FILE.read_text())
            return data.get("ntfy_topic")
        except (json.JSONDecodeError, OSError):
            return None
    return None


def send_notification(
    title: str,
    body: str,
    topic: str | None = None,
    click_action: str | None = None,
    copy_text: str | None = None,
) -> bool:
    topic = topic or _load_topic()
    if not topic:
        return False

    payload: dict[str, Any] = {
        "title": title,
        "message": body,
        "priority": 4,
    }

    if click_action == "copy" and copy_text:
        payload["actions"] = [
            {
                "action": "view",
                "label": "Copy",
                "url": f"holmium://clipboard?text={copy_text[:500]}",
            }
        ]

    try:
        with httpx.Client(verify=False, timeout=15.0) as client:
            resp = client.post(
                f"https://ntfy.sh/{topic}",
                json=payload,
            )
            return resp.is_success
    except httpx.HTTPError:
        return False


def send_audio_notification(
    title: str,
    body: str,
    audio_bytes: bytes,
    filename: str = "holmium.wav",
    topic: str | None = None,
) -> bool:
    """Send a notification with an audio attachment via ntfy."""
    topic = topic or _load_topic()
    if not topic:
        return False

    try:
        with httpx.Client(verify=False, timeout=30.0) as client:
            files = {"file": (filename, audio_bytes, "audio/wav")}
            data = {
                "title": title,
                "message": body,
                "priority": 4,
            }
            resp = client.post(
                f"https://ntfy.sh/{topic}",
                data=data,
                files=files,
            )
            return resp.is_success
    except httpx.HTTPError:
        return False


def register_device(device_token: str, topic: str) -> bool:
    try:
        with httpx.Client(verify=False, timeout=15.0) as client:
            resp = client.post(
                f"https://ntfy.sh/{topic}/register",
                json={"device_token": device_token},
            )
            return resp.is_success
    except httpx.HTTPError:
        return False
