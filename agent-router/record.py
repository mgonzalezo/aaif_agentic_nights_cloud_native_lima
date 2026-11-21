"""Record a real call through Agent Router (aigw run) as the replay for encounter 9."""

from __future__ import annotations

import os
import sys
import time

import httpx

from bestiary.engine import save_replay
from bestiary.llm import Detection, Provider

URL = os.environ.get("AGENT_ROUTER_URL", "http://localhost:1975")
MODEL = os.environ.get("BESTIARY_MODEL", "qwen3.5:9b")


def main() -> int:
    body = {"model": MODEL, "messages": [{"role": "user", "content": "In one sentence: what does an AI gateway do?"}]}
    started = time.time()
    try:
        r = httpx.post(f"{URL}/v1/chat/completions", json=body, timeout=120)
    except httpx.HTTPError as err:
        print(f"Agent Router not reachable at {URL}: {err}")
        return 1
    events = [
        {"kind": f"POST {URL}/v1/chat/completions (app talks to Agent Router)", "data": body},
        {"kind": f"HTTP {r.status_code} via Agent Router", "data": {k: v for k, v in r.headers.items() if k.lower().startswith(("x-", "server", "content-type"))}},
        {"kind": "response (served by Ollama behind Agent Router)", "data": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text},
    ]
    path = save_replay("e9_agent_router", events, Detection(Provider("agent-router", URL, MODEL), []), time.time() - started)
    print(f"saved {path}")
    return 0 if r.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
