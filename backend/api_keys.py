"""External API key system — create, list, revoke, validate."""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

from ..memory.sqlite_store import SQLiteStore
from .logger import get_logger

logger = get_logger("api_keys")


def api_key_create(label: str) -> Optional[str]:
    store = SQLiteStore()
    raw_key = secrets.token_hex(32)
    key_hash = _hash_key(raw_key)
    store.api_key_set(key_hash, label)
    logger.info("API key created: %s", label)
    return raw_key


def api_key_list() -> list[dict]:
    store = SQLiteStore()
    keys = store.api_key_list(only_enabled=False)
    result = []
    for k in keys:
        result.append({
            "label": k.get("label", ""),
            "created_at": k.get("created_at", ""),
            "last_used": k.get("last_used"),
            "enabled": bool(k.get("enabled", 0)),
        })
    return result


def api_key_revoke(label: str) -> bool:
    store = SQLiteStore()
    keys = store.api_key_list(only_enabled=False)
    for k in keys:
        if k.get("label") == label:
            key_hash = _hash_key_for_label(label, store)
            if key_hash:
                return store.api_key_revoke(key_hash)
    logger.warning("API key not found for revocation: %s", label)
    return False


def validate_api_key(key: str) -> bool:
    store = SQLiteStore()
    key_hash = _hash_key(key)
    row = store.api_key_get(key_hash)
    if row is not None and row.get("enabled", 0) == 1:
        store.api_key_touch(key_hash)
        return True
    return False


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _hash_key_for_label(label: str, store: SQLiteStore) -> Optional[str]:
    keys = store.api_key_list(only_enabled=False)
    for k in keys:
        if k.get("label") == label:
            return k.get("key_hash")
    return None
