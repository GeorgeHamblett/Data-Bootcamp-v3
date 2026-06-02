"""Rule-assisted parser for guidance requirements."""
from __future__ import annotations

import re
from collections.abc import Iterable

from schemas import CHECKLIST_AREAS, Requirement

KEYWORD_AREAS = [
    ("Budget and Finance", ["budget", "finance", "cost", "costing", "AcoRD", "SoECAT", "rates", "cap", "justification"]),
    ("Uploads", ["upload", "appendix", "gantt", "flow diagram", "references", "supporting document"]),
    ("Acknowledgement and Conflicts", ["artificial intelligence", "AI", "conflict", "acknowledgement"]),
    ("Patient and Public Involvement / Working with People and Communities", ["PPI", "PPIE", "working with people", "communities", "patient and public"]),
    ("Research Inclusion", ["inclusion", "equality", "diversity", "underserved"]),
    ("Health Economics", ["health economics", "economic", "comparator", "cost-effectiveness", "outcome"]),
    ("Project Management", ["project management", "milestone", "gantt", "work package", "risk management"]),
    ("Eligibility", ["eligibility", "remit", "scope", "out of scope", "programme"]),
    ("Clinical Validation", ["clinical", "validation", "sample size", "endpoint", "methodology"]),
]

MANDATORY_RE = re.compile(r"\b(must|required|mandatory|need to|have to|shall)\b", re.I)
IF_APPLICABLE_RE = re.compile(r"\b(if applicable|where applicable|if specified|where relevant)\b", re.I)
RECOMMENDED_RE = re.compile(r"\b(should|recommend|encourage|good practice|consider)\b", re.I)


def classify_area(text: str) -> str:
    haystack = text.lower()
    for area, keywords in KEYWORD_AREAS:
        if any(k.lower() in haystack for k in keywords):
            return area
    return "Application Details"


def mandatory_status(text: str) -> str:
    if IF_APPLICABLE_RE.search(text):
        return "required_if_applicable"
    if MANDATORY_RE.search(text):
        return "mandatory"
    if RECOMMENDED_RE.search(text):
        return "recommended"
    return "optional"


def split_guidance_lines(text: str) -> Iterable[tuple[str, str]]:
    current_section = "General"
    for raw in text.splitlines():
        line = raw.strip(" \t•-*–")
        if not line:
            continue
        if len(line) < 120 and not line.endswith(".") and not MANDATORY_RE.search(line):
            current_section = line[:120]
            continue
        yield current_section, line


def parse_guidance_requirements(text: str, source: str, prefix: str | None = None, overrides: bool = False) -> list[Requirement]:
    requirements: list[Requirement] = []
    seen: set[str] = set()
    prefix = prefix or source
    for section, line in split_guidance_lines(text):
        if len(line) < 20:
            continue
        actionable = MANDATORY_RE.search(line) or IF_APPLICABLE_RE.search(line) or RECOMMENDED_RE.search(line)
        keyword_hit = any(k.lower() in line.lower() for _, keys in KEYWORD_AREAS for k in keys)
        if not actionable and not keyword_hit:
            continue
        compact = re.sub(r"\s+", " ", line)[:280]
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        requirements.append(
            Requirement(
                requirement_id=f"{prefix}_{len(requirements)+1:03d}",
                source=source,
                source_section=section,
                checklist_area=classify_area(compact),
                requirement_text=compact,
                mandatory_status=mandatory_status(compact),
                evidence_needed_from_application=f"Application evidence for: {compact[:120]}",
                overrides_general_guidance=overrides,
            )
        )
        if len(requirements) >= 80:
            break
    return requirements


def derived_reviewer_requirements() -> list[Requirement]:
    rows = [
        ("derived_summary", "Summary Information", "State the project title, claimed call, contracting organisation and concise project summary.", "mandatory"),
        ("derived_team", "Lead Applicant and Research Team", "Identify lead applicant, key partners, roles and relevant expertise.", "mandatory"),
        ("derived_application", "Application Details", "Describe intervention, target population, study design, methodology, duration and setting.", "mandatory"),
        ("derived_eligibility", "Eligibility", "Evidence that the application fits the stated funding opportunity remit and eligibility rules.", "mandatory"),
        ("derived_clinical", "Clinical Validation", "Provide clinical need, endpoints, sample size rationale and validation approach.", "mandatory"),
        ("derived_he", "Health Economics", "Include health economics perspective, comparator, cost-outcome plan and value proposition.", "mandatory"),
        ("derived_ppie", "Patient and Public Involvement / Working with People and Communities", "Describe PPIE activity and name a PPI lead or responsible person.", "mandatory"),
        ("derived_inclusion", "Research Inclusion", "Explain inclusion, equality, diversity and underserved group considerations.", "mandatory"),
        ("derived_pm", "Project Management", "Provide project management evidence such as Gantt chart, work packages, milestones and risk plan.", "mandatory"),
        ("derived_budget", "Budget and Finance", "Check AcoRD, SoECAT if applicable, current rates, cost justification and scheme caps.", "mandatory"),
        ("derived_uploads", "Uploads", "Check required uploads including Gantt/project management plan and references.", "mandatory"),
        ("derived_ack", "Acknowledgement and Conflicts", "Check AI-use declaration and conflicts acknowledgement.", "mandatory"),
        ("derived_similarity", "Similarity / Novelty / Prior Work", "Check novelty, prior work, market or related research evidence.", "recommended"),
    ]
    return [Requirement(rid, "derived_reviewer_check", "Derived RSS reviewer checks", area, text, status, f"Application evidence for {area}.") for rid, area, text, status in rows]


def merge_requirements_with_overrides(baseline: list[Requirement], specific: list[Requirement]) -> list[Requirement]:
    if not specific:
        return baseline
    specific_areas = {r.checklist_area for r in specific if r.overrides_general_guidance or r.source == "specific_call"}
    merged = [r for r in baseline if r.checklist_area not in specific_areas]
    return specific + merged
