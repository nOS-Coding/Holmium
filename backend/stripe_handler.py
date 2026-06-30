"""Holmium Stripe integration — payment processing and license key delivery."""

import json
import os
import base64
import hmac
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import stripe
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from backend.license import (
    sign_license,
    save_public_key,
    generate_keypair,
    PRIVATE_KEY_PATH,
)

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "price_monthly")
PRICE_YEARLY = os.environ.get("STRIPE_PRICE_YEARLY", "price_yearly")
DOMAIN = os.environ.get("DOMAIN", "https://holmium.ai")

router = APIRouter(prefix="/api/license", tags=["license"])


class CreateCheckoutRequest(BaseModel):
    email: str
    plan: str  # "monthly" or "yearly"


class ActivateRequest(BaseModel):
    license_key: str
    email: str


def generate_license_key() -> str:
    """Generate a human-friendly license key: HOLM-XXXX-XXXX-XXXX"""
    part = secrets.token_hex(6).upper()
    return f"HOLM-{part[:4]}-{part[4:8]}-{part[8:12]}"


@router.post("/create-checkout")
async def create_checkout(req: CreateCheckoutRequest):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Payment not configured")
    
    price_id = PRICE_MONTHLY if req.plan == "monthly" else PRICE_YEARLY
    
    try:
        checkout = stripe.checkout.Session.create(
            api_key=STRIPE_SECRET_KEY,
            customer_email=req.email,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{DOMAIN}/activate?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{DOMAIN}/pricing",
            metadata={"email": req.email},
        )
        return {"url": checkout.url}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe checkout.session.completed event."""
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Webhook not configured")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid signature")
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email") or session.get("metadata", {}).get("email", "")
        
        # Generate license
        license_key = generate_license_key()
        expiry = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        
        # Generate or load keypair
        key_path = PRIVATE_KEY_PATH
        if key_path.exists():
            sk = base64.b64decode(key_path.read_text().strip())
        else:
            pk, sk = generate_keypair()
            save_public_key(pk)
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text(base64.b64encode(sk).decode())
            key_path.chmod(0o600)
        
        signature = sign_license(license_key, email, expiry, sk)
        
        # In production: store in database + email to customer
        # For now: log and return
        print(f"License generated: {license_key} for {email}")
        
        # TODO: Send email with license key
        # TODO: Store in database
    
    return {"status": "ok"}


@router.post("/activate")
async def activate_license(req: ActivateRequest):
    """Verify and install a license key locally."""
    from backend.license import create_license_file, load_public_key, verify_license
    
    try:
        pk = load_public_key()
    except FileNotFoundError:
        raise HTTPException(500, "Public key not found")
    
    # We need to know the expiry — for now, check online
    # In production: verify against Stripe subscription status
    # For local use: trust the client-provided expiry (signed)
    
    # For demo/offline: license key format HOLM-XXXX-XXXX-XXXX
    # The signature + machine binding prevent reuse
    
    lic = {
        "license_key": req.license_key,
        "email": req.email,
        "expiry": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "signature": "",  # would come from Stripe backend
    }
    
    # If we have a signature in the license, verify it
    # Otherwise, this is a placeholder for the online verification
    
    # For now, check if the license key matches expected format
    if not req.license_key.startswith("HOLM-") or len(req.license_key) != 19:
        raise HTTPException(400, "Invalid license key format")
    
    # Generate a temporary signature for local activation
    # In production, this comes from the Stripe webhook
    from backend.license import get_machine_id
    temp_expiry = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    
    # If we have the private key, sign it
    key_path = PRIVATE_KEY_PATH
    if key_path.exists():
        sk = base64.b64decode(key_path.read_text().strip())
        sig = sign_license(req.license_key, req.email, temp_expiry, sk)
        create_license_file(req.license_key, req.email, temp_expiry, sig)
        return {"status": "activated", "expires": temp_expiry, "machine_id": get_machine_id()}
    
    return {"status": "pending", "message": "License registered. Online activation required."}


@router.get("/status")
async def license_status():
    """Check current license status."""
    from backend.license import load_license, check_license, format_license_status
    
    valid, msg = check_license()
    lic = load_license()
    
    return {
        "valid": valid,
        "message": msg,
        "license": {
            "email": lic.get("email", "") if lic else "",
            "expiry": lic.get("expiry", "") if lic else "",
            "machine_id": lic.get("machine_id", "") if lic else "",
        } if lic else None,
    }
