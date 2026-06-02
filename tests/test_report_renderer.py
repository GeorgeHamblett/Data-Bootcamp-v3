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
    assert "The setting is NHS community rehabilitation services" in summary
    assert "The setting is Partners include" not in summary
    assert ". with" not in summary
    assert ".." not in summary
    assert "comparator/control Comparator:" not in summary


def test_summary_cleans_user_observed_raw_phrases():
    facts = ApplicationFacts(
        product_or_intervention="StepRight",
        acronym_or_short_name="MQAE",
        target_population="aged 60 and over with recent falls risk and reduced balance confidence will be randomised 2:1 to intervention",
        clinical_or_social_care_need="fall prevention, mobility rehabilitation",
        sites_or_setting="NHS community rehabilitation services",
        study_design="To conduct a randomised mixed-methods real-world pilot trial of the system across NHS community rehabilitation services, assessing feasibility, acceptability, and early clinical outcomes",
        sample_size="54 participants",
        comparator_or_control="Some will use StepRight plus usual care, and some will receive usual care only",
        trl_evidence="TRL 3-4 to TRL 6-7",
        duration_months="24",
        endpoints=["Recruitment", "adherence", "fidelity", "recruitment", "Berg Balance Scale"],
    )
    dashboard = [{"Subsystem": "Eligibility", "RAG": "AMBER", "Priority action": "Add or verify lead applicant."}]
    summary = render_summary(facts, dashboard, "")

    assert "to intervent" not in summary
    assert "The design is To conduct" not in summary
    assert "Recruitment, adherence, fidelity, Berg Balance Scale" in summary
    assert "recruitment, Berg" not in summary
    assert "with sample size 54 participants and comparator/control Some will use" in summary
