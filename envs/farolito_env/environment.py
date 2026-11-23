"""reset() gives the issue and the file list; step() applies the action to a FRESH copy of the
toy repo, runs pytest, and returns reward 1.0 (green) or 0.0.

Each step uses its own temp copy, so the environment is correct over the stateless HTTP
/step endpoint as well as over a WebSocket session.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

from farolito_env.models import FarolitoAction, FarolitoObservation

# In the container the toy repo is copied to /app/toy_repo. In a checkout it is upstream/farolito.
REPO = Path(os.environ.get("FAROLITO_TOY_REPO") or Path(__file__).resolve().parent.parent.parent / "upstream" / "farolito")
IGNORED = shutil.ignore_patterns("__pycache__", ".pytest_cache", "issues.json")
ISSUE_NUMBER = 7


def issue_text() -> str:
    """Issue #7 as a training task. HTML comments are stripped: an environment should not hand
    prompt-injection payloads to the policy it is training."""
    issues = json.loads((REPO / "issues.json").read_text(encoding="utf-8"))
    issue = next(i for i in issues if i["number"] == ISSUE_NUMBER)
    body = re.sub(r"<!--.*?-->", "", issue["body"], flags=re.S).strip()
    return f"Issue #{issue['number']}: {issue['title']}\n\n{body}"


def repo_files() -> list[str]:
    return sorted(
        p.relative_to(REPO).as_posix()
        for p in REPO.rglob("*")
        if p.is_file() and not ({"__pycache__", ".pytest_cache"} & set(p.parts)) and p.name != "issues.json"
    )


class FarolitoEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self) -> None:
        super().__init__()
        self._state = State(episode_id=str(uuid4()), step_count=0)

    def reset(self, seed=None, episode_id=None, **kwargs) -> FarolitoObservation:
        self._state = State(episode_id=episode_id or str(uuid4()), step_count=0)
        return FarolitoObservation(issue=issue_text(), files=repo_files(), done=False, reward=0.0)

    def step(self, action: FarolitoAction, timeout_s=None, **kwargs) -> FarolitoObservation:
        self._state.step_count += 1
        tail, ok = self._run(action, timeout_s or 60)
        return FarolitoObservation(issue=issue_text(), files=repo_files(), pytest_tail=tail, done=True, reward=1.0 if ok else 0.0)

    @property
    def state(self) -> State:
        return self._state

    @staticmethod
    def _run(action: FarolitoAction, timeout: float) -> tuple[str, bool]:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "repo"
            shutil.copytree(REPO, work, ignore=IGNORED)
            if action.cli_py is not None:
                (work / "farolito" / "cli.py").write_text(action.cli_py, encoding="utf-8")
            elif action.diff:
                try:
                    p = subprocess.run(["patch", "-p1", "--batch"], input=action.diff, text=True, cwd=work, capture_output=True, timeout=30)
                except (OSError, subprocess.TimeoutExpired) as err:
                    return f"patch not applied: {err}", False
                if p.returncode != 0:
                    return ("patch failed:\n" + p.stdout + p.stderr)[-1500:], False
            try:
                t = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
                    cwd=work, capture_output=True, text=True, timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                return "pytest timed out", False
            return (t.stdout + t.stderr)[-1500:], t.returncode == 0
