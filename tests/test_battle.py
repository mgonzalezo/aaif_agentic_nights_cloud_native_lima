"""The Pokemon-style battle UI (BESTIARY_UI=battle): scenes fit the terminal, show the real data, and the game still runs."""

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from rich.cells import cell_len
from rich.console import Console

from bestiary import battle
from bestiary.config import Settings
from bestiary.engine import Ctx, Fallback, encounter_header, load_creatures
from bestiary.llm import Detection
from bestiary.sprites import PALETTE
from bestiary.where import Where

ROOT = Path(__file__).resolve().parent.parent
ENCOUNTERS = [
    ("1", "How do I run the tests?", "Consult information", ["scribbit"]),
    ("2", "The issue in the fog", "Read the issue", ["octoplug"]),
    ("3", "Injection", "Stay safe", ["bulwark"]),
    ("4", "The upstream ritual", "How we contribute", ["satchel"]),
    ("5", "The bug", "Propose a change", ["mender", "scribbit", "satchel"]),
    ("6", "The flaky test", "Test safely", ["glasshell"]),
    ("7", "Second opinion", "Review by another team", ["chasqui", "glyphstone"]),
    ("8", "The PR", "Open the pull request", ["octoplug", "bulwark", "satchel"]),
    ("9", "Detour (side quest)", "The team grows: many models", ["switchy", "bulwark"]),
    ("10", "The dojo (epilogue)", "Improve the model later", ["dojolotl"]),
    ("K8s", "Kubernetes region", "Share it with many teams", ["bulwark"]),
]


def make_ctx(monkeypatch, width=110, ui="battle"):
    monkeypatch.setenv("BESTIARY_UI", ui)
    monkeypatch.delenv("BESTIARY_PROFILE", raising=False)
    buf = io.StringIO()
    s = Settings()
    ctx = Ctx(console=Console(file=buf, width=width, force_terminal=False, color_system=None), settings=s,
              detection=Detection(None, []), creatures=load_creatures(), auto=True,
              where=Where(settings=s, kubectl=lambda a: ""))
    return ctx, buf


def test_every_opponent_has_a_valid_16x16_sprite_and_a_name():
    from bestiary.opponents import NAMES, OPPONENTS

    for oid in battle.OPPONENT_OF.values():
        rows = OPPONENTS[oid]
        assert len(rows) == 16 and all(len(r) == 16 for r in rows), oid
        assert set("".join(rows)) <= set(PALETTE) | {"."}, oid
        assert NAMES[oid]
    assert len(set(tuple(r) for r in (OPPONENTS[o] for o in battle.OPPONENT_OF.values()))) == len(battle.OPPONENT_OF)


@pytest.mark.parametrize("number,title,step,ids", ENCOUNTERS)
def test_every_battle_scene_fits_110_columns_and_shows_the_fight(monkeypatch, number, title, step, ids):
    ctx, buf = make_ctx(monkeypatch)
    encounter_header(ctx, number, title, step, ids)
    out = buf.getvalue()
    assert all(cell_len(line) <= 110 for line in out.splitlines()), max(cell_len(line) for line in out.splitlines())
    lead = ctx.creatures[ids[0]]
    assert "appeared!" in out and "HP" in out and "weak to:" in out
    assert lead["name"].upper() in out and "runs on:" in out
    for skill in lead["skills"][:3]:
        assert skill["name"] in out
    assert "RUN" in out


def test_the_party_is_listed_when_the_encounter_has_helpers(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    encounter_header(ctx, "5", "The bug", "Propose a change", ["mender", "scribbit", "satchel"])
    assert "party: DeathNote, Navaja Suiza" in buf.getvalue()


def test_a_narrow_terminal_falls_back_to_the_classic_screen(monkeypatch):
    ctx, buf = make_ctx(monkeypatch, width=80)
    encounter_header(ctx, "3", "Injection", "Stay safe", ["bulwark"])
    assert "Workflow step: Stay safe" in buf.getvalue() and "appeared!" not in buf.getvalue()


def test_classic_stays_the_default(monkeypatch):
    ctx, buf = make_ctx(monkeypatch, ui="classic")
    encounter_header(ctx, "3", "Injection", "Stay safe", ["bulwark"])
    assert "Workflow step: Stay safe" in buf.getvalue() and "appeared!" not in buf.getvalue()


def test_a_live_step_ends_with_the_opponent_fainting(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    encounter_header(ctx, "1", "How do I run the tests?", "Consult information", ["scribbit"])
    assert ctx.attempt("e1_doubt", lambda: ctx.say("the real output")) == "LIVE"
    out = buf.getvalue()
    assert "DeathNote used How to run this!" in out
    assert "DOUBT fainted! It's super effective!" in out and "the real output" in out


def test_a_step_that_is_only_an_explanation_does_not_pretend_to_win(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    encounter_header(ctx, "3", "Injection", "Stay safe", ["bulwark"])

    def live():
        raise Fallback("gateway not reachable")

    assert ctx.attempt("e3_gateway", live, lambda: ctx.say("explanation")) == "DIDACTIC"
    out = buf.getvalue()
    assert "did not really fall: this step is an explanation" in out and "fainted!" not in out and "DIDACTIC" in out


def test_the_title_screen_lists_all_ten_creatures(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    battle.title_screen(ctx)
    out = buf.getvalue()
    assert "AGENTIC BESTIARY" in out and "PRESS ENTER" in out
    for c in ctx.creatures.values():
        assert c["name"] in out


def test_the_whole_game_runs_in_battle_mode(fake_model):
    env = dict(os.environ, BESTIARY_UI="battle", BESTIARY_FORGE_PORT="28767", BESTIARY_REVIEWER_PORT="29997",
               BESTIARY_GATEWAY_URL="http://localhost:1/mcp", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "bestiary.cli", "play", "--auto", "--width", "120"], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=240)
    assert r.returncode == 0, r.stderr[-2000:]
    out = r.stdout
    assert "AGENTIC BESTIARY" in out and "A wild FOG appeared!" in out and "A wild BUG appeared!" in out
    assert "fainted!" in out and "The map" in out and "Traceback" not in r.stderr
