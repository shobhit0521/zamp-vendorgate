"""Resilient Google GenAI multimodal & reasoning service for VendorGate."""

from __future__ import annotations

import json
import os
from typing import Any, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from core.models import (
    AdjudicationSchema,
    CheckItem,
    CommsDraftSchema,
    CriticReviewSchema,
    DocumentForensicsSchema,
    EntityInvestigationSchema,
    VendorSubmission,
)

T = TypeVar("T", bound=BaseModel)

FAST_MODEL = "gemini-3.5-flash-lite"
DEEP_MODEL = "gemini-4-hydrogen"
OPTIONAL_FLASH = "gemini-3.8-flash"


def resolve_api_key(session_override: str = "") -> str:
    """Resolve GEMINI_API_KEY: session override -> st.secrets -> env."""
    if session_override and session_override.strip():
        return session_override.strip()
    try:
        import streamlit as st

        try:
            val = st.secrets["GEMINI_API_KEY"]
            if val:
                return str(val)
        except Exception:
            # StreamlitSecretNotFoundError / KeyError / FileNotFoundError
            pass
    except Exception:
        pass
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def _is_model_access_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    needles = (
        "not found",
        "not supported",
        "permission",
        "quota",
        "resource_exhausted",
        "unavailable",
        "model",
        "403",
        "404",
        "429",
        "access",
        "tier",
    )
    return any(n in msg for n in needles)


class GeminiService:
    def __init__(
        self,
        api_key: str,
        model_mode: str = "Hybrid: Hydrogen + Flash-Lite",
    ) -> None:
        self.api_key = api_key
        self.model_mode = model_mode
        self.client = genai.Client(api_key=api_key) if api_key else None
        self.fast_model = FAST_MODEL
        if "Flash-Lite Only" in model_mode or model_mode == "fast":
            self.deep_model = FAST_MODEL
        else:
            self.deep_model = DEEP_MODEL

    def _generate_structured(
        self,
        *,
        model: str,
        contents: list[Any],
        schema: Type[T],
        system_instruction: str = "",
    ) -> T:
        if not self.client:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        config_kwargs: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        config = types.GenerateContentConfig(**config_kwargs)

        models_to_try = [model]
        if model == DEEP_MODEL and FAST_MODEL not in models_to_try:
            models_to_try.append(FAST_MODEL)

        last_exc: BaseException | None = None
        for m in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=m,
                    contents=contents,
                    config=config,
                )
                text = response.text or ""
                return schema.model_validate_json(text)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if m == DEEP_MODEL and _is_model_access_error(exc):
                    continue
                if m != models_to_try[-1] and _is_model_access_error(exc):
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def extract_document_forensics(
        self,
        pdf_bytes: bytes,
        slot: str,
    ) -> DocumentForensicsSchema:
        prompt = (
            f"You are a KYB document forensics analyst. Analyze this PDF uploaded in the '{slot}' slot. "
            "Classify the document type and extract all visible entity, tax, and banking fields. "
            "If this is a sales quote/invoice instead of tax or bank proof, set detected_doc_type to "
            "WRONG_DOCUMENT_QUOTE_OR_INVOICE. Return structured JSON only."
        )
        part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        return self._generate_structured(
            model=self.fast_model,
            contents=[prompt, part],
            schema=DocumentForensicsSchema,
        )

    def investigate_entity(
        self,
        submission: VendorSubmission | dict[str, Any],
        tax_forensics: DocumentForensicsSchema | dict[str, Any],
        bank_forensics: DocumentForensicsSchema | dict[str, Any],
    ) -> EntityInvestigationSchema:
        sub = (
            submission
            if isinstance(submission, VendorSubmission)
            else VendorSubmission.model_validate(submission)
        )
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
        prompt = (
            "You are the Entity Investigator for VendorGate KYB. Cross-reference the submitted form "
            "against tax certificate forensics and bank verification forensics. Build evidence_rows "
            "for legal_name, dba/parent, tax_id, account_holder, routing/IFSC, account_number, and "
            "bank_country. Classify entity_relationship. Flag personal-account diversion and DBA gaps.\n\n"
            f"SUBMISSION:\n{sub.model_dump_json(indent=2)}\n\n"
            f"TAX_FORENSICS:\n{tax.model_dump_json(indent=2)}\n\n"
            f"BANK_FORENSICS:\n{bank.model_dump_json(indent=2)}"
        )
        return self._generate_structured(
            model=self.deep_model,
            contents=[prompt],
            schema=EntityInvestigationSchema,
        )

    def adjudicate(
        self,
        policy_markdown: str,
        submission: VendorSubmission | dict[str, Any],
        checks: list[CheckItem] | list[dict[str, Any]],
        investigation: EntityInvestigationSchema | dict[str, Any],
    ) -> AdjudicationSchema:
        sub = (
            submission
            if isinstance(submission, VendorSubmission)
            else VendorSubmission.model_validate(submission)
        )
        check_models = [
            c if isinstance(c, CheckItem) else CheckItem.model_validate(c) for c in checks
        ]
        inv = (
            investigation
            if isinstance(investigation, EntityInvestigationSchema)
            else EntityInvestigationSchema.model_validate(investigation)
        )
        prompt = (
            "You are the Policy Adjudicator. Apply the Agent Operating Procedure (AOP) clauses "
            "verbatim. Cite clause headers exactly as written (e.g. 'AOP §1.1 — Standard Auto-Approval'). "
            "Decide APPROVED, PENDING, or REJECTED. Populate remediation_requirements for PENDING. "
            "For REJECTED fraud cases, remediation_requirements may be empty; rationale must not tip off "
            "the vendor about registry collisions.\n\n"
            f"POLICY:\n{policy_markdown}\n\n"
            f"SUBMISSION:\n{sub.model_dump_json(indent=2)}\n\n"
            f"NODE_01_CHECKS:\n{json.dumps([c.model_dump() for c in check_models], indent=2)}\n\n"
            f"INVESTIGATION:\n{inv.model_dump_json(indent=2)}"
        )
        result = self._generate_structured(
            model=self.deep_model,
            contents=[prompt],
            schema=AdjudicationSchema,
            system_instruction="Cite AOP clause headers verbatim. Prefer deterministic FAIL_REJECT over LLM override.",
        )
        return enforce_adjudication_guardrails(result, check_models, inv)

    def draft_comms(
        self,
        submission: VendorSubmission | dict[str, Any],
        adjudication: AdjudicationSchema | dict[str, Any],
        checks: list[CheckItem] | list[dict[str, Any]],
        revision_instructions: str = "",
    ) -> CommsDraftSchema:
        sub = (
            submission
            if isinstance(submission, VendorSubmission)
            else VendorSubmission.model_validate(submission)
        )
        adj = (
            adjudication
            if isinstance(adjudication, AdjudicationSchema)
            else AdjudicationSchema.model_validate(adjudication)
        )
        check_models = [
            c if isinstance(c, CheckItem) else CheckItem.model_validate(c) for c in checks
        ]
        prompt = (
            "Draft vendor-facing email and internal FinOps/security note. "
            "Vendor email MUST cover every remediation_requirements item when status is PENDING. "
            "Vendor email MUST NEVER mention duplicate account collisions, registry matches, fraud rules, "
            "or tip off about internal security findings. Put those details ONLY in internal_security_note.\n\n"
            f"SUBMISSION:\n{sub.model_dump_json(indent=2)}\n\n"
            f"ADJUDICATION:\n{adj.model_dump_json(indent=2)}\n\n"
            f"CHECKS:\n{json.dumps([c.model_dump() for c in check_models], indent=2)}\n\n"
            f"REVISION_INSTRUCTIONS:\n{revision_instructions or '(none)'}"
        )
        return self._generate_structured(
            model=self.fast_model,
            contents=[prompt],
            schema=CommsDraftSchema,
        )

    def critic_review(
        self,
        adjudication: AdjudicationSchema | dict[str, Any],
        comms: CommsDraftSchema | dict[str, Any],
        checks: list[CheckItem] | list[dict[str, Any]],
    ) -> CriticReviewSchema:
        adj = (
            adjudication
            if isinstance(adjudication, AdjudicationSchema)
            else AdjudicationSchema.model_validate(adjudication)
        )
        draft = (
            comms if isinstance(comms, CommsDraftSchema) else CommsDraftSchema.model_validate(comms)
        )
        check_models = [
            c if isinstance(c, CheckItem) else CheckItem.model_validate(c) for c in checks
        ]
        prompt = (
            "You are the Compliance Critic. Approve the vendor email only if: "
            "(1) all remediation_requirements are covered in the vendor email body when status is PENDING, "
            "(2) zero fraud tip-offs appear in the vendor email (no registry collisions, no fraud rule names, "
            "no duplicate account details). Internal note may contain full detail.\n\n"
            f"ADJUDICATION:\n{adj.model_dump_json(indent=2)}\n\n"
            f"COMMS:\n{draft.model_dump_json(indent=2)}\n\n"
            f"CHECKS:\n{json.dumps([c.model_dump() for c in check_models], indent=2)}"
        )
        return self._generate_structured(
            model=self.fast_model,
            contents=[prompt],
            schema=CriticReviewSchema,
        )


def enforce_adjudication_guardrails(
    adjudication: AdjudicationSchema,
    checks: list[CheckItem],
    investigation: EntityInvestigationSchema | None = None,
) -> AdjudicationSchema:
    """Deterministic overrides so LLM cannot soften FAIL_REJECT / hard fraud signals."""
    reject_checks = [c for c in checks if c.severity == "FAIL_REJECT"]
    if reject_checks:
        detail = reject_checks[0].detail
        adjudication.status = "REJECTED"
        adjudication.risk_score = max(adjudication.risk_score, 95)
        if "AOP §5.1 — Zero-Tolerance Fraud & Payment Diversion" not in adjudication.cited_clauses:
            adjudication.cited_clauses = list(adjudication.cited_clauses) + [
                "AOP §5.1 — Zero-Tolerance Fraud & Payment Diversion"
            ]
        adjudication.decision_headline = adjudication.decision_headline or "Onboarding rejected"
        if "fraud" not in adjudication.decision_rationale.lower():
            adjudication.decision_rationale = (
                "Vendor onboarding cannot proceed due to payment integrity controls. "
                "Internal security has been notified. "
                f"(INTERNAL CONTEXT WITHHELD FROM VENDOR: {detail})"
            )
        adjudication.remediation_requirements = []
        return adjudication

    pending_checks = [c for c in checks if c.severity == "FAIL_PENDING"]
    if pending_checks and adjudication.status == "APPROVED":
        adjudication.status = "PENDING"
        adjudication.risk_score = max(adjudication.risk_score, 55)
        if not adjudication.cited_clauses:
            adjudication.cited_clauses = ["AOP §2.1 — Document & Data Discrepancy Remediation"]

    if investigation and investigation.entity_relationship == "UNRELATED_THIRD_PARTY_OR_PERSONAL":
        adjudication.status = "REJECTED"
        adjudication.risk_score = max(adjudication.risk_score, 90)
        if "AOP §5.1 — Zero-Tolerance Fraud & Payment Diversion" not in adjudication.cited_clauses:
            adjudication.cited_clauses = list(adjudication.cited_clauses) + [
                "AOP §5.1 — Zero-Tolerance Fraud & Payment Diversion"
            ]

    return adjudication
