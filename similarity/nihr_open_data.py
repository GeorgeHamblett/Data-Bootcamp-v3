"""NIHR Open Data client."""
from __future__ import annotations


from settings import Settings


def search_nihr_open_data(query: str, settings: Settings) -> list[dict]:
    import requests
    url = f"{settings.nihr_open_data_base_url}/catalog/datasets/{settings.nihr_open_data_dataset_id}/records"
    params = {"limit": 5, "search": query}
    headers = {}
    if settings.nihr_open_data_api_key.strip():
        headers["Authorization"] = f"Apikey {settings.nihr_open_data_api_key}"
    response = requests.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data.get("results", [])
