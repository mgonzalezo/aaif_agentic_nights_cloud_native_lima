# Contributing

Thanks for helping. Small, focused pull requests are easiest to review.

## Development

```bash
uv sync --all-extras
uv run pytest -q
```

Tests use a fake model server (`tests/fake_model.py`), so no Ollama or API key is needed.

## Adding a project (creature number 11)

1. Add an entry to `bestiary/data/creatures.yaml` with a `why` for every stat and a
   primary `source` URL.
2. Draw an original 16x16 sprite in `bestiary/sprites.py` (no third-party characters
   or logos).
3. Add an encounter function in `bestiary/encounters.py` and put it in `ORDER`.
4. If it makes a real call, give it a DIDACTIC fallback and record a replay.

## Rules

- Never fake a LIVE step. If it is simulated, it must use the DIDACTIC badge.
- Replays must come from real runs (`uv run bestiary record`).
- Do not add project logos or mascots. Use project names only to refer to the projects.
- Sign off your commits (`git commit -s`).
