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
    assert keys.decode_escape("") == "esc" and keys.decode_escape("[99~") == ""
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


# ---------------------------------------------------------------- terminals that send arrows differently

def feed(text):
    """read_escape() reads one character at a time; None means nothing else arrived in time."""
    it = iter(text)
    return lambda: next(it, None)


@pytest.mark.parametrize("sent,key", [
    ("[A", "up"), ("[B", "down"), ("[C", "right"), ("[D", "left"),        # the usual ESC [ A
    ("OA", "up"), ("OB", "down"), ("OC", "right"), ("OD", "left"),        # application cursor mode: ESC O A
    ("[1;5C", "right"), ("[1;2A", "up"),                                   # with Ctrl or Shift
    ("[38;72;0;1;0;1_", "up"), ("[40;80;0;1;0;1_", "down"),               # Windows Terminal win32-input-mode
    ("[37;75;0;1;0;1_", "left"), ("[39;77;0;1;0;1_", "right"),
    ("[13;28;13;1;0;1_", "enter"), ("[87;17;119;1;0;1_", "w"),
    ("[38;72;0;0;0;1_", ""),                                              # the key-up half of the same press: ignored
    ("[Z", "backtab"), ("", "esc"),
])
def test_every_known_way_of_sending_an_arrow_is_understood(sent, key):
    assert keys.decode_escape(keys.read_escape(feed(sent))) == key


def test_an_escape_o_sequence_is_read_whole_and_nothing_is_left_over():
    rest = iter("OAxyz")
    assert keys.read_escape(lambda: next(rest, None)) == "OA"
    assert next(rest) == "x"   # the A was not left behind to be read as a letter


def test_an_unknown_sequence_is_reported_not_swallowed():
    assert keys.decode_escape(keys.read_escape(feed("[99~"))) == ""


def test_other_keys_move_the_cursor_too(monkeypatch):
    ctx, _ = terminal_ctx(monkeypatch)
    ctx.dex_seen.add("mender")
    press(monkeypatch, "s", "d", "enter")           # FIGHT -> down (RUN) -> right (stays) ... Enter
    assert battle.choose(ctx, "e5_goose") == "s"
    press(monkeypatch, "h", "j", "l", "enter")       # FIGHT -> left (POKEDEX) -> down (REPLAY) -> right (RUN)
    assert battle.choose(ctx, "e5_goose") == "s"
    press(monkeypatch, "3", "enter")                 # a digit jumps to that choice
    assert battle.choose(ctx, "e5_goose") == "r"
    press(monkeypatch, "tab", "enter")               # Tab goes to the next choice (FIGHT -> REPLAY)
    assert battle.choose(ctx, "e5_goose") == "r"
    left = press(monkeypatch, "backtab", "enter", "enter", "enter")   # Shift+Tab -> POKEDEX; Enter opens it, Enter closes, Enter fights
    assert battle.choose(ctx, "e5_goose") == "" and left == []


def test_the_menu_says_when_a_key_was_not_recognised(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    monkeypatch.setattr(keys, "unknown", "ESC [ 9 9 ~")
    ctx.console.print(battle.menu_panel(ctx, ctx.creatures["mender"], "5", 0))
    assert "key not recognised: ESC [ 9 9 ~" in buf.getvalue()


def test_the_wait_between_screens_accepts_the_alternatives_too(monkeypatch):
    ctx, _ = terminal_ctx(monkeypatch)
    left = press(monkeypatch, "x", "d")
    ctx.pause()
    assert left == []


# ---------------------------------------------------------------- the enemies explain themselves

def test_every_obstacle_says_what_it_is_and_why_it_is_a_problem():
    from bestiary.opponents import NAMES

    info = battle.load_obstacles()
    assert set(info) == set(battle.OPPONENT_OF.values()) == set(NAMES)
    for oid, entry in info.items():
        assert set(entry) == {"short", "what", "problem"}, oid
        assert all(entry[k].strip() for k in entry), oid
        assert len(entry["short"]) <= 70, oid   # one line in the menu


@pytest.mark.parametrize("number", list(battle.OPPONENT_OF))
def test_the_arena_shows_the_description_of_the_monster(monkeypatch, number):
    ctx, buf = make_ctx(monkeypatch)
    encounter_header(ctx, number, "title", "step", ["scribbit"])
    out = buf.getvalue()
    entry = battle.obstacle_info(number)
    flat = " ".join(out.replace("│", " ").split())
    assert "What it is:" in out and "Why it is a problem:" in out
    assert " ".join(entry["what"].split()[:6]) in flat and " ".join(entry["problem"].split()[:6]) in flat
    assert all(cell_len(line) <= 110 for line in out.splitlines())


def test_the_menu_repeats_the_monster_in_one_line(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    ctx.console.print(battle.menu_panel(ctx, ctx.creatures["mender"], "5", 1))
    assert "BUG: farolito crashes with a traceback" in buf.getvalue()


def test_the_card_after_the_fight_stays_compact(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    ctx.current_number = "1"
    battle.outcome(ctx, "e1_doubt", "LIVE", "1")
    assert "FAINTED" in buf.getvalue() and "What it is:" not in buf.getvalue()


def test_raw_mode_is_harmless_when_there_is_no_terminal():
    with keys.raw_mode():
        with keys.raw_mode():   # nested: the inner one changes nothing
            pass
