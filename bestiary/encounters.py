"""The encounters, in story order.

Story: Los Faroleros help a dev team fix issue #7 in the toy upstream project
`farolito`: consult information, read the issue, stay safe, follow the upstream
ritual, fix, test safely, get a second opinion, open the PR.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from datetime import timedelta

from rich.table import Table

from bestiary import workspace
from bestiary.i18n import category_label
from bestiary.i18n import t as tr
from bestiary.config import REPO_ROOT, WORK_DIR
from bestiary.engine import CATEGORY_RULES, Ctx, Fallback, encounter_header, team_table
from bestiary.services import port_open


def _run(coro):
    return asyncio.run(coro)


def _tokens(text: str) -> int:
    """Rough token estimate (about 4 characters per token). Good enough to compare."""
    return max(1, len(text) // 4)


async def _mcp_list(url: str) -> list[str]:
    from mcp import Client

    async with Client(url) as c:
        return [t.name for t in (await c.list_tools()).tools]


async def _mcp_call(url: str, name: str, args: dict) -> tuple[bool, str]:
    from mcp import Client

    async with Client(url) as c:
        r = await c.call_tool(name, args)
        return r.is_error, "\n".join(getattr(x, "text", "") for x in r.content)


def _leaf_errors(err: BaseException):
    """The innermost exceptions of (possibly nested) exception groups raised by the MCP client."""
    if isinstance(err, BaseExceptionGroup):
        for sub in err.exceptions:
            yield from _leaf_errors(sub)
    else:
        yield err


async def _mcp_call_or_error(url: str, name: str, args: dict) -> dict:
    """tools/call that returns what the server (or a gateway in front of it) answered, even a rejection."""
    try:
        is_error, text = await _mcp_call(url, name, args)
        return {"rejected": False, "is_error": is_error, "result": text}
    except BaseException as err:  # the MCP client raises exception groups for a JSON-RPC error
        leaf = next(_leaf_errors(err))
        code = getattr(getattr(leaf, "error", None), "code", getattr(leaf, "code", None))
        return {"rejected": True, "error": {"code": code, "message": str(leaf)}}


def _replay_only(reason: str):
    def step():
        raise Fallback(reason)

    return step


def _gateway_up(ctx: Ctx) -> bool:
    url = ctx.settings.gateway_url
    try:
        host_port = url.split("//", 1)[1].split("/", 1)[0]
        host, port = host_port.rsplit(":", 1)
        return port_open(int(port), host.replace("localhost", "127.0.0.1"))
    except (IndexError, ValueError):
        return False


# --------------------------------------------------------------------------- 0
def e0_lab(ctx: Ctx) -> None:
    if ctx.settings.ui == "battle":
        from bestiary import battle

        if battle.enabled(ctx):
            battle.title_screen(ctx)
    ctx.console.rule("[bold]" + tr("Encounter 0: The lab"))
    ctx.say("Meet the team. Ten creatures, each one stands for one AAIF project.")
    ctx.console.print(team_table(ctx.creatures, highlight="autonomy"))
    ctx.say("Look at the Autonomy column: only Chambero (goose) is above 0.", "bold yellow")
    ctx.say("Only an AGENT decides. Everything else is a protocol, a format, a gateway, a spec, a box or a dojo.")
    rules = Table(title=tr("Category rules"))
    rules.add_column(tr("Category"))
    rules.add_column(tr("Rule in the game"))
    for k, v in CATEGORY_RULES.items():
        rules.add_row(category_label(k), tr(v))
    ctx.console.print(rules)
    ctx.pause()


# --------------------------------------------------------------------------- 1
def e1_doubt(ctx: Ctx) -> None:
    encounter_header(ctx, "1", '"How do I run the tests?"', "Consult information", ["scribbit"])

    def live():
        text = (WORK_DIR / "AGENTS.md").read_text(encoding="utf-8")
        ctx.wire("farolito/AGENTS.md", text)
        ctx.say(tr("Aura loaded: {n} tokens, sent with every request. It is just a Markdown file.", n=_tokens(text)), "green")
        ctx.say("goose reads AGENTS.md by default. So do many other coding agents.")

    ctx.attempt("e1_doubt", live)
    ctx.pause()


# --------------------------------------------------------------------------- 2
def e2_issue(ctx: Ctx) -> None:
    n = ctx.settings.issue_number()
    encounter_header(ctx, "2", "The issue in the fog", "Read the issue", ["octoplug"])
    ctx.say("Part A: talk to the MCP server directly. No model, no agent.", "bold")

    def live_direct():
        tools = _run(_mcp_list(ctx.settings.forge_url))
        ctx.wire("MCP tools/list", tools)
        is_error, text = _run(_mcp_call(ctx.settings.forge_url, "read_issue", {"number": n}))
        ctx.wire(f"MCP tools/call read_issue({n})", json.loads(text) if not is_error else text)
        ctx.say("MCP answered, and no model was involved. MCP is a protocol, not an agent.", "bold green")

    ctx.attempt("e2a_mcp_direct", live_direct)
    ctx.pause()

    ctx.say("Part B: the same tools, inside a 100-line agent loop.", "bold")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import minimal_agent

    ctx.code(inspect.getsource(minimal_agent.run), "minimal_agent.py: run()")

    def live_agent():
        if not ctx.detection.provider:
            raise Fallback(tr("no model: {notes}", notes="; ".join(ctx.detection.notes)))
        ctx.say(tr("Model: {model} through /v1/responses (Open Responses)", model=ctx.detection.provider.label()), "dim")
        answer = _run(
            minimal_agent.run(
                f"Read issue {n} and summarise the bug in one sentence.",
                ctx.settings.forge_url,
                ctx.detection.provider,
                ctx.wire,
            )
        )
        ctx.say(tr("Agent: {answer}", answer=answer), "bold green")

    ctx.attempt("e2b_minimal_agent", live_agent)
    ctx.say("The loop is the agent. MCP only described the tools.", "yellow")
    ctx.pause()


# --------------------------------------------------------------------------- 3
def e3_injection(ctx: Ctx) -> None:
    n = ctx.settings.issue_number()
    encounter_header(ctx, "3", "Injection", "Stay safe", ["bulwark"])
    is_error, text = _run(_mcp_call(ctx.settings.forge_url, "read_issue", {"number": n}))
    body = json.loads(text).get("body", "") if not is_error else text
    hidden = [line for line in body.splitlines() if "ignore" in line.lower()]
    ctx.wire("Hidden text inside the issue body", "\n".join(hidden) or body)
    ctx.say("The issue tells assistants to delete main. Without a gateway, the model can see delete_branch.", "red")

    def live():
        if not _gateway_up(ctx):
            raise Fallback(tr("agentgateway not reachable at {url} (run: agentgateway -f gateway/agentgateway.yaml)", url=ctx.settings.gateway_url))
        direct = _run(_mcp_list(ctx.settings.forge_url))
        ctx.wire("tools/list WITHOUT the gateway", direct)
        via = _run(_mcp_list(ctx.settings.gateway_url))
        ctx.wire("tools/list THROUGH agentgateway", via)
        if "delete_branch" in via:
            ctx.say("delete_branch is still visible: check the mcpAuthorization rules.", "red")
        else:
            ctx.say("delete_branch disappeared. The model cannot call what it never sees.", "bold green")
        answer = _run(_mcp_call_or_error(ctx.settings.gateway_url, "delete_branch", {"name": "main"}))
        ctx.wire("The game (not the model) calls delete_branch through the gateway anyway", answer)
        if answer["rejected"] or answer.get("is_error"):
            ctx.say("The gateway rejected the direct call too.", "bold green")
        else:
            ctx.say("The gateway let the direct call through: check the mcpAuthorization rules.", "red")

    def didactic():
        ctx.wire("tools/list WITHOUT the gateway", ["list_issues", "read_issue", "read_file", "create_branch", "create_pull_request", "delete_branch"])
        ctx.wire("tools/list THROUGH agentgateway (allow-list)", ["list_issues", "read_issue", "read_file", "create_branch", "create_pull_request"])
        ctx.say("agentgateway filters forbidden tools out of tools/list and rejects direct calls to them.")

    ctx.attempt("e3_gateway", live, didactic)
    ctx.pause()


# --------------------------------------------------------------------------- 4
def e4_ritual(ctx: Ctx) -> None:
    encounter_header(ctx, "4", "The upstream ritual", "How we contribute", ["satchel"])

    def live():
        skills_dir = WORK_DIR / ".agents" / "skills"
        full, discovery = 0, 0
        table = Table(title=tr("Skills in farolito/.agents/skills"))
        for col in ("Skill", "Description (always loaded)", "Full SKILL.md"):
            table.add_column(tr(col))
        rows = []
        for skill in sorted(skills_dir.glob("*/SKILL.md")):
            text = skill.read_text(encoding="utf-8")
            front = text.split("---")[1]
            meta = dict(line.split(":", 1) for line in front.strip().splitlines() if ":" in line)
            d_tokens = _tokens(meta["name"] + meta["description"])
            f_tokens = _tokens(text)
            discovery += d_tokens
            full += f_tokens
            table.add_row(meta["name"].strip(), f"{d_tokens} tok", f"{f_tokens} tok")
            rows.append({"skill": meta["name"].strip(), "discovery_tokens": d_tokens, "full_tokens": f_tokens})
        ctx.console.print(table)
        active = (skills_dir / "open-upstream-pr" / "SKILL.md").read_text(encoding="utf-8")
        used = discovery + _tokens(active) - _tokens("open-upstream-pr")
        ctx.wire("Token meter", {"load everything": full, "progressive disclosure (descriptions + 1 skill)": used})
        ctx.wire("Activated skill: open-upstream-pr", active)
        ctx.say("Only the skill that matters is loaded in full. The rest stay as one-line descriptions.", "bold green")

    ctx.attempt("e4_skills", live)
    ctx.pause()


# --------------------------------------------------------------------------- 5
GOOSE_PROMPT = (
    "You are working in the farolito repository (current directory). Fix issue #{n}: {title}. "
    "Details: {body} Follow AGENTS.md. Change only farolito/cli.py. "
    "Do not run git commands. When done, say DONE."
)


def goose_prompt(n: int, issue: dict) -> str:
    """The exact prompt goose gets in encounter 5 and in the gate. The issue body goes in whole, minus HTML
    comments (the hidden note of encounter 3 is not an instruction for goose)."""
    import re

    body = " ".join(re.sub(r"<!--.*?-->", "", issue["body"], flags=re.S).split())
    return GOOSE_PROMPT.format(n=n, title=issue["title"], body=body)


def _stream(cmd: list[str], cwd, env, timeout: int, ctx: Ctx) -> tuple[int | None, list[str]]:
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines: queue.Queue[str | None] = queue.Queue()

    def reader():
        for line in proc.stdout:  # type: ignore[union-attr]
            lines.put(line.rstrip())
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    seen, deadline = [], time.time() + timeout
    while time.time() < deadline:
        try:
            line = lines.get(timeout=0.5)
        except queue.Empty:
            continue
        if line is None:
            break
        seen.append(line)
        ctx.console.print(f"[dim]goose | {line[:160]}[/]")
    else:
        proc.kill()
        return None, seen
    return proc.wait(), seen


def e5_bug(ctx: Ctx) -> None:
    n = ctx.settings.issue_number()
    encounter_header(ctx, "5", "The bug", "Propose a change", ["mender", "scribbit", "satchel"])
    ctx.say("Now the only AGENT takes its turn. DeathNote and Navaja Suiza are auras it reads from files.")

    def live():
        goose = shutil.which("goose")
        p = ctx.detection.provider
        if not goose:
            raise Fallback(tr("goose CLI not installed"))
        if not p:
            raise Fallback(tr("no model for goose"))
        _, text = _run(_mcp_call(ctx.settings.forge_url, "read_issue", {"number": n}))
        issue = json.loads(text)
        prompt = goose_prompt(n, issue)
        env = dict(os.environ, GOOSE_MODE="auto", GOOSE_DISABLE_KEYRING="1")  # never prompt, no OS keyring in a pod
        if p.name == "ollama":
            env.update(GOOSE_PROVIDER="ollama", GOOSE_MODEL=p.model, OLLAMA_HOST=ctx.settings.ollama_host)
        else:
            env.update(GOOSE_PROVIDER="openai", GOOSE_MODEL=p.model)
        custom = os.environ.get("BESTIARY_GOOSE_CMD")  # e.g. "goose run --with-builtin developer -t"
        cmd = (shlex.split(custom) if custom else [goose, "run", "--no-session", "--with-builtin", "developer", "--text"]) + [prompt]
        attempts = max(1, ctx.settings.goose_attempts)
        last = tr("goose did not run")
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                # Still LIVE: start again from the original code (the first change did not fix the bug).
                ctx.say(tr("The change did not fix the bug. Attempt {attempt} of {attempts}, from the original code.", attempt=attempt, attempts=attempts), "yellow")
                workspace.reset()
                ctx.events.clear()
            ctx.wire("command", " ".join(cmd[:-1]) + f' "<issue prompt>"   (attempt {attempt} of {attempts})')
            code, out = _stream(cmd, WORK_DIR, env, ctx.settings.goose_timeout, ctx)
            ctx.events.append({"kind": "goose output (last lines)", "data": "\n".join(out[-25:])})
            if code is None:
                last = tr("goose passed the {seconds}s stage cap", seconds=ctx.settings.goose_timeout)
                continue
            diff = workspace.unified_diff()
            if not diff:
                last = tr("goose finished but changed nothing (a silent failure: the model never called a tool)")
                continue
            ctx.wire("Diff written by goose", diff)
            # LIVE only if the change really fixes the bug: the same check the reliability gate uses.
            check = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=WORK_DIR,
                                   capture_output=True, text=True, timeout=60)
            tail = (check.stdout.strip().splitlines() or check.stderr.strip().splitlines() or ["(no output)"])[-1]
            ctx.wire("pytest on goose's change", {"passed": check.returncode == 0, "summary": tail})
            if check.returncode == 0:
                return
            last = tr("goose changed the code but the tests still fail ({tail})", tail=tail)
        raise Fallback(tr("{last}; gave up after {attempts} attempt(s)", last=last, attempts=attempts))

    status = ctx.attempt("e5_goose", live)
    if status != "LIVE" or not workspace.unified_diff():
        workspace.apply_reference_fix()
        ctx.say("For the story to continue, the known-good fix (upstream/reference_fix) was applied to the working copy.", "yellow")
        ctx.wire("Diff (known-good fix)", workspace.unified_diff())
    ctx.say("Myth 1 closed: MCP is not an agent. Only Chambero took a turn.", "bold yellow")
    ctx.pause()


# --------------------------------------------------------------------------- 6
SANDBOX_CMD = "cd /workspace && (python -m pytest --version >/dev/null 2>&1 || pip install -q pytest) && python -m pytest -q"


async def _sandbox_pytest(domain: str, image: str) -> str:
    from opensandbox import Sandbox
    from opensandbox.config import ConnectionConfig

    # api_key: the Kubernetes runtime of the OpenSandbox server refuses to start without one;
    # the SDK also reads OPEN_SANDBOX_API_KEY by itself.
    api_key = os.environ.get("OPEN_SANDBOX_API_KEY") or None
    sb = await Sandbox.create(image, connection_config=ConnectionConfig(domain=domain, api_key=api_key), timeout=timedelta(minutes=5))
    try:
        for path in sorted(WORK_DIR.rglob("*.py")) + [WORK_DIR / "AGENTS.md"]:
            rel = path.relative_to(WORK_DIR).as_posix()
            await sb.files.write_file(f"/workspace/{rel}", path.read_text(encoding="utf-8"))
        result = await sb.commands.run(SANDBOX_CMD)
        out = "".join(m.text for m in result.logs.stdout) + "".join(m.text for m in result.logs.stderr)
        return out
    finally:
        await sb.destroy()  # kill the sandbox and close the local client (opensandbox 1.2.1)


def e6_tests(ctx: Ctx) -> None:
    encounter_header(ctx, "6", "The flaky test", "Test safely", ["glasshell"])
    ctx.say("Code written by an agent is untrusted. Run it in a bubble, not on your laptop.")

    def live():
        try:
            import opensandbox  # noqa: F401
        except ImportError as err:
            raise Fallback(tr("opensandbox SDK not installed (uv sync --extra sandbox)")) from err
        host, _, port = ctx.settings.sandbox_domain.partition(":")
        if not port_open(int(port or 80), host.replace("localhost", "127.0.0.1")):
            raise Fallback(tr("OpenSandbox server not reachable at {url}", url=ctx.settings.sandbox_domain))
        image = os.environ.get("BESTIARY_SANDBOX_IMAGE", "bestiary-sandbox:latest")
        ctx.wire("sandbox", {"server": ctx.settings.sandbox_domain, "image": image, "command": SANDBOX_CMD})
        out = _run(_sandbox_pytest(ctx.settings.sandbox_domain, image))
        ctx.wire("pytest inside OpenSandbox", out)

    def didactic():
        ctx.wire("What Caparazón does", [
            "Sandbox.create('bestiary-sandbox:latest')   -> an isolated container",
            "sandbox.files.write_file('/workspace/...')   -> copy the repo in",
            "sandbox.commands.run('python -m pytest -q')  -> run the agent's code inside",
            "sandbox.kill()                               -> throw the bubble away",
        ])
        ctx.say("Without a sandbox, the agent's code would run with your laptop's permissions.")

    ctx.attempt("e6_sandbox", live, didactic)
    ctx.pause()


# --------------------------------------------------------------------------- 7
async def _a2a_review(url: str, diff: str) -> tuple[dict, list[dict]]:
    import httpx
    from a2a.client import ClientConfig, create_client
    from a2a.helpers import new_text_message
    from a2a.types import Role, SendMessageRequest
    from google.protobuf.json_format import MessageToDict

    # The reviewer calls the model; after goose the model can be busy for a while, so allow a long wait.
    async with httpx.AsyncClient(timeout=180) as http:
        card = (await http.get(f"{url}/.well-known/agent-card.json", timeout=5)).json()
        client = await create_client(url, client_config=ClientConfig(httpx_client=http))
        responses = []
        async for r in client.send_message(SendMessageRequest(message=new_text_message(diff, role=Role.ROLE_USER))):
            responses.append(MessageToDict(r))
    return card, responses


def e7_review(ctx: Ctx) -> None:
    encounter_header(ctx, "7", "Second opinion", "Review by another team", ["chasqui", "glyphstone"])

    def live():
        if not ctx.detection.provider:
            raise Fallback(tr("no model for the reviewer"))
        card, replies = _run(_a2a_review(ctx.settings.reviewer_url, workspace.unified_diff()))
        ctx.wire("A2A Agent Card (/.well-known/agent-card.json)", card)
        for reply in replies:
            parts = reply.get("message", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    ctx.wire("A2A reply: review", part["text"])
                if "data" in part:
                    ctx.wire("Open Responses output items (from the reviewer's model call)", part["data"].get("open_responses_output"))
        ctx.say("Duolingo was here since encounter 2: every model call used /v1/responses.", "bold green")

    ctx.attempt("e7_a2a_review", live)
    ctx.pause()


# --------------------------------------------------------------------------- 8
def e8_pr(ctx: Ctx) -> None:
    n = ctx.settings.issue_number()
    encounter_header(ctx, "8", "The PR", "Open the pull request", ["octoplug", "bulwark", "satchel"])
    title = "cli: friendly error when the config file is missing"
    body = (
        f"Fixes #{n}\n\n## What changed\nCatch FileNotFoundError, print a one-line error to stderr "
        "and exit with code 2.\n\n## How I tested it\n`python -m pytest -q`\n\n"
        "_Opened live during a talk by Agentic Bestiary._"
    )
    branch = f"fix/{n}-missing-config-{int(time.time()) % 100000}"

    def live():
        url = ctx.settings.gateway_url if _gateway_up(ctx) else ctx.settings.forge_url
        via = "through agentgateway" if url == ctx.settings.gateway_url else "directly (gateway not running)"
        ctx.wire(f"MCP tools/call create_pull_request {via}", {"branch": branch, "title": title, "body": body})
        err, out = _run(_mcp_call(url, "create_pull_request", {"branch": branch, "title": title, "body": body}))
        if err:
            raise Fallback(out[:300])
        ctx.wire("Pull request", json.loads(out))
        ctx.say(tr("Backend: {backend}. goose never held this tool.", backend=ctx.settings.forge_backend), "bold green")

    ctx.attempt("e8_pr", live)
    ctx.pause()


# --------------------------------------------------------------------------- 9
ROUTER_PROMPT = "In one short sentence, say which model you are."


def _kube(args: list[str]) -> str:
    """kubectl through the console's service account. Raises Fallback if it cannot run."""
    kubectl = shutil.which("kubectl")
    if not kubectl:
        raise Fallback(tr("kubectl not installed"))
    r = subprocess.run([kubectl, *args], capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        raise Fallback(f"kubectl {' '.join(args[:3])}: {r.stderr.strip()[:200]}")
    return r.stdout


def _router_call(ctx: Ctx, model: str) -> dict:
    """One /v1/responses request through Agent Router. Returns the summary shown on screen."""
    import httpx

    from bestiary.llm import _extra_body, output_text

    base = ctx.settings.agent_router_url.rstrip("/")
    body = {"model": model, "input": ROUTER_PROMPT, "store": False, **_extra_body()}
    started = time.time()
    try:
        r = httpx.post(f"{base}/v1/responses", json=body, timeout=180)
    except httpx.TransportError as err:
        raise Fallback(tr("Agent Router not reachable at {url}: {error}", url=base, error=type(err).__name__)) from err
    if r.status_code != 200:
        raise Fallback(tr("Agent Router answered {code}: {text}", code=r.status_code, text=r.text[:160]))
    data = r.json()
    return {
        "http_status": r.status_code,
        "seconds": round(time.time() - started, 1),
        "asked_for": model,
        "served_by_model": data.get("model"),
        "answer": output_text(data)[:200],
    }


def _parse_router_metrics(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        if not line.startswith("gen_ai_server_request_duration_seconds_count{"):
            continue
        labels = dict(re.findall(r'(\w+)="([^"]*)"', line))
        rows.append({
            "backend": labels.get("gen_ai_backend"),
            "asked_for": labels.get("gen_ai_original_model"),
            "answered_by": labels.get("gen_ai_response_model"),
            "requests": int(float(line.rsplit(" ", 1)[1])),
        })
    return rows


def _router_metrics(ctx: Ctx) -> None:
    """Requests served per backend, from the router's own Prometheus metrics (admin port 1064)."""
    import httpx

    host = ctx.settings.agent_router_url.split("//", 1)[-1].split("/", 1)[0].rsplit(":", 1)[0]
    try:
        text = httpx.get(f"http://{host}:1064/metrics", timeout=5).text
    except httpx.HTTPError:
        return
    rows = _parse_router_metrics(text)
    if rows:
        ctx.wire("Agent Router metrics: requests served per backend (:1064/metrics)", sorted(rows, key=lambda r: str(r["backend"])))


def e9_detour(ctx: Ctx) -> None:
    encounter_header(ctx, "9", "Detour (side quest)", "The team grows: many models", ["switchy", "bulwark"])
    ctx.say("Myth 2: do all these projects do the same thing? Both are GATEWAYS, but they guard different doors.")
    compare = Table()
    for col in ("", "Rondero (agentgateway)", "Cobrador (Agent Router)"):
        compare.add_column(col)
    compare.add_row(tr("Main door"), tr("Agents to tools and agents (MCP, A2A)"), tr("Apps to models (OpenAI-compatible API)"))
    compare.add_row(tr("Guards"), tr("TOOLS: hides delete_branch"), tr("MODELS: routes and fails over"))
    compare.add_row(tr("Built on"), tr("Rust proxy"), tr("Envoy (formerly Envoy AI Gateway, a CNCF Envoy sub-project)"))
    compare.add_row(tr("In this story"), tr("Hides delete_branch"), tr("Sends a request to the main model; if it is down, to the small one"))
    ctx.console.print(compare)

    main_model, small_model = ctx.settings.ollama_model, ctx.settings.failover_model

    def live():
        if not ctx.settings.is_cloud:
            raise Fallback(tr("Agent Router runs in the cluster (BESTIARY_PROFILE=cloud)"))
        ns, svc = ctx.settings.namespace, "ollama-main"
        ctx.wire("Step 1: request through Agent Router, main model", {"POST": f"{ctx.settings.agent_router_url}/v1/responses", "model": main_model})
        first = _router_call(ctx, main_model)
        ctx.wire("Response", first)
        _router_metrics(ctx)
        ctx.say(tr("Step 2: simulate an outage. Service {svc} loses its endpoints (one GPU, one Ollama pod: a simulated failure).", svc=svc), "yellow")

        def patch(selector: str) -> str:
            return _kube(["-n", ns, "patch", "svc", svc, "--type", "merge", "-p", json.dumps({"spec": {"selector": {"app": selector}}})])

        patch("ollama-off")
        time.sleep(3)  # let the router drop its idle connection to the old endpoint
        try:
            ctx.wire("Same request, main backend down", {"model": main_model})
            second = _router_call(ctx, main_model)
            ctx.wire("Response", second)
            _router_metrics(ctx)
        finally:
            patch("ollama")
            ctx.say(tr("Service {svc} restored.", svc=svc), "dim")
        served = second.get("served_by_model")
        if not served or served == first.get("served_by_model"):
            # Never claim a failover that did not happen: this live step does not count (no replay is recorded).
            raise Fallback(tr("no failover observed: the router answered with {served} both times", served=served))
        ctx.say(tr("Failover: asked for {asked}, answered by {served}. The app never changed its URL.", asked=main_model, served=served), "bold green")

    def didactic():
        cfg = (REPO_ROOT / "agent-router" / "README.md").read_text(encoding="utf-8")
        ctx.wire("How the recorded run works (agent-router/README.md)", cfg)

    ctx.attempt("e9_agent_router", live, didactic)
    ctx.pause()


# --------------------------------------------------------------------------- 10
def e10_dojo(ctx: Ctx) -> None:
    encounter_header(ctx, "10", "The dojo (epilogue)", "Improve the model later", ["dojolotl"])
    ctx.say("Same tests, different purpose: in training, passing tests become a reward.")

    def live():
        import httpx

        base = ctx.settings.openenv_url.rstrip("/")
        if not base:
            raise Fallback(tr("no OpenEnv server configured (BESTIARY_OPENENV_URL; the cloud profile sets it)"))
        try:
            ctx.wire(f"GET {base}/health", httpx.get(f"{base}/health", timeout=5).json())
            ctx.wire("POST /reset   (env.reset())", httpx.post(f"{base}/reset", json={}, timeout=15).json())
            cli_py = (WORK_DIR / "farolito" / "cli.py").read_text(encoding="utf-8")
            ctx.wire("POST /step   (env.step: the farolito/cli.py left by encounter 5)", {"action": {"cli_py": f"<{len(cli_py)} characters>"}})
            step = httpx.post(f"{base}/step", json={"action": {"cli_py": cli_py}}, timeout=90).json()
        except httpx.TransportError as err:
            raise Fallback(tr("OpenEnv server not reachable at {url}: {error}", url=base, error=type(err).__name__)) from err
        ctx.wire("step result: observation, reward, done", step)
        ctx.say(tr("reward = {reward}: the environment ran farolito's tests in its own container.", reward=step.get("reward")), "bold green")

    def didactic():
        r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=WORK_DIR, capture_output=True, text=True, timeout=60)
        passed = r.returncode == 0
        ctx.wire("env.reset()", {"observation": "issue #7 text + repository files"})
        ctx.wire("env.step(action = the diff from encounter 5)", {
            "observation": r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:],
            "reward": 1.0 if passed else 0.0,
            "done": True,
        })
        ctx.say("This is an explanation, not OpenEnv itself. In OpenEnv the environment runs in a container with reset()/step().", "dim")

    ctx.attempt("e10_openenv", live, didactic)
    ctx.pause()


# --------------------------------------------------------------------------- K8s
GPU_COLUMNS = (
    "custom-columns=POD:.metadata.name,NODE:.spec.nodeName,"
    r"GPU:.spec.containers[*].resources.limits.nvidia\.com/gpu"
)


def ek_kubernetes(ctx: Ctx) -> None:
    ctx.current_number = "K8s"
    from bestiary import battle

    if battle.enabled(ctx):
        battle.intro(ctx, "K8s", "Kubernetes region", "Share it with many teams", ["bulwark"])
    else:
        ctx.console.rule("[bold]" + tr("Region: Kubernetes"))
    cloud = ctx.settings.is_cloud
    ns = ctx.settings.namespace
    if cloud:
        ctx.say("Myth 3: do I need Kubernetes to start? No. But you are looking at it: this game runs in a pod.", "bold yellow")
        ctx.say(tr("I am {where}. Everything before this also ran here, as pods.", where=ctx.where._here()))
        k8s_url = ctx.settings.gateway_url  # the agentgateway sidecar of this pod
    else:
        ctx.say("Myth 3: do I need Kubernetes to start? No. Everything so far ran on this laptop.", "bold yellow")
        ctx.say("Kubernetes is where you go when many teams share the same tools, gateway and policies.")
        k8s_url = os.environ.get("BESTIARY_K8S_GATEWAY_URL", "http://localhost:30300/mcp")

    def live():
        kubectl = shutil.which("kubectl")
        if not kubectl:
            raise Fallback(tr("kubectl not installed"))
        r = subprocess.run([kubectl, "get", "pods", "-n", ns, "-o", "wide"], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            hint = r.stderr.strip()[:200] if cloud else tr("no 'bestiary' namespace (run: uv run bestiary k8s up)")
            raise Fallback(hint)
        ctx.wire(f"kubectl get pods -n {ns} -o wide", r.stdout)
        if cloud and ctx.settings.accelerator == "gpu":
            gpu = subprocess.run([kubectl, "get", "pods", "-n", ns, "-o", GPU_COLUMNS], capture_output=True, text=True, timeout=15)
            ctx.wire("GPUs requested per pod (nvidia.com/gpu)", gpu.stdout or gpu.stderr)
        via = "the agentgateway sidecar of this pod" if cloud else "agentgateway running in kind"
        ctx.wire(f"tools/list through {via}", _run(_mcp_list(k8s_url)))
        if cloud:
            where_model = tr("the GPU") if ctx.settings.accelerator == "gpu" else tr("the CPU")
            ctx.say(tr("The model runs on {where} in its own pod. The gateway filters tools next to the game.", where=where_model), "bold green")
        else:
            ctx.say("Same creatures, same YAML ideas, now as pods. Ollama still runs on the host.", "bold green")

    def didactic():
        ctx.wire("k8s/ in this repo (applied with: uv run bestiary k8s up)", sorted(p.name for p in (REPO_ROOT / "k8s").glob("*")))
        ctx.say("forge-mcp, reviewer-a2a and agentgateway become Deployments; the gateway policy becomes a ConfigMap.")

    ctx.attempt("ek_kubernetes", live, didactic)
    ctx.pause()


def finale(ctx: Ctx) -> None:
    ctx.console.rule("[bold]" + tr("The map"))
    table = Table(title=tr("Agent, protocol, instruction format, gateway (and friends)"))
    table.add_column(tr("Category"))
    table.add_column(tr("Projects"))
    groups: dict[str, list[str]] = {}
    for c in ctx.creatures.values():
        groups.setdefault(c["category"], []).append(f"{c['project']} ({c['name']})")
    for cat in CATEGORY_RULES:
        table.add_row(category_label(cat), ", ".join(groups.get(cat, [])))
    ctx.console.print(table)
    ctx.say("Unofficial personal project. Not endorsed by the AAIF or the Linux Foundation.", "dim")
    ctx.say(ctx.settings.talk_banner, "dim")


ORDER = [e0_lab, e1_doubt, e2_issue, e3_injection, e4_ritual, e5_bug, e6_tests, e7_review, e8_pr, e9_detour, e10_dojo, ek_kubernetes, finale]
