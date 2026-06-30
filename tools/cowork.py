"""Cowork tools — second-cursor helper for the Mac.

In Help mode, Holmium acts as a collaborative second cursor on the user's Mac.
These tools enable file ops, app control, diagnostics, and Mac automation
over WireGuard via the daemon-agent running on the Mac.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import logging

import httpx

from tools.registry import registry
from notifications.ntfy_push import send_notification as ntfy_send

logger = logging.getLogger("holmium.tools.cowork")

logger = logging.getLogger("holmium.tools.cowork")

DEVICES_PATH = Path("/etc/holmium/devices.json")
AGENT_PORT = 9877

COWORK_HELP = """\
Cowork / Help Mode — Second Cursor on Mac

When in Help mode, I act as a collaborative second cursor on your Mac.
I can:
- Generate files, folders, and scripts directly on your Mac
- Clean up and organize your Downloads and Desktop folders
- Check Mac performance (CPU, RAM, disk, network, battery)
- Run system diagnostics and health checks
- Suggest optimizations and improvements
- Control apps via AppleScript (Chrome, PowerPoint, Finder, etc.)
- Take screenshots and screen recordings
- Edit and review files on your Mac
- Run terminal commands on your Mac

Just tell me what you need done and I'll do it on your Mac in real-time.
"""


def _load_device(device: str = "mac") -> dict[str, Any]:
    if not DEVICES_PATH.exists():
        raise FileNotFoundError(f"Devices config not found at {DEVICES_PATH}")
    devices = json.loads(DEVICES_PATH.read_text())
    if device not in devices:
        raise KeyError(f"Device '{device}' not found in {DEVICES_PATH}")
    return devices[device]


def _agent_url(device_info: dict[str, Any], endpoint: str) -> str:
    ip = device_info.get("ip", device_info.get("host", "10.0.0.2"))
    port = device_info.get("cowork_port", AGENT_PORT)
    return f"http://{ip}:{port}{endpoint}"


def _agent_headers(device_info: dict[str, Any]) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    token = device_info.get("token", "")
    if token:
        h["X-Holmium-Token"] = token
    return h


def _agent_post(endpoint: str, payload: dict, timeout: float = 30.0) -> dict[str, Any]:
    device_info = _load_device("mac")
    url = _agent_url(device_info, endpoint)
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, json=payload, headers=_agent_headers(device_info))
            r.raise_for_status()
            return r.json()
    except httpx.TimeoutException:
        return {"success": False, "error": f"Mac agent timed out ({timeout}s)"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Cannot reach Mac agent: {e}"}
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"Mac agent HTTP {e.response.status_code}: {e.response.text}"}


def cowork_file_read(path: str) -> dict[str, Any]:
    """Read a file from the Mac."""
    return _agent_post("/cowork/file_read", {"path": path})


def cowork_file_write(path: str, content: str) -> dict[str, Any]:
    """Write a file on the Mac (creates parent dirs)."""
    return _agent_post("/cowork/file_write", {"path": path, "content": content})


def cowork_file_delete(path: str) -> dict[str, Any]:
    """Delete a file or directory on the Mac."""
    return _agent_post("/cowork/file_delete", {"path": path})


def cowork_file_move(src: str, dst: str) -> dict[str, Any]:
    """Move a file or directory on the Mac."""
    return _agent_post("/cowork/file_move", {"src": src, "dst": dst})


def cowork_file_list(path: str) -> dict[str, Any]:
    """List directory contents on the Mac with sizes and modification times."""
    return _agent_post("/cowork/file_list", {"path": path})


def cowork_shell_run(command: str, timeout: int = 30) -> dict[str, Any]:
    """Run a shell command on the Mac and return stdout/stderr/exit_code."""
    return _agent_post("/cowork/shell_run", {"command": command, "timeout": timeout})


def cowork_shell_background(command: str) -> dict[str, Any]:
    """Start a background process on the Mac, returns PID."""
    return _agent_post("/cowork/shell_background", {"command": command})


def cowork_process_list() -> dict[str, Any]:
    """List running processes on the Mac with PID, name, CPU%, RAM%."""
    return _agent_post("/cowork/process_list", {})


def cowork_process_kill(pid_or_name: str | int) -> dict[str, Any]:
    """Kill a process on the Mac by PID or name."""
    return _agent_post("/cowork/process_kill", {"target": str(pid_or_name)})


def cowork_diagnostics() -> dict[str, Any]:
    """Run full system diagnostics on the Mac: CPU, RAM, disk, network, battery."""
    return _agent_post("/cowork/diagnostics", {}, timeout=60.0)


def cowork_performance() -> dict[str, Any]:
    """Get real-time Mac performance metrics."""
    return _agent_post("/cowork/performance", {})


def cowork_cleanup(target: str = "downloads", older_than_days: int = 30) -> dict[str, Any]:
    """Clean up files on Mac. target: 'downloads', 'desktop', 'trash', 'temp'."""
    return _agent_post("/cowork/cleanup", {"target": target, "older_than_days": older_than_days}, timeout=120.0)


def cowork_suggest() -> dict[str, Any]:
    """Analyze Mac state and suggest optimizations."""
    return _agent_post("/cowork/suggest", {}, timeout=60.0)


def cowork_applescript(script: str) -> dict[str, Any]:
    """Run AppleScript on the Mac for app automation (Chrome, PowerPoint, Finder, etc.)."""
    return _agent_post("/cowork/applescript", {"script": script}, timeout=30.0)


def cowork_chrome_open(url: str) -> dict[str, Any]:
    """Open a URL in Google Chrome on the Mac."""
    script = f'tell application "Google Chrome" to open location "{url}"'
    return cowork_applescript(script)


def cowork_chrome_tab_list() -> dict[str, Any]:
    """List open Chrome tabs on the Mac."""
    script = """
    tell application "Google Chrome"
        set tabInfo to {}
        repeat with w in windows
            repeat with t in tabs of w
                set end of tabInfo to {title:title of t, url:URL of t}
            end repeat
        end repeat
        return tabInfo
    end tell
    """
    return cowork_applescript(script)


def cowork_chrome_tab_close(url_or_title_contains: str) -> dict[str, Any]:
    """Close Chrome tabs matching a URL or title fragment."""
    escaped = url_or_title_contains.replace('"', '\\"')
    script = f"""
    tell application "Google Chrome"
        repeat with w in windows
            set tabIndex to 1
            repeat with t in tabs of w
                if (URL of t contains "{escaped}") or (title of t contains "{escaped}") then
                    close t
                end if
                set tabIndex to tabIndex + 1
            end repeat
        end repeat
    end tell
    """
    return cowork_applescript(script)


def cowork_powerpoint_create(title: str, slides: list[dict]) -> dict[str, Any]:
    """Create a PowerPoint presentation on the Mac with given slides.
    Each slide: {"title": "...", "content": "..."} or {"title": "...", "bullets": [...]}
    """
    import json as _json
    slides_json = _json.dumps(slides).replace('"', '\\"')
    script = f"""
    tell application "Microsoft PowerPoint"
        activate
        set newPres to make new presentation
        set slideIndex to 1
        -- slides data passed as JSON
    end tell
    """
    return _agent_post("/cowork/powerpoint_create", {
        "title": title,
        "slides": slides,
    }, timeout=120.0)


def cowork_open_app(app_name: str) -> dict[str, Any]:
    """Open an application on the Mac by name."""
    return cowork_applescript(f'activate application "{app_name}"')


def cowork_screenshot() -> dict[str, Any]:
    """Take a screenshot on the Mac and return the file path."""
    return cowork_applescript("""
    set imgPath to (POSIX path of (path to pictures folder)) & "holmium_screenshot_" & (do shell script "date +%Y%m%d_%H%M%S") & ".png"
    do shell script "screencapture -x " & quoted form of imgPath
    return imgPath
    """)


def cowork_finder_open(path: str) -> dict[str, Any]:
    """Open a Finder window showing the given path."""
    return cowork_applescript(f'tell application "Finder" to open POSIX file "{path}"')


def cowork_finder_new_folder(parent: str, name: str) -> dict[str, Any]:
    """Create a new folder in Finder at the given parent path."""
    return _agent_post("/cowork/file_write", {
        "path": str(Path(parent) / name),
        "content": "",
        "mkdir": True,
    })


def cowork_notify(title: str, body: str) -> dict[str, Any]:
    """Send a macOS notification."""
    return _agent_post("/cowork/notify", {"title": title, "body": body})


def cowork_say(text: str, voice: str = "Samantha") -> dict[str, Any]:
    """Speak text aloud on the Mac using TTS."""
    return _agent_post("/cowork/say", {"text": text, "voice": voice})


def cowork_android_clipboard(text: str) -> dict[str, Any]:
    """Send text to Android clipboard via ntfy notification (click-to-copy)."""
    sent = ntfy_send(
        title="Holmium Clipboard",
        message=f"Tap to copy: {text[:100]}",
        click_action="copy",
        copy_text=text,
    )
    return {"success": bool(sent), "result": "sent" if sent else "failed"}


def register_cowork_tools() -> None:
    tools = [
        ("cowork_file_read", "Read a file from the Mac.", {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute path on Mac"}},
            "required": ["path"],
        }, cowork_file_read),
        ("cowork_file_write", "Write content to a file on the Mac (creates parent dirs).", {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path on Mac"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        }, cowork_file_write),
        ("cowork_file_delete", "Delete a file or directory on the Mac.", {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute path on Mac"}},
            "required": ["path"],
        }, cowork_file_delete),
        ("cowork_file_move", "Move a file or directory on the Mac.", {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "Source path"},
                "dst": {"type": "string", "description": "Destination path"},
            },
            "required": ["src", "dst"],
        }, cowork_file_move),
        ("cowork_file_list", "List directory contents on the Mac.", {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
            "required": ["path"],
        }, cowork_file_list),
        ("cowork_shell_run", "Run a shell command on the Mac. Returns stdout, stderr, exit_code.", {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            },
            "required": ["command"],
        }, cowork_shell_run),
        ("cowork_shell_background", "Start a background process on the Mac.", {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "Command to run in background"}},
            "required": ["command"],
        }, cowork_shell_background),
        ("cowork_process_list", "List running processes on the Mac with CPU% and RAM%.", {
            "type": "object",
            "properties": {},
            "required": [],
        }, cowork_process_list),
        ("cowork_process_kill", "Kill a process on the Mac by PID or name.", {
            "type": "object",
            "properties": {"target": {"type": "string", "description": "PID number or process name"}},
            "required": ["target"],
        }, cowork_process_kill),
        ("cowork_diagnostics", "Run full system diagnostics on the Mac: CPU, RAM, disk, network, battery health.", {
            "type": "object", "properties": {}, "required": [],
        }, cowork_diagnostics),
        ("cowork_performance", "Get real-time Mac performance metrics (CPU, RAM, disk, network, temps).", {
            "type": "object", "properties": {}, "required": [],
        }, cowork_performance),
        ("cowork_cleanup", "Clean up files on the Mac (Downloads, Desktop, temp files).", {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Area to clean: 'downloads', 'desktop', 'temp', 'trash'"},
                "older_than_days": {"type": "integer", "description": "Delete files older than N days", "default": 30},
            },
            "required": ["target"],
        }, cowork_cleanup),
        ("cowork_suggest", "Analyze Mac state and suggest optimizations and improvements.", {
            "type": "object", "properties": {}, "required": [],
        }, cowork_suggest),
        ("cowork_applescript", "Run AppleScript on the Mac for app automation (Chrome, PowerPoint, Finder).", {
            "type": "object",
            "properties": {"script": {"type": "string", "description": "AppleScript code to execute"}},
            "required": ["script"],
        }, cowork_applescript),
        ("cowork_chrome_open", "Open a URL in Google Chrome on the Mac.", {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL to open"}},
            "required": ["url"],
        }, cowork_chrome_open),
        ("cowork_chrome_tab_list", "List all open Chrome tabs on the Mac.", {
            "type": "object", "properties": {}, "required": [],
        }, cowork_chrome_tab_list),
        ("cowork_chrome_tab_close", "Close Chrome tabs matching a URL or title fragment.", {
            "type": "object",
            "properties": {"url_or_title_contains": {"type": "string", "description": "Fragment to match in URL or title"}},
            "required": ["url_or_title_contains"],
        }, cowork_chrome_tab_close),
        ("cowork_powerpoint_create", "Create a PowerPoint presentation on the Mac.", {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Presentation title"},
                "slides": {"type": "array", "description": "List of slides, each with title and content/bullets"},
            },
            "required": ["title", "slides"],
        }, cowork_powerpoint_create),
        ("cowork_open_app", "Open an application on the Mac by name.", {
            "type": "object",
            "properties": {"app_name": {"type": "string", "description": "Application name (e.g. 'Safari', 'Notes')"}},
            "required": ["app_name"],
        }, cowork_open_app),
        ("cowork_screenshot", "Take a screenshot on the Mac.", {
            "type": "object", "properties": {}, "required": [],
        }, cowork_screenshot),
        ("cowork_finder_open", "Open a Finder window on the Mac at the given path.", {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path to show in Finder"}},
            "required": ["path"],
        }, cowork_finder_open),
        ("cowork_notify", "Send a macOS notification.", {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Notification title"},
                "body": {"type": "string", "description": "Notification body text"},
            },
            "required": ["title", "body"],
        }, cowork_notify),
        ("cowork_say", "Speak text aloud on the Mac using TTS.", {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to speak"},
                "voice": {"type": "string", "description": "Voice name (default Samantha)", "default": "Samantha"},
            },
            "required": ["text"],
        }, cowork_say),
        ("cowork_android_clipboard", "Send text to Android clipboard via ntfy (click-to-copy).", {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to copy on Android"},
            },
            "required": ["text"],
        }, cowork_android_clipboard),
    ]

    for name, desc, schema, handler in tools:
        registry.register(name, desc, schema, handler)


register_cowork_tools()
