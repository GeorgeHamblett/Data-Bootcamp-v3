from checklist_engine import build_checklist
from guidance_parser import derived_reviewer_requirements
from rag_dashboard import build_rag_dashboard
from report_renderer import checklist_table_rows, raw_json_payload, render_priority_missing_evidence, render_summary, similarity_table_rows
from schemas import ApplicationFacts


def test_summary_narrative_and_raw_json_separate():
    facts = ApplicationFacts(project_title="Remote COPD monitor", product_or_intervention="Monitor", application_claimed_call="i4i PDA")
    items = build_checklist(facts, derived_reviewer_requirements())
    dash = build_rag_dashboard(items, facts)
    priority = render_priority_missing_evidence(items)
    summary = render_summary(facts, dash, priority)
    assert "Summary of key information extracted" in summary
    assert "## Project at a glance" in summary
    assert "## Proposed evidence generation" in summary
    assert not summary.strip().startswith("{")
    assert raw_json_payload(facts=facts).strip().startswith("{")


def test_checklist_report_not_dump_raw_json_and_similarity_readable():
    rows = checklist_table_rows(build_checklist(ApplicationFacts(), derived_reviewer_requirements()))
    assert "Checklist Area" in rows[0]
    assert not str(rows[0]).startswith("{")  # rendered dataframe rows, not raw JSON tab
    sim_rows = similarity_table_rows([{"source":"NIHR Open Data","status":"not_run","query_terms_used":["A","B"],"matches_found":0,"risk":"NONE"}])
    assert sim_rows[0]["Source"] == "NIHR Open Data"
    assert "Query terms used" in sim_rows[0]


def test_priority_missing_evidence_uses_actions_not_portal_text():
    items = build_checklist(ApplicationFacts(), derived_reviewer_requirements())
    priority = render_priority_missing_evidence(items).lower()
    assert "click invite" not in priority
    assert "fill in" not in priority
    assert "save draft" not in priority
    assert "add or verify" in priority or "upload or verify" in priority

from tests.fixtures import STEPRIGHT_APP, STEPRIGHT_GANTT
from application_facts import extract_application_facts
from document_loader import LoadedDocument


def test_summary_polishes_raw_sentences_and_uses_duration_24():
    facts = extract_application_facts([LoadedDocument("app.txt", STEPRIGHT_APP), LoadedDocument("gantt.txt", STEPRIGHT_GANTT)])
    dash = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    summary = render_summary(facts, dash, "")
    assert "focuses on This project" not in summary
    assert "addressing This project" not in summary
    assert summary.count("This project will test") < 2
    assert "Month 24" in summary


def test_summary_identity_and_setting_are_not_awkward_partner_sentence():
    facts = ApplicationFacts(
        project_title="StepRight",
        application_claimed_call="i4i PDA",
        product_or_intervention="StepRight",
        acronym_or_short_name="MQAE",
        target_population="older adults aged 60 and over at risk of falling",
        clinical_or_social_care_need="falls prevention, balance rehabilitation and confidence",
        sites_or_setting="NHS community rehabilitation services",
        duration_months="24",
    )
    summary = render_summary(facts, [], "")
    assert ". and it is linked" not in summary
    assert ". with acronym" not in summary
    assert "**Setting:** NHS community rehabilitation services" in summary

from report_renderer import (
    clean_table_evidence,
    render_checklist_report_summary,
    render_executive_review_note,
    render_main_case_summary,
    render_rag_dashboard_summary,
    render_raw_json_note,
    render_similarity_check_summary,
    render_table_display_dataframe,
)
from similarity.query_builder import build_similarity_query


def test_section_specific_renderers_return_markdown_summaries():
    facts = ApplicationFacts(project_title="Remote COPD monitor", product_or_intervention="Monitor", application_claimed_call="i4i PDA")
    items = build_checklist(facts, derived_reviewer_requirements())
    dash = build_rag_dashboard(items, facts)
    main = render_main_case_summary(facts, dash, "")
    checklist_summary = render_checklist_report_summary(items, facts)
    rag_summary = render_rag_dashboard_summary(dash)
    similarity = {"query": build_similarity_query(facts), "results": [{"source":"NIHR Open Data", "status":"not_run", "query_terms_used":["Monitor", "COPD"], "matches_found":0, "risk":"NONE", "why_relevant":"disabled"}]}
    similarity_summary = render_similarity_check_summary(similarity)
    priority = render_priority_missing_evidence(items, dash, facts)
    executive = render_executive_review_note(facts, dash, priority)

    assert "Summary of key information extracted" in main
    assert "GREEN" in checklist_summary and "AMBER" in checklist_summary and "RED" in checklist_summary
    assert "Overall risk profile" in rag_summary and "Top 3 adviser actions" in rag_summary
    assert "Cleaned query terms used" in similarity_summary and "Overall novelty/similarity risk" in similarity_summary
    for heading in ["Critical missing items", "Important but fixable gaps", "Items needing human judgement", "Uploads still needed", "Budget/finance checks still needed"]:
        assert heading in priority
    bullets = [line for line in executive.splitlines() if line.startswith("- ")]
    assert 5 <= len(bullets) <= 8
    assert render_raw_json_note().startswith("Developer/debug output only")


def test_table_display_evidence_is_shortened_and_cleaned():
    raw = "rehabilitation, rehabilitation; " + "word " * 80 + "to intervent"
    cleaned = clean_table_evidence(raw, "Clinical Validation", "Evidence")
    assert len(cleaned.split()) <= 35
    assert "rehabilitation, rehabilitation" not in cleaned
    assert "to intervent" not in cleaned
    rows = render_table_display_dataframe(build_checklist(ApplicationFacts(), derived_reviewer_requirements()), "checklist")
    assert "Evidence from application" in rows[0]


def test_output_formatting_avoids_flat_headings_and_huge_paragraphs():
    facts = ApplicationFacts(project_title="X", product_or_intervention="Y", clinical_or_social_care_need="falls prevention, mobility rehabilitation, rehabilitation")
    dash = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    output = render_main_case_summary(facts, dash, "")
    assert "Project at a glance The" not in output
    assert "Proposed evidence generation The" not in output
    assert "rehabilitation, rehabilitation" not in output
    assert "to intervent" not in output
    assert max(len(p.split()) for p in output.split("\n\n") if p.strip()) < 120


def test_similarity_summary_filters_bad_query_terms_and_urls():
    summary = render_similarity_check_summary({
        "query": None,
        "results": [
            {"source":"EPO OPS", "status":"error", "query_terms_used":["Second", "Some", "adherence", "StepRight"], "matches_found":0, "risk":"NONE", "why_relevant":"API error https://example.test/query?x=long"}
        ],
    })
    assert "Second" not in summary and "Some" not in summary and "adherence" not in summary
    assert "https://example.test" not in summary
    assert "StepRight" in summary
