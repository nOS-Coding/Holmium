from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from tools.registry import registry

logger = logging.getLogger("holmium.tools.remote")

DEVICES_PATH = Path("/etc/holmium/devices.json")
DEFAULT_AGENT_PORT = 8766
DEFAULT_TIMEOUT = 30.0


def _load_device(device: str) -> dict[str, Any]:
    if not DEVICES_PATH.exists():
        raise FileNotFoundError(f"Devices config not found at {DEVICES_PATH}")
    try:
        devices = json.loads(DEVICES_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(f"Failed to read devices config: {e}") from e
    if device not in devices:
        raise KeyError(f"Unknown device: {device}. Known devices: {list(devices)}")
    return devices[device]


def _device_url(device_info: dict[str, Any], endpoint: str) -> str:
    ip = device_info.get("ip", device_info.get("host", "10.0.0.2"))
    port = device_info.get("port", DEFAULT_AGENT_PORT)
    return f"http://{ip}:{port}{endpoint}"


def _device_headers(device_info: dict[str, Any]) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = device_info.get("token")
    if token:
        headers["X-Holmium-Token"] = token
    return headers


def remote_shell(device: str, command: str) -> dict[str, Any]:
    device_info = _load_device(device)
    url = _device_url(device_info, "/exec")
    headers = _device_headers(device_info)
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post(url, json={"command": command}, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        return {"stdout": "", "stderr": f"Request to {device} timed out", "exit_code": -1}
    except httpx.HTTPStatusError as e:
        return {"stdout": "", "stderr": f"HTTP {e.response.status_code}: {e.response.text}", "exit_code": -1}
    except httpx.RequestError as e:
        return {"stdout": "", "stderr": f"Connection to {device} failed: {e}", "exit_code": -1}


def remote_file_read(device: str, path: str) -> str:
    device_info = _load_device(device)
    url = _device_url(device_info, "/files/read")
    headers = _device_headers(device_info)
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post(url, json={"path": path}, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("content", "")
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to read file on {device}: {e}") from e


def remote_file_write(device: str, path: str, content: str) -> bool:
    device_info = _load_device(device)
    url = _device_url(device_info, "/files/write")
    headers = _device_headers(device_info)
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post(url, json={"path": path, "content": content}, headers=headers)
            resp.raise_for_status()
            return True
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to write file on {device}: {e}") from e


def remote_file_send(device: str, local_path: str, remote_path: str) -> bool:
    device_info = _load_device(device)
    url = _device_url(device_info, "/files/upload")
    local = Path(local_path).resolve()
    if not local.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            with open(local, "rb") as f:
                files = {"file": (local.name, f, "application/octet-stream")}
                resp = client.post(
                    url,
                    data={"path": remote_path},
                    files=files,
                    headers=_device_headers(device_info),
                )
                resp.raise_for_status()
                return True
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to send file to {device}: {e}") from e


def register_remote_tools() -> None:
    registry.register(
        "remote_shell",
        "Execute a shell command on a remote device over WireGuard. Devices: mac, android, pi.",
        {
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Device name (mac, android, pi)",
                },
                "command": {"type": "string", "description": "Command to execute on the remote device"},
            },
            "required": ["device", "command"],
        },
        remote_shell,
    )
    registry.register(
        "remote_file_read",
        "Read a file from a remote device over WireGuard.",
        {
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Device name (mac, android, pi)",
                },
                "path": {"type": "string", "description": "Absolute path on the remote device"},
            },
            "required": ["device", "path"],
        },
        remote_file_read,
    )
    registry.register(
        "remote_file_write",
        "Write content to a file on a remote device over WireGuard.",
        {
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Device name (mac, android, pi)",
                },
                "path": {"type": "string", "description": "Absolute path on the remote device"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["device", "path", "content"],
        },
        remote_file_write,
    )
    registry.register(
        "remote_file_send",
        "Send a local file to a remote device over WireGuard.",
        {
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Device name (mac, android, pi)",
                },
                "local_path": {"type": "string", "description": "Absolute path on the local machine"},
                "remote_path": {"type": "string", "description": "Destination path on the remote device"},
            },
            "required": ["device", "local_path", "remote_path"],
        },
        remote_file_send,
    )


register_remote_tools()
