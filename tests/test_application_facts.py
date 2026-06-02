from application_facts import extract_application_facts
from document_loader import LoadedDocument
from schemas import NOT_EXPLICITLY_STATED


def test_extraction_does_not_rely_on_filenames_and_missing_fields():
    facts = extract_application_facts([LoadedDocument("amazing_title.docx", "Lead applicant: Dr Smith\nProduct: Smart inhaler")])
    assert facts.project_title == NOT_EXPLICITLY_STATED
    assert facts.product_or_intervention == "Smart inhaler"
    assert facts.evidence


def test_trl_progression_not_contradiction():
    text = "The technology will progress from TRL 3-4 to TRL 6-7 during the award."
    facts = extract_application_facts([LoadedDocument("app.txt", text)])
    assert facts.current_trl_or_stage == "TRL 3-4"
    assert facts.target_trl_or_stage == "TRL 6-7"
    assert facts.contradictions_or_uncertainties == []

from tests.fixtures import STEPRIGHT_APP, STEPRIGHT_GANTT


def test_generic_body_patterns_extract_rich_application_facts():
    text = """
    The intervention is called BalanceHome, a digital programme for adults with stroke.
    The module is abbreviated as BHM. Study design: randomised pilot study.
    We will recruit about 54 people in NHS community clinics. Comparator: usual care.
    Endpoints include EQ-5D-5L and Berg Balance Scale. Regulatory plan includes UKCA, DTAC and ISO 13485.
    The plan runs months 1-24. WP1 setup Month start 1 Month end 6 output setup. Month 6: setup complete.
    """
    facts = extract_application_facts([LoadedDocument("not_used_filename.pdf", text)])
    assert facts.product_or_intervention == "BalanceHome"
    assert facts.acronym_or_short_name == "BHM"
    assert "adults with stroke" in facts.target_population.lower()
    assert "54" in facts.sample_size
    assert "NHS community" in facts.sites_or_setting
    assert "randomised" in facts.study_design.lower()
    assert "usual care" in facts.comparator_or_control.lower()
    assert any("EQ-5D" in e for e in facts.endpoints)
    assert "UKCA" in facts.regulatory_plan and "DTAC" in facts.regulatory_plan
    assert facts.duration_months == "24"
    assert facts.work_packages and facts.milestones


def test_training_labels_are_ignored_as_business_concepts():
    facts = extract_application_facts([LoadedDocument("training.docx", "FOR TRAINING USE ONLY\nFICTIONAL EXAMPLE APPLICATION\nThe intervention is called CareMove, a wearable device.")])
    assert "TRAINING" not in facts.product_or_intervention.upper()
    assert facts.product_or_intervention == "CareMove"


def test_stepright_regression_generic_extraction():
    facts = extract_application_facts([LoadedDocument("main.txt", STEPRIGHT_APP), LoadedDocument("gantt.txt", STEPRIGHT_GANTT)])
    assert facts.product_or_intervention == "StepRight"
    assert facts.acronym_or_short_name == "MQAE"
    assert "older adults" in facts.target_population.lower() or "60" in facts.target_population
    assert "54" in facts.sample_size
    assert "community rehabilitation" in facts.sites_or_setting.lower()
    assert "random" in facts.study_design.lower() or "pilot" in facts.study_design.lower()
    assert any("EQ-5D-5L" in e for e in facts.endpoints)
    assert any("Berg Balance" in e for e in facts.endpoints)
    assert "UKCA" in facts.regulatory_plan and "DTAC" in facts.regulatory_plan
    assert facts.duration_months == "24"
    assert len(facts.work_packages) >= 7
    assert any("Month 24" in m for m in facts.milestones)
    assert facts.ai_use_declaration == NOT_EXPLICITLY_STATED
    assert facts.conflicts_declaration == NOT_EXPLICITLY_STATED
