"""Cautious, metadata-grounded similarity scoring utilities."""
from __future__ import annotations

from similarity.query_builder import normalise, is_generic_term, concept_class
from similarity.identifiers import extract_identifiers

GENERIC_OVERLAP_ONLY = {"sus", "eq-5d", "eq-5d-5l", "recruitment", "retention", "fidelity", "interviews"}
RISK_SCORES = {"NONE": 0.0, "LOW": 0.15, "MEDIUM": 0.45, "HIGH": 0.75, "VERY_HIGH": 0.95, "HUMAN_CHECK": 0.0}
INFRASTRUCTURE_CONCEPTS = {
    "isolated execution", "execution environment", "execution environments", "isolation level", "isolation levels",
    "resource allocation", "computing resource", "computing resources", "deployment architecture",
    "application isolation", "edge artificial intelligence platform", "edge ai platform",
}
GENERIC_DOMAIN_CONCEPTS = {
    "software as a medical device", "software-as-a-medical-device", "samd", "medical device", "clinical safety", "quality management system",
    "technical file", "technical documentation", "regulatory readiness", "technology readiness", "digital health",
    "artificial intelligence", "edge artificial intelligence", "ai platform", "clinical ai", "platform", "application",
    "budget", "health economics", "knowledge mobilisation",
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = normalise(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _contains(haystack: str, phrase: str) -> bool:
    key = normalise(phrase)
    if not key:
        return False
    dehyphenated = haystack.replace("-", " ")
    return key in haystack or key in dehyphenated or key.replace(" ", "-") in haystack


def _exact_identifier_result(exact_ids: list[str]) -> dict:
    return {
        "score": 0.95,
        "risk": "VERY_HIGH",
        "similarity_type": "exact_identifier_match",
        "matched_concepts": exact_ids,
        "specific_matched_concepts": exact_ids,
        "generic_matched_concepts": [],
        "matched_dimensions": {"exact_identifier": exact_ids},
        "why_relevant": "The returned metadata contains the same public award, trial or patent identifier as the application. This should be treated as a direct similarity hit requiring manual review.",
    }


def _generic_matches(terms: list[str], haystack: str) -> list[str]:
    normalised_terms = {normalise(term) for term in terms}
    matches = []
    for concept in GENERIC_DOMAIN_CONCEPTS | GENERIC_OVERLAP_ONLY:
        key = normalise(concept)
        if (key in normalised_terms or any(key in t or t in key for t in normalised_terms)) and _contains(haystack, concept):
            matches.append(concept)
    return _dedupe(matches)


def _infrastructure_matches(haystack: str) -> list[str]:
    return [concept for concept in sorted(INFRASTRUCTURE_CONCEPTS) if _contains(haystack, concept)]


def matched_concepts(terms: list[str], title: str, abstract: str = "") -> list[str]:
    haystack = normalise(f"{title} {abstract}")
    matches: list[str] = []
    for term in terms:
        key = normalise(term)
        if not key or key in GENERIC_OVERLAP_ONLY or (is_generic_term(term) and not extract_identifiers(term)):
            continue
        if _contains(haystack, term):
            matches.append(term)
    return _dedupe(matches)


def _matched_dimensions(specific: list[str], product_or_acronym: str, terms: list[str], haystack: str) -> dict[str, list[str]]:
    dims: dict[str, list[str]] = {}
    for term in specific:
        cls = concept_class(term)
        key = normalise(term)
        if cls == "clinical_or_social_care_problem":
            cls = "clinical_problem"
        elif cls == "technical_method_or_mechanism":
            cls = "technical_method"
        elif cls == "product_or_intervention_function":
            cls = "product_function"
        elif cls == "population_setting":
            cls = "target_setting_population"
        elif cls == "intervention_type":
            pass
        elif cls == "named_entities":
            cls = "specific_named_product_or_phrase"
        dims.setdefault(cls, []).append(term)
        if any(x in key for x in ["deterioration", "risk", "fall", "falls", "ulcer", "wound", "sepsis", "discharge", "infection", "diagnosis"]):
            dims.setdefault("clinical_problem", []).append(term)
        if any(x in key for x in ["detection", "prevention", "rehabilitation", "triage", "feedback", "coordination", "planning", "support", "care"]):
            dims.setdefault("product_function", []).append(term)
    if product_or_acronym and _contains(haystack, product_or_acronym):
        dims.setdefault("specific_named_product_or_phrase", []).append(product_or_acronym)
    return {k: _dedupe(v) for k, v in dims.items()}


def _specific_matches(matches: list[str]) -> list[str]:
    out: list[str] = []
    for m in matches:
        key = normalise(m)
        if key in {normalise(x) for x in GENERIC_DOMAIN_CONCEPTS | GENERIC_OVERLAP_ONLY}:
            continue
        if concept_class(m) in {"generic_document_terms", "population_setting"} or is_generic_term(m):
            continue
        out.append(m)
    return out


def _explanation(similarity_type: str, risk: str, specific: list[str], generic: list[str], infrastructure: list[str]) -> str:
    if similarity_type == "no_meaningful_overlap":
        return "No meaningful overlap found in the available metadata."
    if similarity_type == "generic_overlap":
        return "Only generic document/checklist terms overlap; these do not indicate external novelty similarity."
    if similarity_type == "infrastructure_only":
        return "The returned record concerns generic infrastructure/platform concepts without overlap on the application's named intervention, technical method, product function or target problem."
    if similarity_type == "generic_or_regulatory_overlap":
        return "Only generic domain, regulatory-readiness, finance/checklist or infrastructure concepts overlap; this is background context rather than a direct invention match."
    if similarity_type == "condition_only_overlap":
        return "Only the broad clinical/social-care problem or setting overlaps; this is a low-specificity similarity signal."
    return f"Potential similarity: overlap spans {len(specific)} specific concept(s), including {', '.join(specific[:5])}."


def score_result(terms: list[str], title: str, abstract: str = "", product_or_acronym: str = "") -> dict:
    exact_ids = sorted(set(extract_identifiers(" ".join(terms))) & set(extract_identifiers(f"{title} {abstract}")))
    if exact_ids:
        return _exact_identifier_result(exact_ids)
    haystack = normalise(f"{title} {abstract}")
    matches = matched_concepts(terms, title, abstract)
    generic = _generic_matches(terms, haystack)
    for concept in generic:
        if normalise(concept) not in {normalise(match) for match in matches}:
            matches.append(concept)
    matches = _dedupe(matches)
    specific = _specific_matches(matches)
    infrastructure = _infrastructure_matches(haystack)
    dimensions = _matched_dimensions(specific, product_or_acronym, terms, haystack)
    dimension_names = set(dimensions)

    if infrastructure and not specific:
        return {"score": 0.0, "risk": "NONE", "similarity_type": "infrastructure_only_no_specific_overlap", "matched_concepts": matches, "specific_matched_concepts": [], "generic_matched_concepts": generic or matches, "matched_dimensions": {}, "why_relevant": "The returned record concerns generic infrastructure/platform concepts; it does not address the application's named intervention, technical method, product function or target problem."}
    if not matches:
        return {"score": 0.0, "risk": "NONE", "similarity_type": "no_meaningful_overlap", "matched_concepts": [], "specific_matched_concepts": [], "generic_matched_concepts": [], "matched_dimensions": {}, "why_relevant": _explanation("no_meaningful_overlap", "NONE", [], [], [])}
    if not specific:
        all_generic = bool(generic) and not any(normalise(g) in {"knowledge mobilisation", "budget", "health economics", "sus"} for g in generic)
        risk = "LOW" if all_generic else "NONE"
        stype = "generic_or_regulatory_overlap" if all_generic else "generic_overlap"
        return {"score": RISK_SCORES[risk], "risk": risk, "similarity_type": stype, "matched_concepts": matches, "specific_matched_concepts": [], "generic_matched_concepts": generic or matches, "matched_dimensions": {}, "why_relevant": _explanation(stype, risk, [], generic, infrastructure)}

    condition_dims = {"clinical_problem", "target_setting_population"}
    invention_dims = {"technical_method", "product_function", "intervention_type", "specific_named_product_or_phrase"}
    if dimension_names <= condition_dims:
        risk, stype = "LOW", "condition_only_overlap"
    elif "specific_named_product_or_phrase" in dimension_names and (dimension_names & (condition_dims | invention_dims)):
        risk, stype = "HIGH", "direct_match"
    elif {"technical_method", "product_function", "clinical_problem"} <= dimension_names:
        risk, stype = "HIGH", "direct_match"
    elif {"technical_method", "product_function"} <= dimension_names:
        risk, stype = "MEDIUM", "same_method_and_function"
    elif dimension_names & invention_dims and dimension_names & condition_dims:
        risk, stype = "MEDIUM", "same_domain_broad"
    elif dimension_names & invention_dims:
        risk, stype = "LOW", "same_method_or_function_only"
    else:
        risk, stype = "LOW", "condition_only_overlap"

    score = min(RISK_SCORES[risk], 0.15 + 0.18 * len(specific) + 0.08 * len(generic) + 0.08 * len(dimension_names))
    if stype == "condition_only_overlap":
        score = min(score, 0.20)
    if risk == "HIGH":
        score = max(score, 0.70)
    return {"score": round(score, 2), "risk": risk, "similarity_type": stype, "matched_concepts": matches, "specific_matched_concepts": specific, "generic_matched_concepts": generic, "matched_dimensions": dimensions, "why_relevant": _explanation(stype, risk, specific, generic, infrastructure)}


def score_profiles(app_profile, metadata_profile, app_text: str = "", metadata_raw_text: str = "") -> dict:
    terms: list[str] = []
    for values in app_profile.specific_groups().values():
        terms.extend(values)
    metadata_terms: list[str] = []
    for values in metadata_profile.specific_groups().values():
        metadata_terms.extend(values)
    return score_result(_dedupe(terms), " ".join(metadata_terms), metadata_raw_text)
