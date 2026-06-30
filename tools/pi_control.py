"""Pi remote control tools — SSH over WireGuard to 10.0.0.4."""

import shlex
import subprocess
from pathlib import Path

from tools.registry import register_tool

PI_IP = "10.0.0.4"
PI_USER = "pi"
PI_PORT = 22

_IDENTITY_FILES: list[str] = [
    "/etc/holmium/id_rsa_holmium",
    str(Path.home() / ".ssh" / "id_rsa_holmium"),
]


def _ssh_identity() -> str:
    for f in _IDENTITY_FILES:
        if Path(f).is_file():
            return f
    return _IDENTITY_FILES[0]


def _ssh_base() -> list[str]:
    return [
        "ssh",
        "-i", _ssh_identity(),
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-p", str(PI_PORT),
        f"{PI_USER}@{PI_IP}",
    ]


def _ssh_run(command: str, timeout: int = 30) -> dict:
    try:
        proc = subprocess.run(
            _ssh_base() + [command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": proc.returncode == 0,
            "result": proc.stdout,
            "error": proc.stderr if proc.returncode != 0 else None,
            "exit_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "result": None,
            "error": f"Command timed out after {timeout}s",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "result": None,
            "error": f"SSH error: {e}",
            "exit_code": -1,
        }


@register_tool(
    "pi_run",
    "Run a shell command on the Raspberry Pi via SSH.",
    params_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Command to execute on the Pi",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 30,
            },
        },
        "required": ["command"],
    },
)
def pi_run(command: str, timeout: int = 30) -> dict:
    return _ssh_run(command, timeout)


@register_tool(
    "pi_service",
    "Start, stop, restart, enable, disable, or check status of a systemd service on the Pi.",
    params_schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "stop", "restart", "enable", "disable", "status"],
                "description": "Action to perform on the service",
            },
            "service": {
                "type": "string",
                "description": "Service name",
            },
        },
        "required": ["action", "service"],
    },
)
def pi_service(action: str, service: str) -> dict:
    return _ssh_run(f"sudo systemctl {shlex.quote(action)} {shlex.quote(service)}")


@register_tool(
    "pi_reboot",
    "Reboot the Raspberry Pi.",
)
def pi_reboot() -> dict:
    return _ssh_run("sudo reboot")


@register_tool(
    "pi_shutdown",
    "Shutdown the Raspberry Pi.",
)
def pi_shutdown() -> dict:
    return _ssh_run("sudo shutdown -h now")


@register_tool(
    "pi_status",
    "Get system status from the Raspberry Pi (uptime, CPU temp, memory, disk, load).",
)
def pi_status() -> dict:
    checks = {
        "uptime": "uptime",
        "cpu_temp": "vcgencmd measure_temp 2>/dev/null || awk '{printf \"%.1f\" , $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null",
        "memory": "free -h | head -3",
        "disk": "df -h / | tail -1",
        "load": "cat /proc/loadavg",
    }
    data: dict[str, str | None] = {}
    errors: list[str] = []
    for key, cmd in checks.items():
        r = _ssh_run(cmd)
        if r["success"]:
            data[key] = r["result"].strip()
        else:
            errors.append(f"{key}: {r['error']}")
            data[key] = None
    return {
        "success": len(errors) == 0,
        "result": data,
        "error": "; ".join(errors) if errors else None,
    }


@register_tool(
    "pi_display",
    "Display text on the Pi's console screen (/dev/tty1).",
    params_schema={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to display on the Pi screen",
            },
        },
        "required": ["text"],
    },
)
def pi_display(text: str) -> dict:
    return _ssh_run(f"echo {shlex.quote(text)} | sudo tee /dev/tty1")
