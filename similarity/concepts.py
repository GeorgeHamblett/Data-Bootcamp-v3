"""Dynamic concept extraction for external similarity scoring."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

from schemas import ApplicationFacts, NOT_EXPLICITLY_STATED
from similarity.query_builder import normalise, is_generic_term

GENERIC_DOMAIN_TERMS = {
    "software as a medical device",
    "medical device",
    "clinical ai",
    "digital health",
    "decision support",
    "artificial intelligence",
    "ai",
    "platform",
    "application",
    "app",
}

INFRASTRUCTURE_TERMS = {
    "isolated execution",
    "execution environment",
    "execution environments",
    "isolation level",
    "isolation levels",
    "resource allocation",
    "computing resource",
    "computing resources",
    "deployment architecture",
    "edge ai",
    "edge artificial intelligence",
}

UNRELATED_DOMAIN_SIGNALS = {
    "drug_biologic": {
        "inhibitor", "inhibitors", "compound", "compounds", "therapeutic compound", "dose", "pharmaceutical",
        "small molecule", "agonist", "antagonist", "enzyme", "receptor",
    },
    "gene_cell_animal": {
        "gene", "genes", "protein", "mutation", "cell", "cells", "transgenic", "mouse", "mice", "animal model",
        "prion", "cjd", "senescence", "metabolic defect", "biomarker",
    },
    "computing_infrastructure": INFRASTRUCTURE_TERMS,
    "unrelated_engineering": {"valve", "actuator", "circuit", "semiconductor", "gearbox", "battery terminal"},
}

TECH_SUFFIXES = (
    "imaging", "assessment", "engine", "algorithm", "platform", "software", "device", "sensor", "model",
    "decision support", "therapeutic", "monitor", "monitoring", "classifier", "measurement",
)
FUNCTION_SUFFIXES = (
    "detection", "monitoring", "prediction", "decision support", "risk score", "feedback", "escalation",
    "assessment", "coaching", "measurement", "prevention", "rehabilitation", "support",
)
CLINICAL_HINTS = (
    "deterioration", "risk", "prevention", "rehabilitation", "disease", "condition", "syndrome", "wound",
    "falls", "fall", "balance", "mobility", "pain", "infection", "cancer", "diabetes", "stroke", "frailty",
)
SETTING_HINTS = ("community", "clinic", "clinics", "hospital", "nursing", "nhs", "care home", "patients", "adults", "population")

@dataclass
class ConceptProfile:
    named_entities: list[str] = field(default_factory=list)
    technical_method_terms: list[str] = field(default_factory=list)
    clinical_problem_terms: list[str] = field(default_factory=list)
    product_function_terms: list[str] = field(default_factory=list)
    population_setting_terms: list[str] = field(default_factory=list)
    generic_domain_terms: list[str] = field(default_factory=list)
    infrastructure_terms: list[str] = field(default_factory=list)
    domain_signals: dict[str, list[str]] = field(default_factory=dict)
    metadata_incomplete: bool = False

    def specific_groups(self) -> dict[str, list[str]]:
        return {
            "named_entity": self.named_entities,
            "technical_method": self.technical_method_terms,
            "clinical_problem": self.clinical_problem_terms,
            "product_function": self.product_function_terms,
            "population_setting": self.population_setting_terms,
        }


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        item = re.sub(r"\s+", " ", str(item)).strip(" .;:,/-")
        key = normalise(item)
        if key and key not in seen and not is_generic_term(item):
            seen.add(key)
            out.append(item)
    return out


def _dedupe_all(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        item = re.sub(r"\s+", " ", str(item)).strip(" .;:,/-")
        key = normalise(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _text_from_facts(facts: ApplicationFacts, fields: list[str]) -> str:
    chunks: list[str] = []
    for field_name in fields:
        value = getattr(facts, field_name, "")
        if isinstance(value, list):
            chunks.extend(str(v) for v in value)
        elif value and value != NOT_EXPLICITLY_STATED:
            chunks.append(str(value))
    return ". ".join(chunks)


def _noun_phrases(text: str, suffixes: tuple[str, ...]) -> list[str]:
    phrases: list[str] = []
    suffix_re = "|".join(re.escape(s) for s in sorted(suffixes, key=len, reverse=True))
    pattern = rf"\b(?:[A-Za-z0-9+#-]+\s+){{0,3}}(?:{suffix_re})\b"
    for match in re.finditer(pattern, text, re.I):
        phrase = match.group(0).strip(" .;:,/-")
        words = phrase.split()
        if 2 <= len(words) <= 5 and words[0].lower() not in {"the", "a", "an", "as", "and", "or", "plus", "for", "with"} and not all(normalise(w) in {"the", "a", "an", "and", "or"} for w in words):
            phrases.append(phrase)
    return _dedupe(phrases)


def _capitalised_entities(text: str) -> list[str]:
    entities: list[str] = []
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9]*(?:[-][A-Za-z0-9]+)+\b|\b[A-Z][A-Z0-9]{2,12}\b", text):
        entities.append(match.group(0))
    # product-like title case phrases, but avoid normal sentence starters by requiring a product suffix/acronym/hyphen nearby.
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2}\b", text):
        phrase = match.group(0)
        if re.search(r"[-0-9]", phrase) or any(s in phrase.lower() for s in ("tool", "engine", "platform", "device", "app")):
            entities.append(phrase)
    return _dedupe(entities)[:12]


def _generic_terms(text: str) -> list[str]:
    key_text = normalise(text)
    terms = []
    for term in GENERIC_DOMAIN_TERMS:
        key = normalise(term)
        if key == "ai":
            if re.search(r"\bAI\b|artificial intelligence", text):
                terms.append("AI")
        elif key in key_text:
            terms.append(term)
    return _dedupe_all(terms)


def _infra_terms(text: str) -> list[str]:
    key_text = normalise(text)
    return _dedupe_all(term for term in INFRASTRUCTURE_TERMS if normalise(term) in key_text)


def _domain_signals(text: str) -> dict[str, list[str]]:
    key_text = normalise(text)
    found: dict[str, list[str]] = {}
    for category, terms in UNRELATED_DOMAIN_SIGNALS.items():
        hits = _dedupe_all(term for term in terms if re.search(r"\b" + re.escape(normalise(term)) + r"\b", key_text))
        if hits:
            found[category] = hits
    return found


def _clinical_terms(text: str) -> list[str]:
    phrases: list[str] = []
    for hint in CLINICAL_HINTS:
        for match in re.finditer(rf"\b(?:[A-Za-z0-9+#-]+\s+){{0,3}}{re.escape(hint)}(?:\s+[A-Za-z0-9+#-]+){{0,2}}\b", text, re.I):
            phrase = match.group(0).strip(" .;:,/-")
            if 2 <= len(phrase.split()) <= 6:
                phrases.append(phrase)
    return _dedupe(phrases)


def _setting_terms(text: str) -> list[str]:
    phrases: list[str] = []
    for hint in SETTING_HINTS:
        for match in re.finditer(rf"\b(?:[A-Za-z0-9+#-]+\s+){{0,3}}{re.escape(hint)}(?:\s+[A-Za-z0-9+#-]+){{0,2}}\b", text, re.I):
            phrase = match.group(0).strip(" .;:,/-")
            if 2 <= len(phrase.split()) <= 6:
                phrases.append(phrase)
    return _dedupe(phrases)


def extract_similarity_concepts(facts: ApplicationFacts) -> ConceptProfile:
    named_text = _text_from_facts(facts, ["project_title", "product_or_intervention", "acronym_or_short_name"])
    technical_text = _text_from_facts(facts, ["technology_type", "product_or_intervention", "methodology", "study_design", "regulatory_plan", "mechanism_of_action"])
    clinical_text = _text_from_facts(facts, ["clinical_or_social_care_need", "target_population", "endpoints", "market_or_impact_evidence"])
    function_text = _text_from_facts(facts, ["product_or_intervention", "clinical_or_social_care_need", "endpoints", "study_design", "methodology"])
    setting_text = _text_from_facts(facts, ["target_population", "sites_or_setting"])
    all_text = " ".join([named_text, technical_text, clinical_text, function_text, setting_text])
    return ConceptProfile(
        named_entities=_dedupe([facts.acronym_or_short_name, facts.product_or_intervention, facts.project_title] + _capitalised_entities(named_text)),
        technical_method_terms=_noun_phrases(technical_text, TECH_SUFFIXES),
        clinical_problem_terms=_clinical_terms(clinical_text),
        product_function_terms=_noun_phrases(function_text, FUNCTION_SUFFIXES),
        population_setting_terms=_setting_terms(setting_text),
        generic_domain_terms=_generic_terms(all_text),
        infrastructure_terms=_infra_terms(all_text),
        domain_signals=_domain_signals(all_text),
    )


def extract_metadata_concepts(title: str = "", abstract: str = "", raw: Any = None) -> ConceptProfile:
    raw_text = metadata_text(title, abstract, raw)
    title_abstract_missing = not normalise(f"{title} {abstract}")
    return ConceptProfile(
        named_entities=_capitalised_entities(f"{title} {abstract}"),
        technical_method_terms=_noun_phrases(raw_text, TECH_SUFFIXES),
        clinical_problem_terms=_clinical_terms(raw_text),
        product_function_terms=_noun_phrases(raw_text, FUNCTION_SUFFIXES),
        population_setting_terms=_setting_terms(raw_text),
        generic_domain_terms=_generic_terms(raw_text),
        infrastructure_terms=_infra_terms(raw_text),
        domain_signals=_domain_signals(raw_text),
        metadata_incomplete=title_abstract_missing and bool(normalise(str(raw or ""))),
    )


def metadata_text(title: str = "", abstract: str = "", raw: Any = None) -> str:
    chunks = [str(title or ""), str(abstract or "")]
    if isinstance(raw, dict):
        for key in ("title", "abstract", "snippet", "description", "metadata_text", "applicants", "organisation", "organization"):
            value = raw.get(key)
            if isinstance(value, list):
                chunks.extend(str(v) for v in value)
            elif value:
                chunks.append(str(value))
    elif raw:
        chunks.append(str(raw))
    return " ".join(chunks)
