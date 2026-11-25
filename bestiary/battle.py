"""Pokemon-style battle screens for the encounters (BESTIARY_UI=battle, or --ui battle).

Every encounter is a battle: one of your creatures against the obstacle of the story. You choose the creature: the
menu has CREATURES (the list of the ten, each with what it is good for), and sending the wrong one does not run the
step: the game says it is not very effective and gives a hint. The creature carries the real name of the AAIF project
it stands for, so nobody has to remember who is who. The other choices are POKEDEX (what a project is, what it is
good for, its weakness), FIGHT (run the step live), REPLAY (a real recording) and RUN (skip). With BESTIARY_PICK=auto
(or --pick auto) the right creature is already on the field, for when the time is short.

The skill the creature "uses" (from creatures.yaml) is followed by the real call, its raw output and its
LIVE / REPLAY / DIDACTIC badge. The arena is static (no animation): it survives a slow SSM session and the streaming
output of goose. The texts are in Spanish by default (BESTIARY_LANG=en for English). The classic screens stay the default.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.align import Align
from rich.console import Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bestiary import keys, sprites
from bestiary.i18n import category_label, is_es, localized_yaml
from bestiary.i18n import t as tr

try:  # the opponent art lives in its own module
    from bestiary.opponents import NAMES, OPPONENTS
except ImportError:  # pragma: no cover - only while the art is missing
    NAMES, OPPONENTS = {}, {}

INK = "#1b1b2f"
CREAM = "#f4f1e4"
MUTED = "#59595f"
RED = "#9c2f3f"
SCENE = f"{INK} on {CREAM}"
TAG = "bold #ffffff on #5765ff"   # the real project name, like a name tag
MIN_WIDTH = 100

# encounter number -> opponent id
OPPONENT_OF = {"1": "doubt", "2": "fog", "3": "injection", "4": "ritual", "5": "bug", "6": "flaky",
               "7": "review", "8": "gate", "9": "detour", "10": "dojo", "K8s": "cluster"}

# attempt id (the first argument of Ctx.attempt) -> (the creature that solves it, skill index, what that move achieved)
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

OBSTACLES = Path(__file__).parent / "data" / "obstacles.yaml"


def load_obstacles() -> dict[str, dict]:
    """What each obstacle is, why it is a problem and the hint (data/obstacles.yaml, and obstacles.es.yaml in Spanish)."""
    base = yaml.safe_load(OBSTACLES.read_text(encoding="utf-8"))
    for oid, texts in (localized_yaml("obstacles") or {}).items():
        base.setdefault(oid, {}).update(texts)
    return base


def obstacle_info(number: str | None) -> dict:
    return load_obstacles().get(OPPONENT_OF.get(number or "", ""), {})


# the action menu: label, what it returns to the engine, and the hint shown under the cursor.
# Two columns, row by row: FIGHT | CREATURES, POKEDEX | REPLAY, RUN.
CHOICES = [
    ("FIGHT", "", "Run this step for real. The badge will say LIVE."),
    ("CREATURES", "pick", "Choose which creature to send out against this obstacle."),
    ("POKÉDEX", "dex", "Read the entries of the creatures: what each one is, what it is good for, its weakness."),
    ("REPLAY", "r", "Show a real recording of this step. The badge will say REPLAY."),
    ("RUN", "s", "Skip this step."),
]
FIGHT, PICK, DEX, REPLAY, RUN = range(5)
# when a terminal does not send arrows the game understands: W A S D and H J K L move too, 1 to 5 jump to a choice, Tab cycles
ALIASES = {"w": "up", "k": "up", "s": "down", "j": "down", "a": "left", "h": "left", "d": "right", "l": "right"}


def enabled(ctx) -> bool:
    return getattr(ctx.settings, "ui", "classic") == "battle" and ctx.console.width >= MIN_WIDTH


def interactive(ctx) -> bool:
    """Arrow-key menus need a real terminal; scripted runs (--auto, tests, pipes) keep the plain prompts."""
    return enabled(ctx) and not ctx.auto and ctx.console.is_terminal and keys.stdin_is_tty()


def picking(ctx) -> bool:
    """True when the presenter chooses the creature (the default). With --pick auto the right one is already on the field."""
    return getattr(ctx.settings, "pick", "choose") != "auto" and interactive(ctx)


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
    if is_es():
        from bestiary.i18n_es import OPPONENT_NAMES

        name = OPPONENT_NAMES.get(oid, NAMES.get(oid, oid))
    else:
        name = NAMES.get(oid, oid)
    return name.upper(), rows


def _bar(label: str, frac: float, width: int = 18) -> Text:
    frac = max(0.0, min(1.0, frac))
    color = "#2e9e5b" if frac > 0.5 else "#e0a526" if frac > 0.2 else "#d1495b"
    filled = round(frac * width)
    t = Text(f"{label} ", style=f"bold {INK}", justify="left")
    t.append("█" * filled, style=color)
    t.append("░" * (width - filled), style="#b8b4a0")
    return t


def _pips(label: str, value: int) -> Text:
    t = Text(f"{tr(label)} ", style=f"bold {INK}", justify="left")
    t.append("■" * value, style="#5765ff")
    t.append("□" * (5 - value), style="#b8b4a0")
    return t


def _stats_line(s: dict, gap: str = "   ") -> Text:
    return (_pips("AUT", s["autonomy"]) + Text(gap) + _pips("REA", s["reach"])
            + Text(gap) + _pips("CTL", s["control"]) + Text(gap) + _pips("COST", s["startup"]))


def _box(*lines: RenderableType, width: int, title: str | None = None) -> Panel:
    return Panel(Group(*lines), width=width, border_style=INK, style=SCENE, padding=(0, 1),
                 title=Text(f" {title} ", style=f"bold {INK}") if title else None, title_align="left")


def _field(label: str, text: str, color: str = INK) -> Text:
    t = Text(justify="left", overflow="fold")
    t.append(f"{label} ", style=f"bold {INK}")
    t.append(text, style=color)
    return t


def _opponent_box(name: str, number: str, frac: float, weak_to: str, width: int = 44, detail: dict | None = None) -> Panel:
    """The obstacle. With `detail` (what it is, why it is a problem) it explains itself; without, it is the compact card."""
    title = Text(name, style=f"bold {INK}", justify="left")
    title.append(f"   Lv{number}" if number.isdigit() else f"   {number}", style=MUTED)
    lines = [title, _bar(tr("HP"), frac)]
    if detail:
        lines.append(_field(tr("What it is:"), detail["what"]))
        lines.append(_field(tr("Why it is a problem:"), detail["problem"], RED))
    if frac <= 0:
        lines.append(Text(tr("FAINTED"), style="bold #d1495b", justify="left"))
    elif weak_to:
        lines.append(Text(tr("weak to: {who}", who=weak_to), style=MUTED, justify="left"))
    return _box(*lines, width=width, title=tr("OBSTACLE"))


def _player_box(creature: dict, where: str, width: int = 60) -> Panel:
    head = Text(creature["name"].upper(), style=f"bold {INK}", justify="left")
    head.append("  ")
    head.append(f" {creature['project']} ", style=TAG)   # the real name of the project
    about = Text(f"{category_label(creature['category'], nice=True)}: {creature['tagline']}", style=MUTED, overflow="fold", justify="left")
    s = creature["stats"]
    return _box(
        head,
        about,
        _pips("AUT", s["autonomy"]) + Text("  ") + _pips("REA", s["reach"]),
        _pips("CTL", s["control"]) + Text("  ") + _pips("COST", s["startup"]),
        Text(f"{tr('runs on:')} {where}", style=MUTED, overflow="fold", justify="left"),
        width=width,
        title=tr("YOUR CREATURE"),
    )


def _skills_menu(creature: dict, selected: int | None) -> Table:
    names = [s["name"] for s in creature["skills"]] + [tr("RUN")]
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
    return tr("Your team:") + "  " + "   ·   ".join(f"{ctx.creatures[i]['name']} = {short_project(ctx.creatures[i])}" for i in creature_ids)


def scene(ctx, number: str, title: str, step: str, creature_ids: list[str], with_creature: bool = True) -> RenderableType:
    """The arena. With `with_creature` False (you pick the creature) your side is empty until you send one out."""
    width = _width(ctx)
    name, opp_rows = _opponent(number)
    lead = ctx.creatures[creature_ids[0]]
    top = Table.grid(expand=True)
    top.add_column(ratio=1)
    top.add_column(justify="right")
    weak_to = f"{lead['name']} ({short_project(lead)})" if with_creature else ""
    top.add_row(_opponent_box(name, number, 1.0, weak_to, width=66, detail=obstacle_info(number)),
                _on_platform(sprites.render_grid(opp_rows)))
    bottom = Table.grid(expand=True)
    bottom.add_column(ratio=1)
    bottom.add_column(justify="right")
    headline = tr("A wild {name} appeared!   {title}  ·  {step}", name=name, title=tr(title), step=tr(step))
    if with_creature:
        bottom.add_row(_on_platform(sprites.render(lead["id"])), _player_box(lead, ctx.where.describe(creature_ids[0])))
        lines = [headline, _team_line(ctx, creature_ids)]
    else:
        empty = _box(Text(tr("Nobody is on the field yet."), style=MUTED, justify="left"),
                     Text(tr("Choose CREATURES in the menu and send out the one that solves this."), style=MUTED, justify="left"),
                     width=60, title=tr("YOUR CREATURE"))
        bottom.add_row(Text(""), empty)
        lines = [headline, tr("You have the ten creatures of Los Faroleros. Pick the one that solves this obstacle.")]
    return Group(
        Panel(Group(top, Text(""), bottom), width=width, border_style=INK, style=SCENE, padding=(0, 1)),
        _message_box(lines, None, width),
    )


def intro(ctx, number: str, title: str, step: str, creature_ids: list[str]) -> None:
    ctx.console.rule(f"[bold]{tr('Encounter {n}: {title}', n=number, title=tr(title))}")
    ctx.console.print(scene(ctx, number, title, step, creature_ids, with_creature=not (picking(ctx) and number != "K8s")))


def send_out(ctx, attempt_id: str) -> None:
    """'Go, <creature>!': when you picked the creature, its card enters the field before it fights."""
    if not picking(ctx) or not ctx.chosen or ctx.sent_out == ctx.chosen:
        return
    creature = ctx.creatures[ctx.chosen]
    bottom = Table.grid(expand=True)
    bottom.add_column(ratio=1)
    bottom.add_column(justify="right")
    bottom.add_row(_on_platform(sprites.render(creature["id"])), _player_box(creature, ctx.where.describe(creature["id"])))
    width = _width(ctx)
    ctx.console.print(Panel(bottom, width=width, border_style=INK, style=SCENE, padding=(0, 1)))
    ctx.console.print(_message_box([tr("Go, {name} ({project})!", name=creature["name"], project=short_project(creature))], None, width))
    ctx.sent_out = ctx.chosen


def move_used(ctx, attempt_id: str) -> None:
    """'<Creature> used <skill>!' right after the presenter chooses to run the step."""
    if attempt_id not in MOVES:
        return
    cid, idx, _ = MOVES[attempt_id]
    creature = ctx.creatures[cid]
    skill = creature["skills"][idx]
    ctx.console.print(_message_box([tr("{name} ({project}) used {skill}!", name=creature["name"], project=short_project(creature), skill=skill["name"]),
                                    skill["does"]], _skills_menu(creature, idx), _width(ctx)))


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
    box = _opponent_box(name, number, 0.0 if fell else 1.0, creature["name"], width=44)   # compact: no description
    lines = [tr(OUTCOME.get(status, status), opp=name)]
    if fell:
        lines.append(tr(achieved))
        lines.append(tr("{name} ({project}) gained EXP!", name=creature["name"], project=short_project(creature)))
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(ratio=1)
    grid.add_row(box, Text("\n".join(lines), style=INK))
    ctx.console.print(Panel(grid, width=width, border_style=INK, style=SCENE, padding=(0, 1)))


# ---------------------------------------------------------------- the action menu, the creature list and the Pokedex

def move_cursor(cursor: int, key: str, count: int = len(CHOICES)) -> int:
    """The menu is two columns wide. Arrows move between the cells and stop at the edges, like the game."""
    row, col = divmod(cursor, 2)
    if key == "left":
        col = 0
    elif key == "right":
        col = 1
    elif key == "up":
        row = max(0, row - 1)
    elif key == "down":
        row += 1
    new = row * 2 + col
    if new >= count:   # the last row may have a single cell
        new = count - 1 if key in ("up", "down") else cursor
    return new


def menu_panel(ctx, creature: dict | None, number: str | None, cursor: int, notice: str = "") -> Panel:
    """'Chambero (goose) vs BUG. What will Chambero do?', or 'Which creature do you send against BUG?' while the field is empty."""
    opp = _opponent(number)[0] if number else tr("the obstacle")
    label, _, hint = CHOICES[cursor]
    short = obstacle_info(number).get("short")
    left = Text(justify="left")
    if creature:
        left.append(f"{creature['name']} ({short_project(creature)}) vs {opp}\n", style=f"bold {INK}")
    else:
        left.append(tr("Which creature do you send against {opp}?", opp=opp) + "\n", style=f"bold {INK}")
    if short:
        left.append(f"{short}\n", style=RED)
    if creature:
        left.append(tr("What will {name} do?", name=creature["name"]) + "\n", style=INK)
    if notice:
        left.append(notice, style=f"bold {RED}")
    else:
        left.append(tr(hint), style=MUTED)
    grid = Table.grid(padding=(0, 4))
    grid.add_column()
    grid.add_column()
    cells = [Text(("▶ " if i == cursor else "  ") + tr(c[0]), style=f"bold {INK}" if i == cursor else INK) for i, c in enumerate(CHOICES)]
    for i in range(0, len(cells), 2):
        grid.add_row(*cells[i:i + 2])
    outer = Table.grid(expand=True)
    outer.add_column(ratio=3)
    outer.add_column(ratio=2)
    outer.add_row(left, grid)
    footer = Text(tr(" ← ↑ ↓ → (or W A S D)  move      ENTER  choose "), style=MUTED)
    if keys.unknown:   # a key the game does not know: say what arrived, so it can be fixed
        footer = Text(tr(" key not recognised: {keys}  ·  use W A S D ", keys=keys.unknown), style="bold #d1495b")
    return Panel(outer, width=_width(ctx), border_style=INK, style=SCENE, padding=(0, 2), subtitle=footer, subtitle_align="right")


def creatures_panel(ctx, number: str | None, at: int, chosen: str | None) -> Panel:
    """The list of the ten creatures, with what the highlighted one is good for. You pick the one that fits the obstacle."""
    ids = list(ctx.creatures)
    opp = _opponent(number)[0] if number else tr("the obstacle")
    short = obstacle_info(number).get("short", "")
    listing = Table.grid(padding=(0, 2))
    listing.add_column(no_wrap=True)
    listing.add_column(no_wrap=True)
    for i, cid in enumerate(ids):
        c = ctx.creatures[cid]
        mark = "▶ " if i == at else "  "
        on_field = " ✓" if cid == chosen else ""
        listing.add_row(Text(f"{mark}{c['name']}{on_field}", style=f"bold {INK}" if i == at else INK),
                        Text(short_project(c), style=MUTED))
    c = ctx.creatures[ids[at]]
    info = Text(justify="left")
    info.append(c["name"].upper(), style=f"bold {INK}")
    info.append("  ")
    info.append(f" {c['project']} ", style=TAG)
    info.append(f"\n{category_label(c['category'], nice=True)}: {c['tagline']}\n\n", style=MUTED)
    info.append(tr("GOOD FOR") + "  ", style="bold #5765ff")
    info.append(f"{c['good_for']}\n\n", style=INK)
    info.append(tr("WEAKNESS") + "  ", style="bold #5765ff")
    info.append(c["weakness"], style=RED)
    outer = Table.grid(padding=(0, 3), expand=True)
    outer.add_column(width=30)
    outer.add_column(ratio=1)
    outer.add_row(listing, info)
    head = Text(f"{opp}: {short}", style=f"bold {RED}", justify="left")
    return Panel(Group(head, Text(""), outer), width=_width(ctx), border_style=INK, style=SCENE, padding=(0, 2),
                 title=Text(tr(" CREATURES  ·  who solves this? "), style=f"bold {INK}"), title_align="left",
                 subtitle=Text(tr(" ↑ ↓  move      ENTER  send out      ESC  back "), style=MUTED), subtitle_align="right")


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
    head.append(f"\n{category_label(c['category'], nice=True)}  ·  {tr('joined the AAIF')} {c['joined_aaif']}", style=MUTED)
    head.append(f"\n\n{c['tagline']}", style=f"italic {INK}")
    top = Table.grid(padding=(0, 3))
    top.add_column()
    top.add_column(ratio=1)
    top.add_row(sprites.render(creature_id), head)

    rows = Table.grid(padding=(0, 2))
    rows.add_column(width=13, no_wrap=True)
    rows.add_column(ratio=1)

    def row(label: str, text: str | Text, color: str = INK) -> None:
        rows.add_row(Text(tr(label), style="bold #5765ff", justify="left"),
                     text if isinstance(text, Text) else Text(text, style=color, justify="left"))

    row("WHAT IT IS", c["definition"])
    row("GOOD FOR", c["good_for"])
    row("WEAKNESS", c["weakness"], RED)
    moves = Text(justify="left")
    for i, k in enumerate(c["skills"]):
        moves.append(("\n" if i else "") + k["name"], style=f"bold {INK}")
        moves.append(f"  {k['does']}", style=INK)
    row("MOVES", moves)
    row("IN THE GAME", tr(CATEGORY_RULES.get(c["category"], "")))
    row("STATS", _stats_line(c["stats"]))
    row("LEARN MORE", c["source"], MUTED)

    more = "   " + tr("← → other creatures ({n}/{total})", n=position, total=total) if total > 1 else ""
    return Panel(Group(top, Text(""), rows), width=_width(ctx), border_style=INK, style=SCENE, padding=(0, 2),
                 title=Text(f" POKÉDEX  No. {number:02d} ", style=f"bold {INK}"), title_align="left",
                 subtitle=Text(" " + tr("ENTER  back") + more + " ", style=MUTED), subtitle_align="right")


def _not_effective(ctx, attempt_id: str) -> str:
    """'' when the creature on the field is the one that solves this obstacle; otherwise what to tell the presenter."""
    correct = MOVES[attempt_id][0] if attempt_id in MOVES else None
    if correct is None or ctx.chosen == correct:
        return ""
    if not ctx.chosen:
        return tr("Choose a creature first: pick CREATURES in the menu.")
    c = ctx.creatures[ctx.chosen]
    opp = _opponent(ctx.current_number)[0] if ctx.current_number else tr("the obstacle")
    hint = obstacle_info(ctx.current_number).get("hint", "")
    text = tr("Not very effective! {name} ({project}) is not the best choice against {opp}.", name=c["name"], project=short_project(c), opp=opp)
    return text + ("\n" + tr("Hint: {hint}", hint=hint) if hint else "")


def choose(ctx, attempt_id: str) -> str:
    """The arrow-key menu before a step. Returns what the engine expects: '' (fight), 'r' (replay) or 's' (skip).

    When you pick the creature, FIGHT and REPLAY only work with the one that solves this obstacle; with the wrong one
    the game explains why and stays in the menu. The creature on the field stays for the rest of the encounter."""
    correct = MOVES[attempt_id][0] if attempt_id in MOVES else (ctx.current_party[0] if ctx.current_party else next(iter(ctx.creatures)))
    choosing = picking(ctx)
    if not choosing:
        ctx.chosen = correct   # the right creature is already on the field
    ids = list(ctx.creatures)
    if choosing:
        cursor = FIGHT if ctx.chosen else PICK
    else:
        cursor = FIGHT if correct in ctx.dex_seen else DEX   # the first time, Enter opens the Pokedex
    mode, notice, result = "menu", "", ""
    dex_at = pick_at = 0

    def on_field() -> dict | None:
        return ctx.creatures[ctx.chosen] if ctx.chosen else None

    def frame() -> RenderableType:
        if mode == "dex":
            return dex_panel(ctx, ids[dex_at], dex_at + 1, len(ids))
        if mode == "pick":
            return creatures_panel(ctx, ctx.current_number, pick_at, ctx.chosen)
        return menu_panel(ctx, on_field(), ctx.current_number, cursor, notice)

    with keys.raw_mode(), Live(frame(), console=ctx.console, auto_refresh=False, transient=True) as live:
        keys.flush_input()
        while True:
            key = keys.read_key()
            if key in ALIASES:
                key = ALIASES[key]
            if mode == "dex":
                if key == "left":
                    dex_at = max(0, dex_at - 1)
                elif key == "right":
                    dex_at = min(len(ids) - 1, dex_at + 1)
                elif key in ("enter", "space", "esc", "up", "down"):
                    mode, cursor = "menu", (FIGHT if ctx.chosen or not choosing else PICK)   # read it: next, fight (or pick)
                ctx.dex_seen.add(ids[dex_at])
                live.update(frame(), refresh=True)
                continue
            if mode == "pick":
                if key == "up":
                    pick_at = max(0, pick_at - 1)
                elif key == "down":
                    pick_at = min(len(ids) - 1, pick_at + 1)
                elif key in ("enter", "space"):
                    if ctx.chosen != ids[pick_at]:
                        ctx.chosen, ctx.sent_out = ids[pick_at], None
                    mode, cursor = "menu", FIGHT
                elif key in ("esc", "left"):
                    mode = "menu"
                live.update(frame(), refresh=True)
                continue
            notice = ""
            if key in ("1", "2", "3", "4", "5"):
                cursor = int(key) - 1
            elif key in ("tab", "backtab"):
                cursor = (cursor + (1 if key == "tab" else -1)) % len(CHOICES)
            elif key in ("enter", "space"):
                _, result, _ = CHOICES[cursor]
                if result == "dex":
                    mode = "dex"
                    dex_at = ids.index(ctx.chosen) if ctx.chosen else (0 if choosing else ids.index(correct))
                    ctx.dex_seen.add(ids[dex_at])
                elif result == "pick":
                    mode = "pick"
                    pick_at = ids.index(ctx.chosen) if ctx.chosen else 0
                elif result in ("", "r"):
                    notice = _not_effective(ctx, attempt_id)
                    if not notice:
                        break
                    cursor = PICK
                else:   # run away
                    break
            else:
                cursor = move_cursor(cursor, key)
            live.update(frame(), refresh=True)
    ctx.console.print(Text(f"▶ {tr(CHOICES[cursor][0])}", style="dim"))
    return result


def wait(ctx, prompt: str = "ENTER to continue") -> None:
    """The 'press a key' pause between screens: Enter or the right arrow."""
    ctx.console.print(Text(f"▶ {tr(prompt)}   {tr('(or →)')}", style="dim"))
    with keys.raw_mode():
        keys.flush_input()
        while ALIASES.get(key := keys.read_key(), key) not in ("enter", "space", "right", "down"):
            pass


def title_screen(ctx) -> None:
    """Opening screen: the ten creatures lined up, each with the real name of its project."""
    width = _width(ctx)
    title = Text("AGENTIC BESTIARY", style=f"bold {INK}", justify="center")
    sub = Text("Los Faroleros · " + tr("ten projects, one story"), style=MUTED, justify="center")
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
    rows.append(Text(tr("PRESS ENTER"), style="bold #d1495b", justify="center"))
    ctx.console.print(Panel(Group(*rows), width=width, border_style=INK, style=SCENE, padding=(1, 2)))
    if interactive(ctx):
        wait(ctx, "ENTER to start")
