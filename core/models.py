"""Flat Pydantic schemas for VendorGate structured Gemini outputs and graph state."""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class VendorSubmission(BaseModel):
    legal_name: str = ""
    dba_name: str = ""
    country: Literal["US", "IN", "GB"] = "US"
    registration_address: str = ""
    contact_email: str = ""
    tax_id: str = ""
    expected_annual_spend_usd: int = 0
    account_holder_name: str = ""
    bank_country: Literal["US", "IN", "GB", "KY", "AE"] = "US"
    routing_or_ifsc: str = ""
    account_number: str = ""


class CheckItem(BaseModel):
    check_code: str = ""
    label: str = ""
    passed: bool = False
    severity: Literal["PASS", "WARN", "FAIL_PENDING", "FAIL_REJECT"] = "PASS"
    detail: str = ""


class DocumentForensicsSchema(BaseModel):
    detected_doc_type: Literal[
        "TAX_CERTIFICATE",
        "BANK_VERIFICATION",
        "WRONG_DOCUMENT_QUOTE_OR_INVOICE",
        "UNREADABLE_OR_OTHER",
    ] = "UNREADABLE_OR_OTHER"
    extracted_legal_name: str = ""
    extracted_dba_or_parent: str = ""
    extracted_tax_id: str = ""
    extracted_bank_holder: str = ""
    extracted_routing_or_ifsc: str = ""
    extracted_account_number: str = ""
    extracted_bank_country: str = ""
    document_date: str = ""
    is_signed: bool = False
    is_expired: bool = False
    forensic_summary: str = ""


class EvidenceRow(BaseModel):
    field_name: str = ""
    submitted_value: str = ""
    tax_doc_value: str = ""
    bank_doc_value: str = ""
    alignment_status: Literal["MATCH", "VARIANCE", "CONFLICT", "MISSING"] = "MISSING"


class EntityInvestigationSchema(BaseModel):
    entity_relationship: Literal[
        "EXACT_OR_EQUIVALENT",
        "PARENT_SUBSIDIARY_OR_DBA",
        "UNRELATED_THIRD_PARTY_OR_PERSONAL",
        "INSUFFICIENT_DOCUMENT_EVIDENCE",
    ] = "INSUFFICIENT_DOCUMENT_EVIDENCE"
    jurisdiction_nexus_ok: bool = False
    tax_id_cross_match: bool = False
    bank_details_cross_match: bool = False
    evidence_rows: list[EvidenceRow] = Field(default_factory=list)
    investigator_summary: str = ""
    detected_anomalies: list[str] = Field(default_factory=list)


class AdjudicationSchema(BaseModel):
    status: Literal["APPROVED", "PENDING", "REJECTED"] = "PENDING"
    risk_score: int = 50
    cited_clauses: list[str] = Field(default_factory=list)
    decision_headline: str = ""
    decision_rationale: str = ""
    remediation_requirements: list[str] = Field(default_factory=list)


class CommsDraftSchema(BaseModel):
    vendor_email_subject: str = ""
    vendor_email_body: str = ""
    internal_security_note: str = ""


class CriticReviewSchema(BaseModel):
    approved_by_critic: bool = False
    all_remediation_covered: bool = False
    zero_fraud_tipoff: bool = False
    revision_instructions: str = ""


class StageTraceEntry(BaseModel):
    node_id: str = ""
    stage_name: str = ""
    status: Literal["DONE", "SKIPPED", "FLAGGED", "RETRY", "RUNNING"] = "DONE"
    duration_ms: int = 0
    summary: str = ""
    output_json: str = ""


class VendorGraphState(TypedDict, total=False):
    run_id: str
    submission: dict
    tax_pdf_bytes: bytes
    bank_pdf_bytes: bytes
    policy_markdown: str
    api_key: str
    model_mode: str
    checks: list
    tax_forensics: dict
    bank_forensics: dict
    investigation: dict
    adjudication: dict
    comms: dict
    critic: dict
    stage_trace: list
    draft_attempt: int
    revision_instructions: str
    skip_comms: bool
    pdf_invalid: bool
    final_status: str
    started_at_ms: int
