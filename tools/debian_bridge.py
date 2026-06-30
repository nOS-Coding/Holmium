"""Debian bridge — drop/patch/discard/list files on the Debian partition."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from tools.registry import register_tool

DEBIAN_LABEL = "debian-root"
DEBIAN_MOUNT = Path("/mnt/debian")
HOLMIUM_SIZE_GiB = 900


def _find_debian_partition() -> Optional[str]:
    try:
        result = subprocess.run(
            ["blkid", "-L", DEBIAN_LABEL],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    try:
        result = subprocess.run(
            ["lsblk", "-nlo", "NAME,TYPE,SIZE,LABEL"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] == "part":
                dev = parts[0]
                full_path = f"/dev/{dev}"
                try:
                    label_result = subprocess.run(
                        ["blkid", "-s", "LABEL", "-o", "value", full_path],
                        capture_output=True, text=True, timeout=3,
                    )
                    label = label_result.stdout.strip()
                    if label and label not in ("holmium-root", "holmium-swap", "") and "vfat" not in label.lower():
                        return full_path
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _ensure_mounted() -> tuple[bool, str]:
    DEBIAN_MOUNT.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["mountpoint", "-q", str(DEBIAN_MOUNT)],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return True, f"Mounted at {DEBIAN_MOUNT}"
    except FileNotFoundError:
        pass
    part = _find_debian_partition()
    if not part:
        return False, "Debian partition not found. Install Debian first and label it 'debian-root': sudo e2label /dev/sdX4 debian-root"
    try:
        subprocess.run(
            ["mount", part, str(DEBIAN_MOUNT)],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return True, f"Mounted {part} at {DEBIAN_MOUNT}"
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return False, f"Failed to mount {part}: {exc}"


@register_tool(
    "debian_drop",
    "Copy a file from Holmium to the Debian partition.",
    params_schema={
        "type": "object",
        "properties": {
            "src_path": {
                "type": "string",
                "description": "Path to the source file on Holmium",
            },
            "dest_rel_path": {
                "type": "string",
                "description": "Destination path relative to Debian root (e.g. home/user/Documents/file.txt)",
            },
        },
        "required": ["src_path", "dest_rel_path"],
    },
)
def debian_drop(src_path: str, dest_rel_path: str) -> dict:
    ok, msg = _ensure_mounted()
    if not ok:
        return {"success": False, "result": None, "error": msg}
    src = Path(src_path)
    if not src.exists():
        return {"success": False, "result": None, "error": f"Source not found: {src_path}"}
    dest = DEBIAN_MOUNT / dest_rel_path
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(str(src), str(dest))
        return {"success": True, "result": {"dest": str(dest)}, "error": None}
    except OSError as exc:
        return {"success": False, "result": None, "error": str(exc)}


@register_tool(
    "debian_patch",
    "Write or overwrite a file on the Debian partition.",
    params_schema={
        "type": "object",
        "properties": {
            "debian_path": {
                "type": "string",
                "description": "Path relative to Debian root (e.g. home/user/.bashrc)",
            },
            "new_content": {
                "type": "string",
                "description": "Full new content for the file",
            },
        },
        "required": ["debian_path", "new_content"],
    },
)
def debian_patch(debian_path: str, new_content: str) -> dict:
    ok, msg = _ensure_mounted()
    if not ok:
        return {"success": False, "result": None, "error": msg}
    path = DEBIAN_MOUNT / debian_path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content)
        return {"success": True, "result": {"path": str(path), "size": len(new_content)}, "error": None}
    except OSError as exc:
        return {"success": False, "result": None, "error": str(exc)}


@register_tool(
    "debian_discard",
    "Delete a file or directory from the Debian partition.",
    params_schema={
        "type": "object",
        "properties": {
            "debian_path": {
                "type": "string",
                "description": "Path relative to Debian root (e.g. home/user/temp/file.txt)",
            },
        },
        "required": ["debian_path"],
    },
)
def debian_discard(debian_path: str) -> dict:
    ok, msg = _ensure_mounted()
    if not ok:
        return {"success": False, "result": None, "error": msg}
    path = DEBIAN_MOUNT / debian_path
    if not path.exists():
        return {"success": False, "result": None, "error": f"Not found: {debian_path}"}
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return {"success": True, "result": {"deleted": str(path)}, "error": None}
    except OSError as exc:
        return {"success": False, "result": None, "error": str(exc)}


@register_tool(
    "debian_list",
    "List files and directories on the Debian partition.",
    params_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to Debian root (default: root of Debian partition)",
                "default": "",
            },
        },
    },
)
def debian_list(path: str = "") -> dict:
    ok, msg = _ensure_mounted()
    if not ok:
        return {"success": False, "result": None, "error": msg}
    target = DEBIAN_MOUNT / path
    if not target.exists():
        return {"success": False, "result": None, "error": f"Not found: {path or '/'}"}
    try:
        entries = []
        for entry in sorted(target.iterdir()):
            try:
                stat = entry.stat()
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
            except OSError:
                continue
        return {"success": True, "result": {"path": str(target), "entries": entries, "count": len(entries)}, "error": None}
    except OSError as exc:
        return {"success": False, "result": None, "error": str(exc)}
