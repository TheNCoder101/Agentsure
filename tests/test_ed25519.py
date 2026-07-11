"""Unit tests for Ed25519 asymmetric receipt signing."""

import base64

import pytest

from app.receipt import ed25519


class TestSignAndVerify:
    def test_valid_signature_verifies(self) -> None:
        fields = {"a": 1, "b": "two", "ed25519_signature": ""}
        fields["ed25519_signature"] = ed25519.sign(fields)
        assert ed25519.verify(fields, ed25519.public_key_b64()) is True

    def test_tampered_field_invalidates(self) -> None:
        fields = {"a": 1, "ed25519_signature": ""}
        fields["ed25519_signature"] = ed25519.sign(fields)
        fields["a"] = 2
        assert ed25519.verify(fields, ed25519.public_key_b64()) is False

    def test_tampered_signature_invalidates(self) -> None:
        fields = {"a": 1, "ed25519_signature": ""}
        fields["ed25519_signature"] = ed25519.sign(fields)
        raw = bytearray(base64.b64decode(fields["ed25519_signature"]))
        raw[0] ^= 0xFF
        fields["ed25519_signature"] = base64.b64encode(bytes(raw)).decode()
        assert ed25519.verify(fields, ed25519.public_key_b64()) is False

    def test_missing_signature_is_invalid(self) -> None:
        assert ed25519.verify({"a": 1}, ed25519.public_key_b64()) is False

    def test_wrong_public_key_is_invalid(self) -> None:
        fields = {"a": 1, "ed25519_signature": ""}
        fields["ed25519_signature"] = ed25519.sign(fields)
        # A different, unrelated keypair's public key must not validate.
        wrong_seed = base64.b64encode(b"0" * 32).decode()
        import os

        original = os.environ.get("ED25519_SIGNING_KEY")
        os.environ["ED25519_SIGNING_KEY"] = wrong_seed
        try:
            wrong_public_key = ed25519.public_key_b64()
        finally:
            if original is not None:
                os.environ["ED25519_SIGNING_KEY"] = original
        assert ed25519.verify(fields, wrong_public_key) is False

    def test_garbage_public_key_does_not_raise(self) -> None:
        fields = {"a": 1, "ed25519_signature": "not-valid-base64!!"}
        assert ed25519.verify(fields, "also-not-valid") is False

    def test_signature_excludes_hmac_signature_field_too(self) -> None:
        # Both signature fields must be excluded from what gets signed —
        # changing the HMAC "signature" field alone must not affect an
        # already-valid ed25519 signature.
        fields = {"a": 1, "signature": "x", "ed25519_signature": ""}
        fields["ed25519_signature"] = ed25519.sign(fields)
        fields["signature"] = "y"
        assert ed25519.verify(fields, ed25519.public_key_b64()) is True


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ED25519_SIGNING_KEY")
    with pytest.raises(ed25519.Ed25519KeyMissingError):
        ed25519.sign({"a": 1})


def test_malformed_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ED25519_SIGNING_KEY", "not-valid-base64!!")
    with pytest.raises(ed25519.Ed25519KeyMissingError):
        ed25519.sign({"a": 1})
