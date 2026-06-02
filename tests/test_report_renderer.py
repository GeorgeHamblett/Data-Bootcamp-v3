from application_facts import extract_application_facts
from checklist_engine import build_checklist
from guidance_parser import derived_reviewer_requirements
from rag_dashboard import build_rag_dashboard
from report_renderer import checklist_dataframe, priority_missing_evidence, raw_json_payload, render_summary, similarity_dataframe, validate_report_quality
from schemas import SimilarityResult


def _report_parts():
    facts = extract_application_facts([{"name": "app.txt", "text": "Project title: Diabetes Sensor\nLead applicant: Dr A\nIntervention: wearable glucose sensor\nPopulation: older adults\nClinical need: diabetes monitoring\nStudy design: feasibility study\nBudget: staff and device costs\n"}])
    items = build_checklist(facts, derived_reviewer_requirements())
    dashboard = build_rag_dashboard(items, facts)
    return facts, items, dashboard


def test_summary_around_400_words_and_narrative():
    facts, items, dashboard = _report_parts()
    summary = render_summary(facts, dashboard, priority_missing_evidence(items))
    assert "# Summary of key information extracted" in summary
    assert "## 1. Project at a glance" in summary
    assert not summary.lstrip().startswith("{")
    wc = len(summary.split())
    assert 220 <= wc <= 520


def test_checklist_report_not_raw_json_and_raw_json_separate():
    _, items, _ = _report_parts()
    df = checklist_dataframe(items)
    assert "Checklist Area" in df.columns
    assert not str(df.iloc[0, 0]).startswith("{")
    payload = raw_json_payload(checklist=items)
    assert payload.strip().startswith("{")


def test_similarity_tab_readable_results():
    df = similarity_dataframe([SimilarityResult("NIHR Open Data", "not_run", ["sensor", "diabetes"], 0, "Not run", 0, "NONE", "Disabled", "")])
    assert list(df.columns) == ["Source", "Status", "Query terms used", "Matches found", "Top match", "Score", "Risk", "Why relevant", "Link/ID"]


def test_quality_validation_no_green_without_evidence():
    facts, items, dashboard = _report_parts()
    warnings = validate_report_quality(render_summary(facts, dashboard, {}), items)
    assert not any("GREEN checklist item lacks" in w for w in warnings)
