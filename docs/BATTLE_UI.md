# Battle UI (Pokémon-style screens)

An optional skin for the game. Every encounter is a battle: your creature against the obstacle of the story.
The classic screens are still the default; this one is switched on with a flag, so you can choose on the day.

```bash
uv run bestiary play --ui battle            # on a laptop
powershell infra\aws\present.ps1 -Battle    # in the cluster (bash: present.sh --battle)
BESTIARY_UI=battle uv run bestiary          # the same, with an environment variable
```

## Who fights whom

The creatures have Peruvian names, so every screen also carries the **real name of the AAIF project** it stands for.

| Part of the screen | What it is |
|---|---|
| **OBSTACLE** (top right, with an HP bar) | The obstacle of the encounter: Doubt, Fog, Injection, Ritual, Bug, Flaky Test, Review, Gate, Detour, Dummy, Cluster. 11 original 16x16 sprites in `bestiary/opponents.py` |
| **YOUR CREATURE** (bottom left) | The first creature of the encounter, with its name, a blue tag with the project (`CHAMBERO  goose`), a one-line description, the real stats from `creatures.yaml` (AUT, REA, CTL, COST) and **`runs on:`**, the pod or host where it really runs |
| Message box | "A wild BUG appeared!", the story step and **Your team: Chambero = goose · DeathNote = AGENTS.md ...** |
| The menu, before each step | "Chambero (goose) vs BUG. What will Chambero do?" with the four choices below |
| "X (project) used Y!" | Printed when you choose FIGHT. The skill is the real call that follows |
| The real output | Unchanged and underneath: the raw JSON, goose's trace, the LIVE / REPLAY / DIDACTIC badge |
| The outcome | "BUG fainted! It's super effective!" only when the step really worked (LIVE or REPLAY). A DIDACTIC step says it did not really fall. Skipping says "You ran away!" |

## Move with the arrows

Before each step a menu appears. Move with **← ↑ ↓ →** and choose with **ENTER**:

```
  ▶ POKÉDEX      FIGHT
    REPLAY       RUN
```

| Choice | What it does |
|---|---|
| **POKÉDEX** | An entry like a Pokédex: the project's name and category, **what it is**, **what it is good for**, **its weakness**, its moves, its stats and where to learn more. With a team, **← →** flips between the team members. ENTER (or Esc) goes back |
| **FIGHT** | Runs the step for real. The badge says LIVE |
| **REPLAY** | Shows a real recording of the step, with its date. The badge says REPLAY |
| **RUN** | Skips the step |

The first time you reach a creature the cursor starts on POKÉDEX, so **ENTER, ENTER, ENTER** reads the entry, goes back, and
fights. If you already read it, the cursor starts on FIGHT. Between screens, **ENTER** (or **→**) continues. Keys pressed
earlier are discarded, so a double Enter cannot choose by accident. The letters `p`, `f`, `r`, `s` still work as shortcuts.
Scripted runs (`--auto`, the tests, a pipe) do not wait for keys and use the plain prompts.

The text of the entries is in `bestiary/data/creatures.yaml` (`tagline`, `definition`, `good_for`, `weakness`): edit it there.

The scenes are static on purpose: no animation, so they survive a slow SSM session and goose streaming its trace.

## Limits

- It needs a terminal of **100 columns or more** (the scenes are 108 wide). Below that the game falls back to the classic screens by itself. Give it **at least 40 rows** too: the Pokédex entry is drawn in place of the menu and needs about 22.
- Each scene takes about 24 rows. At a large font on a shared screen it scrolls up quickly: that is expected, the output below is the point.
- Nothing about the demo changes: same encounters, same badges, same replays, same honesty rules.

## Tests

`tests/test_battle_menu.py`: every Pokédex entry fits and has the definition, use and weakness; the menu moves with the arrows and
stops at the edges; ENTER opens the Pokédex, flips team members and goes back to FIGHT; REPLAY and RUN are reachable with the
arrows; scripted runs never wait for a key. The key presses are scripted, and the same game was also driven through a real
pseudo-terminal on the host with the real escape sequences of the arrow keys.

`tests/test_battle.py`: every scene fits in 110 columns and shows the fight, the 11 opponents are valid sprites, a
live step ends with the opponent fainting, a DIDACTIC step does not pretend to win, the narrow terminal falls back, classic
stays the default, and the whole game runs in battle mode with a fake model.

## Real terminal check

Besides the scripted tests, the game was driven through a real pseudo-terminal in the console pod, pressing the real
escape sequences of the arrow keys in bursts (open the Pokédex, close it, move the cursor, FIGHT; RUN with the arrows;
REPLAY with the arrows): all three finished with exit code 0, no escape codes echoed on the screen. The script is not part
of the repo; the idea is `pty.fork()` plus `os.write(fd, "\x1b[C")`.

## Which branch is on the host

The host runs one branch at a time, set by `REPO_REF` in `/etc/bestiary.env`. `feat/battle-ui` contains everything in
`feat/aws-gpu-demo` plus the battle UI, and the classic screens are still what you get without `-Battle`. To switch
(through `present.ps1 -Host`, about a minute, nothing is rebuilt from scratch):

```bash
sudo sed -i 's#^REPO_REF=.*#REPO_REF=feat/aws-gpu-demo#' /etc/bestiary.env   # the safe demo
sudo sed -i 's#^REPO_REF=.*#REPO_REF=feat/battle-ui#' /etc/bestiary.env      # the battle UI
sudo bash /opt/bestiary/infra/aws/refresh.sh --apply
```

The console pod restarts: reopen the game afterwards.
