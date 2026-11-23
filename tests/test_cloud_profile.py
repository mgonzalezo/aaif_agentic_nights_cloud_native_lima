"""BESTIARY_PROFILE=cloud: in-cluster URLs from env vars, and "runs on" on every card."""

import io
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from bestiary.config import Settings
from bestiary.engine import Ctx, encounter_header, load_creatures
from bestiary.llm import Detection
from bestiary.services import local_services
from bestiary.where import Where

ROOT = Path(__file__).resolve().parent.parent


def test_laptop_profile_is_the_default(monkeypatch):
    for name in ("BESTIARY_PROFILE", "OLLAMA_HOST", "BESTIARY_REVIEWER_URL", "OPEN_SANDBOX_DOMAIN"):
        monkeypatch.delenv(name, raising=False)
    s = Settings()
    assert s.profile == "laptop" and not s.is_cloud
    assert s.ollama_host == "http://localhost:11434"
    assert s.reviewer_url == "http://127.0.0.1:9999"
    assert s.sandbox_domain == "localhost:8080"
    assert s.reviewer_is_local


def test_cloud_profile_uses_in_cluster_service_urls(monkeypatch):
    for name in ("OLLAMA_HOST", "BESTIARY_REVIEWER_URL", "OPEN_SANDBOX_DOMAIN", "BESTIARY_AGENT_ROUTER_URL", "BESTIARY_OPENENV_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BESTIARY_PROFILE", "cloud")
    s = Settings()
    assert s.is_cloud
    assert s.ollama_host == "http://ollama:11434"
    assert s.reviewer_url == "http://reviewer-a2a:9999"
    assert s.sandbox_domain == "opensandbox-server.opensandbox-system.svc.cluster.local:80"
    assert s.agent_router_url == "http://agent-router:1975"
    assert s.openenv_url == "http://openenv-farolito:8000"
    assert not s.reviewer_is_local


def test_env_vars_override_the_profile(monkeypatch):
    monkeypatch.setenv("BESTIARY_PROFILE", "cloud")
    monkeypatch.setenv("OLLAMA_HOST", "http://gpu-box:11434")
    monkeypatch.setenv("BESTIARY_REVIEWER_URL", "http://other:1234")
    s = Settings()
    assert s.ollama_host == "http://gpu-box:11434"
    assert s.reviewer_url == "http://other:1234"


def test_game_does_not_start_a_local_reviewer_in_the_cloud(monkeypatch):
    monkeypatch.delenv("BESTIARY_REVIEWER_URL", raising=False)
    monkeypatch.delenv("BESTIARY_PROFILE", raising=False)
    assert [m.rsplit(".", 1)[1] for m, _ in local_services(Settings())] == ["forge_mcp", "reviewer_a2a"]
    monkeypatch.setenv("BESTIARY_PROFILE", "cloud")
    assert [m.rsplit(".", 1)[1] for m, _ in local_services(Settings())] == ["forge_mcp"]


def test_state_dir_can_move_to_a_shared_volume(tmp_path):
    code = "from bestiary.config import STATE_DIR, WORK_DIR; print(STATE_DIR); print(WORK_DIR)"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         env={**__import__("os").environ, "BESTIARY_STATE_DIR": str(tmp_path)})
    state, work = out.stdout.split()
    assert Path(state) == tmp_path and Path(work) == tmp_path / "work" / "farolito"


def _fake_kubectl(calls):
    def run(args):
        calls.append(args)
        selector = args[args.index("-l") + 1]
        return {"app=ollama": "ollama-6f7d9 ip-10-0-1-5", "app=reviewer-a2a": "reviewer-a2a-77c4 ip-10-0-1-5"}.get(selector, "")

    return run


def test_where_in_the_cloud_names_pods_and_nodes(monkeypatch):
    monkeypatch.setenv("BESTIARY_PROFILE", "cloud")
    monkeypatch.setenv("POD_NAME", "console-5d9f7c8b6-x2k4q")
    monkeypatch.setenv("NODE_NAME", "ip-10-0-1-5")
    calls = []
    where = Where(settings=Settings(), kubectl=_fake_kubectl(calls))
    assert where.describe("octoplug").startswith("pod/console-5d9f7c8b6-x2k4q on node ip-10-0-1-5: container forge")
    assert where.describe("bulwark").startswith("pod/console-5d9f7c8b6-x2k4q")
    assert "sidecar" in where.describe("bulwark")
    assert where.describe("glyphstone").startswith("pod/ollama-6f7d9 on node ip-10-0-1-5")
    assert where.describe("chasqui").startswith("pod/reviewer-a2a-77c4")
    where.describe("glyphstone")
    assert len(calls) == 2  # ollama and reviewer-a2a, each looked up once (cached)


def test_where_falls_back_to_the_service_name_without_kubectl(monkeypatch):
    monkeypatch.setenv("BESTIARY_PROFILE", "cloud")

    def broken(args):
        raise FileNotFoundError("kubectl")

    assert Where(settings=Settings(), kubectl=broken).describe("switchy").startswith("svc/agent-router")


def test_where_on_the_laptop_names_the_host(monkeypatch):
    monkeypatch.delenv("BESTIARY_PROFILE", raising=False)
    text = Where(settings=Settings()).describe("octoplug")
    assert text.startswith("host ") and "forge MCP" in text


def test_every_creature_has_a_placement():
    from bestiary.where import LAPTOP_DETAIL, PLACEMENT

    ids = set(load_creatures())
    assert ids == set(PLACEMENT) == set(LAPTOP_DETAIL)


def test_encounter_card_shows_where_the_creature_runs(monkeypatch):
    monkeypatch.setenv("BESTIARY_PROFILE", "cloud")
    monkeypatch.setenv("POD_NAME", "console-abc")
    buf = io.StringIO()
    s = Settings()
    ctx = Ctx(console=Console(file=buf, width=120, force_terminal=False), settings=s, detection=Detection(None, []),
              creatures=load_creatures(), where=Where(settings=s, kubectl=_fake_kubectl([])))
    encounter_header(ctx, "2", "The issue in the fog", "Read the issue", ["octoplug"])
    out = buf.getvalue()
    assert "runs on:" in out and "pod/console-abc" in out


def test_port_open_is_false_for_an_unresolvable_service_name():
    from bestiary.services import port_open

    assert port_open(11434, "ollama.does-not-exist.invalid") is False


def test_doctor_in_the_cloud_profile_does_not_crash_outside_a_cluster(monkeypatch, capsys):
    from bestiary.cli import main

    monkeypatch.setenv("BESTIARY_PROFILE", "cloud")
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "profile: cloud" in out and "Agent Router" in out and "OpenEnv" in out


def _fake_openenv_app():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def health(_):
        return JSONResponse({"status": "healthy"})

    async def reset(_):
        return JSONResponse({"observation": {"issue": "Issue #7", "files": ["farolito/cli.py"]}, "reward": 0.0, "done": False})

    async def step(request):
        body = await request.json()
        fixed = "FileNotFoundError" in body["action"]["cli_py"]
        return JSONResponse({"observation": {"pytest_tail": "2 passed" if fixed else "1 failed"}, "reward": 1.0 if fixed else 0.0, "done": True})

    return Starlette(routes=[Route("/health", health), Route("/reset", reset, methods=["POST"]), Route("/step", step, methods=["POST"])])


def _auto_ctx(buf, monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    s = Settings()
    return Ctx(console=Console(file=buf, width=140, force_terminal=False), settings=s, detection=Detection(None, []),
               creatures=load_creatures(), auto=True, where=Where(settings=s, kubectl=_fake_kubectl([])))


def test_encounter_10_calls_the_openenv_server_live(monkeypatch, fresh_workspace):
    from bestiary.encounters import e10_dojo
    from conftest import free_port, serve

    port = free_port()
    server = serve(_fake_openenv_app(), port)
    try:
        fresh_workspace.apply_reference_fix()
        buf = io.StringIO()
        e10_dojo(_auto_ctx(buf, monkeypatch, BESTIARY_OPENENV_URL=f"http://127.0.0.1:{port}"))
        out = buf.getvalue()
        assert "LIVE" in out and "reward = 1.0" in out and "POST /step" in out
    finally:
        server.should_exit = True


def test_encounter_10_stays_didactic_without_a_server(monkeypatch, fresh_workspace):
    from bestiary.encounters import e10_dojo

    monkeypatch.delenv("BESTIARY_OPENENV_URL", raising=False)
    monkeypatch.delenv("BESTIARY_PROFILE", raising=False)
    buf = io.StringIO()
    e10_dojo(_auto_ctx(buf, monkeypatch))
    out = buf.getvalue()
    assert "DIDACTIC" in out and "not OpenEnv itself" in out


def _fake_router_app(state):
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def responses(request):
        body = await request.json()
        served = state["small"] if state["down"] else body["model"]
        out = [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": f"I am {served}."}]}]
        return JSONResponse({"model": served, "output": out})

    return Starlette(routes=[Route("/v1/responses", responses, methods=["POST"])])


def test_encounter_9_shows_failover_and_always_restores_the_service(monkeypatch):
    import json as _json

    from bestiary import encounters
    from conftest import free_port, serve

    state = {"down": False, "small": "qwen3.5:4b"}
    patches = []

    def fake_kube(args):
        if args[2:4] == ["patch", "svc"]:
            sel = _json.loads(args[-1])["spec"]["selector"]["app"]
            patches.append(sel)
            state["down"] = sel == "ollama-off"
        return ""

    monkeypatch.setattr(encounters, "_kube", fake_kube)
    monkeypatch.setattr(encounters.time, "sleep", lambda s: None)
    port = free_port()
    server = serve(_fake_router_app(state), port)
    try:
        buf = io.StringIO()
        ctx = _auto_ctx(buf, monkeypatch, BESTIARY_PROFILE="cloud", BESTIARY_AGENT_ROUTER_URL=f"http://127.0.0.1:{port}",
                        BESTIARY_MODEL="qwen3.5:35b")
        encounters.e9_detour(ctx)
        out = buf.getvalue()
        assert "LIVE" in out
        assert "I am qwen3.5:35b." in out and "I am qwen3.5:4b." in out
        assert patches == ["ollama-off", "ollama"]  # outage, then restored
    finally:
        server.should_exit = True


def test_encounter_9_never_claims_a_failover_that_did_not_happen(monkeypatch):
    from bestiary import encounters
    from conftest import free_port, serve

    state = {"down": False, "small": "qwen3.5:35b"}  # the router keeps answering from the main model

    monkeypatch.setattr(encounters, "_kube", lambda args: "")
    monkeypatch.setattr(encounters.time, "sleep", lambda s: None)
    port = free_port()
    server = serve(_fake_router_app(state), port)
    try:
        buf = io.StringIO()
        ctx = _auto_ctx(buf, monkeypatch, BESTIARY_PROFILE="cloud", BESTIARY_AGENT_ROUTER_URL=f"http://127.0.0.1:{port}",
                        BESTIARY_MODEL="qwen3.5:35b")
        encounters.e9_detour(ctx)
        out = buf.getvalue()
        assert "no failover observed" in out
        assert "Failover: asked for" not in out
        assert "DIDACTIC" in out  # falls back, and says so
    finally:
        server.should_exit = True


def test_encounter_9_touches_nothing_if_the_router_is_down(monkeypatch):
    from bestiary import encounters
    from conftest import free_port

    patches = []
    monkeypatch.setattr(encounters, "_kube", lambda args: patches.append(args[-1]) or "")
    buf = io.StringIO()
    ctx = _auto_ctx(buf, monkeypatch, BESTIARY_PROFILE="cloud", BESTIARY_AGENT_ROUTER_URL=f"http://127.0.0.1:{free_port()}")
    encounters.e9_detour(ctx)
    assert patches == []  # the first call failed before any outage was simulated
    assert "DIDACTIC" in buf.getvalue()


def test_encounter_9_is_not_live_on_a_laptop(monkeypatch):
    from bestiary import encounters

    monkeypatch.delenv("BESTIARY_PROFILE", raising=False)
    buf = io.StringIO()
    encounters.e9_detour(_auto_ctx(buf, monkeypatch))
    assert "DIDACTIC" in buf.getvalue()


def test_the_model_pod_says_whether_it_runs_on_gpu_or_cpu(monkeypatch):
    monkeypatch.setenv("BESTIARY_PROFILE", "cloud")
    monkeypatch.delenv("BESTIARY_ACCELERATOR", raising=False)
    where = Where(settings=Settings(), kubectl=_fake_kubectl([]))
    assert where.describe("glyphstone").endswith("(GPU)")
    monkeypatch.setenv("BESTIARY_ACCELERATOR", "cpu")
    assert Where(settings=Settings(), kubectl=_fake_kubectl([])).describe("glyphstone").endswith("(CPU)")


def test_a_gateway_rejection_is_shown_as_evidence_not_as_a_crash():
    import asyncio

    from bestiary import encounters

    class Rejected(Exception):
        error = type("E", (), {"code": -32602})()

    async def boom(url, name, args):
        raise BaseExceptionGroup("unhandled errors in a TaskGroup", [ExceptionGroup("inner", [Rejected("unknown resource")])])

    original = encounters._mcp_call
    encounters._mcp_call = boom
    try:
        answer = asyncio.run(encounters._mcp_call_or_error("http://x/mcp", "delete_branch", {"name": "main"}))
    finally:
        encounters._mcp_call = original
    assert answer == {"rejected": True, "error": {"code": -32602, "message": "unknown resource"}}


def test_router_metrics_show_which_backend_served_which_model():
    from bestiary.encounters import _parse_router_metrics

    text = (
        '# HELP x\n'
        'gen_ai_server_request_duration_seconds_count{gen_ai_backend="bestiary/ollama-main",gen_ai_original_model="qwen3.5:35b",'
        'gen_ai_response_model="qwen3.5:35b",otel_scope_name="x",} 1\n'
        'gen_ai_server_request_duration_seconds_count{gen_ai_backend="bestiary/ollama-small",gen_ai_original_model="qwen3.5:35b",'
        'gen_ai_response_model="qwen3.5:4b",} 2\n'
        'gen_ai_client_token_usage_count{gen_ai_backend="ignored",} 9\n'
    ).replace("\\n", "\n")
    assert _parse_router_metrics(text) == [
        {"backend": "bestiary/ollama-main", "asked_for": "qwen3.5:35b", "answered_by": "qwen3.5:35b", "requests": 1},
        {"backend": "bestiary/ollama-small", "asked_for": "qwen3.5:35b", "answered_by": "qwen3.5:4b", "requests": 2},
    ]


def _goose_ctx(buf, monkeypatch, new_cli_text):
    """Encounter 5 with goose stubbed: it 'edits' farolito/cli.py to new_cli_text."""
    import json as _json
    import shutil as _shutil

    from bestiary import encounters
    from bestiary.config import WORK_DIR
    from bestiary.llm import Provider

    monkeypatch.setattr(encounters.shutil, "which", lambda name: "/usr/bin/goose" if name == "goose" else _shutil.which(name))
    issue = {"number": 7, "title": "Traceback when the config file is missing", "body": "Expected a one-line error and exit 2."}

    async def fake_call(url, name, args):
        return False, _json.dumps(issue)

    def fake_stream(cmd, cwd, env, timeout, ctx):
        (WORK_DIR / "farolito" / "cli.py").write_text(new_cli_text, encoding="utf-8")
        return 0, ["goose | done"]

    monkeypatch.setattr(encounters, "_mcp_call", fake_call)
    monkeypatch.setattr(encounters, "_stream", fake_stream)
    ctx = _auto_ctx(buf, monkeypatch)
    ctx.detection = Detection(Provider("ollama", "http://x/v1", "m"), [])
    return ctx


def test_encounter_5_is_not_live_when_goose_breaks_the_tests(monkeypatch, fresh_workspace):
    import subprocess as sp
    import sys as _sys

    from bestiary import encounters
    from bestiary.config import UPSTREAM_TEMPLATE, WORK_DIR

    original = (UPSTREAM_TEMPLATE / "farolito" / "cli.py").read_text(encoding="utf-8")
    plausible_but_wrong = original.replace(
        '    with open(path, "rb") as fh:\n        return tomllib.load(fh)\n',
        '    try:\n        with open(path, "rb") as fh:\n            return tomllib.load(fh)\n'
        '    except FileNotFoundError:\n        print(f"farolito: config file not found: {path}", file=sys.stderr)\n        sys.exit(2)\n',
    )
    assert plausible_but_wrong != original
    buf = io.StringIO()
    encounters.e5_bug(_goose_ctx(buf, monkeypatch, plausible_but_wrong))
    out = buf.getvalue()
    assert "tests still fail" in out and "known-good fix" in out
    after = sp.run([_sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=WORK_DIR, capture_output=True, text=True)
    assert after.returncode == 0  # the story continues with a fix that works


def test_encounter_5_is_live_when_goose_really_fixes_it(monkeypatch, fresh_workspace):
    from bestiary import encounters
    from bestiary.config import REFERENCE_FIX

    buf = io.StringIO()
    encounters.e5_bug(_goose_ctx(buf, monkeypatch, REFERENCE_FIX.read_text(encoding="utf-8")))
    out = buf.getvalue()
    assert "tests still fail" not in out and "known-good fix" not in out
    assert "LIVE" in out and "pytest on goose's change" in out
