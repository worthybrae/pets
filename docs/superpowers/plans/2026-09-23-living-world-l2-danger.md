# Living World L2: Danger and Combat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Mimo's nights dangerous and give it the means to live through them: gloomlings and skitters that come out where the light is low, chase Mimo, strike it and burn or fade by day; light levels from the sky, torches, lanterns, fires and furnaces; Mimo's health that creatures take and time gives back, cut by leather armor; a bow and arrows beside L1's swords; fight and flee reflexes; doors that let Mimo in and keep creatures out; death by a creature on the memorial; `threats` in the model payload; and a viewer that draws the hostiles, their strikes and burns, arrows in flight, doors swinging open, armor on the pet, a danger line and a red flash on the HUD, and red dots on the minimap.

**Architecture:** Everything plugs into a registry or hook that L1 and the Survival Core left for it. The door is one more block at the end of `shared/blocks.json`, not solid (so Mimo's pathing walks through it) and refused by `creatures.moves.steps` (so no creature does); M5's shelter generator plans one in the door gap and `build_shelter` furnishes it. `backend/survival/light.py` computes light on demand. `creatures/hostiles.py` registers the two hostile kinds (`register_kind`) and their actions (`register_action`: sunlit, strike, chase, prowl), `creatures/harm.py` is what a blow does to Mimo, and `creatures/darkness.py` is a spawner beside L1's `populate` in the creature hook, with its own cap. The creature hook lets hostiles take their turns at their own times and the tick runs in one-second steps while one is near, so a fight is fought at the pace it happens, and a blow that takes the last health ends the life with the creature's kind as the cause. `creatures/archery.py` registers the `shoot` step on L1's `strike`; `creatures/gear.py` registers the `make_gear` purpose; `creatures/defense.py` registers the `fight` and `flee` reflexes and builds the model's `threats`. The viewer gets pure, tested modules (`hostileMotion`, `archery`, `doors`, `petGear` and the HUD's words) and three components (`CombatEffects`, `SurvivalDoors` and the pet's armor).

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-living-world-design.md` (L2: the milestone table's row and the whole "L2 Danger and combat" outline; the spec's "Decisions" and "Error handling and testing" where they touch L2). L3 and L4 stay out (resolution 20). It builds on L1 (`docs/superpowers/plans/2026-09-23-living-world-l1-animals.md`, complete with its fix wave) and follows that plan's shape. The code on branch `worthy/23_09_2026/survival_core` at `60460ff` is the "old" text every task edits; the dry run applied every task to that commit.

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls (a fake Jev stands in where a test needs one). Creatures stay deterministic: every roll comes from `worldgen.hash32` with the world seed (`creatures.moves.roll`, `nature.roll`), including where hostiles spawn and whether an arrow hits. Nothing reads `random` or the clock.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments (mutate three.js objects and DOM nodes only through refs inside `useFrame`, effects or event handlers), no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components. No stylesheet changes: the HUD's flash animates with `element.animate`.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. Read-only GETs never write. L2 adds no table and no column: hostiles are rows of L1's `creatures` table, danger places are memory places, and the rest lives in Mimo's state JSON (`hurt_at`, `hurt_by`, `dark_spawn_at`, `brain["threat_at"]`).
- **No model call inside the tick.** Hostile actions, the spawner, the shoot step, the reflexes and `make_gear` are rules. A threat marks an urgent choice, and the worker's Chooser asks Jev outside the tick (Jev's calls are cheap, so an urgent threat asks at once; resolution 17). Validity checks, facts and scores never write.
- A crashing planner, reflex, hook or picker never stops a tick or the worker (L1's `run_creatures` guard covers the spawner and the hostiles' actions).
- New blocks go at the end of `shared/blocks.json`: L2 adds `door` only. Hostile drops (`gloom_dust`, `string`), `flint`, `bow`, `arrow`, `leather_cap` and `leather_tunic` are items.
- Values copied from the spec (L2 outline). gloomling: 20 health, slow, 3 damage every 1.2 s, spawns on dark surface cells at night and in caves, burns and fades at dawn under the open sky, drops gloom_dust. skitter: 12 health, fast, 2 damage, caves and dark places, drops 0–2 string. Sky light 15 by day, 4 at night, 0 underground; block light torch 14, lantern 15, campfire 13, one less per block (Manhattan), on demand in a bounded radius; hostiles spawn only at light 7 or less, 16–40 blocks from Mimo, never in a claimed shelter room. Chase within 16, attack in reach with a cooldown, give up past 24, despawn beyond 64 or at dawn. Regen 1 health per game minute while fed; damage flashes; the HUD's danger line ("A gloomling is close!"). flee (30): health below 35, or a hostile within 6 and no weapon; runs home or away and ends up safe. fight (40): a hostile within 4, health 50 or more and a weapon; the sword, or the bow at 5 or more blocks with arrows. Both are reflex data. Bow: 3 sticks and 3 string; arrows: 1 flint, 1 stick and 1 feather make 4; flint from gravel 1 in 8; `shoot(creature_id)` 1.0 s, range 16, a hit chance that falls with distance, 5 damage, the arrow flies in an arc and is used up. Leather cap and tunic cut damage by 20 % (iron armor, 45 %, is L3); the pet model shows the armor. Door: 6 planks; the M5 generator places one in the door gap; Mimo passes, creatures do not; the viewer draws it open while Mimo passes. Death by a creature on the memorial ("was caught by a gloomling on day 3"); danger places remembered; `threats` in the model payload. At most 8 hostiles active; creature simulation plus light checks cost at most 20 ms per 60-game-second slice on average.
- `MIMO_TIME_SCALE` and `MIMO_ACTION_SCALE` (both default 1) are for manual runs only. Hostile moves, strikes and burns are divided by the action scale like Mimo's steps; game-time spans (the spawn rate, the alarm gap, loitering) follow the time scale. L2 adds no settings.
- Never run `docker` or `docker compose` in Tasks 1–11. Task 12 is the controller's manual check on the demo stack (`mimo-m5demo-api` on :8011 and `mimo-m5demo-worker`, volume `mimo_m5demo`); never touch, mount or migrate the owner's real volume `pets_mimo_data` or the real stack (`pets-api-1`, `pets-mimo-worker-1`). Never print `TYPESAFE_API_KEY` or any other key.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (685 pass at `60460ff`)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_darkness.py" -v`
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` (about 2 minutes) and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
- Frontend tests: `cd frontend && npm test` (259 pass at `60460ff`)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint <paths>` (the survival and engine folders lint clean; older pages have lint errors of their own that L2 leaves alone)

Each task says how many tests it adds. If the real starting totals differ, expect the same increases on top of them.

Transcription: every edit is a fenced block, either a whole new file ("Create `path`:") or a "replace: … with: …" pair in a named file ("In `path`, replace:", then "and replace:" for more pairs in the same file). Old texts are kept short, so a task still applies when a neighbouring line changes. The dry run applied each task with the controller's apply script (`.superpowers/sdd/2026-09-23-living-world-l1-animals/apply_plan.py`) to a copy of `60460ff` and ran the task's checks after each one.

## Plan-level resolutions

The spec is an outline for L2 ("detailed in its plan"). These are the details. Every task follows them; the controller ledgers them.

1. **Base.** L1 is complete with its fix wave (`60460ff`): `Scene.events` is required (kw_only), steps that need the tick's events say so (`StepKind.takes_events`), creatures never step into what Mimo built unless they already stand on it, and one shared voxel grid draws every creature. Every Scene L2 builds, in the tick or in a step (the shoot step), carries the tick's events.
2. **Registries, not rewrites.** The door is a block; hostiles are kinds (`register_kind`) with creature actions (`register_action`); the bow is a step (`register_step`); gear is a purpose (`register`); fight and flee are reflexes (`reflexes.register`); the dark spawner sits beside `populate` in the creature hook. New modules: `light.py` and, in `creatures/`, `harm`, `hostiles`, `darkness`, `archery`, `gear`, `defense` and `eviction`. `creatures/__init__.py` still imports nothing; `darkness` imports `hostiles` (so the kinds are registered wherever hostiles can spawn), `combat` imports `archery` last, and the brain imports `gear` and `defense`.
3. **Light.** A cell's light is the brighter of its sky light and its block light. Sky light is 15 by day (dawn, day and dusk) and 4 at night for a cell open to the sky, else 0: a cell is open when nothing solid but leaves stands over it, up to 8 cells above the natural ground (caves, tunnels and roofed rooms are covered; a pit Mimo dug is not). Block light: torch 14, lantern 15, campfire 13 and furnace 13 (the spec's Decisions name furnaces as a light without a value), less its Manhattan distance, through walls (the spec's simple model). It is never stored: `light.Lights` reads the light blocks placed near a spot once (`Grid.placed_cells`) and answers for every cell near it. A torch keeps the cells within 6 blocks above 7, so the four corner torches M5's light_up places keep the yard safe.
4. **Hostile kinds.** gloomling: 20 health, 0.9 s a block (slow), 3 damage every 1.2 s from 1.5 blocks, 1.7 blocks tall and needing 2 cells of room, burns by day, drops 0–2 gloom_dust (kept, not used, until L3's lanterns). skitter: 12 health, 0.4 s a block (fast), 2 damage every 1.0 s (the spec gives no cooldown; Kind's default) from 1.5 blocks, 0.6 tall, drops 0–2 string. Neither runs when hurt (a hit one turns on Mimo), neither is hunted (`kinds.huntable` already skips hostile kinds) and neither spawns in herds (`land_kinds` skips them).
5. **Where they come from.** Once every 30 game seconds, while fewer than 8 hostiles are alive (counted in the table: every living hostile is near Mimo, resolution 6), the dark gets one chance: up to 4 columns 16–40 blocks from Mimo, rolled from the seed and the time, are searched from just over the natural ground down 24 cells, and no more than 8 above or below Mimo, for a dry, empty cell with room above, not on leaves, claimed by nothing Mimo built ("never inside a claimed shelter room": no claimed cell at all) and with light 7 or less. Open to the sky, it gets a gloomling (dark ground at night); covered, a skitter three times in five, else a gloomling. By day open ground is lit, so only covered places spawn. The 8 is a cap of its own: L1's 24 counts passive creatures only.
6. **Where they go.** Every call deletes the hostiles farther than 64 blocks from Mimo at night, and by day those beyond the 48 the hook simulates (out there nothing would ever burn them). Near Mimo, by day under the open sky, a gloomling catches fire (`burning`) and dies 3 s later without drops, and a skitter fades at once: that is the spec's "despawn at dawn". A hostile that has not come after Mimo for 120 game seconds fades too, so the ones about are the ones Mimo meets and the caves under its feet do not hold the cap all night.
7. **What they do** (creature actions ahead of the animals'): `sunlit` (2), `strike` (4: in reach of a living Mimo, with nothing solid between them, the cooldown passed and Mimo not inside its shelter), `chase` (6: within 16 blocks across and 4 up or down, or 24 once after Mimo or just hurt by it; up to 2 steps a turn, each to the neighbour nearest Mimo; never through a door, into what Mimo built, or for a gloomling under a ceiling lower than 2 cells), `prowl` (25: give up, wander near home or stand). "Give up past 24": a chase ends there. The first hostile to come after Mimo outside its shelter raises the alarm: an urgent `threat` choice and a `threat` event, at most one every 5 game minutes.
8. **Blows and health.** A blow takes the kind's damage less the armor's share (leather cap 8 %, tunic 12 %, 20 % together; armor is worn by carrying it), marks `hurt_at` and `hurt_by`, remembers the place as a `danger` noted with the kind, asks for a choice at once when health falls past 50, 30 or 15, and logs a routine `hurt` event at most every 10 s. No blow goes through a wall or round a roof's edge (`hostiles.can_hit`: a diagonal needs an open corner) or reaches Mimo in a room or passage cell of its shelter (`harm.sheltered`; a window gap is not a way in). Regeneration is 1 health a game minute (`HEAL_RATE = 1/60`, was 1/20) under M1's rule: hunger above 60 and warm. The spec says "while hunger is above 60"; keeping M1's warmth condition too changes nothing a creature does.
9. **Death by a creature.** After every creature run the tick checks whether a blow took the last health (`tick.caught`) and records the death with the kind as the cause: the memorial and the event read "Pip was caught by a gloomling on day 3.", the worker's line "Pip was caught by a gloomling.", the viewer's life line "caught by a gloomling".
10. **Fights at their own pace** (L1's final review, item 1). A hostile takes each turn that comes due up to the hook's time at its own `next_at`, up to 3 in one call and never more than 2 s (at the normal pace) behind the call, from a budget of 32 turns of its own (animals keep L1's 24, one each). While a living hostile is within 16 blocks across and 4 up or down and Mimo is not in a cell it built, the tick's steps last at most 1 second of action time (`FIGHT_SLICE`), so the reflexes see where creatures are. Measured on a hatched world through its first night: 1–2 hostiles by day (caves), up to 7 at night, 0.8 ms a call and 9 ms per game minute on average (16 ms at most); L1's 60-minute day stays at 3 ms per game minute. The limits matter: measured without them, a gloomling that had fallen behind during a long catch-up step caught up at three blows a second and killed a sleeping pet within a game minute.
11. **Doors.** Block `door` (after `chest`): not solid, not replaceable, hardness 2 with an axe, drops itself, layer `none` (the viewer draws it). 6 planks, no station (like the bed). A new shelter plans a door in the lower cell of its door gap (the cell above stays open, as M5 had it); `structures.blueprint_of` gives a shelter designed before L2 one too (`blueprints.with_door`), so `build_shelter` furnishes old homes with a door as it does a bed. A land creature never steps into or through a door (`moves.past_doors`). When the door goes in, any creature standing in the shelter's cells is put outside (`creatures.eviction`). The home Mimo built stays its home from 128 blocks (`BUILT_HOME_RANGE`, was 64), measured on the days runs.
12. **The bow.** Recipes at a crafting table. Flint from mined gravel, 1 in 8 (a chance drop like saplings). `shoot` lasts 1.0 s; it fails without a bow or an arrow, or past 16 blocks. The hit is rolled when the shot starts: sure within 4 blocks, falling in a straight line to 1 in 2 at 16. A hit does 5 damage through `combat.strike` (a hit animal runs, a hit hostile turns on Mimo); a kill's drops go into Mimo's arms with a `hunt` (animal) or `fight` (hostile) event (`combat.spoils`). The arrow is spent hit or miss. The step's `hit` is in the running action and the recorded one, so the viewer flies the arrow true or wide.
13. **Armor and gear.** leather: 4 rabbit hides (L1's review asked for it; cows drop leather too). leather_cap: 2 leather, leather_tunic: 3 leather, at a crafting table (the spec gives no counts). `make_gear` (work band, 55–75) makes the missing armor first, then a bow with its first arrows, then arrows up to 8, one batch per choice, at a crafting table it places and mines back like craft_tools. What gear takes stays on hand: storage keeps 5 leather, 4 feathers, 8 hides, 3 string and 4 flint out of the chest (L1's review, item 7).
14. **Fight and flee.** A threat is a living hostile within 16 blocks across and 4 up or down, none while Mimo is indoors. flee (30): a threat and health below 35, or the nearest threat within 6 and no weapon (a sword, or a bow with arrows): home when the threat is no nearer home than Mimo, else 12 blocks straight away; Mimo walks faster than any hostile. fight (40): a weapon, health 50 or more (35 while a fight is on) and a threat within 4, or, with a bow and arrows, a chasing one within 12 in plain sight (the spec's 5-block bow rule needs a trigger past 4). It shoots from 5 blocks or without a sword, strikes in reach, else steps up and strikes. fight shares priority 40 with eat_now; eat_now registered first and stays first. Both keep quiet for 30 s after they end, so a fight logs one event, not one a round.
15. **What the model is told.** `context_payload` gains `threats` (the nearest 4: kind, distance, whether it is after Mimo) and `defense` (indoors, best sword, arrows with a bow, armor, the kind that hurt Mimo last).
16. **What the viewer is told.** `creatures[]` entries of hostile kinds carry `hostile: true`; states add `chasing`, `attacking` and `burning`; `struck_at` and `burning_at` come when set; chases are moves like walks. The snapshot adds `hurt_at` and `hurt_by`.
17. **Jev.** Model calls are cheap now: a threat is an urgent choice, so the Chooser asks Jev at once even right after another call (the urgent path already skips the minimum gap; a test pins it). The hourly cap and the daily cap still hold.
18. **Viewer.** The gloomling and skitter are voxel models on L1's shared grid (ours, not Minecraft's). A hostile lunges at each strike, hunches while it chases, a skitter scuttles, a burning gloomling flickers and shrinks with flames over it. The pet leans back to draw its bow and the arrow flies in a low arc (a miss flies 3 blocks past and drops). Doors are drawn by the viewer, two blocks tall, and swing open while the drawn pet is within 1.6 blocks. The pet wears the cap and tunic it carries and glows red for 0.4 s at a blow; the HUD's edges flash red; the danger line names hostiles within 12 blocks; hostiles are red dots on the minimap.
19. **Purpose budget.** The headless runs' cap on changes of purpose per game hour (52, and 55 with `MIMO_SLOW_TESTS=1`) holds with make_gear and the reflexes; no change.
20. **Out of scope.** L3: iron armor (45 %), lanterns as a recipe (the light table already knows them), gravel in the terrain, bigger caves and passages, new blocks and biomes. L4: goals. Nothing uses gloom dust yet.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `shared/blocks.json` | Modify | The door block, last |
| `backend/survival/light.py` | Create | Light levels on demand |
| `backend/survival/creatures/harm.py` | Create | What a creature's blow does to Mimo; armor; indoors |
| `backend/survival/creatures/hostiles.py` | Create | gloomling and skitter; sunlit, strike, chase, prowl |
| `backend/survival/creatures/darkness.py` | Create | Spawning in the dark, the cap of 8, despawning far away |
| `backend/survival/creatures/archery.py` | Create | The `shoot` step |
| `backend/survival/creatures/gear.py` | Create | The `make_gear` purpose |
| `backend/survival/creatures/defense.py` | Create | The fight and flee reflexes, threats, the model's `threats` |
| `backend/survival/creatures/eviction.py` | Create | Creatures out of a shelter when its door goes in |
| `backend/services/crafting.py`, `backend/survival/nature.py`, `carrying.py`, `storage.py` | Modify | Door, bow, arrows, leather, cap, tunic; flint; gear is valuable; gear's materials stay on hand |
| `backend/survival/blueprints.py`, `structures.py`, `building.py`, `purposes.py` | Modify | A door in every shelter; furnished; the built home from 128 blocks |
| `backend/survival/creatures/kinds.py`, `acts.py`, `moves.py`, `combat.py`, `simulate.py`, `view.py` | Modify | cooldown, burns, height; the Scene's clock; doors and headroom; spoils; the spawner and hostile turns; hostiles in the stream |
| `backend/survival/tick.py`, `backend/workers/mimo_worker.py`, `vitals.py`, `world.py` | Modify | Short steps near hostiles, death by a creature; healing 1 a minute; routine events |
| `backend/survival/reflexes.py`, `brain.py`, `pickers.py`, `steps.py`, `actions.py`, `snapshot.py`, `lighting.py` | Modify | `quiet`; import L2's purpose and reflexes; `threats`; docstrings; `hit`; `hurt_at` |
| `backend/tests/test_survival_{doors,light,hostiles,archery,gear,defense,darkness,threats}.py` | Create | One test file per new module or area |
| `backend/tests/test_{blocks,survival_creatures,survival_creature_acts,survival_vitals,survival_meat,survival_reflexes,survival_tick,survival_worker,survival_api,survival_herds,survival_pickers}.py` | Modify | What L2 changes in them |
| `frontend/src/survival/types.ts`, `hud.ts`, `SurvivalHud.tsx`, `replay.ts` (+ tests) | Modify | The stream's new fields; the danger line, the flash, the words |
| `frontend/src/survival/creatures.ts`, `SurvivalCreatures.tsx`, `Minimap.tsx`, `animation.ts` (+ tests) | Modify | Hostile models, motion, red dots, the bow draw |
| `frontend/src/survival/hostileMotion.ts`, `archery.ts` (+ tests), `CombatEffects.tsx` | Create | Strike, chase and burn motion; arrows; flames |
| `frontend/src/engine/worldStore.ts` (+ test), `frontend/src/survival/doors.ts`, `petGear.ts` (+ tests), `SurvivalDoors.tsx` | Create / Modify | Doors and armor |
| `frontend/src/survival/SurvivalPet.tsx`, `WorldCanvas.tsx`, `SurvivalWorld.tsx` | Modify | Armor and the hurt glow; mount the effects and doors |
| `README.md` | Modify | Danger and combat |

## Tasks

1. Doors
2. Light levels
3. Hostile creatures and their blows
4. The bow and arrows
5. Leather armor and making gear
6. The fight and flee reflexes
7. Hostiles come out in the dark, in the tick
8. What the model and the viewer are told
9. Viewer: the words for danger
10. Viewer: hostiles, arrows and the minimap
11. Viewer: doors and armor
12. Manual check on the demo and the README

Tasks 1–8 are the backend and 9–11 the viewer; each viewer task needs only the tasks before it. Hostiles first appear in the world in Task 7, after Mimo can fight and flee (Task 6), so the headless runs never meet a hostile they cannot answer. Tasks 1 and 2 need nothing of L2 before them.

---

### Task 1: Doors

**Files:**
- Modify: `shared/blocks.json` (the door block, last), `backend/services/crafting.py` (6 planks), `backend/survival/blueprints.py` (a door in every new shelter's door gap; `with_door` for older designs), `backend/survival/structures.py` (read designs with their door; a missing door is work to do), `backend/survival/building.py` (the door is a furnishing; put creatures out when it goes in), `backend/survival/creatures/moves.py` (no creature passes a door), `backend/survival/purposes.py` (the home Mimo built stays home from twice as far)
- Create: `backend/survival/creatures/eviction.py`
- Modify tests: `backend/tests/test_blocks.py`, `frontend/src/engine/blocks.test.ts` (the door comes after the chest)
- Test: `backend/tests/test_survival_doors.py`

**Interfaces:**
- Consumes: `blueprints.Blueprint`, `Planned`, `from_data`, `shelter`; `structures.missing`, `blueprint_of`; `building.FURNISHINGS` and `note_building`; `creatures.moves.steps`; `purposes.home_of`; `Herd` (L1).
- Produces:
  - Block `door` (id after `chest`): not solid (Mimo's pathing walks through it), not replaceable, hardness 2.0, mined with an axe, drops itself, layer `none` (the viewer draws it, Task 11). Recipe `door`: 6 planks, no station.
  - `blueprints.with_door(blueprint) -> Blueprint`: a shelter design whose door gap has no door gets one in the gap's lower cell; anything else comes back unchanged. `blueprints.shelter` plans `Planned(cell, "door", "door")` in the gap's lower cell and `Planned(cell, "door", "air")` above it.
  - `structures.blueprint_of(structure)` returns `with_door(from_data(...))`; `structures.missing` counts a gap's door cell as missing until a door stands there (the cell above stays open, as before).
  - `building.FURNISHINGS == ("bed", "campfire", "door")`: build_shelter makes (6 planks) or carries a door and places it, in old shelters too. When a door is placed, `note_building` calls `creatures.eviction.evict(grid, blueprint)`.
  - `creatures.eviction.evict(grid, blueprint) -> list[dict]`: every living creature standing in a cell the shelter claims is moved to the first standable, unclaimed cell straight out past the cell in front of the door (up to 3 cells), or removed when there is none. Returns the moved ones.
  - `creatures.moves.steps(grid, cell, water)`: a land creature never steps into a door or through one (`past_doors(grid, start, step)`).
  - `purposes.BUILT_HOME_RANGE = 2 * HOME_RANGE`: `home_of` returns the home Mimo built within 128 blocks, else the nearest remembered home or shelter within 64, as before.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_doors.py`:

```python
import math
import unittest

from backend.services.blocks import hardness, is_replaceable, is_solid, mining_tool
from backend.services.crafting import BLOCKS, craft
from backend.survival.blueprints import Style, find_site, from_data, shelter, with_door
from backend.survival.creatures.moves import steps
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.memory import remember, set_home, structures
from backend.survival.pathing import route
from backend.survival.purposes import BUILT_HOME_RANGE, HOME_RANGE, PURPOSES, home_of
from backend.survival.structures import blueprint_of, todo
from backend.tests.test_survival_building import World, places_of


def meadow():
    return Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")


def hut():
    grid = meadow()
    site = find_site(grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
    return shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Hut")


class DoorBlockTests(unittest.TestCase):
    def test_a_door_takes_six_planks_and_is_no_wall_and_no_floor(self):
        self.assertEqual(craft({"planks": 6}, "door", set()), {"door": 1})
        self.assertFalse(is_solid("door"))
        self.assertFalse(is_replaceable("door"))
        self.assertEqual((hardness("door"), mining_tool("door"), BLOCKS["door"]["drop"]), (2.0, "axe", "door"))

    def test_mimo_walks_through_a_door_in_a_wall(self):
        grid = meadow()
        for z in range(-6, 7):
            for y in (1, 2):
                grid.put(2, y, z, "cobblestone")
        grid.put(2, 1, 0, "door")
        grid.put(2, 2, 0, "air")
        cells, reached = route(grid, (0, 1, 0), (4, 1, 0))
        self.assertTrue(reached)
        self.assertIn((2, 1, 0), cells)

    def test_creatures_never_step_into_a_door_or_a_cell_mimo_built(self):
        grid = meadow()
        grid.put(1, 1, 0, "door")
        grid.claims.add((0, 1, 1))
        self.assertEqual(sorted(steps(grid, (0, 1, 0), False)), [(-1, 1, 0), (0, 1, -1)])
        hole = meadow()
        hole.put(1, 0, 0, "air")  # a hole under a door: dropping into it passes through the door
        hole.put(1, 1, 0, "door")
        self.assertNotIn((1, 0, 0), steps(hole, (0, 1, 0), False))
        hole.put(1, 1, 0, "air")
        self.assertIn((1, 0, 0), steps(hole, (0, 1, 0), False))


class ShelterDoorTests(unittest.TestCase):
    def test_a_new_shelter_plans_a_door_in_the_lower_gap_and_keeps_the_cell_above_open(self):
        design = hut()
        self.assertEqual([(planned.cell, planned.block) for planned in design.parts("door")],
                         [((1, 1, -1), "door"), ((1, 2, -1), "air")])
        self.assertEqual([planned.cell for planned in todo(meadow(), design, ("door",))], [(1, 1, -1)])

    def test_a_shelter_designed_before_doors_gets_one_when_it_is_read(self):
        data = hut().to_data()
        data["cells"] = [[x, y, z, part, "air" if part == "door" else block] for x, y, z, part, block in data["cells"]]
        old = from_data(data)
        self.assertEqual({planned.block for planned in old.parts("door")}, {"air"})
        upgraded = blueprint_of({"data": data})
        self.assertEqual([planned.block for planned in upgraded.parts("door")], ["door", "air"])
        self.assertEqual(with_door(upgraded), upgraded)

    def test_a_finished_shelter_is_furnished_with_a_door_and_mimo_still_walks_in(self):
        world = World({"cobblestone": 40})
        create_creature_tables(world.db)
        world.grid.herd = Herd(world.db)
        for _ in range(4):
            world.carry_out(world.plan())
        design = blueprint_of(structures(world.db)[0])
        rabbit = world.grid.herd.add("rabbit", design.anchor, 3.0, 0.0, 0.0, {"home": list(design.anchor)})
        self.assertTrue(world.grid.claimed(design.anchor))  # it wandered in while the walls went up
        world.state["inventory"] = {"bed": 1, "campfire": 1, "planks": 6}
        self.assertIn("a bed and a campfire and a door", PURPOSES["build_shelter"].facts(world.situation()))
        steps_planned = world.plan()
        self.assertIn({"kind": "craft", "recipe": "door"}, steps_planned)
        door = design.one("door")
        self.assertEqual(places_of(steps_planned)[-1], {"kind": "place", "target": list(door), "block": "door"})
        world.carry_out(steps_planned)
        self.assertEqual(world.grid.material(*door), "door")
        put_out = cell_of(world.grid.herd.get(rabbit["id"]))
        self.assertFalse(world.grid.claimed(put_out))
        self.assertLessEqual(math.dist(put_out, design.front), 3)
        self.assertFalse(PURPOSES["build_shelter"].valid(world.situation()))
        outside = tuple(2 * front - gap for front, gap in zip(design.front, door))  # one beyond the front
        cells, reached = route(world.grid, outside, design.anchor)
        self.assertTrue(reached)
        self.assertIn(door, cells)

    def test_the_home_mimo_built_stays_home_from_twice_as_far_as_any_other_shelter(self):
        self.assertEqual(BUILT_HOME_RANGE, 2 * HOME_RANGE)
        world = World(position=(101, 1, 1))
        set_home(world.db, (1, 1, 1), 0.0)
        remember(world.db, "shelter", (90, 1, 1), 0.0)
        self.assertEqual(home_of(world.situation())["x"], 1)
        world.state["position"]["x"] = 140.0
        self.assertEqual(home_of(world.situation())["x"], 90)


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_blocks.py`, replace:

```python
        self.assertEqual(names[BLOCK_IDS["flower_yellow"] + 1:], list(FOOD_AND_CAMP))
```

with:

```python
        self.assertEqual(names[BLOCK_IDS["flower_yellow"] + 1:BLOCK_IDS["chest"] + 1], list(FOOD_AND_CAMP))
        self.assertEqual(names[BLOCK_IDS["chest"] + 1:], ["door"])  # L2
```

In `frontend/src/engine/blocks.test.ts`, replace:

```ts
    expect(blockId('chest')).toBe(BLOCKS.length - 1)
```

with:

```ts
    expect(blockId('door')).toBe(blockId('chest') + 1)
    expect(blockId('door')).toBe(BLOCKS.length - 1)
    expect(LAYER_BY_ID[blockId('door')]).toBe(0)  // not meshed: the viewer draws doors itself
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_doors.py"`
Expected: an ImportError (`with_door` does not exist yet).

- [ ] **Step 3: Add the door block and its recipe**

In `shared/blocks.json`, replace:

```json
    {"name": "chest", "color": [186, 138, 88], "textures": {"top": "chest_top", "side": "chest_side", "bottom": "planks"}, "layer": "opaque", "solid": true, "drop": "chest", "hardness": 2.0, "tool": "axe"}
```

with:

```json
    {"name": "chest", "color": [186, 138, 88], "textures": {"top": "chest_top", "side": "chest_side", "bottom": "planks"}, "layer": "opaque", "solid": true, "drop": "chest", "hardness": 2.0, "tool": "axe"},
    {"name": "door", "color": [150, 104, 64], "textures": "planks", "layer": "none", "solid": false, "drop": "door", "hardness": 2.0, "tool": "axe"}
```

In `backend/services/crafting.py`, replace:

```python
    "bed": {"ingredients": {"planks": 6}, "output": {"bed": 1}},
```

with:

```python
    "bed": {"ingredients": {"planks": 6}, "output": {"bed": 1}},
    "door": {"ingredients": {"planks": 6}, "output": {"door": 1}},
```

- [ ] **Step 4: Put a door in every shelter's door gap**

In `backend/survival/blueprints.py`, replace:

```python
corners, a campfire outside beside the door, and up to four torches at the outside corners. A
```

with:

```python
corners, a campfire outside beside the door, up to four torches at the outside corners and (L2) a
door in the lower cell of the door gap, which Mimo walks through and creatures never do. A
```

and replace:

```python
from dataclasses import dataclass, field
```

with:

```python
from dataclasses import dataclass, field, replace
```

and replace:

```python
        front=tuple(data["front"]) if data.get("front") else None, style=dict(data.get("style", {})))
```

with:

```python
        front=tuple(data["front"]) if data.get("front") else None, style=dict(data.get("style", {})))


def with_door(blueprint: Blueprint) -> Blueprint:
    """A shelter designed before doors (L2) gets one in the lower cell of its door gap, so build_shelter
    furnishes old homes too; any other design comes back as it is."""
    gap = blueprint.parts("door")
    if blueprint.kind != "shelter" or not gap or any(planned.block == "door" for planned in gap):
        return blueprint
    lowest = min(gap, key=lambda planned: planned.cell[1])
    return replace(blueprint, cells=tuple(Planned(planned.cell, planned.part, "door") if planned is lowest else planned
                                          for planned in blueprint.cells))
```

and replace:

```python
    for y in (1, 2):
        cells.append(Planned(site.world(door, -1, floor + y), "door", "air"))
```

with:

```python
    for y in (1, 2):  # L2: a door in the lower cell of the gap; the cell above it stays open
        cells.append(Planned(site.world(door, -1, floor + y), "door", "door" if y == 1 else "air"))
```

In `backend/survival/structures.py`, replace:

```python
from backend.survival.blueprints import FITTINGS, KEEP_OPEN, STRUCTURAL, Blueprint, Planned, from_data
```

with:

```python
from backend.survival.blueprints import FITTINGS, KEEP_OPEN, STRUCTURAL, Blueprint, Planned, from_data, with_door
```

and replace:

```python
    return from_data(structure["data"])
```

with:

```python
    return with_door(from_data(structure["data"]))
```

and replace:

```python
        return material != "farmland"
    return planned.part in FITTINGS and material != planned.block
```

with:

```python
        return material != "farmland"
    if planned.part == "door":  # L2: the gap's lower cell waits for its door; the one above stays open
        return planned.block == "door" and material != "door"
    return planned.part in FITTINGS and material != planned.block
```

- [ ] **Step 5: No creature passes a door, and creatures inside are put out when it goes in**

In `backend/survival/creatures/moves.py`, replace:

```python
    then claimed ground no longer holds it back, so it can still step somewhere and get out."""
```

with:

```python
    then claimed ground no longer holds it back, so it can still step somewhere and get out. L2: no
    land creature steps into or through a door (`past_doors`)."""
```

and replace:

```python
    return [step for step in moves(grid, cell) if not grid.swimming(step) and (trapped or not grid.claimed(step))]
```

with:

```python
    return [step for step in moves(grid, cell) if not grid.swimming(step) and (trapped or not grid.claimed(step))
            and past_doors(grid, cell, step)]


def past_doors(grid: Grid, start: Cell, step: Cell) -> bool:
    """L2: a door is solid to creatures (Mimo walks through it): neither the cell a move ends in nor
    the cell it passes on the way (the level cell of a drop) may hold one."""
    return all(grid.material(*cell) != "door" for cell in (step, (step[0], start[1], step[2])))
```

Create `backend/survival/creatures/eviction.py`:

```python
"""Creatures out of what Mimo built (L2).

Creatures never step into a cell something Mimo built claims (creatures.moves.steps),
but one can be standing in one already: a rabbit that wandered onto the site before the walls
went up. When a shelter's door goes in (building.note_building), every creature inside the
shelter's claimed cells is put out just beyond the cell in front of the door, so the shelter is
Mimo's alone from then on; with nowhere to stand out there it is removed.
"""

from __future__ import annotations

from backend.survival.blueprints import Blueprint
from backend.survival.creatures.table import cell_of, dead
from backend.survival.grid import Cell, Grid

EVICT_REACH = 8.0  # blocks from the shelter's home cell that its claimed cells lie within
OUT_STEPS = 3  # cells straight out past the front cell where a creature may be put


def outside(grid: Grid, blueprint: Blueprint) -> Cell | None:
    """The first cell straight out past the cell in front of the door where a creature can stand."""
    door, front = blueprint.one("door"), blueprint.front
    if door is None or front is None:
        return None
    dx, dz = front[0] - door[0], front[2] - door[2]
    for step in range(1, OUT_STEPS + 1):
        x, z = front[0] + dx * step, front[2] + dz * step
        for y in range(front[1] + 2, front[1] - 3, -1):
            cell = (x, y, z)
            if grid.standable(cell) and not grid.swimming(cell) and not grid.claimed(cell):
                return cell
    return None


def evict(grid: Grid, blueprint: Blueprint) -> list[dict]:
    """Put every living creature standing in a cell the shelter claims outside it. Returns them."""
    herd = grid.herd
    if herd is None:
        return []
    ax, _, az = blueprint.anchor
    out = outside(grid, blueprint)
    moved = []
    for creature in herd.near(ax, az, EVICT_REACH):
        if dead(creature) or not grid.claimed(cell_of(creature)):
            continue
        if out is None:
            herd.remove(creature["id"])
            continue
        creature["x"], creature["y"], creature["z"] = map(float, out)
        creature["state"].update(path=None, pose="idle", home=list(out))
        herd.save(creature)
        moved.append(creature)
    return moved
```

In `backend/survival/building.py`, replace:

```python
its back corner and a campfire (carried, or made from 2 logs and 3 sticks) beside the door. A
```

with:

```python
its back corner, a campfire (carried, or made from 2 logs and 3 sticks) beside the door and (L2) a
door (carried, or made from 6 planks) in the door gap, older shelters too. A
```

and replace:

```python
to chop), lifts Mimo's mood for each torch and asks for a new choice when Mimo's arms get full.
```

with:

```python
to chop), lifts Mimo's mood for each torch, puts any creature inside out when the door goes in
(L2, backend.survival.creatures.eviction) and asks for a new choice when Mimo's arms get full.
```

and replace:

```python
from backend.survival.cooking import made
from backend.survival.foraging import reach_steps, whole_walk
```

with:

```python
from backend.survival.cooking import made
from backend.survival.creatures.eviction import evict
from backend.survival.foraging import reach_steps, whole_walk
```

and replace:

```python
FURNISHINGS = ("bed", "campfire")
```

with:

```python
FURNISHINGS = ("bed", "campfire", "door")
```

and replace:

```python
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + TORCH_MOOD)
```

with:

```python
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + TORCH_MOOD)
        if kind == "place" and step.get("block") == "door" and number is not None:
            shelter = next((found for found in structures(db) if found["id"] == number), None)
            if shelter is not None:
                evict(context.grid, blueprint_of(shelter))
```

- [ ] **Step 6: The home Mimo built stays home from twice as far**

A shelter with a door is the safe place at night. Measured: with the door furnished, the seed 8 run of `test_survival_days.py` wandered more than 64 blocks from its shelter chasing work and then slept in the open; going back from up to 128 blocks keeps it in bed at night.

In `backend/survival/purposes.py`, replace:

```python
HOME_RANGE = 64.0
SLEEP_HOME_REACH = 8.0
```

with:

```python
HOME_RANGE = 64.0
# L2: a shelter Mimo built, with its door, is the safe place at night, so Mimo goes back to it from
# twice as far as to any other home or shelter it remembers.
BUILT_HOME_RANGE = 2 * HOME_RANGE
SLEEP_HOME_REACH = 8.0
```

and replace:

```python
    """The home Mimo built, when it is within HOME_RANGE blocks (M5); else the nearest remembered
    home or shelter within HOME_RANGE."""
    home = nearest(s.places, s.here, ("home",), HOME_RANGE)
```

with:

```python
    """The home Mimo built, when it is within BUILT_HOME_RANGE blocks (M5, doubled in L2); else the
    nearest remembered home or shelter within HOME_RANGE."""
    home = nearest(s.places, s.here, ("home",), BUILT_HOME_RANGE)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_doors.py"`
Expected: `Ran 7 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 692 tests` … `OK` (7 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 3 tests` … `OK`

Run: `cd frontend && npm test && npm run build`
Expected: `Tests  259 passed (259)` and the build succeeds. The viewer does not mesh doors (layer `none`), so until Task 11 a door gap looks open.

- [ ] **Step 8: Commit**

```bash
git add shared/blocks.json backend/services/crafting.py backend/survival/blueprints.py backend/survival/structures.py backend/survival/building.py backend/survival/creatures/moves.py backend/survival/creatures/eviction.py backend/survival/purposes.py backend/tests/test_blocks.py backend/tests/test_survival_doors.py frontend/src/engine/blocks.test.ts
git commit -m "feat: doors that Mimo walks through and creatures never do, in every shelter's door gap" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Light levels

**Files:**
- Create: `backend/survival/light.py`
- Modify: `backend/survival/lighting.py` (its docstring: torches now keep hostiles away)
- Test: `backend/tests/test_survival_light.py`

**Interfaces:**
- Consumes: `grid.Grid` (`material`, `placed_cells`), `worldgen.terrain_height`, `blocks.is_solid`.
- Produces `backend.survival.light`:
  - `SKY_DAY = 15`, `SKY_NIGHT = 4`, `DARK = 7`, `BLOCK_LIGHT = {"torch": 14, "lantern": 15, "campfire": 13, "furnace": 13}`, `LIGHT_REACH = 15`.
  - `sky_open(grid, seed, cell) -> bool`: nothing solid but leaves in the column over the cell, up to 8 cells above the natural ground (or the cell).
  - `sky_light(grid, seed, cell, night) -> int`: 15 by day, 4 at night when open to the sky, else 0.
  - `Lights(grid, center, reach)`: the light blocks placed within `reach + 15` blocks (across) of `center`, read once; `.at(cell) -> int` is the brightest source less its Manhattan distance, at least 0.
  - `light_at(grid, seed, cell, night, lights=None) -> int` and `dark(grid, seed, cell, night, lights=None) -> bool` (light 7 or less).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_light.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival.grid import Grid
from backend.survival.light import DARK, SKY_DAY, SKY_NIGHT, Lights, dark, light_at, sky_open


def hillside(blocks=None):
    """Grass at y 0, stone below with a cave at y -3..-2 under x 5..8, and `blocks` placed."""
    def natural(x, y, z):
        if y == 0:
            return "grass"
        if y < 0:
            return "air" if 5 <= x <= 8 and -3 <= y <= -2 else "stone"
        return "air"

    grid = Grid(natural)
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    return grid


class LightTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("backend.survival.light.terrain_height", lambda x, z, seed: 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_sky_lights_open_ground_by_day_and_dimly_at_night(self):
        grid = hillside({(3, 5, 0): "leaves"})
        self.assertEqual((light_at(grid, "1", (0, 1, 0), False), light_at(grid, "1", (0, 1, 0), True)),
                         (SKY_DAY, SKY_NIGHT))
        self.assertTrue(sky_open(grid, "1", (3, 1, 0)))  # leaves let the sky through
        self.assertFalse(dark(grid, "1", (0, 1, 0), False))
        self.assertTrue(dark(grid, "1", (0, 1, 0), True))
        self.assertLessEqual(SKY_NIGHT, DARK)

    def test_caves_roofs_and_tunnels_are_dark_by_day_but_an_open_pit_is_not(self):
        grid = hillside({(0, 3, 0): "planks", (2, 0, 0): "air", (2, -1, 0): "air"})
        self.assertEqual(light_at(grid, "1", (6, -3, 0), False), 0)  # in the cave
        self.assertEqual(light_at(grid, "1", (0, 1, 0), False), 0)  # under a roof
        self.assertEqual(light_at(grid, "1", (2, -1, 0), False), SKY_DAY)  # at the bottom of a pit
        self.assertTrue(dark(grid, "1", (6, -3, 0), False))

    def test_torches_lanterns_and_fires_light_what_is_near_one_level_less_a_block(self):
        grid = hillside({(0, 1, 0): "torch", (20, 1, 0): "lantern", (40, 1, 0): "campfire", (60, 1, 0): "furnace"})
        lights = Lights(grid, (30, 1, 0), 40)
        self.assertEqual([lights.at(cell) for cell in ((0, 1, 0), (3, 1, 0), (0, 3, 2), (20, 1, 1), (40, 1, 0), (60, 2, 0))],
                         [14, 11, 10, 14, 13, 12])
        self.assertEqual(lights.at((0, 1, 100)), 0)
        self.assertEqual(light_at(grid, "1", (6, -3, 0), False, lights), 4)  # through the rock, 10 blocks off
        self.assertEqual(light_at(grid, "1", (6, 1, 0), True), 8)  # a torch keeps 6 blocks around it safe
        self.assertTrue(dark(grid, "1", (7, 1, 0), True))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_light.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.light'`.

- [ ] **Step 3: Write the light levels**

Create `backend/survival/light.py`:

```python
"""Light levels (spec L2, "Light levels"): what keeps the dark creatures away.

A cell's light is the brighter of its sky light and its block light, from 0 (pitch dark) to 15.
- Sky light is 15 by day (dawn, day and dusk) and 4 at night for a cell open to the sky, and 0
  for a covered one. A cell is open to the sky when nothing solid stands in the column over it
  up to SKY_SCAN cells above the natural ground (leaves let the sky through): a cave, a tunnel
  and the inside of a roofed shelter are covered, a pit Mimo dug is not (`sky_open`).
- Block light comes from placed torches (14), lanterns (15), campfires (13) and furnaces (13) and
  fades by one level per block of Manhattan distance, walls or not. It is worked out on demand
  from the light blocks near a spot, never stored (`Lights`).
Hostile creatures spawn only where the light is 7 or less (DARK), so torches around home keep the
yard safe; a kind that burns does so under the open sky by day (backend.survival.creatures).
"""

from __future__ import annotations

from backend.services.blocks import is_solid
from backend.services.worldgen import terrain_height
from backend.survival.grid import Cell, Grid

SKY_DAY = 15
SKY_NIGHT = 4
DARK = 7  # hostiles spawn only where the light is this or less
BLOCK_LIGHT = {"torch": 14, "lantern": 15, "campfire": 13, "furnace": 13}
LIGHT_REACH = max(BLOCK_LIGHT.values())  # the farthest any block light carries
SKY_SCAN = 8  # cells over the natural ground (or the cell, when it is higher) that can cover a cell
SEE_THROUGH = ("leaves",)


def sky_open(grid: Grid, seed: str, cell: Cell) -> bool:
    """Nothing solid but leaves over the cell, up to SKY_SCAN cells above the natural ground."""
    x, y, z = cell
    top = max(y, terrain_height(x, z, seed)) + SKY_SCAN
    for above in range(y + 1, top + 1):
        material = grid.material(x, above, z)
        if is_solid(material) and material not in SEE_THROUGH:
            return False
    return True


def sky_light(grid: Grid, seed: str, cell: Cell, night: bool) -> int:
    if not sky_open(grid, seed, cell):
        return 0
    return SKY_NIGHT if night else SKY_DAY


class Lights:
    """The light blocks placed within `reach` blocks of a spot (plus how far light carries), looked
    up once, so the block light of every cell near the spot costs no further reads."""

    def __init__(self, grid: Grid, center: Cell, reach: float):
        x, _, z = center
        self.sources = [(cell, BLOCK_LIGHT[material])
                        for cell, material in grid.placed_cells(x, z, reach + LIGHT_REACH, tuple(BLOCK_LIGHT))]

    def at(self, cell: Cell) -> int:
        """The block light at `cell`: the brightest source less its Manhattan distance, at least 0."""
        x, y, z = cell
        return max([level - abs(x - sx) - abs(y - sy) - abs(z - sz) for (sx, sy, sz), level in self.sources] + [0])


def light_at(grid: Grid, seed: str, cell: Cell, night: bool, lights: Lights | None = None) -> int:
    """The light level of `cell`: the brighter of sky light and block light."""
    lights = lights if lights is not None else Lights(grid, cell, 0)
    return max(sky_light(grid, seed, cell, night), lights.at(cell))


def dark(grid: Grid, seed: str, cell: Cell, night: bool, lights: Lights | None = None) -> bool:
    """Dark enough for hostile creatures to spawn: light 7 or less."""
    return light_at(grid, seed, cell, night, lights) <= DARK
```

In `backend/survival/lighting.py`, replace:

```python
and each one lifts Mimo's mood a little (building.note_building); in sub-project 3 they will keep
creatures away. A mushroom or sapling on a corner is mined first (structures.clearing). The
walks to the corners go all the way or not at all, and head_home leaves light_up alone, since it
keeps Mimo at home.
```

with:

```python
and each one lifts Mimo's mood a little (building.note_building); their light (14, one less a
block) keeps hostile creatures from spawning around home (L2, backend.survival.light). A mushroom
or sapling on a corner is mined first (structures.clearing). The walks to the corners go all the
way or not at all, and head_home leaves light_up alone, since it keeps Mimo at home.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_light.py"`
Expected: `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 695 tests` … `OK` (3 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/light.py backend/survival/lighting.py backend/tests/test_survival_light.py
git commit -m "feat: light levels from the sky and from torches, lanterns, fires and furnaces" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Hostile creatures and their blows

**Files:**
- Modify: `backend/survival/creatures/kinds.py` (`cooldown`, `burns`, `height`), `backend/survival/creatures/acts.py` (the Scene knows the clock; a wander keeps to the kind's height), `backend/survival/creatures/moves.py` (room for a tall creature), `backend/survival/creatures/combat.py` (a hit hostile turns on Mimo; a kill of one is a fight, not a hunt), `backend/survival/creatures/simulate.py` (pass the clock), `backend/survival/vitals.py` (1 health a game minute), `backend/survival/world.py` (`hurt`, `fight` and `threat` are routine)
- Create: `backend/survival/creatures/harm.py`, `backend/survival/creatures/hostiles.py`
- Modify tests: `backend/tests/test_survival_creatures.py`, `backend/tests/test_survival_creature_acts.py` (hostile kinds and actions are registered now), `backend/tests/test_survival_vitals.py`
- Test: `backend/tests/test_survival_hostiles.py`

**Interfaces:**
- Consumes: `kinds.register_kind`, `acts.register_action`, `acts.Scene`, `acts.wander`, `acts.pause`, `moves.move`, `moves.steps`, `moves.where`, `combat.strike`, `light.sky_open`, `memory.remember`, `triggers.crossings`, `triggers.mark_trigger`, `triggers.ensure_brain`.
- Produces:
  - `Kind` gains `cooldown: float = 1.0` (seconds between its attacks), `burns: bool = False` and `height: int = 1` (cells of room it needs). `acts.height_of(creature) -> int`. `moves.steps(grid, cell, water, height=1)`: a step needs `height` cells of room.
  - `acts.Scene` gains `clock: dict` (kw_only, default `{}`, which reads as day at 1x) and the properties `night` and `scale` (game seconds per server second). `simulate` passes `clock=context.clock_at(at)`.
  - `backend.survival.creatures.harm`: `ARMOR = {"leather_cap": 0.08, "leather_tunic": 0.12}`, `INDOORS = ("room", "passage")`, `armor_cut(inventory) -> float`, `sheltered(db, cell) -> bool` (a room or passage cell of a shelter Mimo built; False without the memory tables), `pet_alive(state) -> bool`, `hurt_pet(scene, damage, source) -> float` (the health lost: sets `state["hurt_at"]`, `state["hurt_by"]` and `last_thought`, remembers a `danger` place noted with the kind, marks urgent crossings of 50/30/15, logs a routine `hurt` event at most every `HURT_QUIET = 10` seconds).
  - `backend.survival.creatures.hostiles` registers the kinds `gloomling` (20 health, 0.9 s a block, 3 damage every 1.2 s from 1.5 blocks, 1.7 tall and 2 cells of room, burns, 0–2 `gloom_dust`) and `skitter` (12 health, 0.4 s a block, 2 damage every 1.0 s from 1.5 blocks, 0.6 tall, 0–2 `string`), neither fleeing when hurt, and the creature actions `sunlit` (2), `strike` (4), `chase` (6) and `prowl` (25). Also `can_hit(grid, cell, target, reach) -> bool`, `hostile_near(grid, state) -> bool` (for the tick, Task 7) and the constants `CHASE_SIGHT = 16`, `GIVE_UP = 24`, `CHASE_STEPS = 2`, `CHASE_RISE = 4`, `BURN_SECONDS = 3`, `ALARM_GAP = 300` game seconds, `LOITER = 120` game seconds.
  - `combat.spoils(state, creature, found, at) -> (kind, text)`: the kill's drops go into Mimo's arms; a hostile kill returns `("fight", "Pip fought off a gloomling.")`, any other `("hunt", ...)` and sets `hunted_at` as before. `finish_attack` returns it. `strike` sets `state["chasing"] = True` on a hit hostile.
  - `vitals.HEAL_RATE = 1 / 60`: 1 health a game minute, under M1's conditions (fed and warm).
  - `world.ROUTINE_EVENTS` gains `hurt`, `fight` and `threat`.

Nothing spawns hostiles yet (Task 7). Registering the hostile actions ahead of the animals' changes nothing for the animals: each hostile action's check starts with `kind.hostile`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_hostiles.py`:

```python
import sqlite3
import unittest

from backend.survival.creatures.acts import Scene, act
from backend.survival.creatures.combat import drops_of, strike
from backend.survival.creatures.harm import armor_cut, hurt_pet
from backend.survival.creatures.hostiles import BURN_SECONDS, CHASE_STEPS, LOITER
from backend.survival.creatures.kinds import KINDS, huntable, land_kinds
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables, dead
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, places
from backend.survival.steps import finish_step, start_step
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS

NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}
DAY = {**NIGHT, "phase": "day", "seconds_into_day": 1000.0}


def meadow(blocks=None):
    """Grass at y 0 with `blocks` placed, creatures and memory in one database."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    create_memory_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "died_at": None, "brain": new_brain(0.0), "last_thought": ""}
    state["brain"]["pending"] = None
    state.update(changes)
    return state


def scene(grid, state, at=10.0, clock=NIGHT):
    return Scene(grid, grid.herd, "5", state, at, 1.0, events=[], clock=clock)


def hostile(grid, kind="gloomling", cell=(5, 1, 0), **state):
    return grid.herd.add(kind, cell, KINDS[kind].health, 0.0, 0.0, {"home": list(cell), "turn": 0, "pose": "idle",
                                                                     **state})


class KindTests(unittest.TestCase):
    def test_gloomlings_and_skitters_are_hostile_and_never_hunted_or_spawned_in_herds(self):
        gloom, skitter = KINDS["gloomling"], KINDS["skitter"]
        self.assertEqual((gloom.health, gloom.damage, gloom.cooldown, gloom.burns), (20.0, 3.0, 1.2, True))
        self.assertEqual((skitter.health, skitter.damage, skitter.cooldown, skitter.burns), (12.0, 2.0, 1.0, False))
        self.assertLess(skitter.speed, gloom.speed)  # seconds per block: the skitter is fast
        self.assertEqual((gloom.drops, skitter.drops), ({"gloom_dust": (0, 2)}, {"string": (0, 2)}))
        for kind in (gloom, skitter):
            self.assertTrue(kind.hostile)
            self.assertFalse(kind.flee_when_hurt)
            self.assertFalse(huntable(kind))
            self.assertNotIn(kind, land_kinds("meadow"))


class ChaseTests(unittest.TestCase):
    def test_a_hostile_within_sixteen_blocks_comes_two_blocks_a_turn_and_raises_the_alarm_once(self):
        grid, state = meadow(), pet()
        gloom = hostile(grid, cell=(10, 1, 0))
        night = scene(grid, state)
        self.assertEqual(act(gloom, night), "chase")
        self.assertEqual((cell_of(gloom), gloom["state"]["pose"], gloom["state"]["chasing"]), ((8, 1, 0), "chasing", True))
        self.assertEqual(len(gloom["state"]["path"]), CHASE_STEPS + 1)
        self.assertAlmostEqual(gloom["next_at"], 10.0 + 2 * KINDS["gloomling"].speed)
        self.assertEqual(state["brain"]["pending"]["reasons"], ["threat"])
        self.assertTrue(state["brain"]["pending"]["urgent"])
        other = hostile(grid, "skitter", (0, 1, 12))
        self.assertEqual(act(other, night), "chase")
        self.assertEqual([event[1:] for event in night.events], [("threat", "Pip saw a gloomling coming.")])

    def test_farther_than_sixteen_it_prowls_and_it_gives_up_a_chase_past_twenty_four(self):
        grid, state = meadow(), pet()
        self.assertEqual(act(hostile(grid, cell=(20, 1, 0)), scene(grid, state)), "prowl")
        self.assertEqual(act(hostile(grid, cell=(20, 1, 0), chasing=True), scene(grid, state)), "chase")
        gone = hostile(grid, cell=(30, 1, 0), chasing=True)
        self.assertEqual(act(gone, scene(grid, state)), "prowl")
        self.assertFalse(gone["state"]["chasing"])

    def test_what_lives_in_a_cave_under_mimo_leaves_it_be_and_fades_after_a_while(self):
        cave = {(x, y, 0): "air" for x in range(2, 6) for y in (-5, -4)}
        grid, state = meadow(cave), pet()
        below = hostile(grid, "skitter", (3, -5, 0))
        self.assertEqual(act(below, scene(grid, state)), "prowl")
        self.assertFalse(dead(below))
        act(below, scene(grid, state, at=LOITER + 1.0))
        self.assertTrue(dead(below))
        self.assertEqual(below["state"]["drops"], [])
        chaser = hostile(grid, cell=(10, 1, 0))
        act(chaser, scene(grid, state, at=LOITER + 1.0))  # coming after Mimo keeps it about
        self.assertFalse(dead(chaser))

    def test_a_hit_hostile_turns_on_mimo_from_farther_away(self):
        grid, state = meadow(), pet()
        gloom = hostile(grid, cell=(20, 1, 0))
        strike(scene(grid, state), gloom, 5.0, (0, 1, 0))
        self.assertEqual((gloom["health"], gloom["state"]["chasing"]), (15.0, True))
        self.assertEqual(act(gloom, scene(grid, state, at=11.0)), "chase")

    def test_a_gloomling_needs_two_cells_of_room_and_a_skitter_one(self):
        ceiling = {(x, 2, z): "planks" for x in (2, 3) for z in range(-3, 4)}
        grid, state = meadow(ceiling), pet()
        gloom, skitter = hostile(grid, cell=(4, 1, 0)), hostile(grid, "skitter", (4, 1, 1))
        self.assertEqual(act(gloom, scene(grid, state)), "chase")
        self.assertEqual((cell_of(gloom), gloom["state"]["pose"]), ((4, 1, 0), "idle"))
        self.assertEqual(act(skitter, scene(grid, state)), "chase")
        self.assertEqual(cell_of(skitter)[0], 2)

    def test_it_waits_at_a_door_it_cannot_pass(self):
        wall = {(2, y, z): "cobblestone" for y in (1, 2) for z in range(-4, 5)}
        grid, state = meadow({**wall, (2, 1, 0): "door", (2, 2, 0): "air"}), pet()
        gloom = hostile(grid, cell=(4, 1, 0))
        at = 10.0
        for _ in range(6):
            act(gloom, scene(grid, state, at))
            at = gloom["next_at"]
            self.assertGreater(cell_of(gloom)[0], 2)
        self.assertEqual(cell_of(gloom), (3, 1, 0))
        self.assertEqual(state["vitals"]["health"], 100.0)


class StrikeTests(unittest.TestCase):
    def test_a_hostile_in_reach_hits_mimo_once_a_cooldown_and_mimo_remembers_the_place(self):
        grid, state = meadow(), pet()
        gloom = hostile(grid, cell=(1, 1, 0))
        first = scene(grid, state, at=10.0)
        self.assertEqual(act(gloom, first), "strike")
        self.assertEqual((state["vitals"]["health"], state["hurt_at"], state["hurt_by"]), (97.0, 10.0, "gloomling"))
        self.assertEqual((gloom["state"]["pose"], gloom["state"]["struck_at"], gloom["next_at"]), ("attacking", 10.0, 11.2))
        self.assertEqual([event[1:] for event in first.events], [("hurt", "Pip was hit by a gloomling.")])
        self.assertEqual(act(gloom, scene(grid, state, at=10.5)), "chase")  # waits out its cooldown, in reach
        self.assertEqual((state["vitals"]["health"], gloom["state"]["pose"], gloom["next_at"]), (97.0, "attacking", 11.2))
        again = scene(grid, state, at=11.2)
        self.assertEqual(act(gloom, again), "strike")
        self.assertEqual((state["vitals"]["health"], again.events), (94.0, []))  # one hurt event in ten seconds
        danger = places(grid.herd.db, ("danger",))
        self.assertEqual([((place["x"], place["y"], place["z"]), place["note"]) for place in danger],
                         [((0, 1, 0), "gloomling")])

    def test_armor_takes_its_share_of_every_blow(self):
        self.assertEqual(armor_cut({}), 0.0)
        self.assertAlmostEqual(armor_cut({"leather_cap": 1}), 0.08)
        self.assertAlmostEqual(armor_cut({"leather_cap": 1, "leather_tunic": 1}), 0.2)
        grid, state = meadow(), pet(inventory={"leather_cap": 1, "leather_tunic": 1})
        self.assertAlmostEqual(hurt_pet(scene(grid, state), 3.0, "gloomling"), 2.4)
        self.assertAlmostEqual(state["vitals"]["health"], 97.6)

    def test_health_falling_past_fifty_asks_for_a_choice_at_once(self):
        grid, state = meadow(), pet(vitals={**START_VITALS, "health": 52.0})
        hurt_pet(scene(grid, state), 3.0, "skitter")
        self.assertEqual(state["brain"]["pending"]["reasons"], ["health_50"])
        self.assertTrue(state["brain"]["pending"]["urgent"])

    def test_no_blow_goes_through_a_wall_or_round_a_roofs_edge(self):
        grid, state = meadow({(1, 1, 0): "planks", (0, 2, 0): "planks"}), pet()
        gloom = hostile(grid, cell=(1, 2, 0))  # up on the wall, the roof's edge between it and Mimo
        self.assertEqual(act(gloom, scene(grid, state)), "chase")
        self.assertEqual((state["vitals"]["health"], gloom["state"]["pose"]), (100.0, "idle"))
        grid.put(0, 2, 0, "air")
        self.assertEqual(act(gloom, scene(grid, state, at=12.0)), "strike")
        self.assertEqual(state["vitals"]["health"], 97.0)

    def test_no_blow_reaches_mimo_inside_its_shelter(self):
        grid, state = meadow(), pet()
        grid.herd.db.execute("INSERT INTO structure_cells(x,y,z,structure,part,block) VALUES (0,1,0,1,'room','air')")
        gloom = hostile(grid, cell=(1, 1, 0))  # in a window gap, say
        self.assertEqual(act(gloom, scene(grid, state)), "chase")
        self.assertEqual(state["vitals"]["health"], 100.0)

    def test_a_dead_mimo_is_left_alone(self):
        grid, state = meadow(), pet(vitals={**START_VITALS, "health": 0.0})
        gloom = hostile(grid, cell=(1, 1, 0))
        self.assertEqual(act(gloom, scene(grid, state)), "prowl")
        self.assertEqual(state["vitals"]["health"], 0.0)


class SunlightTests(unittest.TestCase):
    def test_by_day_a_gloomling_under_the_sky_burns_then_goes_without_drops(self):
        grid, state = meadow(), pet()
        gloom = hostile(grid, cell=(1, 1, 0))
        self.assertEqual(act(gloom, scene(grid, state, clock=DAY)), "sunlit")
        self.assertEqual((gloom["state"]["pose"], gloom["state"]["burning_at"], gloom["next_at"]),
                         ("burning", 10.0, 10.0 + BURN_SECONDS))
        self.assertEqual(state["vitals"]["health"], 100.0)  # a burning gloomling strikes no more
        act(gloom, scene(grid, state, at=gloom["next_at"], clock=DAY))
        self.assertTrue(dead(gloom))
        self.assertEqual((gloom["health"], gloom["state"]["drops"], gloom["state"]["dead_at"]), (0.0, [], 13.0))

    def test_a_skitter_in_the_open_fades_at_once_and_a_roof_keeps_both_from_the_sun(self):
        grid, state = meadow({(5, 4, 0): "planks", (6, 4, 0): "planks"}), pet()
        skitter = hostile(grid, "skitter", (9, 1, 0))
        act(skitter, scene(grid, state, clock=DAY))
        self.assertTrue(dead(skitter))
        for kind, cell in (("skitter", (5, 1, 0)), ("gloomling", (6, 1, 0))):
            covered = hostile(grid, kind, cell)
            self.assertEqual(act(covered, scene(grid, state, clock=DAY)), "chase")
        self.assertNotEqual(act(hostile(grid, cell=(9, 1, 0)), scene(grid, state)), "sunlit")  # at night


class FightingBackTests(unittest.TestCase):
    def test_a_hostile_mimo_kills_leaves_its_drops_and_is_no_hunt(self):
        grid, state = meadow(), pet(inventory={"iron_sword": 1})
        skitter = hostile(grid, "skitter", (2, 1, 0))
        skitter["health"] = 5.0
        grid.herd.save(skitter)
        step = start_step({"kind": "attack", "creature": skitter["id"]}, state, grid, 10.0)
        self.assertEqual(finish_step(step, state, grid, 10.5), ("fight", "Pip fought off a skitter."))
        self.assertEqual(state["inventory"], {"iron_sword": 1, **drops_of("5", skitter, KINDS["skitter"])})
        self.assertNotIn("hunted_at", state)
        self.assertTrue(dead(grid.herd.get(skitter["id"])))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_creatures.py`, replace:

```python
        for kind in KINDS.values():
```

with:

```python
        for kind in (KINDS[name] for name in ("rabbit", "chicken", "sheep", "cow", "fish")):
```

In `backend/tests/test_survival_creature_acts.py`, replace:

```python
        sit = register_action(CreatureAction("test_sit", 5, lambda creature, kind, scene: True,
```

with:

```python
        sit = register_action(CreatureAction("test_sit", 0, lambda creature, kind, scene: True,
```

In `backend/tests/test_survival_vitals.py`, replace:

```python
        self.assertAlmostEqual(after["health"], 53.0)
```

with:

```python
        self.assertAlmostEqual(after["health"], 51.0)  # 1 a game minute (L2)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_hostiles.py"`
Expected: an ImportError (`backend.survival.creatures.harm` does not exist yet).

- [ ] **Step 3: Give kinds a cooldown, a burn and a height, and the Scene a clock**

In `backend/survival/creatures/kinds.py`, replace:

```python
    flee_when_hurt: bool = True
```

with:

```python
    flee_when_hurt: bool = True
    cooldown: float = 1.0  # L2: seconds between two of its attacks
    burns: bool = False  # L2: burns and fades under the open sky by day
    height: int = 1  # L2: cells of room it needs to pass (a gloomling needs 2)
```

In `backend/survival/creatures/moves.py`, replace:

```python
def steps(grid: Grid, cell: Cell, water: bool) -> list[Cell]:
```

with:

```python
def steps(grid: Grid, cell: Cell, water: bool, height: int = 1) -> list[Cell]:
```

and replace:

```python
    land creature steps into or through a door (`past_doors`)."""
```

with:

```python
    land creature steps into or through a door (`past_doors`), and one `height` cells tall only
    where it has the room."""
```

and replace:

```python
            and past_doors(grid, cell, step)]
```

with:

```python
            and past_doors(grid, cell, step)
            and all(grid.passable((step[0], step[1] + up, step[2])) for up in range(1, height))]
```

In `backend/survival/creatures/acts.py`, replace:

```python
from backend.survival.creatures.kinds import Kind, huntable, kind_of
```

with:

```python
from backend.survival.clock import is_night
from backend.survival.creatures.kinds import Kind, huntable, kind_of
```

and replace:

```python
    events: list = field(kw_only=True)
```

with:

```python
    events: list = field(kw_only=True)
    clock: dict = field(default_factory=dict, kw_only=True)  # L2: the game clock at `at`; {} reads as day at 1x

    @property
    def night(self) -> bool:
        return is_night(self.clock.get("phase", "day"))

    @property
    def scale(self) -> float:
        """Game seconds per server second (MIMO_TIME_SCALE)."""
        return float(self.clock.get("time_scale", 1.0))
```

and replace:

```python
def wander_cells(creature: dict, scene: Scene) -> list[Cell]:
```

with:

```python
def height_of(creature: dict) -> int:
    """L2: the cells of room a creature of this kind needs to pass."""
    kind = kind_of(creature["kind"])
    return 1 if kind is None else kind.height


def wander_cells(creature: dict, scene: Scene) -> list[Cell]:
```

and replace:

```python
        options = [step for step in steps(scene.grid, cell, False) if step not in cells]
```

with:

```python
        options = [step for step in steps(scene.grid, cell, False, height_of(creature)) if step not in cells]
```

In `backend/survival/creatures/simulate.py`, replace:

```python
        return
    scene = Scene(grid, grid.herd, state.get("world_seed", "0"), state, at, context.action_scale,
```

with:

```python
        return
    clock = context.clock_at(at)
    scene = Scene(grid, grid.herd, state.get("world_seed", "0"), state, at, context.action_scale,
```

and replace:

```python
                  events=context.events)
    scale = context.clock_at(at)["time_scale"]
```

with:

```python
                  events=context.events, clock=clock)
    scale = clock["time_scale"]
```

- [ ] **Step 4: Write what a blow does to Mimo**

Create `backend/survival/creatures/harm.py`:

```python
"""What a creature's blow does to Mimo (spec L2, "Mimo's health" and "Armor").

A hostile creature's blow (backend.survival.creatures.hostiles) takes its kind's damage from
Mimo's health, less the share the armor Mimo carries takes off: a leather cap 8 % and a leather
tunic 12 %, 20 % together (iron armor comes in L3). Armor is worn by carrying it. No blow reaches
Mimo inside its shelter, in a room or passage cell of one it built (`sheltered`), not even from a
window gap. A blow:
- marks Mimo hurt (`state["hurt_at"]`, `state["hurt_by"]`), which the viewer flashes;
- remembers the place as a danger, noted with the creature's kind (memory kind "danger");
- asks for a new choice at once (urgent) when health falls past 50, 30 or 15, as a vital
  crossing does in the tick;
- logs a routine "hurt" event, at most one every HURT_QUIET seconds, so a fight does not flood
  the event log.
At 0 health Mimo dies of it: the tick records the death with the kind as its cause
(backend.survival.tick, "Pip was caught by a gloomling on day 3.").
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from backend.survival.creatures.table import missing_table
from backend.survival.memory import remember
from backend.survival.triggers import crossings, mark_trigger

if TYPE_CHECKING:
    from backend.survival.creatures.acts import Scene

ARMOR = {"leather_cap": 0.08, "leather_tunic": 0.12}  # the share of a blow each piece takes off
INDOORS = ("room", "passage")  # the parts of a shelter Mimo is safe in
HURT_QUIET = 10.0  # server seconds (at the normal pace) between two "hurt" events


def armor_cut(inventory: dict) -> float:
    """The share of a blow the armor Mimo carries takes off."""
    return sum(cut for piece, cut in ARMOR.items() if inventory.get(piece, 0) > 0)


def sheltered(db: sqlite3.Connection, cell: tuple[int, int, int]) -> bool:
    """`cell` is a room or passage cell of a shelter Mimo built."""
    try:
        row = db.execute("SELECT part FROM structure_cells WHERE x=? AND y=? AND z=?", cell).fetchone()
    except sqlite3.OperationalError as error:
        if not missing_table(error):  # a database without memory: unit tests of creatures alone
            raise
        return False
    return row is not None and row[0] in INDOORS


def pet_alive(state: dict) -> bool:
    return state.get("died_at") is None and state["vitals"]["health"] > 0


def hurt_pet(scene: Scene, damage: float, source: str) -> float:
    """Mimo takes a blow from a creature of kind `source`. Returns the health it lost."""
    state = scene.state
    vitals = state["vitals"]
    before = dict(vitals)
    lost = min(vitals["health"], damage * (1.0 - armor_cut(state["inventory"])))
    vitals["health"] = max(0.0, vitals["health"] - lost)
    name = source.replace("_", " ")
    last = state.get("hurt_at")
    if last is None or scene.at - last >= HURT_QUIET / scene.pace:
        scene.events.append((scene.at, "hurt", f"{state['name']} was hit by a {name}."))
    state.update(hurt_at=scene.at, hurt_by=source, last_thought=f"Ow! A {name}!")
    for reason in crossings(before, vitals):
        mark_trigger(state, reason, scene.at, urgent=True)
    try:
        remember(scene.herd.db, "danger", scene.pet, scene.at, source)
    except sqlite3.OperationalError as error:
        if not missing_table(error):  # a database without memory: unit tests of creatures alone
            raise
    return lost
```

- [ ] **Step 5: Write the hostile kinds and their actions**

Create `backend/survival/creatures/hostiles.py`:

```python
"""The hostile creatures and what they do (spec L2, "Hostile kinds" and "Hostile AI").

- gloomling: 20 health, slow (0.9 s a block), a blow of 3 every 1.2 s from 1.5 blocks. It walks
  dark ground at night and caves at any hour, and burns and fades under the open sky by day. It
  drops 0 to 2 gloom_dust (for lanterns or potions in L3).
- skitter: 12 health, fast (0.4 s a block), a blow of 2 every second. It lives in caves and other
  covered dark places, and fades when it is caught under the open sky by day. It drops 0 to 2
  string (a bow takes 3).
Neither runs from a blow (a hit one turns on Mimo instead) and neither is hunted. Both are kinds
in the registry and act through the creature-action registry, ahead of the animals' actions:
- sunlit (2): under the open sky by day (backend.survival.light.sky_open) a gloomling catches
  fire ("burning") and dies BURN_SECONDS later without drops; a skitter fades at once.
- strike (4): within its reach of a living Mimo, with nothing solid between them (`can_hit`: a
  blow does not go through a wall or round a roof's edge), once its cooldown has passed, it hits
  Mimo (backend.survival.creatures.harm) and waits out the cooldown; never while Mimo is inside
  its shelter (harm.sheltered).
- chase (6): within 16 blocks of Mimo (and no more than 4 above or below it, so what lives in a
  cave under Mimo's feet leaves it be), or 24 once it is after Mimo or was just hurt by it, it
  moves up to 2 blocks toward Mimo, each step to the neighbour nearest Mimo, never through a
  door, into anything Mimo built or, for a gloomling (2 cells tall), under a ceiling lower than
  that (creatures.moves.steps): Mimo is safe in its
  shelter, and a hostile outside waits at the wall. The first to come after Mimo outside its
  shelter raises the alarm: an urgent "threat" choice and event, at most one every 5 game
  minutes, so a model picker (Jev) can react at once.
- prowl (25): otherwise it gives up the chase and wanders near where it spawned, or stands. One
  that has not come after Mimo for LOITER game seconds fades away, so the few hostiles about are
  the ones Mimo has to deal with, and new ones can come out where it is.
Spawning in the dark, the cap of 8 and despawning far away are backend.survival.creatures.darkness.
"""

from __future__ import annotations

import math

from backend.survival.creatures.acts import (
    IDLE_SECONDS, PAUSE, WANDER, WANDER_CHANCE, CreatureAction, Scene, flat_distance, pause, register_action, wander,
)
from backend.survival.creatures.harm import hurt_pet, pet_alive, sheltered
from backend.survival.creatures.kinds import Kind, kind_of, register_kind
from backend.survival.creatures.moves import heading, move, steps, where
from backend.survival.creatures.table import dead
from backend.survival.grid import Cell, Grid
from backend.survival.light import sky_open
from backend.survival.triggers import ensure_brain, mark_trigger

CHASE_SIGHT = 16.0
GIVE_UP = 24.0
CHASE_STEPS = 2
ROUSED = 10.0  # server seconds after Mimo hurts a hostile that it chases Mimo from as far as GIVE_UP
BURN_SECONDS = 3.0
ALARM_GAP = 300.0  # game seconds between two "threat" choices
WAIT = (0.5, 1.5)  # seconds a chaser that cannot get closer waits before it looks again
CHASE_RISE = 4  # blocks above or below Mimo a hostile may be to come after it
LOITER = 120.0  # game seconds a hostile stays about without coming after Mimo

register_kind(Kind("gloomling", health=20.0, speed=0.9, size=1.7, hostile=True, damage=3.0, reach=1.5,
                   drops={"gloom_dust": (0, 2)}, flee_when_hurt=False, cooldown=1.2, burns=True, height=2))
register_kind(Kind("skitter", health=12.0, speed=0.4, size=0.6, hostile=True, damage=2.0, reach=1.5,
                   drops={"string": (0, 2)}, flee_when_hurt=False, cooldown=1.0))


# sunlit ----------------------------------------------------------------------------------------

def sunlit(creature: dict, kind: Kind, scene: Scene) -> bool:
    return kind.hostile and not scene.night and sky_open(scene.grid, scene.seed, where(creature, scene.at))


def vanish(creature: dict, scene: Scene) -> None:
    """Gone without a trace: dead now, with no drops (the viewer shows its puff)."""
    creature["x"], creature["y"], creature["z"] = map(float, where(creature, scene.at))
    creature["health"] = 0.0
    creature["state"].update(pose="dead", dead_at=scene.at, drops=[], path=None, chasing=False)


def fade(creature: dict, kind: Kind, scene: Scene) -> None:
    """A gloomling catches fire first and dies when its next turn comes; anything else fades now."""
    state = creature["state"]
    if kind.burns and state.get("burning_at") is None:
        state.update(pose="burning", burning_at=scene.at, chasing=False, path=None)
        creature["next_at"] = scene.at + BURN_SECONDS / scene.pace
        return
    vanish(creature, scene)


register_action(CreatureAction("sunlit", 2, sunlit, fade))


# strike ----------------------------------------------------------------------------------------

def can_hit(grid: Grid, cell: Cell, target: Cell, reach: float) -> bool:
    """`target` is within `reach` of `cell` and open to it: when the two cells differ along two
    axes (a diagonal), at least one of the corner cells between them is not solid."""
    if math.dist(cell, target) > reach:
        return False
    differ = [axis for axis in range(3) if cell[axis] != target[axis]]
    if len(differ) < 2:
        return True
    corners = [tuple(target[index] if index == axis else cell[index] for index in range(3)) for axis in differ]
    return any(not grid.solid(corner) for corner in corners)


def in_reach(creature: dict, kind: Kind, scene: Scene) -> bool:
    return can_hit(scene.grid, where(creature, scene.at), scene.pet, kind.reach)


def cooled(creature: dict, kind: Kind, scene: Scene) -> bool:
    return scene.at >= creature["state"].get("struck_at", -math.inf) + kind.cooldown / scene.pace


def strikes(creature: dict, kind: Kind, scene: Scene) -> bool:
    return (kind.hostile and kind.damage > 0 and pet_alive(scene.state) and in_reach(creature, kind, scene)
            and cooled(creature, kind, scene) and not sheltered(scene.herd.db, scene.pet))


def strike_pet(creature: dict, kind: Kind, scene: Scene) -> None:
    creature["heading"] = heading(where(creature, scene.at), scene.pet, creature["heading"])
    creature["state"].update(pose="attacking", struck_at=scene.at, chasing=True)
    hurt_pet(scene, kind.damage, kind.name)
    creature["next_at"] = scene.at + kind.cooldown / scene.pace


register_action(CreatureAction("strike", 4, strikes, strike_pet))


# chase -----------------------------------------------------------------------------------------

def chases(creature: dict, kind: Kind, scene: Scene) -> bool:
    if not kind.hostile or not pet_alive(scene.state):
        return False
    here = where(creature, scene.at)
    distance = flat_distance(here, scene.pet)
    if abs(here[1] - scene.pet[1]) > CHASE_RISE:
        return False
    state = creature["state"]
    roused = state.get("chasing") or scene.at - state.get("hurt_at", -math.inf) <= ROUSED / scene.pace
    return distance <= CHASE_SIGHT or (bool(roused) and distance <= GIVE_UP)


def hostile_near(grid: Grid, state: dict) -> bool:
    """A living hostile could come after Mimo now: one within CHASE_SIGHT across and CHASE_RISE up
    or down, while Mimo is not in a cell something it built claims (its shelter keeps them out).
    The tick then runs in short steps (backend.survival.tick)."""
    position = state["position"]
    x, y, z = round(position["x"]), round(position["y"]), round(position["z"])
    if grid.herd is None or grid.claimed((x, y, z)):
        return False
    for creature in grid.herd.near(x, z, CHASE_SIGHT):
        kind = kind_of(creature["kind"])
        if kind is not None and kind.hostile and not dead(creature) and abs(creature["y"] - y) <= CHASE_RISE:
            return True
    return False


def alarm(scene: Scene, kind: Kind) -> None:
    """The first hostile to come after Mimo outside its shelter asks for a new choice at once."""
    brain = ensure_brain(scene.state)
    last = brain.get("threat_at")
    if scene.grid.claimed(scene.pet) or (last is not None and (scene.at - last) * scene.scale < ALARM_GAP):
        return
    brain["threat_at"] = scene.at
    mark_trigger(scene.state, "threat", scene.at, urgent=True)
    scene.events.append((scene.at, "threat", f"{scene.state['name']} saw a {kind.name.replace('_', ' ')} coming."))


def chase(creature: dict, kind: Kind, scene: Scene) -> None:
    """Up to CHASE_STEPS steps, each to the neighbour nearest Mimo, stopping in reach of it or when
    no step gets closer; with none, it waits (and keeps its stance when it is in reach)."""
    state = creature["state"]
    state["active_at"] = scene.at
    if not state.get("chasing"):
        state["chasing"] = True
        alarm(scene, kind)
    target = scene.pet
    cell, cells = where(creature, scene.at), []
    for _ in range(CHASE_STEPS):
        if can_hit(scene.grid, cell, target, kind.reach):
            break
        options = [step for step in steps(scene.grid, cell, kind.water, kind.height) if step not in cells]
        best = min(options, key=lambda step: (math.dist(step, target), step), default=None)
        if best is None or math.dist(best, target) >= math.dist(cell, target):
            break
        cells.append(best)
        cell = best
    if cells:
        creature["next_at"] = move(creature, cells, scene.at, kind.speed / scene.pace, "chasing")
        return
    creature["heading"] = heading(cell, target, creature["heading"])
    if can_hit(scene.grid, cell, target, kind.reach):
        state["pose"] = "attacking"
        creature["next_at"] = max(scene.at, state.get("struck_at", scene.at) + kind.cooldown / scene.pace)
        return
    pause(creature, scene, "idle", WAIT, PAUSE)


register_action(CreatureAction("chase", 6, chases, chase))


# prowl -----------------------------------------------------------------------------------------

def prowl(creature: dict, kind: Kind, scene: Scene) -> None:
    creature["state"]["chasing"] = False
    if (scene.at - creature["state"].get("active_at", creature["spawned_at"])) * scene.scale > LOITER:
        vanish(creature, scene)
    elif scene.roll(creature, WANDER) < WANDER_CHANCE:
        wander(creature, kind, scene)
    else:
        pause(creature, scene, "idle", IDLE_SECONDS, PAUSE)


register_action(CreatureAction("prowl", 25, lambda creature, kind, scene: kind.hostile, prowl))
```

- [ ] **Step 6: A hit hostile turns on Mimo, and a kill of one is a fight**

In `backend/survival/creatures/combat.py`, replace:

```python
        run_away(creature, kind, scene, source)
    scene.herd.save(creature)
```

with:

```python
        run_away(creature, kind, scene, source)
    elif kind is not None and kind.hostile:
        state["chasing"] = True  # L2: a hostile that is hit turns on Mimo
    scene.herd.save(creature)
```

and replace:

```python
        return None
    for item, count in found.items():
```

with:

```python
        return None
    return spoils(state, creature, found, at)


def spoils(state: dict, creature: dict, found: dict[str, int], at: float) -> tuple[str, str]:
    """A kill's drops go into Mimo's arms (the engine settles them after the step) and its event
    comes back. A hostile creature (L2) is fought off: a "fight" event that is no hunt. Any other
    kill is a hunt and sets `state["hunted_at"]`. The event is the step's return value, which the
    engine logs."""
    for item, count in found.items():
```

and replace:

```python
        add_item(state["inventory"], item, count)
    state["last_thought"] = f"Got the {label(creature['kind'])}!"
```

with:

```python
        add_item(state["inventory"], item, count)
    kind = kind_of(creature["kind"])
    if kind is not None and kind.hostile:
        state["last_thought"] = f"That {label(creature['kind'])} won't bother me again."
        return "fight", f"{state['name']} fought off a {label(creature['kind'])}."
    state["last_thought"] = f"Got the {label(creature['kind'])}!"
```

- [ ] **Step 7: Heal 1 a game minute, and keep the new events routine**

In `backend/survival/vitals.py`, replace:

```python
HEAL_RATE = 1 / 20
```

with:

```python
HEAL_RATE = 1 / 60  # L2: 1 health a game minute while fed and warm
```

In `backend/survival/world.py`, replace:

```python
                            "hunt"})
```

with:

```python
                            "hunt", "hurt", "fight", "threat"})
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_hostiles.py"`
Expected: `Ran 16 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 711 tests` … `OK` (16 new). The headless runs heal more slowly now; nothing hurts Mimo yet but a fall, the cold and hunger.

- [ ] **Step 9: Commit**

```bash
git add backend/survival/creatures/kinds.py backend/survival/creatures/acts.py backend/survival/creatures/moves.py backend/survival/creatures/simulate.py backend/survival/creatures/harm.py backend/survival/creatures/hostiles.py backend/survival/creatures/combat.py backend/survival/vitals.py backend/survival/world.py backend/tests/test_survival_hostiles.py backend/tests/test_survival_creatures.py backend/tests/test_survival_creature_acts.py backend/tests/test_survival_vitals.py
git commit -m "feat: gloomlings and skitters that chase, strike, burn by day and fade, and what their blows do" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The bow and arrows

**Files:**
- Create: `backend/survival/creatures/archery.py`
- Modify: `backend/services/crafting.py` (bow, arrows), `backend/survival/nature.py` (flint from gravel), `backend/survival/carrying.py` (a bow and arrows are worth carrying), `backend/survival/actions.py` and `backend/survival/snapshot.py` (a shot's `hit` is recorded and shown), `backend/survival/steps.py` (its docstring), `backend/survival/creatures/combat.py` (it imports archery last, so the shoot step registers with the attack step)
- Test: `backend/tests/test_survival_archery.py`

**Interfaces:**
- Consumes: `combat.target_of`, `combat.strike`, `combat.spoils`, `combat.LUNGE`, `moves.where`, `moves.roll`, `steps.register_step`, `StepKind(takes_events=True)`, `crafting.take_items`.
- Produces:
  - Recipes at a crafting table: `bow` (3 sticks, 3 string) and `arrow` (1 flint, 1 stick, 1 feather make 4). `nature.CHANCE_DROPS["gravel"] = (("flint", 1 / 8, 38),)`. `carrying.VALUABLE` gains `bow` and `arrow`.
  - The step `{"kind": "shoot", "creature": id, "target": [x, y, z]}` (`backend.survival.creatures.archery`): `SHOOT_RANGE = 16`, `SHOOT_SECONDS = 1.0`, `ARROW_DAMAGE = 5`, `hit_chance(distance)` (1 within 4 blocks, falling in a line to 0.5 at 16). `start_shoot` fails `missing_item` without a bow or an arrow and `out_of_reach` past 16 blocks, and rolls the hit when it starts (`step["hit"]`). `finish_shoot` spends one arrow, and on a hit strikes the creature for 5 through `combat.strike` (within 16 plus a lunge) and returns `combat.spoils` on a kill. Status `shooting`, working.
  - `actions.RECORDED_FIELDS` and `snapshot.ACTION_FIELDS` gain `hit`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_archery.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.services.crafting import craft
from backend.survival import nature
from backend.survival.actions import ActionContext, advance_actions, ensure_actions, record
from backend.survival.carrying import valuable
from backend.survival.creatures import hostiles  # noqa: F401  (registers the gloomling and the skitter)
from backend.survival.creatures.archery import SHOOT_RANGE, hit_chance
from backend.survival.creatures.combat import drops_of
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.table import Herd, create_creature_tables, dead
from backend.survival.grid import Grid
from backend.survival.snapshot import action_view
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def meadow(blocks=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(inventory=None):
    state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
             "inventory": {"bow": 1, "arrow": 4} if inventory is None else inventory, "vitals": dict(START_VITALS),
             "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    ensure_actions(state)
    return state


def creature(grid, kind="gloomling", cell=(10, 1, 0), health=None):
    return grid.herd.add(kind, cell, KINDS[kind].health if health is None else health, 0.0, 0.0,
                         {"home": list(cell), "turn": 0, "pose": "idle"})


def shoot(target):
    return {"kind": "shoot", "creature": target["id"]}


class BowTests(unittest.TestCase):
    def test_a_bow_and_arrows_are_made_at_a_crafting_table_and_are_worth_carrying(self):
        self.assertEqual(craft({"sticks": 3, "string": 3}, "bow", {"crafting_table"}), {"bow": 1})
        self.assertEqual(craft({"flint": 1, "sticks": 1, "feather": 1}, "arrow", {"crafting_table"}), {"arrow": 4})
        with self.assertRaisesRegex(ValueError, "crafting_table"):
            craft({"sticks": 3, "string": 3}, "bow", set())
        self.assertTrue(valuable("bow") and valuable("arrow"))

    def test_one_mined_gravel_in_eight_gives_flint(self):
        found = sum("flint" in nature.chance_drops("5", (x, 1, z), "gravel") for x in range(20) for z in range(20))
        self.assertTrue(30 <= found <= 70, found)
        grid, state = meadow({(1, 1, 0): "gravel"}), pet({})
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            step = start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 0.0)
            finish_step(step, state, grid, step["ends_at"])
        self.assertEqual(state["inventory"], {"gravel": 1, "flint": 1})

    def test_the_chance_of_a_hit_falls_with_distance(self):
        self.assertEqual([hit_chance(distance) for distance in (2.0, 4.0, 10.0, 16.0)], [1.0, 1.0, 0.75, 0.5])


class ShootStepTests(unittest.TestCase):
    def test_it_needs_a_bow_an_arrow_and_the_creature_in_range(self):
        grid = meadow()
        gloom = creature(grid)
        step = start_step(shoot(gloom), pet(), grid, 10.0)
        self.assertEqual({key: step[key] for key in ("ends_at", "target", "creature", "hit")},
                         {"ends_at": 11.0, "target": {"x": 10, "y": 1, "z": 0}, "creature": gloom["id"], "hit": True})
        self.assertEqual(start_step(shoot(gloom), pet(), grid, 10.0, scale=10.0)["ends_at"], 10.1)
        for inventory, words in (({"arrow": 4}, "no bow"), ({"bow": 1}, "no arrows")):
            with self.assertRaisesRegex(StepFailed, words) as failed:
                start_step(shoot(gloom), pet(inventory), grid, 10.0)
            self.assertEqual(failed.exception.code, "missing_item")
        far = creature(grid, cell=(int(SHOOT_RANGE) + 2, 1, 0))
        with self.assertRaisesRegex(StepFailed, "out of range"):
            start_step(shoot(far), pet(), grid, 10.0)

    def test_a_hit_spends_the_arrow_hurts_the_creature_and_turns_a_hostile_on_mimo(self):
        grid, state = meadow(), pet()
        gloom = creature(grid, cell=(3, 1, 0))
        step = start_step(shoot(gloom), state, grid, 10.0)
        self.assertIsNone(finish_step(step, state, grid, 11.0))
        hurt = grid.herd.get(gloom["id"])
        self.assertEqual((hurt["health"], hurt["state"]["hurt_at"], hurt["state"]["chasing"]), (15.0, 11.0, True))
        self.assertEqual(state["inventory"], {"bow": 1, "arrow": 3})

    def test_a_miss_or_a_creature_gone_spends_the_arrow_and_nothing_else(self):
        grid, state = meadow(), pet()
        gloom = creature(grid, cell=(15, 1, 0))
        with patch("backend.survival.creatures.archery.roll", lambda *args: 0.99):
            step = start_step(shoot(gloom), state, grid, 10.0)
        self.assertFalse(step["hit"])
        self.assertIsNone(finish_step(step, state, grid, 11.0))
        self.assertEqual(grid.herd.get(gloom["id"])["health"], 20.0)
        gone = start_step(shoot(gloom), state, grid, 12.0)
        grid.herd.remove(gloom["id"])
        self.assertIsNone(finish_step(gone, state, grid, 13.0))
        self.assertEqual(state["inventory"], {"bow": 1, "arrow": 2})

    def test_a_kill_brings_its_drops_a_hunt_for_an_animal_a_fight_for_a_hostile(self):
        grid, state = meadow(), pet()
        rabbit, skitter = creature(grid, "rabbit", (2, 1, 0)), creature(grid, "skitter", (0, 1, 3), health=4.0)
        self.assertEqual(finish_step(start_step(shoot(rabbit), state, grid, 10.0), state, grid, 11.0),
                         ("hunt", "Pip hunted a rabbit."))
        self.assertEqual(finish_step(start_step(shoot(skitter), state, grid, 12.0), state, grid, 13.0),
                         ("fight", "Pip fought off a skitter."))
        self.assertTrue(dead(grid.herd.get(skitter["id"])))
        expected = {"bow": 1, "arrow": 2}
        for body, kind in ((rabbit, "rabbit"), (skitter, "skitter")):
            for item, count in drops_of("5", body, KINDS[kind]).items():
                expected[item] = expected.get(item, 0) + count
        self.assertEqual(state["inventory"], expected)

    def test_in_the_tick_the_viewer_sees_whether_the_arrow_flies_true(self):
        grid, state = meadow(), pet()
        gloom = creature(grid, cell=(5, 1, 0))
        state["queue"] = [shoot(gloom)]
        context = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[])
        advance_actions(state, context, 0.5)
        self.assertEqual(action_view(state["action"])["hit"], True)
        self.assertNotIn("creature", action_view(state["action"]))
        advance_actions(state, context, 1.5)
        self.assertEqual({key: state["recent_actions"][-1][key] for key in ("kind", "result", "hit")},
                         {"kind": "shoot", "result": "done", "hit": True})
        record(state, {"kind": "walk", "started_at": 2.0}, 2.5, "done")
        self.assertNotIn("hit", state["recent_actions"][-1])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_archery.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.archery'`.

- [ ] **Step 3: Add the recipes, flint, and what is worth carrying**

In `backend/services/crafting.py`, replace:

```python
    "iron_sword": {"ingredients": {"iron_ingot": 2, "sticks": 1}, "output": {"iron_sword": 1}, "station": "crafting_table"},
```

with:

```python
    "iron_sword": {"ingredients": {"iron_ingot": 2, "sticks": 1}, "output": {"iron_sword": 1}, "station": "crafting_table"},
    "bow": {"ingredients": {"sticks": 3, "string": 3}, "output": {"bow": 1}, "station": "crafting_table"},
    "arrow": {"ingredients": {"flint": 1, "sticks": 1, "feather": 1}, "output": {"arrow": 4}, "station": "crafting_table"},
```

In `backend/survival/nature.py`, replace:

```python
                "leaves": (("sapling", 1 / 12, 32), ("apple", 1 / 20, 33))}
```

with:

```python
                "leaves": (("sapling", 1 / 12, 32), ("apple", 1 / 20, 33)),
                "gravel": (("flint", 1 / 8, 38),)}  # L2: flint for arrows
```

In `backend/survival/carrying.py`, replace:

```python
VALUABLE = ("seeds", "sapling", "wheat", "coal")
```

with:

```python
VALUABLE = ("seeds", "sapling", "wheat", "coal", "bow", "arrow")  # L2: gear
```

- [ ] **Step 4: Write the shoot step**

Create `backend/survival/creatures/archery.py`:

```python
"""The bow: the shoot step (spec L2, "Bow").

A bow takes 3 sticks and 3 string (skitters drop string) at a crafting table; 1 flint, 1 stick
and 1 feather make 4 arrows there (backend.services.crafting). Flint comes from gravel: one mined
gravel in 8 drops one (backend.survival.nature).

shoot(creature): Mimo draws and looses an arrow at a creature up to 16 blocks away. It takes 1.0 s
and spends one arrow, hit or miss. Whether it hits is rolled when the step starts (from the world
seed, the creature and the time), so the viewer can show the arrow fly true or wide
(`hit` in the running step): a sure hit within 4 blocks, falling to one in two at 16. A hit
does 5 damage through the same blow a sword deals (creatures.combat.strike): a hit animal runs, a
hit hostile turns on Mimo, and a kill's drops go into Mimo's arms with a "hunt" or "fight" event
(creatures.combat.spoils). A creature that is gone or dead when the arrow lands, or that ran more
than a block past the bow's range, is missed, which is no failure. The step does not start
without a bow or an arrow ("missing_item") or with the creature out of range ("out_of_reach").
Like the attack step, it takes the tick's events (`takes_events`) for its Scene; the kill's own
event is its return value.
"""

from __future__ import annotations

import math

from backend.services.crafting import take_items
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.combat import LUNGE, spoils, strike, target_of
from backend.survival.creatures.moves import roll, where
from backend.survival.grid import Grid
from backend.survival.steps import StepFailed, StepKind, as_cell, as_point, register_step, seed_of

SHOOT_RANGE = 16.0
SHOOT_SECONDS = 1.0
ARROW_DAMAGE = 5.0
SURE_WITHIN = 4.0  # blocks within which an arrow always hits
WORST_CHANCE = 0.5  # the chance of a hit at the bow's full range
AIM = 95  # roll channel


def hit_chance(distance: float) -> float:
    """1 within SURE_WITHIN blocks, falling in a straight line to WORST_CHANCE at SHOOT_RANGE."""
    if distance <= SURE_WITHIN:
        return 1.0
    share = (distance - SURE_WITHIN) / (SHOOT_RANGE - SURE_WITHIN)
    return max(WORST_CHANCE, 1.0 - (1.0 - WORST_CHANCE) * share)


def start_shoot(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    _, creature = target_of(spec, grid)
    if state["inventory"].get("bow", 0) < 1:
        raise StepFailed("no bow to shoot with", "missing_item")
    if state["inventory"].get("arrow", 0) < 1:
        raise StepFailed("no arrows", "missing_item")
    there = where(creature, at)
    distance = math.dist(as_cell(state["position"]), there)
    if distance > SHOOT_RANGE:
        raise StepFailed("out of range", "out_of_reach")
    hit = roll(seed_of(state), creature["id"], int(at * 10), AIM) < hit_chance(distance)
    return {"kind": "shoot", "started_at": at, "ends_at": round(at + SHOOT_SECONDS / scale, 3),
            "target": as_point(there), "creature": creature["id"], "hit": hit, "pace": scale}


def finish_shoot(step: dict, state: dict, grid: Grid, at: float, events: list) -> tuple[str, str] | None:
    state["inventory"] = take_items(state["inventory"], {"arrow": 1})
    if not step.get("hit"):
        return None
    try:
        herd, creature = target_of(step, grid)
    except StepFailed:
        return None  # it died or went while the arrow flew
    if math.dist(as_cell(state["position"]), where(creature, at)) > SHOOT_RANGE + LUNGE:
        return None
    scene = Scene(grid, herd, seed_of(state), state, at, step.get("pace", 1.0), events=events)
    found = strike(scene, creature, ARROW_DAMAGE, as_cell(state["position"]))
    return None if found is None else spoils(state, creature, found, at)


register_step(StepKind("shoot", start_shoot, finish_shoot, "shooting", working=True, cell_field="target",
                       takes_events=True))
```

In `backend/survival/creatures/combat.py`, replace:

```python
                       takes_events=True))
```

with:

```python
                       takes_events=True))

# L2's shoot step builds on the blow above and registers itself.
from backend.survival.creatures import archery  # noqa: E402,F401
```

In `backend/survival/steps.py`, replace:

```python
housework (store, take, drop) in backend.survival.housework and L1's attack in
backend.survival.creatures.combat. Mining leaves or tall grass may drop
more (nature.CHANCE_DROPS): saplings, apples, seeds. Sleep on a bed is sleep in a bed.
```

with:

```python
housework (store, take, drop) in backend.survival.housework, L1's attack in
backend.survival.creatures.combat and L2's shoot in backend.survival.creatures.archery. Mining
leaves, tall grass or gravel may drop more (nature.CHANCE_DROPS): saplings, apples, seeds, flint.
Sleep on a bed is sleep in a bed.
```

In `backend/survival/actions.py`, replace:

```python
RECORDED_FIELDS = ("kind", "started_at", "target", "block", "item", "recipe", "purpose", "path", "amount")
```

with:

```python
RECORDED_FIELDS = ("kind", "started_at", "target", "block", "item", "recipe", "purpose", "path", "amount", "hit")
```

In `backend/survival/snapshot.py`, replace:

```python
ACTION_FIELDS = ("kind", "started_at", "ends_at", "path", "target", "block", "item", "recipe", "blocks")
```

with:

```python
ACTION_FIELDS = ("kind", "started_at", "ends_at", "path", "target", "block", "item", "recipe", "blocks", "hit")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_archery.py"`
Expected: `Ran 8 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 719 tests` … `OK` (8 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/creatures/archery.py backend/survival/creatures/combat.py backend/services/crafting.py backend/survival/nature.py backend/survival/carrying.py backend/survival/steps.py backend/survival/actions.py backend/survival/snapshot.py backend/tests/test_survival_archery.py
git commit -m "feat: a bow and arrows, flint from gravel, and the shoot step" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Leather armor and making gear

**Files:**
- Create: `backend/survival/creatures/gear.py`
- Modify: `backend/services/crafting.py` (leather from hides, the cap and the tunic), `backend/survival/carrying.py` (armor is worth carrying), `backend/survival/storage.py` (what gear takes stays on hand), `backend/survival/purposes.py` (make_gear's band), `backend/survival/brain.py` (import it)
- Modify tests: `backend/tests/test_survival_meat.py` (leather, feathers and hides are kept on hand up to what gear takes)
- Test: `backend/tests/test_survival_gear.py`

**Interfaces:**
- Consumes: `toolmaking.make`, `toolmaking.place_station`, `toolmaking.station_spots`, `toolmaking.Short`, `carrying.crafts_fit`, `steps.WORKSTATIONS`, `steps.STATION_REACH`, `purposes.Purpose`, `purposes.register`, `harm.ARMOR` (Task 3).
- Produces:
  - Recipes: `leather` (4 rabbit_hide, no station), `leather_cap` (2 leather) and `leather_tunic` (3 leather) at a crafting table. `carrying.VALUABLE` gains both pieces. `storage.KEEP` keeps 5 leather, 4 feathers, 8 rabbit hides, 3 string and 4 flint on hand (the rest goes in the chest) and puts gloom dust away.
  - `backend.survival.creatures.gear`: `ARMOR_PIECES`, `ARROWS_WANTED = 8`, `gear_orders(inventory) -> list[tuple[str, ...]]`, `gear_steps(s, items) -> list[dict] | None`, `gear_choice(s)`, and the purpose `make_gear` (valid by day while something can be made; score 55 + caution / 10, 10 more when a creature hurt Mimo in the last game day; one batch per choice).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_gear.py`:

```python
import sqlite3
import unittest

from backend.services.crafting import craft
from backend.survival import storage
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.carrying import valuable
from backend.survival.creatures.gear import gear_orders
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_storage import Home

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
GEAR = PURPOSES["make_gear"]
ARMOR = {"leather_cap": 1, "leather_tunic": 1}


def meadow(blocks=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    return grid


def situation(inventory, grid=None, clock=DAY, **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {"caution": 50}, "last_tick_at": 0.0, "brain": new_brain(0.0)}
    state.update(changes)
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state, grid or meadow(), clock, 100.0, db)


def plan(s):
    return GEAR.plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=s.db))


def crafts(steps):
    return [step["recipe"] for step in steps if step["kind"] == "craft"]


class GearTests(unittest.TestCase):
    def test_leather_armor_is_made_at_a_crafting_table_and_is_worth_carrying(self):
        self.assertEqual(craft({"rabbit_hide": 4}, "leather", set()), {"leather": 1})
        self.assertEqual(craft({"leather": 2}, "leather_cap", {"crafting_table"}), {"leather_cap": 1})
        self.assertEqual(craft({"leather": 3}, "leather_tunic", {"crafting_table"}), {"leather_tunic": 1})
        self.assertTrue(valuable("leather_cap") and valuable("leather_tunic"))

    def test_armor_first_then_a_bow_with_arrows_then_arrows_up_to_eight(self):
        self.assertEqual(gear_orders({}), [("leather_tunic", "leather_cap"), ("leather_tunic",), ("leather_cap",),
                                           ("bow", "arrow"), ("bow",)])
        self.assertEqual(gear_orders({**ARMOR, "bow": 1, "arrow": 7}), [("arrow",)])
        self.assertEqual(gear_orders({**ARMOR, "bow": 1, "arrow": 8}), [])

    def test_both_pieces_of_armor_from_five_leather_at_a_table_it_places_and_takes_back(self):
        s = situation({"leather": 5, "planks": 4})
        self.assertTrue(GEAR.valid(s))
        self.assertEqual(GEAR.facts(s), "can make a leather tunic and a leather cap now; carrying 0 arrows")
        steps = plan(s)
        self.assertEqual(crafts(steps), ["crafting_table", "leather_tunic", "leather_cap"])
        placed = next(step for step in steps if step["kind"] == "place")
        self.assertEqual((placed["block"], steps[-1]), ("crafting_table", {"kind": "mine", "target": placed["target"],
                                                                           "keep": True}))
        self.assertEqual(crafts(plan(situation({"leather": 3, "planks": 4}))), ["crafting_table", "leather_tunic"])
        hides = situation({"leather": 3, "rabbit_hide": 8, "planks": 4})
        self.assertEqual(crafts(plan(hides)), ["crafting_table", "leather_tunic", "leather", "leather", "leather_cap"])

    def test_a_bow_and_its_first_arrows_then_more_arrows_at_a_table_already_there(self):
        table = meadow({(2, 1, 0): "crafting_table"})
        both = situation({**ARMOR, "sticks": 4, "string": 3, "flint": 1, "feather": 1}, table)
        self.assertEqual(plan(both), [{"kind": "craft", "recipe": "bow"}, {"kind": "craft", "recipe": "arrow"}])
        self.assertEqual(GEAR.facts(both), "can make a bow and 4 arrows now; carrying 0 arrows")
        more = situation({**ARMOR, "bow": 1, "arrow": 4, "sticks": 1, "flint": 1, "feather": 1}, table)
        self.assertEqual(plan(more), [{"kind": "craft", "recipe": "arrow"}])

    def test_nothing_at_night_or_without_the_materials(self):
        self.assertFalse(GEAR.valid(situation({"leather": 5, "planks": 4}, clock=NIGHT)))
        self.assertFalse(GEAR.valid(situation({"leather": 1, "planks": 4})))
        self.assertFalse(GEAR.valid(situation({**ARMOR, "sticks": 4, "string": 2, "planks": 4})))

    def test_it_matters_more_after_a_creature_hurt_mimo(self):
        self.assertEqual(GEAR.score(situation({"leather": 5})), 60.0)
        self.assertEqual(GEAR.score(situation({"leather": 5}, hurt_at=50.0)), 70.0)
        self.assertEqual(GEAR.score(situation({"leather": 5}, hurt_at=100.0 - 3600.0)), 60.0)

    def test_what_gear_takes_is_kept_on_hand_and_the_rest_put_away(self):
        home = Home({"leather": 9, "string": 5, "flint": 4, "feather": 4, "rabbit_hide": 8, "gloom_dust": 2}, chest={})
        self.assertEqual(storage.to_store(home.situation(), home.chest),
                         [("leather", 4), ("gloom_dust", 2), ("string", 2)])


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_meat.py`, replace:

```python
        home = Home({"leather": 2, "wool": 3, "feather": 4, "rabbit_hide": 1, "raw_beef": 1}, chest={})
        self.assertEqual(storage.to_store(home.situation(), home.chest),
                         [("feather", 4), ("wool", 3), ("leather", 2), ("rabbit_hide", 1)])
```

with:

```python
        home = Home({"leather": 7, "wool": 3, "feather": 6, "rabbit_hide": 9, "raw_beef": 1}, chest={})
        self.assertEqual(storage.to_store(home.situation(), home.chest),  # L2 keeps 5 leather, 4 feathers, 8 hides
                         [("wool", 3), ("feather", 2), ("leather", 2), ("rabbit_hide", 1)])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_gear.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.gear'`.

- [ ] **Step 3: Add the recipes and keep the materials on hand**

In `backend/services/crafting.py`, replace:

```python
    "arrow": {"ingredients": {"flint": 1, "sticks": 1, "feather": 1}, "output": {"arrow": 4}, "station": "crafting_table"},
```

with:

```python
    "arrow": {"ingredients": {"flint": 1, "sticks": 1, "feather": 1}, "output": {"arrow": 4}, "station": "crafting_table"},
    "leather": {"ingredients": {"rabbit_hide": 4}, "output": {"leather": 1}},
    "leather_cap": {"ingredients": {"leather": 2}, "output": {"leather_cap": 1}, "station": "crafting_table"},
    "leather_tunic": {"ingredients": {"leather": 3}, "output": {"leather_tunic": 1}, "station": "crafting_table"},
```

In `backend/survival/carrying.py`, replace:

```python
"bow", "arrow")  # L2: gear
```

with:

```python
"bow", "arrow", "leather_cap", "leather_tunic")  # L2: gear
```

In `backend/survival/storage.py`, replace:

```python
        # L1: what animals drop besides meat is put away (L2 makes armor, bows and arrows from it).
        "leather": 0, "wool": 0, "feather": 0, "rabbit_hide": 0}
```

with:

```python
        # L1: what animals drop besides meat is put away, but for what L2's armor, bow and arrows
        # take (backend.survival.creatures.gear); gloom dust waits for L3.
        "leather": 5, "wool": 0, "feather": 4, "rabbit_hide": 8, "string": 3, "flint": 4, "gloom_dust": 0}
```

- [ ] **Step 4: Write the make_gear purpose**

Create `backend/survival/creatures/gear.py`:

```python
"""make_gear: armor, a bow and arrows (spec L2, "Armor" and "Bow").

Gear is made from what animals and hostiles leave behind, at a crafting table Mimo places from
its arms and mines back afterwards, as craft_tools does: a leather cap (2 leather) and a leather
tunic (3 leather), worn by carrying them (backend.survival.creatures.harm: a blow costs 8 % and
12 % less), a bow (3 sticks and 3 string) and arrows (1 flint, 1 stick and 1 feather make 4).
Leather that runs short is made from rabbit hides, 4 to 1, on the way. The order: the missing
armor first (both pieces in one batch when the leather stretches that far), then the bow with a
first bundle of arrows, or the bow alone, then another bundle of arrows while Mimo carries a bow
and fewer than ARROWS_WANTED. One batch per choice, and none while something it makes would not
fit in Mimo's arms (carrying.crafts_fit) or where no table can stand (inside its shelter). Day
work in the work band: 55 plus a tenth of caution, 10 more when a creature hurt Mimo in the last
game day.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival.carrying import crafts_fit
from backend.survival.clock import DAY_SECONDS
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import STATION_REACH, WORKSTATIONS
from backend.survival.toolmaking import Short, make, place_station, station_spots

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

ARMOR_PIECES = ("leather_tunic", "leather_cap")
ARROWS_WANTED = 8
WORDS = {"leather_tunic": "a leather tunic", "leather_cap": "a leather cap", "bow": "a bow", "arrow": "4 arrows"}


def gear_orders(inventory: dict) -> list[tuple[str, ...]]:
    """What make_gear may make, first choice first (see the module docstring)."""
    orders: list[tuple[str, ...]] = []
    armor = tuple(piece for piece in ARMOR_PIECES if inventory.get(piece, 0) < 1)
    if armor:
        orders.append(armor)
        if len(armor) > 1:
            orders += [(piece,) for piece in armor]
    if inventory.get("bow", 0) < 1:
        orders += [("bow", "arrow"), ("bow",)]
    elif inventory.get("arrow", 0) < ARROWS_WANTED:
        orders.append(("arrow",))
    return orders


def gear_steps(s: Situation, items: tuple[str, ...]) -> list[dict] | None:
    """The steps that make one of each of `items` (arrows come 4 at a time), with a crafting table
    placed and mined back when none stands within reach; None when they cannot all be made now."""
    inventory = dict(s.inventory)
    x, _, z = s.here
    steps: list[dict] = []
    placed = []
    try:
        if "crafting_table" not in s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS):
            make(inventory, "crafting_table", 1, steps)
            cell = place_station(station_spots(s), "crafting_table", steps)
            if cell is None:
                raise Short("crafting_table")
            inventory["crafting_table"] -= 1
            placed.append(cell)
        for item in items:
            make(inventory, item, inventory.get(item, 0) + 1, steps)
    except Short:
        return None
    steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
    return steps if crafts_fit(s.inventory, steps) else None


def gear_choice(s: Situation) -> tuple[tuple[str, ...], list[dict]] | None:
    """The first of gear_orders that can be made now, with its steps; or None."""
    def look() -> tuple[tuple[str, ...], list[dict]] | None:
        for items in gear_orders(s.inventory):
            steps = gear_steps(s, items)
            if steps is not None:
                return items, steps
        return None
    return s.sensed("gear_choice", look)


def hurt_lately(s: Situation) -> bool:
    hurt_at = s.state.get("hurt_at")
    return hurt_at is not None and (s.at - hurt_at) * s.scale < DAY_SECONDS


def gear_facts(s: Situation) -> str:
    items, _ = gear_choice(s)
    return f"can make {' and '.join(WORDS[item] for item in items)} now; carrying {s.count('arrow')} arrows"


def plan_gear(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] > 0:
        return []
    choice = gear_choice(s)
    return [] if choice is None else list(choice[1])


register(Purpose(
    "make_gear", "make gear",
    "Make armor, a bow or arrows from leather, string, flint and feathers with a portable crafting table.",
    valid=lambda s: not s.night and gear_choice(s) is not None,
    facts=gear_facts,
    score=lambda s: 55.0 + s.trait("caution") / 10 + (10.0 if hurt_lately(s) else 0.0),
    plan=plan_gear,
    thoughts=("A little armor would help at night.", "With a bow I could keep them at a distance.")))
```

In `backend/survival/purposes.py`, replace:

```python
L1's backend.survival.creatures.hunting registers hunt. backend.survival.brain imports them all.
```

with:

```python
L1's backend.survival.creatures.hunting registers hunt, and L2's backend.survival.creatures.gear
make_gear. backend.survival.brain imports them all.
```

and replace:

```python
  with hunger, 5 more or less with bravery, minus late.
"""
```

with:

```python
  with hunger, 5 more or less with bravery, minus late.
- L2's make_gear sits in the work band: 55-75, 55 plus a tenth of caution and 10 more when a
  creature hurt Mimo in the last game day.
"""
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival.creatures import hunting  # noqa: F401  (L1's hunt purpose)
```

with:

```python
from backend.survival.creatures import gear, hunting  # noqa: F401  (L1's hunt; L2's make_gear)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_gear.py"`
Expected: `Ran 7 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 726 tests` … `OK` (7 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 2 tests` … `OK`: the purpose budget holds with make_gear among the choices.

- [ ] **Step 6: Commit**

```bash
git add backend/survival/creatures/gear.py backend/services/crafting.py backend/survival/carrying.py backend/survival/storage.py backend/survival/purposes.py backend/survival/brain.py backend/tests/test_survival_gear.py backend/tests/test_survival_meat.py
git commit -m "feat: leather armor, and a make_gear purpose for armor, a bow and arrows" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The fight and flee reflexes

**Files:**
- Create: `backend/survival/creatures/defense.py`
- Modify: `backend/survival/reflexes.py` (`quiet`: one event an encounter), `backend/survival/brain.py` (import them)
- Modify tests: `backend/tests/test_survival_reflexes.py` (flee and fight take their places)
- Test: `backend/tests/test_survival_defense.py`

**Interfaces:**
- Consumes: `reflexes.Reflex`, `reflexes.register`, `reflexes.reflex_hook`, `purposes.home_of`, `purposes.walk_to`, `purposes.underground`, `combat.weapon`, `combat.ATTACK_REACH`, `archery.SHOOT_RANGE`, `harm.ARMOR`, `harm.sheltered`, `hostiles.CHASE_SIGHT`, `hostiles.CHASE_RISE`, `Situation.sensed`.
- Produces:
  - `Reflex` gains `quiet: float = 0.0`: a takeover within `quiet` seconds of the reflex's last end logs no event.
  - `backend.survival.creatures.defense`: `threats(s) -> list[dict]` (living hostiles within 16 blocks across and 4 up or down, nearest first; none while Mimo is indoors), `indoors(s)`, `armed(s)`, `bow_ready(s)`, `clear_line(grid, start, end)`, `fight_target(s)`, `threats_payload(s) -> {"threats": [...], "defense": {...}}` (used in Task 8), and the reflexes `flee` (30) and `fight` (40) as data. Constants: `FLEE_BELOW = 35`, `FLEE_NEAR = 6`, `FLEE_RUN = 12`, `FIGHT_FROM = 50`, `FIGHT_REACH = 4`, `SHOOT_FROM = 5`, `BOW_SIGHT = 12`, `FIGHT_KEEP = 3`, `QUIET = 30`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_defense.py`:

```python
import math
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.brain import BRAIN, brain_plan
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.creatures.defense import FIGHT_KEEP, QUIET, armed, clear_line, fight_target, threats
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.simulate import simulate
from backend.survival.creatures.table import Herd, create_creature_tables, dead
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.memory import add_structure, create_memory_tables, set_home
from backend.survival.registry import LifeRegistry
from backend.survival.reflexes import by_name, reflex_hook
from backend.survival.situation import Situation
from backend.survival.tick import tick_life
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS
from backend.survival.world import SurvivalWorld, read_state, write_state

NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}
BORN = 1_000_000.0
FLEE, FIGHT = by_name("flee"), by_name("fight")
SWORD = {"stone_sword": 1}


def meadow(blocks=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "status": "idle", "last_thought": "", "last_tick_at": 0.0,
             "born_at": 0.0, "died_at": None, "brain": new_brain(0.0)}
    state["brain"]["pending"] = None
    state.update(changes)
    ensure_actions(state)
    return state


def situation(grid, state, at=100.0):
    return Situation(state, grid, NIGHT, at, grid.herd.db)


def hostile(grid, kind="gloomling", cell=(3, 1, 0), **state):
    return grid.herd.add(kind, cell, KINDS[kind].health, 0.0, 1e9, {"home": list(cell), "turn": 0, "pose": "idle",
                                                                     **state})


def context(grid):
    return ActionContext(grid=grid, clock_at=lambda at: NIGHT, planner=brain_plan, events=[], db=grid.herd.db,
                         interrupt=reflex_hook)


class ThreatTests(unittest.TestCase):
    def test_threats_are_living_hostiles_that_could_come_after_mimo_nearest_first(self):
        grid = meadow()
        far, near = hostile(grid, cell=(10, 1, 0)), hostile(grid, "skitter", (0, 1, 5))
        hostile(grid, cell=(2, 1, 0), pose="dead")
        hostile(grid, cell=(20, 1, 0))
        hostile(grid, cell=(3, -6, 0))  # in the rock far below
        grid.herd.add("cow", (1, 1, 0), 10.0, 0.0, 1e9, {})
        self.assertEqual([creature["id"] for creature in threats(situation(grid, pet()))], [near["id"], far["id"]])

    def test_inside_its_own_shelter_mimo_has_nothing_to_fear(self):
        grid = meadow()
        hostile(grid)
        add_structure(grid.herd.db, "shelter", "Pip's Hut", (0, 1, 0), 0.0, {},
                      [((0, 1, 0), "room", "air"), ((0, 1, -1), "door", "door")])
        grid.claims.update({(0, 1, 0), (0, 1, -1)})
        self.assertEqual(threats(situation(grid, pet())), [])
        in_the_doorway = pet(position={"x": 0.0, "y": 1.0, "z": -1.0})
        self.assertEqual(len(threats(situation(grid, in_the_doorway))), 1)

    def test_a_weapon_is_a_sword_or_a_bow_with_arrows(self):
        self.assertFalse(armed(situation(meadow(), pet())))
        self.assertTrue(armed(situation(meadow(), pet(inventory={"wooden_sword": 1}))))
        self.assertFalse(armed(situation(meadow(), pet(inventory={"bow": 1}))))
        self.assertTrue(armed(situation(meadow(), pet(inventory={"bow": 1, "arrow": 1}))))

    def test_a_wall_blocks_the_line_of_sight(self):
        grid = meadow({(3, 1, 0): "cobblestone"})
        self.assertFalse(clear_line(grid, (0, 1, 0), (6, 1, 0)))
        self.assertTrue(clear_line(grid, (0, 1, 1), (6, 1, 1)))


class FleeTests(unittest.TestCase):
    def test_an_unarmed_or_badly_hurt_pet_flees_from_a_threat(self):
        grid = meadow()
        hostile(grid, cell=(5, 1, 0))
        self.assertTrue(FLEE.trigger(situation(grid, pet())))
        self.assertFalse(FLEE.trigger(situation(grid, pet(inventory=SWORD))))
        far = meadow()
        hostile(far, cell=(10, 1, 0))
        self.assertFalse(FLEE.trigger(situation(far, pet())))
        hurt = {**START_VITALS, "health": 30.0}
        self.assertTrue(FLEE.trigger(situation(far, pet(inventory=SWORD, vitals=hurt))))
        self.assertFalse(FLEE.trigger(situation(meadow(), pet(vitals=hurt))))  # nothing to run from

    def test_it_runs_home_unless_the_threat_is_nearer_home_and_else_straight_away(self):
        grid = meadow()
        hostile(grid, cell=(5, 1, 0))
        set_home(grid.herd.db, (-10, 1, 0), 0.0)
        self.assertEqual(FLEE.plan(situation(grid, pet()), context(grid)),
                         [{"kind": "walk", "target": [-10, 1, 0], "reach": 0.0}])
        cut_off = meadow()
        hostile(cut_off, cell=(-5, 1, 0))
        set_home(cut_off.herd.db, (-10, 1, 0), 0.0)
        self.assertEqual(FLEE.plan(situation(cut_off, pet()), context(cut_off)),
                         [{"kind": "walk", "target": [12, 1, 0], "reach": 4.0}])


class FightTests(unittest.TestCase):
    def test_armed_and_healthy_it_fights_a_hostile_within_four_blocks_then_flees_when_hurt(self):
        grid = meadow()
        gloom = hostile(grid, cell=(3, 1, 0))
        self.assertEqual(fight_target(situation(grid, pet(inventory=SWORD)))["id"], gloom["id"])
        self.assertIsNone(fight_target(situation(grid, pet())))
        hurt = pet(inventory=SWORD, vitals={**START_VITALS, "health": 40.0})
        self.assertIsNone(fight_target(situation(grid, hurt)))
        hurt["brain"]["reflex_ends"]["fight"] = 100.0 - FIGHT_KEEP  # a fight is on: it goes on down to 35
        self.assertEqual(fight_target(situation(grid, hurt))["id"], gloom["id"])
        hurt["vitals"]["health"] = 30.0
        self.assertIsNone(fight_target(situation(grid, hurt)))
        self.assertTrue(FLEE.trigger(situation(grid, hurt)))

    def test_it_strikes_in_reach_steps_up_to_strike_and_shoots_from_afar(self):
        grid = meadow()
        close = hostile(grid, cell=(2, 1, 0))
        self.assertEqual(FIGHT.plan(situation(grid, pet(inventory=SWORD)), context(grid)),
                         [{"kind": "attack", "creature": close["id"], "target": [2, 1, 0]}])
        step_up = meadow()
        farther = hostile(step_up, cell=(4, 1, 0))
        self.assertEqual(FIGHT.plan(situation(step_up, pet(inventory=SWORD)), context(step_up)),
                         [{"kind": "walk", "target": [4, 1, 0], "reach": 2.0},
                          {"kind": "attack", "creature": farther["id"], "target": [4, 1, 0]}])
        archer = pet(inventory={**SWORD, "bow": 1, "arrow": 3})
        bow = meadow()
        coming = hostile(bow, cell=(9, 1, 0), chasing=True)
        self.assertEqual(FIGHT.plan(situation(bow, archer), context(bow)),
                         [{"kind": "shoot", "creature": coming["id"], "target": [9, 1, 0]}])
        walled = meadow({(5, 1, 0): "cobblestone", (5, 2, 0): "cobblestone"})
        hostile(walled, cell=(9, 1, 0), chasing=True)
        self.assertIsNone(fight_target(situation(walled, archer)))
        idle = meadow()
        hostile(idle, cell=(9, 1, 0))
        self.assertIsNone(fight_target(situation(idle, archer)))  # not after Mimo: left alone

    def test_a_fight_logs_its_event_once_an_encounter(self):
        grid = meadow()
        hostile(grid, cell=(2, 1, 0))
        state = pet(inventory=SWORD)
        ctx = context(grid)
        for at in (100.0, 101.0, 101.0 + QUIET + 1.0):
            self.assertEqual(reflex_hook(state, ctx, at), "fight")
            state["brain"].update(reflex=None)
            state["brain"]["reflex_ends"]["fight"] = at
        self.assertEqual([event[2] for event in ctx.events], ["Pip stood its ground against a creature."] * 2)


class InTheTickTests(unittest.TestCase):
    def night(self, grid, state, until):
        ctx = context(grid)
        at = 0.0
        while at < until:
            at += 0.25
            advance_actions(state, ctx, at)
            simulate(state, ctx, at)
            ctx.searches_left = 2
        return ctx

    def test_an_armed_pet_fights_off_a_gloomling_that_comes_for_it(self):
        grid = meadow()
        gloom = hostile(grid, cell=(6, 1, 0))
        gloom["next_at"] = 0.0
        grid.herd.save(gloom)
        state = pet(inventory={"iron_sword": 1})
        ctx = self.night(grid, state, 20.0)
        self.assertIn(("fight", "Pip fought off a gloomling."), [event[1:] for event in ctx.events])
        body = grid.herd.get(gloom["id"])
        self.assertTrue(body is None or dead(body))  # cleared away once its puff is over
        self.assertGreater(state["vitals"]["health"], 50.0)

    def test_an_unarmed_pet_runs_from_a_gloomling_and_gets_away(self):
        grid = meadow()
        gloom = hostile(grid, cell=(4, 1, 0))
        gloom["next_at"] = 0.0
        grid.herd.save(gloom)
        state = pet()
        ctx = self.night(grid, state, 10.0)
        self.assertIn("Pip ran from a creature.", [event[2] for event in ctx.events])
        chaser = grid.herd.get(gloom["id"])
        self.assertGreater(math.hypot(state["position"]["x"] - chaser["x"], state["position"]["z"] - chaser["z"]), 6.0)
        self.assertGreater(state["vitals"]["health"], 90.0)


class HatchedWorldTests(unittest.TestCase):
    """The whole brain in the real tick, at 1x, a second a tick, on the first night of a new world."""

    def night_with_a_gloomling(self, inventory):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(3), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                state["born_at"] = BORN - 2500.0  # deep in the first night
                state["inventory"].update(inventory)
                write_state(db, state)
                x, y, z = (round(state["position"][axis]) for axis in "xyz")
                Herd(db).add("gloomling", (x + 5, y, z), 20.0, BORN, BORN, {"home": [x + 5, y, z], "turn": 0})
            chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(3), scale=1.0)
            for second in range(1, 61):
                state = tick_life(registry, BORN + second, scale=1.0, mind=BRAIN, action_scale=1.0)
                chooser.poll(registry, BORN + second)
            return state, [event["kind"] for event in world.events(500)]

    def test_an_armed_pet_wakes_and_fights_the_gloomling_off(self):
        state, kinds = self.night_with_a_gloomling({"stone_sword": 1})
        self.assertIsNone(state["died_at"])
        self.assertIn("fight", kinds)
        self.assertGreater(state["vitals"]["health"], 80.0)

    def test_an_unarmed_pet_keeps_away_from_it_all_night(self):
        state, kinds = self.night_with_a_gloomling({})
        self.assertIsNone(state["died_at"])
        self.assertNotIn("hurt", kinds)
        self.assertEqual(kinds.count("reflex"), 1)  # one "ran from a creature" for the whole encounter


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_reflexes.py`, replace:

```python
    def test_m3_reflexes_run_in_priority_order_with_room_for_flee(self):
        self.assertEqual([(reflex.name, reflex.priority) for reflex in REFLEXES][:6],
                         [("surface", 10), ("avoid_drop", 20), ("eat_now", 40), ("warm_up", 50),
                          ("head_home", 60), ("collapse", 70)])
```

with:

```python
    def test_m3_reflexes_run_in_priority_order_with_l2s_flee_and_fight_among_them(self):
        self.assertEqual([(reflex.name, reflex.priority) for reflex in REFLEXES][:8],
                         [("surface", 10), ("avoid_drop", 20), ("flee", 30), ("eat_now", 40), ("fight", 40),
                          ("warm_up", 50), ("head_home", 60), ("collapse", 70)])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_defense.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.defense'`.

- [ ] **Step 3: Let a reflex keep quiet for a while**

In `backend/survival/reflexes.py`, replace:

```python
collapse (70). Priority 30 is left for sub-project 3's flee; creature reflexes register
themselves with `register`. M5: collapse lies down in a bed within 8 blocks when there is one
(and where it stands when the walk there fails), and head_home leaves Mimo be while it builds its
shelter or lights torches at home.
```

with:

```python
collapse (70). L2's flee (30) and fight (40) register themselves from
backend.survival.creatures.defense; a fight goes round after round, so a reflex may stay `quiet`
for a while after it ends and log its event once per encounter. M5: collapse lies down in a bed
within 8 blocks when there is one (and where it stands when the walk there fails), and head_home
leaves Mimo be while it builds its shelter or lights torches at home.
```

and replace:

```python
    ends_purpose: bool = False
```

with:

```python
    ends_purpose: bool = False
    # L2: real seconds after it last ended during which a new takeover logs no event.
    quiet: float = 0.0
```

and replace:

```python
    context.events.append((at, "reflex", reflex.event.format(name=state["name"])))
```

with:

```python
    if at - brain["reflex_ends"].get(reflex.name, -math.inf) >= reflex.quiet:
        context.events.append((at, "reflex", reflex.event.format(name=state["name"])))
```

- [ ] **Step 4: Write the fight and flee reflexes**

Create `backend/survival/creatures/defense.py`:

```python
"""Fight or flee: the reflexes that meet hostile creatures (spec L2, "Fight and flee reflexes").

A threat is a living hostile creature that could come after Mimo: within 16 blocks and no more
than 4 above or below it, nearest first (`threats`). Inside its own shelter (a room or passage
cell of a shelter it built) Mimo has none, since nothing gets in there
(creatures.moves.steps). A weapon is a sword, or a bow with arrows.

- flee (30): a threat, and health below 35, or the nearest threat within 6 blocks and no weapon.
  Mimo runs home when the threat is no nearer its home than Mimo is (inside its shelter it is
  safe), else 12 blocks straight away from the threat. Mimo walks a block in 0.3 s, faster than
  any hostile, so it gets away; the reflex ends when the run does and fires again (2 s later)
  while the danger lasts.
- fight (40): a weapon, health 50 or more (35 or more while a fight is on, that is when it ended
  a round in the last FIGHT_KEEP seconds), and a threat within 4 blocks, or, with a bow and
  arrows, one within 12 that is after Mimo and in plain sight. Mimo shoots when the target is 5 or
  more blocks away or it has no sword, strikes with its sword in reach, and else steps up to the
  target and strikes. One blow or shot a round; the reflex fires again at once while the fight
  goes on. Below 35 health flee, being more urgent, takes over: Mimo fights, then flees.
Both log their event once per encounter (Reflex.quiet), not every round. What a model picker is
told about danger comes from here too (`threats_payload`).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.worldgen import terrain_height
from backend.survival.creatures.archery import SHOOT_RANGE
from backend.survival.creatures.combat import ATTACK_REACH, weapon
from backend.survival.creatures.harm import ARMOR, sheltered
from backend.survival.creatures.hostiles import CHASE_RISE, CHASE_SIGHT
from backend.survival.creatures.kinds import kind_of
from backend.survival.creatures.moves import where
from backend.survival.creatures.table import dead
from backend.survival.grid import Cell, Grid
from backend.survival.memory import cell_of
from backend.survival.purposes import AT_HOME, home_of, underground, walk_to
from backend.survival.reflexes import Reflex, register
from backend.survival.situation import Situation

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FLEE_BELOW = 35.0
FLEE_NEAR = 6.0
FLEE_RUN = 12  # blocks straight away from the threat when home is no refuge
FLEE_REACH = 4.0  # the run may end this close to where it heads
FIGHT_FROM = 50.0
FIGHT_REACH = 4.0
SHOOT_FROM = 5.0  # blocks from which Mimo shoots rather than strikes
BOW_SIGHT = 12.0  # blocks within which Mimo shoots at a hostile coming after it
CLOSE_IN = 2.0  # a step up to the target ends this close to it
FIGHT_KEEP = 3.0  # server seconds after a round in which the fight is still on
QUIET = 30.0  # server seconds after the reflex ended during which a new round logs no event
THREATS_SHOWN = 4


def indoors(s: Situation) -> bool:
    """Mimo stands in a room or passage cell of a shelter it built."""
    return s.db is not None and s.grid.claimed(s.here) and sheltered(s.db, s.here)


def threats(s: Situation) -> list[dict]:
    """Living hostiles that could come after Mimo, nearest first; none while it is indoors."""
    def look() -> list[dict]:
        herd = s.grid.herd
        if herd is None or indoors(s):
            return []
        x, y, z = s.here
        found = []
        for creature in herd.near(x, z, CHASE_SIGHT):
            kind = kind_of(creature["kind"])
            if kind is not None and kind.hostile and not dead(creature) \
                    and abs(where(creature, s.at)[1] - y) <= CHASE_RISE:
                found.append(creature)
        return sorted(found, key=lambda creature: (s.distance(where(creature, s.at)), creature["id"]))
    return s.sensed("threats", look)


def threats_payload(s: Situation) -> dict:
    """What a model is told about danger (L2): `threats`, the hostiles that could come after Mimo
    (nearest first, at most THREATS_SHOWN, and whether each is after it), and `defense`: whether
    Mimo is safe indoors, its best sword, its arrows (with a bow), the armor it wears and the kind
    of creature that hurt it last."""
    shown = [{"kind": creature["kind"], "distance": round(s.distance(where(creature, s.at))),
              "after_mimo": bool(creature["state"].get("chasing"))} for creature in threats(s)[:THREATS_SHOWN]]
    defense = {"indoors": indoors(s), "sword": weapon(s.inventory),
               "arrows": s.count("arrow") if s.count("bow") else 0,
               "armor": [piece for piece in ARMOR if s.count(piece)], "last_hurt_by": s.state.get("hurt_by")}
    return {"threats": shown, "defense": defense}


def bow_ready(s: Situation) -> bool:
    return s.count("bow") > 0 and s.count("arrow") > 0


def armed(s: Situation) -> bool:
    return weapon(s.inventory) is not None or bow_ready(s)


def clear_line(grid: Grid, start: Cell, end: Cell) -> bool:
    """Nothing solid between two cells: points every half block along the line are checked."""
    samples = max(1, int(math.dist(start, end) * 2))
    for index in range(1, samples):
        share = index / samples
        cell = tuple(round(a + (b - a) * share) for a, b in zip(start, end))
        if cell not in (start, end) and grid.solid(cell):
            return False
    return True


# flee ------------------------------------------------------------------------------------------

def flee_due(s: Situation) -> bool:
    found = threats(s)
    if not found:
        return False
    close = s.distance(where(found[0], s.at)) <= FLEE_NEAR
    return s.vitals["health"] < FLEE_BELOW or (close and not armed(s))


def plan_flee(s: Situation, context: ActionContext) -> list[dict]:
    """Home when the threat is no nearer it than Mimo, else FLEE_RUN blocks straight away."""
    danger = where(threats(s)[0], s.at)
    home = home_of(s)
    if home is not None:
        refuge = cell_of(home)
        if s.distance(refuge) > AT_HOME and math.dist(danger, refuge) >= s.distance(refuge):
            return [walk_to(refuge)]
    x, y, z = s.here
    dx, dz = x - danger[0], z - danger[2]
    length = math.hypot(dx, dz) or 1.0
    tx, tz = round(x + dx / length * FLEE_RUN), round(z + dz / length * FLEE_RUN)
    ty = y if underground(s) else terrain_height(tx, tz, s.seed) + 1
    return [{"kind": "walk", "target": [tx, ty, tz], "reach": FLEE_REACH}]


register(Reflex("flee", 30, trigger=flee_due, plan=plan_flee, thought="Run! Get away from it!",
                event="{name} ran from a creature.", cooldown=2.0, quiet=QUIET))


# fight -----------------------------------------------------------------------------------------

def fight_target(s: Situation) -> dict | None:
    """The hostile Mimo fights now, or None (see the module docstring)."""
    if not armed(s):
        return None
    fighting = s.at - s.brain["reflex_ends"].get("fight", -math.inf) <= FIGHT_KEEP
    if s.vitals["health"] < (FLEE_BELOW if fighting else FIGHT_FROM):
        return None
    for creature in threats(s):
        there = where(creature, s.at)
        distance = s.distance(there)
        if distance <= FIGHT_REACH:
            return creature
        if (bow_ready(s) and distance <= BOW_SIGHT and creature["state"].get("chasing")
                and clear_line(s.grid, s.here, there)):
            return creature
    return None


def plan_fight(s: Situation, context: ActionContext) -> list[dict]:
    target = fight_target(s)
    if target is None:
        return []
    there = where(target, s.at)
    distance = s.distance(there)
    blow = {"creature": target["id"], "target": list(there)}
    sword = weapon(s.inventory)
    if bow_ready(s) and (distance >= SHOOT_FROM or sword is None) and distance <= SHOOT_RANGE:
        return [{"kind": "shoot", **blow}]
    if sword is None:
        return []
    if distance <= ATTACK_REACH:
        return [{"kind": "attack", **blow}]
    return [{"kind": "walk", "target": list(there), "reach": CLOSE_IN}, {"kind": "attack", **blow}]


register(Reflex("fight", 40, trigger=lambda s: fight_target(s) is not None, plan=plan_fight,
                thought="Stay back! I'm not afraid of you.", event="{name} stood its ground against a creature.",
                cooldown=0.0, quiet=QUIET))
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival.creatures import gear, hunting  # noqa: F401  (L1's hunt; L2's make_gear)
```

with:

```python
from backend.survival.creatures import defense, gear, hunting  # noqa: F401  (L1's hunt; L2's make_gear, fight, flee)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_defense.py"`
Expected: `Ran 13 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 739 tests` … `OK` (13 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/creatures/defense.py backend/survival/reflexes.py backend/survival/brain.py backend/tests/test_survival_defense.py backend/tests/test_survival_reflexes.py
git commit -m "feat: fight and flee reflexes that meet hostile creatures" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Hostiles come out in the dark, in the tick

**Files:**
- Create: `backend/survival/creatures/darkness.py`
- Modify: `backend/survival/creatures/simulate.py` (spawn in the dark; hostiles take their turns at their own times), `backend/survival/tick.py` (short steps near a hostile; death by a creature), `backend/workers/mimo_worker.py` (its line for such a death)
- Modify tests: `backend/tests/test_survival_tick.py`, `backend/tests/test_survival_worker.py`, `backend/tests/test_survival_api.py` (the starvation checks keep hostiles away), `backend/tests/test_survival_herds.py` (hostiles have a cap of their own; the exploring cost test keeps them away), `backend/tests/test_survival_defense.py` (the tick tests keep new ones away)
- Test: `backend/tests/test_survival_darkness.py`

**Interfaces:**
- Consumes: `light.Lights`, `light.sky_light`, `light.DARK`, `hostiles` (the kinds, `hostile_near`), `spawning.SIM_REACH`, `moves.roll`, `harm.pet_alive`, `acts.act`, `acts.Scene`.
- Produces:
  - `backend.survival.creatures.darkness`: `HOSTILE_CAP = 8`, `SPAWN_NEAR = 16`, `SPAWN_FAR = 40`, `DESPAWN_REACH = 64`, `SPAWN_EVERY = 30` game seconds, `SPAWN_TRIES = 4`, `SCAN_DEPTH = 24`, `SPAWN_RISE = 8`, `SKITTER_SHARE = 0.6`; `hostile_kinds()`, `despawn_far(scene)`, `hostiles_alive(scene) -> int`, `spots(grid, seed, x, z, level) -> list[Cell]`, `spawn_hostiles(scene) -> list[dict]` (the creatures it added; the time of the last chance is `state["dark_spawn_at"]`).
  - `simulate.simulate` calls `spawn_hostiles(scene)` after `populate`, then `take_turns(scene, loaded)`: `MAX_ACTS = 24` animal turns (one each), and for hostiles `HOSTILE_ACTS = 32` turns, each at its own `next_at`, at most `TURNS_EACH = 3` a call and no more than `LATE = 2` seconds (at the normal pace) behind the call.
  - `tick.FIGHT_SLICE = 1.0`: while `hostiles.hostile_near(grid, state)`, a step lasts at most 1 second of action time. `tick.caught(state) -> bool` and `tick.death_words(cause) -> str`; after every creature run, a creature's blow that took the last health records the death with the kind as its cause ("Pip was caught by a gloomling on day 3.").

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_darkness.py`:

```python
import math
import random
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival import tick
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.darkness import (
    DESPAWN_REACH, HOSTILE_CAP, SPAWN_EVERY, SPAWN_FAR, SPAWN_NEAR, spawn_hostiles, spots,
)
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.simulate import TURNS_EACH, take_turns
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables, dead
from backend.survival.grid import Grid, world_grid
from backend.survival.hatch import hatch
from backend.survival.memory import places
from backend.survival.registry import LifeRegistry
from backend.survival.vitals import START_VITALS
from backend.survival.tick import advance_world, tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state

NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}
DAY = {**NIGHT, "phase": "day", "seconds_into_day": 1000.0}
BORN = 1_000_000.0


def land(blocks=None, cave=False):
    """Grass at y 0 over stone; with `cave`, an open cave at y -4..-3 everywhere; `blocks` placed."""
    def natural(x, y, z):
        if y == 0:
            return "grass"
        if y < 0:
            return "air" if cave and -4 <= y <= -3 else "stone"
        return "air"

    grid = Grid(natural)
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet():
    return {"name": "Pip", "world_seed": "4", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
            "vitals": {"health": 100.0}, "died_at": None}


def scene(grid, state, at=100.0, clock=NIGHT):
    return Scene(grid, grid.herd, "4", state, at, 1.0, events=[], clock=clock)


class SpawnTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.survival.creatures.darkness.terrain_height", "backend.survival.light.terrain_height"):
            patcher = patch(target, lambda x, z, seed: 0)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_at_night_a_gloomling_comes_out_on_dark_ground_sixteen_to_forty_blocks_away(self):
        grid, state = land(), pet()
        born = spawn_hostiles(scene(grid, state))
        self.assertEqual([creature["kind"] for creature in born], ["gloomling"])
        x, y, z = cell_of(born[0])
        self.assertTrue(SPAWN_NEAR <= math.hypot(x, z) <= SPAWN_FAR + 1, (x, z))
        self.assertEqual((y, born[0]["next_at"]), (1, 101.0))
        self.assertEqual(spawn_hostiles(scene(grid, state, at=100.0 + SPAWN_EVERY - 1)), [])
        self.assertEqual(len(spawn_hostiles(scene(grid, state, at=100.0 + SPAWN_EVERY))), 1)

    def test_by_day_the_open_ground_is_lit_and_only_caves_spawn_them_mostly_skitters(self):
        self.assertEqual(spawn_hostiles(scene(land(), pet(), clock=DAY)), [])
        kinds = []
        for minute in range(20):
            found = spawn_hostiles(scene(land(cave=True), pet(), at=100.0 + 60 * minute, clock=DAY))
            self.assertEqual([cell_of(creature)[1] for creature in found], [-4])
            kinds += [creature["kind"] for creature in found]
        self.assertEqual(set(kinds), {"skitter", "gloomling"})

    def test_torches_keep_the_ground_near_them_safe_and_nothing_spawns_where_mimo_built(self):
        with patch("backend.survival.creatures.darkness.roll", lambda *args: 0.0):  # every try: 16 blocks east
            self.assertEqual([cell_of(creature) for creature in spawn_hostiles(scene(land(), pet()))],
                             [(16, 1, 0)])
            self.assertEqual(spawn_hostiles(scene(land({(16, 1, 2): "torch"}), pet())), [])
            claimed = land()
            claimed.claims.add((16, 1, 0))
            self.assertEqual(spawn_hostiles(scene(claimed, pet())), [])

    def test_no_more_than_eight_hostiles_alive_near_mimo(self):
        grid, state = land(), pet()
        near = [grid.herd.add("gloomling", (20 + n, 1, 0), 20.0, 0.0, 0.0, {}) for n in range(HOSTILE_CAP)]
        self.assertEqual(spawn_hostiles(scene(grid, state)), [])
        near[0]["state"]["pose"] = "dead"
        grid.herd.save(near[0])
        self.assertEqual(len(spawn_hostiles(scene(grid, state))), 1)

    def test_hostiles_far_from_mimo_go_at_night_and_out_of_its_reach_by_day_but_animals_stay(self):
        grid = land()
        far = grid.herd.add("gloomling", (int(DESPAWN_REACH) + 5, 1, 0), 20.0, 0.0, 0.0, {})
        beyond = grid.herd.add("skitter", (60, 1, 0), 12.0, 0.0, 0.0, {})
        near = grid.herd.add("skitter", (40, 1, 0), 12.0, 0.0, 0.0, {})
        cow = grid.herd.add("cow", (70, 1, 0), 10.0, 0.0, 0.0, {})
        spawn_hostiles(scene(grid, pet()))
        self.assertEqual([grid.herd.get(creature["id"]) is None for creature in (far, beyond, near, cow)],
                         [True, False, False, False])
        spawn_hostiles(scene(grid, pet(), clock=DAY))
        self.assertEqual([grid.herd.get(creature["id"]) is None for creature in (beyond, near, cow)],
                         [True, False, False])

    def test_a_column_offers_its_ground_and_its_caves_but_not_leaves_torches_or_water(self):
        grid = land({(3, 1, 0): "leaves", (4, 1, 0): "torch", (5, 0, 0): "water"}, cave=True)
        self.assertEqual(spots(grid, "4", 0, 0, 1), [(0, 1, 0), (0, -4, 0)])
        self.assertEqual(spots(grid, "4", 3, 0, 1), [(3, -4, 0)])
        self.assertEqual(spots(grid, "4", 4, 0, 1), [(4, -4, 0)])
        self.assertEqual(spots(grid, "4", 5, 0, 1), [(5, -4, 0)])
        self.assertEqual(spots(grid, "4", 0, 0, 8), [(0, 1, 0)])  # the cave is too far below Mimo
        self.assertEqual(spots(grid, "4", 0, 0, -10), [(0, -4, 0)])  # and the ground too far above


class TurnTests(unittest.TestCase):
    def add(self, grid, kind, cell):
        return grid.herd.add(kind, cell, KINDS[kind].health, 0.0, 0.0, {"home": list(cell), "turn": 0, "pose": "idle"})

    def test_a_hostile_takes_each_turn_due_in_a_call_at_its_own_time_but_not_long_ago(self):
        grid, state = land(), {**pet(), "vitals": dict(START_VITALS)}
        gloom, cow = self.add(grid, "gloomling", (1, 1, 0)), self.add(grid, "cow", (0, 1, 6))
        take_turns(scene(grid, state, at=10.0), [gloom, cow])
        self.assertEqual(state["vitals"]["health"], 94.0)  # at 8.0 and 9.2: LATE seconds back at most
        self.assertEqual(grid.herd.get(gloom["id"])["state"]["struck_at"], 9.2)
        self.assertEqual(grid.herd.get(cow["id"])["state"]["turn"], 1)  # an animal takes one turn
        skitter = self.add(grid, "skitter", (0, 1, 1))
        with patch("backend.survival.creatures.simulate.LATE", 100.0):
            take_turns(scene(grid, state, at=20.0), [skitter])
        self.assertEqual(state["vitals"]["health"], 94.0 - 2.0 * TURNS_EACH)  # no more than TURNS_EACH a call


class TickTests(unittest.TestCase):
    def hatched(self, root):
        registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
        life = hatch(registry, random.Random(3), timestamp=BORN)
        return registry, life, SurvivalWorld(registry.world_path(life))

    def test_a_gloomlings_blow_that_takes_mimos_last_health_kills_it(self):
        with tempfile.TemporaryDirectory() as root:
            registry, life, world = self.hatched(root)
            with world.transaction() as db:
                state = read_state(db)
                state["born_at"] = BORN - 2500.0  # deep in the first night
                state["vitals"]["health"] = 2.0
                write_state(db, state)
                x, y, z = (round(state["position"][axis]) for axis in "xyz")
                Herd(db).add("gloomling", (x + 1, y, z), 20.0, BORN, BORN, {"home": [x + 1, y, z], "turn": 0})
            state = tick_life(registry, BORN + 5, scale=1)
            self.assertEqual((state["status"], state["cause"], state["died_at"]), ("dead", "gloomling", BORN + 1))  # a second in: steps are short near it
            self.assertEqual(registry.get(life["id"])["cause"], "gloomling")
            self.assertEqual(world.events()[0]["text"], f"{life['name']} was caught by a gloomling on day 1.")
            with world.connect() as db:
                self.assertEqual([place["note"] for place in places(db, ("danger",))], ["gloomling"])

    def test_while_a_hostile_could_reach_mimo_the_tick_runs_in_one_second_steps(self):
        for near in (True, False):
            calls = []
            real = tick.simulate
            with tempfile.TemporaryDirectory() as root:
                _, _, world = self.hatched(root)
                with world.transaction() as db:
                    state = read_state(db)
                    state["born_at"] = BORN - 2500.0 / 60  # the first night, at 60x
                    write_state(db, state)
                    x, y, z = (round(state["position"][axis]) for axis in "xyz")
                    if near:
                        Herd(db).add("gloomling", (x + 1, y, z), 20.0, BORN, BORN, {"home": [x + 1, y, z], "turn": 0})
                with patch("backend.survival.tick.simulate", lambda *args: calls.append(args[2]) or real(*args)), \
                        patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []), \
                        patch("backend.survival.creatures.hostiles.hurt_pet", lambda *args: 0.0):
                    advance_world(world, BORN + 1.0, 60.0, action_scale=60.0)
            self.assertEqual(len(calls), 60 if near else 1, near)  # a game second a step, else one 60-s step

    def test_hostiles_come_out_at_night_stay_few_and_cost_little(self):
        spent, counts = [], []

        def timed(*args):
            start = time.perf_counter()
            real(*args)
            spent.append(time.perf_counter() - start)

        real = tick.simulate
        with tempfile.TemporaryDirectory() as root:
            _, _, world = self.hatched(root)
            with patch("backend.survival.tick.simulate", timed), \
                    patch("backend.survival.creatures.hostiles.hurt_pet", lambda *args: 0.0):
                for minute in range(1, 61):
                    state = advance_world(world, BORN + 60 * minute, 1.0)
                    with world.connect() as db:
                        found = world_grid(db, world.seed).herd.near(state["position"]["x"], state["position"]["z"], 48)
                    counts.append(sum(1 for creature in found if KINDS[creature["kind"]].hostile and not dead(creature)))
        self.assertLess(sum(spent) / len(spent), 0.020)
        self.assertLessEqual(max(counts), HOSTILE_CAP)
        night, day = counts[41:57], counts[:37]  # night falls 40 game minutes in
        self.assertGreater(sum(night) / len(night), sum(day) / len(day))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_tick.py`, replace:

```python
from pathlib import Path
```

with:

```python
from pathlib import Path
from unittest.mock import patch
```

and replace:

```python
        self.assertEqual(tick_life(self.registry, BORN + 2450, scale=1)["status"], "sleeping")
        self.assertEqual(tick_life(self.registry, BORN + 3700, scale=1)["status"], "idle")
```

with:

```python
        with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):  # L2: asleep in the open
            self.assertEqual(tick_life(self.registry, BORN + 2450, scale=1)["status"], "sleeping")
            self.assertEqual(tick_life(self.registry, BORN + 3700, scale=1)["status"], "idle")
```

and replace:

```python
        state = tick_life(self.registry, BORN + 20_000, scale=1)
```

with:

```python
        with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):
            state = tick_life(self.registry, BORN + 20_000, scale=1)  # L2: no gloomling hurries it along
```

In `backend/tests/test_survival_worker.py`, replace:

```python
            died = run_once(self.registry, line, timestamp=1000.0 + 20_000)
```

with:

```python
            with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):  # L2: it starves
                died = run_once(self.registry, line, timestamp=1000.0 + 20_000)
```

In `backend/tests/test_survival_api.py`, replace:

```python
        born = hatch_egg()["life"]["born_at"]
        tick_life(LifeRegistry(), born + 20_000, scale=1)
        memorial = get_mimo()
```

with:

```python
        born = hatch_egg()["life"]["born_at"]
        with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):  # L2: it starves
            tick_life(LifeRegistry(), born + 20_000, scale=1)
        memorial = get_mimo()
```

In `backend/tests/test_survival_herds.py`, replace:

```python
                    land = [creature for creature in found if not KINDS[creature["kind"]].water]
```

with:

```python
                    land = [creature for creature in found  # L2: hostiles have a cap of their own
                            if not KINDS[creature["kind"]].water and not KINDS[creature["kind"]].hostile]
```

and replace:

```python
                with patch("backend.survival.tick.simulate", timed):
```

with:

```python
                with patch("backend.survival.tick.simulate", timed), \
                        patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):  # L2's own test
```

In `backend/tests/test_survival_defense.py`, replace:

```python
from pathlib import Path
```

with:

```python
from pathlib import Path
from unittest.mock import patch
```

and replace:

```python
        at = 0.0
        while at < until:
            at += 0.25
            advance_actions(state, ctx, at)
            simulate(state, ctx, at)
            ctx.searches_left = 2
```

with:

```python
        at = 0.0
        with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):
            while at < until:
                at += 0.25
                advance_actions(state, ctx, at)
                simulate(state, ctx, at)
                ctx.searches_left = 2
```

and replace:

```python
            for second in range(1, 61):
                state = tick_life(registry, BORN + second, scale=1.0, mind=BRAIN, action_scale=1.0)
                chooser.poll(registry, BORN + second)
```

with:

```python
            with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):
                for second in range(1, 61):
                    state = tick_life(registry, BORN + second, scale=1.0, mind=BRAIN, action_scale=1.0)
                    chooser.poll(registry, BORN + second)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_darkness.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.darkness'`.

- [ ] **Step 3: Write the dark spawner**

Create `backend/survival/creatures/darkness.py`:

```python
"""Where hostile creatures come from, and where they go (spec L2, "Light levels" and "Hostile AI").

Once every SPAWN_EVERY game seconds (at most once a creature-hook call), while fewer than
HOSTILE_CAP hostiles are alive (counted in the table, not from what one call loaded; they are all
near Mimo, see below), the dark gets one chance to bring one near it:
up to SPAWN_TRIES columns 16 to 40 blocks from Mimo (rolled from the world seed and the time) are
searched from just over the natural ground down SCAN_DEPTH cells, and no more than SPAWN_RISE
cells above or below Mimo, for a cell where a creature can stand (dry, empty, room above it, not
on leaves), that nothing Mimo built claims (so never inside its shelter) and whose light is 7 or
less (backend.survival.light): they come out near where Mimo is, on the ground or in a cave
beside its tunnel, not in every cave under the land. The first such cell gets a
gloomling when it is open to the sky (dark ground at night) and, when it is covered (a cave, a
tunnel), a skitter three times in five, else a gloomling. By day the open ground is lit, so only
covered places spawn them; torches, lanterns and fires keep their surroundings lit at night.

Hostiles go too, in one cheap delete by kind and distance each call: any farther than
DESPAWN_REACH blocks from Mimo at night, and by day any beyond the 48 blocks the creature hook
simulates, since out there it would never burn, fade or come back. Daylight burns or fades those
near Mimo caught under the open sky (backend.survival.creatures.hostiles, sunlit).
"""

from __future__ import annotations

import json
import math
import sqlite3

from backend.services.blocks import is_replaceable
from backend.services.worldgen import terrain_height
from backend.survival.creatures import hostiles  # noqa: F401  (registers the hostile kinds and their actions)
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.kinds import KINDS, Kind
from backend.survival.creatures.moves import roll
from backend.survival.creatures.spawning import SIM_REACH
from backend.survival.creatures.table import missing_table
from backend.survival.grid import Cell, Grid
from backend.survival.light import DARK, Lights, sky_light

HOSTILE_CAP = 8
SPAWN_NEAR = 16.0
SPAWN_FAR = 40.0
DESPAWN_REACH = 64.0
SPAWN_EVERY = 30.0  # game seconds between two chances of a spawn
SPAWN_TRIES = 4  # columns one chance looks at
SCAN_DEPTH = 24  # cells a column is searched down from just over its natural ground
SPAWN_RISE = 8  # cells above or below Mimo a spawn may be
SKITTER_SHARE = 0.6  # of the hostiles spawning in covered places
FIRST_TURN = 1.0  # server seconds before a new hostile's first turn
UNDERFOOT = ("leaves",)
# Roll channels.
ANGLE, DISTANCE, KIND = 110, 111, 112


def hostile_kinds() -> list[str]:
    return sorted(kind.name for kind in KINDS.values() if kind.hostile)


def despawn_far(scene: Scene) -> None:
    """Remove every hostile farther (horizontally) from Mimo than DESPAWN_REACH blocks at night, or
    than SIM_REACH by day."""
    kinds = hostile_kinds()
    reach = DESPAWN_REACH if scene.night else SIM_REACH
    x, _, z = scene.pet
    try:
        scene.herd.db.execute(f"DELETE FROM creatures WHERE kind IN ({','.join('?' * len(kinds))}) "
                              "AND (x - ?) * (x - ?) + (z - ?) * (z - ?) > ?", (*kinds, x, x, z, z, reach * reach))
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise


def hostiles_alive(scene: Scene) -> int:
    """How many hostile creatures are alive, counted in the table."""
    kinds = hostile_kinds()
    try:
        rows = scene.herd.db.execute(f"SELECT state FROM creatures WHERE kind IN ({','.join('?' * len(kinds))})",
                                     kinds).fetchall()
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return 0
    return sum(1 for row in rows if json.loads(row[0] or "{}").get("pose") != "dead")


def spots(grid: Grid, seed: str, x: int, z: int, level: int) -> list[Cell]:
    """Cells in the column where a hostile could stand, highest first, within SPAWN_RISE of
    `level` (Mimo's height): empty (air or a plant), dry, on anything but leaves, with room over
    it, and claimed by nothing Mimo built."""
    top = terrain_height(x, z, seed) + 2
    found = []
    for y in range(min(top, level + SPAWN_RISE), max(top - SCAN_DEPTH, level - SPAWN_RISE - 1), -1):
        cell = (x, y, z)
        if (is_replaceable(grid.material(*cell)) and grid.standable(cell) and not grid.swimming(cell)
                and grid.passable((x, y + 1, z)) and grid.material(x, y - 1, z) not in UNDERFOOT
                and not grid.claimed(cell)):
            found.append(cell)
    return found


def born(scene: Scene, kind: Kind, cell: Cell) -> dict:
    """A new hostile of `kind` in `cell`, at home there; its first turn comes a second later."""
    state = {"home": list(cell), "pose": "idle", "turn": 0}
    return scene.herd.add(kind.name, cell, kind.health, scene.at, scene.at + FIRST_TURN / scene.pace, state)


def spawn_hostiles(scene: Scene) -> list[dict]:
    """Despawn far hostiles, then maybe spawn one in the dark near Mimo (see the module docstring).
    Returns the creatures it added."""
    despawn_far(scene)
    last = scene.state.get("dark_spawn_at")
    if hostiles_alive(scene) >= HOSTILE_CAP or (last is not None and (scene.at - last) * scene.scale < SPAWN_EVERY):
        return []
    scene.state["dark_spawn_at"] = scene.at
    x, y, z = scene.pet
    salt, lights = int(scene.at), None
    for attempt in range(SPAWN_TRIES):
        angle = 2 * math.pi * roll(scene.seed, salt, attempt, ANGLE)
        reach = SPAWN_NEAR + (SPAWN_FAR - SPAWN_NEAR) * roll(scene.seed, salt, attempt, DISTANCE)
        cx, cz = round(x + math.cos(angle) * reach), round(z + math.sin(angle) * reach)
        if math.hypot(cx - x, cz - z) < SPAWN_NEAR:
            continue
        for cell in spots(scene.grid, scene.seed, cx, cz, y):
            lights = lights or Lights(scene.grid, scene.pet, SPAWN_FAR)
            sky = sky_light(scene.grid, scene.seed, cell, scene.night)
            if max(sky, lights.at(cell)) > DARK:
                continue
            covered = sky == 0
            name = "skitter" if covered and roll(scene.seed, salt, attempt, KIND) < SKITTER_SHARE else "gloomling"
            return [born(scene, KINDS[name], cell)]
    return []
```

- [ ] **Step 4: Spawn in the creature hook, and let hostiles take their turns at their own times**

In `backend/survival/creatures/simulate.py`, replace:

```python
(backend.survival.creatures.spawning), clears away creatures that died more than DEAD_KEEP
```

with:

```python
(backend.survival.creatures.spawning) and, in the dark, hostile ones (L2,
backend.survival.creatures.darkness), clears away creatures that died more than DEAD_KEEP
```

and replace:

```python
call. Creatures farther away stay put. Moves are written to the creature rows; nothing searches
```

with:

```python
call. L2: a hostile takes each turn that comes due up to the call's time instead, at its own
`next_at` (at most LATE seconds behind the call), up to TURNS_EACH in one call, from a budget of
HOSTILE_ACTS of its own, so the animals never crowd it out. Near Mimo the tick runs in one-second
steps (backend.survival.tick), so there a gloomling strikes every 1.2 s; the cap keeps one that
was out of Mimo's sight when a long step began from walking up and striking within that step.
Creatures farther away stay put. Moves are written to the creature rows; nothing searches
```

and replace:

```python
from typing import TYPE_CHECKING
```

with:

```python
import heapq
from dataclasses import replace
from typing import TYPE_CHECKING
```

and replace:

```python
from backend.survival.creatures.acts import Scene, act
from backend.survival.creatures.spawning import SIM_REACH, populate
```

with:

```python
from backend.survival.creatures.acts import Scene, act
from backend.survival.creatures.darkness import spawn_hostiles
from backend.survival.creatures.kinds import kind_of
from backend.survival.creatures.spawning import SIM_REACH, populate
```

and replace:

```python
MAX_ACTS = 24  # creature turns in one call
```

with:

```python
MAX_ACTS = 24  # animal turns in one call, one each at most
HOSTILE_ACTS = 32  # hostile turns in one call (L2)
TURNS_EACH = 3  # turns one hostile takes in one call at most (L2)
LATE = 2.0  # server seconds (at the normal pace) a hostile's turn may lag the call's time at most
```

and replace:

```python
    loaded += populate(scene, loaded, scale)
    for creature in loaded:
```

with:

```python
    loaded += populate(scene, loaded, scale)
    loaded += spawn_hostiles(scene)
    for creature in loaded:
```

and replace:

```python
    due = sorted((creature for creature in loaded if not dead(creature) and creature["next_at"] <= at),
                 key=lambda creature: (creature["next_at"], creature["id"]))
    for creature in due[:MAX_ACTS]:
        if act(creature, scene) is None:
```

with:

```python
    take_turns(scene, loaded)


def take_turns(scene: Scene, loaded: list[dict]) -> None:
    """The creatures in `loaded` whose turn has come take it, earliest first: an animal once, at the
    scene's time; a hostile each turn that comes due up to then, at its own time (see the module
    docstring for the limits). Each creature that acted is saved once."""
    at, earliest = scene.at, scene.at - LATE / scene.pace
    left = {True: HOSTILE_ACTS, False: MAX_ACTS}
    queue = []
    for creature in loaded:
        if not dead(creature) and creature["next_at"] <= at:
            kind = kind_of(creature["kind"])
            queue.append((max(creature["next_at"], earliest), creature["id"], kind is not None and kind.hostile,
                          creature))
    heapq.heapify(queue)
    turns: dict[int, int] = {}
    acted = {}
    while queue:
        when, number, hostile, creature = heapq.heappop(queue)
        if left[hostile] <= 0:
            continue
        left[hostile] -= 1
        turns[number] = turns.get(number, 0) + 1
        acted[number] = creature
        if act(creature, replace(scene, at=when) if hostile else scene) is None:
```

and replace:

```python
        grid.herd.save(creature)
```

with:

```python
        if (hostile and turns[number] < TURNS_EACH and not dead(creature)
                and when < creature["next_at"] <= at):
            heapq.heappush(queue, (creature["next_at"], number, hostile, creature))
    for creature in acted.values():
        scene.herd.save(creature)
```

- [ ] **Step 5: Short steps near a hostile, and death by a creature, in the tick**

In `backend/survival/tick.py`, replace:

```python
the last tick ended on, since that tick already ran them up to it.
```

with:

```python
the last tick ended on, since that tick already ran them up to it. A hostile creature's blow that
takes Mimo's last health kills it (L2): the creature's kind is the cause of death.
```

and replace:

```python
from backend.survival.clock import DAY_SECONDS, action_scale as action_scale_setting, clock_at, is_night, time_scale
from backend.survival.creatures.simulate import simulate
```

with:

```python
from backend.survival.clock import DAY_SECONDS, action_scale as action_scale_setting, clock_at, is_night, time_scale
from backend.survival.creatures.hostiles import hostile_near
from backend.survival.creatures.simulate import simulate
```

and replace:

```python
MAX_STEP_SECONDS = 60.0
HUNGRY_BELOW = 30.0
```

with:

```python
MAX_STEP_SECONDS = 60.0
# L2: while a hostile creature could reach Mimo, a step lasts at most this many seconds of action
# time (divided by MIMO_ACTION_SCALE), so fights and flights see where the creatures are now.
FIGHT_SLICE = 1.0
HUNGRY_BELOW = 30.0
```

and replace:

```python
def record_death(state: dict, cause: str, at: float, scale: float, events: list[Event]) -> None:
```

with:

```python
def death_words(cause: str) -> str:
    """How a death reads: "died of the cold", or, for a creature's kind (L2), "was caught by a gloomling"."""
    if cause in CAUSE_TEXT:
        return f"died of {CAUSE_TEXT[cause]}"
    return f"was caught by a {cause.replace('_', ' ')}"


def record_death(state: dict, cause: str, at: float, scale: float, events: list[Event]) -> None:
```

and replace:

```python
    events.append((at, "death", f"{state['name']} died of {CAUSE_TEXT[cause]} on day {day}."))
```

with:

```python
    events.append((at, "death", f"{state['name']} {death_words(cause)} on day {day}."))
```

and replace:

```python
def advance_world(world: SurvivalWorld, timestamp: float, scale: float, mind: Mind = RESTING,
```

with:

```python
def caught(state: dict) -> bool:
    """A hostile creature's blow (L2, backend.survival.creatures.harm) took Mimo's last health."""
    return state["vitals"]["health"] <= 0 and bool(state.get("hurt_by"))


def advance_world(world: SurvivalWorld, timestamp: float, scale: float, mind: Mind = RESTING,
```

and replace:

```python
                run_creatures(state, context, cursor)
            step = min(MAX_STEP_SECONDS, remaining)
```

with:

```python
                run_creatures(state, context, cursor)
                if caught(state):
                    record_death(state, state["hurt_by"], cursor, scale, events)
                    break
            step = min(MAX_STEP_SECONDS, remaining)
```

and replace:

```python
            step = min(MAX_STEP_SECONDS, remaining)
            night = is_night(clock_at(state["born_at"], cursor, scale)["phase"])
```

with:

```python
            step = min(MAX_STEP_SECONDS, remaining)
            if hostile_near(context.grid, state):
                step = min(step, FIGHT_SLICE / action_scale * scale)
            night = is_night(clock_at(state["born_at"], cursor, scale)["phase"])
```

and replace:

```python
                run_creatures(state, context, timestamp)
        state["last_tick_at"] = state["died_at"] if state["died_at"] is not None else timestamp
```

with:

```python
                run_creatures(state, context, timestamp)
                if caught(state):
                    record_death(state, state["hurt_by"], timestamp, scale, events)
        state["last_tick_at"] = state["died_at"] if state["died_at"] is not None else timestamp
```

In `backend/workers/mimo_worker.py`, replace:

```python
from backend.survival.tick import RESTING, Mind, tick_life
```

with:

```python
from backend.survival.tick import RESTING, Mind, death_words, tick_life
```

and replace:

```python
        line = f"{state['name']} died of {state['cause']}."
```

with:

```python
        line = f"{state['name']} {death_words(state['cause'])}."
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_darkness.py"`
Expected: `Ran 10 tests` … `OK` (a few seconds: hatched worlds tick through a night).

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 749 tests` … `OK` (10 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`. Every headless pet now meets gloomlings and skitters at night and lives: it sleeps behind its door, and the fight and flee reflexes of Task 6 meet what comes on the way home.

- [ ] **Step 7: Commit**

```bash
git add backend/survival/creatures/darkness.py backend/survival/creatures/simulate.py backend/survival/tick.py backend/workers/mimo_worker.py backend/tests/test_survival_darkness.py backend/tests/test_survival_tick.py backend/tests/test_survival_worker.py backend/tests/test_survival_api.py backend/tests/test_survival_herds.py backend/tests/test_survival_defense.py
git commit -m "feat: hostiles come out in the dark near Mimo, and a creature's blow can end a life" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: What the model and the viewer are told

**Files:**
- Modify: `backend/survival/pickers.py` (`threats` and `defense` in the model payload), `backend/survival/creatures/view.py` (hostiles in the creature stream), `backend/survival/snapshot.py` (`hurt_at`, `hurt_by`)
- Modify tests: `backend/tests/test_survival_pickers.py`
- Test: `backend/tests/test_survival_threats.py`

**Interfaces:**
- Consumes: `defense.threats_payload` (Task 6), `view.creature_view`, `snapshot.survival_view`.
- Produces:
  - `pickers.context_payload(s, events)` gains `threats` (the nearest 4: `kind`, `distance` in whole blocks, `after_mimo`) and `defense` (`indoors`, `sword`, `arrows` (0 without a bow), `armor`, `last_hurt_by`).
  - `/api/mimo` `creatures[]`: a hostile has `hostile: true`, its state may read `chasing`, `attacking` or `burning`, and `struck_at` and `burning_at` come when set; `creature_moves` includes chases. The snapshot gains `hurt_at` and `hurt_by` (null when unset).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_threats.py`:

```python
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.choosing import route_for
from backend.survival.creatures.moves import timed
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.pickers import context_payload
from backend.survival.registry import LifeRegistry
from backend.survival.situation import Situation
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS
from backend.survival.world import SurvivalWorld, read_state, write_state

NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}


class ModelPayloadTests(unittest.TestCase):
    def test_the_model_is_told_what_threatens_mimo_and_what_it_can_meet_them_with(self):
        grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        create_creature_tables(db)
        grid.herd = Herd(db)
        grid.herd.add("gloomling", (5, 1, 0), 20.0, 0.0, 0.0, {"chasing": True})
        grid.herd.add("skitter", (0, 1, 10), 12.0, 0.0, 0.0, {})
        grid.herd.add("cow", (2, 1, 0), 10.0, 0.0, 0.0, {})
        state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                 "inventory": {"stone_sword": 1, "bow": 1, "arrow": 5, "leather_cap": 1}, "vitals": dict(START_VITALS),
                 "traits": {}, "brain": new_brain(0.0), "hurt_by": "skitter"}
        payload = context_payload(Situation(state, grid, NIGHT, 10.0, db), [])
        self.assertEqual(payload["threats"], [{"kind": "gloomling", "distance": 5, "after_mimo": True},
                                              {"kind": "skitter", "distance": 10, "after_mimo": False}])
        self.assertEqual(payload["defense"], {"indoors": False, "sword": "stone_sword", "arrows": 5,
                                              "armor": ["leather_cap"], "last_hurt_by": "skitter"})

    def test_the_alarm_reaches_jev_at_once_even_right_after_another_call(self):
        brain = new_brain(0.0)
        brain["last_call_at"] = 995.0
        brain["pending"] = {"id": 3, "reasons": ["threat"], "since": 990.0, "urgent": True}
        self.assertEqual(route_for(brain, 1000.0, {"TYPESAFE_API_KEY": "k"}, 600.0), "jev")
        brain["pending"]["urgent"] = False
        self.assertEqual(route_for(brain, 1000.0, {"TYPESAFE_API_KEY": "k"}, 600.0), "utility")


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()
        hatch_egg()
        registry = LifeRegistry()
        self.world = SurvivalWorld(registry.world_path(registry.active_life()))

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def add(self, *creatures):
        """Add (kind, dx, dz, health, state) creatures around Mimo; returns Mimo's cell."""
        state = self.world.state()
        x, y, z = (round(state["position"][axis]) for axis in "xyz")
        with self.world.transaction() as db:
            herd = Herd(db)
            for kind, dx, dz, health, extra in creatures:
                herd.add(kind, (x + dx, y, z + dz), health, 0.0, 0.0, {"turn": 0, **extra})
        return x, y, z

    def test_the_viewer_learns_which_creatures_are_hostile_what_they_do_and_when_mimo_was_hurt(self):
        now = time.time()
        self.add(("gloomling", 3, 0, 20.0, {"pose": "attacking", "struck_at": now - 1.0}),
                 ("skitter", 0, 6, 12.0, {"pose": "idle"}),
                 ("gloomling", -4, 0, 20.0, {"pose": "burning", "burning_at": now - 0.5}),
                 ("cow", 5, 5, 10.0, {"pose": "idle"}))
        with self.world.transaction() as db:
            state = read_state(db)
            state.update(hurt_at=now - 1.0, hurt_by="gloomling")
            write_state(db, state)
        view = get_mimo()
        by_state = {creature["state"]: creature for creature in view["creatures"]}
        self.assertAlmostEqual(by_state["attacking"]["struck_at"], now - 1.0, places=1)
        self.assertAlmostEqual(by_state["burning"]["burning_at"], now - 0.5, places=1)
        self.assertEqual({creature["kind"]: creature.get("hostile", False) for creature in view["creatures"]},
                         {"gloomling": True, "skitter": True, "cow": False})
        self.assertEqual((view["hurt_at"], view["hurt_by"]), (now - 1.0, "gloomling"))

    def test_a_chase_reads_chasing_while_it_runs_and_the_stream_stays_small(self):
        now = time.time()
        x, y, z = (round(self.world.state()["position"][axis]) for axis in "xyz")
        run = timed((x + 9, y, z), [(x + 8, y, z), (x + 7, y, z)], now - 0.5, 0.9)
        self.add(*[("gloomling", 9, dz, 20.0, {"pose": "chasing", "chasing": True, "path": run}) for dz in range(8)],
                 *[("sheep", dx, dz, 8.0, {"pose": "fleeing", "path": run}) for dx in range(-3, 3) for dz in range(-2, 2)])
        view = get_mimo()
        chasers = [creature for creature in view["creatures"] if creature["kind"] == "gloomling"]
        self.assertEqual({creature["state"] for creature in chasers}, {"chasing"})
        size = len(json.dumps({"creatures": view["creatures"], "creature_moves": view["creature_moves"]}))
        self.assertLess(size, 16_000)  # 8 hostiles and 24 animals, all on the move


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_pickers.py`, replace:

```python
                                        "known_places", "recent_events", "trigger", "building", "exploration"})
```

with:

```python
                                        "known_places", "recent_events", "trigger", "building", "exploration",
                                        "threats", "defense"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_threats.py"`
Expected: failures: the payload has no `threats` and the creature view no `hostile`.

- [ ] **Step 3: Tell the model about danger**

In `backend/survival/pickers.py`, replace:

```python
Mimo built or could build (M5) and how much of the land around it it has explored.
```

with:

```python
Mimo built or could build (M5), how much of the land around it it has explored, and (L2) the
hostile creatures near it and what it can meet them with.
```

and replace:

```python
from backend.survival.building import building_payload
from backend.survival.exploring import exploration_payload
```

with:

```python
from backend.survival.building import building_payload
from backend.survival.creatures.defense import threats_payload
from backend.survival.exploring import exploration_payload
```

and replace:

```python
        "exploration": exploration_payload(s),
    }
```

with:

```python
        "exploration": exploration_payload(s),
        # L2: the hostile creatures that could come after Mimo, and how it can meet them.
        **threats_payload(s),
    }
```

- [ ] **Step 4: Tell the viewer**

In `backend/survival/creatures/view.py`, replace:

```python
and when a fish last leapt at Mimo's hook (`caught_at`). A creature that died more than DEAD_KEEP
seconds ago is left out.
```

with:

```python
and when a fish last leapt at Mimo's hook (`caught_at`). L2: a hostile kind says so
(`hostile`), its state may also be "chasing", "attacking" or "burning", and it tells when it last
struck Mimo (`struck_at`) and when it caught fire (`burning_at`). A creature that died more than
DEAD_KEEP seconds ago is left out.
```

and replace:

```python
MOVING = ("walking", "fleeing")
WHEN_SET = ("hurt_at", "dead_at", "caught_at")
```

with:

```python
MOVING = ("walking", "fleeing", "chasing")
WHEN_SET = ("hurt_at", "dead_at", "caught_at", "struck_at", "burning_at")
```

and replace:

```python
            "state": state_of(creature, now)}
    for key in WHEN_SET:
```

with:

```python
            "state": state_of(creature, now)}
    if kind is not None and kind.hostile:
        view["hostile"] = True
    for key in WHEN_SET:
```

In `backend/survival/snapshot.py`, replace:

```python
        **creatures,
        **brain_view(state.get("brain")),
```

with:

```python
        **creatures,
        # L2: when a creature last hurt Mimo and its kind, for the viewer's flash and the HUD.
        "hurt_at": state.get("hurt_at"),
        "hurt_by": state.get("hurt_by"),
        **brain_view(state.get("brain")),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_threats.py"`
Expected: `Ran 4 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 753 tests` … `OK` (4 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/pickers.py backend/survival/creatures/view.py backend/survival/snapshot.py backend/tests/test_survival_threats.py backend/tests/test_survival_pickers.py
git commit -m "feat: threats in the model payload, and hostiles and Mimo's hurts in the stream" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Viewer: the words for danger, and the bow's draw

**Files:**
- Modify: `frontend/src/survival/types.ts` (hostiles, shots and hurts in the stream), `frontend/src/survival/hud.ts` (the danger line, the flash's timing, a death by a creature, the new words), `frontend/src/survival/SurvivalHud.tsx` (show them), `frontend/src/survival/replay.ts` (a replayed shot keeps its `hit`), `frontend/src/survival/animation.ts` (the pet draws its bow: every action kind needs a move, so it comes with `shoot`)
- Test: `frontend/src/survival/hud.test.ts`, `frontend/src/survival/replay.test.ts`, `frontend/src/survival/animation.test.ts`

**Interfaces:**
- Consumes: the stream of Task 8; `replay.REPLAY_DELAY`, `hud.thingName`.
- Produces:
  - `types.ts`: `ActionKind` gains `'shoot'`; `MimoAction.hit?` and `FinishedAction.hit?`; `CreatureState` gains `'chasing' | 'attacking' | 'burning'`; `Creature.hostile?`, `struck_at?`, `burning_at?`; `SurvivalState.hurt_at?` and `hurt_by?` (null or absent from an older API).
  - `hud.ts`: `DANGER_REACH = 12`; `dangerText(creatures, position) -> string | null` ("A gloomling is close!", "2 gloomlings are close!", "2 creatures are close!"; burning and dead ones are no danger); `hurtFlashDelay(hurtAt, serverTime) -> number | null` (seconds until the flash, so it lands with the pet drawn REPLAY_DELAY behind; null for none or a blow older than 3 s); `lifeLine` reads "caught by a gloomling" for a creature's kind; words for `shoot` ("Shooting"), `make_gear` ("Making gear") and the `fight` reflex ("Fighting back!").
  - `SurvivalHud.tsx`: the danger line under the purpose line, and a red glow at the screen's edges that fades once per blow (`element.animate`, no stylesheet change).
  - `animation.ts`: `PetMove` gains `'aim'` (`shoot` plays it) and `DRAW_SECONDS = 0.6`: the pet leans back to draw, then recoils as the arrow goes (Task 10 flies the arrow).

- [ ] **Step 1: Write the failing tests**

In `frontend/src/survival/hud.test.ts`, replace:

```ts
  actionText, careLabel, causeText, chestText, clockTime, dayLabel, homeText, lifeLine, purposeText, statusText, thingName,
  vitalBars, workerOnline,
```

with:

```ts
  DANGER_REACH, actionText, careLabel, causeText, chestText, clockTime, dangerText, dayLabel, homeText, hurtFlashDelay,
  lifeLine, purposeText, statusText, thingName, vitalBars, workerOnline,
```

and replace:

```ts
import type { Built, Chests } from './types'
```

with:

```ts
import { REPLAY_DELAY } from './replay'
import type { Built, Chests, Creature } from './types'
```

and replace:

```ts
      .toBe('Survived 1 day · died of starvation')
  })
```

with:

```ts
      .toBe('Survived 1 day · died of starvation')
    expect(lifeLine({ kind: 'survival', alive: false, days: 3, cause: 'gloomling' }))
      .toBe('Survived 3 days · caught by a gloomling')
  })
})

describe('danger', () => {
  const gloom: Creature = { id: 1, kind: 'gloomling', x: 5, y: 1, z: 0, heading: 0, health: 1, state: 'chasing', hostile: true }
  const here = { x: 0, y: 1, z: 0 }

  it('warns of the hostile creatures close to Mimo', () => {
    expect(dangerText([gloom], here)).toBe('A gloomling is close!')
    expect(dangerText([gloom, { ...gloom, id: 2, x: -3 }], here)).toBe('2 gloomlings are close!')
    expect(dangerText([gloom, { ...gloom, id: 3, kind: 'skitter' }], here)).toBe('2 creatures are close!')
    const cow: Creature = { ...gloom, id: 4, kind: 'cow', hostile: undefined }
    expect(dangerText([cow, { ...gloom, x: DANGER_REACH + 1 }, { ...gloom, state: 'burning' }, { ...gloom, state: 'dead' }], here))
      .toBeNull()
    expect(dangerText(undefined, here)).toBeNull()
  })

  it('flashes for a blow when the pet drawn behind the server takes it', () => {
    expect(hurtFlashDelay(100, 100.5)).toBeCloseTo(REPLAY_DELAY - 0.5)
    expect(hurtFlashDelay(100, 102)).toBe(0)
    expect(hurtFlashDelay(100, 104)).toBeNull()
    expect(hurtFlashDelay(null, 100)).toBeNull()
    expect(hurtFlashDelay(undefined, 100)).toBeNull()
  })
```

and replace:

```ts
      .toBe('Attacking')
    expect(thingName('red_mushroom')).toBe('red mushroom')
```

with:

```ts
      .toBe('Attacking')
    expect(actionText({ kind: 'shoot', started_at: 0, ends_at: 1, target: { x: 1, y: 2, z: 3 }, hit: true }, 'shooting'))
      .toBe('Shooting')
    expect(thingName('red_mushroom')).toBe('red mushroom')
```

and replace:

```ts
    expect(purposeText({ purpose: 'hunt', reflex: null, choosing: false })).toBe('Hunting')
    expect(purposeText({ purpose: null, reflex: null, choosing: true })).toBe('Deciding what to do')
```

with:

```ts
    expect(purposeText({ purpose: 'hunt', reflex: null, choosing: false })).toBe('Hunting')
    expect(purposeText({ purpose: 'make_gear', reflex: null, choosing: false })).toBe('Making gear')
    expect(purposeText({ purpose: 'sleep', reflex: 'fight', choosing: false })).toBe('Fighting back!')
    expect(purposeText({ purpose: 'sleep', reflex: 'flee', choosing: false })).toBe('Running away!')
    expect(purposeText({ purpose: null, reflex: null, choosing: true })).toBe('Deciding what to do')
```

In `frontend/src/survival/replay.test.ts`, replace:

```ts
  it('falls back to the server position when no path says', () => {
```

with:

```ts
  it('replays a finished shot with whether its arrow flew true', () => {
    const shot: FinishedAction = { kind: 'shoot', started_at: 20, ended_at: 21, result: 'done', target: { x: 9, y: 1, z: 0 },
      hit: false }
    expect(replayAt(null, [shot], server, 20.5).step).toMatchObject({ kind: 'shoot', ends_at: 21, hit: false })
  })

  it('falls back to the server position when no path says', () => {
```

In `frontend/src/survival/animation.test.ts`, replace:

```ts
import { bodyPose, crumbs, moveFor, zPuffs } from './animation'
```

with:

```ts
import { DRAW_SECONDS, bodyPose, crumbs, moveFor, zPuffs } from './animation'
```

and replace:

```ts
    expect(moveFor({ kind: 'attack', started_at: 0, ends_at: 0.6, target: { x: 2, y: 1, z: 0 } }, 0.3)).toBe('swing')
  })
```

with:

```ts
    expect(moveFor({ kind: 'attack', started_at: 0, ends_at: 0.6, target: { x: 2, y: 1, z: 0 } }, 0.3)).toBe('swing')
    expect(moveFor({ kind: 'shoot', started_at: 0, ends_at: 1, target: { x: 9, y: 1, z: 0 }, hit: true }, 0.3)).toBe('aim')
  })
```

and replace:

```ts
    expect(bodyPose('swing', 0.6, 0, 0).pitch).toBeCloseTo(0)
  })
```

with:

```ts
    expect(bodyPose('swing', 0.6, 0, 0).pitch).toBeCloseTo(0)
  })

  it('leans back to draw the bow, then recoils as the arrow goes', () => {
    expect(bodyPose('aim', 0, 0, 0).pitch).toBeCloseTo(0)
    expect(bodyPose('aim', DRAW_SECONDS - 0.01, 0, 0).pitch).toBeLessThan(-0.15)
    expect(bodyPose('aim', DRAW_SECONDS, 0, 0).pitch).toBeCloseTo(0.12)
    expect(bodyPose('aim', DRAW_SECONDS + 0.5, 0, 0).pitch).toBeCloseTo(0)
  })
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/hud.test.ts src/survival/replay.test.ts src/survival/animation.test.ts`
Expected: failures: `dangerText` and `hurtFlashDelay` are not exported, the replayed shot has no `hit` and a shot plays no `aim`.

- [ ] **Step 3: Add the types**

In `frontend/src/survival/types.ts`, replace:

```ts
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook' | 'store' | 'take' | 'drop' | 'attack'
```

with:

```ts
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook' | 'store' | 'take' | 'drop' | 'attack' | 'shoot'
```

and replace:

```ts
  blocks?: number
}
```

with:

```ts
  blocks?: number
  /** A shot (L2): whether the arrow flies true. */
  hit?: boolean
}
```

and replace:

```ts
  path?: PathPoint[]
}
```

with:

```ts
  path?: PathPoint[]
  /** A shot (L2): whether the arrow flew true. */
  hit?: boolean
}
```

and replace:

```ts
export type CreatureState = 'idle' | 'walking' | 'grazing' | 'fleeing' | 'swimming' | 'dead'
```

with:

```ts
export type CreatureState = 'idle' | 'walking' | 'grazing' | 'fleeing' | 'swimming' | 'dead'
  | 'chasing' | 'attacking' | 'burning'
```

and replace:

```ts
  caught_at?: number
}
```

with:

```ts
  caught_at?: number
  /** L2: a gloomling or skitter, which hunts Mimo. */
  hostile?: boolean
  /** Server time a hostile last struck Mimo: its lunge. */
  struck_at?: number
  /** Server time a hostile caught fire in the sun. */
  burning_at?: number
}
```

and replace:

```ts
  creature_moves: CreatureMove[]
  /** The patches Mimo visited within 96 blocks of it, for the minimap's fog of war. */
```

with:

```ts
  creature_moves: CreatureMove[]
  /** When a creature last hurt Mimo (server time) and its kind (L2); an older API sends neither. */
  hurt_at?: number | null
  hurt_by?: string | null
  /** The patches Mimo visited within 96 blocks of it, for the minimap's fog of war. */
```

- [ ] **Step 4: Add the words, the danger line and the flash's timing**

In `frontend/src/survival/hud.ts`, replace:

```ts
import type { ActionKind, Built, CareKind, Chests, ClockPhase, LifeRow, MimoAction, SurvivalState, VitalName, Vitals } from './types'
```

with:

```ts
import { REPLAY_DELAY } from './replay'
import type {
  ActionKind, Built, CareKind, Chests, ClockPhase, Creature, LifeRow, MimoAction, Point, SurvivalState, VitalName, Vitals,
} from './types'
```

and replace:

```ts
  starvation: 'starvation', cold: 'the cold', drowning: 'drowning', fall: 'a fall', creature: 'a creature',
}

export function vitalBars(vitals: Vitals, names: VitalName[] = HUD_VITALS): VitalBar[] {
```

with:

```ts
  starvation: 'starvation', cold: 'the cold', drowning: 'drowning', fall: 'a fall', creature: 'a creature',
}
/** Causes of death that are a creature's kind (L2): the pet was caught, not killed by the world. */
const CAUGHT_BY = new Set(['gloomling', 'skitter', 'creature'])
/** How close (blocks, across) a hostile creature is for the HUD to warn of it. */
export const DANGER_REACH = 12
/** How long after a blow (server seconds) its flash may still start. */
const FLASH_WINDOW = 3

export function vitalBars(vitals: Vitals, names: VitalName[] = HUD_VITALS): VitalBar[] {
```

and replace:

```ts
  drop: 'Dropping', attack: 'Attacking',
```

with:

```ts
  drop: 'Dropping', attack: 'Attacking', shoot: 'Shooting',
```

and replace:

```ts
  light_up: 'Lighting torches', hunt: 'Hunting',
```

with:

```ts
  light_up: 'Lighting torches', hunt: 'Hunting', make_gear: 'Making gear',
```

and replace:

```ts
  flee: 'Running away!',
```

with:

```ts
  flee: 'Running away!', fight: 'Fighting back!',
```

and replace:

```ts
  if (life.alive) return `Alive · day ${life.days}`
  return `Survived ${daysText(life.days)} · died of ${causeText(life.cause)}`
```

with:

```ts
  if (life.alive) return `Alive · day ${life.days}`
  if (life.cause && CAUGHT_BY.has(life.cause)) return `Survived ${daysText(life.days)} · caught by a ${thingName(life.cause)}`
  return `Survived ${daysText(life.days)} · died of ${causeText(life.cause)}`
```

and replace:

```ts
  return `Survived ${daysText(life.days)} · died of ${causeText(life.cause)}`
}
```

with:

```ts
  return `Survived ${daysText(life.days)} · died of ${causeText(life.cause)}`
}

/**
 * The HUD's danger line (L2): the living hostile creatures within DANGER_REACH blocks of Mimo, like
 * "A gloomling is close!", or null. The server lists creatures nearest first; a burning one is no danger.
 */
export function dangerText(creatures: readonly Creature[] | null | undefined, position: Point): string | null {
  const near = (creatures ?? []).filter((creature) => creature.hostile && creature.state !== 'dead'
    && creature.state !== 'burning' && Math.hypot(creature.x - position.x, creature.z - position.z) <= DANGER_REACH)
  if (near.length === 0) return null
  const kind = thingName(near[0].kind)
  if (near.length === 1) return `A ${kind} is close!`
  return new Set(near.map((creature) => creature.kind)).size === 1 ? `${near.length} ${kind}s are close!`
    : `${near.length} creatures are close!`
}

/**
 * Seconds from now until the HUD flashes for Mimo's last blow (L2), so the flash lands with the
 * pet drawn REPLAY_DELAY behind the server; null when there is no blow to flash for.
 */
export function hurtFlashDelay(hurtAt: number | null | undefined, serverTime: number): number | null {
  if (hurtAt === null || hurtAt === undefined) return null
  const age = serverTime - hurtAt
  return age < 0 || age > FLASH_WINDOW ? null : Math.max(0, REPLAY_DELAY - age)
}
```

In `frontend/src/survival/replay.ts`, replace:

```ts
  if (entry.recipe) step.recipe = entry.recipe
  return step
```

with:

```ts
  if (entry.recipe) step.recipe = entry.recipe
  if (entry.hit !== undefined) step.hit = entry.hit
  return step
```

In `frontend/src/survival/animation.ts`, replace:

```ts
export type PetMove = 'idle' | 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'sleep' | 'work' | 'fish' | 'swing'
```

with:

```ts
export type PetMove = 'idle' | 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'sleep' | 'work' | 'fish' | 'swing'
  | 'aim'
```

and replace:

```ts
  fish: 'fish', cook: 'work', store: 'place', take: 'place', drop: 'place', attack: 'swing',
```

with:

```ts
  fish: 'fish', cook: 'work', store: 'place', take: 'place', drop: 'place', attack: 'swing', shoot: 'aim',
```

and replace:

```ts
const LUNGE_SECONDS = 0.5
const NIBBLES_PER_SECOND = 3
```

with:

```ts
const LUNGE_SECONDS = 0.5
/** A shot (L2): the bow is drawn for this long, then the arrow flies (archery.ts). */
export const DRAW_SECONDS = 0.6
const RECOIL_SECONDS = 0.3
const NIBBLES_PER_SECOND = 3
```

and replace:

```ts
    }
    case 'fish':
```

with:

```ts
    }
    case 'aim':
      // Leaning back as it draws the bow, then a little recoil forward as the arrow goes.
      pose.pitch = stepTime < DRAW_SECONDS
        ? -0.18 * (stepTime / DRAW_SECONDS)
        : 0.12 * Math.max(0, 1 - (stepTime - DRAW_SECONDS) / RECOIL_SECONDS)
      break
    case 'fish':
```

- [ ] **Step 5: Show them on the HUD**

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```tsx
import type { ReactNode } from 'react'
```

with:

```tsx
import { useEffect, useRef, useState, type ReactNode } from 'react'
```

and replace:

```tsx
import { actionText, careLabel, clockTime, dayLabel, homeText, purposeText, vitalBars, type VitalLevel } from './hud'
```

with:

```tsx
import {
  actionText, careLabel, clockTime, dangerText, dayLabel, homeText, hurtFlashDelay, purposeText, vitalBars, type VitalLevel,
} from './hud'
```

and replace:

```tsx
    </svg>
  )
}
```

with:

```tsx
    </svg>
  )
}

/** L2: a red glow at the screen's edges that fades once, `delay` seconds after it mounts (one per blow). */
function HurtFlash({ delay }: { delay: number }) {
  const glow = useRef<HTMLDivElement>(null)
  const [start] = useState(delay)
  useEffect(() => {
    const fade = glow.current?.animate([{ opacity: 1 }, { opacity: 0 }],
      { duration: 700, delay: start * 1000, easing: 'ease-out', fill: 'forwards' })
    return () => fade?.cancel()
  }, [start])
  return <div ref={glow} aria-hidden
    className="pointer-events-none absolute inset-0 z-20 opacity-0 shadow-[inset_0_0_120px_30px_rgba(199,70,58,0.55)]" />
}
```

and replace:

```tsx
  const home = homeText(state.structures)
  return (
```

with:

```tsx
  const home = homeText(state.structures)
  const danger = dangerText(state.creatures, state.position)
  const flash = hurtFlashDelay(state.hurt_at, state.server_time)
  return (
```

and replace:

```tsx
    <>
      <div className="absolute inset-x-4 top-4 z-10 flex flex-col gap-3 sm:inset-x-8 sm:top-8 sm:flex-row sm:items-start sm:justify-between">
```

with:

```tsx
    <>
      {flash !== null && <HurtFlash key={state.hurt_at ?? 0} delay={flash} />}
      <div className="absolute inset-x-4 top-4 z-10 flex flex-col gap-3 sm:inset-x-8 sm:top-8 sm:flex-row sm:items-start sm:justify-between">
```

and replace:

```tsx
          <p className="mt-2 text-sm font-medium leading-5 text-[#315e58]">{purposeText(state)}</p>
          {home && <p className="mt-0.5 truncate text-xs text-[#54726e]">{home}</p>}
```

with:

```tsx
          <p className="mt-2 text-sm font-medium leading-5 text-[#315e58]">{purposeText(state)}</p>
          {danger && <p className="mt-0.5 text-sm font-semibold text-[#b5473a]" role="status">{danger}</p>}
          {home && <p className="mt-0.5 truncate text-xs text-[#54726e]">{home}</p>}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival`
Expected: `Tests  263 passed (263)` (4 new), the build succeeds, eslint prints nothing.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/survival/types.ts frontend/src/survival/hud.ts frontend/src/survival/hud.test.ts frontend/src/survival/SurvivalHud.tsx frontend/src/survival/replay.ts frontend/src/survival/replay.test.ts frontend/src/survival/animation.ts frontend/src/survival/animation.test.ts
git commit -m "feat: the HUD warns of hostiles near Mimo and flashes when one hits it, and the pet draws its bow" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Viewer: hostiles, arrows and the minimap

**Files:**
- Modify: `frontend/src/survival/creatures.ts` (the gloomling and skitter models, their drops' colors, red minimap dots), `frontend/src/survival/SurvivalCreatures.tsx` (hostile motion), `frontend/src/survival/Minimap.tsx` (draw the red dots), `frontend/src/survival/WorldCanvas.tsx` (mount the combat effects)
- Create: `frontend/src/survival/hostileMotion.ts`, `frontend/src/survival/archery.ts`, `frontend/src/survival/CombatEffects.tsx`
- Test: `frontend/src/survival/creatures.test.ts`, `frontend/src/survival/hostileMotion.test.ts`, `frontend/src/survival/archery.test.ts`

**Interfaces:**
- Consumes: `creatureMotion.lookAt` and its `Look`, `creatures.creatureModel`, `replay.replayAt`, the types of Task 9.
- Produces:
  - `creatures.ts`: models for `gloomling` (17 voxels tall, glowing eyes, arms held out) and `skitter` (6 tall, eight legs, red eyes) on the shared VOXEL grid; `dropColor` for `gloom_dust` and `string`; `CreatureDot.hostile`.
  - `hostileMotion.ts`: `STRIKE_SECONDS = 0.4`, `BURN_SECONDS = 3`, `FLAME_BITS = 5`; `hostileLook(creature, look, t, clock) -> Look` (a lunge at each `struck_at`, a hunch while chasing, a skitter's scuttle, a burning one's flicker as it shrinks) and `flames(creature, t, height)`.
  - `archery.ts`: `RELEASE = 0.6`, `MISS_PAST = 3`; `arrowAt(step, from, t) -> ArrowPose | null` (after the draw, `RELEASE` of the shot, as long as `animation.DRAW_SECONDS` of a 1-second shot; in a low arc from the pet's chest to the target's middle; a miss flies 3 blocks past and drops).
  - `CombatEffects.tsx`: the arrow in flight and the flames over burning hostiles, drawn REPLAY_DELAY behind like the pet. The minimap draws hostiles as red dots.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/survival/creatures.test.ts`, replace:

```ts
    const unknown = creatureModel('gloomling')
```

with:

```ts
    const unknown = creatureModel('dragon')
```

and replace:

```ts
    expect(unknown.scale).toBeCloseTo(VOXEL)
  })
```

with:

```ts
    expect(unknown.scale).toBeCloseTo(VOXEL)
  })
})

describe('hostile models', () => {
  it('draws the gloomling tall with glowing eyes and the skitter low on eight legs, on the shared grid', () => {
    const sizes: Record<string, number> = { gloomling: 1.7, skitter: 0.6 }
    for (const kind of ['gloomling', 'skitter']) {
      const model = creatureModel(kind)
      expect(model.scale).toBeCloseTo(VOXEL)
      expect(height(kind)).toBeCloseTo(sizes[kind])
      expect(attached(model.head, [...model.body, ...model.head])).toBe(true)
      const cells = [...model.body, ...model.head].map(key)
      expect(new Set(cells).size).toBe(cells.length)
    }
    const eyes = creatureModel('gloomling').head.filter((voxel) => voxel.g > 200)
    expect(eyes.length).toBe(2)
    const feet = creatureModel('skitter').body.filter((voxel) => voxel.y === 0)
    expect(new Set(feet.map((voxel) => `${Math.sign(voxel.x)},${voxel.z}`)).size).toBe(8)
    const width = (kind: string) => Math.max(...creatureModel(kind).body.map((voxel) => voxel.x)) - Math.min(...creatureModel(kind).body.map((voxel) => voxel.x))
    expect(width('skitter')).toBeGreaterThan(height('skitter') / VOXEL)
  })
```

and replace:

```ts
    expect(dots).toEqual([{ px: 106.5, py: 86.5, fish: false }, { px: 96.5, py: 96.5, fish: true }])
```

with:

```ts
    expect(dots).toEqual([{ px: 106.5, py: 86.5, fish: false, hostile: false }, { px: 96.5, py: 96.5, fish: true, hostile: false }])
```

Create `frontend/src/survival/hostileMotion.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { Look } from './creatureMotion'
import { BURN_SECONDS, FLAME_BITS, STRIKE_SECONDS, flames, hostileLook } from './hostileMotion'
import type { Creature } from './types'

const still: Look = { lift: 0, pitch: 0, roll: 0, headPitch: 0, flash: 0, knock: 0, size: 1 }
const gloom: Creature = { id: 5, kind: 'gloomling', x: 3, y: 1, z: 0, heading: 0, health: 1, state: 'idle', hostile: true }

describe('hostileLook', () => {
  it('lunges once each time it strikes Mimo and hunches forward while it chases', () => {
    const struck = { ...gloom, state: 'attacking' as const, struck_at: 20 }
    expect(hostileLook(struck, still, 19.9, 0).pitch).toBe(0)
    expect(hostileLook(struck, still, 20 + STRIKE_SECONDS / 2, 0).pitch).toBeCloseTo(0.6)
    expect(hostileLook(struck, still, 20 + STRIKE_SECONDS, 0).pitch).toBeCloseTo(0)
    expect(hostileLook({ ...gloom, state: 'chasing' }, still, 0, 0).pitch).toBeCloseTo(0.15)
  })

  it('makes a skitter scuttle as it goes', () => {
    const skitter: Creature = { ...gloom, kind: 'skitter', state: 'chasing' }
    const rolls = [0, 0.02, 0.04, 0.06].map((clock) => hostileLook(skitter, still, 0, clock).roll)
    expect(Math.max(...rolls.map(Math.abs))).toBeGreaterThan(0.05)
    expect(hostileLook({ ...skitter, state: 'idle' }, still, 0, 0.02).roll).toBe(0)
  })

  it('flickers and shrinks while it burns', () => {
    const burning = { ...gloom, state: 'burning' as const, burning_at: 30 }
    const look = hostileLook(burning, still, 30 + BURN_SECONDS / 2, 1)
    expect(look.flash).toBeGreaterThanOrEqual(0.1)
    expect(look.size).toBeCloseTo(0.7)
    expect(hostileLook(burning, still, 30 + BURN_SECONDS, 1).size).toBeCloseTo(0.4)
  })

  it('leaves animals as they are', () => {
    const cow: Creature = { ...gloom, kind: 'cow', hostile: undefined, state: 'walking', struck_at: 20 }
    expect(hostileLook(cow, still, 20.2, 0)).toBe(still)
  })
})

describe('flames', () => {
  it('rise over a burning creature and nothing else', () => {
    const burning = { ...gloom, state: 'burning' as const, burning_at: 30 }
    const bits = flames(burning, 30.2, 1.7)
    expect(bits.length).toBe(FLAME_BITS)
    expect(bits.every((bit) => bit.y > 0.4 && bit.y < 1.7 * 1.1 && bit.scale > 0 && bit.scale <= 1)).toBe(true)
    expect(flames(gloom, 30.2, 1.7)).toEqual([])
    expect(flames(burning, 29, 1.7)).toEqual([])
  })
})
```

Create `frontend/src/survival/archery.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { MISS_PAST, RELEASE, arrowAt } from './archery'
import type { MimoAction } from './types'

const shot: MimoAction = { kind: 'shoot', started_at: 10, ends_at: 11, target: { x: 8, y: 1, z: 0 }, hit: true }
const pet = { x: 0, y: 1, z: 0 }
const release = 10 + RELEASE

describe('arrowAt', () => {
  it('shows no arrow while the bow is drawn, after it lands, or for any other step', () => {
    expect(arrowAt(shot, pet, 10.3)).toBeNull()
    expect(arrowAt(shot, pet, 11)).toBeNull()
    expect(arrowAt({ ...shot, kind: 'attack' }, pet, 10.8)).toBeNull()
    expect(arrowAt(null, pet, 10.8)).toBeNull()
  })

  it('flies from the pet to its target in a low arc, pointing the way it goes', () => {
    expect(arrowAt(shot, pet, release)).toMatchObject({ x: 0.5, y: 1.8, z: 0.5 })
    const middle = arrowAt(shot, pet, (release + 11) / 2)!
    expect(middle.x).toBeCloseTo(4.5)
    expect(middle.y).toBeGreaterThan(1.7)  // above the straight line from 1.8 to 1.6
    expect(middle.yaw).toBeCloseTo(Math.PI / 2)
    const early = arrowAt(shot, pet, release + 0.01)!
    const late = arrowAt(shot, pet, 10.99)!
    expect(early.pitch).toBeGreaterThan(0)
    expect(late.pitch).toBeLessThan(0)
    expect(late.x).toBeCloseTo(8.5, 0)
  })

  it('flies on past the target and drops when it misses', () => {
    const miss = arrowAt({ ...shot, hit: false }, pet, 10.99)!
    expect(miss.x).toBeGreaterThan(8.5 + MISS_PAST - 0.5)
    expect(miss.y).toBeLessThan(1.3)
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/creatures.test.ts src/survival/hostileMotion.test.ts src/survival/archery.test.ts`
Expected: failures: no hostile models, and the two new modules do not exist.

- [ ] **Step 3: Model the hostiles, and color their dots red**

In `frontend/src/survival/creatures.ts`, replace:

```ts
 * a fish. Each model is two voxel lists, the body and the head, so the head can dip to graze.
```

with:

```ts
 * a fish, and (L2) the hostile gloomling, tall and dark with glowing eyes and its arms held out,
 * and the skitter, low and wide on eight legs with red eyes. Each model is two voxel lists, the
 * body and the head, so the head can dip to graze.
```

and replace:

```ts
const FIN: Color = [250, 196, 120]
```

with:

```ts
const FIN: Color = [250, 196, 120]
const GLOOM: Color = [66, 58, 88]
const GLOOM_DARK: Color = [44, 38, 60]
const GLOW: Color = [170, 238, 255]
const SHELL: Color = [78, 64, 54]
const SHELL_DARK: Color = [54, 44, 38]
const RED_EYE: Color = [226, 70, 62]
```

and replace:

```ts
const SIZES: Record<string, number> = { rabbit: 0.5, chicken: 0.6, sheep: 1.0, cow: 1.3, fish: 0.3 }
const HOPS: Record<string, number> = { rabbit: 0.25, chicken: 0.08, sheep: 0.06, cow: 0.04, fish: 0 }
```

with:

```ts
const SIZES: Record<string, number> = { rabbit: 0.5, chicken: 0.6, sheep: 1.0, cow: 1.3, fish: 0.3, gloomling: 1.7,
  skitter: 0.6 }
const HOPS: Record<string, number> = { rabbit: 0.25, chicken: 0.08, sheep: 0.06, cow: 0.04, fish: 0, gloomling: 0.03,
  skitter: 0.02 }
```

and replace:

```ts
/** A plain grey block for a kind this viewer does not know yet. */
```

with:

```ts
/** L2, 17 voxels tall: long legs, a thin dark body with its arms held out in front, a head with two glowing eyes. */
function gloomling(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().pair(1, [0, 6], [0, 0], GLOOM_DARK).box([-2, 2], [7, 12], [-1, 1], GLOOM)
    .pair(3, [9, 12], [0, 0], GLOOM).pair(3, [9, 9], [1, 4], GLOOM_DARK)
  const head = new Builder().box([-2, 2], [13, 16], [-1, 2], GLOOM).pair(1, [15, 15], [2, 2], GLOW)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 13, z: 0 } }
}

/** L2, 6 voxels tall: a low, wide shell on eight splayed legs, a head with red eyes and fangs. */
function skitter(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-2, 2], [2, 4], [-3, 1], SHELL).box([-1, 1], [5, 5], [-2, 0], SHELL_DARK)
  for (const z of [-2, -1, 0, 1]) body.pair(3, [2, 2], [z, z], SHELL_DARK).pair(4, [0, 1], [z, z], SHELL_DARK)
  const head = new Builder().box([-1, 1], [2, 4], [2, 3], SHELL).pair(1, [4, 4], [3, 3], RED_EYE)
    .pair(1, [1, 1], [3, 3], SHELL_DARK)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 3, z: 2 } }
}

/** A plain grey block for a kind this viewer does not know yet. */
```

and replace:

```ts
const MODELS: Record<string, () => Omit<CreatureModel, 'scale' | 'hop'>> = { rabbit, chicken, sheep, cow, fish }
```

with:

```ts
const MODELS: Record<string, () => Omit<CreatureModel, 'scale' | 'hop'>> = {
  rabbit, chicken, sheep, cow, fish, gloomling, skitter,
}
```

and replace:

```ts
  return ({ leather: [150, 96, 62], wool: WOOL, feather: [250, 250, 246], rabbit_hide: [196, 164, 124] } as Record<string, Color>)[item]
    ?? [180, 180, 180]
```

with:

```ts
  return ({ leather: [150, 96, 62], wool: WOOL, feather: [250, 250, 246], rabbit_hide: [196, 164, 124],
    gloom_dust: [132, 120, 176], string: [236, 236, 230] } as Record<string, Color>)[item] ?? [180, 180, 180]
```

and replace:

```ts
  fish: boolean
}
```

with:

```ts
  fish: boolean
  /** L2: a hostile creature, drawn red. */
  hostile: boolean
}
```

and replace:

```ts
    .map((creature) => ({ ...toMap(creature.x, creature.z, origin), fish: creature.kind === 'fish' }))
```

with:

```ts
    .map((creature) => ({ ...toMap(creature.x, creature.z, origin), fish: creature.kind === 'fish',
      hostile: Boolean(creature.hostile) }))
```

In `frontend/src/survival/Minimap.tsx`, replace:

```tsx
import { creatureDots } from './creatures'
```

with:

```tsx
import { creatureDots, type CreatureDot } from './creatures'
```

and replace:

```tsx
const FISH = '#6fb8d8'
/** Patches this far past the map's edge stay cached, for a walk back. */
```

with:

```tsx
const FISH = '#6fb8d8'
const HOSTILE = '#e0584a'
/** Patches this far past the map's edge stay cached, for a walk back. */
```

and replace:

```tsx
/** A creature (L1): a small cream dot, blue for a fish, about 4 CSS pixels across at any size the map shows. */
function drawCreature(context: CanvasRenderingContext2D, x: number, y: number, fish: boolean): void {
```

with:

```tsx
/** A creature (L1): a small cream dot, blue for a fish and (L2) red for a hostile, about 4 CSS pixels
 * across at any size the map shows. */
function drawCreature(context: CanvasRenderingContext2D, x: number, y: number, dot: CreatureDot): void {
```

and replace:

```tsx
  context.fillStyle = fish ? FISH : ANIMAL
```

with:

```tsx
  context.fillStyle = dot.hostile ? HOSTILE : dot.fish ? FISH : ANIMAL
```

and replace:

```tsx
    for (const dot of creatureDots(creatures, origin)) drawCreature(context, dot.px * MAP_SCALE, dot.py * MAP_SCALE, dot.fish)
```

with:

```tsx
    for (const dot of creatureDots(creatures, origin)) drawCreature(context, dot.px * MAP_SCALE, dot.py * MAP_SCALE, dot)
```

- [ ] **Step 4: Move them like hostiles**

Create `frontend/src/survival/hostileMotion.ts`:

```ts
import type { Look } from './creatureMotion'
import type { Creature, Point } from './types'

/**
 * How the hostile creatures move on top of what every creature does (creatureMotion.lookAt), from
 * the snapshot's `struck_at`, `burning_at` and state (backend/survival/creatures/view.py): a lunge
 * each time one strikes Mimo, a forward hunch while it chases, a skitter's scuttle as it goes, and
 * a burning gloomling's flicker as it shrinks away in the sun, with flames over it.
 */

export const STRIKE_SECONDS = 0.4
/** As long as a gloomling burns before it goes (backend/survival/creatures/hostiles.py BURN_SECONDS). */
export const BURN_SECONDS = 3
export const FLAME_BITS = 5
const FLAME_CYCLE = 0.6

function since(at: number | undefined, t: number): number | null {
  return at === undefined || t < at ? null : t - at
}

/** A hostile's look at server time `t` (`clock` runs on for idle motion); any other creature's comes back as it is. */
export function hostileLook(creature: Creature, look: Look, t: number, clock: number): Look {
  if (!creature.hostile) return look
  const next = { ...look }
  if (creature.state === 'chasing') next.pitch += 0.15
  if (creature.kind === 'skitter' && (creature.state === 'chasing' || creature.state === 'walking')) {
    next.roll += 0.12 * Math.sin(clock * 24)
  }
  const struck = since(creature.struck_at, t)
  if (struck !== null && struck < STRIKE_SECONDS) {
    const lunge = Math.sin((Math.PI * struck) / STRIKE_SECONDS)
    next.pitch += 0.6 * lunge
    next.lift += 0.05 * lunge
  }
  const burning = since(creature.burning_at, t)
  if (creature.state === 'burning' && burning !== null) {
    next.flash = Math.max(next.flash, 0.55 + 0.45 * Math.sin(clock * 20))
    next.size = Math.min(next.size, Math.max(0.2, 1 - (0.6 * burning) / BURN_SECONDS))
  }
  return next
}

/** Flames over a burning creature `height` blocks tall: FLAME_BITS bits rising and shrinking, as
 * offsets from its feet in blocks, with their size (1 at the bottom). None when it is not burning. */
export function flames(creature: Creature, t: number, height: number): (Point & { scale: number })[] {
  const burning = since(creature.burning_at, t)
  if (creature.state !== 'burning' || burning === null) return []
  return Array.from({ length: FLAME_BITS }, (_, index) => {
    const age = ((burning + index * 0.13) % FLAME_CYCLE) / FLAME_CYCLE
    const angle = index * 2.4
    return { x: Math.cos(angle) * 0.25, y: height * (0.3 + 0.8 * age), z: Math.sin(angle) * 0.25, scale: 1 - age }
  })
}
```

In `frontend/src/survival/SurvivalCreatures.tsx`, replace:

```tsx
import { dropPops, drawn, healthBar, lookAt, placeAt, puffAge } from './creatureMotion'
import { mergeMoves, type MoveHistory } from './creatureMoves'
```

with:

```tsx
import { dropPops, drawn, healthBar, lookAt, placeAt, puffAge } from './creatureMotion'
import { hostileLook } from './hostileMotion'
import { mergeMoves, type MoveHistory } from './creatureMoves'
```

and replace:

```tsx
    const look = lookAt(creature, place, t, state.clock.elapsedTime, model.hop)
```

with:

```tsx
    const look = hostileLook(creature, lookAt(creature, place, t, state.clock.elapsedTime, model.hop), t,
      state.clock.elapsedTime)
```

- [ ] **Step 5: Fly the arrow, and burn the hostiles in the sun**

Create `frontend/src/survival/archery.ts`:

```ts
import type { MimoAction, Point } from './types'

/**
 * An arrow in flight (L2). A shot (backend/survival/creatures/archery.py) spends its first
 * RELEASE share drawing the bow; then the arrow flies from the pet to the creature it aimed at in a
 * low arc and lands when the shot ends. A shot that misses (`hit` false) flies on past the target
 * and drops. Cell coordinates; the arrow flies from the pet's chest to the target's middle.
 */

export const RELEASE = 0.6
/** Blocks a missed arrow flies past its target. */
export const MISS_PAST = 3
/** How high the arc rises, per block of flight. */
const ARC = 0.08
const CHEST = 0.8
const MIDDLE = 0.6

export interface ArrowPose extends Point {
  /** Radians around +y: 0 flies toward +z. */
  yaw: number
  /** Radians up from level: positive while it climbs. */
  pitch: number
}

/** Where the arrow of `step` is at server time `t`, shot from `from` (the pet's cell), or null. */
export function arrowAt(step: MimoAction | null, from: Point, t: number): ArrowPose | null {
  if (!step || step.kind !== 'shoot' || !step.target || step.ends_at === null) return null
  const release = step.started_at + (step.ends_at - step.started_at) * RELEASE
  if (t < release || t >= step.ends_at || step.ends_at <= release) return null
  const start = { x: from.x + 0.5, y: from.y + CHEST, z: from.z + 0.5 }
  let end = { x: step.target.x + 0.5, y: step.target.y + MIDDLE, z: step.target.z + 0.5 }
  const across = Math.hypot(end.x - start.x, end.z - start.z) || 1
  if (step.hit === false) {
    const on = (across + MISS_PAST) / across
    end = { x: start.x + (end.x - start.x) * on, y: step.target.y + 0.1, z: start.z + (end.z - start.z) * on }
  }
  const p = (t - release) / (step.ends_at - release)
  const flight = Math.hypot(end.x - start.x, end.z - start.z)
  const rise = ARC * flight
  return {
    x: start.x + (end.x - start.x) * p,
    y: start.y + (end.y - start.y) * p + rise * 4 * p * (1 - p),
    z: start.z + (end.z - start.z) * p,
    yaw: Math.atan2(end.x - start.x, end.z - start.z),
    pitch: Math.atan2(end.y - start.y + rise * 4 * (1 - 2 * p), flight),
  }
}
```

Create `frontend/src/survival/CombatEffects.tsx`:

```tsx
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { arrowAt } from './archery'
import { creatureModel } from './creatures'
import { FLAME_BITS, flames } from './hostileMotion'
import { replayAt } from './replay'
import type { Creature, FinishedAction, MimoAction, Point } from './types'

/** Burning creatures drawn at most (the hostile cap is 8). */
const MOST_BURNING = 8
const SHAFT: [number, number, number] = [0.04, 0.04, 0.7]
const TIP: [number, number, number] = [0.08, 0.08, 0.12]
const FLAME_SIZE = 0.16
const NONE: Creature[] = []

/**
 * L2's fighting, drawn REPLAY_DELAY behind the server like the pet: the arrow of a shot in flight
 * from the pet to its target (archery.ts), and flames over each hostile burning in the sun
 * (hostileMotion.ts; a burning creature stands still, where the snapshot has it). All per-frame
 * work is in useFrame; nothing here sets React state.
 */
export default function CombatEffects({ action, recent, position, creatures = NONE, now }: {
  action: MimoAction | null
  recent: FinishedAction[]
  position: Point
  creatures?: Creature[]
  now: () => number
}) {
  const arrow = useRef<THREE.Group>(null)
  const fire = useRef<THREE.InstancedMesh>(null)
  const scratch = useRef<THREE.Object3D | null>(null)

  useFrame(() => {
    const t = now()
    const flight = arrow.current
    if (flight) {
      const { step, rest } = replayAt(action, recent, position, t)
      const pose = arrowAt(step, rest, t)
      flight.visible = pose !== null
      if (pose) {
        flight.position.set(pose.x, pose.y, pose.z)
        flight.rotation.set(-pose.pitch, pose.yaw, 0, 'YXZ')
      }
    }
    const bits = fire.current
    if (!bits) return
    const dummy = (scratch.current ??= new THREE.Object3D())
    let count = 0
    for (const creature of creatures.filter((found) => found.state === 'burning').slice(0, MOST_BURNING)) {
      const model = creatureModel(creature.kind)
      const ys = [...model.body, ...model.head].map((voxel) => voxel.y)
      const height = (Math.max(...ys) - Math.min(...ys) + 1) * model.scale
      for (const bit of flames(creature, t, height)) {
        dummy.position.set(creature.x + 0.5 + bit.x, creature.y + bit.y, creature.z + 0.5 + bit.z)
        dummy.scale.setScalar(FLAME_SIZE * bit.scale)
        dummy.updateMatrix()
        bits.setMatrixAt(count++, dummy.matrix)
      }
    }
    bits.count = count
    bits.visible = count > 0
    bits.instanceMatrix.needsUpdate = true
  })

  return (
    <>
      <group ref={arrow} visible={false}>
        <mesh>
          <boxGeometry args={SHAFT} />
          <meshLambertMaterial color="#b58a5a" />
        </mesh>
        <mesh position={[0, 0, SHAFT[2] / 2]}>
          <boxGeometry args={TIP} />
          <meshLambertMaterial color="#8e979a" />
        </mesh>
        <mesh position={[0, 0, -SHAFT[2] / 2]}>
          <boxGeometry args={[0.12, 0.02, 0.1]} />
          <meshLambertMaterial color="#f4f1ea" />
        </mesh>
      </group>
      <instancedMesh ref={fire} args={[undefined, undefined, MOST_BURNING * FLAME_BITS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color="#ffa53d" />
      </instancedMesh>
    </>
  )
}
```

In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import ActionEffects from './ActionEffects'
import LeafPuffs from './LeafPuffs'
```

with:

```tsx
import ActionEffects from './ActionEffects'
import CombatEffects from './CombatEffects'
import LeafPuffs from './LeafPuffs'
```

and replace:

```tsx
 * replaying their moves the same REPLAY_DELAY behind the server as the pet.
```

with:

```tsx
 * replaying their moves the same REPLAY_DELAY behind the server as the pet. L2: arrows fly and
 * hostiles burn (CombatEffects).
```

and replace:

```tsx
          {serverTime && <SurvivalCreatures creatures={creatures} moves={creatureMoves} now={replayTime} />}
```

with:

```tsx
          {serverTime && <SurvivalCreatures creatures={creatures} moves={creatureMoves} now={replayTime} />}
          {serverTime && <CombatEffects action={action} recent={recentActions} position={position} creatures={creatures}
            now={replayTime} />}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival`
Expected: `Tests  272 passed (272)` (9 new), the build succeeds, eslint prints nothing.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/survival/creatures.ts frontend/src/survival/creatures.test.ts frontend/src/survival/Minimap.tsx frontend/src/survival/hostileMotion.ts frontend/src/survival/hostileMotion.test.ts frontend/src/survival/SurvivalCreatures.tsx frontend/src/survival/archery.ts frontend/src/survival/archery.test.ts frontend/src/survival/CombatEffects.tsx frontend/src/survival/WorldCanvas.tsx
git commit -m "feat: draw gloomlings and skitters, their strikes and burns, arrows in flight and red dots on the minimap" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Viewer: doors and armor

**Files:**
- Modify: `frontend/src/engine/worldStore.ts` (`placedCells`), `frontend/src/survival/SurvivalPet.tsx` (armor and the hurt glow), `frontend/src/survival/WorldCanvas.tsx` (mount the doors; pass the armor and the hurt on), `frontend/src/survival/SurvivalWorld.tsx` (pass the inventory and `hurt_at`)
- Create: `frontend/src/survival/doors.ts`, `frontend/src/survival/SurvivalDoors.tsx`, `frontend/src/survival/petGear.ts`
- Test: `frontend/src/engine/worldStore.test.ts`, `frontend/src/survival/doors.test.ts`, `frontend/src/survival/petGear.test.ts`

**Interfaces:**
- Consumes: `WorldStore` (server changes, `subscribe`), `blocks.blockDef`, `motion.focusPoint`, `PetVoxels`.
- Produces:
  - `WorldStore.placedCells(name, x, z, radius) -> {x, y, z}[]`: the cells within `radius` blocks (across) where the server placed `name`.
  - `doors.ts`: `HELD_OPEN = 0.6`, `OPEN_REACH = 1.6`; `doorSwing(door, pet) -> number` (0 shut to 1 wide open, for the pet drawn at `pet`) and `doorAxis(solidAt, door) -> 'x' | 'z'`.
  - `SurvivalDoors.tsx`: a two-block plank door in each door cell within 32 blocks (the nearest 8), hinged at one side, swinging open as the drawn pet passes and shutting behind it.
  - `petGear.ts`: `TUNIC_SCALE`, `BODY_MIDDLE`, `HURT_GLOW_SECONDS = 0.4`; `tunicVoxels(inventory)`, `capVoxels(inventory)`, `hurtGlow(hurtAt, t) -> number`.
  - `SurvivalPet` takes `tunic`, `cap` and `hurtAt`; `WorldCanvas` takes `inventory` and `hurtAt`.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/engine/worldStore.test.ts`, replace:

```ts
    expect(store.getBlock(3, 30, 3)).toBe(blockId('stone'))
  })
```

with:

```ts
    expect(store.getBlock(3, 30, 3)).toBe(blockId('stone'))
  })

  it('finds the cells where the server placed a block near a spot', () => {
    const store = new WorldStore()
    store.applyServerChanges([
      { x: 3, y: 1, z: 4, material: 'door' }, { x: 40, y: 1, z: 0, material: 'door' }, { x: 3, y: 2, z: 4, material: 'air' },
    ])
    expect(store.placedCells('door', 0, 0, 32)).toEqual([{ x: 3, y: 1, z: 4 }])
    expect(store.placedCells('bed', 0, 0, 32)).toEqual([])
  })
```

Create `frontend/src/survival/doors.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { HELD_OPEN, OPEN_REACH, doorAxis, doorSwing } from './doors'

const door = { x: 4, y: 1, z: 7 }

describe('doors', () => {
  it('opens wide as the pet passes through and shuts behind it', () => {
    expect(doorSwing(door, { x: 4, y: 1, z: 7 })).toBe(1)
    expect(doorSwing(door, { x: 4, y: 1, z: 7 - HELD_OPEN })).toBe(1)
    expect(doorSwing(door, { x: 4, y: 1, z: 8.1 })).toBeCloseTo(0.5)
    expect(doorSwing(door, { x: 4, y: 1, z: 7 + OPEN_REACH })).toBeCloseTo(0)
    expect(doorSwing(door, { x: 4, y: 4, z: 7 })).toBe(0)
    expect(doorSwing(door, null)).toBe(0)
  })

  it('lies along the wall it stands in', () => {
    const wallAlongX = (x: number, _y: number, z: number) => z === 7 && x !== 4
    const wallAlongZ = (x: number, _y: number, z: number) => x === 4 && z !== 7
    expect(doorAxis(wallAlongX, door)).toBe('x')
    expect(doorAxis(wallAlongZ, door)).toBe('z')
  })
})
```

Create `frontend/src/survival/petGear.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { previewPet } from '../components/world/previewWorld'
import { HURT_GLOW_SECONDS, capVoxels, hurtGlow, tunicVoxels } from './petGear'

const key = (voxel: { x: number; y: number; z: number }) => `${voxel.x},${voxel.y},${voxel.z}`

describe('petGear', () => {
  it('puts a tunic over the body and a cap on the head only when Mimo carries them', () => {
    expect(tunicVoxels({})).toEqual([])
    expect(capVoxels(undefined)).toEqual([])
    const body = new Set(previewPet.voxels.filter((voxel) => voxel.y <= 1 && voxel.z >= -1 && voxel.z <= 0).map(key))
    expect(new Set(tunicVoxels({ leather_tunic: 1 }).map(key))).toEqual(body)
    const cap = capVoxels({ leather_cap: 1 })
    const pet = new Set(previewPet.voxels.map(key))
    expect(cap.length).toBe(4)
    expect(cap.some((voxel) => pet.has(key(voxel)))).toBe(false)  // it sits on the head, around the ears
    expect(cap.every((voxel) => voxel.y === 4)).toBe(true)
  })

  it('glows red at once after a blow and fades', () => {
    expect(hurtGlow(undefined, 10)).toBe(0)
    expect(hurtGlow(10, 9.9)).toBe(0)
    expect(hurtGlow(10, 10)).toBe(1)
    expect(hurtGlow(10, 10 + HURT_GLOW_SECONDS / 2)).toBeCloseTo(0.5)
    expect(hurtGlow(10, 10 + HURT_GLOW_SECONDS)).toBe(0)
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/engine/worldStore.test.ts src/survival/doors.test.ts src/survival/petGear.test.ts`
Expected: failures: `placedCells` does not exist and neither do the two new modules.

- [ ] **Step 3: Find the doors, and swing them open for the pet**

In `frontend/src/engine/worldStore.ts`, replace:

```ts
  /** Names of server-placed blocks within `radius` of (x, z), for workstation checks. */
```

with:

```ts
  /** The cells within `radius` blocks (across) of (x, z) where the server placed `name` (L2: doors). */
  placedCells(name: string, x: number, z: number, radius: number): { x: number; y: number; z: number }[] {
    const id = blockId(name)
    const found: { x: number; y: number; z: number }[] = []
    for (const cells of this.server.values()) {
      for (const [cell, value] of cells) {
        if (value !== id) continue
        const [bx, by, bz] = cell.split(',').map(Number)
        if (Math.hypot(bx - x, bz - z) <= radius) found.push({ x: bx, y: by, z: bz })
      }
    }
    return found
  }

  /** Names of server-placed blocks within `radius` of (x, z), for workstation checks. */
```

Create `frontend/src/survival/doors.ts`:

```ts
import type { Point } from './types'

/**
 * Doors (L2). A door block (shared/blocks.json, layer "none") is not meshed: the viewer draws a
 * plank door in its cell itself (SurvivalDoors.tsx), two blocks tall to fill the shelter's door gap,
 * hinged at one side, that swings open while the drawn pet passes through and shuts behind it.
 */

/** Blocks (across) from the door's cell within which the pet holds it wide open. */
export const HELD_OPEN = 0.6
/** Blocks (across) from which the door starts to open as the pet comes. */
export const OPEN_REACH = 1.6
/** Blocks up or down the pet may be and still open it. */
const LEVEL = 1.5

/** How far a door stands open, 0 (shut) to 1 (wide), for the pet drawn at `pet` (cell coordinates). */
export function doorSwing(door: Point, pet: Point | null): number {
  if (!pet || Math.abs(pet.y - door.y) > LEVEL) return 0
  const distance = Math.hypot(pet.x - door.x, pet.z - door.z)
  if (distance >= OPEN_REACH) return 0
  if (distance <= HELD_OPEN) return 1
  return (OPEN_REACH - distance) / (OPEN_REACH - HELD_OPEN)
}

/** The axis a door's panel lies along: x when a wall stands east or west of it, else z. */
export function doorAxis(solidAt: (x: number, y: number, z: number) => boolean, door: Point): 'x' | 'z' {
  return solidAt(door.x - 1, door.y, door.z) || solidAt(door.x + 1, door.y, door.z) ? 'x' : 'z'
}
```

Create `frontend/src/survival/SurvivalDoors.tsx`:

```tsx
import { useEffect, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { blockDef } from '../engine/blocks'
import type { WorldStore } from '../engine/worldStore'
import { doorAxis, doorSwing } from './doors'
import type { Point } from './types'

/** Doors drawn at most, the nearest first, and how far from the pet they are looked for. */
const MOST_DOORS = 8
const DOOR_REACH = 32
/** Seconds between looks for doors when nothing changed in the store. */
const LOOK_EVERY = 2
const PANEL: [number, number, number] = [1, 2, 0.12]
const PLANK = '#8f6a45'
const TRIM = '#6b4a2e'

interface Door {
  cell: Point
  axis: 'x' | 'z'
}

/**
 * The doors near the pet (L2): a two-block plank door in each door block's cell (the mesher draws
 * none, shared/blocks.json layer "none"), hinged on one side and swinging open while the pet drawn
 * at `pet()` passes (doors.ts); in an archive, with no pet to replay, they stay shut. The doors are
 * looked up again when the store changes or every LOOK_EVERY seconds, all inside useFrame.
 */
export default function SurvivalDoors({ store, focus, pet }: {
  store: WorldStore
  focus: Point
  pet?: () => Point | null
}) {
  const hinges = useRef<(THREE.Group | null)[]>([])
  const doors = useRef<Door[]>([])
  const looked = useRef({ dirty: true, at: -Infinity })

  useEffect(() => store.subscribe(() => { looked.current.dirty = true }), [store])

  useFrame((state) => {
    const clock = state.clock.elapsedTime
    if (looked.current.dirty || clock - looked.current.at > LOOK_EVERY) {
      const solidAt = (x: number, y: number, z: number) => blockDef(store.getBlock(x, y, z)).solid
      doors.current = store.placedCells('door', focus.x, focus.z, DOOR_REACH)
        .sort((a, b) => Math.hypot(a.x - focus.x, a.z - focus.z) - Math.hypot(b.x - focus.x, b.z - focus.z))
        .slice(0, MOST_DOORS)
        .map((cell) => ({ cell, axis: doorAxis(solidAt, cell) }))
      looked.current = { dirty: false, at: clock }
    }
    const drawn = pet?.() ?? null
    hinges.current.forEach((hinge, index) => {
      if (!hinge) return
      const door = doors.current[index]
      hinge.visible = door !== undefined
      if (!door) return
      const { x, y, z } = door.cell
      const swing = doorSwing(door.cell, drawn) * (Math.PI / 2)
      if (door.axis === 'x') {
        hinge.position.set(x, y, z + 0.5)
        hinge.rotation.y = swing
      } else {
        hinge.position.set(x + 0.5, y, z)
        hinge.rotation.y = -Math.PI / 2 + swing
      }
    })
  })

  return (
    <>
      {Array.from({ length: MOST_DOORS }, (_, index) => (
        <group key={index} ref={(group) => { hinges.current[index] = group }} visible={false}>
          <mesh position={[PANEL[0] / 2, PANEL[1] / 2, 0]}>
            <boxGeometry args={PANEL} />
            <meshStandardMaterial color={PLANK} roughness={0.8} />
          </mesh>
          <mesh position={[PANEL[0] / 2, PANEL[1] / 2, 0]}>
            <boxGeometry args={[PANEL[0] * 0.92, 0.08, PANEL[2] + 0.02]} />
            <meshStandardMaterial color={TRIM} roughness={0.8} />
          </mesh>
          <mesh position={[PANEL[0] - 0.16, 1.0, PANEL[2] / 2 + 0.03]}>
            <boxGeometry args={[0.06, 0.06, 0.06]} />
            <meshStandardMaterial color="#d8c08a" metalness={0.3} />
          </mesh>
        </group>
      ))}
    </>
  )
}
```

- [ ] **Step 4: Dress the pet in its armor, and let it glow when hit**

Create `frontend/src/survival/petGear.ts`:

```ts
import type { Voxel } from '../types/world'

/**
 * What the pet wears and how a blow shows on it (L2). Mimo wears the armor it carries: a leather
 * tunic over its body and a leather cap between its ears, in the pet model's voxel units
 * (components/world/previewWorld.ts: the body fills x -1..1, y 0..1, z -1..0 and the head x -1..1,
 * y 2..3, z 0..1, with the ears at x -1 and 1, y 4..5, z 0). The tunic is drawn a little larger
 * than the body (TUNIC_SCALE around BODY_MIDDLE) so it sits on the fur.
 */

type Color = readonly [number, number, number]

const LEATHER: Color = [150, 96, 62]
const STITCH: Color = [112, 70, 44]
export const TUNIC_SCALE = 1.12
/** The middle of the body, in voxel units, that the tunic is scaled around. */
export const BODY_MIDDLE: [number, number, number] = [0.5, 1, 0]
/** How long the pet glows red after a blow, in seconds. */
export const HURT_GLOW_SECONDS = 0.4

function voxel(x: number, y: number, z: number, [r, g, b]: Color): Voxel {
  return { x, y, z, r, g, b, a: 255 }
}

/** The tunic's voxels when Mimo carries a leather tunic, else none; a darker belt along the bottom. */
export function tunicVoxels(inventory: Record<string, number> | null | undefined): Voxel[] {
  if ((inventory?.leather_tunic ?? 0) < 1) return []
  const voxels: Voxel[] = []
  for (let x = -1; x <= 1; x++) {
    for (const z of [-1, 0]) {
      voxels.push(voxel(x, 0, z, STITCH), voxel(x, 1, z, LEATHER))
    }
  }
  return voxels
}

/** The cap's voxels when Mimo carries a leather cap, else none: on top of the head, around the ears. */
export function capVoxels(inventory: Record<string, number> | null | undefined): Voxel[] {
  if ((inventory?.leather_cap ?? 0) < 1) return []
  return [voxel(0, 4, 0, LEATHER), voxel(0, 4, 1, LEATHER), voxel(-1, 4, 1, STITCH), voxel(1, 4, 1, STITCH)]
}

/** How red the pet glows (0..1) at server time `t` after a blow at `hurtAt`: at once, then fading. */
export function hurtGlow(hurtAt: number | null | undefined, t: number): number {
  if (hurtAt === null || hurtAt === undefined || t < hurtAt || t >= hurtAt + HURT_GLOW_SECONDS) return 0
  return 1 - (t - hurtAt) / HURT_GLOW_SECONDS
}
```

In `frontend/src/survival/SurvivalPet.tsx`, replace:

```tsx
import { useRef, type ReactNode } from 'react'
```

with:

```tsx
import { useMemo, useRef, type ReactNode } from 'react'
```

and replace:

```tsx
import { bodyPose, crumbs, moveFor, zPuffs } from './animation'
import { poseAt, turnToward } from './motion'
```

with:

```tsx
import { bodyPose, crumbs, moveFor, zPuffs } from './animation'
import { BODY_MIDDLE, TUNIC_SCALE, capVoxels, hurtGlow, tunicVoxels } from './petGear'
import { poseAt, turnToward } from './motion'
```

and replace:

```tsx
const NO_STEPS: FinishedAction[] = []
```

with:

```tsx
const NO_STEPS: FinishedAction[] = []
const UNDER_BODY: [number, number, number] = [-BODY_MIDDLE[0], -BODY_MIDDLE[1], -BODY_MIDDLE[2]]
const GLOW_COLOR = '#e0463a'
```

and replace:

```tsx
 * and plays the step's animation. Cheap on phones: no React state changes per frame, a handful of
 * meshes, and all per-frame work in one useFrame.
```

with:

```tsx
 * and plays the step's animation. L2: it wears the leather tunic and cap it carries (`tunic`,
 * `cap`) and glows red for a moment when a creature hits it (`hurtAt`, server time). Cheap on
 * phones: no React state changes per frame, a handful of meshes, and all per-frame work in one
 * useFrame.
```

and replace:

```tsx
export default function SurvivalPet({ action, recent = NO_STEPS, position, now, onPetClick, hopSignal = 0, hidden, children }: {
```

with:

```tsx
export default function SurvivalPet({ action, recent = NO_STEPS, position, now, onPetClick, hopSignal = 0, hidden,
  tunic = false, cap = false, hurtAt = null, children }: {
```

and replace:

```tsx
  hidden?: () => boolean
  children?: ReactNode
```

with:

```tsx
  hidden?: () => boolean
  tunic?: boolean
  cap?: boolean
  hurtAt?: number | null
  children?: ReactNode
```

and replace:

```tsx
  const drawn = useRef(true)
```

with:

```tsx
  const drawn = useRef(true)
  const glow = useRef<THREE.Mesh>(null)
  const glowMaterial = useRef<THREE.MeshBasicMaterial>(null)
  const tunicParts = useMemo(() => tunicVoxels(tunic ? { leather_tunic: 1 } : {}), [tunic])
  const capParts = useMemo(() => capVoxels(cap ? { leather_cap: 1 } : {}), [cap])
```

and replace:

```tsx
    }
  })
```

with:

```tsx
    }
    const red = hurtGlow(hurtAt, t)
    if (glow.current) glow.current.visible = show && red > 0
    if (glowMaterial.current) glowMaterial.current.opacity = 0.45 * red
  })
```

and replace:

```tsx
          <PetVoxels voxels={previewPet.voxels} />
          {children}
```

with:

```tsx
          <PetVoxels voxels={previewPet.voxels} />
          {tunicParts.length > 0 && (
            <group position={BODY_MIDDLE} scale={TUNIC_SCALE}>
              <group position={UNDER_BODY}>
                <PetVoxels voxels={tunicParts} />
              </group>
            </group>
          )}
          {capParts.length > 0 && <PetVoxels voxels={capParts} />}
          {children}
```

and replace:

```tsx
        </group>
      </group>
```

with:

```tsx
        </group>
        <mesh ref={glow} position={[0, 0.95, 0.1]} visible={false}>
          <boxGeometry args={[1.1, 1.95, 1.1]} />
          <meshBasicMaterial ref={glowMaterial} color={GLOW_COLOR} transparent opacity={0} depthWrite={false} />
        </mesh>
      </group>
```

- [ ] **Step 5: Mount them**

In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import SurvivalCreatures from './SurvivalCreatures'
import SurvivalPet from './SurvivalPet'
```

with:

```tsx
import SurvivalCreatures from './SurvivalCreatures'
import SurvivalDoors from './SurvivalDoors'
import SurvivalPet from './SurvivalPet'
```

and replace:

```tsx
 * replaying their moves the same REPLAY_DELAY behind the server as the pet. L2: arrows fly and
 * hostiles burn (CombatEffects).
```

with:

```tsx
 * replaying their moves the same REPLAY_DELAY behind the server as the pet. L2: the doors Mimo
 * built swing open as the drawn pet passes, arrows fly and hostiles burn (CombatEffects), and the
 * pet wears the armor in `inventory` and glows red when a creature hits it (`hurtAt`).
```

and replace:

```tsx
creatures, creatureMoves, serverTime, cameraMode = 'overview', onAutoPick }: {
```

with:

```tsx
creatures, creatureMoves, inventory, hurtAt = null, serverTime, cameraMode = 'overview', onAutoPick }: {
```

and replace:

```tsx
  creatureMoves?: CreatureMove[]
  serverTime?: () => number
```

with:

```tsx
  creatureMoves?: CreatureMove[]
  /** What Mimo carries (L2: the armor it wears) and when a creature last hurt it. */
  inventory?: Record<string, number>
  hurtAt?: number | null
  serverTime?: () => number
```

and replace:

```tsx
  const petHidden = useCallback(() => view.current.petHidden, [])
```

with:

```tsx
  const petHidden = useCallback(() => view.current.petHidden, [])
  // Where the drawn pet is, for the doors it opens (L2).
  const petAt = useCallback(() => {
    const pose = stepAt()
    return focusPoint(pose.step, pose.rest, pose.t)
  }, [stepAt])
```

and replace:

```tsx
            hopSignal={hopSignal} hidden={petHidden}>
```

with:

```tsx
            hopSignal={hopSignal} hidden={petHidden} tunic={(inventory?.leather_tunic ?? 0) > 0}
            cap={(inventory?.leather_cap ?? 0) > 0} hurtAt={hurtAt}>
```

and replace:

```tsx
            now={replayTime} />}
          <FollowCamera
```

with:

```tsx
            now={replayTime} />}
          <SurvivalDoors store={store} focus={position} pet={serverTime ? petAt : undefined} />
          <FollowCamera
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
        creatures={state.creatures} creatureMoves={state.creature_moves}
```

with:

```tsx
        creatures={state.creatures} creatureMoves={state.creature_moves} inventory={state.inventory} hurtAt={state.hurt_at}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  277 passed (277)` (5 new), the build succeeds, eslint prints nothing.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/engine/worldStore.ts frontend/src/engine/worldStore.test.ts frontend/src/survival/doors.ts frontend/src/survival/doors.test.ts frontend/src/survival/SurvivalDoors.tsx frontend/src/survival/petGear.ts frontend/src/survival/petGear.test.ts frontend/src/survival/SurvivalPet.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/survival/SurvivalWorld.tsx
git commit -m "feat: doors that swing open as Mimo passes, and armor and a hurt glow on the pet" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Manual check on the demo and the README

This task is for the controller. It rebuilds the demo image from the branch and restarts the demo stack on its own scratch volume: `mimo-m5demo-api` (:8011) and `mimo-m5demo-worker`, volume `mimo_m5demo`, a copy of the owner's world at the natural pace (`MIMO_TIME_SCALE=1`, `MIMO_ACTION_SCALE=1`, as the owner asked), with no model key, so the utility picker chooses. The owner's real stack (`pets-api-1`, `pets-mimo-worker-1`) and its volume `pets_mimo_data` are never touched, and no key is printed. The viewer runs on :3000 (:5173 is the owner's dev server). A game day is an hour at the natural pace and its night about 20 minutes, so the checks below take an evening: note the time of dusk from the HUD's sky dial. If a check fails, fix the code in the task that owns it, re-run that task's tests, rebuild and repeat the check.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 753 tests` … `OK`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  277 passed (277)`, the build succeeds, eslint prints nothing.

- [ ] **Step 2: Rebuild the demo on the branch**

```bash
docker build -f backend/Dockerfile -t mimo-m5demo .
docker rm -f mimo-m5demo-api mimo-m5demo-worker
docker run -d --name mimo-m5demo-api -p 127.0.0.1:8011:8000 -v mimo_m5demo:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 mimo-m5demo
docker run -d --name mimo-m5demo-worker -v mimo_m5demo:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 -e MIMO_ACTION_SCALE=1 \
  -e MIMO_TICK_SECONDS=1 mimo-m5demo python -m backend.workers.mimo_worker
```

Expected: two container ids. L2 adds no table: the demo world reads as it is, and its shelter gets a door the next time Mimo works on it (build_shelter furnishes it).

Start the viewer against it (or, when a viewer already runs on :3000 against :8011, restart it so it picks up the branch's frontend) and open `http://localhost:3000/preview` in the Browser pane.

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8011 npm run dev -- --port 3000 --strictPort
```

- [ ] **Step 3: Keep a danger snippet and two nudges ready**

Save these in your scratchpad directory (not in the repo). `danger.sh` prints the phase, the pet's health and what hurt it last, its armor and weapons, the hostiles near it (what each does, how far it is, and the light where it came out and how far that is from the nearest torch), the doors near home and the latest danger events:

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
import math, time
from backend.survival.clock import clock_at, is_night, time_scale
from backend.survival.creatures.harm import armor_cut
from backend.survival.creatures.kinds import kind_of
from backend.survival.grid import world_grid
from backend.survival.light import light_at
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
state = world.state()
clock = clock_at(state["born_at"], time.time(), time_scale())
night = is_night(clock["phase"])
x, y, z = (round(state["position"][axis]) for axis in "xyz")
print("phase", clock["phase"], "| health", round(state["vitals"]["health"], 1), "| hurt by", state.get("hurt_by"),
      "| armor cut", armor_cut(state["inventory"]), "| reflex", (state.get("brain") or {}).get("reflex"))
gear = ("_sword", "bow", "arrow", "leather", "string", "flint", "gloom_dust", "rabbit_hide", "feather")
print("carries", {item: count for item, count in state["inventory"].items() if any(part in item for part in gear)})
with world.connect() as db:
    grid = world_grid(db, state["world_seed"])
    torches = [cell for cell, _ in grid.placed_cells(x, z, 96, ("torch",))]
    for creature in grid.herd.near(x, z, 64):
        kind = kind_of(creature["kind"])
        if kind is None or not kind.hostile or creature["state"].get("pose") == "dead":
            continue
        home = tuple(creature["state"]["home"])
        torch = min((sum(abs(a - b) for a, b in zip(home, cell)) for cell in torches), default=None)
        print(creature["kind"], creature["state"].get("pose"), "chasing" if creature["state"].get("chasing") else "",
              "| distance", round(math.dist((creature["x"], creature["y"], creature["z"]), (x, y, z)), 1),
              "| light where it came out", light_at(grid, state["world_seed"], home, night), "| nearest torch", torch)
    print("doors", [cell for cell, _ in grid.placed_cells(x, z, 96, ("door",))])
for event in reversed(world.events(300)):
    if event["kind"] in ("hurt", "fight", "threat", "reflex", "death") or "leather" in event["text"] \
            or "bow" in event["text"] or "arrow" in event["text"] or "door" in event["text"]:
        print(event["kind"], "|", event["text"])
PY
```

`gear.sh` is a nudge for the bow and armor checks when the pet has not made them by then (a bow needs string from skitters, and flint needs gravel, which the terrain does not have until L3): it puts a bow, 8 arrows, a leather cap and a leather tunic in the pet's arms. `flee.sh` is a nudge for the flee check when the pet is armed and healthy: it sets its health to 30 (below flee's 35) so it runs from the next hostile that comes. Note each nudge you use.

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    for item, count in {"bow": 1, "arrow": 8, "leather_cap": 1, "leather_tunic": 1}.items():
        state["inventory"][item] = max(state["inventory"].get(item, 0), count)
    write_state(db, state)
print("geared up")
PY
```

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    state["vitals"]["health"] = 30.0
    write_state(db, state)
print("health 30")
PY
```

- [ ] **Step 4: A night with gloomlings**

From dusk, run `danger.sh` every few minutes. Confirm hostiles appear after dark, never more than 8, gloomlings on open ground and skitters (and some gloomlings) in caves; by day at most a few, all in caves. In the viewer, confirm: a gloomling is tall and dark with two glowing eyes and its arms held out, a skitter low and brown on eight legs with red eyes, both at their sizes beside the pet and on the ground. A chasing one leans forward and comes two blocks at a time; a skitter scuttles. The HUD shows the danger line (`A gloomling is close!`) under the purpose line while one is within 12 blocks, and the minimap shows red dots. Mimo, at home, sleeps behind its door: gloomlings gather outside and wait at the wall, and none strikes it indoors (`danger.sh` shows no `hurt` events while it sleeps). At dawn, confirm a gloomling left under the open sky catches fire, flickers and shrinks with flames rising over it and is gone after about 3 seconds, without drops.

- [ ] **Step 5: Torches keep the yard safe**

Confirm the shelter's corner torches are lit after dusk (M5's light_up). In `danger.sh`, every hostile's "light where it came out" is 7 or less and its "nearest torch" is 7 or more blocks: none came out in the lit yard around the shelter.

- [ ] **Step 6: The door**

Confirm `danger.sh` lists a door in the shelter's door gap (if not yet, wait for build_shelter to furnish it; the step line reads `Placing`). In the viewer, confirm a plank door fills the lower cell of the gap (drawn two blocks tall), swings open as the pet walks in at dusk or out in the morning, and shuts behind it. Confirm no creature ever stands inside the shelter.

- [ ] **Step 7: A fight**

Watch the pet meet a hostile outside with a sword (at dusk on its way home, or in the morning before the last ones burn). Confirm: the HUD reads `Fighting back!`, the pet lunges at the hostile (`Attacking`), the hostile flashes red with a health bar over it, and when it dies it tips over and puffs away with its drops (gloom dust or string) popping out. When a hostile strikes the pet, it lunges, the pet glows red for a moment, the screen's edges flash red and the health bar drops. `danger.sh` prints `reflex | <name> stood its ground against a creature.` once for the encounter and `fight | <name> fought off a gloomling.`

- [ ] **Step 8: A bow shot**

If the pet carries no bow and arrows, run `gear.sh` once and note it. Wait for a hostile to come for the pet from 5 blocks or more. Confirm: the pet leans back to draw (`Shooting`), an arrow flies in a low arc from its chest to the hostile, a hit flashes the target and a miss flies on past it and drops, and the pet's arrows go down by one a shot.

- [ ] **Step 9: Armor**

With a leather cap and tunic in its arms (made by make gear, `crafted leather cap` in `danger.sh`, or from `gear.sh`), confirm the pet wears a brown tunic over its body and a cap between its ears, and `danger.sh` prints `armor cut 0.2`.

- [ ] **Step 10: A flee**

When a hostile comes for the pet outdoors, confirm the pet runs if it is unarmed or below 35 health; if it is armed and healthy, run `flee.sh` once as a hostile approaches and note it. Confirm: the HUD reads `Running away!`, the pet runs home (or away from the hostile) faster than the hostile follows, and it ends up safe, indoors or far off; `danger.sh` prints `reflex | <name> ran from a creature.` once for the encounter.

- [ ] **Step 11: A quiet worker**

Confirm the worker log stays quiet: `docker logs mimo-m5demo-worker 2>&1 | grep -c "crashed"` prints `0` (or only lines from before the restart). Leave the demo running on the new image for the owner.

- [ ] **Step 12: Describe danger and combat in the README**

In `README.md`, replace:

```markdown
## Current world rules
```

with:

```markdown
## Danger and combat

- **Light.** Every cell has a light level from 0 to 15: 15 under the open sky by day and 4 at night, 0 in caves, tunnels and roofed rooms, and near a torch (14), a lantern (15), a campfire or a furnace (13) that level less one per block. Nothing stores it; the server works it out when it needs it (`backend/survival/light.py`).
- **Hostile creatures** come out where the light is 7 or less, 16 to 40 blocks from Mimo and never in anything it built: gloomlings on dark ground at night and in caves, skitters in caves and covered places. At most 8 are about. A gloomling (20 health, slow) strikes for 3 every 1.2 s and a skitter (12 health, fast) for 2 every second. They chase Mimo within 16 blocks and give up past 24, and none passes a door, so Mimo's shelter keeps them out and its torches keep the yard around it safe. By day a gloomling under the open sky burns and fades and a skitter there fades at once; hostiles far from Mimo, or that have not come after it for two game minutes, go too. Gloomlings drop gloom dust (for later) and skitters string.
- **Health.** A blow takes its damage from Mimo's health, 20 % less with a leather cap and tunic, and Mimo remembers where it was hurt. It heals 1 health a game minute while fed and warm. A blow that takes its last health ends the life: "Pip was caught by a gloomling on day 3."
- **Fighting back.** Armed and healthy, Mimo fights a hostile within 4 blocks: with its best sword in reach, or with its bow from 5 blocks on (and at a hostile coming for it within 12, in plain sight). Unarmed with one within 6, or below 35 health, it runs home, or away. Both are reflexes, like surfacing or eating in a hurry, and log one event an encounter. The first hostile to come for Mimo asks for a new choice at once.
- **Gear.** A bow takes 3 sticks and 3 string, and 1 flint, 1 stick and 1 feather make 4 arrows (1 mined gravel in 8 gives flint). A shot takes a second, reaches 16 blocks, always hits within 4 and 1 time in 2 at 16, and does 5 damage. A leather cap takes 2 leather and a tunic 3 (4 rabbit hides make 1 leather), at a crafting table. Make gear makes the missing armor, then a bow with arrows, then more arrows, and the chest leaves what they take in Mimo's arms.
- **Doors.** A door takes 6 planks. Every shelter gets one in its door gap, older ones too. Mimo walks through it and creatures never do, and a creature inside when it goes in is put out.
- `/api/mimo` marks hostile creatures (`hostile`; `chasing`, `attacking` or `burning`; when one last struck Mimo or caught fire) and says when a creature last hurt Mimo (`hurt_at`, `hurt_by`); the model's payload gets `threats` and `defense`. The viewer draws gloomlings and skitters, their lunges and burns, arrows in flight, doors swinging open for the pet and the armor it wears; the HUD warns "A gloomling is close!" and flashes red at a blow, and hostiles are red dots on the minimap.

## Current world rules
```

- [ ] **Step 13: Commit**

```bash
git add README.md
git commit -m "docs: describe danger and combat" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (L2 outline) | Where |
|-------------------|-------|
| gloomling: 20 health, slow, melee 3 every 1.2 s, spawns on dark surface cells at night and in caves, burns and fades at dawn under the open sky, drops gloom_dust | Task 3 (`hostiles`: the kind, `sunlit`, `strike`; resolutions 4, 6), Task 7 (`darkness`; resolution 5) |
| skitter: 12 health, fast, melee 2, caves and dark places, 0–2 string | Task 3 (the kind; resolution 4), Task 7 (covered cells spawn skitters three times in five) |
| Light levels: sky 15 by day, 4 at night, 0 underground; torch 14, lantern 15, campfire 13, one less per block (Manhattan), on demand in a bounded radius | Task 2 (`light`; resolution 3) |
| Spawn only at light 7 or less, 16–40 blocks from Mimo, never in a claimed shelter room | Task 7 (`spawn_hostiles`, `spots`; resolution 5) |
| Hostile AI: chase within 16, attack in reach with a cooldown, give up past 24, despawn beyond 64 or at dawn | Task 3 (`chase`, `strike`, `prowl`, `sunlit`; resolution 7), Task 7 (`despawn_far`; resolution 6) |
| Mimo's health: regen 1 per game minute while fed | Task 3 (`vitals.HEAL_RATE`; resolution 8) |
| Creature damage; damage flashes in the viewer; the HUD's danger line | Task 3 (`harm.hurt_pet`), Task 8 (`hurt_at` in the stream), Task 9 (`dangerText`, the HUD flash), Task 11 (the pet's glow) |
| flee (30): health below 35, or a hostile within 6 and no weapon; runs home or away and ends up safe | Task 6 (`defense`, flee; resolution 14), Task 7 (the whole brain in the tick outruns a gloomling) |
| fight (40): a hostile within 4, health 50 or more, a weapon; the sword, or the bow at 5 or more with arrows; both are registry data | Task 6 (`defense`, fight; resolution 14), Task 7 (an armed pet fights one off in the tick) |
| Melee attack step with swords | L1's `attack` step; Task 3 (a hostile kill is a fight: `combat.spoils`) |
| Bow: 3 sticks and 3 string; arrows: 1 flint, 1 stick, 1 feather make 4; flint from gravel 1 in 8 | Task 4 (recipes, `nature.CHANCE_DROPS`; resolution 12) |
| `shoot(creature_id)`: 1.0 s, range 16, hit chance falls with distance, 5 damage, the arrow flies in an arc and is used up | Task 4 (`archery`; resolution 12), Task 10 (`arrowAt`, `CombatEffects`) |
| Armor: leather cap and tunic cut damage by 20 %; the pet model shows it (iron, 45 %, is L3) | Task 3 (`harm.ARMOR`), Task 5 (recipes, make_gear; resolution 13), Task 11 (`petGear`) |
| Door: 6 planks; the M5 generator places one in the door gap; Mimo passes, creatures do not; the viewer draws it open while Mimo passes | Task 1 (the block, `with_door`, furnishing, `past_doors`, eviction; resolution 11), Task 11 (`doors`, `SurvivalDoors`) |
| Death by a creature on the memorial ("was caught by a gloomling on day 3") | Task 7 (`tick.caught`, `death_words`; resolution 9), Task 9 (`lifeLine`) |
| Mimo remembers danger places | Task 3 (`hurt_pet` remembers a `danger` place noted with the kind) |
| `threats` in the model payload | Task 8 (`threats_payload`; resolution 15), Task 6 (`threats`) |
| Viewer: hostile models and animations, arrows, armor, the door opening, hostile dots on the minimap | Tasks 10 and 11 (resolution 18) |
| Decisions: original creatures and names; light keeps monsters away and torches keep the yard safe; weapons like Minecraft through the same recipe and portable-station system; a door Mimo walks through and creatures cannot; health matters | Tasks 1–5, 10; resolutions 3, 11, 12, 13 |
| Performance: creature simulation plus light checks within 20 ms per 60-game-second slice, at most 24 passive and 8 hostile creatures active | Task 7 (`HOSTILE_CAP`, `test_hostiles_come_out_at_night_stay_few_and_cost_little`, L1's cost tests; resolution 10) |
| Error handling: crashes logged once, the tick model-free, GETs read-only, migrations idempotent, the headless sims green with the milestone's own sim check | Tasks 3, 7, 8 (no table added; L1's `run_creatures` guard), Task 7 (the whole brain meets a gloomling at night in a hatched world; the slow sims live through their nights) |

L1's final review asked L2 for: finer creature scheduling (Task 7, resolution 10), a despawn sweep (Task 7, resolution 6), passability per kind (Task 1 doors and eviction, Task 3 headroom), kill events by `kind.hostile` (Task 3, `spoils`), a live hostile cap (Task 7, `hostiles_alive`), the spawner beside populate (Task 7), gear's materials kept out of the chest and 4 rabbit hides to 1 leather (Task 5), the viewer's `chasing`, hostile dot color, models in `MODELS` and a shoot that reuses `target_of` and `strike` (Tasks 4, 8, 10), and a hostile cap of its own (Task 7).

Out of scope here (L3, L4): iron armor, lanterns as a recipe, gravel in the terrain, bigger caves and passages, new blocks and biomes, creature seeds, goals. Gloom dust is kept for L3.
