"""Build privacy-preserving similarity queries from extracted facts."""
from __future__ import annotations

import re
from dataclasses import asdict

from schemas import ApplicationFacts, SimilarityQuery, NOT_EXPLICITLY_STATED

GENERIC_DOCUMENT_TERMS = {
    "uploaded", "upload", "file", "document", "docx", "pdf", "txt", "training", "dummy", "application", "plain", "english", "summary", "gantt", "chart", "appendix", "form", "section", "background", "methodology", "project", "research", "study", "objective", "aim", "funding", "proposal", "applicant", "draft", "report", "template", "playbook", "guidance", "work", "package", "task", "month",
}

FIELDS = [
    "product_or_intervention", "acronym_or_short_name", "clinical_or_social_care_need", "target_population", "technology_type", "sites_or_setting", "endpoints", "market_or_impact_evidence",
]


def _clean(term: str) -> str:
    term = re.sub(r"[^A-Za-z0-9 /+\-]", " ", term)
    return re.sub(r"\s+", " ", term).strip()


def is_generic_term(term: str) -> bool:
    cleaned = _clean(term).lower()
    if not cleaned:
        return True
    words = cleaned.split()
    return cleaned in GENERIC_DOCUMENT_TERMS or all(w in GENERIC_DOCUMENT_TERMS for w in words)


def filter_terms(terms: list[str]) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    excluded: list[str] = []
    for term in terms:
        cleaned = _clean(str(term))
        if not cleaned:
            continue
        if is_generic_term(cleaned):
            excluded.append(cleaned)
            continue
        if cleaned.lower() not in {t.lower() for t in kept}:
            kept.append(cleaned)
    return kept, excluded


def build_similarity_query(facts: ApplicationFacts, snippets: str = "") -> SimilarityQuery:
    raw: list[str] = []
    for field in FIELDS:
        value = getattr(facts, field)
        if isinstance(value, list):
            raw.extend(value)
        elif value and value != NOT_EXPLICITLY_STATED:
            raw.append(value)
    # Extract only short concept-like phrases, not full text.
    for pattern in [r"(?:novel|first|new)\s+([A-Za-z][A-Za-z0-9 \-/]{3,60})", r"for\s+([A-Za-z][A-Za-z0-9 \-/]{3,60})"]:
        for match in re.finditer(pattern, snippets[:3000], re.I):
            raw.append(match.group(1))
    kept, excluded = filter_terms(raw)
    primary = kept[:4]
    secondary = kept[4:10]
    query = " AND ".join(f'"{t}"' if " " in t else t for t in primary[:4])
    reasoning = ["Terms come from extracted application facts, not filenames or full document text."]
    if len(primary) < 2:
        reasoning.append("At least two meaningful concepts are required before live API searching.")
    return SimilarityQuery(primary, secondary, excluded, query, reasoning)


def has_minimum_meaningful_terms(query: SimilarityQuery) -> bool:
    return len(query.primary_terms) >= 2
