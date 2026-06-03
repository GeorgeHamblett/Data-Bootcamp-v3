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


def test_no_amber_row_with_no_major_gap_identified():
    facts = ApplicationFacts(research_inclusion_plan="Underserved groups and accessibility are considered")
    rows = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    assert not any(r["RAG"] == "AMBER" and r["Main gap"] == "No major gap identified from relevant evidence." for r in rows)


def test_ppie_named_coordination_amber_not_red_without_payment():
    facts = ApplicationFacts(ppie_plan="Public contributors advise on materials", ppie_leadership_evidence="Ms X, a co-applicant, will provide day-to-day PPI coordination")
    rows = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    ppie = next(r for r in rows if r["Subsystem"] == "Patient and Public Involvement")
    assert ppie["RAG"] == "AMBER"


def test_project_management_and_finance_dashboard_rules():
    facts = ApplicationFacts(duration_months="24", project_management_plan="24-month plan; work packages/Gantt rows present; milestones present", work_packages=["WP1: setup"], milestones=["Month 24: final report"], uploads_detected=["A Gantt chart is included"], finance_or_budget_evidence="")
    rows = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    pm = next(r for r in rows if r["Subsystem"] == "Project Management")
    finance = next(r for r in rows if r["Subsystem"] == "Finance")
    assert pm["RAG"] in {"AMBER", "GREEN"}
    assert finance["RAG"] == "RED"


def test_ppie_leadership_updates_dashboard_gap_and_action():
    facts = ApplicationFacts(
        ppie_plan="Public contributors advise on materials.",
        ppie_leadership_evidence="Ms Leila Karim, a co-applicant, will provide day-to-day PPI coordination.",
    )
    rows = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    ppie = next(r for r in rows if r["Subsystem"] == "Patient and Public Involvement")
    assert "named ppi lead" not in ppie["Priority action"].lower()
    assert "ppi leadership is evidenced" in ppie["Main gap"].lower()


def test_gantt_evidence_updates_dashboard_gap_and_action():
    facts = ApplicationFacts(duration_months="24", work_packages=["WP1 setup Month start 1 Month end 2"], milestones=["Month 2: setup complete"])
    rows = build_rag_dashboard(build_checklist(facts, derived_reviewer_requirements()), facts)
    pm = next(r for r in rows if r["Subsystem"] == "Project Management")
    assert "gantt" not in pm["Priority action"].lower()
    assert "gantt missing" not in pm["Main gap"].lower()
