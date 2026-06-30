from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from tools.registry import registry


def file_read(path: str) -> str:
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not p.is_file():
        raise IsADirectoryError(f"Path is a directory, not a file: {path}")
    try:
        return p.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return p.read_bytes().decode("latin-1")


def file_write(path: str, content: str) -> bool:
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return True


def file_delete(path: str) -> bool:
    p = Path(path).resolve()
    if not p.exists():
        return False
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return True


def file_move(src: str, dst: str) -> bool:
    src_p = Path(src).resolve()
    dst_p = Path(dst).resolve()
    if not src_p.exists():
        raise FileNotFoundError(f"Source not found: {src}")
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_p), str(dst_p))
    return True


def file_list(path: str) -> list[dict]:
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if not p.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")
    entries: list[dict] = []
    for entry in p.iterdir():
        try:
            st = entry.stat()
            entries.append({
                "name": entry.name,
                "size": st.st_size,
                "modified_time": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "is_dir": entry.is_dir(),
            })
        except OSError:
            continue
    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return entries


def file_exists(path: str) -> bool:
    return Path(path).resolve().exists()


def register_file_ops() -> None:
    registry.register(
        "file_read",
        "Read the contents of a file at the given absolute path. Returns the file content as a string.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
            },
            "required": ["path"],
        },
        file_read,
    )
    registry.register(
        "file_write",
        "Write content to a file at the given absolute path. Creates parent directories automatically.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file"},
                "content": {"type": "string", "description": "Text content to write"},
            },
            "required": ["path", "content"],
        },
        file_write,
    )
    registry.register(
        "file_delete",
        "Delete a file or directory at the given absolute path. Directories are deleted recursively.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to delete"},
            },
            "required": ["path"],
        },
        file_delete,
    )
    registry.register(
        "file_move",
        "Move a file or directory from source to destination. Creates parent directories at destination.",
        {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "Source absolute path"},
                "dst": {"type": "string", "description": "Destination absolute path"},
            },
            "required": ["src", "dst"],
        },
        file_move,
    )
    registry.register(
        "file_list",
        "List directory contents with metadata (name, size, modification time, is_dir).",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the directory"},
            },
            "required": ["path"],
        },
        file_list,
    )
    registry.register(
        "file_exists",
        "Check whether a file or directory exists at the given path.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to check"},
            },
            "required": ["path"],
        },
        file_exists,
    )


register_file_ops()
