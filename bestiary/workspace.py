"""The working copy of the toy upstream project (farolito) used during a game."""

from __future__ import annotations

import difflib
import json
import shutil
from pathlib import Path

from bestiary.config import REFERENCE_FIX, STATE_DIR, UPSTREAM_TEMPLATE, WORK_DIR

IGNORED = {"__pycache__", ".pytest_cache"}


def reset() -> Path:
    """Fresh copy of the upstream template, plus an empty local forge."""
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    shutil.copytree(UPSTREAM_TEMPLATE, WORK_DIR, ignore=shutil.ignore_patterns(*IGNORED))
    forge = STATE_DIR / "forge"
    if forge.exists():
        shutil.rmtree(forge)
    (forge / "branches").mkdir(parents=True)
    (forge / "pulls").mkdir()
    shutil.copy(UPSTREAM_TEMPLATE / "issues.json", forge / "issues.json")
    return WORK_DIR


def ensure() -> Path:
    if not WORK_DIR.exists():
        reset()
    return WORK_DIR


def _files(root: Path) -> dict[str, bytes]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (set(p.relative_to(root).parts) & IGNORED) and p.name != "issues.json":
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def changed_files() -> dict[str, str]:
    """Files in the working copy that differ from upstream: {path: new_text}."""
    ensure()
    base, work = _files(UPSTREAM_TEMPLATE), _files(WORK_DIR)
    return {
        path: data.decode("utf-8", errors="replace")
        for path, data in work.items()
        if base.get(path) != data
    }


def unified_diff() -> str:
    ensure()
    base = _files(UPSTREAM_TEMPLATE)
    chunks = []
    for path, new_text in changed_files().items():
        old = base.get(path, b"").decode("utf-8", errors="replace").splitlines(keepends=True)
        new = new_text.splitlines(keepends=True)
        chunks.append("".join(difflib.unified_diff(old, new, f"a/{path}", f"b/{path}")))
    return "\n".join(chunks)


def apply_reference_fix() -> None:
    """Used only when goose cannot run live: puts the known-good fix in place (shown as REPLAY)."""
    ensure()
    shutil.copy(REFERENCE_FIX, WORK_DIR / "farolito" / "cli.py")


def read_issues() -> list[dict]:
    ensure()
    path = STATE_DIR / "forge" / "issues.json"
    if not path.exists():
        reset()
    return json.loads(path.read_text(encoding="utf-8"))
