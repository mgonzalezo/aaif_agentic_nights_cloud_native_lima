# Battle UI (Pokémon-style screens)

An optional skin for the game. Every encounter is a battle: the creature **you choose** against the obstacle of the story.
The classic screens are still the default; this one is switched on with a flag, so you can choose on the day.
The texts are in **Spanish (Latin America) by default**; `--lang en` (or `BESTIARY_LANG=en`) gives the English ones.

```bash
uv run bestiary play --ui battle            # on a laptop
powershell infra\aws\present.ps1 -Battle    # in the cluster (bash: present.sh --battle)
BESTIARY_UI=battle uv run bestiary          # the same, with an environment variable
```

## Who fights whom

The creatures have Peruvian names, so every screen also carries the **real name of the AAIF project** it stands for.

| Part of the screen | What it is |
|---|---|
| **OBSTACLE** (top right, with an HP bar) | The monster of the encounter: Doubt, Fog, Injection, Ritual, Bug, Flaky Test, Review, Gate, Detour, Dummy, Cluster. Its box says **what it is** and **why it is a problem** (text in `bestiary/data/obstacles.yaml`), and **weak to:** the creature that beats it. 11 original 16x16 sprites in `bestiary/opponents.py`. The menu repeats it in one line: `BUG: farolito crashes with a traceback when the config file is missing.` |
| **YOUR CREATURE** (bottom left) | The creature you sent out (empty until you do), with its name, a blue tag with the project (`CHAMBERO  goose`), a one-line description, the real stats from `creatures.yaml` (AUT, REA, CTL, COST) and **`runs on:`**, the pod or host where it really runs |
| Message box | "A wild BUG appeared!" (`¡Apareció BUG!`) and the story step. With `--pick auto` it also lists **Your team: Chambero = goose · DeathNote = AGENTS.md ...** |
| The menu, before each step | "Which creature do you send against BUG?", or "Chambero (goose) vs BUG. What will Chambero do?" once one is out, with the five choices below |
| "X (project) used Y!" | Printed when you choose FIGHT. The skill is the real call that follows |
| The real output | Unchanged and underneath: the raw JSON, goose's trace, the LIVE / REPLAY / DIDACTIC badge |
| The outcome | "BUG fainted! It's super effective!" only when the step really worked (LIVE or REPLAY). A DIDACTIC step says it did not really fall. Skipping says "You ran away!" |

## Choose your creature, then move with the arrows

You send out the creature that solves each obstacle. Before each step a menu appears. Move with **← ↑ ↓ →** and choose with **ENTER**:

```
  ▶ LUCHAR        CRIATURAS        (FIGHT · CREATURES · POKÉDEX · REPLAY · RUN, in English)
    POKÉDEX       REPETICIÓN
    HUIR
```

| Choice | What it does |
|---|---|
| **CRIATURAS** (CREATURES) | The list of the ten creatures with the project of each. The one under the cursor shows **what it is good for** and **its weakness**; the problem of the obstacle stays on top. ENTER sends it out, ESC goes back |
| **LUCHAR** (FIGHT) | Runs the step for real. The badge says LIVE. It only works with the creature that solves this obstacle |
| **POKÉDEX** | An entry like a Pokédex for any of the ten: **what it is**, **what it is good for**, **its weakness**, its moves, its stats. **← →** flips through the ten |
| **REPETICIÓN** (REPLAY) | Shows a real recording of the step, with its date. Same rule as FIGHT |
| **HUIR** (RUN) | Skips the step, whatever creature is out |

**Nobody is on the field at the start**, so the scene does not give the answer away: it shows the obstacle (what it is, why it is a
problem) and asks "which creature do you send?". If you press FIGHT with nobody out, the game says to choose first. If you
send the **wrong creature**, nothing runs: the game says it is **not very effective** (`¡No es muy eficaz!`), names the creature
and the obstacle, and gives a **hint** (`Pista: ...`) written in `bestiary/data/obstacles.yaml`. Choose another and go on. When the
right one fights, its card enters the field (`¡Adelante, Rondero (agentgateway)!`) with its real project name and where it runs, and the
creature stays for the rest of the encounter (encounter 2 has two steps with the same creature). The Kubernetes region has no menu,
so it shows its creature from the start.

**For when time is short:** `--pick auto` (or `BESTIARY_PICK=auto`, `present.ps1 -Pick auto`) puts the right creature on the field
from the start, as in the first version; the menu works the same. Scripted runs (`--auto`, the tests, the recordings) always do that.

Between screens, **ENTER** (or **→**) continues. Keys pressed earlier are discarded, so a double Enter cannot choose by accident.

If a terminal sends arrows the game does not understand, other keys do the same: **W A S D** or **H J K L** move, **1 2 3 4 5** jump to
FIGHT / CREATURES / POKÉDEX / REPLAY / RUN, **Tab** goes to the next choice. The game understands arrows sent as `ESC [ A`, `ESC O A`
(application mode), with Ctrl or Shift, and the Windows Terminal "win32-input-mode". A key it does not know is named in the
footer of the menu (`key not recognised: ESC [ ...`). To see exactly what a terminal sends:

```
powershell infra\aws\present.ps1 -Shell      # a shell in the console pod
bestiary keytest                              # press keys; q to stop
```
Scripted runs (`--auto`, the tests, a pipe) do not wait for keys and use the plain prompts.

The text of the entries is in `bestiary/data/creatures.yaml` (`tagline`, `definition`, `good_for`, `weakness`) and, in Spanish, in `creatures.es.yaml`: edit it there.

The scenes are static on purpose: no animation, so they survive a slow SSM session and goose streaming its trace.

## Limits

- It needs a terminal of **100 columns or more** (the scenes are 108 wide). Below that the game falls back to the classic screens by itself. Give it **at least 40 rows** too: the Pokédex entry is drawn in place of the menu and needs about 22.
- Each scene takes about 24 rows. At a large font on a shared screen it scrolls up quickly: that is expected, the output below is the point.
- Nothing about the demo changes: same encounters, same badges, same replays, same honesty rules.

## Language

Everything the game writes itself is translated: the screens, the narration, the table headings, the creature and obstacle
texts and the doctor. What stays as it came is the **raw output of the real calls** (JSON, goose's trace, the model's answers),
code, the contents of AGENTS.md and the skills, and the goose prompt (translating a prompt would change the reliability that was
measured with it). The texts are in `bestiary/i18n_es.py`, `bestiary/data/creatures.es.yaml` and `bestiary/data/obstacles.es.yaml`;
`tests/test_i18n.py` fails when a new text has no Spanish version.

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

The host runs one branch at a time, set by `REPO_REF` in `/etc/bestiary.env`. The battle screens are part of `main`, and
the classic screens are still what you get without `-Battle`. To run another branch
(through `present.ps1 -Host`, about a minute, nothing is rebuilt from scratch):

```bash
sudo sed -i 's#^REPO_REF=.*#REPO_REF=main#' /etc/bestiary.env        # or any other branch or tag
sudo bash /opt/bestiary/infra/aws/refresh.sh --apply
```

The console pod restarts: reopen the game afterwards.
