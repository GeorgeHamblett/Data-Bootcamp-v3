from application_facts import extract_application_facts
from schemas import NOT_EXPLICITLY_STATED


def test_extraction_uses_content_not_filename():
    facts = extract_application_facts([{"name": "Amazing_Title_TRL9.docx", "text": "Lead applicant: Dr Smith\nProject title: Community Sensor\nTRL 3-4 to TRL 6-7"}])
    assert facts.project_title == "Community Sensor"
    assert facts.applicant_or_lead == "Dr Smith"
    assert "Amazing_Title" not in facts.project_title


def test_missing_fields_use_not_explicitly_stated_and_evidence_exists():
    facts = extract_application_facts([{"name": "app.txt", "text": "Project title: Test Project"}])
    assert facts.contracting_organisation == NOT_EXPLICITLY_STATED
    assert facts.evidence and facts.evidence[0].quote.startswith("Project title")


def test_trl_progression_not_contradiction():
    facts = extract_application_facts([{"name": "app.txt", "text": "The innovation will progress from TRL 3-4 to TRL 6-7."}])
    assert facts.current_trl_or_stage == "TRL 3-4"
    assert facts.target_trl_or_stage == "TRL 6-7"
    assert not facts.contradictions_or_uncertainties
