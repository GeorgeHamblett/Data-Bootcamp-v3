"""Requirement-specific checklist evidence matching."""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Iterable

from guidance_parser import derived_reviewer_requirements, ensure_area_coverage, merge_requirements_with_specific_override
from schemas import CHECKLIST_AREAS, NOT_EXPLICITLY_STATED, SOURCE_LABELS, ApplicationFacts, ChecklistItem, Requirement

FIELD_PURPOSES = {
    "project_title": ["title", "summary", "project identity"],
    "application_claimed_call": ["call", "programme", "opportunity", "remit", "fit"],
    "product_or_intervention": ["product", "intervention", "technology", "innovation", "device", "software", "service", "model"],
    "acronym_or_short_name": ["acronym", "short name", "module"],
    "applicant_or_lead": ["lead", "applicant", "chief investigator", "team"],
    "contracting_organisation": ["contracting", "organisation", "organization", "host", "eligible"],
    "partners": ["partner", "collaborator", "clinical", "care partner", "team"],
    "target_population": ["population", "patients", "people", "service users"],
    "clinical_or_social_care_need": ["need", "problem", "rationale", "burden", "evidence gap", "inequality"],
    "technology_type": ["technology", "device", "software", "digital", "method", "validated tools"],
    "current_trl_or_stage": ["trl", "stage", "proof of concept"],
    "target_trl_or_stage": ["trl", "stage", "development"],
    "trl_evidence": ["trl", "stage", "proof of concept", "development"],
    "study_design": ["design", "feasibility", "pilot", "comparative", "trial", "validation"],
    "methodology": ["method", "methodology", "research plan"],
    "sample_size": ["sample", "participants", "size"],
    "sites_or_setting": ["site", "setting", "NHS", "social care"],
    "duration_months": ["duration", "month", "timeline"],
    "work_packages": ["work package", "gantt", "timeline", "project management"],
    "milestones": ["milestone", "deliverable", "timeline"],
    "endpoints": ["endpoint", "outcome", "NICE", "clinical validation"],
    "comparator_or_control": ["comparator", "current care", "usual care", "control"],
    "regulatory_plan": ["regulatory", "ethics", "approval", "UKCA", "DTAC", "ISO", "medical device"],
    "health_economics_plan": ["health economic", "economic", "perspective", "comparator", "EQ-5D", "HRQoL", "QALY", "resource use", "model", "sensitivity", "value proposition", "cost-effectiveness"],
    "ppie_plan": ["PPI", "PPIE", "people and communities", "public", "lived experience", "co-design"],
    "research_inclusion_plan": ["inclusion", "inclusive", "underserved", "sex", "gender", "accessibility", "disability", "ethnicity", "digital exclusion"],
    "project_management_plan": ["project management", "gantt", "work package", "milestone", "risk", "governance", "contingenc"],
    "finance_or_budget_evidence": ["budget", "finance", "cost", "AcoRD", "SoECAT", "current rates", "scheme cap", "funding rate", "treatment cost", "support cost"],
    "uploads_detected": ["upload", "attachment", "gantt", "references", "flow diagram", "logic model", "flexible upload"],
    "references_detected": ["references", "bibliography"],
    "ai_use_declaration": ["AI", "artificial intelligence", "generative AI"],
    "conflicts_declaration": ["conflict", "competing interest"],
    "market_or_impact_evidence": ["market", "impact", "adoption", "commercial", "IP", "novelty", "prior work", "value for money"],
    "next_stage_plan": ["next-stage", "next stage", "future", "adoption-readiness"],
}

AREA_DEFAULT_FIELDS = {
    "Summary Information": ["project_title", "application_claimed_call", "duration_months"],
    "Lead Applicant and Research Team": ["applicant_or_lead", "contracting_organisation", "partners"],
    "Application Details": ["product_or_intervention", "acronym_or_short_name", "target_population", "clinical_or_social_care_need", "technology_type", "trl_evidence"],
    "Eligibility": ["application_claimed_call", "applicant_or_lead", "contracting_organisation", "partners", "trl_evidence", "market_or_impact_evidence"],
    "Clinical Validation": ["study_design", "methodology", "sample_size", "sites_or_setting", "endpoints", "comparator_or_control", "regulatory_plan", "next_stage_plan"],
    "Health Economics": ["health_economics_plan", "comparator_or_control", "endpoints"],
    "Patient and Public Involvement / Working with People and Communities": ["ppie_plan", "ppie_leadership_evidence"],
    "Research Inclusion": ["research_inclusion_plan"],
    "Project Management": ["project_management_plan", "work_packages", "milestones", "duration_months"],
    "Budget and Finance": ["finance_or_budget_evidence"],
    "Uploads": ["uploads_detected", "references_detected", "project_management_plan"],
    "Acknowledgement and Conflicts": ["ai_use_declaration", "conflicts_declaration"],
    "Similarity / Novelty / Prior Work": ["market_or_impact_evidence", "references_detected", "product_or_intervention"],
}

COMPLETENESS_TERMS = {
    "Budget and Finance": ["AcoRD", "SoECAT", "current rates", "justification", "scheme cap"],
    "Health Economics": ["perspective", "comparator", "cost"],
    "Patient and Public Involvement / Working with People and Communities": ["lead", "payment"],
    "Project Management": ["gantt", "milestone"],
    "Uploads": ["gantt", "references"],
    "Acknowledgement and Conflicts": ["AI", "conflict"],
}

PRACTICAL_ACTIONS = {
    "Summary Information": "Add or verify the project title, call, start date and duration in the application summary.",
    "Lead Applicant and Research Team": "Add or verify lead applicant, contracting organisation, partners and team roles.",
    "Application Details": "Add or verify the intervention, acronym, target population, need, technology type and development stage.",
    "Eligibility": "Confirm partner eligibility and call remit fit against the specific funding call guidance.",
    "Clinical Validation": "Add or verify design, sample size, sites, endpoints, comparator, approvals and next-stage plan.",
    "Health Economics": "Add or verify health economics perspective, comparator, resource use, cost-outcome plan, model and sensitivity analysis.",
    "Patient and Public Involvement / Working with People and Communities": "Add or verify named PPI lead, public contributors/advisory group, involvement impact and payment/support costs.",
    "Research Inclusion": "Add or verify underserved groups, accessibility, sex/gender, exclusion criteria, inclusion costs and dissemination.",
    "Project Management": "Upload or verify Gantt/project management plan, work packages, milestones, governance, risks and contingencies.",
    "Budget and Finance": "Add or verify detailed budget, cost justification, current rates, scheme caps, AcoRD and SoECAT applicability.",
    "Uploads": "Upload or verify references, Gantt/project management plan and any flow diagram, logic model or flexible upload required by the call.",
    "Acknowledgement and Conflicts": "Add or verify the AI-use declaration and conflicts declaration in Acknowledgement and Conflicts.",
    "Similarity / Novelty / Prior Work": "Add or verify novelty, prior work, market/adoption route and references.",
}


def _has_value(value: object) -> bool:
    if isinstance(value, list):
        return bool(value)
    return bool(value and value != NOT_EXPLICITLY_STATED)


def _field_text(facts: ApplicationFacts, field: str) -> str:
    value = getattr(facts, field, NOT_EXPLICITLY_STATED)
    if isinstance(value, list):
        return "; ".join(str(v) for v in value if v)
    return "" if value == NOT_EXPLICITLY_STATED else str(value)


def allowed_fields_for_requirement(req: Requirement) -> list[str]:
    text = req.requirement_text.lower()
    allowed = [field for field, keywords in FIELD_PURPOSES.items() if any(k.lower() in text for k in keywords)]
    if not allowed:
        allowed = AREA_DEFAULT_FIELDS.get(req.checklist_area, [])
    # Hard separations.
    if req.checklist_area == "Budget and Finance":
        allowed = ["finance_or_budget_evidence"]
    if req.checklist_area == "Health Economics":
        allowed = ["health_economics_plan", "comparator_or_control", "endpoints"]
    if req.checklist_area == "Patient and Public Involvement / Working with People and Communities":
        allowed = ["ppie_plan", "ppie_leadership_evidence"]
    if req.checklist_area == "Research Inclusion":
        allowed = ["research_inclusion_plan"]
    return list(dict.fromkeys(allowed))


def relevant_evidence(req: Requirement, facts: ApplicationFacts) -> list[str]:
    evidence = []
    for field in allowed_fields_for_requirement(req):
        text = _field_text(facts, field)
        if text:
            evidence.append(f"{field}: {text}")
    return evidence


def missing_completeness_terms(area: str, evidence_text: str) -> list[str]:
    terms = COMPLETENESS_TERMS.get(area, [])
    # Finance: if no actual budget field text exists, all finance terms count as missing.
    return [term for term in terms if term.lower() not in evidence_text.lower()]


def _remaining_action(area: str, missing_terms: list[str], evidence_text: str) -> str:
    missing = [term for term in missing_terms]
    if area == "Patient and Public Involvement / Working with People and Communities":
        if "lead" not in [m.lower() for m in missing]:
            if any(term.lower() == "payment" for term in missing):
                return "Add or verify PPIE payment/support costs and describe public contributor impact."
            return "Add or verify remaining PPIE details, especially public contributor impact and support costs."
    if area == "Project Management":
        lower_missing = [m.lower() for m in missing]
        if "gantt" not in lower_missing and "milestone" not in lower_missing:
            return "Add or verify project governance, risk register and contingencies."
        if "gantt" not in lower_missing:
            return "Add or verify milestones plus project governance, risk register and contingencies."
    return PRACTICAL_ACTIONS.get(area, f"Add or verify {', '.join(missing_terms)}.")


def evaluate_requirement(req: Requirement, facts: ApplicationFacts) -> ChecklistItem:
    evidence = relevant_evidence(req, facts)
    evidence_text = " ".join(evidence)

    if "flow diagram" in req.requirement_text.lower() and req.mandatory_status == "required_if_applicable" and req.source != "specific_call":
        return ChecklistItem(req.checklist_area, req.requirement_text, SOURCE_LABELS.get(req.source, req.source), "Needs human check", "GREY", evidence, "Only required if specified by the funding call.", "Confirm whether the specific call requires a flow diagram before treating it as missing.", 0.45)
    if "logic model" in req.requirement_text.lower() and req.mandatory_status == "required_if_applicable" and req.source != "specific_call":
        return ChecklistItem(req.checklist_area, req.requirement_text, SOURCE_LABELS.get(req.source, req.source), "Needs human check", "GREY", evidence, "Only required if specified by the funding call.", "Confirm whether the specific call requires a logic model.", 0.45)

    if not evidence:
        rag = "RED" if req.mandatory_status in {"mandatory", "required_if_applicable"} else "GREY"
        status = "Missing" if rag == "RED" else "Needs human check"
        return ChecklistItem(req.checklist_area, req.requirement_text, SOURCE_LABELS.get(req.source, req.source), status, rag, [], f"No relevant application evidence found for {req.checklist_area}.", PRACTICAL_ACTIONS.get(req.checklist_area, "Add or verify application-specific evidence."), 0.30)

    missing_terms = missing_completeness_terms(req.checklist_area, evidence_text)
    if req.checklist_area == "Patient and Public Involvement / Working with People and Communities":
        if re.search(r"co-applicant|PPI coord|PPI lead|named\s+PPI|Ms\s+|Mr\s+|Dr\s+", evidence_text, re.I):
            missing_terms = [term for term in missing_terms if term.lower() != "lead"]
    if req.checklist_area == "Project Management":
        if facts.work_packages or facts.milestones or any("gantt" in str(upload).lower() or "workplan" in str(upload).lower() for upload in facts.uploads_detected):
            missing_terms = [term for term in missing_terms if term.lower() != "gantt"]
        if facts.milestones:
            missing_terms = [term for term in missing_terms if term.lower() != "milestone"]
    if missing_terms:
        return ChecklistItem(req.checklist_area, req.requirement_text, SOURCE_LABELS.get(req.source, req.source), "Partially present", "AMBER", evidence, f"Relevant evidence is present but missing or unclear: {', '.join(missing_terms)}.", _remaining_action(req.checklist_area, missing_terms, evidence_text), 0.65)

    return ChecklistItem(req.checklist_area, req.requirement_text, SOURCE_LABELS.get(req.source, req.source), "Present", "GREEN", evidence, "No major gap identified from relevant evidence.", "Review consistency with specific call guidance before submission.", 0.85)


def build_requirements(baseline: Iterable[Requirement], specific_call: Iterable[Requirement] | None = None) -> list[Requirement]:
    baseline_list = ensure_area_coverage(list(baseline) + derived_reviewer_requirements())
    if specific_call:
        return ensure_area_coverage(merge_requirements_with_specific_override(baseline_list, specific_call))
    return baseline_list


def build_checklist(facts: ApplicationFacts, baseline: Iterable[Requirement], specific_call: Iterable[Requirement] | None = None) -> list[ChecklistItem]:
    requirements = build_requirements(baseline, specific_call)
    selected: list[Requirement] = []
    for area in CHECKLIST_AREAS:
        area_reqs = [req for req in requirements if req.checklist_area == area]
        specific = [req for req in area_reqs if req.source == "specific_call"]
        derived = [req for req in area_reqs if req.source == "derived_reviewer_check"]
        non_derived = [req for req in area_reqs if req.source != "derived_reviewer_check"]
        chosen = (specific or non_derived or derived or [req for req in derived_reviewer_requirements() if req.checklist_area == area])[0]
        selected.append(chosen)
    return [evaluate_requirement(req, facts) for req in selected]


def checklist_to_json(items: Iterable[ChecklistItem]) -> list[dict]:
    return [asdict(item) for item in items]
