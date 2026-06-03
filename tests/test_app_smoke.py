import app


def test_app_title_and_main_exist():
    assert app.APP_TITLE == "RSS/NIHR Funding Application Checklist Assistant"
    assert callable(app.main)


def test_app_runtime_document_inputs_are_limited_to_application_and_specific_call():
    source = open("app.py", encoding="utf-8").read()
    assert "The Application" in source
    assert "Optional Specific Funding Call Guidance" in source
    assert "Optional general" not in source
    assert "Paste extra general guidance" not in source
    assert "Upload extra general guidance" not in source
    assert "Upload RSS" not in source
    assert "Upload NIHR" not in source
    assert app.NO_SPECIFIC_CALL_GUIDANCE_MESSAGE == "No specific funding call guidance provided; review uses built-in NIHR domestic guidance and RSS PDA playbook guidance."


def test_app_imports_with_epo_credential_button():
    import app
    assert app.APP_TITLE
