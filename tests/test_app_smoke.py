import app


def test_app_title_and_main_exist():
    assert app.APP_TITLE == "RSS/NIHR Funding Application Checklist Assistant"
    assert callable(app.main)
