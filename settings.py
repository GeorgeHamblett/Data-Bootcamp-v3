"""Environment and privacy settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dependency optional in tests
    load_dotenv = None

MISSING_PREFIXES = ("replace_with", "optional_replace", "your_real")


def _load_env() -> None:
    if load_dotenv:
        load_dotenv()


def str_to_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def is_missing_secret(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return not stripped or stripped.lower().startswith(MISSING_PREFIXES)


def mask_secret(value: str | None) -> str:
    if is_missing_secret(value):
        return "missing"
    assert value is not None
    return f"{value[:3]}…{value[-3:]}" if len(value) > 6 else "***"

@dataclass
class Settings:
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:1b"
    lens_api_token: str = ""
    lens_api_base_url: str = "https://api.lens.org/scholarly/search"
    epo_ops_consumer_key: str = ""
    epo_ops_consumer_secret: str = ""
    epo_ops_base_url: str = "https://ops.epo.org/3.2"
    epo_ops_auth_url: str = "https://ops.epo.org/3.2/auth/accesstoken"
    nihr_open_data_base_url: str = "https://nihr.opendatasoft.com/api/explore/v2.1"
    nihr_open_data_dataset_id: str = "infonihr-open-dataset"
    nihr_open_data_api_key: str = ""
    local_only_mode: bool = True
    allow_external_similarity_queries: bool = False
    save_uploads: bool = False
    mock_similarity_mode: bool = False
    repo_root: Path = Path(__file__).resolve().parent

    @property
    def lens_credentials_available(self) -> bool:
        return not is_missing_secret(self.lens_api_token)

    @property
    def epo_credentials_available(self) -> bool:
        return not is_missing_secret(self.epo_ops_consumer_key) and not is_missing_secret(self.epo_ops_consumer_secret)

    @property
    def can_run_live_similarity(self) -> bool:
        return not self.local_only_mode and self.allow_external_similarity_queries and not self.mock_similarity_mode

    def credential_status(self) -> dict[str, str]:
        return {
            "Lens API token": mask_secret(self.lens_api_token),
            "EPO OPS key": mask_secret(self.epo_ops_consumer_key),
            "EPO OPS secret": mask_secret(self.epo_ops_consumer_secret),
            "NIHR Open Data key": mask_secret(self.nihr_open_data_api_key),
        }


def load_settings() -> Settings:
    _load_env()
    return Settings(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "gemma3:1b"),
        lens_api_token=os.getenv("LENS_API_TOKEN", ""),
        lens_api_base_url=os.getenv("LENS_API_BASE_URL", "https://api.lens.org/scholarly/search"),
        epo_ops_consumer_key=os.getenv("EPO_OPS_CONSUMER_KEY", ""),
        epo_ops_consumer_secret=os.getenv("EPO_OPS_CONSUMER_SECRET", ""),
        epo_ops_base_url=os.getenv("EPO_OPS_BASE_URL", "https://ops.epo.org/3.2"),
        epo_ops_auth_url=os.getenv("EPO_OPS_AUTH_URL", "https://ops.epo.org/3.2/auth/accesstoken"),
        nihr_open_data_base_url=os.getenv("NIHR_OPEN_DATA_BASE_URL", "https://nihr.opendatasoft.com/api/explore/v2.1"),
        nihr_open_data_dataset_id=os.getenv("NIHR_OPEN_DATA_DATASET_ID", "infonihr-open-dataset"),
        nihr_open_data_api_key=os.getenv("NIHR_OPEN_DATA_API_KEY", ""),
        local_only_mode=str_to_bool(os.getenv("LOCAL_ONLY_MODE"), True),
        allow_external_similarity_queries=str_to_bool(os.getenv("ALLOW_EXTERNAL_SIMILARITY_QUERIES"), False),
        save_uploads=str_to_bool(os.getenv("SAVE_UPLOADS"), False),
    )
