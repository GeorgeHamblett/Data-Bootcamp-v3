"""Application settings and privacy controls."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MISSING_PREFIXES = ("replace_with", "optional_replace", "your_real")


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def as_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_missing_credential(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return not stripped or stripped.lower().startswith(MISSING_PREFIXES)


def mask_secret(value: str | None) -> str:
    return "missing" if is_missing_credential(value) else "present"


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:1b"
    require_local_llm: bool = True
    strict_local_only_mode: bool = False
    allow_external_similarity_queries: bool = True
    send_only_safe_query_terms: bool = True
    lens_api_token: str = ""
    lens_api_base_url: str = "https://api.lens.org/scholarly/search"
    epo_ops_consumer_key: str = ""
    epo_ops_consumer_secret: str = ""
    epo_ops_base_url: str = "https://ops.epo.org"  # Backwards-compatible alias for service base.
    epo_ops_auth_url: str = "https://ops.epo.org/3.2/auth/accesstoken"
    epo_ops_service_base_url: str = "https://ops.epo.org"
    nihr_open_data_base_url: str = "https://nihr.opendatasoft.com/api/explore/v2.1"
    nihr_open_data_dataset_id: str = "infonihr-open-dataset"
    nihr_open_data_api_key: str = ""
    local_only_mode: bool = False  # backwards-compatible alias; strict_local_only_mode is authoritative.
    save_uploads: bool = False
    mock_similarity_mode: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        legacy_local_only = as_bool(os.getenv("LOCAL_ONLY_MODE"), False)
        strict_local_only = as_bool(os.getenv("STRICT_LOCAL_ONLY_MODE"), legacy_local_only)
        epo_service_base = os.getenv(
            "EPO_OPS_SERVICE_BASE_URL",
            os.getenv("EPO_OPS_BASE_URL", cls.epo_ops_service_base_url),
        )
        legacy_epo_base = os.getenv("EPO_OPS_BASE_URL", epo_service_base)
        return cls(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", cls.ollama_base_url),
            ollama_model=os.getenv("OLLAMA_MODEL", cls.ollama_model),
            require_local_llm=as_bool(os.getenv("REQUIRE_LOCAL_LLM"), True),
            strict_local_only_mode=strict_local_only,
            allow_external_similarity_queries=as_bool(os.getenv("ALLOW_EXTERNAL_SIMILARITY_QUERIES"), True),
            send_only_safe_query_terms=as_bool(os.getenv("SEND_ONLY_SAFE_QUERY_TERMS"), True),
            lens_api_token=os.getenv("LENS_API_TOKEN", ""),
            lens_api_base_url=os.getenv("LENS_API_BASE_URL", cls.lens_api_base_url),
            epo_ops_consumer_key=os.getenv("EPO_OPS_CONSUMER_KEY", ""),
            epo_ops_consumer_secret=os.getenv("EPO_OPS_CONSUMER_SECRET", ""),
            epo_ops_base_url=legacy_epo_base,
            epo_ops_auth_url=os.getenv("EPO_OPS_AUTH_URL", cls.epo_ops_auth_url),
            epo_ops_service_base_url=epo_service_base,
            nihr_open_data_base_url=os.getenv("NIHR_OPEN_DATA_BASE_URL", cls.nihr_open_data_base_url),
            nihr_open_data_dataset_id=os.getenv("NIHR_OPEN_DATA_DATASET_ID", cls.nihr_open_data_dataset_id),
            nihr_open_data_api_key=os.getenv("NIHR_OPEN_DATA_API_KEY", ""),
            local_only_mode=legacy_local_only,
            save_uploads=as_bool(os.getenv("SAVE_UPLOADS"), False),
            mock_similarity_mode=as_bool(os.getenv("MOCK_SIMILARITY_MODE"), False),
        )

    def credential_status(self) -> dict[str, str]:
        return {
            "Lens API token": mask_secret(self.lens_api_token),
            "EPO OPS consumer key": mask_secret(self.epo_ops_consumer_key),
            "EPO OPS consumer secret": mask_secret(self.epo_ops_consumer_secret),
            "NIHR Open Data API key": mask_secret(self.nihr_open_data_api_key),
        }
