"""Curated guidance parsing into adviser-checkable checklist requirements.

Built-in NIHR/RSS guidance files contain large amounts of portal/process guidance.
This module deliberately avoids extracting arbitrary sentences from those files and
instead produces a controlled baseline of reviewable requirements. Runtime specific
call guidance is parsed only for call-level constraints and uploads.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from schemas import Requirement

# Concise, adviser-checkable baseline requirements. These are not portal tasks.
NIHR_DOMESTIC_BASELINE = [
    ("Summary Information", "Application title present and concise", "mandatory"),
    ("Summary Information", "Start month/year present", "mandatory"),
    ("Summary Information", "Duration in whole months present", "mandatory"),
    ("Summary Information", "Previous submission status stated, with resubmission details where applicable", "required_if_applicable"),
    ("Lead Applicant and Research Team", "Lead applicant named", "mandatory"),
    ("Lead Applicant and Research Team", "Contracting organisation identified", "mandatory"),
    ("Lead Applicant and Research Team", "Contracting organisation department identified where relevant", "required_if_applicable"),
    ("Lead Applicant and Research Team", "Research team roles and partner contributions described", "mandatory"),
    ("Lead Applicant and Research Team", "Dedicated PPI lead included", "mandatory"),
    ("Lead Applicant and Research Team", "ORCID requirement flagged for lead applicant where required", "required_if_applicable"),
    ("Application Details", "Scientific abstract present", "mandatory"),
    ("Application Details", "Plain English summary present and accessible", "mandatory"),
    ("Application Details", "Detailed research plan present", "mandatory"),
    ("Eligibility", "Background/rationale explains problem, evidence gap, inequality and fit to opportunity", "mandatory"),
    ("Eligibility", "Aims and objectives clear", "mandatory"),
    ("Clinical Validation", "Methodology includes design, methods, timeline and milestones", "mandatory"),
    ("Research Inclusion", "Inclusive research including sex and gender addressed", "mandatory"),
    ("Clinical Validation", "Knowledge mobilisation, dissemination and impact plan included", "mandatory"),
    ("Project Management", "Project management plan included", "mandatory"),
    ("Similarity / Novelty / Prior Work", "IP or commercialisation addressed where relevant", "required_if_applicable"),
    ("Budget and Finance", "Budget section present", "mandatory"),
    ("Budget and Finance", "High-level expected costs included", "mandatory"),
    ("Budget and Finance", "NHS/non-NHS support and treatment costs considered where applicable", "required_if_applicable"),
    ("Budget and Finance", "AcoRD considered where relevant", "required_if_applicable"),
    ("Budget and Finance", "Justification of costs present", "mandatory"),
    ("Budget and Finance", "Costs entered at current rates", "mandatory"),
    ("Budget and Finance", "Scheme rates and caps considered", "mandatory"),
    ("Budget and Finance", "Organisation type and funding rate reflected", "required_if_applicable"),
    ("Budget and Finance", "SoECAT considered, uploaded and signed off where applicable", "required_if_applicable"),
    ("Uploads", "Gantt chart or project management plan uploaded", "mandatory"),
    ("Uploads", "References uploaded", "mandatory"),
    ("Uploads", "Flow diagram uploaded only if specified", "required_if_applicable"),
    ("Uploads", "Logic model uploaded only if specified", "required_if_applicable"),
    ("Uploads", "Flexible upload included only if specified", "required_if_applicable"),
    ("Acknowledgement and Conflicts", "AI-use declaration answered Yes/No", "mandatory"),
    ("Acknowledgement and Conflicts", "Conflicts declared", "mandatory"),
    ("Acknowledgement and Conflicts", "Lead applicant confirms terms and responsibility", "mandatory"),
    ("Patient and Public Involvement / Working with People and Communities", "Working with people and communities summary present", "mandatory"),
]

RSS_PDA_BASELINE = [
    ("Eligibility", "Eligible lead and organisation evidenced", "mandatory"),
    ("Lead Applicant and Research Team", "Appropriate partner mix described", "mandatory"),
    ("Lead Applicant and Research Team", "Clinical or care partner included", "mandatory"),
    ("Application Details", "TRL 3+ proof of concept evidenced where PDA applies", "mandatory"),
    ("Eligibility", "Development, validation or adoption-readiness fit explained", "mandatory"),
    ("Eligibility", "NHS or social care value described", "mandatory"),
    ("Eligibility", "ARI-3 or workforce alignment addressed where PDA applies", "required_if_applicable"),
    ("Clinical Validation", "Clinical validation question clear", "mandatory"),
    ("Clinical Validation", "Feasibility, pilot or comparative design described", "mandatory"),
    ("Clinical Validation", "Sample size and justification included", "mandatory"),
    ("Clinical Validation", "Sites and setting described", "mandatory"),
    ("Clinical Validation", "Endpoints aligned with NHS/NICE adoption", "mandatory"),
    ("Clinical Validation", "Ethics and regulatory approval plan included", "mandatory"),
    ("Clinical Validation", "Validated tools and clinician/user training described where relevant", "required_if_applicable"),
    ("Clinical Validation", "Next-stage plan described", "mandatory"),
    ("Health Economics", "Health economist involvement described", "mandatory"),
    ("Health Economics", "Economic perspective stated and justified", "mandatory"),
    ("Health Economics", "Comparator or current care stated", "mandatory"),
    ("Health Economics", "EQ-5D, HRQoL or QALYs considered where relevant", "required_if_applicable"),
    ("Health Economics", "Resource use and cost drivers described", "mandatory"),
    ("Health Economics", "Economic modelling and sensitivity analysis described", "mandatory"),
    ("Health Economics", "Value proposition for NHS or social care adoption described", "mandatory"),
    ("Patient and Public Involvement / Working with People and Communities", "PPIE involvement so far described", "mandatory"),
    ("Patient and Public Involvement / Working with People and Communities", "Named PPI lead identified", "mandatory"),
    ("Patient and Public Involvement / Working with People and Communities", "PPI payment and support budgeted", "mandatory"),
    ("Research Inclusion", "Research inclusion embedded in design", "mandatory"),
    ("Research Inclusion", "Sex and gender addressed", "mandatory"),
    ("Project Management", "Work packages and Gantt included", "mandatory"),
    ("Project Management", "Risk register included", "mandatory"),
    ("Similarity / Novelty / Prior Work", "Market need and impact described", "mandatory"),
    ("Budget and Finance", "Value for money evidenced", "mandatory"),
]

DERIVED_REQUIREMENTS = [
    ("Summary Information", "Project title, short summary and intended funding call are stated", "mandatory"),
    ("Lead Applicant and Research Team", "Lead applicant, contracting organisation, partners and relevant team expertise are evidenced", "mandatory"),
    ("Application Details", "Product/intervention, target population, need, technology type and development stage are described", "mandatory"),
    ("Eligibility", "Fit with funding opportunity remit, eligibility, scope, duration and budget limits is evidenced", "mandatory"),
    ("Clinical Validation", "Study design, methodology, sample size, endpoints, sites/settings and evidence-generation rationale are described", "mandatory"),
    ("Health Economics", "Health economics perspective, comparator, outcomes, resource use, modelling and value plan are described", "required_if_applicable"),
    ("Patient and Public Involvement / Working with People and Communities", "PPIE work, named PPI lead or contributors, future involvement and payment/support are described", "mandatory"),
    ("Research Inclusion", "Underserved groups, accessibility, sex/gender, exclusion criteria, inclusion costs and dissemination are addressed", "mandatory"),
    ("Project Management", "Work packages, milestones, timeline/Gantt, governance, risks and contingencies are included", "mandatory"),
    ("Budget and Finance", "Detailed budget evidence includes cost categories, AcoRD, SoECAT if applicable, current rates, cost justification and scheme caps", "mandatory"),
    ("Uploads", "Required uploads include Gantt/project management plan and references; call-specific uploads are checked", "mandatory"),
    ("Acknowledgement and Conflicts", "AI-use declaration and conflicts declaration are completed", "mandatory"),
    ("Similarity / Novelty / Prior Work", "Novelty, prior work, market/adoption context and related evidence are discussed", "recommended"),
]

EXCLUDED_GUIDANCE_PATTERNS = re.compile(
    r"click invite|fill in (?:the )?name|email address|save draft|submit|use this guidance|awards management system|"
    r"account|profile|on-screen|button|automatically pull|registered|contact the relevant|visit the",
    re.I,
)

AREA_HINTS = [
    ("Budget and Finance", r"budget|cost|AcoRD|SoECAT|rate|cap|finance|treatment cost|support cost"),
    ("Uploads", r"upload|attachment|flow diagram|logic model|gantt|references|flexible upload"),
    ("Acknowledgement and Conflicts", r"AI|artificial intelligence|conflict|acknowledg"),
    ("Health Economics", r"health economic|economic|comparator|QALY|EQ-5D|resource use|cost-effectiveness|budget impact"),
    ("Patient and Public Involvement / Working with People and Communities", r"PPI|PPIE|people and communities|public contributor"),
    ("Research Inclusion", r"inclusion|sex|gender|underserved|accessib|inequal|diversity"),
    ("Project Management", r"project management|gantt|milestone|work package|risk"),
    ("Clinical Validation", r"clinical|validation|sample|endpoint|design|method|ethics|regulatory"),
    ("Eligibility", r"eligib|remit|scope|duration limit|budget limit|out of scope"),
]


def _make_requirement(prefix: str, index: int, source: str, area: str, text: str, status: str, section: str = "Curated baseline") -> Requirement:
    return Requirement(
        requirement_id=f"{prefix}-{index:03d}",
        source=source,  # type: ignore[arg-type]
        source_section=section,
        checklist_area=area,
        requirement_text=text,
        mandatory_status=status,
        evidence_needed_from_application=f"Relevant application evidence for: {text}",
        overrides_general_guidance=(source == "specific_call"),
    )


def canonical_requirements_for_source(source: str, prefix: str = "REQ") -> list[Requirement]:
    if source == "nihr_domestic":
        rows = NIHR_DOMESTIC_BASELINE
    elif source == "rss_playbook":
        rows = RSS_PDA_BASELINE
    elif source == "derived_reviewer_check":
        rows = DERIVED_REQUIREMENTS
    else:
        rows = []
    return [_make_requirement(prefix, i + 1, source, area, text, status) for i, (area, text, status) in enumerate(rows)]


def classify_area(text: str) -> str:
    for area, pattern in AREA_HINTS:
        if re.search(pattern, text, re.I):
            return area
    return "Application Details"


def mandatory_status_for(text: str, source: str = "programme_guidance") -> str:
    lower = text.lower()
    if any(term in lower for term in ["if specified", "if applicable", "where applicable", "where relevant"]):
        return "required_if_applicable"
    if any(term in lower for term in ["flow diagram", "logic model", "flexible upload"]):
        return "mandatory" if source == "specific_call" and re.search(r"must|required|mandatory", lower) else "required_if_applicable"
    if re.search(r"\b(must|required|mandatory|need to|needs to|shall)\b", lower):
        return "mandatory"
    return "recommended"


def parse_specific_call_guidance(text: str, prefix: str = "CALL") -> list[Requirement]:
    """Extract only specific-call constraints that can override baseline guidance."""
    requirements: list[Requirement] = []
    patterns = [
        ("Eligibility", r"(?:eligible|eligibility|remit|scope|out of scope|must not|excluded?).{0,220}"),
        ("Eligibility", r"(?:duration limit|maximum duration|up to \d+ months?|\d+[- ]month).{0,160}"),
        ("Budget and Finance", r"(?:budget cap|maximum budget|funding limit|up to £?[\d,.]+|cost limit).{0,180}"),
        ("Uploads", r"(?:must|required|mandatory).{0,80}(?:upload|flow diagram|logic model|references|gantt|appendix|attachment).{0,180}"),
        ("Clinical Validation", r"(?:assessment criteria|will be assessed|review criteria).{0,220}"),
    ]
    seen: set[str] = set()
    for area, pattern in patterns:
        for match in re.finditer(pattern, text, re.I | re.S):
            clean = re.sub(r"\s+", " ", match.group(0)).strip(" .;:")
            if len(clean) < 20 or EXCLUDED_GUIDANCE_PATTERNS.search(clean):
                continue
            key = clean.lower()[:160]
            if key in seen:
                continue
            seen.add(key)
            requirements.append(_make_requirement(prefix, len(requirements) + 1, "specific_call", area, clean, mandatory_status_for(clean, "specific_call"), "Specific call guidance"))
    return requirements


def parse_guidance_text(text: str, source: str, prefix: str = "REQ") -> list[Requirement]:
    """Return curated baseline requirements or controlled call-specific requirements."""
    if source in {"nihr_domestic", "rss_playbook", "derived_reviewer_check"}:
        return canonical_requirements_for_source(source, prefix)
    if source == "specific_call":
        return parse_specific_call_guidance(text, prefix)

    # Optional programme guidance: only extract clearly reviewer-checkable constraints.
    requirements: list[Requirement] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        clean = re.sub(r"\s+", " ", sentence).strip(" -•\t.;")
        if len(clean) < 30 or len(clean) > 260 or EXCLUDED_GUIDANCE_PATTERNS.search(clean):
            continue
        if not re.search(r"\b(application|proposal|study|budget|PPI|PPIE|inclusion|method|upload|must|required|should include|needs to include)\b", clean, re.I):
            continue
        area = classify_area(clean)
        requirements.append(_make_requirement(prefix, len(requirements) + 1, source, area, clean, mandatory_status_for(clean, source), "Programme guidance"))
        if len(requirements) >= 25:
            break
    return requirements


def derived_reviewer_requirements(start_index: int = 1) -> list[Requirement]:
    return [
        _make_requirement("DRV", start_index + i, "derived_reviewer_check", area, text, status, "Derived RSS reviewer checks")
        for i, (area, text, status) in enumerate(DERIVED_REQUIREMENTS)
    ]


def merge_requirements_with_specific_override(baseline: Iterable[Requirement], specific: Iterable[Requirement]) -> list[Requirement]:
    specific_list = list(specific)
    baseline_list = list(baseline)
    override_areas = {req.checklist_area for req in specific_list if req.overrides_general_guidance or req.source == "specific_call"}
    return specific_list + [req for req in baseline_list if req.checklist_area not in override_areas]


def ensure_area_coverage(requirements: list[Requirement]) -> list[Requirement]:
    existing = {req.checklist_area for req in requirements}
    additions = [req for req in derived_reviewer_requirements(len(requirements) + 1) if req.checklist_area not in existing]
    return requirements + additions
