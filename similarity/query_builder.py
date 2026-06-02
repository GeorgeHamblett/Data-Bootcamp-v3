"""Build privacy-preserving external similarity queries from generic concepts."""
from __future__ import annotations

import re
from schemas import ApplicationFacts, NOT_EXPLICITLY_STATED, SimilarityQuery

GENERIC_DOCUMENT_TERMS = {
    "uploaded", "upload", "file", "document", "docx", "pdf", "txt", "training", "dummy",
    "application", "plain", "english", "plain english", "summary", "gantt", "chart", "appendix", "form", "section",
    "background", "methodology", "project", "research", "study", "objective", "aim", "funding",
    "proposal", "applicant", "draft", "report", "template", "playbook", "guidance", "work", "package",
    "task", "month", "for training use only", "fictional example application", "training use only",
}

NOISE_PHRASES = ["for training use only", "fictional example application", "training use only", "dummy application"]


def normalise(term: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 +#\-/]", " ", term.lower())).strip()


def is_generic_term(term: str) -> bool:
    cleaned = normalise(term)
    if not cleaned or len(cleaned) < 3:
        return True
    if cleaned in GENERIC_DOCUMENT_TERMS:
        return True
    if any(noise in cleaned for noise in NOISE_PHRASES):
        return True
    words = cleaned.split()
    return all(word in GENERIC_DOCUMENT_TERMS for word in words)


def _clean(term: str) -> str:
    cleaned = re.sub(r"FOR\s+TRAINING\s+USE\s+ONLY|FICTIONAL\s+EXAMPLE\s+APPLICATION|DUMMY\s+APPLICATION", " ", term, flags=re.I)
    return re.sub(r"\s+", " ", cleaned).strip(" .;:,\n\t")


def _add(candidates: list[str], value: str) -> None:
    value = _clean(value)
    if value and value != NOT_EXPLICITLY_STATED and not is_generic_term(value) and value not in candidates:
        candidates.append(value[:90])


def _short_concepts_from_text(snippet: str) -> list[str]:
    snippet = _clean(snippet)
    concepts: list[str] = []
    for phrase in re.findall(r"\b[A-Z][A-Za-z0-9-]{3,}(?:\s+[a-z]+){0,2}(?:\s+[A-Z][A-Za-z0-9-]{3,})?\b", snippet[:500]):
        phrase = _clean(phrase)
        if not is_generic_term(phrase):
            concepts.append(phrase)
    return concepts[:5]


def build_similarity_query(facts: ApplicationFacts, snippets: list[str] | None = None) -> SimilarityQuery:
    primary: list[str] = []
    secondary: list[str] = []
    excluded: list[str] = sorted(GENERIC_DOCUMENT_TERMS)
    for field in ["product_or_intervention", "acronym_or_short_name", "clinical_or_social_care_need", "target_population", "technology_type", "mechanism_of_action"]:
        _add(primary, str(getattr(facts, field, NOT_EXPLICITLY_STATED)))
    for field in ["sites_or_setting", "market_or_impact_evidence", "comparator_or_control"]:
        _add(secondary, str(getattr(facts, field, NOT_EXPLICITLY_STATED)))
    for endpoint in facts.endpoints:
        _add(secondary, endpoint)
    for snippet in snippets or []:
        for phrase in _short_concepts_from_text(snippet):
            _add(secondary, phrase)
    terms = [t for t in primary + secondary if not is_generic_term(t)]
    query = " AND ".join(f'"{t}"' if " " in t else t for t in terms[:6]) if len(terms) >= 2 else ""
    reasoning = ["Selected short application-specific concepts only; excluded filename/document/training labels."]
    if len(terms) < 2:
        reasoning.append("At least two meaningful concepts are required before live API searching.")
    return SimilarityQuery(primary_terms=primary, secondary_terms=secondary, excluded_terms=excluded, query_string=query, extraction_reasoning=reasoning)
