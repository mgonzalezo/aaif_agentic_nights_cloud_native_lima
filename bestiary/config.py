"""Settings, read from environment variables (or a .env file in the repo root).

Everything has a default so `uv run bestiary` works with nothing configured.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# BESTIARY_STATE_DIR lets a Kubernetes pod put the working copy on a volume shared by
# the game, the forge MCP server and goose (an emptyDir). Default: .bestiary in the repo.
STATE_DIR = Path(os.environ.get("BESTIARY_STATE_DIR") or REPO_ROOT / ".bestiary")
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


def profile() -> str:
    """laptop (default): everything on 127.0.0.1. cloud: in-cluster Kubernetes service URLs."""
    return os.environ.get("BESTIARY_PROFILE", "laptop").strip().lower() or "laptop"


def _by_profile(laptop: str, cloud: str) -> str:
    return cloud if profile() == "cloud" else laptop


@dataclass
class Settings:
    # Model provider: auto | ollama | openai | none
    profile: str = field(default_factory=profile)
    ui: str = field(default_factory=lambda: _env("BESTIARY_UI", "classic").lower())  # classic | battle
    provider: str = field(default_factory=lambda: _env("BESTIARY_PROVIDER", "auto"))
    ollama_host: str = field(default_factory=lambda: _env("OLLAMA_HOST", _by_profile("http://localhost:11434", "http://ollama:11434")))
    ollama_model: str = field(default_factory=lambda: _env("BESTIARY_MODEL", "qwen3.5:9b"))
    accelerator: str = field(default_factory=lambda: _env("BESTIARY_ACCELERATOR", "gpu").lower())  # where Ollama runs in the cloud profile: gpu | cpu
    failover_model: str = field(default_factory=lambda: _env("BESTIARY_FAILOVER_MODEL", "qwen3.5:4b"))
    openai_base_url: str = field(default_factory=lambda: _env("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", ""))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY", ""))

    # Local services started by the game
    forge_port: int = field(default_factory=lambda: int(_env("BESTIARY_FORGE_PORT", "8765")))
    reviewer_port: int = field(default_factory=lambda: int(_env("BESTIARY_REVIEWER_PORT", "9999")))
    gateway_url: str = field(default_factory=lambda: _env("BESTIARY_GATEWAY_URL", "http://localhost:3000/mcp"))
    sandbox_domain: str = field(default_factory=lambda: _env("OPEN_SANDBOX_DOMAIN", _by_profile("localhost:8080", "opensandbox-server.opensandbox-system.svc.cluster.local:80")))
    # Reviewer (A2A), Agent Router and OpenEnv. In the cloud profile they are separate pods.
    reviewer_url_env: str = field(default_factory=lambda: _env("BESTIARY_REVIEWER_URL", _by_profile("", "http://reviewer-a2a:9999")))
    agent_router_url: str = field(default_factory=lambda: _env("BESTIARY_AGENT_ROUTER_URL", _by_profile("http://localhost:1975", "http://agent-router:1975")))
    openenv_url: str = field(default_factory=lambda: _env("BESTIARY_OPENENV_URL", _by_profile("", "http://openenv-farolito:8000")))
    # Where the game runs (Kubernetes downward API in the cloud profile)
    namespace: str = field(default_factory=lambda: _env("POD_NAMESPACE", "bestiary"))

    # Forge backend: local | github
    forge_backend: str = field(default_factory=lambda: _env("BESTIARY_FORGE", "local"))
    github_repo: str = field(default_factory=lambda: _env("BESTIARY_GITHUB_REPO", ""))
    github_token: str = field(default_factory=lambda: _env("GITHUB_TOKEN", ""))

    # Stage behaviour
    goose_timeout: int = field(default_factory=lambda: int(_env("BESTIARY_GOOSE_TIMEOUT", "120")))
    goose_attempts: int = field(default_factory=lambda: int(_env("BESTIARY_GOOSE_ATTEMPTS", "2")))  # live attempts before the known-good fix
    llm_timeout: int = field(default_factory=lambda: int(_env("BESTIARY_LLM_TIMEOUT", "60")))
    talk_banner: str = field(default_factory=lambda: _env("BESTIARY_TALK_BANNER", "Talk version: Agentic Nights Lima, Nov 2026"))

    @property
    def forge_url(self) -> str:
        return f"http://127.0.0.1:{self.forge_port}/mcp"

    @property
    def reviewer_url(self) -> str:
        return self.reviewer_url_env or f"http://127.0.0.1:{self.reviewer_port}"

    @property
    def reviewer_is_local(self) -> bool:
        """True when the game starts the reviewer itself (laptop). False when it is another pod or host."""
        return not self.reviewer_url_env

    @property
    def is_cloud(self) -> bool:
        return self.profile == "cloud"

    def issue_number(self) -> int:
        """Issue number of the story's bug (7 locally; whatever GitHub assigned online)."""
        if self.forge_backend == "github" and os.environ.get("BESTIARY_GITHUB_ISSUE"):  # pods lose the state file: set the number in the config
            return int(os.environ["BESTIARY_GITHUB_ISSUE"])
        if self.forge_backend == "github" and GITHUB_STATE.exists():
            return int(json.loads(GITHUB_STATE.read_text())["issue_number"])
        return 7


def settings() -> Settings:
    return Settings()
