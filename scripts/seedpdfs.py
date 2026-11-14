#!/usr/bin/env python3
"""Generate 10 realistic corporate sample PDFs + data/presets.json for VendorGate."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "pdfs"
PRESETS_PATH = ROOT / "data" / "presets.json"

NAVY = colors.HexColor("#0F172A")
BLUE = colors.HexColor("#2340F5")
LIGHT = colors.HexColor("#F7F8FA")
BORDER = colors.HexColor("#E2E8F0")
MUTED = colors.HexColor("#64748B")
GREEN = colors.HexColor("#065F46")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "VGTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=NAVY,
            spaceAfter=4,
            leading=20,
        ),
        "sub": ParagraphStyle(
            "VGSub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=MUTED,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "VGH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=BLUE,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "VGBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=NAVY,
            leading=12,
        ),
        "mono": ParagraphStyle(
            "VGMono",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=9,
            textColor=NAVY,
            leading=12,
        ),
        "small": ParagraphStyle(
            "VGSmall",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            leading=10,
        ),
        "sign": ParagraphStyle(
            "VGSign",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=14,
            textColor=NAVY,
            alignment=TA_LEFT,
        ),
        "center": ParagraphStyle(
            "VGCenter",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            alignment=TA_CENTER,
            textColor=NAVY,
        ),
    }


def _header_table(agency: str, form_title: str, form_code: str, styles) -> Table:
    data = [
        [
            Paragraph(f"<b>{agency}</b>", styles["body"]),
            Paragraph(f"<b>{form_code}</b>", ParagraphStyle("r", parent=styles["body"], alignment=TA_RIGHT)),
        ],
        [
            Paragraph(form_title, styles["title"]),
            Paragraph("OFFICIAL COPY", ParagraphStyle("r2", parent=styles["small"], alignment=TA_RIGHT)),
        ],
    ]
    t = Table(data, colWidths=[5.2 * inch, 2.0 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 1, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def _kv_table(rows: list[tuple[str, str]], styles, col1=2.2, col2=5.0) -> Table:
    data = [
        [
            Paragraph(f"<b>{k}</b>", styles["small"]),
            Paragraph(v, styles["mono"] if any(x in k.lower() for x in ("ein", "gstin", "account", "routing", "ifsc", "aba", "tax")) else styles["body"]),
        ]
        for k, v in rows
    ]
    t = Table(data, colWidths=[col1 * inch, col2 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def _signature_block(name: str, title: str, date: str, styles) -> list:
    return [
        Spacer(1, 16),
        Paragraph("Authorized Signature", styles["h2"]),
        HRFlowable(width="40%", thickness=1, color=NAVY, spaceBefore=18, spaceAfter=4),
        Paragraph(f"<i>{name}</i>", styles["sign"]),
        Paragraph(f"{title} · Date: {date}", styles["small"]),
        Paragraph("Document attested / digitally countersigned", styles["small"]),
    ]


def _build(path: Path, story: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=path.stem,
    )
    doc.build(story)


def make_w9(
    path: Path,
    *,
    legal_name: str,
    business_name: str,
    address: str,
    tin: str,
    requester: str = "VendorGate Procurement",
    signed_by: str = "Alex Rivera, CFO",
    date: str = "2026-01-15",
) -> None:
    s = _styles()
    story = [
        _header_table("Department of the Treasury — Internal Revenue Service", "Form W-9 Request for Taxpayer Identification Number and Certification", "Form W-9 (Rev. 2024)", s),
        Spacer(1, 10),
        Paragraph("Part I — Identification of Entity", s["h2"]),
        _kv_table(
            [
                ("1 Name (as shown on tax return)", legal_name),
                ("2 Business name / disregarded entity", business_name or "—"),
                ("3 Federal tax classification", "C Corporation / LLC taxed as C-Corp"),
                ("5 Address (number, street, apt)", address),
                ("6 City, state, ZIP", address.split(",")[-1].strip() if "," in address else address),
                ("Requester name & address", requester),
                ("Taxpayer Identification Number (EIN)", tin),
            ],
            s,
        ),
        Spacer(1, 8),
        Paragraph("Part II — Certification", s["h2"]),
        Paragraph(
            "Under penalties of perjury, I certify that: (1) The number shown on this form is my correct taxpayer "
            "identification number; (2) I am not subject to backup withholding; (3) I am a U.S. person.",
            s["body"],
        ),
        *_signature_block(signed_by, "Authorized Officer", date, s),
        Spacer(1, 12),
        Paragraph("This document is provided solely for vendor onboarding KYB verification.", s["small"]),
    ]
    _build(path, story)


def make_bank_letter(
    path: Path,
    *,
    bank_name: str,
    bank_address: str,
    account_holder: str,
    account_number: str,
    routing: str,
    account_type: str = "Business Checking",
    country: str = "US",
    date: str = "2026-02-01",
    signed_by: str = "Jordan Lee, Branch Manager",
    extra_note: str = "",
) -> None:
    s = _styles()
    story = [
        _header_table(bank_name, "Bank Account Verification Letter", "BVL-2026", s),
        Spacer(1, 8),
        Paragraph(f"<b>Branch / Treasury Desk</b> · {bank_address}", s["sub"]),
        Paragraph("To Whom It May Concern:", s["body"]),
        Spacer(1, 6),
        Paragraph(
            f"This letter confirms that <b>{account_holder}</b> maintains an active {account_type} "
            f"account with {bank_name}. Banking coordinates for vendor remittance are as follows:",
            s["body"],
        ),
        Spacer(1, 8),
        _kv_table(
            [
                ("Account Holder Name", account_holder),
                ("Account Type", account_type),
                ("Account Number", account_number),
                ("Routing / IFSC / SWIFT", routing),
                ("Bank Country", country),
                ("Verification Date", date),
                ("Status", "ACTIVE — Good Standing"),
            ],
            s,
        ),
    ]
    if extra_note:
        story += [Spacer(1, 8), Paragraph(extra_note, s["body"])]
    story += _signature_block(signed_by, "Authorized Bank Officer", date, s)
    story += [
        Spacer(1, 10),
        Paragraph("Official bank letterhead simulation for VendorGate demo packet.", s["small"]),
    ]
    _build(path, story)


def make_gst_certificate(
    path: Path,
    *,
    legal_name: str,
    trade_name: str,
    gstin: str,
    address: str,
    date: str = "2025-11-20",
) -> None:
    s = _styles()
    story = [
        _header_table(
            "Government of India · Goods and Services Tax Network",
            "GST Registration Certificate",
            "FORM GST REG-06",
            s,
        ),
        Spacer(1, 8),
        Paragraph("Registration Details", s["h2"]),
        _kv_table(
            [
                ("GSTIN / UIN", gstin),
                ("Legal Name", legal_name),
                ("Trade Name", trade_name or "—"),
                ("Constitution of Business", "Private Limited Company"),
                ("Principal Place of Business", address),
                ("Date of Liability", date),
                ("Valid / Signed", "YES — Digitally signed by GSTN"),
            ],
            s,
        ),
        Spacer(1, 10),
        Paragraph(
            "This certificate is digitally signed and remains valid unless cancelled or surrendered.",
            s["body"],
        ),
        *_signature_block("GSTN Authorised Signatory", "Central Board of Indirect Taxes", date, s),
    ]
    _build(path, story)


def make_cancelled_cheque(
    path: Path,
    *,
    bank_name: str,
    account_holder: str,
    account_number: str,
    ifsc: str,
    date: str = "2026-01-28",
) -> None:
    s = _styles()
    story = [
        _header_table(bank_name, "Cancelled Cheque / Account Confirmation Slip", "CQ-VERIFY", s),
        Spacer(1, 12),
        Paragraph("<b>★★★ CANCELLED — FOR VERIFICATION ONLY ★★★</b>", s["center"]),
        Spacer(1, 10),
        _kv_table(
            [
                ("Payee / Account Holder", account_holder),
                ("Bank", bank_name),
                ("Account Number", account_number),
                ("IFSC", ifsc),
                ("Cheque Number", "000491"),
                ("Date on Instrument", date),
                ("Signature Present", "YES"),
            ],
            s,
        ),
        Spacer(1, 14),
        Paragraph(
            "This cancelled cheque image is furnished to confirm beneficiary banking details for vendor onboarding.",
            s["body"],
        ),
        *_signature_block(account_holder, "Account Signatory", date, s),
    ]
    _build(path, story)


def make_sales_quote(
    path: Path,
    *,
    vendor_name: str,
    quote_no: str,
    gstin: str,
    date: str = "2026-03-04",
) -> None:
    s = _styles()
    story = [
        _header_table(vendor_name, "Commercial Sales Quotation", quote_no, s),
        Spacer(1, 8),
        Paragraph(
            "<b>NOTE:</b> This is a commercial quotation — NOT a bank verification document.",
            s["body"],
        ),
        Spacer(1, 8),
        _kv_table(
            [
                ("Quote Number", quote_no),
                ("Vendor / Seller", vendor_name),
                ("Seller GSTIN", gstin),
                ("Buyer", "Zamp Procurement Demo Co."),
                ("Quote Date", date),
                ("Validity", "30 days"),
                ("Currency", "INR / USD equivalent"),
            ],
            s,
        ),
        Spacer(1, 10),
        Paragraph("Line Items", s["h2"]),
    ]
    items = Table(
        [
            ["SKU", "Description", "Qty", "Unit", "Amount"],
            ["KX-440", "CNC spindle assembly", "2", "12,500", "25,000"],
            ["KX-118", "Calibration service retainer", "1", "6,000", "6,000"],
        ],
        colWidths=[0.9 * inch, 2.8 * inch, 0.7 * inch, 1.1 * inch, 1.2 * inch],
    )
    items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story += [
        items,
        Spacer(1, 10),
        Paragraph("<b>Total Quote Value:</b> USD 31,000 (indicative)", s["body"]),
        *_signature_block("Priya Nair", "Sales Manager", date, s),
    ]
    _build(path, story)


def generate_all() -> dict:
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # Preset 1 — Happy path US
    p1_tax = PDF_DIR / "preset_1_northstar_w9.pdf"
    p1_bank = PDF_DIR / "preset_1_northstar_chase_bvl.pdf"
    make_w9(
        p1_tax,
        legal_name="Northstar Cloud Systems Inc.",
        business_name="Northstar Cloud Systems Inc.",
        address="1200 Market Street, Suite 400, San Francisco, CA 94103",
        tin="47-3920184",
        signed_by="Alex Rivera, CFO",
    )
    make_bank_letter(
        p1_bank,
        bank_name="JPMorgan Chase Bank, N.A.",
        bank_address="270 Park Avenue, New York, NY 10017",
        account_holder="Northstar Cloud Systems Inc.",
        account_number="4401928374",
        routing="021000021",
        country="US",
    )

    # Preset 2 — DBA variance IN
    p2_tax = PDF_DIR / "preset_2_cloudpulse_gst.pdf"
    p2_bank = PDF_DIR / "preset_2_cloudpulse_hdfc_cheque.pdf"
    make_gst_certificate(
        p2_tax,
        legal_name="CloudPulse Holdings Private Limited",
        trade_name="CloudPulse Technologies",
        gstin="29AABCC4829K1Z5",
        address="12 Residency Road, Bengaluru, Karnataka 560025",
    )
    make_cancelled_cheque(
        p2_bank,
        bank_name="HDFC Bank Limited",
        account_holder="CloudPulse Holdings Private Limited",
        account_number="50200048192011",
        ifsc="HDFC0001204",
    )

    # Preset 3 — Offshore split
    p3_tax = PDF_DIR / "preset_3_meridian_w9.pdf"
    p3_bank = PDF_DIR / "preset_3_meridian_cayman_wire.pdf"
    make_w9(
        p3_tax,
        legal_name="Meridian BioLabs Inc.",
        business_name="Meridian BioLabs Inc.",
        address="500 Innovation Drive, Cambridge, MA 02139",
        tin="82-6410923",
        signed_by="Sam Chen, Treasurer",
    )
    make_bank_letter(
        p3_bank,
        bank_name="Cayman National Bank Ltd.",
        bank_address="200 Elgin Avenue, George Town, Grand Cayman, KY1-1104",
        account_holder="Meridian BioLabs Inc.",
        account_number="KY890011223344",
        routing="CAYMKYKY012",
        account_type="Corporate Operating — Offshore Wire",
        country="KY",
        signed_by="M. Thompson, Treasury Officer",
        extra_note=(
            "Funds are receivable in the Cayman Islands. Cross-border remittance controls and "
            "Form W-8BEN-E may be required by the remitting counterparty."
        ),
    )

    # Preset 4 — Wrong doc + GSTIN typo
    p4_tax = PDF_DIR / "preset_4_kinetix_gst.pdf"
    p4_bank = PDF_DIR / "preset_4_kinetix_quote.pdf"
    make_gst_certificate(
        p4_tax,
        legal_name="Kinetix Precision Engineering Private Limited",
        trade_name="Kinetix Precision Engineering",
        gstin="27AADCK9120M1Z8",  # transposition vs form 27AADCK9102M1Z8
        address="Plot 18, MIDC Andheri East, Mumbai, Maharashtra 400093",
    )
    make_sales_quote(
        p4_bank,
        vendor_name="Kinetix Precision Engineering Pvt Ltd",
        quote_no="Quote #KQ-2026-89",
        gstin="27AADCK9120M1Z8",
    )

    # Preset 5 — Bank fraud / personal diversion + duplicate account
    p5_tax = PDF_DIR / "preset_5_apex_w9.pdf"
    p5_bank = PDF_DIR / "preset_5_apex_personal_bank.pdf"
    make_w9(
        p5_tax,
        legal_name="Apex Digital Supply LLC",
        business_name="Apex Digital Supply LLC",
        address="88 Commerce Blvd, Austin, TX 78701",
        tin="61-4092817",
        signed_by="Marcus Vance, Managing Member",
    )
    make_bank_letter(
        p5_bank,
        bank_name="Chase Personal Banking",
        bank_address="Austin Downtown Branch, Austin, TX 78701",
        account_holder="Marcus Vance (Individual Savings)",
        account_number="8899001122",
        routing="021000021",
        account_type="Personal Savings",
        country="US",
        signed_by="Branch Associate",
        extra_note="Account titled to an individual consumer product — not a corporate operating account.",
    )

    presets = {
        "preset_1_happy_path": {
            "label": "Northstar [Standard US]",
            "expected_status": "APPROVED",
            "expected_clauses": ["AOP §1.1 — Standard Auto-Approval"],
            "tax_pdf": str(p1_tax.relative_to(ROOT)),
            "bank_pdf": str(p1_bank.relative_to(ROOT)),
            "submission": {
                "legal_name": "Northstar Cloud Systems Inc.",
                "dba_name": "",
                "country": "US",
                "registration_address": "1200 Market Street, Suite 400, San Francisco, CA 94103",
                "contact_email": "finance@northstarcloud.io",
                "tax_id": "47-3920184",
                "expected_annual_spend_usd": 42000,
                "account_holder_name": "Northstar Cloud Systems Inc.",
                "bank_country": "US",
                "routing_or_ifsc": "021000021",
                "account_number": "4401928374",
            },
        },
        "preset_2_dba_variance": {
            "label": "CloudPulse [DBA Variance]",
            "expected_status": "PENDING",
            "expected_clauses": ["AOP §2.2 — Corporate Hierarchy & DBA Alignment"],
            "tax_pdf": str(p2_tax.relative_to(ROOT)),
            "bank_pdf": str(p2_bank.relative_to(ROOT)),
            "submission": {
                "legal_name": "CloudPulse Technologies",
                "dba_name": "",
                "country": "IN",
                "registration_address": "12 Residency Road, Bengaluru, Karnataka 560025",
                "contact_email": "billing@cloudpulse.in",
                "tax_id": "29AABCC4829K1Z5",
                "expected_annual_spend_usd": 38000,
                "account_holder_name": "CloudPulse Technologies",
                "bank_country": "IN",
                "routing_or_ifsc": "HDFC0001204",
                "account_number": "50200048192011",
            },
        },
        "preset_3_offshore_split": {
            "label": "Meridian [Offshore Split]",
            "expected_status": "PENDING",
            "expected_clauses": [
                "AOP §3.1 — Cross-Border Treasury & Tax Nexus",
                "AOP §4.1 — High-Value Contract Governance",
            ],
            "tax_pdf": str(p3_tax.relative_to(ROOT)),
            "bank_pdf": str(p3_bank.relative_to(ROOT)),
            "submission": {
                "legal_name": "Meridian BioLabs Inc.",
                "dba_name": "",
                "country": "US",
                "registration_address": "500 Innovation Drive, Cambridge, MA 02139",
                "contact_email": "treasury@meridianbiolabs.com",
                "tax_id": "82-6410923",
                "expected_annual_spend_usd": 140000,
                "account_holder_name": "Meridian BioLabs Inc.",
                "bank_country": "KY",
                "routing_or_ifsc": "CAYMKYKY012",
                "account_number": "KY890011223344",
            },
        },
        "preset_4_wrong_doc_typo": {
            "label": "Kinetix [Wrong Doc + Typo]",
            "expected_status": "PENDING",
            "expected_clauses": ["AOP §2.1 — Document & Data Discrepancy Remediation"],
            "tax_pdf": str(p4_tax.relative_to(ROOT)),
            "bank_pdf": str(p4_bank.relative_to(ROOT)),
            "submission": {
                "legal_name": "Kinetix Precision Engineering Pvt Ltd",
                "dba_name": "",
                "country": "IN",
                "registration_address": "Plot 18, MIDC Andheri East, Mumbai, Maharashtra 400093",
                "contact_email": "accounts@kinetixprecision.in",
                "tax_id": "27AADCK9102M1Z8",
                "expected_annual_spend_usd": 31000,
                "account_holder_name": "Kinetix Precision Engineering Pvt Ltd",
                "bank_country": "IN",
                "routing_or_ifsc": "ICIC0000391",
                "account_number": "039105009281",
            },
        },
        "preset_5_bank_fraud": {
            "label": "Apex [Bank Fraud]",
            "expected_status": "REJECTED",
            "expected_clauses": ["AOP §5.1 — Zero-Tolerance Fraud & Payment Diversion"],
            "tax_pdf": str(p5_tax.relative_to(ROOT)),
            "bank_pdf": str(p5_bank.relative_to(ROOT)),
            "submission": {
                "legal_name": "Apex Digital Supply LLC",
                "dba_name": "",
                "country": "US",
                "registration_address": "88 Commerce Blvd, Austin, TX 78701",
                "contact_email": "apex.billing.ops@gmail.com",
                "tax_id": "61-4092817",
                "expected_annual_spend_usd": 85000,
                "account_holder_name": "Apex Digital Supply LLC",
                "bank_country": "US",
                "routing_or_ifsc": "021000021",
                "account_number": "8899001122",
            },
        },
    }

    PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRESETS_PATH.write_text(json.dumps(presets, indent=2), encoding="utf-8")
    print(f"Wrote {len(list(PDF_DIR.glob('*.pdf')))} PDFs to {PDF_DIR}")
    print(f"Wrote presets → {PRESETS_PATH}")
    return presets


if __name__ == "__main__":
    generate_all()
