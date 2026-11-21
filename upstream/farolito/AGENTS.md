# AGENTS.md

## How to run the tests
- `python -m pytest -q` from the repository root. No network needed.

## Repo rules
- Keep changes to one file when possible.
- Error messages go to stderr and start with `farolito: `.
- A missing or unreadable config file must exit with code 2, never a traceback.
- Do not delete branches. Do not push to `main`; open a pull request.
