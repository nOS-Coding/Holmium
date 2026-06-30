"""Self-update system — git fetch, pull, pip upgrade, service restart."""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger("updater")

_REPO_DIR = Path("/opt/holmium")
_VERSION_FILE = Path("/etc/holmium/VERSION")
_CHANGELOG_FILE = Path("/etc/holmium/CHANGELOG.md")


def get_version() -> str:
    try:
        if _VERSION_FILE.exists():
            return _VERSION_FILE.read_text().strip()
    except OSError as exc:
        logger.warning("Failed to read version file: %s", exc)

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            capture_output=True, text=True, timeout=10,
            cwd=str(_REPO_DIR),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return "unknown"


def _run_git(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, timeout=timeout,
        cwd=str(_REPO_DIR),
    )


async def check_for_updates() -> dict:
    try:
        _run_git(["fetch", "origin"])
        result = _run_git(["rev-list", "--count", "HEAD..origin/main"])
        ahead = int(result.stdout.strip()) if result.returncode == 0 else 0

        local = _run_git(["rev-parse", "--short", "HEAD"])
        remote = _run_git(["rev-parse", "--short", "origin/main"])

        return {
            "updates_available": ahead > 0,
            "commits_behind": ahead,
            "local_commit": local.stdout.strip() if local.returncode == 0 else "",
            "remote_commit": remote.stdout.strip() if remote.returncode == 0 else "",
        }
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        logger.warning("Update check failed: %s", exc)
        return {"updates_available": False, "error": str(exc)}


async def perform_update() -> dict:
    try:
        diff_result = _run_git(["log", "HEAD..origin/main", "--oneline", "--no-decorate"])
        diff_summary = diff_result.stdout.strip() if diff_result.returncode == 0 else ""

        pull_result = _run_git(["pull", "origin", "main"])
        if pull_result.returncode != 0:
            return {"success": False, "error": f"git pull failed: {pull_result.stderr}"}

        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"],
            capture_output=True, text=True, timeout=120,
            cwd=str(_REPO_DIR),
        )

        if _REPO_DIR.joinpath("openrc").exists():
            subprocess.run(
                ["rc-service", "holmium-backend", "restart"],
                capture_output=True, timeout=30,
            )
            subprocess.run(
                ["rc-service", "holmium-vllm", "restart"],
                capture_output=True, timeout=30,
            )

        new_version = get_version()
        logger.info("Update completed: %s", new_version)

        return {
            "success": True,
            "new_version": new_version,
            "diff_summary": diff_summary[:2000],
            "pip_upgrade": pip_result.stdout[:500] if pip_result.returncode == 0 else pip_result.stderr[:500],
        }
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        logger.exception("Update failed")
        return {"success": False, "error": str(exc)}


def bump_version() -> None:
    try:
        from ..os.version import read_version, bump_patch
        old_version = read_version(str(_VERSION_FILE))
        new_version = bump_patch(str(_VERSION_FILE), write=True)
        _VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)

        summary = _run_git(["log", "-1", "--oneline"]).stdout.strip()
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        changelog_entry = f"## {new_version} ({date_str})\n\n{summary}\n\n"
        if _CHANGELOG_FILE.exists():
            existing = _CHANGELOG_FILE.read_text()
            _CHANGELOG_FILE.write_text(changelog_entry + existing)
        else:
            _CHANGELOG_FILE.write_text(f"# Changelog\n\n{changelog_entry}")

        logger.info("Version bumped: %s -> %s", ".".join(map(str, old_version)), new_version)
    except Exception as exc:
        logger.exception("Version bump failed: %s", exc)
