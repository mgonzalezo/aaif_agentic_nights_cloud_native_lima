"""The game speaks Spanish (Latin America) by default: every text it writes has a translation, the data files are
complete, and a whole run in Spanish works. The raw output of the real calls stays as it came."""

import os
import string
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from bestiary import battle, i18n
from bestiary.engine import load_creatures
from bestiary.i18n_es import CATEGORIES, CATEGORIES_NICE, ES, OPPONENT_NAMES
from i18n_scan import needed
from test_battle_menu import make_ctx, press, terminal_ctx

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "bestiary" / "data"


def spanish(monkeypatch):
    monkeypatch.setenv("BESTIARY_LANG", "es")


# ---------------------------------------------------------------- the translator

def test_spanish_is_the_default_and_english_is_one_variable_away(monkeypatch):
    monkeypatch.delenv("BESTIARY_LANG", raising=False)
    assert i18n.lang() == "es"
    monkeypatch.setenv("BESTIARY_LANG", "en")
    assert i18n.lang() == "en" and i18n.t("The map") == "The map"
    monkeypatch.setenv("BESTIARY_LANG", "EN-us")
    assert i18n.lang() == "en"


def test_t_translates_formats_and_falls_back_to_the_english_text(monkeypatch):
    spanish(monkeypatch)
    assert i18n.t("The map") == "El mapa"
    assert i18n.t("Go, {name} ({project})!", name="Chaka", project="MCP") == "¡Adelante, Chaka (MCP)!"
    assert i18n.t("A text nobody translated yet") == "A text nobody translated yet"
    assert i18n.t("braces {stay} when nothing is passed") == "braces {stay} when nothing is passed"


def test_every_text_the_game_writes_has_a_spanish_version():
    missing = {text: where for text, where in needed().items() if text not in ES}
    assert not missing, "add these to bestiary/i18n_es.py:\n" + "\n".join(f"  {where}: {text!r}" for text, where in missing.items())


def test_a_translation_keeps_the_same_placeholders_and_no_banned_words():
    def fields(text):
        return {name for _, name, _, _ in string.Formatter().parse(text) if name}

    for english, es in ES.items():
        assert fields(english) == fields(es), (english, es)
        assert "corrida" not in es.lower(), es   # never, in the talk: it is "ejecución"
    assert set(CATEGORIES) == set(CATEGORIES_NICE) == {"AGENT", "PROTOCOL", "INSTRUCTION FORMAT", "GATEWAY", "API SPECIFICATION", "SANDBOX", "TRAINING ENVIRONMENT"}
    assert set(OPPONENT_NAMES) == set(battle.OPPONENT_OF.values())


# ---------------------------------------------------------------- the data files

def test_the_creatures_in_spanish_cover_every_creature_and_every_skill(monkeypatch):
    base = yaml.safe_load((DATA / "creatures.yaml").read_text(encoding="utf-8"))
    es = {c["id"]: c for c in yaml.safe_load((DATA / "creatures.es.yaml").read_text(encoding="utf-8"))}
    assert set(es) == {c["id"] for c in base}
    for c in base:
        item = es[c["id"]]
        for field in ("animal", "joined_aaif", "tagline", "definition", "good_for", "weakness"):
            assert item[field].strip(), (c["id"], field)
        assert len(item["skills"]) == len(c["skills"]) and all(s["name"] and s["does"] for s in item["skills"]), c["id"]
        assert len(item["tagline"]) <= 75, c["id"]
        assert "corrida" not in " ".join(str(v) for v in item.values()).lower()
    spanish(monkeypatch)
    creatures = load_creatures()
    assert creatures["mender"]["name"] == "Chambero" and creatures["mender"]["project"] == "goose"          # names stay
    assert creatures["mender"]["tagline"].startswith("Agente de IA abierto") and creatures["mender"]["skills"][1]["name"] == "Editar archivo"
    assert creatures["octoplug"]["stats"] == {"autonomy": 0, "reach": 3, "control": 1, "startup": 1}        # numbers stay
    monkeypatch.setenv("BESTIARY_LANG", "en")
    assert load_creatures()["mender"]["tagline"].startswith("Open-source AI agent")


def test_the_obstacles_in_spanish_have_the_same_fields_as_the_english_ones(monkeypatch):
    base = yaml.safe_load((DATA / "obstacles.yaml").read_text(encoding="utf-8"))
    es = yaml.safe_load((DATA / "obstacles.es.yaml").read_text(encoding="utf-8"))
    assert set(es) == set(base)
    for oid, entry in es.items():
        assert set(entry) == set(base[oid]) == {"short", "what", "problem", "hint"}, oid
        assert all(v.strip() for v in entry.values()) and "corrida" not in " ".join(entry.values()).lower()
    spanish(monkeypatch)
    assert battle.obstacle_info("5")["short"].startswith("farolito se cae")
    monkeypatch.setenv("BESTIARY_LANG", "en")
    assert battle.obstacle_info("5")["short"].startswith("farolito crashes")


# ---------------------------------------------------------------- the screens in Spanish

def test_the_arena_in_spanish_shows_the_obstacle_and_the_empty_field(monkeypatch):
    spanish(monkeypatch)
    ctx, buf = terminal_ctx(monkeypatch, pick="choose", number="3", title="Injection", step="Stay safe", ids=("bulwark",))
    out = buf.getvalue()
    assert "Encuentro 3: Inyección" in out and "¡Apareció INYECCIÓN!" in out and "Mantenerse a salvo" in out
    assert "OBSTÁCULO" in out and "TU CRIATURA" in out and "Qué es:" in out and "Por qué es un problema:" in out
    assert "Todavía no hay nadie en el campo." in out and "PS" in out
    assert "Obstacle" not in out and "YOUR CREATURE" not in out and "A wild" not in out


def test_the_menu_and_the_feedback_in_spanish(monkeypatch):
    spanish(monkeypatch)
    ctx, buf = terminal_ctx(monkeypatch, pick="choose", number="3", title="Injection", step="Stay safe", ids=("bulwark",))
    press(monkeypatch, "enter", "down", "enter", "enter",                    # CRIATURAS, Chaka, enviar, LUCHAR (equivocada)
          "enter", "down", "down", "down", "down", "enter", "enter")        # otra vez CRIATURAS, Rondero, enviar, LUCHAR
    assert battle.choose(ctx, "e3_gateway") == ""
    out = " ".join(buf.getvalue().replace("│", " ").split())
    for text in ("LUCHAR", "CRIATURAS", "POKÉDEX", "REPETICIÓN", "HUIR", "¿Qué criatura mandas contra INYECCIÓN?",
                 "¡No es muy eficaz! Chaka (MCP) no es la mejor opción contra INYECCIÓN.",
                 "Pista: Necesitas algo fuera del modelo que decida qué herramientas existen para él.",
                 "mover", "elegir", "CRIATURAS · ¿quién resuelve esto?"):
        assert text in out, text
    assert "Hint:" not in out and "FIGHT" not in out


def test_the_step_in_spanish_goes_through_the_whole_fight(monkeypatch):
    spanish(monkeypatch)
    ctx, buf = terminal_ctx(monkeypatch, pick="choose", number="1", title="How do I run the tests?", step="Consult information", ids=("scribbit",))
    press(monkeypatch, "enter", "down", "down", "down", "enter", "enter")   # CRIATURAS, hasta DeathNote, enviar, LUCHAR
    assert ctx.attempt("e1_doubt", lambda: ctx.say("Aura loaded: {n}")) == "LIVE"
    out = " ".join(buf.getvalue().replace("│", " ").split())
    assert "¡Adelante, DeathNote (AGENTS.md)!" in out and "¡DeathNote (AGENTS.md) usó Cómo correr esto!" in out
    assert "¡DUDA cayó! ¡Es supereficaz!" in out and "Un simple archivo Markdown respondió la pregunta." in out
    assert "¡DeathNote (AGENTS.md) ganó experiencia!" in out and "DERROTADO" in out


def test_the_pokedex_in_spanish(monkeypatch):
    spanish(monkeypatch)
    ctx, buf = make_ctx(monkeypatch)
    ctx.console.print(battle.dex_panel(ctx, "bulwark", 6, 10))
    out = " ".join(buf.getvalue().replace("│", " ").split())
    for text in ("POKÉDEX No. 06", "RONDERO", "agentgateway", "armadillo guardián", "Gateway", "entró a la AAIF", "QUÉ ES", "SIRVE PARA",
                 "DEBILIDAD", "MOVIMIENTOS", "EN EL JUEGO", "ESTADÍSTICAS", "ALC", "COSTO", "MÁS INFO", "Lista de permitidos", "← → otras criaturas (6/10)"):
        assert text in out, text


def test_the_classic_screens_and_the_rest_in_spanish(monkeypatch):
    spanish(monkeypatch)
    from bestiary.engine import creature_card, team_table
    from rich.console import Console
    import io

    buf = io.StringIO()
    console = Console(file=buf, width=120, force_terminal=False, color_system=None)
    creatures = load_creatures()
    console.print(team_table(creatures, highlight="autonomy"))
    console.print(creature_card(creatures["mender"], where="pod/console"))
    out = buf.getvalue()
    for text in ("Criatura", "Representa a", "Categoría", "Autonomía", "Alcance", "Arranque", "AGENTE", "representa a: goose", "corre en: pod/console", "autonomía"):
        assert text in out, text


def test_where_the_creatures_run_in_spanish(monkeypatch):
    spanish(monkeypatch)
    ctx, _ = make_ctx(monkeypatch)
    assert "proceso de la CLI de goose" in ctx.where.describe("mender") and ctx.where.describe("mender").startswith("host ")
    monkeypatch.setenv("BESTIARY_PROFILE", "cloud")
    monkeypatch.setenv("POD_NAME", "console-1")
    monkeypatch.setenv("NODE_NAME", "node-a")
    from bestiary.config import Settings
    from bestiary.where import Where

    where = Where(settings=Settings(), kubectl=lambda a: "reviewer-1 node-a")
    assert where.describe("mender") == "pod/console-1 en el nodo node-a: contenedor console (goose)"
    assert where.describe("glasshell") == "namespace opensandbox: un pod sandbox que OpenSandbox crea en cada ejecución"


@pytest.mark.skipif(os.environ.get("SKIP_SUBPROCESS"), reason="slow")
def test_the_whole_game_runs_in_spanish(fake_model):
    env = dict(os.environ, BESTIARY_LANG="es", BESTIARY_UI="battle", BESTIARY_FORGE_PORT="28768", BESTIARY_REVIEWER_PORT="29998",
               BESTIARY_GATEWAY_URL="http://localhost:1/mcp", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "bestiary.cli", "play", "--auto", "--width", "120"], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=240)
    assert r.returncode == 0, r.stderr[-2000:]
    out = r.stdout
    for text in ("Encuentro 0: El laboratorio", "Encuentro 5: El bug", "¡Apareció BUG!", "Mito 1 cerrado", "Encuentro K8s: región de Kubernetes", "Compartirlo con muchos equipos", "El mapa",
                 "Proyecto personal no oficial; no avalado por la AAIF ni la Linux Foundation.", "modelo:"):
        assert text in out, text
    assert "Traceback" not in r.stderr and "A wild" not in out and "Encounter 0" not in out
