"""Where does each creature run? Shown on every encounter card.

Laptop profile: a local process on this machine.
Cloud profile: a pod (or a container of this pod). The pod that holds the game knows its own
name from the Kubernetes downward API (POD_NAME, NODE_NAME, POD_NAMESPACE); other pods are
looked up with `kubectl get pods -l app=...` through the console's read-only RBAC.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Callable

from bestiary.config import Settings, settings

# creature id -> (where it lives, detail). "here" = a container in the console pod.
# Anything else is the `app` label of the pod that serves the creature.
PLACEMENT: dict[str, tuple[str, str]] = {
    "mender": ("here", "container console (goose)"),
    "octoplug": ("here", "container forge (MCP server)"),
    "bulwark": ("here", "container agentgateway (sidecar, :3000)"),
    "scribbit": ("here", "file in the shared emptyDir (AGENTS.md)"),
    "satchel": ("here", "files in the shared emptyDir (.agents/skills)"),
    "glyphstone": ("ollama", "Ollama /v1/responses"),
    "chasqui": ("reviewer-a2a", "reviewer agent (A2A)"),
    "switchy": ("agent-router", "Agent Router :1975"),
    "glasshell": ("static:namespace opensandbox", "a sandbox pod created per run by OpenSandbox"),
    "dojolotl": ("openenv-farolito", "OpenEnv environment"),
}

LAPTOP_DETAIL: dict[str, str] = {
    "mender": "goose CLI process",
    "octoplug": "forge MCP server process :8765",
    "bulwark": "agentgateway process :3000",
    "scribbit": "AGENTS.md file in .bestiary/work",
    "satchel": "skills files in .bestiary/work",
    "glyphstone": "Ollama (or OpenAI) /v1/responses",
    "chasqui": "reviewer A2A process :9999",
    "switchy": "Agent Router (aigw) :1975",
    "glasshell": "OpenSandbox server (Docker)",
    "dojolotl": "OpenEnv environment (explanation)",
}

Runner = Callable[[list[str]], str]


def _kubectl(args: list[str]) -> str:
    exe = shutil.which("kubectl")
    if not exe:
        raise FileNotFoundError("kubectl")
    r = subprocess.run([exe, *args], capture_output=True, text=True, timeout=5)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return r.stdout.strip()


@dataclass
class Where:
    settings: Settings = field(default_factory=settings)
    kubectl: Runner = _kubectl
    _cache: dict[str, str] = field(default_factory=dict)

    def _here(self) -> str:
        pod = os.environ.get("POD_NAME") or socket.gethostname()
        node = os.environ.get("NODE_NAME")
        return f"pod/{pod}" + (f" on node {node}" if node else "")

    def _pod_of(self, app: str) -> str:
        """Pod name and node of the pod behind `app=<label>`; the service name if kubectl cannot say."""
        if app in self._cache:
            return self._cache[app]
        try:
            out = self.kubectl([
                "-n", self.settings.namespace, "get", "pods", "-l", f"app={app}",
                "-o", r"jsonpath={.items[0].metadata.name} {.items[0].spec.nodeName}",
            ])
            name, _, node = out.partition(" ")
            text = f"pod/{name}" + (f" on node {node}" if node else "") if name else f"svc/{app}"
        except (OSError, RuntimeError, subprocess.SubprocessError):
            text = f"svc/{app}"
        self._cache[app] = text
        return text

    def describe(self, creature_id: str) -> str:
        """One short line: where the creature runs."""
        if not self.settings.is_cloud:
            detail = LAPTOP_DETAIL.get(creature_id, "local process")
            return f"host {socket.gethostname()}: {detail}"
        place, detail = PLACEMENT.get(creature_id, ("here", "console pod"))
        if place == "here":
            base = self._here()
        elif place.startswith("static:"):
            base = place.removeprefix("static:")
        else:
            base = self._pod_of(place)
        if creature_id == "glyphstone":
            detail += f" ({self.settings.accelerator.upper()})"
        return f"{base}: {detail}"
