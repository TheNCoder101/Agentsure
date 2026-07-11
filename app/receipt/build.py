"""Receipt builder: hash the inputs, assemble the canonical body, sign it."""

import hashlib
import uuid
from datetime import UTC, datetime

from app.models import Receipt, RigorLevel, SourceDocument, Verdict
from app.receipt import ed25519
from app.receipt.sign import sign

ENGINE_VERSION = "0.1.0"


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build_receipt(
    output: str,
    sources: list[SourceDocument],
    verdict: Verdict,
    rigor_level: RigorLevel,
) -> Receipt:
    receipt = Receipt(
        receipt_id=str(uuid.uuid4()),
        issued_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        verdict=verdict,
        output_sha256=sha256_hex(output),
        sources_sha256=[sha256_hex(doc.text) for doc in sources],
        rigor_level=rigor_level,
        engine_version=ENGINE_VERSION,
        signature="",
        ed25519_signature="",
    )
    fields = receipt.model_dump(mode="json")
    return receipt.model_copy(
        update={
            "signature": sign(fields),
            "ed25519_signature": ed25519.sign(fields),
        }
    )
