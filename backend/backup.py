"""USB backup — copy facts, LanceDB, vision docs, sessions, notes, config to zip."""

import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..memory.sqlite_store import SQLiteStore
from ..memory.vector_store import VectorStore
from .logger import get_logger

logger = get_logger("backup")

_BACKUP_MOUNT = Path("/mnt/backup")


async def run_backup() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = _ensure_backup_mount()
    if backup_dir is None:
        return "Error: backup mount /mnt/backup/ not available"

    with tempfile.TemporaryDirectory(prefix="holmium_backup_") as tmpdir:
        tmp = Path(tmpdir)
        try:
            _backup_sqlite(tmp)
            _backup_lancedb(tmp)
            _backup_vision_docs(tmp)
            _backup_sessions(tmp)
            _backup_notes(tmp)
            _backup_config(tmp)
        except Exception as exc:
            logger.exception("Backup collection failed: %s", exc)
            return f"Error: backup failed — {exc}"

        zip_name = f"holmium-backup-{timestamp}.zip"
        zip_path = backup_dir / zip_name
        _create_zip(tmp, zip_path)

    logger.info("Backup created: %s (%d bytes)", zip_path, zip_path.stat().st_size)
    return str(zip_path)


def _ensure_backup_mount() -> Optional[Path]:
    try:
        result = subprocess.run(
            ["mountpoint", "-q", str(_BACKUP_MOUNT)],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return _BACKUP_MOUNT
        _BACKUP_MOUNT.mkdir(parents=True, exist_ok=True)
        return _BACKUP_MOUNT
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _BACKUP_MOUNT.mkdir(parents=True, exist_ok=True)
        return _BACKUP_MOUNT


def _backup_sqlite(tmp: Path) -> None:
    src = Path("/var/holmium/memory/facts.db")
    if src.exists():
        shutil.copy2(str(src), str(tmp / "facts.db"))
        logger.debug("Backed up facts.db")

    store = SQLiteStore()
    facts_path = tmp / "facts_export.json"
    facts_path.write_text(json.dumps(store.fact_list(), indent=2))
    logger.debug("Exported facts JSON")


def _backup_lancedb(tmp: Path) -> None:
    src = Path("/var/holmium/memory/lancedb")
    if src.exists():
        dst = tmp / "lancedb"
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        logger.debug("Backed up LanceDB")


def _backup_vision_docs(tmp: Path) -> None:
    src = Path("/var/holmium/vision_docs")
    if src.exists():
        dst = tmp / "vision_docs"
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        logger.debug("Backed up vision docs")


def _backup_sessions(tmp: Path) -> None:
    src = Path("/var/holmium/sessions")
    if src.exists():
        dst = tmp / "sessions"
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        logger.debug("Backed up sessions")


def _backup_notes(tmp: Path) -> None:
    store = SQLiteStore()
    notes_path = tmp / "notes_export.json"
    notes_path.write_text(json.dumps(store.notes_list(), indent=2))
    logger.debug("Exported notes")


def _backup_config(tmp: Path) -> None:
    config_src = Path("/etc/holmium/config.json")
    if config_src.exists():
        try:
            data = json.loads(config_src.read_text())
            sensitive_keys = {"holmium_token", "github_token", "ntfy_topic"}
            for key in sensitive_keys:
                if key in data:
                    data[key] = "REDACTED"
            (tmp / "config.json").write_text(json.dumps(data, indent=2))
            logger.debug("Backed up config (secrets redacted)")
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Config backup failed: %s", exc)


def _create_zip(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for item in source_dir.rglob("*"):
            if item.is_file():
                arcname = str(item.relative_to(source_dir))
                zf.write(str(item), arcname)
