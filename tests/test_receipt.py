"""Receipt integrity: canonical serialization, signing, tamper evidence."""

import pytest

from app.models import RigorLevel, SourceDocument, Verdict
from app.receipt.build import build_receipt, sha256_hex
from app.receipt.sign import SigningKeyMissingError, canonical_body, sign, verify_signature

_DOCS = [SourceDocument(id="doc-1", text="Revenue increased 12% to $4.1M.")]


def _receipt_fields() -> dict[str, object]:
    receipt = build_receipt("Revenue rose 12%.", _DOCS, Verdict.SUPPORTED, RigorLevel.STANDARD)
    return receipt.model_dump(mode="json")


class TestCanonicalSerialization:
    def test_deterministic_and_order_invariant(self) -> None:
        fields = {"b": 2, "a": 1, "c": [1, 2]}
        reordered = {"c": [1, 2], "a": 1, "b": 2}
        assert canonical_body(fields) == canonical_body(reordered)
        assert canonical_body(fields) == b'{"a":1,"b":2,"c":[1,2]}'

    def test_signature_field_excluded_from_body(self) -> None:
        assert canonical_body({"a": 1, "signature": "x"}) == canonical_body({"a": 1})

    def test_signature_reproducible(self) -> None:
        fields = _receipt_fields()
        assert sign(fields) == sign(dict(reversed(list(fields.items()))))


class TestReceiptBuild:
    def test_hashes_inputs(self) -> None:
        fields = _receipt_fields()
        assert fields["output_sha256"] == sha256_hex("Revenue rose 12%.")
        assert fields["sources_sha256"] == [sha256_hex(_DOCS[0].text)]
        assert fields["rigor_level"] == "standard"
        assert fields["verdict"] == "supported"

    def test_fresh_receipt_signature_verifies(self) -> None:
        assert verify_signature(_receipt_fields()) is True


class TestTamperEvidence:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("receipt_id", "00000000-0000-0000-0000-000000000000"),
            ("issued_at", "1999-01-01T00:00:00Z"),
            ("verdict", "unsupported"),
            ("output_sha256", "0" * 64),
            ("sources_sha256", ["0" * 64]),
            ("rigor_level", "strict"),
            ("engine_version", "9.9.9"),
        ],
    )
    def test_tampering_any_field_invalidates(self, field: str, value: object) -> None:
        fields = _receipt_fields()
        assert fields[field] != value, "tamper value must differ from the original"
        fields[field] = value
        assert verify_signature(fields) is False

    def test_tampered_signature_invalidates(self) -> None:
        fields = _receipt_fields()
        signature = str(fields["signature"])
        flipped = ("0" if signature[-1] != "0" else "1") + signature[1:]
        fields["signature"] = flipped[-1] + signature[:-1]
        assert verify_signature(fields) is False

    def test_missing_signature_is_invalid(self) -> None:
        fields = _receipt_fields()
        del fields["signature"]
        assert verify_signature(fields) is False


def test_signing_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGNING_KEY")
    with pytest.raises(SigningKeyMissingError):
        sign({"a": 1})
