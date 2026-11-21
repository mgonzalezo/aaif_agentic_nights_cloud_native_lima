"""Settings, read from environment variables (or a .env file in the repo root).

Everything has a default so `uv run bestiary` works with nothing configured.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / ".bestiary"
WORK_DIR = STATE_DIR / "work" / "farolito"
UPSTREAM_TEMPLATE = REPO_ROOT / "upstream" / "farolito"
REFERENCE_FIX = REPO_ROOT / "upstream" / "reference_fix" / "cli.py"
REPLAY_DIR = REPO_ROOT / "replays"
GITHUB_STATE = STATE_DIR / "github.json"


def _load_dotenv() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default) or default


@dataclass
class Settings:
    # Model provider: auto | ollama | openai | none
    provider: str = field(default_factory=lambda: _env("BESTIARY_PROVIDER", "auto"))
    ollama_host: str = field(default_factory=lambda: _env("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("BESTIARY_MODEL", "qwen3.5:9b"))
    openai_base_url: str = field(default_factory=lambda: _env("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", ""))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY", ""))

    # Local services started by the game
    forge_port: int = field(default_factory=lambda: int(_env("BESTIARY_FORGE_PORT", "8765")))
    reviewer_port: int = field(default_factory=lambda: int(_env("BESTIARY_REVIEWER_PORT", "9999")))
    gateway_url: str = field(default_factory=lambda: _env("BESTIARY_GATEWAY_URL", "http://localhost:3000/mcp"))
    sandbox_domain: str = field(default_factory=lambda: _env("OPEN_SANDBOX_DOMAIN", "localhost:8080"))

    # Forge backend: local | github
    forge_backend: str = field(default_factory=lambda: _env("BESTIARY_FORGE", "local"))
    github_repo: str = field(default_factory=lambda: _env("BESTIARY_GITHUB_REPO", ""))
    github_token: str = field(default_factory=lambda: _env("GITHUB_TOKEN", ""))

    # Stage behaviour
    goose_timeout: int = field(default_factory=lambda: int(_env("BESTIARY_GOOSE_TIMEOUT", "75")))
    llm_timeout: int = field(default_factory=lambda: int(_env("BESTIARY_LLM_TIMEOUT", "60")))
    talk_banner: str = field(default_factory=lambda: _env("BESTIARY_TALK_BANNER", "Talk version: Agentic Nights Lima, Nov 2026"))

    @property
    def forge_url(self) -> str:
        return f"http://127.0.0.1:{self.forge_port}/mcp"

    @property
    def reviewer_url(self) -> str:
        return f"http://127.0.0.1:{self.reviewer_port}"

    def issue_number(self) -> int:
        """Issue number of the story's bug (7 locally; whatever GitHub assigned online)."""
        if self.forge_backend == "github" and GITHUB_STATE.exists():
            return int(json.loads(GITHUB_STATE.read_text())["issue_number"])
        return 7


def settings() -> Settings:
    return Settings()
