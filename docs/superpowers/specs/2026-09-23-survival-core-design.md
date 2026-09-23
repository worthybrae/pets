# Survival Core — Design Spec

Sub-project 2 of the "Mimo's world feels like Minecraft" roadmap. It replaces the earlier "physical Mimo" sub-project.

| # | Sub-project | Status |
|---|-------------|--------|
| 1 | Voxel engine and soft pixel look | Done (branch `worthy/22_09_2026/voxel_engine_soft_pixel`) |
| 2 | Survival core | This spec |
| 3 | Creatures: passive and hostile creatures, night spawning, light levels, fight and flee, creature seeds | Later |
| 4 | Chat with Mimo | Later |
| 5 | Block updates: flowing water, falling sand entities | Later |
| 6 | App shell: Capacitor iOS/Android, PWA, hosted API | Later |

## Why

Mimo builds the same seven blueprints forever. Builds are free, needs are shallow (energy and mood), and nothing is at stake. The owner wants a survival game: Mimo has health, gets hungry and cold, resources are scarce, and building happens because Mimo needs something.

## Decisions made with the owner

- **Brain:** three layers. Rule-based reflexes react instantly. Jev picks a purpose when something changes, using traits, mood, memory and vitals. A rule-based planner turns the purpose into concrete steps. Luna is used only for rare creative calls.
- **Reflexes must cover short-term changes.** Example from the owner: when Mimo is fighting and its health gets low, it should naturally switch to fleeing.
- **Threats in the full game:** hunger, night and cold, creatures, and hazards. This sub-project covers hunger, night and cold, falls and drowning. Creatures come in sub-project 3, which plugs into the same reflex and purpose system.
- **Day length:** one real hour. 40 minutes of day, 20 minutes of night.
- **Resources renew slowly.** Wild food regrows over days. Trees return only when Mimo plants saplings. Mined ore never returns. Fish stocks recover slowly. The world is endless, so there is always more far away, at a risk.
- **Permadeath.** At zero health Mimo dies for good.
- **Fresh start every time.** A new pet hatches from an egg into a brand-new world with a new seed. It remembers nothing. The old world is archived and can be viewed read-only.
- **Today's Mimo retires.** Its world, with the station and its 61 builds, becomes the first archived life. The first survival pet hatches into a new world.
- **The owner is a limited helper.** Crafting help stays. The owner also gets a small daily care budget: one snack and one bandage per real day. Saying hello lifts mood.
- **The owner wants to chat with Mimo.** That is sub-project 4. This spec leaves room for it (an "owner said something" trigger).

## Scope

In scope: lives, eggs and archives; the world clock; vitals; the three-layer brain; physical movement and timed actions on real blocks; falls and drowning; food, foraging, fishing, farming and cooking; renewal; purposeful building with a procedural generator; owner care; and the viewer changes these need.

Out of scope: creatures and combat, light-level propagation, chat, flowing water, the app shell.

## Milestones

Each milestone gets its own implementation plan and ships working software on its own.

| M | Name | Delivers |
|---|------|----------|
| M1 | Lives and vitals | Life registry, retiring today's Mimo, egg hatch into a new world, world clock, vitals and their rates, death and archive, owner care, HUD, day and night visuals, archive browser |
| M2 | Physical Mimo | Server pathfinding over real blocks, timed action steps (walk, mine, place, eat, sleep), falls and drowning, viewer animation of actions |
| M3 | Brain | Reflexes, purposes, planner, memory, purpose pickers (Jev, Luna, rule-based fallback) |
| M4 | Food and renewal | Berry bushes, mushrooms, crops, saplings, fishing, cooking, regrowth, depletion |
| M5 | Purposeful building | Shelter, farm, storage and light structures generated from needs and inventory, placed block by block |

M3 onward depends on M2's actions. M4 and M5 depend on M3's purposes.

---

## 1. Lives and worlds (M1)

### Storage

- A registry database `/data/lives.sqlite3` holds one row per life: `id`, `name`, `kind` (`legacy` or `survival`), `db_path`, `seed`, `spawn_x`, `spawn_z`, `born_at`, `died_at`, `cause`, `egg` (JSON), `traits` (JSON).
- Every life has its own world database with the schema `MimoStore` uses today (blocks with `seq`, events, meta) plus survival tables. Survival worlds live at `/data/lives/<id>.sqlite3`.
- Life 1 is today's `/data/mimo.sqlite3`, registered as `kind = legacy` and marked retired the first time the survival code starts. The file is not moved or rewritten. Nothing ticks it after retirement.
- `MIMO_DB_PATH` keeps pointing at the legacy file so an older build could still open it. A new `MIMO_DATA_DIR` (default `/data`) locates the registry and survival worlds.

### Hatching

- When no life is alive, `/api/mimo` answers `{ "phase": "egg" }` with the previous life's summary if any.
- `POST /api/lives/hatch` rolls an egg on the server (port of the viewer's egg tiers: shape, scales, color, size, pattern, glow, each common to mythic), derives traits from it, picks a name, creates a new world database and a new life row, and returns the new life.
- **Traits** (0–100): `curiosity`, `creativity`, `sociability`, `patience` (existing) plus `bravery`, `caution`, `thrift`, `diligence`. Rarer eggs raise the trait floor. Traits feed purpose picking and utility scores.
- **Spawn point:** new worlds use a random 64-bit seed. Mimo spawns 3,000 to 6,000 blocks from the origin in a random direction, so the legacy home clearing (radius 192 plus a 48-block blend) is never nearby. The spawn column must be dry grass or moss in a meadow or forest biome, with at least one tree within 24 blocks. Search outward in a spiral until one fits.
- The server's coordinate limit rises from ±4,096 to ±30,000 (still exact in Float32 on the client).

### Death and archive

- When health reaches 0, the life gets `died_at` and `cause` (`starvation`, `cold`, `fall`, `drowning`, later `creature`). A final event is logged. The worker stops ticking that world.
- Archived lives are read-only. `GET /api/lives` lists all lives. `GET /api/lives/{id}` returns a life's final state and summary. `GET /api/lives/{id}/blocks?since=` pages its block edits.
- The viewer's archive browser can open any life. The legacy life still renders its blueprint builds through the existing client-side overlay compiler.

## 2. World clock (M1)

- One game day equals 3,600 real seconds, starting at dawn when the life is born.
- Phases by seconds into the day: dawn 0–180, day 180–2,220, dusk 2,220–2,400, night 2,400–3,420, pre-dawn 3,420–3,600. Night therefore lasts 20 minutes including twilight.
- The server computes `day_number`, `time_of_day` (0–1) and `phase` from `born_at` and the current time. The viewer receives `server_time` to align its own clock.

## 3. Vitals (M1)

All values run 0–100. Rates are per real second unless noted. They are tuned so an idle Mimo that never eats starves in about two game days.

| Vital | Drains | Recovers | At 0 or critical |
|-------|--------|----------|------------------|
| Health | Starving: −1 per 30 s. Freezing: −1 per 15 s. Drowning: −2 per s. Falls: `(fall − 3) × 10` | +1 per 20 s while hunger > 60 and warmth > 50 | 0 = death |
| Hunger (fullness) | −0.014 idle, ×1.5 while walking, mining or building | Eating (food table below) | 0 = starving |
| Warmth | Moves toward the target warmth at 0.5 per s | Same | < 20 = freezing |
| Energy | −0.008 idle, −0.03 while working | Sleeping +0.2 (in a bed +0.35) | < 10 = exhausted |
| Air | −10 per s with its head in water | +25 per s in air | 0 = drowning |
| Mood | Starving, freezing, hurt, alone for long | Eating well, warm, finishing builds, owner hellos | Affects purpose choice |

**Target warmth** starts from the time and place: 100 by day, 30 at night, −20 in alpine biomes at night, 40 in alpine biomes by day. Being sheltered (roof within 4 blocks overhead and enclosed on at least 3 sides) adds 45. Being within 4 blocks of a lit campfire or furnace sets it to 100. The shelter check is computed on the server. Until M5 adds shelters, natural overhangs and caves count.

## 4. Owner care (M1)

- Each real day (UTC) the owner gets one **snack** (+30 hunger) and one **bandage** (+25 health). `POST /api/mimo/care` with `{ "kind": "snack" | "bandage" }`. The response says how many remain.
- Hello stays (+5 mood, wakes Mimo's decision loop). Crafting help stays, with the same station rules.
- A dead or unhatched pet cannot receive care.

## 5. The brain (M3)

The brain has three layers.

### Reflexes

Rules evaluated every tick in priority order. The first match takes over: it pauses the current plan, runs its own short plan, then returns control to the purpose layer.

| Reflex | Trigger | Response |
|--------|---------|----------|
| Surface | Air < 40 | Swim to the nearest air cell above water, then to shore |
| Avoid drop | Next step would fall more than 3 blocks, or into lava | Cancel the step, re-plan the path with that cell blocked |
| Flee (sub-project 3) | In a fight and health < 35, or health < 25 with a threat nearby | Run toward the known shelter or away from the threat |
| Eat now | Hunger < 15 and food in inventory | Eat the best available food |
| Warm up | Warmth < 25 | Go to the nearest warm spot (shelter, fire), or light a campfire if Mimo has one |
| Head home | Dusk within 3 game minutes, outdoors, known shelter within 64 blocks | Walk home |
| Collapse | Energy < 10 | Sleep where it stands, or in a bed within 8 blocks |

Reflexes are data: a list of objects with a trigger function, a priority and a planner. Sub-project 3 adds creature reflexes to the same list.

### Purposes

A purpose is a goal with a validity check, facts for the chooser and a planner. The purpose layer runs only on triggers: a plan finished or failed, a reflex ended, a vital crossed 50, 30 or 15, dawn or dusk, a new discovery, an owner hello, or one game hour since the last choice. There is at least 60 real seconds between model calls, except for vital-crossing triggers.

Core purposes: `eat`, `forage`, `fish`, `farm`, `cook`, `gather_wood`, `gather_stone`, `mine_ore`, `craft_tools`, `build_shelter`, `build_farm`, `build_storage`, `light_up`, `explore`, `go_home`, `sleep`, `rest`. Each purpose's validity check decides whether it is offered right now. For example, `cook` needs raw food and a lit fire or furnace nearby, and `build_shelter` needs no shelter yet or a damaged one.

**Pickers:**

1. **Jev** when `TYPESAFE_API_KEY` is set: one question with the valid purposes as choices, each with facts. Context: traits, mood, vitals, phase, inventory summary, known places, and the last 8 events.
2. **Luna** when only `OPENAI_API_KEY` is set: the same payload with structured output restricted to the valid purposes. It counts against the Luna daily cap.
3. **Utility picker** (rules, always available). Each purpose gets a score from needs, trait weights and memory. The best score wins, with a small random factor so behavior varies. It is used when no key is set, when the daily budget is spent, or when a model call fails.

The picker's choice and a one-line thought are logged. Thoughts come from a template per purpose. Luna may add an occasional reflection (at most 12 per real day).

### Planner

Each purpose compiles to a queue of steps: `walk(path)`, `mine(cell)`, `pick(cell)`, `place(cell, block)`, `craft(recipe)`, `smelt(item)`, `eat(item)`, `fish(water cell)`, `till(cell)`, `plant(cell, seed)`, `harvest(cell)`, `sleep`, `wait(seconds)`. Steps run on the M2 action system. A failed step (blocked path, block already gone, missing material) re-plans the purpose once. A second failure reports back to the purpose layer as a trigger.

### Memory

Per life, stored in the world database:

- **Places:** home, shelters, beds, chests, fires, food patches (with last-seen ripe count and time), water bodies, ore sightings, danger spots (big drops, deep water), each with coordinates and last-visit time.
- **Events:** the existing event log, plus typed entries (ate, got hurt, found, built, discovered).
- **Knowledge:** recipes Mimo has used successfully.

Memory is what "fresh start" wipes. A new life begins with empty memory.

## 6. Physical Mimo (M2)

### Body and movement

- Mimo occupies one cell. It stands in a non-solid cell whose cell below is solid (registry `solid`) or water.
- **Pathfinding:** 3D A* on cells. Moves: to the 4 horizontal neighbors on the same level; step up 1 when the cell above Mimo is free; drop down up to 3; swim through water cells (cost ×3). No diagonal corner cutting. Search budget: 20,000 nodes and 96 blocks. Beyond that, the planner walks in segments toward waypoints.
- Reach: Mimo can mine or place within 4 blocks of its cell, with line of sight not required (kept simple).

### Timed actions

The world worker ticks every 1 s. Each tick advances the current step according to elapsed time, so several steps can finish in one tick.

| Step | Duration |
|------|----------|
| Walk | 0.3 s per block (0.9 s per block swimming) |
| Mine | Block hardness ÷ tool speed. Hardness (registry `hardness` seconds): dirt/grass/sand/gravel 0.6, leaves 0.3, plants 0.1, wood 2.0, stone/cobblestone 4.0, ores 5.0, bedrock ∞. Tool speed: hand 1, wooden pickaxe 2 (stone-type), stone pickaxe 4, iron pickaxe 6; an axe (M5 recipe) doubles wood speed |
| Place | 0.3 s |
| Eat | 1.6 s |
| Craft / smelt | 1 s / 5 s |
| Sleep | Until energy ≥ 95 or dawn, whichever is later at night |

Mining still requires the right tool (`requires` in the registry) and yields the `drop`. Placing consumes the item from inventory. All block changes go through `_write_block`, so viewers sync them as before.

### Falls and drowning

- If the cell below Mimo stops being solid (dug, or Mimo stepped off a ledge by reflex), Mimo falls to the next solid cell. Damage is `(blocks fallen − 3) × 10`.
- Air drains while Mimo's cell is water. The surface reflex (M3) handles escaping. Before M3, the planner avoids water it cannot cross, and a fallback rule swims Mimo up.

### Streaming actions to the viewer

`/api/mimo` gains:

- `server_time`
- `action`: the current step, with `kind`, `started_at`, `ends_at`, and `path` (list of cells with arrival times) for walks, or `target` for block actions
- `vitals`, `clock`, `life`, and `care`

The viewer interpolates Mimo's position along the path by arrival times and plays animations:

- **walk:** hop cycle, facing the direction of travel
- **mine:** swing toward the target, crack overlay progressing with time, particles and an item pop when the block breaks (the block change arrives through block sync)
- **place:** block scales in from 0.6 with a small bounce
- **eat:** nibble with crumbs
- **sleep:** lying down with floating "z"s
- **fall:** accelerated drop
- **swim:** bobbing

## 7. Food and renewal (M4)

### New blocks

`berry_bush`, `berry_bush_ripe`, `brown_mushroom`, `red_mushroom`, `farmland`, `wheat_0` to `wheat_3`, `carrot_0` to `carrot_3`, `sapling`, `campfire` (glow), `torch` (glow), `bed`, `chest`. Plants and crops are `cutout` and `solid: false`. Worldgen places berry bushes (meadow, forest edge) and mushrooms (forest floor, caves) in both languages, with the parity fixture updated.

### Items and food

| Item | Hunger | Notes |
|------|--------|-------|
| Berries | +8 | From a ripe bush; the bush becomes unripe |
| Brown mushroom | +6 | Red mushroom is poisonous: −10 health (memory learns this) |
| Carrot | +10 | Replant to grow more |
| Wheat | 0 | 3 wheat → 1 bread at a crafting table |
| Bread | +25 | |
| Raw fish | +8 | Fishing: 20–60 s per catch, success depends on the water body's stock |
| Cooked fish | +30 | 5 s at a lit campfire or furnace |
| Seeds | 0 | 20% chance when breaking tall grass |
| Sapling | 0 | 1 in 12 chance when leaves are removed |

### Renewal

A `growth` table in the world database holds `(x, y, z, block, ready_at)`. The worker applies due entries each tick.

- A picked berry bush regrows ripe after 2 game days.
- Crops advance one stage every 12 game minutes on farmland with water within 4 blocks, and every 36 game minutes otherwise.
- A sapling becomes a tree after 1 game day if there is space.
- Fish stock is tracked per 16×16 water region (starts at 12 and recovers 1 per game day).
- Tilled farmland reverts to dirt after 2 game days without a crop.
- Mined ore never regrows. Mushrooms reappear on dark forest floor at a low rate (one per chunk per game day, capped at 3 per chunk).

## 8. Purposeful building (M5)

Needs decide what to build. A procedural generator makes the design.

| Structure | Purpose | Requirements |
|-----------|---------|--------------|
| Shelter | `build_shelter` | Enclosed interior at least 3×3×2, roof over all of it, a door gap, and a bed if Mimo has one. Must pass the server's shelter check |
| Farm | `build_farm` | 3×3 to 5×5 farmland beside water (or a dug 1-block water source with a bucket later), low fence optional |
| Storage | `build_storage` | A chest under a roof, inside or beside the shelter |
| Lights | `light_up` | Torches around home at night (they matter for creatures in sub-project 3; for now they glow and lift mood) |
| Campfire | part of `build_shelter` or `warm_up` | A campfire beside home |

**Generator:** inputs are the site (flat-enough area near home, chosen from observed columns), size tier, materials Mimo actually has (for example planks, cobblestone, logs, dirt as a last resort), and style knobs. The knobs are roof shape (flat, gable, dome), wall material, window pattern and door side. Luna may pick the style knobs and a name once per structure. Otherwise traits choose: creativity varies the style, thrift picks cheaper materials. The output is an ordered block list (floor, walls, roof, fittings) placed by the planner one block at a time. If materials run out, the purpose pauses and gathering purposes become more valuable.

**Inventory limit:** Mimo carries at most 16 stacks of 32. Chests hold 24 stacks. Full inventory makes `build_storage` and dropping low-value items valid purposes, which gives storage a real reason to exist.

## 9. Viewer (M1 and M2 mainly)

- **HUD:** health, hunger, warmth, energy and air bars; day number and a sun/moon clock; current purpose and step in plain words; the latest thought.
- **Day and night:** sky and fog color follow the phase. Terrain brightness is multiplied by a daylight factor (1.0 day, 0.35 night, smooth at dawn and dusk) through one uniform on the terrain materials. Glow blocks ignore it. The pet gets a soft point light at night so it stays visible.
- **Egg and hatch:** when the phase is `egg`, show the egg (reuse the existing `EggScene`), its rolled attributes and a Hatch button that calls the API. Then the camera flies to the new world.
- **Death:** a memorial card with name, days survived, cause, and notable events, plus buttons to view the world or hatch a new egg.
- **Archive browser:** a list of lives. Opening one renders its world read-only (legacy lives with their blueprint overlays).
- **Care:** "Give snack" and "Bandage" buttons showing how many remain today.
- **Actions:** the animations listed in section 6.

## 10. API summary

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/mimo` | Active life state (`phase: alive`), or `phase: egg` with the last life's summary |
| GET | `/api/mimo/blocks?since=` | Block changes for the active life |
| POST | `/api/mimo/hello` | As today |
| POST | `/api/mimo/action` | Crafting help, as today |
| POST | `/api/mimo/care` | Snack or bandage |
| POST | `/api/lives/hatch` | New life |
| GET | `/api/lives` | All lives, newest first |
| GET | `/api/lives/{id}` | One life's summary and final state |
| GET | `/api/lives/{id}/blocks?since=` | That life's block changes |

The `/api/mimo` response keeps `plans`, `currentIndex`, `progress` only for legacy lives. Survival lives use the new fields.

## 11. Cost controls

- Model calls happen only on purpose triggers, with at least 60 s between calls (except vital crossings). Expected: 3–8 calls per game hour.
- Existing daily caps stay (`MIMO_MAX_DECISIONS_PER_DAY`, `MIMO_MAX_LUNA_DECISIONS_PER_DAY`). When a cap is hit, the utility picker takes over instead of sleeping, so Mimo keeps surviving.
- With no model key at all, the game is fully playable on the utility picker.

## 12. Error handling

| Failure | Behavior |
|---------|----------|
| Model call fails or returns an invalid purpose | Utility picker decides this time; log once |
| Planner cannot find a path or material | Re-plan once, then report failure as a trigger; purpose is scored lower for 10 game minutes |
| Worker restarts mid-action | On start, the step resumes from its stored `started_at`; walks snap to the last reached cell |
| Registry or world database missing | API returns 503 with a clear message; worker logs and waits |
| Clock jump (laptop slept for hours) | The worker catches up in simulated steps of at most 60 s, applying vitals, growth and death. A laptop that sleeps for a day can wake up to a dead Mimo |

## 13. Testing

- **Simulation tests** with an injected clock: vitals rates, warmth targets, shelter check, starvation and cold deaths, catch-up after a clock jump.
- **Pathfinding tests** on small hand-built worlds: step up, drop limits, swimming cost, blocked routes, segment walking.
- **Action tests:** mining durations with and without tools, placing consumes items, falls deal the right damage.
- **Brain tests:** every reflex triggers and yields back; every purpose's validity check; the utility picker's choices for scripted situations; the Jev and Luna payloads (with fake HTTP) and their fallback.
- **Lives tests:** retiring the legacy database without modifying it, hatching, spawn search, death and archive, read-only archive endpoints.
- **Viewer unit tests:** clock phase and daylight factor, action interpolation along a path, HUD formatting.
- **Parity fixture** regenerated when worldgen gains bushes and mushrooms.
- **Manual:** run a scratch world at 60× speed (`MIMO_TIME_SCALE=60`, a test-only setting that speeds the clock and all rates) and watch a full day, a meal, a night in shelter and a death.

## Done when

All five milestones ship their tests green. A fresh egg hatches into a new world. The new Mimo gathers, eats, survives nights in a shelter it built from blocks it mined, farms, and eventually dies of its own choices. Its life is then archived and viewable, and a new egg is ready. Today's Mimo and its world stay viewable as the first life.
