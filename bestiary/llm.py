"""Model access through the Open Responses shape: POST {base}/responses.

Provider choice (BESTIARY_PROVIDER=auto):
  1. Ollama on OLLAMA_HOST, if BESTIARY_MODEL (default qwen3.5:9b) is pulled.
  2. Otherwise OpenAI, if OPENAI_API_KEY and OPENAI_MODEL are set.
  3. Otherwise no model: model-dependent encounters fall back to REPLAY or DIDACTIC.

Plain httpx on purpose, so the request and the response items can be shown unedited.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from bestiary.config import Settings, settings


@dataclass
class Provider:
    name: str
    base_url: str
    model: str
    headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        return f"{self.name}:{self.model}"


@dataclass
class Detection:
    provider: Provider | None
    notes: list[str]


def _extra_body() -> dict[str, Any]:
    raw = os.environ.get("BESTIARY_EXTRA_BODY", "").strip()
    return json.loads(raw) if raw else {}


def detect(s: Settings | None = None) -> Detection:
    s = s or settings()
    notes: list[str] = []
    want = s.provider.lower()

    if want in ("auto", "ollama"):
        try:
            tags = httpx.get(f"{s.ollama_host}/api/tags", timeout=2).json()
            names = [m.get("name", "") for m in tags.get("models", [])]
            if s.ollama_model in names or f"{s.ollama_model}:latest" in names:
                return Detection(
                    Provider("ollama", f"{s.ollama_host}/v1", s.ollama_model, extra_body=_extra_body()), notes
                )
            notes.append(f"Ollama is running but '{s.ollama_model}' is not pulled: ollama pull {s.ollama_model}")
        except (httpx.HTTPError, ValueError):
            notes.append(f"Ollama not reachable at {s.ollama_host}")
        if want == "ollama":
            return Detection(None, notes)

    if want in ("auto", "openai"):
        if s.openai_api_key and s.openai_model:
            return Detection(
                Provider(
                    "openai",
                    s.openai_base_url,
                    s.openai_model,
                    headers={"Authorization": f"Bearer {s.openai_api_key}"},
                    extra_body=_extra_body(),
                ),
                notes,
            )
        notes.append("OpenAI fallback needs OPENAI_API_KEY and OPENAI_MODEL")

    return Detection(None, notes)


def responses(
    provider: Provider,
    input_items: list[dict] | str,
    *,
    tools: list[dict] | None = None,
    instructions: str | None = None,
    timeout: float | None = None,
) -> dict:
    """One stateless call to {base}/responses. Returns the raw JSON response."""
    body: dict[str, Any] = {"model": provider.model, "input": input_items, "store": False}
    if instructions:
        body["instructions"] = instructions
    if tools:
        body["tools"] = tools
    body.update(provider.extra_body)
    r = httpx.post(
        f"{provider.base_url}/responses",
        json=body,
        headers=provider.headers,
        timeout=timeout or settings().llm_timeout,
    )
    if r.status_code == 404:
        raise RuntimeError(
            f"{provider.name} does not serve /v1/responses (Open Responses). "
            "For Ollama, upgrade to 0.13.3 or later."
        )
    r.raise_for_status()
    return r.json()


def output_text(resp: dict) -> str:
    parts = []
    for item in resp.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") in ("output_text", "text"):
                    parts.append(c.get("text", ""))
    return "".join(parts).strip() or resp.get("output_text", "")


def function_calls(resp: dict) -> list[dict]:
    return [i for i in resp.get("output", []) if i.get("type") == "function_call"]
