"""Load built-in guidance files as reference requirements, never examples."""
from __future__ import annotations

from pathlib import Path

from guidance_parser import derived_reviewer_requirements, parse_guidance_requirements
from schemas import GuidanceDocument, Requirement, SOURCE_LABELS

SEARCH_DIRS = [".", "guidance_examples", "docs", "data"]


def classify_guidance_file(path: str | Path) -> str:
    name = Path(path).name.lower()
    if "nihr" in name and "domestic" in name:
        return "nihr_domestic"
    if "rss" in name or "pda" in name or "playbook" in name:
        return "rss_playbook"
    return "programme_guidance"


def discover_guidance_paths(repo_root: str | Path | None = None) -> list[Path]:
    root = Path(repo_root or Path(__file__).resolve().parent)
    paths: list[Path] = []
    for rel in SEARCH_DIRS:
        directory = root / rel
        if not directory.exists() or not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.txt")):
            if path.name.startswith("."):
                continue
            source = classify_guidance_file(path)
            if source in {"nihr_domestic", "rss_playbook", "programme_guidance"}:
                paths.append(path)
    # Keep root-level built-ins first and avoid duplicates.
    return sorted(set(paths), key=lambda p: (0 if p.parent == root else 1, p.name.lower()))


def load_builtin_guidance(repo_root: str | Path | None = None) -> list[GuidanceDocument]:
    docs: list[GuidanceDocument] = []
    for path in discover_guidance_paths(repo_root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        source = classify_guidance_file(path)
        docs.append(
            GuidanceDocument(
                path=str(path),
                name=path.name,
                source_type=source,
                source_label=SOURCE_LABELS.get(source, source),
                text=text,
                is_application_example=False,
            )
        )
    return docs


def build_baseline_requirement_bank(repo_root: str | Path | None = None) -> list[Requirement]:
    requirements: list[Requirement] = []
    for doc in load_builtin_guidance(repo_root):
        requirements.extend(parse_guidance_requirements(doc.text, doc.source_type, prefix=Path(doc.name).stem))
    requirements.extend(derived_reviewer_requirements())
    return requirements
