"""Original 16x16 pixel-art creatures, drawn as text grids.

Generated with AI assistance for this project (no third-party characters, no game IP).
Each grid uses single-letter palette keys; '.' is transparent.
Render in a terminal with half-block characters, or export to PNG for slides:

    uv run bestiary sprites --out assets/sprites
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

# Shared palette (16-bit console style, colour-blind friendly contrasts).
PALETTE = {
    "k": "#1b1b2f",  # outline
    "w": "#f4f4f4",  # white
    "g": "#8b8fa3",  # grey
    "d": "#4a4e69",  # dark grey
    "y": "#f2c14e",  # yellow
    "o": "#f78154",  # orange
    "r": "#d1495b",  # red
    "p": "#b388eb",  # purple
    "m": "#7b4fb3",  # dark purple
    "b": "#4d9de0",  # blue
    "n": "#1f5f99",  # navy
    "c": "#7fd8e8",  # cyan
    "e": "#5fad56",  # green
    "f": "#2e6b30",  # dark green
    "t": "#c08552",  # tan
    "s": "#7a4a2a",  # brown
    "i": "#f6a6b2",  # pink
}

SPRITES: dict[str, list[str]] = {
    # goose -> Mender, a mechanic raccoon holding a wrench
    "mender": [
        "................",
        "..kk........kk..",
        ".kgdk......kdgk.",
        ".kggkkkkkkkkggk.",
        ".kgggggggggggggk",
        "kgkkkkggggkkkkgk",
        "kkwkwkkggkkwkwkk",
        "kgkkkkggggkkkkgk",
        ".kggggwkkwggggk.",
        "..kgggwwwwgggk..",
        "...kkgggggggk.yk",
        "..kddkgggggkkyk.",
        ".kd.kgggggggk.k.",
        ".kd.kggkkkggk...",
        "..k.kssk.kssk...",
        "....kkk...kkk...",
    ],
    # MCP -> Octoplug, an octopus whose arms end in plugs
    "octoplug": [
        "................",
        ".....kkkkkk.....",
        "...kkppppppkk...",
        "..kppppppppppk..",
        "..kpwwkppkwwpk..",
        "..kpwkkppkkwpk..",
        "..kppppppppppk..",
        "..kpppmmmmpppk..",
        "...kpppppppk....",
        "..kpkpkpkpkpk...",
        ".kpk.kpkpk.kpk..",
        ".kp..kp.kp..kpk.",
        "kyk.kyk.kyk..kyk",
        "kyk.kyk.kyk..kyk",
        ".k...k...k....k.",
        "................",
    ],
    # A2A -> Chasqui, an Andean relay runner carrying a knotted cord (quipu)
    "chasqui": [
        "................",
        ".....kkkkk......",
        "....krrorrk.....",
        "...krrrrrrrk....",
        "....ktttttk.....",
        "....ktkttkk.....",
        "....kttttk......",
        "...kkrrrrkk..k..",
        "..ktkroorktk.ky.",
        ".kt.krrrrk.tkyk.",
        ".k..kyyyyk..kk..",
        "....knnnnk......",
        "...knnk.knk.....",
        "..ktk....ktk....",
        ".kssk....kssk...",
        "..kk......kk....",
    ],
    # AGENTS.md -> Scribbit, a living notebook
    "scribbit": [
        "................",
        "...kkkkkkkkkk...",
        "..kbwwwwwwwwk...",
        "..kbwkkwwkkwk...",
        "..kbwkwwwwkwk...",
        "..kbwwwwwwwwk...",
        "..kbwwkkkkwwk...",
        "..kbwwwwwwwwk...",
        "..kbwdddddwwk...",
        "..kbwwwwwwwwk...",
        "..kbwdddddwwk...",
        "..kbwwwwwwwwk...",
        "..kkkkkkkkkkk...",
        "...ktk...ktk....",
        "..kttk...kttk...",
        "...kk.....kk....",
    ],
    # Agent Skills -> Satchel, a backpack with labelled pockets
    "satchel": [
        "................",
        "......kkkk......",
        ".....ks..sk.....",
        "...kkkkkkkkkk...",
        "..ksttttttttsk..",
        "..kttwkttkwttk..",
        "..kttkkttkkttk..",
        "..kttttttttttk..",
        "..kskkkkkkkksk..",
        "..ksyykkyykksk..",
        "..ksyykkyykksk..",
        "..kskkkkkkkksk..",
        "..kssssssssssk..",
        "...kkk....kkk...",
        "...ksk....ksk...",
        "....k......k....",
    ],
    # agentgateway -> Bulwark, a guardian armadillo with a banded shell
    "bulwark": [
        "................",
        "................",
        ".....kkkkkk.....",
        "...kkgdgdgdkk...",
        "..kgdgdgdgdgdk..",
        ".kgdgdgdgdgdgdk.",
        ".kgdgdgdgdgdgdkk",
        "kgdgdgdgdgdgdkik",
        "kgdgdgdgdgdgktwk",
        "kkkkkkkkkkkkttkk",
        "kttttttttttttttk",
        ".kttkttttttkttk.",
        "..ktk.kkkk.ktk..",
        "..kk........kk..",
        "................",
        "................",
    ],
    # Agent Router -> Switchy, a capybara operating a rail switch lever
    "switchy": [
        "................",
        "..............k.",
        ".............kyk",
        "....kkk.....kyk.",
        "...ktttkk..kyk..",
        "..ktttttttkkk...",
        ".kttkwttttttk...",
        ".ktttttttttttk..",
        "kkstttttttttttk.",
        "kssttttttttttttk",
        ".kkttttttttttttk",
        "..ktttttttttttk.",
        "..kttkkkkkkttk..",
        "..ksk......ksk..",
        "..kk........kk..",
        "kkkkkkkkkkkkkkkk",
    ],
    # Open Responses -> Glyphstone, a stone tablet with several scripts
    "glyphstone": [
        "................",
        "....kkkkkkkk....",
        "...kggggggggk...",
        "..kggkgkkgkggk..",
        "..kgggggggggggk.",
        "..kgkkgkgkkggk..",
        "..kggggggggggk..",
        "..kgwkggggwkgk..",
        "..kggggggggggk..",
        "..kgkgkkgkgkgk..",
        "..kggggggggggk..",
        "..kggkkkkkkggk..",
        "..kggggggggggk..",
        "..kddddddddddk..",
        "...kkkkkkkkkk...",
        "................",
    ],
    # OpenSandbox -> Glasshell, a turtle with a glass shell (a bubble inside)
    "glasshell": [
        "................",
        "................",
        "......kkkkk.....",
        "....kkcccccck...",
        "...kccwcccccck..",
        "..kcccccbbcccck.",
        "..kccccbccbccck.",
        "..kcccccbbcccckk",
        "..kkkkkkkkkkkkek",
        ".kekeeeeeeeekkwk",
        ".keeeeeeeeeeeeek",
        "..kek.kkkk.kek..",
        "..kk........kk..",
        "................",
        "................",
        "................",
    ],
    # OpenEnv -> Dojolotl, an axolotl wearing a dojo headband
    "dojolotl": [
        "................",
        ".ik..........ki.",
        "..ik.kkkkkk.ki..",
        "..kikiiiiiikik..",
        "...kiiiiiiiik...",
        "..krrrrrrrrrrk..",
        "..kiikwiiwkiik..",
        "..kiiikiikiiik..",
        "...kiiiiiiiik...",
        "....kiikkiik....",
        "...kiiiiiiiik...",
        "..kiiiwwwwiiik..",
        "..kiikiiiikiik..",
        "...kk.kiik.kk...",
        "......kiik......",
        ".......kk.......",
    ],
}


def _grid(sprite_id: str) -> list[str]:
    rows = SPRITES[sprite_id]
    return [row.ljust(16, ".")[:16] for row in rows[:16]] + ["." * 16] * (16 - len(rows))


def render(sprite_id: str, scale: int = 1) -> Text:
    """Render a sprite with upper-half blocks: one cell = 1 x 2 pixels."""
    grid = _grid(sprite_id)
    if scale > 1:
        grid = [("".join(ch * scale for ch in row)) for row in grid for _ in range(scale)]
    out = Text()
    for y in range(0, len(grid), 2):
        top, bottom = grid[y], grid[y + 1] if y + 1 < len(grid) else "." * len(grid[y])
        for a, b in zip(top, bottom):
            fa, fb = PALETTE.get(a), PALETTE.get(b)
            if fa and fb:
                out.append("▀", style=f"{fa} on {fb}")
            elif fa:
                out.append("▀", style=fa)
            elif fb:
                out.append("▄", style=fb)
            else:
                out.append(" ")
        out.append("\n")
    out.rstrip()
    return out


def export_png(out_dir: Path, pixel: int = 24) -> list[Path]:
    """Export every sprite as a PNG (needs pillow: uv sync --extra art)."""
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for sprite_id in SPRITES:
        img = Image.new("RGBA", (16 * pixel, 16 * pixel), (0, 0, 0, 0))
        for y, row in enumerate(_grid(sprite_id)):
            for x, ch in enumerate(row):
                colour = PALETTE.get(ch)
                if not colour:
                    continue
                rgb = tuple(int(colour[i : i + 2], 16) for i in (1, 3, 5))
                for dy in range(pixel):
                    for dx in range(pixel):
                        img.putpixel((x * pixel + dx, y * pixel + dy), (*rgb, 255))
        path = out_dir / f"{sprite_id}.png"
        img.save(path)
        written.append(path)
    return written
