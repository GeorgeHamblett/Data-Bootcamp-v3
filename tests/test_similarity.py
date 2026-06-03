from schemas import ApplicationFacts
from settings import Settings
from similarity.query_builder import build_similarity_query, is_generic_term
from similarity.service import run_similarity_service
from similarity.epo_ops import build_epo_cql_query, search_epo


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
    assert len(terms) <= 10
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
    for expected in ["woundwise-ai", "multispectral wound imaging", "wound imaging device", "wound deterioration detection"]:
        assert expected in joined
    assert any(term in joined for term in ["lower-limb wounds", "pressure wounds", "surgical wounds", "community wound services"])


def test_stopword_only_similarity_match_scores_none():
    scored = score_result(["The"], "The CJD mice project", "The study evaluates a mouse model.")
    assert scored["risk"] == "NONE"
    assert scored["score"] == 0.0


def test_nvidia_samd_edge_ai_patent_is_adjacent_not_direct_wound_match():
    terms = [
        "WoundWise-AI",
        "multispectral wound imaging",
        "wound imaging device",
        "software as a medical device",
        "wound deterioration detection",
        "community wound services",
    ]
    title = "System and method for isolated execution of software-as-a-medical-device applications on edge-artificial intelligence platforms"
    abstract = (
        "Systems and methods provide isolated execution of software-as-a-medical-device applications "
        "on edge-artificial intelligence platforms. Applications are assigned execution environments, "
        "isolation levels and computing resources based on criticality and resource requirements."
    )

    scored = score_result(terms, title, abstract, "WoundWise-AI")

    assert scored["risk"] == "NONE"
    assert scored["risk"] not in {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}
    assert scored["similarity_type"] == "infrastructure_only_no_specific_overlap"
    assert not any("wound" in concept.lower() for concept in scored["specific_matched_concepts"])
    assert "generic infrastructure/platform" in scored["why_relevant"]


def test_generic_samd_overlap_alone_cannot_score_high():
    scored = score_result(
        ["software as a medical device", "AI platform", "digital health"],
        "Software as a medical device application on an AI platform",
        "A digital health platform supports clinical AI applications.",
    )

    assert scored["risk"] == "LOW"
    assert scored["similarity_type"] == "generic_or_regulatory_overlap"
    assert scored["specific_matched_concepts"] == []


def test_wound_specific_overlap_scores_high_with_problem_method_and_function():
    scored = score_result(
        [
            "multispectral wound imaging",
            "wound deterioration detection",
            "community wound services",
            "wound imaging device",
        ],
        "Multispectral wound imaging device for wound deterioration detection",
        "The device supports wound assessment and wound measurement in community wound services.",
    )

    assert scored["risk"] in {"HIGH", "VERY_HIGH"}
    assert scored["similarity_type"] == "direct_match"
    assert {"clinical_problem", "technical_method", "product_function"} <= set(scored["matched_dimensions"])


def test_very_high_requires_problem_method_and_product_function_overlap():
    broad = score_result(
        ["multispectral wound imaging", "community wound services", "lower-limb wounds"],
        "Multispectral wound imaging in community wound services",
        "A broad wound assessment study for lower-limb wounds without deterioration detection or wound measurement product functions.",
    )
    direct = score_result(
        ["wound deterioration", "multispectral wound imaging", "wound deterioration detection"],
        "Wound deterioration detection using multispectral wound imaging",
        "A clinical wound decision support product predicts wound deterioration and generates wound risk scores.",
    )

    assert broad["risk"] != "VERY_HIGH"
    assert direct["risk"] == "HIGH"


def test_similarity_service_keeps_epo_live_but_scores_samd_infrastructure_as_adjacent(monkeypatch):
    f = extract_application_facts([LoadedDocument("app.txt", WOUNDWISE_APP)])
    settings = Settings(local_only_mode=False, allow_external_similarity_queries=True)
    nvidia_result = {
        "source": "EPO OPS",
        "status": "success",
        "matches_found": 1,
        "top_match": "System and method for isolated execution of software-as-a-medical-device applications on edge-artificial intelligence platforms",
        "raw": (
            "US 2026/0064432 A1 NVIDIA Corporation. Isolated execution of "
            "software-as-a-medical-device applications on edge-artificial intelligence platforms, "
            "including execution environments, isolation levels and computing resource allocation."
        ),
        "link_or_id": "US20260064432A1",
    }

    monkeypatch.setattr("similarity.service.search_lens", lambda query, settings: {"source": "Lens Scholarly", "status": "success", "matches_found": 0, "top_match": "", "raw": "", "link_or_id": ""})
    monkeypatch.setattr("similarity.service.search_epo", lambda query, settings: nvidia_result.copy())
    monkeypatch.setattr("similarity.service.search_nihr_open_data", lambda query, settings: {"source": "NIHR Open Data", "status": "success", "matches_found": 0, "top_match": "", "raw": "", "link_or_id": ""})

    result = run_similarity_service(f, settings, run_similarity_check=True)
    epo = next(row for row in result["results"] if row["source"] == "EPO OPS")

    assert epo["status"] == "success"
    assert epo["risk"] == "NONE"
    assert epo["similarity_type"] == "infrastructure_only_no_specific_overlap"
    assert epo["specific_matched_concepts"] == []
    assert "generic infrastructure/platform" in epo["why_relevant"]


def test_identifier_extraction_and_validation_preserves_public_anchors():
    from similarity.query_builder import _identifier_phrases, _valid_query_concept

    text = "Woubot uses AI_AWARD01723, AI-AWARD01724, NIHR204173 and US20210201479A1."
    identifiers = _identifier_phrases(text)

    assert "AI_AWARD01723" in identifiers
    assert "AI_AWARD01724" in identifiers
    assert "NIHR204173" in identifiers
    assert "US20210201479A1" in identifiers
    assert _valid_query_concept("US20210201479A1")
    assert _valid_query_concept("AI-AWARD01723")
    assert _valid_query_concept("NIHR204173")


def test_woubot_identifier_query_prioritises_exact_anchors_and_excludes_noise():
    f = ApplicationFacts(
        project_title="Woubot AI_AWARD01723 NIHR204173 US20210201479A1",
        product_or_intervention="Woubot personalised wound care",
        acronym_or_short_name="Woubot",
        technology_type="wound image segmentation and wound healing prediction",
        clinical_or_social_care_need="personalised wound care",
        endpoints=["endpoint", "12-month decision model", "related incidents"],
    )

    q = build_similarity_query(f)
    terms = q.primary_terms + q.secondary_terms
    joined = " ".join(terms).lower()

    assert terms[:4] == ["US20210201479A1", "AI_AWARD01723", "NIHR204173", "Woubot"]
    assert "wound healing prediction" in joined
    assert "wound image segmentation" in joined
    assert "personalised wound care" in joined
    assert "endpoint" not in joined
    assert "12-month decision model" not in joined
    assert "related incidents" not in joined


def test_nihr_open_data_list_query_stops_at_first_matching_term(monkeypatch):
    from similarity.nihr_open_data import search_nihr_open_data

    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, params, headers, timeout):
        calls.append(params["search"])
        if params["search"] == "AI_AWARD01723":
            return Response({"results": [{"project_title": "Woubot award", "project_id": "NIHR204173", "acronym": "AI_AWARD01723"}]})
        return Response({"results": []})

    monkeypatch.setattr("requests.get", fake_get)

    result = search_nihr_open_data(["Woubot", "AI_AWARD01723", "NIHR204173"], Settings())

    assert calls == ["Woubot", "AI_AWARD01723"]
    assert result["matches_found"] == 1
    assert result["searched_term"] == "AI_AWARD01723"
    assert result["top_match"] == "Woubot award"
    assert result["link_or_id"] == "NIHR204173"


def test_epo_cql_uses_publication_number_for_patent_identifiers():
    cql = build_epo_cql_query(["US20210201479A1", "wound image segmentation"])

    assert "pn=US20210201479" in cql
    assert 'ta="US20210201479A1"' not in cql
    assert 'ta="wound image segmentation"' in cql


def test_exact_identifier_overlap_scores_very_high():
    scored = score_result(
        ["Woubot", "AI_AWARD01723", "US20210201479A1"],
        "Woubot award metadata",
        "This NIHR record contains AI-AWARD01723 and project NIHR204173.",
    )

    assert scored["risk"] == "VERY_HIGH"
    assert scored["score"] == 0.95
    assert scored["similarity_type"] == "exact_identifier_match"
    assert scored["matched_concepts"] == ["AI_AWARD01723"]


def test_new_generic_evaluation_terms_are_excluded():
    assert is_generic_term("endpoint")
    assert is_generic_term("primary endpoint")
    assert is_generic_term("12-month decision model")
    assert is_generic_term("related incidents")

    q = build_similarity_query(ApplicationFacts(product_or_intervention="Woubot", endpoints=["endpoint", "12-month decision model"]))
    joined = " ".join(q.primary_terms + q.secondary_terms).lower()
    assert "endpoint" not in joined
    assert "12-month decision model" not in joined


def test_domain_agnostic_stepright_extraction_expected_terms():
    text = "StepRight MQAE Motion Quality Assessment Engine wearable digital therapeutic fall prevention mobility rehabilitation movement quality assessment wearable sensors Hidden Markov Models deep convolutional neural network classifier"
    q = build_similarity_query(ApplicationFacts(project_title=text, product_or_intervention=text, technology_type=text, clinical_or_social_care_need=text))
    joined = " ".join(q.primary_terms + q.secondary_terms).lower()
    for expected in [
        "stepright", "mqae", "motion quality assessment engine", "wearable digital therapeutic",
        "movement quality assessment", "hidden markov models",
        "deep convolutional neural network classifier", "fall prevention", "mobility rehabilitation",
    ]:
        assert expected in joined


def test_domain_agnostic_noise_exclusion():
    text = "Knowledge Knowledge mobilisation their risk of falling health economics budget aims methodology"
    q = build_similarity_query(ApplicationFacts(project_title=text, product_or_intervention=text, clinical_or_social_care_need=text))
    assert q.primary_terms + q.secondary_terms == []


def test_epo_domain_agnostic_routing_and_weak_skip():
    from similarity.service import _api_terms, _epo_has_run_basis
    strong = build_similarity_query(ApplicationFacts(product_or_intervention="StepRight MQAE", technology_type="wearable digital therapeutic movement quality assessment wearable sensors", clinical_or_social_care_need="fall prevention mobility rehabilitation"))
    epo_terms = _api_terms("EPO OPS", strong.primary_terms, strong.secondary_terms)
    assert _epo_has_run_basis(epo_terms)
    assert "wound" not in " ".join(epo_terms).lower()

    weak = build_similarity_query(ApplicationFacts(target_population="older adults", clinical_or_social_care_need="fall risk", sites_or_setting="NHS community rehabilitation", health_economics_plan="health economics"))
    weak_terms = _api_terms("EPO OPS", weak.primary_terms, weak.secondary_terms)
    assert not _epo_has_run_basis(weak_terms)


def test_non_ai_service_intervention_query_terms():
    text = "HomeFirst discharge coordination pathway personalised care planning social worker-led transitional support delayed discharge older adults budget project management knowledge mobilisation"
    q = build_similarity_query(ApplicationFacts(project_title=text, product_or_intervention=text, clinical_or_social_care_need=text, target_population="older adults"))
    joined = " ".join(q.primary_terms + q.secondary_terms).lower()
    for expected in ["homefirst", "discharge coordination pathway", "personalised care planning", "social worker-led transitional support"]:
        assert expected in joined
    for excluded in ["older adults", "budget", "project management", "knowledge mobilisation"]:
        assert excluded not in joined


def test_diagnostic_assay_query_terms():
    text = "RapidSepsis multiplex biomarker panel point-of-care test sepsis triage emergency department lactate procalcitonin CRP"
    q = build_similarity_query(ApplicationFacts(project_title=text, product_or_intervention=text, technology_type=text, clinical_or_social_care_need=text))
    joined = " ".join(q.primary_terms + q.secondary_terms).lower()
    for expected in ["rapidsepsis", "multiplex biomarker panel", "point-of-care test", "sepsis triage"]:
        assert expected in joined


def test_generic_document_scoring_none_and_exact_identifiers_very_high():
    generic = score_result(["knowledge mobilisation", "health economics", "budget"], "knowledge mobilisation plan and budget", "")
    assert generic["risk"] == "NONE"

    nihr = score_result(["AI_AWARD01723"], "Award", "AI-AWARD01723")
    patent = score_result(["US20210201479A1"], "Patent", "US20210201479A1")
    assert nihr["risk"] == "VERY_HIGH"
    assert patent["risk"] == "VERY_HIGH"
