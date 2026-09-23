# Mimo's voxel world

Mimo is a persistent pet with a server-owned world. Each pet lives one life: it hatches from an egg into a brand-new world, gets hungry, cold and tired, and can die. A separate worker runs the active life's clock and vitals while no browser is open. The `/preview` page shows the egg, the living pet with its HUD, a memorial after a death, and an archive of every earlier life.

## Run locally

```bash
docker compose up -d --build api mimo-worker
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/preview`. The API runs at `http://localhost:8000/api/mimo`. Both API and Redis ports bind to localhost for this prototype. The Compose volume `pets_mimo_data` holds the life registry (`/data/lives.sqlite3`), one world database per survival life (`/data/lives/<id>.sqlite3`) and the first Mimo's retired world (`/data/mimo.sqlite3`). Redis remains available for the older multi-pet routes, on host port 6380 by default.

The worker ticks the active life every second (`MIMO_TICK_SECONDS`, default 1). If your `.env` still sets `MIMO_TICK_SECONDS=5` from an older example, change it to 1. A laptop that sleeps or a stopped Docker pauses the worker. When it starts again, it catches up in steps of at most one game minute, so a pet can die while nobody watches. For 24/7 operation, run the API and worker on an always-on host with a persistent `/data` volume.

`MIMO_TIME_SCALE` (default 1) speeds up the clock and every vital. It is for manual tests only: with `MIMO_TIME_SCALE=60` a game day lasts one real minute. Give the API and the worker the same value.

`MIMO_ACTION_SCALE` (default 1) makes every step that many times shorter. It is for manual tests only: at `MIMO_TIME_SCALE=60` the clock runs fast but the steps do not, so also set `MIMO_ACTION_SCALE=60` to see a whole day of purposes. Only the worker reads it.

Model settings: with `TYPESAFE_API_KEY` the worker asks Jev (`TYPESAFE_MODEL`, `TYPESAFE_API_URL`) to choose Mimo's purposes. With only `OPENAI_API_KEY` or `MIMO_MODEL_API_KEY` it asks Luna (`MIMO_MODEL`, `MIMO_MODEL_URL`). With neither, rules choose. `MIMO_MAX_DECISIONS_PER_DAY` (default 200) and `MIMO_MAX_LUNA_DECISIONS_PER_DAY` (default 64) cap the model calls per UTC day. See Brain.

The preview polls `/api/mimo` every second. Block changes carry sequence numbers, so the page fetches only new changes from `/api/mimo/blocks`. A Web Worker generates chunk columns from the world seed and meshes them with 8×8 pixel textures and corner shading; the page stays smooth on phones. Sky, fog and terrain brightness follow the game clock. Glowing blocks (lanterns, furnaces, lava) keep their light at night. Add `?debug` to the URL to see frame rate, draw calls and mesh time.

## Lives

- Life 1 is the first Mimo and its world with the station and all its builds. The first time the survival code starts, it is registered as retired. Its database file is never written again. The archive reads it read-only and still draws its builds with the browser's blueprint compiler.
- When no pet is alive, `/api/mimo` answers `{"phase": "egg"}` with an egg the server rolled (shape, scales, color, size and mist, each common to mythic) and the previous life's summary. `POST /api/lives/hatch` hatches it: a new 64-bit world seed, a spawn 3,000 to 6,000 blocks from the origin on grass or moss with a tree nearby, traits from the egg (rarer eggs raise every trait's floor) and a name.
- A game day lasts one real hour: 3 minutes of dawn, 34 of day and 3 of dusk, then 20 dark minutes of night and pre-dawn.
- Vitals run 0 to 100: health, hunger, warmth, energy, air and mood. An unfed pet's hunger empties in about two game days, then starvation costs 1 health every 30 seconds. Warmth moves toward 100 by day and 30 at night (colder in alpine biomes). A roof within 4 blocks overhead with walls on 3 sides, or a furnace within 4 blocks, keeps the pet warm; natural overhangs and caves count. Health recovers while the pet is fed and warm. At 0 health the pet dies for good, its life is archived and a new egg waits.
- A brain runs the pet: reflexes for emergencies, purposes it chooses, and a planner that turns a purpose into steps. See Brain.
- The owner gets one snack (+30 hunger) and one bandage (+25 health) per UTC day, can say hello (+5 mood), and can still help craft with the pet's inventory.
- `GET /api/lives` lists every life, newest first. `GET /api/lives/{id}` returns one life's summary and final state (the old snapshot shape for life 1). `GET /api/lives/{id}/blocks?since=` pages its block changes.

## Actions

- Mimo is one block tall. It stands in an open cell with a solid block or water below it. The server finds paths with 3D A*: one block to a side, one block up when there is headroom, or down a drop of at most 3 blocks. On water it swims on the surface at a third of its walking speed and never plans a route under water. A search looks at no more than 20,000 cells within 96 blocks; farther places are reached in segments.
- Every step takes time: walking 0.3 s per block (0.9 s swimming), mining the block's hardness divided by the tool speed (hand 1; wooden, stone and iron pickaxes 2, 4 and 6 on stone-type blocks), placing 0.3 s, eating 1.6 s, crafting 1 s and smelting 5 s. Sleep lasts until Mimo is rested and it is day. Mimo mines and places within 4 blocks. Mining still needs the right pickaxe and gives the block's drop. `hardness` and `tool` live in `shared/blocks.json`.
- The worker runs the steps once a second, so several short steps can finish in one tick. The current step, the queue and the last 20 finished steps are saved with the world, so a restarted worker carries on where it stopped.
- A block dug out from under Mimo makes it fall. A fall deals (blocks − 3) × 10 damage, and water breaks a fall. Air drains while Mimo's cell is water; Mimo then swims straight up, and the surface reflex digs through a ceiling or heads for the shore.
- `/api/mimo` streams the current step (`action`: kind, start and end time, and a timed path or a target block) and `recent_actions`. The viewer moves the pet along the path by server time and animates each step: a hop per block, a swing and growing cracks while mining, particles and an item pop when a block breaks, a bounce when a block is placed, nibbling with crumbs, lying down with floating z's, bobbing in water and a quickening drop when falling. The viewer draws the pet 1.5 s behind server time, and the newest finished walks keep their path in `recent_actions`, so a step that started and ended between two polls still plays out.
- `MIMO_TIME_SCALE` speeds the clock and the vitals, not the steps, so the animations stay watchable in a fast test run. `MIMO_ACTION_SCALE` shortens the steps for a fast manual run.

## Brain

The brain has three layers. It runs in the worker; the tick itself never waits for a model.

- **Reflexes** take over at once, most urgent first: surface (air below 40: dig through a ceiling or swim to shore), avoid drop (never mine the block under Mimo over a drop of more than 3 blocks or into lava, and walk around a cell that lost its floor), eat now (hunger below 15 with food), warm up (warmth below 25: place a carried furnace, or go to a known shelter or furnace), head home (from 3 game minutes before dusk until night, when a shelter is known within 64 blocks) and collapse (energy below 10: sleep on the spot). A reflex sets the current plan aside and gives it back when it is done; head home instead ends the purpose, so Mimo chooses again at home. Walks, sleep and waits can be cut short; a cut walk stops on the last cell it reached.
- **Purposes** are goals in a registry (`backend/survival/purposes.py`): gather wood, gather stone (a staircase dug into the ground that never turns back on itself or digs out its own steps), mine ore (coal and iron Mimo has seen), craft tools (the next pickaxe, with a crafting table it places and then picks up again, in a niche it digs when underground), explore (three walks), go home, sleep, rest (until something happens, at most 10 game minutes) and eat. Each has a validity check, facts for the chooser, a score and a planner. Late in the day, work away from home scores lower, so sleep and go home win at dusk. Food, farming and building purposes arrive with the next milestones.
- **Choosing.** Mimo chooses a new purpose when a plan finishes or fails, a reflex ends, a vital falls past 50, 30 or 15, at dawn and dusk, after a discovery, after a hello, and after a game hour without a choice. Jev chooses when `TYPESAFE_API_KEY` is set, else Luna when an OpenAI key is set, else rules (the utility picker: needs first, then traits, with a small random nudge). Rules also choose when a daily cap is spent, when a call fails (or hangs 15 s past its timeout), when 8 model calls were made in the last game hour (even for a falling vital), after a short purpose (rest, explore, eat, go home) ends with nothing more significant waiting, and when the last model call was less than 60 s ago (a falling vital does not wait). Model calls run in a background thread, so the pet keeps moving while a model thinks. Each choice gets a one-line thought; after a model's choice at dawn, after a hello or after a discovery, Luna may add a reflection instead (at most 12 a day).
- **Planner.** A purpose becomes batches of the timed steps above. A failed step (codes `no_path`, `out_of_reach`, `gone`, `missing_item`, `blocked`, `bad_step`) plans the purpose again once. A second failure drops the purpose, scores it lower for 10 game minutes and asks for a new choice. When two walks of the purpose found no way and Mimo can reach almost nothing, it is trapped: it digs a staircase out, or builds one from blocks it carries. Picking up a placed crafting table or furnace survives a new purpose, a failure or a reflex.
- **Memory** lives in each world's database and starts empty: places (home, shelters, ore it saw, dangerous drops, water) and the recipes Mimo has used. Home is the first sheltered spot Mimo finds, often its own mine staircase.
- `/api/mimo` adds `purpose`, `reflex`, `picker` and `choosing`. The HUD shows the purpose, the step and the latest thought. When Mimo is underground, the viewer cuts the terrain away above it so it stays in sight.

## Current world rules

- Each world has a persisted 64-bit seed. The viewer generates nearby 16×16 terrain chunks from that seed as the camera follows the pet. The server uses the same height, biome, cave, and ore math. The first world's 192-block home region keeps its earlier terrain so saved buildings stay in place; the next 48 blocks blend into the generated landscape. Survival worlds reach ±30,000 blocks.
- Generated terrain has meadow, forest, desert, and alpine biomes, hills, sea-level water, trees, surface materials, caves, and underground ores. The viewer generates whole chunk columns, so dug holes show solid dirt, stone and ore walls.
- Every block is listed once in `shared/blocks.json`. The server and the viewer both read it.
- Trees, flowers, tall grass and the home cottage are part of worldgen on both sides. Python (`backend/services/worldgen.py`) and TypeScript (`frontend/src/engine/worldgen.ts`) must agree cell for cell; `shared/worldgen-fixture.json` checks that, including cells near the ±30,000 limit.
- Water is translucent and gently animated in the viewer; it does not flow yet.
- Logs become planks and sticks; a placed crafting table unlocks furnace and pickaxe recipes. A placed furnace consumes fuel to smelt ore or sand. The **Blocks & crafting** panel lets the owner help with the same persistent inventory.

This is a functional base for a Minecraft-style world, not a full one-to-one recreation. Owner actions currently have no account authentication, so add authentication before exposing this API publicly.

## Checks

```bash
python3 -m unittest discover -s backend/tests
cd frontend && npm test && npm run build
```

After changing worldgen in either language, run `python3 -m backend.scripts.worldgen_fixture` and commit the updated fixture.
