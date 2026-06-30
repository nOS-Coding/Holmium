"""NAS (Network Attached Storage) management tools for Holmium.

Provides tools to control the WebDAV NAS server and manage the network share.
"""

from pathlib import Path
from tools.registry import register_tool


def _get_config():
    from backend.config import HolmiumConfig
    return HolmiumConfig.load()


def _nas_root() -> Path:
    return Path(_get_config().nas_path)


def _get_nas_server():
    from backend.nas_server import NasServer
    return NasServer(_get_config())


@register_tool(
    "nas_status",
    "Get the current status of the NAS (WebDAV) server: running, port, path, disk usage.",
)
def nas_status() -> dict:
    server = _get_nas_server()
    status = server.get_status()

    path = Path(status["path"])
    if path.exists():
        total = 0
        used = 0
        free = 0
        try:
            st = path.stat()
            import shutil
            usage = shutil.disk_usage(path)
            status["size_bytes"] = {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
            }
            status["size_human"] = {
                "total": _human(usage.total),
                "used": _human(usage.used),
                "free": _human(usage.free),
            }
        except OSError:
            pass

    return status


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


@register_tool(
    "nas_start",
    "Start the WebDAV NAS server if it is not already running.",
)
async def nas_start() -> dict:
    server = _get_nas_server()
    ok = await server.start()
    return {
        "success": ok,
        "running": server.is_running,
        "port": server.port,
        "path": server.nas_path,
        "message": "NAS server started" if ok else "NAS server already running or disabled",
    }


@register_tool(
    "nas_stop",
    "Stop the WebDAV NAS server.",
)
async def nas_stop() -> dict:
    server = _get_nas_server()
    ok = await server.stop()
    return {
        "success": ok,
        "message": "NAS server stopped" if ok else "NAS server was not running",
    }


@register_tool(
    "nas_list",
    "List files and directories in the NAS share.",
    {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path inside the NAS share (default: /)",
            },
        },
        "required": [],
    },
)
def nas_list(path: str = "") -> list:
    base = _nas_root().resolve()
    target = (base / path).resolve()
    if not str(target).startswith(str(base)):
        raise PermissionError("Path is outside the NAS share")
    if not target.exists():
        raise FileNotFoundError(f"Path not found in NAS: {path}")
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    from datetime import datetime
    entries = []
    for entry in target.iterdir():
        try:
            st = entry.stat()
            entries.append({
                "name": entry.name,
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "is_dir": entry.is_dir(),
                "rel_path": str(entry.relative_to(base)),
            })
        except OSError:
            continue
    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return entries
