# Mimo's voxel world

Mimo is a persistent pet with a server-owned world. A separate worker observes its stored world, asks a configured chat model what to do, validates the choice, and saves its actions. The `/preview` page renders that state; closing the page does not stop the worker.

## Run locally

```bash
docker compose up -d --build api mimo-worker
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/preview`. The API runs at `http://localhost:8000/api/mimo`. Both API and Redis ports bind to localhost for this prototype. The Compose volume `pets_mimo_data` keeps Mimo's world, inventory, activity, and block edits across container restarts. Redis remains available for the older multi-pet routes, on host port 6380 by default.

Mimo defaults to the GPT-6 Luna API model and pauses until an API key is configured. To enable autonomous choices, make a local `.env` from `.env.example` and set `OPENAI_API_KEY`. API usage is billed separately from a ChatGPT subscription. A compatible local chat endpoint can instead be used with `MIMO_MODEL_URL` and `MIMO_MODEL`; a model served on the host must use a Docker-reachable host name such as `host.docker.internal`. Recreate the containers after changing model settings:

```bash
docker compose up -d --force-recreate api mimo-worker
```

The worker wakes every five seconds to check if an action is due. It advances an active build every 20 seconds and normally asks the model for one new choice every 15 minutes after a small action. The default cap is 64 model attempts per UTC day. Set `MIMO_THINK_SECONDS`, `MIMO_TICK_SECONDS`, and `MIMO_MAX_DECISIONS_PER_DAY` to adjust those limits.

For 24/7 operation, run the API and worker on an always-on host with a persistent `/data` volume and a configured model. A laptop sleeping or Docker being stopped pauses Mimo; the stored world remains intact.

## Current world rules

- Mimo has persistent energy, mood, traits, inventory, projects, individual block edits, and an activity log.
- Its observation includes known structures, the pond, nearby vertical block columns, and validated open sites. Build choices are limited to available space and a set of structure compilers.
- The world has 24 block types, including transparent glass and water, glowing blocks, ore, wood, sand, and gravel. Ground has small hills; Mimo can place blocks above ground and dig to four blocks below it.
- Placed sand and gravel fall one cell per world tick when unsupported. Water is translucent and gently animated in the viewer; it does not flow yet.
- Mining yields materials. Logs become planks and sticks; a placed crafting table unlocks furnace and pickaxe recipes. A placed furnace consumes fuel to smelt ore or sand. Inventory and placed machines survive restart.
- The **Blocks & crafting** panel lets the owner help by crafting, placing the table or furnace, and smelting. These actions use the same persistent inventory as Mimo's autonomous actions.

The current large structures are compiled from parameterized designs. The model selects the project and site; it does not yet generate arbitrary voxel schematics. This is a functional base for a Minecraft-style world, not a full one-to-one recreation: player movement, multiplayer, fluid simulation, lighting propagation, redstone-style circuits, biomes, and broad crafting progression remain future work. Owner actions currently have no account authentication, so add authentication before exposing this API publicly.

## Checks

```bash
python3 -m unittest backend.tests.test_live_mimo -v
cd frontend && npm run build
```
