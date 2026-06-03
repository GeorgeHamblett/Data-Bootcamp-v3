"""Shared public identifier extraction and routing helpers for similarity checks."""
from __future__ import annotations

import re

PATENT_RE = re.compile(r"\b(?:US|EP|WO)\s?\d{6,}[A-Z0-9]*\b", re.I)
NIHR_RE = re.compile(r"\bAI[_\-\s]?AWARD\d{3,}\b|\bNIHR\d{4,}\b", re.I)
TRIAL_RE = re.compile(r"\bISRCTN\d{6,}\b|\bNCT\d{8}\b", re.I)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)


def normalise_identifier(value: str) -> str:
    item = str(value or "").strip().strip(".,;:()[]{}")
    if PATENT_RE.fullmatch(item):
        return re.sub(r"\s+", "", item).upper()
    item = re.sub(r"AI[_\-\s]?AWARD", "AI_AWARD", item, flags=re.I)
    if NIHR_RE.fullmatch(item) or TRIAL_RE.fullmatch(item):
        return item.upper().replace(" ", "")
    return item


def extract_identifiers(text: str) -> list[str]:
    ids: list[str] = []
    for pattern in (PATENT_RE, NIHR_RE, TRIAL_RE, DOI_RE):
        for match in pattern.finditer(str(text or "")):
            ids.append(normalise_identifier(match.group(0)))
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        key = item.upper()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def is_patent_identifier(value: str) -> bool:
    return bool(PATENT_RE.fullmatch(normalise_identifier(value)))


def is_nihr_identifier(value: str) -> bool:
    return bool(NIHR_RE.fullmatch(normalise_identifier(value)))


def is_trial_identifier(value: str) -> bool:
    return bool(TRIAL_RE.fullmatch(normalise_identifier(value)))


def is_any_identifier(value: str) -> bool:
    item = normalise_identifier(value)
    return is_patent_identifier(item) or is_nihr_identifier(item) or is_trial_identifier(item) or bool(DOI_RE.fullmatch(item))
