"""Cautious, metadata-grounded similarity scoring utilities."""
from __future__ import annotations

from typing import Any
import re

from similarity.concepts import ConceptProfile, extract_metadata_concepts, metadata_text
from similarity.query_builder import normalise, is_generic_term

GENERIC_OVERLAP_ONLY = {"sus", "eq-5d", "eq-5d-5l", "recruitment", "retention", "fidelity", "interviews"}
RISK_SCORES = {"NONE": 0.0, "LOW": 0.15, "MEDIUM": 0.45, "HIGH": 0.75, "VERY_HIGH": 0.95, "HUMAN_CHECK": 0.0}
SPECIFIC_DIMENSIONS = {"named_entity", "technical_method", "clinical_problem", "product_function"}
IDENTIFIER_RE = re.compile(
    r"\b(?:US|EP|WO)\s?\d{6,}[A-Z0-9]*\b|\bAI[_\-\s]?AWARD\d{3,}\b|\bNIHR\d{4,}\b",
    re.I,
)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = normalise(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _identifiers(text: str) -> set[str]:
    ids = set()
    for match in IDENTIFIER_RE.finditer(text or ""):
        item = match.group(0).upper().replace(" ", "_")
        item = re.sub(r"AI[_\-\s]?AWARD", "AI_AWARD", item, flags=re.I)
        ids.add(item)
    return ids


def _exact_identifier_result(exact_ids: list[str]) -> dict:
    return {
        "score": 0.95,
        "risk": "VERY_HIGH",
        "similarity_type": "exact_identifier_match",
        "matched_concepts": exact_ids,
        "specific_matched_concepts": exact_ids,
        "generic_matched_concepts": [],
        "matched_dimensions": {"named_entity": exact_ids},
        "why_relevant": "The returned metadata contains the same public award, project or patent identifier as the application. This should be treated as a direct similarity hit requiring manual review.",
    }


def _profile_text(profile: ConceptProfile) -> str:
    chunks: list[str] = []
    for values in profile.specific_groups().values():
        chunks.extend(values)
    chunks.extend(profile.generic_domain_terms)
    chunks.extend(profile.infrastructure_terms)
    for values in profile.domain_signals.values():
        chunks.extend(values)
    return " ".join(chunks)


def _contains_phrase(haystack: str, phrase: str) -> bool:
    key = normalise(phrase)
    if not key:
        return False
    dehyphenated = haystack.replace("-", " ")
    return key in haystack or key in dehyphenated or key.replace(" ", "-") in haystack


def _overlap(app_terms: list[str], metadata_terms: list[str], metadata_haystack: str) -> list[str]:
    """Return app concepts that are actually present in returned metadata."""
    hits: list[str] = []
    metadata_keys = [normalise(term) for term in metadata_terms]
    for app_term in app_terms:
        app_key = normalise(app_term)
        if not app_key or app_key in GENERIC_OVERLAP_ONLY or is_generic_term(app_term):
            continue
        if _contains_phrase(metadata_haystack, app_term) or any(app_key in mk or mk in app_key for mk in metadata_keys if len(mk) >= 4):
            hits.append(app_term)
    return _dedupe(hits)

GENERIC_DOMAIN_CONCEPTS = {
    "software as a medical device",
    "samd",
    "ai platform",
    "edge ai",
    "medical device",
    "medical device application",
    "computing resource",
    "decision support",
    "platform",
    "clinical ai",
    "digital health",
    "artificial intelligence platform",
}

INFRASTRUCTURE_CONCEPTS = {
    "isolated execution",
    "execution environment",
    "resource allocation",
    "computing resource",
    "edge artificial intelligence platform",
    "edge ai platform",
    "application isolation",
    "deployment architecture",
}

DIMENSION_PHRASES = {
    "clinical_problem": {
        "wound deterioration",
        "chronic wounds",
        "wound assessment",
        "lower-limb wounds",
        "lower limb wounds",
        "pressure wounds",
        "surgical wounds",
        "atrial fibrillation detection",
        "falls prevention",
    },
    "technical_method": {
        "multispectral imaging",
        "multispectral wound imaging",
        "wound imaging",
        "wound imaging device",
        "wound boundary measurement",
        "tissue oxygenation",
        "thermal pattern analysis",
        "wound deterioration model",
        "wearable ecg sensor",
        "movement quality assessment",
    },
    "target_setting_population": {
        "community wound services",
        "community nursing",
        "tissue viability",
        "wound clinics",
        "lower-limb wounds",
        "lower limb wounds",
        "pressure wounds",
        "surgical wounds",
        "older adults falls risk",
        "nhs community rehabilitation",
        "community rehabilitation",
    },
    "product_function": {
        "wound risk score",
        "wound deterioration detection",
        "wound measurement",
        "escalation support",
        "clinical wound decision support",
        "wound decision support",
        "decision support platform for community wound deterioration detection",
    },
    "specific_named_product_or_phrase": {
        "woundwise-ai",
        "wound deterioration decision support",
        "multispectral wound imaging",
    },
}

RISK_SCORES = {"NONE": 0.0, "LOW": 0.15, "MEDIUM": 0.45, "HIGH": 0.75, "VERY_HIGH": 0.95}


def _contains(haystack: str, phrase: str) -> bool:
    key = normalise(phrase)
    dehyphenated = haystack.replace("-", " ")
    hyphenated_key = key.replace(" ", "-")
    return key in haystack or key in dehyphenated or hyphenated_key in haystack


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = normalise(item)
        if key and key not in seen:
            result.append(item)
            seen.add(key)
    return result


def _generic_matches(terms: list[str], haystack: str) -> list[str]:
    matches: list[str] = []
    normalised_terms = {normalise(term) for term in terms}
    for concept in sorted(GENERIC_DOMAIN_CONCEPTS):
        key = normalise(concept)
        term_matches_concept = any(key in term or term in key for term in normalised_terms)
        if term_matches_concept and _contains(haystack, concept):
            matches.append(concept)
    return _dedupe(matches)


def _infrastructure_matches(haystack: str) -> list[str]:
    return [concept for concept in sorted(INFRASTRUCTURE_CONCEPTS) if _contains(haystack, concept)]


def matched_concepts(terms: list[str], title: str, abstract: str = "") -> list[str]:
    haystack = normalise(f"{title} {abstract}")
    matches = []
    for term in terms:
        if normalise(term) in GENERIC_OVERLAP_ONLY:
            if _contains(haystack, term):
                matches.append(term)
            continue
        if not is_generic_term(term) and _contains(haystack, term):
            matches.append(term)
    return _dedupe(matches)


def _specific_matches(matches: list[str]) -> list[str]:
    generic_keys = {normalise(concept) for concept in GENERIC_DOMAIN_CONCEPTS}
    return [match for match in matches if normalise(match) not in generic_keys and normalise(match) not in GENERIC_OVERLAP_ONLY]


def _matched_dimensions(specific_matches: list[str], product_or_acronym: str) -> dict[str, list[str]]:
    dimensions: dict[str, list[str]] = {name: [] for name in DIMENSION_PHRASES}
    for match in specific_matches:
        key = normalise(match)
        for dimension, phrases in DIMENSION_PHRASES.items():
            if any(normalise(phrase) in key or key in normalise(phrase) for phrase in phrases):
                dimensions[dimension].append(match)
    if product_or_acronym:
        product_key = normalise(product_or_acronym)
        for match in specific_matches:
            if product_key and product_key == normalise(match):
                dimensions["specific_named_product_or_phrase"].append(match)
    return {dimension: _dedupe(values) for dimension, values in dimensions.items() if values}


def _wound_absence_note(specific_matches: list[str]) -> str:
    if any("wound" in normalise(match) for match in specific_matches):
        return ""
    return " It does not appear to address wound imaging, wound deterioration, community wound workflow, multispectral imaging or wound-specific decision support."


def _explanation(similarity_type: str, risk: str, specific: list[str], generic: list[str], infrastructure: list[str]) -> str:
    if similarity_type == "adjacent_infrastructure":
        return (
            "This appears to be an adjacent SaMD/AI infrastructure patent, not a direct wound-imaging "
            "deterioration-detection match. Shares broad SaMD/AI platform concepts but does not address "
            "wound imaging, wound deterioration, community wound workflow, multispectral imaging or "
            "wound-specific decision support."
        )
    if similarity_type == "generic_overlap":
        return "Only generic domain concepts overlap; this should be treated as background context rather than a direct invention match."
    if similarity_type == "same_domain_broad":
        return (
            f"Broad same-domain overlap found via {', '.join(specific or generic)}."
            f"{_wound_absence_note(specific)} Manual review is recommended before treating this as blocking IP."
        )
    if similarity_type == "direct_match":
        return (
            f"Potential direct invention match: specific overlap spans {len(specific)} concept(s), including "
            f"{', '.join(specific[:5])}."
        )
    return "No meaningful overlap found in the available metadata."


def score_profiles(app_profile: ConceptProfile, metadata_profile: ConceptProfile, app_text: str = "", metadata_raw_text: str = "") -> dict:
    app_ids = _identifiers(" ".join([app_text, _profile_text(app_profile)]))
    metadata_ids = _identifiers(" ".join([metadata_raw_text, _profile_text(metadata_profile)]))
    exact_ids = sorted(app_ids & metadata_ids)
    if exact_ids:
        return _exact_identifier_result(exact_ids)
    terms: list[str] = []
    for values in app_profile.specific_groups().values():
        terms.extend(values)
    metadata_text_value = _profile_text(metadata_profile)
    return score_result(_dedupe(terms), metadata_text_value, metadata_raw_text)


def score_result(terms: list[str], title: str, abstract: str = "", product_or_acronym: str = "") -> dict:
    exact_ids = sorted(_identifiers(" ".join(terms)) & _identifiers(f"{title} {abstract}"))
    if exact_ids:
        return _exact_identifier_result(exact_ids)
    haystack = normalise(f"{title} {abstract}")
    matches = matched_concepts(terms, title, abstract)
    generic = _generic_matches(terms, haystack)
    # Ensure matched_concepts remains backwards-compatible while the new fields split the display.
    for concept in generic:
        if normalise(concept) not in {normalise(match) for match in matches}:
            matches.append(concept)
    matches = _dedupe(matches)
    specific = _specific_matches(matches)
    infrastructure = _infrastructure_matches(haystack)
    dimensions = _matched_dimensions(specific, product_or_acronym)
    dimension_names = set(dimensions)

    if not matches:
        return {
            "score": 0.0,
            "risk": "NONE",
            "similarity_type": "no_meaningful_overlap",
            "matched_concepts": [],
            "specific_matched_concepts": [],
            "generic_matched_concepts": [],
            "matched_dimensions": {},
            "why_relevant": _explanation("no_meaningful_overlap", "NONE", [], [], []),
        }

    if len(matches) == 1 and normalise(matches[0]) in GENERIC_OVERLAP_ONLY:
        return {
            "score": 0.0,
            "risk": "NONE",
            "similarity_type": "generic_overlap",
            "matched_concepts": matches,
            "specific_matched_concepts": [],
            "generic_matched_concepts": matches,
            "matched_dimensions": {},
            "why_relevant": _explanation("generic_overlap", "NONE", [], matches, []),
        }

    if not specific:
        similarity_type = "adjacent_infrastructure" if infrastructure else "generic_overlap"
        risk = "MEDIUM" if infrastructure and generic else "LOW"
        return {
            "score": RISK_SCORES[risk],
            "risk": risk,
            "similarity_type": similarity_type,
            "matched_concepts": matches,
            "specific_matched_concepts": [],
            "generic_matched_concepts": generic or matches,
            "matched_dimensions": {},
            "why_relevant": _explanation(similarity_type, risk, [], generic or matches, infrastructure),
        }

    core_direct = {"clinical_problem", "technical_method", "product_function"}
    if core_direct <= dimension_names:
        risk = "VERY_HIGH" if len(dimension_names) >= 3 else "HIGH"
        similarity_type = "direct_match"
    elif len(dimension_names) >= 3:
        risk = "HIGH"
        similarity_type = "direct_match"
    elif not (dimension_names & core_direct):
        risk = "MEDIUM"
        similarity_type = "same_domain_broad"
    elif len(dimension_names) >= 2:
        risk = "MEDIUM"
        similarity_type = "same_domain_broad"
    else:
        risk = "LOW"
        similarity_type = "same_domain_broad"

    # Explicit caps: no clinical/problem/method/product-specific overlap may exceed MEDIUM.
    if not (dimension_names & core_direct) and risk in {"HIGH", "VERY_HIGH"}:
        risk = "MEDIUM"
        similarity_type = "same_domain_broad"
    # VERY_HIGH requires all three direct-invention dimensions.
    if risk == "VERY_HIGH" and not (core_direct <= dimension_names):
        risk = "HIGH"

    score = min(RISK_SCORES[risk], 0.15 + 0.18 * len(specific) + 0.08 * len(generic) + 0.08 * len(dimension_names))
    if risk == "VERY_HIGH":
        score = max(score, 0.90)
    elif risk == "HIGH":
        score = max(score, 0.70)

    return {
        "score": round(score, 2),
        "risk": risk,
        "similarity_type": similarity_type,
        "matched_concepts": matches,
        "specific_matched_concepts": specific,
        "generic_matched_concepts": generic,
        "matched_dimensions": dimensions,
        "why_relevant": _explanation(similarity_type, risk, specific, generic, infrastructure),
    }
