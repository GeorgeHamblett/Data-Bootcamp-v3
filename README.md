# RSS/NIHR Funding Application Checklist Assistant

A Streamlit checklist-first adviser tool for Research Support Service (RSS) advisers reviewing NIHR/RSS funding applications. The app compares a runtime application against specific call guidance, optional programme guidance, built-in NIHR domestic guidance, built-in RSS/i4i PDA playbook guidance, and derived reviewer checks.

The app is **not** a generic essay reviewer. It produces structured checklist outputs showing what is present, partially present, missing, not applicable, or needing human check. It never treats guidance text as application evidence.

## Built-in guidance knowledge base

The repository `.txt` files are guidance/reference material, not example applications:

- `nihr_domestic_guidance.txt` is loaded as built-in NIHR domestic guidance.
- `rss_pda_playbook_notes.txt` is loaded as built-in RSS PDA playbook guidance.

`guidance_loader.py` classifies these files by filename and builds the baseline requirement bank. The actual application is supplied only at runtime by pasting text or uploading files.

## Guidance priority

The checklist applies guidance in this order:

1. Specific funding opportunity guidance supplied at runtime.
2. Built-in NIHR domestic guidance from `nihr_domestic_guidance.txt`.
3. Built-in RSS/i4i PDA playbook guidance from `rss_pda_playbook_notes.txt` where PDA/i4i/product-development relevance is detected.
4. Derived RSS reviewer checks.

Specific funding call requirements override built-in general guidance for the same checklist area.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
```

Edit `.env` only with local/private values. **Never commit `.env` or real API keys.** The committed `.env.template` is safe because it contains placeholders only.

## Running Streamlit

```bash
streamlit run app.py
```

In the sidebar:

1. Paste or upload the actual funding application. This is required.
2. Optionally paste or upload specific funding call guidance.
3. Choose whether to run similarity checks. Similarity is off by default.

There is no manual upload input for NIHR domestic guidance or the RSS PDA playbook. Those repository files are loaded automatically as built-in baseline sources. Supported application uploads are `.docx`, `.pdf`, `.txt`, and `.xlsx`. Specific call guidance uploads support `.docx`, `.pdf`, and `.txt`.

## Outputs

The app displays six tabs:

1. Summary — readable narrative summary of key extracted information.
2. Checklist Report — table with checklist area, requirement, source guidance, status, RAG, evidence, and action.
3. RAG Dashboard — exactly seven subsystems: Eligibility, Clinical Validation, Health Economics, Patient and Public Involvement, Research Inclusion, Project Management, and Finance.
4. Similarity Check — readable status/results from Lens, EPO OPS, and NIHR Open Data when enabled.
5. Priority Missing Evidence — grouped adviser actions.
6. Raw JSON — raw structured payload only; raw JSON is kept out of the first five user-facing tabs.

## Live similarity checks

The LLM remains local through Ollama. External similarity checks are separate metadata API calls that run only when explicitly enabled and when privacy gates allow them.

Similarity checks can use:

- Lens Scholarly API
- EPO Open Patent Services (OPS) API
- NIHR Open Data

Normal user flow does **not** simulate results. Live external calls run only when all privacy gates allow them:

- `Run similarity check` is enabled in the UI.
- Mock mode is disabled.
- `STRICT_LOCAL_ONLY_MODE=false`.
- `ALLOW_EXTERNAL_SIMILARITY_QUERIES=true`.
- `SEND_ONLY_SAFE_QUERY_TERMS=true`.
- Required credentials are present for APIs that need them, including EPO OPS.

EPO OPS calls are external metadata API calls, not LLM calls. Only short, cleaned query terms are sent to EPO OPS; full application text, uploaded documents, raw filenames and long extracted paragraphs are never sent to EPO OPS. Real EPO consumer keys and secrets must be stored only in a local `.env` file or local secret store and must never be committed.

Mock similarity mode is hidden under advanced developer/testing options and defaults to off.

## Privacy notes

- The app is designed for local-first review.
- Built-in guidance files are never application evidence.
- Similarity query building excludes filename/document terms and sends only short application-specific concepts, not full application text.
- Blank credentials and placeholders such as `replace_with...`, `optional_replace...`, and `your_real...` are treated as missing.
- Credential status displays only `present` or `missing`; secret values are not shown.
- Do not commit `.env`, Streamlit secrets, or real API keys.

## Running tests

```bash
python -m pytest -q
```

The tests cover prompt architecture, automatic built-in guidance loading, application fact extraction, checklist rules, RAG hard validations, similarity privacy gates, app input constraints, and report rendering.
