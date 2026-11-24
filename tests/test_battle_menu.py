"""The Pokedex and the arrow-key menu of the battle UI. No real terminal needed: the key presses are scripted."""

import io

import pytest
from rich.cells import cell_len
from rich.console import Console

from bestiary import battle, keys
from bestiary.config import Settings
from bestiary.engine import Ctx, encounter_header, load_creatures
from bestiary.llm import Detection
from bestiary.where import Where


def make_ctx(monkeypatch, width=110):
    monkeypatch.setenv("BESTIARY_UI", "battle")
    monkeypatch.delenv("BESTIARY_PROFILE", raising=False)
    buf = io.StringIO()
    s = Settings()
    ctx = Ctx(console=Console(file=buf, width=width, force_terminal=False, color_system=None), settings=s,
              detection=Detection(None, []), creatures=load_creatures(), auto=True,
              where=Where(settings=s, kubectl=lambda a: ""))
    return ctx, buf


def press(monkeypatch, *pressed):
    """Script the next key presses. The returned list shrinks as the game reads them."""
    queue = list(pressed)
    monkeypatch.setattr(keys, "read_key", lambda: queue.pop(0))
    monkeypatch.setattr(keys, "flush_input", lambda: None)
    return queue


def terminal_ctx(monkeypatch):
    """A battle context that behaves as if the presenter were at a real terminal, on encounter 5."""
    ctx, buf = make_ctx(monkeypatch)
    ctx.console = Console(file=buf, width=110, force_terminal=True, color_system=None)
    ctx.auto = False
    monkeypatch.setattr(keys, "stdin_is_tty", lambda: True)
    encounter_header(ctx, "5", "The bug", "Propose a change", ["mender", "scribbit", "satchel"])
    return ctx, buf


# ---------------------------------------------------------------- the Pokedex text

def test_every_creature_has_a_pokedex_entry():
    for c in load_creatures().values():
        for field in ("tagline", "definition", "good_for", "weakness", "source", "project"):
            assert c[field].strip(), (c["id"], field)
        assert len(c["tagline"]) <= 60, c["id"]   # it sits under the name in the creature box


def test_short_project_is_the_name_people_know():
    cs = load_creatures()
    assert battle.short_project(cs["octoplug"]) == "MCP" and battle.short_project(cs["chasqui"]) == "A2A"
    assert battle.short_project(cs["mender"]) == "goose" and battle.short_project(cs["satchel"]) == "Agent Skills"


@pytest.mark.parametrize("cid", list(load_creatures()))
def test_every_pokedex_page_fits_110_columns_and_has_the_definition_use_and_weakness(monkeypatch, cid):
    ctx, buf = make_ctx(monkeypatch)
    ctx.console.print(battle.dex_panel(ctx, cid, 1, 3))
    out = buf.getvalue()
    c = ctx.creatures[cid]
    assert all(cell_len(line) <= 110 for line in out.splitlines())
    assert "POKÉDEX" in out and c["name"].upper() in out and c["project"] in out
    for label in ("WHAT IT IS", "GOOD FOR", "WEAKNESS", "MOVES", "STATS"):
        assert label in out
    assert c["tagline"] in out and c["weakness"].split(".")[0][:30] in out
    assert "← → other team members (1/3)" in out


def test_a_pokedex_page_with_no_teammates_does_not_offer_to_flip(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    ctx.console.print(battle.dex_panel(ctx, "dojolotl", 1, 1))
    assert "other team members" not in buf.getvalue()


# ---------------------------------------------------------------- the menu

def test_the_menu_moves_with_the_arrows_and_stops_at_the_edges():
    assert battle.move_cursor(0, "right") == 1 and battle.move_cursor(1, "right") == 1
    assert battle.move_cursor(0, "down") == 2 and battle.move_cursor(2, "down") == 2
    assert battle.move_cursor(3, "left") == 2 and battle.move_cursor(3, "up") == 1
    assert battle.move_cursor(0, "left") == 0 and battle.move_cursor(0, "up") == 0
    assert battle.move_cursor(2, "banana") == 2


def test_the_menu_says_who_fights_whom(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    ctx.console.print(battle.menu_panel(ctx, ctx.creatures["mender"], "5", 1))
    out = buf.getvalue()
    assert "Chambero (goose) vs BUG" in out and "What will Chambero do?" in out
    assert "▶ FIGHT" in out and "POKÉDEX" in out and "REPLAY" in out and "RUN" in out
    assert "Run this step for real" in out and all(cell_len(line) <= 110 for line in out.splitlines())


def test_keys_decode_arrows_enter_and_escape():
    assert [keys.decode_escape(s) for s in ("[A", "[B", "[C", "[D", "OA", "OD", "[1;5C")] == ["up", "down", "right", "left", "up", "left", "right"]
    assert keys.decode_escape("") == "esc" and keys.decode_escape("[Z") == ""
    assert keys.decode_char("\r") == "enter" and keys.decode_char(" ") == "space" and keys.decode_char("R") == "r"
    assert keys.decode_char("\x01") == ""
    with pytest.raises(KeyboardInterrupt):
        keys.decode_char("\x03")


def test_the_first_enter_opens_the_pokedex_and_the_next_ones_lead_to_the_fight(monkeypatch):
    ctx, buf = terminal_ctx(monkeypatch)
    left = press(monkeypatch, "enter", "right", "right", "left", "enter", "enter")   # open, 2nd member, 3rd, back to 2nd, close, FIGHT
    assert battle.interactive(ctx)
    assert battle.choose(ctx, "e5_goose") == "" and left == []
    out = buf.getvalue()
    assert "POKÉDEX  No. 01" in out and "POKÉDEX  No. 04" in out   # goose first, then DeathNote (AGENTS.md)
    assert {"mender", "scribbit", "satchel"} <= ctx.dex_seen


def test_once_read_the_cursor_starts_on_fight(monkeypatch):
    ctx, _ = terminal_ctx(monkeypatch)
    ctx.dex_seen.add("mender")
    left = press(monkeypatch, "enter")
    assert battle.choose(ctx, "e5_goose") == "" and left == []


def test_arrows_pick_replay_and_run(monkeypatch):
    ctx, _ = terminal_ctx(monkeypatch)
    press(monkeypatch, "down", "enter")             # POKEDEX -> REPLAY
    assert battle.choose(ctx, "e5_goose") == "r"
    press(monkeypatch, "right", "down", "enter")    # POKEDEX -> FIGHT -> RUN
    assert battle.choose(ctx, "e5_goose") == "s"


def test_escape_closes_the_pokedex_and_unknown_keys_do_nothing(monkeypatch):
    ctx, _ = terminal_ctx(monkeypatch)
    left = press(monkeypatch, "banana", "enter", "esc", "enter")
    assert battle.choose(ctx, "e5_goose") == "" and left == []


def test_the_engine_asks_with_the_arrow_menu_in_battle_mode(monkeypatch):
    ctx, buf = terminal_ctx(monkeypatch)
    ctx.dex_seen.add("mender")
    press(monkeypatch, "enter")
    assert ctx.attempt("e5_goose", lambda: ctx.say("the real output")) == "LIVE"
    out = buf.getvalue()
    assert "Chambero (goose) used Edit file!" in out and "the real output" in out and "BUG fainted!" in out
    press(monkeypatch, "down", "enter")             # FIGHT -> RUN
    assert ctx.attempt("e5_goose", lambda: ctx.say("never runs")) == "SKIPPED"
    assert "never runs" not in buf.getvalue()


def test_the_plain_pause_waits_for_enter_or_the_right_arrow(monkeypatch):
    ctx, buf = terminal_ctx(monkeypatch)
    left = press(monkeypatch, "up", "left", "x", "right")
    ctx.pause()
    assert left == [] and "ENTER to continue" in buf.getvalue()


def test_scripted_runs_never_wait_for_keys(monkeypatch):
    ctx, _ = make_ctx(monkeypatch)   # auto=True, like the tests, --auto and the recordings

    def boom():
        raise AssertionError("read a key")

    monkeypatch.setattr(keys, "read_key", boom)
    assert not battle.interactive(ctx)
    assert ctx.attempt("e1_doubt", lambda: ctx.say("x")) == "LIVE"
    ctx.pause()
