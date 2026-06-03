from settings import Settings


def test_settings_from_env_uses_default_epo_urls_without_name_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EPO_OPS_BASE_URL", raising=False)
    monkeypatch.delenv("EPO_OPS_SERVICE_BASE_URL", raising=False)

    settings = Settings.from_env()

    assert settings.epo_ops_base_url == "https://ops.epo.org"
    assert settings.epo_ops_service_base_url == "https://ops.epo.org"


def test_settings_from_env_supports_epo_service_base_url(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EPO_OPS_BASE_URL", raising=False)
    monkeypatch.setenv("EPO_OPS_SERVICE_BASE_URL", "https://example.test/service")

    settings = Settings.from_env()

    assert settings.epo_ops_service_base_url == "https://example.test/service"
    assert settings.epo_ops_base_url == "https://example.test/service"


def test_settings_from_env_supports_legacy_epo_base_url_alias(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EPO_OPS_BASE_URL", "https://legacy.example.test")
    monkeypatch.setenv("EPO_OPS_SERVICE_BASE_URL", "https://service.example.test")

    settings = Settings.from_env()

    assert settings.epo_ops_service_base_url == "https://service.example.test"
    assert settings.epo_ops_base_url == "https://legacy.example.test"
