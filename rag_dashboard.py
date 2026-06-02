"""RAG dashboard generation and hard validation."""
from __future__ import annotations

from dataclasses import asdict

from schemas import ApplicationFacts, ChecklistItem, RagSubsystem, RAG_SUBSYSTEMS, NOT_EXPLICITLY_STATED

AREA_TO_SUBSYSTEM = {
    "Eligibility": "Eligibility",
    "Clinical Validation": "Clinical Validation",
    "Health Economics": "Health Economics",
    "Patient and Public Involvement / Working with People and Communities": "Patient and Public Involvement",
    "Research Inclusion": "Research Inclusion",
    "Project Management": "Project Management",
    "Budget and Finance": "Finance",
}


def _has(value) -> bool:
    return bool(value) and value != NOT_EXPLICITLY_STATED


def _base_rag(items: list[ChecklistItem]) -> str:
    if not items:
        return "GREY"
    rags = {i.rag for i in items}
    if "RED" in rags:
        return "RED"
    if "AMBER" in rags:
        return "AMBER"
    if "GREEN" in rags:
        return "GREEN"
    return "GREY"


def _score(rag: str, evidenced: int, total: int) -> int:
    if total == 0:
        return 0
    ratio = evidenced / total
    cap = {"GREEN": 5, "AMBER": 3, "RED": 2, "GREY": 1}.get(rag, 0)
    return min(cap, round(ratio * 5))


def build_rag_dashboard(items: list[ChecklistItem], facts: ApplicationFacts, funding_mismatch: bool = False) -> list[RagSubsystem]:
    subsystems: list[RagSubsystem] = []
    for subsystem in RAG_SUBSYSTEMS:
        sub_items = [i for i in items if AREA_TO_SUBSYSTEM.get(i.area) == subsystem]
        evidenced = sum(1 for i in sub_items if i.evidence)
        total = len(sub_items)
        rag = _base_rag(sub_items)
        warnings: list[str] = []

        if subsystem == "Eligibility" and funding_mismatch:
            rag = "RED"; warnings.append("Funding mismatch forces Eligibility RED.")
        if subsystem == "Finance" and not _has(facts.finance_or_budget_evidence):
            rag = "RED"; warnings.append("No budget evidence forces Finance RED.")
        if subsystem == "Patient and Public Involvement" and not _has(facts.ppie_plan):
            rag = "RED"; warnings.append("No PPIE evidence forces PPIE RED.")
        if subsystem == "Patient and Public Involvement" and rag == "GREEN" and "lead" not in facts.ppie_plan.lower():
            rag = "AMBER"; warnings.append("No named PPI lead prevents PPIE GREEN.")
        if subsystem == "Health Economics" and rag == "GREEN":
            he = facts.health_economics_plan.lower()
            if not all(term in he for term in ["perspective", "comparator"]) or not ("cost" in he and "outcome" in he):
                rag = "AMBER"; warnings.append("No health economics perspective/comparator/cost-outcome plan prevents GREEN.")
        if subsystem == "Project Management" and rag == "GREEN":
            pm = (facts.project_management_plan + " " + " ".join(facts.uploads_detected)).lower()
            if "gantt" not in pm and "milestone" not in pm:
                rag = "AMBER"; warnings.append("No Gantt/project management evidence prevents GREEN.")
        if rag == "GREEN" and evidenced == 0:
            rag = "RED"; warnings.append("No GREEN without evidence.")

        first_gap = next((i.gap for i in sub_items if i.rag in {"RED", "AMBER", "GREY"}), "No major gap identified in extracted evidence.")
        first_action = next((i.action for i in sub_items if i.rag in {"RED", "AMBER", "GREY"}), "Verify evidence quality during adviser review.")
        subsystems.append(RagSubsystem(subsystem, rag, _score(rag, evidenced, total), f"{evidenced}/{total}", first_gap, first_action, warnings))
    return subsystems


def dashboard_to_rows(subsystems: list[RagSubsystem]) -> list[dict]:
    return [asdict(s) for s in subsystems]
