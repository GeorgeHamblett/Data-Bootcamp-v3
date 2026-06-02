"""EPO Open Patent Services client."""
from __future__ import annotations

from settings import Settings


def _token(settings: Settings) -> str:
    import requests
    from requests.auth import HTTPBasicAuth
    response = requests.post(settings.epo_ops_auth_url, data={"grant_type": "client_credentials"}, auth=HTTPBasicAuth(settings.epo_ops_consumer_key, settings.epo_ops_consumer_secret), timeout=20)
    response.raise_for_status()
    return response.json()["access_token"]


def search_epo(query: str, settings: Settings) -> list[dict]:
    if not settings.epo_credentials_available:
        raise RuntimeError("EPO OPS credentials are missing")
    token = _token(settings)
    url = f"{settings.epo_ops_base_url}/rest-services/published-data/search"
    import requests
    response = requests.get(url, params={"q": query, "Range": "1-5"}, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data.get("ops:world-patent-data", {}).get("ops:biblio-search", {}).get("ops:search-result", {}).get("exchange-documents", []) or []
