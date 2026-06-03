"""EPO Open Patent Services integration with safe CQL query construction."""
from __future__ import annotations

from typing import Any

from settings import Settings, is_missing_credential

EPO_SOURCE = "EPO OPS"
STOP_TERMS = {
    "the", "a", "an", "early", "consistent", "detection", "support",
    "application", "project", "research", "study", "patients", "people",
    "adults", "community", "guidance", "uploaded", "docx", "template",
}


def _base_result(status: str, *, top_match: str = "", why: str = "", safe_terms: list[str] | None = None) -> dict[str, Any]:
    return {
        "source": EPO_SOURCE,
        "status": status,
        "matches_found": 0,
        "top_match": top_match,
        "score": 0.0,
        "risk": "NONE",
        "why_relevant": why or top_match,
        "link_or_id": "",
        "query_terms_used": safe_terms or [],
    }


def _token(settings: Settings) -> str:
    import base64
    import requests

    creds = f"{settings.epo_ops_consumer_key}:{settings.epo_ops_consumer_secret}".encode("utf-8")
    encoded = base64.b64encode(creds).decode("ascii")

    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    response = requests.post(
        settings.epo_ops_auth_url,
        data={"grant_type": "client_credentials"},
        headers=headers,
        timeout=20,
    )

    if response.status_code in {400, 401, 403}:
        raise RuntimeError(f"EPO OPS authentication failed with HTTP {response.status_code}")

    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("EPO OPS authentication response did not include access_token")
    return str(token)


def _is_bad_epo_term(term: str) -> bool:
    t = " ".join(str(term or "").strip().split())
    if not t:
        return True
    if t.lower() in STOP_TERMS:
        return True
    if len(t) < 4 and not t.isupper():
        return True
    if len(t) > 80:
        return True
    if len(t.split()) > 6:
        return True
    # reject obvious truncation like "surgical w"
    if len(t.split()) >= 2 and len(t.split()[-1]) == 1:
        return True
    return False


def _escape_cql(term: str) -> str:
    return str(term).replace('"', " ").strip()


def _terms_from_query(query: str | list[str]) -> list[str]:
    if isinstance(query, str):
        return [part.strip('" ') for part in query.replace(" AND ", "|").replace(" OR ", "|").replace(" and ", "|").replace(" or ", "|").split("|")]
    return list(query or [])


def build_epo_cql_query(terms: list[str] | str) -> tuple[str, list[str]]:
    safe: list[str] = []
    seen: set[str] = set()

    for term in _terms_from_query(terms):
        t = " ".join(str(term or "").strip().split())
        if _is_bad_epo_term(t):
            continue
        key = t.lower()
        if key not in seen:
            seen.add(key)
            safe.append(t)

    # Prefer patent-relevant title/abstract terms only.
    safe = safe[:4]

    if not safe:
        return "", []

    clauses: list[str] = []
    for term in safe:
        term = _escape_cql(term)
        if " " in term or "-" in term:
            clauses.append(f'ta="{term}"')
        else:
            clauses.append(f"ta={term}")

    return " or ".join(clauses), safe


def check_epo_credentials(settings: Settings) -> dict[str, Any]:
    """Request only an OAuth token to verify EPO OPS credentials without exposing secrets."""
    if is_missing_credential(settings.epo_ops_consumer_key) or is_missing_credential(settings.epo_ops_consumer_secret):
        return _base_result("not_run", top_match="EPO OPS credentials missing", why="EPO OPS credentials missing.")
    try:
        _token(settings)
        return {"source": EPO_SOURCE, "status": "success", "message": "EPO OPS authentication succeeded."}
    except Exception as exc:
        return _base_result(
            "error",
            why=f"EPO OPS authentication failed. Check consumer key and secret. Error type: {exc.__class__.__name__}",
        )


def search_epo(query: str | list[str], settings: Settings) -> dict[str, Any]:
    import requests
    import xml.etree.ElementTree as ET

    if is_missing_credential(settings.epo_ops_consumer_key) or is_missing_credential(settings.epo_ops_consumer_secret):
        return _base_result(
            "not_run",
            top_match="EPO OPS credentials missing",
            why="Live EPO search not run because credentials are missing.",
            safe_terms=[],
        )

    terms = _terms_from_query(query)
    cql, safe_terms = build_epo_cql_query(terms)
    if len(safe_terms) < 1 or not cql:
        return _base_result(
            "not_run",
            top_match="Fewer than one safe EPO query term after cleaning.",
            why="EPO search not run because no safe patent-search terms remained.",
            safe_terms=safe_terms,
        )

    try:
        token = _token(settings)
    except Exception as exc:
        return _base_result(
            "error",
            why=f"EPO OPS authentication failed. Check consumer key and secret. Error type: {exc.__class__.__name__}",
            safe_terms=safe_terms,
        )

    service_base = getattr(settings, "epo_ops_service_base_url", "https://ops.epo.org").rstrip("/")
    url = f"{service_base}/rest-services/published-data/search/biblio"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/exchange+xml",
        "X-OPS-Range": "1-5",
    }

    try:
        response = requests.get(
            url,
            params={"q": cql},
            headers=headers,
            timeout=30,
        )
        if response.status_code in {400, 404}:
            # fallback to base search endpoint if biblio constituent path is rejected
            fallback_url = f"{service_base}/rest-services/published-data/search"
            response = requests.get(
                fallback_url,
                params={"q": cql},
                headers=headers,
                timeout=30,
            )

        if response.status_code in {401, 403}:
            return _base_result(
                "error",
                why=f"EPO OPS request rejected with HTTP {response.status_code}. Check app approval, quota/fair-use limits and credentials.",
                safe_terms=safe_terms,
            )

        if response.status_code == 400:
            return _base_result(
                "error",
                why="EPO OPS query rejected. Query URL suppressed.",
                safe_terms=safe_terms,
            )

        response.raise_for_status()
        xml_text = response.text

        root = ET.fromstring(xml_text)
        titles: list[str] = []
        doc_numbers: list[str] = []

        for elem in root.iter():
            tag = elem.tag.lower()
            text = (elem.text or "").strip()
            if not text:
                continue
            if tag.endswith("invention-title") and text not in titles:
                titles.append(text)
            if tag.endswith("doc-number") and text not in doc_numbers:
                doc_numbers.append(text)

        top_title = titles[0] if titles else "Patent bibliographic result"
        top_id = doc_numbers[0] if doc_numbers else ""
        matches = max(len(titles), len(doc_numbers))
        if matches == 0 and xml_text.strip():
            matches = 1

        return {
            "source": EPO_SOURCE,
            "status": "success",
            "matches_found": matches,
            "top_match": top_title,
            "raw": {"titles": titles[:5], "doc_numbers": doc_numbers[:5]},
            "score": 0.0,
            "risk": "NONE",
            "why_relevant": "EPO OPS returned patent metadata; relevance requires scoring and human review.",
            "link_or_id": top_id,
            "query_terms_used": safe_terms,
        }

    except Exception as exc:
        return _base_result(
            "error",
            why=f"EPO OPS live search failed. Query URL suppressed. Error type: {exc.__class__.__name__}",
            safe_terms=safe_terms,
        )
