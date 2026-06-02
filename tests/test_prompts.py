import prompts

REQUIRED = [
    "SYSTEM_REVIEWER_PROMPT", "GUIDANCE_REQUIREMENT_EXTRACTION_PROMPT", "SPECIFIC_CALL_REQUIREMENT_PROMPT",
    "APPLICATION_FACT_EXTRACTION_PROMPT", "EVIDENCE_MATCHING_PROMPT", "CHECKLIST_ITEM_EVALUATION_PROMPT",
    "RAG_DASHBOARD_PROMPT", "SUMMARY_PROMPT", "SIMILARITY_QUERY_EXTRACTION_PROMPT",
    "SIMILARITY_RESULT_INTERPRETATION_PROMPT", "PRIORITY_MISSING_EVIDENCE_PROMPT", "OUTPUT_QUALITY_VALIDATION_PROMPT",
]


def test_required_prompts_exist_with_purpose():
    for name in REQUIRED:
        value = getattr(prompts, name)
        assert isinstance(value, str) and "Purpose:" in value


def test_extraction_prompts_require_json_and_forbid_invention():
    for name in ["GUIDANCE_REQUIREMENT_EXTRACTION_PROMPT", "SPECIFIC_CALL_REQUIREMENT_PROMPT", "APPLICATION_FACT_EXTRACTION_PROMPT", "EVIDENCE_MATCHING_PROMPT"]:
        text = getattr(prompts, name).lower()
        assert "output json" in text
        assert "do not invent" in text or "must not invent" in text


def test_prompts_distinguish_application_from_guidance():
    combined = "\n".join(getattr(prompts, name) for name in REQUIRED).lower()
    assert "distinguish application evidence" in combined
    assert "do not use guidance text as evidence" in combined or "not treat guidance text as application evidence" in combined


def test_summary_prompt_not_raw_field_list():
    text = prompts.SUMMARY_PROMPT.lower()
    assert "not a field list" in text
    assert "narrative" in text


def test_similarity_prompt_excludes_generic_terms():
    text = prompts.SIMILARITY_QUERY_EXTRACTION_PROMPT.lower()
    for term in ["uploaded", "document", "docx", "pdf", "application", "gantt", "guidance"]:
        assert term in text
    assert "at least two meaningful" in text
