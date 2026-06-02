"""Shared dataclasses and constants for the RSS/NIHR checklist assistant."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

NOT_EXPLICITLY_STATED = "Not explicitly stated"

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
    source_type: str
    source_label: str
    text: str
    is_application_example: bool = False

@dataclass
class Requirement:
    requirement_id: str
    source: str
    source_section: str
    checklist_area: str
    requirement_text: str
    mandatory_status: str = "recommended"
    evidence_needed_from_application: str = "Application evidence addressing the requirement."
    overrides_general_guidance: bool = False

    @property
    def source_label(self) -> str:
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
    regulatory_plan: str = NOT_EXPLICITLY_STATED
    health_economics_plan: str = NOT_EXPLICITLY_STATED
    ppie_plan: str = NOT_EXPLICITLY_STATED
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
    evidence: list[Evidence] = field(default_factory=list)

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

@dataclass
class RagSubsystem:
    subsystem: str
    rag: str
    score_0_5: int
    checks_evidenced: str
    main_gap: str
    priority_action: str
    hard_validation_warnings: list[str] = field(default_factory=list)

@dataclass
class SimilarityQuery:
    primary_terms: list[str]
    secondary_terms: list[str]
    excluded_terms: list[str]
    query_string: str
    extraction_reasoning: list[str]

@dataclass
class SimilarityResult:
    source: str
    status: str
    query_terms_used: list[str]
    matches_found: int
    top_match: str
    score: float
    risk: str
    why_relevant: str
    link_or_id: str
