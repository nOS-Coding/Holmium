"""Encrypted secrets vault — Fernet + PBKDF2."""

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from tools.registry import register_tool

SALT_PATH = Path("/etc/holmium/vault.salt")
VAULT_PATH = Path("/var/holmium/vault.enc")

_passphrase: Optional[str] = None


def set_passphrase(passphrase: str) -> None:
    global _passphrase
    _passphrase = passphrase


def _ensure_salt() -> bytes:
    if SALT_PATH.is_file():
        return SALT_PATH.read_bytes()
    salt = os.urandom(16)
    SALT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SALT_PATH.write_bytes(salt)
    return salt


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


def _get_fernet() -> Optional[Fernet]:
    passphrase = _passphrase or os.environ.get("HOLMIUM_VAULT_PASSPHRASE")
    if not passphrase:
        try:
            machine_id = Path("/etc/machine-id").read_text().strip()
            passphrase = machine_id
        except Exception:
            return None
    salt = _ensure_salt()
    key = _derive_key(passphrase, salt)
    return Fernet(key)


def _load_vault() -> Dict[str, str]:
    if not VAULT_PATH.is_file():
        return {}
    fernet = _get_fernet()
    if fernet is None:
        return {}
    try:
        encrypted = VAULT_PATH.read_bytes()
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode())
    except Exception:
        return {}


def _save_vault(data: Dict[str, str]) -> bool:
    fernet = _get_fernet()
    if fernet is None:
        return False
    try:
        VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        encrypted = fernet.encrypt(json.dumps(data).encode())
        VAULT_PATH.write_bytes(encrypted)
        return True
    except Exception:
        return False


@register_tool(
    "vault_add",
    "Store an encrypted key-value pair in the vault.",
    params_schema={
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Key name"},
            "value": {"type": "string", "description": "Value to encrypt and store"},
        },
        "required": ["key", "value"],
    },
)
def vault_add(key: str, value: str) -> bool:
    data = _load_vault()
    data[key] = value
    return _save_vault(data)


@register_tool(
    "vault_get",
    "Retrieve a decrypted value from the vault by key.",
    params_schema={
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Key name to retrieve"},
        },
        "required": ["key"],
    },
)
def vault_get(key: str) -> str:
    data = _load_vault()
    return data.get(key, "")


@register_tool(
    "vault_list",
    "List all key names stored in the vault (values remain encrypted).",
)
def vault_list() -> List[str]:
    data = _load_vault()
    return sorted(data.keys())


@register_tool(
    "vault_delete",
    "Delete a key-value pair from the vault.",
    params_schema={
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Key name to delete"},
        },
        "required": ["key"],
    },
)
def vault_delete(key: str) -> bool:
    data = _load_vault()
    if key not in data:
        return False
    del data[key]
    return _save_vault(data)


@register_tool(
    "vault_search",
    "Search vault key names matching a query.",
    params_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term to match against key names"},
        },
        "required": ["query"],
    },
)
def vault_search(query: str) -> List[str]:
    data = _load_vault()
    q = query.lower()
    return sorted(k for k in data if q in k.lower())
