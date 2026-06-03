"""EPO Open Patent Services integration with safe CQL query construction."""
from __future__ import annotations

import base64
import json
import re
import xml.etree.ElementTree as ET
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


def _is_patent_identifier(term: str) -> bool:
    return bool(re.search(r"\b(?:US|EP|WO)\s?\d{6,}[A-Z0-9]*\b", term, re.I))


def _patent_number_for_cql(term: str) -> str:
    cleaned = re.sub(r"\s+", "", term.upper())
    cleaned = re.sub(r"(A\d|B\d|U\d)$", "", cleaned)
    return cleaned




def _is_epo_technical_or_function_term(term: str) -> bool:
    key = normalise(term)
    return any(x in key for x in [
        "woubot",
        "woucare-ai",
        "woundwise-ai",
        "woundwise",
        "wound image segmentation",
        "wound healing prediction",
        "wound deterioration detection",
        "wound care recommendation",
        "personalised wound care",
        "personalized wound care",
        "wound pixels",
        "non-wound pixels",
        "thermal imaging",
        "temperature condition index",
        "multispectral wound imaging",
        "wound imaging device",
        "multispectral imaging device",
        "neural network wound",
        "image-based wound assessment",
        "wound assessment",
        "risk categorisation",
        "risk categorization",
        "screening frequency recommendation",
        "escalation decision support",
    ])


def _is_epo_clinical_condition_term(term: str) -> bool:
    key = normalise(term)
    return any(x in key for x in [
        "diabetic foot ulcer",
        "venous leg ulcer",
        "chronic wound",
        "chronic lower-limb wound",
        "lower-limb wound",
        "pressure ulcer",
        "wounds",
    ])


def _ta(term: str) -> str:
    return f'ta="{term.replace(chr(34), "")}"'

def _is_safe_epo_term(term: str) -> bool:
    cleaned = _clean_epo_term(term)
    if _is_patent_identifier(cleaned):
        return True
    key = normalise(cleaned)
    if not cleaned or is_generic_term(cleaned) or key in EPO_GENERIC_TERMS:
        return False
    if len(cleaned) > 60 or len(cleaned.split()) > 5:
        return False
    if re.search(r"\baged\s*\d+", key) or key in {"older adults", "adults", "patients", "people", "community", "nhs", "rehabilitation", "detection"}:
        return False
    if key.startswith("over with ") or key.startswith("under with "):
        return False
    if re.search(r"\b[a-z]{1,3}$", cleaned) and not re.search(r"\b(?:AI|IP|ECG|NHS)$", cleaned):
        return False
    if all(word in EPO_GENERIC_TERMS for word in key.split()):
        return False
    return True

def build_epo_cql_query(terms: list[str] | str, *, max_terms: int = 4, quote_first: bool = True) -> str:
    """Build a high-precision EPO OPS CQL query from safe patent-relevant terms only."""
    selected: list[str] = []
    seen: set[str] = set()
    for raw in _terms_from_query(terms):
        term = _clean_epo_term(raw)
        key = normalise(term)
        if not _is_safe_epo_term(term) or key in seen:
            continue
        if _is_patent_identifier(term):
            return f"pn={_patent_number_for_cql(term)}"
        selected.append(term)
        seen.add(key)
        if len(selected) >= max_terms:
            break
    if not selected:
        return ""

    invention_terms = [term for term in selected if _is_epo_technical_or_function_term(term)]
    condition_terms = [term for term in selected if _is_epo_clinical_condition_term(term)]
    if not invention_terms:
        return ""

    primary = invention_terms[0]
    if condition_terms and normalise(condition_terms[0]) != normalise(primary):
        return f"{_ta(primary)} and {_ta(condition_terms[0])}"
    return _ta(primary)



def _text(elem: ET.Element) -> str:
    return " ".join(part.strip() for part in elem.itertext() if part and part.strip())


def _parse_epo_xml(text: str) -> dict[str, Any]:
    title = ""
    abstract_parts: list[str] = []
    doc_numbers: list[str] = []
    countries: list[str] = []
    kinds: list[str] = []
    applicants: list[str] = []
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except Exception:
        return {}
    for elem in root.iter():
        tag = elem.tag.split("}")[-1].lower()
        value = _text(elem)
        if not value:
            continue
        if tag == "invention-title" and not title:
            title = value
        elif tag == "abstract":
            abstract_parts.append(value)
        elif tag == "doc-number":
            doc_numbers.append(value)
        elif tag == "country":
            countries.append(value)
        elif tag == "kind":
            kinds.append(value)
        elif tag in {"applicant-name", "name"}:
            applicants.append(value)
    # If p/abstract parent tracking was not available from iter(), collect direct p text under abstract nodes.
    for elem in root.iter():
        if elem.tag.split("}")[-1].lower() == "abstract":
            for child in elem.iter():
                if child.tag.split("}")[-1].lower() == "p":
                    v = _text(child)
                    if v:
                        abstract_parts.append(v)
    abstract = " ".join(dict.fromkeys(abstract_parts))
    applicants = list(dict.fromkeys(applicants))
    doc_numbers = list(dict.fromkeys(doc_numbers))
    countries = list(dict.fromkeys(countries))
    kinds = list(dict.fromkeys(kinds))
    return {
        "title": title,
        "abstract": abstract,
        "doc_numbers": doc_numbers,
        "applicants": applicants,
        "country": countries[0] if countries else "",
        "kind": kinds[0] if kinds else "",
        "metadata_text": " ".join([title, abstract, " ".join(applicants)]).strip(),
    }


def _find_values(obj: Any, wanted: set[str]) -> list[str]:
    values: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            norm_key = str(key).replace("_", "-").lower()
            if norm_key in wanted:
                if isinstance(value, dict) and "$" in value:
                    values.append(str(value["$"]))
                elif not isinstance(value, (dict, list)):
                    values.append(str(value))
            values.extend(_find_values(value, wanted))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(_find_values(item, wanted))
    return [v.strip() for v in values if str(v).strip()]


def parse_epo_metadata(text: str) -> dict[str, Any]:
    """Extract title/abstract/publication/applicant metadata from EPO XML or JSON safely."""
    if not text:
        return {"title": "", "abstract": "", "doc_numbers": [], "applicants": [], "metadata_text": ""}
    stripped = text.strip()
    parsed: dict[str, Any] = {}
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(stripped)
            titles = _find_values(data, {"invention-title", "title"})
            abstracts = _find_values(data, {"abstract", "p"})
            doc_numbers = _find_values(data, {"doc-number", "publication-number"})
            countries = _find_values(data, {"country"})
            kinds = _find_values(data, {"kind"})
            applicants = _find_values(data, {"applicant-name", "name", "applicant"})
            parsed = {
                "title": titles[0] if titles else "",
                "abstract": " ".join(dict.fromkeys(abstracts)),
                "doc_numbers": list(dict.fromkeys(doc_numbers)),
                "applicants": list(dict.fromkeys(applicants)),
                "country": countries[0] if countries else "",
                "kind": kinds[0] if kinds else "",
            }
        except Exception:
            parsed = {}
    if not parsed:
        parsed = _parse_epo_xml(stripped)
    if not parsed:
        parsed = {"title": "", "abstract": "", "doc_numbers": [], "applicants": [], "metadata_text": ""}
    parsed["metadata_text"] = " ".join([
        str(parsed.get("title", "")),
        str(parsed.get("abstract", "")),
        " ".join(parsed.get("doc_numbers", []) or []),
        str(parsed.get("country", "")),
        str(parsed.get("kind", "")),
        " ".join(parsed.get("applicants", []) or []),
    ]).strip()
    return parsed

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
            metadata = parse_epo_metadata(text)
            title = metadata.get("title") or ("Patent record returned; title/abstract not parsed" if text else "")
            return {
                "source": EPO_SOURCE,
                "status": "success",
                "matches_found": 1 if text else 0,
                "top_match": title,
                "raw": metadata if metadata.get("metadata_text") else {**metadata, "unparsed_excerpt": text[:1000]},
                "link_or_id": _extract_epo_identifier(text) or " ".join(metadata.get("doc_numbers", [])[:1]),
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
