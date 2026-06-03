"""Section-specific report rendering helpers for Streamlit and tests."""

from __future__ import annotations

import json
import re
import textwrap
from collections import Counter
from dataclasses import asdict, is_dataclass
from typing import Any

from schemas import NOT_EXPLICITLY_STATED, ApplicationFacts, ChecklistItem

RAW_JSON_DEBUG_NOTE = "Developer/debug output only. This is not intended as the adviser-facing report."

RISK_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "VERY_HIGH": 4}


class TableRow(dict):
    """Dictionary row whose string form is human-readable rather than raw JSON-like."""

    def __str__(self) -> str:
        return " | ".join(f"{k}: {v}" for k, v in self.items())


# ---------------------------------------------------------------------
# General safe access / cleaning helpers
# ---------------------------------------------------------------------



def clean_markdown_output(markdown: str) -> str:
    if markdown is None:
        return ""

    text = str(markdown)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("```markdown", "").replace("```", "")
    text = textwrap.dedent(text).strip()

    cleaned_lines = []
    for line in text.splitlines():
        line = line.replace("\t", " ")
        line = line.rstrip()

        # Critical: remove leading indentation from all normal Markdown lines.
        # Four leading spaces make Markdown render as a code block.
        if line.startswith("    ") or line.startswith("  "):
            line = line.lstrip()

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Remove accidental large blank sections.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Safely read a value from a dict, dataclass, pydantic-style model or object."""
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    if hasattr(obj, key):
        return getattr(obj, key)

    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump().get(key, default)
        except Exception:
            return default

    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict().get(key, default)
        except Exception:
            return default

    if is_dataclass(obj):
        try:
            return asdict(obj).get(key, default)
        except Exception:
            return default

    return default


def _to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return obj

    if hasattr(obj, "to_row"):
        try:
            return obj.to_row()
        except Exception:
            pass

    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass

    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass

    if is_dataclass(obj):
        try:
            return asdict(obj)
        except Exception:
            pass

    try:
        return dict(obj)
    except Exception:
        return {}


def _present(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        text = value.strip()
        return bool(text and text != NOT_EXPLICITLY_STATED)

    if isinstance(value, list):
        return any(_present(v) for v in value)

    return bool(value)


def _strip_terminal_punctuation(value: Any) -> str:
    return str(value or "").strip().rstrip(" .;:")


def _remove_label_prefix(value: Any, labels: tuple[str, ...]) -> str:
    text = _strip_terminal_punctuation(value)
    for label in labels:
        text = re.sub(rf"^{re.escape(label)}\s*[:\-]\s*", "", text, flags=re.I)
    return text


def _safe(value: Any) -> str:
    if not _present(value):
        return NOT_EXPLICITLY_STATED
    return clean_display_value(value)


def _dedupe_keep_order(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not _present(value):
            continue

        text = clean_display_value(value)
        key = text.lower().strip()

        if not key or key == NOT_EXPLICITLY_STATED.lower():
            continue

        if key not in seen:
            seen.add(key)
            out.append(text)

    return out


def _sentence_safe_trim(value: Any, max_chars: int = 180) -> str:
    text = str(value or "").strip()

    if len(text) <= max_chars:
        return text

    cut = text[:max_chars].rsplit(" ", 1)[0].strip()
    return cut.rstrip(" ,;:") + "…"


def _remove_repeated_comma_terms(text: str) -> str:
    parts = [p.strip() for p in re.split(r",|/|;", text) if p.strip()]
    if len(parts) <= 1:
        return text

    deduped: list[str] = []
    seen: set[str] = set()

    for part in parts:
        key = part.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(part)

    if len(deduped) == 1:
        return deduped[0]

    separator = " / " if "/" in text else ", "
    return separator.join(deduped)


def clean_display_value(value: Any, max_chars: int = 180) -> str:
    """Clean a value for adviser-facing Markdown display."""
    if not _present(value):
        return NOT_EXPLICITLY_STATED

    if isinstance(value, list):
        value = ", ".join(str(v) for v in value if _present(v))

    text = str(value).strip()

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^(First|Second|Third|Finally),\s+", "", text, flags=re.I)
    text = text.replace(" will be randomised 2:1 to intervent", "")
    text = text.replace(" to intervent", "")
    text = re.sub(r"\brehabilitation,\s*rehabilitation\b", "rehabilitation", text, flags=re.I)
    text = _remove_repeated_comma_terms(text)

    if text.lower() in {"second", "some", "adherence", "recruitment", "retention", "fidelity"}:
        return NOT_EXPLICITLY_STATED

    return _sentence_safe_trim(text, max_chars=max_chars)


def _compress(value: Any, kind: str = "generic") -> str:
    """Compress extracted raw text into concise adviser-facing phrases."""
    if not _present(value):
        return ""

    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)

    if kind == "population":
        patterns = [
            r"(adults? aged\s*\d+\s*(?:and over|\+)?[^.;]{0,110})",
            r"(older adults?[^.;]{0,110})",
            r"(participants? aged\s*\d+[^.;]{0,110})",
            r"((?:patients|people|adults|children|service users)\s+(?:with|who have|aged)[^.;]{0,110})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                result = match.group(1).strip(" .;:")
                result = re.sub(r"\s+will be randomised.*$", "", result, flags=re.I)
                result = result.replace("aged 60 and over", "adults aged 60+")
                return clean_display_value(result)

    if kind == "need":
        concepts: list[str] = []
        mapping = [
            (r"falls? prevention|reduce(?:d)? risk of falling|falling", "falls prevention"),
            (r"balance", "balance"),
            (r"confidence", "confidence"),
            (r"mobility rehabilitation", "mobility rehabilitation"),
            (r"\bindependence\b", "independence"),
            (r"community rehabilitation", "community rehabilitation"),
        ]

        for pattern, label in mapping:
            if re.search(pattern, text, flags=re.I) and label not in concepts:
                concepts.append(label)

        if concepts:
            if len(concepts) == 1:
                return concepts[0]
            return ", ".join(concepts[:-1]) + " and " + concepts[-1]

    if kind == "setting":
        patterns = [
            r"(NHS community rehabilitation services?)",
            r"(community rehabilitation teams?[^.;,]{0,80})",
            r"(NHS[^.;,]{0,140}(?:services?|clinics?|teams?|trusts?|sites?|settings?|rehabilitation))",
            r"((?:primary|secondary|community|social) care[^.;,]{0,80})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return clean_display_value(match.group(1))

    if kind == "technology":
        concepts: list[str] = []

        mapping = [
            (r"AI-enabled", "AI-enabled"),
            (r"wearable digital therapeutic", "wearable digital therapeutic"),
            (r"wearable", "wearable"),
            (r"movement quality assessment", "movement quality assessment"),
            (r"digital therapeutic", "digital therapeutic"),
            (r"platform", "platform"),
            (r"software", "software"),
            (r"device", "device"),
        ]

        for pattern, label in mapping:
            if re.search(pattern, text, flags=re.I) and label not in concepts:
                concepts.append(label)

        if "AI-enabled" in concepts and "movement quality assessment" in concepts:
            return "AI-enabled movement quality assessment platform"

        if concepts:
            return " / ".join(concepts[:4])

    if kind == "design":
        text = re.sub(r"^To conduct\s+", "", text, flags=re.I)
        text = text.rstrip(".")
        return clean_display_value(text, max_chars=220)

    if len(text.split()) > 22 or text.lower().startswith(("this project", "we will", "the project will")):
        text = text.split(".")[0]
        text = text.replace("This project will test", "testing")
        text = text.replace("this project will test", "testing")

    return clean_display_value(text)


def _lines(values: list[Any]) -> str:
    cleaned = _dedupe_keep_order(values)

    if not cleaned:
        return "- None identified from available evidence."

    return "\n".join(f"- {value}" for value in cleaned)


def _top_actions_from_items(items: list[Any], rags: set[str] | None = None, limit: int = 5) -> list[str]:
    wanted = {r.upper() for r in (rags or {"RED", "AMBER", "GREY"})}

    actions: list[str] = []
    seen: set[str] = set()

    for item in items or []:
        data = _to_dict(item)

        rag = str(
            _get(item, "rag")
            or data.get("RAG")
            or data.get("rag")
            or ""
        ).upper()

        if rag not in wanted:
            continue

        area = (
                _get(item, "area")
                or data.get("Checklist Area")
                or data.get("area")
                or data.get("Area")
                or ""
        )

        action = (
                _get(item, "action")
                or data.get("Gap / action needed")
                or data.get("action")
                or data.get("Priority action")
                or ""
        )

        text = ACTION_LIBRARY.get(str(area), action or "Add or verify application-specific evidence.")
        text = clean_display_value(text, max_chars=220)

        if _present(text) and text not in seen:
            seen.add(text)
            actions.append(text)

        if len(actions) >= limit:
            break

    return actions


def _counts_by_rag(items: list[Any]) -> Counter:
    counts: Counter = Counter({"GREEN": 0, "AMBER": 0, "RED": 0, "GREY": 0})

    for item in items or []:
        data = _to_dict(item)
        rag = str(
            _get(item, "rag")
            or data.get("RAG")
            or data.get("rag")
            or ""
        ).upper()

        if rag in counts:
            counts[rag] += 1

    return counts


# ---------------------------------------------------------------------
# Dashboard grouping helpers
# ---------------------------------------------------------------------


def group_dashboard_by_rag(dashboard: list[dict] | None) -> dict[str, list[str]]:
    """Group RAG dashboard subsystem names by RAG value."""
    groups: dict[str, list[str]] = {"GREEN": [], "AMBER": [], "RED": [], "GREY": []}

    for row in dashboard or []:
        if not isinstance(row, dict):
            continue

        rag = str(row.get("RAG") or row.get("rag") or "").upper()
        subsystem = (
                row.get("Subsystem")
                or row.get("subsystem")
                or row.get("area")
                or row.get("Area")
        )

        if rag in groups and subsystem:
            subsystem = str(subsystem)
            if subsystem not in groups[rag]:
                groups[rag].append(subsystem)

    return groups


def _dashboard_groups(dashboard: list[dict] | None) -> dict[str, list[str]]:
    """Backward-compatible alias used by older renderer code/tests."""
    return group_dashboard_by_rag(dashboard)


# ---------------------------------------------------------------------
# Main Summary tab
# ---------------------------------------------------------------------


def render_main_case_summary(
        facts: ApplicationFacts,
        dashboard: list[dict],
        priority_gaps: str = "",
) -> str:
    """Render the main adviser-facing case summary as Markdown."""
    project_title = _get(facts, "project_title", NOT_EXPLICITLY_STATED)
    claimed_call = _get(facts, "application_claimed_call", NOT_EXPLICITLY_STATED)
    product = _get(facts, "product_or_intervention", NOT_EXPLICITLY_STATED)
    acronym = _get(facts, "acronym_or_short_name", NOT_EXPLICITLY_STATED)

    target_population = _compress(_get(facts, "target_population"), "population") or _safe(
        _get(facts, "target_population"))
    clinical_need = _compress(_get(facts, "clinical_or_social_care_need"), "need") or _safe(
        _get(facts, "clinical_or_social_care_need"))
    setting = _compress(_get(facts, "sites_or_setting"), "setting") or _safe(_get(facts, "sites_or_setting"))
    technology = _compress(_get(facts, "technology_type"), "technology") or _safe(_get(facts, "technology_type"))

    study_design = _compress(_get(facts, "study_design"), "design") or _safe(_get(facts, "study_design"))
    sample_size = _safe(_get(facts, "sample_size"))
    comparator = _safe(_remove_label_prefix(_get(facts, "comparator_or_control"), ("comparator", "control")))
    trl = _safe(_get(facts, "trl_evidence"))
    duration = _safe(_get(facts, "duration_months"))
    duration_text = f"{duration} months" if duration.isdigit() else duration
    milestones = _dedupe_keep_order(_get(facts, "milestones", []) or [])
    month_milestones = [milestone for milestone in milestones if re.search(r"\bMonth\s+\d+", str(milestone), re.I)]
    if month_milestones:
        duration_text = f"{duration_text} (latest extracted milestone: {month_milestones[-1]})"

    endpoints = _dedupe_keep_order(_get(facts, "endpoints", []) or [])[:10]
    endpoints_text = ", ".join(endpoints) if endpoints else NOT_EXPLICITLY_STATED

    regulatory = clean_table_evidence(_get(facts, "regulatory_plan"), max_words=45)
    health_econ = clean_table_evidence(_get(facts, "health_economics_plan"), max_words=45)
    ppie = clean_table_evidence(_get(facts, "ppie_plan"), max_words=35)
    ppie_lead = clean_table_evidence(_get(facts, "ppie_leadership_evidence"), max_words=25)
    inclusion = clean_table_evidence(_get(facts, "research_inclusion_plan"), max_words=35)
    project_management = clean_table_evidence(_get(facts, "project_management_plan"), max_words=35)
    finance = clean_table_evidence(_get(facts, "finance_or_budget_evidence"), max_words=40)

    groups = group_dashboard_by_rag(dashboard)
    risk_rows = [row for row in dashboard or [] if str(row.get("RAG", "")).upper() in {"RED", "AMBER", "GREY"}]
    top_actions = _dedupe_keep_order([row.get("Priority action", "") for row in risk_rows])[:5]

    return clean_markdown_output(f"""# Summary of key information extracted

    ## Project at a glance

    - **Project title:** {_safe(project_title)}
    - **Claimed funding call:** {_safe(claimed_call)}
    - **Intervention/product:** {_safe(product)}
    - **Acronym/module:** {_safe(acronym)}
    - **Technology type:** {technology}
    - **Target population:** {target_population}
    - **Clinical or care need:** {clinical_need}
    - **Setting:** {setting}

    The setting is {setting}.

    The summary is based on the runtime application and supporting documents only. Built-in NIHR/RSS guidance is used as checklist guidance, not as application evidence.

    ## Proposed evidence generation

    - **Design:** {study_design}
    - **Sample size:** {sample_size}
    - **Comparator/control:** {comparator}
    - **Development stage:** {trl}
    - **Timeline:** {duration_text}
    - **Main outcomes:** {endpoints_text}

    The extracted evidence is used only where it directly matches the requirement being checked. For example, duration or outcome evidence is not reused to satisfy unrelated applicant, finance or eligibility requirements.

    ## Adoption and delivery readiness

    - **Regulatory/adoption evidence:** {regulatory}
    - **Health economics evidence:** {health_econ}
    - **PPIE evidence:** {ppie}
    - **PPIE leadership evidence:** {ppie_lead}
    - **Research inclusion evidence:** {inclusion}
    - **Project management evidence:** {project_management}
    - **Finance evidence:** {finance}

    Finance is considered separately from health economics. Economic modelling, EQ-5D/QALY or cost-effectiveness wording supports health economics, while Finance requires actual budget, cost-category, rate, cap, AcoRD, SoECAT or cost-justification evidence.

    ## Main RSS checklist risks

    - **GREEN areas:** {", ".join(groups["GREEN"]) if groups["GREEN"] else "None identified from available evidence."}
    - **AMBER areas:** {", ".join(groups["AMBER"]) if groups["AMBER"] else "None identified from available evidence."}
    - **RED areas:** {", ".join(groups["RED"]) if groups["RED"] else "None identified from available evidence."}

    **Top adviser actions**

    {_lines(top_actions)}
    """)


def render_summary(
        facts: ApplicationFacts,
        dashboard: list[dict],
        priority_gaps: str = "",
) -> str:
    """Backward-compatible alias for the Summary tab renderer."""
    return render_main_case_summary(facts, dashboard, priority_gaps)


# ---------------------------------------------------------------------
# Checklist Report tab
# ---------------------------------------------------------------------


def render_checklist_report_summary(
        items: list[ChecklistItem],
        facts: ApplicationFacts | None = None,
) -> str:
    counts = _counts_by_rag(items)

    strongest = sorted(
        {
            str(_get(item, "area") or _to_dict(item).get("Checklist Area"))
            for item in items or []
            if str(_get(item, "rag") or _to_dict(item).get("RAG") or "").upper() == "GREEN"
        }
    )

    high_risk = sorted(
        {
            str(_get(item, "area") or _to_dict(item).get("Checklist Area"))
            for item in items or []
            if str(_get(item, "rag") or _to_dict(item).get("RAG") or "").upper() in {"RED", "AMBER"}
        }
    )

    evidence_found = sorted(
        {
            str(_get(item, "area") or _to_dict(item).get("Checklist Area"))
            for item in items or []
            if _present(_get(item, "evidence") or _to_dict(item).get("Evidence from application"))
                        and str(_get(item, "rag") or _to_dict(item).get("RAG") or "").upper() in {"GREEN", "AMBER"}
        }
    )

    missing_actions = _top_actions_from_items(items, {"RED", "AMBER"}, 5)

    return clean_markdown_output(f"""## Summary of key information extracted

    - **Checklist row counts:** GREEN {counts["GREEN"]}, AMBER {counts["AMBER"]}, RED {counts["RED"]}, GREY {counts["GREY"]}.
    - **Strongest evidenced areas:** {", ".join(strongest[:6]) if strongest else "None identified from available evidence."}
    - **Missing/high-risk areas:** {", ".join(high_risk[:6]) if high_risk else "None identified from available evidence."}
    - **Application evidence found for:** {", ".join(evidence_found[:8]) if evidence_found else "None identified from available evidence."}
    - **Evidence still missing:** focus on RED and AMBER rows where the table shows missing, partial or human-check status.

    **Adviser follow-up actions**

    {_lines(missing_actions[:5])}

    Built-in NIHR/RSS guidance is used as checklist guidance only. It is not treated as application evidence.

    Detailed row-level evidence is shown in the table below.
    """)


# ---------------------------------------------------------------------
# RAG Dashboard tab
# ---------------------------------------------------------------------


def render_rag_dashboard_summary(dashboard: list[dict]) -> str:
    groups = group_dashboard_by_rag(dashboard)

    red = groups["RED"]
    amber = groups["AMBER"]

    if red:
        profile = "high risk"
    elif amber:
        profile = "moderate risk"
    else:
        profile = "lower risk"

    actions: list[str] = []

    for row in dashboard or []:
        if str(row.get("RAG", "")).upper() in {"RED", "AMBER", "GREY"}:
            action = str(row.get("Priority action", "")).strip()
            if action and action not in actions:
                actions.append(action)

        if len(actions) >= 3:
            break

    return clean_markdown_output(f"""## Summary of key information extracted

    ### Overall risk profile

    The dashboard suggests a **{profile}** application profile. It summarises the detailed checklist into seven RSS risk areas.

    ### GREEN subsystems

    {_lines(groups["GREEN"])}

    ### AMBER subsystems

    {_lines(groups["AMBER"])}

    ### RED subsystems

    {_lines(groups["RED"])}

    ### Top adviser actions

    {_lines(actions[:3])}
    """)


# ---------------------------------------------------------------------
# Similarity Check tab
# ---------------------------------------------------------------------


def _clean_similarity_terms(terms: list[Any]) -> list[str]:
    """Return short, adviser-safe similarity terms with duplicates and placeholders removed."""
    blocked = {
        "second",
        "some",
        "adherence",
        "recruitment",
        "retention",
        "fidelity",
        "interviews",
        "training use only",
        "fictional example application",
    }

    cleaned: list[str] = []
    seen: set[str] = set()

    for term in terms or []:
        text = clean_display_value(term, max_chars=60)

        if not _present(text):
            continue

        key = text.lower().strip()

        if key in blocked:
            continue

        if len(text) > 60:
            continue

        if key not in seen:
            seen.add(key)
            cleaned.append(text)

        if len(cleaned) >= 8:
            break

    return cleaned


def _query_terms_from_similarity(similarity: dict) -> list[str]:
    terms: list[str] = []

    query = similarity.get("query") if isinstance(similarity, dict) else None

    if isinstance(query, dict):
        candidate_terms = list(query.get("primary_terms", [])) + list(query.get("secondary_terms", []))
    elif query is not None:
        candidate_terms = list(_get(query, "primary_terms", []) or []) + list(_get(query, "secondary_terms", []) or [])
    else:
        candidate_terms = []

    for term in candidate_terms:
        if _present(term):
            terms.append(str(term))

    for result in similarity.get("results", []) if isinstance(similarity, dict) else []:
        for term in result.get("query_terms_used", []) or []:
            if _present(term):
                terms.append(str(term))

    return _clean_similarity_terms(terms)


def similarity_query_terms_display(terms: list[str]) -> str:
    """Return cleaned similarity query terms for captions and disabled-result rows."""
    cleaned = _clean_similarity_terms(terms)
    return ", ".join(cleaned) if cleaned else NOT_EXPLICITLY_STATED


def render_similarity_check_summary(similarity: dict) -> str:
    similarity = similarity or {}
    results = similarity.get("results", [])

    clean_terms = _query_terms_from_similarity(similarity)

    statuses = [str(result.get("status", "")) for result in results if isinstance(result, dict)]

    if not results or all(status == "not_run" for status in statuses):
        run_state = "Similarity checking was disabled or not run."
    elif any(status == "error" for status in statuses):
        run_state = "Similarity checking partially failed for one or more sources."
    else:
        run_state = "Similarity checking ran for the available sources."

    highest = "NONE"

    for result in results:
        risk = str(result.get("risk", "NONE")).upper()
        if RISK_ORDER.get(risk, 0) > RISK_ORDER.get(highest, 0):
            highest = risk

    total_matches = sum(int(result.get("matches_found", 0) or 0) for result in results if isinstance(result, dict))

    errors = [
        str(result.get("why_relevant", "API error"))
        for result in results
        if isinstance(result, dict) and result.get("status") == "error"
    ]

    safe_errors = [
        re.sub(r"https?://\S+", "[URL suppressed]", error)
        for error in errors
    ]

    return clean_markdown_output(f"""## Summary of key information extracted

    ### Query basis

    Similarity checking used cleaned concept terms:

    {_lines(clean_terms)}

    ### Results

    - **Run status:** {run_state}
    - **Reported matches:** {total_matches}
    - **Overall novelty/similarity risk:** {highest}
    - **API errors:** {"; ".join(safe_errors) if safe_errors else "None reported."}

    ### Interpretation

    Similarity checking is an initial screening signal only. It does not prove novelty or duplication. Any potentially related records should be reviewed manually before drawing conclusions.

    Full application text, long sentence fragments and generic document labels should not be sent externally.
    """)


# ---------------------------------------------------------------------
# Priority Missing Evidence tab
# ---------------------------------------------------------------------


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


def _action(item: Any) -> str:
    area = str(_get(item, "area") or _to_dict(item).get("Checklist Area") or "")
    action = str(_get(item, "action") or _to_dict(item).get("Gap / action needed") or "")
    return ACTION_LIBRARY.get(area, action or "Add or verify application-specific evidence.")


def render_priority_missing_evidence(
        items: list[ChecklistItem],
        dashboard: list[dict] | None = None,
        facts: ApplicationFacts | None = None,
) -> str:
    critical: list[Any] = []
    amber: list[Any] = []
    grey: list[Any] = []
    uploads: list[Any] = []
    budget: list[Any] = []

    for item in items or []:
        area = str(_get(item, "area") or _to_dict(item).get("Checklist Area") or "")
        rag = str(_get(item, "rag") or _to_dict(item).get("RAG") or "").upper()

        if rag == "RED":
            critical.append(item)
        elif rag == "AMBER":
            amber.append(item)
        elif rag == "GREY":
            grey.append(item)

        if area == "Uploads" and rag != "GREEN":
            uploads.append(item)

        if area == "Budget and Finance" and rag != "GREEN":
            budget.append(item)

    def action_lines(entries: list[Any]) -> str:
        return _lines([_action(entry) for entry in entries])

    return clean_markdown_output(f"""# Priority Missing Evidence

    ## Summary of key information extracted

    These are practical adviser actions grouped by priority. They are generated from missing, partial or human-check checklist rows and should be resolved against the uploaded application and the specific funding call.

    ## Critical missing items

    {action_lines(critical)}

    ## Important but fixable gaps

    {action_lines(amber)}

    ## Items needing human judgement

    {action_lines(grey)}

    ## Uploads still needed

    {action_lines(uploads)}

    ## Budget/finance checks still needed

    {action_lines(budget)}
    """)


# ---------------------------------------------------------------------
# Executive Review Note
# ---------------------------------------------------------------------


def render_executive_review_note(
        facts: ApplicationFacts,
        dashboard: list[dict],
        priority_gaps: str = "",
) -> str:
    groups = group_dashboard_by_rag(dashboard)

    first_action = next(
        (
            row.get("Priority action")
            for row in dashboard or []
            if str(row.get("RAG", "")).upper() in {"RED", "AMBER", "GREY"}
        ),
        "Review the detailed checklist table.",
    )

    bullets = [
        f"- **Application focus:** {_safe(_get(facts, 'product_or_intervention'))} for {_compress(_get(facts, 'target_population'), 'population') or _safe(_get(facts, 'target_population'))}.",
        f"- **Evidence generation:** {_compress(_get(facts, 'study_design'), 'design') or _safe(_get(facts, 'study_design'))} with {_safe(_get(facts, 'sample_size'))}.",
        f"- **Timeline:** {_safe(_get(facts, 'duration_months'))} months.",
        f"- **Strongest areas:** {', '.join(groups['GREEN'][:3]) if groups['GREEN'] else 'None identified from available evidence.'}.",
        f"- **Areas needing attention:** {', '.join((groups['RED'] + groups['AMBER'])[:4]) if groups['RED'] or groups['AMBER'] else 'None identified from available evidence.'}.",
        f"- **Finance position:** {_safe(_get(facts, 'finance_or_budget_evidence'))}.",
        f"- **RSS adviser should check first:** {clean_display_value(first_action, max_chars=220)}.",
    ]

    return clean_markdown_output("## Executive review note\n\n" + "\n".join(bullets[:8]))


# ---------------------------------------------------------------------
# Table rendering helpers
# ---------------------------------------------------------------------


def clean_table_evidence(
        value: Any,
        area: str = "",
        requirement: str = "",
        max_words: int = 35,
) -> str:
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
        flags=re.I,
    )

    text = re.sub(r"\s+", " ", text)
    parts = [part.strip(" .;:\n\t") for part in re.split(r"[.;]\s+", text) if part.strip()]
    useful = [part for part in parts if not portal_noise.search(part)]

    cleaned = "; ".join(useful).strip(" ;")

    if not cleaned:
        return NOT_EXPLICITLY_STATED

    cleaned = clean_display_value(cleaned, max_chars=600)

    words = cleaned.split()
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words]).rstrip(" ,;:") + "…"

    return cleaned


def checklist_table_rows(items: list[ChecklistItem]) -> list[dict[str, Any]]:
    return render_table_display_dataframe(items, "checklist")


def dashboard_table_rows(rows: list[dict]) -> list[dict[str, Any]]:
    return render_table_display_dataframe(rows, "dashboard")



def _safe_similarity_link(source: str, link_or_id: object) -> str:
    value = str(link_or_id or "")
    if re.search(r"https?://", value, re.I) and re.search(r"EPO|NIHR|ops\.epo|opendatasoft|api/", f"{source} {value}", re.I):
        return "URL suppressed"
    return value

def similarity_table_rows(results: list[dict]) -> list[dict[str, Any]]:
    return render_table_display_dataframe(results, "similarity")


def render_table_display_dataframe(
        rows: list[Any],
        table_type: str = "checklist",
) -> list[dict[str, Any]]:
    if table_type == "checklist":
        rendered: list[dict[str, Any]] = []

        for item in rows or []:
            row = item.to_row() if isinstance(item, ChecklistItem) and hasattr(item, "to_row") else _to_dict(item)

            if not row:
                continue

            evidence = row.get("Evidence from application") or row.get("evidence") or NOT_EXPLICITLY_STATED
            action = row.get("Gap / action needed") or row.get("action") or ""

            row["Evidence from application"] = clean_table_evidence(
                evidence,
                row.get("Checklist Area", row.get("area", "")),
                row.get("Requirement", row.get("requirement", "")),
            )

            if action:
                row["Gap / action needed"] = clean_table_evidence(action, max_words=45)

            preferred_order = [
                "Checklist Area",
                "Requirement",
                "Source Guidance",
                "Status",
                "RAG",
                "Evidence from application",
                "Gap / action needed",
            ]

            normalised = {
                "Checklist Area": row.get("Checklist Area") or row.get("area", ""),
                "Requirement": row.get("Requirement") or row.get("requirement", ""),
                "Source Guidance": row.get("Source Guidance") or row.get("source_guidance", ""),
                "Status": row.get("Status") or row.get("status", ""),
                "RAG": row.get("RAG") or row.get("rag", ""),
                "Evidence from application": row.get("Evidence from application", NOT_EXPLICITLY_STATED),
                "Gap / action needed": row.get("Gap / action needed") or row.get("action", ""),
            }

            rendered.append(TableRow({key: normalised[key] for key in preferred_order}))

        return rendered

    if table_type == "dashboard":
        return [
            {
                key: value
                for key, value in dict(row).items()
                if key != "hard_validation_warnings"
            }
            for row in rows or []
        ]

    if table_type == "similarity":
        rendered = []

        for result in rows or []:
            query_terms = _dedupe_keep_order(result.get("query_terms_used", []) or [])[:8]

            rendered.append(
                {
                    "Source": result.get("source", ""),
                    "Status": result.get("status", ""),
                    "Query terms used": ", ".join(query_terms) if query_terms else NOT_EXPLICITLY_STATED,
                    "Raw records returned": result.get("raw_records_returned", result.get("matches_found", 0)),
                    "Matches found": result.get("matches_found", 0),
                    "Top match": clean_table_evidence(result.get("top_match", ""), "Similarity", "Top match"),
                    "Score": result.get("score", 0.0),
                    "Risk": result.get("risk", "NONE"),
                    "Similarity type": result.get("similarity_type", ""),
                    "Specific matched concepts": ", ".join(result.get("specific_matched_concepts", []) or []) or "None found",
                    "Generic matched concepts": ", ".join(result.get("generic_matched_concepts", []) or []) or "None found",
                    "Why relevant": clean_table_evidence(result.get("why_relevant", ""), "Similarity", "Why relevant"),
                    "Link/ID": _safe_similarity_link(result.get("source", ""), result.get("link_or_id", "")),
                }
            )

        return rendered

    return [_to_dict(row) for row in rows or []]


# ---------------------------------------------------------------------
# Raw JSON helpers
# ---------------------------------------------------------------------


def render_raw_json_note() -> str:
    return RAW_JSON_DEBUG_NOTE


def raw_json_payload(**kwargs: Any) -> str:
    def default(obj: Any) -> Any:
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if is_dataclass(obj):
            return asdict(obj)
        return str(obj)

    return json.dumps(kwargs, default=default, indent=2)


# ---------------------------------------------------------------------
# Public export contract
# ---------------------------------------------------------------------


EXPECTED_RENDERER_FUNCTIONS = (
    "render_main_case_summary",
    "render_checklist_report_summary",
    "render_rag_dashboard_summary",
    "render_similarity_check_summary",
    "render_priority_missing_evidence",
    "render_executive_review_note",
    "render_table_display_dataframe",
    "render_raw_json_note",
    "similarity_query_terms_display",
)

__all__ = (
    "TableRow",
    "checklist_table_rows",
    "clean_display_value",
    "clean_table_evidence",
    "dashboard_table_rows",
    "group_dashboard_by_rag",
    "raw_json_payload",
    "render_summary",
    "similarity_table_rows",
    *EXPECTED_RENDERER_FUNCTIONS,
)
