"""Spanish for the text the game itself writes (BESTIARY_LANG=es, the default; en keeps the English).

What is translated: the screens, the narration, the table headings, the creature and obstacle texts. What is not:
the raw output of the real calls (JSON, goose's trace, the model's answers), code, file contents (AGENTS.md, the
skills) and the goose prompt. Those are what the components really said, and translating a prompt would change the
reliability that was measured with it.

`t("English source text", name=value)` returns the Spanish text when the language is es and the text is in the
catalog (bestiary/i18n_es.py); otherwise the English text. The English text is the key, so a string that has no
translation yet still shows, and tests/test_i18n.py checks that every literal passed to t() or ctx.say() has one.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

DATA = Path(__file__).parent / "data"


def lang() -> str:
    """'es' (default) or 'en'. Read on every call, so a test or a flag can change it."""
    value = (os.environ.get("BESTIARY_LANG") or "es").strip().lower()
    return "en" if value.startswith("en") else "es"


def is_es() -> bool:
    return lang() == "es"


def t(msg: str, **kw) -> str:
    if is_es():
        from bestiary.i18n_es import ES

        msg = ES.get(msg, msg)
    return msg.format(**kw) if kw else msg


def category_label(category: str, nice: bool = False) -> str:
    """The category as shown: 'PROTOCOL' -> 'PROTOCOLO' in Spanish, the English key as is otherwise.
    `nice` gives the sentence-style version used in the boxes: 'Protocolo', 'Formato de instrucciones', 'Instruction Format'."""
    if is_es():
        from bestiary.i18n_es import CATEGORIES, CATEGORIES_NICE

        return (CATEGORIES_NICE if nice else CATEGORIES).get(category, category)
    return category.title() if nice else category


def localized_yaml(name: str) -> list | dict | None:
    """data/<name>.es.yaml when the language is Spanish and the file exists."""
    if not is_es():
        return None
    path = DATA / f"{name}.es.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
