import prompts

REQUIRED = [
    "SYSTEM_REVIEWER_PROMPT",
    "GUIDANCE_REQUIREMENT_EXTRACTION_PROMPT",
    "SPECIFIC_CALL_REQUIREMENT_PROMPT",
    "APPLICATION_FACT_EXTRACTION_PROMPT",
    "EVIDENCE_MATCHING_PROMPT",
    "CHECKLIST_ITEM_EVALUATION_PROMPT",
    "RAG_DASHBOARD_PROMPT",
    "SUMMARY_PROMPT",
    "SIMILARITY_QUERY_EXTRACTION_PROMPT",
    "SIMILARITY_RESULT_INTERPRETATION_PROMPT",
    "PRIORITY_MISSING_EVIDENCE_PROMPT",
    "OUTPUT_QUALITY_VALIDATION_PROMPT",
]

SECTION_PROMPTS = [
    "MAIN_CASE_SUMMARY_PROMPT",
    "CHECKLIST_REPORT_SUMMARY_PROMPT",
    "RAG_DASHBOARD_SUMMARY_PROMPT",
    "SIMILARITY_CHECK_SUMMARY_PROMPT",
    "PRIORITY_MISSING_EVIDENCE_PROMPT",
    "EXECUTIVE_REVIEW_NOTE_PROMPT",
    "TABLE_EVIDENCE_DISPLAY_PROMPT",
    "RAW_JSON_NOTE_PROMPT",
]


def test_required_internal_prompts_present_with_purpose():
    for name in REQUIRED:
        text = getattr(prompts, name)
        assert isinstance(text, str) and len(text) > 100
        assert "Purpose:" in text


def test_required_section_prompts_exist_and_are_focused():
    focus_words = {
        "MAIN_CASE_SUMMARY_PROMPT": "Summary tab",
        "CHECKLIST_REPORT_SUMMARY_PROMPT": "Checklist Report tab",
        "RAG_DASHBOARD_SUMMARY_PROMPT": "RAG Dashboard tab",
        "SIMILARITY_CHECK_SUMMARY_PROMPT": "Similarity Check tab",
        "PRIORITY_MISSING_EVIDENCE_PROMPT": "Priority Missing Evidence",
        "EXECUTIVE_REVIEW_NOTE_PROMPT": "executive adviser note",
        "TABLE_EVIDENCE_DISPLAY_PROMPT": "table evidence display",
        "RAW_JSON_NOTE_PROMPT": "Raw JSON",
    }
    for name in SECTION_PROMPTS:
        text = getattr(prompts, name)
        assert isinstance(text, str) and "Purpose:" in text
        assert focus_words[name].lower() in text.lower()


def test_section_prompts_share_output_safety_rules():
    for name in SECTION_PROMPTS[:-1]:
        text = getattr(prompts, name)
        assert "Markdown only" in text
        assert "Do not invent" in text or "not invent" in text
        assert "Do not output raw JSON" in text or "Do not output JSON" in text
        assert "Do not treat built-in guidance as application evidence" in text
        assert "Do not hard-code" in text


def test_extraction_prompts_require_json():
    for name in ["GUIDANCE_REQUIREMENT_EXTRACTION_PROMPT", "SPECIFIC_CALL_REQUIREMENT_PROMPT", "APPLICATION_FACT_EXTRACTION_PROMPT", "EVIDENCE_MATCHING_PROMPT"]:
        assert "JSON" in getattr(prompts, name)


def test_prompts_forbid_invention_and_distinguish_guidance():
    combined = "\n".join(getattr(prompts, n) for n in REQUIRED + SECTION_PROMPTS)
    assert "Do not invent" in combined or "must not invent" in combined
    assert "guidance" in combined.lower() and "application evidence" in combined.lower()
    assert "must not treat guidance text as application evidence" in prompts.SYSTEM_REVIEWER_PROMPT


def test_summary_not_raw_field_list_and_similarity_excludes_generic_terms():
    assert "Not a field list" in prompts.SUMMARY_PROMPT or "raw field-list" in prompts.SUMMARY_PROMPT
    for term in ["uploaded", "docx", "application", "template", "playbook", "guidance"]:
        assert term in prompts.SIMILARITY_QUERY_EXTRACTION_PROMPT
