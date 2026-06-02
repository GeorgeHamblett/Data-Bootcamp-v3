import importlib


def test_app_imports_and_exposes_title():
    app = importlib.import_module("app")
    assert app.APP_TITLE == "RSS/NIHR Funding Application Checklist Assistant"
