"""Extract structured facts from application documents only."""
from __future__ import annotations

import re
from collections.abc import Iterable

from schemas import ApplicationFacts, Evidence, NOT_EXPLICITLY_STATED

FIELD_PATTERNS = {
    "project_title": [r"project title\s*[:\-]\s*(.+)", r"title\s*[:\-]\s*(.+)"],
    "application_claimed_call": [r"(?:funding call|call|programme)\s*[:\-]\s*(.+)"],
    "product_or_intervention": [r"(?:intervention|product|innovation|technology)\s*[:\-]\s*(.+)"],
    "acronym_or_short_name": [r"(?:acronym|short name)\s*[:\-]\s*(.+)"],
    "applicant_or_lead": [r"(?:lead applicant|chief investigator|applicant|lead)\s*[:\-]\s*(.+)"],
    "contracting_organisation": [r"contracting organi[sz]ation\s*[:\-]\s*(.+)"],
    "target_population": [r"target population\s*[:\-]\s*(.+)", r"population\s*[:\-]\s*(.+)"],
    "clinical_or_social_care_need": [r"(?:clinical need|social care need|unmet need|need)\s*[:\-]\s*(.+)"],
    "technology_type": [r"technology type\s*[:\-]\s*(.+)"],
    "study_design": [r"study design\s*[:\-]\s*(.+)"],
    "methodology": [r"methodology\s*[:\-]\s*(.+)", r"methods?\s*[:\-]\s*(.+)"],
    "sample_size": [r"sample size\s*[:\-]\s*(.+)", r"n\s*=\s*([0-9][^\n\r]*)"],
    "sites_or_setting": [r"(?:sites?|setting)\s*[:\-]\s*(.+)"],
    "duration_months": [r"duration\s*[:\-]\s*(.+?months?)", r"([0-9]{1,2})\s*months?"],
    "regulatory_plan": [r"regulatory(?: plan)?\s*[:\-]\s*(.+)"],
    "health_economics_plan": [r"health economics?\s*[:\-]\s*(.+)", r"economic evaluation\s*[:\-]\s*(.+)"],
    "ppie_plan": [r"(?:PPIE|PPI|patient and public involvement|working with people and communities)\s*[:\-]\s*(.+)"],
    "research_inclusion_plan": [r"(?:research inclusion|equality|diversity|inclusion)\s*[:\-]\s*(.+)"],
    "project_management_plan": [r"(?:project management|gantt|milestones?)\s*[:\-]\s*(.+)"],
    "finance_or_budget_evidence": [r"(?:budget|finance|costs?)\s*[:\-]\s*(.+)"],
    "references_detected": [r"references?\s*[:\-]\s*(.+)", r"bibliography\s*[:\-]\s*(.+)"],
    "ai_use_declaration": [r"(?:AI use|artificial intelligence|generative AI)\s*[:\-]\s*(.+)"],
    "conflicts_declaration": [r"conflicts?\s*[:\-]\s*(.+)"],
    "market_or_impact_evidence": [r"(?:market|impact|adoption)\s*[:\-]\s*(.+)"],
    "next_stage_plan": [r"next stage\s*[:\-]\s*(.+)"],
}

LIST_PATTERNS = {
    "partners": r"(?:partners?|collaborators?)\s*[:\-]\s*(.+)",
    "work_packages": r"(?:work packages?|WP\d+)\s*[:\-]\s*(.+)",
    "milestones": r"milestones?\s*[:\-]\s*(.+)",
    "endpoints": r"(?:endpoints?|outcomes?)\s*[:\-]\s*(.+)",
}


def _clip(value: str, limit: int = 220) -> str:
    return re.sub(r"\s+", " ", value.strip())[:limit].strip(" ;,")


def _first_match(text: str, patterns: list[str]) -> tuple[str, str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            value = _clip(match.group(1))
            if value:
                return value, _clip(match.group(0), 260)
    return None


def _evidence(source: str, field: str, quote: str) -> Evidence:
    return Evidence(source, field, quote, f"Supports extracted field: {field}.")


def _find_trl(text: str) -> tuple[str, str, str] | None:
    progression = re.search(r"TRL\s*([0-9](?:\s*-\s*[0-9])?)\s*(?:to|→|-)\s*TRL?\s*([0-9](?:\s*-\s*[0-9])?)", text, re.I)
    if progression:
        quote = _clip(progression.group(0))
        return f"TRL {progression.group(1)}", f"TRL {progression.group(2)}", quote
    current = re.search(r"current\s+TRL\s*[:\-]?\s*([0-9](?:\s*-\s*[0-9])?)", text, re.I)
    target = re.search(r"target\s+TRL\s*[:\-]?\s*([0-9](?:\s*-\s*[0-9])?)", text, re.I)
    if current or target:
        quote = _clip("; ".join(m.group(0) for m in (current, target) if m))
        return f"TRL {current.group(1)}" if current else NOT_EXPLICITLY_STATED, f"TRL {target.group(1)}" if target else NOT_EXPLICITLY_STATED, quote
    return None


def extract_application_facts(documents: list[dict[str, str]]) -> ApplicationFacts:
    """Extract facts from supplied application docs; filenames alone are ignored."""
    facts = ApplicationFacts()
    for doc in documents:
        name = doc.get("name", "application document")
        text = doc.get("text", "")
        if not text.strip():
            continue
        for field, patterns in FIELD_PATTERNS.items():
            if getattr(facts, field) != NOT_EXPLICITLY_STATED:
                continue
            found = _first_match(text, patterns)
            if found:
                value, quote = found
                setattr(facts, field, value)
                facts.evidence.append(_evidence(name, field, quote))
        for field, pattern in LIST_PATTERNS.items():
            current = getattr(facts, field)
            if current:
                continue
            match = re.search(pattern, text, re.I | re.M)
            if match:
                values = [_clip(v) for v in re.split(r"[,;\n]", match.group(1)) if _clip(v)]
                setattr(facts, field, values[:12])
                facts.evidence.append(_evidence(name, field, _clip(match.group(0), 260)))
        trl = _find_trl(text)
        if trl and facts.trl_evidence == NOT_EXPLICITLY_STATED:
            facts.current_trl_or_stage, facts.target_trl_or_stage, facts.trl_evidence = trl
            facts.evidence.append(_evidence(name, "trl_evidence", trl[2]))
        uploads: list[str] = []
        for term in ["Gantt", "SoECAT", "AcoRD", "references", "flow diagram", "CV", "letters of support"]:
            if re.search(rf"\b{re.escape(term)}\b", text, re.I):
                uploads.append(term)
        facts.uploads_detected.extend(u for u in uploads if u not in facts.uploads_detected)
    _detect_contradictions(facts)
    return facts


def _detect_contradictions(facts: ApplicationFacts) -> None:
    # TRL progression is intentionally not a contradiction. Only incompatible current claims are flagged by parser users.
    if facts.current_trl_or_stage != NOT_EXPLICITLY_STATED and facts.target_trl_or_stage != NOT_EXPLICITLY_STATED:
        return
