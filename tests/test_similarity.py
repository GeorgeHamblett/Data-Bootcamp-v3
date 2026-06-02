from application_facts import extract_application_facts
from settings import Settings
from similarity.query_builder import build_similarity_query, filter_terms, has_minimum_meaningful_terms
from similarity.service import run_similarity


def test_generic_filename_document_terms_excluded():
    kept, excluded = filter_terms(["uploaded", "document", "diabetes sensor", "gantt", "older adults"])
    assert "diabetes sensor" in kept and "older adults" in kept
    assert "uploaded" in excluded and "document" in excluded and "gantt" in excluded


def test_at_least_two_meaningful_terms_required():
    facts = extract_application_facts([{"name": "app.txt", "text": "Intervention: Sensor"}])
    query = build_similarity_query(facts)
    assert not has_minimum_meaningful_terms(query)


def test_mock_default_false_and_disabled_calls_nothing():
    settings = Settings()
    assert settings.mock_similarity_mode is False
    facts = extract_application_facts([{"name": "app.txt", "text": "Intervention: Diabetes sensor\nPopulation: older adults"}])
    _, results = run_similarity(facts, "", settings, run_similarity_check=False, mock_mode=False)
    assert all(r.status == "not_run" for r in results)
    assert all("disabled" in r.why_relevant.lower() for r in results)


def test_local_only_blocks_live_apis_and_no_simulation_without_mock():
    settings = Settings(local_only_mode=True, allow_external_similarity_queries=True)
    facts = extract_application_facts([{"name": "app.txt", "text": "Intervention: Diabetes sensor\nPopulation: older adults"}])
    _, results = run_similarity(facts, "", settings, run_similarity_check=True, mock_mode=False)
    assert all(r.status == "not_run" for r in results)
    assert all(r.link_or_id != "mock" for r in results)


def test_mock_only_when_explicit_enabled():
    settings = Settings(local_only_mode=True)
    facts = extract_application_facts([{"name": "app.txt", "text": "Intervention: Diabetes sensor\nPopulation: older adults"}])
    _, results = run_similarity(facts, "", settings, run_similarity_check=True, mock_mode=True)
    assert all(r.link_or_id == "mock" for r in results)
