# RSS/NIHR Funding Application Checklist Assistant

A Streamlit checklist-first adviser tool for Research Support Service (RSS) teams reviewing NIHR funding applications. The app helps advisers compare an uploaded or pasted application against call-specific guidance, programme guidance, built-in NIHR domestic guidance, built-in RSS/i4i PDA playbook guidance, and derived RSS reviewer checks.

The tool is not a generic essay reviewer. It produces a structured report showing what is present, partially present, missing, not applicable, or needing human check, with evidence from the uploaded application.

## Built-in guidance files

The repository `.txt` files are a built-in guidance knowledge base, not example applications:

- `nihr_domestic_guidance.txt` is classified as **NIHR domestic guidance**.
- `rss_pda_playbook_notes.txt` is classified as **RSS PDA playbook** guidance.

At runtime, the actual application must be pasted or uploaded by the user. The built-in guidance files are loaded automatically as baseline requirements and are never treated as application evidence.

## Guidance priority

Guidance is applied in this order:

1. Specific funding opportunity guidance supplied at runtime.
2. Programme-specific guidance supplied or detected at runtime.
3. Built-in NIHR domestic guidance from the repository `.txt` files.
4. Built-in RSS/i4i PDA playbook guidance from the repository `.txt` files.
5. Derived RSS reviewer checks.

Specific funding call guidance overrides built-in general guidance for the same checklist area.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
```

Edit `.env` if you want live local LLM or external similarity services. Never commit `.env` or real API keys.

## Run Streamlit

```bash
streamlit run app.py
```

In the app:

1. Paste or upload the actual application and supporting documents (`.docx`, `.pdf`, `.txt`, `.xlsx`).
2. Optionally paste or upload specific funding call guidance (`.docx`, `.pdf`, `.txt`).
3. Optionally paste or upload additional general NIHR/RSS guidance. Built-in guidance is used by default.
4. Generate the checklist report.

## Outputs

The app provides six tabs:

1. Summary — a readable narrative summary of key extracted information.
2. Checklist Report — structured checklist table with application evidence and gaps.
3. RAG Dashboard — exactly seven subsystems: Eligibility, Clinical Validation, Health Economics, Patient and Public Involvement, Research Inclusion, Project Management, and Finance.
4. Similarity Check — Lens Scholarly, EPO OPS, and NIHR Open Data status/results when enabled.
5. Priority Missing Evidence — grouped adviser actions.
6. Raw JSON — raw payload kept separate for developer inspection.

## Similarity checks and privacy

Similarity is disabled by default. Live API calls only run when all of the following are true:

- Run similarity check is switched on in the UI.
- Mock similarity mode is off.
- `LOCAL_ONLY_MODE=false`.
- `ALLOW_EXTERNAL_SIMILARITY_QUERIES=true`.
- Required credentials are present for Lens and EPO OPS. NIHR Open Data may run without a key.

The query builder uses extracted application concepts only and excludes filename/document terms such as `upload`, `document`, `docx`, `pdf`, `application`, `template`, `playbook`, and `guidance`. It requires at least two meaningful concepts before live searching and does not send the full application text externally.

Mock similarity mode is hidden under advanced developer/testing options and is off by default. Normal user flow does not simulate similarity results.

## Environment variables

See `.env.template` for all variables. Blank values and placeholders beginning with `replace_with`, `optional_replace`, or `your_real` are treated as missing credentials. If credential status is displayed, secrets are masked.

## Tests

```bash
python -m pytest -q
```

The tests cover prompt architecture, guidance loading/classification, application fact extraction, checklist behaviour, RAG hard validation, similarity privacy controls, and report rendering.

## Privacy warning

Do not commit `.env`, Streamlit secrets, uploaded applications, or real API keys. Keep `LOCAL_ONLY_MODE=true` unless the adviser/user has explicitly approved external similarity queries and understands what extracted terms will be sent.
