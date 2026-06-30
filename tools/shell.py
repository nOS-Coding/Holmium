from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any

from tools.registry import registry

logger = logging.getLogger("holmium.tools.shell")


def shell_run(command: str, timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"{type(e).__name__}: {e}",
            "exit_code": -1,
        }


def shell_run_background(command: str) -> int:
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
        logger.exception("Failed to start background command: %s", command)
        raise RuntimeError(f"Failed to start background process: {e}") from e


def register_shell_tools() -> None:
    registry.register(
        "shell_run",
        "Execute a shell command and wait for it to complete. Returns stdout, stderr, and exit code.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30)",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
        shell_run,
    )
    registry.register(
        "shell_run_background",
        "Execute a shell command in the background and return immediately with the PID.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
            },
            "required": ["command"],
        },
        shell_run_background,
    )


register_shell_tools()
