"""The kustomize overlays render, and the ec2 one has the shape the talk relies on."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
KUBECTL = shutil.which("kubectl")
pytestmark = pytest.mark.skipif(not KUBECTL, reason="kubectl (for `kubectl kustomize`) not installed")


def render(overlay: str) -> list[dict]:
    out = subprocess.run([KUBECTL, "kustomize", str(ROOT / "k8s" / "overlays" / overlay)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return [d for d in yaml.safe_load_all(out.stdout) if d]


def by_kind(docs, kind):
    return {d["metadata"]["name"]: d for d in docs if d["kind"] == kind}


def containers(dep):
    return {c["name"]: c for c in dep["spec"]["template"]["spec"]["containers"]}


def test_kind_overlay_keeps_the_laptop_layout():
    deps = by_kind(render("kind"), "Deployment")
    assert set(deps) == {"agentgateway", "forge-mcp", "reviewer-a2a"}
    rev = containers(deps["reviewer-a2a"])["reviewer-a2a"]
    env = {e["name"]: e.get("value") for e in rev["env"]}
    assert env["OLLAMA_HOST"] == "http://host.docker.internal:11434" and env["BESTIARY_MODEL"]


def test_ec2_overlay_has_every_workload():
    docs = render("ec2")
    assert set(by_kind(docs, "Deployment")) == {"ollama", "agent-router", "openenv-farolito", "console", "reviewer-a2a"}
    assert set(by_kind(docs, "Service")) >= {"ollama", "ollama-main", "ollama-small", "agent-router", "openenv-farolito", "reviewer-a2a"}
    assert "ollama-pull" in by_kind(docs, "Job")


def test_console_pod_shares_one_working_copy_between_game_forge_and_gateway_sidecar():
    dep = by_kind(render("ec2"), "Deployment")["console"]
    c = containers(dep)
    assert set(c) == {"console", "forge", "agentgateway"}
    vols = {v["name"]: v for v in dep["spec"]["template"]["spec"]["volumes"]}
    assert "emptyDir" in vols["state"]
    for name in ("console", "forge"):  # game, forge and goose (in console) see the same /state
        assert {"name": "state", "mountPath": "/state"} in c[name]["volumeMounts"]
        env = {e["name"]: e.get("value") for e in c[name]["env"]}
        assert env["BESTIARY_STATE_DIR"] == "/state" and env["BESTIARY_PROFILE"] == "cloud"
    assert c["agentgateway"]["ports"] == [{"containerPort": 3000}]
    cfg = yaml.safe_load(by_kind(render("ec2"), "ConfigMap")["agentgateway-config"]["data"]["config.yaml"])
    assert cfg["mcp"]["port"] == 3000 and cfg["mcp"]["targets"][0]["mcp"]["host"] == "http://127.0.0.1:8765/mcp"
    rules = cfg["mcp"]["policies"]["mcpAuthorization"]["rules"]
    assert not any("delete_branch" in r for r in rules) and len(rules) == 5


def test_only_ollama_requests_the_gpu():
    for dep in by_kind(render("ec2"), "Deployment").values():
        for name, c in containers(dep).items():
            gpu = c.get("resources", {}).get("limits", {}).get("nvidia.com/gpu")
            assert (gpu == 1) == (dep["metadata"]["name"] == "ollama"), f"{dep['metadata']['name']}/{name}"
    ollama = by_kind(render("ec2"), "Deployment")["ollama"]
    assert ollama["spec"]["template"]["spec"]["runtimeClassName"] == "nvidia"


def test_console_rbac_is_read_only_plus_one_service_patch():
    docs = render("ec2")
    for role in by_kind(docs, "Role").values():
        for rule in role["rules"]:
            if role["metadata"]["name"] == "console-read":
                assert set(rule["verbs"]) <= {"get", "list", "watch"}
                assert "secrets" not in rule["resources"]
            else:
                assert rule["verbs"] == ["patch"] and rule["resourceNames"] == ["ollama-main"] and rule["resources"] == ["services"]


def test_the_failover_trigger_matches_the_game_and_the_router_config():
    """Encounter 9 patches Service ollama-main; the router must use it as priority 0."""
    docs = render("ec2")
    router_cfg = list(yaml.safe_load_all(by_kind(docs, "ConfigMap")["aigw-config"]["data"]["config.yaml"]))
    route = next(d for d in router_cfg if d["kind"] == "AIGatewayRoute")
    refs = route["spec"]["rules"][0]["backendRefs"]
    assert [(r["name"], r["priority"]) for r in refs] == [("ollama-main", 0), ("ollama-small", 1)]
    assert "FAILOVER_MODEL" in refs[1]["modelNameOverride"]
    assert by_kind(docs, "Service")["ollama-main"]["spec"]["selector"] == {"app": "ollama"}


def test_no_secret_material_in_the_repo():
    pattern = re.compile(r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})")
    for base in ("k8s", "infra", "envs", "docker", "gateway", "bestiary"):
        for path in (ROOT / base).rglob("*"):
            if path.is_file() and path.suffix in {".yaml", ".yml", ".sh", ".ps1", ".py", ".toml", ".md", ""}:
                assert not pattern.search(path.read_text(encoding="utf-8", errors="ignore")), path


def test_cpu_overlay_is_the_ec2_stack_without_any_gpu():
    cpu, gpu = render("ec2-cpu"), render("ec2")
    assert set(by_kind(cpu, "Deployment")) == set(by_kind(gpu, "Deployment"))
    ollama = by_kind(cpu, "Deployment")["ollama"]["spec"]["template"]["spec"]
    assert "runtimeClassName" not in ollama
    for dep in by_kind(cpu, "Deployment").values():
        for c in containers(dep).values():
            assert "nvidia.com/gpu" not in c.get("resources", {}).get("limits", {})
    env = {e["name"]: e["value"] for e in ollama["containers"][0]["env"]}
    assert env["OLLAMA_KEEP_ALIVE"] == "-1" and env["OLLAMA_CONTEXT_LENGTH"] == "16384"
