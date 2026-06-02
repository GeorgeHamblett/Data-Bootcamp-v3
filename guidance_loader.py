"""Load built-in NIHR/RSS guidance files from the repository."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from guidance_parser import ensure_area_coverage, parse_guidance_text
from schemas import GuidanceDocument, Requirement

SEARCH_DIRS = [".", "guidance_examples", "docs", "data"]
BUILTIN_GUIDANCE_FILENAMES = {
    "nihr_domestic_guidance.txt": "nihr_domestic",
    "rss_pda_playbook_notes.txt": "rss_playbook",
}



def classify_guidance_file(path: str | Path) -> str:
    name = Path(path).name.lower()
    if "nihr" in name and "domestic" in name:
        return "nihr_domestic"
    if "rss" in name or "pda" in name or "playbook" in name:
        return "rss_playbook"
    return "programme_guidance"


def discover_guidance_paths(repo_root: str | Path = ".") -> list[Path]:
    """Find the built-in guidance files by filename without treating them as examples."""
    root = Path(repo_root)
    paths: list[Path] = []
    # Prefer explicit filename search so advisers never need to upload these files.
    for filename in BUILTIN_GUIDANCE_FILENAMES:
        direct = root / filename
        if direct.exists():
            paths.append(direct)
            continue
        for path in root.rglob(filename):
            if ".git" not in path.parts and path.is_file():
                paths.append(path)
                break
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


def build_baseline_requirement_bank(repo_root: str | Path = ".", include_pda_playbook: bool = True) -> list[Requirement]:
    """Build the baseline bank from built-in files.

    NIHR domestic guidance is always included. RSS PDA playbook checks can be
    switched on only when the application/call indicates i4i PDA/product-development
    relevance, preventing PDA-specific checks from being forced onto unrelated calls.
    """
    requirements: list[Requirement] = []
    for doc in load_guidance_documents(repo_root):
        if doc.source == "rss_playbook" and not include_pda_playbook:
            continue
        prefix = "NIHR" if doc.source == "nihr_domestic" else "RSS" if doc.source == "rss_playbook" else "PGM"
        requirements.extend(parse_guidance_text(doc.text, doc.source, prefix=prefix))
    return ensure_area_coverage(requirements)


def detects_pda_relevance(*texts: str) -> bool:
    joined = " ".join(t for t in texts if t).lower()
    indicators = ["i4i", "product development award", "pda", "product-development", "medical device", "digital health", "innovation", "trl"]
    return any(indicator in joined for indicator in indicators)


def add_runtime_guidance(texts: Iterable[tuple[str, str]], start: int = 1) -> list[Requirement]:
    requirements: list[Requirement] = []
    for source, text in texts:
        if text.strip():
            requirements.extend(parse_guidance_text(text, source, prefix=f"RT{start}"))
            start += 1
    return requirements
