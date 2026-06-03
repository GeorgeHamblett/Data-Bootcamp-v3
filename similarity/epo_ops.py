"""EPO Open Patent Services integration with safe CQL query construction."""
from __future__ import annotations

import base64
import re
from typing import Any

from settings import Settings, is_missing_credential
from similarity.query_builder import normalise, is_generic_term

EPO_SOURCE = "EPO OPS"
EPO_SEARCH_PATH = "/rest-services/published-data/search/biblio"
EPO_GENERIC_TERMS = {
    "the", "a", "an", "early", "consistent", "adults", "patients", "people",
    "community", "support", "detection", "device", "platform", "system", "study",
    "research", "application", "wounds", "wound",
}


def _safe_result(status: str, message: str, *, error_type: str = "", http_status: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source": EPO_SOURCE,
        "status": status,
        "matches_found": 0,
        "top_match": message,
        "score": 0.0,
        "risk": "NONE",
        "why_relevant": message,
        "link_or_id": "",
    }
    if error_type:
        result["error_type"] = error_type
    if http_status is not None:
        result["http_status"] = http_status
    return result


def _http_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _token(settings: Settings) -> str:
    import requests

    creds = f"{settings.epo_ops_consumer_key}:{settings.epo_ops_consumer_secret}".encode()
    headers = {
        "Authorization": "Basic " + base64.b64encode(creds).decode(),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    response = requests.post(settings.epo_ops_auth_url, data={"grant_type": "client_credentials"}, headers=headers, timeout=20)
    response.raise_for_status()
    return str(response.json()["access_token"])


def _terms_from_query(query: str | list[str]) -> list[str]:
    if isinstance(query, list):
        return [str(term) for term in query]
    quoted = re.findall(r'"([^"]+)"', query)
    remainder = re.sub(r'"[^"]+"', " ", query)
    bare = re.split(r"\s+AND\s+|\s+OR\s+|[,;]", remainder, flags=re.I)
    return quoted + [part.strip() for part in bare if part.strip()]


def _clean_epo_term(term: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 +#\-/]", " ", str(term))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .;:,/-")
    return cleaned


def _is_safe_epo_term(term: str) -> bool:
    cleaned = _clean_epo_term(term)
    key = normalise(cleaned)
    if not cleaned or is_generic_term(cleaned) or key in EPO_GENERIC_TERMS:
        return False
    if len(cleaned) > 60 or len(cleaned.split()) > 5:
        return False
    if re.search(r"\b[a-z]{1,3}$", cleaned) and not re.search(r"\b(?:AI|IP|ECG|NHS)$", cleaned):
        return False
    if all(word in EPO_GENERIC_TERMS for word in key.split()):
        return False
    return True


def build_epo_cql_query(terms: list[str] | str, *, max_terms: int = 4, quote_first: bool = True) -> str:
    """Build a short EPO OPS CQL query from safe patent-relevant terms only."""
    selected: list[str] = []
    seen: set[str] = set()
    for raw in _terms_from_query(terms):
        term = _clean_epo_term(raw)
        key = normalise(term)
        if not _is_safe_epo_term(term) or key in seen:
            continue
        selected.append(term)
        seen.add(key)
        if len(selected) >= max_terms:
            break
    if not selected:
        return ""

    parts: list[str] = []
    for idx, term in enumerate(selected):
        if not quote_first and idx == 0 and re.match(r"^[A-Za-z0-9-]+$", term):
            parts.append(f"ta={term}")
        else:
            escaped = term.replace('"', "")
            parts.append(f'ta="{escaped}"')
    return " or ".join(parts)


def _extract_epo_identifier(text: str) -> str:
    match = re.search(r"\b(?:EP|WO|US)\s?\d{6,}[A-Z0-9]*\b", text)
    return match.group(0).replace(" ", "") if match else "URL suppressed"


def check_epo_credentials(settings: Settings) -> dict[str, Any]:
    """Request only an OAuth token to verify EPO OPS credentials without exposing secrets."""
    if is_missing_credential(settings.epo_ops_consumer_key) or is_missing_credential(settings.epo_ops_consumer_secret):
        return _safe_result("not_run", "EPO OPS credentials missing.", error_type="missing_credentials")
    try:
        _token(settings)
        return {"source": EPO_SOURCE, "status": "success", "message": "EPO OPS authentication succeeded.", "error_type": ""}
    except Exception as exc:  # requests is optional in tests/import contexts
        return _safe_result(
            "error",
            "EPO OPS authentication failed. Check consumer key and secret.",
            error_type="authentication_failed",
            http_status=_http_status(exc),
        )


def search_epo(query: str | list[str], settings: Settings) -> dict[str, Any]:
    import requests

    if is_missing_credential(settings.epo_ops_consumer_key) or is_missing_credential(settings.epo_ops_consumer_secret):
        return _safe_result("not_run", "Live EPO search not run because credentials are missing.", error_type="missing_credentials")
    try:
        token = _token(settings)
    except Exception as exc:
        return _safe_result(
            "error",
            "EPO OPS authentication failed. Check consumer key and secret.",
            error_type="authentication_failed",
            http_status=_http_status(exc),
        )

    cql = build_epo_cql_query(query)
    fallback_cql = build_epo_cql_query(query, max_terms=2, quote_first=False)
    if not cql:
        return _safe_result("not_run", "No safe EPO OPS query terms available after cleaning.", error_type="no_safe_terms")

    url = f"{settings.epo_ops_base_url.rstrip('/')}{EPO_SEARCH_PATH}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    for idx, candidate in enumerate([cql, fallback_cql]):
        if not candidate:
            continue
        try:
            response = requests.get(url, params={"q": candidate, "Range": "1-5"}, headers=headers, timeout=20)
            response.raise_for_status()
            text = response.text or ""
            return {
                "source": EPO_SOURCE,
                "status": "success",
                "matches_found": 1 if text else 0,
                "top_match": "Patent bibliographic result" if text else "",
                "raw": text[:1000],
                "link_or_id": _extract_epo_identifier(text),
            }
        except requests.HTTPError as exc:
            status = _http_status(exc)
            if status in {400, 422} and idx == 0 and fallback_cql and fallback_cql != candidate:
                continue
            return _safe_result(
                "error",
                "EPO OPS query rejected. Query URL suppressed." if status in {400, 422} else "EPO OPS request failed. Query URL suppressed.",
                error_type="query_rejected" if status in {400, 422} else "request_failed",
                http_status=status,
            )
        except Exception as exc:
            return _safe_result(
                "error",
                "EPO OPS request failed. Query URL suppressed.",
                error_type="request_failed",
                http_status=_http_status(exc),
            )
    return _safe_result("error", "EPO OPS query rejected. Query URL suppressed.", error_type="query_rejected")
