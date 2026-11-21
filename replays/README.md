# Replays

Recorded real runs, shown with a REPLAY badge when a live step is not available
(or when the presenter presses `r`). Each file says when it was recorded and with
which model.

Record on the stage laptop, after the rehearsal checks pass:

```bash
uv run bestiary record               # every encounter that can run live
uv run python agent-router/record.py # encounter 9 (Linux/macOS, needs aigw)
```

Nothing here is invented: an encounter without a recording falls back to a
DIDACTIC explanation, labelled as such.
