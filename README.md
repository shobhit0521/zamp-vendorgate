# VendorGate

Autonomous Know Your Business (KYB) & vendor onboarding governance for procurement FinOps.

Built with **Python**, **Streamlit**, **LangGraph (`StateGraph`)**, **SQLite**, **ReportLab**, and the official **Google GenAI SDK (`google-genai`)**.

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/seedpdfs.py
streamlit run app.py
```

Set `GEMINI_API_KEY` in the environment, `.streamlit/secrets.toml`, or the **Engine Config** popover.

## Streamlit Community Cloud

1. Deploy this repository with entrypoint `app.py`.
2. Add secret `GEMINI_API_KEY` in the Streamlit Cloud app settings.
3. Sample PDFs under `data/pdfs/` and `data/presets.json` are committed so cold starts work without regeneration.

## Architecture

Six-node LangGraph pipeline:

1. **Intake Guardrails** — deterministic validators + SQLite duplicate-account collision
2. **Document Forensics** — Gemini multimodal PDF extraction
3. **Entity Investigator** — cross-source evidence matrix
4. **Policy Adjudicator** — AOP clause citation (`core/policy.md`)
5. **Comms Drafter** — vendor email + internal security note
6. **Compliance Critic** — remediation coverage + anti-tip-off QA (retry ≤ 1)

Conditional gates skip forensics on invalid PDFs, skip Comms/Critic on `APPROVED`, and loop Critic→Drafter once when needed.

## Verification

```bash
pytest tests/verify.py -q
```
