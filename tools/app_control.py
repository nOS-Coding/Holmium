from __future__ import annotations

import logging
import os
import signal
import subprocess
from typing import Any

import psutil

from tools.registry import registry

logger = logging.getLogger("holmium.tools.app_control")


def process_list() -> list[dict[str, Any]]:
    processes: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            pinfo = proc.info
            processes.append({
                "pid": pinfo["pid"],
                "name": pinfo["name"],
                "cpu_percent": pinfo["cpu_percent"] or 0.0,
                "ram_percent": pinfo["memory_percent"] or 0.0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    processes.sort(key=lambda p: p["cpu_percent"], reverse=True)
    return processes


def process_kill(pid_or_name: str) -> bool:
    try:
        pid = int(pid_or_name)
        os.kill(pid, signal.SIGKILL)
        return True
    except (ValueError, OSError):
        pass
    killed = False
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] == pid_or_name:
                os.kill(proc.info["pid"], signal.SIGKILL)
                killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    return killed


def process_start(command: str) -> int:
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return proc.pid
    except Exception as e:
        logger.exception("Failed to start process: %s", command)
        raise RuntimeError(f"Failed to start process: {e}") from e


def process_status(pid: int) -> dict[str, Any]:
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            return {
                "pid": proc.pid,
                "name": proc.name(),
                "status": proc.status(),
                "running": proc.is_running(),
                "cpu_percent": proc.cpu_percent(interval=0.0),
                "ram_percent": proc.memory_percent(),
                "create_time": proc.create_time(),
            }
    except psutil.NoSuchProcess:
        return {"pid": pid, "running": False, "status": "not found"}
    except psutil.AccessDenied:
        return {"pid": pid, "running": False, "status": "access denied"}


def register_app_control() -> None:
    registry.register(
        "process_list",
        "List all running processes with PID, name, CPU%, and RAM%.",
        {
            "type": "object",
            "properties": {},
            "required": [],
        },
        process_list,
    )
    registry.register(
        "process_kill",
        "Kill a process by PID or name using SIGKILL.",
        {
            "type": "object",
            "properties": {
                "pid_or_name": {
                    "type": "string",
                    "description": "PID (integer string) or process name to kill",
                },
            },
            "required": ["pid_or_name"],
        },
        process_kill,
    )
    registry.register(
        "process_start",
        "Start a process in the background and return its PID.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
            },
            "required": ["command"],
        },
        process_start,
    )
    registry.register(
        "process_status",
        "Check the status of a process by PID.",
        {
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "Process ID to check"},
            },
            "required": ["pid"],
        },
        process_status,
    )


register_app_control()
