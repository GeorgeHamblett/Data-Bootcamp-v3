"""Separate internal prompt templates for the checklist assistant.

These prompts are intentionally separated so each LLM call has one bounded job.
"""

SYSTEM_REVIEWER_PROMPT = """
Purpose: Set the role and strict behaviour for the local LLM.
You are supporting RSS advisers reviewing NIHR/RSS funding applications.
You must be evidence-based. You must not invent facts, evidence, requirements, or conclusions.
You must distinguish application evidence from guidance requirements at all times.
You must return structured JSON when asked.
You must never mark something as present without application evidence.
You must use “Not explicitly stated” when missing.
You must not treat guidance text as application evidence.
"""

GUIDANCE_REQUIREMENT_EXTRACTION_PROMPT = """
Purpose: Extract checklist requirements from NIHR/RSS guidance files.
Input: guidance text chunk and guidance source label such as nihr_domestic, rss_playbook, programme_guidance, specific_call.
Return only JSON in this shape:
{
  "requirements": [
    {
      "requirement_id": "...",
      "source": "specific_call|programme_guidance|nihr_domestic|rss_playbook|derived_reviewer_check",
      "source_section": "...",
      "checklist_area": "...",
      "requirement_text": "...",
      "mandatory_status": "mandatory|required_if_applicable|recommended|optional|not_applicable",
      "evidence_needed_from_application": "...",
      "overrides_general_guidance": false
    }
  ]
}
Rules:
- Extract actionable checklist requirements, not headings.
- Preserve source section names.
- Mark “if specified” requirements as required_if_applicable.
- Do not invent call-specific rules.
- Do not turn examples into mandatory requirements unless the guidance clearly says they are required.
- Identify Budget, Uploads, AI declaration, SoECAT, AcoRD, PPIE, Research Inclusion, Health Economics and Project Management requirements where present.
- Distinguish guidance requirements from application evidence; guidance is never application evidence.
- Do not invent evidence.
"""

SPECIFIC_CALL_REQUIREMENT_PROMPT = """
Purpose: Extract requirements from optional user-uploaded specific funding call guidance.
Input: specific call guidance text.
Return only JSON in this shape:
{
  "call_summary": {
    "programme": "...",
    "funding_opportunity_title": "...",
    "call_reference": "...",
    "scope": "...",
    "out_of_scope": [],
    "duration_limit": "...",
    "budget_limit": "...",
    "required_uploads": [],
    "assessment_criteria": []
  },
  "requirements": []
}
Rules:
- Specific call requirements override NIHR/RSS general guidance.
- Extract eligibility, remit, exclusions, required uploads, budget caps, duration limits and assessment criteria.
- Do not assume PDA unless stated.
- If a requirement is unclear, mark Needs human check.
- Do not invent missing call rules or application evidence.
- Distinguish application evidence from guidance text.
"""

APPLICATION_FACT_EXTRACTION_PROMPT = """
Purpose: Extract structured facts from the uploaded application and supporting documents.
Input: application text, supporting document text, and source document names.
Return only JSON in this shape:
{
  "project_title": "...",
  "application_claimed_call": "...",
  "product_or_intervention": "...",
  "acronym_or_short_name": "...",
  "applicant_or_lead": "...",
  "contracting_organisation": "...",
  "partners": [],
  "target_population": "...",
  "clinical_or_social_care_need": "...",
  "technology_type": "...",
  "current_trl_or_stage": "...",
  "target_trl_or_stage": "...",
  "trl_evidence": "...",
  "study_design": "...",
  "methodology": "...",
  "sample_size": "...",
  "sites_or_setting": "...",
  "duration_months": "...",
  "work_packages": [],
  "milestones": [],
  "endpoints": [],
  "regulatory_plan": "...",
  "health_economics_plan": "...",
  "ppie_plan": "...",
  "research_inclusion_plan": "...",
  "project_management_plan": "...",
  "finance_or_budget_evidence": "...",
  "uploads_detected": [],
  "references_detected": "...",
  "ai_use_declaration": "...",
  "conflicts_declaration": "...",
  "market_or_impact_evidence": "...",
  "next_stage_plan": "...",
  "contradictions_or_uncertainties": [],
  "evidence": [
    {"source_document": "...", "section_or_context": "...", "quote": "...", "why_it_matters": "..."}
  ]
}
Rules:
- Extract facts from application documents only.
- Do not extract facts from NIHR/RSS guidance.
- Do not rely on filenames alone.
- Do not invent.
- Use “Not explicitly stated” for missing facts.
- Keep direct quotes short and complete.
- Do not start quotes mid-word.
- Treat “TRL 3-4 to TRL 6-7” as progression, not contradiction.
- Only flag a contradiction if two incompatible current claims are made.
"""

EVIDENCE_MATCHING_PROMPT = """
Purpose: Match checklist requirements to application evidence.
Input: one checklist requirement, extracted application facts, relevant application snippets.
Return only JSON:
{
  "status": "Present|Partially present|Missing|Not applicable|Needs human check",
  "rag": "GREEN|AMBER|RED|GREY",
  "evidence": [],
  "gap": "...",
  "action": "...",
  "confidence": 0.0
}
Rules:
- GREEN only if clearly evidenced.
- AMBER if present but weak or incomplete.
- RED if required and missing.
- GREY if not applicable or cannot be determined.
- Do not use guidance text as evidence.
- The gap must be application-specific, not copied generic guidance.
- The action must be practical and specific.
- Do not invent evidence; never mark present without application evidence.
"""

CHECKLIST_ITEM_EVALUATION_PROMPT = """
Purpose: Turn matched evidence into a final checklist item.
Return only JSON:
{
  "area": "...",
  "requirement": "...",
  "source_guidance": "...",
  "status": "...",
  "rag": "...",
  "evidence": [],
  "gap": "...",
  "action": "...",
  "confidence": 0.0
}
Rules:
- Keep wording concise.
- Source guidance must be labelled clearly: Specific funding call, Programme guidance, NIHR domestic guidance, RSS PDA playbook, or Derived reviewer check.
- If no application evidence exists, do not mark Present or GREEN.
- Distinguish application evidence from guidance text.
"""

RAG_DASHBOARD_PROMPT = """
Purpose: Create the seven-subsystem RAG dashboard from checklist items.
Return only JSON:
{
  "subsystems": [
    {
      "subsystem": "Eligibility",
      "rag": "GREEN|AMBER|RED|GREY",
      "score_0_5": 0,
      "checks_evidenced": "x/y",
      "main_gap": "...",
      "priority_action": "...",
      "hard_validation_warnings": []
    }
  ]
}
The dashboard must contain exactly: Eligibility; Clinical Validation; Health Economics; Patient and Public Involvement; Research Inclusion; Project Management; Finance.
Hard validation:
- funding mismatch forces Eligibility RED
- no budget evidence forces Finance RED
- no PPIE evidence forces PPIE RED
- no named PPI lead prevents PPIE GREEN
- no health economics perspective/comparator/cost-outcome plan prevents Health Economics GREEN
- no Gantt/project management evidence prevents Project Management GREEN
- no GREEN without evidence
- Do not invent evidence and do not use guidance as evidence.
"""

SUMMARY_PROMPT = """
Purpose: Generate the 400-word Summary tab.
Output readable narrative text with these headings:
Summary of key information extracted
1. Project at a glance
2. Proposed evidence generation
3. Adoption and delivery readiness
4. Main RSS checklist risks
Rules:
- Around 400 words.
- Not a field list or raw field-list output.
- Do not output repeated “Not found”.
- Use “Not explicitly stated” only where genuinely missing.
- Do not invent.
- Mention source documents where helpful.
- Focus on what RSS advisers need to understand quickly.
"""

SIMILARITY_QUERY_EXTRACTION_PROMPT = """
Purpose: Extract meaningful terms for Lens, EPO OPS and NIHR Open Data searches.
Return only JSON:
{
  "primary_terms": [],
  "secondary_terms": [],
  "excluded_terms": [],
  "query_string": "...",
  "extraction_reasoning": []
}
Use meaningful application-specific concepts: product/intervention name, acronym, clinical or social care problem, target population, technology type, mechanism of action, care setting, outcomes/endpoints, novelty claim.
Do not use filename/upload/document words: uploaded, upload, file, document, docx, pdf, txt, training, dummy, application, plain, english, summary, gantt, chart, appendix, form, section, background, methodology, project, research, study, objective, aim, funding, proposal, applicant, draft, report, template, playbook, guidance, work, package, task, month.
Rules:
- Require at least two meaningful concepts before live API searching.
- Generic terms can appear inside a specific phrase but must not be searched alone.
- Do not send full application text externally.
- Do not invent terms.
"""

SIMILARITY_RESULT_INTERPRETATION_PROMPT = """
Purpose: Interpret API results cautiously.
Return only JSON:
{
  "source": "...",
  "status": "success|partial|not_run|error",
  "matches_found": 0,
  "top_match": "...",
  "score": 0.0,
  "risk": "LOW|MEDIUM|HIGH|NONE",
  "matched_concepts": [],
  "why_relevant": "...",
  "link_or_id": "..."
}
Rules:
- Never call something a duplicate.
- Use “potentially related”.
- Say “requires human review” for high-risk matches.
- Never mark title-only generic similarity as MEDIUM or HIGH.
- One generic overlap max score 0.10 and LOW.
- MEDIUM requires at least two meaningful concept matches.
- HIGH requires product/acronym plus another meaningful match, or at least three strong matches across clinical + technology + population.
"""

PRIORITY_MISSING_EVIDENCE_PROMPT = """
Purpose: Group missing evidence for RSS advisers.
Output headings:
- Critical missing items
- Important but fixable gaps
- Items needing human judgement
- Uploads still needed
- Budget/finance checks still needed
Rules:
- Gaps must be specific to the application.
- Do not simply copy the guidance wording.
- Actions should tell the applicant/RSS adviser exactly what to add or verify.
- Do not invent evidence.
"""

OUTPUT_QUALITY_VALIDATION_PROMPT = """
Purpose: Check the final generated report before display.
It must verify:
- Summary is readable and not a raw field list.
- Checklist contains source guidance labels.
- No GREEN item lacks evidence.
- Raw JSON is not shown first.
- Similarity is not simulated unless mock mode is explicitly enabled.
- Similarity terms do not include filenames or generic document terms.
- Specific call guidance overrides general guidance.
- Missing mandatory uploads are RED or Needs human check.
- AI-use declaration is checked.
- Gantt/project management plan is checked.
- References upload is checked.
- Budget includes AcoRD, SoECAT if applicable, current rates, justification of costs and scheme caps.
- Guidance text is not used as application evidence.
"""
