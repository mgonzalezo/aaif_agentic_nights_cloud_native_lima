import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(app, port: int) -> uvicorn.Server:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return server


@pytest.fixture
def fake_model(monkeypatch):
    import fake_model as fm

    port = free_port()
    server = serve(fm.app, port)
    monkeypatch.setenv("OLLAMA_HOST", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("BESTIARY_PROVIDER", "ollama")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


@pytest.fixture
def fresh_workspace():
    from bestiary import workspace

    workspace.reset()
    yield workspace
    workspace.reset()


@pytest.fixture(autouse=True)
def isolated_replays(tmp_path, monkeypatch):
    """In-process tests must not pick up the recordings committed in replays/ (they would turn
    DIDACTIC fallbacks into REPLAY). Tests that write replays use this empty directory."""
    import bestiary.engine as engine

    monkeypatch.setattr(engine, "REPLAY_DIR", tmp_path / "replays")
