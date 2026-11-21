"""Start and stop the local services the game talks to."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from contextlib import contextmanager

from bestiary.config import REPO_ROOT, settings


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def _wait(port: int, seconds: float = 20) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if port_open(port):
            return True
        time.sleep(0.2)
    return False


@contextmanager
def running_services():
    """Start forge (MCP) and reviewer (A2A) unless something already listens on their ports."""
    s = settings()
    procs = []
    (REPO_ROOT / ".bestiary").mkdir(exist_ok=True)
    log = open(REPO_ROOT / ".bestiary" / "services.log", "a", encoding="utf-8")
    for module, port in (("bestiary.services.forge_mcp", s.forge_port), ("bestiary.services.reviewer_a2a", s.reviewer_port)):
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
