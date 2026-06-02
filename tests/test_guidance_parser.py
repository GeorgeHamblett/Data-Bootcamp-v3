from guidance_parser import merge_requirements_with_overrides, parse_guidance_requirements
from schemas import Requirement


def test_parser_extracts_budget_upload_ai_requirements():
    text = "Budget\nYou must justify costs and include SoECAT if applicable.\nUploads\nYou must upload references.\nAI\nYou must acknowledge generative AI use."
    reqs = parse_guidance_requirements(text, "nihr_domestic")
    areas = {r.checklist_area for r in reqs}
    assert "Budget and Finance" in areas
    assert "Uploads" in areas
    assert "Acknowledgement and Conflicts" in areas
    assert any(r.mandatory_status == "required_if_applicable" for r in reqs)


def test_specific_call_overrides_baseline_area():
    baseline = [Requirement("b1", "nihr_domestic", "s", "Budget and Finance", "General budget", "mandatory")]
    specific = [Requirement("s1", "specific_call", "s", "Budget and Finance", "Call budget cap £100k", "mandatory", overrides_general_guidance=True)]
    merged = merge_requirements_with_overrides(baseline, specific)
    assert merged == specific
