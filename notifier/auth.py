"""HMAC-SHA256 signature verification for inbound webhooks.

The Google Apps Script shim signs the raw request body with a shared
secret and sets it as the X-Signature header. This module verifies
that signature using a constant-time comparison to prevent timing
attacks.
"""
import hashlib
import hmac
import os
from typing import Optional


SIGNATURE_HEADER = "X-Signature"


class AuthError(Exception):
    """Raised when a webhook signature is missing or invalid."""


def compute_signature(body: bytes, secret: str) -> str:
    """Compute hex HMAC-SHA256 of body using secret. Used by GAS via
    `Utilities.computeHmacSha256Signature` (see gas/sendTele_v2.gs)."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, signature: Optional[str]) -> bytes:
    """Verify the X-Signature header against the body. Returns body on
    success. Raises AuthError on any failure.

    Use `hmac.compare_digest` to avoid timing side-channels.
    """
    secret = os.getenv("WEBHOOK_SECRET")
    if not secret:
        raise AuthError("WEBHOOK_SECRET is not configured on the server")

    if not signature:
        raise AuthError("Missing X-Signature header")

    expected = compute_signature(body, secret)
    if not hmac.compare_digest(expected, signature):
        raise AuthError("Invalid X-Signature")

    return body
