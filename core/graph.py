"""6-node LangGraph StateGraph for VendorGate autonomous KYB onboarding."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterator

from langgraph.graph import END, StateGraph

from core.database import next_run_id, persist_run
from core.gemini import GeminiService
from core.models import (
    AdjudicationSchema,
    CheckItem,
    CommsDraftSchema,
    CriticReviewSchema,
    DocumentForensicsSchema,
    EntityInvestigationSchema,
    VendorGraphState,
    VendorSubmission,
)
from core.validators import run_intake_checks

POLICY_PATH = Path(__file__).resolve().parent / "policy.md"


def load_policy(override: str = "") -> str:
    if override and override.strip():
        return override
    return POLICY_PATH.read_text(encoding="utf-8")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _append_trace(
    state: VendorGraphState,
    *,
    node_id: str,
    stage_name: str,
    status: str,
    duration_ms: int,
    summary: str,
    output: Any,
) -> list[dict[str, Any]]:
    trace = list(state.get("stage_trace") or [])
    payload = output
    if hasattr(output, "model_dump"):
        payload = output.model_dump()
    trace.append(
        {
            "node_id": node_id,
            "stage_name": stage_name,
            "status": status,
            "duration_ms": duration_ms,
            "summary": summary,
            "output_json": json.dumps(payload, default=str),
        }
    )
    return trace


def _service(state: VendorGraphState) -> GeminiService:
    return GeminiService(
        api_key=state.get("api_key") or "",
        model_mode=state.get("model_mode") or "Hybrid: Hydrogen + Flash-Lite",
    )


def node_1_intake(state: VendorGraphState) -> dict[str, Any]:
    t0 = _now_ms()
    submission = state.get("submission") or {}
    tax_bytes = state.get("tax_pdf_bytes") or b""
    bank_bytes = state.get("bank_pdf_bytes") or b""
    checks = run_intake_checks(submission, tax_bytes, bank_bytes)
    pdf_invalid = any(
        (not c.passed and c.check_code in {"TAX_PDF_MAGIC", "BANK_PDF_MAGIC"}) for c in checks
    )
    reject = any(c.severity == "FAIL_REJECT" for c in checks)
    warn = any(c.severity in {"WARN", "FAIL_PENDING"} for c in checks)
    status = "FLAGGED" if (reject or warn or pdf_invalid) else "DONE"
    summary = (
        f"{sum(1 for c in checks if c.passed)}/{len(checks)} checks passed"
        + ("; PDF invalid — skipping forensics" if pdf_invalid else "")
        + ("; FAIL_REJECT present" if reject else "")
    )
    duration = _now_ms() - t0
    trace = _append_trace(
        state,
        node_id="01",
        stage_name="Intake Guardrails",
        status=status,
        duration_ms=duration,
        summary=summary,
        output=[c.model_dump() for c in checks],
    )
    return {
        "checks": [c.model_dump() for c in checks],
        "pdf_invalid": pdf_invalid,
        "stage_trace": trace,
        "draft_attempt": 0,
        "revision_instructions": "",
        "skip_comms": False,
    }


def _route_after_intake(state: VendorGraphState) -> str:
    if state.get("pdf_invalid"):
        return "node_4_adjudicator"
    return "node_2_forensics"


def node_2_forensics(state: VendorGraphState) -> dict[str, Any]:
    t0 = _now_ms()
    svc = _service(state)
    tax = svc.extract_document_forensics(state.get("tax_pdf_bytes") or b"", "tax_certificate")
    bank = svc.extract_document_forensics(state.get("bank_pdf_bytes") or b"", "bank_verification")
    flagged = (
        tax.detected_doc_type == "WRONG_DOCUMENT_QUOTE_OR_INVOICE"
        or bank.detected_doc_type == "WRONG_DOCUMENT_QUOTE_OR_INVOICE"
        or not tax.is_signed
        or not bank.is_signed
    )
    duration = _now_ms() - t0
    summary = (
        f"Tax={tax.detected_doc_type}; Bank={bank.detected_doc_type}; "
        f"signed tax/bank={tax.is_signed}/{bank.is_signed}"
    )
    trace = _append_trace(
        state,
        node_id="02",
        stage_name="Document Forensics",
        status="FLAGGED" if flagged else "DONE",
        duration_ms=duration,
        summary=summary,
        output={"tax": tax.model_dump(), "bank": bank.model_dump()},
    )
    return {
        "tax_forensics": tax.model_dump(),
        "bank_forensics": bank.model_dump(),
        "stage_trace": trace,
    }


def node_3_investigator(state: VendorGraphState) -> dict[str, Any]:
    t0 = _now_ms()
    svc = _service(state)
    inv = svc.investigate_entity(
        state.get("submission") or {},
        state.get("tax_forensics") or {},
        state.get("bank_forensics") or {},
    )
    duration = _now_ms() - t0
    flagged = inv.entity_relationship not in {"EXACT_OR_EQUIVALENT"} or bool(inv.detected_anomalies)
    summary = f"{inv.entity_relationship}; anomalies={len(inv.detected_anomalies)}"
    trace = _append_trace(
        state,
        node_id="03",
        stage_name="Entity Investigator",
        status="FLAGGED" if flagged else "DONE",
        duration_ms=duration,
        summary=summary,
        output=inv,
    )
    return {"investigation": inv.model_dump(), "stage_trace": trace}


def node_4_adjudicator(state: VendorGraphState) -> dict[str, Any]:
    t0 = _now_ms()
    checks = [CheckItem.model_validate(c) for c in (state.get("checks") or [])]
    inv_raw = state.get("investigation")
    if not inv_raw:
        # PDF-invalid shortcut path — synthesize minimal investigation
        inv = EntityInvestigationSchema(
            entity_relationship="INSUFFICIENT_DOCUMENT_EVIDENCE",
            jurisdiction_nexus_ok=False,
            tax_id_cross_match=False,
            bank_details_cross_match=False,
            evidence_rows=[],
            investigator_summary="Forensics skipped due to invalid or missing PDF bytes.",
            detected_anomalies=["Missing or invalid supporting PDFs"],
        )
    else:
        inv = EntityInvestigationSchema.model_validate(inv_raw)

    # If no API key and deterministic reject/pending already known, still allow Gemini path;
    # tests monkeypatch GeminiService methods.
    svc = _service(state)
    policy = state.get("policy_markdown") or load_policy()
    try:
        adjudication = svc.adjudicate(policy, state.get("submission") or {}, checks, inv)
    except Exception:
        # Deterministic fallback for offline / missing key demos
        from core.gemini import enforce_adjudication_guardrails

        adjudication = AdjudicationSchema(
            status="PENDING",
            risk_score=60,
            cited_clauses=["AOP §2.1 — Document & Data Discrepancy Remediation"],
            decision_headline="Manual review required",
            decision_rationale="Adjudicator unavailable; deterministic guardrails applied.",
            remediation_requirements=["Re-submit complete signed tax and bank PDFs"],
        )
        adjudication = enforce_adjudication_guardrails(adjudication, checks, inv)

    duration = _now_ms() - t0
    skip_comms = adjudication.status == "APPROVED"
    if skip_comms:
        adjudication.decision_headline = (
            adjudication.decision_headline or "Vendor cleared for onboarding"
        )
        # Attach clean confirmation summary for APPROVED path
        confirmation = {
            "onboarding_confirmation": (
                f"{(state.get('submission') or {}).get('legal_name', 'Vendor')} is approved "
                "under AOP §1.1. No remediation communications required."
            )
        }
        adj_dump = adjudication.model_dump()
        adj_dump.update(confirmation)
    else:
        adj_dump = adjudication.model_dump()

    summary = f"{adjudication.status} · risk {adjudication.risk_score}/100"
    if skip_comms:
        summary += " · Gate 2 skip Comms/Critic"
    trace = _append_trace(
        state,
        node_id="04",
        stage_name="Policy Adjudicator",
        status="DONE",
        duration_ms=duration,
        summary=summary,
        output=adj_dump,
    )
    if skip_comms:
        # Mark 05-06 skipped on the rail
        trace.append(
            {
                "node_id": "05-06",
                "stage_name": "Comms & Critic QA",
                "status": "SKIPPED",
                "duration_ms": 0,
                "summary": "SKIPPED (Auto-Approved via Conditional Gate 2)",
                "output_json": "{}",
            }
        )
    return {
        "adjudication": adj_dump,
        "investigation": inv.model_dump(),
        "skip_comms": skip_comms,
        "final_status": adjudication.status,
        "stage_trace": trace,
        "comms": {} if skip_comms else state.get("comms") or {},
    }


def _route_after_adjudicator(state: VendorGraphState) -> str:
    adj = state.get("adjudication") or {}
    if adj.get("status") == "APPROVED" or state.get("skip_comms"):
        return END
    return "node_5_drafter"


def node_5_drafter(state: VendorGraphState) -> dict[str, Any]:
    t0 = _now_ms()
    attempt = int(state.get("draft_attempt") or 0) + 1
    svc = _service(state)
    checks = state.get("checks") or []
    revision = state.get("revision_instructions") or ""
    try:
        comms = svc.draft_comms(
            state.get("submission") or {},
            state.get("adjudication") or {},
            checks,
            revision_instructions=revision,
        )
    except Exception:
        adj = AdjudicationSchema.model_validate(state.get("adjudication") or {})
        rem = "\n".join(f"- {r}" for r in adj.remediation_requirements) or "- Contact procurement"
        reject_detail = next(
            (
                CheckItem.model_validate(c).detail
                for c in checks
                if CheckItem.model_validate(c).severity == "FAIL_REJECT"
            ),
            "",
        )
        body = (
            f"Dear Vendor,\n\nRegarding your onboarding for "
            f"{(state.get('submission') or {}).get('legal_name', 'your entity')}:\n\n"
        )
        if adj.status == "REJECTED":
            body += (
                "We are unable to proceed with vendor onboarding at this time based on our "
                "standard payment integrity controls. Please contact your procurement sponsor "
                "if you believe this decision was made in error.\n"
            )
        else:
            body += "Additional information is required before we can complete onboarding:\n" + rem + "\n"
        body += "\nRegards,\nVendorGate Procurement Governance"
        internal = ""
        if reject_detail:
            internal = f"INTERNAL SECURITY ESCALATION:\n{reject_detail}"
        comms = CommsDraftSchema(
            vendor_email_subject=f"Vendor Onboarding Update — {(state.get('submission') or {}).get('legal_name', '')}",
            vendor_email_body=body,
            internal_security_note=internal,
        )
    duration = _now_ms() - t0
    trace = _append_trace(
        state,
        node_id="05",
        stage_name="Comms Drafter",
        status="RETRY" if attempt > 1 else "DONE",
        duration_ms=duration,
        summary=f"Draft attempt {attempt}; subject={comms.vendor_email_subject[:60]}",
        output=comms,
    )
    return {
        "comms": comms.model_dump(),
        "draft_attempt": attempt,
        "stage_trace": trace,
    }


def node_6_critic(state: VendorGraphState) -> dict[str, Any]:
    t0 = _now_ms()
    svc = _service(state)
    try:
        critic = svc.critic_review(
            state.get("adjudication") or {},
            state.get("comms") or {},
            state.get("checks") or [],
        )
    except Exception:
        # Deterministic critic fallback
        adj = AdjudicationSchema.model_validate(state.get("adjudication") or {})
        comms = CommsDraftSchema.model_validate(state.get("comms") or {})
        body_l = (comms.vendor_email_body or "").lower()
        tipoff_needles = (
            "zenith",
            "duplicate",
            "collision",
            "registry",
            "8899001122",
            "fraud",
            "aop §5.1",
        )
        tipoff = any(n in body_l for n in tipoff_needles)
        covered = True
        if adj.status == "PENDING":
            covered = all(
                any(tok.lower() in body_l for tok in r.lower().split()[:3])
                for r in adj.remediation_requirements
            ) if adj.remediation_requirements else True
        critic = CriticReviewSchema(
            approved_by_critic=covered and not tipoff,
            all_remediation_covered=covered,
            zero_fraud_tipoff=not tipoff,
            revision_instructions=(
                ""
                if (covered and not tipoff)
                else "Revise vendor email: cover all remediation items and remove any fraud tip-offs."
            ),
        )
    duration = _now_ms() - t0
    status = "DONE" if critic.approved_by_critic else "RETRY"
    summary = (
        f"approved={critic.approved_by_critic}; "
        f"remediation_covered={critic.all_remediation_covered}; "
        f"zero_tipoff={critic.zero_fraud_tipoff}"
    )
    trace = _append_trace(
        state,
        node_id="06",
        stage_name="Compliance Critic",
        status=status,
        duration_ms=duration,
        summary=summary,
        output=critic,
    )
    return {
        "critic": critic.model_dump(),
        "revision_instructions": critic.revision_instructions,
        "stage_trace": trace,
    }


def _route_after_critic(state: VendorGraphState) -> str:
    critic = state.get("critic") or {}
    attempt = int(state.get("draft_attempt") or 0)
    if (not critic.get("approved_by_critic")) and attempt < 2:
        return "node_5_drafter"
    return END


def build_graph():
    graph = StateGraph(VendorGraphState)
    graph.add_node("node_1_intake", node_1_intake)
    graph.add_node("node_2_forensics", node_2_forensics)
    graph.add_node("node_3_investigator", node_3_investigator)
    graph.add_node("node_4_adjudicator", node_4_adjudicator)
    graph.add_node("node_5_drafter", node_5_drafter)
    graph.add_node("node_6_critic", node_6_critic)

    graph.set_entry_point("node_1_intake")
    graph.add_conditional_edges(
        "node_1_intake",
        _route_after_intake,
        {
            "node_2_forensics": "node_2_forensics",
            "node_4_adjudicator": "node_4_adjudicator",
        },
    )
    graph.add_edge("node_2_forensics", "node_3_investigator")
    graph.add_edge("node_3_investigator", "node_4_adjudicator")
    graph.add_conditional_edges(
        "node_4_adjudicator",
        _route_after_adjudicator,
        {
            "node_5_drafter": "node_5_drafter",
            END: END,
        },
    )
    graph.add_edge("node_5_drafter", "node_6_critic")
    graph.add_conditional_edges(
        "node_6_critic",
        _route_after_critic,
        {
            "node_5_drafter": "node_5_drafter",
            END: END,
        },
    )
    return graph.compile()


_COMPILED = None


def get_compiled_graph():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_graph()
    return _COMPILED


def stream_onboarding_run(
    *,
    submission: VendorSubmission | dict[str, Any],
    tax_pdf_bytes: bytes,
    bank_pdf_bytes: bytes,
    api_key: str = "",
    model_mode: str = "Hybrid: Hydrogen + Flash-Lite",
    policy_markdown: str = "",
    run_id: str = "",
    persist: bool = True,
    db_path: str | Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream LangGraph node updates live, then persist the final run."""
    sub = (
        submission.model_dump()
        if isinstance(submission, VendorSubmission)
        else dict(submission)
    )
    rid = run_id or next_run_id(db_path=db_path)
    started = _now_ms()
    initial: VendorGraphState = {
        "run_id": rid,
        "submission": sub,
        "tax_pdf_bytes": tax_pdf_bytes or b"",
        "bank_pdf_bytes": bank_pdf_bytes or b"",
        "policy_markdown": load_policy(policy_markdown),
        "api_key": api_key,
        "model_mode": model_mode,
        "checks": [],
        "tax_forensics": {},
        "bank_forensics": {},
        "investigation": {},
        "adjudication": {},
        "comms": {},
        "critic": {},
        "stage_trace": [],
        "draft_attempt": 0,
        "revision_instructions": "",
        "skip_comms": False,
        "pdf_invalid": False,
        "final_status": "",
        "started_at_ms": started,
    }

    compiled = get_compiled_graph()
    merged: dict[str, Any] = dict(initial)
    for update in compiled.stream(initial, stream_mode="updates"):
        # update is {node_name: partial_state}
        for node_name, partial in update.items():
            if isinstance(partial, dict):
                merged.update(partial)
            yield {"node": node_name, "partial": partial, "state": dict(merged), "run_id": rid}

    duration = _now_ms() - started
    adjudication = merged.get("adjudication") or {}
    investigation = merged.get("investigation") or {}
    evidence_rows = investigation.get("evidence_rows") or []
    if persist:
        persist_run(
            run_id=rid,
            submission=sub,
            adjudication=adjudication,
            stage_trace=merged.get("stage_trace") or [],
            evidence_rows=evidence_rows,
            comms=merged.get("comms") or {},
            duration_ms=duration,
            db_path=db_path,
        )
    yield {
        "node": "__complete__",
        "partial": {},
        "state": merged,
        "run_id": rid,
        "duration_ms": duration,
    }
