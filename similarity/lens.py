"""Lens Scholarly API integration."""
from __future__ import annotations

from settings import Settings, is_missing_credential


def search_lens(query: str, settings: Settings) -> dict:
    import requests
    if is_missing_credential(settings.lens_api_token):
        return {"source": "Lens Scholarly", "status": "not_run", "matches_found": 0, "top_match": "Lens API token missing", "score": 0.0, "risk": "NONE", "why_relevant": "Live Lens search not run because credentials are missing.", "link_or_id": ""}
    headers = {"Authorization": f"Bearer {settings.lens_api_token}", "Content-Type": "application/json"}
    payload = {"query": query, "size": 5}
    response = requests.post(settings.lens_api_base_url, json=payload, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()
    results = data.get("data", []) or data.get("results", [])
    top = results[0] if results else {}
    title = top.get("title") or top.get("display_name") or ""
    return {"source": "Lens Scholarly", "status": "success", "matches_found": len(results), "top_match": title, "raw": top, "link_or_id": top.get("lens_id") or top.get("external_ids", "")}
