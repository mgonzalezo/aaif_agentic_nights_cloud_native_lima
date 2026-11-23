"""Game engine: screens, badges, stage controls, live-or-replay logic."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from bestiary import sprites
from bestiary.config import REPLAY_DIR, Settings
from bestiary.llm import Detection
from bestiary.where import Where

DATA = Path(__file__).parent / "data" / "creatures.yaml"

BADGES = {
    "LIVE": ("LIVE", "bold black on #5fad56"),
    "REPLAY": ("REPLAY", "bold black on #f2c14e"),
    "DIDACTIC": ("DIDACTIC", "bold white on #1f5f99"),
}

CATEGORY_RULES = {
    "AGENT": "Takes turns and chooses moves.",
    "PROTOCOL": "Gives the agent moves. Has no turn of its own.",
    "INSTRUCTION FORMAT": "A passive aura loaded from a file.",
    "GATEWAY": "A field effect: filters, routes, records.",
    "API SPECIFICATION": "The language spoken in the arena.",
    "SANDBOX": "Run moves take no Risk damage.",
    "TRAINING ENVIRONMENT": "A dojo between chapters. Not used in battle.",
}


def load_creatures() -> dict[str, dict]:
    return {c["id"]: c for c in yaml.safe_load(DATA.read_text(encoding="utf-8"))}


class Fallback(Exception):
    """Raised by a live step to say: show the replay (or didactic version) instead."""


@dataclass
class Ctx:
    console: Console
    settings: Settings
    detection: Detection
    creatures: dict[str, dict]
    auto: bool = False  # no key presses (tests, recording)
    replay_only: bool = False
    record: bool = False
    events: list[dict] = field(default_factory=list)
    badge: str = "LIVE"
    where: Where = field(default_factory=Where)
    _pending_live: bool = False

    def _flush_badge(self) -> None:
        if self._pending_live:
            self._pending_live = False
            self.show_badge("LIVE")

    # ---------- output helpers ----------
    def say(self, text: str, style: str = "") -> None:
        self._flush_badge()
        self.console.print(Text(text, style=style) if style else text)

    def wire(self, kind: str, data: Any) -> None:
        """Show a raw protocol event (and keep it for recording)."""
        self._flush_badge()
        self.events.append({"kind": kind, "data": data})
        body = data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False)
        if len(body) > 1400:
            body = body[:1400] + "\n... (truncated)"
        lexer = "text" if isinstance(data, str) else "json"
        self.console.print(
            Panel(Syntax(body, lexer, theme="ansi_dark", word_wrap=True), title=f"[dim]{kind}[/]", border_style="dim")
        )

    def code(self, source: str, title: str, lexer: str = "python") -> None:
        self._flush_badge()
        self.console.print(Panel(Syntax(source, lexer, theme="ansi_dark", line_numbers=True), title=title))

    def pause(self, prompt: str = "Enter to continue") -> str:
        if self.auto:
            return ""
        return self.console.input(f"[dim]{prompt} > [/]").strip().lower()

    # ---------- live / replay ----------
    def attempt(self, encounter_id: str, live: Callable[[], Any], didactic: Callable[[], Any] | None = None) -> str:
        """Run a live step; on Fallback (or if the presenter presses r) show the replay; else didactic."""
        self.events = []
        choice = "" if self.auto else self.pause("[Enter] run live   [r] show replay   [s] skip")
        if choice == "s":
            return "SKIPPED"
        if not self.replay_only and choice != "r":
            try:
                self.badge = "LIVE"
                self._pending_live = True  # badge appears with the first live output
                started = time.time()
                live()
                self._flush_badge()
                if self.record:
                    save_replay(encounter_id, self.events, self.detection, time.time() - started)
                return "LIVE"
            except Fallback as why:
                self._pending_live = False
                self.console.print(f"[dim]live step not available: {why}[/]")
            except Exception as err:  # never crash on stage
                self._pending_live = False
                self.console.print(f"[red]live step failed: {type(err).__name__}: {err}[/]")
        replay = load_replay(encounter_id)
        if replay:
            self.badge = "REPLAY"
            self.show_badge("REPLAY", f"recorded {replay['recorded_at']} with {replay.get('model') or 'no model'}")
            for ev in replay["events"]:
                self.wire(ev["kind"], ev["data"])
            return "REPLAY"
        if didactic:
            self.badge = "DIDACTIC"
            self.show_badge("DIDACTIC", "simulated explanation, not a real run")
            didactic()
            return "DIDACTIC"
        self.say("No replay recorded yet. Record one with: uv run bestiary record", "yellow")
        return "MISSING"

    def show_badge(self, badge: str, note: str = "") -> None:
        label, style = BADGES[badge]
        t = Text(f" {label} ", style=style)
        if note:
            t.append(f"  {note}", style="dim")
        self.console.print(t)


def creature_card(c: dict, scale: int = 1, where: str = "") -> Panel:
    stats = c["stats"]
    lines = Text()
    lines.append(f"{c['name']}", style="bold")
    lines.append(f"  ({c['animal']})\n", style="dim")
    lines.append(f"stands for: {c['project']}\n", style="cyan")
    lines.append(f"{c['category']}\n", style="bold magenta")
    for key in ("autonomy", "reach", "control", "startup"):
        v = stats[key]
        lines.append(f"{key:<9}{'#' * v}{'.' * (5 - v)} {v}\n")
    if where:
        lines.append("runs on: ", style="dim")
        lines.append(where, style="cyan")
    return Panel(Group(sprites.render(c["id"], scale), lines), width=34, border_style="grey50")


def encounter_header(ctx: Ctx, number: str, title: str, step: str, creature_ids: list[str]) -> None:
    ctx.console.rule(f"[bold]Encounter {number}: {title}")
    ctx.say(f"Workflow step: {step}", "italic")
    ctx.console.print(Columns([creature_card(ctx.creatures[i], where=ctx.where.describe(i)) for i in creature_ids]))


def team_table(creatures: dict[str, dict], highlight: str | None = None) -> Table:
    t = Table(title="The Lamplighters", show_lines=False)
    for col in ("Creature", "Stands for", "Category", "Autonomy", "Reach", "Control", "Startup"):
        t.add_column(col, style="bold yellow" if col.lower() == highlight else None)
    for c in creatures.values():
        s = c["stats"]
        t.add_row(c["name"], c["project"], c["category"], str(s["autonomy"]), str(s["reach"]), str(s["control"]), str(s["startup"]))
    return t


# ---------- replays ----------

def save_replay(encounter_id: str, events: list[dict], detection: Detection, seconds: float) -> Path:
    REPLAY_DIR.mkdir(exist_ok=True)
    path = REPLAY_DIR / f"{encounter_id}.json"
    payload = {
        "encounter": encounter_id,
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model": detection.provider.label() if detection.provider else None,
        "seconds": round(seconds, 1),
        "events": events,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_replay(encounter_id: str) -> dict | None:
    path = REPLAY_DIR / f"{encounter_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
