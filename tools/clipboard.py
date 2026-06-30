"""Clipboard tools — Mac (daemon API) and Android (ntfy push)."""

from typing import Optional

import httpx

from notifications.ntfy_push import send_notification
from tools.registry import register_tool

MAC_DAEMON_URL = "http://10.0.0.2:9876"

_VALID_DEVICES = ("mac", "android")


def _mac_clipboard(action: str, content: Optional[str] = None) -> Optional[str]:
    try:
        payload = {"action": action}
        if content is not None:
            payload["content"] = content
        resp = httpx.post(
            f"{MAC_DAEMON_URL}/clipboard",
            json=payload,
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("content")
    except Exception:
        return None


def _resolve_device(device: str) -> Optional[str]:
    if device in ("mac", "macos", "macbook"):
        return "mac"
    if device in ("android", "phone"):
        return "android"
    return None


@register_tool(
    "clipboard_read",
    "Read clipboard contents from a device (mac or android).",
    params_schema={
        "type": "object",
        "properties": {
            "device": {
                "type": "string",
                "enum": ["mac", "android"],
                "description": "Device: mac or android",
            },
        },
        "required": ["device"],
    },
)
def clipboard_read(device: str) -> str:
    d = _resolve_device(device)
    if d is None:
        return f"Error: unknown device '{device}'"
    if d == "android":
        return "Error: Android clipboard read not supported"
    result = _mac_clipboard("read")
    return result if result is not None else "Error reading Mac clipboard"


@register_tool(
    "clipboard_write",
    "Write content to a device's clipboard (mac or android).",
    params_schema={
        "type": "object",
        "properties": {
            "device": {
                "type": "string",
                "enum": ["mac", "android"],
                "description": "Device: mac or android",
            },
            "content": {
                "type": "string",
                "description": "Content to write to clipboard",
            },
        },
        "required": ["device", "content"],
    },
)
def clipboard_write(device: str, content: str) -> bool:
    d = _resolve_device(device)
    if d is None:
        return False
    if d == "mac":
        return _mac_clipboard("write", content) is not None
    return send_notification(
        "Holmium Clipboard",
        f"Tap to copy: {content[:100]}",
        click_action="copy",
        copy_text=content,
    )


@register_tool(
    "clipboard_sync",
    "Sync clipboard contents from one device to another.",
    params_schema={
        "type": "object",
        "properties": {
            "from_device": {
                "type": "string",
                "enum": ["mac", "android"],
                "description": "Source device (mac or android)",
            },
            "to_device": {
                "type": "string",
                "enum": ["mac", "android"],
                "description": "Target device (mac or android)",
            },
        },
        "required": ["from_device", "to_device"],
    },
)
def clipboard_sync(from_device: str, to_device: str) -> bool:
    content = clipboard_read(from_device)
    if content.startswith("Error"):
        return False
    return clipboard_write(to_device, content)
