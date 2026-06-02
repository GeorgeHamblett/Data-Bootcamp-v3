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


def test_required_internal_prompts_present_with_purpose():
    for name in REQUIRED:
        text = getattr(prompts, name)
        assert isinstance(text, str) and len(text) > 100
        assert "Purpose:" in text


def test_extraction_prompts_require_json():
    for name in ["GUIDANCE_REQUIREMENT_EXTRACTION_PROMPT", "SPECIFIC_CALL_REQUIREMENT_PROMPT", "APPLICATION_FACT_EXTRACTION_PROMPT", "EVIDENCE_MATCHING_PROMPT"]:
        assert "JSON" in getattr(prompts, name)


def test_prompts_forbid_invention_and_distinguish_guidance():
    combined = "\n".join(getattr(prompts, n) for n in REQUIRED)
    assert "Do not invent" in combined or "must not invent" in combined
    assert "guidance" in combined.lower() and "application evidence" in combined.lower()
    assert "must not treat guidance text as application evidence" in prompts.SYSTEM_REVIEWER_PROMPT


def test_summary_not_raw_field_list_and_similarity_excludes_generic_terms():
    assert "Not a field list" in prompts.SUMMARY_PROMPT or "raw field-list" in prompts.SUMMARY_PROMPT
    for term in ["uploaded", "docx", "application", "template", "playbook", "guidance"]:
        assert term in prompts.SIMILARITY_QUERY_EXTRACTION_PROMPT
