# Survival M5: Purposeful Building Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Mimo build its own home from blocks it gathered: a seeded generator that designs shelters and farms from the site, the materials Mimo carries and its style, the build_shelter, build_storage, light_up and build_farm purposes that place them block by block, beds, chests and torches in use, a carrying limit with storage, one rule that keeps every other plan off what Mimo built, a catch-up that no longer starves a pet after a long outage, and a viewer that names home and shows Mimo inside or behind its walls.

**Architecture:** A pure generator (`backend/survival/blueprints.py`) turns a site, a size tier, the blocks Mimo carries and style knobs into a Blueprint: an ordered list of (cell, part, block). When a building purpose plans its first batch, the design is stored in two new memory tables (`structures`, `structure_cells`) and every cell it uses is claimed; `Grid.claimed` loads those claims chunk by chunk, and `structures.reserved` is the one rule stairs, saplings, farm plots and stations follow. The purposes are new modules that register themselves like M4's (`building`, `storage`, `lighting`, `farmstead`), the chest and drop steps register in the step registry (`housework`), and the brain's observer gains one M5 learner (`building.note_building`) that finishes structures and moves home into a finished shelter. The carrying limit (`carrying`) settles the inventory once per finished step in the action engine. `tick_life` now catches up one 60-game-second transaction at a time.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-survival-core-design.md` (M5: section 8 "Purposeful building", and M5's parts of sections 3, 5, 9, 10, 12 and 13; M5 completes sub-project 2 and its "Done when"). It builds on `docs/superpowers/plans/2026-09-23-survival-m4-food-renewal.md`. The code on branch `worthy/23_09_2026/survival_core` at `17acc6b` (M4, its final fix wave and follow-up) is the "old" text every task edits; the dry run applied every task to that commit.

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls. The generator is deterministic: the same site, traits, world seed and inventory always give the same design (`blueprints.roll` hashes the seed; nothing reads the clock or `random`).
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments (mutate three.js objects only through refs inside `useFrame`, effects or event handlers), no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. Read-only GETs never write. Schema setup runs at most once per process per path (`_ensure_world_schema`), and every schema change is idempotent (`CREATE ... IF NOT EXISTS`). M5's two tables are created by `memory.create_memory_tables`, so every world and every test database that has memory has them. The legacy world file is only ever opened read-only.
- **No model call inside the tick.** The generator, the site search and every planner are rules; M5's planners do no path search of their own (walks search when they start). Validity checks, facts and scores never write: the Chooser runs them on a read-only connection. Only a planner (inside the tick) starts a structure.
- A crashing planner, reflex, hook or picker never stops a tick or the worker. Crashes are logged once per distinct error (`backend.survival.once.log_once`).
- `shared/blocks.json` does not change: `bed`, `chest` and `torch` (and `campfire`) exist since M4.
- Values copied from the spec. Section 8: a shelter has an enclosed interior at least 3×3×2, a roof over all of it, a door gap, and a bed if Mimo has one, and must pass the server's shelter check; a farm is 3×3 to 5×5 farmland beside water, a low fence optional; storage is a chest under a roof, inside or beside the shelter; lights are torches around home at night that glow and lift mood; a campfire beside home is part of build_shelter or warm_up; the generator's inputs are the site (flat-enough area near home, chosen from observed columns), size tier, the materials Mimo has (planks, cobblestone, logs, dirt as a last resort) and style knobs (roof shape flat, gable or dome; wall material; window pattern; door side); creativity varies the style and thrift picks cheaper materials; its output is an ordered block list (floor, walls, roof, fittings) placed one block at a time; when materials run out the purpose pauses and gathering purposes become more valuable; Mimo carries at most 16 stacks of 32 and chests hold 24 stacks; a full inventory makes build_storage and dropping low-value items valid. Section 3: sleeping restores energy +0.2 per second, in a bed +0.35; sheltered means a roof within 4 blocks overhead and walls on at least 3 sides; a lit campfire or furnace within 4 blocks sets the target warmth to 100. Section 5: `build_shelter` needs no shelter yet or a damaged one; collapse sleeps where Mimo stands or in a bed within 8 blocks; head home works with a known shelter within 64 blocks. Section 12: a clock jump is caught up in simulated steps of at most 60 s.
- `MIMO_TIME_SCALE` and `MIMO_ACTION_SCALE` (both default 1) are for manual runs only. M5 adds no settings.
- Never run `docker` or `docker compose` in Tasks 1–13. Task 14 is the controller's manual check on a scratch volume; never touch, mount or migrate the owner's real volume `pets_mimo_data`.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (471 pass at `17acc6b`)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_building.py" -v`
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` (about 90 s)
- Frontend tests: `cd frontend && npm test` (175 pass at `17acc6b`)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint <paths>`

Each task says how many tests it adds. If the real starting totals differ, expect the same increases on top of them.

Transcription: every edit is a fenced block: a new file ("Create `path`:"), a "replace: … with: …" pair, "the whole `name` function", "append" or "add this test class before `class Name`", as in M4. The dry run applied each task with M4's apply script (`.superpowers/sdd/2026-09-23-survival-m4-food-renewal/apply_plan.py`) to a copy of `17acc6b` and ran the task's checks after each one.

## Plan-level resolutions

The spec leaves these open or ambiguous, and the M3 and M4 reviews asked for some of them. Every task follows them; the controller ledgers them.

1. **Base.** M4 is complete at `17acc6b` (its final fix wave landed: score-band docs, poison tasting, growth-row retries, sapling and plot placement off the staircase and home, recent decays, whole walks kept). M5 plans against that commit. The M4 controller deferred three items to M5, and all three are here: grown-tree marking (resolution 14), inventory limits and hoarding (15–18) and the long-outage catch-up (24).
2. **One shelter of its own.** build_shelter designs a shelter only while Mimo has none of its own within 128 blocks (so an explore trip does not start a second home), and works on one within 64 blocks (`HOME_RANGE`). It starts once Mimo carries half the design's blocks, goes on with 8 blocks (or what is left), places up to 12 blocks a batch and plans at most 8 batches per choice. With no blocks left the plan is done: the purpose pauses.
3. **Sizes.** Inside 3×3, 4×3 or 5×4, two blocks high (the spec's minimum is 3×3×2). Creativity 60 allows 4×3 and 80 allows 5×4, and the larger tiers are taken only when Mimo carries the blocks for them; otherwise 3×3. A 3×3 flat-roofed hut takes 37 to 39 blocks.
4. **Style and name.** Traits and the world seed choose the knobs (`blueprints.style_for`): a fancy roof (gable or dome) and windows with a chance of creativity/100 each, cobblestone walls with thrift 50 or more (else planks), a roof of the other material from creativity 50, and the order of door sides to try. The name is a template, like "Pip's Snug Cottage". Luna does not pick knobs or names in M5: the tick may not call a model and the Chooser has no per-structure hook; the spec says Luna *may*.
5. **Materials.** Building blocks, in the order they stand in for each other: cobblestone, planks, brick, limestone, sandstone, basalt, moss, clay, sand, gravel, dirt (last). Each cell names the block it prefers; any other building block stands in when that one runs short. Mimo keeps 2 logs (a campfire's worth, or sticks for a tool); every log beyond them counts as the 4 planks it makes and is crafted into planks by the batch that needs them (planks need no station). Logs are never placed raw: a placed log would read as a tree (resolution 14). Without the 2 kept logs, a pet whose chooser picked build_shelter right after its first pickaxe turned its whole wood supply into walls.
6. **Sites** (`blueprints.find_site`), within 12 blocks of the site's center: home on the surface above it (a staircase home is underground), else where Mimo stands. The inside is exactly flat with 5 open cells above it; the wall ring is within one block of the floor (a lower column gets a floor block, a one-higher column's ground serves as the bottom wall block); the door column is level and the cell in front of the door level or one lower. Every column is untouched natural ground (never farmland, a sapling, water, a placed block, a claimed cell or a dug column) and no wall or door-front column is beside a dug column, so a staircase keeps its way out. The site search reads the Grid (`Grid.natural_material` tells an edit from the natural block), so it needs no worldgen and tests use small worlds.
7. **The shelter check.** Every inside cell and the cell on top of the bed pass `vitals.is_sheltered` for all 36 designs (3 roofs × 3 sizes × 4 door sides); a test builds each one and checks.
8. **Order and reach.** Floor blocks, walls (the bottom row, then the top), gable ends, roof (lowest first), then the fittings: the bed and the chest in the back corners, a campfire outside beside the cell in front of the door, torches on the four outside corners. Mimo builds from inside, standing on the inside cells except the two back corners: every block is within reach 4 of such a stand (tested), so there is no scaffolding to take down.
9. **Beds, chests, torches, axes.** A bed is a solid block and Mimo sleeps in it by lying on top of it: `start_sleep` notes a bed under Mimo and `activity_of` then says `sleeping_in_bed` (+0.35 energy per second). The sleep purpose and the collapse reflex walk onto a bed within 8 blocks first. A bed takes 6 planks and a chest 8 planks, with no crafting table, because Mimo makes them inside its shelter, where no station may stand (resolution 13). Torches: 1 coal and 1 stick make 4, no station. Wooden, stone and iron axes are recipes at a crafting table (spec section 6 names them M5's); Mimo does not craft an axe itself in M5, but `steps.tool_speed` already doubles wood speed with one.
10. **Done and home.** When a placed block completes a shelter's floor, walls and roof, the M5 learner marks the structure done, moves home into its inside cell with `memory.set_home` (noted `built`; the old home is remembered as a shelter), logs a notable `built` event, lifts mood by 10 and asks for a choice. `purposes.home_of` prefers the built home within 64 blocks over a nearer shelter, and `memory.forget` never forgets a built home, so a blocked door cannot make the brain drop it.
11. **Damage.** A done shelter missing a floor, wall or roof block, or with something solid in its door gap, the cell in front of the door (or above it) or the passage to the home cell, makes build_shelter valid again at 75. Repairs take any carried block; a blocked way in is cleared from outside when Mimo is out.
12. **Structures memory.** `memory.create_memory_tables` creates `structures` (id, kind, name, anchor, status `building` or `done`, started_at, built_at, the design as JSON) and `structure_cells` (every claimed cell with its structure, part and block). `world_grid` loads a chunk's claims with its edits.
13. **One reserved rule** (M4 final review item 2). `structures.reserved(grid, cell)` is true for a claimed cell or a cell holding farmland or a sapling (M4's `work.TENDED`, which moves there). A shelter claims its walls, roof, floor blocks, fittings, every inside cell (`room` and `passage`), the door gap, and the cell in front of the door with the one above it (`front`). `work.stair`, `work.sapling_spots`, `farming.new_plots` and `toolmaking.free_cells` (so craft_tools, cook and warm_up's stations) follow it, and the site search skips claimed cells. So Mimo never digs, plants, tills or puts a station in its home or its way in, and makes no tools inside it.
14. **Trees Mimo planted** (M4 final review item 1). The M5 learner remembers a `tree` place at every sapling Mimo plants (instead of marking trees in `renewal.grow_tree`, which the fix wave just changed); `senses.standing_logs` counts placed logs only in the `grown` columns gather_wood passes, so a placed log elsewhere is never chopped as a tree.
15. **Carrying** (spec section 8, M4 final review item 3). 16 stacks of 32 on Mimo and 24 in a chest; a tool or station is a stack of its own. `actions.finish` settles the inventory after every finished step (`carrying.after_step`): of what the step brought in, the part that does not fit stays behind (there are no dropped items), and what Mimo already carried is never lost. `state["full_at"]` notes when something first had to stay behind, and the learner asks for a choice then. Owner crafting and leaf-decay drops are not capped as they happen.
16. **Storage.** build_storage places a chest in the shelter's chest corner (making it when needed), puts away loose blocks, materials beyond `storage.KEEP` and food beyond a day's worth (60 hunger), up to 8 store steps, and takes food out when Mimo carries less than 20 hunger of food. Offered at a done shelter within 64 blocks from 13 stacks, or when the chest holds food Mimo needs; one batch per choice. Chest contents live in `state["chests"]` ("x,y,z" keys) and go with a chest that is gone.
17. **Dropping.** drop_items drops known poison, pickaxes and axes a better one replaced, and flowers; when Mimo is full and has no chest placed, also moss, gravel, sand and clay. Offered from 10 stacks with something to drop.
18. **Hoarding** (M4 final review item 3). farm harvests ripe crops only while Mimo lacks food (`foraging.food_need`); otherwise they wait in the field. Known red mushrooms are dropped (17), unknown ones count as food and their spare servings are stored (16).
19. **Torches.** light_up runs from 5 game minutes before dusk until nightfall at a done shelter within 16 blocks, while a torch corner is dark and Mimo carries torches or can make them; it places them with whole walks and walks back inside. Each torch lifts mood by 2 (the spec's "lift mood"; there is no light level until sub-project 3). head_home leaves build_shelter and light_up alone (`reflexes.AT_HOME_WORK`), since both keep Mimo at home at dusk.
20. **Farm** (M4 final review item 4). build_farm lays a square over the farm Mimo keeps (the remembered `farm` place and the farmland within 3 blocks of it, as much as the square can hold), else beside the nearest shore within 16 blocks of home, else at home. Size 3×3, 4×4 with 12 things to plant and diligence 60, 5×5 with 20 and diligence 80. It claims its plots, tills 4 a batch and plants carrots first, and is offered again when plots turned back into dirt. No fence (the spec makes it optional) and no dug water source (the spec defers it to a bucket).
21. **Campfire beside home** is a shelter fitting, placed by build_shelter after the walls and roof (resolution 8); warm_up is unchanged.
22. **Gathering motivation.** `building.building_need` is how many blocks a started shelter still lacks beyond what Mimo carries. gather_stone aims for 12 cobblestone plus that need and gather_wood for 8 logs plus a quarter of it, so both are offered again while a shelter waits. Before a shelter is started the goals stay 8 and 12. build_shelter's facts say how many blocks it is short, and the model payload's `building` entry carries that number.
23. **Scores**, in the documented bands: build_shelter 60 + caution/10, 10 more from 1,200 game seconds into the day (so the roof is up before night), 75 to repair, 45–55 to furnish; build_storage 50 + 5 per stack over 13, 5 more when full (55 to take food out); drop_items 30 + 8 per stack over 10; light_up 72 (above waiting for night at home, 60); build_farm 45 + diligence/10 minus the late penalty. Building happens beside home, so build_shelter takes no late penalty.
24. **Catch-up in slices** (M4 final review item 5). `tick_life` advances a gap one 60-game-second step per `advance_world` call: each is its own transaction with its own search budget, the way a 60× run ticks, so a pet that slept through an 8-hour outage keeps walking and eating (measured: alive after 8 game days caught up at once). Between steps `run_once` lets a rules-only Chooser answer, so no model calls burst out during a catch-up. This replaces M2's ruling of one search budget for a whole catch-up and its test.
25. **Purpose-change budget.** The headless check allowed 36 purpose events in a game hour; M5's first day adds a shelter in two or three goes, furnishing, storage, dropping, a farm and torches. Measured after all of M5 on seeds 3, 11, 5 and 21 with both pickers: at most 40 at the default settings and 41 with `MIMO_SLOW_TESTS=1`. Task 5 raises the budget to 46.
26. **Events.** `built` is notable (it stays on memorials). Full arms are a thought and a trigger, not an event.
27. **API.** `/api/mimo` adds `structures` (id, kind, name, status, x, y, z) and `chests`. An archive from before M5 opened read-only has no structures table and shows none. Section 10's endpoints are unchanged.
28. **Viewer.** HUD words for the new steps and purposes, a home line under the purpose, the chest's contents in the Blocks & crafting panel, and the place pose for storing, taking and dropping. The cutaway (M3 review's Finding B, generalised) also cuts when a wall or roof reaching above the cut height stands between the pet and the camera within 6 blocks, so Mimo stays visible behind its house; `BlockWorld` passes the camera's position to the cutaway callback.
29. **Game time units** stay M3's: a game minute is 60 game seconds and a game day 3,600.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/survival/carrying.py` | Create | Stacks, room, settling the inventory after a step |
| `backend/survival/housework.py` | Create | Step kinds store, take and drop; chest contents |
| `backend/survival/beds.py` | Create | The nearest bed to lie on |
| `backend/survival/blueprints.py` | Create | The generator: styles, materials, sites, shelter and farm designs |
| `backend/survival/structures.py` | Create | Starting a structure, what is left to build, damage, `reserved` |
| `backend/survival/building.py` | Create | build_shelter, `building_need`, the M5 learner, the model payload |
| `backend/survival/storage.py` | Create | build_storage and drop_items |
| `backend/survival/lighting.py` | Create | light_up |
| `backend/survival/farmstead.py` | Create | build_farm |
| `backend/services/crafting.py` | Modify | Torch, chest, bed and axe recipes |
| `backend/survival/actions.py` | Modify | Settle the inventory after each step; sleeping in a bed |
| `backend/survival/steps.py` | Modify | Import housework; a bed under a sleeping Mimo |
| `backend/survival/grid.py` | Modify | `natural_material`, claims loaded per chunk, `claimed` |
| `backend/survival/memory.py` | Modify | Structures tables, `set_home`, `BUILT`, a built home is never forgotten |
| `backend/survival/purposes.py` | Modify | Sleep walks onto a bed; `home_of` prefers the built home; the M5 bands |
| `backend/survival/reflexes.py` | Modify | Collapse into a bed; head_home spares building and lighting |
| `backend/survival/work.py`, `farming.py`, `toolmaking.py` | Modify | The reserved rule; shelter-driven goals; trees Mimo planted; ripe crops wait |
| `backend/survival/senses.py` | Modify | `standing_logs` counts placed logs only in grown columns |
| `backend/survival/brain.py` | Modify | Imports M5's purposes; calls the M5 learner |
| `backend/survival/tick.py`, `backend/workers/mimo_worker.py` | Modify | Catch-up one transaction per step; rules between steps |
| `backend/survival/snapshot.py`, `pickers.py` | Modify | `structures` and `chests` in `/api/mimo`; `building` in the model payload |
| `backend/tests/test_survival_{carrying,housework,blueprints,structures,building,storage,lighting,farmstead}.py` | Create | One test file per new module |
| `backend/tests/test_survival_{grid,senses,work,sim,tick_actions,worker,pickers,api,days}.py` | Modify | Claims, grown trees, the budget, the catch-up, the payload and the API, four days alone |
| `frontend/src/survival/types.ts`, `hud.ts`, `animation.ts` (+ tests) | Modify | New kinds and fields, HUD words, home and chest text, poses |
| `frontend/src/survival/SurvivalHud.tsx`, `CraftingPanel.tsx`, `SurvivalWorld.tsx` | Modify | The home line and the chest's contents |
| `frontend/src/survival/cutaway.ts` (+ test), `WorldCanvas.tsx`, `frontend/src/engine/BlockWorld.tsx` | Modify | Cut when a wall or roof hides the pet from the camera |
| `README.md` | Modify | Building |

## Tasks

1. Carry limits and M5's recipes
2. Chests, dropping and sleeping in a bed
3. The building generator
4. What Mimo built, and one rule that keeps every plan off it
5. build_shelter
6. Gathering for the shelter, and trees Mimo planted
7. Storage and a lighter load
8. Torches for the night
9. A farm laid out near home
10. Catching up one transaction at a time
11. What the viewer and the models are told, and four days alone
12. Viewer: building words, the home line and the chest
13. Viewer: see Mimo inside and behind what it built
14. Manual check at 60× and the README

The M4 fix wave changed files some tasks edit; their anchors were dry-run against `17acc6b`: 2 and 5 (`purposes.py`, `reflexes.py`), 4 and 6 (`work.py`, `farming.py`), 7 (`farming.py`), 11 (`snapshot.py`, `purposes.py`).

---
### Task 1: Carry limits and M5's recipes

**Files:**
- Create: `backend/survival/carrying.py`
- Modify: `backend/survival/actions.py`, `backend/services/crafting.py`, `backend/survival/steps.py` (a comment)
- Test: `backend/tests/test_survival_carrying.py`

**Interfaces:**
- Consumes: `actions.finish` (the engine's step finisher), `crafting.RECIPES` and `craft`.
- Produces:
  - `backend.survival.carrying`: `STACK = 32`, `CARRY_STACKS = 16`, `CHEST_STACKS = 24`; `stacks(items: dict[str, int]) -> int`; `room_for(items, item, limit: int) -> int` (how many more of `item` fit in `limit` stacks); `full(items) -> bool`; `settle(inventory, before) -> dict[str, int]` (leaves behind what a step brought in that does not fit, returns it); `after_step(state, before, at)` (settles and keeps `state["full_at"]`: the time something first had to stay behind, cleared when Mimo carries less than 16 stacks).
  - `actions.finish` calls `after_step(state, before, at)` after every finished step.
  - `crafting.RECIPES` gains `torch` (1 coal + 1 sticks → 4 torches), `chest` (8 planks), `bed` (6 planks), all with no station, and `wooden_axe`, `stone_axe`, `iron_axe` (3 planks, cobblestone or iron ingots + 2 sticks, at a crafting table).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_carrying.py`:

```python
import unittest

from backend.services.crafting import RECIPES, craft
from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.carrying import CARRY_STACKS, after_step, room_for, settle, stacks
from backend.survival.grid import Grid
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
# 16 kinds of item, one stack each: Mimo's arms are full.
FULL = {f"item_{n}": 1 for n in range(CARRY_STACKS)}


def pet(inventory):
    state = {"name": "Pip", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": dict(inventory),
             "vitals": dict(START_VITALS), "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    ensure_actions(state)
    return state


class StackTests(unittest.TestCase):
    def test_stacks_hold_up_to_32_of_one_item(self):
        self.assertEqual(stacks({}), 0)
        self.assertEqual(stacks({"dirt": 32, "planks": 1}), 2)
        self.assertEqual(stacks({"dirt": 33, "stone_pickaxe": 1, "moss": 0}), 3)

    def test_room_fills_the_last_stack_then_free_stacks(self):
        self.assertEqual(room_for({"dirt": 30}, "dirt", 1), 2)
        self.assertEqual(room_for({"dirt": 30}, "moss", 1), 0)
        self.assertEqual(room_for({"dirt": 30}, "moss", 2), 32)
        self.assertEqual(room_for(FULL, "item_0", CARRY_STACKS), 31)

    def test_what_a_step_brought_in_that_does_not_fit_stays_behind(self):
        inventory = {**FULL, "cobblestone": 1}
        self.assertEqual(settle(inventory, FULL), {"cobblestone": 1})
        self.assertNotIn("cobblestone", inventory)
        more = {**FULL, "item_0": 33}
        self.assertEqual(settle(more, FULL), {"item_0": 1})
        self.assertEqual(more["item_0"], 32)

    def test_what_mimo_already_carried_is_never_left(self):
        crowded = {**FULL, "dirt": 5}
        self.assertEqual(settle(dict(crowded), crowded), {})

    def test_full_hands_are_noted_once_and_cleared_when_there_is_room(self):
        state = pet({**FULL, "berries": 3})
        after_step(state, FULL, 10.0)
        self.assertEqual(state["full_at"], 10.0)
        state["inventory"]["berries"] = 3
        after_step(state, FULL, 12.0)
        self.assertEqual(state["full_at"], 10.0)
        state["inventory"] = {"berries": 3}
        after_step(state, {}, 14.0)
        self.assertIsNone(state["full_at"])


class FullHandsInTheTickTests(unittest.TestCase):
    def test_a_mined_block_that_does_not_fit_is_left_and_mimo_says_so(self):
        grid = Grid(lambda x, y, z: "dirt" if y <= 1 and (x, y, z) == (1, 1, 0) else "stone" if y <= 0 else "air")
        state = pet(FULL)
        state["queue"] = [{"kind": "mine", "target": [1, 1, 0]}]
        advance_actions(state, ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                             events=[]), 1.0)
        self.assertEqual(grid.material(1, 1, 0), "air")
        self.assertEqual(state["inventory"], FULL)
        self.assertEqual(state["full_at"], 0.6)
        self.assertIn("full", state["last_thought"])


class RecipeTests(unittest.TestCase):
    def test_torches_chests_beds_and_axes_can_be_made(self):
        self.assertEqual(craft({"coal": 1, "sticks": 1}, "torch", set()), {"torch": 4})
        self.assertEqual(craft({"planks": 8}, "chest", set()), {"chest": 1})
        self.assertEqual(craft({"planks": 6}, "bed", set()), {"bed": 1})
        self.assertEqual(craft({"cobblestone": 3, "sticks": 2}, "stone_axe", {"crafting_table"}), {"stone_axe": 1})
        for axe in ("wooden_axe", "stone_axe", "iron_axe"):
            self.assertEqual(RECIPES[axe]["station"], "crafting_table")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_carrying.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.carrying'`.

- [ ] **Step 3: Write the carrying rules**

Create `backend/survival/carrying.py`:

```python
"""How much Mimo can carry, and how much a chest holds (spec section 8).

Items come in stacks of up to 32 of one kind; a tool or station is a stack of its own. Mimo
carries at most 16 stacks and a chest holds 24. When a finished step brings in more than fits,
the part that does not fit stays behind (there are no dropped items to pick up later), the way
a full inventory in a block game leaves the new item on the ground. Only what the step brought
in is left: what Mimo already carried is never lost. Being full makes putting things away in a
chest and dropping low-value items worth doing (backend.survival.storage).
"""

from __future__ import annotations

import math

STACK = 32
CARRY_STACKS = 16
CHEST_STACKS = 24


def stacks(items: dict[str, int]) -> int:
    """How many stacks `items` fill."""
    return sum(math.ceil(count / STACK) for count in items.values() if count > 0)


def room_for(items: dict[str, int], item: str, limit: int) -> int:
    """How many more of `item` fit in `items` without going over `limit` stacks."""
    have = items.get(item, 0)
    in_last = (-have) % STACK if have > 0 else 0
    return in_last + max(0, limit - stacks(items)) * STACK


def full(items: dict[str, int]) -> bool:
    return stacks(items) >= CARRY_STACKS


def settle(inventory: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    """Leave behind what a step brought in that Mimo cannot carry: while it carries more than
    CARRY_STACKS stacks, each item that grew goes back down (a stack at a time, never below what
    it was before the step). Changes `inventory` in place and returns what was left behind."""
    left: dict[str, int] = {}
    for item in sorted(item for item, count in inventory.items() if count > before.get(item, 0)):
        while stacks(inventory) > CARRY_STACKS and inventory.get(item, 0) > before.get(item, 0):
            count = inventory[item]
            drop = min(count % STACK or STACK, count - before.get(item, 0))
            inventory[item] = count - drop
            left[item] = left.get(item, 0) + drop
            if inventory[item] == 0:
                del inventory[item]
    return left


def after_step(state: dict, before: dict[str, int], at: float) -> None:
    """Settle the inventory after a finished step. `state["full_at"]` is the time Mimo last found
    its hands full (something had to stay behind), cleared once it carries less than the limit."""
    if settle(state["inventory"], before) and state.get("full_at") is None:
        state["full_at"] = at
        state["last_thought"] = "My arms are full. I can't carry any more."
    elif not full(state["inventory"]):
        state["full_at"] = None
```

- [ ] **Step 4: Settle the inventory after every finished step**

In `backend/survival/actions.py`, replace:

```python
the purpose that planned it; queued steps carry that purpose as `purpose`. A failure drops the
rest of the plan except its cleanup steps (`keep`, see kept_steps).
```

with:

```python
the purpose that planned it; queued steps carry that purpose as `purpose`. A failure drops the
rest of the plan except its cleanup steps (`keep`, see kept_steps). What a finished step brings
in beyond what Mimo can carry stays behind (backend.survival.carrying).
```

and replace:

```python
from backend.survival.clock import is_night
```

with:

```python
from backend.survival.carrying import after_step
from backend.survival.clock import is_night
```

and replace:

```python
    try:
        event = finish_step(step, state, grid, at)
    except (ValueError, KeyError) as error:
        fail(state, step, at, str(error), failure_code(error))
        return False
    except Exception as error:
        log_once(logger, "finish_step", error)
        fail(state, step, at, "bad step", "bad_step")
        return False
    record(state, step, at, "done")
```

with:

```python
    before = dict(state["inventory"])
    try:
        event = finish_step(step, state, grid, at)
    except (ValueError, KeyError) as error:
        fail(state, step, at, str(error), failure_code(error))
        return False
    except Exception as error:
        log_once(logger, "finish_step", error)
        fail(state, step, at, "bad step", "bad_step")
        return False
    after_step(state, before, at)  # what does not fit stays behind (backend.survival.carrying)
    record(state, step, at, "done")
```

- [ ] **Step 5: Add the recipes**

Beds and chests need no crafting table: Mimo makes them inside its shelter, where no station may stand (resolution 13).

In `backend/services/crafting.py`, replace:

```python
    "campfire": {"ingredients": {"oak_log": 2, "sticks": 3}, "output": {"campfire": 1}},
}
```

with:

```python
    "campfire": {"ingredients": {"oak_log": 2, "sticks": 3}, "output": {"campfire": 1}},
    "torch": {"ingredients": {"coal": 1, "sticks": 1}, "output": {"torch": 4}},
    "chest": {"ingredients": {"planks": 8}, "output": {"chest": 1}},
    "bed": {"ingredients": {"planks": 6}, "output": {"bed": 1}},
    "wooden_axe": {"ingredients": {"planks": 3, "sticks": 2}, "output": {"wooden_axe": 1}, "station": "crafting_table"},
    "stone_axe": {"ingredients": {"cobblestone": 3, "sticks": 2}, "output": {"stone_axe": 1}, "station": "crafting_table"},
    "iron_axe": {"ingredients": {"iron_ingot": 3, "sticks": 2}, "output": {"iron_axe": 1}, "station": "crafting_table"},
}
```

In `backend/survival/steps.py`, replace:

```python
# Axe recipes arrive with purposeful building (M5). Any axe doubles the speed on wood.
```

with:

```python
# Axes are crafting recipes (M5). Any axe doubles the speed on wood.
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_carrying.py"`
Expected: `Ran 7 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 478 tests` … `OK` (7 new). The headless runs still pass: before storage exists (Task 7) Mimo only rarely fills 16 stacks in its first day.

- [ ] **Step 7: Commit**

```bash
git add backend/survival/carrying.py backend/survival/actions.py backend/services/crafting.py backend/survival/steps.py backend/tests/test_survival_carrying.py
git commit -m "feat: carry at most 16 stacks, leave behind what does not fit, and add torch, chest, bed and axe recipes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 2: Chests, dropping and sleeping in a bed

**Files:**
- Create: `backend/survival/housework.py`, `backend/survival/beds.py`
- Modify: `backend/survival/steps.py`, `backend/survival/actions.py`, `backend/survival/purposes.py`, `backend/survival/reflexes.py`
- Test: `backend/tests/test_survival_housework.py`

**Interfaces:**
- Consumes: Task 1's `carrying.room_for`, `CARRY_STACKS`, `CHEST_STACKS`; `steps.register_step`, `StepKind`, `StepFailed`, `in_reach`, `PLACE_SECONDS`; `purposes.plan_sleep`; the `collapse` reflex.
- Produces:
  - Step kinds `store` and `take` (`{"kind", "target": [x, y, z], "item", "amount"}`, 0.3 s, a chest within reach) and `drop` (`{"kind", "item", "amount"}`, 0.3 s); statuses `storing`, `taking`, `dropping`. `housework.chest_key(cell) -> str` ("x,y,z"), `chest_items(state, cell) -> dict` (the live contents in `state["chests"]`).
  - `steps.start_sleep` adds `"bed": True` when the block under Mimo is a bed; `actions.activity_of` then returns `"sleeping_in_bed"`.
  - `backend.survival.beds`: `BED_REACH = 8.0`; `bed_near(s, reach=8.0) -> Cell | None` (the open cell on top of the nearest placed bed); `to_bed(s) -> list[dict]` (a walk onto it, or []).
  - The sleep purpose walks onto a bed within 8 blocks before it sleeps or waits for night; the collapse reflex does the same.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_housework.py`:

```python
import sqlite3
import unittest

from backend.survival.actions import activity_of, ensure_actions
from backend.survival.carrying import CARRY_STACKS, CHEST_STACKS
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.reflexes import by_name
from backend.survival.situation import Situation
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
CHEST = (1, 1, 0)


def room(cells=None):
    """Stone at y <= 0 and air above, with `cells` placed as Mimo placed them."""
    grid = Grid(lambda x, y, z: "stone" if y <= 0 else "air")
    for cell, block in (cells or {}).items():
        grid.put(*cell, block)
    return grid


def pet(position=(0, 1, 0), **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": float(position[0]), "y": float(position[1]),
             "z": float(position[2])}, "inventory": {}, "vitals": dict(START_VITALS), "traits": {},
             "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def run(spec, state, grid):
    step = start_step(spec, state, grid, 0.0)
    finish_step(step, state, grid, step["ends_at"])
    return step


def store(item, amount):
    return {"kind": "store", "target": list(CHEST), "item": item, "amount": amount}


def take(item, amount):
    return {"kind": "take", "target": list(CHEST), "item": item, "amount": amount}


class ChestStepTests(unittest.TestCase):
    def test_storing_moves_items_into_the_chest_in_a_moment(self):
        grid, state = room({CHEST: "chest"}), pet(inventory={"dirt": 10, "planks": 2})
        step = run(store("dirt", 6), state, grid)
        self.assertEqual((step["ends_at"], step["target"], step["item"]), (0.3, {"x": 1, "y": 1, "z": 0}, "dirt"))
        self.assertEqual(state["inventory"], {"dirt": 4, "planks": 2})
        self.assertEqual(state["chests"], {"1,1,0": {"dirt": 6}})
        run(store("dirt", 9), state, grid)
        self.assertEqual(state["inventory"], {"planks": 2})
        self.assertEqual(state["chests"]["1,1,0"], {"dirt": 10})

    def test_taking_moves_them_back_as_far_as_mimo_can_carry(self):
        grid, state = room({CHEST: "chest"}), pet(chests={"1,1,0": {"bread": 3}})
        run(take("bread", 2), state, grid)
        self.assertEqual((state["inventory"], state["chests"]["1,1,0"]), ({"bread": 2}, {"bread": 1}))
        full = pet(inventory={f"item_{n}": 1 for n in range(CARRY_STACKS)}, chests={"1,1,0": {"bread": 3}})
        with self.assertRaisesRegex(StepFailed, "arms are full"):
            start_step(take("bread", 1), full, grid, 0.0)

    def test_a_full_chest_takes_nothing_more(self):
        packed = {f"item_{n}": 32 for n in range(CHEST_STACKS)}
        grid, state = room({CHEST: "chest"}), pet(inventory={"dirt": 3}, chests={"1,1,0": packed})
        with self.assertRaisesRegex(StepFailed, "chest is full"):
            start_step(store("dirt", 3), state, grid, 0.0)

    def test_chest_steps_need_a_chest_in_reach_and_the_item(self):
        grid = room({CHEST: "chest"})
        with self.assertRaisesRegex(StepFailed, "no dirt"):
            start_step(store("dirt", 1), pet(), grid, 0.0)
        with self.assertRaisesRegex(StepFailed, "no bread in the chest"):
            start_step(take("bread", 1), pet(), grid, 0.0)
        with self.assertRaisesRegex(StepFailed, "out of reach"):
            start_step(store("dirt", 1), pet(position=(9, 1, 0), inventory={"dirt": 1}), grid, 0.0)
        with self.assertRaisesRegex(StepFailed, "bad step: amount"):
            start_step(store("dirt", 0), pet(inventory={"dirt": 1}), grid, 0.0)

    def test_a_chest_that_is_gone_took_its_contents_along(self):
        grid, state = room(), pet(inventory={"dirt": 1}, chests={"1,1,0": {"bread": 3}})
        with self.assertRaises(StepFailed) as caught:
            start_step(store("dirt", 1), state, grid, 0.0)
        self.assertEqual(caught.exception.code, "gone")
        self.assertEqual(state["chests"], {})

    def test_dropping_leaves_items_behind_for_good(self):
        grid, state = room(), pet(inventory={"red_mushroom": 3, "dirt": 1})
        run({"kind": "drop", "item": "red_mushroom", "amount": 5}, state, grid)
        self.assertEqual(state["inventory"], {"dirt": 1})


class BedTests(unittest.TestCase):
    def test_sleeping_on_a_bed_rests_at_the_bed_rate(self):
        grid = room({(0, 1, 0): "bed"})
        on_bed = pet(position=(0, 2, 0))
        on_bed["action"] = start_step({"kind": "sleep"}, on_bed, grid, 0.0)
        self.assertTrue(on_bed["action"]["bed"])
        self.assertEqual(activity_of(on_bed), "sleeping_in_bed")
        floor = pet()
        floor["action"] = start_step({"kind": "sleep"}, floor, grid, 0.0)
        self.assertEqual(activity_of(floor), "sleeping")

    def situation(self, grid, clock=NIGHT, position=(0, 1, 0), energy=100.0):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        state = pet(position=position)
        state["vitals"]["energy"] = energy
        return Situation(state, grid, clock, 0.0, db)

    def test_sleep_walks_onto_a_bed_within_eight_blocks_first(self):
        s = self.situation(room({(5, 1, 0): "bed"}))
        plan = PURPOSES["sleep"].plan(s, None)
        self.assertEqual(plan, [{"kind": "walk", "target": [5, 2, 0], "reach": 0.0}, {"kind": "sleep"}])
        on_it = self.situation(room({(5, 1, 0): "bed"}), position=(5, 2, 0))
        self.assertEqual(PURPOSES["sleep"].plan(on_it, None), [{"kind": "sleep"}])
        far = self.situation(room({(12, 1, 0): "bed"}))
        self.assertEqual(PURPOSES["sleep"].plan(far, None), [{"kind": "sleep"}])

    def test_collapsing_mimo_crawls_into_a_near_bed(self):
        collapse = by_name("collapse")
        s = self.situation(room({(3, 1, 0): "bed"}), clock=DAY, energy=5.0)
        self.assertTrue(collapse.trigger(s))
        self.assertEqual(collapse.plan(s, None), [{"kind": "walk", "target": [3, 2, 0], "reach": 0.0}, {"kind": "sleep"}])
        self.assertEqual(collapse.plan(self.situation(room(), clock=DAY, energy=5.0), None), [{"kind": "sleep"}])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_housework.py"`
Expected: 9 failures and errors, among them `StepFailed: unknown step 'store'` and `KeyError: 'bed'`.

- [ ] **Step 3: Write the housework steps**

Create `backend/survival/housework.py`:

```python
"""Housework: the step kinds M5 adds for chests and for leaving things behind, registered in
backend.survival.steps.

- store(cell, item, amount): put carried items into the chest at the cell, within reach. What the
  chest has no room for (24 stacks of 32, backend.survival.carrying) stays with Mimo.
- take(cell, item, amount): take items out of the chest, as many as it holds and Mimo can carry.
- drop(item, amount): leave carried items behind for good. There are no item entities in the
  world, so dropped things are gone.
Each takes 0.3 s, like placing a block. Chest contents live in the state, in state["chests"]
keyed "x,y,z", so they are saved with Mimo and sent to the viewer. A chest that is gone takes
what was in it along.
"""

from __future__ import annotations

from backend.services.crafting import add_item, take_items
from backend.survival.carrying import CARRY_STACKS, CHEST_STACKS, room_for
from backend.survival.grid import Cell, Grid
from backend.survival.steps import (
    PLACE_SECONDS, StepFailed, StepKind, as_cell, as_point, in_reach, label, register_step,
)


def chest_key(cell: Cell) -> str:
    return f"{cell[0]},{cell[1]},{cell[2]}"


def chest_items(state: dict, cell: Cell) -> dict[str, int]:
    """What the chest at `cell` holds (a live dict inside the state; empty for a new chest)."""
    return state.setdefault("chests", {}).setdefault(chest_key(cell), {})


def amount_of(spec: dict) -> int:
    amount = spec.get("amount", 1)
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
        raise StepFailed("bad step: amount")
    return amount


def chest_in_reach(spec: dict, state: dict, grid: Grid) -> Cell:
    target = as_cell(spec["target"])
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    if grid.material(*target) != "chest":
        state.get("chests", {}).pop(chest_key(target), None)
        raise StepFailed("there is no chest there", "gone")
    return target


def running(kind: str, at: float, scale: float, item: str, amount: int, target: Cell | None = None) -> dict:
    step = {"kind": kind, "started_at": at, "ends_at": round(at + PLACE_SECONDS / scale, 3), "item": item,
            "amount": amount}
    if target is not None:
        step["target"] = as_point(target)
    return step


def start_store(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item, amount = spec["item"], amount_of(spec)
    target = chest_in_reach(spec, state, grid)
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to put away", "missing_item")
    if room_for(chest_items(state, target), item, CHEST_STACKS) < 1:
        raise StepFailed("the chest is full", "blocked")
    return running("store", at, scale, item, amount, target)


def finish_store(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = chest_in_reach(step, state, grid)
    chest, item = chest_items(state, target), step["item"]
    moved = min(step["amount"], state["inventory"].get(item, 0), room_for(chest, item, CHEST_STACKS))
    if moved > 0:
        state["inventory"] = take_items(state["inventory"], {item: moved})
        add_item(chest, item, moved)
    return None


def start_take(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item, amount = spec["item"], amount_of(spec)
    target = chest_in_reach(spec, state, grid)
    if chest_items(state, target).get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} in the chest", "missing_item")
    if room_for(state["inventory"], item, CARRY_STACKS) < 1:
        raise StepFailed("its arms are full", "blocked")
    return running("take", at, scale, item, amount, target)


def finish_take(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = chest_in_reach(step, state, grid)
    chest, item = chest_items(state, target), step["item"]
    moved = min(step["amount"], chest.get(item, 0), room_for(state["inventory"], item, CARRY_STACKS))
    if moved > 0:
        chest[item] -= moved
        if chest[item] == 0:
            del chest[item]
        add_item(state["inventory"], item, moved)
    return None


def start_drop(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item, amount = spec["item"], amount_of(spec)
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to drop", "missing_item")
    return running("drop", at, scale, item, amount)


def finish_drop(step: dict, state: dict, grid: Grid, at: float) -> None:
    dropped = min(step["amount"], state["inventory"].get(step["item"], 0))
    if dropped > 0:
        state["inventory"] = take_items(state["inventory"], {step["item"]: dropped})
    return None


register_step(StepKind("store", start_store, finish_store, "storing", cell_field="target", string_field="item"))
register_step(StepKind("take", start_take, finish_take, "taking", cell_field="target", string_field="item"))
register_step(StepKind("drop", start_drop, finish_drop, "dropping", string_field="item"))
```

In `backend/survival/steps.py`, replace:

```python
field work (pick, harvest, till, plant, fish, cook) lives in backend.survival.fieldwork. Mining
leaves or tall grass may drop more (nature.CHANCE_DROPS): saplings, apples, seeds.
```

with:

```python
field work (pick, harvest, till, plant, fish, cook) lives in backend.survival.fieldwork and M5's
housework (store, take, drop) in backend.survival.housework. Mining leaves or tall grass may drop
more (nature.CHANCE_DROPS): saplings, apples, seeds. Sleep on a bed is sleep in a bed.
```

and replace:

```python
# M4's field work (pick, harvest, till, plant, fish, cook) registers itself. It is imported last
# because it builds on everything above.
from backend.survival import fieldwork  # noqa: E402,F401
```

with:

```python
# M4's field work (pick, harvest, till, plant, fish, cook) and M5's housework (store, take, drop)
# register themselves. They are imported last because they build on everything above.
from backend.survival import fieldwork, housework  # noqa: E402,F401
```

- [ ] **Step 4: Sleep in a bed**

In `backend/survival/steps.py`, replace the whole `start_sleep` function with:

```python
def start_sleep(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    # Sleep has no fixed end: actions.py ends it once Mimo is rested and it is not night. Lying on
    # a bed (the block under Mimo) it sleeps in the bed, which rests it faster.
    x, y, z = as_cell(state["position"])
    step = {"kind": "sleep", "started_at": at, "ends_at": None}
    if grid.material(x, y - 1, z) == "bed":
        step["bed"] = True
    return step
```

In `backend/survival/actions.py`, replace the whole `activity_of` function with:

```python
def activity_of(state: dict) -> str:
    """The vitals activity of the current step: sleeping (in a bed when Mimo lies on one), working
    (walk, swim, mine, place) or idle."""
    action = state.get("action")
    if action is None:
        return "idle"
    if action["kind"] == "sleep":
        return "sleeping_in_bed" if action.get("bed") else "sleeping"
    return "working" if is_working(action["kind"]) else "idle"
```

Create `backend/survival/beds.py`:

```python
"""Beds: where Mimo sleeps best.

A bed is a solid block. Mimo sleeps in one by lying on top of it: steps.start_sleep notes the
bed under Mimo, and the vitals then rest it at the bed rate (spec section 3). The sleep purpose
and the collapse reflex walk onto a bed within 8 blocks first, when there is one Mimo can lie on.
"""

from __future__ import annotations

from backend.survival.grid import Cell
from backend.survival.situation import Situation

BED_REACH = 8.0


def bed_near(s: Situation, reach: float = BED_REACH) -> Cell | None:
    """The top of the nearest placed bed within `reach` blocks with room to lie on it."""
    x, _, z = s.here
    tops = [(cell[0], cell[1] + 1, cell[2]) for cell, _ in s.grid.placed_cells(x, z, reach, ("bed",))]
    tops = [top for top in tops if s.grid.passable(top)]
    return min(tops, key=lambda top: (s.distance(top), top)) if tops else None


def to_bed(s: Situation) -> list[dict]:
    """A walk onto the nearest bed within 8 blocks, or nothing when there is none or Mimo lies on it."""
    top = bed_near(s)
    if top is None or top == s.here:
        return []
    return [{"kind": "walk", "target": list(top), "reach": 0.0}]
```

- [ ] **Step 5: Walk onto a bed to sleep, and to collapse**

In `backend/survival/purposes.py`, replace:

```python
from backend.survival.memory import SHELTER_KINDS, cell_of, nearest
```

with:

```python
from backend.survival.beds import to_bed
from backend.survival.memory import SHELTER_KINDS, cell_of, nearest
```

In `backend/survival/purposes.py`, replace the whole `plan_sleep` function with:

```python
def plan_sleep(s: Situation, context: ActionContext) -> list[dict]:
    """Walk onto a bed within 8 blocks (M5), else to a shelter within 8 blocks, then sleep; at
    dusk, wait there for nightfall. After a walk there failed, sleep where Mimo stands."""
    steps = []
    home = nearest(s.places, s.here, SHELTER_KINDS, SLEEP_HOME_REACH)
    tried = (s.state.get("last_failure") or {}).get("purpose") == "sleep"
    x, y, z = s.here
    if not tried and s.grid.material(x, y - 1, z) != "bed":
        steps.extend(to_bed(s))
        if not steps and home is not None and s.distance(cell_of(home)) > 1.0:
            steps.append(walk_to(cell_of(home)))
    steps.append({"kind": "sleep"} if s.night or s.vitals["energy"] < TIRED_BELOW else wait_for_nightfall(s))
    return steps
```

In `backend/survival/reflexes.py`, replace:

```python
collapse (70). Priority 30 is left for sub-project 3's flee; creature reflexes register
themselves with `register`.
```

with:

```python
collapse (70). Priority 30 is left for sub-project 3's flee; creature reflexes register
themselves with `register`. M5: collapse lies down in a bed within 8 blocks when there is one.
```

and replace:

```python
from backend.survival.actions import SAFE_FALL, ActionContext, as_started, fail, take_search
```

with:

```python
from backend.survival.actions import SAFE_FALL, ActionContext, as_started, fail, take_search
from backend.survival.beds import to_bed
```

and replace:

```python
                plan=lambda s, context: [{"kind": "sleep"}],
```

with:

```python
                plan=lambda s, context: [*to_bed(s), {"kind": "sleep"}],
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_housework.py"`
Expected: `Ran 9 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 487 tests` … `OK` (9 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/housework.py backend/survival/beds.py backend/survival/steps.py backend/survival/actions.py backend/survival/purposes.py backend/survival/reflexes.py backend/tests/test_survival_housework.py
git commit -m "feat: store in and take from chests, drop things, and sleep in a bed" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 3: The building generator

**Files:**
- Create: `backend/survival/blueprints.py`
- Modify: `backend/survival/grid.py`
- Test: `backend/tests/test_survival_blueprints.py`, `backend/tests/test_survival_grid.py`

**Interfaces:**
- Consumes: `grid.Grid`, `services.blocks.is_solid`, `is_replaceable`, `worldgen.hash32`, `vitals.is_sheltered` (in tests), `steps.REACH` (in tests).
- Produces:
  - `Grid(natural, load_edits=None, write=None, load_claims=None)`; `Grid.claims: set[Cell]`; `Grid.claimed(cell) -> bool` (loads the chunk's claims with its edits); `Grid.natural_material(x, y, z) -> str` (the generated block, ignoring edits). `world_grid` loads claims from the `structure_cells` table (Task 4 creates it; a world without it has none).
  - `backend.survival.blueprints`: `ROOFS`, `DOOR_SIDES`, `TIERS = ((3, 3), (4, 3), (5, 4))`, `BUILDING` (stand-in order), `LOGS_KEPT = 2`, `STRUCTURAL = ("floor", "wall", "roof")`, `FITTINGS = ("bed", "chest", "campfire", "torch")`, `KEEP_OPEN = ("door", "front", "passage")`, `SITE_RANGE = 12`, `FARM_REACH = 6`; dataclasses `Style(roof, wall, roof_block, windows, doors)`, `Planned(cell, part, block)`, `Blueprint(kind, name, anchor, cells, stands, front, style)` with `parts(*parts)`, `one(part)`, `to_data()`, and `from_data(data) -> Blueprint`; `style_for(traits, seed, salt=0) -> Style`; `supplies(inventory) -> dict[str, int]` (logs beyond the 2 kept count as 4 planks each); `pick_block(wanted, have) -> str | None`; `find_site(grid, center, size, sides, roof, reach=12) -> Site | None`; `shelter(site, style, name) -> Blueprint`; `bill(blueprint, grid=None) -> int` (floor, wall and roof blocks still to place); `design_shelter(grid, seed, center, traits, inventory, owner, salt=0) -> Blueprint | None`; `design_farm(grid, center, size, owner, tilled=(), reach=6) -> Blueprint | None`.
  - A shelter's parts: `floor`, `wall` (block `"natural"` where a one-higher column's ground serves as wall), `roof`, `bed`, `campfire`, `chest`, `torch`, and the cells kept free, with block `"air"`: `door`, `front` (the cell before the door and the one above it), `passage` (from the door to the home cell) and `room` (the rest of the inside). `anchor` is the home cell inside; `stands` are the inside cells except the two back corners, nearest the anchor first; `front` is the cell in front of the door. A farm's parts are `plot` (ground cells, block `farmland`); its anchor is the middle plot.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_blueprints.py`:

```python
import math
import unittest

from backend.services.blocks import is_solid
from backend.survival.blueprints import (
    DOOR_SIDES, FITTINGS, KEEP_OPEN, ROOFS, STRUCTURAL, TIERS, Style, bill, design_farm, design_shelter, find_site,
    from_data, pick_block, shelter, style_for, supplies,
)
from backend.survival.grid import Grid
from backend.survival.steps import REACH
from backend.survival.vitals import is_sheltered

SEED = "12345"


def meadow(cells=None):
    """Grass at y 0 (dirt below, air above), with `cells` placed the way Mimo placed them."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (cells or {}).items():
        grid.put(*cell, block)
    return grid


def built(grid, design):
    """Put every floor, wall and roof block and the bed of `design` into `grid`."""
    for planned in design.cells:
        if planned.part in STRUCTURAL and not is_solid(grid.material(*planned.cell)):
            grid.put(*planned.cell, "cobblestone")
        elif planned.part == "bed":
            grid.put(*planned.cell, "bed")
    return grid


def one_shelter(roof="flat", size=(3, 3), side="north", grid=None):
    grid = grid or meadow()
    site = find_site(grid, (1, 1, 1), size, (side,), roof, reach=0)
    return grid, shelter(site, Style(roof, "cobblestone", "planks", "sides", (side,)), "Pip's Hut")


class StyleTests(unittest.TestCase):
    def test_the_same_traits_and_seed_always_give_the_same_style(self):
        traits = {"creativity": 70, "thrift": 20}
        self.assertEqual(style_for(traits, SEED, 0), style_for(traits, SEED, 0))
        self.assertEqual(sorted(style_for(traits, SEED, 0).doors), sorted(DOOR_SIDES))

    def test_thrift_prefers_cobblestone_walls_and_creativity_fancier_roofs(self):
        self.assertEqual(style_for({"thrift": 80}, SEED).wall, "cobblestone")
        self.assertEqual(style_for({"thrift": 20}, SEED).wall, "planks")
        dull = [style_for({"creativity": 0}, str(seed)) for seed in range(40)]
        bold = [style_for({"creativity": 100}, str(seed)) for seed in range(40)]
        self.assertEqual({style.roof for style in dull}, {"flat"})
        self.assertEqual({style.windows for style in dull}, {"none"})
        self.assertEqual({style.roof for style in bold}, {"gable", "dome"})
        self.assertEqual({style.windows for style in bold}, {"sides"})

    def test_logs_count_as_planks_and_any_block_stands_in_for_a_missing_one(self):
        self.assertEqual(supplies({"oak_log": 4, "planks": 1, "dirt": 3, "berries": 5}), {"planks": 9, "dirt": 3})
        self.assertEqual(supplies({"oak_log": 2}), {})  # a campfire's worth of logs is kept
        self.assertEqual(pick_block("planks", {"planks": 2}), "planks")
        self.assertEqual(pick_block("planks", {"dirt": 2, "cobblestone": 1}), "cobblestone")
        self.assertIsNone(pick_block("planks", {}))


class ShelterTests(unittest.TestCase):
    def test_every_inside_cell_of_every_design_passes_the_shelter_check(self):
        for roof in ROOFS:
            for size in TIERS:
                for side in DOOR_SIDES:
                    grid, design = one_shelter(roof, size, side)
                    built(grid, design)
                    for stand in design.stands:
                        self.assertTrue(is_sheltered(grid.material, *stand), (roof, size, side, stand))
                    bed = design.one("bed")
                    self.assertTrue(is_sheltered(grid.material, bed[0], bed[1] + 1, bed[2]), (roof, size, side))

    def test_mimo_builds_everything_from_inside_without_scaffolding(self):
        for roof in ROOFS:
            for size in TIERS:
                _, design = one_shelter(roof, size)
                for planned in design.parts(*STRUCTURAL, "bed", "chest", "campfire"):
                    self.assertTrue(any(math.dist(stand, planned.cell) <= REACH for stand in design.stands),
                                    (roof, size, planned))

    def test_the_order_is_floor_walls_roof_then_fittings_with_the_door_and_way_in_left_open(self):
        _, design = one_shelter(size=(3, 3))
        parts = [planned.part for planned in design.cells if planned.part in STRUCTURAL + FITTINGS]
        self.assertEqual(parts[:28], ["wall"] * 28)  # 32 wall cells less the 2-block door and 2 windows
        self.assertEqual(parts[28:37], ["roof"] * 9)
        self.assertEqual(parts[37:], ["bed", "campfire", "chest", "torch", "torch", "torch", "torch"])
        self.assertEqual(design.anchor, (1, 1, 1))
        self.assertEqual(design.front, (1, 1, -2))
        self.assertEqual([planned.cell for planned in design.parts("door")], [(1, 1, -1), (1, 2, -1)])
        self.assertEqual([planned.cell for planned in design.parts(*KEEP_OPEN)],
                         [(1, 1, -1), (1, 2, -1), (1, 1, -2), (1, 2, -2), (1, 1, 0), (1, 1, 1)])
        self.assertEqual(bill(design), 37)

    def test_a_gable_roof_rises_to_a_ridge_and_closes_its_ends(self):
        grid, design = one_shelter("gable", (5, 4))  # inside x -1..3, z 0..3, floor 0
        heights = {planned.cell[0]: planned.cell[1] for planned in design.parts("roof")}
        self.assertEqual(heights, {-1: 3, 0: 4, 1: 5, 2: 4, 3: 3})
        ends = [planned.cell for planned in design.parts("wall") if planned.cell[1] >= 3]
        self.assertEqual(sorted(ends), [(0, 3, -1), (0, 3, 4), (1, 3, -1), (1, 3, 4), (1, 4, -1), (1, 4, 4),
                                        (2, 3, -1), (2, 3, 4)])

    def test_a_low_ring_column_gets_a_floor_block_and_a_bump_serves_as_wall(self):
        dug = meadow({(-1, 0, 2): "air"})  # dug out by Mimo under the west wall: not a site
        self.assertIsNone(find_site(dug, (1, 1, 1), (3, 3), ("north",), "flat", reach=0))
        natural = Grid(lambda x, y, z: "grass" if (y == 0 and (x, z) != (-1, 2)) or (y == -1 and (x, z) == (-1, 2))
                       or (y == 1 and (x, z) == (3, 0)) else "dirt" if y < 0 else "air")
        site = find_site(natural, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Hut")
        self.assertIn((-1, 0, 2), [planned.cell for planned in design.parts("floor")])
        self.assertIn(("wall", "natural"), [(planned.part, planned.block) for planned in design.cells
                                            if planned.cell == (3, 1, 0)])
        self.assertEqual(bill(design, natural), 30 + 9 + 1 - 1)  # walls less the door, roof, a floor block, the bump

    def test_sites_keep_off_farmland_saplings_water_stairs_and_what_mimo_built(self):
        for cells in ({(0, 0, 0): "farmland"}, {(2, 1, 1): "sapling"}, {(1, 1, 1): "water"},
                      {(3, 0, 0): "air"}, {(0, 1, 2): "cobblestone"}):
            grid = meadow(cells)
            self.assertIsNone(find_site(grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0), cells)
        claimed = meadow()
        claimed.claims.add((1, 1, 1))
        self.assertIsNone(find_site(claimed, (1, 1, 1), (3, 3), ("north",), "flat", reach=0))
        self.assertIsNotNone(find_site(meadow(), (1, 1, 1), (3, 3), ("north",), "flat", reach=0))

    def test_never_beside_a_dug_column_so_a_staircase_keeps_its_way_out(self):
        stair = meadow({(-2, 0, 1): "air", (-2, -1, 1): "air"})
        self.assertIsNone(find_site(stair, (1, 1, 1), (3, 3), ("north",), "flat", reach=0))
        site = find_site(stair, (1, 1, 1), (3, 3), ("north",), "flat", reach=3)
        self.assertIsNotNone(site)
        self.assertGreater(site.origin[0], -1)

    def test_a_design_is_deterministic_and_survives_json(self):
        traits = {"creativity": 90, "thrift": 30}
        first = design_shelter(meadow(), SEED, (1, 1, 1), traits, {"cobblestone": 90}, "Pip")
        again = design_shelter(meadow(), SEED, (1, 1, 1), traits, {"cobblestone": 90}, "Pip")
        self.assertEqual(first, again)
        self.assertEqual(from_data(first.to_data()), first)
        self.assertTrue(first.name.startswith("Pip's "))

    def test_the_tier_grows_with_creativity_and_the_blocks_carried(self):
        rich = {"cobblestone": 200}
        self.assertEqual(design_shelter(meadow(), SEED, (1, 1, 1), {"creativity": 90}, rich, "Pip").style["size"], [5, 4])
        self.assertEqual(design_shelter(meadow(), SEED, (1, 1, 1), {"creativity": 90}, {"dirt": 5}, "Pip").style["size"],
                         [3, 3])
        self.assertEqual(design_shelter(meadow(), SEED, (1, 1, 1), {"creativity": 10}, rich, "Pip").style["size"], [3, 3])


class FarmTests(unittest.TestCase):
    def test_a_new_farm_is_the_nearest_flat_tillable_square(self):
        design = design_farm(meadow({(0, 0, 0): "sand"}), (0, 0, 0), 3, "Pip")
        self.assertEqual(len(design.cells), 9)
        self.assertEqual({planned.part for planned in design.cells}, {"plot"})
        self.assertNotIn((0, 0, 0), [planned.cell for planned in design.cells])
        self.assertTrue(all(planned.cell[1] == 0 for planned in design.cells))

    def test_an_old_farm_grows_into_the_square_instead_of_a_second_farm(self):
        tilled = ((5, 0, 5), (6, 0, 5), (7, 0, 5))
        grid = meadow({cell: "farmland" for cell in tilled})
        design = design_farm(grid, (5, 0, 5), 3, "Pip", tilled)
        cells = [planned.cell for planned in design.cells]
        self.assertTrue(all(cell in cells for cell in tilled))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_grid.py`, add this test class before `class WorldGridTests`:

```python
class ClaimTests(unittest.TestCase):
    def test_the_natural_block_ignores_edits_and_claims_load_with_each_chunk(self):
        grid = Grid(lambda x, y, z: "stone" if y <= 0 else "air", load_edits=lambda cx, cz: {},
                    load_claims=lambda cx, cz: {(cx * 16, 1, cz * 16)})
        grid.put(0, 0, 0, "air")
        self.assertEqual((grid.material(0, 0, 0), grid.natural_material(0, 0, 0)), ("air", "stone"))
        self.assertTrue(grid.claimed((16, 1, 0)))
        self.assertFalse(grid.claimed((17, 1, 0)))
        self.assertFalse(small_world({}).claimed((0, 1, 0)))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_blueprints.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.blueprints'`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_grid.py"`
Expected: `TypeError` … `unexpected keyword argument 'load_claims'`.

- [ ] **Step 3: Let the grid tell natural blocks and claimed cells**

In `backend/survival/grid.py`, replace:

```python
passes it to the world's write_block, so viewers receive it through block sync. It also keeps
each change until `take_changes` collects it, so renewal can react to what Mimo changed.
```

with:

```python
passes it to the world's write_block, so viewers receive it through block sync. It also keeps
each change until `take_changes` collects it, so renewal can react to what Mimo changed. Cells
that something Mimo built claims (backend.survival.structures) load the same way, chunk by chunk,
so planners that dig or till can leave them alone (`claimed`).
```

and replace:

```python
LoadEdits = Callable[[int, int], dict[Cell, str]]
```

with:

```python
LoadEdits = Callable[[int, int], dict[Cell, str]]
LoadClaims = Callable[[int, int], set[Cell]]
```

and replace:

```python
    def __init__(self, natural: MaterialAt, load_edits: LoadEdits | None = None, write: WriteBlock | None = None):
        self._natural = natural
        self._load_edits = load_edits
        self._write = write
        self._natural_cache: dict[Cell, str] = {}
        self._loaded_chunks: set[tuple[int, int]] = set()
        self.edits: dict[Cell, str] = {}
        self.changes: list[tuple[Cell, str, str]] = []
```

with:

```python
    def __init__(self, natural: MaterialAt, load_edits: LoadEdits | None = None, write: WriteBlock | None = None,
                 load_claims: LoadClaims | None = None):
        self._natural = natural
        self._load_edits = load_edits
        self._write = write
        self._load_claims = load_claims
        self._natural_cache: dict[Cell, str] = {}
        self._loaded_chunks: set[tuple[int, int]] = set()
        self.edits: dict[Cell, str] = {}
        self.changes: list[tuple[Cell, str, str]] = []
        self.claims: set[Cell] = set()
```

and replace:

```python
        for cell, material in self._load_edits(*chunk).items():
            self.edits.setdefault(cell, material)
```

with:

```python
        for cell, material in self._load_edits(*chunk).items():
            self.edits.setdefault(cell, material)
        if self._load_claims is not None:
            self.claims.update(self._load_claims(*chunk))
```

and replace:

```python
    def put(self, x: int, y: int, z: int, material: str) -> None:
```

with:

```python
    def natural_material(self, x: int, y: int, z: int) -> str:
        """The block worldgen put at the cell, before any edit."""
        natural = self._natural_cache.get((x, y, z))
        if natural is None:
            natural = self._natural(x, y, z)
            self._natural_cache[(x, y, z)] = natural
        return natural

    def put(self, x: int, y: int, z: int, material: str) -> None:
```

and replace:

```python
    def solid(self, cell: Cell) -> bool:
        return is_solid(self.material(*cell))
```

with:

```python
    def solid(self, cell: Cell) -> bool:
        return is_solid(self.material(*cell))

    def claimed(self, cell: Cell) -> bool:
        """Part of something Mimo built: a planner that digs or tills leaves it alone."""
        self._load(cell[0], cell[2])
        return cell in self.claims
```

and replace:

```python
    def write(x: int, y: int, z: int, material: str) -> None:
        write_block(db, x, y, z, material)

    return Grid(lambda x, y, z: block_at(x, y, z, seed), load_edits, write)
```

with:

```python
    def write(x: int, y: int, z: int, material: str) -> None:
        write_block(db, x, y, z, material)

    def load_claims(cx: int, cz: int) -> set[Cell]:
        try:
            rows = db.execute("SELECT x,y,z FROM structure_cells WHERE x BETWEEN ? AND ? AND z BETWEEN ? AND ?",
                              (cx * CHUNK, cx * CHUNK + CHUNK - 1, cz * CHUNK, cz * CHUNK + CHUNK - 1)).fetchall()
        except sqlite3.OperationalError:  # a world from before M5, read without its schema update
            return set()
        return {(row[0], row[1], row[2]) for row in rows}

    return Grid(lambda x, y, z: block_at(x, y, z, seed), load_edits, write, load_claims)
```

- [ ] **Step 4: Write the generator**

The site search reads the Grid, never worldgen, so a test's small world is enough. `look_at` finds a column's ground by scanning down from 6 above the reference height: the first cell that is not open must be solid, natural (not an edit), with a solid cell under it, not claimed, and not dug (the natural block above it is not solid, or Mimo dug that one out). `check_site` then applies resolution 6 to one placement and `find_site` tries placements nearest the center first, each door side in the style's order.

Create `backend/survival/blueprints.py`:

```python
"""The building generator: designs for what Mimo builds, from its site, materials and style.

A design is a Blueprint: an ordered list of Planned cells (cell, part, block) that the planner
places one block at a time, floor first, then the walls (bottom row, then top), the roof and the
fittings, plus the cells that matter afterwards: where Mimo lives inside (`inside`), where it
stands to build (`stands`), the door gap and the cell in front of it, and the cells that must
stay open (the passage from the door to the home cell). Everything comes from the inputs alone,
so the same site, style and materials always give the same design, and tests need no world.

Inputs (spec section 8):
- the site: flat-enough natural ground near home, read through the Grid so Mimo's own digging
  and building count (`find_site`). Every column must be untouched ground: never farmland, a
  sapling, water, a dug stair or anything built, and never next to a dug column (a way out);
- the size tier: 3x3, 4x3 or 5x4 inside and two blocks high, the largest the materials cover
  and creativity allows;
- the materials Mimo has: planks and cobblestone first, then other stone and loose blocks, dirt
  as a last resort. Logs beyond the 2 Mimo keeps count as the 4 planks each makes. A design
  names the block each cell prefers; when that block runs short any other building block stands
  in for it;
- style knobs (`style_for`): roof shape (flat, gable, dome), wall material, window pattern and
  door side. Creativity makes a fancier roof and windows likelier and allows bigger tiers,
  thrift prefers cobblestone walls to planks, and the world seed breaks ties, so two pets with
  the same traits still build differently.

A shelter's inside is enclosed on every side with a roof over all of it, so every inside cell
passes the server's shelter check (vitals.is_sheltered). Fittings: a bed and a chest in the back
corners, a campfire outside beside the door, and up to four torches at the outside corners. A
farm is a rectangle of 3x3 to 5x5 plots on flat tillable ground, as near its center as it fits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.services.blocks import is_replaceable, is_solid
from backend.services.worldgen import hash32
from backend.survival.grid import Cell, Grid

ROOFS = ("flat", "gable", "dome")
DOOR_SIDES = ("north", "east", "south", "west")
TIERS = ((3, 3), (4, 3), (5, 4))  # (width across the door side, depth), inside
# Blocks a structure can be built from, in the order they stand in for each other; dirt is last.
BUILDING = ("cobblestone", "planks", "brick", "limestone", "sandstone", "basalt", "moss", "clay", "sand",
            "gravel", "dirt")
LOGS_KEPT = 2  # logs Mimo never turns into building planks: a campfire's worth
STRUCTURAL = ("floor", "wall", "roof")
FITTINGS = ("bed", "chest", "campfire", "torch")
# Parts that must stay open: the door gap, the way in from outside and on to the home cell.
KEEP_OPEN = ("door", "front", "passage")
SITE_RANGE = 12  # blocks from the site's center to where the search starts
CLEARANCE = 5  # open cells a shelter's inside needs above its floor (room for the tallest roof)
SCAN = 6  # blocks above and below the reference height a column's ground is looked for
FARM_REACH = 6  # blocks from the farm's center (beside water, or home) a farm's corner may move
TILLABLE = ("grass", "dirt", "moss")
NAMES = {"flat": "Snug", "gable": "Peaked", "dome": "Round"}
NOUNS = {"planks": "Cabin", "cobblestone": "Cottage", "dirt": "Burrow"}


@dataclass(frozen=True)
class Style:
    roof: str  # "flat", "gable" or "dome"
    wall: str  # the wall block it prefers
    roof_block: str  # the roof block it prefers
    windows: str  # "none" or "sides" (a gap high in the middle of each side wall)
    doors: tuple[str, ...]  # door sides to try, best first


@dataclass(frozen=True)
class Planned:
    cell: Cell
    part: str  # floor, wall, roof, bed, chest, campfire, torch, plot; door, front, passage or room (kept free)
    block: str  # the block it wants; floor, wall and roof take any building block when it runs short


@dataclass(frozen=True)
class Blueprint:
    kind: str  # "shelter" or "farm"
    name: str
    anchor: Cell  # the inside cell Mimo lives in (a shelter), or the middle plot's ground (a farm)
    cells: tuple[Planned, ...]
    stands: tuple[Cell, ...] = ()  # where Mimo stands to build, inside
    front: Cell | None = None  # the cell in front of the door, outside
    style: dict = field(default_factory=dict)

    def parts(self, *parts: str) -> list[Planned]:
        return [planned for planned in self.cells if planned.part in parts]

    def one(self, part: str) -> Cell | None:
        found = self.parts(part)
        return found[0].cell if found else None

    def to_data(self) -> dict:
        return {"kind": self.kind, "name": self.name, "anchor": list(self.anchor),
                "cells": [[*planned.cell, planned.part, planned.block] for planned in self.cells],
                "stands": [list(cell) for cell in self.stands], "front": list(self.front) if self.front else None,
                "style": dict(self.style)}


def from_data(data: dict) -> Blueprint:
    """A Blueprint back from Blueprint.to_data (the structures table keeps it as JSON)."""
    return Blueprint(
        kind=data["kind"], name=data["name"], anchor=tuple(data["anchor"]),
        cells=tuple(Planned((x, y, z), part, block) for x, y, z, part, block in data["cells"]),
        stands=tuple(tuple(cell) for cell in data.get("stands", [])),
        front=tuple(data["front"]) if data.get("front") else None, style=dict(data.get("style", {})))


# Style and materials ---------------------------------------------------------------------------

def roll(seed: str, salt: int, channel: int) -> float:
    """A number in [0, 1) fixed by the world seed, a salt (which structure) and a channel."""
    return hash32(salt, 0, 0, seed, 40 + channel) / 4294967296


def style_for(traits: dict, seed: str, salt: int = 0) -> Style:
    """Style knobs from traits and the world seed: creativity makes a fancy roof and windows
    likelier and mixes the roof block, thrift prefers cobblestone walls, the seed breaks ties."""
    creativity, thrift = float(traits.get("creativity", 50)), float(traits.get("thrift", 50))
    fancy = roll(seed, salt, 1) * 100 < creativity
    roof = ROOFS[1 + int(roll(seed, salt, 2) * 2)] if fancy else "flat"
    wall = "cobblestone" if thrift >= 50 else "planks"
    other = "planks" if wall == "cobblestone" else "cobblestone"
    roof_block = other if creativity >= 50 else wall
    windows = "sides" if roll(seed, salt, 3) * 100 < creativity else "none"
    turn = int(roll(seed, salt, 4) * 4)
    return Style(roof, wall, roof_block, windows, DOOR_SIDES[turn:] + DOOR_SIDES[:turn])


def supplies(inventory: dict) -> dict[str, int]:
    """Building blocks Mimo has, with each log beyond the LOGS_KEPT it keeps for a campfire or a
    tool's sticks counted as the 4 planks it makes."""
    have = {block: inventory.get(block, 0) for block in BUILDING if inventory.get(block, 0) > 0}
    logs = inventory.get("oak_log", 0) - LOGS_KEPT
    if logs > 0:
        have["planks"] = have.get("planks", 0) + 4 * logs
    return have


def pick_block(wanted: str, have: dict[str, int]) -> str | None:
    """The block to place for a cell that wants `wanted`: it, else the first building block left."""
    if have.get(wanted, 0) > 0:
        return wanted
    return next((block for block in BUILDING if have.get(block, 0) > 0), None)


def name_for(style: Style) -> str:
    return f"{NAMES[style.roof]} {NOUNS.get(style.wall, 'Hut')}"


# Sites -----------------------------------------------------------------------------------------

@dataclass
class Ground:
    """What one column offers: its natural ground height and how many open cells stand above it.
    `ground` is None when the column cannot be built on (water, a plant or fitting in the way,
    placed or dug blocks, a cave under it, nothing found near the reference height)."""
    ground: int | None
    open_above: int
    dug: bool


def open_cell(material: str) -> bool:
    return material != "water" and is_replaceable(material)


def look_at(grid: Grid, x: int, z: int, reference: int) -> Ground:
    """Scan the column down from SCAN above `reference` for the first block that is not open."""
    top = reference + SCAN
    for y in range(top, reference - SCAN - 1, -1):
        material = grid.material(x, y, z)
        if open_cell(material):
            continue
        natural = grid.natural_material(x, y, z)
        dug = is_solid(grid.natural_material(x, y + 1, z))
        firm = (is_solid(material) and material == natural and not dug and grid.solid((x, y - 1, z))
                and not any(grid.claimed((x, y + dy, z)) for dy in range(0, CLEARANCE + 1)))
        return Ground(y if firm else None, top - y, dug)
    return Ground(None, 0, False)


class Survey:
    """Columns looked at once and remembered, for one site search."""

    def __init__(self, grid: Grid, reference: int):
        self.grid, self.reference = grid, reference
        self.columns: dict[tuple[int, int], Ground] = {}

    def at(self, x: int, z: int) -> Ground:
        found = self.columns.get((x, z))
        if found is None:
            found = self.columns[(x, z)] = look_at(self.grid, x, z, self.reference)
        return found

    def height(self, x: int, z: int) -> int | None:
        return self.at(x, z).ground

    def room(self, x: int, z: int, up_to: int) -> bool:
        """Every cell from just above the column's ground up to height `up_to` is open."""
        column = self.at(x, z)
        return column.ground is not None and column.ground + column.open_above >= up_to

    def dug_near(self, x: int, z: int) -> bool:
        """A dug column (a stair or hole Mimo made) beside this one: keep the way out clear."""
        return any(self.at(x + dx, z + dz).dug for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def local_to_world(side: str, origin: tuple[int, int], size: tuple[int, int], i: int, j: int) -> tuple[int, int]:
    """(x, z) of local (i, j): i runs across the door side, j from the front (-1 is the front
    wall) to the back. `origin` is the smallest (x, z) inside; the door faces `side`."""
    width, depth = size
    ox, oz = origin
    if side == "north":
        return ox + i, oz + j
    if side == "south":
        return ox + width - 1 - i, oz + depth - 1 - j
    if side == "west":
        return ox + j, oz + width - 1 - i
    return ox + depth - 1 - j, oz + i


@dataclass(frozen=True)
class Site:
    origin: tuple[int, int]
    floor: int  # the ground height inside; Mimo stands at floor + 1
    size: tuple[int, int]
    side: str
    grounds: dict  # (i, j) -> ground height, for every column the design uses

    def world(self, i: int, j: int, y: int) -> Cell:
        x, z = local_to_world(self.side, self.origin, self.size, i, j)
        return x, y, z


def roof_heights(roof: str, width: int, depth: int) -> dict[tuple[int, int], int]:
    """The roof's height above the floor over each inside column: 3 over the walls' top, higher
    toward the middle for a gable (a ridge from front to back) or a dome."""
    heights = {}
    for i in range(width):
        for j in range(depth):
            if roof == "gable":
                rise = min(i, width - 1 - i)
            elif roof == "dome":
                rise = min(i, width - 1 - i, j, depth - 1 - j, 1)
            else:
                rise = 0
            heights[(i, j)] = 3 + rise
    return heights


def door_column(size: tuple[int, int]) -> int:
    return (size[0] - 1) // 2


def check_site(survey: Survey, origin: tuple[int, int], size: tuple[int, int], side: str,
               roof: str) -> Site | None:
    """The site with the inside's local corner at `origin` and the door on `side`, or None when
    the ground there does not suit a shelter."""
    width, depth = size

    def where(i: int, j: int) -> tuple[int, int]:
        return local_to_world(side, origin, size, i, j)

    grounds: dict[tuple[int, int], int] = {}
    floor = survey.height(*where(0, 0))
    if floor is None:
        return None
    top = max(roof_heights(roof, width, depth).values())
    for i in range(width):
        for j in range(depth):
            x, z = where(i, j)
            if survey.height(x, z) != floor or not survey.room(x, z, floor + top):
                return None
            grounds[(i, j)] = floor
    door = door_column(size)
    for i in range(-1, width + 1):
        for j in range(-1, depth + 1):
            if 0 <= i < width and 0 <= j < depth:
                continue
            x, z = where(i, j)
            ground = survey.height(x, z)
            if ground is None or abs(ground - floor) > 1 or not survey.room(x, z, floor + top):
                return None
            if (i, j) == (door, -1) and ground != floor:
                return None
            if survey.dug_near(x, z):
                return None
            grounds[(i, j)] = ground
    x, z = where(door, -2)
    ground = survey.height(x, z)
    if ground is None or not floor - 1 <= ground <= floor or not survey.room(x, z, floor + 2) \
            or survey.dug_near(x, z):
        return None
    grounds[(door, -2)] = ground
    for i, j in ((door + 1, -2), (door - 1, -2), (-2, -2), (width + 1, -2), (-2, depth + 1), (width + 1, depth + 1)):
        ground = survey.height(*where(i, j))
        if ground is not None and floor - 1 <= ground <= floor + 1 and survey.room(*where(i, j), ground + 1):
            grounds[(i, j)] = ground
    return Site(origin, floor, size, side, grounds)


def find_site(grid: Grid, center: Cell, size: tuple[int, int], sides: tuple[str, ...], roof: str,
              reach: int = SITE_RANGE) -> Site | None:
    """The nearest site to `center` (its inside's middle closest first) where a shelter of `size`
    fits with its door on one of `sides` (tried in order)."""
    survey = Survey(grid, center[1] - 1)
    cx, _, cz = center
    width, depth = size
    candidates = []
    for dx in range(-reach, reach + 1):
        for dz in range(-reach, reach + 1):
            if math.hypot(dx, dz) <= reach:
                candidates.append((math.hypot(dx, dz), dx, dz))
    for _, dx, dz in sorted(candidates):
        for side in sides:
            span = (width, depth) if side in ("north", "south") else (depth, width)
            origin = (cx + dx - (span[0] - 1) // 2, cz + dz - (span[1] - 1) // 2)
            site = check_site(survey, origin, size, side, roof)
            if site is not None:
                return site
    return None


# Shelters --------------------------------------------------------------------------------------

def shelter(site: Site, style: Style, name: str) -> Blueprint:
    """The shelter's cells in build order: floor under low wall columns, walls (bottom row, then
    top), the roof (lowest first), then the bed, the campfire, the chest and the torches."""
    width, depth = site.size
    floor, door = site.floor, door_column(site.size)
    heights = roof_heights(style.roof, width, depth)
    ring = [(i, j) for j in range(-1, depth + 1) for i in range(-1, width + 1)
            if not (0 <= i < width and 0 <= j < depth)]
    cells: list[Planned] = []
    for i, j in ring:
        if site.grounds[(i, j)] < floor:
            cells.append(Planned(site.world(i, j, floor), "floor", "dirt"))
    middle = (depth - 1) // 2
    for y in (1, 2):
        for i, j in ring:
            if i == door and j == -1:
                continue
            if y == 2 and style.windows == "sides" and i in (-1, width) and j == middle:
                continue
            if y == 1 and site.grounds[(i, j)] > floor:
                cells.append(Planned(site.world(i, j, floor + 1), "wall", "natural"))
                continue
            cells.append(Planned(site.world(i, j, floor + y), "wall", style.wall))
    if style.roof == "gable":
        for i in range(width):
            for y in range(3, heights[(i, 0)]):
                for j in (-1, depth):
                    cells.append(Planned(site.world(i, j, floor + y), "wall", style.wall))
    for (i, j), height in sorted(heights.items(), key=lambda item: (item[1], item[0][1], item[0][0])):
        cells.append(Planned(site.world(i, j, floor + height), "roof", style.roof_block))
    cells.append(Planned(site.world(0, depth - 1, floor + 1), "bed", "bed"))
    for i in (door + 1, door - 1):
        if (i, -2) in site.grounds and site.grounds[(i, -2)] <= floor:
            cells.append(Planned(site.world(i, -2, site.grounds[(i, -2)] + 1), "campfire", "campfire"))
            break
    cells.append(Planned(site.world(width - 1, depth - 1, floor + 1), "chest", "chest"))
    for i, j in ((-2, -2), (width + 1, -2), (-2, depth + 1), (width + 1, depth + 1)):
        if (i, j) in site.grounds:
            cells.append(Planned(site.world(i, j, site.grounds[(i, j)] + 1), "torch", "torch"))
    home = (door, middle)
    for y in (1, 2):
        cells.append(Planned(site.world(door, -1, floor + y), "door", "air"))
    front = site.world(door, -2, site.grounds[(door, -2)] + 1)
    cells.append(Planned(front, "front", "air"))
    cells.append(Planned((front[0], front[1] + 1, front[2]), "front", "air"))
    passage = {(door, j) for j in range(0, middle + 1)}
    for j in range(depth):
        for i in range(width):
            if (i, j) in passage:
                cells.append(Planned(site.world(i, j, floor + 1), "passage", "air"))
            elif (i, j) not in ((0, depth - 1), (width - 1, depth - 1)):
                cells.append(Planned(site.world(i, j, floor + 1), "room", "air"))
            cells.append(Planned(site.world(i, j, floor + 2), "room", "air"))
    taken = {(0, depth - 1), (width - 1, depth - 1)}
    stands = [site.world(i, j, floor + 1) for j in range(depth) for i in range(width) if (i, j) not in taken]
    stands.sort(key=lambda cell: math.dist(cell, site.world(*home, floor + 1)))
    return Blueprint("shelter", name, site.world(*home, floor + 1), tuple(cells), tuple(stands), front,
                     {"roof": style.roof, "wall": style.wall, "roof_block": style.roof_block,
                      "windows": style.windows, "door": site.side, "size": list(site.size)})


def bill(blueprint: Blueprint, grid: Grid | None = None) -> int:
    """How many blocks the floor, walls and roof still need (natural ground counts as wall)."""
    needed = 0
    for planned in blueprint.parts(*STRUCTURAL):
        if planned.block == "natural":
            continue
        if grid is None or not is_solid(grid.material(*planned.cell)):
            needed += 1
    return needed


def design_shelter(grid: Grid, seed: str, center: Cell, traits: dict, inventory: dict, owner: str,
                   salt: int = 0) -> Blueprint | None:
    """A shelter near `center`: the largest tier creativity allows and the materials cover (else
    the smallest), on the nearest site that fits it."""
    style = style_for(traits, seed, salt)
    have = sum(supplies(inventory).values())
    allowed = 1 + (float(traits.get("creativity", 50)) >= 60) + (float(traits.get("creativity", 50)) >= 80)
    sizes = list(reversed(TIERS[:allowed]))
    for size in sizes:
        site = find_site(grid, center, size, style.doors, style.roof)
        if site is None:
            continue
        design = shelter(site, style, f"{owner}'s {name_for(style)}")
        if bill(design, grid) <= have or size == TIERS[0]:
            return design
    return None


# Farms -----------------------------------------------------------------------------------------

def farm_ground(survey: Survey, x: int, z: int, floor: int) -> bool:
    """Untouched tillable ground at `floor` with room above it."""
    grid = survey.grid
    return (survey.height(x, z) == floor and grid.material(x, floor, z) in TILLABLE
            and open_cell(grid.material(x, floor + 1, z)))


def design_farm(grid: Grid, center: Cell, size: int, owner: str, tilled: tuple[Cell, ...] = (),
                reach: int = FARM_REACH) -> Blueprint | None:
    """A size x size rectangle of plots on flat tillable ground, the nearest to `center` (a ground
    cell: beside water, or home). With `tilled` (the farmland of the farm Mimo keeps, `center`
    its first plot) the rectangle covers `center` and as much of that farmland as it can, so the
    old farm grows instead of a second one starting."""
    survey = Survey(grid, center[1])
    cx, cy, cz = center
    old = {(x, z) for x, y, z in tilled if y == cy}
    best = None
    for dx in range(-reach, reach + 1):
        for dz in range(-reach, reach + 1):
            ox, oz = cx + dx - (size - 1) // 2, cz + dz - (size - 1) // 2
            ground = [(ox + i, oz + j) for i in range(size) for j in range(size)]
            if tilled and (cx, cz) not in ground:
                continue
            floor = cy if tilled else survey.height(ox, oz)
            if floor is None or not all((x, z) in old or farm_ground(survey, x, z, floor) for x, z in ground):
                continue
            key = (-len(old.intersection(ground)), math.hypot(dx, dz), dx, dz)
            if best is None or key < best[0]:
                best = (key, [(x, floor, z) for x, z in ground])
    if best is None:
        return None
    plots = best[1]
    return Blueprint("farm", f"{owner}'s farm", plots[len(plots) // 2],
                     tuple(Planned(cell, "plot", "farmland") for cell in plots), style={"size": [size, size]})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_blueprints.py"`
Expected: `Ran 14 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_grid.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 502 tests` … `OK` (15 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/blueprints.py backend/survival/grid.py backend/tests/test_survival_blueprints.py backend/tests/test_survival_grid.py
git commit -m "feat: a seeded generator for shelters and farms, and claimed cells in the grid" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: What Mimo built, and one rule that keeps every plan off it

**Files:**
- Create: `backend/survival/structures.py`
- Modify: `backend/survival/memory.py`, `backend/survival/work.py`, `backend/survival/farming.py`, `backend/survival/toolmaking.py`
- Test: `backend/tests/test_survival_structures.py`

**Interfaces:**
- Consumes: Task 3's `Blueprint`, `Planned`, `from_data`, `STRUCTURAL`, `FITTINGS`, `KEEP_OPEN`, `Grid.claimed`, `Grid.claims`.
- Produces:
  - `backend.survival.memory`: tables `structures` and `structure_cells` (made by `create_memory_tables`); `BUILT = "built"`; `set_home(db, cell, at, note=BUILT)`; `add_structure(db, kind, name, anchor, at, data, cells) -> int` (`cells` as (cell, part, block)); `structures(db, kinds=None) -> list[dict]` (id, kind, name, x, y, z, status, started_at, built_at, data decoded); `finish_structure(db, number, at)`. `forget` never forgets a home noted `built`.
  - `backend.survival.structures`: `TENDED = ("farmland", "sapling")` (moved from work.py); `reserved(grid, cell) -> bool`; `start(db, grid, blueprint, at) -> int` (stores the design and claims its cells in the grid at once); `blueprint_of(structure) -> Blueprint`; `missing(grid, planned) -> bool`; `todo(grid, blueprint, parts=STRUCTURAL) -> list[Planned]`; `blocked(grid, blueprint) -> list[Cell]` (solid things in the door, the way in or the passage); `damaged(grid, blueprint) -> bool`; `structure_at(db, cell) -> int | None`.
  - `work.stair`, `work.sapling_spots`, `farming.new_plots` and `toolmaking.free_cells` skip reserved cells.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_structures.py`:

```python
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.actions import ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.grid import Grid, world_grid
from backend.survival.memory import (
    BUILT, create_memory_tables, finish_structure, forget, places, remember, set_home, structures,
)
from backend.survival.situation import Situation
from backend.survival.structures import blocked, damaged, reserved, start, structure_at, todo
from backend.survival.toolmaking import free_cells
from backend.survival.vitals import START_VITALS
from backend.survival.work import sapling_spots, stair
from backend.survival.world import SurvivalWorld, new_survival_state

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def meadow(cells=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (cells or {}).items():
        grid.put(*cell, block)
    return grid


def hut(grid):
    site = find_site(grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
    return shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")


def memory():
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return db


def finish(grid, design):
    for planned in design.parts("floor", "wall", "roof"):
        if planned.block != "natural":
            grid.put(*planned.cell, "cobblestone")


class MemoryTests(unittest.TestCase):
    def test_set_home_moves_home_and_keeps_the_old_one_as_a_shelter(self):
        db = memory()
        remember(db, "home", (0, -3, 0), 0.0)
        self.assertFalse(remember(db, "home", (9, 1, 9), 1.0))  # remember never moves home
        set_home(db, (9, 1, 9), 2.0)
        homes = places(db, ("home",))
        self.assertEqual([(place["x"], place["note"]) for place in homes], [(9, BUILT)])
        self.assertEqual([(place["kind"], place["x"]) for place in places(db, ("shelter",))], [("shelter", 0)])

    def test_a_built_home_is_never_forgotten(self):
        db = memory()
        set_home(db, (9, 1, 9), 0.0)
        forget(db, "home", (9, 1, 9))
        self.assertEqual(len(places(db, ("home",))), 1)
        remember(db, "shelter", (30, 1, 30), 0.0)
        forget(db, "shelter", (30, 1, 30))
        self.assertEqual(places(db, ("shelter",)), [])

    def test_a_structure_remembers_its_design_and_claims_its_cells(self):
        db, grid = memory(), meadow()
        design = hut(grid)
        number = start(db, grid, design, 5.0)
        found = structures(db)
        self.assertEqual([(row["kind"], row["name"], row["status"]) for row in found],
                         [("shelter", "Pip's Snug Cottage", "building")])
        self.assertEqual(found[0]["data"]["anchor"], [1, 1, 1])
        self.assertEqual(structure_at(db, (1, 1, 1)), number)
        self.assertTrue(grid.claimed((-1, 1, 0)))  # at once, for plans later in the same tick
        finish_structure(db, number, 9.0)
        self.assertEqual((structures(db)[0]["status"], structures(db)[0]["built_at"]), ("done", 9.0))


class WorldClaimsTests(unittest.TestCase):
    def test_a_world_grid_loads_the_claims_of_each_chunk_it_reads(self):
        with tempfile.TemporaryDirectory() as root:
            world = SurvivalWorld.create(Path(root) / "2.sqlite3", new_survival_state(
                name="Pip", seed="7", spawn={"x": 3682, "y": 5, "z": 4143}, born_at=0.0, traits={}))
            with world.transaction() as db:
                db.execute("INSERT INTO structure_cells(x,y,z,structure,part,block) VALUES (3682, 6, 4143, 1, 'wall', 'dirt')")
            with world.connect() as db:
                grid = world_grid(db, "7")
                self.assertTrue(grid.claimed((3682, 6, 4143)))
                self.assertFalse(grid.claimed((3682, 7, 4143)))


class ProgressTests(unittest.TestCase):
    def test_todo_lists_what_is_missing_in_build_order_and_damage_reopens_it(self):
        grid = meadow()
        design = hut(grid)
        self.assertEqual(len(todo(grid, design)), 39)
        finish(grid, design)
        self.assertEqual(todo(grid, design), [])
        self.assertFalse(damaged(grid, design))
        grid.put(-1, 2, 1, "air")
        self.assertEqual([planned.cell for planned in todo(grid, design)], [(-1, 2, 1)])
        self.assertTrue(damaged(grid, design))
        self.assertEqual([planned.cell for planned in todo(grid, design, ("bed", "campfire"))], [(0, 1, 2), (2, 1, -2)])

    def test_something_solid_in_the_door_or_the_way_in_blocks_it(self):
        grid = meadow()
        design = hut(grid)
        finish(grid, design)
        grid.put(1, 1, -2, "furnace")
        grid.put(1, 1, -1, "campfire")  # a campfire can be walked through
        self.assertEqual(blocked(grid, design), [(1, 1, -2)])
        self.assertTrue(damaged(grid, design))


class ReservedTests(unittest.TestCase):
    def setUp(self):
        self.grid = meadow({(6, 0, 0): "farmland"})
        start(memory(), self.grid, hut(self.grid), 0.0)

    def situation(self, position, inventory=None):
        state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                 "inventory": inventory or {}, "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(state)
        return Situation(state, self.grid, DAY, 0.0, memory())

    def test_the_home_its_door_and_the_way_in_are_reserved_and_so_are_plots(self):
        for cell in ((1, 1, 1), (0, 2, 2), (1, 1, -1), (1, 1, -2), (1, 2, -2), (-1, 1, 0), (6, 0, 0)):
            self.assertTrue(reserved(self.grid, cell), cell)
        self.assertFalse(reserved(self.grid, (5, 1, 5)))

    def test_no_stair_is_dug_into_the_house(self):
        inventory = {"wooden_pickaxe": 1}
        self.assertIsNone(stair(self.grid, {}, (1, 1, 1), (1, 0), inventory, "1"))
        self.assertIsNone(stair(self.grid, {}, (4, 1, 0), (-1, 0), inventory, "1"))
        self.assertIsNotNone(stair(self.grid, {}, (4, 1, 0), (1, 0), inventory, "1"))

    def test_no_station_goes_down_inside_or_in_the_way_in(self):
        self.assertEqual(free_cells(self.situation((1, 1, 1))), [])
        self.assertNotIn((1, 1, -2), free_cells(self.situation((1, 1, -3))))

    def test_no_sapling_is_planted_in_the_way_in(self):
        spots = sapling_spots(self.situation((1, 1, -4), {"sapling": 2}))
        self.assertTrue(spots)
        self.assertNotIn((1, 1, -2), spots)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_structures.py"`
Expected: `ImportError: cannot import name 'BUILT' from 'backend.survival.memory'`.

- [ ] **Step 3: Remember what Mimo built**

In `backend/survival/memory.py`, replace:

```python
- farm: where Mimo tilled its first plot (one per 16 blocks)
M5 adds its own kinds (beds, chests) the same way. A place's `data` is a JSON object that
`update_place` merges into. Places are read in a bounded box around a cell, since memory keeps
growing. Recipes are the ones Mimo crafted or smelted successfully; facts are things it learned,
like that red mushrooms are poisonous. A new life's world starts with empty tables: that is what
"fresh start" wipes.
```

with:

```python
- farm: where Mimo tilled its first plot (one per 16 blocks)
A place's `data` is a JSON object that `update_place` merges into. Places are read in a bounded
box around a cell, since memory keeps growing. Recipes are the ones Mimo crafted or smelted
successfully; facts are things it learned, like that red mushrooms are poisonous.

M5: what Mimo built. The `structures` table keeps each structure it started (kind, name, anchor,
status "building" or "done", and its design as JSON) and `structure_cells` every cell the design
claims, with its part and block, so damage can be found and diggers leave it alone
(backend.survival.structures). When a shelter is done, `set_home` moves home into it, noted
"built" (BUILT); the old home is remembered as a shelter.

A new life's world starts with empty tables: that is what "fresh start" wipes.
```

and replace:

```python
    db.execute("CREATE TABLE IF NOT EXISTS memory_knowledge (subject TEXT NOT NULL, fact TEXT NOT NULL, "
               "learned_at REAL NOT NULL, PRIMARY KEY (subject, fact))")
```

with:

```python
    db.execute("CREATE TABLE IF NOT EXISTS memory_knowledge (subject TEXT NOT NULL, fact TEXT NOT NULL, "
               "learned_at REAL NOT NULL, PRIMARY KEY (subject, fact))")
    db.execute("CREATE TABLE IF NOT EXISTS structures (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, "
               "name TEXT NOT NULL, x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, status TEXT NOT NULL, "
               "started_at REAL NOT NULL, built_at REAL, data TEXT NOT NULL DEFAULT '{}')")
    db.execute("CREATE TABLE IF NOT EXISTS structure_cells (x INTEGER NOT NULL, y INTEGER NOT NULL, "
               "z INTEGER NOT NULL, structure INTEGER NOT NULL, part TEXT NOT NULL, block TEXT NOT NULL, "
               "PRIMARY KEY (x, y, z))")
    db.execute("CREATE INDEX IF NOT EXISTS structure_cells_by_column ON structure_cells(x, z)")
```

and replace:

```python
def forget(db: sqlite3.Connection, kind: str, cell: Cell) -> None:
    db.execute("DELETE FROM memory_places WHERE kind=? AND x=? AND y=? AND z=?", (kind, *cell))
```

with:

```python
def forget(db: sqlite3.Connection, kind: str, cell: Cell) -> None:
    """Forget a place. A home Mimo built is never forgotten: only set_home moves it."""
    db.execute("DELETE FROM memory_places WHERE kind=? AND x=? AND y=? AND z=? "
               "AND NOT (kind='home' AND note=?)", (kind, *cell, BUILT))
```

In `backend/survival/memory.py`, replace:

```python
    return best[1] if best else None
```

with:

```python
    return best[1] if best else None


# What Mimo built (M5) -------------------------------------------------------------------------

BUILT = "built"  # the note on a home Mimo built itself
STRUCTURE_COLUMNS = ("id", "kind", "name", "x", "y", "z", "status", "started_at", "built_at", "data")


def set_home(db: sqlite3.Connection, cell: Cell, at: float, note: str = BUILT) -> None:
    """Make `cell` home, noted `note`: the shelter Mimo built. remember() never moves home, since
    the first sheltered spot stays home until Mimo builds a better one. The old home is
    remembered as a shelter."""
    old = db.execute("SELECT x, y, z FROM memory_places WHERE kind='home'").fetchone()
    db.execute("DELETE FROM memory_places WHERE kind='home'")
    if old is not None and tuple(old) != tuple(cell):
        db.execute("INSERT OR IGNORE INTO memory_places(kind,x,y,z,note,found_at) VALUES ('shelter',?,?,?,'',?)",
                   (*tuple(old), at))
    db.execute("DELETE FROM memory_places WHERE kind='shelter' AND x=? AND y=? AND z=?", tuple(cell))
    db.execute("INSERT INTO memory_places(kind,x,y,z,note,found_at) VALUES ('home',?,?,?,?,?)", (*cell, note, at))


def add_structure(db: sqlite3.Connection, kind: str, name: str, anchor: Cell, at: float, data: dict,
                  cells: list[tuple[Cell, str, str]]) -> int:
    """Remember a structure Mimo started building and the (cell, part, block) cells it claims."""
    cursor = db.execute("INSERT INTO structures(kind,name,x,y,z,status,started_at,data) VALUES (?,?,?,?,?,?,?,?)",
                        (kind, name, *anchor, "building", at, json.dumps(data)))
    number = cursor.lastrowid
    db.executemany("INSERT OR REPLACE INTO structure_cells(x,y,z,structure,part,block) VALUES (?,?,?,?,?,?)",
                   [(*cell, number, part, block) for cell, part, block in cells])
    return number


def structures(db: sqlite3.Connection, kinds: tuple[str, ...] | None = None) -> list[dict]:
    """Every structure Mimo started, oldest first, as dicts with its design decoded in `data`."""
    query, params = f"SELECT {','.join(STRUCTURE_COLUMNS)} FROM structures", []
    if kinds:
        query += f" WHERE kind IN ({','.join('?' * len(kinds))})"
        params.extend(kinds)
    rows = db.execute(query + " ORDER BY id", params).fetchall()
    found = []
    for row in rows:
        structure = dict(zip(STRUCTURE_COLUMNS, tuple(row)))
        structure["data"] = json.loads(structure["data"] or "{}")
        found.append(structure)
    return found


def finish_structure(db: sqlite3.Connection, number: int, at: float) -> None:
    db.execute("UPDATE structures SET status='done', built_at=? WHERE id=?", (at, number))
```

- [ ] **Step 4: Write the structures module and its reserved rule**

Create `backend/survival/structures.py`:

```python
"""What Mimo built, and the cells no other plan may touch.

A structure starts when a building purpose plans its first batch: `start` stores its design
(backend.survival.blueprints) in the structures table and claims every cell of it in
structure_cells (backend.survival.memory), including the cells that must stay open: the door
gap and the passage from the door to the home cell. From then on:
- `todo` lists the cells still waiting for their block, in build order. A finished shelter with
  a floor, wall or roof block missing is damaged, and build_shelter repairs it (`damaged`); a
  door gap or passage something was put in is `blocked`, and build_shelter clears it.
- `reserved` is the one rule every planner that digs, tills, plants or puts a station down
  follows: it keeps off whatever something Mimo built claims (walls, roof, floor, fittings, the
  door gap, the passage and the home cell) and off Mimo's farm plots and saplings (TENDED).
"""

from __future__ import annotations

import sqlite3

from backend.services.blocks import is_solid
from backend.survival.blueprints import FITTINGS, KEEP_OPEN, STRUCTURAL, Blueprint, Planned, from_data
from backend.survival.grid import Cell, Grid
from backend.survival.memory import add_structure

TENDED = ("farmland", "sapling")  # Mimo's own plots and plantings


def reserved(grid: Grid, cell: Cell) -> bool:
    """Part of something Mimo built or tends: no plan digs, tills, plants or puts a station there."""
    return grid.claimed(cell) or grid.material(*cell) in TENDED


def start(db: sqlite3.Connection, grid: Grid, blueprint: Blueprint, at: float) -> int:
    """Remember a structure Mimo starts building and claim its cells at once, so plans made later
    in the same tick keep off them too."""
    cells = [(planned.cell, planned.part, planned.block) for planned in blueprint.cells]
    number = add_structure(db, blueprint.kind, blueprint.name, blueprint.anchor, at, blueprint.to_data(), cells)
    grid.claims.update(planned.cell for planned in blueprint.cells)
    return number


def blueprint_of(structure: dict) -> Blueprint:
    return from_data(structure["data"])


def missing(grid: Grid, planned: Planned) -> bool:
    """The cell still waits for its block: a floor, wall, roof or plot that is not solid (natural
    ground used as a wall counts), a fitting that is not there."""
    material = grid.material(*planned.cell)
    if planned.part in STRUCTURAL:
        return not is_solid(material)
    if planned.part == "plot":
        return material != "farmland"
    return planned.part in FITTINGS and material != planned.block


def todo(grid: Grid, blueprint: Blueprint, parts: tuple[str, ...] = STRUCTURAL) -> list[Planned]:
    """The cells of these parts still waiting for their block, in build order."""
    return [planned for planned in blueprint.parts(*parts) if missing(grid, planned)]


def blocked(grid: Grid, blueprint: Blueprint) -> list[Cell]:
    """Door gap and passage cells something solid was put in."""
    return [planned.cell for planned in blueprint.parts(*KEEP_OPEN) if is_solid(grid.material(*planned.cell))]


def damaged(grid: Grid, blueprint: Blueprint) -> bool:
    return bool(todo(grid, blueprint)) or bool(blocked(grid, blueprint))


def structure_at(db: sqlite3.Connection, cell: Cell) -> int | None:
    """The structure that claims `cell`, if any."""
    row = db.execute("SELECT structure FROM structure_cells WHERE x=? AND y=? AND z=?", tuple(cell)).fetchone()
    return None if row is None else row[0]
```

- [ ] **Step 5: Keep stairs, saplings, plots and stations off what Mimo built**

M4's `work.TENDED` moves into `structures.reserved`, so there is one rule.

In `backend/survival/work.py`, replace:

```python
keeps digging to prospect for iron. It never digs into
water, lava, bedrock, a hole or a cave, or a block it cannot mine, and never digs up farmland or
a sapling. It never digs back the way it came, and never mines the floor of an open cell below
the natural surface (a stair or tunnel it dug earlier, or a cave) unless the same stair just
opened that cell, so it cannot cut its own staircase. The staircase stays climbable, and from
its third stair it is sheltered, so it often becomes Mimo's first home.
```

with:

```python
keeps digging to prospect for iron. It never digs into
water, lava, bedrock, a hole or a cave, or a block it cannot mine, and never digs up farmland, a
sapling or anything Mimo built, its door or the way in (structures.reserved). It never digs back
the way it came, and never mines the floor of an open cell below the natural surface (a stair or
tunnel it dug earlier, or a cave) unless the same stair just opened that cell, so it cannot cut
its own staircase. The staircase stays climbable, and from its third stair it is sheltered, so it
often becomes Mimo's first home.
```

and replace:

```python
from backend.survival.steps import REACH
```

with:

```python
from backend.survival.steps import REACH
from backend.survival.structures import reserved
```

and replace:

```python
FLUIDS = ("water", "lava")
TENDED = ("farmland", "sapling")  # Mimo's own plots and plantings
```

with:

```python
FLUIDS = ("water", "lava")
```

and replace:

```python
                if 1.0 <= math.dist(cell, s.here) <= REACH and sapling_fits(s, cell):
```

with:

```python
                if 1.0 <= math.dist(cell, s.here) <= REACH and sapling_fits(s, cell) and not reserved(s.grid, cell):
```

and replace:

```python
        if material in TENDED or look(grid, changed, (nx, cell[1] + 1, nz)) in TENDED:
            return None  # never dig up Mimo's farm or a sapling it planted
```

with:

```python
        if reserved(grid, cell) or reserved(grid, (nx, cell[1] + 1, nz)):
            return None  # never dig up Mimo's farm, a sapling it planted or anything it built
```

In `backend/survival/farming.py`, replace:

```python
3. till new plots next to the farm, up to 9, for the carrots and seeds left over;
```

with:

```python
3. till new plots next to the farm, up to 9, for the carrots and seeds left over, never where
   something Mimo built keeps its ground (structures.reserved);
```

and replace:

```python
from backend.survival.situation import Situation
```

with:

```python
from backend.survival.situation import Situation
from backend.survival.structures import reserved
```

and replace:

```python
            if y >= surface and s.grid.material(*ground) in TILLABLE and open_above(s, ground):
```

with:

```python
            if (y >= surface and s.grid.material(*ground) in TILLABLE and open_above(s, ground)
                    and not reserved(s.grid, ground) and not reserved(s.grid, above(ground))):
```

In `backend/survival/toolmaking.py`, replace:

```python
(under a solid ceiling, so no floor is dug away) and puts the station in it. The reflex warm_up
places a carried furnace the same way.
```

with:

```python
(under a solid ceiling, so no floor is dug away) and puts the station in it. The reflex warm_up
places a carried furnace the same way. A station never goes where something Mimo built keeps its
room, door or way in (structures.reserved), so inside its shelter Mimo makes no tools.
```

and replace:

```python
from backend.survival.steps import STATION_REACH, WORKSTATIONS
```

with:

```python
from backend.survival.steps import STATION_REACH, WORKSTATIONS
from backend.survival.structures import reserved
```

and replace:

```python
        if material != "water" and is_replaceable(material):
            cells.append(cell)
```

with:

```python
        if material != "water" and is_replaceable(material) and not reserved(s.grid, cell):
            cells.append(cell)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_structures.py"`
Expected: `Ran 10 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 512 tests` … `OK` (10 new; M4's stair, sapling and plot tests still pass, since farmland and saplings are still reserved).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/structures.py backend/survival/memory.py backend/survival/work.py backend/survival/farming.py backend/survival/toolmaking.py backend/tests/test_survival_structures.py
git commit -m "feat: remember what Mimo built and keep stairs, saplings, plots and stations off it" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 5: build_shelter

**Files:**
- Create: `backend/survival/building.py`
- Modify: `backend/survival/brain.py`, `backend/survival/purposes.py`, `backend/survival/reflexes.py`, `backend/tests/test_survival_sim.py`
- Test: `backend/tests/test_survival_building.py`

**Interfaces:**
- Consumes: Task 3's `design_shelter`, `bill`, `pick_block`, `supplies`, `Blueprint`, `Planned`; Task 4's `structures.start`, `todo`, `blocked`, `blueprint_of`, `structure_at`, `memory.structures`, `finish_structure`, `set_home`, `BUILT`; `cooking.made(inventory, item)` (craft steps for one item, M4); `foraging.whole_walk`, `reach_steps` (M4); `purposes.register`, `HOME_RANGE`; `triggers.mark_trigger`.
- Produces:
  - `backend.survival.building`: `PLACES_PER_BATCH = 12`, `SHELTER_BATCHES = 8`, `START_SHARE = 0.5`, `RESUME_BLOCKS = 8`, `FEWEST_BLOCKS = 12`, `NOMINAL_BILL = 38`, `AFTERNOON = 1200.0`, `SHELTER_RANGE = 128`; `structures_near(s, kind, reach=64) -> list[dict]`; `current_shelter(s) -> dict | None` (the newest shelter within 64 blocks); `shelter_elsewhere(s) -> bool`; `site_center(s) -> Cell`; `carried_blocks(s) -> int`; `shelter_design(s) -> Blueprint | None`; `fittings_due(s, blueprint) -> list[Planned]`; `building_need(s) -> int`; `note_building(state, step, context, at)` (the M5 learner). Registered purpose `build_shelter`.
  - `brain.observe_step` calls `note_building` after M4's `learn_from_step`.
  - `purposes.home_of(s)` returns the home noted `built` when it is within 64 blocks, else the nearest home or shelter as before.
  - `reflexes.AT_HOME_WORK = ("build_shelter", "light_up")`: head_home does not fire while either is the purpose.
  - `test_survival_sim.PURPOSE_EVENTS_PER_HOUR` goes from 36 to 46 (resolution 25).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_building.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import building  # noqa: F401  (registers build_shelter)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.building import building_need, note_building
from backend.survival.grid import Grid
from backend.survival.memory import BUILT, create_memory_tables, places, remember, set_home, structures
from backend.survival.purposes import PURPOSES, home_of
from backend.survival.reflexes import by_name
from backend.survival.situation import Situation
from backend.survival.structures import blueprint_of, todo
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
AFTERNOON = {**DAY, "seconds_into_day": 1500.0}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
TRAITS = {"creativity": 0, "thrift": 90, "caution": 50}  # a flat cobblestone roof, no windows: a 39-block hut


def meadow(cells=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (cells or {}).items():
        grid.put(*cell, block)
    return grid


class World:
    """One pet on a flat meadow with its memory, kept across situations like the tick keeps them."""

    def __init__(self, inventory=None, position=(1, 1, 1), grid=None):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = grid or meadow()
        self.state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                      "inventory": dict(inventory or {}), "vitals": dict(START_VITALS), "traits": dict(TRAITS),
                      "last_tick_at": 0.0}
        ensure_actions(self.state)

    def situation(self, clock=DAY):
        return Situation(self.state, self.grid, clock, 0.0, self.db)

    def context(self):
        return ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=self.db)

    def plan(self, clock=DAY):
        s = self.situation(clock)
        return PURPOSES["build_shelter"].plan(s, self.context())

    def carry_out(self, steps):
        """Do the planned steps at once, the way they would end: walks move Mimo, places use a block."""
        context = self.context()
        for step in steps:
            if step["kind"] == "walk":
                self.state["position"] = dict(zip("xyz", map(float, step["target"])))
            elif step["kind"] == "craft":
                from backend.services.crafting import craft
                self.state["inventory"] = craft(self.state["inventory"], step["recipe"], set())
            elif step["kind"] == "place":
                self.state["inventory"][step["block"]] -= 1
                self.grid.put(*step["target"], step["block"])
                note_building(self.state, {**step, "purpose": "build_shelter"}, context, 1.0)
            elif step["kind"] == "mine":
                self.grid.put(*step["target"], "air")
        return context


def places_of(steps):
    return [step for step in steps if step["kind"] == "place"]


class ShelterTests(unittest.TestCase):
    def test_offered_by_day_once_mimo_carries_half_the_blocks(self):
        shelter = PURPOSES["build_shelter"]
        self.assertFalse(shelter.valid(World({"cobblestone": 19}).situation()))
        self.assertTrue(shelter.valid(World({"cobblestone": 20}).situation()))
        self.assertFalse(shelter.valid(World({"cobblestone": 60}).situation(NIGHT)))
        self.assertIn("would need 39 blocks, carrying 20 (short 19)", shelter.facts(World({"cobblestone": 20}).situation()))

    def test_the_first_batch_starts_the_design_walks_in_and_places_twelve_blocks_in_order(self):
        world = World({"cobblestone": 60}, position=(6, 1, 6))
        remember(world.db, "home", (1, -3, 1), 0.0)  # a mine staircase: the shelter goes on the surface above
        steps = world.plan()
        self.assertEqual(steps[0], {"kind": "walk", "target": [1, 1, 1], "reach": 0.0, "whole": True})
        placed = places_of(steps)
        self.assertEqual(len(placed), 12)
        self.assertEqual({step["block"] for step in placed}, {"cobblestone"})
        self.assertEqual([row["status"] for row in structures(world.db)], ["building"])
        self.assertTrue(world.grid.claimed((1, 1, 1)))
        design = blueprint_of(structures(world.db)[0])
        self.assertEqual([step["target"] for step in placed], [list(planned.cell) for planned in todo(world.grid, design)[:12]])

    def test_logs_become_planks_when_the_planks_run_short(self):
        world = World({"oak_log": 10})
        steps = world.plan()
        self.assertEqual(steps[:3], [{"kind": "craft", "recipe": "planks"}] * 3)
        self.assertEqual({step["block"] for step in places_of(steps)}, {"planks"})

    def test_it_pauses_when_the_blocks_run_out_and_gathering_aims_higher(self):
        world = World({"cobblestone": 20, "wooden_pickaxe": 1})
        world.carry_out(world.plan())
        world.carry_out(world.plan())
        self.assertEqual(world.state["inventory"]["cobblestone"], 0)
        s = world.situation()
        self.assertEqual(world.plan(), [])
        self.assertFalse(PURPOSES["build_shelter"].valid(s))
        self.assertEqual(building_need(s), 19)
        self.assertIn("19 blocks to go, carrying 0 (short 19)", PURPOSES["build_shelter"].facts(s))
        world.state["inventory"]["dirt"] = 8
        self.assertTrue(PURPOSES["build_shelter"].valid(world.situation()))
        self.assertEqual({step["block"] for step in places_of(world.plan())}, {"dirt"})

    def test_the_last_block_finishes_it_and_home_moves_in(self):
        world = World({"cobblestone": 40})
        remember(world.db, "home", (30, -4, 30), 0.0)
        with patch("backend.survival.building.site_center", lambda s: (1, 1, 1)):
            for _ in range(4):
                context = world.carry_out(world.plan())
        self.assertEqual(structures(world.db)[0]["status"], "done")
        home = places(world.db, ("home",))[0]
        self.assertEqual(((home["x"], home["y"], home["z"]), home["note"]), ((1, 1, 1), BUILT))
        self.assertEqual(context.events[-1][1:], ("built", "Pip finished building Pip's Snug Cottage and moved in."))
        self.assertIn("built", world.state["brain"]["pending"]["reasons"])
        self.assertEqual(world.state["vitals"]["mood"], 80.0)

    def test_a_finished_shelter_gets_a_bed_and_a_campfire(self):
        world = World({"cobblestone": 40})
        for _ in range(4):
            world.carry_out(world.plan())
        world.state["inventory"] = {"oak_log": 4}
        self.assertTrue(PURPOSES["build_shelter"].valid(world.situation()))
        self.assertEqual(PURPOSES["build_shelter"].score(world.situation()), 45.0)
        steps = world.plan()
        design = blueprint_of(structures(world.db)[0])
        self.assertEqual(places_of(steps), [{"kind": "place", "target": list(design.one("bed")), "block": "bed"},
                                            {"kind": "place", "target": list(design.one("campfire")), "block": "campfire"}])
        self.assertIn({"kind": "craft", "recipe": "bed"}, steps)
        world.carry_out(steps)
        self.assertFalse(PURPOSES["build_shelter"].valid(world.situation()))

    def test_a_damaged_shelter_is_repaired_and_a_blocked_door_cleared(self):
        world = World({"cobblestone": 40})
        for _ in range(4):
            world.carry_out(world.plan())
        design = blueprint_of(structures(world.db)[0])
        wall = design.parts("wall")[5].cell
        world.grid.put(*wall, "air")
        world.grid.put(*design.front, "furnace")
        world.state["inventory"] = {"dirt": 3}
        s = world.situation()
        self.assertTrue(PURPOSES["build_shelter"].valid(s))
        self.assertEqual(PURPOSES["build_shelter"].score(s), 75.0)
        self.assertIn("damaged: 1 blocks missing", PURPOSES["build_shelter"].facts(s))
        self.assertEqual(world.plan(), [{"kind": "mine", "target": list(design.front)},
                                        {"kind": "place", "target": list(wall), "block": "dirt"}])
        world.state["position"] = {"x": 9.0, "y": 1.0, "z": 9.0}  # outside: the way in is cleared from outside
        steps = world.plan()
        self.assertEqual(steps[1], {"kind": "mine", "target": list(design.front)})
        self.assertEqual(steps[0]["reach"], 2.0)
        self.assertEqual(steps[2], {"kind": "walk", "target": list(design.anchor), "reach": 0.0, "whole": True})

    def test_it_scores_in_the_needs_band_and_more_in_the_afternoon(self):
        world = World({"cobblestone": 40})
        self.assertEqual(PURPOSES["build_shelter"].score(world.situation()), 65.0)
        self.assertEqual(PURPOSES["build_shelter"].score(world.situation(AFTERNOON)), 75.0)

    def test_one_shelter_within_128_blocks_is_enough(self):
        world = World({"cobblestone": 40})
        world.plan()
        world.state["position"] = {"x": 90.0, "y": 1.0, "z": 1.0}
        self.assertFalse(PURPOSES["build_shelter"].valid(world.situation()))
        world.state["position"] = {"x": 200.0, "y": 1.0, "z": 1.0}
        self.assertTrue(PURPOSES["build_shelter"].valid(world.situation()))


class HomeTests(unittest.TestCase):
    def test_the_built_home_comes_before_a_nearer_shelter(self):
        world = World()
        remember(world.db, "shelter", (5, 1, 1), 0.0)
        set_home(world.db, (20, 1, 1), 0.0)
        self.assertEqual(home_of(world.situation())["x"], 20)
        found = World()
        remember(found.db, "shelter", (5, 1, 1), 0.0)
        remember(found.db, "home", (20, 1, 1), 0.0)
        self.assertEqual(home_of(found.situation())["x"], 5)

    def test_head_home_leaves_building_and_lighting_at_home_alone(self):
        world = World(position=(10, 1, 10))
        set_home(world.db, (1, 1, 1), 0.0)
        head_home = by_name("head_home")
        dusk = {**DAY, "seconds_into_day": 2100.0}
        self.assertTrue(head_home.trigger(world.situation(dusk)))
        for purpose in ("build_shelter", "light_up"):
            world.state["brain"]["purpose"] = purpose
            self.assertFalse(head_home.trigger(world.situation(dusk)), purpose)


class LessonTests(unittest.TestCase):
    def test_a_planted_sapling_is_remembered_so_its_tree_is_mimos_to_chop(self):
        world = World()
        note_building(world.state, {"kind": "plant", "target": [5, 1, 0], "item": "sapling"}, world.context(), 3.0)
        self.assertEqual([(place["kind"], place["x"], place["z"]) for place in places(world.db, ("tree",))],
                         [("tree", 5, 0)])

    def test_full_arms_ask_for_a_choice(self):
        world = World()
        world.state["full_at"] = 4.0
        note_building(world.state, {"kind": "mine", "target": [5, 0, 0], "block": "dirt"}, world.context(), 4.0)
        self.assertIn("full", world.state["brain"]["pending"]["reasons"])

    def test_each_torch_lifts_mood_a_little(self):
        world = World()
        note_building(world.state, {"kind": "place", "target": [5, 1, 0], "block": "torch"}, world.context(), 4.0)
        self.assertEqual(world.state["vitals"]["mood"], 72.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_building.py"`
Expected: `ImportError: cannot import name 'building' from 'backend.survival'`.

- [ ] **Step 3: Write build_shelter and the M5 learner**

A batch: clear a blocked door or way in (walking to it from outside when Mimo is out), walk inside to the stand nearest the home cell, then place up to 12 blocks in the design's order, walking to another stand only when a block is out of reach. Planks are crafted from logs first when the batch uses more planks than Mimo carries. Once the floor, walls and roof are done, a batch makes and places the bed and the campfire instead.

Create `backend/survival/building.py`:

```python
"""build_shelter: a home Mimo builds itself, one block at a time.

With no shelter of its own within 64 blocks, Mimo designs one (backend.survival.blueprints) on
flat ground near its home (a mine staircase or overhang it found), or near where it stands, and
starts once it carries at least half the blocks it needs. The design and the cells it claims are
remembered (backend.survival.structures), so every later batch goes on with the same design:
walk inside, then place up to 12 blocks a batch in the design's order, floor, walls, roof, making
planks from logs when the planks run short and letting any building block stand in for another.
When the blocks run out the purpose pauses (its plan is done) and the gathering purposes aim for
what is still missing (`building_need`); it goes on once Mimo carries 8 blocks again, or what is
left. When the last floor, wall or roof block is down the shelter is done: home moves into it
(memory.set_home, noted "built"), a notable "built" event is logged and Mimo is pleased.

A finished shelter is furnished by the same purpose: a bed (carried, or made from 6 planks) in
its back corner and a campfire (carried, or made from 2 logs and 3 sticks) beside the door. A
shelter with a floor, wall or roof block gone is damaged and build_shelter repairs it; a door gap
or passage something solid was put in is cleared. build_storage puts a chest in the other back
corner and light_up the torches at the outside corners (backend.survival.storage, lighting).

Scores sit in the needs band: 60 to 70 by caution, 10 more from the afternoon on so the roof is
up before night, 75 for repairs, 45 to 55 for furnishing. Building is day work next to home, so
it takes no late-day penalty; at night Mimo sleeps.

`note_building` hears about every finished step (brain.observe_step): it finishes structures,
remembers the saplings Mimo planted (so gather_wood knows the trees that grow there are its own
to chop), lifts Mimo's mood for each torch and asks for a new choice when Mimo's arms get full.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.worldgen import terrain_height
from backend.survival.blueprints import Blueprint, Planned, bill, design_shelter, pick_block, supplies
from backend.survival.cooking import made
from backend.survival.foraging import reach_steps, whole_walk
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, finish_structure, nearest, remember, set_home, structures
from backend.survival.purposes import HOME_RANGE, Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import REACH, as_cell
from backend.survival.structures import blocked, blueprint_of, start, structure_at, todo
from backend.survival.triggers import mark_trigger

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

PLACES_PER_BATCH = 12
SHELTER_BATCHES = 8
START_SHARE = 0.5  # start a shelter once Mimo carries half the blocks it needs
RESUME_BLOCKS = 8  # go on with one once it carries this many blocks (or all that is left)
FEWEST_BLOCKS = 12  # below this no shelter design is even looked for
NOMINAL_BILL = 38  # about what the smallest shelter takes, before a design says exactly
AFTERNOON = 1200.0  # game seconds into the day from which building gets more urgent
BUILT_MOOD = 10.0
TORCH_MOOD = 2.0
FURNISHINGS = ("bed", "campfire")
SHELTER_RANGE = 2 * HOME_RANGE  # a shelter Mimo built this close is still its own: it starts no other


def structures_near(s: Situation, kind: str, reach: float = HOME_RANGE) -> list[dict]:
    """Structures of `kind` Mimo started, oldest first, whose anchor is within `reach` blocks."""
    known = s.sensed("structures", lambda: structures(s.db) if s.db is not None else [])
    x, _, z = s.here
    return [found for found in known if found["kind"] == kind and math.hypot(found["x"] - x, found["z"] - z) <= reach]


def current_shelter(s: Situation) -> dict | None:
    """The newest shelter Mimo started within 64 blocks, being built or done."""
    near = structures_near(s, "shelter")
    return near[-1] if near else None


def shelter_elsewhere(s: Situation) -> bool:
    """Mimo has a shelter of its own farther than 64 but within 128 blocks: it goes back to that
    one instead of starting another."""
    return current_shelter(s) is None and bool(structures_near(s, "shelter", SHELTER_RANGE))


def site_center(s: Situation) -> Cell:
    """Where to look for a site: home (on the surface above it, when home is a staircase or cave),
    else where Mimo stands."""
    home = nearest(s.places, s.here, ("home",), HOME_RANGE)
    x, y, z = cell_of(home) if home is not None else s.here
    return x, max(y, terrain_height(x, z, s.seed) + 1), z


def carried_blocks(s: Situation) -> int:
    return sum(supplies(s.inventory).values())


def shelter_design(s: Situation) -> Blueprint | None:
    """A new shelter's design (looked for once per Situation)."""
    def look() -> Blueprint | None:
        if carried_blocks(s) < FEWEST_BLOCKS:
            return None
        known = s.sensed("structures", lambda: structures(s.db) if s.db is not None else [])
        return design_shelter(s.grid, s.seed, site_center(s), s.state.get("traits", {}), s.inventory,
                              s.state["name"], len(known))
    return s.sensed("shelter_design", look)


def fittings_due(s: Situation, blueprint: Blueprint) -> list[Planned]:
    """A bed and a campfire still missing that Mimo carries or can make now."""
    due, trial = [], dict(s.inventory)
    for planned in todo(s.grid, blueprint, FURNISHINGS):
        if trial.get(planned.block, 0) > 0:
            trial[planned.block] -= 1
            due.append(planned)
        elif made(trial, planned.block) is not None:
            trial[planned.block] -= 1
            due.append(planned)
    return due


def enough_to_resume(s: Situation, remaining: int) -> bool:
    return carried_blocks(s) >= min(RESUME_BLOCKS, remaining)


def shelter_valid(s: Situation) -> bool:
    if s.night:
        return False
    structure = current_shelter(s)
    if structure is None:
        design = None if shelter_elsewhere(s) else shelter_design(s)
        return design is not None and carried_blocks(s) >= START_SHARE * bill(design, s.grid)
    blueprint = blueprint_of(structure)
    remaining = todo(s.grid, blueprint)
    if remaining:
        return enough_to_resume(s, len(remaining))
    return bool(blocked(s.grid, blueprint)) or bool(fittings_due(s, blueprint))


def shelter_facts(s: Situation) -> str:
    carried = carried_blocks(s)
    structure = current_shelter(s)
    if structure is None:
        design = shelter_design(s)
        need = bill(design, s.grid) if design else NOMINAL_BILL
        return (f"no shelter of its own yet; {design.name if design else 'a small shelter'} would need {need} "
                f"blocks, carrying {carried} (short {max(0, need - carried)})")
    blueprint = blueprint_of(structure)
    remaining = len(todo(s.grid, blueprint))
    if remaining and structure["status"] == "done":
        return f"{structure['name']} is damaged: {remaining} blocks missing, carrying {carried}"
    if remaining:
        return (f"building {structure['name']}: {remaining} blocks to go, carrying {carried} "
                f"(short {max(0, remaining - carried)})")
    furnishing = [planned.part for planned in fittings_due(s, blueprint)]
    return f"{structure['name']} is built; it could still use a {' and a '.join(furnishing) or 'clear door'}"


def shelter_score(s: Situation) -> float:
    structure = current_shelter(s)
    if structure is not None and structure["status"] == "done":
        blueprint = blueprint_of(structure)
        if todo(s.grid, blueprint) or blocked(s.grid, blueprint):
            return 75.0
        return 45.0 + s.trait("creativity") / 10
    urgent = 10.0 if s.clock["seconds_into_day"] >= AFTERNOON else 0.0
    return 60.0 + s.trait("caution") / 10 + urgent


def stand_for(blueprint: Blueprint, at: Cell, cell: Cell) -> Cell | None:
    """Where to stand to reach `cell`: where Mimo will be if it reaches, else the nearest stand that does."""
    if math.dist(at, cell) <= REACH:
        return at
    reaching = [stand for stand in blueprint.stands if math.dist(stand, cell) <= REACH]
    return min(reaching, key=lambda stand: (math.dist(stand, at), stand)) if reaching else None


def planks_first(inventory: dict, blocks: list[str]) -> list[dict]:
    """Craft steps turning logs into the planks `blocks` use beyond the planks carried."""
    short = sum(1 for block in blocks if block == "planks") - inventory.get("planks", 0)
    crafts = min(math.ceil(max(0, short) / 4), inventory.get("oak_log", 0))
    return [{"kind": "craft", "recipe": "planks"} for _ in range(crafts)]


def reach_all(blueprint: Blueprint, stand: Cell, jobs: list[tuple[Cell, dict]]) -> list[dict]:
    """Each job's step, walking to another stand inside first when its cell is out of reach."""
    steps, at = [], stand
    for cell, step in jobs:
        spot = stand_for(blueprint, at, cell)
        if spot is None:
            continue
        if spot != at:
            steps.append(whole_walk(spot))
            at = spot
        steps.append(step)
    return steps


def structural_batch(s: Situation, blueprint: Blueprint, stand: Cell) -> list[dict]:
    """The next blocks in the design's order, making planks from logs when they run short."""
    have = supplies(s.inventory)
    jobs: list[tuple[Cell, dict]] = []
    blocks = []
    for planned in todo(s.grid, blueprint):
        block = pick_block(planned.block, have)
        if block is None or len(blocks) >= PLACES_PER_BATCH:
            break
        have[block] -= 1
        blocks.append(block)
        jobs.append((planned.cell, {"kind": "place", "target": list(planned.cell), "block": block}))
    return planks_first(s.inventory, blocks) + reach_all(blueprint, stand, jobs)


def furnishing_batch(s: Situation, blueprint: Blueprint, stand: Cell) -> list[dict]:
    """Make and place the bed and the campfire Mimo can."""
    inventory, crafting, jobs = dict(s.inventory), [], []
    for planned in fittings_due(s, blueprint):
        if inventory.get(planned.block, 0) < 1:
            steps = made(inventory, planned.block)
            if steps is None:
                continue
            crafting.extend(steps)
        inventory[planned.block] -= 1
        jobs.append((planned.cell, {"kind": "place", "target": list(planned.cell), "block": planned.block}))
    return crafting + reach_all(blueprint, stand, jobs) if jobs else []


def build_batch(s: Situation, blueprint: Blueprint) -> list[dict]:
    """Clear a blocked door or way in (from outside when Mimo is out), walk inside if Mimo is not
    there, then place the next blocks, or furnish the shelter once it is built."""
    clear = reach_steps(s, [(cell, [{"kind": "mine", "target": list(cell)}]) for cell in blocked(s.grid, blueprint)])
    walk: list[dict] = []
    stand = s.here
    if stand not in blueprint.stands:
        stand = blueprint.stands[0]
        walk = [whole_walk(stand)]
    if todo(s.grid, blueprint):
        work = structural_batch(s, blueprint, stand)
    else:
        work = furnishing_batch(s, blueprint, stand)
    return clear + walk + work if clear or work else []


def plan_shelter(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= SHELTER_BATCHES or s.db is None:
        return []
    structure = current_shelter(s)
    if structure is not None:
        return build_batch(s, blueprint_of(structure))
    design = None if shelter_elsewhere(s) else shelter_design(s)
    if design is None or carried_blocks(s) < START_SHARE * bill(design, s.grid):
        return []
    start(s.db, s.grid, design, s.at)
    return build_batch(s, design)


register(Purpose(
    "build_shelter", "build a shelter",
    "Build a shelter of its own near home, block by block, and furnish it with a bed and a campfire.",
    valid=shelter_valid, facts=shelter_facts, score=shelter_score, plan=plan_shelter,
    thoughts=("A roof of my own would be so cozy.", "One block at a time, a home.")))


def building_need(s: Situation) -> int:
    """Blocks the shelter Mimo started still needs beyond what it carries (0 with none started):
    while it waits for them, gather_wood and gather_stone aim that much higher (backend.survival.work)."""
    structure = current_shelter(s)
    if structure is None:
        return 0
    return max(0, len(todo(s.grid, blueprint_of(structure))) - carried_blocks(s))


# What finished steps teach ---------------------------------------------------------------------

def finish_if_built(state: dict, context, number: int, at: float) -> None:
    """Mark a structure done once nothing is left to place or till; a finished shelter becomes home."""
    structure = next((found for found in structures(context.db) if found["id"] == number), None)
    if structure is None or structure["status"] != "building":
        return
    blueprint = blueprint_of(structure)
    parts = ("plot",) if structure["kind"] == "farm" else ("floor", "wall", "roof")
    if todo(context.grid, blueprint, parts):
        return
    finish_structure(context.db, number, at)
    name = state["name"]
    if structure["kind"] == "shelter":
        set_home(context.db, blueprint.anchor, at)
        text = f"{name} finished building {structure['name']} and moved in."
        state["last_thought"] = "I built this myself. Home sweet home."
    else:
        text = f"{name} laid out {structure['name']}."
    context.events.append((at, "built", text))
    state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + BUILT_MOOD)
    mark_trigger(state, "built", at)


def note_building(state: dict, step: dict, context, at: float) -> None:
    """What a finished step teaches (see the module docstring)."""
    db = context.db
    if db is None:
        return
    if state.get("full_at") == at:
        mark_trigger(state, "full", at)
    kind = step["kind"]
    if kind == "plant" and step.get("item") == "sapling":
        remember(db, "tree", as_cell(step["target"]), at)
    elif kind in ("place", "till"):
        cell = as_cell(step["target"])
        number = structure_at(db, cell)
        if number is not None:
            finish_if_built(state, context, number, at)
        if kind == "place" and step.get("block") == "torch":
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + TORCH_MOOD)
```

- [ ] **Step 4: Let the brain learn from building, prefer the built home and leave home work alone at dusk**

In `backend/survival/brain.py`, replace:

```python
in, places visited, and M4's lessons (backend.survival.learning: poisonous food, food patches,
fires and farms). `notice_step` runs after each vitals step: vital crossings (urgent), dawn and
```

with:

```python
in, places visited, M4's lessons (backend.survival.learning: poisonous food, food patches,
fires and farms) and M5's (building.note_building: finished structures, planted trees, full
arms, torches). `notice_step` runs after each vitals step: vital crossings (urgent), dawn and
```

and replace:

```python
from backend.survival import cooking, farming, foraging, toolmaking, work  # noqa: F401  (they register their purposes)
```

with:

```python
from backend.survival import cooking, farming, foraging, toolmaking, work  # noqa: F401  (they register their purposes)
from backend.survival.building import note_building
```

and replace:

```python
    learn_from_step(state, step, context, at)
```

with:

```python
    learn_from_step(state, step, context, at)
    note_building(state, step, context, at)
```

In `backend/survival/purposes.py`, replace:

```python
from backend.survival.memory import SHELTER_KINDS, cell_of, nearest
```

with:

```python
from backend.survival.memory import BUILT, SHELTER_KINDS, cell_of, nearest
```

In `backend/survival/purposes.py`, replace the whole `home_of` function with:

```python
def home_of(s: Situation) -> dict | None:
    """The home Mimo built, when it is within HOME_RANGE blocks (M5); else the nearest remembered
    home or shelter within HOME_RANGE."""
    home = nearest(s.places, s.here, ("home",), HOME_RANGE)
    if home is not None and home["note"] == BUILT:
        return home
    return nearest(s.places, s.here, SHELTER_KINDS, HOME_RANGE)
```

In `backend/survival/reflexes.py`, replace:

```python
themselves with `register`. M5: collapse lies down in a bed within 8 blocks when there is one.
```

with:

```python
themselves with `register`. M5: collapse lies down in a bed within 8 blocks when there is one,
and head_home leaves Mimo be while it builds its shelter or lights torches at home.
```

and replace:

```python
FIRE_STAND = 2.0
```

with:

```python
FIRE_STAND = 2.0
# Purposes that keep Mimo at its home at dusk (M5): head_home leaves them be.
AT_HOME_WORK = ("build_shelter", "light_up")
```

and replace:

```python
    if s.brain["purpose"] in ("go_home", "sleep"):
```

with:

```python
    if s.brain["purpose"] in ("go_home", "sleep", *AT_HOME_WORK):
```

- [ ] **Step 5: Give the headless check room for a day of building**

In `backend/tests/test_survival_sim.py`, replace:

```python
# The first hour is busy: wood, tools, stone, ores, better tools, and from M4 food work too
# (forage, fish, farm, cook, eat), each a change of purpose and a change back.
PURPOSE_EVENTS_PER_HOUR = 36
```

with:

```python
# The first hour is busy: wood, tools, stone, ores, better tools, from M4 food work (forage,
# fish, farm, cook, eat) and from M5 building (a shelter in a few goes, furnishing it, storage,
# dropping junk, a farm, torches), each a change of purpose and a change back.
PURPOSE_EVENTS_PER_HOUR = 46
```

M5's first day holds a shelter built in two or three goes, its furnishing, storage, dropping, a farm and torches, each a change of purpose and a change back. Measured with all of M5 in, on seeds 3, 11, 5 and 21 with both pickers: at most 40 changes in a game hour at the default settings and 41 with `MIMO_SLOW_TESTS=1`. 46 keeps the check meaningful: a thrashing brain makes far more.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_building.py"`
Expected: `Ran 14 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 526 tests` … `OK` (14 new). The headless runs build a shelter on their first day.

- [ ] **Step 7: Commit**

```bash
git add backend/survival/building.py backend/survival/brain.py backend/survival/purposes.py backend/survival/reflexes.py backend/tests/test_survival_building.py backend/tests/test_survival_sim.py
git commit -m "feat: build a shelter block by block from what Mimo carries and move home into it" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: Gathering for the shelter, and trees Mimo planted

**Files:**
- Modify: `backend/survival/work.py`, `backend/survival/senses.py`
- Test: `backend/tests/test_survival_building.py`, `backend/tests/test_survival_senses.py`, `backend/tests/test_survival_work.py`

**Interfaces:**
- Consumes: Task 5's `building.building_need(s) -> int` and the learner's `tree` places (a sapling Mimo planted).
- Produces:
  - `work.TREE = "tree"`; `work.wood_goal(s) -> float` (8 + need / 4) and `work.stone_goal(s) -> float` (12 + need); gather_wood and gather_stone use them for their validity and their plans.
  - `senses.standing_logs(grid, seed, here, skip=frozenset(), radius=24, grown=frozenset())`: placed logs count as a tree only in the `grown` columns; `work.logs_to_chop` passes the columns of remembered `tree` places.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_building.py`, replace:

```python
from backend.survival.vitals import START_VITALS
```

with:

```python
from backend.survival.vitals import START_VITALS
from backend.survival.work import stone_goal, wood_goal
```

and replace:

```python
    def test_one_shelter_within_128_blocks_is_enough(self):
        world = World({"cobblestone": 40})
        world.plan()
        world.state["position"] = {"x": 90.0, "y": 1.0, "z": 1.0}
        self.assertFalse(PURPOSES["build_shelter"].valid(world.situation()))
        world.state["position"] = {"x": 200.0, "y": 1.0, "z": 1.0}
        self.assertTrue(PURPOSES["build_shelter"].valid(world.situation()))


class HomeTests(unittest.TestCase):
```

with:

```python
    def test_one_shelter_within_128_blocks_is_enough(self):
        world = World({"cobblestone": 40})
        world.plan()
        world.state["position"] = {"x": 90.0, "y": 1.0, "z": 1.0}
        self.assertFalse(PURPOSES["build_shelter"].valid(world.situation()))
        world.state["position"] = {"x": 200.0, "y": 1.0, "z": 1.0}
        self.assertTrue(PURPOSES["build_shelter"].valid(world.situation()))

    def test_a_shelter_waiting_for_blocks_makes_gathering_aim_higher(self):
        world = World({"cobblestone": 20, "wooden_pickaxe": 1})
        self.assertEqual((stone_goal(world.situation()), wood_goal(world.situation())), (12, 8))
        world.carry_out(world.plan())
        world.carry_out(world.plan())
        s = world.situation()
        self.assertEqual((stone_goal(s), wood_goal(s)), (12 + 19, 8 + 19 / 4))
        self.assertFalse(PURPOSES["gather_stone"].valid(s))  # never a staircase inside the house
        world.state["position"] = {"x": 8.0, "y": 1.0, "z": 8.0}
        self.assertTrue(PURPOSES["gather_stone"].valid(world.situation()))


class HomeTests(unittest.TestCase):
```

In `backend/tests/test_survival_senses.py`, replace:

```python
        grid = meadow()
        for y in (1, 2, 3, 4):
            grid.put(6, y, 0, "oak_log")
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0)), [(6, 1, 0), (6, 2, 0), (6, 3, 0), (6, 4, 0)])
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0), skip={(6, 0)}), [])
```

with:

```python
        grid = meadow()
        for y in (1, 2, 3, 4):
            grid.put(6, y, 0, "oak_log")
        grown = {(6, 0)}  # a sapling Mimo planted there
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0), grown=grown), [(6, 1, 0), (6, 2, 0), (6, 3, 0), (6, 4, 0)])
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0), skip={(6, 0)}, grown=grown), [])

    @patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [])
    def test_placed_logs_that_did_not_grow_from_a_sapling_are_not_a_tree(self):
        grid = meadow()
        for y in (1, 2):
            grid.put(6, y, 0, "oak_log")  # a log wall, say
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0)), [])
```

In `backend/tests/test_survival_work.py`, replace:

```python
        self.assertFalse(PURPOSES["gather_wood"].valid(situation(state, forest())))


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
```

with:

```python
        self.assertFalse(PURPOSES["gather_wood"].valid(situation(state, forest())))

    def test_a_tree_grown_from_a_planted_sapling_is_chopped_and_a_log_wall_is_not(self):
        placed = ground()
        for y in (1, 2, 3, 4):
            placed.put(9, y, 0, "oak_log")
        with patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: []):
            self.assertFalse(PURPOSES["gather_wood"].valid(situation(pet(), placed)))
            grown = situation(pet(), placed, places_seen=[("tree", (9, 1, 0), "")])
            self.assertEqual(PURPOSES["gather_wood"].plan(grown, context(placed))[:2], [walk(9, 1, 0, 2.0), mine(9, 1, 0)])


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_building.py"`
Expected: `ImportError: cannot import name 'stone_goal' from 'backend.survival.work'`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_senses.py"`
Expected: `TypeError` … `unexpected keyword argument 'grown'`, and `FAIL: test_placed_logs_that_did_not_grow_from_a_sapling_are_not_a_tree`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py"`
Expected: `FAIL: test_a_tree_grown_from_a_planted_sapling_is_chopped_and_a_log_wall_is_not` (a log wall is chopped).

- [ ] **Step 3: Count only the trees Mimo planted among placed logs**

In `backend/survival/senses.py`, replace:

```python
def standing_logs(grid: Grid, seed: str, here: Cell, skip: set[tuple[int, int]] | frozenset = frozenset(),
                  radius: int = TREE_SEARCH) -> list[Cell]:
    """The logs still standing in the nearest tree worth trying, lowest first; [] when there is none.
    Trees grown from saplings count too: their logs are placed blocks."""
```

with:

```python
def standing_logs(grid: Grid, seed: str, here: Cell, skip: set[tuple[int, int]] | frozenset = frozenset(),
                  radius: int = TREE_SEARCH, grown: set[tuple[int, int]] | frozenset = frozenset()) -> list[Cell]:
    """The logs still standing in the nearest tree worth trying, lowest first; [] when there is none.
    Trees grown from saplings Mimo planted count too, in the `grown` columns: their logs are placed
    blocks. Other placed logs (something built) are not trees."""
```

and replace:

```python
    for cell, _ in grid.placed_cells(x, z, radius, (LOG,)):
        trunks.setdefault((cell[0], cell[2]), set()).add(cell)
```

with:

```python
    for cell, _ in grid.placed_cells(x, z, radius, (LOG,)):
        if (cell[0], cell[2]) in grown:
            trunks.setdefault((cell[0], cell[2]), set()).add(cell)
```

- [ ] **Step 4: Aim gathering at what a started shelter lacks**

In `backend/survival/work.py`, replace:

```python
gather_wood chops the nearest standing tree within 24 blocks, lowest log first, until Mimo
carries 8 logs' worth of wood (craft_tools turns logs into planks). Trees only come back when
Mimo plants saplings (they drop from leaves), so each batch first plants up to 2 carried
saplings on open ground within reach, 3 blocks or more from any trunk or other sapling, on the
natural surface (never in Mimo's own staircase) and 2 blocks or more from a home or shelter.
gather_stone needs a pickaxe:
it digs a staircase down from where Mimo stands, two blocks per stair, and turns into a level
tunnel 10 blocks under the surface (or at y -3), until Mimo carries 12 cobblestone; with a stone
pickaxe and no iron ore seen yet, it keeps digging to prospect for iron. It never digs into
water, lava, bedrock, a hole or a cave, or a block it cannot mine, and never digs up farmland, a
sapling or anything Mimo built, its door or the way in (structures.reserved). It never digs back
the way it came, and never mines the floor of an open cell below the natural surface (a stair or
tunnel it dug earlier, or a cave) unless the same stair just opened that cell, so it cannot cut
its own staircase. The staircase stays climbable, and from its third stair it is sheltered, so it
often becomes Mimo's first home.
```

with:

```python
gather_wood chops the nearest standing tree within 24 blocks, lowest log first, until Mimo
carries 8 logs' worth of wood (craft_tools turns logs into planks), and while a shelter Mimo
started waits for blocks, that many more as logs (building.building_need). A tree is a generated
one or one grown from a sapling Mimo planted (remembered as a `tree` place); other placed logs are
something built, not a tree. Trees only come back when Mimo plants saplings (they drop from
leaves), so each batch first plants up to 2 carried saplings on open ground within reach, 3
blocks or more from any trunk or other sapling, on the natural surface (never in Mimo's own
staircase) and 2 blocks or more from a home or shelter.
gather_stone needs a pickaxe:
it digs a staircase down from where Mimo stands, two blocks per stair, and turns into a level
tunnel 10 blocks under the surface (or at y -3), until Mimo carries 12 cobblestone (and the
blocks a started shelter still waits for); with a stone pickaxe and no iron ore seen yet, it
keeps digging to prospect for iron. It never digs into water, lava, bedrock, a hole or a cave, or
a block it cannot mine, and never digs up farmland, a sapling or anything Mimo built, its door or
the way in (structures.reserved). It never digs back the way it came, and never mines the floor
of an open cell below the natural surface (a stair or tunnel it dug earlier, or a cave) unless
the same stair just opened that cell, so it cannot cut its own staircase. The staircase stays
climbable, and from its third stair it is sheltered, so it often becomes Mimo's first home.
```

and replace:

```python
from backend.survival.purposes import Purpose, late_penalty, register, underground, walk_to
```

with:

```python
from backend.survival.purposes import Purpose, late_penalty, register, underground, walk_to
from backend.survival.building import building_need
```

and replace:

```python
FLUIDS = ("water", "lava")
ORE_RANGE = 48.0
```

with:

```python
FLUIDS = ("water", "lava")
TREE = "tree"  # a remembered place: a sapling Mimo planted, so the tree there is its to chop
ORE_RANGE = 48.0
```

and replace:

```python
    if wood(s.inventory) >= WOOD_GOAL:
        return []
```

with:

```python
    if wood(s.inventory) >= wood_goal(s):
        return []
```

and replace:

```python
    valid=lambda s: wood(s.inventory) < WOOD_GOAL and bool(logs_to_chop(s)),
```

with:

```python
    valid=lambda s: wood(s.inventory) < wood_goal(s) and bool(logs_to_chop(s)),
```

and replace:

```python
    goal = math.inf if prospecting(s) else STONE_GOAL
```

with:

```python
    goal = math.inf if prospecting(s) else stone_goal(s)
```

In `backend/survival/work.py`, replace the whole `logs_to_chop` function with:

```python
def logs_to_chop(s: Situation) -> list[Cell]:
    """The nearest tree's logs: a generated tree, or one grown from a sapling Mimo planted (placed
    logs anywhere else, like a wall, are not trees)."""
    grown = {(place["x"], place["z"]) for place in s.places if place["kind"] == TREE}
    return standing_logs(s.grid, s.seed, s.here, failed_columns(s.state), grown=grown)


def wood_goal(s: Situation) -> float:
    """8 logs of wood, and the shelter's missing blocks as logs (4 planks each) on top."""
    return WOOD_GOAL + building_need(s) / 4
```

In `backend/survival/work.py`, replace the whole `wants_stone` function with:

```python
def stone_goal(s: Situation) -> float:
    """12 cobblestone, and the shelter's missing blocks on top."""
    return STONE_GOAL + building_need(s)


def wants_stone(s: Situation) -> bool:
    return has_pickaxe(s.inventory) and (s.count("cobblestone") < stone_goal(s) or prospecting(s))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_building.py"`
Expected: `Ran 15 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_senses.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 529 tests` … `OK` (3 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/work.py backend/survival/senses.py backend/tests/test_survival_building.py backend/tests/test_survival_senses.py backend/tests/test_survival_work.py
git commit -m "feat: gather what a started shelter lacks and chop only trees, never placed logs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 7: Storage and a lighter load

**Files:**
- Create: `backend/survival/storage.py`
- Modify: `backend/survival/brain.py`, `backend/survival/farming.py`
- Test: `backend/tests/test_survival_storage.py`

**Interfaces:**
- Consumes: Task 1's `carrying`; Task 2's `housework.chest_key` and the `store`, `take` and `drop` steps; Task 5's `building.current_shelter`; Task 4's `blueprint_of`; `cooking.made`; `foraging.FOOD_WANTED`, `food_need`, `whole_walk`; `purposes.foods`; `steps.FOOD`, `AXES`, `REACH`; `crafting.TOOL_RANK`.
- Produces:
  - `backend.survival.storage`: `STORE_FROM = 13`, `DROP_FROM = 10`, `TAKE_BELOW = 20.0`, `STORE_STEPS = 8`, `KEEP`, `FLOWERS`, `LEAST_USEFUL`; `chest_spot(s)`, `chest_placed(s, cell)`, `chest_contents(s, cell)`, `spare_food(s)`, `to_store(s, cell)`, `carried_food(s)`, `to_take(s, cell)`, `junk(s)`. Registered purposes `build_storage` and `drop_items`.
  - `farming.farm_jobs` harvests ripe crops only while `food_need(s) > 0`.
  - `brain.py` imports `storage`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_storage.py`:

```python
import sqlite3
import unittest

from backend.survival import farming, storage  # noqa: F401  (register farm, build_storage and drop_items)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, finish_structure, know
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.structures import start
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
LOOSE = {"dirt": 40, "moss": 3, "gravel": 5, "sand": 5, "clay": 2, "basalt": 1, "limestone": 1, "sandstone": 1,
         "copper_ore": 2, "brick": 1, "glass": 1, "cobblestone": 20, "oak_log": 3}  # 14 stacks


def meadow():
    return Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")


class Home:
    """A pet at the door of a finished 3x3 shelter (inside x 0..2, z 0..2, chest corner (2, 1, 2))."""

    def __init__(self, inventory, chest=None, position=(1, 1, 1)):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = meadow()
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in design.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        self.chest = design.one("chest")
        self.state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                      "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        if chest is not None:
            self.grid.put(*self.chest, "chest")
            self.state["chests"] = {"2,1,2": dict(chest)}
        ensure_actions(self.state)

    def situation(self):
        return Situation(self.state, self.grid, DAY, 0.0, self.db)

    def plan(self, name):
        s = self.situation()
        return PURPOSES[name].plan(s, ActionContext(grid=self.grid, clock_at=lambda at: DAY,
                                                    planner=lambda *args: [], events=[], db=self.db))


def store(item, amount):
    return {"kind": "store", "target": [2, 1, 2], "item": item, "amount": amount}


class StorageTests(unittest.TestCase):
    def test_nearly_full_arms_make_a_chest_and_fill_it_with_what_mimo_does_not_need(self):
        home = Home({**LOOSE, "planks": 8})
        self.assertEqual(home.chest, (2, 1, 2))
        self.assertTrue(PURPOSES["build_storage"].valid(home.situation()))
        steps = home.plan("build_storage")
        self.assertEqual(steps[:2], [{"kind": "craft", "recipe": "chest"},
                                     {"kind": "place", "target": [2, 1, 2], "block": "chest"}])
        self.assertEqual(steps[2:6], [store("dirt", 40), store("gravel", 5), store("sand", 5), store("cobblestone", 4)])
        self.assertEqual(len(steps), 2 + 8)

    def test_not_offered_with_room_to_spare_or_without_a_built_shelter(self):
        self.assertFalse(PURPOSES["build_storage"].valid(Home({"dirt": 40, "planks": 8}).situation()))
        home = Home({**LOOSE, "planks": 8})
        home.db.execute("DELETE FROM structures")
        self.assertFalse(PURPOSES["build_storage"].valid(home.situation()))

    def test_it_walks_home_first_and_takes_food_out_when_mimo_carries_little(self):
        home = Home({"cobblestone": 1}, chest={"bread": 4, "berries": 9}, position=(9, 1, 9))
        s = home.situation()
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        self.assertEqual(PURPOSES["build_storage"].score(s), 55.0)
        self.assertEqual(home.plan("build_storage"), [
            {"kind": "walk", "target": [1, 1, 1], "reach": 0.0, "whole": True},
            {"kind": "take", "target": [2, 1, 2], "item": "bread", "amount": 3}])

    def test_more_food_than_a_days_worth_goes_in_the_chest(self):
        home = Home({**LOOSE, "bread": 4, "berries": 10}, chest={})
        steps = home.plan("build_storage")
        self.assertIn(store("berries", 10), steps)
        self.assertNotIn("bread", [step.get("item") for step in steps])

    def test_the_fuller_mimo_is_the_more_it_wants_to_tidy(self):
        score = PURPOSES["build_storage"].score
        self.assertEqual(score(Home({**LOOSE, "planks": 8}).situation()), 60.0)  # 15 stacks
        home = Home({**LOOSE, "planks": 8, "seeds": 9})  # 16 stacks, and something had to stay behind
        home.state["full_at"] = 5.0
        self.assertEqual(score(home.situation()), 70.0)


class DropTests(unittest.TestCase):
    def test_known_poison_old_pickaxes_and_flowers_are_dropped(self):
        home = Home({"dirt": 40, "cobblestone": 20, "oak_log": 3, "planks": 5, "seeds": 3, "sticks": 2,
                     "red_mushroom": 3, "wooden_pickaxe": 1, "stone_pickaxe": 1, "flower_pink": 2})  # 11 stacks
        self.assertFalse(PURPOSES["drop_items"].valid(Home({"dirt": 1, "wooden_pickaxe": 1, "stone_pickaxe": 1}).situation()))
        know(home.db, "red_mushroom", "poisonous", 0.0)
        s = home.situation()
        self.assertTrue(PURPOSES["drop_items"].valid(s))
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "red_mushroom", "amount": 3},
                                                   {"kind": "drop", "item": "wooden_pickaxe", "amount": 1},
                                                   {"kind": "drop", "item": "flower_pink", "amount": 2}])
        self.assertEqual(PURPOSES["drop_items"].score(s), 38.0)

    def test_full_with_no_chest_the_least_useful_blocks_go_too(self):
        full = {**LOOSE, "seeds": 1, "wheat": 1}
        home = Home(full)
        self.assertEqual([step["item"] for step in home.plan("drop_items")], ["moss", "gravel", "sand", "clay"])
        with_chest = Home(full, chest={})
        self.assertFalse(PURPOSES["drop_items"].valid(with_chest.situation()))


class FarmHarvestTests(unittest.TestCase):
    def test_ripe_crops_wait_in_the_field_while_mimo_carries_a_days_food(self):
        grid = meadow()
        grid.put(3, 0, 0, "farmland")
        grid.put(3, 1, 0, "wheat_3")
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)

        def situation(inventory):
            state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                     "inventory": inventory, "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
            ensure_actions(state)
            return Situation(state, grid, DAY, 0.0, db)

        context = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=db)
        hungry = PURPOSES["farm"].plan(situation({}), context)
        self.assertIn({"kind": "harvest", "target": [3, 1, 0]}, hungry)
        self.assertFalse(PURPOSES["farm"].valid(situation({"bread": 3})))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_storage.py"`
Expected: `ImportError: cannot import name 'storage' from 'backend.survival'`.

- [ ] **Step 3: Write build_storage and drop_items**

Create `backend/survival/storage.py`:

```python
"""A lighter load: build_storage and drop_items (spec section 8, inventory limit).

Mimo carries at most 16 stacks (backend.survival.carrying). build_storage puts a chest in the
back corner the shelter design keeps for it, under the roof, making it from 8 planks when Mimo
carries none, and puts away what Mimo does not need to carry: loose blocks, materials beyond what
a day's work takes (KEEP), and food beyond a day's worth. It takes food back out when Mimo
carries less than a meal's worth. It is offered at the built shelter when Mimo's arms are getting
full (13 stacks) or the chest holds food Mimo needs, and scores higher the fuller Mimo is.

drop_items leaves behind what is no use at all: food Mimo knows is poisonous, pickaxes and axes a
better one replaced, and flowers. When its arms are full and there is no chest to use, the least
useful loose blocks (moss, gravel, sand, clay) go too. It scores low while Mimo has room and
high when it is full.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.crafting import TOOL_RANK
from backend.survival.building import current_shelter
from backend.survival.carrying import CARRY_STACKS, CHEST_STACKS, room_for, stacks
from backend.survival.cooking import made
from backend.survival.foraging import FOOD_WANTED, whole_walk
from backend.survival.housework import chest_key
from backend.survival.purposes import Purpose, foods, register
from backend.survival.situation import Situation
from backend.survival.steps import AXES, FOOD, REACH
from backend.survival.structures import blueprint_of

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

STORE_FROM = 13  # stacks from which putting things away is worth a trip home
DROP_FROM = 10
TAKE_BELOW = 20.0  # hunger points of food carried below which Mimo takes food out
STORE_STEPS = 8
# What Mimo keeps on it of each material; the rest goes into the chest. Items not listed (tools,
# stations, food up to a day's worth) stay with Mimo.
KEEP = {"cobblestone": 16, "planks": 16, "oak_log": 8, "sticks": 8, "coal": 8, "iron_ore": 3, "iron_ingot": 3,
        "seeds": 8, "sapling": 4, "wheat": 6, "torch": 4, "dirt": 0, "gravel": 0, "sand": 0, "clay": 0, "moss": 0,
        "basalt": 0, "limestone": 0, "sandstone": 0, "brick": 0, "glass": 0, "copper_ore": 0, "copper_ingot": 0}
FLOWERS = ("flower_orange", "flower_pink", "flower_yellow")
LEAST_USEFUL = ("moss", "gravel", "sand", "clay")


def chest_spot(s: Situation) -> tuple[int, int, int] | None:
    """The chest corner of the shelter Mimo built, or None before it has one."""
    structure = current_shelter(s)
    if structure is None or structure["status"] != "done":
        return None
    return blueprint_of(structure).one("chest")


def chest_placed(s: Situation, cell) -> bool:
    return cell is not None and s.grid.material(*cell) == "chest"


def chest_contents(s: Situation, cell) -> dict[str, int]:
    return dict(s.state.get("chests", {}).get(chest_key(cell), {})) if cell else {}


def spare_food(s: Situation) -> list[tuple[str, int]]:
    """Food beyond a day's worth (60 hunger), the least filling first."""
    kept, spare = 0.0, []
    for item in foods(s.inventory, s.poisons):
        count = s.inventory[item]
        keep = 0
        while keep < count and kept < FOOD_WANTED:
            keep += 1
            kept += FOOD[item]
        if count > keep:
            spare.append((item, count - keep))
    return list(reversed(spare))


def to_store(s: Situation, cell) -> list[tuple[str, int]]:
    """(item, amount) Mimo would put away, most first, as far as the chest has room."""
    chest = chest_contents(s, cell)
    wanted = [(item, count - KEEP[item]) for item, count in s.inventory.items()
              if item in KEEP and count > KEEP[item]] + spare_food(s)
    found = []
    for item, amount in sorted(wanted, key=lambda entry: (-entry[1], entry[0])):
        amount = min(amount, room_for(chest, item, CHEST_STACKS))
        if amount > 0:
            chest[item] = chest.get(item, 0) + amount
            found.append((item, amount))
    return found[:STORE_STEPS]


def carried_food(s: Situation) -> float:
    return sum(FOOD[item] * s.inventory[item] for item in foods(s.inventory, s.poisons))


def to_take(s: Situation, cell) -> list[tuple[str, int]]:
    """Food to take out of the chest when Mimo carries less than a meal's worth, best first."""
    if carried_food(s) >= TAKE_BELOW:
        return []
    chest, have, found = chest_contents(s, cell), carried_food(s), []
    for item in foods(chest, s.poisons):
        amount = 0
        while amount < chest[item] and have < FOOD_WANTED:
            amount += 1
            have += FOOD[item]
        if amount:
            found.append((item, amount))
    return found


def storage_valid(s: Situation) -> bool:
    cell = chest_spot(s)
    if cell is None or s.night:
        return False
    if not chest_placed(s, cell):
        can_have = s.count("chest") > 0 or made(dict(s.inventory), "chest") is not None
        return can_have and stacks(s.inventory) >= STORE_FROM
    return (stacks(s.inventory) >= STORE_FROM and bool(to_store(s, cell))) or bool(to_take(s, cell))


def storage_facts(s: Situation) -> str:
    cell = chest_spot(s)
    chest = chest_contents(s, cell)
    where = "a chest at home" if chest_placed(s, cell) else "no chest yet"
    return (f"carrying {stacks(s.inventory)} of {CARRY_STACKS} stacks; {where} holding {stacks(chest)} of "
            f"{CHEST_STACKS} stacks")


def storage_score(s: Situation) -> float:
    cell = chest_spot(s)
    if chest_placed(s, cell) and to_take(s, cell) and stacks(s.inventory) < STORE_FROM:
        return 55.0
    return 50.0 + 5.0 * max(0, stacks(s.inventory) - STORE_FROM) + (5.0 if s.state.get("full_at") else 0.0)


def plan_storage(s: Situation, context: ActionContext) -> list[dict]:
    """Walk home, make and place the chest if it is not there, put things away and take food out."""
    cell = chest_spot(s)
    if cell is None or s.brain["batches"] > 0:
        return []
    structure = current_shelter(s)
    home = blueprint_of(structure).anchor
    steps = [] if s.distance(cell) <= REACH and s.here in blueprint_of(structure).stands else [whole_walk(home)]
    if not chest_placed(s, cell):
        if s.count("chest") < 1:
            crafting = made(dict(s.inventory), "chest")
            if crafting is None:
                return []
            steps.extend(crafting)
        steps.append({"kind": "place", "target": list(cell), "block": "chest"})
    for kind, moves in (("store", to_store(s, cell)), ("take", to_take(s, cell))):
        steps.extend({"kind": kind, "target": list(cell), "item": item, "amount": amount} for item, amount in moves)
    return steps


register(Purpose(
    "build_storage", "put things away",
    "Put a chest in the shelter and store what it does not need to carry; take food back out when short.",
    valid=storage_valid, facts=storage_facts, score=storage_score, plan=plan_storage,
    thoughts=("My arms are getting full. Time to tidy up.", "A chest would keep all this safe.")))


def junk(s: Situation) -> list[tuple[str, int]]:
    """(item, amount) that is no use to carry: known poison, replaced tools, flowers; and, full with
    no chest to use, the least useful loose blocks."""
    found = [(item, s.inventory[item]) for item in s.poisons if s.inventory.get(item, 0) > 0]
    best = max((TOOL_RANK[tool] for tool in TOOL_RANK if s.count(tool)), default=0)
    found += [(tool, s.count(tool)) for tool, rank in TOOL_RANK.items() if s.count(tool) and rank < best]
    axes = [axe for axe in AXES if s.count(axe)]
    found += [(axe, s.count(axe)) for axe in axes[:-1]]
    found += [(flower, s.count(flower)) for flower in FLOWERS if s.count(flower)]
    if stacks(s.inventory) >= CARRY_STACKS and not chest_placed(s, chest_spot(s)):
        found += [(item, s.count(item)) for item in LEAST_USEFUL if s.count(item)]
    return found


def plan_drop(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return [{"kind": "drop", "item": item, "amount": amount} for item, amount in junk(s)]


register(Purpose(
    "drop_items", "drop what it cannot use",
    "Leave behind food it knows is poisonous, tools a better one replaced and other things of no use.",
    valid=lambda s: stacks(s.inventory) >= DROP_FROM and bool(junk(s)),
    facts=lambda s: f"carrying {stacks(s.inventory)} of {CARRY_STACKS} stacks; no use for "
                    + ", ".join(item.replace("_", " ") for item, _ in junk(s)),
    score=lambda s: 30.0 + 8.0 * max(0, stacks(s.inventory) - DROP_FROM),
    plan=plan_drop,
    thoughts=("I don't need all of this.", "Lighter is better.")))
```

- [ ] **Step 4: Let ripe crops wait while Mimo carries enough food**

In `backend/survival/farming.py`, replace:

```python
1. harvest ripe crops within 24 blocks and plant each plot again with what it gave;
```

with:

```python
1. harvest ripe crops within 24 blocks and plant each plot again with what it gave, but only
   while Mimo carries less than a day's worth of food: otherwise the crops wait in the field;
```

and replace:

```python
    for cell in ripe[:PLOTS_PER_BATCH]:
```

with:

```python
    # Ripe crops wait in the field while Mimo carries a day's worth of food: its arms fill up.
    for cell in ripe[:PLOTS_PER_BATCH] if food_need(s) > 0 else []:
```

- [ ] **Step 5: Let the brain offer them**

In `backend/survival/brain.py`, replace:

```python
from backend.survival.building import note_building
```

with:

```python
from backend.survival import storage  # noqa: F401  (M5's building purposes)
from backend.survival.building import note_building
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_storage.py"`
Expected: `Ran 8 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 537 tests` … `OK` (8 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/storage.py backend/survival/brain.py backend/survival/farming.py backend/tests/test_survival_storage.py
git commit -m "feat: put things away in a chest at home, drop what is no use and leave ripe crops while fed" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 8: Torches for the night

**Files:**
- Create: `backend/survival/lighting.py`
- Modify: `backend/survival/brain.py`
- Test: `backend/tests/test_survival_lighting.py`

**Interfaces:**
- Consumes: Task 5's `building.current_shelter` and the learner's torch mood; Task 4's `blueprint_of`, `todo`; `toolmaking.make`, `Short`; `foraging.reach_steps`, `whole_walk`; `purposes.LATE_DAY`; `situation.NIGHTFALL`.
- Produces: `backend.survival.lighting`: `HOME_REACH = 16.0`; `dark_corners(s) -> list[Cell]`; `evening(s) -> bool`; `torch_supply(s, wanted) -> tuple[list[dict], int]`. Registered purpose `light_up`. `brain.py` imports `lighting`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_lighting.py`:

```python
import sqlite3
import unittest

from backend.survival import lighting  # noqa: F401  (registers light_up)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, finish_structure
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.structures import start
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
EVENING = {**DAY, "seconds_into_day": 2000.0}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
CORNERS = [[-2, 1, -2], [4, 1, -2], [-2, 1, 4], [4, 1, 4]]


class LightTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in design.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)

    def situation(self, inventory, clock=EVENING, position=(1, 1, 1)):
        state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                 "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(state)
        return Situation(state, self.grid, clock, 0.0, self.db)

    def plan(self, s):
        return PURPOSES["light_up"].plan(s, ActionContext(grid=self.grid, clock_at=lambda at: s.clock,
                                                           planner=lambda *args: [], events=[], db=self.db))

    def test_offered_in_the_evening_at_home_with_torches_or_coal_and_sticks(self):
        light = PURPOSES["light_up"]
        self.assertTrue(light.valid(self.situation({"torch": 1})))
        self.assertTrue(light.valid(self.situation({"coal": 1, "planks": 2})))
        self.assertFalse(light.valid(self.situation({})))
        self.assertFalse(light.valid(self.situation({"torch": 4}, clock=DAY)))
        self.assertFalse(light.valid(self.situation({"torch": 4}, clock=NIGHT)))
        self.assertFalse(light.valid(self.situation({"torch": 4}, position=(40, 1, 40))))
        self.assertEqual(light.score(self.situation({"torch": 4})), 72.0)

    def test_it_makes_torches_puts_one_on_each_dark_corner_and_goes_back_inside(self):
        steps = self.plan(self.situation({"coal": 2, "sticks": 1, "planks": 2}))
        self.assertEqual([step["recipe"] for step in steps if step["kind"] == "craft"], ["torch"])
        placed = [step["target"] for step in steps if step["kind"] == "place"]
        self.assertEqual(sorted(placed), sorted(CORNERS))
        self.assertTrue(all(step["whole"] for step in steps if step["kind"] == "walk"))
        self.assertEqual(steps[-1], {"kind": "walk", "target": [1, 1, 1], "reach": 0.0, "whole": True})

    def test_lit_corners_are_left_and_one_torch_lights_one_corner(self):
        self.grid.put(-2, 1, -2, "torch")
        steps = self.plan(self.situation({"torch": 1}))
        self.assertEqual(len([step for step in steps if step["kind"] == "place"]), 1)
        for cell in CORNERS[1:]:
            self.grid.put(*cell, "torch")
        self.assertFalse(PURPOSES["light_up"].valid(self.situation({"torch": 3})))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_lighting.py"`
Expected: `ImportError: cannot import name 'lighting' from 'backend.survival'`.

- [ ] **Step 3: Write light_up**

`torch_supply` crafts one batch of 4 torches at a time until Mimo carries enough, and stops at the first batch it cannot make. (Asking `cooking.made` for "one torch" while Mimo carries one already would return no steps forever.)

Create `backend/survival/lighting.py`:

```python
"""light_up: torches around home for the night.

From 5 game minutes before dusk until nightfall, at the shelter it built, Mimo puts a torch on
each outside corner the design marked (up to four) that is still dark, making torches from coal
and sticks (1 coal and 1 stick make 4) when it carries none. Torches glow at night in the viewer
and each one lifts Mimo's mood a little (building.note_building); in sub-project 3 they will keep
creatures away. The walks to the corners go all the way or not at all, and head_home leaves
light_up alone, since it keeps Mimo at home.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival.building import current_shelter
from backend.survival.foraging import reach_steps, whole_walk
from backend.survival.grid import Cell
from backend.survival.purposes import LATE_DAY, Purpose, register
from backend.survival.situation import NIGHTFALL, Situation
from backend.survival.structures import blueprint_of, todo
from backend.survival.toolmaking import Short, make

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

HOME_REACH = 16.0  # light_up is offered this close to the shelter


def dark_corners(s: Situation) -> list[Cell]:
    """The shelter's torch cells without a torch that one can stand in now (open, on solid ground)."""
    structure = current_shelter(s)
    if structure is None or structure["status"] != "done":
        return []
    blueprint = blueprint_of(structure)
    if s.distance(blueprint.anchor) > HOME_REACH:
        return []
    return [planned.cell for planned in todo(s.grid, blueprint, ("torch",))
            if s.grid.standable(planned.cell)]


def evening(s: Situation) -> bool:
    return not s.night and LATE_DAY <= s.clock["seconds_into_day"] < NIGHTFALL


def torch_supply(s: Situation, wanted: int) -> tuple[list[dict], int]:
    """Craft steps making torches (4 at a time) until Mimo has `wanted`, or as many as it can, and
    how many it will then carry."""
    inventory, steps = dict(s.inventory), []
    while inventory.get("torch", 0) < wanted:
        trial, more = dict(inventory), []
        try:
            make(trial, "torch", inventory.get("torch", 0) + 1, more)
        except Short:
            break
        inventory, steps = trial, steps + more
    return steps, inventory.get("torch", 0)


def light_valid(s: Situation) -> bool:
    return evening(s) and bool(dark_corners(s)) and torch_supply(s, 1)[1] > 0


def plan_light(s: Situation, context: ActionContext) -> list[dict]:
    if not evening(s) or s.brain["batches"] > 0:
        return []
    corners = dark_corners(s)
    crafting, have = torch_supply(s, len(corners))
    jobs = [(cell, [{"kind": "place", "target": list(cell), "block": "torch"}]) for cell in corners[:have]]
    if not jobs:
        return []
    home = blueprint_of(current_shelter(s)).anchor
    return crafting + reach_steps(s, jobs) + [whole_walk(home)]  # and back inside for the night


register(Purpose(
    "light_up", "light torches", "Put torches around home before night; they glow in the dark.",
    valid=light_valid,
    facts=lambda s: f"{len(dark_corners(s))} dark corners around home, carrying {s.count('torch')} torches",
    score=lambda s: 72.0, plan=plan_light,
    thoughts=("A little light for the night.", "Torches make home feel safe.")))
```

- [ ] **Step 4: Let the brain offer it**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import storage  # noqa: F401  (M5's building purposes)
```

with:

```python
from backend.survival import lighting, storage  # noqa: F401  (M5's building purposes)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_lighting.py"`
Expected: `Ran 3 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 540 tests` … `OK` (3 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/lighting.py backend/survival/brain.py backend/tests/test_survival_lighting.py
git commit -m "feat: light torches on the corners of home before night" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 9: A farm laid out near home

**Files:**
- Create: `backend/survival/farmstead.py`
- Modify: `backend/survival/brain.py`
- Test: `backend/tests/test_survival_farmstead.py`

**Interfaces:**
- Consumes: Task 3's `design_farm`, `Blueprint`; Task 4's `start`, `todo`, `blueprint_of`, `reserved`; Task 5's `site_center`, `structures_near`, `note_building` (it finishes a farm on its last till); `farming.FARM_TRAVEL`, `PLANTABLE`, `SITE_SEARCH`, `next_seed`, `open_above`, `plant`; `foraging.reach_steps`; `senses.shores_near`.
- Produces: `backend.survival.farmstead`: `PLOTS_PER_BATCH = 4`, `FARM_BATCHES = 6`, `OLD_FARM_REACH = 3.0`; `plantables(s)`, `farm_size(s)`, `current_farm(s)`, `farm_design(s)`, `plots_left(s, blueprint)`. Registered purpose `build_farm`. `brain.py` imports `farmstead`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_farmstead.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import farmstead  # noqa: F401  (registers build_farm)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.building import note_building
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, remember, structures
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.structures import reserved
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
SHORE = ((8, 1, 0), (9, 0, 0))


class Farmstead:
    def __init__(self, inventory, farmland=()):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        for cell in farmland:
            self.grid.put(*cell, "farmland")
        remember(self.db, "home", (0, 1, 0), 0.0)
        self.state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                      "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(self.state)

    def situation(self):
        return Situation(self.state, self.grid, DAY, 0.0, self.db)

    def context(self):
        return ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=self.db)

    def plan(self):
        return PURPOSES["build_farm"].plan(self.situation(), self.context())


@patch("backend.survival.farmstead.shores_near", lambda grid, seed, here, radius: [SHORE])
class BuildFarmTests(unittest.TestCase):
    def test_a_first_farm_is_laid_out_beside_the_nearest_shore_four_plots_a_batch(self):
        farm = Farmstead({"seeds": 5, "carrot": 2})
        self.assertTrue(PURPOSES["build_farm"].valid(farm.situation()))
        steps = farm.plan()
        tills = [step["target"] for step in steps if step["kind"] == "till"]
        sown = [step["item"] for step in steps if step["kind"] == "plant"]
        self.assertEqual(len(tills), 4)
        self.assertEqual(sown, ["carrot", "carrot", "seeds", "seeds"])
        self.assertTrue(all(abs(x - 8) <= 1 and abs(z) <= 1 and y == 0 for x, y, z in tills))
        self.assertEqual([(row["kind"], row["status"]) for row in structures(farm.db)], [("farm", "building")])
        self.assertTrue(reserved(farm.grid, tuple(tills[0])))

    def test_needs_a_home_and_two_things_to_plant(self):
        self.assertFalse(PURPOSES["build_farm"].valid(Farmstead({"seeds": 1}).situation()))
        homeless = Farmstead({"seeds": 5})
        homeless.db.execute("DELETE FROM memory_places")
        self.assertFalse(PURPOSES["build_farm"].valid(homeless.situation()))

    def test_an_old_farm_grows_into_the_square_instead_of_a_second_farm(self):
        old = ((3, 0, 3), (4, 0, 3))
        farm = Farmstead({"seeds": 9}, farmland=old)
        remember(farm.db, "farm", (3, 0, 3), 0.0)
        farm.plan()
        plots = structures(farm.db)[0]["data"]["cells"]
        self.assertIn([3, 0, 3, "plot", "farmland"], plots)
        self.assertIn([4, 0, 3, "plot", "farmland"], plots)

    def test_the_last_plot_tilled_finishes_the_farm(self):
        farm = Farmstead({"seeds": 20})
        context = farm.context()
        for _ in range(3):
            for step in farm.plan():
                if step["kind"] == "till":
                    farm.grid.put(*step["target"], "farmland")
                    note_building(farm.state, step, context, 2.0)
        self.assertEqual(structures(farm.db)[0]["status"], "done")
        self.assertEqual(context.events[-1][1:], ("built", "Pip laid out Pip's farm."))
        self.assertFalse(PURPOSES["build_farm"].valid(farm.situation()))

    def test_plots_that_turned_back_into_dirt_are_tilled_again(self):
        farm = Farmstead({"seeds": 20})
        for _ in range(3):
            for step in farm.plan():
                if step["kind"] == "till":
                    farm.grid.put(*step["target"], "farmland")
        cells = structures(farm.db)[0]["data"]["cells"]
        farm.grid.put(*cells[0][:3], "dirt")
        self.assertTrue(PURPOSES["build_farm"].valid(farm.situation()))
        self.assertIn({"kind": "till", "target": cells[0][:3]}, farm.plan())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_farmstead.py"`
Expected: `ImportError: cannot import name 'farmstead' from 'backend.survival'`.

- [ ] **Step 3: Write build_farm**

Create `backend/survival/farmstead.py`:

```python
"""build_farm: lay out a proper farm near home.

The generator (blueprints.design_farm) picks a 3x3 rectangle of plots on flat tillable ground,
4x4 with 12 things to plant and diligence 60, 5x5 with 20 and diligence 80. When Mimo already
keeps a farm (the remembered `farm` place, where it tilled first), the rectangle is laid over
that farm and as much of its farmland as it can hold, so the old farm grows into the new shape
instead of a second one starting. With no farm yet it goes beside the nearest shore within 16
blocks of home, where crops grow three times as fast, else near home. build_farm tills the plots still
missing and plants what Mimo carries on them, carrots first, 4 plots a batch; farming then tends
them. The plots are claimed (structures.reserved), so nothing digs them up and farm leaves them to
build_farm, which is offered again when some turned back into dirt and Mimo has seeds for them.
It is day work, offered once Mimo has a home and at least 2 things to plant, and scores in the
work band.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival.blueprints import Blueprint, design_farm
from backend.survival.building import site_center, structures_near
from backend.survival.farming import FARM_TRAVEL, PLANTABLE, SITE_SEARCH, next_seed, open_above, plant
from backend.survival.foraging import reach_steps
from backend.survival.memory import cell_of, nearest
from backend.survival.purposes import HOME_RANGE, Purpose, late_penalty, register
from backend.survival.senses import shores_near
from backend.survival.situation import Situation
from backend.survival.structures import blueprint_of, start, todo

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

PLOTS_PER_BATCH = 4
FARM_BATCHES = 6
OLD_FARM_REACH = 3.0  # farmland this close to the remembered farm is part of it


def plantables(s: Situation) -> int:
    return s.count(*PLANTABLE)


def farm_size(s: Situation) -> int:
    count, diligence = plantables(s), s.trait("diligence")
    if count >= 20 and diligence >= 80:
        return 5
    if count >= 12 and diligence >= 60:
        return 4
    return 3


def current_farm(s: Situation) -> dict | None:
    near = structures_near(s, "farm")
    return near[-1] if near else None


def farm_design(s: Situation) -> Blueprint | None:
    """A new farm's design, over the farm Mimo keeps, else beside the nearest shore within 16
    blocks of home, else at home (looked for once per Situation)."""
    def look() -> Blueprint | None:
        if nearest(s.places, s.here, ("home",), HOME_RANGE) is None:
            return None
        old = nearest(s.places, s.here, ("farm",), FARM_TRAVEL)
        if old is not None:
            x, y, z = cell_of(old)
            tilled = tuple(cell for cell, _ in s.grid.placed_cells(x, z, OLD_FARM_REACH, ("farmland",)) if cell[1] == y)
            return design_farm(s.grid, (x, y, z), farm_size(s), s.state["name"], tilled or ((x, y, z),))
        home = site_center(s)
        shores = shores_near(s.grid, s.seed, home, SITE_SEARCH)
        x, y, z = shores[0][0] if shores else home
        return design_farm(s.grid, (x, y - 1, z), farm_size(s), s.state["name"])
    return s.sensed("farm_design", look)


def plots_left(s: Situation, blueprint: Blueprint) -> list:
    return [planned for planned in todo(s.grid, blueprint, ("plot",)) if open_above(s, planned.cell)]


def farm_valid(s: Situation) -> bool:
    if s.night or plantables(s) < 2:
        return False
    farm = current_farm(s)
    if farm is None:
        return farm_design(s) is not None
    return bool(plots_left(s, blueprint_of(farm)))


def farm_facts(s: Situation) -> str:
    farm = current_farm(s)
    if farm is None:
        design = farm_design(s)
        size = design.style["size"][0] if design else 3
        return f"no laid-out farm yet; room for a {size}x{size} farm, carrying {plantables(s)} things to plant"
    return f"{farm['name']} has {len(plots_left(s, blueprint_of(farm)))} plots to till again"


def plan_build_farm(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= FARM_BATCHES or s.db is None:
        return []
    farm = current_farm(s)
    if farm is None:
        design = farm_design(s)
        if design is None:
            return []
        start(s.db, s.grid, design, s.at)
        blueprint = design
    else:
        blueprint = blueprint_of(farm)
    inventory, jobs = dict(s.inventory), []
    nearest_first = sorted(plots_left(s, blueprint),
                           key=lambda planned: (math.dist(planned.cell, s.here), planned.cell))
    for planned in nearest_first:
        seed = next_seed(inventory)
        if seed is None or len(jobs) >= PLOTS_PER_BATCH:
            break
        inventory[seed] -= 1
        ground = planned.cell
        top = (ground[0], ground[1] + 1, ground[2])
        jobs.append((top, [{"kind": "till", "target": list(ground)}, plant(top, seed)]))
    return reach_steps(s, jobs)


register(Purpose(
    "build_farm", "lay out a farm",
    "Lay out a neat farm of 3x3 to 5x5 plots near home, beside water if it can, over the farm it keeps.",
    valid=farm_valid, facts=farm_facts,
    score=lambda s: 45.0 + s.trait("diligence") / 10 - late_penalty(s), plan=plan_build_farm,
    thoughts=("Rows of crops, right by home.", "A proper farm would feed me all year.")))
```

- [ ] **Step 4: Let the brain offer it**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import lighting, storage  # noqa: F401  (M5's building purposes)
```

with:

```python
from backend.survival import farmstead, lighting, storage  # noqa: F401  (M5's building purposes)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_farmstead.py"`
Expected: `Ran 5 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 545 tests` … `OK` (5 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/farmstead.py backend/survival/brain.py backend/tests/test_survival_farmstead.py
git commit -m "feat: lay out a square farm near home, over the farm Mimo keeps" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 10: Catching up one transaction at a time

**Files:**
- Modify: `backend/survival/tick.py`, `backend/workers/mimo_worker.py`
- Test: `backend/tests/test_survival_tick_actions.py`, `backend/tests/test_survival_worker.py`

**Interfaces:**
- Consumes: `tick.advance_world`, `MAX_STEP_SECONDS`; `choosing.Chooser`, `InlineExecutor`.
- Produces:
  - `tick_life(registry, timestamp=None, scale=None, mind=RESTING, action_scale=None, between=None)`: a gap is advanced one 60-game-second step per `advance_world` call (one transaction, one ActionContext, 2 path searches each); `between(at)` runs after every step but the last while Mimo lives.
  - `run_once` passes a `between` that lets a rules-only Chooser (`env={}`, inline) answer pending choices, logging a crash once as `chooser`.

- [ ] **Step 1: Write the failing tests**

The M2 test that pinned one search budget to a whole catch-up is replaced: it is the behaviour this task changes (resolution 24).

In `backend/tests/test_survival_tick_actions.py`, replace:

```python
    def test_a_long_catch_up_shares_one_search_budget_for_the_whole_tick(self):
        """Controller ruling (Task 6 fix round 1): advance_world creates one ActionContext per
        tick_life call and every catch-up step's advance_actions call shares it, so a gap spanning
        several 60-game-second steps still spends at most MAX_SEARCHES_PER_TICK (2) route()
        searches for the whole tick, not that many per catch-up step. The deferred walks stay
        queued and the next tick call can pick them up with a fresh budget."""
```

with:

```python
    def test_a_long_catch_up_runs_one_transaction_per_step_each_with_its_own_search_budget(self):
        """M5 (replacing the M2 ruling of one budget for a whole catch-up): tick_life advances a
        gap one 60-game-second step per advance_world call, and each call is one transaction with
        its own ActionContext, so each step gets MAX_SEARCHES_PER_TICK (2) route() searches, the
        way a 60x run ticks. `between` hears about each step but the last."""
```

and replace:

```python
        with patch("backend.survival.steps.route", wraps=steps_module.route) as spy:
            state = tick_life(self.registry, BORN + 300, scale=1)  # 5 catch-up steps + 1 final call
        self.assertIsNone(state["died_at"])
        self.assertLessEqual(spy.call_count, 2)
        self.assertTrue(state["queue"] or (state["action"] and state["action"]["kind"] == "walk"))
        with patch("backend.survival.steps.route", wraps=steps_module.route) as spy_next:
            tick_life(self.registry, BORN + 301, scale=1)
        self.assertGreaterEqual(spy_next.call_count, 1)
```

with:

```python
        between = []
        with patch("backend.survival.steps.route", wraps=steps_module.route) as spy:
            state = tick_life(self.registry, BORN + 300, scale=1, between=between.append)  # 5 steps
        self.assertIsNone(state["died_at"])
        self.assertEqual(spy.call_count, 5)  # every walk started, one after another
        self.assertEqual(between, [BORN + 60, BORN + 120, BORN + 180, BORN + 240])
        self.assertEqual(state["last_tick_at"], BORN + 300)
        self.assertEqual(state["position"]["x"], x + 5)
```

In `backend/tests/test_survival_worker.py`, replace:

```python
from backend.survival.world import WorldMissing
from backend.workers.mimo_worker import run_once, should_log_data_error, tick_seconds
```

with:

```python
from backend.survival.world import SurvivalWorld, WorldMissing
from backend.workers.mimo_worker import WORKER_MIND, run_once, should_log_data_error, tick_seconds
```

and replace:

```python
    def test_tick_seconds_defaults_to_one(self):
```

with:

```python
    def test_after_a_long_outage_mimo_kept_choosing_and_eating_on_the_rules(self):
        life = hatch(self.registry, random.Random(8), timestamp=1000.0)
        asked = []
        chooser = Chooser(env={"TYPESAFE_API_KEY": "k"}, http=lambda *args: asked.append(args) or {},
                          executor=InlineExecutor(), rng=random.Random(8), scale=60.0)
        with patch.dict(os.environ, {"MIMO_TIME_SCALE": "60", "MIMO_ACTION_SCALE": "60"}):
            line = run_once(self.registry, None, timestamp=1000.0 + 2 * 60, mind=WORKER_MIND, chooser=chooser)
        self.assertIn(life["name"], line)
        events = SurvivalWorld(self.registry.world_path(life)).events(5000)
        kinds = [event["kind"] for event in events]
        self.assertGreater(kinds.count("purpose"), 5)
        self.assertIn("ate", kinds)
        self.assertLessEqual(len(asked), 1)  # at most the last ask goes to Jev; the catch-up ran on rules

    def test_tick_seconds_defaults_to_one(self):
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_tick_actions.py"`
Expected: `TypeError` … `unexpected keyword argument 'between'`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_worker.py"`
Expected: `FAIL: test_after_a_long_outage_mimo_kept_choosing_and_eating_on_the_rules` (one pending choice for two game days: a single `purpose` event).

- [ ] **Step 3: Catch up one transaction per step**

In `backend/survival/tick.py`, replace:

```python
The worker calls `tick_life` about once a second. A longer gap (a laptop that slept) is
caught up in steps of at most 60 game seconds, so a pet can starve while nobody watches.
```

with:

```python
The worker calls `tick_life` about once a second. A longer gap (a laptop that slept) is
caught up in steps of at most 60 game seconds, so a pet can starve while nobody watches. Each
step is its own transaction with its own path-search budget (`advance_world`), the way a fast
test run ticks, so a long catch-up is not one long write that locks the owner out, and a pet
catching up still walks, forages and gets home; between steps the worker lets its rules chooser
answer (`between`), so Mimo keeps choosing what to do.
```

In `backend/survival/tick.py`, replace the whole `tick_life` function with:

```python
def tick_life(registry: LifeRegistry, timestamp: float | None = None, scale: float | None = None,
              mind: Mind = RESTING, action_scale: float | None = None,
              between: Callable[[float], None] | None = None) -> dict | None:
    """Advance the active life and archive it if it died. Returns its state, or None if no pet is alive.

    A gap longer than one catch-up step (60 game seconds) is advanced one step per transaction,
    calling `between(at)` after each step but the last while Mimo lives."""
    life = registry.active_life()
    if life is None:
        return None
    timestamp = time.time() if timestamp is None else timestamp
    scale = time_scale() if scale is None else scale
    action_scale = action_scale_setting() if action_scale is None else action_scale
    world = SurvivalWorld(registry.world_path(life))
    at = world.state()["last_tick_at"]
    while True:
        at = min(timestamp, at + MAX_STEP_SECONDS / scale)
        state = advance_world(world, at, scale, mind, action_scale)
        if at >= timestamp or state["died_at"] is not None:
            break
        if between is not None:
            between(at)
    if state["died_at"] is not None:
        registry.mark_dead(life["id"], state["died_at"], state["cause"])
    return state
```

- [ ] **Step 4: Let the rules choose between the steps**

Model calls are slow and cost money: a catch-up must not ask Jev or Luna for every step. The worker's own Chooser answers once the tick is done, as before.

In `backend/workers/mimo_worker.py`, replace:

```python
pending purpose trigger outside the tick's transaction (backend.survival.choosing). The retired
```

with:

```python
pending purpose trigger outside the tick's transaction (backend.survival.choosing). A long
catch-up runs one transaction per 60 game seconds, and between them a rules-only chooser
answers, so a pet that slept through the laptop's night kept choosing without a burst of model
calls. The retired
```

and replace:

```python
from backend.survival.choosing import Chooser
```

with:

```python
from backend.survival.choosing import Chooser, InlineExecutor
```

and replace:

```python
    state = tick_life(registry, timestamp, mind=mind)
```

with:

```python
    between = None
    if chooser is not None:
        rules = Chooser(env={}, executor=InlineExecutor(), rng=chooser.rng, scale=chooser.scale)

        def between(at: float) -> None:
            try:
                rules.poll(registry, at)
            except Exception as error:
                log_once(logger, "chooser", error)

    state = tick_life(registry, timestamp, mind=mind, between=between)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_tick_actions.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_worker.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 546 tests` … `OK` (1 new; one test replaced).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/tick.py backend/workers/mimo_worker.py backend/tests/test_survival_tick_actions.py backend/tests/test_survival_worker.py
git commit -m "fix: catch up a long gap one transaction per game minute and let the rules choose in between" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 11: What the viewer and the models are told, and four days alone

**Files:**
- Modify: `backend/survival/building.py`, `backend/survival/pickers.py`, `backend/survival/snapshot.py`, `backend/survival/purposes.py`
- Test: `backend/tests/test_survival_pickers.py`, `backend/tests/test_survival_api.py`, `backend/tests/test_survival_days.py`

**Interfaces:**
- Consumes: Task 5's `building.shelter_facts`, `building_need`, `structures_near`; Task 4's `memory.structures`, `add_structure`; Task 2's `state["chests"]`.
- Produces:
  - `building.building_payload(s) -> dict`: `{"home": None | "found" | "built", "built": [{"kind", "name", "status"}], "shelter": <build_shelter's facts>, "blocks_short": int}`; `pickers.context_payload` adds it as `building`.
  - `snapshot.built_view(world) -> list[dict]`; `/api/mimo` adds `structures` (id, kind, name, status, x, y, z) and `chests`.
  - The purposes docstring names M5's modules and places their scores in the bands.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_pickers.py`, replace:

```python
        self.assertEqual(set(payload), {"name", "traits", "mood", "vitals", "phase", "day", "inventory",
                                        "known_places", "recent_events", "trigger"})
```

with:

```python
        self.assertEqual(set(payload), {"name", "traits", "mood", "vitals", "phase", "day", "inventory",
                                        "known_places", "recent_events", "trigger", "building"})
        self.assertEqual(payload["building"], {"home": "found", "built": [], "blocks_short": 0,
                                               "shelter": "no shelter of its own yet; a small shelter would need 38 "
                                                          "blocks, carrying 0 (short 38)"})
```

In `backend/tests/test_survival_api.py`, replace:

```python
from backend.survival.registry import LifeRegistry
```

with:

```python
from backend.survival.memory import add_structure
from backend.survival.registry import LifeRegistry
```

and replace:

```python
        self.assertEqual(state["decays"], [])
        self.assertNotIn("plans", state)
```

with:

```python
        self.assertEqual(state["decays"], [])
        self.assertEqual((state["structures"], state["chests"]), ([], {}))
        self.assertNotIn("plans", state)
```

and replace:

```python
    def test_only_leaves_that_decayed_in_the_last_ten_seconds_are_streamed(self):
```

with:

```python
    def test_what_mimo_built_and_its_chests_are_streamed(self):
        hatch_egg()
        world = self.active_world()
        with world.transaction() as db:
            add_structure(db, "shelter", "Pip's Snug Cottage", (5, 6, 7), 10.0, {}, [((5, 6, 7), "passage", "air")])
            state = read_state(db)
            state["chests"] = {"6,6,8": {"dirt": 9}}
            write_state(db, state)
        state = get_mimo()
        self.assertEqual(state["structures"], [{"id": 1, "kind": "shelter", "name": "Pip's Snug Cottage",
                                                "status": "building", "x": 5, "y": 6, "z": 7}])
        self.assertEqual(state["chests"], {"6,6,8": {"dirt": 9}})

    def test_only_leaves_that_decayed_in_the_last_ten_seconds_are_streamed(self):
```

The days test runs the real brain for four game days at 60× on seed 8 (about 3 s) and checks the whole story: a shelter built before the second night falls, home moved into it, a notable `built` event, at least two nights asleep in its bed, a torch alight on some night and something stored in a chest.

In `backend/tests/test_survival_days.py`, replace:

```python
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import notable
from backend.survival.tick import tick_life
```

with:

```python
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.grid import world_grid
from backend.survival.hatch import hatch
from backend.survival.memory import places, structures
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import notable
from backend.survival.structures import blueprint_of
from backend.survival.tick import tick_life
```

and replace:

```python
        self.assertNotIn("ate", [event["kind"] for event in notable(events)])
```

with:

```python
        self.assertNotIn("ate", [event["kind"] for event in notable(events)])

    def test_left_alone_mimo_builds_a_home_before_its_second_night_and_lives_in_it(self):
        chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(8), scale=SCALE)
        in_bed, lit = set(), set()
        for second in range(1, 4 * 60 + 1):
            state = tick_life(self.registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            self.assertIsNone(state["died_at"], state["cause"])
            chooser.poll(self.registry, BORN + second)
            if second % 60 == 50:  # deep in the night
                night = second // 60 + 1
                action = state["action"] or {}
                if action.get("kind") == "sleep" and action.get("bed"):
                    in_bed.add(night)
                with self.world.connect() as db:
                    grid = world_grid(db, state["world_seed"])
                    for shelter in structures(db, ("shelter",)):
                        if any(grid.material(*cell.cell) == "torch" for cell in blueprint_of(shelter).parts("torch")):
                            lit.add(night)
        built = [event for event in self.world.events(5000) if event["kind"] == "built" and "moved in" in event["text"]]
        self.assertEqual(len(built), 1)
        self.assertLess(built[0]["at"], BORN + 60 + 40)  # before the second night falls
        self.assertIn("built", [event["kind"] for event in notable(self.world.events(5000))])
        with self.world.connect() as db:
            home = places(db, ("home",))[0]
            shelter = blueprint_of(structures(db, ("shelter",))[0])
        self.assertEqual((home["note"], (home["x"], home["y"], home["z"])), ("built", shelter.anchor))
        self.assertGreaterEqual(len(in_bed), 2)
        self.assertTrue(lit)
        self.assertTrue(any(state.get("chests", {}).values()))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_pickers.py"`
Expected: `FAIL: test_the_model_payload_carries_needs_traits_places_and_events` (no `building` key).

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_api.py"`
Expected: `KeyError: 'structures'`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `OK`: the four-day story already holds after Tasks 5–9; this test keeps it.

- [ ] **Step 3: Tell the models what Mimo built and could build**

In `backend/survival/building.py`, replace:

```python
        if kind == "place" and step.get("block") == "torch":
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + TORCH_MOOD)
```

with:

```python
        if kind == "place" and step.get("block") == "torch":
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + TORCH_MOOD)


def building_payload(s: Situation) -> dict:
    """What a model is told about building: home, what Mimo built and what it could build now."""
    home = nearest(s.places, s.here, ("home",), HOME_RANGE)
    built = [{"kind": found["kind"], "name": found["name"], "status": found["status"]}
             for found in structures_near(s, "shelter") + structures_near(s, "farm")]
    return {"home": None if home is None else (home["note"] or "found"), "built": built,
            "shelter": shelter_facts(s), "blocks_short": building_need(s)}
```

In `backend/survival/pickers.py`, replace:

```python
from each purpose's templates. `context_payload(s, events)` is what Jev and Luna see: name,
traits, mood, vitals, phase, day, inventory, known places, the last 8 events and the trigger.
```

with:

```python
from each purpose's templates. `context_payload(s, events)` is what Jev and Luna see: name,
traits, mood, vitals, phase, day, inventory, known places, the last 8 events, the trigger and
what Mimo built or could build (M5).
```

and replace:

```python
from backend.survival.memory import cell_of
```

with:

```python
from backend.survival.building import building_payload
from backend.survival.memory import cell_of
```

and replace:

```python
        "trigger": list(pending["reasons"]) if pending else [],
    }
```

with:

```python
        "trigger": list(pending["reasons"]) if pending else [],
        # M5: home, what Mimo built and what it could build now, with the blocks it is short of.
        "building": building_payload(s),
    }
```

- [ ] **Step 4: Stream what Mimo built and its chests**

In `backend/survival/snapshot.py`, replace:

```python
import math

from backend.services.crafting import RECIPES
```

with:

```python
import math
import sqlite3

from backend.services.crafting import RECIPES
```

and replace:

```python
from backend.survival.clock import clock_at
```

with:

```python
from backend.survival.clock import clock_at
from backend.survival.memory import structures
```

and replace:

```python
def survival_view(world: SurvivalWorld, now: float, scale: float) -> dict:
```

with:

```python
def built_view(world: SurvivalWorld) -> list[dict]:
    """What Mimo built, oldest first: kind, name, status and anchor. A world from before M5 that
    is only read (an archive) has no structures table yet, and so built nothing."""
    try:
        with world.connect() as db:
            found = structures(db)
    except sqlite3.OperationalError:
        return []
    return [{key: structure[key] for key in ("id", "kind", "name", "status", "x", "y", "z")} for structure in found]


def survival_view(world: SurvivalWorld, now: float, scale: float) -> dict:
```

and replace:

```python
        **brain_view(state.get("brain")),
```

with:

```python
        # M5: what Mimo built, and what its chests hold ({"x,y,z": {item: count}}).
        "structures": built_view(world),
        "chests": state.get("chests", {}),
        **brain_view(state.get("brain")),
```

- [ ] **Step 5: Document M5's purposes and their scores**

In `backend/survival/purposes.py`, replace:

```python
backend.survival.brain imports them all. M5 registers build_* and light_up the same way.
```

with:

```python
M5's backend.survival.building registers build_shelter, backend.survival.storage build_storage
and drop_items, backend.survival.lighting light_up and backend.survival.farmstead build_farm.
backend.survival.brain imports them all.
```

and replace:

```python
  late but never below 0.
```

with:

```python
  late but never below 0.
- M5's building purposes sit in the same bands. build_shelter 60-80 while Mimo has no shelter of
  its own (70 and up from the afternoon on), 75 to repair one and 45-55 to furnish it; light_up
  72 in the evening at home, so the torches go up before sleep; build_storage 50-70, rising as
  Mimo's arms fill (55 to take food out); drop_items 30-78, from leisure into needs as the arms
  fill; build_farm 45-55, minus late.
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_pickers.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_api.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 548 tests` … `OK` (2 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 2 tests` … `OK` (about 90 s: seeds 3, 11, 5 and 21 over two game days, both pickers).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/building.py backend/survival/pickers.py backend/survival/snapshot.py backend/survival/purposes.py backend/tests/test_survival_pickers.py backend/tests/test_survival_api.py backend/tests/test_survival_days.py
git commit -m "feat: stream structures and chests, tell the models what Mimo could build and check four days alone" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 12: Viewer: building words, the home line and the chest

**Files:**
- Modify: `frontend/src/survival/types.ts`, `frontend/src/survival/hud.ts`, `frontend/src/survival/animation.ts`, `frontend/src/survival/SurvivalHud.tsx`, `frontend/src/survival/CraftingPanel.tsx`, `frontend/src/survival/SurvivalWorld.tsx`
- Test: `frontend/src/survival/hud.test.ts`, `frontend/src/survival/animation.test.ts`

**Interfaces:**
- Consumes: Task 11's `/api/mimo` fields `structures` and `chests`; Task 2's step kinds and statuses.
- Produces:
  - `types.ts`: `ActionKind` adds `'store' | 'take' | 'drop'`; `interface Built extends Point { id; kind: 'shelter' | 'farm'; name; status: 'building' | 'done' }`; `type Chests = Record<string, Record<string, number>>`; `SurvivalState.structures: Built[]` and `SurvivalState.chests: Chests`.
  - `hud.ts`: words for the new steps and purposes; `homeText(structures: Built[]): string | null`; `chestText(chests: Chests): string | null`.
  - The HUD shows the home line under the purpose; `CraftingPanel` takes `chests` and lists what the chest holds.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/survival/hud.test.ts`, replace:

```ts
import {
  actionText, careLabel, causeText, clockTime, dayLabel, lifeLine, purposeText, statusText, thingName, vitalBars,
  workerOnline,
} from './hud'
```

with:

```ts
import {
  actionText, careLabel, causeText, chestText, clockTime, dayLabel, homeText, lifeLine, purposeText, statusText, thingName,
  vitalBars, workerOnline,
} from './hud'
```

and replace:

```ts
    expect(purposeText({ purpose: 'build_shelter', reflex: null, choosing: false })).toBe('Build shelter')
```

with:

```ts
    expect(purposeText({ purpose: 'build_shelter', reflex: null, choosing: false })).toBe('Building a shelter')
    expect(purposeText({ purpose: 'light_up', reflex: null, choosing: false })).toBe('Lighting torches')
    expect(purposeText({ purpose: 'mend_fences', reflex: null, choosing: false })).toBe('Mend fences')
```

and replace:

```ts
    expect(purposeText({ purpose: null, reflex: null, choosing: false })).toBe('Taking it easy')
  })
})
```

with:

```ts
    expect(purposeText({ purpose: null, reflex: null, choosing: false })).toBe('Taking it easy')
  })
})

describe('building', () => {
  const hut = { id: 1, kind: 'shelter' as const, name: "Pip's Snug Cottage", status: 'building' as const, x: 1, y: 2, z: 3 }

  it('names the chest and hand work', () => {
    expect(actionText({ kind: 'store', started_at: 0, ends_at: 0.3, item: 'dirt' }, 'storing')).toBe('Putting away dirt')
    expect(actionText({ kind: 'take', started_at: 0, ends_at: 0.3, item: 'bread' }, 'taking')).toBe('Taking out bread')
    expect(actionText({ kind: 'drop', started_at: 0, ends_at: 0.3, item: 'red_mushroom' }, 'dropping'))
      .toBe('Dropping red mushroom')
    expect(actionText({ kind: 'place', started_at: 0, ends_at: 0.3, block: 'cobblestone' }, 'building'))
      .toBe('Placing cobblestone')
  })

  it('says where home is: the shelter Mimo built, or the one it is building', () => {
    expect(homeText([])).toBeNull()
    expect(homeText([hut])).toBe("Building Pip's Snug Cottage")
    expect(homeText([{ ...hut, status: 'done' }, { ...hut, id: 2, kind: 'farm', name: "Pip's farm" }]))
      .toBe("Home: Pip's Snug Cottage")
  })

  it('sums up what the chests hold, most first', () => {
    expect(chestText({})).toBeNull()
    expect(chestText({ '1,2,3': { dirt: 40, red_mushroom: 2 }, '5,2,3': { dirt: 2, gravel: 5, sand: 0 } }))
      .toBe('42 dirt, 5 gravel, 2 red mushroom')
  })
})
```

In `frontend/src/survival/animation.test.ts`, replace:

```ts
    expect(moveFor({ kind: 'cook', started_at: 0, ends_at: 5 }, 1)).toBe('work')
```

with:

```ts
    expect(moveFor({ kind: 'cook', started_at: 0, ends_at: 5 }, 1)).toBe('work')
    expect(moveFor({ kind: 'store', started_at: 0, ends_at: 0.3 }, 0.1)).toBe('place')
    expect(moveFor({ kind: 'drop', started_at: 0, ends_at: 0.3 }, 0.1)).toBe('place')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/hud.test.ts src/survival/animation.test.ts`
Expected: the new tests fail (for example `expected 'Build shelter' to be 'Building a shelter'`, and `homeText is not a function`).

- [ ] **Step 3: The new kinds and fields**

In `frontend/src/survival/types.ts`, replace:

```ts
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook'
```

with:

```ts
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook' | 'store' | 'take' | 'drop'
```

and replace:

```ts
export type PickerName = 'jev' | 'luna' | 'utility'
```

with:

```ts
/** Something Mimo built or is building (backend/survival/memory.py structures), by its anchor. */
export interface Built extends Point {
  id: number
  kind: 'shelter' | 'farm'
  name: string
  status: 'building' | 'done'
}

/** What each chest holds, keyed "x,y,z". */
export type Chests = Record<string, Record<string, number>>

export type PickerName = 'jev' | 'luna' | 'utility'
```

and replace:

```ts
  /** Leaves that decayed lately, newest last, for a puff as each goes. */
  decays: LeafDecay[]
```

with:

```ts
  /** Leaves that decayed lately, newest last, for a puff as each goes. */
  decays: LeafDecay[]
  /** What Mimo built, oldest first (M5). */
  structures: Built[]
  /** What its chests hold (M5). */
  chests: Chests
```

- [ ] **Step 4: Words, the home line, the chest and poses**

In `frontend/src/survival/hud.ts`, replace:

```ts
import type { ActionKind, CareKind, ClockPhase, LifeRow, MimoAction, SurvivalState, VitalName, Vitals } from './types'
```

with:

```ts
import type { ActionKind, Built, CareKind, Chests, ClockPhase, LifeRow, MimoAction, SurvivalState, VitalName, Vitals } from './types'
```

and replace:

```ts
  till: 'Tilling', plant: 'Planting', fish: 'Fishing', cook: 'Cooking',
}
```

with:

```ts
  till: 'Tilling', plant: 'Planting', fish: 'Fishing', cook: 'Cooking', store: 'Putting away', take: 'Taking out',
  drop: 'Dropping',
}
```

and replace:

```ts
  fish: 'Fishing', farm: 'Tending the farm', cook: 'Cooking a meal',
}
```

with:

```ts
  fish: 'Fishing', farm: 'Tending the farm', cook: 'Cooking a meal', build_shelter: 'Building a shelter',
  build_farm: 'Laying out a farm', build_storage: 'Putting things away', drop_items: 'Dropping what it cannot use',
  light_up: 'Lighting torches',
}
```

and replace:

```ts
export function careLabel(kind: CareKind, remaining: number): string {
```

with:

```ts
/** Mimo's home in a few words: the shelter it built (or is building), or null before it starts one. */
export function homeText(structures: Built[]): string | null {
  const shelter = [...structures].reverse().find((built) => built.kind === 'shelter')
  if (!shelter) return null
  return shelter.status === 'done' ? `Home: ${shelter.name}` : `Building ${shelter.name}`
}

/** What Mimo keeps in its chests, most first, like "40 dirt, 5 gravel"; null when they are empty. */
export function chestText(chests: Chests): string | null {
  const totals = new Map<string, number>()
  for (const chest of Object.values(chests)) {
    for (const [item, count] of Object.entries(chest)) totals.set(item, (totals.get(item) ?? 0) + count)
  }
  const items = [...totals].filter(([, count]) => count > 0).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  return items.length ? items.map(([item, count]) => `${count} ${item.replaceAll('_', ' ')}`).join(', ') : null
}

export function careLabel(kind: CareKind, remaining: number): string {
```

In `frontend/src/survival/animation.ts`, replace:

```ts
  fish: 'fish', cook: 'work',
}
```

with:

```ts
  fish: 'fish', cook: 'work', store: 'place', take: 'place', drop: 'place',
}
```

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```tsx
import { actionText, careLabel, clockTime, dayLabel, purposeText, vitalBars, type VitalLevel } from './hud'
```

with:

```tsx
import { actionText, careLabel, clockTime, dayLabel, homeText, purposeText, vitalBars, type VitalLevel } from './hud'
```

and replace:

```tsx
  const careKinds: CareKind[] = ['snack', 'bandage']
```

with:

```tsx
  const careKinds: CareKind[] = ['snack', 'bandage']
  const home = homeText(state.structures)
```

and replace:

```tsx
          <p className="mt-2 text-sm font-medium leading-5 text-[#315e58]">{purposeText(state)}</p>
```

with:

```tsx
          <p className="mt-2 text-sm font-medium leading-5 text-[#315e58]">{purposeText(state)}</p>
          {home && <p className="mt-0.5 truncate text-xs text-[#54726e]">{home}</p>}
```

In `frontend/src/survival/CraftingPanel.tsx`, replace:

```tsx
import { AIR, BLOCKS } from '../engine/blocks'
import type { Recipe } from './types'
```

with:

```tsx
import { AIR, BLOCKS } from '../engine/blocks'
import { chestText } from './hud'
import type { Chests, Recipe } from './types'
```

and replace:

```tsx
export default function CraftingPanel({ name, inventory, recipes, stations, worldSeed, message, onAction, onClose }: {
  name: string
  inventory: Record<string, number>
```

with:

```tsx
export default function CraftingPanel({ name, inventory, chests, recipes, stations, worldSeed, message, onAction, onClose }: {
  name: string
  inventory: Record<string, number>
  /** What Mimo keeps in its chests at home. */
  chests: Chests
```

and replace:

```tsx
  const owned = Object.entries(inventory).filter(([, amount]) => amount > 0)
```

with:

```tsx
  const owned = Object.entries(inventory).filter(([, amount]) => amount > 0)
  const stored = chestText(chests)
```

and replace:

```tsx
            <span key={item} className="rounded-lg bg-[#e1eee7] px-3 py-1.5">{item.replaceAll('_', ' ')} ×{amount}</span>)}
        </div>
```

with:

```tsx
            <span key={item} className="rounded-lg bg-[#e1eee7] px-3 py-1.5">{item.replaceAll('_', ' ')} ×{amount}</span>)}
        </div>
        {stored && <p className="mt-2 text-xs text-[#54726e]">In {name}'s chest at home: {stored}</p>}
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
        <CraftingPanel name={state.life.name} inventory={state.inventory} recipes={state.recipes} stations={stations}
```

with:

```tsx
        <CraftingPanel name={state.life.name} inventory={state.inventory} chests={state.chests} recipes={state.recipes} stations={stations}
```

- [ ] **Step 5: Test, build and lint**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  178 passed (178)` (3 new), the build succeeds, eslint prints nothing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/survival/types.ts frontend/src/survival/hud.ts frontend/src/survival/hud.test.ts frontend/src/survival/animation.ts frontend/src/survival/animation.test.ts frontend/src/survival/SurvivalHud.tsx frontend/src/survival/CraftingPanel.tsx frontend/src/survival/SurvivalWorld.tsx
git commit -m "feat: show building work, home and the chest's contents in the viewer" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 13: Viewer: see Mimo inside and behind what it built

**Files:**
- Modify: `frontend/src/survival/cutaway.ts`, `frontend/src/survival/WorldCanvas.tsx`, `frontend/src/engine/BlockWorld.tsx`
- Test: `frontend/src/survival/cutaway.test.ts`

**Interfaces:**
- Consumes: `cutaway.underground`, `NOT_COVER`, `CUT_CLEARANCE`, `CUTAWAY_RADIUS`; the terrain cutaway uniform (M3).
- Produces: `cutaway.HIDE_REACH = 6`; `hidden(store, pose, camera): boolean`; `cutawayFor(store, pose, camera?)` also cuts when `hidden`; `BlockWorld`'s `cutaway` prop becomes `(camera: THREE.Vector3) => Cutaway | null`, called with the camera's position every frame.

The cut discards terrain above 1.5 blocks over Mimo's feet near Mimo and in the cone toward the camera. Inside a shelter the roof covers Mimo, so `underground` already cuts it away (a dirt or cobblestone roof counts, a test pins it). What M3's rule missed is Mimo just outside or at its door with the house between it and the camera: nothing is over its head, so nothing was cut and the walls hid it. `hidden` walks the line from Mimo's middle toward the camera for 6 blocks, and any cover that reaches above the cut height turns the cut on (lower walls stay: the cut would not remove them).

- [ ] **Step 1: Write the failing tests**

In `frontend/src/survival/cutaway.test.ts`, replace:

```ts
import { CUTAWAY_RADIUS, cutawayFor, cutsAway, underground } from './cutaway'
```

with:

```ts
import { CUTAWAY_RADIUS, cutawayFor, cutsAway, hidden, underground } from './cutaway'
```

and replace:

```ts
describe('cutawayFor', () => {
```

with:

```ts
describe('a shelter Mimo built', () => {
  /** A wall at x = 3 in front of Mimo (at 0, 1, 0), `height` blocks tall, made of `block`. */
  const wall = (height: number, block = 'cobblestone') =>
    ground(Object.fromEntries(Array.from({ length: height }, (_, i) => [`3,${1 + i},0`, block])))
  const camera = { x: 18, y: 14, z: 0.5 }

  it('counts a dirt or cobblestone roof as cover', () => {
    expect(underground(ground({ '0,3,0': 'dirt' }), { x: 0, y: 1, z: 0 })).toBe(true)
    expect(underground(ground({ '0,4,0': 'cobblestone' }), { x: 0, y: 1, z: 0 })).toBe(true)
  })

  it('is hidden by a wall or roof reaching above the cut between it and the camera', () => {
    expect(hidden(wall(3), { x: 0, y: 1, z: 0 }, camera)).toBe(true)
    expect(hidden(wall(2), { x: 0, y: 1, z: 0 }, camera)).toBe(false)  // the cut would leave it anyway
    expect(hidden(wall(3, 'leaves'), { x: 0, y: 1, z: 0 }, camera)).toBe(false)
    expect(hidden(wall(3), { x: 0, y: 1, z: 0 }, { x: -18, y: 14, z: 0.5 })).toBe(false)  // seen from the other side
  })

  it('cuts the walls away when they hide the pet from the camera, and not in the open', () => {
    expect(cutawayFor(wall(3), { x: 0, y: 1, z: 0 }, camera)).toEqual({ x: 0.5, y: 2.5, z: 0.5, radius: CUTAWAY_RADIUS })
    expect(cutawayFor(wall(3), { x: 0, y: 1, z: 0 })).toBeNull()
    expect(cutawayFor(ground(), { x: 0, y: 1, z: 0 }, camera)).toBeNull()
  })
})

describe('cutawayFor', () => {
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/cutaway.test.ts`
Expected: the new tests fail (`hidden is not a function`).

- [ ] **Step 3: Cut when a wall or roof hides the pet**

In `frontend/src/survival/cutaway.ts`, replace:

```ts
/**
 * Seeing Mimo underground. When rock (or a roof) covers Mimo, the terrain materials discard
 * their fragments above Mimo's head (the cut height, 1.5 blocks over its feet) in two places:
 * within CUTAWAY_RADIUS blocks of Mimo horizontally, and inside a cone from the camera to Mimo
 * that is CUTAWAY_RADIUS wide at Mimo, so the follow camera (about 27 degrees up) sees down a
 * tunnel ten blocks deep. One uniform carries the cut; it changes every frame without remeshing.
```

with:

```ts
/**
 * Seeing Mimo underground or at home. When rock or a roof covers Mimo, or a wall or roof it built
 * stands between it and the camera, the terrain materials discard their fragments above Mimo's
 * head (the cut height, 1.5 blocks over its feet) in two places: within CUTAWAY_RADIUS blocks of
 * Mimo horizontally, and inside a cone from the camera to Mimo that is CUTAWAY_RADIUS wide at
 * Mimo, so the follow camera (about 27 degrees up) sees down a tunnel ten blocks deep, and into a
 * shelter over its walls. One uniform carries the cut; it changes every frame without remeshing.
```

and replace:

```ts
/** How far up the column over Mimo's head to look for cover. */
export const COVER_SEARCH = 12
```

with:

```ts
/** How far up the column over Mimo's head to look for cover. */
export const COVER_SEARCH = 12
/** How far from Mimo, toward the camera, a wall or roof that hides it is looked for. */
export const HIDE_REACH = 6
const HIDE_STEP = 0.5
```

and replace:

```ts
/** Whether a solid block (not a tree) covers the cell within COVER_SEARCH blocks over Mimo's head. */
export function underground(store: BlockReader, cell: Point): boolean {
  for (let dy = 1; dy <= COVER_SEARCH; dy++) {
    const id = store.getBlock(cell.x, cell.y + dy, cell.z)
    if (id === AIR) continue
    const block = blockDef(id)
    if (block.solid && !NOT_COVER.has(block.name)) return true
  }
  return false
}

/** The cut for Mimo drawn at `pose` (cell coordinates, fractional while it moves), or null in the open. */
export function cutawayFor(store: BlockReader, pose: Point): Cutaway | null {
  const cell = { x: Math.round(pose.x), y: Math.round(pose.y), z: Math.round(pose.z) }
  if (!underground(store, cell)) return null
```

with:

```ts
function isCover(store: BlockReader, x: number, y: number, z: number): boolean {
  const id = store.getBlock(x, y, z)
  if (id === AIR) return false
  const block = blockDef(id)
  return block.solid && !NOT_COVER.has(block.name)
}

/** Whether a solid block (not a tree) covers the cell within COVER_SEARCH blocks over Mimo's head. */
export function underground(store: BlockReader, cell: Point): boolean {
  for (let dy = 1; dy <= COVER_SEARCH; dy++) {
    if (isCover(store, cell.x, cell.y + dy, cell.z)) return true
  }
  return false
}

/**
 * Whether cover the cut can remove hides Mimo, drawn at `pose`, from `camera`: a solid block (not a
 * tree or fixture) reaching above the cut height on the line from Mimo's middle toward the camera,
 * within HIDE_REACH blocks. A wall lower than that stays, since the cut would not take it away.
 */
export function hidden(store: BlockReader, pose: Point, camera: Point): boolean {
  const from = { x: pose.x + 0.5, y: pose.y + 0.5, z: pose.z + 0.5 }
  const toward = { x: camera.x - from.x, y: camera.y - from.y, z: camera.z - from.z }
  const length = Math.hypot(toward.x, toward.y, toward.z)
  if (length === 0) return false
  const lowest = Math.floor(pose.y + CUT_CLEARANCE)
  const home = { x: Math.round(pose.x), y: Math.round(pose.y), z: Math.round(pose.z) }
  for (let along = HIDE_STEP; along <= Math.min(HIDE_REACH, length); along += HIDE_STEP) {
    const x = Math.floor(from.x + (toward.x * along) / length)
    const y = Math.floor(from.y + (toward.y * along) / length)
    const z = Math.floor(from.z + (toward.z * along) / length)
    if (y < lowest || (x === home.x && y === home.y && z === home.z)) continue
    if (isCover(store, x, y, z)) return true
  }
  return false
}

/** The cut for Mimo drawn at `pose` (cell coordinates, fractional while it moves), or null in the
 * open. With the `camera` position, walls and roofs that hide Mimo from it count too. */
export function cutawayFor(store: BlockReader, pose: Point, camera?: Point): Cutaway | null {
  const cell = { x: Math.round(pose.x), y: Math.round(pose.y), z: Math.round(pose.z) }
  if (!underground(store, cell) && !(camera && hidden(store, pose, camera))) return null
```

In `frontend/src/engine/BlockWorld.tsx`, replace:

```tsx
  /** Called every frame for the terrain to cut away over an underground pet (null: none). */
  cutaway?: () => Cutaway | null
```

with:

```tsx
  /** Called every frame, with the camera's position, for the terrain to cut away over an
   * underground or hidden pet (null: none). */
  cutaway?: (camera: THREE.Vector3) => Cutaway | null
```

and replace:

```tsx
  useFrame((_, delta) => {
    const current = renderer.current
    if (!current) return
    current.setDaylight(daylight ? daylight() : 1)
    current.setCutaway(cutaway ? cutaway() : null)
```

with:

```tsx
  useFrame(({ camera }, delta) => {
    const current = renderer.current
    if (!current) return
    current.setDaylight(daylight ? daylight() : 1)
    current.setCutaway(cutaway ? cutaway(camera.position) : null)
```

In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import type { FinishedAction, LeafDecay, MimoAction } from './types'
```

with:

```tsx
import type { FinishedAction, LeafDecay, MimoAction, Point } from './types'
```

and replace:

```tsx
 * When the pet is underground, the terrain over it is cut away (cutaway.ts).
```

with:

```tsx
 * When the pet is underground, or a wall or roof hides it, the terrain over it is cut away (cutaway.ts).
```

and replace:

```tsx
  // Underground, the terrain over the drawn pet is cut away so the camera can still see it.
  const cutawayAt = useCallback(() => cutawayFor(store, serverTime ? focusAt() : position),
    [store, serverTime, focusAt, position])
```

with:

```tsx
  // Underground, or hidden behind a wall or roof, the terrain over the drawn pet is cut away so the
  // camera can still see it.
  const cutawayAt = useCallback((camera: Point) => cutawayFor(store, serverTime ? focusAt() : position, camera),
    [store, serverTime, focusAt, position])
```

- [ ] **Step 4: Test, build and lint**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  181 passed (181)` (3 new), the build succeeds, eslint prints nothing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/survival/cutaway.ts frontend/src/survival/cutaway.test.ts frontend/src/survival/WorldCanvas.tsx frontend/src/engine/BlockWorld.tsx
git commit -m "feat: cut away the walls and roof that hide Mimo from the camera" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 14: Manual check at 60× and the README

This task is for the controller. It runs Docker against a scratch volume and a separately tagged image; the real `pets_mimo_data` volume is never mounted. At `MIMO_TIME_SCALE=60` a game day lasts 60 real seconds (40 s of day, 20 s of night) and `MIMO_ACTION_SCALE=60` makes the steps 60 times shorter, so a shelter goes up in a few real seconds. If a check fails, fix the code in the task that owns it, re-run that task's tests, and repeat the check. Stop any other server on ports 8011 and 3000 first.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 548 tests` … `OK`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 2 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  181 passed (181)`, the build succeeds, eslint prints nothing.

- [ ] **Step 2: Build a scratch image and start a scratch world at 60×**

```bash
docker build -f backend/Dockerfile -t mimo-m5-check .
docker volume create mimo_m5_check
docker run --rm -v mimo_m5_check:/data -e MIMO_DB_PATH=/data/mimo.sqlite3 mimo-m5-check \
  python -c "from backend.services.live_mimo import MimoStore; MimoStore(); print('scratch legacy world ready')"
docker run -d --name mimo-m5-api -p 127.0.0.1:8011:8000 -v mimo_m5_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 mimo-m5-check
docker run -d --name mimo-m5-worker -v mimo_m5_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 -e MIMO_ACTION_SCALE=60 \
  -e MIMO_TICK_SECONDS=1 mimo-m5-check python -m backend.workers.mimo_worker
```

Expected: `scratch legacy world ready`, then two container ids. No model key is passed, so the utility picker chooses.

After a few seconds, hatch the egg and note the time:

```bash
curl -s -X POST http://127.0.0.1:8011/api/lives/hatch | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['life']['id'], d['life']['name'])"
date
```

Expected: `2 <name>`.

- [ ] **Step 3: Keep a story snippet and two nudges ready**

Save these in your scratchpad directory (not in the repo). `story.sh` prints the building story, what Mimo built with its fittings, the chest, home and whether Mimo is sheltered:

```bash
docker exec -i mimo-m5-api python - <<'PY'
from backend.survival.carrying import stacks
from backend.survival.clock import clock_at
from backend.survival.grid import world_grid
from backend.survival.memory import places, structures
from backend.survival.registry import LifeRegistry
from backend.survival.structures import blueprint_of, todo
from backend.survival.tick import surroundings_at
from backend.survival.world import SurvivalWorld

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
state = world.state()
for event in reversed(world.events(400)):
    if event["kind"] in ("built", "purpose", "reflex", "plan", "trapped", "sleep", "death"):
        print(event["kind"], "|", event["text"])
clock = clock_at(state["born_at"], state["last_tick_at"], 60)
action = state.get("action") or {}
print("day", clock["day_number"], clock["phase"], "| vitals", {k: round(v) for k, v in state["vitals"].items()})
print("doing", action.get("kind"), "in bed" if action.get("bed") else "", "| stacks", stacks(state["inventory"]),
      "| chests", state.get("chests"))
with world.connect() as db:
    grid = world_grid(db, state["world_seed"])
    home = places(db, ("home",))
    print("home", [(p["x"], p["y"], p["z"], p["note"]) for p in home])
    for found in structures(db):
        design = blueprint_of(found)
        fittings = {planned.part + str(i): grid.material(*planned.cell)
                    for i, planned in enumerate(design.parts("bed", "chest", "campfire", "torch"))}
        print(found["kind"], found["name"], found["status"], "| left", len(todo(grid, design)), "|", design.style,
              "|", fittings)
    around = surroundings_at(db, state["world_seed"], state["position"])
    print("sheltered", around.sheltered, "| near a fire", around.near_fire)
PY
```

`blocks.sh` gives Mimo 30 cobblestone, 6 logs and 2 coal and asks for a choice (a manual nudge, for a spawn so poor in stone that no shelter is started by the end of day 2):

```bash
docker exec -i mimo-m5-api python - <<'PY'
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import mark_trigger
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    for item, count in (("cobblestone", 30), ("oak_log", 6), ("coal", 2)):
        state["inventory"][item] = state["inventory"].get(item, 0) + count
    mark_trigger(state, "nudge", state["last_tick_at"])
    write_state(db, state)
print("gave 30 cobblestone, 6 logs and 2 coal")
PY
```

`end.sh` takes all food away and leaves 2 health, so the life ends by starvation within a game hour (only for the last check):

```bash
docker exec -i mimo-m5-api python - <<'PY'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    state["inventory"] = {item: n for item, n in state["inventory"].items() if item not in (
        "berries", "brown_mushroom", "red_mushroom", "carrot", "bread", "raw_fish", "cooked_fish", "apple")}
    state["chests"] = {key: {} for key in state.get("chests", {})}
    state["vitals"].update(hunger=0.0, health=2.0)
    write_state(db, state)
print("no food left anywhere; health 2")
PY
```

Expected: the story snippet prints event lines, a `day` line and a `home` line; the nudges print their one line.

- [ ] **Step 4: Start the viewer against the scratch API**

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8011 npm run dev -- --port 3000 --strictPort
```

Open `http://localhost:3000/preview?debug` in the Browser pane.

- [ ] **Step 5: Check the API stream**

```bash
curl -s http://127.0.0.1:8011/api/mimo | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['purpose'], d['status'], d['structures'], d['chests'])"
```

Expected: a purpose, a status, a list for `structures` (empty until the first shelter is started) and a dict for `chests`.

- [ ] **Step 6: A shelter before the first or second night**

Run the story snippet every 20 seconds through the first two game days (2 real minutes). Confirm:

- `decided to build a shelter` appears on day 1 (if it has not by the end of day 2, run `blocks.sh` once and note it); the HUD reads `Building a shelter`, a home line `Building <name>'s … Cottage` (or `… Cabin`) appears under it, and the step line reads `Placing cobblestone` (or planks, dirt …). Walls rise around the pet two rows high, then the roof; the pet stays inside and walks out through the door gap.
- `built | <name> finished building <name>'s … and moved in.` appears before the second night falls; the `shelter` line reads `done | left 0`; `home` shows the anchor with note `built`; the HUD's home line turns into `Home: …`.
- When the pet is inside, the roof is cut away so the pet stays in sight; when it stands outside with the house between it and the camera, the walls above its head are cut away too.
- The notable list keeps the event: `curl -s http://127.0.0.1:8011/api/lives/2 | python3 -c "import json,sys; print([e['kind'] for e in json.load(sys.stdin)['notable_events']])"` shows `built`.

- [ ] **Step 7: Sleeping in its own bed, warm, with a campfire beside home**

On the first night after the shelter is done, and on later nights, run the story snippet between 45 and 55 seconds into a real minute (deep in the night). Confirm the `fittings` show `bed…: bed` and `campfire…: campfire` (the bed can come a day later, once Mimo has 6 planks to spare), `doing sleep in bed`, `sheltered True`, and `near a fire True` or a warmth of 75 or more in the vitals. In the viewer the pet lies on its bed inside, and the campfire glows outside beside the door.

- [ ] **Step 8: Torches at night and a chest with stored items**

Confirm that on some evening the HUD reads `Lighting torches`, the pet walks round the outside corners and back inside, and at night the `torch…` fittings read `torch`: four small glowing torches at the shelter's corners in the viewer. (A pet that has found no coal yet has no torches; it gets them once `mine_ore` brings coal, or after `blocks.sh`.) Confirm that once the pet carries 13 stacks or more, `decided to put things away` appears, a chest appears in the back corner, `chests` in the story (and `/api/mimo`) lists what it holds, and the Blocks & crafting panel shows `In <name>'s chest at home: …`. If the pet carried known red mushrooms or an old pickaxe, `decided to drop what it cannot use` appears too.

- [ ] **Step 9: A long outage**

Stop the worker for two real minutes (two game days at 60×) and start it again:

```bash
docker stop mimo-m5-worker && sleep 120 && docker start mimo-m5-worker
```

Within a few seconds of the start the HUD's day has jumped two days ahead. Confirm in the story snippet that `decided to …` events appeared during the gap (the rules chose between catch-up steps), that the pet ate during it (hunger is not 0) and that `docker logs mimo-m5-worker 2>&1 | grep -c "crashed"` stays small.

- [ ] **Step 10: Seven days on its own**

Leave the pet alone for at least 7 game days from the hatch (about 9 real minutes including the outage). Confirm: it is alive on day 8, it sleeps in its shelter every night (story snippet: `sheltered True` at night), the shelter stays `done | left 0` (or is repaired soon after if something broke it) and the worker log has no repeated crash lines.

- [ ] **Step 11: Check the phone layout**

Resize the Browser pane to the mobile preset and reload. Confirm the HUD shows the purpose line, the home line and the step line without overlapping the vitals. Reset the viewport to desktop afterwards.

- [ ] **Step 12: The end of a life keeps its home**

Run `end.sh`. Within a game hour the pet dies of starvation. Confirm the memorial lists `built` among its notable events, `View <name>'s world` opens the archived world with the shelter standing, read-only, and `Hatch a new egg` waits.

- [ ] **Step 13: Clean up the scratch run**

Stop the dev server (Ctrl+C), then remove only what this task created:

```bash
docker rm -f mimo-m5-api mimo-m5-worker
docker volume rm mimo_m5_check
docker image rm mimo-m5-check
```

- [ ] **Step 14: Describe building in the README**

In `README.md`, replace:

```markdown
A roof within 4 blocks overhead with walls on 3 sides, or a campfire or furnace within 4 blocks, keeps the pet warm; natural overhangs and caves count.
```

with:

```markdown
A roof within 4 blocks overhead with walls on 3 sides, or a campfire or furnace within 4 blocks, keeps the pet warm; natural overhangs and caves count, and so does the shelter the pet builds (see Building).
```

and replace:

```markdown
fishing 20 to 60 s and cooking 5 s. Sleep lasts until Mimo is rested and it is day.
```

with:

```markdown
fishing 20 to 60 s, cooking 5 s, and putting items into a chest, taking them out or dropping them 0.3 s. Sleep lasts until Mimo is rested and it is day; lying on a bed, Mimo sleeps in it and rests almost twice as fast.
```

and replace:

```markdown
`MIMO_ACTION_SCALE` shortens the steps for a fast manual run.
```

with:

```markdown
`MIMO_ACTION_SCALE` shortens the steps for a fast manual run.
- A long gap (a laptop that slept) is caught up one 60-game-second step at a time, each its own short transaction with its own path-search budget, so the pet still walks, forages and gets home. Between the steps the worker lets its rules chooser answer, so the pet keeps choosing what to do without a burst of model calls.
```

and replace:

```markdown
and collapse (energy below 10: sleep on the spot).
```

with:

```markdown
and collapse (energy below 10: sleep on the spot, or in a bed within 8 blocks). Head home leaves the pet be while it builds its shelter or lights torches at home.
```

and replace:

```markdown
and gather wood plants the saplings Mimo carries; building purposes arrive with the next milestone.
```

with:

```markdown
and gather wood plants the saplings Mimo carries. Build a shelter, put things away, drop what it cannot use, light torches and lay out a farm make a home (see Building).
```

and replace:

```markdown
Home is the first sheltered spot Mimo finds, often its own mine staircase.
```

with:

```markdown
Home is the first sheltered spot Mimo finds, often its own mine staircase, until Mimo builds a shelter: then home moves in, and a home Mimo built is never forgotten.
```

and replace:

```markdown
When Mimo is underground, the viewer cuts the terrain away above it so it stays in sight.
```

with:

```markdown
When Mimo is underground, or a wall or roof hides it from the camera, the viewer cuts the terrain away above it so it stays in sight.
```

and replace:

```markdown
## Current world rules
```

with:

```markdown
## Building

- **Shelter.** With no shelter of its own within 128 blocks, Mimo designs one near home and builds it block by block once it carries half the blocks it needs: a room 3 wide, 3 deep and 2 high (4 by 3 or 5 by 4 when creativity and the blocks it carries allow), walls and a roof over all of it, a door gap and a way in that stay open. Every inside cell passes the server's shelter check. Mimo builds from inside, so it needs no scaffolding.
- **The generator** (`backend/survival/blueprints.py`) is seeded and needs no world to test. It picks flat natural ground near home, never farmland, a sapling, water, a dug stair or anything built, and never beside a dug column, so a staircase keeps its way out. Traits and the world seed choose the style: a flat, gable or dome roof (creativity makes the fancier ones likelier), cobblestone or plank walls (thrift prefers cobblestone), windows and the door side. Walls and roof take any building block when the one they prefer runs short: cobblestone and planks first, other stone and loose blocks next, dirt last, and logs become planks. When the blocks run out, building pauses and gather wood and gather stone aim for what is missing.
- **Home.** When the last floor, wall or roof block is down, home moves in (a notable "built" event) and Mimo is pleased. It then furnishes the shelter with a bed (6 planks), which rests it faster, and a campfire (2 logs and 3 sticks) beside the door, which keeps it warm. A damaged shelter is repaired, and a blocked door or way in is cleared.
- **Carrying and storage.** Mimo carries at most 16 stacks of 32; a tool is a stack of its own. What a step brings in beyond that stays behind. Put things away places a chest (8 planks) in the shelter's back corner once Mimo's arms fill up. It stores loose blocks, spare materials and more food than a day's worth, and it takes food back out when Mimo carries little. Drop what it cannot use leaves known poison, replaced tools and flowers behind. Ripe crops wait in the field while Mimo carries a day's worth of food.
- **Torches.** In the evening at home, light torches puts a torch on each outside corner of the shelter (1 coal and 1 stick make 4). Torches glow at night and lift Mimo's mood; in the next sub-project they will keep creatures away.
- **Farm.** Lay out a farm tills a 3 by 3 to 5 by 5 square of plots near home, beside water when there is some, or over the farm Mimo already keeps, and plants it. The farm purpose then tends it.
- **What stays clear.** Every cell a structure uses is claimed. Stairs, saplings, farm plots and portable stations keep off its walls, roof, fittings, room, door gap and way in. Gather wood chops only generated trees and trees grown from saplings Mimo planted, never placed logs.
- `/api/mimo` adds `structures` (kind, name, status and anchor) and `chests` (what each chest holds). The HUD names home, the **Blocks & crafting** panel lists what is in the chest, and Jev and Luna are told what Mimo built and how many blocks it is short.

## Current world rules
```

and replace:

```markdown
Bread (3 wheat at a crafting table) and a campfire (2 logs and 3 sticks) are recipes too, and raw fish cooks at a campfire or furnace without fuel.
```

with:

```markdown
Bread (3 wheat at a crafting table) and a campfire (2 logs and 3 sticks) are recipes too, and raw fish cooks at a campfire or furnace without fuel. So are torches (1 coal and 1 stick make 4), a chest (8 planks), a bed (6 planks) and wooden, stone and iron axes (at a crafting table; any axe chops wood twice as fast).
```

- [ ] **Step 15: Run every check again and commit**

Run: `python3 -m unittest discover -s backend/tests && cd frontend && npm test && npm run build`
Expected: `Ran 548 tests` … `OK`, `Tests  181 passed (181)`, the build succeeds.

```bash
git add README.md
git commit -m "docs: describe shelters, storage, torches, the farm and catching up" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (M5) | Where |
|-----------|-------|
| §8 needs decide what to build; a procedural generator makes the design | Tasks 3 (`blueprints`), 5, 7, 8, 9 (the purposes that use it; resolutions 2–8) |
| §8 shelter: interior at least 3×3×2, roof over all of it, a door gap, a bed if Mimo has one, passes the server's shelter check | Task 3 (sizes, door, roof shapes; every design checked with `vitals.is_sheltered`), Task 5 (bed and campfire furnishing; resolutions 3, 7, 9) |
| §8 farm: 3×3 to 5×5 farmland beside water, low fence optional | Tasks 3 (`design_farm`), 9 (`build_farm`; resolution 20: no fence, no dug water source) |
| §8 storage: a chest under a roof, inside or beside the shelter | Tasks 2 (chest steps), 7 (`build_storage` puts it in the shelter's back corner; resolution 16) |
| §8 lights: torches around home at night; they glow and lift mood | Tasks 1 (torch recipe), 8 (`light_up`), 5 (+2 mood per torch; resolution 19) |
| §8 campfire beside home, part of build_shelter or warm_up | Task 5 (a shelter fitting; resolution 21) |
| §8 generator inputs: site (flat-enough, near home, observed columns), size tier, materials Mimo has (planks, cobblestone, logs, dirt last), style knobs (roof flat/gable/dome, wall material, window pattern, door side); creativity varies style, thrift cheaper materials | Task 3 (`find_site`, `TIERS`, `supplies`, `BUILDING`, `style_for`; resolutions 3–6) |
| §8 Luna may pick the style knobs and a name once per structure | Not in M5 (resolution 4): traits and the seed choose, names are templates |
| §8 output: an ordered block list (floor, walls, roof, fittings) placed one block at a time | Tasks 3 (build order), 5 (12 placements a batch; resolution 8) |
| §8 materials run out → the purpose pauses, gathering becomes more valuable | Tasks 5 (pause and resume), 6 (`wood_goal`, `stone_goal`; resolution 22) |
| §8 inventory: 16 stacks of 32, chests 24 stacks; full makes build_storage and dropping valid | Tasks 1 (`carrying`), 2 (chest capacity), 7 (`build_storage`, `drop_items`; resolutions 15–17) |
| §5 purposes build_shelter (no shelter yet or a damaged one), build_farm, build_storage, light_up | Tasks 5, 9, 7, 8 (resolutions 2, 11, 20, 16, 19) |
| §5 reflexes: collapse sleeps in a bed within 8 blocks; head home with a shelter within 64 | Tasks 2 (collapse, sleep), 5 (head_home spares home work; `home_of` prefers the built home) |
| §5 memory: home, shelters, beds, chests | Task 4 (`structures` tables, `set_home`, `BUILT`), Task 5 (home moves into the shelter; resolutions 10, 12) |
| §5 no model call inside the tick; the payload may say what Mimo could build | All planners are rules; Task 11 (`building` in the payload) |
| §3 sleeping +0.2, in a bed +0.35; sheltered warmth; a campfire within 4 sets warmth 100 | Task 2 (`sleeping_in_bed`), Tasks 3 and 5 (the shelter check, the campfire beside the door) |
| §9 viewer: purpose and step in plain words; seeing the pet | Tasks 12 (words, home line, chest), 13 (cutaway under and behind what Mimo built; resolution 28) |
| §10 API | Task 11 (`structures` and `chests` in `/api/mimo`; resolution 27) |
| §12 planner cannot find a path or material: re-plan once, then report | M3's rule; building pauses instead of failing when blocks run out, and a blocked way in is cleared (Task 5) |
| §12 clock jump: catch-up in steps of at most 60 s applying vitals, growth and death | Task 10 (one transaction per step, rules choose between; resolution 24) |
| §13 tests: the generator (deterministic, the shelter check), every new purpose's validity and scores, headless sims | Tasks 3, 5–9, 11 (four days alone), Task 5 (the purpose budget; resolution 25) |
| §13 manual run at 60×: a night in shelter | Task 14 |
| Done when: survives nights in a shelter it built from blocks it mined; archived and viewable | Tasks 5, 11 (four-day check), 14 (seven days, then a death and the archive) |
| M3 review: `set_home` and a built marker; a structures table for damage; carry limits vs prospecting; roof cutaway; keep cleanup steps; score bands; the payload | Tasks 4 and 5; 4 and 5 (damage re-validates); 1 and 7 (the limit caps prospecting's cobblestone, resolution 15); 13; no scaffolding, so no cleanup steps (resolution 8); 11; 11 |
| M4 final review: grown trees vs built logs; one reserved rule; inventory limit and hoarding; build_farm reuses the farm; long outages | Tasks 6 (resolution 14); 4 (resolution 13); 1, 7 (resolutions 15–18); 9 (resolution 20); 10 (resolution 24) |

Out of scope here: creatures, light levels that matter, hunting and fleeing (sub-project 3); chat (sub-project 4); flowing water, falling sand and buckets (sub-project 5); Luna naming or styling a structure; fences; multi-room houses and a second home within 128 blocks.
