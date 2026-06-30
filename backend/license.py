"""Holmium Licensing System — Ed25519 signed license keys.
- Key pair generation
- License signing (key + email + expiry)
- Local verification
- Machine binding (via /etc/machine-id)
- Subscription status check
"""

import json
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from nacl.bindings import (
    crypto_sign_keypair,
    crypto_sign,
    crypto_sign_open,
)

PUBLIC_KEY_PATH = Path("/etc/holmium/license.pub")
PRIVATE_KEY_PATH = Path("/etc/holmium/license.key")  # only on Stripe backend
LICENSE_PATH = Path("/etc/holmium/license.json")
MACHINE_ID_PATH = Path("/etc/machine-id")


class LicenseError(Exception):
    pass


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate Ed25519 key pair. Returns (public_key, private_key)."""
    pk, sk = crypto_sign_keypair()
    return pk, sk


def save_public_key(pk: bytes, path: Path = PUBLIC_KEY_PATH):
    """Save base64-encoded public key."""
    path.write_text(base64.b64encode(pk).decode())


def load_public_key(path: Path = PUBLIC_KEY_PATH) -> bytes:
    """Load base64-encoded public key."""
    return base64.b64decode(path.read_text().strip())


def sign_license(
    license_key: str,
    email: str,
    expiry: str,  # ISO 8601 date
    sk: bytes,
) -> str:
    """Sign license data. Returns base64 signature."""
    data = json.dumps({"key": license_key, "email": email, "expiry": expiry}, separators=(",", ":")).encode()
    sig = crypto_sign(data, sk)
    return base64.b64encode(sig).decode()


def verify_license(
    signature_b64: str,
    license_key: str,
    email: str,
    expiry: str,
    pk: bytes,
) -> bool:
    """Verify license signature. Returns True if valid."""
    try:
        sig = base64.b64decode(signature_b64)
        data = json.dumps({"key": license_key, "email": email, "expiry": expiry}, separators=(",", ":")).encode()
        crypto_sign_open(sig, pk)
        return True
    except Exception:
        return False


def get_machine_id() -> str:
    """Get machine ID for hardware binding."""
    try:
        return MACHINE_ID_PATH.read_text().strip()
    except FileNotFoundError:
        return "unknown"


def create_license_file(
    license_key: str,
    email: str,
    expiry: str,
    signature_b64: str,
    path: Path = LICENSE_PATH,
):
    """Write license file to disk."""
    data = {
        "license_key": license_key,
        "email": email,
        "expiry": expiry,
        "signature": signature_b64,
        "machine_id": get_machine_id(),
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)


def load_license(path: Path = LICENSE_PATH) -> Optional[dict]:
    """Load license file from disk."""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def check_license(
    pk: Optional[bytes] = None,
    path: Path = LICENSE_PATH,
) -> tuple[bool, str]:
    """Check if installed license is valid.
    Returns (is_valid, message).
    
    Checks:
    1. License file exists
    2. Signature is valid
    3. Not expired
    4. Machine ID matches (if bound)
    """
    lic = load_license(path)
    if lic is None:
        return False, "No license found. Please activate Holmium."

    if pk is None:
        try:
            pk = load_public_key()
        except FileNotFoundError:
            return False, "No public key found. Corrupt installation."

    # Check signature
    if not verify_license(
        lic["signature"],
        lic["license_key"],
        lic["email"],
        lic["expiry"],
        pk,
    ):
        return False, "License signature invalid. Tampered or forged."

    # Check expiry
    try:
        expiry = datetime.fromisoformat(lic["expiry"])
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry:
            return False, f"License expired on {lic['expiry']}. Renew at holmium.ai."
    except (ValueError, KeyError):
        return False, "Invalid expiry date in license."

    # Check machine binding
    current_mid = get_machine_id()
    stored_mid = lic.get("machine_id", "")
    if stored_mid and stored_mid != current_mid:
        return False, f"License bound to different machine. Contact support."

    # Check how long until expiry
    days_left = (expiry - datetime.now(timezone.utc)).days
    if days_left < 7:
        return True, f"License valid — {days_left} days remaining. Renew soon."
    return True, f"License valid — {days_left} days remaining."


def days_remaining(path: Path = LICENSE_PATH) -> int:
    """Get days until license expiry. Returns -1 if expired, -2 if no license."""
    lic = load_license(path)
    if lic is None:
        return -2
    try:
        expiry = datetime.fromisoformat(lic["expiry"])
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return (expiry - datetime.now(timezone.utc)).days
    except (ValueError, KeyError):
        return -2


def format_license_status(path: Path = LICENSE_PATH) -> str:
    """Human-readable license status."""
    valid, msg = check_license(path=path)
    if valid:
        days = days_remaining(path=path)
        return f"✅ {msg}" if days > 7 else f"⚠️ {msg}"
    return f"❌ {msg}"
