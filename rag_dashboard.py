"""Seven-subsystem RAG dashboard with relevant-evidence hard validation."""
from __future__ import annotations

from collections import defaultdict

from schemas import NOT_EXPLICITLY_STATED, RAG_SUBSYSTEMS, ApplicationFacts, ChecklistItem

AREA_TO_SUBSYSTEM = {
    "Eligibility": "Eligibility",
    "Application Details": "Eligibility",
    "Lead Applicant and Research Team": "Eligibility",
    "Clinical Validation": "Clinical Validation",
    "Health Economics": "Health Economics",
    "Patient and Public Involvement / Working with People and Communities": "Patient and Public Involvement",
    "Research Inclusion": "Research Inclusion",
    "Project Management": "Project Management",
    "Budget and Finance": "Finance",
    "Uploads": "Project Management",
}


def _has(value: object) -> bool:
    if isinstance(value, list):
        return bool(value)
    return bool(value and value != NOT_EXPLICITLY_STATED)


def _text(*values: object) -> str:
    parts = []
    for value in values:
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif _has(value):
            parts.append(str(value))
    return " ".join(parts).lower()


def _score_from_checks(checks: list[bool]) -> tuple[int, str]:
    total = len(checks)
    met = sum(checks)
    if met == 0:
        return 0, f"{met}/{total}"
    return round((met / total) * 5), f"{met}/{total}"


def _rag(score: int) -> str:
    if score >= 4:
        return "GREEN"
    if score >= 2:
        return "AMBER"
    return "RED"


def build_rag_dashboard(items: list[ChecklistItem], facts: ApplicationFacts) -> list[dict]:
    grouped: dict[str, list[ChecklistItem]] = defaultdict(list)
    for item in items:
        subsystem = AREA_TO_SUBSYSTEM.get(item.area)
        if subsystem:
            grouped[subsystem].append(item)

    he_text = _text(facts.health_economics_plan, facts.comparator_or_control, facts.endpoints)
    ppie_text = _text(facts.ppie_plan, getattr(facts, "ppie_leadership_evidence", NOT_EXPLICITLY_STATED))
    pm_text = _text(facts.project_management_plan, facts.work_packages, facts.milestones, facts.uploads_detected)
    has_gantt_or_workplan = bool(facts.work_packages) or bool(facts.milestones) or any("gantt" in str(u).lower() or "workplan" in str(u).lower() for u in facts.uploads_detected)
    has_ppie_leadership = any(x in ppie_text for x in ["lead", "co-applicant", "coordinat", "ms ", "mr ", "dr "])
    finance_text = _text(facts.finance_or_budget_evidence)

    checks_by_subsystem = {
        "Eligibility": [
            _has(facts.applicant_or_lead), _has(facts.contracting_organisation), _has(facts.partners),
            _has(facts.application_claimed_call), _has(facts.trl_evidence) or _has(facts.current_trl_or_stage), _has(facts.market_or_impact_evidence),
        ],
        "Clinical Validation": [
            _has(facts.study_design), _has(facts.sample_size), _has(facts.sites_or_setting), bool(facts.endpoints),
            _has(facts.regulatory_plan), _has(facts.next_stage_plan),
        ],
        "Health Economics": [
            _has(facts.health_economics_plan), "perspective" in he_text, any(x in he_text for x in ["comparator", "usual care", "current care"]),
            any(x in he_text for x in ["resource use", "micro-cost", "cost"]), any(x in he_text for x in ["model", "sensitivity", "scenario"]),
            "health economist" in he_text,
        ],
        "Patient and Public Involvement": [
            _has(facts.ppie_plan) or _has(getattr(facts, "ppie_leadership_evidence", NOT_EXPLICITLY_STATED)),
            has_ppie_leadership or "advisory group" in ppie_text,
            any(x in ppie_text for x in ["payment", "expenses", "support"]), any(x in ppie_text for x in ["shaped", "co-design", "changed"]),
        ],
        "Research Inclusion": [
            _has(facts.research_inclusion_plan), any(x in _text(facts.research_inclusion_plan) for x in ["underserved", "underrepresented", "inequal", "digital exclusion"]),
            any(x in _text(facts.research_inclusion_plan) for x in ["sex", "gender"]), any(x in _text(facts.research_inclusion_plan) for x in ["accessib", "interpreter", "disability"]),
            "cost" in _text(facts.research_inclusion_plan),
        ],
        "Project Management": [
            _has(facts.project_management_plan), bool(facts.work_packages), bool(facts.milestones), has_gantt_or_workplan,
            any(x in pm_text for x in ["risk", "governance", "contingenc"]), _has(facts.duration_months),
        ],
        "Finance": [
            _has(facts.finance_or_budget_evidence), any(x in finance_text for x in ["staff", "equipment", "travel", "cost category", "budget section"]),
            "justification" in finance_text, "current rates" in finance_text, "scheme cap" in finance_text,
            any(x in finance_text for x in ["acord", "soecat", "support costs", "treatment costs"]),
        ],
    }

    rows: list[dict] = []
    for subsystem in RAG_SUBSYSTEMS:
        score, evidenced = _score_from_checks(checks_by_subsystem[subsystem])
        rag = _rag(score)
        warnings: list[str] = []
        if subsystem == "Eligibility" and "mismatch" in _text(facts.contradictions_or_uncertainties):
            rag = "RED"; score = 0; warnings.append("Funding mismatch forces Eligibility RED.")
        if subsystem == "Finance" and not _has(facts.finance_or_budget_evidence):
            rag = "RED"; score = 0; warnings.append("No budget evidence forces Finance RED.")
        if subsystem == "Finance" and rag == "GREEN" and score < 5:
            rag = "AMBER"; warnings.append("Incomplete budget evidence prevents Finance GREEN.")
        if subsystem == "Patient and Public Involvement" and not (_has(facts.ppie_plan) or _has(getattr(facts, "ppie_leadership_evidence", NOT_EXPLICITLY_STATED))):
            rag = "RED"; score = 0; warnings.append("No PPIE evidence forces PPIE RED.")
        if subsystem == "Patient and Public Involvement" and _has(getattr(facts, "ppie_leadership_evidence", NOT_EXPLICITLY_STATED)) and rag == "RED":
            rag = "AMBER"; score = max(score, 2); warnings.append("Named PPI coordination prevents PPIE RED but needs payment/support and dedicated-lead confirmation.")
        if subsystem == "Patient and Public Involvement" and rag == "GREEN" and (not has_ppie_leadership or not any(x in ppie_text for x in ["payment", "expenses", "support"])):
            rag = "AMBER"; warnings.append("PPIE payment/support or contributor impact needs confirmation before PPIE GREEN.")
        if subsystem == "Health Economics" and rag == "GREEN" and not ("perspective" in he_text and any(x in he_text for x in ["comparator", "usual care", "current care"]) and "cost" in he_text):
            rag = "AMBER"; warnings.append("No health economics perspective/comparator/cost-outcome plan prevents Health Economics GREEN.")
        if subsystem == "Project Management" and rag == "GREEN" and not (has_gantt_or_workplan and bool(facts.milestones)):
            rag = "AMBER"; warnings.append("Project governance, risk register or contingencies need confirmation before Project Management GREEN.")
        if rag == "GREEN" and score == 0:
            rag = "GREY"; warnings.append("No GREEN without relevant evidence.")

        sub_items = grouped.get(subsystem, [])
        default_gap = "No major gap identified from relevant evidence." if rag == "GREEN" else f"{subsystem} is {rag}; verify the missing checks shown by {evidenced} evidence coverage."
        main_gap = next((item.gap for item in sub_items if item.rag in {"RED", "AMBER", "GREY"}), default_gap)
        if rag == "AMBER" and main_gap == "No major gap identified from relevant evidence.":
            main_gap = default_gap
        priority_action = next((item.action for item in sub_items if item.rag in {"RED", "AMBER", "GREY"}), "Review consistency with application evidence and call guidance.")
        if subsystem == "Patient and Public Involvement" and has_ppie_leadership and rag != "GREEN":
            main_gap = "PPI leadership is evidenced; verify PPIE payment/support costs and public contributor impact."
            priority_action = "Verify PPIE payment/support costs and public contributor impact."
        if subsystem == "Project Management" and has_gantt_or_workplan and rag != "GREEN":
            main_gap = "Gantt/workplan evidence is present; verify governance, risk register and contingencies."
            priority_action = "Verify project governance, risk register and contingencies."
        rows.append({"Subsystem": subsystem, "RAG": rag, "Score 0-5": score, "Checks evidenced": evidenced, "Main gap": main_gap, "Priority action": priority_action, "hard_validation_warnings": warnings})
    return rows
