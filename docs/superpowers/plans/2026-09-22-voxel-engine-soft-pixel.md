# Voxel Engine and Soft Pixel Look Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/preview` renderer with a solid voxel engine: a block registry shared by Python and TypeScript, worldgen that owns every natural block in both languages, incremental block sync, and chunk-column meshes with 8×8 soft pixel textures and baked ambient occlusion.

**Architecture:** `shared/blocks.json` lists every block. Python and TypeScript worldgen produce identical natural blocks, checked against `shared/worldgen-fixture.json`. The server numbers every block write with a `seq` and serves deltas at `/api/mimo/blocks`. In the browser, `WorldStore` holds edits and generated columns, a Web Worker generates and meshes columns, and `ColumnRenderer` uploads the meshes into three.js.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-22-voxel-engine-soft-pixel-design.md`

## Global Constraints

- Python code must run on Python 3.10 (local tests) and 3.12 (Docker). Keep `from __future__ import annotations` at the top of modules.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters` on. Do not use constructor parameter properties, enums or namespaces. Prefix intentionally unused parameters with `_`.
- Block ids are array indexes in `shared/blocks.json`. Id 0 is `air`. Id 255 is reserved for the client-only `missing` block. The list is append-only.
- World height is y = -8 to 119 (128 cells). Chunk columns are 16 × 128 × 16.
- Face shade: up 1.0, east/west 0.82, south/north 0.66, down 0.5. AO light for levels 0–3: 0.45, 0.62, 0.8, 1.0. Per-block tint ±3%.
- View distance: 6 chunks on desktop, 4 when the smaller viewport side is under 600 px or `navigator.hardwareConcurrency` ≤ 4. Unload columns 2 beyond the view distance.
- Palette: the current pastel catalog colors. Textures are 8×8 with ±4.5% noise.
- Do not change the `World` or `VoxelTest` pages, `WorldManager.tsx`, `VoxelChunk.tsx` or `WorldScene.tsx`.
- Never write to the real `pets_mimo_data` Docker volume during checks. Use a scratch database.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests`
- Frontend tests: `cd frontend && npm test`
- Frontend build: `cd frontend && npm run build`

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `shared/blocks.json` | Create | Block registry: tiles and ordered blocks |
| `shared/worldgen-fixture.json` | Create (generated) | Cells both worldgen ports must agree on |
| `backend/services/blocks.py` | Create | Load the registry, `is_replaceable` |
| `backend/services/crafting.py` | Modify | `BLOCKS` comes from the registry |
| `backend/services/worldgen.py` | Modify | Home clearing, trees, plants, `block_at` |
| `backend/scripts/worldgen_fixture.py` | Create | Build and write the fixture |
| `backend/services/live_mimo.py` | Modify | `seq`, `_write_block`, `blocks_since`, replaceable checks |
| `backend/api/mimo.py` | Modify | `GET /api/mimo/blocks` |
| `backend/Dockerfile` | Modify | Copy `shared/` into the image |
| `frontend/src/engine/blocks.ts` | Create | TS registry, ids, per-id lookup tables |
| `frontend/src/engine/worldgen.ts` | Move + modify | From `components/world/worldgen.ts`; adds `blockAt`, `generateColumn` |
| `frontend/src/engine/atlas.ts` | Create | Paint 8×8 tiles, face → tile map, water animation |
| `frontend/src/engine/mesher.ts` | Create | Column volume → three layers of vertex buffers |
| `frontend/src/engine/worldStore.ts` | Create | Edits, base columns, `getBlock`, dirty columns |
| `frontend/src/engine/blockSync.ts` | Create | Page `/api/mimo/blocks` into the store |
| `frontend/src/engine/columnVolume.ts` | Create | Column cache and padded volume for the mesher |
| `frontend/src/engine/workerProtocol.ts` | Create | Worker message types |
| `frontend/src/engine/world.worker.ts` | Create | Generate and mesh columns off the main thread |
| `frontend/src/engine/columnRenderer.ts` | Create | Worker queue, three.js meshes, textures |
| `frontend/src/engine/BlockWorld.tsx` | Create | React wrapper for `ColumnRenderer` |
| `frontend/src/components/world/worldPlanner.ts` | Modify | Compilers emit materials; station moves here |
| `frontend/src/components/world/previewWorld.ts` | Modify | Keep only the pet model |
| `frontend/src/components/world/expandingWorld.ts` | Delete | Replaced by the engine |
| `frontend/src/pages/WorldPreview.tsx` | Modify | Use the engine |

---

### Task 1: Block registry shared by Python

**Files:**
- Create: `shared/blocks.json`
- Create: `backend/services/blocks.py`
- Modify: `backend/services/crafting.py:7-33` (the `BLOCKS` literal)
- Modify: `backend/Dockerfile`
- Modify: `docs/superpowers/specs/2026-09-22-voxel-engine-soft-pixel-design.md` (registry section)
- Test: `backend/tests/test_blocks.py`

**Interfaces:**
- Produces: `shared/blocks.json` with `{"tiles": {name: {pattern, color, accent?}}, "blocks": [ {name, color, textures, layer, solid, drop, ...} ]}`. `textures` is a tile name or `{"top", "side", "bottom"}`.
- Produces (Python): `backend.services.blocks.TILES: dict`, `BLOCK_LIST: list[dict]`, `BLOCK_IDS: dict[str, int]`, `BLOCK_PROPERTIES: dict[str, dict]`, `is_replaceable(material: str) -> bool`.
- Produces: `backend.services.crafting.BLOCKS` keeps its exact old shape for the 25 existing blocks.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_blocks.py`:

```python
import unittest

from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, TILES, is_replaceable
from backend.services.crafting import BLOCKS

# Gameplay properties as they were before the registry moved to shared/blocks.json.
LEGACY_BLOCKS = {
    "grass": {"color": [127, 173, 137], "drop": "dirt"},
    "snow": {"color": [236, 241, 243], "drop": "dirt"},
    "dirt": {"color": [126, 105, 89], "drop": "dirt"},
    "stone": {"color": [153, 151, 148], "drop": "cobblestone", "requires": "wooden_pickaxe"},
    "cobblestone": {"color": [130, 137, 137], "drop": "cobblestone"},
    "bedrock": {"color": [67, 72, 75], "drop": None},
    "sand": {"color": [222, 203, 158], "drop": "sand", "gravity": True},
    "gravel": {"color": [159, 166, 162], "drop": "gravel", "gravity": True},
    "clay": {"color": [166, 190, 192], "drop": "clay"},
    "brick": {"color": [184, 105, 86], "drop": "brick"},
    "basalt": {"color": [75, 83, 86], "drop": "basalt"},
    "oak_log": {"color": [139, 105, 82], "drop": "oak_log"},
    "planks": {"color": [202, 171, 125], "drop": "planks"},
    "leaves": {"color": [101, 164, 128], "drop": None},
    "coal_ore": {"color": [88, 94, 97], "drop": "coal", "requires": "wooden_pickaxe"},
    "iron_ore": {"color": [182, 138, 107], "drop": "iron_ore", "requires": "stone_pickaxe"},
    "copper_ore": {"color": [170, 116, 91], "drop": "copper_ore", "requires": "stone_pickaxe"},
    "glass": {"color": [160, 218, 218], "drop": "glass", "opacity": 0.38},
    "water": {"color": [103, 179, 203], "drop": None, "opacity": 0.58, "fluid": True},
    "lava": {"color": [244, 117, 57], "drop": None, "opacity": 0.85, "fluid": True, "glow": True},
    "wool": {"color": [238, 226, 204], "drop": "wool"},
    "moss": {"color": [85, 139, 100], "drop": "moss"},
    "lantern": {"color": [247, 213, 143], "drop": "lantern", "glow": True},
    "crafting_table": {"color": [169, 117, 72], "drop": "crafting_table"},
    "furnace": {"color": [88, 91, 89], "drop": "furnace", "glow": True},
}


class BlockRegistryTests(unittest.TestCase):
    def test_air_is_id_zero_and_ids_fit_below_the_missing_id(self):
        self.assertEqual(BLOCK_IDS["air"], 0)
        self.assertLess(len(BLOCK_LIST), 255)
        self.assertEqual(len(BLOCK_IDS), len(BLOCK_LIST), "block names must be unique")

    def test_existing_block_properties_are_unchanged(self):
        for name, properties in LEGACY_BLOCKS.items():
            self.assertEqual(BLOCKS[name], properties, name)
        self.assertNotIn("air", BLOCKS)

    def test_every_block_face_uses_a_defined_tile(self):
        for block in BLOCK_LIST:
            textures = block["textures"]
            tiles = [textures] if isinstance(textures, str) else [textures["top"], textures["side"], textures["bottom"]]
            for tile in tiles:
                self.assertIn(tile, TILES, f"{block['name']} uses unknown tile {tile}")

    def test_new_build_and_plant_materials_exist(self):
        for name in ("limestone", "polished_stone", "dark_slate", "plaster", "roof_tile", "dirt_path",
                     "hull_panel", "solar_panel", "brass", "sandstone", "verdigris",
                     "tall_grass", "flower_orange", "flower_pink", "flower_yellow"):
            self.assertIn(name, BLOCKS)

    def test_only_air_water_and_plants_are_replaceable(self):
        for name in ("air", "water", "tall_grass", "flower_pink"):
            self.assertTrue(is_replaceable(name), name)
        for name in ("stone", "leaves", "glass", "not_a_block"):
            self.assertFalse(is_replaceable(name), name)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest backend.tests.test_blocks -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.blocks'`

- [ ] **Step 3: Create the registry**

Create `shared/blocks.json`. Keep the block order exactly as written: the index is the id.

```json
{
  "tiles": {
    "missing": {"pattern": "missing", "color": [255, 0, 255]},
    "grass_top": {"pattern": "grass_top", "color": [127, 173, 137]},
    "grass_side": {"pattern": "grass_side", "color": [126, 105, 89], "accent": [127, 173, 137]},
    "dirt": {"pattern": "noise", "color": [126, 105, 89]},
    "snow": {"pattern": "noise", "color": [236, 241, 243]},
    "snow_side": {"pattern": "grass_side", "color": [126, 105, 89], "accent": [236, 241, 243]},
    "stone": {"pattern": "specks", "color": [153, 151, 148]},
    "cobblestone": {"pattern": "cobble", "color": [130, 137, 137]},
    "bedrock": {"pattern": "specks", "color": [67, 72, 75]},
    "sand": {"pattern": "specks", "color": [222, 203, 158]},
    "gravel": {"pattern": "cobble", "color": [159, 166, 162]},
    "clay": {"pattern": "noise", "color": [166, 190, 192]},
    "brick": {"pattern": "bricks", "color": [184, 105, 86], "accent": [214, 200, 184]},
    "basalt": {"pattern": "rows", "color": [75, 83, 86]},
    "log_side": {"pattern": "log_side", "color": [139, 105, 82]},
    "log_top": {"pattern": "log_top", "color": [190, 160, 118], "accent": [139, 105, 82]},
    "planks": {"pattern": "planks", "color": [202, 171, 125]},
    "leaves": {"pattern": "leaves", "color": [101, 164, 128]},
    "coal_ore": {"pattern": "ore", "color": [153, 151, 148], "accent": [70, 74, 77]},
    "iron_ore": {"pattern": "ore", "color": [153, 151, 148], "accent": [201, 150, 116]},
    "copper_ore": {"pattern": "ore", "color": [153, 151, 148], "accent": [196, 122, 90]},
    "glass": {"pattern": "glass", "color": [160, 218, 218]},
    "water": {"pattern": "water", "color": [103, 179, 203]},
    "lava": {"pattern": "glow", "color": [244, 117, 57]},
    "wool": {"pattern": "noise", "color": [238, 226, 204]},
    "moss": {"pattern": "grass_top", "color": [85, 139, 100]},
    "lantern": {"pattern": "glow", "color": [247, 213, 143]},
    "crafting_table_top": {"pattern": "table_top", "color": [202, 171, 125], "accent": [120, 84, 52]},
    "crafting_table_side": {"pattern": "table_side", "color": [169, 117, 72], "accent": [202, 171, 125]},
    "furnace_top": {"pattern": "specks", "color": [110, 114, 112]},
    "furnace_side": {"pattern": "furnace_side", "color": [110, 114, 112], "accent": [247, 160, 90]},
    "limestone": {"pattern": "noise", "color": [227, 211, 181]},
    "polished_stone": {"pattern": "panel", "color": [169, 183, 178]},
    "dark_slate": {"pattern": "rows", "color": [82, 104, 111]},
    "plaster": {"pattern": "noise", "color": [229, 206, 171]},
    "roof_tile": {"pattern": "rows", "color": [193, 112, 100]},
    "dirt_path": {"pattern": "specks", "color": [215, 196, 159]},
    "hull_panel": {"pattern": "panel", "color": [189, 200, 198]},
    "solar_panel": {"pattern": "panel", "color": [91, 155, 171]},
    "brass": {"pattern": "panel", "color": [226, 192, 126]},
    "sandstone": {"pattern": "rows", "color": [245, 197, 151]},
    "verdigris": {"pattern": "noise", "color": [152, 192, 187]},
    "tall_grass": {"pattern": "sprite_grass", "color": [89, 147, 112]},
    "flower_orange": {"pattern": "sprite_flower", "color": [246, 192, 124], "accent": [90, 151, 113]},
    "flower_pink": {"pattern": "sprite_flower", "color": [243, 164, 168], "accent": [90, 151, 113]},
    "flower_yellow": {"pattern": "sprite_flower", "color": [250, 218, 139], "accent": [90, 151, 113]}
  },
  "blocks": [
    {"name": "air", "color": [0, 0, 0], "textures": "missing", "layer": "none", "solid": false, "replaceable": true, "drop": null},
    {"name": "grass", "color": [127, 173, 137], "textures": {"top": "grass_top", "side": "grass_side", "bottom": "dirt"}, "layer": "opaque", "solid": true, "drop": "dirt"},
    {"name": "snow", "color": [236, 241, 243], "textures": {"top": "snow", "side": "snow_side", "bottom": "dirt"}, "layer": "opaque", "solid": true, "drop": "dirt"},
    {"name": "dirt", "color": [126, 105, 89], "textures": "dirt", "layer": "opaque", "solid": true, "drop": "dirt"},
    {"name": "stone", "color": [153, 151, 148], "textures": "stone", "layer": "opaque", "solid": true, "drop": "cobblestone", "requires": "wooden_pickaxe"},
    {"name": "cobblestone", "color": [130, 137, 137], "textures": "cobblestone", "layer": "opaque", "solid": true, "drop": "cobblestone"},
    {"name": "bedrock", "color": [67, 72, 75], "textures": "bedrock", "layer": "opaque", "solid": true, "drop": null},
    {"name": "sand", "color": [222, 203, 158], "textures": "sand", "layer": "opaque", "solid": true, "drop": "sand", "gravity": true},
    {"name": "gravel", "color": [159, 166, 162], "textures": "gravel", "layer": "opaque", "solid": true, "drop": "gravel", "gravity": true},
    {"name": "clay", "color": [166, 190, 192], "textures": "clay", "layer": "opaque", "solid": true, "drop": "clay"},
    {"name": "brick", "color": [184, 105, 86], "textures": "brick", "layer": "opaque", "solid": true, "drop": "brick"},
    {"name": "basalt", "color": [75, 83, 86], "textures": "basalt", "layer": "opaque", "solid": true, "drop": "basalt"},
    {"name": "oak_log", "color": [139, 105, 82], "textures": {"top": "log_top", "side": "log_side", "bottom": "log_top"}, "layer": "opaque", "solid": true, "drop": "oak_log"},
    {"name": "planks", "color": [202, 171, 125], "textures": "planks", "layer": "opaque", "solid": true, "drop": "planks"},
    {"name": "leaves", "color": [101, 164, 128], "textures": "leaves", "layer": "opaque", "solid": true, "drop": null},
    {"name": "coal_ore", "color": [88, 94, 97], "textures": "coal_ore", "layer": "opaque", "solid": true, "drop": "coal", "requires": "wooden_pickaxe"},
    {"name": "iron_ore", "color": [182, 138, 107], "textures": "iron_ore", "layer": "opaque", "solid": true, "drop": "iron_ore", "requires": "stone_pickaxe"},
    {"name": "copper_ore", "color": [170, 116, 91], "textures": "copper_ore", "layer": "opaque", "solid": true, "drop": "copper_ore", "requires": "stone_pickaxe"},
    {"name": "glass", "color": [160, 218, 218], "textures": "glass", "layer": "translucent", "solid": true, "drop": "glass", "opacity": 0.38},
    {"name": "water", "color": [103, 179, 203], "textures": "water", "layer": "translucent", "solid": false, "replaceable": true, "drop": null, "opacity": 0.58, "fluid": true},
    {"name": "lava", "color": [244, 117, 57], "textures": "lava", "layer": "translucent", "solid": false, "drop": null, "opacity": 0.85, "fluid": true, "glow": true},
    {"name": "wool", "color": [238, 226, 204], "textures": "wool", "layer": "opaque", "solid": true, "drop": "wool"},
    {"name": "moss", "color": [85, 139, 100], "textures": "moss", "layer": "opaque", "solid": true, "drop": "moss"},
    {"name": "lantern", "color": [247, 213, 143], "textures": "lantern", "layer": "opaque", "solid": true, "drop": "lantern", "glow": true},
    {"name": "crafting_table", "color": [169, 117, 72], "textures": {"top": "crafting_table_top", "side": "crafting_table_side", "bottom": "planks"}, "layer": "opaque", "solid": true, "drop": "crafting_table"},
    {"name": "furnace", "color": [88, 91, 89], "textures": {"top": "furnace_top", "side": "furnace_side", "bottom": "furnace_top"}, "layer": "opaque", "solid": true, "drop": "furnace", "glow": true},
    {"name": "limestone", "color": [227, 211, 181], "textures": "limestone", "layer": "opaque", "solid": true, "drop": "limestone"},
    {"name": "polished_stone", "color": [169, 183, 178], "textures": "polished_stone", "layer": "opaque", "solid": true, "drop": "polished_stone"},
    {"name": "dark_slate", "color": [82, 104, 111], "textures": "dark_slate", "layer": "opaque", "solid": true, "drop": "dark_slate"},
    {"name": "plaster", "color": [229, 206, 171], "textures": "plaster", "layer": "opaque", "solid": true, "drop": "plaster"},
    {"name": "roof_tile", "color": [193, 112, 100], "textures": "roof_tile", "layer": "opaque", "solid": true, "drop": "roof_tile"},
    {"name": "dirt_path", "color": [215, 196, 159], "textures": {"top": "dirt_path", "side": "dirt", "bottom": "dirt"}, "layer": "opaque", "solid": true, "drop": "dirt"},
    {"name": "hull_panel", "color": [189, 200, 198], "textures": "hull_panel", "layer": "opaque", "solid": true, "drop": "hull_panel"},
    {"name": "solar_panel", "color": [91, 155, 171], "textures": "solar_panel", "layer": "opaque", "solid": true, "drop": "solar_panel"},
    {"name": "brass", "color": [226, 192, 126], "textures": "brass", "layer": "opaque", "solid": true, "drop": "brass"},
    {"name": "sandstone", "color": [245, 197, 151], "textures": "sandstone", "layer": "opaque", "solid": true, "drop": "sandstone"},
    {"name": "verdigris", "color": [152, 192, 187], "textures": "verdigris", "layer": "opaque", "solid": true, "drop": "verdigris"},
    {"name": "tall_grass", "color": [89, 147, 112], "textures": "tall_grass", "layer": "cutout", "solid": false, "replaceable": true, "drop": null},
    {"name": "flower_orange", "color": [246, 192, 124], "textures": "flower_orange", "layer": "cutout", "solid": false, "replaceable": true, "drop": "flower_orange"},
    {"name": "flower_pink", "color": [243, 164, 168], "textures": "flower_pink", "layer": "cutout", "solid": false, "replaceable": true, "drop": "flower_pink"},
    {"name": "flower_yellow", "color": [250, 218, 139], "textures": "flower_yellow", "layer": "cutout", "solid": false, "replaceable": true, "drop": "flower_yellow"}
  ]
}
```

- [ ] **Step 4: Create the Python loader**

Create `backend/services/blocks.py`:

```python
"""Block registry shared with the viewer.

shared/blocks.json is the single list of blocks. The viewer turns each entry into a
texture and a numeric id (its index); the server uses the same names and properties.
"""

from __future__ import annotations

import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "shared" / "blocks.json"
_REGISTRY = json.loads(REGISTRY_PATH.read_text())

TILES: dict[str, dict] = _REGISTRY["tiles"]
BLOCK_LIST: list[dict] = _REGISTRY["blocks"]
BLOCK_IDS: dict[str, int] = {block["name"]: index for index, block in enumerate(BLOCK_LIST)}
_RENDER_KEYS = {"name", "textures", "layer", "solid", "replaceable"}

# Gameplay properties keyed by name, in the shape crafting.BLOCKS has always had.
BLOCK_PROPERTIES: dict[str, dict] = {
    block["name"]: {key: value for key, value in block.items() if key not in _RENDER_KEYS}
    for block in BLOCK_LIST if block["name"] != "air"
}


def is_replaceable(material: str) -> bool:
    """True for cells a placed or falling block may take over: air, water and plants."""
    index = BLOCK_IDS.get(material)
    return index is not None and bool(BLOCK_LIST[index].get("replaceable"))
```

In `backend/services/crafting.py`, replace the whole `BLOCKS = { ... }` literal (lines 7–33) with:

```python
from backend.services.blocks import BLOCK_PROPERTIES

# Block properties live in shared/blocks.json so the viewer uses the same list.
BLOCKS = BLOCK_PROPERTIES
```

Keep the existing `from copy import deepcopy` import above it. Put the new import directly after `from copy import deepcopy`.

- [ ] **Step 5: Copy `shared/` into the Docker image**

In `backend/Dockerfile`, add this line directly before `COPY backend /app/backend`:

```dockerfile
COPY shared /app/shared
```

- [ ] **Step 6: Update the spec's registry description**

In `docs/superpowers/specs/2026-09-22-voxel-engine-soft-pixel-design.md`, replace the paragraph that starts with "`shared/blocks.json` is an ordered array." with:

```markdown
`shared/blocks.json` has two keys. `tiles` maps a tile name to a texture recipe: a `pattern` name, a base `color` and an optional `accent` color. `blocks` is an ordered array. The array index is the numeric block id used on the client. Id 0 is `air`. The list is append-only: never reorder or remove an entry, only mark it unused. The server keeps storing material names, so ids never reach the database.
```

Also change the sentence "`textures` names recipes in the atlas." to "`textures` names tiles from `tiles`."

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests`
Expected: all tests pass, including the 5 new ones (26 total).

- [ ] **Step 8: Commit**

```bash
git add shared/blocks.json backend/services/blocks.py backend/services/crafting.py backend/Dockerfile backend/tests/test_blocks.py
git add -f docs/superpowers/specs/2026-09-22-voxel-engine-soft-pixel-design.md
git commit -m "feat: move block catalog into shared registry" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Frontend test setup and TypeScript registry

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.app.json`
- Create: `frontend/src/engine/blocks.ts`
- Test: `frontend/src/engine/blocks.test.ts`

**Interfaces:**
- Consumes: `shared/blocks.json` from Task 1.
- Produces: `type Layer`, `type Rgb`, `interface TileRecipe`, `interface BlockDef { id, name, color, layer, solid, textures: {top, side, bottom}, glow, fluid }`, `AIR = 0`, `MISSING_ID = 255`, `MISSING: BlockDef`, `TILES`, `BLOCKS: BlockDef[]`, `blockId(name): number`, `hasBlock(name): boolean`, `blockDef(id): BlockDef`, `LAYER_NONE/OPAQUE/CUTOUT/TRANSLUCENT = 0/1/2/3`, `LAYER_BY_ID`, `GLOW_BY_ID`, `FLUID_BY_ID` (each `Uint8Array(256)`).

- [ ] **Step 1: Install dependencies and add Vitest**

```bash
cd frontend && npm ci && npm install --save-dev vitest@^5.0.1
```

In `frontend/package.json`, add to `"scripts"`:

```json
"test": "vitest run"
```

Replace `frontend/vite.config.ts` with:

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: '..',
  // shared/ sits beside frontend/ and holds the block registry and worldgen fixture.
  server: { fs: { allow: ['..'] } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
```

In `frontend/tsconfig.app.json`, add `"resolveJsonModule": true,` directly after `"moduleDetection": "force",`.

- [ ] **Step 2: Write the failing test**

Create `frontend/src/engine/blocks.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest'
import {
  AIR, BLOCKS, FLUID_BY_ID, GLOW_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
  MISSING_ID, TILES, blockDef, blockId, hasBlock,
} from './blocks'

describe('block registry', () => {
  it('puts air at id 0 and keeps ids below the missing id', () => {
    expect(blockId('air')).toBe(AIR)
    expect(BLOCKS.length).toBeLessThan(MISSING_ID)
    BLOCKS.forEach((block, index) => expect(block.id).toBe(index))
  })

  it('expands a single texture name to every face', () => {
    const stone = blockDef(blockId('stone'))
    expect(stone.textures).toEqual({ top: 'stone', side: 'stone', bottom: 'stone' })
    expect(blockDef(blockId('grass')).textures.side).toBe('grass_side')
  })

  it('uses only tiles that exist', () => {
    for (const block of BLOCKS) {
      for (const tile of Object.values(block.textures)) expect(TILES[tile], `${block.name} → ${tile}`).toBeDefined()
    }
  })

  it('maps unknown names to the missing block and warns once', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(blockId('unobtainium')).toBe(MISSING_ID)
    expect(blockId('unobtainium')).toBe(MISSING_ID)
    expect(warn).toHaveBeenCalledTimes(1)
    expect(hasBlock('unobtainium')).toBe(false)
    expect(blockDef(MISSING_ID).layer).toBe('opaque')
    warn.mockRestore()
  })

  it('fills per-id lookup tables', () => {
    expect(LAYER_BY_ID[blockId('stone')]).toBe(LAYER_OPAQUE)
    expect(LAYER_BY_ID[blockId('water')]).toBe(LAYER_TRANSLUCENT)
    expect(LAYER_BY_ID[blockId('flower_pink')]).toBe(LAYER_CUTOUT)
    expect(LAYER_BY_ID[AIR]).toBe(0)
    expect(GLOW_BY_ID[blockId('lantern')]).toBe(1)
    expect(FLUID_BY_ID[blockId('water')]).toBe(1)
    expect(LAYER_BY_ID[MISSING_ID]).toBe(LAYER_OPAQUE)
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/engine/blocks.test.ts`
Expected: FAIL with `Failed to resolve import "./blocks"`

- [ ] **Step 4: Write the registry module**

Create `frontend/src/engine/blocks.ts`:

```ts
import registry from '../../../shared/blocks.json'

export type Layer = 'opaque' | 'cutout' | 'translucent' | 'none'
export type Rgb = [number, number, number]

export interface TileRecipe {
  pattern: string
  color: Rgb
  accent?: Rgb
}

export interface FaceTextures {
  top: string
  side: string
  bottom: string
}

export interface BlockDef {
  id: number
  name: string
  color: Rgb
  layer: Layer
  solid: boolean
  textures: FaceTextures
  glow: boolean
  fluid: boolean
}

interface RawBlock {
  name: string
  color: number[]
  textures: string | FaceTextures
  layer: Layer
  solid: boolean
  glow?: boolean
  fluid?: boolean
}

export const AIR = 0
/** Client-only id for material names the registry does not know. */
export const MISSING_ID = 255

export const TILES = registry.tiles as unknown as Record<string, TileRecipe>

function toDef(raw: RawBlock, id: number): BlockDef {
  const textures = typeof raw.textures === 'string'
    ? { top: raw.textures, side: raw.textures, bottom: raw.textures }
    : raw.textures
  return {
    id, name: raw.name, color: [raw.color[0], raw.color[1], raw.color[2]], layer: raw.layer,
    solid: raw.solid, textures, glow: Boolean(raw.glow), fluid: Boolean(raw.fluid),
  }
}

const rawBlocks = registry.blocks as unknown as RawBlock[]
if (rawBlocks.length >= MISSING_ID) throw new Error('Block registry is full; ids must stay below 255')

export const BLOCKS: BlockDef[] = rawBlocks.map(toDef)
export const MISSING: BlockDef = {
  id: MISSING_ID, name: 'missing', color: [255, 0, 255], layer: 'opaque', solid: true,
  textures: { top: 'missing', side: 'missing', bottom: 'missing' }, glow: false, fluid: false,
}

const ids = new Map(BLOCKS.map((block) => [block.name, block.id]))
const warned = new Set<string>()

export function blockId(name: string): number {
  const id = ids.get(name)
  if (id !== undefined) return id
  if (!warned.has(name)) {
    warned.add(name)
    console.warn(`Unknown block "${name}" is shown with the missing texture`)
  }
  return MISSING_ID
}

export function hasBlock(name: string): boolean {
  return ids.has(name)
}

export function blockDef(id: number): BlockDef {
  return BLOCKS[id] ?? MISSING
}

export const LAYER_NONE = 0
export const LAYER_OPAQUE = 1
export const LAYER_CUTOUT = 2
export const LAYER_TRANSLUCENT = 3
const LAYER_CODES: Record<Layer, number> = {
  none: LAYER_NONE, opaque: LAYER_OPAQUE, cutout: LAYER_CUTOUT, translucent: LAYER_TRANSLUCENT,
}

// Flat tables so the mesher never looks up objects in its inner loop.
export const LAYER_BY_ID = new Uint8Array(256)
export const GLOW_BY_ID = new Uint8Array(256)
export const FLUID_BY_ID = new Uint8Array(256)
for (let id = 0; id < 256; id++) {
  const def = blockDef(id)
  LAYER_BY_ID[id] = LAYER_CODES[def.layer]
  GLOW_BY_ID[id] = def.glow ? 1 : 0
  FLUID_BY_ID[id] = def.fluid ? 1 : 0
}
```

- [ ] **Step 5: Run tests and the build**

Run: `cd frontend && npm test && npm run build`
Expected: 5 tests pass; build succeeds. If `tsc -b` rejects the JSON import because it is outside `include`, add `"../shared/*.json"` to the `include` array in `tsconfig.app.json` and rerun.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/tsconfig.app.json frontend/src/engine/blocks.ts frontend/src/engine/blocks.test.ts
git commit -m "feat: add Vitest and TypeScript block registry" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Python worldgen owns trees, plants and the home clearing

**Files:**
- Modify: `backend/services/worldgen.py`
- Modify: `backend/services/live_mimo.py` (imports, `put_block`, `step_loose_blocks`, `owner_action`, `observe_world`, place validation in `run_tick`)
- Test: `backend/tests/test_worldgen.py`, `backend/tests/test_live_mimo.py`

**Interfaces:**
- Consumes: `is_replaceable` from Task 1.
- Produces (in `backend.services.worldgen`): `WORLD_MIN_Y = -8`, `WORLD_MAX_Y = 119`, `legacy_hash(x, z) -> int`, `home_ground(x, y, z) -> str | None`, `HOME_BLOCKS: dict[tuple[int, int, int], str]`, `terrain_block(x, y, z, seed) -> str`, `tree_base(x, z, seed) -> int | None`, `trees_in_chunk(cx, cz, seed) -> tuple[tuple[int, int, int], ...]`, `is_leaf(dx, dy, dz) -> bool`, `plant_at(x, z, seed) -> str | None`, `decoration_at(x, y, z, seed) -> str | None`, `block_at(x, y, z, seed) -> str`, and `base_material` as an alias of `block_at`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_worldgen.py`, and extend its import to:

```python
from backend.services.worldgen import (
    LEGACY_WORLD_SEED, base_material, biome_at, block_at, cave_at, hash32, legacy_hash, plant_at,
    surface_material, terrain_height, trees_in_chunk,
)
```

```python
class NaturalBlockTests(unittest.TestCase):
    def test_home_clearing_matches_what_the_viewer_always_drew(self):
        seed = LEGACY_WORLD_SEED
        expected = {
            (5, 0, -4): "dirt_path",      # cottage floor
            (4, 1, -4): "plaster",        # cottage wall
            (5, 1, -3): "air",            # doorway
            (5, 2, -6): "glass",          # window
            (3, 4, -7): "roof_tile",
            (-6, 3, -4): "oak_log",       # big tree trunk
            (-6, 5, -4): "oak_log",       # trunk wins over canopy
            (-7, 5, -4): "leaves",
            (-6, 7, -4): "leaves",
            (-8, 1, 0): "flower_orange",
            (-5, 0, 4): "water",          # pond
            (-3, 0, 2): "dirt_path",      # stepping stone
            (3, 0, -2): "dirt_path",      # walkway
            (0, -1, 0): "dirt",
        }
        for (x, y, z), material in expected.items():
            self.assertEqual(block_at(x, y, z, seed), material, (x, y, z))

    def test_javascript_hash_is_reproduced(self):
        # Values from the viewer: Math.abs((x * 73856093) ^ (z * 19349663)).
        self.assertEqual(legacy_hash(0, 0), 0)
        self.assertEqual(legacy_hash(1, 0), 73856093)
        self.assertEqual(legacy_hash(100, 100), 882750904)  # 100 * 73856093 overflows int32
        self.assertEqual(legacy_hash(-7, 3), 497381208)

    def test_generated_trees_have_trunk_and_canopy_inside_their_chunk(self):
        seed = "123456789123456789"
        trees = [tree for cx in range(20, 40) for cz in range(-10, 10) for tree in trees_in_chunk(cx, cz, seed)]
        self.assertGreater(len(trees), 5)
        for tx, tz, _ in trees:
            self.assertTrue(3 <= tx % 16 <= 12 and 3 <= tz % 16 <= 12)
        x, z, base = trees[0]
        self.assertEqual([block_at(x, base + dy, z, seed) for dy in range(1, 7)],
                         ["oak_log"] * 4 + ["leaves", "leaves"])
        if terrain_height(x + 1, z, seed) < base + 5:
            self.assertEqual(block_at(x + 1, base + 5, z, seed), "leaves")

    def test_plants_grow_on_open_grass_only(self):
        seed = "123456789123456789"
        found = {}
        for x in range(300, 460):
            for z in range(-80, 80):
                plant = plant_at(x, z, seed)
                if plant:
                    found.setdefault(plant, (x, z))
                    self.assertIn(surface_material(x, z, seed), ("grass", "moss"))
        self.assertIn("tall_grass", found)
        x, z = found["tall_grass"]
        self.assertEqual(block_at(x, terrain_height(x, z, seed) + 1, z, seed), "tall_grass")
        self.assertIsNone(plant_at(0, 0, seed))
        self.assertIs(base_material, block_at)
```

The two literals come from JavaScript: `node -e "console.log(Math.abs((100 * 73856093) ^ (100 * 19349663)), Math.abs((-7 * 73856093) ^ (3 * 19349663)))"` prints `882750904 497381208`.

Append to `LiveMimoTests` in `backend/tests/test_live_mimo.py` (add `from backend.services.worldgen import terrain_height` to the imports):

```python
    def test_sand_falls_through_plants(self):
        height = terrain_height(80, 0, self.store.world_seed)
        self.store.put_block(80, height + 1, 0, "tall_grass")
        self.store.put_block(80, height + 2, 0, "sand")
        self.assertEqual(self.store.step_loose_blocks(), 1)
        self.assertEqual(self.store.material_at(80, height + 1, 0), "sand")

    def test_block_heights_match_the_viewer_world(self):
        self.store.put_block(90, 119, 0, "stone")
        with self.assertRaises(ValueError):
            self.store.put_block(90, 120, 0, "stone")
        with self.assertRaises(ValueError):
            self.store.put_block(90, -9, 0, "stone")

    def test_observation_columns_reach_tree_canopies(self):
        state = self.store.snapshot()
        column = observe_world(state)["nearby_columns"][0]
        top = max(3, terrain_height(column["x"], column["z"], state["world_seed"]) + 7)
        self.assertEqual(column["layers"][0]["y"], top)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_worldgen backend.tests.test_live_mimo -v`
Expected: FAIL with `ImportError: cannot import name 'block_at'`

- [ ] **Step 3: Add the natural blocks to Python worldgen**

In `backend/services/worldgen.py`:

1. After `MASK = 0xFFFFFFFF`, add:

```python
WORLD_MIN_Y = -8
WORLD_MAX_Y = 119
HOME_RADIUS = 12
STEPPING_STONES = {(-3, 2), (-2, 1), (3, 2), (4, 1)}
HOME_FLOWERS = ((-8, 0, "flower_orange"), (-7, 1, "flower_pink"), (-2, -5, "flower_yellow"),
                (1, -6, "flower_pink"), (8, 1, "flower_orange"), (7, 5, "flower_yellow"),
                (-1, 7, "flower_pink"), (3, 7, "flower_orange"))
```

2. After `lerp`, add:

```python
def to_int32(value: int) -> int:
    value &= MASK
    return value - (1 << 32) if value >= 1 << 31 else value


def legacy_hash(x: int, z: int) -> int:
    """The viewer's `Math.abs((x * 73856093) ^ (z * 19349663))`, with JavaScript's int32 XOR."""
    return abs(to_int32(x * 73856093) ^ to_int32(z * 19349663))


def js_round(value: float) -> int:
    """JavaScript Math.round: halves round up, unlike Python's round()."""
    return math.floor(value + 0.5)
```

3. Rename `def base_material(` to `def terrain_block(`, change its docstring-free body so the legacy branch checks the home island first, and add everything below it. The full replacement for the old `base_material` function is:

```python
def in_pond(x: int, z: int) -> bool:
    return ((x + 5) / 3.2) ** 2 + ((z - 4) / 2.4) ** 2 < 1


def home_ground(x: int, y: int, z: int) -> str | None:
    """Ground of Mimo's original home island, or None outside it."""
    distance = math.hypot(x, z)
    if distance > 10.4 + (legacy_hash(x, z) % 5) * 0.16:
        return None
    if y == 0:
        if 4 <= x <= 7 and -6 <= z <= -3:
            return "dirt_path"
        if (x, z) in STEPPING_STONES:
            return "dirt_path"
        if in_pond(x, z):
            return "water"
        shore = ((x + 5) / 4.2) ** 2 + ((z - 4) / 3.4) ** 2 < 1
        if shore or distance > 9.3:
            return "sand"
        walkway = 0 <= x <= 6 and abs(z + js_round(x * 0.55)) <= 0.6
        return "dirt_path" if walkway else "grass"
    if y == -1:
        return "sand" if distance > 9 else "dirt"
    if y == -2 and distance < 9.1:
        return "dirt"
    return None


def _home_blocks() -> dict[tuple[int, int, int], str]:
    """The cottage, big tree and flowers that used to exist only in the viewer."""
    blocks: dict[tuple[int, int, int], str] = {}
    for x in range(4, 8):
        for z in range(-6, -2):
            for y in range(1, 4):
                wall = x in (4, 7) or z in (-6, -3)
                door = x == 5 and z == -3 and y <= 2
                if wall and not door:
                    blocks[(x, y, z)] = "plaster"
    blocks[(5, 2, -6)] = "glass"
    blocks[(6, 2, -6)] = "glass"
    for x in range(3, 9):
        for z in range(-7, -1):
            blocks[(x, 4, z)] = "roof_tile"
            if 3 < x < 8 and -7 < z < -2:
                blocks[(x, 5, z)] = "roof_tile"
    for x in range(-8, -3):
        for z in range(-6, -1):
            spread = abs(x + 6) + abs(z + 4)
            if spread > 3:
                continue
            blocks[(x, 5, z)] = "leaves"
            if spread <= 2:
                blocks[(x, 6, z)] = "leaves"
    blocks[(-6, 7, -4)] = "leaves"
    for y in range(1, 6):
        blocks[(-6, y, -4)] = "oak_log"
    for x, z, flower in HOME_FLOWERS:
        blocks[(x, 1, z)] = flower
    return blocks


HOME_BLOCKS = _home_blocks()


def terrain_block(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """Terrain, water, caves and ores, before trees and plants are added."""
    if y <= -5:
        return "bedrock"
    height = terrain_height(x, z, seed)
    if math.hypot(x, z) <= LEGACY_RADIUS:
        home = home_ground(x, y, z)
        if home:
            return home
        if -4 <= y < -1:
            ore_seed = abs(x * 31 + z * 17 + y * 101)
            return "iron_ore" if ore_seed % 37 == 0 else "coal_ore" if ore_seed % 19 == 0 else "stone"
        if y == -1:
            return "dirt"
        if y == 0 and in_pond(x, z):
            return "water"
        if y == height:
            return "grass"
        if 0 <= y < height:
            return "dirt" if y >= height - 1 else "stone"
        return "air"
    if y > height:
        return "water" if y <= SEA_LEVEL else "air"
    if y == height:
        return surface_material(x, z, seed)
    if y >= height - 2:
        return "sand" if biome_at(x, z, seed) == "desert" else "dirt"
    if cave_at(x, y, z, seed):
        return "air"
    ore = hash32(x, y, z, seed, 9)
    if ore % 97 == 0:
        return "iron_ore"
    if ore % 61 == 0:
        return "coal_ore"
    if ore % 151 == 0:
        return "copper_ore"
    return "stone"


def _decoration_column(x: int, z: int, seed: str) -> bool:
    """Columns where the viewer has always allowed trees and flowers."""
    if not (3 <= x % 16 <= 12 and 3 <= z % 16 <= 12) or math.hypot(x, z) < 17:
        return False
    if terrain_height(x, z, seed) < SEA_LEVEL or biome_at(x, z, seed) in ("desert", "alpine"):
        return False
    mx, mz = x % 13, z % 13
    return not (min(mx, 13 - mx) < 5 and min(mz, 13 - mz) < 5)


def tree_base(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> int | None:
    """Ground height under a tree trunk at (x, z), or None when no tree grows there."""
    if not _decoration_column(x, z, seed):
        return None
    if math.hypot(x, z) <= LEGACY_RADIUS:
        grows = legacy_hash(x, z) % 257 == 0
    else:
        grows = hash32(x, 0, z, seed, 12) % (78 if biome_at(x, z, seed) == "forest" else 300) == 0
    return terrain_height(x, z, seed) if grows else None


@lru_cache(maxsize=4096)
def trees_in_chunk(cx: int, cz: int, seed: str = LEGACY_WORLD_SEED) -> tuple[tuple[int, int, int], ...]:
    """(x, z, ground height) of every tree rooted in a 16×16 chunk. Canopies never leave the chunk."""
    trees = []
    for x in range(cx * 16 + 3, cx * 16 + 13):
        for z in range(cz * 16 + 3, cz * 16 + 13):
            base = tree_base(x, z, seed)
            if base is not None:
                trees.append((x, z, base))
    return tuple(trees)


def is_leaf(dx: int, dy: int, dz: int) -> bool:
    """Canopy shape relative to a trunk's ground cell; dy counts up from the ground."""
    dx, dz = abs(dx), abs(dz)
    if dy == 5:
        return dx <= 2 and dz <= 2 and dx + dz <= 3
    return dy == 6 and dx + dz < 2


def tree_block(x: int, y: int, z: int, seed: str) -> str | None:
    trees = trees_in_chunk(x // 16, z // 16, seed)
    if any(x == tx and z == tz and base < y <= base + 4 for tx, tz, base in trees):
        return "oak_log"
    if any(is_leaf(x - tx, y - base, z - tz) for tx, tz, base in trees):
        return "leaves"
    return None


def plant_at(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """Flower or tall grass growing on top of the terrain at (x, z)."""
    if math.hypot(x, z) <= HOME_RADIUS:
        return None
    if _decoration_column(x, z, seed):
        if tree_base(x, z, seed) is not None:
            return None
        if hash32(x, 0, z, seed, 13) % 97 == 0:
            return "flower_orange" if legacy_hash(x + 1, z) % 2 else "flower_yellow"
    if math.hypot(x, z) > LEGACY_RADIUS and terrain_height(x, z, seed) < SEA_LEVEL:
        return None
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


def block_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """The natural block at any cell: terrain first, then decorations in air."""
    terrain = terrain_block(x, y, z, seed)
    if terrain != "air":
        return terrain
    return decoration_at(x, y, z, seed) or "air"


# Older callers use this name.
base_material = block_at
```

Delete the old `base_material` function body; the alias above replaces it.

- [ ] **Step 4: Update the server to use replaceable cells and the new height range**

In `backend/services/live_mimo.py`:

1. Change the imports:

```python
from backend.services.blocks import is_replaceable
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, SEA_LEVEL, WORLD_MAX_Y, WORLD_MIN_Y, base_material, terrain_height,
)
```

2. In `put_block`, change `not (-8 <= y <= 128)` to `not (WORLD_MIN_Y <= y <= WORLD_MAX_Y)`.

3. In `step_loose_blocks`, change `if below not in ("air", "water") or y <= -5:` to `if not is_replaceable(below) or y <= -5:`.

4. In `owner_action`, replace

```python
                    if (row_at["material"] if row_at else base_material(x, y, z, self.world_seed)) == "air":
```

with

```python
                    here = row_at["material"] if row_at else base_material(x, y, z, self.world_seed)
                    if is_replaceable(here) and here != "water":
```

5. In `observe_world`, change `top = max(3, terrain_height(x, z, seed) + 3)` to `top = max(3, terrain_height(x, z, seed) + 7)`.

6. In `run_tick`, change `if choice["action"] == "place" and existing not in ("air", "water"):` to `if choice["action"] == "place" and not is_replaceable(existing):`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests`
Expected: all tests pass (33 total).

- [ ] **Step 6: Commit**

```bash
git add backend/services/worldgen.py backend/services/live_mimo.py backend/tests/test_worldgen.py backend/tests/test_live_mimo.py
git commit -m "feat: make trees, plants and home cottage real server blocks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Worldgen parity fixture

**Files:**
- Create: `backend/scripts/__init__.py` (empty)
- Create: `backend/scripts/worldgen_fixture.py`
- Create (generated): `shared/worldgen-fixture.json`
- Test: `backend/tests/test_worldgen.py`

**Interfaces:**
- Consumes: `block_at`, `trees_in_chunk`, `plant_at`, `biome_at`, `terrain_height` from Task 3.
- Produces: `backend.scripts.worldgen_fixture.build_fixture() -> dict`, `FIXTURE_PATH`, and the JSON file `{"seeds": [str, str], "materials": [str], "cells": [[seedIndex, x, y, z, materialIndex]]}`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_worldgen.py` (add `import json` at the top and `from backend.scripts.worldgen_fixture import FIXTURE_PATH, build_fixture` to the imports):

```python
class FixtureTests(unittest.TestCase):
    def test_shared_fixture_matches_python_worldgen(self):
        saved = json.loads(FIXTURE_PATH.read_text())
        self.assertTrue(build_fixture() == saved,
                        "Worldgen output changed. Run: python3 -m backend.scripts.worldgen_fixture")

    def test_fixture_covers_every_natural_feature(self):
        materials = set(json.loads(FIXTURE_PATH.read_text())["materials"])
        for name in ("oak_log", "leaves", "tall_grass", "plaster", "roof_tile", "dirt_path",
                     "water", "sand", "stone", "bedrock", "grass"):
            self.assertIn(name, materials)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest backend.tests.test_worldgen -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.scripts'`

- [ ] **Step 3: Write the fixture builder**

Create an empty `backend/scripts/__init__.py`, then create `backend/scripts/worldgen_fixture.py`:

```python
"""Write shared/worldgen-fixture.json: sampled cells both worldgen ports must agree on.

Run from the repo root after any worldgen change:

    python3 -m backend.scripts.worldgen_fixture
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from backend.services.worldgen import (
    LEGACY_WORLD_SEED, biome_at, block_at, plant_at, terrain_height, trees_in_chunk,
)

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "shared" / "worldgen-fixture.json"
GENERATED_SEED = "123456789123456789"
SEEDS = [LEGACY_WORLD_SEED, GENERATED_SEED]
LEGACY_CHUNKS = [(cx, cz) for cz in range(2, 12) for cx in range(2, 12)]
WILD_CHUNKS = [(cx, cz) for cz in range(-15, 15) for cx in range(16, 46)]


def _trees(seed: str, chunks: list[tuple[int, int]], count: int,
           biome: str | None = None) -> list[tuple[int, int, int]]:
    found = []
    for cx, cz in chunks:
        for tree in trees_in_chunk(cx, cz, seed):
            if biome is None or biome_at(tree[0], tree[1], seed) == biome:
                found.append(tree)
                if len(found) == count:
                    return found
    return found


def _plants(seed: str, count: int) -> list[tuple[int, int]]:
    found = []
    for x in range(250, 900):
        for z in range(-40, 40, 3):
            if plant_at(x, z, seed):
                found.append((x, z))
                if len(found) == count:
                    return found
    return found


def _biome_patch(seed: str, biome: str) -> list[tuple[int, int, int]]:
    for x in range(250, 1250, 25):
        for z in range(-500, 500, 25):
            if biome_at(x, z, seed) == biome:
                return [(x + dx, y, z + dz) for dx in range(4) for dz in range(4)
                        for y in range(terrain_height(x + dx, z + dz, seed) - 2,
                                       terrain_height(x + dx, z + dz, seed) + 2)]
    return []


def sample_cells() -> list[tuple[str, int, int, int]]:
    """Home clearing, tree canopies, plants, rare biomes and random cells for both seeds."""
    cells = {(LEGACY_WORLD_SEED, x, y, z) for x in range(-12, 13) for z in range(-12, 13) for y in range(-2, 8)}
    rng = random.Random(7)
    for seed in SEEDS:
        trees = _trees(seed, LEGACY_CHUNKS, 3) + _trees(seed, WILD_CHUNKS, 3, "forest")
        for tx, tz, base in trees:
            cells |= {(seed, tx + dx, base + dy, tz + dz)
                      for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 8)}
        for x, z in _plants(seed, 20):
            height = terrain_height(x, z, seed)
            cells |= {(seed, x, height, z), (seed, x, height + 1, z)}
        for biome in ("desert", "alpine"):
            cells |= {(seed, x, y, z) for x, y, z in _biome_patch(seed, biome)}
        for _ in range(1500):
            cells.add((seed, rng.randint(-700, 700), rng.randint(-8, 40), rng.randint(-700, 700)))
    return sorted(cells, key=lambda cell: (SEEDS.index(cell[0]), cell[1], cell[2], cell[3]))


def build_fixture() -> dict:
    cells = sample_cells()
    names = [block_at(x, y, z, seed) for seed, x, y, z in cells]
    materials = sorted(set(names))
    index = {name: position for position, name in enumerate(materials)}
    return {
        "seeds": SEEDS,
        "materials": materials,
        "cells": [[SEEDS.index(seed), x, y, z, index[name]] for (seed, x, y, z), name in zip(cells, names)],
    }


def main() -> None:
    fixture = build_fixture()
    FIXTURE_PATH.write_text(json.dumps(fixture, separators=(",", ":")) + "\n")
    print(f"Wrote {len(fixture['cells'])} cells to {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Generate the fixture**

Run: `python3 -m backend.scripts.worldgen_fixture`
Expected: `Wrote 13… cells to …/shared/worldgen-fixture.json` (about 14,000 cells, about 220 KB).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests`
Expected: all tests pass (35 total). The fixture test takes a few seconds.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/__init__.py backend/scripts/worldgen_fixture.py shared/worldgen-fixture.json backend/tests/test_worldgen.py
git commit -m "test: add worldgen parity fixture shared with the viewer" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: TypeScript worldgen port with column generation

**Files:**
- Move: `frontend/src/components/world/worldgen.ts` → `frontend/src/engine/worldgen.ts`
- Modify: `frontend/src/components/world/expandingWorld.ts:4,6` (import path and name)
- Modify: `frontend/src/components/world/worldPlanner.ts:8` (import path)
- Modify: `frontend/src/pages/WorldPreview.tsx:12` (import path)
- Test: `frontend/src/engine/worldgen.test.ts`

**Interfaces:**
- Consumes: `AIR`, `blockId` from Task 2; `shared/worldgen-fixture.json` from Task 4.
- Produces (in `engine/worldgen.ts`): everything the old file exported (`DEFAULT_WORLD_SEED`, `LEGACY_RADIUS`, `SEA_LEVEL`, `hash32`, `terrainHeight`, `biomeAt`, `surfaceMaterial`, `caveAt`) plus `CHUNK_SIZE = 16`, `WORLD_MIN_Y = -8`, `WORLD_HEIGHT = 128`, `WORLD_MAX_Y = 119`, `legacyHash(x, z)`, `terrainBlock(x, y, z, seed): string`, `treeBase(x, z, seed): number | null`, `treesInChunk(cx, cz, seed): [number, number, number][]`, `plantAt(x, z, seed): string | null`, `blockAt(x, y, z, seed): string`, `columnIndex(lx, y, lz): number`, `generateColumn(cx, cz, seed): Uint8Array`. `baseMaterial` is removed.

- [ ] **Step 1: Move the file and fix imports**

```bash
git mv frontend/src/components/world/worldgen.ts frontend/src/engine/worldgen.ts
```

- In `expandingWorld.ts`, change line 4 to `import { blockAt as baseMaterial, biomeAt, DEFAULT_WORLD_SEED, hash32, LEGACY_RADIUS, SEA_LEVEL, surfaceMaterial, terrainHeight } from '../../engine/worldgen'` and line 6 to `export { terrainHeight } from '../../engine/worldgen'`.
- In `worldPlanner.ts`, change line 8 to `import { DEFAULT_WORLD_SEED } from '../../engine/worldgen'`.
- In `WorldPreview.tsx`, change line 12 to `import { DEFAULT_WORLD_SEED, terrainHeight } from '../engine/worldgen'`.

Run `grep -rn "world/worldgen'" frontend/src` and confirm there are no other importers.

- [ ] **Step 2: Write the failing test**

Create `frontend/src/engine/worldgen.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import fixture from '../../../shared/worldgen-fixture.json'
import { blockDef, blockId } from './blocks'
import {
  blockAt, columnIndex, DEFAULT_WORLD_SEED, generateColumn, legacyHash, treesInChunk, WORLD_MAX_Y, WORLD_MIN_Y,
} from './worldgen'

const WILD_SEED = '123456789123456789'

function columnMismatches(cx: number, cz: number, seed: string): string[] {
  const data = generateColumn(cx, cz, seed)
  const mismatches: string[] = []
  for (let lx = 0; lx < 16; lx++) for (let lz = 0; lz < 16; lz++) {
    for (let y = WORLD_MIN_Y; y <= WORLD_MAX_Y; y++) {
      const expected = blockAt(cx * 16 + lx, y, cz * 16 + lz, seed)
      const actual = blockDef(data[columnIndex(lx, y, lz)]).name
      if (actual !== expected) mismatches.push(`(${cx * 16 + lx}, ${y}, ${cz * 16 + lz}) ${expected} vs ${actual}`)
    }
  }
  return mismatches
}

describe('worldgen', () => {
  it('matches every cell the Python worldgen wrote to the shared fixture', () => {
    const mismatches: string[] = []
    for (const [seedIndex, x, y, z, material] of fixture.cells) {
      const seed = fixture.seeds[seedIndex]
      const expected = fixture.materials[material]
      const actual = blockAt(x, y, z, seed)
      if (actual !== expected) mismatches.push(`seed ${seed} (${x}, ${y}, ${z}): expected ${expected}, got ${actual}`)
    }
    expect(mismatches.slice(0, 20)).toEqual([])
  })

  it('reproduces the legacy hash', () => {
    expect(legacyHash(1, 0)).toBe(73856093)
    expect(legacyHash(100, 100)).toBe(882750904)
    expect(legacyHash(-7, 3)).toBe(497381208)
  })

  it.each([[0, 0], [0, -1], [-1, -1], [3, 2], [-20, 14]])('generateColumn(%i, %i) agrees with blockAt', (cx, cz) => {
    expect(columnMismatches(cx, cz, DEFAULT_WORLD_SEED).slice(0, 10)).toEqual([])
  })

  it('generates trees inside columns exactly like blockAt', () => {
    let treeChunk: [number, number] | null = null
    for (let cx = 16; cx < 46 && !treeChunk; cx++) {
      for (let cz = -15; cz < 15 && !treeChunk; cz++) if (treesInChunk(cx, cz, WILD_SEED).length) treeChunk = [cx, cz]
    }
    expect(treeChunk).not.toBeNull()
    const [cx, cz] = treeChunk!
    expect(generateColumn(cx, cz, WILD_SEED).includes(blockId('oak_log'))).toBe(true)
    expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/engine/worldgen.test.ts`
Expected: FAIL with `does not provide an export named 'blockAt'` (or similar missing-export error).

- [ ] **Step 4: Write the port**

Replace the whole contents of `frontend/src/engine/worldgen.ts` with:

```ts
// Keep this file in sync with backend/services/worldgen.py. shared/worldgen-fixture.json
// checks both ports cell by cell. The seed is persisted as a decimal string so
// JavaScript never rounds its 64-bit value.
import { AIR, blockId } from './blocks'

export const DEFAULT_WORLD_SEED = '13897963875510148821'
export const LEGACY_RADIUS = 192
const TRANSITION_WIDTH = 48
export const SEA_LEVEL = 2
export const CHUNK_SIZE = 16
export const WORLD_MIN_Y = -8
export const WORLD_HEIGHT = 128
export const WORLD_MAX_Y = WORLD_MIN_Y + WORLD_HEIGHT - 1
const HOME_RADIUS = 12
const MASK = 0xffffffff
const seedCache = new Map<string, [number, number]>()
const heightCache = new Map<string, number>()

function mod(value: number, n: number): number {
  return ((value % n) + n) % n
}

function seedParts(seed: string): [number, number] {
  let parts = seedCache.get(seed)
  if (!parts) {
    const value = BigInt.asUintN(64, BigInt(seed))
    parts = [Number(value & 0xffffffffn), Number(value >> 32n)]
    seedCache.set(seed, parts)
  }
  return parts
}

export function hash32(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED, channel = 0): number {
  const [low, high] = seedParts(seed)
  let value = (low ^ Math.imul(high, 0x9e3779b1) ^ Math.imul(x, 0x85ebca6b) ^
    Math.imul(y, 0x27d4eb2f) ^ Math.imul(z, 0xc2b2ae35) ^ Math.imul(channel, 0x165667b1)) >>> 0
  value = Math.imul(value ^ (value >>> 16), 0x7feb352d) >>> 0
  value = Math.imul(value ^ (value >>> 15), 0x846ca68b) >>> 0
  return (value ^ (value >>> 16)) >>> 0
}

/** The viewer's original position hash. Python reproduces JavaScript's int32 XOR. */
export function legacyHash(x: number, z: number): number {
  return Math.abs((x * 73856093) ^ (z * 19349663))
}

function smooth(value: number) { return value * value * (3 - 2 * value) }
function lerp(a: number, b: number, t: number) { return a + (b - a) * t }

function noise2(x: number, z: number, scale: number, seed: string, channel: number): number {
  const gx = Math.floor(x / scale), gz = Math.floor(z / scale)
  const fx = smooth(x / scale - gx), fz = smooth(z / scale - gz)
  const sample = (dx: number, dz: number) => hash32(gx + dx, 0, gz + dz, seed, channel) / MASK * 2 - 1
  return lerp(lerp(sample(0, 0), sample(1, 0), fx), lerp(sample(0, 1), sample(1, 1), fx), fz)
}

function noise3(x: number, y: number, z: number, scale: number, seed: string, channel: number): number {
  const gx = Math.floor(x / scale), gy = Math.floor(y / scale), gz = Math.floor(z / scale)
  const fx = smooth(x / scale - gx), fy = smooth(y / scale - gy), fz = smooth(z / scale - gz)
  const sample = (dx: number, dy: number, dz: number) => hash32(gx + dx, gy + dy, gz + dz, seed, channel) / MASK * 2 - 1
  const a = lerp(lerp(sample(0, 0, 0), sample(1, 0, 0), fx),
    lerp(sample(0, 0, 1), sample(1, 0, 1), fx), fz)
  const b = lerp(lerp(sample(0, 1, 0), sample(1, 1, 0), fx),
    lerp(sample(0, 1, 1), sample(1, 1, 1), fx), fz)
  return lerp(a, b, fy)
}

function legacyHeight(x: number, z: number): number {
  if (Math.hypot(x, z) < 17 || Math.hypot(x - 48, z) < 27) return 0
  const wave = Math.sin(x * 0.085) + Math.cos(z * 0.075) + Math.sin((x + z) * 0.037)
  return wave > 1.65 ? 3 : wave > 1.15 ? 2 : wave > 0.65 ? 1 : 0
}

export function terrainHeight(x: number, z: number, seed = DEFAULT_WORLD_SEED): number {
  const key = `${seed}:${x},${z}`
  const cached = heightCache.get(key)
  if (cached !== undefined) return cached
  const height = calculateHeight(x, z, seed)
  heightCache.set(key, height)
  if (heightCache.size > 200000) heightCache.clear()
  return height
}

function calculateHeight(x: number, z: number, seed: string): number {
  const radius = Math.hypot(x, z)
  if (radius <= LEGACY_RADIUS) return legacyHeight(x, z)
  const broad = noise2(x, z, 96, seed, 1) * 6
  const detail = noise2(x, z, 32, seed, 2) * 2
  const ridge = Math.max(0, noise2(x, z, 72, seed, 3)) ** 2 * 10
  const generated = Math.max(0, Math.min(18, Math.floor(3.5 + broad + detail + ridge)))
  if (radius >= LEGACY_RADIUS + TRANSITION_WIDTH) return generated
  const blend = smooth((radius - LEGACY_RADIUS) / TRANSITION_WIDTH)
  return Math.floor(legacyHeight(x, z) * (1 - blend) + generated * blend + 0.5)
}

export function biomeAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return 'meadow'
  const height = terrainHeight(x, z, seed)
  if (height >= 11) return 'alpine'
  const heat = noise2(x, z, 160, seed, 4)
  const moisture = noise2(x, z, 160, seed, 5)
  if (heat > 0.08 && moisture < -0.12) return 'desert'
  if (moisture > 0.08) return 'forest'
  return 'meadow'
}

export function surfaceMaterial(x: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert') return 'sand'
  if (biome === 'alpine') return 'snow'
  if (biome === 'forest' && hash32(x, 0, z, seed, 6) % 7 === 0) return 'moss'
  return 'grass'
}

export function caveAt(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): boolean {
  if (Math.hypot(x, z) <= LEGACY_RADIUS || y <= -5 || y >= terrainHeight(x, z, seed) - 2) return false
  return noise3(x, y, z, 11, seed, 7) > 0.27 && noise3(x, y, z, 5, seed, 8) > -0.12
}

function inPond(x: number, z: number): boolean {
  return ((x + 5) / 3.2) ** 2 + ((z - 4) / 2.4) ** 2 < 1
}

const STEPPING_STONES = new Set(['-3,2', '-2,1', '3,2', '4,1'])
const HOME_FLOWERS: [number, number, string][] = [
  [-8, 0, 'flower_orange'], [-7, 1, 'flower_pink'], [-2, -5, 'flower_yellow'], [1, -6, 'flower_pink'],
  [8, 1, 'flower_orange'], [7, 5, 'flower_yellow'], [-1, 7, 'flower_pink'], [3, 7, 'flower_orange'],
]

/** Ground of Mimo's original home island, or null outside it. */
function homeGround(x: number, y: number, z: number): string | null {
  const distance = Math.hypot(x, z)
  if (distance > 10.4 + (legacyHash(x, z) % 5) * 0.16) return null
  if (y === 0) {
    if (x >= 4 && x <= 7 && z >= -6 && z <= -3) return 'dirt_path'
    if (STEPPING_STONES.has(`${x},${z}`)) return 'dirt_path'
    if (inPond(x, z)) return 'water'
    const shore = ((x + 5) / 4.2) ** 2 + ((z - 4) / 3.4) ** 2 < 1
    if (shore || distance > 9.3) return 'sand'
    const walkway = x >= 0 && x <= 6 && Math.abs(z + Math.round(x * 0.55)) <= 0.6
    return walkway ? 'dirt_path' : 'grass'
  }
  if (y === -1) return distance > 9 ? 'sand' : 'dirt'
  if (y === -2 && distance < 9.1) return 'dirt'
  return null
}

function buildHomeBlocks(): Map<string, string> {
  const blocks = new Map<string, string>()
  const put = (x: number, y: number, z: number, name: string) => blocks.set(`${x},${y},${z}`, name)
  for (let x = 4; x <= 7; x++) for (let z = -6; z <= -3; z++) for (let y = 1; y <= 3; y++) {
    const wall = x === 4 || x === 7 || z === -6 || z === -3
    const door = x === 5 && z === -3 && y <= 2
    if (wall && !door) put(x, y, z, 'plaster')
  }
  put(5, 2, -6, 'glass')
  put(6, 2, -6, 'glass')
  for (let x = 3; x <= 8; x++) for (let z = -7; z <= -2; z++) {
    put(x, 4, z, 'roof_tile')
    if (x > 3 && x < 8 && z > -7 && z < -2) put(x, 5, z, 'roof_tile')
  }
  for (let x = -8; x <= -4; x++) for (let z = -6; z <= -2; z++) {
    const spread = Math.abs(x + 6) + Math.abs(z + 4)
    if (spread > 3) continue
    put(x, 5, z, 'leaves')
    if (spread <= 2) put(x, 6, z, 'leaves')
  }
  put(-6, 7, -4, 'leaves')
  for (let y = 1; y <= 5; y++) put(-6, y, -4, 'oak_log')
  for (const [x, z, name] of HOME_FLOWERS) put(x, 1, z, name)
  return blocks
}

const HOME_BLOCKS = buildHomeBlocks()

/** Terrain, water, caves and ores, before trees and plants are added. */
export function terrainBlock(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  if (y <= -5) return 'bedrock'
  const height = terrainHeight(x, z, seed)
  if (Math.hypot(x, z) <= LEGACY_RADIUS) {
    const home = homeGround(x, y, z)
    if (home) return home
    if (y >= -4 && y < -1) {
      const oreSeed = Math.abs(x * 31 + z * 17 + y * 101)
      return oreSeed % 37 === 0 ? 'iron_ore' : oreSeed % 19 === 0 ? 'coal_ore' : 'stone'
    }
    if (y === -1) return 'dirt'
    if (y === 0 && inPond(x, z)) return 'water'
    if (y === height) return 'grass'
    if (y >= 0 && y < height) return y >= height - 1 ? 'dirt' : 'stone'
    return 'air'
  }
  if (y > height) return y <= SEA_LEVEL ? 'water' : 'air'
  if (y === height) return surfaceMaterial(x, z, seed)
  if (y >= height - 2) return biomeAt(x, z, seed) === 'desert' ? 'sand' : 'dirt'
  if (caveAt(x, y, z, seed)) return 'air'
  const ore = hash32(x, y, z, seed, 9)
  if (ore % 97 === 0) return 'iron_ore'
  if (ore % 61 === 0) return 'coal_ore'
  if (ore % 151 === 0) return 'copper_ore'
  return 'stone'
}

/** Columns where the viewer has always allowed trees and flowers. */
function decorationColumn(x: number, z: number, seed: string): boolean {
  const lx = mod(x, 16), lz = mod(z, 16)
  if (lx < 3 || lx > 12 || lz < 3 || lz > 12 || Math.hypot(x, z) < 17) return false
  if (terrainHeight(x, z, seed) < SEA_LEVEL) return false
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert' || biome === 'alpine') return false
  const mx = mod(x, 13), mz = mod(z, 13)
  return !(Math.min(mx, 13 - mx) < 5 && Math.min(mz, 13 - mz) < 5)
}

/** Ground height under a tree trunk at (x, z), or null when no tree grows there. */
export function treeBase(x: number, z: number, seed = DEFAULT_WORLD_SEED): number | null {
  if (!decorationColumn(x, z, seed)) return null
  const grows = Math.hypot(x, z) <= LEGACY_RADIUS
    ? legacyHash(x, z) % 257 === 0
    : hash32(x, 0, z, seed, 12) % (biomeAt(x, z, seed) === 'forest' ? 78 : 300) === 0
  return grows ? terrainHeight(x, z, seed) : null
}

const treeCache = new Map<string, [number, number, number][]>()

/** [x, z, ground height] of every tree rooted in a chunk. Canopies never leave the chunk. */
export function treesInChunk(cx: number, cz: number, seed = DEFAULT_WORLD_SEED): [number, number, number][] {
  const key = `${seed}:${cx},${cz}`
  let trees = treeCache.get(key)
  if (trees) return trees
  trees = []
  for (let x = cx * 16 + 3; x < cx * 16 + 13; x++) {
    for (let z = cz * 16 + 3; z < cz * 16 + 13; z++) {
      const base = treeBase(x, z, seed)
      if (base !== null) trees.push([x, z, base])
    }
  }
  treeCache.set(key, trees)
  if (treeCache.size > 4096) treeCache.delete(treeCache.keys().next().value!)
  return trees
}

function isLeaf(dx: number, dy: number, dz: number): boolean {
  const ax = Math.abs(dx), az = Math.abs(dz)
  if (dy === 5) return ax <= 2 && az <= 2 && ax + az <= 3
  return dy === 6 && ax + az < 2
}

function treeBlock(x: number, y: number, z: number, seed: string): string | null {
  const trees = treesInChunk(Math.floor(x / 16), Math.floor(z / 16), seed)
  if (trees.some(([tx, tz, base]) => x === tx && z === tz && y > base && y <= base + 4)) return 'oak_log'
  if (trees.some(([tx, tz, base]) => isLeaf(x - tx, y - base, z - tz))) return 'leaves'
  return null
}

/** Flower or tall grass growing on top of the terrain at (x, z). */
export function plantAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  if (Math.hypot(x, z) <= HOME_RADIUS) return null
  if (decorationColumn(x, z, seed)) {
    if (treeBase(x, z, seed) !== null) return null
    if (hash32(x, 0, z, seed, 13) % 97 === 0) return legacyHash(x + 1, z) % 2 ? 'flower_orange' : 'flower_yellow'
  }
  if (Math.hypot(x, z) > LEGACY_RADIUS && terrainHeight(x, z, seed) < SEA_LEVEL) return null
  const surface = surfaceMaterial(x, z, seed)
  if (surface !== 'grass' && surface !== 'moss') return null
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

/** The natural block at any cell: terrain first, then decorations in air. */
export function blockAt(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  const terrain = terrainBlock(x, y, z, seed)
  if (terrain !== 'air') return terrain
  return decorationAt(x, y, z, seed) ?? 'air'
}

/** Index into a 16 × 128 × 16 column. y is a world y. */
export function columnIndex(lx: number, y: number, lz: number): number {
  return ((y - WORLD_MIN_Y) * CHUNK_SIZE + lz) * CHUNK_SIZE + lx
}

/**
 * Fill a whole column at once. Equivalent to blockAt for every cell, but stamps
 * decorations instead of searching for them per cell.
 */
export function generateColumn(cx: number, cz: number, seed = DEFAULT_WORLD_SEED): Uint8Array {
  const data = new Uint8Array(CHUNK_SIZE * CHUNK_SIZE * WORLD_HEIGHT)
  const x0 = cx * CHUNK_SIZE, z0 = cz * CHUNK_SIZE
  for (let lz = 0; lz < CHUNK_SIZE; lz++) for (let lx = 0; lx < CHUNK_SIZE; lx++) {
    const x = x0 + lx, z = z0 + lz
    const top = Math.max(terrainHeight(x, z, seed), SEA_LEVEL)
    for (let y = WORLD_MIN_Y; y <= top; y++) {
      const name = terrainBlock(x, y, z, seed)
      if (name !== 'air') data[columnIndex(lx, y, lz)] = blockId(name)
    }
  }
  const terrain = data.slice()
  // Later stamps win, so stamp in rising precedence: plants, leaves, trunks, home.
  const stamp = (x: number, y: number, z: number, name: string) => {
    const lx = x - x0, lz = z - z0
    if (lx < 0 || lx >= CHUNK_SIZE || lz < 0 || lz >= CHUNK_SIZE || y < WORLD_MIN_Y || y > WORLD_MAX_Y) return
    const index = columnIndex(lx, y, lz)
    if (terrain[index] === AIR) data[index] = blockId(name)
  }
  for (let lz = 0; lz < CHUNK_SIZE; lz++) for (let lx = 0; lx < CHUNK_SIZE; lx++) {
    const plant = plantAt(x0 + lx, z0 + lz, seed)
    if (plant) stamp(x0 + lx, terrainHeight(x0 + lx, z0 + lz, seed) + 1, z0 + lz, plant)
  }
  const trees = treesInChunk(cx, cz, seed)
  for (const [tx, tz, base] of trees) {
    for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (const dy of [5, 6]) {
      if (isLeaf(dx, dy, dz)) stamp(tx + dx, base + dy, tz + dz, 'leaves')
    }
  }
  for (const [tx, tz, base] of trees) for (let y = base + 1; y <= base + 4; y++) stamp(tx, y, tz, 'oak_log')
  for (const [key, name] of HOME_BLOCKS) {
    const [x, y, z] = key.split(',').map(Number)
    stamp(x, y, z, name)
  }
  return data
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test`
Expected: all tests pass. If the fixture test reports mismatches, the TypeScript port differs from Python. Compare the failing cells against the old viewer code in git history (`git show HEAD~5:frontend/src/components/world/expandingWorld.ts`) to decide which side is wrong; fix that side, regenerate the fixture if Python changed, and rerun both test suites.

- [ ] **Step 6: Run the build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 7: Commit**

```bash
git add -A frontend/src/engine/worldgen.ts frontend/src/engine/worldgen.test.ts frontend/src/components/world/worldgen.ts frontend/src/components/world/expandingWorld.ts frontend/src/components/world/worldPlanner.ts frontend/src/pages/WorldPreview.tsx
git commit -m "feat: port natural blocks and column generation to TypeScript worldgen" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Block sequence numbers and the delta endpoint

**Files:**
- Modify: `backend/services/live_mimo.py` (`initialize`, new `_write_block`, `put_block`, `step_loose_blocks`, `finish`, `owner_action`, `snapshot`, new `blocks_since`, `run_tick`)
- Modify: `backend/api/mimo.py`
- Modify: `backend/tests/test_live_mimo.py:342-344`
- Test: `backend/tests/test_block_sync.py`

**Interfaces:**
- Produces: `MimoStore.blocks_since(since: int, limit: int = 5000) -> {"seq": int, "changes": [{"x", "y", "z", "material"}], "more": bool}`; `snapshot()` returns `blocks_seq: int` and no longer returns `block_edits` or `catalog`; `GET /api/mimo/blocks?since=&limit=` returns the same shape as `blocks_since`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_block_sync.py`:

```python
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.live_mimo import MimoStore


class BlockSyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "mimo.sqlite3"
        self.store = MimoStore(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_every_block_write_gets_a_new_sequence_number(self):
        self.store.put_block(80, 20, 0, "stone")
        first = self.store.blocks_since(0)
        self.assertEqual(first["changes"], [{"x": 80, "y": 20, "z": 0, "material": "stone"}])
        self.store.put_block(80, 20, 0, "air")
        second = self.store.blocks_since(first["seq"])
        self.assertEqual(second["changes"], [{"x": 80, "y": 20, "z": 0, "material": "air"}])
        self.assertGreater(second["seq"], first["seq"])
        self.assertFalse(second["more"])

    def test_falling_sand_reports_both_cells(self):
        self.store.put_block(73, 2, 0, "sand")
        seq = self.store.blocks_since(0)["seq"]
        self.assertEqual(self.store.step_loose_blocks(), 1)
        changes = self.store.blocks_since(seq)["changes"]
        self.assertIn({"x": 73, "y": 2, "z": 0, "material": "air"}, changes)
        self.assertIn({"x": 73, "y": 1, "z": 0, "material": "sand"}, changes)

    def test_worker_and_owner_writes_are_numbered(self):
        state = self.store.claim_due(time.time() + 10 ** 6)
        self.store.finish(state, None, (81, 3, 0, "planks"))
        seq = self.store.blocks_since(0)["seq"]
        self.assertEqual(self.store.blocks_since(0)["changes"], [{"x": 81, "y": 3, "z": 0, "material": "planks"}])
        self.store.owner_action("craft", "planks")
        self.store.owner_action("craft", "crafting_table")
        self.store.owner_action("place_machine", "crafting_table")
        materials = [change["material"] for change in self.store.blocks_since(seq)["changes"]]
        self.assertEqual(materials, ["crafting_table"])

    def test_since_pages_through_changes_in_order(self):
        for x in range(90, 97):
            self.store.put_block(x, 20, 0, "stone")
        page = self.store.blocks_since(0, limit=3)
        self.assertEqual(len(page["changes"]), 3)
        self.assertTrue(page["more"])
        seen = list(page["changes"])
        while page["more"]:
            page = self.store.blocks_since(page["seq"], limit=3)
            seen += page["changes"]
        self.assertEqual([change["x"] for change in seen], list(range(90, 97)))

    def test_old_database_without_seq_is_migrated(self):
        path = Path(self.directory.name) / "old.sqlite3"
        connection = sqlite3.connect(path)
        with connection:
            connection.execute("CREATE TABLE mimo_blocks (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, "
                               "material TEXT NOT NULL, PRIMARY KEY(x,y,z))")
            connection.execute("INSERT INTO mimo_blocks VALUES (1,2,3,'stone'), (4,5,6,'air')")
        connection.close()
        store = MimoStore(path)
        page = store.blocks_since(0)
        self.assertEqual(len(page["changes"]), 2)
        self.assertEqual(page["seq"], 2)
        store.put_block(7, 8, 9, "dirt")
        self.assertEqual(store.blocks_since(2)["changes"], [{"x": 7, "y": 8, "z": 9, "material": "dirt"}])

    def test_snapshot_reports_blocks_seq_instead_of_every_edit(self):
        self.store.put_block(80, 20, 0, "stone")
        snapshot = self.store.snapshot()
        self.assertNotIn("block_edits", snapshot)
        self.assertNotIn("catalog", snapshot)
        self.assertIn("recipes", snapshot)
        self.assertEqual(snapshot["blocks_seq"], self.store.blocks_since(0)["seq"])

    def test_blocks_endpoint_reads_the_configured_store(self):
        self.store.put_block(80, 20, 0, "stone")
        with patch.dict("os.environ", {"MIMO_DB_PATH": str(self.path)}):
            from backend.api.mimo import get_mimo_blocks
            result = get_mimo_blocks(since=0, limit=5000)
        self.assertEqual(result["changes"], [{"x": 80, "y": 20, "z": 0, "material": "stone"}])


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_live_mimo.py`, replace the last three assertions of `test_owner_can_craft_and_place_real_machines` with:

```python
        saved = MimoStore(self.path)
        self.assertEqual(saved.snapshot()["inventory"]["iron_ingot"], 1)
        self.assertEqual(len([block for block in saved.block_edits() if block["material"] in ("crafting_table", "furnace")]), 2)
        self.assertEqual(saved.snapshot()["events"][0]["kind"], "owner")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_block_sync -v`
Expected: FAIL with `AttributeError: 'MimoStore' object has no attribute 'blocks_since'`

- [ ] **Step 3: Add sequence numbers to the store**

In `backend/services/live_mimo.py`:

1. In `initialize()`, replace the `mimo_blocks` `CREATE TABLE` line with:

```python
            db.execute("CREATE TABLE IF NOT EXISTS mimo_blocks (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, material TEXT NOT NULL, seq INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(x,y,z))")
            db.execute("CREATE TABLE IF NOT EXISTS mimo_meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
            if "seq" not in {row["name"] for row in db.execute("PRAGMA table_info(mimo_blocks)")}:
                # Worlds saved before block sync get sequence numbers in row order.
                db.execute("ALTER TABLE mimo_blocks ADD COLUMN seq INTEGER NOT NULL DEFAULT 0")
                db.execute("UPDATE mimo_blocks SET seq = rowid")
            db.execute("CREATE INDEX IF NOT EXISTS mimo_blocks_by_seq ON mimo_blocks(seq)")
            db.execute("INSERT OR IGNORE INTO mimo_meta(key, value) VALUES('blocks_seq', 0)")
            db.execute("UPDATE mimo_meta SET value = MAX(value, (SELECT COALESCE(MAX(seq), 0) FROM mimo_blocks)) WHERE key='blocks_seq'")
```

2. Add this method to `MimoStore`, directly after `connect`:

```python
    @staticmethod
    def _write_block(db: sqlite3.Connection, x: int, y: int, z: int, material: str) -> int:
        """Every block write goes through here so viewers can fetch changes by seq."""
        db.execute("UPDATE mimo_meta SET value = value + 1 WHERE key='blocks_seq'")
        seq = db.execute("SELECT value FROM mimo_meta WHERE key='blocks_seq'").fetchone()["value"]
        db.execute("INSERT INTO mimo_blocks(x,y,z,material,seq) VALUES(?,?,?,?,?) "
                   "ON CONFLICT(x,y,z) DO UPDATE SET material=excluded.material, seq=excluded.seq",
                   (x, y, z, material, seq))
        return seq
```

3. Replace every direct `INSERT INTO mimo_blocks` with `_write_block`:
   - `put_block`: the body inside `with self.connect() as db:` becomes `self._write_block(db, x, y, z, material)`.
   - `step_loose_blocks`: the two inserts become `self._write_block(db, x, y, z, "air")` and `self._write_block(db, x, y - 1, z, material)`.
   - `finish`: `if block_edit: self._write_block(db, *block_edit)`.
   - `owner_action`: `self._write_block(db, *candidate, item)`.

   Run `grep -n "INSERT INTO mimo_blocks" backend/services/live_mimo.py` and confirm the only match is inside `_write_block`.

4. Add this method after `block_edits`:

```python
    def blocks_since(self, since: int, limit: int = 5000) -> dict:
        """Block changes after `since`, oldest first. Removed blocks come back as air."""
        limit = max(1, min(limit, 5000))
        with self.connect() as db:
            # Read the latest seq first so a write landing mid-query is fetched next time.
            latest = db.execute("SELECT value FROM mimo_meta WHERE key='blocks_seq'").fetchone()["value"]
            rows = db.execute("SELECT x,y,z,material,seq FROM mimo_blocks WHERE seq > ? AND seq <= ? "
                              "ORDER BY seq LIMIT ?", (since, latest, limit + 1)).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        return {"seq": rows[-1]["seq"] if more else latest,
                "changes": [{"x": row["x"], "y": row["y"], "z": row["z"], "material": row["material"]} for row in rows],
                "more": more}
```

5. In `snapshot()`, delete the `state["block_edits"] = ...` statement and `state["catalog"] = BLOCKS`, and add:

```python
            state["blocks_seq"] = db.execute("SELECT value FROM mimo_meta WHERE key='blocks_seq'").fetchone()["value"]
```

6. In `run_tick`, change `observation = observe_world(state, snapshot["block_edits"])` to `observation = observe_world(state, store.block_edits())`.

- [ ] **Step 4: Add the endpoint**

Replace `backend/api/mimo.py` imports and add the route:

```python
from fastapi import APIRouter, HTTPException, Query
```

```python
@router.get("/mimo/blocks")
def get_mimo_blocks(since: int = Query(0, ge=0), limit: int = Query(5000, ge=1, le=5000)):
    return MimoStore().blocks_since(since, limit)
```

Put it directly after `get_mimo`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests`
Expected: all tests pass (42 total).

- [ ] **Step 6: Commit**

```bash
git add backend/services/live_mimo.py backend/api/mimo.py backend/tests/test_block_sync.py backend/tests/test_live_mimo.py
git commit -m "feat: number block writes and serve block deltas" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Soft pixel texture atlas

**Files:**
- Create: `frontend/src/engine/atlas.ts`
- Test: `frontend/src/engine/atlas.test.ts`

**Interfaces:**
- Consumes: `TILES`, `BLOCKS`, `blockDef`, `type Rgb`, `type TileRecipe` from Task 2.
- Produces: `TILE_SIZE = 8`, `ATLAS_COLUMNS = 16`, `ATLAS_SIZE = 128`, `FACE_EAST = 0`, `FACE_WEST = 1`, `FACE_UP = 2`, `FACE_DOWN = 3`, `FACE_SOUTH = 4`, `FACE_NORTH = 5`, `interface Atlas { size, data: Uint8Array, tileIndex: Map<string, number>, faceTiles: Uint16Array, waterTile: number, waterPixels: Uint8Array }`, `PATTERNS: Record<string, Painter>`, `buildAtlas(): Atlas`, `tileUv(tile): [u0, v0, u1, v1]`, `animateWater(atlas, step): void`. Tile 0 is always `missing`. `data` rows are bottom-first (three.js `DataTexture` with `flipY` off).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/engine/atlas.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { ATLAS_SIZE, FACE_UP, PATTERNS, TILE_SIZE, animateWater, buildAtlas, tileUv, type Atlas } from './atlas'
import { BLOCKS, MISSING_ID, TILES } from './blocks'

/** Pixel (i, j) of a tile, with j = 0 as the top row the way it was painted. */
function pixelAt(atlas: Atlas, tile: number, i: number, j: number): number[] {
  const tx = (tile % 16) * TILE_SIZE, ty = Math.floor(tile / 16) * TILE_SIZE
  const offset = ((ty + TILE_SIZE - 1 - j) * ATLAS_SIZE + tx + i) * 4
  return Array.from(atlas.data.slice(offset, offset + 4))
}

function tilePixels(atlas: Atlas, tile: number): number[][] {
  const pixels: number[][] = []
  for (let j = 0; j < TILE_SIZE; j++) for (let i = 0; i < TILE_SIZE; i++) pixels.push(pixelAt(atlas, tile, i, j))
  return pixels
}

describe('atlas', () => {
  const atlas = buildAtlas()

  it('knows every tile pattern in the registry', () => {
    for (const [name, recipe] of Object.entries(TILES)) expect(PATTERNS[recipe.pattern], name).toBeDefined()
  })

  it('gives every registered block face a real tile', () => {
    for (const block of BLOCKS) {
      if (block.layer === 'none') continue
      for (let face = 0; face < 6; face++) expect(atlas.faceTiles[block.id * 6 + face], `${block.name} face ${face}`).not.toBe(0)
    }
  })

  it('shows unknown ids with the magenta missing tile', () => {
    expect(atlas.faceTiles[MISSING_ID * 6 + FACE_UP]).toBe(0)
    expect(pixelAt(atlas, 0, 2, 0)).toEqual([255, 0, 255, 255])
    expect(pixelAt(atlas, 0, 0, 0)).toEqual([24, 24, 24, 255])
  })

  it('puts the grass lip on the top rows of the side tile', () => {
    const side = atlas.tileIndex.get('grass_side')!
    const top = pixelAt(atlas, side, 3, 0)
    const bottom = pixelAt(atlas, side, 3, 7)
    expect(top[1]).toBeGreaterThan(bottom[1] + 30) // green lip above brown dirt
  })

  it('keeps sprites and glass see-through', () => {
    const alphas = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).map((pixel) => pixel[3])
    expect(alphas('tall_grass')).toContain(0)
    expect(alphas('flower_pink')).toContain(0)
    expect(Math.min(...alphas('glass'))).toBeLessThan(255)
    expect(Math.max(...alphas('water'))).toBeLessThan(255)
  })

  it('insets uvs by a quarter texel', () => {
    const inset = 0.25 / ATLAS_SIZE
    expect(tileUv(0)).toEqual([inset, inset, 8 / 128 - inset, 8 / 128 - inset])
    expect(tileUv(17)).toEqual([8 / 128 + inset, 8 / 128 + inset, 16 / 128 - inset, 16 / 128 - inset])
  })

  it('is deterministic', () => {
    expect(buildAtlas().data).toEqual(atlas.data)
  })

  it('scrolls the water tile in place', () => {
    const scratch = buildAtlas()
    const before = scratch.data.slice()
    const water = tilePixels(scratch, scratch.waterTile)
    animateWater(scratch, 1)
    const after = tilePixels(scratch, scratch.waterTile)
    expect(after).not.toEqual(water)
    const grass = scratch.tileIndex.get('grass_top')!
    expect(tilePixels(scratch, grass)).toEqual(tilePixels({ ...scratch, data: before }, grass))
    animateWater(scratch, 0)
    expect(scratch.data).toEqual(before)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/engine/atlas.test.ts`
Expected: FAIL with `Failed to resolve import "./atlas"`

- [ ] **Step 3: Write the atlas**

Create `frontend/src/engine/atlas.ts`:

```ts
import { blockDef, TILES, type Rgb, type TileRecipe } from './blocks'

export const TILE_SIZE = 8
export const ATLAS_COLUMNS = 16
export const ATLAS_SIZE = TILE_SIZE * ATLAS_COLUMNS
// Face order shared with the mesher.
export const FACE_EAST = 0
export const FACE_WEST = 1
export const FACE_UP = 2
export const FACE_DOWN = 3
export const FACE_SOUTH = 4
export const FACE_NORTH = 5

export interface Atlas {
  size: number
  /** RGBA, bottom row first, as THREE.DataTexture reads it with flipY off. */
  data: Uint8Array
  tileIndex: Map<string, number>
  /** faceTiles[id * 6 + face] is the tile drawn on that face of that block. */
  faceTiles: Uint16Array
  waterTile: number
  /** The water tile as first painted, in data row order. */
  waterPixels: Uint8Array
}

type Pixel = [number, number, number, number]
type Painter = (recipe: TileRecipe, random: () => number) => Pixel[]

const N = TILE_SIZE
const AMP = 0.09
const CLEAR: Pixel = [0, 0, 0, 0]

function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function hashString(text: string): number {
  let hash = 2166136261
  for (let i = 0; i < text.length; i++) hash = Math.imul(hash ^ text.charCodeAt(i), 16777619)
  return hash >>> 0
}

function tone(color: Rgb, k: number, alpha = 255): Pixel {
  return [color[0] * k, color[1] * k, color[2] * k, alpha]
}

function grid(paint: (i: number, j: number) => Pixel): Pixel[] {
  const pixels: Pixel[] = []
  for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) pixels.push(paint(i, j))
  return pixels
}

const jitter = (random: () => number, amount = AMP) => 1 + (random() - 0.5) * amount
const edge = (i: number, j: number) => i === 0 || j === 0 || i === N - 1 || j === N - 1

/** Tile painters. Row j = 0 is the top of the tile. */
export const PATTERNS: Record<string, Painter> = {
  missing: () => grid((i, j) => ((i >> 1) + (j >> 1)) % 2 ? [255, 0, 255, 255] : [24, 24, 24, 255]),
  noise: ({ color }, random) => grid(() => tone(color, jitter(random))),
  specks: ({ color }, random) => grid(() => tone(color, (random() < 0.14 ? 0.84 : 1) * jitter(random))),
  grass_top: ({ color }, random) => grid(() => tone(color, (random() < 0.14 ? 0.88 : 1) * jitter(random))),
  grass_side: ({ color, accent }, random) => {
    const lips = Array.from({ length: N }, () => 2 + Math.floor(random() * 2))
    return grid((i, j) => tone(j < lips[i] ? accent ?? color : color, jitter(random)))
  },
  log_side: ({ color }, random) => grid((i) => tone(color, (i % 2 ? 0.86 : 1) * jitter(random))),
  log_top: ({ color, accent }, random) => grid((i, j) => {
    const ring = Math.max(Math.abs(i - 3.5), Math.abs(j - 3.5))
    if (ring >= 3) return tone(accent ?? color, jitter(random))
    return tone(color, (Math.round(ring) % 2 ? 0.88 : 1) * jitter(random))
  }),
  planks: ({ color }, random) => grid((i, j) => {
    const board = Math.floor(j / 4)
    const seam = j % 4 === 3 || i === (board * 5 + 3) % N
    return tone(color, (seam ? 0.76 : 1) * jitter(random))
  }),
  cobble: ({ color }, random) => {
    const points = Array.from({ length: 6 }, () => [random() * N, random() * N, 0.82 + random() * 0.28])
    return grid((i, j) => {
      const distances = points.map(([px, py, k]) => {
        const dx = Math.min(Math.abs(i - px), N - Math.abs(i - px))
        const dy = Math.min(Math.abs(j - py), N - Math.abs(j - py))
        return [Math.hypot(dx, dy), k]
      }).sort((a, b) => a[0] - b[0])
      return distances[1][0] - distances[0][0] < 0.8 ? tone(color, 0.62) : tone(color, distances[0][1] * jitter(random))
    })
  },
  ore: ({ color, accent }, random) => {
    const spots = Array.from({ length: 3 }, () => [1 + Math.floor(random() * 6), 1 + Math.floor(random() * 6)])
    return grid((i, j) => spots.some(([x, y]) => Math.abs(i - x) + Math.abs(j - y) <= 1)
      ? tone(accent ?? color, jitter(random))
      : tone(color, (random() < 0.14 ? 0.84 : 1) * jitter(random)))
  },
  leaves: ({ color }, random) => grid(() => tone(color, (random() < 0.2 ? 0.7 : 1) * jitter(random, 0.14))),
  glass: ({ color }, random) => grid((i, j) => {
    if (edge(i, j)) return tone(color, 0.9, 220)
    if (i - j === 2 && i < 6) return tone(color, 1.15, 150)
    return tone(color, jitter(random, 0.04), 70)
  }),
  water: ({ color }, random) => grid(() => tone(color, (random() < 0.08 ? 1.15 : 1) * jitter(random, 0.06), 190)),
  glow: ({ color }, random) => grid((i, j) =>
    tone(color, (1.12 - 0.04 * Math.max(Math.abs(i - 3.5), Math.abs(j - 3.5))) * jitter(random, 0.06))),
  bricks: ({ color, accent }, random) => grid((i, j) => {
    const mortar = j % 4 === 3 || i === (Math.floor(j / 4) % 2 ? 1 : 5)
    return mortar ? tone(accent ?? color, jitter(random, 0.04)) : tone(color, jitter(random))
  }),
  rows: ({ color }, random) => grid((_i, j) => tone(color, (j % 2 ? 0.92 : 1) * jitter(random))),
  panel: ({ color }, random) => grid((i, j) => tone(color, (edge(i, j) ? 0.82 : 1) * jitter(random, 0.045))),
  table_top: ({ color, accent }, random) => grid((i, j) => {
    if (edge(i, j)) return tone(accent ?? color, jitter(random))
    return tone(color, (i === N / 2 || j === N / 2 ? 0.72 : 1) * jitter(random))
  }),
  table_side: ({ color, accent }, random) => grid((i, j) => {
    if (j < 2) return tone(accent ?? color, jitter(random))
    const tool = j >= 3 && j <= 6 && i >= 2 && i <= 5
    return tone(color, (i === 0 || i === N - 1 || tool ? 0.7 : 1) * jitter(random))
  }),
  furnace_side: ({ color, accent }, random) => grid((i, j) => {
    if (i >= 2 && i <= 5 && j >= 4 && j <= 6) return tone(accent ?? color, jitter(random, 0.12))
    const frame = i >= 1 && i <= 6 && j >= 3 && j <= 7
    return tone(color, (frame ? 0.6 : random() < 0.14 ? 0.84 : 1) * jitter(random))
  }),
  sprite_grass: ({ color }, random) => {
    const heights = [0, 4 + Math.floor(random() * 3), 0, 3 + Math.floor(random() * 4),
      5 + Math.floor(random() * 3), 0, 3 + Math.floor(random() * 3), 0]
    return grid((i, j) => j >= N - heights[i] ? tone(color, jitter(random, 0.16)) : CLEAR)
  },
  sprite_flower: ({ color, accent }, random) => grid((i, j) => {
    if (i >= 2 && i <= 4 && j >= 1 && j <= 3) return tone(color, (i === 3 && j === 2 ? 0.8 : 1) * jitter(random))
    if ((i === 3 && j >= 4) || (i === 2 && j === 5) || (i === 4 && j === 6)) return tone(accent ?? color, jitter(random))
    return CLEAR
  }),
}

function tileOrigin(tile: number): [number, number] {
  return [(tile % ATLAS_COLUMNS) * TILE_SIZE, Math.floor(tile / ATLAS_COLUMNS) * TILE_SIZE]
}

function writeTile(data: Uint8Array, tile: number, pixels: Pixel[]): void {
  const [tx, ty] = tileOrigin(tile)
  pixels.forEach((pixel, index) => {
    const i = index % N, j = Math.floor(index / N)
    const offset = ((ty + N - 1 - j) * ATLAS_SIZE + tx + i) * 4
    for (let c = 0; c < 4; c++) data[offset + c] = Math.max(0, Math.min(255, Math.round(pixel[c])))
  })
}

function readTile(data: Uint8Array, tile: number): Uint8Array {
  const [tx, ty] = tileOrigin(tile)
  const pixels = new Uint8Array(N * N * 4)
  for (let row = 0; row < N; row++) {
    const start = ((ty + row) * ATLAS_SIZE + tx) * 4
    pixels.set(data.subarray(start, start + N * 4), row * N * 4)
  }
  return pixels
}

export function buildAtlas(): Atlas {
  const data = new Uint8Array(ATLAS_SIZE * ATLAS_SIZE * 4)
  const tileIndex = new Map<string, number>()
  const names = ['missing', ...Object.keys(TILES).filter((name) => name !== 'missing')]
  if (names.length > ATLAS_COLUMNS * ATLAS_COLUMNS) throw new Error('Texture atlas is full')
  names.forEach((name, index) => {
    tileIndex.set(name, index)
    const recipe = TILES[name] ?? { pattern: 'missing', color: [255, 0, 255] }
    const painter = PATTERNS[recipe.pattern] ?? PATTERNS.missing
    writeTile(data, index, painter(recipe, mulberry32(hashString(name))))
  })
  const faceTiles = new Uint16Array(256 * 6)
  for (let id = 0; id < 256; id++) {
    const { textures } = blockDef(id)
    const perFace = [textures.side, textures.side, textures.top, textures.bottom, textures.side, textures.side]
    perFace.forEach((tile, face) => { faceTiles[id * 6 + face] = tileIndex.get(tile) ?? 0 })
  }
  const waterTile = tileIndex.get('water') ?? 0
  return { size: ATLAS_SIZE, data, tileIndex, faceTiles, waterTile, waterPixels: readTile(data, waterTile) }
}

/** UV rectangle of a tile, inset a quarter texel so neighbors never bleed in. */
export function tileUv(tile: number): [number, number, number, number] {
  const [tx, ty] = tileOrigin(tile)
  const inset = 0.25 / ATLAS_SIZE
  const span = TILE_SIZE / ATLAS_SIZE
  const u0 = tx / ATLAS_SIZE, v0 = ty / ATLAS_SIZE
  return [u0 + inset, v0 + inset, u0 + span - inset, v0 + span - inset]
}

/** Scroll the water tile by whole texel rows. The caller re-uploads the texture. */
export function animateWater(atlas: Atlas, step: number): void {
  const [tx, ty] = tileOrigin(atlas.waterTile)
  const shift = ((step % N) + N) % N
  for (let row = 0; row < N; row++) {
    const source = (row + shift) % N
    atlas.data.set(atlas.waterPixels.subarray(source * N * 4, (source + 1) * N * 4), ((ty + row) * atlas.size + tx) * 4)
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/engine/atlas.test.ts`
Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/engine/atlas.ts frontend/src/engine/atlas.test.ts
git commit -m "feat: paint soft pixel block atlas" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Column mesher with ambient occlusion

**Files:**
- Create: `frontend/src/engine/mesher.ts`
- Test: `frontend/src/engine/mesher.test.ts`

**Interfaces:**
- Consumes: `tileUv`, `buildAtlas().faceTiles` (Task 7); `AIR`, `LAYER_BY_ID`, `GLOW_BY_ID`, `FLUID_BY_ID`, `LAYER_*` (Task 2); `CHUNK_SIZE`, `WORLD_HEIGHT`, `WORLD_MIN_Y` (Task 5).
- Produces: `PADDED = 18`, `paddedIndex(px, layer, pz): number` (px, pz in 0..17 where 0 and 17 are neighbor cells; layer = worldY − WORLD_MIN_Y), `interface LayerBuffers { positions: Float32Array; uvs: Float32Array; colors: Float32Array; indices: Uint32Array }`, `interface ColumnMesh { opaque; cutout; translucent }`, `interface MeshInput { cx; cz; volume: Uint8Array; faceTiles: Uint16Array }`, `meshColumn(input): ColumnMesh`, `cornerAo(side1, side2, corner): number`, `srgbToLinear(value): number`. Positions are world coordinates. Each quad is 4 consecutive vertices and 6 consecutive indices.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/engine/mesher.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildAtlas } from './atlas'
import { blockId } from './blocks'
import { cornerAo, meshColumn, PADDED, paddedIndex, type LayerBuffers } from './mesher'
import { WORLD_HEIGHT, WORLD_MIN_Y } from './worldgen'

const { faceTiles } = buildAtlas()

/** Blocks use padded x/z (1..16 is this column, 0 and 17 are neighbors) and world y. */
function mesh(blocks: [number, number, number, string][]) {
  const volume = new Uint8Array(PADDED * PADDED * WORLD_HEIGHT)
  for (const [px, y, pz, name] of blocks) volume[paddedIndex(px, y - WORLD_MIN_Y, pz)] = blockId(name)
  return meshColumn({ cx: 0, cz: 0, volume, faceTiles })
}

const quadCount = (buffers: LayerBuffers) => buffers.indices.length / 6

function quads(buffers: LayerBuffers) {
  const result: { vertices: number[][]; light: number[]; indices: number[] }[] = []
  for (let q = 0; q < quadCount(buffers); q++) {
    const vertices: number[][] = [], light: number[] = []
    for (let k = 0; k < 4; k++) {
      const v = q * 4 + k
      vertices.push([buffers.positions[v * 3], buffers.positions[v * 3 + 1], buffers.positions[v * 3 + 2]])
      light.push(buffers.colors[v * 3])
    }
    result.push({ vertices, light, indices: Array.from(buffers.indices.slice(q * 6, q * 6 + 6)).map((i) => i - q * 4) })
  }
  return result
}

/** The top face of the block at padded (5, 10, 5): world x and z 4..5, y 11. */
function topOfBlock(buffers: LayerBuffers) {
  return quads(buffers).find((quad) => quad.vertices.every(([x, y, z]) => y === 11 && x >= 4 && x <= 5 && z >= 4 && z <= 5))!
}

describe('meshColumn', () => {
  it('draws all six faces of a lone block', () => {
    expect(quadCount(mesh([[5, 10, 5, 'stone']]).opaque)).toBe(6)
  })

  it('hides faces between opaque neighbors', () => {
    expect(quadCount(mesh([[5, 10, 5, 'stone'], [6, 10, 5, 'stone']]).opaque)).toBe(10)
  })

  it('hides faces between blocks of the same translucent kind', () => {
    const result = mesh([[5, 10, 5, 'glass'], [6, 10, 5, 'glass']])
    expect(quadCount(result.translucent)).toBe(10)
    expect(quadCount(result.opaque)).toBe(0)
  })

  it('keeps sand visible under water and lowers the water surface', () => {
    const result = mesh([[5, 10, 5, 'sand'], [5, 11, 5, 'water']])
    expect(quadCount(result.opaque)).toBe(6)
    expect(quadCount(result.translucent)).toBe(5)
    const ys = quads(result.translucent).flatMap((quad) => quad.vertices.map((vertex) => vertex[1]))
    expect(Math.max(...ys)).toBeCloseTo(11.875)
  })

  it('uses neighbor columns to hide border faces', () => {
    expect(quadCount(mesh([[1, 10, 5, 'stone'], [0, 10, 5, 'stone']]).opaque)).toBe(5)
  })

  it('never draws the underside of the world', () => {
    expect(quadCount(mesh([[5, WORLD_MIN_Y, 5, 'bedrock']]).opaque)).toBe(5)
  })

  it('draws plants as two crossed quads', () => {
    const result = mesh([[5, 10, 5, 'flower_pink']])
    expect(quadCount(result.cutout)).toBe(2)
    expect(quadCount(result.opaque)).toBe(0)
  })

  it('scores corner occlusion with the three-neighbor rule', () => {
    expect(cornerAo(0, 0, 0)).toBe(3)
    expect(cornerAo(1, 0, 0)).toBe(2)
    expect(cornerAo(0, 0, 1)).toBe(2)
    expect(cornerAo(1, 0, 1)).toBe(1)
    expect(cornerAo(1, 1, 0)).toBe(0)
  })

  it('darkens the corners next to a wall', () => {
    const top = topOfBlock(mesh([[5, 10, 5, 'stone'], [6, 11, 5, 'stone']]).opaque)
    const nearWall = top.light.filter((_, k) => top.vertices[k][0] === 5)
    const open = top.light.filter((_, k) => top.vertices[k][0] === 4)
    expect(Math.max(...nearWall)).toBeLessThan(Math.min(...open))
  })

  it('splits the quad along the diagonal through a lone dark corner', () => {
    const top = topOfBlock(mesh([[5, 10, 5, 'stone'], [6, 11, 6, 'stone']]).opaque)
    const dark = top.vertices.findIndex(([x, , z]) => x === 5 && z === 5)
    expect(top.indices.filter((index) => index === dark)).toHaveLength(2)
  })

  it('does not shade glowing blocks', () => {
    const top = topOfBlock(mesh([[5, 10, 5, 'lantern'], [6, 11, 5, 'stone']]).opaque)
    expect(new Set(top.light).size).toBe(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/engine/mesher.test.ts`
Expected: FAIL with `Failed to resolve import "./mesher"`

- [ ] **Step 3: Write the mesher**

Create `frontend/src/engine/mesher.ts`:

```ts
import { tileUv } from './atlas'
import {
  AIR, FLUID_BY_ID, GLOW_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
} from './blocks'
import { CHUNK_SIZE, WORLD_HEIGHT, WORLD_MIN_Y } from './worldgen'

/** A column plus a one-cell border on each side, so faces and AO at the edges are right. */
export const PADDED = CHUNK_SIZE + 2

/** px and pz run 0..17 (0 and 17 are neighbor cells); layer is worldY - WORLD_MIN_Y. */
export function paddedIndex(px: number, layer: number, pz: number): number {
  return (layer * PADDED + pz) * PADDED + px
}

export interface LayerBuffers {
  positions: Float32Array
  uvs: Float32Array
  colors: Float32Array
  indices: Uint32Array
}

export interface ColumnMesh {
  opaque: LayerBuffers
  cutout: LayerBuffers
  translucent: LayerBuffers
}

export interface MeshInput {
  cx: number
  cz: number
  volume: Uint8Array
  faceTiles: Uint16Array
}

type Vec3 = [number, number, number]

interface Face {
  dir: Vec3
  /** Bottom-left, bottom-right, top-right, top-left as seen from outside (counter-clockwise). */
  corners: Vec3[]
  shade: number
  /** The two axes (0 = x, 1 = y, 2 = z) that span the face. */
  axes: [number, number]
}

// Same order as the atlas faces: east, west, up, down, south, north.
const FACES: Face[] = [
  { dir: [1, 0, 0], corners: [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]], shade: 0.82, axes: [1, 2] },
  { dir: [-1, 0, 0], corners: [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]], shade: 0.82, axes: [1, 2] },
  { dir: [0, 1, 0], corners: [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]], shade: 1, axes: [0, 2] },
  { dir: [0, -1, 0], corners: [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], shade: 0.5, axes: [0, 2] },
  { dir: [0, 0, 1], corners: [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], shade: 0.66, axes: [0, 1] },
  { dir: [0, 0, -1], corners: [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0]], shade: 0.66, axes: [0, 1] },
]
const CORNER_UV = [[0, 0], [1, 0], [1, 1], [0, 1]]
const AO_LIGHT = [0.45, 0.62, 0.8, 1]
const WATER_DROP = 0.125
const SIDE_FACE = 4
const CROSS: Vec3[][] = [
  [[0.05, 0, 0.05], [0.95, 0, 0.95], [0.95, 1, 0.95], [0.05, 1, 0.05]],
  [[0.95, 0, 0.05], [0.05, 0, 0.95], [0.05, 1, 0.95], [0.95, 1, 0.05]],
]

/** Light level 0 (darkest) to 3 from the two side neighbors and the diagonal neighbor of a corner. */
export function cornerAo(side1: number, side2: number, corner: number): number {
  return side1 && side2 ? 0 : 3 - (side1 + side2 + corner)
}

/** Vertex colors are multiplied in linear space; convert so shading matches the sRGB mockup. */
export function srgbToLinear(value: number): number {
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
}

/** ±3% brightness per block so flat areas don't look printed. */
function tint(x: number, y: number, z: number): number {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(z, 1274126177)
  h = Math.imul(h ^ (h >>> 13), 1103515245)
  return 1 + (((h >>> 16) & 255) / 255 - 0.5) * 0.06
}

class LayerBuilder {
  positions: number[] = []
  uvs: number[] = []
  colors: number[] = []
  indices: number[] = []

  quad(corners: Vec3[], uv: [number, number, number, number], light: number[], flip: boolean): void {
    const base = this.positions.length / 3
    corners.forEach(([x, y, z], k) => {
      this.positions.push(x, y, z)
      this.uvs.push(CORNER_UV[k][0] ? uv[2] : uv[0], CORNER_UV[k][1] ? uv[3] : uv[1])
      const value = srgbToLinear(Math.min(1, light[k]))
      this.colors.push(value, value, value)
    })
    if (flip) this.indices.push(base + 1, base + 2, base + 3, base + 1, base + 3, base)
    else this.indices.push(base, base + 1, base + 2, base, base + 2, base + 3)
  }

  build(): LayerBuffers {
    return {
      positions: new Float32Array(this.positions),
      uvs: new Float32Array(this.uvs),
      colors: new Float32Array(this.colors),
      indices: new Uint32Array(this.indices),
    }
  }
}

export function meshColumn({ cx, cz, volume, faceTiles }: MeshInput): ColumnMesh {
  const opaque = new LayerBuilder()
  const cutout = new LayerBuilder()
  const translucent = new LayerBuilder()
  // -1 means below the world: treated as solid so the underside is never drawn.
  const idAt = (px: number, layer: number, pz: number) =>
    layer < 0 ? -1 : layer >= WORLD_HEIGHT ? AIR : volume[paddedIndex(px, layer, pz)]
  const opaqueAt = (px: number, layer: number, pz: number) => {
    const id = idAt(px, layer, pz)
    return id === -1 || LAYER_BY_ID[id] === LAYER_OPAQUE ? 1 : 0
  }
  const x0 = cx * CHUNK_SIZE - 1, z0 = cz * CHUNK_SIZE - 1

  for (let layer = 0; layer < WORLD_HEIGHT; layer++) {
    for (let pz = 1; pz <= CHUNK_SIZE; pz++) {
      for (let px = 1; px <= CHUNK_SIZE; px++) {
        const id = volume[paddedIndex(px, layer, pz)]
        if (id === AIR) continue
        const kind = LAYER_BY_ID[id]
        if (kind === 0) continue
        const wx = x0 + px, wy = WORLD_MIN_Y + layer, wz = z0 + pz
        const blockTint = tint(wx, wy, wz)

        if (kind === LAYER_CUTOUT) {
          const uv = tileUv(faceTiles[id * 6 + SIDE_FACE])
          for (const quad of CROSS) {
            cutout.quad(quad.map(([x, y, z]) => [wx + x, wy + y, wz + z] as Vec3), uv,
              [blockTint, blockTint, blockTint, blockTint], false)
          }
          continue
        }

        const builder = kind === LAYER_OPAQUE ? opaque : translucent
        const glow = GLOW_BY_ID[id] === 1
        const lowered = FLUID_BY_ID[id] === 1 && idAt(px, layer + 1, pz) !== id
        FACES.forEach((face, faceIndex) => {
          const [dx, dy, dz] = face.dir
          const nx = px + dx, nl = layer + dy, nz = pz + dz
          const neighbor = idAt(nx, nl, nz)
          if (neighbor === -1 || LAYER_BY_ID[neighbor] === LAYER_OPAQUE) return
          if (kind === LAYER_TRANSLUCENT && neighbor === id) return
          const aos: number[] = []
          const corners = face.corners.map((corner): Vec3 => {
            let ao = 3
            if (!glow) {
              const [u, v] = face.axes
              const a: Vec3 = [0, 0, 0], b: Vec3 = [0, 0, 0]
              a[u] = corner[u] ? 1 : -1
              b[v] = corner[v] ? 1 : -1
              ao = cornerAo(
                opaqueAt(nx + a[0], nl + a[1], nz + a[2]),
                opaqueAt(nx + b[0], nl + b[1], nz + b[2]),
                opaqueAt(nx + a[0] + b[0], nl + a[1] + b[1], nz + a[2] + b[2]),
              )
            }
            aos.push(ao)
            return [wx + corner[0], wy + (lowered && corner[1] === 1 ? 1 - WATER_DROP : corner[1]), wz + corner[2]]
          })
          const light = aos.map((ao) => (glow ? 1 : face.shade) * AO_LIGHT[ao] * blockTint)
          // Split along the diagonal that holds the odd corner so gradients don't crease.
          const flip = aos[0] + aos[2] > aos[1] + aos[3]
          builder.quad(corners, tileUv(faceTiles[id * 6 + faceIndex]), light, flip)
        })
      }
    }
  }
  return { opaque: opaque.build(), cutout: cutout.build(), translucent: translucent.build() }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/engine/mesher.test.ts`
Expected: 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/engine/mesher.ts frontend/src/engine/mesher.test.ts
git commit -m "feat: mesh block columns with face culling and ambient occlusion" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: WorldStore and block sync

**Files:**
- Create: `frontend/src/engine/worldStore.ts`
- Create: `frontend/src/engine/blockSync.ts`
- Test: `frontend/src/engine/worldStore.test.ts`, `frontend/src/engine/blockSync.test.ts`

**Interfaces:**
- Consumes: `AIR`, `blockDef`, `blockId` (Task 2); `blockAt`, `CHUNK_SIZE`, `columnIndex`, `DEFAULT_WORLD_SEED`, `WORLD_MIN_Y`, `WORLD_MAX_Y` (Task 5).
- Produces (`worldStore.ts`): `interface PlacedBlock { x; y; z; material: string }`, `type DirtyListener = (columns: string[]) => void`, `columnKey(cx, cz): string` (format `"cx,cz"`), `columnsTouching(x, z): string[]`, `class WorldStore` with `seed`, `getBlock(x, y, z): number`, `setBaseColumn(cx, cz, data)`, `dropBaseColumn(cx, cz)`, `applyServerChanges(changes, reset = false): string[]`, `setOverlay(blocks): string[]`, `editsNear(cx, cz): Int32Array` (x, y, z, id quadruples), `materialsNear(x, z, radius): Set<string>`, `subscribe(listener): () => void`.
- Produces (`blockSync.ts`): `interface BlocksPage { seq: number; changes: PlacedBlock[]; more: boolean }`, `class BlockSync` with `seq` and `syncTo(serverSeq): Promise<boolean>`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/engine/worldStore.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { blockId } from './blocks'
import { columnIndex } from './worldgen'
import { columnsTouching, WorldStore } from './worldStore'

describe('WorldStore', () => {
  it('falls back to worldgen for untouched cells', () => {
    const store = new WorldStore()
    expect(store.getBlock(0, -6, 0)).toBe(blockId('bedrock'))
    expect(store.getBlock(0, 200, 0)).toBe(0)
  })

  it('reads base columns and lets edits override them, including negative coordinates', () => {
    const store = new WorldStore()
    const column = new Uint8Array(16 * 16 * 128)
    column[columnIndex(15, 40, 0)] = blockId('clay')
    store.setBaseColumn(-1, -2, column)
    expect(store.getBlock(-1, 40, -32)).toBe(blockId('clay'))
    store.applyServerChanges([{ x: -1, y: 40, z: -32, material: 'air' }])
    expect(store.getBlock(-1, 40, -32)).toBe(0)
  })

  it('prefers server edits over the build overlay', () => {
    const store = new WorldStore()
    store.setOverlay([{ x: 3, y: 30, z: 3, material: 'limestone' }])
    expect(store.getBlock(3, 30, 3)).toBe(blockId('limestone'))
    store.applyServerChanges([{ x: 3, y: 30, z: 3, material: 'stone' }])
    expect(store.getBlock(3, 30, 3)).toBe(blockId('stone'))
  })

  it('marks neighbor columns dirty for border blocks', () => {
    expect(columnsTouching(5, 5)).toEqual(['0,0'])
    expect(columnsTouching(16, 5).sort()).toEqual(['0,0', '1,0'])
    expect(columnsTouching(15, 15).sort()).toEqual(['0,0', '0,1', '1,0', '1,1'])
    expect(columnsTouching(-16, 5).sort()).toEqual(['-1,0', '-2,0'])
  })

  it('reports only changed overlay cells', () => {
    const store = new WorldStore()
    const a = { x: 5, y: 30, z: 5, material: 'limestone' }
    const b = { x: 40, y: 30, z: 5, material: 'limestone' }
    expect(store.setOverlay([a, b]).sort()).toEqual(['0,0', '2,0'])
    expect(store.setOverlay([a])).toEqual(['2,0'])
    expect(store.setOverlay([a])).toEqual([])
    expect(store.getBlock(40, 30, 5)).not.toBe(blockId('limestone'))
  })

  it('clears server edits on reset', () => {
    const store = new WorldStore()
    store.applyServerChanges([{ x: 5, y: 30, z: 5, material: 'stone' }])
    expect(store.applyServerChanges([], true)).toEqual(['0,0'])
    expect(store.getBlock(5, 30, 5)).toBe(0)
  })

  it('collects edits for a column and its one-cell border', () => {
    const store = new WorldStore()
    store.setOverlay([{ x: 16, y: 30, z: 0, material: 'limestone' }])
    store.applyServerChanges([
      { x: 0, y: 30, z: 0, material: 'stone' },
      { x: 16, y: 30, z: 0, material: 'glass' },
      { x: 17, y: 30, z: 0, material: 'stone' },
    ])
    const edits = Array.from(store.editsNear(0, 0))
    const cells = []
    for (let i = 0; i < edits.length; i += 4) cells.push(edits.slice(i, i + 4))
    expect(cells).toContainEqual([0, 30, 0, blockId('stone')])
    expect(cells).toContainEqual([16, 30, 0, blockId('glass')])
    expect(cells).not.toContainEqual([17, 30, 0, blockId('stone')])
    expect(cells).toHaveLength(2)
  })

  it('finds nearby server-placed workstations', () => {
    const store = new WorldStore()
    store.applyServerChanges([{ x: 75, y: 1, z: 0, material: 'crafting_table' }, { x: 99, y: 1, z: 0, material: 'furnace' }])
    expect([...store.materialsNear(73, 0, 6)]).toEqual(['crafting_table'])
  })

  it('tells subscribers which columns changed', () => {
    const store = new WorldStore()
    const seen: string[][] = []
    const unsubscribe = store.subscribe((columns) => seen.push(columns))
    store.applyServerChanges([{ x: 5, y: 30, z: 5, material: 'stone' }])
    unsubscribe()
    store.applyServerChanges([{ x: 6, y: 30, z: 5, material: 'stone' }])
    expect(seen).toEqual([['0,0']])
  })
})
```

Create `frontend/src/engine/blockSync.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { BlockSync, type BlocksPage } from './blockSync'
import type { PlacedBlock } from './worldStore'

function setup(pages: Record<number, BlocksPage>) {
  const calls: number[] = []
  const applied: { changes: PlacedBlock[]; reset: boolean }[] = []
  const sync = new BlockSync(async (since) => {
    calls.push(since)
    const page = pages[since]
    if (!page) throw new Error('offline')
    return page
  }, (changes, reset) => { applied.push({ changes, reset }) })
  return { sync, calls, applied }
}

const stone = (x: number): PlacedBlock => ({ x, y: 30, z: 0, material: 'stone' })

describe('BlockSync', () => {
  it('pages until the server says there is no more', async () => {
    const { sync, calls, applied } = setup({
      0: { seq: 2, changes: [stone(1), stone(2)], more: true },
      2: { seq: 3, changes: [stone(3)], more: false },
    })
    expect(await sync.syncTo(3)).toBe(true)
    expect(calls).toEqual([0, 2])
    expect(applied.flatMap((batch) => batch.changes.map((change) => change.x))).toEqual([1, 2, 3])
    expect(sync.seq).toBe(3)
  })

  it('does nothing when already in sync', async () => {
    const { sync, calls } = setup({})
    expect(await sync.syncTo(0)).toBe(false)
    expect(calls).toEqual([])
  })

  it('resyncs from zero with a reset when the server seq goes backwards', async () => {
    const { sync, applied } = setup({
      0: { seq: 5, changes: [stone(1)], more: false },
    })
    sync.seq = 9
    await sync.syncTo(5)
    expect(applied).toEqual([{ changes: [stone(1)], reset: true }])
    expect(sync.seq).toBe(5)
  })

  it('keeps its place and its pending reset when a fetch fails', async () => {
    const pages: Record<number, BlocksPage> = {}
    const { sync, applied } = setup(pages)
    sync.seq = 9
    await expect(sync.syncTo(5)).rejects.toThrow('offline')
    expect(sync.seq).toBe(0)
    pages[0] = { seq: 5, changes: [], more: false }
    await sync.syncTo(5)
    expect(applied).toEqual([{ changes: [], reset: true }])
  })

  it('skips a call while another sync is running', async () => {
    let release: (page: BlocksPage) => void = () => {}
    const sync = new BlockSync(() => new Promise<BlocksPage>((resolve) => { release = resolve }), () => {})
    const first = sync.syncTo(1)
    expect(await sync.syncTo(1)).toBe(false)
    release({ seq: 1, changes: [], more: false })
    expect(await first).toBe(true)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/engine/worldStore.test.ts src/engine/blockSync.test.ts`
Expected: FAIL with `Failed to resolve import "./worldStore"` and `"./blockSync"`

- [ ] **Step 3: Write the store**

Create `frontend/src/engine/worldStore.ts`:

```ts
import { AIR, blockDef, blockId } from './blocks'
import { blockAt, CHUNK_SIZE, columnIndex, DEFAULT_WORLD_SEED, WORLD_MAX_Y, WORLD_MIN_Y } from './worldgen'

export interface PlacedBlock {
  x: number
  y: number
  z: number
  material: string
}

export type DirtyListener = (columns: string[]) => void
type CellMap = Map<string, Map<string, number>>

export function columnKey(cx: number, cz: number): string {
  return `${cx},${cz}`
}

function cellKey(x: number, y: number, z: number): string {
  return `${x},${y},${z}`
}

function chunkOf(value: number): number {
  return Math.floor(value / CHUNK_SIZE)
}

/** Columns whose mesh can change when a block at (x, z) changes: its own plus neighbors on borders. */
export function columnsTouching(x: number, z: number): string[] {
  const cx = chunkOf(x), cz = chunkOf(z)
  const lx = x - cx * CHUNK_SIZE, lz = z - cz * CHUNK_SIZE
  const xs = [cx, ...(lx === 0 ? [cx - 1] : lx === CHUNK_SIZE - 1 ? [cx + 1] : [])]
  const zs = [cz, ...(lz === 0 ? [cz - 1] : lz === CHUNK_SIZE - 1 ? [cz + 1] : [])]
  return xs.flatMap((a) => zs.map((b) => columnKey(a, b)))
}

function put(target: CellMap, x: number, y: number, z: number, id: number): void {
  const column = columnKey(chunkOf(x), chunkOf(z))
  let cells = target.get(column)
  if (!cells) {
    cells = new Map()
    target.set(column, cells)
  }
  cells.set(cellKey(x, y, z), id)
}

function markCell(dirty: Set<string>, cell: string): void {
  const [x, , z] = cell.split(',').map(Number)
  for (const key of columnsTouching(x, z)) dirty.add(key)
}

/**
 * Every block the viewer knows about. Precedence per cell: server edit, then build
 * overlay, then the generated column, then worldgen.
 */
export class WorldStore {
  readonly seed: string
  private readonly base = new Map<string, Uint8Array>()
  private readonly server: CellMap = new Map()
  private overlay: CellMap = new Map()
  private overlayCells = new Map<string, number>()
  private readonly listeners = new Set<DirtyListener>()

  constructor(seed = DEFAULT_WORLD_SEED) {
    this.seed = seed
  }

  getBlock(x: number, y: number, z: number): number {
    if (y < WORLD_MIN_Y || y > WORLD_MAX_Y) return AIR
    const cx = chunkOf(x), cz = chunkOf(z)
    const column = columnKey(cx, cz)
    const cell = cellKey(x, y, z)
    const edited = this.server.get(column)?.get(cell) ?? this.overlay.get(column)?.get(cell)
    if (edited !== undefined) return edited
    const base = this.base.get(column)
    if (base) return base[columnIndex(x - cx * CHUNK_SIZE, y, z - cz * CHUNK_SIZE)]
    return blockId(blockAt(x, y, z, this.seed))
  }

  setBaseColumn(cx: number, cz: number, data: Uint8Array): void {
    this.base.set(columnKey(cx, cz), data)
  }

  dropBaseColumn(cx: number, cz: number): void {
    this.base.delete(columnKey(cx, cz))
  }

  applyServerChanges(changes: PlacedBlock[], reset = false): string[] {
    const dirty = new Set<string>()
    if (reset) {
      for (const cells of this.server.values()) for (const cell of cells.keys()) markCell(dirty, cell)
      this.server.clear()
    }
    for (const { x, y, z, material } of changes) {
      put(this.server, x, y, z, blockId(material))
      for (const key of columnsTouching(x, z)) dirty.add(key)
    }
    return this.emit(dirty)
  }

  /** Replace the client-only build overlay and report the columns that changed. */
  setOverlay(blocks: PlacedBlock[]): string[] {
    const next = new Map<string, number>()
    for (const { x, y, z, material } of blocks) next.set(cellKey(x, y, z), blockId(material))
    const dirty = new Set<string>()
    for (const [cell, id] of next) if (this.overlayCells.get(cell) !== id) markCell(dirty, cell)
    for (const cell of this.overlayCells.keys()) if (!next.has(cell)) markCell(dirty, cell)
    if (dirty.size === 0) return []
    this.overlayCells = next
    this.overlay = new Map()
    for (const [cell, id] of next) {
      const [x, y, z] = cell.split(',').map(Number)
      put(this.overlay, x, y, z, id)
    }
    return this.emit(dirty)
  }

  /** Edits inside a column and its one-cell border as x, y, z, id quadruples. Server edits win. */
  editsNear(cx: number, cz: number): Int32Array {
    const minX = cx * CHUNK_SIZE - 1, maxX = cx * CHUNK_SIZE + CHUNK_SIZE
    const minZ = cz * CHUNK_SIZE - 1, maxZ = cz * CHUNK_SIZE + CHUNK_SIZE
    const merged = new Map<string, number[]>()
    for (const source of [this.overlay, this.server]) {
      for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) {
        const cells = source.get(columnKey(cx + dx, cz + dz))
        if (!cells) continue
        for (const [cell, id] of cells) {
          const [x, y, z] = cell.split(',').map(Number)
          if (x >= minX && x <= maxX && z >= minZ && z <= maxZ) merged.set(cell, [x, y, z, id])
        }
      }
    }
    return Int32Array.from([...merged.values()].flat())
  }

  /** Names of server-placed blocks within `radius` of (x, z), for workstation checks. */
  materialsNear(x: number, z: number, radius: number): Set<string> {
    const found = new Set<string>()
    for (const cells of this.server.values()) {
      for (const [cell, id] of cells) {
        const [bx, , bz] = cell.split(',').map(Number)
        if (id !== AIR && Math.hypot(bx - x, bz - z) <= radius) found.add(blockDef(id).name)
      }
    }
    return found
  }

  subscribe(listener: DirtyListener): () => void {
    this.listeners.add(listener)
    return () => { this.listeners.delete(listener) }
  }

  private emit(dirty: Set<string>): string[] {
    const keys = [...dirty]
    if (keys.length) for (const listener of this.listeners) listener(keys)
    return keys
  }
}
```

- [ ] **Step 4: Write the sync client**

Create `frontend/src/engine/blockSync.ts`:

```ts
import type { PlacedBlock } from './worldStore'

export interface BlocksPage {
  seq: number
  changes: PlacedBlock[]
  more: boolean
}

type FetchPage = (since: number) => Promise<BlocksPage>
type ApplyChanges = (changes: PlacedBlock[], reset: boolean) => void

/** Pages /api/mimo/blocks into the store. Errors reach the caller; the next poll retries. */
export class BlockSync {
  seq = 0
  private readonly fetchPage: FetchPage
  private readonly apply: ApplyChanges
  private running = false
  private pendingReset = false

  constructor(fetchPage: FetchPage, apply: ApplyChanges) {
    this.fetchPage = fetchPage
    this.apply = apply
  }

  async syncTo(serverSeq: number): Promise<boolean> {
    if (this.running || serverSeq === this.seq) return false
    this.running = true
    try {
      if (serverSeq < this.seq) {
        // The server database was reset. Start over and drop local server edits.
        this.seq = 0
        this.pendingReset = true
      }
      let more = true
      while (more) {
        const page = await this.fetchPage(this.seq)
        this.apply(page.changes, this.pendingReset)
        this.pendingReset = false
        this.seq = page.seq
        more = page.more
      }
      return true
    } finally {
      this.running = false
    }
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/engine/worldStore.test.ts src/engine/blockSync.test.ts`
Expected: 14 tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/engine/worldStore.ts frontend/src/engine/worldStore.test.ts frontend/src/engine/blockSync.ts frontend/src/engine/blockSync.test.ts
git commit -m "feat: add world store and incremental block sync" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Worker, column renderer and BlockWorld component

**Files:**
- Create: `frontend/src/engine/columnVolume.ts`
- Create: `frontend/src/engine/workerProtocol.ts`
- Create: `frontend/src/engine/world.worker.ts`
- Create: `frontend/src/engine/columnRenderer.ts`
- Create: `frontend/src/engine/BlockWorld.tsx`
- Test: `frontend/src/engine/columnVolume.test.ts`, `frontend/src/engine/columnRenderer.test.ts`

**Interfaces:**
- Consumes: `generateColumn`, `columnIndex`, `CHUNK_SIZE`, `WORLD_HEIGHT`, `WORLD_MIN_Y` (Task 5); `meshColumn`, `PADDED`, `paddedIndex`, `ColumnMesh`, `LayerBuffers` (Task 8); `buildAtlas`, `animateWater` (Task 7); `WorldStore`, `columnKey` (Task 9).
- Produces: `class ColumnCache(seed, limit = 256)` with `get(cx, cz)` and `size`; `buildPaddedVolume(cx, cz, columnAt, edits): Uint8Array`; worker message types `WorkerRequest`, `WorkerResponse`, `MeshedResponse`; `meshTransfers(mesh): ArrayBuffer[]`; `MAX_IN_FLIGHT = 4`; `interface WorldStats { columns; pending; lastMeshMs }`; `createWorldWorker(): Worker`; `class ColumnRenderer(store, group, onError, worker?)` with `setView(centerX, centerZ, viewDistance)`, `tick(delta)`, `stats()`, `restoreGpuResources()`, `dispose()`; default export `BlockWorld` React component with props `{ store, centerX, centerZ, viewDistance, onStats?, onError? }` and `interface ViewStats extends WorldStats { fps; drawCalls }`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/engine/columnVolume.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildPaddedVolume, ColumnCache } from './columnVolume'
import { paddedIndex } from './mesher'
import { columnIndex, WORLD_MIN_Y } from './worldgen'

const filled = (id: number) => new Uint8Array(16 * 16 * 128).fill(id)

describe('buildPaddedVolume', () => {
  const columns = new Map([['0,0', filled(3)], ['-1,0', filled(4)], ['1,0', filled(5)]])
  const columnAt = (cx: number, cz: number) => columns.get(`${cx},${cz}`) ?? filled(9)

  it('fills the border from neighbor columns', () => {
    const volume = buildPaddedVolume(0, 0, columnAt, new Int32Array())
    expect(volume[paddedIndex(1, 10, 5)]).toBe(3)
    expect(volume[paddedIndex(0, 10, 5)]).toBe(4)
    expect(volume[paddedIndex(17, 10, 5)]).toBe(5)
    expect(volume[paddedIndex(5, 10, 0)]).toBe(9)
  })

  it('reads the right cell from the neighbor column', () => {
    const west = filled(0)
    west[columnIndex(15, 20, 7)] = 42
    const volume = buildPaddedVolume(0, 0, (cx) => (cx === -1 ? west : filled(0)), new Int32Array())
    expect(volume[paddedIndex(0, 20 - WORLD_MIN_Y, 8)]).toBe(42)
  })

  it('applies edits in range and ignores the rest', () => {
    const edits = Int32Array.from([0, 20, 0, 7, -1, 20, 0, 8, 40, 20, 0, 9])
    const volume = buildPaddedVolume(0, 0, columnAt, edits)
    expect(volume[paddedIndex(1, 20 - WORLD_MIN_Y, 1)]).toBe(7)
    expect(volume[paddedIndex(0, 20 - WORLD_MIN_Y, 1)]).toBe(8)
  })
})

describe('ColumnCache', () => {
  it('generates once and evicts the least recently used column', () => {
    const cache = new ColumnCache('1', 2)
    const first = cache.get(0, 0)
    expect(cache.get(0, 0)).toBe(first)
    cache.get(1, 0)
    cache.get(0, 0)
    cache.get(2, 0)
    expect(cache.size).toBe(2)
    expect(cache.get(0, 0)).toBe(first)
  })
})
```

Create `frontend/src/engine/columnRenderer.test.ts`:

```ts
import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import { ColumnRenderer, MAX_IN_FLIGHT } from './columnRenderer'
import type { LayerBuffers } from './mesher'
import type { MeshRequest, WorkerResponse } from './workerProtocol'
import { WorldStore } from './worldStore'

class FakeWorker {
  posted: MeshRequest[] = []
  onmessage: ((event: MessageEvent<WorkerResponse>) => void) | null = null
  onerror: ((event: ErrorEvent) => void) | null = null
  terminated = false
  postMessage(message: MeshRequest) { this.posted.push(message) }
  terminate() { this.terminated = true }
  reply(response: WorkerResponse) { this.onmessage?.({ data: response } as MessageEvent<WorkerResponse>) }
}

const empty = (): LayerBuffers => ({
  positions: new Float32Array(0), uvs: new Float32Array(0), colors: new Float32Array(0), indices: new Uint32Array(0),
})
const oneQuad = (): LayerBuffers => ({
  positions: new Float32Array(12), uvs: new Float32Array(8), colors: new Float32Array(12),
  indices: new Uint32Array([0, 1, 2, 0, 2, 3]),
})

function meshed(request: MeshRequest): WorkerResponse {
  return {
    type: 'meshed', key: request.key, cx: request.cx, cz: request.cz, version: request.version,
    base: new Uint8Array(16 * 16 * 128), mesh: { opaque: oneQuad(), cutout: empty(), translucent: empty() }, ms: 2,
  }
}

function setup() {
  const store = new WorldStore('1')
  const group = new THREE.Group()
  const worker = new FakeWorker()
  const onError = vi.fn()
  const renderer = new ColumnRenderer(store, group, onError, worker as unknown as Worker)
  return { store, group, worker, onError, renderer }
}

describe('ColumnRenderer', () => {
  it('requests the nearest columns first and caps work in flight', () => {
    const { worker, renderer } = setup()
    renderer.setView(8, 8, 1)
    expect(worker.posted).toHaveLength(MAX_IN_FLIGHT)
    expect(worker.posted[0].key).toBe('0,0')
    // Each reply frees a slot, so the list grows while we answer it.
    for (let i = 0; i < worker.posted.length; i++) worker.reply(meshed(worker.posted[i]))
    expect(worker.posted).toHaveLength(9)
  })

  it('adds meshes for non-empty layers and remembers the base column', () => {
    const { store, group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    const response = meshed(worker.posted[0])
    if (response.type === 'meshed') response.base[0] = 42
    worker.reply(response)
    expect(group.children).toHaveLength(1)
    expect(store.getBlock(0, -8, 0)).toBe(42)
    expect(renderer.stats()).toMatchObject({ columns: 1, pending: 0, lastMeshMs: 2 })
  })

  it('ignores a stale reply after a block change', () => {
    const { store, group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    store.applyServerChanges([{ x: 3, y: 30, z: 3, material: 'stone' }])
    expect(worker.posted.map((request) => request.version)).toEqual([1, 2])
    worker.reply(meshed(worker.posted[0]))
    expect(group.children).toHaveLength(0)
    worker.reply(meshed(worker.posted[1]))
    expect(group.children).toHaveLength(1)
  })

  it('retries a failed column once, then logs', () => {
    const { worker, renderer } = setup()
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderer.setView(8, 8, 0)
    worker.reply({ type: 'error', key: '0,0', version: 1, message: 'boom' })
    expect(worker.posted).toHaveLength(2)
    worker.reply({ type: 'error', key: '0,0', version: 2, message: 'boom' })
    expect(worker.posted).toHaveLength(2)
    expect(log).toHaveBeenCalledOnce()
    log.mockRestore()
  })

  it('unloads columns that fall out of range', () => {
    const { group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    worker.reply(meshed(worker.posted[0]))
    renderer.setView(8 + 16 * 5, 8, 0)
    expect(group.children).toHaveLength(0)
    expect(worker.posted.at(-1)?.key).toBe('5,0')
  })

  it('reports a worker crash and cleans up on dispose', () => {
    const { group, worker, onError, renderer } = setup()
    renderer.setView(8, 8, 0)
    worker.reply(meshed(worker.posted[0]))
    worker.onerror?.({ preventDefault() {} } as ErrorEvent)
    expect(onError).toHaveBeenCalledOnce()
    renderer.dispose()
    expect(worker.terminated).toBe(true)
    expect(group.children).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/engine/columnVolume.test.ts src/engine/columnRenderer.test.ts`
Expected: FAIL with `Failed to resolve import "./columnVolume"` and `"./columnRenderer"`

- [ ] **Step 3: Write the volume builder**

Create `frontend/src/engine/columnVolume.ts`:

```ts
import { PADDED, paddedIndex } from './mesher'
import { CHUNK_SIZE, columnIndex, generateColumn, WORLD_HEIGHT, WORLD_MIN_Y } from './worldgen'

/** Generated columns, least recently used evicted first. */
export class ColumnCache {
  readonly seed: string
  private readonly limit: number
  private readonly columns = new Map<string, Uint8Array>()

  constructor(seed: string, limit = 256) {
    this.seed = seed
    this.limit = limit
  }

  get size(): number {
    return this.columns.size
  }

  get(cx: number, cz: number): Uint8Array {
    const key = `${cx},${cz}`
    const cached = this.columns.get(key)
    if (cached) {
      this.columns.delete(key)
      this.columns.set(key, cached)
      return cached
    }
    const column = generateColumn(cx, cz, this.seed)
    this.columns.set(key, column)
    if (this.columns.size > this.limit) this.columns.delete(this.columns.keys().next().value!)
    return column
  }
}

/** The mesher's input: this column plus a one-cell border, with edits applied on top. */
export function buildPaddedVolume(cx: number, cz: number, columnAt: (cx: number, cz: number) => Uint8Array,
  edits: Int32Array): Uint8Array {
  const volume = new Uint8Array(PADDED * PADDED * WORLD_HEIGHT)
  for (let pz = 0; pz < PADDED; pz++) {
    const wz = cz * CHUNK_SIZE + pz - 1
    const sourceZ = Math.floor(wz / CHUNK_SIZE), lz = wz - sourceZ * CHUNK_SIZE
    for (let px = 0; px < PADDED; px++) {
      const wx = cx * CHUNK_SIZE + px - 1
      const sourceX = Math.floor(wx / CHUNK_SIZE), lx = wx - sourceX * CHUNK_SIZE
      const source = columnAt(sourceX, sourceZ)
      for (let layer = 0; layer < WORLD_HEIGHT; layer++) {
        volume[paddedIndex(px, layer, pz)] = source[columnIndex(lx, WORLD_MIN_Y + layer, lz)]
      }
    }
  }
  for (let i = 0; i < edits.length; i += 4) {
    const px = edits[i] - cx * CHUNK_SIZE + 1
    const layer = edits[i + 1] - WORLD_MIN_Y
    const pz = edits[i + 2] - cz * CHUNK_SIZE + 1
    if (px < 0 || px >= PADDED || pz < 0 || pz >= PADDED || layer < 0 || layer >= WORLD_HEIGHT) continue
    volume[paddedIndex(px, layer, pz)] = edits[i + 3]
  }
  return volume
}
```

- [ ] **Step 4: Write the worker protocol and worker**

Create `frontend/src/engine/workerProtocol.ts`:

```ts
import type { ColumnMesh } from './mesher'

export interface MeshRequest {
  type: 'mesh'
  key: string
  cx: number
  cz: number
  seed: string
  /** x, y, z, id quadruples for the column and its one-cell border. */
  edits: Int32Array
  version: number
}

export type WorkerRequest = MeshRequest

export interface MeshedResponse {
  type: 'meshed'
  key: string
  cx: number
  cz: number
  version: number
  /** The generated column without edits, for WorldStore.getBlock. */
  base: Uint8Array
  mesh: ColumnMesh
  ms: number
}

export interface ErrorResponse {
  type: 'error'
  key: string
  version: number
  message: string
}

export type WorkerResponse = MeshedResponse | ErrorResponse

export function meshTransfers(mesh: ColumnMesh): ArrayBuffer[] {
  return [mesh.opaque, mesh.cutout, mesh.translucent].flatMap((layer) => [
    layer.positions.buffer, layer.uvs.buffer, layer.colors.buffer, layer.indices.buffer,
  ] as ArrayBuffer[])
}
```

Create `frontend/src/engine/world.worker.ts`:

```ts
import { buildAtlas } from './atlas'
import { buildPaddedVolume, ColumnCache } from './columnVolume'
import { meshColumn } from './mesher'
import { meshTransfers, type WorkerRequest, type WorkerResponse } from './workerProtocol'

// The DOM lib types `self` as Window; describe the two worker members this file uses.
const scope = self as unknown as {
  onmessage: ((event: MessageEvent<WorkerRequest>) => void) | null
  postMessage: (message: WorkerResponse, transfer: Transferable[]) => void
}

const { faceTiles } = buildAtlas()
let cache: ColumnCache | null = null

scope.onmessage = (event) => {
  const request = event.data
  const started = performance.now()
  try {
    if (!cache || cache.seed !== request.seed) cache = new ColumnCache(request.seed)
    const columns = cache
    const volume = buildPaddedVolume(request.cx, request.cz, (cx, cz) => columns.get(cx, cz), request.edits)
    const mesh = meshColumn({ cx: request.cx, cz: request.cz, volume, faceTiles })
    const base = columns.get(request.cx, request.cz).slice()
    scope.postMessage({
      type: 'meshed', key: request.key, cx: request.cx, cz: request.cz, version: request.version,
      base, mesh, ms: performance.now() - started,
    }, [base.buffer as ArrayBuffer, ...meshTransfers(mesh)])
  } catch (error) {
    scope.postMessage({
      type: 'error', key: request.key, version: request.version,
      message: error instanceof Error ? error.message : String(error),
    }, [])
  }
}
```

- [ ] **Step 5: Write the renderer**

Create `frontend/src/engine/columnRenderer.ts`:

```ts
import * as THREE from 'three'
import { animateWater, buildAtlas, type Atlas } from './atlas'
import type { LayerBuffers } from './mesher'
import type { MeshedResponse, WorkerRequest, WorkerResponse } from './workerProtocol'
import { columnKey, type WorldStore } from './worldStore'
import { CHUNK_SIZE } from './worldgen'

export const MAX_IN_FLIGHT = 4
const WATER_FRAME_SECONDS = 0.25
const LAYER_NAMES = ['opaque', 'cutout', 'translucent'] as const
type LayerName = (typeof LAYER_NAMES)[number]

export interface WorldStats {
  columns: number
  pending: number
  lastMeshMs: number
}

interface ColumnEntry {
  cx: number
  cz: number
  version: number
  failures: number
  meshes: THREE.Mesh[]
}

export function createWorldWorker(): Worker {
  return new Worker(new URL('./world.worker.ts', import.meta.url), { type: 'module' })
}

function toGeometry(buffers: LayerBuffers): THREE.BufferGeometry | null {
  if (buffers.indices.length === 0) return null
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(buffers.positions, 3))
  geometry.setAttribute('uv', new THREE.BufferAttribute(buffers.uvs, 2))
  geometry.setAttribute('color', new THREE.BufferAttribute(buffers.colors, 3))
  geometry.setIndex(new THREE.BufferAttribute(buffers.indices, 1))
  geometry.computeBoundingSphere()
  return geometry
}

/** Loads columns around a point, meshes them in a worker and keeps their three.js meshes. */
export class ColumnRenderer {
  lastMeshMs = 0
  private readonly store: WorldStore
  private readonly group: THREE.Group
  private readonly onError: (message: string) => void
  private readonly worker: Worker
  private readonly atlas: Atlas
  private readonly texture: THREE.DataTexture
  private readonly materials: Record<LayerName, THREE.MeshBasicMaterial>
  private readonly entries = new Map<string, ColumnEntry>()
  private readonly unsubscribe: () => void
  private queue: string[] = []
  private inFlight = 0
  private center = { cx: 0, cz: 0 }
  private waterClock = 0
  private waterStep = 0

  constructor(store: WorldStore, group: THREE.Group, onError: (message: string) => void,
    worker: Worker = createWorldWorker()) {
    this.store = store
    this.group = group
    this.onError = onError
    this.worker = worker
    this.atlas = buildAtlas()
    this.texture = new THREE.DataTexture(this.atlas.data, this.atlas.size, this.atlas.size, THREE.RGBAFormat)
    this.texture.magFilter = THREE.NearestFilter
    this.texture.minFilter = THREE.NearestFilter
    this.texture.generateMipmaps = false
    this.texture.colorSpace = THREE.SRGBColorSpace
    this.texture.needsUpdate = true
    this.materials = {
      opaque: new THREE.MeshBasicMaterial({ map: this.texture, vertexColors: true }),
      cutout: new THREE.MeshBasicMaterial({ map: this.texture, vertexColors: true, alphaTest: 0.5, side: THREE.DoubleSide }),
      translucent: new THREE.MeshBasicMaterial({ map: this.texture, vertexColors: true, transparent: true, depthWrite: false }),
    }
    this.worker.onmessage = (event: MessageEvent<WorkerResponse>) => this.receive(event.data)
    this.worker.onerror = (event) => {
      event.preventDefault()
      this.onError('The world renderer stopped. Try again to restart it.')
    }
    this.unsubscribe = store.subscribe((keys) => {
      for (const key of keys) if (this.entries.has(key)) this.enqueue(key)
      this.pump()
    })
  }

  setView(centerX: number, centerZ: number, viewDistance: number): void {
    const cx = Math.floor(centerX / CHUNK_SIZE), cz = Math.floor(centerZ / CHUNK_SIZE)
    this.center = { cx, cz }
    for (const [key, entry] of [...this.entries]) {
      if (Math.max(Math.abs(entry.cx - cx), Math.abs(entry.cz - cz)) > viewDistance + 2) this.unload(key, entry)
    }
    for (let dx = -viewDistance; dx <= viewDistance; dx++) {
      for (let dz = -viewDistance; dz <= viewDistance; dz++) {
        const key = columnKey(cx + dx, cz + dz)
        if (this.entries.has(key)) continue
        this.entries.set(key, { cx: cx + dx, cz: cz + dz, version: 0, failures: 0, meshes: [] })
        this.enqueue(key)
      }
    }
    const distance = (key: string) => {
      const entry = this.entries.get(key)
      return entry ? (entry.cx - cx) ** 2 + (entry.cz - cz) ** 2 : Infinity
    }
    this.queue.sort((a, b) => distance(a) - distance(b))
    this.pump()
  }

  tick(delta: number): void {
    this.waterClock += delta
    if (this.waterClock < WATER_FRAME_SECONDS) return
    this.waterClock %= WATER_FRAME_SECONDS
    this.waterStep += 1
    animateWater(this.atlas, this.waterStep)
    this.texture.needsUpdate = true
  }

  stats(): WorldStats {
    let columns = 0
    for (const entry of this.entries.values()) if (entry.meshes.length) columns += 1
    return { columns, pending: this.queue.length + this.inFlight, lastMeshMs: this.lastMeshMs }
  }

  /** After a lost WebGL context comes back, upload everything again. */
  restoreGpuResources(): void {
    this.texture.needsUpdate = true
    for (const entry of this.entries.values()) {
      for (const mesh of entry.meshes) {
        for (const attribute of Object.values(mesh.geometry.attributes)) attribute.needsUpdate = true
        if (mesh.geometry.index) mesh.geometry.index.needsUpdate = true
      }
    }
  }

  dispose(): void {
    this.unsubscribe()
    this.worker.terminate()
    for (const [key, entry] of [...this.entries]) this.unload(key, entry)
    for (const material of Object.values(this.materials)) material.dispose()
    this.texture.dispose()
  }

  private enqueue(key: string): void {
    if (!this.queue.includes(key)) this.queue.push(key)
  }

  private pump(): void {
    while (this.inFlight < MAX_IN_FLIGHT && this.queue.length) {
      const key = this.queue.shift()!
      const entry = this.entries.get(key)
      if (!entry) continue
      entry.version += 1
      const request: WorkerRequest = {
        type: 'mesh', key, cx: entry.cx, cz: entry.cz, seed: this.store.seed,
        edits: this.store.editsNear(entry.cx, entry.cz), version: entry.version,
      }
      this.inFlight += 1
      this.worker.postMessage(request, [request.edits.buffer as ArrayBuffer])
    }
  }

  private receive(response: WorkerResponse): void {
    this.inFlight = Math.max(0, this.inFlight - 1)
    const entry = this.entries.get(response.key)
    if (entry && response.version === entry.version) {
      if (response.type === 'meshed') this.install(entry, response)
      else if (entry.failures++ < 1) this.enqueue(response.key)
      else console.error(`Column ${response.key} could not be meshed: ${response.message}`)
    }
    this.pump()
  }

  private install(entry: ColumnEntry, response: MeshedResponse): void {
    this.removeMeshes(entry)
    for (const name of LAYER_NAMES) {
      const geometry = toGeometry(response.mesh[name])
      if (!geometry) continue
      const mesh = new THREE.Mesh(geometry, this.materials[name])
      if (name === 'translucent') mesh.renderOrder = 1
      mesh.matrixAutoUpdate = false
      entry.meshes.push(mesh)
      this.group.add(mesh)
    }
    entry.failures = 0
    this.store.setBaseColumn(entry.cx, entry.cz, response.base)
    this.lastMeshMs = response.ms
  }

  private removeMeshes(entry: ColumnEntry): void {
    for (const mesh of entry.meshes) {
      this.group.remove(mesh)
      mesh.geometry.dispose()
    }
    entry.meshes = []
  }

  private unload(key: string, entry: ColumnEntry): void {
    this.removeMeshes(entry)
    this.entries.delete(key)
    this.queue = this.queue.filter((queued) => queued !== key)
    this.store.dropBaseColumn(entry.cx, entry.cz)
  }
}
```

In the stale-reply test, `setView` posts version 1 and the store change posts version 2 right away because only one request is in flight.

- [ ] **Step 6: Write the React wrapper**

Create `frontend/src/engine/BlockWorld.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { ColumnRenderer, type WorldStats } from './columnRenderer'
import type { WorldStore } from './worldStore'

export interface ViewStats extends WorldStats {
  fps: number
  drawCalls: number
}

interface BlockWorldProps {
  store: WorldStore
  centerX: number
  centerZ: number
  viewDistance: number
  onStats?: (stats: ViewStats) => void
  onError?: (message: string) => void
}

export default function BlockWorld({ store, centerX, centerZ, viewDistance, onStats, onError }: BlockWorldProps) {
  const { gl } = useThree()
  const [group] = useState(() => new THREE.Group())
  const renderer = useRef<ColumnRenderer | null>(null)
  const onErrorRef = useRef(onError)
  const statsClock = useRef({ elapsed: 0, frames: 0 })

  useEffect(() => { onErrorRef.current = onError }, [onError])

  useEffect(() => {
    const next = new ColumnRenderer(store, group, (message) => onErrorRef.current?.(message))
    renderer.current = next
    return () => {
      next.dispose()
      renderer.current = null
    }
  }, [store, group])

  useEffect(() => {
    renderer.current?.setView(centerX, centerZ, viewDistance)
  }, [store, centerX, centerZ, viewDistance])

  useEffect(() => {
    const canvas = gl.domElement
    const restore = () => renderer.current?.restoreGpuResources()
    canvas.addEventListener('webglcontextrestored', restore)
    return () => canvas.removeEventListener('webglcontextrestored', restore)
  }, [gl])

  useFrame((_, delta) => {
    const current = renderer.current
    if (!current) return
    current.tick(delta)
    if (!onStats) return
    const clock = statsClock.current
    clock.elapsed += delta
    clock.frames += 1
    if (clock.elapsed < 0.5) return
    onStats({ ...current.stats(), fps: Math.round(clock.frames / clock.elapsed), drawCalls: gl.info.render.calls })
    clock.elapsed = 0
    clock.frames = 0
  })

  return <primitive object={group} />
}
```

- [ ] **Step 7: Run tests and the build**

Run: `cd frontend && npm test && npm run build`
Expected: all tests pass; build succeeds and emits a separate worker chunk (look for `world.worker` in the `dist/assets` listing).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/engine/columnVolume.ts frontend/src/engine/columnVolume.test.ts frontend/src/engine/workerProtocol.ts frontend/src/engine/world.worker.ts frontend/src/engine/columnRenderer.ts frontend/src/engine/columnRenderer.test.ts frontend/src/engine/BlockWorld.tsx
git commit -m "feat: mesh columns in a worker and render them with three.js" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Wire the engine into /preview

**Files:**
- Modify: `frontend/src/components/world/worldPlanner.ts` (whole file)
- Modify: `frontend/src/components/world/previewWorld.ts` (keep only the pet)
- Delete: `frontend/src/components/world/expandingWorld.ts`
- Modify: `frontend/src/pages/WorldPreview.tsx` (whole file)
- Test: `frontend/src/components/world/worldPlanner.test.ts`

**Interfaces:**
- Consumes: `PlacedBlock`, `WorldStore` (Task 9); `BlockSync`, `BlocksPage` (Task 9); `BlockWorld`, `ViewStats` (Task 10); `hasBlock`, `BLOCKS`, `AIR` (Task 2); `DEFAULT_WORLD_SEED`, `terrainHeight` (Task 5); `/api/mimo/blocks` and `blocks_seq` (Task 6).
- Produces: `ORBITAL_STATION`, `interface WorldPlan` (unchanged), `interface BuildProject { name; site; standOff; blocks: PlacedBlock[] }`, `compileWorldPlan(plan): BuildProject`, `overlayBlocks(plans, currentIndex, stepIndex): PlacedBlock[]`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/world/worldPlanner.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { hasBlock } from '../../engine/blocks'
import { compileWorldPlan, overlayBlocks, type WorldPlan } from './worldPlanner'

const kinds = ['station', 'landing_pad', 'boardwalk', 'greenhouse', 'observatory', 'sculpture', 'grove', 'plaza'] as const
const plan = (kind: WorldPlan['kind'], x = 100): WorldPlan =>
  ({ kind, site: { x, z: 40 }, variant: 3, observation: '', clearance: 15, base_y: 2 })

describe('build compilers', () => {
  it.each(kinds)('%s compiles to blocks from the registry', (kind) => {
    const project = compileWorldPlan(plan(kind))
    expect(project.blocks.length).toBeGreaterThan(0)
    expect([...new Set(project.blocks.filter((block) => !hasBlock(block.material)).map((block) => block.material))]).toEqual([])
  })

  it('keeps the station where it has always been', () => {
    const station = compileWorldPlan(plan('station'))
    expect(station.site).toEqual({ x: 48, z: 0 })
    expect(Math.max(...station.blocks.map((block) => block.y))).toBe(42)
    expect(new Set(station.blocks.map((block) => block.material))).toEqual(new Set(['hull_panel', 'dark_slate', 'solar_panel']))
  })

  it('reveals finished plans fully and the current plan up to stepIndex', () => {
    const plans = [plan('station'), plan('plaza', 200)]
    const station = compileWorldPlan(plans[0]).blocks.length
    expect(overlayBlocks(plans, 1, 5)).toHaveLength(station + 5)
    expect(overlayBlocks(plans, 0, 7)).toHaveLength(7)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/world/worldPlanner.test.ts`
Expected: FAIL (`project.blocks` is undefined and `overlayBlocks` is not exported).

- [ ] **Step 3: Rewrite the build compilers**

Replace `frontend/src/components/world/worldPlanner.ts` with:

```ts
import type { PlacedBlock } from '../../engine/worldStore'

type Point = { x: number; z: number }
type ProjectKind = 'station' | 'landing_pad' | 'boardwalk' | 'greenhouse' | 'observatory' | 'sculpture' | 'grove' | 'plaza'

export interface WorldPlan {
  kind: ProjectKind
  site: Point
  variant: number
  observation: string
  clearance: number
  base_y?: number
}

export interface BuildProject {
  name: string
  site: Point
  standOff: number
  /** In the order Mimo places them. */
  blocks: PlacedBlock[]
}

export const ORBITAL_STATION = { x: 48, z: 0, radius: 20, centerY: 22 } as const

const names: Record<ProjectKind, string> = {
  station: 'an orbital station', landing_pad: 'a station landing pad',
  boardwalk: 'a boardwalk over the pond', greenhouse: 'a glass greenhouse',
  observatory: 'a hilltop observatory', sculpture: 'a tall voxel sculpture',
  grove: 'a sheltered grove', plaza: 'a fountain plaza',
}
const radii: Record<ProjectKind, number> = {
  station: ORBITAL_STATION.radius, landing_pad: 6, boardwalk: 6,
  greenhouse: 5, observatory: 5, sculpture: 5, grove: 7, plaza: 7,
}

function compileStation(): BuildProject {
  const { radius, centerY } = ORBITAL_STATION
  const dish = { x: -8, y: 6, radius: 6 }
  const blocks: PlacedBlock[] = []
  for (let y = -radius; y <= radius; y++) {
    for (let x = -radius; x <= radius; x++) {
      for (let z = -radius; z <= radius; z++) {
        if (Math.abs(Math.hypot(x, y, z) - radius) > 0.55) continue
        const dishDistance = Math.hypot(x - dish.x, y - dish.y)
        const inDish = z > radius / 2 && dishDistance < dish.radius
        const material = inDish ? (dishDistance < dish.radius / 2 ? 'solar_panel' : 'dark_slate')
          : Math.abs(y) <= 1 ? 'dark_slate' : 'hull_panel'
        blocks.push({ x: ORBITAL_STATION.x + x, y: centerY + y, z: ORBITAL_STATION.z + z, material })
      }
    }
  }
  blocks.sort((a, b) => a.y - b.y || a.z - b.z || a.x - b.x)
  return { name: names.station, site: { x: ORBITAL_STATION.x, z: ORBITAL_STATION.z }, standOff: radius + 5, blocks }
}

const planCache = new Map<string, BuildProject>()

export function compileWorldPlan(plan: WorldPlan): BuildProject {
  const key = `${plan.kind}:${plan.site.x},${plan.site.z}:${plan.variant}:${plan.base_y ?? 0}`
  const cached = planCache.get(key)
  if (cached) return cached
  if (plan.kind === 'station') {
    const station = compileStation()
    planCache.set(key, station)
    return station
  }
  const { site, kind, variant } = plan
  const baseY = plan.base_y ?? 0
  const blocks: PlacedBlock[] = []
  const add = (x: number, y: number, z: number, material: string) =>
    blocks.push({ x: site.x + x, y: baseY + y, z: site.z + z, material })

  if (kind === 'landing_pad') {
    for (let x = -5; x <= 5; x++) for (let z = -5; z <= 5; z++) {
      if (Math.hypot(x, z) <= 5.5) add(x, 0, z, Math.hypot(x, z) > 4 ? 'limestone' : 'dark_slate')
      if (Math.abs(x) <= 1 && Math.abs(z) <= 1 && (x === 0 || z === 0)) add(x, 1, z, 'brass')
    }
    for (const x of [-5, 5]) for (const z of [-5, 5]) {
      for (let y = 1; y <= 5; y++) add(x, y, z, 'polished_stone')
      add(x, 6, z, 'lantern')
    }
  } else if (kind === 'boardwalk') {
    for (let x = -6; x <= 6; x++) for (let z = -1; z <= 1; z++) {
      add(x, 1, z, 'planks')
      if (Math.abs(z) === 1 && x % 3 === 0) for (let y = 2; y <= 3; y++) add(x, y, z, 'limestone')
    }
    for (let x = -6; x <= 6; x++) for (const z of [-1, 1]) add(x, 3, z, 'planks')
  } else if (kind === 'greenhouse') {
    for (let x = -4; x <= 4; x++) for (let z = -3; z <= 3; z++) {
      add(x, 0, z, 'limestone')
      if (Math.abs(x) < 4 && Math.abs(z) < 3 && (x + z + variant) % 4 === 0) {
        add(x, 1, z, 'leaves')
        add(x, 2, z, 'flower_pink')
      }
      const edge = Math.abs(x) === 4 || Math.abs(z) === 3
      if (edge && !(x === 0 && z === 3)) for (let y = 1; y <= 4; y++) add(x, y, z, y === 1 || y === 4 ? 'oak_log' : 'glass')
      add(x, 5, z, 'glass')
    }
  } else if (kind === 'observatory') {
    for (let y = 0; y <= 8; y++) for (let x = -4; x <= 4; x++) for (let z = -4; z <= 4; z++) {
      const radius = Math.hypot(x, z)
      if (y === 0 && radius <= 4.5) add(x, y, z, 'limestone')
      else if (y > 0 && y < 6 && radius > 3.25 && radius <= 4.5 && !(z === 4 && x === 0 && y < 3)) add(x, y, z, y % 3 === 0 ? 'limestone' : 'polished_stone')
      else if (y >= 6 && Math.hypot(x, z, (y - 6) * 1.6) < 4.5 && Math.hypot(x, z, (y - 6) * 1.6) > 3) add(x, y, z, 'glass')
    }
    for (let y = 8; y <= 12; y++) add(0, y, 0, 'dark_slate')
    add(0, 13, 0, 'lantern')
  } else if (kind === 'sculpture') {
    for (let x = -5; x <= 5; x++) for (let z = -5; z <= 5; z++) if (Math.hypot(x, z) <= 5) add(x, 0, z, 'limestone')
    for (let y = 1; y <= 17; y++) {
      const angle = y * 0.58 + variant
      const x = Math.round(Math.cos(angle) * 3)
      const z = Math.round(Math.sin(angle) * 3)
      const material = y % 4 === 0 ? 'sandstone' : 'verdigris'
      for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) add(x + dx, y, z + dz, material)
    }
  } else if (kind === 'grove') {
    for (let x = -6; x <= 6; x++) for (let z = -6; z <= 6; z++) if (Math.hypot(x, z) <= 6.5) add(x, 0, z, x % 3 === 0 || z % 3 === 0 ? 'limestone' : 'grass')
    for (const [tx, tz] of [[-4, -3], [4, -3], [-4, 3], [4, 3]] as const) {
      for (let y = 1; y <= 5; y++) add(tx, y, tz, 'oak_log')
      for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (let y = 5; y <= 7; y++) {
        if (Math.abs(dx) + Math.abs(dz) + Math.abs(y - 6) <= 4) add(tx + dx, y, tz + dz, 'leaves')
      }
    }
    for (let x = -2; x <= 2; x++) for (let z = -2; z <= 2; z++) add(x, 1, z, 'planks')
  } else {
    for (let x = -6; x <= 6; x++) for (let z = -6; z <= 6; z++) if (Math.hypot(x, z) <= 6.5) add(x, 0, z, Math.hypot(x, z) > 4.5 ? 'limestone' : 'polished_stone')
    for (let x = -2; x <= 2; x++) for (let z = -2; z <= 2; z++) if (Math.hypot(x, z) <= 2.5) add(x, 1, z, 'water')
    for (let y = 1; y <= 6; y++) add(0, y, 0, 'limestone')
    add(0, 7, 0, 'lantern')
    for (const x of [-5, 5]) for (const z of [-5, 5]) for (let y = 1; y <= 3; y++) add(x, y, z, 'oak_log')
  }

  const project = { name: names[kind], site, standOff: radii[kind] + 3, blocks }
  planCache.set(key, project)
  if (planCache.size > 256) planCache.delete(planCache.keys().next().value!)
  return project
}

/** Blocks the viewer shows for builds: finished plans in full, the current one up to stepIndex. */
export function overlayBlocks(plans: WorldPlan[], currentIndex: number, stepIndex: number): PlacedBlock[] {
  const blocks: PlacedBlock[] = []
  for (let index = 0; index <= currentIndex && index < plans.length; index++) {
    const project = compileWorldPlan(plans[index])
    const count = index < currentIndex ? project.blocks.length : Math.min(stepIndex, project.blocks.length)
    for (let i = 0; i < count; i++) blocks.push(project.blocks[i])
  }
  return blocks
}
```

The geometry and block order match the old compilers exactly; only colors became materials. The mapping is: pale → `limestone`, stone → `polished_stone`, dark → `dark_slate`, wood posts and frames → `oak_log`, wood decks and rails → `planks`, landing-pad center → `brass`, greenhouse bloom → `flower_pink`, sculpture accent → `sandstone`, sculpture body → `verdigris`, grove green floor → `grass`, grove platform → `planks`, station hull → `hull_panel`, station trench and dish rim → `dark_slate`, dish center → `solar_panel`.

- [ ] **Step 4: Trim previewWorld.ts and delete expandingWorld.ts**

Replace `frontend/src/components/world/previewWorld.ts` with only the pet model:

```ts
import type { PetEntity, Voxel } from '../../types/world'

type Color = readonly [number, number, number]

const petVoxels: Voxel[] = []
function petVoxel(x: number, y: number, z: number, color: Color) {
  petVoxels.push({ x, y, z, r: color[0], g: color[1], b: color[2], a: 255 })
}

const fur: Color = [242, 173, 148]
const lightFur: Color = [251, 204, 176]
const ear: Color = [215, 122, 129]

for (let x = -1; x <= 1; x++) {
  for (let z = -1; z <= 0; z++) {
    petVoxel(x, 0, z, fur)
    petVoxel(x, 1, z, fur)
  }
}
for (let x = -1; x <= 1; x++) {
  for (let z = 0; z <= 1; z++) {
    petVoxel(x, 2, z, lightFur)
    petVoxel(x, 3, z, lightFur)
  }
}
for (const x of [-1, 1]) {
  petVoxel(x, 4, 0, fur)
  petVoxel(x, 5, 0, ear)
  petVoxel(x, 0, 1, lightFur)
}
petVoxel(0, 1, -2, lightFur)

export const previewPet: PetEntity = {
  position: { x: 0, y: 1, z: 0 },
  voxels: petVoxels,
}
```

```bash
git rm frontend/src/components/world/expandingWorld.ts
grep -rn "expandingWorld\|previewChunks" frontend/src
```

Expected: the grep prints only `WorldPreview.tsx` lines, which Step 5 replaces.

- [ ] **Step 5: Rewrite WorldPreview.tsx**

Replace `frontend/src/pages/WorldPreview.tsx` with:

```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import type { OrbitControls as OrbitControlsType } from 'three-stdlib'
import * as THREE from 'three'
import PetEntity from '../components/world/PetEntity'
import { previewPet } from '../components/world/previewWorld'
import { compileWorldPlan, ORBITAL_STATION, overlayBlocks, type WorldPlan } from '../components/world/worldPlanner'
import BlockWorld, { type ViewStats } from '../engine/BlockWorld'
import { AIR, BLOCKS } from '../engine/blocks'
import { BlockSync, type BlocksPage } from '../engine/blockSync'
import { DEFAULT_WORLD_SEED, terrainHeight } from '../engine/worldgen'
import { WorldStore } from '../engine/worldStore'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WILDERNESS = { x: 260, z: 120 }
interface Point { x: number; y?: number; z: number }
interface MimoEvent { id: number; at: number; kind: string; text: string }
interface LiveMimoState {
  name: string
  world_seed: string
  position: Point
  energy: number
  mood: number
  plans: WorldPlan[]
  currentIndex: number
  progress: number
  status: string
  last_thought: string
  last_observation: string
  last_action_at: number
  last_error: string | null
  worker_last_seen_at: number | null
  fetched_at: number
  blocks_seq: number
  inventory: Record<string, number>
  recipes: Record<string, { ingredients: Record<string, number>; output: Record<string, number>; station?: string }>
  events: MimoEvent[]
}

/** Phones and low-core devices draw fewer columns. */
function pickViewDistance(): number {
  const small = Math.min(window.innerWidth, window.innerHeight) < 600
  return small || (navigator.hardwareConcurrency ?? 8) <= 4 ? 4 : 6
}

async function fetchBlocksPage(since: number): Promise<BlocksPage> {
  const response = await fetch(`${API_URL}/api/mimo/blocks?since=${since}`)
  if (!response.ok) throw new Error(`Server returned ${response.status}`)
  return await response.json() as BlocksPage
}

function BuildCamera({ focus, focusY, initialFocus, initialFocusY, distance, follow, onOrbit, onChunkChange }: {
  focus: Point
  focusY: number
  initialFocus: Point
  initialFocusY: number
  distance: number
  follow: boolean
  onOrbit: () => void
  onChunkChange: (x: number, z: number) => void
}) {
  const controlsRef = useRef<OrbitControlsType>(null)
  const lastChunk = useRef('0,0')
  const { camera } = useThree()

  useFrame((_, delta) => {
    const controls = controlsRef.current
    if (!controls) return
    if (follow) {
      const desired = new THREE.Vector3(focus.x, focusY, focus.z)
      const movement = desired.sub(controls.target).multiplyScalar(1 - Math.exp(-3 * delta))
      controls.target.add(movement)
      camera.position.add(movement)
      const offset = camera.position.clone().sub(controls.target)
      const currentDistance = offset.length()
      camera.position.addScaledVector(offset.normalize(), (distance - currentDistance) * (1 - Math.exp(-2 * delta)))
      controls.update()
    }
    const cx = Math.floor(controls.target.x / 16)
    const cz = Math.floor(controls.target.z / 16)
    const key = `${cx},${cz}`
    if (key !== lastChunk.current) {
      lastChunk.current = key
      onChunkChange(cx, cz)
    }
  })

  return (
    <OrbitControls ref={controlsRef} target={[initialFocus.x, initialFocusY, initialFocus.z]}
      enableDamping dampingFactor={0.08} minDistance={11} maxDistance={130}
      maxPolarAngle={Math.PI / 2.04} onStart={onOrbit} />
  )
}

function LiveWorld({ state, onHello, onAction, connectionError }: {
  state: LiveMimoState
  onHello: () => Promise<void>
  onAction: (action: string, item: string) => Promise<string>
  connectionError: string
}) {
  const worldSeed = state.world_seed || DEFAULT_WORLD_SEED
  const store = useMemo(() => new WorldStore(worldSeed), [worldSeed])
  const sync = useMemo(() => new BlockSync(fetchBlocksPage, (changes, reset) => {
    store.applyServerChanges(changes, reset)
  }), [store])
  const [viewDistance] = useState(pickViewDistance)
  const [debug] = useState(() => new URLSearchParams(window.location.search).has('debug'))
  const [stats, setStats] = useState<ViewStats | null>(null)
  const [syncError, setSyncError] = useState('')
  const [engineError, setEngineError] = useState('')
  const [engineKey, setEngineKey] = useState(0)
  const [initialPosition] = useState<Point>(() => ({ ...state.position }))
  const [cameraChunk, setCameraChunk] = useState(() => ({ x: Math.floor(state.position.x / 16), z: Math.floor(state.position.z / 16) }))
  const [following, setFollowing] = useState(true)
  const [viewingStation, setViewingStation] = useState(false)
  const [viewingWilderness, setViewingWilderness] = useState(false)
  const [helloCount, setHelloCount] = useState(0)
  const [showSystems, setShowSystems] = useState(false)
  const [interactionError, setInteractionError] = useState('')
  const [systemMessage, setSystemMessage] = useState('')
  const plan = state.plans[state.currentIndex]
  const project = useMemo(() => compileWorldPlan(plan), [plan])
  const targetStepIndex = Math.floor(project.blocks.length * state.progress / 100)
  const [revealed, setRevealed] = useState(() => ({ projectIndex: state.currentIndex, count: targetStepIndex }))
  const revealedRef = useRef(revealed)
  const stepIndex = revealed.projectIndex === state.currentIndex ? Math.min(revealed.count, targetStepIndex) : targetStepIndex
  const visibleProgress = project.blocks.length ? Math.round(stepIndex / project.blocks.length * 100) : 100
  useEffect(() => { revealedRef.current = revealed }, [revealed])
  useEffect(() => {
    const current = revealedRef.current
    if (current.projectIndex !== state.currentIndex || current.count > targetStepIndex) {
      setRevealed({ projectIndex: state.currentIndex, count: targetStepIndex })
      return
    }
    if (current.count >= targetStepIndex) return
    const startCount = current.count
    const newBlocks = targetStepIndex - startCount
    const startedAt = performance.now()
    let frame = 0
    const revealFrame = (time: number) => {
      const fraction = Math.min(1, (time - startedAt) / 4800)
      const count = startCount + Math.max(1, Math.ceil(newBlocks * fraction))
      setRevealed((previous) => previous.projectIndex === state.currentIndex && count > previous.count
        ? { ...previous, count: Math.min(count, targetStepIndex) } : previous)
      if (fraction < 1) frame = window.requestAnimationFrame(revealFrame)
    }
    frame = window.requestAnimationFrame(revealFrame)
    return () => window.cancelAnimationFrame(frame)
  }, [state.currentIndex, targetStepIndex])
  // Poll-driven: fetched_at changes every second, so a failed delta is retried on the next poll.
  useEffect(() => {
    sync.syncTo(state.blocks_seq).then(
      () => setSyncError(''),
      () => setSyncError('Some block changes could not be loaded. Retrying.'),
    )
  }, [sync, state.blocks_seq, state.fetched_at])
  useEffect(() => {
    store.setOverlay(overlayBlocks(state.plans, state.currentIndex, stepIndex))
  }, [store, state.plans, state.currentIndex, stepIndex])
  const pet = useMemo(() => ({
    ...previewPet, position: { ...previewPet.position, x: initialPosition.x, y: initialPosition.y ?? 1, z: initialPosition.z },
  }), [initialPosition])
  const workerOnline = !connectionError && state.worker_last_seen_at !== null && state.fetched_at - state.worker_last_seen_at < 25
  const activelyLiving = workerOnline && state.status !== 'waiting_for_model'
  const nearbyStations = store.materialsNear(state.position.x, state.position.z, 6)
  const cameraFocus = viewingStation ? ORBITAL_STATION : viewingWilderness ? WILDERNESS : state.progress < 100
    ? { x: (state.position.x + plan.site.x) / 2, z: (state.position.z + plan.site.z) / 2 }
    : state.position
  const cameraY = viewingStation ? ORBITAL_STATION.centerY
    : viewingWilderness ? terrainHeight(WILDERNESS.x, WILDERNESS.z, worldSeed) + 2
      : state.position.y ?? 1
  const blockTypes = BLOCKS.filter((block) => block.id !== AIR)

  const sayHello = async () => {
    setInteractionError('')
    try {
      await onHello()
      setHelloCount((count) => count + 1)
    } catch {
      setInteractionError('Mimo could not hear you. The server may be offline.')
    }
  }

  const helpMimo = async (action: string, item: string) => {
    try {
      setSystemMessage(await onAction(action, item))
    } catch (error) {
      setSystemMessage(error instanceof Error ? error.message : 'That action could not be completed.')
    }
  }

  return (
    <main className="relative h-screen min-h-[540px] overflow-hidden bg-[#dce9eb] text-[#243e3d]">
      <div className="absolute inset-0">
        <Canvas camera={{ position: [initialPosition.x + 18, 14, initialPosition.z + 18], fov: 48, near: 0.1, far: 280 }}
          gl={{ antialias: true }} dpr={[1, 2]}>
          <color attach="background" args={['#dce9eb']} />
          <fog attach="fog" args={['#dce9eb', viewDistance * 16 * 0.6, viewDistance * 16 + 8]} />
          <ambientLight intensity={0.8} />
          <directionalLight position={[12, 24, 16]} intensity={1.7} />
          <directionalLight position={[-10, 8, -12]} intensity={0.35} color="#d5eaff" />
          <BlockWorld key={engineKey} store={store} centerX={cameraChunk.x * 16 + 8} centerZ={cameraChunk.z * 16 + 8}
            viewDistance={viewDistance} onStats={debug ? setStats : undefined} onError={setEngineError} />
          <PetEntity pet={pet} scale={0.31}
            destination={{ x: state.position.x, y: state.position.y, z: state.position.z, token: Math.round(state.last_action_at) }}
            onPetClick={() => { void sayHello() }} hopSignal={helloCount}>
            {[-0.25, 1.25].map((x) => (
              <mesh key={x} position={[x, 3.35, 2.08]}>
                <boxGeometry args={[0.34, 0.38, 0.16]} />
                <meshStandardMaterial color="#39454a" />
              </mesh>
            ))}
            <mesh position={[0.5, 2.58, 2.1]}>
              <boxGeometry args={[0.32, 0.25, 0.18]} />
              <meshStandardMaterial color="#cd8a84" />
            </mesh>
          </PetEntity>
          <BuildCamera focus={cameraFocus} focusY={cameraY} initialFocus={initialPosition} initialFocusY={initialPosition.y ?? 1}
            distance={viewingStation ? 84 : viewingWilderness ? 52 : state.progress < 100 ? 30 : 26} follow={following}
            onOrbit={() => setFollowing(false)}
            onChunkChange={(x, z) => setCameraChunk((current) => current.x === x && current.z === z ? current : { x, z })} />
        </Canvas>
      </div>

      {debug && stats && (
        <div className="pointer-events-none absolute left-3 top-3 z-30 rounded-lg bg-black/70 px-3 py-2 font-mono text-[11px] leading-5 text-white">
          {stats.fps} fps · {stats.drawCalls} draws<br />
          {stats.columns} columns · {stats.pending} pending · mesh {stats.lastMeshMs.toFixed(1)} ms
        </div>
      )}

      {engineError && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-[#dce9eb]/90 px-6 text-center text-[#315e58]">
          <div>
            <p className="text-2xl font-semibold">Mimo's world stopped drawing</p>
            <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{engineError}</p>
            <button type="button" onClick={() => { setEngineError(''); setEngineKey((key) => key + 1) }}
              className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>
          </div>
        </div>
      )}

      <div className="pointer-events-none absolute left-5 top-20 z-10 max-w-xs sm:left-10 sm:top-24">
        <p className="mb-2 text-sm font-medium text-[#637d79]">Mimo's world</p>
        <h1 className="text-4xl font-semibold leading-[1.04] tracking-[-0.065em] sm:text-6xl">Made by Mimo.</h1>
        <p className="mt-4 max-w-[18rem] text-sm leading-6 text-[#4f6967] sm:text-base">
          Mimo's world and activity are stored on the server. Its worker runs while this page is closed.
        </p>
      </div>

      <div className="absolute right-5 top-5 z-10 max-w-[15rem] rounded-2xl border border-white/75 bg-[#f5faf7]/90 px-4 py-3 text-xs shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md sm:right-10 sm:top-9">
        <p className="font-semibold"><span className={activelyLiving ? 'text-[#3c9a73]' : 'text-[#c76e5c]'}>●</span> {activelyLiving ? 'Mimo is live' : workerOnline ? 'Mimo is paused' : 'Worker offline'}</p>
        <p className="mt-1 text-[#54726e]">{state.status.replaceAll('_', ' ')} · energy {Math.round(state.energy)}%</p>
        <p className="mt-1 text-[#54726e]">Last action {new Date(state.last_action_at * 1000).toLocaleString()}</p>
      </div>

      <div className="absolute bottom-6 left-5 right-5 z-10 flex flex-col gap-4 sm:bottom-9 sm:left-10 sm:right-10 sm:flex-row sm:items-end sm:justify-between">
        <div className="w-[min(100%,21rem)] rounded-2xl border border-white/75 bg-[#f5faf7]/90 px-5 py-4 shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f5c0a9] text-xl" aria-hidden="true">✿</div>
            <div>
              <p className="text-base font-semibold leading-tight">Mimo</p>
              <p className="text-xs text-[#65817b]">{state.status.replaceAll('_', ' ')}</p>
            </div>
          </div>
          <p className="mt-4 text-sm font-medium">{stepIndex < project.blocks.length ? 'Building' : 'Finished'} {project.name}</p>
          {stepIndex < project.blocks.length && <p className="mt-1 text-xs text-[#54726e]">{stepIndex} / {project.blocks.length} blocks placed</p>}
          <p className="mt-2 text-xs leading-5 text-[#54726e]">{plan.observation}</p>
          <p className="mt-2 text-xs italic leading-5 text-[#54726e]">“{state.last_thought}”</p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#d9e8df]" role="progressbar"
            aria-valuenow={visibleProgress} aria-valuemin={0} aria-valuemax={100} aria-label={`${project.name} progress`}>
            <div className="h-full rounded-full bg-[#4d8c77] transition-[width] duration-150" style={{ width: `${visibleProgress}%` }} />
          </div>
          <div className="mt-4 flex gap-2">
            <button type="button" onClick={() => { void sayHello() }}
              className="flex-1 rounded-xl bg-[#315e58] px-3 py-2.5 text-sm font-medium text-white hover:bg-[#244b47]">Say hello</button>
            <button type="button" onClick={() => { setViewingStation(false); setViewingWilderness(false); setFollowing(true) }}
              className="flex-1 rounded-xl border border-[#bfd5cd] px-3 py-2.5 text-sm font-medium text-[#315e58] hover:bg-white">Follow Mimo</button>
          </div>
          <button type="button" onClick={() => { setViewingStation(true); setViewingWilderness(false); setFollowing(true) }}
            className="mt-3 text-sm font-medium text-[#315e58] underline decoration-[#8cafa2] underline-offset-4">
            Visit the orbital station
          </button>
          <button type="button" onClick={() => { setViewingStation(false); setViewingWilderness(true); setFollowing(true) }}
            className="ml-4 mt-3 text-sm font-medium text-[#315e58] underline decoration-[#8cafa2] underline-offset-4">
            Explore the wilderness
          </button>
          <button type="button" onClick={() => setShowSystems(true)}
            className="ml-4 mt-3 text-sm font-medium text-[#315e58] underline decoration-[#8cafa2] underline-offset-4">
            Blocks & crafting
          </button>
          {(state.last_error || interactionError || syncError) && (
            <p className="mt-3 text-xs text-[#a65b50]">{interactionError || syncError || state.last_error}</p>
          )}
        </div>
        <div className="hidden w-64 rounded-2xl border border-white/75 bg-[#f5faf7]/90 px-4 py-4 text-xs shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md md:block">
          <p className="mb-2 font-semibold">Mimo's inventory</p>
          <div className="mb-4 flex flex-wrap gap-1.5 text-[#315e58]">
            {Object.entries(state.inventory).filter(([, amount]) => amount > 0).slice(0, 8).map(([item, amount]) =>
              <span key={item} className="rounded-md bg-[#e1eee7] px-2 py-1">{item.replaceAll('_', ' ')} ×{amount}</span>)}
          </div>
          <p className="mb-2 font-semibold">What Mimo has done</p>
          <ul className="space-y-2 text-[#54726e]">
            {state.events.slice(0, 4).map((event) => <li key={event.id}>{event.text}</li>)}
          </ul>
          <p className="mt-3 text-[#65817b]">Drag to look around · Scroll to zoom</p>
        </div>
      </div>
      {showSystems && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={() => setShowSystems(false)}>
          <section role="dialog" aria-modal="true" aria-label="Mimo's blocks and crafting" onClick={(event) => event.stopPropagation()}
            className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8">
            <div className="flex items-start justify-between gap-4">
              <div><p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">World systems</p>
                <h2 className="mt-1 text-3xl font-semibold tracking-tight">Blocks & crafting</h2></div>
              <button type="button" onClick={() => setShowSystems(false)} aria-label="Close blocks and crafting" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
            </div>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[#54726e]">Mimo can mine, place, craft, and smelt these materials. You can help with crafting here. Inventory and machines persist when you leave.</p>
            <p className="mt-2 text-xs text-[#54726e]">World seed: <code>{worldSeed}</code></p>
            <h3 className="mt-6 text-sm font-semibold">Mimo's inventory</h3>
            <div className="mt-2 flex flex-wrap gap-2 text-sm">
              {Object.entries(state.inventory).filter(([, amount]) => amount > 0).map(([item, amount]) =>
                <span key={item} className="rounded-lg bg-[#e1eee7] px-3 py-1.5">{item.replaceAll('_', ' ')} ×{amount}</span>)}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" disabled={!state.inventory.crafting_table} onClick={() => { void helpMimo('place_machine', 'crafting_table') }}
                className="rounded-lg bg-[#315e58] px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-35">Place crafting table</button>
              <button type="button" disabled={!state.inventory.furnace} onClick={() => { void helpMimo('place_machine', 'furnace') }}
                className="rounded-lg bg-[#315e58] px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-35">Place furnace</button>
              <button type="button" disabled={!state.inventory.iron_ore || !nearbyStations.has('furnace') || !(state.inventory.coal || state.inventory.planks)} onClick={() => { void helpMimo('smelt', 'iron_ore') }}
                className="rounded-lg border border-[#bfd5cd] px-3 py-2 text-xs font-medium text-[#315e58] disabled:cursor-not-allowed disabled:opacity-35">Smelt iron ore</button>
            </div>
            <p className="mt-2 text-xs text-[#65817b]">Smelting needs a placed furnace and coal or planks for fuel.</p>
            {systemMessage && <p className="mt-3 rounded-lg bg-[#e1eee7] px-3 py-2 text-xs text-[#315e58]" role="status">{systemMessage}</p>}
            <h3 className="mt-6 text-sm font-semibold">{blockTypes.length} block types</h3>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {blockTypes.map((block) => (
                <div key={block.name} className="flex items-center gap-2 rounded-lg border border-[#d6e5dc] px-2 py-1.5 text-xs">
                  <span className="h-5 w-5 shrink-0 rounded-sm border border-black/10" style={{ backgroundColor: `rgb(${block.color.join(',')})` }} />
                  {block.name.replaceAll('_', ' ')}
                </div>
              ))}
            </div>
            <h3 className="mt-6 text-sm font-semibold">Recipes</h3>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {Object.entries(state.recipes).map(([name, recipe]) => (
                <div key={name} className="rounded-xl bg-[#e9f2eb] px-3 py-2 text-xs leading-5">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold">{name.replaceAll('_', ' ')}</p>
                    <button type="button" disabled={Boolean(recipe.station && !nearbyStations.has(recipe.station)) ||
                      Object.entries(recipe.ingredients).some(([item, amount]) => (state.inventory[item] || 0) < amount)}
                      onClick={() => { void helpMimo('craft', name) }}
                      className="rounded-md bg-[#315e58] px-2 py-1 font-medium text-white hover:bg-[#244b47] disabled:cursor-not-allowed disabled:opacity-35">Craft</button>
                  </div>
                  <p className="text-[#54726e]">{Object.entries(recipe.ingredients).map(([item, amount]) => `${amount} ${item.replaceAll('_', ' ')}`).join(' + ')}
                    {recipe.station ? ` · needs placed ${recipe.station.replaceAll('_', ' ')}` : ''}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </main>
  )
}

export default function WorldPreview() {
  const [state, setState] = useState<LiveMimoState | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/mimo`)
      if (!response.ok) throw new Error(`Server returned ${response.status}`)
      const next = await response.json() as LiveMimoState
      next.fetched_at = Date.now() / 1000
      setState((previous) => {
        if (previous && JSON.stringify(previous.plans) === JSON.stringify(next.plans)) next.plans = previous.plans
        return next
      })
      setError('')
    } catch {
      setError('Mimo’s server is unavailable. Its world will appear when the server is running.')
    }
  }, [])

  useEffect(() => {
    const initial = window.setTimeout(() => { void refresh() }, 0)
    const timer = window.setInterval(() => { void refresh() }, 1000)
    return () => { window.clearTimeout(initial); window.clearInterval(timer) }
  }, [refresh])

  const hello = async () => {
    const response = await fetch(`${API_URL}/api/mimo/hello`, { method: 'POST' })
    if (!response.ok) throw new Error('Greeting failed')
    await refresh()
  }

  const act = async (action: string, item: string) => {
    const response = await fetch(`${API_URL}/api/mimo/action`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, item }),
    })
    const result = await response.json() as { message?: string; detail?: string }
    if (!response.ok) throw new Error(result.detail || 'That action could not be completed.')
    await refresh()
    return result.message || 'Done.'
  }

  if (!state) return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <div><p className="text-2xl font-semibold">Connecting to Mimo’s world…</p>
        {error && <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{error}</p>}
        {error && <button type="button" onClick={() => { void refresh() }} className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>}
      </div>
    </main>
  )
  return <LiveWorld state={state} onHello={hello} onAction={act} connectionError={error} />
}
```

- [ ] **Step 6: Run tests, lint and the build**

Run: `cd frontend && npm test && npm run build && npx eslint src/engine src/components/world/worldPlanner.ts src/components/world/worldPlanner.test.ts src/components/world/previewWorld.ts src/pages/WorldPreview.tsx`
Expected: tests pass; build succeeds; eslint reports no errors in these files. Fix any lint errors in these files only.

- [ ] **Step 7: Commit**

```bash
git add -A frontend/src/components/world frontend/src/pages/WorldPreview.tsx
git commit -m "feat: render /preview with the voxel engine" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Verify in the running app and update the README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Start a scratch API**

Never point checks at the real `pets_mimo_data` volume. Run the API with a throwaway database inside the container:

```bash
docker compose build api
docker compose run --rm -d --name mimo-check -p 127.0.0.1:8001:8000 -e MIMO_DB_PATH=/tmp/check.sqlite3 api
curl -s http://127.0.0.1:8001/api/mimo | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['blocks_seq'], 'block_edits' in d)"
```

Expected: `0 False`.

Dig a shaft so the underground shows:

```bash
docker exec mimo-check python -c "from backend.services.live_mimo import MimoStore; s = MimoStore(); [s.put_block(60, y, 6, 'air') for y in range(-4, 2)]"
curl -s "http://127.0.0.1:8001/api/mimo/blocks?since=0" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['seq'], len(d['changes']), d['more'])"
```

Expected: `6 6 False`.

- [ ] **Step 2: Start the viewer against the scratch API**

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8001 npm run dev
```

Open `http://127.0.0.1:5173/preview?debug` in the Browser pane.

- [ ] **Step 3: Check the look and the world**

Take screenshots and confirm each item:

- Blocks show 8×8 pastel pixel textures, face shading and darker inside corners, like mockup C.
- Grass blocks show a green lip over dirt on their sides.
- The home clearing shows the pond, sand shore, dirt path walkway, cottage (plaster, glass windows, roof tiles) and the big tree.
- Tall grass and flowers show as crossed sprites.
- The shaft at (60, 6) shows solid stone, dirt and any ore on its walls, not a hollow shell.
- "Visit the orbital station" shows the station at the same place as before, in hull panels with a darker trench and dish.
- Water is translucent with a lowered surface and slowly moving texture.
- The debug overlay shows fps, draw calls and mesh time.

- [ ] **Step 4: Check the phone budget**

Resize the Browser pane to 390 × 844 (mobile preset), reload `?debug`, wait for `pending` to reach 0 and note fps, draws and mesh ms. Expected: view distance 4 (81 columns), draws under about 250, fps near 60 on this machine. Reset the viewport to desktop afterwards.

- [ ] **Step 5: Check the build reveal**

Stop the scratch container and use the real stack only for viewing (no writes):

```bash
docker stop mimo-check
docker compose up -d --build api mimo-worker
```

Open `/preview` without `VITE_API_URL`. If Mimo is building, confirm blocks appear one by one. Confirm every earlier build is still in its place.

- [ ] **Step 6: Update the README**

In `README.md`:

1. Replace the paragraph that starts "The preview refreshes the saved world every second." with:

```markdown
The preview polls Mimo's state every second. Block changes carry sequence numbers, so the page fetches only new changes from `/api/mimo/blocks`. A Web Worker generates chunk columns from the world seed and meshes them with 8×8 pixel textures and corner shading; the page stays smooth on phones. Add `?debug` to the URL to see frame rate, draw calls and mesh time.
```

2. In "Current world rules", add these bullets after the bullet about generated terrain:

```markdown
- Every block is listed once in `shared/blocks.json`. The server and the viewer both read it.
- Trees, flowers, tall grass and the home cottage are part of worldgen on both sides, so Mimo can mine real trees. Python (`backend/services/worldgen.py`) and TypeScript (`frontend/src/engine/worldgen.ts`) must agree cell for cell; `shared/worldgen-fixture.json` checks that.
```

3. Replace the "Checks" code block with:

```bash
python3 -m unittest discover -s backend/tests
cd frontend && npm test && npm run build
```

and add this sentence after it: "After changing worldgen in either language, run `python3 -m backend.scripts.worldgen_fixture` and commit the updated fixture."

- [ ] **Step 7: Run every check**

Run: `python3 -m unittest discover -s backend/tests && cd frontend && npm test && npm run build`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add README.md
git commit -m "docs: describe the voxel engine, block registry and checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
