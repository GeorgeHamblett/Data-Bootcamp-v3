"""Checklist-first evaluation engine."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from guidance_parser import merge_requirements_with_overrides, parse_guidance_requirements
from schemas import CHECKLIST_AREAS, ApplicationFacts, ChecklistItem, Requirement, SOURCE_LABELS, NOT_EXPLICITLY_STATED

MANDATORY_MISSING_RED = {"mandatory", "required_if_applicable"}

FACT_FIELDS_BY_AREA = {
    "Summary Information": ["project_title", "application_claimed_call", "contracting_organisation"],
    "Lead Applicant and Research Team": ["applicant_or_lead", "partners"],
    "Application Details": ["product_or_intervention", "target_population", "study_design", "duration_months"],
    "Eligibility": ["application_claimed_call", "clinical_or_social_care_need"],
    "Clinical Validation": ["clinical_or_social_care_need", "sample_size", "endpoints", "methodology"],
    "Health Economics": ["health_economics_plan"],
    "Patient and Public Involvement / Working with People and Communities": ["ppie_plan"],
    "Research Inclusion": ["research_inclusion_plan"],
    "Project Management": ["project_management_plan", "work_packages", "milestones"],
    "Budget and Finance": ["finance_or_budget_evidence"],
    "Uploads": ["uploads_detected", "references_detected"],
    "Acknowledgement and Conflicts": ["ai_use_declaration", "conflicts_declaration"],
    "Similarity / Novelty / Prior Work": ["market_or_impact_evidence", "references_detected"],
}


def _has_value(value: Any) -> bool:
    return bool(value) and value != NOT_EXPLICITLY_STATED


def _evidence_for_area(facts: ApplicationFacts, area: str) -> list[str]:
    fields = FACT_FIELDS_BY_AREA.get(area, [])
    evidence: list[str] = []
    for field in fields:
        value = getattr(facts, field)
        if isinstance(value, list):
            if value:
                evidence.append(f"{field}: {', '.join(map(str, value[:5]))}")
        elif _has_value(value):
            evidence.append(f"{field}: {value}")
    # Prefer short source quotes where available.
    for ev in facts.evidence:
        if ev.section_or_context in fields and ev.quote not in " ".join(evidence):
            evidence.append(f"{ev.source_document}: “{ev.quote}”")
    return evidence[:5]


def _required_terms(requirement: Requirement) -> list[str]:
    text = requirement.requirement_text.lower()
    terms = []
    for term in ["acord", "soecat", "current rates", "cost justification", "scheme caps", "gantt", "references", "ai", "flow diagram", "ppi lead", "comparator"]:
        if term in text:
            terms.append(term)
    return terms


def _term_evidenced(term: str, facts: ApplicationFacts, evidence: list[str]) -> bool:
    haystack = "\n".join(evidence + [str(v) for v in facts.to_dict().values()]).lower()
    if term == "ai":
        return _has_value(facts.ai_use_declaration)
    if term == "gantt":
        return "gantt" in haystack or _has_value(facts.project_management_plan)
    if term == "references":
        return _has_value(facts.references_detected) or "references" in haystack
    return term in haystack


def evaluate_requirement(requirement: Requirement, facts: ApplicationFacts) -> ChecklistItem:
    evidence = _evidence_for_area(facts, requirement.checklist_area)
    required_terms = _required_terms(requirement)
    missing_terms = [term for term in required_terms if not _term_evidenced(term, facts, evidence)]

    if evidence and not missing_terms:
        status, rag, confidence = "Present", "GREEN", 0.82
        gap = "No obvious gap in the extracted application evidence for this requirement."
        action = "RSS adviser should verify evidence quality and consistency with the full application."
    elif evidence:
        status, rag, confidence = "Partially present", "AMBER", 0.58
        gap = f"Evidence is present but does not explicitly cover: {', '.join(missing_terms) or 'all expected detail'}."
        action = f"Add or verify application-specific detail for {requirement.checklist_area}."
    else:
        if requirement.mandatory_status in MANDATORY_MISSING_RED:
            status, rag, confidence = "Missing", "RED", 0.72
        else:
            status, rag, confidence = "Needs human check", "GREY", 0.42
        gap = f"Application evidence for {requirement.checklist_area} is Not explicitly stated."
        action = f"Ask the applicant to add explicit evidence addressing: {requirement.requirement_text[:140]}."

    if "flow diagram" in requirement.requirement_text.lower() and requirement.source != "specific_call" and not evidence:
        status, rag = "Needs human check", "GREY"
        gap = "Flow diagram is not explicitly evidenced, but no specific call rule made it mandatory."
        action = "Check whether the specific opportunity requires a flow diagram before marking as missing."

    if rag == "GREEN" and not evidence:
        rag, status = "RED", "Missing"

    return ChecklistItem(
        area=requirement.checklist_area,
        requirement=requirement.requirement_text,
        source_guidance=SOURCE_LABELS.get(requirement.source, requirement.source),
        status=status,
        rag=rag,
        evidence=evidence,
        gap=gap,
        action=action,
        confidence=confidence,
    )


def _ensure_area_coverage(requirements: list[Requirement]) -> list[Requirement]:
    existing = {r.checklist_area for r in requirements}
    added = list(requirements)
    for area in CHECKLIST_AREAS:
        if area not in existing:
            added.append(Requirement(f"coverage_{len(added)+1:03d}", "derived_reviewer_check", "Derived RSS reviewer checks", area, f"Provide application evidence for {area}.", "mandatory"))
    return added


def prepare_requirements(baseline: list[Requirement], specific_call_text: str = "") -> list[Requirement]:
    specific: list[Requirement] = []
    if specific_call_text.strip():
        specific = parse_guidance_requirements(specific_call_text, "specific_call", prefix="specific_call", overrides=True)
        for req in specific:
            req.overrides_general_guidance = True
    return _ensure_area_coverage(merge_requirements_with_overrides(baseline, specific))


def build_checklist(facts: ApplicationFacts, baseline_requirements: list[Requirement], specific_call_text: str = "") -> list[ChecklistItem]:
    requirements = prepare_requirements(baseline_requirements, specific_call_text)
    items = [evaluate_requirement(req, facts) for req in requirements]
    # Guarantee important derived checks are present even if parser did not find relevant wording.
    required_phrases = {
        "Budget and Finance": "Budget must include AcoRD, SoECAT if applicable, current rates, cost justification and scheme caps.",
        "Uploads": "Required uploads should include Gantt/project management plan and references.",
        "Acknowledgement and Conflicts": "Application must include AI-use declaration and conflicts acknowledgement.",
    }
    existing_text = "\n".join(i.requirement.lower() for i in items)
    for area, phrase in required_phrases.items():
        if phrase.lower() not in existing_text:
            items.append(evaluate_requirement(Requirement(f"required_{area}", "derived_reviewer_check", "Derived RSS reviewer checks", area, phrase, "mandatory"), facts))
    return items


def checklist_to_rows(items: list[ChecklistItem]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]
