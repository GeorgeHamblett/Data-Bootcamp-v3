"""Similarity orchestration with privacy gates."""
from __future__ import annotations

from schemas import ApplicationFacts, SimilarityResult
from settings import Settings
from similarity.query_builder import build_similarity_query, has_minimum_meaningful_terms
from similarity.scoring import result_from_metadata
from similarity.lens import search_lens
from similarity.epo_ops import search_epo
from similarity.nihr_open_data import search_nihr_open_data

SOURCES = ["Lens Scholarly", "EPO OPS", "NIHR Open Data"]


def _not_run(source: str, terms: list[str], why: str) -> SimilarityResult:
    return SimilarityResult(source, "not_run", terms, 0, "Not run", 0.0, "NONE", why, "")


def _mock_result(source: str, terms: list[str]) -> SimilarityResult:
    return SimilarityResult(source, "success", terms, 1, "Mock potentially related record", 0.2, "LOW", "Mock mode explicitly enabled for developer testing; not a live result.", "mock")


def run_similarity(facts: ApplicationFacts, snippets: str, settings: Settings, run_similarity_check: bool = False, mock_mode: bool = False) -> tuple[dict, list[SimilarityResult]]:
    query = build_similarity_query(facts, snippets)
    terms = query.primary_terms
    if not run_similarity_check:
        return query.__dict__, [_not_run(s, terms, "Similarity check is disabled; no mock or live APIs were called.") for s in SOURCES]
    if not has_minimum_meaningful_terms(query):
        return query.__dict__, [_not_run(s, terms, "At least two meaningful application-specific terms are required before searching.") for s in SOURCES]
    if mock_mode:
        return query.__dict__, [_mock_result(s, terms) for s in SOURCES]
    if settings.local_only_mode or not settings.allow_external_similarity_queries:
        return query.__dict__, [_not_run(s, terms, "LOCAL_ONLY_MODE or ALLOW_EXTERNAL_SIMILARITY_QUERIES blocks live external APIs.") for s in SOURCES]

    results: list[SimilarityResult] = []
    live_calls = [
        ("Lens Scholarly", search_lens, settings.lens_credentials_available),
        ("EPO OPS", search_epo, settings.epo_credentials_available),
        ("NIHR Open Data", search_nihr_open_data, True),
    ]
    for source, func, available in live_calls:
        if not available:
            results.append(_not_run(source, terms, "Required credentials are missing."))
            continue
        try:
            records = func(query.query_string, settings)
            results.append(result_from_metadata(source, terms, records))
        except Exception as exc:
            results.append(SimilarityResult(source, "error", terms, 0, "Error", 0.0, "NONE", f"Live API error: {exc}", ""))
    return query.__dict__, results
