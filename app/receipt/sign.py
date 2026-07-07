"""HMAC-SHA256 signing over the canonical receipt body.

SIGNING_KEY comes from the environment only. It is never logged and never
appears in any response.
"""

import hashlib
import hmac
import json
import os
from typing import Any

_ENV_VAR = "SIGNING_KEY"


class SigningKeyMissingError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(f"{_ENV_VAR} is not set; the service cannot issue or verify receipts")


def _signing_key() -> bytes:
    key = os.environ.get(_ENV_VAR, "")
    if not key:
        raise SigningKeyMissingError()
    return key.encode()


def canonical_body(fields: dict[str, Any]) -> bytes:
    """Deterministic serialization: sorted keys, no whitespace, no signature field."""
    body = {k: v for k, v in fields.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sign(fields: dict[str, Any]) -> str:
    return hmac.new(_signing_key(), canonical_body(fields), hashlib.sha256).hexdigest()


def verify_signature(fields: dict[str, Any]) -> bool:
    """Recompute the signature over every non-signature field; compare in constant time."""
    presented = fields.get("signature", "")
    if not isinstance(presented, str) or not presented:
        return False
    return hmac.compare_digest(sign(fields), presented)
