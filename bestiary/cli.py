"""Command line: uv run bestiary [play|doctor|record|services|github-setup|sprites|k8s]."""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from bestiary import workspace
from bestiary.config import REPO_ROOT, settings
from bestiary.engine import Ctx, load_creatures
from bestiary.llm import detect
from bestiary.services import port_open, running_services


def _ctx(console: Console, **kw) -> Ctx:
    return Ctx(console=console, settings=settings(), detection=detect(), creatures=load_creatures(), **kw)


def cmd_play(args: argparse.Namespace) -> int:
    from bestiary.encounters import ORDER

    console = Console(force_terminal=None if not args.auto else True, width=args.width)
    if not args.no_reset:
        workspace.reset()
    ctx = _ctx(console, auto=args.auto, replay_only=args.replay_only, record=args.record)
    console.print(f"[bold]Agentic Bestiary[/]  [dim]{ctx.settings.talk_banner}[/]")
    p = ctx.detection.provider
    console.print(f"[dim]model: {p.label() if p else 'none (replay mode for model steps)'}  forge: {ctx.settings.forge_backend}[/]")
    steps = ORDER[args.start:] if args.only is None else [ORDER[args.only]]
    with running_services():
        for step in steps:
            step(ctx)
    return 0


def _host_port(url: str, default_port: int = 80) -> tuple[str, int]:
    """host and port of 'http://host:port/path' or 'host:port'."""
    hostport = url.split("//", 1)[-1].split("/", 1)[0]
    host, _, port = hostport.partition(":")
    return host.replace("localhost", "127.0.0.1"), int(port or default_port)


def _reachable(url: str) -> bool:
    try:
        host, port = _host_port(url)
        return port_open(port, host)
    except ValueError:
        return False


def cmd_doctor(_: argparse.Namespace) -> int:
    s = settings()
    d = detect(s)
    t = Table(title=f"bestiary doctor (profile: {s.profile})")
    t.add_column("Check")
    t.add_column("Status")
    t.add_column("Unlocks")

    def row(name, ok, unlocks, note=""):
        t.add_row(name, ("[green]ok[/] " if ok else "[yellow]missing[/] ") + note, unlocks)

    row("Python + uv", True, "game, MCP, A2A, AGENTS.md, Skills", sys.version.split()[0])
    row("Model", bool(d.provider), "agent loop, reviewer, goose", d.provider.label() if d.provider else "; ".join(d.notes))
    row("goose", bool(shutil.which("goose")), "encounter 5 live")
    if s.is_cloud:
        # Services are other pods or sidecars: check that they answer, not that binaries exist.
        row("forge MCP", _reachable(s.forge_url), "encounters 2, 3, 8", s.forge_url)
        row("agentgateway (sidecar)", _reachable(s.gateway_url), "encounters 3 and 8", s.gateway_url)
        row("reviewer A2A", _reachable(s.reviewer_url), "encounter 7 live", s.reviewer_url)
        row("Agent Router", _reachable(s.agent_router_url), "encounter 9 live", s.agent_router_url)
        row("OpenSandbox server", _reachable(s.sandbox_domain), "encounter 6 live", s.sandbox_domain)
        row("OpenEnv environment", _reachable(s.openenv_url), "encounter 10 live", s.openenv_url)
        row("kubectl (read access)", bool(shutil.which("kubectl")), "Kubernetes region")
    else:
        row("agentgateway", bool(shutil.which("agentgateway")), "encounter 3 live")
        row("gateway listening", _reachable(s.gateway_url), "encounters 3 and 8", s.gateway_url)
        row("Docker", bool(shutil.which("docker")), "OpenSandbox, kind")
        row("OpenSandbox server", _reachable(s.sandbox_domain), "encounter 6 live", s.sandbox_domain)
        row("kind + kubectl", bool(shutil.which("kind") and shutil.which("kubectl")), "Kubernetes region")
        row("aigw (Agent Router)", bool(shutil.which("aigw")), "record encounter 9 (Linux/macOS)")
    gh_ok = s.forge_backend != "github" or bool(s.github_repo and s.github_token)
    row("Forge backend", gh_ok, "encounter 8", s.forge_backend + (f" {s.github_repo}" if s.github_repo else ""))
    Console().print(t)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    args.auto, args.replay_only, args.record = True, False, True
    return cmd_play(args)


def cmd_services(_: argparse.Namespace) -> int:
    console = Console()
    s = settings()
    workspace.ensure()
    with running_services():
        console.print(f"forge MCP: {s.forge_url}\nreviewer A2A: {s.reviewer_url}\nCtrl+C to stop.")
        try:
            import time

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return 0


def cmd_github_setup(args: argparse.Namespace) -> int:
    from bestiary.github_setup import setup

    return setup(args.repo, private=not args.public)


def cmd_sprites(args: argparse.Namespace) -> int:
    from bestiary.sprites import SPRITES, export_png, render

    console = Console()
    if args.out:
        for p in export_png(Path(args.out), args.pixel):
            console.print(f"wrote {p}")
        return 0
    creatures = load_creatures()
    for sid in SPRITES:
        console.print(render(sid, args.scale))
        console.print(f"[bold]{creatures[sid]['name']}[/] stands for {creatures[sid]['project']}\n")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    from bestiary.gate import run_gate

    return run_gate(args.runs, args.goose)


def cmd_k8s(args: argparse.Namespace) -> int:
    k8s = REPO_ROOT / "k8s"
    steps = {
        "up": [
            ["kind", "create", "cluster", "--name", "bestiary", "--config", str(k8s / "overlays" / "kind" / "kind-cluster.yaml")],
            ["docker", "build", "--target", "services", "-t", "bestiary-services:dev", "-f", str(k8s / "Dockerfile"), str(REPO_ROOT)],
            ["kind", "load", "docker-image", "bestiary-services:dev", "--name", "bestiary"],
            ["kubectl", "apply", "-k", str(k8s / "overlays" / "kind")],
            ["kubectl", "-n", "bestiary", "rollout", "status", "deploy/forge-mcp", "--timeout=180s"],
            ["kubectl", "-n", "bestiary", "rollout", "status", "deploy/agentgateway", "--timeout=180s"],
        ],
        "down": [["kind", "delete", "cluster", "--name", "bestiary"]],
    }[args.action]
    for cmd in steps:
        Console().print(f"[dim]$ {' '.join(cmd)}[/]")
        if subprocess.run(cmd).returncode != 0:
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    for noisy in ("httpx", "httpcore", "mcp", "a2a", "uvicorn"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles and pipes
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="bestiary", description="Agentic Bestiary: a map of the AAIF projects as a terminal game.")
    sub = parser.add_subparsers(dest="cmd")

    def play_args(p):
        p.add_argument("--auto", action="store_true", help="no key presses")
        p.add_argument("--replay-only", action="store_true", help="never run live steps")
        p.add_argument("--start", type=int, default=0, help="start at encounter index")
        p.add_argument("--only", type=int, help="run a single encounter index")
        p.add_argument("--no-reset", action="store_true", help="keep the current working copy")
        p.add_argument("--width", type=int, default=None)
        p.add_argument("--record", action="store_true", help="save live runs to replays/")

    play_args(sub.add_parser("play", help="play the game (default)"))
    play_args(sub.add_parser("record", help="run every encounter live and save replays"))
    sub.add_parser("doctor", help="what is installed and what it unlocks")
    sub.add_parser("services", help="run the forge MCP and reviewer A2A servers")
    g = sub.add_parser("github-setup", help="create the farolito demo repo and issue on GitHub")
    g.add_argument("repo", help="owner/name, for example mgonzalezo/farolito-demo")
    g.add_argument("--public", action="store_true")
    sp = sub.add_parser("sprites", help="show sprites or export PNGs")
    sp.add_argument("--out")
    sp.add_argument("--pixel", type=int, default=24)
    sp.add_argument("--scale", type=int, default=1)
    gt = sub.add_parser("gate", help="reliability gate: run model steps N times")
    gt.add_argument("--runs", type=int, default=50)
    gt.add_argument("--goose", action="store_true", help="also gate goose (slow)")
    k = sub.add_parser("k8s", help="create or delete the kind cluster")
    k.add_argument("action", choices=["up", "down"])

    args = parser.parse_args(argv)
    if args.cmd is None:
        args = parser.parse_args(["play", *(argv or sys.argv[1:])])
    handler = {
        "play": cmd_play, "record": cmd_record, "doctor": cmd_doctor, "services": cmd_services,
        "github-setup": cmd_github_setup, "sprites": cmd_sprites, "k8s": cmd_k8s, "gate": cmd_gate,
    }[args.cmd]
    return handler(args) or 0


if __name__ == "__main__":
    sys.exit(main())
