import os
import subprocess
import sys
from pathlib import Path

from bestiary.sprites import PALETTE, SPRITES, render

ROOT = Path(__file__).resolve().parent.parent


def test_sprites_are_valid_16x16():
    assert len(SPRITES) == 10
    for name, rows in SPRITES.items():
        assert len(rows) == 16, name
        assert all(len(r) == 16 for r in rows), name
        assert set("".join(rows)) <= set(PALETTE) | {"."}, name
        assert render(name).plain.strip()


def test_upstream_bug_and_reference_fix(tmp_path):
    import shutil

    work = tmp_path / "farolito"
    shutil.copytree(ROOT / "upstream" / "farolito", work)
    bug = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=work, capture_output=True, text=True)
    assert bug.returncode != 0
    shutil.copy(ROOT / "upstream" / "reference_fix" / "cli.py", work / "farolito" / "cli.py")
    ok = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=work, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout


def test_full_game_runs_unattended(fake_model):
    env = dict(os.environ, BESTIARY_FORGE_PORT="28765", BESTIARY_REVIEWER_PORT="29999", BESTIARY_GATEWAY_URL="http://localhost:1/mcp", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "bestiary.cli", "play", "--auto", "--width", "120"],
                       cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=240)
    assert r.returncode == 0, r.stderr[-2000:]
    out = r.stdout
    assert "The map" in out
    assert "MCP answered, and no model was involved" in out
    assert "VERDICT: approve" in out
    assert "forge://farolito/pull/" in out
    assert "Traceback" not in r.stderr
