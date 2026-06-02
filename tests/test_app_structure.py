from pathlib import Path

APP = Path("app.py").read_text()


def test_tabs_render_summaries_before_dataframes():
    checklist_summary = APP.index('st.markdown(render_checklist_report_summary(checklist, facts))')
    checklist_table = APP.index('st.dataframe(checklist_table_rows(checklist)')
    rag_summary = APP.index('st.markdown(render_rag_dashboard_summary(dashboard))')
    rag_table = APP.index('st.dataframe(dashboard_table_rows(dashboard)')
    similarity_summary = APP.index('st.markdown(render_similarity_check_summary(similarity))')
    similarity_table = APP.index('st.dataframe(similarity_table_rows(similarity["results"])')
    assert checklist_summary < checklist_table
    assert rag_summary < rag_table
    assert similarity_summary < similarity_table


def test_priority_and_raw_json_tabs_have_required_renderers():
    assert 'st.markdown(priority)' in APP
    assert 'render_priority_missing_evidence(checklist, dashboard, facts)' in APP
    assert 'st.markdown(render_raw_json_note())' in APP
    assert 'st.json(raw_json_payload' in APP
    assert 'render_main_case_summary' in APP
    assert 'render_executive_review_note' in APP
