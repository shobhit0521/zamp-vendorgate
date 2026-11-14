# VendorGate Procurement & KYB Agent Operating Procedure (AOP)

This document is the authoritative operating policy for autonomous Know Your Business (KYB) and vendor onboarding adjudication. The Policy Adjudicator MUST cite clause headers verbatim when rendering decisions.

---

## AOP §1.1 — Standard Auto-Approval

Approve a vendor (`APPROVED`) when ALL of the following are satisfied:

1. All deterministic Node 01 guardrail checks pass with no `FAIL_PENDING` or `FAIL_REJECT` findings.
2. Tax certificate and bank verification PDFs are authentic, readable, and signed (or otherwise formally attested).
3. The submitted legal entity name exactly matches — or is a harmless corporate-suffix equivalent of — the name on tax and bank documents (examples: "Inc." vs "Incorporated"; "Pvt Ltd" vs "Private Limited"; "LLC" vs "L.L.C.").
4. The bank country matches the tax registration country (domestic payouts only under this clause).
5. Expected annual spend is under USD 100,000.

When AOP §1.1 applies in full, issue a clean onboarding confirmation and do not require remediation communications.

---

## AOP §2.1 — Document & Data Discrepancy Remediation

Hold the case as `PENDING` and produce a consolidated remediation list when ANY of the following occur without fraud indicators:

1. Required fields or signatures are missing from the submission packet or supporting PDFs.
2. The wrong document type was uploaded into a verification slot (for example, a commercial invoice or sales quotation uploaded instead of bank verification / cancelled cheque).
3. Minor digit transposition or formatting variance between the form and a certificate (for example, GSTIN digit swap) where there is no evidence of intentional fraud or payment diversion.

Remediation requirements must be specific, actionable, and listed exhaustively for the vendor.

---

## AOP §2.2 — Corporate Hierarchy & DBA Alignment

When bank and/or tax documents name a parent holding company, trade name (DBA), or affiliate that is **not** explicitly declared and evidenced on the submission form:

1. Hold the case as `PENDING`.
2. Request an official DBA / trade-name certificate, or a legal entity amendment that aligns the form name with the documented legal entity.
3. Do not auto-approve solely on brand similarity when the documented legal name differs from the submitted legal name beyond harmless suffix equivalence.

---

## AOP §3.1 — Cross-Border Treasury & Tax Nexus

When `bank_country` differs from the `country` of tax registration (for example, a US-registered entity routing funds to Cayman Islands `KY` or UAE `AE`):

1. Hold the case as `PENDING`.
2. Require Form W-8BEN-E (or equivalent cross-border tax documentation) AND Treasury Cross-Border Remittance Authorization before approval.
3. Cite this clause whenever jurisdiction nexus fails, regardless of document authenticity.

---

## AOP §4.1 — High-Value Contract Governance

1. When expected annual spend is greater than or equal to USD 100,000 AND any warning signal is present (cross-border banking, consumer webmail, document variance, or incomplete evidence), escalate to Finance Controller review (`PENDING`).
2. Consumer webmail domains (`gmail.com`, `yahoo.com`, `outlook.com`, `hotmail.com`) on spend greater than or equal to USD 25,000 raise a compliance warning requiring corporate domain verification before final approval.

---

## AOP §5.1 — Zero-Tolerance Fraud & Payment Diversion

Immediately `REJECT` the case when EITHER of the following is detected:

1. Bank account numbers collide with another vendor already present in the approved vendors master registry (duplicate payout destination).
2. Corporate payouts are being routed to an unrelated individual's personal bank account (payment diversion risk).

**Anti-tip-off rule (mandatory):** External vendor notices MUST NEVER disclose internal duplicate-match findings, registry collision details, fraud rule identifiers, or security investigation language. Full forensic detail belongs solely in the Internal Security Escalation note for FinOps / Security review.

---

## Decision Status Vocabulary

| Status | Meaning |
|--------|---------|
| `APPROVED` | Vendor cleared for onboarding under AOP §1.1 |
| `PENDING` | Remediation or escalation required under AOP §2.x, §3.1, or §4.1 |
| `REJECTED` | Hard block under AOP §5.1 |

End of Agent Operating Procedure.
