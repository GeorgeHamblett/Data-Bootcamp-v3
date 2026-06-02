"""Minimal Ollama client used only when a local LLM is available."""
from __future__ import annotations

import json
from typing import Any


from prompts import SYSTEM_REVIEWER_PROMPT
from settings import Settings


class OllamaClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()

    def generate(self, prompt: str, system_prompt: str = SYSTEM_REVIEWER_PROMPT, expect_json: bool = False) -> Any:
        import requests
        payload = {"model": self.settings.ollama_model, "prompt": prompt, "system": system_prompt, "stream": False}
        response = requests.post(f"{self.settings.ollama_base_url}/api/generate", json=payload, timeout=60)
        response.raise_for_status()
        text = response.json().get("response", "")
        if expect_json:
            return json.loads(text)
        return text
