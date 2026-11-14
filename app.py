"""VendorGate — Autonomous KYB & Vendor Onboarding (Streamlit Community Cloud entrypoint)."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.database import get_run, init_and_seed_db, list_runs, run_kpis
from core.gemini import resolve_api_key
from core.graph import load_policy, stream_onboarding_run
from core.models import VendorSubmission
from ui.styles import (
    evidence_matrix_html,
    inject_global_css,
    kpi_strip,
    rail_item_html,
    status_pill,
)

ROOT = Path(__file__).resolve().parent
PRESETS_PATH = ROOT / "data" / "presets.json"
POLICY_PATH = ROOT / "core" / "policy.md"

st.set_page_config(
    page_title="VendorGate · Autonomous KYB",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_and_seed_db()
st.html(inject_global_css())


def _load_presets() -> dict:
    if PRESETS_PATH.exists():
        return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    return {}


def _read_pdf(rel_or_abs: str) -> bytes:
    path = Path(rel_or_abs)
    if not path.is_absolute():
        path = ROOT / path
    return path.read_bytes() if path.exists() else b""


def _blank_submission() -> dict:
    return VendorSubmission().model_dump()


def _ensure_session() -> None:
    defaults = {
        "submission": _blank_submission(),
        "tax_pdf_bytes": b"",
        "bank_pdf_bytes": b"",
        "tax_pdf_name": "",
        "bank_pdf_name": "",
        "active_preset": "manual",
        "policy_markdown": load_policy(),
        "api_key_override": "",
        "model_mode": "Hybrid: Hydrogen + Flash-Lite",
        "live_trace": [],
        "live_state": {},
        "live_run_id": "",
        "history_status": "All Statuses",
        "history_country": "All Countries",
        "history_search": "",
        "inspector_run_id": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_ensure_session()
PRESETS = _load_presets()


@st.dialog("Operating Policy (AOP)", width="large")
def policy_dialog() -> None:
    st.caption("Edit the Agent Operating Procedure used by the Policy Adjudicator for this session.")
    edited = st.text_area(
        "policy.md",
        value=st.session_state.policy_markdown,
        height=420,
        label_visibility="collapsed",
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save Session Policy", type="primary", use_container_width=True):
            st.session_state.policy_markdown = edited
            st.rerun()
    with c2:
        if st.button("Reset to Disk policy.md", use_container_width=True):
            st.session_state.policy_markdown = POLICY_PATH.read_text(encoding="utf-8")
            st.rerun()


def apply_preset(key: str) -> None:
    if key == "manual":
        st.session_state.submission = _blank_submission()
        st.session_state.tax_pdf_bytes = b""
        st.session_state.bank_pdf_bytes = b""
        st.session_state.tax_pdf_name = ""
        st.session_state.bank_pdf_name = ""
        st.session_state.active_preset = "manual"
        return
    preset = PRESETS.get(key)
    if not preset:
        return
    st.session_state.submission = dict(preset["submission"])
    st.session_state.tax_pdf_bytes = _read_pdf(preset["tax_pdf"])
    st.session_state.bank_pdf_bytes = _read_pdf(preset["bank_pdf"])
    st.session_state.tax_pdf_name = Path(preset["tax_pdf"]).name
    st.session_state.bank_pdf_name = Path(preset["bank_pdf"]).name
    st.session_state.active_preset = key


# --- Masthead ---
left, right = st.columns([3.2, 1.6])
with left:
    st.html(
        """
        <div class="vg-masthead" style="border:none;margin:0;padding:0;">
          <div>
            <div class="vg-wordmark">VENDORGATE</div>
            <div class="vg-subtitle">/ Autonomous KYB &amp; Procurement Governance</div>
          </div>
        </div>
        """
    )
with right:
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Operating Policy (AOP)", use_container_width=True):
            policy_dialog()
    with b2:
        with st.popover("Engine Config", use_container_width=True):
            resolved = resolve_api_key(st.session_state.api_key_override)
            status = "Configured" if resolved else "Missing"
            st.markdown(f"**API key status:** `{status}`")
            st.session_state.api_key_override = st.text_input(
                "GEMINI_API_KEY override",
                value=st.session_state.api_key_override,
                type="password",
                help="Session override → st.secrets → environment variable",
            )
            st.session_state.model_mode = st.selectbox(
                "Model mode",
                [
                    "Hybrid: Hydrogen + Flash-Lite",
                    "Fast: Flash-Lite Only",
                    "Hybrid + gemini-3.8-flash selector",
                ],
                index=[
                    "Hybrid: Hydrogen + Flash-Lite",
                    "Fast: Flash-Lite Only",
                    "Hybrid + gemini-3.8-flash selector",
                ].index(st.session_state.model_mode)
                if st.session_state.model_mode
                in {
                    "Hybrid: Hydrogen + Flash-Lite",
                    "Fast: Flash-Lite Only",
                    "Hybrid + gemini-3.8-flash selector",
                }
                else 0,
            )

tab_live, tab_history = st.tabs(["Live Onboarding Review", "Case History & Audit Log"])


with tab_live:
    st.html('<div class="vg-section-label">Scenario Preset Bar</div>')
    preset_keys = [
        ("preset_1_happy_path", "Northstar [Standard US]"),
        ("preset_2_dba_variance", "CloudPulse [DBA Variance]"),
        ("preset_3_offshore_split", "Meridian [Offshore Split]"),
        ("preset_4_wrong_doc_typo", "Kinetix [Wrong Doc + Typo]"),
        ("preset_5_bank_fraud", "Apex [Bank Fraud]"),
        ("manual", "Manual Blank Form"),
    ]
    cols = st.columns(6)
    for col, (key, label) in zip(cols, preset_keys):
        with col:
            active = st.session_state.active_preset == key
            if st.button(
                label,
                key=f"preset_btn_{key}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                apply_preset(key)
                st.rerun()

    left_col, right_col = st.columns([0.4, 0.6], gap="large")

    with left_col:
        st.html('<div class="vg-section-label">Submission Packet</div>')
        sub = st.session_state.submission

        st.markdown("**Entity & Tax Registration**")
        sub["legal_name"] = st.text_input("Legal name", value=sub.get("legal_name", ""))
        sub["dba_name"] = st.text_input("DBA / trade name", value=sub.get("dba_name", ""))
        c_a, c_b = st.columns(2)
        with c_a:
            sub["country"] = st.selectbox(
                "Tax country",
                ["US", "IN", "GB"],
                index=["US", "IN", "GB"].index(sub.get("country", "US")),
            )
        with c_b:
            sub["tax_id"] = st.text_input("Tax ID (EIN / GSTIN / VAT)", value=sub.get("tax_id", ""))
        sub["registration_address"] = st.text_area(
            "Registration address",
            value=sub.get("registration_address", ""),
            height=68,
        )
        sub["contact_email"] = st.text_input("Contact email", value=sub.get("contact_email", ""))
        sub["expected_annual_spend_usd"] = int(
            st.number_input(
                "Expected annual spend (USD)",
                min_value=0,
                step=1000,
                value=int(sub.get("expected_annual_spend_usd", 0) or 0),
            )
        )

        st.markdown("**Payout Banking Coordinates**")
        sub["account_holder_name"] = st.text_input(
            "Account holder name", value=sub.get("account_holder_name", "")
        )
        b1, b2 = st.columns(2)
        with b1:
            sub["bank_country"] = st.selectbox(
                "Bank country",
                ["US", "IN", "GB", "KY", "AE"],
                index=["US", "IN", "GB", "KY", "AE"].index(sub.get("bank_country", "US")),
            )
        with b2:
            sub["routing_or_ifsc"] = st.text_input(
                "Routing / IFSC / SWIFT", value=sub.get("routing_or_ifsc", "")
            )
        sub["account_number"] = st.text_input(
            "Account number", value=sub.get("account_number", "")
        )
        st.session_state.submission = sub

        st.markdown("**Supporting Compliance PDFs**")
        t1, t2 = st.columns(2)
        with t1:
            if st.session_state.tax_pdf_bytes:
                st.caption(f"Tax PDF bound: `{st.session_state.tax_pdf_name or 'session.pdf'}`")
                st.download_button(
                    "Download tax PDF",
                    data=st.session_state.tax_pdf_bytes,
                    file_name=st.session_state.tax_pdf_name or "tax.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            tax_up = st.file_uploader("Override tax PDF", type=["pdf"], key="tax_uploader")
            if tax_up is not None:
                st.session_state.tax_pdf_bytes = tax_up.getvalue()
                st.session_state.tax_pdf_name = tax_up.name
        with t2:
            if st.session_state.bank_pdf_bytes:
                st.caption(f"Bank PDF bound: `{st.session_state.bank_pdf_name or 'session.pdf'}`")
                st.download_button(
                    "Download bank PDF",
                    data=st.session_state.bank_pdf_bytes,
                    file_name=st.session_state.bank_pdf_name or "bank.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            bank_up = st.file_uploader("Override bank PDF", type=["pdf"], key="bank_uploader")
            if bank_up is not None:
                st.session_state.bank_pdf_bytes = bank_up.getvalue()
                st.session_state.bank_pdf_name = bank_up.name

        execute = st.button(
            "Execute Onboarding Review →",
            type="primary",
            use_container_width=True,
        )

    with right_col:
        st.html('<div class="vg-section-label">Live Execution & Adjudication</div>')
        rail_ph = st.empty()
        verdict_ph = st.empty()
        evidence_ph = st.empty()
        comms_ph = st.empty()

        def render_live(trace: list, state: dict, run_id: str = "") -> None:
            with rail_ph.container():
                st.markdown("**Live LangGraph Execution Rail**")
                if run_id:
                    st.caption(f"Run ID · `{run_id}`")
                if not trace:
                    st.html(
                        '<div class="vg-panel">Awaiting execution. Select a preset and run '
                        "<b>Execute Onboarding Review →</b>.</div>"
                    )
                else:
                    html = ['<div class="vg-rail">']
                    for item in trace:
                        html.append(
                            rail_item_html(
                                item.get("node_id", ""),
                                item.get("stage_name", ""),
                                int(item.get("duration_ms", 0) or 0),
                                item.get("status", "DONE"),
                                item.get("summary", ""),
                            )
                        )
                    html.append("</div>")
                    st.html("".join(html))
                    with st.expander("Raw stage outputs", expanded=False):
                        for item in trace:
                            st.markdown(
                                f"**{item.get('node_id')} · {item.get('stage_name')}** "
                                f"({item.get('duration_ms', 0)} ms)"
                            )
                            try:
                                st.json(json.loads(item.get("output_json") or "{}"))
                            except Exception:
                                st.code(item.get("output_json") or "")

            adj = state.get("adjudication") or {}
            with verdict_ph.container():
                if adj:
                    status = adj.get("status", "PENDING")
                    clauses = "".join(
                        f'<span class="vg-clause">{c}</span>' for c in adj.get("cited_clauses", [])
                    )
                    st.html(
                        f"""
                        <div class="vg-verdict">
                          <div style="display:flex;justify-content:space-between;align-items:center;gap:0.75rem;flex-wrap:wrap;">
                            <div style="display:flex;gap:0.55rem;align-items:center;">
                              {status_pill(status)}
                              <span style="font-weight:700;">{adj.get('decision_headline','')}</span>
                            </div>
                            <div class="vg-mono" style="font-size:0.85rem;color:#475569;">
                              Risk Score · <b>{adj.get('risk_score', 0)} / 100</b>
                            </div>
                          </div>
                          <div style="margin-top:0.55rem;">{clauses}</div>
                          <div style="margin-top:0.65rem;font-size:0.88rem;color:#334155;line-height:1.45;">
                            {adj.get('decision_rationale','')}
                          </div>
                        </div>
                        """
                    )

            inv = state.get("investigation") or {}
            rows = inv.get("evidence_rows") or []
            with evidence_ph.container():
                if rows or adj:
                    st.markdown("**Cross-Source Evidence Matrix**")
                    st.html(evidence_matrix_html(rows))

            with comms_ph.container():
                comms = state.get("comms") or {}
                if comms and (comms.get("vendor_email_body") or comms.get("vendor_email_subject")):
                    st.markdown("**Vendor Outbox & Internal Governance**")
                    to_email = (state.get("submission") or {}).get("contact_email", "")
                    st.html(
                        f"""
                        <div class="vg-email-card">
                          <div class="vg-email-meta">To · {to_email}</div>
                          <div class="vg-email-subject">{comms.get('vendor_email_subject','')}</div>
                          <div class="vg-email-body">{comms.get('vendor_email_body','')}</div>
                        </div>
                        """
                    )
                    st.text_area(
                        "Copyable vendor email",
                        value=comms.get("vendor_email_body", ""),
                        height=140,
                        label_visibility="collapsed",
                    )
                    note = comms.get("internal_security_note") or ""
                    if note.strip():
                        st.html(
                            f"""
                            <div class="vg-security">
                              <div class="vg-security-title">Internal FinOps Security Alert</div>
                              <div style="white-space:pre-wrap;font-size:0.84rem;color:#7F1D1D;">{note}</div>
                              <div style="margin-top:0.45rem;font-size:0.72rem;color:#991B1B;">
                                Fraud / registry details were withheld from the external vendor email (AOP §5.1 anti-tip-off).
                              </div>
                            </div>
                            """
                        )
                elif adj.get("status") == "APPROVED":
                    st.html(
                        '<div class="vg-panel">Auto-approved via Conditional Gate 2 — '
                        "Comms & Critic QA skipped. Onboarding confirmation attached to adjudication.</div>"
                    )

        # Initial paint from session
        render_live(
            st.session_state.live_trace,
            st.session_state.live_state,
            st.session_state.live_run_id,
        )

        if execute:
            api_key = resolve_api_key(st.session_state.api_key_override)
            st.session_state.live_trace = []
            st.session_state.live_state = {}
            try:
                for event in stream_onboarding_run(
                    submission=st.session_state.submission,
                    tax_pdf_bytes=st.session_state.tax_pdf_bytes,
                    bank_pdf_bytes=st.session_state.bank_pdf_bytes,
                    api_key=api_key,
                    model_mode=st.session_state.model_mode,
                    policy_markdown=st.session_state.policy_markdown,
                    persist=True,
                ):
                    state = event.get("state") or {}
                    trace = state.get("stage_trace") or []
                    st.session_state.live_trace = trace
                    st.session_state.live_state = state
                    st.session_state.live_run_id = event.get("run_id", "")
                    render_live(trace, state, event.get("run_id", ""))
            except Exception as exc:  # noqa: BLE001
                st.error(f"Onboarding run failed: {exc}")


with tab_history:
    kpis = run_kpis()
    st.html(kpi_strip(kpis["total"], kpis["approved"], kpis["pending"], kpis["rejected"]))

    f1, f2, f3 = st.columns([1, 1, 2])
    with f1:
        st.session_state.history_status = st.selectbox(
            "Status",
            ["All Statuses", "APPROVED", "PENDING", "REJECTED"],
            index=["All Statuses", "APPROVED", "PENDING", "REJECTED"].index(
                st.session_state.history_status
            ),
        )
    with f2:
        st.session_state.history_country = st.selectbox(
            "Country",
            ["All Countries", "US", "IN", "GB"],
            index=["All Countries", "US", "IN", "GB"].index(st.session_state.history_country),
        )
    with f3:
        st.session_state.history_search = st.text_input(
            "Search legal name / run ID",
            value=st.session_state.history_search,
        )

    runs = list_runs(
        status=st.session_state.history_status,
        country=st.session_state.history_country,
        search=st.session_state.history_search,
    )
    if runs:
        table_rows = [
            {
                "Run ID": r["run_id"],
                "Created": r["created_at"],
                "Legal Name": r["legal_name"],
                "Country": r["country"],
                "Spend USD": r["annual_spend_usd"],
                "Status": r["final_status"],
                "Risk": r["risk_score"],
                "Duration ms": r["duration_ms"],
            }
            for r in runs
        ]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        ids = [r["run_id"] for r in runs]
        default_idx = ids.index(st.session_state.inspector_run_id) if st.session_state.inspector_run_id in ids else 0
        selected = st.selectbox("Run Inspector", ids, index=default_idx)
        st.session_state.inspector_run_id = selected
        detail = get_run(selected)
        if detail:
            st.html(
                f"<div style='margin:0.5rem 0;'>{status_pill(detail['final_status'])} "
                f"<span class='vg-mono'>{detail['run_id']}</span> · {detail['legal_name']}</div>"
            )
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Stage Trace**")
                try:
                    trace = json.loads(detail["stage_trace_json"] or "[]")
                except Exception:
                    trace = []
                for item in trace:
                    st.html(
                        rail_item_html(
                            item.get("node_id", ""),
                            item.get("stage_name", ""),
                            int(item.get("duration_ms", 0) or 0),
                            item.get("status", "DONE"),
                            item.get("summary", ""),
                        )
                    )
                try:
                    adj = json.loads(detail["adjudication_json"] or "{}")
                    st.json(adj)
                except Exception:
                    st.code(detail["adjudication_json"])
            with c2:
                st.markdown("**Evidence Matrix**")
                try:
                    rows = json.loads(detail["evidence_rows_json"] or "[]")
                except Exception:
                    rows = []
                st.html(evidence_matrix_html(rows))
                st.markdown("**Vendor Communication**")
                try:
                    comms = json.loads(detail["comms_json"] or "{}")
                except Exception:
                    comms = {}
                if comms:
                    st.html(
                        f"""
                        <div class="vg-email-card">
                          <div class="vg-email-subject">{comms.get('vendor_email_subject','')}</div>
                          <div class="vg-email-body">{comms.get('vendor_email_body','')}</div>
                        </div>
                        """
                    )
                    if comms.get("internal_security_note"):
                        st.html(
                            f"""
                            <div class="vg-security">
                              <div class="vg-security-title">Internal FinOps Security Alert</div>
                              <div style="white-space:pre-wrap;font-size:0.84rem;">{comms.get('internal_security_note')}</div>
                            </div>
                            """
                        )
                else:
                    st.caption("No vendor communication stored for this run.")
    else:
        st.info("No historical runs match the current filters.")
