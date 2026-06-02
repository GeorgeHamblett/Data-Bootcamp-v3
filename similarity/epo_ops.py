"""EPO Open Patent Services integration."""
from __future__ import annotations

import base64
from settings import Settings, is_missing_credential


def _token(settings: Settings) -> str:
    import requests
    creds = f"{settings.epo_ops_consumer_key}:{settings.epo_ops_consumer_secret}".encode()
    headers = {"Authorization": "Basic " + base64.b64encode(creds).decode(), "Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(settings.epo_ops_auth_url, data="grant_type=client_credentials", headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()["access_token"]


def search_epo(query: str, settings: Settings) -> dict:
    import requests
    if is_missing_credential(settings.epo_ops_consumer_key) or is_missing_credential(settings.epo_ops_consumer_secret):
        return {"source": "EPO OPS", "status": "not_run", "matches_found": 0, "top_match": "EPO OPS credentials missing", "score": 0.0, "risk": "NONE", "why_relevant": "Live EPO search not run because credentials are missing.", "link_or_id": ""}
    token = _token(settings)
    url = f"{settings.epo_ops_base_url}/rest-services/published-data/search/biblio"
    response = requests.get(url, params={"q": query, "Range": "1-5"}, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    response.raise_for_status()
    text = response.text
    return {"source": "EPO OPS", "status": "success", "matches_found": 1 if text else 0, "top_match": "Patent bibliographic result", "raw": text[:1000], "link_or_id": url}
