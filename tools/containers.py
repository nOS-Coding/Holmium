"""Podman container management tools."""

import shlex
import subprocess
from typing import Optional

from tools.registry import register_tool


def _podman(*args: str, timeout: int = 30) -> str:
    result = subprocess.run(
        ["podman", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


@register_tool(
    "container_list",
    "List Podman containers (running/all).",
    params_schema={
        "type": "object",
        "properties": {
            "all": {
                "type": "boolean",
                "description": "Include stopped containers (default: running only)",
            },
        },
    },
)
def container_list(all: bool = False) -> dict:
    try:
        out = _podman("ps", "--format", "json")
        if all:
            out = _podman("ps", "-a", "--format", "json")
        import json
        containers = json.loads(out) if out.strip() else []
        if isinstance(containers, dict):
            containers = [containers]
        return {"success": True, "result": {"containers": containers, "count": len(containers)}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


@register_tool(
    "container_start",
    "Start a stopped Podman container.",
    params_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Container name or ID"},
        },
        "required": ["name"],
    },
)
def container_start(name: str) -> dict:
    try:
        out = _podman("start", name)
        return {"success": True, "result": {"container": name, "status": "started", "output": out}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


@register_tool(
    "container_stop",
    "Stop a running Podman container.",
    params_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Container name or ID"},
            "timeout": {"type": "integer", "description": "Seconds to wait before force kill"},
        },
        "required": ["name"],
    },
)
def container_stop(name: str, timeout: Optional[int] = None) -> dict:
    try:
        args = ["stop"]
        if timeout is not None:
            args.extend(["-t", str(timeout)])
        args.append(name)
        out = _podman(*args)
        return {"success": True, "result": {"container": name, "status": "stopped", "output": out}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


@register_tool(
    "container_restart",
    "Restart a Podman container.",
    params_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Container name or ID"},
        },
        "required": ["name"],
    },
)
def container_restart(name: str) -> dict:
    try:
        out = _podman("restart", name)
        return {"success": True, "result": {"container": name, "status": "restarted", "output": out}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


@register_tool(
    "container_logs",
    "Get logs from a Podman container.",
    params_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Container name or ID"},
            "tail": {"type": "integer", "description": "Number of recent lines (default: all)"},
        },
        "required": ["name"],
    },
)
def container_logs(name: str, tail: Optional[int] = None) -> dict:
    try:
        args = ["logs"]
        if tail is not None:
            args.extend(["--tail", str(tail)])
        args.append(name)
        out = _podman(*args)
        return {"success": True, "result": {"container": name, "logs": out}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


@register_tool(
    "container_exec",
    "Execute a command inside a Podman container.",
    params_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Container name or ID"},
            "command": {"type": "string", "description": "Command to run"},
        },
        "required": ["name", "command"],
    },
)
def container_exec(name: str, command: str) -> dict:
    try:
        out = _podman("exec", name, *shlex.split(command))
        return {"success": True, "result": {"container": name, "output": out}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


@register_tool(
    "container_create",
    "Create a new Podman container from an image.",
    params_schema={
        "type": "object",
        "properties": {
            "image": {"type": "string", "description": "Container image name"},
            "name": {"type": "string", "description": "Container name"},
            "command": {"type": "string", "description": "Startup command"},
            "detach": {"type": "boolean", "description": "Run in background (default: true)"},
        },
        "required": ["image"],
    },
)
def container_create(image: str, name: str = "", command: str = "", detach: bool = True) -> dict:
    try:
        args = ["create"]
        if detach:
            args.append("-d")
        if name:
            args.extend(["--name", name])
        args.append(image)
        if command:
            args.extend(shlex.split(command))
        out = _podman(*args)
        return {"success": True, "result": {"container_id": out, "image": image}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


@register_tool(
    "container_remove",
    "Remove a Podman container.",
    params_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Container name or ID"},
            "force": {"type": "boolean", "description": "Force removal of running container"},
        },
        "required": ["name"],
    },
)
def container_remove(name: str, force: bool = False) -> dict:
    try:
        args = ["rm"]
        if force:
            args.append("-f")
        args.append(name)
        out = _podman(*args)
        return {"success": True, "result": {"container": name, "output": out, "removed": True}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


@register_tool(
    "image_list",
    "List Podman images.",
    params_schema={
        "type": "object",
        "properties": {},
    },
)
def image_list() -> dict:
    try:
        out = _podman("images", "--format", "json")
        import json
        images = json.loads(out) if out.strip() else []
        if isinstance(images, dict):
            images = [images]
        return {"success": True, "result": {"images": images, "count": len(images)}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}


@register_tool(
    "image_pull",
    "Pull a container image from a registry.",
    params_schema={
        "type": "object",
        "properties": {
            "image": {"type": "string", "description": "Image name (e.g. docker.io/library/nginx)"},
        },
        "required": ["image"],
    },
)
def image_pull(image: str) -> dict:
    try:
        out = _podman("pull", image)
        return {"success": True, "result": {"image": image, "output": out}, "error": None}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)}
