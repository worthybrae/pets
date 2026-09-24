# Living World L1: Animals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill Mimo's world with animals: a creature system the server owns (a `creatures` table, a kinds registry, seeded spawning near Mimo, a cheap creature tick, a creature-action registry and an API stream), passive rabbits, chickens, sheep and cows on land and fish in the water, a generic attack step and a hunt purpose that chases an animal down for its meat, hides, wool and feathers, cooked meats, swords, and a viewer that draws each kind as a blocky voxel model that walks, grazes, flashes when hit and puffs away with its drops, with dots on the minimap.

**Architecture:** A new package, `backend/survival/creatures/`, holds everything L1 adds, and each part plugs into a registry or hook that already exists. `kinds` is a registry of plain data (with `hostile`, `damage` and `reach` for L2). `table` creates the two tables and wraps them in `Herd`, which every `world_grid` Grid carries as `grid.herd`, so steps, planners and the tick reach creatures the way they reach blocks. `moves` and `acts` move creatures greedily by the Grid's own rules through a creature-action registry (flee, swim, graze, wander, idle; L2 adds chase and attack). `spawning` and `simulate` are the creature hook that `advance_world` runs after renewal, near Mimo only and with a per-call budget. `combat` registers the generic `attack` step in the step registry, `hunting` registers the `hunt` purpose in the purpose registry, `fishing` joins fishing's catch, and `view` is what `/api/mimo` streams. Meat, swords and the storage of hides are small edits to the existing recipe, food, carrying, cooking, toolmaking and storage modules. The viewer gets pure, tested model and motion modules and one component that draws them.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-living-world-design.md` (L1: the milestone table's row and the whole "L1 Animals (detail)" section; the spec's "Decisions" and "Error handling and testing" where they touch L1). L2 to L4 stay out, but the creature system leaves room for them (resolutions 2, 7, 11 and 22). It builds on the Survival Core (`docs/superpowers/specs/2026-09-23-survival-core-design.md`, complete) and follows the shape of `docs/superpowers/plans/2026-09-23-survival-m5-building.md`. The code on branch `worthy/23_09_2026/survival_core` at `f4927b1` (the Survival Core, then the explore memory and minimap) is the "old" text every task edits; the dry run applied every task to that commit.

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls. Creatures are deterministic: every roll comes from `worldgen.hash32` with the world seed, the creature's id, its turn and a channel (`creatures.moves.roll`), or the chunk and the herd (`creatures.spawning.chunk_roll`), or the dead creature's id (`creatures.combat.drops_of`). Nothing reads `random` or the clock, so the same world does the same thing every time.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments (mutate three.js objects only through refs inside `useFrame`, effects or event handlers), no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. Read-only GETs never write. Schema setup runs at most once per process per path (`_ensure_world_schema`), and every schema change is idempotent (`CREATE ... IF NOT EXISTS`). L1's two tables are created by `world.create_world_tables` (the world-schema hook). A world read before its schema update (an archive) has no creature tables and reads as having no creatures. The legacy world file is only ever opened read-only.
- **No model call inside the tick.** The creature hook, the attack step and the hunt planner are rules. Creatures never search for a path: they move one block at a time. Validity checks, facts and scores never write: the Chooser runs them on a read-only connection. Only the tick (the creature hook, the attack step and the fish step) writes creature rows, and nothing in L1 edits a block.
- A crashing planner, reflex, hook or picker never stops a tick or the worker. The creature hook's crashes are logged once per distinct error (`backend.survival.once.log_once`).
- `shared/blocks.json` does not change. `wool` is already a block; meat, hides, leather and feathers are items, not blocks.
- Values copied from the spec (L1 detail). Table `creatures(id INTEGER PRIMARY KEY, kind TEXT, x REAL, y REAL, z REAL, heading REAL, health REAL, state TEXT JSON, spawned_at REAL, next_at REAL)` with an index on `(x, z)`. Kinds carry `name`, `health`, `speed` (seconds per block), `size`, `hostile`, `damage`, `reach`, `drops` (item → (min, max) or chance), `biomes`, `herd` (min, max), `water` and `flee_when_hurt`: rabbit 3 health, fast, raw_rabbit and sometimes rabbit_hide; chicken 4, raw_chicken and 0–2 feathers; sheep 8, raw_mutton and 1–2 wool; cow 10, raw_beef and 0–2 leather; fish 2, swims in water, not hunted, where fishing's catch shows, fishing stock as in M4, more fish nearby slightly raises the catch chance. Spawning: herds spawn when Mimo first comes within 48 blocks of a chunk, seeded by the world seed and the chunk, 0–2 herds per chunk, chosen by biome; at most 24 passive creatures within 48 blocks and 6 fish per water region; a chunk that lost its animals regains one herd after 3 game days. Creature tick: inside `advance_world` at step resolution, only within 48 blocks of Mimo; each creature has a `next_at`; wander to a standable neighbour with pauses, within 12 blocks of the spawn point; flee when hurt or when Mimo is hunting within 6 blocks, at double speed for about 8 blocks; graze and idle poses; step up 1, drop up to 3, no water for land animals, water only for fish; at most N creature actions per slice, no path search, moves written to the row, no block edits. Hunting: `attack(creature_id)`, reach 2.5 blocks, 0.6 s by hand or 0.5 s with a sword, damage 1 by hand, 4 wooden, 5 stone, 6 iron; the target takes damage, flees and dies at 0 health, and its drops go straight into Mimo's arms subject to the carry limits; `hunt` is scored by food need in the needs band with the late-day penalty, rises for hungry pets and falls when food is carried, picks the nearest huntable animal within 32 blocks not near a failed step, walks within reach and attacks until the animal is dead or has fled out of range; bold pets hunt a little more (a kindness trait lowers it only if one exists). Cooking: raw_beef, raw_mutton, raw_chicken and raw_rabbit cook into cooked_*, from roughly 8 raw to 25–35 cooked, and raw chicken has a small chance of sickness. Crafting: wooden_sword 2 planks and 1 stick, stone_sword 2 cobblestone and 1 stick, iron_sword 2 iron_ingot and 1 stick; the toolmaking ladder makes the next sword only after the pickaxe it needs. API: `/api/mimo` adds `creatures` within 48 blocks (id, kind, x, y, z, heading, health fraction, state: walking, fleeing, idle, dead) and `creature_moves` (each creature's last move with from, to, started and ends, replayed 1.5 s behind the server). Viewer: a white rabbit with long ears, a woolly sheep, a spotted cow, a small chicken and a fish in water; a walk hop and bob, a head-down graze, a hurt flash and knockback, a death puff with the drops popping; Mimo's attack swing at the target; a health bar for a few seconds after a hit; creatures as small dots on the minimap. Performance: creature simulation costs at most 20 ms per 60-game-second slice on average, with at most 24 passive creatures active.
- `MIMO_TIME_SCALE` and `MIMO_ACTION_SCALE` (both default 1) are for manual runs only. Creature moves and pauses are divided by the action scale, like Mimo's own steps. L1 adds no settings.
- Never run `docker` or `docker compose` in Tasks 1–11. Task 12 is the controller's manual check on the demo stack (`mimo-m5demo-api` on :8011 and `mimo-m5demo-worker`, volume `mimo_m5demo`); never touch, mount or migrate the owner's real volume `pets_mimo_data` or the real stack (`pets-api-1`, `pets-mimo-worker-1`).
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (613 pass at `f4927b1`)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_herds.py" -v`
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` (about 3 minutes) and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
- Frontend tests: `cd frontend && npm test` (236 pass at `f4927b1`)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint <paths>`

Each task says how many tests it adds. If the real starting totals differ, expect the same increases on top of them.

Transcription: every edit is a fenced block, either a whole new file ("Create `path`:") or a "replace: … with: …" pair in a named file ("In `path`, replace:", then "and replace:" for more pairs in the same file). Old texts are kept short, so a task still applies when a neighbouring line changes. The dry run applied each task with the controller's apply script (`.superpowers/sdd/2026-09-23-survival-m5-building/apply_plan.py`) to a copy of `f4927b1` and ran the task's checks after each one.

## Plan-level resolutions

The spec leaves these open or ambiguous. Every task follows them; the controller ledgers them.

1. **Base.** The Survival Core is complete (M5, its fix wave and follow-ups, the camera modes), and so is the explore memory with its minimap (`explored` table, `exploring.py`, `/api/mimo` `explored` and `landmarks`, `Minimap.tsx`, `overheadMap.ts`). L1 plans against `f4927b1`. Anchors in files the explore work touched (`snapshot.py`, `types.ts`, `SurvivalWorld.tsx`, `Minimap.tsx`, `brain.py`, `purposes.py`) are single lines or its stable doc lines, and Task 11's Minimap anchors fit both the minimap's first version (`d4a80ba`) and its follow-up (`f4927b1`, glyphs sized per CSS pixel); the creature dots size themselves the same way without depending on it.
2. **One package, plugged into the registries that exist.** `backend/survival/creatures/` holds `kinds` (a registry of plain data), `table` (the tables and `Herd`), `moves`, `acts` (a new registry: the creature actions), `spawning`, `simulate` (the tick hook), `combat` (registers the `attack` step in `steps.STEP_KINDS`), `hunting` (registers `hunt` in `purposes.PURPOSES`), `fishing` and `view`. Its `__init__.py` imports nothing, so any module can be imported alone without a cycle. L2 adds its hostile kinds with `register_kind`, its chase and attack with `register_action`, and fights with the same `attack` step and `strike`.
3. **How code reaches creatures.** A Grid made by `grid.world_grid` carries `grid.herd`, a `Herd` over the same connection: the tick's write transaction, or the Chooser's and the API's read-only one. Steps only get the grid, so this is how the attack and fish steps reach creatures without changing the StepKind signature. A Grid built from `natural` alone (unit tests) has `herd = None`: tests that need creatures attach a `Herd` over an in-memory database. Reads of a database without the tables return nothing.
4. **Tables.** `creatures` is exactly the spec's table, indexed on `(x, z)`. A second table, `creature_chunks(cx, cz, herds, animals, spawned_at, empty_since)`, notes each chunk whose herds spawned, so it never spawns twice, and counts its living land animals, so a chunk "that lost its animals" is known without reading every creature (`Herd.lost` when one dies; `empty_since` is when the last one died). Both are created by `world.create_world_tables`, the world-schema hook, next to the growth table (not by `memory.create_memory_tables`: creatures are not Mimo's memory). Test databases that need them call `create_creature_tables`.
5. **A creature's state JSON:** `pose` ("idle", "walking", "grazing", "fleeing", "swimming", "dead"), `path` (its last move, `[{x, y, z, at}]`), `home` (its spawn cell), `chunk` (its home chunk), `turn` (the salt of its rolls), `hurt_at`, `calm_until`, `dead_at`, `drops` and, for fish, `caught_at`. The row's `x, y, z` is the cell its last move ends in; `moves.where(creature, at)` is where it is along the move at any moment (the attack's reach check uses it).
6. **Moves.** A creature steps to a neighbour by `pathing.moves` (level, one up with headroom, down at most 3), a land creature never onto a cell whose floor is water, a fish only between water cells (all six sides). A move is 1 to 8 steps with the same time per block, written to the row at once as a timed path, like Mimo's walks. Creature durations are server seconds divided by the action scale (`Scene.pace`, `MIMO_ACTION_SCALE`), like Mimo's steps.
7. **The creature-action registry** (`acts.CREATURE_ACTIONS`, data like the reflexes), checked in priority order: flee (10), swim (20: fish move 1–2 cells, then drift 2–6 s), graze (30: 3 in 10 turns, head down 3–6 s), wander (40: 2 in 3 of the rest, 1–3 blocks within 12 of home, else back toward it, then a 1–4 s pause) and idle (90: 2–5 s). Each action decides the creature's next move or pose and its `next_at`. L2 registers chase and attack here.
8. **Fleeing.** "When Mimo is hunting within 6 blocks" means Mimo's purpose is `hunt` and it stands within 6 blocks (horizontally) when the creature's turn comes. A flee runs up to 8 blocks, each step to the neighbour farthest from Mimo, stopping when none gets farther, at half the kind's seconds per block, then the creature is calm for 8 s: a hunting Mimo does not scare it again until then, so a chase can end. A hit makes a creature that flees when hurt run at once, whatever its calm. A flee may carry an animal past its 12-block leash; wandering brings it back.
9. **Spawning.** A chunk rolls no herd (35 %), one (45 %) or two (20 %). A herd's spot is one of 6 rolled columns in the chunk whose cell above the ground is standable, dry and not claimed by anything Mimo built; its kind is rolled among the passive kinds of the spot's biome (meadow: rabbit, chicken, sheep, cow; forest: rabbit, chicken, cow; desert: rabbit; alpine: rabbit, sheep), its size within the kind's `herd`, and it spreads over the spot and the 8 cells around it. A chunk with natural surface water also gets a school of 2–4 fish. The 24-creature cap counts every passive creature within 48 blocks, fish too (the spec's performance budget: at most 24 passive creatures active); a region (16×16, fishing's stock region) holds at most 6 fish. At most 8 new chunks spawn in one call, nearest first. A regained herd rolls with the time as salt, so it differs from the first.
10. **The creature hook.** `simulate` runs after `renewal` at the same two points of `advance_world` (after each chunk of actions and after the final catch-up), in its own try/except (`tick.run_creatures`). It reads the creatures within 48 blocks, spawns, removes the dead after 10 s (the viewer has shown their puff), and lets at most `MAX_ACTS = 24` due creatures take one turn each, earliest first. Farther creatures stay put. Measured on a hatched world: about 4 ms a call on average and 30 ms for the call that spawns the first 8 chunks; a test keeps the average under the spec's 20 ms per 60-game-second slice.
11. **The attack step** (`combat`). `{"kind": "attack", "creature": id, "target": [x, y, z]}`: the target cell is only the planner's note (and marks a failure's place); the step finds the creature by id. Reach 2.5 is checked when the swing starts. The blow lands when the swing ends if the creature is within reach plus one block (a lunge); one that ran off is missed, which is no failure. The running step keeps the action scale (`pace`), so a hit's flee runs at the same pace as everything else. It works for any kind and any weapon (the best sword carried); `strike(scene, creature, damage, source)` is the generic blow L2 reuses. A kill's drops go straight into Mimo's arms and the engine settles them (`carrying.after_step`): meat is valuable (food) and pushes out a low-value block when the arms are full; leather, wool, feathers and hides are not and stay behind. A kill sets `state["hunted_at"]` and logs a routine `hunt` event ("Pip hunted a cow.").
12. **The hunt purpose.** Valid by day while a huntable animal is within 32 blocks and Mimo lacks food (`foraging.food_need`) or has not killed anything for a game day. Measured on the headless runs: gated on food need alone, hunting almost never happened (Mimo keeps 4 cooked fish, 120 hunger of food), and ungated a well-fed pet hunted 24 animals a game day and made 77 purpose changes an hour; the daily hunt gives one or two hunts a day. Score: `foraging.hunger_score` from a base of 30 (25–88, in the needs band with forage and fish) plus (bravery − 50) / 10. There is no kindness or gentleness trait (the traits are curiosity, creativity, sociability, patience, bravery, caution, thrift and diligence), so nothing lowers it. One animal per choice: the nearest when the hunt starts (`brain["prey"]` keeps it), then each batch attacks it when it is within reach or walks, all the way or not at all, to within 2 blocks of where its move ends; done when it is dead, out of range or beside a failed step, or after 40 batches.
13. **Meat.** Hunger: raw beef and mutton 8, raw chicken and rabbit 6; cooked beef 35, mutton 30, chicken 25, rabbit 25. Raw chicken is a gamble (`steps.FOOD_RISK`): a 1 in 4 chance of 4 health (never the last point), rolled from the seed, Mimo's cell and the time, and not learned as poison (only `FOOD_HEALTH` teaches that), since cooking makes it safe. `cook` cooks every raw food Mimo carries (fish and the four meats, in name order).
14. **Swords.** Recipes at a crafting table (the spec's "same recipe and portable-station system"; pickaxes and axes need one too). A sword is made only up to the tier of the best pickaxe Mimo has. craft_tools makes the sword a new pickaxe opens up in the same batch, right after it, when the materials stretch that far (three logs make a wooden pickaxe and a wooden sword), else the pickaxe alone, and with no pickaxe to make, the best sword it may: a separate sword choice after every pickaxe would add a purpose change each time. Swords are valuable to carry, and drop_items drops one a better sword replaced.
15. **What animals leave.** Item names: `raw_beef`, `raw_mutton`, `raw_chicken`, `raw_rabbit`, `leather`, `wool`, `feather` (singular, like L2's arrow recipe "1 flint, 1 stick and 1 feather") and `rabbit_hide`. build_storage puts leather, wool, feathers and hides in the chest (`storage.KEEP` 0) until L2 needs them; spare meat already goes as spare food.
16. **Fish.** Not hunted and never removed. Each living fish within 8 blocks of the hook adds 0.02 to the catch chance, at most 0.1, only while the region still has stock (`nature.catches(..., bonus)`). When a catch lands, the nearest of those fish darts to the hook (0.3 s) and leaps (`caught_at`); the viewer shows the leap.
17. **API.** `creatures`: up to 48 creatures within 48 blocks of Mimo, nearest first, with id, kind, x, y, z, heading, health fraction and state (a walk or flee that has ended reads "idle"; "grazing" and "swimming" are states too), and `hurt_at`, `dead_at`, `drops` and `caught_at` only when set; a creature dead more than 10 s is left out. `creature_moves`: the last move of each listed creature that ended within 3 s (the viewer draws 1.5 s behind and polls every second; an older move has nothing left to replay) with `from`, `to`, `started`, `ends`, and `cells` ([x, y, z] of every cell) only for a move longer than one block. Measured: about 4.5 KB for 24 animals; a test keeps the worst case (30 creatures all fleeing) under 14 KB. It is read in the same read-only transaction as the rest of `survival_view`.
18. **Viewer.** One `CreatureFigure` per creature (the nearest 32): two instanced voxel meshes (body and head, so the head can dip to graze), a health bar that faces the camera, a puff of 6 bits and up to 4 drops. Creatures are drawn in the live world only (archives have no server clock to replay by). Model sizes follow the kinds' `size`; the models are ours, not Minecraft's. Mimo's attack plays a lunge toward its target. The minimap draws each living creature as a small cream dot (blue for fish).
19. **Purpose budget.** The headless runs cap the changes of purpose in any game hour (`test_survival_sim.PURPOSE_EVENTS_PER_HOUR`: 46, and 55 with `MIMO_SLOW_TESTS=1`, at `f4927b1`, where the busiest hours measured 38 and 40). L1 adds a hunt, cooking its meat, putting away what animals leave and now and then a sword, each a change of purpose and a change back. Measured after all of L1 on seeds 3, 11, 5 and 21 with both pickers: at most 47 at the default settings (seed 3, rules) and 52 with `MIMO_SLOW_TESTS=1`; after Task 5, before anything hunts, the default runs stay within 46. Task 6 raises the default budget to 52; the slow one stays 55, still under the 58 to 116 an hour of the floods it is there to catch.
20. **The model payload does not change.** hunt's facts name the nearest animal and how far it is; L2 adds `threats`.
21. **Game time units** stay M3's: a game minute is 60 game seconds and a game day 3,600. "3 game days" is 10,800 game seconds on the life's clock (`time_scale` from the clock).
22. **Room for L2.** Kinds carry `hostile`, `damage` and `reach`, and passive-only rules say so (`land_kinds`, `water_kinds`, `huntable` and the flee on a hunting Mimo skip hostile kinds). L2 registers its chase and attack as creature actions; the `Scene` carries Mimo's state and the tick's events, so a creature's attack can hurt Mimo and log it. Mimo's fight reflex queues the same `attack` step, and a creature's blow on another creature would use `strike`. `moves.steps` is the one place a creature's passability lives, so L2's doors (solid to creatures, open to Mimo) and its light checks for dark spawning (a spawner of its own beside `populate`, which only spawns passive herds) plug in there. The API streams any kind by name, and the viewer draws a kind it has no model for as a plain grey block until L2 adds one.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/survival/creatures/__init__.py` | Create | The package's map; imports nothing |
| `backend/survival/creatures/kinds.py` | Create | The kinds registry: rabbit, chicken, sheep, cow, fish |
| `backend/survival/creatures/table.py` | Create | The `creatures` and `creature_chunks` tables, `Herd` |
| `backend/survival/creatures/moves.py` | Create | Greedy one-block moves, seeded rolls, `where` |
| `backend/survival/creatures/acts.py` | Create | The creature-action registry (flee, swim, graze, wander, idle) and `Scene` |
| `backend/survival/creatures/spawning.py` | Create | Herds per chunk near Mimo, the caps, a herd back after 3 game days |
| `backend/survival/creatures/simulate.py` | Create | The creature hook the tick runs |
| `backend/survival/creatures/combat.py` | Create | The `attack` step, `strike`, weapons and drops |
| `backend/survival/creatures/hunting.py` | Create | The `hunt` purpose |
| `backend/survival/creatures/fishing.py` | Create | Fish near the hook: the bite bonus and the leap |
| `backend/survival/creatures/view.py` | Create | `creatures` and `creature_moves` for `/api/mimo` |
| `backend/survival/grid.py`, `world.py`, `tick.py` | Modify | `grid.herd`; the tables; the creature hook beside renewal |
| `backend/services/crafting.py`, `backend/survival/steps.py`, `carrying.py`, `cooking.py`, `toolmaking.py`, `storage.py` | Modify | Swords and cooked meats; meat's hunger and raw chicken's risk; swords are valuable; cook every raw food; the sword ladder; hides in the chest and replaced swords dropped |
| `backend/survival/steps.py`, `world.py` | Modify | Register the attack step; `hunt` is a routine event |
| `backend/survival/brain.py`, `purposes.py` | Modify | Import the hunt purpose; its score band |
| `backend/survival/nature.py`, `fieldwork.py` | Modify | The catch bonus; the fish step shows the catch |
| `backend/survival/snapshot.py` | Modify | Stream the creatures |
| `backend/tests/test_survival_{creatures,creature_acts,herds,meat,combat,hunting,fish,creature_api}.py` | Create | One test file per new module or area |
| `backend/tests/test_survival_{pickers,toolmaking,days,sim}.py` | Modify | Swords in the tool ladder; a headless run that hunts and cooks; the purpose budget |
| `frontend/src/survival/types.ts`, `hud.ts`, `animation.ts` (+ tests) | Modify | `Creature`, `CreatureMove`, `attack`; HUD words; the attack lunge |
| `frontend/src/survival/creatures.ts`, `creatureMotion.ts` (+ tests) | Create | Voxel models and drop colors; replay, poses, flash, knockback, health bar, puff, minimap dots |
| `frontend/src/survival/SurvivalCreatures.tsx` | Create | Draw the creatures |
| `frontend/src/survival/WorldCanvas.tsx`, `SurvivalWorld.tsx`, `Minimap.tsx` | Modify | Mount the creatures; pass them on; dots on the minimap |
| `README.md` | Modify | Animals |

## Tasks

1. Creature kinds and where creatures live
2. How creatures move
3. Herds near Mimo, in the tick
4. Meat, cooking and swords
5. The attack step
6. The hunt purpose
7. Fish show the catch
8. What the viewer is told
9. Viewer: the creature types, hunting words and the attack lunge
10. Viewer: creature models and how they move
11. Viewer: creatures in the world and on the minimap
12. Manual check on the demo and the README

Tasks 1–8 are the backend and 9–11 the viewer; each viewer task needs only the tasks before it. Task 4 does not need the creatures (it could run first), and Task 7 needs only Tasks 1 and 2.

---

### Task 1: Creature kinds and where creatures live

**Files:**
- Create: `backend/survival/creatures/__init__.py`, `backend/survival/creatures/kinds.py`, `backend/survival/creatures/table.py`
- Modify: `backend/survival/grid.py` (a `herd` on every world grid), `backend/survival/world.py` (the tables)
- Test: `backend/tests/test_survival_creatures.py`

**Interfaces:**
- Consumes: `world.create_world_tables` (the world-schema hook), `grid.world_grid`, `grid.Grid`.
- Produces:
  - `backend.survival.creatures.kinds`: `Kind` (frozen dataclass: `name`, `health`, `speed` in seconds per block, `size` in blocks tall, `hostile=False`, `damage=0.0`, `reach=0.0`, `drops: dict[str, tuple[int, int] | float]`, `biomes: tuple[str, ...]`, `herd: tuple[int, int]`, `water=False`, `flee_when_hurt=True`); `KINDS: dict[str, Kind]`; `register_kind(kind) -> Kind`; `kind_of(name) -> Kind | None`; `land_kinds(biome) -> list[Kind]` (passive kinds that are not water kinds and spawn in the biome); `water_kinds() -> list[Kind]`; `huntable(kind_or_None) -> bool` (passive land animals). Registered: rabbit, chicken, sheep, cow and fish.
  - `backend.survival.creatures.table`: `create_creature_tables(db)`; `cell_of(creature) -> (x, y, z)` as ints; `dead(creature) -> bool` (`state["pose"] == "dead"`); `Herd(db)` with `near(x, z, reach) -> list[dict]` (dead and alive, by id), `get(id) -> dict | None`, `add(kind, cell, health, at, next_at, state) -> dict`, `save(creature)`, `remove(id)`, `chunks(low, high) -> dict[(cx, cz), dict]` (rows with `cx, cz, herds, animals, spawned_at, empty_since`), `note_chunk(chunk, herds, animals, at)`, `regained(chunk, animals, at)` and `lost(chunk_list_or_None, at)`. A creature is a dict with `id, kind, x, y, z, heading, health, state` (a dict), `spawned_at` and `next_at`.
  - `grid.Grid.herd: Herd | None`, None unless set; `grid.world_grid(db, seed)` sets it to `Herd(db)`.
  - Every world database has the tables `creatures` (indexed on `x, z`) and `creature_chunks`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_creatures.py`:

```python
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.creatures.kinds import KINDS, Kind, huntable, kind_of, land_kinds, register_kind, water_kinds
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables, dead
from backend.survival.grid import Grid, world_grid
from backend.survival.world import SurvivalWorld, new_survival_state


def herd():
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    return Herd(db)


class KindTests(unittest.TestCase):
    def test_the_four_animals_and_fish_are_registered_with_the_spec_values(self):
        self.assertEqual({name: KINDS[name].health for name in ("rabbit", "chicken", "sheep", "cow", "fish")},
                         {"rabbit": 3.0, "chicken": 4.0, "sheep": 8.0, "cow": 10.0, "fish": 2.0})
        self.assertLess(KINDS["rabbit"].speed, KINDS["cow"].speed)  # seconds per block: the rabbit is fast
        self.assertEqual(KINDS["rabbit"].drops, {"raw_rabbit": (1, 1), "rabbit_hide": 0.5})
        self.assertEqual(KINDS["chicken"].drops, {"raw_chicken": (1, 1), "feather": (0, 2)})
        self.assertEqual(KINDS["sheep"].drops, {"raw_mutton": (1, 2), "wool": (1, 2)})
        self.assertEqual(KINDS["cow"].drops, {"raw_beef": (1, 3), "leather": (0, 2)})
        self.assertTrue(KINDS["fish"].water)
        self.assertEqual(KINDS["fish"].drops, {})
        for kind in KINDS.values():
            self.assertFalse(kind.hostile)
            self.assertTrue(kind.flee_when_hurt)
            self.assertLessEqual(kind.herd[0], kind.herd[1])

    def test_kinds_by_biome_and_what_mimo_hunts(self):
        self.assertEqual([kind.name for kind in land_kinds("meadow")], ["rabbit", "chicken", "sheep", "cow"])
        self.assertEqual([kind.name for kind in land_kinds("desert")], ["rabbit"])
        self.assertEqual([kind.name for kind in water_kinds()], ["fish"])
        self.assertTrue(huntable(KINDS["cow"]))
        self.assertFalse(huntable(KINDS["fish"]))
        self.assertFalse(huntable(None))
        self.assertIsNone(kind_of("dragon"))
        self.assertIsNone(kind_of(None))

    def test_a_hostile_kind_registers_like_any_other_and_is_not_hunted_or_spawned_as_a_herd(self):
        gloom = register_kind(Kind("test_gloom", health=20.0, speed=1.0, size=1.6, hostile=True, damage=3.0,
                                   reach=1.5, biomes=("meadow",)))
        try:
            self.assertIs(kind_of("test_gloom"), gloom)
            self.assertFalse(huntable(gloom))
            self.assertNotIn(gloom, land_kinds("meadow"))
        finally:
            del KINDS["test_gloom"]


class HerdTests(unittest.TestCase):
    def test_creatures_are_added_read_near_saved_and_removed(self):
        creatures = herd()
        cow = creatures.add("cow", (3, 1, 4), 10.0, 5.0, 6.0, {"home": [3, 1, 4], "pose": "idle", "turn": 0})
        far = creatures.add("rabbit", (90, 1, 0), 3.0, 5.0, 6.0, {})
        self.assertEqual((cow["kind"], cell_of(cow), cow["health"], cow["heading"], cow["spawned_at"], cow["next_at"]),
                         ("cow", (3, 1, 4), 10.0, 0.0, 5.0, 6.0))
        self.assertEqual([found["id"] for found in creatures.near(0, 0, 48)], [cow["id"]])
        cow.update(x=4.0, heading=1.5, health=6.0, next_at=9.0)
        cow["state"]["pose"] = "walking"
        creatures.save(cow)
        again = creatures.get(cow["id"])
        self.assertEqual((again["x"], again["heading"], again["health"], again["next_at"], again["state"]["pose"]),
                         (4.0, 1.5, 6.0, 9.0, "walking"))
        self.assertFalse(dead(again))
        creatures.remove(far["id"])
        self.assertIsNone(creatures.get(far["id"]))

    def test_chunks_count_their_living_animals_and_empty_when_the_last_one_dies(self):
        creatures = herd()
        creatures.note_chunk((1, 2), 2, 2, 10.0)
        creatures.note_chunk((5, 5), 1, 0, 10.0)  # its herd could not stand anywhere
        creatures.note_chunk((1, 2), 0, 0, 99.0)  # noted once: a second note changes nothing
        creatures.lost([1, 2], 20.0)
        self.assertEqual(creatures.chunks((1, 2), (1, 2))[(1, 2)]["animals"], 1)
        self.assertIsNone(creatures.chunks((1, 2), (1, 2))[(1, 2)]["empty_since"])
        creatures.lost([1, 2], 30.0)
        creatures.lost([1, 2], 40.0)
        self.assertEqual(creatures.chunks((0, 0), (9, 9)), {
            (1, 2): {"cx": 1, "cz": 2, "herds": 2, "animals": 0, "spawned_at": 10.0, "empty_since": 30.0},
            (5, 5): {"cx": 5, "cz": 5, "herds": 1, "animals": 0, "spawned_at": 10.0, "empty_since": 10.0}})
        creatures.regained((1, 2), 3, 50.0)
        self.assertEqual(creatures.chunks((1, 2), (1, 2))[(1, 2)]["animals"], 3)
        self.assertIsNone(creatures.chunks((1, 2), (1, 2))[(1, 2)]["empty_since"])
        creatures.lost(None, 60.0)  # a creature with no home chunk changes nothing

    def test_a_database_without_the_tables_reads_as_no_creatures(self):
        empty = Herd(sqlite3.connect(":memory:"))
        self.assertEqual((empty.near(0, 0, 48), empty.get(1), empty.chunks((0, 0), (1, 1))), ([], None, {}))


class WorldTests(unittest.TestCase):
    def test_every_world_has_the_creature_tables_and_its_grid_reaches_them(self):
        with tempfile.TemporaryDirectory() as root:
            state = new_survival_state(name="Pip", seed="1", spawn={"x": 0, "y": 1, "z": 0}, born_at=0.0, traits={})
            world = SurvivalWorld.create(Path(root) / "world.sqlite3", state)
            with world.transaction() as db:
                grid = world_grid(db, "1")
                grid.herd.add("sheep", (2, 1, 2), 8.0, 0.0, 1.0, {})
                create_creature_tables(db)  # again: changes nothing
            with world.connect() as db:
                self.assertEqual([found["kind"] for found in world_grid(db, "1").herd.near(0, 0, 10)], ["sheep"])
        self.assertIsNone(Grid(lambda x, y, z: "air").herd)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_creatures.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures'`.

- [ ] **Step 3: Add the package and the kinds registry**

The package's `__init__.py` imports nothing, so any of its modules can be imported on its own without an import cycle (resolution 2). Its docstring lists the modules the later tasks add.

Create `backend/survival/creatures/__init__.py`:

```python
"""Creatures: the animals that share Mimo's world (Living World L1).

The server owns them, like Mimo: they live in the world database (backend.survival.creatures.table)
and move inside the tick (backend.survival.creatures.simulate), and the viewer only draws them.
- kinds: what each kind of creature is, as plain data in a registry.
- table: the creatures and creature_chunks tables, and `Herd`, how the tick and readers reach them.
- moves: greedy one-block moves by the Grid's rules, seeded rolls and where a creature is now.
- acts: the creature-action registry (flee, swim, graze, wander, idle) and the Scene they act in.
- spawning: herds that appear the first time Mimo comes near a chunk, the caps, and animals coming back.
- simulate: the creature hook advance_world calls after each chunk of Mimo's actions.
- combat: the generic attack step and what a blow does to any creature.
- hunting: the hunt purpose.
- fishing: fish in the water show where a catch comes from.
- view: what /api/mimo streams about them.
This module imports nothing, so any of them can be imported on its own without a cycle.
"""
```

Create `backend/survival/creatures/kinds.py`:

```python
"""The kinds of creature, as a registry of plain data (spec L1, "Creatures table and registry").

A Kind says how much health a creature has, how fast it walks (`speed`, seconds per block; it
flees at double speed), how big it is (`size`, blocks tall, for the viewer), whether it is
`hostile`, how much `damage` its attack does and from how far (`reach`), what it drops when it
dies (`drops`: item -> (least, most), or item -> the chance of one), the biomes it spawns in, how
many come together (`herd`), whether it lives in `water` (fish) and whether it runs off when hurt
(`flee_when_hurt`). L1 registers the passive rabbit, chicken, sheep and cow, and fish; L2's
hostile kinds register themselves the same way, with `hostile`, `damage` and `reach` set.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Drop = tuple[int, int] | float  # (least, most) of the item, or the chance of exactly one


@dataclass(frozen=True)
class Kind:
    name: str
    health: float
    speed: float  # seconds per block while walking; fleeing takes half as long
    size: float  # blocks tall
    hostile: bool = False
    damage: float = 0.0  # what one attack of its own does to Mimo (L2)
    reach: float = 0.0  # how close it must be to attack (L2)
    drops: dict[str, Drop] = field(default_factory=dict)
    biomes: tuple[str, ...] = ()  # where herds spawn; a water kind spawns in any biome's water
    herd: tuple[int, int] = (1, 1)  # how many spawn together, least and most
    water: bool = False  # lives in water (fish), else on land and never in water
    flee_when_hurt: bool = True


KINDS: dict[str, Kind] = {}


def register_kind(kind: Kind) -> Kind:
    """Add a kind, or replace the one with the same name."""
    KINDS[kind.name] = kind
    return kind


def kind_of(name) -> Kind | None:
    """The registered kind called `name`, or None."""
    return KINDS.get(name) if isinstance(name, str) else None


def land_kinds(biome: str) -> list[Kind]:
    """The passive land kinds whose herds spawn in `biome`, in registration order."""
    return [kind for kind in KINDS.values() if not kind.water and not kind.hostile and biome in kind.biomes]


def water_kinds() -> list[Kind]:
    return [kind for kind in KINDS.values() if kind.water and not kind.hostile]


def huntable(kind: Kind | None) -> bool:
    """Mimo hunts passive land animals: not fish, and (from L2) not the hostile kinds it fights."""
    return kind is not None and not kind.water and not kind.hostile


register_kind(Kind("rabbit", health=3.0, speed=0.35, size=0.5, drops={"raw_rabbit": (1, 1), "rabbit_hide": 0.5},
                   biomes=("meadow", "forest", "desert", "alpine"), herd=(1, 3)))
register_kind(Kind("chicken", health=4.0, speed=0.6, size=0.6, drops={"raw_chicken": (1, 1), "feather": (0, 2)},
                   biomes=("meadow", "forest"), herd=(2, 4)))
register_kind(Kind("sheep", health=8.0, speed=0.7, size=1.0, drops={"raw_mutton": (1, 2), "wool": (1, 2)},
                   biomes=("meadow", "alpine"), herd=(2, 4)))
register_kind(Kind("cow", health=10.0, speed=0.8, size=1.3, drops={"raw_beef": (1, 3), "leather": (0, 2)},
                   biomes=("meadow", "forest"), herd=(2, 3)))
register_kind(Kind("fish", health=2.0, speed=0.8, size=0.3, herd=(2, 4), water=True))
```

- [ ] **Step 4: Add the tables and `Herd`**

Create `backend/survival/creatures/table.py`:

```python
"""Where creatures live: two tables in the world database, and `Herd`, the way to them.

`creatures(id, kind, x, y, z, heading, health, state, spawned_at, next_at)`, indexed on (x, z),
holds every creature: where it stands (the cell its last move ends in), which way it faces
(radians around +y, 0 facing +z, like the viewer), its health, when it spawned and when it acts
next. `state` is JSON: its pose ("idle", "walking", "grazing", "fleeing", "swimming" or "dead"),
its last move as a timed path, its home (the spawn cell it stays near), its home chunk, how many
times it has acted (`turn`, the salt of its rolls) and when it was last hurt, calmed, caught or
killed. `creature_chunks(cx, cz, herds, animals, spawned_at, empty_since)` notes each 16x16 chunk
whose herds have spawned: how many herds its roll gave it, how many of the land animals that
spawned there are alive, and since when they have all been gone
(backend.survival.creatures.spawning).

A Grid made by grid.world_grid carries a Herd over the same connection (`grid.herd`), so steps,
planners and the creature hook all reach creatures the way they reach blocks. Reads work on a
read-only connection; a world read before its schema update (an archive from before L1) has no
creatures table and reads as having no creatures. `create_creature_tables` runs with the other
world tables (world.create_world_tables); running it again changes nothing.
"""

from __future__ import annotations

import json
import math
import sqlite3

COLUMNS = ("id", "kind", "x", "y", "z", "heading", "health", "state", "spawned_at", "next_at")
CHUNK_COLUMNS = ("cx", "cz", "herds", "animals", "spawned_at", "empty_since")


def create_creature_tables(db: sqlite3.Connection) -> None:
    """Create the creature tables. Run it inside the caller's BEGIN IMMEDIATE."""
    db.execute("CREATE TABLE IF NOT EXISTS creatures (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, x REAL NOT NULL, "
               "y REAL NOT NULL, z REAL NOT NULL, heading REAL NOT NULL DEFAULT 0, health REAL NOT NULL, "
               "state TEXT NOT NULL DEFAULT '{}', spawned_at REAL NOT NULL, next_at REAL NOT NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS creatures_by_column ON creatures(x, z)")
    db.execute("CREATE TABLE IF NOT EXISTS creature_chunks (cx INTEGER NOT NULL, cz INTEGER NOT NULL, "
               "herds INTEGER NOT NULL, animals INTEGER NOT NULL DEFAULT 0, spawned_at REAL NOT NULL, "
               "empty_since REAL, PRIMARY KEY (cx, cz))")


def missing_table(error: sqlite3.OperationalError) -> bool:
    return "no such table" in str(error)


def creature_of(row) -> dict:
    creature = dict(zip(COLUMNS, tuple(row)))
    creature["state"] = json.loads(creature["state"] or "{}")
    return creature


def cell_of(creature: dict) -> tuple[int, int, int]:
    """The cell a creature stands in (where its last move ends)."""
    return round(creature["x"]), round(creature["y"]), round(creature["z"])


def dead(creature: dict) -> bool:
    return creature["state"].get("pose") == "dead"


class Herd:
    """The creatures of one world through one connection (the tick's, or a reader's)."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def near(self, x: float, z: float, reach: float) -> list[dict]:
        """Every creature, dead or alive, within `reach` blocks (horizontally) of (x, z), by id."""
        box = math.ceil(reach)
        try:
            rows = self.db.execute(f"SELECT {','.join(COLUMNS)} FROM creatures WHERE x BETWEEN ? AND ? "
                                   "AND z BETWEEN ? AND ? ORDER BY id", (x - box, x + box, z - box, z + box)).fetchall()
        except sqlite3.OperationalError as error:
            if not missing_table(error):
                raise
            return []
        found = [creature_of(row) for row in rows]
        return [creature for creature in found if math.hypot(creature["x"] - x, creature["z"] - z) <= reach]

    def get(self, number: int) -> dict | None:
        try:
            row = self.db.execute(f"SELECT {','.join(COLUMNS)} FROM creatures WHERE id=?", (number,)).fetchone()
        except sqlite3.OperationalError as error:
            if not missing_table(error):
                raise
            return None
        return None if row is None else creature_of(row)

    def add(self, kind: str, cell: tuple[int, int, int], health: float, at: float, next_at: float,
            state: dict) -> dict:
        """A new creature standing in `cell`, facing +z."""
        cursor = self.db.execute("INSERT INTO creatures(kind,x,y,z,heading,health,state,spawned_at,next_at) "
                                 "VALUES (?,?,?,?,?,?,?,?,?)",
                                 (kind, *map(float, cell), 0.0, health, json.dumps(state), at, next_at))
        return self.get(cursor.lastrowid)

    def save(self, creature: dict) -> None:
        self.db.execute("UPDATE creatures SET x=?, y=?, z=?, heading=?, health=?, state=?, next_at=? WHERE id=?",
                        (creature["x"], creature["y"], creature["z"], creature["heading"], creature["health"],
                         json.dumps(creature["state"]), creature["next_at"], creature["id"]))

    def remove(self, number: int) -> None:
        self.db.execute("DELETE FROM creatures WHERE id=?", (number,))

    def chunks(self, low: tuple[int, int], high: tuple[int, int]) -> dict[tuple[int, int], dict]:
        """The noted chunks from `low` to `high` (cx, cz, both ends included), by (cx, cz)."""
        try:
            rows = self.db.execute(f"SELECT {','.join(CHUNK_COLUMNS)} FROM creature_chunks WHERE cx BETWEEN ? AND ? "
                                   "AND cz BETWEEN ? AND ?", (low[0], high[0], low[1], high[1])).fetchall()
        except sqlite3.OperationalError as error:
            if not missing_table(error):
                raise
            return {}
        return {(row[0], row[1]): dict(zip(CHUNK_COLUMNS, tuple(row))) for row in rows}

    def note_chunk(self, chunk: tuple[int, int], herds: int, animals: int, at: float) -> None:
        """Note that a chunk's herds spawned: `herds` rolled, `animals` land animals alive. A chunk
        whose roll gave herds but where none could stand is empty from now on."""
        self.db.execute("INSERT OR IGNORE INTO creature_chunks(cx, cz, herds, animals, spawned_at, empty_since) "
                        "VALUES (?, ?, ?, ?, ?, ?)", (*chunk, herds, animals, at,
                                                      at if herds > 0 and animals == 0 else None))

    def regained(self, chunk: tuple[int, int], animals: int, at: float) -> None:
        """A herd of `animals` came back to an empty chunk (none could stand: it waits again)."""
        self.db.execute("UPDATE creature_chunks SET animals=?, empty_since=? WHERE cx=? AND cz=?",
                        (animals, None if animals else at, *chunk))

    def lost(self, chunk, at: float) -> None:
        """A land animal from `chunk` died; when it was the last, the chunk is empty from `at`."""
        if not (isinstance(chunk, list) and len(chunk) == 2):
            return
        self.db.execute("UPDATE creature_chunks SET animals = MAX(0, animals - 1) WHERE cx=? AND cz=?", tuple(chunk))
        self.db.execute("UPDATE creature_chunks SET empty_since=? WHERE cx=? AND cz=? AND animals=0 "
                        "AND empty_since IS NULL", (at, *chunk))
```

- [ ] **Step 5: Create the tables with every world, and give world grids their herd**

In `backend/survival/world.py`, replace:

```python
"""A survival life's world database: the shared block table, Mimo's state and its events.
```

with:

```python
"""A survival life's world database: the shared block table, Mimo's state, its events and its creatures.
```

and replace:

```python
from backend.survival.memory import create_memory_tables
```

with:

```python
from backend.survival.creatures.table import create_creature_tables
from backend.survival.memory import create_memory_tables
```

and replace:

```python
    create_growth_table(db)
```

with:

```python
    create_growth_table(db)
    create_creature_tables(db)
```

In `backend/survival/grid.py`, replace:

```python
so planners that dig or till can leave them alone (`claimed`).
```

with:

```python
so planners that dig or till can leave them alone (`claimed`). A grid over a world database also
carries the world's creatures (`herd`, backend.survival.creatures.table.Herd), so steps and
planners reach them the way they reach blocks; a grid built from `natural` alone has none.
```

and replace:

```python
from backend.services.worldgen import block_at
```

with:

```python
from backend.services.worldgen import block_at
from backend.survival.creatures.table import Herd
```

and replace:

```python
        self.claims: set[Cell] = set()
```

with:

```python
        self.claims: set[Cell] = set()
        self.herd: Herd | None = None
```

and replace:

```python
    return Grid(lambda x, y, z: block_at(x, y, z, seed), load_edits, write, load_claims)
```

with:

```python
    grid = Grid(lambda x, y, z: block_at(x, y, z, seed), load_edits, write, load_claims)
    grid.herd = Herd(db)
    return grid
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_creatures.py"`
Expected: `Ran 7 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 620 tests` … `OK` (7 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/creatures/__init__.py backend/survival/creatures/kinds.py backend/survival/creatures/table.py backend/survival/grid.py backend/survival/world.py backend/tests/test_survival_creatures.py
git commit -m "feat: add the creature kinds registry and the creatures table every world grid reaches" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 2: How creatures move

**Files:**
- Create: `backend/survival/creatures/moves.py`, `backend/survival/creatures/acts.py`
- Test: `backend/tests/test_survival_creature_acts.py`

**Interfaces:**
- Consumes: Task 1's `Kind`, `kind_of`, `huntable`, `Herd`, `cell_of` and `dead`; `pathing.moves(grid, cell)` (Mimo's rule for one move: level, one up with headroom, down at most 3); `worldgen.hash32`.
- Produces:
  - `backend.survival.creatures.moves`: `roll(seed, number, turn, channel) -> float` in [0, 1); `steps(grid, cell, water) -> list[Cell]` (on land, `pathing.moves` without cells on water; in water, the water cells on all six sides); `timed(start, cells, at, seconds) -> list[dict]` (`x, y, z, at` per cell, the start first); `where(creature, at) -> Cell`; `heading(start, end, fallback) -> float` (`atan2(dx, dz)`); `move(creature, cells, at, seconds, pose) -> float` (a move from `where(creature, at)`: the row moves to its end, `heading`, `state["path"]` and `state["pose"]` are set, and it returns when the move ends).
  - `backend.survival.creatures.acts`: `Scene(grid, herd, seed, state, at, pace=1.0, events=[])` with `pet` (Mimo's cell), `hunting` (Mimo's purpose is `hunt`), `roll(creature, channel)` and `between(creature, span, channel)` (a duration from the span, divided by `pace`); `CreatureAction(name, priority, when, act)`, where `when(creature, kind, scene) -> bool` and `act(creature, kind, scene) -> None` sets the next move or pose and `creature["next_at"]`; `CREATURE_ACTIONS`; `register_action(action) -> CreatureAction`; `act(creature, scene) -> str | None` (runs the first action whose `when` holds and counts `state["turn"]`; None for a dead creature or a kind no longer registered); `run_away(creature, kind, scene, danger)`; `flat_distance(a, b)`; `FLEE_BLOCKS = 8`, `SCARE_REACH = 6.0`, `CALM_SECONDS = 8.0`, `LEASH = 12.0`. Registered: `flee` (10), `swim` (20), `graze` (30), `wander` (40) and `idle` (90).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_creature_acts.py`:

```python
import math
import sqlite3
import unittest

from backend.survival.creatures.acts import (
    CALM_SECONDS, CREATURE_ACTIONS, FLEE_BLOCKS, LEASH, CreatureAction, Scene, act, register_action, run_away,
)
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.moves import roll, steps, timed, where
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables
from backend.survival.grid import Grid

POND = {(x, z) for x in range(4, 7) for z in range(-1, 2)}


def meadow(blocks=None):
    """Grass at y 0 with a pond at x 4..6, z -1..1 (water at y 0), and `blocks` placed."""
    blocks = blocks or {}

    def natural(x, y, z):
        if (x, y, z) in blocks:
            return blocks[(x, y, z)]
        if y == 0:
            return "water" if (x, z) in POND else "grass"
        return "dirt" if y < 0 else "air"
    return Grid(natural)


def herd():
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    return Herd(db)


def pet(x=30, purpose=None):
    return {"name": "Pip", "position": {"x": float(x), "y": 1.0, "z": 0.0}, "brain": {"purpose": purpose}}


def scene(grid, creatures, at=0.0, **changes):
    return Scene(grid, creatures, "7", changes.pop("state", pet()), at, **changes)


def animal(creatures, kind="cow", cell=(0, 1, 0), **state):
    return creatures.add(kind, cell, KINDS[kind].health, 0.0, 0.0, {"home": list(cell), "turn": 0, **state})


class MoveTests(unittest.TestCase):
    def test_land_steps_follow_mimos_rules_and_never_go_onto_water(self):
        grid = meadow({(1, 1, 0): "stone", (0, 1, 1): "stone", (0, 2, 1): "stone"})
        self.assertEqual(sorted(steps(grid, (0, 1, 0), False)), [(-1, 1, 0), (0, 1, -1), (1, 2, 0)])
        self.assertNotIn((4, 1, 0), steps(grid, (3, 1, 0), False))  # the pond's surface
        self.assertEqual(sorted(steps(grid, (5, 0, 0), True)), [(4, 0, 0), (5, 0, -1), (5, 0, 1), (6, 0, 0)])

    def test_a_move_is_a_timed_path_and_where_follows_it(self):
        path = timed((0, 1, 0), [(1, 1, 0), (2, 1, 0)], 10.0, 0.5)
        self.assertEqual([entry["at"] for entry in path], [10.0, 10.5, 11.0])
        creature = {"x": 2.0, "y": 1.0, "z": 0.0, "state": {"path": path}}
        self.assertEqual([where(creature, at) for at in (9.0, 10.2, 10.5, 12.0)],
                         [(0, 1, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0)])
        self.assertEqual(where({"x": 3.0, "y": 1.0, "z": 3.0, "state": {}}, 0.0), (3, 1, 3))

    def test_rolls_are_fixed_by_the_seed_the_creature_its_turn_and_the_channel(self):
        self.assertEqual(roll("7", 4, 2, 40), roll("7", 4, 2, 40))
        self.assertEqual(len({roll("7", 4, 2, 40), roll("8", 4, 2, 40), roll("7", 5, 2, 40), roll("7", 4, 3, 40),
                              roll("7", 4, 2, 41)}), 5)


class ActTests(unittest.TestCase):
    def test_wandering_stays_standable_dry_and_within_twelve_blocks_of_home(self):
        grid, creatures = meadow({(2, 1, 2): "stone", (-3, 1, 1): "stone", (-3, 2, 1): "stone"}), herd()
        cow = animal(creatures)
        at, seen = 0.0, set()
        for _ in range(300):
            at = max(at, cow["next_at"])
            seen.add(act(cow, scene(grid, creatures, at)))
            for entry in cow["state"].get("path") or []:
                cell = (entry["x"], entry["y"], entry["z"])
                self.assertTrue(grid.standable(cell) and not grid.swimming(cell), cell)
                self.assertLessEqual(math.hypot(cell[0], cell[2]), LEASH)
        self.assertEqual(seen, {"graze", "wander", "idle"})
        self.assertEqual(cow["state"]["turn"], 300)

    def test_an_animal_that_strayed_past_its_leash_heads_home(self):
        grid, creatures = meadow(), herd()
        cow = animal(creatures, cell=(0, 1, 20), home=[0, 1, 0])
        for turn in range(40):
            cow["state"]["turn"] = turn
            act(cow, scene(grid, creatures, float(turn * 10)))
            if cow["state"].get("path"):
                break
        path = cow["state"]["path"]
        self.assertLess(math.hypot(path[-1]["x"], path[-1]["z"]), 20)

    def test_flee_runs_about_eight_blocks_away_at_double_speed_then_calms(self):
        grid, creatures = meadow(), herd()
        cow = animal(creatures, cell=(-10, 1, 0))
        run_away(cow, KINDS["cow"], scene(grid, creatures, 100.0), (-9, 1, 0))
        path = cow["state"]["path"]
        self.assertEqual(len(path), FLEE_BLOCKS + 1)
        distances = [math.hypot(entry["x"] + 9, entry["z"]) for entry in path]
        self.assertEqual(distances, sorted(distances))
        self.assertAlmostEqual(path[1]["at"] - path[0]["at"], KINDS["cow"].speed / 2)
        self.assertEqual((cell_of(cow), cow["state"]["pose"]), ((path[-1]["x"], 1, path[-1]["z"]), "fleeing"))
        self.assertAlmostEqual(cow["state"]["calm_until"], path[-1]["at"] + CALM_SECONDS)
        self.assertGreater(cow["next_at"], path[-1]["at"])

    def test_a_hunting_mimo_close_by_scares_animals_but_not_fish_and_not_twice_in_a_row(self):
        grid, creatures = meadow(), herd()
        cow, fish = animal(creatures, cell=(26, 1, 0)), animal(creatures, "fish", (5, 0, 0))
        self.assertNotEqual(act(dict(cow), scene(grid, creatures, 0.0)), "flee")  # Mimo is not hunting
        hunting = pet(30, "hunt")
        self.assertEqual(act(cow, scene(grid, creatures, 0.0, state=hunting)), "flee")
        self.assertNotEqual(act(cow, scene(grid, creatures, cow["next_at"], state=pet(cell_of(cow)[0] + 2, "hunt"))),
                            "flee")  # calm for a while
        self.assertEqual(act(fish, scene(grid, creatures, 0.0, state=pet(5, "hunt"))), "swim")

    def test_fish_only_swim_through_water(self):
        grid, creatures = meadow(), herd()
        fish = animal(creatures, "fish", (5, 0, 0))
        at = 0.0
        for _ in range(50):
            at = max(at, fish["next_at"])
            act(fish, scene(grid, creatures, at))
            self.assertEqual(fish["state"]["pose"], "swimming")
            for entry in fish["state"]["path"]:
                self.assertTrue(grid.water((entry["x"], entry["y"], entry["z"])))

    def test_the_same_world_does_the_same_thing_and_the_pace_shortens_every_wait(self):
        grid = meadow()
        runs = []
        for pace in (1.0, 1.0, 10.0):
            creatures = herd()
            cow = animal(creatures)
            for turn in range(20):
                act(cow, scene(grid, creatures, float(turn * 10), pace=pace))
            runs.append((cell_of(cow), cow["next_at"] - 190.0))
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[2][0], runs[0][0])
        self.assertAlmostEqual(runs[2][1], runs[0][1] / 10, places=2)

    def test_a_dead_creature_or_an_unknown_kind_does_nothing(self):
        grid, creatures = meadow(), herd()
        self.assertIsNone(act(animal(creatures, pose="dead"), scene(grid, creatures)))
        stranger = animal(creatures)
        stranger["kind"] = "dragon"
        self.assertIsNone(act(stranger, scene(grid, creatures)))

    def test_a_new_action_registers_in_priority_order_and_comes_first(self):
        grid, creatures = meadow(), herd()
        sit = register_action(CreatureAction("test_sit", 5, lambda creature, kind, scene: True,
                                             lambda creature, kind, scene: creature["state"].update(pose="sitting")))
        try:
            self.assertEqual(CREATURE_ACTIONS[0], sit)
            cow = animal(creatures)
            self.assertEqual((act(cow, scene(grid, creatures)), cow["state"]["pose"]), ("test_sit", "sitting"))
        finally:
            CREATURE_ACTIONS.remove(sit)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_creature_acts.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.acts'`.

- [ ] **Step 3: Write the moves**

Create `backend/survival/creatures/moves.py`:

```python
"""How creatures move: greedy one-block steps by the Grid's rules, seeded rolls, and where one is.

There is no path search. A creature steps to one of its 4 neighbours at a time by the rules
Mimo's paths follow (backend.survival.pathing.moves: level, one up with headroom, or down at most
3). A land creature never steps onto water (a cell whose floor is water), and a fish only ever
moves from water cell to water cell. Each move is a short timed path, like Mimo's walks, so the
viewer can replay it: the creature's row holds the cell the move ends in, and `where` says where
it is along the way at any moment. Chance comes from `roll`, fixed by the world seed, the
creature, its turn and a channel, so a world always does the same thing.
"""

from __future__ import annotations

import math

from backend.services.worldgen import hash32
from backend.survival.creatures.table import cell_of
from backend.survival.grid import Cell, Grid
from backend.survival.pathing import moves

WATER_SIDES = ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0))


def roll(seed: str, number: int, turn: int, channel: int) -> float:
    """A number in [0, 1) fixed by the world seed, the creature's id, its turn and the channel."""
    return hash32(number, turn, 0, seed, channel) / 4294967296


def steps(grid: Grid, cell: Cell, water: bool) -> list[Cell]:
    """The cells a creature can step to from `cell`: water cells around a fish, else the cells Mimo
    could walk to in one move that are not on the water."""
    if water:
        x, y, z = cell
        return [(x + dx, y + dy, z + dz) for dx, dy, dz in WATER_SIDES if grid.water((x + dx, y + dy, z + dz))]
    return [step for step in moves(grid, cell) if not grid.swimming(step)]


def timed(start: Cell, cells: list[Cell], at: float, seconds: float) -> list[dict]:
    """The start and each cell after it with the server time the creature gets there."""
    path = [{"x": start[0], "y": start[1], "z": start[2], "at": round(at, 3)}]
    for number, cell in enumerate(cells, start=1):
        path.append({"x": cell[0], "y": cell[1], "z": cell[2], "at": round(at + number * seconds, 3)})
    return path


def where(creature: dict, at: float) -> Cell:
    """The cell a creature is in at `at`: the last cell of its move reached by then (the move's
    first cell before it starts), or where it stands when it has no move."""
    path = creature["state"].get("path")
    if not path:
        return cell_of(creature)
    spot = path[0]
    for entry in path:
        if entry["at"] <= at:
            spot = entry
    return spot["x"], spot["y"], spot["z"]


def heading(start: Cell, end: Cell, fallback: float) -> float:
    """Radians around +y from `start` toward `end` (0 faces +z, as in the viewer), or `fallback`."""
    dx, dz = end[0] - start[0], end[2] - start[2]
    return fallback if dx == 0 and dz == 0 else math.atan2(dx, dz)


def move(creature: dict, cells: list[Cell], at: float, seconds: float, pose: str) -> float:
    """Start a move through `cells` from where the creature is at `at`, `seconds` per block, in
    `pose`. The row moves to the last cell at once; returns when the move ends."""
    start = where(creature, at)
    path = timed(start, cells, at, seconds)
    end = cells[-1] if cells else start
    creature["x"], creature["y"], creature["z"] = map(float, end)
    before = cells[-2] if len(cells) > 1 else start
    creature["heading"] = heading(before, end, creature["heading"])
    creature["state"].update(path=path, pose=pose)
    return path[-1]["at"]
```

- [ ] **Step 4: Write the creature-action registry and L1's actions**

Create `backend/survival/creatures/acts.py`:

```python
"""What a creature does when its turn comes: the creature-action registry.

A CreatureAction is data, like a reflex: a name, a priority (lower is checked first), a `when`
check and an `act` that starts the creature's next move or pose and sets when it acts again
(`next_at`). `act(creature, scene)` runs the first action whose check holds. L1 registers:

- flee (10): a passive land animal within 6 blocks of Mimo while Mimo is hunting runs about 8
  blocks away from it at double speed, then stays calm for 8 seconds (it does not flee from a
  hunting Mimo again until then). A creature that is hit flees at once (backend.survival.creatures
  .combat calls `run_away`), whatever its calm.
- swim (20): a fish moves 1 or 2 cells through the water, then drifts 2 to 6 seconds.
- graze (30): three times in ten, a land animal lowers its head and grazes for 3 to 6 seconds.
- wander (40): otherwise, two times in three, it walks 1 to 3 blocks to random standable
  neighbours, staying within 12 blocks of its home (the cell it spawned in) or heading back to it,
  then pauses 1 to 4 seconds.
- idle (90): else it stands still for 2 to 5 seconds.

L2's hostile kinds register their chase and attack here the same way. Every duration is in
server seconds and is divided by the action scale (`Scene.pace`, MIMO_ACTION_SCALE), like Mimo's
own steps. Nothing here searches for a path or edits a block.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from backend.survival.creatures.kinds import Kind, huntable, kind_of
from backend.survival.creatures.moves import move, roll, steps, where
from backend.survival.creatures.table import Herd, dead
from backend.survival.grid import Cell, Grid

FLEE_BLOCKS = 8
SCARE_REACH = 6.0
CALM_SECONDS = 8.0
FLEE_PAUSE = 0.5
LEASH = 12.0
GRAZE_CHANCE = 0.3
WANDER_CHANCE = 2 / 3
WANDER_MOST = 3
WANDER_PAUSE = (1.0, 4.0)
GRAZE_SECONDS = (3.0, 6.0)
IDLE_SECONDS = (2.0, 5.0)
SWIM_PAUSE = (2.0, 6.0)
# Roll channels: each choice rolls on its own channel.
GRAZE, WANDER, LENGTH, PAUSE, STEP = 40, 41, 42, 43, 50


@dataclass
class Scene:
    """What creatures act in at one moment: the world, Mimo, and the time."""

    grid: Grid
    herd: Herd
    seed: str
    state: dict  # Mimo's state: where it is and what it is doing (L2's attacks hurt it through here)
    at: float
    pace: float = 1.0  # MIMO_ACTION_SCALE: moves and pauses are this many times shorter
    events: list = field(default_factory=list)

    @property
    def pet(self) -> Cell:
        position = self.state["position"]
        return round(position["x"]), round(position["y"]), round(position["z"])

    @property
    def hunting(self) -> bool:
        return (self.state.get("brain") or {}).get("purpose") == "hunt"

    def roll(self, creature: dict, channel: int) -> float:
        return roll(self.seed, creature["id"], creature["state"].get("turn", 0), channel)

    def between(self, creature: dict, span: tuple[float, float], channel: int) -> float:
        """A duration from `span` (server seconds at the normal pace), divided by the pace."""
        low, high = span
        return (low + (high - low) * self.roll(creature, channel)) / self.pace


@dataclass(frozen=True)
class CreatureAction:
    name: str
    priority: int
    when: Callable[[dict, Kind, Scene], bool]
    act: Callable[[dict, Kind, Scene], None]


CREATURE_ACTIONS: list[CreatureAction] = []


def register_action(action: CreatureAction) -> CreatureAction:
    """Add an action (or replace the one with the same name), keeping the list in priority order."""
    CREATURE_ACTIONS[:] = sorted([known for known in CREATURE_ACTIONS if known.name != action.name] + [action],
                                 key=lambda known: known.priority)
    return action


def act(creature: dict, scene: Scene) -> str | None:
    """Run the first registered action whose check holds, count the turn and return its name.
    A dead creature, or one of a kind no longer registered, does nothing."""
    kind = kind_of(creature["kind"])
    if kind is None or dead(creature):
        return None
    for action in CREATURE_ACTIONS:
        if action.when(creature, kind, scene):
            action.act(creature, kind, scene)
            creature["state"]["turn"] = creature["state"].get("turn", 0) + 1
            return action.name
    return None


def flat_distance(a: Cell, b: Cell) -> float:
    return math.hypot(a[0] - b[0], a[2] - b[2])


def pause(creature: dict, scene: Scene, pose: str, span: tuple[float, float], channel: int) -> None:
    """Stand still in `pose` for a while (the last move stays in the state, finished)."""
    creature["state"]["pose"] = pose
    creature["next_at"] = scene.at + scene.between(creature, span, channel)


# flee ------------------------------------------------------------------------------------------

def run_away(creature: dict, kind: Kind, scene: Scene, danger: Cell) -> None:
    """Run up to FLEE_BLOCKS blocks away from `danger` at double speed, each step to the neighbour
    farthest from it, stopping when none gets farther; then stay calm for CALM_SECONDS."""
    cell, cells = where(creature, scene.at), []
    for _ in range(FLEE_BLOCKS):
        options = [step for step in steps(scene.grid, cell, kind.water) if step not in cells]
        if not options:
            break
        best = max(options, key=lambda step: flat_distance(step, danger))
        if flat_distance(best, danger) <= flat_distance(cell, danger):
            break
        cells.append(best)
        cell = best
    ends = move(creature, cells, scene.at, kind.speed / 2 / scene.pace, "fleeing")
    creature["next_at"] = ends + FLEE_PAUSE / scene.pace
    creature["state"]["calm_until"] = ends + CALM_SECONDS / scene.pace


def scared(creature: dict, kind: Kind, scene: Scene) -> bool:
    return (huntable(kind) and scene.hunting and scene.at >= creature["state"].get("calm_until", -math.inf)
            and flat_distance(where(creature, scene.at), scene.pet) <= SCARE_REACH)


register_action(CreatureAction("flee", 10, scared, lambda creature, kind, scene: run_away(creature, kind, scene,
                                                                                           scene.pet)))


# swim ------------------------------------------------------------------------------------------

def swim(creature: dict, kind: Kind, scene: Scene) -> None:
    cell, cells = where(creature, scene.at), []
    for number in range(1 + int(scene.roll(creature, LENGTH) * 2)):
        options = [step for step in steps(scene.grid, cell, True) if step not in cells]
        if not options:
            break
        cell = options[int(scene.roll(creature, STEP + number) * len(options))]
        cells.append(cell)
    ends = move(creature, cells, scene.at, kind.speed / scene.pace, "swimming")
    creature["next_at"] = ends + scene.between(creature, SWIM_PAUSE, PAUSE)


register_action(CreatureAction("swim", 20, lambda creature, kind, scene: kind.water, swim))


# graze -----------------------------------------------------------------------------------------

register_action(CreatureAction(
    "graze", 30, lambda creature, kind, scene: not kind.water and scene.roll(creature, GRAZE) < GRAZE_CHANCE,
    lambda creature, kind, scene: pause(creature, scene, "grazing", GRAZE_SECONDS, PAUSE)))


# wander ----------------------------------------------------------------------------------------

def wander_cells(creature: dict, scene: Scene) -> list[Cell]:
    """1 to 3 random steps, each to a standable neighbour within LEASH blocks of home, or the one
    nearest home when it has strayed beyond (a flee can take it past the leash)."""
    home = tuple(creature["state"].get("home") or where(creature, scene.at))
    cell, cells = where(creature, scene.at), []
    for number in range(1 + int(scene.roll(creature, LENGTH) * WANDER_MOST)):
        options = [step for step in steps(scene.grid, cell, False) if step not in cells]
        near = [step for step in options if flat_distance(step, home) <= LEASH]
        if not near and options:
            near = [min(options, key=lambda step: (flat_distance(step, home), step))]
        if not near:
            break
        cell = near[int(scene.roll(creature, STEP + number) * len(near))]
        cells.append(cell)
    return cells


def wander(creature: dict, kind: Kind, scene: Scene) -> None:
    cells = wander_cells(creature, scene)
    if not cells:
        pause(creature, scene, "idle", IDLE_SECONDS, PAUSE)
        return
    ends = move(creature, cells, scene.at, kind.speed / scene.pace, "walking")
    creature["next_at"] = ends + scene.between(creature, WANDER_PAUSE, PAUSE)


register_action(CreatureAction(
    "wander", 40, lambda creature, kind, scene: not kind.water and scene.roll(creature, WANDER) < WANDER_CHANCE,
    wander))


# idle ------------------------------------------------------------------------------------------

register_action(CreatureAction("idle", 90, lambda creature, kind, scene: True,
                               lambda creature, kind, scene: pause(creature, scene, "idle", IDLE_SECONDS, PAUSE)))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_creature_acts.py"`
Expected: `Ran 11 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 631 tests` … `OK` (11 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/creatures/moves.py backend/survival/creatures/acts.py backend/tests/test_survival_creature_acts.py
git commit -m "feat: move creatures one block at a time through a creature-action registry" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 3: Herds near Mimo, in the tick

**Files:**
- Create: `backend/survival/creatures/spawning.py`, `backend/survival/creatures/simulate.py`
- Modify: `backend/survival/tick.py` (the creature hook, beside renewal)
- Test: `backend/tests/test_survival_herds.py`

**Interfaces:**
- Consumes: Tasks 1 and 2 (`Herd` and its chunk methods, `Scene`, `act`, `land_kinds`, `water_kinds`, `kind_of`, `dead`); `worldgen.biome_at`, `terrain_height`, `SEA_LEVEL` and `hash32`; `grid.CHUNK`; `clock.DAY_SECONDS`; the way `tick.advance_world` runs `run_renewal`.
- Produces:
  - `backend.survival.creatures.spawning`: `SIM_REACH = 48.0`, `PASSIVE_CAP = 24`, `FISH_PER_REGION = 6`, `REGAIN_SECONDS = 3 * DAY_SECONDS`, `NEW_CHUNKS = 8`; `chunk_roll(seed, chunk, index, channel, salt=0) -> float`; `chunks_near(x, z, reach) -> list[(cx, cz)]`; `herd_count(seed, chunk) -> int` (0, 1 or 2); `plan_herd(grid, seed, chunk, index, salt=0) -> (Kind, cells) | None`; `fish_school(grid, seed, chunk) -> (Kind, cells) | None`; `populate(scene, loaded, scale) -> list[dict]` (the creatures it added).
  - `backend.survival.creatures.simulate`: `MAX_ACTS = 24`, `DEAD_KEEP = 10.0`; `simulate(state, context, at)`, which needs `context.db` and `context.grid.herd` and does nothing without them.
  - `tick.run_creatures(state, context, at)` runs `simulate` after `run_renewal` at both points of `advance_world`; a crash is logged once (`log_once(logger, "creatures", error)`) and the tick goes on.

- [ ] **Step 1: Write the failing tests**

The spawner reads worldgen's height and biome, so the unit tests patch `terrain_height`, `biome_at` and `SEA_LEVEL` in `spawning` to make a flat meadow; the tick tests hatch a real world and tick it.

Create `backend/tests/test_survival_herds.py`:

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
from backend.survival.actions import ActionContext
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.simulate import DEAD_KEEP, MAX_ACTS, simulate
from backend.survival.creatures.spawning import (
    FISH_PER_REGION, NEW_CHUNKS, PASSIVE_CAP, SIM_REACH, chunks_near, herd_count, plan_herd, populate,
)
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables, dead
from backend.survival.grid import Grid, world_grid
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.tick import advance_world
from backend.survival.world import SurvivalWorld

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
BORN = 1_000_000.0


def flat(water=()):
    """Grass at y 0, or water in the `water` columns."""
    return Grid(lambda x, y, z: ("water" if (x, z) in water else "grass") if y == 0 else "dirt" if y < 0 else "air")


def pet(x=8, z=8):
    return {"name": "Pip", "world_seed": "1", "position": {"x": float(x), "y": 1.0, "z": float(z)}, "brain": {}}


def herd():
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    return Herd(db)


def context(grid, db):
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=db)


def flatland(test):
    """Flat meadow for the spawner: ground at y 0 everywhere, sea level 2 (so no natural water)."""
    for target, value in (("terrain_height", lambda x, z, seed: 0), ("biome_at", lambda x, z, seed: "meadow"),
                          ("SEA_LEVEL", -9)):
        patcher = patch(f"backend.survival.creatures.spawning.{target}", value)
        patcher.start()
        test.addCleanup(patcher.stop)


class SpawnTests(unittest.TestCase):
    def setUp(self):
        flatland(self)

    def test_chunks_within_reach_nearest_first_when_populating(self):
        near = chunks_near(8, 8, SIM_REACH)
        self.assertIn((0, 0), near)
        self.assertIn((3, 0), near)
        self.assertNotIn((4, 4), near)  # its nearest column is 56 blocks off on each axis
        self.assertEqual(len(near), len(set(near)))

    def test_a_chunk_rolls_the_same_herds_every_time(self):
        grid = flat()
        counts = {herd_count("1", (cx, 0)) for cx in range(40)}
        self.assertEqual(counts, {0, 1, 2})
        first = plan_herd(grid, "1", (3, 5), 0)
        self.assertEqual(plan_herd(flat(), "1", (3, 5), 0), first)
        kind, cells = first
        self.assertIn(kind.name, ("rabbit", "chicken", "sheep", "cow"))
        self.assertTrue(kind.herd[0] <= len(cells) <= kind.herd[1])
        self.assertTrue(all(3 * 16 - 1 <= x <= 4 * 16 and y == 1 for x, y, _ in cells))

    def test_herds_spawn_once_per_chunk_as_mimo_comes_near_and_stop_at_the_cap(self):
        grid, creatures = flat(), herd()
        state = pet()
        scene = Scene(grid, creatures, "1", state, 10.0)
        added = populate(scene, [], 1.0)
        self.assertTrue(added)
        noted = creatures.chunks((-9, -9), (9, 9))
        self.assertEqual(len(noted), NEW_CHUNKS)  # the rest wait for the next call
        self.assertLessEqual(len(added), PASSIVE_CAP)
        for _ in range(10):
            added += populate(Scene(grid, creatures, "1", state, 10.0), creatures.near(8, 8, SIM_REACH), 1.0)
        self.assertEqual(set(creatures.chunks((-9, -9), (9, 9))), set(chunks_near(8, 8, SIM_REACH)))
        self.assertEqual(len(creatures.near(8, 8, SIM_REACH)), PASSIVE_CAP)
        for creature in added:
            self.assertEqual(creature["state"]["home"], list(cell_of(creature)))
            self.assertTrue(grid.standable(cell_of(creature)))
            self.assertEqual(creature["health"], KINDS[creature["kind"]].health)
        self.assertEqual(populate(Scene(grid, creatures, "1", state, 11.0), creatures.near(8, 8, SIM_REACH), 1.0), [])

    def test_a_school_of_fish_spawns_in_natural_water_and_a_region_holds_at_most_six(self):
        with patch("backend.survival.creatures.spawning.SEA_LEVEL", 0), \
                patch("backend.survival.creatures.spawning.terrain_height", lambda x, z, seed: -1):
            lake = {(x, z) for x in range(-40, 60) for z in range(-40, 60)}
            grid, creatures = flat(lake), herd()
            for _ in range(10):
                populate(Scene(grid, creatures, "1", pet(), 10.0), creatures.near(8, 8, SIM_REACH), 1.0)
        fish = [creature for creature in creatures.near(8, 8, 100) if creature["kind"] == "fish"]
        self.assertTrue(fish)
        for creature in fish:
            self.assertTrue(grid.water(cell_of(creature)))
        regions = {}
        for creature in fish:
            key = (int(creature["x"]) // 16, int(creature["z"]) // 16)
            regions[key] = regions.get(key, 0) + 1
        self.assertLessEqual(max(regions.values()), FISH_PER_REGION)

    def test_a_chunk_whose_animals_were_all_hunted_gets_a_herd_back_after_three_game_days(self):
        grid, creatures = flat(), herd()
        with patch("backend.survival.creatures.spawning.chunks_near", lambda x, z, reach: [(0, 0)]), \
                patch("backend.survival.creatures.spawning.herd_count", lambda seed, chunk: 1):
            first = populate(Scene(grid, creatures, "1", pet(), 0.0), [], 1.0)
            self.assertTrue(first)
            for creature in first:
                creatures.remove(creature["id"])
                creatures.lost([0, 0], 100.0)
            again = populate(Scene(grid, creatures, "1", pet(), 100.0 + 3 * DAY_SECONDS - 1), [], 1.0)
            self.assertEqual(again, [])
            back = populate(Scene(grid, creatures, "1", pet(), 100.0 + 3 * DAY_SECONDS), [], 1.0)
        self.assertTrue(back)
        self.assertEqual(creatures.chunks((0, 0), (0, 0))[(0, 0)]["animals"], len(back))


class SimulateTests(unittest.TestCase):
    def setUp(self):
        flatland(self)

    def test_only_creatures_near_mimo_take_turns_and_at_most_max_acts_a_call(self):
        grid, creatures = flat(), herd()
        with patch("backend.survival.creatures.simulate.populate", lambda scene, loaded, scale: []):
            near = [creatures.add("cow", (x, 1, 0), 10.0, 0.0, 0.0, {"home": [x, 1, 0]}) for x in range(-15, 15)]
            far = creatures.add("cow", (300, 1, 0), 10.0, 0.0, 0.0, {"home": [300, 1, 0]})
            grid.herd = creatures
            simulate(pet(0, 0), context(grid, creatures.db), 5.0)
        turned = [creature for creature in near if creatures.get(creature["id"])["next_at"] > 5.0]
        self.assertEqual(len(turned), MAX_ACTS)
        self.assertEqual(creatures.get(far["id"])["next_at"], 0.0)

    def test_dead_creatures_stay_for_the_puff_then_go(self):
        grid, creatures = flat(), herd()
        grid.herd = creatures
        body = creatures.add("cow", (0, 1, 0), 0.0, 0.0, 99.0, {"pose": "dead", "dead_at": 100.0})
        with patch("backend.survival.creatures.simulate.populate", lambda scene, loaded, scale: []):
            simulate(pet(0, 0), context(grid, creatures.db), 100.0 + DEAD_KEEP)
            self.assertTrue(dead(creatures.get(body["id"])))
            simulate(pet(0, 0), context(grid, creatures.db), 100.0 + DEAD_KEEP + 1)
        self.assertIsNone(creatures.get(body["id"]))

    def test_without_a_database_nothing_happens(self):
        simulate(pet(), context(flat(), None), 5.0)


class TickTests(unittest.TestCase):
    def hatched(self, root):
        registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
        life = hatch(registry, random.Random(3), timestamp=BORN)
        return SurvivalWorld(registry.world_path(life))

    def creatures_of(self, world):
        with world.connect() as db:
            return [tuple(row) for row in db.execute("SELECT id, kind, x, y, z, health, next_at FROM creatures "
                                                    "ORDER BY id").fetchall()]

    def test_the_tick_spawns_and_moves_animals_near_mimo_the_same_way_every_time(self):
        runs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as root:
                world = self.hatched(root)
                for second in range(1, 301):
                    advance_world(world, BORN + second, 1.0)
                runs.append(self.creatures_of(world))
                with world.connect() as db:
                    grid, state = world_grid(db, world.seed), world.state()
                    found = grid.herd.near(state["position"]["x"], state["position"]["z"], SIM_REACH)
                    land = [creature for creature in found if not KINDS[creature["kind"]].water]
                    self.assertTrue(land)
                    self.assertLessEqual(len(land), PASSIVE_CAP)
                    self.assertTrue(any(creature["state"].get("path") for creature in land))
                    for creature in found:
                        cell = cell_of(creature)
                        self.assertTrue(grid.water(cell) if creature["kind"] == "fish" else grid.standable(cell))
        self.assertEqual(runs[0], runs[1])

    def test_a_crashing_creature_hook_never_stops_the_tick(self):
        with tempfile.TemporaryDirectory() as root:
            world = self.hatched(root)
            with patch("backend.survival.tick.simulate", side_effect=RuntimeError("boom")), \
                    self.assertLogs("backend.survival.tick", "ERROR"):
                state = advance_world(world, BORN + 30, 1.0)
        self.assertEqual(state["last_tick_at"], BORN + 30)

    def test_creatures_cost_well_under_twenty_milliseconds_a_slice(self):
        spent = []

        def timed(*args):
            start = time.perf_counter()
            real(*args)
            spent.append(time.perf_counter() - start)

        real = tick.simulate
        with tempfile.TemporaryDirectory() as root:
            world = self.hatched(root)
            with patch("backend.survival.tick.simulate", timed):
                for minute in range(1, 61):
                    advance_world(world, BORN + 60 * minute, 1.0)
        self.assertLess(sum(spent) / 60, 0.020)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_herds.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.simulate'`.

- [ ] **Step 3: Write the spawner**

Create `backend/survival/creatures/spawning.py`:

```python
"""Where animals come from (spec L1, "Spawning").

The first time Mimo comes within 48 blocks of a 16x16 chunk, the chunk's herds spawn: 0, 1 or 2
of them (a roll fixed by the world seed and the chunk), each of a kind that lives in the biome at
its spot, and a school of fish when the chunk has natural water. Spots are rolled columns in the
chunk whose cell above the ground is standable and dry, and not a cell something Mimo built
claims; a herd spreads over the spot and the cells around it. The chunk is noted in
creature_chunks, so it never spawns twice.

Numbers are capped: a herd or school stops growing once 24 passive creatures (animals and fish)
are within 48 blocks of Mimo, and a school once its 16x16 water region holds 6 fish. Spawning
takes at most NEW_CHUNKS chunks a call, nearest first. A chunk whose land animals have all
been gone (hunted) for 3 game days regains one herd. (L3's creature seeds add more.)
"""

from __future__ import annotations

import math

from backend.services.worldgen import SEA_LEVEL, biome_at, hash32, terrain_height
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.kinds import Kind, kind_of, land_kinds, water_kinds
from backend.survival.creatures.table import dead
from backend.survival.grid import CHUNK, Cell, Grid

SIM_REACH = 48.0
PASSIVE_CAP = 24
FISH_PER_REGION = 6
REGAIN_SECONDS = 3 * DAY_SECONDS  # game seconds a chunk's land animals stay gone before a herd comes back
NEW_CHUNKS = 8  # chunks whose herds spawn in one call, nearest first; the rest wait for the next
HERD_ODDS = (0.35, 0.8)  # a chunk rolls no herd below the first, one below the second, else two
SPOT_TRIES = 6
FIRST_TURN_WITHIN = 2.0  # server seconds: new creatures take their first turn within this, not all at once
SPREAD = ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))
# Roll channels.
HERDS, SPOT_X, SPOT_Z, KIND, SIZE, FIRST = 60, 61, 62, 63, 64, 65

Herd = tuple[Kind, list[Cell]]


def chunk_roll(seed: str, chunk: tuple[int, int], index: int, channel: int, salt: int = 0) -> float:
    """A number in [0, 1) fixed by the world seed, the chunk, which herd or try it is and the channel."""
    return hash32(chunk[0], index + salt * 64, chunk[1], seed, channel) / 4294967296


def chunks_near(x: int, z: int, reach: float) -> list[tuple[int, int]]:
    """The chunks with some column within `reach` blocks of (x, z), nearest rows first."""
    found = []
    for cx in range(math.floor((x - reach) / CHUNK), math.floor((x + reach) / CHUNK) + 1):
        for cz in range(math.floor((z - reach) / CHUNK), math.floor((z + reach) / CHUNK) + 1):
            dx = max(cx * CHUNK - x, 0, x - (cx * CHUNK + CHUNK - 1))
            dz = max(cz * CHUNK - z, 0, z - (cz * CHUNK + CHUNK - 1))
            if math.hypot(dx, dz) <= reach:
                found.append((cx, cz))
    return found


def herd_count(seed: str, chunk: tuple[int, int]) -> int:
    chance = chunk_roll(seed, chunk, 0, HERDS)
    return 0 if chance < HERD_ODDS[0] else 1 if chance < HERD_ODDS[1] else 2


def dry_ground(grid: Grid, cell: Cell) -> bool:
    return grid.standable(cell) and not grid.swimming(cell) and not grid.claimed(cell)


def plan_herd(grid: Grid, seed: str, chunk: tuple[int, int], index: int, salt: int = 0) -> Herd | None:
    """The kind and cells of a chunk's `index`-th herd, or None when no rolled spot fits."""
    cx, cz = chunk
    for attempt in range(SPOT_TRIES):
        roll_at = index * SPOT_TRIES + attempt
        x = cx * CHUNK + int(chunk_roll(seed, chunk, roll_at, SPOT_X, salt) * CHUNK)
        z = cz * CHUNK + int(chunk_roll(seed, chunk, roll_at, SPOT_Z, salt) * CHUNK)
        kinds = land_kinds(biome_at(x, z, seed))
        spot = (x, terrain_height(x, z, seed) + 1, z)
        if not kinds or not dry_ground(grid, spot):
            continue
        kind = kinds[int(chunk_roll(seed, chunk, index, KIND, salt) * len(kinds))]
        low, high = kind.herd
        size = low + int(chunk_roll(seed, chunk, index, SIZE, salt) * (high - low + 1))
        cells = []
        for dx, dz in SPREAD:
            cell = (x + dx, terrain_height(x + dx, z + dz, seed) + 1, z + dz)
            if len(cells) < size and dry_ground(grid, cell):
                cells.append(cell)
        return kind, cells
    return None


def fish_school(grid: Grid, seed: str, chunk: tuple[int, int]) -> Herd | None:
    """Fish for a rolled column of natural water in the chunk (top water layer), or None."""
    kinds = water_kinds()
    if not kinds:
        return None
    cx, cz = chunk
    for attempt in range(SPOT_TRIES):
        x = cx * CHUNK + int(chunk_roll(seed, chunk, 100 + attempt, SPOT_X) * CHUNK)
        z = cz * CHUNK + int(chunk_roll(seed, chunk, 100 + attempt, SPOT_Z) * CHUNK)
        if terrain_height(x, z, seed) >= SEA_LEVEL or not grid.water((x, SEA_LEVEL, z)):
            continue
        kind = kinds[0]
        low, high = kind.herd
        size = low + int(chunk_roll(seed, chunk, 100, SIZE) * (high - low + 1))
        cells = [(x + dx, SEA_LEVEL, z + dz) for dx, dz in SPREAD if grid.water((x + dx, SEA_LEVEL, z + dz))]
        return kind, cells[:size]
    return None


def passive(creature: dict) -> bool:
    kind = kind_of(creature["kind"])
    return kind is not None and not kind.hostile


def born(scene: Scene, kind: Kind, cell: Cell, chunk: tuple[int, int], number: int) -> dict:
    """A new creature of `kind` in `cell`, at home there, taking its first turn within 2 seconds."""
    first = chunk_roll(scene.seed, chunk, number, FIRST, int(scene.at)) * FIRST_TURN_WITHIN / scene.pace
    state = {"home": list(cell), "chunk": list(chunk), "pose": "swimming" if kind.water else "idle", "turn": 0}
    return scene.herd.add(kind.name, cell, kind.health, scene.at, scene.at + first, state)


def populate(scene: Scene, loaded: list[dict], scale: float) -> list[dict]:
    """Spawn the herds of up to NEW_CHUNKS chunks Mimo came near for the first time, nearest first,
    and bring a herd back to each chunk near Mimo whose land animals have been gone for 3 game
    days. `loaded` are the creatures within 48 blocks of Mimo. Returns the creatures it added."""
    x, _, z = scene.pet
    near = sorted(chunks_near(x, z, SIM_REACH),
                  key=lambda chunk: (math.hypot(chunk[0] * CHUNK + 8 - x, chunk[1] * CHUNK + 8 - z), chunk))
    known = scene.herd.chunks((min(c[0] for c in near), min(c[1] for c in near)),
                              (max(c[0] for c in near), max(c[1] for c in near)))
    alive = [creature for creature in loaded if not dead(creature)]
    count = sum(1 for creature in alive if passive(creature))
    added: list[dict] = []

    def place(herds: list[Herd], chunk: tuple[int, int]) -> int:
        """Add the herds' creatures as far as the caps allow; returns how many land animals came."""
        nonlocal count
        came = 0
        for kind, cells in herds:
            for cell in cells:
                region = (cell[0] // CHUNK, cell[2] // CHUNK)
                if count >= PASSIVE_CAP or (kind.water and sum(
                        1 for creature in alive + added if creature["kind"] == kind.name
                        and (int(creature["x"]) // CHUNK, int(creature["z"]) // CHUNK) == region) >= FISH_PER_REGION):
                    break
                count += 1
                came += 0 if kind.water else 1
                added.append(born(scene, kind, cell, chunk, len(added)))
        return came

    fresh = 0
    for chunk in near:
        row = known.get(chunk)
        if row is None and fresh < NEW_CHUNKS:
            fresh += 1
            rolled = herd_count(scene.seed, chunk)
            planned = (plan_herd(scene.grid, scene.seed, chunk, index) for index in range(rolled))
            herds = [herd for herd in planned if herd]
            school = fish_school(scene.grid, scene.seed, chunk)
            scene.herd.note_chunk(chunk, rolled, place(herds + ([school] if school else []), chunk), scene.at)
        elif (row is not None and row["herds"] > 0 and row["animals"] == 0 and row["empty_since"] is not None
              and (scene.at - row["empty_since"]) * scale >= REGAIN_SECONDS):
            herd = plan_herd(scene.grid, scene.seed, chunk, 0, salt=int(scene.at))
            scene.herd.regained(chunk, place([herd], chunk) if herd else 0, scene.at)
    return added
```

- [ ] **Step 4: Write the creature hook**

Create `backend/survival/creatures/simulate.py`:

```python
"""The creature hook: what advance_world runs after each chunk of Mimo's actions (spec L1,
"Creature tick").

`simulate(state, context, at)` works only near Mimo. It reads the creatures within 48 blocks of
Mimo, spawns the herds of chunks Mimo came near and brings herds back to emptied ones
(backend.survival.creatures.spawning), clears away creatures that died more than DEAD_KEEP
seconds ago (the viewer has shown their puff by then), and lets each living one whose `next_at`
has come take one turn (backend.survival.creatures.acts), earliest first, at most MAX_ACTS in one
call. Creatures farther away stay put. Moves are written to the creature rows; nothing searches
for a path and no block changes, so a call costs a few queries and a few hundred cell lookups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival.creatures.acts import Scene, act
from backend.survival.creatures.spawning import SIM_REACH, populate
from backend.survival.creatures.table import dead

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

MAX_ACTS = 24  # creature turns in one call
DEAD_KEEP = 10.0  # server seconds a dead creature stays listed, for the viewer's puff
UNKNOWN_WAIT = 60.0  # server seconds a creature of a kind no longer registered waits between turns


def simulate(state: dict, context: ActionContext, at: float) -> None:
    """Spawn, clear away and move the creatures near Mimo up to `at`. Needs the tick's database."""
    grid = context.grid
    if context.db is None or grid.herd is None:
        return
    scene = Scene(grid, grid.herd, state.get("world_seed", "0"), state, at, context.action_scale, context.events)
    scale = context.clock_at(at)["time_scale"]
    x, _, z = scene.pet
    loaded = grid.herd.near(x, z, SIM_REACH)
    loaded += populate(scene, loaded, scale)
    for creature in loaded:
        if dead(creature) and at - creature["state"].get("dead_at", at) > DEAD_KEEP:
            grid.herd.remove(creature["id"])
    due = sorted((creature for creature in loaded if not dead(creature) and creature["next_at"] <= at),
                 key=lambda creature: (creature["next_at"], creature["id"]))
    for creature in due[:MAX_ACTS]:
        if act(creature, scene) is None:
            creature["next_at"] = at + UNKNOWN_WAIT
        grid.herd.save(creature)
```

- [ ] **Step 5: Run it in the tick, beside renewal**

In `backend/survival/tick.py`, replace:

```python
write transaction. After each chunk of actions the world regrows on its own
(backend.survival.renewal), whatever mind runs Mimo.
```

with:

```python
write transaction. After each chunk of actions the world regrows on its own
(backend.survival.renewal) and the creatures near Mimo take their turns
(backend.survival.creatures.simulate), whatever mind runs Mimo.
```

and replace:

```python
from backend.survival.clock import DAY_SECONDS, action_scale as action_scale_setting, clock_at, is_night, time_scale
```

with:

```python
from backend.survival.clock import DAY_SECONDS, action_scale as action_scale_setting, clock_at, is_night, time_scale
from backend.survival.creatures.simulate import simulate
```

and replace:

```python
        log_once(logger, "renewal", error)
```

with:

```python
        log_once(logger, "renewal", error)


def run_creatures(state: dict, context: ActionContext, at: float) -> None:
    """Let the creatures near Mimo take their turns up to `at` (backend.survival.creatures.simulate).
    A crash is logged once and the tick goes on."""
    try:
        simulate(state, context, at)
    except Exception as error:
        log_once(logger, "creatures", error)
```

and replace:

```python
            run_renewal(state, context, cursor)
```

with:

```python
            run_renewal(state, context, cursor)
            run_creatures(state, context, cursor)
```

and replace:

```python
                run_renewal(state, context, timestamp)
```

with:

```python
                run_renewal(state, context, timestamp)
                run_creatures(state, context, timestamp)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_herds.py"`
Expected: `Ran 11 tests` … `OK` (a few seconds: three hatched worlds tick).

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 642 tests` … `OK` (11 new). The headless runs now have animals around Mimo. Nothing hunts yet, so Mimo's purposes do not change.

- [ ] **Step 7: Commit**

```bash
git add backend/survival/creatures/spawning.py backend/survival/creatures/simulate.py backend/survival/tick.py backend/tests/test_survival_herds.py
git commit -m "feat: spawn seeded herds near Mimo and let them take their turns in the tick" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: Meat, cooking and swords

**Files:**
- Modify: `backend/services/crafting.py` (swords; the meats cook), `backend/survival/steps.py` (meat's hunger; raw chicken's risk), `backend/survival/carrying.py` (swords are valuable), `backend/survival/cooking.py` (every raw food), `backend/survival/toolmaking.py` (the sword ladder), `backend/survival/storage.py` (hides go in the chest; replaced swords are dropped)
- Modify tests: `backend/tests/test_survival_pickers.py`, `backend/tests/test_survival_toolmaking.py` (a wooden sword now comes with the wooden pickaxe)
- Test: `backend/tests/test_survival_meat.py`

**Interfaces:**
- Consumes: `crafting.RECIPES`, `SMELTING`, `COOKING`; `steps.FOOD`, `finish_eat`, `nature.roll`; `carrying.valuable`; `cooking.cook_plan`; `toolmaking.next_tool`, `make`, `station_spots`; `storage.KEEP`, `junk`, `to_store`; `backend.tests.test_survival_storage.Home` and `LOOSE` (a pet at a finished shelter).
- Produces:
  - `crafting.RECIPES`: `wooden_sword` (2 planks, 1 sticks), `stone_sword` (2 cobblestone, 1 sticks), `iron_sword` (2 iron_ingot, 1 sticks), each at a crafting table. `SMELTING` and `COOKING` gain `raw_beef`, `raw_mutton`, `raw_chicken` and `raw_rabbit`, which cook into `cooked_*`.
  - `steps.FOOD` gains the raw and cooked meats; `steps.FOOD_RISK = {"raw_chicken": (0.25, -4.0)}` and `steps.RISK_CHANNEL = 39`; a `sick` event "… felt a little sick." when the roll hits.
  - `cooking.RAW_FOODS` (every cookable raw food, in name order); cook cooks all of them.
  - `toolmaking.SWORD_LADDER`, `open_swords(inventory) -> list[str]`, `tool_orders(inventory) -> list[tuple[str, ...]]`, `tool_steps(s, tools) -> list[dict] | None`, `tool_choice(s) -> (tools, steps) | None`; `tool_plan(s)` keeps its signature.
  - `storage.KEEP` gains `leather`, `wool`, `feather` and `rabbit_hide` (0 each); `storage.junk` lists swords a better one replaced.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_meat.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.services.crafting import COOKING, RECIPES, craft, smelt
from backend.survival import cooking, storage  # noqa: F401  (register cook, build_storage and drop_items)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.carrying import valuable
from backend.survival.grid import Grid
from backend.survival.learning import learn_from_step
from backend.survival.memory import create_memory_tables, known
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.steps import FOOD, FOOD_RISK, finish_step
from backend.survival.toolmaking import open_swords, tool_orders, tool_plan
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_storage import LOOSE, Home

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
MEATS = ("beef", "mutton", "chicken", "rabbit")


def meadow(edits=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (edits or {}).items():
        grid.put(*cell, block)
    return grid


def situation(inventory, grid=None):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state, grid or meadow(), DAY, 0.0, db)


def craft_step(recipe):
    return {"kind": "craft", "recipe": recipe}


class MeatTests(unittest.TestCase):
    def test_raw_meat_fills_a_little_and_cooks_at_a_fire_into_far_more(self):
        for meat in MEATS:
            self.assertIn(f"raw_{meat}", COOKING)
            self.assertEqual(smelt({f"raw_{meat}": 1}, f"raw_{meat}", {"campfire"}), {f"cooked_{meat}": 1})
            self.assertLessEqual(FOOD[f"raw_{meat}"], 8.0)
            self.assertTrue(25.0 <= FOOD[f"cooked_{meat}"] <= 35.0)
            self.assertTrue(valuable(f"raw_{meat}") and valuable(f"cooked_{meat}"))

    def test_the_cook_purpose_cooks_every_raw_meat_mimo_carries(self):
        s = situation({"raw_beef": 2, "raw_chicken": 1, "raw_fish": 1}, meadow({(3, 1, 0): "campfire"}))
        self.assertTrue(PURPOSES["cook"].valid(s))
        plan = PURPOSES["cook"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                                       events=[], db=s.db))
        self.assertEqual(plan, [{"kind": "cook", "item": item} for item in ("raw_beef", "raw_beef", "raw_chicken",
                                                                             "raw_fish")])
        self.assertEqual(PURPOSES["cook"].facts(s), "carrying 4 raw fish and meat and 0 wheat")

    def test_raw_chicken_is_a_gamble_that_mimo_does_not_learn_to_shun(self):
        chance, _ = FOOD_RISK["raw_chicken"]
        for roll, kind in ((chance - 0.01, "sick"), (chance + 0.01, "ate")):
            state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                     "inventory": {"raw_chicken": 1}, "vitals": {**START_VITALS, "hunger": 50.0}}
            with patch("backend.survival.nature.roll", lambda *args: roll):
                event = finish_step({"kind": "eat", "item": "raw_chicken"}, state, meadow(), 10.0)
            self.assertEqual(event[0], kind)
            self.assertEqual(state["vitals"]["health"], 96.0 if kind == "sick" else 100.0)
            self.assertEqual(state["vitals"]["hunger"], 56.0)
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        learn_from_step(state, {"kind": "eat", "item": "raw_chicken"},
                        ActionContext(grid=meadow(), clock_at=lambda at: DAY, planner=lambda *args: [], events=[],
                                      db=db), 10.0)
        self.assertEqual(known(db, "poisonous"), [])


class SwordTests(unittest.TestCase):
    def test_swords_are_made_at_a_crafting_table(self):
        self.assertEqual(craft({"planks": 2, "sticks": 1}, "wooden_sword", {"crafting_table"}), {"wooden_sword": 1})
        self.assertEqual(craft({"cobblestone": 2, "sticks": 1}, "stone_sword", {"crafting_table"}), {"stone_sword": 1})
        self.assertEqual(craft({"iron_ingot": 2, "sticks": 1}, "iron_sword", {"crafting_table"}), {"iron_sword": 1})
        for sword in ("wooden_sword", "stone_sword", "iron_sword"):
            self.assertEqual(RECIPES[sword]["station"], "crafting_table")
            self.assertTrue(valuable(sword))

    def test_a_sword_only_up_to_the_tier_of_the_best_pickaxe(self):
        self.assertEqual(open_swords({}), [])
        self.assertEqual(open_swords({"wooden_pickaxe": 1}), ["wooden_sword"])
        self.assertEqual(open_swords({"stone_pickaxe": 1}), ["stone_sword", "wooden_sword"])
        self.assertEqual(open_swords({"stone_pickaxe": 1, "wooden_sword": 1}), ["stone_sword"])
        self.assertEqual(open_swords({"iron_pickaxe": 1, "iron_sword": 1}), [])
        self.assertEqual(tool_orders({"wooden_pickaxe": 1}), [("stone_pickaxe", "stone_sword"),
                                                                ("stone_pickaxe", "wooden_sword"),
                                                                ("stone_pickaxe",), ("wooden_sword",)])

    def test_a_new_pickaxe_comes_with_the_sword_it_opens_up_when_the_materials_stretch(self):
        table = meadow({(2, 1, 0): "crafting_table"})
        both = situation({"wooden_pickaxe": 1, "wooden_sword": 1, "cobblestone": 5, "sticks": 3}, table)
        self.assertEqual(tool_plan(both), [craft_step("stone_pickaxe"), craft_step("stone_sword")])
        self.assertEqual(PURPOSES["craft_tools"].facts(both), "can make a stone pickaxe and a stone sword now")
        short = situation({"wooden_pickaxe": 1, "wooden_sword": 1, "cobblestone": 3, "sticks": 2}, table)
        self.assertEqual(tool_plan(short), [craft_step("stone_pickaxe")])
        sword = situation({"stone_pickaxe": 1, "wooden_sword": 1, "cobblestone": 2, "sticks": 1}, table)
        self.assertEqual(tool_plan(sword), [craft_step("stone_sword")])


class LeftoversTests(unittest.TestCase):
    def test_hides_wool_and_feathers_are_put_away_and_a_meal_of_meat_is_kept(self):
        home = Home({"leather": 2, "wool": 3, "feather": 4, "rabbit_hide": 1, "raw_beef": 1}, chest={})
        self.assertEqual(storage.to_store(home.situation(), home.chest),
                         [("feather", 4), ("wool", 3), ("leather", 2), ("rabbit_hide", 1)])

    def test_a_sword_a_better_one_replaced_is_dropped(self):
        junk = storage.junk(Home({**LOOSE, "wooden_sword": 1, "stone_sword": 1}).situation())
        self.assertIn(("wooden_sword", 1), junk)
        self.assertNotIn(("stone_sword", 1), junk)


if __name__ == "__main__":
    unittest.main()
```

A wooden sword now comes with the wooden pickaxe from the same three logs, and four logs make a sword for a pet that has only a pickaxe, so two older expectations change.

In `backend/tests/test_survival_pickers.py`, replace:

```python
        self.assertEqual(picks(situation(inventory={"oak_log": 4, "wooden_pickaxe": 1})), {"gather_stone"})
```

with:

```python
        self.assertEqual(picks(situation(inventory={"oak_log": 4, "wooden_pickaxe": 1})), {"craft_tools"})  # a sword
        self.assertEqual(picks(situation(inventory={"oak_log": 4, "wooden_pickaxe": 1, "wooden_sword": 1})),
                         {"gather_stone"})
```

In `backend/tests/test_survival_toolmaking.py`, replace:

```python
            craft("planks"), craft("sticks"), craft("planks"), craft("wooden_pickaxe"), mine_back(1, 1, 0)])
```

with:

```python
            craft("planks"), craft("sticks"), craft("planks"), craft("wooden_pickaxe"), craft("wooden_sword"),
            mine_back(1, 1, 0)])
```

and replace:

```python
            craft("planks"), craft("sticks"), craft("planks"), craft("wooden_pickaxe"), mine_back(0, -2, 1)])
```

with:

```python
            craft("planks"), craft("sticks"), craft("planks"), craft("wooden_pickaxe"), craft("wooden_sword"),
            mine_back(0, -2, 1)])
```

and replace:

```python
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"iron_pickaxe": 1, "oak_log": 9})))
```

with:

```python
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"iron_pickaxe": 1, "iron_sword": 1, "oak_log": 9})))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_meat.py"`
Expected: `ImportError: cannot import name 'FOOD_RISK' from 'backend.survival.steps'`.

- [ ] **Step 3: Add the sword recipes and the cooking of meat**

In `backend/services/crafting.py`, replace:

```python
    "iron_axe": {"ingredients": {"iron_ingot": 3, "sticks": 2}, "output": {"iron_axe": 1}, "station": "crafting_table"},
}
```

with:

```python
    "iron_axe": {"ingredients": {"iron_ingot": 3, "sticks": 2}, "output": {"iron_axe": 1}, "station": "crafting_table"},
    "wooden_sword": {"ingredients": {"planks": 2, "sticks": 1}, "output": {"wooden_sword": 1}, "station": "crafting_table"},
    "stone_sword": {"ingredients": {"cobblestone": 2, "sticks": 1}, "output": {"stone_sword": 1}, "station": "crafting_table"},
    "iron_sword": {"ingredients": {"iron_ingot": 2, "sticks": 1}, "output": {"iron_sword": 1}, "station": "crafting_table"},
}
```

and replace:

```python
SMELTING = {"iron_ore": "iron_ingot", "copper_ore": "copper_ingot", "sand": "glass", "clay": "brick",
            "raw_fish": "cooked_fish"}
# Food cooks at a lit campfire or a furnace and burns no fuel: the fire is already lit.
COOKING = frozenset({"raw_fish"})
```

with:

```python
SMELTING = {"iron_ore": "iron_ingot", "copper_ore": "copper_ingot", "sand": "glass", "clay": "brick",
            "raw_fish": "cooked_fish", "raw_beef": "cooked_beef", "raw_mutton": "cooked_mutton",
            "raw_chicken": "cooked_chicken", "raw_rabbit": "cooked_rabbit"}
# Food cooks at a lit campfire or a furnace and burns no fuel: the fire is already lit.
COOKING = frozenset({"raw_fish", "raw_beef", "raw_mutton", "raw_chicken", "raw_rabbit"})
```

In `backend/survival/steps.py`, replace:

```python
        "cooked_fish": 30.0, "apple": 15.0}
# Health a food changes when eaten: a red mushroom is poisonous. Poison never takes the last point
# of health (it is not a cause of death).
FOOD_HEALTH = {"red_mushroom": -10.0}
```

with:

```python
        "cooked_fish": 30.0, "apple": 15.0,
        # L1: meat from hunting. Raw it fills little; cooked at a fire it fills far more.
        "raw_beef": 8.0, "raw_mutton": 8.0, "raw_chicken": 6.0, "raw_rabbit": 6.0,
        "cooked_beef": 35.0, "cooked_mutton": 30.0, "cooked_chicken": 25.0, "cooked_rabbit": 25.0}
# Health a food changes when eaten: a red mushroom is poisonous. Poison never takes the last point
# of health (it is not a cause of death).
FOOD_HEALTH = {"red_mushroom": -10.0}
# Food that only sometimes makes Mimo sick: (chance, health). Raw chicken is a gamble, not poison, so
# Mimo never learns to shun it (backend.survival.learning); cooking makes it safe.
FOOD_RISK = {"raw_chicken": (0.25, -4.0)}
RISK_CHANNEL = 39
```

and replace:

```python
        return "sick", f"{name} ate {label(item)} and felt sick."
    return "ate", f"{name} ate {label(item)}."
```

with:

```python
        return "sick", f"{name} ate {label(item)} and felt sick."
    chance, risk = FOOD_RISK.get(item, (0.0, 0.0))
    if chance > 0 and nature.roll(seed_of(state), as_cell(state["position"]), RISK_CHANNEL, int(at)) < chance:
        vitals["health"] = max(min(vitals["health"], 1.0), vitals["health"] + risk)
        return "sick", f"{name} ate {label(item)} and felt a little sick."
    return "ate", f"{name} ate {label(item)}."
```

In `backend/survival/carrying.py`, replace:

```python
coal and tools) pushes out the least valuable block Mimo carries instead (LOW_VALUE, moss first
```

with:

```python
coal, tools and swords) pushes out the least valuable block Mimo carries instead (LOW_VALUE, moss first
```

and replace:

```python
    """Food that will not make Mimo sick, seeds, saplings, wheat, ore, ingots, coal and tools: worth
```

with:

```python
    """Food that will not make Mimo sick, seeds, saplings, wheat, ore, ingots, coal, tools and swords: worth
```

and replace:

```python
            or item in AXES or item.endswith(("_ore", "_ingot")))
```

with:

```python
            or item in AXES or item.endswith(("_ore", "_ingot", "_sword")))
```

- [ ] **Step 4: Cook every raw food**

In `backend/survival/cooking.py`, replace:

```python
- Raw fish (8 hunger) cooks into cooked fish (30) in 5 s at a lit campfire or furnace within 6
  blocks. With no fire that close, Mimo places a campfire or furnace it carries beside it (in a
  niche it digs when it is below the surface, as toolmaking does), or first crafts a campfire
  from 2 logs and 3 sticks; failing both, it walks to a fire within 32 blocks and cooks there
  next batch. A fire within 4 blocks of where a step just failed is left alone for a while
  (senses.near_failure).
```

with:

```python
- Raw fish (8 hunger) cooks into cooked fish (30) in 5 s at a lit campfire or furnace within 6
  blocks, and so does the raw meat hunting brings (L1): beef (8 to 35), mutton (8 to 30),
  chicken and rabbit (6 to 25). With no fire that close, Mimo places a campfire or furnace it
  carries beside it (in a niche it digs when it is below the surface, as toolmaking does), or
  first crafts a campfire from 2 logs and 3 sticks; failing both, it walks to a fire within 32
  blocks and cooks there next batch. A fire within 4 blocks of where a step just failed is left
  alone for a while (senses.near_failure).
```

and replace:

```python
from backend.services.crafting import FIRES
```

with:

```python
from backend.services.crafting import COOKING, FIRES
```

and replace:

```python
FIRE_TRAVEL = 32.0
```

with:

```python
RAW_FOODS = tuple(sorted(COOKING))
FIRE_TRAVEL = 32.0
```

and replace:

```python
    fish = inventory.get("raw_fish", 0)
    if fish and not near.intersection(FIRES) and not station(inventory, "campfire", spots, steps, placed, FIRES):
```

with:

```python
    raw = [(item, inventory[item]) for item in RAW_FOODS if inventory.get(item, 0) > 0]
    if raw and not near.intersection(FIRES) and not station(inventory, "campfire", spots, steps, placed, FIRES):
```

and replace:

```python
        fish = 0
    steps.extend({"kind": "cook", "item": "raw_fish"} for _ in range(fish))
```

with:

```python
        raw = []
    steps.extend({"kind": "cook", "item": item} for item, count in raw for _ in range(count))
```

and replace:

```python
    if not fish and not loaves:
```

with:

```python
    if not raw and not loaves:
```

and replace:

```python
    servings = s.count("raw_fish") + s.count("wheat") // BREAD_WHEAT
```

with:

```python
    servings = s.count(*RAW_FOODS) + s.count("wheat") // BREAD_WHEAT
```

and replace:

```python
    "cook", "cook", "Cook raw fish at a fire and bake wheat into bread; cooked food fills far more.",
    valid=lambda s: cook_plan(s) is not None,
    facts=lambda s: f"carrying {s.count('raw_fish')} raw fish and {s.count('wheat')} wheat",
```

with:

```python
    "cook", "cook", "Cook raw fish and meat at a fire and bake wheat into bread; cooked food fills far more.",
    valid=lambda s: cook_plan(s) is not None,
    facts=lambda s: f"carrying {s.count(*RAW_FOODS)} raw fish and meat and {s.count('wheat')} wheat",
```

- [ ] **Step 5: Make swords on the toolmaking ladder**

In `backend/survival/toolmaking.py`, replace:

```python
"""craft_tools: make the next pickaxe, with portable stations.

The ladder is wooden pickaxe, stone pickaxe, iron pickaxe. Only the next one Mimo lacks is on
offer, and only when everything it needs can be made from what Mimo carries. The planner works
the whole chain out on a copy of the inventory: logs into planks, planks into sticks, a crafting
```

with:

```python
"""craft_tools: make the next pickaxe, and swords, with portable stations.

The ladder is wooden pickaxe, stone pickaxe, iron pickaxe. Only the next one Mimo lacks is on
offer, and only when everything it needs can be made from what Mimo carries. Swords (L1) climb a
ladder of their own (wooden, stone, iron: 2 planks, cobblestone or ingots and a stick, at a
crafting table) no higher than the best pickaxe Mimo has. The sword a new pickaxe opens up is
made in the same batch, right after it, when the materials stretch that far; with no pickaxe to
make, the best sword Mimo may make comes alone. The planner works the whole chain out on a copy
of the inventory: logs into planks, planks into sticks, a crafting
```

and replace:

```python
already placed within reach is used as it is and left there. One tool per choice, and none while
something the chain makes would not fit in Mimo's arms (carrying.crafts_fit).
```

with:

```python
already placed within reach is used as it is and left there. One pickaxe (with its sword) or one
sword per choice, and none while something the chain makes would not fit in Mimo's arms
(carrying.crafts_fit).
```

and replace:

```python
LADDER = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe")
STATIONS = {"wooden_pickaxe": ("crafting_table",), "stone_pickaxe": ("crafting_table",),
            "iron_pickaxe": ("crafting_table", "furnace")}
```

with:

```python
LADDER = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe")
SWORD_LADDER = ("wooden_sword", "stone_sword", "iron_sword")
STATIONS = {"wooden_pickaxe": ("crafting_table",), "stone_pickaxe": ("crafting_table",),
            "iron_pickaxe": ("crafting_table", "furnace"), "wooden_sword": ("crafting_table",),
            "stone_sword": ("crafting_table",), "iron_sword": ("crafting_table", "furnace")}
```

and replace:

```python
    return LADDER[rank] if rank < len(LADDER) else None
```

with:

```python
    return LADDER[rank] if rank < len(LADDER) else None


def open_swords(inventory: dict) -> list[str]:
    """The swords Mimo may make now, best first: better than the best one it has, and no better
    than the tier of its best pickaxe."""
    sword = max((rank for rank, name in enumerate(SWORD_LADDER, start=1) if inventory.get(name, 0) > 0), default=0)
    pickaxe = max((TOOL_RANK[tool] for tool in TOOL_RANK if inventory.get(tool, 0) > 0), default=0)
    return list(reversed(SWORD_LADDER[sword:pickaxe]))


def tool_orders(inventory: dict) -> list[tuple[str, ...]]:
    """What craft_tools may make, first choice first: the next pickaxe with the best sword it opens
    up, the pickaxe alone, then a sword alone."""
    orders: list[tuple[str, ...]] = []
    pickaxe = next_tool(inventory)
    if pickaxe is not None:
        orders += [(pickaxe, sword) for sword in open_swords({**inventory, pickaxe: 1})]
        orders.append((pickaxe,))
    orders += [(sword,) for sword in open_swords(inventory)]
    return orders
```

and replace:

```python
def tool_plan(s: Situation) -> list[dict] | None:
    """The steps that make the next pickaxe, or None when it cannot be made now."""
    tool = next_tool(s.inventory)
    if tool is None:
        return None
    inventory = dict(s.inventory)
```

with:

```python
def tool_steps(s: Situation, tools: tuple[str, ...]) -> list[dict] | None:
    """The steps that make `tools` in order, or None when they cannot all be made now."""
    inventory = dict(s.inventory)
```

and replace:

```python
        for station in STATIONS[tool]:
```

with:

```python
        for station in dict.fromkeys(station for tool in tools for station in STATIONS[tool]):
```

and replace:

```python
        make(inventory, tool, 1, steps)
    except Short:
        return None
    steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
    return steps if crafts_fit(s.inventory, steps) else None
```

with:

```python
        for tool in tools:
            make(inventory, tool, 1, steps)
    except Short:
        return None
    steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
    return steps if crafts_fit(s.inventory, steps) else None


def tool_choice(s: Situation) -> tuple[tuple[str, ...], list[dict]] | None:
    """The first of tool_orders that can be made now, with its steps; or None."""
    def look() -> tuple[tuple[str, ...], list[dict]] | None:
        for tools in tool_orders(s.inventory):
            steps = tool_steps(s, tools)
            if steps is not None:
                return tools, steps
        return None
    return s.sensed("tool_choice", look)


def tool_plan(s: Situation) -> list[dict] | None:
    """The steps that make the next pickaxe (and the sword it opens up) or a sword, or None."""
    choice = tool_choice(s)
    return None if choice is None else list(choice[1])
```

and replace:

```python
    "craft_tools", "craft tools", "Make the next pickaxe from carried materials with a portable crafting table.",
    valid=lambda s: tool_plan(s) is not None,
    facts=lambda s: f"can make a {next_tool(s.inventory).replace('_', ' ')} now",
```

with:

```python
    "craft_tools", "craft tools",
    "Make the next pickaxe, and a sword, from carried materials with a portable crafting table.",
    valid=lambda s: tool_plan(s) is not None,
    facts=lambda s: "can make " + " and ".join(f"a {tool.replace('_', ' ')}" for tool in tool_choice(s)[0]) + " now",
```

- [ ] **Step 6: Put hides, wool and feathers away, and drop a replaced sword**

In `backend/survival/storage.py`, replace:

```python
drop_items leaves behind what is no use at all: food Mimo knows is poisonous, pickaxes and axes a
better one replaced, and flowers. When its arms are full and build_storage cannot use a chest
```

with:

```python
drop_items leaves behind what is no use at all: food Mimo knows is poisonous, pickaxes, axes and
swords a better one replaced, and flowers. When its arms are full and build_storage cannot use a chest
```

and replace:

```python
from backend.survival.structures import blueprint_of, clearing, todo
```

with:

```python
from backend.survival.structures import blueprint_of, clearing, todo
from backend.survival.toolmaking import SWORD_LADDER
```

and replace:

```python
        "basalt": 0, "limestone": 0, "sandstone": 0, "brick": 0, "glass": 0, "copper_ore": 0, "copper_ingot": 0}
```

with:

```python
        "basalt": 0, "limestone": 0, "sandstone": 0, "brick": 0, "glass": 0, "copper_ore": 0, "copper_ingot": 0,
        # L1: what animals drop besides meat is put away (L2 makes armor, bows and arrows from it).
        "leather": 0, "wool": 0, "feather": 0, "rabbit_hide": 0}
```

and replace:

```python
    """(item, amount) that is no use to carry: known poison, replaced tools, flowers; and, full with
```

with:

```python
    """(item, amount) that is no use to carry: known poison, replaced tools and swords, flowers; and, full with
```

and replace:

```python
    found += [(axe, s.count(axe)) for axe in axes[:-1]]
```

with:

```python
    found += [(axe, s.count(axe)) for axe in axes[:-1]]
    swords = [sword for sword in SWORD_LADDER if s.count(sword)]
    found += [(sword, s.count(sword)) for sword in swords[:-1]]
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_meat.py"`
Expected: `Ran 8 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 650 tests` … `OK` (8 new). The headless runs still pass: a wooden sword now comes with the wooden pickaxe, and a sword is sometimes a choice of its own, well within the purpose budget.

- [ ] **Step 8: Commit**

```bash
git add backend/services/crafting.py backend/survival/steps.py backend/survival/carrying.py backend/survival/cooking.py backend/survival/toolmaking.py backend/survival/storage.py backend/tests/test_survival_meat.py backend/tests/test_survival_pickers.py backend/tests/test_survival_toolmaking.py
git commit -m "feat: cook meat, make swords after each pickaxe, and put hides, wool and feathers away" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 5: The attack step

**Files:**
- Create: `backend/survival/creatures/combat.py`
- Modify: `backend/survival/steps.py` (import it with the other step modules), `backend/survival/world.py` (a kill is a routine event)
- Test: `backend/tests/test_survival_combat.py`

**Interfaces:**
- Consumes: Tasks 1 and 2 (`Herd`, `kind_of`, `dead`, `Scene`, `run_away`, `moves.roll`, `moves.where`); `steps.StepKind`, `register_step`, `StepFailed`, `as_cell`, `as_point`, `label`, `seed_of`; `crafting.add_item`; `actions.finish` (it settles the inventory after every finished step, `carrying.after_step`).
- Produces:
  - `backend.survival.creatures.combat`: `ATTACK_REACH = 2.5`, `LUNGE = 1.0`, `HAND = (1.0, 0.6)`, `SWORDS = {"wooden_sword": 4.0, "stone_sword": 5.0, "iron_sword": 6.0}`, `SWORD_SECONDS = 0.5`; `weapon(inventory) -> str | None`; `blow(sword_or_None) -> (damage, seconds)`; `drops_of(seed, creature, kind) -> dict[str, int]`; `strike(scene, creature, damage, source) -> dict[str, int] | None` (the drops when it killed, else None; saves the creature).
  - Step kind `attack`: `{"kind": "attack", "creature": id, "target": [x, y, z]}`, status `attacking`, counts as work. The running step has `target` (the creature's cell at the start), `creature`, `pace` and, with a sword, `weapon`. A kill returns the event `("hunt", "<name> hunted a <kind>.")`, sets `state["hunted_at"]` and a thought.
  - `world.ROUTINE_EVENTS` includes `hunt`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_combat.py`:

```python
import math
import sqlite3
import unittest

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.carrying import CARRY_STACKS
from backend.survival.creatures.combat import ATTACK_REACH, blow, drops_of, weapon
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.table import Herd, create_creature_tables, dead
from backend.survival.grid import Grid
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def meadow():
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def animal(grid, kind="cow", cell=(2, 1, 0), health=None):
    creature = grid.herd.add(kind, cell, KINDS[kind].health if health is None else health, 0.0, 0.0,
                             {"home": list(cell), "chunk": [0, 0], "turn": 0})
    grid.herd.note_chunk((0, 0), 1, 1, 0.0)
    return creature


def attack(creature):
    return {"kind": "attack", "creature": creature["id"]}


class BlowTests(unittest.TestCase):
    def test_a_bare_hand_or_the_best_sword_carried(self):
        self.assertEqual((weapon({}), blow(None)), (None, (1.0, 0.6)))
        self.assertEqual(weapon({"wooden_sword": 1, "stone_sword": 1}), "stone_sword")
        self.assertEqual([blow(sword)[0] for sword in ("wooden_sword", "stone_sword", "iron_sword")], [4.0, 5.0, 6.0])
        self.assertEqual(blow("iron_sword")[1], 0.5)

    def test_drops_are_rolled_from_the_seed_and_stay_in_their_ranges(self):
        cows = [drops_of("5", {"id": number}, KINDS["cow"]) for number in range(60)]
        self.assertEqual(cows, [drops_of("5", {"id": number}, KINDS["cow"]) for number in range(60)])
        self.assertTrue(all(1 <= found["raw_beef"] <= 3 and found.get("leather", 0) <= 2 for found in cows))
        self.assertEqual({found.get("leather", 0) for found in cows}, {0, 1, 2})
        rabbits = [drops_of("5", {"id": number}, KINDS["rabbit"]) for number in range(60)]
        self.assertTrue(all(found["raw_rabbit"] == 1 for found in rabbits))
        self.assertEqual({found.get("rabbit_hide", 0) for found in rabbits}, {0, 1})
        self.assertEqual(drops_of("5", {"id": 1}, KINDS["fish"]), {})


class AttackStepTests(unittest.TestCase):
    def test_a_swing_takes_longer_by_hand_and_needs_the_animal_within_reach(self):
        grid, state = meadow(), pet()
        cow = animal(grid)
        step = start_step(attack(cow), state, grid, 10.0)
        self.assertEqual((step["ends_at"], step["target"], step["creature"]),
                         (10.6, {"x": 2, "y": 1, "z": 0}, cow["id"]))
        armed = start_step(attack(cow), pet(inventory={"wooden_sword": 1}), grid, 10.0, scale=10.0)
        self.assertEqual((armed["ends_at"], armed["weapon"]), (10.05, "wooden_sword"))
        far = animal(grid, cell=(3, 1, 0))
        self.assertGreater(3.0, ATTACK_REACH)
        with self.assertRaisesRegex(StepFailed, "out of reach"):
            start_step(attack(far), state, grid, 10.0)
        with self.assertRaisesRegex(StepFailed, "got away"):
            start_step({"kind": "attack", "creature": 999}, state, grid, 10.0)
        with self.assertRaisesRegex(StepFailed, "bad step: creature"):
            start_step({"kind": "attack", "creature": "cow"}, state, grid, 10.0)
        with self.assertRaisesRegex(StepFailed, "got away"):
            start_step(attack(cow), state, Grid(lambda x, y, z: "air"), 10.0)

    def test_a_hit_hurts_the_animal_and_it_runs_away_from_mimo(self):
        grid, state = meadow(), pet()
        cow = animal(grid)
        step = start_step(attack(cow), state, grid, 10.0)
        self.assertIsNone(finish_step(step, state, grid, 10.6))
        hurt = grid.herd.get(cow["id"])
        self.assertEqual((hurt["health"], hurt["state"]["hurt_at"], hurt["state"]["pose"]), (9.0, 10.6, "fleeing"))
        path = hurt["state"]["path"]
        self.assertEqual(path[0]["at"], 10.6)
        self.assertGreater(math.hypot(path[-1]["x"], path[-1]["z"]), 6)

    def test_the_killing_blow_puts_the_drops_in_mimos_arms(self):
        grid, state = meadow(), pet(inventory={"stone_sword": 1})
        cow = animal(grid, health=5.0)
        step = start_step(attack(cow), state, grid, 10.0)
        event = finish_step(step, state, grid, 10.5)
        self.assertEqual(event, ("hunt", "Pip hunted a cow."))
        found = drops_of("5", cow, KINDS["cow"])
        self.assertEqual(state["inventory"], {"stone_sword": 1, **found})
        body = grid.herd.get(cow["id"])
        self.assertTrue(dead(body))
        self.assertEqual((body["health"], body["state"]["dead_at"], body["state"]["drops"]), (0.0, 10.5, sorted(found)))
        self.assertEqual(state["hunted_at"], 10.5)
        self.assertEqual(grid.herd.chunks((0, 0), (0, 0))[(0, 0)]["animals"], 0)
        with self.assertRaisesRegex(StepFailed, "got away"):
            start_step(attack(cow), state, grid, 11.0)

    def test_what_does_not_fit_in_full_arms_stays_behind_and_meat_pushes_out_dirt(self):
        grid = meadow()
        filler = {f"item_{n}": 1 for n in range(CARRY_STACKS - 1)}
        state = pet(inventory={**filler, "dirt": 3})
        cow = animal(grid, health=1.0)
        state["queue"] = [attack(cow)]
        context = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[])
        advance_actions(state, context, 1.0)
        found = drops_of("5", cow, KINDS["cow"])
        self.assertIn("leather", found)  # left behind: it is not worth more than the dirt
        self.assertEqual(state["inventory"], {**filler, "raw_beef": found["raw_beef"]})
        self.assertIsNotNone(state["full_at"])
        self.assertIn((0.6, "hunt", "Pip hunted a cow."), context.events)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_combat.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.combat'`.

- [ ] **Step 3: Write the attack step**

Create `backend/survival/creatures/combat.py`:

```python
"""Hitting a creature: the attack step and what a blow does (spec L1, "Hunting").

attack(creature): Mimo swings at a creature within 2.5 blocks of it: 0.6 s with a bare hand for 1
damage, 0.5 s with a sword for 4 (wooden), 5 (stone) or 6 (iron); the best sword Mimo carries is
used. It works on any creature of any kind, so L2's fights use the same step. The step fails when
the creature is gone or dead ("gone") or out of reach when the swing starts ("out_of_reach").
It lands when the swing ends if the creature still lives and is within a block of that reach
(the lunge); one that ran off in the meantime is missed, which is no failure.

A blow (`strike`) takes health, marks the creature hurt (the viewer flashes it, knocks it back
and shows its health bar) and, for a kind that flees when hurt, sends it running from Mimo at
once. At 0 health it dies: it stays listed a few seconds as "dead" with what it dropped (the
viewer's puff), its home chunk counts one animal fewer, and its drops go straight into Mimo's
arms, as far as the carry limit lets them (the engine settles the inventory after the step,
backend.survival.carrying). A kill sets `state["hunted_at"]` and is a routine "hunt" event.
Drops are rolled from the world seed and the creature, so they never depend on how often the
tick ran.
"""

from __future__ import annotations

import math

from backend.services.crafting import add_item
from backend.survival.creatures.acts import Scene, run_away
from backend.survival.creatures.kinds import Kind, kind_of
from backend.survival.creatures.moves import roll, where
from backend.survival.creatures.table import Herd, dead
from backend.survival.grid import Cell, Grid
from backend.survival.steps import StepFailed, StepKind, as_cell, as_point, label, register_step, seed_of

ATTACK_REACH = 2.5
LUNGE = 1.0  # a swing still lands on a creature this much farther away when it ends
HAND = (1.0, 0.6)  # damage and seconds of a blow without a sword
SWORDS = {"wooden_sword": 4.0, "stone_sword": 5.0, "iron_sword": 6.0}  # damage, weakest first
SWORD_SECONDS = 0.5
DROP_CHANNEL = 70


def weapon(inventory: dict) -> str | None:
    """The best sword Mimo carries, or None for a bare hand."""
    return max((sword for sword in SWORDS if inventory.get(sword, 0) > 0), key=SWORDS.get, default=None)


def blow(sword: str | None) -> tuple[float, float]:
    """The damage and seconds of a blow with `sword` (None: a bare hand)."""
    return (SWORDS[sword], SWORD_SECONDS) if sword in SWORDS else HAND


def drops_of(seed: str, creature: dict, kind: Kind) -> dict[str, int]:
    """What a dead creature drops: each (least, most) range or chance rolled on its own channel."""
    found = {}
    for index, (item, drop) in enumerate(sorted(kind.drops.items())):
        chance = roll(seed, creature["id"], 0, DROP_CHANNEL + index)
        if isinstance(drop, tuple):
            low, high = drop
            count = low + int(chance * (high - low + 1))
        else:
            count = 1 if chance < drop else 0
        if count > 0:
            found[item] = count
    return found


def strike(scene: Scene, creature: dict, damage: float, source: Cell) -> dict[str, int] | None:
    """Hit a creature from `source`: take `damage` from its health and mark it hurt, then either
    kill it (returns its drops) or, for a kind that flees when hurt, send it running (returns
    None). The creature is saved."""
    kind = kind_of(creature["kind"])
    state = creature["state"]
    creature["health"] = max(0.0, creature["health"] - damage)
    state["hurt_at"] = scene.at
    if creature["health"] <= 0:
        found = drops_of(scene.seed, creature, kind) if kind is not None else {}
        cell = where(creature, scene.at)
        creature["x"], creature["y"], creature["z"] = map(float, cell)
        state.update(pose="dead", dead_at=scene.at, drops=sorted(found), path=None)
        scene.herd.save(creature)
        if kind is not None and not kind.water and not kind.hostile:
            scene.herd.lost(state.get("chunk"), scene.at)
        return found
    if kind is not None and kind.flee_when_hurt:
        run_away(creature, kind, scene, source)
    scene.herd.save(creature)
    return None


def target_of(spec: dict, grid: Grid) -> tuple[Herd, dict]:
    number = spec.get("creature")
    if isinstance(number, bool) or not isinstance(number, int):
        raise StepFailed("bad step: creature")
    herd = grid.herd
    creature = herd.get(number) if herd is not None else None
    if creature is None or dead(creature):
        raise StepFailed("it got away", "gone")
    return herd, creature


def start_attack(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    _, creature = target_of(spec, grid)
    there = where(creature, at)
    if math.dist(as_cell(state["position"]), there) > ATTACK_REACH:
        raise StepFailed("out of reach", "out_of_reach")
    sword = weapon(state["inventory"])
    _, seconds = blow(sword)
    step = {"kind": "attack", "started_at": at, "ends_at": round(at + seconds / scale, 3), "target": as_point(there),
            "creature": creature["id"], "pace": scale}
    if sword is not None:
        step["weapon"] = sword
    return step


def finish_attack(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str] | None:
    herd, creature = target_of(step, grid)
    if math.dist(as_cell(state["position"]), where(creature, at)) > ATTACK_REACH + LUNGE:
        return None  # it ran off before the blow landed
    damage, _ = blow(step.get("weapon"))
    scene = Scene(grid, herd, seed_of(state), state, at, step.get("pace", 1.0))
    found = strike(scene, creature, damage, as_cell(state["position"]))
    if found is None:
        return None
    for item, count in found.items():
        add_item(state["inventory"], item, count)
    state["last_thought"] = f"Got the {label(creature['kind'])}!"
    state["hunted_at"] = at
    return "hunt", f"{state['name']} hunted a {label(creature['kind'])}."


register_step(StepKind("attack", start_attack, finish_attack, "attacking", working=True, cell_field="target"))
```

- [ ] **Step 4: Register it with the other steps, and make a kill routine**

In `backend/survival/steps.py`, replace:

```python
field work (pick, harvest, till, plant, fish, cook) lives in backend.survival.fieldwork and M5's
housework (store, take, drop) in backend.survival.housework. Mining leaves or tall grass may drop
```

with:

```python
field work (pick, harvest, till, plant, fish, cook) lives in backend.survival.fieldwork, M5's
housework (store, take, drop) in backend.survival.housework and L1's attack in
backend.survival.creatures.combat. Mining leaves or tall grass may drop
```

and replace:

```python
# M4's field work (pick, harvest, till, plant, fish, cook) and M5's housework (store, take, drop)
# register themselves. They are imported last because they build on everything above.
from backend.survival import fieldwork, housework  # noqa: E402,F401
```

with:

```python
# M4's field work (pick, harvest, till, plant, fish, cook), M5's housework (store, take, drop) and
# L1's attack register themselves. They are imported last because they build on everything above.
from backend.survival import fieldwork, housework  # noqa: E402,F401
from backend.survival.creatures import combat  # noqa: E402,F401
```

In `backend/survival/world.py`, replace:

```python
                            "explore", "owner", "plan", "purpose", "reflex", "ate", "cook", "fish", "grow"})
```

with:

```python
                            "explore", "owner", "plan", "purpose", "reflex", "ate", "cook", "fish", "grow",
                            "hunt"})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_combat.py"`
Expected: `Ran 6 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 656 tests` … `OK` (6 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/creatures/combat.py backend/survival/steps.py backend/survival/world.py backend/tests/test_survival_combat.py
git commit -m "feat: add the attack step: a blow hurts any creature, a hurt animal runs and a kill drops its loot into Mimo's arms" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: The hunt purpose

**Files:**
- Create: `backend/survival/creatures/hunting.py`
- Modify: `backend/survival/brain.py` (import it), `backend/survival/purposes.py` (the score bands)
- Modify tests: `backend/tests/test_survival_days.py` (a new headless run: a hunt and the meat cooked), `backend/tests/test_survival_sim.py` (the purpose budget)
- Test: `backend/tests/test_survival_hunting.py`

**Interfaces:**
- Consumes: Tasks 1–5 (`Herd.near`, `huntable`, `kind_of`, `where`, `cell_of`, `dead`, `ATTACK_REACH`, the `attack` step, `state["hunted_at"]`, `simulate`); `foraging.food_need`, `food_points`, `hunger_score`, `whole_walk`; `purposes.Purpose`, `register`; `senses.near_failure`; `brain.brain_plan`.
- Produces:
  - `backend.survival.creatures.hunting`: `HUNT_SIGHT = 32.0`, `CHASE_REACH = 2.0`, `HUNT_BATCHES = 40`, `BASE = 30.0`; `prey(s) -> list[dict]` (nearest first); `quarry(s) -> dict | None`; `hunted_lately(s) -> bool`; `hunt_valid`, `hunt_facts`, `hunt_score`, `plan_hunt`; the purpose `hunt` (phrase "hunt"). The planner keeps its prey's id in `brain["prey"]`.
  - `test_survival_sim.PURPOSE_EVENTS_PER_HOUR` becomes `55 if SLOW else 52` (resolution 19).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_hunting.py`:

```python
import sqlite3
import unittest

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.brain import brain_plan
from backend.survival.creatures.hunting import HUNT_BATCHES, prey
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.simulate import simulate
from backend.survival.creatures.table import Herd, create_creature_tables, dead
from backend.survival.foraging import hunger_score
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
HUNT = PURPOSES["hunt"]


def meadow():
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "status": "idle", "last_thought": "", "last_tick_at": 0.0,
             "born_at": 0.0, "brain": new_brain(0.0)}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(grid, state=None, clock=DAY, at=100.0):
    return Situation(state or pet(), grid, clock, at, grid.herd.db)


def animal(grid, kind="rabbit", cell=(5, 1, 0), **state):
    return grid.herd.add(kind, cell, KINDS[kind].health, 0.0, 1e9, {"home": list(cell), "turn": 0, **state})


def context(grid):
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=brain_plan, events=[], db=grid.herd.db)


class PreyTests(unittest.TestCase):
    def test_the_nearest_living_land_animal_within_32_blocks_away_from_failed_steps(self):
        grid = meadow()
        far, near = animal(grid, cell=(20, 1, 0)), animal(grid, "cow", (8, 1, 3))
        animal(grid, "fish", (3, 0, 0))
        animal(grid, cell=(4, 1, 0), pose="dead")
        animal(grid, cell=(40, 1, 0))
        self.assertEqual([found["id"] for found in prey(situation(grid))], [near["id"], far["id"]])
        failed = pet(recent_actions=[{"kind": "walk", "started_at": 1.0, "ended_at": 2.0, "result": "failed",
                                      "target": {"x": 8, "y": 1, "z": 2}}])
        self.assertEqual([found["id"] for found in prey(situation(grid, failed))], [far["id"]])
        self.assertEqual(prey(Situation(pet(), Grid(lambda x, y, z: "air"), DAY, 0.0)), [])


class HuntValidityTests(unittest.TestCase):
    def test_offered_by_day_with_prey_near_when_food_is_needed_or_after_a_day_without_a_kill(self):
        grid = meadow()
        animal(grid)
        self.assertTrue(HUNT.valid(situation(grid)))
        self.assertFalse(HUNT.valid(situation(grid, clock=NIGHT)))
        self.assertFalse(HUNT.valid(situation(meadow())))
        fed = {"cooked_beef": 2}
        self.assertTrue(HUNT.valid(situation(grid, pet(inventory=fed))))  # never hunted yet
        self.assertFalse(HUNT.valid(situation(grid, pet(inventory=fed, hunted_at=50.0), at=100.0)))
        self.assertTrue(HUNT.valid(situation(grid, pet(inventory=fed, hunted_at=50.0), at=50.0 + 3600.0)))
        self.assertTrue(HUNT.valid(situation(grid, pet(hunted_at=50.0), at=100.0)))  # hungry for more

    def test_scores_like_food_work_and_bold_pets_hunt_a_little_more(self):
        grid = meadow()
        animal(grid)
        plain = situation(grid)
        self.assertEqual(HUNT.score(plain), hunger_score(plain, 30.0))
        bold = situation(grid, pet(traits={"bravery": 90}))
        self.assertEqual(HUNT.score(bold), HUNT.score(plain) + 4.0)
        hungry = situation(grid, pet(vitals={**START_VITALS, "hunger": 30.0}))
        fed = situation(grid, pet(inventory={"cooked_beef": 2}))
        self.assertGreater(HUNT.score(hungry), HUNT.score(plain))
        self.assertLess(HUNT.score(fed), HUNT.score(plain))
        self.assertIn("rabbit 5 blocks away", HUNT.facts(plain))


class HuntPlanTests(unittest.TestCase):
    def test_walks_to_where_the_animal_is_going_then_attacks_it_within_reach(self):
        grid = meadow()
        rabbit = animal(grid, cell=(9, 1, 0))
        s = situation(grid)
        self.assertEqual(HUNT.plan(s, context(grid)),
                         [{"kind": "walk", "target": [9, 1, 0], "reach": 2.0, "whole": True}])
        self.assertEqual(s.brain["prey"], rabbit["id"])
        close = situation(grid, pet(position={"x": 7.0, "y": 1.0, "z": 0.0}))
        self.assertEqual(HUNT.plan(close, context(grid)),
                         [{"kind": "attack", "creature": rabbit["id"], "target": [9, 1, 0]}])

    def test_keeps_after_the_same_animal_and_stops_when_it_is_gone_or_after_forty_batches(self):
        grid = meadow()
        first, second = animal(grid, cell=(9, 1, 0)), animal(grid, cell=(4, 1, 0))
        state = pet()
        state["brain"].update(purpose="hunt", batches=3, prey=first["id"])
        self.assertEqual(HUNT.plan(situation(grid, state), context(grid))[0]["target"], [9, 1, 0])
        grid.herd.remove(first["id"])
        self.assertEqual(HUNT.plan(situation(grid, state), context(grid)), [])
        self.assertIsNone(state["brain"]["prey"])
        state["brain"].update(batches=HUNT_BATCHES, prey=second["id"])
        self.assertEqual(HUNT.plan(situation(grid, state), context(grid)), [])

    def test_a_hunt_in_the_tick_chases_the_rabbit_down_and_takes_its_meat(self):
        grid = meadow()
        rabbit = animal(grid, cell=(12, 1, 0))
        rabbit["next_at"] = 0.0
        grid.herd.save(rabbit)
        state = pet()
        state["brain"].update(purpose="hunt", pending=None)
        ctx = context(grid)
        at = 0.0
        while at < 120.0 and not dead(grid.herd.get(rabbit["id"])):
            at += 0.5
            advance_actions(state, ctx, at)
            simulate(state, ctx, at)
            ctx.searches_left = 2
        self.assertTrue(dead(grid.herd.get(rabbit["id"])), state["recent_actions"][-3:])
        self.assertEqual(state["inventory"].get("raw_rabbit"), 1)
        self.assertIn("hunt", [event[1] for event in ctx.events])
        swings = [entry for entry in state["recent_actions"] if entry["kind"] == "attack"]
        self.assertEqual({entry["result"] for entry in swings}, {"done"})


if __name__ == "__main__":
    unittest.main()
```

Four game days alone at 60× must now include a hunt and the meat cooked (seed 8, as in the other runs of this file):

In `backend/tests/test_survival_days.py`, replace:

```python
        self.assertTrue(any(state.get("chests", {}).values()))
```

with:

```python
        self.assertTrue(any(state.get("chests", {}).values()))

    def test_left_alone_mimo_hunts_an_animal_and_cooks_its_meat(self):
        chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(8), scale=SCALE)
        for second in range(1, 4 * 60 + 1):
            state = tick_life(self.registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            self.assertIsNone(state["died_at"], state["cause"])
            chooser.poll(self.registry, BORN + second)
        events = self.world.events(5000)
        hunts = [event["text"] for event in events if event["kind"] == "hunt"]
        cooked = [event["text"] for event in events if event["kind"] == "cook"]
        self.assertTrue(hunts, "Mimo never hunted")
        self.assertTrue(any(f"raw {meat}" in text for text in cooked for meat in ("beef", "mutton", "chicken", "rabbit")),
                        cooked)
        self.assertNotIn("hunt", [event["kind"] for event in notable(events)])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_hunting.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.hunting'`.

- [ ] **Step 3: Write the hunt purpose**

Create `backend/survival/creatures/hunting.py`:

```python
"""hunt: chase an animal down for its meat (spec L1, "Hunting").

hunt picks the nearest huntable animal within 32 blocks (a passive land animal, not one within 4
blocks of where a step just failed) and keeps after that one: each batch either attacks it, when
it is within the attack's 2.5 blocks, or walks (all the way or not at all) to where its last move
ends, at most 40 batches. It is done when the animal is dead or has fled out of range. A hit
animal runs off (backend.survival.creatures.combat), and animals near a hunting Mimo flee now and
then (backend.survival.creatures.acts), so a hunt is a chase: hit, run after it, hit again.

It is day work, offered while an animal is in range and Mimo lacks food (foraging.food_need), or
has not killed anything for a game day (`state["hunted_at"]`), so a well-fed pet still hunts now
and then for hides, wool and feathers but never empties the land. It scores like the other food
work (foraging.hunger_score: higher the less food Mimo carries and the hungrier it is, minus the
late-day penalty) from a base of 30, and bold pets hunt a little more: bravery above 50 adds up to
5, below 50 takes up to 5 off. There is no kindness or gentleness trait, so nothing makes a pet
hunt less for being kind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.combat import ATTACK_REACH
from backend.survival.creatures.kinds import huntable, kind_of
from backend.survival.creatures.moves import where
from backend.survival.creatures.table import cell_of, dead
from backend.survival.foraging import food_need, food_points, hunger_score, whole_walk
from backend.survival.purposes import Purpose, register
from backend.survival.senses import near_failure
from backend.survival.situation import Situation
from backend.survival.steps import label

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

HUNT_SIGHT = 32.0
CHASE_REACH = 2.0  # a chase walk ends this close to where the animal's move ends
HUNT_BATCHES = 40
BASE = 30.0


def prey(s: Situation) -> list[dict]:
    """Huntable animals within 32 blocks, nearest first, leaving out any near a failed step."""
    def look() -> list[dict]:
        herd = s.grid.herd
        if herd is None:
            return []
        x, _, z = s.here
        found = [creature for creature in herd.near(x, z, HUNT_SIGHT) if not dead(creature)
                 and huntable(kind_of(creature["kind"])) and not near_failure(s.state, where(creature, s.at))]
        return sorted(found, key=lambda creature: (s.distance(where(creature, s.at)), creature["id"]))
    return s.sensed("prey", look)


def quarry(s: Situation) -> dict | None:
    """The animal this hunt is after: the nearest prey when the hunt starts, then the same one while
    it lives and stays in range."""
    found = prey(s)
    if s.brain["batches"] == 0 and s.brain["replans"] == 0:
        return found[0] if found else None
    chased = s.brain.get("prey")
    return next((creature for creature in found if creature["id"] == chased), None)


def hunted_lately(s: Situation) -> bool:
    """Mimo killed an animal less than a game day ago."""
    hunted_at = s.state.get("hunted_at")
    return hunted_at is not None and (s.at - hunted_at) * s.scale < DAY_SECONDS


def hunt_valid(s: Situation) -> bool:
    return not s.night and (food_need(s) > 0 or not hunted_lately(s)) and bool(prey(s))


def hunt_facts(s: Situation) -> str:
    nearest = prey(s)[0]
    return (f"{len(prey(s))} animals within {round(HUNT_SIGHT)} blocks, the nearest a {label(nearest['kind'])} "
            f"{round(s.distance(where(nearest, s.at)))} blocks away; carrying {round(food_points(s))} hunger of food")


def hunt_score(s: Situation) -> float:
    return hunger_score(s, BASE) + (s.trait("bravery") - 50.0) / 10


def plan_hunt(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= HUNT_BATCHES:
        return []
    target = quarry(s)
    s.brain["prey"] = None if target is None else target["id"]
    if target is None:
        return []
    there = where(target, s.at)
    if s.distance(there) <= ATTACK_REACH:
        return [{"kind": "attack", "creature": target["id"], "target": list(there)}]
    return [whole_walk(cell_of(target), CHASE_REACH)]


register(Purpose(
    "hunt", "hunt", "Chase down an animal nearby for its meat, and hides, wool or feathers.",
    valid=hunt_valid, facts=hunt_facts, score=hunt_score, plan=plan_hunt,
    thoughts=("I could catch something to eat.", "Meat would fill me up.")))
```

- [ ] **Step 4: Let the brain choose it, and note its band**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import farmstead, lighting, storage  # noqa: F401  (M5's building purposes)
```

with:

```python
from backend.survival import farmstead, lighting, storage  # noqa: F401  (M5's building purposes)
from backend.survival.creatures import hunting  # noqa: F401  (L1's hunt purpose)
```

In `backend/survival/purposes.py`, replace:

```python
backend.survival.brain imports them all.
```

with:

```python
L1's backend.survival.creatures.hunting registers hunt. backend.survival.brain imports them all.
```

and replace:

```python
  fill; build_farm 45-55, minus late.
```

with:

```python
  fill; build_farm 45-55, minus late.
- L1's hunt sits in the needs band with forage and fish: 25-88, rising with the food Mimo lacks and
  with hunger, 5 more or less with bravery, minus late.
```

- [ ] **Step 5: Raise the purpose budget of the headless runs**

With hunting, the busiest game hour of the headless runs holds up to 47 changes of purpose at the default settings and 52 with `MIMO_SLOW_TESTS=1` (resolution 19). Raise the default budget; the slow one stays.

In `backend/tests/test_survival_sim.py`, replace:

```python
PURPOSE_EVENTS_PER_HOUR = 55 if SLOW else 46
```

with:

```python
# L1 adds a hunt, cooking its meat, putting away hides, wool and feathers, and swords (with all
# of L1, seeds 3, 11, 5 and 21 and both pickers reached 47, and 52 in slow mode).
PURPOSE_EVENTS_PER_HOUR = 55 if SLOW else 52
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_hunting.py"`
Expected: `Ran 6 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 3 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 663 tests` … `OK` (7 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`.

- [ ] **Step 7: Commit**

```bash
git add backend/survival/creatures/hunting.py backend/survival/brain.py backend/survival/purposes.py backend/tests/test_survival_hunting.py backend/tests/test_survival_days.py backend/tests/test_survival_sim.py
git commit -m "feat: add the hunt purpose: chase the nearest animal down when food runs short, or once a game day" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 7: Fish show the catch

**Files:**
- Create: `backend/survival/creatures/fishing.py`
- Modify: `backend/survival/nature.py` (a bonus to the catch chance), `backend/survival/fieldwork.py` (the fish step uses both)
- Test: `backend/tests/test_survival_fish.py`

**Interfaces:**
- Consumes: Tasks 1 and 2 (`Herd.near`, `kind_of`, `dead`, `moves.move`, `moves.where`); `nature.catches`, `fish_stock`, `take_fish`; `fieldwork.finish_fish`.
- Produces:
  - `backend.survival.creatures.fishing`: `BITE_REACH = 8.0`, `BITE_BONUS = 0.02`, `BITE_MOST = 0.1`, `DART_SECONDS = 0.3`; `is_fish(creature) -> bool`; `fish_near(grid, hook, at) -> list[dict]`; `bite_bonus(grid, hook, at) -> float`; `show_catch(grid, hook, at)` (the nearest fish darts to the hook and gets `state["caught_at"]`).
  - `nature.catches(seed, cell, at, stock, bonus=0.0) -> bool` (the bonus counts only while `stock > 0`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_fish.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import nature
from backend.survival.creatures.fishing import BITE_MOST, bite_bonus, fish_near, show_catch
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.steps import finish_step
from backend.survival.vitals import START_VITALS

HOOK = (3, 0, 0)


def lake():
    """Water at y 0 for x >= 2, grass elsewhere."""
    grid = Grid(lambda x, y, z: ("water" if x >= 2 else "grass") if y == 0 else "dirt" if y < 0 else "air")
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def fish(grid, cell):
    return grid.herd.add("fish", cell, 2.0, 0.0, 50.0, {"home": list(cell), "pose": "swimming", "turn": 0})


def pet():
    return {"name": "Pip", "world_seed": "1", "position": {"x": 1.0, "y": 1.0, "z": 0.0}, "inventory": {},
            "vitals": dict(START_VITALS)}


class FishTests(unittest.TestCase):
    def test_each_fish_near_the_hook_adds_a_little_to_the_chance_up_to_a_tenth(self):
        grid = lake()
        self.assertEqual(bite_bonus(grid, HOOK, 0.0), 0.0)
        near = [fish(grid, (4 + n, 0, 0)) for n in range(3)]
        fish(grid, (30, 0, 0))
        grid.herd.add("cow", (1, 1, 0), 10.0, 0.0, 0.0, {})
        self.assertEqual([found["id"] for found in fish_near(grid, HOOK, 0.0)], [creature["id"] for creature in near])
        self.assertAlmostEqual(bite_bonus(grid, HOOK, 0.0), 0.06)
        for n in range(6):
            fish(grid, (3, 0, 1 + n))
        self.assertEqual(bite_bonus(grid, HOOK, 0.0), BITE_MOST)
        self.assertEqual(bite_bonus(Grid(lambda x, y, z: "water"), HOOK, 0.0), 0.0)

    def test_the_bonus_helps_only_while_the_water_has_stock(self):
        with patch("backend.survival.nature.roll", lambda *args: 0.05):
            self.assertFalse(nature.catches("1", HOOK, 0.0, 0))
            self.assertFalse(nature.catches("1", HOOK, 0.0, 0, 0.1))
            self.assertTrue(nature.catches("1", HOOK, 0.0, 1, 0.0))
        with patch("backend.survival.nature.roll", lambda *args: 0.2):
            self.assertFalse(nature.catches("1", HOOK, 0.0, 1))  # 0.9 / 12 = 0.075
            self.assertTrue(nature.catches("1", HOOK, 0.0, 1, 0.14))

    def test_a_catch_shows_at_the_nearest_fish_which_leaps_at_the_hook_and_swims_on(self):
        grid = lake()
        nearest, other = fish(grid, (5, 0, 0)), fish(grid, (8, 0, 2))
        show_catch(grid, HOOK, 40.0)
        leapt = grid.herd.get(nearest["id"])
        self.assertEqual((cell_of(leapt), leapt["state"]["caught_at"], leapt["state"]["path"][-1]["at"]),
                         (HOOK, 40.0, 40.3))
        self.assertEqual(leapt["next_at"], 50.0)
        self.assertNotIn("caught_at", grid.herd.get(other["id"])["state"])
        show_catch(lake(), HOOK, 40.0)  # no fish near: nothing happens

    def test_a_fishing_step_that_lands_a_fish_shows_the_catch(self):
        grid = lake()
        swimmer = fish(grid, (5, 0, 0))
        state = pet()
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            step = {"kind": "fish", "started_at": 10.0, "ends_at": 30.0, "target": {"x": 3, "y": 0, "z": 0}}
            event = finish_step(step, state, grid, 30.0)
        self.assertEqual(event, ("fish", "Pip caught a fish."))
        self.assertEqual(state["inventory"], {"raw_fish": 1})
        self.assertEqual(grid.herd.get(swimmer["id"])["state"]["caught_at"], 30.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_fish.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.fishing'`.

- [ ] **Step 3: Write the fish's part in fishing**

Create `backend/survival/creatures/fishing.py`:

```python
"""Fish in the water and Mimo's fishing (spec L1: fish are "where fishing's catch shows").

Fish are not hunted. Fishing's stock stays M4's (backend.survival.nature: a 16x16 region's stock
sets the chance of a bite), and each fish swimming within 8 blocks of the hook adds 2 points to
that chance, at most 10, while the region has stock at all. When a catch lands, the nearest of
those fish darts to the hook and leaps (`caught_at`, which the viewer shows as a splash); it swims
on afterwards, since the catch comes from the stock, not from the fish Mimo can see.
"""

from __future__ import annotations

import math

from backend.survival.creatures.kinds import kind_of
from backend.survival.creatures.moves import move, where
from backend.survival.creatures.table import dead
from backend.survival.grid import Cell, Grid

BITE_REACH = 8.0
BITE_BONUS = 0.02  # added to the catch chance for each fish within BITE_REACH of the hook
BITE_MOST = 0.1
DART_SECONDS = 0.3


def is_fish(creature: dict) -> bool:
    kind = kind_of(creature["kind"])
    return kind is not None and kind.water


def fish_near(grid: Grid, hook: Cell, at: float) -> list[dict]:
    """Living fish within BITE_REACH blocks of the hook, nearest first."""
    if grid.herd is None:
        return []
    found = [creature for creature in grid.herd.near(hook[0], hook[2], BITE_REACH)
             if not dead(creature) and is_fish(creature)]
    return sorted(found, key=lambda creature: (math.dist(where(creature, at), hook), creature["id"]))


def bite_bonus(grid: Grid, hook: Cell, at: float) -> float:
    return min(BITE_MOST, BITE_BONUS * len(fish_near(grid, hook, at)))


def show_catch(grid: Grid, hook: Cell, at: float) -> None:
    """The nearest fish darts to the hook and leaps there, if one is near."""
    found = fish_near(grid, hook, at)
    if not found:
        return
    fish = found[0]
    fish["next_at"] = max(fish["next_at"], move(fish, [hook], at, DART_SECONDS, "swimming"))
    fish["state"]["caught_at"] = at
    grid.herd.save(fish)
```

- [ ] **Step 4: Add the bonus to the catch, and show the catch**

In `backend/survival/nature.py`, replace:

```python
def catches(seed: str, cell: Cell, at: float, stock: int) -> bool:
    """Whether a catch started at `at` lands a fish, with the region's stock as it is."""
    return roll(seed, cell, FISH_CATCH, int(at)) < CATCH_CHANCE * stock / FULL_STOCK
```

with:

```python
def catches(seed: str, cell: Cell, at: float, stock: int, bonus: float = 0.0) -> bool:
    """Whether a catch started at `at` lands a fish, with the region's stock as it is. `bonus` (the
    fish Mimo can see near the hook, backend.survival.creatures.fishing) adds to the chance while
    the region has any stock."""
    chance = CATCH_CHANCE * stock / FULL_STOCK + (bonus if stock > 0 else 0.0)
    return roll(seed, cell, FISH_CATCH, int(at)) < chance
```

In `backend/survival/fieldwork.py`, replace:

```python
  cell's 16x16 region (nature.catches); a catch takes one fish from it. A reflex may cut it short.
```

with:

```python
  cell's 16x16 region (nature.catches), a little more when fish swim near the hook (L1,
  backend.survival.creatures.fishing); a catch takes one fish from the stock, and the nearest fish
  leaps at the hook. A reflex may cut it short.
```

and replace:

```python
from backend.survival import nature
```

with:

```python
from backend.survival import nature
from backend.survival.creatures import fishing
```

and replace:

```python
    if not nature.catches(seed_of(state), target, step["started_at"], nature.fish_stock(state, target)):
        return None
    nature.take_fish(state, target, at)
```

with:

```python
    bonus = fishing.bite_bonus(grid, target, at)
    if not nature.catches(seed_of(state), target, step["started_at"], nature.fish_stock(state, target), bonus):
        return None
    nature.take_fish(state, target, at)
    fishing.show_catch(grid, target, at)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_fish.py"`
Expected: `Ran 4 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 667 tests` … `OK` (4 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/creatures/fishing.py backend/survival/nature.py backend/survival/fieldwork.py backend/tests/test_survival_fish.py
git commit -m "feat: fish near the hook raise the catch chance a little and one leaps at the hook when a fish bites" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 8: What the viewer is told

**Files:**
- Create: `backend/survival/creatures/view.py`
- Modify: `backend/survival/snapshot.py` (`creatures` and `creature_moves` in `/api/mimo`)
- Test: `backend/tests/test_survival_creature_api.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`Herd.near`, `kind_of`, `dead`, `SIM_REACH`, `DEAD_KEEP`); `snapshot.survival_view` (it reads everything on one read-only connection, in one transaction); `backend.api.mimo.get_mimo`, `backend.api.lives.hatch_egg`.
- Produces:
  - `backend.survival.creatures.view`: `MOST_SHOWN = 48`, `MOVE_WINDOW = 3.0`; `state_of(creature, now) -> str`; `creature_view(creature, now) -> dict` (`id, kind, x, y, z, heading, health, state`, and `hurt_at`, `dead_at`, `caught_at`, `drops` when set); `move_view(creature) -> dict` (`id, from, to, started, ends` and `cells` for a move longer than one block); `creatures_view(db, position, now) -> {"creatures": [...], "creature_moves": [...]}`.
  - `/api/mimo` (alive): `creatures` and `creature_moves`. The viewer's types follow in Task 9.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_creature_api.py`:

```python
import hashlib
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
from backend.survival.creatures.moves import timed
from backend.survival.creatures.table import Herd
from backend.survival.creatures.view import creatures_view
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, new_survival_state


class CreatureApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def active_world(self):
        registry = LifeRegistry()
        return SurvivalWorld(registry.world_path(registry.active_life()))

    def around_mimo(self, world, *creatures):
        """Add (kind, dx, dz, health, state) creatures around Mimo; returns Mimo's cell."""
        state = world.state()
        x, y, z = (round(state["position"][axis]) for axis in "xyz")
        with world.transaction() as db:
            herd = Herd(db)
            for kind, dx, dz, health, extra in creatures:
                herd.add(kind, (x + dx, y, z + dz), health, 0.0, 0.0, {"turn": 0, **extra})
        return x, y, z

    def test_creatures_near_mimo_and_their_recent_moves_are_streamed(self):
        hatch_egg()
        world = self.active_world()
        now = time.time()
        x, y, z = world.state()["position"]["x"], world.state()["position"]["y"], world.state()["position"]["z"]
        start = (round(x) + 3, round(y), round(z))
        walk = timed(start, [(start[0] + 1, start[1], start[2])], now - 0.5, 0.7)
        old = timed(start, [(start[0], start[1], start[2] + 1)], now - 60.0, 0.7)
        self.around_mimo(world,
                         ("cow", 4, 0, 5.0, {"pose": "walking", "path": walk}),
                         ("sheep", 0, 5, 8.0, {"pose": "walking", "path": old}),
                         ("rabbit", 2, 2, 0.0, {"pose": "dead", "dead_at": now - 2.0, "drops": ["raw_rabbit"],
                                                "hurt_at": now - 2.0}),
                         ("chicken", 3, 3, 0.0, {"pose": "dead", "dead_at": now - 60.0}),
                         ("cow", 200, 0, 10.0, {"pose": "idle"}))
        state = get_mimo()
        by_kind = {creature["kind"]: creature for creature in state["creatures"]}
        self.assertEqual(set(by_kind), {"cow", "sheep", "rabbit"})
        self.assertEqual(by_kind["cow"], {"id": 1, "kind": "cow", "x": x + 4, "y": y, "z": z, "heading": 0.0,
                                          "health": 0.5, "state": "walking"})
        self.assertEqual(by_kind["sheep"]["state"], "idle")  # its walk ended long ago
        self.assertEqual({key: by_kind["rabbit"][key] for key in ("state", "health", "dead_at", "hurt_at", "drops")},
                         {"state": "dead", "health": 0.0, "dead_at": now - 2.0, "hurt_at": now - 2.0,
                          "drops": ["raw_rabbit"]})
        self.assertEqual(state["creature_moves"], [{"id": 1, "from": {"x": start[0], "y": start[1], "z": start[2]},
                                                    "to": {"x": start[0] + 1, "y": start[1], "z": start[2]},
                                                    "started": walk[0]["at"], "ends": walk[-1]["at"]}])

    def test_the_stream_stays_small_with_every_animal_moving(self):
        hatch_egg()
        world = self.active_world()
        now = time.time()
        x, y, z = (round(world.state()["position"][axis]) for axis in "xyz")
        flee = timed((x, y, z), [(x + step, y, z) for step in range(1, 9)], now - 1.0, 0.2)
        self.around_mimo(world, *[("sheep", dx, dz, 8.0, {"pose": "fleeing", "path": flee})
                                  for dx in range(-3, 3) for dz in range(-2, 2)],
                         *[("fish", dx, 9, 2.0, {"pose": "swimming", "path": flee[:3]}) for dx in range(6)])
        state = get_mimo()
        self.assertEqual(len(state["creatures"]), 30)
        flight = next(move for move in state["creature_moves"] if len(move.get("cells", [])) == 9)
        self.assertEqual((flight["cells"][0], flight["cells"][-1]), ([x, y, z], [x + 8, y, z]))
        size = len(json.dumps({"creatures": state["creatures"], "creature_moves": state["creature_moves"]}))
        self.assertLess(size, 14_000)  # the worst case: all 30 on the move at once

    def test_reading_creatures_never_writes(self):
        hatch_egg()
        world = self.active_world()
        self.around_mimo(world, ("cow", 2, 0, 10.0, {"pose": "idle"}))
        before = hashlib.sha256(world.path.read_bytes()).hexdigest()
        get_mimo()
        get_mimo()
        self.assertEqual(hashlib.sha256(world.path.read_bytes()).hexdigest(), before)

    def test_an_archived_world_from_before_l1_has_no_creatures(self):
        path = Path(self.directory.name) / "before-l1.sqlite3"
        state = new_survival_state(name="Pip", seed="1", spawn={"x": 0, "y": 1, "z": 0}, born_at=10.0, traits={})
        SurvivalWorld.create(path, state)
        db = sqlite3.connect(path)
        with db:
            db.execute("DROP TABLE creatures")
        db.close()
        archive = SurvivalWorld(path, read_only=True)
        with archive.connect() as db:
            self.assertEqual(creatures_view(db, {"x": 0.0, "y": 1.0, "z": 0.0}, 20.0),
                             {"creatures": [], "creature_moves": []})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_creature_api.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.view'`.

- [ ] **Step 3: Write the view**

Create `backend/survival/creatures/view.py`:

```python
"""What /api/mimo tells the viewer about creatures (spec L1, "API and viewer").

`creatures`: up to MOST_SHOWN creatures within 48 blocks of Mimo, nearest first: id, kind, the
cell it stands in (where its last move ends), heading, health as a fraction of its kind's, and
its state ("walking", "fleeing", "swimming", "grazing", "idle" or "dead"; a walk or flee that has
ended reads "idle"). Only when they are set: when it was last hurt (`hurt_at`: the flash,
knockback and health bar), when it died and what it dropped (`dead_at`, `drops`: the death puff)
and when a fish last leapt at Mimo's hook (`caught_at`). A creature that died more than DEAD_KEEP
seconds ago is left out.
`creature_moves`: the last move of each listed creature that ended within MOVE_WINDOW seconds,
with from, to, started and ends, and for a move longer than one block every cell it passes
(`cells`, [x, y, z] from `from` to `to`; a creature takes the same time over each), so the
viewer can replay it 1.5 s behind the server as it does Mimo's walks. A move that ended earlier
has nothing left to replay: the creature stands where it ended.
Reading never writes: the snapshot reads it on its read-only connection, in the same transaction as
the rest of the view, and a world from before L1 (an archive read without its schema update) has no
creatures.
"""

from __future__ import annotations

import math
import sqlite3

from backend.survival.creatures.kinds import kind_of
from backend.survival.creatures.simulate import DEAD_KEEP
from backend.survival.creatures.spawning import SIM_REACH
from backend.survival.creatures.table import Herd, dead

MOST_SHOWN = 48
MOVE_WINDOW = 3.0  # server seconds: the viewer draws 1.5 s behind and polls every second
MOVING = ("walking", "fleeing")
WHEN_SET = ("hurt_at", "dead_at", "caught_at")


def state_of(creature: dict, now: float) -> str:
    pose = creature["state"].get("pose", "idle")
    path = creature["state"].get("path")
    if pose in MOVING and (not path or path[-1]["at"] <= now):
        return "idle"
    return pose


def point(entry: dict) -> dict:
    return {"x": entry["x"], "y": entry["y"], "z": entry["z"]}


def creature_view(creature: dict, now: float) -> dict:
    kind = kind_of(creature["kind"])
    state = creature["state"]
    most = kind.health if kind is not None else max(creature["health"], 1.0)
    view = {"id": creature["id"], "kind": creature["kind"], "x": creature["x"], "y": creature["y"], "z": creature["z"],
            "heading": round(creature["heading"], 3), "health": round(max(0.0, creature["health"]) / most, 2),
            "state": state_of(creature, now)}
    view.update({key: state[key] for key in WHEN_SET if state.get(key) is not None})
    if state.get("drops"):
        view["drops"] = list(state["drops"])
    return view


def move_view(creature: dict) -> dict:
    path = creature["state"]["path"]
    move = {"id": creature["id"], "from": point(path[0]), "to": point(path[-1]), "started": path[0]["at"],
            "ends": path[-1]["at"]}
    if len(path) > 2:
        move["cells"] = [[entry["x"], entry["y"], entry["z"]] for entry in path]
    return move


def creatures_view(db: sqlite3.Connection, position: dict, now: float) -> dict:
    """The `creatures` and `creature_moves` fields of /api/mimo around `position`, read through `db`."""
    found = Herd(db).near(position["x"], position["z"], SIM_REACH)
    shown = [creature for creature in found
             if not dead(creature) or now - creature["state"].get("dead_at", now) <= DEAD_KEEP]
    shown.sort(key=lambda creature: (math.hypot(creature["x"] - position["x"], creature["z"] - position["z"]),
                                     creature["id"]))
    shown = shown[:MOST_SHOWN]
    moves = [move_view(creature) for creature in shown if creature["state"].get("path")
             and creature["state"]["path"][-1]["at"] >= now - MOVE_WINDOW]
    return {"creatures": [creature_view(creature, now) for creature in shown], "creature_moves": moves}
```

- [ ] **Step 4: Stream it**

In `backend/survival/snapshot.py`, replace:

```python
from backend.survival.clock import clock_at
```

with:

```python
from backend.survival.clock import clock_at
from backend.survival.creatures.view import creatures_view
```

and replace:

```python
        landmarks = landmarks_view(db, state)
```

with:

```python
        landmarks = landmarks_view(db, state)
        creatures = creatures_view(db, state["position"], now)
```

and replace:

```python
        "landmarks": landmarks,
```

with:

```python
        "landmarks": landmarks,
        # L1: the creatures within 48 blocks of Mimo and their last moves (backend.survival.creatures.view).
        **creatures,
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_creature_api.py"`
Expected: `Ran 4 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 671 tests` … `OK` (4 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/creatures/view.py backend/survival/snapshot.py backend/tests/test_survival_creature_api.py
git commit -m "feat: stream the creatures near Mimo and their last moves in /api/mimo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Viewer: the creature types, hunting words and the attack lunge

**Files:**
- Modify: `frontend/src/survival/types.ts`, `frontend/src/survival/hud.ts`, `frontend/src/survival/animation.ts`
- Test: `frontend/src/survival/hud.test.ts`, `frontend/src/survival/animation.test.ts`

**Interfaces:**
- Consumes: Task 8's `/api/mimo` fields; `hud.ACTION_WORDS`, `PURPOSE_TEXT`; `animation.MOVES`, `bodyPose`.
- Produces:
  - `types.ts`: `ActionKind` gains `'attack'`; `CreatureState`; `Creature` (a `Point` with `id`, `kind`, `heading`, `health` 0..1, `state`, and optional `hurt_at`, `dead_at`, `drops`, `caught_at`); `CreatureMove` (`id`, `from`, `to`, `started`, `ends`, optional `cells: [x, y, z][]`); `SurvivalState.creatures` and `SurvivalState.creature_moves`.
  - `hud.ts`: the step `attack` reads "Attacking"; the purpose `hunt` reads "Hunting".
  - `animation.ts`: `PetMove` gains `'swing'`; an `attack` step plays it: a lunge forward and back over 0.5 s (pitch up to 0.55, lift up to 0.08), facing the step's target like every step with a target (`motion.poseAt`).

- [ ] **Step 1: Write the failing tests**

In `frontend/src/survival/hud.test.ts`, replace:

```ts
    expect(actionText({ kind: 'cook', started_at: 0, ends_at: 5, item: 'raw_fish' }, 'cooking')).toBe('Cooking raw fish')
```

with:

```ts
    expect(actionText({ kind: 'cook', started_at: 0, ends_at: 5, item: 'raw_fish' }, 'cooking')).toBe('Cooking raw fish')
    expect(actionText({ kind: 'attack', started_at: 0, ends_at: 0.6, target: { x: 1, y: 2, z: 3 } }, 'attacking'))
      .toBe('Attacking')
```

and replace:

```ts
    expect(purposeText({ purpose: 'farm', reflex: null, choosing: false })).toBe('Tending the farm')
```

with:

```ts
    expect(purposeText({ purpose: 'farm', reflex: null, choosing: false })).toBe('Tending the farm')
    expect(purposeText({ purpose: 'hunt', reflex: null, choosing: false })).toBe('Hunting')
```

In `frontend/src/survival/animation.test.ts`, replace:

```ts
    expect(moveFor({ kind: 'drop', started_at: 0, ends_at: 0.3 }, 0.1)).toBe('place')
```

with:

```ts
    expect(moveFor({ kind: 'drop', started_at: 0, ends_at: 0.3 }, 0.1)).toBe('place')
    expect(moveFor({ kind: 'attack', started_at: 0, ends_at: 0.6, target: { x: 2, y: 1, z: 0 } }, 0.3)).toBe('swing')
```

and replace:

```ts
  it('hops once per block while walking', () => {
```

with:

```ts
  it('lunges at its target once when it attacks', () => {
    expect(bodyPose('swing', 0, 0, 0).pitch).toBeCloseTo(0)
    expect(bodyPose('swing', 0.25, 0, 0)).toMatchObject({ pitch: 0.55, lift: 0.08 })
    expect(bodyPose('swing', 0.5, 0, 0).pitch).toBeCloseTo(0)
    expect(bodyPose('swing', 0.6, 0, 0).pitch).toBeCloseTo(0)
  })

  it('hops once per block while walking', () => {
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/hud.test.ts src/survival/animation.test.ts`
Expected: 4 tests FAIL, among them `expected 'attacking' to be 'Attacking'`, `expected 'Hunt' to be 'Hunting'` and `expected undefined to be 'swing'`.

- [ ] **Step 3: Add the types, the words and the lunge**

In `frontend/src/survival/types.ts`, replace:

```ts
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook' | 'store' | 'take' | 'drop'
```

with:

```ts
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook' | 'store' | 'take' | 'drop' | 'attack'
```

and replace:

```ts
export type PickerName = 'jev' | 'luna' | 'utility'
```

with:

```ts
/** What a creature is doing (backend/survival/creatures/view.py); a finished walk reads idle. */
export type CreatureState = 'idle' | 'walking' | 'grazing' | 'fleeing' | 'swimming' | 'dead'

/** A creature within 48 blocks of Mimo, standing in the cell its last move ends in. */
export interface Creature extends Point {
  id: number
  /** rabbit, chicken, sheep, cow or fish in L1; other kinds come later. */
  kind: string
  /** Radians around +y; 0 faces +z. */
  heading: number
  /** Health left, 0..1. */
  health: number
  state: CreatureState
  /** Server time it was last hit: a flash, a knock back and its health bar. */
  hurt_at?: number
  /** Server time it died, and what it dropped: a puff with the drops popping out. */
  dead_at?: number
  drops?: string[]
  /** Server time a fish leapt at Mimo's hook. */
  caught_at?: number
}

/** A creature's last move, for replay: one block from `from` to `to`, or through every cell of `cells`. */
export interface CreatureMove {
  id: number
  from: Point
  to: Point
  started: number
  ends: number
  /** [x, y, z] of every cell from `from` to `to` when the move is longer than one block; each takes as long. */
  cells?: [number, number, number][]
}

export type PickerName = 'jev' | 'luna' | 'utility'
```

and replace:

```ts
  chests: Chests
```

with:

```ts
  chests: Chests
  /** The creatures within 48 blocks, nearest first, and their last moves (L1). */
  creatures: Creature[]
  creature_moves: CreatureMove[]
```

In `frontend/src/survival/hud.ts`, replace:

```ts
  drop: 'Dropping',
}
```

with:

```ts
  drop: 'Dropping', attack: 'Attacking',
}
```

and replace:

```ts
  light_up: 'Lighting torches',
}
```

with:

```ts
  light_up: 'Lighting torches', hunt: 'Hunting',
}
```

In `frontend/src/survival/animation.ts`, replace:

```ts
export type PetMove = 'idle' | 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'sleep' | 'work' | 'fish'
```

with:

```ts
export type PetMove = 'idle' | 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'sleep' | 'work' | 'fish' | 'swing'
```

and replace:

```ts
  fish: 'fish', cook: 'work', store: 'place', take: 'place', drop: 'place',
}
```

with:

```ts
  fish: 'fish', cook: 'work', store: 'place', take: 'place', drop: 'place', attack: 'swing',
}
```

and replace:

```ts
const SWING_SECONDS = 0.45
```

with:

```ts
const SWING_SECONDS = 0.45
/** An attack lunges forward and back once: a sword swing lasts 0.5 s, a bare hand 0.6 s. */
const LUNGE_SECONDS = 0.5
```

and replace:

```ts
    case 'fish':
```

with:

```ts
    case 'swing': {
      // A lunge at the target (the pet already faces it): forward and a little up, then back.
      const lunge = Math.sin(Math.PI * Math.min(1, stepTime / LUNGE_SECONDS))
      pose.pitch = 0.55 * lunge
      pose.lift = 0.08 * lunge
      break
    }
    case 'fish':
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test`
Expected: `Tests  237 passed (237)` (1 new; three existing tests gain checks).

Run: `cd frontend && npm run build && npx eslint src/survival/types.ts src/survival/hud.ts src/survival/animation.ts src/survival/hud.test.ts src/survival/animation.test.ts`
Expected: the build succeeds and eslint prints nothing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/survival/types.ts frontend/src/survival/hud.ts frontend/src/survival/animation.ts frontend/src/survival/hud.test.ts frontend/src/survival/animation.test.ts
git commit -m "feat: viewer types for creatures, words for hunting and a lunge when Mimo attacks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 10: Viewer: creature models and how they move

**Files:**
- Create: `frontend/src/survival/creatures.ts`, `frontend/src/survival/creatureMotion.ts`
- Test: `frontend/src/survival/creatures.test.ts`, `frontend/src/survival/creatureMotion.test.ts`

**Interfaces:**
- Consumes: Task 9's `Creature`, `CreatureMove`, `Point`; `types/world.Voxel`; `motion.facingToward`.
- Produces:
  - `creatures.ts`: `CreatureModel` (`body` and `head` voxel lists, `neck` point, `scale` blocks per voxel, `hop` blocks); `creatureModel(kind) -> CreatureModel` (cached; a grey block for an unknown kind); `dropColor(item) -> [r, g, b]`.
  - `creatureMotion.ts`: `Placement` (`x, y, z, facing, moving, travelled`), `Look` (`lift, pitch, roll, headPitch, flash, knock, size`); `movesById(moves) -> Map<number, CreatureMove>`; `placeAt(creature, move, t) -> Placement`; `lookAt(creature, placement, t, clock, hop) -> Look`; `healthBar(creature, t) -> { shown, fraction }`; `puffAge(creature, t) -> number | null`; `dropPops(drops, age) -> { item, offset, scale }[]`; `drawn(creature, t) -> boolean`; constants `FLASH_SECONDS = 0.35`, `KNOCK_SECONDS = 0.25`, `KNOCK_BLOCKS = 0.35`, `TIP_SECONDS = 0.3`, `PUFF_AFTER = 0.5`, `PUFF_LENGTH = 0.8`, `LEAP_SECONDS = 0.8`, `BAR_SECONDS = 3`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/creatures.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { creatureModel, dropColor } from './creatures'

const KINDS = ['rabbit', 'chicken', 'sheep', 'cow', 'fish']

function height(kind: string): number {
  const model = creatureModel(kind)
  const ys = [...model.body, ...model.head].map((voxel) => voxel.y)
  return (Math.max(...ys) - Math.min(...ys) + 1) * model.scale
}

describe('creatureModel', () => {
  it('builds every kind from voxels, as tall as the kind is', () => {
    const sizes: Record<string, number> = { rabbit: 0.5, chicken: 0.6, sheep: 1, cow: 1.3, fish: 0.3 }
    for (const kind of KINDS) {
      const model = creatureModel(kind)
      expect(model.body.length).toBeGreaterThan(5)
      expect(height(kind)).toBeCloseTo(sizes[kind])
      const cells = [...model.body, ...model.head].map((voxel) => `${voxel.x},${voxel.y},${voxel.z}`)
      expect(new Set(cells).size).toBe(cells.length)
    }
    expect(creatureModel('cow')).toBe(creatureModel('cow'))
  })

  it('gives the rabbit long ears, the cow its spots and the sheep its wool', () => {
    const rabbit = creatureModel('rabbit')
    const top = Math.max(...rabbit.head.map((voxel) => voxel.y))
    expect(top - Math.max(...rabbit.body.map((voxel) => voxel.y))).toBeGreaterThanOrEqual(5)
    const cow = creatureModel('cow').body.map((voxel) => voxel.r)
    expect(cow.some((red) => red < 80)).toBe(true)
    expect(cow.some((red) => red > 200)).toBe(true)
    const sheep = creatureModel('sheep').body
    expect(sheep.filter((voxel) => voxel.r > 220).length).toBeGreaterThan(sheep.length / 2)
    expect(creatureModel('fish').head).toEqual([])
  })

  it('hops rabbits highest and draws a kind it does not know as a plain block', () => {
    expect(creatureModel('rabbit').hop).toBeGreaterThan(creatureModel('cow').hop)
    expect(creatureModel('gloomling').body.length).toBe(27)
  })
})

describe('dropColor', () => {
  it('colors meat, leather, wool and feathers', () => {
    expect(dropColor('raw_beef')).toEqual(dropColor('raw_rabbit'))
    expect(new Set(['raw_beef', 'leather', 'wool', 'feather', 'rabbit_hide'].map((item) => dropColor(item).join()))
      .size).toBe(5)
    expect(dropColor('mystery')).toEqual([180, 180, 180])
  })
})
```

Create `frontend/src/survival/creatureMotion.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import {
  BAR_SECONDS, FLASH_SECONDS, KNOCK_SECONDS, LEAP_SECONDS, PUFF_AFTER, PUFF_LENGTH, dropPops, drawn, healthBar,
  lookAt, movesById, placeAt, puffAge,
} from './creatureMotion'
import type { Creature, CreatureMove } from './types'

const cow: Creature = { id: 3, kind: 'cow', x: 12, y: 5, z: 2, heading: 1.2, health: 0.6, state: 'idle' }
const walk: CreatureMove = { id: 3, from: { x: 10, y: 5, z: 2 }, to: { x: 12, y: 5, z: 2 }, started: 100, ends: 102,
  cells: [[10, 5, 2], [11, 5, 2], [12, 5, 2]] }
const step: CreatureMove = { id: 3, from: { x: 11, y: 5, z: 2 }, to: { x: 12, y: 5, z: 2 }, started: 100, ends: 101 }

describe('placeAt', () => {
  it('replays a move cell by cell, facing the way it goes, then stands where it ended', () => {
    expect(placeAt(cow, walk, 99)).toMatchObject({ x: 10, z: 2, moving: false, travelled: 0 })
    expect(placeAt(cow, walk, 100.5)).toMatchObject({ x: 10.5, y: 5, z: 2, facing: Math.PI / 2, moving: true, travelled: 0.5 })
    expect(placeAt(cow, walk, 101.5)).toMatchObject({ x: 11.5, travelled: 1.5 })
    expect(placeAt(cow, walk, 102)).toEqual({ x: 12, y: 5, z: 2, facing: 1.2, moving: false, travelled: 0 })
    expect(placeAt(cow, step, 100.25).x).toBeCloseTo(11.25)
    expect(placeAt(cow, undefined, 100)).toMatchObject({ x: 12, facing: 1.2, moving: false })
  })

  it('finds each creature\'s move by id, and none from an API without moves', () => {
    expect(movesById([walk]).get(3)).toBe(walk)
    expect(movesById(undefined).size).toBe(0)
  })
})

describe('lookAt', () => {
  const still = placeAt(cow, undefined, 0)

  it('hops as it walks and dips its head to graze', () => {
    const halfway = lookAt(cow, { ...still, moving: true, travelled: 0.5 }, 0, 0, 0.2)
    expect(halfway.lift).toBeCloseTo(0.2)
    expect(lookAt(cow, { ...still, moving: true, travelled: 1 }, 0, 0, 0.2).lift).toBeCloseTo(0)
    expect(lookAt({ ...cow, state: 'grazing' }, still, 0, 0, 0.2).headPitch).toBeGreaterThan(0.6)
    expect(lookAt(cow, still, 0, 0, 0.2).headPitch).toBe(0)
  })

  it('flashes and is knocked back when hit, then settles', () => {
    const hit = { ...cow, hurt_at: 50 }
    expect(lookAt(hit, still, 49, 0, 0).flash).toBe(0)
    expect(lookAt(hit, still, 50, 0, 0).flash).toBe(1)
    expect(lookAt(hit, still, 50 + KNOCK_SECONDS / 2, 0, 0).knock).toBeCloseTo(0.35)
    expect(lookAt(hit, still, 50 + FLASH_SECONDS, 0, 0)).toMatchObject({ flash: 0, knock: 0 })
  })

  it('tips over when it dies and shrinks away in its puff', () => {
    const body = { ...cow, state: 'dead' as const, health: 0, dead_at: 60, drops: ['raw_beef', 'leather'] }
    expect(lookAt(body, still, 59, 0, 0)).toMatchObject({ roll: 0, size: 1 })
    expect(lookAt(body, still, 60.3, 0, 0).roll).toBeCloseTo(Math.PI / 2)
    expect(lookAt(body, still, 60 + PUFF_AFTER + PUFF_LENGTH / 2, 0, 0).size).toBeCloseTo(0.5)
    expect(drawn(body, 60 + PUFF_AFTER + PUFF_LENGTH - 0.05)).toBe(true)
    expect(drawn(body, 60 + PUFF_AFTER + PUFF_LENGTH + 0.05)).toBe(false)
    expect(drawn(cow, 1e9)).toBe(true)
  })

  it('makes a fish wiggle, and leap once when it takes the hook', () => {
    const fish: Creature = { id: 4, kind: 'fish', x: 0, y: 2, z: 0, heading: 0, health: 1, state: 'swimming', caught_at: 70 }
    const swimming = [0, 0.5, 1, 1.5].map((clock) => lookAt(fish, still, 0, clock, 0).roll)
    expect(Math.max(...swimming.map(Math.abs))).toBeGreaterThan(0.05)
    expect(lookAt(fish, still, 70 + LEAP_SECONDS / 2, 0, 0).lift).toBeGreaterThan(1)
    expect(lookAt(fish, still, 70 + LEAP_SECONDS, 0, 0).lift).toBeLessThan(0.1)
  })
})

describe('health bar, puff and drops', () => {
  it('shows the health left for a few seconds after a hit it lived through', () => {
    const hit = { ...cow, hurt_at: 50 }
    expect(healthBar(cow, 50)).toEqual({ shown: false, fraction: 0.6 })
    expect(healthBar(hit, 49)).toMatchObject({ shown: false })
    expect(healthBar(hit, 51)).toEqual({ shown: true, fraction: 0.6 })
    expect(healthBar(hit, 50 + BAR_SECONDS).shown).toBe(false)
    expect(healthBar({ ...hit, state: 'dead', dead_at: 50.5 }, 51).shown).toBe(false)
  })

  it('puffs once the body has tipped over and pops the drops out of it', () => {
    const body = { ...cow, state: 'dead' as const, dead_at: 60, drops: ['raw_beef', 'leather'] }
    expect(puffAge(body, 60.2)).toBeNull()
    expect(puffAge(body, 60 + PUFF_AFTER + 0.1)).toBeCloseTo(0.1)
    expect(puffAge(cow, 60)).toBeNull()
    const pops = dropPops(body.drops, PUFF_LENGTH)
    expect(pops.map((pop) => pop.item)).toEqual(['raw_beef', 'leather'])
    expect(pops[0].offset.x).toBeLessThan(0)
    expect(pops[1].offset.x).toBeGreaterThan(0)
    expect(pops[0].offset.y).toBeCloseTo(1.5)
    expect(dropPops(undefined, 0.3)).toEqual([])
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/creatures.test.ts src/survival/creatureMotion.test.ts`
Expected: both files FAIL to load: `./creatures` and `./creatureMotion` do not exist yet.

- [ ] **Step 3: Write the models**

Each model is built from boxes of voxels in the pet's soft pixel style. `scale` makes the model as tall as the kind's `size` in blocks (backend `kinds.py`), and the head is its own list so it can dip to graze.

Create `frontend/src/survival/creatures.ts`:

```ts
import type { Voxel } from '../types/world'
import type { Point } from './types'

/**
 * Blocky voxel models of the creatures, in the soft pixel style of the pet (PetVoxels): a white
 * rabbit with long ears, a woolly sheep, a spotted cow, a small chicken and a fish. Each model is
 * two voxel lists, the body and the head, so the head can dip to graze. Voxel units: x across,
 * y up from the feet, z forward (the way the creature faces). `scale` makes the model as tall as
 * the kind's size in blocks (backend/survival/creatures/kinds.py).
 */
export interface CreatureModel {
  body: Voxel[]
  head: Voxel[]
  /** Where the head turns to graze, in voxel units. */
  neck: Point
  /** Blocks per voxel. */
  scale: number
  /** How high a walk hops, in blocks. */
  hop: number
}

type Color = readonly [number, number, number]

const WHITE: Color = [240, 238, 232]
const PINK: Color = [236, 168, 176]
const EYE: Color = [44, 42, 52]
const WOOL: Color = [236, 229, 212]
const FACE: Color = [96, 90, 88]
const SPOT: Color = [52, 48, 50]
const NOSE: Color = [226, 158, 150]
const HORN: Color = [226, 214, 180]
const COMB: Color = [214, 72, 64]
const BEAK: Color = [240, 184, 72]
const SCALES: Color = [242, 150, 76]
const FIN: Color = [250, 196, 120]

/** Blocks tall, as in the kinds registry. */
const SIZES: Record<string, number> = { rabbit: 0.5, chicken: 0.6, sheep: 1.0, cow: 1.3, fish: 0.3 }
const HOPS: Record<string, number> = { rabbit: 0.25, chicken: 0.08, sheep: 0.06, cow: 0.04, fish: 0 }

class Builder {
  voxels: Voxel[] = []

  box(x: [number, number], y: [number, number], z: [number, number], color: Color | ((x: number, y: number, z: number) => Color)) {
    for (let i = x[0]; i <= x[1]; i++) {
      for (let j = y[0]; j <= y[1]; j++) {
        for (let k = z[0]; k <= z[1]; k++) {
          const [r, g, b] = typeof color === 'function' ? color(i, j, k) : color
          this.voxels = this.voxels.filter((voxel) => voxel.x !== i || voxel.y !== j || voxel.z !== k)
          this.voxels.push({ x: i, y: j, z: k, r, g, b, a: 255 })
        }
      }
    }
    return this
  }
}

/** Black patches on a cow, fixed by the voxel's place. */
function spotted(x: number, y: number, z: number): Color {
  return ((x * 7 + y * 13 + z * 5) % 11 + 11) % 11 < 3 ? SPOT : WHITE
}

function rabbit(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-1, 1], [0, 2], [-3, 1], WHITE).box([0, 0], [2, 2], [-4, -4], WHITE)
  const head = new Builder().box([-1, 1], [2, 4], [2, 4], WHITE)
    .box([-1, -1], [3, 3], [4, 4], EYE).box([1, 1], [3, 3], [4, 4], EYE).box([0, 0], [2, 2], [4, 4], PINK)
    .box([-1, -1], [5, 8], [2, 2], WHITE).box([1, 1], [5, 8], [2, 2], WHITE)
    .box([-1, -1], [5, 7], [3, 3], PINK).box([1, 1], [5, 7], [3, 3], PINK)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 2.5, z: 1.5 } }
}

function chicken(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-1, 1], [1, 3], [-2, 1], WHITE).box([0, 0], [3, 4], [-3, -3], WHITE)
    .box([-2, -2], [2, 2], [-1, 0], WHITE).box([2, 2], [2, 2], [-1, 0], WHITE)
    .box([-1, -1], [0, 0], [0, 0], BEAK).box([1, 1], [0, 0], [0, 0], BEAK)
  const head = new Builder().box([0, 0], [4, 5], [1, 2], WHITE).box([0, 0], [6, 6], [1, 2], COMB)
    .box([0, 0], [4, 4], [3, 3], BEAK).box([0, 0], [3, 3], [2, 2], COMB)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 3.5, z: 1 } }
}

function sheep(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-2, 2], [2, 5], [-3, 3], WOOL)
  for (const [x, z] of [[-1, -2], [1, -2], [-1, 2], [1, 2]]) body.box([x, x], [0, 1], [z, z], FACE)
  const head = new Builder().box([-1, 1], [4, 6], [4, 5], FACE).box([-1, 1], [7, 7], [4, 5], WOOL)
    .box([-1, -1], [6, 6], [6, 6], EYE).box([1, 1], [6, 6], [6, 6], EYE).box([-1, 1], [4, 5], [6, 6], FACE)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 4.5, z: 3.5 } }
}

function cow(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-2, 2], [3, 6], [-4, 3], spotted)
  for (const [x, z] of [[-2, -3], [2, -3], [-2, 2], [2, 2]]) body.box([x, x], [0, 2], [z, z], WHITE)
  const head = new Builder().box([-1, 1], [5, 7], [4, 6], spotted).box([-1, 1], [5, 5], [7, 7], NOSE)
    .box([-1, -1], [7, 7], [7, 7], EYE).box([1, 1], [7, 7], [7, 7], EYE)
    .box([-2, -2], [8, 8], [5, 5], HORN).box([2, 2], [8, 8], [5, 5], HORN)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 5.5, z: 3.5 } }
}

function fish(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([0, 0], [0, 1], [-2, 1], SCALES).box([0, 0], [2, 2], [-1, 0], FIN)
    .box([0, 0], [-1, 2], [-3, -3], FIN).box([0, 0], [1, 1], [1, 1], EYE)
  return { body: body.voxels, head: [], neck: { x: 0, y: 1, z: 1 } }
}

/** A plain grey block for a kind this viewer does not know yet. */
function unknown(): Omit<CreatureModel, 'scale' | 'hop'> {
  return { body: new Builder().box([-1, 1], [0, 2], [-1, 1], [150, 150, 150]).voxels, head: [], neck: { x: 0, y: 2, z: 1 } }
}

const MODELS: Record<string, () => Omit<CreatureModel, 'scale' | 'hop'>> = { rabbit, chicken, sheep, cow, fish }
const cache = new Map<string, CreatureModel>()

/** The voxel model of a kind of creature (the same object every time). */
export function creatureModel(kind: string): CreatureModel {
  const known = cache.get(kind)
  if (known) return known
  const parts = (MODELS[kind] ?? unknown)()
  const all = [...parts.body, ...parts.head]
  const low = Math.min(...all.map((voxel) => voxel.y))
  const high = Math.max(...all.map((voxel) => voxel.y))
  const model = { ...parts, scale: (SIZES[kind] ?? 0.6) / (high - low + 1), hop: HOPS[kind] ?? 0.05 }
  cache.set(kind, model)
  return model
}

/** The color of a dropped item as it pops out of a creature's puff. */
export function dropColor(item: string): Color {
  if (item.startsWith('raw_')) return [214, 112, 108]
  return ({ leather: [150, 96, 62], wool: WOOL, feather: [250, 250, 246], rabbit_hide: [196, 164, 124] } as Record<string, Color>)[item]
    ?? [180, 180, 180]
}
```

- [ ] **Step 4: Write the motion**

Create `frontend/src/survival/creatureMotion.ts`:

```ts
import { facingToward } from './motion'
import type { Creature, CreatureMove, Point } from './types'

/**
 * Where a creature is and how it moves at a moment, from the snapshot (backend/survival/creatures
 * /view.py), drawn REPLAY_DELAY behind the server like the pet: its last move is replayed cell by
 * cell, and the moments in its state (hurt, died, caught) play once each.
 */

/** Where a creature stands at a moment: cell coordinates, fractional while it moves. */
export interface Placement extends Point {
  /** Radians around +y; 0 faces +z. */
  facing: number
  moving: boolean
  /** Cells passed since the move began, fractional, for the hop cycle. */
  travelled: number
}

/** How the body moves on top of its placement. */
export interface Look {
  /** Extra height in blocks: hops, bobbing, a fish's leap. */
  lift: number
  /** Lean forward, in radians. */
  pitch: number
  /** Roll onto the side, in radians: a fish's wiggle, a dead animal tipping over. */
  roll: number
  /** The head's dip, in radians: down to graze. */
  headPitch: number
  /** 0..1: how red the hurt flash is. */
  flash: number
  /** Blocks pushed along the facing by a blow (it faces away as it flees). */
  knock: number
  /** 1 normally, shrinking to 0 as a dead creature puffs away. */
  size: number
}

export const FLASH_SECONDS = 0.35
export const KNOCK_SECONDS = 0.25
export const KNOCK_BLOCKS = 0.35
export const TIP_SECONDS = 0.3
export const PUFF_AFTER = 0.5
export const PUFF_LENGTH = 0.8
export const LEAP_SECONDS = 0.8
export const BAR_SECONDS = 3
const GRAZE_PITCH = 0.8

/** The last moves by creature id. */
export function movesById(moves: readonly CreatureMove[] | null | undefined): Map<number, CreatureMove> {
  return new Map((moves ?? []).map((move) => [move.id, move]))
}

function cellsOf(move: CreatureMove): Point[] {
  return move.cells ? move.cells.map(([x, y, z]) => ({ x, y, z })) : [move.from, move.to]
}

/** Where a creature is at server time `t`: along its last move while that runs, else where it stands. */
export function placeAt(creature: Creature, move: CreatureMove | undefined, t: number): Placement {
  if (!move || t >= move.ends) {
    return { x: creature.x, y: creature.y, z: creature.z, facing: creature.heading, moving: false, travelled: 0 }
  }
  const cells = cellsOf(move)
  const steps = cells.length - 1
  const span = move.ends - move.started
  const along = t <= move.started || span <= 0 ? 0 : ((t - move.started) / span) * steps
  const index = Math.min(steps - 1, Math.floor(along))
  const from = cells[index]
  const to = cells[index + 1]
  const p = along - index
  return {
    x: from.x + (to.x - from.x) * p,
    y: from.y + (to.y - from.y) * p,
    z: from.z + (to.z - from.z) * p,
    facing: facingToward(from, to) ?? creature.heading,
    moving: t > move.started,
    travelled: along,
  }
}

/** Seconds since `at`, or null when it has not happened yet (or never did). */
function since(at: number | undefined, t: number): number | null {
  return at === undefined || t < at ? null : t - at
}

/** How the creature's body moves at server time `t`; `clock` runs on for idle motion, `hop` is its kind's hop. */
export function lookAt(creature: Creature, place: Placement, t: number, clock: number, hop: number): Look {
  const look: Look = { lift: 0, pitch: 0, roll: 0, headPitch: 0, flash: 0, knock: 0, size: 1 }
  const wobble = clock + creature.id * 1.7
  if (creature.kind === 'fish') {
    look.lift = Math.sin(wobble * 2) * 0.04
    look.roll = Math.sin(wobble * 3) * 0.15
  } else if (place.moving) {
    look.lift = Math.abs(Math.sin(Math.PI * place.travelled)) * hop
    look.pitch = 0.08 * Math.sin(2 * Math.PI * place.travelled)
  } else if (creature.state === 'grazing') {
    look.headPitch = GRAZE_PITCH + 0.08 * Math.sin(wobble * 6)
  } else {
    look.lift = Math.sin(wobble * 1.5) * 0.015
  }
  const hurt = since(creature.hurt_at, t)
  if (hurt !== null && hurt < FLASH_SECONDS) look.flash = 1 - hurt / FLASH_SECONDS
  if (hurt !== null && hurt < KNOCK_SECONDS) look.knock = KNOCK_BLOCKS * Math.sin((Math.PI * hurt) / KNOCK_SECONDS)
  const leapt = since(creature.caught_at, t)
  if (leapt !== null && leapt < LEAP_SECONDS) {
    look.lift += 1.1 * Math.sin((Math.PI * leapt) / LEAP_SECONDS)
    look.pitch = -1.2 + (2.4 * leapt) / LEAP_SECONDS
  }
  const dead = since(creature.dead_at, t)
  if (dead !== null) {
    look.roll = (Math.PI / 2) * Math.min(1, dead / TIP_SECONDS)
    look.lift = 0.15 * Math.min(1, dead / TIP_SECONDS)
    look.headPitch = 0
    look.size = dead < PUFF_AFTER ? 1 : Math.max(0, 1 - (dead - PUFF_AFTER) / PUFF_LENGTH)
  }
  return look
}

/** The health bar over a creature: shown for BAR_SECONDS after a hit it lived through. */
export function healthBar(creature: Creature, t: number): { shown: boolean; fraction: number } {
  const hurt = since(creature.hurt_at, t)
  const dead = since(creature.dead_at, t)
  return { shown: hurt !== null && hurt < BAR_SECONDS && dead === null, fraction: Math.max(0, Math.min(1, creature.health)) }
}

/** Seconds into a dead creature's puff (it starts once the body has tipped over), or null. */
export function puffAge(creature: Creature, t: number): number | null {
  const dead = since(creature.dead_at, t)
  if (dead === null || dead < PUFF_AFTER || dead >= PUFF_AFTER + PUFF_LENGTH) return null
  return dead - PUFF_AFTER
}

/** The drops popping out of a puff `age` seconds in: up in an arc, spread apart, shrinking. */
export function dropPops(drops: readonly string[] | undefined, age: number): { item: string; offset: Point; scale: number }[] {
  const p = Math.min(1, Math.max(0, age / PUFF_LENGTH))
  const shown = drops ?? []
  return shown.map((item, index) => {
    const spread = (index - (shown.length - 1) / 2) * 0.35
    return { item, offset: { x: spread * p, y: 0.4 + 1.1 * Math.sin((Math.PI * p) / 2), z: 0 }, scale: 1 - 0.6 * p }
  })
}

/** Whether to draw a creature at all: not once a dead one's puff is over. */
export function drawn(creature: Creature, t: number): boolean {
  const dead = since(creature.dead_at, t)
  return dead === null || dead < PUFF_AFTER + PUFF_LENGTH
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test`
Expected: `Tests  249 passed (249)` (12 new).

Run: `cd frontend && npm run build && npx eslint src/survival/creatures.ts src/survival/creatureMotion.ts src/survival/creatures.test.ts src/survival/creatureMotion.test.ts`
Expected: the build succeeds and eslint prints nothing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/survival/creatures.ts frontend/src/survival/creatureMotion.ts frontend/src/survival/creatures.test.ts frontend/src/survival/creatureMotion.test.ts
git commit -m "feat: voxel models of the animals and the pure maths of how they move, graze, flinch and puff away" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 11: Viewer: creatures in the world and on the minimap

**Files:**
- Create: `frontend/src/survival/SurvivalCreatures.tsx`
- Modify: `frontend/src/survival/WorldCanvas.tsx`, `frontend/src/survival/SurvivalWorld.tsx`, `frontend/src/survival/Minimap.tsx`, `frontend/src/survival/creatures.ts` (the minimap's dots)
- Test: `frontend/src/survival/creatures.test.ts`

**Interfaces:**
- Consumes: Task 10's `creatureModel`, `dropColor`, `movesById`, `placeAt`, `lookAt`, `healthBar`, `puffAge`, `dropPops`, `drawn`; `effects.puffBits`; `overheadMap.toMap`, `MAP_BLOCKS`, `MapOrigin`, `mapOrigin`; `WorldCanvas`'s `replayTime` (server time minus `REPLAY_DELAY`); the `Minimap` component.
- Produces:
  - `SurvivalCreatures.tsx`: `SurvivalCreatures({ creatures, moves, now })` draws the nearest 32 creatures; its per-frame work is in each creature's `useFrame`.
  - `WorldCanvas` props `creatures?: Creature[]` and `creatureMoves?: CreatureMove[]`, drawn only with a server clock (the live world, not archives).
  - `creatures.ts`: `CreatureDot` (`px, py, fish`) and `creatureDots(creatures, origin) -> CreatureDot[]` (living creatures on the map).
  - `Minimap` prop `creatures?: readonly Creature[]`, drawn as small dots after home and the farm, before Mimo.

- [ ] **Step 1: Write the failing test**

In `frontend/src/survival/creatures.test.ts`, replace:

```ts
import { creatureModel, dropColor } from './creatures'
```

with:

```ts
import { creatureDots, creatureModel, dropColor } from './creatures'
import { mapOrigin } from './overheadMap'
import type { Creature } from './types'
```

and replace:

```ts
    expect(dropColor('mystery')).toEqual([180, 180, 180])
  })
})
```

with:

```ts
    expect(dropColor('mystery')).toEqual([180, 180, 180])
  })
})

describe('creatureDots', () => {
  it('puts the living creatures on the minimap, fish apart, and leaves out the dead and the far', () => {
    const origin = mapOrigin({ x: 100, y: 5, z: 100 })
    const cow: Creature = { id: 1, kind: 'cow', x: 110, y: 5, z: 90, heading: 0, health: 1, state: 'grazing' }
    const dots = creatureDots([cow, { ...cow, id: 2, kind: 'fish', x: 100, z: 100 },
      { ...cow, id: 3, state: 'dead', dead_at: 5 }, { ...cow, id: 4, x: 400 }], origin)
    expect(dots).toEqual([{ px: 106.5, py: 86.5, fish: false }, { px: 96.5, py: 96.5, fish: true }])
    expect(creatureDots(undefined, origin)).toEqual([])
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/survival/creatures.test.ts`
Expected: 1 test FAILS: `creatureDots is not a function` (it is not exported yet).

- [ ] **Step 3: Put creatures on the minimap**

In `frontend/src/survival/creatures.ts`, replace:

```ts
import type { Voxel } from '../types/world'
import type { Point } from './types'
```

with:

```ts
import type { Voxel } from '../types/world'
import { MAP_BLOCKS, toMap, type MapOrigin } from './overheadMap'
import type { Creature, Point } from './types'
```

and replace:

```ts
  return ({ leather: [150, 96, 62], wool: WOOL, feather: [250, 250, 246], rabbit_hide: [196, 164, 124] } as Record<string, Color>)[item]
    ?? [180, 180, 180]
}
```

with:

```ts
  return ({ leather: [150, 96, 62], wool: WOOL, feather: [250, 250, 246], rabbit_hide: [196, 164, 124] } as Record<string, Color>)[item]
    ?? [180, 180, 180]
}

/** A creature as a small dot on the minimap, in blocks from the map's top-left corner. */
export interface CreatureDot {
  px: number
  py: number
  fish: boolean
}

/** The living creatures on the minimap (overheadMap.ts): dead ones and ones off the map are left out. */
export function creatureDots(creatures: readonly Creature[] | null | undefined, origin: MapOrigin): CreatureDot[] {
  return (creatures ?? [])
    .filter((creature) => creature.state !== 'dead')
    .map((creature) => ({ ...toMap(creature.x, creature.z, origin), fish: creature.kind === 'fish' }))
    .filter(({ px, py }) => px >= 0 && py >= 0 && px < MAP_BLOCKS && py < MAP_BLOCKS)
}
```

In `frontend/src/survival/Minimap.tsx`, replace:

```tsx
import type { Built, ExploredPatch, Landmark, MimoAction, Point } from './types'
```

with:

```tsx
import { creatureDots } from './creatures'
import type { Built, Creature, ExploredPatch, Landmark, MimoAction, Point } from './types'
```

and replace:

```tsx
const SPROUT = '#9ed07a'
```

with:

```tsx
const SPROUT = '#9ed07a'
const ANIMAL = '#fff4de'
const FISH = '#6fb8d8'
```

and replace:

```tsx
/**
 * A top-down map of the land 96 blocks each way around Mimo, north up: the terrain as the 3D
```

with:

```tsx
/** A creature (L1): a small cream dot, blue for a fish, about 4 CSS pixels across at any size the map shows. */
function drawCreature(context: CanvasRenderingContext2D, x: number, y: number, fish: boolean): void {
  const u = SIZE / (context.canvas.clientWidth || 140)  // canvas pixels to a CSS pixel
  context.beginPath()
  context.arc(x, y, 2 * u, 0, Math.PI * 2)
  context.fillStyle = fish ? FISH : ANIMAL
  context.fill()
  context.lineWidth = 0.8 * u
  context.strokeStyle = INK
  context.stroke()
}

/**
 * A top-down map of the land 96 blocks each way around Mimo, north up: the terrain as the 3D
```

and replace:

```tsx
export default function Minimap({ store, position, explored, structures, landmarks, action, name, onHide }: {
```

with:

```tsx
export default function Minimap({ store, position, explored, structures, landmarks, creatures, action, name, onHide }: {
```

and replace:

```tsx
  landmarks: readonly Landmark[] | undefined
```

with:

```tsx
  landmarks: readonly Landmark[] | undefined
  /** The creatures near Mimo (L1), drawn as small dots. */
  creatures?: readonly Creature[]
```

and replace:

```tsx
    const middle = (MAP_RADIUS + 0.5) * MAP_SCALE
```

with:

```tsx
    for (const dot of creatureDots(creatures, origin)) drawCreature(context, dot.px * MAP_SCALE, dot.py * MAP_SCALE, dot.fish)
    const middle = (MAP_RADIUS + 0.5) * MAP_SCALE
```

and replace:

```tsx
  }, [cache, position, explored, structures, landmarks, action])
```

with:

```tsx
  }, [cache, position, explored, structures, landmarks, creatures, action])
```

- [ ] **Step 4: Draw the creatures in the world**

Create `frontend/src/survival/SurvivalCreatures.tsx`:

```tsx
import { useLayoutEffect, useMemo, useRef, type RefObject } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Voxel } from '../types/world'
import { creatureModel, dropColor } from './creatures'
import { dropPops, drawn, healthBar, lookAt, movesById, placeAt, puffAge } from './creatureMotion'
import { puffBits } from './effects'
import type { Creature, CreatureMove } from './types'

/** Creatures drawn at most: the nearest ones, as the server lists them. */
const MAX_DRAWN = 32
const PUFF_BITS = 6
const MOST_DROPS = 4
const BAR_WIDTH = 0.7
const FISH_LIFT = 0.3
const PUFF_COLOR = '#f4f1ea'
const BAR_BACK = '#3b2f2f'
const BAR_FILL = '#79c46b'
const HIDDEN: Creature[] = []

/** One part's voxels as an instanced mesh of unit cubes, colored per voxel, like PetVoxels, with its
 * material in `material` so the hurt flash can light it up. */
function Voxels({ voxels, material }: { voxels: Voxel[]; material: RefObject<THREE.MeshStandardMaterial | null> }) {
  const mesh = useRef<THREE.InstancedMesh>(null)

  useLayoutEffect(() => {
    const cubes = mesh.current
    if (!cubes) return
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()
    voxels.forEach((voxel, index) => {
      dummy.position.set(voxel.x + 0.5, voxel.y + 0.5, voxel.z + 0.5)
      dummy.updateMatrix()
      cubes.setMatrixAt(index, dummy.matrix)
      color.setRGB(voxel.r / 255, voxel.g / 255, voxel.b / 255, THREE.SRGBColorSpace)
      cubes.setColorAt(index, color)
    })
    cubes.instanceMatrix.needsUpdate = true
    if (cubes.instanceColor) cubes.instanceColor.needsUpdate = true
  }, [voxels])

  if (voxels.length === 0) return null
  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, voxels.length]} frustumCulled={false}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial ref={material} roughness={0.55} metalness={0.05} />
    </instancedMesh>
  )
}

function flashRed(material: THREE.MeshStandardMaterial | null, flash: number) {
  material?.emissive.setRGB(0.9 * flash, 0.12 * flash, 0.1 * flash)
}

/**
 * One creature: its voxel model walking its last move with a hop and bob, grazing head down, a red
 * flash and a knock back when hit with its health bar over it for a few seconds, and when it dies
 * it tips over and puffs away as its drops pop out. All per-frame work happens in useFrame.
 */
function CreatureFigure({ creature, move, now }: { creature: Creature; move: CreatureMove | undefined; now: () => number }) {
  const model = creatureModel(creature.kind)
  const low = Math.min(...[...model.body, ...model.head].map((voxel) => voxel.y))
  const height = (Math.max(...[...model.body, ...model.head].map((voxel) => voxel.y)) - low + 1) * model.scale
  const colors = useMemo(() => (creature.drops ?? []).slice(0, MOST_DROPS).map((item) => {
    const [r, g, b] = dropColor(item)
    return new THREE.Color().setRGB(r / 255, g / 255, b / 255, THREE.SRGBColorSpace)
  }), [creature.drops])
  const root = useRef<THREE.Group>(null)
  const body = useRef<THREE.Group>(null)
  const head = useRef<THREE.Group>(null)
  const bodyMaterial = useRef<THREE.MeshStandardMaterial>(null)
  const headMaterial = useRef<THREE.MeshStandardMaterial>(null)
  const bar = useRef<THREE.Group>(null)
  const fill = useRef<THREE.Mesh>(null)
  const puff = useRef<THREE.InstancedMesh>(null)
  const pops = useRef<THREE.Group>(null)
  const scratch = useRef<THREE.Object3D | null>(null)

  useFrame((state) => {
    const group = root.current
    if (!group) return
    const t = now()
    group.visible = drawn(creature, t)
    if (!group.visible) return
    const place = placeAt(creature, move, t)
    const look = lookAt(creature, place, t, state.clock.elapsedTime, model.hop)
    const lift = creature.kind === 'fish' ? FISH_LIFT : 0
    group.position.set(place.x + 0.5 + Math.sin(place.facing) * look.knock, place.y + lift + look.lift,
      place.z + 0.5 + Math.cos(place.facing) * look.knock)
    group.rotation.y = place.facing
    body.current?.rotation.set(look.pitch, 0, look.roll)
    body.current?.scale.setScalar(Math.max(0.001, look.size))
    if (head.current) head.current.rotation.x = look.headPitch
    flashRed(bodyMaterial.current, look.flash)
    flashRed(headMaterial.current, look.flash)

    const health = healthBar(creature, t)
    if (bar.current) {
      bar.current.visible = health.shown
      if (health.shown) {
        // Keep the bar square to the camera whichever way the creature faces.
        bar.current.quaternion.copy(group.quaternion).invert().multiply(state.camera.quaternion)
        fill.current?.scale.set(Math.max(0.001, health.fraction), 1, 1)
        fill.current?.position.set((health.fraction - 1) * BAR_WIDTH / 2, 0, 0.01)
      }
    }

    const age = puffAge(creature, t)
    const bits = puff.current
    if (bits) {
      bits.visible = age !== null
      if (age !== null) {
        const dummy = (scratch.current ??= new THREE.Object3D())
        const { offsets, scale } = puffBits(PUFF_BITS, age)
        offsets.forEach((offset, index) => {
          dummy.position.set(offset.x, height / 2 + offset.y, offset.z)
          dummy.scale.setScalar(scale)
          dummy.updateMatrix()
          bits.setMatrixAt(index, dummy.matrix)
        })
        bits.instanceMatrix.needsUpdate = true
      }
    }
    const popped = pops.current
    if (popped) {
      popped.visible = age !== null
      if (age !== null) {
        dropPops(creature.drops?.slice(0, MOST_DROPS), age).forEach((pop, index) => {
          popped.children[index]?.position.set(pop.offset.x, pop.offset.y, pop.offset.z)
          popped.children[index]?.scale.setScalar(pop.scale)
        })
      }
    }
  })

  const neck: [number, number, number] = [model.neck.x, model.neck.y, model.neck.z]
  return (
    <group ref={root} visible={false}>
      <group ref={body}>
        <group scale={model.scale} position={[-0.5 * model.scale, -low * model.scale, -0.5 * model.scale]}>
          <Voxels voxels={model.body} material={bodyMaterial} />
          <group ref={head} position={neck}>
            <group position={[-neck[0], -neck[1], -neck[2]]}>
              <Voxels voxels={model.head} material={headMaterial} />
            </group>
          </group>
        </group>
      </group>
      <group ref={bar} position={[0, height + 0.3, 0]} visible={false}>
        <mesh>
          <boxGeometry args={[BAR_WIDTH, 0.09, 0.02]} />
          <meshBasicMaterial color={BAR_BACK} />
        </mesh>
        <mesh ref={fill}>
          <boxGeometry args={[BAR_WIDTH, 0.07, 0.02]} />
          <meshBasicMaterial color={BAR_FILL} />
        </mesh>
      </group>
      <instancedMesh ref={puff} args={[undefined, undefined, PUFF_BITS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.16, 0.16, 0.16]} />
        <meshLambertMaterial color={PUFF_COLOR} />
      </instancedMesh>
      <group ref={pops} visible={false}>
        {colors.map((color, index) => (
          <mesh key={index}>
            <boxGeometry args={[0.18, 0.18, 0.18]} />
            <meshLambertMaterial color={color} />
          </mesh>
        ))}
      </group>
    </group>
  )
}

/** The creatures near Mimo (the snapshot's list, nearest first), drawn at `now` (the replay time). */
export default function SurvivalCreatures({ creatures, moves, now }: {
  creatures: Creature[] | undefined
  moves: CreatureMove[] | undefined
  now: () => number
}) {
  const byId = useMemo(() => movesById(moves), [moves])
  const shown = (creatures ?? HIDDEN).slice(0, MAX_DRAWN)
  return (
    <>
      {shown.map((creature) => (
        <CreatureFigure key={creature.id} creature={creature} move={byId.get(creature.id)} now={now} />
      ))}
    </>
  )
}
```

In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import SurvivalPet from './SurvivalPet'
import type { Built, FinishedAction, LeafDecay, MimoAction, Point } from './types'
```

with:

```tsx
import SurvivalCreatures from './SurvivalCreatures'
import SurvivalPet from './SurvivalPet'
import type { Built, Creature, CreatureMove, FinishedAction, LeafDecay, MimoAction, Point } from './types'
```

and replace:

```tsx
 * defaults to the overview camera (archives).
 */
```

with:

```tsx
 * defaults to the overview camera (archives). `creatures` and `creatureMoves` (L1) are drawn
 * replaying their moves the same REPLAY_DELAY behind the server as the pet.
 */
```

and replace:

```tsx
decays = NO_DECAYS, structures = NO_STRUCTURES, serverTime, cameraMode = 'overview', onAutoPick }: {
```

with:

```tsx
decays = NO_DECAYS, structures = NO_STRUCTURES, creatures, creatureMoves, serverTime, cameraMode = 'overview', onAutoPick }: {
```

and replace:

```tsx
  structures?: Built[]
  serverTime?: () => number
```

with:

```tsx
  structures?: Built[]
  /** The creatures near Mimo and their last moves (the snapshot's lists). */
  creatures?: Creature[]
  creatureMoves?: CreatureMove[]
  serverTime?: () => number
```

and replace:

```tsx
          {serverTime && <LeafPuffs decays={decays} now={replayTime} />}
```

with:

```tsx
          {serverTime && <LeafPuffs decays={decays} now={replayTime} />}
          {serverTime && <SurvivalCreatures creatures={creatures} moves={creatureMoves} now={replayTime} />}
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
        action={state.action} recentActions={state.recent_actions} decays={state.decays} structures={state.structures}
```

with:

```tsx
        action={state.action} recentActions={state.recent_actions} decays={state.decays} structures={state.structures}
        creatures={state.creatures} creatureMoves={state.creature_moves}
```

and replace:

```tsx
        landmarks={state.landmarks} action={state.action} name={state.life.name} onHide={() => showMap(false)} />
```

with:

```tsx
        landmarks={state.landmarks} creatures={state.creatures} action={state.action} name={state.life.name}
        onHide={() => showMap(false)} />
```

- [ ] **Step 5: Run the tests, the build and the linter**

Run: `cd frontend && npm test`
Expected: `Tests  250 passed (250)` (1 new).

Run: `cd frontend && npm run build && npx eslint src/survival/SurvivalCreatures.tsx src/survival/WorldCanvas.tsx src/survival/SurvivalWorld.tsx src/survival/Minimap.tsx src/survival/creatures.ts src/survival/creatures.test.ts`
Expected: the build succeeds and eslint prints nothing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/survival/SurvivalCreatures.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/survival/SurvivalWorld.tsx frontend/src/survival/Minimap.tsx frontend/src/survival/creatures.ts frontend/src/survival/creatures.test.ts
git commit -m "feat: draw the animals in the world, replaying their moves, and as dots on the minimap" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Manual check on the demo and the README

This task is for the controller. It rebuilds the demo image from the branch and restarts the demo stack on its own scratch volume: `mimo-m5demo-api` (:8011) and `mimo-m5demo-worker`, volume `mimo_m5demo`, a copy of the owner's world at the natural pace (`MIMO_TIME_SCALE=1`, `MIMO_ACTION_SCALE=1`, as the owner asked), with no model key, so the utility picker chooses. The owner's real stack (`pets-api-1`, `pets-mimo-worker-1`) and its volume `pets_mimo_data` are never touched. The viewer runs on :3000 (:5173 is the owner's dev server). If a check fails, fix the code in the task that owns it, re-run that task's tests, rebuild and repeat the check.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 671 tests` … `OK`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  250 passed (250)`, the build succeeds, eslint prints nothing.

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

Expected: two container ids. The worker's first write adds the creature tables to the demo world (`create_creature_tables` runs with the schema check), and herds appear around the pet within a tick or two.

Start the viewer against it (or, when a viewer already runs on :3000 against :8011, restart it so it picks up the branch's frontend) and open `http://localhost:3000/preview` in the Browser pane.

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8011 npm run dev -- --port 3000 --strictPort
```

- [ ] **Step 3: Keep a creature snippet and a nudge ready**

Save these in your scratchpad directory (not in the repo). `animals.sh` prints the creatures near the pet, the latest hunts and cooking, what the pet carries of the hunt and what its chests hold:

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
import collections, time
from backend.survival.creatures.view import creatures_view
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
state = world.state()
with world.connect() as db:
    view = creatures_view(db, state["position"], time.time())
print("creatures", collections.Counter((c["kind"], c["state"]) for c in view["creatures"]))
print("moving now", len(view["creature_moves"]), "| hurt lately", [c["kind"] for c in view["creatures"] if "hurt_at" in c])
print("purpose", (state.get("brain") or {}).get("purpose"), "| doing", (state.get("action") or {}).get("kind"))
for event in reversed(world.events(300)):
    if event["kind"] in ("hunt", "cook", "sick") or "hunt" in event["text"]:
        print(event["kind"], "|", event["text"])
kept = ("raw_", "cooked_", "leather", "wool", "feather", "rabbit_hide", "_sword")
print("carries", {item: count for item, count in state["inventory"].items() if any(part in item for part in kept)})
print("chests", state.get("chests"))
PY
```

`hunt.sh` is a manual nudge for a pet that has not hunted by the time the checks below need it: it makes hunt the pet's purpose (the tick plans its next batch as soon as the current step ends):

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    state["brain"].update(purpose="hunt", batches=0, replans=0, planned_at=None, pending=None, reflex=None)
    state["queue"] = []
    write_state(db, state)
print("hunting")
PY
```

- [ ] **Step 4: Creatures are there, and alive**

Run `animals.sh`. Confirm up to 24 creatures are listed, of the kinds the pet's biome has (a meadow has rabbits, chickens, sheep and cows; water nearby adds fish), in several states. In the viewer, pan around the pet in Overview. Confirm: a white rabbit with long ears, a woolly sheep, a spotted black-and-white cow and a small chicken stand on the grass at their own sizes, and fish swim in the water. Walking animals hop a block at a time and turn the way they go; some stand with their heads down, grazing; the rest bob gently. Nothing sinks into the ground or floats above it. The minimap shows a small cream dot for each animal and a blue one for each fish, and they move between polls.

- [ ] **Step 5: A hunt**

Wait for the pet to hunt by day (the HUD reads `Hunting`; `animals.sh` shows purpose `hunt`). If it has not hunted within 15 minutes of daylight, run `hunt.sh` once and note it. Confirm in the viewer: the pet walks to an animal, faces it and lunges (the step line reads `Attacking`); the animal flashes red, is knocked back a little and runs about 8 blocks away at double speed, with a green health bar over it for a few seconds that shows what is left; the pet follows and strikes again. When the animal dies, it tips over and puffs away, and its drops pop out of the puff. `animals.sh` then prints `hunt | <name> hunted a <kind>.` and the pet carries the raw meat (and leather, wool, feathers or a hide).

- [ ] **Step 6: Meat cooked, and drops in the chest**

Keep watching (or run `animals.sh` every few minutes). Confirm the pet cooks the raw meat at a campfire or furnace (`cook | <name> cooked raw beef.`, or mutton, chicken or rabbit; the HUD reads `Cooking a meal`), and eats cooked meat when hungry. Confirm that once its arms fill up at home, `put things away` stores the leather, wool, feathers or hides in the chest: `chests` in `animals.sh` lists them, and the **Blocks & crafting** panel shows them under what the chest holds. If the pet already has a stone pickaxe and a crafting table's worth of planks, confirm it made a sword along the way (`carries` shows `wooden_sword` or `stone_sword`).

- [ ] **Step 7: Fish at the hook, and a quiet worker**

If the pet fishes, confirm a fish swims to the hook and leaps out of the water when a catch lands. Confirm the worker log stays quiet: `docker logs mimo-m5demo-worker 2>&1 | grep -c "crashed"` prints `0` (or only lines from before the restart). Leave the demo running on the new image for the owner.

- [ ] **Step 8: Describe animals in the README**

In `README.md`, replace:

```markdown
## Current world rules
```

with:

```markdown
## Animals

- **Creatures** live in each world's database (`creatures`, `backend/survival/creatures/`) and move in the tick like Mimo, only within 48 blocks of it; the rest stay put. Rabbits, chickens, sheep and cows roam the land and fish swim in the water. The first time Mimo comes within 48 blocks of a 16×16 chunk, 0 to 2 herds of animals that live in its biome appear there, seeded by the world seed and the chunk, and a school of fish in its water; at most 24 creatures are ever near Mimo, and 6 fish in one stretch of water. A chunk whose animals were all hunted gets a herd back after 3 game days.
- **Moving.** No creature searches for a path: each steps one block at a time by Mimo's own rules (up one, down at most three), animals never into water and fish only through it. They wander within 12 blocks of where they appeared, graze with their heads down and stand about. A hurt animal runs about 8 blocks away at double speed, and so does one within 6 blocks of Mimo while it hunts, then it calms down for a few seconds. What each creature does is a registry of actions (flee, swim, graze, wander, idle) that the hostile creatures of the next milestone add to.
- **Hunting.** Hunt picks the nearest animal within 32 blocks and chases it: Mimo walks to where it is going and attacks it within 2.5 blocks, 0.6 s and 1 damage by hand or 0.5 s and 4, 5 or 6 damage with a wooden, stone or iron sword. A rabbit has 3 health, a chicken 4, a sheep 8 and a cow 10. A dying animal tips over and puffs away, and its drops go straight into Mimo's arms as far as it can carry them: raw rabbit and sometimes a rabbit hide, raw chicken and up to 2 feathers, raw mutton and 1 or 2 wool, raw beef and up to 2 leather. Mimo hunts by day when it needs food, or when it has not hunted for a game day, and bold pets hunt a little more.
- **Meat and swords.** Raw beef and mutton fill 8 hunger, raw chicken and rabbit 6, and raw chicken sometimes makes Mimo a little sick; cooked at a campfire or furnace, beef fills 35, mutton 30, chicken and rabbit 25. A sword takes 2 planks, cobblestone or iron ingots and a stick at a crafting table, and craft tools makes each one after the pickaxe of its tier, in the same batch when the materials stretch that far. Hides, wool and feathers go in the chest, and a sword a better one replaced is dropped.
- **Fish** are not hunted. Fishing's catch still comes from the water's stock, a little likelier with fish swimming near the hook, and the nearest fish leaps at the hook when one bites.
- `/api/mimo` adds `creatures` (within 48 blocks: kind, where, heading, health, what it is doing, and when it was hurt, died or leapt) and `creature_moves` (each one's last move). The viewer draws each kind as a small voxel model, replays their moves 1.5 s behind the server like the pet, makes them hop as they walk and graze head down, flashes a hurt animal red with a health bar over it, shows Mimo's lunge at its prey and the dying animal's puff with its drops popping out, and puts a dot for each on the minimap.

## Current world rules
```

- [ ] **Step 9: Run the checks again and commit**

Run: `python3 -m unittest discover -s backend/tests && cd frontend && npm test && npm run build`
Expected: `Ran 671 tests` … `OK`, `Tests  250 passed (250)`, the build succeeds.

```bash
git add README.md
git commit -m "docs: describe the animals, hunting, meat and swords" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (L1 detail) | Where |
|------------------|-------|
| Creatures table `creatures(id, kind, x, y, z, heading, health, state JSON, spawned_at, next_at)`, index on `(x, z)`, idempotent migration in a world-schema hook | Task 1 (`table.create_creature_tables`, run by `world.create_world_tables`; resolutions 3–5) |
| Kinds registry `creatures/kinds.py`, pure data with name, health, speed, size, hostile, damage, reach, drops, biomes, herd, water, flee_when_hurt | Task 1 (`Kind`, `register_kind`; L2 registers hostiles the same way) |
| rabbit 3 (fast; raw_rabbit, sometimes rabbit_hide), chicken 4 (raw_chicken, 0–2 feathers), sheep 8 (raw_mutton, 1–2 wool), cow 10 (raw_beef, 0–2 leather), fish 2 (swims, not hunted) | Task 1 (the registered kinds), Task 5 (`drops_of`; resolution 15) |
| Fish: where fishing's catch shows; stock as in M4; more fish nearby slightly raises the catch chance | Task 7 (`fishing.bite_bonus`, `show_catch`, `nature.catches(..., bonus)`; resolution 16) |
| Spawning: herds when Mimo first comes within 48 blocks of a chunk, seeded by world seed and chunk, 0–2 per chunk, by biome | Task 3 (`spawning.populate`, `herd_count`, `plan_herd`, `creature_chunks`; resolution 9) |
| Caps: 24 passive within 48 blocks, 6 fish per water region | Task 3 (`PASSIVE_CAP`, `FISH_PER_REGION`; resolution 9) |
| A chunk that lost its animals regains one herd after 3 game days (seeds in L3) | Tasks 3 and 5 (`Herd.lost`, `REGAIN_SECONDS`; resolution 4) |
| Creature tick inside `advance_world` at step resolution, only within 48 blocks; `next_at` | Task 3 (`simulate`, `tick.run_creatures`; resolution 10) |
| Wander to a standable neighbour with pauses, within 12 blocks of the spawn point | Task 2 (`wander`, `LEASH`; resolution 7) |
| Flee when hurt or when Mimo hunts within 6 blocks: double speed, about 8 blocks | Tasks 2 and 5 (`run_away`, `scared`, `strike`; resolution 8) |
| Graze and idle poses | Task 2 (`graze`, `idle`), Tasks 10–11 (head down, bobbing) |
| Grid standability: step up 1, drop up to 3, no water for land animals, water only for fish | Task 2 (`moves.steps` over `pathing.moves`; resolution 6) |
| Bounded cost: at most N actions per slice, no path search, moves written to the row, no block edits | Task 3 (`MAX_ACTS`; measured; resolution 10) |
| `attack(creature_id)`: reach 2.5, 0.6 s hand / 0.5 s sword, damage 1 / 4 / 5 / 6, the target takes damage, flees, dies at 0 with its drops into Mimo's arms under the carry limits | Task 5 (`combat`; resolution 11) |
| `hunt`: needs band by food need with the late penalty, rises when hungry, falls with food carried; nearest huntable within 32 not near a failed step; walks within reach and attacks until dead or out of range; bold pets more, kind pets less if such a trait exists | Task 6 (`hunting`; resolution 12: no kindness trait exists, and the daily hunt) |
| Cooking: raw_beef, raw_mutton, raw_chicken, raw_rabbit into cooked_*, roughly 8 raw to 25–35 cooked, raw chicken a small chance of sickness | Task 4 (`crafting.COOKING`, `steps.FOOD`, `FOOD_RISK`, `cooking.RAW_FOODS`; resolution 13) |
| Crafting: wooden, stone and iron swords (2 planks, cobblestone or iron_ingot and 1 stick); the ladder makes the next sword only after the pickaxe it needs | Task 4 (recipes, `toolmaking.open_swords`, `tool_orders`; resolution 14) |
| Wool, feathers and leather | Tasks 1 and 5 (drops), Task 4 (stored in the chest; resolution 15) |
| API: `creatures` within 48 blocks (id, kind, x, y, z, heading, health fraction, state) and `creature_moves` (from, to, started, ends) replayed 1.5 s behind | Task 8 (`view`; resolution 17), Task 10 (`placeAt` at the replay time) |
| Viewer models: white long-eared rabbit, woolly sheep, spotted cow, small chicken, fish in water | Task 10 (`creatureModel`), Task 11 (`SurvivalCreatures`) |
| Animation: walk hop and bob, head-down graze, hurt flash and knockback, death puff with drops popping | Task 10 (`lookAt`, `puffAge`, `dropPops`), Task 11 |
| Hunting visuals: Mimo's attack swing at the target; a health bar for a few seconds after a hit | Task 9 (the `swing` lunge), Task 10 (`healthBar`), Task 11 |
| Minimap: creatures as small dots | Task 11 (`creatureDots`, `Minimap`) |
| Tests: registry values and spawn determinism; the cap; wander standable and within range; flee runs away; attack reduces health and drops loot with carry limits; hunt validity and scoring; cooking the meats; API shape and size, GETs read-only; viewer pure helpers; the headless sims still pass and a new sim hunts and cooks | Tasks 1, 3, 2, 2, 5, 6, 4, 8, 9–11, 6 (`test_left_alone_mimo_hunts_an_animal_and_cooks_its_meat`; resolution 19) |
| Performance: at most 20 ms per 60-game-second slice on average, bounded counts | Task 3 (`test_creatures_cost_well_under_twenty_milliseconds_a_slice`; resolution 10) |
| Decisions: server owns creatures, only within 48 simulated; creatures stay cheap (no A*, greedy, a hard cap); original creatures and names; no model calls in the tick | Tasks 1–3, 10; resolutions 2, 6, 10, 18 |
| Error handling: crashes logged once, the tick model-free, GETs read-only, migrations idempotent, the headless sims green with the milestone's own sim check | Tasks 1, 3 (`run_creatures`), 6, 8 |

Out of scope here (L2–L4): hostile creatures (gloomling, skitter), light levels and dark spawning, Mimo's health regen and creature damage, fight and flee reflexes, the bow and arrows, armor, doors, death by a creature, `threats` in the model payload and HUD danger cues (L2); new blocks, biomes, bigger caves and passages and creature seeds (L3); the goal layer (L4). The kinds' `hostile`, `damage` and `reach`, the creature-action registry and the generic `attack` step and `strike` are ready for L2.
