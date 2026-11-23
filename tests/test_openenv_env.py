"""Encounter 10: the farolito OpenEnv environment. Needs: uv run --group openenv pytest"""

import json
import threading
import time

import httpx
import pytest

pytest.importorskip("openenv")

from farolito_env.environment import FarolitoEnvironment, issue_text  # noqa: E402
from farolito_env.models import FarolitoAction  # noqa: E402
from conftest import free_port, serve  # noqa: E402

from pathlib import Path  # noqa: E402

REFERENCE = (Path(__file__).resolve().parent.parent / "upstream" / "reference_fix" / "cli.py").read_text(encoding="utf-8")


def test_reset_gives_the_issue_without_the_injection_payload():
    obs = FarolitoEnvironment().reset()
    assert "Traceback when the config file is missing" in obs.issue
    assert "ignore your previous instructions" not in issue_text()
    assert "farolito/cli.py" in obs.files and obs.reward == 0.0 and not obs.done


def test_step_rewards_the_reference_fix_and_not_the_bug():
    env = FarolitoEnvironment()
    env.reset()
    bug = env.step(FarolitoAction(cli_py="import sys\nsys.exit(0)\n"))
    assert bug.reward == 0.0 and bug.done
    good = env.step(FarolitoAction(cli_py=REFERENCE))
    assert good.reward == 1.0 and good.done and "passed" in good.pytest_tail


def test_an_unchanged_repo_fails_the_tests():
    assert FarolitoEnvironment().step(FarolitoAction()).reward == 0.0


def test_http_endpoints_reset_and_step():
    from farolito_env.app import app

    port = free_port()
    server = serve(app, port)
    try:
        base = f"http://127.0.0.1:{port}"
        assert httpx.get(f"{base}/health").status_code == 200
        reset = httpx.post(f"{base}/reset", json={}).json()
        assert "Traceback" in reset["observation"]["issue"]
        step = httpx.post(f"{base}/step", json={"action": {"cli_py": REFERENCE}}, timeout=60).json()
        assert step["reward"] == 1.0 and step["done"] is True
        assert "passed" in step["observation"]["pytest_tail"]
    finally:
        server.should_exit = True
