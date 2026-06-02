"""Similarity service orchestration with strict privacy gates."""
from __future__ import annotations

from schemas import ApplicationFacts
from settings import Settings
from similarity.query_builder import build_similarity_query, normalise, is_generic_term
from similarity.scoring import score_result
from similarity.lens import search_lens
from similarity.epo_ops import search_epo
from similarity.nihr_open_data import search_nihr_open_data


def _not_run(source: str, reason: str, terms: list[str]) -> dict:
    return {"source": source, "status": "not_run", "query_terms_used": terms, "matches_found": 0, "top_match": reason, "score": 0.0, "risk": "NONE", "why_relevant": reason, "link_or_id": ""}


def _mock_result(source: str, terms: list[str]) -> dict:
    return {"source": source, "status": "success", "query_terms_used": terms, "matches_found": 1, "top_match": "Mock potentially related result", "score": 0.2, "risk": "LOW", "why_relevant": "Mock mode explicitly enabled for developer/testing use only; result is simulated.", "link_or_id": "mock"}


def _format_query(terms: list[str]) -> str:
    return " AND ".join(f'"{t}"' if " " in t else t for t in terms)


def _api_terms(source: str, primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    picked: list[str] = []
    pool = primary if source == "EPO OPS" else primary + secondary
    for term in pool:
        if is_generic_term(term):
            continue
        # EPO gets product/acronym/technology only; avoid endpoints/outcome lists.
        if source == "EPO OPS" and any(x in normalise(term) for x in ["eq-5d", "berg", "timed up", "outcome", "recruitment", "retention", "usual care"]):
            continue
        key = normalise(term)
        if key not in seen and len(term) <= 60 and len(term.split()) <= 5:
            picked.append(term)
            seen.add(key)
        if len(picked) >= (5 if source != "EPO OPS" else 4):
            break
    return picked[:5]


def _clean_api_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    return f"API error: {name}; live search failed. Query URL suppressed."


def run_similarity_service(facts: ApplicationFacts, settings: Settings, run_similarity_check: bool = False, mock_mode: bool = False, snippets: list[str] | None = None) -> dict:
    query = build_similarity_query(facts, snippets)
    terms = query.primary_terms + query.secondary_terms
    sources = ["Lens Scholarly", "EPO OPS", "NIHR Open Data"]
    if not run_similarity_check:
        return {"query": query, "results": [_not_run(s, "Similarity check disabled by user.", terms) for s in sources]}
    if query.meaningful_term_count < 2:
        return {"query": query, "results": [_not_run(s, "At least two meaningful application-specific terms are required before live searching.", terms) for s in sources]}
    if mock_mode:
        return {"query": query, "results": [_mock_result(s, terms) for s in sources]}
    if settings.local_only_mode or not settings.allow_external_similarity_queries:
        return {"query": query, "results": [_not_run(s, "Live similarity blocked by LOCAL_ONLY_MODE or ALLOW_EXTERNAL_SIMILARITY_QUERIES=false.", terms) for s in sources]}

    raw_results = []
    for func, source in [(search_lens, "Lens Scholarly"), (search_epo, "EPO OPS"), (search_nihr_open_data, "NIHR Open Data")]:
        api_terms = _api_terms(source, query.primary_terms, query.secondary_terms)
        if len(api_terms) < 2:
            raw_results.append(_not_run(source, "Fewer than two safe source-specific query terms after cleaning.", api_terms))
            continue
        try:
            result = func(_format_query(api_terms), settings)
        except Exception as exc:
            result = {"source": source, "status": "error", "matches_found": 0, "top_match": "", "score": 0.0, "risk": "NONE", "why_relevant": _clean_api_error(exc), "link_or_id": ""}
        title = str(result.get("top_match", ""))
        scored = score_result(api_terms, title, str(result.get("raw", "")), facts.acronym_or_short_name)
        result.update(scored)
        result.setdefault("why_relevant", "Potentially related metadata; requires human review." if scored["risk"] in {"MEDIUM", "HIGH"} else "Low or no relatedness from available metadata.")
        result["query_terms_used"] = api_terms
        raw_results.append(result)
    return {"query": query, "results": raw_results}
