"""SQLite audit store and approved-vendor reference registry for VendorGate."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "vendorgate.db"

SEED_VENDORS = [
    {
        "legal_name": "Zenith Logistics Inc.",
        "country": "US",
        "tax_id": "34-7719201",
        "account_number": "8899001122",
        "routing_or_ifsc": "021000021",
        "bank_country": "US",
        "status": "APPROVED",
    },
    {
        "legal_name": "Harborline Components Ltd",
        "country": "GB",
        "tax_id": "GB123456789",
        "account_number": "GB29NWBK60161331926819",
        "routing_or_ifsc": "60-16-13",
        "bank_country": "GB",
        "status": "APPROVED",
    },
    {
        "legal_name": "Nimbus Packing Private Limited",
        "country": "IN",
        "tax_id": "29AABCN4829K1Z5",
        "account_number": "50100022918374",
        "routing_or_ifsc": "HDFC0000456",
        "bank_country": "IN",
        "status": "APPROVED",
    },
]

SEED_RUNS = [
    {
        "run_id": "VG-2026-091",
        "created_at": "2026-10-28T14:22:11Z",
        "legal_name": "Northstar Cloud Systems Inc.",
        "country": "US",
        "annual_spend_usd": 42000,
        "final_status": "APPROVED",
        "risk_score": 12,
        "cited_clauses_json": json.dumps(["AOP §1.1 — Standard Auto-Approval"]),
        "submission_json": json.dumps(
            {
                "legal_name": "Northstar Cloud Systems Inc.",
                "country": "US",
                "tax_id": "47-3920184",
                "expected_annual_spend_usd": 42000,
            }
        ),
        "stage_trace_json": json.dumps(
            [
                {
                    "node_id": "01",
                    "stage_name": "Intake Guardrails",
                    "status": "DONE",
                    "duration_ms": 18,
                    "summary": "All deterministic checks passed",
                },
                {
                    "node_id": "04",
                    "stage_name": "Policy Adjudicator",
                    "status": "DONE",
                    "duration_ms": 840,
                    "summary": "APPROVED under AOP §1.1",
                },
            ]
        ),
        "evidence_rows_json": json.dumps([]),
        "adjudication_json": json.dumps(
            {
                "status": "APPROVED",
                "risk_score": 12,
                "decision_headline": "Vendor cleared for onboarding",
                "cited_clauses": ["AOP §1.1 — Standard Auto-Approval"],
            }
        ),
        "comms_json": json.dumps({}),
        "duration_ms": 2100,
    },
    {
        "run_id": "VG-2026-097",
        "created_at": "2026-11-03T09:41:05Z",
        "legal_name": "CloudPulse Technologies",
        "country": "IN",
        "annual_spend_usd": 38000,
        "final_status": "PENDING",
        "risk_score": 48,
        "cited_clauses_json": json.dumps(["AOP §2.2 — Corporate Hierarchy & DBA Alignment"]),
        "submission_json": json.dumps(
            {
                "legal_name": "CloudPulse Technologies",
                "country": "IN",
                "tax_id": "29AABCC4829K1Z5",
                "expected_annual_spend_usd": 38000,
            }
        ),
        "stage_trace_json": json.dumps(
            [
                {
                    "node_id": "03",
                    "stage_name": "Entity Investigator",
                    "status": "FLAGGED",
                    "duration_ms": 1120,
                    "summary": "Parent/DBA variance detected",
                }
            ]
        ),
        "evidence_rows_json": json.dumps([]),
        "adjudication_json": json.dumps(
            {
                "status": "PENDING",
                "risk_score": 48,
                "decision_headline": "DBA alignment required",
                "cited_clauses": ["AOP §2.2 — Corporate Hierarchy & DBA Alignment"],
            }
        ),
        "comms_json": json.dumps(
            {
                "vendor_email_subject": "Action Required: DBA Certificate for CloudPulse Technologies",
                "vendor_email_body": "Please provide an official DBA certificate.",
            }
        ),
        "duration_ms": 4200,
    },
    {
        "run_id": "VG-2026-102",
        "created_at": "2026-11-10T16:08:44Z",
        "legal_name": "Apex Digital Supply LLC",
        "country": "US",
        "annual_spend_usd": 85000,
        "final_status": "REJECTED",
        "risk_score": 97,
        "cited_clauses_json": json.dumps(["AOP §5.1 — Zero-Tolerance Fraud & Payment Diversion"]),
        "submission_json": json.dumps(
            {
                "legal_name": "Apex Digital Supply LLC",
                "country": "US",
                "tax_id": "61-4092817",
                "account_number": "8899001122",
                "expected_annual_spend_usd": 85000,
            }
        ),
        "stage_trace_json": json.dumps(
            [
                {
                    "node_id": "01",
                    "stage_name": "Intake Guardrails",
                    "status": "FLAGGED",
                    "duration_ms": 22,
                    "summary": "Duplicate bank account collision with Zenith Logistics Inc.",
                }
            ]
        ),
        "evidence_rows_json": json.dumps([]),
        "adjudication_json": json.dumps(
            {
                "status": "REJECTED",
                "risk_score": 97,
                "decision_headline": "Fraud block — payment diversion risk",
                "cited_clauses": ["AOP §5.1 — Zero-Tolerance Fraud & Payment Diversion"],
            }
        ),
        "comms_json": json.dumps(
            {
                "vendor_email_subject": "Vendor Onboarding Decision — Apex Digital Supply LLC",
                "vendor_email_body": "We are unable to proceed with onboarding at this time.",
                "internal_security_note": "INTERNAL: Account 8899001122 collides with Zenith Logistics Inc.",
            }
        ),
        "duration_ms": 3800,
    },
]


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_and_seed_db(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else DB_PATH
    conn = get_connection(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS approved_vendors_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                legal_name TEXT NOT NULL,
                country TEXT NOT NULL,
                tax_id TEXT NOT NULL,
                account_number TEXT NOT NULL,
                routing_or_ifsc TEXT NOT NULL,
                bank_country TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'APPROVED',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS onboarding_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                legal_name TEXT NOT NULL,
                country TEXT NOT NULL,
                annual_spend_usd INTEGER NOT NULL,
                final_status TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                cited_clauses_json TEXT NOT NULL,
                submission_json TEXT NOT NULL,
                stage_trace_json TEXT NOT NULL,
                evidence_rows_json TEXT NOT NULL,
                adjudication_json TEXT NOT NULL,
                comms_json TEXT NOT NULL,
                duration_ms INTEGER NOT NULL
            )
            """
        )
        cur.execute("SELECT COUNT(*) AS c FROM approved_vendors_registry")
        if cur.fetchone()["c"] == 0:
            for v in SEED_VENDORS:
                cur.execute(
                    """
                    INSERT INTO approved_vendors_registry
                    (legal_name, country, tax_id, account_number, routing_or_ifsc, bank_country, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        v["legal_name"],
                        v["country"],
                        v["tax_id"],
                        v["account_number"],
                        v["routing_or_ifsc"],
                        v["bank_country"],
                        v["status"],
                    ),
                )
        cur.execute("SELECT COUNT(*) AS c FROM onboarding_runs")
        if cur.fetchone()["c"] == 0:
            for r in SEED_RUNS:
                cur.execute(
                    """
                    INSERT INTO onboarding_runs (
                        run_id, created_at, legal_name, country, annual_spend_usd,
                        final_status, risk_score, cited_clauses_json, submission_json,
                        stage_trace_json, evidence_rows_json, adjudication_json,
                        comms_json, duration_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r["run_id"],
                        r["created_at"],
                        r["legal_name"],
                        r["country"],
                        r["annual_spend_usd"],
                        r["final_status"],
                        r["risk_score"],
                        r["cited_clauses_json"],
                        r["submission_json"],
                        r["stage_trace_json"],
                        r["evidence_rows_json"],
                        r["adjudication_json"],
                        r["comms_json"],
                        r["duration_ms"],
                    ),
                )
        conn.commit()
    finally:
        conn.close()
    return path


def find_account_collisions(
    account_number: str,
    legal_name: str,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    if not account_number:
        return []
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT legal_name, country, tax_id, account_number, routing_or_ifsc
            FROM approved_vendors_registry
            WHERE account_number = ? AND LOWER(legal_name) != LOWER(?)
            """,
            (account_number.strip(), legal_name.strip()),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def next_run_id(db_path: str | Path | None = None) -> str:
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT run_id FROM onboarding_runs
            WHERE run_id LIKE 'VG-2026-%'
            ORDER BY id DESC LIMIT 1
            """
        )
        row = cur.fetchone()
        if row:
            try:
                seq = int(str(row["run_id"]).split("-")[-1]) + 1
            except ValueError:
                seq = 104
        else:
            seq = 104
        return f"VG-2026-{seq:03d}"
    finally:
        conn.close()


def persist_run(
    *,
    run_id: str,
    submission: dict[str, Any],
    adjudication: dict[str, Any],
    stage_trace: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    comms: dict[str, Any],
    duration_ms: int,
    db_path: str | Path | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO onboarding_runs (
                run_id, created_at, legal_name, country, annual_spend_usd,
                final_status, risk_score, cited_clauses_json, submission_json,
                stage_trace_json, evidence_rows_json, adjudication_json,
                comms_json, duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                submission.get("legal_name", ""),
                submission.get("country", ""),
                int(submission.get("expected_annual_spend_usd", 0) or 0),
                adjudication.get("status", "PENDING"),
                int(adjudication.get("risk_score", 0) or 0),
                json.dumps(adjudication.get("cited_clauses", [])),
                json.dumps(submission),
                json.dumps(stage_trace),
                json.dumps(evidence_rows),
                json.dumps(adjudication),
                json.dumps(comms or {}),
                int(duration_ms),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_runs(
    *,
    status: str = "",
    country: str = "",
    search: str = "",
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        query = "SELECT * FROM onboarding_runs WHERE 1=1"
        params: list[Any] = []
        if status and status != "All Statuses":
            query += " AND final_status = ?"
            params.append(status)
        if country and country != "All Countries":
            query += " AND country = ?"
            params.append(country)
        if search:
            query += " AND (legal_name LIKE ? OR run_id LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY id DESC"
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_run(run_id: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM onboarding_runs WHERE run_id = ?", (run_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def run_kpis(db_path: str | Path | None = None) -> dict[str, int]:
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM onboarding_runs")
        total = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM onboarding_runs WHERE final_status = 'APPROVED'")
        approved = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM onboarding_runs WHERE final_status = 'PENDING'")
        pending = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM onboarding_runs WHERE final_status = 'REJECTED'")
        rejected = cur.fetchone()["c"]
        return {
            "total": total,
            "approved": approved,
            "pending": pending,
            "rejected": rejected,
        }
    finally:
        conn.close()


# Ensure DB exists for local imports / Streamlit cold start.
if not os.environ.get("VENDORGATE_SKIP_AUTO_SEED"):
    try:
        init_and_seed_db()
    except Exception:
        pass
