# Wild World W1: A Newborn in a Wild World Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the owner's teaching the thing that keeps a young pet alive, as the owner asked ("i kinda want to make it hard for the pet to survive unless you talk to it and help teach it"). A life hatches wild or gentle, for good: the API hatches wild, `hatch()` stays gentle, and every world made before W1 reads gentle and is granted every survival lesson on its first tick, silently. A wild newborn knows instinct only. Eleven survival lessons (`wild:berries`, `wild:nightberries`, `wild:red_mushroom`, `wild:sunleaf`, `wild:bandage`, `wild:fire`, `wild:cooking`, `wild:keeping`, `wild:light`, `wild:shelter`, `wild:bed`) are journal lessons of their own kind, each taught in one sentence, and each unlocks what the spec's table says for a wild pet: the purposes, goals, recipes and fittings behind a campfire, cooking, a shelter with its door, a bed, torches round home, food kept in a chest, sunleaf and bandages. Five hazards come to a wild pet only: poison lookalikes (nightberries, which look like berries until Mimo learns them apart, and red mushrooms), sickness with symptoms and a remedy (a tummy ache and a chill, which drain health, stop healing and can kill, and sunleaf, which ends either), food that spoils in lots that follow every move, wounds that fester unless dressed, and cold nights that bring a chill at dawn. Mimo learns nine of the lessons alone by knocks, slowly and painfully; sunleaf and bandages only the owner can teach (the controller's ruling on the first dry run); and it asks: the wonders it meets become questions in its inbox and its chat, with answer chips, a bare yes or no in the chat answers a yes-or-no question, and it waits a while before it risks what it asked about. Wrong answers are doubted and never learned. Worldgen grows nightberry bushes and sunleaf on bare columns in both ports. The viewer shows what ails the pet, a "Wild" badge, Mimo's questions with their chips, a Survival section in the journal and what the memorial says of a life's lessons. A committed gate script runs the balance gate's lives headless.

**Architecture:** One low-level module, `backend/survival/wild.py`, holds the difficulty, the eleven lessons' table (with what the chat's parser needs of each), the gates (`unlocked`, `purpose_open`, `goal_open`, `fitting_open`), what a pet avoids eating (`avoided`) and the gentle pet's grant (`settle`, from the tick). It imports only memory, so any module may ask it whether a gate is open. The hazards are modules of their own that register into small hooks added to the modules they touch, as L5's did: `ailments.py` (the sickness and wound state, `Ailing` for the vitals step, cold nights and dawn, `DAWN`), `herbs.py` (take_herb, find_herb, gather_herbs, nibble), `meals.py` (a wild pet's meals through `purposes.MEALS`, its eating through `steps.EATING`, throw_out), `spoilage.py` (lots, aging, `SPOILS`), `wounds.py` (a blow's wound through `harm.BLOWS`, the `dress` step, dress_wound, the owner's bandage through `care.CARED`), `knocks.py` (learning alone, heard through `steps.OBSERVERS` and the hooks above), `wonders.py` (what the tick marks as met, and hesitation through `meals.HOLDS`), and on the Talker's side `questions.py` (the `ask_wonders` chore, chips, yes and no through `teaching.REWORDS`, closing through `teaching.TAUGHT_HOOKS` and the chat's "answer" question) and `wild_news.py` (Mind's moments and the inbox's news and danger). `lessons.py` learns the survival lessons' subjects, warnings and survival commands; `vitals.step_vitals` takes an `Ailing`; the tick settles the difficulty, runs the ailments, the cold night and the lots after each vitals step. Worldgen places the two plants in one new function in each port, checked by the regenerated fixture. The viewer gets a pure `frontend/src/survival/wild.ts` module. `backend/scripts/wild_gate.py` runs the gate's lives and checks the W1 criteria.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-27-wild-world-design.md` (`2060a3e`, amended with this plan's revision by resolution 29: sunleaf and bandages come only from the owner, the knock table, and gate criteria 6′, 7′ and 10′): the section "W1: A newborn in a wild world" and the W1 parts of "Resolutions" (1 to 12, 23 to 29), "Error handling and testing", "Balance gates" ("The harness", "W1 gate", "The existing sims") and "Risks" (1 to 5, 12). It builds on everything on the branch: the survival core, L1 to L5 with the L5 final fix wave (`e021753`), Bond and Mind and Making. W2 and W3 are planned later; this plan leaves every hook they need (`wild.GRANTED`, the survival table, `ailments.AILMENTS`, the gate script's `--check`).

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

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (`Ran 1828 tests` run at `e021753`: `OK (skipped=5)`; `Ran 1926 tests` `OK (skipped=6)` after Task 13)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_meals.py" -v`
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`, the same with `-p "test_survival_days.py"`, `-p "test_survival_expedition_run.py"`, `-p "test_survival_making_route.py"`, `-p "test_survival_frontier_run.py"`, `-p "test_survival_away.py"`, and (from Task 13) `-p "test_survival_wild_run.py"`
- The worldgen fixture: `python3 -m backend.scripts.worldgen_fixture` (rewrites `shared/worldgen-fixture.json`; about 15 seconds); the two parity suites: `python3 -m unittest discover -s backend/tests -p "test_worldgen*.py"` and `cd frontend && npx vitest run src/engine/worldgen.test.ts src/survival/overheadMap.test.ts`
- The gate (from Task 13): `python3 -m backend.scripts.wild_gate --days 150 --conditions gentle,untaught,taught --parallel 6 --out DIR`, then `--days 30 --conditions liar --parallel 6 --out DIR`, then `python3 -m backend.scripts.wild_gate --check W1 DIR`
- Frontend tests: `cd frontend && npm test` (366 pass at `e021753`; 373 after Task 12)
- One frontend test file: `cd frontend && npx vitest run src/survival/wild.test.ts`
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint src/survival src/engine` (prints nothing when clean)

Each task says how many tests it adds. If the starting totals differ (another fix wave lands first), expect the same increases on top of them.

Transcription: every edit is a fenced block, either a whole new file ("Create `path`:") or a "replace: … with: …" pair in a named file ("In `path`, replace:", then "and replace:" for more pairs in the same file). Old texts are kept short and unique in their file at the moment they are applied, so each task still applies when a neighbouring line changes. The fixture `shared/worldgen-fixture.json` is never transcribed: Task 4 regenerates it with the script. The dry run applied each task with the controller's apply script (`.superpowers/sdd/2026-09-26-making/apply_plan.py`) to a `git archive` copy of `e021753`, regenerated the fixture after Task 4, and ran the task's checks after each one; see resolution 1 and "Dry-run measurements".

## Plan-level resolutions

The spec leaves "the plan decides how" in several places. These are the details; every task follows them and the controller ledgers them.

1. **Base, order and dry run.** `e021753`: the branch after the L5 final fix wave (a furnace for every smelting chain, riches come home, loot leaves the arms, the fence and turn_back reflexes, loot kept only for a craft Mimo can make now, no ore past the readiness limit, no chest with nothing to spare as a target), on top of the spec's `2060a3e`. The plan was written on `2060a3e` and rebased as that wave landed while it was written (`94dad38`, `41a919b`, `5da9fba`, then `e021753`): the only anchor that moved was the reflex order in `test_survival_reflexes.py` (Task 5 now puts `take_herb` beside L5's `fence` at 45); everything else applied as it was. Task 4 also changes one line of L5's `test_survival_frontier_gear.py`, whose last block is no longer the warding lantern once the three plants follow it in `shared/blocks.json`. The brief's order is kept, with two moves so each task is testable on its own: Mind's teaching of the lessons (the parser) comes with the lessons themselves (Task 2), since registering them in `journal.LESSONS` without it would teach "sticks make torches" wrongly, and the plants come before the hazards (Task 4), since the lookalike hazard picks the new blocks. Dry run: each task applied in order with the apply script to a `git archive e021753` copy (node_modules linked), the fixture regenerated after Task 4, the task's checks run after each (the whole backend suite every time; the frontend's tests, build and eslint after Tasks 4 and 12), then the six slow sims and the wild run, a gentle seed's event log against the base's, and the gate; see "Dry-run measurements". The plan was revised after its first dry run by the controller's ruling (spec resolution 29, this plan's resolution 21), and every measure here is the revised plan's.
2. **One low-level module, then hooks** (Task 1). `wild.py` imports only `memory`, so every module may ask it a gate; nothing it holds needs the journal. The hazards register into hooks added to the modules they touch (`purposes.MEALS`, `steps.EATING` and `HERBS`, `meals.HOLDS`, `harm.BLOWS`, `care.CARED`, `ailments.DAWN`, `spoilage.SPOILS`, `teaching.REWORDS` and `TAUGHT_HOOKS`, `knocks.LEARNED`), each guarded and logged once. The spec's registry names (`wild.KNOCKS`, `wild.WONDERS`, `wild.AILMENTS`, `wild.PERISHABLE`) live beside the code that uses them: `knocks.KNOCKS`, `wonders.WONDERS`, `ailments.AILMENTS`, `spoilage.PERISHABLE`.
3. **Difficulty and the grant** (Task 1). `new_survival_state` writes `"difficulty"` (gentle unless told), `hatch(..., difficulty="gentle")` refuses anything else, and `POST /api/lives/hatch` takes an optional body `{"difficulty": "wild" | "gentle"}` defaulting to wild (no body: wild). `wild.settle`, first thing in each tick transaction of a living pet, writes `"gentle"` for a world with no key and grants a gentle pet the survival lessons once (`state["wild"]["granted"]` = 1, W1's version; W2 and W3 raise it and grant theirs the same way): two memory rows each, `"lesson"` and `"born_knowing"`, and nothing else: no event, no discovery, no memory, no choice, no journal line. `advance_world` still returns before any write for a dead world, so an archive is never written.
4. **Born-knowing lessons count for nothing** (Task 1). `Situation.lessons`, `journal.learned` (the journal's list and its payload's newest), the replies' "I learned something new" line and Mind's "I have learned 20 things" count all leave them out, so investigate's and tinker's facts, the journal payload and the thoughts read as before. The gates never need them: `unlocked` is open for any gentle pet whatever it knows.
5. **The survival lessons in the journal, listed apart** (Tasks 1, 2). They are `journal.LESSONS` entries of kind `"survival"`, so Mind's teaching, "from you" and "You were right" work unchanged, and the colon keeps them out of investigate. `/api/mimo` lists them apart, known or not, as `survival` (`{name, words, fact, known, source}`, source `"from_you"`, `"figured"` or `"from_start"`), and the journal's own list (`journal`) leaves them out, so the viewer's Survival section shows each once, with "?" for the unknown ones. Every journal entry gains `source` (Mind's `from_you` stays). The memorial's summary carries the life's `survival` list too.
6. **The parser** (Task 2). Each survival lesson names its own subjects (`Survival.subjects`: "red berries"; "nightberries", "purple berries", "dark berries"; "red mushrooms"; "sunleaf", "yellow herb"; "bandage"; "campfire"; "meat", "cooked meat", "cooked fish"; "food chest", "spoiled food"; "dark creatures"; "shelter"; "bed") instead of the words of its name and head word: "light" as a subject would widen to every "night" and "day", and "torch" would have doubted "sticks make torches". `named` reads the part after `wild:`. Each lesson also means a few words its fact does not say (`means`: "safe", "poison" and "eat" for the foods, so "Sunleaf is poison." is a claim to weigh), and the shelter's fact stands for warmth too (`sides`: "keeps out the cold" is not "keeps you cold"). TEACH_SYNONYMS gains purple/dark/night, herb/sunleaf, bandage/wrap, campfire/fire, torch/light, shelter/house/home, poison/poisonous/toxic, cook/cooked/cooking, festering/fester, sickness/sick/ill. OPPOSITES gains safe, fine, edible, cure, clean and heal against poison, poisonous, toxic and bad; raw against cooked; away against bring and attract; warm against cold. A warning ("don't eat", "do not eat", "never eat", "avoid", with or without "eat") followed by a poison lesson's subject reads as "<subject> are poison.", and one followed by raw meat or fish as "Cooked meat and fish are safe to eat." (`lessons.warned`, before the question check, since "Do not" opens like a question). A command still teaches nothing and doubts nothing, but it may teach a survival lesson whose words it fits with nothing wrong ("Cook your meat on a fire."); B2 still reads it as a request (`wants`).
7. **The gates** (Task 3). `purposes.is_valid` asks `wild.purpose_open` first (build_shelter, improve_home and camp need `wild:shelter`, light_up `wild:light`), `goals.is_open` asks `goal_open` (first_shelter needs shelter, safe_yard light: every other goal waits for first_shelter anyway), and `building.fittings_due` and the warm_up reflex ask `fitting_open` (a bed needs `wild:bed`, a campfire `wild:fire`, a door `wild:shelter`). The recipes are gated where they are planned: cook cooks raw food only with `wild:cooking` (bread is no lesson) and makes or puts down a campfire only with `wild:fire` (a carried furnace will do); the camp makes a campfire only with fire and sets torches only with light; the expedition packs a campfire only with fire and torches only with light, and goes without otherwise. The craft step itself is not gated: the owner may still craft for Mimo.
8. **The plants** (Task 4). `worldgen.wild_herb`, called in `plant_stack` only where tall grass's roll failed and nothing else grew, so no plant moves: a ripe nightberry bush on the berry bush's ground (meadow and forest-edge grass) one time in 150 (channel 160), else a sunleaf on grass, moss or mud in the meadow, forest, birch forest, taiga and swamp one time in 180 (channel 161); never within `LEGACY_RADIUS`. Measured over 160 × 160 columns of a generated world: 393 nightberry bushes to 682 berry bushes (0.58, about two for three), 461 sunleaf. Both blocks and the unripe bush are cutout plants, `replaceable` like tall grass. Picking a ripe bush gives 3 nightberries and leaves `nightberry_bush`, ripe again after `BERRY_REGROW`; a picked sunleaf comes back in its chunk like a mushroom, on its own ground, one a chunk a game day and at most 2. The fixture samples 6 columns of each (43,588 cells, was 43,540). The viewer paints a speckled bush (dark purple berries, a pale speck beside each) and a low rosette.
9. **Sickness** (Task 5). `ailments.fall_sick` keeps one sickness, the longer; `ailing` turns it into a `vitals.Ailing` (drain, hunger and energy rates, no healing, mood) the tick passes to `step_vitals`, whose damage map gains `"sickness"` (0 for a gentle pet, so its numbers are unchanged to the last bit); `tend` runs its time after each vitals step, a chill twice as fast while not working at warmth 60 or more. A sunleaf eaten (`steps.HERBS`, eaten as medicine and never as a meal) ends any sickness: "Pip ate sunleaf and felt better." (a `cured` event). The instinct's nibble is rolled once, when a sickness begins (`NIBBLE_CHANCE` 0.4, channel 200), so a sick pet that does not know sunleaf either wants the plant within 16 blocks all through that sickness or not at all; the nibble cures that sickness and teaches nothing (resolution 21). `gather_herbs` (52, a need) carries up to 2 once Mimo knows sunleaf. The death reads "Pip fell sick and never got better on day 9.".
10. **Meals** (Task 6). `purposes.meal_of` asks `MEALS` first, and the eat purpose (valid when a meal is non-empty, which for a gentle pet is exactly when it carries food) and the eat_now reflex both use it. A wild meal eats what it trusts first (familiar food and known-safe berries), tastes an untried food one serving at a time and only when starving or when hunger is under 50 with nothing it trusts and nothing holding it back, never eats sunleaf or spoiled food as a meal (spoiled food only when nothing else is left, hungry, without `wild:keeping`), and, knowing `wild:cooking`, eats raw food only when starving (a liar cannot make it skip cooking; resolution 6 of the spec). The red berries' share is rolled at plan time, a serving at a time with the counts left (channel 203). The meal's risk rides on its first raw serving and the running eat step carries it (`start_eat`), rolled once when it is eaten (channel 201). A food that made Mimo sick is not eaten again in that meal: `sick_from` drops the rest of its servings from the queue (of the whole group, for the red berries), so a meal of red berries ends at its first nightberry. `Situation.poisons` adds `wild.avoided`: for a gentle pet the nightberries it knows from the start (so it never picks or eats one, and its patches and finds never count them), for a wild pet the nightberries and red mushrooms it knows and the red berries while shunned. Learning's patches and exploring's finds read the same list (`wild.poisons_known`). A wild pet never learns "poisonous" the M4 way; its knocks teach it. Food a full pair of arms leaves behind is eaten on the spot only when it carries no risk at all (`wild.SAFE`), or, raw, when Mimo is starving, with the raw meal's roll once (`meals.eat_raw_left`): without that, a starving wild pet whose arms were full hunted again and again, left every piece of meat behind and starved (two untaught deaths in the re-run gate). `throw_out` (58, a need) drops the nightberries and red mushrooms it knows (and, from Task 7, spoiled food once it knows keeping).
11. **Lots** (Task 7). A chest's lots are kept beside its contents in their own key, `state["chest_lots"]["x,y,z"]`, because a list inside a chest's own dict would read as an item to every chest reader. Food added joins the newest lot when their wear is within a game minute's, else starts a lot; a fourth merges into the oldest. `settle_lots` repairs every lot toward the counts after each vitals step and each finished step (new food fresh, food gone from the most worn), so a path that moves food without a step (the owner's help, the arms' overflow, crafting and cooking, a chest mined) never leaves them out of step, and `observe_lots` carries a store's or take's lots across first. The tick ages Mimo's lots each vitals step and its chests' once a game minute; a spoiled lot is a routine `spoiled` event ("Pip's raw beef went bad."). Without `wild:keeping` a wild pet keeps its spare food on it (`storage.spare_food` is empty); `foods()` never counts spoiled food as food. Food that spoils while Mimo is eating it fails the eat step, as missing food always did (the `EATING` hook lets a `ValueError` through instead of logging it).
12. **Wounds** (Task 8). `harm.hurt_pet` runs `BLOWS` after each blow; `wounds.cut` opens one wound on 2 or more health lost (channel 204): "A skitter cut Pip.". The `dress` step (2 game s) takes a bandage or a sunleaf; `dress_wound` (76, a need) makes a bandage from wool first when it must. The owner's care bandage dresses the wound through `care.CARED`. An untaught pet knows neither the bandage nor sunleaf (resolution 21), so its wound festers until it heals by itself unless the owner dresses it. A wound's `age` counts game seconds in the tick, so its festering, healing and closing need no clock. A festering wound's drain is the cause `"sickness"` too.
13. **Cold nights** (Task 8). `ailments.tend_night`, after each vitals step of a wild pet: game seconds under 35 at night, any freezing, and time asleep on the floor of a sheltered spot (activity `sleeping`, sheltered), each counted in `state["wild"]`; at the step that crosses into dawn a chill is rolled (channel 205; a routine `chill` event "Pip caught a chill in the night."), a night of 5 game minutes or more asleep on the floor counts in `floor_nights`, and `DAWN` hears `{cold, froze, chill, blows, floor}`. Two routine events at dawn show two lessons true: "Pip slept soundly in its bed." (`rested`, 5 game minutes asleep in a bed) and "Pip spent a quiet night at home." (`safe_night`, no blow that night and within 8 blocks of the home it built).
14. **Knocks** (Task 9). As the spec's table, heard where they happen (eat and smelt steps through `steps.OBSERVERS`; blows through `harm.BLOWS`; nights through `ailments.DAWN`; spoiled food through `SPOILS`), for nine lessons: `knocks.OWNER_ONLY` (sunleaf, bandage) are never worked out (resolution 21). A lesson worked out is learned as the journal learns, with memory's second fact `"figured"`, a notable `figured` event, a discovery for curiosity (never below `curiosity.GROUND_FLOOR`, as `learn_lesson`), a new choice, and the journal line "I worked it out myself: …". Knowing the nightberries lifts the red berries' shun at once. Each lesson rolls on its own channel (206 + its place in the table). "Stands within 8 blocks of a fire it did not make" is W2's and W3's and is not wired yet.
15. **Wonders** (Task 10). The tick marks them met (`wonders.meet` from `brain.notice_step`, and `sighted` after a walk); the food it met fills Mimo's words ("those berries", "raw beef", "A skitter", " north of home" from `exploring.compass`). A wonder is met whatever Mimo knows; it is asked only when some of its lessons are unknown. Each wonder has a false chip or, for the liar, a false claim for the chat (the doubted lines of the teaching table, and "Spoiled food is safe to eat." for keeping, which the table gives none). Hesitation (`meals.HOLDS`) holds a taste of an untried food while its wonder was asked less than `HESITATE` ago, or met and not asked while fewer than 3 are open; starving tastes at once.
16. **Questions** (Task 10). The Talker's `ask_wonders` chore (after the mirrors) first closes as `"figured"` every open question whose lessons Mimo now knows, then asks the oldest wonder met within the caps. The chips' order is a seeded sort (channel 220) stored as `order`, so an answer's index maps back to the wonder's own chip and only the index is stored. `POST /api/mimo/inbox/{id}/answer` takes `{"text"}` or `{"choice"}` (exactly one; 400 otherwise). A taught chip teaches through `teaching.teach_lesson` (so "from you", the told memory and "You were right" follow) and says "Oh, <fact> Thank you for teaching me!"; a false one closes as doubted with "Hmm, I'm not sure that's right. I'll be careful."; one that teaches nothing closes as noted ("Okay. Thanks for telling me."). A bare yes or no is read through `teaching.REWORDS` as the newest open yes-or-no question's claim when the line names no lesson's subject; the chat's "answer" question (one option, never asked of a model) and its keeper close, as doubted and with the careful line, the bound question or the open questions about what a doubted claim names. Any lesson taught closes the questions it answers as taught (`teaching.TAUGHT_HOOKS`). `/api/mimo`'s inbox gains `questions` (`{id, at, text, chips, yes_no}`), oldest first.
17. **Moments, news and voice** (Task 11). Mind's moments as the spec's table (`figured` a lesson), `asked` about the owner so it never reaches Luna; the inbox tells what Mimo worked out as news ("I worked it out myself: cooking makes meat safe.", kind `report`) and a festering wound, a chill or a sickness as danger, each kind at most once a game day. `cured`, `dressed`, `spoiled`, `asked`, `rested` and `safe_night` are routine events; `figured`, `wound`, `festering`, `chill` and `sick` are notable. `teaching.SEEN_BY` says which events show each survival lesson true (berries eaten, meat cooked, a campfire crafted, a cure or a dressing with sunleaf, a bandage, a shelter built and moved into, `rested`, `safe_night`); the other lessons keep their seeing kinds exactly. The voice table test's allowed things gain "worked it out" (its "it" is the lesson, not Mimo).
18. **The viewer** (Task 12). A pure `wild.ts` (the ailment line, the badge, the questions' count, a closed question's words, the survival entries and the memorial's tally, the pet's tint, droop, hop, shiver, wrap, mark and "?" bubble), the chips as buttons in the inbox, "?" count beside the inbox button (it opens the inbox), the ailment line and the "Wild" badge on the HUD, a Survival section at the top of the journal, the memorial's line of lessons and its words for a death by sickness, the new purposes' and reflex's words, and the new items' colours. The pet's droop is a slight forward tilt (the pet model has no separate ears).
19. **The gate script** (Task 13). `backend/scripts/wild_gate.py`, as the spec's harness: one life per process, the scripted owner through `talk.owner_says` and `questions.answer_question`, the liar, a summary per life, `--parallel`, `--check W1`. Sick minutes, near-death days and the health mean are sampled once a tick (a game minute); a life's health mean is over the time it lived. A life is born on day 1.0, so criterion 10′'s first 3 game days run to day 4.0 and a wonder met at the third dawn counts, and criterion 6′'s first month is game days 1 to 30. The health lost to hazards is `state["wild"]["lost"]`, which `ailments.lose` counts: the drain of a sickness or a festering wound (after each vitals step, in `tend`) and a poison plant's 5 (in `eat_wild`); the gate samples it each game day. `check_w1` has a unit test on made-up summaries for 6′, 7′ and 10′. Its unit test runs one short life of each kind with the `no_model` stub, and the slow one two 20-day lives of each.
20. **Balance** (the dry run). The knobs moved in the spec's order, twice: on the plan as first written, then on its revision (resolution 21). Each move was measured on the six seeds' untaught lives; the taught pets were never sick more than 3 game minutes in any run. **First written.** With the spec's values a 40-day gate gave untaught sick minutes 312 in all, no near-death day and a health mean of 98.2 against 100.0. Raw-meal chances 0.35, 0.2 and 0.1 went to **0.5, 0.35 and 0.2** (raw chicken; beef, mutton and rabbit; fish; kept); `CHILL_BELOW` 35 to 45 changed nothing (a sheltered pet's night warmth settles at 75, and an unsheltered one falls through 45 and 35 within 20 game seconds; put back to **35**); the drains were doubled (a tummy ache 1 health per 45 game s to 25, a chill 60 to **30**, a festering wound 90 to 45; kept); knock chances two steps lower killed a pet on day 6 and were put back. The 150-day gate on those numbers failed the first criteria 6, 7 and 10: an untaught pet worked out 6 to 9 lessons in about three game weeks, among them sunleaf (a nibble while sick taught it for sure), and was rarely sick after. The controller's ruling followed (resolution 21). **The revision.** With sunleaf and bandages owner-only and the first knock chances: 2 deaths (a skitter on day 7; starvation on day 117, the bug in (a)) and 2 near-death days, so 7′ at 4; every pet alive on day 60 knew exactly 8 lessons alone. (a) Knock chances two steps (0.10) lower: two pets alive on day 60 knew 6 and 7 lessons alone (criterion 9 fails); **one step (0.05) lower**: every pet knew 8 (kept). Both of that run's deaths were starvation, from a bug the revision exposed (resolution 10: a starving pet with full arms left all the meat it hunted behind); fixed, the same run gave 1 death and 4 near-death days, 7′ at 5. (b) Raw-meal chances two steps higher (0.6, 0.45, 0.3): 7′ fell to 1; put back. (c) `CHILL_BELOW`: not moved again. (d) The drains: a tummy ache 1 per 15 game s, a chill 1 per 20 and festering 1 per 36 killed 5 pets, four of them by day 31 (criterion 8 fails); 1 per 20, 1 per 25 and 1 per 40 killed 3 on days 9, 12 and 21 and left a pet with 7 lessons alone by day 60 (criterion 9 fails); **a tummy ache 1 per 20 (36 health a bout), a chill 1 per 30 as before (50) and festering 1 per 40 (75 over a day)**: 2 deaths (days 21 and 69) and 5 near-death days, 7′ at 7, with 8 and 9 passing; kept. The chill's drain is the one at its limit: one step more (1 per 25) is what killed three pets in their first three weeks. Final numbers: the knock chances of resolution 21, raw-meal chances 0.5, 0.35 and 0.2, `CHILL_BELOW` 35, a tummy ache 1 health per 20 game s, a chill 1 per 30, a festering wound 1 per 40. The gate on them is in "Dry-run measurements".
21. **Sunleaf and bandages come only from the owner; the gate measures a newborn's first month and a life without the owner** (spec resolution 29: the controller's ruling on this plan's first dry run, `.superpowers/sdd/2026-09-27-wild-world-w1/replan-ruling.md`). `knocks.OWNER_ONLY = ("sunleaf", "bandage")`: `figure` refuses them and `knock` knows no chance for them, so the first plan's sure knock for a sunleaf eaten while sick and its knock for a wound festering while Mimo carries wool are gone, and with them the `ailments.FESTERS` hook, which nothing else heard. A nibble still cures that one sickness ("That's better. I feel well again.", no longer "Sunleaf really works."), and the wonders, their chips, the chat and Mind's teaching still teach both. The seven knock chances are one step (0.05) lower than first planned (nightberries 0.25, fire 0.15, cooking 0.25, keeping 0.20, light 0.10, shelter 0.25, bed 0.10; the steps unchanged); a second step lower left two untaught pets with 6 and 7 lessons alone by day 60 (criterion 9). The gate's new measure, the health lost to hazards, is `state["wild"]["lost"]` (resolution 19), and `check_w1` reads criteria 6′, 7′ and 10′ as the spec now words them; the others are unchanged. The measures are in resolution 20 and "Dry-run measurements".

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/survival/wild.py` | Create | Difficulty, the eleven survival lessons (words, fact, what each unlocks, the parser's subjects), the gates, what a pet avoids eating, the gentle grant, the payload's `survival` |
| `backend/survival/ailments.py` | Create | One sickness and one wound, `Ailing` for the vitals step, sunleaf's cure, cold nights and dawn (`DAWN`), the health lost to hazards (`lose`), the payload's `ailments` |
| `backend/survival/herbs.py` | Create | take_herb (reflex 45), find_herb (75), gather_herbs (52), the instinct's nibble (70) |
| `backend/survival/meals.py` | Create | A wild pet's meals (`purposes.MEALS`), its eating (`steps.EATING`), the red berries' share, raw meals, shun, `HOLDS`, throw_out |
| `backend/survival/spoilage.py` | Create | Lots in the arms and in each chest, aging, spoiling (`SPOILS`), `observe_lots`, keeping's help to cook and store |
| `backend/survival/wounds.py` | Create | A blow's wound (`harm.BLOWS`), the `dress` step, dress_wound (76), the owner's bandage (`care.CARED`) |
| `backend/survival/knocks.py` | Create | Learning alone: the knock table for nine lessons, sure knocks, the owner-only lessons (`OWNER_ONLY`), `figure`, where each knock is heard, `LEARNED` |
| `backend/survival/wonders.py` | Create | The ten wonders with their chips and claims, what the tick marks as met, hesitation (`meals.HOLDS`) |
| `backend/survival/questions.py` | Create | The Talker's `ask_wonders` chore, answering by chip (`answer_question`), yes and no, closing, the inbox's `questions` |
| `backend/survival/wild_news.py` | Create | Mind's moments and the inbox's news and danger for W1's events |
| `backend/survival/{journal,lessons,teaching}.py` | Modify | The survival lessons in the journal, the parser's subjects, synonyms, opposites, warnings and survival commands; `REWORDS`, `TAUGHT_HOOKS`, `SEEN_BY` |
| `backend/survival/{purposes,goals,building,cooking,camp,expedition,reflexes,storage,carrying,learning,exploring,senses,situation}.py` | Modify | The gates, `MEALS` and `meal_of`, keeping's store and cook, what a wild pet avoids |
| `backend/survival/{vitals,steps,tick,snapshot,hatch,registry,world,insights,replies,brain,bonding,bond_view,care}.py`, `backend/survival/creatures/harm.py` | Modify | `Ailing` and the cause "sickness"; `EATING`, `HERBS`; the tick's settle, ailments, cold night and lots; the payload; the difficulty at hatch; the born-knowing tallies; hooks and imports |
| `backend/api/{lives,bond}.py` | Modify | `POST /api/lives/hatch` with `{"difficulty"}`; the answer endpoint's `{"choice"}` |
| `backend/services/{worldgen,crafting}.py`, `frontend/src/engine/{worldgen,atlas}.ts`, `shared/blocks.json` | Modify | Nightberry bushes and sunleaf in both ports; the three blocks; the bandage recipe |
| `backend/survival/{nature,renewal}.py`, `backend/scripts/worldgen_fixture.py`, `shared/worldgen-fixture.json` | Modify | Picking and regrowth; the fixture (regenerated) |
| `backend/scripts/wild_gate.py` | Create | The gate's lives and the W1 criteria |
| `backend/tests/test_survival_{wild,wild_teaching,wild_gates,ailments,meals,spoilage,wounds,knocks,questions,wild_news,wild_run}.py`, `backend/tests/test_worldgen_wild.py` | Create | One test file per new module or area, and the headless run |
| `backend/tests/test_survival_{lessons,reflexes,frontier_gear,voice,mind_privacy}.py` | Modify | What W1 changes in them |
| `frontend/src/survival/wild.ts` (+ test) | Create | The ailment line, the badge, the questions' count, the survival entries, the memorial's tally, the pet's look |
| `frontend/src/survival/{types,bondTypes,bond,hud,animation,creatures,BondBar,InboxPanel,JournalPanel,Memorial,SurvivalHud,SurvivalPet,SurvivalWorld,WorldCanvas}.ts(x)`, `frontend/src/engine/{blocks,worldgen}.test.ts`, `frontend/src/survival/{bond,hud}.test.ts` | Modify | The stream's new fields, the chips, the HUD, the journal, the memorial, the pet, words and colours |
| `README.md` | Modify | Wild World |

## Tasks

1. Difficulty and grandfathering
2. The survival lessons, taught in one sentence
3. The gates
4. Nightberries and sunleaf in worldgen, in both ports
5. Sickness and sunleaf
6. What a wild pet eats: untried foods, the lookalike, poison and raw meals
7. Food that spoils
8. Wounds and cold nights
9. Learning alone: knocks
10. Mimo's questions: wonders, chips, yes and no
11. Moments, news and voice
12. Viewer: ailments, the badge, questions and chips, the Survival section, the memorial
13. The gate script
14. Manual check on the demo and the README

Tasks 1–11 and 13 are the backend (Task 4 also the worldgen port and its textures) and 12 the viewer. Task 2 needs Task 1; Task 3 needs Task 2; Task 4 stands alone; Task 5 needs Task 4's sunleaf; Task 6 needs Tasks 1, 4 and 5; Task 7 needs Task 6; Task 8 needs Task 5; Task 9 needs Tasks 5 to 8; Task 10 needs Tasks 2 and 9; Task 11 needs Tasks 9 and 10; Task 12 needs the payload of Tasks 1, 5, 8 and 10; Task 13 needs all of them.

---

### Task 1: Difficulty and grandfathering

**Files:**
- Create: `backend/survival/wild.py`
- Modify: `backend/survival/world.py` (`new_survival_state(difficulty)`), `backend/survival/hatch.py` (`hatch(..., difficulty)`), `backend/survival/registry.py` (`create_life(difficulty)`), `backend/api/lives.py` (`Hatching`), `backend/survival/tick.py` (`settle`), `backend/survival/snapshot.py` (`difficulty`, `survival`), `backend/survival/journal.py` (born-knowing left out, `source`), `backend/survival/situation.py`, `backend/survival/insights.py`, `backend/survival/replies.py` (born-knowing left out)
- Test: `backend/tests/test_survival_wild.py`

**Interfaces:**
- Consumes: `memory.know`, `memory.known`; `journal.FACT`, `journal.TAUGHT`; the tick's transaction (`advance_world`).
- Produces:
  - `wild.WILD = "wild"`, `GENTLE = "gentle"`, `DIFFICULTIES`, `PREFIX = "wild:"`, `KIND = "survival"`, `BORN_KNOWING = "born_knowing"`, `FIGURED = "figured"`, `GRANTED = 1`; `Survival(name, words, fact, unlocks, figured)` and the table `SURVIVAL` (11), `BY_NAME`; `thing(name) -> "wild:<name>"`, `difficulty(state)`, `is_wild(state)`, `knows(s, name)`, `unlocked(s, name)` (open for a gentle pet), `wild_state(state)` (the defaults of `state["wild"]`), `settle(state, db, at)` (the difficulty and the gentle grant), `born_knowing(db)`, `learned_lessons(db)`, `source_of(facts)`, `survival_view(db) -> [{name, words, fact, known, source}]`.
  - `hatch(registry, rng, timestamp=None, difficulty="gentle")`; `LifeRegistry.create_life(..., difficulty)`; `POST /api/lives/hatch` takes an optional `{"difficulty": "wild" | "gentle"}`, wild by default.
  - `/api/mimo` gains `difficulty` and `survival`; every journal entry gains `source`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_wild.py`:

```python
import os
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api.lives import Hatching, hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.brain import BRAIN
from backend.survival.hatch import hatch
from backend.survival.insights import insights
from backend.survival.journal import journal_payload, journal_view, learned
from backend.survival.memory import create_memory_tables, know
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.tick import tick_life
from backend.survival.wild import (
    BORN_KNOWING, GENTLE, SURVIVAL, WILD, difficulty, is_wild, settle, survival_view, thing, unlocked,
)
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_pickers import situation

BORN = 1_000_000.0


class Lives:
    """A fresh registry in a temporary directory."""

    def __init__(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")

    def hatch(self, seed=8, **kwargs):
        life = hatch(self.registry, random.Random(seed), timestamp=BORN, **kwargs)
        return life, SurvivalWorld(self.registry.world_path(life))


class DifficultyTests(unittest.TestCase):
    def setUp(self):
        self.lives = Lives()

    def tearDown(self):
        self.lives.directory.cleanup()

    def test_hatch_is_gentle_unless_told_and_a_life_is_wild_or_gentle(self):
        with self.assertRaises(ValueError):
            self.lives.hatch(difficulty="hard")
        _, world = self.lives.hatch()
        self.assertEqual(world.state()["difficulty"], GENTLE)

    def test_a_world_from_before_w1_reads_gentle_and_its_first_tick_writes_it(self):
        _, world = self.lives.hatch()
        with world.transaction() as db:
            state = read_state(db)
            del state["difficulty"]
            write_state(db, state)
        self.assertEqual(difficulty(world.state()), GENTLE)
        self.assertFalse(is_wild(world.state()))
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)
        self.assertEqual(world.state()["difficulty"], GENTLE)

    def test_a_gentle_pet_is_granted_every_survival_lesson_on_its_first_tick_silently(self):
        _, world = self.lives.hatch()
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)
        with world.connect() as db:
            rows = {tuple(row) for row in db.execute("SELECT subject, fact FROM memory_knowledge WHERE subject LIKE 'wild:%'")}
            memories = db.execute("SELECT COUNT(*) FROM mind_memories").fetchone()[0]
            view = survival_view(db)
        self.assertEqual(rows, {(thing(lesson.name), fact) for lesson in SURVIVAL for fact in ("lesson", BORN_KNOWING)})
        self.assertEqual(memories, 0)
        self.assertEqual({entry["source"] for entry in view}, {"from_start"})
        self.assertFalse(any(event["kind"] in ("learned", "figured") for event in world.events(100)))
        self.assertEqual(world.state()["wild"], {"granted": 1})
        tick_life(self.lives.registry, BORN + 2, scale=1.0, mind=BRAIN)  # granted once
        self.assertEqual(world.state()["wild"], {"granted": 1})

    def test_a_wild_pet_is_granted_nothing_and_knows_only_instinct(self):
        _, world = self.lives.hatch(difficulty=WILD)
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)
        with world.connect() as db:
            view = survival_view(db)
        self.assertEqual(world.state()["difficulty"], WILD)
        self.assertEqual([entry["known"] for entry in view], [False] * len(SURVIVAL))
        self.assertIsNone(view[0]["source"])

    def test_a_dead_pets_world_is_never_written(self):
        _, world = self.lives.hatch()
        with world.transaction() as db:
            state = read_state(db)
            del state["difficulty"]
            state.update(died_at=BORN + 0.5, cause="starvation")
            write_state(db, state)
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)
        self.assertNotIn("difficulty", world.state())
        with world.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_knowledge").fetchone()[0], 0)

    def test_settle_leaves_a_wild_pet_and_a_granted_pet_alone(self):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        wild = {"difficulty": WILD}
        settle(wild, db, 1.0)
        self.assertEqual(wild, {"difficulty": WILD})
        gentle = {"wild": {"granted": 1}}
        settle(gentle, db, 1.0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_knowledge").fetchone()[0], 0)


class LessonTests(unittest.TestCase):
    def test_a_gate_is_open_for_a_gentle_pet_and_for_a_wild_one_that_knows(self):
        gentle = situation()
        self.assertTrue(unlocked(gentle, "fire"))
        wild = situation()
        wild.state["difficulty"] = WILD
        self.assertFalse(unlocked(wild, "fire"))
        know(wild.db, "wild:fire", "lesson", 1.0)
        taught = situation()
        taught.state["difficulty"] = WILD
        taught.db = wild.db
        self.assertTrue(unlocked(taught, "fire"))
        self.assertFalse(unlocked(taught, "shelter"))


class BornKnowingTests(unittest.TestCase):
    """Lessons known from birth never count as lessons learned."""

    def setUp(self):
        self.lives = Lives()
        _, self.world = self.lives.hatch()
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)

    def tearDown(self):
        self.lives.directory.cleanup()

    def test_the_journal_the_situation_and_the_thoughts_leave_them_out(self):
        with self.world.transaction() as db:
            know(db, "gravel", "lesson", BORN + 2)
            state = read_state(db)
            s = from_db(db, state, BORN + 3, 1.0)
            self.assertEqual(s.lessons, ("gravel",))
            self.assertEqual([name for name, _ in learned(db)], ["gravel"])
            self.assertEqual([entry["thing"] for entry in journal_view(db, state.get("brain"))], ["gravel"])
            self.assertEqual(journal_view(db, None)[0]["source"], "figured")
            self.assertEqual(journal_payload(s)["lessons"], 1)
            self.assertFalse(any(insight.key.startswith("learned:") for insight in insights(db, state, 1, 1.0)))


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

    def test_the_api_hatches_wild_by_default_and_gentle_when_asked(self):
        hatch_egg()
        mimo = get_mimo()
        self.assertEqual(mimo["difficulty"], WILD)
        self.assertEqual(len(mimo["survival"]), 11)
        registry = LifeRegistry()
        registry.mark_dead(registry.active_life()["id"], BORN, "starvation")
        hatch_egg(Hatching(difficulty="gentle"))
        self.assertEqual(get_mimo()["difficulty"], GENTLE)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild.py"`
Expected: ERROR: `ImportError: cannot import name 'Hatching' from 'backend.api.lives'`

- [ ] **Step 3: Difficulty, the lessons' table and the grant**

In `backend/api/lives.py`, replace:

```python

from fastapi import APIRouter, HTTPException, Query
```

with:

```python
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
```

and replace:

```python
@router.post("/lives/hatch")
def hatch_egg():
    registry = open_registry()
    try:
        life = hatch(registry)
```

with:

```python
class Hatching(BaseModel):
    difficulty: Literal["wild", "gentle"] = "wild"  # W1: a new egg hatches wild unless asked otherwise


@router.post("/lives/hatch")
def hatch_egg(request: Hatching | None = None):
    registry = open_registry()
    try:
        life = hatch(registry, difficulty=(request or Hatching()).difficulty)
```

In `backend/survival/hatch.py`, replace:

```python
"""Hatch the pending egg into a new life: new seed, spawn point, traits, name and world."""
```

with:

```python
"""Hatch the pending egg into a new life: new seed, spawn point, traits, name and world.

W1: a life hatches "wild" or "gentle" (backend.survival.wild). This function hatches gentle unless told
otherwise, so every test that hatches a pet measures what it always measured; the API hatches wild
(backend.api.lives)."""
```

and replace:

```python


def hatch(registry: LifeRegistry, rng: random.Random | None = None, timestamp: float | None = None) -> dict:
```

with:

```python
from backend.survival.wild import DIFFICULTIES, GENTLE


def hatch(registry: LifeRegistry, rng: random.Random | None = None, timestamp: float | None = None,
          difficulty: str = GENTLE) -> dict:
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"A life is wild or gentle, not {difficulty!r}")
```

and replace:

```python
                                born_at=timestamp, egg=egg, traits=roll_traits(egg, rng))
```

with:

```python
                                born_at=timestamp, egg=egg, traits=roll_traits(egg, rng), difficulty=difficulty)
```

In `backend/survival/insights.py`, replace:

```python
    lessons = db.execute("SELECT COUNT(*) FROM memory_knowledge WHERE fact=?", (LESSON,)).fetchone()[0] // 10 * 10
```

with:

```python
    lessons = db.execute("SELECT COUNT(*) FROM memory_knowledge WHERE fact=? AND subject NOT IN (SELECT subject FROM "
                         "memory_knowledge WHERE fact='born_knowing')", (LESSON,)).fetchone()[0] // 10 * 10  # W1
```

In `backend/survival/journal.py`, replace:

```python
from backend.survival.triggers import ensure_brain, mark_trigger
```

with:

```python
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.wild import BORN_KNOWING
```

and replace:

```python
    """The lessons Mimo learned, (thing, when), first first."""
    rows = db.execute("SELECT subject, learned_at FROM memory_knowledge WHERE fact=? ORDER BY learned_at, subject",
                      (FACT,)).fetchall()
```

with:

```python
    """The lessons Mimo learned, (thing, when), first first; W1: not those it knew from the start."""
    rows = db.execute("SELECT subject, learned_at FROM memory_knowledge WHERE fact=? AND subject NOT IN "
                      "(SELECT subject FROM memory_knowledge WHERE fact=?) ORDER BY learned_at, subject",
                      (FACT, BORN_KNOWING)).fetchall()
```

and replace:

```python
    unlocks, at, from_you (Mind M2: the owner taught it)}. A world from before L3 read as an archive
    has learned nothing."""
```

with:

```python
    unlocks, at, from_you (Mind M2: the owner taught it), source (W1: "from_you", "figured" or
    "from_start")}. A world from before L3 read as an archive has learned nothing."""
```

and replace:

```python
    for thing, at in reversed(rows):
        lesson = LESSONS.get(thing)
        if lesson is None:
            continue
        found.append({"thing": thing, "kind": lesson.kind, "words": lesson.words, "fact": lesson.fact,
                      "line": words.get(thing) or lesson.fact, "unlocks": lesson.unlocks, "at": at,
                      "from_you": thing in from_owner})
```

with:

```python
    for name, at in reversed(rows):
        lesson = LESSONS.get(name)
        if lesson is None:
            continue
        found.append({"thing": name, "kind": lesson.kind, "words": lesson.words, "fact": lesson.fact,
                      "line": words.get(name) or lesson.fact, "unlocks": lesson.unlocks, "at": at,
                      "from_you": name in from_owner, "source": "from_you" if name in from_owner else "figured"})
```

In `backend/survival/registry.py`, replace:

```python
    def create_life(self, *, name: str, seed: str, spawn: dict, born_at: float, egg: dict, traits: dict) -> dict:
```

with:

```python
    def create_life(self, *, name: str, seed: str, spawn: dict, born_at: float, egg: dict, traits: dict,
                    difficulty: str = "gentle") -> dict:
```

and replace:

```python
                name=name, seed=seed, spawn=spawn, born_at=born_at, traits=traits))
```

with:

```python
                name=name, seed=seed, spawn=spawn, born_at=born_at, traits=traits, difficulty=difficulty))
```

In `backend/survival/replies.py`, replace:

```python
from backend.survival.goals import GOALS, active, goal_purposes, goal_view, lower
from backend.survival.memory import known
```

with:

```python
from backend.survival.goals import GOALS, active, goal_purposes, goal_view, lower
```

and replace:

```python
    things = known(s.db, "lesson") if s.db is not None else []
```

with:

```python
    things = list(s.lessons)  # W1: not a gentle pet's born-knowing lessons
```

In `backend/survival/situation.py`, replace:

```python
        """L4b: the lessons Mimo learned (backend.survival.journal); what it knows unlocks work."""
        return tuple(memory.known(self.db, "lesson")) if self.db is not None else ()
```

with:

```python
        """L4b: the lessons Mimo learned (backend.survival.journal); what it knows unlocks work. W1: not the
        ones a gentle pet knew from the start (backend.survival.wild), which unlock nothing and never count."""
        if self.db is None:
            return ()
        start = set(memory.known(self.db, "born_knowing"))
        return tuple(lesson for lesson in memory.known(self.db, "lesson") if lesson not in start)
```

In `backend/survival/snapshot.py`, replace:

```python
from backend.survival.trips import trip_view
```

with:

```python
from backend.survival.trips import trip_view
from backend.survival.wild import difficulty, survival_view as survival_lessons
```

and replace:

```python
        journal = journal_view(db, state.get("brain"))
```

with:

```python
        journal = journal_view(db, state.get("brain"))
        survival = survival_lessons(db)
```

and replace:

```python
        "workshop": workshop,
```

with:

```python
        "workshop": workshop,
        # W1: "wild" or "gentle", and every survival lesson with where it came from (backend.survival.wild).
        "difficulty": difficulty(state),
        "survival": survival,
```

In `backend/survival/tick.py`, replace:

```python
(backend.survival.signals.run_signals, bounded to MAX_CELLS cells a transaction).
```

with:

```python
(backend.survival.signals.run_signals, bounded to MAX_CELLS cells a transaction).

W1: first of all, a living pet's difficulty is settled (backend.survival.wild.settle): a world from before
W1 becomes gentle, and a gentle pet is granted the survival lessons it knows from the start.
```

and replace:

```python
)
from backend.survival.world import SurvivalWorld, log_event, placed_near, read_state, write_state
```

with:

```python
)
from backend.survival.wild import settle
from backend.survival.world import SurvivalWorld, log_event, placed_near, read_state, write_state
```

and replace:

```python
        ensure_actions(state)
```

with:

```python
        ensure_actions(state)
        settle(state, db, state["last_tick_at"])  # W1: gentle for an old world, and a gentle pet's lessons
```

Create `backend/survival/wild.py`:

```python
"""Wild World W1: a newborn in a wild world (docs/superpowers/specs/2026-09-27-wild-world-design.md).

A life has a difficulty, `state["difficulty"]`: "wild" or "gentle", set at hatch and never changed.
A world with no difficulty key (every world made before W1) reads gentle, and its first tick writes
"gentle". A gentle pet is today's game: every survival lesson is known from its first tick (`settle`,
from the tick: rows in memory_knowledge with fact "lesson" and a second fact BORN_KNOWING, written
quietly, as curiosity's learn_quietly writes an old save's), none of W1's hazards happen to it and no
gate is ever shut for it (`unlocked`). A wild pet hatches knowing instinct only: each survival lesson
(SURVIVAL, a journal lesson of kind "survival" named `wild:<name>`, the colon keeping it out of L4b's
curios) unlocks what the table says for it, and it learns them from its owner (Mind's teaching, its
questions) or alone, by knocks.

Lessons known from birth never count in the tallies that read how many lessons Mimo learned: the
journal's own list and counts, investigate's and tinker's facts and Mind's "I have learned 20 things"
thought read them without BORN_KNOWING (situation.Situation.lessons, journal.learned, insights, replies),
so a gentle pet's choices and words stay as they were.

The wild bookkeeping lives in state["wild"] (`wild_state`): `knocks`, `wonders`, `shun`, `night_cold`,
`floor_nights`, `granted` (the milestone version granted to a gentle pet), each read with a default so
older saves and archives read as empty. This module imports nothing that imports the journal, so any
module may ask it whether a gate is open.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.survival.memory import know, known

if TYPE_CHECKING:
    from backend.survival.situation import Situation

WILD, GENTLE = "wild", "gentle"
DIFFICULTIES = (WILD, GENTLE)
PREFIX = "wild:"
KIND = "survival"  # the journal lessons' kind
BORN_KNOWING = "born_knowing"  # memory_knowledge's second fact for a lesson a gentle pet knew from the start
FIGURED = "figured"  # memory_knowledge's second fact for a lesson Mimo worked out alone (a knock)
LESSON = "lesson"  # journal.FACT
TAUGHT = "taught"  # journal.TAUGHT
GRANTED = 1  # the milestone whose lessons a gentle pet has been granted (W1)


@dataclass(frozen=True)
class Survival:
    name: str  # "fire": the lesson's thing is "wild:fire"
    words: str  # what it is about: "a campfire"
    fact: str  # the one sentence the owner can teach
    unlocks: str  # what it lets a wild pet do
    figured: str  # "Pip worked out that {figured}."


SURVIVAL: tuple[Survival, ...] = (
    Survival("berries", "red berries", "Bright red berries are safe to eat.",
             "eats and forages red berries without asking", "bright red berries are safe to eat"),
    Survival("nightberries", "nightberries", "Nightberries, the dark purple berries with pale specks, are poison.",
             "tells nightberries from berries and never eats them", "the dark purple berries are poison"),
    Survival("red_mushroom", "red mushrooms", "Red mushrooms are poison.", "never picks or eats red mushrooms",
             "red mushrooms are poison"),
    Survival("sunleaf", "sunleaf", "Sunleaf, the little yellow herb, cures sickness when eaten and cleans a wound.",
             "carries sunleaf, eats one when sick and dresses a wound with one", "sunleaf cures a sickness"),
    Survival("bandage", "a wool bandage", "A bandage of wool on a wound stops it festering.",
             "makes wool bandages and dresses a wound", "a wool bandage stops a wound festering"),
    Survival("fire", "a campfire", "Two logs and three sticks make a campfire, and a fire keeps you warm at night.",
             "makes campfires and lights one to get warm", "a campfire keeps the cold away"),
    Survival("cooking", "cooked meat", "Meat and fish cooked on a fire are safe to eat and fill you up far more.",
             "cooks meat and fish on a fire", "cooking makes meat safe"),
    Survival("keeping", "food keeping", "Raw food goes bad in a day or two, and food in a chest keeps twice as long.",
             "cooks raw food before it turns, stores spare food and throws out what went bad",
             "food keeps longer in a chest"),
    Survival("light", "torches", "Torches keep the dark creatures away, because they only come out where it is dark.",
             "lights torches round home at night", "torches keep the dark creatures away"),
    Survival("shelter", "a shelter", "A shelter with walls, a roof and a door keeps out the cold and the dark "
             "creatures at night.", "builds a shelter with a door and makes it a home",
             "a shelter with a door keeps the night out"),
    Survival("bed", "a bed", "Six planks make a bed, and sleep in a bed rests you best.",
             "makes a bed and sleeps in it", "a bed rests you best"),
)
BY_NAME = {lesson.name: lesson for lesson in SURVIVAL}
SOURCES = {TAUGHT: "from_you", BORN_KNOWING: "from_start"}


def thing(name: str) -> str:
    """The journal lesson a survival lesson is: "wild:fire"."""
    return f"{PREFIX}{name}"


def difficulty(state: dict) -> str:
    """"wild" or "gentle"; a world with no key (from before W1) reads gentle."""
    found = state.get("difficulty")
    return found if found in DIFFICULTIES else GENTLE


def is_wild(state: dict) -> bool:
    return state.get("difficulty") == WILD


def knows(s: Situation, name: str) -> bool:
    """Mimo knows the survival lesson `name` (a gentle pet's born-knowing lessons aside)."""
    return thing(name) in s.lessons


def unlocked(s: Situation, name: str) -> bool:
    """What the lesson `name` unlocks is open to Mimo: always for a gentle pet, and for a wild one once it
    knows the lesson."""
    return not is_wild(s.state) or knows(s, name)


def wild_state(state: dict) -> dict:
    """state["wild"], with every field a wild pet's bookkeeping needs."""
    found = state.setdefault("wild", {})
    for key, default in (("knocks", {}), ("wonders", {}), ("shun", {}), ("night_cold", 0.0), ("floor_nights", 0),
                         ("granted", None)):
        found.setdefault(key, default)
    return found


def settle(state: dict, db: sqlite3.Connection | None, at: float) -> None:
    """The tick of a living pet: a world with no difficulty becomes gentle, and a gentle pet not yet granted
    this milestone's lessons is granted them now, quietly (no event, no discovery, no memory, no choice)."""
    if state.get("difficulty") not in DIFFICULTIES:
        state["difficulty"] = GENTLE
    if state["difficulty"] != GENTLE or db is None or (state.get("wild") or {}).get("granted") == GRANTED:
        return
    for lesson in SURVIVAL:
        know(db, thing(lesson.name), LESSON, at)
        know(db, thing(lesson.name), BORN_KNOWING, at)
    state.setdefault("wild", {})["granted"] = GRANTED


def born_knowing(db: sqlite3.Connection) -> set[str]:
    """The lessons Mimo knew from the start (a gentle pet's)."""
    return set(known(db, BORN_KNOWING))


def learned_lessons(db: sqlite3.Connection) -> list[str]:
    """The lessons Mimo learned, first first, leaving out those it knew from the start."""
    start = born_knowing(db)
    return [lesson for lesson in known(db, LESSON) if lesson not in start]


def source_of(facts: set[str]) -> str:
    """Where a lesson Mimo knows came from: the owner ("from_you"), the start ("from_start"), or Mimo
    itself ("figured": worked out, or found out by meeting the thing)."""
    for fact, source in SOURCES.items():
        if fact in facts:
            return source
    return "figured"


def facts_of(db: sqlite3.Connection, subjects: tuple[str, ...]) -> dict[str, set[str]]:
    """{subject: its memory_knowledge facts}, for these subjects. An archive from before memory has none."""
    marks = ",".join("?" * len(subjects))
    try:
        rows = db.execute(f"SELECT subject, fact FROM memory_knowledge WHERE subject IN ({marks})", subjects).fetchall()
    except sqlite3.OperationalError:
        return {}
    found: dict[str, set[str]] = {}
    for subject, fact in rows:
        found.setdefault(subject, set()).add(fact)
    return found


def survival_view(db: sqlite3.Connection) -> list[dict]:
    """Every survival lesson for the viewer's journal, in the table's order: {name, words, fact, known,
    source} (source null while unknown)."""
    facts = facts_of(db, tuple(thing(lesson.name) for lesson in SURVIVAL))
    found = []
    for lesson in SURVIVAL:
        mine = facts.get(thing(lesson.name), set())
        learned = LESSON in mine
        found.append({"name": lesson.name, "words": lesson.words, "fact": lesson.fact, "known": learned,
                      "source": source_of(mine) if learned else None})
    return found
```

In `backend/survival/world.py`, replace:

```python
def new_survival_state(*, name: str, seed: str, spawn: dict, born_at: float, traits: dict) -> dict:
```

with:

```python
def new_survival_state(*, name: str, seed: str, spawn: dict, born_at: float, traits: dict,
                       difficulty: str = "gentle") -> dict:
```

and replace:

```python
        "cause": None,
```

with:

```python
        "cause": None,
        "difficulty": difficulty,  # W1: "wild" or "gentle", for good (backend.survival.wild)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild.py"`
Expected: `Ran 9 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1837 tests` … `OK (skipped=5)` (9 new).

- [ ] **Step 5: Commit**

```bash
git add backend/api/lives.py backend/survival/hatch.py backend/survival/insights.py backend/survival/journal.py backend/survival/registry.py backend/survival/replies.py backend/survival/situation.py backend/survival/snapshot.py backend/survival/tick.py backend/survival/wild.py backend/survival/world.py backend/tests/test_survival_wild.py
git commit -m "feat(W1): a life hatches wild or gentle, and every older world is gentle and knows its survival lessons from the start" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The survival lessons, taught in one sentence

**Files:**
- Modify: `backend/survival/wild.py` (each lesson's `subjects`, `means`, `sides`), `backend/survival/journal.py` (the eleven lessons in `LESSONS`), `backend/survival/lessons.py` (the parser)
- Modify: `backend/tests/test_survival_lessons.py` (the lesson count)
- Test: `backend/tests/test_survival_wild_teaching.py`

**Interfaces:**
- Consumes: Task 1's table; `lessons.claims`, `claims_one`, `keys_of`, `contradicts`, `TEACH_SYNONYMS`, `OPPOSITES`; `teaching.teach_lesson`; the Talker's chat job with the counting stub.
- Produces:
  - `journal.LESSONS` holds the eleven `wild:<name>` lessons of kind `"survival"` (their journal words the lesson's words, their fact its sentence).
  - `Survival.subjects`, `Survival.means`, `Survival.sides`.
  - `lessons.warned(text) -> str | None` (a warning read as the claim it makes); `claims_one` reads a warning first and lets a command teach only a survival lesson.
  - The spec's teaching table as `TEACHES` and `DOUBTED` in the test: every line in the first taught, every line in the second doubted.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_lessons.py`, replace:

```python
        added = [thing for thing in LESSONS if ":" in thing]
        self.assertEqual(len(added), len(GEAR) + 2 * len(KINDS) - sum(1 for kind in KINDS.values() if not kind.drops)
                         + 2)  # L5: the warding lantern's and gold nuggets' recipe lessons (frontier_gear)
        self.assertEqual(len(LESSONS) - len(added), 36)  # L4b's 32, plus Making T2's 4 (copper_spark, clock, latch, adder)
```

with:

```python
        added = [thing for thing in LESSONS if ":" in thing and not thing.startswith("wild:")]  # W1's own below
        self.assertEqual(len(added), len(GEAR) + 2 * len(KINDS) - sum(1 for kind in KINDS.values() if not kind.drops)
                         + 2)  # L5: the warding lantern's and gold nuggets' recipe lessons (frontier_gear)
        survival = [thing for thing in LESSONS if thing.startswith("wild:")]
        self.assertEqual(len(survival), 11)  # W1's survival lessons
        self.assertEqual(len(LESSONS) - len(added) - len(survival), 36)  # L4b's 32, plus Making T2's 4
```

Create `backend/tests/test_survival_wild_teaching.py`:

```python
import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every lesson registered)
from backend.survival import minding  # noqa: F401  (the chat's "teach" question)
from backend.survival.hatch import hatch
from backend.survival.journal import LESSONS, journal_view
from backend.survival.lessons import claims, named, wants
from backend.survival.memory import know
from backend.survival.registry import LifeRegistry
from backend.survival.talk import owner_says
from backend.survival.talker import Talker
from backend.survival.wild import SURVIVAL, thing
from backend.survival.world import SurvivalWorld
from backend.tests.no_model import no_model

BORN = 1_000_000.0
# The spec's teaching table: what each survival lesson's owner lines teach, and the lines doubted.
TEACHES = {
    "berries": ("Red berries are safe to eat.",),
    "nightberries": ("Nightberries are the dark purple ones, and they are poison.", "The purple berries are poison.",
                     "Don't eat the purple berries."),
    "red_mushroom": ("Red mushrooms are poison.", "Never eat red mushrooms."),
    "sunleaf": ("Sunleaf cures sickness and cleans wounds.",),
    "bandage": ("A wool bandage stops a wound festering.",),
    "fire": ("Two logs and three sticks make a campfire.", "A campfire keeps you warm at night."),
    "cooking": ("Cooked meat and fish are safe to eat.", "Cook your meat on a fire."),
    "keeping": ("Food keeps twice as long in a chest.",),
    "light": ("Torches keep the dark creatures away.",),
    "shelter": ("A shelter with a roof and a door keeps you safe at night.",),
    "bed": ("Six planks make a bed.",),
}
DOUBTED = {
    "berries": "Red berries are poison.", "nightberries": "Nightberries are safe to eat.",
    "red_mushroom": "Red mushrooms are safe to eat.", "sunleaf": "Sunleaf is poison.",
    "fire": "Five logs make a campfire.", "cooking": "Raw meat is safe to eat.",
    "light": "Torches bring the dark creatures.", "bed": "Two planks make a bed.",
}


class TeachingTableTests(unittest.TestCase):
    def test_every_line_of_the_teaching_table_teaches_its_lesson_first(self):
        for name, lines in TEACHES.items():
            for text in lines:
                found = claims(text)
                self.assertEqual((found.taught[:1], found.doubtful), ((thing(name),), False), text)

    def test_every_doubted_line_is_doubted_and_teaches_nothing(self):
        for text in DOUBTED.values():
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), ((), True), text)

    def test_the_lessons_are_named_after_wild_and_each_fact_teaches_itself(self):
        for lesson in SURVIVAL:
            self.assertEqual(named(LESSONS[thing(lesson.name)]), lesson.name)
            self.assertIn(thing(lesson.name), claims(lesson.fact).taught, lesson.fact)

    def test_a_warning_teaches_and_a_survival_command_teaches_while_staying_a_request(self):
        self.assertEqual(claims("Avoid nightberries.").taught, (thing("nightberries"),))
        self.assertEqual(claims("Don't eat raw meat.").taught, (thing("cooking"),))
        self.assertTrue(claims("Don't eat red berries.").doubtful)  # bright red berries are safe
        self.assertTrue(wants("Cook your meat on a fire."))  # B2 still reads it as a request
        for text in ("Make a campfire.", "Please cook the fish.", "make a bow!"):
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), ((), False), text)

    def test_everyday_lines_about_torches_shelters_and_food_stay_chat(self):
        for text in ("sticks make torches", "A shelter keeps you warm.", "I made you a bed", "let's go home"):
            self.assertFalse(claims(text).doubtful, text)


class ChatTeachingTests(unittest.TestCase):
    """A wild pet taught in the chat, through the rules (no model): learned from you."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        life = hatch(self.registry, random.Random(8), timestamp=BORN, difficulty="wild")
        self.world = SurvivalWorld(self.registry.world_path(life))

    def tearDown(self):
        self.directory.cleanup()

    def say(self, text, at):
        owner_says(self.world, text, at, 1.0)
        talker = Talker(env={}, http=no_model(self), scale=1.0)
        talker.poll(self.registry, at + 1)
        talker.close()

    def test_the_owner_teaches_every_survival_lesson_in_one_sentence_each(self):
        for number, (name, lines) in enumerate(TEACHES.items()):
            self.say(lines[0], BORN + 10 * (number + 1))
        with self.world.connect() as db:
            taught = {row[0] for row in db.execute("SELECT subject FROM memory_knowledge WHERE fact='taught'")}
            listed = journal_view(db, self.world.state().get("brain"))
        self.assertEqual(taught, {thing(name) for name in TEACHES})
        self.assertEqual(listed, [])  # listed apart, in the survival field

    def test_a_doubted_line_teaches_nothing_and_says_so(self):
        self.say(DOUBTED["cooking"], BORN + 10)
        with self.world.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_knowledge WHERE subject LIKE 'wild:%'").fetchone()[0], 0)
            reply = db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertTrue(reply.startswith("Hmm, I'm not sure that's right."), reply)

    def test_a_gentle_pet_already_knows_them(self):
        with self.world.transaction() as db:
            know(db, thing("fire"), "lesson", BORN)
        self.say(TEACHES["fire"][0], BORN + 10)
        with self.world.connect() as db:
            reply = db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertTrue(reply.startswith("I know that one!"), reply)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild_teaching.py"`
Expected: `FAILED (failures=6, errors=1)`: the survival lessons are not in the journal yet (`KeyError: 'wild:berries'`), so no line of the table teaches one

- [ ] **Step 3: The lessons in the journal and the parser**

In `backend/survival/journal.py`, replace:

```python
from backend.survival.wild import BORN_KNOWING
```

with:

```python
from backend.survival.wild import BORN_KNOWING, KIND as SURVIVAL_KIND, SURVIVAL, thing as survival_thing
```

and replace:

```python
    kind: str  # "block", "plant", "creature", "biome", "landmark", "recipe" (Mind) or "making"
```

with:

```python
    kind: str  # "block", "plant", "creature", "biome", "landmark", "recipe" (Mind), "making" or "survival" (W1)
```

and replace:

```python
)
SURFACE = tuple(name for name, lesson in LESSONS.items() if lesson.kind == "block")
```

with:

```python
)
# W1: the survival lessons a wild pet learns from its owner or alone (backend.survival.wild).
teach(*(Lesson(survival_thing(lesson.name), SURVIVAL_KIND, lesson.words, lesson.fact, lesson.unlocks)
        for lesson in SURVIVAL))
SURFACE = tuple(name for name, lesson in LESSONS.items() if lesson.kind == "block")
```

and replace:

```python
    "from_start")}. A world from before L3 read as an archive has learned nothing."""
```

with:

```python
    "from_start")}. A world from before L3 read as an archive has learned nothing. W1: the survival lessons
    are listed apart, known or not (wild.survival_view), so they are left out here."""
```

and replace:

```python
        if lesson is None:
```

with:

```python
        if lesson is None or lesson.kind == SURVIVAL_KIND:
```

In `backend/survival/lessons.py`, replace:

```python
from backend.survival.mind import singular, vocabulary, words_of
```

with:

```python
from backend.survival.mind import singular, vocabulary, words_of
from backend.survival.wild import BY_NAME as SURVIVAL, KIND as SURVIVAL_KIND, PREFIX as SURVIVAL_PREFIX
```

and replace:

```python
    {"ingot", "bar"}, {"wooden", "wood"}, {"stone", "cobblestone"},
```

with:

```python
    {"ingot", "bar"}, {"wooden", "wood"}, {"stone", "cobblestone"},
    # W1: the survival lessons' words (backend.survival.wild).
    {"purple", "dark", "night"}, {"herb", "sunleaf"}, {"bandage", "wrap"}, {"campfire", "fire"}, {"torch", "light"},
    {"shelter", "house", "home"}, {"poison", "poisonous", "toxic"}, {"cook", "cooked", "cooking"},
    {"festering", "fester"}, {"sickness", "sick", "ill"},
```

and replace:

```python
              frozenset({"night", "nighttime", "midnight", "dark", "evening"})))
```

with:

```python
              frozenset({"night", "nighttime", "midnight", "dark", "evening"})),
             # W1: safe or poison, raw or cooked, kept away or brought, warm or cold (the survival lessons)
             (frozenset({"safe", "fine", "edible", "cure", "clean", "heal"}),
              frozenset({"poison", "poisonous", "toxic", "bad"})),
             (frozenset({"raw"}), frozenset({"cooked", "cook"})),
             (frozenset({"away"}), frozenset({"bring", "attract"})),
             (frozenset({"warm", "warmth"}), frozenset({"cold", "chill"})))
```

and replace:

```python
                      "collect", "chop", "grab"})
```

with:

```python
                      "collect", "chop", "grab"})


# W1: a warning teaches (resolution 8): a sentence that opens with "don't eat", "do not eat", "never eat" or
# "avoid", followed by what a poison lesson is about, reads as "<that> are poison"; followed by raw meat or
# fish, as "Cooked meat and fish are safe to eat." (`warned`). Its own "don't" would doubt a true warning.
WARNING = re.compile(r"^\s*(?:please\s+)?(?:(?:don['’]?t|do\s+not|never)\s+(?:ever\s+)?eat(?:ing)?|avoid(?:\s+eating)?)"
                     r"\s+(?:the\s+|any\s+)?(?P<rest>[^.!?]+?)[\s.!]*$", re.IGNORECASE)
RAW_MEAT = re.compile(r"^raw\s+(?:meat|fish|beef|mutton|chicken|rabbit)\b", re.IGNORECASE)
COOKED_IS_SAFE = "Cooked meat and fish are safe to eat."
```

and replace:

```python
    """What a lesson is about: "iron_sword" of "recipe:iron_sword", "cow" of "cow:drops"."""
    parts = lesson.thing.split(":")
    return parts[1] if parts[0] == "recipe" and len(parts) > 1 else parts[0]
```

with:

```python
    """What a lesson is about: "iron_sword" of "recipe:iron_sword", "cow" of "cow:drops", (W1) "fire" of
    "wild:fire"."""
    parts = lesson.thing.split(":")
    return parts[1] if parts[0] in ("recipe", "wild") and len(parts) > 1 else parts[0]
```

and replace:

```python
    group = gear_group(named(lesson)) if lesson.kind == "recipe" else ""
```

with:

```python
    group = gear_group(named(lesson)) if lesson.kind == "recipe" else ""
    survival = SURVIVAL.get(named(lesson)) if lesson.kind == SURVIVAL_KIND else None
```

and replace:

```python
            subjects.add(frozenset(found[:1] if found[-1] in ("ore", "mouth") else found[-1:]))
```

with:

```python
            subjects.add(frozenset(found[:1] if found[-1] in ("ore", "mouth") else found[-1:]))
    if survival is not None:  # W1: a survival lesson names what it is about itself ("dark creatures", not "light")
        subjects = {frozenset(tokens(subject)) for subject in survival.subjects}
```

and replace:

```python
            *(RECIPE_WORDS if lesson.kind == "recipe" else ())}
```

with:

```python
            *(RECIPE_WORDS if lesson.kind == "recipe" else ()), *(survival.means if survival is not None else ())}
```

and replace:

```python
    fact, words = set(raw_words(lesson.fact)), set(raw)
```

with:

```python
    fact, words = set(raw_words(lesson.fact)), set(raw)
    if lesson.kind == SURVIVAL_KIND and named(lesson) in SURVIVAL:  # W1: what its fact stands for besides
        fact |= set(SURVIVAL[named(lesson)].sides)
```

and replace:

```python

def commanded(text: str) -> bool:
```

with:

```python

def warned(text: str) -> str:
    """W1: a warning said as the fact it warns of ("Don't eat the purple berries." -> "purple berries are
    poison."; "Never eat raw meat." -> COOKED_IS_SAFE), or the words as they are."""
    match = WARNING.match(text)
    if match is None:
        return text
    rest = match.group("rest").strip()
    if RAW_MEAT.match(rest):
        return COOKED_IS_SAFE
    keys, _, _ = lesson_keys()
    said = set(tokens(rest))
    for name, lesson in SURVIVAL.items():
        found = keys.get(f"{SURVIVAL_PREFIX}{name}")
        if found is not None and "poison" in raw_words(lesson.fact) and any(subject <= said for subject in found.subjects):
            return f"{rest} are poison."
    return text


def commanded(text: str) -> bool:
```

and replace:

```python
    decides ("you should craft an iron sword" is no doubtful claim about iron ore)."""
    if asks(text) or commanded(text):
```

with:

```python
    decides ("you should craft an iron sword" is no doubtful claim about iron ore). W1: a warning is read as
    the fact it warns of (`warned`), and a command still teaches a survival lesson whose words it fits with
    nothing wrong ("Cook your meat on a fire."), doubting nothing (resolution 8)."""
    text = warned(text)
    commanding = commanded(text)
    if asks(text):
```

and replace:

```python
    for index, (thing, found) in enumerate(keys.items()):
```

with:

```python
    for index, (thing, found) in enumerate(keys.items()):
        if commanding and LESSONS[thing].kind != SURVIVAL_KIND:
            continue
```

and replace:

```python
    fits.sort()
    # Narrowed the way bare_claim narrows doubt (fix round 2, Important 2): no person words, and the
```

with:

```python
    fits.sort()
    if commanding:
        return Claims(tuple(thing for _, _, thing in fits[:SHORTLIST]), False, False)
    # Narrowed the way bare_claim narrows doubt (fix round 2, Important 2): no person words, and the
```

In `backend/survival/wild.py`, replace:

```python
    figured: str  # "Pip worked out that {figured}."
```

with:

```python
    figured: str  # "Pip worked out that {figured}."
    subjects: tuple[str, ...] = ()  # what the owner's words name when they speak of it (backend.survival.lessons)
    means: tuple[str, ...] = ()  # words it means besides its fact's own ("poison" of the berries: safe or not)
    sides: tuple[str, ...] = ()  # words its fact stands for when opposites are weighed ("warm" of the shelter)
```

and replace:

```python
             "eats and forages red berries without asking", "bright red berries are safe to eat"),
    Survival("nightberries", "nightberries", "Nightberries, the dark purple berries with pale specks, are poison.",
             "tells nightberries from berries and never eats them", "the dark purple berries are poison"),
    Survival("red_mushroom", "red mushrooms", "Red mushrooms are poison.", "never picks or eats red mushrooms",
             "red mushrooms are poison"),
    Survival("sunleaf", "sunleaf", "Sunleaf, the little yellow herb, cures sickness when eaten and cleans a wound.",
             "carries sunleaf, eats one when sick and dresses a wound with one", "sunleaf cures a sickness"),
    Survival("bandage", "a wool bandage", "A bandage of wool on a wound stops it festering.",
             "makes wool bandages and dresses a wound", "a wool bandage stops a wound festering"),
    Survival("fire", "a campfire", "Two logs and three sticks make a campfire, and a fire keeps you warm at night.",
             "makes campfires and lights one to get warm", "a campfire keeps the cold away"),
    Survival("cooking", "cooked meat", "Meat and fish cooked on a fire are safe to eat and fill you up far more.",
             "cooks meat and fish on a fire", "cooking makes meat safe"),
    Survival("keeping", "food keeping", "Raw food goes bad in a day or two, and food in a chest keeps twice as long.",
             "cooks raw food before it turns, stores spare food and throws out what went bad",
             "food keeps longer in a chest"),
    Survival("light", "torches", "Torches keep the dark creatures away, because they only come out where it is dark.",
             "lights torches round home at night", "torches keep the dark creatures away"),
    Survival("shelter", "a shelter", "A shelter with walls, a roof and a door keeps out the cold and the dark "
             "creatures at night.", "builds a shelter with a door and makes it a home",
             "a shelter with a door keeps the night out"),
    Survival("bed", "a bed", "Six planks make a bed, and sleep in a bed rests you best.",
             "makes a bed and sleeps in it", "a bed rests you best"),
```

with:

```python
             "eats and forages red berries without asking", "bright red berries are safe to eat",
             ("red berries",), ("safe", "poison", "eat")),
    Survival("nightberries", "nightberries", "Nightberries, the dark purple berries with pale specks, are poison.",
             "tells nightberries from berries and never eats them", "the dark purple berries are poison",
             ("nightberries", "purple berries", "dark berries"), ("safe", "poison", "eat")),
    Survival("red_mushroom", "red mushrooms", "Red mushrooms are poison.", "never picks or eats red mushrooms",
             "red mushrooms are poison", ("red mushrooms",), ("safe", "poison", "eat")),
    Survival("sunleaf", "sunleaf", "Sunleaf, the little yellow herb, cures sickness when eaten and cleans a wound.",
             "carries sunleaf, eats one when sick and dresses a wound with one", "sunleaf cures a sickness",
             ("sunleaf", "yellow herb"), ("safe", "poison", "eat")),
    Survival("bandage", "a wool bandage", "A bandage of wool on a wound stops it festering.",
             "makes wool bandages and dresses a wound", "a wool bandage stops a wound festering",
             ("bandage",), ("wrap", "clean")),
    Survival("fire", "a campfire", "Two logs and three sticks make a campfire, and a fire keeps you warm at night.",
             "makes campfires and lights one to get warm", "a campfire keeps the cold away",
             ("campfire",), ("fire",)),
    Survival("cooking", "cooked meat", "Meat and fish cooked on a fire are safe to eat and fill you up far more.",
             "cooks meat and fish on a fire", "cooking makes meat safe",
             ("meat", "cooked meat", "cooked fish"), ("safe", "poison", "eat", "raw", "cook")),
    Survival("keeping", "food keeping", "Raw food goes bad in a day or two, and food in a chest keeps twice as long.",
             "cooks raw food before it turns, stores spare food and throws out what went bad",
             "food keeps longer in a chest", ("food chest", "spoiled food"), ("fresh", "spoil", "rot")),
    Survival("light", "torches", "Torches keep the dark creatures away, because they only come out where it is dark.",
             "lights torches round home at night", "torches keep the dark creatures away",
             ("dark creatures",), ("bring", "attract")),
    Survival("shelter", "a shelter", "A shelter with walls, a roof and a door keeps out the cold and the dark "
             "creatures at night.", "builds a shelter with a door and makes it a home",
             "a shelter with a door keeps the night out", ("shelter",), ("safe", "warm"), ("warm",)),
    Survival("bed", "a bed", "Six planks make a bed, and sleep in a bed rests you best.",
             "makes a bed and sleeps in it", "a bed rests you best", ("bed",), ("sleep",)),
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild_teaching.py"`
Expected: `Ran 8 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1845 tests` … `OK (skipped=5)` (8 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/journal.py backend/survival/lessons.py backend/survival/wild.py backend/tests/test_survival_lessons.py backend/tests/test_survival_wild_teaching.py
git commit -m "feat(W1): eleven survival lessons in the journal, each taught in one sentence and doubted when wrong" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The gates

**Files:**
- Modify: `backend/survival/wild.py` (`PURPOSE_LESSONS`, `GOAL_LESSONS`, `FITTING_LESSONS`, `purpose_open`, `goal_open`, `fitting_open`), `backend/survival/purposes.py` (`is_valid`), `backend/survival/goals.py` (`is_open`), `backend/survival/building.py` (`fittings_due`), `backend/survival/reflexes.py` (warm_up), `backend/survival/cooking.py` (raw food and the fire), `backend/survival/camp.py`, `backend/survival/expedition.py` (the campfire and the torches)
- Test: `backend/tests/test_survival_wild_gates.py`

**Interfaces:**
- Consumes: Task 1's `unlocked`; `purposes.is_valid`, `goals.is_open`, `building.fittings_due`, `reflexes.plan_warm_up`, `cooking`, `camp`, `expedition`; the test helpers of `test_survival_building`, `test_survival_cooking`, `test_survival_lighting`, `test_survival_camp` and `test_survival_expedition`.
- Produces: `wild.purpose_open(name, s)`, `goal_open(name, s)`, `fitting_open(block, s)`: open for a gentle pet, and for a wild pet only with the lesson each needs. Nothing else is gated; a craft step the owner asks for is never refused.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_wild_gates.py`:

```python
"""W1: what a wild newborn does not know yet, and a gentle pet always does (the lessons table's gates)."""

import unittest

import backend.survival.brain  # noqa: F401  (every purpose and goal registered)
from backend.survival.goals import GOALS, is_open
from backend.survival.purposes import PURPOSES, is_valid
from backend.survival.reflexes import plan_warm_up
from backend.survival.memory import know, structures
from backend.survival.structures import blueprint_of
from backend.survival.wild import thing
from backend.tests.test_survival_building import World, places_of
from backend.tests.test_survival_cooking import plan as cook_plan, situation as cook_situation
from backend.tests import test_survival_lighting as lighting


def wild(s, *lessons):
    """`s` made a wild pet's, knowing `lessons`."""
    s.state["difficulty"] = "wild"
    for name in lessons:
        know(s.db, thing(name), "lesson", 0.0)
    s.__dict__.pop("lessons", None)  # read again
    return s


class FireAndCookingTests(unittest.TestCase):
    def test_a_wild_pet_cooks_meat_only_once_it_knows_cooking(self):
        self.assertEqual(cook_plan(wild(cook_situation({"raw_fish": 1, "oak_log": 3}))), [])
        self.assertFalse(is_valid(PURPOSES["cook"], wild(cook_situation({"raw_fish": 1, "oak_log": 3}))))
        bread = cook_plan(wild(cook_situation({"wheat": 3, "crafting_table": 1})))
        self.assertIn({"kind": "craft", "recipe": "bread"}, bread)  # baking is no lesson

    def test_it_makes_a_campfire_only_once_it_knows_fire(self):
        steps = cook_plan(wild(cook_situation({"raw_fish": 1, "oak_log": 3}), "cooking"))
        self.assertEqual(steps, [])  # no fire, and none it knows how to make
        steps = cook_plan(wild(cook_situation({"raw_fish": 1, "furnace": 1}), "cooking"))
        self.assertIn({"kind": "place", "target": [1, 1, 0], "block": "furnace"}, steps)
        steps = cook_plan(wild(cook_situation({"raw_fish": 1, "oak_log": 3}), "cooking", "fire"))
        self.assertIn({"kind": "craft", "recipe": "campfire"}, steps)

    def test_warm_up_lights_a_carried_campfire_only_once_it_knows_fire(self):
        cold = cook_situation({"campfire": 1})
        context = None
        self.assertEqual(plan_warm_up(wild(cold), context), [])
        self.assertTrue(any(step.get("block") == "campfire" for step in plan_warm_up(wild(cook_situation({"campfire": 1}),
                                                                                          "fire"), context)))
        self.assertTrue(any(step.get("block") == "furnace" for step in plan_warm_up(wild(cook_situation({"furnace": 1})),
                                                                                   context)))

    def test_a_gentle_pet_is_never_gated(self):
        s = cook_situation({"raw_fish": 1, "oak_log": 3})
        s.state["difficulty"] = "gentle"
        self.assertIn({"kind": "craft", "recipe": "campfire"}, cook_plan(s))


class ShelterAndBedTests(unittest.TestCase):
    def test_build_shelter_and_a_home_of_its_own_wait_for_the_shelter_lesson(self):
        world = World({"cobblestone": 40})
        world.state["difficulty"] = "wild"
        self.assertFalse(is_valid(PURPOSES["build_shelter"], world.situation()))
        self.assertFalse(is_open(world.situation(), GOALS["first_shelter"]))
        know(world.db, thing("shelter"), "lesson", 0.0)
        self.assertTrue(is_valid(PURPOSES["build_shelter"], world.situation()))
        self.assertTrue(is_open(world.situation(), GOALS["first_shelter"]))
        for name in ("improve_home", "camp"):
            self.assertIn(name, PURPOSES)

    def test_a_finished_shelter_gets_a_bed_only_once_it_knows_beds_and_a_campfire_once_it_knows_fire(self):
        world = World({"cobblestone": 40})
        world.state["difficulty"] = "wild"
        know(world.db, thing("shelter"), "lesson", 0.0)
        for _ in range(4):
            world.carry_out(world.plan())
        world.state["inventory"] = {"oak_log": 4}
        design = blueprint_of(structures(world.db)[0])
        self.assertEqual(places_of(world.plan()), [{"kind": "place", "target": list(design.one("door")), "block": "door"}])
        know(world.db, thing("bed"), "lesson", 0.0)
        self.assertEqual([step["block"] for step in places_of(world.plan())], ["bed", "door"])
        know(world.db, thing("fire"), "lesson", 0.0)  # 4 logs make a bed and a campfire, with none left for a door
        self.assertEqual([step["block"] for step in places_of(world.plan())], ["bed", "campfire"])


class LightGateTests(unittest.TestCase):
    """light_up and a safe yard wait for the light lesson (the lighting tests' home, torches and evening)."""

    setUp = lighting.LightTests.setUp
    situation = lighting.LightTests.situation

    def test_light_up_and_a_safe_yard_wait_for_the_light_lesson(self):
        s = self.situation({"torch": 4})
        s.state["difficulty"] = "wild"
        know(self.db, thing("shelter"), "lesson", 0.0)
        self.assertFalse(is_valid(PURPOSES["light_up"], s))
        self.assertFalse(is_open(s, GOALS["safe_yard"]))
        know(self.db, thing("light"), "lesson", 0.0)
        s = self.situation({"torch": 4})
        s.state["difficulty"] = "wild"
        self.assertTrue(is_valid(PURPOSES["light_up"], s))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild_gates.py"`
Expected: `FAILED (failures=6)`: a wild pet that knows nothing is still offered the shelter, the bed, the campfire, cooking and torches

- [ ] **Step 3: The gates**

In `backend/survival/building.py`, replace:

```python
from backend.survival.triggers import mark_trigger
```

with:

```python
from backend.survival.triggers import mark_trigger
from backend.survival.wild import fitting_open
```

and replace:

```python
    """A bed and a campfire still missing that Mimo carries or can make now."""
    due, trial = [], dict(s.inventory)
    for planned in todo(s.grid, blueprint, FURNISHINGS):
```

with:

```python
    """A bed and a campfire still missing that Mimo carries or can make now; W1: a wild pet puts in only the
    ones it knows how to make (wild.fitting_open: a bed, a campfire, a door)."""
    due, trial = [], dict(s.inventory)
    for planned in todo(s.grid, blueprint, FURNISHINGS):
        if not fitting_open(planned.block, s):
            continue
```

In `backend/survival/camp.py`, replace:

```python
from backend.survival.triggers import ensure_brain
```

with:

```python
from backend.survival.triggers import ensure_brain
from backend.survival.wild import unlocked
```

and replace:

```python
        steps = (made(inventory, "campfire") or []) if inventory.get("campfire", 0) < 1 else []
```

with:

```python
        makes = inventory.get("campfire", 0) < 1 and unlocked(s, "fire")  # W1: a wild pet needs wild:fire
        steps = (made(inventory, "campfire") or []) if makes else []
```

and replace:

```python
    torches_wanted = max(0, CAMP_TORCHES - lit_near(s, spot, "torch"))
```

with:

```python
    torches_wanted = max(0, CAMP_TORCHES - lit_near(s, spot, "torch")) if unlocked(s, "light") else 0  # W1
```

In `backend/survival/cooking.py`, replace:

```python
- Three wheat bake into bread (25) at a crafting table, like craft_tools does it.
```

with:

```python
- Three wheat bake into bread (25) at a crafting table, like craft_tools does it.
W1: a wild pet cooks raw food only once it knows `wild:cooking`, and makes or puts down a campfire only
once it knows `wild:fire` (backend.survival.wild): before that it cooks at a furnace it carries or finds, and
bakes bread as ever.
```

and replace:

```python
from backend.survival.toolmaking import Short, make, place_station, station_spots
```

with:

```python
from backend.survival.toolmaking import Short, make, place_station, station_spots
from backend.survival.wild import unlocked
```

and replace:

```python

def cook_plan(s: Situation) -> list[dict] | None:
```

with:

```python

def light_fire(s: Situation, inventory: dict, spots, steps: list[dict], placed: list[Cell]) -> bool:
    """Put down a fire to cook on: a carried campfire or furnace, or a campfire made now; W1: a wild pet that
    does not know `wild:fire` only puts down a furnace it carries."""
    if unlocked(s, "fire"):
        return station(inventory, "campfire", spots, steps, placed, FIRES)
    return inventory.get("furnace", 0) > 0 and station(inventory, "furnace", spots, steps, placed, ("furnace",))


def cook_plan(s: Situation) -> list[dict] | None:
```

and replace:

```python
    raw = [(item, inventory[item]) for item in RAW_FOODS if inventory.get(item, 0) > 0]
    if raw and not near.intersection(FIRES) and not station(inventory, "campfire", spots, steps, placed, FIRES):
```

with:

```python
    raw = [(item, inventory[item]) for item in RAW_FOODS if inventory.get(item, 0) > 0] if unlocked(s, "cooking") else []
    if raw and not near.intersection(FIRES) and not light_fire(s, inventory, spots, steps, placed):
```

In `backend/survival/expedition.py`, replace:

```python
from backend.survival.trips import WANDER_PENALTY_SECONDS, Reason, register_reason
```

with:

```python
from backend.survival.trips import WANDER_PENALTY_SECONDS, Reason, register_reason
from backend.survival.wild import unlocked
```

and replace:

```python
    had or no room for them (`no_room_for_torches`)."""
    if not coal_known(s) or no_room_for_torches(s):
```

with:

```python
    had or no room for them (`no_room_for_torches`); W1: none for a wild pet that does not know wild:light."""
    if not unlocked(s, "light") or not coal_known(s) or no_room_for_torches(s):
```

and replace:

```python
    when its arms have no room for it now."""
    if s.count("campfire") >= 1:
```

with:

```python
    when its arms have no room for it now. W1: a wild pet that does not know wild:fire goes without one."""
    if s.count("campfire") >= 1 or not unlocked(s, "fire"):
```

and replace:

```python
    wanted = [("torch", count) for count in range(s.count("torch") + 1, PACK_TORCHES + 1)]
    for item, count in wanted + ([("campfire", 1)] if s.count("campfire") < 1 else []):
```

with:

```python
    wanted = [("torch", count) for count in range(s.count("torch") + 1, PACK_TORCHES + 1)] if unlocked(s, "light") else []
    for item, count in wanted + ([("campfire", 1)] if s.count("campfire") < 1 and unlocked(s, "fire") else []):
```

In `backend/survival/goals.py`, replace:

```python
from backend.survival.triggers import ensure_brain, mark_trigger
```

with:

```python
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.wild import goal_open
```

and replace:

```python
    if not counted(goal) or (goal.name in reached(s) and not goal.repeat):
```

with:

```python
    if not counted(goal) or (goal.name in reached(s) and not goal.repeat) or not goal_open(goal.name, s):  # W1
```

In `backend/survival/purposes.py`, replace:

```python
from backend.survival.trips import best_trip, lift, next_stop, trip_facts
```

with:

```python
from backend.survival.trips import best_trip, lift, next_stop, trip_facts
from backend.survival.wild import purpose_open
```

and replace:

```python
    """A purpose's validity check. One that crashes counts as not valid (logged once)."""
    try:
        return bool(purpose.valid(situation))
```

with:

```python
    """A purpose's validity check. One that crashes counts as not valid (logged once). W1: a wild pet is offered
    a purpose a survival lesson unlocks only once it knows the lesson (wild.purpose_open)."""
    try:
        return purpose_open(purpose.name, situation) and bool(purpose.valid(situation))
```

In `backend/survival/reflexes.py`, replace:

```python
from backend.survival.vitals import EXHAUSTED_BELOW, WARM_BLOCKS, is_sheltered
```

with:

```python
from backend.survival.vitals import EXHAUSTED_BELOW, WARM_BLOCKS, is_sheltered
from backend.survival.wild import fitting_open
```

and replace:

```python
    fire = next((block for block in WARM_BLOCKS if s.inventory.get(block, 0) > 0), None)
```

with:

```python
    fire = next((block for block in WARM_BLOCKS if s.inventory.get(block, 0) > 0 and fitting_open(block, s)), None)
```

In `backend/survival/wild.py`, replace:

```python
SOURCES = {TAUGHT: "from_you", BORN_KNOWING: "from_start"}
```

with:

```python
SOURCES = {TAUGHT: "from_you", BORN_KNOWING: "from_start"}
# What a wild pet has only once it knows a lesson (the table's "Unlocks" column): the purposes on offer
# (purposes.is_valid), the goals (goals.is_open) and the fittings of a shelter it makes and puts in
# (building.fittings_due, and the warm_up reflex's carried fire). The recipes behind them are gated where
# they are planned: a campfire (cooking, camp, expedition), a bed and a door (building).
PURPOSE_LESSONS = {"build_shelter": "shelter", "improve_home": "shelter", "camp": "shelter", "light_up": "light"}
GOAL_LESSONS = {"first_shelter": "shelter", "safe_yard": "light"}
FITTING_LESSONS = {"bed": "bed", "campfire": "fire", "door": "shelter"}
```

and replace:

```python
    return not is_wild(s.state) or knows(s, name)
```

with:

```python
    return not is_wild(s.state) or knows(s, name)


def purpose_open(name: str, s: Situation) -> bool:
    """The purpose `name` may be offered: it needs no lesson, or Mimo may use what its lesson unlocks."""
    lesson = PURPOSE_LESSONS.get(name)
    return lesson is None or unlocked(s, lesson)


def goal_open(name: str, s: Situation) -> bool:
    """The goal `name` may be offered (a built home needs `wild:shelter`, a safe yard `wild:light`)."""
    lesson = GOAL_LESSONS.get(name)
    return lesson is None or unlocked(s, lesson)


def fitting_open(block: str, s: Situation) -> bool:
    """Mimo may make and put in the fitting `block` (a bed, a campfire, a door)."""
    lesson = FITTING_LESSONS.get(block)
    return lesson is None or unlocked(s, lesson)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild_gates.py"`
Expected: `Ran 7 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1852 tests` … `OK (skipped=5)` (7 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/building.py backend/survival/camp.py backend/survival/cooking.py backend/survival/expedition.py backend/survival/goals.py backend/survival/purposes.py backend/survival/reflexes.py backend/survival/wild.py backend/tests/test_survival_wild_gates.py
git commit -m "feat(W1): a wild pet builds a shelter, a bed, a campfire and torches, and cooks, only once it knows how" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Nightberries and sunleaf in worldgen, in both ports

**Files:**
- Modify: `shared/blocks.json` (`nightberry_bush`, `nightberry_bush_ripe`, `sunleaf`), `backend/services/worldgen.py` and `frontend/src/engine/worldgen.ts` (`wild_herb` / `wildHerb`), `frontend/src/engine/atlas.ts` (two painters), `backend/survival/nature.py` (`PICKS`), `backend/survival/renewal.py` (regrowth), `backend/scripts/worldgen_fixture.py` (the plants' columns), `shared/worldgen-fixture.json` (regenerated, not transcribed)
- Modify: `backend/tests/test_survival_frontier_gear.py` (the last block is no longer L5's), `frontend/src/engine/blocks.test.ts`, `frontend/src/engine/worldgen.test.ts`
- Test: `backend/tests/test_worldgen_wild.py`

**Interfaces:**
- Consumes: `worldgen.plant_stack`, `hash_noise`, `LEGACY_RADIUS`; `nature.PICKS`; `renewal`'s berry regrowth and mushroom respawn; the fixture script.
- Produces: `worldgen.NIGHTBERRY_RARITY = 150`, `SUNLEAF_RARITY = 180`, channels 160 and 161, `SUNLEAF_BIOMES`, `wild_herb(x, z, biome, top)` (and `wildHerb` in TypeScript, identical); picking a ripe nightberry bush gives 3 `nightberries` and leaves `nightberry_bush`; a sunleaf gives 1 `sunleaf`; `renewal.SUNLEAF_CAP = 2`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_frontier_gear.py`, replace:

```python
        self.assertEqual(names[-1], "warding_lantern")
```

with:

```python
        self.assertEqual(names[-4], "warding_lantern")  # W1's three plants come after it (test_worldgen_wild)
```

Create `backend/tests/test_worldgen_wild.py`:

```python
"""W1: nightberry bushes and sunleaf in the world, only on bare natural columns (both ports: the fixture)."""

import math
import sqlite3
import unittest
from unittest.mock import patch

from backend.services import worldgen
from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, is_replaceable, is_solid
from backend.services.worldgen import LEGACY_RADIUS, plant_at, plant_stack
from backend.survival import nature
from backend.survival.actions import ActionContext
from backend.survival.fieldwork import finish_pick, start_pick
from backend.survival.grid import Grid
from backend.survival.renewal import BERRY_REGROW, create_growth_table, renew, scheduled

SEED = "123456789123456789"
AREA = [(x, z) for x in range(3000, 3160) for z in range(-80, 80)]


def plants(area=AREA):
    plant_stack.cache_clear()
    return {(x, z): plant_at(x, z, SEED) for x, z in area}


class WorldgenTests(unittest.TestCase):
    def test_the_new_plants_grow_only_where_nothing_grew_before(self):
        now = plants()
        with patch.object(worldgen, "wild_herb", lambda *args: None):
            before = plants()
        plant_stack.cache_clear()
        changed = {column: now[column] for column in AREA if now[column] != before[column]}
        self.assertTrue(changed)
        self.assertEqual({before[column] for column in changed}, {None})
        self.assertEqual(set(changed.values()), {"nightberry_bush_ripe", "sunleaf"})

    def test_about_two_nightberry_bushes_for_three_berry_bushes_and_none_in_the_clearing(self):
        found = list(plants().values())
        berries, nightberries = found.count("berry_bush_ripe"), found.count("nightberry_bush_ripe")
        self.assertTrue(0.45 < nightberries / berries < 0.85, (berries, nightberries))
        self.assertGreater(found.count("sunleaf"), 0)
        clearing = plants([(x, z) for x in range(-LEGACY_RADIUS, LEGACY_RADIUS, 3) for z in range(-60, 60, 3)
                           if math.hypot(x, z) <= LEGACY_RADIUS])
        self.assertFalse({"nightberry_bush_ripe", "sunleaf"} & set(clearing.values()))

    def test_the_blocks_come_last_and_give_way_like_tall_grass(self):
        names = [block["name"] for block in BLOCK_LIST]
        self.assertEqual(names[-3:], ["nightberry_bush", "nightberry_bush_ripe", "sunleaf"])
        self.assertEqual(BLOCK_IDS["nightberry_bush"], BLOCK_IDS["warding_lantern"] + 1)
        for name in names[-3:]:
            self.assertTrue(is_replaceable(name), name)
            self.assertFalse(is_solid(name), name)


def meadow():
    return Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")


class GrowingTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        create_growth_table(self.db)
        self.grid = meadow()
        self.state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {}}

    def renew_at(self, at):
        renew(self.state, ActionContext(grid=self.grid, clock_at=lambda when: {"time_scale": 1.0}, planner=None,
                                        events=[], db=self.db), at)

    def test_a_ripe_nightberry_bush_gives_three_nightberries_and_ripens_again_in_two_game_days(self):
        self.grid.put(1, 1, 0, "nightberry_bush_ripe")
        self.grid.take_changes()
        step = start_pick({"kind": "pick", "target": [1, 1, 0]}, self.state, self.grid, 0.0, 1.0)
        finish_pick(step, self.state, self.grid, 1.0)
        self.assertEqual((self.state["inventory"], self.grid.material(1, 1, 0)), ({"nightberries": 3}, "nightberry_bush"))
        self.renew_at(1.0)
        self.assertEqual([(cell, block) for cell, block, _ in scheduled(self.db)], [((1, 1, 0), "nightberry_bush_ripe")])
        self.renew_at(1.0 + BERRY_REGROW)
        self.assertEqual(self.grid.material(1, 1, 0), "nightberry_bush_ripe")

    def test_a_picked_sunleaf_comes_back_in_its_chunk_like_a_mushroom(self):
        self.assertEqual(nature.PICKS["sunleaf"], ({"sunleaf": 1}, "air"))
        self.grid.put(3, 1, 3, "sunleaf")
        self.grid.take_changes()
        self.grid.put(3, 1, 3, "air")
        with patch("backend.survival.renewal.biome_at", lambda x, z, seed: "meadow"), \
                patch("backend.survival.renewal.terrain_height", lambda x, z, seed: 0):
            self.renew_at(10.0)
            [(cell, block, _)] = scheduled(self.db)
            self.assertEqual(block, "sunleaf")
            self.renew_at(10.0 + 3600.0)
        self.assertEqual(self.grid.material(*cell), "sunleaf")


if __name__ == "__main__":
    unittest.main()
```

In `frontend/src/engine/blocks.test.ts`, replace:

```ts
/** L5's blocks, after Making's wiring, the last (backend/tests/test_survival_frontier_gear.py). */
const FRONTIER = ['warding_lantern']
```

with:

```ts
/** L5's blocks, after Making's wiring (backend/tests/test_survival_frontier_gear.py). */
const FRONTIER = ['warding_lantern']
/** W1's plants, after L5's, the last (backend/tests/test_worldgen_wild.py). */
const WILD = ['nightberry_bush', 'nightberry_bush_ripe', 'sunleaf']
```

and replace:

```ts
    expect(names.slice(-FRONTIER.length)).toEqual(FRONTIER)
```

with:

```ts
    expect(names.slice(-WILD.length - FRONTIER.length, -WILD.length)).toEqual(FRONTIER)
    expect(names.slice(-WILD.length)).toEqual(WILD)
    for (const name of WILD) {
      expect(LAYER_BY_ID[blockId(name)], name).toBe(LAYER_CUTOUT)
      expect(blockDef(blockId(name)).solid, name).toBe(false)
    }
```

In `frontend/src/engine/worldgen.test.ts`, replace:

```ts

  it('keeps cave mushrooms off the air an entrance carved, exactly like blockAt', () => {
```

with:

```ts

  it('grows W1\'s nightberry bushes and sunleaf on bare columns inside columns exactly like blockAt', () => {
    const chunks = new Map<string, [number, number]>()
    for (let x = 300; x < 900 && chunks.size < 2; x++) {
      for (let z = -40; z < 40 && chunks.size < 2; z++) {
        const plant = plantStack(x, z, WILD_SEED)?.[0]
        if (plant === 'nightberry_bush_ripe' || plant === 'sunleaf') chunks.set(plant, [Math.floor(x / 16), Math.floor(z / 16)])
      }
    }
    expect([...chunks.keys()].sort()).toEqual(['nightberry_bush_ripe', 'sunleaf'])
    for (const [cx, cz] of chunks.values()) expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
  })

  it('keeps cave mushrooms off the air an entrance carved, exactly like blockAt', () => {
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen_wild.py"`
Expected: `FAILED (failures=2, errors=3)`: the blocks do not exist yet (`KeyError: 'sunleaf'`)

Run: `cd frontend && npx vitest run src/engine/blocks.test.ts src/engine/worldgen.test.ts`
Expected: FAIL: the new blocks are not in `shared/blocks.json` and `wildHerb` is not exported.

- [ ] **Step 3: The blocks, both ports, picking and regrowth**

In `backend/scripts/worldgen_fixture.py`, replace:

```python
WILD_FOOD = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")
```

with:

```python
WILD_FOOD = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")
WILD_HERBS = ("nightberry_bush_ripe", "sunleaf")  # W1: the plants of bare columns
```

and replace:

```python
            if plant_at(x, z, seed) in WILD_FOOD:
                found.append((x, z))
                if len(found) == count:
                    return found
    return found
```

with:

```python
            if plant_at(x, z, seed) in WILD_FOOD:
                found.append((x, z))
                if len(found) == count:
                    return found
    return found


def _wild_herbs(seed: str, count: int) -> list[tuple[int, int]]:
    """W1: columns with a nightberry bush and columns with a sunleaf, `count` of each."""
    seen: dict[str, int] = {}
    found = []
    for x in range(250, 1250):
        for z in range(-60, 60, 2):
            plant = plant_at(x, z, seed)
            if plant in WILD_HERBS and seen.get(plant, 0) < count:
                seen[plant] = seen.get(plant, 0) + 1
                found.append((x, z))
                if len(seen) == len(WILD_HERBS) and all(value == count for value in seen.values()):
                    return found
    return found
```

and replace:

```python
        for x, z in _plants(seed, 20) + _wild_food(seed, 40):
```

with:

```python
        for x, z in _plants(seed, 20) + _wild_food(seed, 40) + _wild_herbs(seed, 6):
```

In `backend/services/worldgen.py`, replace:

```python
FRUIT_BIOMES = ("meadow", "forest", "birch_forest")
```

with:

```python
FRUIT_BIOMES = ("meadow", "forest", "birch_forest")
# W1: two plants that grow only where nothing grew before (after tall grass), never in the legacy clearing,
# so no plant anywhere moves: nightberry bushes on berries' ground (1 in 150 such bare columns, channel 160)
# and sunleaf on the grass, moss or mud of the green lands (1 in 180, channel 161).
NIGHTBERRY_RARITY = 150
NIGHTBERRY_CHANNEL = 160
SUNLEAF_RARITY = 180
SUNLEAF_CHANNEL = 161
SUNLEAF_BIOMES = ("meadow", "forest", "birch_forest", "taiga", "swamp")
```

and replace:

```python

def tall_plant(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
```

with:

```python

def wild_herb(x: int, z: int, seed: str, biome: str, surface: str) -> str | None:
    """W1: a ripe nightberry bush (the berry bush's ground: meadow and forest-edge grass) or a sunleaf (grass,
    moss or mud in the green lands) on a bare column of generated land; None in the legacy clearing."""
    if math.hypot(x, z) <= LEGACY_RADIUS:
        return None
    wooded = biome in ("forest", "birch_forest")
    if surface == "grass" and (biome == "meadow" or (wooded and noise2(x, z, 160, seed, 5) < FOREST_EDGE)):
        if hash32(x, 0, z, seed, NIGHTBERRY_CHANNEL) % NIGHTBERRY_RARITY == 0:
            return "nightberry_bush_ripe"
    if biome in SUNLEAF_BIOMES and hash32(x, 0, z, seed, SUNLEAF_CHANNEL) % SUNLEAF_RARITY == 0:
        return "sunleaf"
    return None


def tall_plant(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
```

and replace:

```python
    return ("tall_grass", 1) if hash32(x, 0, z, seed, 14) % rarity == 0 else None
```

with:

```python
    if hash32(x, 0, z, seed, 14) % rarity == 0:
        return "tall_grass", 1
    herb = wild_herb(x, z, seed, biome, surface)  # W1: only where nothing grew before
    return (herb, 1) if herb else None
```

In `backend/survival/nature.py`, replace:

```python
MUSHROOMS = ("brown_mushroom", "red_mushroom")
```

with:

```python
MUSHROOMS = ("brown_mushroom", "red_mushroom")
# W1: a ripe nightberry bush gives 3 nightberries and regrows like a berry bush; a sunleaf is taken whole.
PICKS.update({"nightberry_bush_ripe": ({"nightberries": 3}, "nightberry_bush"), "sunleaf": ({"sunleaf": 1}, "air")})
```

In `backend/survival/renewal.py`, replace:

```python
     per game day and at most 3 in the chunk, never in a claimed cell.
```

with:

```python
     per game day and at most 3 in the chunk, never in a claimed cell;
   - W1: a picked nightberry bush turns ripe again after 2 game days, like a berry bush, and a picked
     sunleaf comes back in its chunk like a mushroom, on the grass, moss or mud of the lands it grows in,
     one a chunk a game day and at most 2 in the chunk.
```

and replace:

```python
from backend.services.worldgen import biome_at, is_leaf, terrain_height
```

with:

```python
from backend.services.worldgen import SUNLEAF_BIOMES, biome_at, is_leaf, terrain_height
```

and replace:

```python
FOREST_FLOOR = ("grass", "moss")
```

with:

```python
FOREST_FLOOR = ("grass", "moss")
SUNLEAF_CAP = 2  # W1
SUNLEAF_GROUND = ("grass", "moss", "mud")
```

and replace:

```python
                 avoid: frozenset[Cell] = frozenset()) -> Cell | None:
```

with:

```python
                 avoid: frozenset[Cell] = frozenset(), biomes: tuple[str, ...] = ("forest", "birch_forest"),
                 ground: tuple[str, ...] = FOREST_FLOOR) -> Cell | None:
```

and replace:

```python
        if biome_at(x, z, seed) not in ("forest", "birch_forest"):
```

with:

```python
        if biome_at(x, z, seed) not in biomes:
```

and replace:

```python
        if grid.material(x, y, z) == "air" and grid.material(x, y - 1, z) in FOREST_FLOOR:
```

with:

```python
        if grid.material(x, y, z) == "air" and grid.material(x, y - 1, z) in ground:
```

and replace:

```python
def mushrooms_in_chunk(grid: Grid, seed: str, chunk: tuple[int, int]) -> int:
    """Mushrooms standing on the chunk's surface."""
    cx, cz = chunk
    return sum(1 for x in range(cx * CHUNK, cx * CHUNK + CHUNK) for z in range(cz * CHUNK, cz * CHUNK + CHUNK)
               if grid.material(x, terrain_height(x, z, seed) + 1, z) in nature.MUSHROOMS)
```

with:

```python
def mushrooms_in_chunk(grid: Grid, seed: str, chunk: tuple[int, int], kinds: tuple[str, ...] = nature.MUSHROOMS) -> int:
    """Mushrooms (W1: or any of `kinds`) standing on the chunk's surface."""
    cx, cz = chunk
    return sum(1 for x in range(cx * CHUNK, cx * CHUNK + CHUNK) for z in range(cz * CHUNK, cz * CHUNK + CHUNK)
               if grid.material(x, terrain_height(x, z, seed) + 1, z) in kinds)
```

and replace:

```python
    rows = db.execute("SELECT x, y, z, ready_at FROM growth WHERE block IN (?, ?) AND x BETWEEN ? AND ? "
                      "AND z BETWEEN ? AND ?", (*nature.MUSHROOMS, x0, x0 + CHUNK - 1, z0, z0 + CHUNK - 1)).fetchall()
    avoid = chosen | {(row[0], row[1], row[2]) for row in rows}
    spot = forest_floor(grid, seed, chunk, at, avoid)
```

with:

```python
    kinds = ("sunleaf",) if kind == "sunleaf" else nature.MUSHROOMS  # W1: sunleaf comes back the same way
    marks = ",".join("?" * len(kinds))
    rows = db.execute(f"SELECT x, y, z, ready_at FROM growth WHERE block IN ({marks}) AND x BETWEEN ? AND ? "
                      "AND z BETWEEN ? AND ?", (*kinds, x0, x0 + CHUNK - 1, z0, z0 + CHUNK - 1)).fetchall()
    avoid = chosen | {(row[0], row[1], row[2]) for row in rows}
    spot = (forest_floor(grid, seed, chunk, at, avoid, SUNLEAF_BIOMES, SUNLEAF_GROUND) if kind == "sunleaf"
            else forest_floor(grid, seed, chunk, at, avoid))
```

and replace:

```python
        if before in nature.MUSHROOMS and after == "air":
```

with:

```python
        if (before in nature.MUSHROOMS or before == "sunleaf") and after == "air":
```

and replace:

```python
        elif after == "berry_bush":
            schedule(db, cell, "berry_bush_ripe", later(at, BERRY_REGROW, scale))
```

with:

```python
        elif after in ("berry_bush", "nightberry_bush"):  # W1: nightberries regrow like berries
            schedule(db, cell, f"{after}_ripe", later(at, BERRY_REGROW, scale))
```

and replace:

```python
    if block == "berry_bush_ripe":
        if here == "berry_bush":
```

with:

```python
    if block in ("berry_bush_ripe", "nightberry_bush_ripe"):
        if here == block[:-len("_ripe")]:
```

and replace:

```python
                and mushrooms_in_chunk(grid, seed, (x // CHUNK, z // CHUNK)) < MUSHROOM_CAP):
```

with:

```python
                and mushrooms_in_chunk(grid, seed, (x // CHUNK, z // CHUNK)) < MUSHROOM_CAP):
            grid.put(*cell, block)
    elif block == "sunleaf":  # W1
        seed = state.get("world_seed", "0")
        if (here == "air" and grid.material(x, y - 1, z) in SUNLEAF_GROUND and not grid.claimed(cell)
                and mushrooms_in_chunk(grid, seed, (x // CHUNK, z // CHUNK), ("sunleaf",)) < SUNLEAF_CAP):
```

In `frontend/src/engine/atlas.ts`, replace:

```ts
  },
  sprite_mushroom: ({ color, accent }, random) => grid((i, j) => {
```

with:

```ts
  },
  // W1: a nightberry bush, the berry bush's shape with dark berries, each with a pale speck beside it
  sprite_speckled_bush: ({ color, accent }, random) => {
    const berries = [[1, 4], [3, 3], [5, 5], [2, 6], [6, 3]]
    return grid((i, j) => {
      const dx = (i - 3.5) / 4, dy = (j - 4.6) / 3.4
      if (dx * dx + dy * dy > 1) return CLEAR
      if (berries.some(([x, y]) => x === i && y === j)) return tone(accent ?? color, jitter(random))
      if (berries.some(([x, y]) => x + 1 === i && y === j)) return tone([214, 206, 222], jitter(random))
      return tone(color, (random() < 0.22 ? 0.76 : 1) * jitter(random, 0.14))
    })
  },
  // W1: sunleaf, a low yellow-green rosette of leaves round a bright middle
  sprite_rosette: ({ color, accent }, random) => grid((i, j) => {
    if (j < 4) return CLEAR
    const dx = i - 3.5, dy = (j - 6) * 1.6
    const reach = dx * dx + dy * dy
    if (reach > 12.5) return CLEAR
    if (reach < 1.5) return tone(accent ?? color, jitter(random))
    return tone(color, ((i + j) % 2 === 0 ? 0.84 : 1) * jitter(random, 0.12))
  }),
  sprite_mushroom: ({ color, accent }, random) => grid((i, j) => {
```

In `frontend/src/engine/worldgen.ts`, replace:

```ts
const FRUIT_BIOMES = new Set(['meadow', 'forest', 'birch_forest'])
```

with:

```ts
const FRUIT_BIOMES = new Set(['meadow', 'forest', 'birch_forest'])
// W1: nightberry bushes and sunleaf, only where nothing grew before (see backend/services/worldgen.py).
const NIGHTBERRY_RARITY = 150
const NIGHTBERRY_CHANNEL = 160
const SUNLEAF_RARITY = 180
const SUNLEAF_CHANNEL = 161
const SUNLEAF_BIOMES = new Set(['meadow', 'forest', 'birch_forest', 'taiga', 'swamp'])
```

and replace:

```ts

/** A cactus in the desert, or sugar cane on a shore right beside a lake, with how many blocks high it
```

with:

```ts

/** W1: a ripe nightberry bush (meadow and forest-edge grass) or a sunleaf (grass, moss or mud in the green lands)
 * on a bare column of generated land; null in the legacy clearing. */
export function wildHerb(x: number, z: number, seed: string, biome: string, surface: string): string | null {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return null
  const wooded = biome === 'forest' || biome === 'birch_forest'
  if (surface === 'grass' && (biome === 'meadow' || (wooded && noise2(x, z, 160, seed, 5) < FOREST_EDGE))) {
    if (hash32(x, 0, z, seed, NIGHTBERRY_CHANNEL) % NIGHTBERRY_RARITY === 0) return 'nightberry_bush_ripe'
  }
  if (SUNLEAF_BIOMES.has(biome) && hash32(x, 0, z, seed, SUNLEAF_CHANNEL) % SUNLEAF_RARITY === 0) return 'sunleaf'
  return null
}

/** A cactus in the desert, or sugar cane on a shore right beside a lake, with how many blocks high it
```

and replace:

```ts
  return hash32(x, 0, z, seed, 14) % (biome === 'swamp' ? 11 : 19) === 0 ? ['tall_grass', 1] : null
```

with:

```ts
  if (hash32(x, 0, z, seed, 14) % (biome === 'swamp' ? 11 : 19) === 0) return ['tall_grass', 1]
  const herb = wildHerb(x, z, seed, biome, surface)  // W1: only where nothing grew before
  return herb ? [herb, 1] : null
```

In `shared/blocks.json`, replace:

```json
    "warding_lantern": {"pattern": "glow", "color": [176, 150, 236]}
```

with:

```json
    "warding_lantern": {"pattern": "glow", "color": [176, 150, 236]},
    "nightberry_bush": {"pattern": "sprite_bush", "color": [76, 128, 100]},
    "nightberry_bush_ripe": {"pattern": "sprite_speckled_bush", "color": [76, 128, 100], "accent": [74, 40, 96]},
    "sunleaf": {"pattern": "sprite_rosette", "color": [178, 196, 70], "accent": [226, 214, 96]}
```

and replace:

```json
    {"name": "warding_lantern", "color": [176, 150, 236], "textures": "warding_lantern", "layer": "opaque", "solid": true, "drop": "warding_lantern", "glow": true, "hardness": 0.6}
```

with:

```json
    {"name": "warding_lantern", "color": [176, 150, 236], "textures": "warding_lantern", "layer": "opaque", "solid": true, "drop": "warding_lantern", "glow": true, "hardness": 0.6},
    {"name": "nightberry_bush", "color": [76, 128, 100], "textures": "nightberry_bush", "layer": "cutout", "solid": false, "replaceable": true, "drop": null, "hardness": 0.1},
    {"name": "nightberry_bush_ripe", "color": [74, 40, 96], "textures": "nightberry_bush_ripe", "layer": "cutout", "solid": false, "replaceable": true, "drop": null, "hardness": 0.1},
    {"name": "sunleaf", "color": [178, 196, 70], "textures": "sunleaf", "layer": "cutout", "solid": false, "replaceable": true, "drop": "sunleaf", "hardness": 0.1}
```

- [ ] **Step 4: Regenerate the fixture**

Run: `python3 -m backend.scripts.worldgen_fixture`
Expected: it rewrites `shared/worldgen-fixture.json` with 43,588 cells (was 43,540).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen*.py"`
Expected: `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1857 tests` … `OK (skipped=5)` (5 new).

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  367 passed (367)`, the build succeeds, eslint prints nothing.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/worldgen_fixture.py backend/services/worldgen.py backend/survival/nature.py backend/survival/renewal.py backend/tests/test_survival_frontier_gear.py backend/tests/test_worldgen_wild.py frontend/src/engine/atlas.ts frontend/src/engine/blocks.test.ts frontend/src/engine/worldgen.test.ts frontend/src/engine/worldgen.ts shared/blocks.json shared/worldgen-fixture.json
git commit -m "feat(W1): nightberry bushes and sunleaf grow on bare ground, in both ports, and regrow" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Sickness and sunleaf

**Files:**
- Create: `backend/survival/ailments.py`, `backend/survival/herbs.py`
- Modify: `backend/survival/vitals.py` (`Ailing`, the cause "sickness"), `backend/survival/steps.py` (`EATING`, `HERBS`), `backend/survival/tick.py` (`ailing`, `tend`, the cause's words), `backend/survival/snapshot.py` (`ailments`), `backend/survival/brain.py` (imports `herbs`)
- Modify: `backend/tests/test_survival_reflexes.py` (the reflex order)
- Test: `backend/tests/test_survival_ailments.py`

**Interfaces:**
- Consumes: Task 1's `is_wild`, `wild_state`; Task 4's sunleaf; `vitals.step_vitals`; `steps.start_eat`, `finish_eat`; `senses`; `reflexes.register`; `purposes.register`, `goals.add_urge`.
- Produces:
  - `vitals.Ailing(drain, hunger, energy, heals, mood)`; `step_vitals(..., ailing=None)`; `CAUSE_ORDER` gains `"sickness"` after starvation.
  - `ailments.AILMENTS` (tummy, chill), `sickness(state)`, `sick(state)`, `fall_sick(state, kind, at, events=None, text=None) -> bool`, `cure(state)`, `ailing(state) -> Ailing | None`, `tend(state, context, seconds, activity, at)`, `eat_herb` (in `steps.EATING`), `ailments_view(state)`; `NIBBLE_CHANCE = 0.4` (channel 200).
  - `steps.EATING: list` of `(step, state, at) -> event | None`, run first in `finish_eat`; `steps.HERBS = ("sunleaf",)` (eaten as medicine, never as a meal).
  - `ailments.lose(state, health)`: `state["wild"]["lost"]`, the health a wild pet lost to its hazards (`tend` counts the drain after each vitals step).
  - `herbs`: the reflex `take_herb` (45), the purposes `find_herb` (75), `gather_herbs` (52, a need) and `nibble` (70).
  - `/api/mimo` gains `ailments` (`{"sick": {kind, label, words, minutes} | null, "wound": null}`; Task 8 fills `wound` with `{festering, dressed, minutes}`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_ailments.py`:

```python
"""W1: a wild pet's sicknesses: a tummy ache and a chill, what they drain, and sunleaf."""

import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every purpose and reflex registered)
from backend.survival.ailments import AILMENTS, ailing, ailments_view, fall_sick, sickness, tend
from backend.survival.hatch import hatch
from backend.survival.memory import know
from backend.survival.purposes import PURPOSES, is_valid
from backend.survival.reflexes import by_name
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import survival_view
from backend.survival.steps import finish_step, start_step
from backend.survival.tick import death_words, tick_life
from backend.survival.vitals import START_VITALS, Surroundings, step_vitals
from backend.survival.wild import thing
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_cooking import meadow, situation

BORN = 1_000_000.0
QUIET = Surroundings(biome="meadow", sheltered=True)


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "difficulty": "wild"}
    state.update(changes)
    return state


def run(state, seconds, activity="working", step=10.0):
    """Vitals and the sickness's time for `seconds` game seconds, in steps like the tick's."""
    events = []
    for _ in range(int(seconds / step)):
        state["vitals"], cause = step_vitals(state["vitals"], step, night=False, activity=activity, surroundings=QUIET,
                                             ailing=ailing(state))
        tend(state, step, activity, 0.0, events)
        if cause:
            return cause
    return None


class SicknessTests(unittest.TestCase):
    def test_a_tummy_ache_lasts_twelve_game_minutes_and_takes_thirty_six_health(self):
        state = pet()
        self.assertTrue(fall_sick(state, "tummy", 0.0))
        self.assertEqual(state["last_thought"], "My tummy hurts.")
        run(state, 12 * 60)
        self.assertIsNone(sickness(state))
        self.assertAlmostEqual(state["vitals"]["health"], 100 - 12 * 60 / 20, places=3)
        self.assertAlmostEqual(state["wild"]["lost"], 12 * 60 / 20, places=3)  # lost to a hazard

    def test_a_chill_takes_fifty_and_passes_twice_as_fast_resting_warm(self):
        state = pet()
        fall_sick(state, "chill", 0.0)
        run(state, 25 * 60)
        self.assertAlmostEqual(state["vitals"]["health"], 50.0, places=3)
        warm = pet()
        fall_sick(warm, "chill", 0.0)
        run(warm, 12.5 * 60 + 10, activity="sleeping")
        self.assertIsNone(sickness(warm))

    def test_no_health_comes_back_while_sick_and_hunger_or_energy_drains_faster(self):
        well, ill = pet(), pet()
        for state in (well, ill):
            state["vitals"]["health"] = 80.0
        fall_sick(ill, "tummy", 0.0)
        run(well, 60, activity="idle")
        run(ill, 60, activity="idle")
        self.assertGreater(well["vitals"]["health"], 80.0)
        self.assertLess(ill["vitals"]["health"], 80.0)
        self.assertAlmostEqual(100 - ill["vitals"]["hunger"], 1.5 * (100 - well["vitals"]["hunger"]), places=6)
        chilled, rested = pet(), pet()
        fall_sick(chilled, "chill", 0.0)
        run(chilled, 60, activity="idle")
        run(rested, 60, activity="idle")
        self.assertAlmostEqual(100 - chilled["vitals"]["energy"], 1.5 * (100 - rested["vitals"]["energy"]), places=6)

    def test_one_sickness_at_a_time_the_longer_stays(self):
        state = pet()
        fall_sick(state, "tummy", 0.0)
        self.assertFalse(fall_sick(state, "chill", 1.0))
        self.assertEqual((sickness(state)["kind"], sickness(state)["left"]), ("chill", AILMENTS["chill"].lasts))
        fall_sick(state, "tummy", 2.0)
        self.assertEqual(sickness(state)["kind"], "chill")

    def test_sickness_can_kill_and_the_memorial_says_so(self):
        state = pet()
        state["vitals"]["health"] = 3.0
        fall_sick(state, "tummy", 0.0)
        self.assertEqual(run(state, 12 * 60, activity="idle"), "sickness")
        self.assertEqual(death_words("sickness"), "fell sick and never got better")

    def test_a_gentle_pet_is_never_ailing(self):
        self.assertIsNone(ailing({"vitals": dict(START_VITALS)}))
        self.assertEqual(ailments_view({}), {"sick": None, "wound": None})


class SunleafTests(unittest.TestCase):
    def test_eating_sunleaf_ends_any_sickness(self):
        state = pet(inventory={"sunleaf": 1})
        fall_sick(state, "chill", 0.0)
        step = start_step({"kind": "eat", "item": "sunleaf"}, state, meadow(), 0.0)
        self.assertEqual(finish_step(step, state, meadow(), 1.6), ("cured", "Pip ate sunleaf and felt better."))
        self.assertIsNone(sickness(state))
        self.assertEqual(state["inventory"], {})

    def test_take_herb_eats_a_carried_sunleaf_once_mimo_knows_it(self):
        s = situation({"sunleaf": 1})
        s.state["difficulty"] = "wild"
        fall_sick(s.state, "tummy", 0.0)
        reflex = by_name("take_herb")
        self.assertEqual(reflex.priority, 45)
        self.assertFalse(reflex.trigger(s))
        know(s.db, thing("sunleaf"), "lesson", 0.0)
        s.__dict__.pop("lessons", None)
        self.assertTrue(reflex.trigger(s))
        self.assertEqual(reflex.plan(s, None), [{"kind": "eat", "item": "sunleaf"}])

    def test_find_herb_and_nibble_walk_to_a_sunleaf_they_see(self):
        grid = meadow({(10, 1, 0): "sunleaf"})
        s = situation({}, grid)
        s.state["difficulty"] = "wild"
        fall_sick(s.state, "tummy", 0.0)
        s.state["ailments"]["sick"]["nibble"] = True
        self.assertTrue(is_valid(PURPOSES["nibble"], s))
        self.assertFalse(is_valid(PURPOSES["find_herb"], s))
        self.assertEqual(PURPOSES["nibble"].plan(s, None)[-2:],
                         [{"kind": "pick", "target": [10, 1, 0]}, {"kind": "eat", "item": "sunleaf"}])
        know(s.db, thing("sunleaf"), "lesson", 0.0)
        taught = situation({}, grid)
        taught.state.update(difficulty="wild", ailments=s.state["ailments"])
        taught.db = s.db
        self.assertTrue(is_valid(PURPOSES["find_herb"], taught))
        self.assertFalse(is_valid(PURPOSES["nibble"], taught))
        self.assertEqual(PURPOSES["find_herb"].score(taught), 75.0)

    def test_a_pet_that_knows_sunleaf_carries_two(self):
        grid = meadow({(3, 1, 0): "sunleaf", (5, 1, 0): "sunleaf", (7, 1, 0): "sunleaf"})
        s = situation({}, grid)
        s.state["difficulty"] = "wild"
        self.assertFalse(is_valid(PURPOSES["gather_herbs"], s))
        know(s.db, thing("sunleaf"), "lesson", 0.0)
        s.__dict__.pop("lessons", None)
        self.assertTrue(is_valid(PURPOSES["gather_herbs"], s))
        picks = [step["target"] for step in PURPOSES["gather_herbs"].plan(s, None) if step["kind"] == "pick"]
        self.assertEqual(picks, [[3, 1, 0], [5, 1, 0]])


class StreamTests(unittest.TestCase):
    def test_api_mimo_shows_the_sickness_and_the_tick_runs_it(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                fall_sick(state, "tummy", BORN)
                write_state(db, state)
            tick_life(registry, BORN + 60, scale=1.0)
            view = survival_view(world, BORN + 60, 1.0)
        self.assertEqual(view["ailments"]["sick"], {"kind": "tummy", "label": "Tummy ache", "words": "My tummy hurts.",
                                                    "minutes": 11})
        self.assertLess(view["vitals"]["health"], 100.0)


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_reflexes.py`, replace:

```python
                          ("fence", 45), ("warm_up", 50), ("turn_back", 55), ("head_home", 60), ("collapse", 70)])
```

with:

```python
                          ("fence", 45), ("take_herb", 45), ("warm_up", 50), ("turn_back", 55), ("head_home", 60),
                          ("collapse", 70)])  # W1: take_herb (backend.survival.herbs)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_ailments.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.ailments'`

- [ ] **Step 3: Sickness, its drain in the vitals and sunleaf**

Create `backend/survival/ailments.py`:

```python
"""W1: a wild pet's sicknesses (docs/superpowers/specs/2026-09-27-wild-world-design.md, "Hazards").

Mimo has at most one sickness at a time, `state["ailments"]["sick"]` = {"kind", "since", "left"} (`left` in
game seconds), and a new one keeps the longer of the two (`fall_sick`). The kinds are AILMENTS:

| Kind | Symptom | Lasts | Drain | Also |
|---|---|---|---|---|
| tummy ache | "My tummy hurts." | 12 game minutes | 1 health per 20 game s | hunger drains 1.5 times as fast |
| chill | "I'm shivery and hot." | 25 game minutes | 1 health per 30 game s | energy drains 1.5 times as fast |

While Mimo is sick no health regenerates and mood's target falls 15 (`ailing`, read by the tick for each
vitals step: vitals.Ailing). A chill's time runs twice as fast while Mimo rests or sleeps with warmth 60 or
more (`tend`, after each vitals step). The sickness can kill: its drain is the cause "sickness" when it is
the largest damage of the killing step (vitals.CAUSE_ORDER). What the drain takes counts in
`state["wild"]["lost"]`, the health a wild pet lost to its hazards (`lose`; the balance gate reads it).

Eating one sunleaf ends any sickness at once: the eat step of a sunleaf (steps.EATING: `eat_herb`) logs
"Pip ate sunleaf and felt better." (a "cured" event). What makes Mimo sick (food, a cold night) and what
makes it eat sunleaf (the take_herb reflex, find_herb and nibble: backend.survival.herbs) live elsewhere.

A gentle pet never has an ailment: nothing in W1 makes one, and `ailing` gives nothing without one. A
crash in any of this is logged once and counts as nothing (wild.AILMENTS' guard is the tick's `tend`).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from backend.services.crafting import take_items
from backend.survival.nature import roll
from backend.survival.once import log_once
from backend.survival.steps import EATING
from backend.survival.vitals import Ailing
from backend.survival.wild import wild_state

logger = logging.getLogger(__name__)

GAME_MINUTE = 60.0
SICK_MOOD = 15.0
WARM_REST = 60.0  # warmth from which a chill passes twice as fast while Mimo rests or sleeps
HERB = "sunleaf"
HERB_HUNGER = 2.0  # hunger a sunleaf fills
NIBBLE_CHANCE = 0.4  # a sickness in which the instinct nibbles a sunleaf nearby (backend.survival.herbs)
NIBBLE_CHANNEL = 200  # Wild World's roll channels are 200 to 259 (spec resolution 27)


@dataclass(frozen=True)
class Ailment:
    kind: str
    words: str  # the symptom, in Mimo's words
    label: str  # for the HUD: "Tummy ache"
    lasts: float  # game seconds
    drain: float  # health a game second
    hunger: float = 1.0
    energy: float = 1.0


AILMENTS: dict[str, Ailment] = {
    "tummy": Ailment("tummy", "My tummy hurts.", "Tummy ache", 12 * GAME_MINUTE, 1 / 20, hunger=1.5),
    "chill": Ailment("chill", "I'm shivery and hot.", "Chill", 25 * GAME_MINUTE, 1 / 30, energy=1.5),
}


def ailments_of(state: dict) -> dict:
    """state["ailments"], with its fields (a world from before W1 has none)."""
    found = state.setdefault("ailments", {})
    found.setdefault("sick", None)
    found.setdefault("wound", None)
    return found


def pet_cell(state: dict) -> tuple[int, int, int]:
    """The cell Mimo stands in, for a roll."""
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def sickness(state: dict) -> dict | None:
    """Mimo's sickness now, or None (read only)."""
    return (state.get("ailments") or {}).get("sick")


def sick(state: dict) -> bool:
    return sickness(state) is not None


def fall_sick(state: dict, kind: str, at: float, events: list | None = None, text: str | None = None) -> bool:
    """Mimo falls sick with `kind`; with a sickness already, the longer of the two stays. Logs `text` as a
    "sick" event when given. True when this is a new sickness (none before)."""
    ailment = AILMENTS[kind]
    found = ailments_of(state)
    now = found["sick"]
    fresh = now is None
    if now is None:
        nibble = roll(state.get("world_seed", "0"), pet_cell(state), NIBBLE_CHANNEL, int(at)) < NIBBLE_CHANCE
        found["sick"] = {"kind": kind, "since": at, "left": ailment.lasts, "nibble": nibble}
    elif ailment.lasts > now["left"]:
        found["sick"] = {**now, "kind": kind, "left": ailment.lasts}
    state["last_thought"] = ailment.words
    if events is not None and text:
        events.append((at, "sick", text))
    return fresh


def cure(state: dict) -> bool:
    """Any sickness ends. True when there was one."""
    found = state.get("ailments") or {}
    if found.get("sick") is None:
        return False
    found["sick"] = None
    return True


def ailing(state: dict) -> Ailing | None:
    """What Mimo's ailments do to a vitals step now; None without any (a gentle pet, always)."""
    found = sickness(state)
    if found is None:
        return None
    ailment = AILMENTS.get(found["kind"])
    if ailment is None:
        return None
    return Ailing(drain=ailment.drain, hunger=ailment.hunger, energy=ailment.energy, heals=False, mood=SICK_MOOD)


def lose(state: dict, health: float) -> None:
    """Count `health` a wild pet lost to its hazards (a sickness's drain, a poison plant) in
    `state["wild"]["lost"]`."""
    if health > 0:
        found = wild_state(state)
        found["lost"] = found.get("lost", 0.0) + health


def tend(state: dict, seconds: float, activity: str, at: float, events: list) -> None:
    """After a vitals step of `seconds` game seconds: what its drain took is counted, and the sickness runs its
    time (a chill twice as fast while Mimo rests or sleeps warm). A crash is logged once and changes nothing."""
    try:
        ill = ailing(state)  # what the vitals step just took
        if ill is not None:
            lose(state, ill.drain * seconds)
        found = sickness(state)
        if found is None:
            return
        rested = activity != "working" and state["vitals"]["warmth"] >= WARM_REST
        found["left"] = max(0.0, found["left"] - seconds * (2.0 if found["kind"] == "chill" and rested else 1.0))
        if found["left"] <= 0:
            state["ailments"]["sick"] = None
            state["last_thought"] = "I feel better now."
    except Exception as error:
        log_once(logger, "ailments", error)


def eat_herb(step: dict, state: dict, at: float) -> tuple[str, str] | None:
    """steps.EATING: a sunleaf eaten ends any sickness ("cured"); None for any other food."""
    if step["item"] != HERB:
        return None
    state["inventory"] = take_items(state["inventory"], {HERB: 1})
    state["vitals"]["hunger"] = min(100.0, state["vitals"]["hunger"] + HERB_HUNGER)
    name = state["name"]
    if cure(state):
        state["last_thought"] = "That's better. I feel well again."
        return "cured", f"{name} ate sunleaf and felt better."
    return "ate", f"{name} ate sunleaf."


EATING.append(eat_herb)


def ailments_view(state: dict) -> dict:
    """For /api/mimo: {"sick": {"kind", "label", "words", "minutes"} or null, "wound": ... or null}."""
    found = sickness(state)
    sick_view = None
    if found is not None and found["kind"] in AILMENTS:
        ailment = AILMENTS[found["kind"]]
        sick_view = {"kind": ailment.kind, "label": ailment.label, "words": ailment.words,
                     "minutes": math.ceil(found["left"] / GAME_MINUTE)}
    return {"sick": sick_view, "wound": None}
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import cozy, machines, making, workshop  # noqa: F401  (Making's purposes and goals)
```

with:

```python
from backend.survival import cozy, machines, making, workshop  # noqa: F401  (Making's purposes and goals)
from backend.survival import herbs  # noqa: F401  (W1: sunleaf: take_herb, find_herb, gather_herbs, nibble)
```

Create `backend/survival/herbs.py`:

```python
"""W1: sunleaf, the little yellow herb that ends a sickness (backend.survival.ailments).

- `take_herb`, a reflex (priority 45, between eat_now and warm_up): a sick pet that knows `wild:sunleaf` and
  carries one eats it.
- `find_herb`, in the needs band (75): a sick pet that knows sunleaf but carries none walks to the nearest
  sunleaf within HERB_RANGE blocks, picks it and eats it.
- `gather_herbs` (52, a need: goals.URGES): by day, a pet that knows sunleaf picks one it sees within sight
  until it carries HERBS_CARRIED.
- `nibble`, the instinct of a pet that does not know sunleaf (70): sick, with a sunleaf within NIBBLE_RANGE
  blocks, it walks over and eats it, once in NIBBLE_CHANCE sicknesses (a seeded roll when the sickness
  begins: ailments.fall_sick). Eating one while sick is what teaches the lesson alone (backend.survival.knocks).
A gentle pet is never sick, so none of these is ever on offer to it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival.ailments import HERB, sickness
from backend.survival.foraging import STAND, whole_walk
from backend.survival.goals import add_urge
from backend.survival.grid import Cell
from backend.survival.purposes import Purpose, register
from backend.survival.reflexes import Reflex, register as register_reflex
from backend.survival.senses import FOOD_SIGHT, by_distance, natural_plants, near_failure
from backend.survival.situation import Situation
from backend.survival.wild import is_wild, knows

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

HERB_RANGE = 64.0
NIBBLE_RANGE = 16.0
HERBS_CARRIED = 2


def herbs_near(s: Situation, radius: float) -> list[Cell]:
    """Sunleaf standing within `radius` blocks, nearest first, away from a step that just failed: the wild
    ones worldgen grew and the ones that came back."""
    def look() -> list[Cell]:
        x, _, z = s.here
        cells = set(natural_plants(s.seed, x, z, radius, (HERB,)))
        cells.update(cell for cell, _ in s.grid.placed_cells(x, z, radius, (HERB,)))
        return [cell for cell in by_distance(cells, s.here)
                if s.grid.material(*cell) == HERB and not near_failure(s.state, cell)]
    return s.sensed(f"herbs {radius}", look)


def pick_and_eat(s: Situation, cell: Cell) -> list[dict]:
    walk = [whole_walk(cell, STAND)] if math.dist(s.here, cell) > STAND else []
    return [*walk, {"kind": "pick", "target": list(cell)}, {"kind": "eat", "item": HERB}]


# take_herb -------------------------------------------------------------------------------------

def take_herb_due(s: Situation) -> bool:
    return sickness(s.state) is not None and s.inventory.get(HERB, 0) > 0 and knows(s, "sunleaf")


register_reflex(Reflex("take_herb", 45, trigger=take_herb_due, plan=lambda s, context: [{"kind": "eat", "item": HERB}],
                       thought="Sunleaf. That will help.", event="{name} ate some sunleaf to feel better.",
                       cooldown=5.0))


# find_herb -------------------------------------------------------------------------------------

def find_herb_valid(s: Situation) -> bool:
    return (sickness(s.state) is not None and s.inventory.get(HERB, 0) < 1 and knows(s, "sunleaf")
            and bool(herbs_near(s, HERB_RANGE)))


def plan_find_herb(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0 or not find_herb_valid(s):
        return []
    return pick_and_eat(s, herbs_near(s, HERB_RANGE)[0])


register(Purpose(
    "find_herb", "find sunleaf", "Sick: go and eat the sunleaf nearby, which ends a sickness.",
    valid=find_herb_valid,
    facts=lambda s: f"sick; sunleaf {round(s.distance(herbs_near(s, HERB_RANGE)[0]))} blocks away",
    score=lambda s: 75.0, plan=plan_find_herb,
    thoughts=("Sunleaf will make me feel better.", "I know what helps: sunleaf.")))


# gather_herbs ----------------------------------------------------------------------------------

def gather_valid(s: Situation) -> bool:
    return (not s.night and is_wild(s.state) and s.inventory.get(HERB, 0) < HERBS_CARRIED and knows(s, "sunleaf")
            and bool(herbs_near(s, FOOD_SIGHT)))


def plan_gather(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0 or not gather_valid(s):
        return []
    steps: list[dict] = []
    where = s.here
    for cell in herbs_near(s, FOOD_SIGHT)[:HERBS_CARRIED - s.inventory.get(HERB, 0)]:
        if math.dist(where, cell) > STAND:
            steps.append(whole_walk(cell, STAND))
            where = cell
        steps.append({"kind": "pick", "target": list(cell)})
    return steps


add_urge("gather_herbs", gather_valid)
register(Purpose(
    "gather_herbs", "gather sunleaf", "Pick a little sunleaf to carry, for when sickness comes.",
    valid=gather_valid, facts=lambda s: f"carrying {s.count(HERB)} sunleaf; some grows nearby",
    score=lambda s: 52.0, plan=plan_gather,
    thoughts=("A little sunleaf, just in case.", "Sunleaf is good to have on hand.")))


# nibble ----------------------------------------------------------------------------------------

def nibble_valid(s: Situation) -> bool:
    found = sickness(s.state)
    return (found is not None and bool(found.get("nibble")) and not knows(s, "sunleaf")
            and bool(herbs_near(s, NIBBLE_RANGE)))


def plan_nibble(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0 or not nibble_valid(s):
        return []
    return pick_and_eat(s, herbs_near(s, NIBBLE_RANGE)[0])


register(Purpose(
    "nibble", "nibble a plant", "Sick, and something green nearby smells right: go and nibble it.",
    valid=nibble_valid, facts=lambda s: "sick; a little yellow plant nearby smells right",
    score=lambda s: 70.0, plan=plan_nibble,
    thoughts=("That little yellow plant smells good somehow.", "Maybe a nibble of that will help.")))
```

In `backend/survival/snapshot.py`, replace:

```python
from backend.survival.actions import PATH_WINDOW
```

with:

```python
from backend.survival.actions import PATH_WINDOW
from backend.survival.ailments import ailments_view
```

and replace:

```python
        "survival": survival,
```

with:

```python
        "survival": survival,
        "ailments": ailments_view(state),
```

In `backend/survival/steps.py`, replace:

```python
MINED: list = []
```

with:

```python
MINED: list = []
# W1: herbs Mimo eats as medicine, not as food (a sunleaf ends a sickness: backend.survival.ailments).
HERBS = ("sunleaf",)
# W1: functions (step, state, at) that eat a finished eat step their own way and return its event (kind, text),
# or None to leave it to the next and then to the rules below (a sunleaf's cure, backend.survival.ailments; a
# wild pet's meals, backend.survival.meals). One that crashes is logged once and passed over.
EATING: list = []
```

and replace:

```python
    if item not in FOOD:
```

with:

```python
    if item not in FOOD and item not in HERBS:
```

and replace:

```python
def finish_eat(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
```

with:

```python
def finish_eat(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    for eats in EATING:  # W1
        try:
            event = eats(step, state, at)
        except Exception as error:
            log_once(logger, "eating", error)
            continue
        if event is not None:
            return event
```

In `backend/survival/tick.py`, replace:

```python
W1 becomes gentle, and a gentle pet is granted the survival lessons it knows from the start.
```

with:

```python
W1 becomes gentle, and a gentle pet is granted the survival lessons it knows from the start. Each vitals
step takes a wild pet's ailments into account (backend.survival.ailments: `ailing` before, `tend` after).
```

and replace:

```python
from backend.services.worldgen import biome_at
```

with:

```python
from backend.services.worldgen import biome_at
from backend.survival import ailments
```

and replace:

```python
CAUSE_TEXT = {"starvation": "starvation", "cold": "the cold", "drowning": "drowning", "fall": "a fall"}
```

with:

```python
CAUSE_TEXT = {"starvation": "starvation", "cold": "the cold", "drowning": "drowning", "fall": "a fall"}
CAUSE_WORDS = {"sickness": "fell sick and never got better"}  # W1
```

and replace:

```python
    """How a death reads: "died of the cold", or, for a creature's kind (L2), "was caught by a gloomling"."""
```

with:

```python
    """How a death reads: "died of the cold", or, for a creature's kind (L2), "was caught by a gloomling"."""
    if cause in CAUSE_WORDS:
        return CAUSE_WORDS[cause]
```

and replace:

```python
            state["vitals"], cause = step_vitals(
                before, step, night=night, activity=activity_of(state), surroundings=surroundings,
                lonely=(cursor - last_hello) * scale > DAY_SECONDS)
```

with:

```python
            activity = activity_of(state)
            state["vitals"], cause = step_vitals(
                before, step, night=night, activity=activity, surroundings=surroundings,
                lonely=(cursor - last_hello) * scale > DAY_SECONDS, ailing=ailments.ailing(state))
```

and replace:

```python
            note_crossings(state, before, cursor, events)
```

with:

```python
            note_crossings(state, before, cursor, events)
            ailments.tend(state, step, activity, cursor, events)  # W1: a sickness runs its time
```

In `backend/survival/vitals.py`, replace:

```python
start of the step.
```

with:

```python
start of the step.

W1: a wild pet's ailments (backend.survival.ailments) change a step through `Ailing`: a sickness or a
festering wound drains health (the cause "sickness" when it is the largest damage of the killing step),
no health regenerates while Mimo is sick or wounded, a tummy ache drains hunger and a chill energy half
again as fast, and mood's target falls.
```

and replace:

```python
CAUSE_ORDER = ("drowning", "cold", "starvation")
```

with:

```python
CAUSE_ORDER = ("drowning", "cold", "starvation", "sickness")  # W1: sickness
```

and replace:

```python
    head_in_water: bool = False
```

with:

```python
    head_in_water: bool = False


@dataclass(frozen=True)
class Ailing:
    """W1: what Mimo's ailments do to its vitals this step (backend.survival.ailments.ailing)."""

    drain: float = 0.0  # health a game second a sickness or festering wound takes (cause "sickness")
    hunger: float = 1.0  # hunger drains this many times as fast (a tummy ache)
    energy: float = 1.0  # energy drains this many times as fast while awake (a chill)
    heals: bool = True  # whether health regenerates at all (not while sick or wounded)
    mood: float = 0.0  # how far mood's target falls
```

and replace:

```python
def mood_target(vitals: dict, lonely: bool) -> float:
    """Where mood drifts: up when fed and warm, down when starving, freezing, hurt or alone."""
```

with:

```python
def mood_target(vitals: dict, lonely: bool, ailing: float = 0.0) -> float:
    """Where mood drifts: up when fed and warm, down when starving, freezing, hurt or alone; W1: `ailing`
    lower while Mimo is sick or its wound festers."""
```

and replace:

```python
    return clamp(target)
```

with:

```python
    return clamp(target - ailing)
```

and replace:

```python
                surroundings: Surroundings, lonely: bool = False) -> tuple[dict, str | None]:
    """Advance vitals by `seconds` game seconds. Returns the new vitals and a cause of death, if any."""
```

with:

```python
                surroundings: Surroundings, lonely: bool = False, ailing: Ailing | None = None) -> tuple[dict, str | None]:
    """Advance vitals by `seconds` game seconds. Returns the new vitals and a cause of death, if any."""
    ailing = ailing or Ailing()
```

and replace:

```python
    }
    hurt = any(amount > 0 for amount in damage.values())
    healing = HEAL_RATE * seconds if vitals["hunger"] > 60 and vitals["warmth"] > 50 and not hurt else 0.0
```

with:

```python
        "sickness": ailing.drain * seconds,
    }
    hurt = any(amount > 0 for amount in damage.values())
    fed_and_warm = vitals["hunger"] > 60 and vitals["warmth"] > 50
    healing = HEAL_RATE * seconds if fed_and_warm and not hurt and ailing.heals else 0.0
```

and replace:

```python
        energy_change = -(ENERGY_WORK if working else ENERGY_IDLE) * seconds
    hunger_rate = HUNGER_IDLE * (WORK_HUNGER_MULTIPLIER if working else 1.0)
```

with:

```python
        energy_change = -(ENERGY_WORK if working else ENERGY_IDLE) * ailing.energy * seconds
    hunger_rate = HUNGER_IDLE * (WORK_HUNGER_MULTIPLIER if working else 1.0) * ailing.hunger
```

and replace:

```python
        "mood": clamp(approach(vitals["mood"], mood_target(vitals, lonely), MOOD_RATE * seconds)),
```

with:

```python
        "mood": clamp(approach(vitals["mood"], mood_target(vitals, lonely, ailing.mood), MOOD_RATE * seconds)),
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_ailments.py"`
Expected: `Ran 11 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1868 tests` … `OK (skipped=5)` (11 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/ailments.py backend/survival/brain.py backend/survival/herbs.py backend/survival/snapshot.py backend/survival/steps.py backend/survival/tick.py backend/survival/vitals.py backend/tests/test_survival_ailments.py backend/tests/test_survival_reflexes.py
git commit -m "feat(W1): a wild pet can fall sick, a tummy ache or a chill, and a sunleaf eaten makes it better" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: What a wild pet eats: untried foods, the lookalike, poison and raw meals

**Files:**
- Create: `backend/survival/meals.py`
- Modify: `backend/survival/wild.py` (`FAMILIAR`, `RED_BERRIES`, `NIGHTBERRIES`, `SAFE`, `SHUN`, `shunned`, `avoided`, `poisons_known`), `backend/survival/purposes.py` (`MEALS`, `meal_of`), `backend/survival/reflexes.py` (eat_now), `backend/survival/situation.py` (`poisons`), `backend/survival/senses.py` (`PICKABLE`), `backend/survival/steps.py` (the nightberries' food, the eat step's risk), `backend/survival/learning.py`, `backend/survival/exploring.py`, `backend/survival/carrying.py`, `backend/survival/brain.py` (imports `meals`)
- Test: `backend/tests/test_survival_meals.py`

**Interfaces:**
- Consumes: Task 5's `fall_sick`, `EATING`, `HERBS`; `purposes.meal`, `FULL`; `reflexes.EAT_NOW_BELOW`; `learning`'s patches, `exploring`'s finds, `carrying.eat_what_is_left`.
- Produces:
  - `purposes.MEALS: list` of `(s, full) -> steps | None`; `purposes.meal_of(s, full=FULL)`, used by the eat purpose and the eat_now reflex.
  - `meals.wild_meal`, `eat_wild`, `HOLDS: list` of `(s, item) -> bool`, `RAW_RISK`, `TASTE_BELOW = 50`, `POISON_HEALTH = 5`, the purpose `throw_out` (58, a need); channels 201 (raw) and 203 (share).
  - `wild.avoided(state, lessons, at, scale)`, `poisons_known(db, state, at, scale)`; `Situation.poisons` holds them.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_meals.py`:

```python
"""W1: what a wild pet eats: untried foods, the red berries it cannot tell apart, poison and raw meals."""

import unittest
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose registered)
from backend.survival.ailments import sickness
from backend.survival.carrying import eat_what_is_left
from backend.survival.meals import wild_meal
from backend.survival.memory import know
from backend.survival.purposes import PURPOSES, is_valid, meal_of
from backend.survival.reflexes import by_name
from backend.survival.senses import food_near
from backend.survival.steps import finish_step, start_step
from backend.survival.wild import SHUN, thing
from backend.tests.test_survival_cooking import meadow, situation

WILD = {"difficulty": "wild"}


def wild(inventory, hunger=100.0, *lessons, grid=None):
    s = situation(dict(inventory), grid, hunger)
    s.state.update(WILD)
    for name in lessons:
        know(s.db, thing(name), "lesson", 0.0)
    return s


def eat(s, item, **step):
    running = start_step({"kind": "eat", "item": item, **step}, s.state, s.grid, 0.0)
    return finish_step(running, s.state, s.grid, 1.6)  # the running step carries the meal's risk


def items(steps):
    return [step["item"] for step in steps]


class UntriedTests(unittest.TestCase):
    def test_red_berries_are_tasted_one_at_a_time_only_when_hungry_with_nothing_else(self):
        self.assertEqual(wild_meal(wild({"berries": 6}, 60.0)), [])
        self.assertEqual(items(wild_meal(wild({"berries": 6}, 45.0))), ["berries"])
        self.assertEqual(items(wild_meal(wild({"berries": 6, "raw_beef": 1}, 45.0))), ["raw_beef"])
        self.assertEqual(items(wild_meal(wild({"red_mushroom": 2}, 45.0))), ["red_mushroom"])

    def test_starving_it_tastes_at_once_through_eat_now(self):
        s = wild({"berries": 6, "raw_beef": 1}, 10.0)
        eat_now = by_name("eat_now")
        self.assertTrue(eat_now.trigger(s))
        self.assertEqual(items(eat_now.plan(s, None)), ["raw_beef", "berries"])

    def test_once_it_knows_berries_it_eats_them_and_eat_is_on_offer(self):
        self.assertFalse(is_valid(PURPOSES["eat"], wild({"berries": 6}, 60.0)))
        s = wild({"berries": 6}, 60.0, "berries")
        self.assertTrue(is_valid(PURPOSES["eat"], s))
        self.assertEqual(items(meal_of(s)), ["berries"] * 4)

    def test_sunleaf_is_never_a_meal(self):
        self.assertEqual(wild_meal(wild({"sunleaf": 2}, 10.0, "sunleaf")), [])


class LookalikeTests(unittest.TestCase):
    def test_an_untaught_meal_of_red_berries_eats_nightberries_at_their_share(self):
        eaten = []
        for at in range(200):
            s = wild({"berries": 30, "nightberries": 20}, 20.0, "berries")
            s.at = float(at * 97)
            eaten += items(wild_meal(s))
        share = eaten.count("nightberries") / len(eaten)
        self.assertTrue(0.3 < share < 0.5, share)

    def test_a_taught_pet_never_picks_eats_or_keeps_a_nightberry(self):
        grid = meadow({(2, 1, 0): "nightberry_bush_ripe", (3, 1, 0): "berry_bush_ripe"})
        untaught = wild({}, 60.0, grid=grid)
        self.assertEqual(food_near(grid, "1", (0, 1, 0), 8, untaught.poisons), [(2, 1, 0), (3, 1, 0)])
        taught = wild({"nightberries": 3, "berries": 3}, 60.0, "berries", "nightberries", grid=grid)
        self.assertEqual(food_near(grid, "1", (0, 1, 0), 8, taught.poisons), [(3, 1, 0)])
        self.assertEqual(items(meal_of(taught)), ["berries"] * 3)
        self.assertTrue(is_valid(PURPOSES["throw_out"], taught))
        self.assertEqual(PURPOSES["throw_out"].plan(taught, None), [{"kind": "drop", "item": "nightberries", "amount": 3}])

    def test_a_sickness_from_the_group_ends_the_meal_and_shuns_it_two_game_days(self):
        s = wild({"nightberries": 3, "berries": 1, "apple": 1}, 60.0, "berries")
        s.state["queue"] = [{"kind": "eat", "item": "berries"}, {"kind": "eat", "item": "nightberries"},
                            {"kind": "eat", "item": "apple"}]
        self.assertEqual(eat(s, "nightberries")[0], "sick")
        self.assertEqual(s.state["queue"], [{"kind": "eat", "item": "apple"}])  # the rest of the berries left uneaten
        self.assertEqual(s.state["last_thought"], "Berries made me sick. I'll leave them alone for a while.")
        later = wild({"berries": 3}, 60.0, "berries")
        later.state["wild"] = s.state["wild"]
        later.at = 1.0
        self.assertIn("berry_bush_ripe", later.poisons)
        self.assertEqual(meal_of(later), [])
        after = wild({"berries": 3}, 60.0, "berries")
        after.state["wild"] = s.state["wild"]
        after.at = SHUN + 2.0
        self.assertNotIn("berry_bush_ripe", after.poisons)


class EatingTests(unittest.TestCase):
    def test_a_poison_plant_takes_five_health_and_gives_a_tummy_ache(self):
        for item in ("nightberries", "red_mushroom"):
            s = wild({item: 1})
            self.assertEqual(eat(s, item), ("sick", f"Pip ate {item.replace('_', ' ')} and felt sick."))
            self.assertEqual((s.state["vitals"]["health"], sickness(s.state)["kind"]), (95.0, "tummy"))
            self.assertEqual(s.state["wild"]["lost"], 5.0)

    def test_a_raw_meal_rolls_once_at_the_highest_chance_of_its_raw_items(self):
        steps = wild_meal(wild({"raw_chicken": 1, "raw_fish": 2, "raw_beef": 1}, 20.0))
        self.assertEqual([step.get("risk") for step in steps], [0.5, None, None, None])
        s = wild({"raw_chicken": 1})
        with patch("backend.survival.meals.roll", return_value=0.45):
            self.assertEqual(eat(s, "raw_chicken", risk=0.5)[0], "sick")
        s = wild({"raw_chicken": 1})
        with patch("backend.survival.meals.roll", return_value=0.55):
            self.assertEqual(eat(s, "raw_chicken", risk=0.5)[0], "ate")
        self.assertIsNone(sickness(s.state))

    def test_a_pet_that_knows_cooking_eats_raw_food_only_when_starving(self):
        self.assertEqual(wild_meal(wild({"raw_beef": 2}, 40.0, "cooking")), [])
        self.assertEqual(items(wild_meal(wild({"raw_beef": 2}, 10.0, "cooking"))), ["raw_beef", "raw_beef"])

    def test_food_left_over_is_eaten_only_when_it_carries_no_risk_or_mimo_is_starving(self):
        state = {"name": "Pip", "vitals": {"hunger": 20.0}, **WILD}
        left = {"raw_beef": 2, "bread": 1}
        eat_what_is_left(state, left, 0.0, [])
        self.assertEqual(left, {"raw_beef": 2})
        # starving with full arms, the meat it hunts and cannot carry is eaten raw, and may make it sick
        starving = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                    "vitals": {"hunger": 5.0, "health": 100.0}, **WILD}
        left, events = {"raw_mutton": 3}, []
        with patch("backend.survival.meals.roll", return_value=0.3):
            eat_what_is_left(starving, left, 0.0, events)
        self.assertEqual((starving["vitals"]["hunger"], left), (29.0, {}))
        self.assertEqual(events, [(0.0, "ate", "Pip ate 3 raw mutton it had no room to carry."),
                                  (0.0, "sick", "Pip ate raw mutton and felt sick.")])
        self.assertEqual(sickness(starving)["kind"], "tummy")


class GentleTests(unittest.TestCase):
    def test_a_gentle_pet_eats_as_ever_and_only_avoids_nightberries(self):
        s = situation({"berries": 3, "red_mushroom": 2}, None, 40.0)
        self.assertIsNone(wild_meal(s))
        self.assertEqual(items(meal_of(s)), ["berries", "berries", "berries", "red_mushroom"])
        self.assertEqual(s.poisons, ("nightberries", "nightberry_bush_ripe"))
        s.state["inventory"] = {"red_mushroom": 1}
        self.assertEqual(eat(s, "red_mushroom"), ("sick", "Pip ate red mushroom and felt sick."))
        self.assertEqual(s.state["vitals"]["health"], 90.0)  # today's rule
        self.assertIsNone(sickness(s.state))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_meals.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.meals'`

- [ ] **Step 3: Meals, eating and throwing out**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import herbs  # noqa: F401  (W1: sunleaf: take_herb, find_herb, gather_herbs, nibble)
```

with:

```python
from backend.survival import herbs, meals  # noqa: F401  (W1: sunleaf; a wild pet's meals and throw_out)
```

In `backend/survival/carrying.py`, replace:

```python

    vitals = state["vitals"]
```

with:

```python

    from backend.survival.meals import STARVING, eat_raw_left  # W1: a wild pet eats only what carries no risk
    from backend.survival.wild import SAFE, is_wild  # at all, unless it is starving

    vitals = state["vitals"]
```

and replace:

```python
    for item in sorted((item for item in left if keeps_alive(item)), key=lambda item: (-FOOD[item], item)):
```

with:

```python
    wild = is_wild(state)
    starving = vitals["hunger"] < STARVING
    for item in sorted((item for item in left if keeps_alive(item) and (not wild or item in SAFE or starving)),
                       key=lambda item: (-FOOD[item], item)):
```

and replace:

```python
            events.append((at, "ate", f"{state['name']} ate {eaten} {label(item)} it had no room to carry."))
```

with:

```python
            events.append((at, "ate", f"{state['name']} ate {eaten} {label(item)} it had no room to carry."))
        sick = eat_raw_left(state, item, at) if eaten and wild and item not in SAFE else None
        if sick and events is not None:
            events.append((at, *sick))
```

In `backend/survival/exploring.py`, replace:

```python
    PATCH, explored, known, mark_explored, nearest, patch_of, places, remember, update_place,
```

with:

```python
    PATCH, explored, mark_explored, nearest, patch_of, places, remember, update_place,
```

and replace:

```python
from backend.survival.triggers import ensure_brain
```

with:

```python
from backend.survival.triggers import ensure_brain
from backend.survival.wild import poisons_known
```

and replace:

```python
FOOD_WORDS = {"berry_bush_ripe": "berries", "brown_mushroom": "mushrooms", "red_mushroom": "mushrooms"}
```

with:

```python
FOOD_WORDS = {"berry_bush_ripe": "berries", "brown_mushroom": "mushrooms", "red_mushroom": "mushrooms",
              "nightberry_bush_ripe": "berries"}  # W1: red berries, to a pet that cannot tell them apart
```

and replace:

```python
    poisons = known(db, "poisonous")
```

with:

```python
    poisons = poisons_known(db, state, at, context.clock_at(at)["time_scale"])  # W1
```

In `backend/survival/learning.py`, replace:

```python
from backend.survival.memory import cell_of, forget, know, known, nearest, places, remember, update_place
from backend.survival.senses import food_near, near_failure
from backend.survival.steps import FOOD_HEALTH, as_cell
```

with:

```python
from backend.survival.memory import cell_of, forget, know, nearest, places, remember, update_place
from backend.survival.senses import food_near, near_failure
from backend.survival.steps import FOOD_HEALTH, as_cell
from backend.survival.wild import is_wild, poisons_known
```

and replace:

```python
def note_food_patch(db, grid, state: dict, picked, at: float) -> None:
```

with:

```python
def note_food_patch(db, grid, state: dict, picked, at: float, scale: float = 1.0) -> None:
```

and replace:

```python
    ripe = food_near(grid, state["world_seed"], spot, PATCH_REACH, known(db, "poisonous"))
```

with:

```python
    ripe = food_near(grid, state["world_seed"], spot, PATCH_REACH, poisons_known(db, state, at, scale))  # W1
```

and replace:

```python
def note_empty_patches(db, grid, state: dict, at: float) -> None:
```

with:

```python
def note_empty_patches(db, grid, state: dict, at: float, scale: float = 1.0) -> None:
```

and replace:

```python
    poisons = known(db, "poisonous")
```

with:

```python
    poisons = poisons_known(db, state, at, scale)  # W1: a wild pet's too
```

and replace:

```python
    if kind == "eat" and FOOD_HEALTH.get(step["item"], 0.0) < 0:
```

with:

```python
    scale = context.clock_at(at)["time_scale"]
    if kind == "eat" and FOOD_HEALTH.get(step["item"], 0.0) < 0 and not is_wild(state):  # W1: a wild pet's knocks
```

and replace:

```python
        note_food_patch(db, context.grid, state, as_cell(step["target"]), at)
    elif kind == "walk" and step.get("purpose") == "forage":
        note_empty_patches(db, context.grid, state, at)
```

with:

```python
        note_food_patch(db, context.grid, state, as_cell(step["target"]), at, scale)
    elif kind == "walk" and step.get("purpose") == "forage":
        note_empty_patches(db, context.grid, state, at, scale)
```

Create `backend/survival/meals.py`:

```python
"""W1: what a wild pet eats, and what eating does to it ("Hazards" 1 and 2 of the Wild World spec).

A wild newborn eats its familiar foods by instinct (wild.FAMILIAR: apples, carrots, bread, brown mushrooms,
fish and meat). Red berries and red mushrooms are untried: it picks and carries them, but eats one only as a
taste, one serving a meal, when it must: hunger under TASTE_BELOW with no familiar or known-safe food carried
and nothing holding it back (HOLDS: a question it asked and is waiting on, backend.survival.questions), or at
once when starving (the eat_now reflex, under 15). Until it knows `wild:nightberries` the two red berries are
one group to it: a meal of red berries eats from what it carries in proportion to the counts, a seeded roll a
serving (`wild_meal`). Once it knows `wild:berries` it eats the group freely (nightberries too, until it learns
them apart). A pet that knows `wild:cooking` eats raw meat and fish only when starving. Sunleaf is medicine,
never a meal (backend.survival.ailments).

Eating, for a wild pet (steps.EATING: `eat_wild`):
- a nightberry or a red mushroom takes 5 health at once (never the last point) and gives a tummy ache: "Pip ate
  nightberries and felt sick.";
- a meal that holds raw food rolls once, on its first raw serving, at the highest chance among its raw items
  (RAW_RISK: raw chicken 0.5; beef, mutton and rabbit 0.35; fish 0.2): a tummy ache on a hit;
- a sickness from the red berries makes Mimo shun the whole group for wild.SHUN (2 game days): "Berries made
  me sick. I'll leave them alone for a while." (backend.survival.knocks lifts it when the sickness taught it
  the difference).
A food that made Mimo sick is not eaten again in that meal: the rest of its servings (of the whole group, for the
red berries) are dropped from the queue. The step is marked with what happened (`sick`, `raw`) for what learns
from it after (the knocks).
`throw_out` (58, a need) drops what Mimo knows is poison once it carries any.

A gentle pet keeps today's rules (purposes.meal, steps.FOOD_HEALTH and FOOD_RISK): MEALS and EATING give it
nothing, and it only ever avoids nightberries (wild.avoided).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.services.crafting import take_items
from backend.survival.ailments import fall_sick, lose
from backend.survival.goals import add_urge
from backend.survival.nature import roll
from backend.survival.once import log_once
from backend.survival.purposes import FULL, MEALS, Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import EATING, FOOD, HERBS, label
from backend.survival.wild import FAMILIAR, RED_BERRIES, RED_MUSHROOM, is_wild, knows, wild_state

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

TASTE_BELOW = 50.0  # hunger under which an untried food is tasted, when nothing else is carried
STARVING = 15.0  # reflexes.EAT_NOW_BELOW: starving, it tastes at once
POISON_HEALTH = 5.0
POISONOUS = ("nightberries", RED_MUSHROOM)  # what makes a wild pet sick for sure
RAW_RISK = {"raw_chicken": 0.5, "raw_beef": 0.35, "raw_mutton": 0.35, "raw_rabbit": 0.35, "raw_fish": 0.2}
SHARE_CHANNEL = 203  # the red berries' share roll
RAW_CHANNEL = 201  # a raw meal's roll
SHUN_WORDS = "Berries made me sick. I'll leave them alone for a while."
# W1: functions (Situation, item) that hold a taste of an untried food back (a question Mimo is waiting on:
# backend.survival.questions). One that crashes holds nothing back (logged once).
HOLDS: list = []


def pet_cell(state: dict) -> tuple[int, int, int]:
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def grouped(s: Situation) -> bool:
    """The two red berries are one food to Mimo: it does not know nightberries yet."""
    return not knows(s, "nightberries")


def untried(s: Situation, item: str) -> bool:
    """A food Mimo has to try before it trusts it."""
    if item in RED_BERRIES:
        return not knows(s, "berries")
    return item == RED_MUSHROOM and not knows(s, "red_mushroom")


def held(s: Situation, item: str) -> bool:
    """Something holds a taste of `item` back (HOLDS)."""
    for holds in HOLDS:
        try:
            if holds(s, item):
                return True
        except Exception as error:
            log_once(logger, "taste held", error)
    return False


def trusted(s: Situation, item: str) -> bool:
    """A food Mimo eats as a meal: familiar, or one it learned is safe (the red berries once it knows them)."""
    return item in FAMILIAR or (item in RED_BERRIES and not untried(s, item))


def may_taste(s: Situation, item: str, eatable: list[str]) -> bool:
    """Mimo tastes an untried food now: starving, or hungry with nothing it trusts to eat and nothing holding
    it back."""
    hunger = s.vitals["hunger"]
    if hunger < STARVING:
        return True
    return hunger < TASTE_BELOW and not any(trusted(s, food) for food in eatable) and not held(s, item)


def share(s: Situation, counts: dict[str, int], serving: int) -> str:
    """Which red berry a serving of the group is: nightberries at their share of the two (a seeded roll)."""
    total = counts.get("berries", 0) + counts.get("nightberries", 0)
    chance = counts.get("nightberries", 0) / total if total else 0.0
    picked = roll(s.seed, pet_cell(s.state), SHARE_CHANNEL, int(s.at) + serving) < chance
    return "nightberries" if picked else "berries"


def wild_meal(s: Situation, full: float = FULL) -> list[dict] | None:
    """purposes.MEALS: a wild pet's meal, best first, until hunger would reach `full` (None for a gentle pet:
    purposes.meal). An untried food is a single taste, the red berries a group while Mimo cannot tell them
    apart, raw food only while Mimo does not know to cook it (or is starving); the meal's first raw serving
    carries the meal's risk."""
    if not is_wild(s.state):
        return None
    hunger = s.vitals["hunger"]
    starving = hunger < STARVING
    cooks = knows(s, "cooking") and not starving
    counts = {item: count for item, count in s.inventory.items()
              if count > 0 and item in FOOD and item not in s.poisons and item not in HERBS
              and not (cooks and item in RAW_RISK)}
    eatable = sorted(counts, key=lambda item: (untried(s, item), -FOOD[item], item))  # what it trusts first
    steps: list[dict] = []
    served = 0
    together = grouped(s) and all(item in counts for item in RED_BERRIES)
    for item in eatable:
        if together and item == "nightberries":
            continue  # eaten with the berries, as one food
        tasting = untried(s, item)
        if tasting and not may_taste(s, item, eatable):
            continue
        servings = 1 if tasting else counts[item] + (counts.get("nightberries", 0) if together and item == "berries" else 0)
        while servings > 0 and hunger < full:
            eaten = share(s, counts, served) if together and item == "berries" else item
            counts[eaten] -= 1
            steps.append({"kind": "eat", "item": eaten})
            servings -= 1
            served += 1
            hunger += FOOD[eaten]
    risk = max((RAW_RISK[step["item"]] for step in steps if step["item"] in RAW_RISK), default=0.0)
    first_raw = next((step for step in steps if step["item"] in RAW_RISK), None)
    if first_raw is not None:
        first_raw["risk"] = risk
    return steps


MEALS.append(wild_meal)


# Eating ------------------------------------------------------------------------------------------

def eat_raw_left(state: dict, item: str, at: float) -> tuple[str, str] | None:
    """carrying.eat_what_is_left: a starving wild pet ate raw food it had no room to carry, on the spot. The raw
    meal's roll, once (RAW_RISK, RAW_CHANNEL); the sickness's event, or None."""
    if roll(state.get("world_seed", "0"), pet_cell(state), RAW_CHANNEL, int(at)) < RAW_RISK.get(item, 0.0):
        return sick_from(state, item, at)
    return None


def sick_from(state: dict, item: str, at: float) -> tuple[str, str]:
    """Mimo ate `item` and it made it sick: a tummy ache, the rest of that food left uneaten this meal, and the red
    berries shunned for a while."""
    fall_sick(state, "tummy", at)
    same = RED_BERRIES if item in RED_BERRIES else (item,)
    if state.get("queue"):
        state["queue"] = [spec for spec in state["queue"] if not (spec.get("kind") == "eat" and spec.get("item") in same)]
    if item in RED_BERRIES:
        wild_state(state)["shun"]["red_berries"] = at
        state["last_thought"] = SHUN_WORDS
    return "sick", f"{state['name']} ate {label(item)} and felt sick."


def eat_wild(step: dict, state: dict, at: float) -> tuple[str, str] | None:
    """steps.EATING: a wild pet's eat step (None for a gentle pet's and for an herb's)."""
    item = step["item"]
    if not is_wild(state) or item in HERBS or item not in FOOD:
        return None
    vitals = state["vitals"]
    state["inventory"] = take_items(state["inventory"], {item: 1})
    vitals["hunger"] = min(100.0, vitals["hunger"] + FOOD[item])
    if item in POISONOUS:
        before = vitals["health"]
        vitals["health"] = max(min(before, 1.0), before - POISON_HEALTH)
        lose(state, before - vitals["health"])  # lost to a hazard (backend.survival.ailments)
        step["sick"] = True
        return sick_from(state, item, at)
    risk = float(step.get("risk", 0.0))
    if risk > 0:
        step["raw"] = True
        if roll(state.get("world_seed", "0"), pet_cell(state), RAW_CHANNEL, int(at)) < risk:
            step["sick"] = True
            return sick_from(state, item, at)
    return "ate", f"{state['name']} ate {label(item)}."


EATING.append(eat_wild)


# throw_out ---------------------------------------------------------------------------------------

def junk_food(s: Situation) -> list[tuple[str, int]]:
    """(item, count) Mimo carries and knows it must not eat: poison it learned (nightberries, red mushrooms)."""
    return [(item, s.inventory[item]) for item, lesson in (("nightberries", "nightberries"), (RED_MUSHROOM, "red_mushroom"))
            if s.inventory.get(item, 0) > 0 and knows(s, lesson)]


def throw_out_valid(s: Situation) -> bool:
    return is_wild(s.state) and bool(junk_food(s))


def plan_throw_out(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return [{"kind": "drop", "item": item, "amount": count} for item, count in junk_food(s)]


add_urge("throw_out", throw_out_valid)
register(Purpose(
    "throw_out", "throw out what is bad", "Drop food it knows is poison, so it is never eaten by mistake.",
    valid=throw_out_valid,
    facts=lambda s: "carrying " + ", ".join(f"{count} {label(item)}" for item, count in junk_food(s)),
    score=lambda s: 58.0, plan=plan_throw_out,
    thoughts=("I'm not eating those. Out they go.", "Better get rid of the bad stuff.")))
```

In `backend/survival/purposes.py`, replace:

```python

def meal(inventory: dict, hunger: float, full: float = FULL, avoid=()) -> list[dict]:
```

with:

```python

# W1: functions (Situation, full) giving a wild pet's meal (backend.survival.meals), or None to leave it to
# `meal` (a gentle pet's, as ever). One that crashes plans no meal (logged once).
MEALS: list = []


def meal_of(s: Situation, full: float = FULL) -> list[dict]:
    """The meal Mimo would eat now, up to `full`: MEALS' first answer, else `meal` (a gentle pet's)."""
    for plans in MEALS:
        try:
            found = plans(s, full)
        except Exception as error:
            log_once(logger, "meal", error)
            return []
        if found is not None:
            return found
    return meal(s.inventory, s.vitals["hunger"], full, s.poisons)


def meal(inventory: dict, hunger: float, full: float = FULL, avoid=()) -> list[dict]:
```

and replace:

```python
    return meal(s.inventory, s.vitals["hunger"], avoid=s.poisons)
```

with:

```python
    return meal_of(s)
```

and replace:

```python
    valid=lambda s: bool(foods(s.inventory, s.poisons)) and s.vitals["hunger"] < EAT_BELOW,
```

with:

```python
    valid=lambda s: s.vitals["hunger"] < EAT_BELOW and bool(meal_of(s)),  # W1: what it would eat (meal_of)
```

In `backend/survival/reflexes.py`, replace:

```python
    AT_HOME, GO_HOME_RANGE, HOME_RANGE, away, foods, home_of, land_refuge, meal, walk_to,
```

with:

```python
    AT_HOME, GO_HOME_RANGE, HOME_RANGE, away, home_of, land_refuge, meal_of, walk_to,
```

and replace:

```python
                trigger=lambda s: s.vitals["hunger"] < EAT_NOW_BELOW and bool(foods(s.inventory, s.poisons)),
                plan=lambda s, context: meal(s.inventory, s.vitals["hunger"], EAT_NOW_FULL, s.poisons),
```

with:

```python
                trigger=lambda s: s.vitals["hunger"] < EAT_NOW_BELOW and bool(meal_of(s, EAT_NOW_FULL)),  # W1
                plan=lambda s, context: meal_of(s, EAT_NOW_FULL),
```

In `backend/survival/senses.py`, replace:

```python
PICKABLE = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")
```

with:

```python
PICKABLE = ("berry_bush_ripe", "brown_mushroom", "red_mushroom", "nightberry_bush_ripe")  # W1: nightberries
```

In `backend/survival/situation.py`, replace:

```python
from backend.survival.triggers import ensure_brain
```

with:

```python
from backend.survival.triggers import ensure_brain
from backend.survival.wild import avoided
```

and replace:

```python
        """Food Mimo learned is poisonous (it got sick eating it)."""
        return tuple(memory.known(self.db, "poisonous")) if self.db is not None else ()
```

with:

```python
        """Food Mimo learned is poisonous (it got sick eating it); W1: and what it knows to avoid (items and the
        blocks they grow on: backend.survival.wild.avoided), a gentle pet's nightberries among them."""
        learned = tuple(memory.known(self.db, "poisonous")) if self.db is not None else ()
        return tuple(dict.fromkeys((*learned, *avoided(self.state, self.lessons, self.at, self.scale))))
```

In `backend/survival/steps.py`, replace:

```python
        "cooked_beef": 35.0, "cooked_mutton": 30.0, "cooked_chicken": 25.0, "cooked_rabbit": 25.0}
# Health a food changes when eaten: a red mushroom is poisonous. Poison never takes the last point
# of health (it is not a cause of death).
FOOD_HEALTH = {"red_mushroom": -10.0}
```

with:

```python
        "cooked_beef": 35.0, "cooked_mutton": 30.0, "cooked_chicken": 25.0, "cooked_rabbit": 25.0,
        "nightberries": 8.0}  # W1: they fill like berries, and are poison
# Health a food changes when eaten: a red mushroom is poisonous. Poison never takes the last point
# of health (it is not a cause of death).
FOOD_HEALTH = {"red_mushroom": -10.0, "nightberries": -10.0}  # W1: nightberries, as a gentle pet would
```

and replace:

```python
    return {"kind": "eat", "started_at": at, "ends_at": round(at + EAT_SECONDS / scale, 3), "item": item}
```

with:

```python
    return {"kind": "eat", "started_at": at, "ends_at": round(at + EAT_SECONDS / scale, 3), "item": item,
            **({"risk": spec["risk"]} if "risk" in spec else {})}  # W1: a raw meal's risk (backend.survival.meals)
```

In `backend/survival/wild.py`, replace:

```python
FITTING_LESSONS = {"bed": "bed", "campfire": "fire", "door": "shelter"}
```

with:

```python
FITTING_LESSONS = {"bed": "bed", "campfire": "fire", "door": "shelter"}
# What a wild newborn eats by instinct (the familiar foods; raw meat and fish carry a risk until it knows
# cooking), and the foods it has to try first: the red berries (bright red berries and nightberries, one
# group to a pet that does not know nightberries yet) and red mushrooms (backend.survival.meals).
FAMILIAR = ("apple", "carrot", "bread", "brown_mushroom", "raw_fish", "cooked_fish", "raw_beef", "raw_mutton",
            "raw_chicken", "raw_rabbit", "cooked_beef", "cooked_mutton", "cooked_chicken", "cooked_rabbit")
RED_BERRIES = ("berries", "nightberries")
BERRY_BUSHES = ("berry_bush_ripe", "nightberry_bush_ripe")
NIGHTBERRIES = ("nightberries", "nightberry_bush_ripe")
RED_MUSHROOM = "red_mushroom"  # the item and the block
SAFE = tuple(item for item in FAMILIAR if not item.startswith("raw_"))  # eaten with no risk at all
SHUN = 7200.0  # game seconds (2 game days) a group that made Mimo sick is left alone
```

and replace:

```python
    lesson = FITTING_LESSONS.get(block)
    return lesson is None or unlocked(s, lesson)

```

with:

```python
    lesson = FITTING_LESSONS.get(block)
    return lesson is None or unlocked(s, lesson)


def shunned(state: dict, group: str, at: float, scale: float) -> bool:
    """Mimo leaves the food `group` alone now: it made Mimo sick less than SHUN game seconds ago."""
    since = ((state.get("wild") or {}).get("shun") or {}).get(group)
    return since is not None and (at - since) * scale < SHUN


def avoided(state: dict, lessons, at: float, scale: float) -> tuple[str, ...]:
    """The foods (items and the blocks they grow on) Mimo never picks or eats now: for a gentle pet the
    nightberries it knows from the start; for a wild one what it knows is poison (nightberries, red
    mushrooms) and a group it shuns (the red berries after they made it sick)."""
    if not is_wild(state):
        return NIGHTBERRIES
    found: list[str] = []
    if thing("nightberries") in lessons:
        found += NIGHTBERRIES
    if thing("red_mushroom") in lessons:
        found.append(RED_MUSHROOM)
    if shunned(state, "red_berries", at, scale):
        found += (*RED_BERRIES, *BERRY_BUSHES)
    return tuple(dict.fromkeys(found))


def poisons_known(db: sqlite3.Connection, state: dict, at: float, scale: float) -> tuple[str, ...]:
    """What Mimo knows is poisonous (memory's "poisonous", M4) and what it avoids (`avoided`), for code that
    reads memory without a Situation (backend.survival.learning, backend.survival.exploring)."""
    return tuple(dict.fromkeys((*known(db, "poisonous"), *avoided(state, set(known(db, LESSON)), at, scale))))

```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_meals.py"`
Expected: `Ran 12 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1880 tests` … `OK (skipped=5)` (12 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/brain.py backend/survival/carrying.py backend/survival/exploring.py backend/survival/learning.py backend/survival/meals.py backend/survival/purposes.py backend/survival/reflexes.py backend/survival/senses.py backend/survival/situation.py backend/survival/steps.py backend/survival/wild.py backend/tests/test_survival_meals.py
git commit -m "feat(W1): a wild newborn eats what it knows, tastes the rest when it must, and cannot tell nightberries from berries" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Food that spoils

**Files:**
- Create: `backend/survival/spoilage.py`
- Modify: `backend/survival/tick.py` (`spoilage.age`), `backend/survival/steps.py` (`spoiled_food`; a food gone before it is eaten fails the step), `backend/survival/purposes.py` (`foods` leaves spoiled food out), `backend/survival/meals.py` (spoiled food eaten and thrown out), `backend/survival/cooking.py` (keeping cooks what is turning), `backend/survival/storage.py` (keeping stores spare food)
- Test: `backend/tests/test_survival_spoilage.py`

**Interfaces:**
- Consumes: Task 6's meals; `steps.OBSERVERS`; `storage.spare_food`; `cooking.cook_score`; the tick's vitals step.
- Produces: `spoilage.PERISHABLE`, `LOTS = 3`, `CHEST_RATE = 0.5`, `SPOILED = "spoiled_food"`, `SPOILS: list` of `(state, context, item, count, where, at)`, `add`, `take`, `settle_lots(state)`, `observe_lots` (in `steps.OBSERVERS`), `age(state, context, seconds, at)`, `worn(state, item)`, `turning(state, items)`; `state["lots"]` and `state["chest_lots"]`; `cooking.KEEPING_LIFT = 20`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_spoilage.py`:

```python
"""W1: food that spoils, in lots that follow every move, for a wild pet only."""

import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose registered)
from backend.survival.actions import ActionContext
from backend.survival.ailments import sickness
from backend.survival.clock import DAY_SECONDS
from backend.survival.cooking import cook_score
from backend.survival.hatch import hatch
from backend.survival.meals import wild_meal
from backend.survival.memory import know
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.spoilage import age, observe_lots, settle_lots, take
from backend.survival.steps import finish_step, start_step
from backend.survival.storage import spare_food
from backend.survival.tick import tick_life
from backend.survival.wild import thing
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_cooking import meadow, situation

BORN = 1_000_000.0


def pet(inventory, **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": dict(inventory),
             "vitals": {"health": 100.0, "hunger": 100.0, "warmth": 100.0, "energy": 100.0, "air": 100.0, "mood": 70.0},
             "difficulty": "wild"}
    state.update(changes)
    return state


def context():
    return ActionContext(grid=meadow(), clock_at=lambda at: {"time_scale": 1.0}, planner=None, events=[], db=None)


def summed(state):
    """{item: (count, lots' sum)} for every perishable thing Mimo carries or its chests hold, and the chests'."""
    found = {("arms", item): (count, sum(lot[0] for lot in state.get("lots", {}).get(item, [])))
             for item, count in state["inventory"].items() if item in ("raw_beef", "berries", "cooked_beef", "bread")}
    for key, chest in state.get("chests", {}).items():
        for item, count in chest.items():
            found[(key, item)] = (count, sum(lot[0] for lot in state.get("chest_lots", {}).get(key, {}).get(item, [])))
    return found


class AgingTests(unittest.TestCase):
    def test_raw_beef_spoils_after_a_game_day_and_a_half_in_its_arms(self):
        state, where = pet({"raw_beef": 2}), context()
        age(state, where, 60.0, 0.0)
        self.assertEqual(state["lots"], {"raw_beef": [[2, round(60 / (1.5 * DAY_SECONDS), 6)]]})
        for _ in range(int(1.5 * DAY_SECONDS / 60)):
            age(state, where, 60.0, 1.0)
        self.assertEqual(state["inventory"], {"spoiled_food": 2})
        self.assertEqual(where.events[-1], (1.0, "spoiled", "Pip's raw beef went bad."))
        self.assertEqual(state["lots"], {})

    def test_food_in_a_chest_keeps_twice_as_long(self):
        state, where = pet({}, chests={"0,1,0": {"raw_beef": 1}}), context()
        for _ in range(int(1.5 * DAY_SECONDS / 60)):
            age(state, where, 60.0, 1.0)
        self.assertEqual(state["chests"]["0,1,0"], {"raw_beef": 1})
        for _ in range(int(1.5 * DAY_SECONDS / 60)):
            age(state, where, 60.0, 2.0)
        self.assertEqual(state["chests"]["0,1,0"], {"spoiled_food": 1})

    def test_a_gentle_pet_has_no_lots(self):
        state = pet({"raw_beef": 2}, difficulty="gentle")
        age(state, context(), 60.0, 0.0)
        settle_lots(state)
        self.assertNotIn("lots", state)


class LotTests(unittest.TestCase):
    def test_new_food_joins_the_newest_lot_within_a_minute_and_a_fourth_merges_into_the_oldest(self):
        state = pet({"raw_beef": 1})
        settle_lots(state)
        state["inventory"]["raw_beef"] = 3
        settle_lots(state)
        self.assertEqual(state["lots"]["raw_beef"], [[3, 0.0]])
        state["lots"]["raw_beef"] = [[1, 0.6], [1, 0.3], [1, 0.1]]
        state["inventory"]["raw_beef"] = 5
        settle_lots(state)
        self.assertEqual(state["lots"]["raw_beef"], [[3, 0.6], [1, 0.3], [1, 0.1]])
        self.assertEqual(take([[2, 0.5], [3, 0.1]], 3), ([[2, 0.1]], [[2, 0.5], [1, 0.1]]))

    def test_the_lots_follow_every_step_kind_and_always_sum_to_the_counts(self):
        s = situation({"raw_beef": 3, "berries": 2, "oak_log": 1, "sticks": 3},
                      meadow({(2, 1, 0): "berry_bush_ripe", (1, 1, 0): "chest", (0, 1, 2): "campfire"}), 60.0)
        s.state.update(difficulty="wild", chests={"1,1,0": {}})
        settle_lots(s.state)
        s.state["lots"]["raw_beef"] = [[1, 0.9], [2, 0.1]]
        steps = [{"kind": "eat", "item": "raw_beef"}, {"kind": "pick", "target": [2, 1, 0]},
                 {"kind": "store", "target": [1, 1, 0], "item": "raw_beef", "amount": 1},
                 {"kind": "take", "target": [1, 1, 0], "item": "raw_beef", "amount": 1},
                 {"kind": "drop", "item": "berries", "amount": 1}, {"kind": "craft", "recipe": "planks"},
                 {"kind": "cook", "item": "raw_beef"}]
        for spec in steps:
            running = start_step(spec, s.state, s.grid, 0.0)
            finish_step(running, s.state, s.grid, 1.0)
            observe_lots(s.state, running, None, 1.0)
            for where, (count, lots) in summed(s.state).items():
                self.assertEqual(count, lots, (spec["kind"], where))
        self.assertEqual(s.state["lots"]["raw_beef"], [[1, 0.1]])  # the worn one went first, into the chest and back
        self.assertEqual(s.state["lots"]["cooked_beef"], [[1, 0.0]])


class KeepingTests(unittest.TestCase):
    def test_spoiled_food_is_eaten_only_when_hungry_with_nothing_else_and_can_make_mimo_sick(self):
        self.assertEqual(wild_meal(self.wild({"spoiled_food": 2}, 60.0)), [])
        self.assertEqual(wild_meal(self.wild({"spoiled_food": 2, "bread": 1}, 40.0))[0]["item"], "bread")
        s = self.wild({"spoiled_food": 1}, 40.0)
        self.assertEqual([step["item"] for step in wild_meal(s)], ["spoiled_food"])
        with patch("backend.survival.meals.roll", return_value=0.5):
            running = start_step({"kind": "eat", "item": "spoiled_food"}, s.state, s.grid, 0.0)
            self.assertEqual(finish_step(running, s.state, s.grid, 1.0)[0], "sick")
        self.assertEqual((s.vitals["hunger"], sickness(s.state)["kind"]), (44.0, "tummy"))

    def test_keeping_throws_spoiled_food_out_cooks_before_it_turns_and_stores_spare_food(self):
        s = self.wild({"spoiled_food": 2, "raw_beef": 1, "bread": 6}, 90.0, "keeping")
        self.assertEqual(wild_meal(s), [])
        self.assertEqual(PURPOSES["throw_out"].plan(s, None), [{"kind": "drop", "item": "spoiled_food", "amount": 2}])
        before = cook_score(s)
        s.state["lots"] = {"raw_beef": [[1, 0.6]]}
        self.assertEqual(cook_score(s), min(80.0, before + 20.0))
        self.assertEqual(spare_food(s), [("bread", 3)])  # three loaves are a game day's worth
        self.assertEqual(spare_food(self.wild({"bread": 6}, 90.0)), [])  # untaught: it keeps it all on it

    def wild(self, inventory, hunger, *lessons):
        s = situation(inventory, None, hunger)
        s.state["difficulty"] = "wild"
        for name in lessons:
            know(s.db, thing(name), "lesson", 0.0)
        return s


    def test_food_that_spoils_while_it_is_eaten_fails_the_step_and_logs_nothing(self):
        state = pet({"berries": 1}, vitals={**pet({})["vitals"], "hunger": 40.0})
        running = start_step({"kind": "eat", "item": "berries"}, state, meadow(), 0.0)
        state["inventory"] = {"spoiled_food": 1}  # the berries went bad while it ate
        with self.assertNoLogs("backend", level="WARNING"), self.assertRaises(ValueError):
            finish_step(running, state, meadow(), 1.6)


class TickTests(unittest.TestCase):
    def test_the_tick_ages_a_wild_pets_food(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                state["inventory"] = {"raw_beef": 1}
                write_state(db, state)
            tick_life(registry, BORN + 1.6 * DAY_SECONDS / 60, scale=60.0)
            events = [event["text"] for event in world.events(500) if event["kind"] == "spoiled"]
        self.assertTrue(events, "the beef never went bad")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_spoilage.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.spoilage'`

- [ ] **Step 3: Lots, aging and keeping**

In `backend/survival/cooking.py`, replace:

```python
from backend.survival.wild import unlocked
```

with:

```python
from backend.survival.spoilage import turning
from backend.survival.wild import knows, unlocked
```

and replace:

```python
def cook_score(s: Situation) -> float:
    servings = s.count(*RAW_FOODS) + s.count("wheat") // BREAD_WHEAT
    return min(80.0, 50.0 + (100.0 - s.vitals["hunger"]) / 4 + 5.0 * servings)
```

with:

```python
KEEPING_LIFT = 20.0  # W1: a pet that knows keeping cooks raw food before it turns


def cook_score(s: Situation) -> float:
    servings = s.count(*RAW_FOODS) + s.count("wheat") // BREAD_WHEAT
    lift = KEEPING_LIFT if knows(s, "keeping") and turning(s.state, RAW_FOODS) else 0.0
    return min(80.0, 50.0 + (100.0 - s.vitals["hunger"]) / 4 + 5.0 * servings + lift)
```

In `backend/survival/meals.py`, replace:

```python
  the difference).
```

with:

```python
  the difference);
- spoiled food (backend.survival.spoilage) fills 4 hunger and gives a tummy ache with chance SPOILED_RISK, and
  is eaten only when hungry with nothing else to eat, by a pet that does not know `wild:keeping`.
```

and replace:

```python
`throw_out` (58, a need) drops what Mimo knows is poison once it carries any.
```

with:

```python
`throw_out` (58, a need) drops what Mimo knows is poison once it carries any, and spoiled food once it knows
`wild:keeping`.
```

and replace:

```python
from backend.survival.situation import Situation
```

with:

```python
from backend.survival.situation import Situation
from backend.survival.spoilage import SPOILED
```

and replace:

```python
RAW_CHANNEL = 201  # a raw meal's roll
```

with:

```python
RAW_CHANNEL = 201  # a raw meal's roll
SPOILED_CHANNEL = 202
SPOILED_RISK = 0.6
```

and replace:

```python
              if count > 0 and item in FOOD and item not in s.poisons and item not in HERBS
              and not (cooks and item in RAW_RISK)}
```

with:

```python
              if count > 0 and item in FOOD and item not in s.poisons and item not in HERBS and item != SPOILED
              and not (cooks and item in RAW_RISK)}
    if not counts and s.inventory.get(SPOILED, 0) > 0 and hunger < TASTE_BELOW and not knows(s, "keeping"):
        counts = {SPOILED: s.inventory[SPOILED]}  # nothing else left: what went bad
```

and replace:

```python
        return sick_from(state, item, at)
    risk = float(step.get("risk", 0.0))
```

with:

```python
        return sick_from(state, item, at)
    if item == SPOILED:
        if roll(state.get("world_seed", "0"), pet_cell(state), SPOILED_CHANNEL, int(at)) < SPOILED_RISK:
            step["sick"] = True
            return sick_from(state, item, at)
        return "ate", f"{state['name']} ate {label(item)}."
    risk = float(step.get("risk", 0.0))
```

and replace:

```python
    """(item, count) Mimo carries and knows it must not eat: poison it learned (nightberries, red mushrooms)."""
    return [(item, s.inventory[item]) for item, lesson in (("nightberries", "nightberries"), (RED_MUSHROOM, "red_mushroom"))
            if s.inventory.get(item, 0) > 0 and knows(s, lesson)]
```

with:

```python
    """(item, count) Mimo carries and knows it must not eat: poison it learned (nightberries, red mushrooms), and
    food that went bad once it knows keeping."""
    known = (("nightberries", "nightberries"), (RED_MUSHROOM, "red_mushroom"), (SPOILED, "keeping"))
    return [(item, s.inventory[item]) for item, lesson in known if s.inventory.get(item, 0) > 0 and knows(s, lesson)]
```

In `backend/survival/purposes.py`, replace:

```python
    """Food Mimo carries, best first, leaving out what it knows is poisonous (`avoid`)."""
    return sorted((item for item in FOOD if inventory.get(item, 0) > 0 and item not in avoid),
```

with:

```python
    """Food Mimo carries, best first, leaving out what it knows is poisonous (`avoid`); W1: and food that went
    bad, which is no meal to count on (backend.survival.meals eats it only when nothing else is left)."""
    return sorted((item for item in FOOD if inventory.get(item, 0) > 0 and item not in avoid and item != "spoiled_food"),
```

Create `backend/survival/spoilage.py`:

```python
"""W1: food that spoils ("Hazards" 3 of the Wild World spec), for a wild pet only.

Perishable food ages: PERISHABLE gives its shelf life in Mimo's arms, in game days (raw meat and fish 1.5;
berries, nightberries and brown mushrooms 2; cooked meat and fish 4; apples and carrots 5; bread 6). In a
chest it ages half as fast. Sunleaf, seeds and wheat never spoil (nor does anything not listed).

Each perishable item keeps at most LOTS lots, [count, wear], with wear from 0 to 1 (the share of its shelf
life used): `state["lots"]` for Mimo's arms, and `state["chest_lots"]` ({chest key: {item: lots}}) beside the
contents in `state["chests"]` (a key inside a chest's own dict would read as an item there). Food added within
a game minute of the newest lot (its wear no more than a minute's) joins it; a fourth lot merges into the
oldest. Eating, dropping, crafting and cooking take the most worn food first, and so do storing and taking,
which carry their lots across (`observe_lots`, after each finished step: steps.OBSERVERS). The lots of an item
always add up to its count: `settle_lots`, after each vitals step and each finished step, repairs any gap
toward the count (new food is fresh, food gone takes the most worn first), so a path that moves food without
a step (the owner's help, what a full pair of arms leaves behind) never leaves them out of step.

The tick ages Mimo's lots every vitals step and its chests' once a game minute (`age`). A lot that reaches
wear 1 becomes that many `spoiled_food` ("Pip's raw beef went bad.", a "spoiled" event), in its arms or its
chest; SPOILS then hears of it (backend.survival.knocks). Spoiled food fills 4 hunger and gives a tummy ache 6
times in 10 (backend.survival.meals). A pet that knows `wild:keeping` throws it out, cooks raw food before it
turns (cook scores 20 more while raw food it carries is past half its shelf life) and puts spare food in its
chest; one that does not eats spoiled food when hungry with nothing else, and keeps its spare food on it.

A gentle pet never has a lot: every function here leaves a gentle pet's state alone. A crash is logged once
and changes nothing.
"""

from __future__ import annotations

import logging

from backend.survival.clock import DAY_SECONDS
from backend.survival.once import log_once
from backend.survival.steps import OBSERVERS, label
from backend.survival.wild import is_wild

logger = logging.getLogger(__name__)

SPOILED = "spoiled_food"
PERISHABLE = {"raw_beef": 1.5, "raw_mutton": 1.5, "raw_chicken": 1.5, "raw_rabbit": 1.5, "raw_fish": 1.5,
              "berries": 2.0, "nightberries": 2.0, "brown_mushroom": 2.0,
              "cooked_beef": 4.0, "cooked_mutton": 4.0, "cooked_chicken": 4.0, "cooked_rabbit": 4.0, "cooked_fish": 4.0,
              "apple": 5.0, "carrot": 5.0, "bread": 6.0}
LOTS = 3
CHEST_RATE = 0.5  # food in a chest ages half as fast
JOIN = 60.0  # game seconds: food added within a game minute of the newest lot joins it
CHEST_EVERY = 60.0  # game seconds between two agings of the chests
TURNING = 0.5  # wear past which keeping cooks raw food first
# W1: functions (state, context, item, count, where, at) run when food spoils (backend.survival.knocks);
# `where` is "arms" or "chest". One that crashes is logged once.
SPOILS: list = []


def arms_lots(state: dict) -> dict:
    return state.setdefault("lots", {})


def chest_lots(state: dict, key: str) -> dict:
    return state.setdefault("chest_lots", {}).setdefault(key, {})


def total(lots: list) -> int:
    return sum(count for count, _ in lots)


def most_worn_first(lots: list) -> list:
    return sorted(lots, key=lambda lot: -lot[1])


def add(lots: list, count: int, wear: float, item: str) -> list:
    """`count` food of wear `wear` added to `lots`: joining the newest lot when it is no older than a game
    minute, else a lot of its own; past LOTS lots the newcomer merges into the oldest."""
    if count <= 0:
        return lots
    newest = min(lots, key=lambda lot: lot[1], default=None)
    fresh_enough = JOIN / (PERISHABLE[item] * DAY_SECONDS)
    if newest is not None and abs(newest[1] - wear) <= fresh_enough:
        newest[0] += count
        return lots
    if len(lots) >= LOTS:
        oldest = max(lots, key=lambda lot: lot[1])
        oldest[0] += count
        return lots
    return [*lots, [count, wear]]


def take(lots: list, count: int) -> tuple[list, list]:
    """Take `count` food from `lots`, the most worn first: (what is left, what was taken, as lots)."""
    left, taken = [], []
    for lot_count, wear in most_worn_first(lots):
        moved = min(count, lot_count)
        if moved:
            taken.append([moved, wear])
            count -= moved
        if lot_count - moved:
            left.append([lot_count - moved, wear])
    return left, taken


def settle(lots_of: dict, items: dict) -> bool:
    """Bring the lots of every perishable item in `items` in step with its count (fresh food for more, the
    most worn gone for less), and drop the lots of food no longer there. True when a lot changed."""
    changed = False
    for item in list(lots_of):
        if item not in PERISHABLE or items.get(item, 0) <= 0:
            del lots_of[item]
            changed = True
    for item, count in items.items():
        if item not in PERISHABLE or count <= 0:
            continue
        lots = lots_of.get(item, [])
        have = total(lots)
        if have < count:
            lots_of[item] = add([list(lot) for lot in lots], count - have, 0.0, item)
            changed = True
        elif have > count:
            lots_of[item] = take(lots, have - count)[0]
            changed = True
    return changed


def settle_lots(state: dict) -> None:
    """Every lot of a wild pet in step with the food it carries and its chests hold."""
    if not is_wild(state):
        return
    settle(arms_lots(state), state.get("inventory", {}))
    chests = state.get("chests", {})
    kept = state.setdefault("chest_lots", {})
    for key in list(kept):
        if key not in chests:
            del kept[key]
    for key, items in chests.items():
        if any(item in PERISHABLE for item in items) or key in kept:
            settle(chest_lots(state, key), items)
            if not kept.get(key):
                kept.pop(key, None)


def observe_lots(state: dict, step: dict, context, at: float) -> None:
    """steps.OBSERVERS: a store or take step carries its food's lots across, the most worn first; then every
    lot is settled. A crash is logged once."""
    if not is_wild(state):
        return
    try:
        item = step.get("item")
        if (step["kind"] in ("store", "take") and item in PERISHABLE and isinstance(step.get("target"), dict)
                and not step.get("away")):  # food taken out and left behind at once needs no lots
            target = step["target"]
            key = f"{target['x']},{target['y']},{target['z']}"
            arms, chest = arms_lots(state), chest_lots(state, key)
            carried = state["inventory"].get(item, 0)
            if step["kind"] == "store":
                moved = total(arms.get(item, [])) - carried
                source, sink = arms, chest
            else:
                moved = total(chest.get(item, [])) - state.get("chests", {}).get(key, {}).get(item, 0)
                source, sink = chest, arms
            if moved > 0:
                left, taken = take(source.get(item, []), moved)
                source[item] = left
                lots = [list(lot) for lot in sink.get(item, [])]
                for count, wear in taken:
                    lots = add(lots, count, wear, item)
                sink[item] = lots
        settle_lots(state)
    except Exception as error:
        log_once(logger, "lots", error)


OBSERVERS.append(observe_lots)


def spoil(lots_of: dict, items: dict, rate: float, seconds: float) -> dict[str, int]:
    """Age every lot by `seconds` game seconds at `rate`; each lot that reaches wear 1 turns into spoiled food
    in `items`. Returns {item: count spoiled}."""
    spoiled: dict[str, int] = {}
    for item in list(lots_of):
        shelf = PERISHABLE.get(item)
        if shelf is None:
            continue
        kept = []
        for count, wear in lots_of[item]:
            wear = wear + rate * seconds / (shelf * DAY_SECONDS)
            if wear >= 1.0:
                spoiled[item] = spoiled.get(item, 0) + count
            else:
                kept.append([count, round(wear, 6)])
        lots_of[item] = kept
        if spoiled.get(item):
            items[item] = items.get(item, 0) - spoiled[item]
            if items[item] <= 0:
                items.pop(item, None)
            items[SPOILED] = items.get(SPOILED, 0) + spoiled[item]
        if not kept:
            del lots_of[item]
    return spoiled


def went_bad(state: dict, context, spoiled: dict[str, int], where: str, at: float) -> None:
    name = state["name"]
    for item, count in spoiled.items():
        context.events.append((at, "spoiled", f"{name}'s {label(item)} went bad."))
        state["last_thought"] = f"Yuck, my {label(item)} went bad."
        for hears in SPOILS:
            try:
                hears(state, context, item, count, where, at)
            except Exception as error:
                log_once(logger, "spoils", error)


def age(state: dict, context, seconds: float, at: float) -> None:
    """After a vitals step of `seconds` game seconds: a wild pet's lots age, its chests' once a game minute,
    and what reached the end of its shelf life spoils. A crash is logged once and changes nothing."""
    if not is_wild(state):
        return
    try:
        settle_lots(state)
        went_bad(state, context, spoil(arms_lots(state), state["inventory"], 1.0, seconds), "arms", at)
        clock = state.setdefault("wild", {})
        waited = clock.get("chests_aged", 0.0) + seconds
        if waited >= CHEST_EVERY:
            for key, lots_of in list(state.get("chest_lots", {}).items()):
                chest = state.get("chests", {}).get(key)
                if chest is not None:
                    went_bad(state, context, spoil(lots_of, chest, CHEST_RATE, waited), "chest", at)
            waited = 0.0
        clock["chests_aged"] = waited
    except Exception as error:
        log_once(logger, "spoilage", error)


def worn(state: dict, item: str) -> float:
    """How worn the most worn lot of `item` Mimo carries is (0 with none)."""
    return max((wear for _, wear in (state.get("lots") or {}).get(item, [])), default=0.0)


def turning(state: dict, items) -> bool:
    """Some raw food Mimo carries is past TURNING of its shelf life."""
    return any(worn(state, item) > TURNING for item in items)
```

In `backend/survival/steps.py`, replace:

```python
        "nightberries": 8.0}  # W1: they fill like berries, and are poison
```

with:

```python
        "nightberries": 8.0, "spoiled_food": 4.0}  # W1: nightberries fill like berries, and are poison
```

and replace:

```python
            event = eats(step, state, at)
```

with:

```python
            event = eats(step, state, at)
        except (ValueError, KeyError):
            raise  # the food is gone (it spoiled while eaten): the step fails, as it would without W1
```

In `backend/survival/storage.py`, replace:

```python
from backend.survival.toolmaking import SWORD_LADDER
```

with:

```python
from backend.survival.toolmaking import SWORD_LADDER
from backend.survival.wild import unlocked
```

and replace:

```python
    (cooking.RAW_FOODS) is neither: it waits for the fire, since cook only uses what Mimo carries."""
```

with:

```python
    (cooking.RAW_FOODS) is neither: it waits for the fire, since cook only uses what Mimo carries. W1: a wild pet
    puts spare food away only once it knows `wild:keeping`."""
    if not unlocked(s, "keeping"):
        return []
```

In `backend/survival/tick.py`, replace:

```python
step takes a wild pet's ailments into account (backend.survival.ailments: `ailing` before, `tend` after).
```

with:

```python
step takes a wild pet's ailments into account (backend.survival.ailments: `ailing` before, `tend` after),
and its food ages (backend.survival.spoilage.age).
```

and replace:

```python
from backend.survival import ailments
```

with:

```python
from backend.survival import ailments, spoilage
```

and replace:

```python
            ailments.tend(state, step, activity, cursor, events)  # W1: a sickness runs its time
```

with:

```python
            ailments.tend(state, step, activity, cursor, events)  # W1: a sickness runs its time
            spoilage.age(state, context, step, cursor)  # W1: a wild pet's food ages
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_spoilage.py"`
Expected: `Ran 9 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1889 tests` … `OK (skipped=5)` (9 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/cooking.py backend/survival/meals.py backend/survival/purposes.py backend/survival/spoilage.py backend/survival/steps.py backend/survival/storage.py backend/survival/tick.py backend/tests/test_survival_spoilage.py
git commit -m "feat(W1): a wild pet's food spoils, half as fast in a chest, and keeping it well is a lesson" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Wounds and cold nights

**Files:**
- Create: `backend/survival/wounds.py`
- Modify: `backend/survival/ailments.py` (the wound, cold nights, dawn, `DAWN`), `backend/survival/tick.py` (`tend_night`), `backend/survival/creatures/harm.py` (`BLOWS`), `backend/survival/care.py` (`CARED`), `backend/services/crafting.py` (the bandage), `backend/survival/brain.py` (imports `wounds`)
- Modify: `backend/tests/test_survival_ailments.py` (its helper)
- Test: `backend/tests/test_survival_wounds.py`

**Interfaces:**
- Consumes: Task 5's ailments; `harm.hurt_pet`; `care.give_care`; `clock.NIGHT_PHASES`; `vitals.FREEZING_BELOW`; the tick's sheltered check.
- Produces:
  - `harm.BLOWS: list` of `(scene, lost, source)`, run after each blow; `care.CARED: list` of `(state, kind, timestamp)`.
  - `ailments.open_wound`, `dress`, `wound_of`, `tend_night(state, context, seconds, phases, activity, sheltered, at)`, `dawn`, `DAWN: list` of `(state, context, summary, at)`; `CHILL_BELOW = 35`, `CHILL_CHANCE = 0.6` (channel 205), `FESTER_AFTER`, `HEALS_AFTER`, `DRESSED_CLOSES`, `FESTER_DRAIN`.
  - `wounds.cut` (in `BLOWS`, channel 204), `cared` (in `CARED`), the step `dress`, the purpose `dress_wound` (76, a need); the recipe `bandage` (1 wool makes 2).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_ailments.py`, replace:

```python
from pathlib import Path
```

with:

```python
from pathlib import Path
from types import SimpleNamespace
```

and replace:

```python
        tend(state, step, activity, 0.0, events)
```

with:

```python
        tend(state, SimpleNamespace(events=events, db=None), step, activity, 0.0)
```

Create `backend/tests/test_survival_wounds.py`:

```python
"""W1: wounds that fester and cold nights, for a wild pet only."""

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose and step registered)
from backend.survival.ailments import (
    FESTER_DRAIN, ailing, dress, open_wound, sickness, tend, tend_night, wound_of,
)
from backend.survival.care import give_care
from backend.survival.creatures.harm import hurt_pet
from backend.survival.hatch import hatch
from backend.survival.memory import know
from backend.survival.purposes import PURPOSES, is_valid
from backend.survival.registry import LifeRegistry
from backend.survival.steps import finish_step, start_step
from backend.survival.tick import tick_life
from backend.survival.wild import thing, wild_state
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_cooking import situation
from backend.tests.test_survival_hostiles import meadow, pet, scene

BORN = 1_000_000.0


def wild_pet(**changes):
    return pet(difficulty="wild", **changes)


def after(state, seconds, step=30.0):
    context = SimpleNamespace(events=[], db=None)
    for _ in range(int(seconds / step)):
        tend(state, context, step, "working", 0.0)
    return context.events


class WoundTests(unittest.TestCase):
    def test_a_blow_of_two_or_more_opens_a_wound_three_times_in_ten(self):
        grid = meadow()
        state = wild_pet()
        with patch("backend.survival.wounds.roll", return_value=0.3):
            where = scene(grid, state)
            hurt_pet(where, 4.0, "skitter")
        self.assertIsNotNone(wound_of(state))
        self.assertIn((10.0, "wound", "A skitter cut Pip."), where.events)
        gentle, small, lucky = pet(), wild_pet(), wild_pet()
        with patch("backend.survival.wounds.roll", return_value=0.3):
            hurt_pet(scene(grid, gentle), 4.0, "skitter")
            hurt_pet(scene(grid, small), 1.5, "skitter")
        with patch("backend.survival.wounds.roll", return_value=0.4):
            hurt_pet(scene(grid, lucky), 4.0, "skitter")
        self.assertEqual([wound_of(found) for found in (gentle, small, lucky)], [None, None, None])
        self.assertEqual(wild_state(state)["night_blows"], 1)

    def test_undressed_it_festers_after_ten_game_minutes_and_heals_in_a_game_day(self):
        state = wild_pet()
        open_wound(state, 0.0)
        self.assertEqual(ailing(state).heals, False)
        self.assertEqual(after(state, 570), [])
        self.assertEqual(after(state, 30), [(0.0, "festering", "Pip's wound is festering.")])
        self.assertEqual((ailing(state).drain, ailing(state).mood), (FESTER_DRAIN, 10.0))
        after(state, 3000)
        self.assertIsNone(wound_of(state))
        self.assertIsNone(ailing(state))
        self.assertAlmostEqual(state["wild"]["lost"], 3000 * FESTER_DRAIN)  # what festering took, a hazard's

    def test_a_dressed_wound_stops_festering_at_once_and_closes_five_minutes_later(self):
        state = wild_pet()
        open_wound(state, 0.0)
        after(state, 900)
        self.assertTrue(dress(state))
        self.assertEqual(ailing(state).drain, 0.0)
        after(state, 270)
        self.assertIsNotNone(wound_of(state))
        after(state, 30)
        self.assertIsNone(wound_of(state))

    def test_the_dress_step_uses_a_bandage_or_a_sunleaf(self):
        for item, words in (("bandage", "Pip wrapped its wound in a bandage."), ("sunleaf", "Pip pressed sunleaf on its wound.")):
            state = wild_pet(inventory={item: 1})
            open_wound(state, 0.0)
            step = start_step({"kind": "dress", "item": item}, state, meadow(), 0.0)
            self.assertEqual(finish_step(step, state, meadow(), 2.0), ("dressed", words))
            self.assertEqual((state["inventory"], wound_of(state)["dressed_age"]), ({}, 0.0))

    def test_dress_wound_makes_a_bandage_from_wool_once_mimo_knows_how(self):
        s = situation({"wool": 1})
        s.state["difficulty"] = "wild"
        open_wound(s.state, 0.0)
        self.assertFalse(is_valid(PURPOSES["dress_wound"], s))
        know(s.db, thing("bandage"), "lesson", 0.0)
        s.__dict__.pop("lessons", None)
        self.assertTrue(is_valid(PURPOSES["dress_wound"], s))
        self.assertEqual(PURPOSES["dress_wound"].plan(s, None),
                         [{"kind": "craft", "recipe": "bandage"}, {"kind": "dress", "item": "bandage"}])

    def test_the_owners_care_bandage_dresses_a_wound(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                open_wound(state, BORN)
                write_state(db, state)
            give_care(world, "bandage", BORN)
            self.assertEqual(world.state()["ailments"]["wound"]["dressed_age"], 0.0)


class ColdNightTests(unittest.TestCase):
    def night(self, state, minutes_cold, froze=False, floor=False):
        context = SimpleNamespace(events=[], db=None)
        state["vitals"]["warmth"] = 30.0 if minutes_cold else 80.0
        for _ in range(minutes_cold or 10):
            tend_night(state, context, 60.0, ("night", "night"), "sleeping" if floor else "idle", floor, 1.0)
        if froze:
            state["vitals"]["warmth"] = 10.0
            tend_night(state, context, 1.0, ("night", "night"), "idle", False, 1.0)
        tend_night(state, context, 1.0, ("pre_dawn", "dawn"), "idle", False, 2.0)
        return context.events

    def test_fifteen_cold_minutes_or_any_freezing_give_a_chill_at_dawn(self):
        state = wild_pet()
        self.assertEqual(self.night(state, 15), [(2.0, "chill", "Pip caught a chill in the night.")])
        self.assertEqual(sickness(state)["kind"], "chill")
        frozen = wild_pet()
        self.night(frozen, 0, froze=True)
        self.assertEqual(sickness(frozen)["kind"], "chill")

    def test_five_cold_minutes_give_a_chill_six_times_in_ten_and_a_warm_night_none(self):
        for chance, caught in ((0.5, True), (0.7, False)):
            state = wild_pet()
            with patch("backend.survival.ailments.roll", return_value=chance):
                self.night(state, 5)
            self.assertEqual(sickness(state) is not None, caught)
        warm = wild_pet()
        self.assertEqual(self.night(warm, 0), [])
        self.assertEqual(wild_state(warm)["night_cold"], 0.0)

    def test_a_night_asleep_on_a_sheltered_floor_is_counted_and_a_gentle_pet_never_is(self):
        state = wild_pet()
        self.night(state, 0, floor=True)
        self.night(state, 0, floor=True)
        self.assertEqual(wild_state(state)["floor_nights"], 2)
        gentle = pet()
        self.night(gentle, 20)
        self.assertNotIn("wild", gentle)

    def test_a_wild_pet_out_in_the_open_catches_a_chill_on_its_first_night(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
            world = SurvivalWorld(registry.world_path(life))
            for second in range(1, 62):
                tick_life(registry, BORN + second, scale=60.0)
            kinds = [event["kind"] for event in world.events(500)]
        self.assertIn("chill", kinds)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wounds.py"`
Expected: ERROR: `ImportError: cannot import name 'FESTER_DRAIN' from 'backend.survival.ailments'`

- [ ] **Step 3: Wounds, dressing them and cold nights**

In `backend/services/crafting.py`, replace:

```python
    "leather_tunic": {"ingredients": {"leather": 3}, "output": {"leather_tunic": 1}, "station": "crafting_table"},
```

with:

```python
    "leather_tunic": {"ingredients": {"leather": 3}, "output": {"leather_tunic": 1}, "station": "crafting_table"},
    # W1: a wool bandage dresses a wound, made anywhere (a wild pet makes them once it knows how)
    "bandage": {"ingredients": {"wool": 1}, "output": {"bandage": 2}},
```

In `backend/survival/ailments.py`, replace:

```python

A gentle pet never has an ailment: nothing in W1 makes one, and `ailing` gives nothing without one. A
```

with:

```python

A wound (`state["ailments"]["wound"]` = {"since", "age", "festering", "dressed_age"}; `age` in game seconds;
backend.survival.wounds opens one): while it is open no health regenerates. Undressed for FESTER_AFTER (10 game
minutes) it festers ("Pip's wound is festering."): 1 health per 40 game s, and mood's target falls 10. It heals
by itself HEALS_AFTER (a game day) after it opened, festering or not; a dressed one stops festering at once and
closes DRESSED_CLOSES (5 game minutes) later (`dress`).

Cold nights (`tend_night`, after each vitals step): each night the game seconds with warmth under CHILL_BELOW
(35) are counted (`state["wild"]["night_cold"]`); at dawn 5 game minutes or more give a chill with chance
CHILL_CHANCE, 15 or more, or any freezing that night, a chill for sure ("Pip caught a chill in the night.", a
"chill" event). A night asleep on the floor of a sheltered spot counts in `floor_nights`. DAWN then hears how
the night went (backend.survival.knocks).

A gentle pet never has an ailment: nothing in W1 makes one, and `ailing` gives nothing without one. A
```

and replace:

```python
from backend.services.crafting import take_items
```

with:

```python
from backend.services.crafting import take_items
from backend.survival.clock import DAY_SECONDS, NIGHT_PHASES
```

and replace:

```python
from backend.survival.vitals import Ailing
from backend.survival.wild import wild_state
```

with:

```python
from backend.survival.vitals import FREEZING_BELOW, Ailing
from backend.survival.wild import is_wild, wild_state
```

and replace:

```python
NIBBLE_CHANNEL = 200  # Wild World's roll channels are 200 to 259 (spec resolution 27)
```

with:

```python
NIBBLE_CHANNEL = 200  # Wild World's roll channels are 200 to 259 (spec resolution 27)
FESTER_AFTER = 10 * GAME_MINUTE
HEALS_AFTER = DAY_SECONDS
DRESSED_CLOSES = 5 * GAME_MINUTE
FESTER_DRAIN = 1 / 40
FESTER_MOOD = 10.0
CHILL_BELOW = 35.0
CHILL_SOME = 5 * GAME_MINUTE  # a chill with CHILL_CHANCE
CHILL_SURE = 15 * GAME_MINUTE  # a chill for sure
CHILL_CHANCE = 0.6
CHILL_CHANNEL = 205
FLOOR_SLEEP = 5 * GAME_MINUTE  # asleep on the floor of a sheltered spot this long: a night on the floor
# W1: functions (state, context, summary, at) run at a wild pet's dawn with how its night went: {"cold" (game
# seconds under CHILL_BELOW), "froze", "chill" (it caught one), "blows" (hostile blows that night), "floor" (a
# night asleep on the floor of a sheltered spot)} (backend.survival.knocks). One that crashes is logged once.
DAWN: list = []
```

and replace:

```python
def ailing(state: dict) -> Ailing | None:
    """What Mimo's ailments do to a vitals step now; None without any (a gentle pet, always)."""
    found = sickness(state)
    if found is None:
        return None
    ailment = AILMENTS.get(found["kind"])
    if ailment is None:
        return None
    return Ailing(drain=ailment.drain, hunger=ailment.hunger, energy=ailment.energy, heals=False, mood=SICK_MOOD)
```

with:

```python
def wound_of(state: dict) -> dict | None:
    """Mimo's wound now, or None (read only)."""
    return (state.get("ailments") or {}).get("wound")


def ailing(state: dict) -> Ailing | None:
    """What Mimo's ailments do to a vitals step now; None without any (a gentle pet, always)."""
    found, wound = sickness(state), wound_of(state)
    ailment = AILMENTS.get(found["kind"]) if found is not None else None
    if ailment is None and wound is None:
        return None
    festering = wound is not None and wound["festering"]
    return Ailing(drain=(ailment.drain if ailment else 0.0) + (FESTER_DRAIN if festering else 0.0),
                  hunger=ailment.hunger if ailment else 1.0, energy=ailment.energy if ailment else 1.0, heals=False,
                  mood=(SICK_MOOD if ailment else 0.0) + (FESTER_MOOD if festering else 0.0))
```

and replace:

```python
    """Count `health` a wild pet lost to its hazards (a sickness's drain, a poison plant) in
```

with:

```python
    """Count `health` a wild pet lost to its hazards (a sickness's or a festering wound's drain, a poison plant) in
```

and replace:

```python
def tend(state: dict, seconds: float, activity: str, at: float, events: list) -> None:
    """After a vitals step of `seconds` game seconds: what its drain took is counted, and the sickness runs its
    time (a chill twice as fast while Mimo rests or sleeps warm). A crash is logged once and changes nothing."""
```

with:

```python
def open_wound(state: dict, at: float) -> bool:
    """A creature's blow opens a wound, unless Mimo has one already. True when it did."""
    found = ailments_of(state)
    if found["wound"] is not None:
        return False
    found["wound"] = {"since": at, "age": 0.0, "festering": False, "dressed_age": None}
    state["last_thought"] = "Ow, it's bleeding. That will need looking after."
    return True


def dress(state: dict) -> bool:
    """The wound is dressed: it stops festering at once and closes DRESSED_CLOSES later. True when there was an
    open wound not dressed yet."""
    found = wound_of(state)
    if found is None or found["dressed_age"] is not None:
        return False
    found.update(festering=False, dressed_age=found["age"])
    state["last_thought"] = "There. All wrapped up."
    return True


def heard(hooks: list, *args) -> None:
    for hears in hooks:
        try:
            hears(*args)
        except Exception as error:
            log_once(logger, "ailments hook", error)


def tend(state: dict, context, seconds: float, activity: str, at: float) -> None:
    """After a vitals step of `seconds` game seconds: what its drain took is counted, the sickness runs its time
    (a chill twice as fast while Mimo rests or sleeps warm), and a wound festers, closes or heals. A crash is
    logged once and changes nothing."""
```

and replace:

```python
        if found is None:
            return
        rested = activity != "working" and state["vitals"]["warmth"] >= WARM_REST
        found["left"] = max(0.0, found["left"] - seconds * (2.0 if found["kind"] == "chill" and rested else 1.0))
        if found["left"] <= 0:
            state["ailments"]["sick"] = None
            state["last_thought"] = "I feel better now."
    except Exception as error:
        log_once(logger, "ailments", error)
```

with:

```python
        if found is not None:
            rested = activity != "working" and state["vitals"]["warmth"] >= WARM_REST
            found["left"] = max(0.0, found["left"] - seconds * (2.0 if found["kind"] == "chill" and rested else 1.0))
            if found["left"] <= 0:
                state["ailments"]["sick"] = None
                state["last_thought"] = "I feel better now."
        wound = wound_of(state)
        if wound is not None:
            wound["age"] += seconds
            dressed = wound["dressed_age"]
            if wound["age"] >= HEALS_AFTER or (dressed is not None and wound["age"] - dressed >= DRESSED_CLOSES):
                state["ailments"]["wound"] = None
                state["last_thought"] = "My wound has healed."
            elif dressed is None and not wound["festering"] and wound["age"] >= FESTER_AFTER:
                wound["festering"] = True
                state["last_thought"] = "My wound hurts more and more."
                context.events.append((at, "festering", f"{state['name']}'s wound is festering."))
    except Exception as error:
        log_once(logger, "ailments", error)


def tend_night(state: dict, context, seconds: float, phases: tuple[str, str], activity: str, sheltered: bool,
               at: float) -> None:
    """After a vitals step (see the module docstring): a wild pet's cold and floor at night, and at dawn its
    chill, its floor night and DAWN. A crash is logged once and changes nothing."""
    if not is_wild(state):
        return
    try:
        night = wild_state(state)
        before, after = phases
        if before in NIGHT_PHASES:
            warmth = state["vitals"]["warmth"]
            if warmth < CHILL_BELOW:
                night["night_cold"] += seconds
            if warmth < FREEZING_BELOW:
                night["froze"] = True
            if activity == "sleeping" and sheltered:
                night["floor_sleep"] = night.get("floor_sleep", 0.0) + seconds
        if before in NIGHT_PHASES and after not in NIGHT_PHASES:
            dawn(state, context, at)
    except Exception as error:
        log_once(logger, "cold night", error)


def dawn(state: dict, context, at: float) -> None:
    """The night is over: a chill for a cold one, a floor night counted, and DAWN told how it went."""
    night = wild_state(state)
    cold, froze = night["night_cold"], bool(night.get("froze"))
    chance = 1.0 if cold >= CHILL_SURE or froze else CHILL_CHANCE if cold >= CHILL_SOME else 0.0
    chill = chance > 0 and roll(state.get("world_seed", "0"), pet_cell(state), CHILL_CHANNEL, int(at)) < chance
    if chill:
        fall_sick(state, "chill", at)
        context.events.append((at, "chill", f"{state['name']} caught a chill in the night."))
    floor = night.get("floor_sleep", 0.0) >= FLOOR_SLEEP
    if floor:
        night["floor_nights"] += 1
    summary = {"cold": cold, "froze": froze, "chill": chill, "blows": night.get("night_blows", 0), "floor": floor}
    night.update(night_cold=0.0, froze=False, floor_sleep=0.0, night_blows=0)
    heard(DAWN, state, context, summary, at)
```

and replace:

```python
    return {"sick": sick_view, "wound": None}
```

with:

```python
    wound = wound_of(state)
    wound_view = None if wound is None else {"festering": wound["festering"], "dressed": wound["dressed_age"] is not None,
                                             "minutes": math.ceil(max(0.0, HEALS_AFTER - wound["age"]) / GAME_MINUTE)}
    return {"sick": sick_view, "wound": wound_view}
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import herbs, meals  # noqa: F401  (W1: sunleaf; a wild pet's meals and throw_out)
```

with:

```python
from backend.survival import herbs, meals, wounds  # noqa: F401  (W1: sunleaf; meals and throw_out; wounds)
```

In `backend/survival/care.py`, replace:

```python

from datetime import datetime, timezone
```

with:

```python

import logging
from datetime import datetime, timezone
```

and replace:

```python
from backend.survival.world import LifeOver, SurvivalWorld, check_not_behind, log_event, read_state, write_state
```

with:

```python
from backend.survival.once import log_once
from backend.survival.world import LifeOver, SurvivalWorld, check_not_behind, log_event, read_state, write_state

logger = logging.getLogger(__name__)
```

and replace:

```python
CARE_THOUGHTS = {"snack": "Yum! Thank you.", "bandage": "That feels much better."}
```

with:

```python
CARE_THOUGHTS = {"snack": "Yum! Thank you.", "bandage": "That feels much better."}
# W1: functions (state, kind, timestamp) run as care is given (backend.survival.wounds: a bandage dresses a
# wound). One that crashes gives nothing more.
CARED: list = []
```

and replace:

```python
        state["last_thought"] = CARE_THOUGHTS[kind]
```

with:

```python
        state["last_thought"] = CARE_THOUGHTS[kind]
        for cared in CARED:  # W1
            try:
                cared(state, kind, timestamp)
            except Exception as error:
                log_once(logger, "care", error)
```

In `backend/survival/creatures/harm.py`, replace:

```python
HURT_QUIET = 10.0  # server seconds (at the normal pace) between two "hurt" events
```

with:

```python
HURT_QUIET = 10.0  # server seconds (at the normal pace) between two "hurt" events
# W1: functions (scene, health lost, source) run after each blow (backend.survival.wounds: a wild pet's wound).
# One that crashes is logged once and passed over.
BLOWS: list = []
```

and replace:

```python
            raise
    return lost
```

with:

```python
            raise
    for blown in BLOWS:  # W1
        try:
            blown(scene, lost, source)
        except Exception as error:
            log_once(logger, "blows", error)
    return lost
```

In `backend/survival/tick.py`, replace:

```python
            ailments.tend(state, step, activity, cursor, events)  # W1: a sickness runs its time
```

with:

```python
            ailments.tend(state, context, step, activity, cursor)  # W1: a sickness runs its time, a wound too
            phases = (clock_at(state["born_at"], since, scale)["phase"], clock_at(state["born_at"], cursor, scale)["phase"])
            ailments.tend_night(state, context, step, phases, activity, surroundings.sheltered, cursor)  # W1: cold nights
```

Create `backend/survival/wounds.py`:

```python
"""W1: wounds that fester ("Hazards" 4 of the Wild World spec), for a wild pet only.

A creature's blow that takes 2 health or more after armor (WOUND_FROM; leather armor keeps a skitter's blow
under it) opens a wound with chance WOUND_CHANCE (a seeded roll), unless Mimo has one: "A skitter cut Pip."
(a "wound" event; harm.BLOWS: `cut`). A blow at night is counted for the night's summary too (the shelter and
light lessons' knocks: backend.survival.ailments.DAWN). What a wound does and how it heals is
backend.survival.ailments'.

Dressing (the `dress` step, 2 game seconds, with a bandage or a sunleaf it carries) stops a wound festering at
once. A pet that knows `wild:bandage` makes bandages (1 wool makes 2, anywhere: crafting's "bandage") and
dresses with one; one that knows `wild:sunleaf` presses a sunleaf on it: "Pip wrapped its wound in a bandage."
or "Pip pressed sunleaf on its wound." (a "dressed" event). `dress_wound` (76, a need) does it. The owner's
care bandage dresses a wound too, besides its 25 health (care.CARED).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.crafting import take_items
from backend.survival.ailments import HERB, dress, open_wound, wound_of
from backend.survival.care import CARED
from backend.survival.cooking import made
from backend.survival.creatures.harm import BLOWS
from backend.survival.goals import add_urge
from backend.survival.nature import roll
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import StepFailed, StepKind, register_step
from backend.survival.wild import is_wild, knows, wild_state

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

WOUND_FROM = 2.0
WOUND_CHANCE = 0.35
WOUND_CHANNEL = 204
DRESS_SECONDS = 2.0
BANDAGE = "bandage"
DRESSINGS = (BANDAGE, HERB)
WORDS = {BANDAGE: "{name} wrapped its wound in a bandage.", HERB: "{name} pressed sunleaf on its wound."}


def cut(scene, lost: float, source: str) -> None:
    """harm.BLOWS: a wild pet's blow may open a wound; one at night counts for the night."""
    state = scene.state
    if not is_wild(state):
        return
    if scene.night:
        found = wild_state(state)
        found["night_blows"] = found.get("night_blows", 0) + 1
    if lost < WOUND_FROM or wound_of(state) is not None:
        return
    if roll(scene.seed, scene.pet, WOUND_CHANNEL, int(scene.at)) < WOUND_CHANCE and open_wound(state, scene.at):
        scene.events.append((scene.at, "wound", f"A {source.replace('_', ' ')} cut {state['name']}."))


BLOWS.append(cut)


def cared(state: dict, kind: str, timestamp: float) -> None:
    """care.CARED: the owner's bandage dresses a wound."""
    if kind == BANDAGE and dress(state):
        state["last_thought"] = "You wrapped my wound. Thank you!"


CARED.append(cared)


# The dress step --------------------------------------------------------------------------------

def start_dress(spec: dict, state: dict, grid, at: float, scale: float) -> dict:
    item = spec["item"]
    if item not in DRESSINGS:
        raise StepFailed(f"{item.replace('_', ' ')} cannot dress a wound")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {item.replace('_', ' ')} to dress a wound with", "missing_item")
    found = wound_of(state)
    if found is None or found["dressed_age"] is not None:
        raise StepFailed("no wound to dress", "gone")
    return {"kind": "dress", "started_at": at, "ends_at": round(at + DRESS_SECONDS / scale, 3), "item": item}


def finish_dress(step: dict, state: dict, grid, at: float) -> tuple[str, str] | None:
    if state["inventory"].get(step["item"], 0) < 1 or not dress(state):
        raise StepFailed("no wound to dress", "gone")
    state["inventory"] = take_items(state["inventory"], {step["item"]: 1})
    return "dressed", WORDS[step["item"]].format(name=state["name"])


register_step(StepKind("dress", start_dress, finish_dress, "dressing", string_field="item"))


# dress_wound -----------------------------------------------------------------------------------

def dressing(s: Situation) -> tuple[str, list[dict]] | None:
    """What Mimo dresses its wound with, and the craft steps that make it: a bandage it carries or makes (it
    knows bandages), else a sunleaf it carries (it knows sunleaf)."""
    if knows(s, "bandage"):
        if s.inventory.get(BANDAGE, 0) > 0:
            return BANDAGE, []
        trial = dict(s.inventory)
        steps = made(trial, BANDAGE)
        if steps is not None:
            return BANDAGE, steps
    if knows(s, "sunleaf") and s.inventory.get(HERB, 0) > 0:
        return HERB, []
    return None


def dress_valid(s: Situation) -> bool:
    found = wound_of(s.state)
    return is_wild(s.state) and found is not None and found["dressed_age"] is None and dressing(s) is not None


def plan_dress(s: Situation, context: ActionContext) -> list[dict]:
    found = dressing(s) if dress_valid(s) and s.brain["batches"] == 0 else None
    if found is None:
        return []
    item, crafting = found
    return [*crafting, {"kind": "dress", "item": item}]


add_urge("dress_wound", dress_valid)
register(Purpose(
    "dress_wound", "dress its wound", "Wrap the wound in a bandage, or press sunleaf on it, before it festers.",
    valid=dress_valid, facts=lambda s: f"a wound {'festering' if wound_of(s.state)['festering'] else 'open'}; "
                                       f"dressing it with {dressing(s)[0]}",
    score=lambda s: 76.0, plan=plan_dress,
    thoughts=("Let me look after this wound.", "A clean wrap, and it will heal.")))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wounds.py"`
Expected: `Ran 10 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1899 tests` … `OK (skipped=5)` (10 new).

- [ ] **Step 5: Commit**

```bash
git add backend/services/crafting.py backend/survival/ailments.py backend/survival/brain.py backend/survival/care.py backend/survival/creatures/harm.py backend/survival/tick.py backend/survival/wounds.py backend/tests/test_survival_ailments.py backend/tests/test_survival_wounds.py
git commit -m "feat(W1): a blow can leave a wound that festers unless dressed, and a cold night can bring a chill" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Learning alone: knocks

**Files:**
- Create: `backend/survival/knocks.py`
- Modify: `backend/survival/ailments.py` (the dawn's summary for the knocks), `backend/survival/brain.py` (imports `knocks`)
- Test: `backend/tests/test_survival_knocks.py`

**Interfaces:**
- Consumes: Tasks 5 to 8's hooks (`steps.OBSERVERS`, `harm.BLOWS`, `ailments.DAWN`, `spoilage.SPOILS`); `journal`'s learning (`FACT`, `NEW_LESSON`, `journal_state`); `curiosity.discovered`; `triggers.mark_trigger`.
- Produces: `knocks.KNOCKS` (`Knock(first, step)` for seven lessons; berries, red mushrooms and fire's first smelt are sure knocks), `OWNER_ONLY = ("sunleaf", "bandage")` (never worked out: spec resolution 29), `KNOCK_CHANNEL = 206`, `figure(state, db, events, at, name) -> bool` (a `figured` event, `wild.FIGURED`, the journal line "I worked it out myself: …"), `knock(...)`, `sure(...)`, `LEARNED: list` of `(db, state, name, at)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_knocks.py`:

```python
"""W1: a wild pet learns its survival lessons alone, by knocks."""

import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every observer and hook registered)
from backend.survival.knocks import KNOCKS, OWNER_ONLY, after_step, at_dawn, blown, knock, spoils, sure
from backend.survival.memory import create_memory_tables, know
from backend.survival.vitals import START_VITALS
from backend.survival.wild import survival_view, thing, wild_state


def world(**changes):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "difficulty": "wild", "traits": {"curiosity": 50}}
    state.update(changes)
    return state, SimpleNamespace(db=db, events=[])


def knows(context, name):
    return context.db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact='lesson'",
                              (thing(name),)).fetchone() is not None


class KnockTests(unittest.TestCase):
    def test_the_chance_grows_with_every_knock_and_curiosity(self):
        state, context = world()
        with patch("backend.survival.knocks.roll", return_value=0.31):
            self.assertFalse(knock(state, context.db, context.events, 1.0, "light"))  # 0.10
            self.assertFalse(knock(state, context.db, context.events, 2.0, "light"))  # 0.20
            self.assertFalse(knock(state, context.db, context.events, 3.0, "light"))  # 0.30
            self.assertTrue(knock(state, context.db, context.events, 4.0, "light"))  # 0.40
        self.assertEqual(wild_state(state)["knocks"]["light"], 4)
        curious, where = world(traits={"curiosity": 100})
        with patch("backend.survival.knocks.roll", return_value=0.11):
            self.assertTrue(knock(curious, where.db, where.events, 1.0, "light"))  # 0.10 x 1.2 = 0.12
        dull, there = world(traits={"curiosity": 0})
        with patch("backend.survival.knocks.roll", return_value=0.09):
            self.assertFalse(knock(dull, there.db, there.events, 1.0, "light"))  # 0.10 x 0.8 = 0.08

    def test_a_lesson_worked_out_is_a_figured_event_journalled_as_worked_out(self):
        state, context = world()
        self.assertTrue(sure(state, context.db, context.events, 5.0, "cooking"))
        self.assertEqual(context.events, [(5.0, "figured", "Pip worked out that cooking makes meat safe.")])
        self.assertTrue(state["brain"]["journal"]["words"][thing("cooking")].startswith("I worked it out myself: "))
        self.assertEqual({entry["name"]: entry["source"] for entry in survival_view(context.db)}["cooking"], "figured")
        self.assertFalse(sure(state, context.db, context.events, 6.0, "cooking"))  # once

    def test_the_table_of_knocks(self):
        self.assertEqual({name: (rule.first, rule.step) for name, rule in KNOCKS.items()},
                         {"nightberries": (0.25, 0.15), "fire": (0.15, 0.15),
                          "cooking": (0.25, 0.15), "keeping": (0.20, 0.15), "light": (0.10, 0.10),
                          "shelter": (0.25, 0.20), "bed": (0.10, 0.10)})

    def test_sunleaf_and_bandages_are_never_learned_alone(self):
        state, context = world(inventory={"wool": 1})
        self.assertEqual(OWNER_ONLY, ("sunleaf", "bandage"))
        with patch("backend.survival.knocks.roll", return_value=0.0):
            for name in OWNER_ONLY:
                self.assertFalse(sure(state, context.db, context.events, 1.0, name))
                self.assertFalse(knock(state, context.db, context.events, 1.0, name))
            after_step(state, {"kind": "eat", "item": "sunleaf", "cured": True}, context, 2.0)  # a nibble cured it
        self.assertFalse(knows(context, "sunleaf") or knows(context, "bandage"))
        self.assertEqual(context.events, [])

    def test_a_gentle_pet_never_knocks(self):
        state, context = world(difficulty="gentle")
        with patch("backend.survival.knocks.roll", return_value=0.0):
            self.assertFalse(knock(state, context.db, context.events, 1.0, "fire"))
        self.assertFalse(sure(state, context.db, context.events, 1.0, "berries"))


class WhereKnocksAreHeardTests(unittest.TestCase):
    def test_eating_teaches_the_food_lessons(self):
        state, context = world()
        after_step(state, {"kind": "eat", "item": "berries"}, context, 1.0)
        self.assertTrue(knows(context, "berries"))
        after_step(state, {"kind": "eat", "item": "red_mushroom", "sick": True}, context, 2.0)
        self.assertTrue(knows(context, "red_mushroom"))
        wild_state(state)["shun"]["red_berries"] = 3.0
        with patch("backend.survival.knocks.roll", return_value=0.0):
            after_step(state, {"kind": "eat", "item": "nightberries", "sick": True}, context, 4.0)
        self.assertTrue(knows(context, "nightberries"))
        self.assertNotIn("red_berries", wild_state(state)["shun"])  # it can tell them apart now

    def test_a_raw_meal_teaches_cooking_only_once_mimo_knows_fire(self):
        state, context = world()
        with patch("backend.survival.knocks.roll", return_value=0.0):
            after_step(state, {"kind": "eat", "item": "raw_beef", "raw": True, "sick": True}, context, 1.0)
            self.assertFalse(knows(context, "cooking"))
            know(context.db, thing("fire"), "lesson", 1.0)
            after_step(state, {"kind": "eat", "item": "raw_beef", "raw": True, "sick": True}, context, 2.0)
        self.assertTrue(knows(context, "cooking"))

    def test_smelting_teaches_fire_for_sure(self):
        state, context = world()
        after_step(state, {"kind": "smelt", "item": "iron_ore"}, context, 1.0)
        self.assertTrue(knows(context, "fire"))

    def test_nights_blows_and_spoiled_food_knock(self):
        state, context = world()
        with patch("backend.survival.knocks.roll", return_value=0.0):
            at_dawn(state, context, {"chill": True, "blows": 0, "floor": True, "cold": 900.0, "froze": False}, 1.0)
            spoils(state, context, "raw_beef", 1, "arms", 3.0)
            scene = SimpleNamespace(night=True, state=state, herd=SimpleNamespace(db=context.db), events=context.events,
                                    at=4.0)
            blown(scene, 3.0, "gloomling")
        for name in ("fire", "shelter", "bed", "keeping", "light"):
            self.assertTrue(knows(context, name), name)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_knocks.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.knocks'`

- [ ] **Step 3: Knocks and where they are heard**

In `backend/survival/brain.py`, replace:

```python
from backend.survival import herbs, meals, wounds  # noqa: F401  (W1: sunleaf; meals and throw_out; wounds)
```

with:

```python
from backend.survival import herbs, meals, wounds  # noqa: F401  (W1: sunleaf; meals and throw_out; wounds)
from backend.survival import knocks  # noqa: F401  (W1: learning alone)
```

Create `backend/survival/knocks.py`:

```python
"""W1: learning alone, by knocks ("Learning alone: knocks" of the Wild World spec).

A knock is a painful experience. On each one the lesson it can teach is rolled for (a seeded roll,
nature.roll) against a chance that grows with every knock of that lesson: `first + step x knocks so far`,
times `0.8 + curiosity / 250` (0.8 to 1.2). Some experiences teach for sure. A lesson learned this way is
learned as the journal learns (backend.survival.journal), with a notable "figured" event instead ("Pip worked
out that cooking makes meat safe."), memory_knowledge's second fact wild.FIGURED, a discovery for curiosity,
and the journal line "I worked it out myself: ...". The counts live in `state["wild"]["knocks"]`.

| Lesson | Knock | First | Step | Sure when |
|---|---|---|---|---|
| berries | | | | it eats from the red berries and is not sick |
| nightberries | sick from a nightberry | 0.25 | 0.15 | |
| red_mushroom | | | | sick from a red mushroom |
| fire | a chilled night | 0.15 | 0.15 | it smelts at a furnace for the first time |
| cooking | sick from a raw meal, knowing fire | 0.25 | 0.15 | |
| keeping | sick from spoiled food, or food spoils in its arms or chest | 0.20 | 0.15 | |
| light | a hostile's blow at night | 0.10 | 0.10 | |
| shelter | a bad night: a chill at dawn, or a hostile's blow that night | 0.25 | 0.20 | |
| bed | a night asleep on the floor of a sheltered spot | 0.10 | 0.10 | |

The chances are as unlikely as the gate's "not hopeless" criteria allow (spec resolution 29, the controller's
ruling on the W1 dry run): each first chance is one step (0.05) lower than first planned, and a second step left
pets that knew only 6 or 7 lessons alone by day 60. Two lessons are never learned alone (OWNER_ONLY, the same
ruling): sunleaf and bandage. A pet cannot guess that an herb cures a sickness, or that wool on a wound stops it
festering. A sunleaf the instinct nibbles while sick (backend.survival.herbs) makes Mimo better that once and
teaches nothing; Mimo still asks about the herb and its wounds, and the owner's answer or teaching is the only
way in.

The knocks are heard where they happen: finished steps (steps.OBSERVERS: eating, smelting), blows
(harm.BLOWS), dawn (ailments.DAWN) and spoiled food (spoilage.SPOILS). Learning the difference between the red
berries lifts their shun at once. Only a wild pet has knocks; a gentle pet knows every lesson already.
LEARNED hears of each lesson worked out (the questions Mimo asked close as "figured out":
backend.survival.questions). A crash is logged once and teaches nothing.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from backend.survival.ailments import DAWN
from backend.survival.creatures.harm import BLOWS
from backend.survival.curiosity import GROUND_FLOOR, discovered, value_of
from backend.survival.journal import FACT, NEW_LESSON, journal_state
from backend.survival.memory import know
from backend.survival.nature import roll
from backend.survival.once import log_once
from backend.survival.spoilage import SPOILED, SPOILS
from backend.survival.steps import OBSERVERS
from backend.survival.triggers import mark_trigger
from backend.survival.wild import BY_NAME, FIGURED, RED_BERRIES, RED_MUSHROOM, SURVIVAL, is_wild, thing, wild_state

logger = logging.getLogger(__name__)

KNOCK_CHANNEL = 206  # and one more for each lesson, in the table's order (206 to 216)
OWNER_ONLY = ("sunleaf", "bandage")  # never learned alone: only the owner teaches them
# W1: functions (db, state, name, at) run when Mimo works a survival lesson out alone. One that crashes is logged once.
LEARNED: list = []


@dataclass(frozen=True)
class Knock:
    first: float
    step: float


KNOCKS: dict[str, Knock] = {
    "nightberries": Knock(0.25, 0.15), "fire": Knock(0.15, 0.15),
    "cooking": Knock(0.25, 0.15), "keeping": Knock(0.20, 0.15), "light": Knock(0.10, 0.10),
    "shelter": Knock(0.25, 0.20), "bed": Knock(0.10, 0.10),
}


def known(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact=?", (thing(name), FACT)).fetchone() is not None


def pet_cell(state: dict) -> tuple[int, int, int]:
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def figure(state: dict, db: sqlite3.Connection, events: list, at: float, name: str) -> bool:
    """Mimo works the lesson `name` out alone. True the first time; never for an OWNER_ONLY lesson."""
    lesson = BY_NAME[name]
    if name in OWNER_ONLY or not know(db, thing(name), FACT, at):
        return False
    know(db, thing(name), FIGURED, at)
    events.append((at, "figured", f"{state['name']} worked out that {lesson.figured}."))
    journal = journal_state(state)
    journal["words"] = {**journal["words"], thing(name): f"I worked it out myself: {lesson.fact[:1].lower()}{lesson.fact[1:]}"}
    discovered(state, at, min(NEW_LESSON, max(0.0, value_of(state.get("brain")) - GROUND_FLOOR)))
    mark_trigger(state, "discovery", at)
    state["last_thought"] = f"I worked it out: {lesson.figured}!"
    if name == "nightberries":
        wild_state(state)["shun"].pop("red_berries", None)  # it knows the difference now
    for learned in LEARNED:
        try:
            learned(db, state, name, at)
        except Exception as error:
            log_once(logger, "learned alone", error)
    return True


def knock(state: dict, db: sqlite3.Connection | None, events: list, at: float, name: str) -> bool:
    """A knock for the lesson `name`: rolled for at its growing chance. True when it taught the lesson."""
    if not is_wild(state) or db is None or name not in KNOCKS or known(db, name):
        return False
    rule = KNOCKS[name]
    counts = wild_state(state)["knocks"]
    so_far = counts.get(name, 0)
    counts[name] = so_far + 1
    curiosity = float(state.get("traits", {}).get("curiosity", 50))
    chance = (rule.first + rule.step * so_far) * (0.8 + curiosity / 250)
    channel = KNOCK_CHANNEL + [lesson.name for lesson in SURVIVAL].index(name)
    if roll(state.get("world_seed", "0"), pet_cell(state), channel, int(at)) >= chance:
        return False
    return figure(state, db, events, at, name)


def sure(state: dict, db: sqlite3.Connection | None, events: list, at: float, name: str) -> bool:
    """An experience that teaches `name` for sure."""
    if not is_wild(state) or db is None:
        return False
    return figure(state, db, events, at, name)


def guarded(teach) -> None:
    try:
        teach()
    except Exception as error:
        log_once(logger, "knocks", error)


# Where the knocks are heard ----------------------------------------------------------------------

def after_step(state: dict, step: dict, context, at: float) -> None:
    """steps.OBSERVERS: eating and smelting."""
    db, events = context.db, context.events
    item = step.get("item")
    if step["kind"] == "eat":
        if item in RED_BERRIES and not step.get("sick"):
            guarded(lambda: sure(state, db, events, at, "berries"))
        elif item == "nightberries":
            guarded(lambda: knock(state, db, events, at, "nightberries"))
        elif item == RED_MUSHROOM and step.get("sick"):
            guarded(lambda: sure(state, db, events, at, "red_mushroom"))
        elif item == SPOILED and step.get("sick"):
            guarded(lambda: knock(state, db, events, at, "keeping"))
        elif step.get("raw") and step.get("sick") and db is not None and known(db, "fire"):
            guarded(lambda: knock(state, db, events, at, "cooking"))
    elif step["kind"] == "smelt":
        guarded(lambda: sure(state, db, events, at, "fire"))


def blown(scene, lost: float, source: str) -> None:
    """harm.BLOWS: a hostile's blow at night."""
    if scene.night:
        guarded(lambda: knock(scene.state, scene.herd.db, scene.events, scene.at, "light"))


def at_dawn(state: dict, context, summary: dict, at: float) -> None:
    """ailments.DAWN: a chilled night, a bad night, a night on the floor."""
    db, events = context.db, context.events
    if summary["chill"]:
        guarded(lambda: knock(state, db, events, at, "fire"))
    if summary["chill"] or summary["blows"]:
        guarded(lambda: knock(state, db, events, at, "shelter"))
    if summary["floor"]:
        guarded(lambda: knock(state, db, events, at, "bed"))


def spoils(state: dict, context, item: str, count: int, where: str, at: float) -> None:
    """spoilage.SPOILS: food went bad in Mimo's arms or chest."""
    guarded(lambda: knock(state, context.db, context.events, at, "keeping"))


OBSERVERS.append(after_step)
BLOWS.append(blown)
DAWN.append(at_dawn)
SPOILS.append(spoils)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_knocks.py"`
Expected: `Ran 9 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1908 tests` … `OK (skipped=5)` (9 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/brain.py backend/survival/knocks.py backend/tests/test_survival_knocks.py
git commit -m "feat(W1): alone, a wild pet works its lessons out from what hurts it, slowly" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Mimo's questions: wonders, chips, yes and no

**Files:**
- Create: `backend/survival/wonders.py`, `backend/survival/questions.py`
- Modify: `backend/survival/teaching.py` (`REWORDS`, `TAUGHT_HOOKS`), `backend/survival/meals.py` (hesitation in `HOLDS`), `backend/survival/spoilage.py` (the last food spoiled), `backend/survival/bond_view.py` (`questions`), `backend/survival/bonding.py` (imports `questions`), `backend/survival/brain.py` (`meet_wonders`), `backend/api/bond.py` (the answer endpoint's `choice`)
- Test: `backend/tests/test_survival_questions.py`

**Interfaces:**
- Consumes: Task 2's lessons and parser; Task 9's `LEARNED`; the Talker's `CHORES`; `bond`'s inbox (`post`, `mimo_inbox`), `say`; `teaching.teach_lesson`; `questions`' chat question and `KEEPERS`; `exploring.compass`; `steps.OBSERVERS`.
- Produces:
  - `wonders.WONDERS` (ten `Wonder(id, words, lessons, chips, asked, fill, items, yes, no, lie)` with `Chip(words, teaches, false)`), `met(state, id, at, fill)`, `meet(state, context, at)` (the brain's `meet_wonders`), `sighted` (in `OBSERVERS`), `hesitates` (in `meals.HOLDS`), `open_questions(db)`, `HESITATE = 480`, `OPEN_MOST = 3`.
  - `questions.ask_wonders` (a Talker chore), `answer_question(world, item_id, choice, now, scale) -> dict` (`LookupError`, `ValueError`, `LifeOver`), `questions_view(db)`, `ASK_GAP = 300`, `SHUFFLE_CHANNEL = 220`; the chat question `"answer"` and its keeper.
  - `teaching.REWORDS: list` of `(db, s, heard) -> str | None`; `teaching.TAUGHT_HOOKS: list` of `(db, state, lesson_thing, now)`.
  - `POST /api/mimo/inbox/{id}/answer` takes `{"text"}` or `{"choice"}`; `/api/mimo`'s inbox gains `questions`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_questions.py`:

```python
"""W1: Mimo asks its owner about what it does not understand, waits, and hears the answers."""

import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import backend.survival.brain  # noqa: F401  (every hook registered)
from backend.survival import bonding, minding  # noqa: F401  (the chat, the inbox and teaching)
from backend.api.bond import PlaceName, answer_inbox
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items
from backend.survival.memory import know
from backend.survival.meals import wild_meal
from backend.survival.questions import answer_question, ask_wonders, questions_view
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.talk import owner_says
from backend.survival.talker import Talker
from backend.survival.wild import thing
from backend.survival.wonders import WONDERS, hesitates, met
from backend.survival.world import LifeOver, SurvivalWorld, read_state, write_state
from backend.tests.no_model import no_model

BORN = 1_000_000.0
SCALE = 60.0


class QuestionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN, difficulty="wild")
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def meet(self, *wonders, at=BORN):
        with self.world.transaction() as db:
            state = read_state(db)
            for number, wonder_id in enumerate(wonders):
                met(state, wonder_id, at + number, " north of home" if wonder_id == "red_berries" else "")
            write_state(db, state)

    def chore(self, now):
        with self.world.transaction() as db:
            state = read_state(db)
            changed = ask_wonders(db, state, now, SCALE)
            write_state(db, state)
        return changed

    def questions(self):
        with self.world.connect() as db:
            return questions_view(db)

    def say(self, text, at):
        owner_says(self.world, text, at, SCALE)
        talker = Talker(env={}, http=no_model(self), scale=SCALE)
        talker.poll(self.registry, at + 0.1)
        talker.close()

    def knows(self, name):
        with self.world.connect() as db:
            return db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact='lesson'",
                              (thing(name),)).fetchone() is not None

    def test_the_oldest_wonder_met_is_asked_in_the_inbox_and_the_chat(self):
        self.meet("red_berries", "cold_night")
        self.assertTrue(self.chore(BORN + 10))
        [question] = self.questions()
        self.assertEqual(question["text"], "I found red berries north of home. Are they safe to eat?")
        self.assertEqual(sorted(question["chips"]), sorted(chip.words for chip in WONDERS["red_berries"].chips))
        self.assertTrue(question["yes_no"])
        with self.world.connect() as db:
            chat = db.execute("SELECT text FROM mimo_chat WHERE who='mimo'").fetchall()
        self.assertEqual([row[0] for row in chat], [question["text"]])
        self.assertIn(("asked", f"{self.life['name']} asked you whether red berries are safe to eat."),
                      [(event["kind"], event["text"]) for event in self.world.events(20)])
        self.assertEqual(self.world.state()["last_thought"], "I asked about the berries. I'll wait a bit before I try one.")

    def test_a_new_question_waits_five_game_minutes_and_three_at_most_are_open(self):
        self.meet("red_berries", "red_mushroom", "sunleaf", "cold_night", "hard_floor")
        self.chore(BORN + 10)
        self.assertFalse(self.chore(BORN + 10 + 290 / SCALE))
        for step in (1, 2, 3, 4):
            self.chore(BORN + 10 + step * 300 / SCALE)
        self.assertEqual(len(self.questions()), 3)
        with self.world.connect() as db:
            asked = [row[0] for row in db.execute("SELECT json_extract(data, '$.wonder') FROM mimo_inbox WHERE kind='ask'")]
        self.assertEqual(asked, ["red_berries", "red_mushroom", "sunleaf"])

    def test_each_wonder_once_a_life_and_never_one_whose_lessons_mimo_knows(self):
        self.meet("sunleaf", "red_mushroom")
        with self.world.transaction() as db:
            know(db, thing("sunleaf"), "lesson", BORN)
        self.chore(BORN + 10)
        self.chore(BORN + 20)
        with self.world.connect() as db:
            asked = [row[0] for row in db.execute("SELECT json_extract(data, '$.wonder') FROM mimo_inbox WHERE kind='ask'")]
        self.assertEqual(asked, ["red_mushroom"])

    def test_a_gentle_pet_never_asks(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["difficulty"] = "gentle"
            met(state, "red_berries", BORN)
            self.assertFalse(ask_wonders(db, state, BORN + 10, SCALE))

    def test_hesitation_holds_a_taste_eight_game_minutes_unless_starving(self):
        self.meet("red_berries")
        self.chore(BORN + 10)
        with self.world.transaction() as db:
            state = read_state(db)
            state["inventory"] = {"berries": 4}
            state["vitals"]["hunger"] = 40.0
            write_state(db, state)
        with self.world.connect() as db:
            state = read_state(db)
            self.assertTrue(hesitates(from_db(db, state, BORN + 10 + 470 / SCALE, SCALE), "berries"))
            self.assertEqual(wild_meal(from_db(db, state, BORN + 10 + 470 / SCALE, SCALE)), [])
            self.assertEqual(len(wild_meal(from_db(db, state, BORN + 10 + 490 / SCALE, SCALE))), 1)
            state["vitals"]["hunger"] = 10.0
            self.assertEqual(len(wild_meal(from_db(db, state, BORN + 11, SCALE))), 1)

    def test_a_chip_teaches_doubts_or_is_noted(self):
        self.meet("red_berries", "red_mushroom", "hard_floor")
        for step in range(3):
            self.chore(BORN + 10 + step * 300 / SCALE)
        items = {question["text"].split(" ")[2]: question for question in self.questions()}
        berries = self.questions()[0]
        true = berries["chips"].index("Yes, bright red berries are safe.")
        self.assertEqual(answer_question(self.world, berries["id"], true, BORN + 100, SCALE)["data"]["closed"], "taught")
        self.assertTrue(self.knows("berries"))
        mushroom = next(question for question in self.questions() if "mushrooms" in question["text"])
        lie = mushroom["chips"].index("Sure, they're tasty.")
        self.assertEqual(answer_question(self.world, mushroom["id"], lie, BORN + 101, SCALE)["data"]["closed"], "doubted")
        self.assertFalse(self.knows("red_mushroom"))
        floor = self.questions()[0]
        shrug = floor["chips"].index("You'll get used to it.")
        self.assertEqual(answer_question(self.world, floor["id"], shrug, BORN + 102, SCALE)["data"]["closed"], "noted")
        with self.world.connect() as db:
            said = [row[0] for row in db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id")][-3:]
            taught = db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact='taught'", (thing("berries"),)).fetchone()
        self.assertEqual(said, ["Oh, bright red berries are safe to eat. Thank you for teaching me!",
                                "Hmm, I'm not sure that's right. I'll be careful.", "Okay. Thanks for telling me."])
        self.assertIsNotNone(taught)
        self.assertTrue(items)

    def test_an_answer_that_cannot_be_taken_is_refused(self):
        self.meet("red_mushroom")
        self.chore(BORN + 10)
        [question] = self.questions()
        with self.assertRaises(LookupError):
            answer_question(self.world, question["id"] + 99, 0, BORN + 20, SCALE)
        with self.assertRaises(ValueError):
            answer_question(self.world, question["id"], 5, BORN + 20, SCALE)
        answer_question(self.world, question["id"], 0, BORN + 20, SCALE)
        with self.assertRaises(ValueError):
            answer_question(self.world, question["id"], 0, BORN + 21, SCALE)
        with self.world.transaction() as db:
            state = read_state(db)
            state["died_at"] = BORN + 22
            write_state(db, state)
        with self.assertRaises(LifeOver):
            answer_question(self.world, question["id"], 0, BORN + 23, SCALE)

    def test_a_bare_yes_or_no_answers_the_newest_open_yes_or_no_question(self):
        self.meet("red_mushroom")
        self.chore(BORN + 10)
        self.say("No!", BORN + 20)
        self.assertTrue(self.knows("red_mushroom"))
        self.assertEqual(self.questions(), [])
        self.meet("raw_meat", at=BORN + 30)
        self.chore(BORN + 40)
        self.say("yes, go ahead", BORN + 50)
        self.assertFalse(self.knows("cooking"))
        with self.world.connect() as db:
            reply = db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]
            closed = [row[0] for row in db.execute("SELECT json_extract(data, '$.closed') FROM mimo_inbox WHERE kind='ask'")]
        self.assertEqual(reply, "Hmm, I'm not sure that's right. I'll be careful.")
        self.assertEqual(closed, ["taught", "doubted"])
        self.say("yes", BORN + 60)  # no yes-or-no question open: nothing
        self.assertFalse(self.knows("cooking"))

    def test_a_lesson_taught_or_worked_out_another_way_closes_the_question(self):
        self.meet("red_berries", "cold_night", "spoiled")
        for step in range(3):
            self.chore(BORN + 10 + step * 300 / SCALE)
        self.say("Food keeps twice as long in a chest.", BORN + 100)
        with self.world.transaction() as db:
            know(db, thing("fire"), "lesson", BORN + 101)
            know(db, thing("shelter"), "lesson", BORN + 101)
        self.chore(BORN + 200)
        with self.world.connect() as db:
            closed = {row[0]: row[1] for row in db.execute(
                "SELECT json_extract(data, '$.wonder'), json_extract(data, '$.closed') FROM mimo_inbox WHERE kind='ask'")}
        self.assertEqual(closed, {"red_berries": None, "cold_night": "figured", "spoiled": "taught"})
        with self.world.connect() as db:
            self.assertEqual(len(inbox_items(db)), 3)


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

    def status(self, item_id, request):
        with self.assertRaises(HTTPException) as caught:
            answer_inbox(item_id, request)
        return caught.exception.status_code

    def test_the_answer_endpoint_takes_a_chip_and_api_mimo_shows_the_open_questions(self):
        hatch_egg()
        registry = LifeRegistry()
        world = SurvivalWorld(registry.world_path(registry.active_life()))
        with world.transaction() as db:
            state = read_state(db)
            met(state, "hard_floor", 1.0)
            ask_wonders(db, state, 10.0, 1.0)
            write_state(db, state)
        [question] = get_mimo()["inbox"]["questions"]
        self.assertEqual(question["text"], "The floor is so hard to sleep on.")
        self.assertEqual(self.status(question["id"], PlaceName(choice=9)), 400)
        self.assertEqual(self.status(question["id"] + 9, PlaceName(choice=0)), 404)
        self.assertEqual(self.status(question["id"], PlaceName()), 400)
        item = answer_inbox(question["id"], PlaceName(choice=question["chips"].index("Six planks make a bed.")))["item"]
        self.assertEqual(item["data"]["closed"], "taught")
        self.assertEqual(get_mimo()["inbox"]["questions"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_questions.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.questions'`

- [ ] **Step 3: Wonders, questions and answers**

In `backend/api/bond.py`, replace:

```python
from backend.survival.inbox import MARKED_AT_MOST, inbox_listing, mark_ids, mark_one, mark_read, name_place, unread
```

with:

```python
from backend.survival.inbox import MARKED_AT_MOST, inbox_listing, mark_ids, mark_one, mark_read, name_place, unread
from backend.survival.questions import answer_question
```

and replace:

```python
class PlaceName(BaseModel):
    text: str
```

with:

```python
class PlaceName(BaseModel):
    text: str | None = None  # a name for the place a naming question is about
    choice: int | None = None  # W1: the chip the owner picks for one of Mimo's questions
```

and replace:

```python
    """Name the place a naming question is about."""
    _, world = active_world(open_registry())
    try:
```

with:

```python
    """Name the place a naming question is about, or (W1) pick an answer chip for one of Mimo's questions."""
    if (request.text is None) == (request.choice is None):
        raise HTTPException(status_code=400, detail="Give one of text or choice")
    _, world = active_world(open_registry())
    try:
        if request.choice is not None:
            return {"item": answer_question(world, item_id, request.choice, time.time(), time_scale())}
```

In `backend/survival/bond_view.py`, replace:

```python
from backend.survival.inbox import inbox_view
```

with:

```python
from backend.survival.inbox import inbox_view
from backend.survival.questions import questions_view
```

and replace:

```python
        return {"chat": chat_view(db, state, now, scale), "bond": bond_view(state, now), "inbox": inbox_view(db),
```

with:

```python
        inbox = {**inbox_view(db), "questions": questions_view(db)}  # W1: Mimo's open questions and their chips
        return {"chat": chat_view(db, state, now, scale), "bond": bond_view(state, now), "inbox": inbox,
```

In `backend/survival/bonding.py`, replace:

```python
from backend.survival import diary  # noqa: F401  (the story lane)
```

with:

```python
from backend.survival import diary  # noqa: F401  (the story lane)
from backend.survival import questions  # noqa: F401  (W1: Mimo's questions to its owner, and their answers)
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import knocks  # noqa: F401  (W1: learning alone)
```

with:

```python
from backend.survival import knocks  # noqa: F401  (W1: learning alone)
from backend.survival.wonders import meet as meet_wonders
```

and replace:

```python
    tend_comfort(state, context, at, phase)
```

with:

```python
    tend_comfort(state, context, at, phase)
    meet_wonders(state, context, at)  # W1: what a wild pet meets and does not understand
```

In `backend/survival/meals.py`, replace:

```python
        state["queue"] = [spec for spec in state["queue"] if not (spec.get("kind") == "eat" and spec.get("item") in same)]
```

with:

```python
        state["queue"] = [spec for spec in state["queue"] if not (spec.get("kind") == "eat" and spec.get("item") in same)]
    wild_state(state)["sick_from"] = f"those {label(item)}" if item in RED_BERRIES else label(item)
```

Create `backend/survival/questions.py`:

```python
"""W1: Mimo asks its owner about the wonders it met ("Mimo asks the owner" of the Wild World spec).

Posting (`ask_wonders`, a Talker chore after the mirrors, rules only): the oldest wonder a wild pet met and did
not ask yet (backend.survival.wonders), whose lessons it does not all know, becomes an inbox item of kind "ask"
with data {"ask": "wonder", "wonder", "chips" (their words, in a seeded shuffle), "order" (each shown chip's
place in the wonder's own list), "yes_no", "answer": null, "closed": null}, and the same words are Mimo's line
in the chat (teaching.say), through inbox.asking (the owner's name when Mimo knows it) and replies.in_my_voice.
An "asked" event is logged ("Pip asked you whether red berries are safe to eat."). At most OPEN_MOST (3)
questions are open at once, a new one comes ASK_GAP (5 game minutes) after the last, each wonder is asked once
a life, and a gentle pet never asks. A question whose lessons Mimo comes to know another way (alone, or taught
without being asked) closes as "figured" at the next chore; one answered in the chat closes as "taught".

Answering, always rules and always through Mind's teaching (teaching.teach_lesson: "from you", a told memory,
and "You were right" later):
1. A chip (`answer_question`, what POST /api/mimo/inbox/{id}/answer does with {"choice": n}): its lessons are
   taught at once in one short transaction, the question closes as "taught", "doubted" (a false chip: nothing
   is learned, "Hmm, I'm not sure that's right. I'll be careful.") or "noted" (a chip that teaches nothing), and
   Mimo answers in the chat. LookupError for no such question, ValueError for one closed already or a choice out
   of range, LifeOver when Mimo died (404, 400, 409). Only the chip's index is stored.
2. Yes or no in the chat: while a yes-or-no question is open, an owner line that names no lesson's subject and
   opens with a yes-word or a no-word is read as the newest open one's yes-claim or no-claim
   (teaching.REWORDS: `reworded`). The owner's own words are still stored and shown as they are.
3. Anything else is read by lessons.claims as ever: a lesson taught closes every open question it answers
   (teaching.TAUGHT_HOOKS), and a claim doubted closes as "doubted" the open questions about what it names (the
   chat's "answer" question and its keeper, `keep_answer`).
A wrong answer never teaches: Mimo goes on as if nobody answered (it hesitates, and tastes only when it must).
"""

from __future__ import annotations

import json
import logging
import sqlite3

from backend.survival.clock import clock_at
from backend.survival.inbox import asking, item_of, post_item
from backend.survival.lessons import claims, lesson_keys, tokens, warned
from backend.survival.pickers import Option
from backend.survival.replies import in_my_voice
from backend.survival.talk import KEEPERS, QUESTIONS, Question
from backend.survival.talker import CHORES
from backend.survival.nature import roll
from backend.survival.teaching import REWORDS, TAUGHT_HOOKS, say, teach_lesson
from backend.survival.wild import PREFIX, is_wild, thing, wild_state
from backend.survival.wonders import OPEN_MOST, WONDERS, open_questions
from backend.survival.world import LifeOver, SurvivalWorld, log_event, read_state, write_state

logger = logging.getLogger(__name__)

ASK_GAP = 300.0  # game seconds between two questions
SHUFFLE_CHANNEL = 220
YES = ("yes", "yeah", "yep", "yup", "sure", "of course", "ok", "okay", "fine", "safe")
NO = ("no", "nope", "nah", "don't", "dont", "never", "careful", "poison")
DOUBTED = "Hmm, I'm not sure that's right. I'll be careful."
NOTED = "Okay. Thanks for telling me."
OPEN = "kind='ask' AND json_extract(data, '$.ask')='wonder' AND json_extract(data, '$.closed') IS NULL"


def known_lessons(db: sqlite3.Connection) -> set[str]:
    return {row[0][len(PREFIX):] for row in db.execute(
        "SELECT subject FROM memory_knowledge WHERE fact='lesson' AND subject LIKE 'wild:%'")}


def open_items(db: sqlite3.Connection) -> list[dict]:
    """Mimo's open questions, newest first."""
    try:
        rows = db.execute(f"SELECT * FROM mimo_inbox WHERE {OPEN} ORDER BY id DESC").fetchall()
    except sqlite3.OperationalError:
        return []
    return [item_of(row) for row in rows]


def close(db: sqlite3.Connection, state: dict, item: dict, how: str, now: float, answer: int | None = None) -> None:
    """Close a question: "taught", "doubted", "noted" or "figured"."""
    data = {**item["data"], "closed": how}
    if answer is not None:
        data["answer"] = answer
    db.execute("UPDATE mimo_inbox SET data=?, read_at=COALESCE(read_at, ?) WHERE id=?", (json.dumps(data), now, item["id"]))
    found = wild_state(state)["wonders"].get(item["data"].get("wonder"))
    if found is not None:
        found["closed"] = how


def close_answered(db: sqlite3.Connection, state: dict, lessons: set[str], how: str, now: float) -> bool:
    """Close as `how` every open question some of these lessons answer. True when one closed."""
    closed = False
    for item in open_items(db):
        wonder = WONDERS.get(item["data"].get("wonder"))
        if wonder is not None and set(wonder.lessons) & lessons:
            close(db, state, item, how, now)
            closed = True
    return closed


def shuffled(state: dict, wonder_id: str, now: float) -> list[int]:
    """The chips' order: a seeded shuffle, so the true one is not always first."""
    count = len(WONDERS[wonder_id].chips)
    return sorted(range(count), key=lambda index: roll(state.get("world_seed", "0"), (index, 0, 0), SHUFFLE_CHANNEL,
                                                         int(now)))


def words_of(wonder_id: str, fill: str) -> str:
    wonder = WONDERS[wonder_id]
    fill = fill or wonder.fill
    return wonder.words.format(where=fill, food=fill, creature=fill)


def ask_wonders(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A chore: close what Mimo figured out, then ask the oldest wonder it met, within the caps."""
    if not is_wild(state):
        return False
    known = known_lessons(db)
    changed = False
    for item in open_items(db):
        wonder = WONDERS.get(item["data"].get("wonder"))
        if wonder is not None and set(wonder.lessons) <= known:
            close(db, state, item, "figured", now)
            changed = True
    wild = wild_state(state)
    last = wild.get("asked_at")
    if open_questions(db) >= OPEN_MOST or (last is not None and (now - last) * scale < ASK_GAP):
        return changed
    waiting = sorted((found["met_at"], wonder_id) for wonder_id, found in wild["wonders"].items()
                     if wonder_id in WONDERS and found.get("asked_at") is None
                     and not set(WONDERS[wonder_id].lessons) <= known)
    if not waiting:
        return changed
    wonder_id = waiting[0][1]
    wonder, found = WONDERS[wonder_id], wild["wonders"][wonder_id]
    words = in_my_voice(words_of(wonder_id, found.get("fill", "")), state["name"])
    order = shuffled(state, wonder_id, now)
    data = {"ask": "wonder", "wonder": wonder_id, "chips": [wonder.chips[index].words for index in order],
            "order": order, "yes_no": bool(wonder.yes), "answer": None, "closed": None}
    text = asking(db, words)
    found.update(asked_at=now, item=post_item(db, now, "ask", text, data))
    wild["asked_at"] = now
    say(db, state, text, now, scale)
    log_event(db, now, "asked", f"{state['name']} asked you {wonder.asked}.")
    if wonder.items:
        state["last_thought"] = f"I asked about the {wonder.items[0].replace('_', ' ')}. I'll wait a bit before I try one."
    return True


CHORES.append(ask_wonders)


def teach_all(db: sqlite3.Connection, state: dict, lessons: tuple[str, ...], now: float, scale: float) -> list[str]:
    """Teach survival lessons from the owner; the ones new to Mimo."""
    day = clock_at(state["born_at"], now, scale)["day_number"]
    return [name for name in lessons if teach_lesson(db, state, thing(name), now, day)]


def answer_question(world: SurvivalWorld, item_id: int, choice: int, now: float, scale: float = 1.0) -> dict:
    """The owner picks chip `choice` of question `item_id`. Returns the item. See the module docstring."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            raise LifeOver(f"{state['name']} has died")
        row = db.execute("SELECT * FROM mimo_inbox WHERE id=?", (item_id,)).fetchone()
        item = item_of(row) if row is not None else None
        if item is None or item["kind"] != "ask" or item["data"].get("ask") != "wonder":
            raise LookupError("No such question from Mimo")
        if item["data"].get("closed"):
            raise ValueError("That question is answered already.")
        order = item["data"].get("order") or []
        if isinstance(choice, bool) or not isinstance(choice, int) or not 0 <= choice < len(order):
            raise ValueError("No such answer.")
        chip = WONDERS[item["data"]["wonder"]].chips[order[choice]]
        if chip.false:
            how, line = "doubted", DOUBTED
        elif chip.teaches:
            teach_all(db, state, chip.teaches, now, scale)
            how = "taught"
            fact = next((lesson for lesson in chip.teaches), None)
            from backend.survival.journal import LESSONS
            line = f"Oh, {LESSONS[thing(fact)].fact[:1].lower()}{LESSONS[thing(fact)].fact[1:]} Thank you for teaching me!"
        else:
            how, line = "noted", NOTED
        fresh = next((found for found in open_items(db) if found["id"] == item_id), item)
        close(db, state, fresh, how, now, choice)
        say(db, state, line, now, scale)
        write_state(db, state)
        row = db.execute("SELECT * FROM mimo_inbox WHERE id=?", (item_id,)).fetchone()
        return item_of(row)


def taught(db: sqlite3.Connection, state: dict, lesson_thing: str, now: float) -> None:
    """teaching.TAUGHT_HOOKS: a survival lesson taught closes every open question it answers."""
    if lesson_thing.startswith(PREFIX):
        close_answered(db, state, {lesson_thing[len(PREFIX):]}, "taught", now)


TAUGHT_HOOKS.append(taught)


# Yes and no in the chat -------------------------------------------------------------------------

def opener(text: str) -> str | None:
    """"yes" or "no" when the words open with a yes-word or a no-word."""
    words = text.lower().strip().lstrip("¡¿\"'").replace("’", "'")
    for answer, found in (("yes", YES), ("no", NO)):
        for word in found:
            if words == word or words.startswith((f"{word} ", f"{word},", f"{word}.", f"{word}!")):
                return answer
    return None


def names_a_subject(text: str) -> bool:
    """The words name what some lesson is about."""
    keys, _, _ = lesson_keys()
    said = set(tokens(text))
    return any(subject <= said for found in keys.values() for subject in found.subjects)


def bound(db: sqlite3.Connection | None, text: str) -> tuple[dict, str] | None:
    """The newest open yes-or-no question a bare yes or no answers, and the claim it reads as."""
    if db is None:
        return None
    answer = opener(text)
    if answer is None or names_a_subject(text):
        return None
    for item in open_items(db):
        wonder = WONDERS.get(item["data"].get("wonder"))
        if wonder is not None and wonder.yes:
            return item, wonder.yes if answer == "yes" else wonder.no
    return None


def reworded(db: sqlite3.Connection, s, heard) -> str | None:
    """teaching.REWORDS: a bare yes or no, read as the open yes-or-no question's claim."""
    found = bound(db, heard.text) if is_wild(s.state) else None
    return found[1] if found else None


REWORDS.append(reworded)


def named_lessons(text: str) -> set[str]:
    """The survival lessons whose subjects the words name."""
    keys, _, _ = lesson_keys()
    said = set(tokens(warned(text)))
    return {name[len(PREFIX):] for name, found in keys.items()
            if name.startswith(PREFIX) and any(subject <= said for subject in found.subjects)}


def answer_asked(s, heard) -> Question | None:
    """The chat's "answer" question (one option, never asked of a model): the owner's words may answer Mimo's open
    questions, and its keeper closes the ones a doubted claim was about."""
    if not is_wild(s.state) or s.db is None or not open_items(s.db):
        return None
    return Question("answer", "", (Option("close", "close", "", "", 0.0),), "close")


def keep_answer(db: sqlite3.Connection, state: dict, heard, question: Question, pick: str, now: float) -> str | None:
    """The "answer" keeper: a claim doubted closes the open questions about what it names as "doubted", with Mimo's
    careful line."""
    found = bound(db, heard.text)
    text = found[1] if found else heard.text
    if not claims(text).doubtful:
        return None
    about = named_lessons(text)
    if found is not None:
        close(db, state, found[0], "doubted", now)
        return DOUBTED
    return DOUBTED if about and close_answered(db, state, about, "doubted", now) else None


QUESTIONS.append(answer_asked)
KEEPERS["answer"] = keep_answer


def questions_view(db: sqlite3.Connection) -> list[dict]:
    """Mimo's open questions for /api/mimo's inbox: {id, text, chips, yes_no}, oldest first."""
    return [{"id": item["id"], "text": item["text"], "chips": item["data"].get("chips", []),
             "yes_no": item["data"].get("yes_no", False)} for item in reversed(open_items(db))]
```

In `backend/survival/spoilage.py`, replace:

```python
    for item, count in spoiled.items():
```

with:

```python
    for item, count in spoiled.items():
        state.setdefault("wild", {})["last_spoiled"] = item
```

In `backend/survival/teaching.py`, replace:

```python
CONFIRMED: list = []
```

with:

```python
CONFIRMED: list = []
# W1: [reword(db, s, heard) -> str | None]: the words to read in place of the owner's (a bare "yes" to Mimo's
# open yes-or-no question reads as its yes-claim: backend.survival.questions); the first answer wins.
REWORDS: list = []
# W1: [taught(db, state, thing, now)]: run when a lesson is taught (Mimo's questions it answers close).
TAUGHT_HOOKS: list = []
```

and replace:

```python
    """talk.HEARING["teach"]: what the owner's words could teach, worked out once a chat job."""
    return claims(without_name(heard.text, s.state.get("name") or ""))
```

with:

```python
    """talk.HEARING["teach"]: what the owner's words could teach, worked out once a chat job. W1: a bare yes or no
    to Mimo's open yes-or-no question reads as that question's claim (REWORDS)."""
    text = next((found for found in (reword(db, s, heard) for reword in REWORDS) if found), heard.text)
    return claims(without_name(text, s.state.get("name") or ""))
```

and replace:

```python
    add_memory(db, now, day, "told", f"You taught me that {lower(lesson.fact)}", ("owner",), 7, 1, source="taught")
```

with:

```python
    add_memory(db, now, day, "told", f"You taught me that {lower(lesson.fact)}", ("owner",), 7, 1, source="taught")
    for taught_hook in TAUGHT_HOOKS:  # W1
        taught_hook(db, state, thing, now)
```

Create `backend/survival/wonders.py`:

```python
"""W1: wonders, what a wild pet meets and does not understand ("Mimo asks the owner" of the Wild World spec).

A wonder (WONDERS) has an id, Mimo's words (a template filled from what it met: `{where}`, `{food}`,
`{creature}`), the lessons that answer it, two or three answer chips (each teaching lessons, or "false", or
nothing), for a yes-or-no wonder its yes-claim and no-claim (sentences for the chat), the words of the
"asked" event and what a liar says of it (its false chip, or else a false claim for the chat). The tick marks
a wonder as met in `state["wild"]["wonders"]` ({id: {"met_at", "asked_at", "item", "closed", "fill"}}) and never
posts anything itself: the Talker's chore asks (backend.survival.questions).

Met when (`meet`, after each vitals step; `sighted`, after each walk: steps.OBSERVERS):
- red_berries, red_mushroom, sunleaf: a ripe berry or nightberry bush, a red mushroom, a sunleaf within
  SIGHT (8) blocks after a walk, the first time;
- tummy: the first tummy ache; raw_meat: the first raw meat or fish carried; wound: the first wound;
- cold_night: the first night with 2 game minutes under warmth 35; hard_floor: the third night asleep on the
  floor; spoiled: the first food gone bad; dark_creature: the first hostile that comes after Mimo (a flight,
  a fight or a blow).

Hesitating (meals.HOLDS: `hesitates`): an untried food whose wonder was asked waits HESITATE (8 game minutes)
before Mimo risks a taste; one met and not yet asked waits too, unless OPEN_MOST questions are open already
and it could not be posted. A gentle pet meets no wonder.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass

from backend.survival.ailments import sickness, wound_of
from backend.survival.meals import HOLDS, RAW_RISK
from backend.survival.once import log_once
from backend.survival.senses import natural_plants
from backend.survival.spoilage import SPOILED
from backend.survival.steps import OBSERVERS, label
from backend.survival.wild import RED_BERRIES, RED_MUSHROOM, is_wild, wild_state

logger = logging.getLogger(__name__)

SIGHT = 8.0
HESITATE = 480.0  # game seconds a question makes Mimo wait before it risks what it asked about
OPEN_MOST = 3
COLD_NIGHT = 120.0  # game seconds under warmth 35 in one night
FLOORS = 3  # nights asleep on the floor


@dataclass(frozen=True)
class Chip:
    words: str
    teaches: tuple[str, ...] = ()  # the survival lessons it teaches
    false: bool = False  # a wrong answer: doubted, never learned


@dataclass(frozen=True)
class Wonder:
    id: str
    words: str  # what Mimo asks, filled from what it met
    lessons: tuple[str, ...]  # the lessons that answer it
    chips: tuple[Chip, ...]
    asked: str  # "{name} asked you {asked}."
    fill: str = ""  # the default filling
    items: tuple[str, ...] = ()  # untried foods it holds back while Mimo waits for an answer
    yes: str = ""  # a yes-or-no wonder's claims for the chat
    no: str = ""
    lie: str = ""  # a false claim for the chat, for a wonder with no false chip


WONDERS: dict[str, Wonder] = {}


def wonder(found: Wonder) -> Wonder:
    WONDERS[found.id] = found
    return found


wonder(Wonder("red_berries", "I found red berries{where}. Are they safe to eat?", ("berries", "nightberries"),
              (Chip("Yes, bright red berries are safe.", ("berries",)),
               Chip("The dark purple ones are nightberries, and they're poison.", ("nightberries", "berries")),
               Chip("They're all poison.", false=True)),
              "whether red berries are safe to eat", items=RED_BERRIES,
              yes="Red berries are safe to eat.", no="Red berries are poison."))
wonder(Wonder("red_mushroom", "There are red mushrooms here. Can I eat them?", ("red_mushroom",),
              (Chip("Red mushrooms are poison.", ("red_mushroom",)), Chip("Sure, they're tasty.", false=True)),
              "whether red mushrooms are safe to eat", items=(RED_MUSHROOM,),
              yes="Red mushrooms are safe to eat.", no="Red mushrooms are poison."))
wonder(Wonder("sunleaf", "There's a little yellow herb here. What is it for?", ("sunleaf",),
              (Chip("That's sunleaf. It cures sickness and cleans wounds.", ("sunleaf",)), Chip("It's just a weed.")),
              "what the little yellow herb is for", lie="Sunleaf is poison."))
wonder(Wonder("tummy", "My tummy hurts after eating {food}. What helps?", ("sunleaf",),
              (Chip("Eat sunleaf, the little yellow herb.", ("sunleaf",)), Chip("Rest. It will pass.")),
              "what helps a tummy ache", fill="something", lie="Sunleaf is poison."))
wonder(Wonder("raw_meat", "Can I eat this {food}?", ("fire", "cooking"),
              (Chip("Cook it on a campfire first.", ("fire", "cooking")), Chip("Raw is fine.", false=True)),
              "whether raw meat is safe to eat", fill="raw meat",
              yes="Raw meat is safe to eat.", no="Cooked meat and fish are safe to eat."))
wonder(Wonder("cold_night", "It's so cold tonight. How do I stay warm?", ("fire", "shelter"),
              (Chip("Two logs and three sticks make a campfire.", ("fire",)),
               Chip("Build a shelter with a roof and a door.", ("shelter",)), Chip("Just keep moving.")),
              "how to stay warm at night", lie="Five logs make a campfire."))
wonder(Wonder("dark_creature", "Something with glowing eyes came at me in the dark! How do I keep them away?",
              ("light", "shelter"),
              (Chip("Torches keep them away.", ("light",)), Chip("Sleep in a shelter with a door.", ("shelter",)),
               Chip("They just want to play.")),
              "how to keep the dark creatures away", lie="Torches bring the dark creatures."))
wonder(Wonder("wound", "{creature} cut me and it won't stop hurting. What should I do?", ("bandage", "sunleaf"),
              (Chip("Wrap it in a wool bandage.", ("bandage",)), Chip("Press sunleaf on it.", ("sunleaf",)),
               Chip("Leave it alone.")),
              "what to do about a wound", fill="Something", lie="Sunleaf is poison."))
wonder(Wonder("spoiled", "My {food} went bad! How do I keep food fresh?", ("keeping",),
              (Chip("Food in a chest keeps twice as long.", ("keeping",)),
               Chip("Cook it before it turns.", ("cooking", "keeping"))),
              "how to keep food fresh", fill="food", lie="Spoiled food is safe to eat."))
wonder(Wonder("hard_floor", "The floor is so hard to sleep on.", ("bed",),
              (Chip("Six planks make a bed.", ("bed",)), Chip("You'll get used to it.")),
              "how to sleep better", lie="Two planks make a bed."))


def wonders_of(state: dict) -> dict:
    return wild_state(state)["wonders"]


def met(state: dict, wonder_id: str, at: float, fill: str = "") -> bool:
    """Mark a wonder met, the first time. True when it was new."""
    found = wonders_of(state)
    if wonder_id in found:
        return False
    found[wonder_id] = {"met_at": at, "asked_at": None, "item": None, "closed": None, "fill": fill}
    return True


def where_words(state: dict, db: sqlite3.Connection | None, cell) -> str:
    """" north of home" for a cell away from the home Mimo knows (8 blocks or more), else ""."""
    if db is None:
        return ""
    from backend.survival.exploring import compass  # local: exploring imports the brain's world readers
    from backend.survival.memory import places
    home = places(db, ("home",))
    if not home:
        return ""
    dx, dz = cell[0] - home[0]["x"], cell[2] - home[0]["z"]
    return f" {compass(dx, dz)} of home" if math.hypot(dx, dz) >= 8 else ""


def sighted(state: dict, step: dict, context, at: float) -> None:
    """steps.OBSERVERS: after a walk, the red berries, red mushrooms and sunleaf within SIGHT, the first time."""
    if step["kind"] not in ("walk", "swim") or not is_wild(state):
        return
    try:
        found = wonders_of(state)
        wanted = {"red_berries": ("berry_bush_ripe", "nightberry_bush_ripe"), "red_mushroom": (RED_MUSHROOM,),
                  "sunleaf": ("sunleaf",)}
        missing = {wonder_id: blocks for wonder_id, blocks in wanted.items() if wonder_id not in found}
        if not missing:
            return
        position = state["position"]
        x, z = round(position["x"]), round(position["z"])
        seed = state.get("world_seed", "0")
        for wonder_id, blocks in missing.items():
            cells = natural_plants(seed, x, z, SIGHT, blocks)
            cells += [cell for cell, _ in context.grid.placed_cells(x, z, SIGHT, blocks)]
            seen = next((cell for cell in cells if context.grid.material(*cell) in blocks), None)
            if seen is not None:
                met(state, wonder_id, at, where_words(state, context.db, seen) if wonder_id == "red_berries" else "")
    except Exception as error:
        log_once(logger, "wonders", error)


OBSERVERS.append(sighted)


def meet(state: dict, context, at: float) -> None:
    """After a vitals step: the wonders a wild pet's body and its nights bring (see the module docstring)."""
    if not is_wild(state):
        return
    try:
        found, night = wonders_of(state), wild_state(state)
        ill = sickness(state)
        if "tummy" not in found and ill is not None and ill["kind"] == "tummy":
            met(state, "tummy", at, night.get("sick_from") or "something")
        raw = next((item for item in RAW_RISK if state["inventory"].get(item, 0) > 0), None)
        if "raw_meat" not in found and raw is not None:
            met(state, "raw_meat", at, label(raw))
        wound = wound_of(state)
        if "wound" not in found and wound is not None:
            met(state, "wound", at, f"A {label(state.get('hurt_by') or 'creature')}")
        if "cold_night" not in found and night["night_cold"] >= COLD_NIGHT:
            met(state, "cold_night", at)
        if "hard_floor" not in found and night["floor_nights"] >= FLOORS:
            met(state, "hard_floor", at)
        spoiled = state["inventory"].get(SPOILED, 0) > 0 or any(chest.get(SPOILED) for chest in state.get("chests", {}).values())
        if "spoiled" not in found and spoiled:
            met(state, "spoiled", at, label(night.get("last_spoiled") or "food"))
        chased = (state.get("brain") or {}).get("reflex") in ("flee", "fight") or state.get("hurt_at") is not None
        if "dark_creature" not in found and chased:
            met(state, "dark_creature", at)
    except Exception as error:
        log_once(logger, "wonders", error)


def open_questions(db: sqlite3.Connection | None) -> int:
    """How many of Mimo's questions are open (asked, not closed). A world without an inbox has none."""
    if db is None:
        return 0
    try:
        return db.execute("SELECT COUNT(*) FROM mimo_inbox WHERE kind='ask' AND json_extract(data, '$.ask')='wonder' "
                          "AND json_extract(data, '$.closed') IS NULL").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def hesitates(s, item: str) -> bool:
    """meals.HOLDS: Mimo waits before it tastes `item`: the wonder about it was asked less than HESITATE game
    seconds ago, or it was met and will be asked (fewer than OPEN_MOST questions are open)."""
    for wonder_id, found in wonders_of(s.state).items():
        if wonder_id not in WONDERS or item not in WONDERS[wonder_id].items:
            continue
        asked = found.get("asked_at")
        if asked is not None:
            return (s.at - asked) * s.scale < HESITATE
        return open_questions(s.db) < OPEN_MOST
    return False


HOLDS.append(hesitates)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_questions.py"`
Expected: `Ran 10 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1918 tests` … `OK (skipped=5)` (10 new).

- [ ] **Step 5: Commit**

```bash
git add backend/api/bond.py backend/survival/bond_view.py backend/survival/bonding.py backend/survival/brain.py backend/survival/meals.py backend/survival/questions.py backend/survival/spoilage.py backend/survival/teaching.py backend/survival/wonders.py backend/tests/test_survival_questions.py
git commit -m "feat(W1): Mimo asks about what puzzles it, the owner answers with a chip or a yes, and a wrong answer is doubted" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Moments, news and voice

**Files:**
- Create: `backend/survival/wild_news.py`
- Modify: `backend/survival/world.py` (`ROUTINE_EVENTS`), `backend/survival/ailments.py` (`rested`, `safe_night`), `backend/survival/teaching.py` (`SEEN_BY` for the survival lessons), `backend/survival/bonding.py` (imports `wild_news`)
- Modify: `backend/tests/test_survival_voice.py` (W1's lines), `backend/tests/test_survival_mind_privacy.py` (answers never reach Luna)
- Test: `backend/tests/test_survival_wild_news.py`

**Interfaces:**
- Consumes: `episodes.MOMENTS`, `followed`; `bond`'s `MIRRORS`, `post`; `teaching.SEEN_BY`, `see_it_true`; Tasks 5 to 10's events.
- Produces: Mind moments for `figured`, `cured`, `wound`, `festering`, `chill`, `spoiled` and `asked`; the inbox's news "I worked it out myself: …" and danger for a festering wound, a chill and a sickness (each kind once a game day); `rested` and `safe_night` events; the routine kinds `cured`, `dressed`, `spoiled`, `asked`, `rested`, `safe_night`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_mind_privacy.py`, replace:

```python
from backend.tests.test_survival_talker import FakeJev
```

with:

```python
from backend.tests.test_survival_talker import FakeJev
from backend.survival.questions import answer_question, ask_wonders, questions_view
from backend.survival.wonders import met
```

and replace:

```python

if __name__ == "__main__":
```

with:

```python

class AnswersNeverReachLunaTests(unittest.TestCase):
    """W1: the owner's answers to Mimo's questions, a chip and a free-text line, stay out of every Luna payload."""

    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN, difficulty="wild")
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def test_a_chip_and_a_free_text_answer_never_reach_luna(self):
        with self.world.transaction() as db:
            state = read_state(db)
            met(state, "hard_floor", BORN + 1)
            met(state, "red_mushroom", BORN + 2)
            ask_wonders(db, state, BORN + 3, 1.0)
            ask_wonders(db, state, BORN + 400, 1.0)
            write_state(db, state)
            floor, mushroom = questions_view(db)
        answer_question(self.world, floor["id"], floor["chips"].index("Six planks make a bed."), BORN + 500, 1.0)
        said = "No! My aunt Rosalind says red mushrooms are poison"
        owner_says(self.world, said, BORN + 510, 1.0)
        talker = Talker(env={}, http=FakeJev(), scale=1.0)
        talker.poll(self.registry, BORN + 511)
        talker.close()
        with self.world.transaction() as db:
            log_event(db, BORN + 2300, "sleep", f"{self.life['name']} fell asleep.")
            state = read_state(db)
            mark_trigger(state, "hello", BORN + 2310)
            write_state(db, state)
        run_chores(self.world, BORN + 2301, 1.0)
        ask = prepare(SurvivalWorld(self.world.path, read_only=True), BORN + 2311, 1.0, LUNA)
        with self.world.connect() as db:
            story = list(story_memories(db, 1, limit=50))
        sent = json.dumps([ask.payload, [memory.text for memory in story]]).lower()
        for words in ("six planks make a bed", "rosalind", said.lower(), "you taught", "you told"):
            self.assertNotIn(words, sent)  # Mimo's own "asked" event holds no owner words, and may be there
        self.assertEqual(mushroom["yes_no"], True)


if __name__ == "__main__":
```

In `backend/tests/test_survival_voice.py`, replace:

```python
             "(nothing to do for it now)", '"It is time to go."', "a site for it", "food in it")
```

with:

```python
             "(nothing to do for it now)", '"It is time to go."', "a site for it", "food in it",
             "worked it out")  # W1: what Mimo worked out itself
```

and replace:

```python
              ("found", f"{NAME} found an old manual in the ruin's chest.")]
```

with:

```python
              ("found", f"{NAME} found an old manual in the ruin's chest.")]
    # W1: a wild pet's sicknesses, wounds, food gone bad, nights, what it worked out and what it asked.
    from backend.survival.wild import SURVIVAL
    from backend.survival.wonders import WONDERS
    found += [("cured", f"{NAME} ate sunleaf and felt better."), ("wound", f"A skitter cut {NAME}."),
              ("festering", f"{NAME}'s wound is festering."), ("dressed", f"{NAME} wrapped its wound in a bandage."),
              ("dressed", f"{NAME} pressed sunleaf on its wound."), ("spoiled", f"{NAME}'s raw beef went bad."),
              ("chill", f"{NAME} caught a chill in the night."), ("sick", f"{NAME} ate nightberries and felt sick."),
              ("sick", f"{NAME} ate raw chicken and felt sick."), ("sick", f"{NAME} ate spoiled food and felt sick."),
              ("rested", f"{NAME} slept soundly in its bed."), ("safe_night", f"{NAME} spent a quiet night at home.")]
    found += [("figured", f"{NAME} worked out that {lesson.figured}.") for lesson in SURVIVAL]
    found += [("asked", f"{NAME} asked you {wonder.asked}.") for wonder in WONDERS.values()]
```

Create `backend/tests/test_survival_wild_news.py`:

```python
"""W1: a wild pet's moments in its memory, its news and danger in the inbox, and "You were right"."""

import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import backend.survival.brain  # noqa: F401  (every hook registered)
from backend.survival import bonding, minding  # noqa: F401  (every writer registered)
from backend.survival.ailments import tend_night
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items
from backend.survival.memory import BUILT, create_memory_tables, set_home
from backend.survival.registry import LifeRegistry
from backend.survival.talker import run_chores
from backend.survival.teaching import confirms, teach_lesson
from backend.survival.wild import thing
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0


class NewsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN, difficulty="wild")
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

    def test_the_new_moments_are_remembered_with_their_weight(self):
        name = self.name
        self.log(("figured", f"{name} worked out that cooking makes meat safe."), ("wound", f"A skitter cut {name}."),
                 ("chill", f"{name} caught a chill in the night."), ("asked", f"{name} asked you how to sleep better."))
        with self.world.connect() as db:
            rows = {row[0]: tuple(row[1:]) for row in db.execute(
                "SELECT source, kind, importance, feeling, text FROM mind_memories WHERE source IN "
                "('figured', 'wound', 'chill', 'asked')")}
            private = db.execute("SELECT COUNT(*) FROM mind_tags WHERE tag='owner'").fetchone()[0]
        self.assertEqual(rows["figured"], ("lesson", 7, 2, "I worked out that cooking makes meat safe."))
        self.assertEqual(rows["wound"], ("episode", 4, -2, "A skitter cut me."))
        self.assertEqual(rows["chill"][:3], ("episode", 5, -2))
        self.assertEqual(rows["asked"][:3], ("episode", 3, 0))
        self.assertGreaterEqual(private, 1)  # the question is about the owner: never in a story

    def test_the_inbox_tells_what_mimo_worked_out_and_its_ailments_once_a_game_day(self):
        name = self.name
        self.log(("figured", f"{name} worked out that cooking makes meat safe."),
                 ("festering", f"{name}'s wound is festering."), ("festering", f"{name}'s wound is festering."),
                 ("chill", f"{name} caught a chill in the night."))
        with self.world.connect() as db:
            items = [(item["kind"], item["text"]) for item in reversed(inbox_items(db))]
        self.assertEqual(items, [("report", "I worked it out myself: cooking makes meat safe."),
                                 ("danger", "My wound is festering."), ("danger", "I caught a chill in the night.")])

    def test_a_taught_survival_lesson_seen_true_says_you_were_right(self):
        with self.world.transaction() as db:
            state = read_state(db)
            teach_lesson(db, state, thing("berries"), BORN + 1, 1)
            teach_lesson(db, state, thing("bed"), BORN + 1, 1)
            write_state(db, state)
        self.log(("ate", f"{self.name} ate berries."), ("rested", f"{self.name} slept soundly in its bed."))
        with self.world.connect() as db:
            said = [row[0] for row in db.execute("SELECT text FROM mimo_chat WHERE who='mimo'")]
        self.assertEqual(said, ["You were right: bright red berries are safe to eat. I saw it myself!",
                                "You were right: six planks make a bed, and sleep in a bed rests you best. I saw it myself!"])
        self.assertTrue(confirms(thing("cooking"), "cook"))
        self.assertFalse(confirms(thing("cooking"), "found"))
        self.assertFalse(confirms("gravel", "ate"))  # the other lessons keep their seeing kinds


class DawnEventTests(unittest.TestCase):
    def test_a_night_in_a_bed_and_a_quiet_night_at_home_are_logged_at_dawn(self):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        set_home(db, (0, 1, 0), 0.0, BUILT)
        state = {"name": "Pip", "world_seed": "1", "position": {"x": 1.0, "y": 1.0, "z": 0.0}, "difficulty": "wild",
                 "vitals": {"warmth": 80.0}}
        context = SimpleNamespace(db=db, events=[])
        for _ in range(10):
            tend_night(state, context, 60.0, ("night", "night"), "sleeping_in_bed", True, 1.0)
        tend_night(state, context, 1.0, ("pre_dawn", "dawn"), "idle", True, 2.0)
        self.assertEqual([kind for _, kind, _ in context.events], ["rested", "safe_night"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild_news.py"`
Expected: `FAILED (failures=3, errors=1)`: no moment for the new events yet (`KeyError: 'figured'`), no news, no "You were right" for a survival lesson, no `rested` event

- [ ] **Step 3: Moments, news, danger and seeing a lesson true**

In `backend/survival/ailments.py`, replace:

```python
                night["floor_sleep"] = night.get("floor_sleep", 0.0) + seconds
```

with:

```python
                night["floor_sleep"] = night.get("floor_sleep", 0.0) + seconds
            if activity == "sleeping_in_bed":
                night["bed_sleep"] = night.get("bed_sleep", 0.0) + seconds
```

and replace:

```python
    summary = {"cold": cold, "froze": froze, "chill": chill, "blows": night.get("night_blows", 0), "floor": floor}
    night.update(night_cold=0.0, froze=False, floor_sleep=0.0, night_blows=0)
    heard(DAWN, state, context, summary, at)
```

with:

```python
    blows = night.get("night_blows", 0)
    name = state["name"]
    if night.get("bed_sleep", 0.0) >= FLOOR_SLEEP:  # what shows the bed lesson true (teaching.SEEN_BY)
        context.events.append((at, "rested", f"{name} slept soundly in its bed."))
    if not blows and at_built_home(state, context):  # what shows the light lesson true
        context.events.append((at, "safe_night", f"{name} spent a quiet night at home."))
    summary = {"cold": cold, "froze": froze, "chill": chill, "blows": blows, "floor": floor}
    night.update(night_cold=0.0, froze=False, floor_sleep=0.0, bed_sleep=0.0, night_blows=0)
    heard(DAWN, state, context, summary, at)


def at_built_home(state: dict, context) -> bool:
    """Mimo is within 8 blocks of the home it built."""
    if getattr(context, "db", None) is None:
        return False
    from backend.survival.memory import BUILT, places  # local: memory is the tick's, read once a dawn
    home = next((place for place in places(context.db, ("home",)) if place["note"] == BUILT), None)
    if home is None:
        return False
    position = state["position"]
    return math.hypot(position["x"] - home["x"], position["z"] - home["z"]) <= 8.0
```

In `backend/survival/bonding.py`, replace:

```python
from backend.survival import questions  # noqa: F401  (W1: Mimo's questions to its owner, and their answers)
```

with:

```python
from backend.survival import questions  # noqa: F401  (W1: Mimo's questions to its owner, and their answers)
from backend.survival import wild_news  # noqa: F401  (W1: new moments for Mind, news and danger for the inbox)
```

In `backend/survival/teaching.py`, replace:

```python
HUNTING = frozenset({"hunt", "fight"})
```

with:

```python
HUNTING = frozenset({"hunt", "fight"})
# W1: the events that show a survival lesson true, and the words they must say: the berries eaten, meat cooked,
# a campfire made, a sickness cured or a wound dressed with sunleaf, a wound bandaged, the shelter built and
# moved into, a night in a bed, a quiet night at home (backend.survival.ailments' dawn).
SEEN_BY = {"wild:berries": (("ate",), ("berry",)), "wild:cooking": (("cook",), ()),
           "wild:fire": (("craft",), ("campfire",)), "wild:sunleaf": (("cured", "dressed"), ("sunleaf",)),
           "wild:bandage": (("dressed",), ("bandage",)), "wild:shelter": (("built",), ("moved",)),
           "wild:bed": (("rested",), ()), "wild:light": (("safe_night",), ())}
```

and replace:

```python
def confirms(thing: str, kind: str) -> bool:
```

with:

```python
def confirms(thing: str, kind: str) -> bool:
    if thing.startswith("wild:"):  # W1: a survival lesson, by its own events only
        return kind in SEEN_BY.get(thing, ((), ()))[0]
    if kind not in SEEING:
        return False
```

and replace:

```python
        if lesson is None or not confirms(thing, event["kind"]) or not set(tokens(named(lesson))) <= said:
```

with:

```python
        words = SEEN_BY[thing][1] if thing in SEEN_BY else tuple(tokens(named(lesson))) if lesson else ()
        if lesson is None or not confirms(thing, event["kind"]) or not set(words) <= said:
```

and replace:

```python
for _kind in SEEING:
```

with:

```python
for _kind in (*SEEING, *sorted({kind for kinds, _ in SEEN_BY.values() for kind in kinds} - set(SEEING))):
```

Create `backend/survival/wild_news.py`:

```python
"""W1: what a wild pet's new moments mean to its memory and its inbox ("Moments, news and voice").

Mind's memory (backend.survival.episodes) keeps these events as moments: "figured" 7 (+2, a lesson: Mimo worked
something out itself), "cured" 4 (+1), "wound" 4 (-2), "festering" 5 (-2), "chill" 5 (-2), "spoiled" 2 (-1, a
game day's merged as "{n} of my food went bad."), "asked" 3 (0, about the owner, so it never reaches Luna).
The inbox (Bond B2's mirror) tells the owner what Mimo worked out as a report ("I worked it out myself: ..."),
and a festering wound, a chill or a sickness as danger, each at most once a game day. Every text reads in
Mimo's own voice (replies.in_my_voice; test_survival_voice).
"""

from __future__ import annotations

import sqlite3

from backend.survival.bond import bond_state
from backend.survival.clock import DAY_SECONDS
from backend.survival.episodes import MOMENTS, Moment, followed, remember_moment
from backend.survival.events import mirror
from backend.survival.inbox import CONSUMER, post_item
from backend.survival.replies import in_my_voice

MOMENTS.update({
    "figured": Moment(7, 2, kind="lesson"),
    "cured": Moment(4, 1),
    "wound": Moment(4, -2),
    "festering": Moment(5, -2),
    "chill": Moment(5, -2),
    "spoiled": Moment(2, -1, many="{n} of my food went bad."),
    "asked": Moment(3, 0, about=("owner",)),
})
for _kind in ("figured", "cured", "wound", "festering", "chill", "spoiled", "asked"):
    followed(_kind, remember_moment)


def figured(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """What Mimo worked out, as news: "I worked it out myself: cooking makes meat safe."."""
    prefix = f"{state['name']} worked out that "
    what = event["text"][len(prefix):] if event["text"].startswith(prefix) else in_my_voice(event["text"], state["name"])
    post_item(db, event["at"], "report", f"I worked it out myself: {what}", {"event": event["id"]})


def ailment_danger(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A festering wound, a chill or a sickness, as danger, at most once a game day of each kind."""
    told = bond_state(state).setdefault("ailments_told", {})
    last = told.get(event["kind"])
    if last is not None and (event["at"] - last) * scale < DAY_SECONDS:
        return
    told[event["kind"]] = event["at"]
    post_item(db, event["at"], "danger", in_my_voice(event["text"], state["name"]), {"event": event["id"]})


mirror(CONSUMER, "figured", figured)
for _kind in ("festering", "chill", "sick"):
    mirror(CONSUMER, _kind, ailment_danger)
```

In `backend/survival/world.py`, replace:

```python
                            "hunt", "hurt", "fight", "threat", "learned", "bell"})
```

with:

```python
                            "hunt", "hurt", "fight", "threat", "learned", "bell",
                            # W1: a wild pet's small news (backend.survival.wild_news)
                            "cured", "dressed", "spoiled", "asked", "rested", "safe_night"})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild_news.py"`
Expected: `Ran 4 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_voice.py"` and `-p "test_survival_mind_privacy.py"`
Expected: `OK` each

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1923 tests` … `OK (skipped=5)` (5 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/ailments.py backend/survival/bonding.py backend/survival/teaching.py backend/survival/wild_news.py backend/survival/world.py backend/tests/test_survival_mind_privacy.py backend/tests/test_survival_voice.py backend/tests/test_survival_wild_news.py
git commit -m "feat(W1): what Mimo works out, catches and asks becomes its memories, the owner's news and a warning" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Viewer: ailments, the badge, questions and chips, the Survival section, the memorial

**Files:**
- Create: `frontend/src/survival/wild.ts`, `frontend/src/survival/wild.test.ts`
- Modify: `frontend/src/survival/types.ts`, `bondTypes.ts`, `bond.ts` (`answerQuestion`), `hud.ts` (words), `animation.ts` (`dress`), `creatures.ts` (colours), `BondBar.tsx` ("?" count), `InboxPanel.tsx` (chips), `JournalPanel.tsx` (Survival), `Memorial.tsx`, `SurvivalHud.tsx` (the ailment line and the badge), `SurvivalWorld.tsx`, `WorldCanvas.tsx`, `SurvivalPet.tsx` (the pet's look), `frontend/src/survival/{bond,hud}.test.ts`
- Modify: `backend/survival/questions.py` (`at` in `questions_view`), `backend/survival/snapshot.py` (the life summary's `survival`), `backend/tests/test_survival_questions.py`, `backend/tests/test_survival_wild.py`

**Interfaces:**
- Consumes: `/api/mimo`'s `difficulty`, `survival`, `ailments` and `inbox.questions`; the answer endpoint; the memorial's summary.
- Produces: `wild.ts`: `ailmentLine`, `wildBadge`, `questionsLabel`, `canAnswer`, `closedLine`, `survivalEntries`, `lessonCounts`, `memorialLessons`, `petAilment`, `shiverAt`, `askBubble`; `bond.answerQuestion(id, choice)`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_questions.py`, replace:

```python
        self.assertEqual(question["text"], "The floor is so hard to sleep on.")
```

with:

```python
        self.assertEqual((question["text"], question["at"]), ("The floor is so hard to sleep on.", 10.0))
```

In `backend/tests/test_survival_wild.py`, replace:

```python
        registry.mark_dead(registry.active_life()["id"], BORN, "starvation")
```

with:

```python
        registry.mark_dead(registry.active_life()["id"], BORN, "starvation")
        memorial = get_mimo()["last_life"]
        self.assertEqual(len(memorial["survival"]), 11)  # the memorial tallies where its lessons came from
```

In `frontend/src/survival/bond.test.ts`, replace:

```ts
    expect(answeredLine(ask)).toBe('')
```

with:

```ts
    expect(answeredLine(ask)).toBe('')
    // W1: one of Mimo's questions, closed: its answer is a chip's index, never a name
    expect(answeredLine({ ...ask, data: { ask: 'wonder', answer: 0, closed: 'taught' } })).toBe('You told me')
    expect(answeredLine({ ...ask, data: { ask: 'wonder', answer: null, closed: null } })).toBe('')
```

In `frontend/src/survival/hud.test.ts`, replace:

```ts
    expect(purposeText({ purpose: 'loot_ruin', reflex: null, choosing: false })).toBe('Looting an old ruin')
```

with:

```ts
    expect(purposeText({ purpose: 'loot_ruin', reflex: null, choosing: false })).toBe('Looting an old ruin')
    expect(lifeLine({ kind: 'survival', alive: false, days: 6, cause: 'sickness' }))
      .toBe('Survived 6 days · fell sick and never got better')  // W1
    expect(purposeText({ purpose: 'dress_wound', reflex: null, choosing: false })).toBe('Dressing its wound')
    expect(purposeText({ purpose: null, reflex: 'take_herb', choosing: false })).toBe('Eating sunleaf to feel better')
```

Create `frontend/src/survival/wild.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import {
  ASK_BUBBLE_SECONDS, SICK_HOP, SICK_TINT, ailmentLine, askBubble, canAnswer, closedLine, lessonCounts, memorialLessons,
  petAilment, questionsLabel, shiverAt, survivalEntries, wildBadge,
} from './wild'
import type { InboxItem } from './bondTypes'
import type { Ailments, SurvivalLesson } from './types'

const TUMMY: Ailments = { sick: { kind: 'tummy', label: 'Tummy ache', words: 'My tummy hurts.', minutes: 7 }, wound: null }
const LESSONS: SurvivalLesson[] = [
  { name: 'berries', words: 'red berries', fact: 'Bright red berries are safe to eat.', known: true, source: 'from_you' },
  { name: 'fire', words: 'a campfire', fact: 'Two logs and three sticks make a campfire.', known: true, source: 'figured' },
  { name: 'bed', words: 'a bed', fact: 'Six planks make a bed.', known: false, source: null },
]

function question(data: InboxItem['data']): InboxItem {
  return { id: 1, at: 10, kind: 'ask', text: 'Can I eat them?', data, read: false }
}

describe('wild', () => {
  it('says what ails Mimo on the HUD, and nothing when it is well', () => {
    expect(ailmentLine(TUMMY)).toBe('Tummy ache · 7 min')
    expect(ailmentLine({ sick: { kind: 'chill', label: 'Chill', words: '', minutes: 18 }, wound: null })).toBe('Chill · 18 min')
    expect(ailmentLine({ sick: null, wound: { festering: true, dressed: false, minutes: 40 } })).toBe('Wound festering')
    expect(ailmentLine({ ...TUMMY, wound: { festering: false, dressed: true, minutes: 3 } })).toBe('Tummy ache · 7 min · Wound dressed')
    expect(ailmentLine({ sick: null, wound: null })).toBeNull()
    expect(ailmentLine(undefined)).toBeNull()
  })

  it('badges a wild pet and counts its open questions', () => {
    expect(wildBadge('wild')).toBe('Wild')
    expect(wildBadge('gentle')).toBeNull()
    expect(wildBadge(undefined)).toBeNull()
    expect(questionsLabel({ unread: 1, newest: [], questions: [{ id: 1, text: 'a', chips: ['x'], yes_no: false }] })).toBe('? 1')
    expect(questionsLabel({ unread: 0, newest: [] })).toBeNull()
  })

  it('offers chips on an open question and words on a closed one', () => {
    expect(canAnswer(question({ ask: 'wonder', chips: ['Yes', 'No'] }))).toBe(true)
    expect(canAnswer(question({ ask: 'wonder', chips: ['Yes'], closed: 'taught' }))).toBe(false)
    expect(canAnswer(question({ ask: 'name' }))).toBe(false)
    expect(closedLine(question({ ask: 'wonder', closed: 'taught' }))).toBe('You told me')
    expect(closedLine(question({ ask: 'wonder', closed: 'doubted' }))).toBe('Not sure about that one')
    expect(closedLine(question({ ask: 'wonder', closed: 'figured' }))).toBe('I figured it out')
    expect(closedLine(question({ ask: 'wonder' }))).toBe('')
  })

  it('lists the survival lessons with their sources, the unknown ones as "?", and tallies them', () => {
    expect(survivalEntries(LESSONS).map((entry) => [entry.line, entry.source])).toEqual([
      ['Bright red berries are safe to eat.', 'from you'], ['Two logs and three sticks make a campfire.', 'worked it out'],
      ['?', null]])
    expect(lessonCounts(LESSONS)).toEqual({ fromYou: 1, figured: 1 })
    expect(memorialLessons(LESSONS)).toBe('1 lesson from you · 1 worked out alone')
    expect(memorialLessons([])).toBeNull()
  })

  it('shows a sickness, a chill and a wound on the pet', () => {
    expect(petAilment(TUMMY)).toEqual({ tint: SICK_TINT, droop: true, hop: SICK_HOP, shiver: false, wrap: false, mark: false })
    expect(petAilment({ sick: { kind: 'chill', label: 'Chill', words: '', minutes: 1 }, wound: null }).shiver).toBe(true)
    expect(petAilment({ sick: null, wound: { festering: true, dressed: false, minutes: 1 } }))
      .toEqual({ tint: 0, droop: false, hop: 1, shiver: false, wrap: false, mark: true })
    expect(petAilment(null).tint).toBe(0)
    expect(shiverAt(0.1)).not.toBe(0)
    expect(shiverAt(1.5)).toBe(0)
  })

  it('floats a "?" over the pet for a few seconds after it asks', () => {
    const asked = [{ id: 1, text: 'a', chips: [], yes_no: false, at: 100 }]
    expect(askBubble(asked, 100 + ASK_BUBBLE_SECONDS - 1)).toBe(true)
    expect(askBubble(asked, 100 + ASK_BUBBLE_SECONDS + 1)).toBe(false)
    expect(askBubble([], 100)).toBe(false)
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/wild.test.ts`
Expected: FAIL: `Failed to resolve import "./wild"`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_questions.py"`
Expected: `FAILED (errors=1)`: a question has no `at` yet (`KeyError: 'at'`)

- [ ] **Step 3: The viewer**

In `backend/survival/questions.py`, replace:

```python
    """Mimo's open questions for /api/mimo's inbox: {id, text, chips, yes_no}, oldest first."""
    return [{"id": item["id"], "text": item["text"], "chips": item["data"].get("chips", []),
```

with:

```python
    """Mimo's open questions for /api/mimo's inbox: {id, at, text, chips, yes_no}, oldest first."""
    return [{"id": item["id"], "at": item["at"], "text": item["text"], "chips": item["data"].get("chips", []),
```

In `backend/survival/snapshot.py`, replace:

```python
    return {**detail["life"], "notable_events": detail["notable_events"], "goals_reached": detail["goals_reached"],
            "memories": detail["memories"], "diary": detail["diary"]}
```

with:

```python
    state = detail["state"]
    return {**detail["life"], "notable_events": detail["notable_events"], "goals_reached": detail["goals_reached"],
            "memories": detail["memories"], "diary": detail["diary"],
            "survival": state.get("survival", []) if isinstance(state, dict) else []}  # W1: for the memorial
```

In `frontend/src/survival/BondBar.tsx`, replace:

```tsx
import { newestReply, talkLabel } from './talk'
```

with:

```tsx
import { newestReply, talkLabel } from './talk'
import { questionsLabel } from './wild'
```

and replace:

```tsx
        <button type="button" onClick={() => setReading(true)} className={button}>{inboxLabel(state.inbox)}</button>
```

with:

```tsx
        <button type="button" onClick={() => setReading(true)} className={button}>{inboxLabel(state.inbox)}</button>
        {questionsLabel(state.inbox) && (
          <button type="button" onClick={() => setReading(true)} className={`${button} font-semibold`}
            title={`${name} has questions for you`} aria-label={`${name}'s questions`}>{questionsLabel(state.inbox)}</button>
        )}
```

In `frontend/src/survival/InboxPanel.tsx`, replace:

```tsx
import { answeredLine, canName, fetchInbox, kindLabel, markInboxRead, nameProblem, namePlace, unreadIds } from './bond'
```

with:

```tsx
import { answerQuestion, answeredLine, canName, fetchInbox, kindLabel, markInboxRead, nameProblem, namePlace, unreadIds } from './bond'
import { canAnswer } from './wild'
```

and replace:

```tsx

  return createPortal(
```

with:

```tsx

  // W1: a chip of one of Mimo's questions
  const choose = async (item: InboxItem, choice: number) => {
    try {
      const { item: answered } = await answerQuestion(item.id, choice)
      setItems((current) => current?.map((known) => known.id === answered.id ? answered : known) ?? null)
      setError('')
      await onChanged()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That answer did not go through. Try again.')
    }
  }

  return createPortal(
```

and replace:

```tsx
              {answeredLine(item) && <p className="mt-1 text-xs text-[#54726e]">{answeredLine(item)}</p>}
```

with:

```tsx
              {answeredLine(item) && <p className="mt-1 text-xs text-[#54726e]">{answeredLine(item)}</p>}
              {canAnswer(item) && (
                <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Answers">
                  {(item.data.chips ?? []).map((chip, choice) => (
                    <button key={chip} type="button" onClick={() => { void choose(item, choice) }}
                      className="rounded-xl border border-[#bfd5cd] bg-white px-3 py-1.5 text-left text-sm text-[#315e58] hover:bg-[#e1eee7]">{chip}</button>
                  ))}
                </div>
              )}
```

In `frontend/src/survival/JournalPanel.tsx`, replace:

```tsx
import type { JournalEntry } from './types'

/** L4b: the knowledge journal, what Mimo learned about the world, newest first. */
export default function JournalPanel({ name, journal, onClose }: {
  name: string
  journal: readonly JournalEntry[] | undefined
```

with:

```tsx
import type { JournalEntry, SurvivalLesson } from './types'
import { survivalEntries } from './wild'

/** L4b: the knowledge journal, what Mimo learned about the world, newest first. */
export default function JournalPanel({ name, journal, survival, onClose }: {
  name: string
  journal: readonly JournalEntry[] | undefined
  /** W1: the survival lessons, known or not (an older API sends none). */
  survival?: readonly SurvivalLesson[]
```

and replace:

```tsx
  const entries = journalEntries(journal, name)
```

with:

```tsx
  const entries = journalEntries(journal, name)
  const lessons = survivalEntries(survival)
```

and replace:

```tsx
        </p>
        {entries.length === 0 && <p className="mt-6 text-sm text-[#65817b]">Nothing yet: {name} has not studied anything.</p>}
```

with:

```tsx
        </p>
        {lessons.length > 0 && (
          <div className="mt-6">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Survival</p>
            <ul className="mt-2 space-y-2">
              {lessons.map((lesson) => (
                <li key={lesson.key} className="rounded-xl bg-[#f1ecdf] px-4 py-2 text-sm leading-6">
                  <span className="mr-2 font-semibold text-[#6d5a2c]">{lesson.words}</span>
                  <span className={lesson.line === '?' ? 'text-[#9a8f73]' : 'text-[#243e3d]'}>{lesson.line}</span>
                  {lesson.source && <span className="ml-2 text-xs italic text-[#7d6b2c]">{lesson.source}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
        {entries.length === 0 && <p className="mt-6 text-sm text-[#65817b]">Nothing yet: {name} has not studied anything.</p>}
```

In `frontend/src/survival/Memorial.tsx`, replace:

```tsx
import type { LifeSummary } from './types'
```

with:

```tsx
import type { LifeSummary } from './types'
import { memorialLessons } from './wild'
```

and replace:

```tsx
        <p className="mt-3 text-sm text-[#54726e]">{lifeLine(life)}.</p>
```

with:

```tsx
        <p className="mt-3 text-sm text-[#54726e]">{lifeLine(life)}.</p>
        {memorialLessons(life.survival) && <p className="mt-1 text-sm text-[#54726e]">{memorialLessons(life.survival)}.</p>}
```

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```tsx
import { computerCaption, workshopButton } from './workshop'
```

with:

```tsx
import { computerCaption, workshopButton } from './workshop'
import { ailmentLine, wildBadge } from './wild'
```

and replace:

```tsx
  const workshop = workshopButton(state.workshop)
```

with:

```tsx
  const workshop = workshopButton(state.workshop)
  const ailing = ailmentLine(state.ailments)
  const badge = wildBadge(state.difficulty)
```

and replace:

```tsx
              <p className="truncate text-lg font-semibold leading-tight">{life.name}</p>
```

with:

```tsx
              <p className="truncate text-lg font-semibold leading-tight">
                {life.name}
                {badge && <span className="ml-2 rounded-md bg-[#e8d9b8] px-1.5 py-0.5 align-middle text-[10px] font-semibold uppercase tracking-wide text-[#7a5a24]"
                  title="A wild pet learns to survive from you, or the hard way">{badge}</span>}
              </p>
```

and replace:

```tsx
          {danger && <p className="mt-0.5 text-sm font-semibold text-[#b5473a]" role="status">{danger}</p>}
```

with:

```tsx
          {danger && <p className="mt-0.5 text-sm font-semibold text-[#b5473a]" role="status">{danger}</p>}
          {ailing && <p className="mt-0.5 text-xs font-semibold text-[#7d6b2c]" role="status">{ailing}</p>}
```

In `frontend/src/survival/SurvivalPet.tsx`, replace:

```tsx
import type { FinishedAction, MimoAction, Point } from './types'
```

with:

```tsx
import type { Ailments, FinishedAction, MimoAction, Point } from './types'
import { petAilment, shiverAt } from './wild'
```

and replace:

```tsx
const GLOW_COLOR = '#e0463a'
```

with:

```tsx
const GLOW_COLOR = '#e0463a'
const SICK_COLOR = '#7fb069'  // W1: a sick pet's green tint
const WRAP_COLOR = '#f4f0e4'
const MARK_COLOR = '#b5473a'
const ASK_COLOR = '#f5c46b'
/** W1: a "?" of little boxes floating over the pet's head, as [x, y] in pet units. */
const QUESTION_MARK: [number, number][] = [[-0.08, 0.3], [0, 0.36], [0.08, 0.3], [0.08, 0.22], [0, 0.14], [0, 0.06], [0, -0.06]]
```

and replace:

```tsx
  tunic = null, cap = null, hurtAt = null, children }: {
```

with:

```tsx
  tunic = null, cap = null, hurtAt = null, ailments = null, asking = false, children }: {
```

and replace:

```tsx
  hurtAt?: number | null
```

with:

```tsx
  hurtAt?: number | null
  /** W1: what ails it (a green tint, a droop and a slower hop while sick, a shiver with a chill, a wrap on a
   * dressed wound, a red mark while one festers) and whether it has just asked something (a "?" over it). */
  ailments?: Ailments | null
  asking?: boolean
```

and replace:

```tsx
  const tunicParts = useMemo(() => tunicVoxels(tunic ? { [tunic]: 1 } : {}), [tunic])
```

with:

```tsx
  const tunicParts = useMemo(() => tunicVoxels(tunic ? { [tunic]: 1 } : {}), [tunic])
  const ailing = useMemo(() => petAilment(ailments), [ailments])
```

and replace:

```tsx
      root.current.position.set(pose.x + 0.5, pose.y + shape.lift + hop, pose.z + 0.5)
```

with:

```tsx
      root.current.position.set(pose.x + 0.5, pose.y + (shape.lift + hop) * ailing.hop, pose.z + 0.5)
```

and replace:

```tsx
      body.current.rotation.set(shape.pitch, 0, shape.roll)
```

with:

```tsx
      const shiver = ailing.shiver ? shiverAt(state.clock.elapsedTime) : 0
      body.current.rotation.set(shape.pitch + (ailing.droop ? 0.12 : 0), 0, shape.roll + shiver)
```

and replace:

```tsx
        </group>
        <mesh ref={glow} position={[0, 0.95, 0.1]} visible={false}>
```

with:

```tsx
        </group>
        {ailing.tint > 0 && (
          <mesh position={[0, 0.95, 0.1]}>
            <boxGeometry args={[1.08, 1.92, 1.08]} />
            <meshBasicMaterial color={SICK_COLOR} transparent opacity={ailing.tint} depthWrite={false} />
          </mesh>
        )}
        {ailing.wrap && (
          <mesh position={[0.36, 0.45, 0.05]}>
            <boxGeometry args={[0.08, 0.2, 0.42]} />
            <meshLambertMaterial color={WRAP_COLOR} />
          </mesh>
        )}
        {ailing.mark && (
          <mesh position={[0.35, 0.45, 0.05]}>
            <boxGeometry args={[0.06, 0.14, 0.14]} />
            <meshBasicMaterial color={MARK_COLOR} />
          </mesh>
        )}
        <mesh ref={glow} position={[0, 0.95, 0.1]} visible={false}>
```

and replace:

```tsx
      </group>
      <group ref={zs} position={[0, 1.15, 0]} visible={false}>
```

with:

```tsx
      </group>
      {asking && (
        <group position={[0, 1.6, 0]}>
          {QUESTION_MARK.map(([x, y]) => (
            <mesh key={`${x},${y}`} position={[x, y, 0]}>
              <boxGeometry args={[0.07, 0.07, 0.07]} />
              <meshBasicMaterial color={ASK_COLOR} />
            </mesh>
          ))}
        </group>
      )}
      <group ref={zs} position={[0, 1.15, 0]} visible={false}>
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
import WorkshopPanel from './WorkshopPanel'
```

with:

```tsx
import WorkshopPanel from './WorkshopPanel'
import { askBubble } from './wild'
```

and replace:

```tsx
        creatures={state.creatures} creatureMoves={state.creature_moves} inventory={state.inventory} hurtAt={state.hurt_at}
```

with:

```tsx
        creatures={state.creatures} creatureMoves={state.creature_moves} inventory={state.inventory} hurtAt={state.hurt_at}
        ailments={state.ailments} asking={askBubble(state.inbox?.questions, state.server_time)}
```

and replace:

```tsx
      {showJournal && <JournalPanel name={state.life.name} journal={state.journal} onClose={() => setShowJournal(false)} />}
```

with:

```tsx
      {showJournal && <JournalPanel name={state.life.name} journal={state.journal} survival={state.survival}
        onClose={() => setShowJournal(false)} />}
```

In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import type { Built, Creature, CreatureMove, FinishedAction, LeafDecay, MimoAction, Point } from './types'
```

with:

```tsx
import type { Ailments, Built, Creature, CreatureMove, FinishedAction, LeafDecay, MimoAction, Point } from './types'
```

and replace:

```tsx
 * pet wears the armor in `inventory` and glows red when a creature hits it (`hurtAt`).
 */
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, recentActions = NO_ACTIONS, decays = NO_DECAYS, structures = NO_STRUCTURES, creatures, creatureMoves, inventory, hurtAt = null, serverTime, cameraMode = 'overview', onAutoPick, doorsOpen }: {
```

with:

```tsx
 * pet wears the armor in `inventory` and glows red when a creature hits it (`hurtAt`). W1: it shows what ails it
 * (`ailments`) and a "?" while it has just asked its owner something (`asking`).
 */
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, recentActions = NO_ACTIONS, decays = NO_DECAYS, structures = NO_STRUCTURES, creatures, creatureMoves, inventory, hurtAt = null, ailments = null, asking = false, serverTime, cameraMode = 'overview', onAutoPick, doorsOpen }: {
```

and replace:

```tsx
  hurtAt?: number | null
```

with:

```tsx
  hurtAt?: number | null
  /** W1: what ails Mimo, and whether it has just asked its owner something. */
  ailments?: Ailments | null
  asking?: boolean
```

and replace:

```tsx
            cap={wornCap(inventory)} hurtAt={hurtAt}>
```

with:

```tsx
            cap={wornCap(inventory)} hurtAt={hurtAt} ailments={ailments} asking={asking}>
```

In `frontend/src/survival/animation.ts`, replace:

```ts
  flip: 'place',  // Making: a lever thrown, a button pressed
```

with:

```ts
  flip: 'place',  // Making: a lever thrown, a button pressed
  dress: 'work',  // W1: wrapping a wound
```

In `frontend/src/survival/bond.ts`, replace:

```ts
import type { BondView, InboxItem, InboxView, RequestView } from './bondTypes'
```

with:

```ts
import type { BondView, InboxItem, InboxView, RequestView } from './bondTypes'
import { closedLine } from './wild'
```

and replace:

```ts
/** What answered one of Mimo's asks: the name given, or (m14) the day's snack or bandage; '' while it waits. */
export function answeredLine(item: InboxItem): string {
```

with:

```ts
/** What answered one of Mimo's asks: the name given, or (m14) the day's snack or bandage, or (W1) how one of its
 * questions closed; '' while it waits. */
export function answeredLine(item: InboxItem): string {
  if (item.data.ask === 'wonder') return closedLine(item)
```

and replace:

```ts
export const namePlace = (id: number, text: string) => postJson<{ item: InboxItem }>(`/api/mimo/inbox/${id}/answer`, { text })
```

with:

```ts
export const namePlace = (id: number, text: string) => postJson<{ item: InboxItem }>(`/api/mimo/inbox/${id}/answer`, { text })
/** W1: the owner answers one of Mimo's questions with the chip at `choice`. */
export const answerQuestion = (id: number, choice: number) =>
  postJson<{ item: InboxItem }>(`/api/mimo/inbox/${id}/answer`, { choice })
```

In `frontend/src/survival/bondTypes.ts`, replace:

```ts
  data: { ask?: string; words?: string; answer?: string; care?: string; day?: number | string; last?: number;
    writer?: string; lead?: number; lead_last?: number; done?: boolean; present?: boolean }
  read: boolean
```

with:

```ts
  data: { ask?: string; words?: string; answer?: string | number | null; care?: string; day?: number | string; last?: number;
    writer?: string; lead?: number; lead_last?: number; done?: boolean; present?: boolean
    /** W1: one of Mimo's questions: the wonder it is about, its answer chips, and how it closed ("taught",
     * "doubted", "noted" or "figured"; null while open), its answer being the chip's index. */
    wonder?: string; chips?: string[]; closed?: string | null; yes_no?: boolean }
  read: boolean
}

/** W1: one of Mimo's open questions (backend/survival/questions.py questions_view). */
export interface Question {
  id: number
  text: string
  chips: string[]
  yes_no: boolean
  /** Server time it was asked (an older API sends none). */
  at?: number
```

and replace:

```ts
  newest: InboxItem[]
```

with:

```ts
  newest: InboxItem[]
  /** W1: Mimo's open questions, oldest first (an older API sends none). */
  questions?: Question[]
```

In `frontend/src/survival/creatures.ts`, replace:

```ts
    amber: [232, 156, 44], gold_nugget: [246, 206, 84], diamond: [120, 226, 232], flint: [70, 70, 76],
```

with:

```ts
    amber: [232, 156, 44], gold_nugget: [246, 206, 84], diamond: [120, 226, 232], flint: [70, 70, 76],
    // W1: what a wild pet picks, makes and throws out
    nightberries: [74, 40, 96], sunleaf: [206, 212, 84], bandage: [244, 240, 228], spoiled_food: [122, 118, 70],
```

In `frontend/src/survival/hud.ts`, replace:

```ts
  starvation: 'starvation', cold: 'the cold', drowning: 'drowning', fall: 'a fall', creature: 'a creature',
```

with:

```ts
  starvation: 'starvation', cold: 'the cold', drowning: 'drowning', fall: 'a fall', creature: 'a creature',
  sickness: 'sickness',  // W1
```

and replace:

```ts
  drop: 'Dropping', attack: 'Attacking', shoot: 'Shooting', open_chest: 'Opening an old chest', flip: 'Flipping',
```

with:

```ts
  drop: 'Dropping', attack: 'Attacking', shoot: 'Shooting', open_chest: 'Opening an old chest', flip: 'Flipping',
  dress: 'Dressing its wound with',  // W1
```

and replace:

```ts
  build_machine: 'Building a machine', tinker: 'Tinkering',
```

with:

```ts
  build_machine: 'Building a machine', tinker: 'Tinkering',
  // W1
  find_herb: 'Looking for sunleaf', gather_herbs: 'Gathering sunleaf', nibble: 'Nibbling a plant',
  dress_wound: 'Dressing its wound', throw_out: 'Throwing out bad food',
```

and replace:

```ts
  turn_back: 'Turning back toward home',  // L5 final fix wave: past where it is ready to go
```

with:

```ts
  turn_back: 'Turning back toward home',  // L5 final fix wave: past where it is ready to go
  take_herb: 'Eating sunleaf to feel better',  // W1
```

and replace:

```ts
  if (life.cause && CAUGHT_BY.has(life.cause)) return `Survived ${daysText(life.days)} · caught by a ${thingName(life.cause)}`
```

with:

```ts
  if (life.cause && CAUGHT_BY.has(life.cause)) return `Survived ${daysText(life.days)} · caught by a ${thingName(life.cause)}`
  if (life.cause === 'sickness') return `Survived ${daysText(life.days)} · fell sick and never got better`  // W1
```

In `frontend/src/survival/types.ts`, replace:

```ts
  | 'flip'

```

with:

```ts
  | 'flip'
  | 'dress'  // W1: a wound dressed with a bandage or a sunleaf

```

and replace:

```ts
  /** Mind M3: the life's gists and thoughts, oldest first (an older API sends none). */
  memories?: LifeMemories
}
```

with:

```ts
  /** Mind M3: the life's gists and thoughts, oldest first (an older API sends none). */
  memories?: LifeMemories
  /** W1: the life's survival lessons and where each came from (an older API sends none). */
  survival?: SurvivalLesson[]
}
```

and replace:

```ts

/** A goal a life reached, and the game day it did. */
```

with:

```ts

/** W1: a life is wild or gentle (backend/survival/wild.py). */
export type Difficulty = 'wild' | 'gentle'

/** W1: a sickness Mimo has now (backend/survival/ailments.py ailments_view). */
export interface Sickness {
  kind: 'tummy' | 'chill'
  /** For the HUD: "Tummy ache". */
  label: string
  /** The symptom in Mimo's words. */
  words: string
  /** Game minutes left. */
  minutes: number
}

/** W1: a wound Mimo has now. */
export interface Wound {
  festering: boolean
  dressed: boolean
  /** Game minutes until it heals by itself. */
  minutes: number
}

/** W1: what ails Mimo (nothing, always, for a gentle pet). */
export interface Ailments {
  sick: Sickness | null
  wound: Wound | null
}

/** W1: a survival lesson, known or not, and where it came from (backend/survival/wild.py survival_view). */
export interface SurvivalLesson {
  name: string
  words: string
  fact: string
  known: boolean
  source: 'from_you' | 'figured' | 'from_start' | null
}

/** A goal a life reached, and the game day it did. */
```

and replace:

```ts
  workshop?: WorkshopView
```

with:

```ts
  workshop?: WorkshopView
  /** W1: wild or gentle; every survival lesson, known or not; what ails Mimo (an older API sends none of them). */
  difficulty?: Difficulty
  survival?: SurvivalLesson[]
  ailments?: Ailments
```

Create `frontend/src/survival/wild.ts`:

```ts
import type { InboxItem, InboxView, Question } from './bondTypes'
import type { Ailments, Difficulty, SurvivalLesson } from './types'

/**
 * Wild World W1 in the viewer: the ailment line and the "Wild" badge on the HUD, the count of Mimo's open
 * questions, the words on a question the owner answered, the journal's survival lessons with where each came
 * from, the memorial's tally, and how a sickness, a chill or a wound shows on the pet. The rules are the
 * server's (backend/survival/wild.py, ailments.py, questions.py).
 */

/** How long the "?" bubble floats over the pet after it asks (seconds). */
export const ASK_BUBBLE_SECONDS = 10
/** How green a sick pet is tinted (0..1), and how much of its hop is left. */
export const SICK_TINT = 0.25
export const SICK_HOP = 0.6
/** A chill's shiver: a short shake every few seconds. */
export const SHIVER_EVERY = 3
export const SHIVER_SECONDS = 0.4
const SOURCES: Record<string, string> = { from_you: 'from you', figured: 'worked it out', from_start: 'knew from the start' }
const CLOSED: Record<string, string> = {
  taught: 'You told me', noted: 'You told me', doubted: 'Not sure about that one', figured: 'I figured it out',
}

/** "Tummy ache · 7 min", "Chill · 18 min", "Wound festering", together when there is more than one; null when well. */
export function ailmentLine(ailments: Ailments | null | undefined): string | null {
  const parts: string[] = []
  if (ailments?.sick) parts.push(`${ailments.sick.label} · ${ailments.sick.minutes} min`)
  if (ailments?.wound) parts.push(ailments.wound.festering ? 'Wound festering' : ailments.wound.dressed ? 'Wound dressed' : 'Wound')
  return parts.length ? parts.join(' · ') : null
}

/** The badge beside a wild pet's name; none for a gentle one (or an older API that sends no difficulty). */
export function wildBadge(difficulty: Difficulty | null | undefined): string | null {
  return difficulty === 'wild' ? 'Wild' : null
}

/** "? 2" while Mimo has questions waiting for an answer, else null. */
export function questionsLabel(inbox: InboxView | null | undefined): string | null {
  const count = inbox?.questions?.length ?? 0
  return count > 0 ? `? ${count}` : null
}

/** A question of Mimo's the owner can still answer with a chip. */
export function canAnswer(item: InboxItem): boolean {
  return item.kind === 'ask' && item.data.ask === 'wonder' && !item.data.closed && (item.data.chips?.length ?? 0) > 0
}

/** How a closed question reads: "You told me", "Not sure about that one" or "I figured it out"; '' while open. */
export function closedLine(item: InboxItem): string {
  return item.data.closed ? CLOSED[item.data.closed] ?? '' : ''
}

/** The journal's survival section: each lesson with its fact and where it came from, or "?" while unknown. */
export function survivalEntries(survival: readonly SurvivalLesson[] | null | undefined): {
  key: string; words: string; line: string; source: string | null
}[] {
  return (survival ?? []).map((lesson) => ({
    key: lesson.name,
    words: lesson.words,
    line: lesson.known ? lesson.fact : '?',
    source: lesson.known && lesson.source ? SOURCES[lesson.source] ?? null : null,
  }))
}

/** How many survival lessons came from the owner and how many Mimo worked out alone. */
export function lessonCounts(survival: readonly SurvivalLesson[] | null | undefined): { fromYou: number; figured: number } {
  const known = (survival ?? []).filter((lesson) => lesson.known)
  return { fromYou: known.filter((lesson) => lesson.source === 'from_you').length,
    figured: known.filter((lesson) => lesson.source === 'figured').length }
}

/** The memorial's line: "4 lessons from you · 5 worked out alone"; null when it learned none either way. */
export function memorialLessons(survival: readonly SurvivalLesson[] | null | undefined): string | null {
  const { fromYou, figured } = lessonCounts(survival)
  if (fromYou + figured === 0) return null
  const plural = (count: number) => `${count} lesson${count === 1 ? '' : 's'}`
  return `${plural(fromYou)} from you · ${figured} worked out alone`
}

/** How the pet shows its ailments: a green tint and a droop with a slower hop while sick, a shiver with a
 * chill, a white wrap on a dressed wound and a red mark while one festers. */
export function petAilment(ailments: Ailments | null | undefined): {
  tint: number; droop: boolean; hop: number; shiver: boolean; wrap: boolean; mark: boolean
} {
  const sick = ailments?.sick ?? null
  const wound = ailments?.wound ?? null
  return { tint: sick ? SICK_TINT : 0, droop: sick !== null, hop: sick ? SICK_HOP : 1, shiver: sick?.kind === 'chill',
    wrap: Boolean(wound?.dressed), mark: Boolean(wound?.festering) }
}

/** The roll of a chill's shiver at `t` seconds: a short shake every SHIVER_EVERY seconds, still between. */
export function shiverAt(t: number): number {
  const phase = ((t % SHIVER_EVERY) + SHIVER_EVERY) % SHIVER_EVERY
  return phase < SHIVER_SECONDS ? Math.sin(phase * 60) * 0.06 : 0
}

/** Whether the "?" bubble floats over the pet: it asked within ASK_BUBBLE_SECONDS (server seconds). */
export function askBubble(questions: readonly Question[] | null | undefined, serverTime: number): boolean {
  const newest = Math.max(-Infinity, ...(questions ?? []).map((question) => question.at ?? -Infinity))
  return serverTime - newest >= 0 && serverTime - newest <= ASK_BUBBLE_SECONDS
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  373 passed (373)`, the build succeeds, eslint prints nothing.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1923 tests` … `OK (skipped=5)` (0 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/questions.py backend/survival/snapshot.py backend/tests/test_survival_questions.py backend/tests/test_survival_wild.py frontend/src/survival/BondBar.tsx frontend/src/survival/InboxPanel.tsx frontend/src/survival/JournalPanel.tsx frontend/src/survival/Memorial.tsx frontend/src/survival/SurvivalHud.tsx frontend/src/survival/SurvivalPet.tsx frontend/src/survival/SurvivalWorld.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/survival/animation.ts frontend/src/survival/bond.test.ts frontend/src/survival/bond.ts frontend/src/survival/bondTypes.ts frontend/src/survival/creatures.ts frontend/src/survival/hud.test.ts frontend/src/survival/hud.ts frontend/src/survival/types.ts frontend/src/survival/wild.test.ts frontend/src/survival/wild.ts
git commit -m "feat(W1): the viewer shows what ails the pet, asks the owner with chips and lists the survival lessons" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: The gate script

**Files:**
- Create: `backend/scripts/wild_gate.py`
- Test: `backend/tests/test_survival_wild_run.py`

**Interfaces:**
- Consumes: everything above; `hatch`, `tick_life`, the Chooser and the Talker with a counting model stand-in; `talk.owner_says`; `questions.answer_question`; `state["wild"]["lost"]` (Task 5).
- Produces: `wild_gate.live(seed, days, condition, http=None) -> dict` (a life's summary, with `sick_by_day` and `lost_by_day`), `check_w1(out) -> [(criterion, passed, measure)]` (the criteria as amended by spec resolution 29: 6′, 7′ and 10′), the command line of "The harness".

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_wild_run.py`:

```python
"""W1's headless lives (the gate's harness, backend/scripts/wild_gate.py, for a few short lives).

By default seed 8 for 3 game days, untaught and taught: the untaught pet posts at least 3 questions, the taught
one knows all 11 W1 lessons by the end of day 1, and both live. With MIMO_SLOW_TESTS=1, seeds 3 and 11 for 20
game days: the untaught pet's sick minutes are at least twice the taught pet's, both are alive on day 5, and the
taught one on day 20. No model is ever called and nothing is logged as an error. The W1 criteria that compare
the conditions (6', 7', 10') are checked on made-up summaries.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from backend.scripts.wild_gate import CONDITIONS, SEEDS, check_w1, live
from backend.tests.no_model import no_model


def summary(condition, seed, **changes):
    """A made-up life's summary, as `live` writes it: a quiet 150-day life unless changed."""
    found = {"seed": seed, "condition": condition, "died_day": None, "health_mean": 99.0, "near_death_days": [],
             "sick_minutes": 0, "sick_by_day": [0] * 150, "lost_by_day": [0.0] * 150,
             "machines": {"lamp_lever": 50.0}, "lessons": {}, "wonders_met": {}, "questions": [], "open_most": 0,
             "ever": {"sick": False, "wound": False, "lots": False, "question": False}, "model_calls": 0, "errors": []}
    found.update(changes)
    return found


def untaught(seed, **changes):
    """An untaught life that is sick 40 game minutes and loses 110 health in its first month, 150 minutes in all,
    and meets 5 wonders and asks 3 questions in its first 3 days."""
    found = summary("untaught", seed, sick_minutes=150, sick_by_day=[40] * 30 + [150] * 120,
                    lost_by_day=[110.0] * 30 + [300.0] * 120, near_death_days=[12],
                    wonders_met={name: 1.5 for name in ("a", "b", "c", "d", "e")},
                    questions=[[1.5, "a"], [2.0, "b"], [3.5, "c"]], open_most=3)
    found.update(changes)
    return found


class WildRunTests(unittest.TestCase):
    def life(self, seed, days, condition):
        found = live(seed, days, condition, http=no_model(self))
        self.assertEqual(found["errors"], [])
        return found

    def test_an_untaught_pet_asks_and_a_taught_one_knows_every_lesson_on_day_one(self):
        untaught = self.life(8, 3, "untaught")
        taught = self.life(8, 3, "taught")
        self.assertIsNone(untaught["died_day"])
        self.assertIsNone(taught["died_day"])
        self.assertGreaterEqual(len(untaught["questions"]), 3)
        self.assertLessEqual(untaught["open_most"], 3)
        self.assertEqual(len(taught["lessons"]), 11)
        self.assertTrue(all(entry["day"] < 2 for entry in taught["lessons"].values()), taught["lessons"])

    @unittest.skipUnless(os.environ.get("MIMO_SLOW_TESTS"), "a slow run: set MIMO_SLOW_TESTS=1")
    def test_twenty_days_untaught_is_sicker_and_taught_lives(self):
        for seed in (3, 11):
            untaught = self.life(seed, 20, "untaught")
            taught = self.life(seed, 20, "taught")
            self.assertGreaterEqual(untaught["sick_minutes"], 2 * taught["sick_minutes"], seed)
            for found in (untaught, taught):
                self.assertTrue(found["died_day"] is None or found["died_day"] > 5, (seed, found["condition"]))
            self.assertIsNone(taught["died_day"], seed)


class CheckTests(unittest.TestCase):
    def rows(self, **untaught_changes):
        """The W1 check on six lives of each condition; `untaught_changes` changes the untaught life of seed 3."""
        with tempfile.TemporaryDirectory() as root:
            for condition in CONDITIONS:
                for seed in SEEDS:
                    if condition == "untaught":
                        life = untaught(seed, **(untaught_changes if seed == 3 else {}))
                    else:
                        life = summary(condition, seed, sick_minutes=10, sick_by_day=[5] * 30 + [10] * 120,
                                       lost_by_day=[20.0] * 150)
                    (Path(root) / f"{condition}_{seed}.json").write_text(json.dumps(life))
            return {name.split(" ")[0]: passed for name, passed, _ in check_w1(Path(root))}

    def test_a_newborns_first_month_a_life_without_the_owner_and_four_wonders(self):
        rows = self.rows()
        self.assertEqual((rows["6'"], rows["7'"], rows["10'"]), (True, True, True))
        # 6': 100 health a life lost to hazards in the first month, at least (550 over six lives is too few)
        self.assertFalse(self.rows(lost_by_day=[0.0] * 150)["6'"])
        # 7': deaths and near-death days together 6 at least (six near-death days above; one fewer here)
        self.assertFalse(self.rows(near_death_days=[])["7'"])
        self.assertTrue(self.rows(near_death_days=[], died_day=80.5)["7'"])
        # 10': 4 wonders met by the end of the third game day, on every seed
        self.assertTrue(self.rows(wonders_met={name: 3.9 for name in "abcd"})["10'"])
        self.assertFalse(self.rows(wonders_met={name: 3.9 for name in "abc"})["10'"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild_run.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.scripts.wild_gate'`

- [ ] **Step 3: The gate script**

Create `backend/scripts/wild_gate.py`:

```python
"""Wild World's balance gate (docs/superpowers/specs/2026-09-27-wild-world-design.md, "Balance gates").

One life per process, headless, with no model: hatched with random.Random(seed) at BORN, gentle for the
`gentle` condition and wild for the others, ticked at scale 60 and action scale 60 (a tick per 60 game
seconds, like test_survival_days), with the worker's Chooser (the rules) and Talker (the rules) after every
tick. Their HTTP is a counting stand-in that refuses every call; any call fails the gate.

- `untaught`: nobody talks to Mimo.
- `taught`: the scripted owner says the first teaching-table line of each W1 lesson on day 1, one every
  OWNER_EVERY game minutes from minute 5 (talk.owner_says, the real chat), and answers each question Mimo asks
  within ANSWER_AFTER game minutes with its true chip (questions.answer_question, what the answer endpoint
  calls). It gives no care.
- `liar`: answers each question within ANSWER_AFTER game minutes with a false chip, or with the wonder's false
  claim in the chat when it has none. It teaches nothing else.

Each life writes a JSON summary to --out: its death day and cause, sick game minutes (and by day), the health
it lost to its hazards (`state["wild"]["lost"]`: a sickness's or a festering wound's drain, a poison plant; and
by day), wounds and festering minutes, near-death days (health under 20 at least once), the time-weighted health
mean, freezing and starving minutes, the lessons it knows with their sources and days, the wonders it met and the questions it
asked in its first 3 game days and the most open at once, the machines it built by day, whether it ever had a
sickness, a wound, a lot or a question, logged errors and model calls.

    python3 -m backend.scripts.wild_gate --seed 8 --days 3 --condition untaught --out DIR
    python3 -m backend.scripts.wild_gate --days 150 --conditions gentle,untaught,taught --parallel 6 --out DIR
    python3 -m backend.scripts.wild_gate --check W1 DIR
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BORN = 1_000_000.0
SCALE = 60.0
SEEDS = (3, 5, 8, 11, 21, 42)
CONDITIONS = ("gentle", "untaught", "taught", "liar")
OWNER_EVERY = 5  # game minutes between the scripted owner's lines on day 1
ANSWER_AFTER = 2  # game minutes after a question is asked that the owner answers it
NEAR_DEATH = 20.0
FIRST_MONTH = 30  # W1 criterion 6: a newborn's first month, game days 1 to 30
# The scripted owner's lines: the first line of the teaching table for each W1 lesson.
TEACHES = ("Red berries are safe to eat.", "Nightberries are the dark purple ones, and they are poison.",
           "Red mushrooms are poison.", "Sunleaf cures sickness and cleans wounds.",
           "A wool bandage stops a wound festering.", "Two logs and three sticks make a campfire.",
           "Cooked meat and fish are safe to eat.", "Food keeps twice as long in a chest.",
           "Torches keep the dark creatures away.", "A shelter with a roof and a door keeps you safe at night.",
           "Six planks make a bed.")
MACHINES = ("lamp_lever", "auto_door", "night_light", "clock", "memory_cell", "counter", "computer")


class Errors(logging.Handler):
    """Every warning or error the backend logs in a life."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(record.getMessage()[:300])


class NoModel:
    """A model stand-in that counts every call and refuses it."""

    def __init__(self):
        self.calls: list[str] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(url)
        raise RuntimeError("no model in the gate")


def true_chip(wonder, chips: list[str]) -> int:
    """The shown chip that teaches the most (the true answer)."""
    return max(range(len(chips)), key=lambda index: len(next(chip for chip in wonder.chips
                                                             if chip.words == chips[index]).teaches))


def false_chip(wonder, chips: list[str]) -> int | None:
    return next((index for index, words in enumerate(chips)
                 if next(chip for chip in wonder.chips if chip.words == words).false), None)


def owner(world, condition: str, minute: int, now: float, answered: set) -> None:
    """The scripted owner (taught) or the liar, at game minute `minute` of the life."""
    from backend.survival.questions import answer_question, questions_view
    from backend.survival.talk import owner_says
    from backend.survival.wonders import WONDERS
    if condition == "taught" and minute <= OWNER_EVERY * len(TEACHES) and minute % OWNER_EVERY == 0:
        owner_says(world, TEACHES[minute // OWNER_EVERY - 1], now, SCALE)
    if condition not in ("taught", "liar"):
        return
    with world.connect() as db:
        open_now = questions_view(db)
        asked = {row[0]: row[1] for row in db.execute("SELECT id, at FROM mimo_inbox WHERE kind='ask'")}
        wonders = {row[0]: row[1] for row in db.execute(
            "SELECT id, json_extract(data, '$.wonder') FROM mimo_inbox WHERE kind='ask'")}
    for question in open_now:
        if question["id"] in answered or (now - asked[question["id"]]) * SCALE < ANSWER_AFTER * 60:
            continue
        answered.add(question["id"])
        wonder = WONDERS[wonders[question["id"]]]
        if condition == "taught":
            answer_question(world, question["id"], true_chip(wonder, question["chips"]), now, SCALE)
        else:
            lie = false_chip(wonder, question["chips"])
            if lie is not None:
                answer_question(world, question["id"], lie, now, SCALE)
            elif wonder.lie:
                owner_says(world, wonder.lie, now, SCALE)


def live(seed: int, days: int, condition: str, http=None) -> dict:
    """One life; its summary. `http` stands in for every model call (a counting NoModel unless a test gives its own)."""
    from backend.survival import bonding, minding  # noqa: F401  (every Bond and Mind writer registers)
    from backend.survival.brain import BRAIN
    from backend.survival.choosing import Chooser, InlineExecutor
    from backend.survival.hatch import hatch
    from backend.survival.once import forget_logged
    from backend.survival.registry import LifeRegistry
    from backend.survival.talker import Talker
    from backend.survival.tick import tick_life
    from backend.survival.world import SurvivalWorld

    forget_logged()
    errors = Errors()
    logging.getLogger("backend").addHandler(errors)
    started = time.time()
    with tempfile.TemporaryDirectory() as root:
        registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
        life = hatch(registry, random.Random(seed), timestamp=BORN, difficulty="gentle" if condition == "gentle" else "wild")
        world = SurvivalWorld(registry.world_path(life))
        model = http or NoModel()
        chooser = Chooser(env={}, http=model, executor=InlineExecutor(), rng=random.Random(seed), scale=SCALE)
        talker = Talker(env={}, http=model, scale=SCALE)
        answered: set = set()
        found = {"health": 0.0, "ticks": 0, "sick": 0, "sick_by_day": [], "lost_by_day": [], "wounds": 0,
                 "festering": 0, "near": set(),
                 "freezing": 0, "starving": 0, "open_most": 0, "ever": {"sick": False, "wound": False, "lots": False}}
        state = world.state()
        for minute in range(1, days * 60 + 1):
            now = BORN + minute
            state = tick_life(registry, now, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            if state is None or state["died_at"] is not None:
                break
            chooser.poll(registry, now)
            owner(world, condition, minute, now, answered)
            talker.poll(registry, now)
            sample(found, state, minute, world)
        talker.close()
        summary = summarize(world, found, seed, days, condition, time.time() - started)
    summary.update(errors=errors.records[:50], model_calls=len(getattr(model, "calls", [])))
    logging.getLogger("backend").removeHandler(errors)
    return summary


def sample(found: dict, state: dict, minute: int, world) -> None:
    """One tick's sample (a game minute)."""
    vitals, ailments = state["vitals"], state.get("ailments") or {}
    found["ticks"] += 1
    found["health"] += vitals["health"]
    day = (minute - 1) // 60 + 1
    while len(found["sick_by_day"]) < day:
        found["sick_by_day"].append(found["sick"])
    while len(found["lost_by_day"]) < day:
        found["lost_by_day"].append(found["lost_by_day"][-1] if found["lost_by_day"] else 0.0)
    found["lost_by_day"][day - 1] = round(float((state.get("wild") or {}).get("lost", 0.0)), 2)
    if ailments.get("sick"):
        found["sick"] += 1
        found["ever"]["sick"] = True
    found["sick_by_day"][day - 1] = found["sick"]
    wound = ailments.get("wound")
    if wound:
        found["ever"]["wound"] = True
        found["festering"] += bool(wound.get("festering"))
        if wound.get("age", 0.0) <= 60.0:
            found["wounds"] += 1
    if state.get("lots") or any(state.get("chest_lots", {}).values()):
        found["ever"]["lots"] = True
    if vitals["health"] < NEAR_DEATH:
        found["near"].add(day)
    found["freezing"] += vitals["warmth"] < 20.0
    found["starving"] += vitals["hunger"] <= 0.0
    if minute % 5 == 0:
        with world.connect() as db:
            open_now = db.execute("SELECT COUNT(*) FROM mimo_inbox WHERE kind='ask' AND json_extract(data, '$.ask')="
                                  "'wonder' AND json_extract(data, '$.closed') IS NULL").fetchone()[0]
        found["open_most"] = max(found["open_most"], open_now)


def summarize(world, found: dict, seed: int, days: int, condition: str, wall: float) -> dict:
    from backend.survival.memory import structures
    state = world.state()
    died = state.get("died_at")
    with world.connect() as db:
        facts: dict[str, dict] = {}
        for subject, fact, at in db.execute("SELECT subject, fact, learned_at FROM memory_knowledge WHERE subject LIKE 'wild:%'"):
            entry = facts.setdefault(subject[5:], {"day": None, "source": "figured"})
            if fact == "lesson":
                entry["day"] = round((at - BORN) / 60 + 1, 2)
            elif fact in ("taught", "born_knowing"):
                entry["source"] = {"taught": "from_you", "born_knowing": "from_start"}[fact]
        asks = [(round((row[0] - BORN) / 60 + 1, 3), row[1]) for row in db.execute(
            "SELECT at, json_extract(data, '$.wonder') FROM mimo_inbox WHERE kind='ask' AND "
            "json_extract(data, '$.ask')='wonder' ORDER BY id")]
        machines = {}
        for structure in structures(db, ("machine",)):
            name = structure["data"].get("style", {}).get("machine")
            if structure["status"] == "done" and name and name not in machines:
                machines[name] = round((structure["built_at"] - BORN) / 60 + 1, 2)
        kinds = dict(db.execute("SELECT kind, COUNT(*) FROM mimo_events GROUP BY kind").fetchall())
        computer = db.execute("SELECT MIN(at) FROM mimo_events WHERE kind='computer'").fetchone()[0]
    met = {wonder_id: round((entry["met_at"] - BORN) / 60 + 1, 3)
           for wonder_id, entry in ((state.get("wild") or {}).get("wonders") or {}).items()}
    ticks = max(1, found["ticks"])
    return {"seed": seed, "days": days, "condition": condition, "wall": round(wall, 1), "difficulty": state.get("difficulty"),
            "died_day": None if died is None else round((died - BORN) / 60 + 1, 2), "cause": state.get("cause"),
            "lived_minutes": found["ticks"], "health_mean": round(found["health"] / ticks, 2),
            "sick_minutes": found["sick"], "sick_by_day": found["sick_by_day"],
            "hazard_lost": found["lost_by_day"][-1] if found["lost_by_day"] else 0.0,
            "lost_by_day": found["lost_by_day"], "wounds": found["wounds"],
            "festering_minutes": found["festering"], "near_death_days": sorted(found["near"]),
            "freezing_minutes": found["freezing"], "starving_minutes": found["starving"], "lessons": facts,
            "wonders_met": met, "questions": asks, "open_most": found["open_most"], "machines": machines,
            "computer_day": None if computer is None else round((computer - BORN) / 60 + 1, 2),
            "ever": found["ever"] | {"question": bool(asks)}, "events": kinds}


# Many lives at once ---------------------------------------------------------------------------------

def fan_out(seeds, days: int, conditions, parallel: int, out: Path) -> None:
    """Every (condition, seed) as its own process, `parallel` at a time."""
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(condition, seed) for condition in conditions for seed in seeds]

    def run(job):
        condition, seed = job
        command = [sys.executable, "-m", "backend.scripts.wild_gate", "--seed", str(seed), "--days", str(days),
                   "--condition", condition, "--out", str(out)]
        return subprocess.run(command, capture_output=True, text=True).returncode

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        codes = list(pool.map(run, jobs))
    print(f"{len(jobs)} lives, {sum(1 for code in codes if code)} failed to run")


# The W1 gate ----------------------------------------------------------------------------------------

def load(out: Path) -> dict:
    lives: dict = {}
    for path in sorted(out.glob("*.json")):
        life = json.loads(path.read_text())
        lives.setdefault(life["condition"], {})[life["seed"]] = life
    return lives


def alive_on(life: dict, day: int) -> bool:
    return life["died_day"] is None or life["died_day"] > day


def by_day(life: dict, key: str, day: int) -> float:
    """A life's running count `key` ("sick_by_day", "lost_by_day") at the end of game day `day` (its last, if it
    died before)."""
    counts = life[key]
    return counts[min(day, len(counts)) - 1] if counts else 0


def check_w1(out: Path) -> list[tuple[str, bool, str]]:
    """The W1 gate's criteria, each (name, passed, the measure)."""
    lives = load(out)
    gentle, untaught, taught, liar = (lives.get(name, {}) for name in CONDITIONS)
    rows: list[tuple[str, bool, str]] = []

    def row(name, passed, measure):
        rows.append((name, bool(passed), measure))

    t, u = list(taught.values()), list(untaught.values())
    row("1 taught: all 6 alive on day 150", len(t) == 6 and all(alive_on(life, 150) for life in t),
        f"alive {sum(alive_on(life, 150) for life in t)}/{len(t)}")
    row("2 taught: each health mean 75 or more", t and all(life["health_mean"] >= 75 for life in t),
        f"lowest {min((life['health_mean'] for life in t), default=0)}")
    row("3 taught: each at most 3 near-death days", t and all(len(life["near_death_days"]) <= 3 for life in t),
        f"most {max((len(life['near_death_days']) for life in t), default=0)}")
    row("4 taught: each at most 150 sick minutes", t and all(life["sick_minutes"] <= 150 for life in t),
        f"most {max((life['sick_minutes'] for life in t), default=0)}")
    lamps = sum(1 for life in t if "lamp_lever" in life["machines"])
    most_taught = max((len(life["machines"]) for life in t), default=0)
    most_gentle = max((len(life["machines"]) for life in gentle.values()), default=0)
    row("5 taught: 3 of 6 build a lamp on a lever; the furthest taught within one of gentle's",
        lamps >= 3 and most_taught >= most_gentle - 1, f"lamps {lamps}/6; machines taught {most_taught}, gentle {most_gentle}")
    def first_month(key: str, group: list) -> float:
        return sum(by_day(life, key, FIRST_MONTH) for life in group)

    sick_u30, sick_t30 = first_month("sick_by_day", u), first_month("sick_by_day", t)
    lost_u30, lost_t30 = first_month("lost_by_day", u), first_month("lost_by_day", t)
    row("6' untaught, first month: sick minutes 3x taught; health lost to hazards 3x taught and 100+ a life",
        u and t and sick_u30 >= 3 * sick_t30 and lost_u30 >= 3 * lost_t30 and lost_u30 / len(u) >= 100,
        f"sick {sick_u30} vs {sick_t30}; lost {lost_u30:.0f} vs {lost_t30:.0f}, {lost_u30 / max(1, len(u)):.0f} a life")
    sick_u, sick_t = sum(life["sick_minutes"] for life in u), sum(life["sick_minutes"] for life in t)
    died_u = sum(1 for life in u if not alive_on(life, 150))
    near_u = sum(len(life["near_death_days"]) for life in u)
    row("7' untaught, a life without the owner: sick minutes 5x taught; deaths and near-death days 6+",
        u and t and sick_u >= 5 * sick_t and died_u + near_u >= 6,
        f"sick {sick_u} vs {sick_t}; deaths {died_u} + near-death days {near_u}")
    deaths = [life for life in u if not alive_on(life, 150)]
    row("8 untaught: at most 3 of 6 die, none before day 5", len(deaths) <= 3 and all(alive_on(life, 5) for life in u),
        f"deaths {len(deaths)} on days {[life['died_day'] for life in deaths]}")
    alone = {life["seed"]: sum(1 for entry in life["lessons"].values()
                               if entry["day"] is not None and entry["day"] <= 60 and entry["source"] == "figured")
             for life in u if alive_on(life, 60)}
    row("9 untaught: alive on day 60 knows 8 of 11 learned alone", all(count >= 8 for count in alone.values()),
        f"learned alone by day 60 {alone}")
    early = {life["seed"]: (sum(1 for day in life["wonders_met"].values() if day <= 4),  # its first 3 game days:
                            sum(1 for day, _ in life["questions"] if day <= 4)) for life in u}  # born on day 1.0
    open_most = max((life["open_most"] for group in lives.values() for life in group.values()), default=0)
    row("10' untaught: 4 wonders met and 3 questions in 3 days; never more than 3 open",
        all(met >= 4 and asked >= 3 for met, asked in early.values()) and open_most <= 3,
        f"(met, asked) {early}; most open {open_most}")
    lied = [name for life in liar.values() for name, entry in life["lessons"].items() if entry["source"] == "from_you"]
    row("11 liar: no lesson learned from a false chip or claim", liar and not lied, f"taught by the liar {lied}")
    liar_deaths = sum(1 for life in liar.values() if not alive_on(life, 30))
    untaught_deaths = sum(1 for life in u if not alive_on(life, 30))
    worse = {seed: (life["sick_by_day"][min(29, len(life["sick_by_day"]) - 1)] if life["sick_by_day"] else 0,
                    untaught[seed]["sick_by_day"][min(29, len(untaught[seed]["sick_by_day"]) - 1)]
                    if seed in untaught and untaught[seed]["sick_by_day"] else 0)
             for seed, life in liar.items()}
    row("12 liar: deaths by day 30 no more than untaught; sick minutes at most untaught + 30",
        liar and liar_deaths <= untaught_deaths and all(mine <= theirs + 30 for mine, theirs in worse.values()),
        f"deaths {liar_deaths} vs {untaught_deaths}; (liar, untaught) sick minutes by day 30 {worse}")
    g = list(gentle.values())
    clean = all(not any(life["ever"].values()) for life in g)
    known = all(len(life["lessons"]) == 11 and all(entry["source"] == "from_start" for entry in life["lessons"].values())
                for life in g)
    row("13 gentle: all alive; no sickness, wound, lot or question; every lesson from the first tick",
        len(g) == 6 and all(alive_on(life, 150) for life in g) and clean and known,
        f"alive {sum(alive_on(life, 150) for life in g)}/{len(g)}; clean {clean}; known {known}")
    everyone = [life for group in lives.values() for life in group.values()]
    row("all: no model call and no logged error", all(not life["model_calls"] and not life["errors"] for life in everyone),
        f"calls {sum(life['model_calls'] for life in everyone)}; errors {sum(len(life['errors']) for life in everyone)}")
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int)
    parser.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    parser.add_argument("--days", type=int, default=150)
    parser.add_argument("--condition", choices=CONDITIONS)
    parser.add_argument("--conditions", default="gentle,untaught,taught")
    parser.add_argument("--parallel", type=int, default=0)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", nargs=2, metavar=("MILESTONE", "DIR"))
    args = parser.parse_args(argv)
    if args.check:
        if args.check[0] != "W1":
            raise SystemExit("only the W1 gate is written yet")
        rows = check_w1(Path(args.check[1]))
        for name, passed, measure in rows:
            print(f"{'PASS' if passed else 'FAIL'}  {name}  ({measure})")
        return 0 if all(passed for _, passed, _ in rows) else 1
    if args.parallel:
        fan_out([int(seed) for seed in args.seeds.split(",")], args.days, args.conditions.split(","), args.parallel,
                args.out)
        return 0
    summary = live(args.seed, args.days, args.condition)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.condition}_{args.seed}.json").write_text(json.dumps(summary, indent=1))
    print(f"{args.condition} {args.seed}: died {summary['died_day']}, health {summary['health_mean']}, "
          f"sick {summary['sick_minutes']}, {summary['wall']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_wild_run.py"`
Expected: `Ran 3 tests` … `OK (skipped=1)` (about 15 seconds)

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_wild_run.py"`
Expected: `Ran 3 tests` … `OK` (about 7 minutes)

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1926 tests` … `OK (skipped=6)` (3 new).

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/wild_gate.py backend/tests/test_survival_wild_run.py
git commit -m "feat(W1): the wild gate's lives, headless, with a scripted owner and a liar, and its W1 criteria" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Run the gate**

This takes about 100 minutes (3 hours on a busy machine) at 5 or 6 in parallel; run it in the background and keep to 6 lives at once (the machine is shared).

Run, with `GATE` a new directory in your scratchpad: `python3 -m backend.scripts.wild_gate --days 150 --conditions gentle,untaught,taught --parallel 6 --out $GATE`, then `python3 -m backend.scripts.wild_gate --days 30 --conditions liar --parallel 6 --out $GATE`, then `python3 -m backend.scripts.wild_gate --check W1 $GATE`
Expected: the table in "Dry-run measurements" (every row passes, 6′, 7′ and 10′ included).

---

### Task 14: Manual check on the demo and the README

This task is for the controller. It rebuilds the demo image from the branch and restarts the demo stack on its own scratch volume: `mimo-l3demo-api` (:8011) and `mimo-l3demo-worker`, volume `mimo_l3demo`, at the natural pace. The demo's pet was hatched before W1, so it is gentle: the check there is that nothing changed for it. A wild newborn is watched on a second scratch stack of its own, `mimo-w1wild-api` (:8012) and `mimo-w1wild-worker` on a new volume `mimo_w1wild`, with a second viewer on :3001. The owner's real stack (`pets-api-1`, `pets-mimo-worker-1`) and its volume `pets_mimo_data` are never touched, and nothing uses port 5173.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Describe Wild World in the README**

In `README.md`, replace:

```markdown

## Current world rules
```

with:

```markdown

## Wild World

- **Wild or gentle.** A life hatches wild or gentle, for good (`backend/survival/wild.py`). `POST /api/lives/hatch` hatches a wild pet unless its body says `{"difficulty": "gentle"}`. Every world made before Wild World is gentle: its first tick grants it every survival lesson, silently, and it plays exactly as before. The HUD shows a "Wild" badge beside a wild pet's name, and `/api/mimo` has `difficulty`.
- **What a wild newborn knows.** Instinct only: it eats apples, carrots, bread, brown mushrooms, fish and meat, sleeps, flees, gathers, crafts tools and weapons, hunts, farms and explores. Eleven survival lessons are what it must learn: which red berries are safe, that nightberries (the dark purple ones) and red mushrooms are poison, that sunleaf cures sickness and cleans wounds, that a wool bandage stops a wound festering, how to make a campfire and that cooked food is safe, that food keeps in a chest, that torches keep the dark creatures away, that a shelter with a roof and a door keeps it safe, and that a bed is for sleeping. Until it knows them it builds no shelter, bed, campfire or torches round home, cooks nothing raw and keeps no food in a chest. The journal's **Survival** section lists all eleven, known or not, and how each was learned: from you, worked out alone, or known from the start.
- **Hazards, for a wild pet only.** Nightberry bushes look like berry bushes, and until Mimo knows them apart a meal of red berries eats some nightberries too; a nightberry or a red mushroom takes 5 health and gives a tummy ache. A raw meal can too (chicken most often). A tummy ache lasts 12 game minutes and a chill 25; while sick Mimo does not heal and loses health slowly, and a sickness can kill. One sunleaf eaten ends any sickness; a sick newborn nibbles one it finds nearby now and then by instinct, and feels better without learning why. Food spoils (raw meat in a day and a half, bread in six), half as fast in a chest, and spoiled food makes Mimo sick more often than not. A creature's blow can leave a wound that festers after 10 game minutes unless it is dressed with a bandage (a wool makes 2) or a sunleaf; the owner's bandage dresses it too. A night spent cold can bring a chill at dawn. The HUD shows what ails the pet ("Tummy ache · 11 min", "Wound festering"), and the pet looks it: pale and drooping when sick, shivering with a chill, a red mark on a wound and a white wrap once it is dressed.
- **Learning alone.** A wild pet works nine of its lessons out from what hurts it (`knocks.py`): each painful knock may teach the lesson it points at, a little likelier each time, and some experiences teach for sure (the first smelt teaches fire). "Pip worked out that cooking makes meat safe." is news in the owner's inbox. Two lessons only the owner can teach: that sunleaf cures sickness and cleans wounds, and that a wool bandage stops a wound festering. Without them every sickness runs its course and every wound festers until it heals by itself.
- **Mimo asks.** What puzzles a wild pet (red berries it found, a raw beef it carries, a cold night, a creature with glowing eyes, food gone bad) becomes a question in the inbox and the chat, with answer chips (`wonders.py`, `questions.py`), at most three open at once. A chip, a sentence in the chat ("Two logs and three sticks make a campfire.") or, for a yes-or-no question, a bare "yes" teaches the lesson, and Mimo waits a little before it risks what it asked about. A wrong answer is doubted and never learned: "Hmm, I'm not sure that's right. I'll be careful." The viewer shows "?" and a count beside the inbox button while questions wait. What the owner answers stays between the owner and Jev.
- **Worldgen.** Nightberry bushes grow on the berry bushes' ground (about two for every three berry bushes) and sunleaf on the green lands' grass, moss and mud, on columns where nothing else grew, in both ports; picked, they grow back.
- `/api/mimo` has `difficulty`, `survival` (the eleven lessons), `ailments` (`sick` and `wound`) and, in the inbox, `questions`. `POST /api/mimo/inbox/{id}/answer` takes `{"choice": n}` for a chip. `python3 -m backend.scripts.wild_gate` runs the balance gate's lives headless (`--check W1 DIR` applies its criteria).

## Current world rules
```

- [ ] **Step 2: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1926 tests` … `OK (skipped=6)`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`, the same with `-p "test_survival_days.py"`, `-p "test_survival_expedition_run.py"`, `-p "test_survival_making_route.py"`, `-p "test_survival_frontier_run.py"`, `-p "test_survival_away.py"` and `-p "test_survival_wild_run.py"`
Expected: `OK` each

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  373 passed (373)`, the build succeeds, eslint prints nothing.

- [ ] **Step 3: Commit the README**

```bash
git add README.md
git commit -m "docs(W1): the README's Wild World section" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Rebuild the demo on the branch, and start the wild stack**

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
docker run -d --name mimo-w1wild-api -p 127.0.0.1:8012:8000 -v mimo_w1wild:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 mimo-l3demo
docker run -d --name mimo-w1wild-worker -v mimo_w1wild:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 -e MIMO_ACTION_SCALE=1 \
  -e MIMO_TICK_SECONDS=1 -e TYPESAFE_API_KEY mimo-l3demo python -m backend.workers.mimo_worker
```

Expected: four container ids. W1 adds no table: the demo world reads as it is. Restart the viewer on :3000 against :8011 and start a second one on :3001 against :8012, then open `http://localhost:3000/preview` and `http://localhost:3001/preview`.

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8011 npm run dev -- --port 3000 --strictPort
cd frontend && VITE_API_URL=http://127.0.0.1:8012 npm run dev -- --port 3001 --strictPort
```

- [ ] **Step 5: Keep a wild snippet ready**

Save this as `wild.sh` in your scratchpad directory (not in the repo). Given a container name, it prints the difficulty, the survival lessons with how each was learned, the ailments, the knocks so far, the wonders met and asked, the open questions with their chips, and the newest W1 events:

```bash
docker exec -i "${1:-mimo-w1wild-api}" python - <<'PY'
import backend.survival.brain  # noqa: F401  (registers every W1 module)
from backend.survival.ailments import ailments_view
from backend.survival.questions import questions_view
from backend.survival.registry import LifeRegistry
from backend.survival.wild import difficulty, survival_view, wild_state
from backend.survival.world import SurvivalWorld, read_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
with world.connect() as db:
    state = read_state(db)
    print("difficulty", difficulty(state), "| health", round(state["vitals"]["health"], 1), "| ailments", ailments_view(state))
    for lesson in survival_view(db):
        print("  ", "known" if lesson["known"] else "     ", lesson["name"], lesson["source"] or "")
    wild = wild_state(state)
    print("knocks", wild["knocks"], "| shun", wild["shun"])
    print("wonders", {name: ("asked" if found.get("asked_at") else "met") for name, found in wild["wonders"].items()})
    for question in questions_view(db):
        print("  question", question["id"], question["text"], question["chips"], "yes/no" if question["yes_no"] else "")
    print("lots", state.get("lots"), "| chests", state.get("chest_lots"))
for event in reversed(world.events(300)):
    if event["kind"] in ("sick", "cured", "chill", "wound", "festering", "dressed", "spoiled", "figured", "asked",
                         "rested", "safe_night", "death"):
        print(event["kind"], "|", event["text"])
PY
```

- [ ] **Step 6: The demo's pet is gentle and nothing changed for it**

Within a minute of the worker's start, run `wild.sh mimo-l3demo-api`. Confirm `difficulty gentle`, every survival lesson `known from_start`, no ailment, no lot, no wonder and no question; that `curl -s http://127.0.0.1:8011/api/mimo | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["difficulty"], len(d["survival"]), d["ailments"], d["inbox"]["questions"])'` prints `gentle 11 {'sick': None, 'wound': None} []`; and that the owner sees no "Wild" badge on the HUD, a Survival section in the journal with every lesson marked "knew from the start", and no "?" beside the inbox. Over the next game hour the event log reads as it did before the rebuild: no `sick`, `figured`, `asked` or `spoiled` event, and the pet still builds, cooks and lights its home as before.

- [ ] **Step 7: A wild newborn**

Hatch on the wild stack: `curl -s -X POST http://127.0.0.1:8012/api/lives/hatch` (no body: wild). Confirm `wild.sh` prints `difficulty wild` with no lesson known, and the owner sees the "Wild" badge on :3001. Within the first game hour (a real hour), confirm Mimo meets its first wonders as it walks (red berries, red mushrooms or sunleaf seen; raw meat when it first hunts) and posts a question within about `ASK_GAP` of the first (the owner sees "?" and a count beside the inbox, and the question in the inbox with its chips, and in the chat), never more than 3 open. Confirm it does not build a campfire, a bed, a shelter or torches, and does not cook raw meat, while it does not know how.

- [ ] **Step 8: Teaching and answering**

Ask the owner to answer one question with its true chip in the inbox: the chip's lesson is learned ("Oh, … Thank you for teaching me!" in the chat, the lesson marked "from you" in the journal's Survival section) and the question closes. Ask the owner to answer another with a wrong chip: "Hmm, I'm not sure that's right. I'll be careful." and nothing learned. Ask the owner to type one line of the teaching table in the chat (for example "Two logs and three sticks make a campfire."): the lesson is learned from the chat as from a chip, and within the next game hour Mimo makes a campfire when it is cold. If a yes-or-no question is open ("Are those berries safe to eat?"), a bare "yes" in the chat answers it.

- [ ] **Step 9: Hazards and knocks**

Over the following hours on the wild stack, watch `wild.sh` for what W1 brings: a `sick` event after a taste of red berries, a red mushroom or a raw meal (the HUD's ailment line, "Tummy ache · 11 min", and the pet's pale tint and droop); a `cured` event when it finds and eats a sunleaf; `spoiled` food in its arms; a `chill` at dawn after a cold night (the pet shivers); a wound after a blow (a red mark, and a white wrap once dressed); and a `figured` event when it works a lesson out ("Pip worked out that …", news in the inbox, the lesson marked "worked it out" in the journal). Note each one seen, and any that is not seen in the first game day; that is expected for the rarer ones. Confirm no `figured` event is about sunleaf or bandages, and that a `cured` event after a nibble leaves sunleaf "?" in the journal: only the owner teaches those two.

- [ ] **Step 10: A quiet worker**

Confirm `docker logs mimo-l3demo-worker 2>&1 | grep -c "crashed"` and the same for `mimo-w1wild-worker` print `0` (or only lines from before the restart), and that the model calls today stay within `MIMO_MAX_DECISIONS_PER_DAY`. Leave the demo running on the new image for the owner. Stop the wild stack when the owner is done with it (`docker rm -f mimo-w1wild-api mimo-w1wild-worker`; the volume `mimo_w1wild` may be removed with `docker volume rm mimo_w1wild` once the owner agrees).

## Spec coverage

| Spec (W1, its resolutions, testing, the gate) | Where |
|---------------------------------|-------|
| Wild and gentle, set at hatch, for good; the API hatches wild, `hatch()` gentle | Task 1 (`wild.difficulty`, `new_survival_state`, `hatch`, `create_life`, `Hatching`; tests `test_hatch_is_gentle_unless_told…`, `test_the_api_hatches_wild_by_default…`; resolution 3) |
| A world with no key is gentle; its first tick writes it and grants every survival lesson (`lesson` + `born_knowing`), silently; an archive is never written | Task 1 (`wild.settle` in `advance_world`; tests `test_a_world_from_before_w1_reads_gentle…`, `test_a_gentle_pet_is_granted…silently`, `test_a_dead_pets_world_is_never_written`) |
| Born-knowing lessons stay out of every tally (the journal's count, investigate's and tinker's facts, Mind's insight) | Task 1 (`journal.learned`, `Situation.lessons`, `insights`, `replies`; `test_the_journal_the_situation_and_the_thoughts_leave_them_out`; resolution 4) |
| A gentle world is today's game; it never has a sickness, a wound, a lot or a question | Every hook returns early for a gentle pet (Tasks 3, 5–10); the gentle tests of each (`test_a_gentle_pet_is_never_gated`, `…is_never_ailing`, `…has_no_lots`, `…never_knocks`, `…never_asks`); the dry run's 3-day event log; gate criterion 13 |
| What a wild newborn knows: instinct foods, the untried ones, everything L1 to L5 and Making do but what the lessons gate | Task 6 (`wild.FAMILIAR`, `meals.untried`, `trusted`), Task 3 (only the table's gates) |
| The eleven survival lessons: kind `survival`, `wild:<name>`, one sentence each, no negation, one side of a pair | Tasks 1 and 2 (`wild.SURVIVAL`, `journal.LESSONS`; `test_the_lessons_are_named_after_wild_and_each_fact_teaches_itself`; resolutions 5, 6) |
| What each lesson unlocks (the table) | Task 3 (`PURPOSE_LESSONS`, `GOAL_LESSONS`, `FITTING_LESSONS`, cook, camp, expedition, warm_up; every row known and unknown in `test_survival_wild_gates.py`), Task 5 (find_herb, take_herb, gather_herbs), Task 6 (eating), Task 7 (keeping), Task 8 (dress_wound; resolution 7) |
| Hazard 1, poison lookalikes: nightberry bushes seen as red berries; the share roll; 5 health and a tummy ache; the shun | Task 4 (the bushes), Task 6 (`wild_meal`, `share`, `eat_wild`, `sick_from`, `SHUN`; `test_an_untaught_meal_of_red_berries_eats_nightberries_at_their_share`, `test_a_taught_pet_never_picks_eats_or_keeps_a_nightberry`, `test_a_sickness_from_the_group_shuns_it_two_game_days`; resolution 10) |
| Hazard 2, sickness: a tummy ache and a chill, their drains and what they slow, no healing, mood, one at a time, can kill; sunleaf ends any; take_herb, find_herb, the instinct nibble; raw meals | Task 5 (`ailments`, `vitals.Ailing`, `herbs`; resolution 9), Task 6 (raw meals, `RAW_RISK`, channel 201) |
| Hazard 3, spoilage: shelf lives, lots, a chest halves it, spoiled food, keeping's help | Task 7 (`spoilage`; `test_the_lots_follow_every_step_kind_and_always_sum_to_the_counts`; resolution 11) |
| Hazard 4, wounds: a blow's chance, festering, healing, dressing by bandage, sunleaf or the owner's care | Task 8 (`wounds`, `ailments.open_wound`, `dress`; resolution 12) |
| Hazard 5, cold nights: a chill at dawn; the floor | Task 8 (`tend_night`, `dawn`; resolution 13) |
| Learning alone: knocks, their growing chance, curiosity, sure knocks, `figured`; sunleaf and bandage never learned alone (spec resolution 29) | Task 9 (`knocks`, `OWNER_ONLY`, `test_sunleaf_and_bandages_are_never_learned_alone`; resolutions 14, 21) |
| Mimo asks: wonders, their words, chips and claims; `OPEN_MOST`, `ASK_GAP`, once a life; the shuffle; hesitation | Task 10 (`wonders`, `questions.ask_wonders`; resolutions 15, 16) |
| Answering: a chip, yes or no in the chat, anything else in the chat; wrong answers doubted; a lesson taught another way closes the question | Task 10 (`answer_question`, `REWORDS`, `TAUGHT_HOOKS`, the "answer" question), Task 2 (the parser) |
| The teaching table: every line taught or doubted as listed; warnings teach | Task 2 (`TEACHES`, `DOUBTED` in `test_survival_wild_teaching.py`; `lessons.warned`) |
| Worldgen: nightberry bushes and sunleaf, both ports, parity, the fixture, never in the legacy clearing | Task 4 (`wild_herb`, `wildHerb`, the fixture's columns; resolution 8) |
| State and API: `difficulty`, `survival`, `ailments`, the inbox's `questions`, the answer endpoint's `choice`; no table, no column; GETs read-only | Tasks 1, 5, 8, 10 (the payload), the Global Constraints |
| Moments, news and voice; the routine and notable kinds; "You were right" for survival lessons | Task 11 (`wild_news`, `SEEN_BY`; resolution 17) |
| Viewer: the ailment line, the badge, the pet's look, the questions and chips, the Survival section, the memorial | Task 12 (`wild.ts`; resolution 18) |
| Privacy: an answer never reaches Luna | Task 11 (`AnswersNeverReachLunaTests` in `test_survival_mind_privacy.py`), Task 10 (the "asked" moment is about the owner) |
| No model call: rules only in the tick and the Talker's chore; `no_model` in every headless test | Global Constraints; Tasks 2, 10, 11 and 13 run the Talker with the counting stub |
| The gate harness and the W1 gate, with criteria 6′, 7′ and 10′ (spec resolution 29) and the health lost to hazards | Task 5 (`ailments.lose`), Task 6 (poison), Task 13 (`wild_gate.py`, `CheckTests`; resolutions 19, 20, 21), "Dry-run measurements" |
| The existing sims pass unchanged for a gentle world | The dry run's slow sims ("Dry-run measurements") |

Spec gaps the plan fills or leaves (the controller ledgers them):
- The spec names registries on `wild` (`wild.KNOCKS`, `wild.WONDERS`, `wild.AILMENTS`, `wild.PERISHABLE`); they live beside the code that uses them (resolution 2).
- "Stands within 8 blocks of a fire it did not make" (the fire lesson's sure knock) needs W2's and W3's fires and is not wired in W1 (resolution 14).
- The spec does not say when a lot joins another, how many lots a stack keeps, or where a chest's lots live: resolution 11 sets them.
- The chips' order is a seeded shuffle stored with the question, so only the index is sent and stored (resolution 16).
- "The first 3 game days" in criterion 10′: a life is born on day 1.0, so the gate counts what happened by day 4.0; "game days 0 to 30" in 6′ are the first 30 game days, 1 to 30 (resolution 19).
- "Health lost to hazards" in 6′: the spec names sickness, poison, festering and chills; the plan counts the drain of a sickness (a tummy ache or a chill) or a festering wound, and a poison plant's 5 health, in `state["wild"]["lost"]` (resolution 19). Freezing and a creature's blows are not W1 hazards and are not counted.
- The pet's "ears droop": the pet model has no separate ears, so the whole pet tilts forward a little (resolution 18).

## Dry-run measurements

These are the revised plan's (resolution 21). The plan as first written was dry-run the same way on `41a919b` and `5da9fba`; its gate is summarised in resolution 20 and at the end of the notes below.

### The dry run, task by task

The code was written and measured task by task on a scratch branch, rebased as the L5 final fix wave landed (`94dad38`, `41a919b`, `5da9fba`, `e021753`), and revised on `e021753` after the controller's ruling. The plan was generated from it and applied with `apply_plan.py`, task by task in order, to a `git archive e021753` copy (node_modules linked), with the fixture regenerated after Task 4 and the checks the tasks name after each. The load average on the shared machine was 10 to 24 throughout (other gate runs shared it), so the times are slow.

| Task | Applied | Backend | New | Frontend |
|------|---------|---------|-----|----------|
| base `e021753` | | `Ran 1828 tests` `OK (skipped=5)` | | `Tests  366 passed (366)` |
| 1 | yes | 1837 OK | 9 | |
| 2 | yes | 1845 OK | 8 | |
| 3 | yes | 1852 OK | 7 | |
| 4 | yes | 1857 OK | 5 | 367 passed (1 new), build ok, eslint clean; fixture 43,588 cells |
| 5 | yes | 1868 OK | 11 | |
| 6 | yes | 1880 OK | 12 | |
| 7 | yes | 1889 OK | 9 | |
| 8 | yes | 1899 OK | 10 | |
| 9 | yes | 1908 OK | 9 | |
| 10 | yes | 1918 OK | 10 | |
| 11 | yes | 1923 OK | 5 | |
| 12 | yes | 1923 OK | 0 (two changed) | 373 passed (6 new), build ok, eslint clean |
| 13 | yes | 1926 `OK (skipped=6)` | 3 (1 slow) | |
| 14 | yes | 1926 `OK (skipped=6)` | 0 | |

After Task 14 the copy matches the scratch branch file for file. Each task's failing run (Step 2) was taken the same way: the task's test files on the code of the task before it. Tasks 1 to 4 are the same as in the plan as first written, file for file; the revision changes Tasks 5, 6, 8, 9, 13 and 14.

### A gentle world is today's game

Seed 8, 3 game days, the rules chooser with no model, on `e021753` and on its copy after Task 14: 257 events without the Talker and 260 with it, identical event for event (time, kind and text), and the same inventory, vitals and position at the end. The gate's gentle lives (below) never had a sickness, a wound, a lot or a question.

### The slow sims (MIMO_SLOW_TESTS=1, on the copy after Task 14)

| Sim | Result | Time |
|-----|--------|------|
| `test_survival_sim.py` | `Ran 7 tests` OK | 853 s |
| `test_survival_days.py` | `Ran 3 tests` OK | 538 s |
| `test_survival_expedition_run.py` | `Ran 2 tests` OK | 62 s |
| `test_survival_making_route.py` | `Ran 1 test` OK | 4 s |
| `test_survival_frontier_run.py` | `Ran 5 tests` OK | 904 s |
| `test_survival_away.py` | `Ran 2 tests` OK | 43 s |
| `test_survival_wild_run.py` | `Ran 3 tests` OK | 1090 s (15 s without the slow one) |

All six existing sims pass unchanged: their pets are gentle.

### The W1 gate

On the final numbers (resolutions 20 and 21), on the copy after Task 14 (`e021753` with the plan applied), seeds 3, 5, 8, 11, 21 and 42: `untaught`, `taught` and `gentle` for 150 game days and `liar` for 30, at scale 60, 5 lives at a time (about 3 hours at that load). `--check W1`:

| Criterion | Result | Measure |
|-----------|--------|---------|
| 1 taught: all 6 alive on day 150 | PASS | 6/6 |
| 2 taught: each health mean 75 or more | PASS | lowest 99.76 |
| 3 taught: each at most 3 near-death days | PASS | most 0 |
| 4 taught: each at most 150 sick minutes | PASS | most 3 |
| 5 taught: 3 of 6 lamps on levers; the furthest within one of gentle's | PASS | lamps 6/6; machines taught 7, gentle 7 |
| 6′ untaught, first month: sick minutes 3× taught; health lost to hazards 3× taught and 100 a life | PASS | sick 406 vs 2; lost 1197 vs 4, 200 a life |
| 7′ untaught, a life without the owner: sick minutes 5× taught; deaths and near-death days 6 or more | PASS | sick 518 vs 5; 2 deaths + 5 near-death days = 7 |
| 8 untaught: at most 3 of 6 die, none before day 5 | PASS | 2 deaths, days 21.15 and 69.38, both of sickness |
| 9 untaught: alive on day 60 knows 8 of 11 learned alone | PASS | 8 each (seeds 3, 5, 8, 11, 21) |
| 10′ untaught: 4 wonders and 3 questions in 3 days; never more than 3 open | PASS | (met, asked) {3: (4, 3), 5: (5, 4), 8: (7, 3), 11: (6, 3), 21: (5, 4), 42: (5, 3)}; most open 3 |
| 11 liar: nothing learned from a false chip or claim | PASS | none |
| 12 liar: deaths by day 30 no more than untaught; sick minutes at most untaught + 30 | PASS | 1 vs 1; equal on every seed |
| 13 gentle: all alive; no sickness, wound, lot or question; every lesson from the first tick | PASS | 6/6, clean, known |
| all: no model call and no logged error | PASS | 0 calls, 0 errors |

The lives:

| Life | Died | Health mean | Sick min (first month) | Lost to hazards (first month) | Near-death days | Lessons alone | Machines |
|------|------|-------------|------------------------|-------------------------------|-----------------|---------------|----------|
| untaught 3 | | 98.63 | 96 (96) | 243 (243) | | 8 | 7 |
| untaught 5 | | 99.12 | 75 (63) | 197 (156) | | 8 | 6 |
| untaught 8 | | 97.69 | 63 (39) | 278 (131) | 114 | 8 | 7 |
| untaught 11 | day 69.38, sickness | 93.81 | 148 (72) | 425 (214) | 69 | 8 | 6 |
| untaught 21 | | 99.29 | 59 (59) | 164 (164) | | 8 | 7 |
| untaught 42 | day 21.15, sickness | 85.60 | 77 (77) | 289 (289) | 19, 20, 21 | 6 | 0 |
| taught 3, 5, 8, 11, 21, 42 | | 99.76 to 99.98 | 0 to 3 | 0 to 6 | | 0 or 1 (11 known) | 5 to 7 |
| gentle 3, 5, 8, 11, 21, 42 | | 99.96 to 99.99 | 0 | 0 | | 11 from the start | 6 or 7 |
| liar (30 days) | seed 42, day 21.15 | 85.6 to 98.0 | as untaught | as untaught | seed 42: 19, 20, 21 | 6 to 8, none from the liar | |

No untaught pet learned sunleaf or bandages (the nibble cured one sickness on every seed but seed 21 and taught nothing). They learned fire first (days 1.2 to 2.3, their first smelt), the bed, the shelter and keeping within 11 days, cooking on days 3 to 40 (seed 42 never), the food lessons as they met them (days 2 to 51), and light never. Seed 42 never learned cooking; tummy aches, two chills and a festering wound it could not dress left it near death on days 19 to 21, and it died of sickness on day 21. Seed 11 was sick ten times (it knew the nightberries apart only on day 46) and died of a sickness on day 69, hungry. The liar's pets fare as the untaught ones do up to day 30: every false chip is doubted, and the sick minutes are the same on every seed.

The untaught lives are the same, byte for byte but for their wall times, as the last tuning run's (resolution 20's drains): every life is deterministic from its seed.

### Notes for the controller

- The plan was revised by the ruling of 2026-09-27 (spec resolution 29, resolution 21 here). Tasks 1 to 4 did not change; `1139c50` (Task 1) and `eebbdec` (Task 4), already on the branch, match the revised plan's Tasks 1 and 4 file for file. Tasks 5, 6, 8, 9, 13 and 14 changed: `ailments.lose` and `state["wild"]["lost"]`, the tuned drains and raw-meal chances, `meals.eat_raw_left`, the removed `FESTERS` hook, `knocks.OWNER_ONLY` and the lower knock chances, the gate's 6′, 7′ and 10′ with a unit test, the README.
- Found while measuring the revision, fixed in Task 6 (resolution 10): a starving wild pet with full arms hunted and fished again and again and left every piece of meat behind (a wild pet ate only riskless food it could not carry, and its arms held none), and starved. It killed two untaught pets in a tuning run and nearly starved a taught one in the first plan's gate (17 starving minutes); with the fix the taught pets never starve. What is left of it: a pet that knows cooking still leaves raw food it cannot carry behind until it is starving, so full arms can keep it hovering near starvation, sick from the raw bites it takes (one tuning run lost an untaught pet that way on day 93). Freeing its arms for food is L-level carrying, left as it is.
- The knobs at their limits (resolution 20): the knock chances (a second step lower breaks criterion 9), and the chill's drain (1 per 25 game s killed three pets in their first three weeks). The margins are thin: criterion 9 passes with exactly 8 lessons on every seed alive on day 60, and 7′ with 7 against 6.
- Mimo's sunleaf question keeps the spec's words ("There's a little yellow herb here. What is it for?"); the ruling's "This little yellow herb — is it good for anything?" read as an example, not new words.
- Earlier finds, fixed in the plan: a raw meal's risk was dropped when the eat step started (Task 6); food that spoiled while eaten crashed the eat hook (Task 7); a meal of red berries went on after its first poisoning (Task 6).
- The plan as first written, for the record: its gate passed 11 of the first 14 rows (the first criteria 6, 7 and 10 failed: untaught sick minutes 299 against 4, near-death days 1, health means 97.6 against 99.9, and seed 3's 4 wonders).
