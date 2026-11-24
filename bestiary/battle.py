"""Pokemon-style battle screens for the encounters (BESTIARY_UI=battle, or --ui battle).

Every encounter is a battle: your creature against the obstacle of the story. The creature always carries the
real name of the AAIF project it stands for, so nobody has to remember who is who. Before each step the
presenter moves a cursor with the arrow keys: POKEDEX (what the project is, what it is good for, its weakness),
FIGHT (run the step live), REPLAY (a real recording) or RUN (skip). The creature's skills (from creatures.yaml)
are what it "uses" when it fights, followed by the real call, its raw output and its LIVE / REPLAY / DIDACTIC
badge. The arena is static (no animation): it survives a slow SSM session and the streaming output of goose.
The classic screens stay the default.
"""

from __future__ import annotations

from rich.align import Align
from rich.console import Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bestiary import keys, sprites

try:  # the opponent art lives in its own module
    from bestiary.opponents import NAMES, OPPONENTS
except ImportError:  # pragma: no cover - only while the art is missing
    NAMES, OPPONENTS = {}, {}

INK = "#1b1b2f"
CREAM = "#f4f1e4"
MUTED = "#59595f"
SCENE = f"{INK} on {CREAM}"
TAG = "bold #ffffff on #5765ff"   # the real project name, like a name tag
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

# the action menu, row by row (2 x 2): label, what it returns to the engine, and the hint shown under the cursor
CHOICES = [
    ("POKÉDEX", "dex", "Read the entry for {project}: what it is, what it is good for, its weakness."),
    ("FIGHT", "", "Run this step for real. The badge will say LIVE."),
    ("REPLAY", "r", "Show a real recording of this step. The badge will say REPLAY."),
    ("RUN", "s", "Skip this step."),
]
FIGHT = 1
LETTERS = {"p": 0, "i": 0, "f": 1, "r": 2, "s": 3}   # old habits still work, but the arrows are the way


def enabled(ctx) -> bool:
    return getattr(ctx.settings, "ui", "classic") == "battle" and ctx.console.width >= MIN_WIDTH


def interactive(ctx) -> bool:
    """Arrow-key menus need a real terminal; scripted runs (--auto, tests, pipes) keep the plain prompts."""
    return enabled(ctx) and not ctx.auto and ctx.console.is_terminal and keys.stdin_is_tty()


def short_project(creature: dict) -> str:
    """'Model Context Protocol (MCP)' -> 'MCP'; 'goose' -> 'goose'."""
    p = creature["project"]
    return p[p.rfind("(") + 1:p.rfind(")")] if "(" in p and p.endswith(")") else p


def _width(ctx) -> int:
    return min(ctx.console.width, 108)


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


def _box(*lines: RenderableType, width: int, title: str | None = None) -> Panel:
    return Panel(Group(*lines), width=width, border_style=INK, style=SCENE, padding=(0, 1),
                 title=Text(f" {title} ", style=f"bold {INK}") if title else None, title_align="left")


def _opponent_box(name: str, number: str, frac: float, weak_to: str, width: int = 44) -> Panel:
    title = Text(name, style=f"bold {INK}", justify="left")
    title.append(f"   Lv{number}" if number.isdigit() else f"   {number}", style=MUTED)
    lines = [title, _bar("HP", frac)]
    lines.append(Text("FAINTED", style="bold #d1495b", justify="left") if frac <= 0 else Text(f"weak to: {weak_to}", style=MUTED, justify="left"))
    return _box(*lines, width=width, title="OBSTACLE")


def _player_box(creature: dict, where: str, width: int = 60) -> Panel:
    s = creature["stats"]
    head = Text(creature["name"].upper(), style=f"bold {INK}", justify="left")
    head.append("  ")
    head.append(f" {creature['project']} ", style=TAG)   # the real name of the project
    about = Text(f"{creature['category'].title()}: {creature['tagline']}", style=MUTED, overflow="fold", justify="left")
    return _box(
        head,
        about,
        _pips("AUT", s["autonomy"]) + Text("  ") + _pips("REA", s["reach"]),
        _pips("CTL", s["control"]) + Text("  ") + _pips("COST", s["startup"]),
        Text(f"runs on: {where}", style=MUTED, overflow="fold", justify="left"),
        width=width,
        title="YOUR CREATURE",
    )


def _skills_menu(creature: dict, selected: int | None) -> Table:
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


def _team_line(ctx, creature_ids: list[str]) -> str:
    return "Your team:  " + "   ·   ".join(f"{ctx.creatures[i]['name']} = {short_project(ctx.creatures[i])}" for i in creature_ids)


def scene(ctx, number: str, title: str, step: str, creature_ids: list[str]) -> RenderableType:
    width = _width(ctx)
    name, opp_rows = _opponent(number)
    lead = ctx.creatures[creature_ids[0]]
    where = ctx.where.describe(creature_ids[0])
    top = Table.grid(expand=True)
    top.add_column(ratio=1)
    top.add_column(justify="right")
    top.add_row(_opponent_box(name, number, 1.0, f"{lead['name']} ({short_project(lead)})"), _on_platform(sprites.render_grid(opp_rows)))
    bottom = Table.grid(expand=True)
    bottom.add_column(ratio=1)
    bottom.add_column(justify="right")
    bottom.add_row(_on_platform(sprites.render(lead["id"])), _player_box(lead, where))
    lines = [f"A wild {name} appeared!   {title}  ·  {step}", _team_line(ctx, creature_ids)]
    body = Group(top, Text(""), bottom)
    return Group(
        Panel(body, width=width, border_style=INK, style=SCENE, padding=(0, 1)),
        _message_box(lines, None, width),
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
    ctx.console.print(_message_box([f"{creature['name']} ({short_project(creature)}) used {skill['name']}!", skill["does"]],
                                   _skills_menu(creature, idx), _width(ctx)))


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
    creature = ctx.creatures[cid]
    name, _ = _opponent(number)
    width = _width(ctx)
    fell = status in ("LIVE", "REPLAY")
    box = _opponent_box(name, number, 0.0 if fell else 1.0, creature["name"], width=44)
    lines = [OUTCOME.get(status, status).format(opp=name)]
    if fell:
        lines.append(achieved)
        lines.append(f"{creature['name']} ({short_project(creature)}) gained EXP!")
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(ratio=1)
    grid.add_row(box, Text("\n".join(lines), style=INK))
    ctx.console.print(Panel(grid, width=width, border_style=INK, style=SCENE, padding=(0, 1)))


# ---------------------------------------------------------------- the action menu and the Pokedex

def move_cursor(cursor: int, key: str) -> int:
    """The 2 x 2 menu: arrows move between the cells and stop at the edges, like the game."""
    row, col = divmod(cursor, 2)
    if key == "left":
        col = 0
    elif key == "right":
        col = 1
    elif key == "up":
        row = 0
    elif key == "down":
        row = 1
    return row * 2 + col


def menu_panel(ctx, creature: dict, number: str | None, cursor: int) -> Panel:
    """'Chambero (goose) vs BUG. What will Chambero do?' with the four choices, the cursor on one of them."""
    opp = _opponent(number)[0] if number else "the obstacle"
    label, _, hint = CHOICES[cursor]
    left = Text(justify="left")
    left.append(f"{creature['name']} ({short_project(creature)}) vs {opp}\n", style=f"bold {INK}")
    left.append(f"What will {creature['name']} do?\n", style=INK)
    left.append(hint.format(project=creature["project"]), style=MUTED)
    grid = Table.grid(padding=(0, 4))
    grid.add_column()
    grid.add_column()
    cells = [Text(("▶ " if i == cursor else "  ") + c[0], style=f"bold {INK}" if i == cursor else INK) for i, c in enumerate(CHOICES)]
    grid.add_row(cells[0], cells[1])
    grid.add_row(cells[2], cells[3])
    outer = Table.grid(expand=True)
    outer.add_column(ratio=3)
    outer.add_column(ratio=2)
    outer.add_row(left, grid)
    return Panel(outer, width=_width(ctx), border_style=INK, style=SCENE, padding=(0, 2),
                 subtitle=Text(" ← ↑ ↓ →  move      ENTER  choose ", style=MUTED), subtitle_align="right")


def dex_panel(ctx, creature_id: str, position: int, total: int) -> Panel:
    """The Pokedex entry: what the project is, what it is good for, its weakness."""
    from bestiary.engine import CATEGORY_RULES

    c = ctx.creatures[creature_id]
    number = list(ctx.creatures).index(creature_id) + 1
    head = Text(justify="left")
    head.append(c["name"].upper(), style=f"bold {INK}")
    head.append("  ")
    head.append(f" {c['project']} ", style=TAG)
    head.append(f"\n({c['animal']})", style=MUTED)
    head.append(f"\n{c['category'].title()}  ·  joined the AAIF {c['joined_aaif']}", style=MUTED)
    head.append(f"\n\n{c['tagline']}", style=f"italic {INK}")
    top = Table.grid(padding=(0, 3))
    top.add_column()
    top.add_column(ratio=1)
    top.add_row(sprites.render(creature_id), head)

    s = c["stats"]
    rows = Table.grid(padding=(0, 2))
    rows.add_column(width=11, no_wrap=True)
    rows.add_column(ratio=1)

    def row(label: str, text: str | Text, color: str = INK) -> None:
        rows.add_row(Text(label, style="bold #5765ff", justify="left"),
                     text if isinstance(text, Text) else Text(text, style=color, justify="left"))

    row("WHAT IT IS", c["definition"])
    row("GOOD FOR", c["good_for"])
    row("WEAKNESS", c["weakness"], "#9c2f3f")
    moves = Text(justify="left")
    for i, k in enumerate(c["skills"]):
        moves.append(("\n" if i else "") + k["name"], style=f"bold {INK}")
        moves.append(f"  {k['does']}", style=INK)
    row("MOVES", moves)
    row("IN THE GAME", CATEGORY_RULES.get(c["category"], ""))
    stats = _pips("AUT", s["autonomy"]) + Text("   ") + _pips("REA", s["reach"]) + Text("   ") + _pips("CTL", s["control"]) + Text("   ") + _pips("COST", s["startup"])
    row("STATS", stats)
    row("LEARN MORE", c["source"], MUTED)

    more = f"   ← → other team members ({position}/{total})" if total > 1 else ""
    return Panel(Group(top, Text(""), rows), width=_width(ctx), border_style=INK, style=SCENE, padding=(0, 2),
                 title=Text(f" POKÉDEX  No. {number:02d} ", style=f"bold {INK}"), title_align="left",
                 subtitle=Text(f" ENTER  back to the fight{more} ", style=MUTED), subtitle_align="right")


def dex_order(ctx, attempt_id: str) -> list[str]:
    """The creature of this step first, then the rest of the team in the order of the encounter."""
    first = MOVES[attempt_id][0] if attempt_id in MOVES else (ctx.current_party[0] if ctx.current_party else next(iter(ctx.creatures)))
    return [first] + [c for c in ctx.current_party if c != first]


def choose(ctx, attempt_id: str) -> str:
    """The arrow-key menu before a step. Returns what the engine expects: '' (fight), 'r' (replay) or 's' (skip)."""
    order = dex_order(ctx, attempt_id)
    lead = ctx.creatures[order[0]]
    cursor = FIGHT if order[0] in ctx.dex_seen else 0   # the first time, Enter opens the Pokedex
    in_dex, dex_at = False, 0

    def frame() -> RenderableType:
        return dex_panel(ctx, order[dex_at], dex_at + 1, len(order)) if in_dex else menu_panel(ctx, lead, ctx.current_number, cursor)

    with keys.raw_mode(), Live(frame(), console=ctx.console, auto_refresh=False, transient=True) as live:
        keys.flush_input()
        while True:
            key = keys.read_key()
            if in_dex:
                if key == "left":
                    dex_at = max(0, dex_at - 1)
                elif key == "right":
                    dex_at = min(len(order) - 1, dex_at + 1)
                elif key in ("enter", "space", "esc", "up", "down"):
                    in_dex, cursor = False, FIGHT   # read it: the next Enter fights
                ctx.dex_seen.add(order[dex_at])
                live.update(frame(), refresh=True)
                continue
            if key in LETTERS:
                cursor, key = LETTERS[key], "enter"
            if key in ("enter", "space"):
                _, result, _ = CHOICES[cursor]
                if result != "dex":
                    break
                in_dex, dex_at = True, 0
                ctx.dex_seen.add(order[0])
            else:
                cursor = move_cursor(cursor, key)
            live.update(frame(), refresh=True)
    ctx.console.print(Text(f"▶ {CHOICES[cursor][0]}", style="dim"))
    return result


def wait(ctx, prompt: str = "ENTER to continue") -> None:
    """The 'press a key' pause between screens: Enter or the right arrow."""
    ctx.console.print(Text(f"▶ {prompt}   (or →)", style="dim"))
    with keys.raw_mode():
        keys.flush_input()
        while keys.read_key() not in ("enter", "space", "right", "down"):
            pass


def title_screen(ctx) -> None:
    """Opening screen: the ten creatures lined up, each with the real name of its project."""
    width = _width(ctx)
    title = Text("AGENTIC BESTIARY", style=f"bold {INK}", justify="center")
    sub = Text("Los Faroleros · ten projects, one story", style=MUTED, justify="center")
    rows: list[RenderableType] = [title, sub, Text("")]
    ids = list(ctx.creatures)
    for chunk in (ids[:5], ids[5:]):
        grid = Table.grid(padding=(0, 2))
        for _ in chunk:
            grid.add_column(justify="center")
        grid.add_row(*[sprites.render(i) for i in chunk])
        grid.add_row(*[Text(ctx.creatures[i]["name"], style=f"bold {INK}", justify="center") for i in chunk])
        grid.add_row(*[Text(short_project(ctx.creatures[i]), style="bold #5765ff", justify="center") for i in chunk])
        rows.append(Align.center(grid))
        rows.append(Text(""))
    rows.append(Text("PRESS ENTER", style="bold #d1495b", justify="center"))
    ctx.console.print(Panel(Group(*rows), width=width, border_style=INK, style=SCENE, padding=(1, 2)))
    if interactive(ctx):
        wait(ctx, "ENTER to start")
