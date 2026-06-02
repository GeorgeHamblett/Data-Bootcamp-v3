"""Section-specific report rendering helpers for Streamlit and tests."""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict
from typing import Any

from schemas import NOT_EXPLICITLY_STATED, ApplicationFacts, ChecklistItem

RAW_JSON_DEBUG_NOTE = "Developer/debug output only. This is not intended as the adviser-facing report."
RISK_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


class TableRow(dict):
    """Dictionary row whose string form is human-readable rather than raw JSON-like."""
    def __str__(self) -> str:
        return " | ".join(f"{k}: {v}" for k, v in self.items())


def _present(value: object) -> bool:
    if isinstance(value, list):
        return bool(value)
    return bool(value and value != NOT_EXPLICITLY_STATED)


def _safe(value: object, fallback: str = NOT_EXPLICITLY_STATED) -> str:
    if not _present(value):
        return fallback
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if _present(v)) or fallback
    return str(value).strip() or fallback


def _truncate_words(text: str, max_words: int = 35) -> str:
    words = re.sub(r"\s+", " ", text).strip().split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(" ,;:-") + "…"


def _dedupe_repeated_phrases(text: str) -> str:
    parts = [p.strip() for p in re.split(r"\s*,\s*", text) if p.strip()]
    out: list[str] = []
    for part in parts:
        key = part.lower()
        if key not in {x.lower() for x in out}:
            out.append(part)
    return ", ".join(out) if len(out) > 1 else text


def clean_table_evidence(raw_evidence: object, checklist_area: str = "", requirement: str = "") -> str:
    """Shorten table evidence while leaving full detail for raw JSON."""
    if isinstance(raw_evidence, list):
        text = "; ".join(str(v) for v in raw_evidence if _present(v))
    else:
        text = str(raw_evidence or "")
    if not text or text == NOT_EXPLICITLY_STATED:
        return NOT_EXPLICITLY_STATED
    chunks = [c.strip() for c in re.split(r"\s*;\s*", text) if c.strip()]
    text = chunks[0] if chunks else text
    text = re.sub(r"\b(\w+)(,\s*\1\b)+", r"\1", text, flags=re.I)
    text = _dedupe_repeated_phrases(text)
    text = re.sub(r"\bto intervent\b", "to intervention", text, flags=re.I)
    return _truncate_words(text.strip(" .;:"), 35)


def _compress(value: object, kind: str = "generic") -> str:
    if not _present(value):
        return ""
    text = str(value).strip()
    if kind == "population":
        for pattern in [r"(older adults?[^.;]{0,120})", r"(participants? aged \d+[^.;]{0,100})", r"((?:patients|people|adults|children|service users)[^.;]{0,100})"]:
            m = re.search(pattern, text, re.I)
            if m:
                return m.group(1).strip(" .;:")
    if kind == "need":
        bits = []
        labels = [
            (r"falls? prevention|falls? risk|risk of falling", "falls prevention"),
            (r"balance", "balance"),
            (r"mobility rehabilitation", "mobility rehabilitation"),
            (r"confidence", "confidence"),
            (r"independence", "independence"),
            (r"\brehabilitation\b", "rehabilitation"),
        ]
        for pattern, label in labels:
            if re.search(pattern, text, re.I) and label not in bits:
                bits.append(label)
        if "mobility rehabilitation" in bits and "rehabilitation" in bits:
            bits.remove("rehabilitation")
        if bits:
            return ", ".join(bits)
    if kind == "setting":
        for pattern in [r"NHS community rehabilitation services?", r"community rehabilitation (?:services|teams|clinics)", r"primary care", r"secondary care", r"social care"]:
            m = re.search(pattern, text, re.I)
            if m:
                return m.group(0)
    if len(text.split()) > 18 or text.lower().startswith(("this project", "we will", "the project will")):
        text = text.split(".")[0]
        text = text.replace("This project will test", "testing").replace("this project will test", "testing")
        return text[:140].strip(" .;:")
    return text


def _bullet(label: str, value: object, kind: str = "generic") -> str:
    text = _compress(value, kind) if kind != "generic" else _safe(value)
    return f"- **{label}:** {text}" if _present(text) and text != NOT_EXPLICITLY_STATED else f"- **{label}:** {NOT_EXPLICITLY_STATED}"


def _counts_by_rag(items: list[ChecklistItem] | list[dict]) -> Counter:
    counts: Counter = Counter({"GREEN": 0, "AMBER": 0, "RED": 0, "GREY": 0})
    for item in items:
        rag = item.rag if isinstance(item, ChecklistItem) else str(item.get("RAG", item.get("rag", "")))
        if rag in counts:
            counts[rag] += 1
    return counts


def _top_actions_from_items(items: list[ChecklistItem], rags: set[str], limit: int = 5) -> list[str]:
    out: list[str] = []
    for item in items:
        if item.rag in rags:
            action = _action(item)
            if action not in out:
                out.append(action)
        if len(out) >= limit:
            break
    return out


def _lines(entries: list[str]) -> str:
    return "\n".join(f"- {entry}" for entry in entries) if entries else "- None identified from available evidence."


def _dashboard_groups(dashboard: list[dict]) -> dict[str, list[str]]:
    return {
        rag: [str(row.get("Subsystem", "")) for row in dashboard if row.get("RAG") == rag]
        for rag in ["GREEN", "AMBER", "RED", "GREY"]
    }


def render_main_case_summary(facts: ApplicationFacts, dashboard: list[dict], priority_gaps: str = "") -> str:
    risk_rows = [row for row in dashboard if row.get("RAG") in {"RED", "AMBER", "GREY"}]
    risk_lines = [f"{row.get('Subsystem')} — {row.get('Priority action', 'Review evidence.')}" for row in risk_rows[:4]]
    duration = f"Month {facts.duration_months}" if _present(facts.duration_months) and "month" not in str(facts.duration_months).lower() else _safe(facts.duration_months)
    return f"""# Summary of key information extracted

## Project at a glance
- **Project:** {_safe(facts.project_title)}
- **Call:** {_safe(facts.application_claimed_call)}
- **Intervention/product:** {_safe(facts.product_or_intervention)} ({_safe(facts.acronym_or_short_name)})
{_bullet("Target population", facts.target_population, "population")}
{_bullet("Clinical or care need", facts.clinical_or_social_care_need, "need")}
{_bullet("Setting", facts.sites_or_setting, "setting")}

## Proposed evidence generation
- **Study design:** {_safe(facts.study_design)}
- **Sample and comparator:** {_safe(facts.sample_size)}; comparator/control: {_safe(facts.comparator_or_control)}
- **Timeline:** the extracted timeline appears to run to {duration}.
- **Endpoints/outcomes:** {_truncate_words(_safe(facts.endpoints), 30)}

## Adoption and delivery readiness
- **Regulatory/compliance:** {_truncate_words(_safe(facts.regulatory_plan), 30)}
- **Health economics:** {_truncate_words(_safe(facts.health_economics_plan), 30)}
- **PPIE and inclusion:** {_truncate_words(_safe(facts.ppie_plan), 20)}; {_truncate_words(_safe(facts.research_inclusion_plan), 20)}
- **Project management:** {_truncate_words(_safe(facts.project_management_plan), 30)}
- Built-in NIHR/RSS guidance is used as checklist guidance only, not as application evidence.

## Main RSS checklist risks
{_lines(risk_lines)}
"""


def render_summary(facts: ApplicationFacts, dashboard: list[dict], priority_gaps: str = "") -> str:
    """Backward-compatible alias for the Summary tab renderer."""
    return render_main_case_summary(facts, dashboard, priority_gaps)


def render_checklist_report_summary(items: list[ChecklistItem], facts: ApplicationFacts | None = None) -> str:
    counts = _counts_by_rag(items)
    strongest = sorted({item.area for item in items if item.rag == "GREEN"})[:5]
    high_risk = sorted({item.area for item in items if item.rag in {"RED", "AMBER"}})[:6]
    found = [item.area for item in items if item.evidence and item.rag in {"GREEN", "AMBER"}]
    missing_actions = _top_actions_from_items(items, {"RED", "AMBER"}, 5)
    return f"""- **Checklist row counts:** GREEN {counts['GREEN']}, AMBER {counts['AMBER']}, RED {counts['RED']}, GREY {counts['GREY']}.
- **Strongest evidenced areas:** {', '.join(strongest) if strongest else 'None identified from available evidence.'}
- **Missing/high-risk areas:** {', '.join(high_risk) if high_risk else 'None identified from available evidence.'}
- **Evidence found from the application:** {', '.join(dict.fromkeys(found[:8])) if found else 'None identified from available evidence.'}
- **Evidence still missing:** focus on RED and AMBER rows where the table shows missing, partial or human-check status.
- **Adviser follow-up actions:**
{_lines(missing_actions[:3])}
- The detailed row-level checklist table follows below; use it for requirement-by-requirement evidence and actions.
"""


def render_rag_dashboard_summary(dashboard: list[dict]) -> str:
    groups = _dashboard_groups(dashboard)
    red = groups["RED"]
    amber = groups["AMBER"]
    profile = "high risk" if red else "moderate risk" if amber else "lower risk"
    actions: list[str] = []
    for row in dashboard:
        if row.get("RAG") in {"RED", "AMBER", "GREY"}:
            action = str(row.get("Priority action", "Review application evidence."))
            if action not in actions:
                actions.append(action)
        if len(actions) >= 3:
            break
    return f"""- **Overall risk profile:** {profile}. The dashboard summarises the detailed checklist into seven RSS risk areas.
- **GREEN subsystems:** {', '.join(groups['GREEN']) if groups['GREEN'] else 'None identified from available evidence.'}
- **AMBER subsystems:** {', '.join(groups['AMBER']) if groups['AMBER'] else 'None identified from available evidence.'}
- **RED subsystems:** {', '.join(groups['RED']) if groups['RED'] else 'None identified from available evidence.'}
- **Top 3 adviser actions:**
{_lines(actions[:3])}
"""


def render_similarity_check_summary(similarity: dict) -> str:
    query = similarity.get("query")
    results = similarity.get("results", [])
    terms = []
    if query is not None:
        terms = list(getattr(query, "primary_terms", [])) + list(getattr(query, "secondary_terms", []))
    for result in results:
        for term in result.get("query_terms_used", []):
            if term not in terms:
                terms.append(term)
    clean_terms = [t for t in terms if t and t.lower() not in {"second", "some", "adherence"}]
    statuses = [str(r.get("status", "")) for r in results]
    if not results or all(s == "not_run" for s in statuses):
        run_state = "Similarity checking was disabled or not run."
    elif any(s == "error" for s in statuses):
        run_state = "Similarity checking partially failed."
    else:
        run_state = "Similarity checking ran for the available sources."
    highest = "NONE"
    for result in results:
        risk = str(result.get("risk", "NONE"))
        if RISK_ORDER.get(risk, 0) > RISK_ORDER.get(highest, 0):
            highest = risk
    total_matches = sum(int(r.get("matches_found", 0) or 0) for r in results)
    errors = [str(r.get("why_relevant", "API error")) for r in results if r.get("status") == "error"]
    safe_errors = [re.sub(r"https?://\S+", "[URL suppressed]", e) for e in errors]
    return f"""- **Run status:** {run_state}
- **Cleaned query terms used:** {', '.join(clean_terms[:8]) if clean_terms else 'None identified from available evidence.'}
- **Meaningful matches found:** {'Yes' if total_matches else 'No'} ({total_matches} total reported matches).
- **Overall novelty/similarity risk:** {highest}.
- **API errors:** {'; '.join(safe_errors) if safe_errors else 'None reported.'}
- **Human-review warning:** Similarity is only an initial screening signal; review any potentially related records manually before drawing novelty conclusions.
"""


ACTION_LIBRARY = {
    "Summary Information": "Add or verify project title, funding call, start date and duration.",
    "Lead Applicant and Research Team": "Add or verify contracting organisation, lead applicant details, partners and team roles.",
    "Application Details": "Add or verify intervention name, acronym, population, need, technology type and development stage.",
    "Eligibility": "Confirm partner eligibility and call remit fit against specific funding call guidance.",
    "Clinical Validation": "Add or verify study design, sample size, sites, comparator, endpoints, approvals and next-stage plan.",
    "Health Economics": "Add or verify health economics perspective, comparator, resource use, model, sensitivity analysis and cost-outcome plan.",
    "Patient and Public Involvement / Working with People and Communities": "Add or verify named PPI lead, public contributors/advisory group, involvement impact and PPIE payment/support costs.",
    "Research Inclusion": "Add or verify underserved groups, accessibility, sex/gender, exclusion criteria, inclusion costs and accessible dissemination.",
    "Project Management": "Upload or verify Gantt/project management plan, work packages, milestones, governance, risk register and contingencies.",
    "Budget and Finance": "Add or verify detailed budget, cost justification, current rates, scheme caps, and whether AcoRD/SoECAT apply.",
    "Uploads": "Upload or verify references and Gantt/project management plan; confirm whether flow diagram, logic model or flexible upload are required by the call.",
    "Acknowledgement and Conflicts": "Add or verify the AI-use declaration and conflicts declaration in Acknowledgement and Conflicts.",
    "Similarity / Novelty / Prior Work": "Add or verify novelty, prior work, related evidence, market/adoption route and references.",
}


def _action(item: ChecklistItem) -> str:
    return ACTION_LIBRARY.get(item.area, item.action or "Add or verify application-specific evidence.")


def render_priority_missing_evidence(items: list[ChecklistItem], dashboard: list[dict] | None = None, facts: ApplicationFacts | None = None) -> str:
    critical = [i for i in items if i.rag == "RED"]
    amber = [i for i in items if i.rag == "AMBER"]
    grey = [i for i in items if i.rag == "GREY"]
    uploads = [i for i in items if i.area == "Uploads" and i.rag != "GREEN"]
    budget = [i for i in items if i.area == "Budget and Finance" and i.rag != "GREEN"]

    def action_lines(entries: list[ChecklistItem]) -> str:
        seen: set[str] = set()
        out = []
        for item in entries:
            action = _action(item)
            if action not in seen:
                seen.add(action)
                out.append(action)
        return _lines(out)

    return f"""## Critical missing items
{action_lines(critical)}

## Important but fixable gaps
{action_lines(amber)}

## Items needing human judgement
{action_lines(grey)}

## Uploads still needed
{action_lines(uploads)}

## Budget/finance checks still needed
{action_lines(budget)}
"""


def render_executive_review_note(facts: ApplicationFacts, dashboard: list[dict], priority_gaps: str = "") -> str:
    groups = _dashboard_groups(dashboard)
    first_action = next((row.get("Priority action") for row in dashboard if row.get("RAG") in {"RED", "AMBER"}), "Review the detailed checklist table.")
    bullets = [
        f"- Application focus: {_safe(facts.product_or_intervention)} for {_compress(facts.target_population, 'population') or NOT_EXPLICITLY_STATED}.",
        f"- Proposed evidence generation: {_safe(facts.study_design)} with {_safe(facts.sample_size)} and timeline {_safe(facts.duration_months)} months.",
        f"- Strongest areas: {', '.join(groups['GREEN'][:3]) if groups['GREEN'] else 'None identified from available evidence.'}.",
        f"- Areas needing attention: {', '.join((groups['RED'] + groups['AMBER'])[:4]) if groups['RED'] or groups['AMBER'] else 'None identified from available evidence.'}.",
        f"- Finance position: {_safe(facts.finance_or_budget_evidence)}.",
        f"- RSS adviser should check first: {first_action}.",
    ]
    return "\n".join(bullets[:8])


def checklist_table_rows(items: list[ChecklistItem]) -> list[dict[str, Any]]:
    return render_table_display_dataframe(items, "checklist")


def dashboard_table_rows(rows: list[dict]) -> list[dict]:
    return render_table_display_dataframe(rows, "dashboard")


def similarity_table_rows(results: list[dict]) -> list[dict]:
    return render_table_display_dataframe(results, "similarity")


def render_table_display_dataframe(rows: list[Any], table_type: str = "checklist") -> list[dict[str, Any]]:
    if table_type == "checklist":
        rendered: list[dict[str, Any]] = []
        for item in rows:
            row = item.to_row() if isinstance(item, ChecklistItem) else dict(item)
            row["Evidence from application"] = clean_table_evidence(row.get("Evidence from application", NOT_EXPLICITLY_STATED), row.get("Checklist Area", ""), row.get("Requirement", ""))
            rendered.append(TableRow(row))
        return rendered
    if table_type == "dashboard":
        return [{k: v for k, v in dict(row).items() if k != "hard_validation_warnings"} for row in rows]
    if table_type == "similarity":
        return [
            {
                "Source": r.get("source", ""),
                "Status": r.get("status", ""),
                "Query terms used": clean_table_evidence(", ".join(r.get("query_terms_used", [])), "Similarity", "Query terms"),
                "Matches found": r.get("matches_found", 0),
                "Top match": clean_table_evidence(r.get("top_match", ""), "Similarity", "Top match"),
                "Score": r.get("score", 0.0),
                "Risk": r.get("risk", "NONE"),
                "Why relevant": clean_table_evidence(r.get("why_relevant", ""), "Similarity", "Why relevant"),
                "Link/ID": r.get("link_or_id", ""),
            }
            for r in rows
        ]
    return [dict(row) for row in rows]


def render_raw_json_note() -> str:
    return RAW_JSON_DEBUG_NOTE


def raw_json_payload(**kwargs: Any) -> str:
    def default(obj: Any) -> Any:
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        return str(obj)
    return json.dumps(kwargs, default=default, indent=2)


EXPECTED_RENDERER_FUNCTIONS = (
    "render_main_case_summary",
    "render_checklist_report_summary",
    "render_rag_dashboard_summary",
    "render_similarity_check_summary",
    "render_priority_missing_evidence",
    "render_executive_review_note",
    "render_table_display_dataframe",
    "render_raw_json_note",
)

__all__ = (
    "TableRow",
    "checklist_table_rows",
    "clean_table_evidence",
    "dashboard_table_rows",
    "raw_json_payload",
    "render_summary",
    "similarity_table_rows",
    *EXPECTED_RENDERER_FUNCTIONS,
)
