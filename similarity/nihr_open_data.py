"""NIHR Open Data integration."""
from __future__ import annotations

from settings import Settings, is_missing_credential


def search_nihr_open_data(query: str, settings: Settings) -> dict:
    import requests
    url = f"{settings.nihr_open_data_base_url}/catalog/datasets/{settings.nihr_open_data_dataset_id}/records"
    params = {"limit": 5, "search": query}
    headers = {}
    if not is_missing_credential(settings.nihr_open_data_api_key):
        headers["apikey"] = settings.nihr_open_data_api_key
    response = requests.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    top = results[0] if results else {}
    top_match = top.get("title") or top.get("project_title") or top.get("recordid") or ""
    return {"source": "NIHR Open Data", "status": "success", "matches_found": len(results), "top_match": top_match, "raw": top, "link_or_id": top.get("id") or top.get("recordid") or url}
