"""Lemon Squeezy webhook handler for Holmium licensing.
Replaces the old Stripe handler. Processes subscription events
and updates local license files.
"""

import json
import hashlib
import hmac
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException

from .license import (
    create_license_file,
    load_license,
    generate_keypair,
    save_public_key,
    sign_license,
    PUBLIC_KEY_PATH,
    PRIVATE_KEY_PATH,
)

router = APIRouter()

# Lemon Squeezy webhook secret from environment
LS_WEBHOOK_SECRET = os.environ.get("LS_WEBHOOK_SECRET", "")


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify Lemon Squeezy webhook signature."""
    if not LS_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        LS_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/lemonsqueezy/webhook")
async def lemonsqueezy_webhook(request: Request):
    """Handle Lemon Squeezy subscription webhooks."""
    body = await request.body()
    signature = request.headers.get("x-signature", "")

    if LS_WEBHOOK_SECRET and not verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = json.loads(body)
    event_name = data.get("meta", {}).get("event_name", "")

    # Extract license info from the payload
    lic_data = data.get("data", {}).get("attributes", {})
    customer_email = lic_data.get("user_email", "")
    license_key = lic_data.get("key", "")
    expires_at = lic_data.get("expires_at", "")

    if not license_key or not customer_email:
        return {"status": "ignored", "reason": "missing key or email"}

    # Handle specific events
    if event_name in ("order_created", "subscription_created", "subscription_updated"):
        # Generate Ed25519 key pair on first use
        if not PUBLIC_KEY_PATH.exists():
            pk, sk = generate_keypair()
            save_public_key(pk)
            PRIVATE_KEY_PATH.write_text(sk.hex())

        # Sign the license
        if PRIVATE_KEY_PATH.exists():
            sk = bytes.fromhex(PRIVATE_KEY_PATH.read_text().strip())
            signature = sign_license(license_key, customer_email, expires_at, sk)
        else:
            signature = ""

        # Write license file
        create_license_file(
            license_key=license_key,
            email=customer_email,
            expiry=expires_at,
            signature_b64=signature,
        )

        return {"status": "ok", "license_key": license_key}

    elif event_name == "subscription_cancelled":
        # Mark as expired
        lic = load_license()
        if lic and lic["license_key"] == license_key:
            lic["expiry"] = datetime.now(timezone.utc).isoformat()
            create_license_file(
                license_key=lic["license_key"],
                email=lic["email"],
                expiry=lic["expiry"],
                signature_b64=lic.get("signature", ""),
            )
        return {"status": "cancelled", "license_key": license_key}

    return {"status": "ignored", "event": event_name}
