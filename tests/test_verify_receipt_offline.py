"""Tests for the standalone offline verifier script.

Run via subprocess against a real receipt end-to-end, the way a third party
who copied this one file out would use it — plus a drift guard against the
in-app canonicalization it deliberately duplicates.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from app.models import Receipt
from app.receipt import ed25519
from app.receipt.build import build_receipt
from app.receipt.sign import canonical_body as app_canonical_body

SCRIPT = Path(__file__).parent.parent / "scripts" / "verify_receipt_offline.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("verify_receipt_offline", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_receipt() -> Receipt:
    from app.models import RigorLevel, SourceDocument, Verdict

    docs = [SourceDocument(id="doc-1", text="Revenue increased 12% to $4.1M.")]
    return build_receipt("Revenue rose 12%.", docs, Verdict.SUPPORTED, RigorLevel.STANDARD)


class TestCanonicalBodyMatchesApp:
    def test_same_bytes_as_app_sign_module(self) -> None:
        offline = _load_script_module()
        fields = {"z": 1, "a": 2, "signature": "x", "ed25519_signature": "y"}
        assert offline.canonical_body(fields) == app_canonical_body(fields)


class TestVerifyReceiptFunction:
    def test_valid_receipt_verifies(self) -> None:
        offline = _load_script_module()
        receipt = _sample_receipt()
        public_key = ed25519.public_key_b64()
        assert offline.verify_receipt(receipt.model_dump(mode="json"), public_key) is True

    def test_tampered_receipt_fails(self) -> None:
        offline = _load_script_module()
        receipt = _sample_receipt().model_dump(mode="json")
        receipt["verdict"] = "unsupported"
        public_key = ed25519.public_key_b64()
        assert offline.verify_receipt(receipt, public_key) is False


class TestScriptCli:
    def test_cli_reports_valid(self, tmp_path: Path) -> None:
        receipt = _sample_receipt()
        receipt_file = tmp_path / "receipt.json"
        receipt_file.write_text(json.dumps(receipt.model_dump(mode="json")))
        public_key = ed25519.public_key_b64()

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(receipt_file), public_key],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "VALID" in result.stdout

    def test_cli_reports_invalid_for_tampered_receipt(self, tmp_path: Path) -> None:
        receipt = _sample_receipt().model_dump(mode="json")
        receipt["verdict"] = "unsupported"
        receipt_file = tmp_path / "receipt.json"
        receipt_file.write_text(json.dumps(receipt))
        public_key = ed25519.public_key_b64()

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(receipt_file), public_key],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "INVALID" in result.stdout
