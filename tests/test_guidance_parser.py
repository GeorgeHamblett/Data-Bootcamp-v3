from guidance_parser import merge_requirements_with_specific_override, parse_guidance_text
from schemas import Requirement


def test_parse_budget_upload_ai_requirements():
    text = "Budget section\nYou must include AcoRD, SoECAT if applicable, current rates and justification of costs.\nUploads\nYou must upload references and a Gantt chart if specified.\nAcknowledgement\nYou must acknowledge generative AI usage."
    reqs = parse_guidance_text(text, "nihr_domestic")
    joined = " ".join(r.requirement_text for r in reqs)
    assert "AcoRD" in joined and "SoECAT" in joined and "AI" in joined
    assert any(r.mandatory_status == "required_if_applicable" for r in reqs)


def test_specific_call_overrides_baseline():
    baseline = [Requirement("b1", "nihr_domestic", "s", "Eligibility", "General eligibility")]
    specific = [Requirement("s1", "specific_call", "s", "Eligibility", "Specific eligibility", overrides_general_guidance=True)]
    merged = merge_requirements_with_specific_override(baseline, specific)
    assert merged[0].requirement_text == "Specific eligibility"
    assert not any(r.requirement_text == "General eligibility" for r in merged)


def test_guidance_parser_excludes_portal_instructions_and_uses_curated_baselines():
    noisy = "Click Invite and fill in name/email. Save draft. Use this guidance. The application must include a budget section."
    reqs = parse_guidance_text(noisy, "programme_guidance")
    joined = " ".join(r.requirement_text for r in reqs).lower()
    assert "click invite" not in joined
    assert "fill in" not in joined
    assert "save draft" not in joined
    assert "use this guidance" not in joined

    nihr = parse_guidance_text("click Invite repeatedly", "nihr_domestic", "NIHR")
    rss = parse_guidance_text("portal instructions", "rss_playbook", "RSS")
    assert any(r.requirement_text == "Contracting organisation identified" for r in nihr)
    assert any(r.requirement_text == "Eligible lead and organisation evidenced" for r in rss)
    assert any("Flow diagram" in r.requirement_text and r.mandatory_status == "required_if_applicable" for r in nihr)


def test_specific_call_flow_diagram_mandatory():
    reqs = parse_guidance_text("Applicants must upload a flow diagram with the application.", "specific_call", "CALL")
    assert any("flow diagram" in r.requirement_text.lower() and r.mandatory_status == "mandatory" for r in reqs)
