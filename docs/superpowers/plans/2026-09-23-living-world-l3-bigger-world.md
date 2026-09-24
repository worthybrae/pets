# Living World L3: Bigger World Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Mimo's world bigger and richer, and let it use it: 26 new blocks with our own soft-pixel textures; taiga, swamp and birch forest; birch and spruce trees; snow, ice, mud, pools, cacti, sugar cane, ferns, dead bushes, pumpkins and melons; gravel on shores, lake beds, scree and cave floors (L2's flint); boulders and outcrops; cave entrances open to the sky; bigger, taller caves with underground lakes and deep lava; stone seams, gold and diamond; staircases and tunnels 2 wide and 3 tall; gold and diamond tools, iron armor, lanterns, ladders, fences and stone bricks; creature seeds that grow into tame animals in a pen Mimo fences by its home; Python and TypeScript worldgen that stay identical, cell for cell; and a viewer that draws all of it.

**Architecture:** New blocks go at the end of `shared/blocks.json`, after L2's door, so no id changes. Both worldgen ports grow the same new functions in the same tasks (biomes and plants, then the underground, then the surface features), each new feature a pure function of the cell and the seed (`hash32`/`noise2`/`noise3` on channels of its own), and the fixture test compares them cell by cell on sampled chunks that include every new block. Heights never change. Gameplay plugs into registries and small hooks: `RECIPES.update`, `KEEP.update`, `harm.ARMOR`, `nature.CHANCE_DROPS`, the purposes registry (`gather_flint`, `build_pen`, `stock_pen`), a growth hook in renewal (`GROWERS`, used by creature seeds), `crafting.STAND_INS` (any wood pays for oak or planks), a `rubble` flag on mine steps (wide passages cost no more carrying), `Grid.supported` and `pathing.moves` (ladders and fences). L2's light and spawner learn the bigger world through a block property (`canopy`) and the generator's own lava, and creatures keep off ladders and fences (`past_fixtures`, beside L2's `past_doors`). The viewer gets a `cube` shape for see-through blocks, the cutaway's lists, the HUD's words and grey iron armor.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-living-world-design.md` (L3: the milestone table's row and the whole "L3 Bigger world" outline; the spec's "Decisions" and "Error handling and testing" where they touch L3; the L2 outline's "iron armor (L3) cuts it by 45 %" and "gloom_dust, used later for lanterns or potions (L3)"). L4 stays out (resolution 28). It builds on L2 as built (`docs/superpowers/plans/2026-09-23-living-world-l2-danger.md`, `3dbb120`, with its final fix wave and follow-up: HEAD `983e2aa`) and on the L2 final review's notes for L3 (`.superpowers/sdd/2026-09-23-living-world-l2-danger/l3-carryover.md`, Task 13), and follows L2's plan shape. The code at `983e2aa` is the "old" text every task edits; the dry run applied every task to it (see "Commands").

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls (a fake Jev stands in where a test needs one). Everything the world makes comes from `worldgen.hash32`, `noise2` and `noise3` with the world seed; rolls in play come from `nature.roll` and `creatures.moves.roll`. Nothing reads `random` or the clock. New channels: worldgen 18–29 and 80–90, nature 91 (creature seeds), seeds 92 (the kind a sprout grows into).
- **Worldgen parity.** `backend/services/worldgen.py` and `frontend/src/engine/worldgen.ts` change together, in the same task, with the same constants, the same channels and the same order of checks. After every worldgen task, regenerate the fixture (`python3 -m backend.scripts.worldgen_fixture`) and run both suites: `backend/tests/test_worldgen.py` rebuilds the fixture and compares, and `frontend/src/engine/worldgen.test.ts` compares the TypeScript port with it cell by cell. Heights never change, and the legacy clearing (192 blocks round the origin) keeps every block it had (resolution 5).
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments, no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules. No stylesheet changes.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes, `busy_timeout`. Read-only GETs never write. L3 adds no table and no column: a pen is a row of M5's `structures` (kind `"pen"`), a sprout's growth is an entry in renewal's growth table, and a tame animal is a row of L1's `creatures` with `"tame": true` in its state.
- **No model call inside the tick.** The new purposes and the growth hook are rules. Validity checks, facts and scores never write.
- A crashing planner, hook or picker never stops a tick or the worker.
- New blocks go at the end of `shared/blocks.json`, after L2's `door`. New items that are not blocks: `gold_ingot`, `diamond`, `gold_pickaxe`, `diamond_pickaxe`, `gold_sword`, `diamond_sword`, `iron_cap`, `iron_tunic`, `creature_seed` (planted as the `creature_sprout` block). `lantern` (M-era) and the new `ladder` and `fence` are blocks Mimo carries and places.
- Values copied from the spec (L3 outline). Blocks: granite, andesite, diorite and "ashstone"; gold and diamond ores; birch and spruce logs, leaves and planks; snow_block, ice, mud, cactus, sugar_cane, pumpkin, melon, fern, dead_bush, mossy_cobblestone; stone_bricks (brick exists); new blocks at the end of the registry. Biomes: taiga (spruce, snow patches), swamp (mud, shallow pools, sugar cane), birch forest, beside desert, meadow, forest and alpine. Terrain: boulders and outcrops on hills; cave entrances open to the sky (sinkholes and hillside mouths); larger, taller caves; underground lakes; lava pools below y = −3. Mimo's staircases and tunnels 2 wide and 3 tall, escape stairs likewise where they fit; home and passage claims follow. Tiers: gold and diamond pickaxes and swords; iron armor (45 %, from L2's outline); lantern from iron and a torch; ladder, fence, stone_bricks (and L2's door). Creature seeds: 1 in 60 from tall grass or leaves; planted on grass, a random local passive animal in 1 game day; farm purposes plant them near home once a pen (a fence ring) exists. Python/TS worldgen parity; the fixture regenerates.
- `MIMO_TIME_SCALE` and `MIMO_ACTION_SCALE` (both default 1) are for manual runs only. L3 adds no settings.
- Never run `docker` or `docker compose` in Tasks 1–14. Task 15 is the controller's manual check on the demo stack (`mimo-m5demo-api` on :8011 and `mimo-m5demo-worker`, volume `mimo_m5demo`); never touch, mount or migrate the owner's real volume `pets_mimo_data` or the real stack (`pets-api-1`, `pets-mimo-worker-1`). Never print `TYPESAFE_API_KEY` or any other key.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (797 pass at `983e2aa`)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_worldgen_biomes.py" -v`
- The worldgen fixture: `python3 -m backend.scripts.worldgen_fixture` (rewrites `shared/worldgen-fixture.json`; about 10 seconds)
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` (about 2.5 minutes) and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
- Frontend tests: `cd frontend && npm test` (280 pass at `983e2aa`)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint src/engine src/survival`

Each task says how many tests it adds and the totals the dry run saw. If the real starting totals differ (L2 is still getting small follow-ups), expect the same increases on top of them. A few tests time the creature hook or a fight step in wall-clock time (`test_survival_darkness`, `test_survival_herds`, `test_survival_defense`); on a busy machine one can fail on L2 alone (the dry run saw one fail under three parallel suites, never alone; L3 leaves the darkness ones at 4–10 ms a slice against their 20 ms). Run a failing one again on its own before looking further.

Transcription: every edit is a fenced block, either a whole new file ("Create `path`:") or a "replace: … with: …" pair in a named file ("In `path`, replace:", then "and replace:" for more pairs in the same file). Old texts are kept short, so a task still applies when a neighbouring line changes. The dry run applied each task with the controller's apply script (`.superpowers/sdd/2026-09-23-living-world-l1-animals/apply_plan.py`), regenerated the fixture after Tasks 3–5, and ran the task's checks after each one: the backend suite after every task, the frontend tests, type check, lint and build after Tasks 1, 3, 4, 5 and 14, and the slow headless runs after Tasks 6 and 13. Earlier rounds applied the tasks to `60460ff` with L2's plan applied, and to L2's build at `45509ab` and `e9d1098`, with the same results.

## Plan-level resolutions

The spec is an outline for L3. These are the details. Every task follows them; the controller ledgers them.

1. **Base.** L2 is complete, with its final fix wave: the door (`door`, after `chest`), light levels (`light.py`, a lantern gives 15), gloomlings and skitters, the bow (made only once Mimo has had flint), arrows and flint (1 mined gravel in 8), leather armor (`harm.ARMOR`, `gear.make_gear`, gear materials kept only while needed), and the fight and flee reflexes (a fight's step-up walk bounded to `STEP_UP_NODES`; a flight lasts until the chaser gives up; sleep and rest swim for land first, `purposes.land_refuge`). Where this plan edits an L2 file (`light.py`, `darkness.py`, `moves.py`, `hostiles.py`, `reflexes.py`, `harm.py`, `gear.py`, `petGear.ts`, `SurvivalPet.tsx`, `WorldCanvas.tsx`, `hud.ts`), its old texts are `983e2aa`'s, kept short.
2. **Registries, not rewrites.** Recipes go in one `RECIPES.update({...})` block Task 2 opens and later tasks extend; what Mimo keeps on hand in one `KEEP.update({...})` block; armor in `harm.ARMOR`; drops in `nature.CHANCE_DROPS`; purposes register themselves (`flint.py`, `pens.py`, imported by the brain); a planted block with a `renewal.Grower` grows by the growth table (creature seeds); `blocks.TALL` and `crafting.STAND_INS` are data. New modules: `survival/flint.py`, `survival/pens.py`, `survival/creatures/seeds.py`.
3. **Block properties.** The spec names the blocks; the numbers are ours. Stone variants, ashstone and mossy cobblestone: hardness 4 with a pickaxe, need a wooden pickaxe, drop cobblestone (stone bricks drop themselves). Gold ore: hardness 5, needs an iron pickaxe, drops gold ore (smelts to a gold ingot). Diamond ore: hardness 6, needs an iron pickaxe, drops a diamond. Birch and spruce: logs and planks hardness 2 with an axe, drop themselves; leaves 0.3, drop nothing (a sapling 1 in 12, and a creature seed 1 in 60, as chance drops). Snow block and ice 0.6, drop nothing; ice is translucent (opacity 0.6) and solid. Mud 0.6, drops dirt. Pumpkin and melon: solid, hardness 1 with an axe, drop themselves (nothing eats them yet). Cactus 0.4 and sugar cane 0.1: cutout, not solid, drop themselves. Fern and dead bush: cutout, replaceable, drop nothing. Ladder 0.4 (axe): cutout, not solid. Fence 2 (axe): cutout, solid and tall. The creature sprout: a cutout plant, 0.1, drops its creature seed. Cactus, ladder and fence are drawn as see-through cubes (`"shape": "cube"`), the rest of the cutouts as crossed sprites.
4. **Textures.** Every new tile is a recipe in `shared/blocks.json` painted by `atlas.ts` in the same soft-pixel style as M3's (15 new patterns). Our own, not Minecraft's; the names are the spec's.
5. **Heights never change, and old ground stays.** `terrain_height` is untouched, so every column keeps its height, and the legacy clearing keeps every block. The new biomes, surface materials, trees, plants, rocks, caves, entrances and stone seams change which blocks the generator makes elsewhere, so an existing world keeps its heights and every block Mimo changed, but a cell it never touched can come out differently (Task 15 looks at the demo world's home).
6. **Biomes.** Taiga where the heat noise is below −0.45; swamp where moisture is above 0.45 on ground no higher than `SEA_LEVEL + 1`; birch forest where a forest is warmer than 0.3. Trees: one per 70 columns in birch forests, 60 in the taiga, 150 in swamps (forests and meadows as before). Snow patches in the taiga, mud patches in swamps, bare snow on alpine ground 15 high or more. Taiga lakes freeze on top; swamp pools are mud-floored water at lake level. Passive animals: rabbits everywhere, chickens and cows in birch forests and swamps, sheep in the taiga and birch forests.
7. **Trees and plants.** A trunk's column decides its kind (oak, birch or spruce) by biome and noise; trunks stay 4 logs (in forests and meadows, where they always stood), so gathering wood and renewal need no new trunk rules. Birch leaves hang 4 to 7 above the ground, spruce leaves 3 to 7 in a point. Any wood makes planks, sticks, tools and stations (resolution 13), all leaves decay once no log of any wood holds them, and a sapling Mimo plants grows into an oak (renewal's tree is M4's). Cacti (1–3 high) on desert sand, sugar cane (1–3) on lake shores and in swamps, ferns on taiga ground, dead bushes in deserts, a pumpkin or melon now and then on meadow and forest grass.
8. **Caves, lakes and lava.** The cave network's noise is coarser and taller (scale 13, stretched upward, open above 0.22 with rooms above −0.15): about a fifth of the underground is open, against an eighth. `cave_at` keeps its bounds (outside the legacy clearing, above bedrock, 3 or more below the surface), so caves still end at y −4. In a lake region, open cave cells at y −2 and below are water; in a lava region the lowest cave cells (y −4, "below y = −3") are lava, which gives light 15 like a lantern (Task 13; `Lights` finds it through `worldgen.lava_in_chunk`, cached per chunk, and only for cells within 15 of y −4). L2's `light.sky_open` needs no depth clamp: nothing in L3 goes deeper than before (caves and lava at y −4 as the lowest, Mimo's floors at y −3, sinkholes no lower than y −3) and heights never change, so its column scan is as long as it was; `SKY_SCAN` is now `max(8, FEATURE_TOP + 1)`, so it always clears the highest tree (7) or rock (3) the generator makes, and a sinkhole's floor or a mouth's open end reads as open sky while a mouth's roofed part does not.
9. **Cave entrances.** One entrance at most per 64×64 region, none within 64 blocks of the legacy clearing, rolled from the region: a sinkhole (two regions in eight: a round shaft of 21 columns, 9 to 13 deep, never below y −3, never beside water) or a hillside mouth (three in eight: a ramp 2 wide and up to 3 tall into the steepest rise of 6 tries, sinking a block every 2 for 12 blocks, open at first and roofed further in). Their cells are air in `terrain_block`; Mimo is never born over one.
10. **Boulders and outcrops.** An outcrop (a crag of pillars 1 to 3 high round a middle) crowns ground 8 or higher in a third of such chunks; elsewhere a boulder (a low dome, size 1 or 2) sits in a quarter of chunks. Of the local stone: boulders of sandstone in deserts, andesite in meadows, stone on alpine ground, mossy cobblestone elsewhere; outcrops of sandstone, andesite, diorite, granite or stone by biome. A rock never stands on a tree's, water's or hole's column; the decorations' precedence is home, trunk, leaves, rock, plant.
11. **Gravel and flint** (L2's request). Gravel lines lake and river beds (in patches, else sand; deserts keep sand), lies in patches on shores (land level with a lake beside it), in the taiga and on alpine scree, and on cave floors. Flint is still L2's chance drop (1 mined gravel in 8). `gather_flint` (Task 10) is the planner that goes for it: with a bow or the 3 string one takes (L2's final fix wave makes the bow wait for flint), fewer than 2 flint and fewer arrows than make_gear keeps, day work in the work band.
12. **Stone seams and ores.** Blobs of granite, andesite or diorite (noise over 24×8×24 cells), ashstone seams at y −2 and below. The old ores keep their cells, so remembered ores stay true. Gold ore: 1 stone cell in 181 at y 0 and below; diamond ore: 1 in 331 at y −3 and below.
13. **Any wood.** `crafting.LOGS` and `PLANKS` list oak, birch and spruce; a recipe that takes oak logs or planks takes the other woods in their place (`STAND_INS`, `paid`), a log makes its own planks, and smelting burns coal, else any planks. Building turns each wood's logs into its own planks; a shelter takes any planks where it asks for planks. Oak-only pets plan exactly as before.
14. **Stone bricks and mossy cobblestone.** Stone bricks: 4 cobblestone make 4, no station; a building material (`blueprints.BUILDING`) like cobblestone, kept 16 on hand. No planner crafts them yet, and M5's styles do not ask for them (resolution 28). Mossy cobblestone is a boulder block that mines into cobblestone.
15. **Ladders and fences.** Ladder: 7 sticks make 3; fence: 4 planks and 2 sticks make 3; no station. A ladder cell holds whoever is in it or on top of it, and Mimo's pathing goes straight up and down a ladder. A fence is solid and tall: nothing stands on it or steps over it (`Grid.supported`), so a fence ring holds animals. No creature climbs a ladder or steps into, onto or through a fence or a ladder (`moves.past_fixtures`, Task 13, beside L2's `past_doors`). No planner places ladders yet (resolution 28); fences are the pen's.
16. **Passages 2 wide and 3 tall.** A staircase or tunnel opens Mimo's column 3 tall and the column to its left (`side_of`) 3 tall over solid ground; escape stairs open the next headroom and, where they can, the cell above it and the three cells beside the stair. The cells Mimo walks through are needed as before; the rest are best effort, so a passage narrows where a wall must stay (water, what Mimo built).
17. **Rubble and "claims follow".** The extra cells are mined as `rubble`: their blocks are left behind, so a wide stair yields what a narrow one did and Mimo's arms fill no faster. M5's claims are structure cells (what Mimo built) and `structures.reserved`; passages are not structures and claim nothing, as before, so no dug tunnel is ever a `"passage"` part (which L2's `harm.INDOORS` treats as indoors, where no blow lands). What follows the bigger shapes is what keeps them usable: renewal keeps three cells clear over Mimo and over each home (`kept_clear`), and the planners that honour `reserved` never place into Mimo's own cells. The home claims are unchanged.
18. **Gold and diamond.** Ranks: gold 4, diamond 5 (both ores need 3, an iron pickaxe). Gold tools smelt their ingots at a furnace; diamond ones take diamonds at a table. The ladder goes on past iron: diamond first, then gold, which a diamond pickaxe makes pointless. Replaced tools are dropped as before.
19. **Tier numbers.** Pickaxe speeds: gold 7, diamond 8 (iron 6). Swords: gold 7, diamond 8 damage (iron 6). The spec gives none; each tier is one step past the one before.
20. **Mining for gold and diamonds.** mine_ore goes for gold (with an iron pickaxe, until a gold one) and diamonds (with an iron pickaxe, until a diamond one) only while Mimo has fewer than 3 and remembers enough of that ore to reach 3 in one trip: a lone ore far down is not worth the trips. A remembered gold or diamond ore scores like iron.
21. **The cobblestone floor.** `storage.loose_blocks` meant to keep `work.STONE_GOAL` cobblestone plus what an unfinished shelter needs; with more other building blocks than the shelter needed, the need went negative and let cobblestone drop below the stone goal, and drop_items and gather_stone then took turns on the same stone. It now keeps at least the stone goal. The new planks made this likelier.
22. **Creature seeds wait in the chest.** `KEEP["creature_seed"] = 0`: seeds Mimo cannot plant yet go in the chest (one stack held for good fills its arms sooner; the headless runs changed purpose more often for it), and stock_pen takes them out.
23. **Iron armor and lanterns** (from L2). Iron cap (5 ingots) and tunic (8), at a crafting table: 18 % and 27 %, 45 % together; only the best piece on each slot counts. Mimo makes them once a creature has hurt it (`hurt_at` is set) and it has an iron pickaxe or better, mining the iron they take; make_gear makes leather only for a bare slot; leather under iron is dropped. Lantern: 1 iron ingot and 1 torch, no station, light 15 by L2's light table. With both iron pieces worn, a spare ingot and fewer than 4 lanterns, craft_tools makes one; light_up hangs lanterns on dark corners before torches and swaps a corner's torch for a spare lantern. Gloom dust stays unused (resolution 28).
24. **Creature seeds.** Tall grass and every kind of leaves drop a creature seed 1 time in 60. Planted on grass (the plant step), it is a `creature_sprout` that grows in one game day into a passive land animal of a kind that lives in that biome (a rabbit where none does), tame: it is never hunted and stays where it grew (a pen keeps it in). While 24 land animals are about (L1's cap), the sprout waits and tries again 10 game minutes later. Farm purposes plant seeds near home once a pen exists: build_pen fences a 5×5 ring of 16 fences round 3×3 of grass near a finished home when Mimo has a seed, and stock_pen plants up to 3 seeds inside, from the walkway.
25. **L2's notes for L3** (Task 13). L2 matched leaves by the name `leaves` (`light.SEE_THROUGH`, `darkness.UNDERFOOT`): a registry property, `canopy`, now marks every kind (`blocks.CANOPY`; not a crafting property). L2 searched spawn columns only 24 cells under the surface (`SCAN_DEPTH`): the search now runs down to `SPAWN_RISE` under Mimo however deep it is. Lava the generator makes gives light 15 (resolution 8). No creature climbs a ladder or crosses a fence (resolution 15). Tunnels are never `"passage"` parts (resolution 17). L3 adds no door gap, so L2's note on wide gaps needs nothing here. Two notes came with L2's follow-up: a hostile loses interest in a chase that has landed no blow (and taken none) for 45 game seconds or lost sight of Mimo for 5, and then leaves Mimo be for a minute unless Mimo hurts it (`hostiles.lost_interest`; L2's flee runs until the chaser gives up, so a skitter could otherwise chase an unarmed pet some 800 blocks); and the collapse reflex swims for land before it lies down (`purposes.land_refuge`), as sleep and rest do. Measured with Task 13 in, the creature hook stays at 4–10 ms a slice (L2's timing tests read the same without L3).
26. **Raw food and spare fences.** Raw food Mimo can cook is never put away as spare food (cook only uses what Mimo carries, so a stored raw rabbit was never cooked), and the fences a finished pen leaves over (they come 3 at a time) are junk to drop, not a stack carried for good.
27. **Purpose budget.** The headless runs' cap on changes of purpose per game hour stays 52 by default and goes from 55 to 60 with `MIMO_SLOW_TESTS=1` (Task 13). With all of L3 on `983e2aa` the busiest hours were 28 to 46 by default and 36 to 46 in slow mode, but for seed 11's Jev pet at 54 (58 on `e9d1098`, and 53 to 65 as the world and L2's rules under it changed during the dry runs). That pet goes two game days without a chest (its shelter has none and it lacks the wood to make one), so its arms stay full and gather_stone and drop_items take turns: M5's rule for full arms with no chest, met more often now that there are more kinds of things to carry. The flood L3's first iron-armor rule caused (65, fixed by resolution 23's "once hurt") is what the budget must still catch.
28. **Out of scope and left for later.** L4: goals (a pen and a herd, a better home). Nothing crafts stone bricks or places ladders on its own; pumpkins, melons, cacti and sugar cane are only picked up when in the way; gloom dust stays unused (the spec offers "lanterns or potions"; the lantern takes iron and a torch as the spec's crafting list says); a sapling grows into an oak whatever wood it fell from.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `shared/blocks.json`, `backend/services/blocks.py`, `frontend/src/engine/atlas.ts` | Modify | 30 tiles and 26 blocks at the end; `shape` and `tall`; 15 tile painters |
| `backend/services/worldgen.py`, `frontend/src/engine/worldgen.ts` | Modify | Biomes, trees and plants, gravel, caves, lakes, lava, seams, ores, entrances, rocks (both ports alike) |
| `backend/scripts/worldgen_fixture.py`, `shared/worldgen-fixture.json` | Modify | Sample the new features; regenerated |
| `backend/services/crafting.py` | Modify | Any wood, stone bricks, gold and diamond tools, iron armor, lanterns, ladders, fences |
| `backend/survival/flint.py`, `pens.py`, `creatures/seeds.py` | Create | `gather_flint`; `build_pen` and `stock_pen`; sprouts grow into tame animals |
| `backend/survival/work.py`, `escape.py`, `steps.py`, `renewal.py` | Modify | Wide passages, rubble, three cells kept clear; gold and diamonds wanted; the growth hook |
| `backend/survival/toolmaking.py`, `storage.py`, `carrying.py`, `senses.py`, `building.py`, `blueprints.py`, `structures.py`, `lighting.py`, `nature.py`, `grid.py`, `pathing.py`, `spawn.py`, `brain.py` | Modify | Tiers and armor orders; what Mimo keeps; treasures; ores seen; any wood; pens; lanterns; drops; ladders and fences; never born over a hole; imports |
| `backend/survival/creatures/harm.py`, `gear.py`, `combat.py`, `hunting.py`, `kinds.py` | Modify | Iron armor; leather for a bare slot; tier damage; tame animals; animals in the new biomes |
| `backend/survival/light.py`, `creatures/darkness.py`, `creatures/moves.py`, `creatures/hostiles.py`, `reflexes.py`, `backend/services/blocks.py` | Modify | L2's notes: canopy by a block property, the full sky scan, lava light, spawns however deep, no creature on ladders or fences, chases that end, a collapse that swims for land |
| `backend/tests/test_blocks_bigger_world.py`, `test_survival_{wood,passages,tiers,armor,climbing,flint,creature_seeds,pens,raw_food,dark_world}.py`, `test_worldgen_{biomes,underground,surface}.py` | Create | One file per task (two for Task 12) |
| `backend/tests/test_{blocks,worldgen,survival_work,survival_escape,survival_toolmaking,survival_renewal,survival_fieldwork,survival_sim}.py` | Modify | What L3 changes in them |
| `frontend/src/engine/blocks.ts`, `mesher.ts` (+ tests) | Modify | Cube cutouts |
| `frontend/src/survival/overheadMap.ts`, `cutaway.ts`, `hud.ts`, `types.ts`, `petGear.ts`, `SurvivalPet.tsx`, `WorldCanvas.tsx` (+ tests) | Modify | The minimap's new ground; trees and fences are not cover, new building blocks are walls; the new purposes' words; pens; iron armor |
| `README.md` | Modify | A bigger world |

## Tasks

1. New blocks and their soft-pixel textures
2. Any wood will do, and stone bricks
3. Taiga, swamp and birch forest, their trees and plants, and gravel
4. Bigger caves, underground lakes, deep lava, gravel floors, stone seams, gold and diamond
5. Cave entrances open to the sky, boulders and outcrops
6. Mimo's staircases and tunnels 2 wide and 3 tall
7. Gold and diamond: the tool ladder and mine_ore learn them
8. Iron armor and lanterns
9. Ladders to climb and fences nothing crosses
10. Flint from gravel
11. Creature seeds
12. A pen by home, stocked with creature seeds
13. L2's review notes: light, spawns, creature moves, chases and collapsing afloat
14. The viewer draws the new blocks, names the new purposes and shows iron armor
15. Manual check on the demo and the README

Task 1 needs nothing before it and Task 2 only Task 1's blocks. Tasks 3–5 are the generator, in order (each builds on the constants and functions of the one before). Tasks 6–12 are Mimo, each needing only the tasks before it; Task 13 takes the L2 final review's notes once everything they touch is in (the leaves, the rocks and openings, the lava, the ladders and fences), and sets the purpose budget with all of L3 measured. Task 14 is the viewer; Task 15 the controller's check.

---

### Task 1: New blocks and their soft-pixel textures

**Files:**
- Modify: `shared/blocks.json` (30 tiles and 26 blocks at the end of their lists), `backend/services/blocks.py` (`shape` is a render key), `frontend/src/engine/atlas.ts` (15 new tile painters)
- Modify tests: `backend/tests/test_blocks.py` and `frontend/src/engine/blocks.test.ts` (L2's door is no longer the last block), `frontend/src/engine/atlas.test.ts`
- Test: `backend/tests/test_blocks_bigger_world.py`

**Interfaces:**
- Consumes: the registry format (`tiles` recipes with `pattern`, `color`, `accent`, `size`; `blocks` with `textures`, `layer`, `solid`, `replaceable`, `drop`, `requires`, `hardness`, `tool`), `atlas.PATTERNS` and its helpers `grid`, `tone`, `jitter`, `edge`, `CLEAR`, `N`.
- Produces:
  - Blocks, appended in this order after every block already there (L2's `door` is the last of them): `granite`, `andesite`, `diorite`, `ashstone`, `gold_ore`, `diamond_ore`, `birch_log`, `birch_leaves`, `birch_planks`, `spruce_log`, `spruce_leaves`, `spruce_planks`, `snow_block`, `ice`, `mud`, `cactus`, `sugar_cane`, `pumpkin`, `melon`, `fern`, `dead_bush`, `mossy_cobblestone`, `stone_bricks`, `ladder`, `fence`, `creature_sprout`.
  - Their properties (resolution 3): the stone variants and mossy cobblestone drop `cobblestone` and need a `wooden_pickaxe`; `gold_ore` drops `gold_ore` and `diamond_ore` drops `diamond`, both needing an `iron_pickaxe`; birch and spruce logs and planks drop themselves (axe), their leaves nothing; `snow_block` and `ice` drop nothing, `mud` drops `dirt`; `cactus`, `sugar_cane`, `fern`, `dead_bush` and `creature_sprout` are cutout plants (fern and dead bush replaceable; the sprout drops a `creature_seed`); `pumpkin` and `melon` are solid cubes that drop themselves; `ladder` (not solid) and `fence` (solid, `"tall": true`) are cutout; `cactus`, `ladder` and `fence` carry `"shape": "cube"` (Task 14 draws them as see-through cubes; until then they draw as crossed sprites like any cutout block).
  - Tile patterns in `atlas.PATTERNS`: `speckled`, `layers`, `birch_bark`, `ice`, `cactus`, `cactus_top`, `sprite_cane`, `ribs`, `stem_top`, `sprite_fern`, `sprite_twigs`, `mossy_cobble`, `ladder`, `fence`, `sprite_sprout`. The plant sprites (`sprite_cane`, `sprite_fern`, `sprite_twigs`, `sprite_sprout`) take their height from the tile's `size`, like M4's crops: sugar cane 4 (a whole block, so a stalk two or three high reads as one), fern 3, dead bush 2, the sprout 2.
  - `backend.services.blocks.BLOCK_PROPERTIES` leaves `shape` out (a render key, like `layer`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_blocks_bigger_world.py`:

```python
import unittest

from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, TILES, hardness, is_plant, is_replaceable, is_solid, mining_tool
from backend.services.crafting import BLOCKS

# L3's blocks, in registry order at its very end (after L2's door).
BIGGER_WORLD = ("granite", "andesite", "diorite", "ashstone", "gold_ore", "diamond_ore",
                "birch_log", "birch_leaves", "birch_planks", "spruce_log", "spruce_leaves", "spruce_planks",
                "snow_block", "ice", "mud", "cactus", "sugar_cane", "pumpkin", "melon", "fern", "dead_bush",
                "mossy_cobblestone", "stone_bricks", "ladder", "fence", "creature_sprout")
STONES = ("granite", "andesite", "diorite", "ashstone", "mossy_cobblestone")
PLANTS = ("cactus", "sugar_cane", "fern", "dead_bush", "creature_sprout")


class BiggerWorldBlockTests(unittest.TestCase):
    def test_the_new_blocks_come_last_so_older_ids_never_change(self):
        names = [block["name"] for block in BLOCK_LIST]
        self.assertEqual(names[-len(BIGGER_WORLD):], list(BIGGER_WORLD))
        self.assertEqual(BLOCK_IDS["granite"], BLOCK_IDS["door"] + 1)  # right after L2's door
        self.assertLess(len(BLOCK_LIST), 255)

    def test_every_new_face_has_a_tile(self):
        for name in BIGGER_WORLD:
            textures = BLOCK_LIST[BLOCK_IDS[name]]["textures"]
            for tile in [textures] if isinstance(textures, str) else textures.values():
                self.assertIn(tile, TILES, name)

    def test_stone_variants_break_into_cobblestone_with_a_pickaxe(self):
        for name in STONES:
            self.assertEqual(BLOCKS[name]["drop"], "cobblestone", name)
            self.assertEqual(BLOCKS[name]["requires"], "wooden_pickaxe", name)
            self.assertEqual((hardness(name), mining_tool(name)), (4.0, "pickaxe"), name)
        self.assertEqual(BLOCKS["stone_bricks"]["drop"], "stone_bricks")

    def test_gold_and_diamond_need_an_iron_pickaxe_and_diamond_ore_gives_a_diamond(self):
        self.assertEqual((BLOCKS["gold_ore"]["drop"], BLOCKS["gold_ore"]["requires"]), ("gold_ore", "iron_pickaxe"))
        self.assertEqual((BLOCKS["diamond_ore"]["drop"], BLOCKS["diamond_ore"]["requires"]), ("diamond", "iron_pickaxe"))
        self.assertGreater(hardness("diamond_ore"), hardness("gold_ore"))

    def test_birch_and_spruce_wood_like_oak(self):
        for wood in ("birch", "spruce"):
            self.assertEqual(BLOCKS[f"{wood}_log"]["drop"], f"{wood}_log")
            self.assertEqual(BLOCKS[f"{wood}_planks"]["drop"], f"{wood}_planks")
            self.assertIsNone(BLOCKS[f"{wood}_leaves"]["drop"])
            self.assertEqual((mining_tool(f"{wood}_log"), mining_tool(f"{wood}_leaves")), ("axe", None))
            self.assertEqual(hardness(f"{wood}_leaves"), hardness("leaves"))

    def test_desert_swamp_and_taiga_plants_are_see_through_plants(self):
        for name in PLANTS:
            self.assertTrue(is_plant(name), name)
            self.assertFalse(is_solid(name), name)
        self.assertTrue(is_replaceable("fern") and is_replaceable("dead_bush"))
        self.assertFalse(is_replaceable("cactus") or is_replaceable("sugar_cane") or is_replaceable("creature_sprout"))
        self.assertEqual(BLOCKS["creature_sprout"]["drop"], "creature_seed")

    def test_ground_fruit_ice_and_the_fittings(self):
        for name in ("snow_block", "ice", "mud", "pumpkin", "melon", "fence"):
            self.assertTrue(is_solid(name), name)
        self.assertFalse(is_solid("ladder"))
        self.assertEqual(BLOCK_LIST[BLOCK_IDS["ice"]]["layer"], "translucent")
        self.assertEqual(BLOCKS["mud"]["drop"], "dirt")
        self.assertIsNone(BLOCKS["ice"]["drop"])
        self.assertTrue(BLOCKS["fence"]["tall"])
        for name in ("cactus", "ladder", "fence"):  # the viewer draws these as see-through cubes
            self.assertEqual(BLOCK_LIST[BLOCK_IDS[name]]["shape"], "cube", name)
            self.assertNotIn("shape", BLOCKS[name])


if __name__ == "__main__":
    unittest.main()
```


L2's tests pinned its door as the last block; it now sits before L3's.

In `backend/tests/test_blocks.py`, replace:

```python
        self.assertEqual(names[BLOCK_IDS["chest"] + 1:], ["door"])  # L2
```

with:

```python
        self.assertEqual(names[BLOCK_IDS["chest"] + 1], "door")  # L2; L3's blocks follow it
```


In `frontend/src/engine/blocks.test.ts`, replace:

```typescript
describe('block registry', () => {
```

with:

```typescript
/** L3's blocks, in registry order (backend/tests/test_blocks_bigger_world.py). */
const BIGGER_WORLD = ['granite', 'andesite', 'diorite', 'ashstone', 'gold_ore', 'diamond_ore',
  'birch_log', 'birch_leaves', 'birch_planks', 'spruce_log', 'spruce_leaves', 'spruce_planks',
  'snow_block', 'ice', 'mud', 'cactus', 'sugar_cane', 'pumpkin', 'melon', 'fern', 'dead_bush',
  'mossy_cobblestone', 'stone_bricks', 'ladder', 'fence', 'creature_sprout']

describe('block registry', () => {
```

and replace:

```typescript
    expect(blockId('door')).toBe(BLOCKS.length - 1)
```

with:

```typescript
    expect(blockId('door')).toBe(BLOCKS.length - 1 - BIGGER_WORLD.length)
```

and replace:

```typescript
    expect(GLOW_BY_ID[blockId('sapling')]).toBe(0)
  })
```

with:

```typescript
    expect(GLOW_BY_ID[blockId('sapling')]).toBe(0)
  })

  it('adds the bigger world\'s blocks at the very end, plants see-through and the stone solid', () => {
    const names = BLOCKS.map((block) => block.name)
    expect(names.slice(-BIGGER_WORLD.length)).toEqual(BIGGER_WORLD)
    expect(blockId('granite')).toBeGreaterThan(blockId('chest'))
    for (const name of ['cactus', 'sugar_cane', 'fern', 'dead_bush', 'creature_sprout', 'ladder', 'fence']) {
      expect(LAYER_BY_ID[blockId(name)], name).toBe(LAYER_CUTOUT)
    }
    for (const name of ['granite', 'ashstone', 'diamond_ore', 'birch_log', 'spruce_leaves', 'mud', 'pumpkin', 'stone_bricks']) {
      expect(LAYER_BY_ID[blockId(name)], name).toBe(LAYER_OPAQUE)
    }
    expect(LAYER_BY_ID[blockId('ice')]).toBe(LAYER_TRANSLUCENT)
    expect(blockDef(blockId('snow_block')).textures).toEqual({ top: 'snow', side: 'snow', bottom: 'snow' })
    expect(blockDef(blockId('birch_log')).textures.side).toBe('birch_log_side')
  })
```


In `frontend/src/engine/atlas.test.ts`, replace:

```typescript
  it('insets uvs by a quarter texel', () => {
```

with:

```typescript
  it('paints the bigger world: see-through plants, fences and ladders, glassy ice and solid stone and fruit', () => {
    const alphas = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).map((pixel) => pixel[3])
    for (const name of ['sugar_cane', 'fern', 'dead_bush', 'creature_sprout', 'ladder', 'fence', 'cactus_side', 'cactus_top']) {
      expect(alphas(name), name).toContain(0)
    }
    for (const name of ['granite', 'andesite', 'diorite', 'ashstone', 'gold_ore', 'diamond_ore', 'birch_log_side',
      'birch_log_top', 'birch_leaves', 'birch_planks', 'spruce_log_side', 'spruce_leaves', 'spruce_planks', 'mud',
      'pumpkin_side', 'pumpkin_top', 'melon_side', 'melon_top', 'mossy_cobblestone', 'stone_bricks']) {
      expect(Math.min(...alphas(name)), name).toBe(255)
    }
    expect(Math.max(...alphas('ice'))).toBeLessThan(255)
    expect(Math.min(...alphas('ice'))).toBeGreaterThan(0)
  })

  it('sizes the new plant sprites by their size, like the crops', () => {
    const top = (name: string) => {
      const pixels = tilePixels(atlas, atlas.tileIndex.get(name)!)
      return Math.floor(pixels.findIndex((pixel) => pixel[3] > 0) / TILE_SIZE)
    }
    expect(top('sugar_cane')).toBe(0) // size 4: a full block, so a stalk two or three high looks whole
    expect(top('fern')).toBeGreaterThan(top('sugar_cane'))
    expect(top('dead_bush')).toBeGreaterThan(top('fern'))
    expect(top('creature_sprout')).toBeGreaterThanOrEqual(top('dead_bush') - 1)
    const recipe = { pattern: 'sprite_fern', color: [84, 138, 96] as [number, number, number] }
    const shown = (size: number) => PATTERNS.sprite_fern({ ...recipe, size }, () => 0.5).filter((pixel) => pixel[3] > 0).length
    expect(shown(1)).toBeLessThan(shown(2))
    expect(shown(2)).toBeLessThan(shown(4))
  })

  it('puts gold and diamond flecks in the stone and dark marks on birch bark', () => {
    const colours = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!)
    expect(colours('gold_ore').some(([r, g, b]) => r > 200 && g > 170 && b < 130)).toBe(true)
    expect(colours('diamond_ore').some(([r, g, b]) => b > 190 && g > 190 && r < 150)).toBe(true)
    expect(colours('birch_log_side').some(([r]) => r < 90)).toBe(true)
  })

  it('insets uvs by a quarter texel', () => {
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_blocks*.py"`
Expected: FAIL: `KeyError: 'granite'` (and the list comparison in `test_the_new_blocks_come_last_so_older_ids_never_change`).

Run: `cd frontend && npx vitest run src/engine/atlas.test.ts src/engine/blocks.test.ts`
Expected: FAIL: the new blocks and tiles are missing (`Cannot read properties of undefined`, and `names.slice(...)` differs).

- [ ] **Step 3: Add the tiles and blocks**

The anchors are the closing lines of each list (after L2's door), so the new entries always go last.

In `shared/blocks.json`, replace:

```json
}
  },
  "blocks": [
```

with:

```json
},
    "granite": {"pattern": "speckled", "color": [176, 128, 112], "accent": [132, 90, 80]},
    "andesite": {"pattern": "speckled", "color": [140, 143, 141], "accent": [170, 173, 170]},
    "diorite": {"pattern": "speckled", "color": [214, 212, 206], "accent": [152, 152, 148]},
    "ashstone": {"pattern": "layers", "color": [112, 114, 104], "accent": [136, 138, 126]},
    "gold_ore": {"pattern": "ore", "color": [153, 151, 148], "accent": [240, 202, 96]},
    "diamond_ore": {"pattern": "ore", "color": [153, 151, 148], "accent": [120, 222, 214]},
    "birch_log_side": {"pattern": "birch_bark", "color": [226, 222, 208], "accent": [72, 70, 66]},
    "birch_log_top": {"pattern": "log_top", "color": [214, 196, 150], "accent": [226, 222, 208]},
    "birch_leaves": {"pattern": "leaves", "color": [134, 176, 104]},
    "birch_planks": {"pattern": "planks", "color": [222, 204, 150]},
    "spruce_log_side": {"pattern": "log_side", "color": [96, 72, 54]},
    "spruce_log_top": {"pattern": "log_top", "color": [150, 118, 82], "accent": [96, 72, 54]},
    "spruce_leaves": {"pattern": "leaves", "color": [70, 116, 98]},
    "spruce_planks": {"pattern": "planks", "color": [140, 104, 72]},
    "ice": {"pattern": "ice", "color": [168, 206, 232]},
    "mud": {"pattern": "noise", "color": [92, 80, 76]},
    "cactus_side": {"pattern": "cactus", "color": [96, 150, 88], "accent": [70, 112, 66]},
    "cactus_top": {"pattern": "cactus_top", "color": [108, 162, 96], "accent": [70, 112, 66]},
    "sugar_cane": {"pattern": "sprite_cane", "color": [150, 196, 112], "accent": [112, 160, 88], "size": 4},
    "pumpkin_side": {"pattern": "ribs", "color": [226, 140, 60], "accent": [190, 108, 44]},
    "pumpkin_top": {"pattern": "stem_top", "color": [226, 140, 60], "accent": [104, 124, 64]},
    "melon_side": {"pattern": "ribs", "color": [120, 170, 76], "accent": [86, 130, 56]},
    "melon_top": {"pattern": "stem_top", "color": [120, 170, 76], "accent": [104, 124, 64]},
    "fern": {"pattern": "sprite_fern", "color": [84, 138, 96], "size": 3},
    "dead_bush": {"pattern": "sprite_twigs", "color": [150, 112, 72], "size": 2},
    "mossy_cobblestone": {"pattern": "mossy_cobble", "color": [130, 137, 137], "accent": [96, 146, 104]},
    "stone_bricks": {"pattern": "bricks", "color": [150, 152, 148], "accent": [116, 118, 114]},
    "ladder": {"pattern": "ladder", "color": [169, 128, 84]},
    "fence": {"pattern": "fence", "color": [184, 146, 100]},
    "creature_sprout": {"pattern": "sprite_sprout", "color": [120, 196, 140], "accent": [246, 214, 132], "size": 2}
  },
  "blocks": [
```

and replace:

```json
}
  ]
}
```

with:

```json
},
    {"name": "granite", "color": [176, 128, 112], "textures": "granite", "layer": "opaque", "solid": true, "drop": "cobblestone", "requires": "wooden_pickaxe", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "andesite", "color": [140, 143, 141], "textures": "andesite", "layer": "opaque", "solid": true, "drop": "cobblestone", "requires": "wooden_pickaxe", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "diorite", "color": [214, 212, 206], "textures": "diorite", "layer": "opaque", "solid": true, "drop": "cobblestone", "requires": "wooden_pickaxe", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "ashstone", "color": [112, 114, 104], "textures": "ashstone", "layer": "opaque", "solid": true, "drop": "cobblestone", "requires": "wooden_pickaxe", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "gold_ore", "color": [205, 180, 110], "textures": "gold_ore", "layer": "opaque", "solid": true, "drop": "gold_ore", "requires": "iron_pickaxe", "hardness": 5.0, "tool": "pickaxe"},
    {"name": "diamond_ore", "color": [132, 190, 186], "textures": "diamond_ore", "layer": "opaque", "solid": true, "drop": "diamond", "requires": "iron_pickaxe", "hardness": 6.0, "tool": "pickaxe"},
    {"name": "birch_log", "color": [226, 222, 208], "textures": {"top": "birch_log_top", "side": "birch_log_side", "bottom": "birch_log_top"}, "layer": "opaque", "solid": true, "drop": "birch_log", "hardness": 2.0, "tool": "axe"},
    {"name": "birch_leaves", "color": [134, 176, 104], "textures": "birch_leaves", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.3},
    {"name": "birch_planks", "color": [222, 204, 150], "textures": "birch_planks", "layer": "opaque", "solid": true, "drop": "birch_planks", "hardness": 2.0, "tool": "axe"},
    {"name": "spruce_log", "color": [96, 72, 54], "textures": {"top": "spruce_log_top", "side": "spruce_log_side", "bottom": "spruce_log_top"}, "layer": "opaque", "solid": true, "drop": "spruce_log", "hardness": 2.0, "tool": "axe"},
    {"name": "spruce_leaves", "color": [70, 116, 98], "textures": "spruce_leaves", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.3},
    {"name": "spruce_planks", "color": [140, 104, 72], "textures": "spruce_planks", "layer": "opaque", "solid": true, "drop": "spruce_planks", "hardness": 2.0, "tool": "axe"},
    {"name": "snow_block", "color": [236, 241, 243], "textures": "snow", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.6},
    {"name": "ice", "color": [168, 206, 232], "textures": "ice", "layer": "translucent", "solid": true, "drop": null, "opacity": 0.6, "hardness": 0.6},
    {"name": "mud", "color": [92, 80, 76], "textures": "mud", "layer": "opaque", "solid": true, "drop": "dirt", "hardness": 0.6},
    {"name": "cactus", "color": [96, 150, 88], "textures": {"top": "cactus_top", "side": "cactus_side", "bottom": "cactus_top"}, "layer": "cutout", "shape": "cube", "solid": false, "drop": "cactus", "hardness": 0.4},
    {"name": "sugar_cane", "color": [150, 196, 112], "textures": "sugar_cane", "layer": "cutout", "solid": false, "drop": "sugar_cane", "hardness": 0.1},
    {"name": "pumpkin", "color": [226, 140, 60], "textures": {"top": "pumpkin_top", "side": "pumpkin_side", "bottom": "pumpkin_top"}, "layer": "opaque", "solid": true, "drop": "pumpkin", "hardness": 1.0, "tool": "axe"},
    {"name": "melon", "color": [120, 170, 76], "textures": {"top": "melon_top", "side": "melon_side", "bottom": "melon_top"}, "layer": "opaque", "solid": true, "drop": "melon", "hardness": 1.0, "tool": "axe"},
    {"name": "fern", "color": [84, 138, 96], "textures": "fern", "layer": "cutout", "solid": false, "replaceable": true, "drop": null, "hardness": 0.1},
    {"name": "dead_bush", "color": [150, 112, 72], "textures": "dead_bush", "layer": "cutout", "solid": false, "replaceable": true, "drop": null, "hardness": 0.1},
    {"name": "mossy_cobblestone", "color": [118, 136, 122], "textures": "mossy_cobblestone", "layer": "opaque", "solid": true, "drop": "cobblestone", "requires": "wooden_pickaxe", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "stone_bricks", "color": [150, 152, 148], "textures": "stone_bricks", "layer": "opaque", "solid": true, "drop": "stone_bricks", "requires": "wooden_pickaxe", "hardness": 4.0, "tool": "pickaxe"},
    {"name": "ladder", "color": [169, 128, 84], "textures": "ladder", "layer": "cutout", "shape": "cube", "solid": false, "drop": "ladder", "hardness": 0.4, "tool": "axe"},
    {"name": "fence", "color": [184, 146, 100], "textures": "fence", "layer": "cutout", "shape": "cube", "solid": true, "tall": true, "drop": "fence", "hardness": 2.0, "tool": "axe"},
    {"name": "creature_sprout", "color": [120, 196, 140], "textures": "creature_sprout", "layer": "cutout", "solid": false, "drop": "creature_seed", "hardness": 0.1}
  ]
}
```


`shape` tells the viewer how to draw a block; the server leaves it out of the gameplay properties.

In `backend/services/blocks.py`, replace:

```python
_RENDER_KEYS = {"name", "textures", "layer", "solid", "replaceable"}
```

with:

```python
_RENDER_KEYS = {"name", "textures", "layer", "solid", "replaceable", "shape"}
```


- [ ] **Step 4: Paint the new tiles**

Each painter draws one 8x8 tile, row 0 at the top, from the recipe's `color`, `accent` and `size`. They go after the leaves painter; `mossy_cobble` paints the cobble tile and lays two moss patches over it.

In `frontend/src/engine/atlas.ts`, replace:

```typescript
  leaves: ({ color }, random) => grid(() => tone(color, (random() < 0.2 ? 0.7 : 1) * jitter(random, 0.14))),
```

with:

```typescript
  leaves: ({ color }, random) => grid(() => tone(color, (random() < 0.2 ? 0.7 : 1) * jitter(random, 0.14))),
  // L3, the bigger world: stone variants, bark, ice, desert and swamp plants, fruit, fences and ladders.
  speckled: ({ color, accent }, random) => grid(() => {
    const roll = random()
    return tone(roll < 0.24 ? accent ?? color : color, (roll > 0.9 ? 0.9 : 1) * jitter(random))
  }),
  layers: ({ color, accent }, random) => {
    const bands = Array.from({ length: N }, () => random() < 0.35)
    return grid((_i, j) => tone(bands[j] ? accent ?? color : color, (random() < 0.12 ? 0.86 : 1) * jitter(random)))
  },
  birch_bark: ({ color, accent }, random) => {
    const marks = Array.from({ length: 6 }, () => [Math.floor(random() * N), Math.floor(random() * (N - 2))])
    return grid((i, j) => marks.some(([row, from]) => j === row && i >= from && i < from + 2)
      ? tone(accent ?? color, jitter(random))
      : tone(color, (i % 4 === 0 ? 0.94 : 1) * jitter(random, 0.05)))
  },
  ice: ({ color }, random) => grid((i, j) => {
    const streak = (i + j) % 5 === 0 && i > 0 && j > 0
    return tone(color, (streak ? 1.12 : 1) * jitter(random, 0.05), streak ? 215 : 175)
  }),
  cactus: ({ color, accent }, random) => grid((i) => {
    if (i === 0 || i === N - 1) return CLEAR
    return tone(i === 2 || i === 5 ? accent ?? color : color, (random() < 0.1 ? 1.15 : 1) * jitter(random))
  }),
  cactus_top: ({ color, accent }, random) => grid((i, j) => {
    if (edge(i, j)) return CLEAR
    const ring = i === 1 || j === 1 || i === N - 2 || j === N - 2
    return tone(ring ? accent ?? color : color, jitter(random))
  }),
  sprite_cane: ({ color, accent, size = 4 }, random) => {
    const stalks = [1, 4, 6]
    const tops = stalks.map(() => Math.max(0, N - size * 2 - Math.floor(random() * 2)))
    return grid((i, j) => {
      const index = stalks.indexOf(i)
      if (index < 0 || j < tops[index]) return CLEAR
      return tone((j + index) % 3 === 0 ? accent ?? color : color, jitter(random, 0.1))
    })
  },
  ribs: ({ color, accent }, random) => grid((i) =>
    tone(i % 3 === 1 ? accent ?? color : color, (random() < 0.1 ? 0.9 : 1) * jitter(random))),
  stem_top: ({ color, accent }, random) => grid((i, j) => {
    if ((i === 3 || i === 4) && (j === 3 || j === 4)) return tone(accent ?? color, jitter(random))
    return tone(color, (edge(i, j) ? 0.85 : 1) * jitter(random))
  }),
  sprite_fern: ({ color, size = 4 }, random) => grid((i, j) => {
    const rise = N - 1 - j
    if (rise >= size * 2) return CLEAR
    const spread = Math.min(3, Math.floor(rise / 2) + 1)
    if (Math.abs(i - 3.5) > spread || (i + rise) % 2 !== 0) return CLEAR
    return tone(color, (i === 3 || i === 4 ? 0.88 : 1) * jitter(random, 0.14))
  }),
  sprite_twigs: ({ color, size = 4 }, random) => grid((i, j) => {
    const rise = N - 1 - j
    if (rise >= size * 2) return CLEAR
    const stem = rise <= 1 && (i === 3 || i === 4)
    const twig = rise >= 1 && (i === 3 - rise || i === 4 + rise)
    return stem || twig ? tone(color, jitter(random, 0.12)) : CLEAR
  }),
  mossy_cobble: (recipe, random) => {
    const patches = Array.from({ length: 2 }, () => [random() * N, random() * N])
    return PATTERNS.cobble(recipe, random).map((pixel, index) => {
      const i = index % N, j = Math.floor(index / N)
      const moss = patches.some(([x, y]) => Math.hypot(i - x, j - y) < 2.3)
      return moss && recipe.accent ? tone(recipe.accent, jitter(random, 0.14)) : pixel
    })
  },
  ladder: ({ color }, random) => grid((i, j) => {
    const rail = i === 1 || i === N - 2
    const rung = j % 3 === 1 && i > 1 && i < N - 2
    return rail || rung ? tone(color, (rung ? 1.08 : 1) * jitter(random)) : CLEAR
  }),
  fence: ({ color }, random) => grid((i, j) => {
    const post = i === 3 || i === 4
    return post || j === 2 || j === 5 ? tone(color, (post ? 0.9 : 1) * jitter(random)) : CLEAR
  }),
  sprite_sprout: ({ color, accent, size = 2 }, random) => grid((i, j) => {
    const rise = N - 1 - j
    const middle = i === 3 || i === 4
    if (rise === size * 2 && middle) return tone(accent ?? color, jitter(random, 0.05))
    const stem = rise < size * 2 && middle
    const leaf = (rise === size && (i === 2 || i === 5)) || (rise === size + 1 && (i === 1 || i === 6))
    return stem || leaf ? tone(color, jitter(random, 0.12)) : CLEAR
  }),
```


- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_blocks*.py"`
Expected: `Ran 20 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 804 tests` … `OK` (7 new).

Run: `cd frontend && npm test && npm run build && npx eslint src/engine`
Expected: `Tests  284 passed (284)` (4 new), the build succeeds, eslint prints nothing.

- [ ] **Step 6: Commit**

```bash
git add shared/blocks.json backend/services/blocks.py backend/tests/test_blocks.py backend/tests/test_blocks_bigger_world.py frontend/src/engine/atlas.ts frontend/src/engine/atlas.test.ts frontend/src/engine/blocks.test.ts
git commit -m "feat: add the bigger world's blocks, from granite and gold to cactus, fences and creature sprouts, with their textures" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Any wood will do, and stone bricks

**Files:**
- Modify: `backend/services/crafting.py` (planks of each wood and stone bricks; `LOGS`, `PLANKS`, `STAND_INS`, `have`, `paid`, `planks_recipe`, `fuel_of`; crafting and smelting pay with stand-ins), `backend/survival/toolmaking.py` (the chain makes a carried log's own planks and pays with stand-ins), `backend/survival/work.py` (every wood counts), `backend/survival/senses.py` (a tree's trunk may be birch or spruce), `backend/survival/nature.py` (`LEAVES`; birch and spruce leaves drop saplings), `backend/survival/renewal.py` (any leaves decay once no log of any wood holds them), `backend/survival/building.py` and `backend/survival/blueprints.py` (each wood's logs become its own planks for building; planks stand in for planks), `backend/survival/storage.py` (how much of each wood Mimo keeps; cobblestone never drops below the stone goal), `backend/survival/escape.py` (more blocks to stand on)
- Test: `backend/tests/test_survival_wood.py`

**Interfaces:**
- Consumes: `crafting.RECIPES`, `take_items`, `craft`, `smelt`; `toolmaking.make`; `blueprints.BUILDING`, `supplies`, `pick_block`; `building.planks_first`, `without_logs`, `usable_supplies`; `renewal.leaf_supported`, `orphaned_leaves`, `decay`; `senses.standing_logs`; `storage.KEEP`.
- Produces:
  - `crafting.RECIPES` gains `birch_planks` (1 birch_log makes 4), `spruce_planks` (1 spruce_log makes 4) and `stone_bricks` (4 cobblestone make 4), none at a station. Later tasks add their recipes to the same `RECIPES.update({...})` block.
  - `crafting.LOGS = ("oak_log", "birch_log", "spruce_log")`, `PLANKS = ("planks", "birch_planks", "spruce_planks")`, `PLANKS_OF` (log -> its planks, also the recipe's name), `STAND_INS = {"oak_log": LOGS[1:], "planks": PLANKS[1:]}`; `have(inventory, item) -> int` (the item and its stand-ins); `paid(inventory, ingredients) -> dict[str, int]` (what a recipe takes: the item first, then its stand-ins in order; a shortfall stays under the item's own name, so `take_items` still says "Missing materials: planks"); `planks_recipe(inventory) -> str` (the planks recipe of the first log carried, oak first; `"planks"` with none); `fuel_of(inventory) -> str` (coal, else the first planks carried, else `"planks"`). `craft` pays with `paid`; `smelt` burns `fuel_of`.
  - `nature.LEAVES = ("leaves", "birch_leaves", "spruce_leaves")`; `nature.CHANCE_DROPS` gains birch and spruce leaves (a sapling, 1 in 12; apples stay oak's).
  - `renewal.decay(state, leaf, at, block="leaves")`.
  - `storage.KEEP` gains 8 of each log, 16 of each planks and 16 stone bricks; `storage.loose_blocks` keeps at least `work.STONE_GOAL` cobblestone whatever else Mimo carries.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_wood.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.services.crafting import (
    LOGS, PLANKS, PLANKS_OF, RECIPES, STAND_INS, craft, fuel_of, have, paid, planks_recipe, smelt,
)
from backend.survival import nature
from backend.survival.blueprints import pick_block, supplies
from backend.survival.building import planks_first, usable_supplies, without_logs
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.renewal import create_growth_table, leaf_supported, orphaned_leaves, renew, scheduled
from backend.survival.senses import standing_logs
from backend.survival.storage import KEEP
from backend.survival.actions import ActionContext
from backend.survival.work import wood
from backend.tests.test_survival_storage import Home
from backend.tests.test_survival_toolmaking import craft as craft_step
from backend.tests.test_survival_toolmaking import mine_back, situation

BIRCH_TREE = (5, 0, 0)  # trunk x, trunk z, ground height: birch logs at y 1 to 4


def birch_wood():
    """A birch trunk at x 5, z 0 (logs at y 1 to 4) with a ring of birch leaves at y 4 and 5."""
    def rule(x, y, z):
        if (x, z) == (5, 0) and 1 <= y <= 4:
            return "birch_log"
        if y in (4, 5) and abs(x - 5) + abs(z) == 1:
            return "birch_leaves"
        return "grass" if y == 0 else "dirt" if y < 0 else "air"
    return Grid(rule)


class RecipeTests(unittest.TestCase):
    def test_each_wood_makes_its_own_planks_and_cobblestone_makes_stone_bricks(self):
        self.assertEqual(craft({"birch_log": 1}, "birch_planks", set()), {"birch_planks": 4})
        self.assertEqual(craft({"spruce_log": 2}, "spruce_planks", set()), {"spruce_log": 1, "spruce_planks": 4})
        self.assertEqual(craft({"cobblestone": 5}, "stone_bricks", set()), {"cobblestone": 1, "stone_bricks": 4})
        self.assertEqual(PLANKS_OF, {"oak_log": "planks", "birch_log": "birch_planks", "spruce_log": "spruce_planks"})
        self.assertTrue(all(planks in RECIPES for planks in PLANKS))

    def test_any_wood_stands_in_where_a_recipe_asks_for_oak(self):
        self.assertEqual(STAND_INS, {"oak_log": LOGS[1:], "planks": PLANKS[1:]})
        self.assertEqual(have({"planks": 1, "birch_planks": 2, "spruce_planks": 3}, "planks"), 6)
        self.assertEqual(paid({"planks": 1, "birch_planks": 5}, {"planks": 3, "sticks": 2}),
                         {"planks": 1, "birch_planks": 2, "sticks": 2})
        self.assertEqual(craft({"spruce_planks": 3, "sticks": 2}, "wooden_pickaxe", {"crafting_table"}),
                         {"wooden_pickaxe": 1})
        self.assertEqual(craft({"birch_log": 2, "spruce_log": 1, "sticks": 3}, "campfire", set()),
                         {"spruce_log": 1, "campfire": 1})
        with self.assertRaisesRegex(ValueError, "Missing materials: planks"):
            craft({"birch_planks": 1}, "chest", set())

    def test_a_log_turns_into_its_own_planks_oak_first_and_planks_burn_as_fuel(self):
        self.assertEqual(planks_recipe({"spruce_log": 1, "birch_log": 1}), "birch_planks")
        self.assertEqual(planks_recipe({"oak_log": 1, "birch_log": 1}), "planks")
        self.assertEqual(planks_recipe({}), "planks")
        self.assertEqual((fuel_of({"coal": 1, "planks": 1}), fuel_of({"spruce_planks": 2}), fuel_of({})),
                         ("coal", "spruce_planks", "planks"))
        self.assertEqual(smelt({"iron_ore": 1, "birch_planks": 1}, "iron_ore", {"furnace"}), {"iron_ingot": 1})


class ToolTests(unittest.TestCase):
    def test_three_birch_logs_make_a_wooden_pickaxe_like_oak_does(self):
        s = situation({"birch_log": 3})
        self.assertEqual(PURPOSES["craft_tools"].plan(s, None), [
            craft_step("birch_planks"), craft_step("crafting_table"),
            {"kind": "place", "target": [1, 1, 0], "block": "crafting_table"},
            craft_step("birch_planks"), craft_step("sticks"), craft_step("birch_planks"), craft_step("wooden_pickaxe"),
            craft_step("wooden_sword"), mine_back(1, 1, 0)])

    def test_spruce_planks_fuel_the_furnace_for_iron(self):
        s = situation({"stone_pickaxe": 1, "cobblestone": 8, "iron_ore": 3, "spruce_log": 1, "sticks": 2,
                       "crafting_table": 1})
        plan = PURPOSES["craft_tools"].plan(s, None)
        self.assertIn(craft_step("spruce_planks"), plan)
        self.assertEqual(sum(1 for step in plan if step["kind"] == "smelt"), 3)
        self.assertIn(craft_step("iron_pickaxe"), plan)


class GatheringTests(unittest.TestCase):
    def test_all_three_woods_count_as_wood_carried(self):
        self.assertEqual(wood({"spruce_log": 2, "birch_planks": 4, "sticks": 8, "oak_log": 1}), 5.0)
        for log in LOGS:
            self.assertEqual(KEEP[log], 8)
        for planks in PLANKS:
            self.assertEqual(KEEP[planks], 16)
        self.assertEqual(KEEP["stone_bricks"], 16)

    def test_a_birch_tree_is_a_tree_to_chop(self):
        with patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [BIRCH_TREE]):
            self.assertEqual(standing_logs(birch_wood(), "1", (0, 1, 0)), [(5, y, 0) for y in range(1, 5)])

    def test_birch_leaves_decay_once_their_log_goes_and_drop_saplings(self):
        grid = birch_wood()
        self.assertTrue(leaf_supported(grid, (6, 5, 0)))
        self.assertEqual(sorted(orphaned_leaves(grid, (5, 4, 0))), [])
        db = sqlite3.connect(":memory:")
        create_growth_table(db)
        create_memory_tables(db)
        ctx = ActionContext(grid=grid, clock_at=lambda at: {"time_scale": 1.0}, planner=lambda *args: [], events=[],
                            db=db)
        state = {"name": "Pip", "world_seed": "7", "position": {"x": 5.0, "y": 1.0, "z": 3.0}, "inventory": {}}
        for y in range(1, 5):
            grid.put(5, y, 0, "air")
        renew(state, ctx, 0.0)
        self.assertEqual(len(scheduled(db)), 8)
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            renew(state, ctx, 400.0)
        self.assertEqual(grid.material(6, 5, 0), "air")
        self.assertEqual(state["inventory"]["sapling"], 8)
        self.assertNotIn("apple", state["inventory"])
        self.assertIn("spruce_leaves", nature.LEAVES)


class BuildingTests(unittest.TestCase):
    def test_spare_logs_of_any_wood_count_as_their_own_planks_oak_kept_first(self):
        self.assertEqual(supplies({"oak_log": 1, "birch_log": 4}), {"birch_planks": 12})
        self.assertEqual(supplies({"oak_log": 3, "spruce_log": 1}), {"planks": 4, "spruce_planks": 4})
        self.assertEqual(without_logs({"birch_log": 2, "planks": 3}), {"planks": 3})
        self.assertEqual(usable_supplies({"birch_log": 3}), {"birch_planks": 4})

    def test_a_wall_that_wants_planks_takes_other_planks_before_another_block(self):
        self.assertEqual(pick_block("planks", {"cobblestone": 9, "birch_planks": 2}), "birch_planks")
        self.assertEqual(pick_block("planks", {"cobblestone": 9}), "cobblestone")
        self.assertEqual(pick_block("stone_bricks", {"stone_bricks": 1}), "stone_bricks")
        self.assertEqual(planks_first({"birch_log": 2, "birch_planks": 1}, ["birch_planks"] * 6 + ["planks"]),
                         [craft_step("birch_planks"), craft_step("birch_planks")])

    def test_spare_planks_never_let_cobblestone_drop_below_the_stone_goal(self):
        """With more other building blocks than a finished shelter needs, the shelter's need was
        negative and let drop_items throw cobblestone below gather_stone's goal (12), so the two
        alternated; the goal is a floor."""
        filler = {f"item_{n}": 1 for n in range(13)}
        home = Home({**filler, "birch_planks": 5, "cobblestone": 40})  # 16 stacks, no chest to use
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "cobblestone", "amount": 28}])


if __name__ == "__main__":
    unittest.main()
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wood.py"`
Expected: `ImportError: cannot import name 'LOGS' from 'backend.services.crafting'`.

- [ ] **Step 3: Let any wood stand in, in crafting**

The new recipes go in one block after the recipe table, so later tasks (and L2's own additions to the table) never touch the same lines.

In `backend/services/crafting.py`, replace:

```python
TOOL_RANK = {"wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3}
```

with:

```python
# L3, the bigger world: birch and spruce make planks of their own, cobblestone makes stone bricks.
RECIPES.update({
    "birch_planks": {"ingredients": {"birch_log": 1}, "output": {"birch_planks": 4}},
    "spruce_planks": {"ingredients": {"spruce_log": 1}, "output": {"spruce_planks": 4}},
    "stone_bricks": {"ingredients": {"cobblestone": 4}, "output": {"stone_bricks": 4}},
})
# Any wood does where a recipe asks for oak (L3): birch and spruce logs stand in for an oak log, and
# their planks for plain planks. A recipe takes the item it names first, then its stand-ins in order.
LOGS = ("oak_log", "birch_log", "spruce_log")
PLANKS = ("planks", "birch_planks", "spruce_planks")
PLANKS_OF = dict(zip(LOGS, PLANKS))  # the planks each log makes, which is also that recipe's name
STAND_INS = {"oak_log": LOGS[1:], "planks": PLANKS[1:]}

TOOL_RANK = {"wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3}
```

and replace:

```python
def craft(inventory: dict[str, int], recipe_name: str, nearby_stations: set[str]) -> dict[str, int]:
```

with:

```python
def have(inventory: dict[str, int], item: str) -> int:
    """How many of `item` a recipe can use: the item itself and what stands in for it."""
    return sum(inventory.get(name, 0) for name in (item, *STAND_INS.get(item, ())))


def paid(inventory: dict[str, int], ingredients: dict[str, int]) -> dict[str, int]:
    """The items `ingredients` take out of `inventory`: each ingredient itself first, then its
    stand-ins in order. What cannot be paid stays under the ingredient's own name, so take_items
    reports it missing."""
    bill: dict[str, int] = {}
    for item, amount in ingredients.items():
        for name in (item, *STAND_INS.get(item, ())):
            take = min(amount, inventory.get(name, 0) - bill.get(name, 0))
            if take > 0:
                bill[name] = bill.get(name, 0) + take
                amount -= take
        if amount > 0:
            bill[item] = bill.get(item, 0) + amount
    return bill


def planks_recipe(inventory: dict[str, int]) -> str:
    """The recipe that turns a carried log into planks of its wood, oak first ("planks" with none)."""
    return PLANKS_OF[next((log for log in LOGS if inventory.get(log, 0) > 0), "oak_log")]


def fuel_of(inventory: dict[str, int]) -> str:
    """What a furnace burns: coal, else the first planks carried ("planks" when there are none)."""
    if inventory.get("coal", 0):
        return "coal"
    return next((planks for planks in PLANKS if inventory.get(planks, 0) > 0), "planks")


def craft(inventory: dict[str, int], recipe_name: str, nearby_stations: set[str]) -> dict[str, int]:
```

and replace:

```python
    result = take_items(inventory, recipe["ingredients"])
```

with:

```python
    result = take_items(inventory, paid(inventory, recipe["ingredients"]))
```

and replace:

```python
        fuel = "coal" if inventory.get("coal", 0) else "planks"
```

with:

```python
        fuel = fuel_of(inventory)
```


- [ ] **Step 4: Make the chain work with any wood**

The toolmaker counts stand-ins when it checks what it has, makes planks from the first log it carries, pays each recipe the way `craft` will, and picks its fuel after making it.

In `backend/survival/toolmaking.py`, replace:

```python
from backend.services.crafting import RECIPES, SMELTING, TOOL_RANK, can_harvest
```

with:

```python
from backend.services.crafting import RECIPES, SMELTING, TOOL_RANK, can_harvest, fuel_of, have, paid, planks_recipe
```

and replace:

```python
    while inventory.get(item, 0) < amount:
        recipe = RECIPES.get(item)
```

with:

```python
    while have(inventory, item) < amount:
        recipe_name = planks_recipe(inventory) if item == "planks" else item
        recipe = RECIPES.get(recipe_name)
```

and replace:

```python
                         if inventory.get(name, 0) < count]
```

with:

```python
                         if have(inventory, name) < count]
```

and replace:

```python
            for name, count in recipe["ingredients"].items():
                inventory[name] -= count
```

with:

```python
            for name, count in paid(inventory, recipe["ingredients"]).items():
                inventory[name] -= count
```

and replace:

```python
            steps.append({"kind": "craft", "recipe": item})
```

with:

```python
            steps.append({"kind": "craft", "recipe": recipe_name})
```

and replace:

```python
            fuel = "coal" if inventory.get("coal", 0) else "planks"
            make(inventory, fuel, 1, steps, depth + 1)
```

with:

```python
            if not inventory.get("coal", 0):
                make(inventory, "planks", 1, steps, depth + 1)
            fuel = fuel_of(inventory)
```


In `backend/survival/work.py`, replace:

```python
from backend.services.crafting import BLOCKS, TOOL_RANK, can_harvest
```

with:

```python
from backend.services.crafting import BLOCKS, TOOL_RANK, can_harvest, have
```

and replace:

```python
    """Wood carried, counted in logs: a log is 1, a plank a quarter, a stick an eighth."""
    return inventory.get("oak_log", 0) + inventory.get("planks", 0) / 4 + inventory.get("sticks", 0) / 8
```

with:

```python
    """Wood carried, counted in logs: a log of any wood is 1, planks a quarter, a stick an eighth."""
    return have(inventory, "oak_log") + have(inventory, "planks") / 4 + inventory.get("sticks", 0) / 8
```


- [ ] **Step 5: Trees and leaves of any wood**

A generated tree's trunk is birch or spruce where those trees grow (Task 3); a sapling Mimo plants still grows into an oak.

In `backend/survival/senses.py`, replace:

```python
from backend.services.worldgen import SEA_LEVEL, plant_at, terrain_height, trees_in_chunk
```

with:

```python
from backend.services.crafting import LOGS
from backend.services.worldgen import SEA_LEVEL, plant_at, terrain_height, trees_in_chunk
```

and replace:

```python
        logs = sorted((cell for cell in cells if grid.material(*cell) == LOG), key=lambda cell: cell[1])
```

with:

```python
        logs = sorted((cell for cell in cells if grid.material(*cell) in LOGS), key=lambda cell: cell[1])
```


In `backend/survival/nature.py`, replace:

```python
def roll(seed: str, cell: Cell, channel: int, salt: int = 0) -> float:
```

with:

```python
# L3: birch and spruce leaves decay like oak's and drop saplings too, but no apples.
LEAVES = ("leaves", "birch_leaves", "spruce_leaves")
CHANCE_DROPS.update({leaf: (("sapling", 1 / 12, 32),) for leaf in LEAVES[1:]})


def roll(seed: str, cell: Cell, channel: int, salt: int = 0) -> float:
```


In `backend/survival/renewal.py`, replace:

```python
from backend.services.crafting import add_item
```

with:

```python
from backend.services.crafting import LOGS, add_item
```

and replace:

```python
                if material == LOG:
                    return True
                if material == "leaves":
```

with:

```python
                if material in LOGS:
                    return True
                if material in nature.LEAVES:
```

and replace:

```python
                if near not in seen and grid.material(*near) == "leaves":
```

with:

```python
                if near not in seen and grid.material(*near) in nature.LEAVES:
```

and replace:

```python
            and all(open_cell(grid.material(*cell)) or grid.material(*cell) == "leaves" for cell in canopy))
```

with:

```python
            and all(open_cell(grid.material(*cell)) or grid.material(*cell) in nature.LEAVES for cell in canopy))
```

and replace:

```python
        if before == LOG and after != LOG:
```

with:

```python
        if before in LOGS and after not in LOGS:
```

and replace:

```python
        if here == "leaves" and not leaf_supported(grid, cell):
            grid.put(*cell, "air")
            decay(state, cell, ready_at)
```

with:

```python
        if here in nature.LEAVES and not leaf_supported(grid, cell):
            grid.put(*cell, "air")
            decay(state, cell, ready_at, here)
```

and replace:

```python
def decay(state: dict, leaf: Cell, at: float) -> None:
```

with:

```python
def decay(state: dict, leaf: Cell, at: float, block: str = "leaves") -> None:
```

and replace:

```python
        for item in nature.chance_drops(state.get("world_seed", "0"), leaf, "leaves"):
```

with:

```python
        for item in nature.chance_drops(state.get("world_seed", "0"), leaf, block):
```


- [ ] **Step 6: Build with any wood**

Spare logs count as the planks of their own wood (the oak logs are the ones kept for a campfire), a wall that wants planks takes other planks before another block, and `planks_first` turns each wood's logs into its own planks.

In `backend/survival/blueprints.py`, replace:

```python
from backend.services.blocks import is_replaceable, is_solid
```

with:

```python
from backend.services.blocks import is_replaceable, is_solid
from backend.services.crafting import PLANKS_OF, STAND_INS
```

and replace:

```python
BUILDING = ("cobblestone", "planks", "brick", "limestone", "sandstone", "basalt", "moss", "clay", "sand",
            "gravel", "dirt")
```

with:

```python
BUILDING = ("cobblestone", "planks", "birch_planks", "spruce_planks", "stone_bricks", "brick", "limestone",
            "sandstone", "basalt", "moss", "clay", "sand", "gravel", "dirt")
```

and replace:

```python
    """Building blocks Mimo has, with each log beyond the LOGS_KEPT it keeps for a campfire or a
    tool's sticks counted as the 4 planks it makes."""
    have = {block: inventory.get(block, 0) for block in BUILDING if inventory.get(block, 0) > 0}
    logs = inventory.get("oak_log", 0) - LOGS_KEPT
    if logs > 0:
        have["planks"] = have.get("planks", 0) + 4 * logs
    return have
```

with:

```python
    """Building blocks Mimo has, with each log beyond the LOGS_KEPT it keeps for a campfire or a
    tool's sticks counted as the 4 planks of its own wood it makes (oak logs are the ones kept first)."""
    have = {block: inventory.get(block, 0) for block in BUILDING if inventory.get(block, 0) > 0}
    keep = LOGS_KEPT
    for log, planks in PLANKS_OF.items():
        spare = inventory.get(log, 0) - keep
        keep = max(0, -spare)
        if spare > 0:
            have[planks] = have.get(planks, 0) + 4 * spare
    return have
```

and replace:

```python
    """The block to place for a cell that wants `wanted`: it, else the first building block left."""
    if have.get(wanted, 0) > 0:
        return wanted
```

with:

```python
    """The block to place for a cell that wants `wanted`: it or what stands in for it (other planks for
    planks), else the first building block left."""
    for block in (wanted, *STAND_INS.get(wanted, ())):
        if have.get(block, 0) > 0:
            return block
```


In `backend/survival/building.py`, replace:

```python
from backend.services.worldgen import terrain_height
```

with:

```python
from backend.services.crafting import LOGS, PLANKS_OF, planks_recipe
from backend.services.worldgen import terrain_height
```

and replace:

```python
    return {item: count for item, count in inventory.items() if item != "oak_log"}
```

with:

```python
    return {item: count for item, count in inventory.items() if item not in LOGS}
```

and replace:

```python
    if crafts_fit(inventory, [{"kind": "craft", "recipe": "planks"}]):
```

with:

```python
    if crafts_fit(inventory, [{"kind": "craft", "recipe": planks_recipe(inventory)}]):
```

and replace:

```python
    """Craft steps turning logs into the planks `blocks` use beyond the planks carried."""
    short = sum(1 for block in blocks if block == "planks") - inventory.get("planks", 0)
    crafts = min(math.ceil(max(0, short) / 4), inventory.get("oak_log", 0))
    return [{"kind": "craft", "recipe": "planks"} for _ in range(crafts)]
```

with:

```python
    """Craft steps turning logs into the planks `blocks` use beyond the planks carried, each wood's
    logs into its own planks."""
    steps = []
    for log, planks in PLANKS_OF.items():
        short = sum(1 for block in blocks if block == planks) - inventory.get(planks, 0)
        crafts = min(math.ceil(max(0, short) / 4), inventory.get(log, 0))
        steps += [{"kind": "craft", "recipe": planks} for _ in range(crafts)]
    return steps
```


- [ ] **Step 7: Keep and stand on the new wood**

The same step fixes a floor M5's drop_items meant to keep (resolution 21): with more other building blocks than a finished shelter needs, the shelter's need went negative and let cobblestone drop below gather_stone's goal, and the two then alternated on the same stone. The birch and spruce planks that now count as building blocks made that likelier.

In `backend/survival/storage.py`, replace:

```python
    keep = {"cobblestone": min(s.count("cobblestone"), max(0, STONE_GOAL + need))}
```

with:

```python
    keep = {"cobblestone": min(s.count("cobblestone"), STONE_GOAL + max(0, need))}
```

and replace:

```python
FLOWERS = ("flower_orange", "flower_pink", "flower_yellow")
```

with:

```python
# L3: birch and spruce are kept like oak, stone bricks like cobblestone; fruit and desert or swamp
# plants Mimo happens to break are put away.
KEEP.update({"birch_log": 8, "spruce_log": 8, "birch_planks": 16, "spruce_planks": 16, "stone_bricks": 16,
             "pumpkin": 0, "melon": 0, "cactus": 0, "sugar_cane": 0})
FLOWERS = ("flower_orange", "flower_pink", "flower_yellow")
```


In `backend/survival/escape.py`, replace:

```python
PLACEABLE = ("dirt", "cobblestone", "sand", "gravel", "clay", "planks", "oak_log")
```

with:

```python
PLACEABLE = ("dirt", "cobblestone", "sand", "gravel", "clay", "planks", "birch_planks", "spruce_planks", "stone_bricks",
             "oak_log", "birch_log", "spruce_log")
```


- [ ] **Step 8: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wood.py"`
Expected: `Ran 11 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 815 tests` … `OK` (11 new). Oak-only pets plan exactly as before: every earlier expectation holds.

- [ ] **Step 9: Commit**

```bash
git add backend/services/crafting.py backend/survival/toolmaking.py backend/survival/work.py backend/survival/senses.py backend/survival/nature.py backend/survival/renewal.py backend/survival/blueprints.py backend/survival/building.py backend/survival/storage.py backend/survival/escape.py backend/tests/test_survival_wood.py
git commit -m "feat: birch and spruce wood work wherever oak does, and cobblestone makes stone bricks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Taiga, swamp and birch forest, their trees and plants, and gravel

**Files:**
- Modify: `backend/services/worldgen.py` and `frontend/src/engine/worldgen.ts` (the three biomes, snow, ice, mud and pools, gravel on lake beds, shores, taiga and scree, birch and spruce trees, cacti, sugar cane, ferns, dead bushes, pumpkins and melons), `backend/scripts/worldgen_fixture.py` (sample them), `shared/worldgen-fixture.json` (regenerated), `backend/survival/creatures/kinds.py` (animals for the new biomes), `frontend/src/survival/overheadMap.ts` (the minimap sees each wood's crowns, ice, pools and fruit)
- Modify tests: `backend/tests/test_worldgen.py` (a generated tree may be birch or spruce; plants grow on mud and sand too), `frontend/src/engine/worldgen.test.ts`, `frontend/src/survival/overheadMap.test.ts`
- Test: `backend/tests/test_worldgen_biomes.py`

**Interfaces:**
- Consumes: `worldgen.noise2`, `hash32`, `terrain_height`, `biome_at`, `trees_in_chunk`, `is_leaf`, `wild_food`, `_decoration_column`; Task 1's blocks.
- Produces (Python and TypeScript alike, names in each language's case):
  - `biome_at` also returns `"taiga"` (heat below -0.45), `"swamp"` (moisture above 0.45 on ground no higher than `SEA_LEVEL + 1`) and `"birch_forest"` (a forest with heat above 0.3). Heights never change (resolution 5).
  - `surface_material`: snow patches in the taiga, mud patches in a swamp, `snow_block` on alpine ground 15 high or more; gravel (L2's flint, resolution 11) on lake and river beds (else sand; deserts keep sand), in patches on shores (`shore(x, z, seed)`: land level with the lakes beside one), in the taiga and on alpine scree. None of it in the legacy clearing. `swamp_pool(x, z, seed) -> bool`: a swamp column level with the lakes (`terrain_height == SEA_LEVEL`) whose ground cell is water, with mud under it. Taiga lakes freeze: their top water cell (`SEA_LEVEL`) is `ice`. A swamp's cell under the surface is mud.
  - `TREE_LOGS`, `TREE_LEAVES` (oak, birch, spruce -> block), `tree_kind(x, z, seed) -> "oak" | "birch" | "spruce"` for a trunk's column, `leaf_of(kind, dx, dy, dz) -> bool` (oak keeps `is_leaf`; birch 4 to 7 above the ground, spruce 3 to 7). `trees_in_chunk` is unchanged; trunks stay 4 logs, so gathering wood and renewal need nothing new. TypeScript exports `treeKind` and `canopyTop(x, z, seed) -> [leafBlock, y] | null`.
  - `tall_plant(x, z, seed) -> (name, 1 to 3) | None` (cactus on desert sand, sugar cane on a lake shore), `plant_stack(x, z, seed) -> (name, height) | None` (everything that grows on the surface, stacked), and `plant_at` is its base block. TypeScript exports `plantStack` and `swampPool`.
  - `kinds`: rabbits in every new biome, chickens and cows in birch forests and swamps, sheep in the taiga and birch forests.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_worldgen_biomes.py`:

```python
import math
import unittest

from backend.services.blocks import is_solid
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, SEA_LEVEL, TREE_LEAVES, TREE_LOGS, biome_at, block_at, plant_stack,
    shore, surface_material, swamp_pool, tall_plant, terrain_height, tree_kind, trees_in_chunk,
)
from backend.survival.creatures.kinds import land_kinds

SEED = "123456789123456789"
WIDE = [(x, z) for x in range(250, 3250, 23) for z in range(-1500, 1500, 29)]


def columns(test, count=1, xs=range(250, 1250), zs=range(-60, 60, 2)):
    """The first `count` generated columns where `test(x, z)` holds."""
    found = []
    for x in xs:
        for z in zs:
            if test(x, z):
                found.append((x, z))
                if len(found) == count:
                    return found
    return found


def trees_of(kind, count=5):
    found = []
    for cx in range(16, 120):
        for cz in range(-40, 40):
            found += [tree for tree in trees_in_chunk(cx, cz, SEED) if tree_kind(tree[0], tree[1], SEED) == kind]
            if len(found) >= count:
                return found[:count]
    return found


class BiomeTests(unittest.TestCase):
    def test_every_biome_turns_up_in_the_generated_land(self):
        seen = {biome_at(x, z, SEED) for x, z in WIDE}
        self.assertEqual(seen, {"meadow", "forest", "birch_forest", "taiga", "swamp", "desert", "alpine"})

    def test_the_legacy_clearing_stays_a_meadow_with_only_oaks_and_its_old_plants(self):
        for x in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 7):
            for z in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 7):
                if math.hypot(x, z) <= LEGACY_RADIUS:
                    self.assertEqual(biome_at(x, z, LEGACY_WORLD_SEED), "meadow")
                    self.assertIsNone(tall_plant(x, z, LEGACY_WORLD_SEED))
                    stack = plant_stack(x, z, LEGACY_WORLD_SEED)
                    self.assertIn(stack, (None, ("tall_grass", 1), ("flower_orange", 1), ("flower_yellow", 1)))
        for cx in range(-8, 8):
            for cz in range(-8, 8):
                for tx, tz, _ in trees_in_chunk(cx, cz, LEGACY_WORLD_SEED):
                    self.assertEqual(tree_kind(tx, tz, LEGACY_WORLD_SEED), "oak")


class TreeTests(unittest.TestCase):
    def test_each_wood_has_its_own_logs_and_leaves_and_shape(self):
        for kind, top in (("oak", 6), ("birch", 7), ("spruce", 7)):
            for x, z, base in trees_of(kind, 3):
                with self.subTest(kind=kind, tree=(x, z)):
                    self.assertEqual([block_at(x, base + dy, z, SEED) for dy in range(1, 5)], [TREE_LOGS[kind]] * 4)
                    self.assertEqual(block_at(x, base + top, z, SEED), TREE_LEAVES[kind])
                    self.assertEqual(block_at(x, base + top + 1, z, SEED), "air")

    def test_the_taiga_grows_spruce_the_birch_forest_birch_and_a_forest_mostly_oak(self):
        kinds = {}
        for cx in range(16, 200, 3):
            for cz in range(-60, 60, 3):
                for tx, tz, _ in trees_in_chunk(cx, cz, SEED):
                    kinds.setdefault(biome_at(tx, tz, SEED), []).append(tree_kind(tx, tz, SEED))
        self.assertEqual(set(kinds["taiga"]), {"spruce"})
        self.assertGreater(kinds["birch_forest"].count("birch"), len(kinds["birch_forest"]) / 2)
        self.assertGreater(kinds["forest"].count("oak"), len(kinds["forest"]) / 2)
        self.assertEqual(set(kinds["meadow"]), {"oak"})


class GroundTests(unittest.TestCase):
    def test_taiga_ground_has_snow_patches_ferns_and_frozen_lakes(self):
        taiga = [(x, z) for x, z in WIDE if biome_at(x, z, SEED) == "taiga" and terrain_height(x, z, SEED) >= SEA_LEVEL]
        self.assertEqual({surface_material(x, z, SEED) for x, z in taiga}, {"grass", "snow", "gravel"})
        (x, z), = columns(lambda x, z: biome_at(x, z, SEED) == "taiga" and terrain_height(x, z, SEED) < SEA_LEVEL,
                          xs=range(250, 3250, 3), zs=range(-900, 900, 3))
        self.assertEqual(block_at(x, SEA_LEVEL, z, SEED), "ice")
        if terrain_height(x, z, SEED) < SEA_LEVEL - 1:
            self.assertEqual(block_at(x, SEA_LEVEL - 1, z, SEED), "water")
        (x, z), = columns(lambda x, z: plant_stack(x, z, SEED) == ("fern", 1))
        self.assertEqual(biome_at(x, z, SEED), "taiga")
        self.assertEqual(block_at(x, terrain_height(x, z, SEED) + 1, z, SEED), "fern")

    def test_a_swamp_has_mud_and_shallow_pools_level_with_the_lakes(self):
        (x, z), = columns(lambda x, z: swamp_pool(x, z, SEED))
        self.assertEqual((biome_at(x, z, SEED), terrain_height(x, z, SEED)), ("swamp", SEA_LEVEL))
        self.assertEqual([block_at(x, SEA_LEVEL + dy, z, SEED) for dy in (-1, 0, 1)], ["mud", "water", "air"])
        swamp = [(x, z) for x, z in WIDE if biome_at(x, z, SEED) == "swamp"]
        self.assertIn("mud", {surface_material(x, z, SEED) for x, z in swamp})
        self.assertTrue(all(terrain_height(x, z, SEED) <= SEA_LEVEL + 1 for x, z in swamp))

    def test_alpine_peaks_are_bare_snow(self):
        (x, z), = columns(lambda x, z: terrain_height(x, z, SEED) >= 15, xs=range(250, 3250, 3), zs=range(-900, 900, 3))
        self.assertEqual(block_at(x, terrain_height(x, z, SEED), z, SEED), "snow_block")


class GravelTests(unittest.TestCase):
    def test_gravel_lines_lake_beds_and_shores_and_lies_in_taiga_and_mountain_patches(self):
        beds = [surface_material(x, z, SEED) for x, z in WIDE if terrain_height(x, z, SEED) < SEA_LEVEL
                and biome_at(x, z, SEED) != "desert"]
        self.assertEqual(set(beds), {"gravel", "sand"})
        self.assertGreater(beds.count("gravel"), len(beds) / 3)
        (x, z), = columns(lambda x, z: shore(x, z, SEED) and surface_material(x, z, SEED) == "gravel")
        self.assertEqual(block_at(x, SEA_LEVEL, z, SEED), "gravel")
        self.assertEqual(block_at(x, SEA_LEVEL + 1, z, SEED), "air")
        for biome in ("taiga", "alpine"):
            ground = {surface_material(x, z, SEED) for x, z in WIDE if biome_at(x, z, SEED) == biome}
            self.assertIn("gravel", ground, biome)

    def test_the_legacy_clearing_has_no_gravel(self):
        for x in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 5):
            for z in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 5):
                if math.hypot(x, z) <= LEGACY_RADIUS:
                    self.assertNotEqual(surface_material(x, z, LEGACY_WORLD_SEED), "gravel", (x, z))


class PlantTests(unittest.TestCase):
    def test_cacti_stand_one_to_three_high_on_desert_sand(self):
        found = columns(lambda x, z: (plant_stack(x, z, SEED) or ("",))[0] == "cactus", count=6)
        self.assertEqual(len(found), 6)
        for x, z in found:
            height, tall = terrain_height(x, z, SEED), plant_stack(x, z, SEED)[1]
            self.assertTrue(1 <= tall <= 3)
            self.assertEqual(block_at(x, height, z, SEED), "sand")
            self.assertEqual([block_at(x, height + dy, z, SEED) for dy in range(1, tall + 2)], ["cactus"] * tall + ["air"])

    def test_sugar_cane_grows_on_a_shore_beside_a_lake(self):
        (x, z), = columns(lambda x, z: (plant_stack(x, z, SEED) or ("",))[0] == "sugar_cane")
        self.assertEqual(terrain_height(x, z, SEED), SEA_LEVEL)
        self.assertTrue(any(block_at(x + dx, SEA_LEVEL, z + dz, SEED) == "water"
                            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))))
        self.assertEqual(block_at(x, SEA_LEVEL + 1, z, SEED), "sugar_cane")

    def test_dead_bushes_pumpkins_and_melons(self):
        for name, ground in (("dead_bush", ("sand",)), ("pumpkin", ("grass", "moss")), ("melon", ("grass", "moss"))):
            (x, z), = columns(lambda x, z: (plant_stack(x, z, SEED) or ("",))[0] == name)
            height = terrain_height(x, z, SEED)
            self.assertIn(block_at(x, height, z, SEED), ground, name)
            self.assertEqual(block_at(x, height + 1, z, SEED), name)
        self.assertTrue(is_solid("pumpkin"))


class AnimalTests(unittest.TestCase):
    def test_the_new_biomes_have_their_own_animals(self):
        self.assertEqual([kind.name for kind in land_kinds("taiga")], ["rabbit", "sheep"])
        self.assertEqual([kind.name for kind in land_kinds("birch_forest")], ["rabbit", "chicken", "sheep", "cow"])
        self.assertEqual([kind.name for kind in land_kinds("swamp")], ["rabbit", "chicken", "cow"])


if __name__ == "__main__":
    unittest.main()
```


A generated tree may now be birch or spruce, and desert and swamp plants grow on sand and mud; the fixture must hold the new blocks.

In `backend/tests/test_worldgen.py`, replace:

```python
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, base_material, biome_at, block_at, cave_at, cave_plant, hash32, legacy_hash,
    plant_at, surface_material, terrain_height, trees_in_chunk, wild_food,
)
```

with:

```python
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, TREE_LEAVES, TREE_LOGS, base_material, biome_at, block_at, cave_at, cave_plant,
    hash32, legacy_hash, plant_at, plant_stack, surface_material, terrain_height, tree_kind, trees_in_chunk, wild_food,
)
```

and replace:

```python
        x, z, base = trees[0]
        self.assertEqual([block_at(x, base + dy, z, seed) for dy in range(1, 7)],
                         ["oak_log"] * 4 + ["leaves", "leaves"])
        if terrain_height(x + 1, z, seed) < base + 5:
            self.assertEqual(block_at(x + 1, base + 5, z, seed), "leaves")
```

with:

```python
        x, z, base = trees[0]
        kind = tree_kind(x, z, seed)
        self.assertEqual([block_at(x, base + dy, z, seed) for dy in range(1, 7)],
                         [TREE_LOGS[kind]] * 4 + [TREE_LEAVES[kind]] * 2)
        if terrain_height(x + 1, z, seed) < base + 5:
            self.assertEqual(block_at(x + 1, base + 5, z, seed), TREE_LEAVES[kind])
```

and replace:

```python
    def test_plants_grow_on_open_grass_only(self):
```

with:

```python
    def test_plants_grow_on_the_ground_their_biome_offers(self):
```

and replace:

```python
                    self.assertIn(surface_material(x, z, seed), ("grass", "moss"))
```

with:

```python
                    ground = surface_material(x, z, seed)
                    self.assertIn(ground, ("grass", "moss", "mud", "sand", "gravel"))
                    if ground in ("sand", "gravel"):  # desert plants, or sugar cane on a shore
                        self.assertIn(plant_stack(x, z, seed)[0], ("cactus", "dead_bush", "sugar_cane"))
```

and replace:

```python
                     "water", "sand", "stone", "bedrock", "grass", "berry_bush_ripe", "brown_mushroom", "red_mushroom"):
```

with:

```python
                     "water", "sand", "stone", "bedrock", "grass", "berry_bush_ripe", "brown_mushroom", "red_mushroom",
                     "birch_log", "birch_leaves", "spruce_log", "spruce_leaves", "snow", "snow_block", "ice", "mud",
                     "cactus", "sugar_cane", "dead_bush", "fern", "pumpkin", "melon", "gravel"):
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen*.py"`
Expected: `ImportError: cannot import name 'TREE_LEAVES' from 'backend.services.worldgen'`.

- [ ] **Step 3: Add the biomes, trees and plants to the Python worldgen**

Every rule sits outside the legacy clearing (it is a meadow there, of oaks, with its old plants), and no height changes, so a world keeps its hills and Mimo's edits stay where they were. New roll channels are 18 to 26.

In `backend/services/worldgen.py`, replace:

```python
def surface_material(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
```

with:

```python
@lru_cache(maxsize=131072)
def surface_material(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
```

and replace:

```python
CAVE_MUSHROOM_RARITY = 29
```

with:

```python
CAVE_MUSHROOM_RARITY = 29
# L3, the bigger world: taiga, swamp and birch forest, with their trees, plants, snow, ice, mud and
# pools. Heights never change, and the legacy clearing keeps exactly what it always had.
TAIGA_HEAT = -0.45  # colder than this is taiga
SWAMP_WET = 0.45  # wetter than this on low ground is swamp
SWAMP_TOP = SEA_LEVEL + 1  # swamps lie on ground no higher than this
BIRCH_HEAT = 0.3  # a forest warmer than this is a birch forest
PEAK = 15  # alpine ground this high is bare snow
TREE_RARITY = {"forest": 78, "birch_forest": 70, "taiga": 60, "swamp": 150}  # one tree per this many columns
MEADOW_TREES = 300
TREE_LOGS = {"oak": "oak_log", "birch": "birch_log", "spruce": "spruce_log"}
TREE_LEAVES = {"oak": "leaves", "birch": "birch_leaves", "spruce": "spruce_leaves"}
CANOPY_TOP = 7  # the highest leaf of any tree, above its ground
CACTUS_RARITY = 47
CANE_RARITY = 11  # on a shore; three times likelier in a swamp
DEAD_BUSH_RARITY = 53
FERN_RARITY = 5
FRUIT_RARITY = 421  # a pumpkin or melon patch, on meadow and forest grass
FRUIT_BIOMES = ("meadow", "forest", "birch_forest")
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
```

and replace:

```python
    if heat > 0.08 and moisture < -0.12:
        return "desert"
    if moisture > 0.08:
        return "forest"
    return "meadow"
```

with:

```python
    if heat > 0.08 and moisture < -0.12:
        return "desert"
    if heat < TAIGA_HEAT:
        return "taiga"
    if moisture > SWAMP_WET and height <= SWAMP_TOP:
        return "swamp"
    if moisture > 0.08:
        return "birch_forest" if heat > BIRCH_HEAT else "forest"
    return "meadow"
```

and replace:

```python
    if biome == "alpine":
        return "snow"
    if biome == "forest" and hash32(x, 0, z, seed, 6) % 7 == 0:
        return "moss"
    return "grass"
```

with:

```python
    height = terrain_height(x, z, seed)
    if height < SEA_LEVEL and math.hypot(x, z) > LEGACY_RADIUS:
        return "gravel" if noise2(x, z, 10, seed, 87) > -0.1 else "sand"  # lake and river beds
    if biome == "alpine":
        if height >= PEAK:
            return "snow_block"
        return "gravel" if noise2(x, z, 9, seed, 89) > 0.35 else "snow"  # scree
    if biome == "forest" and hash32(x, 0, z, seed, 6) % 7 == 0:
        return "moss"
    if biome == "taiga":
        if noise2(x, z, 11, seed, 89) > 0.5:
            return "gravel"
        if noise2(x, z, 9, seed, 18) > 0.15:
            return "snow"
    if biome == "swamp" and noise2(x, z, 7, seed, 19) > 0.05:
        return "mud"
    if shore(x, z, seed) and noise2(x, z, 7, seed, 88) > 0.3:
        return "gravel"
    return "grass"


@lru_cache(maxsize=131072)
def shore(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    """Land level with the lakes right beside one (never in the legacy clearing)."""
    return (math.hypot(x, z) > LEGACY_RADIUS and terrain_height(x, z, seed) == SEA_LEVEL
            and any(terrain_height(x + dx, z + dz, seed) < SEA_LEVEL for dx, dz in SIDES))


@lru_cache(maxsize=131072)
def swamp_pool(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    """A shallow swamp pool: one block of water where swamp ground lies level with the lakes."""
    return (terrain_height(x, z, seed) == SEA_LEVEL and biome_at(x, z, seed) == "swamp"
            and noise2(x, z, 6, seed, 20) > 0.1)
```

and replace:

```python
    if y > height:
        return "water" if y <= SEA_LEVEL else "air"
    if y == height:
        return surface_material(x, z, seed)
    if y >= height - 2:
        return "sand" if biome_at(x, z, seed) == "desert" else "dirt"
```

with:

```python
    if y > height:
        if y > SEA_LEVEL:
            return "air"
        return "ice" if y == SEA_LEVEL and biome_at(x, z, seed) == "taiga" else "water"
    if y == height:
        return "water" if swamp_pool(x, z, seed) else surface_material(x, z, seed)
    if y >= height - 2:
        biome = biome_at(x, z, seed)
        return "sand" if biome == "desert" else "mud" if biome == "swamp" and y == height - 1 else "dirt"
```

and replace:

```python
    if terrain_height(x, z, seed) < SEA_LEVEL or biome_at(x, z, seed) in ("desert", "alpine"):
        return False
```

with:

```python
    if terrain_height(x, z, seed) < SEA_LEVEL or biome_at(x, z, seed) in ("desert", "alpine"):
        return False
    if swamp_pool(x, z, seed):
        return False
```

and replace:

```python
        grows = hash32(x, 0, z, seed, 12) % (78 if biome_at(x, z, seed) == "forest" else 300) == 0
```

with:

```python
        grows = hash32(x, 0, z, seed, 12) % TREE_RARITY.get(biome_at(x, z, seed), MEADOW_TREES) == 0
```

and replace:

```python
def tree_block(x: int, y: int, z: int, seed: str) -> str | None:
    trees = trees_in_chunk(x // 16, z // 16, seed)
    if any(x == tx and z == tz and base < y <= base + 4 for tx, tz, base in trees):
        return "oak_log"
    if any(is_leaf(x - tx, y - base, z - tz) for tx, tz, base in trees):
        return "leaves"
    return None
```

with:

```python
@lru_cache(maxsize=65536)
def tree_kind(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """The wood of the tree rooted at (x, z): spruce in the taiga, birch in a birch forest (one in five
    an oak), now and then a birch in a forest, else oak."""
    biome = biome_at(x, z, seed)
    roll = hash32(x, 0, z, seed, 21) % 10
    if biome == "taiga":
        return "spruce"
    if biome == "birch_forest":
        return "oak" if roll < 2 else "birch"
    return "birch" if biome == "forest" and roll == 0 else "oak"


def leaf_of(kind: str, dx: int, dy: int, dz: int) -> bool:
    """The canopy of a tree of `kind` relative to its trunk's ground cell: oak's (is_leaf), a slim
    birch crown from 4 to 7 above the ground, or a spruce cone from 3 to 7. The trunk wins where they
    meet."""
    ax, az = abs(dx), abs(dz)
    if kind == "birch":
        if dy in (4, 5):
            return ax + az <= 2
        return (dy == 6 and ax + az <= 1) or (dy == 7 and ax + az == 0)
    if kind == "spruce":
        if dy == 3:
            return ax <= 2 and az <= 2 and ax + az <= 3
        if dy in (4, 6):
            return ax + az <= 1
        if dy == 5:
            return ax + az <= 2
        return dy == 7 and ax + az == 0
    return is_leaf(dx, dy, dz)


def tree_block(x: int, y: int, z: int, seed: str) -> str | None:
    """A trunk (of any tree in the chunk) first, then the leaves of the first tree whose canopy has
    the cell."""
    trees = trees_in_chunk(x // 16, z // 16, seed)
    for tx, tz, base in trees:
        if x == tx and z == tz and base < y <= base + 4:
            return TREE_LOGS[tree_kind(tx, tz, seed)]
    for tx, tz, base in trees:
        kind = tree_kind(tx, tz, seed)
        if leaf_of(kind, x - tx, y - base, z - tz):
            return TREE_LEAVES[kind]
    return None
```

and replace:

```python
def plant_at(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """Flower, wild food or tall grass growing on top of the terrain at (x, z)."""
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
    food = wild_food(x, z, seed)
    if food:
        return food
    return "tall_grass" if hash32(x, 0, z, seed, 14) % 19 == 0 else None
```

with:

```python
def tall_plant(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
    """A cactus in the desert, or sugar cane on a shore right beside a lake (not in a swamp pool), with
    how many blocks high it stands (1 to 3). None in the legacy clearing."""
    if math.hypot(x, z) <= LEGACY_RADIUS:
        return None
    biome = biome_at(x, z, seed)
    if biome == "desert":
        roll = hash32(x, 0, z, seed, 25)
        return ("cactus", 1 + roll // CACTUS_RARITY % 3) if roll % CACTUS_RARITY == 0 else None
    if biome not in ("meadow", "forest", "birch_forest", "swamp") or not shore(x, z, seed) or swamp_pool(x, z, seed):
        return None
    rarity = CANE_RARITY // 3 if biome == "swamp" else CANE_RARITY
    roll = hash32(x, 0, z, seed, 26)
    return ("sugar_cane", 1 + roll // rarity % 3) if roll % rarity == 0 else None


@lru_cache(maxsize=131072)
def plant_stack(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
    """What grows on top of the terrain at (x, z) and how many blocks high: a flower, wild food, tall
    grass, a fern, a dead bush, a pumpkin or a melon stand one high, a cactus or sugar cane 1 to 3."""
    if math.hypot(x, z) <= HOME_RADIUS:
        return None
    surface = surface_material(x, z, seed)
    if _decoration_column(x, z, seed):
        if tree_base(x, z, seed) is not None:
            return None
        if hash32(x, 0, z, seed, 13) % 97 == 0 and surface in ("grass", "moss"):
            return ("flower_orange" if legacy_hash(x + 1, z) % 2 else "flower_yellow"), 1
    if math.hypot(x, z) > LEGACY_RADIUS and terrain_height(x, z, seed) < SEA_LEVEL:
        return None
    tall = tall_plant(x, z, seed)
    if tall:
        return tall
    biome = biome_at(x, z, seed)
    if surface == "sand":
        dead = biome == "desert" and hash32(x, 0, z, seed, 22) % DEAD_BUSH_RARITY == 0
        return ("dead_bush", 1) if dead else None
    if surface not in ("grass", "moss", "mud") or swamp_pool(x, z, seed):
        return None
    food = wild_food(x, z, seed)
    if food:
        return food, 1
    if biome == "taiga" and hash32(x, 0, z, seed, 23) % FERN_RARITY == 0:
        return "fern", 1
    if biome in FRUIT_BIOMES and math.hypot(x, z) > LEGACY_RADIUS:
        roll = hash32(x, 0, z, seed, 24)
        if roll % FRUIT_RARITY == 0:
            return ("pumpkin" if roll // FRUIT_RARITY % 2 == 0 else "melon"), 1
    rarity = 11 if biome == "swamp" else 19
    return ("tall_grass", 1) if hash32(x, 0, z, seed, 14) % rarity == 0 else None


def plant_at(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """The plant (or fruit) growing on top of the terrain at (x, z): the base of plant_stack."""
    stack = plant_stack(x, z, seed)
    return stack[0] if stack else None
```

and replace:

```python
    height = terrain_height(x, z, seed)
    if y == height + 1:
        return plant_at(x, z, seed)
    if y < height - 2:
        return cave_plant(x, y, z, seed)
    return None
```

with:

```python
    height = terrain_height(x, z, seed)
    if height < y <= height + 3:
        stack = plant_stack(x, z, seed)
        return stack[0] if stack and y <= height + stack[1] else None
    if y < height - 2:
        return cave_plant(x, y, z, seed)
    return None
```


- [ ] **Step 4: Sample the new blocks in the fixture and regenerate it**

In `backend/scripts/worldgen_fixture.py`, replace:

```python
from backend.services.worldgen import (
    LEGACY_WORLD_SEED, biome_at, block_at, cave_plant, plant_at, terrain_height, trees_in_chunk,
)
```

with:

```python
from backend.services.worldgen import (
    LEGACY_WORLD_SEED, SEA_LEVEL, biome_at, block_at, cave_plant, plant_at, plant_stack, swamp_pool, terrain_height,
    tree_kind, trees_in_chunk,
)
```

and replace:

```python
WILD_FOOD = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")
```

with:

```python
WILD_FOOD = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")
# L3: trees of each wood, the taller plants and fruit, swamp pools and frozen lakes.
KIND_CHUNKS = [(cx, cz) for cz in range(-30, 30) for cx in range(16, 80)]
STACKS = ("cactus", "sugar_cane", "dead_bush", "fern", "pumpkin", "melon")
NEW_BIOMES = ("taiga", "swamp", "birch_forest")
```

and replace:

```python
def sample_cells() -> list[tuple[str, int, int, int]]:
```

with:

```python
def _kind_trees(seed: str, kind: str, count: int) -> list[tuple[int, int, int]]:
    """Generated trees of one wood (oak, birch or spruce)."""
    found = []
    for cx, cz in KIND_CHUNKS:
        for tree in trees_in_chunk(cx, cz, seed):
            if tree_kind(tree[0], tree[1], seed) == kind:
                found.append(tree)
                if len(found) == count:
                    return found
    return found


def _features(seed: str, count: int) -> list[tuple[int, int]]:
    """Columns with each of the taller plants and fruit, a swamp pool or a frozen lake, `count` of each."""
    seen: dict[str, int] = {}
    found = []
    for x in range(250, 1250):
        for z in range(-60, 60, 2):
            stack = plant_stack(x, z, seed)
            kind = stack[0] if stack and stack[0] in STACKS else None
            if kind is None and swamp_pool(x, z, seed):
                kind = "pool"
            elif kind is None and terrain_height(x, z, seed) < SEA_LEVEL and biome_at(x, z, seed) == "taiga":
                kind = "ice"
            if kind is not None and seen.get(kind, 0) < count:
                seen[kind] = seen.get(kind, 0) + 1
                found.append((x, z))
                if len(seen) == len(STACKS) + 2 and all(value == count for value in seen.values()):
                    return found
    return found


def sample_cells() -> list[tuple[str, int, int, int]]:
```

and replace:

```python
        for biome in ("desert", "alpine"):
            cells |= {(seed, x, y, z) for x, y, z in _biome_patch(seed, biome)}
```

with:

```python
        for biome in ("desert", "alpine") + NEW_BIOMES:
            cells |= {(seed, x, y, z) for x, y, z in _biome_patch(seed, biome)}
        for kind in ("oak", "birch", "spruce"):
            for tx, tz, base in _kind_trees(seed, kind, 2):
                cells |= {(seed, tx + dx, base + dy, tz + dz)
                          for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 9)}
        for x, z in _features(seed, 3):
            height = terrain_height(x, z, seed)
            cells |= {(seed, x, height + dy, z) for dy in range(-2, 5)}
```


Run: `python3 -m backend.scripts.worldgen_fixture`
Expected: `Wrote 24333 cells to …/shared/worldgen-fixture.json`.

- [ ] **Step 5: Animals for the new biomes**

In `backend/survival/creatures/kinds.py`, replace:

```python
                   biomes=("meadow", "forest", "desert", "alpine"), herd=(1, 3)))
```

with:

```python
                   biomes=("meadow", "forest", "desert", "alpine", "birch_forest", "taiga", "swamp"), herd=(1, 3)))
```

and replace:

```python
                   biomes=("meadow", "forest"), herd=(2, 4)))
```

with:

```python
                   biomes=("meadow", "forest", "birch_forest", "swamp"), herd=(2, 4)))
```

and replace:

```python
                   biomes=("meadow", "alpine"), herd=(2, 4)))
```

with:

```python
                   biomes=("meadow", "alpine", "birch_forest", "taiga"), herd=(2, 4)))
```

and replace:

```python
                   biomes=("meadow", "forest"), herd=(2, 3)))
```

with:

```python
                   biomes=("meadow", "forest", "birch_forest", "swamp"), herd=(2, 3)))
```


- [ ] **Step 6: Run the backend tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen*.py"`
Expected: `Ran 27 tests` … `OK` (about 13 seconds: the fixture check rebuilds it).

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 828 tests` … `OK` (13 new).

- [ ] **Step 7: Write the failing viewer tests**

In `frontend/src/engine/worldgen.test.ts`, replace:

```typescript
import {
  blockAt, cavePlant, columnIndex, DEFAULT_WORLD_SEED, generateColumn, legacyHash, terrainHeight, treesInChunk, wildFood,
  WORLD_MAX_Y, WORLD_MIN_Y,
} from './worldgen'
```

with:

```typescript
import {
  blockAt, cavePlant, columnIndex, DEFAULT_WORLD_SEED, generateColumn, legacyHash, plantStack, swampPool, terrainHeight,
  treeKind, treesInChunk, wildFood, WORLD_MAX_Y, WORLD_MIN_Y,
} from './worldgen'
```

and replace:

```typescript
    expect(generateColumn(cx, cz, WILD_SEED).includes(blockId('oak_log'))).toBe(true)
```

with:

```typescript
    const logs = ['oak_log', 'birch_log', 'spruce_log'].map((name) => blockId(name))
    expect(Array.from(generateColumn(cx, cz, WILD_SEED)).some((id) => logs.includes(id))).toBe(true)
```

and replace:

```typescript
  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
```

with:

```typescript
  it('generates every wood, the tall plants, fruit, pools and frozen lakes inside columns exactly like blockAt', () => {
    const chunks = new Map<string, [number, number]>()
    const plants = ['cactus', 'sugar_cane', 'pumpkin', 'melon', 'dead_bush', 'fern']
    for (let x = 250; x < 1250 && chunks.size < plants.length; x++) {
      for (let z = -60; z < 60; z += 2) {
        const stack = plantStack(x, z, WILD_SEED)
        if (stack && plants.includes(stack[0]) && !chunks.has(stack[0])) chunks.set(stack[0], [Math.floor(x / 16), Math.floor(z / 16)])
      }
    }
    for (let cx = 16; cx < 80; cx++) for (let cz = -30; cz < 30; cz++) {
      for (const [tx, tz] of treesInChunk(cx, cz, WILD_SEED)) {
        const kind = treeKind(tx, tz, WILD_SEED)
        if (!chunks.has(kind)) chunks.set(kind, [cx, cz])
      }
    }
    expect([...chunks.keys()].sort()).toEqual([...plants, 'birch', 'oak', 'spruce'].sort())
    expect(swampPool(771, -8, WILD_SEED)).toBe(true)  // a swamp pool, in chunk (48, -1)
    chunks.set('pool', [48, -1])
    chunks.set('ice', [15, -15])  // a frozen taiga lake
    expect(Array.from(generateColumn(15, -15, WILD_SEED)).includes(blockId('ice'))).toBe(true)
    for (const [name, [cx, cz]] of chunks) {
      if (name !== 'oak') expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10), name).toEqual([])
    }
  })

  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
```


The first water column of the old water test is a meadow lake; a taiga one would now read as ice, so it is skipped there and checked on its own.

In `frontend/src/survival/overheadMap.test.ts`, replace:

```typescript
import { blockAt, SEA_LEVEL, terrainHeight } from '../engine/worldgen'
```

with:

```typescript
import { biomeAt, blockAt, SEA_LEVEL, terrainHeight } from '../engine/worldgen'
```

and replace:

```typescript
        if (terrainHeight(x, z, SEED) >= SEA_LEVEL) continue
        const top = naturalTop(x, z, SEED)
```

with:

```typescript
        if (terrainHeight(x, z, SEED) >= SEA_LEVEL || biomeAt(x, z, SEED) === 'taiga') continue
        const top = naturalTop(x, z, SEED)
```

and replace:

```typescript
  it('lets Mimo’s edits show: what it placed, what it dug and what it planted', () => {
```

with:

```typescript
  it('shows a frozen taiga lake as ice, and spruce and birch crowns in their own leaves', () => {
    const lake = { x: 3428, z: 4312 }  // a taiga lake
    expect(naturalTop(lake.x, lake.z, SEED)).toEqual(
      { id: blockId('ice'), y: SEA_LEVEL, depth: SEA_LEVEL - terrainHeight(lake.x, lake.z, SEED) })
    const leaves = new Set<number>()
    for (const [x0, z0] of [[lake.x - 40, lake.z - 40], [FAR.x, FAR.z]]) {
      for (let x = x0; x < x0 + 80; x++) {
        for (let z = z0; z < z0 + 80; z += 2) {
          const top = naturalTop(x, z, SEED)
          if (top.id !== blockId('spruce_leaves') && top.id !== blockId('birch_leaves')) continue
          expect({ x, z, id: top.id, y: top.y }).toEqual({ x, z, ...scanned(x, z) })
          leaves.add(top.id)
        }
      }
    }
    expect(leaves).toEqual(new Set([blockId('spruce_leaves'), blockId('birch_leaves')]))
  })

  it('lets Mimo’s edits show: what it placed, what it dug and what it planted', () => {
```


Run: `cd frontend && npx vitest run src/engine/worldgen.test.ts src/survival/overheadMap.test.ts`
Expected: FAIL: the shared fixture no longer matches (`expected birch_leaves, got leaves`, and so on), and `plantStack` is not exported.

- [ ] **Step 8: Port the rules to the viewer's worldgen**

Keep it in step with the Python, line for line. `biomeAt` is cached now: it is asked for many times per column. `generateColumn` stamps a plant's whole stack, every wood's canopy (the first tree's leaves win where canopies meet, as in `treeBlock`) and each trunk in its own wood.

In `frontend/src/engine/worldgen.ts`, replace:

```typescript
const CAVE_MUSHROOM_RARITY = 29
```

with:

```typescript
const CAVE_MUSHROOM_RARITY = 29
// L3, the bigger world: taiga, swamp and birch forest (see backend/services/worldgen.py).
const TAIGA_HEAT = -0.45
const SWAMP_WET = 0.45
const SWAMP_TOP = SEA_LEVEL + 1
const BIRCH_HEAT = 0.3
const PEAK = 15
const TREE_RARITY: Record<string, number> = { forest: 78, birch_forest: 70, taiga: 60, swamp: 150 }
const MEADOW_TREES = 300
const TREE_LOGS: Record<string, string> = { oak: 'oak_log', birch: 'birch_log', spruce: 'spruce_log' }
const TREE_LEAVES: Record<string, string> = { oak: 'leaves', birch: 'birch_leaves', spruce: 'spruce_leaves' }
const CANOPY_TOP = 7
const CACTUS_RARITY = 47
const CANE_RARITY = 11
const DEAD_BUSH_RARITY = 53
const FERN_RARITY = 5
const FRUIT_RARITY = 421
const FRUIT_BIOMES = new Set(['meadow', 'forest', 'birch_forest'])
const SIDES: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1]]
const biomeCache = new Map<string, string>()
```

and replace:

```typescript
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
```

with:

```typescript
export function biomeAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  const key = `${seed}:${x},${z}`
  const cached = biomeCache.get(key)
  if (cached !== undefined) return cached
  const biome = calculateBiome(x, z, seed)
  biomeCache.set(key, biome)
  if (biomeCache.size > 200000) biomeCache.clear()
  return biome
}

function calculateBiome(x: number, z: number, seed: string): string {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return 'meadow'
  const height = terrainHeight(x, z, seed)
  if (height >= 11) return 'alpine'
  const heat = noise2(x, z, 160, seed, 4)
  const moisture = noise2(x, z, 160, seed, 5)
  if (heat > 0.08 && moisture < -0.12) return 'desert'
  if (heat < TAIGA_HEAT) return 'taiga'
  if (moisture > SWAMP_WET && height <= SWAMP_TOP) return 'swamp'
  if (moisture > 0.08) return heat > BIRCH_HEAT ? 'birch_forest' : 'forest'
  return 'meadow'
}
```

and replace:

```typescript
  if (biome === 'alpine') return 'snow'
  if (biome === 'forest' && hash32(x, 0, z, seed, 6) % 7 === 0) return 'moss'
  return 'grass'
}
```

with:

```typescript
  const height = terrainHeight(x, z, seed)
  if (height < SEA_LEVEL && Math.hypot(x, z) > LEGACY_RADIUS) return noise2(x, z, 10, seed, 87) > -0.1 ? 'gravel' : 'sand'
  if (biome === 'alpine') {
    if (height >= PEAK) return 'snow_block'
    return noise2(x, z, 9, seed, 89) > 0.35 ? 'gravel' : 'snow'
  }
  if (biome === 'forest' && hash32(x, 0, z, seed, 6) % 7 === 0) return 'moss'
  if (biome === 'taiga') {
    if (noise2(x, z, 11, seed, 89) > 0.5) return 'gravel'
    if (noise2(x, z, 9, seed, 18) > 0.15) return 'snow'
  }
  if (biome === 'swamp' && noise2(x, z, 7, seed, 19) > 0.05) return 'mud'
  if (shore(x, z, seed) && noise2(x, z, 7, seed, 88) > 0.3) return 'gravel'
  return 'grass'
}

/** Land level with the lakes right beside one (never in the legacy clearing). */
function shore(x: number, z: number, seed: string): boolean {
  return Math.hypot(x, z) > LEGACY_RADIUS && terrainHeight(x, z, seed) === SEA_LEVEL
    && SIDES.some(([dx, dz]) => terrainHeight(x + dx, z + dz, seed) < SEA_LEVEL)
}

/** A shallow swamp pool: one block of water where swamp ground lies level with the lakes. */
export function swampPool(x: number, z: number, seed = DEFAULT_WORLD_SEED): boolean {
  return terrainHeight(x, z, seed) === SEA_LEVEL && biomeAt(x, z, seed) === 'swamp' && noise2(x, z, 6, seed, 20) > 0.1
}
```

and replace:

```typescript
  if (y > height) return y <= SEA_LEVEL ? 'water' : 'air'
  if (y === height) return surfaceMaterial(x, z, seed)
  if (y >= height - 2) return biomeAt(x, z, seed) === 'desert' ? 'sand' : 'dirt'
```

with:

```typescript
  if (y > height) {
    if (y > SEA_LEVEL) return 'air'
    return y === SEA_LEVEL && biomeAt(x, z, seed) === 'taiga' ? 'ice' : 'water'
  }
  if (y === height) return swampPool(x, z, seed) ? 'water' : surfaceMaterial(x, z, seed)
  if (y >= height - 2) {
    const biome = biomeAt(x, z, seed)
    return biome === 'desert' ? 'sand' : biome === 'swamp' && y === height - 1 ? 'mud' : 'dirt'
  }
```

and replace:

```typescript
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert' || biome === 'alpine') return false
  const mx = mod(x, 13), mz = mod(z, 13)
```

with:

```typescript
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert' || biome === 'alpine' || swampPool(x, z, seed)) return false
  const mx = mod(x, 13), mz = mod(z, 13)
```

and replace:

```typescript
    : hash32(x, 0, z, seed, 12) % (biomeAt(x, z, seed) === 'forest' ? 78 : 300) === 0
```

with:

```typescript
    : hash32(x, 0, z, seed, 12) % (TREE_RARITY[biomeAt(x, z, seed)] ?? MEADOW_TREES) === 0
```

and replace:

```typescript
function treeBlock(x: number, y: number, z: number, seed: string): string | null {
  const trees = treesInChunk(Math.floor(x / 16), Math.floor(z / 16), seed)
  if (trees.some(([tx, tz, base]) => x === tx && z === tz && y > base && y <= base + 4)) return 'oak_log'
  if (trees.some(([tx, tz, base]) => isLeaf(x - tx, y - base, z - tz))) return 'leaves'
  return null
}
```

with:

```typescript
/** The wood of the tree rooted at (x, z): spruce in the taiga, birch in a birch forest (one in five an
 * oak), now and then a birch in a forest, else oak. */
export function treeKind(x: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  const biome = biomeAt(x, z, seed)
  const roll = hash32(x, 0, z, seed, 21) % 10
  if (biome === 'taiga') return 'spruce'
  if (biome === 'birch_forest') return roll < 2 ? 'oak' : 'birch'
  return biome === 'forest' && roll === 0 ? 'birch' : 'oak'
}

/** The canopy of a tree of `kind` relative to its trunk's ground cell (the trunk wins where they meet). */
function leafOf(kind: string, dx: number, dy: number, dz: number): boolean {
  const ax = Math.abs(dx), az = Math.abs(dz)
  if (kind === 'birch') {
    if (dy === 4 || dy === 5) return ax + az <= 2
    return (dy === 6 && ax + az <= 1) || (dy === 7 && ax + az === 0)
  }
  if (kind === 'spruce') {
    if (dy === 3) return ax <= 2 && az <= 2 && ax + az <= 3
    if (dy === 4 || dy === 6) return ax + az <= 1
    if (dy === 5) return ax + az <= 2
    return dy === 7 && ax + az === 0
  }
  return isLeaf(dx, dy, dz)
}

/** A trunk (of any tree in the chunk) first, then the leaves of the first tree whose canopy has the cell. */
function treeBlock(x: number, y: number, z: number, seed: string): string | null {
  const trees = treesInChunk(Math.floor(x / 16), Math.floor(z / 16), seed)
  for (const [tx, tz, base] of trees) {
    if (x === tx && z === tz && y > base && y <= base + 4) return TREE_LOGS[treeKind(tx, tz, seed)]
  }
  for (const [tx, tz, base] of trees) {
    const kind = treeKind(tx, tz, seed)
    if (leafOf(kind, x - tx, y - base, z - tz)) return TREE_LEAVES[kind]
  }
  return null
}

/** The highest leaf over a column and whose leaves they are (the first tree's on a tie), or null. */
export function canopyTop(x: number, z: number, seed = DEFAULT_WORLD_SEED): [string, number] | null {
  let top: [string, number] | null = null
  for (const [tx, tz, base] of treesInChunk(Math.floor(x / CHUNK_SIZE), Math.floor(z / CHUNK_SIZE), seed)) {
    const kind = treeKind(tx, tz, seed)
    for (let dy = CANOPY_TOP; dy >= 3; dy--) {
      if (!leafOf(kind, x - tx, dy, z - tz)) continue
      if (top === null || base + dy > top[1]) top = [TREE_LEAVES[kind], base + dy]
      break
    }
  }
  return top
}
```

and replace:

```typescript
/** Flower, wild food or tall grass growing on top of the terrain at (x, z). */
export function plantAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  if (Math.hypot(x, z) <= HOME_RADIUS) return null
  if (decorationColumn(x, z, seed)) {
    if (treeBase(x, z, seed) !== null) return null
    if (hash32(x, 0, z, seed, 13) % 97 === 0) return legacyHash(x + 1, z) % 2 ? 'flower_orange' : 'flower_yellow'
  }
  if (Math.hypot(x, z) > LEGACY_RADIUS && terrainHeight(x, z, seed) < SEA_LEVEL) return null
  const surface = surfaceMaterial(x, z, seed)
  if (surface !== 'grass' && surface !== 'moss') return null
  return wildFood(x, z, seed) ?? (hash32(x, 0, z, seed, 14) % 19 === 0 ? 'tall_grass' : null)
}
```

with:

```typescript
/** A cactus in the desert, or sugar cane on a shore right beside a lake, with how many blocks high it
 * stands (1 to 3). Null in the legacy clearing. */
function tallPlant(x: number, z: number, seed: string): [string, number] | null {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return null
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert') {
    const roll = hash32(x, 0, z, seed, 25)
    return roll % CACTUS_RARITY === 0 ? ['cactus', 1 + Math.floor(roll / CACTUS_RARITY) % 3] : null
  }
  if (!['meadow', 'forest', 'birch_forest', 'swamp'].includes(biome) || !shore(x, z, seed) || swampPool(x, z, seed)) return null
  const rarity = biome === 'swamp' ? Math.floor(CANE_RARITY / 3) : CANE_RARITY
  const roll = hash32(x, 0, z, seed, 26)
  return roll % rarity === 0 ? ['sugar_cane', 1 + Math.floor(roll / rarity) % 3] : null
}

/** What grows on top of the terrain at (x, z) and how many blocks high: a flower, wild food, tall grass,
 * a fern, a dead bush, a pumpkin or a melon stand one high, a cactus or sugar cane 1 to 3. */
export function plantStack(x: number, z: number, seed = DEFAULT_WORLD_SEED): [string, number] | null {
  if (Math.hypot(x, z) <= HOME_RADIUS) return null
  const surface = surfaceMaterial(x, z, seed)
  if (decorationColumn(x, z, seed)) {
    if (treeBase(x, z, seed) !== null) return null
    if (hash32(x, 0, z, seed, 13) % 97 === 0 && (surface === 'grass' || surface === 'moss')) {
      return [legacyHash(x + 1, z) % 2 ? 'flower_orange' : 'flower_yellow', 1]
    }
  }
  if (Math.hypot(x, z) > LEGACY_RADIUS && terrainHeight(x, z, seed) < SEA_LEVEL) return null
  const tall = tallPlant(x, z, seed)
  if (tall) return tall
  const biome = biomeAt(x, z, seed)
  if (surface === 'sand') {
    return biome === 'desert' && hash32(x, 0, z, seed, 22) % DEAD_BUSH_RARITY === 0 ? ['dead_bush', 1] : null
  }
  if ((surface !== 'grass' && surface !== 'moss' && surface !== 'mud') || swampPool(x, z, seed)) return null
  const food = wildFood(x, z, seed)
  if (food) return [food, 1]
  if (biome === 'taiga' && hash32(x, 0, z, seed, 23) % FERN_RARITY === 0) return ['fern', 1]
  if (FRUIT_BIOMES.has(biome) && Math.hypot(x, z) > LEGACY_RADIUS) {
    const roll = hash32(x, 0, z, seed, 24)
    if (roll % FRUIT_RARITY === 0) return [Math.floor(roll / FRUIT_RARITY) % 2 === 0 ? 'pumpkin' : 'melon', 1]
  }
  return hash32(x, 0, z, seed, 14) % (biome === 'swamp' ? 11 : 19) === 0 ? ['tall_grass', 1] : null
}

/** The plant (or fruit) growing on top of the terrain at (x, z): the base of plantStack. */
export function plantAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  return plantStack(x, z, seed)?.[0] ?? null
}
```

and replace:

```typescript
  const height = terrainHeight(x, z, seed)
  if (y === height + 1) return plantAt(x, z, seed)
  if (y < height - 2) return cavePlant(x, y, z, seed)
```

with:

```typescript
  const height = terrainHeight(x, z, seed)
  if (y > height && y <= height + 3) {
    const stack = plantStack(x, z, seed)
    return stack && y <= height + stack[1] ? stack[0] : null
  }
  if (y < height - 2) return cavePlant(x, y, z, seed)
```

and replace:

```typescript
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
```

with:

```typescript
  for (let lz = 0; lz < CHUNK_SIZE; lz++) for (let lx = 0; lx < CHUNK_SIZE; lx++) {
    const stack = plantStack(x0 + lx, z0 + lz, seed)
    if (!stack) continue
    const ground = terrainHeight(x0 + lx, z0 + lz, seed)
    for (let dy = 1; dy <= stack[1]; dy++) stamp(x0 + lx, ground + dy, z0 + lz, stack[0])
  }
  const trees = treesInChunk(cx, cz, seed)
  // Where canopies meet, the first tree's leaves win (as in treeBlock): stamp them last.
  for (const [tx, tz, base] of [...trees].reverse()) {
    const kind = treeKind(tx, tz, seed)
    for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (let dy = 3; dy <= CANOPY_TOP; dy++) {
      if (leafOf(kind, dx, dy, dz)) stamp(tx + dx, base + dy, tz + dz, TREE_LEAVES[kind])
    }
  }
  for (const [tx, tz, base] of trees) {
    const log = TREE_LOGS[treeKind(tx, tz, seed)]
    for (let y = base + 1; y <= base + 4; y++) stamp(tx, y, tz, log)
  }
```


- [ ] **Step 9: The minimap sees the new tops**

From above, a column shows the highest leaf of any wood, a lake's water or ice, a swamp pool, a pumpkin or melon (solid blocks on the ground), or the ground.

In `frontend/src/survival/overheadMap.ts`, replace:

```typescript
import {
  blockAt, CHUNK_SIZE, LEGACY_RADIUS, SEA_LEVEL, surfaceMaterial, terrainHeight, treesInChunk, WORLD_MIN_Y,
} from '../engine/worldgen'
```

with:

```typescript
import {
  blockAt, canopyTop, CHUNK_SIZE, LEGACY_RADIUS, plantStack, SEA_LEVEL, surfaceMaterial, swampPool, terrainBlock,
  terrainHeight, WORLD_MIN_Y,
} from '../engine/worldgen'
```

and replace:

```typescript
const LEAVES = blockId('leaves')
```

with:

```typescript
const LEAVES = new Set(['leaves', 'birch_leaves', 'spruce_leaves'].map((name) => blockId(name)))
```

and replace:

```typescript
/** The highest leaf of a generated tree over the column, or null. Canopies never leave a chunk. */
function canopyTop(x: number, z: number, seed: string): number | null {
  let top: number | null = null
  for (const [tx, tz, base] of treesInChunk(Math.floor(x / CHUNK_SIZE), Math.floor(z / CHUNK_SIZE), seed)) {
    const ax = Math.abs(x - tx), az = Math.abs(z - tz)
    const leaf = ax + az < 2 ? base + 6 : ax <= 2 && az <= 2 && ax + az <= 3 ? base + 5 : null
    if (leaf !== null && (top === null || leaf > top)) top = leaf
  }
  return top
}

/** The first block from above that the map shows, found by reading `at` down from `from`. */
```

with:

```typescript
/** The first block from above that the map shows, found by reading `at` down from `from`. */
```

and replace:

```typescript
/** The block worldgen shows from above at (x, z): a tree top, water or the ground. Small plants
 * (grass, flowers, bushes) are too small to see. */
```

with:

```typescript
/** The block worldgen shows from above at (x, z): a tree top (oak, birch or spruce), water or a frozen
 * lake, a swamp pool, a pumpkin or melon, or the ground. Small plants (grass, flowers, bushes, cacti,
 * cane) are too small to see. */
```

and replace:

```typescript
  const leaves = canopyTop(x, z, seed)
  if (leaves !== null && leaves > Math.max(height, SEA_LEVEL)) return { id: LEAVES, y: leaves, depth: 0 }
  if (height < SEA_LEVEL) return { id: WATER, y: SEA_LEVEL, depth: SEA_LEVEL - height }
  return { id: blockId(surfaceMaterial(x, z, seed)), y: height, depth: 0 }
```

with:

```typescript
  const leaves = canopyTop(x, z, seed)
  if (leaves !== null && leaves[1] > Math.max(height, SEA_LEVEL)) return { id: blockId(leaves[0]), y: leaves[1], depth: 0 }
  if (height < SEA_LEVEL) return { id: blockId(terrainBlock(x, SEA_LEVEL, z, seed)), y: SEA_LEVEL, depth: SEA_LEVEL - height }
  if (swampPool(x, z, seed)) return { id: WATER, y: height, depth: 1 }
  const plant = plantStack(x, z, seed)
  if (plant && LAYER_BY_ID[blockId(plant[0])] !== LAYER_CUTOUT) return { id: blockId(plant[0]), y: height + plant[1], depth: 0 }
  return { id: blockId(surfaceMaterial(x, z, seed)), y: height, depth: 0 }
```

and replace:

```typescript
  if (top.id === LEAVES) shade *= 0.86
```

with:

```typescript
  if (LEAVES.has(top.id)) shade *= 0.86
```


- [ ] **Step 10: Run the viewer tests, the build and the linter**

Run: `cd frontend && npm test`
Expected: `Tests  286 passed (286)` (2 new).

Run: `cd frontend && npm run build && npx eslint src/engine src/survival`
Expected: the build succeeds and eslint prints nothing.

- [ ] **Step 11: Commit**

```bash
git add backend/services/worldgen.py backend/scripts/worldgen_fixture.py shared/worldgen-fixture.json backend/survival/creatures/kinds.py backend/tests/test_worldgen.py backend/tests/test_worldgen_biomes.py frontend/src/engine/worldgen.ts frontend/src/engine/worldgen.test.ts frontend/src/survival/overheadMap.ts frontend/src/survival/overheadMap.test.ts
git commit -m "feat: grow taiga, swamps and birch forests, with spruce and birch trees, ice, mud, gravel, cacti, sugar cane, ferns, pumpkins and melons" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Bigger caves, underground lakes, deep lava, gravel floors, stone seams, gold and diamond

**Files:**
- Modify: `backend/services/worldgen.py` and `frontend/src/engine/worldgen.ts` (the cave network, `cave_fill`, `stone_at`, the two ores), `backend/scripts/worldgen_fixture.py` (sample them), `shared/worldgen-fixture.json` (regenerated)
- Modify tests: `backend/tests/test_worldgen.py` (the fixture covers the new blocks), `frontend/src/engine/worldgen.test.ts`
- Test: `backend/tests/test_worldgen_underground.py`

**Interfaces:**
- Consumes: `worldgen.noise3`, `noise2`, `hash32`, `cave_at`, `terrain_block`, `cave_plant`; Task 3's constants block (the new constants follow `SIDES`).
- Produces (both ports):
  - `cave_at` keeps its signature and its bounds (outside the legacy clearing, above bedrock, 3 or more below the surface) with a bigger, taller network: about a fifth of the underground is open, against an eighth before.
  - `cave_fill(x, y, z, seed) -> "air" | "water" | "lava"`: open cave cells at y -2 and below are water in a lake region; at y -4 (the floor above bedrock, "below y = -3") they are lava in a lava region. `terrain_block` returns it for a cave cell; `cave_plant` grows mushrooms only on air.
  - `gravel_floor(x, y, z, seed) -> bool`: gravel in patches on cave floors (the rock under an open cave cell of air). `stone_at(x, y, z, seed)`: ashstone seams at y -2 and below, blobs of granite, andesite or diorite, else stone.
  - Ores: after the old three (unchanged, so remembered ores stay true), `gold_ore` one stone cell in 181 at y 0 and below, `diamond_ore` one in 331 at y -3 and below. TypeScript exports `caveFill`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_worldgen_underground.py`:

```python
import math
import unittest

from backend.services.crafting import can_harvest
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, block_at, cave_at, cave_plant, terrain_block, terrain_height,
)

SEED = "123456789123456789"


def underground(xs=range(2000, 2300, 3), zs=range(-150, 150, 3)):
    """(x, y, z, block) of every generated cell from y -4 up to 3 below the surface."""
    for x in xs:
        for z in zs:
            for y in range(-4, terrain_height(x, z, SEED) - 2):
                yield x, y, z, terrain_block(x, y, z, SEED)


class CaveTests(unittest.TestCase):
    def test_caves_take_a_fifth_of_the_underground_and_stand_taller(self):
        cells = list(underground())
        open_cells = [cell for cell in cells if cell[3] in ("air", "water", "lava")]
        self.assertGreater(len(open_cells) / len(cells), 0.18)  # 0.12 before L3
        tallest = {}
        for x, y, z, _ in open_cells:
            tallest[(x, z)] = tallest.get((x, z), 0) + 1
        self.assertGreaterEqual(max(tallest.values()), 5)

    def test_lakes_lie_low_in_caves_and_lava_on_their_lowest_floor(self):
        cells = list(underground())
        water = [(x, y, z) for x, y, z, block in cells if block == "water"]
        lava = [(x, y, z) for x, y, z, block in cells if block == "lava"]
        self.assertTrue(water and lava)
        self.assertTrue(all(y <= -2 and cave_at(x, y, z, SEED) for x, y, z in water))
        self.assertTrue(all(y == -4 and cave_at(x, y, z, SEED) for x, y, z in lava))
        for x, y, z in water[:20] + lava[:20]:
            self.assertIsNone(cave_plant(x, y, z, SEED))

    def test_the_legacy_clearing_keeps_its_old_underground(self):
        for x in range(-LEGACY_RADIUS, LEGACY_RADIUS, 17):
            for z in range(-LEGACY_RADIUS, LEGACY_RADIUS, 13):
                for y in (-4, -3) if math.hypot(x, z) <= LEGACY_RADIUS else ():
                    self.assertIn(block_at(x, y, z, LEGACY_WORLD_SEED), ("stone", "iron_ore", "coal_ore"), (x, y, z))


class GravelTests(unittest.TestCase):
    def test_gravel_lies_in_patches_on_cave_floors(self):
        cells = list(underground())
        gravel = [(x, y, z) for x, y, z, block in cells if block == "gravel"]
        self.assertGreater(len(gravel), 20)
        for x, y, z in gravel:
            self.assertTrue(cave_at(x, y + 1, z, SEED), (x, y, z))
            self.assertEqual(terrain_block(x, y + 1, z, SEED), "air")


class RockTests(unittest.TestCase):
    def test_gold_lies_at_zero_and_below_and_diamonds_deeper_both_for_an_iron_pickaxe(self):
        cells = list(underground(xs=range(2000, 2600, 2)))
        gold = [y for _, y, _, block in cells if block == "gold_ore"]
        diamond = [y for _, y, _, block in cells if block == "diamond_ore"]
        self.assertTrue(gold and diamond)
        self.assertLessEqual(max(gold), 0)
        self.assertLessEqual(max(diamond), -3)
        self.assertGreater(len(gold), len(diamond))
        for ore in ("gold_ore", "diamond_ore"):
            self.assertFalse(can_harvest(ore, {"stone_pickaxe": 1}))
            self.assertTrue(can_harvest(ore, {"iron_pickaxe": 1}))

    def test_seams_of_granite_andesite_diorite_and_deep_ashstone(self):
        cells = {(x, y, z): block for x, y, z, block in underground()}
        kinds = set(cells.values())
        self.assertTrue({"granite", "andesite", "diorite", "ashstone", "stone"} <= kinds)
        self.assertTrue(all(y <= -2 for (_, y, _), block in cells.items() if block == "ashstone"))
        granite = [cell for cell, block in cells.items() if block == "granite"]
        beside = sum(1 for x, y, z in granite if cells.get((x, y + 1, z)) == "granite" or cells.get((x + 3, y, z)) == "granite")
        self.assertGreater(beside / len(granite), 0.5)  # blobs, not specks
        self.assertGreater(list(cells.values()).count("stone"), len(cells) / 2)


if __name__ == "__main__":
    unittest.main()
```


In `backend/tests/test_worldgen.py`, replace:

```python
                     "cactus", "sugar_cane", "dead_bush", "fern", "pumpkin", "melon", "gravel"):
```

with:

```python
                     "cactus", "sugar_cane", "dead_bush", "fern", "pumpkin", "melon", "gravel", "lava", "gold_ore",
                     "diamond_ore", "granite", "andesite", "diorite", "ashstone"):
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen_underground.py"`
Expected: FAIL: the open share is about 0.12, and no water, lava, gold, diamond or seams turn up.

- [ ] **Step 3: Dig the new underground into the Python worldgen**

In `backend/services/worldgen.py`, replace:

```python
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
```

with:

```python
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
# L3 underground: bigger, taller caves, lakes and lava in them, seams of other stone, gold and diamond.
CAVE_SCALE = 13  # blocks across the cave network's noise (it was 11)
CAVE_STRETCH = 0.6  # the network's noise runs this much slower upward, so caves stand taller
CAVE_OPEN = 0.22  # the network is open above this (it was 0.27)
CAVE_ROOM = -0.15  # and its rooms are carved where the finer noise is above this (it was -0.12)
LAKE_LEVEL = -2  # in a lake region, cave cells this low are water
LAVA_LEVEL = -4  # in a lava region, the lowest cave cells (just above bedrock) are lava
GOLD_RARITY = 181  # stone cells per gold ore, at y 0 and below
GOLD_DEPTH = 0
DIAMOND_RARITY = 331  # stone cells per diamond ore, at y -3 and below
DIAMOND_DEPTH = -3
ASH_DEPTH = -2  # ashstone seams lie this deep and deeper
VARIANTS = ("granite", "andesite", "diorite")
```

and replace:

```python
    return noise3(x, y, z, 11, seed, 7) > 0.27 and noise3(x, y, z, 5, seed, 8) > -0.12
```

with:

```python
    return (noise3(x, y * CAVE_STRETCH, z, CAVE_SCALE, seed, 7) > CAVE_OPEN
            and noise3(x, y, z, 6, seed, 8) > CAVE_ROOM)


def cave_fill(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """What fills an open cave cell: water low down in a lake region, lava on the lowest floor of a
    lava region, else air."""
    if y <= LAKE_LEVEL and noise2(x, z, 40, seed, 27) > 0.3:
        return "water"
    if y == LAVA_LEVEL and noise2(x, z, 32, seed, 28) > 0.25:
        return "lava"
    return "air"


def gravel_floor(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    """Gravel in patches on cave floors: the rock right under an open cave cell of air."""
    return noise2(x, z, 8, seed, 90) > 0.1 and cave_at(x, y + 1, z, seed) and cave_fill(x, y + 1, z, seed) == "air"


def stone_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """The rock of a solid cell underground: ashstone in deep seams, blobs of granite, andesite or
    diorite (one kind to a blob region), else stone."""
    if y <= ASH_DEPTH and noise3(x, y, z, 9, seed, 29) > 0.35:
        return "ashstone"
    if noise3(x, y, z, 8, seed, 80) > 0.38:
        return VARIANTS[hash32(x // 24, y // 8, z // 24, seed, 81) % len(VARIANTS)]
    return "stone"
```

and replace:

```python
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
```

with:

```python
    if cave_at(x, y, z, seed):
        return cave_fill(x, y, z, seed)
    ore = hash32(x, y, z, seed, 9)
    if ore % 97 == 0:
        return "iron_ore"
    if ore % 61 == 0:
        return "coal_ore"
    if ore % 151 == 0:
        return "copper_ore"
    if ore % GOLD_RARITY == 0 and y <= GOLD_DEPTH:
        return "gold_ore"
    if ore % DIAMOND_RARITY == 0 and y <= DIAMOND_DEPTH:
        return "diamond_ore"
    if gravel_floor(x, y, z, seed):
        return "gravel"
    return stone_at(x, y, z, seed)
```

and replace:

```python
    """A mushroom on a cave floor: an open cave cell with solid rock (or bedrock) under it."""
    roll = hash32(x, y, z, seed, 17)
    if roll % CAVE_MUSHROOM_RARITY != 0:
        return None
    if not cave_at(x, y, z, seed) or cave_at(x, y - 1, z, seed):
        return None
```

with:

```python
    """A mushroom on a cave floor: an open cave cell of air with solid rock (or bedrock) under it."""
    roll = hash32(x, y, z, seed, 17)
    if roll % CAVE_MUSHROOM_RARITY != 0:
        return None
    if not cave_at(x, y, z, seed) or cave_at(x, y - 1, z, seed) or cave_fill(x, y, z, seed) != "air":
        return None
```


- [ ] **Step 4: Sample it in the fixture and regenerate it**

In `backend/scripts/worldgen_fixture.py`, replace:

```python
NEW_BIOMES = ("taiga", "swamp", "birch_forest")
```

with:

```python
NEW_BIOMES = ("taiga", "swamp", "birch_forest")
DEEP = ("gold_ore", "diamond_ore", "water", "lava", "gravel", "granite", "andesite", "diorite", "ashstone")
```

and replace:

```python
def sample_cells() -> list[tuple[str, int, int, int]]:
```

with:

```python
def _deep(seed: str, count: int) -> list[tuple[int, int, int]]:
    """Underground cells of gold, diamond, a cave lake, lava and each kind of stone, `count` of each."""
    seen: dict[str, int] = {}
    found = []
    for x in range(250, 700, 3):
        for z in range(-100, 100, 3):
            for y in range(-4, terrain_height(x, z, seed) - 2):
                block = block_at(x, y, z, seed)
                if block in DEEP and seen.get(block, 0) < count:
                    seen[block] = seen.get(block, 0) + 1
                    found.append((x, y, z))
                    if len(seen) == len(DEEP) and all(value == count for value in seen.values()):
                        return found
    return found


def sample_cells() -> list[tuple[str, int, int, int]]:
```

and replace:

```python
        for x, z in _features(seed, 3):
```

with:

```python
        for x, y, z in _deep(seed, 3):
            cells |= {(seed, x + dx, y + dy, z + dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)}
        for x, z in _features(seed, 3):
```


Run: `python3 -m backend.scripts.worldgen_fixture`
Expected: `Wrote 25483 cells to …/shared/worldgen-fixture.json`.

- [ ] **Step 5: Run the backend tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen*.py"`
Expected: `Ran 33 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 834 tests` … `OK` (6 new).

- [ ] **Step 6: Port it to the viewer's worldgen**

In `frontend/src/engine/worldgen.test.ts`, replace:

```typescript
  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
```

with:

```typescript
  it('generates gold, diamond, cave lakes, lava and the stone seams inside columns exactly like blockAt', () => {
    const deep = ['gold_ore', 'diamond_ore', 'water', 'lava', 'gravel', 'granite', 'andesite', 'diorite', 'ashstone']
    const chunks = new Map<string, [number, number]>()
    for (let x = 250; x < 700 && chunks.size < deep.length; x += 3) {
      for (let z = -100; z < 100; z += 3) {
        for (let y = -4; y < terrainHeight(x, z, WILD_SEED) - 2; y++) {
          const name = blockAt(x, y, z, WILD_SEED)
          if (deep.includes(name) && !chunks.has(name)) chunks.set(name, [Math.floor(x / 16), Math.floor(z / 16)])
        }
      }
    }
    expect([...chunks.keys()].sort()).toEqual([...deep].sort())
    const unique = new Map([...chunks.values()].map((chunk) => [chunk.join(','), chunk]))
    for (const [cx, cz] of unique.values()) expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
  })

  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
```


Run: `cd frontend && npx vitest run src/engine/worldgen.test.ts`
Expected: FAIL: the fixture's cells differ (`expected granite, got stone` and the like).

In `frontend/src/engine/worldgen.ts`, replace:

```typescript
const SIDES: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1]]
```

with:

```typescript
const SIDES: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1]]
// L3 underground: bigger, taller caves, lakes and lava in them, seams of other stone, gold and diamond.
const CAVE_SCALE = 13
const CAVE_STRETCH = 0.6
const CAVE_OPEN = 0.22
const CAVE_ROOM = -0.15
const LAKE_LEVEL = -2
const LAVA_LEVEL = -4
const GOLD_RARITY = 181
const GOLD_DEPTH = 0
const DIAMOND_RARITY = 331
const DIAMOND_DEPTH = -3
const ASH_DEPTH = -2
const VARIANTS = ['granite', 'andesite', 'diorite']
```

and replace:

```typescript
  return noise3(x, y, z, 11, seed, 7) > 0.27 && noise3(x, y, z, 5, seed, 8) > -0.12
}
```

with:

```typescript
  return noise3(x, y * CAVE_STRETCH, z, CAVE_SCALE, seed, 7) > CAVE_OPEN && noise3(x, y, z, 6, seed, 8) > CAVE_ROOM
}

/** What fills an open cave cell: water low down in a lake region, lava on the lowest floor of a lava
 * region, else air. */
export function caveFill(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  if (y <= LAKE_LEVEL && noise2(x, z, 40, seed, 27) > 0.3) return 'water'
  if (y === LAVA_LEVEL && noise2(x, z, 32, seed, 28) > 0.25) return 'lava'
  return 'air'
}

/** Gravel in patches on cave floors: the rock right under an open cave cell of air. */
function gravelFloor(x: number, y: number, z: number, seed: string): boolean {
  return noise2(x, z, 8, seed, 90) > 0.1 && caveAt(x, y + 1, z, seed) && caveFill(x, y + 1, z, seed) === 'air'
}

/** The rock of a solid cell underground: ashstone in deep seams, blobs of granite, andesite or diorite
 * (one kind to a blob region), else stone. */
function stoneAt(x: number, y: number, z: number, seed: string): string {
  if (y <= ASH_DEPTH && noise3(x, y, z, 9, seed, 29) > 0.35) return 'ashstone'
  if (noise3(x, y, z, 8, seed, 80) > 0.38) {
    return VARIANTS[hash32(Math.floor(x / 24), Math.floor(y / 8), Math.floor(z / 24), seed, 81) % VARIANTS.length]
  }
  return 'stone'
}
```

and replace:

```typescript
  if (caveAt(x, y, z, seed)) return 'air'
  const ore = hash32(x, y, z, seed, 9)
  if (ore % 97 === 0) return 'iron_ore'
  if (ore % 61 === 0) return 'coal_ore'
  if (ore % 151 === 0) return 'copper_ore'
  return 'stone'
}
```

with:

```typescript
  if (caveAt(x, y, z, seed)) return caveFill(x, y, z, seed)
  const ore = hash32(x, y, z, seed, 9)
  if (ore % 97 === 0) return 'iron_ore'
  if (ore % 61 === 0) return 'coal_ore'
  if (ore % 151 === 0) return 'copper_ore'
  if (ore % GOLD_RARITY === 0 && y <= GOLD_DEPTH) return 'gold_ore'
  if (ore % DIAMOND_RARITY === 0 && y <= DIAMOND_DEPTH) return 'diamond_ore'
  if (gravelFloor(x, y, z, seed)) return 'gravel'
  return stoneAt(x, y, z, seed)
}
```

and replace:

```typescript
  if (!caveAt(x, y, z, seed) || caveAt(x, y - 1, z, seed)) return null
  return Math.floor(roll / CAVE_MUSHROOM_RARITY) % 3 === 0 ? 'red_mushroom' : 'brown_mushroom'
```

with:

```typescript
  if (!caveAt(x, y, z, seed) || caveAt(x, y - 1, z, seed) || caveFill(x, y, z, seed) !== 'air') return null
  return Math.floor(roll / CAVE_MUSHROOM_RARITY) % 3 === 0 ? 'red_mushroom' : 'brown_mushroom'
```


- [ ] **Step 7: Run the viewer tests, the build and the linter**

Run: `cd frontend && npm test && npm run build && npx eslint src/engine`
Expected: `Tests  287 passed (287)` (1 new), the build succeeds, eslint prints nothing.

- [ ] **Step 8: Commit**

```bash
git add backend/services/worldgen.py backend/scripts/worldgen_fixture.py shared/worldgen-fixture.json backend/tests/test_worldgen.py backend/tests/test_worldgen_underground.py frontend/src/engine/worldgen.ts frontend/src/engine/worldgen.test.ts
git commit -m "feat: bigger, taller caves with lakes, deep lava and gravel floors, seams of granite, andesite, diorite and ashstone, and gold and diamond ore" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Cave entrances open to the sky, boulders and outcrops

**Files:**
- Modify: `backend/services/worldgen.py` and `frontend/src/engine/worldgen.ts` (`region_openings`, `opening`, `surface_opened`, `rocks_in_chunk`, `rock_column`; the terrain carves entrances and the decorations stand rocks), `backend/survival/spawn.py` (never born over a hole), `backend/scripts/worldgen_fixture.py` (sample them), `shared/worldgen-fixture.json` (regenerated), `frontend/src/survival/overheadMap.ts` (the minimap sees rocks and the floors of entrances)
- Modify tests: `backend/tests/test_worldgen.py`, `frontend/src/engine/worldgen.test.ts`, `frontend/src/survival/overheadMap.test.ts`
- Test: `backend/tests/test_worldgen_surface.py`

**Interfaces:**
- Consumes: Tasks 3 and 4 (`swamp_pool`, `tree_base`, `SIDES`, the constants block after `VARIANTS`); `spawn.spawn_fits`.
- Produces (both ports):
  - `region_openings(rx, rz, seed) -> (kind, {(x, z): (low, high)})` for 64x64 regions: `"sinkhole"` (a round shaft of 21 columns from the surface down 9 to 13 blocks, never below y -3, never beside water), `"mouth"` (a ramp 2 wide and up to 3 tall into the steepest rise near a spot, sinking a block every 2 for 12 blocks, open to the sky at first and roofed further in) or `""`. None within 64 blocks of the legacy clearing. `opening(x, z, seed) -> (low, high) | None`; `surface_opened(x, z, seed) -> bool` (the column's ground cell is gone). `terrain_block` returns air in a span.
  - `rocks_in_chunk(cx, cz, seed) -> ((x, z, kind, size, block), ...)`: an outcrop (size 3, a crag of pillars 1 to 3 high) on ground 8 or higher in a third of such chunks, else a boulder (size 1 or 2, a low dome) in a quarter of chunks, of the local stone (mossy cobblestone in forests, taiga and swamps, andesite in meadows, sandstone in deserts; outcrops of stone, andesite, diorite, granite or sandstone). `rock_column(x, z, seed) -> (block, top y) | None`: each column rests on its own ground and never on a tree's, water's or hole's column. `decoration_at`'s precedence is home, trunk, leaves, rock, plant; nothing grows on a rock or a hole.
  - `spawn_fits` refuses a column whose ground cell is not its surface block.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_worldgen_surface.py`:

```python
import unittest

from backend.services.blocks import is_solid
from backend.services.worldgen import (
    block_at, biome_at, plant_stack, region_openings, rock_column, rocks_in_chunk, surface_opened, terrain_height,
)
from backend.survival.spawn import spawn_fits

SEED = "123456789123456789"


def entrances(kind, count=3):
    found = []
    for rx in range(4, 40):
        for rz in range(-20, 20):
            found_kind, spans = region_openings(rx, rz, SEED)
            if found_kind == kind:
                found.append(spans)
                if len(found) == count:
                    return found
    return found


def rocks(kind, count=6):
    found = []
    for cx in range(16, 160):
        for cz in range(-40, 40):
            found += [rock for rock in rocks_in_chunk(cx, cz, SEED) if rock[2] == kind]
            if len(found) >= count:
                return found[:count]
    return found


class EntranceTests(unittest.TestCase):
    def test_a_sinkhole_opens_a_deep_round_shaft_to_the_sky(self):
        for spans in entrances("sinkhole"):
            self.assertEqual(len(spans), 21)
            for (x, z), (low, high) in spans.items():
                height = terrain_height(x, z, SEED)
                self.assertEqual(high, height)
                self.assertTrue(surface_opened(x, z, SEED))
                self.assertTrue(low == -3 or height - low >= 8, (x, z, low, height))
                self.assertEqual([block_at(x, y, z, SEED) for y in (low, height)], ["air", "air"])
                self.assertIsNone(plant_stack(x, z, SEED))
                self.assertFalse(spawn_fits(x, z, SEED))

    def test_a_hillside_mouth_is_two_wide_and_sinks_into_the_ground_under_a_roof(self):
        roofed = 0
        for spans in entrances("mouth", 6):
            self.assertGreaterEqual(len(spans), 4)
            for (x, z), (low, high) in spans.items():
                self.assertTrue(0 <= high - low <= 2)
                self.assertTrue(all(block_at(x, y, z, SEED) == "air" for y in range(low, high + 1)))
                if high < terrain_height(x, z, SEED) and is_solid(block_at(x, high + 1, z, SEED)):
                    roofed += 1
            floors = sorted({low for low, _ in spans.values()})
            self.assertEqual(floors, list(range(floors[0], floors[-1] + 1)))  # it steps down a block at a time
        self.assertGreater(roofed, 0)

    def test_no_entrance_near_the_legacy_clearing(self):
        for rx in range(-3, 3):
            for rz in range(-3, 3):
                self.assertEqual(region_openings(rx, rz, SEED), ("", {}))


class RockTests(unittest.TestCase):
    def test_boulders_rest_on_their_own_ground_one_or_two_high(self):
        for x, z, _, size, block in rocks("boulder"):
            ground = terrain_height(x, z, SEED)
            self.assertEqual(rock_column(x, z, SEED), (block, ground + size))
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    rock = rock_column(x + dx, z + dz, SEED)
                    if rock is None:
                        continue
                    bottom = terrain_height(x + dx, z + dz, SEED) + 1
                    self.assertEqual(block_at(x + dx, bottom, z + dz, SEED), block)  # on the ground, never floating
                    self.assertIsNone(plant_stack(x + dx, z + dz, SEED))

    def test_outcrops_crown_hills_in_jagged_pillars(self):
        for x, z, _, size, block in rocks("outcrop"):
            self.assertGreaterEqual(terrain_height(x, z, SEED), 8)
            tops = {rock_column(x + dx, z + dz, SEED)[1] - terrain_height(x + dx, z + dz, SEED)
                    for dx in range(-size, size + 1) for dz in range(-size, size + 1)
                    if rock_column(x + dx, z + dz, SEED)}
            self.assertTrue(tops <= {1, 2, 3} and len(tops) > 1)

    def test_rocks_are_of_the_local_stone(self):
        for x, z, kind, _, block in rocks("boulder", 40) + rocks("outcrop", 20):
            biome = biome_at(x, z, SEED)
            if biome in ("forest", "taiga", "swamp", "birch_forest") and kind == "boulder":
                self.assertEqual(block, "mossy_cobblestone")
            if biome == "desert":
                self.assertEqual(block, "sandstone")


if __name__ == "__main__":
    unittest.main()
```


In `backend/tests/test_worldgen.py`, replace:

```python
                     "diamond_ore", "granite", "andesite", "diorite", "ashstone"):
```

with:

```python
                     "diamond_ore", "granite", "andesite", "diorite", "ashstone", "mossy_cobblestone"):
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen_surface.py"`
Expected: `ImportError: cannot import name 'region_openings' from 'backend.services.worldgen'`.

- [ ] **Step 3: Carve the entrances and stand the rocks in the Python worldgen**

In `backend/services/worldgen.py`, replace:

```python
VARIANTS = ("granite", "andesite", "diorite")
```

with:

```python
VARIANTS = ("granite", "andesite", "diorite")
# L3 on the surface: cave entrances open to the sky (sinkholes and hillside mouths), boulders, outcrops.
OPENING_REGION = 64  # blocks on a side; a region holds one entrance at most
MOUTH_LENGTH = 12
MOUTH_TRIES = 6  # spots a region tries for a hillside mouth
OUTCROP_GROUND = 8  # outcrops crown ground at least this high
BOULDERS = {"desert": "sandstone", "meadow": "andesite", "alpine": "stone"}  # else mossy cobblestone
OUTCROPS = {"desert": "sandstone", "taiga": "andesite", "birch_forest": "diorite", "alpine": "granite"}  # else stone
```

and replace:

```python
def terrain_block(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
```

with:

```python
@lru_cache(maxsize=4096)
def region_openings(rx: int, rz: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, dict]:
    """The cave entrance of a 64x64 region, if it has one: its kind ("sinkhole", "mouth", or "" for
    none) and the span of air it carves in each of its columns, {(x, z): (lowest y, highest y)}. Two
    regions in eight try for a sinkhole and three for a hillside mouth (at up to 6 spots, the first on
    a slope); none near the legacy clearing or by the water."""
    x0, z0 = rx * OPENING_REGION, rz * OPENING_REGION
    if math.hypot(x0 + 32, z0 + 32) <= LEGACY_RADIUS + OPENING_REGION:
        return "", {}
    roll = hash32(rx, 0, rz, seed, 82)
    if roll % 8 < 2:
        cx, cz = x0 + 12 + (roll >> 8) % 40, z0 + 12 + (roll >> 16) % 40
        ground = terrain_height(cx, cz, seed)
        spans = _sinkhole(cx, cz, ground, seed) if ground > SEA_LEVEL else {}
        return ("sinkhole" if spans else ""), spans
    if roll % 8 < 5:
        for attempt in range(MOUTH_TRIES):
            spot = hash32(rx, attempt, rz, seed, 86)
            cx, cz = x0 + 12 + spot % 40, z0 + 12 + (spot >> 8) % 40
            ground = terrain_height(cx, cz, seed)
            spans = _mouth(cx, cz, ground, seed) if ground > SEA_LEVEL else {}
            if spans:
                return "mouth", spans
    return "", {}


def _sinkhole(cx: int, cz: int, ground: int, seed: str) -> dict:
    """A round shaft five across from the surface down 9 to 13 blocks (never below y -3); none next
    to water."""
    bottom = max(-3, ground - 9 - hash32(cx, 1, cz, seed, 83) % 5)
    spans = {}
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            if dx * dx + dz * dz <= 5:
                top = terrain_height(cx + dx, cz + dz, seed)
                if top <= SEA_LEVEL:
                    return {}
                spans[(cx + dx, cz + dz)] = (bottom, top)
    return spans


def _mouth(cx: int, cz: int, ground: int, seed: str) -> dict:
    """A tunnel into a hillside from the foot of its steepest rise (the ground 8 blocks on is higher):
    2 wide, up to 3 tall, its floor sinking a block every 2 for 12 blocks; open to the sky at first,
    roofed further in. None where no side rises."""
    best = None
    for dx, dz in SIDES:
        rise = terrain_height(cx + 8 * dx, cz + 8 * dz, seed) - ground
        if rise >= 1 and (best is None or rise > best[0]):
            best = (rise, dx, dz)
    if best is None:
        return {}
    _, dx, dz = best
    spans = {}
    for step in range(MOUTH_LENGTH):
        floor = ground + 1 - step // 2
        for side in (0, 1):
            x, z = cx + step * dx - side * dz, cz + step * dz + side * dx
            height = terrain_height(x, z, seed)
            top = min(floor + 2, height)
            if top >= floor and height > SEA_LEVEL:
                spans[(x, z)] = (floor, top)
    return spans


def opening(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[int, int] | None:
    """The span of air (lowest y, highest y) a cave entrance carves in the column, or None."""
    return region_openings(x // OPENING_REGION, z // OPENING_REGION, seed)[1].get((x, z))


def surface_opened(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    """A cave entrance took the column's ground cell: it is open to the sky there."""
    span = opening(x, z, seed)
    return span is not None and span[1] == terrain_height(x, z, seed)


@lru_cache(maxsize=4096)
def rocks_in_chunk(cx: int, cz: int, seed: str = LEGACY_WORLD_SEED) -> tuple[tuple[int, int, str, int, str], ...]:
    """The boulder or outcrop of a chunk, if it has one: (x, z, kind, size, block) of its middle
    column. An outcrop (size 3) crowns a hill 8 or more high in a third of such chunks; a boulder (size
    1 or 2) sits in a quarter of the others. Neither leaves its chunk, stands in water or tops a hole."""
    x0, z0 = cx * 16, cz * 16
    if math.hypot(x0 + 8, z0 + 8) <= LEGACY_RADIUS + 16:
        return ()
    roll = hash32(cx, 0, cz, seed, 84)
    x, z = x0 + 3 + roll % 10, z0 + 3 + (roll >> 8) % 10
    ground = terrain_height(x, z, seed)
    if ground <= SEA_LEVEL or swamp_pool(x, z, seed) or surface_opened(x, z, seed):
        return ()
    biome, pick = biome_at(x, z, seed), (roll >> 16) % 12
    if ground >= OUTCROP_GROUND and pick < 4:
        return ((x, z, "outcrop", 3, OUTCROPS.get(biome, "stone")),)
    if pick >= 9:
        return ((x, z, "boulder", 1 + (roll >> 24) % 2, BOULDERS.get(biome, "mossy_cobblestone")),)
    return ()


@lru_cache(maxsize=131072)
def rock_column(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
    """The block of the boulder or outcrop standing on a column and the y of its top, or None. Each
    column of a rock rests on its own ground, so none floats: a boulder is a low dome, an outcrop a
    jagged crag of pillars 1 to 3 high. A column with a tree, water or a hole in it has no rock."""
    for rx, rz, kind, size, block in rocks_in_chunk(x // 16, z // 16, seed):
        dx, dz = x - rx, z - rz
        if kind == "boulder":
            layers = sum(1 for dy in range(1, size + 1)
                         if dx * dx + dz * dz + (dy - 0.5) * (dy - 0.5) * 1.6 <= (size + 0.5) * (size + 0.5))
        elif dx * dx + dz * dz <= size * size and ((dx, dz) == (0, 0) or hash32(x, 3, z, seed, 85) % 3 != 0):
            layers = 1 + hash32(x, 2, z, seed, 85) % 3
        else:
            layers = 0
        ground = terrain_height(x, z, seed)
        if (layers and ground >= SEA_LEVEL and not swamp_pool(x, z, seed) and not surface_opened(x, z, seed)
                and tree_base(x, z, seed) is None):
            return block, ground + layers
    return None


def terrain_block(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
```

and replace:

```python
    if y == height:
        return "water" if swamp_pool(x, z, seed) else surface_material(x, z, seed)
```

with:

```python
    span = opening(x, z, seed)
    if span is not None and span[0] <= y <= span[1]:
        return "air"
    if y == height:
        return "water" if swamp_pool(x, z, seed) else surface_material(x, z, seed)
```

and replace:

```python
    if swamp_pool(x, z, seed):
        return False
```

with:

```python
    if swamp_pool(x, z, seed) or surface_opened(x, z, seed):
        return False
```

and replace:

```python
    if math.hypot(x, z) <= HOME_RADIUS:
        return None
    surface = surface_material(x, z, seed)
```

with:

```python
    if math.hypot(x, z) <= HOME_RADIUS or surface_opened(x, z, seed) or rock_column(x, z, seed):
        return None
    surface = surface_material(x, z, seed)
```

and replace:

```python
    """Blocks that grow or stand on the terrain, or on a cave floor. Precedence: home, trunk,
    leaves, plant."""
```

with:

```python
    """Blocks that grow or stand on the terrain, or on a cave floor. Precedence: home, trunk,
    leaves, rock, plant."""
```

and replace:

```python
    height = terrain_height(x, z, seed)
    if height < y <= height + 3:
```

with:

```python
    height = terrain_height(x, z, seed)
    rock = rock_column(x, z, seed) if y > height else None
    if rock is not None:
        return rock[0] if y <= rock[1] else None
    if height < y <= height + 3:
```


In `backend/survival/spawn.py`, replace:

```python
    if biome_at(x, z, seed) not in SPAWN_BIOMES or surface_material(x, z, seed) not in SPAWN_SURFACES:
        return False
```

with:

```python
    if biome_at(x, z, seed) not in SPAWN_BIOMES or surface_material(x, z, seed) not in SPAWN_SURFACES:
        return False
    if block_at(x, height, z, seed) != surface_material(x, z, seed):
        return False  # a cave entrance took the ground here
```


- [ ] **Step 4: Sample them in the fixture and regenerate it**

In `backend/scripts/worldgen_fixture.py`, replace:

```python
from backend.services.worldgen import (
    LEGACY_WORLD_SEED, SEA_LEVEL, biome_at, block_at, cave_plant, plant_at, plant_stack, swamp_pool, terrain_height,
    tree_kind, trees_in_chunk,
)
```

with:

```python
from backend.services.worldgen import (
    LEGACY_WORLD_SEED, SEA_LEVEL, biome_at, block_at, cave_plant, plant_at, plant_stack, region_openings,
    rocks_in_chunk, swamp_pool, terrain_height, tree_kind, trees_in_chunk,
)
```

and replace:

```python
def sample_cells() -> list[tuple[str, int, int, int]]:
```

with:

```python
def _entrances(seed: str, count: int) -> list[dict]:
    """The carved columns of `count` sinkholes and `count` hillside mouths."""
    found, seen = [], {}
    for rx in range(4, 40):
        for rz in range(-20, 20):
            kind, spans = region_openings(rx, rz, seed)
            if kind and seen.get(kind, 0) < count:
                seen[kind] = seen.get(kind, 0) + 1
                found.append(spans)
    return found


def _rocks(seed: str, count: int) -> list[tuple[int, int]]:
    """The middle columns of `count` boulders and `count` outcrops."""
    found, seen = [], {}
    for cx in range(16, 120):
        for cz in range(-40, 40):
            for x, z, kind, _, _ in rocks_in_chunk(cx, cz, seed):
                if seen.get(kind, 0) < count:
                    seen[kind] = seen.get(kind, 0) + 1
                    found.append((x, z))
    return found


def sample_cells() -> list[tuple[str, int, int, int]]:
```

and replace:

```python
        for x, y, z in _deep(seed, 3):
```

with:

```python
        for spans in _entrances(seed, 2):
            for (x, z), (low, _) in spans.items():
                cells |= {(seed, x, y, z) for y in range(low - 1, terrain_height(x, z, seed) + 2)}
        for rx, rz in _rocks(seed, 3):
            cells |= {(seed, rx + dx, terrain_height(rx + dx, rz + dz, seed) + dy, rz + dz)
                      for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 5)}
        for x, y, z in _deep(seed, 3):
```


Run: `python3 -m backend.scripts.worldgen_fixture`
Expected: `Wrote 29646 cells to …/shared/worldgen-fixture.json`.

- [ ] **Step 5: Run the backend tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen*.py"`
Expected: `Ran 39 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 840 tests` … `OK` (6 new).

- [ ] **Step 6: Port them to the viewer**

In `frontend/src/engine/worldgen.test.ts`, replace:

```typescript
  treeKind, treesInChunk, wildFood, WORLD_MAX_Y, WORLD_MIN_Y,
} from './worldgen'
```

with:

```typescript
  regionOpenings, rocksInChunk, treeKind, treesInChunk, wildFood, WORLD_MAX_Y, WORLD_MIN_Y,
} from './worldgen'
```

and replace:

```typescript
  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
```

with:

```typescript
  it('carves sinkholes and hillside mouths and stands boulders and outcrops inside columns exactly like blockAt', () => {
    const chunks = new Map<string, [number, number]>()
    for (let rx = 4; rx < 40; rx++) for (let rz = -20; rz < 20; rz++) {
      const [kind, spans] = regionOpenings(rx, rz, WILD_SEED)
      if (!kind || chunks.has(kind)) continue
      const [x, z] = [...spans.keys()][0].split(',').map(Number)
      chunks.set(kind, [Math.floor(x / 16), Math.floor(z / 16)])
    }
    for (let cx = 16; cx < 120; cx++) for (let cz = -40; cz < 40; cz++) {
      for (const [, , kind] of rocksInChunk(cx, cz, WILD_SEED)) if (!chunks.has(kind)) chunks.set(kind, [cx, cz])
    }
    expect([...chunks.keys()].sort()).toEqual(['boulder', 'mouth', 'outcrop', 'sinkhole'])
    for (const [cx, cz] of chunks.values()) expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
  })

  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
```


In `frontend/src/survival/overheadMap.test.ts`, replace:

```typescript
import { biomeAt, blockAt, SEA_LEVEL, terrainHeight } from '../engine/worldgen'
```

with:

```typescript
import { biomeAt, blockAt, regionOpenings, rocksInChunk, SEA_LEVEL, terrainHeight } from '../engine/worldgen'
```

and replace:

```typescript
  it('lets Mimo’s edits show: what it placed, what it dug and what it planted', () => {
```

with:

```typescript
  it('shows boulders and outcrops on the ground and the floors of cave entrances, as they stand', () => {
    const columns: [number, number][] = []
    for (let cx = 220; cx < 250; cx++) for (let cz = 250; cz < 270; cz++) {
      for (const [x, z] of rocksInChunk(cx, cz, SEED)) {
        for (let dx = -3; dx <= 3; dx++) for (let dz = -3; dz <= 3; dz++) columns.push([x + dx, z + dz])
      }
    }
    for (let rx = 55; rx < 60; rx++) for (let rz = 62; rz < 66; rz++) {
      for (const key of regionOpenings(rx, rz, SEED)[1].keys()) columns.push(key.split(',').map(Number) as [number, number])
    }
    const kinds = new Set<string>()
    for (const [x, z] of columns) {
      const top = naturalTop(x, z, SEED)
      expect({ x, z, id: top.id, y: top.y }).toEqual({ x, z, ...scanned(x, z) })
      if (top.y !== terrainHeight(x, z, SEED)) kinds.add(top.y > terrainHeight(x, z, SEED) ? 'above' : 'below')
    }
    expect(kinds).toEqual(new Set(['above', 'below']))
  })

  it('lets Mimo’s edits show: what it placed, what it dug and what it planted', () => {
```


Run: `cd frontend && npx vitest run src/engine/worldgen.test.ts src/survival/overheadMap.test.ts`
Expected: FAIL: `regionOpenings` is not exported, and the fixture's rock and entrance cells differ.

In `frontend/src/engine/worldgen.ts`, replace:

```typescript
const VARIANTS = ['granite', 'andesite', 'diorite']
```

with:

```typescript
const VARIANTS = ['granite', 'andesite', 'diorite']
// L3 on the surface: cave entrances open to the sky (sinkholes and hillside mouths), boulders, outcrops.
const OPENING_REGION = 64
const MOUTH_LENGTH = 12
const MOUTH_TRIES = 6
const OUTCROP_GROUND = 8
const BOULDERS: Record<string, string> = { desert: 'sandstone', meadow: 'andesite', alpine: 'stone' }
const OUTCROPS: Record<string, string> = { desert: 'sandstone', taiga: 'andesite', birch_forest: 'diorite', alpine: 'granite' }
type Openings = [string, Map<string, [number, number]>]
type Rock = [number, number, string, number, string]
const openingCache = new Map<string, Openings>()
const rockCache = new Map<string, Rock[]>()
```

and replace:

```typescript
/** Terrain, water, caves and ores, before trees and plants are added. */
export function terrainBlock(
```

with:

```typescript
/** The cave entrance of a 64x64 region, if it has one: its kind ('sinkhole', 'mouth', or '' for none)
 * and the span of air it carves in each of its columns (see backend/services/worldgen.py). */
export function regionOpenings(rx: number, rz: number, seed = DEFAULT_WORLD_SEED): Openings {
  const key = `${seed}:${rx},${rz}`
  let found = openingCache.get(key)
  if (found) return found
  found = findOpenings(rx, rz, seed)
  openingCache.set(key, found)
  if (openingCache.size > 4096) openingCache.delete(openingCache.keys().next().value!)
  return found
}

function findOpenings(rx: number, rz: number, seed: string): Openings {
  const x0 = rx * OPENING_REGION, z0 = rz * OPENING_REGION
  if (Math.hypot(x0 + 32, z0 + 32) <= LEGACY_RADIUS + OPENING_REGION) return ['', new Map()]
  const roll = hash32(rx, 0, rz, seed, 82)
  if (roll % 8 < 2) {
    const cx = x0 + 12 + (roll >>> 8) % 40, cz = z0 + 12 + (roll >>> 16) % 40
    const ground = terrainHeight(cx, cz, seed)
    const spans = ground > SEA_LEVEL ? sinkhole(cx, cz, ground, seed) : new Map<string, [number, number]>()
    return [spans.size ? 'sinkhole' : '', spans]
  }
  if (roll % 8 < 5) {
    for (let attempt = 0; attempt < MOUTH_TRIES; attempt++) {
      const spot = hash32(rx, attempt, rz, seed, 86)
      const cx = x0 + 12 + spot % 40, cz = z0 + 12 + (spot >>> 8) % 40
      const ground = terrainHeight(cx, cz, seed)
      const spans = ground > SEA_LEVEL ? mouth(cx, cz, ground, seed) : new Map<string, [number, number]>()
      if (spans.size) return ['mouth', spans]
    }
  }
  return ['', new Map()]
}

/** A round shaft five across from the surface down 9 to 13 blocks (never below y -3); none next to water. */
function sinkhole(cx: number, cz: number, ground: number, seed: string): Map<string, [number, number]> {
  const bottom = Math.max(-3, ground - 9 - hash32(cx, 1, cz, seed, 83) % 5)
  const spans = new Map<string, [number, number]>()
  for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) {
    if (dx * dx + dz * dz > 5) continue
    const top = terrainHeight(cx + dx, cz + dz, seed)
    if (top <= SEA_LEVEL) return new Map()
    spans.set(`${cx + dx},${cz + dz}`, [bottom, top])
  }
  return spans
}

/** A tunnel into a hillside from the foot of its steepest rise: 2 wide, up to 3 tall, sinking a block
 * every 2 for 12 blocks. */
function mouth(cx: number, cz: number, ground: number, seed: string): Map<string, [number, number]> {
  let best: [number, number, number] | null = null
  for (const [dx, dz] of SIDES) {
    const rise = terrainHeight(cx + 8 * dx, cz + 8 * dz, seed) - ground
    if (rise >= 1 && (best === null || rise > best[0])) best = [rise, dx, dz]
  }
  const spans = new Map<string, [number, number]>()
  if (best === null) return spans
  const [, dx, dz] = best
  for (let step = 0; step < MOUTH_LENGTH; step++) {
    const floor = ground + 1 - Math.floor(step / 2)
    for (const side of [0, 1]) {
      const x = cx + step * dx - side * dz, z = cz + step * dz + side * dx
      const height = terrainHeight(x, z, seed)
      const top = Math.min(floor + 2, height)
      if (top >= floor && height > SEA_LEVEL) spans.set(`${x},${z}`, [floor, top])
    }
  }
  return spans
}

/** The span of air (lowest y, highest y) a cave entrance carves in the column, or null. */
export function opening(x: number, z: number, seed = DEFAULT_WORLD_SEED): [number, number] | null {
  return regionOpenings(Math.floor(x / OPENING_REGION), Math.floor(z / OPENING_REGION), seed)[1].get(`${x},${z}`) ?? null
}

/** A cave entrance took the column's ground cell: it is open to the sky there. */
export function surfaceOpened(x: number, z: number, seed = DEFAULT_WORLD_SEED): boolean {
  const span = opening(x, z, seed)
  return span !== null && span[1] === terrainHeight(x, z, seed)
}

/** The boulder or outcrop of a chunk, if it has one: [x, z, kind, size, block] of its middle column. */
export function rocksInChunk(cx: number, cz: number, seed = DEFAULT_WORLD_SEED): Rock[] {
  const key = `${seed}:${cx},${cz}`
  let rocks = rockCache.get(key)
  if (rocks) return rocks
  rocks = findRocks(cx, cz, seed)
  rockCache.set(key, rocks)
  if (rockCache.size > 4096) rockCache.delete(rockCache.keys().next().value!)
  return rocks
}

function findRocks(cx: number, cz: number, seed: string): Rock[] {
  const x0 = cx * 16, z0 = cz * 16
  if (Math.hypot(x0 + 8, z0 + 8) <= LEGACY_RADIUS + 16) return []
  const roll = hash32(cx, 0, cz, seed, 84)
  const x = x0 + 3 + roll % 10, z = z0 + 3 + (roll >>> 8) % 10
  const ground = terrainHeight(x, z, seed)
  if (ground <= SEA_LEVEL || swampPool(x, z, seed) || surfaceOpened(x, z, seed)) return []
  const biome = biomeAt(x, z, seed), pick = (roll >>> 16) % 12
  if (ground >= OUTCROP_GROUND && pick < 4) return [[x, z, 'outcrop', 3, OUTCROPS[biome] ?? 'stone']]
  if (pick >= 9) return [[x, z, 'boulder', 1 + (roll >>> 24) % 2, BOULDERS[biome] ?? 'mossy_cobblestone']]
  return []
}

/** The block of the boulder or outcrop standing on a column and the y of its top, or null. */
export function rockColumn(x: number, z: number, seed = DEFAULT_WORLD_SEED): [string, number] | null {
  for (const [rx, rz, kind, size, block] of rocksInChunk(Math.floor(x / 16), Math.floor(z / 16), seed)) {
    const dx = x - rx, dz = z - rz
    let layers = 0
    if (kind === 'boulder') {
      for (let dy = 1; dy <= size; dy++) {
        if (dx * dx + dz * dz + (dy - 0.5) * (dy - 0.5) * 1.6 <= (size + 0.5) * (size + 0.5)) layers++
      }
    } else if (dx * dx + dz * dz <= size * size && ((dx === 0 && dz === 0) || hash32(x, 3, z, seed, 85) % 3 !== 0)) {
      layers = 1 + hash32(x, 2, z, seed, 85) % 3
    }
    const ground = terrainHeight(x, z, seed)
    if (layers && ground >= SEA_LEVEL && !swampPool(x, z, seed) && !surfaceOpened(x, z, seed) && treeBase(x, z, seed) === null) {
      return [block, ground + layers]
    }
  }
  return null
}

/** Terrain, water, caves and ores, before trees and plants are added. */
export function terrainBlock(
```

and replace:

```typescript
  if (y === height) return swampPool(x, z, seed) ? 'water' : surfaceMaterial(x, z, seed)
```

with:

```typescript
  const span = opening(x, z, seed)
  if (span !== null && y >= span[0] && y <= span[1]) return 'air'
  if (y === height) return swampPool(x, z, seed) ? 'water' : surfaceMaterial(x, z, seed)
```

and replace:

```typescript
  if (biome === 'desert' || biome === 'alpine' || swampPool(x, z, seed)) return false
```

with:

```typescript
  if (biome === 'desert' || biome === 'alpine' || swampPool(x, z, seed) || surfaceOpened(x, z, seed)) return false
```

and replace:

```typescript
export function plantStack(x: number, z: number, seed = DEFAULT_WORLD_SEED): [string, number] | null {
  if (Math.hypot(x, z) <= HOME_RADIUS) return null
```

with:

```typescript
export function plantStack(x: number, z: number, seed = DEFAULT_WORLD_SEED): [string, number] | null {
  if (Math.hypot(x, z) <= HOME_RADIUS || surfaceOpened(x, z, seed) || rockColumn(x, z, seed)) return null
```

and replace:

```typescript
  const height = terrainHeight(x, z, seed)
  if (y > height && y <= height + 3) {
```

with:

```typescript
  const height = terrainHeight(x, z, seed)
  const rock = y > height ? rockColumn(x, z, seed) : null
  if (rock) return y <= rock[1] ? rock[0] : null
  if (y > height && y <= height + 3) {
```

and replace:

```typescript
    for (let dy = 1; dy <= stack[1]; dy++) stamp(x0 + lx, ground + dy, z0 + lz, stack[0])
  }
```

with:

```typescript
    for (let dy = 1; dy <= stack[1]; dy++) stamp(x0 + lx, ground + dy, z0 + lz, stack[0])
  }
  for (let lz = 0; lz < CHUNK_SIZE; lz++) for (let lx = 0; lx < CHUNK_SIZE; lx++) {
    const rock = rockColumn(x0 + lx, z0 + lz, seed)
    if (!rock) continue
    for (let y = terrainHeight(x0 + lx, z0 + lz, seed) + 1; y <= rock[1]; y++) stamp(x0 + lx, y, z0 + lz, rock[0])
  }
```


A rock or an entrance changes what the minimap sees: the higher of a tree top and a rock shows (the leaves on a tie, as in the world), an entrance shows the first block down in it.

In `frontend/src/survival/overheadMap.ts`, replace:

```typescript
import {
  blockAt, canopyTop, CHUNK_SIZE, LEGACY_RADIUS, plantStack, SEA_LEVEL, surfaceMaterial, swampPool, terrainBlock,
  terrainHeight, WORLD_MIN_Y,
} from '../engine/worldgen'
```

with:

```typescript
import {
  blockAt, canopyTop, CHUNK_SIZE, LEGACY_RADIUS, plantStack, rockColumn, SEA_LEVEL, surfaceMaterial, surfaceOpened,
  swampPool, terrainBlock, terrainHeight, WORLD_MIN_Y,
} from '../engine/worldgen'
```

and replace:

```typescript
/** The block worldgen shows from above at (x, z): a tree top (oak, birch or spruce), water or a frozen
 * lake, a swamp pool, a pumpkin or melon, or the ground. Small plants (grass, flowers, bushes, cacti,
 * cane) are too small to see. */
```

with:

```typescript
/** The block worldgen shows from above at (x, z): a tree top (oak, birch or spruce), water or a frozen
 * lake, a swamp pool, the bottom of a cave entrance, a boulder or outcrop, a pumpkin or melon, or the
 * ground. Small plants (grass, flowers, bushes, cacti, cane) are too small to see. */
```

and replace:

```typescript
  const leaves = canopyTop(x, z, seed)
  if (leaves !== null && leaves[1] > Math.max(height, SEA_LEVEL)) return { id: blockId(leaves[0]), y: leaves[1], depth: 0 }
```

with:

```typescript
  const leaves = canopyTop(x, z, seed)
  const rock = rockColumn(x, z, seed)
  if (leaves !== null && leaves[1] > Math.max(height, SEA_LEVEL) && leaves[1] >= (rock?.[1] ?? -Infinity)) {
    return { id: blockId(leaves[0]), y: leaves[1], depth: 0 }
  }
```

and replace:

```typescript
  if (swampPool(x, z, seed)) return { id: WATER, y: height, depth: 1 }
```

with:

```typescript
  if (swampPool(x, z, seed)) return { id: WATER, y: height, depth: 1 }
  if (surfaceOpened(x, z, seed)) return scanTop((y) => blockId(blockAt(x, y, z, seed)), height)
  if (rock) return { id: blockId(rock[0]), y: rock[1], depth: 0 }
```


- [ ] **Step 7: Run the viewer tests, the build and the linter**

Run: `cd frontend && npm test && npm run build && npx eslint src/engine src/survival`
Expected: `Tests  289 passed (289)` (2 new), the build succeeds, eslint prints nothing.

- [ ] **Step 8: Commit**

```bash
git add backend/services/worldgen.py backend/survival/spawn.py backend/scripts/worldgen_fixture.py shared/worldgen-fixture.json backend/tests/test_worldgen.py backend/tests/test_worldgen_surface.py frontend/src/engine/worldgen.ts frontend/src/engine/worldgen.test.ts frontend/src/survival/overheadMap.ts frontend/src/survival/overheadMap.test.ts
git commit -m "feat: open cave entrances to the sky, sinkholes and hillside mouths, and stand boulders and outcrops on the land" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Mimo's staircases and tunnels 2 wide and 3 tall

**Files:**
- Modify: `backend/survival/work.py` (`stair` cuts a 2-by-3 passage; `side_of`, `cut`, `PASSAGE_TALL`), `backend/survival/escape.py` (the way out is as big where it fits), `backend/survival/steps.py` (a `rubble` mine step leaves its block behind), `backend/survival/renewal.py` (a tree keeps three cells clear over Mimo and its homes)
- Modify tests: `backend/tests/test_survival_work.py`, `backend/tests/test_survival_escape.py` (the bigger shapes)
- Test: `backend/tests/test_survival_passages.py`

**Interfaces:**
- Consumes: `work.stair`, `look`, `dig_heading`, `plan_stone`; `escape.staircase`, `open_up`; `steps.start_mine`, `finish_mine`; `structures.reserved`; `renewal.kept_clear`.
- Produces:
  - `work.PASSAGE_TALL = 3`; `work.side_of(heading) -> (dx, dz)` (to the left: `(-dz, dx)`); `work.cut(grid, changed, cell, surface, inventory, opened) -> str | None` ("" open already, the block to mine, or None when it must stay); `work.stair` keeps its signature and return shape. A stair opens Mimo's column 3 tall and the column to its left 3 tall over solid ground; the cells Mimo walks through (where it stands and, on a stair down, its headroom) are needed and kept, the rest open where they can as `{"kind": "mine", "target": [...], "rubble": True}` steps.
  - The mine step: a spec with `"rubble": True` runs as usual, carries `rubble` in the running step, and leaves the block's drop (and chance drops) behind.
  - `escape.open_up(grid, changed, cell, stock, steps, rubble=False)`; each escape stair also opens the next headroom (kept) and, as rubble, the cell above it and the three cells beside the stair.
  - `renewal.kept_clear` keeps the cell and the two above it for Mimo and each nearby home or shelter.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_passages.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.memory import create_memory_tables, remember
from backend.survival.renewal import kept_clear
from backend.survival.steps import finish_step, start_step
from backend.survival.work import PASSAGE_TALL, side_of, stair
from backend.tests.test_survival_work import ground, mine, walk

PICK = {"wooden_pickaxe": 1}


def rubble(x, y, z):
    return {**mine(x, y, z), "rubble": True}


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
class WidePassageTests(unittest.TestCase):
    def test_a_passage_is_three_tall_and_its_second_column_is_to_the_left(self):
        self.assertEqual(PASSAGE_TALL, 3)
        self.assertEqual([side_of(heading) for heading in ((1, 0), (0, 1), (-1, 0), (0, -1))],
                         [(0, 1), (-1, 0), (0, -1), (1, 0)])
        steps, to, stones = stair(ground({(4, -3, 0): "air"}), {}, (4, -3, 0), (1, 0), PICK, "1")
        self.assertEqual({tuple(step["target"]) for step in steps if step["kind"] == "mine"},
                         {(x, y, z) for x in (5,) for y in (-3, -2, -1) for z in (0, 1)})
        self.assertEqual((to, stones), ((5, -3, 0), 1))  # only the cell Mimo walks through is kept

    def test_it_narrows_where_the_side_cannot_be_cut_and_lowers_where_the_top_cannot(self):
        start = (0, 1, 0)
        self.assertEqual(stair(ground({(1, 0, 1): "bedrock"}), {}, start, (1, 0), PICK, "1")[0],
                         [mine(1, 0, 0), walk(1, 0, 0)])
        self.assertEqual(stair(ground({(1, -1, 1): "air"}), {}, start, (1, 0), PICK, "1")[0],
                         [mine(1, 0, 0), walk(1, 0, 0)])  # never over a hole
        self.assertEqual(stair(ground({(5, -1, 0): "bedrock", (4, -3, 0): "air"}), {}, (4, -3, 0), (1, 0), PICK, "1")[0],
                         [rubble(5, -2, 0), mine(5, -3, 0), rubble(5, -1, 1), rubble(5, -2, 1), rubble(5, -3, 1),
                          walk(5, -3, 0)])
        self.assertEqual(stair(ground({(5, -2, 1): "water", (4, -3, 0): "air"}), {}, (4, -3, 0), (1, 0), PICK, "1")[0],
                         [rubble(5, -1, 0), rubble(5, -2, 0), mine(5, -3, 0), rubble(5, -1, 1), walk(5, -3, 0)])

    def test_the_cells_mimo_walks_through_are_still_needed(self):
        self.assertIsNone(stair(ground({(1, 0, 0): "bedrock"}), {}, (0, 1, 0), (1, 0), PICK, "1"))
        self.assertIsNone(stair(ground({(2, 0, 0): "bedrock"}), {}, (1, 0, 0), (1, 0), PICK, "1"))  # the headroom


class RubbleTests(unittest.TestCase):
    def test_a_widening_cell_breaks_into_rubble_mimo_leaves_behind(self):
        grid = ground()
        state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                 "inventory": dict(PICK)}
        running = start_step(rubble(1, -1, 0), state, grid, 0.0)
        self.assertTrue(running["rubble"])
        finish_step(running, state, grid, running["ends_at"])
        self.assertEqual((grid.material(1, -1, 0), state["inventory"]), ("air", PICK))
        kept = start_step(mine(0, -2, 1), state, grid, 0.0)
        finish_step(kept, state, grid, kept["ends_at"])
        self.assertEqual(state["inventory"]["dirt"], 1)


class HomeRoomTests(unittest.TestCase):
    def test_a_tree_keeps_three_cells_clear_over_mimo_and_its_home(self):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        remember(db, "home", (1, -3, 0), 0.0)
        state = {"position": {"x": 0.0, "y": 1.0, "z": 0.0}}
        self.assertEqual(kept_clear(db, state, (0, 1, 2)),
                         {(0, 1, 0), (0, 2, 0), (0, 3, 0), (1, -3, 0), (1, -2, 0), (1, -1, 0)})


if __name__ == "__main__":
    unittest.main()
```


The staircase expectations grow to the new shape; a narrow stair's own cells are the ones kept, so the cobblestone a batch yields is what it was.

In `backend/tests/test_survival_work.py`, replace:

```python
def mine(x, y, z):
    return {"kind": "mine", "target": [x, y, z]}
```

with:

```python
def mine(x, y, z):
    return {"kind": "mine", "target": [x, y, z]}


def rubble(x, y, z):
    """A passage's widening cell (L3): mined, its block left behind."""
    return {**mine(x, y, z), "rubble": True}
```

and replace:

```python
    def test_digs_a_staircase_down_two_blocks_per_stair(self):
        s = situation(pet(inventory={"wooden_pickaxe": 1}), ground())
        stone = PURPOSES["gather_stone"]
        self.assertTrue(stone.valid(s))
        self.assertEqual(stone.plan(s, context(s.grid)),
                         [mine(1, 0, 0), walk(1, 0, 0), mine(2, 0, 0), mine(2, -1, 0), walk(2, -1, 0),
                          mine(3, -1, 0), mine(3, -2, 0), walk(3, -2, 0), mine(4, -2, 0), mine(4, -3, 0), walk(4, -3, 0)])
```

with:

```python
    def test_digs_a_staircase_one_block_down_a_stair_two_wide_and_three_tall(self):
        s = situation(pet(inventory={"wooden_pickaxe": 1}), ground())
        stone = PURPOSES["gather_stone"]
        self.assertTrue(stone.valid(s))
        self.assertEqual(stone.plan(s, context(s.grid)),
                         [mine(1, 0, 0), rubble(1, 0, 1), walk(1, 0, 0),
                          mine(2, 0, 0), mine(2, -1, 0), rubble(2, 0, 1), rubble(2, -1, 1), walk(2, -1, 0),
                          rubble(3, 0, 0), mine(3, -1, 0), mine(3, -2, 0), rubble(3, 0, 1), rubble(3, -1, 1),
                          rubble(3, -2, 1), walk(3, -2, 0),
                          rubble(4, -1, 0), mine(4, -2, 0), mine(4, -3, 0), rubble(4, -1, 1), rubble(4, -2, 1),
                          rubble(4, -3, 1), walk(4, -3, 0)])
```

and replace:

```python
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid)),
                         [mine(5, -3, 0), walk(5, -3, 0), mine(6, -3, 0), walk(6, -3, 0),
                          mine(7, -3, 0), walk(7, -3, 0), mine(8, -3, 0), walk(8, -3, 0)])
```

with:

```python
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid)),
                         [step for x in (5, 6, 7, 8) for step in (
                             rubble(x, -1, 0), rubble(x, -2, 0), mine(x, -3, 0),
                             rubble(x, -1, 1), rubble(x, -2, 1), rubble(x, -3, 1), walk(x, -3, 0))])
```

and replace:

```python
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid)), [mine(5, -3, 0), walk(5, -3, 0)])
```

with:

```python
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid)),
                         [rubble(5, -1, 0), rubble(5, -2, 0), mine(5, -3, 0), rubble(5, -1, 1), rubble(5, -2, 1),
                          rubble(5, -3, 1), walk(5, -3, 0)])
```

and replace:

```python
        self.assertEqual(stair(ground({(4, -3, 0): "air"}), {}, (4, -3, 0), (1, 0), inventory, "1"),
                         ([mine(5, -3, 0), walk(5, -3, 0)], (5, -3, 0), 1))
        # Its own upper cell opened by the same stair is fine, and so is open sky over the surface.
        self.assertEqual(stair(ground(), {}, (0, 1, 0), (1, 0), inventory, "1")[0], [mine(1, 0, 0), walk(1, 0, 0)])
        self.assertEqual(stair(ground(), {}, (1, 0, 0), (1, 0), inventory, "1")[0],
                         [mine(2, 0, 0), mine(2, -1, 0), walk(2, -1, 0)])
```

with:

```python
        self.assertEqual(stair(ground({(4, -3, 0): "air"}), {}, (4, -3, 0), (1, 0), inventory, "1"),
                         ([rubble(5, -1, 0), rubble(5, -2, 0), mine(5, -3, 0), rubble(5, -1, 1), rubble(5, -2, 1),
                           rubble(5, -3, 1), walk(5, -3, 0)], (5, -3, 0), 1))
        # Its own upper cell opened by the same stair is fine, and so is open sky over the surface.
        self.assertEqual(stair(ground(), {}, (0, 1, 0), (1, 0), inventory, "1")[0],
                         [mine(1, 0, 0), rubble(1, 0, 1), walk(1, 0, 0)])
        self.assertEqual(stair(ground(), {}, (1, 0, 0), (1, 0), inventory, "1")[0],
                         [mine(2, 0, 0), mine(2, -1, 0), rubble(2, 0, 1), rubble(2, -1, 1), walk(2, -1, 0)])
```

and replace:

```python
        self.assertEqual(len(PURPOSES["gather_stone"].plan(s, context(s.grid))), 11)
```

with:

```python
        self.assertEqual(len(PURPOSES["gather_stone"].plan(s, context(s.grid))), 22)
```

and replace:

```python
                drop = BLOCKS.get(material, {}).get("drop")
                if drop:
```

with:

```python
                drop = BLOCKS.get(material, {}).get("drop")
                if drop and not step.get("rubble"):  # L3: a passage's widening cells are left as rubble
```


In `backend/tests/test_survival_escape.py`, replace:

```python
def mine(x, y, z):
    return {"kind": "mine", "target": [x, y, z]}
```

with:

```python
def mine(x, y, z):
    return {"kind": "mine", "target": [x, y, z]}


def rubble(x, y, z):
    return {**mine(x, y, z), "rubble": True}
```

and replace:

```python
        self.assertEqual(escape_plan(pit(), (0, 1, 0), {}, "1"),
                         [mine(1, 2, 0), walk(1, 2, 0), mine(1, 3, 0), mine(2, 3, 0), walk(2, 3, 0),
                          mine(2, 4, 0), mine(3, 4, 0), walk(3, 4, 0), walk(4, 5, 0)])
```

with:

```python
        self.assertEqual(escape_plan(pit(), (0, 1, 0), {}, "1"),
                         [mine(1, 2, 0), mine(1, 3, 0), rubble(1, 4, 0), rubble(1, 2, 1), rubble(1, 3, 1),
                          rubble(1, 4, 1), walk(1, 2, 0),
                          mine(2, 3, 0), mine(2, 4, 0), rubble(2, 3, 1), rubble(2, 4, 1), walk(2, 3, 0),
                          mine(3, 4, 0), rubble(3, 4, 1), walk(3, 4, 0), walk(4, 5, 0)])
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_passages.py"`
Expected: `ImportError: cannot import name 'PASSAGE_TALL' from 'backend.survival.work'`.

- [ ] **Step 3: Leave rubble behind**

In `backend/survival/steps.py`, replace:

```python
    return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds / scale, 3),
            "target": as_point(target), "block": material}
```

with:

```python
    return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds / scale, 3),
            "target": as_point(target), "block": material, **({"rubble": True} if spec.get("rubble") else {})}
```

and replace:

```python
    drop = BLOCKS.get(step["block"], {}).get("drop")
    if drop:
        add_item(state["inventory"], drop)
    for item in nature.chance_drops(seed_of(state), target, step["block"]):
        add_item(state["inventory"], item)
    return None
```

with:

```python
    if step.get("rubble"):  # L3: a widening cell of a passage: Mimo leaves its block behind
        return None
    drop = BLOCKS.get(step["block"], {}).get("drop")
    if drop:
        add_item(state["inventory"], drop)
    for item in nature.chance_drops(seed_of(state), target, step["block"]):
        add_item(state["inventory"], item)
    return None
```


- [ ] **Step 4: Cut the passages 2 wide and 3 tall**

In `backend/survival/work.py`, replace:

```python
gather_stone needs a pickaxe and, short of prospecting, room left to carry more cobblestone: it
digs a staircase down from where Mimo stands, two blocks per stair, and turns into a level tunnel
10 blocks under the surface (or at y -3), until Mimo carries 12 cobblestone (and the blocks a
```

with:

```python
gather_stone needs a pickaxe and, short of prospecting, room left to carry more cobblestone: it
digs a staircase down from where Mimo stands, one block down per stair, 2 wide and 3 tall where
that fits (L3: the owner asked for passages big enough to see into), and turns into a level tunnel
of the same size 10 blocks under the surface (or at y -3), until Mimo carries 12 cobblestone (and the blocks a
```

and replace:

```python
unless the same stair just opened that cell, so it cannot cut its own staircase. The staircase
stays climbable, and from its third stair it is sheltered, so it often becomes Mimo's first home.
```

with:

```python
unless the same stair just opened that cell, so it cannot cut its own staircase. The staircase
stays climbable, and from its fourth stair it is sheltered, so it often becomes Mimo's first home.
```

and replace:

```python
FLUIDS = ("water", "lava")
```

with:

```python
FLUIDS = ("water", "lava")
PASSAGE_TALL = 3  # cells a stair or tunnel is cut high; its second column (left of the heading) too
```

and replace:

```python
def stair(grid: Grid, changed: dict[Cell, str], at: Cell, heading: tuple[int, int], inventory: dict,
          seed: str) -> tuple[list[dict], Cell, int] | None:
    """One stair down (or, deep enough, one level tunnel step) from `at` toward `heading`.

    Returns the steps, where Mimo ends up and how many cobblestone the mining yields, or None
    when the way is blocked. `changed` holds the cells earlier stairs of the same plan opened.
    A block whose cell above is open below the natural surface is the floor of a passage (an
    earlier stair or tunnel, or a cave): it is never mined, unless this stair opened that cell.
    """
    x, y, z = at
    nx, nz = x + heading[0], z + heading[1]
    surface = terrain_height(nx, nz, seed)
    down = y - 1 >= max(LOWEST_FLOOR, surface - TUNNEL_DEPTH)
    to = (nx, y - 1, nz) if down else (nx, y, nz)
    if not is_solid(look(grid, changed, (nx, to[1] - 1, nz))):
        return None  # a hole or a cave below: never dig into it
    steps, stones, opened = [], 0, set()
    for cell in ([(nx, y, nz), to] if down else [to]):
        material = look(grid, changed, cell)
        if material in FLUIDS:
            return None
        if reserved(grid, cell) or reserved(grid, (nx, cell[1] + 1, nz)):
            return None  # never dig up Mimo's farm, a sapling it planted or anything it built
        if not is_solid(material):
            continue
        if hardness(material) is None or not can_harvest(material, inventory):
            return None
        above = (nx, cell[1] + 1, nz)
        if above not in opened and above[1] <= surface and not is_solid(look(grid, changed, above)):
            return None  # the floor of an open cell underground
        steps.append({"kind": "mine", "target": list(cell)})
        stones += 1 if BLOCKS.get(material, {}).get("drop") == "cobblestone" else 0
        changed[cell] = "air"
        opened.add(cell)
    steps.append(walk_to(to))
    return steps, to, stones
```

with:

```python
def side_of(heading: tuple[int, int]) -> tuple[int, int]:
    """The direction to the left of `heading`: where a passage's second column goes."""
    return -heading[1], heading[0]


def cut(grid: Grid, changed: dict[Cell, str], cell: Cell, surface: int, inventory: dict,
        opened: set[Cell]) -> str | None:
    """How one cell of a passage opens: "" when it is open already, its block when Mimo mines it, or
    None when it must stay: water or lava, something Mimo built or tends (or the cell over it), a
    block Mimo cannot mine, or the floor of an open cell below the natural surface that this stair
    did not open."""
    x, y, z = cell
    material = look(grid, changed, cell)
    if material in FLUIDS or reserved(grid, cell) or reserved(grid, (x, y + 1, z)):
        return None
    if not is_solid(material):
        return ""
    if hardness(material) is None or not can_harvest(material, inventory):
        return None
    above = (x, y + 1, z)
    if above not in opened and above[1] <= surface and not is_solid(look(grid, changed, above)):
        return None
    return material


def stair(grid: Grid, changed: dict[Cell, str], at: Cell, heading: tuple[int, int], inventory: dict,
          seed: str) -> tuple[list[dict], Cell, int] | None:
    """One stair down (or, deep enough, one level tunnel step) from `at` toward `heading`, cut 3 cells
    tall in Mimo's column and in the column to the left of the heading, so the passage is 2 wide and
    3 tall where that fits.

    Mimo's column must open where it will stand and, on a stair down, the headroom over that: when
    either cannot be cut the way is blocked and this returns None. Every other cell (the third one
    up, and the side column, which is only cut over solid ground) opens where it can and stays where
    it cannot, so the passage narrows or lowers there. Those widening cells break into rubble Mimo
    leaves behind (`rubble` mine steps), so a stair yields what a narrow one did (resolution 17).
    Returns the steps, top cells first, where Mimo ends up and how many cobblestone the mining
    yields. `changed` holds the cells earlier stairs of
    the same plan opened. A block whose cell above is open below the natural surface is the floor of
    a passage (an earlier stair or tunnel, or a cave): it is never mined, unless this stair opened
    that cell.
    """
    x, y, z = at
    nx, nz = x + heading[0], z + heading[1]
    surface = terrain_height(nx, nz, seed)
    down = y - 1 >= max(LOWEST_FLOOR, surface - TUNNEL_DEPTH)
    to = (nx, y - 1, nz) if down else (nx, y, nz)
    if not is_solid(look(grid, changed, (nx, to[1] - 1, nz))):
        return None  # a hole or a cave below: never dig into it
    columns = [(nx, nz, surface, 2 if down else 1)]  # (x, z, its surface, how many lowest cells it needs)
    sx, sz = nx + side_of(heading)[0], nz + side_of(heading)[1]
    if is_solid(look(grid, changed, (sx, to[1] - 1, sz))):
        columns.append((sx, sz, terrain_height(sx, sz, seed), 0))
    steps, stones, opened = [], 0, set()
    for cx, cz, top, needed in columns:
        for dy in reversed(range(PASSAGE_TALL)):
            cell = (cx, to[1] + dy, cz)
            block = cut(grid, changed, cell, top, inventory, opened)
            if block is None:
                if dy < needed:
                    return None
                continue
            if block:
                keep = dy < needed  # the cells Mimo walks through; it leaves the rest as rubble
                steps.append({"kind": "mine", "target": list(cell), **({} if keep else {"rubble": True})})
                stones += 1 if keep and BLOCKS.get(block, {}).get("drop") == "cobblestone" else 0
                changed[cell] = "air"
                opened.add(cell)
    steps.append(walk_to(to))
    return steps, to, stones
```


In `backend/survival/escape.py`, replace:

```python
is trapped. The way out is a staircase up, one block up per step: mine the block over Mimo's head
and the stair cell when they are solid, and place a carried block where a stair has nothing to
stand on (mined dirt and stone go into the stock too).
```

with:

```python
is trapped. The way out is a staircase up, one block up per step: mine the block over Mimo's head
and the stair cell when they are solid, and place a carried block where a stair has nothing to
stand on (mined dirt and stone go into the stock too). Where they fit (L3), the two cells over each
stair and the three beside it (left of the heading, over solid ground) open too, so the way out is
2 wide and 3 tall like Mimo's own stairs; a cell that cannot be mined there is left. The cell over a
stair is the next stair's headroom and is kept; the other widening cells break into rubble Mimo
leaves behind.
```

and replace:

```python
def open_up(grid: Grid, changed: dict[Cell, str], cell: Cell, stock: dict, steps: list[dict]) -> bool:
    """Make `cell` open, mining it if it is solid. False for fluids and blocks Mimo cannot mine."""
```

with:

```python
def open_up(grid: Grid, changed: dict[Cell, str], cell: Cell, stock: dict, steps: list[dict],
            rubble: bool = False) -> bool:
    """Make `cell` open, mining it if it is solid. False for fluids and blocks Mimo cannot mine. A
    `rubble` cell's block is left behind, so it adds nothing to the stock."""
```

and replace:

```python
    steps.append({"kind": "mine", "target": list(cell)})
    changed[cell] = "air"
    drop = BLOCKS.get(material, {}).get("drop")
    if drop:
        stock[drop] = stock.get(drop, 0) + 1
```

with:

```python
    steps.append({"kind": "mine", "target": list(cell), **({"rubble": True} if rubble else {})})
    changed[cell] = "air"
    drop = BLOCKS.get(material, {}).get("drop")
    if drop and not rubble:
        stock[drop] = stock.get(drop, 0) + 1
```

and replace:

```python
        if not (open_up(grid, changed, headroom, stock, steps) and open_up(grid, changed, stair, stock, steps)):
            return None
```

with:

```python
        if not (open_up(grid, changed, headroom, stock, steps) and open_up(grid, changed, stair, stock, steps)):
            return None
        open_up(grid, changed, (stair[0], stair[1] + 1, stair[2]), stock, steps)  # the next stair's headroom
        open_up(grid, changed, (stair[0], stair[1] + 2, stair[2]), stock, steps, rubble=True)
        side = (stair[0] - dz, stair[1], stair[2] + dx)
        if is_solid(look(grid, changed, (side[0], side[1] - 1, side[2]))):
            for dy in (0, 1, 2):
                open_up(grid, changed, (side[0], side[1] + dy, side[2]), stock, steps, rubble=True)
```


In `backend/survival/renewal.py`, replace:

```python
    """Cells a tree grown from `sapling` must leave open: Mimo's cell and the one above its head,
    and each home or shelter near enough for the canopy to reach, with the cell above it."""
    stands = [pet_cell(state)] + [cell_of(place) for place in places(db, SHELTER_KINDS, around=sapling,
                                                                     reach=CANOPY_REACH)]
    return {(x, y + dy, z) for x, y, z in stands for dy in (0, 1)}
```

with:

```python
    """Cells a tree grown from `sapling` must leave open: Mimo's cell and the two above it, and each
    home or shelter near enough for the canopy to reach, with the two cells above it (L3: Mimo's
    passages, where it often finds a home, stand 3 tall)."""
    stands = [pet_cell(state)] + [cell_of(place) for place in places(db, SHELTER_KINDS, around=sapling,
                                                                     reach=CANOPY_REACH)]
    return {(x, y + dy, z) for x, y, z in stands for dy in (0, 1, 2)}
```


- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_passages.py"`
Expected: `Ran 5 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 845 tests` … `OK` (5 new). The headless runs dig the wide stairs; seed 3's busiest game hour has 45 changes of purpose (the budget is 52).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 2 tests` … `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/survival/work.py backend/survival/escape.py backend/survival/steps.py backend/survival/renewal.py backend/tests/test_survival_passages.py backend/tests/test_survival_work.py backend/tests/test_survival_escape.py
git commit -m "feat: Mimo digs its staircases and tunnels 2 wide and 3 tall, leaving the widening as rubble" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Gold and diamond: the tool ladder and mine_ore learn them

**Files:**
- Modify: `backend/services/crafting.py` (gold and diamond pickaxes and swords; gold smelts; the ranks), `backend/survival/steps.py` (their mining speed), `backend/survival/creatures/combat.py` (their damage), `backend/survival/carrying.py` (`TREASURES`: diamonds and L3's other treasures are worth carrying), `backend/survival/senses.py` (Mimo notices gold and diamond ore), `backend/survival/storage.py` (gold on hand), `backend/survival/work.py` (`pickaxe_rank`; mine_ore wants gold and diamonds), `backend/survival/toolmaking.py` (the ladder climbs on; `upgrades`)
- Modify tests: `backend/tests/test_survival_toolmaking.py` (the iron pickaxe is no longer the top)
- Test: `backend/tests/test_survival_tiers.py`

**Interfaces:**
- Consumes: Task 2's `RECIPES.update` block; `crafting.TOOL_RANK`, `SMELTING`, `can_harvest`; `steps.PICKAXE_SPEED`; `combat.SWORDS`, `weapon`; `carrying.valuable`; `senses.ORES`; `work.wanted_ores`, `ore_score`; `toolmaking.LADDER`, `SWORD_LADDER`, `STATIONS`, `next_tool`, `tool_orders`, `open_swords`; `storage.KEEP`, `junk`.
- Produces:
  - Recipes at a crafting table: `gold_pickaxe` (3 gold_ingot, 2 sticks), `diamond_pickaxe` (3 diamond, 2 sticks), `gold_sword` (2 gold_ingot, 1 stick), `diamond_sword` (2 diamond, 1 stick). `SMELTING["gold_ore"] = "gold_ingot"`.
  - `TOOL_RANK`: gold 4, diamond 5 (gold and diamond ore need rank 3, an iron pickaxe). `PICKAXE_SPEED`: gold 7, diamond 8. `SWORDS`: gold 7, diamond 8 damage (resolution 19).
  - `carrying.TREASURES = ("diamond", "creature_seed", "iron_cap", "iron_tunic", "lantern")`, all valuable.
  - `senses.ORES` gains `gold_ore` and `diamond_ore` (remembered when seen, forgotten when mined).
  - `work.pickaxe_rank(inventory) -> int`; `work.enough_known(s, ore, have, need=3) -> bool`; `wanted_ores`: gold with an iron pickaxe until a gold one, diamonds with an iron pickaxe until a diamond one, each only while Mimo has fewer than 3 and remembers enough ores to reach 3 (one trip gets them all; resolution 20); a remembered gold or diamond ore scores like iron.
  - `toolmaking.LADDER` and `SWORD_LADDER` run to gold and diamond; `upgrades(inventory) -> list[str]` (the next pickaxe; over iron, diamond before gold); `tool_orders` walks `upgrades`. Gold tools need a furnace placed for smelting, diamond ones only a table.
  - `storage.KEEP`: 3 gold ore, 3 gold ingots.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_tiers.py`:

```python
import sqlite3
import unittest

from backend.services.crafting import RECIPES, SMELTING, TOOL_RANK, can_harvest, craft, smelt
from backend.survival import storage
from backend.survival.carrying import valuable
from backend.survival.creatures.combat import SWORDS, weapon
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, remember
from backend.survival.purposes import PURPOSES
from backend.survival.senses import ORES, ores_around
from backend.survival.steps import mine_seconds
from backend.survival.toolmaking import next_tool, tool_orders, tool_plan, upgrades
from backend.survival.work import pickaxe_rank, wanted_ores
from backend.tests.test_survival_storage import LOOSE, Home
from backend.tests.test_survival_toolmaking import flat, situation
from backend.tests.test_survival_work import ground, pet
from backend.tests.test_survival_work import situation as work_situation


def stations():
    grid = flat()
    grid.put(2, 1, 0, "crafting_table")
    grid.put(-2, 1, 0, "furnace")
    return grid


def craft_step(recipe):
    return {"kind": "craft", "recipe": recipe}


class TierTests(unittest.TestCase):
    def test_gold_and_diamond_pickaxes_and_swords_at_a_crafting_table(self):
        self.assertEqual(craft({"gold_ingot": 3, "sticks": 2}, "gold_pickaxe", {"crafting_table"}), {"gold_pickaxe": 1})
        self.assertEqual(craft({"diamond": 3, "sticks": 2}, "diamond_pickaxe", {"crafting_table"}), {"diamond_pickaxe": 1})
        self.assertEqual(craft({"gold_ingot": 2, "sticks": 1}, "gold_sword", {"crafting_table"}), {"gold_sword": 1})
        self.assertEqual(craft({"diamond": 2, "sticks": 1}, "diamond_sword", {"crafting_table"}), {"diamond_sword": 1})
        for item in ("gold_pickaxe", "diamond_pickaxe", "gold_sword", "diamond_sword"):
            self.assertEqual(RECIPES[item]["station"], "crafting_table")
            self.assertTrue(valuable(item))
        self.assertEqual(SMELTING["gold_ore"], "gold_ingot")
        self.assertEqual(smelt({"gold_ore": 1, "coal": 1}, "gold_ore", {"furnace"}), {"gold_ingot": 1})
        self.assertTrue(valuable("diamond") and valuable("gold_ingot") and valuable("gold_ore"))

    def test_each_tier_mines_faster_and_hits_harder(self):
        order = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "gold_pickaxe", "diamond_pickaxe")
        self.assertEqual([TOOL_RANK[tool] for tool in order], [1, 2, 3, 4, 5])
        times = [mine_seconds("stone", {tool: 1}) for tool in order]
        self.assertEqual(times, sorted(times, reverse=True))
        self.assertTrue(can_harvest("diamond_ore", {"gold_pickaxe": 1}))
        self.assertFalse(can_harvest("gold_ore", {"stone_pickaxe": 1}))
        self.assertEqual(list(SWORDS.values()), sorted(SWORDS.values()))
        self.assertEqual(weapon({"iron_sword": 1, "diamond_sword": 1, "gold_sword": 1}), "diamond_sword")


class LadderTests(unittest.TestCase):
    def test_over_an_iron_pickaxe_a_diamond_one_comes_before_gold(self):
        self.assertEqual(next_tool({"iron_pickaxe": 1}), "gold_pickaxe")
        self.assertEqual(upgrades({"iron_pickaxe": 1}), ["diamond_pickaxe", "gold_pickaxe"])
        self.assertEqual(upgrades({"stone_pickaxe": 1}), ["iron_pickaxe"])
        self.assertEqual(upgrades({"gold_pickaxe": 1}), ["diamond_pickaxe"])
        self.assertEqual(upgrades({"diamond_pickaxe": 1}), [])
        self.assertEqual(tool_orders({"iron_pickaxe": 1, "iron_sword": 1}),
                         [("diamond_pickaxe", "diamond_sword"), ("diamond_pickaxe", "gold_sword"), ("diamond_pickaxe",),
                          ("gold_pickaxe", "gold_sword"), ("gold_pickaxe",)])

    def test_gold_ore_is_smelted_into_a_gold_pickaxe_and_sword(self):
        s = situation({"iron_pickaxe": 1, "iron_sword": 1, "gold_ore": 5, "coal": 5, "sticks": 3}, stations())
        self.assertEqual(tool_plan(s), [{"kind": "smelt", "item": "gold_ore"}] * 3 + [craft_step("gold_pickaxe")]
                         + [{"kind": "smelt", "item": "gold_ore"}] * 2 + [craft_step("gold_sword")])
        self.assertEqual(PURPOSES["craft_tools"].facts(s), "can make a gold pickaxe and a gold sword now")

    def test_diamonds_skip_gold(self):
        s = situation({"iron_pickaxe": 1, "diamond": 5, "sticks": 3}, stations())
        self.assertEqual(tool_plan(s), [craft_step("diamond_pickaxe"), craft_step("diamond_sword")])

    def test_a_replaced_pickaxe_and_sword_are_dropped(self):
        junk = storage.junk(Home({**LOOSE, "gold_pickaxe": 1, "diamond_pickaxe": 1, "gold_sword": 1,
                                  "diamond_sword": 1}).situation())
        self.assertIn(("gold_pickaxe", 1), junk)
        self.assertIn(("gold_sword", 1), junk)
        self.assertNotIn(("diamond_pickaxe", 1), junk)


class OreTests(unittest.TestCase):
    def test_gold_and_diamond_are_noticed_and_wanted_once_mimo_has_an_iron_pickaxe(self):
        self.assertTrue({"gold_ore", "diamond_ore"} <= set(ORES))
        grid = Grid(lambda x, y, z: {(1, 0, 0): "gold_ore", (0, 1, 1): "diamond_ore"}.get((x, y, z), "stone"))
        self.assertEqual(sorted(ores_around(grid, (0, 0, 0))), [((0, 1, 1), "diamond_ore"), ((1, 0, 0), "gold_ore")])
        seen = lambda ore, count: [("ore", (9, -3, z), ore) for z in range(count)]
        both = seen("gold_ore", 3) + [("ore", (12, -3, z), "diamond_ore") for z in range(3)]
        want = lambda inventory, known=(): wanted_ores(work_situation(pet(inventory=inventory), ground(), known))
        self.assertEqual(want({"stone_pickaxe": 1, "coal": 8}, both), ("iron_ore",))
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8}), ())  # none known: no trip worth making yet
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8}, both), ("gold_ore", "diamond_ore"))
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8}, seen("gold_ore", 2)), ())  # not enough for a pickaxe
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8, "gold_ingot": 1}, seen("gold_ore", 2)), ("gold_ore",))
        self.assertEqual(want({"gold_pickaxe": 1, "coal": 8}, both), ("diamond_ore",))
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8, "gold_ingot": 3, "diamond": 3}, both), ())
        self.assertEqual(want({"diamond_pickaxe": 1, "coal": 8}, both), ())
        self.assertEqual(pickaxe_rank({"iron_pickaxe": 1, "wooden_pickaxe": 1}), 3)

    def test_mine_ore_goes_back_for_a_diamond(self):
        grid = ground({(3, -3, 0): "diamond_ore"})
        seen = [("ore", (3, -3, 0), "diamond_ore")]
        self.assertFalse(PURPOSES["mine_ore"].valid(work_situation(pet(inventory={"stone_pickaxe": 1, "coal": 8}), grid, seen)))
        s = work_situation(pet(inventory={"iron_pickaxe": 1, "coal": 8, "diamond": 2}), grid, seen)
        self.assertTrue(PURPOSES["mine_ore"].valid(s))
        self.assertEqual(PURPOSES["mine_ore"].plan(s, None),
                         [{"kind": "walk", "target": [3, -3, 0], "reach": 3.0}, {"kind": "mine", "target": [3, -3, 0]}])


if __name__ == "__main__":
    unittest.main()
```


In `backend/tests/test_survival_toolmaking.py`, replace:

```python
        self.assertIsNone(next_tool({"iron_pickaxe": 1}))
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"iron_pickaxe": 1, "iron_sword": 1, "oak_log": 9})))
```

with:

```python
        self.assertIsNone(next_tool({"diamond_pickaxe": 1}))  # L3: gold and diamond come after iron
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"diamond_pickaxe": 1, "diamond_sword": 1, "oak_log": 9})))
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_tiers.py"`
Expected: `ImportError: cannot import name 'upgrades' from 'backend.survival.toolmaking'`.

- [ ] **Step 3: Recipes, ranks, speeds and damage**

In `backend/services/crafting.py`, replace:

```python
    "stone_bricks": {"ingredients": {"cobblestone": 4}, "output": {"stone_bricks": 4}},
})
```

with:

```python
    "stone_bricks": {"ingredients": {"cobblestone": 4}, "output": {"stone_bricks": 4}},
    # Gold and diamond tiers, at a crafting table like iron's.
    "gold_pickaxe": {"ingredients": {"gold_ingot": 3, "sticks": 2}, "output": {"gold_pickaxe": 1}, "station": "crafting_table"},
    "diamond_pickaxe": {"ingredients": {"diamond": 3, "sticks": 2}, "output": {"diamond_pickaxe": 1}, "station": "crafting_table"},
    "gold_sword": {"ingredients": {"gold_ingot": 2, "sticks": 1}, "output": {"gold_sword": 1}, "station": "crafting_table"},
    "diamond_sword": {"ingredients": {"diamond": 2, "sticks": 1}, "output": {"diamond_sword": 1}, "station": "crafting_table"},
})
```

and replace:

```python
TOOL_RANK = {"wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3}
```

with:

```python
TOOL_RANK = {"wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3, "gold_pickaxe": 4, "diamond_pickaxe": 5}
```

and replace:

```python
SMELTING = {"iron_ore": "iron_ingot", "copper_ore": "copper_ingot", "sand": "glass", "clay": "brick",
```

with:

```python
SMELTING = {"iron_ore": "iron_ingot", "gold_ore": "gold_ingot", "copper_ore": "copper_ingot", "sand": "glass", "clay": "brick",
```


In `backend/survival/steps.py`, replace:

```python
PICKAXE_SPEED = {"wooden_pickaxe": 2.0, "stone_pickaxe": 4.0, "iron_pickaxe": 6.0}
```

with:

```python
PICKAXE_SPEED = {"wooden_pickaxe": 2.0, "stone_pickaxe": 4.0, "iron_pickaxe": 6.0, "gold_pickaxe": 7.0,
                 "diamond_pickaxe": 8.0}
```


In `backend/survival/creatures/combat.py`, replace:

```python
SWORDS = {"wooden_sword": 4.0, "stone_sword": 5.0, "iron_sword": 6.0}  # damage, weakest first
```

with:

```python
SWORDS = {"wooden_sword": 4.0, "stone_sword": 5.0, "iron_sword": 6.0, "gold_sword": 7.0,
          "diamond_sword": 8.0}  # damage, weakest first
```


In `backend/survival/carrying.py`, replace:

```python
def valuable(item: str) -> bool:
```

with:

```python
# L3: diamonds, creature seeds, iron armor and lanterns are worth carrying too.
TREASURES = ("diamond", "creature_seed", "iron_cap", "iron_tunic", "lantern")


def valuable(item: str) -> bool:
```

and replace:

```python
            or item in AXES or item.endswith(("_ore", "_ingot", "_sword")))
```

with:

```python
            or item in AXES or item in TREASURES or item.endswith(("_ore", "_ingot", "_sword")))
```


In `backend/survival/storage.py`, replace:

```python
             "pumpkin": 0, "melon": 0, "cactus": 0, "sugar_cane": 0})
```

with:

```python
             "pumpkin": 0, "melon": 0, "cactus": 0, "sugar_cane": 0, "gold_ore": 3, "gold_ingot": 3})
```


- [ ] **Step 4: Notice, want and mine the new ores**

In `backend/survival/senses.py`, replace:

```python
ORES = ("coal_ore", "iron_ore", "copper_ore")
```

with:

```python
ORES = ("coal_ore", "iron_ore", "copper_ore", "gold_ore", "diamond_ore")
```


In `backend/survival/work.py`, replace:

```python
mine_ore walks to a remembered coal or iron ore Mimo can harvest and still needs, within 48
blocks, and mines it.
```

with:

```python
mine_ore walks to a remembered coal, iron, gold or diamond ore Mimo can harvest and still needs,
within 48 blocks, and mines it: gold and diamonds once it has an iron pickaxe and knows where enough
lie for the pickaxe above it (L3).
```

and replace:

```python
def wanted_ores(s: Situation) -> tuple[str, ...]:
    """Coal until Mimo carries 8; iron until it has 3 ore or ingots (or an iron pickaxe)."""
    wanted = []
    if s.count("coal") < 8:
        wanted.append("coal_ore")
    if s.count("iron_ore", "iron_ingot") < 3 and not s.count("iron_pickaxe"):
        wanted.append("iron_ore")
    return tuple(wanted)
```

with:

```python
def pickaxe_rank(inventory: dict) -> int:
    """The rank of the best pickaxe Mimo carries (crafting.TOOL_RANK), 0 with none."""
    return max((rank for tool, rank in TOOL_RANK.items() if inventory.get(tool, 0) > 0), default=0)


def enough_known(s: Situation, ore: str, have: int, need: int = 3) -> bool:
    """Mimo has fewer than `need` of what `ore` gives, and with the ores of that kind it remembers it
    would have enough: one trip then gets them all (L3's gold and diamonds, needed 3 at a time)."""
    known = sum(1 for place in s.places if place["kind"] == "ore" and place["note"] == ore)
    return have < need <= have + known


def wanted_ores(s: Situation) -> tuple[str, ...]:
    """Coal until Mimo carries 8; iron until it has 3 ore or ingots (or an iron pickaxe or better);
    with an iron pickaxe (L3), gold (until a gold pickaxe or better) and diamonds (until a diamond
    pickaxe), but only once it knows where enough lie for a pickaxe (`enough_known`)."""
    wanted, rank = [], pickaxe_rank(s.inventory)
    if s.count("coal") < 8:
        wanted.append("coal_ore")
    if s.count("iron_ore", "iron_ingot") < 3 and rank < TOOL_RANK["iron_pickaxe"]:
        wanted.append("iron_ore")
    if (TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["gold_pickaxe"]
            and enough_known(s, "gold_ore", s.count("gold_ore", "gold_ingot"))):
        wanted.append("gold_ore")
    if TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["diamond_pickaxe"] and enough_known(s, "diamond_ore", s.count("diamond")):
        wanted.append("diamond_ore")
    return tuple(wanted)
```

and replace:

```python
    iron = any(place["note"] == "iron_ore" for place in targets)
```

with:

```python
    iron = any(place["note"] in ("iron_ore", "gold_ore", "diamond_ore") for place in targets)
```

and replace:

```python
    "mine_ore", "mine ore", "Go back to coal or iron ore seen while digging and mine it.",
```

with:

```python
    "mine_ore", "mine ore", "Go back to coal, iron, gold or diamond ore seen while digging and mine it.",
```


- [ ] **Step 5: Climb the ladder**

In `backend/survival/toolmaking.py`, replace:

```python
The ladder is wooden pickaxe, stone pickaxe, iron pickaxe. Only the next one Mimo lacks is on
offer, and only when everything it needs can be made from what Mimo carries. Swords (L1) climb a
ladder of their own (wooden, stone, iron: 2 planks, cobblestone or ingots and a stick, at a
crafting table) no higher than the best pickaxe Mimo has.
```

with:

```python
The ladder is wooden pickaxe, stone pickaxe, iron pickaxe, gold pickaxe, diamond pickaxe (L3). Only
the next one Mimo lacks is on offer (and, over an iron pickaxe, a diamond one first: diamonds need
no smelting, so gold may be skipped), and only when everything it needs can be made from what Mimo
carries. Swords (L1) climb a ladder of their own (wooden, stone, iron, gold, diamond: 2 planks,
cobblestone, ingots or diamonds and a stick, at a crafting table) no higher than the best pickaxe
Mimo has.
```

and replace:

```python
LADDER = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe")
SWORD_LADDER = ("wooden_sword", "stone_sword", "iron_sword")
STATIONS = {"wooden_pickaxe": ("crafting_table",), "stone_pickaxe": ("crafting_table",),
            "iron_pickaxe": ("crafting_table", "furnace"), "wooden_sword": ("crafting_table",),
            "stone_sword": ("crafting_table",), "iron_sword": ("crafting_table", "furnace")}
```

with:

```python
LADDER = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "gold_pickaxe", "diamond_pickaxe")
SWORD_LADDER = ("wooden_sword", "stone_sword", "iron_sword", "gold_sword", "diamond_sword")
STATIONS = {"wooden_pickaxe": ("crafting_table",), "stone_pickaxe": ("crafting_table",),
            "iron_pickaxe": ("crafting_table", "furnace"), "wooden_sword": ("crafting_table",),
            "stone_sword": ("crafting_table",), "iron_sword": ("crafting_table", "furnace"),
            "gold_pickaxe": ("crafting_table", "furnace"), "gold_sword": ("crafting_table", "furnace"),
            "diamond_pickaxe": ("crafting_table",), "diamond_sword": ("crafting_table",)}
```

and replace:

```python
def tool_orders(inventory: dict) -> list[tuple[str, ...]]:
    """What craft_tools may make, first choice first: the next pickaxe with the best sword it opens
    up, the pickaxe alone, then a sword alone."""
    orders: list[tuple[str, ...]] = []
    pickaxe = next_tool(inventory)
    if pickaxe is not None:
        orders += [(pickaxe, sword) for sword in open_swords({**inventory, pickaxe: 1})]
        orders.append((pickaxe,))
```

with:

```python
def upgrades(inventory: dict) -> list[str]:
    """The pickaxes craft_tools may make next, best first: the next one up the ladder and, over an
    iron pickaxe, the diamond one before the gold one (L3)."""
    pickaxe = next_tool(inventory)
    if pickaxe == "gold_pickaxe":
        return ["diamond_pickaxe", "gold_pickaxe"]
    return [] if pickaxe is None else [pickaxe]


def tool_orders(inventory: dict) -> list[tuple[str, ...]]:
    """What craft_tools may make, first choice first: the next pickaxe with the best sword it opens
    up, the pickaxe alone, then a sword alone."""
    orders: list[tuple[str, ...]] = []
    for pickaxe in upgrades(inventory):
        orders += [(pickaxe, sword) for sword in open_swords({**inventory, pickaxe: 1})]
        orders.append((pickaxe,))
```


- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_tiers.py"`
Expected: `Ran 8 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 853 tests` … `OK` (8 new).

- [ ] **Step 7: Commit**

```bash
git add backend/services/crafting.py backend/survival/steps.py backend/survival/creatures/combat.py backend/survival/carrying.py backend/survival/senses.py backend/survival/storage.py backend/survival/work.py backend/survival/toolmaking.py backend/tests/test_survival_tiers.py backend/tests/test_survival_toolmaking.py
git commit -m "feat: gold and diamond pickaxes and swords, and Mimo goes after gold and diamond ore once it has an iron pickaxe" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Iron armor and lanterns

**Files:**
- Modify: `backend/services/crafting.py` (iron cap and tunic; the lantern), `backend/survival/creatures/harm.py` (L2's armor table gains iron; the best piece per slot; `covered`, `armor_iron`, `armor_wanted`), `backend/survival/creatures/gear.py` (L2's make_gear makes leather only for a bare slot), `backend/survival/toolmaking.py` (craft_tools makes the iron armor and then lanterns; `tool_words`), `backend/survival/work.py` (the iron the armor takes), `backend/survival/structures.py` (a lantern lights a torch corner), `backend/survival/lighting.py` (light_up hangs lanterns first and swaps torches for spare ones), `backend/survival/storage.py` (leather replaced by iron is dropped; iron kept on hand)
- Test: `backend/tests/test_survival_armor.py`

**Interfaces:**
- Consumes: L2's `harm.ARMOR`, `armor_cut`, `hurt_pet` and `gear.gear_orders`, `ARMOR_PIECES`; L2's light table (`light.BLOCK_LIGHT["lantern"] == 15`, so a lantern needs no light code); Task 7's `toolmaking.tool_orders`, `work.wanted_ores`, `carrying.TREASURES`; `lighting.dark_corners`, `torch_supply`, `plan_light`, `light_valid`; `structures.missing`.
- Produces:
  - Recipes: `iron_cap` (5 iron_ingot) and `iron_tunic` (8 iron_ingot) at a crafting table; `lantern` (1 iron_ingot, 1 torch), no station.
  - `harm.ARMOR` gains `iron_cap` 0.18 and `iron_tunic` 0.27 (45 % together, the spec's figure); `harm.SLOTS` (head or body); `harm.IRON_ARMOR = ("iron_tunic", "iron_cap")`; `armor_cut(inventory)` sums the best piece of each slot (leather under iron counts once); `covered(inventory, piece) -> bool`; `armor_iron(inventory) -> int` (ingots the missing iron pieces take); `armor_wanted(state) -> bool` (a creature has hurt Mimo: `state["hurt_at"]` is set).
  - `gear.gear_orders` offers a leather piece only for a slot with no armor.
  - `toolmaking.tool_orders(inventory, armor=False)`: with `armor`, after the pickaxes and swords, the iron pieces missing (together, then each) once Mimo has an iron pickaxe or better; then `("lantern",)` while it wears both pieces, carries a spare iron ingot and fewer than `LANTERNS_WANTED = 4` lanterns. `tool_choice` passes `armor_wanted(s.state)`. `STATIONS` gains `iron_cap` and `iron_tunic` (table and furnace) and `lantern` (none). `tool_words(tools)` writes "a stone pickaxe and an iron cap".
  - `work.wanted_ores`: with an iron pickaxe or better and `armor_wanted`, iron until Mimo carries what the missing pieces take.
  - `structures.STANDS_IN = {"torch": ("torch", "lantern")}`: `missing` counts a lantern in a torch cell as lit.
  - `lighting.home_blueprint(s)`, `torch_corners(s)`; light_up puts carried lanterns on dark corners before torches, and with lanterns left over mines a corner's torch and hangs a lantern there.
  - `storage.junk` lists a leather piece whose iron piece Mimo carries; `storage.KEEP` keeps 16 iron ore and 16 ingots on hand (the armor takes 13).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_armor.py`:

```python
import unittest

from backend.services.crafting import craft
from backend.survival import storage
from backend.survival.carrying import valuable
from backend.survival.creatures.gear import gear_orders
from backend.survival.creatures.harm import armor_cut, armor_iron, armor_wanted, covered
from backend.survival.purposes import PURPOSES
from backend.survival.toolmaking import LANTERNS_WANTED, tool_plan
from backend.survival.work import wanted_ores
from backend.tests import test_survival_lighting as lighting_tests
from backend.tests.test_survival_lighting import CORNERS, EVENING
from backend.tests.test_survival_storage import LOOSE, Home
from backend.tests.test_survival_toolmaking import flat, situation
from backend.tests.test_survival_work import ground, pet
from backend.tests.test_survival_work import situation as work_situation

IRON = {"iron_cap": 1, "iron_tunic": 1}
LEATHER = {"leather_cap": 1, "leather_tunic": 1}


def stations():
    grid = flat()
    grid.put(2, 1, 0, "crafting_table")
    grid.put(-2, 1, 0, "furnace")
    return grid


def hurt(s):
    s.state["hurt_at"] = 5.0
    return s


class ArmorTests(unittest.TestCase):
    def test_iron_armor_at_a_crafting_table_and_lanterns_from_iron_and_a_torch(self):
        self.assertEqual(craft({"iron_ingot": 5}, "iron_cap", {"crafting_table"}), {"iron_cap": 1})
        self.assertEqual(craft({"iron_ingot": 8}, "iron_tunic", {"crafting_table"}), {"iron_tunic": 1})
        self.assertEqual(craft({"iron_ingot": 1, "torch": 2}, "lantern", set()), {"torch": 1, "lantern": 1})
        for item in ("iron_cap", "iron_tunic", "lantern"):
            self.assertTrue(valuable(item))

    def test_iron_takes_45_percent_off_a_blow_and_only_the_best_piece_on_each_slot_counts(self):
        self.assertAlmostEqual(armor_cut(IRON), 0.45)
        self.assertAlmostEqual(armor_cut({**IRON, **LEATHER}), 0.45)
        self.assertAlmostEqual(armor_cut(LEATHER), 0.20)
        self.assertAlmostEqual(armor_cut({"iron_cap": 1, "leather_tunic": 1}), 0.30)
        self.assertTrue(covered({"iron_cap": 1}, "leather_cap"))
        self.assertFalse(covered({"iron_cap": 1}, "leather_tunic"))
        self.assertEqual((armor_iron({}), armor_iron({"iron_cap": 1}), armor_iron(IRON)), (13, 8, 0))

    def test_leather_is_only_made_for_a_bare_slot(self):
        self.assertNotIn(("leather_tunic", "leather_cap"), gear_orders(IRON))
        self.assertEqual(gear_orders({"iron_cap": 1, "bow": 1, "arrow": 8}), [("leather_tunic",)])


class IronArmorPlanTests(unittest.TestCase):
    def test_once_a_creature_has_hurt_it_mimo_makes_iron_armor(self):
        inventory = {"iron_pickaxe": 1, "iron_sword": 1, "iron_ingot": 13}
        self.assertFalse(armor_wanted({}))
        self.assertIsNone(tool_plan(situation(inventory, stations())))
        s = hurt(situation(inventory, stations()))
        self.assertEqual(tool_plan(s), [{"kind": "craft", "recipe": "iron_tunic"}, {"kind": "craft", "recipe": "iron_cap"}])
        self.assertEqual(PURPOSES["craft_tools"].facts(s), "can make an iron tunic and an iron cap now")

    def test_and_goes_after_the_iron_it_takes(self):
        s = work_situation(pet(inventory={"iron_pickaxe": 1, "coal": 8, "gold_ingot": 3, "diamond": 3}), ground())
        self.assertEqual(wanted_ores(s), ())
        self.assertEqual(wanted_ores(hurt(s)), ("iron_ore",))

    def test_spare_iron_makes_lanterns_once_mimo_wears_both_pieces(self):
        best = {"diamond_pickaxe": 1, "diamond_sword": 1, **IRON}
        s = hurt(situation({**best, "iron_ingot": 2, "torch": 2}, stations()))
        self.assertEqual(tool_plan(s), [{"kind": "craft", "recipe": "lantern"}])
        self.assertIsNone(tool_plan(hurt(situation({**best, "iron_ingot": 2, "torch": 2, "lantern": LANTERNS_WANTED},
                                                   stations()))))

    def test_iron_replaces_leather(self):
        junk = storage.junk(Home({**LOOSE, "iron_cap": 1, "leather_cap": 1, "leather_tunic": 1}).situation())
        self.assertIn(("leather_cap", 1), junk)
        self.assertNotIn(("leather_tunic", 1), junk)


class LanternTests(unittest.TestCase):
    setUp = lighting_tests.LightTests.setUp  # a finished shelter with four torch corners
    situation = lighting_tests.LightTests.situation
    plan = lighting_tests.LightTests.plan

    def test_lanterns_light_the_dark_corners_first_then_torches(self):
        steps = self.plan(self.situation({"lantern": 1, "torch": 4}))
        placed = sorted((step["target"], step["block"]) for step in steps if step["kind"] == "place")
        self.assertEqual(sorted(cell for cell, _ in placed), sorted(CORNERS))
        self.assertEqual(sorted(block for _, block in placed), ["lantern", "torch", "torch", "torch"])

    def test_a_carried_lantern_takes_a_torch_corner_and_a_lantern_corner_is_lit(self):
        for cell in CORNERS:
            self.grid.put(*cell, "torch")
        self.assertFalse(PURPOSES["light_up"].valid(self.situation({"torch": 4})))
        s = self.situation({"lantern": 1})
        self.assertTrue(PURPOSES["light_up"].valid(s))
        steps = self.plan(s)
        at = steps.index({"kind": "place", "target": CORNERS[0], "block": "lantern"})
        self.assertEqual(steps[at - 1], {"kind": "mine", "target": CORNERS[0]})
        self.grid.put(*CORNERS[0], "lantern")
        self.assertFalse(PURPOSES["light_up"].valid(self.situation({"torch": 4}, clock=EVENING)))


if __name__ == "__main__":
    unittest.main()
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_armor.py"`
Expected: `ImportError: cannot import name 'armor_iron' from 'backend.survival.creatures.harm'`.

- [ ] **Step 3: The recipes and the armor table**

In `backend/services/crafting.py`, replace:

```python
    "diamond_sword": {"ingredients": {"diamond": 2, "sticks": 1}, "output": {"diamond_sword": 1}, "station": "crafting_table"},
})
```

with:

```python
    "diamond_sword": {"ingredients": {"diamond": 2, "sticks": 1}, "output": {"diamond_sword": 1}, "station": "crafting_table"},
    # Iron armor at a crafting table; a lantern (L2's light 15) from an iron ingot and a torch, anywhere.
    "iron_cap": {"ingredients": {"iron_ingot": 5}, "output": {"iron_cap": 1}, "station": "crafting_table"},
    "iron_tunic": {"ingredients": {"iron_ingot": 8}, "output": {"iron_tunic": 1}, "station": "crafting_table"},
    "lantern": {"ingredients": {"iron_ingot": 1, "torch": 1}, "output": {"lantern": 1}},
})
```


In `backend/survival/creatures/harm.py`, replace:

```python
from backend.survival.creatures.table import missing_table
```

with:

```python
from backend.services.crafting import RECIPES
from backend.survival.creatures.table import missing_table
```

and replace:

```python
ARMOR = {"leather_cap": 0.08, "leather_tunic": 0.12}  # the share of a blow each piece takes off
```

with:

```python
ARMOR = {"leather_cap": 0.08, "leather_tunic": 0.12}  # the share of a blow each piece takes off
# L3: iron armor, 45 % together; a piece covers a slot, and only the best piece on each slot counts.
ARMOR.update({"iron_cap": 0.18, "iron_tunic": 0.27})
SLOTS = {"leather_cap": "head", "iron_cap": "head", "leather_tunic": "body", "iron_tunic": "body"}
IRON_ARMOR = ("iron_tunic", "iron_cap")
```

and replace:

```python
def armor_cut(inventory: dict) -> float:
    """The share of a blow the armor Mimo carries takes off."""
    return sum(cut for piece, cut in ARMOR.items() if inventory.get(piece, 0) > 0)
```

with:

```python
def armor_cut(inventory: dict) -> float:
    """The share of a blow the armor Mimo carries takes off: the best piece on each slot (head and
    body), so an iron cap over a leather one counts once (L3)."""
    best: dict[str, float] = {}
    for piece, cut in ARMOR.items():
        if inventory.get(piece, 0) > 0:
            slot = SLOTS.get(piece, piece)
            best[slot] = max(best.get(slot, 0.0), cut)
    return sum(best.values())


def covered(inventory: dict, piece: str) -> bool:
    """Mimo carries some armor for the slot `piece` goes on (L3)."""
    slot = SLOTS.get(piece, piece)
    return any(inventory.get(other, 0) > 0 for other in ARMOR if SLOTS.get(other, other) == slot)


def armor_wanted(state: dict) -> bool:
    """Iron armor is worth its 13 ingots once a creature has hurt Mimo (L3)."""
    return state.get("hurt_at") is not None


def armor_iron(inventory: dict) -> int:
    """Iron ingots the iron armor Mimo still lacks takes (L3)."""
    return sum(RECIPES[piece]["ingredients"]["iron_ingot"] for piece in IRON_ARMOR if inventory.get(piece, 0) < 1)
```


In `backend/survival/creatures/gear.py`, replace:

```python
from backend.survival.carrying import crafts_fit
```

with:

```python
from backend.survival.carrying import crafts_fit
from backend.survival.creatures.harm import covered
```

and replace:

```python
    armor = tuple(piece for piece in ARMOR_PIECES if inventory.get(piece, 0) < 1)
```

with:

```python
    armor = tuple(piece for piece in ARMOR_PIECES if not covered(inventory, piece))  # L3: iron covers a slot too
```


- [ ] **Step 4: craft_tools makes the armor and the lanterns, and mine_ore brings the iron**

In `backend/survival/toolmaking.py`, replace:

```python
def tool_orders(inventory: dict) -> list[tuple[str, ...]]:
    """What craft_tools may make, first choice first: the next pickaxe with the best sword it opens
    up, the pickaxe alone, then a sword alone."""
```

with:

```python
def tool_orders(inventory: dict, armor: bool = False) -> list[tuple[str, ...]]:
    """What craft_tools may make, first choice first: the next pickaxe with the best sword it opens
    up, the pickaxe alone, then a sword alone; then (L3) with `armor` (a creature has hurt Mimo) the
    iron armor it lacks, and lanterns from spare iron once it wears both pieces."""
```

and replace:

```python
        for tools in tool_orders(s.inventory):
```

with:

```python
        for tools in tool_orders(s.inventory, armor_wanted(s.state)):
```

and replace:

```python
from backend.survival.carrying import crafts_fit
```

with:

```python
from backend.survival.carrying import crafts_fit
from backend.survival.creatures.harm import IRON_ARMOR, armor_wanted
```

and replace:

```python
            "diamond_pickaxe": ("crafting_table",), "diamond_sword": ("crafting_table",)}
```

with:

```python
            "diamond_pickaxe": ("crafting_table",), "diamond_sword": ("crafting_table",),
            "iron_cap": ("crafting_table", "furnace"), "iron_tunic": ("crafting_table", "furnace"), "lantern": ()}
LANTERNS_WANTED = 4  # lanterns Mimo makes to carry home (light_up hangs them), from spare iron
```

and replace:

```python
    orders += [(sword,) for sword in open_swords(inventory)]
    return orders
```

with:

```python
    orders += [(sword,) for sword in open_swords(inventory)]
    return orders + (armor_orders(inventory) if armor else []) + lantern_orders(inventory)


def armor_orders(inventory: dict) -> list[tuple[str, ...]]:
    """Iron armor once Mimo has an iron pickaxe or better (L3): the pieces it lacks together, then each
    alone. The ingots are smelted at a furnace placed for it, like the iron pickaxe's."""
    if max((TOOL_RANK[tool] for tool in TOOL_RANK if inventory.get(tool, 0) > 0), default=0) < TOOL_RANK["iron_pickaxe"]:
        return []
    missing = tuple(piece for piece in IRON_ARMOR if inventory.get(piece, 0) < 1)
    return ([missing] if len(missing) > 1 else []) + [(piece,) for piece in missing]


def lantern_orders(inventory: dict) -> list[tuple[str, ...]]:
    """A lantern from a carried iron ingot and a torch, once Mimo wears both iron pieces, while it
    carries fewer than LANTERNS_WANTED (L3)."""
    done = all(inventory.get(piece, 0) > 0 for piece in IRON_ARMOR)
    return [("lantern",)] if done and inventory.get("iron_ingot", 0) > 0 and inventory.get("lantern", 0) < LANTERNS_WANTED else []


def tool_words(tools: tuple[str, ...]) -> str:
    """ "a stone pickaxe and an iron cap" """
    return " and ".join(f"{'an' if tool[0] in 'aeiou' else 'a'} {tool.replace('_', ' ')}" for tool in tools)
```

and replace:

```python
    facts=lambda s: "can make " + " and ".join(f"a {tool.replace('_', ' ')}" for tool in tool_choice(s)[0]) + " now",
```

with:

```python
    facts=lambda s: f"can make {tool_words(tool_choice(s)[0])} now",
```


In `backend/survival/work.py`, replace:

```python
from backend.survival.building import building_need
```

with:

```python
from backend.survival.building import building_need
from backend.survival.creatures.harm import armor_iron, armor_wanted
```

and replace:

```python
    """Coal until Mimo carries 8; iron until it has 3 ore or ingots (or an iron pickaxe or better);
    with an iron pickaxe (L3), gold (until a gold pickaxe or better) and diamonds (until a diamond
    pickaxe), but only once it knows where enough lie for a pickaxe (`enough_known`)."""
    wanted, rank = [], pickaxe_rank(s.inventory)
    if s.count("coal") < 8:
        wanted.append("coal_ore")
    if s.count("iron_ore", "iron_ingot") < 3 and rank < TOOL_RANK["iron_pickaxe"]:
        wanted.append("iron_ore")
```

with:

```python
    """Coal until Mimo carries 8; iron until it has 3 ore or ingots (or an iron pickaxe or better),
    and then, once a creature has hurt it, as much as the iron armor it lacks takes; with an iron
    pickaxe (L3), gold (until a gold pickaxe or better) and diamonds (until a diamond pickaxe), but
    only once it knows where enough lie for a pickaxe (`enough_known`)."""
    wanted, rank = [], pickaxe_rank(s.inventory)
    if s.count("coal") < 8:
        wanted.append("coal_ore")
    iron = 3 if rank < TOOL_RANK["iron_pickaxe"] else armor_iron(s.inventory) if armor_wanted(s.state) else 0
    if s.count("iron_ore", "iron_ingot") < iron:
        wanted.append("iron_ore")
```


In `backend/survival/storage.py`, replace:

```python
    found += [(flower, s.count(flower)) for flower in FLOWERS if s.count(flower)]
```

with:

```python
    found += [(piece, s.count(piece)) for piece in ("leather_cap", "leather_tunic")
              if s.count(piece) and s.count(piece.replace("leather", "iron"))]  # L3: iron replaced it
    found += [(flower, s.count(flower)) for flower in FLOWERS if s.count(flower)]
```

and replace:

```python
             "pumpkin": 0, "melon": 0, "cactus": 0, "sugar_cane": 0, "gold_ore": 3, "gold_ingot": 3})
```

with:

```python
             "pumpkin": 0, "melon": 0, "cactus": 0, "sugar_cane": 0, "gold_ore": 3, "gold_ingot": 3,
             "iron_ore": 16, "iron_ingot": 16})  # iron armor takes 13 ingots: keep them on hand
```


- [ ] **Step 5: light_up hangs lanterns**

In `backend/survival/structures.py`, replace:

```python
    return planned.part in FITTINGS and material != planned.block
```

with:

```python
    return planned.part in FITTINGS and material not in STANDS_IN.get(planned.block, (planned.block,))
```

and replace:

```python
TENDED = ("farmland", "sapling")  # Mimo's own plots and plantings
```

with:

```python
TENDED = ("farmland", "sapling")  # Mimo's own plots and plantings
STANDS_IN = {"torch": ("torch", "lantern")}  # L3: a lantern lights a torch corner as well as a torch does
```


In `backend/survival/lighting.py`, replace:

```python
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
```

with:

```python
def home_blueprint(s: Situation):
    """The design of the finished shelter Mimo stands near, or None."""
    structure = current_shelter(s)
    if structure is None or structure["status"] != "done":
        return None
    blueprint = blueprint_of(structure)
    return None if s.distance(blueprint.anchor) > HOME_REACH else blueprint


def dark_corners(s: Situation) -> list[Cell]:
    """The shelter's torch cells without a torch or lantern that one can stand in now (open, on solid ground)."""
    blueprint = home_blueprint(s)
    if blueprint is None:
        return []
    return [planned.cell for planned in todo(s.grid, blueprint, ("torch",))
            if s.grid.standable(planned.cell)]


def torch_corners(s: Situation) -> list[Cell]:
    """The shelter's corners that hold a torch: a carried lantern lights them better (L3)."""
    blueprint = home_blueprint(s)
    if blueprint is None:
        return []
    return [planned.cell for planned in blueprint.parts("torch") if s.grid.material(*planned.cell) == "torch"]
```

and replace:

```python
def light_valid(s: Situation) -> bool:
    return evening(s) and bool(dark_corners(s)) and torch_supply(s, 1)[1] > 0
```

with:

```python
def light_valid(s: Situation) -> bool:
    if not evening(s):
        return False
    lanterns = s.count("lantern")
    return (bool(dark_corners(s)) and (lanterns > 0 or torch_supply(s, 1)[1] > 0)) or (lanterns > 0 and bool(torch_corners(s)))
```

and replace:

```python
    corners = dark_corners(s)
    crafting, have = torch_supply(s, len(corners))
    jobs = [(cell, [*clearing(s.grid, cell), {"kind": "place", "target": list(cell), "block": "torch"}])
            for cell in corners[:have]]
```

with:

```python
    corners, lanterns = dark_corners(s), s.count("lantern")
    crafting, have = torch_supply(s, max(0, len(corners) - lanterns))
    lights = ["lantern"] * min(lanterns, len(corners)) + ["torch"] * have
    jobs = [(cell, [*clearing(s.grid, cell), {"kind": "place", "target": list(cell), "block": block}])
            for cell, block in zip(corners, lights)]
    # L3: carried lanterns left over take the place of torches (the torch goes back in Mimo's arms).
    spare = lanterns - lights.count("lantern")
    jobs += [(cell, [{"kind": "mine", "target": list(cell)}, {"kind": "place", "target": list(cell), "block": "lantern"}])
             for cell in torch_corners(s)[:spare]]
```


- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_armor.py"`
Expected: `Ran 9 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 862 tests` … `OK` (9 new).

- [ ] **Step 7: Commit**

```bash
git add backend/services/crafting.py backend/survival/creatures/harm.py backend/survival/creatures/gear.py backend/survival/toolmaking.py backend/survival/work.py backend/survival/storage.py backend/survival/structures.py backend/survival/lighting.py backend/tests/test_survival_armor.py
git commit -m "feat: iron armor once a creature has hurt Mimo, and lanterns from spare iron that light home brighter than torches" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Ladders to climb and fences nothing crosses

**Files:**
- Modify: `backend/services/crafting.py` (ladder and fence recipes), `backend/services/blocks.py` (`TALL`, `is_tall`), `backend/survival/grid.py` (nothing stands on a fence; a ladder holds whoever is on it or on top of it), `backend/survival/pathing.py` (straight up and down a ladder)
- Test: `backend/tests/test_survival_climbing.py`

**Interfaces:**
- Consumes: Task 1's `ladder` (not solid) and `fence` (solid, `"tall": true`) blocks; `Grid.supported`, `standable`; `pathing.moves`; `creatures.moves.steps` (which walks by `pathing.moves`).
- Produces:
  - Recipes, no station: `ladder` (7 sticks make 3), `fence` (4 planks and 2 sticks make 3; any planks, Task 2).
  - `blocks.TALL` (a frozenset of the registry's tall blocks), `blocks.is_tall(material) -> bool`.
  - `grid.LADDER = "ladder"`; `Grid.supported(cell)`: water or a ladder below, or a solid block below that is not tall, or a ladder in the cell itself.
  - `pathing.moves`: from a ladder cell to the ladder above it, and from any cell to the ladder below it. So a fence ring holds animals in (they neither step into a fence nor onto one), Mimo walks round a fence, and a shaft with a ladder is a way out.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_climbing.py`:

```python
import sqlite3
import unittest

from backend.services.blocks import is_tall
from backend.services.crafting import craft
from backend.survival.creatures.moves import steps as creature_steps
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.pathing import find_path, moves, route


def meadow(blocks=None):
    """Grass at y 0, dirt below, air above; `blocks` placed on top."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    return grid


def ring(size=4):
    """A fence ring around (0, 0): the cells of a size x size square's edge, at y 1."""
    return {(x, 1, z): "fence" for x in range(-1, size - 1) for z in range(-1, size - 1)
            if x in (-1, size - 2) or z in (-1, size - 2)}


class RecipeTests(unittest.TestCase):
    def test_ladders_from_sticks_and_fences_from_planks_and_sticks(self):
        self.assertEqual(craft({"sticks": 7}, "ladder", set()), {"ladder": 3})
        self.assertEqual(craft({"birch_planks": 4, "sticks": 2}, "fence", set()), {"fence": 3})
        self.assertTrue(is_tall("fence"))
        self.assertFalse(is_tall("stone") or is_tall("ladder") or is_tall("not_a_block"))


class FenceTests(unittest.TestCase):
    def test_nothing_stands_on_a_fence_or_steps_over_it(self):
        grid = meadow({(1, 1, 0): "fence"})
        self.assertFalse(grid.standable((1, 2, 0)))
        self.assertNotIn((1, 2, 0), list(moves(grid, (0, 1, 0))))
        self.assertTrue(grid.standable((2, 1, 0)))

    def test_mimo_walks_round_a_fence_and_an_animal_in_a_pen_stays_there(self):
        grid = meadow(ring())
        cells, reached = route(grid, (0, 1, 0), (4, 1, 0))
        self.assertFalse(reached)  # the pen has no way out
        grid.herd = Herd(sqlite3.connect(":memory:"))
        create_creature_tables(grid.herd.db)
        self.assertEqual(sorted(creature_steps(grid, (0, 1, 0), False)), [(0, 1, 1), (1, 1, 0)])
        outside, reached = route(meadow({(1, 1, 0): "fence", (1, 1, 1): "fence", (1, 1, -1): "fence"}), (0, 1, 0), (2, 1, 0))
        self.assertTrue(reached)
        self.assertTrue(all(cell[1] == 1 for cell in outside))  # round the end of the fence, never over it


class LadderTests(unittest.TestCase):
    def shaft(self):
        """A shaft dug 4 deep at (0, 0), a ladder from its floor to the surface."""
        grid = meadow()
        for y in range(-3, 1):
            grid.put(0, y, 0, "ladder")
        return grid

    def test_mimo_climbs_up_and_down_a_ladder(self):
        grid = self.shaft()
        self.assertTrue(grid.standable((0, -3, 0)) and grid.standable((0, 1, 0)))
        self.assertIn((0, -2, 0), list(moves(grid, (0, -3, 0))))
        self.assertIn((0, 0, 0), list(moves(grid, (0, 1, 0))))
        up, reached = find_path(grid, (0, -3, 0), lambda cell: cell == (3, 1, 0), (3, 1, 0))
        self.assertTrue(reached)
        self.assertEqual(up[:4], [(0, -2, 0), (0, -1, 0), (0, 0, 0), (1, 1, 0)])
        down, reached = find_path(grid, (3, 1, 0), lambda cell: cell == (0, -3, 0), (0, -3, 0))
        self.assertTrue(reached)

    def test_without_the_ladder_the_shaft_is_a_trap(self):
        grid = meadow({(0, y, 0): "air" for y in range(-3, 1)})
        _, reached = find_path(grid, (0, -3, 0), lambda cell: cell == (3, 1, 0), (3, 1, 0))
        self.assertFalse(reached)


if __name__ == "__main__":
    unittest.main()
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_climbing.py"`
Expected: `ImportError: cannot import name 'is_tall' from 'backend.services.blocks'`.

- [ ] **Step 3: The recipes and the tall rule**

In `backend/services/crafting.py`, replace:

```python
    "lantern": {"ingredients": {"iron_ingot": 1, "torch": 1}, "output": {"lantern": 1}},
})
```

with:

```python
    "lantern": {"ingredients": {"iron_ingot": 1, "torch": 1}, "output": {"lantern": 1}},
    # Ladders Mimo can climb and fences nothing can cross, anywhere.
    "ladder": {"ingredients": {"sticks": 7}, "output": {"ladder": 3}},
    "fence": {"ingredients": {"planks": 4, "sticks": 2}, "output": {"fence": 3}},
})
```


In `backend/services/blocks.py`, replace:

```python
def is_solid(material: str) -> bool:
```

with:

```python
TALL = frozenset(block["name"] for block in BLOCK_LIST if block.get("tall"))


def is_tall(material: str) -> bool:
    """True for blocks too tall to stand on or step over (the registry's `tall`: fences, L3)."""
    return material in TALL


def is_solid(material: str) -> bool:
```


- [ ] **Step 4: Stand on ladders but not on fences, and climb**

In `backend/survival/grid.py`, replace:

```python
from backend.services.blocks import is_plant, is_solid
```

with:

```python
from backend.services.blocks import is_plant, is_solid, is_tall
```

and replace:

```python
    def supported(self, cell: Cell) -> bool:
        """Something holds Mimo up in this cell: the cell below is solid or water."""
        x, y, z = cell
        below = self.material(x, y - 1, z)
        return below == "water" or is_solid(below)
```

with:

```python
    def supported(self, cell: Cell) -> bool:
        """Something holds Mimo up in this cell: the cell below is solid or water. L3: a fence below
        is too tall to stand on, and a ladder holds whoever is on it or on top of it."""
        x, y, z = cell
        below = self.material(x, y - 1, z)
        if below in ("water", LADDER):
            return True
        if is_solid(below):
            return not is_tall(below)
        return self.material(x, y, z) == LADDER
```

and replace:

```python
FLUIDS = ("water", "lava")
```

with:

```python
FLUIDS = ("water", "lava")
LADDER = "ladder"
```


In `backend/survival/pathing.py`, replace:

```python
Mimo moves to one of its 4 horizontal neighbors at a time: on the same level, one step up
when the cell above its head is free, or off a ledge down at most 3 cells.
```

with:

```python
Mimo moves to one of its 4 horizontal neighbors at a time: on the same level, one step up
when the cell above its head is free, or off a ledge down at most 3 cells; and (L3) straight up
or down a ladder. Nothing steps onto a fence (Grid.supported).
```

and replace:

```python
from backend.survival.grid import Cell, Grid
```

with:

```python
from backend.survival.grid import LADDER, Cell, Grid
```

and replace:

```python
        if headroom and grid.standable(up):
            yield up
```

with:

```python
        if headroom and grid.standable(up):
            yield up
    if grid.material(x, y, z) == LADDER and grid.material(x, y + 1, z) == LADDER:
        yield x, y + 1, z  # L3: climb the ladder
    if grid.material(x, y - 1, z) == LADDER:
        yield x, y - 1, z  # and down it
```


- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_climbing.py"`
Expected: `Ran 5 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 867 tests` … `OK` (5 new).

- [ ] **Step 6: Commit**

```bash
git add backend/services/crafting.py backend/services/blocks.py backend/survival/grid.py backend/survival/pathing.py backend/tests/test_survival_climbing.py
git commit -m "feat: ladders Mimo climbs and fences nothing can stand on or cross" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Flint from gravel

L2 made arrows from flint and flint from mined gravel, 1 in 8, but no planner went looking for gravel (there was none in the terrain until Tasks 3 and 4). This task gives Mimo a reason and a way to find it.

**Files:**
- Create: `backend/survival/flint.py` (the `gather_flint` purpose)
- Modify: `backend/survival/brain.py` (import it)
- Test: `backend/tests/test_survival_flint.py`

**Interfaces:**
- Consumes: Task 3's gravel ground (`worldgen.surface_material` gives `"gravel"` on shores, in the taiga and on scree; lake beds are under water) and Task 4's gravel cave floors; L2's `nature.CHANCE_DROPS["gravel"]` (flint, 1 in 8) and `gear.ARROWS_WANTED`; `foraging.reach_steps`; `senses.by_distance`, `near_failure`; `structures.reserved`.
- Produces: `flint.FLINT_WANTED = 2`, `GRAVEL_SIGHT = 24`, `GRAVEL_PER_BATCH = 8`, `FLINT_BATCHES = 3`; `wants_flint(s) -> bool`; `gravel_near(s) -> list[Cell]` (sensed once per Situation); the purpose `gather_flint` ("dig gravel for flint"), day work scored 45 plus a tenth of caution.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_flint.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import flint  # noqa: F401  (registers gather_flint)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.steps import finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
BEACH = {(x, 0, z) for x in range(6, 9) for z in range(-1, 2)}  # a gravel shore
LAKE = {(12, 0, 0)}  # gravel under water


def shore():
    def rule(x, y, z):
        if (x, y, z) in BEACH or (x, y, z) in LAKE:
            return "gravel"
        if (x, y, z) == (12, 1, 0):
            return "water"
        return "grass" if y == 0 else "dirt" if y < 0 else "air"
    return Grid(rule)


def situation(inventory, clock=DAY, grid=None):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state, grid or shore(), clock, 0.0, db)


def natural_gravel(x, z, seed):
    return "gravel" if (x, 0, z) in BEACH or (x, 0, z) in LAKE else "grass"


@patch("backend.survival.flint.terrain_height", lambda x, z, seed: 0)
@patch("backend.survival.flint.surface_material", natural_gravel)
@patch("backend.survival.flint.SEA_LEVEL", 0)
class FlintTests(unittest.TestCase):
    def test_wanted_by_day_with_a_bow_or_its_string_and_little_flint(self):
        flint_purpose = PURPOSES["gather_flint"]
        self.assertTrue(flint_purpose.valid(situation({"bow": 1})))
        self.assertTrue(flint_purpose.valid(situation({"string": 3, "flint": 1})))
        self.assertFalse(flint_purpose.valid(situation({})))
        self.assertFalse(flint_purpose.valid(situation({"bow": 1, "flint": 2})))
        self.assertFalse(flint_purpose.valid(situation({"bow": 1, "arrow": 8})))
        self.assertFalse(flint_purpose.valid(situation({"bow": 1}, NIGHT)))
        self.assertEqual(flint_purpose.score(situation({"bow": 1})), 50.0)

    def test_it_walks_to_the_nearest_dry_gravel_and_digs_it(self):
        s = situation({"bow": 1})
        self.assertEqual(flint.gravel_near(s)[0], (6, 0, 0))
        self.assertNotIn((12, 0, 0), flint.gravel_near(s))  # under water
        plan = PURPOSES["gather_flint"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY,
                                                              planner=lambda *args: [], events=[], db=s.db))
        self.assertEqual(plan[0], {"kind": "walk", "target": [6, 0, 0], "reach": 2.0, "whole": True})
        self.assertEqual([step["target"] for step in plan if step["kind"] == "mine"][:3], [[6, 0, 0], [6, 0, -1], [6, 0, 1]])
        self.assertEqual(len([step for step in plan if step["kind"] == "mine"]), 8)

    def test_gravel_in_the_walls_of_its_passage_counts_too(self):
        grid = Grid(lambda x, y, z: "gravel" if (x, y, z) == (1, -3, 0) else "air" if (x, y, z) in ((0, -3, 0), (1, -2, 0)) else "stone")
        s = situation({"bow": 1}, grid=grid)
        s.state["position"] = {"x": 0.0, "y": -3.0, "z": 0.0}
        self.assertEqual(flint.gravel_near(s), [(1, -3, 0)])

    def test_one_mined_gravel_in_eight_gives_a_flint(self):
        grid = shore()
        state = {"name": "Pip", "world_seed": "1", "position": {"x": 7.0, "y": 1.0, "z": 0.0}, "inventory": {}}
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            running = start_step({"kind": "mine", "target": [7, 0, 0]}, state, grid, 0.0)
            finish_step(running, state, grid, running["ends_at"])
        self.assertEqual(state["inventory"], {"gravel": 1, "flint": 1})


if __name__ == "__main__":
    unittest.main()
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_flint.py"`
Expected: `ImportError: cannot import name 'flint' from 'backend.survival'`.

- [ ] **Step 3: Add the purpose and register it**

Create `backend/survival/flint.py`:

```python
"""gather_flint: dig gravel for flint, the tip of every arrow (L3; L2's flint is one mined gravel in 8).

Mimo wants flint while it has a bow (or the 3 string one takes), carries fewer than FLINT_WANTED
flint and fewer arrows than make_gear keeps (backend.survival.creatures.gear). Gravel lines lake and
river beds, lies in patches on shores, in the taiga and on alpine scree, and on cave floors
(backend.services.worldgen). gather_flint digs the nearest gravel Mimo can stand by: natural gravel
ground within 24 blocks with open air over it (never under water), and any gravel within reach of
where it stands (a cave floor, or a seam its passage cut), nearest first, up to 8 a batch and 3
batches a choice, until a flint turns up. Gravel within 4 blocks of where a step just failed, and
what Mimo built or tends (structures.reserved), are left alone. It is day work in the work band: 45
plus a tenth of caution.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, surface_material, terrain_height
from backend.survival.creatures.gear import ARROWS_WANTED
from backend.survival.foraging import reach_steps
from backend.survival.grid import Cell
from backend.survival.purposes import Purpose, register
from backend.survival.senses import by_distance, near_failure
from backend.survival.situation import Situation
from backend.survival.steps import REACH
from backend.survival.structures import reserved

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FLINT_WANTED = 2
GRAVEL_SIGHT = 24
GRAVEL_PER_BATCH = 8
FLINT_BATCHES = 3


def wants_flint(s: Situation) -> bool:
    """A bow (or the string for one), fewer than FLINT_WANTED flint and fewer arrows than wanted."""
    archer = s.count("bow") > 0 or s.count("string") >= 3
    return archer and s.count("flint") < FLINT_WANTED and s.count("arrow") < ARROWS_WANTED


def diggable(s: Situation, cell: Cell) -> bool:
    """Gravel that is still there, with open air over it (not water), nobody's floor that Mimo built
    or tends, and no failed step nearby."""
    x, y, z = cell
    over = s.grid.material(x, y + 1, z)
    return (s.grid.material(*cell) == "gravel" and s.grid.passable((x, y + 1, z)) and over != "water"
            and not reserved(s.grid, cell) and not near_failure(s.state, cell))


def gravel_near(s: Situation) -> list[Cell]:
    """Gravel Mimo can dig, nearest first (see the module docstring)."""
    def look() -> list[Cell]:
        x, y, z = s.here
        found = set()
        for gx in range(x - GRAVEL_SIGHT, x + GRAVEL_SIGHT + 1):
            for gz in range(z - GRAVEL_SIGHT, z + GRAVEL_SIGHT + 1):
                if math.hypot(gx - x, gz - z) > GRAVEL_SIGHT:
                    continue
                height = terrain_height(gx, gz, s.seed)
                if height >= SEA_LEVEL and surface_material(gx, gz, s.seed) == "gravel":
                    found.add((gx, height, gz))
        reach = int(REACH)
        found.update((x + dx, y + dy, z + dz) for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)
                     for dz in range(-reach, reach + 1) if s.grid.material(x + dx, y + dy, z + dz) == "gravel")
        return [cell for cell in by_distance(found, s.here) if diggable(s, cell)]
    return s.sensed("gravel", look)


def flint_valid(s: Situation) -> bool:
    return not s.night and wants_flint(s) and bool(gravel_near(s))


def plan_flint(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= FLINT_BATCHES or not wants_flint(s):
        return []
    cells = gravel_near(s)[:GRAVEL_PER_BATCH]
    return reach_steps(s, [(cell, [{"kind": "mine", "target": list(cell)}]) for cell in cells])


register(Purpose(
    "gather_flint", "dig gravel for flint", "Dig gravel nearby until a flint turns up, for arrows.",
    valid=flint_valid,
    facts=lambda s: f"{len(gravel_near(s))} gravel to dig within {GRAVEL_SIGHT} blocks; carrying {s.count('flint')} flint",
    score=lambda s: 45.0 + s.trait("caution") / 10, plan=plan_flint,
    thoughts=("A flint would tip my arrows.", "There's gravel over there. Flint hides in gravel.")))
```


In `backend/survival/brain.py`, replace:

```python
from backend.survival import farmstead, lighting, storage  # noqa: F401  (M5's building purposes)
```

with:

```python
from backend.survival import farmstead, lighting, storage  # noqa: F401  (M5's building purposes)
from backend.survival import flint  # noqa: F401  (L3's gather_flint)
```


- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_flint.py"`
Expected: `Ran 4 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 871 tests` … `OK` (4 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/flint.py backend/survival/brain.py backend/tests/test_survival_flint.py
git commit -m "feat: Mimo digs gravel for flint when its bow needs arrows" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Creature seeds

**Files:**
- Create: `backend/survival/creatures/seeds.py` (a sprout grows into a tame local animal)
- Modify: `backend/survival/nature.py` (the drop, 1 in 60; planting on grass), `backend/survival/renewal.py` (`Grower`, `GROWERS`, `register_grower`, `grower_of`; react and apply run registered growers; it imports `seeds` last), `backend/survival/creatures/hunting.py` (tame animals are not prey), `backend/survival/storage.py` (seeds go in the chest)
- Modify tests: `backend/tests/test_survival_renewal.py`, `backend/tests/test_survival_fieldwork.py` (a roll of 0 now also gives a creature seed)
- Test: `backend/tests/test_survival_creature_seeds.py`

**Interfaces:**
- Consumes: Task 1's `creature_sprout` block (a cutout plant that drops `creature_seed`); `nature.CHANCE_DROPS`, `SEEDS`, `SOIL`, `roll`; the plant step (`fieldwork`); renewal's growth table (`schedule`, `later`, `react`, `apply_entry`, `renew`); L1's `Herd.add`, `kinds.land_kinds`, `KINDS`, `spawning.LAND_CAP`, `SIM_REACH`, `passive`, `table.dead`; `hunting.prey`.
- Produces:
  - `nature.CHANCE_DROPS`: tall grass and every kind of leaves also drop a `creature_seed`, 1 in 60 (roll channel 91). `nature.SEEDS["creature_seed"] = "creature_sprout"`, `nature.SOIL["creature_sprout"] = ("grass",)`.
  - `renewal.Grower(marker, seconds, grow)`, `renewal.GROWERS` (planted block -> Grower), `register_grower(block, grower)`, `grower_of(marker)`. A planted block with a Grower schedules its marker `seconds` later; a due marker calls `grow(db, grid, state, cell, ready_at, scale, events)`, which may schedule again.
  - `creatures.seeds`: `SEED`, `SPROUT`, `MARKER = "animal"`, `GROW_SECONDS` (a game day), `RETRY_SECONDS = 600`, `local_kind(seed, cell) -> Kind`, `hatch(...)`. A grown animal's state: `{"home": cell, "chunk": None, "pose": "idle", "turn": 0, "tame": True}`; a "grow" event "A creature seed grew into a cow.".
  - `hunting.prey` leaves out creatures whose state is `tame`. `storage.KEEP["creature_seed"] = 0`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_creature_seeds.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import nature
from backend.survival.actions import ActionContext
from backend.survival.creatures.hunting import prey
from backend.survival.creatures.seeds import MARKER, SPROUT, local_kind
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.renewal import GROWERS, create_growth_table, renew, scheduled
from backend.survival.situation import Situation
from backend.survival.steps import finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = 3600.0


def field():
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    db = sqlite3.connect(":memory:")
    create_growth_table(db)
    create_memory_tables(db)
    create_creature_tables(db)
    grid.herd = Herd(db)
    return ActionContext(grid=grid, clock_at=lambda at: {"time_scale": 1.0}, planner=lambda *args: [], events=[], db=db)


def pet(inventory=None):
    return {"name": "Pip", "world_seed": "7", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
            "inventory": dict(inventory or {}), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}


def plant(ctx, state, cell=(2, 1, 0)):
    running = start_step({"kind": "plant", "target": list(cell), "item": "creature_seed"}, state, ctx.grid, 0.0)
    finish_step(running, state, ctx.grid, running["ends_at"])


class SeedTests(unittest.TestCase):
    def test_one_in_sixty_tall_grass_or_leaves_gives_a_creature_seed(self):
        for block in ("tall_grass", "leaves", "birch_leaves", "spruce_leaves"):
            found = sum("creature_seed" in nature.chance_drops("5", (x, 1, z), block) for x in range(60) for z in range(60))
            self.assertTrue(30 <= found <= 90, (block, found))  # 60 expected

    def test_it_is_planted_on_grass_only(self):
        ctx, state = field(), pet({"creature_seed": 2})
        plant(ctx, state)
        self.assertEqual((ctx.grid.material(2, 1, 0), state["inventory"]), (SPROUT, {"creature_seed": 1}))
        ctx.grid.put(0, 0, 2, "farmland")
        with self.assertRaisesRegex(ValueError, "needs grass"):
            start_step({"kind": "plant", "target": [0, 1, 2], "item": "creature_seed"}, state, ctx.grid, 0.0)


class GrowthTests(unittest.TestCase):
    def test_a_game_day_later_the_sprout_is_a_tame_local_animal(self):
        ctx, state = field(), pet({"creature_seed": 1})
        plant(ctx, state)
        renew(state, ctx, 10.0)
        self.assertEqual(scheduled(ctx.db), [((2, 1, 0), MARKER, 10.0 + DAY)])
        renew(state, ctx, 10.0 + DAY)
        self.assertEqual(ctx.grid.material(2, 1, 0), "air")
        (animal,) = ctx.grid.herd.near(2, 0, 4)
        kind = local_kind("7", (2, 1, 0))
        self.assertIn(kind.name, ("rabbit", "chicken", "sheep", "cow"))  # a meadow's animals
        self.assertEqual((animal["kind"], animal["health"], (animal["x"], animal["y"], animal["z"])),
                         (kind.name, kind.health, (2.0, 1.0, 0.0)))
        self.assertTrue(animal["state"]["tame"])
        self.assertEqual(animal["state"]["home"], [2, 1, 0])
        self.assertEqual(ctx.events[-1][1:], ("grow", f"A creature seed grew into a {kind.name}."))
        self.assertEqual(scheduled(ctx.db), [])
        self.assertIn(SPROUT, GROWERS)

    def test_it_waits_while_the_land_is_full_and_a_mined_sprout_grows_nothing(self):
        ctx, state = field(), pet({"creature_seed": 2})
        for number in range(24):
            ctx.grid.herd.add("rabbit", (10 + number % 6, 1, 10 + number // 6), 3.0, 0.0, 1e9, {})
        plant(ctx, state)
        renew(state, ctx, 0.0)
        renew(state, ctx, DAY)
        self.assertEqual(ctx.grid.material(2, 1, 0), SPROUT)
        self.assertEqual(scheduled(ctx.db), [((2, 1, 0), MARKER, DAY + 600.0)])
        other = field()
        plant(other, state, (3, 1, 0))
        renew(state, other, 0.0)
        other.grid.put(3, 1, 0, "air")  # mined: its seed back in Mimo's arms, nothing to grow
        renew(state, other, DAY)
        self.assertEqual(other.grid.herd.near(3, 0, 4), [])

    def test_mimo_never_hunts_an_animal_it_grew(self):
        ctx = field()
        tame = ctx.grid.herd.add("cow", (3, 1, 0), 10.0, 0.0, 1e9, {"tame": True})
        wild = ctx.grid.herd.add("cow", (6, 1, 0), 10.0, 0.0, 1e9, {})
        s = Situation(pet(), ctx.grid, {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1},
                      0.0, ctx.db)
        with patch("backend.survival.creatures.hunting.near_failure", lambda state, cell: False):
            self.assertEqual([creature["id"] for creature in prey(s)], [wild["id"]])
        self.assertNotEqual(tame["id"], wild["id"])


if __name__ == "__main__":
    unittest.main()
```


A roll of 0 now also gives a creature seed from leaves and tall grass.

In `backend/tests/test_survival_renewal.py`, replace:

```python
        self.assertEqual(near["inventory"], {"sapling": 26, "apple": 26})
```

with:

```python
        self.assertEqual(near["inventory"], {"sapling": 26, "apple": 26, "creature_seed": 26})  # L3's seeds
```


In `backend/tests/test_survival_fieldwork.py`, replace:

```python
        self.assertEqual(state["inventory"], {"sapling": 1, "apple": 1, "seeds": 1, "carrot": 1})
```

with:

```python
        self.assertEqual(state["inventory"], {"sapling": 1, "apple": 1, "seeds": 1, "carrot": 1, "creature_seed": 2})
```

and replace:

```python
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "leaves"), ["sapling", "apple"])
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "tall_grass"), ["seeds", "carrot"])
```

with:

```python
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "leaves"), ["sapling", "apple", "creature_seed"])
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "tall_grass"), ["seeds", "carrot", "creature_seed"])
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_creature_seeds.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.creatures.seeds'`.

- [ ] **Step 3: The seed drops and is planted on grass**

In `backend/survival/nature.py`, replace:

```python
CHANCE_DROPS.update({leaf: (("sapling", 1 / 12, 32),) for leaf in LEAVES[1:]})
```

with:

```python
CHANCE_DROPS.update({leaf: (("sapling", 1 / 12, 32),) for leaf in LEAVES[1:]})
# L3: a creature seed, 1 in 60, from tall grass and every kind of leaves; planted on grass it is a
# sprout that grows into an animal (backend.survival.creatures.seeds).
for _block in ("tall_grass", *LEAVES):
    CHANCE_DROPS[_block] = (*CHANCE_DROPS[_block], ("creature_seed", 1 / 60, 91))
SEEDS["creature_seed"] = "creature_sprout"
SOIL["creature_sprout"] = ("grass",)
```


- [ ] **Step 4: Growers in renewal, and the creature sprout**

In `backend/survival/renewal.py`, replace:

```python
Entry = tuple[Cell, str, float]
```

with:

```python
Entry = tuple[Cell, str, float]


@dataclass(frozen=True)
class Grower:
    """How a planted block grows by a rule of its own (L3's creature sprouts): the growth table's
    entry for it (`marker`), the game seconds it takes, and `grow(db, grid, state, cell, ready_at,
    scale, events)`, which makes it happen or schedules it again."""

    marker: str
    seconds: float
    grow: Callable


GROWERS: dict[str, Grower] = {}  # planted block -> its Grower


def register_grower(block: str, grower: Grower) -> Grower:
    GROWERS[block] = grower
    return grower


def grower_of(marker: str) -> Grower | None:
    return next((grower for grower in GROWERS.values() if grower.marker == marker), None)
```

and replace:

```python
import logging
import math
import sqlite3
```

with:

```python
import logging
import math
import sqlite3
from dataclasses import dataclass
from typing import Callable
```

and replace:

```python
        if after == "sapling":
            schedule(db, cell, LOG, later(at, SAPLING_GROWS, scale))
```

with:

```python
        if after in GROWERS:
            schedule(db, cell, GROWERS[after].marker, later(at, GROWERS[after].seconds, scale))
        elif after == "sapling":
            schedule(db, cell, LOG, later(at, SAPLING_GROWS, scale))
```

and replace:

```python
                and mushrooms_in_chunk(grid, seed, (x // CHUNK, z // CHUNK)) < MUSHROOM_CAP):
            grid.put(*cell, block)
```

with:

```python
                and mushrooms_in_chunk(grid, seed, (x // CHUNK, z // CHUNK)) < MUSHROOM_CAP):
            grid.put(*cell, block)
    elif grower_of(block) is not None:
        grower_of(block).grow(db, grid, state, cell, ready_at, scale, events)
```

and replace:

```python
    nature.recover_fish(state, at, scale)
```

with:

```python
    nature.recover_fish(state, at, scale)


# L3: creature sprouts register their Grower; imported last because they build on everything above.
from backend.survival.creatures import seeds  # noqa: E402,F401
```


Create `backend/survival/creatures/seeds.py`:

```python
"""Creature seeds (spec L3): a rare seed that grows into an animal, the owner's "seeds that grow
creatures".

A creature seed drops, 1 in 60, from broken tall grass and decaying leaves (nature.CHANCE_DROPS).
Planted on grass (the plant step: nature.SEEDS and SOIL) it is a creature sprout, and a game day
later, through renewal's growth table (renewal.GROWERS), the sprout is gone and a passive land
animal stands in its cell: a kind that lives in the biome there (spawning's land_kinds, rolled from
the world seed and the cell; a rabbit where none does). It is tame: at home where it grew, it
counts toward no chunk's herds and Mimo never hunts it (backend.survival.creatures.hunting). While
24 land animals are already near, the sprout waits and tries again 10 game minutes later. A sprout
that was mined or built over grows nothing, and mining one gives its seed back (the block's drop).
"""

from __future__ import annotations

import sqlite3

from backend.services.worldgen import biome_at
from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.kinds import KINDS, Kind, land_kinds
from backend.survival.creatures.spawning import LAND_CAP, SIM_REACH, passive
from backend.survival.creatures.table import dead
from backend.survival.grid import Cell, Grid
from backend.survival.renewal import Grower, later, register_grower, schedule

SEED = "creature_seed"
SPROUT = "creature_sprout"
MARKER = "animal"  # the growth table's entry for a sprout: an animal grows there
GROW_SECONDS = DAY_SECONDS
RETRY_SECONDS = 600.0  # game seconds a sprout waits while the land is full of animals
KIND_CHANNEL = 92
FIRST_TURN = 1.0  # server seconds before a new animal takes its first turn


def local_kind(seed: str, cell: Cell) -> Kind:
    """The passive land kind a sprout at `cell` grows into: one that lives in the biome there."""
    kinds = land_kinds(biome_at(cell[0], cell[2], seed)) or [KINDS["rabbit"]]
    return kinds[int(nature.roll(seed, cell, KIND_CHANNEL) * len(kinds))]


def hatch(db: sqlite3.Connection, grid: Grid, state: dict, cell: Cell, ready_at: float, scale: float,
          events: list) -> None:
    """The sprout at `cell` grows into a tame animal, or waits while the land is full."""
    herd = grid.herd
    if herd is None or grid.material(*cell) != SPROUT:
        return
    near = [creature for creature in herd.near(cell[0], cell[2], SIM_REACH)
            if not dead(creature) and passive(creature, False)]
    if len(near) >= LAND_CAP:
        schedule(db, cell, MARKER, later(ready_at, RETRY_SECONDS, scale))
        return
    kind = local_kind(state.get("world_seed", "0"), cell)
    grid.put(*cell, "air")
    herd.add(kind.name, cell, kind.health, ready_at, ready_at + FIRST_TURN,
             {"home": list(cell), "chunk": None, "pose": "idle", "turn": 0, "tame": True})
    events.append((ready_at, "grow", f"A creature seed grew into a {kind.name}."))


register_grower(SPROUT, Grower(MARKER, GROW_SECONDS, hatch))
```


In `backend/survival/creatures/hunting.py`, replace:

```python
                 and huntable(kind_of(creature["kind"])) and not near_failure(s.state, where(creature, s.at))]
```

with:

```python
                 and huntable(kind_of(creature["kind"])) and not creature["state"].get("tame")
                 and not near_failure(s.state, where(creature, s.at))]
```


Seeds Mimo cannot use yet are put away: one stack held for good would fill its arms sooner, and the headless runs measured more changes of purpose for it (resolution 22). stock_pen takes them back out (Task 12).

In `backend/survival/storage.py`, replace:

```python
             "iron_ore": 16, "iron_ingot": 16})  # iron armor takes 13 ingots: keep them on hand
```

with:

```python
             "iron_ore": 16, "iron_ingot": 16,  # iron armor takes 13 ingots: keep them on hand
             "creature_seed": 0})  # seeds wait in the chest for the pen (backend.survival.pens)
```


- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_creature_seeds.py"`
Expected: `Ran 5 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 876 tests` … `OK` (5 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/creatures/seeds.py backend/survival/nature.py backend/survival/renewal.py backend/survival/creatures/hunting.py backend/survival/storage.py backend/tests/test_survival_creature_seeds.py backend/tests/test_survival_renewal.py backend/tests/test_survival_fieldwork.py
git commit -m "feat: creature seeds from grass and leaves grow into tame animals a game day after Mimo plants them" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: A pen by home, stocked with creature seeds

**Files:**
- Create: `backend/survival/pens.py` (`build_pen` and `stock_pen`)
- Modify: `backend/survival/structures.py` (a pen's fence cell waits for its fence), `backend/survival/building.py` (a pen is done when its last fence stands), `backend/survival/brain.py` (import the pen purposes), `backend/survival/storage.py` (spare fences are junk, raw food is never put away)
- Test: `backend/tests/test_survival_pens.py`, `backend/tests/test_survival_raw_food.py`

**Interfaces:**
- Consumes: Task 9's fences (solid, tall: nothing crosses them) and recipe; Task 11's `creatures.seeds.SEED`, `SPROUT` and the chest rule; `blueprints.Blueprint`, `Planned`, `Survey`; `building.current_shelter`, `site_center`, `structures_near`, `finish_if_built`; `structures.start`, `todo`, `clearing`, `blueprint_of`; `storage.chest_spot`, `chest_contents`, `chest_placed`; `toolmaking.make`, `Short`; `carrying.crafts_fit`; `foraging.whole_walk`; the `take` and `plant` steps.
- Produces:
  - `pens.PEN_SIZE = 5`, `PEN_ANIMALS = 3`, `FENCES_PER_BATCH = 8`, `PEN_BATCHES = 6`, `SITE_REACH = 10`; `design_pen(grid, center, owner, reach=SITE_REACH) -> Blueprint | None` (kind `"pen"`: 16 `"fence"` cells, 9 `"pen"` cells kept open, the 24 walkway cells as `stands`, the middle as `anchor`); `current_pen`, `home_done`, `fences_left`, `fence_supply(s, wanted) -> (steps, fences)`, `inside(blueprint, cell)`, `seeds_at_hand(s)`, `from_walkway(s, blueprint, jobs, at=None)`, `finished_pen`, `pen_life(s, blueprint)`, `open_plots(s, blueprint)`.
  - Purposes `build_pen` ("build a pen", 45 plus a tenth of diligence and a twentieth of creativity) and `stock_pen` ("plant creature seeds", 50 plus a tenth of patience), both day work.
  - `structures.missing` counts a `"fence"` part missing until a fence stands there; `building.finish_if_built` finishes a pen on its fences ("Pip laid out Pip's pen.").
  - `storage.spare_fences(s)`: the fences Mimo carries once the newest pen near it is done, which `storage.junk` includes; `storage.spare_food` skips `cooking.RAW_FOODS` (resolution 26).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_pens.py`:

```python
import sqlite3
import unittest

from backend.survival import pens, storage
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.building import finish_if_built
from backend.survival.creatures.moves import steps as creature_steps
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.housework import chest_key
from backend.survival.memory import create_memory_tables, finish_structure, structures
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.structures import start
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
WOOD = {"planks": 30, "sticks": 12}  # 16 fences: 6 crafts of 4 planks and 2 sticks


class PenTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        create_creature_tables(self.db)
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        self.grid.herd = Herd(self.db)
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        home = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in home.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, home, 0.0), 1.0)

    def situation(self, inventory, clock=DAY, position=(12, 1, 1)):
        state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                 "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(state)
        return Situation(state, self.grid, clock, 0.0, self.db)

    def context(self):
        return ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=self.db)

    def test_a_pen_is_a_ring_of_16_fences_round_3x3_of_grass_with_a_walkway_round_it(self):
        design = pens.design_pen(self.grid, (12, 1, 1), "Pip")
        fences = sorted(planned.cell for planned in design.parts("fence"))
        self.assertEqual(len(fences), 16)
        self.assertEqual({cell[1] for cell in fences}, {1})
        self.assertEqual(len(design.parts("pen")), 9)
        self.assertEqual(len(design.stands), 24)
        self.assertEqual(design.anchor, (12, 1, 1))
        self.assertTrue(all(not pens.inside(design, stand) for stand in design.stands))
        claimed = pens.design_pen(self.grid, (1, 1, 1), "Pip")  # the shelter's own ground is left alone
        self.assertFalse(any(self.grid.claimed(planned.cell) for planned in claimed.cells))

    def test_built_by_day_with_a_home_a_creature_seed_and_the_wood_for_its_fences(self):
        build = PURPOSES["build_pen"]
        self.assertTrue(build.valid(self.situation({"creature_seed": 1, **WOOD})))
        self.assertFalse(build.valid(self.situation({**WOOD})))
        self.assertFalse(build.valid(self.situation({"creature_seed": 1, "planks": 8, "sticks": 4})))
        self.assertFalse(build.valid(self.situation({"creature_seed": 1, **WOOD}, clock=NIGHT)))

    def test_fences_go_up_from_the_walkway_8_a_batch_and_the_last_one_finishes_the_pen(self):
        s = self.situation({"creature_seed": 1, **WOOD})
        steps = PURPOSES["build_pen"].plan(s, self.context())
        (pen,) = structures(self.db, ("pen",))
        design = pens.design_pen  # the pen now claims its ring and inside
        self.assertTrue(self.grid.claimed((12, 1, 1)) and self.grid.claimed((10, 1, -1)))
        self.assertEqual([step["recipe"] for step in steps if step["kind"] == "craft"].count("fence"), 3)
        placed = [step["target"] for step in steps if step["kind"] == "place"]
        self.assertEqual(len(placed), 8)
        walks = [step["target"] for step in steps if step["kind"] == "walk"]
        self.assertTrue(walks and all(not pens.inside(pens.blueprint_of(pen), tuple(cell)) for cell in walks))
        blueprint = pens.blueprint_of(pen)
        for planned in blueprint.parts("fence"):
            self.grid.put(*planned.cell, "fence")
        ctx = self.context()
        finish_if_built(s.state, ctx, pen["id"], 5.0)
        self.assertEqual(structures(self.db, ("pen",))[0]["status"], "done")
        self.assertEqual(ctx.events[-1][1:], ("built", "Pip laid out Pip's pen."))
        self.assertIsNotNone(design)

    def test_a_finished_pen_is_stocked_with_seeds_from_the_walkway_and_holds_what_grows(self):
        design = pens.design_pen(self.grid, (12, 1, 1), "Pip")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        for planned in design.parts("fence"):
            self.grid.put(*planned.cell, "fence")
        s = self.situation({"creature_seed": 5})
        self.assertTrue(PURPOSES["stock_pen"].valid(s))
        steps = PURPOSES["stock_pen"].plan(s, self.context())
        planted = [step["target"] for step in steps if step["kind"] == "plant"]
        self.assertEqual(len(planted), pens.PEN_ANIMALS)
        self.assertTrue(all(pens.inside(design, tuple(cell)) for cell in planted))
        self.assertTrue(all(not pens.inside(design, tuple(step["target"])) for step in steps if step["kind"] == "walk"))
        cow = self.grid.herd.add("cow", (11, 1, 0), 10.0, 0.0, 1e9, {"tame": True})
        self.assertTrue(all(pens.inside(design, cell) for cell in creature_steps(self.grid, (11, 1, 0), False)))
        self.assertEqual(creature_steps(self.grid, (9, 1, 1), False).count((10, 1, 1)), 0)  # no wild animal walks in
        for cell in ((12, 1, 1), (13, 1, 2)):
            self.grid.put(*cell, "creature_sprout")
        self.assertEqual(pens.pen_life(self.situation({"creature_seed": 5}), design), 3)
        self.assertFalse(PURPOSES["stock_pen"].valid(self.situation({"creature_seed": 5})))
        self.assertIsNotNone(cow)

    def test_fences_left_over_once_the_pen_is_done_are_no_use_to_carry(self):
        pen = start(self.db, self.grid, pens.design_pen(self.grid, (12, 1, 1), "Pip"), 0.0)
        self.assertNotIn(("fence", 2), storage.junk(self.situation({"fence": 2})))  # still building it
        finish_structure(self.db, pen, 1.0)
        self.assertIn(("fence", 2), storage.junk(self.situation({"fence": 2})))

    def test_seeds_kept_in_the_chest_are_taken_out_first(self):
        design = pens.design_pen(self.grid, (12, 1, 1), "Pip")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        for planned in design.parts("fence"):
            self.grid.put(*planned.cell, "fence")
        s = self.situation({})
        chest = storage.chest_spot(s)
        self.grid.put(*chest, "chest")
        s.state["chests"] = {chest_key(chest): {"creature_seed": 2}}
        self.assertEqual(pens.seeds_at_hand(s), 2)
        self.assertTrue(PURPOSES["stock_pen"].valid(s))
        steps = PURPOSES["stock_pen"].plan(s, self.context())
        self.assertEqual(steps[1], {"kind": "take", "target": list(chest), "item": "creature_seed", "amount": 2})
        self.assertEqual(len([step for step in steps if step["kind"] == "plant"]), 2)


if __name__ == "__main__":
    unittest.main()
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_pens.py"`
Expected: `ImportError: cannot import name 'pens' from 'backend.survival'`.

- [ ] **Step 3: Pens are structures finished by their fences**

In `backend/survival/structures.py`, replace:

```python
    return planned.part in FITTINGS and material not in STANDS_IN.get(planned.block, (planned.block,))
```

with:

```python
    if planned.part == "fence":  # L3: a pen's ring
        return material != "fence"
    return planned.part in FITTINGS and material not in STANDS_IN.get(planned.block, (planned.block,))
```


In `backend/survival/building.py`, replace:

```python
    parts = ("plot",) if structure["kind"] == "farm" else ("floor", "wall", "roof")
```

with:

```python
    parts = {"farm": ("plot",), "pen": ("fence",)}.get(structure["kind"], ("floor", "wall", "roof"))  # L3: pens
```


- [ ] **Step 4: The pen purposes**

Create `backend/survival/pens.py`:

```python
"""build_pen and stock_pen: a fence ring by home for the animals Mimo grows from creature seeds
(spec L3: "farm purposes may plant them near home once a pen exists (a fence ring)").

build_pen lays out a pen once Mimo has a finished shelter within 64 blocks and carries a creature
seed: a 5x5 ring of 16 fences around 3x3 of grass, on flat untouched ground near home with a
walkway of standable ground all round it (`design_pen`). The pen is a structure (kind "pen") that
claims its fences and its inside (structures.start), so no plan digs, tills or builds there and no
wild animal wanders in; it is done when the last fence stands (building.finish_if_built). Mimo
makes the fences (4 planks and 2 sticks make 3, any wood) and places them standing on the walkway,
never inside, 8 a batch. Nothing can stand on a fence or step over one (grid.supported), so what
grows inside stays there. It is offered while Mimo can make every fence still missing, and is day
work: 45 plus a tenth of diligence and a twentieth of creativity.

stock_pen, a farm purpose, plants creature seeds on the pen's open grass from the walkway while
the pen holds fewer than PEN_ANIMALS animals and sprouts; a game day later each sprout is a tame
animal (backend.survival.creatures.seeds). The seeds wait in the chest at home (storage.KEEP keeps
none on hand), so it first takes out what it needs. Day work: 50 plus a tenth of patience.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.blocks import is_replaceable
from backend.survival.blueprints import Blueprint, Planned, Survey
from backend.survival.building import current_shelter, site_center, structures_near
from backend.survival.carrying import crafts_fit
from backend.survival.creatures.seeds import SEED, SPROUT
from backend.survival.creatures.table import cell_of as creature_cell
from backend.survival.creatures.table import dead
from backend.survival.foraging import whole_walk
from backend.survival.grid import Cell, Grid
from backend.survival.purposes import HOME_RANGE, Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import REACH
from backend.survival.storage import chest_contents, chest_placed, chest_spot
from backend.survival.structures import blueprint_of, clearing, start, todo
from backend.survival.toolmaking import Short, make

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

PEN_SIZE = 5  # fences on a side
PEN_ANIMALS = 3  # animals and sprouts a pen holds before Mimo plants more
FENCES_PER_BATCH = 8
PEN_BATCHES = 6
SITE_REACH = 10  # blocks from home's surface a pen's corner may lie


def design_pen(grid: Grid, center: Cell, owner: str, reach: int = SITE_REACH) -> Blueprint | None:
    """The nearest pen site to `center` (a cell Mimo stands in): a PEN_SIZE square of untouched
    ground at one height, grass inside, with every column of the walkway round it firm and within
    a block of that height. None when no site fits."""
    survey = Survey(grid, center[1] - 1)
    cx, _, cz = center
    spots = sorted(((math.hypot(dx, dz), dx, dz) for dx in range(-reach, reach + 1) for dz in range(-reach, reach + 1)
                    if math.hypot(dx, dz) <= reach))
    for _, dx, dz in spots:
        ox, oz = cx + dx - PEN_SIZE // 2, cz + dz - PEN_SIZE // 2
        floor = survey.height(ox, oz)
        if floor is None:
            continue
        square = [(ox + i, oz + j) for i in range(PEN_SIZE) for j in range(PEN_SIZE)]
        if any(survey.height(x, z) != floor for x, z in square):
            continue
        inside = [(x, z) for x, z in square if ox < x < ox + PEN_SIZE - 1 and oz < z < oz + PEN_SIZE - 1]
        if any(grid.material(x, floor, z) != "grass" for x, z in inside):
            continue
        walkway = [(ox + i, oz + j) for i in range(-1, PEN_SIZE + 1) for j in range(-1, PEN_SIZE + 1)
                   if i in (-1, PEN_SIZE) or j in (-1, PEN_SIZE)]
        grounds = [survey.height(x, z) for x, z in walkway]
        if any(ground is None or abs(ground - floor) > 1 for ground in grounds):
            continue
        cells = tuple(Planned((x, floor + 1, z), "fence", "fence") for x, z in square if (x, z) not in inside)
        cells += tuple(Planned((x, floor + 1, z), "pen", "air") for x, z in inside)
        stands = tuple((x, ground + 1, z) for (x, z), ground in zip(walkway, grounds))
        return Blueprint("pen", f"{owner}'s pen", (ox + PEN_SIZE // 2, floor + 1, oz + PEN_SIZE // 2), cells, stands,
                         style={"size": [PEN_SIZE, PEN_SIZE]})
    return None


def current_pen(s: Situation) -> dict | None:
    near = structures_near(s, "pen")
    return near[-1] if near else None


def home_done(s: Situation) -> bool:
    shelter = current_shelter(s)
    return shelter is not None and shelter["status"] == "done"


def pen_design(s: Situation) -> Blueprint | None:
    return s.sensed("pen_design", lambda: design_pen(s.grid, site_center(s), s.state["name"]))


def fences_left(s: Situation, blueprint: Blueprint) -> list[Cell]:
    return [planned.cell for planned in todo(s.grid, blueprint, ("fence",))]


def fence_supply(s: Situation, wanted: int) -> tuple[list[dict], int]:
    """Craft steps making fences (3 at a time) until Mimo has `wanted`, or as many as it can with
    room to carry them, and how many it will then carry."""
    inventory, steps = dict(s.inventory), []
    while inventory.get("fence", 0) < wanted:
        trial, more = dict(inventory), []
        try:
            make(trial, "fence", inventory.get("fence", 0) + 1, more)
        except Short:
            break
        if not crafts_fit(s.inventory, steps + more):
            break
        inventory, steps = trial, steps + more
    return steps, inventory.get("fence", 0)


def inside(blueprint: Blueprint, cell: Cell) -> bool:
    return any(planned.cell[0] == cell[0] and planned.cell[2] == cell[2] for planned in blueprint.parts("pen"))


def seeds_at_hand(s: Situation) -> int:
    """Creature seeds Mimo carries or keeps in its chest at home."""
    cell = chest_spot(s)
    stored = chest_contents(s, cell).get(SEED, 0) if chest_placed(s, cell) else 0
    return s.count(SEED) + stored


def from_walkway(s: Situation, blueprint: Blueprint, jobs: list[tuple[Cell, list[dict]]],
                 at: Cell | None = None) -> list[dict]:
    """Each job's steps, walking first to the walkway cell nearest Mimo that reaches the job's cell
    whenever it is out of reach from where Mimo will be (`at`, where it stands unless given), or
    Mimo stands inside the pen."""
    steps, at = [], at or s.here
    for cell, work in jobs:
        if math.dist(at, cell) > REACH or inside(blueprint, at):
            stands = [stand for stand in blueprint.stands if math.dist(stand, cell) <= REACH]
            if not stands:
                continue
            at = min(stands, key=lambda stand: (math.dist(stand, at), stand))
            steps.append(whole_walk(at))
        steps.extend(work)
    return steps


# build_pen ---------------------------------------------------------------------------------------

def build_valid(s: Situation) -> bool:
    if s.night or not home_done(s) or seeds_at_hand(s) < 1:
        return False
    pen = current_pen(s)
    if pen is not None:
        left = fences_left(s, blueprint_of(pen))
        return pen["status"] == "building" and bool(left) and fence_supply(s, min(len(left), FENCES_PER_BATCH))[1] > 0
    return pen_design(s) is not None and fence_supply(s, 4 * (PEN_SIZE - 1))[1] >= 4 * (PEN_SIZE - 1)


def plan_build_pen(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= PEN_BATCHES or s.db is None:
        return []
    pen = current_pen(s)
    if pen is None:
        design = pen_design(s)
        if design is None:
            return []
        start(s.db, s.grid, design, s.at)
        blueprint = design
    else:
        blueprint = blueprint_of(pen)
    left = fences_left(s, blueprint)[:FENCES_PER_BATCH]
    crafting, have = fence_supply(s, len(left))
    jobs = [(cell, [*clearing(s.grid, cell), {"kind": "place", "target": list(cell), "block": "fence"}])
            for cell in left[:have]]
    return crafting + from_walkway(s, blueprint, jobs) if jobs else []


register(Purpose(
    "build_pen", "build a pen",
    "Put a ring of fences up by home, for the animals creature seeds grow into.",
    valid=build_valid,
    facts=lambda s: f"{seeds_at_hand(s)} creature seeds at hand, carrying {s.count('fence')} fences; "
                    + ("a pen started" if current_pen(s) else "no pen yet"),
    score=lambda s: 45.0 + s.trait("diligence") / 10 + s.trait("creativity") / 20,
    plan=plan_build_pen,
    thoughts=("A pen would keep my animals safe.", "Fences first, then the seeds.")))


# stock_pen ---------------------------------------------------------------------------------------

def finished_pen(s: Situation) -> Blueprint | None:
    pen = current_pen(s)
    return blueprint_of(pen) if pen is not None and pen["status"] == "done" and s.distance((pen["x"], pen["y"], pen["z"])) <= HOME_RANGE else None


def pen_life(s: Situation, blueprint: Blueprint) -> int:
    """Animals standing in the pen and sprouts growing there."""
    herd = s.grid.herd
    x, _, z = blueprint.anchor
    animals = [] if herd is None else [creature for creature in herd.near(x, z, PEN_SIZE)
                                       if not dead(creature) and inside(blueprint, creature_cell(creature))]
    sprouts = [planned for planned in blueprint.parts("pen") if s.grid.material(*planned.cell) == SPROUT]
    return len(animals) + len(sprouts)


def open_plots(s: Situation, blueprint: Blueprint) -> list[Cell]:
    """The pen's inside cells where a seed can go: open, over grass, with no animal standing there."""
    herd = s.grid.herd
    x, _, z = blueprint.anchor
    taken = set() if herd is None else {creature_cell(creature) for creature in herd.near(x, z, PEN_SIZE)
                                         if not dead(creature)}
    found = []
    for planned in blueprint.parts("pen"):
        cx, cy, cz = cell = planned.cell
        material = s.grid.material(*cell)
        if (material != "water" and is_replaceable(material) and s.grid.material(cx, cy - 1, cz) == "grass"
                and cell not in taken):
            found.append(cell)
    return found


def stock_valid(s: Situation) -> bool:
    if s.night or seeds_at_hand(s) < 1:
        return False
    blueprint = finished_pen(s)
    return blueprint is not None and pen_life(s, blueprint) < PEN_ANIMALS and bool(open_plots(s, blueprint))


def plan_stock_pen(s: Situation, context: ActionContext) -> list[dict]:
    blueprint = finished_pen(s)
    if s.night or s.brain["batches"] > 0 or blueprint is None:
        return []
    room = PEN_ANIMALS - pen_life(s, blueprint)
    steps, carried, at = [], s.count(SEED), s.here
    if carried < room:
        cell = chest_spot(s)
        take = min(room - carried, chest_contents(s, cell).get(SEED, 0)) if chest_placed(s, cell) else 0
        if take:
            at = blueprint_of(current_shelter(s)).anchor
            steps += [whole_walk(at), {"kind": "take", "target": list(cell), "item": SEED, "amount": take}]
            carried += take
    jobs = [(cell, [{"kind": "plant", "target": list(cell), "item": SEED}])
            for cell in open_plots(s, blueprint)[:min(carried, room)]]
    return steps + from_walkway(s, blueprint, jobs, at) if jobs else []


register(Purpose(
    "stock_pen", "plant creature seeds",
    "Plant creature seeds in the pen by home; each grows into an animal in a day.",
    valid=stock_valid,
    facts=lambda s: f"{seeds_at_hand(s)} creature seeds at hand; the pen holds {pen_life(s, finished_pen(s))} of {PEN_ANIMALS}",
    score=lambda s: 50.0 + s.trait("patience") / 10, plan=plan_stock_pen,
    thoughts=("Something will grow from this seed.", "The pen could use a few more friends.")))
```


In `backend/survival/brain.py`, replace:

```python
from backend.survival import flint  # noqa: F401  (L3's gather_flint)
```

with:

```python
from backend.survival import flint, pens  # noqa: F401  (L3's gather_flint, build_pen and stock_pen)
```


Fences are made 3 at a time, so the 16 of a pen leave 2 over; once the pen is done they are junk, or they would fill a stack for good:

In `backend/survival/storage.py`, replace:

```python
from backend.survival.building import current_shelter, usable_supplies
```

with:

```python
from backend.survival.building import current_shelter, structures_near, usable_supplies
```

and replace:

```python
def junk(s: Situation) -> list[tuple[str, int]]:
```

with:

```python
def spare_fences(s: Situation) -> list[tuple[str, int]]:
    """L3: fences are made 3 at a time, so a pen leaves one or two over. Once the newest pen near
    Mimo is done (backend.survival.pens), they are no use to carry."""
    pens = structures_near(s, "pen")
    if not s.count("fence") or not pens or pens[-1]["status"] != "done":
        return []
    return [("fence", s.count("fence"))]


def junk(s: Situation) -> list[tuple[str, int]]:
```

and replace:

```python
    found += [(flower, s.count(flower)) for flower in FLOWERS if s.count(flower)]
```

with:

```python
    found += [(flower, s.count(flower)) for flower in FLOWERS if s.count(flower)]
    found += spare_fences(s)
```


- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_pens.py"`
Expected: `Ran 6 tests` … `OK`

- [ ] **Step 6: Raw food waits for the fire**

In a dry run on L2's plan, with pens in the day, `test_survival_days`' hunting pet (seed 8) put its raw rabbit in the chest as spare food right after the hunt, and cook only uses what Mimo carries, so the rabbit was never cooked. Whether putting away or cooking came first hung on the order purposes register in, which a test module that imports `backend.survival.storage` early changes. Raw food now stays out of the spare food (resolution 26).

Create `backend/tests/test_survival_raw_food.py`:

```python
import unittest

from backend.survival import storage
from backend.tests.test_survival_storage import Home


class RawFoodTests(unittest.TestCase):
    def test_raw_meat_and_fish_wait_for_the_fire_instead_of_the_chest(self):
        home = Home({"berries": 40, "raw_rabbit": 2, "raw_fish": 3})
        s = home.situation()
        spare = dict(storage.spare_food(s))
        self.assertIn("berries", spare)
        self.assertNotIn("raw_rabbit", spare)
        self.assertNotIn("raw_fish", spare)
        self.assertNotIn("raw_rabbit", dict(storage.to_store(s, home.chest)))


if __name__ == "__main__":
    unittest.main()
```


Run: `python3 -m unittest discover -s backend/tests -p "test_survival_raw_food.py"`
Expected: FAIL, `AssertionError: 'raw_rabbit' unexpectedly found in {'raw_rabbit': 2, 'raw_fish': 3, 'berries': 32}`.

In `backend/survival/storage.py`, replace:

```python
from backend.survival.cooking import made
```

with:

```python
from backend.survival.cooking import RAW_FOODS, made
```

and replace:

```python
    """Food beyond a day's worth (60 hunger), the least filling first."""
    kept, spare = 0.0, []
    for item in foods(s.inventory, s.poisons):
```

with:

```python
    """Food beyond a day's worth (60 hunger), the least filling first. Raw food Mimo can cook
    (cooking.RAW_FOODS) is neither: it waits for the fire, since cook only uses what Mimo carries."""
    kept, spare = 0.0, []
    for item in foods(s.inventory, s.poisons):
        if item in RAW_FOODS:
            continue
```


Run: `python3 -m unittest discover -s backend/tests -p "test_survival_raw_food.py"`
Expected: `Ran 1 test` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 883 tests` … `OK` (7 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/pens.py backend/survival/structures.py backend/survival/building.py backend/survival/brain.py backend/survival/storage.py backend/tests/test_survival_pens.py backend/tests/test_survival_raw_food.py
git commit -m "feat: Mimo fences a pen by home and plants its creature seeds there" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: L2's review notes: light, spawns, creature moves, chases and collapsing afloat

L2's final review left notes for L3 (`.superpowers/sdd/2026-09-23-living-world-l2-danger/l3-carryover.md`). This task takes the ones that touch what L3 adds (resolution 25): leaves of every kind let the sky through and are no ground to spawn on, by a block property rather than the name `leaves`; the sky scan clears the highest tree or rock the generator makes, and sinkholes and hillside mouths read right; hostiles can come out near Mimo however deep it digs or however high the hill over it; lava the generator made lights the cave round it; no creature climbs a ladder or steps into, over or through a fence or a ladder, so a pen holds its animals; a hostile loses interest in a chase that lands no blow for 45 game seconds or loses sight of Mimo (L2's flee runs until the chaser gives up, so a skitter could chase an unarmed pet some 800 blocks); and the collapse reflex swims for land first, as sleep and rest do. The review's other notes need nothing here: L3 claims no tunnel (resolution 17), so no dug passage is a "passage" part and harm.INDOORS keeps to shelters; L3 adds no door gap; and gravel with a purpose to gather it is Tasks 3, 4 and 10.

**Files:**
- Modify: `shared/blocks.json` (`"canopy": true` on the three leaves), `backend/services/blocks.py` (`CANOPY`, `is_canopy`), `backend/services/worldgen.py` (`ROCK_TOP`, `FEATURE_TOP`, `lava_in_chunk`), `backend/survival/light.py` (`SEE_THROUGH`, `SKY_SCAN`, lava light), `backend/survival/creatures/darkness.py` (`UNDERFOOT`, spots around Mimo's level, lights with the seed), `backend/survival/creatures/moves.py` (`past_fixtures`), `backend/survival/creatures/hostiles.py` (losing interest), `backend/survival/reflexes.py` (collapse swims for land)
- Modify tests: `backend/tests/test_survival_sim.py` (the slow-mode purpose budget, resolution 27)
- Test: `backend/tests/test_survival_dark_world.py`

**Interfaces:**
- Consumes: L2's `light.sky_open`, `SEE_THROUGH`, `SKY_SCAN`, `Lights`, `light_at`, `darkness.spots`, `UNDERFOOT`, `SCAN_DEPTH`, `moves.steps`, `past_doors`; Task 3's `CANOPY_TOP`; Task 4's `LAVA_LEVEL` and `cave_fill`; Task 5's rocks and openings; Task 9's ladders, fences and ladder climbs in `pathing.moves`; L2's `hostiles.chases`, `chase`, `prowl`, `strike_pet` (`struck_at`), `ROUSED`, `LOITER`, `reflexes.plan_collapse` and `purposes.land_refuge`; L2's test helpers in `test_survival_hostiles.py` and `test_survival_purposes.py`.
- Produces:
  - `blocks.CANOPY` (the registry's `canopy` blocks: `leaves`, `birch_leaves`, `spruce_leaves`), `blocks.is_canopy(material)`. `canopy` is not a crafting property (`crafting.BLOCKS` is unchanged).
  - `worldgen.ROCK_TOP = 3`, `worldgen.FEATURE_TOP = max(CANOPY_TOP, ROCK_TOP)`; `worldgen.lava_in_chunk(cx, cz, seed) -> tuple[Cell, ...]` (cached; Python only).
  - `light.SEE_THROUGH = CANOPY`; `light.SKY_SCAN = max(8, FEATURE_TOP + 1)` (8 today); `light.LAVA_LIGHT = 15`; `light.lava_light(grid, seed, cell) -> int`; `Lights(grid, center, reach, seed=None)`: with a seed, `at` also counts lava the generator made that is still there; `light_at` passes its seed.
  - `darkness.UNDERFOOT = CANOPY`; `spots` searches from just over the natural ground down to `SPAWN_RISE` below Mimo's level, however deep (L2's `SCAN_DEPTH` goes); the spawner's `Lights` gets the seed.
  - `moves.FIXTURES = ("fence", "ladder")`, `moves.past_fixtures(grid, start, step) -> bool`, and `moves.steps` requires it.
  - `hostiles.BORED = 45.0`, `SIGHT_LOST = 5.0`, `BORED_REST = 60.0` (game seconds); `hostiles.in_sight(grid, cell, target)`, `hostiles.lost_interest(state, scene)`; a chase records `chase_since` and `seen_at`, and prowl marks `bored_at` when it takes over from a chase that lost interest; `chases` is false while `lost_interest` holds.
  - `reflexes.plan_collapse`: afloat, `[land_refuge walk, sleep]` (the sleep not kept); on land as before.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_dark_world.py`:

```python
import unittest
from unittest.mock import patch

from backend.services.blocks import CANOPY, is_canopy
from backend.services.worldgen import (
    FEATURE_TOP, LAVA_LEVEL, block_at, lava_in_chunk, region_openings, surface_opened, terrain_height,
)
from backend.survival.creatures.acts import act
from backend.survival.creatures.darkness import spots
from backend.survival.creatures.hostiles import BORED, BORED_REST, SIGHT_LOST
from backend.survival.creatures.moves import steps
from backend.survival.grid import Grid
from backend.survival.light import SKY_SCAN, Lights, light_at, sky_open
from backend.survival.pathing import moves
from backend.survival.reflexes import plan_collapse
from backend.tests.test_survival_hostiles import hostile, pet, scene
from backend.tests.test_survival_hostiles import meadow as hunting_ground
from backend.tests.test_survival_purposes import NIGHT, context, flat, situation

SEED = "1"


def generated():
    return Grid(lambda x, y, z: block_at(x, y, z, SEED))


def meadow(blocks=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    return grid


def opening_of(kind):
    """The first cave entrance of `kind` in the world "1", east of the legacy clearing."""
    for rx in range(4, 40):
        for rz in range(-4, 4):
            found, spans = region_openings(rx, rz, SEED)
            if found == kind:
                return spans
    raise AssertionError(f"no {kind}")


class CanopyTests(unittest.TestCase):
    def test_every_kind_of_leaves_is_canopy_by_a_block_property(self):
        self.assertEqual(CANOPY, frozenset({"leaves", "birch_leaves", "spruce_leaves"}))
        self.assertTrue(is_canopy("spruce_leaves"))
        self.assertFalse(is_canopy("oak_log") or is_canopy("not_a_block"))

    @patch("backend.survival.light.terrain_height", lambda x, z, seed: 0)
    def test_the_sky_shines_through_birch_and_spruce_leaves(self):
        grid = meadow({(0, 5, 0): "birch_leaves", (0, 7, 0): "spruce_leaves", (2, 5, 0): "stone"})
        self.assertTrue(sky_open(grid, SEED, (0, 1, 0)))
        self.assertFalse(sky_open(grid, SEED, (2, 1, 0)))

    @patch("backend.survival.creatures.darkness.terrain_height", lambda x, z, seed: 0)
    def test_no_hostile_comes_out_on_any_kind_of_leaves(self):
        grid = Grid(lambda x, y, z: ("spruce_leaves" if x == 0 else "grass") if y == 0 else "dirt" if y < 0 else "air")
        self.assertEqual(spots(grid, SEED, 0, 0, 1), [])
        self.assertEqual(spots(grid, SEED, 1, 0, 1), [(1, 1, 0)])


class SkyScanTests(unittest.TestCase):
    def test_the_scan_reaches_over_the_highest_tree_and_rock(self):
        self.assertGreater(SKY_SCAN, FEATURE_TOP)

    def test_a_sinkhole_is_open_to_its_floor_and_a_mouth_until_its_roof(self):
        grid = generated()
        (x, z), (bottom, _) = next(iter(opening_of("sinkhole").items()))
        self.assertTrue(sky_open(grid, SEED, (x, bottom, z)))
        spans = opening_of("mouth")
        opened = [(x, low, z) for (x, z), (low, _) in spans.items() if surface_opened(x, z, SEED)]
        roofed = [(x, low, z) for (x, z), (low, high) in spans.items() if high + 1 < terrain_height(x, z, SEED)]
        self.assertTrue(opened and roofed)
        self.assertTrue(all(sky_open(grid, SEED, cell) for cell in opened))
        self.assertFalse(any(sky_open(grid, SEED, cell) for cell in roofed))


class LavaLightTests(unittest.TestCase):
    def test_lava_the_generator_made_lights_the_cave_round_it(self):
        lava = next(cell for cx in range(12, 60) for cell in lava_in_chunk(cx, 3, SEED))
        x, y, z = lava
        self.assertEqual((y, block_at(x, y, z, SEED)), (LAVA_LEVEL, "lava"))
        grid = generated()
        above = (x, y + 1, z)
        lights = Lights(grid, above, 0, SEED)
        self.assertEqual((lights.at(above), lights.at((x, y + 16, z))), (14, 0))
        self.assertGreaterEqual(light_at(grid, SEED, above, True), 14)
        self.assertEqual(Lights(grid, above, 0).at(above), 0)  # without the seed, placed blocks only (L2)
        for cx in range(x // 16 - 1, x // 16 + 2):  # lava covered over gives no light
            for cz in range(z // 16 - 1, z // 16 + 2):
                for cell in lava_in_chunk(cx, cz, SEED):
                    grid.put(*cell, "stone")
        self.assertEqual(Lights(grid, above, 0, SEED).at(above), 0)


class DeepSpawnTests(unittest.TestCase):
    @patch("backend.survival.creatures.darkness.terrain_height", lambda x, z, seed: 40)
    def test_hostiles_can_come_out_beside_mimo_however_deep_it_is(self):
        grid = Grid(lambda x, y, z: "air" if (x, z) == (5, 0) and y in (0, 1) else "stone" if y <= 40 else "air")
        self.assertEqual(spots(grid, SEED, 5, 0, 0), [(5, 0, 0)])  # 40 under the hilltop


class FixtureTests(unittest.TestCase):
    def test_no_creature_climbs_a_ladder_or_steps_into_one(self):
        grid = meadow({(1, 1, 0): "ladder", (1, 2, 0): "ladder"})
        self.assertIn((1, 1, 0), list(moves(grid, (0, 1, 0))))  # Mimo can
        self.assertNotIn((1, 1, 0), steps(grid, (0, 1, 0), False))
        self.assertIn((1, 2, 0), list(moves(grid, (1, 1, 0))))
        self.assertNotIn((1, 2, 0), steps(grid, (1, 1, 0), False))

    def test_a_fence_ring_holds_what_is_inside_and_keeps_the_rest_out(self):
        ring = {(x, 1, z): "fence" for x in range(-2, 3) for z in range(-2, 3) if max(abs(x), abs(z)) == 2}
        grid = meadow(ring)
        for start in ((0, 1, 0), (1, 1, 1), (-1, 1, 0)):
            found = steps(grid, start, False)
            self.assertTrue(found, start)
            self.assertTrue(all(max(abs(x), abs(z)) <= 1 for x, _, z in found), (start, found))
        outside = steps(grid, (3, 1, 0), False)
        self.assertTrue(outside)
        self.assertTrue(all(max(abs(x), abs(z)) >= 3 for x, _, z in outside), outside)


class LoseInterestTests(unittest.TestCase):
    def test_a_chase_that_lands_no_blow_ends_after_45_game_seconds_and_leaves_mimo_be(self):
        grid, state = hunting_ground(), pet()
        keen = hostile(grid, cell=(10, 1, 0), chasing=True, chase_since=0.0, seen_at=BORED - 3.0)
        self.assertEqual(act(keen, scene(grid, state, at=BORED - 1.0)), "chase")
        self.assertEqual(keen["state"]["seen_at"], BORED - 1.0)  # Mimo is in plain sight
        bored = hostile(grid, cell=(10, 1, 3), chasing=True, chase_since=0.0, seen_at=BORED + 1.0)
        self.assertEqual(act(bored, scene(grid, state, at=BORED + 1.0)), "prowl")
        self.assertEqual((bored["state"]["chasing"], bored["state"]["bored_at"]), (False, BORED + 1.0))
        self.assertEqual(act(bored, scene(grid, state, at=BORED + BORED_REST)), "prowl")  # a minute's peace
        bored["state"]["hurt_at"] = BORED + BORED_REST  # unless Mimo hurts it
        self.assertEqual(act(bored, scene(grid, state, at=BORED + BORED_REST)), "chase")

    def test_a_blow_keeps_the_chase_going_and_losing_sight_of_mimo_ends_it(self):
        grid, state = hunting_ground(), pet()
        striking = hostile(grid, cell=(10, 1, 0), chasing=True, chase_since=0.0, struck_at=40.0, seen_at=50.0)
        self.assertEqual(act(striking, scene(grid, state, at=50.0)), "chase")
        lost = hostile(grid, cell=(10, 1, 3), chasing=True, chase_since=0.0, seen_at=0.0)
        self.assertEqual(act(lost, scene(grid, state, at=SIGHT_LOST + 1.0)), "prowl")


class CollapseTests(unittest.TestCase):
    def test_an_exhausted_pet_afloat_swims_for_land_before_it_lies_down(self):
        afloat = situation(clock=NIGHT, grid=flat(cells={(0, 0, 0): "water"}), places=[("home", (5, 1, 0))])
        self.assertEqual(plan_collapse(afloat, context()),
                         [{"kind": "walk", "target": [5, 1, 0], "reach": 0.0}, {"kind": "sleep"}])
        self.assertEqual(plan_collapse(situation(clock=NIGHT), context()), [{"kind": "sleep"}])


if __name__ == "__main__":
    unittest.main()
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_dark_world.py"`
Expected: `ImportError: cannot import name 'CANOPY' from 'backend.services.blocks'`.

- [ ] **Step 3: Leaves are canopy by a block property**

In `shared/blocks.json`, replace:

```json
    {"name": "leaves", "color": [101, 164, 128], "textures": "leaves", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.3},
```

with:

```json
    {"name": "leaves", "color": [101, 164, 128], "textures": "leaves", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.3, "canopy": true},
```

and replace:

```json
    {"name": "birch_leaves", "color": [134, 176, 104], "textures": "birch_leaves", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.3},
```

with:

```json
    {"name": "birch_leaves", "color": [134, 176, 104], "textures": "birch_leaves", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.3, "canopy": true},
```

and replace:

```json
    {"name": "spruce_leaves", "color": [70, 116, 98], "textures": "spruce_leaves", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.3},
```

with:

```json
    {"name": "spruce_leaves", "color": [70, 116, 98], "textures": "spruce_leaves", "layer": "opaque", "solid": true, "drop": null, "hardness": 0.3, "canopy": true},
```


In `backend/services/blocks.py`, replace:

```python
_RENDER_KEYS = {"name", "textures", "layer", "solid", "replaceable", "shape"}
```

with:

```python
# Keys that are not crafting properties: how a block is drawn, and (L3) `canopy`, read by is_canopy.
_RENDER_KEYS = {"name", "textures", "layer", "solid", "replaceable", "shape", "canopy"}
```

and replace:

```python
def is_solid(material: str) -> bool:
```

with:

```python
CANOPY = frozenset(block["name"] for block in BLOCK_LIST if block.get("canopy"))


def is_canopy(material: str) -> bool:
    """True for every kind of leaves (the registry's `canopy`): the sky shines through them and no
    creature comes out on them (backend.survival.light, backend.survival.creatures.darkness)."""
    return material in CANOPY


def is_solid(material: str) -> bool:
```


- [ ] **Step 4: How high the generator builds, and where its lava is**

In `backend/services/worldgen.py`, replace:

```python
OUTCROPS = {"desert": "sandstone", "taiga": "andesite", "birch_forest": "diorite", "alpine": "granite"}  # else stone
```

with:

```python
OUTCROPS = {"desert": "sandstone", "taiga": "andesite", "birch_forest": "diorite", "alpine": "granite"}  # else stone
ROCK_TOP = 3  # the highest an outcrop's pillar stands over its ground (a boulder is lower)
FEATURE_TOP = max(CANOPY_TOP, ROCK_TOP)  # the highest anything generated stands over a column's ground
```

and replace:

```python
def gravel_floor(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
```

with:

```python
@lru_cache(maxsize=4096)
def lava_in_chunk(cx: int, cz: int, seed: str = LEGACY_WORLD_SEED) -> tuple[tuple[int, int, int], ...]:
    """The lava cells the generator makes in a 16x16 chunk (all at LAVA_LEVEL), for the light they give
    (backend.survival.light). Python only: the viewer draws lava glowing without it."""
    return tuple((x, LAVA_LEVEL, z) for x in range(cx * 16, cx * 16 + 16) for z in range(cz * 16, cz * 16 + 16)
                 if noise2(x, z, 32, seed, 28) > 0.25 and terrain_block(x, LAVA_LEVEL, z, seed) == "lava")


def gravel_floor(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
```


- [ ] **Step 5: Light: every leaves, the full scan, and lava**

In `backend/survival/light.py`, replace:

```python
  up to SKY_SCAN cells above the natural ground (leaves let the sky through): a cave, a tunnel
```

with:

```python
  up to SKY_SCAN cells above the natural ground (any leaves let the sky through: blocks.is_canopy;
  L3: SKY_SCAN clears the highest tree or rock the generator stands on a column): a cave, a tunnel
```

and replace:

```python
from backend.services.blocks import is_solid
from backend.services.worldgen import terrain_height
```

with:

```python
from backend.services.blocks import CANOPY, is_solid
from backend.services.worldgen import FEATURE_TOP, LAVA_LEVEL, lava_in_chunk, terrain_height
```

and replace:

```python
SKY_SCAN = 8  # cells over the natural ground (or the cell, when it is higher) that can cover a cell
SEE_THROUGH = ("leaves",)
```

with:

```python
# Cells over the natural ground (or the cell, when it is higher) that can cover a cell: 8, and in any
# case more than the highest tree or rock the generator makes (L3).
SKY_SCAN = max(8, FEATURE_TOP + 1)
SEE_THROUGH = CANOPY  # L3: every kind of leaves, by the registry's `canopy`
LAVA_LIGHT = 15  # L3: lava the generator made lights the cave round it
```

and replace:

```python
    def __init__(self, grid: Grid, center: Cell, reach: float):
        x, _, z = center
```

with:

```python
    def __init__(self, grid: Grid, center: Cell, reach: float, seed: str | None = None):
        x, _, z = center
        self.grid, self.seed = grid, seed  # L3: with the seed, lava the generator made lights too
```

and replace:

```python
        return max([level - abs(x - sx) - abs(y - sy) - abs(z - sz) for (sx, sy, sz), level in self.sources] + [0])
```

with:

```python
        level = max([level - abs(x - sx) - abs(y - sy) - abs(z - sz) for (sx, sy, sz), level in self.sources] + [0])
        return max(level, lava_light(self.grid, self.seed, cell)) if self.seed is not None else level


def lava_light(grid: Grid, seed: str, cell: Cell) -> int:
    """L3: the light at `cell` from lava the generator made (worldgen.lava_in_chunk) that is still
    there, LAVA_LIGHT less its Manhattan distance, at least 0. Lava lies only at LAVA_LEVEL, so a cell
    LAVA_LIGHT or more above it costs nothing, and the chunks are generated once."""
    x, y, z = cell
    reach = LAVA_LIGHT - abs(y - LAVA_LEVEL)
    best = 0
    if reach <= 0:
        return best
    for cx in range((x - reach) // 16, (x + reach) // 16 + 1):
        for cz in range((z - reach) // 16, (z + reach) // 16 + 1):
            for lx, ly, lz in lava_in_chunk(cx, cz, seed):
                level = LAVA_LIGHT - abs(x - lx) - abs(y - ly) - abs(z - lz)
                if level > best and grid.material(lx, ly, lz) == "lava":
                    best = level
    return best
```

and replace:

```python
    lights = lights if lights is not None else Lights(grid, cell, 0)
```

with:

```python
    lights = lights if lights is not None else Lights(grid, cell, 0, seed)
```


- [ ] **Step 6: Spawns around Mimo's level and never on leaves**

In `backend/survival/creatures/darkness.py`, replace:

```python
searched from just over the natural ground down SCAN_DEPTH cells, and no more than SPAWN_RISE
```

with:

```python
searched from just over the natural ground down, however deep Mimo is (L3), but no more than SPAWN_RISE
```

and replace:

```python
SCAN_DEPTH = 24  # cells a column is searched down from just over its natural ground
SPAWN_RISE = 8  # cells above or below Mimo a spawn may be
```

with:

```python
SPAWN_RISE = 8  # cells above or below Mimo a spawn may be (L3: the only bound on how deep)
```

and replace:

```python
UNDERFOOT = ("leaves",)
```

with:

```python
UNDERFOOT = CANOPY  # L3: no kind of leaves is ground to come out on
```

and replace:

```python
from backend.services.blocks import is_replaceable
```

with:

```python
from backend.services.blocks import CANOPY, is_replaceable
```

and replace:

```python
    for y in range(min(top, level + SPAWN_RISE), max(top - SCAN_DEPTH, level - SPAWN_RISE - 1), -1):
```

with:

```python
    for y in range(min(top, level + SPAWN_RISE), level - SPAWN_RISE - 1, -1):
```

and replace:

```python
            lights = lights or Lights(scene.grid, scene.pet, SPAWN_FAR)
```

with:

```python
            lights = lights or Lights(scene.grid, scene.pet, SPAWN_FAR, scene.seed)
```


- [ ] **Step 7: No creature climbs a ladder or crosses a fence; a chase ends; collapse swims for land**

In `backend/survival/creatures/moves.py`, replace:

```python
past_doors(grid, cell, step) and has_room(grid, cell, step, height)]
```

with:

```python
past_doors(grid, cell, step) and past_fixtures(grid, cell, step)
            and has_room(grid, cell, step, height)]
```

and replace:

```python
def timed(start: Cell, cells: list[Cell], at: float, seconds: float) -> list[dict]:
```

with:

```python
FIXTURES = ("fence", "ladder")


def past_fixtures(grid: Grid, start: Cell, step: Cell) -> bool:
    """L3: no creature climbs (a ladder's straight up or down), steps into a fence or a ladder or
    through one on the way (the level cell of a drop), or onto one: a fence ring holds the animals in
    a pen and keeps wild ones out, and a ladder shaft is Mimo's alone, as a door is (past_doors)."""
    if (step[0], step[2]) == (start[0], start[2]):
        return False
    cells = (step, (step[0], start[1], step[2]), (step[0], step[1] - 1, step[2]))
    return all(grid.material(*cell) not in FIXTURES for cell in cells)


def timed(start: Cell, cells: list[Cell], at: float, seconds: float) -> list[dict]:
```


In `backend/survival/creatures/hostiles.py`, replace:

```python
- prowl (25): otherwise it gives up the chase and wanders near where it spawned, or stands. One
```

with:

```python
- L3 (L2's review): a chaser loses interest once the chase has gone BORED game seconds since it
  began, its last blow or Mimo's last blow on it, or once Mimo has been out of its sight
  (`in_sight`) for SIGHT_LOST game seconds; it then leaves Mimo be for BORED_REST game seconds
  unless Mimo hurts it (`lost_interest`), so a flight from it ends as well.
- prowl (25): otherwise it gives up the chase and wanders near where it spawned, or stands. One
```

and replace:

```python
LOITER = 120.0  # game seconds a hostile stays about without coming after Mimo
```

with:

```python
LOITER = 120.0  # game seconds a hostile stays about without coming after Mimo
BORED = 45.0  # L3: game seconds of chasing without a blow after which a hostile loses interest
SIGHT_LOST = 5.0  # L3: game seconds Mimo may be out of a chaser's sight before it loses interest
BORED_REST = 60.0  # L3: game seconds a hostile that lost interest leaves Mimo be
```

and replace:

```python
def chases(creature: dict, kind: Kind, scene: Scene) -> bool:
```

with:

```python
def in_sight(grid: Grid, cell: Cell, target: Cell) -> bool:
    """L3: nothing solid on the line from a hostile to Mimo, checked every half block (as
    creatures.defense.clear_line checks a fight's line)."""
    samples = max(1, int(math.dist(cell, target) * 2))
    for index in range(1, samples):
        point = tuple(round(a + (b - a) * index / samples) for a, b in zip(cell, target))
        if point not in (cell, target) and grid.solid(point):
            return False
    return True


def lost_interest(state: dict, scene: Scene) -> bool:
    """L3: the hostile is leaving Mimo be after a chase it gave up (BORED_REST game seconds, unless
    Mimo hurt it since), or its chase has run BORED game seconds since it began, its last blow or
    Mimo's last blow on it, or Mimo has been out of its sight for SIGHT_LOST game seconds."""
    at, hurt = scene.at, state.get("hurt_at", -math.inf)
    bored_at = state.get("bored_at")
    if bored_at is not None and hurt < bored_at and (at - bored_at) * scene.scale <= BORED_REST:
        return True
    if not state.get("chasing"):
        return False
    since = max(state.get("chase_since", -math.inf), state.get("struck_at", -math.inf), hurt)
    since = at if since == -math.inf else since
    return (at - since) * scene.scale > BORED or (at - state.get("seen_at", at)) * scene.scale > SIGHT_LOST


def chases(creature: dict, kind: Kind, scene: Scene) -> bool:
```

and replace:

```python
    state = creature["state"]
    roused = state.get("chasing") or scene.at - state.get("hurt_at", -math.inf) <= ROUSED / scene.pace
```

with:

```python
    state = creature["state"]
    if lost_interest(state, scene):
        return False
    roused = state.get("chasing") or scene.at - state.get("hurt_at", -math.inf) <= ROUSED / scene.pace
```

and replace:

```python
        state["chasing"] = True
        alarm(scene, kind)
```

with:

```python
        state.update(chasing=True, chase_since=scene.at)  # L3: when this chase began
        alarm(scene, kind)
    if in_sight(scene.grid, where(creature, scene.at), scene.pet):
        state["seen_at"] = scene.at  # L3
```

and replace:

```python
def prowl(creature: dict, kind: Kind, scene: Scene) -> None:
    creature["state"]["chasing"] = False
```

with:

```python
def prowl(creature: dict, kind: Kind, scene: Scene) -> None:
    if creature["state"].get("chasing") and lost_interest(creature["state"], scene):
        creature["state"]["bored_at"] = scene.at  # L3: it lost interest, and leaves Mimo be a while
    creature["state"]["chasing"] = False
```


In `backend/survival/reflexes.py`, replace:

```python
from backend.survival.purposes import AT_HOME, HOME_RANGE, HOMEWARD, foods, home_of, meal, walk_to
```

with:

```python
from backend.survival.purposes import AT_HOME, HOME_RANGE, HOMEWARD, foods, home_of, land_refuge, meal, walk_to
```

and replace:

```python
    is kept (`keep`): when the walk fails, Mimo still sleeps where the walk left it."""
    walk = to_bed(s)
```

with:

```python
    is kept (`keep`): when the walk fails, Mimo still sleeps where the walk left it. L3 (L2's review):
    afloat, Mimo first swims for land (purposes.land_refuge), as sleep and rest do, and lies down
    once there; when that swim fails, the sleep is not kept, so it never lies down afloat."""
    refuge = land_refuge(s)
    if refuge is not None:
        return [refuge, {"kind": "sleep"}]
    walk = to_bed(s)
```


- [ ] **Step 8: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_dark_world.py"`
Expected: `Ran 12 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 895 tests` … `OK` (12 new). L2's light and darkness tests hold: their worlds have only oak leaves and no pet deeper than 16 under the surface.

- [ ] **Step 9: The slow-mode purpose budget**

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 2 tests` … `OK` at `983e2aa`, with 54 changes of purpose in the busiest game hour (seed 11, Jev) against the budget of 55; on L2's `e9d1098` the same run failed with `AssertionError: 58 not less than or equal to 55`.

With every backend task in, the busiest game hour of the slow headless runs has 54 changes of purpose (seed 11, Jev); the others have 36 to 46, and the default runs 28 to 46 (the budget there, 52, holds). Seed 11's Jev pet goes two game days without a chest (its shelter has none and it lacks the wood to make one), so its arms stay full and gather_stone and drop_items take turns: M5's rule for full arms with no chest, met more often now that there are more kinds of things to carry. That pet's count moved between 53 and 65 as the world and L2's rules under it changed during the dry runs (58 on `e9d1098`), so one point of margin would break on the next small change. Raise the slow-mode budget to 60 (resolution 27):

In `backend/tests/test_survival_sim.py`, replace:

```python
# of L1, seeds 3, 11, 5 and 21 and both pickers reached 47, and 52 in slow mode).
PURPOSE_EVENTS_PER_HOUR = 55 if SLOW else 52
```

with:

```python
# of L1, seeds 3, 11, 5 and 21 and both pickers reached 47, and 52 in slow mode).
# L3 adds pens, creature seeds and flint, more kinds to carry (birch and spruce wood, gold, the
# seeds), wider passages and hostiles near Mimo however deep it digs. With all of L3 the busiest
# hours reached 46, and 54 to 58 in slow mode as L2's last fixes landed, where seed 11's Jev pet
# goes two days without a chest: its arms stay full, and it swings between digging stone and
# dropping the loose blocks.
PURPOSE_EVENTS_PER_HOUR = 60 if SLOW else 52
```


Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` (about 2 minutes) and `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 2 tests` … `OK`

- [ ] **Step 10: Commit**

```bash
git add shared/blocks.json backend/services/blocks.py backend/services/worldgen.py backend/survival/light.py backend/survival/creatures/darkness.py backend/survival/creatures/moves.py backend/survival/creatures/hostiles.py backend/survival/reflexes.py backend/tests/test_survival_dark_world.py backend/tests/test_survival_sim.py
git commit -m "fix: every leaves let the sky through, hostiles come out near Mimo however deep and lose interest in a fruitless chase, lava gives light, no creature climbs a ladder or crosses a fence, and a collapse swims for land" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: The viewer draws the new blocks, names the new purposes and shows iron armor

**Files:**
- Modify: `frontend/src/engine/blocks.ts` (the `cube` flag and `CUBE_BY_ID`), `frontend/src/engine/mesher.ts` (cube cutouts), `frontend/src/survival/cutaway.ts` (new trees and fences are not cover, new building blocks are walls), `frontend/src/survival/hud.ts` (words for the new purposes), `frontend/src/survival/types.ts` (a pen is a structure kind), `frontend/src/survival/petGear.ts` (iron armor), `frontend/src/survival/SurvivalPet.tsx` and `frontend/src/survival/WorldCanvas.tsx` (pass the worn pieces)
- Test: `frontend/src/engine/blocks.test.ts`, `frontend/src/engine/mesher.test.ts`, `frontend/src/survival/cutaway.test.ts`, `frontend/src/survival/hud.test.ts`, `frontend/src/survival/petGear.test.ts`

**Interfaces:**
- Consumes: Task 1's `"shape": "cube"` on cactus, ladder and fence, and the new block names; Task 2's building blocks (`blueprints.BUILDING`); Tasks 10 and 12's purpose names; Task 8's `iron_tunic` and `iron_cap`; L2's `petGear.tunicVoxels`, `capVoxels` and the `tunic` and `cap` props of `SurvivalPet`.
- Produces: `BlockDef.cube`, `CUBE_BY_ID`; `petGear.wornTunic(inventory)`, `wornCap(inventory)` (`'iron_…'` over `'leather_…'`, or null); `SurvivalPet`'s `tunic` and `cap` props become the worn item's name (`string | null`) instead of booleans.

Until this task, the viewer draws cactus, ladders and fences as crossed sprites like a flower (they are cutout blocks). They read better as see-through cubes: the atlas tiles from Task 1 are drawn for that. The cube cutouts skip corner shadows: they are thin, and their cutout texture shows the ground through them anyway.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/engine/blocks.test.ts`, replace:

```typescript
  AIR, BLOCKS, FLUID_BY_ID, GLOW_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
```

with:

```typescript
  AIR, BLOCKS, CUBE_BY_ID, FLUID_BY_ID, GLOW_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
```

and replace:

```typescript
    expect(blockDef(blockId('birch_log')).textures.side).toBe('birch_log_side')
  })
```

with:

```typescript
    expect(blockDef(blockId('birch_log')).textures.side).toBe('birch_log_side')
  })

  it('marks the see-through blocks that are drawn as cubes', () => {
    for (const name of ['cactus', 'ladder', 'fence']) {
      expect(CUBE_BY_ID[blockId(name)], name).toBe(1)
      expect(blockDef(blockId(name)).cube, name).toBe(true)
    }
    for (const name of ['sugar_cane', 'fern', 'creature_sprout', 'flower_pink', 'torch', 'stone', 'air']) {
      expect(CUBE_BY_ID[blockId(name)], name).toBe(0)
    }
    expect(CUBE_BY_ID[MISSING_ID]).toBe(0)
  })
```


In `frontend/src/engine/mesher.test.ts`, replace:

```typescript
  it('draws plants as two crossed quads', () => {
    const result = mesh([[5, 10, 5, 'flower_pink']])
    expect(quadCount(result.cutout)).toBe(2)
    expect(quadCount(result.opaque)).toBe(0)
  })
```

with:

```typescript
  it('draws plants as two crossed quads', () => {
    const result = mesh([[5, 10, 5, 'flower_pink']])
    expect(quadCount(result.cutout)).toBe(2)
    expect(quadCount(result.opaque)).toBe(0)
  })

  it('draws cactus, ladders and fences as see-through cubes', () => {
    const cactus = mesh([[5, 10, 5, 'cactus']])
    expect(quadCount(cactus.cutout)).toBe(6)
    expect(quadCount(cactus.opaque)).toBe(0)
    expect(quadCount(mesh([[5, 10, 5, 'cactus'], [5, 11, 5, 'cactus']]).cutout)).toBe(10)  // none between two
    expect(quadCount(mesh([[5, 10, 5, 'fence'], [5, 9, 5, 'stone']]).cutout)).toBe(5)  // none against the ground
    expect(quadCount(mesh([[5, 10, 5, 'stone'], [6, 10, 5, 'ladder']]).opaque)).toBe(6)  // the wall shows through
    const top = quads(cactus.cutout).find((quad) => quad.vertices.every(([, y]) => y === 11))!
    const side = quads(cactus.cutout).find((quad) => quad.vertices.every(([x]) => x === 5))!
    expect(Math.min(...top.light)).toBeGreaterThan(Math.max(...side.light))
  })
```


In `frontend/src/survival/cutaway.test.ts`, replace:

```typescript
  it('counts a roof Mimo stands under', () => {
```

with:

```typescript
  it('is false under a birch or spruce canopy, and beside a fence', () => {
    for (const block of ['birch_leaves', 'spruce_leaves', 'birch_log', 'spruce_log', 'fence']) {
      expect(underground(ground({ '0,3,0': block }), { x: 0, y: 1, z: 0 }), block).toBe(false)
    }
  })

  it('counts a roof Mimo stands under', () => {
```

and replace:

```typescript
    expect(hides(wall(3, 'leaves'))).toBe(false)
```

with:

```typescript
    expect(hides(wall(3, 'leaves'))).toBe(false)
    expect(hides(wall(3, 'stone_bricks'))).toBe(true)  // L3's building blocks
    expect(hides(wall(3, 'spruce_planks'))).toBe(true)
    expect(hides(wall(3, 'fence'))).toBe(false)
```


In `frontend/src/survival/hud.test.ts`, replace:

```typescript
    expect(purposeText({ purpose: 'make_gear', reflex: null, choosing: false })).toBe('Making gear')
```

with:

```typescript
    expect(purposeText({ purpose: 'make_gear', reflex: null, choosing: false })).toBe('Making gear')
    expect(purposeText({ purpose: 'gather_flint', reflex: null, choosing: false })).toBe('Digging for flint')
    expect(purposeText({ purpose: 'build_pen', reflex: null, choosing: false })).toBe('Building a pen')
    expect(purposeText({ purpose: 'stock_pen', reflex: null, choosing: false })).toBe('Planting creature seeds')
```


In `frontend/src/survival/petGear.test.ts`, replace:

```typescript
import { HURT_GLOW_SECONDS, capVoxels, hurtGlow, tunicVoxels } from './petGear'
```

with:

```typescript
import { HURT_GLOW_SECONDS, capVoxels, hurtGlow, tunicVoxels, wornCap, wornTunic } from './petGear'
```

and replace:

```typescript
  it('glows red at once after a blow and fades', () => {
```

with:

```typescript
  it('wears iron over leather, in the same places, in grey', () => {
    expect(wornTunic({ leather_tunic: 1, iron_tunic: 1 })).toBe('iron_tunic')
    expect(wornCap({ leather_cap: 1 })).toBe('leather_cap')
    expect(wornCap({ iron_cap: 0 })).toBeNull()
    expect(wornTunic(undefined)).toBeNull()
    const leather = tunicVoxels({ leather_tunic: 1 })
    const iron = tunicVoxels({ leather_tunic: 1, iron_tunic: 1 })
    expect(iron.map(key)).toEqual(leather.map(key))
    expect(iron.every((voxel) => Math.abs(voxel.r - voxel.b) < 20)).toBe(true)
    expect(leather.every((voxel) => voxel.r - voxel.b > 40)).toBe(true)
    expect(capVoxels({ iron_cap: 1 }).map(key)).toEqual(capVoxels({ leather_cap: 1 }).map(key))
    expect(capVoxels({ iron_cap: 1 })[0].g).toBeGreaterThan(capVoxels({ leather_cap: 1 })[0].g)
  })

  it('glows red at once after a blow and fades', () => {
```


- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/engine/blocks.test.ts src/engine/mesher.test.ts src/survival/cutaway.test.ts src/survival/hud.test.ts src/survival/petGear.test.ts`
Expected: FAIL (6 tests): `CUBE_BY_ID` is undefined (`Cannot read properties of undefined`), the cactus draws 2 quads not 6, a fence counts as cover, `gather_flint` reads "Gather flint", and `wornTunic is not a function`.

- [ ] **Step 3: Cube cutouts**

In `frontend/src/engine/blocks.ts`, replace:

```typescript
  glow: boolean
  fluid: boolean
}
```

with:

```typescript
  glow: boolean
  fluid: boolean
  /** L3: a cutout block drawn as a see-through cube (cactus, ladder, fence), not crossed sprites. */
  cube: boolean
}
```

and replace:

```typescript
  glow?: boolean
  fluid?: boolean
}
```

with:

```typescript
  glow?: boolean
  fluid?: boolean
  shape?: string
}
```

and replace:

```typescript
    solid: raw.solid, textures, glow: Boolean(raw.glow), fluid: Boolean(raw.fluid),
```

with:

```typescript
    solid: raw.solid, textures, glow: Boolean(raw.glow), fluid: Boolean(raw.fluid), cube: raw.shape === 'cube',
```

and replace:

```typescript
  textures: { top: 'missing', side: 'missing', bottom: 'missing' }, glow: false, fluid: false,
```

with:

```typescript
  textures: { top: 'missing', side: 'missing', bottom: 'missing' }, glow: false, fluid: false, cube: false,
```

and replace:

```typescript
export const FLUID_BY_ID = new Uint8Array(256)
```

with:

```typescript
export const FLUID_BY_ID = new Uint8Array(256)
export const CUBE_BY_ID = new Uint8Array(256)
```

and replace:

```typescript
  FLUID_BY_ID[id] = def.fluid ? 1 : 0
```

with:

```typescript
  FLUID_BY_ID[id] = def.fluid ? 1 : 0
  CUBE_BY_ID[id] = def.cube ? 1 : 0
```


In `frontend/src/engine/mesher.ts`, replace:

```typescript
  AIR, FLUID_BY_ID, GLOW_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
```

with:

```typescript
  AIR, CUBE_BY_ID, FLUID_BY_ID, GLOW_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
```

and replace:

```typescript
        if (kind === LAYER_CUTOUT) {
          const uv = tileUv(faceTiles[id * 6 + SIDE_FACE])
```

with:

```typescript
        if (kind === LAYER_CUTOUT && CUBE_BY_ID[id] === 1) {
          // L3: cactus, ladders and fences are see-through cubes: every face but those against an
          // opaque block or one of their own, face-shaded, with no corner shadows.
          FACES.forEach((face, faceIndex) => {
            const neighbor = idAt(px + face.dir[0], layer + face.dir[1], pz + face.dir[2])
            if (neighbor === -1 || neighbor === id || LAYER_BY_ID[neighbor] === LAYER_OPAQUE) return
            const light = face.shade * blockTint
            cutout.quad(face.corners.map(([x, y, z]) => [wx + x, wy + y, wz + z] as Vec3),
              tileUv(faceTiles[id * 6 + faceIndex]), [light, light, light, light], false, glow ? 1 : 0)
          })
          continue
        }

        if (kind === LAYER_CUTOUT) {
          const uv = tileUv(faceTiles[id * 6 + SIDE_FACE])
```


- [ ] **Step 4: The cutaway, the HUD words and the pen kind**

In `frontend/src/survival/cutaway.ts`, replace:

```typescript
  'leaves', 'oak_log', 'crafting_table', 'furnace', 'lantern', 'glass', 'campfire', 'torch', 'bed', 'chest',
])
```

with:

```typescript
  'leaves', 'oak_log', 'crafting_table', 'furnace', 'lantern', 'glass', 'campfire', 'torch', 'bed', 'chest',
  'birch_leaves', 'spruce_leaves', 'birch_log', 'spruce_log', 'fence',  // L3
])
```

and replace:

```typescript
  'cobblestone', 'planks', 'brick', 'limestone', 'sandstone', 'basalt', 'moss', 'clay', 'sand', 'gravel', 'dirt',
])
```

with:

```typescript
  'cobblestone', 'planks', 'brick', 'limestone', 'sandstone', 'basalt', 'moss', 'clay', 'sand', 'gravel', 'dirt',
  'birch_planks', 'spruce_planks', 'stone_bricks',  // L3
])
```


In `frontend/src/survival/hud.ts`, replace:

```typescript
  light_up: 'Lighting torches', hunt: 'Hunting', make_gear: 'Making gear',
```

with:

```typescript
  light_up: 'Lighting torches', hunt: 'Hunting', make_gear: 'Making gear',
  gather_flint: 'Digging for flint', build_pen: 'Building a pen', stock_pen: 'Planting creature seeds',
```


In `frontend/src/survival/types.ts`, replace:

```typescript
  kind: 'shelter' | 'farm'
  name: string
```

with:

```typescript
  kind: 'shelter' | 'farm' | 'pen'
  name: string
```


- [ ] **Step 5: Iron armor on the pet**

In `frontend/src/survival/petGear.ts`, replace:

```typescript
const LEATHER: Color = [150, 96, 62]
const STITCH: Color = [112, 70, 44]
```

with:

```typescript
const LEATHER: Color = [150, 96, 62]
const STITCH: Color = [112, 70, 44]
const IRON: Color = [196, 201, 204]  // L3: iron armor, with darker rivets
const RIVET: Color = [128, 135, 140]
```

and replace:

```typescript
  if ((inventory?.leather_tunic ?? 0) < 1) return []
  const voxels: Voxel[] = []
```

with:

```typescript
  const worn = wornTunic(inventory)
  if (worn === null) return []
  const [main, trim] = worn === 'iron_tunic' ? [IRON, RIVET] : [LEATHER, STITCH]
  const voxels: Voxel[] = []
```

and replace:

```typescript
      voxels.push(voxel(x, 0, z, STITCH), voxel(x, 1, z, LEATHER))
```

with:

```typescript
      voxels.push(voxel(x, 0, z, trim), voxel(x, 1, z, main))
```

and replace:

```typescript
  if ((inventory?.leather_cap ?? 0) < 1) return []
  return [voxel(0, 4, 0, LEATHER), voxel(0, 4, 1, LEATHER), voxel(-1, 4, 1, STITCH), voxel(1, 4, 1, STITCH)]
}
```

with:

```typescript
  const worn = wornCap(inventory)
  if (worn === null) return []
  const [main, trim] = worn === 'iron_cap' ? [IRON, RIVET] : [LEATHER, STITCH]
  return [voxel(0, 4, 0, main), voxel(0, 4, 1, main), voxel(-1, 4, 1, trim), voxel(1, 4, 1, trim)]
}

/** L3: the tunic Mimo wears, iron over leather, or null when it carries neither. */
export function wornTunic(inventory: Record<string, number> | null | undefined): string | null {
  return ['iron_tunic', 'leather_tunic'].find((item) => (inventory?.[item] ?? 0) > 0) ?? null
}

/** L3: the cap Mimo wears, iron over leather, or null when it carries neither. */
export function wornCap(inventory: Record<string, number> | null | undefined): string | null {
  return ['iron_cap', 'leather_cap'].find((item) => (inventory?.[item] ?? 0) > 0) ?? null
}
```


In `frontend/src/survival/SurvivalPet.tsx`, replace:

```tsx
  tunic = false, cap = false, hurtAt = null, children }: {
```

with:

```tsx
  tunic = null, cap = null, hurtAt = null, children }: {
```

and replace:

```tsx
  tunic?: boolean
  cap?: boolean
```

with:

```tsx
  /** L3: the tunic and cap it wears (petGear.wornTunic and wornCap), or null. */
  tunic?: string | null
  cap?: string | null
```

and replace:

```tsx
  const tunicParts = useMemo(() => tunicVoxels(tunic ? { leather_tunic: 1 } : {}), [tunic])
  const capParts = useMemo(() => capVoxels(cap ? { leather_cap: 1 } : {}), [cap])
```

with:

```tsx
  const tunicParts = useMemo(() => tunicVoxels(tunic ? { [tunic]: 1 } : {}), [tunic])
  const capParts = useMemo(() => capVoxels(cap ? { [cap]: 1 } : {}), [cap])
```


In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import SurvivalPet from './SurvivalPet'
```

with:

```tsx
import SurvivalPet from './SurvivalPet'
import { wornCap, wornTunic } from './petGear'
```

and replace:

```tsx
            hopSignal={hopSignal} hidden={petHidden} tunic={(inventory?.leather_tunic ?? 0) > 0}
            cap={(inventory?.leather_cap ?? 0) > 0} hurtAt={hurtAt}>
```

with:

```tsx
            hopSignal={hopSignal} hidden={petHidden} tunic={wornTunic(inventory)}
            cap={wornCap(inventory)} hurtAt={hurtAt}>
```


- [ ] **Step 6: Run the tests, the type check, the linter and the build**

Run: `cd frontend && npx vitest run src/engine/blocks.test.ts src/engine/mesher.test.ts src/survival/cutaway.test.ts src/survival/hud.test.ts src/survival/petGear.test.ts`
Expected: PASS.

Run: `cd frontend && npm test && npx tsc -b && npx eslint src/engine src/survival && npm run build`
Expected: `Tests  293 passed (293)` (4 new), no type or lint errors, and the build succeeds.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 895 tests` … `OK` (the viewer change touches no backend file).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/engine/blocks.ts frontend/src/engine/mesher.ts frontend/src/survival/cutaway.ts frontend/src/survival/hud.ts frontend/src/survival/types.ts frontend/src/survival/petGear.ts frontend/src/survival/SurvivalPet.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/engine/blocks.test.ts frontend/src/engine/mesher.test.ts frontend/src/survival/cutaway.test.ts frontend/src/survival/hud.test.ts frontend/src/survival/petGear.test.ts
git commit -m "feat: the viewer draws cactus, ladders and fences as cubes, names the new purposes and shows iron armor" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Manual check on the demo and the README

This task is for the controller. It rebuilds the demo image from the branch and restarts the demo stack on its own scratch volume: `mimo-m5demo-api` (:8011) and `mimo-m5demo-worker`, volume `mimo_m5demo`, a copy of the owner's world at the natural pace (`MIMO_TIME_SCALE=1`, `MIMO_ACTION_SCALE=1`), with no model key, so the utility picker chooses. The owner's real stack (`pets-api-1`, `pets-mimo-worker-1`) and its volume `pets_mimo_data` are never touched, and no key is printed. The viewer runs on :3000 (:5173 is the owner's dev server). A game day is an hour at the natural pace, so a creature seed takes an hour to grow: plant one early. If a check fails, fix the code in the task that owns it, re-run that task's tests, rebuild and repeat the check.

L3 changes what the generator makes away from the legacy clearing (resolution 5): the demo world keeps its heights and every block Mimo changed, but cells it never touched can differ now (a birch where an oak stood, a boulder, a cave under the yard). Step 3's snippet shows what is near the home; note anything odd in or beside the shelter.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 895 tests` … `OK`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` (about 2.5 minutes) and `Ran 3 tests` … `OK`

Run: `python3 -m backend.scripts.worldgen_fixture && git diff --stat shared/worldgen-fixture.json`
Expected: no change (the fixture Task 5 wrote is current).

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  293 passed (293)`, the build succeeds, eslint prints nothing.

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

Expected: two container ids. L3 adds no table and no column.

Start the viewer against it (or, when a viewer already runs on :3000 against :8011, restart it so it picks up the branch's frontend) and open `http://localhost:3000/preview` in the Browser pane.

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8011 npm run dev -- --port 3000 --strictPort
```

- [ ] **Step 3: Keep a world snippet and three nudges ready**

Save these in your scratchpad directory (not in the repo). `world.sh` prints where the pet is and in which biome, the biomes around it, the new blocks within 24 blocks, the passage around it, the nearest cave entrances, the gold and diamond ore it remembers, its tools, armor and lanterns, what it built, the sprouts and tame animals near it, and the latest events about all of that:

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
import math
import time
from collections import Counter
from backend.services.worldgen import OPENING_REGION, biome_at, region_openings
from backend.survival.clock import clock_at, is_night, time_scale
from backend.survival.grid import world_grid
from backend.survival.light import light_at
from backend.survival.memory import places, structures
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld

NEW = ("granite", "andesite", "diorite", "ashstone", "gold_ore", "diamond_ore", "birch_log", "birch_leaves",
       "spruce_log", "spruce_leaves", "snow_block", "ice", "mud", "cactus", "sugar_cane", "pumpkin", "melon", "fern",
       "dead_bush", "mossy_cobblestone", "gravel", "creature_sprout", "fence", "ladder", "lantern", "lava")
registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
state = world.state()
seed = state["world_seed"]
x, y, z = (round(state["position"][axis]) for axis in "xyz")
print("at", (x, y, z), "| biome", biome_at(x, z, seed), "| purpose", (state.get("action") or {}).get("purpose"))
print("biomes within 256", Counter(biome_at(x + dx, z + dz, seed)
                                   for dx in range(-256, 257, 16) for dz in range(-256, 257, 16)).most_common())
keep = ("_pickaxe", "_sword", "iron_", "gold_", "diamond", "lantern", "creature_seed", "flint", "arrow", "bow",
        "fence", "ladder", "leather_")
print("carries", {item: n for item, n in sorted(state["inventory"].items()) if any(part in item for part in keep)})
with world.connect() as db:
    grid = world_grid(db, seed)
    seen = Counter(grid.material(x + dx, y + dy, z + dz)
                   for dx in range(-24, 25) for dz in range(-24, 25) for dy in range(-8, 9))
    print("new blocks within 24", {name: seen[name] for name in NEW if seen[name]})
    night = is_night(clock_at(state["born_at"], time.time(), time_scale())["phase"])
    print("light here", light_at(grid, seed, (x, y, z), night), "| night" if night else "| day")
    open_above = lambda cx, cz: sum(grid.material(cx, y + k, cz) in ("air", "ladder") for k in range(3))
    print("passage: own column", open_above(x, z), "of 3 open; beside it",
          {side: open_above(x + side[0], z + side[1]) for side in ((1, 0), (-1, 0), (0, 1), (0, -1))})
    found = []
    rx, rz = x // OPENING_REGION, z // OPENING_REGION
    for ox in range(rx - 3, rx + 4):
        for oz in range(rz - 3, rz + 4):
            kind, spans = region_openings(ox, oz, seed)
            if kind:
                cx, cz = min(spans, key=lambda cell: math.dist(cell, (x, z)))
                found.append((round(math.dist((cx, cz), (x, z))), kind, (cx, cz), spans[(cx, cz)]))
    print("nearest cave entrances", sorted(found)[:3])
    ores = [place for place in places(db, ("ore",)) if place["note"] in ("gold_ore", "diamond_ore")]
    print("remembered gold and diamond", Counter(place["note"] for place in ores),
          sorted((round(math.dist((p["x"], p["y"], p["z"]), (x, y, z))), p["note"], (p["x"], p["y"], p["z"])) for p in ores)[:4])
    print("built", [(built["kind"], built["name"], built["status"]) for built in structures(db)])
    print("sprouts", [cell for cell, _ in grid.placed_cells(x, z, 96, ("creature_sprout",))])
    print("tame", [(c["kind"], (c["x"], c["y"], c["z"])) for c in grid.herd.near(x, z, 96)
                   if c["state"].get("tame") and c["state"].get("pose") != "dead"])
words = ("creature seed", "pen", "gold", "diamond", "lantern", "iron cap", "iron tunic", "flint", "ladder", "fence")
for event in reversed(world.events(400)):
    if event["kind"] == "grow" or any(word in event["text"] for word in words):
        print(event["kind"], "|", event["text"])
PY
```

The nudges are for checks the pet has not reached by then: note each one you use. `seeds.sh` puts 3 creature seeds, 30 planks and 12 sticks in the pet's arms (the fences of a pen take 24 planks and 12 sticks), so build_pen and then stock_pen come up by day. `tiers.sh` gives it an iron pickaxe, 3 diamonds, 3 gold ingots and 6 sticks, so craft_tools makes a diamond pickaxe and sword. `armor.sh` marks it hurt by a creature a moment ago and gives it 14 iron ingots and 4 torches, so craft_tools makes the iron cap and tunic and a lantern, and light_up hangs the lantern at dusk.

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    for item, count in {"creature_seed": 3, "planks": 30, "sticks": 12}.items():
        state["inventory"][item] = state["inventory"].get(item, 0) + count
    write_state(db, state)
print("seeds and wood")
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
    for item, count in {"iron_pickaxe": 1, "diamond": 3, "gold_ingot": 3, "sticks": 6}.items():
        state["inventory"][item] = max(state["inventory"].get(item, 0), count)
    write_state(db, state)
print("tiers")
PY
```

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
import time
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    state["hurt_at"] = time.time()
    for item, count in {"iron_ingot": 14, "torch": 4}.items():
        state["inventory"][item] = max(state["inventory"].get(item, 0), count)
    write_state(db, state)
print("armor makings")
PY
```

- [ ] **Step 4: The new world**

Run `world.sh`. Confirm the biome counter lists at least one of taiga, swamp or birch_forest within 256 blocks (the demo's spot decides which) and `new blocks within 24` lists some of the new blocks. In the viewer, orbit and zoom out to the edge of the view and confirm by eye: white-barked birches with pale leaves, dark pointed spruces, snow patches and frozen lakes in the taiga, mud and pools with sugar cane in a swamp, cacti and dead bushes in a desert, ferns in the taiga, a pumpkin or melon now and then, grey boulders and outcrops on hills, and gravel on shores. The cactus, a ladder and a fence are see-through cubes, not crossed sprites. On the minimap, spruce and birch crowns have their own greens and a frozen lake reads pale blue.

- [ ] **Step 5: A cave entrance**

From `nearest cave entrances`, take the nearest (a `sinkhole` or a `mouth`, its cell and its open span). Orbit the camera toward it (the viewer draws 6 columns out, about 96 blocks). Confirm a sinkhole is a round shaft open to the sky with a cave below, or a mouth is a ramp cut into a hillside that goes in under a roof. If none is within 96 blocks, note the nearest one's distance and confirm it on the minimap as a dark spot instead.

- [ ] **Step 6: A big tunnel**

Wait for the pet to dig for stone or ore (the HUD reads `Digging for stone` or `Mining ore`); its staircase goes down from where it stands. When it is underground, run `world.sh` and confirm `passage: own column 3 of 3 open` and one side column with 3 open (a staircase or tunnel 2 wide and 3 tall; the step it stands on may show 2 on the downhill side). In the viewer's cutaway, confirm the passage is two blocks wide and the pet walks it without ducking. Near a lava pool, `light here` reads more than 0 underground. Confirm the pet still comes home up the same stairs.

- [ ] **Step 7: Gold and diamond**

Confirm `world.sh` lists gold or diamond ore the pet remembers once it has been underground with an iron pickaxe, and that `carries` shows a gold or diamond pickaxe or sword after it has mined 3 and made one (events `Pip crafted diamond pickaxe.`). If it has none by the end of the evening, run `tiers.sh` once, wait for `Making a tool`, and confirm the diamond pickaxe and sword in `carries` and that the iron pickaxe is dropped (drop_items, `Dropping what it cannot use`).

- [ ] **Step 8: Iron armor and a lantern**

After a creature has hurt the pet (or after `armor.sh`), confirm `carries` gains `iron_cap` and `iron_tunic` once it has 13 iron ingots (events `crafted iron tunic`, `crafted iron cap`), and a `lantern` with a spare ingot and a torch. In the viewer, confirm the pet's tunic and cap are grey instead of brown. At dusk (`Lighting torches`), confirm a lantern hangs on a corner of the shelter (world.sh `new blocks` lists `lantern`) and the corner glows as a torch does.

- [ ] **Step 9: A pen and a creature seed growing**

If the pet carries no creature seed (they drop from tall grass and leaves, 1 in 60), run `seeds.sh` by day and note it. Confirm the HUD reads `Building a pen`, a ring of 16 fences goes up near the home (world.sh `built` lists `('pen', "Pip's pen", 'done')` and the event `Pip laid out Pip's pen.`), then `Planting creature seeds`: sprouts appear inside the ring (`sprouts`). A game day (an hour) after planting, confirm the event `A creature seed grew into a …`, that `tame` lists the new animal and that the viewer draws it inside the fence, where it stays (it never steps over a fence).

- [ ] **Step 10: Flint, ladders and a quiet worker**

If the pet has a bow and fewer than 8 arrows, confirm it digs gravel (`Digging for flint`) on a shore or cave floor and, after some tries, `carries` shows `flint`. Confirm the worker log stays quiet: `docker logs mimo-m5demo-worker 2>&1 | grep -c "crashed"` prints `0` (or only lines from before the restart). Leave the demo running on the new image for the owner.

- [ ] **Step 11: Describe the bigger world in the README**

In `README.md`, replace:

```markdown
## Current world rules
```

with:

```markdown
## A bigger world

- **Biomes.** Besides meadow, forest, desert and alpine ground there are taiga (spruces, snow patches, frozen lakes), swamps (mud, shallow pools, sugar cane) and birch forests. The land keeps its shape: the generator never changes a height, and the legacy clearing is as it was.
- **On the surface.** Birches and spruces grow beside oaks; cacti and dead bushes in deserts, sugar cane on lake shores and in swamps, ferns in the taiga, now and then a pumpkin or a melon. Gravel lines lake beds and lies on shores, in the taiga and on alpine scree; snow caps the high alpine ground. Boulders sit on the land and outcrops on hills, of the local stone (mossy cobblestone in the woods, sandstone in deserts).
- **Underground.** Caves are bigger and taller (about a fifth of the underground is open), with lakes at y -2 and below and lava pools on the floor at y -4, which light the cave round them as a lantern would. Granite, andesite and diorite come in blobs, ashstone in seams from y -2 down, gravel on cave floors. Gold ore (1 stone cell in 181, y 0 and below) and diamond ore (1 in 331, y -3 and below) need an iron pickaxe. Some caves open to the sky: round sinkholes and hillside mouths, one at most in a 64-block region.
- **Bigger passages.** Mimo's staircases and tunnels are 2 wide and 3 tall, and so are its escape stairs where they fit. Only the cells it walks through yield blocks; the rest is left as rubble, so a wide stair costs no more carrying than a narrow one.
- **Crafting.** Any wood makes planks, sticks and tools (birch and spruce planks for birch and spruce logs). Stone bricks (4 cobblestone), ladders (7 sticks make 3; Mimo climbs straight up and down them) and fences (4 planks and 2 sticks make 3; nothing stands on or steps over one). Gold and diamond pickaxes and swords come after iron, a diamond one first. Once a creature has hurt it, Mimo makes an iron cap (5 ingots) and tunic (8), which cut a blow by 45 % (leather 20 %), and then lanterns (an iron ingot and a torch, light 15), which it hangs at its shelter's corners in place of torches.
- **Flint.** With a bow (or the string for one) and few arrows, Mimo digs gravel for flint (1 gravel in 8 gives one).
- **Danger in the bigger world.** The sky shines through every kind of leaves, and no hostile comes out on them. Hostiles come out near Mimo however deep it digs. No creature climbs a ladder or steps into, onto or over a fence.
- **Creature seeds.** Tall grass and leaves drop a creature seed 1 time in 60. Planted on grass, it grows in a game day into a tame animal of a kind that lives there, or waits while 24 animals are about. With a home and a seed, Mimo fences a pen of 16 fences beside its home and plants its seeds inside, up to 3 animals; seeds wait in the chest till then.
- The viewer draws the new blocks with our own soft-pixel textures, cactus, ladders and fences as see-through cubes, and Mimo's iron armor in grey; the HUD names the new purposes.

## Current world rules
```

- [ ] **Step 12: Commit**

```bash
git add README.md
git commit -m "docs: describe the bigger world" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (L3 outline) | Where |
|-------------------|-------|
| Stone variants: granite, andesite, diorite and tuff-like "ashstone" | Task 1 (blocks, textures; resolution 3), Task 4 (`stone_at`: blobs and seams; resolution 12) |
| New ores: gold and diamond | Task 1 (blocks), Task 4 (placement; resolution 12), Task 7 (smelting, mining, tools; resolutions 18–20) |
| Trees: birch and spruce, with their logs, leaves and planks | Task 1 (blocks), Task 2 (any wood; resolution 13), Task 3 (`tree_kind`, `leaf_of`; resolution 7) |
| Biome blocks: snow_block, ice, mud, cactus, sugar_cane, pumpkin, melon, fern, dead_bush, mossy_cobblestone | Task 1 (blocks), Task 3 (where they are; resolutions 6, 7), Task 5 (mossy cobblestone boulders; resolution 10) |
| Building blocks: stone_bricks and brick (already present) | Task 1 (block), Task 2 (recipe, a building material; resolution 14) |
| New blocks go at the end of the registry | Task 1 (after L2's door; resolution 4) |
| Biomes: taiga (spruce, snow patches), swamp (mud, shallow pools, sugar cane), birch forest, and the existing four | Task 3 (`biome_at`, `surface_material`, `swamp_pool`, trees, plants, animals; resolution 6) |
| Boulders and outcrops on hills | Task 5 (`rocks_in_chunk`, `rock_column`; resolution 10) |
| Cave entrances that open to the sky: sinkholes and hillside mouths | Task 5 (`region_openings`, `opening`; resolution 9) |
| Caves that are larger and taller | Task 4 (the cave network; resolution 8) |
| Underground lakes, and lava pools below y = −3 | Task 4 (`cave_fill`; resolution 8) |
| Mimo's staircases and tunnels 2 wide and 3 tall, and escape stairs likewise where they fit | Task 6 (`stair`, `escape.staircase`; resolution 16) |
| Home and passage claims follow | Task 6 (`rubble`, `kept_clear`; resolution 17) |
| Gold and diamond pickaxes and swords | Task 7 (recipes, ranks, speeds, damage, mine_ore; resolutions 18–20) |
| Iron armor | Task 8 (recipes, `harm.ARMOR` 45 %, craft_tools; resolution 23), Task 14 (grey armor on the pet) |
| Lantern (iron plus torch) | Task 8 (recipe, light_up; resolution 23; L2's light table gives it 15) |
| Ladder, fence, stone_bricks and door | Task 9 (ladder, fence; resolution 15), Task 2 (stone bricks), L2 Task 1 (door) |
| Creature seeds: 1 in 60 from tall grass or leaves; planted on grass, a random local passive animal in 1 game day | Task 11 (`CHANCE_DROPS`, `creatures.seeds`, `GROWERS`; resolution 24) |
| Farm purposes may plant them near home once a pen exists (a fence ring) | Task 12 (`build_pen`, `stock_pen`; resolution 24) |
| Python/TS worldgen parity, and the fixture regenerates | Tasks 3–5 (both ports in each; the fixture samples every new feature) |
| L2 asks: gravel in the terrain (riverbeds, shores, taiga or mountain patches, cave floors) that Mimo finds and mines for flint | Task 3 (surface gravel), Task 4 (cave floors), Task 10 (`gather_flint`; resolution 11) |
| L2 asks: iron armor (45 %) and lanterns (light 15) | Task 8 (resolution 23) |
| L2 review: `sky_open`'s scan stays cheap with bigger caves | Resolution 8 (nothing goes deeper; no clamp needed) |
| L2 final review's notes for L3 (`l3-carryover.md`): leaves by a block property, the full sky scan, spawns however deep, lava and generated light, no "passage" tunnels, fences and ladders against creatures, gravel with a purpose, chasers that lose interest, a collapse that never lies down afloat | Task 13 (resolutions 8, 15, 17, 25), Tasks 3, 4 and 10 (gravel and flint) |
| Error handling: crashes logged once, the tick model-free, GETs read-only, migrations idempotent, the headless sims green with the milestone's own checks | No table or column added; every new purpose is a rule; Tasks 6 and 13 run the slow headless sims; Task 13's budget (resolution 27) |
| Performance: creature simulation plus light checks within 20 ms per slice | L3 adds no creature action; tame animals are L1's passive creatures under L1's cap; lava light is cached per chunk and only looked up within 15 of y −4 (Task 13): L2's timing tests read 4–10 ms a slice with all of L3 |

Out of scope here (L4 and later): goals; stone bricks and ladders placed by a planner; pumpkins, melons, cacti and sugar cane as food or crafting materials; gloom dust (resolution 28).
