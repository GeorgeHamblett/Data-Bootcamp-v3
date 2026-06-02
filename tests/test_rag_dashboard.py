from application_facts import extract_application_facts
from checklist_engine import build_checklist
from guidance_parser import derived_reviewer_requirements
from rag_dashboard import build_rag_dashboard
from schemas import RAG_SUBSYSTEMS


def test_dashboard_exactly_seven_subsystems():
    facts = extract_application_facts([{"name": "app.txt", "text": "Project title: A"}])
    dashboard = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    assert [s.subsystem for s in dashboard] == RAG_SUBSYSTEMS


def test_hard_validation_rules_enforced():
    facts = extract_application_facts([{"name": "app.txt", "text": "Project title: A"}])
    dashboard = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts, funding_mismatch=True)
    by_name = {s.subsystem: s for s in dashboard}
    assert by_name["Eligibility"].rag == "RED"
    assert by_name["Finance"].rag == "RED"
    assert by_name["Patient and Public Involvement"].rag == "RED"
