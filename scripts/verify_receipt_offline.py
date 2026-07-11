#!/usr/bin/env python3
"""Standalone Ed25519 receipt verifier.

Verifies a Verification Gate receipt's authenticity completely offline: no
network call to the API, no need to trust that Agentsure is still operating
or cooperative. This is deliberately self-contained (only stdlib + the
`cryptography` package) so it can be copied out and run on its own — a
regulator or auditor should not have to install this whole codebase to
check one receipt.

Fetch the public key once from GET /.well-known/agentsure-receipt-key and
cache it; it only changes on a deliberate key rotation.

Usage:
    python verify_receipt_offline.py receipt.json <public_key_b64>
"""

import base64
import json
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_SIGNATURE_FIELDS = frozenset({"signature", "ed25519_signature"})


def canonical_body(fields: dict[str, object]) -> bytes:
    """Must exactly match app/receipt/sign.py's canonical_body — this is an
    intentional, small duplication so this file has zero dependency on the
    rest of the codebase."""
    body = {k: v for k, v in fields.items() if k not in _SIGNATURE_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify_receipt(receipt: dict[str, object], public_key_b64: str) -> bool:
    presented = receipt.get("ed25519_signature", "")
    if not isinstance(presented, str) or not presented:
        return False
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        signature = base64.b64decode(presented, validate=True)
    except (ValueError, TypeError):
        return False
    try:
        public_key.verify(signature, canonical_body(receipt))
        return True
    except InvalidSignature:
        return False


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    receipt_path, public_key_b64 = sys.argv[1], sys.argv[2]
    with open(receipt_path, encoding="utf-8") as f:
        receipt = json.load(f)
    valid = verify_receipt(receipt, public_key_b64)
    print("VALID" if valid else "INVALID")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
