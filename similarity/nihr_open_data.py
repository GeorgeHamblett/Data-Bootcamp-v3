"""NIHR Open Data integration."""
from __future__ import annotations

from typing import Any

from settings import Settings, is_missing_credential


def _result(candidates: list[dict[str, Any]], searched_terms: list[str], top: dict[str, Any], url: str) -> dict[str, Any]:
    top_match = top.get("title") or top.get("project_title") or top.get("acronym") or top.get("recordid") or ""
    return {
        "source": "NIHR Open Data",
        "status": "success",
        "matches_found": len(candidates),
        "top_match": top_match,
        "searched_term": top.get("searched_term", "") if top else (searched_terms[-1] if searched_terms else ""),
        "searched_terms": searched_terms,
        "raw": top,
        "raw_candidates": candidates,
        "link_or_id": top.get("id") or top.get("recordid") or top.get("project_id") or top.get("funding_and_awards_link") or url,
    }


def search_nihr_open_data(query: str | list[str], settings: Settings) -> dict[str, Any]:
    import requests

    url = f"{settings.nihr_open_data_base_url}/catalog/datasets/{settings.nihr_open_data_dataset_id}/records"
    headers = {}
    if not is_missing_credential(settings.nihr_open_data_api_key):
        headers["apikey"] = settings.nihr_open_data_api_key

    terms = [str(term) for term in query if str(term).strip()] if isinstance(query, list) else [str(query)]
    searched_terms: list[str] = []
    candidates: list[dict[str, Any]] = []
    for term in terms:
        searched_terms.append(term)
        response = requests.get(url, params={"limit": 5, "search": term}, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", []) if isinstance(data, dict) and isinstance(data.get("results", []), list) else []
        for result in results[:5]:
            if isinstance(result, dict):
                candidates.append({**result, "searched_term": term})

    top = candidates[0] if candidates else {}
    return _result(candidates, searched_terms, top, url)
