"""Enterprise FinOps visual system for VendorGate Streamlit UI."""

from __future__ import annotations

STATUS_STYLES = {
    "APPROVED": {"bg": "#ECFDF5", "fg": "#065F46", "dot": "#10B981"},
    "PENDING": {"bg": "#FFFBEB", "fg": "#92400E", "dot": "#F59E0B"},
    "REJECTED": {"bg": "#FEF2F2", "fg": "#991B1B", "dot": "#EF4444"},
    "DONE": {"bg": "#ECFDF5", "fg": "#065F46", "dot": "#10B981"},
    "SKIPPED": {"bg": "#F1F5F9", "fg": "#475569", "dot": "#94A3B8"},
    "FLAGGED": {"bg": "#FFFBEB", "fg": "#92400E", "dot": "#F59E0B"},
    "RETRY": {"bg": "#EEF2FF", "fg": "#3730A3", "dot": "#6366F1"},
    "MATCH": {"bg": "#ECFDF5", "fg": "#065F46", "dot": "#10B981"},
    "VARIANCE": {"bg": "#FFFBEB", "fg": "#92400E", "dot": "#F59E0B"},
    "CONFLICT": {"bg": "#FEF2F2", "fg": "#991B1B", "dot": "#EF4444"},
    "MISSING": {"bg": "#F1F5F9", "fg": "#475569", "dot": "#94A3B8"},
}


def inject_global_css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
  font-family: 'Inter', sans-serif;
  letter-spacing: -0.02em;
}
.stApp {
  background: #FFFFFF;
}
[data-testid="stHeader"] { display: none; }
footer { visibility: hidden; }
.block-container {
  padding-top: 1.2rem !important;
  padding-bottom: 2rem !important;
  max-width: 1280px;
}
.mono, .vg-mono, code, pre {
  font-family: 'JetBrains Mono', monospace !important;
  letter-spacing: 0 !important;
}
div[data-testid="stMetricValue"] {
  font-family: 'JetBrains Mono', monospace;
}

/* Tighten buttons */
.stButton > button {
  border-radius: 7px;
  border: 1px solid #E2E8F0;
  font-weight: 560;
  letter-spacing: -0.02em;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: #2340F5 !important;
  border-color: #2340F5 !important;
  color: #fff !important;
}

.vg-masthead {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding: 0.2rem 0 1rem 0;
  border-bottom: 1px solid #E2E8F0;
  margin-bottom: 1rem;
}
.vg-wordmark {
  font-family: 'Inter', sans-serif;
  font-weight: 700;
  font-size: 1.35rem;
  letter-spacing: -0.04em;
  color: #0F172A;
  line-height: 1.1;
}
.vg-subtitle {
  margin-top: 0.2rem;
  font-size: 0.72rem;
  font-weight: 560;
  color: #64748B;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.vg-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  border: 1px solid transparent;
  white-space: nowrap;
}
.vg-pill .dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  display: inline-block;
}
.vg-panel {
  background: #F7F8FA;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 0.9rem 1rem;
}
.vg-panel-title {
  font-size: 0.78rem;
  font-weight: 650;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.55rem;
}
.vg-rail {
  border-left: 2px solid #E2E8F0;
  margin-left: 0.55rem;
  padding-left: 1rem;
}
.vg-rail-item {
  position: relative;
  margin-bottom: 0.85rem;
  padding: 0.65rem 0.75rem;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
}
.vg-rail-item::before {
  content: '';
  position: absolute;
  left: -1.22rem;
  top: 1rem;
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  background: #2340F5;
  border: 2px solid #FFFFFF;
  box-shadow: 0 0 0 1px #2340F5;
}
.vg-rail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}
.vg-rail-idx {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #2340F5;
  font-weight: 600;
}
.vg-rail-ms {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  color: #64748B;
  background: #F7F8FA;
  border: 1px solid #E2E8F0;
  border-radius: 5px;
  padding: 0.1rem 0.35rem;
}
.vg-verdict {
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 1rem 1.1rem;
  background: #FFFFFF;
  margin: 0.75rem 0;
}
.vg-kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.65rem;
  margin-bottom: 0.9rem;
}
.vg-kpi {
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  background: #FFFFFF;
  padding: 0.75rem 0.85rem;
}
.vg-kpi .label {
  font-size: 0.68rem;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 600;
}
.vg-kpi .value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.35rem;
  color: #0F172A;
  margin-top: 0.2rem;
  font-weight: 600;
}
.vg-matrix {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
.vg-matrix th, .vg-matrix td {
  border: 1px solid #E2E8F0;
  padding: 0.45rem 0.55rem;
  text-align: left;
  vertical-align: top;
}
.vg-matrix th {
  background: #F7F8FA;
  font-weight: 650;
  color: #475569;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.vg-matrix .mono-cell {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
}
.vg-email-card {
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  background: #FFFFFF;
  padding: 0.9rem 1rem;
}
.vg-email-meta {
  font-size: 0.78rem;
  color: #64748B;
  margin-bottom: 0.35rem;
}
.vg-email-subject {
  font-weight: 650;
  color: #0F172A;
  margin-bottom: 0.65rem;
}
.vg-email-body {
  white-space: pre-wrap;
  font-size: 0.84rem;
  line-height: 1.45;
  color: #0F172A;
}
.vg-security {
  border: 1px solid #FECACA;
  background: #FEF2F2;
  border-radius: 8px;
  padding: 0.9rem 1rem;
  margin-top: 0.75rem;
}
.vg-security-title {
  color: #991B1B;
  font-weight: 700;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.45rem;
}
.vg-clause {
  display: inline-block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  background: #EEF2FF;
  color: #3730A3;
  border: 1px solid #C7D2FE;
  border-radius: 5px;
  padding: 0.15rem 0.4rem;
  margin: 0.15rem 0.25rem 0.15rem 0;
}
.vg-section-label {
  font-size: 0.72rem;
  font-weight: 650;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0.4rem 0 0.55rem 0;
}
@media (max-width: 900px) {
  .vg-kpi-strip { grid-template-columns: repeat(2, 1fr); }
  .vg-masthead { flex-direction: column; }
}
</style>
"""


def status_pill(status: str, label: str | None = None) -> str:
    key = (status or "").upper()
    style = STATUS_STYLES.get(key, STATUS_STYLES["MISSING"])
    text = label or key
    return (
        f'<span class="vg-pill" style="background:{style["bg"]};color:{style["fg"]};'
        f'border-color:{style["bg"]};">'
        f'<span class="dot" style="background:{style["dot"]};"></span>{text}</span>'
    )


def kpi_strip(total: int, approved: int, pending: int, rejected: int) -> str:
    cells = [
        ("Total Reviews", total),
        ("Auto-Approved", approved),
        ("Pending Remediation", pending),
        ("Fraud Blocked", rejected),
    ]
    inner = "".join(
        f'<div class="vg-kpi"><div class="label">{lab}</div><div class="value">{val}</div></div>'
        for lab, val in cells
    )
    return f'<div class="vg-kpi-strip">{inner}</div>'


def evidence_matrix_html(rows: list[dict]) -> str:
    if not rows:
        return '<div class="vg-panel"><div class="vg-panel-title">Evidence Matrix</div><div>No evidence rows captured for this run.</div></div>'
    body = []
    for r in rows:
        st = status_pill(r.get("alignment_status", "MISSING"))
        body.append(
            "<tr>"
            f"<td>{r.get('field_name','')}</td>"
            f"<td class='mono-cell'>{r.get('submitted_value','')}</td>"
            f"<td class='mono-cell'>{r.get('tax_doc_value','')}</td>"
            f"<td class='mono-cell'>{r.get('bank_doc_value','')}</td>"
            f"<td>{st}</td>"
            "</tr>"
        )
    return (
        '<table class="vg-matrix"><thead><tr>'
        "<th>Field</th><th>Submitted Form</th><th>Tax Certificate PDF</th>"
        "<th>Bank Verification PDF</th><th>Status</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def rail_item_html(
    node_id: str,
    stage_name: str,
    duration_ms: int,
    status: str,
    summary: str,
) -> str:
    return (
        f'<div class="vg-rail-item">'
        f'<div class="vg-rail-head">'
        f'<div><span class="vg-rail-idx">{node_id}</span> · <b>{stage_name}</b></div>'
        f'<div style="display:flex;gap:0.4rem;align-items:center;">'
        f'{status_pill(status)}'
        f'<span class="vg-rail-ms">{duration_ms} ms</span>'
        f"</div></div>"
        f'<div style="font-size:0.8rem;color:#475569;">{summary}</div>'
        f"</div>"
    )
