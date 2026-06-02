"""Lens Scholarly API client."""
from __future__ import annotations


from settings import Settings


def search_lens(query: str, settings: Settings) -> list[dict]:
    import requests
    if not settings.lens_credentials_available:
        raise RuntimeError("Lens API token is missing")
    headers = {"Authorization": f"Bearer {settings.lens_api_token}", "Content-Type": "application/json"}
    payload = {"query": {"query_string": {"query": query}}, "size": 5}
    response = requests.post(settings.lens_api_base_url, json=payload, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data.get("data", []) or data.get("results", []) or []
