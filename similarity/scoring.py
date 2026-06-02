"""Cautious similarity scoring utilities."""
from __future__ import annotations

from similarity.query_builder import is_generic_term


def matched_concepts(terms: list[str], title: str, abstract: str = "") -> list[str]:
    haystack = f"{title} {abstract}".lower()
    matches = []
    for term in terms:
        if not is_generic_term(term) and term.lower() in haystack:
            matches.append(term)
    return matches


def score_result(terms: list[str], title: str, abstract: str = "", product_or_acronym: str = "") -> dict:
    matches = matched_concepts(terms, title, abstract)
    if not matches:
        return {"score": 0.0, "risk": "NONE", "matched_concepts": []}
    if len(matches) == 1:
        return {"score": 0.10, "risk": "LOW", "matched_concepts": matches}
    product_match = bool(product_or_acronym and product_or_acronym.lower() in [m.lower() for m in matches])
    if product_match and len(matches) >= 2 or len(matches) >= 3:
        return {"score": min(0.95, 0.30 * len(matches)), "risk": "HIGH", "matched_concepts": matches}
    return {"score": min(0.65, 0.20 * len(matches)), "risk": "MEDIUM", "matched_concepts": matches}
