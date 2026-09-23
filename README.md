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

Model settings (`TYPESAFE_API_KEY`, `OPENAI_API_KEY`, `MIMO_MODEL`, `MIMO_MODEL_URL`, `MIMO_MAX_DECISIONS_PER_DAY`, `MIMO_MAX_LUNA_DECISIONS_PER_DAY`) are kept for the brain milestone. The survival worker does not call a model yet.

The preview polls `/api/mimo` every second. Block changes carry sequence numbers, so the page fetches only new changes from `/api/mimo/blocks`. A Web Worker generates chunk columns from the world seed and meshes them with 8×8 pixel textures and corner shading; the page stays smooth on phones. Sky, fog and terrain brightness follow the game clock. Glowing blocks (lanterns, furnaces, lava) keep their light at night. Add `?debug` to the URL to see frame rate, draw calls and mesh time.

## Lives

- Life 1 is the first Mimo and its world with the station and all its builds. The first time the survival code starts, it is registered as retired. Its database file is never written again. The archive reads it read-only and still draws its builds with the browser's blueprint compiler.
- When no pet is alive, `/api/mimo` answers `{"phase": "egg"}` with an egg the server rolled (shape, scales, color, size and mist, each common to mythic) and the previous life's summary. `POST /api/lives/hatch` hatches it: a new 64-bit world seed, a spawn 3,000 to 6,000 blocks from the origin on grass or moss with a tree nearby, traits from the egg (rarer eggs raise every trait's floor) and a name.
- A game day lasts one real hour: 3 minutes of dawn, 34 of day and 3 of dusk, then 20 dark minutes of night and pre-dawn.
- Vitals run 0 to 100: health, hunger, warmth, energy, air and mood. An unfed pet's hunger empties in about two game days, then starvation costs 1 health every 30 seconds. Warmth moves toward 100 by day and 30 at night (colder in alpine biomes). A roof within 4 blocks overhead with walls on 3 sides, or a furnace within 4 blocks, keeps the pet warm; natural overhangs and caves count. Health recovers while the pet is fed and warm. At 0 health the pet dies for good, its life is archived and a new egg waits.
- Until the brain milestone, the pet stands where it hatched and sleeps at night or when exhausted.
- The owner gets one snack (+30 hunger) and one bandage (+25 health) per UTC day, can say hello (+5 mood), and can still help craft with the pet's inventory.
- `GET /api/lives` lists every life, newest first. `GET /api/lives/{id}` returns one life's summary and final state (the old snapshot shape for life 1). `GET /api/lives/{id}/blocks?since=` pages its block changes.

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
