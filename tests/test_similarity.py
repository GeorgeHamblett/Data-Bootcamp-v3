from schemas import ApplicationFacts
from settings import Settings
from similarity.query_builder import build_similarity_query, is_generic_term
from similarity.service import run_similarity_service


def facts():
    return ApplicationFacts(product_or_intervention="CardioPatch", acronym_or_short_name="CPX", clinical_or_social_care_need="atrial fibrillation detection", target_population="older adults", technology_type="wearable ECG sensor")


def test_generic_filename_document_terms_excluded():
    assert is_generic_term("uploaded")
    assert is_generic_term("docx")
    q = build_similarity_query(facts(), ["uploaded application docx template"])
    assert "uploaded" not in q.query_string
    assert q.meaningful_term_count >= 2


def test_mock_default_false_and_disabled_no_api(monkeypatch):
    settings = Settings()
    called = {"value": False}
    def fake(*args, **kwargs):
        called["value"] = True
    monkeypatch.setattr("similarity.service.search_lens", fake)
    result = run_similarity_service(facts(), settings, run_similarity_check=False)
    assert all(r["status"] == "not_run" for r in result["results"])
    assert not settings.mock_similarity_mode
    assert called["value"] is False


def test_local_only_blocks_live_apis_and_mock_explicit():
    settings = Settings(local_only_mode=True, allow_external_similarity_queries=True)
    result = run_similarity_service(facts(), settings, run_similarity_check=True, mock_mode=False)
    assert all(r["status"] == "not_run" for r in result["results"])
    mock = run_similarity_service(facts(), settings, run_similarity_check=True, mock_mode=True)
    assert all("Mock mode explicitly enabled" in r["why_relevant"] for r in mock["results"])


def test_training_labels_excluded_and_no_full_text_query():
    app_text = "FOR TRAINING USE ONLY FICTIONAL EXAMPLE APPLICATION " + "x" * 1000
    q = build_similarity_query(facts(), [app_text])
    query = q.query_string.lower()
    assert "training" not in query
    assert "fictional" not in query
    assert "x" * 50 not in query

from tests.fixtures import STEPRIGHT_APP
from similarity.scoring import score_result


def test_stepright_query_terms_short_clean_deduped_meaningful():
    f = ApplicationFacts(
        product_or_intervention="StepRight",
        acronym_or_short_name="MQAE",
        clinical_or_social_care_need="falls prevention, balance, mobility rehabilitation, confidence and independence",
        target_population="older adults aged 60+ at risk of falling / with reduced balance confidence",
        technology_type="AI-enabled wearable digital therapeutic / movement quality assessment platform",
        sites_or_setting="NHS community rehabilitation",
        endpoints=["recruitment", "retention", "SUS", "EQ-5D-5L"],
    )
    q = build_similarity_query(f, ["TRAINING USE ONLY FICTIONAL EXAMPLE APPLICATION This project will test StepRight. Many people do. Falls can seriously. Milestones Month 8."])
    terms = q.primary_terms + q.secondary_terms
    assert len(terms) <= 8
    assert len(terms) >= 2
    assert len({t.lower() for t in terms}) == len(terms)
    assert all(len(t) <= 60 for t in terms)
    assert not any(t.startswith("This project will") for t in terms)
    joined = " ".join(terms).lower()
    for bad in ["training use only", "fictional example application", "many people do", "falls can seriously", "milestones month"]:
        assert bad not in joined
    assert "This project will test StepRight" not in q.query_string


def test_api_error_suppresses_full_query_url_and_epo_uses_short_terms(monkeypatch):
    f = facts()
    settings = Settings(local_only_mode=False, allow_external_similarity_queries=True)
    def boom(query, settings):
        raise RuntimeError("404 https://example.test/search?q=" + "x" * 200)
    monkeypatch.setattr("similarity.service.search_lens", boom)
    monkeypatch.setattr("similarity.service.search_epo", lambda query, settings: {"source":"EPO OPS", "status":"success", "matches_found":0, "top_match":"", "raw":"", "link_or_id":""})
    monkeypatch.setattr("similarity.service.search_nihr_open_data", lambda query, settings: {"source":"NIHR Open Data", "status":"success", "matches_found":0, "top_match":"", "raw":"", "link_or_id":""})
    result = run_similarity_service(f, settings, run_similarity_check=True)
    lens = next(r for r in result["results"] if r["source"] == "Lens Scholarly")
    assert "https://example.test" not in lens["why_relevant"]
    epo = next(r for r in result["results"] if r["source"] == "EPO OPS")
    assert all(len(t) <= 60 and len(t.split()) <= 5 for t in epo["query_terms_used"])


def test_single_generic_sus_overlap_is_none():
    scored = score_result(["SUS"], "A study using SUS", "")
    assert scored["risk"] == "NONE"
    assert scored["score"] == 0.0
