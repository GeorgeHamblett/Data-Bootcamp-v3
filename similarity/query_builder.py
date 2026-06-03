"""Build privacy-preserving external similarity queries from generic concepts."""
from __future__ import annotations

import re
from similarity.identifiers import extract_identifiers, is_any_identifier, is_patent_identifier, is_nihr_identifier, is_trial_identifier, normalise_identifier
from schemas import ApplicationFacts, NOT_EXPLICITLY_STATED, SimilarityQuery

MAX_QUERY_TERMS = 10
MAX_TERM_CHARS = 60


GENERIC_DOCUMENT_TERMS = {
    "the", "a", "an", "it", "this", "we", "our", "early", "earlier", "new", "novel", "current", "clear", "named",
    "uploaded", "upload", "file", "document", "docx", "pdf", "txt", "training", "dummy", "application", "plain",
    "english", "summary", "gantt", "chart", "appendix", "form", "section", "background", "methodology",
    "project", "research", "study", "objective", "aim", "funding", "proposal", "applicant", "partners", "partner",
    "draft", "report", "template", "playbook", "guidance", "work", "package", "task", "month", "milestones",
    "milestone", "recruitment", "retention", "fidelity", "interviews", "reduc", "reduce", "avoidable", "patients", "people", "adults",
    "older adults", "community", "nhs", "nhs england", "nice", "nice-aligned", "regulatory", "system", "knowledge", "knowledge mobilisation",
    "dissemination", "impact", "health economics", "economic model", "budget", "budget impact", "cost effectiveness",
    "cost utility", "qaly", "icer", "roi", "value for money", "aims", "objectives", "rationale",
    "project management", "risk register", "ppie", "patient and public involvement", "research inclusion",
    "plain english summary", "adoption pathway", "commercialisation strategy", "grant requested", "scheme cap",
    "acord", "soecat", "trl", "technology readiness level", "regulatory readiness", "ukca", "iso 13485",
    "iso 14971", "clinical validation needs", "implementation readiness", "comparator", "current best practice", "decision-tree modelling", "sensitivity analysis", "iec 62304 documentation", "equality impact summaries", "north pennine nhs trust", "intervention",
    "endpoint", "endpoints", "primary endpoint", "secondary endpoint", "outcome", "outcomes",
    "related incidents", "12-month decision model", "decision model", "cost model",
    "for training use only", "fictional example application", "training use only",
}

NOISE_PHRASES = [
    "for training use only", "fictional example application", "training use only", "dummy application",
    "this project will", "many people do", "falls can seriously", "milestones month",
]
GENERIC_ACRONYMS = {"SUS", "PPI", "PPIE", "NHS", "NIHR", "QALY", "EQ-5D", "EQ-5D-5L", "PDA", "IEC", "IRAS", "ISO", "MHRA", "PSS"}
VALID_SHORT_ACRONYMS = {"AI", "IP", "ECG"}
TECH_SUFFIXES = (
    "assessment", "monitoring", "prediction", "detection", "diagnosis", "triage", "classification",
    "stratification", "risk score", "risk model", "decision support", "feedback", "coaching",
    "rehabilitation", "intervention", "pathway", "assay", "biomarker", "imaging", "sensor",
    "sensors", "wearable", "therapeutic", "diagnostic", "algorithm", "model", "classifier",
    "platform", "device", "software", "training package", "behaviour-change programme",
    "self-management programme", "implementation package", "clinical pathway", "care pathway",
    "remote monitoring", "point-of-care test", "engine", "analysis", "planning", "support",
)
FUNCTION_SUFFIXES = (
    "fall prevention", "prevention", "rehabilitation", "detection", "diagnosis", "triage", "prioritisation",
    "remote monitoring", "symptom management", "medication optimisation", "care coordination",
    "adherence support", "risk scoring", "personalised feedback", "personalized feedback",
    "referral decision support", "decision support", "feedback", "coaching", "escalation", "assessment",
    "measurement", "care planning", "transitional support",
)
NAMED_TECHNICAL_METHODS = (
    "Hidden Markov Models", "Hidden Markov Model", "convolutional neural network",
    "deep convolutional neural network classifier", "random forest", "transformer model", "SHAP", "LIME",
    "PCR", "ELISA", "mass spectrometry", "ultrasound", "MRI", "CT", "thermal imaging",
    "multispectral imaging", "motion analysis", "inertial measurement unit", "accelerometer", "gyroscope",
    "motion quality assessment engine", "wearable digital therapeutic", "movement quality assessment", "wearable sensors", "multiplex biomarker panel", "biomarker panel", "point-of-care test", "care pathway redesign",
    "intervention mapping", "mixed-methods implementation evaluation", "randomised feasibility trial",
)


def normalise(term: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 +#\-/]", " ", str(term).lower())).strip()


def _canonical_identifier(value: str) -> str:
    return normalise_identifier(value)


def _identifier_phrases(value: str) -> list[str]:
    return extract_identifiers(value)


def _looks_like_identifier(value: str) -> bool:
    return is_any_identifier(_clean(value) if "_clean" in globals() else value)


def is_generic_term(term: str) -> bool:
    cleaned = normalise(term)
    if not cleaned or len(cleaned) < 3:
        return True
    if re.fullmatch(r"trl(?:\s+\d+)?(?:\s+to\s+trl?\s*\d+)?", cleaned):
        return True
    if re.fullmatch(r"(?:iso\s*)?(?:13485|14971)", cleaned):
        return True
    if cleaned in GENERIC_DOCUMENT_TERMS:
        return True
    if cleaned.upper() in GENERIC_ACRONYMS:
        return True
    if any(noise in cleaned for noise in NOISE_PHRASES):
        return True
    words = cleaned.split()
    return all(word in GENERIC_DOCUMENT_TERMS for word in words)


def _clean(term: str) -> str:
    cleaned = re.sub(r"FOR\s+TRAINING\s+USE\s+ONLY|FICTIONAL\s+EXAMPLE\s+APPLICATION|SYNTHETIC\s+EXEMPLAR|DUMMY\s+APPLICATION", " ", str(term), flags=re.I)
    cleaned = re.sub(r"\b(?:fictional|invented|training only|dummy)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"^(?:this project will|this proposal will|we will)\b", " ", cleaned, flags=re.I)
    cleaned = cleaned.replace("/", " / ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .;:,\n\t")
    return cleaned.strip(" ,;:-/")


def _sentence_like(value: str) -> bool:
    return bool(re.search(r"[.!?]", value) or len(value.split()) > 6 or re.search(r"\b(?:will|designed to|participants? aged|include|includes|across)\b", value, re.I))


def _recognised_product_or_acronym(value: str) -> bool:
    cleaned = _clean(value)
    if len(cleaned.split()) > 2:
        return False
    if re.fullmatch(r"[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*", cleaned):
        return True
    return bool(re.fullmatch(r"[A-Z0-9-]{3,12}", cleaned))


def _looks_like_sentence_fragment(value: str) -> bool:
    key = normalise(value)
    words = key.split()
    if is_any_identifier(value):
        return False
    technical_markers = tuple(normalise(x) for x in TECH_SUFFIXES + FUNCTION_SUFFIXES + NAMED_TECHNICAL_METHODS)
    if any(marker and marker in key for marker in technical_markers):
        return False
    if len(words) > 5:
        return True
    if re.search(
        r"\b(their|his|her|our|your|is|are|was|were|will|would|could|should|consume|consuming|create|creating|reduce|reducing|improve|improving|support|supporting|needs|needed|designed|including|capacity|burden|pressure|adoption|implementation)\b",
        key,
    ):
        return True
    return False


def _is_demographic_or_context_only(value: str) -> bool:
    key = normalise(value)
    if re.fullmatch(r"(?:aged|age|over|under|older|younger|adults?|patients?|people)(?:\s+\d+\+?)?(?:\s+(?:and|or|over|under))*", key):
        return True
    if re.fullmatch(r"(?:older adults|adults|patients|people|community|nhs|care|usual care|rehabilitation|detection|support|platform|device)", key):
        return True
    if re.search(r"\baged\s*\d+", key):
        return True
    return False


def _valid_query_concept(value: str) -> bool:
    value = _clean(value)
    if _looks_like_identifier(value):
        return True
    key = normalise(value)
    words = key.split()
    if not value or value == NOT_EXPLICITLY_STATED or is_generic_term(value):
        return False
    if _identifier_phrases(value) and not _looks_like_identifier(value):
        return False
    if any(blocked in key for blocked in ["software as a medical device", "medical device", "technology readiness", "quality management system", "technical file", "iso 13485", "iso 14971", "ukca"]):
        return False
    if _looks_like_sentence_fragment(value) or " and " in key or " including " in key or " substantial patient burden" in key or "create substantial" in key:
        return False
    if key.endswith(" diabetic"):
        return False
    if len(value) > MAX_TERM_CHARS or len(words) > 5:
        return False
    if len(value) < 3 and value.upper() not in VALID_SHORT_ACRONYMS:
        return False
    if _is_demographic_or_context_only(value):
        return False
    if re.search(r"\b[a-z]{1,3}$", value) and not re.search(r"\b(?:AI|IP|ECG|CJD)$", value):
        return False
    if re.search(r"\b(cost|costing|utility|economic|economics|mhra|nice|nihr|comparator|current best practice|plain-language|advice|award)\b", key):
        return False
    if key.split()[0] in {"and", "or", "for", "with", "plus", "the", "a", "an", "as", "reduce", "to", "including", "include", "includes", "create", "lead"}:
        return False
    if key.split()[-1] in {"and", "or", "for", "with", "of", "plus"}:
        return False
    if re.search(r"\b[a-z]\b$", key):
        return False
    return True


def _dedupe_add(candidates: list[str], value: str) -> None:
    value = _clean(value)
    key = normalise(value)
    if not _valid_query_concept(value):
        return
    for idx, existing in enumerate(list(candidates)):
        existing_key = normalise(existing)
        if key == existing_key:
            return
        if _looks_like_identifier(existing) or _looks_like_identifier(value):
            continue
        useful_suffix = any(key.endswith(normalise(suffix)) for suffix in TECH_SUFFIXES + FUNCTION_SUFFIXES)
        if key in existing_key and len(key.split()) > 1:
            if useful_suffix and len(key.split()) >= len(existing_key.split()):
                candidates[idx] = value
            return
        if existing_key in key and len(existing_key.split()) > 1:
            existing_useful = any(existing_key.endswith(normalise(suffix)) for suffix in TECH_SUFFIXES + FUNCTION_SUFFIXES)
            if useful_suffix or (not existing_useful and len(key.split()) > len(existing_key.split())):
                candidates[idx] = value
            return
    candidates.append(value)


def _suffix_phrases(value: str, suffixes: tuple[str, ...]) -> list[str]:
    suffix_re = "|".join(re.escape(s) for s in sorted(suffixes, key=len, reverse=True))
    phrases: list[str] = []
    for m in re.finditer(rf"\b(?:[A-Za-z0-9+#-]+\s+){{1,4}}(?:{suffix_re})\b", value, re.I):
        phrase = m.group(0).strip(" .;:,/-")
        words = phrase.split()
        if 2 <= len(words) <= 5:
            for window in (3, 4, 5):
                if len(words) >= window:
                    phrases.append(" ".join(words[-window:]))
            phrases.append(phrase)
    return phrases


def _named_method_phrases(value: str) -> list[str]:
    patterns = tuple(re.escape(term).replace(r"\ ", r"\s+") for term in NAMED_TECHNICAL_METHODS) + (
        r"[A-Za-z0-9+#-]+\s+deterioration\s+detection",
        r"[A-Za-z0-9+#-]+\s+image\s+segmentation",
        r"personali[sz]ed\s+[A-Za-z0-9+#-]+\s+care",
        r"[A-Za-z0-9+#-]+\s+care\s+recommendation",
        r"temperature\s+condition\s+index",
    )
    phrases: list[str] = []
    for pattern in patterns:
        for match in re.finditer(rf"\b{pattern}\b", value, re.I):
            phrases.append(match.group(0).strip(" .;:,/-"))
    return phrases


def _clinical_problem_phrases(value: str) -> list[str]:
    phrases: list[str] = []
    hints = "deterioration|risk|prevention|rehabilitation|assessment|disease|condition|wounds?|ulcers?|falls?|fall|balance|mobility|decline|diagnosis|infection|inequality|burden|discharge|sepsis|triage"
    for explicit in ("fall prevention", "falls prevention", "mobility rehabilitation", "sepsis triage"):
        for m0 in re.finditer(rf"\b{explicit}\b", value, re.I):
            phrases.append(m0.group(0).strip(" .;:,/-"))
    for m in re.finditer(rf"\b(?:[A-Za-z0-9+#-]+\s+){{0,3}}(?:{hints})(?:\s+[A-Za-z0-9+#-]+){{0,2}}\b", value, re.I):
        phrase = m.group(0).strip(" .;:,/-")
        if 2 <= len(phrase.split()) <= 5:
            phrases.append(phrase)
    return phrases


def _capitalised_or_acronym_phrases(value: str) -> list[str]:
    phrases: list[str] = []
    for m in re.finditer(r"\b[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b|\b[A-Z][A-Z0-9]{2,12}\b|\b[A-Z][a-z]+[A-Z][A-Za-z0-9]*\b", value):
        phrases.append(m.group(0))
    if len(value.split()) <= 20:
        for m in re.finditer(r"\b[A-Z][a-z][A-Za-z0-9]{2,20}(?:\s+[A-Z][a-z][A-Za-z0-9]{2,20}){0,4}\b", value):
            phrase = m.group(0)
            if len(phrase.split()) > 1 or not _sentence_like(phrase):
                phrases.append(phrase)
    return phrases


def _concepts_from_value(value: str) -> list[str]:
    value = _clean(value)
    if not value or value == NOT_EXPLICITLY_STATED:
        return []
    concepts: list[str] = []
    identifiers = _identifier_phrases(value)
    for phrase in identifiers:
        _dedupe_add(concepts, phrase)
    for phrase in _named_method_phrases(value):
        _dedupe_add(concepts, phrase)
    for phrase in _capitalised_or_acronym_phrases(value):
        _dedupe_add(concepts, phrase)
    for m in re.finditer(r"\b[A-Za-z0-9+#-]*spectral\s+[A-Za-z0-9+#-]+\s+imaging\b", value, re.I):
        _dedupe_add(concepts, m.group(0))
    for phrase in _suffix_phrases(value, TECH_SUFFIXES + FUNCTION_SUFFIXES):
        _dedupe_add(concepts, phrase)
    if not identifiers and not _sentence_like(value) and not re.search(r"[,;]", value):
        _dedupe_add(concepts, value)
    for phrase in _clinical_problem_phrases(value):
        # Only keep broad clinical/context phrases when they include a specific modifier.
        _dedupe_add(concepts, phrase)
    for part in re.split(r"[,;]|\s+and\s+|\s+or\s+", value):
        part = _clean(part)
        if part and part != value and not _sentence_like(part):
            _dedupe_add(concepts, part)
    return concepts


def _short_concepts_from_text(snippet: str) -> list[str]:
    snippet = _clean(snippet[:1500])
    concepts: list[str] = []
    for phrase in _identifier_phrases(snippet) + _capitalised_or_acronym_phrases(snippet) + _named_method_phrases(snippet) + _suffix_phrases(snippet, TECH_SUFFIXES + FUNCTION_SUFFIXES):
        _dedupe_add(concepts, phrase)
    return concepts[:5]


def concept_class(term: str) -> str:
    key = normalise(term)
    if is_patent_identifier(term) or is_nihr_identifier(term) or is_trial_identifier(term):
        return "exact_identifier"
    if is_generic_term(term):
        return "generic_document_terms"
    if _recognised_product_or_acronym(term) or re.fullmatch(r"[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]+){1,4}", str(term).strip()):
        return "named_entities"
    if any(normalise(s) in key for s in FUNCTION_SUFFIXES):
        return "product_or_intervention_function"
    if any(normalise(method) in key for method in NAMED_TECHNICAL_METHODS) or any(key.endswith(normalise(s)) or normalise(s) in key for s in TECH_SUFFIXES):
        if any(x in key for x in ["therapeutic", "programme", "program", "platform", "device", "test", "pathway", "package", "tool"]):
            return "intervention_type"
        return "technical_method_or_mechanism"
    if any(h in key for h in ["risk", "decline", "wound", "ulcer", "stroke", "depression", "diagnosis", "infection", "inequality", "burden", "fall", "sepsis", "cancer", "discharge"]):
        return "clinical_or_social_care_problem"
    if any(h in key for h in ["older adults", "children", "care homes", "primary care", "emergency department", "community", "nhs", "social care"]):
        return "population_setting"
    return "named_entities" if _recognised_product_or_acronym(term) else "technical_method_or_mechanism"


def _term_priority(term: str) -> tuple[int, str]:
    class_order = {
        "exact_identifier": 0,
        "named_entities": 1,
        "product_or_intervention_function": 2,
        "technical_method_or_mechanism": 3,
        "intervention_type": 4,
        "clinical_or_social_care_problem": 5,
        "population_setting": 6,
        "generic_document_terms": 7,
    }
    if is_patent_identifier(term):
        return (0, normalise(term))
    if is_nihr_identifier(term):
        return (1, normalise(term))
    if is_trial_identifier(term):
        return (2, normalise(term))
    cls = concept_class(term)
    boost = -2 if normalise(term) in {"fall prevention", "falls prevention", "mobility rehabilitation", "wearable digital therapeutic"} else (-1 if any(marker in normalise(term) for marker in ["imaging", "detection", "assessment", "therapeutic", "sensor", "classifier", "rehabilitation", "prevention", "pathway", "biomarker", "test"]) else 0)
    return (class_order.get(cls, 8) + 3 + boost, normalise(term))


def _prioritise_terms(terms: list[str]) -> list[str]:
    return sorted(terms, key=_term_priority)


def _cap_terms(primary: list[str], secondary: list[str]) -> tuple[list[str], list[str]]:
    primary = _prioritise_terms(primary)
    secondary = _prioritise_terms(secondary)
    capped_primary: list[str] = []
    capped_secondary: list[str] = []
    seen: set[str] = set()
    primary_limit = MAX_QUERY_TERMS - 1 if secondary else MAX_QUERY_TERMS
    for target, terms in [(capped_primary, primary), (capped_secondary, secondary)]:
        for term in terms:
            key = normalise(term)
            if key and key not in seen and _valid_query_concept(term):
                if target is capped_primary and len(capped_primary) >= primary_limit:
                    continue
                target.append(term)
                seen.add(key)
            if len(capped_primary) + len(capped_secondary) >= MAX_QUERY_TERMS:
                return capped_primary, capped_secondary
    return capped_primary, capped_secondary


def build_similarity_query(facts: ApplicationFacts, snippets: list[str] | None = None) -> SimilarityQuery:
    primary: list[str] = []
    secondary: list[str] = []
    for field in [
        "project_title",
        "application_claimed_call",
        "product_or_intervention",
        "acronym_or_short_name",
        "technology_type",
        "target_population",
        "clinical_or_social_care_need",
        "mechanism_of_action",
        "methodology",
        "market_or_impact_evidence",
        "regulatory_plan",
        "references_detected",
        "health_economics_plan",
        "next_stage_plan",
    ]:
        for concept in _concepts_from_value(str(getattr(facts, field, NOT_EXPLICITLY_STATED))):
            _dedupe_add(primary, concept)
    # Population/setting are weak: keep only if tied to a specific problem or technical phrase.
    for field in ["target_population", "sites_or_setting", "market_or_impact_evidence", "comparator_or_control"]:
        for concept in _concepts_from_value(str(getattr(facts, field, NOT_EXPLICITLY_STATED))):
            if any(suffix in normalise(concept) for suffix in ["risk", "assessment", "rehabilitation", "service", "services", "clinic"]):
                _dedupe_add(secondary, concept)
    for endpoint in facts.endpoints:
        for concept in _concepts_from_value(endpoint):
            _dedupe_add(secondary, concept)
    for snippet in snippets or []:
        for phrase in _short_concepts_from_text(snippet):
            _dedupe_add(secondary, phrase)
    primary, secondary = _cap_terms(primary, secondary)
    terms = primary + secondary
    query = " AND ".join(f'"{t}"' if " " in t else t for t in terms) if len(terms) >= 2 else ""
    reasoning = ["Selected short product, acronym, technical-method and specific function noun phrases; demographic-only, setting-only, generic and truncated terms are excluded."]
    if len(terms) < 2:
        reasoning.append("At least two meaningful concepts are required before live API searching.")
    return SimilarityQuery(primary_terms=primary, secondary_terms=secondary, excluded_terms=sorted(GENERIC_DOCUMENT_TERMS), query_string=query, extraction_reasoning=reasoning)
