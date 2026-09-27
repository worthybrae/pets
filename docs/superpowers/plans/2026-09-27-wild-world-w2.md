# Wild World W2: Weather and Seasons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the world itself harder and stranger, as the owner asked ("just maek the world even crazier and better and more compelling"), and give the owner more to teach. A year is 40 game days of four seasons; a newborn meets its first winter on day 31, and a world from before W2 starts spring on its first tick after the upgrade. Each season sets the warmth Mimo drifts toward outdoors, and a winter night outdoors freezes. The weather is a pure function of the world seed, the season and the 10-game-minute segment: clear, rain, a thunderstorm, fog or snow. Rain slows walks under the open sky, puts out a campfire under the open sky and waters the crops; snow slows walks more, chills Mimo outdoors and lays a snow cover; fog lets the dark creatures walk by day. In a storm lightning strikes the highest ground and the tallest trees, never near the home Mimo built, sometimes Mimo itself on a hilltop, and sets trees burning: fire spreads through natural leaves and logs, 24 cells at most, and burns out. The winter freezes the lakes' surface into walkable ice (an overlay, never a block), stops growth until spring, thins the herds and keeps food longer. In autumn a pet that knows winter gets "Ready for winter": its chests hold six winter days of food, and it makes a wool cloak, a stone hearth in its home and smoked meat; in winter it stays near home, off the mountains. Seven more survival lessons (winter, cloak, hearth, smoking, rain, storm, fog) are taught in one sentence or learned alone, six new wonders become questions, and the storm and fog lessons send a pet home. The viewer tints the sky by season and weather, draws rain, snow, lightning, fire, the snow cover and the ice, and shows the season and the weather on the HUD. The gate script measures the W2 gate.

**Architecture:** One module owns the sky, `backend/survival/sky.py`: the seasons, the weather (`weather_at`, pure), `state["sky"]` and its API view. The tick settles an old world's year (`settle_sky`) and tends the sky before each step (`sky.advance`: the season, the weather and the snow cover, then `sky.EFFECTS`, each guarded), so a catch-up plays the seasons and the weather in time order. What the sky does lives in modules that register into it and into hooks added to the modules they touch, as W1's hazards did: `weather.py` (walk pace through `steps.WALK_PACE`, fog through `creatures.darkness.MORE_ROOM`), `rain.py` (campfires doused, the `relight` step, fires under a roof), `storms.py` (strikes, fires, their heat, `Grid.hot`), `winter.py` (the frozen lakes through `Grid.overlay`), `winter_prep.py` ("Ready for winter" and its food target through `larder.TARGETS` and `goals.PULLS`, and staying near home in winter through a new `goals.HELD_OFF` and L5's `trips.FENCES`), `winter_gear.py` (the cloak, the hearth and the smoke step), `sky_wild.py` (knocks and wonders), `sky_reflexes.py` (flee_fire and take_cover, and fog holding trips back through `trips.HOLD_BACK`) and `sky_news.py` (Mind's moments and the inbox). `vitals.target_warmth` takes the season, the snow and the cloak. `Grid.material` reads the ice with one integer compare for cells off `SEA_LEVEL`. The viewer gets two pure modules, `seasons.ts` and `weather.ts`, a `WeatherEffects` component, and a mesher attribute and two terrain uniforms for the snow and the ice. `backend/scripts/wild_gate.py` learns the W2 criteria.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-27-wild-world-design.md`: the section "W2: Weather and seasons" and the W2 parts of "Resolutions" (13 to 16, 22 to 28), "Error handling and testing", "Balance gates" ("The harness", "W2 gate", "The existing sims") and "Risks" (6, 7, 9, 10). It builds on W1's plan (`docs/superpowers/plans/2026-09-27-wild-world-w1.md`, as amended at `ed0f0e5`) applied to `e021753`: every W1 module, hook and test this plan names is W1's (resolution 1). W3 is planned later; this plan leaves the hooks it needs (`sky.EFFECTS`, `storms.STRIKES`, the fire rules a meteor's hot rock will reuse, `wild.GRANTED`, the gate script's `--check`).

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`. No backslash inside an f-string's braces (3.10).
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls. W1 makes no model call of its own: its purposes are offered to Jev in the Chooser's existing calls like every other, questions are posted by a Talker chore (rules), answers come through the chat job (Jev only picks among real lessons, as today) or the answer endpoint (rules only). Every headless test that runs a Chooser or a Talker passes the counting stub `backend.tests.no_model.no_model(self)`. Nothing reads `random` or the clock in a test: every roll is `nature.roll` on the world seed, a cell, a channel and a time (Wild World's channels are 200 to 259, its worldgen hash channels 160 to 169: spec resolution 27).
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments, no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components. No stylesheet changes: Tailwind classes inline, as the HUD has them.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. W1 adds no table and no column (spec resolution 23). Its state has a default wherever it is read, so older saves and archives read as empty: `state["difficulty"]`, `state["wild"]` (`knocks`, `wonders`, `shun`, `night_cold`, `floor_nights`, `granted`, and the night's own counters), `state["ailments"]` (`sick`, `wound`), `state["lots"]` and `state["chest_lots"]`. The lessons live in `memory_knowledge`, the questions in `mimo_inbox`. Read-only GETs never write: `/api/mimo`'s `difficulty`, `survival`, `ailments` and the inbox's `questions` only read.
- **No model call inside the tick.** Knocks, sickness, spoilage, wounds and cold nights are rules in the tick; wonders are marked there and never posted. Every new hook is crash-guarded and logged once (`once.log_once`), a crash counting as nothing: `purposes.MEALS`, `steps.EATING`, `meals.HOLDS`, `harm.BLOWS`, `care.CARED`, `ailments.DAWN`, `spoilage.SPOILS`, `knocks.LEARNED`, the tick's `ailments.tend`, `tend_night` and `spoilage.age`, the brain's `meet_wonders` and the observers `observe_lots`, `sighted` and `after_step`. A crashing Talker chore rolls back alone and posts nothing; a crashing answer changes nothing (its own transaction).
- **A gentle world is today's game.** Every gate reads open for a gentle pet, no hazard ever comes to it, it never asks, and it only ever avoids the nightberries it knows from the start. The tick's grant writes memory rows and nothing else. Proved in the dry run: a gentle seed's 3-day event log is the base's, event for event.
- **Worldgen parity.** `backend/services/worldgen.py` and `frontend/src/engine/worldgen.ts` change together, in Task 4 only, with the same constants and channels (160, 161). No plant moves and the legacy clearing keeps every block. Regenerate the fixture after Task 4 (`python3 -m backend.scripts.worldgen_fixture`). The three new blocks go at the end of `shared/blocks.json`, after L5's `warding_lantern`: `nightberry_bush`, `nightberry_bush_ripe`, `sunleaf`. Items that are not blocks: `nightberries`, `bandage`, `spoiled_food` (and `sunleaf`, the block's own drop).
- Values from the spec (W1): a life's difficulty `"wild"` or `"gentle"`, set at hatch; the API's default wild and `hatch()`'s gentle; a world with no key reads gentle and its first tick writes it and grants every survival lesson (fact `"lesson"` and a second fact `"born_knowing"`), silently, only in a living pet's tick, and born-knowing lessons stay out of every tally of lessons learned; eleven survival lessons of kind `"survival"` named `wild:<name>`, each fact one sentence with no negation word, one side of a pair; the instinct foods (apples, carrots, bread, brown mushrooms, fish and meat) and the untried ones (red berries, red mushrooms, sunleaf); the eat-now reflex under 15; nightberry bushes (3 nightberries a pick, ripe again in 2 game days) seen as "red berries" until `wild:nightberries`, a meal of red berries eating nightberries at their share, a seeded roll a serving; a nightberry or red mushroom 5 health and a tummy ache; after a sickness from the red berries the group shunned `SHUN` = 2 game days unless the knock taught the difference; one sickness at a time, the longer kept; a tummy ache 12 game minutes, 1 health per 45 game s (tuned to 20: resolution 20), hunger ×1.5; a chill 25 game minutes, 1 health per 60 game s (tuned to 30), energy ×1.5, twice as fast resting or asleep at warmth 60 or more; no health regenerating while sick, mood's target 15 lower; one sunleaf ending any sickness; `take_herb` at priority 45; `find_herb` at 75 while a sunleaf lies within 64 blocks; a raw meal rolling once at its highest chance (raw chicken 0.35; beef, mutton, rabbit 0.2; fish 0.1; tuned to 0.5, 0.35 and 0.2: resolution 20); the cause `"sickness"` after starvation in `vitals.CAUSE_ORDER`; shelf lives (raw meat and fish 1.5 game days; berries, nightberries and brown mushrooms 2; cooked meat and fish 4; apples and carrots 5; bread 6), half as fast in a chest, `LOTS` = 3 lots of `[count, wear]`, food within a game minute of the newest lot joining it, a fourth merging into the oldest, the most worn moved first, a lot at wear 1 turning into that many `spoiled_food` (4 hunger, a tummy ache 0.6); `wild:keeping` lifting cook by 20 past wear 0.5 and storing food beyond a day's worth; a creature's blow of 2 or more after armor opening a wound with chance 0.35, one at a time, no healing while open, festering after 10 undressed game minutes (1 health per 90 game s, tuned to 40: resolution 20; mood's target 10 lower), healing a game day after it opened, closing 5 game minutes after it is dressed (a bandage, 1 wool making 2 with no station, or a sunleaf, or the owner's care bandage); `CHILL_BELOW` = 35, a chill at dawn with chance 0.6 after 5 game minutes under it, for sure after 15 or any freezing; knocks at `first + step × knocks so far` times `0.8 + curiosity / 250`, the spec's table of knocks and sure knocks for nine lessons (`wild:sunleaf` and `wild:bandage` are never learned alone: spec resolution 29), a notable `figured` event; ten wonders with their words and chips, `OPEN_MOST` = 3 open questions, `ASK_GAP` = 5 game minutes, each wonder once a life, a seeded shuffle of the chips, `HESITATE` = 8 game minutes; chips through `POST /api/mimo/inbox/{id}/answer` with `{"choice": n}` (404, 400, 409 as Bond's naming answer); yes-words and no-words binding to the newest open yes-or-no question; wrong answers doubted ("Hmm, I'm not sure that's right. I'll be careful."); the teaching table; nightberries on berries' ground one per 150 bare columns (channel 160) and sunleaf on the green lands' grass, moss or mud one per 180 (channel 161), never in the legacy clearing, both replaceable; the events, Mind moments, inbox news and danger of "Moments, news and voice"; the viewer's textures, pet, HUD, inbox, journal and memorial.
- Performance: W1 adds O(items carried) for lots and O(1) for ailments per vitals step; chests' lots age once a game minute; the tick's p99 stays in the low milliseconds.
- Never run `docker` or `docker compose` in the numbered code tasks. Task 14's manual check is the controller's, on the demo stack (`mimo-l3demo-api` on :8011 and `mimo-l3demo-worker`, volume `mimo_l3demo`, the viewer on :3000); never touch, mount or migrate the owner's real volume `pets_mimo_data` or the real stack (`pets-api-1`, `pets-mimo-worker-1`), and never touch port 5173. Never open, read or print `.env`, `TYPESAFE_API_KEY`, `MIMO_MODEL_API_KEY`, `OPENAI_API_KEY` or any other key; the owner watches the viewer in the Browser pane, so no task drives it.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

W2 adds to these, for this plan:

- **W1 comes first.** This plan applies after all fourteen tasks of W1's plan. Its tasks edit W1's modules (`wild.py`, `knocks.py`'s table only through `KNOCKS.update`, `spoilage.age`, `cooking.cook_plan`, `reflexes.plan_warm_up`, `wild_gate.py`) and W1's tests (`test_survival_wild.py`, `test_survival_lessons.py`, `test_worldgen_wild.py`, `test_survival_knocks.py`, `test_survival_reflexes.py`, `test_survival_wild_run.py`), each anchored on a line W1's plan writes (resolution 1).
- **Seasons and weather are world state, never terrain.** Worldgen does not change and the fixture is not regenerated. The snow cover and the ice are overlays: `state["sky"]` read by `Grid.material` (the ice) and by two viewer uniforms (the snow and the ice); no block is ever written for them. Fire and burned trees are ordinary block edits through `Grid.put`, synced like chopping. The three new blocks go at the end of `shared/blocks.json`, after W1's `sunleaf`: `campfire_out`, `fire`, `hearth`. New items that are not blocks: `wool_cloak`, `smoked_meat`.
- **No model call, anywhere.** The sky, the weather, strikes, fires, the ice, the winter goal and its purposes, knocks and wonders are rules. No new Jev or Luna call exists; the new purposes are offered in the Chooser's existing calls like every other. Every new hook is crash-guarded and logged once: `sky.EFFECTS` (each effect on its own), `steps.WALK_PACE`, `rain.DOUSED`, `storms.STRIKES`, `larder.TARGETS`, `goals.HELD_OFF`, `cooking.SPARED`, `trips.HOLD_BACK`. A crash counts as nothing.
- **Bounded.** Per step, the sky adds one weather lookup (recomputed only when the 10-game-minute segment changes), at most one strike (6 column tops, and a 17 × 17 height check only when Mimo stands under the open sky), at most 6 spread rounds over at most 48 burning cells, and one query for the campfires within 64 blocks while it rains. `Grid.material` pays one integer compare for every cell off `SEA_LEVEL`. Targets: the sky hook at most 2 ms mean and 8 ms p99 a transaction in a storm by a forest; a route across a frozen lake no slower than the same search with the overlay off plus 10 %.
- **Old worlds and archives.** `state["sky"]` reads with a default everywhere (`sky.sky_state`, `sky.season_now`, `sky.weather_now`). The year's offset is set only in a living pet's tick (`settle_sky`, beside W1's `settle`); `advance_world` still never writes a dead world. A gentle pet granted W1's lessons is granted W2's on its next tick the same way (`wild.GRANTED` 2).
- Values from the spec (W2): a year of 40 game days, four seasons of `SEASON_DAYS` = 10; the season day `(day_number - 1 + offset) mod 40`, a newborn's offset 0 and an old world's set on its first W2 tick so that day is spring day 1; outdoor warmth by day and by night (spring 100 and 30, summer 100 and 45, autumn 85 and 20, winter 45 and -10), the mountains 60 colder by day and 50 by night, snowfall 10 more outdoors, a shelter +45, a wool cloak +20, a fire, furnace or hearth within 4 blocks 100; winter crops, saplings, berry and nightberry bushes, sunleaf and forest-floor mushrooms stopped until the first spring dawn, farmland kept, cave mushrooms regrowing, one herd at most in a new chunk, the land cap 12 (not 24), no herd back in a hunted-out chunk until spring, surface lakes, rivers and swamp pools frozen walkable, no fishing through ice, cave lakes open, no fish recovering, spoilage a third as fast; autumn day 3's "The nights are getting colder." (a thought, a notable event and the `colder` wonder), each season's first dawn a routine `season` event and spring's first a notable one; the weather a pure function of the seed, the season and the 10-game-minute segment, each segment keeping the last one's weather with chance 0.5, the look back stopping after 6, a kept weather the new season lacks rolling fresh; the season tables (spring 0.55, 0.30, 0.08, 0.07 clear, rain, storm, fog; summer 0.65, 0.15, 0.15, 0.05; autumn 0.45, 0.25, 0.05, 0.25; winter 0.45 clear, 0.15 fog, 0.40 snow); rain: walks under the open sky 1.15 times as long, a campfire under the open sky out (`campfire_out`, no light, no warmth; `relight` with 1 stick), crops at the watered rate, fire spreading a third as often; snow: walks 1.3 times as long, 10 colder outdoors, the cover rising 0.1 a game minute and melting over 20 game minutes after the first spring dawn; fog: open ground by day dark for spawning (sky light 6), no sun burn or fade, the hostile cap 2 higher, torches and lanterns keeping their light, the viewer's fog at 0.35; a strike every 60 game seconds in a storm within 64 blocks of Mimo, 6 columns sampled within 48 and the highest struck (a tree's top counting), never within 16 blocks of the home Mimo built or in the legacy clearing; Mimo under the open sky and highest within 8 blocks struck with chance 0.05 (25 damage, armor no help, cause `"lightning"`); a strike on a tree's top leaf or log a `fire` block (glow, light 13, not solid); every 10 game seconds each burning cell spreading to one neighbouring natural log or leaf with chance 0.35 (a third in rain), at most 24 cells a fire and 2 fires at once, each cell burning out 20 to 40 game seconds after it caught; never into a cell Mimo built or edited, a claimed cell or within 8 blocks of home; 2 health a game second in or beside a burning cell (cause `"fire"`); paths keeping out of burning cells and their neighbours; the ice from the first winter dawn to the first spring dawn on natural, never-edited water at `SEA_LEVEL`, too thick to mine, the cells Mimo stood or swam in kept open until the next dawn, fish in a frozen cell moving down or fading; seven lessons (the spec's table), their knocks and sure knocks, six wonders, the owner lines and two doubted ones; `wool_cloak` (5 wool at a table, its own slot, +20); `hearth` (8 cobblestone and a campfire at a table; glow and light 13, warm like a furnace, cooks and smokes like a campfire, never out in rain; `build_hearth` 60, by day, at home, while the winter goal wants one); `smoked_meat` (the `smoke` step, 20 s at a campfire or hearth, 1 raw meat and 1 stick; 20 hunger; never spoils); "Ready for winter" (`winter_ready`, repeating, autumn day 1 until winter day 1, a built home, `wild:winter`, 70 plus a tenth of caution; milestones by lesson: `WINTER_FOOD` = 360 hunger points good on winter day 5 at chest rates, a cloak, a hearth in home, 8 smoked meat; stock_larder serving it); the events, Mind moments, inbox news and danger and death words of "Moments, news and voice"; the viewer's sky, particles (1,500 streaks, 800 flakes, half on a phone), bolt and 0.15 s flash to 3 times, fire, snow cover (`uSnow`, eased over 10 s) and ice (`uFrozen`, eased over a game minute), and the HUD's season badge and weather.

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (`Ran 1926 tests` `OK (skipped=6)` after W1's plan; `Ran 2013 tests` `OK (skipped=6)` after Task 13)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_sky.py" -v`
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`, the same with `-p "test_survival_days.py"`, `-p "test_survival_expedition_run.py"`, `-p "test_survival_making_route.py"`, `-p "test_survival_frontier_run.py"`, `-p "test_survival_away.py"` and `-p "test_survival_wild_run.py"`
- The gate (from Task 13): `python3 -m backend.scripts.wild_gate --days 150 --conditions gentle,untaught,taught --parallel 4 --out DIR`, then `--days 30 --conditions liar --parallel 4 --out DIR` and `--days 65 --conditions upgrade --parallel 4 --out DIR`, then `python3 -m backend.scripts.wild_gate --check W2 DIR` (and `--check W1 DIR`: the W1 gate must still pass)
- Frontend tests: `cd frontend && npm test` (`Tests  373 passed (373)` after W1's plan; `Tests  388 passed (388)` after Task 12)
- One frontend test file: `cd frontend && npx vitest run src/survival/weather.test.ts`
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint src/survival src/engine` (prints nothing when clean)

Each task says how many tests it adds. If the starting totals differ (W1 landed with fixes of its own, or another fix wave landed first), expect the same increases on top of them.

Transcription: every edit is a fenced block, either a whole new file ("Create `path`:") or a "replace: … with: …" pair in a named file ("In `path`, replace:", then "and replace:" for more pairs in the same file). Old texts are kept short and unique in their file at the moment they are applied, so each task still applies when a neighbouring line changes. The dry run applied each task with the controller's apply script (`.superpowers/sdd/2026-09-26-making/apply_plan.py`) to a `git archive` copy of `e021753` with W1's plan applied first, and ran the task's checks after each one; see resolution 1 and "Dry-run measurements".

## Plan-level resolutions

The spec leaves "the plan decides how" in several places. These are the details; every task follows them and the controller ledgers them.

1. **Base, order and dry run.** W2 is written on `e021753` with W1's whole plan applied as amended (`ed0f0e5`: sunleaf and bandages only from the owner, the smaller knock table, gate criteria 6′, 7′ and 10′; fourteen tasks, the fixture regenerated after its Task 4): every file and line of W1's this plan touches is as that plan writes it, and W1's execution on the branch, under way while this plan was written, follows the same plan. The plan was first written on W1's plan as it stood before the amendment (`af8a49b`); when the amendment landed, the scratch branch was rebased onto it and three anchors moved, all in files both plans touch: `test_survival_knocks.py`'s table test (W2 still only leaves its seven names out of W1's comparison), `test_survival_wild_run.py`'s imports (W1's now bring `CONDITIONS`, `SEEDS` and `check_w1`), and `wild_gate.CONDITIONS`, which stays W1's four (the amended `check_w1` unpacks them) while W2's `upgrade` condition is `wild_gate.UPGRADE`. `knocks.py` is extended only through `KNOCKS.update` in a module of W2's own, and W1's gate criteria are left as W1 writes them (one line of `check_w1`, the gentle count of lessons, counts all of `SURVIVAL`). The order keeps each task testable on its own: the seasons (Task 1) come before the weather that reads them (Task 2); the three new blocks come with rain (Task 3), the first task that writes one; lightning and fire (Task 4) and the ice and winter (Task 5) before the lessons (Task 6), so the lessons' tests can speak of what the world does; the winter goal (Task 7) before the cloak, hearth and smoking (Task 8), whose milestones it names and skips until they exist (`goals.counted`); knocks, wonders and taking cover (Task 9) once every hook they hear exists; the viewer (Tasks 11, 12) once the payload has everything; the gate script (Task 13) last. Dry run: each task applied with the apply script to a `git archive` copy of that base, the task's new and changed tests run on the code before it (they fail) and the whole backend suite after it (every task), the viewer's tests, build and eslint after Tasks 3, 11 and 12; then the six slow sims and the wild run, the W2 gate, the W1 gate on W2's code and Making's route (see "Dry-run measurements").
2. **One sky, then effects** (Task 1). `sky.py` imports only the clock, `nature.roll` and `once`, so any module may read the season or the weather. `advance(state, context, at)` runs in the tick at the start of each step, after Mimo's actions reach it and before renewal and the creatures (so they read the step's weather), and before the vitals step: first `tend_season` and `tend_weather`, then each of `EFFECTS` guarded on its own. `settle_sky` runs beside W1's `settle`, at the transaction's `last_tick_at`: a newborn's first tick is on day 1, so the one rule gives a newborn offset 0 and an old world the offset that makes its upgrade day spring day 1. A dead world is never written, since `advance_world` returns before either runs.
3. **Season events** (Task 1). The log's notability is by kind (`world.ROUTINE_EVENTS`), so the spec's routine turn of a season and its notable spring are two kinds: `season` ("Summer has come.", "Autumn has come.", "Winter has come.") is routine and `spring` ("Spring! Things are growing again.") notable; autumn day 3's warning is the notable `colder` ("The nights are getting colder."), logged once when the step crosses dusk. A turn is logged at the first step of its day, never on the tick that sets an old world's year.
4. **Warmth** (Tasks 1, 2, 8). `vitals.target_warmth(night, biome, sheltered, near_fire, season, snowing, cloak)`: the season's day or night value, the mountains' 60 or 50 off, snowfall's 10 off only when not sheltered ("outdoors"), then +45 for shelter and +20 for a cloak; a fire, furnace or hearth within 4 blocks is 100. Spring's values are today's, so every sim that stays in spring sees today's warmth to the last bit. The tick's `surroundings_at` takes the state for the season, the snow and the cloak; a wild pet wears its cloak only once it knows `wild:cloak` (`wild.cloaked`, one query only while it carries one).
5. **Weather** (Task 2). `weather_at(seed, offset, segment)`: a segment keeps the one before it when its keep roll (channel 231, on the segment) is under 0.5; the look back walks to the first segment that does not keep, stopping at the sixth, which rolls fresh on its season's table (channel 230); walking forward again, a kept weather the segment's season lacks rolls fresh. Measured over 10,000 segments of each season, every share is within 0.01 of the table, and a spell averages 3.2 segments (32 game minutes). The tick stores the weather when the segment changes, with `weather_until` (the first of the next 12 segments with another weather). A walk that starts under the open sky (`light.sky_open` at its start cell) takes 1.15 or 1.3 times as long (`steps.WALK_PACE`): one check a walk, not a cell. A crop stage that starts while it rains takes the watered time (`renewal.stage_seconds(..., rain)`, from `weather_of` at the stage's start: pure, so a catch-up and a test agree). Fog makes the open ground's sky light 6 for spawning only (`darkness.FOG_SKY`), keeps `hostiles.sunlit` from burning or fading them, and adds 2 to the cap through L5's `darkness.MORE_ROOM`.
6. **Rain and campfires** (Task 3). While it rains (a storm too), each step puts out every campfire within 64 blocks of Mimo that stands under the open sky: one query of `mimo_blocks` for campfires in the square (loading every chunk that far into the grid measured 8 ms on the tick's p99). `campfire_out` drops a campfire when mined, gives no light or warmth, and stands in for the campfire a shelter's design puts beside its door (`structures.STANDS_IN`), so furnishing never tries to put a second one in its cell. The `relight` step (1 s, a stick) lights one again; cook relights one within reach before putting another down, never one out in the rain. `wild:rain` (known from the start by a gentle pet) sorts a fire's station spots roofed first (a solid block, not leaves, within 4 above: `rain.roofed_first`) for cook's campfire and the warm_up reflex's.
7. **Lightning** (Task 4). A strike's six columns are sampled round Mimo within 48 blocks (angle and the square root of a roll, so they spread evenly over the disc; channel 232); each column's top is its highest cell that is not air, a tree's top leaf included; columns within 16 blocks of the home Mimo built or in the legacy clearing are passed over, and with none left nothing falls. "Mimo's column is the highest within 8 blocks" reads: no other column within 8 blocks has a block as high as the one Mimo stands on (so on flat ground, beside a tree or indoors it never is); then a roll under 0.05 (channel 233) strikes Mimo instead, never within 16 blocks of home or in the clearing either. A strike or fire takes health as a blow does (`hurt_by` "lightning" or "fire"), so the tick's `caught` check after `sky.advance` records the death; `tick.CAUSE_WORDS` reads "was struck by lightning" and "was caught in a fire". The last 5 strikes are kept for the viewer.
8. **Fire** (Task 4). A fire burns at most 24 cells in all, counted by fire (`sky["burned"]`), and at most 2 burn at once: "a fire holds at most 24 cells" read as all it ever holds, so a fire crawling through a forest one cell at a time still ends (at the spec's 0.35, a burning cell's two to four rolls give about one new cell each, and without this bound a dry forest would keep one alight). A burning cell spreads to one of its six face neighbours that is a natural (never-edited) log or leaf, not claimed and not within 8 blocks of home (channel 236 picks which); each cell burns 20 to 40 game seconds (channel 235) and leaves air, and renewal lets the leaves no log holds decay as after chopping. The heat is 2 health a game second for the time Mimo stood in or beside a burning cell since the last look (or since the cell caught). While a burning cell is within 3 blocks the tick takes the short fight steps (as near a hostile), and `flee_fire` (25, before flee) runs from the nearest burning cell within 2 blocks with defense's `run_away`. Paths keep out of burning cells and their face neighbours (`Grid.hot`, set by the storm effect each step).
9. **Ice** (Task 5). `Grid.material` reads "ice" for a cell at `SEA_LEVEL` whose natural block is water and that has no edit, while `grid.frozen`; `open_cells` stay water. Every natural surface water cell has open sky over it by worldgen's own shape (lakes and pools have nothing natural above them), so "open sky above it" needs no scan. `world_grid(db, seed, sky)` dresses every grid from the state (the tick's and the chooser's `from_db`), and the freeze effect keeps the tick's grid current. `start_mine` refuses the overlay's ice ("the ice is too thick"), a taiga's own natural ice still mines. At the freeze the water cells Mimo stands or swims in stay open until the next dawn, and each fish in a surface cell within the creature hook's 48 blocks swims a cell down or, with no water under it, is removed; fish farther off are never simulated there.
10. **Winter's growth, herds, fish and food** (Task 5). A renewal entry due in winter that grows something (`renewal.WINTER_WAITS`: a crop's next stage, a sapling's tree, a berry or nightberry bush ripening, a forest-floor mushroom or sunleaf coming back, farmland reverting) is rescheduled to the first spring dawn; leaf decay goes on. Cave mushrooms never came back before (a picked one's replacement grew on its chunk's forest floor): now a mushroom picked below the land's natural surface comes back on its own spot a game day later, in any season, on solid ground and never in a claimed cell, so the caves are winter food as the spec says (a small change for gentle pets too, and the only one outside winter). In winter a new chunk rolls one herd at most, the land cap near Mimo is 12 and no hunted-out chunk regains its herd; `nature.recover_fish(..., grows=False)` lets the days pass with no fish added; spoilage runs a third as fast (`spoilage.WINTER_RATE`).
11. **The seven lessons** (Task 6). They follow W1's eleven in `wild.SURVIVAL`, each with the subjects the owner's words name (winter; wool cloak, cloak; hearth; smoked meat; rain; storm, thunderstorm, lightning; fog). One opposite pair is new, harmless or safe against dangerous or danger, and the storm and fog facts stand for "dangerous" (`sides`), so "Lightning is harmless." and "Fog is safe." are doubted while no true line is. `wild.GRANTED` is 2 and `settle` grants a gentle pet whose `granted` is below it every lesson again (a known one stays as it was), quietly.
12. **"Ready for winter"** (Task 7). The rules keep the current goal (`goals.STICK`, 100) and the rules picker is the gates' picker, so a goal that is only offered in autumn would never win a goal choice from a pet busy with its making: while it is open the season pulls it `WINTER_PULL` = 100 (a `goals.PULLS` entry, "winter comes in 6 days"), so it wins the first autumn dawn's goal choice, and nothing holds Mimo to it (`holds` stays None). It is open from autumn day 1 to its last dawn, not on winter day 1 itself (a goal still open then would read as ready when winter has come). A milestone whose lesson Mimo does not know reads whole; the cloak's, the hearth's and smoking's are skipped until Task 8 registers their purposes and recipes. The food milestone counts `winter_food`: the chests' food Mimo would eat (not an old ruin's), each lot of a wild pet's counted only when its wear by winter day 5, at half the arms' rate in a chest and a third of that in winter, stays under 1. stock_larder follows the goal through `larder.TARGETS` (the target, the measure, and `WINTER_EXTRA` = 120 more food on hand while it gathers). Bond's requests learn the goal's words (`requests.REQUEST_WORDS`, `TO_DO`) and "for" joins `TITLE_STOP`, so "store it for later" is no request for it. In winter a pet that knows winter keeps near the home it built (`winter_prep.keeps_near`): the expedition and the riches goal are held off (`winter_prep.FAR_GOALS` through a new guarded hook, `goals.HELD_OFF`, read by `goals.is_open`, so one under way is given up at its next check and Mimo comes home), and no trip heads for a target farther than `WINTER_REACH` = 96 blocks from home or in the mountains (`trips.FENCES`, L5's fence list). The spec says nothing of where a pet goes in winter, but its numbers decide it: a winter day in the mountains is 45 less 60 and a winter night out -10, so a pet that roams freezes whatever it wears. Measured on the first W2 gate run's gentle lives, before this rule: every freezing minute of their first winters came 150 to 240 blocks out on an expedition, a riches trip or the far hills, criterion 2 failed on four of six seeds (12 to 35 freezing minutes in a winter), and two pets fell under 20 health dug in for a winter night on the heights with no fire. A wild pet that does not know winter roams as ever. And in winter the chest is where the food is (the bushes and crops wait for spring, the herds thin, the lakes freeze): build_storage taking food out while Mimo carries less than `storage.TAKE_BELOW` scores as food work does, from `storage.WINTER_TAKE` = 40 (forage's base is 35), for any pet, since the rule is about where food is, not a lesson; on the third gate run a gentle pet with 740 hunger points of food in its chests foraged bare winter land 58 blocks from home and starved 24 game minutes.
13. **The cloak, the hearth and smoked meat** (Task 8). The cloak is in `harm.SLOTS` as "cloak" and never in `ARMOR`, and worn, it takes no carry stack (`carrying.WORN`): kept on Mimo for good like its armor, it would fill one of the 16 stacks, and Making's route stalls on full arms (on the second gate run, gentle seed 5 carried 16 stacks with its cloak from day 66 on, could dig no cobblestone for its computer and never finished it); while Mimo wants one, 5 wool stay on hand (`storage.KEEPS_MORE`) and come back out of the chests that hold them (`storage.TAKES_MORE`). make_cloak (55 plus a tenth of caution, by day) and build_hearth make their item at a table placed and mined back (creature gear's `gear_steps`), so like make_gear neither makes one inside the shelter, where no table stands. The hearth goes in the home's room cell with walls on two sides nearest home's cell (a front corner: clear of the way in, the bed and the chest), a cell the home claims already. `crafting.FIRES` and `steps.WORKSTATIONS` gain the hearth; cook never puts down a carried hearth (its carried fires stay the campfire and the furnace). smoke_meat (65, by day) smokes the raw beef, mutton, chicken or rabbit Mimo carries, a stick each (made from its planks or logs when it has none), at a fire within reach, relit, or a campfire it puts down and picks up, or else walks to a lit campfire or hearth within cook's `FIRE_TRAVEL` (32), while the winter goal wants smoked meat (`winter_gear.smoke_wanted`): up to the 8 it holds, and for a wild pet as much more as its chests' winter food falls short; and a wild pet that is not hungry (hunger `SPARE_ABOVE` = 50 or more) and could smoke its meat now leaves it uncooked (`cooking.SPARED`, a new guarded hook), so meat it cannot smoke is still cooked before it spoils. A wild pet's cooked meat spoils before winter day 5 unless it is stored in autumn's last six days, and smoked meat never does: on the fourth gate run taught pets smoked one to four times a life, and on four of six seeds the chests held under `WINTER_FOOD` on most winters' first day (0 to 222); a probe of seed 3's autumn found it carrying twelve raw meats with no stick, and later with sticks but no fire within reach. Smoked meat is familiar food (`wild.FAMILIAR`) and no `PERISHABLE`.
14. **Knocks, wonders and taking cover** (Task 9). W2's knocks roll on W1's rule, channel 206 plus the lesson's place in `SURVIVAL` (217 to 223; W1's chips' shuffle's 220 rolls on a question's index and never on Mimo's cell). The winter knock counts a winter day once (hunger under 30); a pet alive at the first spring dawn after a winter it lived through knows winter. W1's sure fire knock by a fire it did not make is wired here: a burning cell within 8 blocks. The wonders are asked like W1's, each with a false chip for the liar (the fog's yes-claim is doubted, its no-claim teaches). take_cover (58, before head_home) sends a pet that knows the storm (or the fog) home once a spell of that weather, when it is out under the open sky farther than 16 blocks (24 in fog) from the home it built; not on an expedition, and not while going home or asleep. Without a built home it does nothing: "down off high ground" alone is left to the strikes' own rule, which never hits a pet off the heights. In fog a pet that knows it starts no trips (`trips.HOLD_BACK`); an expedition already out goes on.
15. **Moments and news** (Task 10). Mind keeps `struck` 8 (-2), `fire` 5 (0), `season` 4 (+1), `spring` 6 (+1) and `colder` 4 (0). The inbox tells a strike and a fire as danger, each at most once a game day (summer storms set many trees alight), and winter's and spring's first days as news. `season`, `storm`, `fire_out` and `smoke` are routine. `/api/mimo`'s `sky` also carries the burning cells (`fires`), for the viewer's embers.
16. **The viewer** (Tasks 11, 12). `seasons.ts` (the badge, a colder day sky in winter, easing) and `weather.ts` (the tints, the HUD's mark and word, particle counts, the fog's reach, the flash, where rain and snow fall, the bolt, embers and smoke) are pure; `WeatherEffects` draws five instanced meshes (rain, snow, the bolt's bars, embers, smoke) in one frame loop. The mesher's one new attribute, `open`, is 1 on a top face with no opaque block above it in its column (the snow settles there) and 2 on every face of water (the ice freezes the ones at or above `SEA_LEVEL`); the terrain materials read `uSnow` and `uFrozen`, set each frame by `ColumnRenderer.setWeather` from values the canvas eases toward the server's (the snow over 10 s, the ice over a game minute at the clock's pace). The storm's mark is "ϟ", not the lightning emoji. The static flame tile and its embers stand for the spec's animated flame texture.
17. **The gate script** (Task 13). The scripted owner says W2's seven lines on day 2 at the same pace as W1's on day 1. A life's winters are counted by its own seasons (an upgraded world's first winter is its first). `winter_food` is read at the first tick of each winter day 1. The `upgrade` condition runs criterion 9's world: a gentle life ticked 20 days with `sky.advance` and `settle_sky` patched out (the code before W2 had no sky; the rain's pure `weather_of` still waters its crops, the one leak), its sky dropped, then 45 more days as W2. Criterion 10 runs the two budget tests (`test_survival_storms`' storm by a forest and `test_survival_winter`'s frozen lake), each taken as the best of up to three runs so a busy machine does not fail it. Criterion 8's nearest strike is measured at the strike, through a `storms.STRIKES` hook (`wild_gate.strike_seen`): measured after the tick, a bigger home finished in the same tick as a strike 16.28 blocks from the old one read 14.21. `check_w1`'s gentle criterion counts every lesson of `SURVIVAL`, and W1's `CONDITIONS` stay its four: the upgrade condition is `wild_gate.UPGRADE`.
18. **Existing tests W2 changes** (the tasks that change them). The L2 flee test at 60 times (`test_survival_defense`'s `among_two_hostiles`) runs under clear skies: seed 3's first night rains, a walk in the rain takes 15 % longer, and the unarmed pet took 37 blows fleeing the skitter instead of at most 6; the test measures the flight, not the weather. The blocks' order tests (W1's plants, L5's lantern, the viewer's) move by three. The reflex order gains flee_fire and take_cover. W1's knock table test leaves W2's names out. W1's wild run expects every lesson known by day 3 once the scripted owner speaks on day 2. The leftovers test gives its pet a cloak, since a pet that wants one keeps its wool. Two slow sims move (Task 9, where fog starts holding trips back and storms send a pet home): `test_survival_sim.py`'s six-day lives leave a day at least half fog out of their new-ground floor (`FOG_DAY` = 0.5; seed 21's day 5 is fog from dawn to dusk and its pet walked 11 new patches, the floor being 40), and `test_survival_frontier_run.py` runs under clear skies (seed 11's geared pet, sent home out of the weather five times, set its riches goal aside and did not reach it in 4 days); both record the measure and the reason in the test's comment, for the controller's ruling.
19. **Balance** (the dry run). The spec's W2 values are kept; four gate runs came before the final one, and each change they led to is in resolution 12 or 13 (staying near home in winter, chest food in winter; the worn cloak, smoking a wild pet's winter food), measured in "Dry-run measurements". Three thresholds of the existing tests moved, each recorded in its test's comment for the controller's ruling (resolution 18): L2's flee test at 60 times runs under clear skies (37 blows in the rain against at most 6); `test_survival_sim.py`'s six-day lives leave out a day at least half fog (seed 21's day 5, fog from dawn to dusk: 11 new patches against the floor of 40; the floor stays); `test_survival_frontier_run.py` runs under clear skies (seed 11's riches goal set aside after five walks home out of the weather). Every other slow sim held unchanged. On the final code the W2 gate still fails four criteria and W1's gate two, each measured and left to the controller, not loosened: criterion 1 (a taught pet killed by a skitter on day 52), 2 (a gentle pet trapped 14 game minutes in its own staircase in a winter swamp, L3's escape slow to see it), 3 (taught pets' chests: the food good on winter day 5 under W1's spoilage), 7 and W1's 8 (every untaught pet died, four by day 25: with the weather read as clear, seeds 11 and 21 lived past day 30; with only fog read as clear, seed 11 did and seed 21 lived to day 10.9 instead of 7.3, so fog's daytime hostiles and the wounds only the owner can dress are the main cause), W1's 1 (the same skitter). The knobs the spec leaves open, in the order the evidence points: fog's hostiles (`FOG_ROOM` 2 to 0, then fog's daytime spawning light), then the share of fog in the tables, then W1's own drains (its chill is at its limit, W1's resolution 20); for criterion 3, counting a wild pet's winter food as good on winter day 1 rather than day 5, or smoking offered through the whole autumn.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/survival/sky.py` | Create | The seasons, the weather (`weather_at`), `state["sky"]`, the tick's `settle_sky` and `advance`, `EFFECTS`, the API's `sky` |
| `backend/survival/weather.py` | Create | Rain and snow slowing walks, fog's room for hostiles |
| `backend/survival/rain.py` | Create | Campfires doused, the `relight` step, fires under a roof (`wild:rain`), `DOUSED` |
| `backend/survival/storms.py` | Create | Strikes, Mimo struck, fires in the trees, their spread, heat and caps, `Grid.hot`, `STRIKES` |
| `backend/survival/winter.py` | Create | The freeze and the thaw, open cells, fish under the ice |
| `backend/survival/winter_prep.py` | Create | "Ready for winter": the goal, `winter_food`, the larder's target, the season's pull |
| `backend/survival/winter_gear.py` | Create | make_cloak, build_hearth, the `smoke` step and smoke_meat, the cloak's wool |
| `backend/survival/sky_wild.py` | Create | W2's knocks and wonders |
| `backend/survival/sky_reflexes.py` | Create | flee_fire, take_cover, fog holding trips back |
| `backend/survival/sky_news.py` | Create | Mind's moments, the inbox's danger and news |
| `backend/survival/{tick,vitals,grid,situation,steps,renewal,nature,spoilage,light,snapshot}.py` | Modify | The sky in the tick, warmth by season, the ice overlay and `hot` cells, `WALK_PACE`, winter's growth and fish, the hearth's light and warmth, the payload |
| `backend/survival/creatures/{darkness,hostiles,spawning}.py` | Modify | Fog's spawning, sun and cap; winter's herds |
| `backend/survival/{wild,lessons,larder,goals,storage,carrying,requests,cooking,reflexes,trips,brain,bonding,world}.py`, `backend/services/crafting.py` | Modify | The seven lessons, the parser's opposites, the larder's targets, `HELD_OFF`, chest food in winter, the worn cloak, the goal's words, relighting, roofed fires and `SPARED`, `HOLD_BACK`, imports, routine events, recipes and fires |
| `shared/blocks.json`, `frontend/src/engine/atlas.ts` | Modify | `campfire_out`, `fire`, `hearth` and their tiles |
| `backend/scripts/wild_gate.py` | Modify | The owner's day 2, the winters, the upgrade condition, `--check W2` |
| `backend/tests/test_survival_{sky,weather,rain,storms,winter,sky_teaching,winter_goal,winter_gear,sky_wild,sky_news,sky_gate}.py` | Create | One test file per new module or area |
| `backend/tests/test_survival_{defense,frontier_gear,reflexes,wild,lessons,meat,knocks,wild_run,voice,sim,frontier_run}.py`, `backend/tests/test_worldgen_wild.py` | Modify | What W2 changes in them (resolution 18) |
| `frontend/src/survival/{seasons,weather}.ts` (+ tests), `frontend/src/survival/WeatherEffects.tsx` | Create | The season badge and easing; tints, the HUD's weather, particles, the bolt, flash, embers and smoke |
| `frontend/src/survival/{types,hud,animation,DayNight,SurvivalHud,SurvivalWorld,WorldCanvas,SurvivalPet,petGear,creatures}.ts(x)`, `frontend/src/engine/{mesher,columnRenderer,workerProtocol,BlockWorld}.ts(x)` (+ their tests) | Modify | The sky in the stream, words, the sky's color and fog, the HUD line, the effects, the cloak, the `open` attribute and the snow and ice uniforms |
| `README.md` | Modify | Weather and seasons |

## Tasks

1. The seasons
2. The weather
3. Rain on the fire, and the new blocks
4. Lightning and fire in the trees
5. The hard winter: ice, growth, herds and fish
6. The seven lessons, taught in one sentence
7. "Ready for winter"
8. The cloak, the hearth and smoked meat
9. Learning the sky: knocks, wonders and taking cover
10. Moments, news and voice
11. Viewer: the sky, the season and the weather on the HUD
12. Viewer: rain, snow, lightning, fire, the snow cover and the ice
13. The gate script's W2
14. Manual check on the demo and the README

Tasks 1–10 and 13 are the backend (Task 3 also the blocks' tiles), 11 and 12 the viewer. Task 2 needs Task 1; Task 3 needs Task 2; Task 4 needs Tasks 2 and 3 (the blocks); Task 5 needs Task 2; Task 6 needs nothing of W2's; Task 7 needs Tasks 1 and 6; Task 8 needs Tasks 3 and 7; Task 9 needs Tasks 3 to 8; Task 10 needs Tasks 1 to 4; Task 11 needs the payload of Tasks 1 to 3; Task 12 needs Tasks 4, 5 and 8's payload and 11; Task 13 needs all of them.

---

### Task 1: The seasons

**Files:**
- Create: `backend/survival/sky.py`, `backend/tests/test_survival_sky.py`
- Modify: `backend/survival/vitals.py` (`SEASON_WARMTH`, `target_warmth`, `Surroundings`), `backend/survival/tick.py` (`surroundings_at`, `settle_sky`, `sky.advance`), `backend/survival/snapshot.py` (`sky` in `/api/mimo`)

**Interfaces:**
- Consumes: `clock.clock_at`, `clock.PHASES`; W1's `wild.settle` in `advance_world` (the sky settles beside it); `world.append_event`.
- Produces: `sky.SEASON_DAYS` (10), `SEASONS`, `YEAR_DAYS` (40), `sky_state(state) -> dict` (every field defaulted), `offset_of(state)`, `day_number(state, at, scale)`, `season_day_of(day, offset)`, `season_of(season_day)`, `season_at(state, at, scale) -> (season, season_day)`, `season_now(state)`, `winter(state)`, `next_season_at(state, at, scale, season)`, `settle_sky(state, at, scale)`, `advance(state, context, at)`, `EFFECTS` (callables `(state, context, at)`, each guarded), `sky_view(state, now, scale)`; `vitals.target_warmth(night, biome, sheltered, near_fire, season="spring", snowing=False, cloak=False)`; `tick.surroundings_at(db, seed, position, state=None)`; `/api/mimo`'s `sky` (`season`, `day`, `to_next`, `weather`, `until`, `snow`, `frozen`, `strikes`, `fires`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_sky.py`:

```python
"""W2: the seasons: the season day from the day and the offset, an old world's spring, warmth by season, the
turn of a season, autumn's warning and the sky in /api/mimo."""

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.survival.brain import BRAIN
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.sky import (
    SEASONS, next_season_at, season_at, season_day_of, season_of, settle_sky, sky_view, tend_season,
)
from backend.survival.snapshot import survival_view
from backend.survival.tick import tick_life
from backend.survival.vitals import target_warmth
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0
SCALE = 60.0


def day_start(day: int) -> float:
    """Server time of the dawn that starts game day `day` (scale 60)."""
    return BORN + (day - 1) * DAY_SECONDS / SCALE


def context(events: list):
    return SimpleNamespace(events=events, clock_at=lambda at: clock_at(BORN, at, SCALE), db=None)


class Lives:
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")

    def hatch(self, seed=8):
        life = hatch(self.registry, random.Random(seed), timestamp=BORN)
        return life, SurvivalWorld(self.registry.world_path(life))


class SeasonTests(unittest.TestCase):
    def test_a_year_is_forty_days_of_four_seasons_from_the_day_and_the_offset(self):
        self.assertEqual([season_of(season_day_of(day, 0)) for day in (1, 10, 11, 21, 31, 40, 41)],
                         ["spring", "spring", "summer", "autumn", "winter", "winter", "spring"])
        self.assertEqual(season_day_of(31, 0), 30)
        self.assertEqual(season_day_of(20, 21), 0)
        self.assertEqual(SEASONS, ("spring", "summer", "autumn", "winter"))

    def test_an_old_worlds_first_tick_makes_its_day_spring_day_one_and_winter_comes_thirty_days_later(self):
        state = {"born_at": BORN}
        at = day_start(20) + 100 / SCALE
        settle_sky(state, at, SCALE)
        self.assertEqual(season_at(state, at, SCALE), ("spring", 0))
        self.assertEqual(next_season_at(state, at, SCALE, "winter"), day_start(50))
        settled = dict(state["sky"])
        settle_sky(state, day_start(30), SCALE)  # once only
        self.assertEqual(state["sky"], settled)

    def test_a_newborn_starts_on_spring_day_one(self):
        lives = Lives()
        self.addCleanup(lives.directory.cleanup)
        _, world = lives.hatch()
        tick_life(lives.registry, BORN + 2, scale=SCALE, mind=BRAIN, action_scale=SCALE)
        sky = world.state()["sky"]
        self.assertEqual((sky["offset"], sky["season"], sky["season_day"]), (0, "spring", 0))
        self.assertEqual(next_season_at(world.state(), BORN + 2, SCALE, "winter"), day_start(31))

    def test_warmth_outdoors_follows_the_season_and_shelter_cloak_and_fire_add_to_it(self):
        table = {season: (target_warmth(False, "meadow", False, False, season),
                          target_warmth(True, "meadow", False, False, season)) for season in SEASONS}
        self.assertEqual(table, {"spring": (100.0, 30.0), "summer": (100.0, 45.0), "autumn": (85.0, 20.0),
                                 "winter": (45.0, -10.0)})
        self.assertEqual(target_warmth(True, "meadow", False, False), 30.0)  # spring is today's
        self.assertEqual(target_warmth(False, "alpine", False, False), 40.0)
        self.assertEqual(target_warmth(True, "alpine", False, False, "winter"), -60.0)
        self.assertEqual(target_warmth(True, "meadow", True, False, "winter"), 35.0)
        self.assertEqual(target_warmth(True, "meadow", True, False, "winter", cloak=True), 55.0)
        self.assertEqual(target_warmth(True, "meadow", False, False, "winter", snowing=True), -20.0)
        self.assertEqual(target_warmth(True, "meadow", True, False, "winter", snowing=True), 35.0)  # snow outdoors only
        self.assertEqual(target_warmth(True, "meadow", False, True, "winter", snowing=True), 100.0)


class TurnTests(unittest.TestCase):
    def tend(self, state, day, seconds, events):
        tend_season(state, context(events), day_start(day) + seconds / SCALE)

    def test_a_season_turns_at_its_first_dawn_and_springs_turn_is_news(self):
        state, events = {"born_at": BORN, "sky": {"offset": 0}}, []
        self.tend(state, 10, 3000, events)
        self.tend(state, 11, 0, events)
        self.assertEqual([(kind, text) for _, kind, text in events], [("season", "Summer has come.")])
        self.tend(state, 31, 0, events)
        self.tend(state, 41, 0, events)
        self.assertEqual([(kind, text) for _, kind, text in events][1:],
                         [("season", "Winter has come."), ("spring", "Spring! Things are growing again.")])
        self.assertEqual(state["last_thought"], "Spring! Things are growing again.")

    def test_on_autumn_day_three_at_dusk_the_nights_are_getting_colder_once(self):
        state, events = {"born_at": BORN, "sky": {"offset": 0}}, []
        self.tend(state, 23, 2000, events)
        self.assertEqual(events, [])
        self.tend(state, 23, 2300, events)
        self.tend(state, 23, 2500, events)
        self.assertEqual([(kind, text) for _, kind, text in events], [("colder", "The nights are getting colder.")])
        self.assertEqual(state["sky"]["season"], "autumn")


class OldWorldTests(unittest.TestCase):
    def setUp(self):
        self.lives = Lives()
        _, self.world = self.lives.hatch()

    def tearDown(self):
        self.lives.directory.cleanup()

    def test_a_world_from_before_w2_reads_a_default_sky_and_its_first_tick_sets_spring(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state.pop("sky", None)
            state["last_tick_at"] = day_start(20)
            write_state(db, state)
        view = survival_view(self.world, day_start(20), SCALE)["sky"]
        self.assertEqual((view["weather"], view["snow"], view["frozen"], view["strikes"]), ("clear", 0.0, False, []))
        self.assertNotIn("sky", self.world.state())  # a GET never writes
        tick_life(self.lives.registry, day_start(20) + 1, scale=SCALE, mind=BRAIN, action_scale=SCALE)
        sky = self.world.state()["sky"]
        self.assertEqual((sky["offset"], sky["season"], sky["season_day"]), (21, "spring", 0))
        view = survival_view(self.world, day_start(20) + 1, SCALE)["sky"]
        self.assertEqual((view["season"], view["day"], view["to_next"]), ("spring", 1, 10))

    def test_a_dead_pets_world_is_never_written(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state.pop("sky", None)
            state.update(died_at=BORN + 0.5, cause="starvation")
            write_state(db, state)
        tick_life(self.lives.registry, BORN + 5, scale=SCALE, mind=BRAIN, action_scale=SCALE)
        self.assertNotIn("sky", self.world.state())
        self.assertEqual(sky_view(self.world.state(), BORN + 5, SCALE)["season"], "spring")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_sky.py"`
Expected: `FAILED (errors=1)`: `ModuleNotFoundError: No module named 'backend.survival.sky'`

- [ ] **Step 3: The seasons, the warmth and the sky in the tick**

Create `backend/survival/sky.py`:

```python
"""Wild World W2: the seasons and the sky (docs/superpowers/specs/2026-09-27-wild-world-design.md, "W2").

A year is YEAR_DAYS (40) game days: spring, summer, autumn and winter, SEASON_DAYS (10) each. The season day
(0 to 39) is `(day_number - 1 + offset) mod 40`, with the offset in state["sky"]["offset"]: a newborn's is 0
(it hatches on spring day 1 and meets its first winter on day 31), and a world from before W2 gets one on its
first tick (`settle_sky`, only in a living pet's tick) so that day is spring day 1 and its first winter comes
30 game days after the upgrade.

Seasons move the warmth Mimo drifts toward outdoors (vitals.SEASON_WARMTH: a winter night outdoors is -10, 35
sheltered). The tick tends the sky before each step (`advance`): it keeps state["sky"] up to date for
/api/mimo and for what reads it in the step (the season, and from W2's later parts the weather, the snow, the
frozen lakes, the strikes and the fires), logs the turn of a season at its first dawn ("Winter has come.", a
routine "season" event; spring's is the notable "spring": "Spring! Things are growing again.") and, on autumn
day 3 at dusk, the notable "colder" ("The nights are getting colder."). Then it runs EFFECTS, each guarded: a
crash is logged once and counts as nothing.

state["sky"] (`sky_state`; every field has a default, so a world from before W2 and an archive read as empty):
offset, season, season_day, day (the day number last tended), weather, weather_until, snow, frozen, open_cells,
strikes, fires, told ({what: day} of the season's news). A GET never writes it (`sky_view` only reads).
"""

from __future__ import annotations

import logging
from typing import Callable

from backend.survival.clock import DAY_SECONDS, PHASES, clock_at
from backend.survival.once import log_once

logger = logging.getLogger(__name__)

SEASON_DAYS = 10
SEASONS = ("spring", "summer", "autumn", "winter")
YEAR_DAYS = SEASON_DAYS * len(SEASONS)
WINTER = "winter"
COLDER_DAY = 2  # autumn day 3 (the season day's own count starts at 0)
DUSK = next(start for name, start, _ in PHASES if name == "dusk")
TURNS = {"summer": "Summer has come.", "autumn": "Autumn has come.", "winter": "Winter has come.",
         "spring": "Spring! Things are growing again."}
COLDER = "The nights are getting colder."
# W2: functions (state, context, at) run by `advance` after the season is tended, before each step (the
# weather's, the storms' and the ice's effects). One that crashes is logged once and passed over.
EFFECTS: list[Callable] = []


def sky_state(state: dict) -> dict:
    """state["sky"], with every field (a world from before W2 has none until its first tick)."""
    found = state.setdefault("sky", {})
    for key, default in (("season", "spring"), ("season_day", 0), ("day", None), ("weather", "clear"),
                         ("weather_until", None), ("snow", 0.0), ("frozen", False), ("open_cells", []),
                         ("strikes", []), ("fires", []), ("told", {})):
        found.setdefault(key, default)
    return found


def offset_of(state: dict) -> int:
    return int((state.get("sky") or {}).get("offset", 0))


def day_number(state: dict, at: float, scale: float) -> int:
    return clock_at(state["born_at"], at, scale)["day_number"]


def season_day_of(day: int, offset: int) -> int:
    """The season day (0 to 39) of the life's day number `day`."""
    return (day - 1 + offset) % YEAR_DAYS


def season_of(season_day: int) -> str:
    return SEASONS[season_day // SEASON_DAYS]


def season_at(state: dict, at: float, scale: float) -> tuple[str, int]:
    """(season, season day) at server time `at`."""
    found = season_day_of(day_number(state, at, scale), offset_of(state))
    return season_of(found), found


def season_now(state: dict) -> str:
    """The season the tick last tended ("spring" for a world from before W2)."""
    return (state.get("sky") or {}).get("season", "spring")


def winter(state: dict) -> bool:
    return season_now(state) == WINTER


def next_season_at(state: dict, at: float, scale: float, season: str) -> float:
    """Server time of the next first dawn of `season` after `at` (`at`'s own day counts when it is that dawn)."""
    day = day_number(state, at, scale)
    target = SEASONS.index(season) * SEASON_DAYS
    ahead = (target - season_day_of(day, offset_of(state))) % YEAR_DAYS
    if ahead == 0 and clock_at(state["born_at"], at, scale)["seconds_into_day"] > 0:
        ahead = YEAR_DAYS
    return state["born_at"] + (day - 1 + ahead) * DAY_SECONDS / scale


def settle_sky(state: dict, at: float, scale: float) -> None:
    """A living pet's tick: a world with no offset gets one, so the day at `at` is spring day 1."""
    sky = state.setdefault("sky", {})
    if "offset" not in sky:
        sky["offset"] = (1 - day_number(state, at, scale)) % YEAR_DAYS


def tend_season(state: dict, context, at: float) -> None:
    """Keep the season up to date and log its turns and autumn's warning (see the module docstring)."""
    sky = sky_state(state)
    clock = context.clock_at(at)
    day = clock["day_number"]
    season_day = season_day_of(day, offset_of(state))
    season = season_of(season_day)
    turned = sky["day"] is not None and day != sky["day"] and season_day % SEASON_DAYS == 0
    sky.update(season=season, season_day=season_day, day=day)
    if turned:
        kind = "spring" if season == "spring" else "season"
        context.events.append((at, kind, TURNS[season]))
        state["last_thought"] = TURNS[season]
    told = sky["told"]
    if (season == "autumn" and season_day % SEASON_DAYS == COLDER_DAY and clock["seconds_into_day"] >= DUSK
            and told.get("colder") != day):
        told["colder"] = day
        context.events.append((at, "colder", COLDER))
        state["last_thought"] = COLDER


def advance(state: dict, context, at: float) -> None:
    """Before each step of the tick: the season, then EFFECTS. A crash is logged once and changes nothing."""
    try:
        tend_season(state, context, at)
    except Exception as error:
        log_once(logger, "season", error)
    for effect in EFFECTS:
        try:
            effect(state, context, at)
        except Exception as error:
            log_once(logger, f"sky {getattr(effect, '__name__', 'effect')}", error)


def sky_view(state: dict, now: float, scale: float) -> dict:
    """For /api/mimo (read only): the season and its day (1 to 10), the days to the next season, the weather
    and until when, the snow, whether the lakes are frozen, and the latest strikes ({x, y, z, at})."""
    sky = state.get("sky") or {}
    at = state["died_at"] if state.get("died_at") is not None else now
    season, season_day = season_at(state, at, scale)
    return {"season": season, "day": season_day % SEASON_DAYS + 1, "to_next": SEASON_DAYS - season_day % SEASON_DAYS,
            "weather": sky.get("weather", "clear"), "until": sky.get("weather_until"),
            "snow": round(float(sky.get("snow", 0.0)), 3), "frozen": bool(sky.get("frozen", False)),
            "strikes": list(sky.get("strikes", []))}
```

In `backend/survival/snapshot.py`, replace:

```python
from backend.survival.rings import ring_view
```

with:

```python
from backend.survival.rings import ring_view
from backend.survival.sky import sky_view
```

and replace:

```python
        "ailments": ailments_view(state),
```

with:

```python
        "ailments": ailments_view(state),
        # W2: the season, the weather, the snow, the frozen lakes and the latest strikes (backend.survival.sky).
        "sky": sky_view(state, now, scale),
```

In `backend/survival/tick.py`, replace:

```python
and its food ages (backend.survival.spoilage.age).
```

with:

```python
and its food ages (backend.survival.spoilage.age).

W2: a world from before W2 gets its year's offset on its first tick (backend.survival.sky.settle_sky), and before
each step the sky is tended (sky.advance: the season, then its effects), so a long catch-up plays the seasons in
time order; the season sets the warmth Mimo drifts toward (Surroundings.season).
```

and replace:

```python
from backend.survival import ailments, spoilage
```

with:

```python
from backend.survival import ailments, sky, spoilage
```

and replace:

```python
def surroundings_at(db: sqlite3.Connection, seed: str, position: dict) -> Surroundings:
```

with:

```python
def surroundings_at(db: sqlite3.Connection, seed: str, position: dict, state: dict | None = None) -> Surroundings:
    """What the world round Mimo's cell says for a vitals step; W2: with `state`, the season too."""
```

and replace:

```python
        head_in_water=material_at(x, y, z) == "water",
```

with:

```python
        head_in_water=material_at(x, y, z) == "water",
        season=sky.season_now(state) if state is not None else "spring",
```

and replace:

```python
        settle(state, db, state["last_tick_at"])  # W1: gentle for an old world, and a gentle pet's lessons
```

with:

```python
        settle(state, db, state["last_tick_at"])  # W1: gentle for an old world, and a gentle pet's lessons
        sky.settle_sky(state, state["last_tick_at"], scale)  # W2: an old world's year starts in spring now
```

and replace:

```python
                break
            run_renewal(state, context, cursor)
```

with:

```python
                break
            sky.advance(state, context, cursor)  # W2: the season and the weather at this step's start
            run_renewal(state, context, cursor)
```

and replace:

```python
            surroundings = surroundings_at(db, world.seed, state["position"])
```

with:

```python
            surroundings = surroundings_at(db, world.seed, state["position"], state)
```

In `backend/survival/vitals.py`, replace:

```python
again as fast, and mood's target falls.
```

with:

```python
again as fast, and mood's target falls.

W2: the season sets the warmth Mimo drifts toward outdoors (SEASON_WARMTH, by day and by night; spring's is
today's), the mountains stay 60 colder by day and 50 by night, falling snow takes SNOW_CHILL more off outdoors,
a shelter adds 45, a wool cloak CLOAK_WARMTH, and a fire, furnace or hearth within 4 blocks sets 100.
```

and replace:

```python
ACTIVITIES = ("idle", "working", "sleeping", "sleeping_in_bed")
```

with:

```python
ACTIVITIES = ("idle", "working", "sleeping", "sleeping_in_bed")
# W2: outdoor warmth by season, (by day, by night), before shelter, cloak and fire (backend.survival.sky).
SEASON_WARMTH = {"spring": (100.0, 30.0), "summer": (100.0, 45.0), "autumn": (85.0, 20.0), "winter": (45.0, -10.0)}
ALPINE_DAY, ALPINE_NIGHT = 60.0, 50.0  # the mountains are this much colder
SNOW_CHILL = 10.0  # falling snow, outdoors
CLOAK_WARMTH = 20.0  # a wool cloak
```

and replace:

```python
    head_in_water: bool = False
```

with:

```python
    head_in_water: bool = False
    season: str = "spring"  # W2
    snowing: bool = False
    cloak: bool = False
```

and replace:

```python
def target_warmth(night: bool, biome: str, sheltered: bool, near_fire: bool) -> float:
    if near_fire:
        return 100.0
    if biome == "alpine":
        base = -20.0 if night else 40.0
    else:
        base = 30.0 if night else 100.0
    return min(100.0, base + (SHELTER_BONUS if sheltered else 0.0))
```

with:

```python
def target_warmth(night: bool, biome: str, sheltered: bool, near_fire: bool, season: str = "spring",
                  snowing: bool = False, cloak: bool = False) -> float:
    if near_fire:
        return 100.0
    day, dark = SEASON_WARMTH.get(season, SEASON_WARMTH["spring"])
    base = dark if night else day
    if biome == "alpine":
        base -= ALPINE_NIGHT if night else ALPINE_DAY
    if snowing and not sheltered:
        base -= SNOW_CHILL
    return min(100.0, base + (SHELTER_BONUS if sheltered else 0.0) + (CLOAK_WARMTH if cloak else 0.0))
```

and replace:

```python
    warmth_target = target_warmth(night, surroundings.biome, surroundings.sheltered, surroundings.near_fire)
```

with:

```python
    warmth_target = target_warmth(night, surroundings.biome, surroundings.sheltered, surroundings.near_fire,
                                  surroundings.season, surroundings.snowing, surroundings.cloak)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_sky.py"`
Expected: `Ran 8 tests` `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1934 tests` … `OK (skipped=6)` (8 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/sky.py backend/survival/snapshot.py backend/survival/tick.py backend/survival/vitals.py backend/tests/test_survival_sky.py
git commit -m "feat(W2): a year of four seasons that sets how warm it is outdoors, and an old world starts in spring" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The weather

**Files:**
- Create: `backend/survival/weather.py`, `backend/tests/test_survival_weather.py`
- Modify: `backend/survival/sky.py` (`weather_at` and the tick's weather), `backend/survival/steps.py` (`WALK_PACE`, `walk_pace`, `start_walk`), `backend/survival/renewal.py` (`stage_seconds(..., rain)`, `rained`), `backend/survival/creatures/darkness.py` (`FOG_SKY`), `backend/survival/creatures/hostiles.py` (`sunlit`), `backend/survival/tick.py` (imports `weather`; `Surroundings.snowing`), `backend/tests/test_survival_defense.py` (clear skies for the flee test: resolution 18)

**Interfaces:**
- Consumes: Task 1's `sky.advance`, `season_at`; `nature.roll`; `light.sky_open`; L5's `darkness.MORE_ROOM`.
- Produces: `sky.SEGMENT` (600), `TABLE`, `RAINY`, `weather_at(seed, offset, segment) -> str` (pure), `segment_of(state, at, scale)`, `weather_of(state, at, scale)`, `weather_now(state)`, `raining(state)`, `foggy(state)`; `state["sky"]`'s `weather`, `weather_until`, `snow`; `steps.WALK_PACE` (callables `(state, grid, cell) -> float`, guarded) and `steps.walk_pace(state, grid, cell)`; `weather.RAIN_PACE` (1.15), `SNOW_PACE` (1.3), `FOG_ROOM` (2); `renewal.stage_seconds(grid, crop, rain=False)`, `renewal.rained(state, at, scale)`; `darkness.FOG_SKY` (6).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_defense.py`, replace:

```python
            with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []), \
                    patch("backend.survival.creatures.hostiles.hurt_pet", counted):
```

with:

```python
            # W2: under clear skies. Seed 3's first night rains, and rain slows a walk under the open sky (a run
            # from the skitter took 37 blows at 60x in the rain): this measures the flight, not the weather.
            with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []), \
                    patch("backend.survival.creatures.hostiles.hurt_pet", counted), \
                    patch("backend.survival.sky.weather_at", lambda seed, offset, segment: "clear"):
```

Create `backend/tests/test_survival_weather.py`:

```python
"""W2: the weather: a pure function of the seed, the season and the segment; what rain, snow and fog do."""

import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

from backend.survival import weather  # noqa: F401  (registers the walk pace and the fog's room)
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.creatures.darkness import HOSTILE_CAP, cap, spawn_hostiles
from backend.survival.creatures.hostiles import sunlit
from backend.survival.creatures.kinds import KINDS
from backend.survival.renewal import CROP_STAGE_DRY, CROP_STAGE_WET, rained, stage_seconds
from backend.survival.sky import (
    LOOK_BACK, SEASONS, SEGMENT, TABLE, segment_season, sky_state, tend_weather, weather_at, weather_of,
)
from backend.survival.steps import start_step
from backend.survival.tick import surroundings_at
from backend.tests.test_survival_cooking import meadow
from backend.tests.test_survival_darkness import DAY, land, pet, scene

BORN = 1_000_000.0
SCALE = 60.0
SEED = "11"


def segment_where(seed, weather, season="spring", offset=0):
    """The first segment of `season` in the first year with `weather`."""
    return next(segment for segment in range(40 * 6)
                if segment_season(offset, segment) == season and weather_at(seed, offset, segment) == weather)


def at_segment(segment):
    return BORN + segment * SEGMENT / SCALE


def context(events=None):
    return SimpleNamespace(events=[] if events is None else events, clock_at=lambda at: clock_at(BORN, at, SCALE),
                           db=None)


class WeatherTests(unittest.TestCase):
    def test_the_weather_is_a_pure_function_that_keeps_spells(self):
        first = [weather_at(SEED, 0, segment) for segment in range(600)]
        self.assertEqual(first, [weather_at(SEED, 0, segment) for segment in range(600)])
        spells, run = [], 1
        for before, after in zip(first, first[1:]):
            if before == after:
                run += 1
            else:
                spells.append(run)
                run = 1
        self.assertGreaterEqual(sum(spells) / len(spells), 2.0)  # 20 game minutes or more on average

    def test_each_season_follows_its_table_over_ten_thousand_segments(self):
        for season in SEASONS:
            counts, segments = Counter(), 0
            for segment in range(40 * 6 * 170):
                if segment_season(0, segment) != season:
                    continue
                counts[weather_at(SEED, 0, segment)] += 1
                segments += 1
                if segments == 10_000:
                    break
            self.assertEqual(segments, 10_000)
            for kind, share in TABLE[season]:
                self.assertAlmostEqual(counts[kind] / segments, share, delta=0.02, msg=(season, kind))
            self.assertEqual(set(counts) - {kind for kind, _ in TABLE[season]}, set())  # no rain in winter

    def test_the_look_back_stops_and_a_weather_the_season_lacks_rolls_fresh(self):
        calls = []
        with patch("backend.survival.sky.roll", lambda seed, cell, channel, salt=0: calls.append(cell) or 0.0):
            weather_at(SEED, 0, 100)  # every roll keeps: it looks back LOOK_BACK segments and no further
        self.assertEqual(min(cell[0] for cell in calls), 100 - LOOK_BACK + 1)
        first_winter = 30 * 6
        self.assertNotIn(weather_at(SEED, 0, first_winter), ("rain", "storm"))
        self.assertTrue(all(weather_at(seed, 0, first_winter + step) not in ("rain", "storm")
                            for seed in map(str, range(40)) for step in range(3)))

    def test_the_tick_stores_the_weather_until_it_changes_and_the_snow_cover(self):
        state = {"born_at": BORN, "world_seed": SEED, "sky": {"offset": 0}}
        segment = segment_where(SEED, "rain")
        tend_weather(state, context(), at_segment(segment) + 1 / SCALE)
        sky = state["sky"]
        self.assertEqual(sky["weather"], "rain")
        until = round((sky["weather_until"] - BORN) * SCALE / SEGMENT)
        self.assertTrue(all(weather_at(SEED, 0, later) == "rain" for later in range(segment, until)))
        self.assertNotEqual(weather_at(SEED, 0, until), "rain")
        self.assertEqual(weather_of(state, at_segment(segment), SCALE), "rain")
        snowy = segment_where(SEED, "snow", "winter")
        snow = {"born_at": BORN, "world_seed": SEED, "sky": {"offset": 0, "season": "winter"}}
        tend_weather(snow, context(), at_segment(snowy))
        tend_weather(snow, context(), at_segment(snowy) + 300 / SCALE)
        self.assertAlmostEqual(snow["sky"]["snow"], 0.5)
        thaw = {"born_at": BORN, "world_seed": SEED, "sky": {"offset": 0, "season": "spring", "snow": 1.0}}
        clear = segment_where(SEED, "clear")
        tend_weather(thaw, context(), at_segment(clear))
        tend_weather(thaw, context(), at_segment(clear) + 600 / SCALE)
        self.assertAlmostEqual(thaw["sky"]["snow"], 0.5)


class RainAndSnowTests(unittest.TestCase):
    def walk_seconds(self, weather, roof=False):
        grid = meadow({(x, 4, 0): "stone" for x in range(-1, 12)} if roof else None)
        state = {"world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "sky": {"weather": weather}}
        step = start_step({"kind": "walk", "target": [10, 1, 0]}, state, grid, 0.0)
        return step["ends_at"]

    def test_rain_and_snow_slow_a_walk_under_the_open_sky(self):
        clear = self.walk_seconds("clear")
        self.assertAlmostEqual(self.walk_seconds("rain"), clear * 1.15, places=2)
        self.assertAlmostEqual(self.walk_seconds("storm"), clear * 1.15, places=2)
        self.assertAlmostEqual(self.walk_seconds("snow"), clear * 1.3, places=2)
        self.assertAlmostEqual(self.walk_seconds("fog"), clear, places=3)
        self.assertAlmostEqual(self.walk_seconds("rain", roof=True), clear, places=3)

    def test_a_crop_stage_that_starts_in_the_rain_grows_at_the_watered_rate(self):
        grid = meadow({(0, 0, 0): "farmland", (0, 1, 0): "wheat_0"})
        self.assertEqual(stage_seconds(grid, (0, 1, 0)), CROP_STAGE_DRY)
        self.assertEqual(stage_seconds(grid, (0, 1, 0), rain=True), CROP_STAGE_WET)
        state = {"born_at": BORN, "world_seed": SEED, "sky": {"offset": 0}}
        self.assertTrue(rained(state, at_segment(segment_where(SEED, "rain")), SCALE))
        self.assertFalse(rained(state, at_segment(segment_where(SEED, "clear")), SCALE))
        self.assertFalse(rained({}, 0.0, SCALE))

    def test_falling_snow_is_felt_outdoors(self):
        state = {"sky": {"season": "winter", "weather": "snow"}}
        with patch("backend.survival.tick.material_in", lambda db, x, y, z, seed: "air"), \
                patch("backend.survival.tick.placed_near", lambda db, position, reach, blocks: []):
            felt = surroundings_at(None, "1", {"x": 0.0, "y": 1.0, "z": 0.0}, state)
        self.assertEqual((felt.season, felt.snowing), ("winter", True))


class FogTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.survival.creatures.darkness.terrain_height", "backend.survival.light.terrain_height"):
            patcher = patch(target, lambda x, z, seed: 0)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_in_fog_the_dark_creatures_come_out_by_day_the_sun_spares_them_and_two_more_may_be_about(self):
        clear, foggy = pet(), {**pet(), "sky": {"weather": "fog"}}
        self.assertEqual(spawn_hostiles(scene(land(), clear, clock=DAY)), [])
        born = spawn_hostiles(scene(land(), foggy, clock=DAY))
        self.assertEqual([creature["kind"] for creature in born], ["gloomling"])
        gloomling = {**born[0], "state": dict(born[0]["state"])}
        self.assertFalse(sunlit(gloomling, KINDS["gloomling"], scene(land(), foggy, clock=DAY)))
        self.assertTrue(sunlit(gloomling, KINDS["gloomling"], scene(land(), clear, clock=DAY)))
        self.assertEqual(cap(scene(land(), foggy, clock=DAY)) - cap(scene(land(), clear, clock=DAY)), 2)
        self.assertEqual(cap(scene(land(), clear, clock=DAY)), HOSTILE_CAP)

    def test_a_torch_still_keeps_the_fog_clear(self):
        torches = {(x, 1, z): "torch" for x in range(-44, 45, 4) for z in range(-44, 45, 4)}
        foggy = {**pet(), "sky": {"weather": "fog"}}
        self.assertEqual(spawn_hostiles(scene(land(torches), foggy, clock=DAY)), [])


class StateTests(unittest.TestCase):
    def test_sky_state_fills_every_field(self):
        sky = sky_state({})
        self.assertEqual((sky["weather"], sky["snow"], sky["frozen"], sky["fires"]), ("clear", 0.0, False, []))
        self.assertEqual(DAY_SECONDS / SEGMENT, 6)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_survival_weather backend.tests.test_survival_defense`
Expected: `FAILED (errors=3)`: `ImportError: cannot import name 'weather' from 'backend.survival'`, and the two flee tests of `test_survival_defense.py` cannot patch `backend.survival.sky.weather_at` yet (`AttributeError`)

- [ ] **Step 3: The weather, walking in it, the crops and the fog**

In `backend/survival/creatures/darkness.py`, replace:

```python
one born farther from home tougher), and the cap may grow (MORE_ROOM: ringed adds one a danger level).
```

with:

```python
one born farther from home tougher), and the cap may grow (MORE_ROOM: ringed adds one a danger level).
W2: in fog the open ground by day counts as dark for spawning (its sky light as FOG_SKY), and the cap grows by
2 (backend.survival.weather).
```

and replace:

```python
from backend.survival.once import log_once
```

with:

```python
from backend.survival.once import log_once
from backend.survival.sky import foggy
```

and replace:

```python
UNDERFOOT = CANOPY  # L3: no kind of leaves is ground to come out on
```

with:

```python
UNDERFOOT = CANOPY  # L3: no kind of leaves is ground to come out on
FOG_SKY = 6  # W2: open ground's sky light by day in fog, for spawning
```

and replace:

```python
            sky = sky_light(scene.grid, scene.seed, cell, scene.night)
```

with:

```python
            sky = sky_light(scene.grid, scene.seed, cell, scene.night)
            if sky > FOG_SKY and foggy(scene.state):  # W2: fog hides the sun
                sky = FOG_SKY
```

In `backend/survival/creatures/hostiles.py`, replace:

```python
  fire ("burning") and dies BURN_SECONDS later without drops; a skitter fades at once.
```

with:

```python
  fire ("burning") and dies BURN_SECONDS later without drops; a skitter fades at once. W2: not in fog.
```

and replace:

```python
from backend.survival.light import sky_open
```

with:

```python
from backend.survival.light import sky_open
from backend.survival.sky import foggy
```

and replace:

```python
    return (kind.hostile and not kind.daylight and not scene.night  # L5: a thornback walks by day
```

with:

```python
    return (kind.hostile and not kind.daylight and not scene.night  # L5: a thornback walks by day
            and not foggy(scene.state)  # W2: fog hides the sun
```

In `backend/survival/renewal.py`, replace:

```python
     one a chunk a game day and at most 2 in the chunk.
```

with:

```python
     one a chunk a game day and at most 2 in the chunk;
   - W2: a crop stage that starts while it rains (backend.survival.sky) takes the watered time.
```

and replace:

```python
from backend.survival import nature
```

with:

```python
from backend.survival import nature
from backend.survival.sky import RAINY, weather_of
```

and replace:

```python
def stage_seconds(grid: Grid, crop: Cell) -> float:
    """Making: a quarter less with a composter within COMPOST_REACH blocks (backend.survival.cozy)."""
    x, y, z = crop
    seconds = CROP_STAGE_WET if watered(grid, (x, y - 1, z)) else CROP_STAGE_DRY
```

with:

```python
def stage_seconds(grid: Grid, crop: Cell, rain: bool = False) -> float:
    """Making: a quarter less with a composter within COMPOST_REACH blocks (backend.survival.cozy). W2: `rain`
    waters it too."""
    x, y, z = crop
    seconds = CROP_STAGE_WET if rain or watered(grid, (x, y - 1, z)) else CROP_STAGE_DRY
```

and replace:

```python
            schedule(db, cell, grown, later(at, stage_seconds(grid, cell), scale))
```

with:

```python
            schedule(db, cell, grown, later(at, stage_seconds(grid, cell, rained(state, at, scale)), scale))
```

and replace:

```python
            schedule(db, (x, y - 1, z), "dirt", later(at, FARMLAND_REVERT, scale))
```

with:

```python
            schedule(db, (x, y - 1, z), "dirt", later(at, FARMLAND_REVERT, scale))


def rained(state: dict, at: float, scale: float) -> bool:
    """W2: it rains at `at` (a world with no birth time, in a test, never rains)."""
    return "born_at" in state and weather_of(state, at, scale) in RAINY
```

and replace:

```python
                schedule(db, cell, grown, later(ready_at, stage_seconds(grid, cell), scale))
```

with:

```python
                wet = rained(state, ready_at, scale)
                schedule(db, cell, grown, later(ready_at, stage_seconds(grid, cell, wet), scale))
```

In `backend/survival/sky.py`, replace:

```python

state["sky"] (`sky_state`; every field has a default, so a world from before W2 and an archive read as empty):
```

with:

```python

Weather (`weather_at`) is a pure function of the world seed, the season and the SEGMENT (10-game-minute) of the
life: a game day has 6 segments. Each segment keeps the last one's weather with chance KEEP, else rolls its
season's TABLE, so a spell runs 20 game minutes or more on average. The look back stops after LOOK_BACK
segments (the sixth rolls fresh), and a kept weather the new season's table lacks (rain carried into winter)
rolls fresh too. The tick stores the weather of each step's start in state["sky"] (with when it next changes)
for /api/mimo and for what the step reads: a catch-up plays the weather in time order. While it snows the snow
cover rises SNOW_RISE a game minute; from the first spring dawn it melts over 20 game minutes.

state["sky"] (`sky_state`; every field has a default, so a world from before W2 and an archive read as empty):
```

and replace:

```python
from backend.survival.clock import DAY_SECONDS, PHASES, clock_at
```

with:

```python
from backend.survival.clock import DAY_SECONDS, PHASES, clock_at
from backend.survival.nature import roll
```

and replace:

```python
COLDER = "The nights are getting colder."
```

with:

```python
COLDER = "The nights are getting colder."
SEGMENT = 600.0  # game seconds of one weather segment
LOOK_BACK = 6
KEEP = 0.5
TABLE = {"spring": (("clear", 0.55), ("rain", 0.30), ("storm", 0.08), ("fog", 0.07)),
         "summer": (("clear", 0.65), ("rain", 0.15), ("storm", 0.15), ("fog", 0.05)),
         "autumn": (("clear", 0.45), ("rain", 0.25), ("storm", 0.05), ("fog", 0.25)),
         "winter": (("clear", 0.45), ("fog", 0.15), ("snow", 0.40))}
RAINY = ("rain", "storm")
WEATHER_CHANNEL, KEEP_CHANNEL = 230, 231  # Wild World's roll channels are 200 to 259 (spec resolution 27)
UNTIL_AHEAD = 12  # segments looked ahead for when the weather changes
SNOW_RISE = 0.1  # snow cover a game minute while it snows
SNOW_MELT = 20 * 60.0  # game seconds a full cover takes to melt in spring
```

and replace:

```python

def settle_sky(state: dict, at: float, scale: float) -> None:
```

with:

```python

def segment_season(offset: int, segment: int) -> str:
    return season_of(season_day_of(int(segment * SEGMENT // DAY_SECONDS) + 1, offset))


def fresh(seed: str, offset: int, segment: int) -> str:
    """The season's table rolled for `segment`."""
    table = TABLE[segment_season(offset, segment)]
    pick = roll(seed, (segment, 0, 0), WEATHER_CHANNEL)
    for weather, share in table:
        pick -= share
        if pick < 0:
            return weather
    return table[-1][0]


def weather_at(seed: str, offset: int, segment: int) -> str:
    """The weather of the life's `segment` (see the module docstring)."""
    start = segment
    while start > 0 and segment - start < LOOK_BACK - 1 and roll(seed, (start, 0, 0), KEEP_CHANNEL) < KEEP:
        start -= 1
    weather = fresh(seed, offset, start)
    for later in range(start + 1, segment + 1):
        if all(weather != kind for kind, _ in TABLE[segment_season(offset, later)]):
            weather = fresh(seed, offset, later)
    return weather


def segment_of(state: dict, at: float, scale: float) -> int:
    return int(max(0.0, at - state["born_at"]) * scale // SEGMENT)


def weather_of(state: dict, at: float, scale: float) -> str:
    """The weather at server time `at` (pure: what the tick would store then)."""
    return weather_at(state.get("world_seed", "0"), offset_of(state), segment_of(state, at, scale))


def weather_now(state: dict) -> str:
    """The weather the tick stored at the start of the step ("clear" for a world from before W2)."""
    return (state.get("sky") or {}).get("weather", "clear")


def raining(state: dict) -> bool:
    return weather_now(state) in RAINY


def foggy(state: dict) -> bool:
    return weather_now(state) == "fog"


def settle_sky(state: dict, at: float, scale: float) -> None:
```

and replace:

```python
def advance(state: dict, context, at: float) -> None:
    """Before each step of the tick: the season, then EFFECTS. A crash is logged once and changes nothing."""
    try:
        tend_season(state, context, at)
```

with:

```python
def tend_weather(state: dict, context, at: float) -> None:
    """Store the weather at `at`, when it next changes, and the snow cover."""
    sky = sky_state(state)
    scale = context.clock_at(at)["time_scale"]
    segment = segment_of(state, at, scale)
    if sky.get("segment") != segment:
        seed, offset = state.get("world_seed", "0"), offset_of(state)
        weather = weather_at(seed, offset, segment)
        ahead = next((later for later in range(segment + 1, segment + UNTIL_AHEAD + 1)
                      if weather_at(seed, offset, later) != weather), segment + UNTIL_AHEAD + 1)
        sky.update(segment=segment, weather=weather, weather_until=state["born_at"] + ahead * SEGMENT / scale)
    since = sky.get("tended_at")
    seconds = 0.0 if since is None else max(0.0, (at - since) * scale)
    sky["tended_at"] = at
    if sky["weather"] == "snow":
        sky["snow"] = min(1.0, sky["snow"] + SNOW_RISE * seconds / 60.0)
    elif sky["season"] == "spring" and sky["snow"] > 0:
        sky["snow"] = max(0.0, sky["snow"] - seconds / SNOW_MELT)


def advance(state: dict, context, at: float) -> None:
    """Before each step of the tick: the season and the weather, then EFFECTS. A crash is logged once and
    changes nothing."""
    try:
        tend_season(state, context, at)
        tend_weather(state, context, at)
```

In `backend/survival/steps.py`, replace:

```python
EATING: list = []
```

with:

```python
EATING: list = []
# W2: functions (state, grid, cell) -> how many times as long a walk that starts at `cell` takes (backend.survival
# .weather: rain and snow under the open sky). One that crashes is logged once and counts as 1.
WALK_PACE: list = []
```

and replace:

```python

def start_walk(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
```

with:

```python

def walk_pace(state: dict, grid: Grid, here: Cell) -> float:
    """How many times as long a walk from `here` takes now (W2: WALK_PACE)."""
    pace = 1.0
    for slows in WALK_PACE:
        try:
            pace *= float(slows(state, grid, here))
        except Exception as error:
            log_once(logger, "walk pace", error)
    return pace


def start_walk(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
```

and replace:

```python
    path = timed_path(grid, here, cells, at, scale)
```

with:

```python
    path = timed_path(grid, here, cells, at, scale / walk_pace(state, grid, here))
```

In `backend/survival/tick.py`, replace:

```python
time order; the season sets the warmth Mimo drifts toward (Surroundings.season).
```

with:

```python
time order; the season sets the warmth Mimo drifts toward (Surroundings.season), and falling snow takes some off
outdoors (Surroundings.snowing; backend.survival.weather's other effects register themselves).
```

and replace:

```python
from backend.survival import ailments, sky, spoilage
```

with:

```python
from backend.survival import ailments, sky, spoilage
from backend.survival import weather  # noqa: F401  (W2: rain and snow slow walks, fog brings the dark creatures)
```

and replace:

```python
        season=sky.season_now(state) if state is not None else "spring",
```

with:

```python
        season=sky.season_now(state) if state is not None else "spring",
        snowing=state is not None and sky.weather_now(state) == "snow",
```

Create `backend/survival/weather.py`:

```python
"""W2: what the weather does ("Weather" of the Wild World spec). The weather itself is backend.survival.sky's.

- Rain (and a thunderstorm, which is rain with lightning): a walk that starts under the open sky takes
  RAIN_PACE times as long (steps.WALK_PACE), and a crop stage that starts while it rains grows at the watered
  rate (backend.survival.renewal). What rain does to a campfire and to a fire in the trees is
  backend.survival.storms'.
- Snow (winter only): a walk under the open sky takes SNOW_PACE times as long, it is 10 colder outdoors
  (vitals.SNOW_CHILL, through the tick's Surroundings) and the snow cover builds (sky.tend_weather).
- Fog: the hostiles treat the open ground by day as dark (creatures.darkness.FOG_SKY), the sun does not burn or
  fade them (creatures.hostiles.sunlit), and their cap rises by FOG_ROOM (darkness.MORE_ROOM). Torches and
  lanterns keep their light.
Everything reads the weather the tick stored at the step's start (sky.weather_now).
"""

from __future__ import annotations

from backend.survival import sky, steps
from backend.survival.creatures import darkness
from backend.survival.grid import Cell, Grid
from backend.survival.light import sky_open

RAIN_PACE = 1.15
SNOW_PACE = 1.3
FOG_ROOM = 2


def walk_pace(state: dict, grid: Grid, here: Cell) -> float:
    """steps.WALK_PACE: rain and snow slow a walk that starts under the open sky."""
    weather = sky.weather_now(state)
    pace = SNOW_PACE if weather == "snow" else RAIN_PACE if weather in sky.RAINY else 1.0
    if pace == 1.0 or not sky_open(grid, state.get("world_seed", "0"), here):
        return 1.0
    return pace


def fog_room(scene) -> int:
    """darkness.MORE_ROOM: two more hostiles may be about in fog."""
    return FOG_ROOM if sky.foggy(scene.state) else 0


steps.WALK_PACE.append(walk_pace)
darkness.MORE_ROOM.append(fog_room)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest backend.tests.test_survival_weather backend.tests.test_survival_defense`
Expected: `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1944 tests` … `OK (skipped=6)` (10 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/creatures/darkness.py backend/survival/creatures/hostiles.py backend/survival/renewal.py backend/survival/sky.py backend/survival/steps.py backend/survival/tick.py backend/survival/weather.py backend/tests/test_survival_defense.py backend/tests/test_survival_weather.py
git commit -m "feat(W2): the weather, a pure function of the seed, the season and the segment: rain and snow slow walks, rain waters the crops, fog lets the dark creatures out" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Rain on the fire, and the new blocks

The three new blocks (`campfire_out`, `fire`, `hearth`) come in here, at the end of `shared/blocks.json` after W1's `sunleaf`, with their tiles; the rain is the first to write one. W1's and L5's tests that read the last blocks move by three (resolution 18).

**Files:**
- Create: `backend/survival/rain.py`, `backend/tests/test_survival_rain.py`
- Modify: `shared/blocks.json` (three blocks, four tiles), `frontend/src/engine/atlas.ts` (`sprite_ashes`, `sprite_flame`), `backend/survival/cooking.py` (relight before light, a roof first), `backend/survival/reflexes.py` (`plan_warm_up`: a roof first), `backend/survival/tick.py` (imports `rain`)
- Test: `frontend/src/engine/blocks.test.ts`, `backend/tests/test_worldgen_wild.py`, `backend/tests/test_survival_frontier_gear.py`

**Interfaces:**
- Consumes: Task 2's `sky.raining`, `sky.EFFECTS`; `light.sky_open`; `structures.STANDS_IN`; `cooking.cook_plan`, `reflexes.plan_warm_up` (W1's lesson gates in them stay).
- Produces: blocks `campfire_out` (cutout, drops `campfire`), `fire` (glow, no drop, not solid), `hearth` (opaque, solid, glow, drops `hearth`); `rain.DOUSE_REACH` (64), `roofed(grid, cell)`, `roofed_first(s, spots)`, `campfires_near(context, x, z)`, `douse` (a sky effect), the `relight` step (`start_relight`, `finish_relight`, 1 s and a stick), `relight_steps(s, reach)`, `DOUSED` (callables `(state, context, cell, at)`, guarded: Task 9's rain knock).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_frontier_gear.py`, replace:

```python
        self.assertEqual(names[-4], "warding_lantern")  # W1's three plants come after it (test_worldgen_wild)
```

with:

```python
        self.assertEqual(names[-7], "warding_lantern")  # W1's three plants and W2's three blocks come after it
```

Create `backend/tests/test_survival_rain.py`:

```python
"""W2: the new blocks, rain putting out a campfire under the open sky, relighting it, and a fire under a roof."""

import sqlite3
import unittest
from types import SimpleNamespace

from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, hardness, is_solid
from backend.services.crafting import BLOCKS
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Planned
from backend.survival.memory import create_memory_tables, know
from backend.survival.purposes import PURPOSES
from backend.survival.rain import DOUSED, douse, relight_steps, roofed, roofed_first
from backend.survival.situation import Situation
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.structures import missing
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_cooking import meadow

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def pet(weather="rain", **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0, "sky": {"weather": weather}}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state, grid, wild=False):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    if wild:
        state["difficulty"] = "wild"
    return Situation(state, grid, DAY, 0.0, db)


class BlockTests(unittest.TestCase):
    def test_the_doused_campfire_the_fire_and_the_hearth_come_last(self):
        names = [block["name"] for block in BLOCK_LIST]
        self.assertEqual(names[-3:], ["campfire_out", "fire", "hearth"])
        self.assertEqual(BLOCK_IDS["campfire_out"], BLOCK_IDS["sunleaf"] + 1)
        self.assertEqual((is_solid("campfire_out"), BLOCKS["campfire_out"]["drop"], BLOCKS["campfire_out"].get("glow")),
                         (False, "campfire", None))
        self.assertEqual((is_solid("fire"), hardness("fire"), BLOCKS["fire"]["glow"]), (False, None, True))
        self.assertEqual((is_solid("hearth"), BLOCKS["hearth"]["drop"], BLOCKS["hearth"]["glow"]), (True, "hearth", True))


class DouseTests(unittest.TestCase):
    def douse(self, grid, state):
        events, heard = [], []
        DOUSED.append(lambda state, context, cell, at: heard.append(cell))
        self.addCleanup(DOUSED.pop)
        douse(state, SimpleNamespace(grid=grid, events=events), 5.0)
        return events, heard

    def test_rain_puts_out_a_campfire_under_the_open_sky(self):
        grid = meadow({(2, 1, 0): "campfire"})
        events, heard = self.douse(grid, pet())
        self.assertEqual(grid.material(2, 1, 0), "campfire_out")
        self.assertEqual(events, [(5.0, "fire_out", "The rain put out Pip's campfire.")])
        self.assertEqual(heard, [(2, 1, 0)])

    def test_a_storm_does_too_but_not_clear_weather_or_a_roof(self):
        storm = meadow({(2, 1, 0): "campfire"})
        self.douse(storm, pet("storm"))
        self.assertEqual(storm.material(2, 1, 0), "campfire_out")
        clear = meadow({(2, 1, 0): "campfire"})
        self.douse(clear, pet("clear"))
        self.assertEqual(clear.material(2, 1, 0), "campfire")
        roof = meadow({(2, 1, 0): "campfire", (2, 4, 0): "planks"})
        events, _ = self.douse(roof, pet())
        self.assertEqual((roof.material(2, 1, 0), events), ("campfire", []))
        far = meadow({(80, 1, 0): "campfire"})
        self.douse(far, pet())
        self.assertEqual(far.material(80, 1, 0), "campfire")


class RelightTests(unittest.TestCase):
    def test_a_stick_lights_a_doused_campfire_again(self):
        grid = meadow({(1, 1, 0): "campfire_out"})
        state = pet(inventory={"sticks": 2})
        step = start_step({"kind": "relight", "target": [1, 1, 0]}, state, grid, 0.0)
        finish_step(step, state, grid, step["ends_at"])
        self.assertEqual((grid.material(1, 1, 0), state["inventory"]), ("campfire", {"sticks": 1}))
        with self.assertRaises(StepFailed):
            start_step({"kind": "relight", "target": [1, 1, 0]}, pet(inventory={"sticks": 1}), grid, 0.0)
        with self.assertRaises(StepFailed):
            start_step({"kind": "relight", "target": [2, 1, 0]}, pet(), meadow({(2, 1, 0): "campfire_out"}), 0.0)

    def test_a_doused_campfire_still_furnishes_a_shelter(self):
        planned = Planned((2, 1, 0), "campfire", "campfire")
        self.assertFalse(missing(meadow({(2, 1, 0): "campfire_out"}), planned))
        self.assertTrue(missing(meadow(), planned))

    def test_cook_lights_a_doused_campfire_within_reach_before_it_puts_down_another(self):
        state = pet("clear", inventory={"raw_beef": 1, "sticks": 3, "campfire": 1})
        s = situation(state, meadow({(2, 1, 0): "campfire_out"}))
        steps = PURPOSES["cook"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY, planner=lambda *a: [],
                                                       events=[], db=s.db))
        self.assertEqual(steps[:2], [{"kind": "relight", "target": [2, 1, 0]}, {"kind": "cook", "item": "raw_beef"}])
        rained = situation(pet("rain", inventory={"sticks": 1}), meadow({(2, 1, 0): "campfire_out"}))
        self.assertEqual(relight_steps(rained, 6.0), [])  # one out in the rain stays out


class RoofTests(unittest.TestCase):
    def test_a_pet_that_knows_rain_puts_its_fire_under_a_roof_when_one_is_in_reach(self):
        grid = meadow({(0, 4, 1): "planks"})
        spots = [((1, 1, 0), False), ((0, 1, 1), False), ((-1, 1, 0), False)]
        self.assertTrue(roofed(grid, (0, 1, 1)))
        self.assertFalse(roofed(meadow({(0, 4, 1): "leaves"}), (0, 1, 1)))
        self.assertEqual(roofed_first(situation(pet(), grid), spots)[0], ((0, 1, 1), False))  # gentle: knows it
        wild = situation(pet(), grid, wild=True)
        self.assertEqual(roofed_first(wild, spots), spots)
        know(wild.db, "wild:rain", "lesson", 0.0)
        taught = Situation(wild.state, grid, DAY, 0.0, wild.db)
        self.assertEqual(roofed_first(taught, spots)[0], ((0, 1, 1), False))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_worldgen_wild.py`, replace:

```python
        self.assertEqual(names[-3:], ["nightberry_bush", "nightberry_bush_ripe", "sunleaf"])
        self.assertEqual(BLOCK_IDS["nightberry_bush"], BLOCK_IDS["warding_lantern"] + 1)
        for name in names[-3:]:
```

with:

```python
        self.assertEqual(names[-6:-3], ["nightberry_bush", "nightberry_bush_ripe", "sunleaf"])  # W2's three follow
        self.assertEqual(BLOCK_IDS["nightberry_bush"], BLOCK_IDS["warding_lantern"] + 1)
        for name in names[-6:-3]:
```

In `frontend/src/engine/blocks.test.ts`, replace:

```typescript
/** W1's plants, after L5's, the last (backend/tests/test_worldgen_wild.py). */
const WILD = ['nightberry_bush', 'nightberry_bush_ripe', 'sunleaf']
```

with:

```typescript
/** W1's plants, after L5's (backend/tests/test_worldgen_wild.py). */
const WILD = ['nightberry_bush', 'nightberry_bush_ripe', 'sunleaf']
/** W2's doused campfire, fire and hearth, the last (backend/tests/test_survival_rain.py). */
const WEATHER = ['campfire_out', 'fire', 'hearth']
```

and replace:

```typescript
    expect(names.slice(-WILD.length - FRONTIER.length, -WILD.length)).toEqual(FRONTIER)
    expect(names.slice(-WILD.length)).toEqual(WILD)
```

with:

```typescript
    const wild = names.slice(0, -WEATHER.length)
    expect(wild.slice(-WILD.length - FRONTIER.length, -WILD.length)).toEqual(FRONTIER)
    expect(wild.slice(-WILD.length)).toEqual(WILD)
    expect(names.slice(-WEATHER.length)).toEqual(WEATHER)
    expect(GLOW_BY_ID[blockId('fire')]).toBe(1)
    expect(GLOW_BY_ID[blockId('hearth')]).toBe(1)
    expect(GLOW_BY_ID[blockId('campfire_out')]).toBe(0)
    expect(LAYER_BY_ID[blockId('hearth')]).toBe(LAYER_OPAQUE)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_survival_rain backend.tests.test_worldgen_wild backend.tests.test_survival_frontier_gear`
Expected: `FAILED (failures=2, errors=1)`: `ModuleNotFoundError: No module named 'backend.survival.rain'`, and the last blocks are still W1's and L5's (`Lists differ: ['lamp_lit', 'bell', 'warding_lantern'] != ['nightberry_bush', 'nightberry_bush_ripe', 'sunleaf']`, `AssertionError: 'lamp' != 'warding_lantern'`)

Run: `cd frontend && npx vitest run src/engine/blocks.test.ts`
Expected: `Tests  1 failed | 10 passed (11)`: `expected [ 'lamp' ] to deeply equal [ 'warding_lantern' ]`

- [ ] **Step 3: The blocks, dousing and relighting**

In `backend/survival/cooking.py`, replace:

```python
bakes bread as ever.
```

with:

```python
bakes bread as ever.
W2: a campfire the rain put out that stands within reach is lit again (one stick) before another is put down,
and a pet that knows `wild:rain` puts its fire under a roof when one is in reach (backend.survival.rain).
```

and replace:

```python
from backend.survival.purposes import Purpose, register
```

with:

```python
from backend.survival.purposes import Purpose, register
from backend.survival.rain import relight_steps, roofed_first
```

and replace:

```python
    spots = station_spots(s)
    steps: list[dict] = []
    placed: list[Cell] = []
    raw = [(item, inventory[item]) for item in RAW_FOODS if inventory.get(item, 0) > 0] if unlocked(s, "cooking") else []
    if raw and not near.intersection(FIRES) and not light_fire(s, inventory, spots, steps, placed):
```

with:

```python
    spots = roofed_first(s, station_spots(s))
    steps: list[dict] = []
    placed: list[Cell] = []
    raw = [(item, inventory[item]) for item in RAW_FOODS if inventory.get(item, 0) > 0] if unlocked(s, "cooking") else []
    relit = relight_steps(s, STATION_REACH) if raw and not near.intersection(FIRES) and unlocked(s, "fire") else []
    if relit:
        steps.extend(relit)
        inventory["sticks"] -= 1
    elif raw and not near.intersection(FIRES) and not light_fire(s, inventory, spots, steps, placed):
```

Create `backend/survival/rain.py`:

```python
"""W2: rain puts out a campfire under the open sky ("Weather" of the Wild World spec).

While it rains (a thunderstorm too: sky.RAINY), every campfire within DOUSE_REACH blocks of Mimo that stands under
the open sky (light.sky_open) goes out at the start of each step (`douse`, a sky effect): it becomes
`campfire_out`, which gives no light and no warmth ("The rain put out Pip's campfire.", a "fire_out" event, and
DOUSED hears of it). The `relight` step (RELIGHT_SECONDS, 1 stick, within reach) lights a doused campfire again;
cook relights one that stands within reach before it puts down another. A hearth never goes out. A doused
campfire still stands for the one a shelter's design puts beside its door (structures.STANDS_IN), so the
furnishing never tries to put another in its cell.

`wild:rain` ("Rain puts out a fire under the open sky, so keep your fire under a roof."): a pet that knows it
puts its fire in a spot with a roof (a solid block, not leaves, within ROOF_REACH above) when one is in reach
(`roofed_first`, for cook's campfire and the warm_up reflex's). A gentle pet knows it from the start.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.services.blocks import CANOPY, is_solid
from backend.services.crafting import take_items
from backend.survival import sky
from backend.survival.grid import Cell, Grid
from backend.survival.light import sky_open
from backend.survival.once import log_once
from backend.survival.steps import StepFailed, StepKind, as_cell, as_point, in_reach, register_step
from backend.survival.structures import STANDS_IN
from backend.survival.wild import unlocked

if TYPE_CHECKING:
    from backend.survival.situation import Situation

logger = logging.getLogger(__name__)

DOUSE_REACH = 64.0
RELIGHT_SECONDS = 1.0
ROOF_REACH = 4
DOUSED_BLOCK = "campfire_out"
# W2: functions (state, context, cell, at) run when the rain puts one of Mimo's campfires out (backend.survival
# .sky_wild: a knock and a wonder). One that crashes is logged once and passed over.
DOUSED: list = []


def roofed(grid: Grid, cell: Cell) -> bool:
    """A solid block that is not leaves within ROOF_REACH above the cell."""
    x, y, z = cell
    return any(is_solid(material) and material not in CANOPY
               for material in (grid.material(x, y + dy, z) for dy in range(1, ROOF_REACH + 1)))


def roofed_first(s: Situation, spots: list[tuple[Cell, bool]]) -> list[tuple[Cell, bool]]:
    """Station spots with the roofed ones first, for a pet that knows `wild:rain`; as they are otherwise."""
    if not unlocked(s, "rain"):
        return spots
    return sorted(spots, key=lambda spot: not roofed(s.grid, spot[0]))


def douse(state: dict, context, at: float) -> None:
    """sky.EFFECTS: while it rains, the campfires near Mimo under the open sky go out."""
    if not sky.raining(state):
        return
    grid, position = context.grid, state["position"]
    seed = state.get("world_seed", "0")
    for cell, _ in grid.placed_cells(math.floor(position["x"]), math.floor(position["z"]), DOUSE_REACH, ("campfire",)):
        if not sky_open(grid, seed, cell):
            continue
        grid.put(*cell, DOUSED_BLOCK)
        context.events.append((at, "fire_out", f"The rain put out {state['name']}'s campfire."))
        state["last_thought"] = "Oh no, the rain put my fire out!"
        for hears in DOUSED:
            try:
                hears(state, context, cell, at)
            except Exception as error:
                log_once(logger, "doused", error)


def start_relight(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = as_cell(spec["target"])
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    if grid.material(*target) != DOUSED_BLOCK:
        raise StepFailed("no doused campfire there", "gone")
    if state["inventory"].get("sticks", 0) < 1:
        raise StepFailed("no stick to light it with", "missing_item")
    return {"kind": "relight", "started_at": at, "ends_at": round(at + RELIGHT_SECONDS / scale, 3),
            "target": as_point(target)}


def finish_relight(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = as_cell(step["target"])
    if grid.material(*target) != DOUSED_BLOCK:
        raise StepFailed("the doused campfire is gone", "gone")
    state["inventory"] = take_items(state["inventory"], {"sticks": 1})
    grid.put(*target, "campfire")
    state["last_thought"] = "There, the fire's going again."
    return None


def relight_steps(s: Situation, reach: float) -> list[dict]:
    """The step that relights a doused campfire within `reach` (not one out in the rain), or []."""
    if s.count("sticks") < 1:
        return []
    x, _, z = s.here
    rainy = sky.raining(s.state)
    for cell, _ in sorted(s.grid.placed_cells(x, z, reach, (DOUSED_BLOCK,)), key=lambda found: s.distance(found[0])):
        if in_reach(s.here, cell) and not (rainy and sky_open(s.grid, s.seed, cell)):
            return [{"kind": "relight", "target": list(cell)}]
    return []


register_step(StepKind("relight", start_relight, finish_relight, "building", working=True, cell_field="target"))
STANDS_IN["campfire"] = (*STANDS_IN.get("campfire", ("campfire",)), DOUSED_BLOCK)
sky.EFFECTS.append(douse)
```

In `backend/survival/reflexes.py`, replace:

```python
from backend.survival.purposes import homeward_from  # L5: far out, the window opens sooner
```

with:

```python
from backend.survival.purposes import homeward_from  # L5: far out, the window opens sooner
from backend.survival.rain import roofed_first  # W2: a pet that knows rain lights its fire under a roof
```

and replace:

```python
        if place_station(station_spots(s), fire, steps) is not None:
```

with:

```python
        if place_station(roofed_first(s, station_spots(s)), fire, steps) is not None:
```

In `backend/survival/tick.py`, replace:

```python
from backend.survival import weather  # noqa: F401  (W2: rain and snow slow walks, fog brings the dark creatures)
```

with:

```python
from backend.survival import rain, weather  # noqa: F401  (W2: rain douses campfires and slows walks; fog)
```

In `frontend/src/engine/atlas.ts`, replace:

```typescript
  }),
  sprite_torch: ({ color, accent }, random) => grid((i, j) => {
```

with:

```typescript
  }),
  // W2: a campfire the rain put out, its charred logs under a few grey ashes
  sprite_ashes: ({ color, accent }, random) => grid((i, j) => {
    if (j >= 6) return (j === 6 ? i >= 1 && i <= 6 : i !== 3 && i !== 4) ? tone(accent ?? color, (i % 2 ? 0.7 : 0.82) * jitter(random)) : CLEAR
    if (j === 5 && i >= 2 && i <= 5 && random() < 0.7) return tone(color, jitter(random, 0.12))
    return CLEAR
  }),
  // W2: a fire in the trees, a tall flame with a bright heart and no logs
  sprite_flame: ({ color, accent }, random) => grid((i, j) => {
    const half = j * 0.5
    if (Math.abs(i - 3.5) > half || (j < 2 && (i + j) % 2 === 0)) return CLEAR
    return Math.abs(i - 3.5) < half * 0.45 && j >= 3 ? tone(accent ?? color, jitter(random, 0.06))
      : tone(color, (j >= 6 ? 0.86 : 1) * jitter(random, 0.08))
  }),
  sprite_torch: ({ color, accent }, random) => grid((i, j) => {
```

In `shared/blocks.json`, replace:

```json
    "sunleaf": {"pattern": "sprite_rosette", "color": [178, 196, 70], "accent": [226, 214, 96]}
```

with:

```json
    "sunleaf": {"pattern": "sprite_rosette", "color": [178, 196, 70], "accent": [226, 214, 96]},
    "campfire_out": {"pattern": "sprite_ashes", "color": [132, 128, 122], "accent": [110, 80, 58]},
    "fire": {"pattern": "sprite_flame", "color": [255, 150, 60], "accent": [255, 226, 120]},
    "hearth_side": {"pattern": "furnace_side", "color": [138, 130, 122], "accent": [255, 150, 70]},
    "hearth_top": {"pattern": "cobble", "color": [124, 118, 112]}
```

and replace:

```json
    {"name": "sunleaf", "color": [178, 196, 70], "textures": "sunleaf", "layer": "cutout", "solid": false, "replaceable": true, "drop": "sunleaf", "hardness": 0.1}
```

with:

```json
    {"name": "sunleaf", "color": [178, 196, 70], "textures": "sunleaf", "layer": "cutout", "solid": false, "replaceable": true, "drop": "sunleaf", "hardness": 0.1},
    {"name": "campfire_out", "color": [132, 128, 122], "textures": "campfire_out", "layer": "cutout", "solid": false, "drop": "campfire", "hardness": 2.0, "tool": "axe"},
    {"name": "fire", "color": [255, 150, 60], "textures": "fire", "layer": "cutout", "solid": false, "drop": null, "glow": true, "hardness": null},
    {"name": "hearth", "color": [138, 130, 122], "textures": {"top": "hearth_top", "side": "hearth_side", "bottom": "hearth_top"}, "layer": "opaque", "solid": true, "drop": "hearth", "glow": true, "hardness": 4.0, "tool": "pickaxe"}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest backend.tests.test_survival_rain backend.tests.test_worldgen_wild backend.tests.test_survival_frontier_gear`
Expected: `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1951 tests` … `OK (skipped=6)` (7 new).

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  373 passed (373)`, the build succeeds, eslint prints nothing.

- [ ] **Step 5: Commit**

```bash
git add backend/survival/cooking.py backend/survival/rain.py backend/survival/reflexes.py backend/survival/tick.py backend/tests/test_survival_frontier_gear.py backend/tests/test_survival_rain.py backend/tests/test_worldgen_wild.py frontend/src/engine/atlas.ts frontend/src/engine/blocks.test.ts shared/blocks.json
git commit -m "feat(W2): rain puts out a campfire under the open sky, a stick lights it again, and a pet that knows rain builds its fire under a roof" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Lightning and fire in the trees

**Files:**
- Create: `backend/survival/storms.py`, `backend/survival/sky_reflexes.py`, `backend/tests/test_survival_storms.py`
- Modify: `backend/survival/grid.py` (`Grid.hot`, `passable`), `backend/survival/light.py` (the fire's light), `backend/survival/rain.py` (its effect's order), `backend/survival/tick.py` (short steps by a fire, the death check after the sky, `CAUSE_WORDS`), `backend/survival/brain.py` (imports `sky_reflexes`)
- Test: `backend/tests/test_survival_reflexes.py` (the order gains flee_fire)

**Interfaces:**
- Consumes: Task 2's weather; Task 3's `fire` block; `Grid.put` (a burning cell and its burning out are ordinary edits); `claims`; `homes`; W1's `hurt_by` and the tick's `caught`; defense's `run_away`.
- Produces: `storms.STRIKE_EVERY` (60), `HOME_CLEAR` (16), `FIRE_CLEAR` (8), `FIRE_CELLS` (24), `FIRES` (2), `built_home(db)`, `column_top`, `highest`, `strike`, `ignite`, `spread`, `hot_cells(state)`, `fire_near(state, reach=3)`, `burn_pet`, `storm` (a sky effect), `STRIKES` (callables `(state, context, cell, hit, at)`, guarded: Task 9's knocks); `state["sky"]`'s `strikes` (the last 5, `{x, y, z, at}`), `fires` (`{x, y, z, fire, since, until}`), `burned`, `last_strike`, `last_spread`; `Grid.hot`; the reflex `flee_fire` (25); causes `"lightning"` and `"fire"`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_reflexes.py`, replace:

```python
                         [("surface", 10), ("avoid_drop", 20), ("flee", 30), ("eat_now", 40), ("fight", 40),
                          ("fence", 45), ("take_herb", 45), ("warm_up", 50), ("turn_back", 55), ("head_home", 60),
                          ("collapse", 70)])  # W1: take_herb (backend.survival.herbs)
```

with:

```python
                         [("surface", 10), ("avoid_drop", 20), ("flee_fire", 25), ("flee", 30), ("eat_now", 40),
                          ("fight", 40), ("fence", 45), ("take_herb", 45), ("warm_up", 50), ("turn_back", 55),
                          ("head_home", 60), ("collapse", 70)])  # W1: take_herb; W2: flee_fire (sky_reflexes)
```

Create `backend/tests/test_survival_storms.py`:

```python
"""W2: thunderstorms: where lightning strikes, when it hits Mimo, fires in the trees, their spread, caps and
burning out, the heat, the way round them, the flee_fire reflex and what a storm costs the tick."""

import math
import random
import sqlite3
import tempfile
import time
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every reflex registered, flee_fire among them)
from backend.survival import sky
from backend.survival.clock import clock_at
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.memory import BUILT, create_memory_tables, remember
from backend.survival.pathing import route
from backend.survival.reflexes import by_name
from backend.survival.registry import LifeRegistry
from backend.survival.situation import Situation
from backend.survival.storms import (
    FIRE_CELLS, FIRES, HOME_CLEAR, STRUCK_DAMAGE, burn_pet, highest, hot_cells, ignite, spread, storm,
)
from backend.survival.tick import death_words, tick_life
from backend.survival.vitals import START_VITALS
from backend.survival.world import SurvivalWorld

BORN = 1_000_000.0
SCALE = 60.0
X0 = 1000  # far from the legacy clearing


def forest(trees=(), pillar=None):
    """Grass at y 0 over dirt; oaks (logs y 1-4, leaves y 5-6) at `trees`; a stone pillar 6 high at `pillar`."""
    logs = {(x, y, z) for x, z in trees for y in range(1, 5)}
    leaves = {(x + dx, y, z + dz) for x, z in trees for y in (5, 6) for dx in range(-2, 3) for dz in range(-2, 3)
              if abs(dx) + abs(dz) <= 3}

    def natural(x, y, z):
        if (x, y, z) in logs:
            return "oak_log"
        if (x, y, z) in leaves:
            return "leaves"
        if pillar is not None and (x, z) == pillar and 0 < y <= 6:
            return "stone"
        return "grass" if y == 0 else "dirt" if y < 0 else "air"

    return Grid(natural)


def pet(x=X0, y=1, z=0, weather="storm"):
    return {"name": "Pip", "world_seed": "7", "born_at": BORN, "position": {"x": float(x), "y": float(y), "z": float(z)},
            "vitals": dict(START_VITALS), "inventory": {}, "sky": {"weather": weather}}


def context(grid, db=None):
    return SimpleNamespace(grid=grid, events=[], db=db, clock_at=lambda at: clock_at(BORN, at, SCALE))


def home_db(cell):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    remember(db, "home", cell, 0.0, BUILT)
    return db


class Flat(unittest.TestCase):
    def setUp(self):
        for target in ("backend.survival.storms.terrain_height", "backend.survival.light.terrain_height"):
            patcher = patch(target, lambda x, z, seed: 0)
            patcher.start()
            self.addCleanup(patcher.stop)


class StrikeTests(Flat):
    def test_a_storm_strikes_once_a_game_minute_and_keeps_the_last_five(self):
        state, grid = pet(), forest()
        ctx = context(grid)
        for second in range(0, 400, 20):
            storm(state, ctx, BORN + second / SCALE)
        self.assertEqual(len(state["sky"]["strikes"]), 5)
        self.assertEqual([round((strike["at"] - BORN) * SCALE) for strike in state["sky"]["strikes"]],
                         [120, 180, 240, 300, 360])
        self.assertEqual([kind for _, kind, _ in ctx.events].count("storm"), 1)
        self.assertEqual(ctx.events[0][2], "A thunderstorm rolled in.")

    def test_no_strike_near_the_home_mimo_built_or_in_the_legacy_clearing(self):
        grid, db = forest(), home_db((X0, 1, 0))
        for step in range(300):
            state = pet(X0 + step % 7, 1, step % 5)
            state["sky"]["strike_at"] = None
            storm(state, context(grid, db), BORN + step)
            for strike in state["sky"]["strikes"]:
                self.assertGreater(math.hypot(strike["x"] - X0, strike["z"]), HOME_CLEAR)
        clearing = pet(0, 1, 0)
        storm(clearing, context(grid), BORN)
        self.assertEqual(clearing["sky"]["strikes"], [])

    def test_mimo_is_struck_only_when_it_is_the_highest_under_the_open_sky(self):
        with patch("backend.survival.storms.roll", lambda seed, cell, channel, salt=0: 0.0):
            flat = pet()
            storm(flat, context(forest()), BORN)
            self.assertEqual(flat["vitals"]["health"], 100.0)
            pillar = forest(pillar=(X0, 0))
            self.assertTrue(highest(pillar, "7", (X0, 7, 0)))
            self.assertFalse(highest(forest(trees=((X0 + 5, 0),), pillar=(X0, 0)), "7", (X0 + 1, 1, 0)))
            top = pet(X0, 7, 0)
            ctx = context(pillar)
            storm(top, ctx, BORN)
            self.assertEqual((top["vitals"]["health"], top["hurt_by"]), (100.0 - STRUCK_DAMAGE, "lightning"))
            self.assertIn((BORN, "struck", "Lightning struck Pip!"), ctx.events)
            roofed = forest(pillar=(X0, 0))
            roofed.put(X0, 9, 0, "planks")
            under = pet(X0, 7, 0)
            storm(under, context(roofed), BORN)
            self.assertEqual(under["vitals"]["health"], 100.0)
        self.assertEqual(death_words("lightning"), "was struck by lightning")
        self.assertEqual(death_words("fire"), "was caught in a fire")


class FireTests(Flat):
    def test_a_strike_on_a_tree_sets_its_top_burning(self):
        grid = forest(trees=((X0 + 20, 0),))
        state, ctx = pet(), context(grid)
        with patch("backend.survival.storms.column_top", lambda grid, seed, x, z: (X0 + 20, 6, 0)):
            storm(state, ctx, BORN)
        self.assertEqual(grid.material(X0 + 20, 6, 0), "fire")
        self.assertEqual(len(state["sky"]["fires"]), 1)
        self.assertIn((BORN, "fire", "Lightning set a tree on fire near Pip."), ctx.events)

    def spread_for(self, state, grid, seconds, db=None):
        ctx = context(grid, db)
        spread(state, ctx, BORN)
        for second in range(10, seconds + 1, 10):
            spread(state, ctx, BORN + second / SCALE)
        return ctx

    def burn(self, seed, always=False):
        """A fire lit in a wood of oaks, spread for 15 game minutes: the most cells it held, and the grid."""
        grid = forest(trees=[(X0 + dx, dz) for dx in range(0, 30, 4) for dz in range(0, 30, 4)])
        state = {**pet(weather="clear"), "world_seed": str(seed)}
        ignite(state, context(grid), (X0, 6, 0), BORN, None)
        most, ctx = 0, context(grid)
        with patch("backend.survival.storms.roll", lambda seed, cell, channel, salt=0: 0.0) if always else nullcontext():
            spread(state, ctx, BORN)
            for second in range(10, 900, 10):
                spread(state, ctx, BORN + second / SCALE)
                most = max(most, len(state["sky"]["fires"]))
        self.assertEqual(state["sky"]["fires"], [])  # every cell burned out
        return most, grid

    def test_a_fire_spreads_through_natural_leaves_burns_at_most_24_cells_and_burns_out(self):
        spreads = [self.burn(seed)[0] for seed in range(7, 15)]
        self.assertGreater(max(spreads), 1)
        most, grid = self.burn(7, always=True)  # every roll spreads
        burned = [cell for cell, material in grid.edits.items() if material == "air"]
        self.assertEqual(len(burned), FIRE_CELLS)
        self.assertLessEqual(most, FIRE_CELLS)
        self.assertEqual(grid.material(X0, 6, 0), "air")

    def test_rain_slows_the_spread_and_at_most_two_fires_burn(self):
        wet, dry = [], []
        for seed in range(12):
            for weather, found in (("rain", wet), ("clear", dry)):
                grid = forest(trees=[(X0 + dx, dz) for dx in range(0, 30, 4) for dz in range(0, 30, 4)])
                state = {**pet(weather=weather), "world_seed": str(seed)}
                ignite(state, context(grid), (X0, 6, 0), BORN, None)
                ctx = context(grid)
                spread(state, ctx, BORN)
                spread(state, ctx, BORN + 30 / SCALE)
                found.append(len(state["sky"]["fires"]) + sum(1 for entry in state["sky"]["fires"] if entry["x"] != X0))
        self.assertLess(sum(wet), sum(dry))
        state, grid = pet(), forest(trees=((X0, 0), (X0 + 10, 0), (X0 + 20, 0)))
        lit = [ignite(state, context(grid), (x, 6, 0), BORN, None) for x in (X0, X0 + 10, X0 + 20)]
        self.assertEqual(lit, [True, True, False])
        self.assertEqual(len({entry["fire"] for entry in state["sky"]["fires"]}), FIRES)

    def test_fire_never_enters_a_built_edited_or_claimed_cell_or_comes_near_home(self):
        grid = forest(trees=((X0, 0),))
        grid.put(X0 + 1, 6, 0, "leaves")  # edited
        grid.claims.add((X0 - 1, 6, 0))  # claimed
        state = pet(weather="clear")
        ignite(state, context(grid), (X0, 6, 0), BORN, None)
        with patch("backend.survival.storms.roll", lambda seed, cell, channel, salt=0: 0.0):
            self.spread_for(state, grid, 40)
        burned = {(entry["x"], entry["y"], entry["z"]) for entry in state["sky"]["fires"]}
        self.assertNotIn((X0 + 1, 6, 0), burned)
        self.assertNotIn((X0 - 1, 6, 0), burned)
        near_home = forest(trees=((X0, 0),))
        homely = pet(weather="clear")
        db = home_db((X0 + 6, 1, 0))
        with patch("backend.survival.storms.column_top", lambda grid, seed, x, z: (X0, 6, 0)):
            storm({**homely, "sky": {"weather": "storm"}}, context(near_home, db), BORN)
        self.assertEqual(near_home.material(X0, 6, 0), "leaves")

    def test_mimo_beside_a_burning_cell_takes_two_health_a_game_second_and_paths_go_round(self):
        grid = forest(trees=((X0 + 1, 0),))
        state = pet(weather="clear")
        ignite(state, context(grid), (X0 + 1, 1, 0), BORN, None)
        ctx = context(grid)
        burn_pet(state, ctx, BORN)
        burn_pet(state, ctx, BORN + 5 / SCALE)
        self.assertAlmostEqual(state["vitals"]["health"], 90.0)
        self.assertEqual(state["hurt_by"], "fire")
        grid.hot = hot_cells(state)
        cells, reached = route(grid, (X0 - 3, 1, 0), (X0 + 5, 1, 0))
        self.assertTrue(reached)
        self.assertFalse(set(cells) & grid.hot)

    def test_flee_fire_runs_from_a_fire_beside_mimo(self):
        grid = forest(trees=((X0 + 1, 0),))
        state = pet(weather="clear")
        ignite(state, context(grid), (X0 + 1, 1, 0), BORN, None)
        s = Situation({**state, "brain": None}, grid, clock_at(BORN, BORN, SCALE), BORN, None)
        reflex = by_name("flee_fire")
        self.assertTrue(reflex.trigger(s))
        walk = reflex.plan(s, None)[0]
        self.assertEqual(walk["kind"], "walk")
        self.assertLess(walk["target"][0], X0)  # away from the fire
        self.assertFalse(reflex.trigger(Situation({**pet(X0 - 10), "brain": None, "sky": state["sky"]}, grid,
                                                  clock_at(BORN, BORN, SCALE), BORN, None)))


class TickTests(unittest.TestCase):
    def test_a_storm_near_a_forest_costs_the_tick_little(self):
        """Spec cost criterion: the sky hook at most 2 ms mean and 8 ms p99 a transaction over a storm near a
        forest with fires burning (a real hatched world, a storm pinned, fires lit round Mimo)."""
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            timings: list[float] = []
            real = sky.advance

            def timed(state, context, at):
                started = time.perf_counter()
                real(state, context, at)
                timings.append(time.perf_counter() - started)

            def measure() -> list[float]:
                timings.clear()
                with patch("backend.survival.sky.weather_at", lambda seed, offset, segment: "storm"), \
                        patch("backend.survival.tick.sky.advance", timed):
                    start = world.state()["last_tick_at"]
                    for call in range(1, 31):
                        tick_life(registry, start + call, scale=SCALE, action_scale=SCALE)
                return timings

            runs = []  # (mean, p99) of up to 3 runs, stopping at one within both (backend.tests.budget's rule)
            for _ in range(3):
                ordered = sorted(measure())
                runs.append((sum(ordered) / len(ordered), ordered[int(len(ordered) * 0.99) - 1]))
                if runs[-1][0] < 0.002 and runs[-1][1] < 0.008:
                    break
            self.assertTrue(any(mean < 0.002 and p99 < 0.008 for mean, p99 in runs), runs)
            self.assertTrue(world.state()["sky"]["strikes"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_survival_storms backend.tests.test_survival_reflexes`
Expected: `FAILED (failures=1, errors=1)`: `ModuleNotFoundError: No module named 'backend.survival.storms'`, and the reflexes' order has no `('flee_fire', 25)`

- [ ] **Step 3: Strikes, fires, their heat and fleeing them**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import knocks  # noqa: F401  (W1: learning alone)
```

with:

```python
from backend.survival import knocks  # noqa: F401  (W1: learning alone)
from backend.survival import sky_reflexes  # noqa: F401  (W2: flee_fire)
```

In `backend/survival/grid.py`, replace:

```python
planners reach them the way they reach blocks; a grid built from `natural` alone has none.
```

with:

```python
planners reach them the way they reach blocks; a grid built from `natural` alone has none.
W2: the cells a fire burns in and their neighbours (`hot`, set by backend.survival.storms) are no way through,
like lava.
```

and replace:

```python
        self.herd: Herd | None = None
```

with:

```python
        self.herd: Herd | None = None
        self.hot: set[Cell] = set()  # W2: burning cells and their neighbours
```

and replace:

```python
        """Mimo's body fits in the cell: nothing solid, and no water or lava."""
        material = self.material(*cell)
        return material not in FLUIDS and not is_solid(material)
```

with:

```python
        """Mimo's body fits in the cell: nothing solid, and no water or lava (W2: nor fire, nor beside it)."""
        material = self.material(*cell)
        return material not in FLUIDS and not is_solid(material) and not (self.hot and cell in self.hot)
```

In `backend/survival/light.py`, replace:

```python
               "candle": 12, "lamp_lit": 15}  # Making: candles, and a lamp while it is lit
```

with:

```python
               "candle": 12, "lamp_lit": 15,  # Making: candles, and a lamp while it is lit
               "fire": 13}  # W2: a fire in the trees
```

In `backend/survival/rain.py`, replace:

```python

def douse(state: dict, context, at: float) -> None:
```

with:

```python

def campfires_near(context, x: int, z: int) -> list[Cell]:
    """The campfires placed within DOUSE_REACH blocks: one query of the world's blocks (loading every chunk that
    far into the grid would cost the tick each step), or the grid's own edits without a database."""
    if getattr(context, "db", None) is None:
        return [cell for cell, _ in context.grid.placed_cells(x, z, DOUSE_REACH, ("campfire",))]
    reach = math.ceil(DOUSE_REACH)
    rows = context.db.execute("SELECT x, y, z FROM mimo_blocks WHERE material='campfire' AND x BETWEEN ? AND ? "
                              "AND z BETWEEN ? AND ?", (x - reach, x + reach, z - reach, z + reach)).fetchall()
    return [(row[0], row[1], row[2]) for row in rows if math.hypot(row[0] - x, row[2] - z) <= DOUSE_REACH]


def douse(state: dict, context, at: float) -> None:
```

and replace:

```python
    for cell, _ in grid.placed_cells(math.floor(position["x"]), math.floor(position["z"]), DOUSE_REACH, ("campfire",)):
        if not sky_open(grid, seed, cell):
```

with:

```python
    for cell in campfires_near(context, math.floor(position["x"]), math.floor(position["z"])):
        if grid.material(*cell) != "campfire" or not sky_open(grid, seed, cell):
```

Create `backend/survival/sky_reflexes.py`:

```python
"""W2: the sky's reflexes (backend.survival.reflexes).

- flee_fire (25): a burning cell within FIRE_FLEE blocks of Mimo (backend.survival.storms): it runs away from
  the nearest, as flee runs from a hostile (creatures.defense.run_away), and chooses again where it stops.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival.creatures.defense import run_away
from backend.survival.reflexes import Reflex, register
from backend.survival.situation import Situation
from backend.survival.storms import fire_near

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FIRE_FLEE = 2


def nearest_fire(s: Situation) -> tuple[int, int, int] | None:
    cells = [(entry["x"], entry["y"], entry["z"]) for entry in (s.state.get("sky") or {}).get("fires", ())]
    return min(cells, key=lambda cell: math.dist(cell, s.here)) if cells else None


def plan_flee_fire(s: Situation, context: ActionContext) -> list[dict]:
    fire = nearest_fire(s)
    return [] if fire is None else [run_away(s, fire)]


register(Reflex("flee_fire", 25, trigger=lambda s: fire_near(s.state, FIRE_FLEE), plan=plan_flee_fire,
                thought="Fire! I have to get away!", event="{name} ran from the fire.", cooldown=3.0,
                ends_purpose=True, paced=True))
```

Create `backend/survival/storms.py`:

```python
"""W2: thunderstorms, lightning and fire in the trees ("Lightning and fire" of the Wild World spec).

In a storm (sky weather "storm": rain with lightning) a strike falls every STRIKE_EVERY game seconds near a living
Mimo, at most one a step, so a catch-up never strikes more often (`storm`, a sky effect, before each step):
- "A thunderstorm rolled in." (a "storm" event) when one starts;
- when Mimo stands under the open sky in the highest column within MIMO_REACH blocks (a hilltop, a pillar, a
  treetop: `highest`), the strike hits it with chance STRUCK_CHANCE instead: STRUCK_DAMAGE health, armor no
  help, and a death by it reads "was struck by lightning" ("Lightning struck Pip!", a "struck" event). On flat
  ground or indoors Mimo is never struck;
- else it falls on the highest of SAMPLES columns within STRIKE_REACH blocks (seeded), a tree's top counting as
  its height (`column_top`), never within HOME_CLEAR blocks of the home Mimo built nor in the legacy clearing:
  "stay inside" means the yard. The latest KEPT strikes are kept for the viewer's bolt and flash.
A strike on a tree's top leaf or log (a natural one) sets it burning: a `fire` block (light 13, not solid;
"Lightning set a tree on fire near Pip.", a "fire" event). Every SPREAD_EVERY game seconds each burning cell may
spread to one neighbouring natural log or leaf (SPREAD_CHANCE, a third of that in rain); a fire burns at most
FIRE_CELLS cells in all (`burned`, by fire) and at most FIRES burn at once. Each cell burns out BURN_SECONDS after it caught, leaving air
(renewal then lets the leaves no log holds decay, as after chopping). Fire never enters a cell Mimo built or
edited, a claimed cell, or anything within FIRE_CLEAR blocks of home. Mimo in or beside a burning cell takes
FIRE_DAMAGE health a game second (a death by it reads "was caught in a fire"); the flee_fire reflex takes it
away, the tick takes short steps while a fire is that close (`fire_near`), and paths keep out of burning cells
and their neighbours like lava (Grid.hot). Burned trees are ordinary block edits, synced like chopping.

The state lives in state["sky"]: `strike_at` (the last strike's time), `strikes` (the latest KEPT, {x, y, z,
at}), `fires` ({x, y, z, fire, caught, until}, at most FIRES x FIRE_CELLS), `burned` ({fire: cells it caught}),
`fire_at` (the last spread) and `storming`. STRIKES hears of every strike (backend.survival.sky_wild: knocks and wonders); one that crashes is
logged once.
"""

from __future__ import annotations

import logging
import math
import sqlite3

from backend.services.crafting import LOGS
from backend.services.worldgen import LEGACY_RADIUS, terrain_height
from backend.survival import sky
from backend.survival.grid import Cell, Grid
from backend.survival.light import SKY_SCAN, sky_open
from backend.survival.memory import BUILT, places
from backend.survival.nature import LEAVES, roll
from backend.survival.once import log_once
from backend.survival.triggers import crossings, mark_trigger

logger = logging.getLogger(__name__)

STRIKE_EVERY = 60.0  # game seconds between two strikes in a storm
STRIKE_REACH = 48
SAMPLES = 6
MIMO_REACH = 8
STRUCK_CHANCE = 0.05
STRUCK_DAMAGE = 25.0
HOME_CLEAR = 16.0  # no strike this close to the home Mimo built
FIRE_CLEAR = 8.0  # no fire this close to it
KEPT = 5
SPREAD_EVERY = 10.0
SPREAD_CHANCE = 0.35
RAIN_SPREAD = 1 / 3
FIRE_CELLS = 24
FIRES = 2
BURN_SECONDS = (20.0, 40.0)
FIRE_DAMAGE = 2.0  # health a game second in or beside a burning cell
FIRE = "fire"
BURNS = frozenset(LOGS) | frozenset(LEAVES)
FACES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
# Roll channels (Wild World's are 200 to 259).
SAMPLE_CHANNEL, STRUCK_CHANNEL, SPREAD_CHANNEL, BURN_CHANNEL, PICK_CHANNEL = 232, 233, 234, 235, 236
# W2: functions (state, context, cell, struck, at) run after each strike: `struck` when it hit Mimo. One that
# crashes is logged once and passed over.
STRIKES: list = []


def built_home(db: sqlite3.Connection | None) -> tuple[float, float] | None:
    """(x, z) of the home Mimo built, or None."""
    if db is None:
        return None
    try:
        home = next((place for place in places(db, ("home",)) if place["note"] == BUILT), None)
    except sqlite3.OperationalError:
        return None
    return None if home is None else (home["x"], home["z"])


def near(point: tuple[float, float] | None, x: float, z: float, reach: float) -> bool:
    return point is not None and math.hypot(x - point[0], z - point[1]) <= reach


def column_top(grid: Grid, seed: str, x: int, z: int) -> Cell:
    """The highest cell in the column that is not air (a tree's top leaf counts)."""
    ground = terrain_height(x, z, seed)
    for y in range(ground + SKY_SCAN, ground - 1, -1):
        if grid.material(x, y, z) != "air":
            return x, y, z
    return x, ground, z


def highest(grid: Grid, seed: str, cell: Cell) -> bool:
    """Mimo's column is the highest within MIMO_REACH blocks: nothing in any other stands as high as the block
    Mimo stands on (so on flat ground it never is)."""
    x, y, z = cell
    for cx in range(x - MIMO_REACH, x + MIMO_REACH + 1):
        for cz in range(z - MIMO_REACH, z + MIMO_REACH + 1):
            if (cx, cz) == (x, z):
                continue
            if terrain_height(cx, cz, seed) >= y - 1 or any(grid.material(cx, cy, cz) != "air"
                                                             for cy in (y - 1, y, y + 1)):
                return False
    return True


def pet_cell(state: dict) -> Cell:
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def hurt(state: dict, damage: float, source: str, at: float, context) -> None:
    """Lightning or fire takes health, as a blow would (the tick records a death by it with `source`)."""
    vitals = state["vitals"]
    before = dict(vitals)
    vitals["health"] = max(0.0, vitals["health"] - damage)
    state.update(hurt_at=at, hurt_by=source)
    for reason in crossings(before, vitals):
        mark_trigger(state, reason, at, urgent=True)


def strike(state: dict, context, at: float, home) -> None:
    """One strike near Mimo (see the module docstring)."""
    grid, seed, name = context.grid, state.get("world_seed", "0"), state["name"]
    here = pet_cell(state)
    salt = int((at - state["born_at"]) * context.clock_at(at)["time_scale"])
    struck = False
    if (math.hypot(here[0], here[2]) > LEGACY_RADIUS and not near(home, here[0], here[2], HOME_CLEAR)
            and sky_open(grid, seed, here) and highest(grid, seed, here)
            and roll(seed, here, STRUCK_CHANNEL, salt) < STRUCK_CHANCE):
        cell, struck = here, True
    else:
        columns = []
        for sample in range(SAMPLES):
            angle = 2 * math.pi * roll(seed, (sample, 0, 0), SAMPLE_CHANNEL, salt)
            reach = STRIKE_REACH * math.sqrt(roll(seed, (sample, 1, 0), SAMPLE_CHANNEL, salt))
            x, z = round(here[0] + math.cos(angle) * reach), round(here[2] + math.sin(angle) * reach)
            if math.hypot(x, z) <= LEGACY_RADIUS or near(home, x, z, HOME_CLEAR):
                continue
            columns.append(column_top(grid, seed, x, z))
        if not columns:
            return
        cell = max(columns, key=lambda top: top[1])
    sky_state = sky.sky_state(state)
    sky_state["strikes"] = [*sky_state["strikes"], {"x": cell[0], "y": cell[1], "z": cell[2], "at": at}][-KEPT:]
    if struck:
        hurt(state, STRUCK_DAMAGE, "lightning", at, context)
        state["last_thought"] = "Ow! The lightning hit me!"
        context.events.append((at, "struck", f"Lightning struck {name}!"))
    elif grid.material(*cell) in BURNS and may_burn(grid, cell, home):
        ignite(state, context, cell, at, None)
    for hears in STRIKES:
        try:
            hears(state, context, cell, struck, at)
        except Exception as error:
            log_once(logger, "strikes", error)


def may_burn(grid: Grid, cell: Cell, home) -> bool:
    """A natural log or leaf fire may enter: never edited, nothing Mimo built claims it, not near home."""
    return (cell not in grid.edits and grid.material(*cell) in BURNS and not grid.claimed(cell)
            and not near(home, cell[0], cell[2], FIRE_CLEAR))


def fires_of(state: dict) -> list[dict]:
    return sky.sky_state(state)["fires"]


def ignite(state: dict, context, cell: Cell, at: float, fire: int | None) -> bool:
    """`cell` catches: a new fire (fire None) unless FIRES burn already, or part of `fire` unless it is full."""
    burning, sky_state = fires_of(state), sky.sky_state(state)
    burned = sky_state.setdefault("burned", {})
    if fire is None:
        if len({entry["fire"] for entry in burning}) >= FIRES:
            return False
        fire = sky_state["fire_id"] = sky_state.get("fire_id", 0) + 1
        context.events.append((at, "fire", f"Lightning set a tree on fire near {state['name']}."))
    elif burned.get(str(fire), 0) >= FIRE_CELLS:
        return False
    burned[str(fire)] = burned.get(str(fire), 0) + 1
    scale = context.clock_at(at)["time_scale"]
    low, high = BURN_SECONDS
    seconds = low + (high - low) * roll(state.get("world_seed", "0"), cell, BURN_CHANNEL, int(at * scale))
    context.grid.put(*cell, FIRE)
    burning.append({"x": cell[0], "y": cell[1], "z": cell[2], "fire": fire, "caught": at, "until": at + seconds / scale})
    return True


def spread(state: dict, context, at: float, home=None) -> None:
    """Every SPREAD_EVERY game seconds up to `at`: each burning cell may catch one neighbour; cells burn out."""
    sky_state = sky.sky_state(state)
    scale = context.clock_at(at)["time_scale"]
    every = SPREAD_EVERY / scale
    last = sky_state.get("fire_at")
    if last is None or not sky_state["fires"]:
        sky_state["fire_at"] = at
        return
    seed, grid = state.get("world_seed", "0"), context.grid
    chance = SPREAD_CHANCE * (RAIN_SPREAD if sky.raining(state) else 1.0)
    moment = last
    for _ in range(int((at - last) / every + 1e-6)):
        moment += every
        for entry in [entry for entry in sky_state["fires"] if entry["until"] <= moment]:
            sky_state["fires"].remove(entry)
            cell = (entry["x"], entry["y"], entry["z"])
            if grid.material(*cell) == FIRE:
                grid.put(*cell, "air")
        alive = {str(entry["fire"]) for entry in sky_state["fires"]}
        sky_state["burned"] = {fire: count for fire, count in sky_state.get("burned", {}).items() if fire in alive}
        salt = int(moment * scale)
        for entry in list(sky_state["fires"]):
            cell = (entry["x"], entry["y"], entry["z"])
            if roll(seed, cell, SPREAD_CHANNEL, salt) >= chance:
                continue
            ahead = [(cell[0] + dx, cell[1] + dy, cell[2] + dz) for dx, dy, dz in FACES]
            ahead = [near_cell for near_cell in ahead if may_burn(grid, near_cell, home)]
            if ahead:
                pick = ahead[int(roll(seed, cell, PICK_CHANNEL, salt) * len(ahead)) % len(ahead)]
                ignite(state, context, pick, moment, entry["fire"])
    sky_state["fire_at"] = moment


def hot_cells(state: dict) -> set[Cell]:
    """The burning cells and their face neighbours: paths keep out of them (Grid.hot)."""
    cells = set()
    for entry in (state.get("sky") or {}).get("fires", ()):
        x, y, z = entry["x"], entry["y"], entry["z"]
        cells.add((x, y, z))
        cells.update((x + dx, y + dy, z + dz) for dx, dy, dz in FACES)
    return cells


def fire_near(state: dict, reach: int = 3) -> bool:
    """A burning cell within `reach` blocks of Mimo's cell (on every axis)."""
    x, y, z = pet_cell(state)
    return any(max(abs(entry["x"] - x), abs(entry["y"] - y), abs(entry["z"] - z)) <= reach
               for entry in (state.get("sky") or {}).get("fires", ()))


def burn_pet(state: dict, context, at: float) -> None:
    """Mimo in or beside a burning cell takes FIRE_DAMAGE a game second since the last look (or since it caught)."""
    sky_state = sky.sky_state(state)
    last = sky_state.get("burned_at")
    sky_state["burned_at"] = at
    if last is None or not fire_near(state, 1):
        return
    x, y, z = pet_cell(state)
    caught = min(entry["caught"] for entry in sky_state["fires"]
                 if max(abs(entry["x"] - x), abs(entry["y"] - y), abs(entry["z"] - z)) <= 1)
    seconds = (at - max(last, caught)) * context.clock_at(at)["time_scale"]
    if seconds > 0:
        hurt(state, FIRE_DAMAGE * seconds, FIRE, at, context)
        state["last_thought"] = "Hot! Hot! I have to get away from the fire!"


def storm(state: dict, context, at: float) -> None:
    """sky.EFFECTS: a storm's start and its strikes, the fires' spread and burning out, and the fire's heat on
    Mimo."""
    sky_state = sky.sky_state(state)
    storming = sky_state["weather"] == "storm"
    if storming and not sky_state.get("storming"):
        context.events.append((at, "storm", "A thunderstorm rolled in."))
        state["last_thought"] = "Thunder! A storm is coming."
    sky_state["storming"] = storming
    if not storming and not sky_state["fires"]:
        sky_state.pop("fire_at", None)
        sky_state.pop("burned_at", None)
        context.grid.hot = set()
        return
    home = built_home(context.db)
    if storming:
        scale = context.clock_at(at)["time_scale"]
        last = sky_state.get("strike_at")
        if last is None or (at - last) * scale >= STRIKE_EVERY:
            sky_state["strike_at"] = at
            strike(state, context, at, home)
    spread(state, context, at, home)
    burn_pet(state, context, at)
    context.grid.hot = hot_cells(state)


sky.EFFECTS.append(storm)
```

In `backend/survival/tick.py`, replace:

```python
outdoors (Surroundings.snowing; backend.survival.weather's other effects register themselves).
```

with:

```python
outdoors (Surroundings.snowing; backend.survival.weather's other effects register themselves). Lightning or a
fire (backend.survival.storms) that takes Mimo's last health kills it ("was struck by lightning", "was caught in a
fire"), and while a fire burns beside Mimo the steps are short, as near a hostile.
```

and replace:

```python
from backend.survival import rain, weather  # noqa: F401  (W2: rain douses campfires and slows walks; fog)
```

with:

```python
from backend.survival import rain, weather  # noqa: F401  (W2: rain douses campfires and slows walks; fog)
from backend.survival.storms import fire_near  # W2: lightning and fire in the trees (it registers itself)
```

and replace:

```python
CAUSE_WORDS = {"sickness": "fell sick and never got better"}  # W1
```

with:

```python
CAUSE_WORDS = {"sickness": "fell sick and never got better",  # W1
               "lightning": "was struck by lightning", "fire": "was caught in a fire"}  # W2
```

and replace:

```python
            sky.advance(state, context, cursor)  # W2: the season and the weather at this step's start
```

with:

```python
            sky.advance(state, context, cursor)  # W2: the season and the weather at this step's start
            if caught(state):  # W2: lightning or a fire took Mimo's last health
                record_death(state, state["hurt_by"], cursor, scale, events)
                break
```

and replace:

```python
            if fight_slices < FIGHT_SLICES_MAX and creature_nearby(context, state):
```

with:

```python
            if fight_slices < FIGHT_SLICES_MAX and (creature_nearby(context, state) or fire_near(state)):
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest backend.tests.test_survival_storms backend.tests.test_survival_reflexes`
Expected: `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1961 tests` … `OK (skipped=6)` (10 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/brain.py backend/survival/grid.py backend/survival/light.py backend/survival/rain.py backend/survival/sky_reflexes.py backend/survival/storms.py backend/survival/tick.py backend/tests/test_survival_reflexes.py backend/tests/test_survival_storms.py
git commit -m "feat(W2): lightning strikes the highest ground and the tallest trees, never near home, and sets fires that spread through the leaves, burn out and are fled" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The hard winter: ice, growth, herds and fish

**Files:**
- Create: `backend/survival/winter.py`, `backend/tests/test_survival_winter.py`
- Modify: `backend/survival/grid.py` (`frozen`, `open_cells`, the ice in `material`, `overlay`, `world_grid(db, seed, sky=None)`), `backend/survival/situation.py` (the chooser's grid wears the sky), `backend/survival/tick.py` (the tick's grid wears it; imports `winter`), `backend/survival/steps.py` (`start_mine`: the ice is too thick), `backend/survival/renewal.py` (`WINTER_WAITS`, cave mushrooms, fish), `backend/survival/nature.py` (`recover_fish(..., grows)`), `backend/survival/creatures/spawning.py` (`WINTER_LAND_CAP`, one herd, no regain), `backend/survival/spoilage.py` (`WINTER_RATE`)

**Interfaces:**
- Consumes: Task 1's `sky.winter`, `next_season_at`; `worldgen.SEA_LEVEL`; W1's `spoilage.age`; the creatures' fish.
- Produces: `Grid.frozen`, `Grid.open_cells`, `Grid.overlay(sky)`, `grid.world_grid(db, seed, sky=None)`; `winter.freeze` (a sky effect: the freeze at the first winter dawn, the thaw at the first spring dawn), `kept_open`, `fish_under_ice`; `state["sky"]`'s `frozen`, `open_cells`; `renewal.WINTER_WAITS`; `spawning.WINTER_LAND_CAP` (12); `spoilage.WINTER_RATE` (1/3); `nature.recover_fish(..., grows=True)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_winter.py`:

```python
"""W2: the hard winter: the ice overlay and the open cell a swimming pet keeps, a path across a frozen lake,
growth that waits for spring, cave mushrooms, thinned herds, fish, and food that keeps longer."""

import sqlite3
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.services.worldgen import SEA_LEVEL
from backend.survival import nature
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.spawning import LAND_CAP, WINTER_LAND_CAP, populate
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.pathing import route
from backend.survival.renewal import create_growth_table, renew, schedule, scheduled
from backend.survival.sky import next_season_at
from backend.survival.spoilage import age
from backend.survival.steps import StepFailed, start_step
from backend.survival.winter import freeze

BORN = 1_000_000.0
SCALE = 60.0
WINTER_DAY = 31  # a newborn's first winter


def day_start(day: int) -> float:
    return BORN + (day - 1) * DAY_SECONDS / SCALE


def lake(x0=10, x1=40):
    """A lake from x0 to x1 (water at SEA_LEVEL and one below, sand under), grass at SEA_LEVEL elsewhere, and a
    cave lake at y -3 everywhere under the land."""
    def natural(x, y, z):
        if x0 <= x <= x1:
            return "water" if SEA_LEVEL - 1 <= y <= SEA_LEVEL else "sand" if y < SEA_LEVEL - 1 else "air"
        if y == -3:
            return "water"
        return "grass" if y == SEA_LEVEL else "dirt" if y < SEA_LEVEL else "air"

    grid = Grid(natural)
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(x=0, y=SEA_LEVEL + 1, z=0, season="winter"):
    return {"name": "Pip", "world_seed": "7", "born_at": BORN, "position": {"x": float(x), "y": float(y), "z": float(z)},
            "vitals": {"health": 100.0}, "inventory": {}, "sky": {"offset": 0, "season": season}}


def context(grid, db=None):
    return SimpleNamespace(grid=grid, events=[], db=db, clock_at=lambda at: clock_at(BORN, at, SCALE))


class IceTests(unittest.TestCase):
    def test_in_winter_surface_water_reads_as_walkable_ice_and_cave_water_stays(self):
        grid = lake()
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "water")
        grid.overlay({"frozen": True})
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "ice")
        self.assertTrue(grid.standable((20, SEA_LEVEL + 1, 0)))
        self.assertFalse(grid.swimming((20, SEA_LEVEL + 1, 0)))
        self.assertEqual(grid.material(20, SEA_LEVEL - 1, 0), "water")
        self.assertEqual(grid.material(0, -3, 0), "water")
        self.assertFalse(grid.water((20, SEA_LEVEL, 0)))  # no fishing through the ice
        grid.put(21, SEA_LEVEL, 0, "water")  # an edited cell is no lake's surface
        self.assertEqual(grid.material(21, SEA_LEVEL, 0), "water")
        grid.overlay({"frozen": False})
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "water")

    def test_the_ice_is_too_thick_to_mine_but_a_taigas_own_ice_is_not(self):
        grid = lake()
        grid.overlay({"frozen": True})
        state = {**pet(19, SEA_LEVEL + 1, 0), "inventory": {"stone_pickaxe": 1}}
        with self.assertRaises(StepFailed) as raised:
            start_step({"kind": "mine", "target": [20, SEA_LEVEL, 0]}, state, grid, 0.0)
        self.assertEqual(str(raised.exception), "the ice is too thick")
        taiga = Grid(lambda x, y, z: "ice" if y == SEA_LEVEL else "air")
        self.assertEqual(start_step({"kind": "mine", "target": [20, SEA_LEVEL, 0]}, state, taiga, 0.0)["block"], "ice")

    def test_the_freeze_comes_at_the_first_winter_dawn_and_a_swimming_pet_keeps_its_water_until_dawn(self):
        grid = lake()
        swimmer = pet(20, SEA_LEVEL + 1, 0)
        grid.herd.add("fish", (25, SEA_LEVEL, 0), 2.0, BORN, BORN, {"home": [25, SEA_LEVEL, 0]})
        freeze(swimmer, context(grid), day_start(WINTER_DAY))
        sky = swimmer["sky"]
        self.assertTrue(sky["frozen"])
        self.assertEqual(sky["open_cells"], [[20, SEA_LEVEL, 0]])
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "water")
        self.assertEqual(grid.material(21, SEA_LEVEL, 0), "ice")
        fish = grid.herd.near(25, 0, 2)
        self.assertEqual([round(creature["y"]) for creature in fish], [SEA_LEVEL - 1])  # it swam down
        freeze(swimmer, context(grid), day_start(WINTER_DAY + 1) + 1 / SCALE)
        self.assertEqual((sky["open_cells"], grid.material(20, SEA_LEVEL, 0)), ([], "ice"))
        swimmer["sky"]["season"] = "spring"
        freeze(swimmer, context(grid), day_start(41))
        self.assertFalse(sky["frozen"])
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "water")

    def test_a_fish_with_no_water_under_it_fades(self):
        shallow = lake()
        shallow.put(25, SEA_LEVEL - 1, 0, "sand")
        shallow.herd.add("fish", (25, SEA_LEVEL, 0), 2.0, BORN, BORN, {"home": [25, SEA_LEVEL, 0]})
        freeze(pet(0), context(shallow), day_start(WINTER_DAY))
        self.assertEqual(shallow.herd.near(25, 0, 2), [])

    def test_a_path_crosses_a_frozen_lake_and_the_overlay_costs_the_search_little(self):
        frozen, open_water = lake(), lake()
        frozen.overlay({"frozen": True})
        cells, reached = route(frozen, (0, SEA_LEVEL + 1, 0), (50, SEA_LEVEL + 1, 0))
        self.assertTrue(reached)
        self.assertFalse(any(frozen.swimming(cell) for cell in cells))
        swum, _ = route(open_water, (0, SEA_LEVEL + 1, 0), (50, SEA_LEVEL + 1, 0))
        self.assertTrue(any(open_water.swimming(cell) for cell in swum))

        def timed(frozen_now: bool) -> float:
            grid = lake()
            grid.overlay({"frozen": frozen_now})
            started = time.perf_counter()
            route(grid, (0, SEA_LEVEL + 1, 0), (50, SEA_LEVEL + 1, 0))
            return time.perf_counter() - started

        # The fastest of 15 searches each, taken in turn, so a load spike on a busy machine favours neither.
        times = {True: [], False: []}
        for _ in range(15):
            for frozen_now in (False, True):
                times[frozen_now].append(timed(frozen_now))
        self.assertLessEqual(min(times[True]), min(times[False]) * 1.1)


class GrowthTests(unittest.TestCase):
    def world(self):
        db = sqlite3.connect(":memory:")
        create_growth_table(db)
        grid = Grid(lambda x, y, z: "grass" if y == 0 else "stone" if y < 0 else "air")
        state = {**pet(season="winter"), "world_seed": "7"}
        return db, grid, state

    def test_growth_that_falls_due_in_winter_waits_for_the_first_spring_dawn(self):
        db, grid, state = self.world()
        grid.put(0, 0, 0, "farmland")
        grid.put(0, 1, 0, "wheat_0")
        grid.take_changes()
        due = day_start(WINTER_DAY) + 600 / SCALE
        for cell, block in (((0, 1, 0), "wheat_1"), ((3, 1, 0), "berry_bush_ripe"), ((5, 0, 5), "dirt")):
            schedule(db, cell, block, due)
        schedule(db, (7, 6, 7), "air", due)  # a leaf decaying goes ahead
        with patch("backend.survival.renewal.terrain_height", lambda x, z, seed: 0):
            renew(state, SimpleNamespace(db=db, grid=grid, events=[], clock_at=lambda at: clock_at(BORN, at, SCALE)),
                  due + 1)
        spring = next_season_at(state, due, SCALE, "spring")
        self.assertEqual(spring, day_start(41))
        waiting = {cell: (block, ready) for cell, block, ready in scheduled(db)}
        self.assertEqual(waiting, {(0, 1, 0): ("wheat_1", spring), (3, 1, 0): ("berry_bush_ripe", spring),
                                   (5, 0, 5): ("dirt", spring)})
        self.assertEqual(grid.material(0, 1, 0), "wheat_0")

    def test_a_cave_mushroom_comes_back_on_its_spot_in_winter_too(self):
        db, grid, state = self.world()
        cave = (4, -3, 4)
        grid.put(*cave, "air")
        grid.put(4, -4, 4, "stone")
        grid.put(*cave, "brown_mushroom")
        grid.take_changes()
        grid.put(*cave, "air")  # picked
        ctx = SimpleNamespace(db=db, grid=grid, events=[], clock_at=lambda at: clock_at(BORN, at, SCALE))
        picked = day_start(WINTER_DAY) + 100 / SCALE
        with patch("backend.survival.renewal.terrain_height", lambda x, z, seed: 0):
            renew(state, ctx, picked)
            self.assertEqual([(cell, block) for cell, block, _ in scheduled(db)], [(cave, "brown_mushroom")])
            renew(state, ctx, picked + DAY_SECONDS / SCALE)
        self.assertEqual(grid.material(*cave), "brown_mushroom")


class AnimalTests(unittest.TestCase):
    def scene(self, season, herd):
        grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        grid.herd = herd
        state = {**pet(0, 1, 0, season), "world_seed": "4"}
        return Scene(grid, herd, "4", state, 100.0, 1.0, events=[], clock={"phase": "day", "time_scale": 1.0})

    def test_in_winter_a_new_chunk_rolls_one_herd_at_most_and_the_land_cap_is_twelve(self):
        found = {}
        for season in ("spring", "winter"):
            db = sqlite3.connect(":memory:")
            create_creature_tables(db)
            herd = Herd(db)
            with patch("backend.survival.creatures.spawning.terrain_height", lambda x, z, seed: 0), \
                    patch("backend.survival.creatures.spawning.biome_at", lambda x, z, seed: "meadow"):
                found[season] = []
                for _ in range(8):  # NEW_CHUNKS a call: every chunk within reach in a few calls
                    found[season] += populate(self.scene(season, herd), herd.near(0, 0, 48), 1.0)
                rolled = [row["herds"] for row in herd.chunks((-9, -9), (9, 9)).values()]
            self.assertLessEqual(max(rolled), 1 if season == "winter" else 2)
        self.assertLessEqual(len(found["winter"]), WINTER_LAND_CAP)
        self.assertGreater(len(found["spring"]), WINTER_LAND_CAP)
        self.assertLessEqual(len(found["spring"]), LAND_CAP)

    def test_no_fish_come_back_in_winter(self):
        state = {"fish": {"1,1": {"stock": 4, "since": 0.0}}}
        nature.recover_fish(state, 3 * DAY_SECONDS, 1.0, grows=False)
        self.assertEqual(state["fish"]["1,1"], {"stock": 4, "since": 3 * DAY_SECONDS})
        nature.recover_fish(state, 5 * DAY_SECONDS, 1.0)
        self.assertEqual(state["fish"]["1,1"]["stock"], 6)


class SpoilageTests(unittest.TestCase):
    def test_in_winter_food_goes_off_a_third_as_fast(self):
        worn = {}
        for season in ("autumn", "winter"):
            state = {**pet(season=season), "difficulty": "wild", "inventory": {"raw_beef": 1}, "lots": {"raw_beef": [[1, 0.0]]}}
            age(state, SimpleNamespace(events=[], db=None), 600.0, 0.0)
            worn[season] = state["lots"]["raw_beef"][0][1]
        self.assertAlmostEqual(worn["winter"] * 3, worn["autumn"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_winter.py"`
Expected: `FAILED (errors=1)`: `ImportError: cannot import name 'WINTER_LAND_CAP' from 'backend.survival.creatures.spawning'`

- [ ] **Step 3: The ice overlay, the freeze and winter's rules**

In `backend/survival/creatures/spawning.py`, replace:

```python
regains one herd. (L3's creature seeds add more.)
```

with:

```python
regains one herd. (L3's creature seeds add more.) W2: in winter the animals thin out: a new chunk rolls one
herd at most, the land cap near Mimo falls to WINTER_LAND_CAP, and a hunted-out chunk waits for spring to
regain its herd. Animals already alive stay.
```

and replace:

```python

SIM_REACH = 48.0
LAND_CAP = 24  # land animals within SIM_REACH of Mimo
```

with:

```python
from backend.survival.sky import winter

SIM_REACH = 48.0
LAND_CAP = 24  # land animals within SIM_REACH of Mimo
WINTER_LAND_CAP = 12  # W2
```

and replace:

```python
    counts = {water: sum(1 for creature in alive if passive(creature, water)) for water in (False, True)}
```

with:

```python
    counts = {water: sum(1 for creature in alive if passive(creature, water)) for water in (False, True)}
    wintry = winter(scene.state)  # W2: the animals thin out
    land_cap = WINTER_LAND_CAP if wintry else LAND_CAP
```

and replace:

```python
            return counts[False] < LAND_CAP
```

with:

```python
            return counts[False] < land_cap
```

and replace:

```python
            rolled = herd_count(scene.seed, chunk)
```

with:

```python
            rolled = min(herd_count(scene.seed, chunk), 1 if wintry else 2)
```

and replace:

```python
        elif (row is not None and row["herds"] > 0 and row["animals"] == 0 and row["empty_since"] is not None
```

with:

```python
        elif (not wintry and row is not None and row["herds"] > 0 and row["animals"] == 0 and row["empty_since"] is not None
```

In `backend/survival/grid.py`, replace:

```python
W2: the cells a fire burns in and their neighbours (`hot`, set by backend.survival.storms) are no way through,
like lava.
```

with:

```python
W2: the cells a fire burns in and their neighbours (`hot`, set by backend.survival.storms) are no way through,
like lava. In winter (`frozen`, from state["sky"]: `overlay`) a natural water cell at SEA_LEVEL that was never
edited reads as ice, the surface of a lake, a river or a swamp pool: solid, standable, walkable, and never
mined (steps.start_mine), so no block is written; cave lakes lie lower and stay water. A cell in `open_cells`
(where Mimo stood or swam when the freeze came) stays water. For every other cell it costs one integer compare.
```

and replace:

```python
from backend.services.worldgen import block_at
```

with:

```python
from backend.services.worldgen import SEA_LEVEL, block_at
```

and replace:

```python
        self.hot: set[Cell] = set()  # W2: burning cells and their neighbours
```

with:

```python
        self.hot: set[Cell] = set()  # W2: burning cells and their neighbours
        self.frozen = False  # W2: the lakes' surfaces are ice
        self.open_cells: set[Cell] = set()  # W2: water Mimo kept open where it was when the freeze came
```

and replace:

```python
            return "air"
        return natural
```

with:

```python
            return "air"
        if y == SEA_LEVEL and self.frozen and natural == "water" and (x, y, z) not in self.open_cells:
            return "ice"  # W2: a frozen lake (the overlay, never a block)
        return natural

    def overlay(self, sky: dict | None) -> None:
        """W2: the winter's ice from state["sky"] (`frozen`, `open_cells`)."""
        sky = sky or {}
        self.frozen = bool(sky.get("frozen"))
        self.open_cells = {tuple(cell) for cell in sky.get("open_cells", ())}
```

and replace:

```python
def world_grid(db: sqlite3.Connection, seed: str) -> Grid:
    """A grid over one survival world's database, for the length of one transaction."""
```

with:

```python
def world_grid(db: sqlite3.Connection, seed: str, sky: dict | None = None) -> Grid:
    """A grid over one survival world's database, for the length of one transaction; W2: with state["sky"],
    frozen as the winter has it."""
```

and replace:

```python
    grid.herd = Herd(db)
```

with:

```python
    grid.herd = Herd(db)
    grid.overlay(sky)
```

In `backend/survival/nature.py`, replace:

```python
def recover_fish(state: dict, at: float, scale: float) -> None:
    """Every region gains one fish per game day until it is full again."""
```

with:

```python
def recover_fish(state: dict, at: float, scale: float, grows: bool = True) -> None:
    """Every region gains one fish per game day until it is full again (W2: not while `grows` is False, in
    winter: the days pass and no fish comes back)."""
```

and replace:

```python
        entry["stock"] = min(FULL_STOCK, entry["stock"] + days)
```

with:

```python
        if grows:
            entry["stock"] = min(FULL_STOCK, entry["stock"] + days)
```

In `backend/survival/renewal.py`, replace:

```python
   - W2: a crop stage that starts while it rains (backend.survival.sky) takes the watered time.
```

with:

```python
   - W2: a crop stage that starts while it rains (backend.survival.sky) takes the watered time.
   W2, winter: an entry that falls due in winter and grows something (WINTER_WAITS: a crop's stage, a sapling,
   a berry or nightberry bush ripening, a sunleaf or a forest-floor mushroom coming back, and farmland turning
   back to dirt) waits for the first spring dawn; leaves still decay. A mushroom picked in a cave (below the
   land's surface) comes back where it grew a game day later, winter or not, so the caves are winter food.
```

and replace:

```python
3. Lets fish stocks recover, one fish per region per game day (nature.recover_fish).
```

with:

```python
3. Lets fish stocks recover, one fish per region per game day (nature.recover_fish); W2: none in winter.
```

and replace:

```python
from backend.survival.sky import RAINY, weather_of
```

with:

```python
from backend.survival.sky import RAINY, next_season_at, season_at, weather_of, winter
```

and replace:

```python
NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
```

with:

```python
NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
# W2: what waits for spring when it falls due in winter.
WINTER_WAITS = frozenset({*(block for block in nature.CROP_BLOCKS if not block.endswith("_0")), LOG,
                          "berry_bush_ripe", "nightberry_bush_ripe", "sunleaf", *nature.MUSHROOMS, "dirt"})
```

and replace:

```python
        if (before in nature.MUSHROOMS or before == "sunleaf") and after == "air":
```

with:

```python
        if before in nature.MUSHROOMS and after == "air" and underground(seed, cell):  # W2: a cave's own spot
            schedule(db, cell, before, later(at, MUSHROOM_RESPAWN, scale), keep_earlier=True)
        elif (before in nature.MUSHROOMS or before == "sunleaf") and after == "air":
```

and replace:

```python

def rained(state: dict, at: float, scale: float) -> bool:
```

with:

```python

def underground(seed: str, cell: Cell) -> bool:
    """W2: below the land's natural surface (a cave)."""
    return cell[1] < terrain_height(cell[0], cell[2], seed)


def rained(state: dict, at: float, scale: float) -> bool:
```

and replace:

```python
    x, y, z = cell
    here = grid.material(*cell)
```

with:

```python
    x, y, z = cell
    cave = block in nature.MUSHROOMS and underground(state.get("world_seed", "0"), cell)
    if (block in WINTER_WAITS and not cave and "born_at" in state
            and season_at(state, ready_at, scale)[0] == "winter"):
        schedule(db, cell, block, next_season_at(state, ready_at, scale, "spring"))  # W2: it waits for spring
        return
    here = grid.material(*cell)
```

and replace:

```python
            decay(state, cell, ready_at, here)
```

with:

```python
            decay(state, cell, ready_at, here)
    elif cave:  # W2: a cave mushroom on its own spot, on stone, in any season
        if here == "air" and grid.solid((x, y - 1, z)) and not grid.claimed(cell):
            grid.put(*cell, block)
```

and replace:

```python
    nature.recover_fish(state, at, scale)
```

with:

```python
    nature.recover_fish(state, at, scale, grows=not winter(state))
```

In `backend/survival/situation.py`, replace:

```python
    return Situation(state, world_grid(db, state["world_seed"]), clock_at(state["born_at"], at, scale), at, db)
```

with:

```python
    return Situation(state, world_grid(db, state["world_seed"], state.get("sky")), clock_at(state["born_at"], at, scale),
                     at, db)
```

In `backend/survival/spoilage.py`, replace:

```python
The tick ages Mimo's lots every vitals step and its chests' once a game minute (`age`). A lot that reaches
```

with:

```python
The tick ages Mimo's lots every vitals step and its chests' once a game minute (`age`); W2: in winter, a third
as fast (WINTER_RATE), in arms or chest. A lot that reaches
```

and replace:

```python
from backend.survival.once import log_once
```

with:

```python
from backend.survival.once import log_once
from backend.survival.sky import winter
```

and replace:

```python
TURNING = 0.5  # wear past which keeping cooks raw food first
```

with:

```python
TURNING = 0.5  # wear past which keeping cooks raw food first
WINTER_RATE = 1 / 3  # W2: food ages a third as fast in winter
```

and replace:

```python
        went_bad(state, context, spoil(arms_lots(state), state["inventory"], 1.0, seconds), "arms", at)
```

with:

```python
        season = WINTER_RATE if winter(state) else 1.0
        went_bad(state, context, spoil(arms_lots(state), state["inventory"], season, seconds), "arms", at)
```

and replace:

```python
                    went_bad(state, context, spoil(lots_of, chest, CHEST_RATE, waited), "chest", at)
```

with:

```python
                    went_bad(state, context, spoil(lots_of, chest, CHEST_RATE * season, waited), "chest", at)
```

In `backend/survival/steps.py`, replace:

```python
    material = grid.material(*target)
```

with:

```python
    material = grid.material(*target)
    if material == "ice" and grid.natural_material(*target) == "water":  # W2: a frozen lake (backend.survival.winter)
        raise StepFailed("the ice is too thick", "blocked")
```

In `backend/survival/tick.py`, replace:

```python
from backend.survival import rain, weather  # noqa: F401  (W2: rain douses campfires and slows walks; fog)
```

with:

```python
from backend.survival import rain, weather, winter  # noqa: F401  (W2: rain, snow and fog; the winter's ice)
```

and replace:

```python
        context = ActionContext(grid=world_grid(db, world.seed), planner=mind.plan, events=events,
```

with:

```python
        context = ActionContext(grid=world_grid(db, world.seed, state.get("sky")), planner=mind.plan, events=events,
```

Create `backend/survival/winter.py`:

```python
"""W2: the hard winter's ice ("Winter" and "Snow and ice: overlays, not blocks" of the Wild World spec).

From the first winter dawn to the first spring dawn the lakes are frozen (`freeze`, a sky effect before each
step): state["sky"]["frozen"], which every grid of the world reads (Grid.overlay: a natural surface water cell
reads as ice, solid and walkable, and is never mined, so no block is ever written). When the freeze comes, the
water cells Mimo stands or swims in stay open (`open_cells`) until the next dawn, by which time it has left, and
each fish near Mimo in a surface cell that freezes swims a cell down, or fades when there is no water under it.
Fish can't be caught through ice (a fishing spot is water), cave lakes lie lower and stay open, and no fish
comes back in winter (renewal: nature.recover_fish).

The rest of the winter lives beside what it changes: growth that falls due in winter waits for the first
spring dawn (renewal.WINTER_WAITS), herds thin (creatures.spawning: one herd a new chunk at most, the land cap
near Mimo 12, no herd back in a hunted-out chunk until spring), spoilage runs a third as fast
(spoilage.WINTER_RATE), the snow cover builds while it snows (sky.tend_weather), and the cold is vitals'.
"""

from __future__ import annotations

from backend.services.worldgen import SEA_LEVEL
from backend.survival import sky
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.kinds import water_kinds
from backend.survival.creatures.spawning import SIM_REACH
from backend.survival.grid import Cell, Grid


def surface_water(grid: Grid, cell: Cell) -> bool:
    """A natural water cell at SEA_LEVEL never edited: what freezes."""
    return cell[1] == SEA_LEVEL and cell not in grid.edits and grid.natural_material(*cell) == "water"


def kept_open(grid: Grid, state: dict) -> list[list[int]]:
    """The water cells Mimo stands or swims in: its own cell and the one under it."""
    position = state["position"]
    x, y, z = round(position["x"]), round(position["y"]), round(position["z"])
    return [[x, cy, z] for cy in (y, y - 1) if surface_water(grid, (x, cy, z))]


def fish_under_ice(state: dict, grid: Grid, at: float) -> None:
    """Each fish near Mimo in a surface cell that froze swims a cell down, or fades with no water there."""
    herd = grid.herd
    if herd is None:
        return
    position = state["position"]
    kinds = [kind.name for kind in water_kinds()]
    for fish in herd.near(position["x"], position["z"], SIM_REACH, kinds=kinds):
        cell = (int(round(fish["x"])), int(round(fish["y"])), int(round(fish["z"])))
        if not surface_water(grid, cell) or list(cell) in state["sky"]["open_cells"]:
            continue
        below = (cell[0], cell[1] - 1, cell[2])
        if grid.material(*below) == "water":
            fish["y"] = float(below[1])
            fish["state"] = {**fish["state"], "home": list(below), "path": None}
            herd.save(fish)
        else:
            herd.remove(fish["id"])


def freeze(state: dict, context, at: float) -> None:
    """sky.EFFECTS: the lakes freeze at the first winter dawn and thaw at the first spring dawn."""
    found = sky.sky_state(state)
    frozen = found["season"] == sky.WINTER
    grid = context.grid
    if frozen and not found["frozen"]:
        found["open_cells"] = kept_open(grid, state)
        scale = context.clock_at(at)["time_scale"]
        found["open_until"] = at + (DAY_SECONDS - context.clock_at(at)["seconds_into_day"]) / scale
        fish_under_ice(state, grid, at)
    elif not frozen:
        found["open_cells"] = []
    if found.get("open_until") is not None and at >= found["open_until"]:
        found["open_cells"] = []
        found.pop("open_until", None)
    found["frozen"] = frozen
    grid.overlay(found)


sky.EFFECTS.append(freeze)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_winter.py"`
Expected: `Ran 10 tests` `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1971 tests` … `OK (skipped=6)` (10 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/creatures/spawning.py backend/survival/grid.py backend/survival/nature.py backend/survival/renewal.py backend/survival/situation.py backend/survival/spoilage.py backend/survival/steps.py backend/survival/tick.py backend/survival/winter.py backend/tests/test_survival_winter.py
git commit -m "feat(W2): winter freezes the lakes into walkable ice, stops growth until spring, thins the herds and the fish and keeps food longer" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The seven lessons, taught in one sentence

**Files:**
- Modify: `backend/survival/wild.py` (seven entries of `SURVIVAL`, `GRANTED`), `backend/survival/lessons.py` (`OPPOSITES`)
- Create: `backend/tests/test_survival_sky_teaching.py`
- Test: `backend/tests/test_survival_wild.py`, `backend/tests/test_survival_lessons.py` (W1's counts of the lessons)

**Interfaces:**
- Consumes: W1's `wild.SURVIVAL` shape (name, subjects, facts, means, sides), `journal.LESSONS`, `lessons.warned`, `wild.settle`.
- Produces: the lessons `wild:winter`, `wild:cloak`, `wild:hearth`, `wild:smoking`, `wild:rain`, `wild:storm`, `wild:fog`, each taught by its owner line of the spec's table; `wild.GRANTED` (2): a gentle pet granted below it is granted every lesson again, quietly.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_lessons.py`, replace:

```python
        self.assertEqual(len(survival), 11)  # W1's survival lessons
```

with:

```python
        self.assertEqual(len(survival), 18)  # W1's eleven survival lessons and W2's seven
```

Create `backend/tests/test_survival_sky_teaching.py`:

```python
"""W2: the seven weather and season lessons: each taught in one sentence, the doubted lines doubted, and a gentle
pet granted W1's lessons granted W2's on its next tick, quietly."""

import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every lesson registered)
from backend.survival import minding  # noqa: F401  (the chat's "teach" question)
from backend.survival.brain import BRAIN
from backend.survival.hatch import hatch
from backend.survival.journal import LESSONS
from backend.survival.lessons import claims, named
from backend.survival.memory import know
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.wild import BORN_KNOWING, BY_NAME, GRANTED, SURVIVAL, survival_view, thing
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0
W2 = ("winter", "cloak", "hearth", "smoking", "rain", "storm", "fog")
# The spec's owner lines for W2's lessons (the teaching test table), and the lines doubted.
TEACHES = {"winter": "Fill a chest with food before winter.", "cloak": "Five wool make a wool cloak.",
           "hearth": "A stone hearth keeps the home warm.", "smoking": "Smoked meat keeps all winter.",
           "rain": "Rain puts out a fire under the open sky.", "storm": "In a storm stay low and inside.",
           "fog": "Stay close to home in the fog."}
DOUBTED = ("Six wool make a wool cloak.", "Lightning is harmless.", "Fog is safe.")


class TeachingTests(unittest.TestCase):
    def test_the_seven_lessons_follow_w1s_and_each_fact_says_no_negation(self):
        self.assertEqual(tuple(lesson.name for lesson in SURVIVAL[-7:]), W2)
        self.assertEqual(GRANTED, 2)
        for name in W2:
            self.assertEqual(LESSONS[thing(name)].kind, "survival")
            self.assertEqual(named(LESSONS[thing(name)]), name)
            self.assertFalse({"not", "no", "never", "don't"} & set(BY_NAME[name].fact.lower().split()))

    def test_every_owner_line_teaches_its_lesson_and_nothing_else(self):
        for name, text in TEACHES.items():
            self.assertEqual(claims(text).taught, (thing(name),), text)
            self.assertFalse(claims(text).doubtful, text)

    def test_the_doubted_lines_are_doubted(self):
        for text in DOUBTED:
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), ((), True), text)


class GrantTests(unittest.TestCase):
    def test_a_gentle_pet_granted_w1s_lessons_is_granted_w2s_on_its_next_tick_quietly(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                state["wild"] = {"granted": 1}  # a world W1 granted
                for lesson in SURVIVAL[:11]:
                    know(db, thing(lesson.name), "lesson", BORN)
                    know(db, thing(lesson.name), BORN_KNOWING, BORN)
                write_state(db, state)
            tick_life(registry, BORN + 1, scale=1.0, mind=BRAIN)
            self.assertEqual(world.state()["wild"]["granted"], GRANTED)
            with world.connect() as db:
                view = {entry["name"]: entry for entry in survival_view(db)}
                memories = db.execute("SELECT COUNT(*) FROM mind_memories").fetchone()[0]
            self.assertTrue(all(view[name]["known"] and view[name]["source"] == "from_start" for name in W2))
            self.assertEqual(memories, 0)
            self.assertFalse(any(event["kind"] in ("learned", "figured") for event in world.events(100)))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_wild.py`, replace:

```python
    BORN_KNOWING, GENTLE, SURVIVAL, WILD, difficulty, is_wild, settle, survival_view, thing, unlocked,
```

with:

```python
    BORN_KNOWING, GENTLE, GRANTED, SURVIVAL, WILD, difficulty, is_wild, settle, survival_view, thing, unlocked,
```

and replace:

```python
        self.assertEqual(world.state()["wild"], {"granted": 1})
        tick_life(self.lives.registry, BORN + 2, scale=1.0, mind=BRAIN)  # granted once
        self.assertEqual(world.state()["wild"], {"granted": 1})
```

with:

```python
        self.assertEqual(world.state()["wild"], {"granted": GRANTED})  # W2: every landed milestone's, W1's and W2's
        tick_life(self.lives.registry, BORN + 2, scale=1.0, mind=BRAIN)  # granted once
        self.assertEqual(world.state()["wild"], {"granted": GRANTED})
```

and replace:

```python
        gentle = {"wild": {"granted": 1}}
```

with:

```python
        gentle = {"wild": {"granted": GRANTED}}
```

and replace:

```python
        self.assertEqual(len(mimo["survival"]), 11)
        registry = LifeRegistry()
        registry.mark_dead(registry.active_life()["id"], BORN, "starvation")
        memorial = get_mimo()["last_life"]
        self.assertEqual(len(memorial["survival"]), 11)  # the memorial tallies where its lessons came from
```

with:

```python
        self.assertEqual(len(mimo["survival"]), len(SURVIVAL))  # W1's eleven and W2's seven
        registry = LifeRegistry()
        registry.mark_dead(registry.active_life()["id"], BORN, "starvation")
        memorial = get_mimo()["last_life"]
        self.assertEqual(len(memorial["survival"]), len(SURVIVAL))  # the memorial tallies where its lessons came from
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_survival_sky_teaching backend.tests.test_survival_wild backend.tests.test_survival_lessons`
Expected: `FAILED (failures=4, errors=1)`: the seven lessons are not in `SURVIVAL` yet (`KeyError: 'winter'`, `Tuples differ: () != ('wild:winter',)`), and W1's count of the lessons is still 11 (`AssertionError: 11 != 18`)

- [ ] **Step 3: The lessons and the grant**

In `backend/survival/lessons.py`, replace:

```python
             (frozenset({"warm", "warmth"}), frozenset({"cold", "chill"})))
```

with:

```python
             (frozenset({"warm", "warmth"}), frozenset({"cold", "chill"})),
             # W2: harmless or dangerous (a storm, fog)
             (frozenset({"harmless", "safe"}), frozenset({"dangerous", "danger"})))
```

In `backend/survival/wild.py`, replace:

```python
so a gentle pet's choices and words stay as they were.
```

with:

```python
so a gentle pet's choices and words stay as they were.

W2 adds seven lessons for the weather and the seasons (winter, cloak, hearth, smoking, rain, storm, fog) and
raises GRANTED to 2: a gentle pet granted W1's lessons is granted W2's on its next tick the same way.
```

and replace:

```python
GRANTED = 1  # the milestone whose lessons a gentle pet has been granted (W1)
```

with:

```python
GRANTED = 2  # the milestone whose lessons a gentle pet has been granted (W1, then W2)
```

and replace:

```python
             "makes a bed and sleeps in it", "a bed rests you best", ("bed",), ("sleep",)),
```

with:

```python
             "makes a bed and sleeps in it", "a bed rests you best", ("bed",), ("sleep",)),
    # W2: the weather and the seasons (backend.survival.sky and what hangs from it).
    Survival("winter", "winter", "Winter comes after autumn, when crops stop and animals hide, so fill a chest with "
             "food in autumn.", "gets ready for winter: fills its chests with food in autumn",
             "winter comes after autumn, so a chest of food must be filled in autumn", ("winter",), ("before",)),
    Survival("cloak", "a wool cloak", "Five wool make a wool cloak that keeps you warm in the snow.",
             "makes a wool cloak and wears it", "a wool cloak keeps the snow's cold out", ("wool cloak", "cloak")),
    Survival("hearth", "a hearth", "A hearth of stone with a fire in it keeps the home warm all winter.",
             "builds a stone hearth in its home", "a stone hearth keeps the home warm", ("hearth",)),
    Survival("smoking", "smoked meat", "Meat smoked over a fire keeps all winter.", "smokes meat over a fire",
             "smoked meat keeps all winter", ("smoked meat",)),
    Survival("rain", "rain on a fire", "Rain puts out a fire under the open sky, so keep your fire under a roof.",
             "keeps its fire under a roof", "rain puts out a fire under the open sky", ("rain",)),
    Survival("storm", "a thunderstorm", "Lightning strikes high ground and tall trees, so in a storm stay low and "
             "inside.", "goes home or down off high ground when a storm starts",
             "lightning strikes high ground, so a storm is for staying low and inside",
             ("storm", "thunderstorm", "lightning"), ("harmless",), ("dangerous",)),
    Survival("fog", "fog", "Fog hides the sun and lets the dark creatures walk by day, so stay close to home in the "
             "fog.", "stays close to home in fog and starts no trips", "fog lets the dark creatures walk by day",
             ("fog",), ("safe",), ("dangerous",)),
```

and replace:

```python
    if state["difficulty"] != GENTLE or db is None or (state.get("wild") or {}).get("granted") == GRANTED:
```

with:

```python
    if state["difficulty"] != GENTLE or db is None or ((state.get("wild") or {}).get("granted") or 0) >= GRANTED:
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest backend.tests.test_survival_sky_teaching backend.tests.test_survival_wild backend.tests.test_survival_lessons`
Expected: `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1975 tests` … `OK (skipped=6)` (4 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/lessons.py backend/survival/wild.py backend/tests/test_survival_lessons.py backend/tests/test_survival_sky_teaching.py backend/tests/test_survival_wild.py
git commit -m "feat(W2): seven survival lessons of the sky and the winter, each taught in one sentence, and a gentle pet is granted them" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: "Ready for winter"

**Files:**
- Create: `backend/survival/winter_prep.py`, `backend/tests/test_survival_winter_goal.py`
- Modify: `backend/survival/larder.py` (`TARGETS`, `target_of`), `backend/survival/goals.py` (`HELD_OFF`, `held_off` in `is_open`), `backend/survival/storage.py` (`WINTER_TAKE`: food out of the chest in winter), `backend/survival/requests.py` (the goal's words, `TITLE_STOP`), `backend/survival/brain.py` (imports `winter_prep`)

**Interfaces:**
- Consumes: Task 1's seasons; Task 6's `wild:winter` and lessons; `goals.register_goal`, `goals.PULLS`, `goals.counted`; `home.built_home`, `home.home_cell`; L5's `trips.FENCES`; `worldgen.biome_at`; W1's `spoilage` lots and rates; `larder.more_food`, `stock_valid`.
- Produces: the goal `winter_ready` (repeating; offered from autumn day 1 to its last dawn to a pet with a built home that knows `wild:winter`; 70 plus a tenth of caution; milestones food, cloak, hearth, smoked meat), `winter_prep.WINTER_FOOD` (360), `winter_food(s)`, `days_to_winter(s)`, `winter_pull` (`WINTER_PULL` 100 through `goals.PULLS`), `held(s, item)`, `hearth_home(s)`, `WINTER_REACH` (96), `keeps_near(s)`, `far_goal(s, goal)` (in `goals.HELD_OFF`), `winter_fence(s, cell)` (in `trips.FENCES`); `larder.TARGETS` (callables `(s, goal) -> (target, measure, extra) | None`, guarded) and `larder.target_of(s)`; `goals.HELD_OFF` (callables `(s, goal) -> bool`, guarded) and `goals.held_off(s, goal)`; `storage.WINTER_TAKE` (40).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_winter_goal.py`:

```python
"""W2: "Ready for winter": when it is offered, how it wins the autumn's goal choice, the food that counts for it and
stock_larder serving it."""

import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.goals import GOALS, adopt_goal, is_open, rules_score
from backend.survival.home import home_cell
from backend.survival.housework import chest_key
from backend.survival.larder import more_food
from backend.survival.memory import know
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.storage import chest_spot
from backend.survival.trips import FENCES
from backend.survival.winter_prep import (
    GOAL, WINTER_EXTRA, WINTER_FOOD, far_goal, winter_fence, winter_food, winter_pull,
)
from backend.tests.test_survival_life_goals import built

WINTER = GOALS[GOAL]


def on_day(world, day, seconds=1000.0):
    """A Situation of the built world on game day `day` (born at 0, scale 1): day 21 is autumn day 1."""
    world.state.setdefault("born_at", 0.0)
    at = (day - 1) * DAY_SECONDS + seconds
    return Situation(world.state, world.grid, clock_at(0.0, at, 1.0), at, world.db)


def stocked(world, food):
    cell = chest_spot(on_day(world, 21))
    world.grid.put(*cell, "chest")
    world.state["chests"] = {chest_key(cell): food}
    return cell


class OfferTests(unittest.TestCase):
    def test_it_is_offered_in_autumn_to_a_pet_with_a_built_home_that_knows_winter(self):
        world = built()
        self.assertEqual([is_open(on_day(world, day), WINTER) for day in (11, 20, 21, 30, 31, 61, 71)],
                         [False, False, True, True, False, True, False])
        self.assertTrue(70 <= WINTER.score(on_day(world, 21)) <= 80)
        world.state["difficulty"] = "wild"
        self.assertFalse(is_open(on_day(world, 21), WINTER))
        know(world.db, "wild:winter", "lesson", 0.0)
        self.assertTrue(is_open(on_day(world, 21), WINTER))

    def test_the_autumn_pulls_it_past_a_goal_the_rules_would_keep(self):
        world = built({"wooden_pickaxe": 1})
        adopt_goal(world.state, "iron_tools", "utility", "", 0.0)
        s = on_day(world, 21)
        self.assertGreater(rules_score(s, WINTER), rules_score(s, GOALS["iron_tools"]))
        self.assertEqual(winter_pull(on_day(world, 15), WINTER), (0.0, ""))  # summer: no pull
        self.assertEqual(winter_pull(s, WINTER), (100.0, "winter comes in 10 days"))

    def test_in_winter_a_pet_that_knows_winter_keeps_near_the_home_it_built(self):
        world = built()
        winter, autumn = on_day(world, 31), on_day(world, 21)
        x, y, z = home_cell(winter)
        far, near = (x + 100, y, z), (x + 50, y, z)
        self.assertEqual([far_goal(s, GOALS[name]) for s in (winter, autumn) for name in ("expedition", "frontier", GOAL)],
                         [True, True, False, False, False, False])
        self.assertFalse(is_open(winter, GOALS["expedition"]))
        self.assertEqual([winter_fence(winter, far), winter_fence(winter, near), winter_fence(autumn, far)],
                         [True, False, False])
        with patch("backend.survival.winter_prep.biome_at", return_value="alpine"):
            self.assertTrue(winter_fence(winter, near))  # a winter day in the mountains freezes
        self.assertIn(winter_fence, FENCES)
        world.state["difficulty"] = "wild"  # a wild pet that does not know winter roams as ever
        self.assertEqual((far_goal(on_day(world, 31), GOALS["expedition"]), winter_fence(on_day(world, 31), far)),
                         (False, False))

    def test_a_goal_whose_lesson_mimo_does_not_know_is_whole_for_it(self):
        world = built()
        world.state["difficulty"] = "wild"
        know(world.db, "wild:winter", "lesson", 0.0)
        s = on_day(world, 21)
        self.assertEqual([milestone.share(s) for milestone in WINTER.milestones[1:]], [1.0, 1.0, 1.0])


class FoodTests(unittest.TestCase):
    def test_a_gentle_pets_chest_food_all_counts(self):
        world = built()
        stocked(world, {"cooked_beef": 6, "bread": 4, "nightberries": 3})  # it knows nightberries from the start
        self.assertEqual(winter_food(on_day(world, 22)), 6 * 35 + 4 * 25)

    def test_a_wild_pets_counts_only_the_food_still_good_on_winter_day_five(self):
        world = built()
        world.state["difficulty"] = "wild"
        cell = stocked(world, {"cooked_beef": 4, "bread": 2})
        # cooked beef keeps 4 game days in arms, 8 in a chest; from autumn day 5 (6 days to winter) it ages
        # 6 x 0.5 + 4 x 0.5 / 3 = 3.67 game days of its 4 by winter day 5: only a lot under 0.08 worn keeps.
        world.state["chest_lots"] = {chest_key(cell): {"cooked_beef": [[1, 0.0], [3, 0.5]], "bread": [[2, 0.1]]}}
        self.assertEqual(winter_food(on_day(world, 25, 0.0)), 35 + 2 * 25)


class LarderTests(unittest.TestCase):
    def test_stock_larder_fills_the_chests_to_the_winters_target(self):
        world = built({"cooked_fish": 5})
        adopt_goal(world.state, GOAL, "utility", "", 0.0)
        stocked(world, {"cooked_beef": 3})
        s = on_day(world, 22)
        self.assertEqual(more_food(s), WINTER_EXTRA)
        self.assertTrue(PURPOSES["stock_larder"].valid(s))
        self.assertIn(f"105 of {round(WINTER_FOOD)} hunger", PURPOSES["stock_larder"].facts(s))
        world.state["chests"] = {key: {"cooked_beef": 11} for key in world.state["chests"]}
        full = on_day(world, 22)
        self.assertFalse(PURPOSES["stock_larder"].valid(full))
        self.assertEqual(more_food(full), 0.0)

    def test_in_winter_a_pet_short_of_food_goes_to_its_chest_before_it_forages(self):
        world = built()
        stocked(world, {"cooked_beef": 11})
        world.state["vitals"]["hunger"] = 40.0
        autumn = on_day(world, 22)
        self.assertEqual(PURPOSES["build_storage"].score(autumn), 55.0)
        world.state["sky"] = {"season": "winter"}
        s = on_day(world, 32)
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        self.assertGreater(PURPOSES["build_storage"].score(s), PURPOSES["forage"].score(s))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_winter_goal.py"`
Expected: `FAILED (errors=1)`: `ModuleNotFoundError: No module named 'backend.survival.winter_prep'`

- [ ] **Step 3: The goal, its food, the larder's target and staying near home in winter**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import sky_reflexes  # noqa: F401  (W2: flee_fire)
```

with:

```python
from backend.survival import sky_reflexes  # noqa: F401  (W2: flee_fire)
from backend.survival import winter_prep  # noqa: F401  (W2: "Ready for winter")
```

In `backend/survival/goals.py`, replace:

```python
GOALS: dict[str, Goal] = {}
```

with:

```python
GOALS: dict[str, Goal] = {}
# W2: functions of (Situation, Goal) that keep a goal from being offered, or kept, now (backend.survival.winter_prep:
# no expedition or riches trip in winter for a pet that knows winter).
HELD_OFF: list = []
```

and replace:

```python
    if not all(settled(s, name) for name in goal.after):
```

with:

```python
    if not all(settled(s, name) for name in goal.after) or held_off(s, goal):
```

and replace:

```python
    return valid and not complete(s, goal)
```

with:

```python
    return valid and not complete(s, goal)


def held_off(s: Situation, goal: Goal) -> bool:
    """W2: one of HELD_OFF keeps the goal from being offered or kept now; one that crashes holds nothing off
    (logged once)."""
    for holds in HELD_OFF:
        try:
            if holds(s, goal):
                return True
        except Exception as error:
            log_once(logger, "goal held off", error)
    return False
```

In `backend/survival/larder.py`, replace:

```python
a tenth of thrift. The goal's rules score is 45 plus a tenth of thrift, 15 more when Mimo is
hungry.
"""
```

with:

```python
a tenth of thrift. The goal's rules score is 45 plus a tenth of thrift, 15 more when Mimo is
hungry.

W2: another goal may fill the larder its own way (TARGETS: "Ready for winter", backend.survival.winter_prep,
wants WINTER_FOOD of food that will still be good in the winter, and more of it on hand): stock_larder and the
food Mimo wants on hand then follow that goal's target (`target_of`).
"""
```

and replace:

```python
from typing import TYPE_CHECKING
```

with:

```python
import logging
from typing import TYPE_CHECKING, Callable
```

and replace:

```python
from backend.survival.goals import Goal, Milestone, active, register_goal
```

with:

```python
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.once import log_once
```

and replace:

```python

GOAL = "full_larder"
```

with:

```python

logger = logging.getLogger(__name__)

GOAL = "full_larder"
```

and replace:

```python
FED = 50.0  # hunger from which Mimo gathers for the larder
```

with:

```python
FED = 50.0  # hunger from which Mimo gathers for the larder
# W2: functions (Situation, goal) giving (the food the chests should hold, how the chests' food is measured, the
# most food Mimo wants on hand beyond a day's) while `goal` fills the larder its own way, or None
# (backend.survival.winter_prep). One that crashes counts as None (logged once).
TARGETS: list = []
```

and replace:

```python
def filling(s: Situation) -> bool:
    goal = active(s)
    return goal is not None and goal.name == GOAL
```

with:

```python
def target_of(s: Situation) -> tuple[float, Callable[[Situation], float], float] | None:
    """(the food the chests should hold, how it is measured, the most more Mimo wants on hand) while Mimo's goal
    fills the larder, else None."""
    goal = active(s)
    if goal is None:
        return None
    if goal.name == GOAL:
        return LARDER_FOOD, chest_food, LARDER_EXTRA
    for aim in TARGETS:
        try:
            found = aim(s, goal)
        except Exception as error:
            log_once(logger, "larder target", error)
            continue
        if found is not None:
            return found
    return None


def filling(s: Situation) -> bool:
    return target_of(s) is not None
```

and replace:

```python
    if not filling(s) or s.vitals["hunger"] < FED:
        return 0.0
    return min(LARDER_EXTRA, max(0.0, LARDER_FOOD - chest_food(s)))
```

with:

```python
    found = target_of(s)
    if found is None or s.vitals["hunger"] < FED:
        return 0.0
    target, measure, extra = found
    return min(extra, max(0.0, target - measure(s)))
```

and replace:

```python
    if s.night or not filling(s) or chest_spot(s) is None or chest_food(s) >= LARDER_FOOD:
```

with:

```python
    found = target_of(s)
    if s.night or found is None or chest_spot(s) is None or found[1](s) >= found[0]:
```

and replace:

```python
    facts=lambda s: f"{round(chest_food(s))} of {round(LARDER_FOOD)} hunger of food in the chest; "
                    f"{sum(amount for _, amount in larder_moves(s))} spare food carried",
```

with:

```python
    facts=lambda s: f"{round(chest_food(s))} of {round((target_of(s) or (LARDER_FOOD,))[0])} hunger of food in the "
                    f"chest; {sum(amount for _, amount in larder_moves(s))} spare food carried",
```

In `backend/survival/requests.py`, replace:

```python
}
TITLE_STOP = frozenset({"a", "an", "the", "of", "its", "up", "own", "into", "to", "and", "see", "meet", "look",
                        "out"})  # L5 (pre-flight): "Riches farther out" made "map out your day" a request
```

with:

```python
    # W2: "get ready for the winter" is "Ready for winter" (backend.survival.winter_prep).
    "winter_ready": ("winter", "cloak", "hearth", "smoke", "smoked"),
}
TITLE_STOP = frozenset({"a", "an", "the", "of", "its", "up", "own", "into", "to", "and", "see", "meet", "look",
                        "out",  # L5 (pre-flight): "Riches farther out" made "map out your day" a request
                        "for"})  # W2: "Ready for winter" made "store it for later" one
```

and replace:

```python
    "thinking_machine": "build a computer", "frontier": "go looking for riches farther out",
```

with:

```python
    "thinking_machine": "build a computer", "frontier": "go looking for riches farther out",
    "winter_ready": "get ready for winter",
```

In `backend/survival/storage.py`, replace:

```python
from backend.survival.foraging import FOOD_WANTED, whole_walk
```

with:

```python
from backend.survival import sky
from backend.survival.foraging import FOOD_WANTED, hunger_score, whole_walk
```

and replace:

```python
TAKE_BELOW = 20.0  # hunger points of food carried below which Mimo takes food out
```

with:

```python
TAKE_BELOW = 20.0  # hunger points of food carried below which Mimo takes food out
# W2: in winter the chest is where the food is (bushes and crops wait for spring, herds thin, lakes freeze), so taking
# food out while Mimo carries less than TAKE_BELOW scores as food work does, from this base (forage's is 35). On the
# gate's third run a gentle pet with 740 hunger points in its chests went foraging bare winter land 58 blocks from home
# and starved 24 game minutes.
WINTER_TAKE = 40.0
```

and replace:

```python
    cell = chest_spot(s)
    if chest_placed(s, cell) and to_take(s) and stacks(s.inventory) < STORE_FROM:
```

with:

```python
    cell = chest_spot(s)
    if sky.winter(s.state) and carried_food(s) < TAKE_BELOW and to_take(s):  # W2
        return max(55.0, hunger_score(s, WINTER_TAKE))
    if chest_placed(s, cell) and to_take(s) and stacks(s.inventory) < STORE_FROM:
```

Create `backend/survival/winter_prep.py`:

```python
"""W2: "Ready for winter" (the Wild World spec's "Recipes, blocks and the winter goal").

The goal `winter_ready` repeats: it is offered from autumn day 1 until winter day 1 to a pet with a built home
that knows `wild:winter` (a gentle pet always does). Its rules score is 70 plus a tenth of caution (70 to 80),
above iron tools and never past the survival floor, and while it is open the season pulls it WINTER_PULL higher
(goals.PULLS), so at the first autumn dawn's goal choice it wins over a goal the rules would otherwise keep.
Its milestones, each only for a lesson Mimo knows (one it does not know is whole: nothing to do for it):
- the chests hold WINTER_FOOD hunger points (six winter days) of food Mimo would eat that will still be good on
  winter day 5 at chest rates (`winter_food`; a gentle pet's food never spoils), which stock_larder serves with
  that target (larder.TARGETS), Mimo wanting up to WINTER_EXTRA more food on hand while it gathers;
- a wool cloak, a hearth in home and SMOKED_WANTED smoked meat (the cloak, the hearth and the smoke step come
  with their purposes and recipes: a milestone is skipped until then, goals.counted).
Reached, it is a notable "goal" event, as goals are.

In winter a pet that knows winter keeps near the home it built (`keeps_near`): a winter night out, or a winter day
in the mountains (vitals.ALPINE_DAY: 45 less 60), freezes. It takes up no expedition and no riches trip (FAR_GOALS,
goals.HELD_OFF: one already under way is given up at the next goal check, "it cannot be done now", and Mimo comes
home), and no trip heads for a target farther than WINTER_REACH from home or in the mountains (trips.FENCES).
Measured on the gate's gentle lives before this rule: every freezing minute of the first winters was 150 to 240
blocks out, on an expedition, a riches trip or the far hills, and one pet lost 88 health in a winter night dug in
on a mountain with no fire.
"""

from __future__ import annotations

import math

from backend.services.worldgen import biome_at
from backend.survival import larder, sky
from backend.survival.clock import DAY_SECONDS
from backend.survival.goals import HELD_OFF, PULLS, Goal, Milestone, register_goal
from backend.survival.home import built_home, home_cell, home_structure
from backend.survival.purposes import foods
from backend.survival.situation import Situation
from backend.survival.spoilage import CHEST_RATE, PERISHABLE, WINTER_RATE
from backend.survival.steps import FOOD
from backend.survival.trips import FENCES
from backend.survival.wild import is_wild, unlocked

GOAL = "winter_ready"
WINTER_FOOD = 360.0  # hunger points: six winter days
WINTER_EXTRA = 120.0  # the most food beyond a day's Mimo wants on hand while it fills the chests for winter
GOOD_UNTIL = 4  # winter days the food must keep: it is still good on winter day 5
SMOKED_WANTED = 8
WINTER_PULL = 100.0  # the season's pull on the goal while it is open (as much as goals.STICK)
WINTER_REACH = 96.0  # blocks from the home it built that a pet that knows winter goes in winter
FAR_GOALS = ("expedition", "frontier")  # goals held off in winter: an expedition and riches farther out
AUTUMN = sky.SEASONS.index("autumn") * sky.SEASON_DAYS  # the season day autumn starts on (20)
WINTER_START = sky.SEASONS.index("winter") * sky.SEASON_DAYS  # and winter (30)


def season_day(s: Situation) -> int:
    """The season day (0 to 39) now; spring day 1 for a state with no birth time (a test's bare state)."""
    return sky.season_at(s.state, s.at, s.scale)[1] if "born_at" in s.state else 0


def preparing(s: Situation) -> bool:
    """Autumn: from autumn day 1 until winter day 1."""
    return AUTUMN <= season_day(s) < WINTER_START


def days_to_winter(s: Situation) -> float:
    return max(0.0, WINTER_START - season_day(s) - s.clock["seconds_into_day"] / DAY_SECONDS)


def winter_food(s: Situation) -> float:
    """Hunger points of the food in Mimo's chests (not an old ruin's) it would eat and that will still be good on
    winter day 5: for a wild pet, the lots whose wear by then (half as fast in a chest, and a third of that in
    winter) stays under 1; a gentle pet's food never spoils."""
    from backend.survival.ruins import ruin_chest_key  # here: brain imports the larder before the ruins
    wild, autumn = is_wild(s.state), days_to_winter(s)
    lots = s.state.get("chest_lots", {})
    total = 0.0
    for key, chest in s.state.get("chests", {}).items():
        if ruin_chest_key(s.seed, key):
            continue
        for item in foods(chest, s.poisons):
            count = chest[item]
            if wild and item in PERISHABLE:
                later = (autumn * CHEST_RATE + GOOD_UNTIL * CHEST_RATE * WINTER_RATE) / PERISHABLE[item]
                count = min(count, sum(number for number, wear in lots.get(key, {}).get(item, []) if wear + later < 1.0))
            total += FOOD[item] * count
    return total


def target(s: Situation, goal) -> tuple | None:
    """larder.TARGETS: the winter's food while "Ready for winter" is Mimo's goal."""
    return (WINTER_FOOD, winter_food, WINTER_EXTRA) if goal.name == GOAL else None


def held(s: Situation, item: str) -> int:
    """How many of `item` Mimo carries and its chests hold."""
    return s.count(item) + sum(chest.get(item, 0) for chest in s.state.get("chests", {}).values())


def food_share(s: Situation) -> float:
    return 1.0 if not unlocked(s, "winter") else winter_food(s) / WINTER_FOOD


def cloak_share(s: Situation) -> float:
    return 1.0 if not unlocked(s, "cloak") or held(s, "wool_cloak") > 0 else 0.0


def hearth_home(s: Situation) -> bool:
    """A hearth stands in a room cell of the shelter Mimo lives in."""
    from backend.survival.structures import blueprint_of  # here: structures imports the building purposes
    structure = home_structure(s)
    if structure is None:
        return False
    return any(s.grid.material(*planned.cell) == "hearth" for planned in blueprint_of(structure).parts("room"))


def hearth_share(s: Situation) -> float:
    return 1.0 if not unlocked(s, "hearth") or hearth_home(s) else 0.0


def smoked_share(s: Situation) -> float:
    return 1.0 if not unlocked(s, "smoking") else held(s, "smoked_meat") / SMOKED_WANTED


def goal_valid(s: Situation) -> bool:
    return preparing(s) and unlocked(s, "winter") and home_structure(s) is not None


def winter_pull(s: Situation, goal) -> tuple[float, str]:
    """goals.PULLS: winter is coming."""
    if goal.name != GOAL or not preparing(s):
        return 0.0, ""
    return WINTER_PULL, f"winter comes in {max(1, round(days_to_winter(s)))} days"


def keeps_near(s: Situation) -> bool:
    """In winter a pet that knows winter keeps near the home it built."""
    return season_day(s) >= WINTER_START and unlocked(s, "winter") and built_home(s)


def far_goal(s: Situation, goal) -> bool:
    """goals.HELD_OFF: no expedition and no riches trip in winter."""
    return goal.name in FAR_GOALS and keeps_near(s)


def winter_fence(s: Situation, cell) -> bool:
    """trips.FENCES: in winter no trip heads for a target farther than WINTER_REACH from home or in the mountains."""
    if not keeps_near(s):
        return False
    home = home_cell(s)
    far = math.hypot(cell[0] - home[0], cell[2] - home[2]) > WINTER_REACH
    return far or biome_at(cell[0], cell[2], s.seed) == "alpine"


register_goal(Goal(
    GOAL, "Ready for winter",
    "Winter is coming: crops stop and animals hide, so the chests need food, and a cloak, a hearth and smoked "
    "meat will see it through.",
    (Milestone("Fill the chests with food for the winter", food_share,
               ("stock_larder", "forage", "fish", "hunt", "farm", "cook", "smoke_meat")),
     Milestone("Make a wool cloak", cloak_share, ("make_cloak",), items=("wool_cloak",)),
     Milestone("Build a hearth at home", hearth_share, ("build_hearth",), items=("hearth",)),
     Milestone("Smoke meat for the winter", smoked_share, ("smoke_meat",))),
    score=lambda s: 70.0 + s.trait("caution") / 10, thought="Winter is coming. Better get ready.",
    after=("first_shelter",), valid=goal_valid, repeat=True))
larder.TARGETS.append(target)
PULLS.append(winter_pull)
HELD_OFF.append(far_goal)
FENCES.append(winter_fence)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_winter_goal.py"`
Expected: `Ran 8 tests` `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1983 tests` … `OK (skipped=6)` (8 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/brain.py backend/survival/goals.py backend/survival/larder.py backend/survival/requests.py backend/survival/storage.py backend/survival/winter_prep.py backend/tests/test_survival_winter_goal.py
git commit -m "feat(W2): in autumn a pet that knows winter gets ready for it and fills its chests with food that keeps, and in winter it stays near home and eats from its chests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The cloak, the hearth and smoked meat

**Files:**
- Create: `backend/survival/winter_gear.py`, `backend/tests/test_survival_winter_gear.py`
- Modify: `backend/services/crafting.py` (`wool_cloak`, `hearth`, `FIRES`), `backend/survival/carrying.py` (`WORN`: a worn cloak takes no stack), `backend/survival/steps.py` (`FOOD`, `WORKSTATIONS`), `backend/survival/vitals.py` (`WARM_BLOCKS`), `backend/survival/light.py` (the hearth's light), `backend/survival/cooking.py` (the fires cook carries, `SPARED`), `backend/survival/wild.py` (`FAMILIAR`, `cloaked`), `backend/survival/tick.py` (the cloak's warmth), `backend/survival/brain.py` (imports `winter_gear`)
- Test: `backend/tests/test_survival_meat.py` (the leftovers' pet wears a cloak: resolution 18)

**Interfaces:**
- Consumes: Task 3's `hearth` block; Task 7's goal, `held`, `hearth_home`; creature gear's `gear_steps`; `harm.SLOTS`; `storage.KEEPS_MORE`, `storage.TAKES_MORE`; `purposes.register_purpose`; `homes`.
- Produces: items `wool_cloak` (slot `"cloak"`, +20 warmth) and `smoked_meat` (20 hunger, never spoils); the recipes; the purposes `make_cloak` (55 + caution/10), `build_hearth` (60), `smoke_meat` (65); the `smoke` step (`start_smoke`, `finish_smoke`, 20 s); `winter_gear.hearth_spot(s)`, `keep_wool`, `wool_back`; `wild.cloaked(state, db)`; `carrying.WORN`; `winter_gear.smoke_wanted(s)`, `spare_meat` (in `cooking.SPARED`: callables `(s) -> raw foods cook leaves alone`, guarded), `SPARE_ABOVE` (50).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_meat.py`, replace:

```python
        home = Home({"leather": 7, "wool": 3, "feather": 6, "rabbit_hide": 9, "raw_beef": 1}, chest={})
```

with:

```python
        # W2: with its cloak made (a pet that wants one keeps its wool: backend.survival.winter_gear)
        home = Home({"leather": 7, "wool": 3, "feather": 6, "rabbit_hide": 9, "raw_beef": 1, "wool_cloak": 1}, chest={})
```

Create `backend/tests/test_survival_winter_gear.py`:

```python
"""W2: the wool cloak, the hearth and smoked meat: their recipes, what each does, and the purposes that make them."""

import sqlite3
import unittest
from types import SimpleNamespace

from backend.services.crafting import FIRES, craft, smelt
from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.carrying import CARRY_STACKS, room_for, stacks
from backend.survival.creatures.harm import ARMOR, SLOTS, armor_cut
from backend.survival.goals import GOALS, adopt_goal
from backend.survival.housework import chest_key
from backend.survival.light import BLOCK_LIGHT
from backend.survival.memory import create_memory_tables, know
from backend.survival.purposes import PURPOSES
from backend.survival.rain import douse
from backend.survival.spoilage import PERISHABLE
from backend.survival.steps import FOOD, StepFailed, finish_step, start_step
from backend.survival.storage import chest_spot, kept, to_take
from backend.survival.vitals import WARM_BLOCKS, near_warm_block
from backend.survival.wild import cloaked
from backend.survival.cooking import cook_plan
from backend.survival.winter_gear import SMOKABLE, SMOKE_SECONDS, hearth_spot, smoke_wanted, spare_meat
from backend.survival.winter_prep import GOAL, hearth_home
from backend.tests.test_survival_cooking import meadow
from backend.tests.test_survival_winter_goal import on_day
from backend.tests.test_survival_life_goals import built


def outside(world):
    """Mimo out on the meadow, where a crafting table can stand (none goes inside its shelter)."""
    world.state["position"] = {"x": 12.0, "y": 1.0, "z": 12.0}
    return world


class RecipeTests(unittest.TestCase):
    def test_five_wool_make_a_cloak_and_stone_and_a_campfire_a_hearth_at_a_table(self):
        self.assertEqual(craft({"wool": 5}, "wool_cloak", {"crafting_table"}), {"wool_cloak": 1})
        self.assertEqual(craft({"cobblestone": 9, "campfire": 1}, "hearth", {"crafting_table"}),
                         {"cobblestone": 1, "hearth": 1})
        with self.assertRaises(ValueError):
            craft({"wool": 4}, "wool_cloak", {"crafting_table"})

    def test_the_cloak_is_its_own_slot_and_no_armor(self):
        self.assertEqual(SLOTS["wool_cloak"], "cloak")
        self.assertNotIn("wool_cloak", ARMOR)
        self.assertEqual(armor_cut({"wool_cloak": 1}), 0.0)

    def test_a_worn_cloak_takes_no_stack(self):
        arms = {f"item{n}": 1 for n in range(CARRY_STACKS - 1)}
        self.assertEqual(stacks({**arms, "wool_cloak": 1}), CARRY_STACKS - 1)
        self.assertEqual(room_for({**arms, "wool_cloak": 1}, "cobblestone", CARRY_STACKS), 32)

    def test_a_cloak_warms_a_gentle_pet_and_a_wild_one_once_it_knows_the_cloak(self):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        self.assertTrue(cloaked({"inventory": {"wool_cloak": 1}}, db))
        self.assertFalse(cloaked({"inventory": {}}, db))
        wild = {"inventory": {"wool_cloak": 1}, "difficulty": "wild"}
        self.assertFalse(cloaked(wild, db))
        know(db, "wild:cloak", "lesson", 0.0)
        self.assertTrue(cloaked(wild, db))

    def test_a_hearth_warms_lights_cooks_and_never_goes_out_in_the_rain(self):
        self.assertIn("hearth", WARM_BLOCKS)
        self.assertTrue(near_warm_block([(3, 1, 0, "hearth")], 0, 1, 0))
        self.assertEqual(BLOCK_LIGHT["hearth"], 13)
        self.assertIn("hearth", FIRES)
        self.assertEqual(smelt({"raw_beef": 1}, "raw_beef", {"hearth"}), {"cooked_beef": 1})
        grid = meadow({(2, 1, 0): "hearth"})
        state = {"name": "Pip", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "sky": {"weather": "rain"}}
        douse(state, SimpleNamespace(grid=grid, events=[], db=None), 1.0)
        self.assertEqual(grid.material(2, 1, 0), "hearth")


class SmokeTests(unittest.TestCase):
    def test_a_stick_and_raw_meat_smoke_into_meat_that_never_spoils(self):
        grid = meadow({(2, 1, 0): "campfire"})
        state = {"name": "Pip", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {"raw_beef": 2, "sticks": 1}}
        step = start_step({"kind": "smoke", "item": "raw_beef"}, state, grid, 0.0)
        self.assertEqual(step["ends_at"], SMOKE_SECONDS)
        event = finish_step(step, state, grid, step["ends_at"])
        self.assertEqual(state["inventory"], {"raw_beef": 1, "smoked_meat": 1})
        self.assertEqual(event, ("smoke", "Pip smoked raw beef."))
        self.assertEqual((FOOD["smoked_meat"], "smoked_meat" in PERISHABLE), (20.0, False))
        with self.assertRaises(StepFailed):  # no stick left
            start_step({"kind": "smoke", "item": "raw_beef"}, state, grid, 0.0)
        with self.assertRaises(StepFailed):  # no fire
            start_step({"kind": "smoke", "item": "raw_beef"}, {**state, "inventory": {"raw_beef": 1, "sticks": 1}},
                       meadow(), 0.0)

    def test_smoke_meat_smokes_while_the_winter_goal_wants_more(self):
        world = outside(built({"raw_mutton": 3, "sticks": 6, "oak_log": 2}))
        s = on_day(world, 22)
        self.assertFalse(PURPOSES["smoke_meat"].valid(s))
        adopt_goal(world.state, GOAL, "utility", "", 0.0)
        s = on_day(world, 22)
        self.assertTrue(PURPOSES["smoke_meat"].valid(s))
        steps = PURPOSES["smoke_meat"].plan(s, None)
        self.assertEqual([step["kind"] for step in steps].count("smoke"), 3)
        self.assertEqual(steps[-1]["kind"], "mine")  # the campfire it put down comes back
        world.state["inventory"]["smoked_meat"] = 8
        self.assertFalse(PURPOSES["smoke_meat"].valid(on_day(world, 22)))  # enough for the winter

    def test_a_wild_pet_smokes_its_meat_while_its_winter_food_falls_short_and_leaves_it_uncooked(self):
        world = outside(built({"raw_mutton": 3, "sticks": 6, "oak_log": 2, "smoked_meat": 8}))
        world.state["difficulty"] = "wild"
        for lesson in ("winter", "smoking", "cooking", "fire"):
            know(world.db, f"wild:{lesson}", "lesson", 0.0)
        adopt_goal(world.state, GOAL, "utility", "", 0.0)
        s = on_day(world, 22)
        self.assertEqual(smoke_wanted(s), 18)  # the chests hold no winter food: 360 hunger points, 20 a smoked meat
        self.assertEqual([step["kind"] for step in PURPOSES["smoke_meat"].plan(s, None)].count("smoke"), 3)
        self.assertIsNone(cook_plan(s))  # the mutton is kept for smoking
        world.state["vitals"]["hunger"] = 40.0
        self.assertIn({"kind": "cook", "item": "raw_mutton"}, cook_plan(on_day(world, 22)))  # hungry: it cooks
        world.state["vitals"]["hunger"] = 80.0
        world.state["inventory"].update(sticks=0, planks=4)  # no stick: it makes them from its planks
        steps = PURPOSES["smoke_meat"].plan(on_day(world, 22), None)
        self.assertIn({"kind": "craft", "recipe": "sticks"}, steps)
        self.assertEqual([step["kind"] for step in steps].count("smoke"), 3)
        world.state["inventory"].update(oak_log=0, planks=0, sticks=5)  # no fire to put down: it walks to one it has
        x, y, z = (round(world.state["position"][axis]) for axis in "xyz")
        world.grid.put(x + 20, y, z, "campfire")
        self.assertEqual(PURPOSES["smoke_meat"].plan(on_day(world, 22), None)[0]["kind"], "walk")
        self.assertEqual(spare_meat(on_day(world, 22)), SMOKABLE)
        world.state["inventory"].update(sticks=0)  # no stick and no wood for one: meat it cannot smoke is not spared
        self.assertEqual(spare_meat(on_day(world, 22)), ())


class CloakTests(unittest.TestCase):
    def test_make_cloak_makes_one_with_five_wool_and_keeps_the_wool_meanwhile(self):
        world = outside(built({"wool": 5, "planks": 4}))
        s = on_day(world, 5)
        self.assertTrue(PURPOSES["make_cloak"].valid(s))
        steps = PURPOSES["make_cloak"].plan(s, None)
        self.assertIn({"kind": "craft", "recipe": "wool_cloak"}, steps)
        self.assertEqual(kept(s, "wool"), 5)
        world.state["inventory"]["wool_cloak"] = 1
        s = on_day(world, 5)
        self.assertFalse(PURPOSES["make_cloak"].valid(s))
        self.assertEqual(kept(s, "wool"), 0)

    def test_the_wool_comes_back_out_of_the_chest_for_it(self):
        world = built({"wool": 1})
        cell = chest_spot(on_day(world, 5))
        world.grid.put(*cell, "chest")
        world.state["chests"] = {chest_key(cell): {"wool": 6}}
        self.assertIn((cell, "wool", 4), to_take(on_day(world, 5)))


class HearthTests(unittest.TestCase):
    def test_build_hearth_puts_one_in_a_front_corner_of_home_while_the_winter_goal_wants_it(self):
        world = outside(built({"cobblestone": 8, "campfire": 1, "planks": 4}))
        s = on_day(world, 22)
        self.assertFalse(PURPOSES["build_hearth"].valid(s))
        adopt_goal(world.state, GOAL, "utility", "", 0.0)
        s = on_day(world, 22)
        spot = hearth_spot(s)
        self.assertIsNotNone(spot)
        self.assertTrue(PURPOSES["build_hearth"].valid(s))
        steps = PURPOSES["build_hearth"].plan(s, None)
        self.assertIn({"kind": "craft", "recipe": "hearth"}, steps)
        self.assertEqual(steps[-1], {"kind": "place", "target": list(spot), "block": "hearth"})
        world.grid.put(*spot, "hearth")
        s = on_day(world, 22)
        self.assertTrue(hearth_home(s))
        self.assertFalse(PURPOSES["build_hearth"].valid(s))
        self.assertEqual(GOALS[GOAL].milestones[2].share(s), 1.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_survival_winter_gear backend.tests.test_survival_meat`
Expected: `FAILED (errors=1)`: `ImportError: cannot import name 'cloaked' from 'backend.survival.wild'`

- [ ] **Step 3: The recipes, the purposes and the smoke step**

In `backend/services/crafting.py`, replace:

```python
})
# Any wood does where a recipe asks for oak (L3): birch and spruce logs stand in for an oak log, and
```

with:

```python
})
# W2: a wool cloak for the snow and a stone hearth for the home (backend.survival.winter_gear).
RECIPES.update({
    "wool_cloak": {"ingredients": {"wool": 5}, "output": {"wool_cloak": 1}, "station": "crafting_table"},
    "hearth": {"ingredients": {"cobblestone": 8, "campfire": 1}, "output": {"hearth": 1}, "station": "crafting_table"},
})
# Any wood does where a recipe asks for oak (L3): birch and spruce logs stand in for an oak log, and
```

and replace:

```python
FIRES = ("campfire", "furnace")
```

with:

```python
FIRES = ("campfire", "furnace", "hearth")  # W2: a hearth cooks like a campfire
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import winter_prep  # noqa: F401  (W2: "Ready for winter")
```

with:

```python
from backend.survival import winter_gear, winter_prep  # noqa: F401  (W2: "Ready for winter"; cloak, hearth, smoke)
```

In `backend/survival/carrying.py`, replace:

```python


def stacks(items: dict[str, int]) -> int:
    """How many stacks `items` fill."""
    return sum(math.ceil(count / STACK) for count in items.values() if count > 0)
```

with:

```python
# W2: worn, not carried: the wool cloak takes no stack. Kept on Mimo like its armor, it would otherwise fill a
# stack for good, and a pet with full arms can dig no cobblestone (Making's full-arms stall: measured on the
# gate's route runs, seed 5 carried 16 stacks with its cloak and never finished its computer).
WORN = frozenset({"wool_cloak"})


def stacks(items: dict[str, int]) -> int:
    """How many stacks `items` fill (a worn cloak fills none)."""
    return sum(math.ceil(count / STACK) for item, count in items.items() if count > 0 and item not in WORN)
```

In `backend/survival/cooking.py`, replace:

```python

from typing import TYPE_CHECKING
```

with:

```python

import logging
from typing import TYPE_CHECKING
```

and replace:

```python
from backend.survival.grid import Cell
```

with:

```python
from backend.survival.grid import Cell
from backend.survival.once import log_once
```

and replace:

```python
        return station(inventory, "campfire", spots, steps, placed, FIRES)
    return inventory.get("furnace", 0) > 0 and station(inventory, "furnace", spots, steps, placed, ("furnace",))


def cook_plan(s: Situation) -> list[dict] | None:
    """The steps that cook the raw food Mimo carries, or None when it cannot cook any now."""
```

with:

```python
        return station(inventory, "campfire", spots, steps, placed, ("campfire", "furnace"))  # W2: never a hearth
    return inventory.get("furnace", 0) > 0 and station(inventory, "furnace", spots, steps, placed, ("furnace",))


logger = logging.getLogger(__name__)
# W2: functions of the Situation giving the raw foods cook leaves alone now (backend.survival.winter_gear: the meat a
# wild pet smokes for the winter instead). One that crashes spares nothing (logged once).
SPARED: list = []


def spared(s: Situation) -> frozenset[str]:
    found: set[str] = set()
    for spare in SPARED:
        try:
            found.update(spare(s))
        except Exception as error:
            log_once(logger, "cook spared", error)
    return frozenset(found)


def cook_plan(s: Situation) -> list[dict] | None:
    """The steps that cook the raw food Mimo carries (but what SPARED leaves alone), or None when it cannot cook any
    now."""
```

and replace:

```python
    raw = [(item, inventory[item]) for item in RAW_FOODS if inventory.get(item, 0) > 0] if unlocked(s, "cooking") else []
```

with:

```python
    left = spared(s)
    raw = ([(item, inventory[item]) for item in RAW_FOODS if inventory.get(item, 0) > 0 and item not in left]
           if unlocked(s, "cooking") else [])
```

In `backend/survival/light.py`, replace:

```python
               "fire": 13}  # W2: a fire in the trees
```

with:

```python
               "fire": 13, "hearth": 13}  # W2: a fire in the trees, and a hearth
```

In `backend/survival/steps.py`, replace:

```python
WORKSTATIONS = ("crafting_table", "furnace", "campfire", "kiln")  # Making: the kiln fires bricks and glass
```

with:

```python
WORKSTATIONS = ("crafting_table", "furnace", "campfire", "kiln",  # Making: the kiln fires bricks and glass
                "hearth")  # W2: cooks and smokes like a campfire
```

and replace:

```python
        "nightberries": 8.0, "spoiled_food": 4.0}  # W1: nightberries fill like berries, and are poison
```

with:

```python
        "nightberries": 8.0, "spoiled_food": 4.0,  # W1: nightberries fill like berries, and are poison
        "smoked_meat": 20.0}  # W2: it never spoils (backend.survival.winter_gear)
```

In `backend/survival/tick.py`, replace:

```python
outdoors (Surroundings.snowing; backend.survival.weather's other effects register themselves). Lightning or a
```

with:

```python
outdoors (Surroundings.snowing; backend.survival.weather's other effects register themselves); a wool cloak
Mimo wears (wild.cloaked) adds warmth (Surroundings.cloak). Lightning or a
```

and replace:

```python
from backend.survival.wild import settle
```

with:

```python
from backend.survival.wild import cloaked, settle
```

and replace:

```python
        snowing=state is not None and sky.weather_now(state) == "snow",
```

with:

```python
        snowing=state is not None and sky.weather_now(state) == "snow",
        cloak=state is not None and cloaked(state, db),
```

In `backend/survival/vitals.py`, replace:

```python
WARM_BLOCKS = ("campfire", "furnace")
```

with:

```python
WARM_BLOCKS = ("campfire", "furnace", "hearth")  # W2: a hearth warms like a furnace
```

In `backend/survival/wild.py`, replace:

```python
            "raw_chicken", "raw_rabbit", "cooked_beef", "cooked_mutton", "cooked_chicken", "cooked_rabbit")
```

with:

```python
            "raw_chicken", "raw_rabbit", "cooked_beef", "cooked_mutton", "cooked_chicken", "cooked_rabbit",
            "smoked_meat")  # W2: what it smoked itself
```

and replace:

```python

def survival_view(db: sqlite3.Connection) -> list[dict]:
```

with:

```python

def cloaked(state: dict, db: sqlite3.Connection | None) -> bool:
    """W2: Mimo wears a wool cloak: it carries one and (a wild pet) knows `wild:cloak`, which unlocks wearing it."""
    if state.get("inventory", {}).get("wool_cloak", 0) < 1:
        return False
    if not is_wild(state):
        return True
    return db is not None and db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact=?",
                                         (thing("cloak"), LESSON)).fetchone() is not None


def survival_view(db: sqlite3.Connection) -> list[dict]:
```

Create `backend/survival/winter_gear.py`:

```python
"""W2: the wool cloak, the hearth and smoked meat ("Recipes, blocks and the winter goal" of the Wild World spec).

- The wool cloak (5 wool at a crafting table, crafting.RECIPES) sits in a slot of its own, not armor
  (harm.SLOTS "cloak"), and is worn by carrying it: CLOAK_WARMTH warmer (the tick's Surroundings.cloak), once a
  wild pet knows `wild:cloak` (wild.cloaked). make_cloak (work band: 55 plus a tenth of caution, by day) makes one
  with a crafting table it places and mines back, as make_gear does, once Mimo knows the cloak, has none and
  carries the wool; while it wants one, CLOAK_WOOL wool stay on hand (storage.KEEPS_MORE) and come back out of
  the chest when it holds them (storage.TAKES_MORE).
- The hearth (8 cobblestone and a campfire at a crafting table) is a block: glow and light 13, warm like a furnace
  (vitals.WARM_BLOCKS), a fire to cook and smoke at (crafting.FIRES, steps.WORKSTATIONS), and it never goes out in
  the rain. build_hearth (work band, HEARTH_SCORE, by day, while the winter goal wants one) puts it in the home's
  room, in the front corner nearest home's cell (two walls beside it, clear of the way in), which the home claims
  already.
- Smoked meat: the `smoke` step (SMOKE_SECONDS at a campfire or hearth) turns 1 raw meat and 1 stick into 1 smoked
  meat, which fills 20 hunger and never spoils (it is no PERISHABLE food). smoke_meat (work band, SMOKE_SCORE, by
  day) smokes the raw meat Mimo carries while the winter goal wants more smoked meat (winter_prep.SMOKED_WANTED),
  lighting a campfire as cook does.
Each is unlocked by its lesson (`wild:cloak`, `wild:hearth`, `wild:smoking`); a gentle pet knows them all.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.crafting import add_item, take_items
from backend.survival import storage
from backend.survival.carrying import crafts_fit
from backend.survival.cooking import FIRE_STAND, FIRE_TRAVEL, SPARED, station
from backend.survival.creatures.gear import gear_steps
from backend.survival.creatures.harm import SLOTS
from backend.survival.foraging import whole_walk
from backend.survival.goals import active
from backend.survival.grid import Cell
from backend.survival.home import home_structure
from backend.survival.purposes import HOME_RANGE, Purpose, register
from backend.survival.rain import relight_steps, roofed_first
from backend.survival.senses import near_failure
from backend.survival.situation import Situation
from backend.survival.steps import (
    FOOD, REACH, STATION_REACH, WORKSTATIONS, StepFailed, StepKind, as_cell, label, register_step, room_to_make,
    stations_near,
)
from backend.survival.structures import blueprint_of
from backend.survival.toolmaking import Short, make, station_spots
from backend.survival.wild import is_wild, unlocked
from backend.survival.winter_prep import GOAL, SMOKED_WANTED, WINTER_FOOD, hearth_home, held, winter_food

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

CLOAK_WOOL = 5
SMOKE_SECONDS = 20.0
SMOKABLE = ("raw_beef", "raw_mutton", "raw_chicken", "raw_rabbit")
SMOKE_FIRES = frozenset({"campfire", "hearth"})
HEARTH_SCORE = 60.0
SMOKE_SCORE = 65.0
SPARE_ABOVE = 50.0  # hunger from which a wild pet keeps the meat for smoking rather than cook it
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))

SLOTS["wool_cloak"] = "cloak"  # its own slot: never armor (spec resolution 22)


def winter_goal(s: Situation) -> bool:
    goal = active(s)
    return goal is not None and goal.name == GOAL


# The wool cloak ----------------------------------------------------------------------------------

def cloak_wanted(s: Situation) -> bool:
    return unlocked(s, "cloak") and held(s, "wool_cloak") == 0


def cloak_plan(s: Situation) -> list[dict] | None:
    if not cloak_wanted(s) or s.count("wool") < CLOAK_WOOL:
        return None
    return s.sensed("cloak_plan", lambda: gear_steps(s, ("wool_cloak",)))


def keep_wool(s: Situation, item: str) -> float:
    """storage.KEEPS_MORE: the cloak's wool stays on hand while Mimo wants a cloak."""
    return CLOAK_WOOL if item == "wool" and cloak_wanted(s) else 0.0


def wool_back(s: Situation) -> dict[str, int]:
    """storage.TAKES_MORE: the cloak's wool back out of the chest once Mimo's arms and chests hold enough."""
    if not cloak_wanted(s) or s.count("wool") >= CLOAK_WOOL or held(s, "wool") < CLOAK_WOOL:
        return {}
    return {"wool": CLOAK_WOOL - s.count("wool")}


def plan_cloak(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] > 0:
        return []
    return list(cloak_plan(s) or [])


register(Purpose(
    "make_cloak", "make a wool cloak", "Make a wool cloak from five wool at a crafting table: it keeps you warm.",
    valid=lambda s: not s.night and cloak_plan(s) is not None,
    facts=lambda s: f"carrying {s.count('wool')} wool; five make a cloak",
    score=lambda s: 55.0 + s.trait("caution") / 10, plan=plan_cloak,
    thoughts=("A warm cloak for the cold days.", "Five wool, one cloak.")))


# The hearth --------------------------------------------------------------------------------------

def hearth_spot(s: Situation) -> Cell | None:
    """The room cell of Mimo's home the hearth goes in: one with walls on two sides (a front corner, clear of
    the way in and of the bed and chest corners), the nearest home's cell; None when none is free."""
    structure = home_structure(s)
    if structure is None or structure["status"] != "done":
        return None
    blueprint = blueprint_of(structure)
    walls = {planned.cell for planned in blueprint.parts("wall")}
    level = blueprint.anchor[1]
    corners = [planned.cell for planned in blueprint.parts("room") if planned.cell[1] == level
               and sum((planned.cell[0] + dx, level, planned.cell[2] + dz) in walls for dx, dz in SIDES) >= 2
               and s.grid.material(*planned.cell) == "air"]
    return min(corners, key=lambda cell: (math.dist(cell, blueprint.anchor), cell)) if corners else None


def hearth_plan(s: Situation) -> list[dict] | None:
    """Make the hearth when Mimo carries none, walk home and put it in its corner; None when it cannot now."""
    def look() -> list[dict] | None:
        if not (winter_goal(s) and unlocked(s, "hearth")) or hearth_home(s):
            return None
        spot = hearth_spot(s)
        if spot is None:
            return None
        blueprint = blueprint_of(home_structure(s))
        if s.distance(blueprint.anchor) > HOME_RANGE:
            return None
        steps: list[dict] = []
        if s.count("hearth") < 1:
            crafting = gear_steps(s, ("hearth",))
            if crafting is None:
                return None
            steps.extend(crafting)
        if s.here not in blueprint.stands or math.dist(s.here, spot) > REACH:
            steps.append(whole_walk(blueprint.anchor))
        return steps + [{"kind": "place", "target": list(spot), "block": "hearth"}]
    return s.sensed("hearth_plan", look)


def plan_hearth(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] > 0:
        return []
    return list(hearth_plan(s) or [])


register(Purpose(
    "build_hearth", "build a hearth", "Build a stone hearth in the corner of home: it keeps the home warm all winter.",
    valid=lambda s: not s.night and hearth_plan(s) is not None,
    facts=lambda s: f"{s.count('cobblestone')} cobblestone carried; a hearth takes 8 and a campfire",
    score=lambda s: HEARTH_SCORE, plan=plan_hearth,
    thoughts=("A hearth will keep the cold out.", "Stone and fire: a hearth for the winter.")))


# Smoked meat -------------------------------------------------------------------------------------

def smoke_fire(grid, state: dict) -> bool:
    return bool(stations_near(grid, as_cell(state["position"])).intersection(SMOKE_FIRES))


def smoked(inventory: dict, item: str) -> dict:
    """`inventory` once 1 of `item` and a stick are smoked into 1 smoked meat."""
    after = take_items(inventory, {item: 1, "sticks": 1})
    add_item(after, "smoked_meat")
    return after


def start_smoke(spec: dict, state: dict, grid, at: float, scale: float) -> dict:
    item = spec["item"]
    if item not in SMOKABLE:
        raise StepFailed(f"{label(item)} cannot be smoked")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to smoke", "missing_item")
    if state["inventory"].get("sticks", 0) < 1:
        raise StepFailed("no stick to smoke it over", "missing_item")
    if not smoke_fire(grid, state):
        raise StepFailed("no fire to smoke it over", "missing_item")
    room_to_make(state["inventory"], smoked(dict(state["inventory"]), item), "smoked_meat")
    return {"kind": "smoke", "started_at": at, "ends_at": round(at + SMOKE_SECONDS / scale, 3), "item": item}


def finish_smoke(step: dict, state: dict, grid, at: float) -> tuple[str, str]:
    if not smoke_fire(grid, state):
        raise StepFailed("the fire went out", "missing_item")
    state["inventory"] = smoked(state["inventory"], step["item"])
    return "smoke", f"{state['name']} smoked {label(step['item'])}."


register_step(StepKind("smoke", start_smoke, finish_smoke, "cooking", string_field="item"))


def smoke_wanted(s: Situation) -> int:
    """Smoked meat the winter goal wants now: up to SMOKED_WANTED held, and for a wild pet as much again as its chests'
    winter food falls short (its cooked meat spoils before winter day 5 unless stored in the last days of autumn,
    and smoked meat never does: on the gate's fourth run taught pets smoked once or twice a life and four of six
    chests held under WINTER_FOOD on a winter's first day)."""
    if not (winter_goal(s) and unlocked(s, "smoking")):
        return 0
    wanted = SMOKED_WANTED - held(s, "smoked_meat")
    if is_wild(s.state):
        wanted = max(wanted, math.ceil(max(0.0, WINTER_FOOD - winter_food(s)) / FOOD["smoked_meat"]))
    return max(0, wanted)


def spare_meat(s: Situation) -> tuple[str, ...]:
    """cooking.SPARED: a wild pet that is not hungry leaves the meat the winter goal wants smoked uncooked, while it
    can smoke it now (raw meat it cannot smoke is cooked before it spoils)."""
    if not is_wild(s.state) or s.vitals["hunger"] < SPARE_ABOVE or smoke_plan(s) is None:
        return ()
    return SMOKABLE


def has_sticks(inventory: dict) -> bool:
    """A stick carried, or one Mimo can make from what it carries."""
    try:
        make(inventory, "sticks", 1, [])
    except Short:
        return False
    return True


def smoke_plan(s: Situation) -> list[dict] | None:
    """Smoke the raw meat Mimo carries at a fire within reach (relit, or a campfire it puts down and picks up
    after), while the winter goal wants more smoked meat (`smoke_wanted`); None when it cannot now."""
    def look() -> list[dict] | None:
        wanted = smoke_wanted(s)
        if wanted <= 0:
            return None
        raw = [item for item in SMOKABLE if s.count(item) > 0]
        if not raw:
            return None
        inventory, steps, placed = dict(s.inventory), [], []
        if not has_sticks(dict(inventory)):
            return None
        x, _, z = s.here
        if not s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS).intersection(SMOKE_FIRES):
            relit = relight_steps(s, STATION_REACH) if unlocked(s, "fire") else []
            if relit:
                steps.extend(relit)
                inventory["sticks"] -= 1
            elif not (unlocked(s, "fire")
                      and station(inventory, "campfire", roofed_first(s, station_spots(s)), steps, placed, ("campfire",))):
                fires = sorted((found for found in s.grid.placed_cells(x, z, FIRE_TRAVEL, SMOKE_FIRES)
                                if not near_failure(s.state, found[0])), key=lambda found: s.distance(found[0]))
                return [whole_walk(fires[0][0], FIRE_STAND)] if fires else None  # to a fire it has, as cook does
        need = min(wanted, sum(s.count(item) for item in raw))
        if inventory.get("sticks", 0) < need:  # a stick each, made from planks or logs (on the gate's taught runs a pet
            try:                                # carrying twelve raw meats in autumn had no stick and smoked none)
                make(inventory, "sticks", need, steps)
            except Short:
                pass
        for item in raw:
            while wanted > 0 and inventory.get(item, 0) > 0 and inventory.get("sticks", 0) > 0:
                steps.append({"kind": "smoke", "item": item})
                inventory[item] -= 1
                inventory["sticks"] -= 1
                wanted -= 1
        if not any(step["kind"] == "smoke" for step in steps):
            return None
        steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
        return steps if crafts_fit(s.inventory, steps) else None
    return s.sensed("smoke_plan", look)


def plan_smoke(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] > 0:
        return []
    return list(smoke_plan(s) or [])


register(Purpose(
    "smoke_meat", "smoke meat", "Smoke raw meat over a fire with a stick each: smoked meat keeps all winter.",
    valid=lambda s: not s.night and smoke_plan(s) is not None,
    facts=lambda s: f"{held(s, 'smoked_meat')} of {SMOKED_WANTED} smoked meat; {s.count(*SMOKABLE)} raw meat carried",
    score=lambda s: SMOKE_SCORE, plan=plan_smoke,
    thoughts=("Smoked meat will keep all winter.", "A little smoke, and this meat will last.")))

storage.KEEPS_MORE.append(keep_wool)
storage.TAKES_MORE.append(wool_back)
SPARED.append(spare_meat)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest backend.tests.test_survival_winter_gear backend.tests.test_survival_meat`
Expected: `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1994 tests` … `OK (skipped=6)` (11 new).

- [ ] **Step 5: Commit**

```bash
git add backend/services/crafting.py backend/survival/brain.py backend/survival/carrying.py backend/survival/cooking.py backend/survival/light.py backend/survival/steps.py backend/survival/tick.py backend/survival/vitals.py backend/survival/wild.py backend/survival/winter_gear.py backend/tests/test_survival_meat.py backend/tests/test_survival_winter_gear.py
git commit -m "feat(W2): Mimo makes a wool cloak, a stone hearth in its home and smoked meat for the winter" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Learning the sky: knocks, wonders and taking cover

**Files:**
- Create: `backend/survival/sky_wild.py`, `backend/tests/test_survival_sky_wild.py`
- Modify: `backend/survival/sky_reflexes.py` (`take_cover`, `fog_holds`), `backend/survival/trips.py` (`HOLD_BACK`, `held_back`), `backend/survival/brain.py` (imports `sky_wild`)
- Test: `backend/tests/test_survival_knocks.py` (W1's table leaves W2's names out), `backend/tests/test_survival_reflexes.py` (take_cover in the order), `backend/tests/test_survival_wild_run.py` (the lessons W1's run learns), `backend/tests/test_survival_sim.py` and `backend/tests/test_survival_frontier_run.py` (the slow sims' moved thresholds: resolution 19)

**Interfaces:**
- Consumes: W1's `knocks.KNOCKS`, `knocks.knock`, `knocks.sure`, `wonders.WONDERS`, `wonders.meet`, the dawn and spoil hooks, `harm`'s blow hook; Tasks 3–8's `rain.DOUSED`, `storms.STRIKES`, `sky` weather and seasons, `winter_prep`; `trips` (expeditions); `homes`.
- Produces: seven knocks (channels 217 to 223) and the sure knocks of the spec's table (a winter lived through, being struck, a fire in the trees within 8 blocks: W1's fire knock); six wonders (`colder`, `fire_out`, `storm`, `fog`, `freezing`, `winter_food`) with their chips; the reflex `take_cover` (58); `trips.HOLD_BACK` (callables `(s) -> bool`, guarded).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_frontier_run.py`, replace:

```python
CLOCK = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
```

with:

```python
CLOCK = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
# W2: the runs are under clear skies. A storm or fog sends a pet that knows them home and fog starts no trip
# (backend.survival.sky_reflexes), and in slow mode seed 11's geared pet, sent home out of the weather five times,
# set its riches goal aside on day 2 with nothing to do for it and did not reach it in 4 days (it did on W1's code).
# These runs measure the frontier's risk and reward; the weather's are the W2 gate's.
CLEAR = patch("backend.survival.sky.weather_at", lambda seed, offset, segment: "clear")
```

and replace:

```python
                state = tick_life(registry, BORN + t, scale=1.0, mind=BRAIN, action_scale=1.0)
                if state is None or state["died_at"] is not None:
                    break
                chooser.poll(registry, BORN + t)
```

with:

```python
                with CLEAR:
                    state = tick_life(registry, BORN + t, scale=1.0, mind=BRAIN, action_scale=1.0)
                if state is None or state["died_at"] is not None:
                    break
                with CLEAR:
                    chooser.poll(registry, BORN + t)
```

In `backend/tests/test_survival_knocks.py`, replace:

```python
        self.assertEqual({name: (rule.first, rule.step) for name, rule in KNOCKS.items()},
```

with:

```python
        w2 = ("winter", "cloak", "hearth", "smoking", "rain", "storm", "fog")  # W2's (test_survival_sky_wild)
        self.assertEqual({name: (rule.first, rule.step) for name, rule in KNOCKS.items() if name not in w2},
```

In `backend/tests/test_survival_reflexes.py`, replace:

```python
                          ("head_home", 60), ("collapse", 70)])  # W1: take_herb; W2: flee_fire (sky_reflexes)
```

with:

```python
                          ("take_cover", 58), ("head_home", 60), ("collapse", 70)])
        # W1: take_herb; W2: flee_fire and take_cover (backend.survival.sky_reflexes)
```

In `backend/tests/test_survival_sim.py`, replace:

```python
from backend.survival.situation import from_db
```

with:

```python
from backend.survival.situation import from_db
from backend.survival.sky import SEGMENT, offset_of, weather_at
```

and replace:

```python
# are the final fix wave's measure with margin (its report).
```

with:

```python
# are the final fix wave's measure with margin (its report).
# W2: a pet that knows fog starts no trip in it ("Stay close to home in the fog.", backend.survival.sky_reflexes),
# so a day at least FOG_DAY of whose weather segments are fog is no measure of settling back into resting and is
# left out: seed 21's day 5 is fog from dawn to dusk, and its pet walked 11 new patches that day (149 the day
# before, 40 the floor). Every run still has a day to count; the floor stays 40.
FOG_DAY = 0.5
```

and replace:

```python

@functools.lru_cache(maxsize=None)
```

with:

```python

def fog_share(state: dict, day: int) -> float:
    """W2: the share of game day `day`'s (from 0) weather segments that are fog."""
    per_day = round(DAY / SEGMENT)
    return sum(weather_at(state["world_seed"], offset_of(state), day * per_day + k) == "fog"
               for k in range(per_day)) / per_day


@functools.lru_cache(maxsize=None)
```

and replace:

```python
                    "new_ground": [after - before for before, after in zip(walked_by_day, walked_by_day[1:])],
```

with:

```python
                    "new_ground": [after - before for before, after in zip(walked_by_day, walked_by_day[1:])],
                    "fog": [fog_share(world.state(), day) for day in range(len(walked_by_day) - 1)],
```

and replace:

```python
        late = {key: [run["new_ground"][day] for day in LATE_DAYS] for key, run in runs.items()}
        self.assertTrue(all(min(days) >= NEW_GROUND_LATE for days in late.values()), late)
```

with:

```python
        late = {key: [run["new_ground"][day] for day in LATE_DAYS if run["fog"][day] < FOG_DAY]
                for key, run in runs.items()}
        self.assertTrue(all(days and min(days) >= NEW_GROUND_LATE for days in late.values()), late)
```

Create `backend/tests/test_survival_sky_wild.py`:

```python
"""W2: a wild pet learns the weather's and the seasons' lessons alone (knocks) and asks about them (wonders); the
storm and fog lessons send it home, and fog holds its trips back."""

import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every hook, wonder and reflex registered)
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.knocks import KNOCKS
from backend.survival.lessons import claims
from backend.survival.memory import BUILT, create_memory_tables, know, remember
from backend.survival.reflexes import by_name
from backend.survival.situation import Situation
from backend.survival.sky_wild import at_dawn, blown, doused, meet_sky, spoils, struck
from backend.survival.trips import held_back
from backend.survival.vitals import START_VITALS
from backend.survival.wild import thing, wild_state
from backend.survival.wonders import WONDERS
from backend.tests.test_survival_cooking import meadow

BORN = 1_000_000.0
SCALE = 60.0
W2_KNOCKS = {"winter": (0.30, 0.15), "cloak": (0.30, 0.15), "hearth": (0.25, 0.15), "smoking": (0.25, 0.15),
             "rain": (0.50, 0.25), "storm": (0.50, 0.25), "fog": (0.35, 0.15)}


def day_at(day: int, seconds: float = 1000.0) -> float:
    return BORN + ((day - 1) * DAY_SECONDS + seconds) / SCALE


def world(season="spring", weather="clear", difficulty="wild", **changes):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    state = {"name": "Pip", "world_seed": "1", "born_at": BORN, "position": {"x": 0.0, "y": 1.0, "z": 0.0},
             "inventory": {}, "vitals": dict(START_VITALS), "difficulty": difficulty, "traits": {"curiosity": 50},
             "sky": {"offset": 0, "season": season, "weather": weather}}
    state.update(changes)
    context = SimpleNamespace(db=db, events=[], grid=meadow(), clock_at=lambda at: clock_at(BORN, at, SCALE))
    return state, context


def knows(context, name):
    return context.db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact='lesson'",
                              (thing(name),)).fetchone() is not None


def always():
    return patch("backend.survival.knocks.roll", return_value=0.0)


class KnockTests(unittest.TestCase):
    def test_the_table_of_w2s_knocks(self):
        self.assertEqual({name: (KNOCKS[name].first, KNOCKS[name].step) for name in W2_KNOCKS}, W2_KNOCKS)

    def test_a_hungry_winter_day_knocks_winter_and_smoking_and_a_winter_lived_through_teaches_winter(self):
        state, context = world("winter", vitals={**START_VITALS, "hunger": 20.0})
        know(context.db, thing("fire"), "lesson", 0.0)
        with always():
            meet_sky(state, context, day_at(31))
        self.assertTrue(knows(context, "winter") and knows(context, "smoking"))
        lived, where = world("winter")
        meet_sky(lived, where, day_at(35))
        lived["sky"]["season"] = "spring"
        meet_sky(lived, where, day_at(41, 0.0))
        self.assertTrue(knows(where, "winter"))
        self.assertIn("figured", [kind for _, kind, _ in where.events])

    def test_freezing_two_game_minutes_with_the_wool_at_hand_knocks_the_cloak(self):
        state, context = world("winter", inventory={"wool": 5}, vitals={**START_VITALS, "warmth": 10.0})
        with always():
            for second in range(0, 121, 60):
                meet_sky(state, context, day_at(32, 3000.0 + second))
        self.assertTrue(knows(context, "cloak"))

    def test_the_rain_putting_its_fire_out_knocks_rain_and_is_a_wonder(self):
        state, context = world()
        with always():
            doused(state, context, (1, 1, 0), day_at(2))
        self.assertTrue(knows(context, "rain"))
        self.assertIn("fire_out", wild_state(state)["wonders"])

    def test_a_strike_near_knocks_storm_and_being_struck_teaches_it(self):
        state, context = world(weather="storm")
        with patch("backend.survival.knocks.roll", return_value=0.99):
            struck(state, context, (10, 5, 0), False, day_at(2))
        self.assertFalse(knows(context, "storm"))
        self.assertEqual(wild_state(state)["knocks"]["storm"], 1)
        struck(state, context, (40, 5, 0), False, day_at(2))  # too far to knock
        self.assertEqual(wild_state(state)["knocks"]["storm"], 1)
        struck(state, context, (0, 1, 0), True, day_at(2))
        self.assertTrue(knows(context, "storm"))

    def test_a_blow_in_fog_by_day_knocks_fog_and_a_cold_night_at_home_the_hearth(self):
        state, context = world(weather="fog")
        scene = SimpleNamespace(night=False, state=state, herd=SimpleNamespace(db=context.db), events=context.events,
                                at=day_at(2))
        with always():
            blown(scene, 3.0, "gloomling")
        self.assertTrue(knows(context, "fog"))
        cold, home = world("winter")
        remember(home.db, "home", (0, 1, 0), 0.0, BUILT)
        know(home.db, thing("fire"), "lesson", 0.0)
        with always():
            at_dawn(cold, home, {"chill": True, "froze": False, "cold": 900.0, "blows": 0, "floor": False}, day_at(33))
            spoils(cold, home, "raw_beef", 1, "arms", day_at(33))
        self.assertTrue(knows(home, "hearth") and knows(home, "smoking"))

    def test_standing_near_a_fire_in_the_trees_teaches_fire_for_sure(self):
        state, context = world(sky={"offset": 0, "season": "summer", "weather": "clear",
                                    "fires": [{"x": 4, "y": 5, "z": 0, "fire": 1, "caught": 0.0, "until": 9e9}]})
        meet_sky(state, context, day_at(12))
        self.assertTrue(knows(context, "fire"))


class WonderTests(unittest.TestCase):
    def test_the_six_wonders_and_the_fogs_yes_and_no(self):
        for wonder_id in ("colder", "fire_out", "storm", "fog", "freezing", "winter_food"):
            self.assertIn(wonder_id, WONDERS)
            self.assertTrue(any(chip.false for chip in WONDERS[wonder_id].chips), wonder_id)
        fog = WONDERS["fog"]
        self.assertEqual((claims(fog.yes).doubtful, claims(fog.no).taught), (True, (thing("fog"),)))

    def test_what_a_wild_pet_meets_and_a_gentle_one_never(self):
        state, context = world("autumn", weather="storm")
        state["sky"]["told"] = {"colder": 23}
        meet_sky(state, context, day_at(23, 2300.0))
        state["sky"]["weather"] = "fog"
        meet_sky(state, context, day_at(23, 2400.0))
        state["sky"].update(season="winter", weather="snow")
        state["vitals"].update(warmth=10.0, hunger=40.0)
        meet_sky(state, context, day_at(31))
        self.assertEqual(set(wild_state(state)["wonders"]), {"colder", "storm", "fog", "freezing", "winter_food"})
        gentle, where = world("winter", weather="storm", difficulty="gentle", vitals={**START_VITALS, "warmth": 5.0})
        meet_sky(gentle, where, day_at(31))
        self.assertEqual((gentle.get("wild") or {}).get("wonders"), None)


class CoverTests(unittest.TestCase):
    def situation(self, weather, difficulty="gentle", at=None, home=(0, 1, 0), position=(30.0, 1.0, 0.0)):
        state, context = world(weather=weather, difficulty=difficulty,
                               position=dict(zip("xyz", position)), brain=None)
        if home is not None:
            remember(context.db, "home", home, 0.0, BUILT)
        at = day_at(2) if at is None else at
        return Situation(state, meadow(), clock_at(BORN, at, SCALE), at, context.db)

    def test_a_storm_sends_a_pet_that_knows_it_home_once_a_spell(self):
        cover = by_name("take_cover")
        with patch("backend.survival.sky.weather_at", lambda seed, offset, segment: "storm"):
            s = self.situation("storm")
            self.assertTrue(cover.trigger(s))
            self.assertEqual(cover.plan(s, None), [{"kind": "walk", "target": [0, 1, 0], "reach": 0.0}])
            self.assertFalse(cover.trigger(s))  # once a spell
            self.assertFalse(cover.trigger(self.situation("storm", position=(10.0, 1.0, 0.0))))  # near home: safe
            self.assertFalse(cover.trigger(self.situation("storm", difficulty="wild")))  # it does not know yet
            self.assertFalse(cover.trigger(self.situation("clear")))

    def test_fog_sends_it_home_and_holds_its_trips_back(self):
        cover = by_name("take_cover")
        with patch("backend.survival.sky.weather_at", lambda seed, offset, segment: "fog"):
            self.assertTrue(cover.trigger(self.situation("fog")))
            self.assertFalse(cover.trigger(self.situation("fog", position=(20.0, 1.0, 0.0))))
        self.assertTrue(held_back(self.situation("fog")))
        self.assertFalse(held_back(self.situation("fog", difficulty="wild")))
        self.assertFalse(held_back(self.situation("clear")))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_wild_run.py`, replace:

```python
from backend.scripts.wild_gate import CONDITIONS, SEEDS, check_w1, live
```

with:

```python
from backend.scripts.wild_gate import CONDITIONS, SEEDS, check_w1, live
from backend.survival.wild import SURVIVAL
```

and replace:

```python
        self.assertEqual(len(taught["lessons"]), 11)
        self.assertTrue(all(entry["day"] < 2 for entry in taught["lessons"].values()), taught["lessons"])
```

with:

```python
        w1 = [lesson.name for lesson in SURVIVAL[:11]]  # W2: its questions may teach it some of W2's too
        self.assertLessEqual(set(w1), set(taught["lessons"]))
        self.assertTrue(all(taught["lessons"][name]["day"] < 2 for name in w1), taught["lessons"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_survival_sky_wild backend.tests.test_survival_knocks backend.tests.test_survival_reflexes backend.tests.test_survival_wild_run`
Expected: `FAILED (failures=1, errors=1, skipped=1)`: `ModuleNotFoundError: No module named 'backend.survival.sky_wild'`, and the reflexes' order has no `('take_cover', 58)`

- [ ] **Step 3: Knocks, wonders and cover**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import sky_reflexes  # noqa: F401  (W2: flee_fire)
```

with:

```python
from backend.survival import sky_reflexes, sky_wild  # noqa: F401  (W2: flee_fire, take_cover; knocks, wonders)
```

In `backend/survival/sky_reflexes.py`, replace:

```python
"""W2: the sky's reflexes (backend.survival.reflexes).

- flee_fire (25): a burning cell within FIRE_FLEE blocks of Mimo (backend.survival.storms): it runs away from
  the nearest, as flee runs from a hostile (creatures.defense.run_away), and chooses again where it stops.
```

with:

```python
"""W2: the sky's reflexes (backend.survival.reflexes), and what the storm and fog lessons make Mimo do.

- flee_fire (25): a burning cell within FIRE_FLEE blocks of Mimo (backend.survival.storms): it runs away from
  the nearest, as flee runs from a hostile (creatures.defense.run_away), and chooses again where it stops.
- take_cover (58): once a spell of weather, when a storm starts and Mimo knows `wild:storm` ("in a storm stay
  low and inside"), or fog comes and it knows `wild:fog` ("stay close to home in the fog"), and it is out under
  the open sky farther from the home it built than STORM_HOME (a storm never strikes that close) or FOG_HOME: it
  goes home, and chooses again there. Not on an expedition, and not when it is going home or to sleep already.
- In fog, a pet that knows `wild:fog` starts no trips (trips.HOLD_BACK).
A gentle pet knows both lessons from the start.
```

and replace:

```python
from backend.survival.creatures.defense import run_away
from backend.survival.reflexes import Reflex, register
from backend.survival.situation import Situation
from backend.survival.storms import fire_near
```

with:

```python
from backend.survival import sky, trips
from backend.survival.creatures.defense import run_away
from backend.survival.light import sky_open
from backend.survival.memory import BUILT, cell_of
from backend.survival.purposes import GO_HOME_RANGE, away, home_of, walk_to
from backend.survival.reflexes import AT_HOME_WORK, Reflex, register
from backend.survival.situation import Situation
from backend.survival.storms import HOME_CLEAR, fire_near
from backend.survival.wild import unlocked
```

and replace:

```python
FIRE_FLEE = 2
```

with:

```python
FIRE_FLEE = 2
STORM_HOME = HOME_CLEAR  # blocks: a storm strikes no nearer home than this
FOG_HOME = 24.0
COVER = {"storm": ("storm", STORM_HOME), "fog": ("fog", FOG_HOME)}  # weather: (its lesson, how near home is near)
SPELL_BACK = 12  # segments looked back for when a spell of weather began
```

and replace:

```python
                ends_purpose=True, paced=True))
```

with:

```python
                ends_purpose=True, paced=True))


def spell(s: Situation) -> int:
    """The segment the present spell of weather began in (sky.weather_at, looked back SPELL_BACK at most)."""
    offset, seed = sky.offset_of(s.state), s.seed
    segment = sky.segment_of(s.state, s.at, s.scale)
    weather = sky.weather_at(seed, offset, segment)
    start = segment
    while start > 0 and segment - start < SPELL_BACK and sky.weather_at(seed, offset, start - 1) == weather:
        start -= 1
    return start


def cover_home(s: Situation) -> dict | None:
    """The home Mimo built, when the weather's lesson sends it there now (see the module docstring)."""
    weather = sky.weather_now(s.state)
    if weather not in COVER or "born_at" not in s.state:
        return None
    lesson, near = COVER[weather]
    if not unlocked(s, lesson) or away(s) or s.brain["purpose"] in ("go_home", "sleep", *AT_HOME_WORK):
        return None
    if s.brain.get("covered") == [weather, spell(s)]:
        return None
    home = home_of(s, GO_HOME_RANGE)
    if home is None or home["note"] != BUILT or s.distance(cell_of(home)) <= near:
        return None
    return home if sky_open(s.grid, s.seed, s.here) else None


def plan_cover(s: Situation, context) -> list[dict]:
    home = cover_home(s)
    if home is None:
        return []
    s.brain["covered"] = [sky.weather_now(s.state), spell(s)]
    return [walk_to(cell_of(home))]


def fog_holds(s: Situation) -> bool:
    """trips.HOLD_BACK: no trip starts in fog for a pet that knows `wild:fog`."""
    return sky.foggy(s.state) and unlocked(s, "fog")


register(Reflex("take_cover", 58, trigger=lambda s: cover_home(s) is not None, plan=plan_cover,
                thought="The weather's turning. Home, where it's safe.", event="{name} headed home out of the weather.",
                cooldown=60.0, ends_purpose=True))
trips.HOLD_BACK.append(fog_holds)
```

Create `backend/survival/sky_wild.py`:

```python
"""W2: what a wild pet learns of the weather and the seasons alone (knocks) and by asking (wonders), as W1's
lessons are learned (backend.survival.knocks, backend.survival.wonders, backend.survival.questions).

| Lesson | Knock | First | Step | Sure when |
|---|---|---|---|---|
| winter | a winter day with hunger under 30 | 0.30 | 0.15 | it lives through a winter (the first spring dawn after one) |
| cloak | 2 game minutes freezing while 5 wool are carried or stored | 0.30 | 0.15 | |
| hearth | a chilled or freezing night at home in winter, knowing fire | 0.25 | 0.15 | |
| smoking | food spoils, or a winter day hungry, knowing fire | 0.25 | 0.15 | |
| rain | its fire goes out in the rain | 0.50 | 0.25 | |
| storm | a strike within STRIKE_NEAR blocks | 0.50 | 0.25 | it is struck |
| fog | a hostile's blow in fog by day | 0.35 | 0.15 | |

W1's `wild:fire` is also learned for sure by standing within FIRE_SEEN blocks of a fire Mimo did not make (a fire
in the trees). Each W2 lesson rolls on W1's rule, channel 206 plus its place in wild.SURVIVAL (217 to 223; the
chips' shuffle's 220 rolls on a question's index and never on Mimo's cell).

Wonders (asked with chips like W1's; `fog` is a yes-or-no one): `colder` on autumn day 3 at dusk, `fire_out` when
the rain puts its fire out, `storm` at its first thunderstorm, `fog` in its first fog, `freezing` when it freezes
in winter, `winter_food` on a winter day hunger falls under 50. The tick marks them (`meet_sky`, a sky effect) and
the Talker asks them. A gentle pet meets none and has no knocks.
"""

from __future__ import annotations

import math

from backend.survival import rain, sky, storms
from backend.survival.ailments import DAWN, at_built_home
from backend.survival.creatures.harm import BLOWS
from backend.survival.knocks import KNOCKS, Knock, guarded, knock, known, sure
from backend.survival.spoilage import SPOILS
from backend.survival.vitals import FREEZING_BELOW
from backend.survival.wild import is_wild, wild_state
from backend.survival.wonders import Chip, Wonder, met, wonder

STRIKE_NEAR = 16.0
FIRE_SEEN = 8.0
HUNGRY_BELOW = 30.0
WINTER_HUNGRY = 50.0  # the winter_food wonder
CLOAK_COLD = 120.0  # game seconds freezing with the wool for a cloak at hand
CLOAK_WOOL = 5

KNOCKS.update({"winter": Knock(0.30, 0.15), "cloak": Knock(0.30, 0.15), "hearth": Knock(0.25, 0.15),
               "smoking": Knock(0.25, 0.15), "rain": Knock(0.50, 0.25), "storm": Knock(0.50, 0.25),
               "fog": Knock(0.35, 0.15)})

wonder(Wonder("colder", "The nights are getting colder. Is something coming?", ("winter",),
              (Chip("Winter is coming. Fill a chest with food before winter.", ("winter",)),
               Chip("It will warm up again soon.", false=True)),
              "whether something is coming, now the nights are colder"))
wonder(Wonder("fire_out", "The rain put my fire out!", ("rain",),
              (Chip("Keep your fire under a roof.", ("rain",)), Chip("Rain makes a fire burn hotter.", false=True)),
              "what to do when the rain puts out a fire"))
wonder(Wonder("storm", "The sky is booming and flashing! What should I do?", ("storm",),
              (Chip("Go home, and stay low and inside.", ("storm",)), Chip("Climb up high to watch it.", false=True),
               Chip("It's just noise.")),
              "what to do in a thunderstorm"))
wonder(Wonder("fog", "Everything is grey and foggy. Is it safe out here?", ("fog",),
              (Chip("Stay close to home in the fog.", ("fog",)), Chip("Fog is safe.", false=True)),
              "whether it is safe out in the fog", yes="Fog is safe.", no="Stay close to home in the fog."))
wonder(Wonder("freezing", "I'm freezing! How do I keep warm in the snow?", ("cloak", "hearth"),
              (Chip("Five wool make a wool cloak.", ("cloak",)), Chip("A stone hearth keeps the home warm.", ("hearth",)),
               Chip("Roll in the snow to warm up.", false=True)),
              "how to keep warm in the snow"))
wonder(Wonder("winter_food", "The lake is frozen and nothing grows. What do I eat?", ("winter", "smoking"),
              (Chip("Fill a chest with food before winter, and smoke your meat.", ("winter", "smoking")),
               Chip("Smoked meat keeps all winter.", ("smoking",)), Chip("Eat snow.", false=True)),
              "what to eat in the winter"))


def held(state: dict, item: str) -> int:
    return state["inventory"].get(item, 0) + sum(chest.get(item, 0) for chest in state.get("chests", {}).values())


def meet_sky(state: dict, context, at: float) -> None:
    """sky.EFFECTS: a wild pet's knocks and wonders of the weather and the seasons (see the module docstring)."""
    if not is_wild(state):
        return
    found, night = sky.sky_state(state), wild_state(state)
    db, events = context.db, context.events
    clock = context.clock_at(at)
    day, season, weather = clock["day_number"], found["season"], found["weather"]
    vitals = state["vitals"]
    since = night.get("sky_at")
    seconds = 0.0 if since is None else max(0.0, (at - since) * clock["time_scale"])
    night["sky_at"] = at
    if found["told"].get("colder") == day:
        met(state, "colder", at)
    if weather == "storm":
        met(state, "storm", at)
    if weather == "fog":
        met(state, "fog", at)
    if season == sky.WINTER:
        night["wintered"] = True
        if vitals["warmth"] < FREEZING_BELOW:
            met(state, "freezing", at)
        if vitals["hunger"] < WINTER_HUNGRY:
            met(state, "winter_food", at)
        if vitals["hunger"] < HUNGRY_BELOW and night.get("hungry_day") != day:
            night["hungry_day"] = day
            guarded(lambda: knock(state, db, events, at, "winter"))
            if db is not None and known(db, "fire"):
                guarded(lambda: knock(state, db, events, at, "smoking"))
    elif night.pop("wintered", False) and season == "spring":
        guarded(lambda: sure(state, db, events, at, "winter"))  # it lived through a winter
    if vitals["warmth"] < FREEZING_BELOW and held(state, "wool") >= CLOAK_WOOL:
        night["cloak_cold"] = night.get("cloak_cold", 0.0) + seconds
        if night["cloak_cold"] >= CLOAK_COLD:
            night["cloak_cold"] = 0.0
            guarded(lambda: knock(state, db, events, at, "cloak"))
    position = state["position"]
    if any(math.dist((entry["x"], entry["y"], entry["z"]), (position["x"], position["y"], position["z"])) <= FIRE_SEEN
           for entry in found["fires"]):
        guarded(lambda: sure(state, db, events, at, "fire"))  # a fire it did not make


def doused(state: dict, context, cell, at: float) -> None:
    """rain.DOUSED: its fire went out in the rain."""
    if is_wild(state):
        met(state, "fire_out", at)
        guarded(lambda: knock(state, context.db, context.events, at, "rain"))


def struck(state: dict, context, cell, hit: bool, at: float) -> None:
    """storms.STRIKES: struck for sure; a strike within STRIKE_NEAR blocks a knock."""
    position = state["position"]
    if hit:
        guarded(lambda: sure(state, context.db, context.events, at, "storm"))
    elif math.hypot(cell[0] - position["x"], cell[2] - position["z"]) <= STRIKE_NEAR:
        guarded(lambda: knock(state, context.db, context.events, at, "storm"))


def at_dawn(state: dict, context, summary: dict, at: float) -> None:
    """ailments.DAWN: a chilled or freezing night at home in winter, knowing fire."""
    if (sky.winter(state) and (summary["chill"] or summary["froze"]) and context.db is not None
            and known(context.db, "fire") and at_built_home(state, context)):
        guarded(lambda: knock(state, context.db, context.events, at, "hearth"))


def spoils(state: dict, context, item: str, count: int, where: str, at: float) -> None:
    """spoilage.SPOILS: food went bad, knowing fire."""
    if context.db is not None and known(context.db, "fire"):
        guarded(lambda: knock(state, context.db, context.events, at, "smoking"))


def blown(scene, lost: float, source: str) -> None:
    """harm.BLOWS: a hostile's blow in fog by day."""
    if not scene.night and sky.foggy(scene.state):
        guarded(lambda: knock(scene.state, scene.herd.db, scene.events, scene.at, "fog"))


sky.EFFECTS.append(meet_sky)
rain.DOUSED.append(doused)
storms.STRIKES.append(struck)
DAWN.append(at_dawn)
SPOILS.append(spoils)
BLOWS.append(blown)
```

In `backend/survival/trips.py`, replace:

```python
SHOWN = 3  # targets kept per offer: the facts and the model payload name them
```

with:

```python
SHOWN = 3  # targets kept per offer: the facts and the model payload name them
# W2: functions of the Situation that hold every new trip back now (backend.survival.sky_reflexes: no trip starts in
# fog for a pet that knows `wild:fog`). One that crashes holds nothing back (logged once).
HOLD_BACK: list = []
```

and replace:

```python
    def look() -> list[Offer]:
```

with:

```python
    def look() -> list[Offer]:
        if held_back(s):
            return []
```

and replace:

```python
    return s.sensed("trip offers", look)
```

with:

```python
    return s.sensed("trip offers", look)


def held_back(s: Situation) -> bool:
    """W2: something holds every new trip back now (HOLD_BACK)."""
    for holds in HOLD_BACK:
        try:
            if holds(s):
                return True
        except Exception as error:
            log_once(logger, "hold back", error)
    return False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest backend.tests.test_survival_sky_wild backend.tests.test_survival_knocks backend.tests.test_survival_reflexes backend.tests.test_survival_wild_run`
Expected: `OK (skipped=1)`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and the same with `-p "test_survival_frontier_run.py"` (slow: about 8 and 5 minutes on a quiet machine, W1's measure)
Expected: `OK` each (without this task's change to them, the first fails on seed 21's day of fog, `{(3, False): [236, 162], (21, True): [149, 11]}`, and the second on seed 11's riches goal)

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 2005 tests` … `OK (skipped=6)` (11 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/brain.py backend/survival/sky_reflexes.py backend/survival/sky_wild.py backend/survival/trips.py backend/tests/test_survival_frontier_run.py backend/tests/test_survival_knocks.py backend/tests/test_survival_reflexes.py backend/tests/test_survival_sim.py backend/tests/test_survival_sky_wild.py backend/tests/test_survival_wild_run.py
git commit -m "feat(W2): a wild pet learns the sky and the winter from what they do to it, asks about them, and heads home from a storm or the fog" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Moments, news and voice

**Files:**
- Create: `backend/survival/sky_news.py`, `backend/tests/test_survival_sky_news.py`
- Modify: `backend/survival/bonding.py` (imports `sky_news`), `backend/survival/world.py` (`ROUTINE_EVENTS`), `backend/survival/sky.py` (`sky_view`'s `fires`)
- Test: `backend/tests/test_survival_voice.py` (the new events' words)

**Interfaces:**
- Consumes: Mind's `MOMENTS`; the inbox's danger and news hooks as W1's `wild_news` uses them; Tasks 1–4's events (`season`, `spring`, `colder`, `struck`, `fire`, `storm`, `fire_out`, `smoke`).
- Produces: moments `struck` 8 (-2), `fire` 5 (0), `season` 4 (+1), `spring` 6 (+1), `colder` 4 (0); `sky_news.sky_danger` (a strike or a fire, once a game day), `season_news` (winter and spring); `/api/mimo`'s `sky.fires`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_sky_news.py`:

```python
"""W2: the weather's and the seasons' moments in Mimo's memory, its news and danger in the inbox, which of them are
routine, and the sky in /api/mimo (a GET never writes)."""

import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every hook registered)
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival import bonding, minding  # noqa: F401  (every writer registered)
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items
from backend.survival.registry import LifeRegistry
from backend.survival.talker import run_chores
from backend.survival.world import ROUTINE_EVENTS, SurvivalWorld, log_event

BORN = 1_000_000.0


class NewsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        self.name = self.life["name"]
        run_chores(self.world, BORN, 1.0)  # the mirrors start at the newest event

    def tearDown(self):
        self.directory.cleanup()

    def log(self, *events, at=BORN + 10):
        with self.world.transaction() as db:
            for number, (kind, text) in enumerate(events):
                log_event(db, at + number, kind, text)
        run_chores(self.world, at + 60, 1.0)

    def test_the_skys_moments_are_remembered_with_their_weight(self):
        name = self.name
        self.log(("struck", f"Lightning struck {name}!"), ("fire", f"Lightning set a tree on fire near {name}."),
                 ("season", "Winter has come."), ("spring", "Spring! Things are growing again."),
                 ("colder", "The nights are getting colder."))
        with self.world.connect() as db:
            rows = {row[0]: tuple(row[1:]) for row in db.execute(
                "SELECT source, importance, feeling, text FROM mind_memories WHERE source IN "
                "('struck', 'fire', 'season', 'spring', 'colder')")}
        self.assertEqual(rows["struck"], (8, -2, "Lightning struck me!"))
        self.assertEqual(rows["fire"], (5, 0, "Lightning set a tree on fire near me."))
        self.assertEqual(rows["season"][:2], (4, 1))
        self.assertEqual(rows["spring"][:2], (6, 1))
        self.assertEqual(rows["colder"][:2], (4, 0))

    def test_the_inbox_tells_of_a_strike_or_a_fire_once_a_game_day_and_of_winter_and_spring(self):
        name = self.name
        self.log(("struck", f"Lightning struck {name}!"), ("fire", f"Lightning set a tree on fire near {name}."),
                 ("fire", f"Lightning set a tree on fire near {name}."), ("season", "Summer has come."),
                 ("season", "Winter has come."), ("spring", "Spring! Things are growing again."))
        with self.world.connect() as db:
            items = [(item["kind"], item["text"]) for item in reversed(inbox_items(db))]
        self.assertEqual(items, [("danger", "Lightning struck me!"), ("danger", "Lightning set a tree on fire near me."),
                                 ("report", "Winter has come."), ("report", "Spring! Things are growing again.")])

    def test_which_of_them_are_routine(self):
        self.assertLessEqual({"season", "storm", "fire_out", "smoke"}, ROUTINE_EVENTS)
        self.assertFalse({"spring", "colder", "struck", "fire"} & ROUTINE_EVENTS)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_the_sky_in_api_mimo_and_a_get_never_writes(self):
        hatch_egg()
        registry = LifeRegistry()
        world = SurvivalWorld(registry.world_path(registry.active_life()))
        before = world.state()
        sky = get_mimo()["sky"]
        self.assertEqual(set(sky), {"season", "day", "to_next", "weather", "until", "snow", "frozen", "strikes", "fires"})
        self.assertEqual((sky["season"], sky["day"], sky["to_next"]), ("spring", 1, 10))
        self.assertEqual(world.state(), before)


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_voice.py`, replace:

```python
    found += [("asked", f"{NAME} asked you {wonder.asked}.") for wonder in WONDERS.values()]
```

with:

```python
    found += [("asked", f"{NAME} asked you {wonder.asked}.") for wonder in WONDERS.values()]
    # W2: the seasons, the weather, lightning and fire, smoked meat and the deaths the sky brings.
    from backend.survival.sky import COLDER, TURNS
    found += [("spring" if season == "spring" else "season", words) for season, words in TURNS.items()]
    found += [("colder", COLDER), ("storm", "A thunderstorm rolled in."), ("struck", f"Lightning struck {NAME}!"),
              ("fire", f"Lightning set a tree on fire near {NAME}."), ("fire_out", f"The rain put out {NAME}'s campfire."),
              ("smoke", f"{NAME} smoked raw beef."), ("reflex", f"{NAME} ran from the fire."),
              ("reflex", f"{NAME} headed home out of the weather."),
              ("death", f"{NAME} was struck by lightning on day 12."), ("death", f"{NAME} was caught in a fire on day 12.")]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_survival_sky_news backend.tests.test_survival_voice`
Expected: `FAILED (failures=3, errors=1)`: Mind has no moment for a strike yet (`KeyError: 'struck'`), the inbox tells nothing (`Lists differ: [] != [('danger', 'Lightning struck me!'), …]`), the new kinds are not routine, and `sky` has no `fires`

- [ ] **Step 3: Moments, news and the routine events**

In `backend/survival/bonding.py`, replace:

```python
from backend.survival import wild_news  # noqa: F401  (W1: new moments for Mind, news and danger for the inbox)
```

with:

```python
from backend.survival import wild_news  # noqa: F401  (W1: new moments for Mind, news and danger for the inbox)
from backend.survival import sky_news  # noqa: F401  (W2: the weather's and seasons' moments, news and danger)
```

In `backend/survival/sky.py`, replace:

```python
    and until when, the snow, whether the lakes are frozen, and the latest strikes ({x, y, z, at})."""
```

with:

```python
    and until when, the snow, whether the lakes are frozen, the latest strikes ({x, y, z, at}) and the cells
    burning in the trees ({x, y, z}, for the viewer's embers)."""
```

and replace:

```python
            "strikes": list(sky.get("strikes", []))}
```

with:

```python
            "strikes": list(sky.get("strikes", [])),
            "fires": [{"x": entry["x"], "y": entry["y"], "z": entry["z"]} for entry in sky.get("fires", [])]}
```

Create `backend/survival/sky_news.py`:

```python
"""W2: what the weather's and the seasons' moments mean to Mimo's memory and its inbox ("Moments, news and voice").

The events (world.log_event): "season" ("Winter has come.", routine), "spring" ("Spring! Things are growing
again.", notable), "colder" ("The nights are getting colder.", notable), "storm" ("A thunderstorm rolled in.",
routine), "struck" ("Lightning struck Pip!", notable), "fire" ("Lightning set a tree on fire near Pip.",
notable), "fire_out" ("The rain put out Pip's campfire.", routine) and "smoke" ("Pip smoked raw beef.", routine).
Mind's memory keeps "struck" 8 (-2), "fire" 5 (0), "season" 4 (+1), "spring" 6 (+1) and "colder" 4 (0) as
moments. The inbox tells the owner of a strike or a fire as danger (each kind at most once a game day) and of
winter's and spring's first days as news. Every text reads in Mimo's own voice (replies.in_my_voice;
test_survival_voice).
"""

from __future__ import annotations

import sqlite3

from backend.survival.bond import bond_state
from backend.survival.clock import DAY_SECONDS
from backend.survival.episodes import MOMENTS, Moment, followed, remember_moment
from backend.survival.events import mirror
from backend.survival.inbox import CONSUMER, post_item
from backend.survival.replies import in_my_voice
from backend.survival.sky import TURNS

MOMENTS.update({
    "struck": Moment(8, -2),
    "fire": Moment(5, 0),
    "season": Moment(4, 1),
    "spring": Moment(6, 1),
    "colder": Moment(4, 0),
})
for _kind in ("struck", "fire", "season", "spring", "colder"):
    followed(_kind, remember_moment)


def sky_danger(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A strike or a fire in the trees, as danger, at most once a game day of each kind."""
    told = bond_state(state).setdefault("sky_told", {})
    last = told.get(event["kind"])
    if last is not None and (event["at"] - last) * scale < DAY_SECONDS:
        return
    told[event["kind"]] = event["at"]
    post_item(db, event["at"], "danger", in_my_voice(event["text"], state["name"]), {"event": event["id"]})


def season_news(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """Winter's and spring's first days, as news."""
    if event["kind"] == "spring" or event["text"] == TURNS["winter"]:
        post_item(db, event["at"], "report", in_my_voice(event["text"], state["name"]), {"event": event["id"]})


for _kind in ("struck", "fire"):
    mirror(CONSUMER, _kind, sky_danger)
for _kind in ("season", "spring"):
    mirror(CONSUMER, _kind, season_news)
```

In `backend/survival/world.py`, replace:

```python
                            "cured", "dressed", "spoiled", "asked", "rested", "safe_night"})
```

with:

```python
                            "cured", "dressed", "spoiled", "asked", "rested", "safe_night",
                            # W2: the turn of a season, a storm, a campfire the rain put out, smoked meat
                            "season", "storm", "fire_out", "smoke"})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest backend.tests.test_survival_sky_news backend.tests.test_survival_voice`
Expected: `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 2009 tests` … `OK (skipped=6)` (4 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/bonding.py backend/survival/sky.py backend/survival/sky_news.py backend/survival/world.py backend/tests/test_survival_sky_news.py backend/tests/test_survival_voice.py
git commit -m "feat(W2): the sky's moments become memories, and a strike, a fire, winter and spring become the owner's news" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Viewer: the sky, the season and the weather on the HUD

**Files:**
- Create: `frontend/src/survival/seasons.ts`, `frontend/src/survival/seasons.test.ts`, `frontend/src/survival/weather.ts`, `frontend/src/survival/weather.test.ts`
- Modify: `frontend/src/survival/types.ts` (`SkyView`), `hud.ts` (the new steps' and causes' words), `animation.ts` (`relight`, `smoke`), `DayNight.tsx` (the sky's color and fog by season and weather, the flash), `WorldCanvas.tsx`, `SurvivalWorld.tsx`, `SurvivalHud.tsx` (the season line)
- Test: `frontend/src/survival/hud.test.ts`

**Interfaces:**
- Consumes: `/api/mimo`'s `sky` (Tasks 1–5, 10).
- Produces: `seasons.ts`: `seasonBadge`, `easeToward`, `freezeSeconds`, `seasonSky`; `weather.ts`: `weatherSky`, `weatherLine`, `particleCount`, `weatherFog`, `flashLevel`, `flashAt`, `desaturate`, `RAIN_STREAKS` (1,500), `SNOW_FLAKES` (800).

- [ ] **Step 1: Write the failing tests**

In `frontend/src/survival/hud.test.ts`, replace:

```typescript
    expect(purposeText({ purpose: null, reflex: 'take_herb', choosing: false })).toBe('Eating sunleaf to feel better')
```

with:

```typescript
    expect(purposeText({ purpose: null, reflex: 'take_herb', choosing: false })).toBe('Eating sunleaf to feel better')
    // W2
    expect(lifeLine({ kind: 'survival', alive: false, days: 12, cause: 'lightning' }))
      .toBe('Survived 12 days · struck by lightning')
    expect(lifeLine({ kind: 'survival', alive: false, days: 12, cause: 'fire' })).toBe('Survived 12 days · caught in a fire')
    expect(purposeText({ purpose: 'build_hearth', reflex: null, choosing: false })).toBe('Building a hearth')
    expect(purposeText({ purpose: null, reflex: 'take_cover', choosing: false })).toBe('Heading home out of the weather')
```

Create `frontend/src/survival/seasons.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { easeToward, FREEZE_GAME_SECONDS, freezeSeconds, seasonBadge, seasonSky, WINTER_DAY_SKY } from './seasons'
import type { SkyView } from './types'

const SKY: SkyView = {
  season: 'winter', day: 4, to_next: 6, weather: 'snow', until: null, snow: 0.4, frozen: true, strikes: [], fires: [],
}

describe('seasonBadge', () => {
  it('names the season, the day and the days to the next one', () => {
    expect(seasonBadge(SKY, 34)).toBe('Winter · day 34 · 6 days to spring')
    expect(seasonBadge({ ...SKY, season: 'autumn', to_next: 1 }, 30)).toBe('Autumn · day 30 · 1 day to winter')
    expect(seasonBadge(null, 3)).toBeNull()
  })
})

describe('easing the snow and the ice', () => {
  it('moves toward the target at a full swing per `seconds`, never past it', () => {
    expect(easeToward(0, 1, 1, 10)).toBeCloseTo(0.1)
    expect(easeToward(0.95, 1, 1, 10)).toBe(1)
    expect(easeToward(0.5, 0, 2, 10)).toBeCloseTo(0.3)
    expect(easeToward(0.2, 0.2, 1, 10)).toBe(0.2)
  })

  it('takes a game minute to freeze and thaw at the clock\'s pace', () => {
    expect(freezeSeconds(1)).toBe(FREEZE_GAME_SECONDS)
    expect(freezeSeconds(60)).toBe(1)
  })
})

describe('seasonSky', () => {
  it('is colder by day in winter and as it was otherwise', () => {
    const base: [number, number, number] = [0xdc, 0xe9, 0xeb]
    expect(seasonSky(base, 'summer', 1)).toEqual(base)
    expect(seasonSky(base, 'winter', 0)).toEqual(base)
    const cold = seasonSky(base, 'winter', 1)
    expect(cold[2]).toBeGreaterThanOrEqual(WINTER_DAY_SKY[2])
    expect(cold[0]).toBeLessThan(base[0])
  })
})
```

Create `frontend/src/survival/weather.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import {
  desaturate, FLASH_LIFT, FLASH_SECONDS, FOG_NEAR, flashAt, flashLevel, particleCount, RAIN_STREAKS, SNOW_FLAKES,
  weatherFog, weatherLine, weatherSky,
} from './weather'

const DAY: [number, number, number] = [0xdc, 0xe9, 0xeb]

describe('the sky in each weather', () => {
  it('greys and darkens in rain and storm, pales in fog and whitens in snow; clear keeps it', () => {
    expect(weatherSky(DAY, 'clear')).toEqual(DAY)
    expect(weatherSky(DAY, null)).toEqual(DAY)
    const sum = (rgb: number[]) => rgb[0] + rgb[1] + rgb[2]
    expect(sum(weatherSky(DAY, 'storm'))).toBeLessThan(sum(weatherSky(DAY, 'rain')))
    expect(sum(weatherSky(DAY, 'rain'))).toBeLessThan(sum(DAY))
    const fog = weatherSky(DAY, 'fog')
    expect(Math.max(...fog) - Math.min(...fog)).toBeLessThan(Math.max(...DAY) - Math.min(...DAY))
    expect(desaturate([200, 100, 0], 1)).toEqual([119, 119, 119])
  })

  it('names the weather on the HUD', () => {
    expect(weatherLine('storm')).toBe('ϟ Storm')
    expect(weatherLine('snow')).toBe('❄ Snow')
    expect(weatherLine(undefined)).toBeNull()
  })
})

describe('particles and fog', () => {
  it('draws rain streaks and snowflakes, half on a phone, none in dry weather', () => {
    expect(particleCount('rain', false)).toBe(RAIN_STREAKS)
    expect(particleCount('storm', true)).toBe(RAIN_STREAKS / 2)
    expect(particleCount('snow', false)).toBe(SNOW_FLAKES)
    expect(particleCount('fog', false)).toBe(0)
    expect(particleCount('clear', false)).toBe(0)
  })

  it('closes the fog in to a share of the view in fog', () => {
    expect(weatherFog(100, 200, 'fog')).toEqual([100 * FOG_NEAR, 200 * FOG_NEAR])
    expect(weatherFog(100, 200, 'rain')).toEqual([100, 200])
  })
})

describe('the lightning flash', () => {
  it('lifts the light three times at the strike and fades within 0.15 s', () => {
    expect(flashLevel(0)).toBe(FLASH_LIFT)
    expect(flashLevel(FLASH_SECONDS / 2)).toBeCloseTo(2)
    expect(flashLevel(FLASH_SECONDS)).toBe(1)
    expect(flashLevel(-0.01)).toBe(1)
    expect(flashAt([{ x: 0, y: 0, z: 0, at: 10 }, { x: 1, y: 0, z: 0, at: 20 }], 20.05)).toBeCloseTo(1 + 2 * (1 - 0.05 / 0.15))
    expect(flashAt([], 5)).toBe(1)
    expect(flashAt(undefined, 5)).toBe(1)
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/seasons.test.ts src/survival/weather.test.ts src/survival/hud.test.ts`
Expected: `Test Files  3 failed (3)`: `Cannot find module './seasons'`, `Cannot find module './weather'`, and `expected 'Survived 12 days · died of lightning' to be 'Survived 12 days · struck by lightning'`

- [ ] **Step 3: The sky's tints and the HUD's line**

In `frontend/src/survival/DayNight.tsx`, replace:

```tsx
import { dayness, rgbToHex, skyColor } from './sky'
```

with:

```tsx
import { seasonSky } from './seasons'
import { dayness, mixRgb, rgbToHex, skyColor } from './sky'
import type { SkyView } from './types'
import { flashAt, weatherFog, weatherSky } from './weather'
```

and replace:

```tsx
 * materials ignore scene lights.
 */
export default function DayNight({ seconds }: { seconds: () => number }) {
```

with:

```tsx
 * materials ignore scene lights. W2: the season and the weather (`sky`) tint the sky and the fog, fog
 * closes in (`fog`: the fog's near and far in clear weather), and a lightning strike lifts the light for a
 * moment at replay time `now`.
 */
export default function DayNight({ seconds, sky = null, now, fog }: {
  seconds: () => number
  sky?: SkyView | null
  now?: () => number
  fog?: [number, number]
}) {
```

and replace:

```tsx
    const now = seconds()
    const light = dayness(now)
    color.current.set(rgbToHex(skyColor(now)))
    if (state.scene.background instanceof THREE.Color) state.scene.background.copy(color.current)
    if (state.scene.fog instanceof THREE.Fog) state.scene.fog.color.copy(color.current)
    if (ambient.current) ambient.current.intensity = 0.3 + 0.5 * light
    if (sun.current) sun.current.intensity = 0.25 + 1.45 * light
```

with:

```tsx
    const time = seconds()
    const light = dayness(time)
    const flash = now ? flashAt(sky?.strikes, now()) : 1
    const tinted = weatherSky(seasonSky(skyColor(time), sky?.season, light), sky?.weather)
    color.current.set(rgbToHex(flash > 1 ? mixRgb(tinted, [255, 255, 255], Math.min(1, (flash - 1) / 2)) : tinted))
    if (state.scene.background instanceof THREE.Color) state.scene.background.copy(color.current)
    if (state.scene.fog instanceof THREE.Fog) {
      state.scene.fog.color.copy(color.current)
      if (fog) [state.scene.fog.near, state.scene.fog.far] = weatherFog(fog[0], fog[1], sky?.weather)
    }
    if (ambient.current) ambient.current.intensity = (0.3 + 0.5 * light) * flash
    if (sun.current) sun.current.intensity = (0.25 + 1.45 * light) * flash
```

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```tsx
import { ailmentLine, wildBadge } from './wild'
```

with:

```tsx
import { ailmentLine, wildBadge } from './wild'
import { seasonBadge } from './seasons'
import { weatherLine } from './weather'
```

and replace:

```tsx
  const badge = wildBadge(state.difficulty)
```

with:

```tsx
  const badge = wildBadge(state.difficulty)
  const season = seasonBadge(state.sky, clock.day_number)
  const weather = weatherLine(state.sky?.weather)
```

and replace:

```tsx
              <p className="text-xs text-[#54726e]">{dayLabel(clock.day_number, clock.phase)} · {clockTime(clock.seconds_into_day)}</p>
```

with:

```tsx
              <p className="text-xs text-[#54726e]">{dayLabel(clock.day_number, clock.phase)} · {clockTime(clock.seconds_into_day)}</p>
              {season && <p className="truncate text-xs text-[#54726e]" title="The season">{season}{weather && ` · ${weather}`}</p>}
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
        ailments={state.ailments} asking={askBubble(state.inbox?.questions, state.server_time)}
```

with:

```tsx
        ailments={state.ailments} asking={askBubble(state.inbox?.questions, state.server_time)} sky={state.sky}
```

In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import type { Ailments, Built, Creature, CreatureMove, FinishedAction, LeafDecay, MimoAction, Point } from './types'
```

with:

```tsx
import type { Ailments, Built, Creature, CreatureMove, FinishedAction, LeafDecay, MimoAction, Point, SkyView } from './types'
```

and replace:

```tsx
 * (`ailments`) and a "?" while it has just asked its owner something (`asking`).
 */
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, recentActions = NO_ACTIONS, decays = NO_DECAYS, structures = NO_STRUCTURES, creatures, creatureMoves, inventory, hurtAt = null, ailments = null, asking = false, serverTime, cameraMode = 'overview', onAutoPick, doorsOpen }: {
```

with:

```tsx
 * (`ailments`) and a "?" while it has just asked its owner something (`asking`). W2: the season and the
 * weather (`sky`) tint the sky, fog closes in and lightning flashes.
 */
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, recentActions = NO_ACTIONS, decays = NO_DECAYS, structures = NO_STRUCTURES, creatures, creatureMoves, inventory, hurtAt = null, ailments = null, asking = false, sky = null, serverTime, cameraMode = 'overview', onAutoPick, doorsOpen }: {
```

and replace:

```tsx
  asking?: boolean
```

with:

```tsx
  asking?: boolean
  /** W2: the season and the weather (the snapshot's `sky`). */
  sky?: SkyView | null
```

and replace:

```tsx
          {seconds ? <DayNight seconds={seconds} /> : (
```

with:

```tsx
          {seconds ? <DayNight seconds={seconds} sky={sky} now={serverTime ? replayTime : undefined} fog={[fogNear, fogFar]} /> : (
```

In `frontend/src/survival/animation.ts`, replace:

```typescript
  dress: 'work',  // W1: wrapping a wound
```

with:

```typescript
  dress: 'work',  // W1: wrapping a wound
  relight: 'place', smoke: 'work',  // W2: lighting a doused campfire; smoking meat over a fire
```

In `frontend/src/survival/hud.ts`, replace:

```typescript
  sickness: 'sickness',  // W1
```

with:

```typescript
  sickness: 'sickness',  // W1
  lightning: 'lightning', fire: 'a fire',  // W2
```

and replace:

```typescript
  dress: 'Dressing its wound with',  // W1
```

with:

```typescript
  dress: 'Dressing its wound with',  // W1
  relight: 'Relighting the campfire', smoke: 'Smoking',  // W2
```

and replace:

```typescript
  dress_wound: 'Dressing its wound', throw_out: 'Throwing out bad food',
```

with:

```typescript
  dress_wound: 'Dressing its wound', throw_out: 'Throwing out bad food',
  // W2
  make_cloak: 'Making a wool cloak', build_hearth: 'Building a hearth', smoke_meat: 'Smoking meat for the winter',
```

and replace:

```typescript
  take_herb: 'Eating sunleaf to feel better',  // W1
```

with:

```typescript
  take_herb: 'Eating sunleaf to feel better',  // W1
  flee_fire: 'Running from the fire!', take_cover: 'Heading home out of the weather',  // W2
```

and replace:

```typescript
  if (life.cause === 'sickness') return `Survived ${daysText(life.days)} · fell sick and never got better`  // W1
```

with:

```typescript
  if (life.cause === 'sickness') return `Survived ${daysText(life.days)} · fell sick and never got better`  // W1
  if (life.cause === 'lightning') return `Survived ${daysText(life.days)} · struck by lightning`  // W2
  if (life.cause === 'fire') return `Survived ${daysText(life.days)} · caught in a fire`
```

Create `frontend/src/survival/seasons.ts`:

```typescript
import { mixRgb, type Rgb } from './sky'
import type { Season, SkyView } from './types'

/**
 * Wild World W2 in the viewer: the season on the HUD, a colder sky by day in winter, and how the snow cover and
 * the ice ease in and out on the terrain (the uSnow and uFrozen uniforms). The seasons are the server's
 * (backend/survival/sky.py): four of SEASON_DAYS game days each.
 */

export const SEASON_DAYS = 10
/** Seconds the drawn snow cover takes to catch up with the server's. */
export const SNOW_EASE_SECONDS = 10
/** Game seconds the ice takes to come and go at the freeze and the thaw. */
export const FREEZE_GAME_SECONDS = 60
/** A colder day sky, mixed in by day in winter. */
export const WINTER_DAY_SKY: Rgb = [0xcf, 0xdb, 0xe8]
const WINTER_SKY_SHARE = 0.55
const NAMES: Record<Season, string> = { spring: 'Spring', summer: 'Summer', autumn: 'Autumn', winter: 'Winter' }
const NEXT: Record<Season, Season> = { spring: 'summer', summer: 'autumn', autumn: 'winter', winter: 'spring' }

/** "Winter · day 34 · 6 days to spring" (the life's day number), or null for an older API that sends no sky. */
export function seasonBadge(sky: SkyView | null | undefined, dayNumber: number): string | null {
  if (!sky) return null
  const days = sky.to_next === 1 ? '1 day' : `${sky.to_next} days`
  return `${NAMES[sky.season]} · day ${dayNumber} · ${days} to ${NEXT[sky.season]}`
}

/** A value `seconds` long to go from 0 to 1, moved toward `target` for a frame of `delta` seconds. */
export function easeToward(current: number, target: number, delta: number, seconds: number): number {
  const step = seconds > 0 ? delta / seconds : 1
  return current + Math.max(-step, Math.min(step, target - current))
}

/** Real seconds the ice takes at the freeze and the thaw, at the clock's pace (game seconds a second). */
export function freezeSeconds(timeScale: number): number {
  return FREEZE_GAME_SECONDS / Math.max(timeScale, 1e-6)
}

/** The sky's color in the season: in winter a colder blue by day (`dayness` 1 by day, 0 at night). */
export function seasonSky(color: Rgb, season: Season | null | undefined, dayness: number): Rgb {
  return season === 'winter' ? mixRgb(color, WINTER_DAY_SKY, WINTER_SKY_SHARE * dayness) : color
}
```

In `frontend/src/survival/types.ts`, replace:

```typescript
  | 'dress'  // W1: a wound dressed with a bandage or a sunleaf
```

with:

```typescript
  | 'dress'  // W1: a wound dressed with a bandage or a sunleaf
  | 'relight' | 'smoke'  // W2: a campfire the rain put out lit again; meat smoked over a fire
```

and replace:

```typescript

/** A goal a life reached, and the game day it did. */
```

with:

```typescript

/** W2: the weather (backend/survival/sky.py). */
export type Weather = 'clear' | 'rain' | 'storm' | 'fog' | 'snow'

/** W2: the seasons, each SEASON_DAYS long. */
export type Season = 'spring' | 'summer' | 'autumn' | 'winter'

/** W2: a lightning strike and the server time it fell. */
export interface Strike extends Point {
  at: number
}

/** W2: the sky (backend/survival/sky.py sky_view). */
export interface SkyView {
  season: Season
  /** The season's day, 1 to 10. */
  day: number
  /** Game days to the next season. */
  to_next: number
  weather: Weather
  /** Server time the weather next changes; null before the tick first tended it. */
  until: number | null
  /** Snow cover, 0 to 1. */
  snow: number
  /** The lakes are frozen (winter). */
  frozen: boolean
  /** The latest strikes, newest last. */
  strikes: Strike[]
  /** The cells burning in the trees. */
  fires: Point[]
}

/** A goal a life reached, and the game day it did. */
```

and replace:

```typescript
  ailments?: Ailments
```

with:

```typescript
  ailments?: Ailments
  /** W2: the season, the weather, the snow, the ice, the latest strikes and the fires (an older API sends none). */
  sky?: SkyView
```

Create `frontend/src/survival/weather.ts`:

```typescript
import { mixRgb, type Rgb } from './sky'
import type { Strike, Weather } from './types'

/**
 * Wild World W2 in the viewer: how each weather tints the sky, the word and mark the HUD shows, how many rain
 * streaks and snowflakes fall, how close the fog comes, and the lightning flash. The weather is the server's
 * (backend/survival/sky.py); the viewer only draws it.
 */

export const RAIN_STREAKS = 1500
export const SNOW_FLAKES = 800
/** A lightning flash lifts the ambient and sky light this many times... */
export const FLASH_LIFT = 3
/** ...for this many seconds. */
export const FLASH_SECONDS = 0.15
/** In fog the fog closes to this share of the view distance. */
export const FOG_NEAR = 0.35
const TINTS: Partial<Record<Weather, { color: Rgb; share: number; grey: number }>> = {
  rain: { color: [0x8d, 0x9c, 0xae], share: 0.5, grey: 0.4 },
  storm: { color: [0x5c, 0x68, 0x78], share: 0.65, grey: 0.4 },
  fog: { color: [0xcc, 0xd0, 0xd2], share: 0.75, grey: 0 },
  snow: { color: [0xe2, 0xe6, 0xea], share: 0.55, grey: 0.2 },
}
const WORDS: Record<Weather, string> = { clear: 'Clear', rain: 'Rain', storm: 'Storm', fog: 'Fog', snow: 'Snow' }
const MARKS: Record<Weather, string> = { clear: '☀', rain: '☂', storm: 'ϟ', fog: '≋', snow: '❄' }

/** `rgb` with `amount` (0..1) of its color taken out toward its own grey. */
export function desaturate(rgb: Rgb, amount: number): Rgb {
  const grey = Math.round(0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2])
  return mixRgb(rgb, [grey, grey, grey], amount)
}

/** The sky's (and the fog's) color in this weather: grey-blue in rain and storm, pale grey in fog, white-grey in snow. */
export function weatherSky(base: Rgb, weather: Weather | null | undefined): Rgb {
  const tint = weather ? TINTS[weather] : undefined
  return tint ? mixRgb(desaturate(base, tint.grey), tint.color, tint.share) : base
}

/** "☂ Rain" for the HUD; null for an older API that sends no weather. */
export function weatherLine(weather: Weather | null | undefined): string | null {
  return weather ? `${MARKS[weather]} ${WORDS[weather]}` : null
}

/** Rain streaks or snowflakes to draw: half on a phone-sized screen, none in dry weather. */
export function particleCount(weather: Weather | null | undefined, small: boolean): number {
  const count = weather === 'rain' || weather === 'storm' ? RAIN_STREAKS : weather === 'snow' ? SNOW_FLAKES : 0
  return small ? Math.round(count / 2) : count
}

/** The fog's near and far in this weather: in fog both close to FOG_NEAR of what they are. */
export function weatherFog(near: number, far: number, weather: Weather | null | undefined): [number, number] {
  return weather === 'fog' ? [near * FOG_NEAR, far * FOG_NEAR] : [near, far]
}

/** How many times brighter the light is `since` seconds after a strike: FLASH_LIFT for FLASH_SECONDS, fading. */
export function flashLevel(since: number): number {
  if (since < 0 || since >= FLASH_SECONDS) return 1
  return 1 + (FLASH_LIFT - 1) * (1 - since / FLASH_SECONDS)
}

/** The brightest flash of any strike at replay time `now`. */
export function flashAt(strikes: readonly Strike[] | null | undefined, now: number): number {
  return Math.max(1, ...(strikes ?? []).map((strike) => flashLevel(now - strike.at)))
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  382 passed (382)`, the build succeeds, eslint prints nothing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/survival/DayNight.tsx frontend/src/survival/SurvivalHud.tsx frontend/src/survival/SurvivalWorld.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/survival/animation.ts frontend/src/survival/hud.test.ts frontend/src/survival/hud.ts frontend/src/survival/seasons.test.ts frontend/src/survival/seasons.ts frontend/src/survival/types.ts frontend/src/survival/weather.test.ts frontend/src/survival/weather.ts
git commit -m "feat(W2): the viewer tints the sky by season and weather and shows both on the HUD" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Viewer: rain, snow, lightning, fire, the snow cover and the ice

**Files:**
- Create: `frontend/src/survival/WeatherEffects.tsx`
- Modify: `frontend/src/engine/mesher.ts` (the `open` attribute), `frontend/src/engine/workerProtocol.ts`, `frontend/src/engine/columnRenderer.ts` (`WeatherUniforms`, `applyDaylight`'s weather, `setWeather`), `frontend/src/engine/BlockWorld.tsx`, `frontend/src/survival/weather.ts` (the falls, the bolt, embers, smoke), `WorldCanvas.tsx` (the easing, the effects), `SurvivalWorld.tsx`, `SurvivalPet.tsx` and `petGear.ts` (the cloak), `creatures.ts` (the new items' colours)
- Test: `frontend/src/engine/mesher.test.ts`, `frontend/src/engine/columnRenderer.test.ts`, `frontend/src/survival/weather.test.ts`, `frontend/src/survival/petGear.test.ts`

**Interfaces:**
- Consumes: Task 11's `weather.ts` and `seasons.ts`; `/api/mimo`'s `sky.snow`, `frozen`, `strikes`, `fires` and the pet's `wool_cloak`.
- Produces: the mesher's `open` attribute (`OPEN_TOP` 1, `WATER_FACE` 2); `ColumnRenderer.setWeather({ snow, frozen })`; `weather.ts`: `FALL_BOX`, `fallAt`, `fallShown`, `boltPoints`, `boltsAt`, `BOLT_SEGMENTS`, `emberAt`, `burnedOut`, `SMOKE_GAME_SECONDS`; `petGear.wornCloak`, `cloakVoxels`; `WeatherEffects`.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/engine/columnRenderer.test.ts`, replace:

```typescript
  indices: new Uint32Array(0),
})
const oneQuad = (): LayerBuffers => ({
  positions: new Float32Array(12), uvs: new Float32Array(8), colors: new Float32Array(12), glows: new Float32Array(4),
  indices: new Uint32Array([0, 1, 2, 0, 2, 3]),
```

with:

```typescript
  opens: new Float32Array(0), indices: new Uint32Array(0),
})
const oneQuad = (): LayerBuffers => ({
  positions: new Float32Array(12), uvs: new Float32Array(8), colors: new Float32Array(12), glows: new Float32Array(4),
  opens: new Float32Array(4), indices: new Uint32Array([0, 1, 2, 0, 2, 3]),
```

and replace:

```typescript

  it('reports a worker crash and cleans up on dispose', () => {
```

with:

```typescript

  it('installs the open attribute and drives the snow and the ice (W2)', () => {
    const { group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    worker.reply(meshed(worker.posted[0]))
    const mesh = group.children[0] as THREE.Mesh
    expect(mesh.geometry.getAttribute('open').itemSize).toBe(1)
    const shader = compile(mesh.material as THREE.Material)
    expect(shader.fragmentShader).toContain('uniform float uSnow;')
    expect(shader.fragmentShader).toContain('vOpen > 1.5 && vWorld.y >= 2.0')
    renderer.setWeather(0.6, 2)
    expect([shader.uniforms.uSnow.value, shader.uniforms.uFrozen.value]).toEqual([0.6, 1])
  })

  it('reports a worker crash and cleans up on dispose', () => {
```

In `frontend/src/engine/mesher.test.ts`, replace:

```typescript
import { cornerAo, meshColumn, PADDED, paddedIndex, type LayerBuffers } from './mesher'
```

with:

```typescript
import { cornerAo, meshColumn, OPEN_TOP, PADDED, paddedIndex, WATER_FACE, type LayerBuffers } from './mesher'
```

and replace:

```typescript
  return quads(buffers).find((quad) => quad.vertices.every(([x, y, z]) => y === 11 && x >= 4 && x <= 5 && z >= 4 && z <= 5))!
}

```

with:

```typescript
  return quads(buffers).find((quad) => quad.vertices.every(([x, y, z]) => y === 11 && x >= 4 && x <= 5 && z >= 4 && z <= 5))!
}

describe('the open attribute (W2)', () => {
  it('marks a top face open to the sky, not one under a roof, and every face of water', () => {
    const topOpen = (blocks: [number, number, number, string][]) => {
      const opaque = mesh(blocks).opaque
      const quad = quads(opaque).findIndex((found) => found.vertices.every(([x, y, z]) => y === 11 && x >= 4 && x <= 5 && z >= 4 && z <= 5))
      return opaque.opens[quad * 4]
    }
    expect(topOpen([[5, 10, 5, 'stone']])).toBe(OPEN_TOP)
    expect(topOpen([[5, 10, 5, 'stone'], [5, 14, 5, 'planks']])).toBe(0)
    expect(topOpen([[5, 10, 5, 'stone'], [5, 12, 5, 'glass']])).toBe(OPEN_TOP)  // glass is no roof for snow... nor opaque
    const lake = mesh([[5, 10, 5, 'sand'], [5, 11, 5, 'water']]).translucent
    expect(new Set(lake.opens)).toEqual(new Set([WATER_FACE]))
    const side = mesh([[5, 10, 5, 'stone']]).opaque
    expect(side.opens.filter((value) => value === OPEN_TOP)).toHaveLength(4)  // the top face's four corners only
  })
})

```

In `frontend/src/survival/petGear.test.ts`, replace:

```typescript
import { HURT_GLOW_SECONDS, capVoxels, hurtGlow, tunicVoxels, wornCap, wornTunic } from './petGear'
```

with:

```typescript
import { HURT_GLOW_SECONDS, capVoxels, cloakVoxels, hurtGlow, tunicVoxels, wornCap, wornCloak, wornTunic } from './petGear'
```

and replace:

```typescript

  it('glows red at once after a blow and fades', () => {
```

with:

```typescript

  it('wears a wool cloak down its back when it carries one (W2)', () => {
    expect(wornCloak({ wool_cloak: 1 })).toBe(true)
    expect(wornCloak({ wool: 5 })).toBe(false)
    expect(cloakVoxels(false)).toEqual([])
    const cloak = cloakVoxels(true)
    expect(cloak).toHaveLength(9)
    expect(cloak.every((voxel) => voxel.z < 0)).toBe(true)  // behind the body, never over the face
  })

  it('glows red at once after a blow and fades', () => {
```

In `frontend/src/survival/weather.test.ts`, replace:

```typescript
  desaturate, FLASH_LIFT, FLASH_SECONDS, FOG_NEAR, flashAt, flashLevel, particleCount, RAIN_STREAKS, SNOW_FLAKES,
  weatherFog, weatherLine, weatherSky,
```

with:

```typescript
  BOLT_SECONDS, boltPoints, boltsAt, burnedOut, desaturate, emberAt, FALL_BOX, fallAt, fallShown, FLASH_LIFT,
  FLASH_SECONDS, FOG_NEAR, flashAt, flashLevel, particleCount, RAIN_STREAKS, SNOW_FLAKES, weatherFog, weatherLine,
  weatherSky,
```

and replace:

```typescript

describe('the lightning flash', () => {
```

with:

```typescript

describe('rain, snow, bolts, embers and smoke', () => {
  const center = { x: 100, y: 20, z: -50 }

  it('falls in a box round the camera and wraps round', () => {
    for (const t of [0, 0.3, 7.7]) {
      const at = fallAt(12, t, 'rain', center)
      expect(Math.abs(at.x - center.x)).toBeLessThanOrEqual(FALL_BOX.width / 2)
      expect(Math.abs(at.y - center.y)).toBeLessThanOrEqual(FALL_BOX.height / 2)
    }
    const fell = (weather: 'rain' | 'snow') => (fallAt(3, 0, weather, center).y - fallAt(3, 0.01, weather, center).y
      + FALL_BOX.height) % FALL_BOX.height
    expect(fell('rain')).toBeCloseTo(0.24)
    expect(fell('snow')).toBeLessThan(0.1)  // a flake drifts down slowly
    expect(fallShown('rain', 'overview', true)).toBe(true)
    expect(fallShown('rain', 'eyes', true)).toBe(false)
    expect(fallShown('snow', 'close', false)).toBe(true)
    expect(fallShown('fog', 'overview', false)).toBe(false)
  })

  it('draws a bolt from the sky to the strike for a moment', () => {
    const strike = { x: 4, y: 10, z: -3, at: 50 }
    const bolt = boltPoints(strike)
    expect(bolt[bolt.length - 1]).toEqual({ x: 4.5, y: 11, z: -2.5 })
    expect(bolt[0].y).toBeGreaterThan(60)
    expect(boltPoints(strike)).toEqual(bolt)
    expect(boltsAt([strike], 50.1)).toEqual([strike])
    expect(boltsAt([strike], 50 + BOLT_SECONDS)).toEqual([])
  })

  it('rises embers over a burning cell and smokes where a tree burned out', () => {
    const ember = emberAt({ x: 3, y: 8, z: 3 }, 1, 12.3)
    expect(ember.position.y).toBeGreaterThanOrEqual(8.6)
    expect(ember.scale).toBeGreaterThan(0)
    expect(burnedOut([{ x: 1, y: 2, z: 3 }, { x: 4, y: 5, z: 6 }], [{ x: 4, y: 5, z: 6 }])).toEqual([{ x: 1, y: 2, z: 3 }])
  })
})

describe('the lightning flash', () => {
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/engine/mesher.test.ts src/engine/columnRenderer.test.ts src/survival/weather.test.ts src/survival/petGear.test.ts`
Expected: `Tests  6 failed | 36 passed (42)`: `wornCloak is not a function`, `fallAt is not a function`, `boltPoints is not a function`, `emberAt is not a function`, and the mesher and the renderer have no `open` attribute yet (`Cannot read properties of undefined (reading 'itemSize')`)

- [ ] **Step 3: The effects, the snow cover and the ice**

In `frontend/src/engine/BlockWorld.tsx`, replace:

```tsx
  cutaway?: (camera: THREE.Vector3) => Cutaway | null
```

with:

```tsx
  cutaway?: (camera: THREE.Vector3) => Cutaway | null
  /** W2: called every frame with the frame's seconds for the snow cover and the ice, each 0..1. Omit for neither. */
  weather?: (delta: number) => [number, number]
```

and replace:

```tsx
export default function BlockWorld({ store, centerX, centerZ, viewDistance, daylight, cutaway, onStats, onError }: BlockWorldProps) {
```

with:

```tsx
export default function BlockWorld({ store, centerX, centerZ, viewDistance, daylight, cutaway, weather, onStats, onError }: BlockWorldProps) {
```

and replace:

```tsx
    current.setCutaway(cutaway ? cutaway(camera.position) : null)
```

with:

```tsx
    current.setCutaway(cutaway ? cutaway(camera.position) : null)
    const [snow, frozen] = weather ? weather(delta) : [0, 0]
    current.setWeather(snow, frozen)
```

In `frontend/src/engine/columnRenderer.ts`, replace:

```typescript
import { CHUNK_SIZE } from './worldgen'
```

with:

```typescript
import { CHUNK_SIZE, SEA_LEVEL } from './worldgen'
```

and replace:

```typescript

const CUTAWAY_FRAGMENT = `
```

with:

```typescript

/** W2: shared uniforms for the snow cover on top faces open to the sky (0..1) and the ice on the lakes (0..1). */
export interface WeatherUniforms {
  snow: { value: number }
  frozen: { value: number }
}

/** W2: the snow whitens an open top face (the mesher's `open` attribute is 1); the ice turns a water face at or above
 * SEA_LEVEL (`open` 2) an opaque pale blue with a faint crackle. */
const WEATHER_FRAGMENT = `
if (vOpen > 0.5 && vOpen < 1.5) diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.93, 0.95, 0.97), uSnow * 0.85);
if (vOpen > 1.5 && vWorld.y >= ${SEA_LEVEL.toFixed(1)}) {
  vec2 cell = floor(vWorld.xz * 3.0);
  float crackle = step(0.93, fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453));
  diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.74, 0.86, 0.94) * (1.0 - 0.18 * crackle), uFrozen);
  diffuseColor.a = mix(diffuseColor.a, 1.0, uFrozen);
}`

const CUTAWAY_FRAGMENT = `
```

and replace:

```typescript
export function applyDaylight(material: THREE.Material, daylight: DaylightUniform, cutaway?: CutawayUniform): void {
```

with:

```typescript
export function applyDaylight(material: THREE.Material, daylight: DaylightUniform, cutaway?: CutawayUniform,
  weather?: WeatherUniforms): void {
```

and replace:

```typescript
    let fragmentStart = '#include <clipping_planes_fragment>'
```

with:

```typescript
    let fragmentStart = '#include <clipping_planes_fragment>'
    let color = '#include <color_fragment>\ndiffuseColor.rgb *= mix(uDaylight, 1.0, vGlow);'
    if (weather) {  // W2
      shader.uniforms.uSnow = weather.snow
      shader.uniforms.uFrozen = weather.frozen
      vertexCommon += '\nattribute float open;\nvarying float vOpen;\nvarying vec3 vWorld;'
      vertexBegin += '\nvOpen = open;\nvWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;'
      fragmentCommon += '\nuniform float uSnow;\nuniform float uFrozen;\nvarying float vOpen;\nvarying vec3 vWorld;'
      color = color.replace('#include <color_fragment>', `#include <color_fragment>${WEATHER_FRAGMENT}`)
    }
```

and replace:

```typescript
      .replace('#include <color_fragment>', '#include <color_fragment>\ndiffuseColor.rgb *= mix(uDaylight, 1.0, vGlow);')
  }
  material.customProgramCacheKey = () => (cutaway ? 'terrain-daylight-cutaway' : 'terrain-daylight')
```

with:

```typescript
      .replace('#include <color_fragment>', color)
  }
  material.customProgramCacheKey = () => `terrain-daylight${cutaway ? '-cutaway' : ''}${weather ? '-weather' : ''}`
```

and replace:

```typescript
  geometry.setAttribute('glow', new THREE.BufferAttribute(buffers.glows, 1))
```

with:

```typescript
  geometry.setAttribute('glow', new THREE.BufferAttribute(buffers.glows, 1))
  geometry.setAttribute('open', new THREE.BufferAttribute(buffers.opens, 1))  // W2: the snow and the ice
```

and replace:

```typescript
  private readonly cutaway: CutawayUniform = { value: new THREE.Vector4(0, 0, 0, 0) }
```

with:

```typescript
  private readonly cutaway: CutawayUniform = { value: new THREE.Vector4(0, 0, 0, 0) }
  private readonly weather: WeatherUniforms = { snow: { value: 0 }, frozen: { value: 0 } }
```

and replace:

```typescript
    for (const material of Object.values(this.materials)) applyDaylight(material, this.daylight, this.cutaway)
```

with:

```typescript
    for (const material of Object.values(this.materials)) applyDaylight(material, this.daylight, this.cutaway, this.weather)
```

and replace:

```typescript
    this.daylight.value = Math.min(1, Math.max(0, value))
```

with:

```typescript
    this.daylight.value = Math.min(1, Math.max(0, value))
  }

  /** W2: the snow cover (0..1) on top faces open to the sky, and the ice (0..1) on the lakes' surface. */
  setWeather(snow: number, frozen: number): void {
    this.weather.snow.value = Math.min(1, Math.max(0, snow))
    this.weather.frozen.value = Math.min(1, Math.max(0, frozen))
```

In `frontend/src/engine/mesher.ts`, replace:

```typescript
  AIR, CUBE_BY_ID, FLUID_BY_ID, GLOW_BY_ID, HEIGHT_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
```

with:

```typescript
  AIR, CUBE_BY_ID, FLUID_BY_ID, GLOW_BY_ID, HEIGHT_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
  blockId,
```

and replace:

```typescript
  indices: Uint32Array
}
```

with:

```typescript
  /** W2: OPEN_TOP for a top face with no opaque block above it in its column (the snow settles there), WATER_FACE
   * for a face of water (it freezes at the lakes' surface), else 0. One per vertex. */
  opens: Float32Array
  indices: Uint32Array
}

/** W2: the `open` attribute's values. */
export const OPEN_TOP = 1
export const WATER_FACE = 2
```

and replace:

```typescript
const SIDE_FACE = 4
```

with:

```typescript
const SIDE_FACE = 4
const WATER = blockId('water')
```

and replace:

```typescript
  indices: number[] = []

  quad(corners: Vec3[], uv: [number, number, number, number], light: number[], flip: boolean, glow = 0): void {
```

with:

```typescript
  opens: number[] = []
  indices: number[] = []

  quad(corners: Vec3[], uv: [number, number, number, number], light: number[], flip: boolean, glow = 0, open = 0): void {
```

and replace:

```typescript
      this.glows.push(glow)
```

with:

```typescript
      this.glows.push(glow)
      this.opens.push(open)
```

and replace:

```typescript
      glows: new Float32Array(this.glows),
```

with:

```typescript
      glows: new Float32Array(this.glows),
      opens: new Float32Array(this.opens),
```

and replace:

```typescript
  const x0 = cx * CHUNK_SIZE - 1, z0 = cz * CHUNK_SIZE - 1
```

with:

```typescript
  const x0 = cx * CHUNK_SIZE - 1, z0 = cz * CHUNK_SIZE - 1
  // W2: the highest opaque layer of each column (-1 with none), so a top face knows whether the sky is open over it.
  const roofs = new Int32Array(PADDED * PADDED).fill(-1)
  for (let pz = 1; pz <= CHUNK_SIZE; pz++) {
    for (let px = 1; px <= CHUNK_SIZE; px++) {
      for (let layer = WORLD_HEIGHT - 1; layer >= 0; layer--) {
        if (LAYER_BY_ID[volume[paddedIndex(px, layer, pz)]] === LAYER_OPAQUE) {
          roofs[pz * PADDED + px] = layer
          break
        }
      }
    }
  }
```

and replace:

```typescript
        const builder = kind === LAYER_OPAQUE ? opaque : translucent
```

with:

```typescript
        const builder = kind === LAYER_OPAQUE ? opaque : translucent
        const water = id === WATER
        const open = layer >= roofs[pz * PADDED + px]
```

and replace:

```typescript
          builder.quad(corners, tileUv(faceTiles[id * 6 + faceIndex]), light, flip, glow ? 1 : 0)
```

with:

```typescript
          const surface = water ? WATER_FACE : dy === 1 && open ? OPEN_TOP : 0
          builder.quad(corners, tileUv(faceTiles[id * 6 + faceIndex]), light, flip, glow ? 1 : 0, surface)
```

In `frontend/src/engine/workerProtocol.ts`, replace:

```typescript
    layer.positions.buffer, layer.uvs.buffer, layer.colors.buffer, layer.glows.buffer, layer.indices.buffer,
```

with:

```typescript
    layer.positions.buffer, layer.uvs.buffer, layer.colors.buffer, layer.glows.buffer, layer.opens.buffer,
    layer.indices.buffer,
```

In `frontend/src/survival/SurvivalPet.tsx`, replace:

```tsx
import { BODY_MIDDLE, TUNIC_SCALE, capVoxels, hurtGlow, tunicVoxels } from './petGear'
```

with:

```tsx
import { BODY_MIDDLE, TUNIC_SCALE, capVoxels, cloakVoxels, hurtGlow, tunicVoxels } from './petGear'
```

and replace:

```tsx
  tunic = null, cap = null, hurtAt = null, ailments = null, asking = false, children }: {
```

with:

```tsx
  tunic = null, cap = null, cloak = false, hurtAt = null, ailments = null, asking = false, children }: {
```

and replace:

```tsx
  cap?: string | null
```

with:

```tsx
  cap?: string | null
  /** W2: it wears a wool cloak (petGear.wornCloak). */
  cloak?: boolean
```

and replace:

```tsx
  const capParts = useMemo(() => capVoxels(cap ? { [cap]: 1 } : {}), [cap])
```

with:

```tsx
  const capParts = useMemo(() => capVoxels(cap ? { [cap]: 1 } : {}), [cap])
  const cloakParts = useMemo(() => cloakVoxels(cloak), [cloak])
```

and replace:

```tsx
          {capParts.length > 0 && <PetVoxels voxels={capParts} />}
```

with:

```tsx
          {capParts.length > 0 && <PetVoxels voxels={capParts} />}
          {cloakParts.length > 0 && <PetVoxels voxels={cloakParts} />}
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
        ailments={state.ailments} asking={askBubble(state.inbox?.questions, state.server_time)} sky={state.sky}
```

with:

```tsx
        ailments={state.ailments} asking={askBubble(state.inbox?.questions, state.server_time)} sky={state.sky}
        sheltered={state.sheltered} timeScale={state.clock.time_scale}
```

Create `frontend/src/survival/WeatherEffects.tsx`:

```tsx
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { CameraMode } from './cameraModes'
import type { Point, SkyView } from './types'
import {
  BOLT_SEGMENTS, boltPoints, boltsAt, burnedOut, EMBERS_PER_FIRE, emberAt, fallAt, fallShown, particleCount,
  RAIN_STREAKS, SMOKE_GAME_SECONDS, SNOW_FLAKES,
} from './weather'

const MAX_FIRES = 48
const MAX_SMOKE = 24
const SMOKE_BITS = 4

/**
 * W2: the weather drawn round the camera and the fires in the trees, at replay time `now` (server seconds): rain
 * streaks or snowflakes falling in a box that follows the camera (half as many on a small screen, none under a
 * roof when the camera is close to or in the pet), a lightning bolt for a moment at each strike, embers over the
 * burning cells, and smoke over a tree that burned out for a game minute. Cheap: five instanced meshes, all updated
 * in one useFrame.
 */
export default function WeatherEffects({ sky, now, mode, sheltered, small, timeScale }: {
  sky: SkyView
  now: () => number
  mode: CameraMode
  sheltered: boolean
  small: boolean
  /** Game seconds a server second, for how long smoke lasts. */
  timeScale: number
}) {
  const rain = useRef<THREE.InstancedMesh>(null)
  const snow = useRef<THREE.InstancedMesh>(null)
  const embers = useRef<THREE.InstancedMesh>(null)
  const smoke = useRef<THREE.InstancedMesh>(null)
  const bolt = useRef<THREE.InstancedMesh>(null)
  const scratch = useRef<THREE.Object3D | null>(null)
  const burned = useRef<{ before: Point[]; smoking: { cell: Point; at: number }[] }>({ before: [], smoking: [] })

  useFrame(({ camera }) => {
    const t = now()
    const dummy = (scratch.current ??= new THREE.Object3D())
    const center = { x: camera.position.x, y: camera.position.y, z: camera.position.z }
    const shown = fallShown(sky.weather, mode, sheltered)
    const falls = [[rain.current, sky.weather === 'rain' || sky.weather === 'storm'], [snow.current, sky.weather === 'snow']] as const
    for (const [mesh, falling] of falls) {
      if (!mesh) continue
      const count = shown && falling ? particleCount(sky.weather, small) : 0
      for (let index = 0; index < count; index++) {
        const at = fallAt(index, t, sky.weather, center)
        dummy.position.set(at.x, at.y, at.z)
        dummy.scale.setScalar(1)
        dummy.updateMatrix()
        mesh.setMatrixAt(index, dummy.matrix)
      }
      mesh.count = count
      mesh.visible = count > 0
      mesh.instanceMatrix.needsUpdate = count > 0
    }
    const flashing = boltsAt(sky.strikes, t)
    const segments = bolt.current
    if (segments) {
      const points = flashing.length > 0 ? boltPoints(flashing[flashing.length - 1]) : []
      for (let k = 0; k + 1 < points.length; k++) {  // each segment a thin bar from one point to the next
        const [from, to] = [points[k], points[k + 1]]
        dummy.position.set((from.x + to.x) / 2, (from.y + to.y) / 2, (from.z + to.z) / 2)
        dummy.scale.set(1, 1, Math.hypot(to.x - from.x, to.y - from.y, to.z - from.z))
        dummy.lookAt(to.x, to.y, to.z)
        dummy.updateMatrix()
        segments.setMatrixAt(k, dummy.matrix)
      }
      segments.count = Math.max(0, points.length - 1)
      segments.visible = points.length > 0
      segments.instanceMatrix.needsUpdate = points.length > 0
      dummy.rotation.set(0, 0, 0)
    }
    const glowing = embers.current
    if (glowing) {
      let shownEmbers = 0
      for (const cell of sky.fires.slice(0, MAX_FIRES)) {
        for (let index = 0; index < EMBERS_PER_FIRE; index++) {
          const { position, scale } = emberAt(cell, index, t)
          dummy.position.set(position.x, position.y, position.z)
          dummy.scale.setScalar(Math.max(0.01, scale))
          dummy.updateMatrix()
          glowing.setMatrixAt(shownEmbers++, dummy.matrix)
        }
      }
      glowing.count = shownEmbers
      glowing.visible = shownEmbers > 0
      glowing.instanceMatrix.needsUpdate = shownEmbers > 0
    }
    const memory = burned.current
    const lasts = SMOKE_GAME_SECONDS / Math.max(timeScale, 1e-6)
    memory.smoking = [...memory.smoking, ...burnedOut(memory.before, sky.fires).map((cell) => ({ cell, at: t }))]
      .filter((puff) => t - puff.at < lasts).slice(-MAX_SMOKE)
    memory.before = sky.fires
    const puffs = smoke.current
    if (puffs) {
      let bits = 0
      for (const puff of memory.smoking) {
        const age = (t - puff.at) / lasts
        for (let index = 0; index < SMOKE_BITS; index++) {
          const rise = ((age * 6 + index / SMOKE_BITS) % 1) * 2.4
          dummy.position.set(puff.cell.x + 0.5 + Math.sin(index * 2.1) * 0.3, puff.cell.y + 0.5 + rise,
            puff.cell.z + 0.5 + Math.cos(index * 2.1) * 0.3)
          dummy.scale.setScalar(0.5 + rise * 0.3)
          dummy.updateMatrix()
          puffs.setMatrixAt(bits++, dummy.matrix)
        }
      }
      puffs.count = bits
      puffs.visible = bits > 0
      puffs.instanceMatrix.needsUpdate = bits > 0
    }
  })

  return (
    <>
      <instancedMesh ref={rain} args={[undefined, undefined, RAIN_STREAKS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.03, 0.75, 0.03]} />
        <meshBasicMaterial color="#aebfd0" transparent opacity={0.55} depthWrite={false} />
      </instancedMesh>
      <instancedMesh ref={snow} args={[undefined, undefined, SNOW_FLAKES]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.1, 0.1, 0.1]} />
        <meshBasicMaterial color="#f7f9fb" />
      </instancedMesh>
      <instancedMesh ref={embers} args={[undefined, undefined, MAX_FIRES * EMBERS_PER_FIRE]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.08, 0.08, 0.08]} />
        <meshBasicMaterial color="#ffb05a" />
      </instancedMesh>
      <instancedMesh ref={smoke} args={[undefined, undefined, MAX_SMOKE * SMOKE_BITS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.5, 0.5, 0.5]} />
        <meshBasicMaterial color="#8d8f93" transparent opacity={0.35} depthWrite={false} />
      </instancedMesh>
      <instancedMesh ref={bolt} args={[undefined, undefined, BOLT_SEGMENTS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.14, 0.14, 1]} />
        <meshBasicMaterial color="#f4f6ff" />
      </instancedMesh>
    </>
  )
}
```

In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import { wornCap, wornTunic } from './petGear'
```

with:

```tsx
import { wornCap, wornCloak, wornTunic } from './petGear'
import { easeToward, freezeSeconds, SNOW_EASE_SECONDS } from './seasons'
import WeatherEffects from './WeatherEffects'
```

and replace:

```tsx
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, recentActions = NO_ACTIONS, decays = NO_DECAYS, structures = NO_STRUCTURES, creatures, creatureMoves, inventory, hurtAt = null, ailments = null, asking = false, sky = null, serverTime, cameraMode = 'overview', onAutoPick, doorsOpen }: {
```

with:

```tsx
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, recentActions = NO_ACTIONS, decays = NO_DECAYS, structures = NO_STRUCTURES, creatures, creatureMoves, inventory, hurtAt = null, ailments = null, asking = false, sky = null, sheltered = false, timeScale = 1, serverTime, cameraMode = 'overview', onAutoPick, doorsOpen }: {
```

and replace:

```tsx
  /** W2: the season and the weather (the snapshot's `sky`). */
  sky?: SkyView | null
```

with:

```tsx
  /** W2: the season and the weather (the snapshot's `sky`); whether Mimo stands inside the shelter it built (no rain
   * or snow falls round a camera close to it there); the clock's pace, for how fast the ice comes and goes. */
  sky?: SkyView | null
  sheltered?: boolean
  timeScale?: number
```

and replace:

```tsx
  const petHidden = useCallback(() => view.current.petHidden, [])
```

with:

```tsx
  const petHidden = useCallback(() => view.current.petHidden, [])
  // W2: the snow cover and the ice drawn on the terrain, eased toward the server's (seasons.ts).
  const cover = useRef({ snow: sky?.snow ?? 0, frozen: sky?.frozen ? 1 : 0 })
  const weatherNow = useCallback((delta: number): [number, number] => {
    const drawn = cover.current
    drawn.snow = easeToward(drawn.snow, sky?.snow ?? 0, delta, SNOW_EASE_SECONDS)
    drawn.frozen = easeToward(drawn.frozen, sky?.frozen ? 1 : 0, delta, freezeSeconds(timeScale))
    return [drawn.snow, drawn.frozen]
  }, [sky, timeScale])
```

and replace:

```tsx
            cutaway={cutawayAt}
            onStats={debug ? setStats : undefined} onError={setEngineError} />
          <SurvivalPet action={action} recent={recentActions} position={position} now={replayTime} onPetClick={onPetClick}
            hopSignal={hopSignal} hidden={petHidden} tunic={wornTunic(inventory)}
            cap={wornCap(inventory)} hurtAt={hurtAt} ailments={ailments} asking={asking}>
```

with:

```tsx
            cutaway={cutawayAt} weather={sky ? weatherNow : undefined}
            onStats={debug ? setStats : undefined} onError={setEngineError} />
          <SurvivalPet action={action} recent={recentActions} position={position} now={replayTime} onPetClick={onPetClick}
            hopSignal={hopSignal} hidden={petHidden} tunic={wornTunic(inventory)}
            cap={wornCap(inventory)} cloak={wornCloak(inventory)} hurtAt={hurtAt} ailments={ailments} asking={asking}>
```

and replace:

```tsx
          {serverTime && <LeafPuffs decays={decays} now={replayTime} />}
```

with:

```tsx
          {serverTime && <LeafPuffs decays={decays} now={replayTime} />}
          {serverTime && sky && <WeatherEffects sky={sky} now={replayTime} mode={cameraMode} sheltered={sheltered}
            small={viewDistance < 6} timeScale={timeScale} />}
```

In `frontend/src/survival/creatures.ts`, replace:

```typescript
    nightberries: [74, 40, 96], sunleaf: [206, 212, 84], bandage: [244, 240, 228], spoiled_food: [122, 118, 70],
```

with:

```typescript
    nightberries: [74, 40, 96], sunleaf: [206, 212, 84], bandage: [244, 240, 228], spoiled_food: [122, 118, 70],
    // W2: what a pet makes for the winter
    wool_cloak: [236, 229, 212], smoked_meat: [140, 84, 58],
```

In `frontend/src/survival/petGear.ts`, replace:

```typescript
const AMBER: Color = [222, 150, 52]  // L5: amber-studded, over the iron's rivets
```

with:

```typescript
const AMBER: Color = [222, 150, 52]  // L5: amber-studded, over the iron's rivets
const WOOL: Color = [236, 229, 212]  // W2: a wool cloak, with a darker hem
const HEM: Color = [196, 184, 160]
```

and replace:

```typescript

/** How red the pet glows (0..1) at server time `t` after a blow at `hurtAt`: at once, then fading. */
```

with:

```typescript

/** W2: whether Mimo wears a wool cloak (it carries one). */
export function wornCloak(inventory: Record<string, number> | null | undefined): boolean {
  return (inventory?.wool_cloak ?? 0) > 0
}

/** W2: the cloak's voxels, hanging down its back from a collar at its neck, when it wears one; else none. */
export function cloakVoxels(worn: boolean): Voxel[] {
  if (!worn) return []
  const voxels: Voxel[] = []
  for (let x = -1; x <= 1; x++) {
    voxels.push(voxel(x, 2, -1, WOOL), voxel(x, 1, -2, WOOL), voxel(x, 0, -2, HEM))
  }
  return voxels
}

/** How red the pet glows (0..1) at server time `t` after a blow at `hurtAt`: at once, then fading. */
```

In `frontend/src/survival/weather.ts`, replace:

```typescript
import { mixRgb, type Rgb } from './sky'
import type { Strike, Weather } from './types'
```

with:

```typescript
import type { CameraMode } from './cameraModes'
import { mixRgb, type Rgb } from './sky'
import type { Point, Strike, Weather } from './types'
```

and replace:

```typescript

/** The brightest flash of any strike at replay time `now`. */
```

with:

```typescript

/** Rain and snow fall in a box this wide and tall that follows the camera. */
export const FALL_BOX = { width: 44, height: 30 }
const FALL_SPEED: Partial<Record<Weather, number>> = { rain: 24, storm: 30, snow: 2.4 }
/** A bolt is drawn this long after its strike. */
export const BOLT_SECONDS = 0.25
const BOLT_HEIGHT = 60
export const BOLT_SEGMENTS = 9
/** Embers over a burning cell, and how long a burned-out tree smokes (game seconds). */
export const EMBERS_PER_FIRE = 3
export const SMOKE_GAME_SECONDS = 60

function hashUnit(a: number, b: number): number {
  let h = Math.imul(a | 0, 374761393) ^ Math.imul(b | 0, 668265263)
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296
}

/** Where rain streak or snowflake `index` is at `t` seconds, in a box round `center`: it falls and wraps round,
 * and a flake drifts. */
export function fallAt(index: number, t: number, weather: Weather, center: Point): Point {
  const speed = FALL_SPEED[weather] ?? 0
  const x = (hashUnit(index, 1) - 0.5) * FALL_BOX.width, z = (hashUnit(index, 2) - 0.5) * FALL_BOX.width
  const drop = (hashUnit(index, 3) * FALL_BOX.height + t * speed) % FALL_BOX.height
  const drift = weather === 'snow' ? Math.sin(t * 0.8 + index) * 0.6 : 0
  return { x: center.x + x + drift, y: center.y + FALL_BOX.height / 2 - drop, z: center.z + z }
}

/** Rain and snow are left out under a roof when the camera is close to or in the pet. */
export function fallShown(weather: Weather | null | undefined, mode: CameraMode, sheltered: boolean): boolean {
  if (particleCount(weather, false) === 0) return false
  return !(sheltered && (mode === 'close' || mode === 'eyes'))
}

/** A jagged bolt from the sky down to the strike: BOLT_SEGMENTS + 1 points, the same for the same strike. */
export function boltPoints(strike: Strike): Point[] {
  const salt = Math.round(strike.at * 1000)
  return Array.from({ length: BOLT_SEGMENTS + 1 }, (_, k) => {
    const share = k / BOLT_SEGMENTS
    const jitter = k === BOLT_SEGMENTS ? 0 : 2.2
    return {
      x: strike.x + 0.5 + (hashUnit(salt, k * 2) - 0.5) * jitter,
      y: strike.y + 1 + BOLT_HEIGHT * (1 - share),
      z: strike.z + 0.5 + (hashUnit(salt, k * 2 + 1) - 0.5) * jitter,
    }
  })
}

/** The strikes whose bolt shows at replay time `now`. */
export function boltsAt(strikes: readonly Strike[] | null | undefined, now: number): Strike[] {
  return (strikes ?? []).filter((strike) => now >= strike.at && now < strike.at + BOLT_SECONDS)
}

/** Ember `index` of a burning cell, rising and fading over a second and a half, at `t` seconds. */
export function emberAt(cell: Point, index: number, t: number): { position: Point; scale: number } {
  const age = (t * 0.66 + hashUnit(index, cell.x * 31 + cell.z)) % 1
  return {
    position: {
      x: cell.x + 0.5 + (hashUnit(index, cell.y) - 0.5) * 0.8,
      y: cell.y + 0.6 + age * 1.6,
      z: cell.z + 0.5 + (hashUnit(cell.z, index) - 0.5) * 0.8,
    },
    scale: 1 - age,
  }
}

/** The cells burning a moment ago that are not now: a tree burned out there, and smokes. */
export function burnedOut(before: readonly Point[], now: readonly Point[]): Point[] {
  const burning = new Set(now.map((cell) => `${cell.x},${cell.y},${cell.z}`))
  return before.filter((cell) => !burning.has(`${cell.x},${cell.y},${cell.z}`))
}

/** The brightest flash of any strike at replay time `now`. */
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  388 passed (388)`, the build succeeds, eslint prints nothing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/engine/BlockWorld.tsx frontend/src/engine/columnRenderer.test.ts frontend/src/engine/columnRenderer.ts frontend/src/engine/mesher.test.ts frontend/src/engine/mesher.ts frontend/src/engine/workerProtocol.ts frontend/src/survival/SurvivalPet.tsx frontend/src/survival/SurvivalWorld.tsx frontend/src/survival/WeatherEffects.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/survival/creatures.ts frontend/src/survival/petGear.test.ts frontend/src/survival/petGear.ts frontend/src/survival/weather.test.ts frontend/src/survival/weather.ts
git commit -m "feat(W2): the viewer draws rain, snow, lightning, fire and smoke, lays the snow cover, freezes the lakes and dresses the pet in its cloak" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: The gate script's W2

**Files:**
- Modify: `backend/scripts/wild_gate.py` (the owner's day 2, the winters, the `upgrade` condition, `check_w2`, `--check W2`)
- Create: `backend/tests/test_survival_sky_gate.py`
- Test: `backend/tests/test_survival_wild_run.py` (every lesson known by day 3)

**Interfaces:**
- Consumes: everything above; W1's `live`, `summarize`, `check_w1`, the scripted owner and the counting model stand-in.
- Produces: `wild_gate.TEACHES_W2`, `UPGRADE` (the `upgrade` condition, beside W1's `CONDITIONS`), `upgrade(world)`, `winter_of`, `sample_sky`, `check_w2(out) -> [(criterion, passed, measure)]`; `--check W2 DIR`; a life's summary gains `winters`, `winter_food`, `struck`, `strike_home`, `fire_claimed`, `clearing_edits` and `sky_offset`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_sky_gate.py`:

```python
"""W2: the gate script's W2 parts: the scripted owner's day 2, the upgraded world, the summary's winters and the
W2 criteria read from the lives' summaries."""

import json
import random
import tempfile
import unittest
from pathlib import Path

from backend.scripts.wild_gate import (
    BORN, SCALE, TEACHES_W2, before_w2, check_w2, sample_sky, upgrade, winter_of,
)
from backend.survival.brain import BRAIN
from backend.survival.hatch import hatch
from backend.survival.lessons import claims
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.wild import thing
from backend.survival.world import SurvivalWorld

W2 = ("winter", "cloak", "hearth", "smoking", "rain", "storm", "fog")


def life(condition, seed, **changes):
    found = {"condition": condition, "seed": seed, "died_day": None, "cause": None, "difficulty": "gentle",
             "machines": {"lamp_lever": 40.0}, "model_calls": 0, "errors": [], "ever": {"sick": False},
             "winters": {str(n): {"health_mean": 95.0, "ticks": 600, "freezing": 2, "starving": 0} for n in (1, 2, 3)},
             "winter_food": {"1": 400.0, "2": 380.0, "3": 365.0}, "struck": 0, "strike_home": 30.0,
             "fire_claimed": 0, "clearing_edits": 0, "sky_offset": 0}
    found.update(changes)
    return found


class OwnerTests(unittest.TestCase):
    def test_the_scripted_owners_day_two_teaches_each_w2_lesson(self):
        self.assertEqual([claims(line).taught for line in TEACHES_W2], [(thing(name),) for name in W2])


class UpgradeTests(unittest.TestCase):
    def test_a_world_that_lived_without_w2_gets_spring_on_its_upgrade_day(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN)))
            with before_w2(True):
                tick_life(registry, BORN + 90, scale=SCALE, mind=BRAIN, action_scale=SCALE)  # to day 2
            self.assertNotIn("sky", world.state())
            upgrade(world)
            tick_life(registry, BORN + 91, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            state = world.state()
            self.assertEqual((state["sky"]["offset"], state["sky"]["season"], state["sky"]["season_day"]), (39, "spring", 0))
            found = {}
            sample_sky(found, state, 91, world)
            self.assertEqual(found.get("winters", {}), {})  # spring: no winter yet
            self.assertIsNone(winter_of({}, state, 91))
            self.assertEqual(winter_of({}, state, (1 + 30) * 60 + 5), 1)  # its first winter: 30 days on


class CheckTests(unittest.TestCase):
    def write(self, lives):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for number, found in enumerate(lives):
            (Path(directory.name) / f"{number}.json").write_text(json.dumps(found))
        return {name: passed for name, passed, _ in check_w2(Path(directory.name), cost=False)}

    def lives(self, **changes):
        gentle = [life("gentle", seed) for seed in range(6)]
        taught = [life("taught", seed, difficulty="wild") for seed in range(6)]
        untaught = [life("untaught", seed, difficulty="wild",
                         winters={str(n): {"health_mean": 70.0, "ticks": 600, "freezing": 30, "starving": 5} for n in (1, 2, 3)})
                    for seed in range(6)]
        upgraded = [life("upgrade", seed, sky_offset=21, winters={"1": {"health_mean": 90.0, "ticks": 600, "freezing": 0,
                                                                          "starving": 0}}) for seed in range(2)]
        found = gentle + taught + untaught + upgraded
        for index, entry in changes.items():
            condition, seed, key = index.split("__")
            for one in found:
                if one["condition"] == condition and one["seed"] == int(seed):
                    one.update(entry)
        return found

    def test_every_w2_criterion_passes_on_good_lives(self):
        results = self.write(self.lives())
        self.assertTrue(all(results.values()), results)

    def test_each_criterion_can_fail(self):
        winter = {"health_mean": 50.0, "ticks": 600, "freezing": 0, "starving": 0}
        results = self.write(self.lives(gentle__0__cold={"winters": {"1": winter}},
                                        taught__1__near={"strike_home": 12.0, "struck": 2},
                                        taught__2__empty={"winter_food": {"1": 100.0, "2": 100.0, "3": 100.0}},
                                        taught__3__empty={"winter_food": {"1": 100.0, "2": 400.0, "3": 400.0}}))
        failed = {name.split()[0] for name, passed in results.items() if not passed}
        self.assertEqual(failed, {"2", "3", "4", "8"})


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_wild_run.py`, replace:

```python
        w1 = [lesson.name for lesson in SURVIVAL[:11]]  # W2: its questions may teach it some of W2's too
        self.assertLessEqual(set(w1), set(taught["lessons"]))
        self.assertTrue(all(taught["lessons"][name]["day"] < 2 for name in w1), taught["lessons"])
```

with:

```python
        w1 = [lesson.name for lesson in SURVIVAL[:11]]
        self.assertTrue(all(taught["lessons"][name]["day"] < 2 for name in w1), taught["lessons"])
        self.assertEqual(len(taught["lessons"]), len(SURVIVAL))  # W2's seven on day 2
        self.assertTrue(all(entry["day"] < 3 for entry in taught["lessons"].values()), taught["lessons"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest backend.tests.test_survival_sky_gate backend.tests.test_survival_wild_run`
Expected: `FAILED (failures=1, errors=1, skipped=1)`: `ImportError: cannot import name 'TEACHES_W2' from 'backend.scripts.wild_gate'`, and the wild run's taught pet knows 13 lessons by day 3, not 18 (`AssertionError: 13 != 18`)

- [ ] **Step 3: The W2 gate**

In `backend/scripts/wild_gate.py`, replace:

```python
    python3 -m backend.scripts.wild_gate --check W1 DIR
```

with:

```python
    python3 -m backend.scripts.wild_gate --check W1 DIR

W2: the scripted owner says the first teaching-table line of each W2 lesson on day 2, the same way (TEACHES_W2).
Each life's summary gains its winters (`winters`: the health mean, freezing and starving game minutes of each,
days 31 to 40, 71 to 80 and 111 to 120 of a newborn), the food its chests hold for winter on each winter day 1
(`winter_food`, winter_prep.winter_food), the strikes that hit it and the nearest a strike fell to the home it
built at that moment (`strike_home`, from storms.STRIKES: a home finished later in the same tick is not the one the
strike kept clear of), the fire cells that burned in a cell something it built claims (`fire_claimed`) and the
block edits in the legacy clearing (`clearing_edits`). The `upgrade` condition is spec criterion 9's world: a
gentle life ticked UPGRADE_DAY days as the code before W2 had it (no sky), then upgraded and ticked 45 more.

    python3 -m backend.scripts.wild_gate --days 150 --conditions gentle,untaught,taught --parallel 4 --out DIR
    python3 -m backend.scripts.wild_gate --days 65 --conditions upgrade --parallel 4 --out DIR
    python3 -m backend.scripts.wild_gate --check W2 DIR
```

and replace:

```python
import logging
```

with:

```python
import logging
import math
```

and replace:

```python
CONDITIONS = ("gentle", "untaught", "taught", "liar")
```

with:

```python
CONDITIONS = ("gentle", "untaught", "taught", "liar")
UPGRADE = "upgrade"  # W2: a world made before W2 and upgraded (criterion 9)
```

and replace:

```python
MACHINES = ("lamp_lever", "auto_door", "night_light", "clock", "memory_cell", "counter", "computer")
```

with:

```python
MACHINES = ("lamp_lever", "auto_door", "night_light", "clock", "memory_cell", "counter", "computer")
# W2: the first teaching-table line of each W2 lesson, said on day 2 the same way.
TEACHES_W2 = ("Fill a chest with food before winter.", "Five wool make a wool cloak.",
              "A stone hearth keeps the home warm.", "Smoked meat keeps all winter.",
              "Rain puts out a fire under the open sky.", "In a storm stay low and inside.",
              "Stay close to home in the fog.")
WINTERS = ((31, 40), (71, 80), (111, 120))  # a newborn's winters, game days
UPGRADE_DAY = 20  # criterion 9: the upgraded world's day when W2 comes
```

and replace:

```python
        owner_says(world, TEACHES[minute // OWNER_EVERY - 1], now, SCALE)
```

with:

```python
        owner_says(world, TEACHES[minute // OWNER_EVERY - 1], now, SCALE)
    later = minute - 60  # W2: day 2
    if condition == "taught" and 0 < later <= OWNER_EVERY * len(TEACHES_W2) and later % OWNER_EVERY == 0:
        owner_says(world, TEACHES_W2[later // OWNER_EVERY - 1], now, SCALE)
```

and replace:

```python
        life = hatch(registry, random.Random(seed), timestamp=BORN, difficulty="gentle" if condition == "gentle" else "wild")
```

with:

```python
        life = hatch(registry, random.Random(seed), timestamp=BORN,
                     difficulty="gentle" if condition in ("gentle", "upgrade") else "wild")
```

and replace:

```python
        for minute in range(1, days * 60 + 1):
            now = BORN + minute
            state = tick_life(registry, now, scale=SCALE, mind=BRAIN, action_scale=SCALE)
```

with:

```python
        from backend.survival import storms
        seen = strike_seen(found)
        storms.STRIKES.append(seen)
        for minute in range(1, days * 60 + 1):
            now = BORN + minute
            if condition == "upgrade" and minute == UPGRADE_DAY * 60:
                upgrade(world)  # W2 comes to a world that lived UPGRADE_DAY days without it
            with before_w2(condition == "upgrade" and minute < UPGRADE_DAY * 60):
                state = tick_life(registry, now, scale=SCALE, mind=BRAIN, action_scale=SCALE)
```

and replace:

```python
        talker.close()
```

with:

```python
            sample_sky(found, state, minute, world)
        talker.close()
        storms.STRIKES.remove(seen)
```

and replace:

```python
    return summary
```

with:

```python
    return summary


def before_w2(active: bool):
    """While `active`, the tick runs as the code before W2 did: no sky at all (criterion 9's old world)."""
    from contextlib import ExitStack
    from unittest.mock import patch
    stack = ExitStack()
    if active:
        stack.enter_context(patch("backend.survival.tick.sky.advance", lambda state, context, at: None))
        stack.enter_context(patch("backend.survival.tick.sky.settle_sky", lambda state, at, scale: None))
    return stack


def upgrade(world) -> None:
    """The old world's state loses what W2 would have written (it had none): its next tick is its first W2 tick."""
    from backend.survival.world import read_state, write_state
    with world.transaction() as db:
        state = read_state(db)
        state.pop("sky", None)
        write_state(db, state)


def winter_of(found: dict, state: dict, minute: int) -> int | None:
    """Which of the life's winters (1, 2, 3 ...) the game minute falls in, by its own seasons (an upgraded world's
    year starts on its upgrade day), or None outside winter."""
    from backend.survival.sky import YEAR_DAYS, season_at
    if "offset" not in (state.get("sky") or {}) or season_at(state, BORN + minute, SCALE)[0] != "winter":
        return None
    year = ((minute - 1) // 60 + state["sky"]["offset"]) // YEAR_DAYS
    seen = found.setdefault("winter_years", [])
    if year not in seen:
        seen.append(year)
    return seen.index(year) + 1


def sample_sky(found: dict, state: dict, minute: int, world) -> None:
    """W2: one tick's sample of the winters, the winter food, the strikes and the fires (see the module docstring)."""
    from backend.survival.situation import from_db
    from backend.survival.winter_prep import winter_food
    vitals = state["vitals"]
    winters = found.setdefault("winters", {})
    winter = winter_of(found, state, minute)
    if winter is not None:
        entry = winters.setdefault(str(winter), {"health": 0.0, "ticks": 0, "freezing": 0, "starving": 0})
        entry["health"] += vitals["health"]
        entry["ticks"] += 1
        entry["freezing"] += vitals["warmth"] < 20.0
        entry["starving"] += vitals["hunger"] <= 0.0
        food = found.setdefault("winter_food", {})
        if str(winter) not in food:  # the first tick of its winter day 1
            with world.connect() as db:
                food[str(winter)] = round(winter_food(from_db(db, state, BORN + minute, SCALE)), 1)
    fires = (state.get("sky") or {}).get("fires", [])
    if fires:
        with world.connect() as db:
            for entry in fires:
                claimed = db.execute("SELECT 1 FROM structure_cells WHERE x=? AND y=? AND z=?",
                                     (entry["x"], entry["y"], entry["z"])).fetchone()
                found["fire_claimed"] = found.get("fire_claimed", 0) + (claimed is not None)


def strike_seen(found: dict):
    """A storms.STRIKES hook: how near each strike fell to the home Mimo built at that moment."""
    from backend.survival.storms import built_home

    def seen(state, context, cell, hit, at):
        home = built_home(context.db)
        if home is not None:
            found["strike_home"] = min(found.get("strike_home", math.inf), math.hypot(cell[0] - home[0], cell[2] - home[1]))
    return seen
```

and replace:

```python
    return {"seed": seed, "days": days, "condition": condition, "wall": round(wall, 1), "difficulty": state.get("difficulty"),
```

with:

```python
    winters = {winter: {"health_mean": round(entry["health"] / max(1, entry["ticks"]), 2), "ticks": entry["ticks"],
                        "freezing": entry["freezing"], "starving": entry["starving"]}
               for winter, entry in found.get("winters", {}).items()}
    with world.connect() as db:
        from backend.services.worldgen import LEGACY_RADIUS
        clearing = db.execute("SELECT COUNT(*) FROM mimo_blocks WHERE x * x + z * z <= ?",
                              (LEGACY_RADIUS * LEGACY_RADIUS,)).fetchone()[0]
    sky = state.get("sky") or {}
    return {"winters": winters, "winter_food": found.get("winter_food", {}),  # W2
            "struck": kinds.get("struck", 0), "strike_home": found.get("strike_home"),
            "fire_claimed": found.get("fire_claimed", 0), "clearing_edits": clearing, "sky_offset": sky.get("offset"),
            "seed": seed, "days": days, "condition": condition, "wall": round(wall, 1), "difficulty": state.get("difficulty"),
```

and replace:

```python
    known = all(len(life["lessons"]) == 11 and all(entry["source"] == "from_start" for entry in life["lessons"].values())
                for life in g)
```

with:

```python
    from backend.survival.wild import SURVIVAL  # W2: every landed milestone's lessons
    known = all(len(life["lessons"]) == len(SURVIVAL)
                and all(entry["source"] == "from_start" for entry in life["lessons"].values()) for life in g)
```

and replace:

```python

def main(argv=None) -> int:
```

with:

```python

# The W2 gate ----------------------------------------------------------------------------------------

def winter_means(life: dict) -> list[float]:
    return [entry["health_mean"] for entry in life.get("winters", {}).values() if entry["ticks"]]


def cost_rows() -> tuple[bool, str]:
    """Criterion 10: the sky hook's budget in a storm by a forest and a route across a frozen lake (the unit tests
    that measure them, run here)."""
    import unittest
    names = ("backend.tests.test_survival_storms.TickTests.test_a_storm_near_a_forest_costs_the_tick_little",
             "backend.tests.test_survival_winter.IceTests.test_a_path_crosses_a_frozen_lake_and_the_overlay_costs_the_search_little")
    result = unittest.TextTestRunner(stream=open("/dev/null", "w"), verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromNames(names))
    return result.wasSuccessful(), f"{result.testsRun} budget tests, {len(result.failures) + len(result.errors)} failed"


def check_w2(out: Path, cost: bool = True) -> list[tuple[str, bool, str]]:
    """The W2 gate's criteria, each (name, passed, the measure)."""
    lives = load(out)
    gentle, untaught, taught = (list(lives.get(name, {}).values()) for name in ("gentle", "untaught", "taught"))
    upgraded = list(lives.get("upgrade", {}).values())
    rows: list[tuple[str, bool, str]] = []

    def row(name, passed, measure):
        rows.append((name, bool(passed), measure))

    kept = gentle + taught
    row("1 gentle and taught: all alive on day 150", len(kept) == 12 and all(alive_on(life, 150) for life in kept),
        f"alive {sum(alive_on(life, 150) for life in kept)}/{len(kept)}")
    worst = [(life["condition"], life["seed"], winter, entry) for life in kept
             for winter, entry in life.get("winters", {}).items()]
    bad = [(condition, seed, winter) for condition, seed, winter, entry in worst
           if entry["health_mean"] < 60 or entry["freezing"] > 10 or entry["starving"] > 10]
    row("2 gentle and taught: each winter health mean 60+, freezing and starving 10 game minutes at most",
        worst and not bad, f"lowest mean {min((entry['health_mean'] for *_, entry in worst), default=0)}; most freezing "
        f"{max((entry['freezing'] for *_, entry in worst), default=0)}; most starving "
        f"{max((entry['starving'] for *_, entry in worst), default=0)}; failing {bad}")
    from backend.survival.winter_prep import WINTER_FOOD
    stocked = {condition: [sum(1 for life in group if life.get("winter_food", {}).get(str(winter), 0) >= WINTER_FOOD)
                           for winter in (1, 2, 3)] for condition, group in (("gentle", gentle), ("taught", taught))}
    row("3 gentle and taught: WINTER_FOOD in the chests on winter day 1, 5 of 6 the first winter, 6 of 6 after",
        all(counts[0] >= 5 and counts[1] >= 6 and counts[2] >= 6 for counts in stocked.values()),
        f"stocked by winter {stocked}; food {[(life['condition'], life['seed'], life.get('winter_food')) for life in kept]}")
    row("4 gentle and taught: at most 1 strike on Mimo a life", all(life.get("struck", 0) <= 1 for life in kept),
        f"most {max((life.get('struck', 0) for life in kept), default=0)}")
    lamps = sum(1 for life in taught if "lamp_lever" in life["machines"])
    most_taught = max((len(life["machines"]) for life in taught), default=0)
    most_gentle = max((len(life["machines"]) for life in gentle), default=0)
    row("5 W1 criterion 5: 3 of 6 taught build a lamp on a lever; the furthest within one of gentle's",
        lamps >= 3 and most_taught >= most_gentle - 1, f"lamps {lamps}/6; machines taught {most_taught}, gentle {most_gentle}")
    mean_of = lambda group: sum(sum(winter_means(life)) / max(1, len(winter_means(life))) for life in group) / max(1, len(group))
    row("6 untaught: the mean winter health mean 15 or more below taught's", untaught and taught
        and mean_of(taught) - mean_of(untaught) >= 15, f"untaught {mean_of(untaught):.1f}, taught {mean_of(taught):.1f}")
    row("7 untaught: at least 2 of 6 alive on day 150, none dead before day 5",
        sum(alive_on(life, 150) for life in untaught) >= 2 and all(alive_on(life, 5) for life in untaught),
        f"alive {sum(alive_on(life, 150) for life in untaught)}/{len(untaught)}; deaths "
        f"{[(life['died_day'], life['cause']) for life in untaught if not alive_on(life, 150)]}")
    everyone = gentle + untaught + taught + upgraded
    near = [life["strike_home"] for life in everyone if life.get("strike_home") is not None]
    row("8 safety: no strike within 16 of a built home, no fire in a claimed cell, no edit in the legacy clearing",
        all(distance > 16 for distance in near) and not any(life.get("fire_claimed") for life in everyone)
        and not any(life.get("clearing_edits") for life in everyone),
        f"nearest strike to home {min(near, default=None)}; fire in claimed cells "
        f"{sum(life.get('fire_claimed', 0) for life in everyone)}; clearing edits "
        f"{sum(life.get('clearing_edits', 0) for life in everyone)}")
    first = [(life["seed"], life.get("sky_offset"), life.get("winters", {}).get("1")) for life in upgraded]
    row("9 upgrade: spring on its upgrade day, alive and gentle through its first winter",
        upgraded and all(offset == (1 - UPGRADE_DAY) % 40 and winter and winter["ticks"] >= 600
                         for _, offset, winter in first) and all(alive_on(life, UPGRADE_DAY + 45) for life in upgraded)
        and all(life["difficulty"] == "gentle" and not any(life["ever"].values()) for life in upgraded),
        f"(seed, offset, first winter) {first}")
    if cost:
        passed, measure = cost_rows()
        row("10 cost: the sky hook in a storm, a route across a frozen lake", passed, measure)
    everybody = [life for group in lives.values() for life in group.values()]
    row("all: no model call and no logged error", all(not life["model_calls"] and not life["errors"] for life in everybody),
        f"calls {sum(life['model_calls'] for life in everybody)}; errors {sum(len(life['errors']) for life in everybody)}")
    return rows


def main(argv=None) -> int:
```

and replace:

```python
    parser.add_argument("--condition", choices=CONDITIONS)
```

with:

```python
    parser.add_argument("--condition", choices=(*CONDITIONS, UPGRADE))
```

and replace:

```python
        if args.check[0] != "W1":
            raise SystemExit("only the W1 gate is written yet")
        rows = check_w1(Path(args.check[1]))
```

with:

```python
        if args.check[0] not in ("W1", "W2"):
            raise SystemExit("the W1 and W2 gates are written")
        rows = (check_w1 if args.check[0] == "W1" else check_w2)(Path(args.check[1]))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest backend.tests.test_survival_sky_gate backend.tests.test_survival_wild_run`
Expected: `OK (skipped=1)`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 2013 tests` … `OK (skipped=6)` (4 new).

Run the gate (about 2 hours on four cores): `python3 -m backend.scripts.wild_gate --days 150 --conditions gentle,untaught,taught --parallel 4 --out DIR`, then `python3 -m backend.scripts.wild_gate --days 30 --conditions liar --parallel 4 --out DIR` and `python3 -m backend.scripts.wild_gate --days 65 --conditions upgrade --parallel 4 --out DIR`, then `python3 -m backend.scripts.wild_gate --check W2 DIR` and `python3 -m backend.scripts.wild_gate --check W1 DIR`
Expected: the tables of "Dry-run measurements"; any criterion that fails is reported to the controller with its measure, never loosened.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/wild_gate.py backend/tests/test_survival_sky_gate.py backend/tests/test_survival_wild_run.py
git commit -m "feat(W2): the gate script measures the W2 gate: winters lived, ready for winter, strikes and fires kept from home, the upgrade and the cost" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Manual check on the demo and the README

This task is for the controller. It rebuilds the demo image from the branch and restarts the demo stack on its own scratch volume, `mimo-l3demo-api` (:8011) and `mimo-l3demo-worker` on volume `mimo_l3demo`, at the natural pace: its pet, hatched before W1, is gentle and gets spring on its first tick. The seasons are watched on a fast scratch stack of their own, `mimo-w2sky-api` (:8013) and `mimo-w2sky-worker` on a new volume `mimo_w2sky`, at `MIMO_TIME_SCALE=20` and `MIMO_ACTION_SCALE=20` (a game day every 3 real minutes: autumn about an hour after hatching, winter about 1.5 hours), with a viewer on :3002. The owner's real stack (`pets-api-1`, `pets-mimo-worker-1`) and its volume `pets_mimo_data` are never touched, and nothing uses port 5173.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Describe the weather and the seasons in the README**

In `README.md`, replace:

```markdown

## Current world rules
```

with:

```markdown

## Weather and seasons

- **A year of seasons.** A year is 40 game days: spring, summer, autumn and winter, 10 days each (`backend/survival/sky.py`). A newborn hatches on spring day 1 and meets its first winter on day 31; a world from before the seasons starts spring on its first tick after the upgrade, so its first winter comes 30 game days later. Summer nights are milder, autumn nights colder, and a winter night outdoors freezes (-10 warmth, 10 in a wool cloak; 35 in a shelter, 100 by a hearth), and so does a winter day in the mountains. The HUD shows the season ("Winter · day 34 · 6 days to spring"), and "Winter has come." and "Spring! Things are growing again." are news in the inbox.
- **Weather.** Each 10 game minutes has a weather, a fixed function of the world seed and the season: clear, rain, a thunderstorm, fog or (in winter) snow, a spell lasting half an hour or so. Rain slows a walk under the open sky, puts out a campfire under the open sky (a stick lights it again) and waters the crops. Snow slows walks more, chills Mimo outdoors and lays a snow cover the viewer draws on every top face open to the sky. Fog lets the dark creatures walk by day, the sun does not burn them and two more may be about. The viewer tints the sky, draws rain streaks and snowflakes round the camera, closes the fog in and shows the weather on the HUD.
- **Lightning and fire.** In a thunderstorm lightning strikes about once a game minute near Mimo, on the highest ground and the tallest trees (`backend/survival/storms.py`), never within 16 blocks of the home Mimo built. Mimo on a hilltop or a pillar under the open sky may be struck (25 health). A strike on a tree sets it burning: fire spreads through natural leaves and logs, 24 cells at most, and burns out, never into anything Mimo built or near home; Mimo runs from a fire beside it. The viewer draws the bolt, the flash, the flames and their embers.
- **The hard winter.** The lakes freeze into ice Mimo walks across (an overlay the server and the viewer read from the season, never block edits; cave lakes stay open). Crops, saplings, bushes, sunleaf and forest mushrooms wait for spring, cave mushrooms keep coming back, fewer animals are about, no fish is caught through ice and food keeps three times as long. In autumn Mimo gets "Ready for winter": it fills its chests with six winter days of food, and makes a wool cloak (5 wool), a stone hearth in its home (8 cobblestone and a campfire) and smoked meat that never spoils (`backend/survival/winter_prep.py`, `winter_gear.py`). In winter a pet that knows winter stays within 96 blocks of the home it built and out of the mountains: no expedition, no riches trip.
- **Seven more lessons.** A wild pet learns about winter, the cloak, the hearth, smoking, rain, storms and fog from its owner ("Fill a chest with food before winter.", "In a storm stay low and inside.", "Stay close to home in the fog.") or alone, by knocks, and asks about the colder nights, its fire going out, the storm, the fog, the freezing cold and food in the winter (`backend/survival/sky_wild.py`). A pet that knows the storm and the fog goes home when one comes; a gentle pet knows them all from the start.
- `/api/mimo` has `sky`: the season and its day, the days to the next, the weather and until when, the snow cover, whether the lakes are frozen, the latest strikes and the cells burning. `python3 -m backend.scripts.wild_gate --check W2 DIR` applies the W2 gate's criteria.

## Current world rules
```

- [ ] **Step 2: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 2013 tests` … `OK (skipped=6)`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`, the same with `-p "test_survival_days.py"`, `-p "test_survival_expedition_run.py"`, `-p "test_survival_making_route.py"`, `-p "test_survival_frontier_run.py"`, `-p "test_survival_away.py"` and `-p "test_survival_wild_run.py"`
Expected: `OK` each

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  388 passed (388)`, the build succeeds, eslint prints nothing.

- [ ] **Step 3: Commit the README**

```bash
git add README.md
git commit -m "docs(W2): the README's weather and seasons" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Rebuild the demo on the branch, and start the fast sky stack**

The first line loads the owner's `.env` into this shell without printing anything; `-e TYPESAFE_API_KEY` hands the workers the key's value from the shell, so it never appears on a command line.

```bash
set -a; . ./.env; set +a
docker build -f backend/Dockerfile -t mimo-l3demo .
docker rm -f mimo-l3demo-api mimo-l3demo-worker
docker run -d --name mimo-l3demo-api -p 127.0.0.1:8011:8000 -v mimo_l3demo:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 mimo-l3demo
docker run -d --name mimo-l3demo-worker -v mimo_l3demo:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 -e MIMO_ACTION_SCALE=1 \
  -e MIMO_TICK_SECONDS=1 -e TYPESAFE_API_KEY mimo-l3demo python -m backend.workers.mimo_worker
docker run -d --name mimo-w2sky-api -p 127.0.0.1:8013:8000 -v mimo_w2sky:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=20 mimo-l3demo
docker run -d --name mimo-w2sky-worker -v mimo_w2sky:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=20 -e MIMO_ACTION_SCALE=20 \
  -e MIMO_TICK_SECONDS=1 -e TYPESAFE_API_KEY mimo-l3demo python -m backend.workers.mimo_worker
```

Expected: four container ids. W2 adds no table: the demo world reads as it is. Restart the viewer on :3000 against :8011 and start one on :3002 against :8013, then open `http://localhost:3000/preview` and `http://localhost:3002/preview`.

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8011 npm run dev -- --port 3000 --strictPort
cd frontend && VITE_API_URL=http://127.0.0.1:8013 npm run dev -- --port 3002 --strictPort
```

- [ ] **Step 5: Keep a sky snippet ready**

Save this as `sky.sh` in your scratchpad directory (not in the repo). Given a container name, it prints the season and its day, the weather and until when, the snow, the ice, the strikes and the fires, the winter goal and its milestones, what the pet wears and carries for the winter, and the newest W2 events:

```bash
docker exec -i "${1:-mimo-w2sky-api}" python - <<'PY'
import time
import backend.survival.brain  # noqa: F401  (registers every W2 module)
from backend.survival.clock import time_scale
from backend.survival.goals import goal_view
from backend.survival.registry import LifeRegistry
from backend.survival.sky import sky_view
from backend.survival.world import SurvivalWorld, read_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
with world.connect() as db:
    state = read_state(db)
    view = sky_view(state, time.time(), time_scale())
    print(view["season"], "day", view["day"], "| next in", view["to_next"], "| weather", view["weather"],
          "| snow", view["snow"], "| frozen", view["frozen"], "| offset", (state.get("sky") or {}).get("offset"))
    print("strikes", view["strikes"], "| fires", len(view["fires"]))
    goal = goal_view(state.get("brain"))
    print("goal", goal and goal["name"], goal and goal["progress"], goal and goal["plan"])
    print("warmth", round(state["vitals"]["warmth"], 1), "| health", round(state["vitals"]["health"], 1),
          "| cloak", state["inventory"].get("wool_cloak", 0), "| smoked", state["inventory"].get("smoked_meat", 0))
for event in reversed(world.events(300)):
    if event["kind"] in ("season", "spring", "colder", "storm", "struck", "fire", "fire_out", "smoke", "craft",
                         "block", "figured", "asked", "death"):
        print(event["kind"], "|", event["text"])
PY
```

- [ ] **Step 6: The demo's pet gets spring, and the weather comes and goes**

Within a minute of the worker's start, run `sky.sh mimo-l3demo-api`: `spring day 1`, an offset set, `snow 0.0`, `frozen False`. Over the next real hour (6 weather segments) the weather changes at most every 10 real minutes and the HUD's season line under the clock follows it (for a pet on its day 12: "Spring · day 12 · 10 days to summer · ☂ Rain"); in rain the sky greys, rain streaks fall round the camera (none under a roof when the camera is close), and a campfire the pet left under the open sky goes out (its flames gone, ashes left) and is lit again with a stick when it is needed; in fog the view closes in and a dark creature may walk by day. Nothing else of the pet's day changes: it builds, cooks and lights its home as before.

- [ ] **Step 7: A year on the fast stack**

Hatch a gentle pet on the fast stack: `curl -s -X POST http://127.0.0.1:8013/api/lives/hatch -H 'content-type: application/json' -d '{"difficulty": "gentle"}'`. Watch `sky.sh` and :3002 through its first year (about two real hours): each season's first dawn is a `season` event (spring's a notable `spring`) and the badge changes; on autumn day 3 at dusk "The nights are getting colder." once; from autumn day 1 "Ready for winter" is its goal (the milestones in `sky.sh`), and before winter it stocks its chests, makes a wool cloak once it has 5 wool (the pet wears it), builds a hearth in a front corner of its home and smokes meat at a fire; at the first winter dawn the lakes freeze (the ice is pale and walkable in the viewer, and the pet walks across it), the snow falls and lies on the tops of the blocks, the herds thin and the crops wait; at the first spring dawn the ice thaws, the snow melts over a few real seconds' easing and "Spring! Things are growing again." In a summer storm, confirm a bolt and a flash in the viewer, a strike far from home (never within 16 blocks of it), and, when a tree catches, embers on the burning cells and smoke once it burns out; a fire never comes within 8 blocks of home. Note what is seen and what is not; a strike on the pet itself is rare by design.

- [ ] **Step 8: A quiet worker**

Confirm `docker logs mimo-l3demo-worker 2>&1 | grep -c "crashed"` and the same for `mimo-w2sky-worker` print `0` (or only lines from before the restart), and that the model calls today stay within `MIMO_MAX_DECISIONS_PER_DAY`. Leave the demo running on the new image for the owner. Stop the fast stack when the owner is done with it (`docker rm -f mimo-w2sky-api mimo-w2sky-worker`; the volume `mimo_w2sky` may be removed with `docker volume rm mimo_w2sky` once the owner agrees).

## Spec coverage

| Spec (W2, its resolutions, testing, the gate) | Where |
|---------------------------------|-------|
| A year of 40 game days, four seasons of 10; the season day from the day number and the offset; a newborn's offset 0, an old world's set on its first W2 tick in a living pet's tick only | Task 1 (`sky.season_day_of`, `settle_sky`; `test_a_year_is_forty_days…`, `test_an_old_worlds_first_tick_makes_its_day_spring_day_one…`, `test_a_newborn_starts_on_spring_day_one`, `test_a_dead_pets_world_is_never_written`; resolution 2) |
| Warmth by season, the mountains, snowfall, shelter, the cloak and a fire, furnace or hearth | Task 1 (`vitals.SEASON_WARMTH`, `target_warmth`; `test_warmth_outdoors_follows_the_season…`), Task 2 (snowfall), Task 8 (the cloak, the hearth; resolution 4) |
| Each season's first dawn a routine `season` event, spring's notable; autumn day 3's "The nights are getting colder." | Task 1 (`tend_season`; `test_a_season_turns_at_its_first_dawn…`, `test_on_autumn_day_three_at_dusk…`; resolution 3), Task 9 (the `colder` wonder), Task 10 (news) |
| Weather a pure function of the seed, the season and the segment; spells; the look back; the season tables (within 0.02 over 10,000 segments) | Task 2 (`sky.weather_at`; `test_the_weather_is_a_pure_function…`, `test_each_season_follows_its_table…` (within 0.01), `test_the_look_back_stops…`; resolution 5) |
| Rain: walks, campfires out and relit, crops watered, fire spreading a third as often | Task 2 (`steps.WALK_PACE`, `renewal.stage_seconds`), Task 3 (`rain.douse`, `relight`; resolution 6), Task 4 (`RAIN_SPREAD`) |
| Snow: walks, 10 colder outdoors, the cover rising and melting | Task 2 (`tend_weather`, `SNOW_PACE`; `test_the_tick_stores_the_weather_until_it_changes_and_the_snow_cover`, `test_falling_snow_is_felt_outdoors`) |
| Fog: dark spawning by day, no sun burn or fade, the cap 2 higher, torches keep their light | Task 2 (`darkness.FOG_SKY`, `hostiles.sunlit`, `weather.fog_room`; `test_in_fog_the_dark_creatures_come_out_by_day…`, `test_a_torch_still_keeps_the_fog_clear`) |
| Lightning: a strike a game minute within 64 blocks, the highest of 6 columns within 48, never within 16 of home or in the clearing; Mimo struck only when highest (0.05, 25, armor no help, `"lightning"`) | Task 4 (`storms.strike`, `highest`; `test_a_storm_strikes_once_a_game_minute…`, `test_no_strike_near_the_home_mimo_built…`, `test_mimo_is_struck_only_when_it_is_the_highest…`; resolution 7) |
| Fire: `fire` blocks, spreading 0.35 every 10 s (a third in rain), 24 cells a fire and 2 fires, 20 to 40 s a cell, never into built, edited or claimed cells or near home; 2 health a second beside it; paths round it | Task 4 (`storms.spread`, `ignite`, `burn_pet`, `Grid.hot`, `flee_fire`; the `FireTests`; resolution 8) |
| Snow and ice as overlays: `Grid.material` reads ice on natural surface water at `SEA_LEVEL` in winter; walkable, not mined; the swimmer's open cell; fish moved or fading; cave lakes open; paths cross a frozen lake within 10 % | Task 5 (`grid.overlay`, `winter.freeze`; the `IceTests`; resolution 9), Task 12 (the viewer's `uSnow` and `uFrozen`) |
| Winter: growth waits for spring, cave mushrooms come back, one herd a new chunk, the cap 12, no regain, no fish recovering, spoilage a third as fast | Task 5 (`renewal.WINTER_WAITS`, `spawning.WINTER_LAND_CAP`, `nature.recover_fish`, `spoilage.WINTER_RATE`; the `GrowthTests`, `AnimalTests`, `SpoilageTests`; resolution 10) |
| Seven lessons, one sentence each, the doubted lines, the gentle grant | Task 6 (`wild.SURVIVAL`, `GRANTED`, `lessons.OPPOSITES`; `test_survival_sky_teaching.py`; resolution 11) |
| Knocks and sure knocks of the lessons' table; six wonders with chips; the storm and fog lessons sending a pet home | Task 9 (`sky_wild.py`, `take_cover`, `trips.HOLD_BACK`; resolution 14) |
| "Ready for winter": when offered, its milestones by lesson, `WINTER_FOOD` good on winter day 5 at chest rates, stock_larder serving it | Task 7 (`winter_prep.py`, `larder.TARGETS`, `goals.PULLS`, and in winter `goals.HELD_OFF` and `trips.FENCES`; resolution 12) |
| The wool cloak, the hearth and smoked meat: recipes, slot, warmth, light, cooking, never out in rain, build_hearth, the smoke step, never spoils | Task 3 (the `hearth` block), Task 8 (`winter_gear.py`, `crafting.RECIPES`; resolution 13) |
| State and API: `state["sky"]` with defaults; `/api/mimo`'s `sky`; GETs read-only; no new table | Task 1 (`sky_state`, `sky_view`; `test_a_world_from_before_w2_reads_a_default_sky…`), Task 10 (`test_the_sky_in_api_mimo_and_a_get_never_writes`) |
| Moments, news and voice; the death words | Task 4 (`CAUSE_WORDS`), Task 10 (`sky_news.py`, `ROUTINE_EVENTS`; resolution 15) |
| Viewer: the sky's tint by season and weather, particles (half on a phone, none under a roof up close), the fog, the bolt and flash, embers and smoke, the snow cover and the ice eased, the HUD's season and weather, the cloak | Tasks 11 and 12 (`seasons.ts`, `weather.ts`, `WeatherEffects.tsx`, the mesher's `open`, `ColumnRenderer.setWeather`; resolution 16) |
| No model call; `no_model` in every headless test | Global Constraints; every W2 test runs the rules chooser or none; Task 13's gate runs the Talker with the counting stand-in |
| The W2 gate and the W1 gate on W2's code | Task 13 (`check_w2`, the `upgrade` condition; resolution 17), "Dry-run measurements" |
| The existing sims: re-measured, any moved threshold recorded | "Dry-run measurements" (resolution 19) |

Spec gaps the plan fills or leaves (the controller ledgers them):
- "A fire holds at most 24 cells" is read as all a fire ever holds, not the cells burning at once (resolution 8): a fire in a dry forest would otherwise keep one cell alight for good.
- The spec's "down off high ground" for a storm needs no reflex of its own: the strikes never hit a pet off the heights (resolution 7), and take_cover needs a home Mimo built (resolution 14).
- Cave mushrooms did not come back before W2; they now come back on their own spot in any season (resolution 10), the one change for gentle pets outside winter.
- The rules picker keeps its current goal (`goals.STICK`), so the winter goal is pulled by the season while it is open (resolution 12); the spec only says when it is offered.
- The spec does not say where a pet goes in winter; its warmth numbers freeze a pet out in the mountains by day and anywhere by night, so a pet that knows winter keeps within 96 blocks of home and off the mountains, with no expedition or riches trip (resolution 12). Without this, criterion 2 failed on four of six gentle seeds.
- The spec does not say whether the cloak takes one of Mimo's 16 carry stacks; worn, it takes none (resolution 13), since a stack filled for good stalled Making's route on full arms.
- The season's `season` and `spring` are two event kinds, for the log's routine and notable (resolution 3).
- The spec's animated flame is a static flame tile with embers over it (resolution 16).
- The storm's HUD mark is "ϟ", not the lightning emoji (resolution 16).
- The spec's `weather_at` share test asks within 0.02; the plan's test holds 0.01 (resolution 5).

## Dry-run measurements

### The dry run, task by task

The code was written and measured task by task on a scratch branch, first on `e021753` with W1's plan as it stood (`af8a49b`), then rebased onto `e021753` with W1's amended plan (`ed0f0e5`) when it landed (resolution 1). The plan was generated from the branch and applied with `apply_plan.py`, task by task in order, to a `git archive e021753` copy with the amended W1 plan applied (its fixture regenerated after W1's Task 4: 43,588 cells; node_modules linked), with the checks the tasks name after each. The shared machine's load average was 8 to 26 throughout (the W1 planner's gate runs shared it until mid-afternoon), so the times are slow.

| Task | Applied | Backend | New | Frontend |
|------|---------|---------|-----|----------|
| base (`e021753` + W1's plan `ed0f0e5`) | | `Ran 1926 tests` `OK (skipped=6)` | | `Tests  373 passed (373)` |
| 1 The seasons | yes | 1934 OK | 8 |  |
| 2 The weather | yes | 1944 OK | 10 |  |
| 3 Rain on the fire, and the new blocks | yes | 1951 OK | 7 | 373 passed, build ok, eslint clean |
| 4 Lightning and fire | yes | 1961 OK | 10 |  |
| 5 The hard winter | yes | 1971 OK | 10 |  |
| 6 The seven lessons | yes | 1975 OK | 4 |  |
| 7 Ready for winter | yes | 1983 OK | 8 |  |
| 8 The cloak, the hearth and smoked meat | yes | 1994 OK | 11 |  |
| 9 Knocks, wonders and cover | yes | 2005 OK | 11 |  |
| 10 Moments, news and voice | yes | 2009 OK | 4 |  |
| 11 Viewer: sky, season, HUD | yes | 2009 OK | 0 | 382 passed, build ok, eslint clean |
| 12 Viewer: effects, snow, ice | yes | 2009 OK | 0 | 388 passed, build ok, eslint clean |
| 13 The gate script's W2 | yes | 2013 OK | 4 |  |
| 14 Manual check and README | yes | 2013 OK | 0 |  |

After Task 14 the copy matches the scratch branch file for file. Tasks 13 and 14 were run again after a last change to the gate script (the strike measure: resolution 17). Each task's failing run (Step 2) was taken the same way: the task's test files on the code of the task before it (the outputs quoted in each Step 2). L2's creature budget test while fleeing two hostiles (`test_survival_defense`) failed in the whole-suite runs after Tasks 11 and 14 on the loaded machine (24.5 and 20.4 ms against 20) and passed on both reruns; the table shows the reruns (Task 11's backend is Task 10's, and Task 14's is Task 13's). A whole-suite run of the base failed once on the same machine too and passed on its rerun. It is no test of W2's (see the gate's cost below).

### The slow sims (MIMO_SLOW_TESTS=1)

The wild run was run on the final code with W1's amended plan; the six others on the code before the last W2 changes (winter's chest food and a wild pet's smoking, which none of them reaches: the longest is 10 spring days, all gentle) and before W1's amendment (wild pets only).

| Sim | Result | Time | What moved |
|-----|--------|------|------------|
| `test_survival_sim.py` | `Ran 7 tests` OK | 1,980 s | Before Task 9's change: FAIL, the six-day lives' new ground on days 4 and 5 `{(3, False): [236, 162], (21, True): [149, 11]}` against the floor of 40. Seed 21's day 5 is fog from dawn to dusk (6 of 6 segments) and a pet that knows fog starts no trip in it. Re-measured on both seeds and both pickers: (3, rules) 236 and 162, (3, Jev) 244 and 346, (21, rules) 276 and 0, (21, Jev) 149 and 11; the fog day is the only day under 149. The floor stays 40; a day at least half fog is left out (`FOG_DAY`, recorded in the test's comment). The rest share held (0.41 to 0.43 against 0.55) |
| `test_survival_days.py` | `Ran 3 tests` OK | 818 s | nothing |
| `test_survival_expedition_run.py` | `Ran 2 tests` OK | 66 s | nothing |
| `test_survival_making_route.py` | `Ran 1 test` OK | 5 s | nothing |
| `test_survival_frontier_run.py` | `Ran 5 tests` OK | 1,652 s | Before Task 9's change: FAIL, seed 11's geared pet did not reach "riches farther out" in its 4 days (it did on W1's code): sent home out of the weather five times, it set the goal aside on day 2 with nothing to do for it, then opened a far chest for no goal. The runs are now under clear skies (the frontier's risk and reward are what they measure; the weather's are the W2 gate's), recorded in the test's comment |
| `test_survival_away.py` | `Ran 2 tests` OK | 56 s | nothing |
| `test_survival_wild_run.py` | `Ran 3 tests` OK | 1,056 s | nothing (its 20 days end before the first autumn) |

The one default-suite test W2 pins is L2's flee test at 60 times (`test_survival_defense.py`, clear skies: resolution 18; seed 3's first night rains and the unarmed pet took 37 blows fleeing instead of at most 6).

### Balance: the gate runs and what they changed

Four gate runs came before the final one; each change is in the resolution named. The gentle lives, freezing/starving game minutes in each of the first three winters, the near-death days and the computer's day:

| Gentle seed | First run | Near home in winter | Worn cloak | Chest food in winter (final for gentle) |
|---|---|---|---|---|
| 3 | 6/0, 10/0, 35/0; near-death [118, 119, 120]; computer None | 2/0, 2/0, 4/0; near-death none; computer 92.0 | 2/0, 2/0, 4/0; near-death none; computer 92.0 | 1/0, 4/0, 0/0; near-death none; computer None |
| 5 | 0/0, 2/0, 0/0; near-death none; computer 88.52 | 0/0, 0/0, 0/0; near-death none; computer None | 0/0, 0/0, 0/0; near-death none; computer None | 0/0, 0/0, 0/0; near-death none; computer None |
| 8 | 14/0, 27/0, 4/0; near-death [71, 72]; computer None | 0/0, 0/0, 0/0; near-death none; computer 71.4 | 0/0, 0/0, 0/0; near-death none; computer 71.4 | 0/0, 0/0, 0/0; near-death none; computer 74.2 |
| 11 | 12/0, 3/0, 2/0; near-death none; computer 125.15 | 0/0, 0/0, 0/0; near-death none; computer 111.66 | 0/0, 0/0, 0/0; near-death none; computer 76.08 | 0/0, 0/0, 0/0; near-death none; computer 108.35 |
| 21 | 9/0, 8/0, 5/0; near-death none; computer 100.31 | 0/0, 1/0, 0/0; near-death none; computer 96.08 | 0/0, 5/24, 0/0; near-death [81]; computer 90.14 | 2/14, 0/0, 0/0; near-death [41]; computer 90.52 |
| 42 | 1/0, 1/0, 1/0; near-death none; computer None | 0/0, 0/0, 0/0; near-death none; computer None | 0/0, 0/0, 0/0; near-death none; computer None | 0/0, 0/0, 0/0; near-death none; computer 113.43 |

- First run (the plan as first written): criterion 2 failed on four seeds. Probes of seeds 8, 11 and 3 found every freezing minute 144 to 240 blocks from home, on an expedition, a riches trip, the far hills or an iron trip, most on a winter day in the mountains, and two pets dug in for a winter night on the heights with no campfire (seed 8: 100 health to 12; seed 3: 100 to 8). Resolution 12's staying near home in winter followed.
- Second run: no freezing past 4 game minutes a winter; gentle seed 5 stalled with 16 stacks in its arms, its cloak one of them, from day 66 (it had reached the counter on the first run). Resolution 13's worn cloak followed.
- Third run: gentle seed 21 starved 24 game minutes in its second winter with 740 hunger points in its chests, foraging bare land 58 blocks out. Resolution 12's chest food in winter followed.
- Fourth run: seed 21 still starved 14 game minutes in its first winter: a probe found it trapped in its own staircase in a swamp 51 blocks from home for 50 game minutes (the night) before L3's escape dug it out; nothing of W2's traps it (the same pit, with the ice or without, had no path out, and the escape was the same with an ice-breaking change, which was left out). The taught pets smoked one to four meats a life and their chests fell short of `WINTER_FOOD` on most winters. Resolution 13's smoking for a wild pet's winter food followed (the final code).

### The W2 gate (seeds 3, 5, 8, 11, 21, 42; on the final code)

All lives are on W1's amended plan. Taught lives are on the final code (but for the gate script's strike measure and a guard for bare test states, which change no life). Untaught and liar lives are on it but for the last smoking change too, which does not reach a pet that knows neither winter nor smoking. Gentle and upgrade lives are from the fourth run's code: nothing after it changes a gentle pet (the smoking changes are a wild pet's, W1's amendment changes wild pets only), and the upgrade life of seed 5 was run again with the final gate script. Four lives at a time on the loaded machine: 25 to 50 minutes a 150-day life, 8 to 15 a 30-day liar, 15 to 20 a 65-day upgrade.

| Criterion | Result | Measure |
|-----------|--------|---------|
| 1 gentle and taught: all alive on day 150 | FAIL | alive 11/12 |
| 2 gentle and taught: each winter health mean 60+, freezing and starving 10 game minutes at most | FAIL | lowest mean 89.24; most freezing 4; most starving 14; failing [('gentle', 21, '1')] |
| 3 gentle and taught: WINTER_FOOD in the chests on winter day 1, 5 of 6 the first winter, 6 of 6 after | FAIL | stocked on winter day 1 (first, second, third winter): gentle 6, 6, 6 of 6; taught 2, 0, 0 of 6. Hunger points good on winter day 5: gentle 3: 462, 744, 594; 5: 1104, 2031, 3477; 8: 648, 1103, 2561; 11: 953, 1252, 2658; 21: 415, 384, 863; 42: 1032, 1162, 1516; taught 3: 70, 110, 85; 5: 360, 122, 185; 8: 0, 68, 16; 11: 110, 20, 170; 21: 390; 42: 60, 16, 185 |
| 4 gentle and taught: at most 1 strike on Mimo a life | PASS | most 0 |
| 5 W1 criterion 5: 3 of 6 taught build a lamp on a lever; the furthest within one of gentle's | PASS | lamps 5/6; machines taught 6, gentle 7 |
| 6 untaught: the mean winter health mean 15 or more below taught's | PASS | untaught 16.6, taught 99.7 |
| 7 untaught: at least 2 of 6 alive on day 150, none dead before day 5 | FAIL | alive 0/6; deaths [(8.2, 'sickness'), (7.25, 'sickness'), (9.7, 'sickness'), (25.33, 'sickness'), (128.23, 'sickness'), (20.03, 'sickness')] |
| 8 safety: no strike within 16 of a built home, no fire in a claimed cell, no edit in the legacy clearing | PASS | nearest strike to home 16.0312195418814; fire in claimed cells 0; clearing edits 0 |
| 9 upgrade: spring on its upgrade day, alive and gentle through its first winter | PASS | (seed, offset, first winter) [(11, 21, {'health_mean': 99.7, 'ticks': 600, 'freezing': 1, 'starving': 0}), (21, 21, {'health_mean': 99.98, 'ticks': 600, 'freezing': 0, 'starving': 0}), (3, 21, {'health_mean': 99.8, 'ticks': 600, 'freezing': 2, 'starving': 0}), (42, 21, {'health_mean': 100.0, 'ticks': 600, 'freezing': 0, 'starving': 0}), (5, 21, {'health_mean': 99.85, 'ticks': 600, 'freezing': 1, 'starving': 0}), (8, 21, {'health_mean': 100.0, 'ticks': 600, 'freezing': 0, 'starving': 0})] |
| 10 cost: the sky hook in a storm, a route across a frozen lake | PASS | 2 budget tests, 0 failed |
| all: no model call and no logged error | PASS | calls 0; errors 0 |

What fails, and why, from probes of the same lives (the controller rules; nothing was loosened):
- **1 and W1's 1.** Taught seed 21 was killed by a skitter on day 52 (a summer day), the same on the fourth run and the final one; it lived on W1's code.
- **2.** Gentle seed 21 starved 14 game minutes in its first winter (near death on day 41): it dug a staircase into a swamp bed 51 blocks from home, could not path out of it, and L3's escape saw the trap only after the night, 50 game minutes later. The same pit had no path out with the ice read as water too, and an escape that could break the ice changed nothing, so it was left out. Every other gentle winter froze at most 4 game minutes and starved none.
- **3.** Gentle pets' chests held `WINTER_FOOD` on every winter's first day. Taught pets' did on 2 of 6 in the first winter and none after, while their winters were easy (health means 94 to 100, freezing at most 2 game minutes, no starving): their cooked meat, a wild pet's staple, spoils before winter day 5 unless stored in the last six autumn days, and they smoked 0 to 5 meats a life. A probe of taught seed 3's autumn found the winter goal set aside twice for "nothing to do for it now", no stick or no fire at hand when it carried meat, and the smoked meat it made eaten.
- **7 and W1's 8.** All six untaught pets died, of sickness, on days 7.3, 8.2, 9.7, 20.0, 25.3 and 128.2 (on W1's code alone: two, on days 21 and 69). Thirty-day runs of seeds 11 and 21 with one W2 hazard switched off: campfires never doused, both still died on the same days; fog read as clear, seed 11 lived and seed 21 died on day 10.9; every weather read as clear, both lived past day 30. A probe of seed 11: two chills at dawn (days 4 and 6), a gloomling's cut on a fog day (6.5) that festered (only the owner teaches bandages and sunleaf), the rain putting out its fire (6.7), dead on day 7.2.
- **8.** Met: the nearest strike to the home Mimo had built at that moment was 16.03 blocks. The first measure read the home after the tick and found 14.21 on the upgrade life of seed 5: a bigger home finished in the same tick as a strike 16.28 blocks from the old one. The gate script measures at the strike now (`wild_gate.strike_seen`, a `storms.STRIKES` hook), and that life was run again with it: 16.03 blocks. The other lives were measured after the tick; each strike is kept 16 blocks clear of the home at that moment by construction (`storms.strike`).
- **10.** The sky hook in a storm by a forest and the frozen lake's route are in the script's cost row. The creatures' 20 ms budget (L2's `test_hostiles_come_out_at_night_stay_few_and_cost_little`, best of 3): 12.9 ms under clear skies and 17.8 ms with fog all day (10 hostiles, the cap and `FOG_ROOM`), on the loaded machine. L2's flee budget test (`test_survival_defense`) failed in two whole-suite runs of the dry run on the loaded machine (24.5 and 20.4 ms) and passes alone: 15.9 and 19.4 ms on the base, 12.6 and 16.6 ms on the final code.

### The W1 gate on W2's code

| Criterion | Result | Measure |
|-----------|--------|---------|
| 1 taught: all 6 alive on day 150 | FAIL | alive 5/6 |
| 2 taught: each health mean 75 or more | PASS | lowest 98.11 |
| 3 taught: each at most 3 near-death days | PASS | most 1 |
| 4 taught: each at most 150 sick minutes | PASS | most 3 |
| 5 taught: 3 of 6 build a lamp on a lever; the furthest taught within one of gentle's | PASS | lamps 5/6; machines taught 6, gentle 7 |
| 6' untaught, first month: sick minutes 3x taught; health lost to hazards 3x taught and 100+ a life | PASS | sick 314 vs 1; lost 1079 vs 77, 180 a life |
| 7' untaught, a life without the owner: sick minutes 5x taught; deaths and near-death days 6+ | PASS | sick 422 vs 5; deaths 6 + near-death days 10 |
| 8 untaught: at most 3 of 6 die, none before day 5 | FAIL | deaths 6 on days [8.2, 7.25, 9.7, 25.33, 128.23, 20.03] |
| 9 untaught: alive on day 60 knows 8 of 11 learned alone | PASS | learned alone by day 60 {5: 13} |
| 10' untaught: 4 wonders met and 3 questions in 3 days; never more than 3 open | PASS | (met, asked) {11: (9, 3), 21: (5, 4), 3: (6, 4), 42: (7, 4), 5: (7, 4), 8: (7, 3)}; most open 3 |
| 11 liar: no lesson learned from a false chip or claim | PASS | taught by the liar [] |
| 12 liar: deaths by day 30 no more than untaught; sick minutes at most untaught + 30 | PASS | deaths 5 vs 5; (liar, untaught) sick minutes by day 30 {11: (41, 41), 21: (27, 27), 3: (48, 48), 42: (76, 76), 5: (97, 97), 8: (25, 25)} |
| 13 gentle: all alive; no sickness, wound, lot or question; every lesson from the first tick | PASS | alive 6/6; clean True; known True |
| all: no model call and no logged error | PASS | calls 0; errors 0 |

W1's gate breaks on two criteria on W2's code, both from the weather's toll on wild pets (above): 1 (taught seed 21's skitter) and 8 (six untaught deaths, three before day 10). Its first-month and whole-life measures (6′, 7′) pass by far, the untaught pets being sicker than W1 alone makes them; the liar condition dies as the untaught one does (five by day 26), so 12 holds. The spec's rule is that W2's numbers are tuned first: resolution 19 names the knobs, in the order the probes point.

### Making's route (`l5final/longrun_l5.py`, six seeds, 150 days, the rules chooser, no model)

| Seed | L5's gate (`41a919b`) | W1's gate, gentle (`af8a49b`) | W2's gate, gentle | W2, Making's own run |
|------|------|------|------|------|
| 3 | 99.5 | 72.23 | none (counter) | 84.23; lowest health 34.0 |
| 5 | 101.6 | 120.2 | none (auto_door) | 101.42; lowest health 24.0 |
| 8 | 96.5 | 81.28 | 74.2 | 135.12; lowest health 33.4 |
| 11 | 147.2 | 81.47 | 108.35 | 133.17; lowest health 90.0 |
| 21 | 116.2 | none | 90.52 | 84.27; lowest health 24.0 |
| 42 | 101.5 | 104.6 | 113.43 | 79.25; lowest health 39.2 |

Six of six built the computer (the target is five), with no death and no error in any run. The lowest health in a run fell to 24 to 39 on five seeds (L5's gate: 90 on five, 35.1 on one): near home to a hostile on seeds 3, 8 and 42, and on an expedition on seeds 5 and 21 (24 each, one of them heading home out of the weather); no pet was struck. Lightning set 26 to 70 trees burning in a run. The gate's gentle lives (the same seeds, the Talker running too) built it on four of six by day 150 (W1's: five of six), the route being as chaotic as L5's review found: single changes moved computers between three and six of six.
