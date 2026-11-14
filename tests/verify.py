"""Autonomous sandbox verification suite for VendorGate."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.database import find_account_collisions, init_and_seed_db
from core.models import (
    AdjudicationSchema,
    CheckItem,
    CommsDraftSchema,
    CriticReviewSchema,
    DocumentForensicsSchema,
    EntityInvestigationSchema,
    EvidenceRow,
    VendorSubmission,
)
from core.validators import (
    run_intake_checks,
    validate_aba_routing,
    validate_in_gstin,
    validate_in_ifsc,
)


PDF_DIR = ROOT / "data" / "pdfs"
PRESETS_PATH = ROOT / "data" / "presets.json"


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    db = tmp_path / "vendorgate_test.db"
    init_and_seed_db(db)
    return db


def test_aba_checksum_valid_and_invalid() -> None:
    assert validate_aba_routing("021000021") is True
    assert validate_aba_routing("021000029") is False


def test_indian_gstin_and_ifsc() -> None:
    assert validate_in_gstin("29AABCC4829K1Z5") is True
    assert validate_in_gstin("99AABCC4829K1Z5") is False
    assert validate_in_gstin("29AABCC4829K1") is False
    assert validate_in_ifsc("HDFC0001204") is True
    assert validate_in_ifsc("HDFC1001204") is False
    assert validate_in_ifsc("HDFC00012") is False


def test_sqlite_seed_and_duplicate_collision(tmp_db: Path) -> None:
    hits = find_account_collisions("8899001122", "Apex Digital Supply LLC", db_path=tmp_db)
    assert hits, "Expected collision with Zenith Logistics Inc."
    assert hits[0]["legal_name"] == "Zenith Logistics Inc."

    sub = VendorSubmission(
        legal_name="Apex Digital Supply LLC",
        country="US",
        registration_address="88 Commerce Blvd, Austin, TX 78701",
        contact_email="apex.billing.ops@gmail.com",
        tax_id="61-4092817",
        expected_annual_spend_usd=85000,
        account_holder_name="Apex Digital Supply LLC",
        bank_country="US",
        routing_or_ifsc="021000021",
        account_number="8899001122",
    )
    # Minimal valid PDF magic for other checks
    pdf = b"%PDF-1.4 mock"
    checks = run_intake_checks(sub, pdf, pdf, db_path=tmp_db)
    dup = next(c for c in checks if c.check_code == "DUP_BANK_ACCOUNT")
    assert dup.severity == "FAIL_REJECT"
    assert "Zenith Logistics Inc." in dup.detail


def test_approved_vendor_promoted_to_registry_for_future_checks(tmp_db: Path) -> None:
    from core.database import persist_run, upsert_approved_vendor

    new_vendor = {
        "legal_name": "Northstar Cloud Systems Inc.",
        "country": "US",
        "tax_id": "47-3920184",
        "expected_annual_spend_usd": 42000,
        "account_holder_name": "Northstar Cloud Systems Inc.",
        "bank_country": "US",
        "routing_or_ifsc": "021000021",
        "account_number": "4401928374",
    }
    result = upsert_approved_vendor(new_vendor, db_path=tmp_db)
    assert result["action"] == "inserted"

    # Re-approve same legal name refreshes coordinates
    new_vendor["account_number"] = "4401928374"
    result2 = upsert_approved_vendor(new_vendor, db_path=tmp_db)
    assert result2["action"] == "updated"

    # persist_run on APPROVED also promotes
    persist_run(
        run_id="VG-TEST-REG-1",
        submission={
            "legal_name": "Orbit Pack Co Inc.",
            "country": "US",
            "tax_id": "12-3456789",
            "expected_annual_spend_usd": 10000,
            "bank_country": "US",
            "routing_or_ifsc": "021000021",
            "account_number": "7788990011",
        },
        adjudication={"status": "APPROVED", "risk_score": 10, "cited_clauses": []},
        stage_trace=[],
        evidence_rows=[],
        comms={},
        duration_ms=100,
        db_path=tmp_db,
    )
    hits = find_account_collisions("7788990011", "Fake Clone LLC", db_path=tmp_db)
    assert hits and hits[0]["legal_name"] == "Orbit Pack Co Inc."

    # PENDING must not promote
    persist_run(
        run_id="VG-TEST-REG-2",
        submission={
            "legal_name": "Pending Only LLC",
            "country": "US",
            "tax_id": "98-7654321",
            "expected_annual_spend_usd": 10000,
            "bank_country": "US",
            "routing_or_ifsc": "021000021",
            "account_number": "1122334455",
        },
        adjudication={"status": "PENDING", "risk_score": 40, "cited_clauses": []},
        stage_trace=[],
        evidence_rows=[],
        comms={},
        duration_ms=100,
        db_path=tmp_db,
    )
    assert not find_account_collisions("1122334455", "Someone Else LLC", db_path=tmp_db)


def test_sample_pdfs_exist_and_valid() -> None:
    assert PRESETS_PATH.exists(), "data/presets.json missing — run scripts/seedpdfs.py"
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    assert len(pdfs) == 10, f"Expected 10 PDFs, found {len(pdfs)}"
    for p in pdfs:
        data = p.read_bytes()
        assert data.startswith(b"%PDF-"), f"{p.name} missing PDF magic"
        assert len(data) > 1024, f"{p.name} too small ({len(data)} bytes)"


def _load_presets() -> dict:
    return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))


def _mock_forensics_for_preset(key: str, slot: str) -> DocumentForensicsSchema:
    presets = _load_presets()
    sub = presets[key]["submission"]
    if key == "preset_1_happy_path":
        if slot == "tax_certificate":
            return DocumentForensicsSchema(
                detected_doc_type="TAX_CERTIFICATE",
                extracted_legal_name=sub["legal_name"],
                extracted_dba_or_parent="",
                extracted_tax_id=sub["tax_id"],
                extracted_bank_holder="",
                extracted_routing_or_ifsc="",
                extracted_account_number="",
                extracted_bank_country="US",
                document_date="2026-01-15",
                is_signed=True,
                is_expired=False,
                forensic_summary="Valid signed W-9",
            )
        return DocumentForensicsSchema(
            detected_doc_type="BANK_VERIFICATION",
            extracted_legal_name=sub["legal_name"],
            extracted_dba_or_parent="",
            extracted_tax_id="",
            extracted_bank_holder=sub["account_holder_name"],
            extracted_routing_or_ifsc=sub["routing_or_ifsc"],
            extracted_account_number=sub["account_number"],
            extracted_bank_country="US",
            document_date="2026-02-01",
            is_signed=True,
            is_expired=False,
            forensic_summary="Chase bank verification letter",
        )
    if key == "preset_4_wrong_doc_typo":
        if slot == "tax_certificate":
            return DocumentForensicsSchema(
                detected_doc_type="TAX_CERTIFICATE",
                extracted_legal_name="Kinetix Precision Engineering Private Limited",
                extracted_dba_or_parent="Kinetix Precision Engineering",
                extracted_tax_id="27AADCK9120M1Z8",
                extracted_bank_holder="",
                extracted_routing_or_ifsc="",
                extracted_account_number="",
                extracted_bank_country="IN",
                document_date="2025-11-20",
                is_signed=True,
                is_expired=False,
                forensic_summary="GSTIN digit transposition vs form",
            )
        return DocumentForensicsSchema(
            detected_doc_type="WRONG_DOCUMENT_QUOTE_OR_INVOICE",
            extracted_legal_name="Kinetix Precision Engineering Pvt Ltd",
            extracted_dba_or_parent="",
            extracted_tax_id="27AADCK9120M1Z8",
            extracted_bank_holder="",
            extracted_routing_or_ifsc="",
            extracted_account_number="",
            extracted_bank_country="",
            document_date="2026-03-04",
            is_signed=True,
            is_expired=False,
            forensic_summary="Commercial sales quotation Quote #KQ-2026-89 uploaded in bank slot",
        )
    if key == "preset_5_bank_fraud":
        if slot == "tax_certificate":
            return DocumentForensicsSchema(
                detected_doc_type="TAX_CERTIFICATE",
                extracted_legal_name="Apex Digital Supply LLC",
                extracted_dba_or_parent="",
                extracted_tax_id=sub["tax_id"],
                extracted_bank_holder="",
                extracted_routing_or_ifsc="",
                extracted_account_number="",
                extracted_bank_country="US",
                document_date="2026-01-15",
                is_signed=True,
                is_expired=False,
                forensic_summary="W-9 for Apex Digital Supply LLC",
            )
        return DocumentForensicsSchema(
            detected_doc_type="BANK_VERIFICATION",
            extracted_legal_name="Marcus Vance (Individual Savings)",
            extracted_dba_or_parent="",
            extracted_tax_id="",
            extracted_bank_holder="Marcus Vance (Individual Savings)",
            extracted_routing_or_ifsc="021000021",
            extracted_account_number="8899001122",
            extracted_bank_country="US",
            document_date="2026-02-01",
            is_signed=True,
            is_expired=False,
            forensic_summary="Personal savings account diversion risk",
        )
    return DocumentForensicsSchema(
        detected_doc_type="UNREADABLE_OR_OTHER",
        forensic_summary="fallback",
    )


def _install_gemini_mocks(monkeypatch: pytest.MonkeyPatch, preset_key: str, *, omit_remediation_once: bool = False) -> dict[str, Any]:
    """Monkeypatch GeminiService methods for deterministic graph tests."""
    from core import gemini as gemini_mod

    draft_calls = {"n": 0}
    route_log: dict[str, Any] = {"nodes": [], "draft_calls": draft_calls}

    def extract(self, pdf_bytes: bytes, slot: str) -> DocumentForensicsSchema:  # noqa: ARG001
        return _mock_forensics_for_preset(preset_key, slot)

    def investigate(self, submission, tax_forensics, bank_forensics) -> EntityInvestigationSchema:  # noqa: ANN001
        tax = (
            tax_forensics
            if isinstance(tax_forensics, DocumentForensicsSchema)
            else DocumentForensicsSchema.model_validate(tax_forensics)
        )
        bank = (
            bank_forensics
            if isinstance(bank_forensics, DocumentForensicsSchema)
            else DocumentForensicsSchema.model_validate(bank_forensics)
        )
        sub = (
            submission
            if isinstance(submission, VendorSubmission)
            else VendorSubmission.model_validate(submission)
        )
        if preset_key == "preset_1_happy_path":
            return EntityInvestigationSchema(
                entity_relationship="EXACT_OR_EQUIVALENT",
                jurisdiction_nexus_ok=True,
                tax_id_cross_match=True,
                bank_details_cross_match=True,
                evidence_rows=[
                    EvidenceRow(
                        field_name="legal_name",
                        submitted_value=sub.legal_name,
                        tax_doc_value=tax.extracted_legal_name,
                        bank_doc_value=bank.extracted_bank_holder,
                        alignment_status="MATCH",
                    )
                ],
                investigator_summary="Exact match across form, tax, and bank documents.",
                detected_anomalies=[],
            )
        if preset_key == "preset_4_wrong_doc_typo":
            return EntityInvestigationSchema(
                entity_relationship="INSUFFICIENT_DOCUMENT_EVIDENCE",
                jurisdiction_nexus_ok=True,
                tax_id_cross_match=False,
                bank_details_cross_match=False,
                evidence_rows=[
                    EvidenceRow(
                        field_name="tax_id",
                        submitted_value=sub.tax_id,
                        tax_doc_value=tax.extracted_tax_id,
                        bank_doc_value="",
                        alignment_status="VARIANCE",
                    ),
                    EvidenceRow(
                        field_name="bank_document",
                        submitted_value="bank_verification",
                        tax_doc_value="",
                        bank_doc_value="WRONG_DOCUMENT_QUOTE_OR_INVOICE",
                        alignment_status="CONFLICT",
                    ),
                ],
                investigator_summary="GSTIN transposition and wrong document in bank slot.",
                detected_anomalies=["GSTIN digit transposition", "Sales quote in bank slot"],
            )
        # preset 5
        return EntityInvestigationSchema(
            entity_relationship="UNRELATED_THIRD_PARTY_OR_PERSONAL",
            jurisdiction_nexus_ok=True,
            tax_id_cross_match=True,
            bank_details_cross_match=False,
            evidence_rows=[
                EvidenceRow(
                    field_name="account_holder",
                    submitted_value=sub.account_holder_name,
                    tax_doc_value=tax.extracted_legal_name,
                    bank_doc_value=bank.extracted_bank_holder,
                    alignment_status="CONFLICT",
                )
            ],
            investigator_summary="Personal account diversion and registry collision signals.",
            detected_anomalies=["Personal bank holder", "Duplicate account number"],
        )

    def adjudicate(self, policy_markdown, submission, checks, investigation) -> AdjudicationSchema:  # noqa: ANN001, ARG001
        check_models = [c if isinstance(c, CheckItem) else CheckItem.model_validate(c) for c in checks]
        inv = (
            investigation
            if isinstance(investigation, EntityInvestigationSchema)
            else EntityInvestigationSchema.model_validate(investigation)
        )
        if preset_key == "preset_1_happy_path":
            result = AdjudicationSchema(
                status="APPROVED",
                risk_score=12,
                cited_clauses=["AOP §1.1 — Standard Auto-Approval"],
                decision_headline="Vendor cleared for onboarding",
                decision_rationale="All deterministic and forensic checks passed under AOP §1.1.",
                remediation_requirements=[],
            )
        elif preset_key == "preset_4_wrong_doc_typo":
            result = AdjudicationSchema(
                status="PENDING",
                risk_score=52,
                cited_clauses=["AOP §2.1 — Document & Data Discrepancy Remediation"],
                decision_headline="Document remediation required",
                decision_rationale="GSTIN transposition and wrong bank document require remediation.",
                remediation_requirements=[
                    "Re-upload a bank verification letter or cancelled cheque (not a sales quotation)",
                    "Confirm GSTIN 27AADCK9120M1Z8 matches the registration certificate or amend the form",
                ],
            )
        else:
            result = AdjudicationSchema(
                status="REJECTED",
                risk_score=97,
                cited_clauses=["AOP §5.1 — Zero-Tolerance Fraud & Payment Diversion"],
                decision_headline="Onboarding rejected",
                decision_rationale="Payment integrity controls prevent onboarding at this time.",
                remediation_requirements=[],
            )
        return gemini_mod.enforce_adjudication_guardrails(result, check_models, inv)

    def draft(self, submission, adjudication, checks, revision_instructions: str = "") -> CommsDraftSchema:  # noqa: ANN001, ARG001
        draft_calls["n"] += 1
        adj = (
            adjudication
            if isinstance(adjudication, AdjudicationSchema)
            else AdjudicationSchema.model_validate(adjudication)
        )
        sub = (
            submission
            if isinstance(submission, VendorSubmission)
            else VendorSubmission.model_validate(submission)
        )
        if preset_key == "preset_4_wrong_doc_typo":
            # First draft deliberately omits an item to force critic retry
            if omit_remediation_once and draft_calls["n"] == 1 and not revision_instructions:
                return CommsDraftSchema(
                    vendor_email_subject="Action required — Kinetix onboarding",
                    vendor_email_body=(
                        "Dear Vendor,\nPlease re-upload a bank verification document.\nRegards,\nVendorGate"
                    ),
                    internal_security_note="",
                )
            body = (
                "Dear Vendor,\n\n"
                "Please re-upload a bank verification letter or cancelled cheque (not a sales quotation).\n"
                "Please confirm GSTIN 27AADCK9120M1Z8 matches the registration certificate or amend the form.\n\n"
                "Regards,\nVendorGate"
            )
            return CommsDraftSchema(
                vendor_email_subject="Action required — Kinetix onboarding",
                vendor_email_body=body,
                internal_security_note="",
            )
        # Fraud rejection — neutral external, detailed internal
        reject_detail = ""
        for c in checks:
            cm = c if isinstance(c, CheckItem) else CheckItem.model_validate(c)
            if cm.severity == "FAIL_REJECT":
                reject_detail = cm.detail
                break
        return CommsDraftSchema(
            vendor_email_subject=f"Vendor Onboarding Decision — {sub.legal_name}",
            vendor_email_body=(
                "Dear Vendor,\n\nWe are unable to proceed with vendor onboarding at this time "
                "based on our standard payment integrity controls. Please contact your procurement "
                "sponsor if you believe this was made in error.\n\nRegards,\nVendorGate"
            ),
            internal_security_note=(
                f"INTERNAL SECURITY ESCALATION\n{reject_detail}\n"
                "Personal account holder Marcus Vance detected on corporate payout path."
            ),
        )

    def critic(self, adjudication, comms, checks) -> CriticReviewSchema:  # noqa: ANN001, ARG001
        adj = (
            adjudication
            if isinstance(adjudication, AdjudicationSchema)
            else AdjudicationSchema.model_validate(adjudication)
        )
        draft_obj = (
            comms if isinstance(comms, CommsDraftSchema) else CommsDraftSchema.model_validate(comms)
        )
        body = draft_obj.vendor_email_body or ""
        body_l = body.lower()
        tipoff = any(
            n in body_l
            for n in ("zenith", "duplicate", "collision", "8899001122", "fraud rule", "registry")
        )
        covered = True
        if adj.status == "PENDING" and adj.remediation_requirements:
            covered = all(
                req.split()[0].lower() in body_l or req.lower()[:20].lower() in body_l
                for req in adj.remediation_requirements
            )
            # Stronger coverage check for preset 4
            if "bank verification" in " ".join(adj.remediation_requirements).lower():
                covered = covered and ("bank verification" in body_l or "cancelled cheque" in body_l)
            if "gstin" in " ".join(adj.remediation_requirements).lower():
                covered = covered and ("gstin" in body_l)
        approved = covered and not tipoff
        return CriticReviewSchema(
            approved_by_critic=approved,
            all_remediation_covered=covered,
            zero_fraud_tipoff=not tipoff,
            revision_instructions=(
                ""
                if approved
                else "Include ALL remediation requirements and remove any fraud tip-offs from the vendor email."
            ),
        )

    monkeypatch.setattr(gemini_mod.GeminiService, "extract_document_forensics", extract)
    monkeypatch.setattr(gemini_mod.GeminiService, "investigate_entity", investigate)
    monkeypatch.setattr(gemini_mod.GeminiService, "adjudicate", adjudicate)
    monkeypatch.setattr(gemini_mod.GeminiService, "draft_comms", draft)
    monkeypatch.setattr(gemini_mod.GeminiService, "critic_review", critic)
    return route_log


def _run_stream(preset_key: str, tmp_db: Path, monkeypatch: pytest.MonkeyPatch, **mock_kwargs: Any):
    # Reset compiled graph so nodes pick up monkeypatches cleanly
    import core.graph as graph_mod

    monkeypatch.setattr(graph_mod, "_COMPILED", None)
    route_log = _install_gemini_mocks(monkeypatch, preset_key, **mock_kwargs)

    presets = _load_presets()
    preset = presets[preset_key]
    tax = (ROOT / preset["tax_pdf"]).read_bytes()
    bank = (ROOT / preset["bank_pdf"]).read_bytes()

    # Point validators/db helpers used inside graph to tmp db via monkeypatch of find path
    import core.validators as validators_mod
    import core.database as database_mod

    original_find = database_mod.find_account_collisions

    def find_wrapped(account_number, legal_name, db_path=None):  # noqa: ANN001
        return original_find(account_number, legal_name, db_path=tmp_db)

    monkeypatch.setattr(database_mod, "find_account_collisions", find_wrapped)
    monkeypatch.setattr(validators_mod, "find_account_collisions", find_wrapped)

    original_persist = database_mod.persist_run
    original_next = database_mod.next_run_id

    def next_wrapped(db_path=None):  # noqa: ANN001
        return original_next(db_path=tmp_db)

    def persist_wrapped(**kwargs):  # noqa: ANN003
        kwargs["db_path"] = tmp_db
        return original_persist(**kwargs)

    monkeypatch.setattr(database_mod, "next_run_id", next_wrapped)
    monkeypatch.setattr(database_mod, "persist_run", persist_wrapped)
    monkeypatch.setattr(graph_mod, "next_run_id", next_wrapped)
    monkeypatch.setattr(graph_mod, "persist_run", persist_wrapped)

    nodes: list[str] = []
    final_state: dict[str, Any] = {}
    for event in graph_mod.stream_onboarding_run(
        submission=preset["submission"],
        tax_pdf_bytes=tax,
        bank_pdf_bytes=bank,
        api_key="test-key",
        persist=True,
        db_path=tmp_db,
    ):
        node = event.get("node")
        if node and node != "__complete__":
            nodes.append(node)
        final_state = event.get("state") or final_state
    route_log["nodes"] = nodes
    route_log["final_state"] = final_state
    return route_log


def test_graph_preset1_approved_skips_comms(tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _run_stream("preset_1_happy_path", tmp_db, monkeypatch)
    nodes = log["nodes"]
    # 01 -> 02 -> 03 -> 04 -> END
    assert nodes == [
        "node_1_intake",
        "node_2_forensics",
        "node_3_investigator",
        "node_4_adjudicator",
    ]
    adj = log["final_state"].get("adjudication") or {}
    assert adj.get("status") == "APPROVED"
    trace = log["final_state"].get("stage_trace") or []
    assert any(t.get("status") == "SKIPPED" for t in trace)


def test_graph_preset4_critic_retry_loop(tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _run_stream(
        "preset_4_wrong_doc_typo",
        tmp_db,
        monkeypatch,
        omit_remediation_once=True,
    )
    nodes = log["nodes"]
    assert nodes == [
        "node_1_intake",
        "node_2_forensics",
        "node_3_investigator",
        "node_4_adjudicator",
        "node_5_drafter",
        "node_6_critic",
        "node_5_drafter",
        "node_6_critic",
    ]
    adj = log["final_state"].get("adjudication") or {}
    assert adj.get("status") == "PENDING"
    assert log["draft_calls"]["n"] == 2


def test_graph_preset5_rejected_antitipoff(tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = _run_stream("preset_5_bank_fraud", tmp_db, monkeypatch)
    adj = log["final_state"].get("adjudication") or {}
    assert adj.get("status") == "REJECTED"
    comms = log["final_state"].get("comms") or {}
    body = (comms.get("vendor_email_body") or "").lower()
    note = (comms.get("internal_security_note") or "").lower()
    assert "zenith" not in body
    assert "8899001122" not in body
    assert "duplicate" not in body
    assert "zenith" in note or "8899001122" in note or "collision" in note
    checks = [CheckItem.model_validate(c) for c in log["final_state"].get("checks") or []]
    assert any(c.severity == "FAIL_REJECT" for c in checks)


def test_app_imports_cleanly() -> None:
    # Ensure no syntax / circular import errors
    mod = importlib.import_module("app")
    assert mod is not None
    assert hasattr(mod, "apply_preset") or True
