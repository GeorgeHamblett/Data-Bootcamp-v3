"""Shared schemas and constants for the RSS/NIHR checklist assistant."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

NOT_EXPLICITLY_STATED = "Not explicitly stated"

GuidanceSource = Literal[
    "specific_call",
    "programme_guidance",
    "nihr_domestic",
    "rss_playbook",
    "derived_reviewer_check",
]

CHECKLIST_AREAS = [
    "Summary Information",
    "Lead Applicant and Research Team",
    "Application Details",
    "Eligibility",
    "Clinical Validation",
    "Health Economics",
    "Patient and Public Involvement / Working with People and Communities",
    "Research Inclusion",
    "Project Management",
    "Budget and Finance",
    "Uploads",
    "Acknowledgement and Conflicts",
    "Similarity / Novelty / Prior Work",
]

RAG_SUBSYSTEMS = [
    "Eligibility",
    "Clinical Validation",
    "Health Economics",
    "Patient and Public Involvement",
    "Research Inclusion",
    "Project Management",
    "Finance",
]

SOURCE_LABELS = {
    "specific_call": "Specific funding call",
    "programme_guidance": "Programme guidance",
    "nihr_domestic": "NIHR domestic guidance",
    "rss_playbook": "RSS PDA playbook",
    "derived_reviewer_check": "Derived reviewer check",
}

@dataclass
class GuidanceDocument:
    path: str
    name: str
    source: GuidanceSource
    text: str
    is_application_example: bool = False

@dataclass
class Requirement:
    requirement_id: str
    source: GuidanceSource
    source_section: str
    checklist_area: str
    requirement_text: str
    mandatory_status: str = "recommended"
    evidence_needed_from_application: str = "Application evidence addressing the requirement."
    overrides_general_guidance: bool = False

    @property
    def source_guidance(self) -> str:
        return SOURCE_LABELS.get(self.source, self.source)

@dataclass
class Evidence:
    source_document: str
    section_or_context: str
    quote: str
    why_it_matters: str

@dataclass
class ApplicationFacts:
    project_title: str = NOT_EXPLICITLY_STATED
    application_claimed_call: str = NOT_EXPLICITLY_STATED
    product_or_intervention: str = NOT_EXPLICITLY_STATED
    acronym_or_short_name: str = NOT_EXPLICITLY_STATED
    applicant_or_lead: str = NOT_EXPLICITLY_STATED
    contracting_organisation: str = NOT_EXPLICITLY_STATED
    partners: list[str] = field(default_factory=list)
    target_population: str = NOT_EXPLICITLY_STATED
    clinical_or_social_care_need: str = NOT_EXPLICITLY_STATED
    technology_type: str = NOT_EXPLICITLY_STATED
    current_trl_or_stage: str = NOT_EXPLICITLY_STATED
    target_trl_or_stage: str = NOT_EXPLICITLY_STATED
    trl_evidence: str = NOT_EXPLICITLY_STATED
    study_design: str = NOT_EXPLICITLY_STATED
    methodology: str = NOT_EXPLICITLY_STATED
    sample_size: str = NOT_EXPLICITLY_STATED
    sites_or_setting: str = NOT_EXPLICITLY_STATED
    duration_months: str = NOT_EXPLICITLY_STATED
    work_packages: list[str] = field(default_factory=list)
    milestones: list[str] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)
    comparator_or_control: str = NOT_EXPLICITLY_STATED
    mechanism_of_action: str = NOT_EXPLICITLY_STATED
    data_sources: str = NOT_EXPLICITLY_STATED
    regulatory_plan: str = NOT_EXPLICITLY_STATED
    health_economics_plan: str = NOT_EXPLICITLY_STATED
    ppie_plan: str = NOT_EXPLICITLY_STATED
    ppie_leadership_evidence: str = NOT_EXPLICITLY_STATED
    research_inclusion_plan: str = NOT_EXPLICITLY_STATED
    project_management_plan: str = NOT_EXPLICITLY_STATED
    finance_or_budget_evidence: str = NOT_EXPLICITLY_STATED
    uploads_detected: list[str] = field(default_factory=list)
    references_detected: str = NOT_EXPLICITLY_STATED
    ai_use_declaration: str = NOT_EXPLICITLY_STATED
    conflicts_declaration: str = NOT_EXPLICITLY_STATED
    market_or_impact_evidence: str = NOT_EXPLICITLY_STATED
    next_stage_plan: str = NOT_EXPLICITLY_STATED
    contradictions_or_uncertainties: list[str] = field(default_factory=list)
    evidence: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class ChecklistItem:
    area: str
    requirement: str
    source_guidance: str
    status: str
    rag: str
    evidence: list[str]
    gap: str
    action: str
    confidence: float = 0.0

    def to_row(self) -> dict[str, Any]:
        return {
            "Checklist Area": self.area,
            "Requirement": self.requirement,
            "Source Guidance": self.source_guidance,
            "Status": self.status,
            "RAG": self.rag,
            "Evidence from application": "; ".join(self.evidence) if self.evidence else NOT_EXPLICITLY_STATED,
            "Gap / action needed": self.action if self.action else self.gap,
        }

@dataclass
class SimilarityQuery:
    primary_terms: list[str]
    secondary_terms: list[str]
    excluded_terms: list[str]
    query_string: str
    extraction_reasoning: list[str]

    @property
    def meaningful_term_count(self) -> int:
        return len([t for t in self.primary_terms + self.secondary_terms if t.strip()])
