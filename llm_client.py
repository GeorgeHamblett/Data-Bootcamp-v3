"""Minimal local Ollama JSON client used as optional enhancement."""
from __future__ import annotations

import json
from typing import Any

import requests

from settings import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.ollama_model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        response = requests.post(f"{self.settings.ollama_base_url}/api/generate", json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("response", "")

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        text = self.generate(system_prompt, user_prompt, json_mode=True)
        return json.loads(text)
