"""Pokemon-style battle screens for the encounters (BESTIARY_UI=battle, or --ui battle).

Every encounter is a battle: your creature against the obstacle of the story. The creature's skills (from
creatures.yaml) are the menu, and the skill it "uses" is the real call that follows, with its raw output
and its LIVE / REPLAY / DIDACTIC badge underneath. The scene is static (no animation): it survives a slow
SSM session and the streaming output of goose. The classic screens stay the default.
"""

from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bestiary import sprites

try:  # the opponent art lives in its own module
    from bestiary.opponents import NAMES, OPPONENTS
except ImportError:  # pragma: no cover - only while the art is missing
    NAMES, OPPONENTS = {}, {}

INK = "#1b1b2f"
CREAM = "#f4f1e4"
SCENE = f"{INK} on {CREAM}"
MIN_WIDTH = 100

# encounter number -> opponent id
OPPONENT_OF = {"1": "doubt", "2": "fog", "3": "injection", "4": "ritual", "5": "bug", "6": "flaky",
               "7": "review", "8": "gate", "9": "detour", "10": "dojo", "K8s": "cluster"}

# attempt id (the first argument of Ctx.attempt) -> (creature id, skill index, what that move achieved)
MOVES = {
    "e1_doubt": ("scribbit", 0, "A plain Markdown file answered the question."),
    "e2a_mcp_direct": ("octoplug", 0, "MCP answered with no model and no agent."),
    "e2b_minimal_agent": ("octoplug", 1, "The loop is the agent; MCP only described the tools."),
    "e3_gateway": ("bulwark", 0, "delete_branch vanished from the list, and direct calls are rejected."),
    "e4_skills": ("satchel", 1, "Only the skill that matters was loaded in full."),
    "e5_goose": ("mender", 1, "The only agent took its turn and edited the code."),
    "e6_sandbox": ("glasshell", 1, "The code ran inside a throwaway bubble."),
    "e7_a2a_review": ("chasqui", 1, "Another team's agent reviewed the change."),
    "e8_pr": ("octoplug", 1, "The pull request went through the gateway."),
    "e9_agent_router": ("switchy", 1, "The request found another route."),
    "e10_openenv": ("dojolotl", 2, "The tests became a reward."),
    "ek_kubernetes": ("bulwark", 2, "Every pod of the team is in sight."),
}


def enabled(ctx) -> bool:
    return getattr(ctx.settings, "ui", "classic") == "battle" and ctx.console.width >= MIN_WIDTH


def _on_platform(art: RenderableType) -> RenderableType:
    """A sprite standing on a flat 'ground' strip."""
    ground = Text("▀" * 16, style="#c9c3a6", justify="left")
    return Group(art, ground)


def _opponent(number: str) -> tuple[str, list[str]]:
    oid = OPPONENT_OF.get(number, "doubt")
    rows = OPPONENTS.get(oid) or ["................"] * 16
    return NAMES.get(oid, oid.upper()).upper(), rows


def _bar(label: str, frac: float, width: int = 18) -> Text:
    frac = max(0.0, min(1.0, frac))
    color = "#2e9e5b" if frac > 0.5 else "#e0a526" if frac > 0.2 else "#d1495b"
    filled = round(frac * width)
    t = Text(f"{label} ", style=f"bold {INK}", justify="left")
    t.append("█" * filled, style=color)
    t.append("░" * (width - filled), style="#b8b4a0")
    return t


def _pips(label: str, value: int) -> Text:
    t = Text(f"{label} ", style=f"bold {INK}", justify="left")
    t.append("■" * value, style="#5765ff")
    t.append("□" * (5 - value), style="#b8b4a0")
    return t


def _box(*lines: RenderableType, width: int) -> Panel:
    return Panel(Group(*lines), width=width, border_style=INK, style=SCENE, padding=(0, 1))


def _opponent_box(name: str, number: str, frac: float, weak_to: str, width: int = 44) -> Panel:
    title = Text(name, style=f"bold {INK}", justify="left")
    title.append(f"   Lv{number}" if number.isdigit() else f"   {number}", style="#59595f")
    lines = [title, _bar("HP", frac)]
    lines.append(Text("FAINTED", style="bold #d1495b", justify="left") if frac <= 0 else Text(f"weak to: {weak_to}", style="#59595f", justify="left"))
    return _box(*lines, width=width)


def _player_box(creature: dict, where: str, width: int = 46) -> Panel:
    s = creature["stats"]
    head = Text(creature["name"].upper(), style=f"bold {INK}", justify="left")
    head.append(f"   {creature['category'].title()}", style="#59595f")
    return _box(
        head,
        _pips("AUT", s["autonomy"]) + Text("  ") + _pips("REA", s["reach"]),
        _pips("CTL", s["control"]) + Text("  ") + _pips("COST", s["startup"]),
        Text(f"runs on: {where}", style="#59595f", overflow="fold", justify="left"),
        width=width,
    )


def _menu(creature: dict, selected: int | None) -> Table:
    names = [s["name"] for s in creature["skills"]] + ["RUN"]
    grid = Table.grid(padding=(0, 3))
    grid.add_column()
    grid.add_column()
    cells = []
    for i, n in enumerate(names[:4]):
        cursor = "▶ " if i == selected else "  "
        cells.append(Text(cursor + n, style=f"bold {INK}" if i == selected else INK, justify="left"))
    while len(cells) < 4:
        cells.append(Text(""))
    grid.add_row(cells[0], cells[1])
    grid.add_row(cells[2], cells[3])
    return grid


def _message_box(lines: list[str], menu: RenderableType | None, width: int) -> Panel:
    msg = Text("\n".join(lines), style=INK, justify="left")
    if menu is None:
        return Panel(msg, width=width, border_style=INK, style=SCENE, padding=(0, 2))
    grid = Table.grid(expand=True)
    grid.add_column(ratio=3)
    grid.add_column(ratio=2)
    grid.add_row(msg, menu)
    return Panel(grid, width=width, border_style=INK, style=SCENE, padding=(0, 2))


def scene(ctx, number: str, title: str, step: str, creature_ids: list[str]) -> RenderableType:
    width = min(ctx.console.width, 108)
    name, opp_rows = _opponent(number)
    lead = ctx.creatures[creature_ids[0]]
    where = ctx.where.describe(creature_ids[0])
    top = Table.grid(expand=True)
    top.add_column(ratio=1)
    top.add_column(justify="right")
    top.add_row(_opponent_box(name, number, 1.0, lead["name"]), _on_platform(sprites.render_grid(opp_rows)))
    bottom = Table.grid(expand=True)
    bottom.add_column(ratio=1)
    bottom.add_column(justify="right")
    bottom.add_row(_on_platform(sprites.render(lead["id"])), _player_box(lead, where))
    party = [ctx.creatures[i]["name"] for i in creature_ids[1:]]
    lines = [f"A wild {name} appeared!", f'"{title}"  ·  {step}', f"What will {lead['name']} do?" + (f"   (party: {', '.join(party)})" if party else "")]
    body = Group(top, Text(""), bottom)
    return Group(
        Panel(body, width=width, border_style=INK, style=SCENE, padding=(0, 1)),
        _message_box(lines, _menu(lead, None), width),
    )


def intro(ctx, number: str, title: str, step: str, creature_ids: list[str]) -> None:
    ctx.console.rule(f"[bold]Encounter {number}: {title}")
    ctx.console.print(scene(ctx, number, title, step, creature_ids))


def move_used(ctx, attempt_id: str) -> None:
    """'<Creature> used <skill>!' right after the presenter chooses to run the step."""
    if attempt_id not in MOVES:
        return
    cid, idx, _ = MOVES[attempt_id]
    creature = ctx.creatures[cid]
    skill = creature["skills"][idx]
    width = min(ctx.console.width, 108)
    ctx.console.print(_message_box([f"{creature['name']} used {skill['name']}!", skill["does"]], _menu(creature, idx), width))


OUTCOME = {
    "LIVE": "{opp} fainted! It's super effective!",
    "REPLAY": "{opp} fainted (shown from a recorded run).",
    "DIDACTIC": "{opp} did not really fall: this step is an explanation.",
    "SKIPPED": "You ran away!",
    "MISSING": "Nothing happened: there is no recording yet.",
}


def outcome(ctx, attempt_id: str, status: str, number: str | None) -> None:
    if attempt_id not in MOVES or number is None:
        return
    cid, _, achieved = MOVES[attempt_id]
    name, _ = _opponent(number)
    width = min(ctx.console.width, 108)
    fell = status in ("LIVE", "REPLAY")
    box = _opponent_box(name, number, 0.0 if fell else 1.0, ctx.creatures[cid]["name"], width=44)
    lines = [OUTCOME.get(status, status).format(opp=name)]
    if fell:
        lines.append(achieved)
        lines.append(f"{ctx.creatures[cid]['name']} gained EXP: {ctx.creatures[cid]['project']}.")
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(ratio=1)
    grid.add_row(box, Text("\n".join(lines), style=INK))
    ctx.console.print(Panel(grid, width=width, border_style=INK, style=SCENE, padding=(0, 1)))


def title_screen(ctx) -> None:
    """Opening screen: the ten creatures lined up, like a party screen."""
    width = min(ctx.console.width, 108)
    title = Text("AGENTIC BESTIARY", style=f"bold {INK}", justify="center")
    sub = Text("Los Faroleros · ten projects, one story", style="#59595f", justify="center")
    rows: list[RenderableType] = [title, sub, Text("")]
    ids = list(ctx.creatures)
    for chunk in (ids[:5], ids[5:]):
        grid = Table.grid(padding=(0, 2))
        for _ in chunk:
            grid.add_column(justify="center")
        grid.add_row(*[sprites.render(i) for i in chunk])
        grid.add_row(*[Text(ctx.creatures[i]["name"], style=f"bold {INK}", justify="center") for i in chunk])
        rows.append(Align.center(grid))
        rows.append(Text(""))
    rows.append(Text("PRESS ENTER", style="bold #d1495b", justify="center"))
    ctx.console.print(Panel(Group(*rows), width=width, border_style=INK, style=SCENE, padding=(1, 2)))
