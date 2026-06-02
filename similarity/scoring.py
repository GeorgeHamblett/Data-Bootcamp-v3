"""Cautious similarity scoring utilities."""
from __future__ import annotations

from schemas import SimilarityResult
from similarity.query_builder import is_generic_term


def score_metadata(query_terms: list[str], title: str, abstract: str = "") -> tuple[float, str, list[str], str]:
    haystack = f"{title} {abstract}".lower()
    matched = [t for t in query_terms if t.lower() in haystack and not is_generic_term(t)]
    if not matched:
        return 0.0, "NONE", [], "No meaningful overlap in returned metadata."
    if len(matched) == 1:
        return 0.10, "LOW", matched, "One meaningful concept overlaps; potentially related but weak and requires human review only if context warrants."
    if len(matched) == 2:
        return 0.45, "MEDIUM", matched, "Two meaningful concepts overlap; potentially related and should be reviewed."
    return 0.78, "HIGH", matched, "Three or more strong concepts overlap; potentially related and requires human review."


def result_from_metadata(source: str, query_terms: list[str], records: list[dict]) -> SimilarityResult:
    if not records:
        return SimilarityResult(source, "success", query_terms, 0, "None", 0.0, "NONE", "No potentially related records returned.", "")
    top = records[0]
    title = str(top.get("title") or top.get("name") or "Untitled result")
    abstract = str(top.get("abstract") or top.get("description") or "")
    score, risk, matched, why = score_metadata(query_terms, title, abstract)
    return SimilarityResult(source, "success", query_terms, len(records), title, score, risk, why, str(top.get("link") or top.get("id") or ""))
