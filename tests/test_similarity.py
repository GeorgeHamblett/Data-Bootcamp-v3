from schemas import ApplicationFacts
from settings import Settings
from similarity.query_builder import build_similarity_query, is_generic_term
from similarity.service import run_similarity_service
from similarity.epo_ops import build_epo_cql_query, search_epo, _token


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


def test_strict_local_only_blocks_live_apis_and_mock_explicit():
    settings = Settings(strict_local_only_mode=True, allow_external_similarity_queries=True)
    result = run_similarity_service(facts(), settings, run_similarity_check=True, mock_mode=False)
    assert all(r["status"] == "not_run" for r in result["results"])
    assert all("Strict local-only mode" in r["why_relevant"] for r in result["results"])
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

from tests.fixtures import WOUNDWISE_APP
from application_facts import extract_application_facts
from document_loader import LoadedDocument


def test_woundwise_similarity_query_excludes_stopwords_and_fragments():
    f = extract_application_facts([LoadedDocument("app.txt", WOUNDWISE_APP)])
    q = build_similarity_query(f, [WOUNDWISE_APP, "pressure wounds or surgical w"])
    terms = q.primary_terms + q.secondary_terms
    normalised_terms = {term.lower() for term in terms}
    assert "the" not in normalised_terms
    assert "early" not in normalised_terms
    assert not any(term.lower().endswith(" surgical w") or term.lower() == "pressure wounds or surgical w" for term in terms)
    joined = " ".join(terms).lower()
    for expected in ["woundwise-ai", "multispectral wound imaging", "wound imaging device", "software as a medical device", "wound deterioration detection"]:
        assert expected in joined
    assert any(term in joined for term in ["lower-limb wounds", "pressure wounds", "surgical wounds", "community wound services"])


def test_stopword_only_similarity_match_scores_none():
    scored = score_result(["The"], "The CJD mice project", "The study evaluates a mouse model.")
    assert scored["risk"] == "NONE"
    assert scored["score"] == 0.0



def test_local_llm_mode_does_not_block_epo(monkeypatch):
    f = facts()
    settings = Settings(
        require_local_llm=True,
        strict_local_only_mode=False,
        allow_external_similarity_queries=True,
        send_only_safe_query_terms=True,
        epo_ops_consumer_key="key",
        epo_ops_consumer_secret="secret",
    )
    called = {"epo": False}
    monkeypatch.setattr("similarity.service.search_lens", lambda query, settings: {"source":"Lens Scholarly", "status":"not_run", "matches_found":0, "top_match":"Lens skipped", "raw":"", "link_or_id":""})
    def fake_epo(query, settings):
        called["epo"] = True
        assert isinstance(query, list)
        return {"source":"EPO OPS", "status":"success", "matches_found":0, "top_match":"", "raw":"", "link_or_id":"EP1234567"}
    monkeypatch.setattr("similarity.service.search_epo", fake_epo)
    monkeypatch.setattr("similarity.service.search_nihr_open_data", lambda query, settings: {"source":"NIHR Open Data", "status":"success", "matches_found":0, "top_match":"", "raw":"", "link_or_id":""})
    run_similarity_service(f, settings, run_similarity_check=True)
    assert called["epo"] is True


def test_external_similarity_privacy_gates_block_separately():
    disabled = run_similarity_service(facts(), Settings(allow_external_similarity_queries=False), run_similarity_check=True)
    assert all("External similarity queries are disabled" in row["why_relevant"] for row in disabled["results"])
    unsafe = run_similarity_service(facts(), Settings(send_only_safe_query_terms=False), run_similarity_check=True)
    assert all("Safe-query-term privacy gate is disabled" in row["why_relevant"] for row in unsafe["results"])


def test_missing_epo_credentials_safe_message():
    result = search_epo(["WoundWise-AI", "wound imaging device"], Settings(epo_ops_consumer_key="", epo_ops_consumer_secret=""))
    assert result["status"] == "not_run"
    assert "credentials are missing" in result["why_relevant"]
    assert "replace_with" not in str(result)


def test_epo_specific_query_builder_excludes_bad_terms():
    cql, safe_terms = build_epo_cql_query(["The", "early", "pressure wounds or surgical w", "WoundWise-AI", "wound imaging device", "multispectral wound imaging", "wound deterioration"])
    lower = cql.lower()
    assert "the" not in lower
    assert "early" not in lower
    assert "surgical w" not in lower
    assert "WoundWise-AI" in safe_terms
    assert "wound imaging device" in safe_terms
    assert 'ta="woundwise-ai"' in lower
    assert 'ta="wound imaging device"' in lower
    assert cql.count("ta=") <= 4


def test_epo_api_errors_never_expose_url_or_secrets(monkeypatch):
    class FakeResponse:
        status_code = 400
        text = "bad query https://ops.epo.org/3.2/rest-services/published-data/search/biblio?q=secret"
        def raise_for_status(self):
            import requests
            raise requests.HTTPError("400 https://ops.epo.org/3.2/rest-services/published-data/search/biblio?q=secret-token", response=self)
    monkeypatch.setattr("similarity.epo_ops._token", lambda settings: "super-secret-token")
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse())
    result = search_epo(["WoundWise-AI", "wound imaging device"], Settings(epo_ops_consumer_key="consumer-key", epo_ops_consumer_secret="consumer-secret"))
    rendered = str(result)
    assert result["status"] == "error"
    assert "Query URL suppressed" in result["why_relevant"]
    assert "https://ops.epo.org" not in rendered
    assert "consumer-key" not in rendered
    assert "consumer-secret" not in rendered
    assert "super-secret-token" not in rendered



def test_epo_token_posts_official_auth_request(monkeypatch):
    captured = {}
    class FakeResponse:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {"access_token": "token-value"}
    def fake_post(url, data, headers, timeout):
        captured.update({"url": url, "data": data, "headers": headers, "timeout": timeout})
        return FakeResponse()
    monkeypatch.setattr("requests.post", fake_post)
    token = _token(Settings(epo_ops_consumer_key="key", epo_ops_consumer_secret="secret"))
    assert token == "token-value"
    assert captured["url"] == "https://ops.epo.org/3.2/auth/accesstoken"
    assert captured["data"] == {"grant_type": "client_credentials"}
    assert captured["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert captured["headers"]["Accept"] == "application/json"
    assert captured["headers"]["Authorization"].startswith("Basic ")


def test_search_epo_uses_service_base_xml_headers_and_no_3_2_resource_path(monkeypatch):
    calls = []
    xml = """<?xml version='1.0'?><ops:world-patent-data xmlns:ops='http://ops.epo.org'><exchange-document><bibliographic-data><publication-reference><document-id><doc-number>1234567</doc-number></document-id></publication-reference><invention-title>Wound imaging device</invention-title></bibliographic-data></exchange-document></ops:world-patent-data>"""
    class FakeResponse:
        status_code = 200
        text = xml
        def raise_for_status(self):
            return None
    def fake_get(url, params, headers, timeout):
        calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse()
    monkeypatch.setattr("similarity.epo_ops._token", lambda settings: "token-value")
    monkeypatch.setattr("requests.get", fake_get)
    result = search_epo(["WoundWise-AI", "wound imaging device"], Settings(epo_ops_consumer_key="key", epo_ops_consumer_secret="secret"))
    assert result["status"] == "success"
    assert calls[0]["url"] == "https://ops.epo.org/rest-services/published-data/search/biblio"
    assert "/3.2/rest-services" not in calls[0]["url"]
    assert calls[0]["headers"]["Accept"] == "application/exchange+xml"
    assert calls[0]["headers"]["X-OPS-Range"] == "1-5"
    assert calls[0]["headers"]["Authorization"] == "Bearer token-value"
    assert calls[0]["params"]["q"].startswith('ta="WoundWise-AI"')


def test_search_epo_401_403_safe_error(monkeypatch):
    class FakeResponse:
        status_code = 403
        text = "forbidden token secret"
        def raise_for_status(self):
            raise AssertionError("should return before raise_for_status")
    monkeypatch.setattr("similarity.epo_ops._token", lambda settings: "token-value")
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse())
    result = search_epo(["WoundWise-AI", "wound imaging device"], Settings(epo_ops_consumer_key="key", epo_ops_consumer_secret="secret"))
    rendered = str(result)
    assert result["status"] == "error"
    assert "HTTP 403" in result["why_relevant"]
    assert "token-value" not in rendered
    assert "key" not in rendered
    assert "secret" not in rendered
    assert "https://" not in rendered


def test_settings_prefers_epo_service_base_and_strips_legacy_3_2(monkeypatch):
    monkeypatch.setenv("EPO_OPS_BASE_URL", "https://ops.epo.org/3.2")
    monkeypatch.delenv("EPO_OPS_SERVICE_BASE_URL", raising=False)
    settings = Settings.from_env()
    assert settings.epo_ops_service_base_url == "https://ops.epo.org"
    monkeypatch.setenv("EPO_OPS_SERVICE_BASE_URL", "https://example.test")
    settings = Settings.from_env()
    assert settings.epo_ops_service_base_url == "https://example.test"
