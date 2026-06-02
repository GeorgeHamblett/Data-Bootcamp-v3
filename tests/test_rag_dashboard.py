from checklist_engine import build_checklist
from guidance_parser import derived_reviewer_requirements
from rag_dashboard import build_rag_dashboard
from schemas import ApplicationFacts, RAG_SUBSYSTEMS


def test_dashboard_exactly_seven_subsystems():
    facts = ApplicationFacts(project_title="X")
    rows = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    assert [r["Subsystem"] for r in rows] == RAG_SUBSYSTEMS


def test_hard_validation_rules_enforced():
    facts = ApplicationFacts(ppie_plan="PPI contributors involved", health_economics_plan="NHS cost plan", project_management_plan="milestones", finance_or_budget_evidence="")
    rows = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    finance = next(r for r in rows if r["Subsystem"] == "Finance")
    ppie = next(r for r in rows if r["Subsystem"] == "Patient and Public Involvement")
    assert finance["RAG"] == "RED"
    assert ppie["RAG"] != "GREEN"


def test_rag_hard_validation_blocks_green_without_specific_evidence():
    facts = ApplicationFacts(
        health_economics_plan="cost-effectiveness model with EQ-5D but no explicit perspective",
        ppie_plan="Public contributors shaped the proposal but no named lead",
        project_management_plan="timeline only",
        finance_or_budget_evidence="",
    )
    rows = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    assert next(r for r in rows if r["Subsystem"] == "Finance")["RAG"] == "RED"
    assert next(r for r in rows if r["Subsystem"] == "Patient and Public Involvement")["RAG"] != "GREEN"
    assert next(r for r in rows if r["Subsystem"] == "Health Economics")["RAG"] != "GREEN"
    assert next(r for r in rows if r["Subsystem"] == "Project Management")["RAG"] != "GREEN"
