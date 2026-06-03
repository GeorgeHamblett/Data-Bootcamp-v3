from checklist_engine import build_checklist
from guidance_parser import derived_reviewer_requirements
from schemas import CHECKLIST_AREAS, ApplicationFacts, Requirement


def populated_facts():
    return ApplicationFacts(
        project_title="Remote COPD monitor",
        application_claimed_call="i4i PDA",
        product_or_intervention="Remote COPD monitor",
        applicant_or_lead="Dr Lead",
        contracting_organisation="NHS Trust",
        target_population="People with COPD",
        clinical_or_social_care_need="COPD admissions",
        technology_type="Digital device",
        trl_evidence="TRL 3-4 to TRL 6-7",
        study_design="Feasibility study",
        methodology="Mixed methods",
        sample_size="60",
        sites_or_setting="Primary care",
        endpoints=["Exacerbations"],
        health_economics_plan="NHS perspective comparator usual care cost outcome plan",
        ppie_plan="Named PPI lead Jane with contributors",
        research_inclusion_plan="Underserved groups included",
        project_management_plan="Gantt timeline with milestones",
        finance_or_budget_evidence="AcoRD, SoECAT if applicable, current rates, justification of costs and scheme cap checked",
        uploads_detected=["Gantt", "references"],
        references_detected="References uploaded",
        ai_use_declaration="No generative AI used",
        conflicts_declaration="No conflicts",
        market_or_impact_evidence="Prior work and adoption plan",
    )


def test_checklist_includes_all_areas_and_source_guidance():
    items = build_checklist(populated_facts(), derived_reviewer_requirements())
    assert [i.area for i in items] == CHECKLIST_AREAS
    assert all(i.source_guidance for i in items)


def test_no_green_without_evidence():
    items = build_checklist(ApplicationFacts(), derived_reviewer_requirements())
    assert not any(i.rag == "GREEN" and not i.evidence for i in items)


def test_specific_call_guidance_overrides_baseline():
    specific = [Requirement("c1", "specific_call", "Call", "Eligibility", "Specific call budget cap is £500k", "mandatory", overrides_general_guidance=True)]
    items = build_checklist(populated_facts(), derived_reviewer_requirements(), specific)
    assert next(i for i in items if i.area == "Eligibility").requirement == "Specific call budget cap is £500k"


def test_flow_diagram_not_red_unless_specific_call_required():
    baseline = [Requirement("f1", "nihr_domestic", "Uploads", "Uploads", "A flow diagram may be useful", "recommended")]
    item = next(i for i in build_checklist(ApplicationFacts(), baseline) if i.area == "Uploads")
    assert item.rag != "RED"
    specific = [Requirement("f2", "specific_call", "Uploads", "Uploads", "You must upload a flow diagram", "mandatory", overrides_general_guidance=True)]
    item2 = next(i for i in build_checklist(ApplicationFacts(), baseline, specific) if i.area == "Uploads")
    assert item2.rag == "RED"


def test_budget_upload_acknowledgement_checks_keywords():
    items = build_checklist(populated_facts(), derived_reviewer_requirements())
    budget = next(i for i in items if i.area == "Budget and Finance")
    upload = next(i for i in items if i.area == "Uploads")
    ack = next(i for i in items if i.area == "Acknowledgement and Conflicts")
    assert all(term in budget.requirement for term in ["AcoRD", "SoECAT", "current rates", "justification", "scheme caps"])
    assert "Gantt" in upload.requirement and "references" in upload.requirement
    assert "AI-use" in ack.requirement or "AI" in ack.requirement


def test_requirement_specific_matching_prevents_irrelevant_green():
    facts = ApplicationFacts(duration_months="24", endpoints=["EQ-5D-5L"], project_management_plan="Gantt plan", uploads_detected=["Gantt"])
    items = build_checklist(facts, derived_reviewer_requirements())
    app_details = next(i for i in items if i.area == "Application Details")
    lead = next(i for i in items if i.area == "Lead Applicant and Research Team")
    ppie = next(i for i in items if i.area.startswith("Patient"))
    assert app_details.rag != "GREEN"
    assert lead.rag != "GREEN"
    assert ppie.rag != "GREEN"


def test_finance_not_green_from_health_economics_only():
    facts = ApplicationFacts(health_economics_plan="NHS perspective usual care comparator EQ-5D QALY cost-effectiveness model budget impact sensitivity analysis")
    items = build_checklist(facts, derived_reviewer_requirements())
    finance = next(i for i in items if i.area == "Budget and Finance")
    he = next(i for i in items if i.area == "Health Economics")
    assert finance.rag != "GREEN"
    assert finance.evidence == []
    assert he.rag in {"GREEN", "AMBER"}


def test_ppie_leadership_evidence_prevents_named_lead_missing_wording():
    facts = ApplicationFacts(
        ppie_plan="Public contributors will advise on materials.",
        ppie_leadership_evidence="Ms Leila Karim, a co-applicant, will provide day-to-day PPI coordination.",
    )
    item = next(i for i in build_checklist(facts, derived_reviewer_requirements()) if i.area == "Patient and Public Involvement / Working with People and Communities")
    assert "lead" not in item.gap.lower()
    assert "named ppi lead" not in item.action.lower()


def test_gantt_work_packages_milestones_prevent_gantt_missing_wording():
    facts = ApplicationFacts(duration_months="24", work_packages=["WP1 setup Month start 1 Month end 2"], milestones=["Month 2: setup complete"])
    item = next(i for i in build_checklist(facts, derived_reviewer_requirements()) if i.area == "Project Management")
    assert "gantt" not in item.gap.lower()
