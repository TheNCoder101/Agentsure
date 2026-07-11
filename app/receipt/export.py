"""Receipt export formats: CSV for bulk retention/audit review, PDF as a
single hand-off document a compliance officer can print or attach to a
regulator filing.
"""

import csv
import io

from fpdf import FPDF

from app.models import Receipt

CSV_HEADER = [
    "receipt_id",
    "issued_at",
    "verdict",
    "output_sha256",
    "sources_sha256",
    "rigor_level",
    "engine_version",
    "signature",
    "ed25519_signature",
]


def to_csv(receipts: list[Receipt]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for r in receipts:
        writer.writerow(
            [
                r.receipt_id,
                r.issued_at,
                r.verdict.value,
                r.output_sha256,
                "|".join(r.sources_sha256),
                r.rigor_level.value,
                r.engine_version,
                r.signature,
                r.ed25519_signature,
            ]
        )
    return buffer.getvalue()


def to_pdf(receipt: Receipt) -> bytes:
    pdf = FPDF(format="letter")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Verification Gate - Audit Receipt", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(
        0,
        6,
        "Cryptographic attestation that a given output was checked against "
        "supplied source documents before being acted on.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(6)
    pdf.set_text_color(0, 0, 0)

    fields = [
        ("Receipt ID", receipt.receipt_id),
        ("Issued At", receipt.issued_at),
        ("Verdict", receipt.verdict.value),
        ("Rigor Level", receipt.rigor_level.value),
        ("Engine Version", receipt.engine_version),
        ("Output SHA-256", receipt.output_sha256),
        ("Source SHA-256(es)", ", ".join(receipt.sources_sha256)),
        ("Signature (HMAC-SHA256)", receipt.signature),
        ("Signature (Ed25519)", receipt.ed25519_signature),
    ]
    for label, value in fields:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 8, label, new_x="RIGHT", new_y="TOP")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 8, value, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(
        0,
        6,
        "This receipt attests only to the hashes above - it does not contain the "
        "underlying output or source text. Verify its authenticity by submitting "
        "these fields to POST /receipt/verify, or independently offline using the "
        "published Ed25519 public key (GET /.well-known/agentsure-receipt-key) - "
        "no call to our API required.",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    return bytes(pdf.output())
