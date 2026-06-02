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


def _strip_terminal_punctuation(value: object) -> str:
    return str(value or "").strip().rstrip(" .;:")


def _join_sentences(parts: list[str], separator: str = ". ") -> str:
    cleaned = [_strip_terminal_punctuation(part) for part in parts if _present(part)]
    return separator.join(part for part in cleaned if part)


def _remove_label_prefix(value: object, labels: tuple[str, ...]) -> str:
    text = _strip_terminal_punctuation(value)
    for label in labels:
        text = re.sub(rf"^{label}\s*[:\-]\s*", "", text, flags=re.I)
    return text


def _normalise_study_design(value: object) -> str:
    text = _remove_label_prefix(value, ("study design", "design", "methods?"))
    text = re.sub(r"^to conduct an?\s+", "", text, flags=re.I)
    text = re.sub(r"^we will conduct an?\s+", "", text, flags=re.I)
    return text[:1].lower() + text[1:] if text.startswith(("A ", "An ")) else text


def _unique_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = value.lower().strip()
        if key and key not in seen:
            seen.add(key)
            output.append(value)
    return output


def _compress(value: object, kind: str = "generic") -> str:
    if not _present(value):
        return ""
    text = str(value).strip()
    if kind == "population":
        text = re.split(r"\bwill be (?:randomi[sz]ed|recruited|allocated|invited)\b", text, maxsplit=1, flags=re.I)[0].strip()
        for pattern in [
            r"(older adults?[^.;]{0,120})",
            r"((?:participants?\s+)?aged \d+[^.;,]{0,100})",
            r"((?:patients|people|adults|children|service users)[^.;]{0,100})",
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                return m.group(1).strip(" .;:")
    if kind == "need":
        bits = []
        for pattern in [r"falls? prevention", r"reduce risk of falling", r"balance(?: confidence)?", r"mobility rehabilitation", r"confidence", r"independence", r"rehabilitation"]:
            if re.search(pattern, text, re.I):
                val = re.search(pattern, text, re.I).group(0).lower()
                if val == "rehabilitation" and any("rehabilitation" in bit for bit in bits):
                    continue
                if val not in bits:
                    bits.append(val)
        if bits:
            return ", ".join(bits)
    if kind == "setting":
        for pattern in [
            r"(NHS[^.;,]{0,140}(?:services?|clinics?|teams?|trusts?|sites?|settings?|rehabilitation))",
            r"((?:primary|secondary|community|social) care[^.;,]{0,80})",
            r"(community rehabilitation[^.;,]{0,80})",
        ]:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(1).strip(" .;:")
        if re.match(r"partners? include", text, re.I):
            return ""
    # Avoid rendering raw proposal sentences in summary clauses.
    if len(text.split()) > 18 or text.lower().startswith(("this project", "we will", "the project will")):
        text = text.split(".")[0]
        text = text.replace("This project will test", "testing").replace("this project will test", "testing")
        return text[:140].strip(" .;:")
    return text


def _unique_phrases(values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    out = []
    for label, value in values:
        key = value.lower().strip()
        if value and key not in seen:
            seen.add(key)
            out.append((label, value))
    return out

def _phrase(label: str, value: object) -> str:
    if isinstance(value, list):
        return f"{label} {', '.join(str(v) for v in value[:8])}" if value else ""
    return f"{label} {value}" if _present(value) else ""


def render_main_case_summary(facts: ApplicationFacts, dashboard: list[dict], priority_gaps: str = "") -> str:
    identity_bits = [
        _phrase("The project title is", facts.project_title),
        _phrase("The application is linked to", facts.application_claimed_call),
        _phrase("The intervention/product is", facts.product_or_intervention),
        _phrase("The acronym or module is", facts.acronym_or_short_name),
    ]
    identity = ". ".join(bit for bit in identity_bits if bit) or "The uploaded documents do not clearly state the project identity."
    compressed_population = _compress(facts.target_population, "population")
    compressed_need = _compress(facts.clinical_or_social_care_need, "need")
    population_bits = [
        ("The target population is", compressed_population),
        ("The clinical or care need is", compressed_need),
        ("The setting is", _compress(facts.sites_or_setting, "setting")),
    ]
    population = ". ".join(f"{label} {value}" for label, value in _unique_phrases(population_bits) if value)

    design = _normalise_study_design(facts.study_design)
    methodology = _strip_terminal_punctuation(facts.methodology) if _present(facts.methodology) else ""
    sample_size = _strip_terminal_punctuation(facts.sample_size) if _present(facts.sample_size) else ""
    comparator = _remove_label_prefix(facts.comparator_or_control, ("comparator", "control")) if _present(facts.comparator_or_control) else ""
    design_sentence = _phrase("The design is", design)
    if methodology:
        design_sentence = _join_sentences([design_sentence, f"using {methodology}"], ", ")
    sample_and_comparator = " and ".join(
        part for part in [
            f"sample size {sample_size}" if sample_size else "",
            f"comparator/control {comparator}" if comparator else "",
        ]
        if part
    )
    if sample_and_comparator:
        design_sentence = _join_sentences([design_sentence, f"with {sample_and_comparator}"], ", ")
    development_parts = [
        _phrase("The development-stage evidence is", facts.trl_evidence),
        _phrase("The extracted timeline appears to run to", ("Month " + facts.duration_months) if _present(facts.duration_months) and "month" not in str(facts.duration_months).lower() else facts.duration_months),
    ]
    evidence = _join_sentences([design_sentence, _join_sentences(development_parts)]) or "The evidence-generation design needs clearer application evidence."
    outcomes = ", ".join(_unique_texts(facts.endpoints)[:10]) if facts.endpoints else "outcomes/endpoints need clearer confirmation"

    readiness_bits = [
        _phrase("Regulatory/adoption evidence includes", facts.regulatory_plan),
        _phrase("Health economics evidence includes", facts.health_economics_plan),
        _phrase("PPIE evidence includes", facts.ppie_plan),
        _phrase("Research inclusion evidence includes", facts.research_inclusion_plan),
        _phrase("Project management evidence includes", facts.project_management_plan),
    ]
    readiness = " ".join(_strip_terminal_punctuation(bit) + "." for bit in readiness_bits if bit)
    if not readiness:
        readiness = "Adoption, regulatory, PPIE, inclusion and project-management readiness need clearer evidence."

    risk_rows = [row for row in dashboard if row["RAG"] in {"RED", "AMBER", "GREY"}]
    risks = "; ".join(f"{row['Subsystem']} - {_strip_terminal_punctuation(row['Priority action'])}" for row in risk_rows[:5]) or "No major checklist risks identified from relevant evidence"

    return f"""Summary of key information extracted

## Project at a glance
{identity}. {population}. The summary is based on the runtime application and supporting documents only; built-in NIHR/RSS guidance is used as checklist guidance, not as application evidence. Where source documents include workplans or appendices, those supporting documents are considered alongside the main application text.

## Proposed evidence generation
{evidence}. Extracted endpoints and outcome measures include {outcomes}. These facts are used to judge clinical validation only where they directly match the requirement being checked, so a duration, Gantt row or outcome measure is not reused to satisfy unrelated applicant, finance or eligibility requirements.

## Adoption and delivery readiness
{readiness} Finance is considered separately from health economics: economic modelling, EQ-5D/QALY or cost-effectiveness wording supports health economics, while Finance requires actual budget, cost-category, rate, cap, AcoRD, SoECAT or cost-justification evidence.

## Main RSS checklist risks
The main adviser risks are: {risks}. The Priority Missing Evidence tab translates these into practical actions, such as verifying AI-use and conflicts declarations, named PPI leadership/payment, call-specific uploads, references, and detailed budget/AcoRD/SoECAT evidence where applicable. Items marked missing, partially present or needing human check should be resolved against the uploaded application and the specific funding call rather than against generic guidance text.
"""


def render_summary(facts: ApplicationFacts, dashboard: list[dict], priority_gaps: str = "") -> str:
    """Backward-compatible alias for the Summary tab renderer."""
    return render_main_case_summary(facts, dashboard, priority_gaps)


def _lines(values: list[str]) -> str:
    """Render unique non-empty values as Markdown bullets."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_table_evidence(value)
        if text == NOT_EXPLICITLY_STATED:
            continue
        key = text.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(text)
    if not cleaned:
        return "- None identified from available evidence."
    return "\n".join(f"- {value}" for value in cleaned)


def clean_table_evidence(value: object, area: str = "", requirement: str = "") -> str:
    """Clean evidence snippets so tables show adviser-facing content, not portal noise."""
    if isinstance(value, list):
        text = "; ".join(str(v) for v in value if _present(v))
    else:
        text = str(value or "").strip()
    if not _present(text):
        return NOT_EXPLICITLY_STATED

    portal_noise = re.compile(
        r"click invite|fill in (?:the )?name/?email|fill in (?:the )?name|email address|save draft|"
        r"awards management system|on-screen|button|automatically pull|registered|use this guidance",
        re.I,
    )
    parts = [part.strip(" .;:\n\t") for part in re.split(r"[.;]\s+", text) if part.strip()]
    useful = [part for part in parts if not portal_noise.search(part)]
    cleaned = "; ".join(useful).strip(" ;")
    if not cleaned:
        return NOT_EXPLICITLY_STATED
    return cleaned[:500]



def _safe(value: object) -> str:
    """Return a readable fallback for missing extracted values."""
    return clean_table_evidence(value)


def _counts_by_rag(items: list[ChecklistItem]) -> dict[str, int]:
    """Count checklist items by RAG status with stable zero defaults."""
    counts = Counter(item.rag for item in items)
    return {rag: counts.get(rag, 0) for rag in ("GREEN", "AMBER", "RED", "GREY")}


def _top_actions_from_items(items: list[ChecklistItem], rags: set[str], limit: int) -> list[str]:
    """Return deduplicated adviser actions for checklist items matching the requested RAG statuses."""
    actions: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item.rag not in rags:
            continue
        action = _action(item)
        key = action.lower()
        if key not in seen:
            seen.add(key)
            actions.append(action)
        if len(actions) >= limit:
            break
    return actions


def group_dashboard_by_rag(dashboard: list[dict]) -> dict[str, list[str]]:
    """Group dashboard subsystem names by RAG status for summaries."""
    groups: dict[str, list[str]] = {rag: [] for rag in ("GREEN", "AMBER", "RED", "GREY")}
    for row in dashboard:
        rag = str(row.get("RAG", "GREY") or "GREY").upper()
        subsystem = str(row.get("Subsystem", "")).strip()
        if not subsystem:
            continue
        groups.setdefault(rag, []).append(subsystem)
    return groups


# Backward-compatible private alias for older imports/tests while public renderers use the public helper.
_dashboard_groups = group_dashboard_by_rag

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
    groups = group_dashboard_by_rag(dashboard)
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
    # Keep this renderer self-contained: it is called after the main summary in the
    # Streamlit app, so it should never fail because a private grouping helper was
    # renamed or unavailable in an older checkout.
    groups: dict[str, list[str]] = {rag: [] for rag in ("GREEN", "AMBER", "RED", "GREY")}
    for row in dashboard:
        rag = str(row.get("RAG", "GREY") or "GREY").upper()
        subsystem = str(row.get("Subsystem", "")).strip()
        if subsystem:
            groups.setdefault(rag, []).append(subsystem)
    first_action = _strip_terminal_punctuation(next((row.get("Priority action") for row in dashboard if row.get("RAG") in {"RED", "AMBER"}), "Review the detailed checklist table"))
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
    "group_dashboard_by_rag",
    "raw_json_payload",
    "render_summary",
    "similarity_table_rows",
    *EXPECTED_RENDERER_FUNCTIONS,
)
