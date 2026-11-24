# Battle UI (Pokémon-style screens)

An optional skin for the game. Every encounter is a battle: your creature against the obstacle of the story.
The classic screens are still the default; this one is switched on with a flag, so you can choose on the day.

```bash
uv run bestiary play --ui battle            # on a laptop
powershell infra\aws\present.ps1 -Battle    # in the cluster (bash: present.sh --battle)
BESTIARY_UI=battle uv run bestiary          # the same, with an environment variable
```

## What you see

| Part of the screen | What it is |
|---|---|
| Opponent (top right, with an HP bar) | The obstacle of the encounter: Doubt, Fog, Injection, Ritual, Bug, Flaky Test, Review, Gate, Detour, Dummy, Cluster. 11 original 16x16 sprites in `bestiary/opponents.py` |
| Your creature (bottom left) | The first creature of the encounter. Its box shows the real stats from `creatures.yaml` (AUT, REA, CTL, COST) and **`runs on:`**, the pod or host where it really runs |
| Message box and menu | "A wild BUG appeared!", the story step, and the creature's three skills from `creatures.yaml` plus RUN. Helpers of the encounter are listed as the party |
| "X used Y!" | Printed when you press Enter. The skill is the real call that follows |
| The real output | Unchanged and underneath: the raw JSON, goose's trace, the LIVE / REPLAY / DIDACTIC badge |
| The outcome | "BUG fainted! It's super effective!" only when the step really worked (LIVE or REPLAY). A DIDACTIC step says it did not really fall. Skipping says "You ran away!" |

The scenes are static on purpose: no animation, so they survive a slow SSM session and goose streaming its trace.

## Limits

- It needs a terminal of **100 columns or more** (the scenes are 108 wide). Below that the game falls back to the classic screens by itself.
- Each scene takes about 24 rows. At a large font on a shared screen it scrolls up quickly: that is expected, the output below is the point.
- Nothing about the demo changes: same encounters, same badges, same replays, same honesty rules.

## Tests

`tests/test_battle.py`: every scene fits in 110 columns and shows the fight, the 11 opponents are valid sprites, a
live step ends with the opponent fainting, a DIDACTIC step does not pretend to win, the narrow terminal falls back, classic
stays the default, and the whole game runs in battle mode with a fake model.
