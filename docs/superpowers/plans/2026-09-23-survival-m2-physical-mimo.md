# Survival M2: Physical Mimo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the survival pet a body in the world: server-side 3D pathfinding over real blocks, timed steps (walk, mine, place, eat, craft, smelt, sleep, wait) that change real blocks, falls and drowning, and a viewer that streams each step and animates it.

**Architecture:** New focused modules in `backend/survival/`: `grid` (cached block lookups for one tick), `pathing` (3D A*), `steps` (what each step needs, how long it takes, what it changes), `actions` (the engine that runs the current step and the queue, with falls and a swim-up fallback), and `script` (an interim plan until the M3 brain). M1's `tick.advance_world` runs the actions at the start of each catch-up step, then advances vitals with the matching activity. `/api/mimo` streams the current step and the last 20 finished steps. The viewer gets pure, tested modules (`motion`, `animation`, `effects`) and two components (`SurvivalPet`, `ActionEffects`) that animate from server time.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-survival-core-design.md` (M2: section 6 and the M2 parts of sections 9–13). It builds on `docs/superpowers/plans/2026-09-23-survival-m1-lives-vitals.md`; that plan's Interfaces blocks are authoritative for M1 names.

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- M1 must be complete before this plan starts. Several tasks edit M1 files using the code in the M1 plan as the "old" text. If an M1 file differs from the M1 plan (review fixes), apply the same change to the equivalent lines and keep the M1 fixes.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments (mutate three.js objects only through refs inside `useFrame`, effects or event handlers), no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components.
- Keep viewer animations cheap for phones: no React state changes per frame, a few small meshes, all per-frame work in `useFrame`.
- Values copied from the spec: Mimo occupies one cell and stands in a non-solid cell whose cell below is solid (registry `solid`) or water; A* moves to the 4 horizontal neighbors, steps up 1 when the cell above Mimo is free, drops down up to 3, swims at cost ×3, no diagonal corner cutting; search budget 20,000 nodes and 96 blocks, beyond that walk in segments toward waypoints; reach 4 blocks, line of sight not required; the worker ticks every 1 s and several steps can finish in one tick; walk 0.3 s per block (0.9 s swimming); mine = hardness ÷ tool speed; hardness dirt/grass/sand/gravel 0.6, leaves 0.3, plants 0.1, wood 2.0, stone/cobblestone 4.0, ores 5.0, bedrock ∞; tool speed hand 1, wooden pickaxe 2 (stone-type), stone pickaxe 4, iron pickaxe 6, an axe doubles wood speed; place 0.3 s; eat 1.6 s; craft 1 s; smelt 5 s; sleep until energy ≥ 95 or dawn, whichever is later at night; mining still requires `requires` and yields `drop`; placing consumes the item; every block change goes through `write_block`; fall damage `(blocks fallen − 3) × 10`; air −10/s with the head in water, +25/s in air (M1 vitals).
- `MIMO_TIME_SCALE` speeds the clock and the vitals (M1). Step durations are real seconds and do not follow it, so the animations stay watchable in a 60× manual run.
- Never touch, mount or migrate the owner's real Docker volume `pets_mimo_data`. The manual check uses a fresh scratch volume and `MIMO_TIME_SCALE=60`.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (137 pass after M1, 194 after Task 7)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_pathing.py" -v`
- Frontend tests: `cd frontend && npm test` (106 pass after M1, 127 after Task 10)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint <paths>`

The counts assume M1 ended at 137 backend and 106 frontend tests, as its plan says. If M1 ended elsewhere, expect the same increases on top of the real totals.

## Decisions this plan makes

The spec leaves these open. Every task follows them.

- **Swimming** means floating on the water surface: Mimo's cell is open and the cell below is water. A route never enters a cell that is itself water, so a planned route never puts Mimo's head under water. That is how "the planner avoids water it cannot cross". When Mimo's cell is water anyway, a fallback swims it straight up at 0.9 s per block (M3's surface reflex replaces it).
- **Falls** are a streamed step (`kind: "fall"`) that lasts `sqrt(2 × blocks / 32)` seconds. Mimo lands on the first cell with something solid or water below it. Landing on water deals no damage. A fall clears the queued plan.
- **Reach** is the straight-line distance between cell coordinates, at most 4.0.
- **Hardness** for blocks the spec table does not name: snow, clay, moss, dirt path, wool, plaster and lantern 0.6; glass 0.3; planks and crafting table 2.0 (wood); brick, basalt, furnace, limestone, polished stone, dark slate, roof tile and sandstone 4.0 (stone-type); hull panel, solar panel, brass and verdigris 5.0. `null` means "cannot be mined" (air, water, lava, bedrock). A new registry key `tool` (`pickaxe` or `axe`) says which tool speeds a block up. Pickaxes help only `tool: pickaxe` blocks, the best pickaxe owned counts, and any axe (recipes arrive in M5) doubles `tool: axe` blocks.
- **Activity for vitals:** walk, swim, mine and place are `working`; sleep is `sleeping` (beds arrive in M4); craft, smelt, eat, wait and fall are `idle`.
- **Sleep** is a step with `ends_at: null`. It ends when energy ≥ 95 and the phase is not night or pre-dawn, checked at every advance.
- **Status** comes from the current step: `walking`, `swimming`, `falling`, `mining`, `building`, `eating`, `crafting`, `smelting`, `sleeping`, `idle`. The HUD shows the step in plain words ("Mining oak log").
- **Failures:** a step that cannot start or finish is recorded with a reason and the rest of the queue is dropped, so the planner plans again. A walk whose path cell turned solid stops before it ("path blocked"). Far walks re-queue themselves segment by segment, at most 12 extra segments.
- **Recent actions:** the last 20 finished steps, except waits. Mining and placing are not logged as events (the viewer gets them from `recent_actions`); crafting, smelting, eating (`ate`), falls (`fall`), sleep and wake are.
- **Planner seam:** `tick_life(..., planner=rest_plan)` and `run_once(..., planner=rest_plan)` default to M1's sleep rule as steps, which keeps every M1 test valid. The worker's `main()` uses `WORKER_PLANNER = scripted_plan`. M3 replaces both planners.
- **Interim script:** by day, walk to within 2 blocks of the lowest log of the nearest generated tree within 24 blocks, chop its logs bottom-up, craft each log into planks; with no tree in sight (or only trees where a recent step failed), walk 48 blocks in a direction that changes each game day. At night or when exhausted, sleep.
- **Food:** the spec's hunger table lives in `steps.FOOD` now; the food items arrive in M4.
- **Surroundings** (shelter, fire, head in water) are recomputed at each catch-up step because Mimo now moves.
- **Viewer timing:** the viewer runs a server clock (`server_time` + local time since the response arrived). A break's particles and item pop play when block sync removes the block (at most 2 s after the step ends); a place bounce plays at the step's end time.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `shared/blocks.json` | Modify | `hardness` for every block, `tool` for stone-type and wood blocks |
| `backend/services/blocks.py` | Modify | `hardness(material)`, `mining_tool(material)` |
| `backend/survival/grid.py` | Create | `Grid`: cached materials, body rules (`passable`, `supported`, `standable`, `swimming`), `put`, `placed_near`; `world_grid(db, seed)` |
| `backend/survival/pathing.py` | Create | `moves`, `find_path` (A* with budget), `route` (reach and segments), `timed_path` |
| `backend/survival/steps.py` | Create | Step rules: `start_step`, `finish_step`, `mine_seconds`, reach, food, stations |
| `backend/survival/actions.py` | Create | The engine: `advance_actions`, queue, hazards (fall, swim up), sleep end, recent actions, status and activity |
| `backend/survival/script.py` | Create | Interim planners `rest_plan` and `scripted_plan` (replaced by M3) |
| `backend/survival/tick.py` | Modify | Run actions at each catch-up step, per-step surroundings, fall deaths, `planner` parameter |
| `backend/survival/snapshot.py` | Modify | `action` and `recent_actions` in the survival view |
| `backend/workers/mimo_worker.py` | Modify | `WORKER_PLANNER = scripted_plan`, `planner` parameter on `run_once` |
| `backend/tests/test_blocks.py` | Modify | Hardness and tool tests |
| `backend/tests/test_survival_grid.py`, `test_survival_pathing.py`, `test_survival_steps.py`, `test_survival_actions.py`, `test_survival_script.py`, `test_survival_tick_actions.py` | Create | Tests for the new modules |
| `backend/tests/test_survival_api.py` | Modify | Streamed step fields |
| `frontend/src/survival/types.ts` | Modify | `ActionKind`, `PathPoint`, `MimoAction`, `FinishedAction`; `SurvivalState.action`, `recent_actions` |
| `frontend/src/survival/motion.ts` (+ test) | Create | Server clock, position and facing along a timed path, turning |
| `frontend/src/survival/animation.ts` (+ test) | Create | Which animation plays, body pose numbers, z's, crumbs |
| `frontend/src/survival/effects.ts` (+ test) | Create | Crack stages and texels, place bounce, particles, item pop, block effects from steps |
| `frontend/src/survival/hud.ts`, `hud.test.ts`, `SurvivalHud.tsx` | Modify | The current step in plain words |
| `frontend/src/components/world/PetVoxels.tsx` | Create | The pet's instanced voxel mesh, shared by both pet components |
| `frontend/src/components/world/PetEntity.tsx` | Modify | Uses `PetVoxels` |
| `frontend/src/survival/SurvivalPet.tsx` | Create | The pet driven by the current step |
| `frontend/src/survival/ActionEffects.tsx` | Create | Cracks, break particles, item pop, place bounce |
| `frontend/src/survival/WorldCanvas.tsx`, `SurvivalWorld.tsx` | Modify | Wire the pet and effects to the streamed step |
| `README.md` | Modify | Actions section |

---

### Task 1: Hardness and mining tools in the block registry

**Files:**
- Modify: `shared/blocks.json` (the `"blocks"` array)
- Modify: `backend/services/blocks.py` (append two functions)
- Test: `backend/tests/test_blocks.py`

**Interfaces:**
- Consumes: `BLOCK_IDS`, `BLOCK_LIST` in `backend.services.blocks`.
- Produces (`backend.services.blocks`): `hardness(material: str) -> float | None` (seconds by hand; None when the block cannot be mined or is unknown), `mining_tool(material: str) -> str | None` (`"pickaxe"`, `"axe"` or None). Every registry block has a `hardness` key (`null` or a positive number). `crafting.BLOCKS[name]` now also carries `hardness` and, for some blocks, `tool`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_blocks.py`, replace the import line (M1 added `is_solid` to it):

```python
from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, TILES, is_plant, is_replaceable, is_solid
```

with:

```python
from backend.services.blocks import (
    BLOCK_IDS, BLOCK_LIST, TILES, hardness, is_plant, is_replaceable, is_solid, mining_tool,
)
```

Replace the test `test_existing_block_properties_are_unchanged`:

```python
    def test_existing_block_properties_are_unchanged(self):
        for name, properties in LEGACY_BLOCKS.items():
            self.assertEqual(BLOCKS[name], properties, name)
        self.assertNotIn("air", BLOCKS)
```

with:

```python
    def test_existing_block_properties_are_unchanged(self):
        mining_keys = {"hardness", "tool"}
        for name, properties in LEGACY_BLOCKS.items():
            gameplay = {key: value for key, value in BLOCKS[name].items() if key not in mining_keys}
            self.assertEqual(gameplay, properties, name)
        self.assertNotIn("air", BLOCKS)
```

Add these tests at the end of `BlockRegistryTests`:

```python
    def test_hardness_follows_the_spec_table(self):
        expected = {"dirt": 0.6, "grass": 0.6, "sand": 0.6, "gravel": 0.6, "leaves": 0.3, "tall_grass": 0.1,
                    "flower_pink": 0.1, "oak_log": 2.0, "planks": 2.0, "stone": 4.0, "cobblestone": 4.0,
                    "coal_ore": 5.0, "iron_ore": 5.0, "copper_ore": 5.0}
        for name, seconds in expected.items():
            self.assertEqual(hardness(name), seconds, name)
        for name in ("bedrock", "air", "water", "lava", "not_a_block"):
            self.assertIsNone(hardness(name), name)

    def test_every_block_declares_a_hardness(self):
        for block in BLOCK_LIST:
            self.assertIn("hardness", block, block["name"])
            self.assertTrue(block["hardness"] is None or block["hardness"] > 0, block["name"])

    def test_pickaxes_help_with_stone_and_axes_with_wood(self):
        for name in ("stone", "cobblestone", "coal_ore", "iron_ore", "furnace", "brick"):
            self.assertEqual(mining_tool(name), "pickaxe", name)
        for name in ("oak_log", "planks", "crafting_table"):
            self.assertEqual(mining_tool(name), "axe", name)
        for name in ("dirt", "leaves", "tall_grass", "bedrock", "not_a_block"):
            self.assertIsNone(mining_tool(name), name)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_blocks.py"`
Expected: `ImportError: cannot import name 'hardness' from 'backend.services.blocks'`.

- [ ] **Step 3: Add hardness and tools to the registry**

In `shared/blocks.json`, replace the whole `"blocks": [ … ]` array (keep `"tiles"` as it is) with:

```json
  "blocks": [
    {"name": "air", "color": [0, 0, 0], "textures": "missing", "layer": "none", "solid": false, "replaceable": true, "drop": null, "hardness": null},
    {"name": "grass", "color": [127, 173, 137], "textures": {"top": "grass_top", "side": "grass_side", "bottom": "dirt"}, "layer": "opaque", "solid": true, "drop": "dirt", "hardness": 0.6},
    {"name": "snow", "color": [236, 241, 243], "textures": {"top": "snow", "side": "snow_side", "bottom": "dirt"}, "layer": "opaque", "solid": true, "drop": "dirt", "hardness": 0.6},
    {"name": "dirt", "color": [126, 105, 89], "textures": "dirt", "layer": "opaque", "solid": true, "drop": "dirt", "hardness": 0.6},
    {"name": "stone", "color": [153, 151, 148], "textures": "stone", "layer": "opaque", "solid": true, "drop": "cobblestone", "requires": "wooden_pickaxe", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "cobblestone", "color": [130, 137, 137], "textures": "cobblestone", "layer": "opaque", "solid": true, "drop": "cobblestone", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "bedrock", "color": [67, 72, 75], "textures": "bedrock", "layer": "opaque", "solid": true, "drop": null, "hardness": null},
    {"name": "sand", "color": [222, 203, 158], "textures": "sand", "layer": "opaque", "solid": true, "drop": "sand", "gravity": true, "hardness": 0.6},
    {"name": "gravel", "color": [159, 166, 162], "textures": "gravel", "layer": "opaque", "solid": true, "drop": "gravel", "gravity": true, "hardness": 0.6},
    {"name": "clay", "color": [166, 190, 192], "textures": "clay", "layer": "opaque", "solid": true, "drop": "clay", "hardness": 0.6},
    {"name": "brick", "color": [184, 105, 86], "textures": "brick", "layer": "opaque", "solid": true, "drop": "brick", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "basalt", "color": [75, 83, 86], "textures": "basalt", "layer": "opaque", "solid": true, "drop": "basalt", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "oak_log", "color": [139, 105, 82], "textures": {"top": "log_top", "side": "log_side", "bottom": "log_top"}, "layer": "opaque", "solid": true, "drop": "oak_log", "hardness": 2.0, "tool": "axe"},
    {"name": "planks", "color": [202, 171, 125], "textures": "planks", "layer": "opaque", "solid": true, "drop": "planks", "hardness": 2.0, "tool": "axe"},
    {"name": "leaves", "color": [101, 164, 128], "textures": "leaves", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.3},
    {"name": "coal_ore", "color": [88, 94, 97], "textures": "coal_ore", "layer": "opaque", "solid": true, "drop": "coal", "requires": "wooden_pickaxe", "hardness": 5.0, "tool": "pickaxe"},
    {"name": "iron_ore", "color": [182, 138, 107], "textures": "iron_ore", "layer": "opaque", "solid": true, "drop": "iron_ore", "requires": "stone_pickaxe", "hardness": 5.0, "tool": "pickaxe"},
    {"name": "copper_ore", "color": [170, 116, 91], "textures": "copper_ore", "layer": "opaque", "solid": true, "drop": "copper_ore", "requires": "stone_pickaxe", "hardness": 5.0, "tool": "pickaxe"},
    {"name": "glass", "color": [160, 218, 218], "textures": "glass", "layer": "translucent", "solid": true, "drop": "glass", "opacity": 0.38, "hardness": 0.3},
    {"name": "water", "color": [103, 179, 203], "textures": "water", "layer": "translucent", "solid": false, "replaceable": true, "drop": null, "opacity": 0.58, "fluid": true, "hardness": null},
    {"name": "lava", "color": [244, 117, 57], "textures": "lava", "layer": "translucent", "solid": false, "drop": null, "opacity": 0.85, "fluid": true, "glow": true, "hardness": null},
    {"name": "wool", "color": [238, 226, 204], "textures": "wool", "layer": "opaque", "solid": true, "drop": "wool", "hardness": 0.6},
    {"name": "moss", "color": [85, 139, 100], "textures": "moss", "layer": "opaque", "solid": true, "drop": "moss", "hardness": 0.6},
    {"name": "lantern", "color": [247, 213, 143], "textures": "lantern", "layer": "opaque", "solid": true, "drop": "lantern", "glow": true, "hardness": 0.6},
    {"name": "crafting_table", "color": [169, 117, 72], "textures": {"top": "crafting_table_top", "side": "crafting_table_side", "bottom": "planks"}, "layer": "opaque", "solid": true, "drop": "crafting_table", "hardness": 2.0, "tool": "axe"},
    {"name": "furnace", "color": [88, 91, 89], "textures": {"top": "furnace_top", "side": "furnace_side", "bottom": "furnace_top"}, "layer": "opaque", "solid": true, "drop": "furnace", "glow": true, "hardness": 4.0, "tool": "pickaxe"},
    {"name": "limestone", "color": [227, 211, 181], "textures": "limestone", "layer": "opaque", "solid": true, "drop": "limestone", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "polished_stone", "color": [169, 183, 178], "textures": "polished_stone", "layer": "opaque", "solid": true, "drop": "polished_stone", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "dark_slate", "color": [82, 104, 111], "textures": "dark_slate", "layer": "opaque", "solid": true, "drop": "dark_slate", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "plaster", "color": [229, 206, 171], "textures": "plaster", "layer": "opaque", "solid": true, "drop": "plaster", "hardness": 0.6},
    {"name": "roof_tile", "color": [193, 112, 100], "textures": "roof_tile", "layer": "opaque", "solid": true, "drop": "roof_tile", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "dirt_path", "color": [215, 196, 159], "textures": {"top": "dirt_path", "side": "dirt", "bottom": "dirt"}, "layer": "opaque", "solid": true, "drop": "dirt", "hardness": 0.6},
    {"name": "hull_panel", "color": [189, 200, 198], "textures": "hull_panel", "layer": "opaque", "solid": true, "drop": "hull_panel", "hardness": 5.0, "tool": "pickaxe"},
    {"name": "solar_panel", "color": [91, 155, 171], "textures": "solar_panel", "layer": "opaque", "solid": true, "drop": "solar_panel", "hardness": 5.0, "tool": "pickaxe"},
    {"name": "brass", "color": [226, 192, 126], "textures": "brass", "layer": "opaque", "solid": true, "drop": "brass", "hardness": 5.0, "tool": "pickaxe"},
    {"name": "sandstone", "color": [245, 197, 151], "textures": "sandstone", "layer": "opaque", "solid": true, "drop": "sandstone", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "verdigris", "color": [152, 192, 187], "textures": "verdigris", "layer": "opaque", "solid": true, "drop": "verdigris", "hardness": 5.0, "tool": "pickaxe"},
    {"name": "tall_grass", "color": [89, 147, 112], "textures": "tall_grass", "layer": "cutout", "solid": false, "replaceable": true, "drop": null, "hardness": 0.1},
    {"name": "flower_orange", "color": [246, 192, 124], "textures": "flower_orange", "layer": "cutout", "solid": false, "replaceable": true, "drop": "flower_orange", "hardness": 0.1},
    {"name": "flower_pink", "color": [243, 164, 168], "textures": "flower_pink", "layer": "cutout", "solid": false, "replaceable": true, "drop": "flower_pink", "hardness": 0.1},
    {"name": "flower_yellow", "color": [250, 218, 139], "textures": "flower_yellow", "layer": "cutout", "solid": false, "replaceable": true, "drop": "flower_yellow", "hardness": 0.1}
  ]
```

Only `hardness` and `tool` are new; every other key and value is unchanged.

- [ ] **Step 4: Add the lookups**

Append to `backend/services/blocks.py`:

```python


def hardness(material: str) -> float | None:
    """Seconds to mine the block by hand (registry `hardness`), or None when it cannot be mined."""
    index = BLOCK_IDS.get(material)
    if index is None:
        return None
    seconds = BLOCK_LIST[index].get("hardness")
    return None if seconds is None else float(seconds)


def mining_tool(material: str) -> str | None:
    """The tool that speeds up mining the block (registry `tool`): "pickaxe", "axe" or None."""
    index = BLOCK_IDS.get(material)
    return None if index is None else BLOCK_LIST[index].get("tool")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_blocks.py"`
Expected: `Ran 10 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 140 tests` … `OK`

Run: `cd frontend && npm test`
Expected: `Tests  106 passed (106)` (the viewer ignores the new keys).

- [ ] **Step 6: Commit**

```bash
git add shared/blocks.json backend/services/blocks.py backend/tests/test_blocks.py
git commit -m "feat: give every block a mining hardness and tool" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Grid lookups for one tick

**Files:**
- Create: `backend/survival/grid.py`
- Test: `backend/tests/test_survival_grid.py`

**Interfaces:**
- Consumes: `write_block(db, x, y, z, material)` (M1 `backend.services.block_table`), `is_plant`, `is_solid` (`backend.services.blocks`), `block_at(x, y, z, seed)` (`backend.services.worldgen`).
- Produces (`backend.survival.grid`): `Cell = tuple[int, int, int]`, `CHUNK = 16`, `FLUIDS = ("water", "lava")`, and `Grid(natural, load_edits=None, write=None)` with `edits: dict[Cell, str]`, `material(x, y, z) -> str`, `put(x, y, z, material) -> None`, `solid(cell) -> bool`, `water(cell) -> bool`, `passable(cell) -> bool` (not solid, not water or lava), `supported(cell) -> bool` (cell below solid or water), `standable(cell) -> bool`, `swimming(cell) -> bool` (passable and the cell below is water), `placed_near(x, z, reach, materials) -> set[str]`. Also `world_grid(db: sqlite3.Connection, seed: str) -> Grid` (loads edits per 16×16 chunk, writes through `write_block`).

`Grid.material` follows `block_table.resolve_block` exactly: an edit wins, and a natural plant whose cell below was edited is air. A grid lives for one transaction; natural blocks are cached for its whole life.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_grid.py`:

```python
import tempfile
import unittest
from pathlib import Path

from backend.services.block_table import material_in
from backend.services.worldgen import terrain_height
from backend.survival.grid import Grid, world_grid
from backend.survival.world import SurvivalWorld, new_survival_state

SEED = "123456789123456789"
SPAWN = {"x": 3682, "y": 5, "z": 4143}


def small_world(cells):
    """Stone at y <= 0 and air above, with `cells` overriding single cells."""
    return Grid(lambda x, y, z: cells.get((x, y, z), "stone" if y <= 0 else "air"))


class GridTests(unittest.TestCase):
    def test_edits_win_and_a_plant_over_an_edited_cell_is_air(self):
        grid = small_world({(0, 1, 0): "tall_grass"})
        self.assertEqual(grid.material(0, 1, 0), "tall_grass")
        grid.put(0, 0, 0, "air")
        self.assertEqual(grid.material(0, 0, 0), "air")
        self.assertEqual(grid.material(0, 1, 0), "air")

    def test_body_rules(self):
        grid = small_world({(1, 0, 0): "water", (2, 1, 0): "water", (3, 1, 0): "tall_grass", (4, 1, 0): "lava",
                            (5, 0, 0): "air"})
        self.assertTrue(grid.standable((0, 1, 0)))
        self.assertFalse(grid.swimming((0, 1, 0)))
        self.assertTrue(grid.standable((1, 1, 0)))
        self.assertTrue(grid.swimming((1, 1, 0)))
        self.assertTrue(grid.water((2, 1, 0)))
        self.assertFalse(grid.passable((2, 1, 0)))
        self.assertTrue(grid.standable((3, 1, 0)))
        self.assertFalse(grid.passable((4, 1, 0)))
        self.assertFalse(grid.supported((5, 1, 0)))
        self.assertTrue(grid.solid((0, 0, 0)))
        self.assertFalse(grid.standable((0, 0, 0)))

    def test_natural_blocks_are_generated_once_per_cell(self):
        calls = []

        def natural(x, y, z):
            calls.append((x, y, z))
            return "air"

        grid = Grid(natural)
        for _ in range(3):
            grid.material(4, 5, 6)
        self.assertEqual(calls, [(4, 5, 6)])

    def test_placed_near_finds_workstations_within_reach(self):
        grid = small_world({})
        grid.put(3, 1, 4, "crafting_table")
        grid.put(20, 1, 0, "furnace")
        self.assertEqual(grid.placed_near(0, 0, 6, ("crafting_table", "furnace")), {"crafting_table"})


class WorldGridTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.world = SurvivalWorld.create(Path(self.directory.name) / "2.sqlite3", new_survival_state(
            name="Pip", seed=SEED, spawn=SPAWN, born_at=1000.0, traits={}))

    def tearDown(self):
        self.directory.cleanup()

    def test_matches_the_world_database_cell_for_cell(self):
        x0, z0 = SPAWN["x"], SPAWN["z"]
        ground = terrain_height(x0, z0, SEED)
        self.world.put_block(x0, ground, z0, "air")
        self.world.put_block(x0 + 1, ground + 1, z0, "planks")
        self.world.put_block(x0 + 17, ground, z0 - 1, "stone")  # in the next chunk
        with self.world.connect() as db:
            grid = world_grid(db, SEED)
            for x in range(x0 - 2, x0 + 19):
                for z in (z0 - 1, z0, z0 + 1):
                    for y in range(ground - 2, ground + 7):
                        self.assertEqual(grid.material(x, y, z), material_in(db, x, y, z, SEED), (x, y, z))

    def test_put_writes_a_numbered_block_change(self):
        x, z = SPAWN["x"], SPAWN["z"]
        with self.world.transaction() as db:
            world_grid(db, SEED).put(x, 40, z, "planks")
        self.assertEqual(self.world.blocks_seq(), 1)
        self.assertEqual(self.world.material_at(x, 40, z), "planks")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_grid.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.grid'`.

- [ ] **Step 3: Write the grid**

Create `backend/survival/grid.py`:

```python
"""Block lookups for one tick of a survival world: saved edits over the natural world.

The pathfinder and the action system ask about thousands of cells in a tick. A Grid caches
natural blocks and loads saved edits one 16x16 chunk at a time. `put` records an edit and
passes it to the world's write_block, so viewers receive it through block sync.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Callable

from backend.services.block_table import write_block
from backend.services.blocks import is_plant, is_solid
from backend.services.worldgen import block_at

Cell = tuple[int, int, int]
MaterialAt = Callable[[int, int, int], str]
LoadEdits = Callable[[int, int], dict[Cell, str]]
WriteBlock = Callable[[int, int, int, str], None]
CHUNK = 16
FLUIDS = ("water", "lava")


class Grid:
    """Materials by cell, with the rules Mimo's one-cell body needs.

    `natural(x, y, z)` gives the generated block. `load_edits(cx, cz)` returns the saved edits of
    one chunk and `write` stores a new edit. Tests build small worlds from `natural` alone.
    """

    def __init__(self, natural: MaterialAt, load_edits: LoadEdits | None = None, write: WriteBlock | None = None):
        self._natural = natural
        self._load_edits = load_edits
        self._write = write
        self._natural_cache: dict[Cell, str] = {}
        self._loaded_chunks: set[tuple[int, int]] = set()
        self.edits: dict[Cell, str] = {}

    def _load(self, x: int, z: int) -> None:
        if self._load_edits is None:
            return
        chunk = (x // CHUNK, z // CHUNK)
        if chunk in self._loaded_chunks:
            return
        self._loaded_chunks.add(chunk)
        for cell, material in self._load_edits(*chunk).items():
            self.edits.setdefault(cell, material)

    def material(self, x: int, y: int, z: int) -> str:
        """The block at a cell by block_table.resolve_block's rule: an edit wins, and a natural
        plant whose cell below was edited (dug out or built on) is air."""
        self._load(x, z)
        edit = self.edits.get((x, y, z))
        if edit is not None:
            return edit
        natural = self._natural_cache.get((x, y, z))
        if natural is None:
            natural = self._natural(x, y, z)
            self._natural_cache[(x, y, z)] = natural
        if is_plant(natural) and (x, y - 1, z) in self.edits:
            return "air"
        return natural

    def put(self, x: int, y: int, z: int, material: str) -> None:
        self._load(x, z)
        self.edits[(x, y, z)] = material
        if self._write is not None:
            self._write(x, y, z, material)

    def solid(self, cell: Cell) -> bool:
        return is_solid(self.material(*cell))

    def water(self, cell: Cell) -> bool:
        return self.material(*cell) == "water"

    def passable(self, cell: Cell) -> bool:
        """Mimo's body fits in the cell: nothing solid, and no water or lava."""
        material = self.material(*cell)
        return material not in FLUIDS and not is_solid(material)

    def supported(self, cell: Cell) -> bool:
        """Something holds Mimo up in this cell: the cell below is solid or water."""
        x, y, z = cell
        below = self.material(x, y - 1, z)
        return below == "water" or is_solid(below)

    def standable(self, cell: Cell) -> bool:
        return self.passable(cell) and self.supported(cell)

    def swimming(self, cell: Cell) -> bool:
        """Mimo floats on the water surface here: its body fits and the cell below is water."""
        x, y, z = cell
        return self.passable(cell) and self.material(x, y - 1, z) == "water"

    def placed_near(self, x: int, z: int, reach: float, materials: tuple[str, ...]) -> set[str]:
        """Which of `materials` have been placed within `reach` blocks (horizontally) of (x, z)."""
        for cx in range(math.floor((x - reach) / CHUNK), math.floor((x + reach) / CHUNK) + 1):
            for cz in range(math.floor((z - reach) / CHUNK), math.floor((z + reach) / CHUNK) + 1):
                self._load(cx * CHUNK, cz * CHUNK)
        return {material for (bx, _, bz), material in self.edits.items()
                if material in materials and math.hypot(bx - x, bz - z) <= reach}


def world_grid(db: sqlite3.Connection, seed: str) -> Grid:
    """A grid over one survival world's database, for the length of one transaction."""

    def load_edits(cx: int, cz: int) -> dict[Cell, str]:
        rows = db.execute("SELECT x,y,z,material FROM mimo_blocks WHERE x BETWEEN ? AND ? AND z BETWEEN ? AND ?",
                          (cx * CHUNK, cx * CHUNK + CHUNK - 1, cz * CHUNK, cz * CHUNK + CHUNK - 1)).fetchall()
        return {(row["x"], row["y"], row["z"]): row["material"] for row in rows}

    def write(x: int, y: int, z: int, material: str) -> None:
        write_block(db, x, y, z, material)

    return Grid(lambda x, y, z: block_at(x, y, z, seed), load_edits, write)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_grid.py"`
Expected: `Ran 6 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 146 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/grid.py backend/tests/test_survival_grid.py
git commit -m "feat: add cached block lookups for survival ticks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 3D pathfinding

**Files:**
- Create: `backend/survival/pathing.py`
- Test: `backend/tests/test_survival_pathing.py`

**Interfaces:**
- Consumes: `Cell`, `Grid` (Task 2).
- Produces (`backend.survival.pathing`): `MAX_NODES = 20_000`, `MAX_RANGE = 96`, `MAX_DROP = 3`, `SWIM_COST = 3.0`, `WALK_SECONDS = 0.3`, `SWIM_SECONDS = 0.9`, `SEGMENT = 88`, `WAYPOINT_SLACK = 3`; `moves(grid, cell) -> Iterator[Cell]`; `move_cost(grid, cell) -> float`; `find_path(grid, start, is_goal, toward, slack=0, max_nodes=MAX_NODES, max_range=MAX_RANGE) -> tuple[list[Cell], bool]` (cells after the start and whether a goal was reached; on failure the route leads to the explored cell nearest `toward`); `route(grid, start, target, reach=0.0) -> tuple[list[Cell], bool]` (reach 0 ends on the target, otherwise on any other cell within `reach`; targets more than 96 blocks away on an axis return one segment with `reached` False); `timed_path(grid, start, cells, started_at) -> list[dict]` (entries `{"x", "y", "z", "at"}` plus `"swim": True` on water-surface cells; the first entry is the start at `started_at`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_pathing.py`:

```python
import unittest

from backend.survival.grid import Grid
from backend.survival.pathing import MAX_NODES, MAX_RANGE, find_path, moves, route, timed_path


def world(rule):
    """A grid from a function of (x, y, z) that returns a material name."""
    return Grid(rule)


def flat(x, y, z):
    return "stone" if y <= 0 else "air"


class MoveTests(unittest.TestCase):
    def test_flat_ground_offers_the_four_neighbors(self):
        self.assertEqual(sorted(moves(world(flat), (0, 1, 0))), [(-1, 1, 0), (0, 1, -1), (0, 1, 1), (1, 1, 0)])

    def test_stepping_up_one_needs_headroom(self):
        step = {(1, 1, 0): "stone"}
        grid = world(lambda x, y, z: step.get((x, y, z)) or flat(x, y, z))
        self.assertIn((1, 2, 0), list(moves(grid, (0, 1, 0))))
        step[(0, 2, 0)] = "stone"
        grid = world(lambda x, y, z: step.get((x, y, z)) or flat(x, y, z))
        self.assertNotIn((1, 2, 0), list(moves(grid, (0, 1, 0))))

    def test_two_blocks_up_is_too_high(self):
        wall = world(lambda x, y, z: "stone" if y <= 0 or (x == 1 and y <= 2) else "air")
        self.assertNotIn(1, [cell[0] for cell in moves(wall, (0, 1, 0))])

    def test_drops_of_up_to_three(self):
        def ledge(height):
            return world(lambda x, y, z: "stone" if y <= 0 or (x <= 0 and y <= height) else "air")
        self.assertIn((1, 1, 0), list(moves(ledge(3), (0, 4, 0))))
        self.assertNotIn(1, [cell[0] for cell in moves(ledge(4), (0, 5, 0))])

    def test_mimo_swims_on_the_surface_but_never_under_it(self):
        pond = world(lambda x, y, z: "water" if x >= 1 and y <= 0 else flat(x, y, z))
        self.assertIn((1, 1, 0), list(moves(pond, (0, 1, 0))))
        self.assertTrue(pond.swimming((1, 1, 0)))
        high = world(lambda x, y, z: "water" if x >= 1 and y <= 1 else flat(x, y, z))
        reachable = list(moves(high, (0, 1, 0)))
        self.assertNotIn((1, 1, 0), reachable)
        self.assertIn((1, 2, 0), reachable)


class RouteTests(unittest.TestCase):
    def assert_connected(self, start, cells):
        previous = start
        for cell in cells:
            self.assertEqual(abs(cell[0] - previous[0]) + abs(cell[2] - previous[2]), 1, (previous, cell))
            previous = cell

    def test_walks_on_flat_ground_one_side_step_at_a_time(self):
        cells, reached = route(world(flat), (0, 1, 0), (5, 1, 5))
        self.assertTrue(reached)
        self.assertEqual(len(cells), 10)
        self.assertEqual(cells[-1], (5, 1, 5))
        self.assert_connected((0, 1, 0), cells)

    def test_climbs_a_step_and_drops_off_the_far_side(self):
        rule = lambda x, y, z: "stone" if y <= 0 or (x == 3 and y <= 1) else "air"
        cells, reached = route(world(rule), (0, 1, 0), (6, 1, 0))
        self.assertTrue(reached)
        self.assertIn((3, 2, 0), cells)
        self.assertEqual(len(cells), 6)

    def test_a_wall_two_high_blocks_the_way(self):
        rule = lambda x, y, z: "stone" if y <= 0 or (x == 3 and y <= 2) else "air"
        cells, reached = find_path(world(rule), (0, 1, 0), lambda cell: cell == (6, 1, 0), (6, 1, 0), max_range=8)
        self.assertFalse(reached)
        self.assertEqual(cells[-1], (2, 1, 0))

    def test_a_drop_deeper_than_three_is_never_taken(self):
        cliff = world(lambda x, y, z: "stone" if y <= 0 or (x <= 0 and y <= 4) else "air")
        _, reached = find_path(cliff, (0, 5, 0), lambda cell: cell == (3, 1, 0), (3, 1, 0), max_range=6)
        self.assertFalse(reached)
        step = world(lambda x, y, z: "stone" if y <= 0 or (x <= 0 and y <= 3) else "air")
        cells, reached = route(step, (0, 4, 0), (3, 1, 0))
        self.assertTrue(reached)
        self.assertEqual(cells, [(1, 1, 0), (2, 1, 0), (3, 1, 0)])

    def test_swimming_costs_three_times_as_much(self):
        def pool(half_width):
            def rule(x, y, z):
                if 1 <= x <= 3 and abs(z) <= half_width and y == 0:
                    return "water"
                return flat(x, y, z)
            return world(rule)

        narrow = pool(1)
        detour, reached = route(narrow, (0, 1, 0), (4, 1, 0))
        self.assertTrue(reached)
        self.assertEqual(len(detour), 8)
        self.assertFalse(any(narrow.swimming(cell) for cell in detour))
        wide = pool(5)
        across, _ = route(wide, (0, 1, 0), (4, 1, 0))
        self.assertEqual(across, [(1, 1, 0), (2, 1, 0), (3, 1, 0), (4, 1, 0)])
        timed = timed_path(wide, (0, 1, 0), across, 10.0)
        self.assertEqual([entry["at"] for entry in timed], [10.0, 10.9, 11.8, 12.7, 13.0])
        self.assertEqual([entry.get("swim", False) for entry in timed], [False, True, True, True, False])

    def test_reach_stops_beside_the_target(self):
        trunk = world(lambda x, y, z: "oak_log" if (x, z) == (5, 0) and 1 <= y <= 4 else flat(x, y, z))
        cells, reached = route(trunk, (0, 1, 0), (5, 1, 0), reach=1.5)
        self.assertTrue(reached)
        self.assertEqual(cells[-1], (4, 1, 0))

    def test_far_targets_are_reached_in_segments(self):
        grid = world(flat)
        position, segments = (0, 1, 0), 0
        while True:
            cells, reached = route(grid, position, (300, 1, 40))
            self.assertTrue(cells)
            for cell in cells:
                self.assertLessEqual(abs(cell[0] - position[0]), MAX_RANGE)
                self.assertLessEqual(abs(cell[2] - position[2]), MAX_RANGE)
            position, segments = cells[-1], segments + 1
            if reached:
                break
        self.assertEqual(position, (300, 1, 40))
        self.assertEqual(segments, 4)

    def test_the_search_stops_at_its_node_budget(self):
        self.assertEqual((MAX_NODES, MAX_RANGE), (20_000, 96))
        walled = world(lambda x, y, z: "stone" if y <= 0 or (x == 30 and y <= 2) else "air")
        cells, reached = find_path(walled, (0, 1, 0), lambda cell: cell == (40, 1, 0), (40, 1, 0), max_nodes=500)
        self.assertFalse(reached)
        self.assertEqual(cells[-1], (29, 1, 0))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_pathing.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.pathing'`.

- [ ] **Step 3: Write the pathfinder**

Create `backend/survival/pathing.py`:

```python
"""Paths for a one-cell Mimo: 3D A* over cells.

Mimo moves to one of its 4 horizontal neighbors at a time: on the same level, one step up
when the cell above its head is free, or off a ledge down at most 3 cells. Swimming happens
on the water surface (the cell below Mimo is water) and costs 3 times as much as walking.
A route never enters a cell that is itself water, so Mimo never plans to put its head under.
A search expands at most 20,000 cells and stays within 96 blocks of the start on each
horizontal axis. Farther targets are reached in segments toward waypoints.
"""

from __future__ import annotations

import heapq
import math
from itertools import count
from typing import Callable, Iterator

from backend.survival.grid import Cell, Grid

MAX_NODES = 20_000
MAX_RANGE = 96
MAX_DROP = 3
SWIM_COST = 3.0
WALK_SECONDS = 0.3
SWIM_SECONDS = 0.9
# A far target gets a waypoint this many blocks along the way, inside MAX_RANGE.
SEGMENT = 88
# A segment ends on any cell this close to its waypoint (horizontal Manhattan distance).
WAYPOINT_SLACK = 3
HORIZONTAL = ((1, 0), (-1, 0), (0, 1), (0, -1))


def moves(grid: Grid, cell: Cell) -> Iterator[Cell]:
    """Cells Mimo can reach from `cell` in one move."""
    x, y, z = cell
    headroom: bool | None = None
    for dx, dz in HORIZONTAL:
        level = (x + dx, y, z + dz)
        if grid.passable(level):
            if grid.supported(level):
                yield level
                continue
            for drop in range(1, MAX_DROP + 1):
                lower = (level[0], y - drop, level[2])
                if not grid.passable(lower):
                    break
                if grid.supported(lower):
                    yield lower
                    break
            continue
        if headroom is None:
            headroom = grid.passable((x, y + 1, z))
        up = (level[0], y + 1, level[2])
        if headroom and grid.standable(up):
            yield up


def move_cost(grid: Grid, cell: Cell) -> float:
    return SWIM_COST if grid.swimming(cell) else 1.0


def trace(came_from: dict[Cell, Cell | None], cell: Cell) -> list[Cell]:
    cells = []
    while came_from[cell] is not None:
        cells.append(cell)
        cell = came_from[cell]
    cells.reverse()
    return cells


def find_path(grid: Grid, start: Cell, is_goal: Callable[[Cell], bool], toward: Cell, slack: int = 0,
              max_nodes: int = MAX_NODES, max_range: int = MAX_RANGE) -> tuple[list[Cell], bool]:
    """A* from `start` to the cheapest cell where `is_goal` holds.

    The estimate is the horizontal Manhattan distance to `toward`, less `slack` (how far a goal
    cell may lie from `toward`), so it never overestimates. Ties go to the cell nearer the goal.
    Returns the cells after the start and whether a goal was reached. When the budget runs out
    first, the route leads to the explored cell with the lowest estimate ([] if that is the start).
    """

    def estimate(cell: Cell) -> int:
        return max(0, abs(cell[0] - toward[0]) + abs(cell[2] - toward[2]) - slack)

    order = count()
    frontier = [(estimate(start), estimate(start), next(order), 0.0, start)]
    came_from: dict[Cell, Cell | None] = {start: None}
    best_cost = {start: 0.0}
    nearest, nearest_estimate = start, estimate(start)
    expanded = 0
    while frontier and expanded < max_nodes:
        _, remaining, _, cost, cell = heapq.heappop(frontier)
        if cost > best_cost[cell]:
            continue
        if is_goal(cell):
            return trace(came_from, cell), True
        expanded += 1
        if remaining < nearest_estimate:
            nearest, nearest_estimate = cell, remaining
        for step in moves(grid, cell):
            if abs(step[0] - start[0]) > max_range or abs(step[2] - start[2]) > max_range:
                continue
            new_cost = cost + move_cost(grid, step)
            if new_cost < best_cost.get(step, math.inf):
                best_cost[step] = new_cost
                came_from[step] = cell
                guess = estimate(step)
                heapq.heappush(frontier, (new_cost + guess, guess, next(order), new_cost, step))
    return trace(came_from, nearest), False


def route(grid: Grid, start: Cell, target: Cell, reach: float = 0.0) -> tuple[list[Cell], bool]:
    """A route from `start` toward `target`.

    With reach 0 the route ends on `target`; otherwise on any cell other than `target` within
    `reach` blocks of it. A target more than MAX_RANGE blocks away on either axis is approached
    one segment at a time: the route ends near a waypoint SEGMENT blocks along the way and
    `reached` is False. The caller walks the segment and asks again.
    """
    dx, dz = target[0] - start[0], target[2] - start[2]
    if max(abs(dx), abs(dz)) > MAX_RANGE:
        share = SEGMENT / max(abs(dx), abs(dz))
        waypoint = (start[0] + round(dx * share), start[1], start[2] + round(dz * share))
        cells, _ = find_path(grid, start,
                             lambda cell: abs(cell[0] - waypoint[0]) + abs(cell[2] - waypoint[2]) <= WAYPOINT_SLACK,
                             waypoint, slack=WAYPOINT_SLACK)
        return cells, False
    if reach <= 0:
        return find_path(grid, start, lambda cell: cell == target, target)
    return find_path(grid, start, lambda cell: cell != target and math.dist(cell, target) <= reach,
                     target, slack=math.ceil(reach * math.sqrt(2)))


def timed_path(grid: Grid, start: Cell, cells: list[Cell], started_at: float) -> list[dict]:
    """The start and each cell after it with the time Mimo gets there. Water-surface cells say so."""
    at = started_at
    path = [{"x": start[0], "y": start[1], "z": start[2], "at": started_at}]
    for cell in cells:
        swim = grid.swimming(cell)
        at = round(at + (SWIM_SECONDS if swim else WALK_SECONDS), 3)
        entry = {"x": cell[0], "y": cell[1], "z": cell[2], "at": at}
        if swim:
            entry["swim"] = True
        path.append(entry)
    return path
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_pathing.py"`
Expected: `Ran 13 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 159 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/pathing.py backend/tests/test_survival_pathing.py
git commit -m "feat: find 3D paths over real blocks with a search budget" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Step rules

**Files:**
- Create: `backend/survival/steps.py`
- Test: `backend/tests/test_survival_steps.py`

**Interfaces:**
- Consumes: `hardness`, `mining_tool`, `is_replaceable` (`backend.services.blocks`); `BLOCKS`, `add_item`, `can_harvest`, `craft`, `smelt`, `take_items` (`backend.services.crafting`); `Grid`, `Cell` (Task 2); `route`, `timed_path` (Task 3).
- Produces (`backend.survival.steps`): `REACH = 4.0`, `STATION_REACH = 6.0`, `WORKSTATIONS`, `PLACE_SECONDS = 0.3`, `EAT_SECONDS = 1.6`, `CRAFT_SECONDS = 1.0`, `SMELT_SECONDS = 5.0`, `PICKAXE_SPEED`, `AXES`, `AXE_SPEED = 2.0`, `FOOD` (hunger per item), `MAX_SEGMENTS = 12`, `StepFailed(ValueError)`, `as_cell(value) -> Cell` (from `[x, y, z]` or `{"x", "y", "z"}`), `as_point(cell) -> dict` (ints), `position_of(point) -> dict` (floats), `tool_speed(material, inventory) -> float`, `mine_seconds(material, inventory) -> float | None`, `in_reach(here, target) -> bool`, `stations_near(grid, here) -> set[str]`, `start_step(spec, state, grid, at) -> dict`, `finish_step(step, state, grid, at) -> tuple[str, str] | None`.
- Queued step shapes (the planner's vocabulary): `{"kind": "walk", "target": [x, y, z], "reach"?: float, "segments"?: int}`, `{"kind": "mine", "target": [x, y, z]}`, `{"kind": "place", "target": [x, y, z], "block": name}`, `{"kind": "eat", "item": name}`, `{"kind": "craft", "recipe": name}`, `{"kind": "smelt", "item": name}`, `{"kind": "sleep"}`, `{"kind": "wait", "seconds": float}`. Any of them may carry `"thought"`.
- Running step shapes (saved in `state["action"]`, streamed to the viewer): every step has `kind`, `started_at`, `ends_at` (None for sleep). Walks add `path` (from `timed_path`), `target` (point), `reach`, `reached`, `segments`. Mine and place add `target` (point) and `block`. Eat and smelt add `item`; craft adds `recipe`.

`start_step` checks and times a step; `finish_step` applies it at its end. Mining checks the block again at the end (another step may have changed it). Crafting and smelting run the real recipe as a dry run at the start so a missing station or ingredient fails early.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_steps.py`:

```python
import unittest

from backend.survival.grid import Grid
from backend.survival.steps import FOOD, StepFailed, finish_step, mine_seconds, start_step
from backend.survival.vitals import START_VITALS


def small_world(cells=None):
    """Stone at y <= 0 and air above, with `cells` overriding single cells. Mimo stands at (0, 1, 0)."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z), "stone" if y <= 0 else "air"))


def pet(**changes):
    state = {"name": "Pip", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {}, "vitals": dict(START_VITALS)}
    state.update(changes)
    return state


class MiningTimeTests(unittest.TestCase):
    def test_hardness_divided_by_tool_speed(self):
        cases = [("dirt", {}, 0.6), ("dirt", {"iron_pickaxe": 1}, 0.6), ("leaves", {}, 0.3), ("tall_grass", {}, 0.1),
                 ("oak_log", {}, 2.0), ("oak_log", {"wooden_axe": 1}, 1.0), ("cobblestone", {}, 4.0),
                 ("stone", {"wooden_pickaxe": 1}, 2.0), ("stone", {"wooden_pickaxe": 1, "stone_pickaxe": 1}, 1.0),
                 ("iron_ore", {"iron_pickaxe": 1}, 5.0 / 6), ("coal_ore", {"wooden_pickaxe": 0}, 5.0)]
        for material, inventory, seconds in cases:
            self.assertAlmostEqual(mine_seconds(material, inventory), seconds, msg=(material, inventory))
        self.assertIsNone(mine_seconds("bedrock", {"iron_pickaxe": 1}))


class StepTests(unittest.TestCase):
    def test_mining_takes_its_time_and_yields_the_drop(self):
        grid, state = small_world({(1, 1, 0): "oak_log"}), pet()
        step = start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 100.0)
        self.assertEqual((step["ends_at"], step["block"], step["target"]), (102.0, "oak_log", {"x": 1, "y": 1, "z": 0}))
        self.assertIsNone(finish_step(step, state, grid, 102.0))
        self.assertEqual(grid.material(1, 1, 0), "air")
        self.assertEqual(state["inventory"], {"oak_log": 1})

    def test_mining_needs_the_right_tool_and_reach(self):
        grid, state = small_world({(0, 1, 4): "dirt", (0, 1, 5): "dirt"}), pet()
        with self.assertRaisesRegex(StepFailed, "stronger pickaxe"):
            start_step({"kind": "mine", "target": [0, 0, 0]}, state, grid, 0.0)
        self.assertEqual(start_step({"kind": "mine", "target": [0, 1, 4]}, state, grid, 0.0)["ends_at"], 0.6)
        with self.assertRaisesRegex(StepFailed, "out of reach"):
            start_step({"kind": "mine", "target": [0, 1, 5]}, state, grid, 0.0)
        with self.assertRaisesRegex(StepFailed, "cannot be mined"):
            start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 0.0)

    def test_a_block_that_vanished_while_mining_fails(self):
        grid, state = small_world({(1, 1, 0): "dirt"}), pet()
        step = start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 0.0)
        grid.put(1, 1, 0, "air")
        with self.assertRaisesRegex(StepFailed, "is gone"):
            finish_step(step, state, grid, 0.6)
        self.assertEqual(state["inventory"], {})

    def test_placing_takes_a_moment_and_uses_the_item(self):
        grid, state = small_world({(2, 1, 0): "tall_grass"}), pet(inventory={"planks": 2})
        step = start_step({"kind": "place", "target": [1, 1, 0], "block": "planks"}, state, grid, 5.0)
        self.assertEqual(step["ends_at"], 5.3)
        finish_step(step, state, grid, 5.3)
        self.assertEqual(grid.material(1, 1, 0), "planks")
        self.assertEqual(state["inventory"], {"planks": 1})
        start_step({"kind": "place", "target": [2, 1, 0], "block": "planks"}, state, grid, 6.0)  # plants give way
        for target, reason in (([1, 1, 0], "taken"), ([0, 1, 0], "stands"), ([9, 1, 0], "out of reach")):
            with self.assertRaisesRegex(StepFailed, reason):
                start_step({"kind": "place", "target": target, "block": "planks"}, state, grid, 6.0)
        with self.assertRaisesRegex(StepFailed, "no cobblestone"):
            start_step({"kind": "place", "target": [0, 1, 1], "block": "cobblestone"}, state, grid, 6.0)

    def test_eating_restores_hunger(self):
        grid, state = small_world(), pet(inventory={"berries": 2})
        state["vitals"]["hunger"] = 50.0
        step = start_step({"kind": "eat", "item": "berries"}, state, grid, 0.0)
        self.assertEqual(step["ends_at"], 1.6)
        self.assertEqual(finish_step(step, state, grid, 1.6), ("ate", "Pip ate berries."))
        self.assertEqual(state["vitals"]["hunger"], 50.0 + FOOD["berries"])
        self.assertEqual(state["inventory"], {"berries": 1})
        with self.assertRaisesRegex(StepFailed, "not food"):
            start_step({"kind": "eat", "item": "planks"}, state, grid, 2.0)

    def test_crafting_and_smelting_take_one_and_five_seconds_near_their_stations(self):
        grid = small_world()
        state = pet(inventory={"oak_log": 1, "cobblestone": 8, "iron_ore": 1, "coal": 1})
        step = start_step({"kind": "craft", "recipe": "planks"}, state, grid, 0.0)
        self.assertEqual(step["ends_at"], 1.0)
        self.assertEqual(finish_step(step, state, grid, 1.0), ("craft", "Pip crafted planks."))
        self.assertEqual(state["inventory"]["planks"], 4)
        with self.assertRaisesRegex(ValueError, "crafting_table"):
            start_step({"kind": "craft", "recipe": "furnace"}, state, grid, 1.0)
        grid.put(3, 1, 0, "crafting_table")
        grid.put(0, 1, 3, "furnace")
        self.assertEqual(start_step({"kind": "craft", "recipe": "furnace"}, state, grid, 1.0)["ends_at"], 2.0)
        step = start_step({"kind": "smelt", "item": "iron_ore"}, state, grid, 2.0)
        self.assertEqual(step["ends_at"], 7.0)
        self.assertEqual(finish_step(step, state, grid, 7.0), ("smelt", "Pip smelted iron ore."))
        self.assertEqual(state["inventory"]["iron_ingot"], 1)

    def test_walks_carry_a_timed_path(self):
        grid, state = small_world(), pet()
        step = start_step({"kind": "walk", "target": [3, 1, 0]}, state, grid, 10.0)
        self.assertEqual(step["ends_at"], 10.9)
        self.assertEqual([(entry["x"], entry["at"]) for entry in step["path"]],
                         [(0, 10.0), (1, 10.3), (2, 10.6), (3, 10.9)])
        self.assertTrue(step["reached"])
        finish_step(step, state, grid, 10.9)
        self.assertEqual(state["position"], {"x": 3.0, "y": 1.0, "z": 0.0})
        walls = {(dx, dy, dz): "stone" for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)) for dy in (1, 2)}
        with self.assertRaisesRegex(StepFailed, "no way there"):
            start_step({"kind": "walk", "target": [3, 1, 0]}, pet(), small_world(walls), 0.0)

    def test_sleep_has_no_fixed_end_waits_do_and_unknown_steps_fail(self):
        grid, state = small_world(), pet()
        self.assertIsNone(start_step({"kind": "sleep"}, state, grid, 0.0)["ends_at"])
        self.assertEqual(start_step({"kind": "wait", "seconds": 5}, state, grid, 1.0)["ends_at"], 6.0)
        with self.assertRaisesRegex(StepFailed, "unknown step"):
            start_step({"kind": "dance"}, state, grid, 0.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_steps.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.steps'`.

- [ ] **Step 3: Write the step rules**

Create `backend/survival/steps.py`:

```python
"""What each timed step needs, how long it takes and what it changes.

A queued step is a small dict, for example {"kind": "mine", "target": [x, y, z]}. `start_step`
checks it against the world and returns the running step with its start and end times.
`finish_step` applies it at its end time. Both raise StepFailed (a ValueError) with a short
reason; crafting errors from backend.services.crafting are ValueErrors too.
"""

from __future__ import annotations

import math

from backend.services.blocks import hardness, is_replaceable, mining_tool
from backend.services.crafting import BLOCKS, add_item, can_harvest, craft, smelt, take_items
from backend.survival.grid import Cell, Grid
from backend.survival.pathing import route, timed_path

REACH = 4.0
STATION_REACH = 6.0
WORKSTATIONS = ("crafting_table", "furnace")
PLACE_SECONDS = 0.3
EAT_SECONDS = 1.6
CRAFT_SECONDS = 1.0
SMELT_SECONDS = 5.0
PICKAXE_SPEED = {"wooden_pickaxe": 2.0, "stone_pickaxe": 4.0, "iron_pickaxe": 6.0}
# Axe recipes arrive with purposeful building (M5). Any axe doubles the speed on wood.
AXES = ("wooden_axe", "stone_axe", "iron_axe")
AXE_SPEED = 2.0
# Hunger each food restores (spec section 7). The food items themselves arrive in M4.
FOOD = {"berries": 8.0, "brown_mushroom": 6.0, "carrot": 10.0, "bread": 25.0, "raw_fish": 8.0, "cooked_fish": 30.0}
# A far walk re-plans segment by segment; after this many extra segments it gives up.
MAX_SEGMENTS = 12


class StepFailed(ValueError):
    """A step cannot start or finish. The message says why."""


def as_cell(value) -> Cell:
    """A cell from [x, y, z] (queued steps) or {"x", "y", "z"} (running steps, paths and positions)."""
    if isinstance(value, dict):
        return round(value["x"]), round(value["y"]), round(value["z"])
    x, y, z = value
    return int(x), int(y), int(z)


def as_point(cell) -> dict:
    x, y, z = as_cell(cell)
    return {"x": x, "y": y, "z": z}


def position_of(point: dict) -> dict:
    """A state position (floats, as M1 stores it) from a path entry or point."""
    return {"x": float(point["x"]), "y": float(point["y"]), "z": float(point["z"])}


def label(name: str) -> str:
    return name.replace("_", " ")


def tool_speed(material: str, inventory: dict[str, int]) -> float:
    """How much faster than a bare hand Mimo mines `material` with what it carries."""
    owned = {item for item, amount in inventory.items() if amount > 0}
    tool = mining_tool(material)
    if tool == "pickaxe":
        return max((PICKAXE_SPEED[item] for item in owned if item in PICKAXE_SPEED), default=1.0)
    if tool == "axe" and owned.intersection(AXES):
        return AXE_SPEED
    return 1.0


def mine_seconds(material: str, inventory: dict[str, int]) -> float | None:
    """Hardness divided by tool speed, or None for blocks that cannot be mined."""
    seconds = hardness(material)
    return None if seconds is None else seconds / tool_speed(material, inventory)


def in_reach(here: Cell, target: Cell) -> bool:
    return math.dist(here, target) <= REACH


def stations_near(grid: Grid, here: Cell) -> set[str]:
    return grid.placed_near(here[0], here[2], STATION_REACH, WORKSTATIONS)


def start_step(spec: dict, state: dict, grid: Grid, at: float) -> dict:
    """Check a queued step against the world and return it running, from `at` to its end time."""
    kind = spec.get("kind")
    here = as_cell(state["position"])
    inventory = state["inventory"]
    if kind == "walk":
        target = as_cell(spec["target"])
        reach = float(spec.get("reach", 0.0))
        segments = int(spec.get("segments", 0))
        if segments > MAX_SEGMENTS:
            raise StepFailed("no way there")
        cells, reached = route(grid, here, target, reach)
        if not cells and not reached:
            raise StepFailed("no way there")
        path = timed_path(grid, here, cells, at)
        return {"kind": "walk", "started_at": at, "ends_at": path[-1]["at"], "path": path,
                "target": as_point(target), "reach": reach, "reached": reached, "segments": segments}
    if kind == "mine":
        target = as_cell(spec["target"])
        if not in_reach(here, target):
            raise StepFailed("out of reach")
        material = grid.material(*target)
        seconds = mine_seconds(material, inventory)
        if seconds is None:
            raise StepFailed(f"{label(material)} cannot be mined")
        if not can_harvest(material, inventory):
            raise StepFailed(f"a stronger pickaxe is needed for {label(material)}")
        return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds, 3),
                "target": as_point(target), "block": material}
    if kind == "place":
        target, block = as_cell(spec["target"]), spec["block"]
        if inventory.get(block, 0) < 1:
            raise StepFailed(f"no {label(block)} to place")
        if block not in BLOCKS:
            raise StepFailed(f"{label(block)} is not a block")
        if not in_reach(here, target):
            raise StepFailed("out of reach")
        if target == here:
            raise StepFailed("that is where it stands")
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken")
        return {"kind": "place", "started_at": at, "ends_at": round(at + PLACE_SECONDS, 3),
                "target": as_point(target), "block": block}
    if kind == "eat":
        item = spec["item"]
        if item not in FOOD:
            raise StepFailed(f"{label(item)} is not food")
        if inventory.get(item, 0) < 1:
            raise StepFailed(f"no {label(item)} to eat")
        return {"kind": "eat", "started_at": at, "ends_at": round(at + EAT_SECONDS, 3), "item": item}
    if kind == "craft":
        craft(inventory, spec["recipe"], stations_near(grid, here))
        return {"kind": "craft", "started_at": at, "ends_at": round(at + CRAFT_SECONDS, 3), "recipe": spec["recipe"]}
    if kind == "smelt":
        smelt(inventory, spec["item"], stations_near(grid, here))
        return {"kind": "smelt", "started_at": at, "ends_at": round(at + SMELT_SECONDS, 3), "item": spec["item"]}
    if kind == "sleep":
        # Sleep has no fixed end: actions.py ends it once Mimo is rested and it is not night.
        return {"kind": "sleep", "started_at": at, "ends_at": None}
    if kind == "wait":
        seconds = float(spec.get("seconds", 1.0))
        if seconds <= 0:
            raise StepFailed("a wait needs some time")
        return {"kind": "wait", "started_at": at, "ends_at": round(at + seconds, 3)}
    raise StepFailed(f"unknown step {kind!r}")


def finish_step(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str] | None:
    """Apply a running step at its end. Returns an event (kind, text) worth logging, if any."""
    kind, name = step["kind"], state["name"]
    if kind == "walk":
        state["position"] = position_of(step["path"][-1])
        return None
    if kind == "mine":
        target = as_cell(step["target"])
        if grid.material(*target) != step["block"]:
            raise StepFailed(f"the {label(step['block'])} is gone")
        grid.put(*target, "air")
        drop = BLOCKS.get(step["block"], {}).get("drop")
        if drop:
            add_item(state["inventory"], drop)
        return None
    if kind == "place":
        target = as_cell(step["target"])
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken")
        state["inventory"] = take_items(state["inventory"], {step["block"]: 1})
        grid.put(*target, step["block"])
        return None
    if kind == "eat":
        state["inventory"] = take_items(state["inventory"], {step["item"]: 1})
        state["vitals"]["hunger"] = min(100.0, state["vitals"]["hunger"] + FOOD[step["item"]])
        return "ate", f"{name} ate {label(step['item'])}."
    if kind == "craft":
        stations = stations_near(grid, as_cell(state["position"]))
        state["inventory"] = craft(state["inventory"], step["recipe"], stations)
        return "craft", f"{name} crafted {label(step['recipe'])}."
    if kind == "smelt":
        stations = stations_near(grid, as_cell(state["position"]))
        state["inventory"] = smelt(state["inventory"], step["item"], stations)
        return "smelt", f"{name} smelted {label(step['item'])}."
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_steps.py"`
Expected: `Ran 9 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 168 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/steps.py backend/tests/test_survival_steps.py
git commit -m "feat: add timed step rules for walking, mining, placing and more" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The action engine with falls and swimming up

**Files:**
- Create: `backend/survival/actions.py`
- Test: `backend/tests/test_survival_actions.py`

**Interfaces:**
- Consumes: `is_night` (M1 clock); `WORLD_MIN_Y` (worldgen); `Grid`, `Cell` (Task 2); `SWIM_SECONDS` (Task 3); `as_cell`, `as_point`, `position_of`, `start_step`, `finish_step` (Task 4).
- Produces (`backend.survival.actions`): `RECENT_LIMIT = 20`, `MAX_STEPS_PER_ADVANCE = 1000`, `GRAVITY = 32.0`, `SAFE_FALL = 3`, `FALL_DAMAGE = 10.0`, `WAKE_ENERGY = 95.0`, `WORKING`, `STATUS`, `Event = tuple[float, str, str]`, `Planner = Callable[[dict, Grid, float, dict], list[dict]]` (arguments: state, grid, time, the game clock dict at that time), `ActionContext(grid, clock_at, planner, events)` (dataclass; `clock_at(real_time) -> clock dict`), `ensure_actions(state)`, `activity_of(state) -> str` (`idle`, `working` or `sleeping`), `advance_actions(state, context, until) -> float | None` (the time a fall killed Mimo, or None).
- State keys it owns: `action` (running step or None), `queue` (queued step dicts), `recent_actions` (finished steps: `kind`, `started_at`, `ended_at`, `result` `"done"`/`"failed"`, and when present `target`, `block`, `item`, `recipe`, `reason`), `actions_at` (the time actions were last advanced to). It also sets `status`, `position`, `last_thought`, `inventory`, `vitals.hunger` (eating) and `vitals.health` (falls).
- Hazard steps it creates itself: `{"kind": "fall", "started_at", "ends_at", "blocks", "path": [start, landing]}` and `{"kind": "swim", "started_at", "ends_at", "path": [...]}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_actions.py`:

```python
import math
import unittest

from backend.survival.actions import ActionContext, activity_of, advance_actions, ensure_actions
from backend.survival.grid import Grid
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}


def small_world(cells=None, floor="stone"):
    """`floor` at y <= 0 and air above, with `cells` overriding single cells."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or (floor if y <= 0 else "air"))


def pet(position=(0, 1, 0), **changes):
    state = {"name": "Pip", "position": {"x": float(position[0]), "y": float(position[1]), "z": float(position[2])},
             "inventory": {}, "vitals": dict(START_VITALS), "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


class Plans:
    """A planner that hands out prepared plans in order and counts how often it was asked."""

    def __init__(self, *plans):
        self.plans = list(plans)
        self.calls = 0

    def __call__(self, state, grid, at, clock):
        self.calls += 1
        return self.plans.pop(0) if self.plans else []


def context(grid, planner=None, clock=None):
    return ActionContext(grid=grid, clock_at=clock or (lambda at: DAY), planner=planner or Plans(), events=[])


class ActionEngineTests(unittest.TestCase):
    def test_several_steps_can_finish_in_one_advance(self):
        grid, state = small_world(), pet(inventory={"planks": 2})
        state["queue"] = [{"kind": "place", "target": [1, 1, 0], "block": "planks"},
                          {"kind": "place", "target": [0, 1, 1], "block": "planks"},
                          {"kind": "wait", "seconds": 5}]
        advance_actions(state, context(grid), 1.0)
        self.assertEqual([(entry["kind"], entry["ended_at"]) for entry in state["recent_actions"]],
                         [("place", 0.3), ("place", 0.6)])
        self.assertEqual((grid.material(1, 1, 0), grid.material(0, 1, 1)), ("planks", "planks"))
        self.assertEqual(state["inventory"], {})
        self.assertEqual((state["action"]["kind"], state["action"]["ends_at"]), ("wait", 5.6))
        self.assertEqual(state["status"], "idle")

    def test_a_walk_moves_mimo_cell_by_cell(self):
        grid, state = small_world(), pet()
        state["queue"] = [{"kind": "walk", "target": [5, 1, 0]}]
        ctx = context(grid)
        advance_actions(state, ctx, 0.7)
        self.assertEqual(state["position"]["x"], 2.0)
        self.assertEqual((state["status"], activity_of(state)), ("walking", "working"))
        advance_actions(state, ctx, 2.0)
        self.assertEqual(state["position"], {"x": 5.0, "y": 1.0, "z": 0.0})
        self.assertEqual(state["recent_actions"][-1]["kind"], "walk")
        self.assertEqual((state["status"], activity_of(state)), ("idle", "idle"))

    def test_the_planner_fills_an_empty_queue(self):
        planner = Plans([{"kind": "wait", "seconds": 2}], [{"kind": "wait", "seconds": 2}],
                        [{"kind": "wait", "seconds": 2}])
        state = pet()
        advance_actions(state, context(small_world(), planner), 5.0)
        self.assertEqual(planner.calls, 3)
        self.assertEqual(state["action"]["ends_at"], 6.0)
        self.assertEqual(state["recent_actions"], [])

    def test_a_failed_step_is_recorded_and_clears_the_plan(self):
        state = pet()
        state["queue"] = [{"kind": "mine", "target": [9, 1, 0]}, {"kind": "wait", "seconds": 1}]
        advance_actions(state, context(small_world({(9, 1, 0): "dirt"})), 1.0)
        failed = state["recent_actions"][-1]
        self.assertEqual((failed["kind"], failed["result"], failed["reason"]), ("mine", "failed", "out of reach"))
        self.assertEqual(failed["target"], {"x": 9, "y": 1, "z": 0})
        self.assertEqual((state["action"], state["queue"]), (None, []))

    def test_digging_out_the_floor_drops_mimo_and_long_falls_hurt(self):
        grid, state = small_world({(0, 8, 0): "dirt"}), pet(position=(0, 9, 0))
        state["queue"] = [{"kind": "mine", "target": [0, 8, 0]}]
        ctx = context(grid)
        self.assertIsNone(advance_actions(state, ctx, 3.0))
        self.assertEqual(state["position"], {"x": 0.0, "y": 1.0, "z": 0.0})
        self.assertEqual(state["vitals"]["health"], 50.0)
        fall = state["recent_actions"][-1]
        self.assertEqual((fall["kind"], fall["ended_at"]), ("fall", round(0.6 + math.sqrt(16 / 32), 3)))
        self.assertEqual(ctx.events[-1][1:], ("fall", "Pip fell 8 blocks and got hurt."))

    def test_falls_of_three_or_into_water_do_not_hurt(self):
        state = pet(position=(0, 4, 0))
        advance_actions(state, context(small_world()), 2.0)
        self.assertEqual((state["position"]["y"], state["vitals"]["health"]), (1.0, 100.0))
        state = pet(position=(0, 20, 0))
        advance_actions(state, context(small_world(floor="water")), 3.0)
        self.assertEqual((state["position"]["y"], state["vitals"]["health"]), (1.0, 100.0))

    def test_a_long_fall_can_kill(self):
        state = pet(position=(0, 12, 0))
        state["vitals"]["health"] = 30.0
        died_at = advance_actions(state, context(small_world()), 5.0)
        self.assertEqual(died_at, round(math.sqrt(2 * 11 / 32), 3))
        self.assertEqual(state["vitals"]["health"], 0.0)

    def test_mimo_swims_up_when_its_cell_is_water(self):
        column = {(0, 1, 0): "water", (0, 2, 0): "water", (0, 3, 0): "water"}
        state = pet()
        ctx = context(small_world(column))
        advance_actions(state, ctx, 1.0)
        self.assertEqual(state["action"]["kind"], "swim")
        self.assertEqual([entry["y"] for entry in state["action"]["path"]], [1, 2, 3, 4])
        self.assertEqual(state["action"]["ends_at"], 2.7)
        self.assertEqual((state["position"]["y"], state["status"], activity_of(state)), (2.0, "swimming", "working"))
        advance_actions(state, ctx, 3.0)
        self.assertEqual((state["position"]["y"], state["status"]), (4.0, "idle"))

    def test_sleep_lasts_until_rested_and_daylight(self):
        planner = Plans([{"kind": "sleep", "thought": "Sleepy."}])
        state = pet()
        state["vitals"]["energy"] = 50.0
        ctx = context(small_world(), planner, clock=lambda at: NIGHT if at < 100 else DAY)
        advance_actions(state, ctx, 10.0)
        self.assertEqual((state["status"], activity_of(state), state["last_thought"]), ("sleeping", "sleeping", "Sleepy."))
        state["vitals"]["energy"] = 99.0
        advance_actions(state, ctx, 60.0)
        self.assertEqual(state["status"], "sleeping")
        advance_actions(state, ctx, 120.0)
        self.assertEqual(state["status"], "idle")
        self.assertEqual([event[1] for event in ctx.events], ["sleep", "wake"])
        self.assertEqual(state["recent_actions"][-1]["ended_at"], 120.0)

    def test_far_walks_continue_segment_by_segment(self):
        state = pet()
        state["queue"] = [{"kind": "walk", "target": [200, 1, 0]}]
        ctx = context(small_world())
        advance_actions(state, ctx, 0.0)
        first = state["action"]
        self.assertFalse(first["reached"])
        advance_actions(state, ctx, first["ends_at"])
        self.assertEqual((state["action"]["kind"], state["action"]["started_at"]), ("walk", first["ends_at"]))
        advance_actions(state, ctx, 100.0)
        self.assertEqual(state["position"], {"x": 200.0, "y": 1.0, "z": 0.0})

    def test_a_walk_stops_where_its_path_became_blocked(self):
        grid, state = small_world(), pet()
        state["queue"] = [{"kind": "walk", "target": [5, 1, 0]}]
        ctx = context(grid)
        advance_actions(state, ctx, 0.4)
        grid.put(3, 1, 0, "planks")
        advance_actions(state, ctx, 2.0)
        self.assertEqual(state["position"]["x"], 2.0)
        self.assertEqual(state["recent_actions"][-1]["reason"], "path blocked")
        self.assertIsNone(state["action"])

    def test_states_saved_before_actions_get_the_new_fields(self):
        state = {"last_tick_at": 42.0}
        ensure_actions(state)
        self.assertEqual(state, {"last_tick_at": 42.0, "action": None, "queue": [], "recent_actions": [],
                                 "actions_at": 42.0})

    def test_only_the_last_twenty_steps_are_kept_and_waits_are_left_out(self):
        state = pet(inventory={"berries": 25})
        state["queue"] = [{"kind": "eat", "item": "berries"} for _ in range(25)] + [{"kind": "wait", "seconds": 1}]
        ctx = context(small_world())
        advance_actions(state, ctx, 50.0)
        self.assertEqual(len(state["recent_actions"]), 20)
        self.assertEqual({entry["kind"] for entry in state["recent_actions"]}, {"eat"})
        self.assertEqual(len(ctx.events), 25)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_actions.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.actions'`.

- [ ] **Step 3: Write the engine**

Create `backend/survival/actions.py`:

```python
"""Mimo's timed actions: the step it is doing, the steps queued after it and the last finished ones.

`advance_actions` brings the actions up to a moment in time. Every step that ends by then
finishes in order, so several short steps can finish in one tick, and each next step starts the
moment the one before it ended. When the queue is empty the planner is asked for more steps.
Before a new step starts, two hazards come first: Mimo falls when nothing holds it up
((blocks - 3) x 10 damage, none when it lands on water), and it swims straight up when its cell
is water (a fallback until the brain's surface reflex in M3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from backend.services.worldgen import WORLD_MIN_Y
from backend.survival.clock import is_night
from backend.survival.grid import Cell, Grid
from backend.survival.pathing import SWIM_SECONDS
from backend.survival.steps import as_cell, as_point, finish_step, position_of, start_step

RECENT_LIMIT = 20
MAX_STEPS_PER_ADVANCE = 1000
GRAVITY = 32.0  # blocks per second squared: a fall of b blocks takes sqrt(2 b / GRAVITY) seconds
SAFE_FALL = 3
FALL_DAMAGE = 10.0
WAKE_ENERGY = 95.0
WORKING = frozenset({"walk", "swim", "mine", "place"})
STATUS = {"walk": "walking", "swim": "swimming", "fall": "falling", "mine": "mining", "place": "building",
          "eat": "eating", "craft": "crafting", "smelt": "smelting", "sleep": "sleeping", "wait": "idle"}
# Waits tell the viewer nothing and would push real steps out of the recent list.
UNRECORDED = frozenset({"wait"})
RECORDED_FIELDS = ("kind", "started_at", "target", "block", "item", "recipe")

Event = tuple[float, str, str]
Planner = Callable[[dict, Grid, float, dict], list[dict]]


@dataclass
class ActionContext:
    """What advance_actions needs besides the state: the world, the game clock, a planner, an event list."""

    grid: Grid
    clock_at: Callable[[float], dict]
    planner: Planner
    events: list[Event]


def ensure_actions(state: dict) -> None:
    """Give a state saved before actions existed (an M1 world) its action fields."""
    state.setdefault("action", None)
    state.setdefault("queue", [])
    state.setdefault("recent_actions", [])
    state.setdefault("actions_at", state["last_tick_at"])


def activity_of(state: dict) -> str:
    """The vitals activity of the current step: sleeping, working (walk, swim, mine, place) or idle."""
    action = state.get("action")
    if action is None:
        return "idle"
    if action["kind"] == "sleep":
        return "sleeping"
    return "working" if action["kind"] in WORKING else "idle"


def record(state: dict, step: dict, ended_at: float, result: str, reason: str | None = None) -> None:
    if step["kind"] in UNRECORDED:
        return
    entry = {key: step[key] for key in RECORDED_FIELDS if key in step}
    entry.update(ended_at=ended_at, result=result)
    if reason:
        entry["reason"] = reason
    state["recent_actions"] = [*state["recent_actions"], entry][-RECENT_LIMIT:]


def fail(state: dict, step: dict, at: float, reason: str) -> None:
    """Record a failed step and drop the rest of the plan, so the planner plans again."""
    record(state, step, at, "failed", reason)
    state["action"] = None
    state["queue"] = []


def as_started(spec: dict, at: float) -> dict:
    """A queued step in the shape of a started one, to record a step that could not start."""
    step = {key: spec[key] for key in ("block", "item", "recipe") if key in spec}
    step.update(kind=spec.get("kind", "unknown"), started_at=at)
    if "target" in spec:
        step["target"] = as_point(spec["target"])
    return step


def landing(grid: Grid, cell: Cell) -> Cell:
    """The first cell at or below `cell` where something holds Mimo up."""
    x, y, z = cell
    while not grid.supported((x, y, z)) and y > WORLD_MIN_Y:
        y -= 1
    return x, y, z


def start_hazard(state: dict, grid: Grid, at: float) -> bool:
    """Start a swim up or a fall when Mimo's cell calls for one. Returns True when one started."""
    here = as_cell(state["position"])
    if grid.water(here):
        x, y, z = here
        path = [{**as_point(here), "at": at}]
        while grid.water((x, y, z)) and not grid.solid((x, y + 1, z)):
            y += 1
            path.append({**as_point((x, y, z)), "at": round(path[-1]["at"] + SWIM_SECONDS, 3), "swim": True})
        if len(path) == 1:
            return False  # a ceiling holds Mimo under; air keeps draining
        state["action"] = {"kind": "swim", "started_at": at, "ends_at": path[-1]["at"], "path": path}
    elif grid.supported(here):
        return False
    else:
        land = landing(grid, here)
        blocks = here[1] - land[1]
        ends_at = round(at + math.sqrt(2 * blocks / GRAVITY), 3)
        state["action"] = {"kind": "fall", "started_at": at, "ends_at": ends_at, "blocks": blocks,
                           "path": [{**as_point(here), "at": at}, {**as_point(land), "at": ends_at}]}
    state["queue"] = []
    return True


def finish_fall(state: dict, step: dict, grid: Grid, at: float, events: list[Event]) -> bool:
    """Land. Returns True when the landing killed Mimo."""
    spot = step["path"][-1]
    state["position"] = position_of(spot)
    if grid.water((spot["x"], spot["y"] - 1, spot["z"])):
        return False
    damage = max(0, step["blocks"] - SAFE_FALL) * FALL_DAMAGE
    if damage == 0:
        return False
    state["vitals"]["health"] = max(0.0, state["vitals"]["health"] - damage)
    state["last_thought"] = "Ouch! That was a long way down."
    events.append((at, "fall", f"{state['name']} fell {step['blocks']} blocks and got hurt."))
    return state["vitals"]["health"] <= 0


def follow_path(state: dict, step: dict, grid: Grid, until: float) -> bool:
    """Move Mimo to the last path cell reached by `until`. False when a cell ahead turned solid."""
    for entry in step["path"][1:]:
        if entry["at"] > until:
            break
        if grid.solid(as_cell(entry)):
            return False
        state["position"] = position_of(entry)
    return True


def step_end(step: dict, state: dict, context: ActionContext, until: float) -> float | None:
    """When the running step ends, or None while it still runs at `until`."""
    if step["kind"] == "sleep":
        rested = state["vitals"]["energy"] >= WAKE_ENERGY
        return until if rested and not is_night(context.clock_at(until)["phase"]) else None
    return step["ends_at"] if step["ends_at"] <= until else None


def begin(state: dict, spec: dict, at: float, events: list[Event]) -> None:
    if spec.get("thought"):
        state["last_thought"] = spec["thought"]
    if spec["kind"] == "sleep":
        events.append((at, "sleep", f"{state['name']} fell asleep."))


def finish(state: dict, step: dict, context: ActionContext, at: float) -> bool:
    """Apply a step that ended at `at`. Returns True when it killed Mimo."""
    grid, events = context.grid, context.events
    if step["kind"] == "fall":
        record(state, step, at, "done")
        return finish_fall(state, step, grid, at, events)
    if step["kind"] == "swim":
        state["position"] = position_of(step["path"][-1])
        record(state, step, at, "done")
        return False
    try:
        event = finish_step(step, state, grid, at)
    except (ValueError, KeyError) as error:
        fail(state, step, at, str(error))
        return False
    record(state, step, at, "done")
    if event:
        events.append((at, *event))
    if step["kind"] == "sleep":
        state["last_thought"] = "Good morning. I feel rested."
        events.append((at, "wake", f"{state['name']} woke up."))
    if step["kind"] == "walk" and not step["reached"]:
        target = step["target"]
        state["queue"].insert(0, {"kind": "walk", "target": [target["x"], target["y"], target["z"]],
                                  "reach": step["reach"], "segments": step["segments"] + 1})
    return False


def advance_actions(state: dict, context: ActionContext, until: float) -> float | None:
    """Run Mimo's actions up to `until`. Returns the time a fall killed Mimo, or None."""
    ensure_actions(state)
    grid = context.grid
    at = min(state["actions_at"], until)
    for _ in range(MAX_STEPS_PER_ADVANCE):
        step = state["action"]
        if step is None:
            if start_hazard(state, grid, at):
                continue
            if not state["queue"]:
                state["queue"] = list(context.planner(state, grid, at, context.clock_at(at)))
                if not state["queue"]:
                    break
            spec = state["queue"].pop(0)
            try:
                state["action"] = start_step(spec, state, grid, at)
            except (ValueError, KeyError) as error:
                fail(state, as_started(spec, at), at, str(error))
                break  # plan again at the next advance, not in a tight loop
            begin(state, spec, at, context.events)
            continue
        if step["kind"] in ("walk", "swim") and not follow_path(state, step, grid, until):
            fail(state, step, until, "path blocked")
            at = until
            continue
        end = step_end(step, state, context, until)
        if end is None:
            break
        state["action"] = None
        at = end
        if finish(state, step, context, end):
            return end
    state["actions_at"] = until
    action = state["action"]
    state["status"] = STATUS.get(action["kind"], "idle") if action else "idle"
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_actions.py"`
Expected: `Ran 13 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 181 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/actions.py backend/tests/test_survival_actions.py
git commit -m "feat: run timed actions with falls and a swim-up fallback" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Interim plan and actions in the survival tick

**Files:**
- Create: `backend/survival/script.py`
- Rewrite: `backend/survival/tick.py`
- Modify: `backend/workers/mimo_worker.py` (imports, a constant, `run_once`, one line in `main`)
- Test: `backend/tests/test_survival_script.py`, `backend/tests/test_survival_tick_actions.py` (M1's `test_survival_tick.py` and `test_survival_worker.py` must keep passing unchanged)

**Interfaces:**
- Consumes: `is_night`, `clock_at`, `time_scale`, `DAY_SECONDS` (M1 clock); `EXHAUSTED_BELOW`, `step_vitals`, `Surroundings` and shelter helpers (M1 vitals); `terrain_height`, `trees_in_chunk`, `biome_at` (worldgen); M1 world, registry and tick names; `world_grid` (Task 2); `as_cell` (Task 4); `ActionContext`, `Planner`, `activity_of`, `advance_actions`, `ensure_actions` (Task 5).
- Produces (`backend.survival.script`, replaced by M3): `rest_plan(state, grid, at, clock) -> list[dict]`, `scripted_plan(state, grid, at, clock) -> list[dict]`, `trees_near(seed, x, z, radius) -> list[tuple[int, int, int]]`, `standing_logs(grid, state) -> list[Cell]`, `wander_target(state, clock) -> list[int]`, constants `TREE_SEARCH = 24`, `STAND_REACH = 2.0`, `WANDER_DISTANCE = 48`, `WANDER_REACH = 3.0`.
- Produces (`backend.survival.tick`): `advance_world(world, timestamp, scale, planner=rest_plan) -> dict`, `tick_life(registry, timestamp=None, scale=None, planner=rest_plan) -> dict | None`, `record_death(state, cause, at, scale, events)`; keeps `MAX_STEP_SECONDS`, `surroundings_at`, `note_crossings`, `CAUSE_TEXT`. M1's `update_sleep` and `WAKE_ENERGY` are removed (sleep is now a step; `WAKE_ENERGY` lives in `actions`).
- Produces (`backend.workers.mimo_worker`): `WORKER_PLANNER = scripted_plan`, `run_once(registry, previous, timestamp=None, planner=rest_plan) -> str`.

`rest_plan` is M1's interim sleep rule as steps, so every M1 tick, API and worker test keeps its meaning: an idle pet waits (status `idle`, activity idle) and sleeps at night or when exhausted. Each catch-up step now runs `advance_actions` up to its start, then computes surroundings at the current position and advances vitals with `activity_of(state)`. After the loop, actions are advanced to the tick's timestamp. A fatal fall ends the life with cause `fall`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_script.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival.actions import ensure_actions
from backend.survival.grid import Grid
from backend.survival.script import rest_plan, scripted_plan
from backend.survival.vitals import START_VITALS

MORNING = {"phase": "day", "seconds_into_day": 1200.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}
TREE = (5, 0, 0)  # trunk x, trunk z, ground height: logs at y 1 to 4
NO_TREES_THOUGHT = "No trees here. I'll look further out."


def forest(cells=None):
    """Flat stone with one oak trunk at x=5, z=0 (logs at y 1 to 4), with `cells` overriding single cells."""
    cells = cells or {}

    def rule(x, y, z):
        if (x, y, z) in cells:
            return cells[(x, y, z)]
        if (x, z) == (5, 0) and 1 <= y <= 4:
            return "oak_log"
        return "stone" if y <= 0 else "air"

    return Grid(rule)


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


class RestPlanTests(unittest.TestCase):
    def test_sleeps_at_night_or_when_exhausted(self):
        self.assertEqual(rest_plan(pet(), forest(), 0.0, NIGHT),
                         [{"kind": "sleep", "thought": "It's dark. Time to curl up and sleep."}])
        tired = pet(vitals={**START_VITALS, "energy": 5.0})
        self.assertEqual(rest_plan(tired, forest(), 0.0, MORNING)[0]["thought"], "I'm too tired to keep my eyes open.")

    def test_waits_for_nightfall_at_most_a_minute_at_a_time(self):
        self.assertEqual(rest_plan(pet(), forest(), 0.0, MORNING), [{"kind": "wait", "seconds": 60.0}])
        dusk = {**MORNING, "phase": "dusk", "seconds_into_day": 2390.0}
        self.assertEqual(rest_plan(pet(), forest(), 0.0, dusk)[0]["seconds"], 10.0)
        fast = {**MORNING, "seconds_into_day": 2399.5, "time_scale": 60.0}
        self.assertEqual(rest_plan(pet(), forest(), 0.0, fast)[0]["seconds"], 1.0)


@patch("backend.survival.script.trees_near", lambda seed, x, z, radius: [TREE])
class ScriptedPlanTests(unittest.TestCase):
    def test_walks_to_the_nearest_tree_and_chops_it_bottom_up(self):
        plan = scripted_plan(pet(), forest(), 0.0, MORNING)
        self.assertEqual(plan[0], {"kind": "walk", "target": [5, 1, 0], "reach": 2.0,
                                   "thought": "That tree has good wood."})
        self.assertEqual([step["target"] for step in plan[1:]], [[5, 1, 0], [5, 2, 0], [5, 3, 0], [5, 4, 0]])
        self.assertEqual({step["kind"] for step in plan[1:]}, {"mine"})

    def test_logs_become_planks_before_more_chopping(self):
        plan = scripted_plan(pet(inventory={"oak_log": 2}), forest(), 0.0, MORNING)
        self.assertEqual(plan, [{"kind": "craft", "recipe": "planks", "thought": "Logs make good planks."}])

    def test_skips_chopped_logs_and_trees_where_a_step_failed(self):
        chopped = forest({(5, 1, 0): "air", (5, 2, 0): "air"})
        self.assertEqual([step["target"] for step in scripted_plan(pet(), chopped, 0.0, MORNING)[1:]],
                         [[5, 3, 0], [5, 4, 0]])
        failed = pet()
        failed["recent_actions"] = [{"kind": "walk", "started_at": 0.0, "ended_at": 0.0, "result": "failed",
                                     "target": {"x": 5, "y": 1, "z": 0}, "reason": "no way there"}]
        self.assertEqual(scripted_plan(failed, forest(), 0.0, MORNING)[0]["thought"], NO_TREES_THOUGHT)

    def test_sleep_comes_first_at_night(self):
        self.assertEqual(scripted_plan(pet(), forest(), 0.0, NIGHT)[0]["kind"], "sleep")

    def test_without_trees_it_walks_out_in_the_day_s_direction(self):
        with patch("backend.survival.script.trees_near", lambda seed, x, z, radius: []), \
                patch("backend.survival.script.terrain_height", lambda x, z, seed: 0):
            plan = scripted_plan(pet(), forest(), 0.0, {**MORNING, "day_number": 2})
        self.assertEqual(plan, [{"kind": "walk", "target": [-48, 1, 0], "reach": 3.0, "thought": NO_TREES_THOUGHT}])


if __name__ == "__main__":
    unittest.main()
```

Create `backend/tests/test_survival_tick_actions.py`:

```python
import random
import tempfile
import unittest
from pathlib import Path

from backend.services.worldgen import terrain_height
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.script import scripted_plan
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.workers import mimo_worker

BORN = 1_000_000.0


class TickActionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.registry = LifeRegistry(self.root / "data", self.root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def edit(self, **changes):
        with self.world.transaction() as db:
            state = read_state(db)
            state.update(changes)
            write_state(db, state)

    def spawn_column(self):
        position = self.world.state()["position"]
        return round(position["x"]), round(position["z"])

    def test_one_tick_can_walk_chop_and_craft(self):
        state = tick_life(self.registry, BORN + 120, scale=1, planner=scripted_plan)
        self.assertIsNone(state["died_at"])
        self.assertGreaterEqual(state["inventory"].get("planks", 0), 4)
        self.assertIn("air", [change["material"] for change in self.world.blocks_since(0)["changes"]])
        self.assertIn("craft", [event["kind"] for event in self.world.events(50)])

    def test_a_restarted_worker_resumes_a_stored_walk(self):
        x, z = self.spawn_column()
        path = [{"x": x + step, "y": 100, "z": z, "at": BORN + 0.3 * step} for step in range(4)]
        self.edit(position={"x": float(x), "y": 100.0, "z": float(z)}, queue=[], recent_actions=[], actions_at=BORN,
                  action={"kind": "walk", "started_at": BORN, "ends_at": path[-1]["at"], "path": path,
                          "target": {"x": x + 3, "y": 100, "z": z}, "reach": 0.0, "reached": True, "segments": 0})
        restarted = LifeRegistry(self.root / "data", self.root / "no-legacy.sqlite3")
        state = tick_life(restarted, BORN + 0.5, scale=1)
        self.assertEqual(state["action"]["started_at"], BORN)
        self.assertEqual(state["position"], {"x": float(x + 1), "y": 100.0, "z": float(z)})
        self.assertEqual(state["status"], "walking")

    def test_a_long_fall_kills_and_archives_the_life(self):
        x, z = self.spawn_column()
        self.edit(position={"x": float(x), "y": float(terrain_height(x, z, self.world.seed) + 40), "z": float(z)})
        state = tick_life(self.registry, BORN + 5, scale=1)
        self.assertEqual((state["status"], state["cause"]), ("dead", "fall"))
        self.assertLess(state["died_at"], BORN + 3)
        self.assertIsNone(state["action"])
        self.assertEqual(self.registry.get(self.life["id"])["cause"], "fall")
        self.assertIn("died of a fall on day 1", self.world.events()[0]["text"])

    def test_night_sleep_is_a_step_without_an_end(self):
        state = tick_life(self.registry, BORN + 2450, scale=1)
        self.assertEqual((state["action"]["kind"], state["action"]["ends_at"]), ("sleep", None))

    def test_the_worker_runs_the_interim_script(self):
        self.assertIs(mimo_worker.WORKER_PLANNER, scripted_plan)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_script.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.script'`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_tick_actions.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.script'`.

- [ ] **Step 3: Write the interim plan**

Create `backend/survival/script.py`:

```python
"""A stand-in plan until the brain arrives. M3 replaces this module with purposes and a planner.

rest_plan is M1's rule as steps: sleep at night or when exhausted, otherwise wait for nightfall.
scripted_plan gives Mimo something to do by day: walk to the nearest tree within 24 blocks,
chop its logs from the bottom up and craft them into planks, and walk out to look for more
trees when none is near.
"""

from __future__ import annotations

import math

from backend.services.worldgen import terrain_height, trees_in_chunk
from backend.survival.clock import is_night
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.steps import as_cell
from backend.survival.vitals import EXHAUSTED_BELOW

NIGHTFALL = 2400.0
MAX_WAIT = 60.0
TREE_SEARCH = 24
TRUNK_HEIGHT = 4
LOG = "oak_log"
# Close enough to the lowest log that the top one (3 higher) stays within reach on level ground.
STAND_REACH = 2.0
WANDER_DISTANCE = 48
WANDER_REACH = 3.0
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def rest_plan(state: dict, grid: Grid, at: float, clock: dict) -> list[dict]:
    """Sleep at night or when exhausted; otherwise wait (at most a minute) for nightfall."""
    night = is_night(clock["phase"])
    if night or state["vitals"]["energy"] < EXHAUSTED_BELOW:
        thought = "It's dark. Time to curl up and sleep." if night else "I'm too tired to keep my eyes open."
        return [{"kind": "sleep", "thought": thought}]
    until_night = (NIGHTFALL - clock["seconds_into_day"]) / clock["time_scale"]
    return [{"kind": "wait", "seconds": max(1.0, min(MAX_WAIT, until_night))}]


def trees_near(seed: str, x: int, z: int, radius: int) -> list[tuple[int, int, int]]:
    """Generated trees (trunk x, trunk z, ground height) within `radius` blocks of (x, z)."""
    found = []
    for cx in range((x - radius) // CHUNK, (x + radius) // CHUNK + 1):
        for cz in range((z - radius) // CHUNK, (z + radius) // CHUNK + 1):
            found.extend(tree for tree in trees_in_chunk(cx, cz, seed)
                         if math.hypot(tree[0] - x, tree[1] - z) <= radius)
    return found


def failed_columns(state: dict) -> set[tuple[int, int]]:
    """Columns where a recent step failed. Their trees are left alone while the failure is recent."""
    return {(entry["target"]["x"], entry["target"]["z"]) for entry in state["recent_actions"]
            if entry["result"] == "failed" and "target" in entry}


def standing_logs(grid: Grid, state: dict) -> list[Cell]:
    """The logs left in the nearest tree worth trying, lowest first, or [] when there is none."""
    x, _, z = as_cell(state["position"])
    skip = failed_columns(state)
    best: tuple[float, list[Cell]] | None = None
    for tx, tz, base in trees_near(state["world_seed"], x, z, TREE_SEARCH):
        if (tx, tz) in skip:
            continue
        logs = [(tx, y, tz) for y in range(base + 1, base + TRUNK_HEIGHT + 1) if grid.material(tx, y, tz) == LOG]
        distance = math.hypot(tx - x, tz - z)
        if logs and (best is None or distance < best[0]):
            best = (distance, logs)
    return best[1] if best else []


def wander_target(state: dict, clock: dict) -> list[int]:
    """A spot 48 blocks away, in a direction that changes each game day."""
    x, _, z = as_cell(state["position"])
    dx, dz = DIRECTIONS[clock["day_number"] % len(DIRECTIONS)]
    tx, tz = x + dx * WANDER_DISTANCE, z + dz * WANDER_DISTANCE
    return [tx, terrain_height(tx, tz, state["world_seed"]) + 1, tz]


def scripted_plan(state: dict, grid: Grid, at: float, clock: dict) -> list[dict]:
    """By day: planks from logs, else chop the nearest tree, else look further out. Rest as rest_plan."""
    rest = rest_plan(state, grid, at, clock)
    if rest[0]["kind"] == "sleep":
        return rest
    if state["inventory"].get(LOG, 0) > 0:
        return [{"kind": "craft", "recipe": "planks", "thought": "Logs make good planks."}]
    logs = standing_logs(grid, state)
    if logs:
        return [{"kind": "walk", "target": list(logs[0]), "reach": STAND_REACH, "thought": "That tree has good wood."},
                *({"kind": "mine", "target": list(log)} for log in logs)]
    return [{"kind": "walk", "target": wander_target(state, clock), "reach": WANDER_REACH,
             "thought": "No trees here. I'll look further out."}]
```

- [ ] **Step 4: Run the tick through actions**

Before replacing `backend/survival/tick.py`, compare it with the M1 plan's Task 5 code. Carry any differences (review fixes) into the new version below.

Replace the whole of `backend/survival/tick.py` with:

```python
"""One survival tick: bring the active life's world up to now.

The worker calls `tick_life` about once a second. A longer gap (a laptop that slept) is
caught up in steps of at most 60 game seconds, so a pet can starve while nobody watches.
Each step first runs Mimo's timed actions up to the step's start (backend.survival.actions),
then advances vitals with the activity and surroundings at that moment. A planner decides the
next steps whenever Mimo runs out: `rest_plan` (M1's sleep rule) unless the caller passes
another; the worker passes the interim `scripted_plan` until the brain arrives.
"""

from __future__ import annotations

import sqlite3
import time

from backend.services.block_table import material_in
from backend.services.worldgen import biome_at
from backend.survival.actions import ActionContext, Planner, activity_of, advance_actions, ensure_actions
from backend.survival.clock import DAY_SECONDS, clock_at, is_night, time_scale
from backend.survival.grid import world_grid
from backend.survival.registry import LifeRegistry
from backend.survival.script import rest_plan
from backend.survival.vitals import (
    FIRE_REACH, FREEZING_BELOW, WARM_BLOCKS, Surroundings, is_sheltered, near_warm_block, step_vitals,
)
from backend.survival.world import SurvivalWorld, log_event, placed_near, read_state, write_state

MAX_STEP_SECONDS = 60.0
HUNGRY_BELOW = 30.0
CAUSE_TEXT = {"starvation": "starvation", "cold": "the cold", "drowning": "drowning", "fall": "a fall"}

Event = tuple[float, str, str]


def surroundings_at(db: sqlite3.Connection, seed: str, position: dict) -> Surroundings:
    x, y, z = round(position["x"]), round(position["y"]), round(position["z"])

    def material_at(cx: int, cy: int, cz: int) -> str:
        return material_in(db, cx, cy, cz, seed)

    return Surroundings(
        biome=biome_at(x, z, seed),
        sheltered=is_sheltered(material_at, x, y, z),
        near_fire=near_warm_block(placed_near(db, position, FIRE_REACH, WARM_BLOCKS), x, y, z),
        head_in_water=material_at(x, y, z) == "water",
    )


def note_crossings(state: dict, before: dict, at: float, events: list[Event]) -> None:
    after, name = state["vitals"], state["name"]
    if before["hunger"] >= HUNGRY_BELOW > after["hunger"]:
        state["last_thought"] = "My tummy is rumbling. I need food."
        events.append((at, "hungry", f"{name} is getting hungry."))
    if before["hunger"] > 0 >= after["hunger"]:
        state["last_thought"] = "I'm starving..."
        events.append((at, "starving", f"{name} is starving."))
    if before["warmth"] >= FREEZING_BELOW > after["warmth"]:
        state["last_thought"] = "I'm so cold."
        events.append((at, "freezing", f"{name} is freezing."))


def record_death(state: dict, cause: str, at: float, scale: float, events: list[Event]) -> None:
    """Mark Mimo dead at `at` and log it. The current step and the plan end with the life."""
    day = clock_at(state["born_at"], at, scale)["day_number"]
    state.update(status="dead", died_at=at, cause=cause, action=None, queue=[])
    events.append((at, "death", f"{state['name']} died of {CAUSE_TEXT[cause]} on day {day}."))


def advance_world(world: SurvivalWorld, timestamp: float, scale: float, planner: Planner = rest_plan) -> dict:
    """Catch the world up to `timestamp` in one transaction and return the saved state."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None or timestamp <= state["last_tick_at"]:
            return state
        ensure_actions(state)
        events: list[Event] = []
        context = ActionContext(grid=world_grid(db, world.seed), planner=planner, events=events,
                                clock_at=lambda at: clock_at(state["born_at"], at, scale))
        cursor = state["last_tick_at"]
        remaining = (timestamp - cursor) * scale
        while remaining > 1e-9:
            fell_at = advance_actions(state, context, cursor)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
                break
            step = min(MAX_STEP_SECONDS, remaining)
            night = is_night(clock_at(state["born_at"], cursor, scale)["phase"])
            last_hello = state["last_hello_at"] or state["born_at"]
            before = state["vitals"]
            state["vitals"], cause = step_vitals(
                before, step, night=night, activity=activity_of(state),
                surroundings=surroundings_at(db, world.seed, state["position"]),
                lonely=(cursor - last_hello) * scale > DAY_SECONDS)
            cursor += step / scale
            remaining -= step
            note_crossings(state, before, cursor, events)
            if cause:
                record_death(state, cause, cursor, scale, events)
                break
        if state["died_at"] is None:
            fell_at = advance_actions(state, context, timestamp)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
        state["last_tick_at"] = state["died_at"] if state["died_at"] is not None else timestamp
        write_state(db, state)
        for at, kind, text in sorted(events, key=lambda event: event[0]):
            log_event(db, at, kind, text)
        return state


def tick_life(registry: LifeRegistry, timestamp: float | None = None, scale: float | None = None,
              planner: Planner = rest_plan) -> dict | None:
    """Advance the active life and archive it if it died. Returns its state, or None if no pet is alive."""
    life = registry.active_life()
    if life is None:
        return None
    timestamp = time.time() if timestamp is None else timestamp
    scale = time_scale() if scale is None else scale
    state = advance_world(SurvivalWorld(registry.world_path(life)), timestamp, scale, planner)
    if state["died_at"] is not None:
        registry.mark_dead(life["id"], state["died_at"], state["cause"])
    return state
```

- [ ] **Step 5: Let the worker run the interim script**

In `backend/workers/mimo_worker.py`, replace the module docstring's sentence:

```
active life up to now (vitals, the interim sleep rule, death). The retired legacy world at
```

with:

```
active life up to now (timed actions, vitals, death). The retired legacy world at
```

Replace the survival imports:

```python
from backend.survival.registry import LifeRegistry, data_dir
from backend.survival.tick import tick_life
from backend.survival.world import WorldMissing
```

with:

```python
from backend.survival.actions import Planner
from backend.survival.registry import LifeRegistry, data_dir
from backend.survival.script import rest_plan, scripted_plan
from backend.survival.tick import tick_life
from backend.survival.world import WorldMissing
```

After the line `stopping = False`, add:

```python

# What the pet does between vitals. The brain milestone (M3) replaces this interim script.
WORKER_PLANNER: Planner = scripted_plan
```

Replace the start of `run_once`:

```python
def run_once(registry: LifeRegistry, previous: str | None, timestamp: float | None = None) -> str:
    """Tick the active life once. Logs a line when the pet's status changes and returns it."""
    state = tick_life(registry, timestamp)
```

with:

```python
def run_once(registry: LifeRegistry, previous: str | None, timestamp: float | None = None,
             planner: Planner = rest_plan) -> str:
    """Tick the active life once. Logs a line when the pet's status changes and returns it.

    `planner` defaults to the plain sleep rule; `main` passes WORKER_PLANNER.
    """
    state = tick_life(registry, timestamp, planner=planner)
```

In `main`, replace:

```python
            previous = run_once(registry, previous)
```

with:

```python
            previous = run_once(registry, previous, planner=WORKER_PLANNER)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_script.py"`
Expected: `Ran 7 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_tick*.py"`
Expected: `Ran 15 tests` … `OK` (M1's 10 tick tests unchanged, plus 5).

If `test_one_tick_can_walk_chop_and_craft` fails, print the state's `recent_actions` for the `random.Random(8)` world before changing any code: a failed step says why (for example `no way there`). Fix the cause in `script.py` or `pathing.py`; do not weaken the assertion.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_worker.py"`
Expected: `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 193 tests` … `OK`

- [ ] **Step 7: Commit**

```bash
git add backend/survival/script.py backend/survival/tick.py backend/workers/mimo_worker.py backend/tests/test_survival_script.py backend/tests/test_survival_tick_actions.py
git commit -m "feat: run timed actions in the survival tick with an interim plan" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Stream the current step from `/api/mimo`

**Files:**
- Modify: `backend/survival/snapshot.py`
- Test: `backend/tests/test_survival_api.py` (add one test)

**Interfaces:**
- Consumes: M1 `survival_view`, `get_mimo`; the running step and `recent_actions` shapes (Tasks 4–5).
- Produces (`backend.survival.snapshot`): `ACTION_FIELDS`, `action_view(action: dict | None) -> dict | None`. The survival view (so `GET /api/mimo` while alive, and `GET /api/lives/{id}` for survival lives) gains `action` (`kind`, `started_at`, `ends_at`, and `path` for walk, swim and fall, or `target` with `block` for mine and place, `item` for eat and smelt, `recipe` for craft, `blocks` for falls; None when idle or dead) and `recent_actions` (list, oldest first, at most 20). `server_time` is already there (M1).

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_survival_api.py`, add this test at the end of `SurvivalApiTests` (before `if __name__ == "__main__":`):

```python
    def test_the_current_step_and_recent_steps_are_streamed(self):
        hatch_egg()
        fresh = get_mimo()
        self.assertEqual((fresh["action"], fresh["recent_actions"]), (None, []))
        path = [{"x": 1, "y": 9, "z": 2, "at": 10.0}, {"x": 2, "y": 9, "z": 2, "at": 10.9, "swim": True}]
        finished = {"kind": "mine", "started_at": 5.0, "target": {"x": 3, "y": 9, "z": 2}, "block": "oak_log",
                    "ended_at": 7.0, "result": "done"}
        world = self.active_world()
        with world.transaction() as db:
            state = read_state(db)
            state.update(action={"kind": "walk", "started_at": 10.0, "ends_at": 10.9, "path": path,
                                 "target": {"x": 2, "y": 9, "z": 2}, "reach": 0.0, "reached": True, "segments": 0},
                         recent_actions=[finished])
            write_state(db, state)
        mimo = get_mimo()
        self.assertEqual(mimo["action"], {"kind": "walk", "started_at": 10.0, "ends_at": 10.9, "path": path,
                                          "target": {"x": 2, "y": 9, "z": 2}})
        self.assertEqual(mimo["recent_actions"], [finished])
        self.assertIn("server_time", mimo)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_api.py"`
Expected: 1 error, `KeyError: 'action'`.

- [ ] **Step 3: Add the fields**

In `backend/survival/snapshot.py`, after the line `NOTABLE_LIMIT = 6`, add:

```python
# The parts of the current step the viewer animates. The rest (reach, reached, segments) is the
# planner's bookkeeping.
ACTION_FIELDS = ("kind", "started_at", "ends_at", "path", "target", "block", "item", "recipe", "blocks")


def action_view(action: dict | None) -> dict | None:
    """The current step for the viewer, or None when Mimo is between steps."""
    if action is None:
        return None
    return {key: action[key] for key in ACTION_FIELDS if key in action}
```

In `survival_view`, replace:

```python
        "died_at": state["died_at"],
        "cause": state["cause"],
    }
```

with:

```python
        "died_at": state["died_at"],
        "cause": state["cause"],
        # Worlds from before M2 have no action fields until their first tick.
        "action": action_view(state.get("action")),
        "recent_actions": state.get("recent_actions", []),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_api.py"`
Expected: `Ran 10 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 194 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/snapshot.py backend/tests/test_survival_api.py
git commit -m "feat: stream Mimo's current and recent steps from /api/mimo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Viewer action types and path motion

**Files:**
- Modify: `frontend/src/survival/types.ts`
- Create: `frontend/src/survival/motion.ts`
- Test: `frontend/src/survival/motion.test.ts`

**Interfaces:**
- Consumes: the `/api/mimo` fields from Task 7; M1 `Point`, `SurvivalState`.
- Produces (`types.ts`): `ActionKind`, `PathPoint` (`Point` + `at`, optional `swim`), `MimoAction` (`kind`, `started_at`, `ends_at: number | null`, optional `path`, `target`, `block`, `item`, `recipe`, `blocks`), `FinishedAction` (`kind`, `started_at`, `ended_at`, `result`, optional `target`, `block`, `item`, `recipe`, `reason`); `SurvivalState.action: MimoAction | null`, `SurvivalState.recent_actions: FinishedAction[]`.
- Produces (`motion.ts`): `interface Pose { x, y, z, facing: number | null, travelled, swimming }` (cell coordinates; the pet stands at the cell's center), `serverNow(serverTime, receivedAt, now) -> number`, `facingToward(from, to) -> number | null` (radians around +y, 0 faces +z), `turnToward(current, target, amount) -> number`, `poseAt(action, rest, t) -> Pose`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/motion.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { facingToward, poseAt, serverNow, turnToward } from './motion'
import type { MimoAction } from './types'

const walk: MimoAction = {
  kind: 'walk', started_at: 10, ends_at: 10.9,
  path: [
    { x: 0, y: 1, z: 0, at: 10 }, { x: 1, y: 1, z: 0, at: 10.3 },
    { x: 2, y: 2, z: 0, at: 10.6 }, { x: 2, y: 2, z: 1, at: 10.9, swim: true },
  ],
}
const rest = { x: 7, y: 3, z: 7 }

describe('serverNow', () => {
  it('adds the local time since the response arrived and never runs backwards', () => {
    expect(serverNow(1000, 50, 52.5)).toBe(1002.5)
    expect(serverNow(1000, 50, 49)).toBe(1000)
  })
})

describe('poseAt', () => {
  it('moves along a walk by arrival times', () => {
    const pose = poseAt(walk, rest, 10.15)
    expect(pose.x).toBeCloseTo(0.5)
    expect(pose.y).toBe(1)
    expect(pose.travelled).toBeCloseTo(0.5)
    expect(pose.facing).toBeCloseTo(Math.PI / 2)
  })

  it('climbs with a step up and faces each new direction', () => {
    const climbing = poseAt(walk, rest, 10.45)
    expect(climbing.x).toBeCloseTo(1.5)
    expect(climbing.y).toBeCloseTo(1.5)
    const turned = poseAt(walk, rest, 10.75)
    expect(turned.z).toBeCloseTo(0.5)
    expect(turned.facing).toBeCloseTo(0)
    expect(turned.swimming).toBe(true)
  })

  it('holds the ends of the path before the start and after the end', () => {
    expect(poseAt(walk, rest, 9)).toMatchObject({ x: 0, y: 1, z: 0 })
    expect(poseAt(walk, rest, 20)).toMatchObject({ x: 2, y: 2, z: 1, travelled: 3 })
  })

  it('drops faster and faster when falling', () => {
    const fall: MimoAction = {
      kind: 'fall', started_at: 0, ends_at: 1, blocks: 8,
      path: [{ x: 3, y: 9, z: 3, at: 0 }, { x: 3, y: 1, z: 3, at: 1 }],
    }
    expect(poseAt(fall, rest, 0.5).y).toBeCloseTo(7)
    expect(poseAt(fall, rest, 0.9).y).toBeCloseTo(9 - 8 * 0.81)
    expect(poseAt(fall, rest, 0.5).facing).toBeNull()
  })

  it('stands at the server position and faces the target of a block step', () => {
    const mine: MimoAction = { kind: 'mine', started_at: 0, ends_at: 2, target: { x: 8, y: 3, z: 8 }, block: 'oak_log' }
    expect(poseAt(mine, rest, 1)).toMatchObject({ x: 7, y: 3, z: 7, travelled: 0, swimming: false })
    expect(poseAt(mine, rest, 1).facing).toBeCloseTo(Math.PI / 4)
    expect(poseAt(null, rest, 1).facing).toBeNull()
  })
})

describe('turning', () => {
  it('faces along the travel direction and turns the short way round', () => {
    expect(facingToward({ x: 0, z: 0 }, { x: 0, z: -1 })).toBeCloseTo(Math.PI)
    expect(facingToward({ x: 1, z: 1 }, { x: 1, z: 1 })).toBeNull()
    expect(turnToward(3, -3, 1)).toBeCloseTo(3 + (2 * Math.PI - 6))
    expect(turnToward(0, 1, 0.5)).toBeCloseTo(0.5)
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/survival/motion.test.ts`
Expected: FAIL, `Failed to resolve import "./motion"`.

- [ ] **Step 3: Add the action types**

In `frontend/src/survival/types.ts`, replace:

```ts
export interface Point {
  x: number
  y: number
  z: number
}
```

with:

```ts
export interface Point {
  x: number
  y: number
  z: number
}

export type ActionKind = 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'craft' | 'smelt' | 'sleep' | 'wait'

/** One cell of a walk, swim or fall, with the server time Mimo gets there. */
export interface PathPoint extends Point {
  at: number
  /** True on water-surface cells. */
  swim?: boolean
}

/** The step Mimo is doing now (backend/survival/steps.py and actions.py). */
export interface MimoAction {
  kind: ActionKind
  started_at: number
  /** Null while sleeping: sleep ends once Mimo is rested and it is not night. */
  ends_at: number | null
  path?: PathPoint[]
  target?: Point
  block?: string
  item?: string
  recipe?: string
  /** How far a fall drops. */
  blocks?: number
}

/** A step that finished, oldest first. Waits are left out. */
export interface FinishedAction {
  kind: ActionKind
  started_at: number
  ended_at: number
  result: 'done' | 'failed'
  target?: Point
  block?: string
  item?: string
  recipe?: string
  reason?: string
}
```

Replace (the end of `SurvivalState`):

```ts
  server_time: number
  died_at: number | null
  cause: string | null
}
```

with:

```ts
  server_time: number
  died_at: number | null
  cause: string | null
  action: MimoAction | null
  recent_actions: FinishedAction[]
}
```

- [ ] **Step 4: Write the motion module**

Create `frontend/src/survival/motion.ts`:

```ts
import type { MimoAction, PathPoint, Point } from './types'

/** Where the pet is at a moment. Cell coordinates, fractional while moving; the pet stands at the cell's center. */
export interface Pose {
  x: number
  y: number
  z: number
  /** Heading in radians around +y (0 faces +z), or null to keep the last heading. */
  facing: number | null
  /** Path cells passed since the step began, fractional, for the hop cycle. */
  travelled: number
  /** True while the pet floats on water. */
  swimming: boolean
}

const PATH_KINDS = new Set(['walk', 'swim', 'fall'])

/** Server time now: the last response's server_time plus the local time since it arrived. */
export function serverNow(serverTime: number, receivedAt: number, now: number): number {
  return serverTime + Math.max(0, now - receivedAt)
}

export function facingToward(from: { x: number; z: number }, to: { x: number; z: number }): number | null {
  const dx = to.x - from.x
  const dz = to.z - from.z
  return dx === 0 && dz === 0 ? null : Math.atan2(dx, dz)
}

/** Turn `current` toward `target` by `amount` (0..1) of the way, the short way round. */
export function turnToward(current: number, target: number, amount: number): number {
  const difference = Math.atan2(Math.sin(target - current), Math.cos(target - current))
  return current + difference * amount
}

function alongPath(path: PathPoint[], t: number, falling: boolean): Pose {
  const last = path[path.length - 1]
  if (path.length === 1 || t >= last.at) {
    const previous = path[path.length - 2]
    return {
      x: last.x, y: last.y, z: last.z, facing: previous ? facingToward(previous, last) : null,
      travelled: path.length - 1, swimming: Boolean(last.swim),
    }
  }
  let index = 0
  while (index < path.length - 2 && t >= path[index + 1].at) index++
  const from = path[index]
  const to = path[index + 1]
  const span = to.at - from.at
  const p = span > 0 ? Math.min(1, Math.max(0, (t - from.at) / span)) : 1
  // A fall speeds up: the drop grows with the square of the time.
  const drop = falling ? p * p : p
  return {
    x: from.x + (to.x - from.x) * p,
    y: from.y + (to.y - from.y) * drop,
    z: from.z + (to.z - from.z) * p,
    facing: facingToward(from, to),
    travelled: index + p,
    swimming: Boolean(to.swim),
  }
}

/** Where the pet is and which way it faces at server time `t`. `rest` is the server's position. */
export function poseAt(action: MimoAction | null, rest: Point, t: number): Pose {
  if (action?.path && action.path.length > 0 && PATH_KINDS.has(action.kind)) {
    return alongPath(action.path, t, action.kind === 'fall')
  }
  return {
    x: rest.x, y: rest.y, z: rest.z, facing: action?.target ? facingToward(rest, action.target) : null,
    travelled: 0, swimming: false,
  }
}
```

- [ ] **Step 5: Run the tests, type check and lint**

Run: `cd frontend && npx vitest run src/survival/motion.test.ts`
Expected: `Tests  7 passed (7)`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival/types.ts src/survival/motion.ts src/survival/motion.test.ts`
Expected: `Tests  113 passed (113)`, the build succeeds, eslint prints nothing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/survival/types.ts frontend/src/survival/motion.ts frontend/src/survival/motion.test.ts
git commit -m "feat: interpolate the pet along its streamed path" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Animation and block effect rules

**Files:**
- Create: `frontend/src/survival/animation.ts`, `frontend/src/survival/effects.ts`
- Test: `frontend/src/survival/animation.test.ts`, `frontend/src/survival/effects.test.ts`

**Interfaces:**
- Consumes: `MimoAction`, `FinishedAction`, `Point` (Task 8).
- Produces (`animation.ts`): `type PetMove = 'idle' | 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'sleep' | 'work'`, `interface BodyPose { lift, pitch, roll, stretch }`, `interface Puff { x, y, scale, opacity }`, `moveFor(action, t, swimming = false) -> PetMove`, `bodyPose(move, stepTime, travelled, clock) -> BodyPose`, `zPuffs(sleepTime) -> Puff[]` (3), `crumbs(stepTime) -> Point[]` (3), `LIE_DOWN_SECONDS = 0.6`.
- Produces (`effects.ts`): `CRACK_STAGES = 6`, `PLACE_BOUNCE_SECONDS = 0.35`, `BURST_SECONDS = 0.6`, `POP_SECONDS = 0.6`, `crackStage(action, t) -> number` (0 = none), `crackMask(stage) -> Uint8Array` (64 flags, row 0 at the top), `crackTexels(stage) -> Uint8Array` (8×8 RGBA, bottom row first), `placeScale(elapsed) -> number`, `burst(count, elapsed) -> Point[]`, `itemPop(elapsed, from, to) -> { position: Point; scale: number }`, `interface BlockEffect { key, kind: 'break' | 'place', cell: Point, block: string, at: number }`, `blockEffects(action, recent) -> BlockEffect[]`.

Units: `lift` in blocks, `pitch` (lean forward) and `roll` (onto the side) in radians, `stretch` a vertical scale. `stepTime` is server seconds since the step started; `clock` is any steady clock in seconds (the renderer's elapsed time).

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/animation.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { bodyPose, crumbs, moveFor, zPuffs } from './animation'
import type { MimoAction } from './types'

const mine: MimoAction = { kind: 'mine', started_at: 10, ends_at: 12, target: { x: 1, y: 1, z: 0 }, block: 'dirt' }

describe('moveFor', () => {
  it('maps each step to an animation', () => {
    expect(moveFor(null, 0)).toBe('idle')
    expect(moveFor(mine, 11)).toBe('mine')
    expect(moveFor({ ...mine, kind: 'craft', recipe: 'planks' }, 11)).toBe('work')
    expect(moveFor({ kind: 'sleep', started_at: 0, ends_at: null }, 5000)).toBe('sleep')
    expect(moveFor({ kind: 'walk', started_at: 0, ends_at: 3, path: [] }, 1, true)).toBe('swim')
  })

  it('goes idle when a step has ended and the next has not arrived yet', () => {
    expect(moveFor(mine, 12.5)).toBe('idle')
    expect(moveFor(mine, 12.5, true)).toBe('swim')
  })
})

describe('bodyPose', () => {
  it('hops once per block while walking', () => {
    expect(bodyPose('walk', 0, 2, 0).lift).toBeCloseTo(0)
    expect(bodyPose('walk', 0, 2.5, 0).lift).toBeCloseTo(0.22)
  })

  it('swings while mining, bobs low while swimming, stretches when falling and lies down to sleep', () => {
    const swings = [0, 0.05, 0.1, 0.2, 0.3, 0.4].map((seconds) => bodyPose('mine', seconds, 0, 0).pitch)
    expect(Math.max(...swings)).toBeGreaterThan(0.3)
    expect(Math.min(...swings)).toBeGreaterThanOrEqual(0)
    expect(bodyPose('swim', 0, 0, 1).lift).toBeLessThan(-0.25)
    expect(bodyPose('fall', 0, 0, 0).stretch).toBeGreaterThan(1)
    expect(bodyPose('sleep', 0.3, 0, 0).roll).toBeCloseTo(Math.PI / 4)
    expect(bodyPose('sleep', 5, 0, 0)).toMatchObject({ roll: Math.PI / 2, lift: 0.45 })
  })
})

describe('sleep and eating details', () => {
  it('floats three z’s one after another once the pet lies down', () => {
    expect(zPuffs(0.3).every((puff) => puff.opacity === 0)).toBe(true)
    const first = zPuffs(0.6)
    expect(first[0]).toMatchObject({ y: 0, opacity: 1 })
    expect(first[1].opacity).toBe(0)
    expect(zPuffs(20).every((puff) => puff.y >= 0 && puff.y <= 1.2)).toBe(true)
    expect(zPuffs(0.6 + 2.39)[0].opacity).toBeLessThan(0.05)
  })

  it('drops crumbs below the mouth', () => {
    const bits = crumbs(0.2)
    expect(bits).toHaveLength(3)
    expect(bits.every((bit) => bit.y <= 0 && bit.y >= -0.4)).toBe(true)
  })
})
```

Create `frontend/src/survival/effects.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { blockEffects, burst, CRACK_STAGES, crackMask, crackStage, crackTexels, itemPop, placeScale } from './effects'
import type { FinishedAction, MimoAction } from './types'

const mine: MimoAction = { kind: 'mine', started_at: 10, ends_at: 12, target: { x: 1, y: 2, z: 3 }, block: 'stone' }

describe('cracks', () => {
  it('grow with mining progress', () => {
    expect(crackStage(null, 11)).toBe(0)
    expect(crackStage({ ...mine, kind: 'place' }, 11)).toBe(0)
    expect(crackStage(mine, 10)).toBe(0)
    expect(crackStage(mine, 10.01)).toBe(1)
    expect(crackStage(mine, 11)).toBe(4)
    expect(crackStage(mine, 12)).toBe(CRACK_STAGES)
    expect(crackStage(mine, 15)).toBe(CRACK_STAGES)
  })

  it('add pixels at every stage and keep the earlier ones', () => {
    const counts = Array.from({ length: CRACK_STAGES + 1 }, (_, stage) => crackMask(stage).reduce((sum, value) => sum + value, 0))
    expect(counts).toEqual([0, 1, 4, 8, 13, 16, 19])
    for (let stage = 1; stage <= CRACK_STAGES; stage++) {
      const after = crackMask(stage)
      crackMask(stage - 1).forEach((value, index) => { if (value) expect(after[index]).toBe(1) })
    }
  })

  it('paint dark see-through texels with the top row stored last', () => {
    const texels = crackTexels(CRACK_STAGES)
    let shown = 0
    for (let i = 3; i < texels.length; i += 4) if (texels[i] > 0) shown++
    expect(shown).toBe(19)
    expect(texels[(7 * 8 + 5) * 4 + 3]).toBe(190)
    expect(crackTexels(0).every((value) => value === 0)).toBe(true)
  })
})

describe('placing and breaking', () => {
  it('bounces a placed block in from 0.6', () => {
    expect(placeScale(0)).toBe(0.6)
    expect(Math.max(...[0.05, 0.1, 0.15, 0.2, 0.25, 0.3].map(placeScale))).toBeGreaterThan(1)
    expect(placeScale(0.35)).toBe(1)
    expect(placeScale(2)).toBe(1)
  })

  it('throws particles out and up, then gravity pulls them down', () => {
    expect(burst(8, 0).every((point) => point.x === 0 && point.y === 0 && point.z === 0)).toBe(true)
    const early = burst(8, 0.1)
    expect(early).toHaveLength(8)
    expect(early.every((point) => point.y > 0)).toBe(true)
    expect(burst(8, 0.6)[0].y).toBeLessThan(0)
  })

  it('pops the item from the block to the pet', () => {
    const from = { x: 0, y: 0, z: 0 }
    const to = { x: 2, y: 1, z: 0 }
    expect(itemPop(0, from, to)).toEqual({ position: from, scale: 1 })
    const end = itemPop(0.6, from, to)
    expect(end.position.x).toBeCloseTo(2)
    expect(end.position.y).toBeCloseTo(1)
    expect(end.scale).toBeCloseTo(0.3)
  })
})

describe('blockEffects', () => {
  it('lists finished breaks and placements once each, with the running step', () => {
    const recent: FinishedAction[] = [
      { kind: 'mine', started_at: 1, ended_at: 3, result: 'done', target: { x: 5, y: 1, z: 0 }, block: 'oak_log' },
      { kind: 'place', started_at: 3, ended_at: 3.3, result: 'done', target: { x: 4, y: 1, z: 0 }, block: 'planks' },
      { kind: 'mine', started_at: 4, ended_at: 4, result: 'failed', target: { x: 9, y: 1, z: 0 }, reason: 'out of reach' },
      { kind: 'craft', started_at: 5, ended_at: 6, result: 'done', recipe: 'planks' },
      { kind: 'mine', started_at: 10, ended_at: 12, result: 'done', target: { x: 1, y: 2, z: 3 }, block: 'stone' },
    ]
    const effects = blockEffects(mine, recent)
    expect(effects.map((effect) => [effect.kind, effect.at])).toEqual([['break', 3], ['place', 3.3], ['break', 12]])
    expect(effects[2].key).toBe('mine:1,2,3:12')
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/survival/animation.test.ts src/survival/effects.test.ts`
Expected: 2 failed files, `Failed to resolve import "./animation"` and `Failed to resolve import "./effects"`.

- [ ] **Step 3: Write the animation rules**

Create `frontend/src/survival/animation.ts`:

```ts
import type { ActionKind, MimoAction, Point } from './types'

export type PetMove = 'idle' | 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'sleep' | 'work'

/** How the body moves on top of its position. */
export interface BodyPose {
  /** Extra height in blocks. */
  lift: number
  /** Lean forward, in radians. */
  pitch: number
  /** Roll onto the side, in radians; π/2 lies flat. */
  roll: number
  /** Vertical stretch; 1 is the normal shape. */
  stretch: number
}

export interface Puff {
  x: number
  y: number
  scale: number
  opacity: number
}

export const LIE_DOWN_SECONDS = 0.6
const MOVES: Record<ActionKind, PetMove> = {
  walk: 'walk', swim: 'swim', fall: 'fall', mine: 'mine', place: 'place', eat: 'eat', sleep: 'sleep',
  craft: 'work', smelt: 'work', wait: 'idle',
}
const HOP_HEIGHT = 0.22
const SWING_SECONDS = 0.45
const NIBBLES_PER_SECOND = 3
const Z_PERIOD = 2.4
const Z_COUNT = 3
const CRUMB_PERIOD = 0.5

/** The animation for the current step at server time t. After a step ends the pet idles until the next arrives. */
export function moveFor(action: MimoAction | null, t: number, swimming = false): PetMove {
  const resting: PetMove = swimming ? 'swim' : 'idle'
  if (!action || (action.ends_at !== null && t >= action.ends_at)) return resting
  const move = MOVES[action.kind]
  return move === 'walk' && swimming ? 'swim' : move
}

/** Body offsets for a move. */
export function bodyPose(move: PetMove, stepTime: number, travelled: number, clock: number): BodyPose {
  const pose: BodyPose = { lift: 0, pitch: 0, roll: 0, stretch: 1 }
  switch (move) {
    case 'walk':
      pose.lift = Math.abs(Math.sin(Math.PI * travelled)) * HOP_HEIGHT
      pose.pitch = 0.08
      break
    case 'swim':
      pose.lift = -0.35 + Math.sin(clock * 3) * 0.06
      pose.pitch = 0.1
      break
    case 'fall':
      pose.pitch = -0.3
      pose.stretch = 1.08
      break
    case 'mine':
      pose.pitch = 0.35 * Math.max(0, Math.sin((2 * Math.PI * stepTime) / SWING_SECONDS))
      break
    case 'place':
      pose.pitch = 0.4 * Math.sin(Math.PI * Math.min(1, stepTime / 0.3))
      break
    case 'eat':
      pose.pitch = 0.09 * (1 + Math.sin(2 * Math.PI * NIBBLES_PER_SECOND * stepTime))
      break
    case 'sleep': {
      const down = Math.min(1, stepTime / LIE_DOWN_SECONDS)
      pose.roll = (Math.PI / 2) * down
      // Lying on its side, the pet's half-width would sink into the ground without this.
      pose.lift = 0.45 * down
      break
    }
    case 'work':
      pose.pitch = 0.06 * Math.sin(stepTime * 8)
      break
    default:
      pose.lift = Math.sin(clock * 2) * 0.05
  }
  return pose
}

/** Three floating z's above a sleeping pet, rising and fading one after another. */
export function zPuffs(sleepTime: number): Puff[] {
  return Array.from({ length: Z_COUNT }, (_, index) => {
    const age = sleepTime - LIE_DOWN_SECONDS - (index * Z_PERIOD) / Z_COUNT
    if (age < 0) return { x: 0, y: 0, scale: 0, opacity: 0 }
    const p = (age % Z_PERIOD) / Z_PERIOD
    return { x: 0.15 + p * 0.3, y: p * 1.2, scale: 0.6 + 0.4 * p, opacity: p < 0.7 ? 1 : (1 - p) / 0.3 }
  })
}

/** Crumbs dropping from the mouth while the pet eats, relative to the mouth. */
export function crumbs(stepTime: number): Point[] {
  return [0, 1, 2].map((index) => {
    const p = ((stepTime + index * 0.17) % CRUMB_PERIOD) / CRUMB_PERIOD
    return { x: (index - 1) * 0.08 * (1 + p), y: -0.4 * p * p, z: 0.05 * p }
  })
}
```

- [ ] **Step 4: Write the block effect rules**

Create `frontend/src/survival/effects.ts`:

```ts
import type { FinishedAction, MimoAction, Point } from './types'

export const CRACK_STAGES = 6
export const PLACE_BOUNCE_SECONDS = 0.35
export const BURST_SECONDS = 0.6
export const POP_SECONDS = 0.6
/**
 * An 8×8 crack in the soft pixel style. Row 0 is the top. Each digit is the stage from which
 * that pixel shows: the crack starts in the middle and spreads to the edges.
 */
const CRACK_ART = [
  '.....5..',
  '..6.4...',
  '...34..6',
  '.4.2...5',
  '..21.3..',
  '.3..2...',
  '4....3.6',
  '.5....4.',
]
const CRACK_COLOR = [44, 36, 32, 190]
const GRAVITY = 9.8
const GOLDEN_ANGLE = 2.39996

/** Which crack stage (0 = none, 1..CRACK_STAGES) shows on the block being mined at server time t. */
export function crackStage(action: MimoAction | null, t: number): number {
  if (!action || action.kind !== 'mine' || action.ends_at === null) return 0
  const span = action.ends_at - action.started_at
  const progress = span > 0 ? (t - action.started_at) / span : 1
  if (progress <= 0) return 0
  return Math.min(CRACK_STAGES, Math.floor(progress * CRACK_STAGES) + 1)
}

/** 64 flags, row 0 at the top: 1 where a crack pixel shows at this stage. */
export function crackMask(stage: number): Uint8Array {
  const mask = new Uint8Array(64)
  CRACK_ART.forEach((row, j) => {
    for (let i = 0; i < row.length; i++) {
      if (row[i] !== '.' && Number(row[i]) <= stage) mask[j * 8 + i] = 1
    }
  })
  return mask
}

/** RGBA texels for an 8×8 THREE.DataTexture, bottom row first like the terrain atlas. */
export function crackTexels(stage: number): Uint8Array {
  const mask = crackMask(stage)
  const data = new Uint8Array(64 * 4)
  for (let j = 0; j < 8; j++) {
    for (let i = 0; i < 8; i++) {
      if (mask[j * 8 + i]) data.set(CRACK_COLOR, ((7 - j) * 8 + i) * 4)
    }
  }
  return data
}

function easeOutBack(p: number): number {
  const c1 = 1.70158
  const c3 = c1 + 1
  return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
}

/** Scale of a just-placed block: in from 0.6 with a small bounce past full size. */
export function placeScale(elapsed: number): number {
  if (elapsed <= 0) return 0.6
  if (elapsed >= PLACE_BOUNCE_SECONDS) return 1
  return 0.6 + 0.4 * easeOutBack(elapsed / PLACE_BOUNCE_SECONDS)
}

/** Offsets of break particles `elapsed` seconds after a block breaks: out and up, then down. */
export function burst(count: number, elapsed: number): Point[] {
  return Array.from({ length: count }, (_, index) => {
    const angle = index * GOLDEN_ANGLE
    const speed = 1.4 + (index % 3) * 0.4
    const rise = 2.4 + (index % 2) * 0.8
    return {
      x: Math.cos(angle) * speed * elapsed,
      y: rise * elapsed - (GRAVITY / 2) * elapsed * elapsed,
      z: Math.sin(angle) * speed * elapsed,
    }
  })
}

/** The dropped item hops out of the broken block and shrinks as it flies to the pet. */
export function itemPop(elapsed: number, from: Point, to: Point): { position: Point; scale: number } {
  const p = Math.min(1, Math.max(0, elapsed / POP_SECONDS))
  const glide = p * p
  return {
    position: {
      x: from.x + (to.x - from.x) * glide,
      y: from.y + (to.y - from.y) * glide + Math.sin(Math.PI * p) * 0.6,
      z: from.z + (to.z - from.z) * glide,
    },
    scale: 1 - 0.7 * p,
  }
}

export interface BlockEffect {
  /** Unique per step: kind, cell and end time. */
  key: string
  kind: 'break' | 'place'
  cell: Point
  block: string
  /** Server time the step ends. */
  at: number
}

/** Breaks and placements from finished steps and the running one, one per step. */
export function blockEffects(action: MimoAction | null, recent: FinishedAction[]): BlockEffect[] {
  const found = new Map<string, BlockEffect>()
  const add = (kind: string, cell: Point | undefined, block: string | undefined, at: number | null) => {
    if ((kind !== 'mine' && kind !== 'place') || !cell || !block || at === null) return
    const key = `${kind}:${cell.x},${cell.y},${cell.z}:${at}`
    if (!found.has(key)) found.set(key, { key, kind: kind === 'mine' ? 'break' : 'place', cell, block, at })
  }
  for (const entry of recent) if (entry.result === 'done') add(entry.kind, entry.target, entry.block, entry.ended_at)
  if (action) add(action.kind, action.target, action.block, action.ends_at)
  return [...found.values()]
}
```

- [ ] **Step 5: Run the tests, type check and lint**

Run: `cd frontend && npx vitest run src/survival/animation.test.ts src/survival/effects.test.ts`
Expected: `Test Files  2 passed (2)`, `Tests  13 passed (13)`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival/animation.ts src/survival/effects.ts src/survival/animation.test.ts src/survival/effects.test.ts`
Expected: `Tests  126 passed (126)`, the build succeeds, eslint prints nothing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/survival/animation.ts frontend/src/survival/effects.ts frontend/src/survival/animation.test.ts frontend/src/survival/effects.test.ts
git commit -m "feat: add pure rules for pet animations and block effects" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: The pet walks and acts out each step

**Files:**
- Create: `frontend/src/components/world/PetVoxels.tsx`, `frontend/src/survival/SurvivalPet.tsx`
- Modify: `frontend/src/components/world/PetEntity.tsx`, `frontend/src/survival/WorldCanvas.tsx`, `frontend/src/survival/SurvivalWorld.tsx`, `frontend/src/survival/hud.ts`, `frontend/src/survival/SurvivalHud.tsx`
- Test: `frontend/src/survival/hud.test.ts`

**Interfaces:**
- Consumes: `poseAt`, `turnToward`, `serverNow` (Task 8); `moveFor`, `bodyPose`, `zPuffs`, `crumbs` (Task 9); M1 `WorldCanvas`, `SurvivalWorld`, `SurvivalHud`, `statusText`, `previewPet`.
- Produces: `PetVoxels({ voxels })` (default export); `SurvivalPet({ action, position, now, onPetClick?, hopSignal?, children? })` (default export; `now` returns server seconds); `WorldCanvas` gains optional props `action?: MimoAction | null` and `serverTime?: () => number`; `actionText(action: MimoAction | null, status: string) -> string` in `hud.ts`.

The pet now follows the server's timed path instead of PetEntity's straight-line glide, faces where it goes or what it works on, hops once per block, swings while mining, leans to place, nibbles with crumbs while eating, lies down with floating z's while sleeping, bobs low in water and stretches as it falls (the drop itself speeds up through `poseAt`). Archived worlds pass no action, so their pet stands still at its last position. PetEntity (still used by the older `/world` page) keeps its behavior; only its voxel mesh moves into `PetVoxels`.

- [ ] **Step 1: Write the failing HUD test**

In `frontend/src/survival/hud.test.ts`, replace the import line:

```ts
import { careLabel, causeText, clockTime, dayLabel, lifeLine, statusText, vitalBars, workerOnline } from './hud'
```

with:

```ts
import { actionText, careLabel, causeText, clockTime, dayLabel, lifeLine, statusText, vitalBars, workerOnline } from './hud'
```

and add at the end of the file:

```ts
describe('actionText', () => {
  it('names the current step in plain words and falls back to the status', () => {
    expect(actionText({ kind: 'mine', started_at: 0, ends_at: 2, block: 'oak_log' }, 'mining')).toBe('Mining oak log')
    expect(actionText({ kind: 'craft', started_at: 0, ends_at: 1, recipe: 'planks' }, 'crafting')).toBe('Crafting planks')
    expect(actionText({ kind: 'walk', started_at: 0, ends_at: 1, path: [] }, 'walking')).toBe('Walking')
    expect(actionText({ kind: 'wait', started_at: 0, ends_at: 5 }, 'idle')).toBe('Standing still')
    expect(actionText(null, 'sleeping')).toBe('Sleeping')
  })
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/survival/hud.test.ts`
Expected: FAIL, `actionText is not a function` (or a missing export error).

- [ ] **Step 3: Name the step in the HUD**

In `frontend/src/survival/hud.ts`, replace:

```ts
import type { CareKind, ClockPhase, LifeRow, VitalName, Vitals } from './types'
```

with:

```ts
import type { ActionKind, CareKind, ClockPhase, LifeRow, MimoAction, VitalName, Vitals } from './types'
```

Replace:

```ts
export function statusText(status: string): string {
  return STATUS_TEXT[status] ?? status.replaceAll('_', ' ')
}
```

with:

```ts
export function statusText(status: string): string {
  return STATUS_TEXT[status] ?? status.replaceAll('_', ' ')
}

const ACTION_WORDS: Partial<Record<ActionKind, string>> = {
  walk: 'Walking', swim: 'Swimming', fall: 'Falling!', mine: 'Mining', place: 'Placing', eat: 'Eating',
  craft: 'Crafting', smelt: 'Smelting', sleep: 'Sleeping',
}

/** The current step in plain words ("Mining oak log"); the status when Mimo is between steps or waiting. */
export function actionText(action: MimoAction | null, status: string): string {
  const words = action ? ACTION_WORDS[action.kind] : undefined
  if (!action || !words) return statusText(status)
  const object = action.block ?? action.item ?? action.recipe
  return object ? `${words} ${object.replaceAll('_', ' ')}` : words
}
```

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```tsx
import { careLabel, clockTime, dayLabel, statusText, vitalBars, type VitalLevel } from './hud'
```

with:

```tsx
import { actionText, careLabel, clockTime, dayLabel, vitalBars, type VitalLevel } from './hud'
```

and replace:

```tsx
{online ? statusText(state.status) : 'Worker offline'}
```

with:

```tsx
{online ? actionText(state.action, state.status) : 'Worker offline'}
```

Run: `cd frontend && npx vitest run src/survival/hud.test.ts`
Expected: all tests in the file pass.

- [ ] **Step 4: Share the pet's voxel mesh**

Create `frontend/src/components/world/PetVoxels.tsx`:

```tsx
import { useLayoutEffect, useRef } from 'react'
import * as THREE from 'three'
import type { Voxel } from '../../types/world'

/** A pet's voxels as one instanced mesh of unit cubes, colored per voxel. */
export default function PetVoxels({ voxels }: { voxels: Voxel[] }) {
  const meshRef = useRef<THREE.InstancedMesh>(null)

  useLayoutEffect(() => {
    const mesh = meshRef.current
    if (!mesh) return
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()
    voxels.forEach((voxel, index) => {
      dummy.position.set(voxel.x + 0.5, voxel.y + 0.5, voxel.z + 0.5)
      dummy.updateMatrix()
      mesh.setMatrixAt(index, dummy.matrix)
      color.setRGB(voxel.r / 255, voxel.g / 255, voxel.b / 255, THREE.SRGBColorSpace)
      mesh.setColorAt(index, color)
    })
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [voxels])

  if (voxels.length === 0) return null
  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, voxels.length]} frustumCulled={false}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial roughness={0.4} metalness={0.1} />
    </instancedMesh>
  )
}
```

In `frontend/src/components/world/PetEntity.tsx`:

Replace:

```tsx
import type { PetEntity as PetEntityType } from '../../types/world'
```

with:

```tsx
import type { PetEntity as PetEntityType } from '../../types/world'
import PetVoxels from './PetVoxels'
```

Replace:

```tsx
  const groupRef = useRef<THREE.Group>(null)
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const timeRef = useRef(0)
  const initializedRef = useRef(false)
  const prevVoxelsRef = useRef(pet.voxels)
```

with:

```tsx
  const groupRef = useRef<THREE.Group>(null)
  const timeRef = useRef(0)
```

Delete this block from the `useFrame` callback (from the `// --- Voxel instancing setup ---` comment to the blank line before `// --- Wander state machine ---`):

```tsx
    // --- Voxel instancing setup ---
    if (meshRef.current && (!initializedRef.current || prevVoxelsRef.current !== pet.voxels)) {
      const mesh = meshRef.current
      const dummy = new THREE.Object3D()
      const color = new THREE.Color()

      for (let i = 0; i < pet.voxels.length; i++) {
        const v = pet.voxels[i]
        dummy.position.set(v.x + 0.5, v.y + 0.5, v.z + 0.5)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, color)
      }
      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
      initializedRef.current = true
      prevVoxelsRef.current = pet.voxels
    }

```

Replace:

```tsx
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, pet.voxels.length]}
        frustumCulled={false}
      >
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial roughness={0.4} metalness={0.1} />
      </instancedMesh>
```

with:

```tsx
      <PetVoxels voxels={pet.voxels} />
```

- [ ] **Step 5: Write the survival pet**

Create `frontend/src/survival/SurvivalPet.tsx`:

```tsx
import { useRef, type ReactNode } from 'react'
import { useFrame, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'
import PetVoxels from '../components/world/PetVoxels'
import { previewPet } from '../components/world/previewWorld'
import { bodyPose, crumbs, moveFor, zPuffs } from './animation'
import { poseAt, turnToward } from './motion'
import type { MimoAction, Point } from './types'

const SCALE = 0.31
/** The pet's voxels span x -1..2 in model units, so its middle sits half a voxel right of the origin. */
const MODEL_OFFSET: [number, number, number] = [-0.5 * SCALE, 0, 0]
const TURN_RATE = 10
const HELLO_HOP_SECONDS = 0.7
const Z_COLOR = '#f5faf7'
const CRUMB_COLOR = '#c99a6b'
const BAR: [number, number, number] = [0.24, 0.05, 0.05]

/** One floating "z" made of three thin bars, in the voxel style. */
function SleepZ() {
  return (
    <group>
      <mesh position={[0, 0.1, 0]}>
        <boxGeometry args={BAR} />
        <meshBasicMaterial color={Z_COLOR} transparent depthWrite={false} />
      </mesh>
      <mesh rotation={[0, 0, Math.atan2(0.2, 0.24)]}>
        <boxGeometry args={[0.31, 0.05, 0.05]} />
        <meshBasicMaterial color={Z_COLOR} transparent depthWrite={false} />
      </mesh>
      <mesh position={[0, -0.1, 0]}>
        <boxGeometry args={BAR} />
        <meshBasicMaterial color={Z_COLOR} transparent depthWrite={false} />
      </mesh>
    </group>
  )
}

function setOpacity(object: THREE.Object3D, opacity: number) {
  object.traverse((child) => {
    if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshBasicMaterial) child.material.opacity = opacity
  })
}

/**
 * The survival pet, driven by the server's current step: it follows a walk's timed path, turns to
 * face where it goes or what it works on, and plays the step's animation. Cheap on phones: no
 * React state changes per frame, a handful of meshes, and all per-frame work in one useFrame.
 */
export default function SurvivalPet({ action, position, now, onPetClick, hopSignal = 0, children }: {
  action: MimoAction | null
  /** The server's position for the pet, used when the step has no path. */
  position: Point
  /** Server time now, in seconds. */
  now: () => number
  onPetClick?: () => void
  hopSignal?: number
  children?: ReactNode
}) {
  const root = useRef<THREE.Group>(null)
  const body = useRef<THREE.Group>(null)
  const zs = useRef<THREE.Group>(null)
  const crumbBits = useRef<THREE.Group>(null)
  const heading = useRef<number | null>(null)
  const hello = useRef({ signal: hopSignal, left: 0 })

  useFrame((state, delta) => {
    const t = now()
    const pose = poseAt(action, position, t)
    const move = moveFor(action, t, pose.swimming)
    const stepTime = action ? Math.max(0, t - action.started_at) : 0
    const shape = bodyPose(move, stepTime, pose.travelled, state.clock.elapsedTime)
    if (hello.current.signal !== hopSignal) hello.current = { signal: hopSignal, left: HELLO_HOP_SECONDS }
    hello.current.left = Math.max(0, hello.current.left - delta)
    const hop = hello.current.left > 0 ? Math.sin((1 - hello.current.left / HELLO_HOP_SECONDS) * Math.PI) * 0.5 : 0
    if (pose.facing !== null) {
      heading.current = heading.current === null
        ? pose.facing
        : turnToward(heading.current, pose.facing, 1 - Math.exp(-TURN_RATE * delta))
    }
    if (root.current) {
      root.current.position.set(pose.x + 0.5, pose.y + shape.lift + hop, pose.z + 0.5)
      root.current.rotation.y = heading.current ?? 0
    }
    if (body.current) {
      body.current.rotation.set(shape.pitch, 0, shape.roll)
      body.current.scale.set(1, shape.stretch, 1)
    }
    const floating = zs.current
    if (floating) {
      floating.visible = move === 'sleep'
      if (floating.visible) {
        zPuffs(stepTime).forEach((puff, index) => {
          const z = floating.children[index]
          if (!z) return
          z.position.set(puff.x, puff.y, 0)
          z.scale.setScalar(puff.scale)
          setOpacity(z, puff.opacity)
        })
      }
    }
    const bits = crumbBits.current
    if (bits) {
      bits.visible = move === 'eat'
      if (bits.visible) crumbs(stepTime).forEach((bit, index) => bits.children[index]?.position.set(bit.x, bit.y, bit.z))
    }
  })

  const click = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    hello.current.left = HELLO_HOP_SECONDS
    onPetClick?.()
  }

  return (
    <group ref={root} onClick={click}>
      <group ref={body}>
        <group position={MODEL_OFFSET} scale={SCALE}>
          <PetVoxels voxels={previewPet.voxels} />
          {children}
        </group>
      </group>
      <group ref={zs} position={[0, 1.15, 0]} visible={false}>
        {[0, 1, 2].map((index) => <SleepZ key={index} />)}
      </group>
      <group ref={crumbBits} position={[0, 0.78, 0.7]} visible={false}>
        {[0, 1, 2].map((index) => (
          <mesh key={index}>
            <boxGeometry args={[0.05, 0.05, 0.05]} />
            <meshLambertMaterial color={CRUMB_COLOR} />
          </mesh>
        ))}
      </group>
    </group>
  )
}
```

- [ ] **Step 6: Put the survival pet in the world canvas**

In `frontend/src/survival/WorldCanvas.tsx`:

Replace:

```tsx
import PetEntity from '../components/world/PetEntity'
import { previewPet } from '../components/world/previewWorld'
import BlockWorld, { type ViewStats } from '../engine/BlockWorld'
```

with:

```tsx
import BlockWorld, { type ViewStats } from '../engine/BlockWorld'
```

Replace:

```tsx
import FollowCamera from './FollowCamera'
import { daylightFactor } from './sky'
```

with:

```tsx
import FollowCamera from './FollowCamera'
import { daylightFactor } from './sky'
import SurvivalPet from './SurvivalPet'
import type { MimoAction } from './types'
```

Replace:

```tsx
const DAY_SKY = '#dce9eb'
```

with:

```tsx
const DAY_SKY = '#dce9eb'
/** Without a server clock (archives) the pet has no step and stands still. */
const NO_TIME = () => 0
```

Replace:

```tsx
 * without it the scene stays in daylight. `arrival` starts the camera high so it flies down.
 */
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0 }: {
  store: WorldStore
  position: { x: number; y: number; z: number }
  seconds?: () => number
  arrival?: boolean
  following: boolean
  onOrbit: () => void
  onPetClick?: () => void
  hopSignal?: number
}) {
```

with:

```tsx
 * without it the scene stays in daylight. `arrival` starts the camera high so it flies down.
 * `action` and `serverTime` (server seconds now) let the pet walk its path and act out its step.
 */
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, serverTime }: {
  store: WorldStore
  position: { x: number; y: number; z: number }
  seconds?: () => number
  arrival?: boolean
  following: boolean
  onOrbit: () => void
  onPetClick?: () => void
  hopSignal?: number
  action?: MimoAction | null
  serverTime?: () => number
}) {
```

Replace:

```tsx
  const [fogNear, fogFar] = fogRange(viewDistance, CAMERA_DISTANCE)
  const pet = { ...previewPet, position: { x: initial.x, y: initial.y, z: initial.z } }
```

with:

```tsx
  const [fogNear, fogFar] = fogRange(viewDistance, CAMERA_DISTANCE)
```

Replace:

```tsx
          <PetEntity pet={pet} scale={0.31} destination={{ ...position, token: 0 }} onPetClick={onPetClick} hopSignal={hopSignal}>
```

with:

```tsx
          <SurvivalPet action={action} position={position} now={serverTime ?? NO_TIME} onPetClick={onPetClick} hopSignal={hopSignal}>
```

Replace:

```tsx
          </PetEntity>
```

with:

```tsx
          </SurvivalPet>
```

The face meshes and `PetGlow` inside it stay as they are: `SurvivalPet` places its children in the same scaled model space as `PetEntity` did.

- [ ] **Step 7: Feed the step and the server clock from the living world**

In `frontend/src/survival/SurvivalWorld.tsx`:

Replace:

```tsx
import { workerOnline } from './hud'
```

with:

```tsx
import { workerOnline } from './hud'
import { serverNow } from './motion'
```

Replace:

```tsx
  const seconds = useCallback(() => liveClock(state.clock, receivedAt, Date.now() / 1000).secondsIntoDay,
    [state.clock, receivedAt])
```

with:

```tsx
  const seconds = useCallback(() => liveClock(state.clock, receivedAt, Date.now() / 1000).secondsIntoDay,
    [state.clock, receivedAt])
  const serverTime = useCallback(() => serverNow(state.server_time, receivedAt, Date.now() / 1000),
    [state.server_time, receivedAt])
```

Replace:

```tsx
      <WorldCanvas store={store} position={state.position} seconds={seconds} arrival={arrival}
        following={following} onOrbit={() => setFollowing(false)} onPetClick={hello} hopSignal={helloCount} />
```

with:

```tsx
      <WorldCanvas store={store} position={state.position} seconds={seconds} arrival={arrival}
        following={following} onOrbit={() => setFollowing(false)} onPetClick={hello} hopSignal={helloCount}
        action={state.action} serverTime={serverTime} />
```

- [ ] **Step 8: Type check, lint and test**

Run: `cd frontend && npm test`
Expected: `Tests  127 passed (127)`

Run: `cd frontend && npm run build`
Expected: the build succeeds.

Run: `cd frontend && npx eslint src/survival src/components/world/PetEntity.tsx src/components/world/PetVoxels.tsx`
Expected: no output.

Visual checks of the pet happen in Task 12.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/world/PetVoxels.tsx frontend/src/components/world/PetEntity.tsx frontend/src/survival/SurvivalPet.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/survival/SurvivalWorld.tsx frontend/src/survival/hud.ts frontend/src/survival/hud.test.ts frontend/src/survival/SurvivalHud.tsx
git commit -m "feat: walk the pet along its path and act out each step" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Cracks, break particles, item pop and place bounce

**Files:**
- Create: `frontend/src/survival/ActionEffects.tsx`
- Modify: `frontend/src/survival/WorldCanvas.tsx`, `frontend/src/survival/SurvivalWorld.tsx`

**Interfaces:**
- Consumes: `crackStage`, `crackTexels`, `placeScale`, `burst`, `itemPop`, `blockEffects`, `CRACK_STAGES`, `BURST_SECONDS`, `POP_SECONDS`, `PLACE_BOUNCE_SECONDS` (Task 9); `poseAt` (Task 8); `WorldStore.getBlock`, `blockId`, `blockDef` (engine); `WorldCanvas` props from Task 10.
- Produces: `ActionEffects({ store, action, recent, position, now })` (default export); `WorldCanvas` gains `recentActions?: FinishedAction[]`.

While Mimo mines, a slightly larger see-through cube shows 8×8 pixel cracks that grow in six stages. When block sync removes the block (or 2 s after the step ends, whichever comes first), eight small cubes in the block's color burst out and fall, and a small cube pops up and flies to the pet. When a place step ends, a stand-in cube in the block's color scales in from 0.6 with a small bounce, and hides once block sync delivers the real block (at most 3 s). Steps that ended before the page opened are not replayed.

- [ ] **Step 1: Write the effects component**

Create `frontend/src/survival/ActionEffects.tsx`:

```tsx
import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { blockDef, blockId } from '../engine/blocks'
import type { WorldStore } from '../engine/worldStore'
import {
  BURST_SECONDS, CRACK_STAGES, PLACE_BOUNCE_SECONDS, POP_SECONDS, blockEffects, burst, crackStage, crackTexels,
  itemPop, placeScale, type BlockEffect,
} from './effects'
import { poseAt } from './motion'
import type { FinishedAction, MimoAction, Point } from './types'

const PARTICLES = 8
/** How long a break waits for block sync to remove the block before it plays anyway. */
const BREAK_WAIT = 2
/** How long a placed block's stand-in waits for block sync to deliver the real block. */
const GHOST_WAIT = 3
const CRACK_SIZE = 1.01
/** Fired keys are trimmed to the current steps once there are this many. */
const FIRED_LIMIT = 64

interface Playing {
  effect: BlockEffect
  /** Server time the animation began. */
  from: number
}

function paint(material: THREE.MeshLambertMaterial | null, block: string) {
  if (!material) return
  const [r, g, b] = blockDef(blockId(block)).color
  material.color.setRGB(r / 255, g / 255, b / 255, THREE.SRGBColorSpace)
}

function crackTexture(stage: number): THREE.DataTexture {
  const texture = new THREE.DataTexture(crackTexels(stage), 8, 8, THREE.RGBAFormat)
  texture.magFilter = THREE.NearestFilter
  texture.minFilter = THREE.NearestFilter
  texture.colorSpace = THREE.SRGBColorSpace
  texture.needsUpdate = true
  return texture
}

function center(cell: Point): Point {
  return { x: cell.x + 0.5, y: cell.y + 0.5, z: cell.z + 0.5 }
}

/**
 * Block effects of Mimo's steps: cracks on the block being mined, particles and an item that pops
 * to the pet when block sync removes a mined block, and a bounce when a block is placed.
 */
export default function ActionEffects({ store, action, recent, position, now }: {
  store: WorldStore
  action: MimoAction | null
  recent: FinishedAction[]
  position: Point
  /** Server time now, in seconds. */
  now: () => number
}) {
  const effects = useMemo(() => blockEffects(action, recent), [action, recent])
  const textures = useRef<THREE.DataTexture[]>([])
  const crack = useRef<THREE.Mesh>(null)
  const crackMaterial = useRef<THREE.MeshBasicMaterial>(null)
  const particles = useRef<THREE.InstancedMesh>(null)
  const particleMaterial = useRef<THREE.MeshLambertMaterial>(null)
  const pop = useRef<THREE.Mesh>(null)
  const popMaterial = useRef<THREE.MeshLambertMaterial>(null)
  const ghost = useRef<THREE.Mesh>(null)
  const ghostMaterial = useRef<THREE.MeshLambertMaterial>(null)
  const scratch = useRef<THREE.Object3D | null>(null)
  const fired = useRef(new Set<string>())
  const openedAt = useRef<number | null>(null)
  const breaking = useRef<Playing | null>(null)
  const placing = useRef<Playing | null>(null)

  useEffect(() => {
    const made = Array.from({ length: CRACK_STAGES + 1 }, (_, stage) => crackTexture(stage))
    textures.current = made
    return () => { for (const texture of made) texture.dispose() }
  }, [])

  useFrame(() => {
    const t = now()
    // Steps that ended before the page opened are not replayed.
    const since = (openedAt.current ??= t - 1)

    // Cracks grow on the block being mined until block sync removes it.
    const crackMesh = crack.current
    const crackMat = crackMaterial.current
    if (crackMesh && crackMat) {
      const stage = crackStage(action, t)
      const texture = textures.current[stage]
      const cell = action?.target
      const standing = action?.block !== undefined && cell !== undefined
        && store.getBlock(cell.x, cell.y, cell.z) === blockId(action.block)
      crackMesh.visible = stage > 0 && standing && texture !== undefined
      if (crackMesh.visible && cell && texture) {
        crackMesh.position.set(cell.x + 0.5, cell.y + 0.5, cell.z + 0.5)
        if (crackMat.map !== texture) {
          const hadMap = crackMat.map !== null
          crackMat.map = texture
          if (!hadMap) crackMat.needsUpdate = true
        }
      }
    }

    // Start breaks and placements when they are due.
    for (const effect of effects) {
      if (fired.current.has(effect.key) || effect.at <= since || t < effect.at) continue
      if (effect.kind === 'break') {
        const { x, y, z } = effect.cell
        const synced = store.getBlock(x, y, z) !== blockId(effect.block)
        if (!synced && t < effect.at + BREAK_WAIT) continue
        breaking.current = { effect, from: t }
        paint(particleMaterial.current, effect.block)
        paint(popMaterial.current, effect.block)
      } else {
        placing.current = { effect, from: effect.at }
        paint(ghostMaterial.current, effect.block)
      }
      fired.current.add(effect.key)
    }
    if (fired.current.size > FIRED_LIMIT) {
      const current = new Set(effects.map((effect) => effect.key))
      fired.current = new Set([...fired.current].filter((key) => current.has(key)))
    }

    // Break particles and the item flying to the pet.
    const broke = breaking.current
    const sinceBreak = broke ? t - broke.from : Infinity
    const burstMesh = particles.current
    if (burstMesh) {
      burstMesh.visible = broke !== null && sinceBreak < BURST_SECONDS
      if (burstMesh.visible && broke) {
        const dummy = (scratch.current ??= new THREE.Object3D())
        const origin = center(broke.effect.cell)
        burst(PARTICLES, sinceBreak).forEach((offset, index) => {
          dummy.position.set(origin.x + offset.x, origin.y + offset.y, origin.z + offset.z)
          dummy.scale.setScalar(1 - (0.5 * sinceBreak) / BURST_SECONDS)
          dummy.updateMatrix()
          burstMesh.setMatrixAt(index, dummy.matrix)
        })
        burstMesh.instanceMatrix.needsUpdate = true
      }
    }
    const item = pop.current
    if (item) {
      item.visible = broke !== null && sinceBreak < POP_SECONDS
      if (item.visible && broke) {
        const pet = poseAt(action, position, t)
        const flight = itemPop(sinceBreak, center(broke.effect.cell), { x: pet.x + 0.5, y: pet.y + 0.6, z: pet.z + 0.5 })
        item.position.set(flight.position.x, flight.position.y, flight.position.z)
        item.scale.setScalar(flight.scale)
      }
    }

    // A placed block bounces in until the real block arrives.
    const stand = ghost.current
    if (stand) {
      const placed = placing.current
      const sincePlace = placed ? t - placed.from : Infinity
      const cell = placed?.effect.cell
      const arrived = placed !== null && cell !== undefined
        && store.getBlock(cell.x, cell.y, cell.z) === blockId(placed.effect.block)
      stand.visible = cell !== undefined && sincePlace < GHOST_WAIT && !(arrived && sincePlace >= PLACE_BOUNCE_SECONDS)
      if (stand.visible && cell) {
        stand.position.set(cell.x + 0.5, cell.y + 0.5, cell.z + 0.5)
        stand.scale.setScalar(placeScale(sincePlace) * 1.002)
      }
    }
  })

  return (
    <>
      <mesh ref={crack} visible={false}>
        <boxGeometry args={[CRACK_SIZE, CRACK_SIZE, CRACK_SIZE]} />
        <meshBasicMaterial ref={crackMaterial} transparent depthWrite={false} />
      </mesh>
      <instancedMesh ref={particles} args={[undefined, undefined, PARTICLES]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.12, 0.12, 0.12]} />
        <meshLambertMaterial ref={particleMaterial} />
      </instancedMesh>
      <mesh ref={pop} visible={false}>
        <boxGeometry args={[0.3, 0.3, 0.3]} />
        <meshLambertMaterial ref={popMaterial} />
      </mesh>
      <mesh ref={ghost} visible={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshLambertMaterial ref={ghostMaterial} />
      </mesh>
    </>
  )
}
```

- [ ] **Step 2: Add the effects to the world canvas**

In `frontend/src/survival/WorldCanvas.tsx`:

Replace:

```tsx
import SurvivalPet from './SurvivalPet'
import type { MimoAction } from './types'
```

with:

```tsx
import ActionEffects from './ActionEffects'
import SurvivalPet from './SurvivalPet'
import type { FinishedAction, MimoAction } from './types'
```

Replace:

```tsx
const NO_TIME = () => 0
```

with:

```tsx
const NO_TIME = () => 0
const NO_ACTIONS: FinishedAction[] = []
```

Replace:

```tsx
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, serverTime }: {
```

with:

```tsx
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, recentActions = NO_ACTIONS, serverTime }: {
```

Replace:

```tsx
  action?: MimoAction | null
  serverTime?: () => number
}) {
```

with:

```tsx
  action?: MimoAction | null
  recentActions?: FinishedAction[]
  serverTime?: () => number
}) {
```

Replace:

```tsx
          </SurvivalPet>
```

with:

```tsx
          </SurvivalPet>
          {serverTime && <ActionEffects store={store} action={action} recent={recentActions} position={position} now={serverTime} />}
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
        action={state.action} serverTime={serverTime} />
```

with:

```tsx
        action={state.action} recentActions={state.recent_actions} serverTime={serverTime} />
```

- [ ] **Step 3: Type check, lint and test**

Run: `cd frontend && npm test`
Expected: `Tests  127 passed (127)`

Run: `cd frontend && npm run build`
Expected: the build succeeds.

Run: `cd frontend && npx eslint src/survival`
Expected: no output.

Visual checks of the effects happen in Task 12.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/survival/ActionEffects.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/survival/SurvivalWorld.tsx
git commit -m "feat: show mining cracks, break particles and placing bounces" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Manual check at 60× and the README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

Every check runs against a scratch Docker volume and a separately tagged image. The real `pets_mimo_data` volume is never mounted. At `MIMO_TIME_SCALE=60` a game day lasts 60 real seconds: 40 s of day, then 20 s of night. Steps keep their real durations. Vitals drain 60 times faster, so use the feed snippet from Step 3 whenever hunger gets low. If a check fails, fix the code in the task that owns it, re-run that task's tests, and repeat the check.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 194 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/components/world/PetEntity.tsx src/components/world/PetVoxels.tsx`
Expected: `Tests  127 passed (127)`, the build succeeds, eslint prints nothing.

- [ ] **Step 2: Build a scratch image and start a scratch world at 60×**

```bash
docker build -f backend/Dockerfile -t mimo-m2-check .
docker volume create mimo_m2_check
docker run --rm -v mimo_m2_check:/data -e MIMO_DB_PATH=/data/mimo.sqlite3 mimo-m2-check \
  python -c "from backend.services.live_mimo import MimoStore; MimoStore(); print('scratch legacy world ready')"
docker run -d --name mimo-m2-api -p 127.0.0.1:8001:8000 -v mimo_m2_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 mimo-m2-check
docker run -d --name mimo-m2-worker -v mimo_m2_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 -e MIMO_TICK_SECONDS=1 \
  mimo-m2-check python -m backend.workers.mimo_worker
```

Expected: `scratch legacy world ready`, then two container ids.

After a few seconds, hatch the egg:

```bash
curl -s -X POST http://127.0.0.1:8001/api/lives/hatch | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['life']['id'], d['life']['name'])"
```

Expected: `2 <name>`.

- [ ] **Step 3: Keep a feed snippet ready**

Save this as `feed.sh` in your scratchpad directory (not in the repo) and run it with `sh <scratchpad>/feed.sh` whenever Hunger or Health gets low during the checks:

```bash
docker exec -i mimo-m2-api python - <<'EOF'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    state["vitals"].update(hunger=100.0, health=100.0, air=100.0)
    write_state(db, state)
print("fed")
EOF
```

Expected: `fed`.

- [ ] **Step 4: Start the viewer against the scratch API**

Stop any other dev server on port 5173 first (the API only allows CORS from port 5173).

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8001 npm run dev -- --port 5173 --strictPort
```

Open `http://127.0.0.1:5173/preview?debug` in the Browser pane.

- [ ] **Step 5: Check the API stream**

```bash
curl -s http://127.0.0.1:8001/api/mimo | python3 -c "import json,sys; d=json.load(sys.stdin); a=d['action']; print(d['status'], a and a['kind'], a and a['started_at'] <= d['server_time'], len(d['recent_actions']))"
```

Expected (by day): a status such as `walking`, `mining` or `crafting`, the same step kind, `True`, and a count from 0 to 20. At night: `sleeping sleep True <count>`.

- [ ] **Step 6: Watch a day of the interim script**

Take screenshots and confirm each item:

- The pet walks toward a tree, one hop per block, turning to face each new direction. It steps up and down single blocks smoothly and never glides through the air.
- The HUD step line reads `Walking`, then `Mining oak log`, then `Crafting planks`.
- While mining, the pet swings toward the log and dark pixel cracks grow over about 2 seconds.
- When a log disappears, small log-colored cubes burst out and fall, and a small cube hops to the pet and shrinks away. The cracks vanish with the block.
- "What happened" shows `<name> crafted planks.`. **Blocks & crafting** shows the planks in the inventory.
- About 40 s after dawn, the pet lies down on its side with three z's rising and fading above it, and the HUD shows `Sleeping`. At dawn it gets up and goes back to work.
- `docker logs mimo-m2-worker 2>&1 | tail -5` shows status lines such as `<name> is mining: That tree has good wood.`.

- [ ] **Step 7: Check placing and eating**

Run this right after dawn:

```bash
docker exec -i mimo-m2-api python - <<'EOF'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    x, y, z = (round(state["position"][key]) for key in ("x", "y", "z"))
    state["inventory"]["planks"] = state["inventory"].get("planks", 0) + 2
    state["inventory"]["berries"] = 2
    state["vitals"]["hunger"] = 60.0
    state["action"] = None
    state["queue"] = [{"kind": "place", "target": [x + 1, y, z], "block": "planks"},
                      {"kind": "place", "target": [x + 1, y + 1, z], "block": "planks"},
                      {"kind": "eat", "item": "berries"}]
    write_state(db, state)
print("queued at", x, y, z)
EOF
```

Confirm:

- The pet leans toward the spot and a planks-colored cube scales in from small with a little bounce, twice (one on top of the other). The textured planks appear within a second or two and the stand-in disappears.
- Then the pet nibbles (quick nods) with crumbs falling in front of its mouth for about 1.6 s. Hunger rises by 8, and "What happened" shows `<name> ate berries.`.
- If a place shows `that cell is taken` in `recent_actions` (`curl -s http://127.0.0.1:8001/api/mimo | python3 -c "import json,sys; print(json.load(sys.stdin)['recent_actions'][-3:])"`), run the snippet again with `x - 1` instead of `x + 1`.

- [ ] **Step 8: Check a fall and the swim-up fallback**

Fall, by day:

```bash
docker exec -i mimo-m2-api python - <<'EOF'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    state["action"], state["queue"] = None, []
    state["position"]["y"] += 8
    write_state(db, state)
print("lifted")
EOF
```

Confirm: the pet drops with increasing speed, stretched and leaning back, lands, and Health falls by 50 (to about 50). "What happened" shows `<name> fell 8 blocks and got hurt.`. Run the feed snippet afterwards.

Swim-up, by day:

```bash
docker exec -i mimo-m2-api python - <<'EOF'
from backend.services.block_table import write_block
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    x, y, z = (round(state["position"][key]) for key in ("x", "y", "z"))
    for dy in range(3):
        write_block(db, x, y + dy, z, "water")
    state["action"], state["queue"] = None, []
    write_state(db, state)
print("water column at", x, y, z)
EOF
```

Confirm: the pet rises through the water column, bobbing low, and floats on top (`Swimming` in the HUD). The Air bar dips while its head is under water and refills once it is on top. Then it steps off the column (a drop of up to 3) and goes back to its trees.

- [ ] **Step 9: Restart the worker mid-walk**

While the HUD shows `Walking`:

```bash
docker restart mimo-m2-worker
```

Confirm: the pet keeps walking along the same path without jumping back, and a few seconds later `docker logs mimo-m2-worker 2>&1 | tail -3` shows the worker started again with status lines continuing.

- [ ] **Step 10: Check the phone layout and frame rate**

Resize the Browser pane to the mobile preset and reload. Confirm the pet still walks, mines and sleeps with its animations, the HUD shows the step line, and the `?debug` frame rate stays close to the desktop value while the pet mines (note both numbers). Reset the viewport to desktop afterwards.

- [ ] **Step 11: Clean up the scratch run**

Stop the dev server (Ctrl+C), then remove only what this task created:

```bash
docker rm -f mimo-m2-api mimo-m2-worker
docker volume rm mimo_m2_check
docker image rm mimo-m2-check
```

- [ ] **Step 12: Describe actions in the README**

In `README.md`, replace:

```markdown
- Until the brain milestone, the pet stands where it hatched and sleeps at night or when exhausted.
```

with:

```markdown
- Until the brain milestone, a stand-in script runs the pet by day, and it sleeps at night or when exhausted. See Actions.
```

Replace:

```markdown
## Current world rules
```

with:

````markdown
## Actions

- Mimo is one block tall. It stands in an open cell with a solid block or water below it. The server finds paths with 3D A*: one block to a side, one block up when there is headroom, or down a drop of at most 3 blocks. On water it swims on the surface at a third of its walking speed and never plans a route under water. A search looks at no more than 20,000 cells within 96 blocks; farther places are reached in segments.
- Every step takes time: walking 0.3 s per block (0.9 s swimming), mining the block's hardness divided by the tool speed (hand 1; wooden, stone and iron pickaxes 2, 4 and 6 on stone-type blocks), placing 0.3 s, eating 1.6 s, crafting 1 s and smelting 5 s. Sleep lasts until Mimo is rested and it is day. Mimo mines and places within 4 blocks. Mining still needs the right pickaxe and gives the block's drop. `hardness` and `tool` live in `shared/blocks.json`.
- The worker runs the steps once a second, so several short steps can finish in one tick. The current step, the queue and the last 20 finished steps are saved with the world, so a restarted worker carries on where it stopped.
- A block dug out from under Mimo makes it fall. A fall deals (blocks − 3) × 10 damage, and water breaks a fall. Air drains while Mimo's cell is water; until the brain milestone Mimo then swims straight up.
- `/api/mimo` streams the current step (`action`: kind, start and end time, and a timed path or a target block) and `recent_actions`. The viewer moves the pet along the path by server time and animates each step: a hop per block, a swing and growing cracks while mining, particles and an item pop when a block breaks, a bounce when a block is placed, nibbling with crumbs, lying down with floating z's, bobbing in water and a quickening drop when falling.
- The stand-in script (`backend/survival/script.py`, replaced by the brain milestone): by day Mimo walks to the nearest tree within 24 blocks, chops its logs and crafts them into planks, and walks out to look for trees when none is near. `MIMO_TIME_SCALE` speeds the clock and the vitals, not the steps, so the animations stay watchable in a fast test run.

## Current world rules
````

- [ ] **Step 13: Run every check again and commit**

Run: `python3 -m unittest discover -s backend/tests && cd frontend && npm test && npm run build`
Expected: `Ran 194 tests` … `OK`, `Tests  127 passed (127)`, the build succeeds.

```bash
git add README.md
git commit -m "docs: describe Mimo's timed actions and the interim script" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (M2) | Where |
|-----------|-------|
| §6 body: one cell, stands on solid or water | Tasks 2 (`standable`), 3 |
| §6 3D A*: 4 neighbors, step up 1 with headroom, drop ≤ 3, swim ×3, no corner cutting | Task 3 |
| §6 budget 20,000 nodes and 96 blocks, segments toward waypoints | Tasks 3 (`route`), 5 (re-queued segments) |
| §6 reach 4, no line of sight | Task 4 (`in_reach`) |
| §6 1 s tick, several steps finish per tick | Tasks 5, 6 |
| §6 durations: walk, swim, mine (hardness ÷ tool speed), place, eat, craft, smelt, sleep | Tasks 1, 3, 4, 5 |
| §6 hardness table in the registry, tool speeds, axes double wood | Tasks 1, 4 |
| §6 mining needs `requires`, yields `drop`; placing consumes the item; writes through `write_block` | Tasks 2 (`put`), 4 |
| §6 falls with `(blocks − 3) × 10` damage | Task 5 |
| §6 air drains in water; planner avoids water it cannot cross; fallback swims up | Tasks 3 (surface-only routes), 5 (`start_hazard`), M1 vitals |
| §6 `/api/mimo` gains `server_time`, `action` (kind, started_at, ends_at, path with arrival times or target) | M1 (`server_time`), Task 7 |
| §6 viewer: interpolate along the path; walk hop and facing; mine swing, cracks, particles, item pop; place bounce; eat nibble with crumbs; sleep lying down with z's; fall accelerated drop; swim bobbing | Tasks 8–11 |
| §9 HUD step in plain words | Task 10 (`actionText`) |
| §12 worker restarts mid-action resume from stored times; walks snap to the last reached cell | Tasks 5 (`follow_path`), 6 (restart test), 12 Step 9 |
| §12 clock-jump catch-up keeps working with actions | Task 6 |
| §13 pathfinding tests (step up, drop limits, swimming cost, blocked routes, segments) | Task 3 |
| §13 action tests (mining with and without tools, placing consumes items, fall damage) | Tasks 4, 5 |
| §13 viewer unit tests for action interpolation | Tasks 8, 9 |
| §13 manual 60× run on a scratch world | Task 12 |

Out of scope here (later milestones): reflexes, purposes and the real planner (M3, which replaces `script.py`), food items, beds and campfires (M4), axe recipes and building (M5), lava damage and flowing water (sub-project 5).
