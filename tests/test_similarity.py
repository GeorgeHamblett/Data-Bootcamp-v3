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

    assert scored["risk"] in {"LOW", "MEDIUM"}
    assert scored["risk"] not in {"HIGH", "VERY_HIGH"}
    assert scored["similarity_type"] in {"adjacent_infrastructure", "same_domain_broad"}
    assert not any("wound" in concept.lower() for concept in scored["specific_matched_concepts"])
    assert "not a direct wound-imaging" in scored["why_relevant"]


def test_generic_samd_overlap_alone_cannot_score_high():
    scored = score_result(
        ["software as a medical device", "AI platform", "digital health"],
        "Software as a medical device application on an AI platform",
        "A digital health platform supports clinical AI applications.",
    )

    assert scored["risk"] == "LOW"
    assert scored["similarity_type"] == "generic_overlap"
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
    assert direct["risk"] == "VERY_HIGH"


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
    assert epo["risk"] in {"LOW", "MEDIUM"}
    assert epo["similarity_type"] == "adjacent_infrastructure"
    assert epo["specific_matched_concepts"] == []
    assert "not a direct wound-imaging" in epo["why_relevant"]


def test_query_terms_are_not_copied_into_matches_for_unrelated_patent():
    scored = score_result(
        ["wearable digital therapeutic", "movement quality assessment"],
        "Use of SHP2 inhibitors for inhibiting senescence",
        "Ageing-associated diseases may be treated with inhibitors that reduce senescence and metabolic defects.",
    )
    assert scored["specific_matched_concepts"] == []
    assert scored["generic_matched_concepts"] == []
    assert scored["risk"] == "NONE"
    assert scored["score"] == 0


def test_service_separates_raw_epo_records_from_relevant_matches_for_unrelated_senescence(monkeypatch):
    f = ApplicationFacts(
        project_title="StepRight movement quality assessment for falls rehabilitation",
        product_or_intervention="StepRight wearable digital therapeutic with movement quality assessment engine",
        acronym_or_short_name="MQAE",
        clinical_or_social_care_need="falls prevention and mobility rehabilitation",
        target_population="older adults aged 60+ with recent falls risk",
        technology_type="wearable sensor digital therapeutic platform",
        sites_or_setting="community rehabilitation",
    )
    settings = Settings(local_only_mode=False, allow_external_similarity_queries=True)
    unrelated = {
        "source": "EPO OPS",
        "status": "success",
        "matches_found": 1,
        "top_match": "Use of SHP2 inhibitors for inhibiting senescence",
        "raw": "Ageing-associated diseases, SHP2 inhibitors, inhibiting senescence, metabolic defects and muscle weakness.",
        "link_or_id": "WO2023180245",
    }
    monkeypatch.setattr("similarity.service.search_lens", lambda query, settings: {"source": "Lens Scholarly", "status": "success", "matches_found": 0, "top_match": "", "raw": "", "link_or_id": ""})
    monkeypatch.setattr("similarity.service.search_epo", lambda query, settings: unrelated.copy())
    monkeypatch.setattr("similarity.service.search_nihr_open_data", lambda query, settings: {"source": "NIHR Open Data", "status": "success", "matches_found": 0, "top_match": "", "raw": "", "link_or_id": ""})

    result = run_similarity_service(f, settings, run_similarity_check=True)
    epo = next(row for row in result["results"] if row["source"] == "EPO OPS")

    assert epo["raw_records_returned"] == 1
    assert epo["matches_found"] == 0
    assert epo["risk"] == "NONE"
    assert epo["score"] == 0
    assert epo["similarity_type"] == "no_meaningful_overlap"
    assert epo["specific_matched_concepts"] == []
    assert epo["top_match"] == "No relevant EPO match found"


def test_nihr_raw_records_with_zero_relevance_are_not_adviser_matches(monkeypatch):
    f = ApplicationFacts(
        product_or_intervention="Wearable movement assessment therapeutic",
        technology_type="wearable sensor assessment software",
        clinical_or_social_care_need="falls prevention rehabilitation",
    )
    settings = Settings(local_only_mode=False, allow_external_similarity_queries=True)
    nihr_record = {
        "source": "NIHR Open Data",
        "status": "success",
        "matches_found": 5,
        "top_match": "Gene Targeted Transgenic Mice Expressing Human PRP as Models for Studying CJD",
        "raw": {"title": "Gene Targeted Transgenic Mice Expressing Human PRP as Models for Studying CJD"},
        "link_or_id": "record-1",
    }
    monkeypatch.setattr("similarity.service.search_lens", lambda query, settings: {"source": "Lens Scholarly", "status": "success", "matches_found": 0, "top_match": "", "raw": "", "link_or_id": ""})
    monkeypatch.setattr("similarity.service.search_epo", lambda query, settings: {"source": "EPO OPS", "status": "success", "matches_found": 0, "top_match": "", "raw": "", "link_or_id": ""})
    monkeypatch.setattr("similarity.service.search_nihr_open_data", lambda query, settings: nihr_record.copy())

    result = run_similarity_service(f, settings, run_similarity_check=True)
    nihr = next(row for row in result["results"] if row["source"] == "NIHR Open Data")

    assert nihr["raw_records_returned"] == 5
    assert nihr["matches_found"] == 0
    assert nihr["risk"] == "NONE"
    assert nihr["score"] == 0
    assert nihr["similarity_type"] == "no_meaningful_overlap"
    assert nihr["top_match"] == "No relevant NIHR Open Data match found"


def test_true_direct_match_requires_actual_metadata_overlap():
    scored = score_result(
        ["CardioPatch", "wearable ECG sensor", "atrial fibrillation detection", "ECG monitoring"],
        "CardioPatch wearable ECG sensor for atrial fibrillation detection",
        "A wearable ECG sensor performs ECG monitoring and atrial fibrillation detection for ambulatory patients.",
        "CardioPatch",
    )
    assert scored["risk"] in {"HIGH", "VERY_HIGH"}
    assert scored["specific_matched_concepts"]
    assert {"technical_method", "clinical_problem", "product_function"} & set(scored["matched_dimensions"])


def test_epo_query_builder_rejects_demographic_and_truncated_terms():
    cql = build_epo_cql_query(["the", "early", "aged 60", "over with recent falls risk", "older adults", "patients", "community", "NHS", "rehabilitation", "detection", "surgical w", "wearable digital therapeutic", "movement quality assessment"])
    assert "aged" not in cql.lower()
    assert "older adults" not in cql.lower()
    assert "surgical w" not in cql.lower()
    assert "wearable digital therapeutic" in cql
    assert "movement quality assessment" in cql


def test_epo_xml_metadata_parser_extracts_structured_fields():
    from similarity.epo_ops import parse_epo_metadata

    xml = """
    <ops:world-patent-data xmlns:ops="http://ops.epo.org">
      <exchange-document>
        <bibliographic-data>
          <publication-reference><document-id><country>US</country><doc-number>20260064432</doc-number><kind>A1</kind></document-id></publication-reference>
          <invention-title>System and method for isolated execution of software-as-a-medical-device applications on edge-artificial intelligence platforms</invention-title>
          <parties><applicants><applicant><applicant-name><name>NVIDIA Corporation</name></applicant-name></applicant></applicants></parties>
        </bibliographic-data>
        <abstract><p>Isolated execution environments allocate computing resources based on criticality.</p></abstract>
      </exchange-document>
    </ops:world-patent-data>
    """
    parsed = parse_epo_metadata(xml)
    assert parsed["title"].startswith("System and method")
    assert "Isolated execution environments" in parsed["abstract"]
    assert "20260064432" in parsed["doc_numbers"]
    assert "NVIDIA Corporation" in parsed["applicants"]
    assert parsed["country"] == "US"
    assert parsed["kind"] == "A1"


def test_similarity_service_imports_when_score_profiles_attribute_is_missing(monkeypatch):
    """Runtime compatibility: app import should not fail if a stale scoring module lacks score_profiles."""
    import similarity.scoring as scoring_module

    if hasattr(scoring_module, "score_profiles"):
        monkeypatch.delattr(scoring_module, "score_profiles")
    f = facts()
    settings = Settings(local_only_mode=False, allow_external_similarity_queries=True)
    monkeypatch.setattr("similarity.service.search_lens", lambda query, settings: {"source": "Lens Scholarly", "status": "success", "matches_found": 0, "top_match": "", "raw": "", "link_or_id": ""})
    monkeypatch.setattr("similarity.service.search_epo", lambda query, settings: {"source": "EPO OPS", "status": "success", "matches_found": 0, "top_match": "", "raw": "", "link_or_id": ""})
    monkeypatch.setattr("similarity.service.search_nihr_open_data", lambda query, settings: {"source": "NIHR Open Data", "status": "success", "matches_found": 0, "top_match": "", "raw": "", "link_or_id": ""})

    result = run_similarity_service(f, settings, run_similarity_check=True)

    assert all(row["risk"] == "NONE" for row in result["results"])


def test_similarity_service_reload_does_not_import_score_profiles_symbol(monkeypatch):
    import importlib
    import similarity.scoring as scoring_module
    import similarity.service as service_module

    if hasattr(scoring_module, "score_profiles"):
        monkeypatch.delattr(scoring_module, "score_profiles")

    reloaded = importlib.reload(service_module)

    assert hasattr(reloaded, "run_similarity_service")
