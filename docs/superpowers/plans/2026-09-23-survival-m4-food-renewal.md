# Survival M4: Food and Renewal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the survival world real food and a world that grows back: berry bushes, mushrooms, crops, saplings and fish; the steps to pick, harvest, till, plant, fish and cook; the purposes forage, fish, farm and cook; a growth table the worker applies each tick; leaf decay with its drops; and a viewer that draws the new blocks, the new steps and a puff as each leaf goes.

**Architecture:** The shared block registry gains 19 blocks at its end and the soft-pixel atlas their tiles; worldgen grows ripe berry bushes and mushrooms on generated land in both languages. The step engine first becomes a registry (`steps.StepKind`), so M4's field work (`backend/survival/fieldwork.py`, rules in `nature.py`) plugs in without touching the engine. Renewal is world physics, not part of the mind: `advance_world` runs `renewal.renew` after each catch-up chunk of actions, which reacts to the blocks Mimo changed (`Grid.take_changes`) and applies due rows of the world database's `growth` table in time order. The brain gains senses for food, grass, water and grown trees, memory for food patches, fires, the farm and learned facts (poisonous food), and four purposes in new modules (`foraging`, `farming`, `cooking`) that register themselves like M3's.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-survival-core-design.md` (M4: section 7 "Food and renewal", and M4's parts of sections 5, 9, 10, 12 and 13). It builds on `docs/superpowers/plans/2026-09-23-survival-m3-brain.md`. The code on branch `worthy/23_09_2026/survival_core` at `8b539ea` (M3 and its fix wave) is the "old" text every task edits; the dry run applied every task to that commit.

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls. Chance is rolled by `backend.survival.nature.roll`; tests patch it where an outcome must be forced.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments (mutate three.js objects only through refs inside `useFrame`, effects or event handlers), no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. Read-only GETs never write. Schema setup runs at most once per process per path (`_ensure_world_schema`), and every schema change is idempotent (`CREATE ... IF NOT EXISTS`, a column added only when `PRAGMA table_info` lacks it). The legacy world file is only ever opened read-only.
- **No model call inside the tick.** Renewal, senses and planners are rules. M4's planners do no path search of their own (walks search when they start, within the tick's budget of 2).
- A crashing renewal pass, planner, reflex, hook or picker never stops a tick or the worker. Crashes are logged once per distinct error (`backend.survival.once.log_once`).
- `shared/blocks.json` ids are positions: new blocks are appended after `flower_yellow`, never inserted. Worldgen changes go into `backend/services/worldgen.py` and `frontend/src/engine/worldgen.ts` together, and `shared/worldgen-fixture.json` is regenerated with `python3 -m backend.scripts.worldgen_fixture`. The retired legacy world (within 192 blocks of the origin) must render exactly as before.
- Values copied from the spec (section 7): berries +8 from a ripe bush that becomes unripe; brown mushroom +6; red mushroom poisonous, −10 health, and memory learns it; carrot +10, replant to grow more; wheat 0, 3 wheat → 1 bread at a crafting table; bread +25; raw fish +8, 20–60 s per catch, success depends on the water's stock; cooked fish +30, 5 s at a lit campfire or furnace; seeds 20% from tall grass; sapling 1 in 12 and apple (+15) 1 in 20 when leaves are removed or decay; a picked berry bush regrows ripe after 2 game days; crops advance one stage every 12 game minutes on farmland with water within 4 blocks and every 36 otherwise; a sapling becomes a tree after 1 game day if there is space; fish stock per 16×16 water region starts at 12 and recovers 1 per game day; farmland reverts to dirt after 2 game days without a crop; leaves with no log within 4 blocks (through leaves and logs) vanish at a random time in the next 1 to 6 game minutes, with a puff in the viewer; mushrooms reappear on forest floor, one per chunk per game day, at most 3 per chunk; ore never regrows. Section 5: eat now = hunger < 15 with food; warm up = warmth < 25, go to a warm spot or light a campfire Mimo has; `cook` needs raw food and a lit fire or furnace nearby.
- `MIMO_TIME_SCALE` and `MIMO_ACTION_SCALE` (both default 1) are for manual runs only. M4 adds no settings.
- Never run `docker` or `docker compose` in Tasks 1–15. Task 16 is the controller's manual check on a scratch volume; never touch, mount or migrate the owner's real volume `pets_mimo_data`.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (361 pass at `8b539ea`)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_renewal.py" -v`
- Frontend tests: `cd frontend && npm test` (164 pass at `8b539ea`)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint <paths>`
- Parity fixture after a worldgen change: `python3 -m backend.scripts.worldgen_fixture`

Each task says how many tests it adds. If the real starting totals differ, expect the same increases on top of them.

Transcription: the plan's edits are fenced blocks (new files, "replace: … with: …" pairs, "the whole `name` function", "at the end of `Class`", "append"), as in M3. Task 1 edits `shared/blocks.json` and Task 3 regenerates `shared/worldgen-fixture.json` with the command above; the M3 apply script only recognises `.py`, `.ts`, `.tsx`, `.md`, `.yml` and `.example` paths, so the dry run used a copy whose path pattern also accepts `.json` (a one-word change) and ran the fixture command by hand.

## Plan-level resolutions

The spec leaves these open or ambiguous. Every task follows them; the controller ledgers them.

1. **Game time units** stay M3's: a game minute is 60 game seconds and a game day (M3's "game hour") 3,600. So berry regrowth and farmland reverting take 7,200 game seconds, a crop stage 720 (water near) or 2,160, a sapling 3,600, leaf decay 60–360 and fish recover one per 3,600.
2. **New blocks** are appended after `flower_yellow` (ids 40–58): `berry_bush`, `berry_bush_ripe`, `brown_mushroom`, `red_mushroom`, `farmland`, `wheat_0`–`wheat_3`, `carrot_0`–`carrot_3`, `sapling`, `campfire`, `torch`, `bed`, `chest`. Plants, crops, sapling, campfire and torch are `cutout`, `solid: false` and not replaceable; farmland, bed and chest are opaque cubes. Crop tiles take a `size` (1–4) for their stage.
3. **Bed, chest and torch** are registered with textures now so their ids are fixed, but their recipes and uses (sleeping in a bed, storage, lights) are M5's. The campfire gets its recipe now (2 logs and 3 sticks, no station), glows, and drops itself when mined.
4. **Wild food** grows only beyond the legacy radius, so the retired world renders unchanged: a ripe berry bush in 1 of 97 meadow or forest-edge columns (forest with moisture below 0.16), a mushroom in 1 of 67 forest columns and on 1 of 29 cave-floor cells, a third of the mushrooms red. Bushes generate ripe.
5. **Water for fishing** is worldgen's existing sea-level water (ground below sea level); no new water is generated.
6. **Chance** is `nature.roll(seed, cell, channel, salt)`, a number in [0, 1) fixed by the world seed, so drops, decay times, fishing times and catches and mushroom spots replay the same and tests can patch one function.
7. **Drops:** tall grass gives seeds 1 in 5 and a carrot 1 in 20 (the spec names no source for the first carrot); leaves give a sapling 1 in 12 and an apple 1 in 20, whether mined or decayed.
8. **Decay drops** have no item entities to land as: Mimo gathers them when it is within 16 blocks (horizontally) of the leaf, otherwise they are lost.
9. **Red mushroom:** +6 hunger and −10 health, never taking the last point (poison is not in the spec's causes of death). Eating one teaches memory that red mushrooms are poisonous; from then on eat, eat now and forage leave them alone. Until then Mimo may eat one.
10. **Step registry first** (M3 review): `steps.StepKind` holds start, finish, status, work, interruptible and the checked fields; `actions` reads it. M4's kinds live in `backend/survival/fieldwork.py`, imported at the end of `steps.py` so `start_step` always knows them.
11. **New steps:** pick 0.5 s, harvest 0.5 s, till 1 s (by hand; no hoe exists), plant 0.3 s, fish 20–60 s, cook 5 s; each on a cell within reach 4, and the action scale divides them. Fishing is interruptible and not work; pick, harvest, till and plant are work.
12. **Yields:** a ripe bush gives 3 berries and turns back into an unripe bush; a mushroom gives itself; `wheat_3` gives 1 wheat and 2 seeds, `carrot_3` 3 carrots; the farmland stays. Seeds grow `wheat_0`, a carrot `carrot_0`, a sapling `sapling` (on grass, dirt or moss).
13. **Cooking** is `crafting.smelt`'s new food rule (raw fish at a campfire or furnace within 6 blocks, no fuel) run by a `cook` step; ore smelting keeps its furnace and fuel. Bread is a crafting recipe (3 wheat at a crafting table).
14. **Fish stock** lives in `state["fish"]` per 16×16 region (`"rx,rz"`, full regions left out); a catch succeeds with chance 0.9 × stock / 12 and takes one fish; renewal adds one per game day.
15. **Renewal is world physics** (M3 review): `renewal.renew` runs inside `advance_world` after each catch-up chunk of actions and after the last, whatever mind runs Mimo. It reacts to the changes Mimo's steps made (`Grid.take_changes`) and applies due `growth` rows oldest first; its own writes need no reaction.
16. **Growth rows** only happen while their cell holds what they grow from (an unripe bush, the crop one stage earlier, bare farmland, a sapling). Crops chain their stages from each stage's own due time. "Water within 4 blocks" is |dx| and |dz| ≤ 4 and |dy| ≤ 1 from the farmland. A sapling without room tries again every 10 game minutes and never grows a trunk through Mimo.
17. **Leaf decay:** the candidates are leaves within 4 steps of the removed log, through leaves; each that no longer reaches a log within 4 steps (through leaves and logs) is scheduled at 1–6 game minutes. `state["decays"]` keeps the newest 24 (`{x, y, z, at}`) and `/api/mimo` sends them as `decays`.
18. **Mushroom respawn:** a picked mushroom schedules one of its kind on forest grass or moss in its chunk, a game day after the latest one already coming there (one per chunk per game day); it grows only while the chunk has fewer than 3. "Dark forest floor" means the forest biome until light levels arrive (sub-project 3).
19. **Memory** (M3 review): `memory_places` gains a JSON `data` column (added when missing) and `update_place`; places are read in a bounded box (a Situation reads 256 blocks around Mimo); a `memory_knowledge` table keeps learned facts. New place kinds: `food` (one per 8 blocks), `fire` (exact cells) and `farm` (one per 16 blocks).
20. **Food patches:** picking remembers the patch within 8 blocks with `{"ripe", "seen_at"}`; forage walks back to a patch beyond sight but within 64 blocks that still had ripe food, or was picked clean at least 2 game days ago.
21. **Purposes** forage, fish and farm are day work; all four register from new modules that `brain.py` imports. Late in the day forage, fish and farm take the fix wave's outdoor penalty (`purposes.late_penalty`). Their planners leave alone places within 4 blocks of where a step just failed (`senses.near_failure`), and their walks are `whole` (`foraging.whole_walk`): all the way or not at all, because the partial route M2 walks toward an unreachable target can end in a pit or a cave, from which the next bush or plot is unreachable too. A remembered farm more than 24 blocks away is only walked back to when work waits there.
22. **Score bands** (M3 review) are documented in `purposes.py`: survival 80–100, needs 50–80, work 40–70, leisure 10–40. forage = 35 + need / 3 + (100 − hunger) / 3, fish = 25 + the same + patience / 10, where need is the hunger points Mimo lacks of 60 carried; farm = 40 + diligence / 10 + patience / 20, +25 with ripe crops, +10 with something to plant; cook = 50 + (100 − hunger) / 4 + 5 per serving, at most 80.
23. **Farm site:** the first plot goes beside the nearest shore within 16 blocks (else under Mimo), later ones around the remembered farm; up to 9 plots, 4 per batch; carrots are planted before seeds; with nothing to plant, Mimo breaks tall grass for seeds.
24. **Cook's fire** is a carried campfire or furnace, else a campfire crafted on the spot, placed in toolmaking's station spots (a dug niche below the surface) and mined back with `keep` steps (M3 review; since `8b539ea` a failed kept step is not charged to the purpose); else Mimo walks to a fire within 32 blocks.
25. **Warm up** lights a carried campfire first, then a carried furnace, and otherwise walks to a shelter, campfire or furnace within 64 blocks.
26. **Trees come back only from saplings:** gather_wood plants up to 2 carried saplings per batch within reach, at least 3 blocks from any trunk or sapling, where the 6 cells above are open. Trees grown from saplings (placed logs) count as trees to chop.
27. **Events:** `ate`, `cook`, `fish` and `grow` are routine (left off memorials); `sick` stays notable.
28. **Viewer:** pick and harvest burst like a break; till and plant show through block sync; fishing has a lean-over pose; each decayed leaf shows a puff of leaf bits for 0.8 s at replay time.
29. **The farm is safe from stairs:** gather_stone digs down from wherever Mimo stands, which after farming is often the farm, so a stair never digs up farmland or a sapling, or the ground under one (`work.TENDED`).
30. **Purpose-change budget:** the fix wave's headless check allows 30 purpose events in a game hour; M4's food work adds a food purpose and the return from it several times a day, so Task 10 raises the budget to 36 (measured after all of M4: at most 30 at the default settings and 33 with `MIMO_SLOW_TESTS=1`, against 23 for M3 alone).
31. **An M3 fix, first in Task 7:** mine_ore never mines an ore that is the floor of an open cell below the natural surface (`work.passage_floor`), the rule `stair` already follows. Leaf decay changes what the fix wave's headless check does, and on seed 3 mine_ore otherwise cuts a stair and seals Mimo in for the night.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `shared/blocks.json` | Modify | 19 food and camp blocks and their 20 tiles, appended |
| `frontend/src/engine/blocks.ts`, `atlas.ts` (+ tests) | Modify | Tile `size`; 12 soft-pixel painters for the new tiles |
| `backend/services/crafting.py` | Modify | Bread and campfire recipes; raw fish cooks at a campfire or furnace without fuel |
| `backend/services/worldgen.py`, `frontend/src/engine/worldgen.ts` (+ tests) | Modify | `wild_food`/`wildFood` and `cave_plant`/`cavePlant`, in both languages |
| `backend/scripts/worldgen_fixture.py`, `shared/worldgen-fixture.json` | Modify | Sample wild food and cave mushrooms; regenerated |
| `backend/survival/steps.py` | Modify | Food and poison tables; the `StepKind` registry; chance drops when mining; `whole` walks |
| `backend/survival/actions.py` | Modify | Status, work and interrupts read from the registry |
| `backend/survival/nature.py` | Create | Picks, harvests, seeds and soil, crop stages, chance drops, `roll`, fish stocks |
| `backend/survival/fieldwork.py` | Create | Step kinds pick, harvest, till, plant, fish and cook |
| `backend/survival/grid.py` | Modify | Keep each change until `take_changes` |
| `backend/survival/renewal.py` | Create | The `growth` table, reacting to changes, applying due growth, leaf decay, trees, mushrooms, fish recovery |
| `backend/survival/tick.py` | Modify | `run_renewal` after each chunk of actions |
| `backend/survival/world.py` | Modify | The growth table in the schema; M4's routine events |
| `backend/survival/snapshot.py` | Modify | `decays` in `/api/mimo` |
| `backend/survival/senses.py` | Modify | Wild plants per chunk, ripe food, tall grass, shores, grown trees, trunks, places near a failed step |
| `backend/survival/situation.py` | Modify | `sensed` memo, bounded places, `poisons` |
| `backend/survival/memory.py` | Modify | Place `data`, `update_place`, bounded `places`, `know`/`known` |
| `backend/survival/learning.py` | Create | What finished M4 steps teach: poison, food patches, fires, the farm |
| `backend/survival/purposes.py` | Modify | Poison-aware `foods`/`meal` and eat; score bands |
| `backend/survival/reflexes.py` | Modify | eat_now skips poison; warm_up lights a campfire |
| `backend/survival/foraging.py` | Create | forage and fish, `reach_steps` |
| `backend/survival/farming.py` | Create | farm |
| `backend/survival/cooking.py` | Create | cook |
| `backend/survival/work.py` | Modify | mine_ore leaves ores in passage floors alone (an M3 fix); gather_wood plants saplings; stairs never dig up farmland or saplings |
| `backend/survival/brain.py` | Modify | Imports the new purposes; observe_step calls `learn_from_step` |
| `backend/tests/test_survival_*.py`, `test_blocks.py`, `test_worldgen.py` | Create/Modify | One test file per new module, additions to existing ones; the headless check's purpose-change budget |
| `frontend/src/survival/types.ts`, `hud.ts`, `animation.ts`, `effects.ts` (+ tests) | Modify | New step kinds and purposes, fishing pose, pick/harvest bursts, leaf puffs |
| `frontend/src/survival/LeafPuffs.tsx` | Create | Draws the puffs |
| `frontend/src/survival/WorldCanvas.tsx`, `SurvivalWorld.tsx` | Modify | Pass `decays` to `LeafPuffs` (small anchors, away from the camera code) |
| `README.md` | Modify | Food and renewal |

## Tasks

1. Food and camp blocks with soft-pixel textures
2. Food items, bread and campfire recipes, cooking at a fire
3. Wild food in worldgen, in both languages
4. A step registry
5. Field work: pick, harvest, till, plant, fish and cook
6. Renewal: the growth table in the tick
7. Trees, leaves and mushrooms come back or go (first an M3 fix: mine_ore leaves passage floors alone)
8. Senses for food, grass, water, grown trees and failed places
9. Memory of food patches, fires, the farm and poison
10. Forage and fish
11. Farm
12. Cook, and warm up by a campfire
13. gather_wood plants saplings
14. Score bands, routine events and three days on its own
15. Viewer: food work, farm work and leaf puffs
16. Manual check at 60× and the README

Tasks that edit files the M3 fix wave changed (their anchors are small and were dry-run against `8b539ea`; re-check them if more fix commits land): 4 (`actions.py`), 7 (`snapshot.py`, `work.py`), 9 (`purposes.py`, `reflexes.py`, `brain.py`), 10 (`brain.py`, `test_survival_sim.py`), 11 (`brain.py`, `work.py`), 12 (`brain.py`, `reflexes.py`), 13 (`work.py`), 14 (`purposes.py`, `world.py`), 15 (`WorldCanvas.tsx`, `SurvivalWorld.tsx`).

---
### Task 1: Food and camp blocks with soft-pixel textures

**Files:**
- Modify: `shared/blocks.json`, `frontend/src/engine/blocks.ts`, `frontend/src/engine/atlas.ts`
- Test: `backend/tests/test_blocks.py`, `frontend/src/engine/atlas.test.ts`, `frontend/src/engine/blocks.test.ts`

**Interfaces:**
- Consumes: the registry format of `shared/blocks.json` (tiles with `pattern`, `color`, `accent`; blocks with `name`, `color`, `textures`, `layer`, `solid`, `replaceable`, `drop`, `hardness`, `tool`, `glow`), `backend.services.blocks` and `frontend/src/engine/atlas.ts` `PATTERNS`.
- Produces:
  - Blocks, in this order after `flower_yellow` (ids 40–58): `berry_bush`, `berry_bush_ripe`, `brown_mushroom`, `red_mushroom`, `farmland`, `wheat_0`, `wheat_1`, `wheat_2`, `wheat_3`, `carrot_0`, `carrot_1`, `carrot_2`, `carrot_3`, `sapling`, `campfire`, `torch`, `bed`, `chest`. Drops: unripe wheat `seeds`, `wheat_3` `wheat`, carrots `carrot`, mushrooms themselves, sapling `sapling`, campfire `campfire`, farmland `dirt`, bushes nothing. The campfire (hardness 2.0, tool `axe`) and torch glow.
  - Tiles `berry_bush`, `berry_bush_ripe`, `brown_mushroom`, `red_mushroom`, `farmland_top`, `wheat_0`–`wheat_3`, `carrot_0`–`carrot_3`, `sapling`, `campfire`, `torch`, `bed_top`, `bed_side`, `chest_top`, `chest_side`.
  - `frontend/src/engine/blocks.ts`: `TileRecipe.size?: number` (crop stage 1–4).
  - `frontend/src/engine/atlas.ts` patterns: `sprite_bush`, `sprite_mushroom`, `furrows`, `sprite_crop`, `sprite_leafy`, `sprite_sapling`, `sprite_campfire`, `sprite_torch`, `bed_top`, `bed_side`, `chest_top`, `chest_side`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_blocks.py`, replace:

```python
    "furnace": {"color": [88, 91, 89], "drop": "furnace", "glow": True},
}
```

with:

```python
    "furnace": {"color": [88, 91, 89], "drop": "furnace", "glow": True},
}
# M4's blocks, in registry order after the older ones.
FOOD_AND_CAMP = ("berry_bush", "berry_bush_ripe", "brown_mushroom", "red_mushroom", "farmland",
                 "wheat_0", "wheat_1", "wheat_2", "wheat_3", "carrot_0", "carrot_1", "carrot_2", "carrot_3",
                 "sapling", "campfire", "torch", "bed", "chest")
CUBES = ("farmland", "bed", "chest")
```

In `backend/tests/test_blocks.py`, add these tests at the end of `BlockRegistryTests`:

```python
    def test_food_and_camp_blocks_come_after_the_older_blocks(self):
        names = [block["name"] for block in BLOCK_LIST]
        self.assertEqual(names[BLOCK_IDS["flower_yellow"] + 1:], list(FOOD_AND_CAMP))

    def test_plants_crops_and_fires_are_see_through_and_kept_when_building(self):
        for name in FOOD_AND_CAMP:
            if name in CUBES:
                self.assertTrue(is_solid(name), name)
                continue
            self.assertTrue(is_plant(name), name)
            self.assertFalse(is_solid(name), name)
            self.assertFalse(is_replaceable(name), name)
        self.assertTrue(BLOCKS["campfire"]["glow"])
        self.assertTrue(BLOCKS["torch"]["glow"])
        self.assertEqual(hardness("wheat_2"), 0.1)
        self.assertEqual(mining_tool("campfire"), "axe")

    def test_plants_drop_what_grows_on_them(self):
        drops = {"wheat_0": "seeds", "wheat_3": "wheat", "carrot_1": "carrot", "sapling": "sapling",
                 "brown_mushroom": "brown_mushroom", "berry_bush_ripe": None, "farmland": "dirt", "campfire": "campfire"}
        for name, drop in drops.items():
            self.assertEqual(BLOCKS[name]["drop"], drop, name)
```

In `frontend/src/engine/atlas.test.ts`, replace:

```ts
  it('insets uvs by a quarter texel', () => {
```

with:

```ts
  it('draws the food and camp sprites on see-through tiles and the new cubes solid', () => {
    const alphas = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).map((pixel) => pixel[3])
    for (const name of ['berry_bush', 'berry_bush_ripe', 'brown_mushroom', 'red_mushroom', 'wheat_0', 'wheat_3',
      'carrot_0', 'carrot_3', 'sapling', 'campfire', 'torch']) {
      expect(alphas(name), name).toContain(0)
    }
    for (const name of ['farmland_top', 'bed_top', 'bed_side', 'chest_top', 'chest_side']) {
      expect(Math.min(...alphas(name)), name).toBe(255)
    }
  })

  it('grows crop sprites with each stage and puts berries on the ripe bush only', () => {
    const shown = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).filter((pixel) => pixel[3] > 0).length
    expect(shown('wheat_0')).toBeLessThan(shown('wheat_1'))
    expect(shown('wheat_1')).toBeLessThan(shown('wheat_2'))
    expect(shown('wheat_2')).toBeLessThan(shown('wheat_3'))
    expect(shown('carrot_0')).toBeLessThan(shown('carrot_1'))
    expect(shown('carrot_1')).toBeLessThan(shown('carrot_2'))
    const red = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!)
      .filter((pixel) => pixel[3] > 0 && pixel[0] > pixel[1] + 60).length
    expect(red('berry_bush')).toBe(0)
    expect(red('berry_bush_ripe')).toBeGreaterThan(3)
  })

  it('insets uvs by a quarter texel', () => {
```

In `frontend/src/engine/blocks.test.ts`, replace:

```ts
    expect(LAYER_BY_ID[MISSING_ID]).toBe(LAYER_OPAQUE)
  })
})
```

with:

```ts
    expect(LAYER_BY_ID[MISSING_ID]).toBe(LAYER_OPAQUE)
  })

  it('adds the food and camp blocks after the existing ones, so older ids never change', () => {
    expect(blockId('berry_bush')).toBe(blockId('flower_yellow') + 1)
    expect(blockId('chest')).toBe(BLOCKS.length - 1)
    for (const name of ['berry_bush_ripe', 'red_mushroom', 'wheat_2', 'carrot_3', 'sapling', 'campfire', 'torch']) {
      expect(LAYER_BY_ID[blockId(name)], name).toBe(LAYER_CUTOUT)
      expect(blockDef(blockId(name)).solid, name).toBe(false)
    }
    expect(LAYER_BY_ID[blockId('farmland')]).toBe(LAYER_OPAQUE)
    expect(blockDef(blockId('farmland')).textures).toEqual({ top: 'farmland_top', side: 'dirt', bottom: 'dirt' })
    expect(GLOW_BY_ID[blockId('campfire')]).toBe(1)
    expect(GLOW_BY_ID[blockId('torch')]).toBe(1)
    expect(GLOW_BY_ID[blockId('sapling')]).toBe(0)
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_blocks.py"`
Expected: the 3 new tests fail (for example `KeyError: 'wheat_0'`).

Run: `cd frontend && npx vitest run src/engine/atlas.test.ts src/engine/blocks.test.ts`
Expected: the 3 new tests fail (the registry test with `expected 255 to be 40`).

- [ ] **Step 3: Append the blocks and tiles to the registry**

In `shared/blocks.json`, replace:

```json
    "flower_yellow": {"pattern": "sprite_flower", "color": [250, 218, 139], "accent": [90, 151, 113]}
  },
```

with:

```json
    "flower_yellow": {"pattern": "sprite_flower", "color": [250, 218, 139], "accent": [90, 151, 113]},
    "berry_bush": {"pattern": "sprite_bush", "color": [92, 146, 104]},
    "berry_bush_ripe": {"pattern": "sprite_bush", "color": [92, 146, 104], "accent": [214, 84, 98]},
    "brown_mushroom": {"pattern": "sprite_mushroom", "color": [176, 132, 96], "accent": [236, 222, 196]},
    "red_mushroom": {"pattern": "sprite_mushroom", "color": [214, 82, 72], "accent": [236, 222, 196]},
    "farmland_top": {"pattern": "furrows", "color": [104, 82, 66]},
    "wheat_0": {"pattern": "sprite_crop", "color": [120, 170, 96], "size": 1},
    "wheat_1": {"pattern": "sprite_crop", "color": [120, 170, 96], "size": 2},
    "wheat_2": {"pattern": "sprite_crop", "color": [150, 176, 92], "size": 3},
    "wheat_3": {"pattern": "sprite_crop", "color": [204, 178, 102], "accent": [236, 208, 130], "size": 4},
    "carrot_0": {"pattern": "sprite_leafy", "color": [108, 168, 98], "size": 1},
    "carrot_1": {"pattern": "sprite_leafy", "color": [108, 168, 98], "size": 2},
    "carrot_2": {"pattern": "sprite_leafy", "color": [108, 168, 98], "size": 3},
    "carrot_3": {"pattern": "sprite_leafy", "color": [108, 168, 98], "accent": [236, 138, 72], "size": 4},
    "sapling": {"pattern": "sprite_sapling", "color": [101, 164, 128], "accent": [139, 105, 82]},
    "campfire": {"pattern": "sprite_campfire", "color": [247, 170, 88], "accent": [120, 86, 62]},
    "torch": {"pattern": "sprite_torch", "color": [250, 214, 120], "accent": [139, 105, 82]},
    "bed_top": {"pattern": "bed_top", "color": [196, 92, 88], "accent": [238, 226, 204]},
    "bed_side": {"pattern": "bed_side", "color": [196, 92, 88], "accent": [169, 117, 72]},
    "chest_top": {"pattern": "chest_top", "color": [186, 138, 88], "accent": [120, 84, 52]},
    "chest_side": {"pattern": "chest_side", "color": [186, 138, 88], "accent": [120, 84, 52]}
  },
```

and replace:

```json
    {"name": "flower_yellow", "color": [250, 218, 139], "textures": "flower_yellow", "layer": "cutout", "solid": false, "replaceable": true, "drop": "flower_yellow", "hardness": 0.1}
  ]
```

with:

```json
    {"name": "flower_yellow", "color": [250, 218, 139], "textures": "flower_yellow", "layer": "cutout", "solid": false, "replaceable": true, "drop": "flower_yellow", "hardness": 0.1},
    {"name": "berry_bush", "color": [92, 146, 104], "textures": "berry_bush", "layer": "cutout", "solid": false, "drop": null, "hardness": 0.1},
    {"name": "berry_bush_ripe", "color": [214, 84, 98], "textures": "berry_bush_ripe", "layer": "cutout", "solid": false, "drop": null, "hardness": 0.1},
    {"name": "brown_mushroom", "color": [176, 132, 96], "textures": "brown_mushroom", "layer": "cutout", "solid": false, "drop": "brown_mushroom", "hardness": 0.1},
    {"name": "red_mushroom", "color": [214, 82, 72], "textures": "red_mushroom", "layer": "cutout", "solid": false, "drop": "red_mushroom", "hardness": 0.1},
    {"name": "farmland", "color": [104, 82, 66], "textures": {"top": "farmland_top", "side": "dirt", "bottom": "dirt"}, "layer": "opaque", "solid": true, "drop": "dirt", "hardness": 0.6},
    {"name": "wheat_0", "color": [120, 170, 96], "textures": "wheat_0", "layer": "cutout", "solid": false, "drop": "seeds", "hardness": 0.1},
    {"name": "wheat_1", "color": [120, 170, 96], "textures": "wheat_1", "layer": "cutout", "solid": false, "drop": "seeds", "hardness": 0.1},
    {"name": "wheat_2", "color": [150, 176, 92], "textures": "wheat_2", "layer": "cutout", "solid": false, "drop": "seeds", "hardness": 0.1},
    {"name": "wheat_3", "color": [204, 178, 102], "textures": "wheat_3", "layer": "cutout", "solid": false, "drop": "wheat", "hardness": 0.1},
    {"name": "carrot_0", "color": [108, 168, 98], "textures": "carrot_0", "layer": "cutout", "solid": false, "drop": "carrot", "hardness": 0.1},
    {"name": "carrot_1", "color": [108, 168, 98], "textures": "carrot_1", "layer": "cutout", "solid": false, "drop": "carrot", "hardness": 0.1},
    {"name": "carrot_2", "color": [108, 168, 98], "textures": "carrot_2", "layer": "cutout", "solid": false, "drop": "carrot", "hardness": 0.1},
    {"name": "carrot_3", "color": [236, 138, 72], "textures": "carrot_3", "layer": "cutout", "solid": false, "drop": "carrot", "hardness": 0.1},
    {"name": "sapling", "color": [101, 164, 128], "textures": "sapling", "layer": "cutout", "solid": false, "drop": "sapling", "hardness": 0.1},
    {"name": "campfire", "color": [247, 170, 88], "textures": "campfire", "layer": "cutout", "solid": false, "drop": "campfire", "glow": true, "hardness": 2.0, "tool": "axe"},
    {"name": "torch", "color": [250, 214, 120], "textures": "torch", "layer": "cutout", "solid": false, "drop": "torch", "glow": true, "hardness": 0.1},
    {"name": "bed", "color": [196, 92, 88], "textures": {"top": "bed_top", "side": "bed_side", "bottom": "planks"}, "layer": "opaque", "solid": true, "drop": "bed", "hardness": 0.6},
    {"name": "chest", "color": [186, 138, 88], "textures": {"top": "chest_top", "side": "chest_side", "bottom": "planks"}, "layer": "opaque", "solid": true, "drop": "chest", "hardness": 2.0, "tool": "axe"}
  ]
```

- [ ] **Step 4: Paint the new tiles**

In `frontend/src/engine/blocks.ts`, replace:

```ts
  accent?: Rgb
}
```

with:

```ts
  accent?: Rgb
  /** Growth stage for crop sprites, 1 (just planted) to 4 (ripe). */
  size?: number
}
```

In `frontend/src/engine/atlas.ts`, replace:

```ts
    return CLEAR
  }),
}

function tileOrigin(tile: number): [number, number] {
```

with:

```ts
    return CLEAR
  }),
  sprite_bush: ({ color, accent }, random) => {
    const berries = accent ? [[1, 4], [3, 3], [5, 5], [2, 6], [6, 3]] : []
    return grid((i, j) => {
      const dx = (i - 3.5) / 4, dy = (j - 4.6) / 3.4
      if (dx * dx + dy * dy > 1) return CLEAR
      if (accent && berries.some(([x, y]) => x === i && y === j)) return tone(accent, jitter(random))
      return tone(color, (random() < 0.22 ? 0.76 : 1) * jitter(random, 0.14))
    })
  },
  sprite_mushroom: ({ color, accent }, random) => grid((i, j) => {
    if (j >= 5 && (i === 3 || i === 4)) return tone(accent ?? color, (i === 4 ? 0.88 : 1) * jitter(random))
    const cap = (j === 2 && i >= 2 && i <= 5) || ((j === 3 || j === 4) && i >= 1 && i <= 6)
    if (!cap) return CLEAR
    const spot = j < 4 && (i + j) % 3 === 0
    return tone(color, (spot ? 1.3 : j === 4 ? 0.82 : 1) * jitter(random))
  }),
  furrows: ({ color }, random) => grid((_i, j) => tone(color, (j % 3 === 2 ? 0.7 : 1.06) * jitter(random))),
  sprite_crop: ({ color, accent, size = 4 }, random) => {
    const stalks = [1, 3, 4, 6]
    const heights = stalks.map(() => Math.max(1, size * 2 - Math.floor(random() * 2)))
    return grid((i, j) => {
      const index = stalks.indexOf(i)
      if (index < 0 || j < N - heights[index]) return CLEAR
      const ear = accent !== undefined && j < N - heights[index] + 3
      return tone(ear ? accent : color, jitter(random, 0.14))
    })
  },
  sprite_leafy: ({ color, accent, size = 4 }, random) => {
    const top = N - size * 2
    return grid((i, j) => {
      if (accent && j === N - 1 && (i === 2 || i === 5)) return tone(accent, jitter(random))
      if (j < top) return CLEAR
      const spread = 1 + Math.floor((j - top) / 2)
      if (Math.abs(i - 3.5) > spread || (i + j) % 3 === 0) return CLEAR
      return tone(color, (j - top < 2 ? 1.1 : 1) * jitter(random, 0.14))
    })
  },
  sprite_sapling: ({ color, accent }, random) => grid((i, j) => {
    if (j >= 4 && i === 3) return tone(accent ?? color, jitter(random))
    const leaf = (j === 1 && i >= 2 && i <= 4) || (j === 2 && i >= 1 && i <= 5) || (j === 3 && (i === 2 || i === 4 || i === 5))
    return leaf ? tone(color, (random() < 0.25 ? 0.8 : 1) * jitter(random, 0.14)) : CLEAR
  }),
  sprite_campfire: ({ color, accent }, random) => grid((i, j) => {
    if (j >= 6) return (j === 6 ? i >= 1 && i <= 6 : i !== 3 && i !== 4) ? tone(accent ?? color, (i % 2 ? 0.86 : 1) * jitter(random)) : CLEAR
    const half = (j - 1) * 0.55
    if (j < 1 || Math.abs(i - 3.5) > half) return CLEAR
    return tone(color, (Math.abs(i - 3.5) < 1 && j >= 3 ? 1.18 : 1) * jitter(random, 0.06))
  }),
  sprite_torch: ({ color, accent }, random) => grid((i, j) => {
    if (i !== 3 && i !== 4) return CLEAR
    if (j >= 3) return tone(accent ?? color, (i === 4 ? 0.86 : 1) * jitter(random))
    return j >= 1 ? tone(color, (j === 2 ? 1 : 1.15) * jitter(random, 0.06)) : CLEAR
  }),
  bed_top: ({ color, accent }, random) => grid((i, j) => {
    if (j <= 2) return tone(accent ?? color, (edge(i, j) ? 0.9 : 1) * jitter(random, 0.04))
    return tone(color, (i === 0 || i === N - 1 ? 0.84 : 1) * jitter(random))
  }),
  bed_side: ({ color, accent }, random) => grid((i, j) => {
    if (j <= 3) return tone(color, (j === 3 ? 0.84 : 1) * jitter(random))
    return tone(accent ?? color, (j >= 6 && i > 0 && i < N - 1 ? 0.55 : 1) * jitter(random))
  }),
  chest_top: ({ color, accent }, random) => grid((i, j) =>
    edge(i, j) ? tone(accent ?? color, jitter(random)) : tone(color, (j % 4 === 3 ? 0.84 : 1) * jitter(random))),
  chest_side: ({ color, accent }, random) => grid((i, j) => {
    if ((i === 3 || i === 4) && (j === 3 || j === 4)) return tone([226, 192, 126], jitter(random, 0.04))
    if (edge(i, j) || j === 3) return tone(accent ?? color, jitter(random))
    return tone(color, jitter(random))
  }),
}

function tileOrigin(tile: number): [number, number] {
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 364 tests` … `OK` (3 new).

Run: `cd frontend && npm test && npm run build && npx eslint src/engine`
Expected: `Tests  167 passed (167)` (3 new), the build succeeds, eslint prints nothing.

- [ ] **Step 6: Commit**

```bash
git add shared/blocks.json frontend/src/engine/blocks.ts frontend/src/engine/atlas.ts frontend/src/engine/atlas.test.ts frontend/src/engine/blocks.test.ts backend/tests/test_blocks.py
git commit -m "feat: add food and camp blocks with soft-pixel textures" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 2: Food items, bread and campfire recipes, cooking at a fire

**Files:**
- Modify: `backend/services/crafting.py`, `backend/survival/steps.py`
- Test: `backend/tests/test_survival_steps.py`

**Interfaces:**
- Consumes: `crafting.RECIPES`, `crafting.SMELTING`, `crafting.smelt`, `crafting.take_items`, `crafting.add_item`; `steps.FOOD`, `steps.WORKSTATIONS`, `steps.finish_step`.
- Produces:
  - `backend.services.crafting`: recipes `bread` (3 `wheat` → 1 `bread`, station `crafting_table`) and `campfire` (2 `oak_log` + 3 `sticks` → 1 `campfire`, no station); `SMELTING["raw_fish"] == "cooked_fish"`; `COOKING = frozenset({"raw_fish"})`; `FIRES = ("campfire", "furnace")`; `smelt(inventory, input_item, nearby_stations)` cooks food at a campfire or furnace without fuel and raises `ValueError("A placed campfire or furnace is required")` with neither.
  - `backend.survival.steps`: `FOOD` gains `red_mushroom: 6.0` and `apple: 15.0`; `FOOD_HEALTH = {"red_mushroom": -10.0}`; `WORKSTATIONS = ("crafting_table", "furnace", "campfire")`; finishing an `eat` of a food with negative `FOOD_HEALTH` takes that health (never the last point) and returns `("sick", "<name> ate <food> and felt sick.")`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_steps.py`, replace:

```python
from backend.survival.steps import FOOD, StepFailed, as_cell, failure_code, finish_step, mine_seconds, start_step
```

with:

```python
from backend.services.crafting import craft, smelt
from backend.survival.steps import FOOD, StepFailed, as_cell, failure_code, finish_step, mine_seconds, start_step
```

In `backend/tests/test_survival_steps.py`, add these tests at the end of `StepTests`:

```python
    def test_an_apple_fills_more_and_a_red_mushroom_makes_mimo_sick(self):
        grid, state = small_world(), pet(inventory={"apple": 1, "red_mushroom": 2})
        state["vitals"].update(hunger=40.0, health=50.0)
        finish_step(start_step({"kind": "eat", "item": "apple"}, state, grid, 0.0), state, grid, 1.6)
        self.assertEqual(state["vitals"]["hunger"], 55.0)
        step = start_step({"kind": "eat", "item": "red_mushroom"}, state, grid, 2.0)
        self.assertEqual(finish_step(step, state, grid, 3.6), ("sick", "Pip ate red mushroom and felt sick."))
        self.assertEqual((state["vitals"]["hunger"], state["vitals"]["health"]), (61.0, 40.0))
        state["vitals"]["health"] = 4.0
        finish_step(start_step({"kind": "eat", "item": "red_mushroom"}, state, grid, 4.0), state, grid, 5.6)
        self.assertEqual(state["vitals"]["health"], 1.0)

    def test_fish_cooks_in_five_seconds_at_a_campfire_without_fuel(self):
        grid, state = small_world(), pet(inventory={"raw_fish": 2})
        with self.assertRaises(ValueError) as caught:
            start_step({"kind": "smelt", "item": "raw_fish"}, state, grid, 0.0)
        self.assertEqual(failure_code(caught.exception), "missing_item")
        grid.put(2, 1, 0, "campfire")
        step = start_step({"kind": "smelt", "item": "raw_fish"}, state, grid, 0.0)
        self.assertEqual(step["ends_at"], 5.0)
        self.assertEqual(finish_step(step, state, grid, 5.0), ("smelt", "Pip smelted raw fish."))
        self.assertEqual(state["inventory"], {"raw_fish": 1, "cooked_fish": 1})
```

In `backend/tests/test_survival_steps.py`, add this class before `class CellTests`:

```python
class CookingRecipeTests(unittest.TestCase):
    def test_bread_needs_a_crafting_table_and_a_campfire_needs_none(self):
        self.assertEqual(craft({"wheat": 4}, "bread", {"crafting_table"}), {"wheat": 1, "bread": 1})
        with self.assertRaisesRegex(ValueError, "crafting_table"):
            craft({"wheat": 3}, "bread", set())
        self.assertEqual(craft({"oak_log": 2, "sticks": 3}, "campfire", set()), {"campfire": 1})

    def test_fish_needs_a_fire_but_ore_still_needs_a_furnace_and_fuel(self):
        self.assertEqual(smelt({"raw_fish": 1}, "raw_fish", {"furnace"}), {"cooked_fish": 1})
        with self.assertRaisesRegex(ValueError, "campfire or furnace"):
            smelt({"raw_fish": 1}, "raw_fish", {"crafting_table"})
        self.assertEqual(smelt({"iron_ore": 1, "coal": 1}, "iron_ore", {"furnace"}), {"iron_ingot": 1})
        with self.assertRaisesRegex(ValueError, "A placed furnace"):
            smelt({"iron_ore": 1, "coal": 1}, "iron_ore", {"campfire"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_steps.py"`
Expected: the 4 new tests fail (for example `StepFailed: apple is not food` and `ValueError: Unknown recipe`).

- [ ] **Step 3: Add the recipes and the cooking rule**

In `backend/services/crafting.py`, replace:

```python
    "iron_pickaxe": {"ingredients": {"iron_ingot": 3, "sticks": 2}, "output": {"iron_pickaxe": 1}, "station": "crafting_table"},
}

TOOL_RANK = {"wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3}
SMELTING = {"iron_ore": "iron_ingot", "copper_ore": "copper_ingot", "sand": "glass", "clay": "brick"}
```

with:

```python
    "iron_pickaxe": {"ingredients": {"iron_ingot": 3, "sticks": 2}, "output": {"iron_pickaxe": 1}, "station": "crafting_table"},
    "bread": {"ingredients": {"wheat": 3}, "output": {"bread": 1}, "station": "crafting_table"},
    "campfire": {"ingredients": {"oak_log": 2, "sticks": 3}, "output": {"campfire": 1}},
}

TOOL_RANK = {"wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3}
SMELTING = {"iron_ore": "iron_ingot", "copper_ore": "copper_ingot", "sand": "glass", "clay": "brick",
            "raw_fish": "cooked_fish"}
# Food cooks at a lit campfire or a furnace and burns no fuel: the fire is already lit.
COOKING = frozenset({"raw_fish"})
FIRES = ("campfire", "furnace")
```

In `backend/services/crafting.py`, replace the whole `smelt` function with:

```python
def smelt(inventory: dict[str, int], input_item: str, nearby_stations: set[str]) -> dict[str, int]:
    output = SMELTING.get(input_item)
    if not output:
        raise ValueError("That material cannot be smelted")
    if input_item in COOKING:
        if not set(nearby_stations).intersection(FIRES):
            raise ValueError("A placed campfire or furnace is required")
        result = take_items(inventory, {input_item: 1})
    else:
        if "furnace" not in nearby_stations:
            raise ValueError("A placed furnace is required")
        fuel = "coal" if inventory.get("coal", 0) else "planks"
        result = take_items(inventory, {input_item: 1, fuel: 1})
    add_item(result, output)
    return result
```

- [ ] **Step 4: Add apples, poison and campfires to the steps**

In `backend/survival/steps.py`, replace:

```python
WORKSTATIONS = ("crafting_table", "furnace")
```

with:

```python
WORKSTATIONS = ("crafting_table", "furnace", "campfire")
```

and replace:

```python
# Hunger each food restores (spec section 7). The food items themselves arrive in M4.
FOOD = {"berries": 8.0, "brown_mushroom": 6.0, "carrot": 10.0, "bread": 25.0, "raw_fish": 8.0, "cooked_fish": 30.0}
```

with:

```python
# Hunger each food restores (spec section 7). A red mushroom fills like a brown one but is poisonous.
FOOD = {"berries": 8.0, "brown_mushroom": 6.0, "red_mushroom": 6.0, "carrot": 10.0, "bread": 25.0, "raw_fish": 8.0,
        "cooked_fish": 30.0, "apple": 15.0}
# Health a food changes when eaten: a red mushroom is poisonous. Poison never takes the last point
# of health (it is not a cause of death).
FOOD_HEALTH = {"red_mushroom": -10.0}
```

and replace:

```python
    if kind == "eat":
        state["inventory"] = take_items(state["inventory"], {step["item"]: 1})
        state["vitals"]["hunger"] = min(100.0, state["vitals"]["hunger"] + FOOD[step["item"]])
        return "ate", f"{name} ate {label(step['item'])}."
```

with:

```python
    if kind == "eat":
        item, vitals = step["item"], state["vitals"]
        state["inventory"] = take_items(state["inventory"], {item: 1})
        vitals["hunger"] = min(100.0, vitals["hunger"] + FOOD[item])
        health = FOOD_HEALTH.get(item, 0.0)
        if health < 0:
            vitals["health"] = max(min(vitals["health"], 1.0), vitals["health"] + health)
            return "sick", f"{name} ate {label(item)} and felt sick."
        return "ate", f"{name} ate {label(item)}."
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_steps.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 368 tests` … `OK` (4 new).

- [ ] **Step 6: Commit**

```bash
git add backend/services/crafting.py backend/survival/steps.py backend/tests/test_survival_steps.py
git commit -m "feat: add apples, poison, bread and campfire recipes, and cook fish at a fire" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 3: Wild food in worldgen, in both languages

**Files:**
- Modify: `backend/services/worldgen.py`, `frontend/src/engine/worldgen.ts`, `backend/scripts/worldgen_fixture.py`, `shared/worldgen-fixture.json` (regenerated)
- Test: `backend/tests/test_worldgen.py`, `frontend/src/engine/worldgen.test.ts`

**Interfaces:**
- Consumes: Task 1's blocks `berry_bush_ripe`, `brown_mushroom`, `red_mushroom`; worldgen's `hash32`, `noise2`, `biome_at`, `cave_at`, `terrain_height`, `plant_at`, `decoration_at` and their TypeScript twins.
- Produces:
  - `backend.services.worldgen`: `FOREST_EDGE = 0.16`, `BUSH_RARITY = 97`, `MUSHROOM_RARITY = 67`, `CAVE_MUSHROOM_RARITY = 29`; `wild_food(x, z, seed) -> str | None` (never within `LEGACY_RADIUS`); `cave_plant(x, y, z, seed) -> str | None`; `plant_at` returns wild food before tall grass; `decoration_at` returns `cave_plant` below `terrain_height - 2`.
  - `frontend/src/engine/worldgen.ts`: `wildFood(x, z, seed)`, `cavePlant(x, y, z, seed)`, the same rules in `plantAt`, `decorationAt` and `generateColumn`.
  - `backend.scripts.worldgen_fixture`: `WILD_FOOD`, `_wild_food(seed, count)`, `_cave_plants(seed, count)`; the fixture samples 40 wild-food columns and 12 cave mushrooms per seed.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_worldgen.py`, replace:

```python
import json
import unittest

from backend.services.worldgen import (
    LEGACY_WORLD_SEED, base_material, biome_at, block_at, cave_at, hash32, legacy_hash, plant_at,
    surface_material, terrain_height, trees_in_chunk,
)
```

with:

```python
import json
import math
import unittest

from backend.services.blocks import is_solid
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, base_material, biome_at, block_at, cave_at, cave_plant, hash32, legacy_hash,
    plant_at, surface_material, terrain_height, trees_in_chunk, wild_food,
)
```

In `backend/tests/test_worldgen.py`, add this class before `class FixtureTests`:

```python
class WildFoodTests(unittest.TestCase):
    def test_bushes_grow_in_meadows_and_forest_edges_and_mushrooms_on_the_forest_floor(self):
        seed = "123456789123456789"
        found = {}
        for x in range(300, 900):
            for z in range(-40, 40):
                food = wild_food(x, z, seed)
                if food is None:
                    continue
                expected = ("meadow", "forest") if food == "berry_bush_ripe" else ("forest",)
                self.assertIn(biome_at(x, z, seed), expected, (x, z, food))
                if plant_at(x, z, seed) == food:
                    found.setdefault(food, (x, z))
        self.assertEqual(set(found), {"berry_bush_ripe", "brown_mushroom", "red_mushroom"})
        for food, (x, z) in found.items():
            self.assertEqual(block_at(x, terrain_height(x, z, seed) + 1, z, seed), food)

    def test_the_legacy_clearing_grows_no_wild_food(self):
        for x in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 3):
            for z in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 3):
                if math.hypot(x, z) <= LEGACY_RADIUS:
                    self.assertIsNone(wild_food(x, z, LEGACY_WORLD_SEED), (x, z))

    def test_mushrooms_grow_on_cave_floors(self):
        seed = "123456789123456789"
        found = [(x, y, z) for x in range(250, 700, 3) for z in range(-100, 100, 3)
                 for y in range(-4, terrain_height(x, z, seed) - 2) if cave_plant(x, y, z, seed)]
        self.assertGreater(len(found), 5)
        for x, y, z in found[:5]:
            self.assertIn(block_at(x, y, z, seed), ("brown_mushroom", "red_mushroom"))
            self.assertTrue(is_solid(block_at(x, y - 1, z, seed)), (x, y, z))
```

and replace:

```python
                     "water", "sand", "stone", "bedrock", "grass"):
```

with:

```python
                     "water", "sand", "stone", "bedrock", "grass", "berry_bush_ripe", "brown_mushroom", "red_mushroom"):
```

In `frontend/src/engine/worldgen.test.ts`, replace:

```ts
  blockAt, columnIndex, DEFAULT_WORLD_SEED, generateColumn, legacyHash, treesInChunk, WORLD_MAX_Y, WORLD_MIN_Y,
```

with:

```ts
  blockAt, cavePlant, columnIndex, DEFAULT_WORLD_SEED, generateColumn, legacyHash, terrainHeight, treesInChunk, wildFood,
  WORLD_MAX_Y, WORLD_MIN_Y,
```

and replace:

```ts
    expect(generateColumn(cx, cz, WILD_SEED).includes(blockId('oak_log'))).toBe(true)
    expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
  })
})
```

with:

```ts
    expect(generateColumn(cx, cz, WILD_SEED).includes(blockId('oak_log'))).toBe(true)
    expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
  })

  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
    let foodChunk: [number, number] | null = null
    for (let x = 300; x < 900 && !foodChunk; x++) {
      for (let z = -40; z < 40 && !foodChunk; z++) if (wildFood(x, z, WILD_SEED)) foodChunk = [Math.floor(x / 16), Math.floor(z / 16)]
    }
    let caveChunk: [number, number] | null = null
    for (let x = 250; x < 700 && !caveChunk; x += 3) {
      for (let z = -100; z < 100 && !caveChunk; z += 3) {
        for (let y = -4; y < terrainHeight(x, z, WILD_SEED) - 2 && !caveChunk; y++) {
          if (cavePlant(x, y, z, WILD_SEED)) caveChunk = [Math.floor(x / 16), Math.floor(z / 16)]
        }
      }
    }
    expect(foodChunk).not.toBeNull()
    expect(caveChunk).not.toBeNull()
    for (const [cx, cz] of [foodChunk!, caveChunk!]) expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
    const food = ['berry_bush_ripe', 'brown_mushroom', 'red_mushroom'].map((name) => blockId(name))
    expect(Array.from(generateColumn(...foodChunk!, WILD_SEED)).some((id) => food.includes(id))).toBe(true)
    expect(Array.from(generateColumn(...caveChunk!, WILD_SEED)).some((id) => food.includes(id))).toBe(true)
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen.py"`
Expected: `ImportError: cannot import name 'cave_plant' from 'backend.services.worldgen'`.

Run: `cd frontend && npx vitest run src/engine/worldgen.test.ts`
Expected: the new test fails (`wildFood` and `cavePlant` are not exported yet).

- [ ] **Step 3: Grow bushes and mushrooms in the Python worldgen**

In `backend/services/worldgen.py`, replace:

```python
                (-1, 7, "flower_pink"), (3, 7, "flower_orange"))
```

with:

```python
                (-1, 7, "flower_pink"), (3, 7, "flower_orange"))
# Wild food on generated land: one berry bush per BUSH_RARITY meadow or forest-edge columns, one
# mushroom per MUSHROOM_RARITY forest columns and per CAVE_MUSHROOM_RARITY cave floor cells.
FOREST_EDGE = 0.16  # forest moisture below this is the forest's edge
BUSH_RARITY = 97
MUSHROOM_RARITY = 67
CAVE_MUSHROOM_RARITY = 29
```

and replace:

```python
def plant_at(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """Flower or tall grass growing on top of the terrain at (x, z)."""
```

with:

```python
def wild_food(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """A ripe berry bush (meadows and forest edges) or a mushroom (forest floor) on generated land.
    The legacy clearing keeps exactly the plants it always had."""
    if math.hypot(x, z) <= LEGACY_RADIUS:
        return None
    biome = biome_at(x, z, seed)
    if biome == "meadow" or (biome == "forest" and noise2(x, z, 160, seed, 5) < FOREST_EDGE):
        if hash32(x, 0, z, seed, 15) % BUSH_RARITY == 0:
            return "berry_bush_ripe"
    if biome == "forest":
        roll = hash32(x, 0, z, seed, 16)
        if roll % MUSHROOM_RARITY == 0:
            return "red_mushroom" if roll // MUSHROOM_RARITY % 3 == 0 else "brown_mushroom"
    return None


def cave_plant(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """A mushroom on a cave floor: an open cave cell with solid rock (or bedrock) under it."""
    roll = hash32(x, y, z, seed, 17)
    if roll % CAVE_MUSHROOM_RARITY != 0:
        return None
    if not cave_at(x, y, z, seed) or cave_at(x, y - 1, z, seed):
        return None
    return "red_mushroom" if roll // CAVE_MUSHROOM_RARITY % 3 == 0 else "brown_mushroom"


def plant_at(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """Flower, wild food or tall grass growing on top of the terrain at (x, z)."""
```

and replace:

```python
    if surface_material(x, z, seed) not in ("grass", "moss"):
        return None
    return "tall_grass" if hash32(x, 0, z, seed, 14) % 19 == 0 else None


def decoration_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """Blocks that grow or stand on the terrain. Precedence: home, trunk, leaves, plant."""
    home = HOME_BLOCKS.get((x, y, z))
    if home:
        return home
    tree = tree_block(x, y, z, seed)
    if tree:
        return tree
    if y == terrain_height(x, z, seed) + 1:
        return plant_at(x, z, seed)
    return None
```

with:

```python
    if surface_material(x, z, seed) not in ("grass", "moss"):
        return None
    food = wild_food(x, z, seed)
    if food:
        return food
    return "tall_grass" if hash32(x, 0, z, seed, 14) % 19 == 0 else None


def decoration_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """Blocks that grow or stand on the terrain, or on a cave floor. Precedence: home, trunk,
    leaves, plant."""
    home = HOME_BLOCKS.get((x, y, z))
    if home:
        return home
    tree = tree_block(x, y, z, seed)
    if tree:
        return tree
    height = terrain_height(x, z, seed)
    if y == height + 1:
        return plant_at(x, z, seed)
    if y < height - 2:
        return cave_plant(x, y, z, seed)
    return None
```

- [ ] **Step 4: The same rules in the viewer's worldgen**

In `frontend/src/engine/worldgen.ts`, replace:

```ts
const HOME_RADIUS = 12
const MASK = 0xffffffff
```

with:

```ts
const HOME_RADIUS = 12
const MASK = 0xffffffff
// Wild food on generated land (see backend/services/worldgen.py).
const FOREST_EDGE = 0.16
const BUSH_RARITY = 97
const MUSHROOM_RARITY = 67
const CAVE_MUSHROOM_RARITY = 29
```

and replace:

```ts
/** Flower or tall grass growing on top of the terrain at (x, z). */
export function plantAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
```

with:

```ts
/** A ripe berry bush (meadows and forest edges) or a mushroom (forest floor) on generated land. */
export function wildFood(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return null
  const biome = biomeAt(x, z, seed)
  if (biome === 'meadow' || (biome === 'forest' && noise2(x, z, 160, seed, 5) < FOREST_EDGE)) {
    if (hash32(x, 0, z, seed, 15) % BUSH_RARITY === 0) return 'berry_bush_ripe'
  }
  if (biome === 'forest') {
    const roll = hash32(x, 0, z, seed, 16)
    if (roll % MUSHROOM_RARITY === 0) return Math.floor(roll / MUSHROOM_RARITY) % 3 === 0 ? 'red_mushroom' : 'brown_mushroom'
  }
  return null
}

/** A mushroom on a cave floor: an open cave cell with solid rock (or bedrock) under it. */
export function cavePlant(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  const roll = hash32(x, y, z, seed, 17)
  if (roll % CAVE_MUSHROOM_RARITY !== 0) return null
  if (!caveAt(x, y, z, seed) || caveAt(x, y - 1, z, seed)) return null
  return Math.floor(roll / CAVE_MUSHROOM_RARITY) % 3 === 0 ? 'red_mushroom' : 'brown_mushroom'
}

/** Flower, wild food or tall grass growing on top of the terrain at (x, z). */
export function plantAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
```

and replace:

```ts
  return hash32(x, 0, z, seed, 14) % 19 === 0 ? 'tall_grass' : null
}

/** Blocks that grow or stand on the terrain. Precedence: home, trunk, leaves, plant. */
function decorationAt(x: number, y: number, z: number, seed: string): string | null {
  const home = HOME_BLOCKS.get(`${x},${y},${z}`)
  if (home) return home
  const tree = treeBlock(x, y, z, seed)
  if (tree) return tree
  if (y === terrainHeight(x, z, seed) + 1) return plantAt(x, z, seed)
  return null
}
```

with:

```ts
  return wildFood(x, z, seed) ?? (hash32(x, 0, z, seed, 14) % 19 === 0 ? 'tall_grass' : null)
}

/** Blocks that grow or stand on the terrain, or on a cave floor. Precedence: home, trunk, leaves, plant. */
function decorationAt(x: number, y: number, z: number, seed: string): string | null {
  const home = HOME_BLOCKS.get(`${x},${y},${z}`)
  if (home) return home
  const tree = treeBlock(x, y, z, seed)
  if (tree) return tree
  const height = terrainHeight(x, z, seed)
  if (y === height + 1) return plantAt(x, z, seed)
  if (y < height - 2) return cavePlant(x, y, z, seed)
  return null
}
```

and replace:

```ts
    const top = Math.max(terrainHeight(x, z, seed), SEA_LEVEL)
    for (let y = WORLD_MIN_Y; y <= top; y++) {
      const name = terrainBlock(x, y, z, seed)
      if (name !== 'air') data[columnIndex(lx, y, lz)] = blockId(name)
    }
```

with:

```ts
    const height = terrainHeight(x, z, seed)
    const top = Math.max(height, SEA_LEVEL)
    for (let y = WORLD_MIN_Y; y <= top; y++) {
      // A cave floor plant counts as terrain here: nothing else is ever stamped in a cave.
      const name = terrainBlock(x, y, z, seed)
      const found = name !== 'air' ? name : y < height - 2 ? cavePlant(x, y, z, seed) : null
      if (found) data[columnIndex(lx, y, lz)] = blockId(found)
    }
```

- [ ] **Step 5: Sample wild food in the parity fixture and regenerate it**

In `backend/scripts/worldgen_fixture.py`, replace:

```python
    LEGACY_WORLD_SEED, biome_at, block_at, plant_at, terrain_height, trees_in_chunk,
```

with:

```python
    LEGACY_WORLD_SEED, biome_at, block_at, cave_plant, plant_at, terrain_height, trees_in_chunk,
```

and replace:

```python
FAR_LIMIT = 30000
```

with:

```python
FAR_LIMIT = 30000
WILD_FOOD = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")
```

and replace:

```python
def _biome_patch(seed: str, biome: str) -> list[tuple[int, int, int]]:
```

with:

```python
def _wild_food(seed: str, count: int) -> list[tuple[int, int]]:
    """Columns with a berry bush or a mushroom on generated land."""
    found = []
    for x in range(250, 1250):
        for z in range(-60, 60, 2):
            if plant_at(x, z, seed) in WILD_FOOD:
                found.append((x, z))
                if len(found) == count:
                    return found
    return found


def _cave_plants(seed: str, count: int) -> list[tuple[int, int, int]]:
    """Mushrooms on cave floors."""
    found = []
    for x in range(250, 700, 3):
        for z in range(-100, 100, 3):
            for y in range(-4, terrain_height(x, z, seed) - 2):
                if cave_plant(x, y, z, seed):
                    found.append((x, y, z))
                    if len(found) == count:
                        return found
    return found


def _biome_patch(seed: str, biome: str) -> list[tuple[int, int, int]]:
```

and replace:

```python
        for x, z in _plants(seed, 20):
            height = terrain_height(x, z, seed)
            cells |= {(seed, x, height, z), (seed, x, height + 1, z)}
```

with:

```python
        for x, z in _plants(seed, 20) + _wild_food(seed, 40):
            height = terrain_height(x, z, seed)
            cells |= {(seed, x, height, z), (seed, x, height + 1, z)}
        for x, y, z in _cave_plants(seed, 12):
            cells |= {(seed, x, y, z), (seed, x, y - 1, z)}
```

Then regenerate the fixture (the apply script cannot run commands; run it by hand):

Run: `python3 -m backend.scripts.worldgen_fixture`
Expected: `Wrote 19081 cells to .../shared/worldgen-fixture.json`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 371 tests` … `OK` (3 new).

Run: `cd frontend && npm test && npm run build && npx eslint src/engine`
Expected: `Tests  168 passed (168)` (1 new; the parity test now checks the wild food cells too), the build succeeds, eslint prints nothing.

- [ ] **Step 7: Commit**

```bash
git add backend/services/worldgen.py frontend/src/engine/worldgen.ts backend/scripts/worldgen_fixture.py shared/worldgen-fixture.json backend/tests/test_worldgen.py frontend/src/engine/worldgen.test.ts
git commit -m "feat: grow berry bushes and mushrooms in both worldgens" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: A step registry

Every kind of step becomes data (the M3 review asked for this before M4 adds kinds): how it starts and finishes, the pet's status while it runs, whether it counts as work and whether a reflex may cut it short. The engine asks the registry instead of its own lists. No behavior changes.

**Files:**
- Modify: `backend/survival/steps.py`, `backend/survival/actions.py`
- Test: `backend/tests/test_survival_steps.py`, `backend/tests/test_survival_actions.py`

**Interfaces:**
- Consumes: `steps.start_step`, `steps.finish_step`, `steps.validate_step`; `actions.activity_of`, `actions.advance_actions`.
- Produces:
  - `backend.survival.steps`: `@dataclass(frozen=True) class StepKind` with `name: str`, `start: Callable[[dict, dict, Grid, float, float], dict]` (spec, state, grid, at, scale), `finish: Callable[[dict, dict, Grid, float], tuple[str, str] | None]` (step, state, grid, at), `status: str`, `working: bool = False`, `interruptible: bool = False`, `cell_field: str | None = None`, `string_field: str | None = None`; `STEP_KINDS: dict[str, StepKind]`; `register_step(kind) -> StepKind`; `step_kind(name) -> StepKind | None`; `nothing_happens(step, state, grid, at) -> None`; the M2 kinds as `start_walk`/`finish_walk`, `start_mine`/`finish_mine`, `start_place`/`finish_place`, `start_eat`/`finish_eat`, `start_craft`/`finish_craft`, `start_smelt`/`finish_smelt`, `start_sleep`, `start_wait`, registered with statuses walking, mining, building, eating, crafting, smelting, sleeping, idle (walk, mine and place are work; walk, sleep and wait are interruptible). `KNOWN_KINDS`, `CELL_FIELD` and `STRING_FIELD` are gone.
  - `backend.survival.actions`: `HAZARDS = {"swim": ("swimming", True), "fall": ("falling", False)}`; `status_of(kind) -> str`, `is_working(kind) -> bool`, `is_interruptible(kind) -> bool`. `WORKING`, `STATUS` and `INTERRUPTIBLE` are gone.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_steps.py`, replace:

```python
from backend.survival.steps import FOOD, StepFailed, as_cell, failure_code, finish_step, mine_seconds, start_step
```

with:

```python
from backend.survival.steps import (
    FOOD, STEP_KINDS, StepFailed, StepKind, as_cell, failure_code, finish_step, mine_seconds, register_step, start_step,
)
```

In `backend/tests/test_survival_steps.py`, add this class before `class CookingRecipeTests`:

```python
class StepRegistryTests(unittest.TestCase):
    def test_the_m2_kinds_are_registered_with_how_they_show(self):
        expected = {"walk": ("walking", True, True), "mine": ("mining", True, False), "place": ("building", True, False),
                    "eat": ("eating", False, False), "craft": ("crafting", False, False),
                    "smelt": ("smelting", False, False), "sleep": ("sleeping", False, True), "wait": ("idle", False, True)}
        for name, shown in expected.items():
            kind = STEP_KINDS[name]
            self.assertEqual((kind.status, kind.working, kind.interruptible), shown, name)

    def test_a_registered_kind_is_validated_started_and_finished_through_the_registry(self):
        def start(spec, state, grid, at, scale):
            return {"kind": "test_hum", "started_at": at, "ends_at": at + 2.0 / scale, "item": spec["item"]}

        def finish(step, state, grid, at):
            return "hum", f"{state['name']} hummed {step['item']}."

        register_step(StepKind("test_hum", start, finish, "humming", string_field="item"))
        try:
            grid, state = small_world(), pet()
            step = start_step({"kind": "test_hum", "item": "a tune"}, state, grid, 1.0, scale=2.0)
            self.assertEqual(step["ends_at"], 2.0)
            self.assertEqual(finish_step(step, state, grid, 2.0), ("hum", "Pip hummed a tune."))
            with self.assertRaisesRegex(StepFailed, "bad step: item"):
                start_step({"kind": "test_hum", "item": 3}, state, grid, 1.0)
        finally:
            STEP_KINDS.pop("test_hum", None)
        with self.assertRaisesRegex(StepFailed, "unknown step 'test_hum'"):
            start_step({"kind": "test_hum", "item": "a tune"}, pet(), small_world(), 1.0)
        self.assertIsNone(finish_step({"kind": "test_hum"}, pet(), small_world(), 1.0))
```

In `backend/tests/test_survival_actions.py`, replace:

```python
from backend.survival.actions import ActionContext, activity_of, advance_actions, ensure_actions, take_search
```

with:

```python
from backend.survival.actions import (
    ActionContext, activity_of, advance_actions, ensure_actions, is_interruptible, is_working, status_of, take_search,
)
```

and replace:

```python
from backend.survival.steps import start_step
```

with:

```python
from backend.survival.steps import STEP_KINDS, StepKind, nothing_happens, register_step, start_step
```

In `backend/tests/test_survival_actions.py`, add these tests at the end of `InterruptTests`:

```python
    def test_status_work_and_interrupts_come_from_the_step_registry(self):
        self.assertEqual([status_of(kind) for kind in ("mine", "place", "swim", "fall", "nope")],
                         ["mining", "building", "swimming", "falling", "idle"])
        self.assertEqual([is_working(kind) for kind in ("walk", "swim", "eat", "fall")], [True, True, False, False])
        self.assertEqual([is_interruptible(kind) for kind in ("sleep", "wait", "mine", "swim")], [True, True, False, False])

    def test_a_registered_interruptible_kind_can_be_cut(self):
        def start(spec, state, grid, at, scale):
            return {"kind": "test_listen", "started_at": at, "ends_at": at + 10.0}

        register_step(StepKind("test_listen", start, nothing_happens, "listening", interruptible=True))
        try:
            state = pet()
            state["queue"] = [{"kind": "test_listen"}]
            ctx = hooked(small_world(), Takeover(lambda state, at: at >= 2.0, [{"kind": "wait", "seconds": 1}], "surface"))
            advance_actions(state, ctx, 1.0)
            self.assertEqual(state["status"], "listening")
            advance_actions(state, ctx, 2.0)
            cut = state["recent_actions"][-1]
            self.assertEqual((cut["kind"], cut["result"], cut["reason"]), ("test_listen", "interrupted", "surface"))
        finally:
            STEP_KINDS.pop("test_listen", None)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_steps.py"`
Expected: `ImportError: cannot import name 'STEP_KINDS' from 'backend.survival.steps'`.

- [ ] **Step 3: Turn the step kinds into a registry**

In `backend/survival/steps.py`, replace:

```python
with a clean StepFailed instead of a TypeError from as_cell or a dict lookup further in.
"""
```

with:

```python
with a clean StepFailed instead of a TypeError from as_cell or a dict lookup further in.

Every kind of step is a StepKind in the STEP_KINDS registry: how it starts and finishes, the
pet's status while it runs, whether it counts as work and whether a reflex may cut it short. The
engine (backend.survival.actions) asks the registry, so a new kind only has to register.
"""
```

and replace:

```python
import math

from backend.services.blocks import hardness, is_replaceable, mining_tool
```

with:

```python
import math
from dataclasses import dataclass
from typing import Callable

from backend.services.blocks import hardness, is_replaceable, mining_tool
```

and replace:

```python
KNOWN_KINDS = frozenset({"walk", "mine", "place", "eat", "craft", "smelt", "sleep", "wait"})
CELL_FIELD = {"walk": "target", "mine": "target", "place": "target"}
STRING_FIELD = {"place": "block", "eat": "item", "craft": "recipe", "smelt": "item"}
```

with:

```python
@dataclass(frozen=True)
class StepKind:
    """One kind of step in the registry that every planned step runs through.

    `start(spec, state, grid, at, scale)` checks a queued spec against the world and returns the
    running step from `at` to its end time (`ends_at`, None when it has no fixed end).
    `finish(step, state, grid, at)` applies it at its end and returns an event (kind, text) worth
    logging, or None. Both raise StepFailed. `status` is the pet's status while it runs, `working`
    makes it count as work for the vitals, and `interruptible` lets a takeover (a reflex) cut it
    short; the other kinds last a few seconds at most and finish first. validate_step checks that
    the spec's `cell_field` is a cell and its `string_field` a string before `start` sees it.
    """

    name: str
    start: Callable[[dict, dict, Grid, float, float], dict]
    finish: Callable[[dict, dict, Grid, float], "tuple[str, str] | None"]
    status: str
    working: bool = False
    interruptible: bool = False
    cell_field: str | None = None
    string_field: str | None = None


STEP_KINDS: dict[str, StepKind] = {}


def register_step(kind: StepKind) -> StepKind:
    """Add a step kind, or replace the one with the same name."""
    STEP_KINDS[kind.name] = kind
    return kind


def step_kind(name) -> StepKind | None:
    """The registered kind called `name`, or None (also when `name` is not a string)."""
    return STEP_KINDS.get(name) if isinstance(name, str) else None
```

In `backend/survival/steps.py`, replace the whole `validate_step` function with:

```python
def validate_step(spec: dict) -> None:
    """Check a queued step's shape before it touches the world or an inventory dict.

    A field that is present but the wrong shape (a target that isn't a cell, a block that isn't
    a string, a non-finite reach or wait) raises StepFailed here, short and clear, instead of a
    TypeError from as_cell or a dict lookup deeper in start_step. A field that is simply missing
    is left to the checks below, which already raise their own StepFailed for it.
    """
    kind = step_kind(spec.get("kind"))
    if kind is None:
        raise StepFailed(f"unknown step {spec.get('kind')!r}")
    if kind.cell_field and kind.cell_field in spec:
        try:
            as_cell(spec[kind.cell_field])
        except ValueError:
            raise StepFailed(f"bad step: {kind.cell_field}")
    if kind.string_field and kind.string_field in spec and not isinstance(spec[kind.string_field], str):
        raise StepFailed(f"bad step: {kind.string_field}")
    if kind.name == "walk" and "reach" in spec and not (_finite_number(spec["reach"]) and spec["reach"] >= 0):
        raise StepFailed("bad step: reach")
    if kind.name == "wait" and "seconds" in spec and not _finite_number(spec["seconds"]):
        raise StepFailed("bad step: seconds")
```

In `backend/survival/steps.py`, replace `start_step` and `finish_step` (the end of the file):

```python
def start_step(spec: dict, state: dict, grid: Grid, at: float, scale: float = 1.0) -> dict:
    """Check a queued step against the world and return it running, from `at` to its end time.

    `scale` (MIMO_ACTION_SCALE, 1 outside manual tests) divides the duration of walks, mining,
    placing, eating, crafting and smelting. Waits time things against the clock and sleep has no
    fixed end, so neither is scaled.
    """
    validate_step(spec)
    kind = spec.get("kind")
    here = as_cell(state["position"])
    inventory = state["inventory"]
    if kind == "walk":
        target = as_cell(spec["target"])
        reach = float(spec.get("reach", 0.0))
        segments = int(spec.get("segments", 0))
        if segments > MAX_SEGMENTS:
            raise StepFailed("no way there", "no_path")
        cells, reached = route(grid, here, target, reach)
        if not cells and not reached:
            raise StepFailed("no way there", "no_path")
        path = timed_path(grid, here, cells, at, scale)
        return {"kind": "walk", "started_at": at, "ends_at": path[-1]["at"], "path": path,
                "target": as_point(target), "reach": reach, "reached": reached, "segments": segments}
    if kind == "mine":
        target = as_cell(spec["target"])
        if not in_reach(here, target):
            raise StepFailed("out of reach", "out_of_reach")
        material = grid.material(*target)
        seconds = mine_seconds(material, inventory)
        if seconds is None:
            raise StepFailed(f"{label(material)} cannot be mined", "blocked")
        if not can_harvest(material, inventory):
            raise StepFailed(f"a stronger pickaxe is needed for {label(material)}", "missing_item")
        return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds / scale, 3),
                "target": as_point(target), "block": material}
    if kind == "place":
        target, block = as_cell(spec["target"]), spec["block"]
        if inventory.get(block, 0) < 1:
            raise StepFailed(f"no {label(block)} to place", "missing_item")
        if block not in BLOCKS:
            raise StepFailed(f"{label(block)} is not a block")
        if not in_reach(here, target):
            raise StepFailed("out of reach", "out_of_reach")
        if target == here:
            raise StepFailed("that is where it stands", "blocked")
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken", "blocked")
        return {"kind": "place", "started_at": at, "ends_at": round(at + PLACE_SECONDS / scale, 3),
                "target": as_point(target), "block": block}
    if kind == "eat":
        item = spec["item"]
        if item not in FOOD:
            raise StepFailed(f"{label(item)} is not food")
        if inventory.get(item, 0) < 1:
            raise StepFailed(f"no {label(item)} to eat", "missing_item")
        return {"kind": "eat", "started_at": at, "ends_at": round(at + EAT_SECONDS / scale, 3), "item": item}
    if kind == "craft":
        craft(inventory, spec["recipe"], stations_near(grid, here))
        return {"kind": "craft", "started_at": at, "ends_at": round(at + CRAFT_SECONDS / scale, 3),
                "recipe": spec["recipe"]}
    if kind == "smelt":
        smelt(inventory, spec["item"], stations_near(grid, here))
        return {"kind": "smelt", "started_at": at, "ends_at": round(at + SMELT_SECONDS / scale, 3),
                "item": spec["item"]}
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
            raise StepFailed(f"the {label(step['block'])} is gone", "gone")
        grid.put(*target, "air")
        drop = BLOCKS.get(step["block"], {}).get("drop")
        if drop:
            add_item(state["inventory"], drop)
        return None
    if kind == "place":
        target = as_cell(step["target"])
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken", "blocked")
        state["inventory"] = take_items(state["inventory"], {step["block"]: 1})
        grid.put(*target, step["block"])
        return None
    if kind == "eat":
        item, vitals = step["item"], state["vitals"]
        state["inventory"] = take_items(state["inventory"], {item: 1})
        vitals["hunger"] = min(100.0, vitals["hunger"] + FOOD[item])
        health = FOOD_HEALTH.get(item, 0.0)
        if health < 0:
            vitals["health"] = max(min(vitals["health"], 1.0), vitals["health"] + health)
            return "sick", f"{name} ate {label(item)} and felt sick."
        return "ate", f"{name} ate {label(item)}."
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

with:

```python
def start_step(spec: dict, state: dict, grid: Grid, at: float, scale: float = 1.0) -> dict:
    """Check a queued step against the world and return it running, from `at` to its end time.

    `scale` (MIMO_ACTION_SCALE, 1 outside manual tests) divides the duration of every step with a
    fixed length except waits, which time things against the clock. Sleep has no fixed end.
    """
    validate_step(spec)
    return STEP_KINDS[spec["kind"]].start(spec, state, grid, at, scale)


def finish_step(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str] | None:
    """Apply a running step at its end. Returns an event (kind, text) worth logging, if any."""
    kind = step_kind(step["kind"])
    return None if kind is None else kind.finish(step, state, grid, at)


def nothing_happens(step: dict, state: dict, grid: Grid, at: float) -> None:
    return None


def start_walk(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    here, target = as_cell(state["position"]), as_cell(spec["target"])
    reach = float(spec.get("reach", 0.0))
    segments = int(spec.get("segments", 0))
    if segments > MAX_SEGMENTS:
        raise StepFailed("no way there", "no_path")
    cells, reached = route(grid, here, target, reach)
    if not cells and not reached:
        raise StepFailed("no way there", "no_path")
    path = timed_path(grid, here, cells, at, scale)
    return {"kind": "walk", "started_at": at, "ends_at": path[-1]["at"], "path": path,
            "target": as_point(target), "reach": reach, "reached": reached, "segments": segments}


def finish_walk(step: dict, state: dict, grid: Grid, at: float) -> None:
    state["position"] = position_of(step["path"][-1])
    return None


def start_mine(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target, inventory = as_cell(spec["target"]), state["inventory"]
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    material = grid.material(*target)
    seconds = mine_seconds(material, inventory)
    if seconds is None:
        raise StepFailed(f"{label(material)} cannot be mined", "blocked")
    if not can_harvest(material, inventory):
        raise StepFailed(f"a stronger pickaxe is needed for {label(material)}", "missing_item")
    return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds / scale, 3),
            "target": as_point(target), "block": material}


def finish_mine(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = as_cell(step["target"])
    if grid.material(*target) != step["block"]:
        raise StepFailed(f"the {label(step['block'])} is gone", "gone")
    grid.put(*target, "air")
    drop = BLOCKS.get(step["block"], {}).get("drop")
    if drop:
        add_item(state["inventory"], drop)
    return None


def start_place(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    here, target, block = as_cell(state["position"]), as_cell(spec["target"]), spec["block"]
    if state["inventory"].get(block, 0) < 1:
        raise StepFailed(f"no {label(block)} to place", "missing_item")
    if block not in BLOCKS:
        raise StepFailed(f"{label(block)} is not a block")
    if not in_reach(here, target):
        raise StepFailed("out of reach", "out_of_reach")
    if target == here:
        raise StepFailed("that is where it stands", "blocked")
    if not is_replaceable(grid.material(*target)):
        raise StepFailed("that cell is taken", "blocked")
    return {"kind": "place", "started_at": at, "ends_at": round(at + PLACE_SECONDS / scale, 3),
            "target": as_point(target), "block": block}


def finish_place(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = as_cell(step["target"])
    if not is_replaceable(grid.material(*target)):
        raise StepFailed("that cell is taken", "blocked")
    state["inventory"] = take_items(state["inventory"], {step["block"]: 1})
    grid.put(*target, step["block"])
    return None


def start_eat(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item = spec["item"]
    if item not in FOOD:
        raise StepFailed(f"{label(item)} is not food")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to eat", "missing_item")
    return {"kind": "eat", "started_at": at, "ends_at": round(at + EAT_SECONDS / scale, 3), "item": item}


def finish_eat(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    item, vitals, name = step["item"], state["vitals"], state["name"]
    state["inventory"] = take_items(state["inventory"], {item: 1})
    vitals["hunger"] = min(100.0, vitals["hunger"] + FOOD[item])
    health = FOOD_HEALTH.get(item, 0.0)
    if health < 0:
        vitals["health"] = max(min(vitals["health"], 1.0), vitals["health"] + health)
        return "sick", f"{name} ate {label(item)} and felt sick."
    return "ate", f"{name} ate {label(item)}."


def start_craft(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    craft(state["inventory"], spec["recipe"], stations_near(grid, as_cell(state["position"])))
    return {"kind": "craft", "started_at": at, "ends_at": round(at + CRAFT_SECONDS / scale, 3),
            "recipe": spec["recipe"]}


def finish_craft(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    stations = stations_near(grid, as_cell(state["position"]))
    state["inventory"] = craft(state["inventory"], step["recipe"], stations)
    return "craft", f"{state['name']} crafted {label(step['recipe'])}."


def start_smelt(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    smelt(state["inventory"], spec["item"], stations_near(grid, as_cell(state["position"])))
    return {"kind": "smelt", "started_at": at, "ends_at": round(at + SMELT_SECONDS / scale, 3),
            "item": spec["item"]}


def finish_smelt(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    stations = stations_near(grid, as_cell(state["position"]))
    state["inventory"] = smelt(state["inventory"], step["item"], stations)
    return "smelt", f"{state['name']} smelted {label(step['item'])}."


def start_sleep(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    # Sleep has no fixed end: actions.py ends it once Mimo is rested and it is not night.
    return {"kind": "sleep", "started_at": at, "ends_at": None}


def start_wait(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    seconds = float(spec.get("seconds", 1.0))
    if seconds <= 0:
        raise StepFailed("a wait needs some time")
    return {"kind": "wait", "started_at": at, "ends_at": round(at + seconds, 3)}


register_step(StepKind("walk", start_walk, finish_walk, "walking", working=True, interruptible=True,
                       cell_field="target"))
register_step(StepKind("mine", start_mine, finish_mine, "mining", working=True, cell_field="target"))
register_step(StepKind("place", start_place, finish_place, "building", working=True, cell_field="target",
                       string_field="block"))
register_step(StepKind("eat", start_eat, finish_eat, "eating", string_field="item"))
register_step(StepKind("craft", start_craft, finish_craft, "crafting", string_field="recipe"))
register_step(StepKind("smelt", start_smelt, finish_smelt, "smelting", string_field="item"))
register_step(StepKind("sleep", start_sleep, nothing_happens, "sleeping", interruptible=True))
register_step(StepKind("wait", start_wait, nothing_happens, "idle", interruptible=True))
```

- [ ] **Step 4: Let the engine ask the registry**

In `backend/survival/actions.py`, replace:

```python
step starts and at every advance while a walk, sleep or wait is still running; a cut walk has
already moved to the last cell it reached. The cut step is recorded as "interrupted" with the
hook's reason. At most MAX_TAKEOVERS takeovers happen per advance_actions call, so a hook that
always says yes cannot spin the tick.
```

with:

```python
step starts and at every advance while an interruptible step (its StepKind in
backend.survival.steps says so) is still running; a cut walk has already moved to the last cell it
reached. The cut step is recorded as "interrupted" with the hook's reason. At most MAX_TAKEOVERS
takeovers happen per advance_actions call, so a hook that always says yes cannot spin the tick.
```

and replace:

```python
from backend.survival.steps import as_cell, as_point, failure_code, finish_step, position_of, start_step
```

with:

```python
from backend.survival.steps import as_cell, as_point, failure_code, finish_step, position_of, start_step, step_kind
```

and replace:

```python
WORKING = frozenset({"walk", "swim", "mine", "place"})
STATUS = {"walk": "walking", "swim": "swimming", "fall": "falling", "mine": "mining", "place": "building",
          "eat": "eating", "craft": "crafting", "smelt": "smelting", "sleep": "sleeping", "wait": "idle"}
# Waits tell the viewer nothing and would push real steps out of the recent list.
UNRECORDED = frozenset({"wait"})
# Running steps a takeover may cut short. The others last a few seconds at most and finish first.
INTERRUPTIBLE = frozenset({"walk", "sleep", "wait"})
```

with:

```python
# The engine's own moves, next to the step kinds registered in backend.survival.steps: (status,
# counts as work).
HAZARDS = {"swim": ("swimming", True), "fall": ("falling", False)}
# Waits tell the viewer nothing and would push real steps out of the recent list.
UNRECORDED = frozenset({"wait"})
```

and replace:

```python
def ensure_actions(state: dict) -> None:
```

with:

```python
def status_of(kind: str) -> str:
    """The pet's status while a step or hazard of this kind runs."""
    step = step_kind(kind)
    return step.status if step is not None else HAZARDS.get(kind, ("idle", False))[0]


def is_working(kind: str) -> bool:
    """Whether a running step or hazard counts as work for the vitals."""
    step = step_kind(kind)
    return step.working if step is not None else HAZARDS.get(kind, ("idle", False))[1]


def is_interruptible(kind: str) -> bool:
    """Whether a takeover may cut a running step of this kind short (its StepKind says)."""
    step = step_kind(kind)
    return step is not None and step.interruptible


def ensure_actions(state: dict) -> None:
```

and replace:

```python
    return "working" if action["kind"] in WORKING else "idle"
```

with:

```python
    return "working" if is_working(action["kind"]) else "idle"
```

and replace:

```python
            if step["kind"] in INTERRUPTIBLE and takeovers < MAX_TAKEOVERS and interrupted(state, context, until):
```

with:

```python
            if is_interruptible(step["kind"]) and takeovers < MAX_TAKEOVERS and interrupted(state, context, until):
```

and replace:

```python
    state["status"] = STATUS.get(action["kind"], "idle") if action else "idle"
```

with:

```python
    state["status"] = status_of(action["kind"]) if action else "idle"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_steps.py"` and `python3 -m unittest discover -s backend/tests -p "test_survival_actions.py"`
Expected: `OK` for both.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 375 tests` … `OK` (4 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/steps.py backend/survival/actions.py backend/tests/test_survival_steps.py backend/tests/test_survival_actions.py
git commit -m "refactor: keep step kinds in a registry the engine reads" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 5: Field work: pick, harvest, till, plant, fish and cook

**Files:**
- Create: `backend/survival/nature.py`, `backend/survival/fieldwork.py`
- Modify: `backend/survival/steps.py`
- Test: `backend/tests/test_survival_fieldwork.py`

**Interfaces:**
- Consumes: Task 4's `StepKind`, `register_step`, `StepFailed`, `as_cell`, `as_point`, `in_reach`, `label`, `stations_near`; Task 2's `crafting.COOKING`, `crafting.FIRES`, `crafting.smelt`; `blocks.is_replaceable`; `worldgen.hash32`; `clock.DAY_SECONDS`.
- Produces:
  - `backend.survival.nature`: `CROPS = ("wheat", "carrot")`, `RIPE_STAGE = 3`, `CROP_BLOCKS` (`wheat_0` … `carrot_3`), `RIPE_CROPS = ("wheat_3", "carrot_3")`, `SEEDS = {"seeds": "wheat_0", "carrot": "carrot_0", "sapling": "sapling"}`, `SOIL`, `TILLABLE = ("grass", "dirt", "moss")`, `PICKS` (block → (items, what the cell becomes)), `MUSHROOMS`, `HARVESTS`, `CHANCE_DROPS`; `roll(seed, cell, channel, salt=0) -> float` in [0, 1); `crop_stage(material) -> tuple[str, int] | None`; `next_stage(material) -> str | None`; `chance_drops(seed, cell, block) -> list[str]`; fish: `FULL_STOCK = 12`, `CATCH_CHANCE = 0.9`, `REGION = 16`, `region_of(cell) -> str`, `fish_stock(state, cell) -> int`, `fish_seconds(seed, cell, at) -> float`, `catches(seed, cell, at, stock) -> bool`, `take_fish(state, cell, at)`, `recover_fish(state, at, scale)`.
  - `backend.survival.fieldwork`: step kinds `pick` (0.5 s, "picking", work), `harvest` (0.5 s, "harvesting", work), `till` (1 s, "tilling", work), `plant` (0.3 s, "planting", work, `item`), `fish` (20–60 s, "fishing", interruptible), `cook` (5 s, "cooking", `item`); `open_for_planting(material) -> bool`.
  - `backend.survival.steps`: `seed_of(state) -> str` (the world seed, "0" without one); mining a block rolls `nature.chance_drops`; the module imports `fieldwork` at its end.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_fieldwork.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival import nature
from backend.survival.grid import Grid
from backend.survival.steps import STEP_KINDS, StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS


def meadow(cells=None):
    """Grass at y 0 over dirt, air above; `cells` override single cells. Mimo stands at (0, 1, 0)."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("grass" if y == 0 else "dirt" if y < 0 else "air"))


def pet(**changes):
    state = {"name": "Pip", "world_seed": "7", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS)}
    state.update(changes)
    return state


def run(spec, state, grid, at=0.0):
    """Start a step and finish it at its end. Returns the running step and the event."""
    step = start_step(spec, state, grid, at)
    return step, finish_step(step, state, grid, step["ends_at"])


class NatureTests(unittest.TestCase):
    def test_crop_stages(self):
        self.assertEqual(nature.crop_stage("wheat_2"), ("wheat", 2))
        self.assertIsNone(nature.crop_stage("berry_bush"))
        self.assertIsNone(nature.crop_stage("wheat_9"))
        self.assertEqual(nature.next_stage("carrot_0"), "carrot_1")
        self.assertIsNone(nature.next_stage("carrot_3"))
        self.assertEqual(nature.RIPE_CROPS, ("wheat_3", "carrot_3"))

    def test_rolls_are_fixed_by_seed_cell_channel_and_salt(self):
        first = nature.roll("7", (1, 2, 3), 30)
        self.assertEqual(first, nature.roll("7", (1, 2, 3), 30))
        self.assertTrue(0.0 <= first < 1.0)
        self.assertNotEqual(first, nature.roll("7", (1, 2, 3), 30, salt=5))
        self.assertNotEqual(first, nature.roll("8", (1, 2, 3), 30))

    def test_chance_drops_follow_the_roll(self):
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "leaves"), ["sapling", "apple"])
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "tall_grass"), ["seeds", "carrot"])
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "stone"), [])
        with patch("backend.survival.nature.roll", lambda *args: 0.1):
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "tall_grass"), ["seeds"])
        with patch("backend.survival.nature.roll", lambda *args: 0.99):
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "leaves"), [])

    def test_fish_stocks_fall_with_each_catch_and_recover_one_a_game_day(self):
        state = pet()
        self.assertEqual(nature.fish_stock(state, (20, 2, 5)), 12)
        nature.take_fish(state, (20, 2, 5), 100.0)
        nature.take_fish(state, (31, 2, 15), 110.0)
        self.assertEqual(state["fish"], {"1,0": {"stock": 10, "since": 100.0}})
        self.assertEqual(nature.fish_stock(state, (16, 2, 0)), 10)
        nature.recover_fish(state, 100.0 + 3599.0, 1.0)
        self.assertEqual(state["fish"]["1,0"]["stock"], 10)
        nature.recover_fish(state, 100.0 + 3600.0, 1.0)
        self.assertEqual(state["fish"]["1,0"], {"stock": 11, "since": 3700.0})
        nature.recover_fish(state, 3700.0 + 60.0, 60.0)
        self.assertEqual(state["fish"], {})


class PickAndHarvestTests(unittest.TestCase):
    def test_picking_a_ripe_bush_gives_berries_and_leaves_the_bush(self):
        grid, state = meadow({(1, 1, 0): "berry_bush_ripe"}), pet()
        step, event = run({"kind": "pick", "target": [1, 1, 0]}, state, grid, 2.0)
        self.assertEqual((step["ends_at"], step["block"], event), (2.5, "berry_bush_ripe", None))
        self.assertEqual(state["inventory"], {"berries": 3})
        self.assertEqual(grid.material(1, 1, 0), "berry_bush")
        with self.assertRaises(StepFailed) as caught:
            start_step({"kind": "pick", "target": [1, 1, 0]}, state, grid, 3.0)
        self.assertEqual(caught.exception.code, "gone")

    def test_picking_a_mushroom_takes_it_whole(self):
        grid, state = meadow({(0, 1, 2): "red_mushroom"}), pet()
        run({"kind": "pick", "target": [0, 1, 2]}, state, grid)
        self.assertEqual((state["inventory"], grid.material(0, 1, 2)), ({"red_mushroom": 1}, "air"))

    def test_a_ripe_crop_is_harvested_and_the_farmland_stays(self):
        grid = meadow({(1, 0, 0): "farmland", (1, 1, 0): "wheat_3", (2, 0, 0): "farmland", (2, 1, 0): "carrot_1"})
        state = pet()
        run({"kind": "harvest", "target": [1, 1, 0]}, state, grid)
        self.assertEqual(state["inventory"], {"wheat": 1, "seeds": 2})
        self.assertEqual((grid.material(1, 1, 0), grid.material(1, 0, 0)), ("air", "farmland"))
        with self.assertRaisesRegex(StepFailed, "not ripe yet") as caught:
            start_step({"kind": "harvest", "target": [2, 1, 0]}, state, grid, 1.0)
        self.assertEqual(caught.exception.code, "blocked")

    def test_a_plant_that_changed_before_the_step_ended_is_gone(self):
        grid, state = meadow({(1, 1, 0): "berry_bush_ripe"}), pet()
        step = start_step({"kind": "pick", "target": [1, 1, 0]}, state, grid, 0.0)
        grid.put(1, 1, 0, "berry_bush")
        with self.assertRaises(StepFailed) as caught:
            finish_step(step, state, grid, 0.5)
        self.assertEqual(caught.exception.code, "gone")
        self.assertEqual(state["inventory"], {})


class TillAndPlantTests(unittest.TestCase):
    def test_tilling_turns_grass_into_farmland_and_the_tall_grass_on_it_goes(self):
        grid = Grid(lambda x, y, z: {(1, 1, 0): "tall_grass"}.get((x, y, z)) or ("grass" if y == 0 else "air"))
        state = pet()
        step, _ = run({"kind": "till", "target": [1, 0, 0]}, state, grid)
        self.assertEqual(step["ends_at"], 1.0)
        self.assertEqual((grid.material(1, 0, 0), grid.material(1, 1, 0)), ("farmland", "air"))
        with self.assertRaisesRegex(StepFailed, "cannot be tilled"):
            start_step({"kind": "till", "target": [1, 0, 0]}, state, grid, 2.0)
        bush = meadow({(0, 1, 1): "berry_bush"})
        with self.assertRaisesRegex(StepFailed, "something is on it"):
            start_step({"kind": "till", "target": [0, 0, 1]}, state, bush, 0.0)

    def test_seeds_go_on_farmland_and_saplings_on_grass(self):
        grid = meadow({(1, 0, 0): "farmland"})
        state = pet(inventory={"seeds": 1, "carrot": 1, "sapling": 1})
        step, _ = run({"kind": "plant", "target": [1, 1, 0], "item": "seeds"}, state, grid)
        self.assertEqual((step["block"], grid.material(1, 1, 0)), ("wheat_0", "wheat_0"))
        with self.assertRaisesRegex(StepFailed, "needs farmland") as caught:
            start_step({"kind": "plant", "target": [0, 1, 1], "item": "carrot"}, state, grid, 1.0)
        self.assertEqual(caught.exception.code, "blocked")
        run({"kind": "plant", "target": [0, 1, 2], "item": "sapling"}, state, grid)
        self.assertEqual(grid.material(0, 1, 2), "sapling")
        self.assertEqual(state["inventory"], {"carrot": 1})
        for spec, code in (({"kind": "plant", "target": [2, 1, 0], "item": "seeds"}, "missing_item"),
                           ({"kind": "plant", "target": [2, 1, 0], "item": "stone"}, "bad_step"),
                           ({"kind": "plant", "target": [1, 1, 0], "item": "carrot"}, "blocked")):
            with self.assertRaises(StepFailed, msg=spec) as caught:
                start_step(spec, state, grid, 2.0)
            self.assertEqual(caught.exception.code, code, spec)


class FishAndCookTests(unittest.TestCase):
    def test_fishing_takes_20_to_60_seconds_and_a_catch_lowers_the_stock(self):
        grid, state = meadow({(2, 0, 0): "water"}), pet()
        with patch("backend.survival.nature.roll", lambda *args: 0.5):
            step, event = run({"kind": "fish", "target": [2, 0, 0]}, state, grid, 10.0)
        self.assertEqual(step["ends_at"], 50.0)
        self.assertEqual(event, ("fish", "Pip caught a fish."))
        self.assertEqual((state["inventory"], nature.fish_stock(state, (2, 0, 0))), ({"raw_fish": 1}, 11))
        with patch("backend.survival.nature.roll", lambda *args: 0.95):
            step, event = run({"kind": "fish", "target": [2, 0, 0]}, state, grid, 60.0)
        self.assertEqual((step["ends_at"], event, state["inventory"]), (118.0, None, {"raw_fish": 1}))
        self.assertTrue(STEP_KINDS["fish"].interruptible)
        with self.assertRaisesRegex(StepFailed, "no water"):
            start_step({"kind": "fish", "target": [1, 0, 0]}, state, grid, 0.0)

    def test_an_empty_region_never_bites(self):
        grid, state = meadow({(2, 0, 0): "water"}), pet(fish={"0,0": {"stock": 0, "since": 0.0}})
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            self.assertIsNone(run({"kind": "fish", "target": [2, 0, 0]}, state, grid)[1])

    def test_cooking_needs_a_fire_within_reach_and_no_fuel(self):
        grid, state = meadow(), pet(inventory={"raw_fish": 1})
        with self.assertRaises(StepFailed) as caught:
            start_step({"kind": "cook", "item": "raw_fish"}, state, grid, 0.0)
        self.assertEqual(caught.exception.code, "missing_item")
        grid.put(2, 1, 0, "campfire")
        step, event = run({"kind": "cook", "item": "raw_fish"}, state, grid)
        self.assertEqual((step["ends_at"], event), (5.0, ("cook", "Pip cooked raw fish.")))
        self.assertEqual(state["inventory"], {"cooked_fish": 1})
        with self.assertRaisesRegex(StepFailed, "cannot be cooked"):
            start_step({"kind": "cook", "item": "iron_ore"}, pet(inventory={"iron_ore": 1}), grid, 0.0)

    def test_the_new_kinds_show_how_mimo_works(self):
        shown = {name: (STEP_KINDS[name].status, STEP_KINDS[name].working)
                 for name in ("pick", "harvest", "till", "plant", "fish", "cook")}
        self.assertEqual(shown, {"pick": ("picking", True), "harvest": ("harvesting", True), "till": ("tilling", True),
                                 "plant": ("planting", True), "fish": ("fishing", False), "cook": ("cooking", False)})


class ChanceDropTests(unittest.TestCase):
    def test_mining_leaves_and_tall_grass_may_drop_more(self):
        grid, state = meadow({(1, 1, 0): "leaves", (0, 1, 1): "tall_grass"}), pet()
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            run({"kind": "mine", "target": [1, 1, 0]}, state, grid)
            run({"kind": "mine", "target": [0, 1, 1]}, state, grid)
        self.assertEqual(state["inventory"], {"sapling": 1, "apple": 1, "seeds": 1, "carrot": 1})
        state = pet()
        with patch("backend.survival.nature.roll", lambda *args: 0.99):
            run({"kind": "mine", "target": [1, 1, 0]}, state, meadow({(1, 1, 0): "leaves"}))
        self.assertEqual(state["inventory"], {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_fieldwork.py"`
Expected: `ImportError: cannot import name 'nature' from 'backend.survival'`.

- [ ] **Step 3: Write the rules of nature**

Create `backend/survival/nature.py`:

```python
"""The living world's rules that M4 adds: what picking and harvesting give, what grows from a
seed and on what ground, crop stages, chance drops and fish stocks.

Chance comes from `roll`: a number in [0, 1) fixed by the world seed, a cell, a channel and a
salt (usually a time), so an outcome never depends on how often the tick ran and tests can patch
`roll` to force one.
"""

from __future__ import annotations

import math

from backend.services.worldgen import hash32
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import Cell

CROPS = ("wheat", "carrot")
RIPE_STAGE = 3
CROP_BLOCKS = tuple(f"{crop}_{stage}" for crop in CROPS for stage in range(RIPE_STAGE + 1))
RIPE_CROPS = tuple(f"{crop}_{RIPE_STAGE}" for crop in CROPS)
# What a planted item grows into, and the ground under it that it needs.
SEEDS = {"seeds": "wheat_0", "carrot": "carrot_0", "sapling": "sapling"}
SOIL = {"wheat_0": ("farmland",), "carrot_0": ("farmland",), "sapling": ("grass", "dirt", "moss")}
TILLABLE = ("grass", "dirt", "moss")
# pick(cell): what a wild plant gives and what the cell turns into.
PICKS = {"berry_bush_ripe": ({"berries": 3}, "berry_bush"),
         "brown_mushroom": ({"brown_mushroom": 1}, "air"),
         "red_mushroom": ({"red_mushroom": 1}, "air")}
MUSHROOMS = ("brown_mushroom", "red_mushroom")
# harvest(cell): what a ripe crop gives. The crop's cell turns to air; the farmland stays.
HARVESTS = {"wheat_3": {"wheat": 1, "seeds": 2}, "carrot_3": {"carrot": 3}}
# Extra drops when a block is mined, or a leaf decays: (item, chance, roll channel).
CHANCE_DROPS = {"tall_grass": (("seeds", 0.2, 30), ("carrot", 0.05, 31)),
                "leaves": (("sapling", 1 / 12, 32), ("apple", 1 / 20, 33))}


def roll(seed: str, cell: Cell, channel: int, salt: int = 0) -> float:
    """A number in [0, 1) fixed by the world seed, the cell, the channel and the salt."""
    x, y, z = cell
    return hash32(x, y, z + salt * 1_000_003, seed, channel) / 4294967296


def crop_stage(material: str) -> tuple[str, int] | None:
    """("wheat", 2) for wheat_2; None for anything that is not a crop."""
    name, _, stage = material.rpartition("_")
    if name in CROPS and stage.isdigit() and int(stage) <= RIPE_STAGE:
        return name, int(stage)
    return None


def next_stage(material: str) -> str | None:
    """The crop block one stage on (wheat_0 -> wheat_1), or None when ripe or not a crop."""
    stage = crop_stage(material)
    if stage is None or stage[1] >= RIPE_STAGE:
        return None
    return f"{stage[0]}_{stage[1] + 1}"


def chance_drops(seed: str, cell: Cell, block: str) -> list[str]:
    """The extra items a mined or decayed block drops at this cell."""
    return [item for item, chance, channel in CHANCE_DROPS.get(block, ()) if roll(seed, cell, channel) < chance]


# Fish ------------------------------------------------------------------------------------------
# state["fish"] = {"rx,rz": {"stock": n, "since": server time}} for 16x16 regions below a full
# stock. A region not listed is full. `since` is when the stock last grew (or first fell).

FISH_CATCH = 34
FISH_TIME = 35
FISH_SECONDS = (20.0, 60.0)
FULL_STOCK = 12
CATCH_CHANCE = 0.9  # with a full stock; the chance falls with the stock
REGION = 16


def region_of(cell: Cell) -> str:
    return f"{cell[0] // REGION},{cell[2] // REGION}"


def fish_stock(state: dict, cell: Cell) -> int:
    return state.get("fish", {}).get(region_of(cell), {"stock": FULL_STOCK})["stock"]


def fish_seconds(seed: str, cell: Cell, at: float) -> float:
    """How long one catch takes (game seconds): 20 to 60."""
    low, high = FISH_SECONDS
    return low + (high - low) * roll(seed, cell, FISH_TIME, int(at))


def catches(seed: str, cell: Cell, at: float, stock: int) -> bool:
    """Whether a catch started at `at` lands a fish, with the region's stock as it is."""
    return roll(seed, cell, FISH_CATCH, int(at)) < CATCH_CHANCE * stock / FULL_STOCK


def take_fish(state: dict, cell: Cell, at: float) -> None:
    entry = state.setdefault("fish", {}).setdefault(region_of(cell), {"stock": FULL_STOCK, "since": at})
    entry["stock"] = max(0, entry["stock"] - 1)


def recover_fish(state: dict, at: float, scale: float) -> None:
    """Every region gains one fish per game day until it is full again."""
    stocks = state.get("fish") or {}
    for key in list(stocks):
        entry = stocks[key]
        days = math.floor((at - entry["since"]) * scale / DAY_SECONDS)
        if days <= 0:
            continue
        entry["stock"] = min(FULL_STOCK, entry["stock"] + days)
        entry["since"] += days * DAY_SECONDS / scale
        if entry["stock"] >= FULL_STOCK:
            del stocks[key]
```

- [ ] **Step 4: Write the field work steps**

Create `backend/survival/fieldwork.py`:

```python
"""Field work: the step kinds M4 adds, registered in backend.survival.steps.

- pick(cell): take what a wild plant gives (nature.PICKS). A ripe berry bush gives 3 berries and
  turns back into a bush that regrows; a mushroom is taken whole.
- harvest(cell): take a ripe crop (nature.HARVESTS). The farmland under it stays.
- till(cell): turn grass, dirt or moss with nothing growing on it into farmland.
- plant(cell, item): put seeds or a carrot on farmland, or a sapling on grass, dirt or moss.
- fish(water cell): 20 to 60 s per catch. Whether a fish bites depends on the stock of the water
  cell's 16x16 region (nature.catches); a catch takes one fish from it. A reflex may cut it short.
- cook(item): 5 s at a lit campfire or furnace within 6 blocks, with no fuel (crafting.smelt's
  rule for food).
All of them work on a cell within reach, like mining. steps.py imports this module last, so
start_step always knows these kinds.
"""

from __future__ import annotations

from backend.services.blocks import is_replaceable
from backend.services.crafting import COOKING, FIRES, add_item, smelt, take_items
from backend.survival import nature
from backend.survival.grid import Cell, Grid
from backend.survival.steps import (
    StepFailed, StepKind, as_cell, as_point, in_reach, label, register_step, seed_of, stations_near,
)

PICK_SECONDS = 0.5
HARVEST_SECONDS = 0.5
TILL_SECONDS = 1.0
PLANT_SECONDS = 0.3
COOK_SECONDS = 5.0


def target_in_reach(spec: dict, state: dict) -> Cell:
    target = as_cell(spec["target"])
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    return target


def running(kind: str, at: float, seconds: float, target: Cell, **fields) -> dict:
    return {"kind": kind, "started_at": at, "ends_at": round(at + seconds, 3), "target": as_point(target), **fields}


def still_there(step: dict, grid: Grid) -> Cell:
    target = as_cell(step["target"])
    if grid.material(*target) != step["block"]:
        raise StepFailed(f"the {label(step['block'])} is gone", "gone")
    return target


def open_for_planting(material: str) -> bool:
    """Air, or a plant that gives way (tall grass, flowers). Never water."""
    return material != "water" and is_replaceable(material)


def check_planting(grid: Grid, target: Cell, grows: str) -> None:
    x, y, z = target
    if not open_for_planting(grid.material(*target)):
        raise StepFailed("that cell is taken", "blocked")
    if grid.material(x, y - 1, z) not in nature.SOIL[grows]:
        raise StepFailed(f"{label(grows)} needs {' or '.join(nature.SOIL[grows])} under it", "blocked")


def start_pick(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = target_in_reach(spec, state)
    material = grid.material(*target)
    if material not in nature.PICKS:
        raise StepFailed("nothing to pick there", "gone")
    return running("pick", at, PICK_SECONDS / scale, target, block=material)


def finish_pick(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = still_there(step, grid)
    items, becomes = nature.PICKS[step["block"]]
    for item, amount in items.items():
        add_item(state["inventory"], item, amount)
    grid.put(*target, becomes)
    return None


def start_harvest(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = target_in_reach(spec, state)
    material = grid.material(*target)
    if material not in nature.HARVESTS:
        stage = nature.crop_stage(material)
        if stage is not None:
            raise StepFailed(f"the {stage[0]} is not ripe yet", "blocked")
        raise StepFailed("nothing to harvest there", "gone")
    return running("harvest", at, HARVEST_SECONDS / scale, target, block=material)


def finish_harvest(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = still_there(step, grid)
    for item, amount in nature.HARVESTS[step["block"]].items():
        add_item(state["inventory"], item, amount)
    grid.put(*target, "air")
    return None


def start_till(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = target_in_reach(spec, state)
    x, y, z = target
    material = grid.material(*target)
    if material not in nature.TILLABLE:
        raise StepFailed(f"{label(material)} cannot be tilled", "blocked")
    if not open_for_planting(grid.material(x, y + 1, z)):
        raise StepFailed("something is on it", "blocked")
    return running("till", at, TILL_SECONDS / scale, target, block=material)


def finish_till(step: dict, state: dict, grid: Grid, at: float) -> None:
    grid.put(*still_there(step, grid), "farmland")
    return None


def start_plant(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item = spec["item"]
    grows = nature.SEEDS.get(item)
    if grows is None:
        raise StepFailed(f"{label(item)} cannot be planted")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to plant", "missing_item")
    target = target_in_reach(spec, state)
    check_planting(grid, target, grows)
    return running("plant", at, PLANT_SECONDS / scale, target, item=item, block=grows)


def finish_plant(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = as_cell(step["target"])
    check_planting(grid, target, step["block"])
    state["inventory"] = take_items(state["inventory"], {step["item"]: 1})
    grid.put(*target, step["block"])
    return None


def start_fish(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = target_in_reach(spec, state)
    if grid.material(*target) != "water":
        raise StepFailed("there is no water there", "gone")
    return running("fish", at, nature.fish_seconds(seed_of(state), target, at) / scale, target)


def finish_fish(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str] | None:
    target = as_cell(step["target"])
    if not nature.catches(seed_of(state), target, step["started_at"], nature.fish_stock(state, target)):
        return None
    nature.take_fish(state, target, at)
    add_item(state["inventory"], "raw_fish")
    return "fish", f"{state['name']} caught a fish."


def start_cook(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item = spec["item"]
    if item not in COOKING:
        raise StepFailed(f"{label(item)} cannot be cooked")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to cook", "missing_item")
    if not stations_near(grid, as_cell(state["position"])).intersection(FIRES):
        raise StepFailed("no fire to cook on", "missing_item")
    return {"kind": "cook", "started_at": at, "ends_at": round(at + COOK_SECONDS / scale, 3), "item": item}


def finish_cook(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    stations = stations_near(grid, as_cell(state["position"]))
    state["inventory"] = smelt(state["inventory"], step["item"], stations)
    return "cook", f"{state['name']} cooked {label(step['item'])}."


register_step(StepKind("pick", start_pick, finish_pick, "picking", working=True, cell_field="target"))
register_step(StepKind("harvest", start_harvest, finish_harvest, "harvesting", working=True, cell_field="target"))
register_step(StepKind("till", start_till, finish_till, "tilling", working=True, cell_field="target"))
register_step(StepKind("plant", start_plant, finish_plant, "planting", working=True, cell_field="target",
                       string_field="item"))
register_step(StepKind("fish", start_fish, finish_fish, "fishing", interruptible=True, cell_field="target"))
register_step(StepKind("cook", start_cook, finish_cook, "cooking", string_field="item"))
```

- [ ] **Step 5: Register them from the steps module and roll drops when mining**

In `backend/survival/steps.py`, replace:

```python
engine (backend.survival.actions) asks the registry, so a new kind only has to register.
"""
```

with:

```python
engine (backend.survival.actions) asks the registry, so a new kind only has to register. M4's
field work (pick, harvest, till, plant, fish, cook) lives in backend.survival.fieldwork. Mining
leaves or tall grass may drop more (nature.CHANCE_DROPS): saplings, apples, seeds.
"""
```

and replace:

```python
from backend.services.crafting import BLOCKS, add_item, can_harvest, craft, smelt, take_items
from backend.survival.grid import Cell, Grid
```

with:

```python
from backend.services.crafting import BLOCKS, add_item, can_harvest, craft, smelt, take_items
from backend.survival import nature
from backend.survival.grid import Cell, Grid
```

and replace:

```python
def in_reach(here: Cell, target: Cell) -> bool:
```

with:

```python
def seed_of(state: dict) -> str:
    """The world seed chance is rolled from (tests without one roll from "0")."""
    return state.get("world_seed", "0")


def in_reach(here: Cell, target: Cell) -> bool:
```

and replace:

```python
    drop = BLOCKS.get(step["block"], {}).get("drop")
    if drop:
        add_item(state["inventory"], drop)
    return None
```

with:

```python
    drop = BLOCKS.get(step["block"], {}).get("drop")
    if drop:
        add_item(state["inventory"], drop)
    for item in nature.chance_drops(seed_of(state), target, step["block"]):
        add_item(state["inventory"], item)
    return None
```

In `backend/survival/steps.py`, append:

```python

# M4's field work (pick, harvest, till, plant, fish, cook) registers itself. It is imported last
# because it builds on everything above.
from backend.survival import fieldwork  # noqa: E402,F401
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_fieldwork.py"`
Expected: `Ran 15 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 390 tests` … `OK` (15 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/nature.py backend/survival/fieldwork.py backend/survival/steps.py backend/tests/test_survival_fieldwork.py
git commit -m "feat: pick, harvest, till, plant, fish and cook as registered steps" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: Renewal: the growth table in the tick

**Files:**
- Create: `backend/survival/renewal.py`
- Modify: `backend/survival/grid.py`, `backend/survival/world.py`, `backend/survival/tick.py`
- Test: `backend/tests/test_survival_renewal.py`

**Interfaces:**
- Consumes: Task 5's `nature.next_stage`, `nature.crop_stage`, `nature.recover_fish`; `ActionContext` (`db`, `grid`, `clock_at`, `events`); `clock.DAY_SECONDS`; `world.create_world_tables`; `tick.advance_world`.
- Produces:
  - `backend.survival.grid`: `Grid.changes: list[tuple[Cell, str, str]]` and `Grid.take_changes() -> list[tuple[Cell, str, str]]` ((cell, before, after) of every `put` since the last call).
  - `backend.survival.renewal`: `BERRY_REGROW = 7200.0`, `CROP_STAGE_WET = 720.0`, `CROP_STAGE_DRY = 2160.0`, `FARMLAND_REVERT = 7200.0`, `WATER_REACH = 4`, `MAX_APPLIED = 512`; `Entry = tuple[Cell, str, float]`; `create_growth_table(db)`; `schedule(db, cell, block, ready_at, keep_earlier=False)`; `due(db, until, limit) -> list[Entry]`; `scheduled(db) -> list[Entry]`; `later(at, game_seconds, scale) -> float`; `watered(grid, farmland) -> bool`; `stage_seconds(grid, crop) -> float`; `react(db, grid, state, changes, at, scale)`; `apply_entry(db, grid, state, entry, scale, events)`; `renew(state, context, at)`.
  - `backend.survival.tick`: `run_renewal(state, context, at)` (crashes logged once as "renewal"), called after each chunk of actions in `advance_world` and after the last.
  - The world schema has a `growth` table (x, y, z, block, ready_at; one row per cell) indexed by `ready_at`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_renewal.py`:

```python
import logging
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.block_table import write_block
from backend.survival.actions import ActionContext
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.renewal import create_growth_table, renew, schedule, scheduled
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld

DAY = 3600.0
BORN = 1_000_000.0


def field(cells=None):
    """Grass at y 0 over dirt, air above, with `cells` overriding single cells."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("grass" if y == 0 else "dirt" if y < 0 else "air"))


def world(grid=None, scale=1.0):
    """A tick's context with a growth table, over `grid`."""
    db = sqlite3.connect(":memory:")
    create_growth_table(db)
    return ActionContext(grid=grid or field(), clock_at=lambda at: {"time_scale": scale}, planner=lambda *args: [],
                         events=[], db=db)


def pet(**changes):
    state = {"name": "Pip", "world_seed": "7", "position": {"x": 8.0, "y": 1.0, "z": 0.0}, "inventory": {}}
    state.update(changes)
    return state


class GrowthTests(unittest.TestCase):
    def test_a_picked_bush_is_ripe_again_after_two_game_days(self):
        ctx, state = world(), pet()
        ctx.grid.put(3, 1, 0, "berry_bush")
        renew(state, ctx, 100.0)
        self.assertEqual(scheduled(ctx.db), [((3, 1, 0), "berry_bush_ripe", 100.0 + 2 * DAY)])
        renew(state, ctx, 100.0 + 2 * DAY - 1)
        self.assertEqual(ctx.grid.material(3, 1, 0), "berry_bush")
        renew(state, ctx, 100.0 + 2 * DAY)
        self.assertEqual(ctx.grid.material(3, 1, 0), "berry_bush_ripe")
        self.assertEqual(scheduled(ctx.db), [])

    def test_the_time_scale_speeds_regrowth_up(self):
        ctx = world(scale=60.0)
        ctx.grid.put(3, 1, 0, "berry_bush")
        renew(pet(), ctx, 0.0)
        self.assertEqual(scheduled(ctx.db)[0][2], 2 * DAY / 60)

    def test_crops_grow_a_stage_every_12_game_minutes_near_water_and_36_without(self):
        wet = world(field({(0, 0, 0): "farmland", (4, 0, 0): "water"}))
        dry = world(field({(0, 0, 0): "farmland"}))
        for ctx in (wet, dry):
            ctx.grid.put(0, 1, 0, "wheat_0")
            renew(pet(), ctx, 0.0)
        self.assertEqual(scheduled(wet.db), [((0, 1, 0), "wheat_1", 720.0)])
        self.assertEqual(scheduled(dry.db), [((0, 1, 0), "wheat_1", 2160.0)])
        renew(pet(), wet, 2159.0)
        self.assertEqual(wet.grid.material(0, 1, 0), "wheat_2")
        renew(pet(), wet, 2160.0)
        self.assertEqual((wet.grid.material(0, 1, 0), scheduled(wet.db)), ("wheat_3", []))
        renew(pet(), dry, 3 * 2160.0)
        self.assertEqual(dry.grid.material(0, 1, 0), "wheat_3")

    def test_farmland_without_a_crop_turns_back_to_dirt_after_two_game_days(self):
        ctx = world()
        ctx.grid.put(0, 0, 0, "farmland")
        ctx.grid.put(1, 0, 0, "farmland")
        ctx.grid.put(1, 1, 0, "carrot_0")
        renew(pet(), ctx, 0.0)
        renew(pet(), ctx, 2 * DAY)
        self.assertEqual((ctx.grid.material(0, 0, 0), ctx.grid.material(1, 0, 0)), ("dirt", "farmland"))

    def test_harvesting_starts_the_farmland_clock_again(self):
        ctx = world(field({(0, 0, 0): "farmland", (0, 1, 0): "carrot_3"}))
        ctx.grid.put(0, 1, 0, "air")
        renew(pet(), ctx, 50.0)
        self.assertEqual(scheduled(ctx.db), [((0, 0, 0), "dirt", 50.0 + 2 * DAY)])

    def test_an_entry_whose_cell_changed_is_dropped(self):
        ctx = world()
        schedule(ctx.db, (5, 1, 5), "berry_bush_ripe", 10.0)
        schedule(ctx.db, (6, 1, 5), "wheat_2", 10.0)
        renew(pet(), ctx, 20.0)
        self.assertEqual((ctx.grid.material(5, 1, 5), ctx.grid.material(6, 1, 5)), ("air", "air"))
        self.assertEqual(scheduled(ctx.db), [])

    def test_fish_stocks_recover_in_the_renewal_pass(self):
        state = pet(fish={"0,0": {"stock": 5, "since": 0.0}})
        renew(state, world(), 2 * DAY)
        self.assertEqual(state["fish"]["0,0"], {"stock": 7, "since": 2 * DAY})

    def test_the_grid_keeps_each_change_until_it_is_taken(self):
        grid = field({(1, 1, 0): "tall_grass"})
        grid.put(1, 1, 0, "air")
        grid.put(1, 0, 0, "farmland")
        self.assertEqual(grid.take_changes(), [((1, 1, 0), "tall_grass", "air"), ((1, 0, 0), "grass", "farmland")])
        self.assertEqual(grid.take_changes(), [])


class RenewalTickTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        position = self.world.state()["position"]
        self.cell = (round(position["x"]) + 3, round(position["y"]), round(position["z"]))
        with self.world.transaction() as db:
            write_block(db, *self.cell, "berry_bush")
            schedule(db, self.cell, "berry_bush_ripe", BORN + 30)

    def tearDown(self):
        self.directory.cleanup()

    def test_the_tick_applies_growth_that_is_due(self):
        tick_life(self.registry, BORN + 20, scale=1)
        self.assertEqual(self.world.material_at(*self.cell), "berry_bush")
        tick_life(self.registry, BORN + 40, scale=1)
        self.assertEqual(self.world.material_at(*self.cell), "berry_bush_ripe")

    def test_a_crashing_renewal_is_logged_once_and_the_tick_goes_on(self):
        def boom(state, context, at):
            raise RuntimeError("boom")

        forget_logged()
        with patch("backend.survival.tick.renew", boom), self.assertLogs("backend.survival.tick", logging.ERROR) as logs:
            tick_life(self.registry, BORN + 20, scale=1)
            state = tick_life(self.registry, BORN + 40, scale=1)
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(state["last_tick_at"], BORN + 40)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_renewal.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.renewal'`.

- [ ] **Step 3: Let the grid keep its changes**

In `backend/survival/grid.py`, replace:

```python
passes it to the world's write_block, so viewers receive it through block sync.
"""
```

with:

```python
passes it to the world's write_block, so viewers receive it through block sync. It also keeps
each change until `take_changes` collects it, so renewal can react to what Mimo changed.
"""
```

and replace:

```python
        self.edits: dict[Cell, str] = {}
```

with:

```python
        self.edits: dict[Cell, str] = {}
        self.changes: list[tuple[Cell, str, str]] = []
```

and replace:

```python
    def put(self, x: int, y: int, z: int, material: str) -> None:
        self._load(x, z)
        self.edits[(x, y, z)] = material
        if self._write is not None:
            self._write(x, y, z, material)
```

with:

```python
    def put(self, x: int, y: int, z: int, material: str) -> None:
        before = self.material(x, y, z)
        self.edits[(x, y, z)] = material
        self.changes.append(((x, y, z), before, material))
        if self._write is not None:
            self._write(x, y, z, material)

    def take_changes(self) -> list[tuple[Cell, str, str]]:
        """(cell, before, after) for every put since the last call, oldest first."""
        changes, self.changes = self.changes, []
        return changes
```

- [ ] **Step 4: Write the renewal pass**

Create `backend/survival/renewal.py`:

```python
"""Renewal: the world regrows on its own clock, whatever Mimo is doing.

Each world database keeps a `growth` table of changes due later: (x, y, z, block, ready_at),
one per cell, with `ready_at` in server time. `renew` is part of the world, not of Mimo's mind:
advance_world runs it after every catch-up chunk of actions (at most 60 game seconds), so a
long gap regrows the world in time order. Each call:

1. Reacts to the blocks Mimo's steps changed since the last call (Grid.take_changes):
   - a picked berry bush turns ripe again after 2 game days;
   - a crop grows one stage every 12 game minutes when water lies within 4 blocks of its
     farmland, and every 36 game minutes otherwise;
   - farmland turns back into dirt after 2 game days without a crop (tilled, or a crop taken
     from it), unless a crop grows on it by then.
2. Applies every entry due by then, oldest first. An entry only happens while its cell still
   holds what it grows from (the unripe bush, the crop one stage earlier, the bare farmland);
   otherwise it is dropped. A crop stage that happens schedules the next one from its own due
   time, so a long catch-up still grows a crop through every stage.
3. Lets fish stocks recover, one fish per region per game day (nature.recover_fish).
Mined ore never comes back: nothing schedules it.
"""

from __future__ import annotations

import sqlite3

from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import Cell, Grid

BERRY_REGROW = 2 * DAY_SECONDS
CROP_STAGE_WET = 12 * 60.0
CROP_STAGE_DRY = 36 * 60.0
FARMLAND_REVERT = 2 * DAY_SECONDS
WATER_REACH = 4
MAX_APPLIED = 512  # entries one call applies at most; the rest wait for the next call

Entry = tuple[Cell, str, float]


def create_growth_table(db: sqlite3.Connection) -> None:
    """Create the growth table. Run it inside the caller's BEGIN IMMEDIATE."""
    db.execute("CREATE TABLE IF NOT EXISTS growth (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, "
               "block TEXT NOT NULL, ready_at REAL NOT NULL, PRIMARY KEY (x, y, z))")
    db.execute("CREATE INDEX IF NOT EXISTS growth_by_time ON growth(ready_at)")


def schedule(db: sqlite3.Connection, cell: Cell, block: str, ready_at: float, keep_earlier: bool = False) -> None:
    """Make `cell` turn into `block` at `ready_at`, replacing what was due there (or, with
    `keep_earlier`, leaving an entry that is already due there alone)."""
    verb = "INSERT OR IGNORE" if keep_earlier else "INSERT OR REPLACE"
    db.execute(f"{verb} INTO growth(x, y, z, block, ready_at) VALUES (?, ?, ?, ?, ?)", (*cell, block, ready_at))


def due(db: sqlite3.Connection, until: float, limit: int) -> list[Entry]:
    rows = db.execute("SELECT x, y, z, block, ready_at FROM growth WHERE ready_at <= ? "
                      "ORDER BY ready_at, x, y, z LIMIT ?", (until, limit)).fetchall()
    return [((row[0], row[1], row[2]), row[3], row[4]) for row in rows]


def scheduled(db: sqlite3.Connection) -> list[Entry]:
    """Every entry, soonest first (for tests and checks)."""
    return due(db, float("inf"), 1_000_000)


def later(at: float, game_seconds: float, scale: float) -> float:
    return at + game_seconds / scale


def watered(grid: Grid, farmland: Cell) -> bool:
    """Water within 4 blocks of the farmland, at its level or one above or below."""
    x, y, z = farmland
    return any(grid.water((x + dx, y + dy, z + dz)) for dy in (0, -1, 1)
               for dx in range(-WATER_REACH, WATER_REACH + 1) for dz in range(-WATER_REACH, WATER_REACH + 1))


def stage_seconds(grid: Grid, crop: Cell) -> float:
    x, y, z = crop
    return CROP_STAGE_WET if watered(grid, (x, y - 1, z)) else CROP_STAGE_DRY


def react(db: sqlite3.Connection, grid: Grid, state: dict, changes: list[tuple[Cell, str, str]], at: float,
          scale: float) -> None:
    """Schedule what the changed blocks will turn into."""
    for cell, before, after in changes:
        x, y, z = cell
        grown = nature.next_stage(after)
        if after == "berry_bush":
            schedule(db, cell, "berry_bush_ripe", later(at, BERRY_REGROW, scale))
        elif grown is not None:
            schedule(db, cell, grown, later(at, stage_seconds(grid, cell), scale))
        elif after == "farmland":
            schedule(db, cell, "dirt", later(at, FARMLAND_REVERT, scale))
        elif nature.crop_stage(before) is not None and grid.material(x, y - 1, z) == "farmland":
            schedule(db, (x, y - 1, z), "dirt", later(at, FARMLAND_REVERT, scale))


def apply_entry(db: sqlite3.Connection, grid: Grid, state: dict, entry: Entry, scale: float,
                events: list) -> None:
    """Make one due change happen if its cell still holds what it grows from."""
    cell, block, ready_at = entry
    x, y, z = cell
    here = grid.material(*cell)
    stage = nature.crop_stage(block)
    if block == "berry_bush_ripe":
        if here == "berry_bush":
            grid.put(*cell, block)
    elif stage is not None:
        crop, number = stage
        if here == f"{crop}_{number - 1}" and grid.material(x, y - 1, z) == "farmland":
            grid.put(*cell, block)
            grown = nature.next_stage(block)
            if grown is not None:
                schedule(db, cell, grown, later(ready_at, stage_seconds(grid, cell), scale))
    elif block == "dirt":
        if here == "farmland" and nature.crop_stage(grid.material(x, y + 1, z)) is None:
            grid.put(*cell, "dirt")


def renew(state: dict, context, at: float) -> None:
    """The world's own changes up to `at` (see the module docstring). Needs the tick's database."""
    db, grid = context.db, context.grid
    if db is None:
        return
    scale = context.clock_at(at)["time_scale"]
    react(db, grid, state, grid.take_changes(), at, scale)
    applied = 0
    while applied < MAX_APPLIED:
        entries = due(db, at, MAX_APPLIED - applied)
        if not entries:
            break
        for entry in entries:
            db.execute("DELETE FROM growth WHERE x=? AND y=? AND z=?", entry[0])
            apply_entry(db, grid, state, entry, scale, context.events)
            applied += 1
    grid.take_changes()  # renewal's own writes need no reaction
    nature.recover_fish(state, at, scale)
```

- [ ] **Step 5: Give every world a growth table and run renewal in the tick**

In `backend/survival/world.py`, replace:

```python
from backend.survival.memory import create_memory_tables
```

with:

```python
from backend.survival.memory import create_memory_tables
from backend.survival.renewal import create_growth_table
```

and replace:

```python
    create_block_tables(db)
    create_memory_tables(db)
```

with:

```python
    create_block_tables(db)
    create_memory_tables(db)
    create_growth_table(db)
```

In `backend/survival/tick.py`, replace:

```python
notice each vitals step (`notice`). Minds never call a model here: the tick holds the world's
write transaction.
"""
```

with:

```python
notice each vitals step (`notice`). Minds never call a model here: the tick holds the world's
write transaction. After each chunk of actions the world regrows on its own
(backend.survival.renewal), whatever mind runs Mimo.
"""
```

and replace:

```python
from backend.survival.registry import LifeRegistry
from backend.survival.script import rest_plan
```

with:

```python
from backend.survival.registry import LifeRegistry
from backend.survival.renewal import renew
from backend.survival.script import rest_plan
```

and replace:

```python
def advance_world(world: SurvivalWorld, timestamp: float, scale: float, mind: Mind = RESTING,
```

with:

```python
def run_renewal(state: dict, context: ActionContext, at: float) -> None:
    """Let the world regrow up to `at` (backend.survival.renewal). A crash is logged once and the
    tick goes on."""
    try:
        renew(state, context, at)
    except Exception as error:
        log_once(logger, "renewal", error)


def advance_world(world: SurvivalWorld, timestamp: float, scale: float, mind: Mind = RESTING,
```

and replace:

```python
                record_death(state, "fall", fell_at, scale, events)
                break
            step = min(MAX_STEP_SECONDS, remaining)
```

with:

```python
                record_death(state, "fall", fell_at, scale, events)
                break
            run_renewal(state, context, cursor)
            step = min(MAX_STEP_SECONDS, remaining)
```

and replace:

```python
            fell_at = advance_actions(state, context, timestamp)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
```

with:

```python
            fell_at = advance_actions(state, context, timestamp)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
            else:
                run_renewal(state, context, timestamp)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_renewal.py"`
Expected: `Ran 10 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 400 tests` … `OK` (10 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/renewal.py backend/survival/grid.py backend/survival/world.py backend/survival/tick.py backend/tests/test_survival_renewal.py
git commit -m "feat: regrow bushes and crops and revert idle farmland from a growth table in the tick" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 7: Trees, leaves and mushrooms come back or go (first an M3 fix: mine_ore leaves passage floors alone)

**Files:**
- Modify: `backend/survival/renewal.py`, `backend/survival/snapshot.py`, `backend/survival/work.py` (Steps 1–3)
- Test: `backend/tests/test_survival_renewal.py`, `backend/tests/test_survival_api.py`, `backend/tests/test_survival_work.py`

**Interfaces:**
- Consumes: Task 6's `renewal` (`schedule`, `later`, `react`, `apply_entry`); Task 5's `nature.roll`, `nature.chance_drops`, `nature.MUSHROOMS`; `senses.LOG`, `senses.TRUNK_HEIGHT`; `worldgen.is_leaf`, `worldgen.biome_at`, `worldgen.terrain_height`; `crafting.add_item`.
- Produces:
  - `backend.survival.renewal`: `LEAF_REACH = 4`, `DECAY_SECONDS = (60.0, 360.0)`, `DROP_REACH = 16.0`, `DECAYS_KEPT = 24`, `SAPLING_GROWS = 3600.0`, `SAPLING_RETRY = 600.0`, `MUSHROOM_RESPAWN = 3600.0`, `MUSHROOM_CAP = 3`, `FOREST_FLOOR = ("grass", "moss")`; `leaf_supported(grid, leaf) -> bool`; `orphaned_leaves(grid, log) -> list[Cell]`; `decay_seconds(seed, leaf, at) -> float`; `tree_cells(sapling) -> tuple[list[Cell], list[Cell]]`; `tree_fits(grid, sapling) -> bool`; `grow_tree(grid, sapling)`; `forest_floor(grid, seed, chunk, at) -> Cell | None`; `mushrooms_in_chunk(grid, seed, chunk) -> int`; `respawn_mushroom(db, grid, seed, picked, kind, at, scale)`; `pet_cell(state) -> Cell`; `decay(state, leaf, at)`. Growth rows with block `oak_log` grow a sapling into a tree, `air` decays a leaf, a mushroom name respawns one. The event `("grow", "A sapling grew into a tree.")`.
  - `state["decays"]`: the newest 24 `{"x", "y", "z", "at"}`; `/api/mimo` returns it as `decays` (`[]` before any).
  - `backend.survival.work`: `passage_floor(s, cell) -> bool`; `ore_targets` leaves out ores that are the floor of an open cell below the natural surface (an M3 fix, Steps 1–3).

- [ ] **Step 1: Write the failing test for ores in a passage floor**

This task first fixes an M3 bug that its leaf decay uncovers. With leaf decay, the leaves of a chopped tree drop saplings and apples into Mimo's pack, the fake Jev of the fix wave's headless check (`test_survival_sim.py`, seed 3) then picks differently, and on that path mine_ore mines a coal ore that is the floor of one of gather_stone's stairs. That stair cell can no longer be stood on, the next stair up is out of reach from below, and Mimo sleeps the night sealed in 5 cells: `AssertionError: 1440.0 not less than or equal to 180.0`. `stair` already leaves such floors alone; mine_ore now does too. If the fix wave has already fixed this, skip Steps 1–3.

In `backend/tests/test_survival_work.py`, replace:

```python
    def test_only_ores_mimo_still_needs_are_wanted(self):
        grid = ground({(2, 0, 0): "coal_ore"})
        seen = [("ore", (2, 0, 0), "coal_ore")]
        self.assertTrue(PURPOSES["mine_ore"].valid(situation(pet(inventory={"wooden_pickaxe": 1}), grid, seen)))
        stocked = pet(inventory={"wooden_pickaxe": 1, "coal": 8})
        self.assertFalse(PURPOSES["mine_ore"].valid(situation(stocked, grid, seen)))
```

with:

```python
    def test_only_ores_mimo_still_needs_are_wanted(self):
        grid = ground({(2, 0, 0): "coal_ore"})
        seen = [("ore", (2, 0, 0), "coal_ore")]
        self.assertTrue(PURPOSES["mine_ore"].valid(situation(pet(inventory={"wooden_pickaxe": 1}), grid, seen)))
        stocked = pet(inventory={"wooden_pickaxe": 1, "coal": 8})
        self.assertFalse(PURPOSES["mine_ore"].valid(situation(stocked, grid, seen)))

    def test_an_ore_in_the_floor_of_a_stair_is_left_alone(self):
        seen = [("ore", (3, -3, 0), "iron_ore")]
        cut = situation(pet(inventory={"stone_pickaxe": 1}), ground({(3, -3, 0): "iron_ore", (3, -2, 0): "air",
                                                                     (3, -1, 0): "air"}), seen)
        self.assertFalse(PURPOSES["mine_ore"].valid(cut))
        buried = situation(pet(inventory={"stone_pickaxe": 1}), ground({(3, -3, 0): "iron_ore"}), seen)
        self.assertTrue(PURPOSES["mine_ore"].valid(buried))
```


Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py"`
Expected: `FAIL: test_an_ore_in_the_floor_of_a_stair_is_left_alone` (`AssertionError: True is not false`).

- [ ] **Step 2: Leave ores in a passage floor alone**

In `backend/survival/work.py`, replace the whole `ore_targets` function with:

```python
def passage_floor(s: Situation, cell: Cell) -> bool:
    """The block is the floor of an open cell below the natural surface: a stair or tunnel Mimo dug,
    or a cave. Mining it can cut Mimo's way back up (a stair one step higher is then out of reach),
    so ores there are left alone, as `stair` leaves such floors alone."""
    x, y, z = cell
    return y + 1 <= terrain_height(x, z, s.seed) and not is_solid(s.grid.material(x, y + 1, z))


def ore_targets(s: Situation) -> list[dict]:
    """Remembered, wanted ores Mimo can harvest within 48 blocks, nearest first, leaving out ores
    that are the floor of a passage."""
    wanted, (x, _, z) = wanted_ores(s), s.here
    found = [place for place in s.places
             if place["kind"] == "ore" and place["note"] in wanted and can_harvest(place["note"], s.inventory)
             and math.hypot(place["x"] - x, place["z"] - z) <= ORE_RANGE and not passage_floor(s, cell_of(place))]
    return sorted(found, key=lambda place: s.distance(cell_of(place)))
```

- [ ] **Step 3: Run the tests and commit**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 401 tests` … `OK` (1 new).

```bash
git add backend/survival/work.py backend/tests/test_survival_work.py
git commit -m "fix: never mine an ore out of the floor of a stair, tunnel or cave" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Write the failing tests**

In `backend/tests/test_survival_renewal.py`, replace:

```python
from backend.services.block_table import write_block
```

with:

```python
from backend.services.block_table import write_block
from backend.services.worldgen import is_leaf
```

In `backend/tests/test_survival_renewal.py`, add this code before `class RenewalTickTests`:

```python
def forest(extra=None):
    """Grass at y 0 with one tree like worldgen's rooted at (0, 0): logs at y 1 to 4, leaves at 5 and 6."""
    extra = extra or {}

    def rule(x, y, z):
        if (x, y, z) in extra:
            return extra[(x, y, z)]
        if (x, z) == (0, 0) and 1 <= y <= 4:
            return "oak_log"
        if is_leaf(x, y, z):
            return "leaves"
        return "grass" if y == 0 else "dirt" if y < 0 else "air"

    return Grid(rule)


def chop(grid, heights=(1, 2, 3, 4)):
    for y in heights:
        grid.put(0, y, 0, "air")


class TreeTests(unittest.TestCase):
    def test_chopping_the_last_log_lets_the_canopy_decay_one_to_six_game_minutes_later(self):
        ctx, state = world(forest()), pet()
        chop(ctx.grid, (1, 2, 3))
        renew(state, ctx, 0.0)
        self.assertEqual(scheduled(ctx.db), [])  # the top log still holds the canopy
        chop(ctx.grid, (4,))
        renew(state, ctx, 10.0)
        leaves = scheduled(ctx.db)
        self.assertEqual(len(leaves), 26)
        self.assertTrue(all(block == "air" and 70.0 <= ready_at <= 370.0 for _, block, ready_at in leaves))
        renew(state, ctx, 370.0)
        self.assertEqual((ctx.grid.material(1, 5, 0), ctx.grid.material(0, 6, 0)), ("air", "air"))
        self.assertEqual((len(state["decays"]), scheduled(ctx.db)), (24, []))
        self.assertEqual(sorted(state["decays"][0]), ["at", "x", "y", "z"])

    def test_leaves_that_still_reach_a_log_stay(self):
        ctx = world(forest({(3, 5, 0): "oak_log"}))
        chop(ctx.grid)
        renew(pet(), ctx, 0.0)
        cells = [cell for cell, _, _ in scheduled(ctx.db)]
        self.assertNotIn((2, 5, 0), cells)
        self.assertIn((-2, 5, 0), cells)

    def test_a_decaying_leaf_drops_saplings_and_apples_to_mimo_nearby(self):
        near, far = pet(), pet(position={"x": 40.0, "y": 1.0, "z": 0.0})
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            for state in (near, far):
                ctx = world(forest())
                chop(ctx.grid)
                renew(state, ctx, 0.0)
                renew(state, ctx, 60.0)
        self.assertEqual(near["inventory"], {"sapling": 26, "apple": 26})
        self.assertEqual((far["inventory"], len(far["decays"])), ({}, 24))

    def test_a_sapling_grows_into_a_tree_after_a_game_day(self):
        ctx = world()
        ctx.grid.put(0, 1, 0, "sapling")
        renew(pet(), ctx, 0.0)
        self.assertEqual(scheduled(ctx.db), [((0, 1, 0), "oak_log", 3600.0)])
        renew(pet(), ctx, 3600.0)
        self.assertEqual([ctx.grid.material(0, y, 0) for y in range(1, 7)], ["oak_log"] * 4 + ["leaves", "leaves"])
        self.assertEqual(ctx.grid.material(2, 5, 1), "leaves")
        self.assertEqual(ctx.events[-1][1:], ("grow", "A sapling grew into a tree."))
        self.assertEqual(scheduled(ctx.db), [])

    def test_a_sapling_without_room_tries_again_later(self):
        ctx = world(field({(0, 3, 0): "stone"}))
        ctx.grid.put(0, 1, 0, "sapling")
        renew(pet(), ctx, 0.0)
        renew(pet(), ctx, 3600.0)
        self.assertEqual(ctx.grid.material(0, 1, 0), "sapling")
        self.assertEqual(scheduled(ctx.db), [((0, 1, 0), "oak_log", 4200.0)])
        standing = world()
        standing.grid.put(0, 1, 0, "sapling")
        renew(pet(position={"x": 0.0, "y": 2.0, "z": 0.0}), standing, 0.0)
        renew(pet(position={"x": 0.0, "y": 2.0, "z": 0.0}), standing, 3600.0)
        self.assertEqual(standing.grid.material(0, 1, 0), "sapling")


@patch("backend.survival.renewal.terrain_height", lambda x, z, seed: 0)
@patch("backend.survival.renewal.biome_at", lambda x, z, seed: "forest")
class MushroomTests(unittest.TestCase):
    def test_a_picked_mushroom_comes_back_on_forest_floor_one_per_chunk_per_game_day(self):
        ctx = world(field({(3, 1, 3): "brown_mushroom", (5, 1, 9): "red_mushroom"}))
        ctx.grid.put(3, 1, 3, "air")
        renew(pet(), ctx, 0.0)
        ctx.grid.put(5, 1, 9, "air")
        renew(pet(), ctx, 10.0)
        coming = scheduled(ctx.db)
        self.assertEqual([(block, ready_at) for _, block, ready_at in coming],
                         [("brown_mushroom", 3600.0), ("red_mushroom", 7200.0)])
        self.assertTrue(all(0 <= cell[0] < 16 and 0 <= cell[2] < 16 and cell[1] == 1 for cell, _, _ in coming))
        renew(pet(), ctx, 3600.0)
        self.assertEqual(ctx.grid.material(*coming[0][0]), "brown_mushroom")

    def test_a_chunk_holds_at_most_three_mushrooms(self):
        ctx = world(field({(1, 1, 1): "brown_mushroom", (2, 1, 2): "red_mushroom", (3, 1, 3): "brown_mushroom"}))
        schedule(ctx.db, (9, 1, 9), "brown_mushroom", 5.0)
        renew(pet(), ctx, 10.0)
        self.assertEqual(ctx.grid.material(9, 1, 9), "air")
```

In `backend/tests/test_survival_api.py`, replace:

```python
        self.assertEqual(state["care"], {"snack": 1, "bandage": 1})
```

with:

```python
        self.assertEqual(state["care"], {"snack": 1, "bandage": 1})
        self.assertEqual(state["decays"], [])
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_renewal.py"`
Expected: the 7 new tests fail (for example `AssertionError: 0 != 26` in the decay test, and `AttributeError: <module 'backend.survival.renewal' ...> does not have the attribute 'biome_at'` in the mushroom tests).

- [ ] **Step 6: Decay leaves, grow saplings and bring mushrooms back**

In `backend/survival/renewal.py`, replace:

```python
     from it), unless a crop grows on it by then.
```

with:

```python
     from it), unless a crop grows on it by then;
   - a planted sapling grows into a tree after 1 game day if there is room for the trunk and
     canopy (worldgen's tree shape), and tries again every 10 game minutes until there is;
   - a log that goes (chopped, or any other way) leaves the leaves that no longer reach a log
     within 4 steps (through leaves and logs) to decay 1 to 6 game minutes later. A decaying
     leaf may drop a sapling (1 in 12) or an apple (1 in 20), which Mimo gathers when it is
     within 16 blocks, and it is kept in state["decays"] so the viewer can show a puff;
   - a picked mushroom comes back on forest floor in its chunk after a game day, one per chunk
     per game day and at most 3 in the chunk.
```

and replace:

```python
import sqlite3

from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import Cell, Grid
```

with:

```python
import math
import sqlite3

from backend.services.blocks import is_replaceable
from backend.services.crafting import add_item
from backend.services.worldgen import biome_at, is_leaf, terrain_height
from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.senses import LOG, TRUNK_HEIGHT
```

and replace:

```python
MAX_APPLIED = 512  # entries one call applies at most; the rest wait for the next call
```

with:

```python
MAX_APPLIED = 512  # entries one call applies at most; the rest wait for the next call
LEAF_REACH = 4
DECAY_SECONDS = (60.0, 360.0)
DECAY_CHANNEL = 36
DROP_REACH = 16.0
DECAYS_KEPT = 24
SAPLING_GROWS = DAY_SECONDS
SAPLING_RETRY = 600.0
MUSHROOM_RESPAWN = DAY_SECONDS
MUSHROOM_CAP = 3
MUSHROOM_SPOT_CHANNEL = 37
FOREST_FLOOR = ("grass", "moss")
NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
```

and replace:

```python
def react(db: sqlite3.Connection, grid: Grid, state: dict, changes: list[tuple[Cell, str, str]], at: float,
```

with:

```python
def step_to(cell: Cell, offset: tuple[int, int, int]) -> Cell:
    return cell[0] + offset[0], cell[1] + offset[1], cell[2] + offset[2]


def leaf_supported(grid: Grid, leaf: Cell) -> bool:
    """A log within 4 steps of the leaf, counting through leaves and logs."""
    seen, frontier = {leaf}, [leaf]
    for _ in range(LEAF_REACH):
        ahead = []
        for cell in frontier:
            for offset in NEIGHBOURS:
                near = step_to(cell, offset)
                if near in seen:
                    continue
                seen.add(near)
                material = grid.material(*near)
                if material == LOG:
                    return True
                if material == "leaves":
                    ahead.append(near)
        frontier = ahead
    return False


def orphaned_leaves(grid: Grid, log: Cell) -> list[Cell]:
    """Leaves within 4 steps (through leaves) of a log that went, which no longer reach a log."""
    seen, frontier, found = {log}, [log], []
    for _ in range(LEAF_REACH):
        ahead = []
        for cell in frontier:
            for offset in NEIGHBOURS:
                near = step_to(cell, offset)
                if near not in seen and grid.material(*near) == "leaves":
                    ahead.append(near)
                    found.append(near)
                seen.add(near)
        frontier = ahead
    return [leaf for leaf in found if not leaf_supported(grid, leaf)]


def decay_seconds(seed: str, leaf: Cell, at: float) -> float:
    low, high = DECAY_SECONDS
    return low + (high - low) * nature.roll(seed, leaf, DECAY_CHANNEL, int(at))


def tree_cells(sapling: Cell) -> tuple[list[Cell], list[Cell]]:
    """The trunk (from the sapling's cell up) and canopy cells of a tree grown from `sapling`,
    in worldgen's shape: 4 logs, then leaves 5 and 6 above the ground."""
    x, y, z = sapling
    ground = y - 1
    trunk = [(x, y + dy, z) for dy in range(TRUNK_HEIGHT)]
    canopy = [(x + dx, ground + dy, z + dz) for dy in (5, 6) for dx in range(-2, 3) for dz in range(-2, 3)
              if is_leaf(dx, dy, dz)]
    return trunk, canopy


def open_cell(material: str) -> bool:
    """Air, or a plant that gives way (never water)."""
    return material != "water" and is_replaceable(material)


def tree_fits(grid: Grid, sapling: Cell) -> bool:
    trunk, canopy = tree_cells(sapling)
    return (all(open_cell(grid.material(*cell)) for cell in trunk[1:])
            and all(open_cell(grid.material(*cell)) or grid.material(*cell) == "leaves" for cell in canopy))


def grow_tree(grid: Grid, sapling: Cell) -> None:
    trunk, canopy = tree_cells(sapling)
    for cell in trunk:
        grid.put(*cell, LOG)
    for cell in canopy:
        if open_cell(grid.material(*cell)):
            grid.put(*cell, "leaves")


def forest_floor(grid: Grid, seed: str, chunk: tuple[int, int], at: float) -> Cell | None:
    """An open cell on forest grass or moss in the chunk, picked by the roll; None if 8 tries miss."""
    cx, cz = chunk
    for attempt in range(8):
        pick = nature.roll(seed, (cx, attempt, cz), MUSHROOM_SPOT_CHANNEL, int(at))
        x, z = cx * CHUNK + int(pick * CHUNK), cz * CHUNK + int(pick * CHUNK * CHUNK) % CHUNK
        if biome_at(x, z, seed) != "forest":
            continue
        y = terrain_height(x, z, seed) + 1
        if grid.material(x, y, z) == "air" and grid.material(x, y - 1, z) in FOREST_FLOOR:
            return x, y, z
    return None


def mushrooms_in_chunk(grid: Grid, seed: str, chunk: tuple[int, int]) -> int:
    """Mushrooms standing on the chunk's surface."""
    cx, cz = chunk
    return sum(1 for x in range(cx * CHUNK, cx * CHUNK + CHUNK) for z in range(cz * CHUNK, cz * CHUNK + CHUNK)
               if grid.material(x, terrain_height(x, z, seed) + 1, z) in nature.MUSHROOMS)


def respawn_mushroom(db: sqlite3.Connection, grid: Grid, seed: str, picked: Cell, kind: str, at: float,
                     scale: float) -> None:
    """Schedule a mushroom on forest floor in the picked one's chunk: a game day after the latest
    one already coming there, so a chunk regrows at most one per game day."""
    chunk = (picked[0] // CHUNK, picked[2] // CHUNK)
    spot = forest_floor(grid, seed, chunk, at)
    if spot is None:
        return
    x0, z0 = chunk[0] * CHUNK, chunk[1] * CHUNK
    latest = db.execute("SELECT MAX(ready_at) FROM growth WHERE block IN (?, ?) AND x BETWEEN ? AND ? "
                        "AND z BETWEEN ? AND ?", (*nature.MUSHROOMS, x0, x0 + CHUNK - 1, z0, z0 + CHUNK - 1)).fetchone()[0]
    ready_at = later(at, MUSHROOM_RESPAWN, scale)
    if latest is not None:
        ready_at = max(ready_at, later(latest, MUSHROOM_RESPAWN, scale))
    schedule(db, spot, kind, ready_at, keep_earlier=True)


def react(db: sqlite3.Connection, grid: Grid, state: dict, changes: list[tuple[Cell, str, str]], at: float,
```

and replace:

```python
    """Schedule what the changed blocks will turn into."""
    for cell, before, after in changes:
        x, y, z = cell
        grown = nature.next_stage(after)
        if after == "berry_bush":
```

with:

```python
    """Schedule what the changed blocks will turn into."""
    seed = state.get("world_seed", "0")
    for cell, before, after in changes:
        x, y, z = cell
        grown = nature.next_stage(after)
        if before == LOG and after != LOG:
            for leaf in orphaned_leaves(grid, cell):
                schedule(db, leaf, "air", later(at, decay_seconds(seed, leaf, at), scale), keep_earlier=True)
        if before in nature.MUSHROOMS and after == "air":
            respawn_mushroom(db, grid, seed, cell, before, at, scale)
        if after == "sapling":
            schedule(db, cell, LOG, later(at, SAPLING_GROWS, scale))
        elif after == "berry_bush":
```

and replace:

```python
    elif block == "dirt":
        if here == "farmland" and nature.crop_stage(grid.material(x, y + 1, z)) is None:
            grid.put(*cell, "dirt")
```

with:

```python
    elif block == "dirt":
        if here == "farmland" and nature.crop_stage(grid.material(x, y + 1, z)) is None:
            grid.put(*cell, "dirt")
    elif block == LOG:
        if here != "sapling":
            return
        if tree_fits(grid, cell) and pet_cell(state) not in tree_cells(cell)[0]:
            grow_tree(grid, cell)
            events.append((ready_at, "grow", "A sapling grew into a tree."))
        else:
            schedule(db, cell, LOG, later(ready_at, SAPLING_RETRY, scale))
    elif block == "air":
        if here == "leaves" and not leaf_supported(grid, cell):
            grid.put(*cell, "air")
            decay(state, cell, ready_at)
    elif block in nature.MUSHROOMS:
        seed = state.get("world_seed", "0")
        if (here == "air" and grid.material(x, y - 1, z) in FOREST_FLOOR
                and mushrooms_in_chunk(grid, seed, (x // CHUNK, z // CHUNK)) < MUSHROOM_CAP):
            grid.put(*cell, block)


def pet_cell(state: dict) -> Cell:
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def decay(state: dict, leaf: Cell, at: float) -> None:
    """A leaf decayed: Mimo gathers what it dropped if it is near, and the viewer gets a puff."""
    position = state["position"]
    if math.hypot(leaf[0] - position["x"], leaf[2] - position["z"]) <= DROP_REACH:
        for item in nature.chance_drops(state.get("world_seed", "0"), leaf, "leaves"):
            add_item(state["inventory"], item)
    puff = {"x": leaf[0], "y": leaf[1], "z": leaf[2], "at": round(at, 3)}
    state["decays"] = [*state.get("decays", []), puff][-DECAYS_KEPT:]
```

- [ ] **Step 7: Send the decays to the viewer**

In `backend/survival/snapshot.py`, replace:

```python
        **brain_view(state.get("brain")),
```

with:

```python
        # Leaves that decayed lately ({x, y, z, at}), so the viewer can show a puff as each goes.
        "decays": state.get("decays", []),
        **brain_view(state.get("brain")),
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_renewal.py"`
Expected: `Ran 17 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 408 tests` … `OK` (7 new), including `test_survival_sim.py`.

- [ ] **Step 9: Commit**

```bash
git add backend/survival/renewal.py backend/survival/snapshot.py backend/tests/test_survival_renewal.py backend/tests/test_survival_api.py
git commit -m "feat: decay orphaned leaves, grow saplings into trees and bring mushrooms back" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 8: Senses for food, grass, water, grown trees and failed places

**Files:**
- Modify: `backend/survival/senses.py`, `backend/survival/situation.py`
- Test: `backend/tests/test_survival_senses.py`

**Interfaces:**
- Consumes: Task 3's `worldgen.plant_at` (with wild food); `worldgen.SEA_LEVEL`, `terrain_height`; `steps.REACH`; `Grid.placed_cells`, `Grid.water`, `Grid.standable`.
- Produces:
  - `backend.survival.senses`: `FOOD_SIGHT = 24`, `WATER_SIGHT = 24`, `PICKABLE = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")`, `SIDES`, `FAILED_REACH = 4.0`; `near_failure(state, cell, radius=FAILED_REACH) -> bool` (a step failed lately within 4 blocks, horizontally); `plants_in_chunk(cx, cz, seed) -> tuple[tuple[Cell, str], ...]` (cached); `natural_plants(seed, x, z, radius, kinds) -> list[Cell]`; `by_distance(cells, here) -> list[Cell]`; `food_near(grid, seed, here, radius=FOOD_SIGHT, avoid=()) -> list[Cell]`; `grass_near(grid, seed, here, radius) -> list[Cell]`; `shores_near(grid, seed, here, radius=WATER_SIGHT) -> list[tuple[Cell, Cell]]` ((cell to stand on, water cell within reach)); `standing_logs` also finds trees grown from saplings (placed logs).
  - `backend.survival.situation`: `Situation.memo: dict` and `Situation.sensed(key, look) -> Any` (looks once per Situation).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_senses.py`:

```python
import math
import sqlite3
import unittest
from unittest.mock import patch

from backend.services.worldgen import block_at, plant_at, terrain_height
from backend.survival.grid import Grid
from backend.survival.senses import food_near, grass_near, near_failure, plants_in_chunk, shores_near, standing_logs
from backend.survival.situation import Situation

SEED = "123456789123456789"


def real():
    """The generated world of SEED."""
    return Grid(lambda x, y, z: block_at(x, y, z, SEED))


def meadow():
    return Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")


def first_plant(kind):
    """The first cell (scanning a strip of generated land) where worldgen grows `kind`."""
    for x in range(300, 900):
        for z in range(-40, 40):
            if plant_at(x, z, SEED) == kind:
                return x, terrain_height(x, z, SEED) + 1, z
    raise AssertionError(f"no {kind} found")


class PlantSenseTests(unittest.TestCase):
    def test_a_chunk_lists_its_wild_plants_once(self):
        bush = first_plant("berry_bush_ripe")
        plants = dict(plants_in_chunk(bush[0] // 16, bush[2] // 16, SEED))
        self.assertEqual(plants[bush], "berry_bush_ripe")
        self.assertTrue(all(kind == plant_at(cell[0], cell[2], SEED) for cell, kind in plants.items()))
        self.assertIs(plants_in_chunk(bush[0] // 16, bush[2] // 16, SEED),
                      plants_in_chunk(bush[0] // 16, bush[2] // 16, SEED))

    def test_ripe_food_is_listed_nearest_first_until_picked_and_again_when_it_grew_back(self):
        bush = first_plant("berry_bush_ripe")
        grid, here = real(), (bush[0] + 3, bush[1], bush[2])
        found = food_near(grid, SEED, here, 8)
        self.assertIn(bush, found)
        self.assertEqual(found, sorted(found, key=lambda cell: (math.dist(cell, here), cell)))
        grid.put(*bush, "berry_bush")
        self.assertNotIn(bush, food_near(grid, SEED, here, 8))
        grid.put(*bush, "berry_bush_ripe")
        self.assertIn(bush, food_near(grid, SEED, here, 8))

    def test_food_known_to_be_poisonous_is_left_out(self):
        grid = meadow()
        grid.put(2, 1, 0, "red_mushroom")
        grid.put(3, 1, 0, "brown_mushroom")
        self.assertEqual(food_near(grid, SEED, (0, 1, 0), 8), [(2, 1, 0), (3, 1, 0)])
        self.assertEqual(food_near(grid, SEED, (0, 1, 0), 8, avoid=("red_mushroom",)), [(3, 1, 0)])

    def test_tall_grass_counts_while_it_stands(self):
        grass = first_plant("tall_grass")
        grid = real()
        self.assertIn(grass, grass_near(grid, SEED, grass, 4))
        grid.put(*grass, "air")
        self.assertNotIn(grass, grass_near(grid, SEED, grass, 4))


@patch("backend.survival.senses.terrain_height", lambda x, z, seed: 0 if x >= 3 else 2)
class ShoreTests(unittest.TestCase):
    def test_a_shore_cell_comes_with_water_within_reach(self):
        lake = Grid(lambda x, y, z: ("water" if 1 <= y <= 2 else "stone" if y <= 0 else "air") if x >= 3
                    else ("stone" if y <= 2 else "air"))
        shores = shores_near(lake, SEED, (0, 3, 0), 6)
        self.assertEqual(shores[0], ((2, 3, 0), (3, 2, 0)))
        self.assertTrue(all(stand[0] == 2 and water[0] == 3 and water[1] == 2 for stand, water in shores))
        lake.put(3, 2, 0, "dirt")
        self.assertNotIn(((2, 3, 0), (3, 2, 0)), shores_near(lake, SEED, (0, 3, 0), 6))


class GrownTreeTests(unittest.TestCase):
    @patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [])
    def test_trees_grown_from_saplings_count_as_trees(self):
        grid = meadow()
        for y in (1, 2, 3, 4):
            grid.put(6, y, 0, "oak_log")
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0)), [(6, 1, 0), (6, 2, 0), (6, 3, 0), (6, 4, 0)])
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0), skip={(6, 0)}), [])


class FailureTests(unittest.TestCase):
    def test_cells_near_a_failed_step_are_left_alone_for_a_while(self):
        state = {"recent_actions": [{"kind": "walk", "result": "failed", "target": {"x": 10, "y": 1, "z": 0}},
                                    {"kind": "walk", "result": "done", "target": {"x": 30, "y": 1, "z": 0}}]}
        self.assertTrue(near_failure(state, (13, 5, 0)))
        self.assertFalse(near_failure(state, (15, 1, 0)))
        self.assertFalse(near_failure(state, (30, 1, 0)))
        self.assertFalse(near_failure({}, (10, 1, 0)))


class SensedTests(unittest.TestCase):
    def test_a_situation_looks_once_per_key(self):
        looks = []
        s = Situation({}, meadow(), {}, 0.0, sqlite3.connect(":memory:"))
        for _ in range(3):
            self.assertEqual(s.sensed("food", lambda: looks.append(1) or ["bush"]), ["bush"])
        self.assertEqual(len(looks), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_senses.py"`
Expected: `ImportError: cannot import name 'food_near' from 'backend.survival.senses'`.

- [ ] **Step 3: Sense wild plants, ripe food, grass, shores and grown trees**

In `backend/survival/senses.py`, replace:

```python
"""Looking around: what the world near Mimo offers.

Trees come from worldgen (cheap, no block reads). Whether their logs still stand, ores and open
cells are read through a Grid, so Mimo's own edits count.
"""

from __future__ import annotations

import math

from backend.services.worldgen import trees_in_chunk
from backend.survival.grid import CHUNK, Cell, Grid

TREE_SEARCH = 24
TRUNK_HEIGHT = 4
LOG = "oak_log"
ORES = ("coal_ore", "iron_ore", "copper_ore")
```

with:

```python
"""Looking around: what the world near Mimo offers.

Trees, wild plants and water come from worldgen (cheap, no block reads; the plants of a chunk
are worked out once and kept). Whether they are still there, ores and open cells are read
through a Grid, so Mimo's own edits count, and so do the trees and food that grew back.
"""

from __future__ import annotations

import math
from functools import lru_cache

from backend.services.worldgen import SEA_LEVEL, plant_at, terrain_height, trees_in_chunk
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.steps import REACH

TREE_SEARCH = 24
TRUNK_HEIGHT = 4
LOG = "oak_log"
ORES = ("coal_ore", "iron_ore", "copper_ore")
FOOD_SIGHT = 24
WATER_SIGHT = 24
# Wild food Mimo can pick (block names; a mushroom's item has the same name).
PICKABLE = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
FAILED_REACH = 4.0
```

In `backend/survival/senses.py`, replace the whole `standing_logs` function with:

```python
def standing_logs(grid: Grid, seed: str, here: Cell, skip: set[tuple[int, int]] | frozenset = frozenset(),
                  radius: int = TREE_SEARCH) -> list[Cell]:
    """The logs still standing in the nearest tree worth trying, lowest first; [] when there is none.
    Trees grown from saplings count too: their logs are placed blocks."""
    x, _, z = here
    trunks: dict[tuple[int, int], set[Cell]] = {}
    for tx, tz, base in trees_near(seed, x, z, radius):
        trunks.setdefault((tx, tz), set()).update((tx, y, tz) for y in range(base + 1, base + TRUNK_HEIGHT + 1))
    for cell, _ in grid.placed_cells(x, z, radius, (LOG,)):
        trunks.setdefault((cell[0], cell[2]), set()).add(cell)
    best: tuple[float, tuple[int, int], list[Cell]] | None = None
    for (tx, tz), cells in trunks.items():
        if (tx, tz) in skip:
            continue
        logs = sorted((cell for cell in cells if grid.material(*cell) == LOG), key=lambda cell: cell[1])
        distance = math.hypot(tx - x, tz - z)
        if logs and (best is None or (distance, (tx, tz)) < best[:2]):
            best = (distance, (tx, tz), logs)
    return best[2] if best else []
```

In `backend/survival/senses.py`, append:

```python


@lru_cache(maxsize=4096)
def plants_in_chunk(cx: int, cz: int, seed: str) -> tuple[tuple[Cell, str], ...]:
    """Every natural surface plant (flowers, tall grass, berry bushes, mushrooms) rooted in a chunk."""
    found = []
    for x in range(cx * CHUNK, cx * CHUNK + CHUNK):
        for z in range(cz * CHUNK, cz * CHUNK + CHUNK):
            plant = plant_at(x, z, seed)
            if plant:
                found.append(((x, terrain_height(x, z, seed) + 1, z), plant))
    return tuple(found)


def natural_plants(seed: str, x: int, z: int, radius: float, kinds: tuple[str, ...]) -> list[Cell]:
    """Cells where worldgen grew one of `kinds` within `radius` blocks of (x, z)."""
    found = []
    for cx in range(math.floor((x - radius) / CHUNK), math.floor((x + radius) / CHUNK) + 1):
        for cz in range(math.floor((z - radius) / CHUNK), math.floor((z + radius) / CHUNK) + 1):
            found.extend(cell for cell, plant in plants_in_chunk(cx, cz, seed)
                         if plant in kinds and math.hypot(cell[0] - x, cell[2] - z) <= radius)
    return found


def by_distance(cells, here: Cell) -> list[Cell]:
    return sorted(cells, key=lambda cell: (math.dist(cell, here), cell))


def food_near(grid: Grid, seed: str, here: Cell, radius: float = FOOD_SIGHT, avoid=()) -> list[Cell]:
    """Ripe food Mimo can pick within `radius`, nearest first: wild bushes and mushrooms and the ones
    that grew back, as they stand now. Food in `avoid` (known to be poisonous) is left out."""
    x, _, z = here
    wanted = tuple(block for block in PICKABLE if block not in avoid)
    cells = set(natural_plants(seed, x, z, radius, PICKABLE))
    cells.update(cell for cell, _ in grid.placed_cells(x, z, radius, PICKABLE))
    return by_distance((cell for cell in cells if grid.material(*cell) in wanted), here)


def grass_near(grid: Grid, seed: str, here: Cell, radius: float) -> list[Cell]:
    """Wild tall grass still standing within `radius`, nearest first (breaking it may give seeds)."""
    x, _, z = here
    return by_distance((cell for cell in natural_plants(seed, x, z, radius, ("tall_grass",))
                        if grid.material(*cell) == "tall_grass"), here)


def shores_near(grid: Grid, seed: str, here: Cell, radius: float = WATER_SIGHT) -> list[tuple[Cell, Cell]]:
    """(cell to stand on, water cell within reach of it) along natural water within `radius`, the
    nearest standing cell first. Natural water lies where the ground is below sea level."""
    x, _, z = here
    reach = math.ceil(radius)
    found: dict[Cell, Cell] = {}
    for wx in range(x - reach, x + reach + 1):
        for wz in range(z - reach, z + reach + 1):
            if math.hypot(wx - x, wz - z) > radius or terrain_height(wx, wz, seed) >= SEA_LEVEL:
                continue
            water = (wx, SEA_LEVEL, wz)
            if not grid.water(water):
                continue
            for dx, dz in SIDES:
                ground = terrain_height(wx + dx, wz + dz, seed)
                stand = (wx + dx, ground + 1, wz + dz)
                if (ground >= SEA_LEVEL and stand not in found and math.dist(stand, water) <= REACH
                        and grid.standable(stand)):
                    found[stand] = water
    return [(stand, found[stand]) for stand in by_distance(found, here)]


def near_failure(state: dict, cell: Cell, radius: float = FAILED_REACH) -> bool:
    """A step failed lately within `radius` blocks (horizontally) of `cell`: somewhere Mimo could
    not get to, so the cells around it are left alone for a while too."""
    return any(math.hypot(cell[0] - x, cell[2] - z) <= radius for x, z in failed_columns(state))
```

- [ ] **Step 4: Let a Situation remember what it sensed**

In `backend/survival/situation.py`, replace:

```python
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING
```

with:

```python
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable
```

and replace:

```python
    at: float
    db: sqlite3.Connection | None = None
```

with:

```python
    at: float
    db: sqlite3.Connection | None = None
    # What Mimo sensed, kept for this Situation: a purpose's check, facts, score and plan look once.
    memo: dict = field(default_factory=dict)

    def sensed(self, key: str, look: Callable[[], Any]) -> Any:
        """`look()` the first time `key` is asked for, then the same answer."""
        if key not in self.memo:
            self.memo[key] = look()
        return self.memo[key]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_senses.py"`
Expected: `Ran 8 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 416 tests` … `OK` (8 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/senses.py backend/survival/situation.py backend/tests/test_survival_senses.py
git commit -m "feat: sense ripe food, tall grass, shores, trees grown from saplings and failed places" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 9: Memory of food patches, fires, the farm and poison

**Files:**
- Create: `backend/survival/learning.py`
- Modify: `backend/survival/memory.py`, `backend/survival/situation.py`, `backend/survival/purposes.py`, `backend/survival/reflexes.py`, `backend/survival/brain.py`
- Test: `backend/tests/test_survival_memory.py`, `backend/tests/test_survival_purposes.py`, `backend/tests/test_survival_reflexes.py`, `backend/tests/test_survival_learning.py`

**Interfaces:**
- Consumes: Task 2's `steps.FOOD_HEALTH`, `crafting.FIRES`; Task 8's `senses.food_near`; `memory.remember`, `forget`, `nearest`, `cell_of`; `brain.observe_step`; `purposes.foods`, `purposes.meal`; the eat_now reflex.
- Produces:
  - `backend.survival.memory`: `PLACE_COLUMNS` ends with `"data"`; `SAME_PLACE` adds `food` (8) and `farm` (16); `create_memory_tables` adds the `data` column when missing and a `memory_knowledge` table (subject, fact, learned_at); `places(db, kinds=None, around=None, reach=None) -> list[dict]` (each with `data` as a dict); `place_of(row) -> dict`; `update_place(db, kind, cell, data) -> bool`; `know(db, subject, fact, at) -> bool`; `known(db, fact) -> list[str]`.
  - `backend.survival.situation`: `PLACE_SIGHT = 256`; `Situation.places` reads places within 256 blocks; `Situation.poisons -> tuple[str, ...]`.
  - `backend.survival.purposes`: `foods(inventory, avoid=())`, `meal(inventory, hunger, full=FULL, avoid=())`; eat uses `s.poisons`.
  - The eat_now reflex skips known poisons.
  - `backend.survival.learning`: `PATCH_REACH = 8.0`; `note_food_patch(db, grid, state, picked, at)`; `learn_from_step(state, step, context, at)`: eating a food with negative `FOOD_HEALTH` → `know(item, "poisonous")`; `pick` → the food patch with `{"ripe", "seen_at"}`; placing a campfire or furnace → a `fire` place (note = the block); mining one → forgets it; `till` → a `farm` place.
  - `brain.observe_step` ends with `learn_from_step(state, step, context, at)`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_memory.py`, replace:

```python
    create_memory_tables, forget, known_recipes, learn, nearest, places, remember, visit,
```

with:

```python
    create_memory_tables, forget, know, known, known_recipes, learn, nearest, places, remember, update_place, visit,
```

In `backend/tests/test_survival_memory.py`, add these tests at the end of `MemoryTests`:

```python
    def test_a_place_keeps_data_that_updates_merge_into(self):
        db = memory_db()
        remember(db, "food", (5, 3, 5), 1.0)
        self.assertTrue(update_place(db, "food", (5, 3, 5), {"ripe": 3, "seen_at": 1.0}))
        self.assertTrue(update_place(db, "food", (5, 3, 5), {"ripe": 1}))
        self.assertFalse(update_place(db, "food", (9, 3, 9), {"ripe": 1}))
        self.assertEqual(places(db)[0]["data"], {"ripe": 1, "seen_at": 1.0})
        self.assertFalse(remember(db, "food", (10, 3, 5), 2.0))
        self.assertTrue(remember(db, "fire", (6, 3, 5), 2.0, "campfire"))
        self.assertEqual(places(db, ("fire",))[0]["data"], {})

    def test_places_are_read_in_a_box_around_a_cell(self):
        db = memory_db()
        remember(db, "ore", (0, 0, 0), 1.0, "coal_ore")
        remember(db, "ore", (300, 0, 0), 2.0, "coal_ore")
        remember(db, "home", (10, 5, -20), 3.0)
        self.assertEqual([place["x"] for place in places(db, around=(0, 0, 0), reach=32)], [0, 10])
        self.assertEqual([place["x"] for place in places(db, ("ore",), around=(290, 0, 0), reach=32)], [300])

    def test_facts_are_learned_once(self):
        db = memory_db()
        self.assertTrue(know(db, "red_mushroom", "poisonous", 1.0))
        self.assertFalse(know(db, "red_mushroom", "poisonous", 2.0))
        self.assertEqual((known(db, "poisonous"), known(db, "tasty")), (["red_mushroom"], []))
```

In `backend/tests/test_survival_memory.py`, add this test at the end of `WorldMemoryTests`:

```python
    def test_memory_from_m3_gets_place_data_and_facts_and_keeps_its_places(self):
        with self.world.connect() as db:
            db.execute("DROP TABLE memory_places")
            db.execute("CREATE TABLE memory_places (kind TEXT NOT NULL, x INTEGER NOT NULL, y INTEGER NOT NULL, "
                       "z INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', found_at REAL NOT NULL, visited_at REAL, "
                       "PRIMARY KEY (kind, x, y, z))")
            db.execute("INSERT INTO memory_places(kind, x, y, z, found_at) VALUES ('home', 1, 5, 1, 9.0)")
            db.execute("DROP TABLE memory_knowledge")
        world_module._schema_ready.discard(self.path.resolve())
        with SurvivalWorld(self.path).connect() as db:
            self.assertEqual([(place["kind"], place["data"]) for place in places(db)], [("home", {})])
            self.assertEqual(known(db, "poisonous"), [])
            create_memory_tables(db)
            self.assertEqual(len(places(db)), 1)
```

In `backend/tests/test_survival_purposes.py`, replace:

```python
from backend.survival.memory import create_memory_tables, remember
```

with:

```python
from backend.survival.memory import create_memory_tables, know, remember
```

In `backend/tests/test_survival_purposes.py`, add this test at the end of `SimplePurposeTests`:

```python
    def test_food_known_to_be_poisonous_is_never_eaten(self):
        hungry = pet(inventory={"red_mushroom": 2, "berries": 1}, vitals={**START_VITALS, "hunger": 20.0})
        s = situation(hungry)
        self.assertEqual(PURPOSES["eat"].plan(s, context()),
                         [{"kind": "eat", "item": "berries"}, {"kind": "eat", "item": "red_mushroom"},
                          {"kind": "eat", "item": "red_mushroom"}])
        know(s.db, "red_mushroom", "poisonous", 0.0)
        s = Situation(hungry, s.grid, DAY, 0.0, s.db)
        self.assertEqual(PURPOSES["eat"].plan(s, context()), [{"kind": "eat", "item": "berries"}])
        only_red = situation(pet(inventory={"red_mushroom": 1}, vitals={**START_VITALS, "hunger": 20.0}))
        know(only_red.db, "red_mushroom", "poisonous", 0.0)
        self.assertNotIn("eat", names(only_red))
        self.assertEqual(meal({"red_mushroom": 3}, 10.0, avoid=("red_mushroom",)), [])
```

In `backend/tests/test_survival_reflexes.py`, replace:

```python
from backend.survival.memory import create_memory_tables, places, remember
```

with:

```python
from backend.survival.memory import create_memory_tables, know, places, remember
```

In `backend/tests/test_survival_reflexes.py`, add this test at the end of `ReflexTests`:

```python
    def test_eat_now_never_eats_food_known_to_be_poisonous(self):
        state = pet(inventory={"red_mushroom": 2, "apple": 1}, vitals={**START_VITALS, "hunger": 10.0})
        ctx = brainy()
        know(ctx.db, "red_mushroom", "poisonous", 0.0)
        self.assertEqual(reflex_hook(state, ctx, 0.0), "eat_now")
        self.assertEqual(state["queue"], [{"kind": "eat", "item": "apple", "purpose": "eat_now"}])
        sick = pet(inventory={"red_mushroom": 2}, vitals={**START_VITALS, "hunger": 10.0})
        self.assertIsNone(reflex_hook(sick, ctx, 0.0))
```

Create `backend/tests/test_survival_learning.py`:

```python
import sqlite3
import unittest

from backend.survival.actions import ActionContext
from backend.survival.brain import observe_step
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, known, places
from backend.survival.triggers import ensure_brain

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def pet():
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "recent_actions": [], "last_tick_at": 0.0}
    ensure_brain(state)["pending"] = None
    return state


def remembering(grid=None):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    grid = grid or Grid(lambda x, y, z: "grass" if y == 0 else "air")
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=db)


def at(x, y, z):
    return {"x": x, "y": y, "z": z}


class LearningTests(unittest.TestCase):
    def test_being_sick_teaches_that_a_food_is_poisonous(self):
        ctx = remembering()
        observe_step(pet(), {"kind": "eat", "item": "berries"}, ctx, 1.0)
        observe_step(pet(), {"kind": "eat", "item": "red_mushroom"}, ctx, 2.0)
        self.assertEqual(known(ctx.db, "poisonous"), ["red_mushroom"])

    def test_picking_remembers_the_patch_with_its_ripe_food_and_when(self):
        ctx = remembering()
        for cell in ((3, 1, 0), (4, 1, 0), (5, 1, 1)):
            ctx.grid.put(*cell, "berry_bush_ripe")
        ctx.grid.put(3, 1, 0, "berry_bush")
        observe_step(pet(), {"kind": "pick", "target": at(3, 1, 0), "block": "berry_bush_ripe"}, ctx, 5.0)
        ctx.grid.put(4, 1, 0, "berry_bush")
        observe_step(pet(), {"kind": "pick", "target": at(4, 1, 0), "block": "berry_bush_ripe"}, ctx, 6.0)
        patches = [(place["x"], place["data"]) for place in places(ctx.db, ("food",))]
        self.assertEqual(patches, [(3, {"ripe": 1, "seen_at": 6.0})])

    def test_fires_are_remembered_while_they_stand_and_farms_where_mimo_tilled(self):
        ctx = remembering()
        observe_step(pet(), {"kind": "place", "target": at(1, 1, 0), "block": "campfire"}, ctx, 1.0)
        observe_step(pet(), {"kind": "place", "target": at(2, 1, 0), "block": "crafting_table"}, ctx, 1.0)
        observe_step(pet(), {"kind": "till", "target": at(0, 0, 3), "block": "grass"}, ctx, 2.0)
        self.assertEqual([(place["kind"], place["x"], place["note"]) for place in places(ctx.db)],
                         [("fire", 1, "campfire"), ("farm", 0, "")])
        observe_step(pet(), {"kind": "mine", "target": at(1, 1, 0), "block": "campfire"}, ctx, 3.0)
        self.assertEqual([place["kind"] for place in places(ctx.db)], ["farm"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_memory.py"`
Expected: `ImportError: cannot import name 'know' from 'backend.survival.memory'`.

- [ ] **Step 3: Give places data, read them in a box and keep learned facts**

In `backend/survival/memory.py`, replace:

```python
"""What a life remembers, kept in its own world database: places and known recipes.

Places are cells worth coming back to, each with the time it was found and last visited:
- home: the first sheltered spot Mimo found (until M5 builds a real one); only ever one
- shelter: other sheltered spots (one per 8 blocks, counting home)
- ore: an ore block Mimo saw, with its material as the note (exact cells)
- danger: a drop or lava Mimo refused to step into, the note says which (one per 2 blocks)
- water: a body of water Mimo swam in (one per 16 blocks)
M4 and M5 add their own kinds (beds, chests, fires, food patches) the same way. Recipes are the
ones Mimo crafted or smelted successfully. A new life's world starts with empty tables: that
is what "fresh start" wipes.
"""
```

with:

```python
"""What a life remembers, kept in its own world database: places, known recipes and facts.

Places are cells worth coming back to, each with the time it was found and last visited:
- home: the first sheltered spot Mimo found (until M5 builds a real one); only ever one
- shelter: other sheltered spots (one per 8 blocks, counting home)
- ore: an ore block Mimo saw, with its material as the note (exact cells)
- danger: a drop or lava Mimo refused to step into, the note says which (one per 2 blocks)
- water: a body of water Mimo swam in (one per 16 blocks)
- food: a patch of wild food Mimo picked from (one per 8 blocks), with data {"ripe": ripe plants
  it still had, "seen_at": when}
- fire: a campfire or furnace Mimo placed and left, the note says which (exact cells)
- farm: where Mimo tilled its first plot (one per 16 blocks)
M5 adds its own kinds (beds, chests) the same way. A place's `data` is a JSON object that
`update_place` merges into. Places are read in a bounded box around a cell, since memory keeps
growing. Recipes are the ones Mimo crafted or smelted successfully; facts are things it learned,
like that red mushrooms are poisonous. A new life's world starts with empty tables: that is what
"fresh start" wipes.
"""
```

and replace:

```python
import math
import sqlite3
```

with:

```python
import json
import math
import sqlite3
```

and replace:

```python
    "water": (16.0, ("water",)),
}
PLACE_COLUMNS = ("kind", "x", "y", "z", "note", "found_at", "visited_at")
```

with:

```python
    "water": (16.0, ("water",)),
    "food": (8.0, ("food",)),
    "farm": (16.0, ("farm",)),
}
PLACE_COLUMNS = ("kind", "x", "y", "z", "note", "found_at", "visited_at", "data")
```

and replace:

```python
def create_memory_tables(db: sqlite3.Connection) -> None:
    """Create the memory tables. Run it inside the caller's BEGIN IMMEDIATE."""
    db.execute("CREATE TABLE IF NOT EXISTS memory_places (kind TEXT NOT NULL, x INTEGER NOT NULL, "
               "y INTEGER NOT NULL, z INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', found_at REAL NOT NULL, "
               "visited_at REAL, PRIMARY KEY (kind, x, y, z))")
    db.execute("CREATE TABLE IF NOT EXISTS memory_recipes (recipe TEXT PRIMARY KEY, learned_at REAL NOT NULL, "
               "uses INTEGER NOT NULL DEFAULT 1)")
```

with:

```python
def create_memory_tables(db: sqlite3.Connection) -> None:
    """Create the memory tables, or bring older ones up to date. Run it inside the caller's
    BEGIN IMMEDIATE; running it again changes nothing."""
    db.execute("CREATE TABLE IF NOT EXISTS memory_places (kind TEXT NOT NULL, x INTEGER NOT NULL, "
               "y INTEGER NOT NULL, z INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', found_at REAL NOT NULL, "
               "visited_at REAL, data TEXT NOT NULL DEFAULT '{}', PRIMARY KEY (kind, x, y, z))")
    if "data" not in {row[1] for row in db.execute("PRAGMA table_info(memory_places)")}:
        # Worlds from M3 remember their places without data.
        db.execute("ALTER TABLE memory_places ADD COLUMN data TEXT NOT NULL DEFAULT '{}'")
    db.execute("CREATE INDEX IF NOT EXISTS memory_places_by_column ON memory_places(x, z)")
    db.execute("CREATE TABLE IF NOT EXISTS memory_recipes (recipe TEXT PRIMARY KEY, learned_at REAL NOT NULL, "
               "uses INTEGER NOT NULL DEFAULT 1)")
    db.execute("CREATE TABLE IF NOT EXISTS memory_knowledge (subject TEXT NOT NULL, fact TEXT NOT NULL, "
               "learned_at REAL NOT NULL, PRIMARY KEY (subject, fact))")
```

and replace:

```python
def places(db: sqlite3.Connection, kinds: tuple[str, ...] | None = None) -> list[dict]:
    """Remembered places, oldest first, as dicts with kind, x, y, z, note, found_at and visited_at."""
    query = f"SELECT {','.join(PLACE_COLUMNS)} FROM memory_places"
    params: tuple = ()
    if kinds:
        query += f" WHERE kind IN ({','.join('?' * len(kinds))})"
        params = tuple(kinds)
    rows = db.execute(query + " ORDER BY found_at, rowid", params).fetchall()
    return [dict(zip(PLACE_COLUMNS, tuple(row))) for row in rows]
```

with:

```python
def places(db: sqlite3.Connection, kinds: tuple[str, ...] | None = None, around: Cell | None = None,
           reach: float | None = None) -> list[dict]:
    """Remembered places, oldest first, as dicts with kind, x, y, z, note, found_at, visited_at and
    data. With `around` and `reach`, only the places in the square column of that reach around it."""
    clauses, params = [], []
    if kinds:
        clauses.append(f"kind IN ({','.join('?' * len(kinds))})")
        params.extend(kinds)
    if around is not None and reach is not None:
        box = math.ceil(reach)
        clauses.append("x BETWEEN ? AND ? AND z BETWEEN ? AND ?")
        params.extend((around[0] - box, around[0] + box, around[2] - box, around[2] + box))
    query = f"SELECT {','.join(PLACE_COLUMNS)} FROM memory_places"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    rows = db.execute(query + " ORDER BY found_at, rowid", params).fetchall()
    return [place_of(row) for row in rows]


def place_of(row) -> dict:
    place = dict(zip(PLACE_COLUMNS, tuple(row)))
    place["data"] = json.loads(place["data"] or "{}")
    return place


def update_place(db: sqlite3.Connection, kind: str, cell: Cell, data: dict) -> bool:
    """Merge `data` into what Mimo remembers about a place. False when it does not remember it."""
    row = db.execute("SELECT data FROM memory_places WHERE kind=? AND x=? AND y=? AND z=?", (kind, *cell)).fetchone()
    if row is None:
        return False
    merged = {**json.loads(row[0] or "{}"), **data}
    db.execute("UPDATE memory_places SET data=? WHERE kind=? AND x=? AND y=? AND z=?", (json.dumps(merged), kind, *cell))
    return True
```

and replace:

```python
def cell_of(place: dict) -> Cell:
```

with:

```python
def know(db: sqlite3.Connection, subject: str, fact: str, at: float) -> bool:
    """Learn that `subject` is `fact` (red_mushroom is "poisonous"). True the first time."""
    cursor = db.execute("INSERT OR IGNORE INTO memory_knowledge(subject, fact, learned_at) VALUES (?, ?, ?)",
                        (subject, fact, at))
    return cursor.rowcount == 1


def known(db: sqlite3.Connection, fact: str) -> list[str]:
    """Every subject Mimo learned is `fact`, first learned first."""
    return [row[0] for row in db.execute("SELECT subject FROM memory_knowledge WHERE fact=? "
                                         "ORDER BY learned_at, subject", (fact,)).fetchall()]


def cell_of(place: dict) -> Cell:
```

- [ ] **Step 4: Read places near Mimo and what it learned is poisonous**

In `backend/survival/situation.py`, replace:

```python
NIGHTFALL = 2400.0
```

with:

```python
NIGHTFALL = 2400.0
PLACE_SIGHT = 256  # remembered places this far away (on each axis) are read; farther ones are not
```

and replace:

```python
    @cached_property
    def places(self) -> list[dict]:
        return memory.places(self.db) if self.db is not None else []
```

with:

```python
    @cached_property
    def places(self) -> list[dict]:
        return memory.places(self.db, around=self.here, reach=PLACE_SIGHT) if self.db is not None else []

    @cached_property
    def poisons(self) -> tuple[str, ...]:
        """Food Mimo learned is poisonous (it got sick eating it)."""
        return tuple(memory.known(self.db, "poisonous")) if self.db is not None else ()
```

- [ ] **Step 5: Never eat known poison**

In `backend/survival/purposes.py`, replace:

```python
def foods(inventory: dict) -> list[str]:
    """Food Mimo carries, best first."""
    return sorted((item for item in FOOD if inventory.get(item, 0) > 0), key=lambda item: -FOOD[item])


def meal(inventory: dict, hunger: float, full: float = FULL) -> list[dict]:
    """Eat steps, best food first, until hunger would reach `full` or the food runs out."""
    steps, left = [], dict(inventory)
    for item in foods(inventory):
```

with:

```python
def foods(inventory: dict, avoid=()) -> list[str]:
    """Food Mimo carries, best first, leaving out what it knows is poisonous (`avoid`)."""
    return sorted((item for item in FOOD if inventory.get(item, 0) > 0 and item not in avoid),
                  key=lambda item: -FOOD[item])


def meal(inventory: dict, hunger: float, full: float = FULL, avoid=()) -> list[dict]:
    """Eat steps, best food first, until hunger would reach `full` or the food runs out. Food in
    `avoid` (known to be poisonous) is never eaten."""
    steps, left = [], dict(inventory)
    for item in foods(inventory, avoid):
```

and replace:

```python
    return meal(s.inventory, s.vitals["hunger"])
```

with:

```python
    return meal(s.inventory, s.vitals["hunger"], avoid=s.poisons)
```

and replace:

```python
    valid=lambda s: bool(foods(s.inventory)) and s.vitals["hunger"] < EAT_BELOW,
```

with:

```python
    valid=lambda s: bool(foods(s.inventory, s.poisons)) and s.vitals["hunger"] < EAT_BELOW,
```

In `backend/survival/reflexes.py`, replace:

```python
                trigger=lambda s: s.vitals["hunger"] < EAT_NOW_BELOW and bool(foods(s.inventory)),
                plan=lambda s, context: meal(s.inventory, s.vitals["hunger"], EAT_NOW_FULL),
```

with:

```python
                trigger=lambda s: s.vitals["hunger"] < EAT_NOW_BELOW and bool(foods(s.inventory, s.poisons)),
                plan=lambda s, context: meal(s.inventory, s.vitals["hunger"], EAT_NOW_FULL, s.poisons),
```

- [ ] **Step 6: Learn from finished steps**

Create `backend/survival/learning.py`:

```python
"""What Mimo learns from the M4 steps it finished, kept in its memory (backend.survival.memory).

- Eating food that made it sick teaches it the food is poisonous; foods() and meal() leave it out
  from then on, so neither the eat purpose nor the eat-now reflex eats it again.
- Picking wild food remembers the patch (one per 8 blocks) with how many ripe plants it still
  had and when (data {"ripe", "seen_at"}), so forage can come back once it grew again.
- Placing a campfire or furnace remembers a fire (a warm spot and a place to cook); mining it
  back forgets it.
- Tilling remembers the farm, where the farm purpose keeps its plots.
backend.survival.brain's observe_step calls `learn_from_step` for every step that finished well.
"""

from __future__ import annotations

from backend.services.crafting import FIRES
from backend.survival.memory import cell_of, forget, know, known, nearest, places, remember, update_place
from backend.survival.senses import food_near
from backend.survival.steps import FOOD_HEALTH, as_cell

PATCH_REACH = 8.0


def note_food_patch(db, grid, state: dict, picked, at: float) -> None:
    """Remember the patch around a picked plant and how much ripe food it still has."""
    patch = nearest(places(db, ("food",), around=picked, reach=PATCH_REACH), picked, ("food",), PATCH_REACH)
    spot = picked if patch is None else cell_of(patch)
    if patch is None:
        remember(db, "food", spot, at)
    ripe = food_near(grid, state["world_seed"], spot, PATCH_REACH, known(db, "poisonous"))
    update_place(db, "food", spot, {"ripe": len(ripe), "seen_at": at})


def learn_from_step(state: dict, step: dict, context, at: float) -> None:
    db = context.db
    if db is None:
        return
    kind = step["kind"]
    if kind == "eat" and FOOD_HEALTH.get(step["item"], 0.0) < 0:
        know(db, step["item"], "poisonous", at)
    elif kind == "pick":
        note_food_patch(db, context.grid, state, as_cell(step["target"]), at)
    elif kind == "place" and step["block"] in FIRES:
        remember(db, "fire", as_cell(step["target"]), at, step["block"])
    elif kind == "mine" and step["block"] in FIRES:
        forget(db, "fire", as_cell(step["target"]))
    elif kind == "till":
        remember(db, "farm", as_cell(step["target"]), at)
```

In `backend/survival/brain.py`, replace:

```python
in, places visited. `notice_step` runs after each vitals step: vital crossings (urgent), dawn and
```

with:

```python
in, places visited, and M4's lessons (backend.survival.learning: poisonous food, food patches,
fires and farms). `notice_step` runs after each vitals step: vital crossings (urgent), dawn and
```

and replace:

```python
from backend.survival.escape import plan_escape
```

with:

```python
from backend.survival.escape import plan_escape
from backend.survival.learning import learn_from_step
```

and replace:

```python
            discover(state, context, at, "water", "discovered", f"{name} found water.")
        visit(db, as_cell(state["position"]), at)
```

with:

```python
            discover(state, context, at, "water", "discovered", f"{name} found water.")
        visit(db, as_cell(state["position"]), at)
    learn_from_step(state, step, context, at)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_learning.py"`
Expected: `Ran 3 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 425 tests` … `OK` (9 new).

- [ ] **Step 8: Commit**

```bash
git add backend/survival/learning.py backend/survival/memory.py backend/survival/situation.py backend/survival/purposes.py backend/survival/reflexes.py backend/survival/brain.py backend/tests/test_survival_memory.py backend/tests/test_survival_purposes.py backend/tests/test_survival_reflexes.py backend/tests/test_survival_learning.py
git commit -m "feat: remember food patches, fires, the farm and poison, and never eat known poison" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 10: Forage and fish

**Files:**
- Create: `backend/survival/foraging.py`
- Modify: `backend/survival/steps.py`, `backend/survival/brain.py`
- Test: `backend/tests/test_survival_foraging.py`, `backend/tests/test_survival_steps.py`, `backend/tests/test_survival_sim.py` (the purpose-change budget)

**Interfaces:**
- Consumes: Task 5's `nature.fish_stock` and the `pick` and `fish` steps; Task 8's `senses.food_near`, `shores_near`, `FOOD_SIGHT`, `WATER_SIGHT`, `Situation.sensed`; Task 9's `foods(inventory, avoid)`, `Situation.poisons`, place `data`; Task 8's `senses.near_failure`; `purposes.Purpose`, `register`, `walk_to`, `late_penalty` (M3 fix wave); `steps.FOOD`, `steps.REACH`.
- Produces:
  - `backend.survival.foraging`: `FOOD_WANTED = 60.0`, `PICKS_PER_BATCH = 4`, `FORAGE_BATCHES = 6`, `STAND = 2.0`, `PATCH_RANGE = 64.0`, `REGROWN = 7200.0`, `FISH_GOAL = 4`, `CATCHES_PER_BATCH = 3`, `FISH_BATCHES = 4`; `food_points(s) -> float`; `food_need(s) -> float`; `hunger_score(s, base) -> float`; `whole_walk(cell, reach=0.0) -> dict` (a walk spec with `"whole": True`); `reach_steps(s, jobs: list[tuple[Cell, list[dict]]]) -> list[dict]` (walks close, with whole walks, only when a job's cell may be out of reach); `ripe_food(s)`, `patches(s)`, `fishing_spots(s)`. Registered purposes `forage` and `fish`.
  - `backend.survival.steps.start_walk`: a walk spec with `"whole": True` fails with `no_path` unless the route reaches its target (no partial walks). Only for targets within `pathing.MAX_RANGE` (96 blocks), which every M4 walk is.
  - `brain.py` imports `foraging`.
  - `test_survival_sim.PURPOSE_EVENTS_PER_HOUR` goes from 30 to 36: a first day now has food work in it (see Step 5).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_foraging.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import foraging  # noqa: F401  (registers forage and fish)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, know, remember, update_place
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
SHORE = ((2, 1, 0), (3, 0, 0))


def meadow(food=None):
    """Grass at y 0 and air above, with `food` placed as blocks that grew there (edits). Near the
    origin worldgen grows no wild food, so only these cells hold any."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (food or {}).items():
        grid.put(*cell, block)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state=None, grid=None, clock=DAY, at=0.0):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state or pet(), grid or meadow(), clock, at, db)


def context(s):
    return ActionContext(grid=s.grid, clock_at=lambda at: s.clock, planner=lambda *args: [], events=[], db=s.db)


def pick(x, y, z):
    return {"kind": "pick", "target": [x, y, z]}


def walk(x, y, z, reach=0.0):
    return {"kind": "walk", "target": [x, y, z], "reach": reach, "whole": True}


class ForageTests(unittest.TestCase):
    def test_picks_ripe_food_nearest_first_walking_only_when_out_of_reach(self):
        grid = meadow({(3, 1, 0): "berry_bush_ripe", (4, 1, 0): "berry_bush_ripe", (10, 1, 0): "brown_mushroom",
                       (0, 1, 2): "berry_bush"})
        s = situation(grid=grid)
        forage = PURPOSES["forage"]
        self.assertTrue(forage.valid(s))
        self.assertEqual(forage.plan(s, context(s)), [pick(3, 1, 0), pick(4, 1, 0), walk(10, 1, 0, 2.0), pick(10, 1, 0)])

    def test_enough_food_carried_night_or_nothing_ripe_means_no_foraging(self):
        grid = meadow({(3, 1, 0): "berry_bush_ripe"})
        forage = PURPOSES["forage"]
        self.assertFalse(forage.valid(situation(pet(inventory={"bread": 2, "berries": 2}), grid)))
        self.assertFalse(forage.valid(situation(grid=grid, clock=NIGHT)))
        self.assertFalse(forage.valid(situation(grid=meadow({(3, 1, 0): "berry_bush"}))))

    def test_red_mushrooms_are_left_once_mimo_knows(self):
        s = situation(grid=meadow({(2, 1, 0): "red_mushroom"}))
        self.assertEqual(PURPOSES["forage"].plan(s, context(s)), [pick(2, 1, 0)])
        wiser = situation(grid=meadow({(2, 1, 0): "red_mushroom"}))
        know(wiser.db, "red_mushroom", "poisonous", 0.0)
        self.assertFalse(PURPOSES["forage"].valid(wiser))

    def test_goes_back_to_a_patch_that_has_grown_again(self):
        s = situation(at=10_000.0)
        remember(s.db, "food", (60, 1, 0), 0.0)
        update_place(s.db, "food", (60, 1, 0), {"ripe": 0, "seen_at": 10_000.0 - 7200.0})
        self.assertEqual(PURPOSES["forage"].plan(s, context(s)), [walk(60, 1, 0, 3.0)])
        recent = situation(at=10_000.0)
        remember(recent.db, "food", (60, 1, 0), 0.0)
        update_place(recent.db, "food", (60, 1, 0), {"ripe": 0, "seen_at": 9_000.0})
        self.assertFalse(PURPOSES["forage"].valid(recent))

    def test_the_hungrier_and_emptier_handed_the_higher_it_scores(self):
        score = PURPOSES["forage"].score
        full = score(situation())
        hungry = score(situation(pet(vitals={**START_VITALS, "hunger": 40.0})))
        stocked = score(situation(pet(vitals={**START_VITALS, "hunger": 40.0}, inventory={"bread": 3})))
        self.assertEqual(round(full), 55)
        self.assertEqual(round(hungry), 75)
        self.assertEqual(round(stocked), 55)
        late = situation(clock={**DAY, "seconds_into_day": 2000.0})
        self.assertEqual(round(score(late)), 25)


@patch("backend.survival.foraging.shores_near", lambda grid, seed, here, radius: [SHORE])
class FishTests(unittest.TestCase):
    def test_walks_to_the_shore_and_fishes_three_times_a_batch(self):
        s = situation()
        fish = PURPOSES["fish"]
        self.assertTrue(fish.valid(s))
        self.assertEqual(fish.plan(s, context(s)), [walk(2, 1, 0)] + [{"kind": "fish", "target": [3, 0, 0]}] * 3)
        there = situation(pet(position={"x": 2.0, "y": 1.0, "z": 0.0}, inventory={"raw_fish": 2}))
        self.assertEqual(fish.plan(there, context(there)), [{"kind": "fish", "target": [3, 0, 0]}] * 2)

    def test_no_fishing_in_empty_water_at_night_or_with_enough_fish(self):
        fish = PURPOSES["fish"]
        self.assertFalse(fish.valid(situation(pet(fish={"0,0": {"stock": 0, "since": 0.0}}))))
        self.assertFalse(fish.valid(situation(clock=NIGHT)))
        self.assertFalse(fish.valid(situation(pet(inventory={"raw_fish": 1, "cooked_fish": 3}))))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_steps.py`, replace:

```python
    def test_sleep_has_no_fixed_end_waits_do_and_unknown_steps_fail(self):
```

with:

```python
    def test_a_whole_walk_goes_all_the_way_or_not_at_all(self):
        walls = {(x, y, z): "stone" for x in (4, 5, 6) for y in (1, 2) for z in (-1, 0, 1) if (x, z) != (5, 0)}
        part = start_step({"kind": "walk", "target": [5, 1, 0]}, pet(), small_world(walls), 0.0)
        self.assertFalse(part["reached"])
        self.assertTrue(part["path"])
        with self.assertRaises(StepFailed) as caught:
            start_step({"kind": "walk", "target": [5, 1, 0], "whole": True}, pet(), small_world(walls), 0.0)
        self.assertEqual(caught.exception.code, "no_path")

    def test_sleep_has_no_fixed_end_waits_do_and_unknown_steps_fail(self):
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_foraging.py"`
Expected: `ImportError: cannot import name 'foraging' from 'backend.survival'`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_steps.py"`
Expected: `FAIL: test_a_whole_walk_goes_all_the_way_or_not_at_all` (`StepFailed not raised`).

- [ ] **Step 3: Let a walk go all the way or not at all**

A walk toward a target it cannot reach walks as far as the route gets (M2). For food work that is a trap: the partial route to a bush on a ridge can end at the bottom of a pit or deep in a cave, and Mimo then tries the next bush from there. A walk marked `whole` fails at once instead, and the purpose's planner leaves that place alone (`senses.near_failure`).

In `backend/survival/steps.py`, replace:

```python
    cells, reached = route(grid, here, target, reach)
    if not cells and not reached:
        raise StepFailed("no way there", "no_path")
```

with:

```python
    cells, reached = route(grid, here, target, reach)
    # A walk marked `whole` goes all the way or not at all: part of the way can end in a pit.
    if not reached and (not cells or spec.get("whole")):
        raise StepFailed("no way there", "no_path")
```

- [ ] **Step 4: Write the forage and fish purposes**

Create `backend/survival/foraging.py`:

```python
"""Food from the wild: forage and fish.

forage picks ripe berry bushes and mushrooms within 24 blocks, nearest first, up to 4 plants a
batch, until Mimo carries a game day's worth of food (60 hunger) or nothing ripe is left near.
With nothing ripe in sight it walks to a remembered food patch within 64 blocks that still had
ripe food, or was seen picked clean at least 2 game days ago (it has grown back since). Red
mushrooms are picked too, until Mimo learns they are poisonous.

fish walks to the nearest shore within 24 blocks whose water still has fish (the 16x16 region's
stock) and fishes there, 3 catches a batch, until Mimo carries 4 fish, raw or cooked.

Both are day work, not offered at night, and both score in the needs band (purposes.py): the
hungrier Mimo is and the less food it carries, the higher. Their walks go all the way or not at
all (`whole`), and places within 4 blocks of where a step just failed are left alone for a while
(senses.near_failure).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import Cell
from backend.survival.memory import cell_of
from backend.survival.purposes import Purpose, foods, late_penalty, register, walk_to
from backend.survival.senses import FOOD_SIGHT, WATER_SIGHT, food_near, near_failure, shores_near
from backend.survival.situation import Situation
from backend.survival.steps import FOOD, REACH

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FOOD_WANTED = 60.0  # hunger points of food Mimo likes to carry: about a game day's worth
PICKS_PER_BATCH = 4
FORAGE_BATCHES = 6
STAND = 2.0  # a walk to pick or tend something ends within this many blocks of it
PATCH_RANGE = 64.0
PATCH_REACH = 3.0
REGROWN = 2 * DAY_SECONDS
FISH_GOAL = 4
CATCHES_PER_BATCH = 3
FISH_BATCHES = 4


def food_points(s: Situation) -> float:
    """Hunger the food Mimo carries would restore, leaving out food it knows is poisonous."""
    return sum(FOOD[item] * s.inventory[item] for item in foods(s.inventory, s.poisons))


def food_need(s: Situation) -> float:
    return max(0.0, FOOD_WANTED - food_points(s))


def hunger_score(s: Situation, base: float) -> float:
    """The needs-band score of food work: `base`, plus the food Mimo lacks and how hungry it is."""
    return base + food_need(s) / 3 + (100.0 - s.vitals["hunger"]) / 3 - late_penalty(s)


def whole_walk(cell: Cell, reach: float = 0.0) -> dict:
    """A walk that goes all the way or fails at once (steps.start_walk): a route that only gets
    part of the way to food or water can drop Mimo into a pit it cannot climb out of. Only for
    targets within pathing.MAX_RANGE (96 blocks); food work never walks farther than 64."""
    return {**walk_to(cell, reach), "whole": True}


def reach_steps(s: Situation, jobs: list[tuple[Cell, list[dict]]]) -> list[dict]:
    """The steps of each (cell, steps) job in turn, walking close to the cell first only when it may
    be out of reach from where Mimo will be (a walk ends within STAND blocks of its target)."""
    steps, where, slack = [], s.here, 0.0
    for cell, work in jobs:
        if math.dist(where, cell) + slack > REACH:
            steps.append(whole_walk(cell, STAND))
            where, slack = cell, STAND
        steps.extend(work)
    return steps


# forage ----------------------------------------------------------------------------------------

def ripe_food(s: Situation) -> list[Cell]:
    """Ripe food within sight, nearest first, leaving out poison and places near a failed step."""
    def look() -> list[Cell]:
        return [cell for cell in food_near(s.grid, s.seed, s.here, FOOD_SIGHT, s.poisons)
                if not near_failure(s.state, cell)]
    return s.sensed("ripe_food", look)


def patch_worth_a_visit(s: Situation, place: dict) -> bool:
    data = place["data"]
    if data.get("ripe", 0) > 0:
        return True
    seen = data.get("seen_at")
    return seen is None or (s.at - seen) * s.scale >= REGROWN


def patches(s: Situation) -> list[dict]:
    """Remembered food patches beyond sight but within 64 blocks that are worth a visit, nearest first."""
    found = [place for place in s.places if place["kind"] == "food"
             and FOOD_SIGHT < s.distance(cell_of(place)) <= PATCH_RANGE and patch_worth_a_visit(s, place)]
    return sorted(found, key=lambda place: s.distance(cell_of(place)))


def forage_valid(s: Situation) -> bool:
    return not s.night and food_need(s) > 0 and bool(ripe_food(s) or patches(s))


def forage_facts(s: Situation) -> str:
    return (f"{len(ripe_food(s))} ripe plants within {FOOD_SIGHT} blocks, {len(patches(s))} food patches to "
            f"revisit, carrying {round(food_points(s))} hunger of food")


def plan_forage(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or food_need(s) <= 0 or s.brain["batches"] >= FORAGE_BATCHES:
        return []
    ripe = ripe_food(s)
    if ripe:
        return reach_steps(s, [(cell, [{"kind": "pick", "target": list(cell)}]) for cell in ripe[:PICKS_PER_BATCH]])
    far = patches(s)
    return [whole_walk(cell_of(far[0]), PATCH_REACH)] if far else []


register(Purpose(
    "forage", "forage", "Pick ripe berries and mushrooms nearby, or go back to a food patch that grew again.",
    valid=forage_valid, facts=forage_facts, score=lambda s: hunger_score(s, 35.0), plan=plan_forage,
    thoughts=("Those berries look ripe.", "I'll gather something to eat.")))


# fish ------------------------------------------------------------------------------------------

def fish_carried(s: Situation) -> int:
    return s.count("raw_fish", "cooked_fish")


def fishing_spots(s: Situation) -> list[tuple[Cell, Cell]]:
    """(shore cell, water cell) within sight whose water still has fish, nearest shore first."""
    def look() -> list[tuple[Cell, Cell]]:
        return [(stand, water) for stand, water in shores_near(s.grid, s.seed, s.here, WATER_SIGHT)
                if nature.fish_stock(s.state, water) > 0 and not near_failure(s.state, stand)]
    return s.sensed("fishing_spots", look)


def fish_valid(s: Situation) -> bool:
    return not s.night and fish_carried(s) < FISH_GOAL and bool(fishing_spots(s))


def fish_facts(s: Situation) -> str:
    stand, water = fishing_spots(s)[0]
    return (f"water {round(s.distance(stand))} blocks away with {nature.fish_stock(s.state, water)} fish left, "
            f"carrying {fish_carried(s)} fish")


def plan_fish(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or fish_carried(s) >= FISH_GOAL or s.brain["batches"] >= FISH_BATCHES:
        return []
    spots = fishing_spots(s)
    if not spots:
        return []
    stand, water = spots[0]
    catches = min(CATCHES_PER_BATCH, FISH_GOAL - fish_carried(s))
    walk = [] if s.here == stand else [whole_walk(stand)]
    return walk + [{"kind": "fish", "target": list(water)} for _ in range(catches)]


register(Purpose(
    "fish", "fish", "Fish from the shore of nearby water; cooked fish is the most filling food.",
    valid=fish_valid, facts=fish_facts, score=lambda s: hunger_score(s, 25.0) + s.trait("patience") / 10,
    plan=plan_fish, thoughts=("Maybe the fish are biting.", "Fish would make a good meal.")))
```

- [ ] **Step 5: Let the brain offer them, with room in the purpose budget**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import toolmaking, work  # noqa: F401  (they register their purposes)
```

with:

```python
from backend.survival import foraging, toolmaking, work  # noqa: F401  (they register their purposes)
```

In `backend/tests/test_survival_sim.py`, replace:

```python
PURPOSE_EVENTS_PER_HOUR = 30  # the first hour is busy: wood, tools, stone, ores, better tools
```

with:

```python
# The first hour is busy: wood, tools, stone, ores, better tools, and from M4 food work too
# (forage, fish, farm, cook, eat), each a change of purpose and a change back.
PURPOSE_EVENTS_PER_HOUR = 36
```

The M3 fix wave set 30 for an M3 day of 17 to 23 changes (seeds 3, 11, 5 and 21, both pickers, `MIMO_SLOW_TESTS=1`). With forage, fish, farm and cook offered (Tasks 10 to 12) the same runs make 19 to 30 changes at the default settings and up to 33 in the slow runs (measured with all of M4 in), most of them a food purpose and the return to what Mimo was doing. 36 keeps the check meaningful: a brain that thrashes between purposes makes far more.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_foraging.py"`
Expected: `Ran 7 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_steps.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 433 tests` … `OK` (8 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/foraging.py backend/survival/steps.py backend/survival/brain.py backend/tests/test_survival_foraging.py backend/tests/test_survival_steps.py backend/tests/test_survival_sim.py
git commit -m "feat: forage ripe berries and mushrooms and fish from the shore, walking all the way or not at all" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 11: Farm

**Files:**
- Create: `backend/survival/farming.py`
- Modify: `backend/survival/brain.py`, `backend/survival/work.py`
- Test: `backend/tests/test_survival_farming.py`, `backend/tests/test_survival_work.py`

**Interfaces:**
- Consumes: Task 5's `nature.CROP_BLOCKS`, `RIPE_CROPS`, `HARVESTS`, `TILLABLE`, `crop_stage` and the `till`, `plant`, `harvest` and `mine` steps; Task 8's `senses.by_distance`, `grass_near`, `shores_near`, `near_failure`; Task 9's `farm` places; Task 10's `foraging.reach_steps`, `whole_walk`; `memory.nearest`, `cell_of`; `purposes.late_penalty`.
- Produces:
  - `backend.survival.farming`: `FARM_SIZE = 9`, `PLOTS_PER_BATCH = 4`, `GRASS_PER_BATCH = 6`, `FARM_BATCHES = 6`, `FARM_RANGE = 24.0`, `FARM_TRAVEL = 64.0`, `SITE_SEARCH = 16.0`, `GRASS_SEARCH = 16.0`, `PLANTABLE = ("carrot", "seeds")`, `PLOT_OFFSETS`; `farm_anchor(s) -> Cell`; `new_plots(s, anchor) -> list[Cell]`; `farm_jobs(s) -> list[tuple[Cell, list[dict]]]`; `far_farm(s) -> dict | None` (the remembered farm when more than 24 blocks away); `work_waiting(s, farm) -> bool`; `farm_trip(s) -> bool` (walk back only with work waiting). Registered purpose `farm`.
  - `backend.survival.work`: `TENDED = ("farmland", "sapling")`; `stair` never digs up farmland or a sapling (nor the ground under one).
  - `brain.py` imports `farming`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_farming.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import farming  # noqa: F401  (registers farm)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, remember
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}


def meadow(edits=None):
    """Grass at y 0 and air above, with `edits` placed the way Mimo placed them."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (edits or {}).items():
        grid.put(*cell, block)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state=None, grid=None, clock=DAY):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state or pet(), grid or meadow(), clock, 0.0, db)


def plan(s):
    return PURPOSES["farm"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: s.clock, planner=lambda *args: [],
                                                  events=[], db=s.db))


def till(x, y, z):
    return {"kind": "till", "target": [x, y, z]}


def sow(x, y, z, item):
    return {"kind": "plant", "target": [x, y, z], "item": item}


def harvest(x, y, z):
    return {"kind": "harvest", "target": [x, y, z]}


class FarmTests(unittest.TestCase):
    @patch("backend.survival.farming.shores_near", lambda grid, seed, here, radius: [((2, 1, 0), (3, 0, 0))])
    def test_a_new_farm_starts_beside_the_nearest_shore(self):
        s = situation(pet(inventory={"seeds": 2}))
        self.assertTrue(PURPOSES["farm"].valid(s))
        self.assertEqual(plan(s), [till(2, 0, 0), sow(2, 1, 0, "seeds"), till(1, 0, 0), sow(1, 1, 0, "seeds")])

    def test_ripe_crops_are_harvested_and_planted_again_then_new_plots_take_the_rest(self):
        grid = meadow({(1, 0, 0): "farmland", (2, 0, 0): "farmland", (3, 0, 0): "farmland",
                       (1, 1, 0): "wheat_3", (2, 1, 0): "carrot_3", (3, 1, 0): "carrot_1"})
        self.assertEqual(plan(situation(grid=grid)), [
            harvest(1, 1, 0), sow(1, 1, 0, "seeds"), harvest(2, 1, 0), sow(2, 1, 0, "carrot"),
            till(0, 0, 0), sow(0, 1, 0, "carrot"), till(-1, 0, 0), sow(-1, 1, 0, "carrot")])

    def test_empty_farmland_gets_carrots_first_then_seeds(self):
        grid = meadow({(1, 0, 0): "farmland", (2, 0, 0): "farmland"})
        steps = plan(situation(pet(inventory={"carrot": 1, "seeds": 1}), grid))
        self.assertEqual(steps, [sow(1, 1, 0, "carrot"), sow(2, 1, 0, "seeds")])

    @patch("backend.survival.farming.grass_near", lambda grid, seed, here, radius: [(5, 1, 0), (6, 1, 0)])
    def test_with_nothing_to_plant_mimo_breaks_tall_grass_for_seeds(self):
        self.assertEqual(plan(situation()), [{"kind": "walk", "target": [5, 1, 0], "reach": 2.0, "whole": True},
                                             {"kind": "mine", "target": [5, 1, 0]}, {"kind": "mine", "target": [6, 1, 0]}])

    def test_a_plot_where_a_step_just_failed_is_left_alone(self):
        state = pet()
        state["recent_actions"] = [{"kind": "walk", "started_at": 0.0, "ended_at": 0.0, "result": "failed",
                                    "target": {"x": 1, "y": 1, "z": 0}, "reason": "no way there", "code": "no_path"}]
        grid = meadow({(1, 0, 0): "farmland", (1, 1, 0): "carrot_3", (6, 0, 0): "farmland", (6, 1, 0): "carrot_3"})
        self.assertEqual(plan(situation(state, grid))[:3], [
            {"kind": "walk", "target": [6, 1, 0], "reach": 2.0, "whole": True}, harvest(6, 1, 0), sow(6, 1, 0, "carrot")])

    def test_a_farm_far_away_is_walked_to_first(self):
        s = situation(pet(inventory={"seeds": 3}))
        remember(s.db, "farm", (50, 0, 0), 0.0)
        self.assertEqual(plan(s), [{"kind": "walk", "target": [50, 1, 0], "reach": 2.0, "whole": True}])

    @patch("backend.survival.farming.grass_near", lambda grid, seed, here, radius: [(5, 1, 0)])
    def test_a_far_farm_with_nothing_waiting_is_not_worth_the_trip(self):
        idle = situation()
        remember(idle.db, "farm", (50, 0, 0), 0.0)
        self.assertFalse(PURPOSES["farm"].valid(idle))
        ripe = situation(grid=meadow({(50, 0, 0): "farmland", (50, 1, 0): "wheat_3"}))
        remember(ripe.db, "farm", (50, 0, 0), 0.0)
        self.assertEqual(plan(ripe), [{"kind": "walk", "target": [50, 1, 0], "reach": 2.0, "whole": True}])

    @patch("backend.survival.farming.grass_near", lambda grid, seed, here, radius: [])
    def test_nothing_to_do_or_night_means_no_farming(self):
        self.assertFalse(PURPOSES["farm"].valid(situation()))
        self.assertFalse(PURPOSES["farm"].valid(situation(pet(inventory={"seeds": 3}), clock=NIGHT)))

    def test_ripe_crops_and_seeds_raise_the_score(self):
        score = PURPOSES["farm"].score
        bare = score(situation())
        seeded = score(situation(pet(inventory={"seeds": 1})))
        ripe = score(situation(pet(inventory={"seeds": 1}), meadow({(1, 0, 0): "farmland", (1, 1, 0): "wheat_3"})))
        self.assertEqual((bare, seeded, ripe), (47.5, 57.5, 82.5))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_work.py`, replace:

```python
    def test_with_a_stone_pickaxe_it_digs_on_for_iron_until_it_sees_some(self):
```

with:

```python
    def test_a_stair_never_digs_up_farmland_or_a_sapling(self):
        inventory = {"wooden_pickaxe": 1}
        self.assertIsNone(stair(ground({(1, 0, 0): "farmland"}), {}, (0, 1, 0), (1, 0), inventory, "1"))
        self.assertIsNone(stair(ground({(1, 1, 0): "sapling"}), {}, (0, 1, 0), (1, 0), inventory, "1"))

    def test_with_a_stone_pickaxe_it_digs_on_for_iron_until_it_sees_some(self):
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_farming.py"`
Expected: `ImportError: cannot import name 'farming' from 'backend.survival'`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py"`
Expected: `FAIL: test_a_stair_never_digs_up_farmland_or_a_sapling` (`AssertionError: ([{'kind': 'mine', 'target': [1, 0, 0]}, ...) is not None`).

- [ ] **Step 3: Write the farm purpose**

Create `backend/survival/farming.py`:

```python
"""Farming: till plots near water, plant seeds and carrots, harvest ripe crops and plant again.

The farm is where Mimo tilled first (a remembered `farm` place). With no farm yet, the first
plot goes beside the nearest shore within 16 blocks, where crops grow three times as fast, or
else under Mimo's feet. A farm more than 24 blocks away is walked to first, but only when there
is work waiting there (ripe crops, or something to plant and a plot for it); far from its farm
Mimo does no farm work. Each batch does the most useful work it can, at most 4 plots:
1. harvest ripe crops within 24 blocks and plant each plot again with what it gave;
2. plant empty farmland, carrots first (they feed Mimo) and then seeds;
3. till new plots next to the farm, up to 9, for the carrots and seeds left over;
4. with nothing to plant, break tall grass within 16 blocks for seeds (1 in 5 gives some, and 1
   in 20 a carrot).
The purpose ends when none of these is left, or after 6 batches. It is day work. Plots, grass
and a farm within 4 blocks of where a step just failed are left alone for a while
(senses.near_failure).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.blocks import is_replaceable
from backend.survival.foraging import reach_steps, whole_walk
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, nearest
from backend.survival.nature import CROP_BLOCKS, HARVESTS, RIPE_CROPS, TILLABLE, crop_stage
from backend.survival.purposes import Purpose, late_penalty, register
from backend.survival.senses import by_distance, grass_near, near_failure, shores_near
from backend.survival.situation import Situation

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FARM_SIZE = 9
PLOTS_PER_BATCH = 4
GRASS_PER_BATCH = 6
FARM_BATCHES = 6
FARM_RANGE = 24.0
FARM_TRAVEL = 64.0
SITE_SEARCH = 16.0
GRASS_SEARCH = 16.0
STAND = 2.0
PLANTABLE = ("carrot", "seeds")  # what to plant, in order of preference
SEED_OF = {"wheat": "seeds", "carrot": "carrot"}
# Plot offsets around the farm, nearest first, in a 5x5 square.
PLOT_OFFSETS = sorted(((dx, dz) for dx in range(-2, 3) for dz in range(-2, 3)),
                      key=lambda offset: (abs(offset[0]) + abs(offset[1]), offset))


def above(cell: Cell) -> Cell:
    return cell[0], cell[1] + 1, cell[2]


def open_above(s: Situation, ground: Cell) -> bool:
    material = s.grid.material(*above(ground))
    return material != "water" and is_replaceable(material)


def farm_place(s: Situation) -> dict | None:
    return nearest(s.places, s.here, ("farm",), FARM_TRAVEL)


def farm_anchor(s: Situation) -> Cell:
    """The ground cell new plots go around: the remembered farm, else beside the nearest shore
    within 16 blocks, else under Mimo."""
    farm = farm_place(s)
    if farm is not None:
        return cell_of(farm)
    shores = s.sensed("farm_shores", lambda: shores_near(s.grid, s.seed, s.here, SITE_SEARCH))
    x, y, z = shores[0][0] if shores else s.here
    return x, y - 1, z


def reachable(s: Situation, cells) -> list[Cell]:
    """The cells with no failed step lately within 4 blocks."""
    return [cell for cell in cells if not near_failure(s.state, cell)]


def new_plots(s: Situation, anchor: Cell) -> list[Cell]:
    """Ground cells next to the farm that can be tilled, nearest the anchor first."""
    ax, ay, az = anchor
    found = []
    for dx, dz in PLOT_OFFSETS:
        if near_failure(s.state, (ax + dx, ay, az + dz)):
            continue
        for y in (ay, ay + 1, ay - 1):
            ground = (ax + dx, y, az + dz)
            if s.grid.material(*ground) in TILLABLE and open_above(s, ground):
                found.append(ground)
                break
    return found


def next_seed(inventory: dict) -> str | None:
    return next((item for item in PLANTABLE if inventory.get(item, 0) > 0), None)


def plant(cell: Cell, item: str) -> dict:
    return {"kind": "plant", "target": list(cell), "item": item}


def farm_jobs(s: Situation) -> list[tuple[Cell, list[dict]]]:
    """This batch's farm work as (cell, steps) jobs, before any walking."""
    x, _, z = s.here
    inventory = dict(s.inventory)
    placed = s.grid.placed_cells(x, z, FARM_RANGE, CROP_BLOCKS + ("farmland",))
    ripe = reachable(s, by_distance((cell for cell, material in placed if material in RIPE_CROPS), s.here))
    farmland = [cell for cell, material in placed if material == "farmland"]
    empty = reachable(s, by_distance((above(cell) for cell in farmland if open_above(s, cell)), s.here))
    jobs: list[tuple[Cell, list[dict]]] = []
    for cell in ripe[:PLOTS_PER_BATCH]:
        crop = s.grid.material(*cell)
        for item, amount in HARVESTS[crop].items():
            inventory[item] = inventory.get(item, 0) + amount
        seed = SEED_OF[crop_stage(crop)[0]]
        inventory[seed] -= 1
        jobs.append((cell, [{"kind": "harvest", "target": list(cell)}, plant(cell, seed)]))
    for cell in empty:
        seed = next_seed(inventory)
        if seed is None or len(jobs) >= PLOTS_PER_BATCH:
            break
        inventory[seed] -= 1
        jobs.append((cell, [plant(cell, seed)]))
    if len(jobs) < PLOTS_PER_BATCH and len(farmland) < FARM_SIZE:
        room = min(PLOTS_PER_BATCH - len(jobs), FARM_SIZE - len(farmland))
        for ground in new_plots(s, farm_anchor(s))[:room]:
            seed = next_seed(inventory)
            if seed is None:
                break
            inventory[seed] -= 1
            jobs.append((above(ground), [{"kind": "till", "target": list(ground)}, plant(above(ground), seed)]))
    if not jobs and next_seed(inventory) is None and (empty or len(farmland) < FARM_SIZE):
        grass = reachable(s, grass_near(s.grid, s.seed, s.here, GRASS_SEARCH))
        jobs = [(cell, [{"kind": "mine", "target": list(cell)}]) for cell in grass[:GRASS_PER_BATCH]]
    return jobs


def farm_work(s: Situation) -> list[tuple[Cell, list[dict]]]:
    return s.sensed("farm_jobs", lambda: farm_jobs(s))


def far_farm(s: Situation) -> dict | None:
    """The remembered farm when it lies beyond reach of the plots Mimo tends."""
    farm = farm_place(s)
    return farm if farm is not None and s.distance(cell_of(farm)) > FARM_RANGE else None


def work_waiting(s: Situation, farm: dict) -> bool:
    """Ripe crops at the farm, or something to plant and a plot for it there."""
    fx, _, fz = cell_of(farm)
    placed = s.grid.placed_cells(fx, fz, FARM_RANGE, CROP_BLOCKS + ("farmland",))
    if any(material in RIPE_CROPS for _, material in placed):
        return True
    farmland = [cell for cell, material in placed if material == "farmland"]
    return next_seed(s.inventory) is not None and (len(farmland) < FARM_SIZE
                                                   or any(open_above(s, cell) for cell in farmland))


def farm_trip(s: Situation) -> bool:
    """Walk back to a far farm: only with work waiting there, and not where a walk just failed."""
    farm = far_farm(s)
    return farm is not None and bool(reachable(s, [cell_of(farm)])) and work_waiting(s, farm)


def farm_valid(s: Situation) -> bool:
    if s.night:
        return False
    return farm_trip(s) if far_farm(s) is not None else bool(farm_work(s))


def farm_facts(s: Situation) -> str:
    x, _, z = s.here
    placed = s.grid.placed_cells(x, z, FARM_RANGE, CROP_BLOCKS + ("farmland",))
    ripe = sum(1 for _, material in placed if material in RIPE_CROPS)
    plots = sum(1 for _, material in placed if material == "farmland")
    return (f"{plots} plots and {ripe} ripe crops near, carrying {s.count('seeds')} seeds and "
            f"{s.count('carrot')} carrots")


def farm_score(s: Situation) -> float:
    x, _, z = s.here
    ripe = bool(s.grid.placed_cells(x, z, FARM_RANGE, RIPE_CROPS))
    score = 40.0 + s.trait("diligence") / 10 + s.trait("patience") / 20
    score += (25.0 if ripe else 0.0) + (10.0 if next_seed(s.inventory) else 0.0)
    return score - late_penalty(s)


def plan_farm(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= FARM_BATCHES:
        return []
    if far_farm(s) is not None:
        return [whole_walk(above(cell_of(far_farm(s))), STAND)] if farm_trip(s) else []
    return reach_steps(s, farm_work(s))


register(Purpose(
    "farm", "farm", "Till plots near water, plant seeds and carrots, and harvest ripe crops.",
    valid=farm_valid, facts=farm_facts, score=farm_score, plan=plan_farm,
    thoughts=("A little farm would keep me fed.", "Time to tend the crops.")))
```

- [ ] **Step 4: Let the brain offer it**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import foraging, toolmaking, work  # noqa: F401  (they register their purposes)
```

with:

```python
from backend.survival import farming, foraging, toolmaking, work  # noqa: F401  (they register their purposes)
```

- [ ] **Step 5: Keep gather_stone's stairs off the farm**

gather_stone digs down from wherever Mimo stands, and after farming that is often the farm: without this, the first stair mines the plot Mimo just planted.

In `backend/survival/work.py`, replace:

```python
water, lava, bedrock, a hole or a cave, or a block it cannot mine. It never digs back the way it
came, and never mines the floor of an open cell below the natural surface (a stair or tunnel it
dug earlier, or a cave) unless the same stair just opened that cell, so it cannot cut its own
staircase. The staircase stays climbable, and from its third stair it is sheltered, so it often
becomes Mimo's first home.
```

with:

```python
water, lava, bedrock, a hole or a cave, or a block it cannot mine, and never digs up farmland or
a sapling. It never digs back the way it came, and never mines the floor of an open cell below
the natural surface (a stair or tunnel it dug earlier, or a cave) unless the same stair just
opened that cell, so it cannot cut its own staircase. The staircase stays climbable, and from
its third stair it is sheltered, so it often becomes Mimo's first home.
```

and replace:

```python
FLUIDS = ("water", "lava")
```

with:

```python
FLUIDS = ("water", "lava")
TENDED = ("farmland", "sapling")  # Mimo's own plots and plantings
```

and replace:

```python
        if material in FLUIDS:
            return None
```

with:

```python
        if material in FLUIDS:
            return None
        if material in TENDED or look(grid, changed, (nx, cell[1] + 1, nz)) in TENDED:
            return None  # never dig up Mimo's farm or a sapling it planted
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_farming.py"`
Expected: `Ran 9 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 443 tests` … `OK` (10 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/farming.py backend/survival/brain.py backend/survival/work.py backend/tests/test_survival_farming.py backend/tests/test_survival_work.py
git commit -m "feat: till plots by water, plant and harvest crops, and gather seeds from tall grass" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 12: Cook, and warm up by a campfire

**Files:**
- Create: `backend/survival/cooking.py`
- Modify: `backend/survival/reflexes.py`, `backend/survival/brain.py`
- Test: `backend/tests/test_survival_cooking.py`, `backend/tests/test_survival_reflexes.py`

**Interfaces:**
- Consumes: Task 2's `crafting.FIRES` and the campfire and bread recipes; Task 5's `cook` step; Task 10's `foraging.whole_walk`; `toolmaking.make`, `Short`, `station_spots`, `place_station` (M3 fix wave: a dug niche below the surface); `steps.STATION_REACH`, `WORKSTATIONS`; `vitals.WARM_BLOCKS`; `purposes.Purpose`, `register`, `walk_to`.
- Produces:
  - `backend.survival.cooking`: `FIRE_TRAVEL = 32.0`, `FIRE_STAND = 2.0`, `BREAD_WHEAT = 3`; `made(inventory, item) -> list[dict] | None`; `station(inventory, name, spots, steps, placed, carried) -> bool`; `cook_plan(s) -> list[dict] | None`; `cook_score(s) -> float`. Registered purpose `cook`; the fire or table it placed is mined back with `{"keep": True}` steps.
  - `reflexes.plan_warm_up` lights a carried campfire first (then a furnace) and walks to shelters, campfires and furnaces within 64 blocks.
  - `brain.py` imports `cooking`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_cooking.py`:

```python
import sqlite3
import unittest

from backend.survival import cooking  # noqa: F401  (registers cook)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
COOK = {"kind": "cook", "item": "raw_fish"}


def meadow(edits=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (edits or {}).items():
        grid.put(*cell, block)
    return grid


def situation(inventory, grid=None, hunger=100.0):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": {**START_VITALS, "hunger": hunger}, "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state, grid or meadow(), DAY, 0.0, db)


def plan(s):
    return PURPOSES["cook"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                                  events=[], db=s.db))


def craft(recipe):
    return {"kind": "craft", "recipe": recipe}


def place(block):
    return {"kind": "place", "target": [1, 1, 0], "block": block}


PICK_UP = {"kind": "mine", "target": [1, 1, 0], "keep": True}


class CookTests(unittest.TestCase):
    def test_fish_cooks_at_a_fire_that_is_already_near(self):
        s = situation({"raw_fish": 2}, meadow({(3, 1, 0): "campfire"}))
        self.assertTrue(PURPOSES["cook"].valid(s))
        self.assertEqual(plan(s), [COOK, COOK])

    def test_a_carried_campfire_is_lit_for_cooking_and_picked_up_after(self):
        self.assertEqual(plan(situation({"raw_fish": 2, "campfire": 1})), [place("campfire"), COOK, COOK, PICK_UP])

    def test_with_no_fire_mimo_makes_a_campfire_from_logs(self):
        self.assertEqual(plan(situation({"raw_fish": 1, "oak_log": 3})),
                         [craft("planks"), craft("sticks"), craft("campfire"), place("campfire"), COOK, PICK_UP])

    def test_or_walks_to_a_fire_it_can_reach(self):
        s = situation({"raw_fish": 1}, meadow({(20, 1, 0): "furnace"}))
        self.assertEqual(plan(s), [{"kind": "walk", "target": [20, 1, 0], "reach": 2.0, "whole": True}])
        self.assertFalse(PURPOSES["cook"].valid(situation({"raw_fish": 1})))

    def test_wheat_bakes_into_bread_at_a_table(self):
        self.assertEqual(plan(situation({"wheat": 7, "planks": 4})),
                         [craft("crafting_table"), place("crafting_table"), craft("bread"), craft("bread"), PICK_UP])
        self.assertFalse(PURPOSES["cook"].valid(situation({"wheat": 2, "planks": 4})))

    def test_hunger_and_raw_food_raise_the_score(self):
        score = PURPOSES["cook"].score
        self.assertEqual(score(situation({"raw_fish": 2})), 60.0)
        self.assertEqual(score(situation({"raw_fish": 2, "wheat": 3}, hunger=40.0)), 80.0)


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_reflexes.py`, add this test at the end of `ReflexTests`:

```python
    def test_warm_up_lights_a_carried_campfire_or_walks_to_one(self):
        cold = pet(inventory={"campfire": 1, "furnace": 1}, vitals={**START_VITALS, "warmth": 20.0})
        self.assertEqual(reflex_hook(cold, brainy(), 0.0), "warm_up")
        self.assertEqual(cold["queue"], [{"kind": "place", "target": [1, 1, 0], "block": "campfire", "purpose": "warm_up"}])
        grid = flat()
        grid.put(12, 1, 0, "campfire")
        wandering = pet(vitals={**START_VITALS, "warmth": 20.0})
        self.assertEqual(reflex_hook(wandering, brainy(grid), 0.0), "warm_up")
        self.assertEqual(wandering["queue"], [{"kind": "walk", "target": [12, 1, 0], "reach": 2.0, "purpose": "warm_up"}])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_cooking.py"`
Expected: `ImportError: cannot import name 'cooking' from 'backend.survival'`.

- [ ] **Step 3: Write the cook purpose**

Create `backend/survival/cooking.py`:

```python
"""cook: turn raw food into better food.

- Raw fish (8 hunger) cooks into cooked fish (30) in 5 s at a lit campfire or furnace within 6
  blocks. With no fire that close, Mimo places a campfire or furnace it carries beside it (in a
  niche it digs when it is below the surface, as toolmaking does), or first crafts a campfire
  from 2 logs and 3 sticks; failing both, it walks to a fire within 32 blocks and cooks there
  next batch.
- Three wheat bake into bread (25) at a crafting table, like craft_tools does it.
A station or fire the plan placed is mined back into Mimo's inventory at the end. Those steps
are kept (`keep`), so a new choice does not leave the station behind. cook is offered while
there is raw food it can cook now, and scores in the needs band.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.crafting import FIRES
from backend.survival.grid import Cell
from backend.survival.foraging import whole_walk
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import STATION_REACH, WORKSTATIONS
from backend.survival.toolmaking import Short, make, place_station, station_spots

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FIRE_TRAVEL = 32.0
FIRE_STAND = 2.0
BREAD_WHEAT = 3


def made(inventory: dict, item: str) -> list[dict] | None:
    """The craft steps that make one `item` from `inventory` (which they then change), or None."""
    trial, steps = dict(inventory), []
    try:
        make(trial, item, 1, steps)
    except Short:
        return None
    inventory.clear()
    inventory.update(trial)
    return steps


def station(inventory: dict, name: str, spots: list[tuple[Cell, bool]], steps: list[dict], placed: list[Cell],
            carried: tuple[str, ...]) -> bool:
    """Place a carried station (the first of `carried`), or make `name` and place it, in the next
    station spot (toolmaking.station_spots). False when there is no spot or nothing to place."""
    if not spots:
        return False
    block = next((item for item in carried if inventory.get(item, 0) > 0), None)
    if block is None:
        crafting = made(inventory, name)
        if crafting is None:
            return False
        steps.extend(crafting)
        block = name
    placed.append(place_station(spots, block, steps))
    inventory[block] -= 1
    return True


def cook_plan(s: Situation) -> list[dict] | None:
    """The steps that cook the raw food Mimo carries, or None when it cannot cook any now."""
    inventory = dict(s.inventory)
    x, _, z = s.here
    near = s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS)
    spots = station_spots(s)
    steps: list[dict] = []
    placed: list[Cell] = []
    fish = inventory.get("raw_fish", 0)
    if fish and not near.intersection(FIRES) and not station(inventory, "campfire", spots, steps, placed, FIRES):
        fires = sorted(s.grid.placed_cells(x, z, FIRE_TRAVEL, FIRES), key=lambda found: s.distance(found[0]))
        if fires:
            return [whole_walk(fires[0][0], FIRE_STAND)]
        fish = 0
    steps.extend({"kind": "cook", "item": "raw_fish"} for _ in range(fish))
    loaves = inventory.get("wheat", 0) // BREAD_WHEAT
    if loaves and "crafting_table" not in near and not station(inventory, "crafting_table", spots, steps, placed,
                                                                ("crafting_table",)):
        loaves = 0
    steps.extend({"kind": "craft", "recipe": "bread"} for _ in range(loaves))
    if not fish and not loaves:
        return None
    steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
    return steps


def plan_cook(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 1:
        return []
    return cook_plan(s) or []


def cook_score(s: Situation) -> float:
    servings = s.count("raw_fish") + s.count("wheat") // BREAD_WHEAT
    return min(80.0, 50.0 + (100.0 - s.vitals["hunger"]) / 4 + 5.0 * servings)


register(Purpose(
    "cook", "cook", "Cook raw fish at a fire and bake wheat into bread; cooked food fills far more.",
    valid=lambda s: cook_plan(s) is not None,
    facts=lambda s: f"carrying {s.count('raw_fish')} raw fish and {s.count('wheat')} wheat",
    score=cook_score, plan=plan_cook,
    thoughts=("Cooked fish tastes so much better.", "Let's get a fire going and cook.")))
```

- [ ] **Step 4: Warm up by a campfire**

In `backend/survival/reflexes.py`, replace:

```python
from backend.survival.vitals import EXHAUSTED_BELOW, is_sheltered
```

with:

```python
from backend.survival.vitals import EXHAUSTED_BELOW, WARM_BLOCKS, is_sheltered
```

In `backend/survival/reflexes.py`, replace the whole `plan_warm_up` function with:

```python
def plan_warm_up(s: Situation, context: ActionContext) -> list[dict]:
    """Light a carried campfire beside Mimo (or place a carried furnace, which warms the same), else
    walk to the nearest known warm spot: a shelter, or a campfire or furnace within 64 blocks.
    Below the surface the fire goes in a niche Mimo digs, never in its way out."""
    fire = next((block for block in WARM_BLOCKS if s.inventory.get(block, 0) > 0), None)
    if fire is not None:
        steps: list[dict] = []
        if place_station(station_spots(s), fire, steps) is not None:
            return steps
    x, _, z = s.here
    spots = []
    home = nearest(s.places, s.here, SHELTER_KINDS, HOME_RANGE)
    if home is not None:
        spots.append((s.distance(cell_of(home)), walk_to(cell_of(home))))
    for cell, _ in s.grid.placed_cells(x, z, HOME_RANGE, WARM_BLOCKS):
        spots.append((s.distance(cell), walk_to(cell, FIRE_STAND)))
    spots = [spot for spot in spots if spot[0] > FIRE_STAND]
    return [min(spots, key=lambda spot: spot[0])[1]] if spots else []
```

- [ ] **Step 5: Let the brain offer cook**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import farming, foraging, toolmaking, work  # noqa: F401  (they register their purposes)
```

with:

```python
from backend.survival import cooking, farming, foraging, toolmaking, work  # noqa: F401  (they register their purposes)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_cooking.py"` and `python3 -m unittest discover -s backend/tests -p "test_survival_reflexes.py"`
Expected: `OK` for both.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 450 tests` … `OK` (7 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/cooking.py backend/survival/reflexes.py backend/survival/brain.py backend/tests/test_survival_cooking.py backend/tests/test_survival_reflexes.py
git commit -m "feat: cook fish at a campfire, bake bread, and warm up by a carried campfire" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 13: gather_wood plants saplings

Trees return only when Mimo plants saplings (spec, "Decisions"). Saplings drop from leaves (Tasks 5 and 7); gather_wood plants the ones Mimo carries before it chops the next tree, and trees grown from them count as trees (Task 8).

**Files:**
- Modify: `backend/survival/senses.py`, `backend/survival/work.py`
- Test: `backend/tests/test_survival_work.py`

**Interfaces:**
- Consumes: Task 5's `nature.SOIL` and the `plant` step; Task 8's `senses.by_distance`; `senses.trees_near`, `LOG`; `Grid.placed_cells`; `blocks.is_replaceable`; `steps.REACH`.
- Produces:
  - `backend.survival.senses`: `trunks_near(grid, seed, x, z, radius) -> set[tuple[int, int]]` (columns of generated trees and of placed or grown logs and saplings).
  - `backend.survival.work`: `SAPLINGS_PER_BATCH = 2`, `SAPLING_ROOM = 3.0`, `TREE_SPACE = 6`; `sapling_spots(s) -> list[Cell]`; `sapling_fits(s, cell) -> bool`; `plant_saplings(s) -> list[dict]`; each gather_wood batch starts with up to 2 `plant` steps for carried saplings.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_survival_work.py`, replace:

```python
    def test_a_tree_where_a_step_failed_is_left_alone(self):
```

with:

```python
    def test_carried_saplings_are_planted_in_open_ground_before_chopping(self):
        grid = ground({(5, y, 0): "oak_log" for y in (1, 2, 3, 4)})
        s = situation(pet(inventory={"sapling": 3}), grid)
        sapling = lambda x, y, z: {"kind": "plant", "target": [x, y, z], "item": "sapling"}  # noqa: E731
        self.assertEqual(PURPOSES["gather_wood"].plan(s, context(grid)),
                         [sapling(-1, 1, 0), sapling(2, 1, 0), walk(5, 1, 0, 2.0),
                          mine(5, 1, 0), mine(5, 2, 0), mine(5, 3, 0), mine(5, 4, 0)])
        roofed = ground({(-1, 3, 0): "stone", **{(5, y, 0): "oak_log" for y in (1, 2, 3, 4)}})
        s = situation(pet(inventory={"sapling": 1}), roofed)
        self.assertEqual(PURPOSES["gather_wood"].plan(s, context(roofed))[0], sapling(0, 1, -1))

    def test_a_tree_where_a_step_failed_is_left_alone(self):
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py"`
Expected: FAIL: the plan starts with the walk (`{'kind': 'walk', ...} != {'kind': 'plant', ...}`).

- [ ] **Step 3: Know where trunks and saplings stand**

In `backend/survival/senses.py`, append:

```python


def trunks_near(grid: Grid, seed: str, x: int, z: int, radius: float) -> set[tuple[int, int]]:
    """Columns within `radius` where a tree stands or a sapling grows: generated trees, and logs
    and saplings that were placed or grew."""
    columns = {(tx, tz) for tx, tz, _ in trees_near(seed, x, z, math.ceil(radius))}
    columns.update((cell[0], cell[2]) for cell, _ in grid.placed_cells(x, z, radius, (LOG, "sapling")))
    return columns
```

- [ ] **Step 4: Plant carried saplings before chopping**

In `backend/survival/work.py`, replace:

```python
gather_wood chops the nearest standing tree within 24 blocks, lowest log first, until Mimo
carries 8 logs' worth of wood (craft_tools turns logs into planks). gather_stone needs a pickaxe:
```

with:

```python
gather_wood chops the nearest standing tree within 24 blocks, lowest log first, until Mimo
carries 8 logs' worth of wood (craft_tools turns logs into planks). Trees only come back when
Mimo plants saplings (they drop from leaves), so each batch first plants up to 2 carried
saplings on open ground within reach, 3 blocks or more from any trunk or other sapling.
gather_stone needs a pickaxe:
```

and replace:

```python
from backend.services.blocks import hardness, is_solid
```

with:

```python
from backend.services.blocks import hardness, is_replaceable, is_solid
```

and replace:

```python
from backend.survival.senses import failed_columns, standing_logs
```

with:

```python
from backend.survival.nature import SOIL
from backend.survival.senses import by_distance, failed_columns, standing_logs, trunks_near
```

and replace:

```python
STAND_REACH = 2.0  # close enough to the lowest log that the top one (3 higher) stays within reach
```

with:

```python
STAND_REACH = 2.0  # close enough to the lowest log that the top one (3 higher) stays within reach
SAPLINGS_PER_BATCH = 2
SAPLING_ROOM = 3.0  # blocks between a planted sapling and any trunk or other sapling
TREE_SPACE = 6  # open cells a sapling needs above its ground for the trunk and canopy
```

and replace:

```python
def plan_wood(s: Situation, context: ActionContext) -> list[dict]:
```

with:

```python
def sapling_spots(s: Situation) -> list[Cell]:
    """Open grass, dirt or moss within reach with room for a tree above, nearest first, and each
    SAPLING_ROOM from every trunk, sapling and other spot."""
    x, y, z = s.here
    taken = trunks_near(s.grid, s.seed, x, z, REACH + SAPLING_ROOM)
    candidates = []
    for dx in range(-3, 4):
        for dz in range(-3, 4):
            for cell in ((x + dx, y, z + dz), (x + dx, y + 1, z + dz), (x + dx, y - 1, z + dz)):
                if 1.0 <= math.dist(cell, s.here) <= REACH and sapling_fits(s, cell):
                    candidates.append(cell)
                    break
    spots = []
    for cell in by_distance(candidates, s.here):
        if all(math.hypot(cell[0] - tx, cell[2] - tz) >= SAPLING_ROOM for tx, tz in taken):
            spots.append(cell)
            taken.add((cell[0], cell[2]))
    return spots


def sapling_fits(s: Situation, cell: Cell) -> bool:
    x, y, z = cell
    if s.grid.material(x, y - 1, z) not in SOIL["sapling"]:
        return False
    return all(is_replaceable(material) and material != "water"
               for material in (s.grid.material(x, y + dy, z) for dy in range(TREE_SPACE)))


def plant_saplings(s: Situation) -> list[dict]:
    count = min(SAPLINGS_PER_BATCH, s.count("sapling"))
    if count <= 0:
        return []
    return [{"kind": "plant", "target": list(cell), "item": "sapling"} for cell in sapling_spots(s)[:count]]


def plan_wood(s: Situation, context: ActionContext) -> list[dict]:
```

and replace:

```python
    return [walk_to(logs[0], STAND_REACH), *({"kind": "mine", "target": list(log)} for log in logs)]
```

with:

```python
    return [*plant_saplings(s), walk_to(logs[0], STAND_REACH), *({"kind": "mine", "target": list(log)} for log in logs)]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 451 tests` … `OK` (1 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/senses.py backend/survival/work.py backend/tests/test_survival_work.py
git commit -m "feat: plant carried saplings before chopping the next tree" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 14: Score bands, routine events and three days on its own

**Files:**
- Modify: `backend/survival/purposes.py`, `backend/survival/world.py`
- Test: `backend/tests/test_survival_days.py`

**Interfaces:**
- Consumes: everything above; `brain.BRAIN`, `choosing.Chooser`, `choosing.InlineExecutor`, `hatch.hatch`, `tick.tick_life`, `snapshot.notable`.
- Produces:
  - The score bands in `purposes.py`'s docstring (survival 80–100, needs 50–80, work 40–70, leisure 10–40).
  - `world.ROUTINE_EVENTS` adds `ate`, `cook`, `fish` and `grow`, so meals and harvests stay off memorials and do not crowd the recent events.
  - `backend/tests/test_survival_days.py`: a hatched pet run by the brain and the utility picker at 60× eats real food it found and lives through three game days.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_survival_days.py`:

```python
import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import notable
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld

BORN = 1_000_000.0
SCALE = 60.0  # a game day is 60 real seconds, as in the manual check
FOODS = ("berries", "brown_mushroom", "red_mushroom", "carrot", "bread", "raw_fish", "cooked_fish", "apple")


class LivingDaysTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def test_left_alone_mimo_finds_real_food_and_lives_through_three_game_days(self):
        chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(8), scale=SCALE)
        lowest = 100.0
        for second in range(1, 3 * 60 + 1):
            state = tick_life(self.registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            self.assertIsNone(state["died_at"], state["cause"])
            chooser.poll(self.registry, BORN + second)
            lowest = min(lowest, state["vitals"]["hunger"])
        events = self.world.events(2000)
        eaten = [event["text"] for event in events if event["kind"] == "ate"]
        self.assertTrue(eaten, "Mimo never ate")
        self.assertGreater(lowest, 15.0)
        self.assertTrue(any(state["inventory"].get(food) for food in FOODS) or len(eaten) >= 3)
        self.assertNotIn("ate", [event["kind"] for event in notable(events)])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: FAIL: `'ate' unexpectedly found in [...]` (meals still count as notable).

- [ ] **Step 3: Document the score bands**

In `backend/survival/purposes.py`, replace:

```python
backend.survival.toolmaking registers craft_tools. backend.survival.brain imports them all.
M4 and M5 register forage, fish, farm, cook, build_* and light_up the same way; nothing here
changes for them.
"""
```

with:

```python
backend.survival.toolmaking registers craft_tools; M4's backend.survival.foraging registers
forage and fish, backend.survival.farming farm, and backend.survival.cooking cook.
backend.survival.brain imports them all. M5 registers build_* and light_up the same way.

Scores fall in bands, so a new purpose fits in with the others (the utility picker adds 0 to 6):
- survival, 80-100: what keeps Mimo alive right now (sleep at night, go home at dusk, eat when
  very hungry);
- needs, 50-80: food and warmth before they turn urgent (forage, fish, cook, eat);
- work, 40-70: tools, materials and the farm (gather_wood, gather_stone, mine_ore, craft_tools,
  farm; a farm with ripe crops climbs into the needs band);
- leisure, 10-40: rest and explore when nothing presses.
"""
```

- [ ] **Step 4: Make meals and harvests routine events**

In `backend/survival/world.py`, replace:

```python
                            "explore", "owner", "plan", "purpose", "reflex"})
```

with:

```python
                            "explore", "owner", "plan", "purpose", "reflex", "ate", "cook", "fish", "grow"})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 1 test` … `OK` (about 3 s).

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 452 tests` … `OK` (1 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/purposes.py backend/survival/world.py backend/tests/test_survival_days.py
git commit -m "feat: document the score bands, keep meals off memorials and check three days alone" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 15: Viewer: food work, farm work and leaf puffs

The new blocks already draw (Task 1) and block sync brings every change the steps and renewal make: bushes turning unripe and ripe, farmland, each crop stage, grown trees, respawned mushrooms. This task names the new steps and purposes in the HUD, gives them poses and bursts, and shows a puff as each leaf decays.

**Files:**
- Create: `frontend/src/survival/LeafPuffs.tsx`
- Modify: `frontend/src/survival/types.ts`, `frontend/src/survival/hud.ts`, `frontend/src/survival/animation.ts`, `frontend/src/survival/effects.ts`, `frontend/src/survival/WorldCanvas.tsx`, `frontend/src/survival/SurvivalWorld.tsx`
- Test: `frontend/src/survival/hud.test.ts`, `frontend/src/survival/animation.test.ts`, `frontend/src/survival/effects.test.ts`

**Interfaces:**
- Consumes: Task 7's `decays` in `/api/mimo`; Task 5's step kinds and their `block`/`item` fields; Tasks 10–12's purpose names; `replay.REPLAY_DELAY` (the pet and, since the M3 fix wave, block changes are drawn that far behind the server; the puffs use the same replay time).
- Produces:
  - `types.ts`: `ActionKind` adds `'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook'`; `interface LeafDecay extends Point { at: number }`; `SurvivalState.decays: LeafDecay[]`.
  - `hud.ts`: `thingName(name) -> string` (drops `_ripe` and a crop stage); action words Picking, Harvesting, Tilling, Planting, Fishing, Cooking; purpose lines "Foraging for food", "Fishing", "Tending the farm", "Cooking a meal".
  - `animation.ts`: `PetMove` adds `'fish'`; pick and plant move like place, harvest and till like mine, cook like work; `bodyPose('fish', …)` leans over the water.
  - `effects.ts`: `PUFF_SECONDS = 0.8`; pick and harvest make break effects; `interface LeafPuff { key: string; cell: Point; age: number }`; `leafPuffs(decays, t) -> LeafPuff[]`; `puffBits(count, age) -> { offsets: Point[]; scale: number }`.
  - `LeafPuffs.tsx`: `LeafPuffs({ decays, now })`; `WorldCanvas` takes `decays?: LeafDecay[]`; `SurvivalWorld` passes `state.decays`.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/survival/hud.test.ts`, replace:

```ts
  actionText, careLabel, causeText, clockTime, dayLabel, lifeLine, purposeText, statusText, vitalBars, workerOnline,
```

with:

```ts
  actionText, careLabel, causeText, clockTime, dayLabel, lifeLine, purposeText, statusText, thingName, vitalBars,
  workerOnline,
```

and replace:

```ts
    expect(actionText(null, 'sleeping')).toBe('Sleeping')
  })
```

with:

```ts
    expect(actionText(null, 'sleeping')).toBe('Sleeping')
  })

  it('names food and farm work without ripeness or crop stages', () => {
    expect(actionText({ kind: 'pick', started_at: 0, ends_at: 1, block: 'berry_bush_ripe' }, 'picking')).toBe('Picking berry bush')
    expect(actionText({ kind: 'harvest', started_at: 0, ends_at: 1, block: 'wheat_3' }, 'harvesting')).toBe('Harvesting wheat')
    expect(actionText({ kind: 'plant', started_at: 0, ends_at: 1, item: 'seeds', block: 'wheat_0' }, 'planting'))
      .toBe('Planting wheat')
    expect(actionText({ kind: 'fish', started_at: 0, ends_at: 40, target: { x: 1, y: 2, z: 3 } }, 'fishing')).toBe('Fishing')
    expect(actionText({ kind: 'cook', started_at: 0, ends_at: 5, item: 'raw_fish' }, 'cooking')).toBe('Cooking raw fish')
    expect(thingName('red_mushroom')).toBe('red mushroom')
  })
```

and replace:

```ts
    expect(purposeText({ purpose: 'build_shelter', reflex: null, choosing: false })).toBe('Build shelter')
```

with:

```ts
    expect(purposeText({ purpose: 'build_shelter', reflex: null, choosing: false })).toBe('Build shelter')
    expect(purposeText({ purpose: 'forage', reflex: null, choosing: false })).toBe('Foraging for food')
    expect(purposeText({ purpose: 'farm', reflex: null, choosing: false })).toBe('Tending the farm')
```

In `frontend/src/survival/animation.test.ts`, replace:

```ts
    expect(moveFor({ kind: 'walk', started_at: 0, ends_at: 3, path: [] }, 1, true)).toBe('swim')
  })
```

with:

```ts
    expect(moveFor({ kind: 'walk', started_at: 0, ends_at: 3, path: [] }, 1, true)).toBe('swim')
    expect(moveFor({ kind: 'fish', started_at: 0, ends_at: 40 }, 10)).toBe('fish')
    expect(moveFor({ kind: 'pick', started_at: 0, ends_at: 1 }, 0.5)).toBe('place')
    expect(moveFor({ kind: 'till', started_at: 0, ends_at: 1 }, 0.5)).toBe('mine')
    expect(moveFor({ kind: 'cook', started_at: 0, ends_at: 5 }, 1)).toBe('work')
  })

  it('leans over the water while fishing', () => {
    const leans = [0, 1, 2, 3, 4].map((seconds) => bodyPose('fish', seconds, 0, 0).pitch)
    expect(Math.min(...leans)).toBeGreaterThanOrEqual(0.28)
    expect(Math.max(...leans)).toBeLessThanOrEqual(0.32)
  })
```

In `frontend/src/survival/effects.test.ts`, replace:

```ts
import { blockEffects, burst, CRACK_STAGES, crackMask, crackStage, crackTexels, itemPop, placeScale } from './effects'
```

with:

```ts
import {
  blockEffects, burst, CRACK_STAGES, crackMask, crackStage, crackTexels, itemPop, leafPuffs, placeScale, PUFF_SECONDS,
  puffBits,
} from './effects'
```

In `frontend/src/survival/effects.test.ts`, append:

```ts

describe('food, farm and leaf effects', () => {
  it('bursts when Mimo picks or harvests, like a break', () => {
    const recent: FinishedAction[] = [
      { kind: 'pick', started_at: 1, ended_at: 1.5, result: 'done', target: { x: 2, y: 1, z: 0 }, block: 'berry_bush_ripe' },
      { kind: 'harvest', started_at: 2, ended_at: 2.5, result: 'done', target: { x: 3, y: 1, z: 0 }, block: 'wheat_3' },
      { kind: 'till', started_at: 3, ended_at: 4, result: 'done', target: { x: 3, y: 0, z: 0 }, block: 'grass' },
    ]
    expect(blockEffects(null, recent).map((effect) => [effect.kind, effect.block])).toEqual([
      ['break', 'berry_bush_ripe'], ['break', 'wheat_3'],
    ])
  })

  it('shows a puff for each leaf that went in the last moment', () => {
    const decays = [{ x: 1, y: 6, z: 1, at: 10 }, { x: 2, y: 6, z: 1, at: 10.5 }, { x: 3, y: 6, z: 1, at: 20 }]
    expect(leafPuffs(decays, 10.6).map((puff) => [puff.cell.x, Number(puff.age.toFixed(2))])).toEqual([[1, 0.6], [2, 0.1]])
    expect(leafPuffs(decays, 10 + PUFF_SECONDS + 0.01).map((puff) => puff.cell.x)).toEqual([2])
    expect(leafPuffs(decays, 5)).toEqual([])
  })

  it('spreads a puff out as it fades', () => {
    const start = puffBits(6, 0)
    const late = puffBits(6, PUFF_SECONDS * 0.9)
    expect(start.offsets).toHaveLength(6)
    expect(start.scale).toBe(1)
    expect(late.scale).toBeCloseTo(0.1)
    expect(Math.hypot(late.offsets[0].x, late.offsets[0].z)).toBeGreaterThan(Math.hypot(start.offsets[0].x, start.offsets[0].z))
    expect(late.offsets[0].y).toBeLessThan(start.offsets[0].y)
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/hud.test.ts src/survival/animation.test.ts src/survival/effects.test.ts`
Expected: FAIL: `thingName is not a function`, `leafPuffs is not a function`, and `expected undefined to be 'fish'`.

- [ ] **Step 3: The new step kinds and the decays in the types**

In `frontend/src/survival/types.ts`, replace:

```ts
export type ActionKind = 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'craft' | 'smelt' | 'sleep' | 'wait'
```

with:

```ts
export type ActionKind = 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'craft' | 'smelt' | 'sleep' | 'wait'
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook'
```

and replace:

```ts
export type PickerName = 'jev' | 'luna' | 'utility'
```

with:

```ts
/** A leaf that decayed after its tree lost its logs, at server time `at`. */
export interface LeafDecay extends Point {
  at: number
}

export type PickerName = 'jev' | 'luna' | 'utility'
```

and replace:

```ts
  recent_actions: FinishedAction[]
  /** The purpose Mimo is working on, like "gather_wood", or null. */
```

with:

```ts
  recent_actions: FinishedAction[]
  /** Leaves that decayed lately, newest last, for a puff as each goes. */
  decays: LeafDecay[]
  /** The purpose Mimo is working on, like "gather_wood", or null. */
```

- [ ] **Step 4: Words, poses, bursts and puffs**

In `frontend/src/survival/hud.ts`, replace:

```ts
  craft: 'Crafting', smelt: 'Smelting', sleep: 'Sleeping',
}
```

with:

```ts
  craft: 'Crafting', smelt: 'Smelting', sleep: 'Sleeping', pick: 'Picking', harvest: 'Harvesting',
  till: 'Tilling', plant: 'Planting', fish: 'Fishing', cook: 'Cooking',
}

/** A block or item in plain words: a crop's stage and a bush's ripeness are left out. */
export function thingName(name: string): string {
  return name.replace(/_(ripe|\d)$/, '').replaceAll('_', ' ')
}
```

and replace:

```ts
  return object ? `${words} ${object.replaceAll('_', ' ')}` : words
```

with:

```ts
  return object ? `${words} ${thingName(object)}` : words
```

and replace:

```ts
  rest: 'Resting', eat: 'Having a meal', escape: 'Digging out of a pit',
```

with:

```ts
  rest: 'Resting', eat: 'Having a meal', escape: 'Digging out of a pit', forage: 'Foraging for food',
  fish: 'Fishing', farm: 'Tending the farm', cook: 'Cooking a meal',
```

In `frontend/src/survival/animation.ts`, replace:

```ts
export type PetMove = 'idle' | 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'sleep' | 'work'
```

with:

```ts
export type PetMove = 'idle' | 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'sleep' | 'work' | 'fish'
```

and replace:

```ts
  craft: 'work', smelt: 'work', wait: 'idle',
}
```

with:

```ts
  craft: 'work', smelt: 'work', wait: 'idle', pick: 'place', harvest: 'mine', till: 'mine', plant: 'place',
  fish: 'fish', cook: 'work',
}
```

and replace:

```ts
    case 'work':
      pose.pitch = 0.06 * Math.sin(stepTime * 8)
      break
```

with:

```ts
    case 'work':
      pose.pitch = 0.06 * Math.sin(stepTime * 8)
      break
    case 'fish':
      // Leaning over the water, with a slow bob now and then as if something nibbles.
      pose.pitch = 0.28 + 0.04 * Math.max(0, Math.sin(stepTime * 1.3)) ** 8
      pose.lift = -0.04
      break
```

In `frontend/src/survival/effects.ts`, replace:

```ts
import type { FinishedAction, MimoAction, Point } from './types'
```

with:

```ts
import type { FinishedAction, LeafDecay, MimoAction, Point } from './types'
```

and replace:

```ts
export const POP_SECONDS = 0.6
```

with:

```ts
export const POP_SECONDS = 0.6
export const PUFF_SECONDS = 0.8
/** Steps that take a block (or what grows on it) away, and so end with a break. */
const BREAKS = new Set(['mine', 'pick', 'harvest'])
```

and replace:

```ts
/** Breaks and placements from finished steps and the running one, one per step. */
export function blockEffects(action: MimoAction | null, recent: FinishedAction[]): BlockEffect[] {
  const found = new Map<string, BlockEffect>()
  const add = (kind: string, cell: Point | undefined, block: string | undefined, at: number | null) => {
    if ((kind !== 'mine' && kind !== 'place') || !cell || !block || at === null) return
    const key = `${kind}:${cell.x},${cell.y},${cell.z}:${at}`
    if (!found.has(key)) found.set(key, { key, kind: kind === 'mine' ? 'break' : 'place', cell, block, at })
  }
```

with:

```ts
/** Breaks and placements from finished steps and the running one, one per step. Picking and
 * harvesting break what grows on a cell, so they burst like mining. */
export function blockEffects(action: MimoAction | null, recent: FinishedAction[]): BlockEffect[] {
  const found = new Map<string, BlockEffect>()
  const add = (kind: string, cell: Point | undefined, block: string | undefined, at: number | null) => {
    if ((!BREAKS.has(kind) && kind !== 'place') || !cell || !block || at === null) return
    const key = `${kind}:${cell.x},${cell.y},${cell.z}:${at}`
    if (!found.has(key)) found.set(key, { key, kind: kind === 'place' ? 'place' : 'break', cell, block, at })
  }
```

In `frontend/src/survival/effects.ts`, append:

```ts

export interface LeafPuff {
  key: string
  cell: Point
  /** Seconds since the leaf went. */
  age: number
}

/** The leaf puffs showing at server time `t`: decays that happened less than PUFF_SECONDS ago. */
export function leafPuffs(decays: LeafDecay[], t: number): LeafPuff[] {
  return decays
    .filter((decay) => t >= decay.at && t - decay.at < PUFF_SECONDS)
    .map((decay) => ({ key: `${decay.x},${decay.y},${decay.z}:${decay.at}`, cell: decay, age: t - decay.at }))
}

/** Where the bits of one puff are, `age` seconds after the leaf went: they drift out, sink slowly
 * and shrink away. */
export function puffBits(count: number, age: number): { offsets: Point[]; scale: number } {
  const p = Math.min(1, Math.max(0, age / PUFF_SECONDS))
  const offsets = Array.from({ length: count }, (_, index) => {
    const angle = index * GOLDEN_ANGLE
    const spread = 0.25 + 0.35 * p
    return { x: Math.cos(angle) * spread, y: 0.1 * (index % 3) - 0.5 * p * p, z: Math.sin(angle) * spread }
  })
  return { offsets, scale: 1 - p }
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/survival/hud.test.ts src/survival/animation.test.ts src/survival/effects.test.ts`
Expected: all pass.

- [ ] **Step 6: Draw the puffs 1.5 s behind the server, like the pet**

Create `frontend/src/survival/LeafPuffs.tsx`:

```tsx
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { blockDef, blockId } from '../engine/blocks'
import { leafPuffs, puffBits } from './effects'
import type { LeafDecay } from './types'

const BITS = 6
const MAX_PUFFS = 8
const [LEAF_R, LEAF_G, LEAF_B] = blockDef(blockId('leaves')).color
const LEAF_COLOR = new THREE.Color().setRGB(LEAF_R / 255, LEAF_G / 255, LEAF_B / 255, THREE.SRGBColorSpace)

/** A small puff of leaf bits where each decaying leaf goes, drawn at `now` (the replay time). */
export default function LeafPuffs({ decays, now }: { decays: LeafDecay[]; now: () => number }) {
  const bits = useRef<THREE.InstancedMesh>(null)
  const scratch = useRef<THREE.Object3D | null>(null)

  useFrame(() => {
    const mesh = bits.current
    if (!mesh) return
    const puffs = leafPuffs(decays, now()).slice(-MAX_PUFFS)
    const dummy = (scratch.current ??= new THREE.Object3D())
    let shown = 0
    for (const puff of puffs) {
      const { offsets, scale } = puffBits(BITS, puff.age)
      for (const offset of offsets) {
        dummy.position.set(puff.cell.x + 0.5 + offset.x, puff.cell.y + 0.5 + offset.y, puff.cell.z + 0.5 + offset.z)
        dummy.scale.setScalar(scale)
        dummy.updateMatrix()
        mesh.setMatrixAt(shown++, dummy.matrix)
      }
    }
    mesh.count = shown
    mesh.visible = shown > 0
    mesh.instanceMatrix.needsUpdate = true
  })

  return (
    <instancedMesh ref={bits} args={[undefined, undefined, BITS * MAX_PUFFS]} visible={false} frustumCulled={false}>
      <boxGeometry args={[0.14, 0.14, 0.14]} />
      <meshLambertMaterial color={LEAF_COLOR} />
    </instancedMesh>
  )
}
```

In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import ActionEffects from './ActionEffects'
```

with:

```tsx
import ActionEffects from './ActionEffects'
import LeafPuffs from './LeafPuffs'
```

and replace:

```tsx
import type { FinishedAction, MimoAction } from './types'
```

with:

```tsx
import type { FinishedAction, LeafDecay, MimoAction } from './types'
```

and replace:

```tsx
const NO_ACTIONS: FinishedAction[] = []
```

with:

```tsx
const NO_ACTIONS: FinishedAction[] = []
const NO_DECAYS: LeafDecay[] = []
```

and replace:

```tsx
recentActions = NO_ACTIONS, serverTime }: {
```

with:

```tsx
recentActions = NO_ACTIONS, decays = NO_DECAYS, serverTime }: {
```

and replace:

```tsx
  recentActions?: FinishedAction[]
```

with:

```tsx
  recentActions?: FinishedAction[]
  decays?: LeafDecay[]
```

and replace:

```tsx
          {serverTime && <ActionEffects store={store} action={action} recent={recentActions} position={position} now={replayTime} />}
```

with:

```tsx
          {serverTime && <ActionEffects store={store} action={action} recent={recentActions} position={position} now={replayTime} />}
          {serverTime && <LeafPuffs decays={decays} now={replayTime} />}
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
recentActions={state.recent_actions} serverTime={serverTime} />
```

with:

```tsx
recentActions={state.recent_actions} decays={state.decays} serverTime={serverTime} />
```

- [ ] **Step 7: Build, lint and test**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  173 passed (173)` (5 new), the build succeeds, eslint prints nothing.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/survival/types.ts frontend/src/survival/hud.ts frontend/src/survival/hud.test.ts frontend/src/survival/animation.ts frontend/src/survival/animation.test.ts frontend/src/survival/effects.ts frontend/src/survival/effects.test.ts frontend/src/survival/LeafPuffs.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/survival/SurvivalWorld.tsx
git commit -m "feat: show food and farm work in the viewer and a puff as each leaf decays" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 16: Manual check at 60× and the README

This task is for the controller. It runs Docker against a scratch volume and a separately tagged image; the real `pets_mimo_data` volume is never mounted. At `MIMO_TIME_SCALE=60` a game day lasts 60 real seconds (40 s of day, 20 s of night), a crop stage near water 12 s, berry regrowth 2 minutes and leaf decay 1–6 s; `MIMO_ACTION_SCALE=60` makes the steps 60 times shorter (fishing takes a third to one real second). If a check fails, fix the code in the task that owns it, re-run that task's tests, and repeat the check. Stop any other server on ports 8011 and 3000 first.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 452 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  173 passed (173)`, the build succeeds, eslint prints nothing.

- [ ] **Step 2: Build a scratch image and start a scratch world at 60×**

```bash
docker build -f backend/Dockerfile -t mimo-m4-check .
docker volume create mimo_m4_check
docker run --rm -v mimo_m4_check:/data -e MIMO_DB_PATH=/data/mimo.sqlite3 mimo-m4-check \
  python -c "from backend.services.live_mimo import MimoStore; MimoStore(); print('scratch legacy world ready')"
docker run -d --name mimo-m4-api -p 127.0.0.1:8011:8000 -v mimo_m4_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 mimo-m4-check
docker run -d --name mimo-m4-worker -v mimo_m4_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 -e MIMO_ACTION_SCALE=60 \
  -e MIMO_TICK_SECONDS=1 mimo-m4-check python -m backend.workers.mimo_worker
```

Expected: `scratch legacy world ready`, then two container ids. No model key is passed, so the utility picker chooses.

After a few seconds, hatch the egg and note the time:

```bash
curl -s -X POST http://127.0.0.1:8011/api/lives/hatch | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['life']['id'], d['life']['name'])"
date
```

Expected: `2 <name>`.

- [ ] **Step 3: Keep a story snippet and two nudges ready**

Save these in your scratchpad directory (not in the repo). `story.sh` prints the food story, the growth table and what Mimo remembers:

```bash
docker exec -i mimo-m4-api python - <<'PY'
import collections
from backend.survival.clock import clock_at
from backend.survival.memory import places
from backend.survival.registry import LifeRegistry
from backend.survival.steps import FOOD
from backend.survival.world import SurvivalWorld

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
state = world.state()
for event in reversed(world.events(400)):
    if event["kind"] in ("ate", "sick", "fish", "cook", "grow", "purpose", "reflex", "plan", "discovered", "death"):
        print(event["kind"], "|", event["text"])
clock = clock_at(state["born_at"], state["last_tick_at"], 60)
print("day", clock["day_number"], clock["phase"], "| vitals", {k: round(v) for k, v in state["vitals"].items()})
print("food carried", {item: n for item, n in state["inventory"].items() if item in FOOD or item in ("wheat", "seeds", "sapling")})
print("fish stocks", state.get("fish"), "| decays kept", len(state.get("decays", [])))
with world.connect() as db:
    print("growth due", collections.Counter(row[0] for row in db.execute("SELECT block FROM growth")))
    print("places", [(place["kind"], place["note"], place["data"]) for place in places(db, ("food", "fire", "farm"))][:10])
    print("poisonous", [row[0] for row in db.execute("SELECT subject FROM memory_knowledge")])
PY
```

`fish.sh` moves Mimo to the nearest shore within 64 blocks and makes fishing its purpose (a manual nudge, for when the spawn has no water near):

```bash
docker exec -i mimo-m4-api python - <<'PY'
from backend.survival.grid import world_grid
from backend.survival.registry import LifeRegistry
from backend.survival.senses import shores_near
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    shores = shores_near(world_grid(db, state["world_seed"]), state["world_seed"], as_cell(state["position"]), 64)
    stand = shores[0][0]
    state["position"] = {"x": float(stand[0]), "y": float(stand[1]), "z": float(stand[2])}
    state["action"], state["queue"] = None, []
    ensure_brain(state).update(purpose="fish", pending=None, batches=0, replans=0, planned_at=None)
    write_state(db, state)
print("fishing from", stand)
PY
```

`farm.sh` gives Mimo 4 seeds and 2 carrots and makes farming its purpose:

```bash
docker exec -i mimo-m4-api python - <<'PY'
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import ensure_brain
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    for item, count in (("seeds", 4), ("carrot", 2)):
        state["inventory"][item] = state["inventory"].get(item, 0) + count
    state["action"], state["queue"] = None, []
    ensure_brain(state).update(purpose="farm", pending=None, batches=0, replans=0, planned_at=None)
    write_state(db, state)
print("farming")
PY
```

Expected: the story snippet prints event lines and a `day` line; the nudges print `fishing from (...)` and `farming`.

- [ ] **Step 4: Start the viewer against the scratch API**

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8011 npm run dev -- --port 3000 --strictPort
```

Open `http://localhost:3000/preview?debug` in the Browser pane.

- [ ] **Step 5: Check the API stream**

```bash
curl -s http://127.0.0.1:8011/api/mimo | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['purpose'], d['status'], d['decays'][-3:], {k: v for k, v in d['inventory'].items()})"
```

Expected: a purpose, a status, a list for `decays` (empty until the first tree falls) and the inventory.

- [ ] **Step 6: Wild food and a meal**

Look around the spawn in the viewer: berry bushes with red berries in meadows and at forest edges, brown and red mushrooms on the forest floor, drawn as soft-pixel sprites. Watch the first two game days (2 real minutes), running the story snippet every 30 seconds. Confirm:

- `decided to forage` appears once hunger has fallen (usually on day 1 or 2); the HUD reads `Foraging for food` and `Picking berry bush`; the pet leans in, a small burst of red flies, and the bush loses its berries (block sync).
- `places` lists a `food` place with `{'ripe': n, 'seen_at': ...}`.
- An `ate | <name> ate berries.` (or another food) line appears, from the eat purpose or the eat-now reflex. If the pet eats a red mushroom, `sick | <name> ate red mushroom and felt sick.` appears, `poisonous` lists `red_mushroom`, and the pet never eats one again.
- The memorial-style notable list stays free of meals: `curl -s http://127.0.0.1:8011/api/lives/2 | python3 -c "import json,sys; print([e['kind'] for e in json.load(sys.stdin)['notable_events']])"` shows no `ate`.

- [ ] **Step 7: Leaf decay after chopping**

When the HUD shows `Gathering wood` and the pet chops the top log of a tree, watch the canopy: the leaves vanish one by one over the next few seconds, each with a small green puff. Confirm the story snippet shows `decays kept` above 0 and `growth due` with `air` rows while the leaves are still going, and that a `sapling` or an `apple` sometimes turns up in `food carried`. On a later `Gathering wood`, the HUD reads `Planting sapling` before the walk to the next tree; a game day later `grow | A sapling grew into a tree.` appears and the new tree stands there.

- [ ] **Step 8: Fishing and cooking**

If `decided to fish` has not appeared by day 3, run `fish.sh`. Confirm: the HUD reads `Fishing` and the pet leans over the water; `fish | <name> caught a fish.` lines appear and `fish stocks` shows the region's stock below 12 (and one higher a game day later). Soon after, `decided to cook` appears: a campfire appears beside the pet (crafted from logs if it carried none), the HUD reads `Cooking raw fish`, `cook | <name> cooked raw fish.` lines follow, and the campfire is mined back. `food carried` shows `cooked_fish`.

- [ ] **Step 9: A farm growing**

If `decided to farm` has not appeared by day 3, run `farm.sh`. Confirm: the pet tills grass into farmland beside water (a new furrowed block), plants carrots and seeds, and `places` lists a `farm`. Within about 40 real seconds the sprouts grow through their stages to ripe wheat with golden ears and carrots with orange tops (`growth due` counts `wheat_1`… rows as they go). On the next `Tending the farm` the pet harvests (`Harvesting wheat`, a burst) and plants again; untended bare farmland turns back to dirt after two game days.

- [ ] **Step 10: Several days on its own**

Leave the pet alone for at least 7 game days (7 real minutes) from the hatch, feeding nothing. Confirm: it is alive on day 8 (M3's pet starved on day 5), the story snippet's hunger stays above 0 whenever it is read, the `ate` lines come from food it found, fished, farmed or cooked, and `docker logs mimo-m4-worker 2>&1 | grep -c "crashed"` stays small (one line per distinct error, none for `renewal`).

- [ ] **Step 11: Check the phone layout**

Resize the Browser pane to the mobile preset and reload. Confirm the HUD shows the purpose line and the step line (for example `Foraging for food` and `Picking berry bush`) without overlapping the vitals, and that the new sprites and the leaf puffs draw. Reset the viewport to desktop afterwards.

- [ ] **Step 12: Clean up the scratch run**

Stop the dev server (Ctrl+C), then remove only what this task created:

```bash
docker rm -f mimo-m4-api mimo-m4-worker
docker volume rm mimo_m4_check
docker image rm mimo-m4-check
```

- [ ] **Step 13: Describe food and renewal in the README**

In `README.md`, replace:

```markdown
Sky, fog and terrain brightness follow the game clock. Glowing blocks (lanterns, furnaces, lava) keep their light at night.
```

with:

```markdown
Sky, fog and terrain brightness follow the game clock. Glowing blocks (lanterns, furnaces, campfires, torches, lava) keep their light at night.
```

and replace:

```markdown
A roof within 4 blocks overhead with walls on 3 sides, or a furnace within 4 blocks, keeps the pet warm;
```

with:

```markdown
A roof within 4 blocks overhead with walls on 3 sides, or a campfire or furnace within 4 blocks, keeps the pet warm;
```

and replace:

```markdown
placing 0.3 s, eating 1.6 s, crafting 1 s and smelting 5 s.
```

with:

```markdown
placing 0.3 s, eating 1.6 s, crafting 1 s, smelting 5 s, picking and harvesting 0.5 s, tilling 1 s, planting 0.3 s, fishing 20 to 60 s and cooking 5 s.
```

and replace:

```markdown
bobbing in water and a quickening drop when falling.
```

with:

```markdown
bobbing in water, a quickening drop when falling, a lean over the water while fishing and a burst when a plant is picked or harvested.
```

and replace:

```markdown
eat now (hunger below 15 with food), warm up (warmth below 25: place a carried furnace, or go to a known shelter or furnace),
```

with:

```markdown
eat now (hunger below 15 with food it does not know is poisonous), warm up (warmth below 25: light a carried campfire or place a carried furnace, or go to a known shelter, campfire or furnace),
```

and replace:

```markdown
Food, farming and building purposes arrive with the next milestones.
```

with:

```markdown
Forage, fish, farm and cook find and grow food (see Food and renewal), and gather wood plants the saplings Mimo carries; building purposes arrive with the next milestone. Scores fall in bands: survival 80–100, needs 50–80, work 40–70, leisure 10–40.
```

and replace:

```markdown
- **Memory** lives in each world's database and starts empty: places (home, shelters, ore it saw, dangerous drops, water) and the recipes Mimo has used.
```

with:

```markdown
- **Memory** lives in each world's database and starts empty: places (home, shelters, ore it saw, dangerous drops, water, food patches with how much was ripe and when, fires it left, its farm), the recipes Mimo has used and facts it learned, like that red mushrooms made it sick.
```

and replace:

```markdown
## Current world rules
```

with:

```markdown
## Food and renewal

- **Food** and the hunger it restores: berries 8 (a ripe bush gives 3), brown mushroom 6, red mushroom 6 (it also takes 10 health, never the last point, and Mimo never eats one again), carrot 10, apple 15, bread 25 (3 wheat at a crafting table), raw fish 8 and cooked fish 30 (5 s at a campfire or furnace, no fuel). Wheat and seeds are not food.
- **Wild food** grows on generated land in both worldgens: ripe berry bushes in meadows and at forest edges, mushrooms on forest floors and cave floors, a third of them red. Water lies wherever the ground is below sea level.
- **Steps:** pick a ripe bush or a mushroom, harvest a ripe crop, till grass, dirt or moss into farmland (by hand), plant seeds or a carrot on farmland and a sapling on grass, fish from a shore, and cook. Breaking tall grass may give seeds (1 in 5) or a carrot (1 in 20); leaves, mined or decayed, may give a sapling (1 in 12) or an apple (1 in 20).
- **Purposes:** forage picks ripe food nearby until Mimo carries a game day's worth, and walks back to a food patch it remembers once it has grown again. Fish fishes from the nearest shore whose water still has fish. Farm tills plots beside water, plants carrots and seeds, harvests ripe crops and plants again, and breaks tall grass for seeds when it has nothing to plant. Cook lights a campfire (carried, or made on the spot from 2 logs and 3 sticks), cooks the fish, bakes bread and picks the fire back up. Their walks go all the way or not at all, so a route that only gets part of the way never strands Mimo in a pit, and places where a step just failed are left alone for a while. A far farm is only visited when work waits there, and gather stone never digs up farmland or a sapling.
- **Renewal** is part of the world, not of Mimo: every tick applies the changes that are due in each world's `growth` table, oldest first, even during a catch-up. A picked bush is ripe again 2 game days later. A crop grows a stage every 12 game minutes with water within 4 blocks and every 36 otherwise. Farmland without a crop turns back into dirt after 2 game days. A sapling becomes a tree after a game day when it has room. A picked mushroom comes back on forest floor, one per chunk per game day and at most 3 in a chunk. Each 16×16 stretch of water starts with 12 fish and gains one a game day. When the last log of a tree goes, its leaves decay over the next 1 to 6 game minutes, and Mimo gathers what they drop if it is within 16 blocks. Mined ore never comes back.
- `/api/mimo` adds `decays`, the leaves that decayed lately. The viewer shows a puff of leaves as each goes, 1.5 s behind the server like the pet and the blocks.

## Current world rules
```

and replace:

```markdown
- Trees, flowers, tall grass and the home cottage are part of worldgen on both sides.
```

with:

```markdown
- Trees, flowers, tall grass, berry bushes, mushrooms and the home cottage are part of worldgen on both sides.
```

and replace:

```markdown
A placed furnace consumes fuel to smelt ore or sand.
```

with:

```markdown
A placed furnace consumes fuel to smelt ore or sand. Bread (3 wheat at a crafting table) and a campfire (2 logs and 3 sticks) are recipes too, and raw fish cooks at a campfire or furnace without fuel.
```

- [ ] **Step 14: Run every check again and commit**

Run: `python3 -m unittest discover -s backend/tests && cd frontend && npm test && npm run build`
Expected: `Ran 452 tests` … `OK`, `Tests  173 passed (173)`, the build succeeds.

```bash
git add README.md
git commit -m "docs: describe food, farming, fishing, cooking and renewal" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (M4) | Where |
|-----------|-------|
| §7 new blocks `berry_bush`, `berry_bush_ripe`, `brown_mushroom`, `red_mushroom`, `farmland`, `wheat_0`–`3`, `carrot_0`–`3`, `sapling`, `campfire` (glow), `torch` (glow), `bed`, `chest`; plants and crops `cutout`, `solid: false` | Task 1 (registry, appended; resolutions 2 and 3) |
| §7 worldgen places berry bushes (meadow, forest edge) and mushrooms (forest floor, caves) in both languages; parity fixture updated | Task 3 (resolution 4) |
| §7 items and food table: berries +8 (bush becomes unripe), brown mushroom +6, red mushroom −10 health and memory learns it, carrot +10 and replant, wheat 0 and 3 → bread at a table, bread +25, raw fish +8 (20–60 s, stock), cooked fish +30 (5 s at a campfire or furnace), seeds 20% from tall grass, sapling 1 in 12, apple +15 1 in 20 | Tasks 2 (food, poison, bread, cooking rule), 5 (picks, harvests, fishing, chance drops), 7 (decay drops), 9 (learning poison) |
| §7 renewal: a `growth` table `(x, y, z, block, ready_at)` the worker applies each tick | Task 6 (`renewal`, `run_renewal` in `advance_world`; resolution 15) |
| §7 berry regrowth after 2 game days; crops every 12 or 36 game minutes with or without water within 4; farmland reverts after 2 game days without a crop | Task 6 (resolution 16) |
| §7 sapling → tree after 1 game day if there is space | Task 7 (`tree_fits`, `grow_tree`, retry; resolution 16) |
| §7 fish stock per 16×16 region, 12, +1 per game day | Tasks 5 (`take_fish`, `catches`), 6 (`recover_fish` in `renew`; resolution 14) |
| §7 leaf decay: no log within 4 through leaves and logs → vanish in 1–6 game minutes, with drops, and a puff in the viewer | Tasks 7 (`orphaned_leaves`, `leaf_supported`, `decay`, `state["decays"]`), 15 (`LeafPuffs`; resolutions 8 and 17) |
| §7 ore never regrows; mushrooms reappear on dark forest floor, one per chunk per game day, at most 3 | Task 7 (`respawn_mushroom`, `MUSHROOM_CAP`; resolution 18); nothing schedules ore |
| Decisions: trees return only when Mimo plants saplings | Tasks 5 (`plant`), 13 (gather_wood plants saplings), 8 (grown trees count) |
| §5 purposes `eat`, `forage`, `fish`, `farm`, `cook` (cook needs raw food and a lit fire or furnace nearby) | Tasks 9 (eat with real food, poison-aware), 10 (forage, fish), 11 (farm), 12 (cook; resolution 24) |
| §5 planner steps `pick`, `fish`, `till`, `plant`, `harvest` (and cooking) | Tasks 4 (registry), 5 (the kinds; resolutions 10–13) |
| §5 reflexes: eat now with real food; warm up with a campfire | Tasks 9 (eat_now skips known poison), 12 (warm_up lights a carried campfire; resolution 25) |
| §5 memory: food patches with last-seen ripe count and time; fires | Task 9 (`data`, `update_place`, `learning.note_food_patch`, `fire` and `farm` places; resolutions 19 and 20) |
| §9 viewer: new block textures in the soft-pixel 8×8 atlas, crop stages, a leaf-decay puff | Tasks 1 (painters, crop `size`), 15 (HUD words, poses, bursts, puffs) |
| §10 API: what the viewer needs | Task 7 (`decays` in `/api/mimo`); step kinds and purposes use the M3 fields |
| §12 a planner cannot find a path or material → re-plan once, report | Unchanged M3 rule; M4 planners also leave places near a failed step alone and walk all the way or not at all (Tasks 8, 10; resolution 21) |
| §12 clock jump: catch-up applies growth | Task 6 (`run_renewal` after each catch-up chunk, crops chained from their own due time) |
| §13 simulation tests with an injected clock; brain tests for every new purpose's validity; the utility picker on real food | Tasks 6 and 7 (renewal with scales), 10–12 (validity and scores), 14 (three game days alone at 60×); the fix wave's headless game day keeps passing with a budget for food work (Task 10; resolution 30) |
| §13 parity fixture regenerated when worldgen gains bushes and mushrooms | Task 3 |
| §13 manual run at 60×: a meal, foraging, a farm growing, fishing, cooking, leaf decay, several days survived | Task 16 |
| M3 review: step registry; food health effects and a knowledge table; memory `data` and `update_place`, bounded reads; growth in the world per catch-up chunk; `keep` steps for campfire pickup; score bands | Tasks 4; 2 and 9; 9; 6; 12; 14 |

Out of scope here: shelters, farms as structures, storage, lights, the building generator, beds and chests in use, torches placed (M5); creatures, light levels, hunting (sub-project 3); chat (sub-project 4); flowing water and falling sand (sub-project 5).
