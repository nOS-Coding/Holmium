"""Image output routing — TUI, macOS, Android, CLI."""

import base64
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger("image_router")

_IMAGES_DIR = Path("/var/holmium/images")
_MAC_PICTURES = Path.home() / "Pictures" / "Holmium"
_DEBIAN_DIR = Path("/mnt/debian/holmium/images")
_WG_TCP_HOST = "10.0.0.1"
_WG_TCP_PORT = 2222


def _ensure_dirs() -> None:
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def route_image(image_path: str, client_type: str) -> str:
    _ensure_dirs()
    src = Path(image_path)
    if not src.exists():
        logger.error("Image not found: %s", image_path)
        return f"Error: image not found at {image_path}"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest_filename = f"{timestamp}_{src.name}"
    dest_path = _IMAGES_DIR / dest_filename

    try:
        shutil.copy2(str(src), str(dest_path))
        logger.info("Image saved locally: %s", dest_path)
    except OSError as exc:
        logger.error("Failed to copy image: %s", exc)
        return f"Error: {exc}"

    if client_type == "TUI":
        return _route_tui(dest_path)
    elif client_type == "macOS":
        return _route_macos(dest_path, dest_filename)
    elif client_type == "Android":
        return _route_android(dest_path)
    else:
        return _route_cli(dest_path)


def _route_tui(image_path: Path) -> str:
    try:
        _debian_copy(image_path)
        logger.debug("Image copied to Debian for TUI")
    except Exception as exc:
        logger.warning("Debian copy failed: %s", exc)
    return str(image_path)


def _route_macos(image_path: Path, filename: str) -> str:
    try:
        _MAC_PICTURES.mkdir(parents=True, exist_ok=True)
        mac_dest = _MAC_PICTURES / filename
        shutil.copy2(str(image_path), str(mac_dest))
        logger.info("Image transferred to macOS: %s", mac_dest)

        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(10)
                sock.connect((_WG_TCP_HOST, _WG_TCP_PORT))
                with open(image_path, "rb") as f:
                    data = f.read()
                sock.sendall(len(data).to_bytes(8, "big") + data)
                logger.debug("Image sent via WG TCP")
        except Exception as exc:
            logger.warning("WG TCP transfer failed: %s", exc)

        return str(mac_dest)
    except OSError as exc:
        logger.error("macOS route failed: %s", exc)
        return str(image_path)


def _route_android(image_path: Path) -> str:
    try:
        b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        logger.debug("Image base64-encoded (%d bytes)", len(b64))
        return b64
    except OSError as exc:
        logger.error("Android route failed: %s", exc)
        return ""


def _route_cli(image_path: Path) -> str:
    try:
        _debian_copy(image_path)
    except Exception as exc:
        logger.warning("Debian copy failed: %s", exc)
    print(f"Image saved: {image_path}")
    return str(image_path)


def _debian_copy(image_path: Path) -> None:
    if _DEBIAN_DIR.exists():
        shutil.copy2(str(image_path), str(_DEBIAN_DIR / image_path.name))
        logger.debug("Image copied to Debian: %s", _DEBIAN_DIR / image_path.name)
