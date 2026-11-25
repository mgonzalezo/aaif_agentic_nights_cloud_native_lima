"""Finds every English text the game passes through the translator, so that tests can check each one has a Spanish version.

A string counts when it is a literal in: tr("..."), ctx.say("..."), ctx.wire("..."), ctx.code(source, "..."),
encounter_header(ctx, number, "title", "step", ...) and the first and third arguments of row() in the doctor; plus the
text tables that are read by name (menu hints, outcomes, category rules, where the creatures run) and a few headings
that are looped over. Texts built with f-strings are not literals: they go through tr("... {x} ...", x=...).
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "bestiary"

# literal headings that are looped over (tr(col) in a for loop), so no call site shows them
LOOPED = [
    "Skill", "Description (always loaded)", "Full SKILL.md",
    "Creature", "Stands for", "Category", "Autonomy", "Reach", "Control", "Startup",
    "autonomy", "reach", "control", "startup", "AUT", "REA", "CTL", "COST",
    "Enter to continue", "[Enter] run live   [r] show replay   [s] skip", "ENTER to continue", "ENTER to start",
    "WHAT IT IS", "GOOD FOR", "WEAKNESS", "MOVES", "IN THE GAME", "STATS", "LEARN MORE",
]


def _literal(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _called(node: ast.Call) -> str:
    fn = node.func
    return fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""


def from_calls() -> dict[str, str]:
    """text -> 'file:line' of the first place that uses it."""
    found: dict[str, str] = {}

    def add(node, path, text):
        if text and text.strip() and text not in found:
            found[text] = f"{path.name}:{node.lineno}"

    for path in sorted(ROOT.glob("*.py")):
        if path.name in ("i18n.py", "i18n_es.py"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name, args = _called(node), node.args
            if name == "tr":
                add(node, path, _literal(args[0]))
            elif name in ("say", "wire"):
                add(node, path, _literal(args[0]))
            elif name == "code" and len(args) > 1:
                add(node, path, _literal(args[1]))
            elif name in ("encounter_header", "intro") and len(args) >= 4:
                add(node, path, _literal(args[2]))
                add(node, path, _literal(args[3]))
            elif name == "row" and path.name == "cli.py" and len(args) >= 3:
                add(node, path, _literal(args[0]))
                add(node, path, _literal(args[2]))
    return found


def from_tables() -> dict[str, str]:
    from bestiary import battle, engine, where

    found: dict[str, str] = {}
    for label, _, hint in battle.CHOICES:
        found[label] = "battle.CHOICES"
        found[hint] = "battle.CHOICES"
    for text in battle.OUTCOME.values():
        found[text] = "battle.OUTCOME"
    for _, _, achieved in battle.MOVES.values():
        found[achieved] = "battle.MOVES"
    for text in engine.CATEGORY_RULES.values():
        found[text] = "engine.CATEGORY_RULES"
    for _, detail in where.PLACEMENT.values():
        found[detail] = "where.PLACEMENT"
    for detail in where.LAPTOP_DETAIL.values():
        found[detail] = "where.LAPTOP_DETAIL"
    for text in ("local process", "console pod", "namespace opensandbox", "a sandbox pod created per run by OpenSandbox"):
        found.setdefault(text, "where")
    for text in LOOPED:
        found.setdefault(text, "looped headings")
    return found


def needed() -> dict[str, str]:
    found = from_tables()
    found.update({k: v for k, v in from_calls().items() if k not in found})
    return found


if __name__ == "__main__":   # python tests/i18n_scan.py  -> every text that needs a Spanish version
    import sys

    sys.path.insert(0, str(ROOT.parent))
    for text, where_ in needed().items():
        print(f"{where_:28} {text!r}")
