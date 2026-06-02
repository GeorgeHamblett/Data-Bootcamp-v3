"""Build privacy-preserving external similarity queries from generic concepts."""
from __future__ import annotations

import re
from schemas import ApplicationFacts, NOT_EXPLICITLY_STATED, SimilarityQuery

MAX_QUERY_TERMS = 8
MAX_TERM_CHARS = 60

GENERIC_DOCUMENT_TERMS = {
    "uploaded", "upload", "file", "document", "docx", "pdf", "txt", "training", "dummy",
    "application", "plain", "english", "plain english", "summary", "gantt", "chart", "appendix", "form", "section",
    "background", "methodology", "project", "research", "study", "objective", "aim", "funding",
    "proposal", "applicant", "partners", "partner", "draft", "report", "template", "playbook", "guidance", "work", "package",
    "task", "month", "milestones", "milestone", "recruitment", "retention", "fidelity", "interviews",
    "for training use only", "fictional example application", "training use only", "many people do", "falls can seriously", "milestones month",
}

NOISE_PHRASES = [
    "for training use only", "fictional example application", "training use only", "dummy application",
    "this project will", "many people do", "falls can seriously", "milestones month",
]
GENERIC_ACRONYMS = {"SUS", "PPI", "PPIE", "NHS", "NIHR", "QALY", "EQ-5D", "EQ-5D-5L"}

PREFERRED_PHRASES = [
    r"movement quality assessment", r"falls prevention", r"older adults", r"wearable digital therapeutic",
    r"NHS community rehabilitation", r"balance rehabilitation", r"mobility rehabilitation", r"digital therapeutic",
    r"community rehabilitation", r"AI-enabled wearable", r"wearable sensor", r"atrial fibrillation detection",
]


def normalise(term: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 +#\-/]", " ", term.lower())).strip()


def is_generic_term(term: str) -> bool:
    cleaned = normalise(term)
    if not cleaned or len(cleaned) < 3:
        return True
    if cleaned in GENERIC_DOCUMENT_TERMS:
        return True
    if cleaned.upper() in GENERIC_ACRONYMS:
        return True
    if any(noise in cleaned for noise in NOISE_PHRASES):
        return True
    words = cleaned.split()
    return all(word in GENERIC_DOCUMENT_TERMS for word in words)


def _clean(term: str) -> str:
    cleaned = re.sub(r"FOR\s+TRAINING\s+USE\s+ONLY|FICTIONAL\s+EXAMPLE\s+APPLICATION|DUMMY\s+APPLICATION", " ", term, flags=re.I)
    cleaned = re.sub(r"^(?:this project will|this proposal will|we will)\b", " ", cleaned, flags=re.I)
    cleaned = cleaned.replace("/", " / ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .;:,\n\t")
    return cleaned[:MAX_TERM_CHARS].strip(" ,;:-/")


def _sentence_like(value: str) -> bool:
    return bool(re.search(r"[.!?]", value) or len(value.split()) > 6 or re.search(r"\b(?:will|designed to|participants? aged|include|includes|across)\b", value, re.I))


def _dedupe_add(candidates: list[str], value: str) -> None:
    value = _clean(value)
    key = normalise(value)
    if not value or value == NOT_EXPLICITLY_STATED or is_generic_term(value):
        return
    if key in {"ai-enabled", "enabled wearable digital therapeutic"} or key.startswith("enabled "):
        return
    if len(value) > MAX_TERM_CHARS or len(value.split()) > 5:
        return
    for idx, existing in enumerate(list(candidates)):
        existing_key = normalise(existing)
        if key == existing_key or (key in existing_key and len(key.split()) > 1):
            return
        if existing_key in key and len(existing_key.split()) > 1:
            candidates[idx] = value
            return
    candidates.append(value)


def _concepts_from_value(value: str) -> list[str]:
    value = _clean(value)
    if not value or value == NOT_EXPLICITLY_STATED:
        return []
    concepts: list[str] = []
    # Product/acronym-style names are allowed if concise.
    if not _sentence_like(value):
        _dedupe_add(concepts, value)
    for phrase in PREFERRED_PHRASES:
        m = re.search(phrase, value, re.I)
        if m:
            _dedupe_add(concepts, m.group(0))
    for pattern in [
        r"\b[A-Z][A-Z0-9-]{2,10}\b",
        r"\b[A-Z][A-Za-z0-9-]{3,20}\b",
        r"\b(?:falls? prevention|balance rehabilitation|movement quality assessment|older adults|wearable digital therapeutic|digital therapeutic|community rehabilitation)\b",
        r"\b(?:[a-z]+\s+){0,3}(?:platform|engine|sensor|device|therapeutic|rehabilitation)\b",
    ]:
        for m in re.finditer(pattern, value):
            _dedupe_add(concepts, m.group(0))
    return concepts


def _short_concepts_from_text(snippet: str) -> list[str]:
    snippet = _clean(snippet[:1500])
    concepts: list[str] = []
    for phrase in PREFERRED_PHRASES:
        for m in re.finditer(phrase, snippet, re.I):
            _dedupe_add(concepts, m.group(0))
    for m in re.finditer(r"\b[A-Z][A-Za-z0-9-]{3,20}\b|\b[A-Z][A-Z0-9-]{2,10}\b", snippet):
        _dedupe_add(concepts, m.group(0))
    return concepts[:5]


def _cap_terms(primary: list[str], secondary: list[str]) -> tuple[list[str], list[str]]:
    capped_primary: list[str] = []
    capped_secondary: list[str] = []
    seen: set[str] = set()
    for target, terms in [(capped_primary, primary), (capped_secondary, secondary)]:
        for term in terms:
            key = normalise(term)
            if key and key not in seen and not is_generic_term(term) and len(term) <= MAX_TERM_CHARS and len(term.split()) <= 5:
                target.append(term)
                seen.add(key)
            if len(capped_primary) + len(capped_secondary) >= MAX_QUERY_TERMS:
                return capped_primary, capped_secondary
    return capped_primary, capped_secondary


def build_similarity_query(facts: ApplicationFacts, snippets: list[str] | None = None) -> SimilarityQuery:
    primary: list[str] = []
    secondary: list[str] = []
    for field in ["product_or_intervention", "acronym_or_short_name", "technology_type", "clinical_or_social_care_need", "target_population", "mechanism_of_action"]:
        for concept in _concepts_from_value(str(getattr(facts, field, NOT_EXPLICITLY_STATED))):
            _dedupe_add(primary, concept)
    for field in ["sites_or_setting", "market_or_impact_evidence", "comparator_or_control"]:
        for concept in _concepts_from_value(str(getattr(facts, field, NOT_EXPLICITLY_STATED))):
            _dedupe_add(secondary, concept)
    # Endpoints are weak context; include only non-generic, distinctive terms if room remains.
    for endpoint in facts.endpoints:
        if normalise(endpoint) not in {"recruitment", "retention", "fidelity", "interviews", "sus"}:
            for concept in _concepts_from_value(endpoint):
                _dedupe_add(secondary, concept)
    for snippet in snippets or []:
        for phrase in _short_concepts_from_text(snippet):
            _dedupe_add(secondary, phrase)
    primary, secondary = _cap_terms(primary, secondary)
    terms = primary + secondary
    query = " AND ".join(f'"{t}"' if " " in t else t for t in terms) if len(terms) >= 2 else ""
    reasoning = ["Selected short noun-phrase concepts only; full sentences, training labels, duplicate and generic terms are excluded."]
    if len(terms) < 2:
        reasoning.append("At least two meaningful concepts are required before live API searching.")
    return SimilarityQuery(primary_terms=primary, secondary_terms=secondary, excluded_terms=sorted(GENERIC_DOCUMENT_TERMS), query_string=query, extraction_reasoning=reasoning)
