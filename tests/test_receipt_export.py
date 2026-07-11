"""Unit tests for CSV/PDF receipt export."""

from app.models import Receipt, RigorLevel, Verdict
from app.receipt.export import to_csv, to_pdf

_RECEIPT = Receipt(
    receipt_id="r-1",
    issued_at="2026-07-11T00:00:00Z",
    verdict=Verdict.SUPPORTED,
    output_sha256="a" * 64,
    sources_sha256=["b" * 64],
    rigor_level=RigorLevel.STANDARD,
    engine_version="0.1.0",
    signature="c" * 64,
    ed25519_signature="ZWQyNTUxOXNpZ25hdHVyZXBsYWNlaG9sZGVy",
)


class TestCsvExport:
    def test_header_row(self) -> None:
        rows = to_csv([]).splitlines()
        assert rows == [
            "receipt_id,issued_at,verdict,output_sha256,sources_sha256,"
            "rigor_level,engine_version,signature,ed25519_signature"
        ]

    def test_one_row_per_receipt(self) -> None:
        rows = to_csv([_RECEIPT, _RECEIPT]).splitlines()
        assert len(rows) == 3  # header + 2 data rows

    def test_fields_present_and_multiple_source_hashes_joined(self) -> None:
        multi_source = _RECEIPT.model_copy(update={"sources_sha256": ["b" * 64, "d" * 64]})
        row = to_csv([multi_source]).splitlines()[1]
        assert "r-1" in row
        assert "b" * 64 + "|" + "d" * 64 in row
        assert "c" * 64 in row


class TestPdfExport:
    def test_produces_valid_pdf_bytes(self) -> None:
        pdf_bytes = to_pdf(_RECEIPT)
        assert pdf_bytes.startswith(b"%PDF-")
        assert pdf_bytes.rstrip().endswith(b"%%EOF")

    def test_does_not_crash_on_non_latin1_free_content(self) -> None:
        # Regression guard: the core PDF fonts only support latin-1; any
        # non-latin1 characters introduced into fixed labels/copy must be
        # caught here rather than raising at request time.
        pdf_bytes = to_pdf(_RECEIPT)
        assert len(pdf_bytes) > 0
