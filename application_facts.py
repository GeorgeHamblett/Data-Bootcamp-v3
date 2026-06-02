"""Generic deterministic application fact extraction.

The extractor reads every runtime application/supporting document supplied to it. It
uses reusable patterns for NIHR/RSS applications and deliberately ignores document
labels such as training/example banners. Built-in guidance should never be passed in.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from document_loader import LoadedDocument
from schemas import ApplicationFacts, NOT_EXPLICITLY_STATED

NOISE_PATTERNS = [
    r"FOR\s+TRAINING\s+USE\s+ONLY",
    r"TRAINING\s+USE\s+ONLY",
    r"FICTIONAL\s+EXAMPLE\s+APPLICATION",
    r"DUMMY\s+APPLICATION",
]

FIELD_PATTERNS = {
    "product_or_intervention": [r"(?:product|intervention|innovation|service|device|software|programme|program|model|method)\s*[:\-]\s*(.+)"],
    "acronym_or_short_name": [r"(?:acronym|short\s+name|module)\s*[:\-]\s*(.+)"],
    "target_population": [r"(?:target\s+population|population)\s*[:\-]\s*(.+)"],
    "clinical_or_social_care_need": [r"(?:clinical\s+need|social\s+care\s+need|need|problem)\s*[:\-]\s*(.+)"],
    "technology_type": [r"(?:technology\s+type|intervention\s+type)\s*[:\-]\s*(.+)"],
    "study_design": [r"(?:study\s+design|design)\s*[:\-]\s*(.+)"],
    "sites_or_setting": [r"(?:sites?|setting)\s*[:\-]\s*(.+)"],
    "project_title": [r"(?:project\s+title|application\s+title|title)\s*[:\-]\s*(.+)"],
    "application_claimed_call": [r"(?:funding\s+call|funding\s+opportunity|claimed\s+call|programme)\s*[:\-]\s*(.+)"],
    "applicant_or_lead": [r"(?:lead\s+applicant|chief\s+investigator|principal\s+investigator|applicant\s+lead)\s*[:\-]\s*(.+)"],
    "contracting_organisation": [r"(?:contracting\s+organisation|contracting\s+organization|host\s+organisation|sponsor)\s*[:\-]\s*(.+)"],
    "methodology": [r"(?:methodology|methods?)\s*[:\-]\s*(.+)"],
    "next_stage_plan": [r"(?:next\s+stage|future\s+work|next\s+step)\s*[:\-]\s*(.+)"],
}

PRODUCT_PATTERNS = [
    r"(?:called|known as|named)\s+([A-Z][A-Za-z0-9\-]{2,}(?:\s+[A-Z][A-Za-z0-9\-]{2,}){0,3})",
    r"\b([A-Z][A-Za-z0-9\-]{2,})\s+(?:platform|system|intervention|device|software|programme|program|service|model|method|tool)\b",
    r"\b([A-Z][A-Za-z0-9\-]{2,})\s*,\s+a\s+(?:wearable|digital|software|device|service|programme|program|platform|system)",
]

ACRONYM_PATTERNS = [
    r"\(([A-Z][A-Z0-9\-]{2,10})\)",
    r"(?:abbreviated as|short name|acronym|module called|or)\s+([A-Z][A-Z0-9\-]{2,10})\b",
]

KEYWORDS = {
    "population": [r"aged\s+\d+\s+(?:and\s+over|or\s+over|\+)", r"older adults?", r"children with", r"patients with", r"adults with", r"service users with", r"people with"],
    "need": [r"unmet need", r"clinical need", r"social care problem", r"burden", r"pressure", r"reduced independence", r"rehabilitation", r"prevention", r"mobility", r"balance"],
    "technology": [r"AI-enabled", r"wearable", r"digital therapeutic", r"software", r"device", r"platform", r"algorithm", r"model", r"programme", r"service", r"sensor"],
    "study_design": [r"randomi[sz]ed", r"two-arm", r"feasibility", r"pilot", r"mixed-methods", r"observational", r"comparative", r"trial", r"real-world"],
    "setting": [r"NHS", r"community", r"primary care", r"secondary care", r"social care", r"Trusts?", r"sites?", r"teams?", r"clinics?"],
    "regulatory": [r"UKCA", r"DTAC", r"ISO\s*\d+", r"IEC\s*\d+", r"MHRA", r"ethics", r"IRAS", r"medical device", r"regulatory approval", r"UKCA classification"],
    "health_economics": [r"health economist", r"perspective", r"comparator", r"current care", r"usual care", r"EQ-5D", r"HRQoL", r"QALY", r"resource use", r"micro-costing", r"cost-effectiveness", r"budget impact", r"decision-analytic", r"economic model", r"ICER", r"ROI", r"sensitivity", r"scenario", r"value proposition", r"commissioning"],
    "ppie": [r"public contributors?", r"PPIE?", r"working with people and communities", r"co-design", r"carers?", r"lived experience", r"public co-applicant", r"advisory group", r"payment", r"expenses", r"shaped"],
    "inclusion": [r"underserved", r"underrepresented", r"inequalities", r"digital exclusion", r"accessibility", r"interpreters", r"sex", r"gender", r"ethnicity", r"disability", r"caring responsibilities", r"inclusion costs", r"accessible dissemination"],
    "finance": [r"budget section", r"cost justification", r"staff costs", r"equipment", r"travel", r"subsistence", r"PPIE costs", r"inclusion costs", r"AcoRD", r"SoECAT", r"current rates", r"funding rate", r"scheme cap", r"support costs", r"treatment costs", r"cost category"],
}

ENDPOINT_RE = re.compile(
    r"\b(?:Berg Balance Scale|Timed Up and Go|Activities-specific Balance Confidence(?: scale)?|EQ-5D-5L|EQ-5D|SUS|PSSUQ|recruitment|retention|adherence|fidelity|interviews?|primary outcome|secondary outcome|endpoint)\b",
    re.I,
)


def _clean_text(text: str) -> str:
    cleaned = text
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I)
    return cleaned


def _short(value: str, limit: int = 260) -> str:
    return re.sub(r"\s+", " ", value).strip(" .;:\n\t")[:limit].rstrip()


def _sentences(text: str) -> list[str]:
    return [_short(s, 500) for s in re.split(r"(?<=[.!?])\s+|\n+", text) if _short(s, 500)]


def _find_first(text: str, patterns: list[str]) -> tuple[str, str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            value = _short(match.group(1).splitlines()[0])
            if _is_noise(value):
                continue
            return value, _short(match.group(0))
    return None


def _is_noise(value: str) -> bool:
    return any(re.search(p, value, re.I) for p in NOISE_PATTERNS)


def _sentence_with(text: str, patterns: list[str], limit: int = 320) -> str | None:
    for sentence in _sentences(text):
        if _is_noise(sentence):
            continue
        if any(re.search(pattern, sentence, re.I) for pattern in patterns):
            return _short(sentence, limit)
    return None


def _sentences_with(text: str, patterns: list[str], max_items: int = 6, limit: int = 220) -> list[str]:
    results: list[str] = []
    for sentence in _sentences(text):
        if _is_noise(sentence):
            continue
        if any(re.search(pattern, sentence, re.I) for pattern in patterns):
            cleaned = _short(sentence, limit)
            if cleaned and cleaned not in results:
                results.append(cleaned)
        if len(results) >= max_items:
            break
    return results


def _first_matching_product(text: str) -> str | None:
    for pattern in PRODUCT_PATTERNS:
        for match in re.finditer(pattern, text):
            candidate = _short(match.group(1), 80)
            if candidate.lower() in {"training", "fictional", "application"} or _is_noise(candidate):
                continue
            return candidate
    return None


def _first_acronym(text: str) -> str | None:
    for pattern in ACRONYM_PATTERNS:
        for match in re.finditer(pattern, text):
            candidate = match.group(1).strip()
            if candidate in {"NHS", "NIHR", "PPI", "PPIE", "QALY", "UKCA", "DTAC", "IRAS", "ISO", "IEC"}:
                continue
            return candidate
    return None


def _extract_sample_size(text: str) -> str:
    patterns = [
        r"(?:sample size\s*(?:of)?|target(?:\s+sample)?(?:\s+of)?|n\s*=)\s*(?:approximately|about|around)?\s*(\d+)\s*(participants?|people|patients?|service users?)?",
        r"(?:approximately|about|around)\s*(\d+)\s*(participants?|people|patients?|service users?)",
        r"\b(\d+)\s*(participants?|people|patients?|service users?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            unit = match.group(2) if len(match.groups()) > 1 and match.group(2) else "participants"
            return f"{match.group(1)} {unit}"
    return NOT_EXPLICITLY_STATED


def _extract_duration(text: str, work_packages: list[str]) -> str:
    labelled = re.search(r"(?:duration|over|programme|program)\D{0,30}(\d{1,3})\s*months?", text, re.I)
    if labelled:
        return labelled.group(1)
    range_match = re.search(r"months?\s*(\d{1,2})\s*[-–]\s*(\d{1,3})", text, re.I)
    if range_match:
        return range_match.group(2)
    max_month = 0
    for row in work_packages + _sentences_with(text, [r"month\s*\d+", r"months?\s*\d+\s*[-–]\s*\d+"], 30):
        for number in re.findall(r"month\s*(\d{1,3})|months?\s*\d{1,3}\s*[-–]\s*(\d{1,3})", row, re.I):
            vals = [int(v) for v in number if v]
            if vals:
                max_month = max(max_month, *vals)
    return str(max_month) if max_month else NOT_EXPLICITLY_STATED


def _extract_trl(text: str) -> tuple[str, str, str, list[str]]:
    progression = re.search(r"TRL\s*(\d\s*(?:[-–]\s*\d)?)\s*(?:to|→|->|progress(?:es)?\s+to)\s*TRL?\s*(\d\s*(?:[-–]\s*\d)?)", text, re.I)
    if progression:
        return f"TRL {progression.group(1).replace(' ', '')}", f"TRL {progression.group(2).replace(' ', '')}", _short(progression.group(0)), []
    current = re.search(r"current\s+TRL\s*[:\-]?\s*(\d\s*(?:[-–]\s*\d)?)", text, re.I)
    target = re.search(r"target\s+TRL\s*[:\-]?\s*(\d\s*(?:[-–]\s*\d)?)", text, re.I)
    if current or target:
        cur = f"TRL {current.group(1).replace(' ', '')}" if current else NOT_EXPLICITLY_STATED
        tar = f"TRL {target.group(1).replace(' ', '')}" if target else NOT_EXPLICITLY_STATED
        return cur, tar, "; ".join(x for x in [cur, tar] if x != NOT_EXPLICITLY_STATED), []
    trls = re.findall(r"TRL\s*\d\s*(?:[-–]\s*\d)?", text, re.I)
    if trls:
        return _short(trls[0]), _short(trls[1]) if len(trls) > 1 else NOT_EXPLICITLY_STATED, "; ".join(trls[:3]), []
    return NOT_EXPLICITLY_STATED, NOT_EXPLICITLY_STATED, NOT_EXPLICITLY_STATED, []


def _extract_gantt_rows(text: str) -> list[str]:
    rows: list[str] = []
    patterns = [
        r"(?:WP\s*\d+|Work package\s*\d+|Task\s*\d+)[:\-– ]+[^\n]{20,220}",
        r"[^\n]*(?:Month start|start month|Month end|duration|output)[^\n]*",
        r"[^\n]*months?\s*\d{1,2}\s*[-–]\s*\d{1,2}[^\n]*",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            row = _short(match.group(0), 240)
            if row and row not in rows and not _is_noise(row):
                rows.append(row)
    return rows[:30]


def _extract_milestones(text: str) -> list[str]:
    milestones: list[str] = []
    for match in re.finditer(r"Month\s*(\d{1,2})\s*[:\-–]\s*([^\n.]{8,180})", text, re.I):
        value = _short(f"Month {match.group(1)}: {match.group(2)}", 220)
        if value not in milestones:
            milestones.append(value)
    for sentence in _sentences_with(text, [r"milestone", r"deliverable"], 12):
        if sentence not in milestones:
            milestones.append(sentence)
    return milestones[:20]


def _extract_endpoints(text: str) -> list[str]:
    endpoints: list[str] = []
    for match in ENDPOINT_RE.finditer(text):
        value = match.group(0)
        canonical = value if value.isupper() else value.strip()
        if canonical not in endpoints:
            endpoints.append(canonical)
    for sentence in _sentences_with(text, [r"endpoint", r"outcome measure", r"primary outcome", r"secondary outcome"], 8, 220):
        if sentence not in endpoints:
            endpoints.append(sentence)
    return endpoints[:20]


def _actual_budget_sentence(text: str) -> str | None:
    # Exclude pure health-economic wording unless concrete budget/cost categories are also present.
    sentences = _sentences(text)
    for sentence in sentences:
        if any(re.search(p, sentence, re.I) for p in KEYWORDS["finance"]):
            return _short(sentence)
    return None


def _add_evidence(evidence: list[dict[str, str]], field: str, quote: str, docs: list[LoadedDocument]) -> None:
    source = next((doc.name for doc in docs if quote and quote in doc.text), "application/supporting documents")
    evidence.append({"source_document": source, "section_or_context": field, "quote": _short(quote, 220), "why_it_matters": f"Supports {field.replace('_', ' ')}."})


def extract_application_facts(documents: Iterable[LoadedDocument]) -> ApplicationFacts:
    docs = list(documents)
    combined = _clean_text("\n".join(doc.text for doc in docs))
    facts = ApplicationFacts()
    evidence_entries: list[dict[str, str]] = []

    for field, patterns in FIELD_PATTERNS.items():
        found = _find_first(combined, patterns)
        if found:
            value, quote = found
            setattr(facts, field, value)
            _add_evidence(evidence_entries, field, quote, docs)

    product = _first_matching_product(combined)
    if product:
        facts.product_or_intervention = product
        _add_evidence(evidence_entries, "product_or_intervention", product, docs)
    acronym = _first_acronym(combined)
    if acronym:
        facts.acronym_or_short_name = acronym
        _add_evidence(evidence_entries, "acronym_or_short_name", acronym, docs)

    current, target, trl_evidence, contradictions = _extract_trl(combined)
    facts.current_trl_or_stage = current
    facts.target_trl_or_stage = target
    facts.trl_evidence = trl_evidence
    facts.contradictions_or_uncertainties = contradictions

    facts.sample_size = _extract_sample_size(combined)
    facts.work_packages = _extract_gantt_rows(combined)
    facts.milestones = _extract_milestones(combined)
    facts.duration_months = _extract_duration(combined, facts.work_packages)
    facts.endpoints = _extract_endpoints(combined)

    fallback_map = {
        "target_population": KEYWORDS["population"],
        "clinical_or_social_care_need": KEYWORDS["need"],
        "technology_type": KEYWORDS["technology"],
        "study_design": KEYWORDS["study_design"],
        "sites_or_setting": [r"NHS[^.\n]{0,120}(?:setting|service|team|clinic|rehabilitation)", r"(?:sites?|setting)[:\-]", r"community rehabilitation", r"primary care", r"secondary care", r"social care"],
        "regulatory_plan": KEYWORDS["regulatory"],
        "health_economics_plan": KEYWORDS["health_economics"],
        "ppie_plan": KEYWORDS["ppie"],
        "research_inclusion_plan": KEYWORDS["inclusion"],
        "market_or_impact_evidence": [r"novel", r"differentiation", r"market", r"adoption", r"commercial", r"IP", r"commissioning"],
        "next_stage_plan": [r"next stage", r"future", r"later-stage", r"definitive trial", r"scale"],
    }
    for field, patterns in fallback_map.items():
        if getattr(facts, field) == NOT_EXPLICITLY_STATED:
            sentence = _sentence_with(combined, patterns)
            if sentence:
                setattr(facts, field, sentence)
                _add_evidence(evidence_entries, field, sentence, docs)

    comparator = _sentence_with(combined, [r"usual care", r"standard care", r"control arm", r"comparator", r"current care"])
    if comparator:
        facts.comparator_or_control = comparator
        if facts.health_economics_plan == NOT_EXPLICITLY_STATED:
            facts.health_economics_plan = comparator

    if facts.project_management_plan == NOT_EXPLICITLY_STATED:
        pm_bits = []
        if facts.duration_months != NOT_EXPLICITLY_STATED:
            pm_bits.append(f"{facts.duration_months}-month plan")
        if facts.work_packages:
            pm_bits.append("work packages/Gantt rows present")
        if facts.milestones:
            pm_bits.append("milestones present")
        risk = _sentence_with(combined, [r"risk register", r"contingenc", r"governance"])
        if risk:
            pm_bits.append(risk)
        if pm_bits:
            facts.project_management_plan = "; ".join(pm_bits)

    budget = _actual_budget_sentence(combined)
    if budget:
        facts.finance_or_budget_evidence = budget
        _add_evidence(evidence_entries, "finance_or_budget_evidence", budget, docs)
    else:
        facts.finance_or_budget_evidence = NOT_EXPLICITLY_STATED

    facts.partners = _sentences_with(combined, [r"partner", r"collaborator", r"co-applicant"], 8)
    facts.uploads_detected = _sentences_with(combined, [r"upload", r"appendix", r"gantt", r"references", r"flow diagram", r"logic model"], 10)
    refs = _sentence_with(combined, [r"references", r"bibliography"])
    if refs:
        facts.references_detected = refs

    # Only explicit Yes/No or declaration wording counts for AI/conflicts.
    ai = _sentence_with(combined, [r"AI[- ]use declaration", r"generative AI\s*[:\-]\s*(yes|no)", r"artificial intelligence\s*[:\-]\s*(yes|no)"])
    if ai:
        facts.ai_use_declaration = ai
    conflicts = _sentence_with(combined, [r"conflicts?\s*[:\-]\s*(yes|no|none|declared)", r"competing interests?\s*[:\-]\s*(yes|no|none)"])
    if conflicts:
        facts.conflicts_declaration = conflicts

    # Add concise evidence for important inferred fields.
    for field in ["sample_size", "duration_months", "project_management_plan", "trl_evidence"]:
        value = getattr(facts, field)
        if value != NOT_EXPLICITLY_STATED:
            _add_evidence(evidence_entries, field, str(value), docs)

    facts.evidence = evidence_entries
    return facts
