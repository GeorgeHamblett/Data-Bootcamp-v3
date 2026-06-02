"""Render report sections for Streamlit and tests."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

try:
    import pandas as pd
except ModuleNotFoundError:  # lightweight fallback for test environments without pandas
    pd = None


class _MiniILoc:
    def __init__(self, rows):
        self._rows = rows
    def __getitem__(self, key):
        row, col = key
        return list(self._rows[row].values())[col]


class MiniDataFrame:
    def __init__(self, rows):
        self.rows = rows
        self.columns = list(rows[0].keys()) if rows else []
        self.iloc = _MiniILoc(rows)
    def __str__(self):
        return str(self.rows)


def _dataframe(rows):
    return pd.DataFrame(rows) if pd is not None else MiniDataFrame(rows)

from schemas import ApplicationFacts, ChecklistItem, RagSubsystem, SimilarityResult, NOT_EXPLICITLY_STATED


def _value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(map(str, value)) if value else NOT_EXPLICITLY_STATED
    return str(value) if value else NOT_EXPLICITLY_STATED


def render_summary(facts: ApplicationFacts, dashboard: list[RagSubsystem], priority_gaps: dict[str, list[str]]) -> str:
    red_or_amber = [s for s in dashboard if s.rag in {"RED", "AMBER"}]
    risk_sentence = "; ".join(f"{s.subsystem}: {s.main_gap}" for s in red_or_amber[:4]) or "No major RED or AMBER subsystem gap was generated from the extracted evidence."
    source_docs = sorted({e.source_document for e in facts.evidence})
    source_sentence = f"Evidence was extracted from {', '.join(source_docs[:4])}." if source_docs else "No source-document evidence quotes were extracted."
    text = f"""# Summary of key information extracted

## 1. Project at a glance
The application appears to describe {_value(facts.project_title)} for the claimed call {_value(facts.application_claimed_call)}. The lead is {_value(facts.applicant_or_lead)} and the contracting organisation is {_value(facts.contracting_organisation)}. The product or intervention is {_value(facts.product_or_intervention)}, with {_value(facts.target_population)} identified as the target population. {source_sentence} The clinical or social care need is {_value(facts.clinical_or_social_care_need)}.

## 2. Proposed evidence generation
The proposed design is {_value(facts.study_design)} with methodology described as {_value(facts.methodology)}. Sample size is {_value(facts.sample_size)}, endpoints are {_value(facts.endpoints)}, and the setting is {_value(facts.sites_or_setting)}. TRL or development-stage evidence is {_value(facts.trl_evidence)}; where progression is stated, it is treated as planned development rather than a contradiction. The regulatory plan is {_value(facts.regulatory_plan)}.

## 3. Adoption and delivery readiness
Project delivery evidence includes {_value(facts.project_management_plan)}. Work packages are {_value(facts.work_packages)} and milestones are {_value(facts.milestones)}. Health economics is {_value(facts.health_economics_plan)}, PPIE is {_value(facts.ppie_plan)}, and research inclusion is {_value(facts.research_inclusion_plan)}. Finance evidence is {_value(facts.finance_or_budget_evidence)}. Uploads detected from application text include {_value(facts.uploads_detected)}; references are {_value(facts.references_detected)}.

## 4. Main RSS checklist risks
The dashboard highlights: {risk_sentence}. AI-use declaration is {_value(facts.ai_use_declaration)} and conflicts declaration is {_value(facts.conflicts_declaration)}. RSS advisers should prioritise missing mandatory evidence, budget justification including AcoRD/SoECAT where applicable, project-management artefacts such as Gantt or milestones, named PPI responsibility, and any call-specific uploads or caps that override general NIHR/RSS guidance. Not explicitly stated is used only where the uploaded application evidence does not make a point clear.
"""
    return text


def checklist_dataframe(items: list[ChecklistItem]) -> object:
    return _dataframe([
        {
            "Checklist Area": i.area,
            "Requirement": i.requirement,
            "Source Guidance": i.source_guidance,
            "Status": i.status,
            "RAG": i.rag,
            "Evidence from application": "\n".join(i.evidence) if i.evidence else "Not explicitly stated",
            "Gap / action needed": f"{i.gap} Action: {i.action}",
        }
        for i in items
    ])


def dashboard_dataframe(subsystems: list[RagSubsystem]) -> object:
    return _dataframe([
        {
            "Subsystem": s.subsystem,
            "RAG": s.rag,
            "Score 0-5": s.score_0_5,
            "Checks evidenced": s.checks_evidenced,
            "Main gap": s.main_gap,
            "Priority action": s.priority_action,
        }
        for s in subsystems
    ])


def similarity_dataframe(results: list[SimilarityResult]) -> object:
    return _dataframe([
        {
            "Source": r.source,
            "Status": r.status,
            "Query terms used": ", ".join(r.query_terms_used),
            "Matches found": r.matches_found,
            "Top match": r.top_match,
            "Score": r.score,
            "Risk": r.risk,
            "Why relevant": r.why_relevant,
            "Link/ID": r.link_or_id,
        }
        for r in results
    ])


def priority_missing_evidence(items: list[ChecklistItem]) -> dict[str, list[str]]:
    result = {
        "Critical missing items": [],
        "Important but fixable gaps": [],
        "Items needing human judgement": [],
        "Uploads still needed": [],
        "Budget/finance checks still needed": [],
    }
    for item in items:
        line = f"{item.area}: {item.gap} Action: {item.action}"
        if item.rag == "RED":
            result["Critical missing items"].append(line)
        elif item.rag == "AMBER":
            result["Important but fixable gaps"].append(line)
        elif item.status == "Needs human check":
            result["Items needing human judgement"].append(line)
        if item.area == "Uploads" and item.rag != "GREEN":
            result["Uploads still needed"].append(line)
        if item.area == "Budget and Finance" and item.rag != "GREEN":
            result["Budget/finance checks still needed"].append(line)
    return result


def raw_json_payload(**kwargs: Any) -> str:
    def default(obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        raise TypeError(type(obj).__name__)
    return json.dumps(kwargs, default=default, indent=2)


def validate_report_quality(summary: str, items: list[ChecklistItem], raw_json_tab_index: int = 5, similarity_mock_mode: bool = False) -> list[str]:
    warnings: list[str] = []
    if summary.strip().startswith("{") or '"project_title"' in summary[:500]:
        warnings.append("Summary appears to be raw JSON or a field list.")
    if raw_json_tab_index != 5:
        warnings.append("Raw JSON must be kept in the final Raw JSON tab, not shown first.")
    for item in items:
        if not item.source_guidance:
            warnings.append("Checklist item lacks source guidance label.")
        if item.rag == "GREEN" and not item.evidence:
            warnings.append("GREEN checklist item lacks application evidence.")
    if similarity_mock_mode:
        warnings.append("Mock similarity mode is enabled; results are simulated for testing only.")
    return warnings
