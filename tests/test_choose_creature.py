"""You choose the creature: the CREATURES list, the 'not very effective' feedback, and the creature that stays on the field.

The key presses are scripted. Creature order in the list (data/creatures.yaml): 0 mender (goose), 1 octoplug (MCP), 2 chasqui (A2A),
3 scribbit (AGENTS.md), 4 satchel (Agent Skills), 5 bulwark (agentgateway), 6 switchy (Agent Router), 7 glyphstone (Open Responses),
8 glasshell (OpenSandbox), 9 dojolotl (OpenEnv). Menu cells: 0 FIGHT, 1 CREATURES, 2 POKEDEX, 3 REPLAY, 4 RUN."""

import pytest
from rich.cells import cell_len

from bestiary import battle
from bestiary.engine import encounter_header
from test_battle_menu import make_ctx, press, terminal_ctx


def flat(text: str) -> str:
    """The panels wrap long lines inside their borders: compare the words, not the layout."""
    return " ".join(text.replace("│", " ").split())


def injection(monkeypatch):   # the right creature is bulwark (agentgateway)
    return terminal_ctx(monkeypatch, pick="choose", number="3", title="Injection", step="Stay safe", ids=("bulwark",))


# ---------------------------------------------------------------- the scene while nobody has been sent out

def test_the_scene_has_no_creature_until_you_send_one(monkeypatch):
    ctx, buf = injection(monkeypatch)
    out = buf.getvalue()
    assert battle.picking(ctx)
    assert "OBSTACLE" in out and "INJECTION" in out and "What it is:" in out
    assert "Nobody is on the field yet." in out and "You have the ten creatures" in out
    assert "weak to:" not in out and "Your team:" not in out and "RONDERO" not in out   # nothing gives the answer away


def test_the_kubernetes_region_still_shows_its_creature(monkeypatch):
    ctx, buf = make_ctx(monkeypatch, pick="choose")
    battle.intro(ctx, "K8s", "Kubernetes region", "Share it with many teams", ["bulwark"])
    assert "RONDERO" in buf.getvalue() and "YOUR CREATURE" in buf.getvalue()   # there is no menu in that scene: nothing to choose


# ---------------------------------------------------------------- the list of creatures

def test_the_creature_list_shows_the_ten_with_what_each_is_good_for(monkeypatch):
    ctx, buf = make_ctx(monkeypatch)
    ctx.current_number = "3"
    ctx.console.print(battle.creatures_panel(ctx, "3", 5, "octoplug"))
    out = buf.getvalue()
    assert all(c["name"] in out for c in ctx.creatures.values())
    assert "Chaka ✓" in out and "▶ Rondero" in out            # on the field, and the cursor
    assert "GOOD FOR" in out and "WEAKNESS" in out and "Hiding dangerous tools" in out
    assert "INJECTION: Hidden text in the issue says: delete the main branch." in out   # the problem stays in view while you choose
    assert all(cell_len(line) <= 110 for line in out.splitlines()) and len(out.splitlines()) <= 20


# ---------------------------------------------------------------- choosing

def test_the_wrong_creature_is_not_effective_and_the_right_one_goes_in(monkeypatch):
    ctx, buf = injection(monkeypatch)
    left = press(monkeypatch,
                 "enter", "down", "enter",                      # CREATURES, down to Chaka (MCP), send out
                 "enter",                                        # FIGHT with the wrong one: not effective
                 "enter", "down", "down", "down", "down", "enter",   # CREATURES again (the cursor is there), down to Rondero, send out
                 "enter")                                        # FIGHT: it goes
    assert battle.choose(ctx, "e3_gateway") == "" and left == []
    out = flat(buf.getvalue())
    assert "Not very effective! Chaka (MCP) is not the best choice against INJECTION." in out
    assert "Hint: You need something outside the model that decides which tools exist for it." in out
    assert ctx.chosen == "bulwark"


def test_fighting_with_nobody_on_the_field_asks_you_to_choose(monkeypatch):
    ctx, buf = terminal_ctx(monkeypatch, pick="choose")
    left = press(monkeypatch, "left", "enter",                  # the cursor starts on CREATURES: go to FIGHT with nobody out
                 "enter", "enter",                               # the notice sends the cursor to CREATURES: open it, send goose out
                 "enter")                                        # FIGHT
    assert battle.choose(ctx, "e5_goose") == "" and left == []
    assert "Choose a creature first: pick CREATURES in the menu." in flat(buf.getvalue()) and ctx.chosen == "mender"


def test_replay_is_blocked_for_the_wrong_creature_but_run_always_works(monkeypatch):
    ctx, buf = terminal_ctx(monkeypatch, pick="choose", number="1", title="How do I run the tests?", step="Consult information", ids=("scribbit",))
    left = press(monkeypatch, "enter", "enter",                 # CREATURES, send goose out (the right one is AGENTS.md)
                 "4", "enter",                                   # REPLAY with the wrong one: blocked
                 "5", "enter")                                   # RUN: allowed
    assert battle.choose(ctx, "e1_doubt") == "s" and left == []
    assert "Not very effective! Chambero (goose) is not the best choice against DOUBT." in flat(buf.getvalue())


def test_escape_goes_back_from_the_list_without_choosing(monkeypatch):
    ctx, _ = injection(monkeypatch)
    left = press(monkeypatch, "enter", "down", "esc", "5", "enter")
    assert battle.choose(ctx, "e3_gateway") == "s" and left == [] and ctx.chosen is None


def test_the_pokedex_flips_through_all_ten_creatures(monkeypatch):
    ctx, buf = injection(monkeypatch)
    left = press(monkeypatch, "3", "enter", *["right"] * 9, "enter", "5", "enter")   # POKEDEX, to the last entry, back, RUN
    assert battle.choose(ctx, "e3_gateway") == "s" and left == []
    out = buf.getvalue()
    assert "POKÉDEX  No. 01" in out and "POKÉDEX  No. 10" in out and "← → other creatures (10/10)" in out
    assert len(ctx.dex_seen) == 10 and ctx.chosen is None


# ---------------------------------------------------------------- through the engine

def test_the_wrong_creature_never_runs_the_step(monkeypatch):
    ctx, buf = injection(monkeypatch)
    ran = []
    press(monkeypatch, "enter", "down", "enter", "enter", "5", "enter")   # send Chaka out, FIGHT (blocked), then RUN
    assert ctx.attempt("e3_gateway", lambda: ran.append(1)) == "SKIPPED" and ran == []
    assert "Go, Chaka" not in buf.getvalue()


def test_the_creature_enters_the_field_once_and_stays_for_the_next_step(monkeypatch):
    ctx, buf = terminal_ctx(monkeypatch, pick="choose", number="2", title="The issue in the fog", step="Read the issue", ids=("octoplug",))
    press(monkeypatch, "enter", "down", "enter", "enter")                 # CREATURES, Chaka, send out, FIGHT
    assert ctx.attempt("e2a_mcp_direct", lambda: ctx.say("part A")) == "LIVE"
    press(monkeypatch, "enter")                                           # part B: Chaka is still there, FIGHT
    assert ctx.attempt("e2b_minimal_agent", lambda: ctx.say("part B")) == "LIVE"
    out = buf.getvalue()
    assert out.count("Go, Chaka (MCP)!") == 1 and "Chaka (MCP) used tools/list!" in out and "Chaka (MCP) used tools/call!" in out
    assert "FOG fainted!" in out


def test_a_new_encounter_starts_with_an_empty_field(monkeypatch):
    ctx, _ = terminal_ctx(monkeypatch, pick="choose", number="2", title="The issue in the fog", step="Read the issue", ids=("octoplug",))
    ctx.chosen, ctx.sent_out = "octoplug", "octoplug"
    encounter_header(ctx, "3", "Injection", "Stay safe", ["bulwark"])
    assert ctx.chosen is None and ctx.sent_out is None


# ---------------------------------------------------------------- the other mode, and scripted runs

def test_with_pick_auto_the_right_creature_is_already_on_the_field(monkeypatch):
    ctx, buf = terminal_ctx(monkeypatch, pick="auto", number="3", title="Injection", step="Stay safe", ids=("bulwark",))
    assert not battle.picking(ctx) and "RONDERO" in buf.getvalue()
    press(monkeypatch, "enter", "enter", "enter")                         # POKEDEX the first time, back, FIGHT
    assert battle.choose(ctx, "e3_gateway") == "" and ctx.chosen == "bulwark"


def test_scripted_runs_put_the_right_creature_on_the_field_without_keys(monkeypatch):
    ctx, buf = make_ctx(monkeypatch, pick="choose")                       # auto=True: tests, --auto, recordings
    encounter_header(ctx, "5", "The bug", "Propose a change", ["mender", "scribbit", "satchel"])
    assert not battle.picking(ctx) and "Your team:" in buf.getvalue()
    assert ctx.attempt("e5_goose", lambda: ctx.say("real")) == "LIVE"


@pytest.mark.parametrize("attempt", [a for a in battle.MOVES if a != "ek_kubernetes"])
def test_every_step_has_one_right_creature_and_a_hint_for_the_others(attempt):
    from bestiary.engine import load_creatures

    cid, skill_index, _ = battle.MOVES[attempt]
    assert cid in load_creatures() and skill_index < len(load_creatures()[cid]["skills"])
