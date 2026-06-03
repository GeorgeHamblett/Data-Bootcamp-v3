"""Cautious, metadata-grounded similarity scoring utilities."""
from __future__ import annotations

from typing import Any

from similarity.concepts import ConceptProfile, extract_metadata_concepts, metadata_text
from similarity.query_builder import normalise, is_generic_term

GENERIC_OVERLAP_ONLY = {"sus", "eq-5d", "eq-5d-5l", "recruitment", "retention", "fidelity", "interviews"}
RISK_SCORES = {"NONE": 0.0, "LOW": 0.15, "MEDIUM": 0.45, "HIGH": 0.75, "VERY_HIGH": 0.95, "HUMAN_CHECK": 0.0}
SPECIFIC_DIMENSIONS = {"named_entity", "technical_method", "clinical_problem", "product_function"}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = normalise(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


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


def matched_concepts(terms: list[str], title: str, abstract: str = "") -> list[str]:
    """Backwards-compatible helper: only terms actually present in returned metadata match."""
    haystack = normalise(f"{title} {abstract}")
    return _dedupe([term for term in terms if not is_generic_term(term) and _contains_phrase(haystack, term)])


def _profile_from_terms(terms: list[str], product_or_acronym: str = "") -> ConceptProfile:
    from similarity.concepts import _clinical_terms, _generic_terms, _setting_terms
    from similarity.concepts import TECH_SUFFIXES, FUNCTION_SUFFIXES

    named: list[str] = [product_or_acronym] if product_or_acronym else []
    technical: list[str] = []
    clinical: list[str] = []
    functions: list[str] = []
    settings: list[str] = []
    generic: list[str] = []
    for term in terms:
        key = normalise(term)
        term_generic = _generic_terms(term)
        generic_only_tokens = {"software", "medical", "device", "ai", "artificial", "intelligence", "platform", "digital", "health", "clinical", "application", "app", "decision", "support", "as", "a", "medical"}
        if term_generic and (is_generic_term(term) or all(token in generic_only_tokens for token in key.split())):
            generic.extend(term_generic)
            continue
        generic.extend(term_generic)
        if product_or_acronym and normalise(term) == normalise(product_or_acronym):
            named.append(term)
        elif term and not is_generic_term(term) and any(ch.isupper() for ch in term[:4]):
            named.append(term)
        if any(key.endswith(normalise(suffix)) for suffix in TECH_SUFFIXES):
            technical.append(term)
        if any(key.endswith(normalise(suffix)) for suffix in FUNCTION_SUFFIXES):
            functions.append(term)
        clinical.extend(_clinical_terms(term))
        settings.extend(_setting_terms(term))
    return ConceptProfile(
        named_entities=_dedupe(named),
        technical_method_terms=_dedupe(technical),
        clinical_problem_terms=_dedupe(clinical),
        product_function_terms=_dedupe(functions),
        population_setting_terms=_dedupe(settings),
        generic_domain_terms=_dedupe(generic),
    )


def score_profiles(app_profile: ConceptProfile, metadata_profile: ConceptProfile, *, title: str = "", abstract: str = "", raw: Any = None) -> dict:
    returned_text = normalise(metadata_text(title, abstract, raw))
    if metadata_profile.metadata_incomplete:
        return {
            "score": 0.0,
            "risk": "NONE",
            "similarity_type": "human_check_metadata_incomplete",
            "matched_concepts": [],
            "specific_matched_concepts": [],
            "generic_matched_concepts": [],
            "matched_dimensions": {},
            "why_relevant": "A record was returned, but title/abstract metadata could not be parsed; it has not been scored from query terms alone.",
        }

    matched_dimensions: dict[str, list[str]] = {}
    specific: list[str] = []
    for dimension, app_terms in app_profile.specific_groups().items():
        metadata_terms = metadata_profile.specific_groups().get(dimension, [])
        hits = _overlap(app_terms, metadata_terms, returned_text)
        if hits:
            matched_dimensions[dimension] = hits
            specific.extend(hits)
    specific = _dedupe(specific)

    generic = _overlap(app_profile.generic_domain_terms, metadata_profile.generic_domain_terms, returned_text)
    if not generic:
        # Generic acronym/compound phrases such as SaMD/edge-AI may not be extracted as exact app generic terms.
        generic = [term for term in metadata_profile.generic_domain_terms if _contains_phrase(returned_text, term) and any(_contains_phrase(normalise(" ".join(app_profile.generic_domain_terms)), term) or _contains_phrase(term, app) for app in app_profile.generic_domain_terms)]
    generic = _dedupe(generic)

    infra = metadata_profile.infrastructure_terms
    dimension_names = set(matched_dimensions)
    unrelated_categories = set(metadata_profile.domain_signals) - set(app_profile.domain_signals)
    dominated_by_unrelated = bool(unrelated_categories & {"drug_biologic", "gene_cell_animal", "unrelated_engineering"}) and not (dimension_names & SPECIFIC_DIMENSIONS)

    if dominated_by_unrelated or (not specific and not generic and not infra):
        return {
            "score": 0.0,
            "risk": "NONE",
            "similarity_type": "no_meaningful_overlap",
            "matched_concepts": [],
            "specific_matched_concepts": [],
            "generic_matched_concepts": [],
            "matched_dimensions": {},
            "why_relevant": "The API returned a record, but the returned title/abstract do not match the application’s extracted product, technical method, clinical problem or product function concepts.",
        }

    if not specific:
        if infra:
            similarity_type = "adjacent_infrastructure"
            risk = "LOW" if not generic else "MEDIUM"
            score = 0.25 if risk == "LOW" else 0.35
            why = "This appears to be an adjacent SaMD/AI infrastructure patent, not a direct wound-imaging deterioration-detection match. The record shares broad platform or deployment concepts, but not the application’s specific clinical problem, technical method or product function."
        else:
            similarity_type = "generic_overlap"
            risk = "LOW"
            score = 0.15
            why = "Only generic domain concepts overlap; this should be treated as background context rather than a direct invention match."
        return {
            "score": score,
            "risk": risk,
            "similarity_type": similarity_type,
            "matched_concepts": generic,
            "specific_matched_concepts": [],
            "generic_matched_concepts": generic,
            "matched_dimensions": {},
            "why_relevant": why,
        }

    major = dimension_names & SPECIFIC_DIMENSIONS
    has_core_triad = {"clinical_problem", "technical_method", "product_function"} <= dimension_names
    if len(major) >= 3 and ("named_entity" in major or has_core_triad):
        risk = "VERY_HIGH"
        similarity_type = "direct_match"
    elif len(major) >= 2:
        risk = "HIGH"
        similarity_type = "strong_same_domain"
    elif ("technical_method" in major or "product_function" in major) and ("clinical_problem" in dimension_names or "named_entity" in dimension_names or "population_setting" in dimension_names):
        risk = "MEDIUM"
        similarity_type = "same_domain_broad"
    else:
        risk = "LOW"
        similarity_type = "same_domain_broad"

    if risk in {"HIGH", "VERY_HIGH"} and len(major) < 2:
        risk = "MEDIUM"
    if risk == "VERY_HIGH" and not has_core_triad and "named_entity" not in major:
        risk = "HIGH"

    score = min(RISK_SCORES[risk], 0.2 + 0.15 * len(major) + 0.05 * len(specific) + 0.04 * len(generic))
    if risk == "HIGH":
        score = max(score, 0.7)
    if risk == "VERY_HIGH":
        score = max(score, 0.9)
    why = f"The returned title/abstract shares specific overlap in {', '.join(sorted(dimension_names))}." if similarity_type in {"direct_match", "strong_same_domain"} else "The returned title/abstract has limited same-domain overlap; manual review is recommended before treating it as blocking IP."
    return {
        "score": round(score, 2),
        "risk": risk,
        "similarity_type": similarity_type,
        "matched_concepts": _dedupe(specific + generic),
        "specific_matched_concepts": specific,
        "generic_matched_concepts": generic,
        "matched_dimensions": matched_dimensions,
        "why_relevant": why,
    }


def score_result(terms: list[str], title: str, abstract: str = "", product_or_acronym: str = "") -> dict:
    app_profile = _profile_from_terms(terms, product_or_acronym)
    metadata_profile = extract_metadata_concepts(title, abstract)
    return score_profiles(app_profile, metadata_profile, title=title, abstract=abstract)
