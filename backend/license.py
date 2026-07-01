"""Holmium Licensing System — Lemon Squeezy + Ed25519 signed license keys.
- Key pair generation
- License signing (key + email + expiry)
- Local verification
- Machine binding (via /etc/machine-id)
- Lemon Squeezy online validation
- Special developer key for free access
"""

import json
import base64
import hashlib
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import httpx
from nacl.bindings import (
    crypto_sign_keypair,
    crypto_sign,
    crypto_sign_open,
)

PUBLIC_KEY_PATH = Path("/etc/holmium/license.pub")
PRIVATE_KEY_PATH = Path("/etc/holmium/license.key")
LICENSE_PATH = Path("/etc/holmium/license.json")
MACHINE_ID_PATH = Path("/etc/machine-id")

# Lemon Squeezy config
LS_API_URL = "https://api.lemonsqueezy.com/v1/licenses"
LS_STORE_ID = "holmiumai"

# Developer key — bypasses all checks, free lifetime access.
# Only the Holmium author knows this key.
DEV_KEY = "HOLM-DEV-QWEN3-35B-A3B-AAAA-0000"

LEMON_SQUEEZY_API_KEY = os.environ.get("LEMON_SQUEEZY_API_KEY", "")


class LicenseError(Exception):
    pass


def is_dev_key(license_key: str) -> bool:
    return license_key.strip().upper() == DEV_KEY


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
    expiry: str,
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
        mid = MACHINE_ID_PATH.read_text().strip()
        return hashlib.sha256(mid.encode()).hexdigest()[:16]
    except FileNotFoundError:
        return "unknown"


def validate_with_lemonsqueezy(license_key: str, machine_id: str) -> tuple[bool, str, Optional[dict]]:
    """Validate license key with Lemon Squeezy API.
    Returns (is_valid, message, license_data).
    """
    if is_dev_key(license_key):
        return True, "Developer key — free lifetime access.", {
            "license_key": license_key,
            "email": "dev@holmium.ai",
            "expiry": "2099-12-31T23:59:59Z",
            "status": "active",
        }

    try:
        resp = httpx.post(
            f"{LS_API_URL}/validate",
            json={
                "license_key": license_key,
                "instance_id": machine_id,
                "instance_name": f"holmium-{machine_id[:8]}",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            status = data.get("valid", False)
            if status:
                lic_data = data.get("license", {})
                meta = lic_data.get("meta", {})
                expiry = meta.get("expires_at", "")
                email = lic_data.get("email", "")
                return True, "License key valid.", {
                    "license_key": license_key,
                    "email": email,
                    "expiry": expiry,
                    "status": "active",
                }
            else:
                return False, "License key is not valid or has been revoked.", None
        elif resp.status_code == 404:
            return False, "License key not found.", None
        else:
            return False, f"License server error ({resp.status_code}). Try again later.", None

    except httpx.TimeoutException:
        return False, "License server unreachable. Check your internet connection.", None
    except Exception as e:
        return False, f"License validation error: {e}", None


def activate_with_lemonsqueezy(license_key: str, machine_id: str) -> tuple[bool, str, Optional[dict]]:
    """Activate a license key with Lemon Squeezy (binds to machine)."""
    if is_dev_key(license_key):
        return True, "Developer key activated.", {
            "license_key": license_key,
            "email": "dev@holmium.ai",
            "expiry": "2099-12-31T23:59:59Z",
        }

    try:
        resp = httpx.post(
            f"{LS_API_URL}/activate",
            json={
                "license_key": license_key,
                "instance_id": machine_id,
                "instance_name": f"holmium-{machine_id[:8]}",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            status = data.get("valid", False)
            if status:
                lic_data = data.get("license", {})
                meta = lic_data.get("meta", {})
                expiry = meta.get("expires_at", "")
                email = lic_data.get("email", "")
                return True, "License activated.", {
                    "license_key": license_key,
                    "email": email,
                    "expiry": expiry,
                }
            else:
                error = data.get("error", "Activation failed.")
                return False, f"Activation failed: {error}", None
        elif resp.status_code == 422:
            error = resp.json().get("error", "Instance limit reached.")
            return False, f"Activation failed: {error}", None
        else:
            return False, f"Activation server error ({resp.status_code}).", None

    except httpx.TimeoutException:
        return False, "License server unreachable.", None
    except Exception as e:
        return False, f"Activation error: {e}", None


def create_license_file(
    license_key: str,
    email: str,
    expiry: str,
    signature_b64: str = "",
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
        "last_verified_at": datetime.now(timezone.utc).isoformat(),
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
    online: bool = True,
) -> tuple[bool, str]:
    """Check if installed license is valid.
    Returns (is_valid, message).

    Checks:
    1. License file exists
    2. Developer key bypass
    3. Lemon Squeezy online validation
    4. Signature is valid (fallback)
    5. Not expired
    6. Machine ID matches
    """
    lic = load_license(path)
    if lic is None:
        return False, "No license found. Please activate Holmium."

    license_key = lic.get("license_key", "")

    # Developer key — instant pass
    if is_dev_key(license_key):
        return True, "Developer license — free lifetime access."

    # Online validation via Lemon Squeezy (primary)
    if online:
        machine_id = get_machine_id()
        valid, msg, data = validate_with_lemonsqueezy(license_key, machine_id)
        if not valid:
            return False, msg

        # Update stored expiry and last verified from server
        now = datetime.now(timezone.utc)
        if data and data.get("expiry"):
            lic["expiry"] = data["expiry"]
        lic["last_verified_at"] = now.isoformat()
        create_license_file(
            license_key=data["license_key"],
            email=data.get("email", lic.get("email", "")),
            expiry=data["expiry"],
            signature_b64=lic.get("signature", ""),
        )
        days_left = _days_until(lic.get("expiry", ""))
        if days_left < 0:
            return False, "License has expired. Renew at holmium.ai."
        if days_left < 7:
            return True, f"License valid — {days_left} days remaining. Renew soon."
        return True, f"License valid — {days_left} days remaining."

    # Offline fallback: Ed25519 signature check
    if pk is None:
        try:
            pk = load_public_key()
        except FileNotFoundError:
            return False, "No public key found. Corrupt installation."

    # 30-day online verification required
    last_verified = lic.get("last_verified_at", "")
    if last_verified:
        try:
            lv = datetime.fromisoformat(last_verified)
            if lv.tzinfo is None:
                lv = lv.replace(tzinfo=timezone.utc)
            days_since_verify = (datetime.now(timezone.utc) - lv).days
            if days_since_verify >= 30:
                return False, f"License not verified in {days_since_verify} days. Connect to the internet and try again."
        except (ValueError, TypeError):
            pass
    else:
        return False, "License has not been verified online yet. Connect to the internet and try again."

    if not verify_license(
        lic.get("signature", ""),
        license_key,
        lic.get("email", ""),
        lic.get("expiry", ""),
        pk,
    ):
        return False, "License signature invalid. Tampered or forged."

    try:
        expiry = datetime.fromisoformat(lic["expiry"])
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry:
            return False, f"License expired on {lic['expiry']}. Renew at holmium.ai."
    except (ValueError, KeyError):
        return False, "Invalid expiry date in license."

    current_mid = get_machine_id()
    stored_mid = lic.get("machine_id", "")
    if stored_mid and stored_mid != current_mid:
        return False, "License bound to different machine. Contact support."

    days_left = _days_until(lic["expiry"])
    if days_left < 7:
        return True, f"License valid — {days_left} days remaining. Renew soon."
    return True, f"License valid — {days_left} days remaining."


def _days_until(expiry_str: str) -> int:
    """Calculate days until expiry. Returns -1 if expired."""
    try:
        expiry = datetime.fromisoformat(expiry_str)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return (expiry - datetime.now(timezone.utc)).days
    except (ValueError, KeyError):
        return -2


def days_remaining(path: Path = LICENSE_PATH) -> int:
    """Get days until license expiry. Returns -1 if expired, -2 if no license."""
    lic = load_license(path)
    if lic is None:
        return -2
    return _days_until(lic.get("expiry", ""))


def format_license_status(path: Path = LICENSE_PATH) -> str:
    """Human-readable license status."""
    valid, msg = check_license(path=path, online=True)
    if valid:
        days = days_remaining(path=path)
        return f"License OK — {days} days remaining" if days > 7 else f"⚠ License — {days} days left, renew soon"
    return f"✗ {msg}"
