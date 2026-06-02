"""Load built-in NIHR/RSS guidance files from the repository."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from guidance_parser import ensure_area_coverage, parse_guidance_text
from schemas import GuidanceDocument, Requirement

SEARCH_DIRS = [".", "guidance_examples", "docs", "data"]


def classify_guidance_file(path: str | Path) -> str:
    name = Path(path).name.lower()
    if "nihr" in name and "domestic" in name:
        return "nihr_domestic"
    if "rss" in name or "pda" in name or "playbook" in name:
        return "rss_playbook"
    return "programme_guidance"


def discover_guidance_paths(repo_root: str | Path = ".") -> list[Path]:
    root = Path(repo_root)
    paths: list[Path] = []
    for rel in SEARCH_DIRS:
        directory = root / rel
        if not directory.exists() or not directory.is_dir():
            continue
        for path in directory.glob("*.txt"):
            if path.name.startswith("."):
                continue
            paths.append(path)
    return sorted(set(paths))


def load_guidance_documents(repo_root: str | Path = ".") -> list[GuidanceDocument]:
    docs: list[GuidanceDocument] = []
    for path in discover_guidance_paths(repo_root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        source = classify_guidance_file(path)
        docs.append(
            GuidanceDocument(
                path=str(path),
                name=path.name,
                source=source,  # type: ignore[arg-type]
                text=text,
                is_application_example=False,
            )
        )
    return docs


def build_baseline_requirement_bank(repo_root: str | Path = ".") -> list[Requirement]:
    requirements: list[Requirement] = []
    for doc in load_guidance_documents(repo_root):
        prefix = "NIHR" if doc.source == "nihr_domestic" else "RSS" if doc.source == "rss_playbook" else "PGM"
        requirements.extend(parse_guidance_text(doc.text, doc.source, prefix=prefix))
    return ensure_area_coverage(requirements)


def add_runtime_guidance(texts: Iterable[tuple[str, str]], start: int = 1) -> list[Requirement]:
    requirements: list[Requirement] = []
    for source, text in texts:
        if text.strip():
            requirements.extend(parse_guidance_text(text, source, prefix=f"RT{start}"))
            start += 1
    return requirements
