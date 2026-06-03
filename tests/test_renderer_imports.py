import ast
import importlib
import inspect
import subprocess
import sys
from pathlib import Path

import report_renderer
from checklist_engine import build_checklist
from guidance_parser import derived_reviewer_requirements
from rag_dashboard import build_rag_dashboard
from schemas import ApplicationFacts

EXPECTED = {
    "render_main_case_summary",
    "render_checklist_report_summary",
    "render_rag_dashboard_summary",
    "render_similarity_check_summary",
    "render_priority_missing_evidence",
    "render_executive_review_note",
    "render_table_display_dataframe",
    "render_raw_json_note",
}


def _app_report_renderer_imports() -> set[str]:
    tree = ast.parse(Path("app.py").read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "report_renderer":
            imported.update(alias.name for alias in node.names)
    return imported


def test_app_report_renderer_imports_exist_on_module():
    imported = _app_report_renderer_imports()
    assert EXPECTED <= imported
    missing = [name for name in imported if not hasattr(report_renderer, name)]
    assert missing == []


def test_expected_renderer_functions_are_exported_and_callable():
    assert EXPECTED <= set(report_renderer.EXPECTED_RENDERER_FUNCTIONS)
    assert EXPECTED <= set(report_renderer.__all__)
    for name in EXPECTED:
        assert callable(getattr(report_renderer, name))


def test_main_case_summary_and_raw_json_note_are_safe_markdown():
    summary = report_renderer.render_main_case_summary(ApplicationFacts(project_title="Import smoke"), [], "")
    assert "Summary of key information extracted" in summary
    assert not summary.strip().startswith("{")
    note = report_renderer.render_raw_json_note()
    assert "Developer/debug output" in note
    assert len(note.split()) < 20


def test_streamlit_app_imports_without_importerror():
    app = importlib.import_module("app")
    assert hasattr(app, "main")


def test_subprocess_app_import_smoke():
    completed = subprocess.run([sys.executable, "-c", "import app; print('app import ok')"], check=True, capture_output=True, text=True)
    assert "app import ok" in completed.stdout


def test_public_renderer_functions_run_without_missing_private_helpers():
    facts = ApplicationFacts(project_title="Import smoke", finance_or_budget_evidence="Staff costs and cost justification are included")
    checklist = build_checklist(facts, derived_reviewer_requirements())
    dashboard = build_rag_dashboard(checklist, facts)

    assert "Checklist row counts" in report_renderer.render_checklist_report_summary(checklist, facts)
    assert "Overall risk profile" in report_renderer.render_rag_dashboard_summary(dashboard)
    assert "Application focus" in report_renderer.render_executive_review_note(facts, dashboard, "")


def test_clean_markdown_output_strips_code_blocks_and_indentation():
    raw = """
        ```markdown
            ## Query basis

            **Checklist row counts:**
        ```
    """

    cleaned = report_renderer.clean_markdown_output(raw)

    assert cleaned == "## Query basis\n\n**Checklist row counts:**"
    assert "```" not in cleaned
    assert not any(line.startswith(("  ", "    ", "\t")) for line in cleaned.splitlines() if line)


def test_report_renderers_return_unindented_markdown():
    facts = ApplicationFacts(project_title="Import smoke", product_or_intervention="Monitor")
    checklist = build_checklist(facts, derived_reviewer_requirements())
    dashboard = build_rag_dashboard(checklist, facts)
    similarity = {
        "query": {"primary_terms": ["Remote monitor"], "secondary_terms": []},
        "results": [],
    }

    rendered_sections = [
        report_renderer.render_main_case_summary(facts, dashboard, ""),
        report_renderer.render_checklist_report_summary(checklist, facts),
        report_renderer.render_rag_dashboard_summary(dashboard),
        report_renderer.render_similarity_check_summary(similarity),
        report_renderer.render_priority_missing_evidence(checklist, dashboard, facts),
        report_renderer.render_executive_review_note(facts, dashboard, ""),
    ]

    for section in rendered_sections:
        assert "```" not in section
        assert not any(line.startswith(("    ", "\t")) for line in section.splitlines() if line)
        assert "## " in section
