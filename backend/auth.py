"""
FastAPI authentication dependency.

Requires X-Holmium-Token header, compared using hmac.compare_digest.
Also accepts valid API keys from the api_keys table.
"""

import hashlib
import hmac
from pathlib import Path

from fastapi import HTTPException, Request

from .logger import get_logger

logger = get_logger("auth")

_TOKEN_PATH = Path("/etc/holmium/token")
_cached_token: str | None = None


def _load_token() -> str:
    global _cached_token
    if _cached_token is not None:
        return _cached_token
    try:
        _cached_token = _TOKEN_PATH.read_text().strip()
    except FileNotFoundError:
        logger.error("Auth token file not found at %s", _TOKEN_PATH)
        _cached_token = ""
    return _cached_token


def _check_api_key(token: str) -> bool:
    try:
        from memory.sqlite_store import get_api_key
    except ImportError:
        return False

    key_hash = hashlib.sha256(token.encode()).hexdigest()
    row = get_api_key(key_hash)
    if row is not None:
        from memory.sqlite_store import mark_api_key_used
        mark_api_key_used(key_hash)
        return True
    return False


async def require_token(request: Request) -> None:
    token = _load_token()
    if not token:
        raise HTTPException(status_code=401, detail="Server not configured")

    header_token = request.headers.get("X-Holmium-Token", "")
    if not header_token:
        raise HTTPException(status_code=401, detail="Missing X-Holmium-Token header")

    if hmac.compare_digest(token, header_token):
        return

    if _check_api_key(header_token):
        return

    raise HTTPException(status_code=401, detail="Invalid token")
