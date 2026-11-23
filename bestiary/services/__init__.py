"""Start and stop the local services the game talks to."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from contextlib import contextmanager

from bestiary.config import REPO_ROOT, STATE_DIR, Settings, settings


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        try:
            return s.connect_ex((host, port)) == 0
        except OSError:  # unresolvable name (a service that does not exist), unreachable network
            return False


def _wait(port: int, seconds: float = 20) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if port_open(port):
            return True
        time.sleep(0.2)
    return False


def local_services(s: Settings) -> list[tuple[str, int]]:
    """Services the game starts itself. The reviewer is skipped when it lives elsewhere
    (another pod in the cloud profile, or BESTIARY_REVIEWER_URL)."""
    services = [("bestiary.services.forge_mcp", s.forge_port)]
    if s.reviewer_is_local:
        services.append(("bestiary.services.reviewer_a2a", s.reviewer_port))
    return services


@contextmanager
def running_services():
    """Start forge (MCP) and reviewer (A2A) unless something already listens on their ports."""
    s = settings()
    procs = []
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log = open(STATE_DIR / "services.log", "a", encoding="utf-8")
    for module, port in local_services(s):
        if port_open(port):
            continue
        procs.append(
            subprocess.Popen([sys.executable, "-m", module, "--port", str(port)], cwd=REPO_ROOT, stdout=log, stderr=log)
        )
        if not _wait(port):
            raise RuntimeError(f"{module} did not start on port {port}; see .bestiary/services.log")
    try:
        yield
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        log.close()
