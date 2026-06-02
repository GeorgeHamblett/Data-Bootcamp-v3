from application_facts import extract_application_facts
from checklist_engine import build_checklist
from guidance_parser import derived_reviewer_requirements
from schemas import CHECKLIST_AREAS, Requirement


def _facts():
    return extract_application_facts([{"name": "app.txt", "text": "Project title: A\nLead applicant: B\nBudget: includes staff costs\nAI use: none\nConflicts: none\nReferences: included\nProject management: Gantt and milestones\nPPIE: led by named PPI lead Sarah\nHealth economics: NHS perspective comparator and cost outcome plan\nResearch inclusion: underserved groups considered\nClinical need: diabetes\nSample size: 50\nEndpoints: HbA1c\n"}])


def test_checklist_includes_all_13_areas_and_source_guidance():
    items = build_checklist(_facts(), derived_reviewer_requirements())
    assert set(CHECKLIST_AREAS).issubset({i.area for i in items})
    assert all(i.source_guidance for i in items)


def test_no_green_without_evidence():
    items = build_checklist(extract_application_facts([{"name": "app.txt", "text": ""}]), derived_reviewer_requirements())
    assert all(not (i.rag == "GREEN" and not i.evidence) for i in items)


def test_specific_call_overrides_baseline_guidance():
    baseline = [Requirement("b", "nihr_domestic", "s", "Uploads", "General upload requirement", "mandatory")]
    items = build_checklist(_facts(), baseline, specific_call_text="Uploads\nYou must upload a specific call logic model.")
    assert any(i.source_guidance == "Specific funding call" for i in items)
    assert not any(i.requirement == "General upload requirement" for i in items)


def test_flow_diagram_not_red_unless_specific_call_requires():
    req = [Requirement("flow", "nihr_domestic", "s", "Uploads", "Upload a flow diagram if specified.", "required_if_applicable")]
    items = build_checklist(extract_application_facts([{"name": "app.txt", "text": "Project title: A"}]), req)
    flow = [i for i in items if "flow diagram" in i.requirement.lower()][0]
    assert flow.rag != "RED"


def test_budget_upload_acknowledgement_checks_present():
    items = build_checklist(_facts(), [])
    text = "\n".join(i.requirement for i in items).lower()
    for term in ["acord", "soecat", "current rates", "cost justification", "scheme caps", "gantt", "references", "ai-use"]:
        assert term in text
