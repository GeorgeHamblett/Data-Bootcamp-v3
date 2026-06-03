"""NIHR Open Data integration."""
from __future__ import annotations

from typing import Any

from settings import Settings, is_missing_credential


def _result(data: dict[str, Any], results: list[dict[str, Any]], top: dict[str, Any], searched_term: str, url: str) -> dict[str, Any]:
    top_match = top.get("title") or top.get("project_title") or top.get("acronym") or top.get("recordid") or ""
    return {
        "source": "NIHR Open Data",
        "status": "success",
        "matches_found": len(results),
        "top_match": top_match,
        "searched_term": searched_term,
        "raw": top,
        "link_or_id": top.get("id") or top.get("recordid") or top.get("project_id") or top.get("funding_and_awards_link") or url,
    }


def search_nihr_open_data(query: str | list[str], settings: Settings) -> dict[str, Any]:
    import requests

    url = f"{settings.nihr_open_data_base_url}/catalog/datasets/{settings.nihr_open_data_dataset_id}/records"
    headers = {}
    if not is_missing_credential(settings.nihr_open_data_api_key):
        headers["apikey"] = settings.nihr_open_data_api_key

    terms = [str(term) for term in query if str(term).strip()] if isinstance(query, list) else [str(query)]
    last_data: dict[str, Any] = {}
    last_term = ""
    for term in terms:
        last_term = term
        response = requests.get(url, params={"limit": 5, "search": term}, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        last_data = data if isinstance(data, dict) else {}
        results = last_data.get("results", []) if isinstance(last_data.get("results", []), list) else []
        if results:
            top = results[0] if isinstance(results[0], dict) else {}
            return _result(last_data, results, top, term, url)

    return _result(last_data, [], {}, last_term, url)
