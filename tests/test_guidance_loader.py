from guidance_loader import build_baseline_requirement_bank, classify_guidance_file, load_guidance_documents


def test_repo_txt_files_loaded_as_guidance_not_applications():
    docs = load_guidance_documents(".")
    names = {d.name for d in docs}
    assert "nihr_domestic_guidance.txt" in names
    assert "rss_pda_playbook_notes.txt" in names
    assert all(d.is_application_example is False for d in docs)


def test_guidance_classification():
    assert classify_guidance_file("nihr_domestic_guidance.txt") == "nihr_domestic"
    assert classify_guidance_file("rss_pda_playbook_notes.txt") == "rss_playbook"


def test_baseline_requirement_bank_built():
    bank = build_baseline_requirement_bank(".")
    assert bank
    assert any(r.source == "nihr_domestic" for r in bank)
    assert any(r.source == "rss_playbook" for r in bank)


def test_builtin_guidance_filename_search_and_contextual_pda_filter():
    docs = load_guidance_documents(".")
    by_name = {doc.name: doc for doc in docs}
    assert by_name["nihr_domestic_guidance.txt"].source == "nihr_domestic"
    assert by_name["rss_pda_playbook_notes.txt"].source == "rss_playbook"

    nihr_only = build_baseline_requirement_bank(".", include_pda_playbook=False)
    assert any(req.source == "nihr_domestic" for req in nihr_only)
    assert not any(req.source == "rss_playbook" for req in nihr_only)

    with_pda = build_baseline_requirement_bank(".", include_pda_playbook=True)
    assert any(req.source == "rss_playbook" for req in with_pda)


def test_pda_relevance_detection_is_generic():
    from guidance_loader import detects_pda_relevance
    assert detects_pda_relevance("This is an i4i Product Development Award call")
    assert detects_pda_relevance("The application develops a medical device from current TRL 3")
    assert not detects_pda_relevance("This is an evidence synthesis application about service delivery.")
