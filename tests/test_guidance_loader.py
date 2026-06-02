from guidance_loader import build_baseline_requirement_bank, classify_guidance_file, load_builtin_guidance


def test_repo_txt_files_loaded_as_guidance_not_applications():
    docs = load_builtin_guidance()
    names = {d.name for d in docs}
    assert "nihr_domestic_guidance.txt" in names
    assert "rss_pda_playbook_notes.txt" in names
    assert all(not d.is_application_example for d in docs)


def test_guidance_classification():
    assert classify_guidance_file("nihr_domestic_guidance.txt") == "nihr_domestic"
    assert classify_guidance_file("rss_pda_playbook_notes.txt") == "rss_playbook"


def test_baseline_requirement_bank_built():
    bank = build_baseline_requirement_bank()
    assert bank
    assert {r.source for r in bank} >= {"nihr_domestic", "rss_playbook", "derived_reviewer_check"}
