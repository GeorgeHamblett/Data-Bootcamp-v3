"""Streamlit app for the RSS/NIHR Funding Application Checklist Assistant."""
from __future__ import annotations

from dataclasses import asdict

try:
    import streamlit as st
except ModuleNotFoundError:  # allows unit tests to import app without Streamlit installed
    class _StreamlitStub:
        def __getattr__(self, name):
            def _missing(*args, **kwargs):
                raise RuntimeError("Streamlit is required to run the app. Install requirements.txt and run streamlit run app.py.")
            return _missing
    st = _StreamlitStub()

from application_facts import extract_application_facts
from checklist_engine import build_checklist
from document_loader import combine_pasted_and_uploaded, load_uploaded_files
from guidance_loader import build_baseline_requirement_bank, load_builtin_guidance
from rag_dashboard import build_rag_dashboard
from report_renderer import (
    checklist_dataframe,
    dashboard_dataframe,
    priority_missing_evidence,
    raw_json_payload,
    render_summary,
    similarity_dataframe,
    validate_report_quality,
)
from settings import load_settings
from similarity.service import run_similarity

APP_TITLE = "RSS/NIHR Funding Application Checklist Assistant"


def _sidebar_settings(settings):
    st.sidebar.header("Similarity settings")
    run_similarity_check = st.sidebar.checkbox("Run similarity check", value=False)
    with st.sidebar.expander("Advanced developer/testing options"):
        mock_similarity_mode = st.checkbox("Mock similarity mode", value=False)
        show_raw_requirements = st.checkbox("Show raw extracted requirements", value=False)
        st.caption("Credential status is masked; full secrets are never displayed.")
        st.json(settings.credential_status())
    return run_similarity_check, mock_similarity_mode, show_raw_requirements


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.write("Checklist-first adviser support grounded in uploaded application evidence and NIHR/RSS guidance.")

    settings = load_settings()
    run_similarity_check, mock_similarity_mode, show_raw_requirements = _sidebar_settings(settings)

    builtins = load_builtin_guidance(settings.repo_root)
    baseline_requirements = build_baseline_requirement_bank(settings.repo_root)

    with st.expander("Built-in guidance loaded by default", expanded=False):
        for doc in builtins:
            st.write(f"- {doc.name}: {doc.source_label}; treated as guidance, not an example application.")

    st.header("1. The Application (required)")
    pasted_application = st.text_area("Paste application text", height=220)
    application_uploads = st.file_uploader("Upload application/supporting documents (.docx, .pdf, .txt, .xlsx)", type=["docx", "pdf", "txt", "xlsx", "xls"], accept_multiple_files=True)

    st.header("2. Optional Specific Application Guidance for Funding Call")
    pasted_call_guidance = st.text_area("Paste specific funding call guidance", height=140)
    call_uploads = st.file_uploader("Upload specific call guidance (.docx, .pdf, .txt)", type=["docx", "pdf", "txt"], accept_multiple_files=True, key="call")

    st.header("3. Optional General NIHR/RSS Guidance")
    pasted_general_guidance = st.text_area("Paste additional general NIHR/RSS guidance", height=100)
    general_uploads = st.file_uploader("Upload additional general guidance (.docx, .pdf, .txt)", type=["docx", "pdf", "txt"], accept_multiple_files=True, key="general")

    if not st.button("Generate checklist report", type="primary"):
        st.info("Paste or upload the actual application, then generate the checklist report. Built-in .txt files are guidance only.")
        return

    application_docs = combine_pasted_and_uploaded(pasted_application, load_uploaded_files(application_uploads), "pasted_application")
    if not application_docs:
        st.error("Application text or upload is required. Built-in guidance files are not application examples.")
        return

    call_docs = combine_pasted_and_uploaded(pasted_call_guidance, load_uploaded_files(call_uploads), "pasted_specific_call_guidance")
    general_docs = combine_pasted_and_uploaded(pasted_general_guidance, load_uploaded_files(general_uploads), "pasted_general_guidance")
    specific_call_text = "\n".join(doc["text"] for doc in call_docs)

    # Additional general guidance augments the baseline without becoming application evidence.
    if general_docs:
        from guidance_parser import parse_guidance_requirements
        for idx, doc in enumerate(general_docs):
            baseline_requirements.extend(parse_guidance_requirements(doc["text"], "programme_guidance", prefix=f"runtime_general_{idx}"))

    facts = extract_application_facts(application_docs)
    checklist_items = build_checklist(facts, baseline_requirements, specific_call_text=specific_call_text)
    dashboard = build_rag_dashboard(checklist_items, facts)
    priorities = priority_missing_evidence(checklist_items)
    summary = render_summary(facts, dashboard, priorities)
    similarity_query, similarity_results = run_similarity(facts, "\n".join(doc["text"][:1500] for doc in application_docs), settings, run_similarity_check, mock_similarity_mode)
    quality_warnings = validate_report_quality(summary, checklist_items, raw_json_tab_index=5, similarity_mock_mode=mock_similarity_mode)

    tabs = st.tabs(["Summary", "Checklist Report", "RAG Dashboard", "Similarity Check", "Priority Missing Evidence", "Raw JSON"])
    with tabs[0]:
        st.markdown(summary)
        if quality_warnings:
            st.warning("Quality checks: " + "; ".join(quality_warnings))
    with tabs[1]:
        st.dataframe(checklist_dataframe(checklist_items), use_container_width=True)
    with tabs[2]:
        st.dataframe(dashboard_dataframe(dashboard), use_container_width=True)
    with tabs[3]:
        st.dataframe(similarity_dataframe(similarity_results), use_container_width=True)
        st.caption("Normal flow does not simulate similarity. Mock results appear only when explicitly enabled in Advanced developer/testing options.")
    with tabs[4]:
        for heading, gaps in priorities.items():
            st.subheader(heading)
            if gaps:
                for gap in gaps[:10]:
                    st.write(f"- {gap}")
            else:
                st.write("No item identified from current checklist output.")
    with tabs[5]:
        if show_raw_requirements:
            st.subheader("Raw extracted/baseline requirements")
            st.json([asdict(r) for r in baseline_requirements])
        st.subheader("Raw JSON report payload")
        st.code(raw_json_payload(facts=facts, checklist=checklist_items, dashboard=dashboard, similarity_query=similarity_query, similarity_results=similarity_results, priorities=priorities), language="json")


if __name__ == "__main__":
    main()
