"""Load text from Streamlit uploads without treating built-in guidance as apps."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any


def _read_txt(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt" or not suffix:
        return _read_txt(data)
    if suffix == ".docx":
        try:
            import docx
            doc = docx.Document(BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return ""
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""
    if suffix in {".xlsx", ".xls"}:
        try:
            import pandas as pd
            frames = pd.read_excel(BytesIO(data), sheet_name=None, header=None)
            return "\n".join(f"Sheet: {name}\n{df.to_string(index=False)}" for name, df in frames.items())
        except Exception:
            return ""
    return _read_txt(data)


def load_uploaded_files(files: list[Any] | None) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    for file in files or []:
        name = getattr(file, "name", "uploaded_document")
        data = file.read()
        documents.append({"name": name, "text": extract_text_from_bytes(name, data)})
    return documents


def combine_pasted_and_uploaded(pasted_text: str, uploaded_docs: list[dict[str, str]], pasted_name: str) -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    if pasted_text.strip():
        docs.append({"name": pasted_name, "text": pasted_text.strip()})
    docs.extend(doc for doc in uploaded_docs if doc.get("text", "").strip())
    return docs
