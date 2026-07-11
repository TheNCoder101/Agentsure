"""Ed25519 asymmetric receipt signing.

HMAC-SHA256 (sign.py) proves a receipt hasn't been tampered with, but only
we can check it — POST /receipt/verify calls back to our own API, which
means a regulator has to trust us to vouch for our own signature. That
undercuts the "hand this to a regulator" pitch: real audit-grade proof has
to be checkable by someone who doesn't trust us at all.

Ed25519 signs the same canonical body asymmetrically. Anyone holding our
published public key (GET /.well-known/agentsure-receipt-key) can verify a
receipt completely offline — no network call to us, no need to trust that
we're still operating or still cooperative. `verify()` below is exactly
that check; scripts/verify_receipt_offline.py is a copy-and-run version of
it for someone who doesn't want to install this codebase at all.

ED25519_SIGNING_KEY is a base64-encoded 32-byte seed, env-only, never
logged, never returned in any response — same handling as SIGNING_KEY.
"""

import base64
import os
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.receipt.sign import canonical_body

_ENV_VAR = "ED25519_SIGNING_KEY"


class Ed25519KeyMissingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(f"{_ENV_VAR} is not set; the service cannot issue or verify receipts")


def _private_key() -> Ed25519PrivateKey:
    seed_b64 = os.environ.get(_ENV_VAR, "")
    if not seed_b64:
        raise Ed25519KeyMissingError()
    try:
        seed = base64.b64decode(seed_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise Ed25519KeyMissingError() from exc
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_key_b64() -> str:
    """The published public key — safe to expose publicly, meant to be
    cached long-term by anyone who wants to verify our receipts offline."""
    raw = _private_key().public_key().public_bytes_raw()
    return base64.b64encode(raw).decode()


def sign(fields: dict[str, Any]) -> str:
    signature = _private_key().sign(canonical_body(fields))
    return base64.b64encode(signature).decode()


def verify(fields: dict[str, Any], public_key_b64_str: str) -> bool:
    """Independent of any server-side key access — only needs the published
    public key. This is the check a third party runs without ever calling
    our API."""
    presented = fields.get("ed25519_signature", "")
    if not isinstance(presented, str) or not presented:
        return False
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64_str))
        signature = base64.b64decode(presented, validate=True)
    except (ValueError, TypeError):
        return False
    try:
        public_key.verify(signature, canonical_body(fields))
        return True
    except InvalidSignature:
        return False
