# Voxel Engine and Soft Pixel Look — Design Spec

Sub-project 1 of 4 in making Mimo's world feel like Minecraft.

| # | Sub-project | Status |
|---|-------------|--------|
| 1 | Voxel engine and soft pixel look | This spec |
| 2 | Physical Mimo: pathing over real blocks, timed walk/mine/place actions, builds placed as real blocks | Later |
| 3 | Block updates: falling sand and gravel as entities, flowing water | Later |
| 4 | App shell: Capacitor iOS/Android and PWA, hosted API, touch and safe-area tuning | Later |

## Goal

Make `/preview` look like "Soft pixel" mockup C from brainstorming: textured 8×8 pixel blocks in the current pastel palette, baked face shading and corner ambient occlusion, hidden faces removed. Make the world solid. Every cell has a known block on the client and on the server, underground included. That solid grid is what sub-project 2 needs for collision.

No change to how Mimo behaves in this sub-project, with one exception: trees become real on the server (see "Behavior changes").

## Decisions already made

- **Mimo only.** There is no player avatar. The viewer keeps the orbit/follow camera.
- **Server owns truth, client animates** (approach A). The Python worker stays the only simulation. The browser renders and, in sub-project 2, plays back server actions with real collision.
- **Website plus app.** The site stays primary. The same code gets wrapped for iOS and Android in sub-project 4. Phone GPUs set the performance budget now.
- **Soft pixel style.** 8×8 textures, low contrast, pastel palette taken from the current catalog colors.

## Problems with the current renderer

- `VoxelChunk.tsx` draws every block as a flat-colored cube in an `InstancedMesh`. There are no textures, no hidden-face removal and no ambient occlusion. Bright even lighting makes neighboring blocks blur into one surface.
- Chunks store voxel lists, not grids, so nothing can answer "what is at (x, y, z)?" quickly.
- `makeTerrainChunk` renders only the top two or three layers. Deeper blocks are added only around dig sites.
- Trees, flowers and the home clearing (pond shore, path, cottage, big tree) exist only in browser code (`expandingWorld.ts`, `previewWorld.ts`). The server does not know about them.
- Builds and the preview world carry raw RGB per voxel instead of materials, so no texture can be chosen for them.
- `/api/mimo` sends every block edit every second, capped at 20,000 rows by `LIMIT 20000`. Past that, edits silently disappear from the view.

## Architecture

```
shared/blocks.json          one block registry, read by Python and TypeScript
shared/worldgen-fixture.json sampled cells used to keep both worldgen ports identical

Server (Python)
  worldgen.py      terrain, caves, ores, trees, plants, home clearing
  live_mimo.py     block edits carry a seq number; one write helper bumps it
  GET /api/mimo/blocks?since=N   changed blocks only

Browser main thread                           Web Worker (world.worker.ts)
  WorldStore      chunk columns, Uint8 ids  ─►  generate column from seed
  BlockWorld      three.js meshes per column ◄─ apply edits, mesh column
  WorldPreview    polls /api/mimo, fetches deltas
```

### Units

Each unit has one job and can be tested alone.

| Unit | File | Job | Depends on |
|------|------|-----|------------|
| Block registry | `shared/blocks.json`, `frontend/src/engine/blocks.ts`, `backend/services/blocks.py` | Map name ↔ id, expose properties | nothing |
| Worldgen (TS) | `frontend/src/engine/worldgen.ts` (moved from `components/world/worldgen.ts`) | `blockAt(x, y, z, seed)` for natural blocks | registry |
| Worldgen (Python) | `backend/services/worldgen.py` | Same function, same answers | registry |
| WorldStore | `frontend/src/engine/worldStore.ts` | Hold chunk columns and edits, answer `getBlock`, emit dirty columns | registry |
| Atlas | `frontend/src/engine/atlas.ts` | Paint 8×8 tiles from texture recipes into one canvas texture | registry |
| Mesher | `frontend/src/engine/mesher.ts` | Turn one column plus its neighbors' border cells into vertex buffers for three layers | registry, atlas tile map |
| Worker | `frontend/src/engine/world.worker.ts` | Run generation and meshing off the main thread | worldgen, mesher |
| BlockWorld | `frontend/src/engine/BlockWorld.tsx` | Own the worker, upload buffers into three.js meshes, load and unload columns around the camera | WorldStore, atlas |
| Build compilers | `frontend/src/components/world/worldPlanner.ts`, `expandingWorld.ts` | Emit `{x, y, z, material}` instead of colors | registry |

The mesher and worldgen are pure functions so they run the same in the worker and in tests.

## Block registry

`shared/blocks.json` has two keys. `tiles` maps a tile name to a texture recipe: a `pattern` name, a base `color` and an optional `accent` color. `blocks` is an ordered array. The array index is the numeric block id used on the client. Id 0 is `air`. The list is append-only: never reorder or remove an entry, only mark it unused. The server keeps storing material names, so ids never reach the database.

Each entry:

```json
{
  "name": "grass",
  "color": [127, 173, 137],
  "textures": { "top": "grass_top", "side": "grass_side", "bottom": "dirt" },
  "layer": "opaque",
  "solid": true,
  "drop": "dirt"
}
```

- `layer` is one of `opaque`, `cutout`, `translucent`, `none` (air).
- `textures` names tiles from `tiles`. A plain string means the same tile on every face.
- Optional fields carry over from today's `BLOCKS`: `requires`, `gravity`, `fluid`, `glow`, `opacity`.
- `solid: false` for air, water, lava, plants. Sub-project 2 uses it for collision.

`backend/services/crafting.py` builds `BLOCKS` from this file so the crafting code does not change. `RECIPES`, `SMELTING` and `TOOL_RANK` stay in Python.

The backend Docker build context is already the repo root, so `shared/` is available there. Vite imports it with a relative path. Add `server.fs.allow: ['..']` to `vite.config.ts` so the dev server can serve it.

### New materials

Builds and the home clearing use colors that have no material today. Each gets a named block. Colors come straight from the current compilers so the world keeps its palette.

| New block | From | Color | Layer |
|-----------|------|-------|-------|
| `limestone` | build `pale` | 227, 211, 181 | opaque |
| `polished_stone` | build `stone` | 169, 183, 178 | opaque |
| `dark_slate` | build `dark`, station trench and dish rim | 82, 104, 111 | opaque |
| `plaster` | cottage walls | 229, 206, 171 | opaque |
| `roof_tile` | cottage roof | 193, 112, 100 | opaque |
| `dirt_path` | walkway, cottage floor | 215, 196, 159 | opaque |
| `hull_panel` | station hull | 189, 200, 198 | opaque |
| `solar_panel` | station dish center | 91, 155, 171 | opaque |
| `brass` | landing pad center | 226, 192, 126 | opaque |
| `sandstone` | sculpture accent | 245, 197, 151 | opaque |
| `verdigris` | sculpture body | 152, 192, 187 | opaque |
| `tall_grass` | terrain decorations | 89, 147, 112 | cutout |
| `flower_orange`, `flower_pink`, `flower_yellow` | flower heads | 246,192,124 / 243,164,168 / 250,218,139 | cutout |

Mapping rules for the rest: build `wood` becomes `oak_log` for posts and `planks` for decks. Existing `glass`, `leaves`, `lantern` and `water` keep their names. A compiler color with no match is a bug caught by a test (see Testing). The two roof tones and the two hull tones merge into one block each; the texture noise provides the variation. The per-block tint described under Rendering adds more.

Stepping stones in the home clearing become `dirt_path` blocks at ground level instead of thin floating slabs.

## World shape

- Height range is y = -8 to 119, 128 cells. Today's tallest structure, the station, reaches y = 42. `put_block` on the server changes its limit from 128 to 119 to match.
- A chunk column is 16 × 128 × 16, stored as a `Uint8Array` of 32,768 ids.
- Bedrock stays at y ≤ -5.

## Worldgen owns natural blocks

`blockAt(x, y, z, seed)` in both languages returns the natural block at any cell: terrain, caves, ores, sea water, trees, plants and the home clearing. Today's Python `base_material` becomes this function (the old name stays as an alias so callers keep working).

Ported from browser-only code into both languages:

- **Trees** from `makeTerrainChunk`: same chance rules per biome and region, same exclusions (desert, alpine, under sea level, within 17 of origin, near the 13-block spiral build grid, trunk kept 3 cells from chunk edges so canopies stay in one chunk). Trunk `oak_log` four tall, `leaves` canopy in the same shape as today.
- **Plants**: today's rare flower decoration becomes a `flower_*` block at surface + 1. Add sparse `tall_grass` on meadow and forest grass.
- **Home clearing** from `previewWorld.ts`: shore sand, the walkway `dirt_path`, the island's dirt and stone underlayers, the cottage (plaster walls, glass windows, roof_tile roof, dirt_path floor), the big tree at (-6, -4) and the eight flowers. The pond keeps its current shape at y = 0.

Porting needs care with JavaScript integer behavior. The legacy `hash(x, z)` uses `(x * 73856093) ^ (z * 19349663)`, which JavaScript truncates to signed 32-bit before the XOR. The Python port must copy that truncation. The parity fixture catches any mistake.

Tree lookup on the server checks the 5 × 5 columns around a cell for a trunk origin, so `blockAt` stays a pure function with no stored state.

### Parity guard

A small Python script, `backend/scripts/write_worldgen_fixture.py`, samples a few thousand cells and writes `shared/worldgen-fixture.json` with the expected block name for each. The sample covers the home clearing, the legacy region, the 48-block blend ring, each biome, caves, ore depths, tree canopies and sea water. The Python test regenerates the samples and compares them with the file. A Vitest test compares the TypeScript answers with the same file. If either port drifts, a test fails.

## Server sync

### Sequence numbers

- `mimo_blocks` gains a `seq INTEGER NOT NULL` column and an index on `seq`. A `mimo_meta` row holds the last issued seq.
- Every block write goes through one `MimoStore._write_block(db, x, y, z, material)` helper that bumps the counter and stores the new seq. That covers `put_block`, the block edit inside `finish`, `step_loose_blocks` (both the vacated cell and the landing cell), and `owner_action` placing a machine.
- Migration runs in `initialize()`. If the column is missing, add it, backfill `seq = rowid`, and set the counter to the max. This is safe to run on every start.

### Endpoints

- `GET /api/mimo/blocks?since=N&limit=5000` returns `{ "seq": latest, "changes": [{x, y, z, material}], "more": bool }`, ordered by seq. A removed block comes back as `material: "air"`. Clients page through with `since` set to the last seq received until `more` is false.
- `GET /api/mimo` stops sending `block_edits` and `catalog` and adds `blocks_seq`. `recipes` stays because the crafting panel uses it.

### Client flow

1. On load, fetch `/api/mimo` and page `/api/mimo/blocks?since=0` until done.
2. Keep the 1 s `/api/mimo` poll. When `blocks_seq` is greater than the local seq, fetch the delta.
3. If `blocks_seq` is lower than the local seq (the database was reset), drop local edits and resync from 0.

## Rendering

### Atlas

- One canvas texture made at startup. Each recipe paints an 8×8 tile using the soft pixel generator from mockup C: base color from the registry, ±4.5% noise, plus a pattern per recipe (`grass_top`, `grass_side` with lip, `dirt`, `stone` specks, `sand`, `log_side` stripes, `log_top` rings, `planks` seams, `cobble` cells, `ore` specks over stone, `leaves`, `glass` frame, `water`, `flower` cross sprite, `tall_grass` sprite, `plain` noise for build materials).
- The recipe pattern is data. A recipe needs only a base color and a pattern name, so a new build material does not need new code.
- `NearestFilter`, no mipmaps. UVs are inset by a quarter texel to stop neighboring tiles bleeding in.
- Unknown material names get a magenta and black checker tile and one console warning.

### Mesher

For one column, with a one-cell border read from the four neighboring columns:

- Emit a face only when the neighbor cell does not hide it. Opaque hides everything. Translucent blocks hide only faces of the same block, so glass-to-glass and water-to-water faces disappear but sand under water still shows.
- Per-vertex ambient occlusion with the standard three-neighbor rule (side, side, corner → level 0 to 3). Flip the quad diagonal when AO is uneven so gradients don't crease.
- Bake face shade into vertex color: top 1.0, the two side axes 0.82 and 0.66, bottom 0.5. Multiply by AO (1.0, 0.8, 0.62, 0.45 for levels 3 to 0) and by a per-block tint of ±3% from a position hash so large flat areas don't look printed.
- Water's top face sits 1/8 lower when the cell above is air.
- Cutout blocks (flowers, tall grass) emit two crossed quads with no culling and no AO.
- Output three sets of typed arrays (opaque, cutout, translucent): positions, UVs, colors and indices. They are transferred to the main thread without copying.

### Materials and scene

- Terrain uses `MeshBasicMaterial` with the atlas, vertex colors and fog. No real-time lights touch terrain. That matches the mockup exactly and costs little on phones.
- Cutout uses `alphaTest: 0.5`. Translucent uses `transparent: true`, `depthWrite: false`, drawn after opaque. Water scrolls its texture slowly instead of moving the whole mesh.
- Glow blocks (lantern, furnace, lava) get bright tiles and skip AO darkening. Light spreading is not part of this sub-project.
- Mimo keeps its current lit material and lights.
- One mesh per column per layer, so about 3 draw calls per column.

### Loading around the camera

- `BlockWorld` loads columns in a square around the camera's chunk, nearest first. The view distance is 6 chunks on desktop and 4 when the viewport is phone-sized or `navigator.hardwareConcurrency` ≤ 4. Columns 2 beyond the view distance unload.
- A block change marks its column dirty, plus the neighbor column when the block is on a border. Dirty columns remesh in the worker. The old mesh stays on screen until the new one arrives, so nothing blinks.
- When the WebGL context is lost and comes back, as iOS does after the app goes to the background, `BlockWorld` re-uploads the stored buffers.

### Builds in this sub-project

Builds stay compiled in the browser for now. Sub-project 2 moves them to the server. `compileWorldPlan` and `makeProject` emit `{x, y, z, material}`. The block-by-block reveal stays. Each revealed block is applied to `WorldStore` as a client-only overlay edit, below server edits in priority, and remeshes its column.

## Behavior changes

- Trees, plants and the home cottage become real server blocks. `material_at` and mining now see them, so Mimo can mine real trees for `oak_log`.
- `observe_world` scans `nearby_columns` up to surface + 7 instead of + 3 so canopies show up in observations.
- Home clearing cells that were `grass` on the server become `sand`, `dirt_path` or cottage blocks to match what the viewer always showed.

## Error handling

| Failure | Behavior |
|---------|----------|
| Unknown material name from the server | Magenta checker tile, one warning per name, no crash |
| Delta fetch fails | Keep the current world and retry on the next poll |
| Server seq lower than local seq | Clear local edits and resync from 0 |
| Worker throws while meshing a column | Keep the last good mesh, retry once, then log |
| Worker fails to start | Show the existing "Connecting" screen with an error and a retry button |
| WebGL context lost | Re-upload stored buffers on restore |

## Testing

### Frontend

Add Vitest as a dev dependency with an `npm test` script.

- `worldStore.test.ts`: get and set across chunk borders and negative coordinates; server edits override overlay edits; dirty columns include neighbors for border blocks.
- `mesher.test.ts`: a single block makes 6 faces; two adjacent opaque blocks make 10; glass next to glass hides the shared faces; sand under water keeps its top face; AO levels at an inside corner match the rule; crossed quads for flowers.
- `atlas.test.ts`: every block face in the registry resolves to a tile; an unknown name resolves to the missing tile.
- `worldgen.test.ts`: every cell in `shared/worldgen-fixture.json` matches.
- `buildMaterials.test.ts`: every plan kind, including the station, compiles to materials that exist in the registry.

### Backend

Extend the existing `unittest` suite.

- Each write path bumps `seq`: `put_block`, `finish` with a block edit, `step_loose_blocks`, `owner_action` placing a machine.
- `since` returns removals as `air`, respects `limit`, and sets `more`.
- Migration adds `seq` to a database created with the old schema and keeps its rows.
- The worldgen fixture matches.
- `BLOCKS` from `blocks.json` keeps every property the crafting tests rely on.

### Manual

- Run `/preview` and compare a screenshot with mockup C.
- Dig spots show solid stone and ore walls, not hollow shells.
- Trees and flowers render. The station, earlier builds and saved block edits appear in the same places as before.
- The build reveal still steps block by block.
- A dev-only `?debug` overlay shows fps, draw calls and mesh time per column. Check it in a 390 × 844 viewport.

## Done when

- `/preview` looks like mockup C.
- The world is solid underground and the server and client agree on every natural block (fixture passes in both languages).
- The existing saved world renders with everything in its place.
- `python3 -m unittest discover -s backend/tests`, `npm test` and `npm run build` pass.

## Out of scope

Mimo physics and collision, mine and place animations, server-side build compilation, falling-block entities, water flow, light propagation, the app wrapper, and the older `World` and `VoxelTest` pages, which keep the old renderer.
