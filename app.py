"""Streamlit entrypoint for the RSS/NIHR Funding Application Checklist Assistant."""
from __future__ import annotations

from application_facts import extract_application_facts
from checklist_engine import build_checklist
from document_loader import combine_pasted_and_uploaded
from guidance_loader import build_baseline_requirement_bank, detects_pda_relevance
from guidance_parser import parse_guidance_text
from rag_dashboard import build_rag_dashboard
from report_renderer import (
    checklist_table_rows,
    dashboard_table_rows,
    raw_json_payload,
    render_checklist_report_summary,
    render_executive_review_note,
    render_main_case_summary,
    render_priority_missing_evidence,
    render_rag_dashboard_summary,
    render_raw_json_note,
    render_similarity_check_summary,
    render_table_display_dataframe,
    similarity_query_terms_display,
    similarity_table_rows,
)
from settings import Settings
from similarity.service import run_similarity_service
from similarity.epo_ops import check_epo_credentials

APP_TITLE = "RSS/NIHR Funding Application Checklist Assistant"
NO_SPECIFIC_CALL_GUIDANCE_MESSAGE = "No specific funding call guidance provided; review uses built-in NIHR domestic guidance and RSS PDA playbook guidance."


def _runtime_guidance_from_inputs(pasted: str, uploads) -> str:
    docs = combine_pasted_and_uploaded(pasted, uploads)
    return "\n\n".join(doc.text for doc in docs)


def main() -> None:
    import streamlit as st
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("Checklist-first adviser tool grounded in runtime application evidence and built-in NIHR/RSS guidance.")

    settings = Settings.from_env()
    with st.sidebar:
        st.header("The Application")
        st.caption("Required. This is the actual applicant submission, not built-in guidance.")
        app_text = st.text_area("Paste application text", height=220, help="Required unless application files are uploaded.")
        app_uploads = st.file_uploader("Upload application/supporting documents", type=["docx", "pdf", "txt", "xlsx"], accept_multiple_files=True)
        st.header("Optional Specific Funding Call Guidance")
        st.caption("Optional but recommended when exact call page/opportunity guidance is available.")
        call_text = st.text_area("Paste specific funding call guidance", height=130)
        call_uploads = st.file_uploader("Upload specific funding call guidance", type=["docx", "pdf", "txt"], accept_multiple_files=True)
        st.subheader("Similarity settings")
        run_similarity = st.checkbox("Run similarity check", value=False)
        with st.expander("Advanced developer/testing options"):
            mock_similarity = st.checkbox("Mock similarity mode", value=False)
            show_raw_requirements = st.checkbox("Show raw extracted requirements", value=False)
            st.write("Credential status", settings.credential_status())
            if st.button("Test EPO OPS credentials"):
                epo_status = check_epo_credentials(settings)
                if epo_status.get("status") == "success":
                    st.success(epo_status.get("message", "EPO OPS authentication succeeded."))
                else:
                    st.warning(epo_status.get("why_relevant") or epo_status.get("top_match") or "EPO OPS authentication failed.")
        run_button = st.button("Generate checklist report", type="primary")

    if not run_button:
        st.info("Paste or upload the actual application, then generate the checklist report. Built-in .txt files are loaded as guidance, not example applications.")
        return

    application_docs = combine_pasted_and_uploaded(app_text, app_uploads)
    if not application_docs:
        st.error("The Application is required. Paste text or upload .docx, .pdf, .txt or .xlsx files.")
        return

    with st.spinner("Extracting application facts and building checklist..."):
        facts = extract_application_facts(application_docs)
        specific_text = _runtime_guidance_from_inputs(call_text, call_uploads)
        include_pda = detects_pda_relevance(specific_text, facts.application_claimed_call, facts.product_or_intervention, facts.technology_type, facts.trl_evidence)
        baseline = build_baseline_requirement_bank(".", include_pda_playbook=include_pda)
        specific_reqs = parse_guidance_text(specific_text, "specific_call", prefix="CALL") if specific_text.strip() else []
        for req in specific_reqs:
            req.overrides_general_guidance = True
        checklist = build_checklist(facts, baseline, specific_reqs)
        dashboard = build_rag_dashboard(checklist, facts)
        priority = render_priority_missing_evidence(checklist, dashboard, facts)
        similarity = run_similarity_service(
            facts,
            settings,
            run_similarity_check=run_similarity,
            mock_mode=mock_similarity,
            snippets=[doc.text[:800] for doc in application_docs],
        )

    tab_summary, tab_checklist, tab_rag, tab_similarity, tab_priority, tab_raw = st.tabs([
        "Summary",
        "Checklist Report",
        "RAG Dashboard",
        "Similarity Check",
        "Priority Missing Evidence",
        "Raw JSON",
    ])

    with tab_summary:
        if not specific_reqs:
            st.info(NO_SPECIFIC_CALL_GUIDANCE_MESSAGE)
        st.markdown(render_main_case_summary(facts, dashboard, priority))
        st.markdown(render_executive_review_note(facts, dashboard, priority))
    with tab_checklist:
        st.markdown(render_checklist_report_summary(checklist, facts))
        st.markdown("## Detailed checklist table")
        st.dataframe(checklist_table_rows(checklist), use_container_width=True)
        if show_raw_requirements:
            st.subheader("Developer: raw extracted requirements")
            st.json([req.__dict__ for req in baseline + specific_reqs])
    with tab_rag:
        st.markdown(render_rag_dashboard_summary(dashboard))
        st.markdown("## Detailed RAG dashboard")
        st.dataframe(dashboard_table_rows(dashboard), use_container_width=True)
        warnings = [w for row in dashboard for w in row.get("hard_validation_warnings", [])]
        if warnings:
            st.warning("; ".join(warnings))
    with tab_similarity:
        st.markdown(render_similarity_check_summary(similarity))
        st.markdown("## Detailed similarity results")
        st.write("Similarity uses live APIs only when explicitly enabled and privacy gates allow it. Normal flow does not simulate results.")
        st.dataframe(similarity_table_rows(similarity["results"]), use_container_width=True)
        st.caption("Query terms: " + similarity_query_terms_display(similarity["query"].primary_terms + similarity["query"].secondary_terms))
    with tab_priority:
        st.markdown(priority)
    with tab_raw:
        st.markdown(render_raw_json_note())
        st.json(raw_json_payload(facts=facts, checklist=checklist, dashboard=dashboard, similarity=similarity))


if __name__ == "__main__":
    main()
