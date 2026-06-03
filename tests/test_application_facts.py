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


def extract_text(text):
    return extract_application_facts([LoadedDocument("app.txt", text)])


def test_duration_prefers_max_project_month_evidence():
    facts = extract_text("Phase 1 months 1-10 and Phase 2 months 11-24. The first phase is 10 months.")
    assert facts.duration_months == "24"


def test_gantt_rows_ending_month_24_drive_duration():
    facts = extract_text("Gantt/workplan\nProject set-up and governance | Month 1 | Month 2 | 2 months | documents\nAnalysis | Month 18 | Month 24 | 7 months | final report")
    assert facts.duration_months == "24"


def test_single_ten_month_plan_only_without_later_month():
    facts = extract_text("This is a single 10-month plan with no later milestone evidence.")
    assert facts.duration_months == "10"


def test_study_design_selected_over_background():
    facts = extract_text("Workforce constraints and falls pressure are severe. Study design: two-arm randomised feasibility evaluation with mixed-methods follow-up.")
    assert "two-arm randomised feasibility" in facts.study_design.lower()
    assert "workforce" not in facts.study_design.lower()


def test_background_sentence_not_study_design():
    facts = extract_text("Workforce constraints create a problem for rehabilitation services. Falls can seriously affect independence.")
    assert facts.study_design == NOT_EXPLICITLY_STATED


def test_population_need_and_technology_are_concise_distinct():
    text = "The intervention is designed to help older adults improve balance and reduce risk of falling. Participants aged 60 and over with recent falls risk and reduced balance confidence will be recruited. It is an AI-enabled wearable digital therapeutic using a movement quality assessment engine."
    facts = extract_text(text)
    assert "older adults" in facts.target_population.lower() or "aged 60" in facts.target_population.lower()
    assert "balance" in facts.clinical_or_social_care_need.lower() and "fall" in facts.clinical_or_social_care_need.lower()
    assert "ai-enabled wearable digital therapeutic" in facts.technology_type.lower()
    assert facts.target_population != facts.clinical_or_social_care_need != facts.technology_type


def test_regulatory_stronger_evidence_not_hidden_by_ethics():
    facts = extract_text("Month 13: Ethics and site approvals complete. Regulatory plan includes UKCA, DTAC, ISO 14971, ISO 13485 and IEC 62304 technical documentation.")
    assert "UKCA" in facts.regulatory_plan and "DTAC" in facts.regulatory_plan
    assert "ISO" in facts.regulatory_plan or "IEC" in facts.regulatory_plan


def test_health_economics_prefers_modelling_resource_use_budget_impact():
    facts = extract_text("Comparator: usual care in community rehabilitation. Health economics will include EQ-5D-5L, resource use, micro-costing, an early decision-analytic model and exploratory budget impact analysis for cost-effectiveness.")
    assert "usual care" not in facts.health_economics_plan.lower()[:30]
    assert "resource use" in facts.health_economics_plan.lower()
    assert "budget impact" in facts.health_economics_plan.lower()


def test_work_packages_only_structured_rows_and_deduped():
    text = """
    Implementation paragraphs mention WP3 and WP4 but are not rows and should not be extracted as work package items because they are long narrative text about inclusion and knowledge mobilisation.
    WP1: Project setup and governance
    WP2: Algorithm development
    Project set-up and governance | Month 1 | Month 2 | 2 months | Sponsor documents
    Project set-up and governance | Month 1 | Month 2 | 2 months | Sponsor documents
    """
    facts = extract_text(text)
    assert any(row.startswith("WP1") for row in facts.work_packages)
    assert any("| Month 1 | Month 2" in row for row in facts.work_packages)
    assert len(facts.work_packages) == len(set(facts.work_packages))
    assert not any(row.startswith("Implementation paragraphs") for row in facts.work_packages)


def test_milestones_exclude_headings_and_generic_gantt_text():
    facts = extract_text("Milestones\nTimeline and milestones\nA Gantt chart is included.\nMonth 8: Algorithm validated to acceptable threshold")
    assert "Month 8: Algorithm validated to acceptable threshold" in facts.milestones
    assert "Milestones" not in facts.milestones
    assert "Timeline and milestones" not in facts.milestones
    assert not any("Gantt chart" in m for m in facts.milestones)


def test_upload_and_reference_detection_no_knowledge_false_positive():
    facts = extract_text("Communication preferences and knowledge mobilisation will be discussed. A Gantt chart is included. References uploaded.")
    assert facts.references_detected != NOT_EXPLICITLY_STATED
    assert any("Gantt chart" in u for u in facts.uploads_detected)
    neg = extract_text("Communication preferences and knowledge mobilisation will be discussed.")
    assert neg.references_detected == NOT_EXPLICITLY_STATED
    assert neg.uploads_detected == []


def test_ppie_named_coordination_extracted():
    facts = extract_text("Ms X, a co-applicant, will provide day-to-day PPI coordination. Public contributors will advise on materials.")
    assert "PPI coordination" in facts.ppie_leadership_evidence


def test_project_title_and_i4i_pda_call_extraction_from_runtime_text():
    facts = extract_text("StepRight movement quality assessment for community falls rehabilitation\nThis is an NIHR i4i PDA application for older adults.")
    assert facts.project_title.startswith("StepRight movement quality assessment")
    assert "i4i" in facts.application_claimed_call.lower() or "pda" in facts.application_claimed_call.lower()

from tests.fixtures import WOUNDWISE_APP
from checklist_engine import build_checklist
from guidance_parser import derived_reviewer_requirements


def test_woundwise_exemplar_regression_extraction():
    facts = extract_application_facts([LoadedDocument("fictional_NIHR_i4i_PDA_exemplar_application_v3.txt", WOUNDWISE_APP)])
    assert facts.product_or_intervention != "The"
    assert "WoundWise-AI handheld multispectral imaging device" in facts.product_or_intervention
    assert facts.acronym_or_short_name == "WoundWise-AI"
    assert "480" in facts.sample_size
    assert facts.sample_size != "126 participants"
    assert "126 participants with events" not in facts.sample_size
    assert "Ms Priya Nair" in facts.ppie_leadership_evidence
    assert "Dr Farah Siddiqui" in facts.research_inclusion_plan or "sex, gender, ethnicity" in facts.research_inclusion_plan
    assert facts.research_inclusion_plan != facts.ppie_leadership_evidence
    assert "Ms Priya Nair" not in facts.research_inclusion_plan
    for term in ["detailed budget", "cost justification", "current rates", "AcoRD", "SoECAT"]:
        assert term in facts.finance_or_budget_evidence
    assert len(facts.work_packages) >= 7
    assert any(row.startswith("WP1") for row in facts.work_packages)
    assert any(row.startswith("WP7") for row in facts.work_packages)
    for month in ["Month 3", "Month 6", "Month 24", "Month 30"]:
        assert any(month in milestone for milestone in facts.milestones)
    assert "invented" not in facts.market_or_impact_evidence.lower()
    assert any(section in facts.market_or_impact_evidence for section in ["Market and adoption", "IP and commercialisation", "Knowledge mobilisation"])


def test_woundwise_budget_and_finance_is_evidenced_not_ppie_only():
    facts = extract_application_facts([LoadedDocument("app.txt", WOUNDWISE_APP)])
    items = build_checklist(facts, derived_reviewer_requirements())
    finance = next(item for item in items if item.area == "Budget and Finance")
    assert finance.rag == "GREEN"
    assert "PPIE" not in facts.finance_or_budget_evidence[:20]
