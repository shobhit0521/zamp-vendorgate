"""Deterministic Python guardrails for VendorGate Node 01 intake."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.database import find_account_collisions
from core.models import CheckItem, VendorSubmission

CONSUMER_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}
INVALID_EIN_PREFIXES = {"00", "07", "08", "96", "97"}

US_EIN_RE = re.compile(r"^\d{2}-\d{7}$")
IN_GSTIN_RE = re.compile(
    r"^(0[1-9]|[12]\d|3[0-8])[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
IN_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
GB_VAT_RE = re.compile(r"^GB\d{9}$")
GB_SORT_RE = re.compile(r"^\d{2}-?\d{2}-?\d{2}$")
GB_IBAN_RE = re.compile(r"^GB\d{2}[A-Z]{4}\d{14}$")


def validate_aba_routing(routing: str) -> bool:
    digits = re.sub(r"\D", "", routing or "")
    if len(digits) != 9:
        return False
    d = [int(c) for c in digits]
    checksum = (
        3 * (d[0] + d[3] + d[6])
        + 7 * (d[1] + d[4] + d[7])
        + (d[2] + d[5] + d[8])
    )
    return checksum % 10 == 0


def validate_us_ein(tax_id: str) -> bool:
    if not US_EIN_RE.match(tax_id or ""):
        return False
    return tax_id[:2] not in INVALID_EIN_PREFIXES


def validate_in_gstin(tax_id: str) -> bool:
    return bool(IN_GSTIN_RE.match(tax_id or ""))


def validate_in_ifsc(ifsc: str) -> bool:
    return bool(IN_IFSC_RE.match(ifsc or ""))


def validate_gb_vat(tax_id: str) -> bool:
    return bool(GB_VAT_RE.match(tax_id or ""))


def validate_gb_routing(routing: str) -> bool:
    r = (routing or "").strip().upper().replace(" ", "")
    return bool(GB_SORT_RE.match(r) or GB_IBAN_RE.match(r))


def _pdf_magic_ok(pdf_bytes: bytes | None) -> bool:
    return bool(pdf_bytes) and pdf_bytes[:5] == b"%PDF-"


def _check(
    code: str,
    label: str,
    passed: bool,
    severity: str,
    detail: str,
) -> CheckItem:
    return CheckItem(
        check_code=code,
        label=label,
        passed=passed,
        severity=severity if not passed else "PASS",  # type: ignore[arg-type]
        detail=detail if not passed else (detail or "OK"),
    )


def run_intake_checks(
    submission: VendorSubmission | dict[str, Any],
    tax_pdf_bytes: bytes | None,
    bank_pdf_bytes: bytes | None,
    db_path: str | Path | None = None,
) -> list[CheckItem]:
    if isinstance(submission, dict):
        sub = VendorSubmission.model_validate(submission)
    else:
        sub = submission

    checks: list[CheckItem] = []

    required = {
        "legal_name": sub.legal_name,
        "country": sub.country,
        "registration_address": sub.registration_address,
        "contact_email": sub.contact_email,
        "tax_id": sub.tax_id,
        "account_holder_name": sub.account_holder_name,
        "bank_country": sub.bank_country,
        "routing_or_ifsc": sub.routing_or_ifsc,
        "account_number": sub.account_number,
    }
    missing = [k for k, v in required.items() if not str(v).strip()]
    checks.append(
        _check(
            "REQ_FIELDS",
            "Required fields present",
            not missing,
            "FAIL_PENDING",
            f"Missing required fields: {', '.join(missing)}" if missing else "All required fields present",
        )
    )

    tax_ok = _pdf_magic_ok(tax_pdf_bytes)
    bank_ok = _pdf_magic_ok(bank_pdf_bytes)
    checks.append(
        _check(
            "TAX_PDF_MAGIC",
            "Tax PDF magic header",
            tax_ok,
            "FAIL_PENDING",
            "Tax PDF missing or invalid (expected %PDF- header)" if not tax_ok else "Tax PDF header valid",
        )
    )
    checks.append(
        _check(
            "BANK_PDF_MAGIC",
            "Bank PDF magic header",
            bank_ok,
            "FAIL_PENDING",
            "Bank PDF missing or invalid (expected %PDF- header)" if not bank_ok else "Bank PDF header valid",
        )
    )

    email = (sub.contact_email or "").strip().lower()
    domain = email.split("@")[-1] if "@" in email else ""
    consumer_warn = domain in CONSUMER_EMAIL_DOMAINS and sub.expected_annual_spend_usd >= 25000
    checks.append(
        CheckItem(
            check_code="EMAIL_DOMAIN",
            label="Corporate email domain",
            passed=not consumer_warn,
            severity="WARN" if consumer_warn else "PASS",
            detail=(
                f"Consumer webmail domain '{domain}' on spend >= USD 25,000 — corporate domain verification required"
                if consumer_warn
                else f"Email domain '{domain or 'n/a'}' acceptable"
            ),
        )
    )

    # Country-specific tax / routing
    if sub.country == "US":
        ein_ok = validate_us_ein(sub.tax_id)
        checks.append(
            _check(
                "US_EIN",
                "US EIN format",
                ein_ok,
                "FAIL_PENDING",
                "US EIN must match NN-NNNNNNN and exclude invalid prefixes" if not ein_ok else "EIN valid",
            )
        )
        if sub.bank_country == "US":
            aba_ok = validate_aba_routing(sub.routing_or_ifsc)
            checks.append(
                _check(
                    "US_ABA",
                    "US ABA routing checksum",
                    aba_ok,
                    "FAIL_PENDING",
                    "ABA routing number failed checksum" if not aba_ok else "ABA routing valid",
                )
            )
    elif sub.country == "IN":
        gstin_ok = validate_in_gstin(sub.tax_id)
        checks.append(
            _check(
                "IN_GSTIN",
                "India GSTIN format",
                gstin_ok,
                "FAIL_PENDING",
                "GSTIN failed format validation" if not gstin_ok else "GSTIN valid",
            )
        )
        if sub.bank_country == "IN":
            ifsc_ok = validate_in_ifsc(sub.routing_or_ifsc)
            checks.append(
                _check(
                    "IN_IFSC",
                    "India IFSC format",
                    ifsc_ok,
                    "FAIL_PENDING",
                    "IFSC failed format validation" if not ifsc_ok else "IFSC valid",
                )
            )
    elif sub.country == "GB":
        vat_ok = validate_gb_vat(sub.tax_id)
        checks.append(
            _check(
                "GB_VAT",
                "UK VAT format",
                vat_ok,
                "FAIL_PENDING",
                "UK VAT must match GB######### " if not vat_ok else "UK VAT valid",
            )
        )
        if sub.bank_country == "GB":
            sort_ok = validate_gb_routing(sub.routing_or_ifsc)
            checks.append(
                _check(
                    "GB_SORT",
                    "UK Sort Code / IBAN",
                    sort_ok,
                    "FAIL_PENDING",
                    "Sort code or GB IBAN invalid" if not sort_ok else "UK routing valid",
                )
            )

    cross_border = sub.country != sub.bank_country
    checks.append(
        CheckItem(
            check_code="CROSS_BORDER",
            label="Bank / tax jurisdiction nexus",
            passed=not cross_border,
            severity="FAIL_PENDING" if cross_border else "PASS",
            detail=(
                f"Cross-border payout: tax country {sub.country} vs bank country {sub.bank_country}"
                if cross_border
                else "Domestic bank country matches tax registration country"
            ),
        )
    )

    collisions = find_account_collisions(sub.account_number, sub.legal_name, db_path=db_path)
    if collisions:
        hit = collisions[0]
        checks.append(
            CheckItem(
                check_code="DUP_BANK_ACCOUNT",
                label="Duplicate bank account registry collision",
                passed=False,
                severity="FAIL_REJECT",
                detail=(
                    f"INTERNAL ONLY: account_number={sub.account_number} collides with approved vendor "
                    f"'{hit['legal_name']}' (tax_id={hit['tax_id']}, routing={hit['routing_or_ifsc']})"
                ),
            )
        )
    else:
        checks.append(
            CheckItem(
                check_code="DUP_BANK_ACCOUNT",
                label="Duplicate bank account registry collision",
                passed=True,
                severity="PASS",
                detail="No registry account collisions",
            )
        )

    return checks
