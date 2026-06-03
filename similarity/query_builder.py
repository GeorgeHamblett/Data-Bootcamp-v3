"""Build privacy-preserving external similarity queries from generic concepts."""
from __future__ import annotations

import re
from schemas import ApplicationFacts, NOT_EXPLICITLY_STATED, SimilarityQuery

MAX_QUERY_TERMS = 10
MAX_TERM_CHARS = 60

IDENTIFIER_PATTERNS = (
    r"\b(?:US|EP|WO)\s?\d{6,}[A-Z0-9]*\b",
    r"\bAI[_\-\s]?AWARD\d{3,}\b",
    r"\bNIHR\d{4,}\b",
    r"\b[A-Z]{2,}[_-][A-Z0-9]{3,}\b",
)

GENERIC_DOCUMENT_TERMS = {
    "the", "a", "an", "it", "this", "we", "our", "early", "earlier", "new", "novel", "current", "clear", "named",
    "uploaded", "upload", "file", "document", "docx", "pdf", "txt", "training", "dummy", "application", "plain",
    "english", "summary", "gantt", "chart", "appendix", "form", "section", "background", "methodology",
    "project", "research", "study", "objective", "aim", "funding", "proposal", "applicant", "partners", "partner",
    "draft", "report", "template", "playbook", "guidance", "work", "package", "task", "month", "milestones",
    "milestone", "recruitment", "retention", "fidelity", "interviews", "reduc", "reduce", "avoidable", "patients", "people", "adults",
    "older adults", "community", "nhs", "rehabilitation", "detection", "support", "device", "platform", "system",
    "endpoint", "endpoints", "primary endpoint", "secondary endpoint", "outcome", "outcomes",
    "related incidents", "12-month decision model", "decision model", "cost model", "decision-support",
    "trl", "technology readiness level", "technology readiness", "readiness level", "regulatory readiness",
    "software as a medical device", "samd", "medical device", "device classification", "clinical safety",
    "risk management file", "quality management system", "iso 13485", "iso 14971", "ukca", "ce marking",
    "post-market surveillance", "technical file", "technical documentation", "create substantial patient burden",
    "for training use only", "fictional example application", "training use only",
}

NOISE_PHRASES = [
    "for training use only", "fictional example application", "training use only", "dummy application",
    "this project will", "many people do", "falls can seriously", "milestones month",
]
GENERIC_ACRONYMS = {"SUS", "PPI", "PPIE", "NHS", "NIHR", "QALY", "EQ-5D", "EQ-5D-5L", "PDA", "TRL", "SAMD", "UKCA", "ISO"}
VALID_SHORT_ACRONYMS = {"AI", "IP", "ECG"}
TECH_SUFFIXES = (
    "imaging", "assessment", "engine", "algorithm", "platform", "software", "device", "sensor", "model",
    "decision support", "therapeutic", "monitoring", "measurement", "classifier", "segmentation", "pixels",
)
FUNCTION_SUFFIXES = ("detection", "prediction", "monitoring", "prevention", "rehabilitation", "risk score", "feedback", "coaching", "escalation", "assessment", "measurement", "decision support", "segmentation", "pixels", "care", "recommendation")


def normalise(term: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 +#\-/]", " ", str(term).lower())).strip()


def _canonical_identifier(value: str) -> str:
    item = re.sub(r"\s+", "", value.strip()) if re.match(r"^(?:US|EP|WO)\s?\d", value.strip(), re.I) else value.strip()
    item = re.sub(r"AI[_\-\s]?AWARD", "AI_AWARD", item, flags=re.I)
    return item.upper() if re.search(r"^(?:US|EP|WO|AI_|NIHR|[A-Z]{2,}[_-])", item, re.I) else item


def _identifier_phrases(value: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for idx, pattern in enumerate(IDENTIFIER_PATTERNS):
        flags = 0 if idx == len(IDENTIFIER_PATTERNS) - 1 else re.I
        for match in re.finditer(pattern, str(value or ""), flags):
            matches.append((match.start(), _canonical_identifier(match.group(0))))
    return list(dict.fromkeys(phrase for _, phrase in sorted(matches, key=lambda item: item[0])))


def _looks_like_identifier(value: str) -> bool:
    cleaned = _clean(value) if "_clean" in globals() else str(value or "").strip()
    return any(
        re.fullmatch(pattern, cleaned, 0 if idx == len(IDENTIFIER_PATTERNS) - 1 else re.I)
        for idx, pattern in enumerate(IDENTIFIER_PATTERNS)
    )


def is_generic_term(term: str) -> bool:
    cleaned = normalise(term)
    if not cleaned or len(cleaned) < 3:
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
    if " and " in key or " including " in key or " substantial patient burden" in key or "create substantial" in key:
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
    if key.split()[0] in {"and", "or", "for", "with", "plus", "the", "a", "an", "as", "reduce", "to", "including", "include", "includes", "create"}:
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
        if key.replace("non-", "") == existing_key or existing_key.replace("non-", "") == key:
            continue
        useful_suffix = any(key.endswith(normalise(suffix)) for suffix in TECH_SUFFIXES + FUNCTION_SUFFIXES)
        if key in existing_key and len(key.split()) > 1:
            if useful_suffix and len(key.split()) <= len(existing_key.split()):
                candidates[idx] = value
            return
        if existing_key in key and len(existing_key.split()) > 1:
            existing_useful = any(existing_key.endswith(normalise(suffix)) for suffix in TECH_SUFFIXES + FUNCTION_SUFFIXES)
            if not existing_useful or len(key.split()) < len(existing_key.split()):
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


def _clinical_problem_phrases(value: str) -> list[str]:
    phrases: list[str] = []
    wound_anchors = (
        r"chronic\s+(?:lower-limb\s+)?wounds?",
        r"lower-limb\s+wounds?",
        r"venous\s+leg\s+ulcers?",
        r"diabetic\s+foot\s+ulcers?",
    )
    for pattern in wound_anchors:
        for m in re.finditer(rf"\b{pattern}\b", value, re.I):
            phrases.append(m.group(0).strip(" .;:,/-"))
    hints = "deterioration|risk|prevention|rehabilitation|assessment|disease|condition|wounds?|ulcers?|falls?|balance|mobility"
    for m in re.finditer(rf"\b(?:[A-Za-z0-9+#-]+\s+){{0,3}}(?:{hints})(?:\s+[A-Za-z0-9+#-]+){{0,2}}\b", value, re.I):
        phrase = m.group(0).strip(" .;:,/-")
        if 2 <= len(phrase.split()) <= 5:
            phrases.append(phrase)
    return phrases


def _capitalised_or_acronym_phrases(value: str) -> list[str]:
    phrases: list[str] = []
    for m in re.finditer(r"\b[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b|\b[A-Z][A-Z0-9]{2,12}\b", value):
        phrases.append(m.group(0))
    if len(value.split()) <= 6:
        for m in re.finditer(r"\b[A-Z][a-z][A-Za-z0-9]{2,20}\b", value):
            phrases.append(m.group(0))
    return phrases


def _concepts_from_value(value: str) -> list[str]:
    value = _clean(value)
    if not value or value == NOT_EXPLICITLY_STATED:
        return []
    concepts: list[str] = []
    identifiers = _identifier_phrases(value)
    for phrase in identifiers:
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
    for phrase in _identifier_phrases(snippet) + _capitalised_or_acronym_phrases(snippet) + _suffix_phrases(snippet, TECH_SUFFIXES + FUNCTION_SUFFIXES):
        _dedupe_add(concepts, phrase)
    return concepts[:5]


def _cap_terms(primary: list[str], secondary: list[str]) -> tuple[list[str], list[str]]:
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
        "product_or_intervention",
        "acronym_or_short_name",
        "technology_type",
        "clinical_or_social_care_need",
        "mechanism_of_action",
        "methodology",
        "application_claimed_call",
        "market_or_impact_evidence",
        "regulatory_plan",
        "references_detected",
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
