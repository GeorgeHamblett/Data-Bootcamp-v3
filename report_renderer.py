"""Report rendering helpers for Streamlit and tests."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from schemas import NOT_EXPLICITLY_STATED, ApplicationFacts, ChecklistItem


class TableRow(dict):
    """Dictionary row whose string form is human-readable rather than raw JSON-like."""
    def __str__(self) -> str:
        return " | ".join(f"{k}: {v}" for k, v in self.items())


def _present(value: object) -> bool:
    if isinstance(value, list):
        return bool(value)
    return bool(value and value != NOT_EXPLICITLY_STATED)



def _compress(value: object, kind: str = "generic") -> str:
    if not _present(value):
        return ""
    text = str(value).strip()
    if kind == "population":
        for pattern in [r"(older adults?[^.;]{0,120})", r"(participants? aged \d+[^.;]{0,100})", r"((?:patients|people|adults|children|service users)[^.;]{0,100})"]:
            import re
            m = re.search(pattern, text, re.I)
            if m:
                return m.group(1).strip(" .;:")
    if kind == "need":
        import re
        bits = []
        for pattern in [r"falls? prevention", r"reduce risk of falling", r"balance(?: confidence)?", r"mobility rehabilitation", r"confidence", r"independence", r"rehabilitation"]:
            if re.search(pattern, text, re.I):
                val = re.search(pattern, text, re.I).group(0).lower()
                if val not in bits:
                    bits.append(val)
        if bits:
            return ", ".join(bits)
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


def render_summary(facts: ApplicationFacts, dashboard: list[dict], priority_gaps: str) -> str:
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
        ("The setting is", _compress(facts.sites_or_setting)),
    ]
    population = ". ".join(f"{label} {value}" for label, value in _unique_phrases(population_bits) if value)

    evidence_bits = [
        _phrase("The design is", facts.study_design),
        _phrase("using", facts.methodology),
        _phrase("with sample size", facts.sample_size),
        _phrase("and comparator/control", facts.comparator_or_control),
        _phrase("The development-stage evidence is", facts.trl_evidence),
        _phrase("The extracted timeline appears to run to", ("Month " + facts.duration_months) if _present(facts.duration_months) and "month" not in str(facts.duration_months).lower() else facts.duration_months),
    ]
    evidence = ". ".join(bit for bit in evidence_bits if bit) or "The evidence-generation design needs clearer application evidence."
    outcomes = ", ".join(facts.endpoints[:10]) if facts.endpoints else "outcomes/endpoints need clearer confirmation"

    readiness_bits = [
        _phrase("Regulatory/adoption evidence includes", facts.regulatory_plan),
        _phrase("Health economics evidence includes", facts.health_economics_plan),
        _phrase("PPIE evidence includes", facts.ppie_plan),
        _phrase("Research inclusion evidence includes", facts.research_inclusion_plan),
        _phrase("Project management evidence includes", facts.project_management_plan),
    ]
    readiness = " ".join(bit + "." for bit in readiness_bits if bit)
    if not readiness:
        readiness = "Adoption, regulatory, PPIE, inclusion and project-management readiness need clearer evidence."

    risk_rows = [row for row in dashboard if row["RAG"] in {"RED", "AMBER", "GREY"}]
    risks = ". ".join(f"{row['Subsystem']} - {row['Priority action']}" for row in risk_rows[:5]) or "No major checklist risks identified from relevant evidence."

    return f"""Summary of key information extracted

1. Project at a glance
{identity}. {population}. The summary is based on the runtime application and supporting documents only; built-in NIHR/RSS guidance is used as checklist guidance, not as application evidence. Where source documents include workplans or appendices, those supporting documents are considered alongside the main application text.

2. Proposed evidence generation
{evidence}. Extracted endpoints and outcome measures include {outcomes}. These facts are used to judge clinical validation only where they directly match the requirement being checked, so a duration, Gantt row or outcome measure is not reused to satisfy unrelated applicant, finance or eligibility requirements.

3. Adoption and delivery readiness
{readiness} Finance is considered separately from health economics: economic modelling, EQ-5D/QALY or cost-effectiveness wording supports health economics, while Finance requires actual budget, cost-category, rate, cap, AcoRD, SoECAT or cost-justification evidence.

4. Main RSS checklist risks
The main adviser risks are: {risks}. The Priority Missing Evidence tab translates these into practical actions, such as verifying AI-use and conflicts declarations, named PPI leadership/payment, call-specific uploads, references, and detailed budget/AcoRD/SoECAT evidence where applicable. Items marked missing, partially present or needing human check should be resolved against the uploaded application and the specific funding call rather than against generic guidance text.
"""


def checklist_table_rows(items: list[ChecklistItem]) -> list[dict[str, Any]]:
    return [TableRow(item.to_row()) for item in items]


def dashboard_table_rows(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in row.items() if k != "hard_validation_warnings"} for row in rows]


def similarity_table_rows(results: list[dict]) -> list[dict]:
    return [
        {
            "Source": r.get("source", ""),
            "Status": r.get("status", ""),
            "Query terms used": ", ".join(r.get("query_terms_used", [])),
            "Matches found": r.get("matches_found", 0),
            "Top match": r.get("top_match", ""),
            "Score": r.get("score", 0.0),
            "Risk": r.get("risk", "NONE"),
            "Why relevant": r.get("why_relevant", ""),
            "Link/ID": r.get("link_or_id", ""),
        }
        for r in results
    ]


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


def render_priority_missing_evidence(items: list[ChecklistItem]) -> str:
    critical = [i for i in items if i.rag == "RED"]
    amber = [i for i in items if i.rag == "AMBER"]
    grey = [i for i in items if i.rag == "GREY"]
    uploads = [i for i in items if i.area == "Uploads" and i.rag != "GREEN"]
    budget = [i for i in items if i.area == "Budget and Finance" and i.rag != "GREEN"]

    def lines(entries: list[ChecklistItem]) -> str:
        seen: set[str] = set()
        out = []
        for item in entries:
            action = _action(item)
            if action not in seen:
                seen.add(action)
                out.append(f"- {action}")
        return "\n".join(out) or "- None identified from available evidence."

    return f"""Critical missing items
{lines(critical)}

Important but fixable gaps
{lines(amber)}

Items needing human judgement
{lines(grey)}

Uploads still needed
{lines(uploads)}

Budget/finance checks still needed
{lines(budget)}
"""


def raw_json_payload(**kwargs: Any) -> str:
    def default(obj: Any) -> Any:
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        return str(obj)
    return json.dumps(kwargs, default=default, indent=2)
