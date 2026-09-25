# Living World L5: Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make distance from home matter, as the owner asked ("the farther from the center you wander the harder the enemies get but better loot"): danger rings around home (home ground, the near wilds, the far wilds, the frontier and the deep frontier) that make the hostiles born in them tougher (35 % more health a level, a harder blow every two levels, elders from the frontier on, one more hostile allowed a level) and richer (more gloom dust, then gold nuggets and a new gem, amber, then diamonds, and a chance of an extra ore when mining); a new hostile of our own, the thornback, a slow armoured crawler of the far wilds that walks by day and that only arrows hurt well; small ruins that worldgen stands in some regions, in the Python and TypeScript ports alike, each with an old chest whose loot the server rolls by the ruin's ring the first time Mimo opens it; the loot put to use (a warding lantern of gloom dust that keeps hostiles six blocks off, amber-studded armor a step past iron, gold for the tool ladder sooner); and a pet that weighs risk against reward: a "riches farther out" goal and its "seek riches farther out" trip, offered only to a pet armed, armored, fed and healthy enough for the ring the trip leads into, flee and fight lines that rise far from home, the walk home started early enough to be home before dark, and the ring and its readiness in the model's payload; the viewer names the ring on the HUD, shades the rings on the minimap, lights elders faintly, draws the thornback, amber armor and the ruins; headless checks that a pet near home lives as before, that a geared pet goes to the far wilds, loots a ruin and is home by nightfall, that an ungeared pet is never offered the trip, and that the creatures still cost under 20 ms a slice out there.

**Architecture:** Everything registers into a registry. `backend/survival/rings.py` keeps the rings: their table, the centre (the home Mimo built, else its birthplace) and the ring Mimo stands in, kept in `state["frontier"]` by the tick (`tend_frontier`, from `brain.notice_step`, before the goal is tended) so steps and creatures read a ring without the database, and what Mimo needs to go into each ring on purpose (`ready_ring`, `short_of`). New modules register into hooks that small edits add to existing modules: `creatures/ringed.py` shapes a hostile at birth (`darkness.BIRTHS`), grows the cap (`darkness.MORE_ROOM`) and Mimo's caution (`defense.CAUTION`); `creatures/thornback.py` registers its kind (with the new `Kind.shell` and `Kind.daylight`), its spawner (`simulate.SPAWNERS`) and `defense.BOW_ONLY`; `loot.py` adds ring drops (`combat.EXTRA_DROPS`) and mining luck (`steps.MINED`); `ruins.py` sees ruins and notes opened chests after each step (`steps.OBSERVERS`, which the brain calls), registers the `open_chest` step and the `loot_ruin` purpose (and its urge, `goals.URGES`); `frontier_gear.py` registers the warding lantern's light, recipes' stations and crafting orders (`toolmaking.MORE_ORDERS`), its barrier (`acts.BARRIERS`) and the `ward_home` purpose, and amber armor's cuts (`harm.ARMOR`); `frontier.py` registers the frontier goal, the "riches" trip reason (L4a's `trips.Reason`, with a reach of 480), the far home and the early walk home (`purposes.FAR_HOMES`, `purposes.HOMEWARD_LEADS`). Worldgen gains ruins as a pure function of seed and region in `backend/services/worldgen.py` and `frontend/src/engine/worldgen.ts`, checked cell by cell by the shared fixture. The viewer gets a pure `frontend/src/survival/frontier.ts` module.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-living-world-design.md`: the milestone table's L5 row, the whole "L5 Frontier (outline; detailed in its plan)" section, "Owner input, 2026-09-24 morning" (the owner's "harder the enemies ... better loot"), the Decisions ("Original creatures", "Server owns creatures", "Creatures stay cheap", "Light keeps monsters away", "Cost") and "Error handling and testing". It builds on L4a (`docs/superpowers/plans/2026-09-23-living-world-l4-purposeful-life.md`: goals, trips with reasons and their `Reason.reach` hook for L5, curiosity) and runs after L4b (`docs/superpowers/plans/2026-09-23-living-world-l4b-curious-mind.md`). It follows the shape of the L3 and L4a plans. The code on branch `worthy/23_09_2026/survival_core` at `62a0e5a` (all of L4a, with its final fix wave and follow-ups) is the "old" text every task edits (resolution 1).

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls: the headless runs use the rules' Chooser (or L4a's fake Jev). Every chance is rolled from the world seed (`nature.roll`, `creatures.moves.roll`); nothing reads `random` or the clock.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments, no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components. No stylesheet changes: the HUD uses Tailwind classes inline, as it does now.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. Read-only GETs never write. L5 adds no table and no column: the rings live in Mimo's state (`state["frontier"]`: `center`, `birthplace`, `ring`, `reached`, `far_at`), the warding lanterns it hung in `state["wards"]`, the thornback's spawn clock in `state["thornback_at"]`, the ruins it saw in `memory_places` (kind `"ruin"`, at the chest, noted with the ring's name, data `{"opened": at}`), an old chest's contents in `state["chests"]` like any chest's, a hostile's ring, full health, extra damage and elder flag in its creature state (`ring`, `most`, `fiercer`, `elder`).
- Worldgen stays a pure function of the seed and the cell: the rings never change terrain, and ruins are placed by seed and region alone, identically in `backend/services/worldgen.py` and `frontend/src/engine/worldgen.ts`. After any worldgen change run `python3 -m backend.scripts.worldgen_fixture` and both parity suites. The one new block, `warding_lantern`, goes at the very end of `shared/blocks.json` so older ids never change.
- **No model call inside the tick.** Rings, spawns, drops, ruins, loot, trips, the walk home and readiness are all rules in the tick; Jev only sees the ring and readiness in the payload of the purpose call it makes anyway. Validity checks, scores, facts and a reason's value never write; `open_chest` writes the chest it opens, the observers the ruin place and `state["wards"]`.
- A crashing hook never stops a tick or the worker: `BIRTHS`, `MORE_ROOM`, `CAUTION`, `SPAWNERS`, `EXTRA_DROPS`, `MINED`, `OBSERVERS`, `FAR_HOMES` and `HOMEWARD_LEADS` are each guarded and logged once (`once.log_once`), counting as nothing; a crashing barrier is caught with its creature's turn (`simulate.take_turns`), a crashing crafting order with craft_tools' validity (`purposes.is_valid`), a crashing reason part by `trips.guarded`.
- Values from the spec ("L5 Frontier"): the rings are home ground (under 48 blocks from home, danger 0), the near wilds (48–128, 1), the far wilds (128–256, 2), the frontier (256–512, 3) and the deep frontier (512 and beyond, 4); the centre is Mimo's built home, or its birthplace until a home stands, and moves with home; home ground plays exactly as today. Hostiles that spawn in a ring get +35 % health per danger level and +1 damage per two levels; the spawn cap grows by one per level; from danger 3 gloomlings and skitters can be elder variants, tougher and faintly glowing in the viewer. The thornback walks the far wilds and beyond (danger 2+), a slow, heavily armoured crawler that hits hard, arrows its weakness; names and designs our own. Hostile drops improve by ring: from danger 1 gloom dust gets likelier, from danger 2 gold nuggets and amber, from danger 3 rare diamonds; mining in a ring has a small chance of an extra ore drop, rising per level. A small ruin (stone-brick walls, mossy cobblestone, a chest) sometimes stands in a region, placed by worldgen as a pure function of seed and region in both ports; the server rolls its chest's loot the first time Mimo opens it, by the ruin's danger ring (nearer ruins hold food, arrows and iron, farther ones gold, amber and diamonds); ruins are landmarks exploring can aim for. Gloom dust with a lantern makes a warding lantern: light 15, and hostiles won't step within 6 blocks of it; amber with iron makes amber-studded armor, a step past iron; diamonds and gold feed L3's tool ladder sooner. The Situation knows Mimo's ring and each target's; the rules offer frontier trips ("seek riches farther out") only when Mimo is armed, armored and healthy enough for that ring; flee and fight thresholds account for the ring; Mimo heads home before dark when far out; Jev sees each option's ring and its gear readiness. The HUD names the current ring ("Far wilds · danger 2"); the minimap shades the rings faintly around home; elder hostiles glow; the thornback gets its own voxel model; ruins and their chests are drawn. Tests: a pet that stays near home lives as before; a geared pet survives a trip to danger 2 and back with better loot; an ungeared pet is never offered a frontier trip; ruin loot is deterministic from seed and ring; worldgen parity holds for ruins.
- Performance budget (spec "Error handling and testing"): creature simulation plus light checks cost no more than 20 ms per 60-game-second slice on average, measured at the surface (Task 9 holds it in the far wilds, where the cap is 10).
- `MIMO_TIME_SCALE` and `MIMO_ACTION_SCALE` (both default 1) are for manual runs only. L5 adds no settings.
- Never run `docker` or `docker compose` in Tasks 1–10. Task 11 is the controller's manual check on the demo stack (`mimo-l3demo-api` on :8011 and `mimo-l3demo-worker`, volume `mimo_l3demo`); never touch, mount or migrate the owner's real volume `pets_mimo_data` or the real stack (`pets-api-1`, `pets-mimo-worker-1`). Never open, read or print `.env` or any key; the owner watches the viewer in the Browser pane, so no task drives it.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (1113 run at `62a0e5a`: `OK (skipped=1)`)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_rings.py" -v`
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` (a few minutes), the same with `-p "test_survival_days.py"`, and (from Task 9) `-p "test_survival_frontier_run.py"` (7 to 15 minutes, 40 under heavy load: three pets, geared and not, for four game days at 1x)
- Regenerate the worldgen fixture after a worldgen change: `python3 -m backend.scripts.worldgen_fixture`; the two parity suites: `python3 -m unittest discover -s backend/tests -p "test_worldgen*.py"` and `cd frontend && npx vitest run src/engine/worldgen.test.ts src/survival/overheadMap.test.ts`
- Frontend tests: `cd frontend && npm test` (308 pass at `62a0e5a`)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint src/survival src/engine` (prints nothing when clean)

Each task says how many tests it adds. If the real starting totals differ (L4b adds tests of both kinds), expect the same increases on top of them.

Transcription: every edit is a fenced block, either a whole new file ("Create `path`:"), or a "replace: … with: …" pair in a named file ("In `path`, replace:", then "and replace:" for more pairs in the same file). Old texts are kept short, so a task still applies when a neighbouring line changes. The fixture `shared/worldgen-fixture.json` is never transcribed: Task 5 regenerates it with the script. The dry run applied each task with the controller's apply script (`.superpowers/sdd/2026-09-23-living-world-l4-purposeful-life/apply_plan.py`) to a `git archive` copy of `62a0e5a`, then ran the task's checks (resolution 1).

## Plan-level resolutions

The spec gives L5 as an outline. These are the details; every task follows them and the controller ledgers them.

1. **Base and anchors.** `62a0e5a`: L1–L3 with their fix waves, and all of L4a (Tasks 1–13, its fix rounds and its final fix wave: the one home lookup in `home.py`, day trips that reach out to 240 blocks as the land nearer home is walked, food first when hungry, going home from as far as a day trip goes; and its follow-ups to `62a0e5a`: going home from any distance, wander free of its cooldown out past 64 blocks, farm work kept near home, storage and pen fixes). The plan was written against `8882757` (L4a's Tasks 1–11), dry-run at `0ae3a97` and `0c4a498`, and rebased and dry-run again, whole, at `62a0e5a`: the final fix wave moved three of Task 8's anchors (`home_of`, the `purposes` import in `reflexes.py`, `beyond`'s last line) and gave L5 the one home lookup, which the frontier goal now reads (resolution 14). L4b comes later: the controller re-runs this plan's dry run on the branch once it has landed. The edits keep off the lines those plans replace: in `SurvivalHud.tsx` they anchor on `homeText` and the home line (L4a replaces the types import and the purpose line, L4b the home line with a line before it, which keeps it), in `hud.ts` on L3's `gather_flint` line (L4a and L4b change the `improve_home` line), in `types.ts` on `burning_at` and `sheltered` (L4a and L4b add their fields at the end), in `purposes.py` on `homeward`, the end of `home_of`'s docstring and its last line, and `late_day` (L4b edits `at_home` and `go_home_valid`), in `trips.py` on `FINDS`, `beyond`'s docstring and its last line (L4a's fix rounds edited the module docstring, `cool_down` and the line that adds a spot), in `reflexes.py` on the `senses` import line, above which a line of its own imports `homeward_from` (L4b replaces the `purposes` import), and the homeward window line (L4b edits the purpose line under it), in `pickers.py` on the `purposes` import and `**threats_payload(s),` (L4b edits the `exploring`/`goals` imports and the last payload line), in `snapshot.py` on the `registry` import and `"sheltered": indoors,` (L4b edits `brain_view`, `indoors = ...` and the curiosity line), in `brain.py` on `tend_goal`, `note_ground`'s find and the creature imports (L4b adds lines after `look_after` and `tend_curiosity`), and in `test_survival_pickers.py` on the payload set's second line (L4b edits its last line). If an anchor moved anyway, the controller re-anchors the same change on the line next to it.
2. **Registries, not rewrites.** New modules: `rings.py`, `creatures/ringed.py`, `creatures/thornback.py`, `loot.py`, `ruins.py`, `frontier_gear.py`, `frontier.py` (backend) and `frontier.ts` (viewer). Hooks added to existing modules, each a list the new modules register into: `darkness.BIRTHS`, `darkness.MORE_ROOM` (and `darkness.cap`), `defense.CAUTION` (`flee_below`, `fight_from`), `defense.BOW_ONLY` (`outmatched`), `simulate.SPAWNERS`, `combat.EXTRA_DROPS` (`more_drops`), `steps.MINED`, `steps.OBSERVERS` (called by `brain.observe_step`), `toolmaking.POOLED` and `toolmaking.MORE_ORDERS`, `acts.BARRIERS` (`barred`), `purposes.FAR_HOMES` (`far_home`) and `purposes.HOMEWARD_LEADS` (`homeward_from`); `Kind` gains `shell` and `daylight`. Registries that already exist take L5's entries from the new modules: `KINDS`, `REASONS`, `GOALS`, `PURPOSES`, `STEP_KINDS`, `goals.URGES`, `goals.ADVANCES`, `light.BLOCK_LIGHT`, `harm.ARMOR` and `harm.SLOTS`, `toolmaking.STATIONS`, `structures.STANDS_IN`, `storage.KEEP`, `carrying.TREASURES`. Recipes are data in `crafting.py`, as L3's are. `brain.py` imports the new modules and calls `tend_frontier`.
3. **The rings** (Task 1). The centre is the home place when Mimo built it (`memory_places` kind `"home"` noted `"built"`), else its birthplace: where it stood when the tick first tended the rings, or, for a life from before L5, its oldest home place (a sheltered spot it found, near where it hatched). `tend_frontier` runs after every vitals step, before `tend_goal` (the frontier goal's validity reads the centre), with one read of the home place. The first time Mimo stands in the far wilds, the frontier or the deep frontier is a notable `found` event ("Pip reached the far wilds for the first time."), so curiosity counts it as a new place; the near wilds are too close to announce. `/api/mimo` gains `ring` (`{"level", "name", "center": {"x", "z"}}`, read from the state: null before the first tend).
4. **Readiness** (Tasks 1 and 8). Rings 0 and 1 are open to every pet. The far wilds take a stone sword or better (or a bow with 8 arrows in its place), armor that takes at least a fifth off a blow (L2's leather cap and tunic), 70 health and 30 hunger of food carried (half a day's); the frontier an iron sword or better, a bow and 8 arrows, iron armor (45 %) and 80 health; the deep frontier a diamond sword, a bow and 16 arrows, amber-studded armor (60 %) and 90 health. `short_of(s, ring)` says what is missing in words; `gear_short_of` weighs only weapons and armor (the goal's validity: a pet does not give its goal up when a blow or a meal moves its health or food below the line; the trip waits instead).
5. **Tougher hostiles** (Task 2). A hostile born in ring n (measured where it is born) has `health × (1 + 0.35 n)` and `+ n // 2` damage a blow; from the frontier (3) a gloomling or skitter is an elder one time in four (one in two in the deep frontier), with 1.5 times the health again and one more damage. The creature state keeps `ring`, `most` (its full health, which the health bar reads), `fiercer` and `elder`; `/api/mimo` sends `elder: true` for one. Home ground is untouched. The cap on hostiles alive near Mimo (L2's 8) grows by the level of the ring Mimo stands in.
6. **A warier pet** (Task 2). From the far wilds on, Mimo flees 5 health points sooner a level (L2's 35: 40 in the far wilds, 45 in the frontier) and stands its ground only from 5 more (L2's 50: 55, 60). Far from home a flight runs away from the threat, not all the way home: the refuge is a built home within 128 blocks, as before L5 (Task 8, since `home_of` now finds the home farther out).
7. **The thornback** (Task 3). 24 health, 1.2 s a block, 4 damage every 1.8 s from 1.6 blocks, 0.9 blocks tall, shell 0.6 (a sword or fist blow does 40 %; an arrow its full 5), walks by day (`daylight`: `sunlit` leaves it be); drops 1–2 flint and a leather hide 3 times in 10. It spawns only while Mimo stands in the far wilds or deeper: one chance every 90 game seconds, by day or night, of 0.35 (far wilds), 0.5 (frontier) or 0.65 (deep frontier), on open ground 20–40 blocks from Mimo, while fewer than 2 thornbacks are near and the cap has room; born through `darkness.born`, so it is toughened by its ring (41 health in the far wilds). It is in `defense.BOW_ONLY`: with a bow and arrows Mimo shoots it even in sword reach, without them it never swings at it and runs when it comes within 6 blocks. At a quarter of Mimo's pace it never catches a pet that runs.
8. **Better drops** (Task 4). A hostile born in ring n also drops, rolled from the world seed and the creature on channels of its own: from danger 1 a gloomling one more gloom dust (0.4, +0.2 a level); from danger 2 1–3 gold nuggets (0.3, +0.1 a level) and amber (0.12 a level past 1; a thornback 0.15 more); from danger 3 a diamond (0.06 a level past 2); an elder's chances doubled. Measured over 600 creatures each: gloom dust 0.4 at 1, gold 0.3 and amber 0.12 at 2, diamonds 0.06 at 3, a thornback's amber 0.27 at 2, an elder's amber 0.48 at 3. Animals never drop more.
9. **Mining luck, gold nuggets and amber** (Task 4). Mining an ore (coal, iron, copper, gold, diamond) in ring n drops one more of what it gives with a chance of 5 % a level (10 % in the far wilds), rolled from the world seed and the cell. Two items: `gold_nugget` (4 make a gold ingot, the `gold_nuggets` recipe, anywhere; `toolmaking.make` crafts ingots from nuggets when it needs gold and has no gold ore to smelt, `toolmaking.POOLED`, so the gold pickaxe and sword come sooner) and `amber`. Both are treasures a full pair of arms makes room for.
10. **Ruins in worldgen** (Task 5). Regions of 96x96 blocks; one in 2 tries a spot (hash channel 92), its middle 12 to 84 blocks into the region, so a ruin never leaves its region; it stands only where every column of its 7x7 square is dry land within 2 blocks of the middle's height, with no swamp pool, cave entrance, tree trunk or rock; none within a region of the legacy clearing. The chest stands on the middle column's ground; the walls stand on the square's edge, each column on its own ground, 1 to 3 blocks high or fallen to a gap (channel 93), the corners always 3, the middle of one side always a doorway; each wall cell is stone bricks, or mossy cobblestone one time in 3 (channel 94). Nothing grows in a wall's or the chest's column. The decoration precedence becomes home, trunk, leaves, ruin, rock, plant; `generateColumn` stamps plants, rocks, ruins, leaves, trunks, home. Walls stand no higher than a rock (3), so `FEATURE_TOP` and `light.SKY_SCAN` are unchanged. The minimap's `naturalTop` shows a ruin's wall or chest, as a scan from above would. The fixture adds two ruins east and two west of the clearing for each seed, 9x9 columns by 6 cells each. Measured: about a quarter of regions hold one (23 %); around 24 hatch spawns, 2 to 11 ruins stand within 240 blocks of each, the nearest 15 to 212 blocks away, and every spawn has at least one in the far wilds.
11. **Ruins in the brain** (Task 6). After a walk or swim, a ruin whose chest stands within 24 blocks and that Mimo does not remember is remembered (a `"ruin"` place at the chest, noted with the ring's name) and is a notable `found` event ("Pip found an old ruin in the far wilds."), a discovery that asks for a new choice and a new place for curiosity (the observers run before curiosity looks over the step's events). `open_chest` (0.6 s, within reach) fails for no chest, a chest that is not a ruin's (`is_ruin_chest`), or one already open; it puts `ruin_loot(seed, cell, ring)` into `state["chests"]` (the ring measured at the chest when it is opened) and is a notable `loot` event ("Pip opened an old chest in a ruin: 9 arrow, 4 bread, 3 gold nugget and 3 iron ingot."). The loot table (item, least, most, chance): home ground bread 1–3 (1), arrows 4–8 (0.8), iron ingots 1–2 (0.7), torches 2–4 (0.5); near wilds bread 2–4, arrows 4–8 (0.9), iron ingots 1–3 (0.8), coal 2–4 (0.6); far wilds bread 2–4 (0.8), arrows 6–12, iron ingots 2–4 (0.8), gold nuggets 2–6 (0.8), amber 1–2 (0.6); frontier arrows 8–16, gold ingots 1–3 (0.8), gold nuggets 3–8 (0.8), amber 1–3 (0.8), a diamond (0.5); deep frontier arrows 8–16, gold ingots 2–4, amber 2–4, diamonds 1–3 (0.8). `loot_ruin` ("loot an old ruin", 58 + a tenth of bravery, minus late): by day, a remembered ruin within 64 blocks whose chest stands and was never opened or holds what Mimo has room for, in a ring no deeper than `ready_ring`, the nearest first; a walk up, `open_chest`, then `take` steps, at most 3 batches. It takes the rarest first (diamond, amber, gold, iron, bread, coal, arrows, torches) and only as much as keeps its arms below 12 stacks (`LOOT_ROOM`, one under storage's `STORE_FROM`); the rest waits in the chest for a later visit. Measured on `2daead4`: taking all that fit in 16 stacks put four new stacks in a young pet's arms near home, and seed 5's fake-Jev pet swung between gathering stone, dropping and putting away: 94 changes of purpose in its busiest slow-mode hour, over the sims' 90 (69 on the base). With `LOOT_ROOM` it is 88; every other seed and picker stays at 63 to 76. The rest of that hour is faster progress, not churn: the chest's iron gave it an iron pickaxe, sword and cap by its 25th minute. An unopened chest within 32 blocks is an urge, so Mimo opens it whatever its goal.
12. **The warding lantern** (Task 7). A lantern and 4 gloom dust, anywhere; the block `warding_lantern` (glow, light 15, violet) comes last in `shared/blocks.json`. No hostile steps within 6 blocks of one to a cell closer to it than the one it stands on (`acts.barred`, in wandering and chasing); its light already keeps spawns off. Mimo keeps the cells of the ones it hung in `state["wards"]` (after each place or mine step), so a creature's step reads no database (a first version that read placed blocks per call cost L2's 20 ms budget test its margin). craft_tools orders one while Mimo carries 4 gloom dust and fewer than 2 warding lanterns (making the lantern from an iron ingot and a torch if needed), and build_storage keeps 4 gloom dust on hand (it put all away before). `ward_home` (62, an urge while one is carried): by day near home, it takes the torch or lantern off a corner of home and hangs the warding lantern there, up to 2; a warding lantern lights a torch corner (`STANDS_IN`).
13. **Amber-studded armor** (Task 7). An amber cap (2 iron ingots, 2 amber) and an amber tunic (3 iron ingots, 3 amber) at a crafting table take 24 % and 36 % off a blow (60 % together); craft_tools makes a piece once Mimo wears iron on that slot and carries the amber. The recipes do not use up the iron piece (it stays in Mimo's arms; only the best piece on a slot counts), so L4a's "iron armor" milestone and L3's armor orders never ask for it again.
14. **The frontier goal** (Task 8), "Riches farther out", repeating: open to a pet with a home it built (L4a's one home lookup, `home.built_home`: a Situation reads remembered places only within 256 blocks on each axis, so a first version, reading home from them, lost the goal out in the frontier; the opened ruins are read the same way, all of them, so a chest opened in the frontier counts back home) whose weapons and armor are fit for the far wilds or deeper (`gear_short_of`) while an old ruin it never opened stands in such a ring within 480 blocks of home. Milestones, counted from when it was set: reach the far wilds (`state["frontier"]["far_at"]`), open an old ruin's chest past the near wilds (a `"ruin"` place opened since), come home to home ground with the loot (go_home). Once a chest is open the goal stays open until Mimo is home with the loot (a first version closed it when the last unopened ruin out there was opened, and the goal was set aside on the spot, measured on seed 5). go_home advances it only with the loot and loot_ruin only for a ruin past the near wilds (`goals.ADVANCES`): before that fix a pet working on armor was sent home by day again and again "toward riches farther out", the goal it worked toward meanwhile. Rules score 40 + a fifth of bravery + a tenth of curiosity (40–70), so iron tools (60–70) still comes first when both are open. An ungeared pet never has it.
15. **The riches trip** (Task 8), "seek riches farther out" (50 + a tenth of bravery; serves the frontier goal): wanted only while the frontier is Mimo's goal and no chest is opened yet, only when `ready_ring` is 2 or more, not at night or late, and only with time to walk out to the farthest its trips may go and back (twice `reach_limit`: 480 blocks for a pet ready for the far wilds) and a game minute before the homeward window opens (`homeward_from`). A column in a ring deeper than Mimo is ready for, or on home ground, is worth nothing; one within 16 blocks of an unopened ruin in a ring it is ready for is sure ("an old ruin in the far wilds, danger 2"); any other 0.2, and up to 0.8 more the nearer such a ruin lies (its pull, falling to nothing 240 blocks off: "toward an old ruin, the far wilds, danger 2"), so the trip heads the ruin's way (a first version gave all the far wilds 0.6, and seed 11's pet, whose two ruins lay 212 and 227 blocks off the other way, walked four trips without seeing one and set the goal aside). The ruins counted are the unopened ones past the near wilds, no deeper than Mimo is ready for, that it could see from inside its trips' limit (resolution 16a). The unopened ruins within 80 blocks of Mimo are its spots. Its reach is 480 blocks from home, so a pet ready for the frontier may go there. A ruin in sight after a walk, in a ring Mimo is ready for past the near wilds, is the find; loot_ruin follows up (the chest is an urge). L4a's other reasons keep their reach: 60 blocks, and wander's and the discovery goals' growing as the land is walked up to 240 (L4a's final fix wave, `curiosity.trip_reach`, `home.FARTHEST_TRIP`), into the far wilds for any pet; resolution 16a's fence stands at the same 240 blocks for a pet not ready for the frontier.
16a. **No trip past readiness** (Task 8). Every trip, whatever its reason, keeps inside the deepest ring Mimo is ready for (the far wilds at least) and 16 blocks short of its outer edge: 240 blocks from home for a pet ready for the far wilds, 496 for the frontier (`trips.FENCES`, checked in `trips.beyond` for spots and targets alike). Measured before it: out near the far wilds' edge L4a's reasons may head anywhere no farther from home than Mimo stands, and walks wind round what is in their way, so a pet geared only for the far wilds stood in the frontier on a wander (seed 11) and on a riches trip to a ruin at the edge (seed 8). The far wilds stay open to L4a's farthest day trips (240 blocks, the same line) and to L4b's expeditions.
16. **Home before dark** (Task 8). From the far wilds on, the head_home window opens earlier by the walk home: 0.45 game seconds a block at 1x (0.3 s a block, 1.5 times the straight line) and a game minute (`purposes.HOMEWARD_LEADS`, read by `reflexes.head_home_due`), and "late in the day" starts earlier by as much (`purposes.late_day`: go_home scores 70 and more and outdoor work 30 less from then on, so a head_home walk that a fight cuts short is not lost to the next choice; measured before it, a pet 340 blocks out hurried home four times, each walk cut by a thornback and followed by farming out there); and `purposes.home_of` falls back to the home Mimo built however far it is (`purposes.FAR_HOMES`, through L4a's one home lookup), so everything that asks `home_of` finds it past its 128 blocks (go_home and head_home look from any distance since L4a's follow-up, `GO_HOME_RANGE`). Home ground and the near wilds play as before (no lead there).
17. **What the model is told** (Tasks 6 and 8). The payload gains `frontier` (`rings.ring_payload`: ring, name, danger, blocks from home, the deepest ring Mimo is ready for and what it lacks for the next); each riches target says its ring and danger in `explore_reasons` and explore's facts; loot_ruin's facts name the ruin's ring and whether its chest was opened. That is how Jev sees each option's ring and Mimo's gear readiness.
18. **The headless checks** (Task 9). The frontier runs hatch the pet, stand a finished cobblestone cottage with a bed beside where it hatched and make it the home it built (first shelter reached), hand it gear and food and tick it at 1x with the rules' Chooser. (A first version only named the hatching spot home, with no shelter: build_shelter stayed on offer everywhere, and in slow mode a pet out past 300 blocks built and slept out there.) Default: seed 8 for a game day in 15-second steps; slow mode: seeds 8, 11 and 5 for four game days in 5-second steps (seed 3 was left out while, with this cottage, its pet got stuck 87 blocks from home and starved on day 4 with or without L5, on `0c4a498`; L4a's final fix wave cured that, and since then seed 3's runs pass too, measured). A geared pet (stone sword, leather cap and tunic, bow and 16 arrows, 6 bread and 4 cooked beef) with the frontier goal must stay alive, stand in the far wilds, open a chest whose loot holds what only the far wilds' ruins hold (gold nuggets or amber), reach the goal and stand on home ground at every nightfall; an ungeared one (the sword and the food) must stay alive and no riches trip may ever run while a pet is not armed and armored for the far wilds (counted every tick, for both pets); in its first game day the ungeared pet also never leaves the near wilds and never sees riches in its events. Over four days (slow mode) an ungeared pet may make its own leather armor (L2's make_gear) and is geared from then on, which the first measure of this check missed: seed 3's pet did so and went out on day 3, as it should. Since L4a's final fix wave any pet's wander may reach the far wilds (up to 240 blocks), so in slow mode the ungeared pets stand in the far wilds too, on their own trips; none makes a riches trip ungeared. The budget check puts a geared pet 150 blocks from its birthplace early in the first night with a toughened gloomling, skitter and thornback beside it and the dark free to spawn: the creature hook's mean over five 60-game-second transactions stays under 20 ms (measured 3–12 ms).
19. **Balance at 1x** (the dry run, resolution 21). Four-game-day lives left alone (L4a's sim setup: seeds 3, 11, 5 and 21, the rules and the fake Jev, 15-second steps) measured on `62a0e5a` and with L5 on top of it (table in "Dry-run measurements"). A pet that never earns its gear lives as before; one that makes a stone sword and leather armor on its own takes the frontier goal when it is open and goes out.
20. **The viewer** (Task 10). Under the home line the HUD names the ring ("Far wilds · danger 2"), amber and bold from the far wilds on, with a tooltip. The minimap shades each ring past home ground that reaches onto the map in a faint red, 0.05 a level, with a fine line at its inner edge. An elder glows a faint violet (emissive 0.35), under a blow's red flash. The thornback is a voxel model of its own (a low, broad crawler under a humped shell of plates with pale thorns, amber eyes), 0.9 blocks tall. Amber armor draws in amber over the iron's rivets. Ruins and their chests are drawn by the worldgen port (Task 5) and on the minimap. The pet lifts the lid of an old chest with the "place" move; the HUD's words: "Looting an old ruin", "Hanging a warding lantern", "Opening an old chest", "caught by a thornback". Drops pop in their colours (amber, gold nugget, diamond, flint).
21. **Measured in the dry run.** See the section "Dry-run measurements" at the end of this plan; the controller re-measures after L4a and L4b land (L4b's expeditions add trips to 200 blocks, into the far wilds, which L5 leaves ungated: resolution 22).
22. **Out of scope, and L4b.** L4b's expedition goes up to 200 blocks from home, into the far wilds; L5 does not gate it by readiness (its pet is packed, fed and camps dug in), but out there its hostiles are tougher, its thornbacks walk by day and its flights and fights are warier, and its `AWAY` still keeps go_home off (the far home only makes home findable). Trips to the frontier (3) happen only for a pet ready for it; nothing in L5's rules sends a pet to the deep frontier (4), though elders, drops and ruin loot are ready for one that walks there. Out of scope: potions (the spec's "gloom dust ... potions" is L3's aside), ruins underground, ruins on the archive browser, a map marker for ruins, Luna choosing, amber anything but armor.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/survival/rings.py` | Create | The ring table, the centre and the ring Mimo stands in (`state["frontier"]`), readiness, the ring for the viewer and the model |
| `backend/survival/creatures/ringed.py` | Create | Hostiles born in a ring: health, damage, elders; the cap and Mimo's caution by ring |
| `backend/survival/creatures/thornback.py` | Create | The thornback kind, its spawner, bow-only |
| `backend/survival/loot.py` | Create | Ring drops, mining luck |
| `backend/survival/ruins.py` | Create | Ruins seen and remembered, the `open_chest` step, the loot table, `loot_ruin` |
| `backend/survival/frontier_gear.py` | Create | The warding lantern (light, barrier, wards kept, orders, `ward_home`) and amber-studded armor |
| `backend/survival/frontier.py` | Create | The frontier goal, the riches trip, home before dark from far out |
| `backend/services/worldgen.py`, `frontend/src/engine/worldgen.ts` | Modify | Ruins, identically |
| `backend/scripts/worldgen_fixture.py`, `shared/worldgen-fixture.json` | Modify | Ruins in the fixture (regenerated) |
| `backend/services/crafting.py`, `shared/blocks.json` | Modify | L5's recipes; the `warding_lantern` block and tile |
| `backend/survival/creatures/{darkness,defense,hostiles,view,kinds,combat,simulate,acts}.py` | Modify | The hooks: births and the cap, caution and bow-only, the ringed blow, the view's full health and elders, shell and daylight, extra drops, spawners, barriers |
| `backend/survival/{steps,toolmaking,carrying,purposes,reflexes,pickers,snapshot,brain}.py` | Modify | `MINED` and `OBSERVERS`; `POOLED` and `MORE_ORDERS`; treasures; the far home and the early walk home; the payload's `frontier`; `/api/mimo`'s `ring`; the brain's imports, `tend_frontier` and observers |
| `backend/tests/test_survival_{rings,ringed,thornback,loot,ruins,frontier_gear,frontier,frontier_run}.py`, `backend/tests/test_worldgen_ruins.py` | Create | One test file per new module or area, and the headless runs |
| `backend/tests/test_{worldgen,blocks_bigger_world,survival_gear,survival_pickers}.py` | Modify | What L5 changes in them |
| `frontend/src/survival/frontier.ts` (+ test) | Create | The ring's words, the minimap's bands, an elder's glow |
| `frontend/src/survival/{types,hud,SurvivalHud,Minimap,SurvivalWorld,SurvivalCreatures,creatures,petGear,animation,cutaway,overheadMap}.ts(x)` | Modify | The stream's `ring` and `elder`, words, the HUD's ring line, the map's rings and ruins, the elder glow, the thornback model, amber armor |
| `frontend/src/engine/{worldgen,blocks}.test.ts`, `frontend/src/survival/{overheadMap,creatures,petGear,hud}.test.ts` | Modify | Ruin parity, the new block, the new model and words |
| `README.md` | Modify | The frontier |

## Tasks

1. Danger rings around home
2. Harder enemies farther out: tougher hostiles, elders, a bigger cap and a warier pet
3. The thornback
4. Better loot farther out: drops, mining luck, gold nuggets and amber
5. Frontier ruins in worldgen, in both ports
6. Ruins in the brain: seeing them, the old chest and loot_ruin
7. Loot put to use: the warding lantern and amber-studded armor
8. Risk against reward: riches farther out, home before dark, what the model is told
9. The headless checks: a geared trip, an ungeared pet, the budget
10. Viewer: the ring, the rings on the map, elders, the thornback and amber armor
11. Manual check on the demo and the README

Tasks 1–9 are the backend (Task 5 also the worldgen port and the minimap's view of ruins) and 10 the viewer. Tasks 2–4 need only Task 1; Task 6 needs Tasks 1 and 5; Task 7 needs Task 6's observers; Task 8 needs Tasks 1, 6 and 7; Task 9 needs all of them; Task 10 needs the stream fields of Tasks 1 and 2 and the worldgen of Task 5.

---

### Task 1: Danger rings around home

**Files:**
- Create: `backend/survival/rings.py`
- Modify: `backend/survival/brain.py` (`tend_frontier` in `notice_step`, before `tend_goal`), `backend/survival/snapshot.py` (`ring` in `/api/mimo`)
- Test: `backend/tests/test_survival_rings.py`

**Interfaces:**
- Consumes: `memory.places`, `memory.set_home`, `memory.BUILT`; `creatures.combat.SWORDS`, `weapon`; `creatures.harm.armor_cut`; `foraging.food_points`; `situation.Situation` (`sensed`); `actions.ActionContext` (`db`, `events`).
- Produces:
  - `rings.RINGS` (`(level, name, start)` for 0–4), `DEEPEST = 4`, `OPEN_RINGS = 1`, `ANNOUNCED_FROM = 2`; `Ready(sword, armor, health, arrows, food=30.0)`, `READY: dict[int, Ready]` for 2–4, `BOW_INSTEAD = 8`.
  - `ring_of_distance(distance) -> int`, `ring_name(ring) -> str`; `center(state) -> (x, z) | None`; `ring_at(state, x, z) -> int` (0 before the first tend); `ring_here(state) -> int`; `distance_home(state) -> float`.
  - `frontier_state(state) -> dict`; `home_place(db) -> dict | None`; `tend_frontier(state, context, at)` (keeps `state["frontier"]`: `center`, `birthplace`, `ring`, `reached`; Task 8 adds `far_at`).
  - `best_sword(s) -> float`; `arrows(s) -> int`; `short_of(s, ring) -> list[str]` (Task 8 adds `gear_only`); `ready_ring(s) -> int` (memoised per Situation).
  - `ring_view(state) -> {"level", "name", "center": {"x", "z"}} | None`; `ring_payload(s) -> dict` (`ring`, `name`, `danger`, `blocks_from_home`, `ready_for`, `ready_for_name`, `short_of_next`; Task 8 puts it in the model payload).
  - `/api/mimo` gains `ring` (`snapshot.survival_view`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_rings.py`:

```python
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.actions import ActionContext
from backend.survival.brain import BRAIN
from backend.survival.hatch import hatch
from backend.survival.memory import BUILT, create_memory_tables, remember, set_home
from backend.survival.rings import (
    center, ready_ring, ring_at, ring_name, ring_of_distance, ring_payload, ring_view, short_of, tend_frontier,
)
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import survival_view
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld
from backend.tests.test_survival_pickers import DAY, situation

GEARED = {"stone_sword": 1, "leather_cap": 1, "leather_tunic": 1, "bread": 2}


def tended(position=(0.0, 1.0, 0.0), home=None, note=BUILT, state=None):
    """A state the tick tended once at `position`, with a home place at `home` (noted `note`)."""
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    if home is not None:
        set_home(db, home, 0.0, note)
    state = state or {"name": "Pip", "position": dict(zip("xyz", position))}
    context = ActionContext(grid=None, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=db)
    tend_frontier(state, context, 5.0)
    return state, context, db


class RingTests(unittest.TestCase):
    def test_distance_from_home_sets_the_ring(self):
        self.assertEqual([ring_of_distance(d) for d in (0, 47.9, 48, 127.9, 128, 255, 256, 511, 512, 9000)],
                         [0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
        self.assertEqual([ring_name(ring) for ring in range(5)],
                         ["Home ground", "Near wilds", "Far wilds", "Frontier", "Deep frontier"])

    def test_the_birthplace_is_the_centre_until_a_home_stands(self):
        state, context, db = tended(position=(10.0, 1.0, 20.0))
        self.assertEqual(state["frontier"]["birthplace"], [10, 20])
        self.assertEqual(center(state), (10.0, 20.0))
        self.assertEqual(ring_at(state, 10 + 130, 20), 2)
        remember(db, "home", (40, 1, 20), 1.0)  # a sheltered spot Mimo found is no home it built
        state["position"] = {"x": 40.0, "y": 1.0, "z": 20.0}
        tend_frontier(state, context, 6.0)
        self.assertEqual(center(state), (10.0, 20.0))

    def test_rings_move_with_the_home_mimo_built(self):
        state, context, db = tended(position=(300.0, 1.0, 0.0), home=(100, 1, 0))
        self.assertEqual((center(state), state["frontier"]["ring"]), ((100.0, 0.0), 2))
        set_home(db, (250, 1, 0), 7.0)  # a bigger home, farther out
        tend_frontier(state, context, 8.0)
        self.assertEqual((center(state), state["frontier"]["ring"]), ((250.0, 0.0), 1))

    def test_a_save_from_before_the_rings_takes_its_oldest_home_as_its_birthplace(self):
        state, _, _ = tended(position=(90.0, 1.0, 0.0), home=(30, 1, 0), note="")
        self.assertEqual(state["frontier"]["birthplace"], [30, 0])
        self.assertEqual(state["frontier"]["ring"], 1)

    def test_the_first_steps_into_the_far_wilds_and_beyond_are_notable(self):
        state, context, _ = tended(position=(60.0, 1.0, 0.0), home=(0, 1, 0))
        for x in (140.0, 60.0, 150.0, 300.0):
            state["position"]["x"] = x
            tend_frontier(state, context, 9.0)
        self.assertEqual([text for _, kind, text in context.events if kind == "found"],
                         ["Pip reached the far wilds for the first time.", "Pip reached the frontier for the first time."])
        self.assertEqual(state["frontier"]["reached"], 3)

    def test_the_viewer_is_told_the_ring_where_mimo_stands(self):
        state, _, _ = tended(position=(200.0, 1.0, 0.0), home=(0, 1, 0))
        self.assertEqual(ring_view(state), {"level": 2, "name": "Far wilds", "center": {"x": 0, "z": 0}})
        self.assertIsNone(ring_view({"position": {"x": 0.0, "y": 1.0, "z": 0.0}}))


class ReadinessTests(unittest.TestCase):
    def test_rings_zero_and_one_are_open_to_every_pet(self):
        s = situation()
        self.assertEqual(ready_ring(s), 1)
        self.assertEqual(short_of(s, 1), [])
        self.assertEqual(short_of(s, 2), ["a stone sword or better", "leather armor or better", "food for half a day"])

    def test_a_pet_armed_armored_well_and_fed_is_ready_for_the_far_wilds(self):
        self.assertEqual(ready_ring(situation(inventory=dict(GEARED))), 2)
        bow = {"bow": 1, "arrow": 8, "leather_cap": 1, "leather_tunic": 1, "bread": 2}
        self.assertEqual(ready_ring(situation(inventory=bow)), 2)
        hurt = situation(inventory=dict(GEARED))
        hurt.vitals["health"] = 60.0
        self.assertEqual((ready_ring(hurt), short_of(hurt, 2)), (1, ["70 health"]))

    def test_the_frontier_takes_iron_a_bow_and_arrows(self):
        iron = {"iron_sword": 1, "iron_cap": 1, "iron_tunic": 1, "bread": 2}
        self.assertEqual(ready_ring(situation(inventory=iron)), 2)
        self.assertEqual(short_of(situation(inventory=iron), 3), ["a bow and 8 arrows"])
        self.assertEqual(ready_ring(situation(inventory={**iron, "bow": 1, "arrow": 8})), 3)

    def test_the_model_is_told_the_ring_and_what_the_next_one_takes(self):
        s = situation(inventory=dict(GEARED))
        s.state["frontier"] = {"center": [0, 0]}
        s.state["position"]["x"] = 60.0
        self.assertEqual(ring_payload(s), {"ring": 1, "name": "Near wilds", "danger": 1, "blocks_from_home": 60,
                                           "ready_for": 2, "ready_for_name": "Far wilds",
                                           "short_of_next": ["an iron sword or better", "a bow and 8 arrows",
                                                             "iron armor or better"]})


class StreamTests(unittest.TestCase):
    def test_api_mimo_names_the_ring_once_the_tick_tended_it(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=1_000_000.0)
            world = SurvivalWorld(registry.world_path(life))
            tick_life(registry, 1_000_010.0, mind=BRAIN)
            view = survival_view(world, 1_000_010.0, 1.0)
        self.assertEqual(view["ring"]["level"], 0)
        self.assertEqual(view["ring"]["name"], "Home ground")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_rings.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.rings'`

- [ ] **Step 3: The rings**

Create `backend/survival/rings.py`:

```python
"""Danger rings around home (L5, "Frontier"): the farther from home, the harder and the richer.

The centre is home: the home Mimo built (memory kind "home", noted "built"), or its birthplace
until a home stands. The distance from it, across, sets the ring, and the ring's number is its
danger:

    ring  name            from (blocks)
    0     Home ground       0
    1     Near wilds       48
    2     Far wilds       128
    3     Frontier        256
    4     Deep frontier   512

Rings move with home: when L4 builds a bigger home and Mimo moves in, the centre moves with it.
Home ground plays exactly as before L5. Worldgen never depends on the rings: the terrain stays a
pure function of the seed and the cell, and only creatures, drops, mining luck and ruin loot read
the ring of a place.

The tick keeps what the rest of the game needs in the state (`state["frontier"]`), so a step or a
creature reads the ring without the database: {"center": [x, z], "birthplace": [x, z], "ring": the
ring Mimo stands in, "reached": the deepest ring it has stood in}. `tend_frontier` (from
brain.notice_step, after every vitals step) reads the home place once, keeps the centre on it (the
birthplace until a home stands; a life from before L5 takes its oldest home place, or where it
stands, as its birthplace), and notes the ring Mimo stands in. The first time Mimo stands in a ring
past the near wilds is a notable "found" event ("Pip reached the far wilds for the first time.").

Readiness: what Mimo needs to go into a ring on purpose (L5's frontier trip). Rings 0 and 1 are
open to every pet. The far wilds (2) take a stone sword or better (or a bow and 8 arrows), armor that
takes a fifth off a blow (leather cap and tunic), 70 health and half a day's food (30 hunger); the
frontier (3) an iron sword, a bow and 8 arrows, iron armor (45 %) and 80 health; the deep frontier
(4) a diamond sword, a bow and 16 arrows, amber armor (60 %) and 90 health. `ready_ring` is the
deepest ring Mimo is ready for, `short_of` what it lacks for one, in words.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.survival.creatures.combat import SWORDS, weapon
from backend.survival.creatures.harm import armor_cut
from backend.survival.foraging import food_points
from backend.survival.memory import BUILT, places
from backend.survival.situation import Situation

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

RINGS = ((0, "Home ground", 0.0), (1, "Near wilds", 48.0), (2, "Far wilds", 128.0), (3, "Frontier", 256.0),
         (4, "Deep frontier", 512.0))
DEEPEST = RINGS[-1][0]
OPEN_RINGS = 1  # rings 0 and 1 are open to every pet
ANNOUNCED_FROM = 2  # the first steps into this ring or a deeper one are notable


@dataclass(frozen=True)
class Ready:
    sword: float  # the least damage the best sword may do (combat.SWORDS): 5 is a stone sword
    armor: float  # the least share of a blow the armor must take off (harm.armor_cut)
    health: float
    arrows: int  # arrows (with a bow) it must carry; 0: a bow with 8 arrows may stand in for the sword
    food: float = 30.0  # hunger points of food it carries


READY = {2: Ready(sword=5.0, armor=0.20, health=70.0, arrows=0),
         3: Ready(sword=6.0, armor=0.45, health=80.0, arrows=8),
         4: Ready(sword=8.0, armor=0.60, health=90.0, arrows=16)}
BOW_INSTEAD = 8  # arrows a bow needs to stand in for a sword on the way into the far wilds
SWORD_WORDS = {5.0: "a stone sword or better", 6.0: "an iron sword or better", 8.0: "a diamond sword"}
ARMOR_WORDS = {0.20: "leather armor or better", 0.45: "iron armor or better", 0.60: "amber-studded armor"}


# Rings -----------------------------------------------------------------------------------------

def ring_of_distance(distance: float) -> int:
    """The ring a place this many blocks (across) from home lies in."""
    return max(number for number, _, start in RINGS if distance >= start)


def ring_name(ring: int) -> str:
    return RINGS[max(0, min(DEEPEST, ring))][1]


def center(state: dict) -> tuple[float, float] | None:
    """The centre of the rings as the tick last saw it, or None before the tick first tended it."""
    found = (state.get("frontier") or {}).get("center")
    return (float(found[0]), float(found[1])) if found else None


def ring_at(state: dict, x: float, z: float) -> int:
    """The ring (x, z) lies in; 0 before the tick first tended the rings."""
    middle = center(state)
    return 0 if middle is None else ring_of_distance(math.hypot(x - middle[0], z - middle[1]))


def ring_here(state: dict) -> int:
    position = state["position"]
    return ring_at(state, position["x"], position["z"])


def distance_home(state: dict) -> float:
    """Blocks (across) from Mimo to the centre; 0 before the tick first tended the rings."""
    middle, position = center(state), state["position"]
    return 0.0 if middle is None else math.hypot(position["x"] - middle[0], position["z"] - middle[1])


# The tick's side -------------------------------------------------------------------------------

def frontier_state(state: dict) -> dict:
    return state.setdefault("frontier", {})


def home_place(db) -> dict | None:
    found = places(db, ("home",))
    return found[0] if found else None


def tend_frontier(state: dict, context: ActionContext, at: float) -> None:
    """Keep the centre on home and note the ring Mimo stands in (see the module docstring)."""
    if context.db is None:
        return
    frontier = frontier_state(state)
    home = home_place(context.db)
    if "birthplace" not in frontier:
        position = state["position"]
        born = (home["x"], home["z"]) if home is not None else (position["x"], position["z"])
        frontier["birthplace"] = [round(born[0]), round(born[1])]
    if home is not None and home["note"] == BUILT:
        frontier["center"] = [home["x"], home["z"]]
    else:
        frontier["center"] = list(frontier["birthplace"])
    ring = ring_here(state)
    frontier["ring"] = ring
    reached = frontier.get("reached", 0)
    if ring > reached:
        frontier["reached"] = ring
        if ring >= ANNOUNCED_FROM:
            context.events.append((at, "found", f"{state['name']} reached the {ring_name(ring).lower()} "
                                                f"for the first time."))


# Readiness -------------------------------------------------------------------------------------

def best_sword(s: Situation) -> float:
    sword = weapon(s.inventory)
    return SWORDS[sword] if sword is not None else 0.0


def arrows(s: Situation) -> int:
    return s.count("arrow") if s.count("bow") > 0 else 0


def short_of(s: Situation, ring: int) -> list[str]:
    """What Mimo lacks to go into `ring` on purpose, in words; [] when it is ready (always for 0 and 1)."""
    need = READY.get(min(ring, DEEPEST))
    if ring <= OPEN_RINGS or need is None:
        return []
    missing = []
    bow_will_do = need.arrows == 0 and arrows(s) >= BOW_INSTEAD
    if best_sword(s) < need.sword and not bow_will_do:
        missing.append(SWORD_WORDS[need.sword])
    if need.arrows and arrows(s) < need.arrows:
        missing.append(f"a bow and {need.arrows} arrows")
    if armor_cut(s.inventory) < need.armor - 1e-9:
        missing.append(ARMOR_WORDS[need.armor])
    if s.vitals["health"] < need.health:
        missing.append(f"{round(need.health)} health")
    if food_points(s) < need.food:
        missing.append("food for half a day")
    return missing


def ready_ring(s: Situation) -> int:
    """The deepest ring Mimo is ready to go into on purpose: OPEN_RINGS (1) or more."""
    def look() -> int:
        ready = OPEN_RINGS
        for ring in range(OPEN_RINGS + 1, DEEPEST + 1):
            if short_of(s, ring):
                break
            ready = ring
        return ready
    return s.sensed("ready ring", look)


# What the viewer and the model are told --------------------------------------------------------

def ring_view(state: dict) -> dict | None:
    """/api/mimo's `ring`: {"level", "name", "center": {"x", "z"}} where Mimo stands, or None
    before the tick first tended the rings (an older save, or a life from before L5)."""
    middle = center(state)
    if middle is None:
        return None
    ring = ring_here(state)
    return {"level": ring, "name": ring_name(ring), "center": {"x": round(middle[0]), "z": round(middle[1])}}


def ring_payload(s: Situation) -> dict:
    """What a model is told about the rings: where Mimo stands, how far from home, the deepest ring it
    is ready for and what it lacks for the next one."""
    ring, ready = ring_here(s.state), ready_ring(s)
    nxt = min(ready + 1, DEEPEST)
    return {"ring": ring, "name": ring_name(ring), "danger": ring, "blocks_from_home": round(distance_home(s.state)),
            "ready_for": ready, "ready_for_name": ring_name(ready),
            "short_of_next": short_of(s, nxt) if ready < DEEPEST else []}
```

- [ ] **Step 4: The tick tends them, before the goal, and the viewer is told**

The rings are tended right before the goal, since Task 8's frontier goal reads the centre in its validity check (a first version tended them after the goal, and a hatched pet's first goal check found no centre and set its goal aside).

In `backend/survival/brain.py`, replace:

```python
event, one a step; it asks for a choice at most once a game hour).
```

with:

```python
event, one a step; it asks for a choice at most once a game hour).
L5: `notice_step` also keeps the danger rings' centre on home and notes the ring Mimo stands in
(backend.survival.rings.tend_frontier).
```

and replace:

```python
from backend.survival.reflexes import by_name, end_reflex, reflex_hook
```

with:

```python
from backend.survival.reflexes import by_name, end_reflex, reflex_hook
from backend.survival.rings import tend_frontier
```

and replace:

```python
        mark_trigger(state, phase, at)
```

with:

```python
        mark_trigger(state, phase, at)
    tend_frontier(state, context, at)  # L5: the danger rings' centre and the ring Mimo stands in
```

In `backend/survival/snapshot.py`, replace:

```python
from backend.survival.registry import LifeRegistry
```

with:

```python
from backend.survival.registry import LifeRegistry
from backend.survival.rings import ring_view
```

and replace:

```python
        "sheltered": indoors,
```

with:

```python
        "sheltered": indoors,
        # L5: the danger ring Mimo stands in and the rings' centre ({"level", "name", "center"}; null
        # before the tick first tends the rings).
        "ring": ring_view(state),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_rings.py"`
Expected: `Ran 11 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1124 tests` … `OK` (11 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/rings.py backend/survival/brain.py backend/survival/snapshot.py backend/tests/test_survival_rings.py
git commit -m "feat: danger rings around home - home ground, the near and far wilds, the frontier and the deep frontier, tended by the tick and named in /api/mimo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Harder enemies farther out: tougher hostiles, elders, a bigger cap and a warier pet

**Files:**
- Create: `backend/survival/creatures/ringed.py`
- Modify: `backend/survival/creatures/darkness.py` (`BIRTHS`, `MORE_ROOM`, `born` shaped by them, `cap`), `backend/survival/creatures/hostiles.py` (a blow adds `fiercer`), `backend/survival/creatures/view.py` (health by `most`, `elder`), `backend/survival/creatures/defense.py` (`CAUTION`, `flee_below`, `fight_from`), `backend/survival/brain.py` (imports `ringed`)
- Test: `backend/tests/test_survival_ringed.py`

**Interfaces:**
- Consumes: Task 1's `rings.ring_at`, `ring_here`, `DEEPEST`; `creatures.moves.roll`; `acts.Scene`; the test helpers `test_survival_darkness.land`, `pet`, `scene` and `test_survival_defense.meadow`, `pet`, `situation`.
- Produces:
  - `darkness.BIRTHS: list` of `(scene, kind, cell, state, health) -> health`; `darkness.MORE_ROOM: list` of `(scene) -> int`; `darkness.cap(scene) -> int`.
  - `defense.CAUTION: list` of `(s) -> float`; `defense.caution(s)`, `flee_below(s)`, `fight_from(s)`.
  - `ringed.HEALTH_PER_LEVEL = 0.35`, `DAMAGE_EVERY = 2`, `ELDERS`, `ELDER_FROM = 3`, `ELDER_CHANCE = {3: 0.25, 4: 0.5}`, `ELDER_HEALTH = 1.5`, `ELDER_DAMAGE = 1.0`, `CAUTION_FROM = 2`, `CAUTION_PER_LEVEL = 5.0`; `level_of(scene, cell)`, `elder_roll(scene, cell)`, `toughen(...)`, `more_room(scene)`, `caution(s)`.
  - A hostile's state may hold `ring`, `most`, `fiercer`, `elder`; `creature_view` sends `elder: True` and reads health against `most`. Task 4's drops read `ring` and `elder`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_ringed.py`:

```python
import unittest

from backend.survival import brain  # noqa: F401  (registers the ringed hostiles' hooks)
from backend.survival.creatures.darkness import HOSTILE_CAP, born, cap
from backend.survival.creatures.defense import FIGHT_FROM, FLEE_BELOW, fight_from, flee_below, flee_due
from backend.survival.creatures.hostiles import strike_pet
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.ringed import ELDER_CHANCE, elder_roll
from backend.survival.creatures.view import creature_view
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_darkness import land, pet, scene
from backend.tests.test_survival_defense import meadow, pet as defended, situation


def far_out(x=0.0, center=(0, 0)):
    """Mimo standing at (x, 1, 0), with the rings centred on `center`."""
    state = pet()
    state["position"]["x"] = x
    state["frontier"] = {"center": list(center)}
    state["name"], state["vitals"] = "Pip", dict(START_VITALS)
    return state


class TougherTests(unittest.TestCase):
    def test_at_home_a_hostile_is_as_it_always_was(self):
        grid = land()
        creature = born(scene(grid, far_out()), KINDS["gloomling"], (20, 1, 0))
        self.assertEqual(creature["health"], 20.0)
        self.assertEqual({key: creature["state"].get(key) for key in ("ring", "most", "fiercer", "elder")},
                         {"ring": None, "most": None, "fiercer": None, "elder": None})

    def test_in_the_far_wilds_it_has_more_health_and_hits_harder(self):
        grid = land()
        creature = born(scene(grid, far_out(150.0)), KINDS["gloomling"], (170, 1, 0))
        self.assertEqual(creature["health"], 34.0)  # 20, and 35 % a level for 2 levels
        self.assertEqual((creature["state"]["ring"], creature["state"]["most"], creature["state"]["fiercer"]),
                         (2, 34.0, 1.0))
        skitter = born(scene(grid, far_out(60.0)), KINDS["skitter"], (80, 1, 0))
        self.assertEqual((skitter["health"], skitter["state"].get("fiercer")), (16.2, None))  # ring 1: health only

    def test_from_the_frontier_some_are_elders(self):
        grid = land()
        where = far_out(300.0)
        cells = [(320 + dx, 1, dz) for dx in range(6) for dz in range(6)]
        elders = [cell for cell in cells if elder_roll(scene(grid, where), cell) < ELDER_CHANCE[3]]
        self.assertTrue(0 < len(elders) < len(cells))
        creature = born(scene(grid, where), KINDS["gloomling"], elders[0])
        self.assertTrue(creature["state"]["elder"])
        self.assertEqual((creature["health"], creature["state"]["fiercer"]), (61.5, 2.0))  # 20 x 2.05 x 1.5
        view = creature_view(creature, 100.0)
        self.assertEqual((view["elder"], view["health"]), (True, 1.0))

    def test_its_blow_takes_the_extra_damage(self):
        grid = land()
        state = far_out(150.0)
        creature = born(scene(grid, state), KINDS["gloomling"], (151, 1, 0))
        strike_pet(creature, KINDS["gloomling"], scene(grid, state))
        self.assertEqual(state["vitals"]["health"], 96.0)  # 3 and 1 for the far wilds

    def test_the_health_bar_reads_the_hostile_s_own_full_health(self):
        grid = land()
        creature = born(scene(grid, far_out(150.0)), KINDS["gloomling"], (170, 1, 0))
        creature["health"] = 17.0
        self.assertEqual(creature_view(creature, 100.0)["health"], 0.5)

    def test_the_cap_grows_one_a_level_of_the_ring_mimo_stands_in(self):
        grid = land()
        self.assertEqual(cap(scene(grid, far_out())), HOSTILE_CAP)
        self.assertEqual(cap(scene(grid, far_out(150.0))), HOSTILE_CAP + 2)


class CautionTests(unittest.TestCase):
    def test_far_out_mimo_runs_sooner_and_fights_from_more_health(self):
        grid = meadow()
        home = defended(frontier={"center": [0, 0]})
        self.assertEqual((flee_below(situation(grid, home)), fight_from(situation(grid, home))), (FLEE_BELOW, FIGHT_FROM))
        far = defended(frontier={"center": [-150, 0]})
        self.assertEqual((flee_below(situation(grid, far)), fight_from(situation(grid, far))), (40.0, 55.0))
        deeper = defended(frontier={"center": [-300, 0]})
        self.assertEqual(flee_below(situation(grid, deeper)), 45.0)

    def test_at_38_health_a_threat_sends_mimo_running_in_the_far_wilds_only(self):
        grid = meadow()
        grid.herd.add("gloomling", (5, 1, 0), 20.0, 0.0, 0.0, {"home": [5, 1, 0], "chasing": True})
        home = defended(inventory={"stone_sword": 1}, frontier={"center": [0, 0]})
        home["vitals"]["health"] = 38.0
        self.assertFalse(flee_due(situation(grid, home)))
        far = defended(inventory={"stone_sword": 1}, frontier={"center": [-150, 0]})
        far["vitals"]["health"] = 38.0
        self.assertTrue(flee_due(situation(grid, far)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_ringed.py"`
Expected: ERROR: `ImportError: cannot import name 'cap' from 'backend.survival.creatures.darkness'`

- [ ] **Step 3: The hooks in the creature modules**

In `backend/survival/creatures/darkness.py`, replace:

```python
those near Mimo caught under the open sky (backend.survival.creatures.hostiles, sunlit).
```

with:

```python
those near Mimo caught under the open sky (backend.survival.creatures.hostiles, sunlit).
L5: a new hostile may be shaped before it is added (BIRTHS: backend.survival.creatures.ringed makes
one born farther from home tougher), and the cap may grow (MORE_ROOM: ringed adds one a danger level).
```

and replace:

```python
import json
import math
import sqlite3
```

with:

```python
import json
import logging
import math
import sqlite3
```

and replace:

```python
from backend.survival.light import DARK, Lights, sky_light
```

with:

```python
from backend.survival.light import DARK, Lights, sky_light
from backend.survival.once import log_once

logger = logging.getLogger(__name__)
```

and replace:

```python
ANGLE, DISTANCE, KIND = 110, 111, 112
```

with:

```python
ANGLE, DISTANCE, KIND = 110, 111, 112
# L5: functions (scene, kind, cell, state, health) -> health that shape a new hostile before it is
# added (backend.survival.creatures.ringed), and functions of the Scene that add room under
# HOSTILE_CAP. One that crashes changes nothing (logged once).
BIRTHS: list = []
MORE_ROOM: list = []
```

and replace:

```python
    """A new hostile of `kind` in `cell`, at home there; its first turn comes a second later."""
    state = {"home": list(cell), "pose": "idle", "turn": 0}
    return scene.herd.add(kind.name, cell, kind.health, scene.at, scene.at + FIRST_TURN / scene.pace, state)
```

with:

```python
    """A new hostile of `kind` in `cell`, at home there; its first turn comes a second later. L5: the
    BIRTHS hooks may change its health and state first."""
    state = {"home": list(cell), "pose": "idle", "turn": 0}
    health = kind.health
    for shape in BIRTHS:
        try:
            health = float(shape(scene, kind, cell, state, health))
        except Exception as error:
            log_once(logger, "hostile birth", error)
    return scene.herd.add(kind.name, cell, health, scene.at, scene.at + FIRST_TURN / scene.pace, state)


def cap(scene: Scene) -> int:
    """How many hostiles may be alive: HOSTILE_CAP, plus what MORE_ROOM adds (L5)."""
    room = 0
    for more in MORE_ROOM:
        try:
            room += int(more(scene))
        except Exception as error:
            log_once(logger, "hostile cap", error)
    return HOSTILE_CAP + room
```

and replace:

```python
    if hostiles_alive(scene) >= HOSTILE_CAP:
```

with:

```python
    if hostiles_alive(scene) >= cap(scene):
```

In `backend/survival/creatures/hostiles.py`, replace:

```python
    hurt_pet(scene, kind.damage, kind.name)
```

with:

```python
    hurt_pet(scene, kind.damage + float(creature["state"].get("fiercer", 0.0)), kind.name)  # L5: ringed
```

In `backend/survival/creatures/view.py`, replace:

```python
the rest of the view, and a world from before L1 (an archive read without its schema update) has no
creatures.
"""
```

with:

```python
the rest of the view, and a world from before L1 (an archive read without its schema update) has no
creatures.
L5: a hostile born farther from home has more health (its "most"), and an elder says so (`elder`).
"""
```

and replace:

```python
    most = kind.health if kind is not None else max(creature["health"], 1.0)
```

with:

```python
    most = state.get("most") or (kind.health if kind is not None else max(creature["health"], 1.0))  # L5: ringed
```

and replace:

```python
        view["tame"] = True
```

with:

```python
        view["tame"] = True
    if state.get("elder"):
        view["elder"] = True  # L5: an elder, drawn glowing faintly
```

In `backend/survival/creatures/defense.py`, replace:

```python
  flee, being more urgent, takes over: Mimo fights, then flees.
```

with:

```python
  flee, being more urgent, takes over: Mimo fights, then flees.
L5: far from home both lines rise (`CAUTION`, backend.survival.creatures.ringed).
```

and replace:

```python
from __future__ import annotations

import math
```

with:

```python
from __future__ import annotations

import logging
import math
```

and replace:

```python
from backend.survival.memory import BUILT, cell_of
```

with:

```python
from backend.survival.memory import BUILT, cell_of
from backend.survival.once import log_once
```

and replace:

```python
THREAT_RISE = 2
```

with:

```python
THREAT_RISE = 2
# L5: functions of the Situation that add health points to both lines, flee's and fight's
# (backend.survival.creatures.ringed: 5 a danger level from the far wilds on). One that crashes adds
# nothing (logged once).
CAUTION: list = []

logger = logging.getLogger(__name__)


def caution(s: Situation) -> float:
    total = 0.0
    for more in CAUTION:
        try:
            total += float(more(s))
        except Exception as error:
            log_once(logger, "caution", error)
    return total


def flee_below(s: Situation) -> float:
    """Below this health a threat sends Mimo running: FLEE_BELOW, more far from home (L5)."""
    return FLEE_BELOW + caution(s)


def fight_from(s: Situation) -> float:
    """From this health Mimo stands its ground: FIGHT_FROM, more far from home (L5)."""
    return FIGHT_FROM + caution(s)
```

and replace:

```python
    if s.vitals["health"] < FLEE_BELOW:
```

with:

```python
    if s.vitals["health"] < flee_below(s):
```

and replace:

```python
    if not armed(s) or health < FLEE_BELOW:
```

with:

```python
    if not armed(s) or health < flee_below(s):
```

and replace:

```python
        if health < FIGHT_FROM and not (fighting or at_bay):
```

with:

```python
        if health < fight_from(s) and not (fighting or at_bay):
```

- [ ] **Step 4: Hostiles born in a ring**

Create `backend/survival/creatures/ringed.py`:

```python
"""Harder enemies farther out (L5, "Frontier"): a hostile born in a danger ring is tougher.

A hostile that comes out in ring n (backend.survival.rings, measured where it is born) has
HEALTH_PER_LEVEL (35 %) more health a level and hits 1 harder for every two levels. From the frontier
(3) a gloomling or a skitter may be an elder: one in four at 3, one in two in the deep frontier, with
half as much health again and one more damage; the viewer draws it glowing faintly. Its state keeps
what the viewer and the drops need: "ring", "most" (its full health, for the health bar), "fiercer"
(the damage its blow adds) and "elder". Home ground (0) is untouched, so life near home plays as
before.

Two more things grow with the ring Mimo stands in: the cap on hostiles near it (darkness.HOSTILE_CAP,
8) by one a level, and Mimo's caution: from the far wilds (2) on it runs 5 health points sooner a
level (defense.FLEE_BELOW, 35) and stands its ground only from 5 points more (defense.FIGHT_FROM,
50), since each blow out there costs more.
All three register into the hooks darkness and defense keep for them.
"""

from __future__ import annotations

from backend.survival.creatures.acts import Scene
from backend.survival.creatures.darkness import BIRTHS, MORE_ROOM
from backend.survival.creatures.defense import CAUTION
from backend.survival.creatures.kinds import Kind
from backend.survival.creatures.moves import roll
from backend.survival.grid import Cell
from backend.survival.rings import DEEPEST, ring_at, ring_here
from backend.survival.situation import Situation

HEALTH_PER_LEVEL = 0.35
DAMAGE_EVERY = 2  # levels for each point of damage a blow adds
ELDERS = ("gloomling", "skitter")
ELDER_FROM = 3
ELDER_CHANCE = {3: 0.25, 4: 0.5}
ELDER_HEALTH = 1.5
ELDER_DAMAGE = 1.0
CAUTION_FROM = 2
CAUTION_PER_LEVEL = 5.0
ELDER_ROLL = 114  # roll channel


def level_of(scene: Scene, cell: Cell) -> int:
    return min(DEEPEST, ring_at(scene.state, cell[0], cell[2]))


def elder_roll(scene: Scene, cell: Cell) -> float:
    return roll(scene.seed, cell[0] * 7919 + cell[1] * 131 + cell[2], int(scene.at * scene.scale), ELDER_ROLL)


def toughen(scene: Scene, kind: Kind, cell: Cell, state: dict, health: float) -> float:
    """A hostile born in ring n: more health, a harder blow, maybe an elder (see the module docstring)."""
    level = level_of(scene, cell)
    if level <= 0 or not kind.hostile:
        return health
    fiercer = float(level // DAMAGE_EVERY)
    health *= 1.0 + HEALTH_PER_LEVEL * level
    if kind.name in ELDERS and elder_roll(scene, cell) < ELDER_CHANCE.get(level, 0.0):
        state["elder"] = True
        health *= ELDER_HEALTH
        fiercer += ELDER_DAMAGE
    health = round(health, 1)
    state.update(ring=level, most=health)
    if fiercer:
        state["fiercer"] = fiercer
    return health


def more_room(scene: Scene) -> int:
    """One more hostile near Mimo for each level of the ring it stands in."""
    return min(DEEPEST, ring_here(scene.state))


def caution(s: Situation) -> float:
    """Health points Mimo adds to its flee and fight lines in the ring it stands in."""
    level = min(DEEPEST, ring_here(s.state))
    return CAUTION_PER_LEVEL * (level - CAUTION_FROM + 1) if level >= CAUTION_FROM else 0.0


BIRTHS.append(toughen)
MORE_ROOM.append(more_room)
CAUTION.append(caution)
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival.creatures import defense, gear, hunting  # noqa: F401  (L1's hunt; L2's make_gear, fight, flee)
```

with:

```python
from backend.survival.creatures import defense, gear, hunting  # noqa: F401  (L1's hunt; L2's make_gear, fight, flee)
from backend.survival.creatures import ringed  # noqa: F401  (L5: tougher hostiles farther from home)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_ringed.py"`
Expected: `Ran 8 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1132 tests` … `OK` (8 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/creatures/ringed.py backend/survival/creatures/darkness.py backend/survival/creatures/hostiles.py backend/survival/creatures/view.py backend/survival/creatures/defense.py backend/survival/brain.py backend/tests/test_survival_ringed.py
git commit -m "feat: hostiles born farther from home are tougher, elders from the frontier, one more allowed a level, and Mimo warier out there" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The thornback

**Files:**
- Create: `backend/survival/creatures/thornback.py`
- Modify: `backend/survival/creatures/kinds.py` (`Kind.shell`, `Kind.daylight`), `backend/survival/creatures/hostiles.py` (`sunlit` leaves a daylight kind be), `backend/survival/creatures/combat.py` (a melee blow through the shell), `backend/survival/creatures/simulate.py` (`SPAWNERS`), `backend/survival/creatures/defense.py` (`BOW_ONLY`, `outmatched`, shoot first), `backend/survival/brain.py` (imports `thornback`)
- Test: `backend/tests/test_survival_thornback.py`

**Interfaces:**
- Consumes: Task 1's `rings.ring_here`, `DEEPEST`; Task 2's `darkness.born` (so a thornback is toughened by its ring), `darkness.cap`; `darkness.spots`, `hostiles_alive`, `SPAWN_NEAR`, `SPAWN_FAR`; `light.sky_open`; `spawning.SIM_REACH`; the test helpers of Task 2.
- Produces:
  - `kinds.Kind` gains `shell: float = 0.0` and `daylight: bool = False`.
  - `simulate.SPAWNERS: list` of `(scene) -> list[dict]`, run after `spawn_hostiles` in every call (fight steps too).
  - `defense.BOW_ONLY: set[str]`, `defense.outmatched(s, found) -> bool`.
  - `thornback.THORNBACK` (the Kind), `SHELL = 0.6`, `FROM_RING = 2`, `SPAWN_EVERY = 90.0`, `CHANCE`, `MOST_NEAR = 2`; `thornbacks_near(scene)`, `spawn_thornbacks(scene)`. The viewer draws the kind (Task 10).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_thornback.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers the thornback, its spawner and the ringed hooks)
from backend.survival.creatures.archery import finish_shoot
from backend.survival.creatures.combat import finish_attack
from backend.survival.creatures.defense import fight_target, flee_due, plan_fight
from backend.survival.creatures.hostiles import sunlit
from backend.survival.creatures.kinds import KINDS, huntable
from backend.survival.creatures.thornback import MOST_NEAR, SPAWN_EVERY, spawn_thornbacks
from backend.tests.test_survival_darkness import DAY, land, scene
from backend.tests.test_survival_defense import meadow, pet as defended, situation
from backend.tests.test_survival_ringed import far_out

THORNBACK = KINDS["thornback"]


class KindTests(unittest.TestCase):
    def test_a_slow_armoured_hostile_that_walks_by_day(self):
        self.assertTrue(THORNBACK.hostile and THORNBACK.daylight)
        self.assertEqual((THORNBACK.health, THORNBACK.speed, THORNBACK.damage, THORNBACK.shell), (24.0, 1.2, 4.0, 0.6))
        self.assertFalse(huntable(THORNBACK))

    def test_the_sun_neither_burns_nor_fades_it(self):
        grid = land()
        creature = grid.herd.add("thornback", (5, 1, 0), 24.0, 0.0, 0.0, {"home": [5, 1, 0]})
        gloomling = grid.herd.add("gloomling", (6, 1, 0), 20.0, 0.0, 0.0, {"home": [6, 1, 0]})
        by_day = scene(grid, far_out(), clock=DAY)
        with patch("backend.survival.light.terrain_height", lambda x, z, seed: 0):
            self.assertFalse(sunlit(creature, THORNBACK, by_day))
            self.assertTrue(sunlit(gloomling, KINDS["gloomling"], by_day))


class ShellTests(unittest.TestCase):
    def test_a_sword_blow_loses_most_of_its_bite_but_an_arrow_gets_through(self):
        grid = meadow()
        target = grid.herd.add("thornback", (1, 1, 0), 24.0, 0.0, 0.0, {"home": [1, 1, 0]})
        state = defended(inventory={"stone_sword": 1, "bow": 1, "arrow": 2})
        finish_attack({"kind": "attack", "creature": target["id"], "weapon": "stone_sword"}, state, grid, 1.0, [])
        self.assertEqual(grid.herd.get(target["id"])["health"], 22.0)  # 5, less 60 %
        finish_shoot({"kind": "shoot", "creature": target["id"], "hit": True}, state, grid, 2.0, [])
        self.assertEqual(grid.herd.get(target["id"])["health"], 17.0)  # an arrow's full 5


class MeetingTests(unittest.TestCase):
    def test_with_only_a_sword_mimo_runs_from_a_thornback_close_by(self):
        grid = meadow()
        grid.herd.add("thornback", (4, 1, 0), 24.0, 0.0, 0.0, {"home": [4, 1, 0], "chasing": True})
        sworded = situation(grid, defended(inventory={"iron_sword": 1}))
        self.assertIsNone(fight_target(sworded))
        self.assertTrue(flee_due(sworded))

    def test_with_a_bow_mimo_shoots_it_even_in_sword_reach(self):
        grid = meadow()
        grid.herd.add("thornback", (2, 1, 0), 24.0, 0.0, 0.0, {"home": [2, 1, 0], "chasing": True})
        s = situation(grid, defended(inventory={"iron_sword": 1, "bow": 1, "arrow": 8}))
        self.assertFalse(flee_due(s))
        self.assertEqual(fight_target(s)["kind"], "thornback")
        self.assertEqual([step["kind"] for step in plan_fight(s, None)], ["shoot"])


class SpawnTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.survival.creatures.darkness.terrain_height", "backend.survival.light.terrain_height"):
            patcher = patch(target, lambda x, z, seed: 0)
            patcher.start()
            self.addCleanup(patcher.stop)

    def chances(self, state, grid, calls=30):
        found = []
        for call in range(calls):
            found += spawn_thornbacks(scene(grid, state, at=100.0 + call * SPAWN_EVERY, clock=DAY))
        return found

    def test_none_come_out_nearer_home_than_the_far_wilds(self):
        self.assertEqual(self.chances(far_out(100.0), land()), [])

    def test_in_the_far_wilds_they_come_out_by_day_on_open_ground_and_tougher(self):
        grid = land()
        found = self.chances(far_out(150.0), grid)
        self.assertEqual(len(found), MOST_NEAR)  # no more than two near Mimo
        for creature in found:
            self.assertEqual(creature["kind"], "thornback")
            self.assertTrue(20 <= abs(complex(creature["x"] - 150.0, creature["z"])) <= 41)
            self.assertEqual((creature["y"], creature["health"], creature["state"]["ring"]), (1.0, 40.8, 2))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_thornback.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.creatures.thornback'`

- [ ] **Step 3: A shell, the daylight and the spawners**

In `backend/survival/creatures/kinds.py`, replace:

```python
hostile kinds register themselves the same way, with `hostile`, `damage` and `reach` set.
```

with:

```python
hostile kinds register themselves the same way, with `hostile`, `damage` and `reach` set. L5's
thornback adds a `shell` against melee blows and walks by `daylight`.
```

and replace:

```python
    height: int = 1  # L2: cells of room it needs to pass (a gloomling needs 2)
```

with:

```python
    height: int = 1  # L2: cells of room it needs to pass (a gloomling needs 2)
    shell: float = 0.0  # L5: the share of a sword or fist blow its shell takes off (arrows get through)
    daylight: bool = False  # L5: it walks by day too: the sun neither burns nor fades it
```

In `backend/survival/creatures/hostiles.py`, replace:

```python
    return kind.hostile and not scene.night and sky_open(scene.grid, scene.seed, where(creature, scene.at))
```

with:

```python
    return (kind.hostile and not kind.daylight and not scene.night  # L5: a thornback walks by day
            and sky_open(scene.grid, scene.seed, where(creature, scene.at)))
```

In `backend/survival/creatures/combat.py`, replace:

```python
(the lunge); one that ran off in the meantime is missed, which is no failure.
```

with:

```python
(the lunge); one that ran off in the meantime is missed, which is no failure. L5: a kind with a
`shell` (the thornback) takes that share off the blow; an arrow (creatures.archery) gets through.
```

and replace:

```python
    damage, _ = blow(step.get("weapon"))
```

with:

```python
    damage, _ = blow(step.get("weapon"))
    kind = kind_of(creature["kind"])
    if kind is not None:
        damage *= 1.0 - kind.shell  # L5: a thornback's shell takes the edge off a melee blow
```

In `backend/survival/creatures/simulate.py`, replace:

```python
UNKNOWN_WAIT = 60.0  # server seconds a creature of a kind no longer registered waits between turns
```

with:

```python
UNKNOWN_WAIT = 60.0  # server seconds a creature of a kind no longer registered waits between turns
# L5: functions of the Scene that may add creatures after the dark's hostiles (the thornback's spawner,
# backend.survival.creatures.thornback), each returning what it added. One that crashes adds none.
SPAWNERS: list = []
```

and replace:

```python
    loaded += spawn_hostiles(scene)
```

with:

```python
    loaded += spawn_hostiles(scene)
    for spawner in SPAWNERS:  # L5: the thornback's
        try:
            loaded += spawner(scene)
        except Exception as error:
            log_once(logger, "creature spawner", error)
```

- [ ] **Step 4: Meeting it with the bow**

In `backend/survival/creatures/defense.py`, replace:

```python
L5: far from home both lines rise (`CAUTION`, backend.survival.creatures.ringed).
```

with:

```python
L5: far from home both lines rise (`CAUTION`, backend.survival.creatures.ringed), and a thornback
(`BOW_ONLY`) is met with the bow alone, or run from.
```

and replace:

```python
CAUTION: list = []
```

with:

```python
CAUTION: list = []
# L5: kinds Mimo meets only with a bow (the thornback's shell turns a sword): it shoots them even in
# sword reach, never swings at them, and runs from one near it when it has no bow and arrows.
BOW_ONLY: set[str] = set()
```

and replace:

```python
    if armed(s):
```

with:

```python
    if armed(s) and not outmatched(s, found):
```

and replace:

```python
    return (chaser if chaser is not None else chasing_near(s, GIVE_UP)) is not None
```

with:

```python
    return (chaser if chaser is not None else chasing_near(s, GIVE_UP)) is not None


def outmatched(s: Situation, found: list[dict]) -> bool:
    """L5: the nearest threat is one Mimo meets only with a bow (BOW_ONLY), and it has none ready."""
    return bool(found) and found[0]["kind"] in BOW_ONLY and not bow_ready(s)
```

and replace:

```python
    for creature in threats(s):
```

with:

```python
    for creature in threats(s):
        if creature["kind"] in BOW_ONLY and not bow_ready(s):
            continue  # L5: a sword is no use against its shell
```

and replace:

```python
    if bow_ready(s) and (distance >= SHOOT_FROM or sword is None) and distance <= SHOOT_RANGE:
```

with:

```python
    if bow_ready(s) and (distance >= SHOOT_FROM or sword is None or target["kind"] in BOW_ONLY) \
            and distance <= SHOOT_RANGE:
```

- [ ] **Step 5: The thornback**

Create `backend/survival/creatures/thornback.py`:

```python
"""The thornback (L5, "Frontier"): a slow, heavily armoured crawler of the far wilds and beyond.

- thornback: 24 health, slow (1.2 s a block, a quarter of Mimo's pace), a blow of 4 every 1.8 s from
  1.6 blocks. Its shell of thorny plates takes SHELL (60 %) off every sword or fist blow, but an arrow
  finds the gaps between them, so arrows are its weakness (creatures.combat: the shell only stops
  a melee blow). It walks by day as well as by night (`daylight`: the sun neither burns nor fades
  it) and drops 1 or 2 flint (its thorns make arrowheads) and sometimes a leather hide. Born in a
  ring, it is tougher like any hostile (backend.survival.creatures.ringed): 41 health in the far wilds.
- Where it comes from: only from the far wilds (danger 2) on, measured where Mimo stands. Once every
  SPAWN_EVERY game seconds, by day or night, it gets a chance of CHANCE (by the ring) to come out on
  open ground 20 to 40 blocks from Mimo, while fewer than MOST_NEAR thornbacks are near it and the
  hostile cap has room (darkness.cap). Light does not keep it away; like any hostile it fades after
  loitering (hostiles.prowl) and goes when Mimo leaves it far behind (darkness.despawn_far).
- Mimo meets it with a bow: a thornback is in defense.BOW_ONLY, so Mimo shoots it even in sword
  reach, never swings at it, and runs from it when it has no bow and arrows. It is too slow to catch
  a pet that runs.
The spawner registers into the creature hook's SPAWNERS (backend.survival.creatures.simulate).
"""

from __future__ import annotations

import math

from backend.survival.creatures.acts import Scene
from backend.survival.creatures.darkness import SPAWN_FAR, SPAWN_NEAR, born, cap, hostiles_alive, spots
from backend.survival.creatures.defense import BOW_ONLY
from backend.survival.creatures.kinds import Kind, register_kind
from backend.survival.creatures.moves import roll
from backend.survival.creatures.simulate import SPAWNERS
from backend.survival.creatures.spawning import SIM_REACH
from backend.survival.creatures.table import dead
from backend.survival.light import sky_open
from backend.survival.rings import DEEPEST, ring_here

SHELL = 0.6
THORNBACK = register_kind(Kind("thornback", health=24.0, speed=1.2, size=0.9, hostile=True, damage=4.0, reach=1.6,
                               drops={"flint": (1, 2), "leather": 0.3}, flee_when_hurt=False, cooldown=1.8,
                               shell=SHELL, daylight=True))
FROM_RING = 2
SPAWN_EVERY = 90.0  # game seconds between two chances
CHANCE = {2: 0.35, 3: 0.5, 4: 0.65}
MOST_NEAR = 2
TRIES = 4
# Roll channels.
CHANCE_ROLL, ANGLE, DISTANCE = 115, 116, 117


def thornbacks_near(scene: Scene) -> int:
    x, _, z = scene.pet
    return sum(1 for creature in scene.herd.near(x, z, SIM_REACH, kinds=[THORNBACK.name]) if not dead(creature))


def spawn_thornbacks(scene: Scene) -> list[dict]:
    """Maybe bring a thornback out near Mimo, from the far wilds on (see the module docstring)."""
    level = min(DEEPEST, ring_here(scene.state))
    if level < FROM_RING:
        return []
    last = scene.state.get("thornback_at")
    if last is not None and (scene.at - last) * scene.scale < SPAWN_EVERY:
        return []
    scene.state["thornback_at"] = scene.at
    salt = int(scene.at * scene.scale)
    if roll(scene.seed, salt, 0, CHANCE_ROLL) >= CHANCE[level] or thornbacks_near(scene) >= MOST_NEAR:
        return []
    if hostiles_alive(scene) >= cap(scene):
        return []
    x, y, z = scene.pet
    for attempt in range(TRIES):
        angle = 2 * math.pi * roll(scene.seed, salt, attempt, ANGLE)
        reach = SPAWN_NEAR + (SPAWN_FAR - SPAWN_NEAR) * roll(scene.seed, salt, attempt, DISTANCE)
        cx, cz = round(x + math.cos(angle) * reach), round(z + math.sin(angle) * reach)
        for cell in spots(scene.grid, scene.seed, cx, cz, y)[:1]:
            if sky_open(scene.grid, scene.seed, cell):
                return [born(scene, THORNBACK, cell)]
    return []


SPAWNERS.append(spawn_thornbacks)
BOW_ONLY.add(THORNBACK.name)
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival.creatures import ringed  # noqa: F401  (L5: tougher hostiles farther from home)
```

with:

```python
from backend.survival.creatures import ringed, thornback  # noqa: F401  (L5: tougher hostiles, the thornback)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_thornback.py"`
Expected: `Ran 7 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1139 tests` … `OK` (7 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/creatures/thornback.py backend/survival/creatures/kinds.py backend/survival/creatures/hostiles.py backend/survival/creatures/combat.py backend/survival/creatures/simulate.py backend/survival/creatures/defense.py backend/survival/brain.py backend/tests/test_survival_thornback.py
git commit -m "feat: the thornback, a slow armoured crawler of the far wilds that walks by day and only arrows hurt well" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Better loot farther out: drops, mining luck, gold nuggets and amber

**Files:**
- Create: `backend/survival/loot.py`
- Modify: `backend/survival/creatures/combat.py` (`EXTRA_DROPS`, `more_drops`), `backend/survival/steps.py` (`MINED`), `backend/services/crafting.py` (the `gold_nuggets` recipe), `backend/survival/toolmaking.py` (`POOLED`, `pooled`), `backend/survival/carrying.py` (amber and nuggets are treasures), `backend/survival/brain.py` (imports `loot`)
- Test: `backend/tests/test_survival_loot.py`

**Interfaces:**
- Consumes: Task 1's `rings.ring_at`, `DEEPEST`; Task 2's creature state `ring` and `elder`; Task 3's thornback kind; `nature.roll`; `creatures.moves.roll`; `crafting.BLOCKS` (a block's `drop`); the test helpers `test_survival_defense.meadow`, `pet`.
- Produces:
  - `combat.EXTRA_DROPS: list` of `(seed, creature, kind) -> {item: count}`; `combat.more_drops(seed, creature, kind, found) -> dict`.
  - `steps.MINED: list` of `(state, cell, block) -> list[str]`.
  - `toolmaking.POOLED = {"gold_ingot": "gold_nuggets"}`; `toolmaking.pooled(inventory, item, steps) -> bool`.
  - `loot.ring_drops(seed, creature, kind)`, `loot.extra_ore(state, cell, block)` and their constants; items `gold_nugget`, `amber`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_loot.py`:

```python
import unittest

from backend.survival import brain  # noqa: F401  (registers the loot hooks)
from backend.survival.carrying import valuable
from backend.survival.creatures.combat import finish_attack
from backend.survival.creatures.kinds import KINDS
from backend.survival.grid import Grid
from backend.survival.loot import extra_ore, ring_drops
from backend.survival.steps import finish_mine
from backend.survival.toolmaking import make
from backend.tests.test_survival_defense import meadow, pet

SEED = "5"


def hostile(number, kind="gloomling", **state):
    return {"id": number, "kind": kind, "state": dict(state)}


def share(kind, item, ring, count=600, **state):
    """How often a hostile of `kind` born in `ring` drops `item`, over `count` creatures."""
    return sum(item in ring_drops(SEED, hostile(number, kind, ring=ring, **state), KINDS[kind])
               for number in range(1, count + 1)) / count


class DropTests(unittest.TestCase):
    def test_at_home_and_from_animals_nothing_more(self):
        self.assertEqual(ring_drops(SEED, hostile(1), KINDS["gloomling"]), {})
        self.assertEqual(ring_drops(SEED, hostile(1, "cow", ring=3), KINDS["cow"]), {})

    def test_farther_out_the_drops_grow_richer(self):
        self.assertAlmostEqual(share("gloomling", "gloom_dust", 1), 0.4, delta=0.06)
        self.assertEqual(share("skitter", "gold_nugget", 1), 0.0)
        self.assertAlmostEqual(share("skitter", "gold_nugget", 2), 0.3, delta=0.06)
        self.assertAlmostEqual(share("skitter", "amber", 2), 0.12, delta=0.04)
        self.assertEqual(share("skitter", "diamond", 2), 0.0)
        self.assertAlmostEqual(share("skitter", "diamond", 3), 0.06, delta=0.03)
        self.assertAlmostEqual(share("thornback", "amber", 2), 0.27, delta=0.06)
        self.assertAlmostEqual(share("skitter", "amber", 3, elder=True), 0.48, delta=0.07)

    def test_the_same_kill_always_drops_the_same(self):
        creature = hostile(42, "skitter", ring=3)
        self.assertEqual(ring_drops(SEED, creature, KINDS["skitter"]), ring_drops(SEED, creature, KINDS["skitter"]))

    def test_a_kill_brings_them_into_mimo_s_arms(self):
        number = next(number for number in range(1, 400)
                      if "amber" in ring_drops("5", hostile(number, "skitter", ring=2), KINDS["skitter"]))
        grid = meadow()
        for _ in range(number):
            grid.herd.add("skitter", (1, 1, 0), 1.0, 0.0, 0.0, {"home": [1, 1, 0], "ring": 2})
        state = pet(inventory={"stone_sword": 1})
        finish_attack({"kind": "attack", "creature": number, "weapon": "stone_sword"}, state, grid, 1.0, [])
        self.assertEqual(state["inventory"].get("amber"), 1)
        self.assertIn("amber", grid.herd.get(number)["state"]["drops"])


class MiningTests(unittest.TestCase):
    def test_an_ore_mined_far_from_home_sometimes_gives_one_more(self):
        state = {"world_seed": SEED, "frontier": {"center": [0, 0]}, "position": {"x": 0.0, "y": 0.0, "z": 0.0}}
        cells = [(150 + x, -5, z) for x in range(20) for z in range(20)]
        lucky = [cell for cell in cells if extra_ore(state, cell, "iron_ore")]
        self.assertAlmostEqual(len(lucky) / len(cells), 0.10, delta=0.04)  # 5 % a level, in the far wilds
        self.assertEqual([cell for cell in cells if extra_ore(state, (cell[0] - 150, cell[1], cell[2]), "iron_ore")], [])
        self.assertEqual(extra_ore(state, lucky[0], "stone"), [])
        grid = Grid(lambda x, y, z: "iron_ore" if (x, y, z) == lucky[0] else "air")
        state["inventory"] = {}
        finish_mine({"kind": "mine", "target": {"x": lucky[0][0], "y": lucky[0][1], "z": lucky[0][2]},
                     "block": "iron_ore"}, state, grid, 1.0)
        self.assertEqual(state["inventory"], {"iron_ore": 2})


class ItemTests(unittest.TestCase):
    def test_four_gold_nuggets_make_an_ingot_when_there_is_no_ore_to_smelt(self):
        inventory, steps = {"gold_nugget": 12, "sticks": 2}, []
        make(inventory, "gold_pickaxe", 1, steps)
        self.assertEqual([step.get("recipe") for step in steps], ["gold_nuggets"] * 3 + ["gold_pickaxe"])
        self.assertEqual(inventory.get("gold_nugget", 0), 0)

    def test_amber_and_nuggets_are_worth_carrying(self):
        self.assertTrue(valuable("amber") and valuable("gold_nugget"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_loot.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.loot'`

- [ ] **Step 3: Room for more drops and more ore**

In `backend/survival/creatures/combat.py`, replace:

```python
the creature, so they never depend on how often the tick ran.
```

with:

```python
the creature, so they never depend on how often the tick ran. L5: EXTRA_DROPS add to them
(backend.survival.loot: a hostile born farther from home drops more).
```

and replace:

```python
from __future__ import annotations

import math
```

with:

```python
from __future__ import annotations

import logging
import math
```

and replace:

```python
from backend.survival.grid import Cell, Grid
```

with:

```python
from backend.survival.grid import Cell, Grid
from backend.survival.once import log_once
```

and replace:

```python
DROP_CHANNEL = 70
```

with:

```python
DROP_CHANNEL = 70
# L5: functions (seed, creature, kind) -> {item: count} a dead creature drops besides its kind's own
# (backend.survival.loot: better drops farther from home). One that crashes adds nothing (logged once).
EXTRA_DROPS: list = []

logger = logging.getLogger(__name__)
```

and replace:

```python
def reached(path: list[dict] | None, at: float) -> list[dict] | None:
```

with:

```python
def more_drops(seed: str, creature: dict, kind: Kind | None, found: dict[str, int]) -> dict[str, int]:
    """`found` and what EXTRA_DROPS add to it (L5)."""
    total = dict(found)
    for extra in EXTRA_DROPS:
        try:
            for item, count in extra(seed, creature, kind).items():
                if count > 0:
                    total[item] = total.get(item, 0) + int(count)
        except Exception as error:
            log_once(logger, "extra drops", error)
    return total


def reached(path: list[dict] | None, at: float) -> list[dict] | None:
```

and replace:

```python
        found = drops_of(scene.seed, creature, kind) if kind is not None else {}
```

with:

```python
        found = more_drops(scene.seed, creature, kind, drops_of(scene.seed, creature, kind) if kind is not None else {})
```

In `backend/survival/steps.py`, replace:

```python
is sleep in a bed.
```

with:

```python
is sleep in a bed. L5: MINED may add to what a mine drops (backend.survival.loot).
```

and replace:

```python
import math
from dataclasses import dataclass
```

with:

```python
import logging
import math
from dataclasses import dataclass
```

and replace:

```python
from backend.survival.pathing import MAX_NODES, route, timed_path
```

with:

```python
from backend.survival.once import log_once
from backend.survival.pathing import MAX_NODES, route, timed_path

logger = logging.getLogger(__name__)
```

and replace:

```python
MAX_SEGMENTS = 12
```

with:

```python
MAX_SEGMENTS = 12
# L5: functions (state, cell, block) -> items a finished mine drops besides the block's own (backend.
# survival.loot: an extra ore farther from home). One that crashes adds nothing (logged once).
MINED: list = []
```

and replace:

```python
        add_item(state["inventory"], item)
```

with:

```python
        add_item(state["inventory"], item)
    for more in MINED:
        try:
            extra = list(more(state, target, step["block"]))
        except Exception as error:
            log_once(logger, "mined", error)
            continue
        for item in extra:
            add_item(state["inventory"], item)
```

- [ ] **Step 4: Gold nuggets and amber**

In `backend/services/crafting.py`, replace:

```python
    "fence": {"ingredients": {"planks": 4, "sticks": 2}, "output": {"fence": 3}},
```

with:

```python
    "fence": {"ingredients": {"planks": 4, "sticks": 2}, "output": {"fence": 3}},
})
# L5, the frontier: gold nuggets that far-off hostiles and ruins give, 4 to a gold ingot, anywhere.
RECIPES.update({
    "gold_nuggets": {"ingredients": {"gold_nugget": 4}, "output": {"gold_ingot": 1}},
```

In `backend/survival/toolmaking.py`, replace:

```python
LANTERNS_WANTED = 4  # lanterns Mimo makes to carry home (light_up hangs them), from spare iron
```

with:

```python
LANTERNS_WANTED = 4  # lanterns Mimo makes to carry home (light_up hangs them), from spare iron
# L5: an item small pieces make too, by the recipe named here (4 gold nuggets make a gold ingot),
# made that way when there is no ore to smelt for it (`pooled`).
POOLED = {"gold_ingot": "gold_nuggets"}
```

and replace:

```python
            ore = SMELTED[item]
```

with:

```python
            ore = SMELTED[item]
            if inventory.get(ore, 0) < 1 and pooled(inventory, item, steps):
                continue
```

and replace:

```python
        else:
            raise Short(item)
```

with:

```python
        else:
            raise Short(item)


def pooled(inventory: dict, item: str, steps: list[dict]) -> bool:
    """L5: craft one `item` from its small pieces (POOLED) when Mimo carries enough of them; False when
    it does not."""
    name = POOLED.get(item)
    recipe = RECIPES.get(name) if name else None
    if recipe is None or any(have(inventory, part) < count for part, count in recipe["ingredients"].items()):
        return False
    for part, count in paid(inventory, recipe["ingredients"]).items():
        inventory[part] -= count
    for part, count in recipe["output"].items():
        inventory[part] = inventory.get(part, 0) + count
    steps.append({"kind": "craft", "recipe": name})
    return True
```

In `backend/survival/carrying.py`, replace:

```python
TREASURES = ("diamond", "creature_seed", "iron_cap", "iron_tunic", "lantern")
```

with:

```python
TREASURES = ("diamond", "creature_seed", "iron_cap", "iron_tunic", "lantern")
TREASURES += ("amber", "gold_nugget")  # L5: the frontier's riches (backend.survival.loot)
```

- [ ] **Step 5: The loot**

Create `backend/survival/loot.py`:

```python
"""Better loot farther out (L5, "Frontier"): hostile drops and mining luck grow with the ring.

- A hostile born in ring n (its state's "ring", backend.survival.creatures.ringed) drops more than its
  kind's own drops (combat.EXTRA_DROPS):
  - from danger 1, a gloomling drops one more gloom dust, with a chance of 0.4 at 1 and 0.2 more a
    level (1 from the frontier on);
  - from danger 2, 1 to 3 gold nuggets (a chance of 0.3, and 0.1 more a level) and amber, a new gem
    (0.12 a level past 1: 12 % in the far wilds, 24 % in the frontier, 36 % in the deep frontier; a
    thornback's shell holds 0.15 more);
  - from danger 3, a diamond (0.06 a level past 2).
  An elder's chances are doubled (at most 1). Each is rolled from the world seed and the creature on
  a channel of its own, like its kind's own drops (combat.drops_of), so a kill always drops the same.
- Mining an ore in ring n drops one more of what the ore gives (coal, raw iron, a diamond, ...) with a
  chance of EXTRA_ORE_PER_LEVEL (5 %) a level, rolled from the world seed and the cell (steps.MINED).
- Two new items: gold nuggets (4 make a gold ingot, the "gold_nuggets" recipe; toolmaking crafts one
  when it needs gold and has no gold ore to smelt, toolmaking.POOLED) and amber (amber-studded armor,
  backend.survival.frontier_gear). Both are treasures a full pair of arms makes room for
  (carrying.TREASURES).
Home ground (0) drops and mines exactly as before.
"""

from __future__ import annotations

from backend.services.crafting import BLOCKS
from backend.survival import nature
from backend.survival.creatures.combat import EXTRA_DROPS
from backend.survival.creatures.kinds import Kind
from backend.survival.creatures.moves import roll
from backend.survival.grid import Cell
from backend.survival.rings import DEEPEST, ring_at
from backend.survival.steps import MINED

GLOOM_FROM, GLOOM_CHANCE, GLOOM_PER_LEVEL = 1, 0.4, 0.2
GOLD_FROM, GOLD_CHANCE, GOLD_PER_LEVEL, GOLD_COUNT = 2, 0.3, 0.1, (1, 3)
AMBER_FROM, AMBER_PER_LEVEL, THORNBACK_AMBER = 2, 0.12, 0.15
DIAMOND_FROM, DIAMOND_PER_LEVEL = 3, 0.06
ELDER_TIMES = 2.0
EXTRA_ORE_PER_LEVEL = 0.05
ORES = ("coal_ore", "iron_ore", "copper_ore", "gold_ore", "diamond_ore")
# Roll channels (a kind's own drops use combat.DROP_CHANNEL, 70 and up).
GLOOM_ROLL, GOLD_ROLL, GOLD_COUNT_ROLL, AMBER_ROLL, DIAMOND_ROLL, EXTRA_ORE_ROLL = 120, 121, 122, 123, 124, 125


def ring_drops(seed: str, creature: dict, kind: Kind | None) -> dict[str, int]:
    """What a hostile born in a ring drops besides its kind's own (see the module docstring)."""
    state = creature["state"]
    level = min(DEEPEST, int(state.get("ring", 0)))
    if kind is None or not kind.hostile or level <= 0:
        return {}
    times = ELDER_TIMES if state.get("elder") else 1.0

    def lucky(chance: float, channel: int) -> bool:
        return roll(seed, creature["id"], 0, channel) < min(1.0, chance * times)

    found = {}
    if kind.name == "gloomling" and lucky(GLOOM_CHANCE + GLOOM_PER_LEVEL * (level - GLOOM_FROM), GLOOM_ROLL):
        found["gloom_dust"] = 1
    if level >= GOLD_FROM and lucky(GOLD_CHANCE + GOLD_PER_LEVEL * (level - GOLD_FROM), GOLD_ROLL):
        low, high = GOLD_COUNT
        found["gold_nugget"] = low + int(roll(seed, creature["id"], 0, GOLD_COUNT_ROLL) * (high - low + 1))
    amber = AMBER_PER_LEVEL * (level - 1) + (THORNBACK_AMBER if kind.name == "thornback" else 0.0)
    if level >= AMBER_FROM and lucky(amber, AMBER_ROLL):
        found["amber"] = 1
    if level >= DIAMOND_FROM and lucky(DIAMOND_PER_LEVEL * (level - DIAMOND_FROM + 1), DIAMOND_ROLL):
        found["diamond"] = 1
    return found


def extra_ore(state: dict, cell: Cell, block: str) -> list[str]:
    """One more of what a mined ore gives, sometimes, in a ring past home ground."""
    drop = BLOCKS.get(block, {}).get("drop")
    level = min(DEEPEST, ring_at(state, cell[0], cell[2]))
    if block not in ORES or not drop or level <= 0:
        return []
    return [drop] if nature.roll(state["world_seed"], cell, EXTRA_ORE_ROLL) < EXTRA_ORE_PER_LEVEL * level else []


EXTRA_DROPS.append(ring_drops)
MINED.append(extra_ore)
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival.creatures import ringed, thornback  # noqa: F401  (L5: tougher hostiles, the thornback)
```

with:

```python
from backend.survival.creatures import ringed, thornback  # noqa: F401  (L5: tougher hostiles, the thornback)
from backend.survival import loot  # noqa: F401  (L5: better drops and mining luck farther out)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_loot.py"`
Expected: `Ran 7 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1146 tests` … `OK` (7 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/loot.py backend/survival/creatures/combat.py backend/survival/steps.py backend/services/crafting.py backend/survival/toolmaking.py backend/survival/carrying.py backend/survival/brain.py backend/tests/test_survival_loot.py
git commit -m "feat: better loot farther out - more gloom dust, gold nuggets, amber and diamonds from hostiles, an extra ore now and then, and nuggets into gold ingots" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Frontier ruins in worldgen, in both ports

**Files:**
- Modify: `backend/services/worldgen.py` (`RUIN_*`, `region_ruin`, `ruin_column`, `ruin_block`; `plant_stack` and `decoration_at`), `frontend/src/engine/worldgen.ts` (`regionRuin`, `ruinColumn`, `ruinBlock`; `plantStack`, `decorationAt`, `generateColumn`), `frontend/src/survival/overheadMap.ts` (`naturalTop` shows ruins), `backend/scripts/worldgen_fixture.py` (`_ruins`), `shared/worldgen-fixture.json` (regenerated)
- Test: `backend/tests/test_worldgen_ruins.py` (create), `backend/tests/test_worldgen.py`, `frontend/src/engine/worldgen.test.ts`, `frontend/src/survival/overheadMap.test.ts` (modify)

**Interfaces:**
- Consumes: worldgen's `hash32`, `terrain_height`, `swamp_pool`, `surface_opened`, `tree_base`, `rock_column` (and the TS twins).
- Produces:
  - Python: `RUIN_REGION = 96`, `RUIN_ODDS = 2`, `RUIN_MARGIN = 12`, `RUIN_HALF = 3`, `RUIN_TOP = 3`, `RUIN_SLOPE = 2`; `region_ruin(rx, rz, seed) -> (x, z, ground) | None` (cached); `ruin_column(x, z, seed) -> ("chest" | "wall", top y) | None`; `ruin_block(x, y, z, seed, part) -> str`.
  - TypeScript: `regionRuin(rx, rz, seed): [x, z, ground] | null`, `ruinColumn(x, z, seed): [string, number] | null` (exported), `ruinBlock` (module-private).
  - A ruin's chest is the natural block `chest` at `(x, ground + 1, z)`; Task 6 finds it by `region_ruin`.

- [ ] **Step 1: Write the failing tests**

Create the Python ruin tests, and add ruins to the fixture's features and to both ports' parity tests:

Create `backend/tests/test_worldgen_ruins.py`:

```python
import math
import unittest

from backend.services.worldgen import (
    LEGACY_RADIUS, RUIN_HALF, RUIN_REGION, RUIN_SLOPE, SEA_LEVEL, block_at, plant_stack, region_ruin, rock_column,
    ruin_column, surface_opened, terrain_height, tree_base,
)

SEED = "123456789123456789"
WALLS = ("stone_bricks", "mossy_cobblestone")


def ruins(count=6, rxs=range(3, 60)):
    found = []
    for rx in rxs:
        for rz in range(-30, 30):
            ruin = region_ruin(rx, rz, SEED)
            if ruin is not None:
                found.append(ruin)
                if len(found) == count:
                    return found
    return found


def square(ruin):
    x, z, _ = ruin
    return [(x + dx, z + dz) for dx in range(-RUIN_HALF, RUIN_HALF + 1) for dz in range(-RUIN_HALF, RUIN_HALF + 1)]


class RuinTests(unittest.TestCase):
    def test_some_regions_hold_a_ruin_and_the_same_seed_always_places_it_the_same(self):
        found = [region_ruin(rx, rz, SEED) for rx in range(30, 50) for rz in range(-10, 10)]
        share = sum(ruin is not None for ruin in found) / len(found)
        self.assertTrue(0.15 < share < 0.4, share)
        region_ruin.cache_clear()
        self.assertEqual(found, [region_ruin(rx, rz, SEED) for rx in range(30, 50) for rz in range(-10, 10)])
        self.assertNotEqual(found, [region_ruin(rx, rz, "42") for rx in range(30, 50) for rz in range(-10, 10)])

    def test_none_stands_near_the_legacy_clearing(self):
        reach = (LEGACY_RADIUS + RUIN_REGION) // RUIN_REGION
        for rx in range(-reach, reach):
            for rz in range(-reach, reach):
                ruin = region_ruin(rx, rz, SEED)
                self.assertTrue(ruin is None or math.hypot(ruin[0], ruin[1]) > LEGACY_RADIUS)

    def test_it_stands_on_dry_even_ground_with_no_tree_rock_or_cave_mouth(self):
        for ruin in ruins(8) + ruins(4, range(-60, -3)):
            for x, z in square(ruin):
                height = terrain_height(x, z, SEED)
                self.assertGreater(height, SEA_LEVEL)
                self.assertLessEqual(abs(height - ruin[2]), RUIN_SLOPE)
                self.assertFalse(surface_opened(x, z, SEED))
                self.assertIsNone(tree_base(x, z, SEED))
                self.assertIsNone(rock_column(x, z, SEED))

    def test_an_old_chest_in_the_middle_and_broken_walls_of_stone_bricks_and_moss_round_it(self):
        for ruin in ruins(6):
            x, z, ground = ruin
            self.assertEqual(block_at(x, ground + 1, z, SEED), "chest")
            self.assertEqual(block_at(x, ground + 2, z, SEED), "air")
            walls = [(wx, wz) for wx, wz in square(ruin) if max(abs(wx - x), abs(wz - z)) == RUIN_HALF]
            standing = [cell for cell in walls if ruin_column(*cell, SEED)]
            self.assertLess(len(standing), len(walls))  # a doorway, and gaps where the wall fell
            for wx, wz in standing:
                _, top = ruin_column(wx, wz, SEED)
                ground_here = terrain_height(wx, wz, SEED)
                self.assertTrue(ground_here + 1 <= top <= ground_here + 3)
                self.assertEqual({block_at(wx, y, wz, SEED) in WALLS for y in range(ground_here + 1, top + 1)}, {True})
                self.assertEqual(block_at(wx, top + 1, wz, SEED), "air")
                self.assertIsNone(plant_stack(wx, wz, SEED))
            for corner in ((x - RUIN_HALF, z - RUIN_HALF), (x + RUIN_HALF, z + RUIN_HALF)):
                self.assertEqual(ruin_column(*corner, SEED)[1], terrain_height(*corner, SEED) + 3)
            inside = [(wx, wz) for wx, wz in square(ruin) if 0 < max(abs(wx - x), abs(wz - z)) < RUIN_HALF]
            self.assertTrue(all(ruin_column(wx, wz, SEED) is None for wx, wz in inside))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_worldgen.py`, replace:

```python
                     "diamond_ore", "granite", "andesite", "diorite", "ashstone", "mossy_cobblestone"):
```

with:

```python
                     "diamond_ore", "granite", "andesite", "diorite", "ashstone", "mossy_cobblestone",
                     "stone_bricks", "chest"):  # L5: the frontier's ruins
```

In `frontend/src/engine/worldgen.test.ts`, replace:

```ts
  regionOpenings, rocksInChunk, treeKind, treesInChunk, wildFood, WORLD_MAX_Y, WORLD_MIN_Y,
```

with:

```ts
  regionOpenings, regionRuin, rocksInChunk, ruinColumn, treeKind, treesInChunk, wildFood, WORLD_MAX_Y, WORLD_MIN_Y,
```

and replace:

```ts
  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
```

with:

```ts
  it('builds the frontier\'s ruins, their walls and their chests, inside columns exactly like blockAt', () => {
    // L5: every chunk a ruin's 7x7 square touches, for two ruins east of the legacy clearing and one west.
    const ruins: [number, number, number][] = []
    for (const rxs of [[3, 40], [-40, -3]]) {
      let found = 0
      for (let rx = rxs[0]; rx < rxs[1] && found < (rxs[0] > 0 ? 2 : 1); rx++) {
        for (let rz = -20; rz < 20 && found < (rxs[0] > 0 ? 2 : 1); rz++) {
          const ruin = regionRuin(rx, rz, WILD_SEED)
          if (ruin) { ruins.push(ruin); found++ }
        }
      }
    }
    expect(ruins).toHaveLength(3)
    for (const [x, z, ground] of ruins) {
      expect(blockAt(x, ground + 1, z, WILD_SEED)).toBe('chest')
      expect(ruinColumn(x, z, WILD_SEED)).toEqual(['chest', ground + 1])
      const chunks = new Set<string>()
      for (const dx of [-3, 3]) for (const dz of [-3, 3]) chunks.add(`${Math.floor((x + dx) / 16)},${Math.floor((z + dz) / 16)}`)
      for (const chunk of chunks) {
        const [cx, cz] = chunk.split(',').map(Number)
        expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
      }
    }
  })

  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
```

In `frontend/src/survival/overheadMap.test.ts`, replace:

```ts
import { biomeAt, blockAt, regionOpenings, rocksInChunk, SEA_LEVEL, terrainHeight } from '../engine/worldgen'
```

with:

```ts
import { biomeAt, blockAt, regionOpenings, regionRuin, rocksInChunk, SEA_LEVEL, terrainHeight } from '../engine/worldgen'
```

and replace:

```ts
    expect(kinds).toEqual(new Set(['above', 'below']))
```

with:

```ts
    expect(kinds).toEqual(new Set(['above', 'below']))
  })

  it('shows an old ruin\'s walls and chest, as they stand (L5)', () => {
    const ruins: [number, number, number][] = []
    for (let rx = 36; rx < 46 && ruins.length < 2; rx++) for (let rz = 40; rz < 46 && ruins.length < 2; rz++) {
      const ruin = regionRuin(rx, rz, SEED)
      if (ruin) ruins.push(ruin)
    }
    expect(ruins).toHaveLength(2)
    const seen = new Set<number>()
    for (const [rx, rz] of ruins) {
      for (let dx = -4; dx <= 4; dx++) for (let dz = -4; dz <= 4; dz++) {
        const top = naturalTop(rx + dx, rz + dz, SEED)
        expect({ x: rx + dx, z: rz + dz, id: top.id, y: top.y }).toEqual({ x: rx + dx, z: rz + dz, ...scanned(rx + dx, rz + dz) })
        seen.add(top.id)
      }
    }
    expect(seen.has(blockId('chest'))).toBe(true)
    expect(seen.has(blockId('stone_bricks'))).toBe(true)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen_ruins.py"`
Expected: ERROR: `ImportError: cannot import name 'RUIN_HALF' from 'backend.services.worldgen'`

Run: `cd frontend && npx vitest run src/engine/worldgen.test.ts src/survival/overheadMap.test.ts`
Expected: FAIL: `regionRuin is not a function` (or a missing export)

- [ ] **Step 3: Ruins in the Python port**

In `backend/services/worldgen.py`, replace:

```python
FEATURE_TOP = max(CANOPY_TOP, ROCK_TOP)  # the highest anything generated stands over a column's ground
```

with:

```python
FEATURE_TOP = max(CANOPY_TOP, ROCK_TOP)  # the highest anything generated stands over a column's ground
# L5, the frontier: a small ruin (stone-brick walls with mossy cobblestone, an old chest in the middle)
# stands in some 96x96 regions, placed by the seed and the region alone, like the cave entrances.
RUIN_REGION = 96  # blocks on a side; a region holds one ruin at most
RUIN_ODDS = 2  # one region in this many tries for one
RUIN_MARGIN = 12  # its middle lies at least this far inside its region, so it never leaves it
RUIN_HALF = 3  # its walls stand on the edge of a square this far from its middle each way (7x7)
RUIN_TOP = 3  # a wall column stands 0 (a gap) to this many blocks over its own ground; never above ROCK_TOP
RUIN_SLOPE = 2  # the ground under it may lie this much above or below its middle's
```

and replace:

```python
@lru_cache(maxsize=COLUMN_CACHE)
def rock_column(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
```

with:

```python
@lru_cache(maxsize=4096)
def region_ruin(rx: int, rz: int, seed: str = LEGACY_WORLD_SEED) -> tuple[int, int, int] | None:
    """The ruin of a 96x96 region, if it has one: (x, z, ground height) of its middle column, where
    its chest stands. One region in RUIN_ODDS tries a spot; the ruin stands there only when every
    column of its 7x7 square is dry land within RUIN_SLOPE of the middle's height, with no swamp pool,
    cave entrance, tree or rock on it. None near the legacy clearing."""
    x0, z0 = rx * RUIN_REGION, rz * RUIN_REGION
    if math.hypot(x0 + RUIN_REGION / 2, z0 + RUIN_REGION / 2) <= LEGACY_RADIUS + RUIN_REGION:
        return None
    roll = hash32(rx, 0, rz, seed, 92)
    if roll % RUIN_ODDS != 0:
        return None
    span = RUIN_REGION - 2 * RUIN_MARGIN
    cx, cz = x0 + RUIN_MARGIN + (roll >> 8) % span, z0 + RUIN_MARGIN + (roll >> 16) % span
    ground = terrain_height(cx, cz, seed)
    for x in range(cx - RUIN_HALF, cx + RUIN_HALF + 1):
        for z in range(cz - RUIN_HALF, cz + RUIN_HALF + 1):
            height = terrain_height(x, z, seed)
            if (height <= SEA_LEVEL or abs(height - ground) > RUIN_SLOPE or swamp_pool(x, z, seed)
                    or surface_opened(x, z, seed) or tree_base(x, z, seed) is not None
                    or rock_column(x, z, seed) is not None):
                return None
    return cx, cz, ground


def ruin_column(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
    """What of a ruin stands on a column and the y of its top: ("chest", ground + 1) on its middle
    column, ("wall", top) on a wall column of its 7x7 square that still stands 1 to 3 high on its own
    ground (the corners always 3, the middle of one side always a doorway), else None."""
    ruin = region_ruin(x // RUIN_REGION, z // RUIN_REGION, seed)
    if ruin is None:
        return None
    rx, rz, ground = ruin
    dx, dz = x - rx, z - rz
    if (dx, dz) == (0, 0):
        return "chest", ground + 1
    if max(abs(dx), abs(dz)) != RUIN_HALF:
        return None
    door = hash32(rx, 1, rz, seed, 92) % 4
    if (dx, dz) == ((RUIN_HALF, 0), (-RUIN_HALF, 0), (0, RUIN_HALF), (0, -RUIN_HALF))[door]:
        return None
    layers = RUIN_TOP if abs(dx) == abs(dz) else hash32(x, 4, z, seed, 93) % (RUIN_TOP + 1)
    return ("wall", terrain_height(x, z, seed) + layers) if layers else None


def ruin_block(x: int, y: int, z: int, seed: str, part: str) -> str:
    """The block of a ruin's cell: its chest, or a wall's stone bricks, one in three mossy cobblestone."""
    if part == "chest":
        return "chest"
    return "mossy_cobblestone" if hash32(x, y, z, seed, 94) % 3 == 0 else "stone_bricks"


@lru_cache(maxsize=COLUMN_CACHE)
def rock_column(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
```

and replace:

```python
    if math.hypot(x, z) <= HOME_RADIUS or surface_opened(x, z, seed) or rock_column(x, z, seed):
```

with:

```python
    if math.hypot(x, z) <= HOME_RADIUS or surface_opened(x, z, seed) or rock_column(x, z, seed) \
            or ruin_column(x, z, seed):  # L5: nothing grows in a ruin's walls or under its chest
```

and replace:

```python
    leaves, rock, plant."""
```

with:

```python
    leaves, ruin (L5), rock, plant."""
```

and replace:

```python
    height = terrain_height(x, z, seed)
    rock = rock_column(x, z, seed) if y > height else None
```

with:

```python
    height = terrain_height(x, z, seed)
    ruin = ruin_column(x, z, seed) if y > height else None
    if ruin is not None:
        return ruin_block(x, y, z, seed, ruin[0]) if y <= ruin[1] else None
    rock = rock_column(x, z, seed) if y > height else None
```

- [ ] **Step 4: Ruins in the TypeScript port, and on the minimap**

In `frontend/src/engine/worldgen.ts`, replace:

```ts
const OUTCROPS: Record<string, string> = { desert: 'sandstone', taiga: 'andesite', birch_forest: 'diorite', alpine: 'granite' }
```

with:

```ts
const OUTCROPS: Record<string, string> = { desert: 'sandstone', taiga: 'andesite', birch_forest: 'diorite', alpine: 'granite' }
// L5, the frontier: a small ruin (stone-brick walls with mossy cobblestone, an old chest in the middle)
// stands in some 96x96 regions (see backend/services/worldgen.py region_ruin).
const RUIN_REGION = 96
const RUIN_ODDS = 2
const RUIN_MARGIN = 12
const RUIN_HALF = 3
const RUIN_TOP = 3
const RUIN_SLOPE = 2
const RUIN_DOORS: [number, number][] = [[RUIN_HALF, 0], [-RUIN_HALF, 0], [0, RUIN_HALF], [0, -RUIN_HALF]]
```

and replace:

```ts
const rockCache = new Map<string, Rock[]>()
```

with:

```ts
const rockCache = new Map<string, Rock[]>()
const ruinCache = new Map<string, [number, number, number] | null>()
```

and replace:

```ts
/** Terrain, water, caves and ores, before trees and plants are added. `columnSpan`, when given (even
```

with:

```ts
/** L5: the ruin of a 96x96 region, if it has one: [x, z, ground height] of its middle column, where its
 * chest stands (see backend/services/worldgen.py region_ruin). */
export function regionRuin(rx: number, rz: number, seed = DEFAULT_WORLD_SEED): [number, number, number] | null {
  const key = `${seed}:${rx},${rz}`
  let ruin = ruinCache.get(key)
  if (ruin !== undefined) return ruin
  ruin = findRuin(rx, rz, seed)
  ruinCache.set(key, ruin)
  if (ruinCache.size > 4096) ruinCache.delete(ruinCache.keys().next().value!)
  return ruin
}

function findRuin(rx: number, rz: number, seed: string): [number, number, number] | null {
  const x0 = rx * RUIN_REGION, z0 = rz * RUIN_REGION
  if (Math.hypot(x0 + RUIN_REGION / 2, z0 + RUIN_REGION / 2) <= LEGACY_RADIUS + RUIN_REGION) return null
  const roll = hash32(rx, 0, rz, seed, 92)
  if (roll % RUIN_ODDS !== 0) return null
  const span = RUIN_REGION - 2 * RUIN_MARGIN
  const cx = x0 + RUIN_MARGIN + (roll >>> 8) % span, cz = z0 + RUIN_MARGIN + (roll >>> 16) % span
  const ground = terrainHeight(cx, cz, seed)
  for (let x = cx - RUIN_HALF; x <= cx + RUIN_HALF; x++) for (let z = cz - RUIN_HALF; z <= cz + RUIN_HALF; z++) {
    const height = terrainHeight(x, z, seed)
    if (height <= SEA_LEVEL || Math.abs(height - ground) > RUIN_SLOPE || swampPool(x, z, seed)
      || surfaceOpened(x, z, seed) || treeBase(x, z, seed) !== null || rockColumn(x, z, seed) !== null) return null
  }
  return [cx, cz, ground]
}

/** L5: what of a ruin stands on a column and the y of its top: ['chest', ground + 1] on its middle
 * column, ['wall', top] on a wall column of its 7x7 square that still stands, else null. */
export function ruinColumn(x: number, z: number, seed = DEFAULT_WORLD_SEED): [string, number] | null {
  const ruin = regionRuin(Math.floor(x / RUIN_REGION), Math.floor(z / RUIN_REGION), seed)
  if (ruin === null) return null
  const [rx, rz, ground] = ruin
  const dx = x - rx, dz = z - rz
  if (dx === 0 && dz === 0) return ['chest', ground + 1]
  if (Math.max(Math.abs(dx), Math.abs(dz)) !== RUIN_HALF) return null
  const [doorX, doorZ] = RUIN_DOORS[hash32(rx, 1, rz, seed, 92) % 4]
  if (dx === doorX && dz === doorZ) return null
  const layers = Math.abs(dx) === Math.abs(dz) ? RUIN_TOP : hash32(x, 4, z, seed, 93) % (RUIN_TOP + 1)
  return layers ? ['wall', terrainHeight(x, z, seed) + layers] : null
}

/** L5: the block of a ruin's cell: its chest, or a wall's stone bricks, one in three mossy cobblestone. */
function ruinBlock(x: number, y: number, z: number, seed: string, part: string): string {
  if (part === 'chest') return 'chest'
  return hash32(x, y, z, seed, 94) % 3 === 0 ? 'mossy_cobblestone' : 'stone_bricks'
}

/** Terrain, water, caves and ores, before trees and plants are added. `columnSpan`, when given (even
```

and replace:

```ts
  if (Math.hypot(x, z) <= HOME_RADIUS || surfaceOpened(x, z, seed) || rockColumn(x, z, seed)) return null
```

with:

```ts
  if (Math.hypot(x, z) <= HOME_RADIUS || surfaceOpened(x, z, seed) || rockColumn(x, z, seed) || ruinColumn(x, z, seed)) {
    return null  // L5: nothing grows in a ruin's walls or under its chest
  }
```

and replace:

```ts
/** Blocks that grow or stand on the terrain, or on a cave floor. Precedence: home, trunk, leaves, rock, plant. */
```

with:

```ts
/** Blocks that grow or stand on the terrain, or on a cave floor. Precedence: home, trunk, leaves, ruin (L5), rock, plant. */
```

and replace:

```ts
  const height = terrainHeight(x, z, seed)
  const rock = y > height ? rockColumn(x, z, seed) : null
```

with:

```ts
  const height = terrainHeight(x, z, seed)
  const ruin = y > height ? ruinColumn(x, z, seed) : null
  if (ruin) return y <= ruin[1] ? ruinBlock(x, y, z, seed, ruin[0]) : null
  const rock = y > height ? rockColumn(x, z, seed) : null
```

and replace:

```ts
  // Later stamps win, so stamp in rising precedence: plants, rocks, leaves, trunks, home.
```

with:

```ts
  // Later stamps win, so stamp in rising precedence: plants, rocks, ruins (L5), leaves, trunks, home.
```

and replace:

```ts
    for (let y = terrainHeight(x0 + lx, z0 + lz, seed) + 1; y <= rock[1]; y++) stamp(x0 + lx, y, z0 + lz, rock[0])
```

with:

```ts
    for (let y = terrainHeight(x0 + lx, z0 + lz, seed) + 1; y <= rock[1]; y++) stamp(x0 + lx, y, z0 + lz, rock[0])
  }
  for (let lz = 0; lz < CHUNK_SIZE; lz++) for (let lx = 0; lx < CHUNK_SIZE; lx++) {
    const ruin = ruinColumn(x0 + lx, z0 + lz, seed)
    if (!ruin) continue
    for (let y = terrainHeight(x0 + lx, z0 + lz, seed) + 1; y <= ruin[1]; y++) {
      stamp(x0 + lx, y, z0 + lz, ruinBlock(x0 + lx, y, z0 + lz, seed, ruin[0]))
    }
```

In `frontend/src/survival/overheadMap.ts`, replace:

```ts
  blockAt, canopyTop, CHUNK_SIZE, LEGACY_RADIUS, plantStack, rockColumn, SEA_LEVEL, surfaceMaterial, surfaceOpened,
  swampPool, terrainBlock, terrainHeight, WORLD_MIN_Y,
```

with:

```ts
  blockAt, canopyTop, CHUNK_SIZE, LEGACY_RADIUS, plantStack, rockColumn, ruinColumn, SEA_LEVEL, surfaceMaterial,
  surfaceOpened, swampPool, terrainBlock, terrainHeight, WORLD_MIN_Y,
```

and replace:

```ts
 * lake, a swamp pool, the bottom of a cave entrance, a boulder or outcrop, a pumpkin or melon, or the
 * ground. Small plants (grass, flowers, bushes, cacti, cane) are too small to see. */
```

with:

```ts
 * lake, a swamp pool, the bottom of a cave entrance, a boulder or outcrop, (L5) a ruin's wall or chest,
 * a pumpkin or melon, or the ground. Small plants (grass, flowers, bushes, cacti, cane) are too small to see. */
```

and replace:

```ts
  if (leaves !== null && leaves[1] > Math.max(height, SEA_LEVEL) && leaves[1] >= (rock?.[1] ?? -Infinity)) {
```

with:

```ts
  const ruin = ruinColumn(x, z, seed)  // L5: an old ruin's wall or chest
  const standing = Math.max(rock?.[1] ?? -Infinity, ruin?.[1] ?? -Infinity)
  if (leaves !== null && leaves[1] > Math.max(height, SEA_LEVEL) && leaves[1] >= standing) {
```

and replace:

```ts
  if (rock) return { id: blockId(rock[0]), y: rock[1], depth: 0 }
```

with:

```ts
  if (rock) return { id: blockId(rock[0]), y: rock[1], depth: 0 }
  if (ruin) return { id: blockId(blockAt(x, ruin[1], z, seed)), y: ruin[1], depth: 0 }
```

- [ ] **Step 5: The fixture samples ruins, and is regenerated**

In `backend/scripts/worldgen_fixture.py`, replace:

```python
    LEGACY_WORLD_SEED, SEA_LEVEL, biome_at, block_at, cave_plant, plant_at, plant_stack, region_openings,
    rocks_in_chunk, swamp_pool, terrain_height, tree_kind, trees_in_chunk,
```

with:

```python
    LEGACY_WORLD_SEED, RUIN_HALF, SEA_LEVEL, biome_at, block_at, cave_plant, plant_at, plant_stack, region_openings,
    region_ruin, rocks_in_chunk, swamp_pool, terrain_height, tree_kind, trees_in_chunk,
```

and replace:

```python
def sample_cells() -> list[tuple[str, int, int, int]]:
```

with:

```python
def _ruins(seed: str, count: int, rxs: range = range(3, 40)) -> list[tuple[int, int, int]]:
    """L5: the middle columns (x, z, ground) of `count` ruins."""
    found = []
    for rx in rxs:
        for rz in range(-20, 20):
            ruin = region_ruin(rx, rz, seed)
            if ruin is not None:
                found.append(ruin)
                if len(found) == count:
                    return found
    return found


def sample_cells() -> list[tuple[str, int, int, int]]:
```

and replace:

```python
                      for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 5)}
```

with:

```python
                      for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 5)}
        for rx, rz, ground in _ruins(seed, 2) + _ruins(seed, 2, range(-40, -3)):
            reach = RUIN_HALF + 1
            cells |= {(seed, rx + dx, ground + dy, rz + dz)
                      for dx in range(-reach, reach + 1) for dz in range(-reach, reach + 1) for dy in range(-1, 5)}
```

Run: `python3 -m backend.scripts.worldgen_fixture`
Expected: `Wrote 43478 cells to …/shared/worldgen-fixture.json` (39590 before: the ruins' cells are new, and `chest` and `stone_bricks` join the materials).

- [ ] **Step 6: Run the tests and both parity suites**

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen*.py"`
Expected: `OK` (4 new in `test_worldgen_ruins.py`; `FixtureTests` pass against the regenerated fixture)

Run: `cd frontend && npx vitest run src/engine/worldgen.test.ts src/survival/overheadMap.test.ts`
Expected: pass (2 new: ruins inside columns exactly like `blockAt`, and the map's view of a ruin)

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1150 tests` … `OK` (4 new).

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  310 passed (310)` (2 new), the build succeeds, eslint prints nothing.

- [ ] **Step 7: Commit**

```bash
git add backend/services/worldgen.py frontend/src/engine/worldgen.ts frontend/src/survival/overheadMap.ts backend/scripts/worldgen_fixture.py shared/worldgen-fixture.json backend/tests/test_worldgen_ruins.py backend/tests/test_worldgen.py frontend/src/engine/worldgen.test.ts frontend/src/survival/overheadMap.test.ts
git commit -m "feat: frontier ruins - stone-brick walls, mossy cobblestone and an old chest, placed by seed and region in both worldgen ports" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Ruins in the brain: seeing them, the old chest and loot_ruin

**Files:**
- Create: `backend/survival/ruins.py`
- Modify: `backend/survival/steps.py` (`OBSERVERS`), `backend/survival/brain.py` (imports `ruins`; `observe_step` calls the `OBSERVERS` before curiosity looks over the step's events)
- Test: `backend/tests/test_survival_ruins.py`

**Interfaces:**
- Consumes: Task 5's `worldgen.region_ruin`, `RUIN_REGION`; Task 1's `rings.ring_at`, `ring_name`, `ready_ring`, `DEEPEST`; `housework.chest_key` and its `take` step; `carrying.room_for`; `storage.STORE_FROM`; `foraging.whole_walk`, `STAND`; `goals.URGES`; `memory.remember`, `update_place`; `nature.roll`.
- Produces:
  - `steps.OBSERVERS: list` of `(state, step, context, at)`, called by `brain.observe_step` after each step that finished well.
  - `ruins.RUIN = "ruin"`, `RUIN_SIGHT = 24.0`, `LOOT_RANGE = 64.0`, `URGE_REACH = 32.0`, `OPEN_SECONDS = 0.6`, `LOOT_BATCHES = 3`, `LOOT_ROOM = STORE_FROM - 1` (12), `RAREST_FIRST`, `LOOT` (by ring); `ruin_chest(seed, rx, rz)`, `ruins_near(seed, x, z, reach) -> list[Cell]` (nearest first), `is_ruin_chest(seed, cell)`, `ruin_loot(seed, cell, ring) -> dict`, `loot_words(loot)`, `notice_ruins`, `note_opened`, `opened(s, chest)`, `takeable(s, chest)` (the rarest first, below `LOOT_ROOM` stacks), `ruin_targets(s)`, `chest_in_sight(s)`.
  - The step `open_chest` (`{"kind": "open_chest", "target": [x, y, z]}`, status "opening"); the purpose `loot_ruin`; `goals.URGES["loot_ruin"]`. Task 8's frontier goal names `loot_ruin` and reads `RUIN` places' `opened`.

- [ ] **Step 1: Write the failing tests**

The tests use the real generated world of seed `123456789123456789`, where region (40, 2) holds a ruin whose chest stands at (3920, 9, 218).

Create `backend/tests/test_survival_ruins.py`:

```python
import sqlite3
import unittest

from backend.services.worldgen import block_at
from backend.survival import brain  # noqa: F401  (registers loot_ruin, the open_chest step and the observers)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.brain import observe_step
from backend.survival.goals import meets_need
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, places
from backend.survival.purposes import PURPOSES
from backend.survival.ruins import LOOT, RUIN, ruin_loot, ruins_near
from backend.survival.situation import Situation
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_pickers import DAY

SEED = "123456789123456789"
CHEST = (3920, 9, 218)  # the chest of region (40, 2)'s ruin, on ground 8
GEARED = {"stone_sword": 1, "leather_cap": 1, "leather_tunic": 1, "bread": 2}


class Pet:
    """Mimo in the real generated world of SEED, with its memory, `offset` blocks east of the ruin's chest."""

    def __init__(self, offset=(2, 0), center=None, inventory=None):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = Grid(lambda x, y, z: block_at(x, y, z, SEED))
        x, z = CHEST[0] + offset[0], CHEST[2] + offset[1]
        self.state = {"name": "Pip", "world_seed": SEED, "position": {"x": float(x), "y": 9.0, "z": float(z)},
                      "inventory": dict(inventory or {}), "vitals": dict(START_VITALS), "traits": {},
                      "last_tick_at": 0.0, "frontier": {"center": list(center or (CHEST[0], CHEST[2]))}}
        ensure_actions(self.state)
        self.context = ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[],
                                     db=self.db)

    def situation(self):
        return Situation(self.state, self.grid, DAY, 0.0, self.db)

    def walked(self):
        observe_step(self.state, {"kind": "walk", "path": [], "target": dict(self.state["position"])}, self.context, 1.0)

    def run(self, spec):
        step = start_step(spec, self.state, self.grid, 1.0)
        return finish_step(step, self.state, self.grid, 2.0)


class LootTableTests(unittest.TestCase):
    def test_the_same_chest_in_the_same_ring_always_holds_the_same(self):
        self.assertEqual(ruin_loot(SEED, CHEST, 2), ruin_loot(SEED, CHEST, 2))
        self.assertNotEqual(ruin_loot(SEED, CHEST, 1), ruin_loot(SEED, CHEST, 3))

    def test_nearer_ruins_hold_food_arrows_and_iron_farther_ones_gold_amber_and_diamonds(self):
        chests = ruins_near(SEED, 4000, 0, 900)
        near = [ruin_loot(SEED, chest, 0) for chest in chests] + [ruin_loot(SEED, chest, 1) for chest in chests]
        far = [ruin_loot(SEED, chest, 3) for chest in chests] + [ruin_loot(SEED, chest, 4) for chest in chests]
        self.assertGreater(len(chests), 10)
        self.assertEqual(set().union(*near), {"bread", "arrow", "iron_ingot", "torch", "coal"})
        self.assertTrue({"gold_ingot", "amber", "diamond"} <= set().union(*far))
        self.assertFalse({"gold_ingot", "gold_nugget", "amber", "diamond"} & set().union(*near))
        self.assertEqual(sorted(LOOT), [0, 1, 2, 3, 4])


class RuinTests(unittest.TestCase):
    def test_a_ruin_in_sight_after_a_walk_is_remembered_once_and_notable(self):
        pet = Pet(offset=(20, 0), center=(CHEST[0] - 150, CHEST[2]))
        pet.walked()
        pet.walked()
        self.assertEqual([(place["kind"], place["note"]) for place in places(pet.db, (RUIN,))], [(RUIN, "far wilds")])
        self.assertEqual([text for _, kind, text in pet.context.events if kind == "found"],
                         ["Pip found an old ruin in the far wilds."])

    def test_opening_its_old_chest_rolls_the_loot_by_its_ring_once(self):
        pet = Pet(center=(CHEST[0] - 150, CHEST[2]))
        with self.assertRaises(StepFailed):
            Pet(offset=(10, 0)).run({"kind": "open_chest", "target": list(CHEST)})  # out of reach
        kind, text = pet.run({"kind": "open_chest", "target": list(CHEST)})
        self.assertEqual(pet.state["chests"]["3920,9,218"], ruin_loot(SEED, CHEST, 2))
        self.assertEqual(kind, "loot")
        self.assertTrue(text.startswith("Pip opened an old chest in a ruin: "))
        with self.assertRaises(StepFailed):
            pet.run({"kind": "open_chest", "target": list(CHEST)})  # open already
        with self.assertRaises(StepFailed):
            pet.run({"kind": "open_chest", "target": [CHEST[0] + 1, CHEST[1], CHEST[2]]})  # no chest there

    def test_loot_ruin_opens_the_chest_then_takes_what_fits(self):
        pet = Pet(offset=(12, 0))
        pet.walked()
        loot = PURPOSES["loot_ruin"]
        s = pet.situation()
        self.assertTrue(loot.valid(s))
        self.assertTrue(meets_need(s, "loot_ruin", loot.score(s)))  # an unopened chest in sight is an urge
        self.assertIn("its chest never opened", loot.facts(s))
        steps = loot.plan(s, pet.context)
        self.assertEqual([step["kind"] for step in steps], ["walk", "open_chest"])
        pet.state["position"] = {"x": float(CHEST[0] + 2), "y": 9.0, "z": float(CHEST[2])}
        pet.run(steps[-1])
        takes = loot.plan(pet.situation(), pet.context)
        self.assertEqual({step["item"]: step["amount"] for step in takes}, ruin_loot(SEED, CHEST, 0))
        for step in takes:
            pet.run(step)
        self.assertFalse(loot.valid(pet.situation()))  # nothing left in it

    def test_with_its_arms_nearly_full_it_takes_the_rarest_first_and_leaves_the_rest(self):
        blocks = ("dirt", "gravel", "sand", "clay", "moss", "basalt", "limestone", "sandstone", "cobblestone", "planks")
        pet = Pet(offset=(2, 0), inventory={block: 1 for block in blocks})  # 10 stacks: room for 2 below LOOT_ROOM
        pet.walked()
        pet.run({"kind": "open_chest", "target": list(CHEST)})
        takes = PURPOSES["loot_ruin"].plan(pet.situation(), pet.context)
        self.assertEqual({step["item"]: step["amount"] for step in takes}, {"iron_ingot": 2, "bread": 3})
        for step in takes:
            pet.run(step)
        self.assertEqual(pet.state["chests"][f"{CHEST[0]},{CHEST[1]},{CHEST[2]}"], {"arrow": 6, "torch": 3})
        self.assertFalse(PURPOSES["loot_ruin"].valid(pet.situation()))  # no room: the rest waits in the chest

    def test_a_pet_goes_to_a_ruin_only_in_a_ring_it_is_ready_for(self):
        far = Pet(offset=(12, 0), center=(CHEST[0] - 150, CHEST[2]))
        far.walked()
        self.assertFalse(PURPOSES["loot_ruin"].valid(far.situation()))
        far.state["inventory"] = dict(GEARED)
        self.assertTrue(PURPOSES["loot_ruin"].valid(far.situation()))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_ruins.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.ruins'`

- [ ] **Step 3: Observers of finished steps**

In `backend/survival/steps.py`, replace:

```python
MINED: list = []
```

with:

```python
MINED: list = []
# L5: functions (state, step, context, at) the brain calls after each step that finished well, before
# curiosity looks over the step's events (brain.observe_step; backend.survival.ruins: ruins seen, an old
# chest opened). One that crashes is logged once and skipped.
OBSERVERS: list = []
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import loot  # noqa: F401  (L5: better drops and mining luck farther out)
```

with:

```python
from backend.survival import loot, ruins  # noqa: F401  (L5: better drops and mining luck, ruins and their loot)
```

and replace:

```python
from backend.survival.steps import as_cell, label
```

with:

```python
from backend.survival.steps import OBSERVERS, as_cell, label
```

and replace:

```python
        announce_find(state, step, context, at, *finds[0])  # one a step: the rest are remembered quietly
```

with:

```python
        announce_find(state, step, context, at, *finds[0])  # one a step: the rest are remembered quietly
    for observer in OBSERVERS:  # L5: ruins seen, an old chest opened (backend.survival.ruins)
        try:
            observer(state, step, context, at)
        except Exception as error:
            log_once(logger, "step observer", error)
```

- [ ] **Step 4: Ruins, their old chests and loot_ruin**

Create `backend/survival/ruins.py`:

```python
"""Frontier ruins in the brain (L5): seeing them, opening their old chests and taking the loot.

Worldgen stands a small ruin in some regions, with an old chest in its middle
(backend.services.worldgen.region_ruin). Here Mimo meets them:
- Seeing one: after every walk or swim (`notice_ruins`, one of steps.OBSERVERS, which the brain
  calls), a ruin whose chest is within RUIN_SIGHT blocks and that Mimo does not remember yet is
  remembered as a "ruin" place (at its chest) and is a notable "found" event ("Pip found an old ruin
  in the far wilds."), a new place for curiosity and a discovery that asks for a new choice.
- The open_chest step (0.6 s, the chest within reach): the first time Mimo opens a ruin's chest the
  server rolls what is inside by the ruin's danger ring (`ruin_loot`, from the world seed, the chest's
  cell and the ring, so the same chest in the same ring always holds the same) and puts it in the
  chest (state["chests"], where every chest's contents live). Nearer ruins hold food, arrows and iron;
  farther ones gold, amber and diamonds. A notable "loot" event names what was inside. A chest once
  opened stays open; the place is noted opened.
- The loot_ruin purpose ("loot an old ruin"): by day, not late, a remembered ruin within LOOT_RANGE
  whose chest still stands and holds something (or was never opened), in a ring Mimo is ready for
  (rings.ready_ring: home ground and the near wilds always), the nearest first. It walks up, opens the
  chest, then takes what it has room for below LOOT_ROOM stacks, the rarest first (housework's take
  step); the rest waits in the chest until Mimo has room again. A first version took all that fit in
  its 16 stacks: four new stacks early in a life pushed a pet near home past the point where putting
  things away and dropping loose blocks are worth doing, and it swung between digging stone, dropping
  and putting away (94 changes of purpose in its busiest hour, over the sims' 90; seed 5, the fake
  Jev, slow mode). Work band: 58 plus a tenth of bravery. A chest in sight (within URGE_REACH) is an
  urge (goals.URGES): Mimo opens it though its goal is something else. The frontier goal
  (backend.survival.frontier) names it too.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.worldgen import RUIN_REGION, region_ruin
from backend.survival import nature
from backend.survival.carrying import room_for
from backend.survival.foraging import STAND, whole_walk
from backend.survival.goals import URGES
from backend.survival.grid import Cell, Grid
from backend.survival.housework import chest_key
from backend.survival.memory import remember, update_place
from backend.survival.purposes import Purpose, late_day, late_penalty, register
from backend.survival.rings import DEEPEST, ready_ring, ring_at, ring_name
from backend.survival.situation import Situation
from backend.survival.storage import STORE_FROM
from backend.survival.steps import (
    OBSERVERS, REACH, StepFailed, StepKind, as_cell, as_point, in_reach, label, register_step, seed_of,
)
from backend.survival.triggers import mark_trigger

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

RUIN = "ruin"  # the memory place kind, at the ruin's chest
RUIN_SIGHT = 24.0  # a ruin's chest this close after a walk is seen
LOOT_RANGE = 64.0  # loot_ruin goes to remembered ruins this close
URGE_REACH = 32.0  # an unopened chest this close is an urge
OPEN_SECONDS = 0.6
LOOT_BATCHES = 3
LOOT_ROOM = STORE_FROM - 1  # stacks Mimo fills with loot at most: below where putting things away is worth a trip
# The order loot is taken in when there is not room for all of it: the rarest first.
RAREST_FIRST = ("diamond", "amber", "gold_ingot", "gold_nugget", "iron_ingot", "bread", "coal", "arrow", "torch")
# What an old chest holds by the ring its ruin stands in: (item, least, most, chance).
LOOT = {
    0: (("bread", 1, 3, 1.0), ("arrow", 4, 8, 0.8), ("iron_ingot", 1, 2, 0.7), ("torch", 2, 4, 0.5)),
    1: (("bread", 2, 4, 1.0), ("arrow", 4, 8, 0.9), ("iron_ingot", 1, 3, 0.8), ("coal", 2, 4, 0.6)),
    2: (("bread", 2, 4, 0.8), ("arrow", 6, 12, 1.0), ("iron_ingot", 2, 4, 0.8), ("gold_nugget", 2, 6, 0.8),
        ("amber", 1, 2, 0.6)),
    3: (("arrow", 8, 16, 1.0), ("gold_ingot", 1, 3, 0.8), ("gold_nugget", 3, 8, 0.8), ("amber", 1, 3, 0.8),
        ("diamond", 1, 1, 0.5)),
    4: (("arrow", 8, 16, 1.0), ("gold_ingot", 2, 4, 1.0), ("amber", 2, 4, 1.0), ("diamond", 1, 3, 0.8)),
}
LOOT_ROLL, COUNT_ROLL = 130, 140  # nature.roll channels (and the next few after each)


# Where ruins are -------------------------------------------------------------------------------

def ruin_chest(seed: str, rx: int, rz: int) -> Cell | None:
    """The cell of the chest of region (rx, rz)'s ruin, or None."""
    ruin = region_ruin(rx, rz, seed)
    return None if ruin is None else (ruin[0], ruin[2] + 1, ruin[1])


def ruins_near(seed: str, x: float, z: float, reach: float) -> list[Cell]:
    """The chests of the ruins within `reach` blocks (across) of (x, z), nearest first."""
    found = []
    for rx in range(math.floor((x - reach) / RUIN_REGION), math.floor((x + reach) / RUIN_REGION) + 1):
        for rz in range(math.floor((z - reach) / RUIN_REGION), math.floor((z + reach) / RUIN_REGION) + 1):
            chest = ruin_chest(seed, rx, rz)
            if chest is not None and math.hypot(chest[0] - x, chest[2] - z) <= reach:
                found.append(chest)
    return sorted(found, key=lambda cell: (math.hypot(cell[0] - x, cell[2] - z), cell))


def is_ruin_chest(seed: str, cell: Cell) -> bool:
    return ruin_chest(seed, cell[0] // RUIN_REGION, cell[2] // RUIN_REGION) == tuple(cell)


def ruin_loot(seed: str, cell: Cell, ring: int) -> dict[str, int]:
    """What the old chest at `cell` holds when first opened in `ring` (see the module docstring)."""
    level = max(0, min(DEEPEST, ring))
    found = {}
    for index, (item, least, most, chance) in enumerate(LOOT[level]):
        if nature.roll(seed, cell, LOOT_ROLL + index, level) < chance:
            found[item] = least + int(nature.roll(seed, cell, COUNT_ROLL + index, level) * (most - least + 1))
    return found


def loot_words(loot: dict[str, int]) -> str:
    parts = [f"{count} {label(item)}" for item, count in sorted(loot.items(), key=lambda entry: (-entry[1], entry[0]))]
    if not parts:
        return "nothing at all"
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


# Seeing ruins ----------------------------------------------------------------------------------

def notice_ruins(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After a walk or swim: remember a ruin whose chest Mimo can see now (see the module docstring)."""
    if step["kind"] not in ("walk", "swim") or context.db is None:
        return
    position = state["position"]
    for chest in ruins_near(seed_of(state), position["x"], position["z"], RUIN_SIGHT):
        if context.grid.material(*chest) != "chest":
            continue
        ring = min(DEEPEST, ring_at(state, chest[0], chest[2]))
        if remember(context.db, RUIN, chest, at, ring_name(ring).lower()):
            context.events.append((at, "found", f"{state['name']} found an old ruin in the {ring_name(ring).lower()}."))
            mark_trigger(state, "discovery", at)


def note_opened(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After an open_chest step: the ruin's place is noted opened (steps.OBSERVERS)."""
    if step["kind"] == "open_chest" and context.db is not None:
        update_place(context.db, RUIN, as_cell(step["target"]), {"opened": at})


# The open_chest step ---------------------------------------------------------------------------

def closed_ruin_chest(spec: dict, state: dict, grid: Grid) -> Cell:
    target = as_cell(spec["target"])
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    if grid.material(*target) != "chest" or not is_ruin_chest(seed_of(state), target):
        raise StepFailed("there is no old chest there", "gone")
    if chest_key(target) in state.get("chests", {}):
        raise StepFailed("it is open already", "blocked")
    return target


def start_open(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = closed_ruin_chest(spec, state, grid)
    return {"kind": "open_chest", "started_at": at, "ends_at": round(at + OPEN_SECONDS / scale, 3),
            "target": as_point(target)}


def finish_open(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    target = closed_ruin_chest(step, state, grid)
    ring = min(DEEPEST, ring_at(state, target[0], target[2]))
    loot = ruin_loot(seed_of(state), target, ring)
    state.setdefault("chests", {})[chest_key(target)] = dict(loot)
    state["last_thought"] = "Treasure!" if loot else "Empty... someone got here first."
    return "loot", f"{state['name']} opened an old chest in a ruin: {loot_words(loot)}."


register_step(StepKind("open_chest", start_open, finish_open, "opening", cell_field="target"))


# loot_ruin -------------------------------------------------------------------------------------

def opened(s: Situation, chest: Cell) -> bool:
    return chest_key(chest) in s.state.get("chests", {})


def takeable(s: Situation, chest: Cell) -> dict[str, int]:
    """What Mimo takes out of an opened chest now: the rarest first, as much as it has room for below
    LOOT_ROOM stacks, all of it together."""
    inside = s.state.get("chests", {}).get(chest_key(chest), {})
    rank = {item: index for index, item in enumerate(RAREST_FIRST)}
    carried, found = dict(s.inventory), {}
    for item in sorted(inside, key=lambda item: (rank.get(item, len(rank)), item)):
        amount = min(inside[item], room_for(carried, item, LOOT_ROOM))
        if amount > 0:
            found[item] = amount
            carried[item] = carried.get(item, 0) + amount
    return found


def worth_a_visit(s: Situation, chest: Cell) -> bool:
    """The chest still stands, and was never opened or holds something Mimo can carry."""
    return s.grid.material(*chest) == "chest" and (not opened(s, chest) or bool(takeable(s, chest)))


def ruin_targets(s: Situation) -> list[Cell]:
    """Remembered ruins within LOOT_RANGE worth a visit, in a ring Mimo is ready for, nearest first."""
    def look() -> list[Cell]:
        ready = ready_ring(s)
        found = [(place["x"], place["y"], place["z"]) for place in s.places if place["kind"] == RUIN]
        found = [chest for chest in found if s.distance(chest) <= LOOT_RANGE
                 and ring_at(s.state, chest[0], chest[2]) <= ready and worth_a_visit(s, chest)]
        return sorted(found, key=lambda chest: (s.distance(chest), chest))
    return s.sensed("ruin targets", look)


def loot_valid(s: Situation) -> bool:
    return not s.night and not late_day(s) and bool(ruin_targets(s))


def loot_facts(s: Situation) -> str:
    chest = ruin_targets(s)[0]
    ring = ring_name(ring_at(s.state, chest[0], chest[2])).lower()
    inside = "its chest never opened" if not opened(s, chest) else \
        f"its chest holds {loot_words(s.state['chests'][chest_key(chest)])}"
    return f"an old ruin {round(s.distance(chest))} blocks away in the {ring}, {inside}"


def plan_loot(s: Situation, context: ActionContext) -> list[dict]:
    """Walk up to the nearest ruin worth a visit, open its chest, then take what fits."""
    targets = ruin_targets(s)
    if not targets or s.brain["batches"] >= LOOT_BATCHES:
        return []
    chest = targets[0]
    steps = [whole_walk(chest, STAND)] if s.distance(chest) > REACH else []
    if not opened(s, chest):
        return steps + [{"kind": "open_chest", "target": list(chest)}]
    takes = [{"kind": "take", "target": list(chest), "item": item, "amount": count}
             for item, count in takeable(s, chest).items()]
    return steps + takes if takes else []


def chest_in_sight(s: Situation) -> bool:
    """An unopened ruin chest within URGE_REACH: Mimo wants to open it, whatever its goal."""
    return any(not opened(s, chest) and s.distance(chest) <= URGE_REACH for chest in ruin_targets(s))


register(Purpose(
    "loot_ruin", "loot an old ruin",
    "Walk to an old ruin Mimo found, open its chest and take what it holds (food, arrows and iron near home; "
    "gold, amber and diamonds farther out).",
    valid=loot_valid, facts=loot_facts,
    score=lambda s: 58.0 + s.trait("bravery") / 10 - late_penalty(s), plan=plan_loot,
    thoughts=("An old ruin! I wonder what's in that chest.", "Somebody left something here long ago.")))

URGES["loot_ruin"] = chest_in_sight
OBSERVERS.extend((notice_ruins, note_opened))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_ruins.py"`
Expected: `Ran 7 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1157 tests` … `OK` (7 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `OK` and `OK` (a pet near home may now see a ruin and loot its chest: food, arrows and iron).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/ruins.py backend/survival/steps.py backend/survival/brain.py backend/tests/test_survival_ruins.py
git commit -m "feat: Mimo sees old ruins, opens their chests (the loot rolled by the ruin's ring the first time) and takes what fits" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Loot put to use: the warding lantern and amber-studded armor

**Files:**
- Create: `backend/survival/frontier_gear.py`
- Modify: `shared/blocks.json` (the `warding_lantern` block and tile, last), `backend/services/crafting.py` (the recipes), `backend/survival/toolmaking.py` (`MORE_ORDERS`), `backend/survival/creatures/acts.py` (`BARRIERS`, `barred`, in wandering), `backend/survival/creatures/hostiles.py` (`barred` in chasing), `backend/survival/carrying.py` (a comment), `backend/survival/brain.py` (imports `frontier_gear`)
- Test: `backend/tests/test_survival_frontier_gear.py` (create), `backend/tests/test_blocks_bigger_world.py`, `backend/tests/test_survival_gear.py`, `frontend/src/engine/blocks.test.ts` (modify)

**Interfaces:**
- Consumes: Task 4's `crafting` L5 block and `carrying.TREASURES`; Task 6's `steps.OBSERVERS`; `light.BLOCK_LIGHT`, `harm.ARMOR`, `harm.SLOTS`, `toolmaking.STATIONS`, `structures.STANDS_IN`, `storage.KEEP`; `lighting.home_blueprint`; `foraging.reach_steps`; `goals.URGES`; the test helpers `test_survival_darkness.land`, `pet`, `scene` and `test_survival_lighting.CORNERS`, `DAY`.
- Produces:
  - The block `warding_lantern` and the recipes `warding_lantern`, `amber_cap`, `amber_tunic`.
  - `toolmaking.MORE_ORDERS: list` of `(inventory) -> list[tuple[str, ...]]`, after craft_tools' own orders.
  - `acts.BARRIERS: list` of `(scene, kind, cell, step) -> bool`; `acts.barred(scene, creature, cell, step) -> bool`.
  - `frontier_gear.WARD = "warding_lantern"`, `WARD_REACH = 6.0`, `WARD_LIGHT = 15`, `WARD_DUST = 4`, `WARDS_WANTED = 2`, `AMBER_PIECES`, `AMBER_CUTS`; `note_wards(state, step, context, at)` (keeps `state["wards"]`), `warded`, `frontier_orders(inventory)`, `wards_at_home(s)`, `ward_corners(s)`; the purpose `ward_home`. Task 1's readiness names amber armor (60 %) for the deep frontier; the viewer draws amber armor (Task 10).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_frontier_gear.py`:

```python
import math
import sqlite3
import unittest

from backend.services.crafting import RECIPES, craft
from backend.survival import brain  # noqa: F401  (registers the warding lantern, amber armor and ward_home)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.carrying import valuable
from backend.survival.creatures.harm import armor_cut
from backend.survival.creatures.hostiles import chase
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.moves import where
from backend.survival.frontier_gear import WARD_REACH, frontier_orders, note_wards
from backend.survival.goals import meets_need
from backend.survival.grid import Grid
from backend.survival.light import Lights
from backend.survival.lighting import dark_corners
from backend.survival.memory import create_memory_tables, finish_structure, set_home
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.storage import KEEP
from backend.survival.structures import start
from backend.survival.toolmaking import tool_orders
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_darkness import land, pet, scene
from backend.tests.test_survival_lighting import CORNERS, DAY


def chased(wards):
    """Where a gloomling 9 blocks east of Mimo stands after chasing it for a minute, with warding lanterns
    Mimo hung at `wards`."""
    grid = land({cell: "warding_lantern" for cell in wards})
    state = pet()
    state.update(name="Pip", position={"x": 0.0, "y": 1.0, "z": 1.0}, wards=[list(cell) for cell in wards])
    creature = grid.herd.add("gloomling", (9, 1, 1), 20.0, 0.0, 0.0, {"home": [9, 1, 1], "turn": 0})
    for turn in range(20):
        creature = grid.herd.get(creature["id"])
        at = 100.0 + turn * 3.0
        chase(creature, KINDS["gloomling"], scene(grid, state, at=at))
        grid.herd.save(creature)
    return where(grid.herd.get(creature["id"]), 200.0)


class WardTests(unittest.TestCase):
    def test_a_lantern_and_four_gloom_dust_make_a_warding_lantern_that_shines_like_a_lantern(self):
        self.assertEqual(craft({"lantern": 1, "gloom_dust": 4}, "warding_lantern", set()), {"warding_lantern": 1})
        grid = land({(0, 1, 5): "warding_lantern"})
        self.assertEqual(Lights(grid, (0, 1, 0), 16.0).at((0, 1, 5)), 15)
        self.assertEqual(KEEP["gloom_dust"], 4)  # kept on hand for one
        self.assertTrue(valuable("warding_lantern"))

    def test_no_hostile_steps_within_six_blocks_of_one(self):
        self.assertLess(math.dist(chased([]), (0, 1, 1)), 2.0)  # without one it walks right up to Mimo
        stopped = chased([(0, 1, 0)])
        self.assertGreater(math.dist(stopped, (0, 1, 0)), WARD_REACH)

    def test_mimo_keeps_the_cells_of_the_wards_it_hangs_and_takes_down(self):
        state = {}
        note_wards(state, {"kind": "place", "block": "warding_lantern", "target": {"x": 1, "y": 2, "z": 3}}, None, 1.0)
        note_wards(state, {"kind": "place", "block": "torch", "target": {"x": 4, "y": 2, "z": 3}}, None, 1.0)
        self.assertEqual(state["wards"], [[1, 2, 3]])
        note_wards(state, {"kind": "mine", "block": "warding_lantern", "target": {"x": 1, "y": 2, "z": 3}}, None, 2.0)
        self.assertEqual(state["wards"], [])


class AmberTests(unittest.TestCase):
    def test_amber_studded_armor_is_a_step_past_iron(self):
        self.assertEqual(RECIPES["amber_cap"]["ingredients"], {"iron_ingot": 2, "amber": 2})
        self.assertAlmostEqual(armor_cut({"iron_cap": 1, "iron_tunic": 1}), 0.45)
        self.assertAlmostEqual(armor_cut({"iron_cap": 1, "iron_tunic": 1, "amber_cap": 1, "amber_tunic": 1}), 0.60)

    def test_craft_tools_studs_a_slot_mimo_wears_iron_on_once_it_carries_the_amber(self):
        self.assertEqual(frontier_orders({"iron_tunic": 1, "amber": 3}), [("amber_tunic",)])
        self.assertEqual(frontier_orders({"iron_tunic": 1, "iron_cap": 1, "amber": 2}), [("amber_cap",)])
        self.assertEqual(frontier_orders({"amber": 5}), [])  # no iron to stud
        self.assertIn(("amber_tunic",), tool_orders({"iron_pickaxe": 1, "iron_tunic": 1, "amber": 3}))
        self.assertIn(("warding_lantern",), tool_orders({"iron_pickaxe": 1, "lantern": 1, "gloom_dust": 4}))


class WardHomeTests(unittest.TestCase):
    """A finished cottage at home on a meadow, as test_survival_lighting builds it."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in design.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        set_home(self.db, design.anchor, 1.0)

    def situation(self, inventory):
        state = {"name": "Pip", "world_seed": "1", "position": {"x": 1.0, "y": 1.0, "z": 1.0},
                 "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(state)
        return Situation(state, self.grid, DAY, 0.0, self.db)

    def test_ward_home_hangs_one_on_a_corner_in_place_of_its_torch(self):
        ward = PURPOSES["ward_home"]
        self.assertFalse(ward.valid(self.situation({"warding_lantern": 1})))  # no light on a corner yet
        self.grid.put(*CORNERS[0], "torch")
        s = self.situation({"warding_lantern": 1})
        self.assertTrue(ward.valid(s))
        self.assertTrue(meets_need(s, "ward_home", ward.score(s)))
        steps = ward.plan(s, ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                           events=[], db=self.db))
        self.assertEqual([step["kind"] for step in steps][-2:], ["mine", "place"])
        self.assertEqual((steps[-1]["target"], steps[-1]["block"]), (CORNERS[0], "warding_lantern"))
        self.grid.put(*CORNERS[0], "warding_lantern")
        self.assertNotIn(tuple(CORNERS[0]), [tuple(cell) for cell in dark_corners(self.situation({}))])


if __name__ == "__main__":
    unittest.main()
```

The new block comes last, after L3's, and gloom dust is now kept for a lantern:

In `backend/tests/test_blocks_bigger_world.py`, replace:

```python
                "mossy_cobblestone", "stone_bricks", "ladder", "fence", "creature_sprout")
```

with:

```python
                "mossy_cobblestone", "stone_bricks", "ladder", "fence", "creature_sprout")
FRONTIER = ("warding_lantern",)  # L5's blocks, after L3's
```

and replace:

```python
        self.assertEqual(names[-len(BIGGER_WORLD):], list(BIGGER_WORLD))
```

with:

```python
        self.assertEqual(names[-len(BIGGER_WORLD) - len(FRONTIER):-len(FRONTIER)], list(BIGGER_WORLD))
        self.assertEqual(names[-len(FRONTIER):], list(FRONTIER))  # L5's come after them
```

In `backend/tests/test_survival_gear.py`, replace:

```python
                         [("leather", 4), ("gloom_dust", 2), ("string", 2)])
```

with:

```python
                         [("leather", 4), ("string", 2)])  # L5: gloom dust is kept for a warding lantern
```

In `frontend/src/engine/blocks.test.ts`, replace:

```ts
  'mossy_cobblestone', 'stone_bricks', 'ladder', 'fence', 'creature_sprout']
```

with:

```ts
  'mossy_cobblestone', 'stone_bricks', 'ladder', 'fence', 'creature_sprout']
/** L5's blocks, after L3's (backend/tests/test_blocks_bigger_world.py FRONTIER). */
const FRONTIER = ['warding_lantern']
```

and replace:

```ts
    expect(blockId('door')).toBe(BLOCKS.length - 1 - BIGGER_WORLD.length)
```

with:

```ts
    expect(blockId('door')).toBe(BLOCKS.length - 1 - BIGGER_WORLD.length - FRONTIER.length)
```

and replace:

```ts
    expect(names.slice(-BIGGER_WORLD.length)).toEqual(BIGGER_WORLD)
```

with:

```ts
    expect(names.slice(-BIGGER_WORLD.length - FRONTIER.length, -FRONTIER.length)).toEqual(BIGGER_WORLD)
    expect(names.slice(-FRONTIER.length)).toEqual(FRONTIER)
    expect(GLOW_BY_ID[blockId('warding_lantern')]).toBe(1)  // L5: it glows like a lantern
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_frontier_gear.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.frontier_gear'`

- [ ] **Step 3: The block and the recipes**

In `shared/blocks.json`, replace:

```json
    "creature_sprout": {"pattern": "sprite_sprout", "color": [120, 196, 140], "accent": [246, 214, 132], "size": 2}
```

with:

```json
    "creature_sprout": {"pattern": "sprite_sprout", "color": [120, 196, 140], "accent": [246, 214, 132], "size": 2},
    "warding_lantern": {"pattern": "glow", "color": [176, 150, 236]}
```

and replace:

```json
    {"name": "creature_sprout", "color": [120, 196, 140], "textures": "creature_sprout", "layer": "cutout", "solid": false, "drop": "creature_seed", "hardness": 0.1}
```

with:

```json
    {"name": "creature_sprout", "color": [120, 196, 140], "textures": "creature_sprout", "layer": "cutout", "solid": false, "drop": "creature_seed", "hardness": 0.1},
    {"name": "warding_lantern", "color": [176, 150, 236], "textures": "warding_lantern", "layer": "opaque", "solid": true, "drop": "warding_lantern", "glow": true, "hardness": 0.6}
```

In `backend/services/crafting.py`, replace:

```python
    "gold_nuggets": {"ingredients": {"gold_nugget": 4}, "output": {"gold_ingot": 1}},
```

with:

```python
    "gold_nuggets": {"ingredients": {"gold_nugget": 4}, "output": {"gold_ingot": 1}},
    # A warding lantern (a lantern and gloom dust, anywhere) and amber-studded armor, a step past iron.
    "warding_lantern": {"ingredients": {"lantern": 1, "gloom_dust": 4}, "output": {"warding_lantern": 1}},
    "amber_cap": {"ingredients": {"iron_ingot": 2, "amber": 2}, "output": {"amber_cap": 1}, "station": "crafting_table"},
    "amber_tunic": {"ingredients": {"iron_ingot": 3, "amber": 3}, "output": {"amber_tunic": 1},
                    "station": "crafting_table"},
```

- [ ] **Step 4: More orders for craft_tools, and barriers for creatures**

In `backend/survival/toolmaking.py`, replace:

```python
POOLED = {"gold_ingot": "gold_nuggets"}
```

with:

```python
POOLED = {"gold_ingot": "gold_nuggets"}
# L5: functions of the inventory giving more orders for craft_tools, after its own (backend.survival.
# frontier_gear: amber-studded armor and warding lanterns). Each item they order needs its STATIONS.
MORE_ORDERS: list = []
```

and replace:

```python
    return orders + (armor_orders(inventory) if armor else []) + lantern_orders(inventory)
```

with:

```python
    extra = [order for more in MORE_ORDERS for order in more(inventory)]  # L5
    return orders + (armor_orders(inventory) if armor else []) + lantern_orders(inventory) + extra
```

In `backend/survival/creatures/acts.py`, replace:

```python
own steps. Nothing here searches for a path or edits a block.
```

with:

```python
own steps. Nothing here searches for a path or edits a block. L5: BARRIERS keep a creature from
some steps (hostiles from a warding lantern's reach).
```

and replace:

```python
CREATURE_ACTIONS: list[CreatureAction] = []
```

with:

```python
CREATURE_ACTIONS: list[CreatureAction] = []
# L5: functions (scene, kind, cell, step) that bar a creature of `kind` from stepping from `cell` to
# `step` (backend.survival.frontier_gear: hostiles keep away from a warding lantern). Wandering and
# chasing (backend.survival.creatures.hostiles) ask `barred`.
BARRIERS: list = []


def barred(scene: Scene, creature: dict, cell: Cell, step: Cell) -> bool:
    kind = kind_of(creature["kind"])
    return kind is not None and any(barrier(scene, kind, cell, step) for barrier in BARRIERS)
```

and replace:

```python
        options = [step for step in steps(scene.grid, cell, False, height_of(creature)) if step not in cells]
```

with:

```python
        options = [step for step in steps(scene.grid, cell, False, height_of(creature))
                   if step not in cells and not barred(scene, creature, cell, step)]
```

In `backend/survival/creatures/hostiles.py`, replace:

```python
    IDLE_SECONDS, PAUSE, WANDER, WANDER_CHANCE, CreatureAction, Scene, flat_distance, pause, register_action, wander,
```

with:

```python
    IDLE_SECONDS, PAUSE, WANDER, WANDER_CHANCE, CreatureAction, Scene, barred, flat_distance, pause, register_action,
    wander,
```

and replace:

```python
        options = [step for step in steps(scene.grid, cell, kind.water, kind.height) if step not in cells]
```

with:

```python
        options = [step for step in steps(scene.grid, cell, kind.water, kind.height)
                   if step not in cells and not barred(scene, creature, cell, step)]  # L5: a warding lantern
```

In `backend/survival/carrying.py`, replace:

```python
TREASURES += ("amber", "gold_nugget")  # L5: the frontier's riches (backend.survival.loot)
```

with:

```python
TREASURES += ("amber", "gold_nugget")  # L5: the frontier's riches (backend.survival.loot)
# backend.survival.frontier_gear adds its warding lantern and amber-studded armor.
```

- [ ] **Step 5: The warding lantern and amber-studded armor**

Create `backend/survival/frontier_gear.py`:

```python
"""Loot put to use (L5, "Frontier"): the warding lantern and amber-studded armor.

- The warding lantern: a lantern and 4 gloom dust (what gloomlings drop), anywhere. It is a block
  (shared/blocks.json, the last one) that gives light 15 like a lantern (light.BLOCK_LIGHT), and no
  hostile steps within WARD_REACH (6) blocks of one: a step that would bring a hostile that close,
  and closer than it is, is barred (acts.BARRIERS, used by wandering and chasing). Its light already
  keeps hostiles from coming out near it. Mimo keeps the cells of the ones it hung in its state
  (state["wards"], noted after each place or mine step: steps.OBSERVERS), so a creature's step never
  has to look for them. craft_tools makes up to WARDS_WANTED once Mimo carries 4 gloom dust and a
  lantern, or the iron and a torch for one (toolmaking.MORE_ORDERS); build_storage keeps 4 gloom dust
  on Mimo for it (storage.KEEP). The
  ward_home purpose hangs one on a corner of home (a torch corner, taking the torch or lantern that
  is there back into Mimo's arms; structures.STANDS_IN), so the yard stays clear: by day or in the
  evening, near home, while Mimo carries one and fewer than WARDS_WANTED hang there. Work band, 62;
  carrying one is an urge (goals.URGES), so it goes up whatever the goal.
- Amber-studded armor: an amber cap (2 iron ingots and 2 amber) and an amber tunic (3 iron ingots and
  3 amber), at a crafting table, a step past iron: they take 24 % and 36 % off a blow (60 % together;
  harm.ARMOR, harm.SLOTS). craft_tools makes a piece once Mimo wears iron on that slot and carries the
  amber (toolmaking.MORE_ORDERS). The iron piece stays with Mimo: only the best piece on a slot counts.
All of it registers into the registries of the modules it touches.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival import carrying, storage
from backend.survival.creatures.acts import BARRIERS, Scene
from backend.survival.creatures.harm import ARMOR, SLOTS
from backend.survival.creatures.kinds import Kind
from backend.survival.foraging import reach_steps
from backend.survival.goals import URGES
from backend.survival.grid import Cell
from backend.survival.light import BLOCK_LIGHT
from backend.survival.lighting import home_blueprint
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.structures import STANDS_IN
from backend.survival.steps import OBSERVERS, as_cell
from backend.survival.toolmaking import MORE_ORDERS, STATIONS

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

WARD = "warding_lantern"
WARD_REACH = 6.0
WARD_LIGHT = 15
WARD_DUST = 4  # gloom dust a warding lantern takes
WARDS_WANTED = 2
AMBER_PIECES = {"amber_tunic": ("iron_tunic", 3), "amber_cap": ("iron_cap", 2)}  # piece: (iron it tops, amber)
AMBER_CUTS = {"amber_cap": 0.24, "amber_tunic": 0.36}
LIGHTS = ("torch", "lantern")  # what a ward takes the place of on a home corner

BLOCK_LIGHT[WARD] = WARD_LIGHT
ARMOR.update(AMBER_CUTS)
SLOTS.update({"amber_cap": "head", "amber_tunic": "body"})
STATIONS.update({WARD: (), "amber_cap": ("crafting_table",), "amber_tunic": ("crafting_table",)})
STANDS_IN["torch"] = (*STANDS_IN["torch"], WARD)
storage.KEEP["gloom_dust"] = WARD_DUST
carrying.TREASURES += (WARD, "amber_cap", "amber_tunic")


# Hostiles keep away ----------------------------------------------------------------------------

def note_wards(state: dict, step: dict, context, at: float) -> None:
    """Keep state["wards"], the cells of the warding lanterns Mimo hung, after a place or mine step."""
    if step["kind"] not in ("place", "mine") or step.get("block") != WARD:
        return
    cell = list(as_cell(step["target"]))
    wards = [ward for ward in state.get("wards", []) if ward != cell]
    state["wards"] = wards + [cell] if step["kind"] == "place" else wards


def warded(scene: Scene, kind: Kind, cell: Cell, step: Cell) -> bool:
    """A hostile may not step within WARD_REACH of a warding lantern, closer than it stands now."""
    if not kind.hostile:
        return False
    for ward in scene.state.get("wards", ()):
        if math.dist(step, ward) <= WARD_REACH and math.dist(step, ward) < math.dist(cell, ward):
            return True
    return False


BARRIERS.append(warded)
OBSERVERS.append(note_wards)


# What craft_tools makes ------------------------------------------------------------------------

def wards_at_home(s: Situation) -> int:
    blueprint = home_blueprint(s)
    if blueprint is None:
        return 0
    return sum(1 for planned in blueprint.parts("torch") if s.grid.material(*planned.cell) == WARD)


def frontier_orders(inventory: dict) -> list[tuple[str, ...]]:
    """Amber armor on a slot Mimo wears iron on, with the amber carried; then a warding lantern."""
    orders = []
    for piece, (iron, amber) in AMBER_PIECES.items():
        if inventory.get(piece, 0) < 1 and inventory.get(iron, 0) > 0 and inventory.get("amber", 0) >= amber:
            orders.append((piece,))
    if inventory.get("gloom_dust", 0) >= WARD_DUST and inventory.get(WARD, 0) < WARDS_WANTED:
        orders.append((WARD,))
    return orders


MORE_ORDERS.append(frontier_orders)


# ward_home -------------------------------------------------------------------------------------

def ward_corners(s: Situation) -> list[Cell]:
    """Home's torch corners holding a torch or lantern a ward could take the place of, while fewer than
    WARDS_WANTED wards hang there."""
    blueprint = home_blueprint(s)
    if blueprint is None or wards_at_home(s) >= WARDS_WANTED:
        return []
    return [planned.cell for planned in blueprint.parts("torch") if s.grid.material(*planned.cell) in LIGHTS]


def ward_valid(s: Situation) -> bool:
    return not s.night and s.count(WARD) > 0 and bool(ward_corners(s))


def plan_ward(s: Situation, context: ActionContext) -> list[dict]:
    corners = ward_corners(s)
    if not corners or s.brain["batches"] > 0 or s.count(WARD) < 1:
        return []
    cell = corners[0]
    return reach_steps(s, [(cell, [{"kind": "mine", "target": list(cell)},
                                   {"kind": "place", "target": list(cell), "block": WARD}])])


register(Purpose(
    "ward_home", "hang a warding lantern",
    "Hang a warding lantern on a corner of home: its light and its gloom keep hostiles six blocks away.",
    valid=ward_valid,
    facts=lambda s: f"carrying {s.count(WARD)} warding lanterns, {wards_at_home(s)} hanging at home",
    score=lambda s: 62.0, plan=plan_ward,
    thoughts=("Let them keep their distance tonight.", "This glow will keep the yard clear.")))

URGES["ward_home"] = lambda s: s.count(WARD) > 0
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import loot, ruins  # noqa: F401  (L5: better drops and mining luck, ruins and their loot)
```

with:

```python
from backend.survival import loot, ruins  # noqa: F401  (L5: better drops and mining luck, ruins and their loot)
from backend.survival import frontier_gear  # noqa: F401  (L5: the warding lantern and amber-studded armor)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_frontier_gear.py"` and `python3 -m unittest discover -s backend/tests -p "test_blocks*.py"`
Expected: `Ran 6 tests` … `OK`, and `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1163 tests` … `OK` (6 new).

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  310 passed (310)`, the build succeeds (the atlas draws the new tile), eslint prints nothing.

- [ ] **Step 7: Commit**

```bash
git add backend/survival/frontier_gear.py shared/blocks.json backend/services/crafting.py backend/survival/toolmaking.py backend/survival/creatures/acts.py backend/survival/creatures/hostiles.py backend/survival/carrying.py backend/survival/brain.py backend/tests/test_survival_frontier_gear.py backend/tests/test_blocks_bigger_world.py backend/tests/test_survival_gear.py frontend/src/engine/blocks.test.ts
git commit -m "feat: loot put to use - a warding lantern of gloom dust that keeps hostiles six blocks off, hung at home, and amber-studded armor a step past iron" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Risk against reward: riches farther out, home before dark, what the model is told

**Files:**
- Create: `backend/survival/frontier.py`
- Modify: `backend/survival/rings.py` (`gear_short_of`, `short_of(gear_only)`, `far_at`), `backend/survival/trips.py` (`FENCES`, `fenced`, in `beyond`), `backend/survival/purposes.py` (`FAR_HOMES`, `HOMEWARD_LEADS`, `far_home`, `homeward_from`; `home_of` falls back; `late_day` earlier far out), `backend/survival/reflexes.py` (head_home's window from `homeward_from`), `backend/survival/creatures/defense.py` (a flight runs home only within 128 blocks), `backend/survival/pickers.py` (the payload's `frontier`), `backend/survival/brain.py` (imports `frontier`)
- Test: `backend/tests/test_survival_frontier.py` (create), `backend/tests/test_survival_pickers.py` (modify)

**Interfaces:**
- Consumes: Task 1's rings (`center`, `distance_home`, `ready_ring`, `ring_at`, `ring_here`, `ring_name`, `ring_payload`, `OPEN_RINGS`, `ANNOUNCED_FROM`, `DEEPEST`); Task 6's `ruins.RUIN`, `RUIN_SIGHT`, `opened`, `ruin_targets`, `ruins_near`; L4a's `goals.Goal`, `Milestone`, `register_goal`, `ADVANCES`, `trips.Reason`, `Find`, `register_reason`, `life_goals.whole`, and its final fix wave's one home lookup (`home.built_home`, `home.home_place`); `memory.places`; `pathing.WALK_SECONDS`; the test helpers `test_survival_ruins.CHEST`, `GEARED`, `Pet`.
- Produces:
  - `rings.gear_short_of(s, ring)`; `short_of(s, ring, gear_only=False)`; `state["frontier"]["far_at"]`.
  - `purposes.FAR_HOMES: list` of `(s) -> dict | None`, `purposes.HOMEWARD_LEADS: list` of `(s) -> float`; `purposes.far_home(s)`, `purposes.homeward_from(s) -> float` (once per Situation); `purposes.late_day(s)` starts earlier by the same lead.
  - `trips.FENCES: list` of `(s, cell) -> bool`, `trips.fenced(s, cell)`, checked first in `trips.beyond`.
  - `frontier.FRONTIER_REACH = 480.0`, `RUIN_SPOTS = 80.0`, `RUIN_NEAR = 16.0`, `DETOUR = 1.5`, `LEAD_SLACK = 60.0`, `EDGE = 16.0`, `RUIN_PULL = 240.0`; `since`, `geared_ring`, `ring_limit(ring)`, `reach_limit(s)`, `past_readiness(s, cell)`, `unopened_ruins(s, deepest)`, `frontier_valid`, `reached_far`, `opened_since`, `ruin_places` (every ruin Mimo remembers, however far), `home_with_loot`, `pull`, `walk_seconds`, `homeward_with_loot`, `looting_far` (in `goals.ADVANCES` as `"go_home"` and `"loot_ruin"`), `riches_wanted`, `danger_words`, `riches_value`, `riches_spots`, `riches_look`, `far_lead`, `far_home`; the goal `frontier` ("Riches farther out") and the reason `riches` ("seek riches farther out").
  - The model payload's `frontier` (`rings.ring_payload`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_frontier.py`:

```python
import math
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers the frontier goal, the riches trip and the hooks)
from backend.survival.creatures.defense import plan_flee
from backend.survival.goals import GOALS, REACHED, adopt_goal, advances, complete, counted, is_open, share_of
from backend.survival.memory import know, remember, set_home, update_place
from backend.survival.pickers import context_payload
from backend.survival.purposes import HOMEWARD, LATE_DAY, PURPOSES, home_of, homeward_from, late_day
from backend.survival.reflexes import head_home_due
from backend.survival.ruins import RUIN, notice_ruins, ruins_near
from backend.survival.situation import Situation
from backend.survival.trips import REASONS, beyond, offers, targets, wanted_now
from backend.tests.test_survival_pickers import DAY
from backend.tests.test_survival_ruins import CHEST, GEARED, Pet

HOME = (CHEST[0] - 150, 9, CHEST[2])  # the ruin stands in the far wilds, 150 blocks east of home
IRON = {"iron_sword": 1, "iron_cap": 1, "iron_tunic": 1, "bow": 1, "arrow": 8, "bread": 2}


def at_home(inventory=None, offset=(0, 0), clock=DAY):
    """A pet with the home it built at HOME (its first shelter reached), standing `offset` blocks from it."""
    pet = Pet(offset=(HOME[0] - CHEST[0] + offset[0], offset[1]), center=(HOME[0], HOME[2]), inventory=inventory)
    set_home(pet.db, HOME, 0.0)
    know(pet.db, "first_shelter", REACHED, 0.0)
    pet.clock = clock
    pet.situation = lambda: Situation(pet.state, pet.grid, pet.clock, 10.0, pet.db)
    return pet


def shares(s):
    return [share_of(s, milestone) for _, milestone in counted(GOALS["frontier"])]


class GoalTests(unittest.TestCase):
    def test_an_ungeared_pet_is_never_offered_riches(self):
        pet = at_home({"stone_sword": 1, "bread": 4})  # a sword, but no armor
        self.assertFalse(is_open(pet.situation(), GOALS["frontier"]))
        adopt_goal(pet.state, "frontier", "utility", "", 0.0)
        s = pet.situation()
        self.assertIsNone(wanted_now(s, REASONS["riches"]))
        self.assertNotIn("riches", [offer.reason for offer in offers(s)])

    def test_a_geared_pet_takes_the_goal_and_its_trip_heads_out(self):
        pet = at_home(dict(GEARED))
        self.assertTrue(is_open(pet.situation(), GOALS["frontier"]))
        adopt_goal(pet.state, "frontier", "utility", "", 0.0)
        s = pet.situation()
        self.assertEqual(wanted_now(s, REASONS["riches"]), "old ruins stand out there, and I'm ready for the far wilds")
        found = targets(s, REASONS["riches"])
        self.assertTrue(found)
        self.assertTrue(found[0].what.startswith("toward an old ruin"), found[0].what)  # the ruin east pulls
        self.assertEqual(found[0].direction, "east")

    def test_its_land_is_the_far_wilds_and_never_past_what_mimo_is_ready_for(self):
        value = REASONS["riches"].value
        pet = at_home(dict(GEARED), offset=(100, 0))
        adopt_goal(pet.state, "frontier", "utility", "", 0.0)
        s = pet.situation()
        self.assertEqual(value(s, CHEST[0] + 3, CHEST[2]), (1.0, "an old ruin in the far wilds, danger 2"))
        nearer, farther = value(s, CHEST[0], CHEST[2] + 30), value(s, CHEST[0], CHEST[2] + 100)
        self.assertGreater(nearer[0], farther[0])  # the ruin's pull
        self.assertEqual(nearer[1], "toward an old ruin, the far wilds, danger 2")
        self.assertEqual(value(s, HOME[0], HOME[2] + 300), (0.0, ""))  # the frontier: not ready for it
        self.assertEqual(value(s, HOME[0] + 10, HOME[2]), (0.0, ""))  # home ground holds no riches
        ready = at_home(dict(IRON), offset=(100, 0))
        adopt_goal(ready.state, "frontier", "utility", "", 0.0)
        self.assertGreater(REASONS["riches"].value(ready.situation(), HOME[0], HOME[2] + 300)[0], 0.0)

    def test_no_trip_heads_into_a_ring_mimo_is_not_ready_for(self):
        far = at_home(dict(GEARED), offset=(250, 0))
        frontier_cell, far_wilds_cell = (HOME[0] + 280, 9, HOME[2]), (HOME[0] + 200, 9, HOME[2])
        edge_cell = (HOME[0] + 245, 9, HOME[2])  # the far wilds, but within 16 blocks of the frontier
        for name in ("wander", "riches", "iron"):
            self.assertTrue(beyond(far.situation(), REASONS[name], None, frontier_cell), name)
            self.assertTrue(beyond(far.situation(), REASONS[name], None, edge_cell), name)
            self.assertFalse(beyond(far.situation(), REASONS[name], None, far_wilds_cell), name)
        ready = at_home(dict(IRON), offset=(250, 0))
        self.assertFalse(beyond(ready.situation(), REASONS["wander"], None, frontier_cell))

    def test_late_in_the_day_there_is_no_time_for_one(self):
        pet = at_home(dict(GEARED), clock={**DAY, "seconds_into_day": 1900.0})
        adopt_goal(pet.state, "frontier", "utility", "", 0.0)
        self.assertIsNone(wanted_now(pet.situation(), REASONS["riches"]))

    def test_the_goal_counts_the_far_wilds_an_opened_chest_and_coming_home(self):
        pet = at_home(dict(GEARED))
        adopt_goal(pet.state, "frontier", "utility", "", 5.0)
        self.assertEqual(shares(pet.situation()), [0.0, 0.0, 0.0])
        pet.state["frontier"]["far_at"] = 20.0
        pet.state["position"] = {"x": float(CHEST[0] + 2), "y": 9.0, "z": float(CHEST[2])}
        notice_ruins(pet.state, {"kind": "walk"}, pet.context, 20.0)
        self.assertEqual(REASONS["riches"].look(pet.situation(), pet.context).words,
                         "an old ruin in the far wilds, danger 2")
        update_place(pet.db, RUIN, CHEST, {"opened": 30.0})
        self.assertEqual(shares(pet.situation()), [1.0, 1.0, 0.0])
        pet.state["position"] = {"x": float(HOME[0] + 3), "y": 9.0, "z": float(HOME[2])}
        self.assertTrue(complete(pet.situation(), GOALS["frontier"]))

    def test_once_a_chest_is_open_the_goal_stays_open_until_home_and_only_then_is_home_a_step(self):
        pet = at_home(dict(GEARED), offset=(150, 0))
        adopt_goal(pet.state, "frontier", "utility", "", 5.0)
        frontier = GOALS["frontier"]
        self.assertFalse(advances(pet.situation(), "go_home", frontier))  # no loot yet: home is no step
        for chest in ruins_near(pet.state["world_seed"], HOME[0], HOME[2], 480):
            pet.state.setdefault("chests", {})[f"{chest[0]},{chest[1]},{chest[2]}"] = {}  # every ruin opened
        pet.walked()
        update_place(pet.db, RUIN, CHEST, {"opened": 30.0})
        s = pet.situation()
        self.assertTrue(is_open(s, frontier))  # still open: the loot has to come home
        self.assertTrue(advances(s, "go_home", frontier))

    def test_far_out_in_the_frontier_home_is_home_and_a_chest_opened_there_counts_back_home(self):
        pet = at_home(dict(IRON), offset=(300, 0))  # ready for the frontier, 300 blocks out
        adopt_goal(pet.state, "frontier", "utility", "", 5.0)
        out_there = (HOME[0] + 300, 9, HOME[2] + 2)  # past the 256 blocks a Situation reads places within
        remember(pet.db, RUIN, out_there, 20.0, "frontier")
        update_place(pet.db, RUIN, out_there, {"opened": 30.0})
        self.assertTrue(is_open(pet.situation(), GOALS["frontier"]))  # the home it built is still home
        pet.state["frontier"]["far_at"] = 20.0
        pet.state["position"] = {"x": float(HOME[0] + 3), "y": 9.0, "z": float(HOME[2])}
        self.assertEqual(shares(pet.situation()), [1.0, 1.0, 1.0])


class HomewardTests(unittest.TestCase):
    def test_far_out_home_is_still_home_and_the_walk_back_starts_sooner(self):
        near = at_home(dict(GEARED), offset=(100, 0)).situation()
        self.assertEqual(homeward_from(near), HOMEWARD)  # the near wilds play as before
        far = at_home(dict(GEARED), offset=(200, 0))
        s = far.situation()
        self.assertEqual((home_of(s)["x"], home_of(s)["z"]), (HOME[0], HOME[2]))
        self.assertAlmostEqual(homeward_from(s), HOMEWARD - (200 * 0.3 * 1.5 + 60.0))
        far.clock = {**DAY, "seconds_into_day": HOMEWARD - 100.0}
        self.assertTrue(head_home_due(far.situation()))
        far.clock = {**DAY, "seconds_into_day": LATE_DAY - 100.0}  # late already, out there: home wins
        self.assertTrue(late_day(far.situation()))
        self.assertGreaterEqual(PURPOSES["go_home"].score(far.situation()), 70.0)
        self.assertFalse(late_day(at_home(dict(GEARED), offset=(100, 0), clock=far.clock).situation()))

    def test_far_from_home_a_flight_runs_from_the_threat_not_all_the_way_home(self):
        far = at_home(dict(GEARED), offset=(200, 0))
        x, z = HOME[0] + 200, HOME[2]
        threat = {"id": 1, "kind": "gloomling", "x": float(x + 3), "y": 9.0, "z": float(z), "state": {"chasing": True}}
        with patch("backend.survival.creatures.defense.flee_threat", lambda situation, found: threat), \
                patch("backend.survival.creatures.defense.threats", lambda situation: [threat]):
            steps = plan_flee(far.situation(), None)
        self.assertLess(math.dist(steps[0]["target"][::2], (x, z)), 20)


class PayloadTests(unittest.TestCase):
    def test_the_model_is_told_the_ring_and_how_ready_mimo_is(self):
        pet = at_home(dict(GEARED), offset=(60, 0))
        frontier = context_payload(pet.situation(), [])["frontier"]
        self.assertEqual((frontier["ring"], frontier["name"], frontier["ready_for"], frontier["ready_for_name"]),
                         (1, "Near wilds", 2, "Far wilds"))


if __name__ == "__main__":
    unittest.main()
```

The payload gains a key:

In `backend/tests/test_survival_pickers.py`, replace:

```python
                                        "known_places", "recent_events", "trigger", "building", "exploration",
```

with:

```python
                                        "known_places", "recent_events", "trigger", "building", "exploration",
                                        "frontier",  # L5
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_frontier.py"`
Expected: ERROR: `ImportError: cannot import name 'homeward_from' from 'backend.survival.purposes'`

- [ ] **Step 3: Gear alone, and when Mimo was last far out**

In `backend/survival/rings.py`, replace:

```python
past the near wilds is a notable "found" event ("Pip reached the far wilds for the first time.").
```

with:

```python
past the near wilds is a notable "found" event ("Pip reached the far wilds for the first time.").
L5's frontier goal adds "far_at", the last time Mimo stood past the near wilds.
```

and replace:

```python
    frontier["ring"] = ring
```

with:

```python
    frontier["ring"] = ring
    if ring >= ANNOUNCED_FROM:
        frontier["far_at"] = at  # the last time Mimo stood past the near wilds (the frontier goal reads it)
```

and replace:

```python
def short_of(s: Situation, ring: int) -> list[str]:
    """What Mimo lacks to go into `ring` on purpose, in words; [] when it is ready (always for 0 and 1)."""
```

with:

```python
def short_of(s: Situation, ring: int, gear_only: bool = False) -> list[str]:
    """What Mimo lacks to go into `ring` on purpose, in words; [] when it is ready (always for 0 and 1).
    With `gear_only`, only its weapons and armor are weighed (not its health or food)."""
```

and replace:

```python
        missing.append(ARMOR_WORDS[need.armor])
```

with:

```python
        missing.append(ARMOR_WORDS[need.armor])
    if gear_only:
        return missing
```

and replace:

```python
        missing.append("food for half a day")
    return missing
```

with:

```python
        missing.append("food for half a day")
    return missing


def gear_short_of(s: Situation, ring: int) -> list[str]:
    """The weapons and armor Mimo lacks for `ring`, in words."""
    return short_of(s, ring, gear_only=True)
```

- [ ] **Step 4: Home from far out, and the walk back started sooner**

In `backend/survival/purposes.py`, replace:

```python
    within HOME_RANGE. L4a final fix wave, I1: the built home is read through the one home lookup
    (backend.survival.home), not only from the places in sight."""
```

with:

```python
    within HOME_RANGE; else (L5) the home FAR_HOMES name. L4a final fix wave, I1: the built home is
    read through the one home lookup (backend.survival.home), not only from the places in sight."""
```

and replace:

```python
    return nearest(s.places, s.here, SHELTER_KINDS, HOME_RANGE)
```

with:

```python
    found = nearest(s.places, s.here, SHELTER_KINDS, HOME_RANGE)
    return found if found is not None else far_home(s)  # L5: the home it built, from far out
```

and replace:

```python
    """Dusk, or the last 5 game minutes of the day before it."""
    return s.phase == "dusk" or (s.phase == "day" and s.clock["seconds_into_day"] >= LATE_DAY)
```

with:

```python
    """Dusk, or the last 5 game minutes of the day before it; L5: far from home, earlier by the walk
    home (`homeward_from`), so going home wins and outdoor work gives way from then on."""
    early = HOMEWARD - homeward_from(s)
    return s.phase == "dusk" or (s.phase == "day" and s.clock["seconds_into_day"] >= LATE_DAY - early)
```

and replace:

```python
    return LATE_PENALTY if outdoors and late_day(s) else 0.0
```

with:

```python
    return LATE_PENALTY if outdoors and late_day(s) else 0.0


# L5: functions of the Situation naming the home Mimo built when home_of's own reach does not find it
# (backend.survival.frontier: from the far wilds on), and functions giving game seconds the head_home
# window opens early (frontier: the walk home from out there). One that crashes counts for nothing.
FAR_HOMES: list = []
HOMEWARD_LEADS: list = []


def far_home(s: Situation) -> dict | None:
    """The first home FAR_HOMES name (L5), looked up once per Situation."""
    def look() -> dict | None:
        for find in FAR_HOMES:
            try:
                home = find(s)
            except Exception as error:
                log_once(logger, "far home", error)
                continue
            if home is not None:
                return home
        return None
    return s.sensed("far home", look)


def homeward_from(s: Situation) -> float:
    """When the head_home window opens: HOMEWARD, earlier by the largest of HOMEWARD_LEADS (L5), worked
    out once per Situation."""
    def look() -> float:
        lead = 0.0
        for more in HOMEWARD_LEADS:
            try:
                lead = max(lead, float(more(s)))
            except Exception as error:
                log_once(logger, "homeward lead", error)
        return max(0.0, HOMEWARD - lead)
    return s.sensed("homeward from", look)
```

In `backend/survival/reflexes.py`, replace:

```python
from backend.survival.senses import near_failure
```

with:

```python
from backend.survival.purposes import homeward_from  # L5: far out, the window opens sooner
from backend.survival.senses import near_failure
```

and replace:

```python
    if not HOMEWARD <= s.clock["seconds_into_day"] < NIGHTFALL:
```

with:

```python
    if not homeward_from(s) <= s.clock["seconds_into_day"] < NIGHTFALL:
```

In `backend/survival/creatures/defense.py`, replace:

```python
from backend.survival.purposes import home_of, underground, walk_to
```

with:

```python
from backend.survival.purposes import BUILT_HOME_RANGE, home_of, underground, walk_to
```

and replace:

```python
    if home is not None and home["note"] == BUILT and not indoors(s):
```

with:

```python
    if home is not None and home["note"] == BUILT and not indoors(s) and s.distance(cell_of(home)) <= BUILT_HOME_RANGE:
```

- [ ] **Step 5: The frontier goal, the riches trip and the fence every trip keeps inside**

The fence goes into L4a's `trips.beyond`, which spots and targets both pass through; it anchors on `FINDS` and `beyond`'s first lines, which L4a's fix rounds leave alone.

In `backend/survival/trips.py`, replace:

```python
FINDS: list = []
```

with:

```python
FINDS: list = []
# L5: functions (s, cell) -> True for a place no trip may head for, whatever its reason
# (backend.survival.frontier: a ring deeper than Mimo is ready for). One that crashes fences nothing.
FENCES: list = []
```

and replace:

```python
    """Farther from home than the reason's reach, and no nearer to it than Mimo is now."""
```

with:

```python
    """Farther from home than the reason's reach, and no nearer to it than Mimo is now; or (L5) a
    place FENCES keep every trip from."""
    if fenced(s, cell):
        return True
```

and replace:

```python
    return away > reach_of(s, reason) and away >= math.hypot(s.here[0] - home[0], s.here[2] - home[2])
```

with:

```python
    return away > reach_of(s, reason) and away >= math.hypot(s.here[0] - home[0], s.here[2] - home[2])


def fenced(s: Situation, cell: Cell) -> bool:
    """A place one of FENCES keeps every trip from (L5); one that crashes fences nothing (logged once)."""
    for fence in FENCES:
        try:
            if fence(s, cell):
                return True
        except Exception as error:
            log_once(logger, "trip fence", error)
    return False
```

Create `backend/survival/frontier.py`:

```python
"""Risk against reward (L5, "Frontier"): a geared pet goes farther out for riches, and comes home.

- The frontier goal, "Riches farther out": open to a pet with a home it built that is geared for the
  far wilds (rings.gear_short_of: a stone sword or better, or a bow and 8 arrows, and leather armor
  or better) while an old ruin whose chest it never opened stands in a ring it is geared for, past the
  near wilds and within FRONTIER_REACH of home. An ungeared pet never has it. It repeats (goals.Goal
  .repeat): its milestones count from when it was set: reach the far wilds, open an old ruin's chest,
  come home to home ground with the loot; once a chest is open it stays open until Mimo is home.
  go_home advances it only with the loot, and loot_ruin only for a ruin past the near wilds
  (goals.ADVANCES), so a pet working toward another goal meanwhile is not sent home or to a near
  ruin in its name. Rules score: 40 plus a fifth of bravery and a tenth of curiosity (40 to 70).
- The "seek riches farther out" trip (trips.Reason "riches"): wanted only while that is Mimo's goal
  and no chest is opened yet, only when Mimo is ready for the ring (rings.ready_ring: the gear, 70
  health and half a day's food for the far wilds) and only with time to walk out to the farthest a
  trip may go (`reach_limit`) and back before the homeward window (`homeward_from`). Its land: a spot
  near an old ruin in a ring Mimo is ready for is sure ("an old ruin in the far wilds, danger 2");
  other land past home ground 0.2, and up to 0.8 more the nearer such a ruin lies (over RUIN_PULL
  blocks: the pull that sends the trip its way; a first version gave all the far wilds 0.6, and a pet
  whose ruins lay the other way walked four trips without finding one, measured on seed 11); nothing
  at all in a ring deeper than Mimo is ready for, so no trip ever leads a pet past its readiness. The
  ruins within RUIN_SPOTS blocks are its spots. Its reach from home is FRONTIER_REACH (480: the
  frontier's far edge, for a pet ready for it). A ruin in sight after a walk is the find; loot_ruin
  (backend.survival.ruins) follows up.
- No trip of any reason heads into the frontier or deeper while Mimo is not ready for it, nor within
  EDGE (16) blocks of it (trips.FENCES).
- Heading home before dark: from the far wilds on, the head_home window opens earlier by the walk
  home (purposes.HOMEWARD_LEADS: 0.45 game seconds a block at the normal pace, plus a game minute), and
  "late in the day" with it (purposes.late_day), so go_home scores 70 and more and outdoor work 30 less
  from then on: a head_home walk that a fight cut short is not lost to the next choice (measured: a
  pet 340 blocks out hurried home four times, each walk cut by a thornback and followed by farming),
  and the home Mimo built stays home however far it is (purposes.FAR_HOMES), so go_home and head_home
  find it however far out it is (L4a's follow-up lets them look from any distance too), and so does
  everything else that asks purposes.home_of, past its 128 blocks. A flight far from home runs away from
  the threat rather than all the way home (the refuge is only a home within 128 blocks, as before L5).
- What a model is told: the ring Mimo stands in, how far from home, the deepest ring it is ready for
  and what it lacks for the next (`frontier` in the payload, rings.ring_payload); each riches target
  names its ring and danger, and loot_ruin's facts the ruin's ring.
"""

from __future__ import annotations

import math

from backend.survival.goals import ADVANCES, Goal, Milestone, register_goal
from backend.survival.home import built_home, home_place
from backend.survival.life_goals import whole
from backend.survival.memory import places
from backend.survival.pathing import WALK_SECONDS
from backend.survival.purposes import FAR_HOMES, HOMEWARD_LEADS, homeward_from, late_day
from backend.survival.rings import (
    ANNOUNCED_FROM, DEEPEST, OPEN_RINGS, RINGS, center, distance_home, gear_short_of, ready_ring, ring_at, ring_here,
    ring_name,
)
from backend.survival.ruins import RUIN, RUIN_SIGHT, opened, ruin_targets, ruins_near
from backend.survival.situation import Situation
from backend.survival.trips import FENCES, Find, Reason, register_reason

FRONTIER_REACH = 480.0  # blocks from home a riches trip may go: the frontier's far edge
RUIN_SPOTS = 80.0  # ruins this close to Mimo are spots of the riches trip (a whole walk reaches them)
RUIN_NEAR = 16.0  # a column this close to an unopened ruin is sure to hold riches
DETOUR = 1.5  # a walk home is this many times the straight line
LEAD_SLACK = 60.0  # game seconds more, to be home before the window closes
EDGE = 16.0  # blocks inside the outer edge of the deepest ring Mimo may go into that every trip keeps to
RUIN_PULL = 240.0  # an unopened ruin draws a riches trip from this far: its pull falls from 1 beside it to 0 here


def since(s: Situation) -> float | None:
    goal = s.brain.get("goal") or {}
    return goal.get("since") if goal.get("name") == "frontier" else None


def geared_ring(s: Situation) -> int:
    """The deepest ring Mimo's weapons and armor alone are fit for (health and food aside)."""
    ring = OPEN_RINGS
    for deeper in range(OPEN_RINGS + 1, DEEPEST + 1):
        if gear_short_of(s, deeper):
            break
        ring = deeper
    return ring


def ring_limit(ring: int) -> float:
    """How far from home a trip may head for a pet ready for `ring`: EDGE short of that ring's outer edge
    (the far wilds' at least: 240 blocks), so a winding walk to a target stays inside it."""
    ready = max(ring, ANNOUNCED_FROM)
    return RINGS[ready + 1][2] - EDGE if ready < DEEPEST else math.inf


def unopened_ruins(s: Situation, deepest: int) -> list[tuple[int, int, int]]:
    """Ruins past the near wilds and no deeper than `deepest`, whose chest Mimo never opened and could see
    from inside `ring_limit(deepest)` (and within FRONTIER_REACH of home)."""
    def look() -> list[tuple[int, int, int]]:
        middle = center(s.state)
        if middle is None:
            return []
        reach = min(FRONTIER_REACH, ring_limit(deepest) + RUIN_NEAR)
        return [chest for chest in ruins_near(s.seed, middle[0], middle[1], reach)
                if ANNOUNCED_FROM <= ring_at(s.state, chest[0], chest[2]) <= deepest and not opened(s, chest)]
    return s.sensed(f"unopened ruins {deepest}", look)


def frontier_valid(s: Situation) -> bool:
    """Geared for the far wilds or deeper, with a home it built, and an unopened ruin out there -- or,
    while riches are its goal, a chest opened already: the goal stays open until Mimo is home with the
    loot (a first version closed it the moment the last chest out there was opened, and the goal was
    set aside before Mimo came home)."""
    ring = geared_ring(s)
    return built_home(s) and ring > OPEN_RINGS and (opened_since(s) or bool(unopened_ruins(s, ring)))


def reached_far(s: Situation) -> bool:
    at = since(s)
    far_at = (s.state.get("frontier") or {}).get("far_at")
    return at is not None and far_at is not None and far_at >= at


def opened_since(s: Situation) -> bool:
    """Mimo opened the chest of a ruin past the near wilds since riches became its goal."""
    at = since(s)
    return at is not None and any((place["data"] or {}).get("opened", -math.inf) >= at
                                  and ring_at(s.state, place["x"], place["z"]) >= ANNOUNCED_FROM
                                  for place in ruin_places(s))


def ruin_places(s: Situation) -> list[dict]:
    """Every ruin Mimo remembers, however far (Situation.places reads only those within 256 blocks on
    each axis, and a frontier ruin lies farther from home), read once per Situation."""
    return s.sensed("ruin places", lambda: places(s.db, (RUIN,)) if s.db is not None else [])


def home_with_loot(s: Situation) -> bool:
    return opened_since(s) and ring_here(s.state) == 0


def pull(s: Situation) -> float:
    return 40.0 + s.trait("bravery") / 5 + s.trait("curiosity") / 10


def homeward_with_loot(s: Situation, goal: Goal) -> bool:
    """go_home advances the frontier goal only with the loot (goals.ADVANCES): before that, going home
    is no step toward riches, and a pet working on another goal meanwhile is not sent home for it."""
    return goal.name != "frontier" or opened_since(s)


def looting_far(s: Situation, goal: Goal) -> bool:
    """loot_ruin advances the frontier goal only for a ruin past the near wilds (goals.ADVANCES)."""
    if goal.name != "frontier":
        return True
    targets = ruin_targets(s)
    return bool(targets) and ring_at(s.state, targets[0][0], targets[0][2]) >= ANNOUNCED_FROM


ADVANCES["go_home"] = homeward_with_loot
ADVANCES["loot_ruin"] = looting_far

register_goal(Goal(
    "frontier", "Riches farther out",
    "Past the near wilds old ruins stand with chests nobody opened, and what lives out there drops gold and amber.",
    (Milestone("Reach the far wilds", lambda s: whole(reached_far(s)), ("explore",)),
     Milestone("Open an old ruin's chest", lambda s: whole(opened_since(s)), ("loot_ruin", "explore")),
     Milestone("Come home with the loot", lambda s: whole(home_with_loot(s)), ("go_home",))),
    score=pull, thought="Old ruins stand out in the far wilds. I'm armed and ready for them.",
    after=("first_shelter",), valid=frontier_valid, repeat=True))


# The riches trip -------------------------------------------------------------------------------

def walk_seconds(s: Situation, blocks: float) -> float:
    """Game seconds Mimo takes to walk `blocks`, the way round included."""
    return blocks * WALK_SECONDS * DETOUR * s.scale / max(s.action_scale, 1e-9)


def riches_wanted(s: Situation) -> str | None:
    """While riches are Mimo's goal and no chest is open yet, ready for the ring and with the daylight
    to walk out and back."""
    ready = ready_ring(s)
    if since(s) is None or opened_since(s) or ready <= OPEN_RINGS or s.night or late_day(s):
        return None
    out_and_back = 2 * min(reach_limit(s), FRONTIER_REACH)  # blocks, at the farthest the trip may go
    if s.clock["seconds_into_day"] + walk_seconds(s, out_and_back) + LEAD_SLACK > homeward_from(s):
        return None
    return f"old ruins stand out there, and I'm ready for the {ring_name(ready).lower()}"


def danger_words(ring: int) -> str:
    return f"the {ring_name(ring).lower()}, danger {ring}"


def riches_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    """Sure beside an unopened ruin in a ring Mimo is ready for; elsewhere past home ground, 0.2 and up to
    0.8 more the nearer such a ruin (its pull, over RUIN_PULL blocks), so the trip heads its way; nothing
    in a ring deeper than Mimo is ready for, or on home ground."""
    ready, ring = ready_ring(s), ring_at(s.state, x, z)
    if ring > ready or ring < OPEN_RINGS:
        return 0.0, ""  # never past what Mimo is ready for
    near = min((math.hypot(chest[0] - x, chest[2] - z) for chest in unopened_ruins(s, ready)), default=math.inf)
    if near <= RUIN_NEAR:
        return 1.0, f"an old ruin in {danger_words(ring)}"
    pull = max(0.0, 1.0 - near / RUIN_PULL)
    where = danger_words(ring) if ring > OPEN_RINGS else "the near wilds, the way out"
    return 0.2 + 0.8 * pull, (f"toward an old ruin, {where}" if pull > 0 else where)


def riches_spots(s: Situation) -> list[tuple[int, int, str]]:
    x, _, z = s.here
    return [(chest[0], chest[2], f"an old ruin in {danger_words(ring_at(s.state, chest[0], chest[2]))}")
            for chest in unopened_ruins(s, ready_ring(s)) if math.hypot(chest[0] - x, chest[2] - z) <= RUIN_SPOTS]


def riches_look(s: Situation, context) -> Find | None:
    x, _, z = s.here
    ready = ready_ring(s)
    for chest in ruins_near(s.seed, x, z, RUIN_SIGHT):
        ring = ring_at(s.state, chest[0], chest[2])
        if ANNOUNCED_FROM <= ring <= ready and not opened(s, chest) and s.grid.material(*chest) == "chest":
            return Find(f"an old ruin in {danger_words(ring)}", True, new=False)
    return None


register_reason(Reason(
    "riches", "seek riches farther out", riches_wanted, riches_value, lambda s: 50.0 + s.trait("bravery") / 10,
    goals=("frontier",), spots=riches_spots, look=riches_look, reach=FRONTIER_REACH))


# Home before dark ------------------------------------------------------------------------------

def far_lead(s: Situation) -> float:
    """Game seconds the head_home window opens early from the far wilds on: the walk home and a minute."""
    if ring_here(s.state) < ANNOUNCED_FROM:
        return 0.0
    return walk_seconds(s, distance_home(s.state)) + LEAD_SLACK


def far_home(s: Situation) -> dict | None:
    """The home Mimo built, from the far wilds on, past purposes.home_of's own reach (128 blocks; going
    home looks from any distance since L4a's follow-up)."""
    if ring_here(s.state) < ANNOUNCED_FROM or not built_home(s):
        return None
    return home_place(s)


HOMEWARD_LEADS.append(far_lead)
FAR_HOMES.append(far_home)


def reach_limit(s: Situation) -> float:
    """How far from home any trip may head: `ring_limit` of the deepest ring Mimo is ready for."""
    return ring_limit(ready_ring(s))


def past_readiness(s: Situation, cell) -> bool:
    """No trip, whatever its reason, heads into the frontier or deeper while Mimo is not ready for that
    ring, nor within EDGE of it (trips.FENCES). Out near the far wilds' edge, L4a's reasons may head
    anywhere no farther from home than Mimo stands, and a walk winds round what is in its way: a geared
    pet drifted past 256 blocks on a wander and on a riches trip to a ruin at the edge (measured, seeds
    11 and 8). The far wilds stay open to the riches trip's own rule and to L4b's expeditions."""
    middle = center(s.state)
    return middle is not None and math.hypot(cell[0] - middle[0], cell[2] - middle[1]) > reach_limit(s)


FENCES.append(past_readiness)
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import frontier_gear  # noqa: F401  (L5: the warding lantern and amber-studded armor)
```

with:

```python
from backend.survival import frontier, frontier_gear  # noqa: F401  (L5: riches farther out; the warding lantern, amber)
```

- [ ] **Step 6: The model is told the ring and how ready Mimo is**

In `backend/survival/pickers.py`, replace:

```python
from backend.survival.purposes import PURPOSES, offered
```

with:

```python
from backend.survival.purposes import PURPOSES, offered
from backend.survival.rings import ring_payload
```

and replace:

```python
        **threats_payload(s),
```

with:

```python
        **threats_payload(s),
        # L5: the danger ring Mimo stands in, how far from home, the deepest ring it is ready for and
        # what it lacks for the next one.
        "frontier": ring_payload(s),
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_frontier.py"` and `python3 -m unittest discover -s backend/tests -p "test_survival_pickers.py"`
Expected: `Ran 11 tests` … `OK`, and `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1174 tests` … `OK` (11 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `OK` and `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/survival/frontier.py backend/survival/rings.py backend/survival/trips.py backend/survival/purposes.py backend/survival/reflexes.py backend/survival/creatures/defense.py backend/survival/pickers.py backend/survival/brain.py backend/tests/test_survival_frontier.py backend/tests/test_survival_pickers.py
git commit -m "feat: riches farther out - a geared pet seeks the far wilds' ruins, no trip goes past its readiness, it heads home before dark from far out, and the model is told the ring" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The headless checks: a geared trip, an ungeared pet, the budget

**Files:**
- Test: `backend/tests/test_survival_frontier_run.py` (create)

**Interfaces:**
- Consumes: everything in Tasks 1–8; L4a's `test_survival_sim.Errors`; `backend.tests.budget.best_mean`.
- Produces: the headless frontier runs (`run_trip(seed, geared)`, shared by the tests) and the far-wilds budget check.

- [ ] **Step 1: Write the checks**

Create `backend/tests/test_survival_frontier_run.py`:

```python
"""Headless frontier runs (L5): the real brain and the rules' Chooser take a pet to the far wilds.

Each run hatches a life on a fixed seed, stands a finished cottage of cobblestone with a bed beside
where it hatched and makes it the home it built (its first shelter reached, so the rings centre there,
its goals open and it sleeps in it), hands it gear and food, and ticks it at 1x in coarse steps, the
way the worker would. A first version only named the hatching spot home, with no shelter: build_shelter
stayed on offer everywhere, and a pet far out built there and slept out. A geared pet (a stone sword, a leather cap and tunic,
a bow and 16 arrows, food) starts with riches farther out as its goal; an ungeared one (the sword and
the food, no armor) is left to choose. Each run is made once and shared by the tests. Set
MIMO_SLOW_TESTS=1 for four game days on three seeds, in finer steps: over four days a pet left without
armor may make its own (L2's make_gear) and is geared from then on, so the check that holds in both
modes is that no riches trip ever runs while a pet is not geared. A last check times the creatures near
a geared pet in the far wilds at night: at most 20 ms a slice, like L2's budget.
"""

import functools
import logging
import os
import random
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.worldgen import terrain_height
from backend.survival import tick
from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.creatures.combat import SWORDS, weapon
from backend.survival.creatures.harm import armor_cut
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.table import Herd
from backend.survival.goals import REACHED, adopt_goal
from backend.survival.hatch import hatch
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.grid import world_grid
from backend.survival.memory import finish_structure, know, set_home
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.rings import BOW_INSTEAD, READY, ring_here
from backend.survival.ruins import LOOT
from backend.survival.situation import NIGHTFALL
from backend.survival.structures import start
from backend.survival.tick import MAX_STEP_SECONDS, tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.budget import best_mean
from backend.tests.test_survival_sim import Errors

BORN = 1_000_000.0
DAY = 3600.0
SLOW = os.environ.get("MIMO_SLOW_TESTS") == "1"
# Slow mode runs three seeds, to keep it within a quarter of an hour. Seed 3 was left out while its pet,
# with this cottage and with or without L5, got stuck 87 blocks from home and starved on day 4 (before
# L4a's final fix wave); since that wave its runs pass too.
SEEDS = (8, 11, 5) if SLOW else (8,)
DAYS = 4 if SLOW else 1
STEP = 5.0 if SLOW else 15.0
GEAR = {"stone_sword": 1, "leather_cap": 1, "leather_tunic": 1, "bow": 1, "arrow": 16, "bread": 6, "cooked_beef": 4}
UNGEARED = {"stone_sword": 1, "bread": 6, "cooked_beef": 4}
FAR_LOOT = {item for item, *_ in LOOT[2]} - {item for item, *_ in LOOT[1]}  # what only the far wilds' ruins hold


def home_of_its_own(db, state: dict) -> None:
    """A finished cottage beside where Mimo hatched, with a bed, made its home; Mimo stands inside."""
    grid = world_grid(db, state["world_seed"])
    here = tuple(round(state["position"][axis]) for axis in "xyz")
    sides = ("north", "east", "south", "west")
    site = find_site(grid, here, (3, 3), sides, "flat")
    design = shelter(site, Style("flat", "cobblestone", "planks", "none", sides), f"{state['name']}'s Snug Cottage")
    for planned in design.parts("floor", "wall", "roof", "bed"):
        grid.put(*planned.cell, "bed" if planned.part == "bed" else "cobblestone")
    finish_structure(db, start(db, grid, design, BORN), BORN)
    set_home(db, design.anchor, BORN)
    know(db, "first_shelter", REACHED, BORN)
    state["position"] = dict(zip("xyz", map(float, design.anchor)))


def armed_and_armored(inventory: dict) -> bool:
    """Armed and armored for the far wilds (rings.READY[2]), health and food aside."""
    sword = weapon(inventory)
    armed = (sword is not None and SWORDS[sword] >= READY[2].sword) or \
        (inventory.get("bow", 0) > 0 and inventory.get("arrow", 0) >= BOW_INSTEAD)
    return armed and armor_cut(inventory) >= READY[2].armor - 1e-9


@functools.lru_cache(maxsize=None)
def run_trip(seed: int, geared: bool) -> dict:
    """One headless run (see the module docstring), shared by the tests."""
    forget_logged()
    errors = Errors()
    logging.getLogger("backend").addHandler(errors)
    try:
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(seed), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                home_of_its_own(db, state)
                state["inventory"].update(GEAR if geared else UNGEARED)
                if geared:
                    adopt_goal(state, "frontier", "utility", "Old ruins stand out in the far wilds.", BORN)
                write_state(db, state)
            chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(seed), scale=1.0)
            t, deepest, at_nightfall, lowest, ungeared_riches = 0.0, 0, [], 100.0, 0
            while t < DAYS * DAY:
                t += STEP
                state = tick_life(registry, BORN + t, scale=1.0, mind=BRAIN, action_scale=1.0)
                if state is None or state["died_at"] is not None:
                    break
                chooser.poll(registry, BORN + t)
                deepest = max(deepest, ring_here(state))
                brain = state.get("brain") or {}
                if (brain.get("purpose") == "explore" and (brain.get("trip") or {}).get("reason") == "riches"
                        and not armed_and_armored(state["inventory"])):
                    ungeared_riches += 1  # a riches trip under way while Mimo is not geared for it
                lowest = min(lowest, state["vitals"]["health"])
                if t % DAY == NIGHTFALL:
                    at_nightfall.append(ring_here(state))
            events = world.events(100_000)
            return {"state": world.state(), "deepest": deepest, "at_nightfall": at_nightfall, "lowest": lowest,
                    "ungeared_riches": ungeared_riches,
                    "texts": [event["text"] for event in events], "kinds": [event["kind"] for event in events],
                    "errors": [record.getMessage() for record in errors.records]}
    finally:
        logging.getLogger("backend").removeHandler(errors)


class FrontierRunTests(unittest.TestCase):
    def test_a_geared_pet_goes_to_the_far_wilds_loots_a_ruin_and_is_home_by_nightfall(self):
        for seed in SEEDS:
            run = run_trip(seed, True)
            self.assertIsNone(run["state"]["died_at"], (seed, run["state"]["cause"]))
            self.assertEqual(run["errors"], [], seed)
            self.assertGreaterEqual(run["deepest"], 2, seed)
            opened = [text for text in run["texts"] if "opened an old chest in a ruin" in text]
            self.assertTrue(opened, seed)
            self.assertTrue(any(item.replace("_", " ") in text for text in opened for item in FAR_LOOT), (seed, opened))
            self.assertIn(f"{run['state']['name']} reached a goal: riches farther out.", run["texts"], seed)
            self.assertEqual(set(run["at_nightfall"]), {0}, seed)  # home ground every night

    def test_an_ungeared_pet_is_never_offered_riches(self):
        for seed in SEEDS:
            run = run_trip(seed, False)
            self.assertIsNone(run["state"]["died_at"], (seed, run["state"]["cause"]))
            self.assertEqual(run["errors"], [], seed)
            self.assertEqual(run["ungeared_riches"], 0, seed)
            if not SLOW:  # in its first game day it makes no armor: it never leaves the near wilds
                self.assertLessEqual(run["deepest"], 1, seed)
                self.assertFalse([text for text in run["texts"] if "seek riches" in text or "riches farther out" in text])
        self.assertEqual([run_trip(seed, True)["ungeared_riches"] for seed in SEEDS], [0] * len(SEEDS))

    def test_creatures_cost_well_under_twenty_milliseconds_a_slice_in_the_far_wilds_at_night(self):
        """A geared pet in the far wilds early in the first night, a toughened gloomling, skitter and
        thornback beside it and the dark free to bring more (the cap is 10 out there), caught up a
        60-game-second transaction at a time; best of up to 3 runs (backend.tests.budget)."""
        def run() -> list[float]:
            spent = [0.0] * 5

            def timed(*args, **kwargs):
                start = time.perf_counter()
                real(*args, **kwargs)
                spent[call - 1] += time.perf_counter() - start

            with tempfile.TemporaryDirectory() as root:
                registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
                life = hatch(registry, random.Random(3), timestamp=BORN)
                world = SurvivalWorld(registry.world_path(life))
                with world.transaction() as db:
                    state = read_state(db)
                    state["born_at"] = BORN - 2450.0  # early in the first night
                    state["inventory"].update(GEAR)
                    x, _, z = (round(state["position"][axis]) for axis in "xyz")
                    state["frontier"] = {"birthplace": [x - 150, z]}  # 150 blocks out: the far wilds
                    write_state(db, state)
                    for kind, cx in (("gloomling", x + 3), ("skitter", x - 3), ("thornback", x + 6)):
                        cell = (cx, terrain_height(cx, z, state["world_seed"]) + 1, z)
                        Herd(db).add(kind, cell, KINDS[kind].health * 1.7, BORN, BORN,
                                     {"home": list(cell), "turn": 0, "ring": 2, "most": KINDS[kind].health * 1.7})
                chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(3), scale=1.0)
                with patch("backend.survival.tick.simulate", timed):
                    for call in range(1, 6):
                        at = BORN + call * MAX_STEP_SECONDS
                        state = tick_life(registry, at, scale=1.0, mind=BRAIN, action_scale=1.0)
                        self.assertIsNone(state["died_at"], state["cause"])
                        self.assertEqual(state["frontier"]["ring"], 2)
                        chooser.poll(registry, at)
            return spent

        real = tick.simulate
        self.assertLess(best_mean(run, 0.020), 0.020)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the checks**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_frontier_run.py" -v`
Expected: `Ran 3 tests` … `OK` (about half a minute)

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_frontier_run.py"`
Expected: `Ran 3 tests` … `OK` (7 to 15 minutes; 40 under heavy load)

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1177 tests` … `OK` (3 new).

If the geared pet of a seed finds no ruin in its day (the ruins are the world's, not the test's), look at which way its riches trips headed (`decided to explore to seek riches farther out` and `Heading …` in its events) before touching the numbers of resolution 15.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_survival_frontier_run.py
git commit -m "test: a geared pet goes to the far wilds, loots a ruin and is home by nightfall, an ungeared one is never offered riches, and the creatures out there stay under 20 ms a slice" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Viewer: the ring, the rings on the map, elders, the thornback and amber armor

**Files:**
- Create: `frontend/src/survival/frontier.ts`, `frontend/src/survival/frontier.test.ts`
- Modify: `frontend/src/survival/types.ts` (`RingView`, `ring`, `elder`, `open_chest`), `frontend/src/survival/hud.ts` (words), `frontend/src/survival/SurvivalHud.tsx` (the ring line), `frontend/src/survival/Minimap.tsx` and `SurvivalWorld.tsx` (the rings on the map), `frontend/src/survival/SurvivalCreatures.tsx` (the elder glow), `frontend/src/survival/creatures.ts` (the thornback model, drop colours), `frontend/src/survival/petGear.ts` (amber armor), `frontend/src/survival/animation.ts` (`open_chest`'s move), `frontend/src/survival/cutaway.ts` (a warding lantern is no cover)
- Test: `frontend/src/survival/frontier.test.ts` (create), `frontend/src/survival/{creatures,petGear,hud}.test.ts` (modify)

**Interfaces:**
- Consumes: Task 1's `ring` in `/api/mimo`; Task 2's `elder` on a creature; Task 3's kind `thornback`; Task 4's items; Task 6's step `open_chest` and purpose `loot_ruin`; Task 7's `ward_home`, `amber_cap`, `amber_tunic`, `warding_lantern`; `overheadMap.toMap`, `MAP_BLOCKS`, `MapOrigin`.
- Produces: `types.RingView`, `SurvivalState.ring`, `Creature.elder`, `ActionKind` `'open_chest'`; `frontier.RING_STARTS`, `BAND_ALPHA`, `ELDER_GLOW`, `ELDER_STRENGTH`, `ringLine(ring)`, `ringTone(ring)`, `RingBand`, `ringBands(ring, origin)`, `elderGlow(creature)`, `emissiveOf(flash, glow)`; `Minimap` takes `ring`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/frontier.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { BAND_ALPHA, ELDER_STRENGTH, elderGlow, emissiveOf, ringBands, ringLine, ringTone } from './frontier'
import { MAP_BLOCKS, mapOrigin } from './overheadMap'

const FAR = { level: 2, name: 'Far wilds', center: { x: 0, z: 0 } }

describe('frontier', () => {
  it('names the ring Mimo stands in, and warns from the far wilds on', () => {
    expect(ringLine(FAR)).toBe('Far wilds · danger 2')
    expect(ringLine({ level: 0, name: 'Home ground', center: { x: 0, z: 0 } })).toBe('Home ground · danger 0')
    expect(ringLine(null)).toBeNull()
    expect(ringLine(undefined)).toBeNull()
    expect(ringTone(FAR)).toBe('wary')
    expect(ringTone({ ...FAR, level: 1 })).toBe('calm')
  })

  it('shades the bands around home that reach onto the map, each danger a little darker', () => {
    const home = ringBands(FAR, mapOrigin({ x: 0, y: 1, z: 0 }))
    expect(home.map((band) => band.level)).toEqual([1, 2])  // 96 blocks each way: the near and far wilds
    expect(home.map((band) => [band.inner, band.outer])).toEqual([[48, 128], [128, 256]])
    expect(home[0]).toMatchObject({ px: MAP_BLOCKS / 2 + 0.5, py: MAP_BLOCKS / 2 + 0.5, alpha: BAND_ALPHA })
    expect(home[1].alpha).toBeCloseTo(2 * BAND_ALPHA)
    const out = ringBands(FAR, mapOrigin({ x: 600, y: 1, z: 0 }))
    expect(out.map((band) => band.level)).toEqual([3, 4])  // 504 to 696 blocks from home
    expect(out[1].outer).toBeGreaterThan(700)
    expect(ringBands(null, mapOrigin({ x: 0, y: 1, z: 0 }))).toEqual([])
  })

  it('lights an elder faintly, and a blow still flashes red over it', () => {
    expect(elderGlow({ elder: true })).toBe(ELDER_STRENGTH)
    expect(elderGlow({})).toBe(0)
    expect(emissiveOf(0, 0)).toEqual([0, 0, 0])
    const [r, g, b] = emissiveOf(0, ELDER_STRENGTH)
    expect(b).toBeGreaterThan(r)
    expect(g).toBeGreaterThan(0)
    expect(emissiveOf(1, ELDER_STRENGTH)).toEqual([0.9, 0.12, 0.1])
  })
})
```

In `frontend/src/survival/creatures.test.ts`, replace:

```ts
describe('creatureModel', () => {
```

with:

```ts
describe('creatureModel', () => {
  it('builds the thornback (L5): low and broad, as tall as its kind, its head on its body', () => {
    const model = creatureModel('thornback')
    expect(model.scale).toBeCloseTo(VOXEL)
    expect(height('thornback')).toBeCloseTo(0.9)
    const cells = [...model.body, ...model.head].map(key)
    expect(new Set(cells).size).toBe(cells.length)
    expect(attached(model.head, [...model.body, ...model.head])).toBe(true)
    expect(dropColor('amber')).not.toEqual(dropColor('unknown_thing'))
    expect(dropColor('gold_nugget')).not.toEqual(dropColor('unknown_thing'))
  })

```

In `frontend/src/survival/petGear.test.ts`, replace:

```ts
    expect(cap.every((voxel) => voxel.y === 4)).toBe(true)
```

with:

```ts
    expect(cap.every((voxel) => voxel.y === 4)).toBe(true)
  })

  it('wears amber-studded armor over iron (L5), in the same places, in amber', () => {
    expect(wornTunic({ iron_tunic: 1, amber_tunic: 1 })).toBe('amber_tunic')
    expect(wornCap({ iron_cap: 1, amber_cap: 1, leather_cap: 1 })).toBe('amber_cap')
    const amber = tunicVoxels({ iron_tunic: 1, amber_tunic: 1 })
    expect(amber.map(key)).toEqual(tunicVoxels({ leather_tunic: 1 }).map(key))
    expect(amber.filter((voxel) => voxel.y === 1).every((voxel) => voxel.r - voxel.b > 100)).toBe(true)
    expect(capVoxels({ amber_cap: 1 }).map(key)).toEqual(capVoxels({ leather_cap: 1 }).map(key))
```

In `frontend/src/survival/hud.test.ts`, replace:

```ts
      .toBe('Survived 3 days · caught by a gloomling')
```

with:

```ts
      .toBe('Survived 3 days · caught by a gloomling')
    expect(lifeLine({ kind: 'survival', alive: false, days: 5, cause: 'thornback' }))
      .toBe('Survived 5 days · caught by a thornback')  // L5
    expect(purposeText({ purpose: 'loot_ruin', reflex: null, choosing: false })).toBe('Looting an old ruin')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/frontier.test.ts src/survival/creatures.test.ts src/survival/petGear.test.ts src/survival/hud.test.ts`
Expected: FAIL: `Failed to resolve import "./frontier"`, and the thornback, amber and thornback-cause checks failing

- [ ] **Step 3: The stream's new fields and words**

In `frontend/src/survival/types.ts`, replace:

```ts
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook' | 'store' | 'take' | 'drop' | 'attack' | 'shoot'
```

with:

```ts
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook' | 'store' | 'take' | 'drop' | 'attack' | 'shoot'
  | 'open_chest'  // L5: an old chest in a ruin
```

and replace:

```ts
  burning_at?: number
```

with:

```ts
  burning_at?: number
  /** L5: an elder, born in the frontier or beyond; it glows faintly. Only sent when true. */
  elder?: boolean
}

/** The danger ring Mimo stands in and the rings' centre, home (L5, backend/survival/rings.py ring_view). */
export interface RingView {
  /** 0 home ground, 1 near wilds, 2 far wilds, 3 frontier, 4 deep frontier: the ring's danger. */
  level: number
  name: string
  center: { x: number; z: number }
```

and replace:

```ts
  sheltered?: boolean
```

with:

```ts
  sheltered?: boolean
  /** L5: the danger ring Mimo stands in; null before the tick tended it (an older API sends none). */
  ring?: RingView | null
```

In `frontend/src/survival/hud.ts`, replace:

```ts
const CAUGHT_BY = new Set(['gloomling', 'skitter', 'creature'])
```

with:

```ts
const CAUGHT_BY = new Set(['gloomling', 'skitter', 'creature', 'thornback'])  // L5: the thornback
```

and replace:

```ts
  drop: 'Dropping', attack: 'Attacking', shoot: 'Shooting',
```

with:

```ts
  drop: 'Dropping', attack: 'Attacking', shoot: 'Shooting', open_chest: 'Opening an old chest',
```

and replace:

```ts
  gather_flint: 'Digging for flint', build_pen: 'Building a pen', stock_pen: 'Planting creature seeds',
```

with:

```ts
  gather_flint: 'Digging for flint', build_pen: 'Building a pen', stock_pen: 'Planting creature seeds',
  loot_ruin: 'Looting an old ruin', ward_home: 'Hanging a warding lantern',  // L5
```

In `frontend/src/survival/animation.ts`, replace:

```ts
  fish: 'fish', cook: 'work', store: 'place', take: 'place', drop: 'place', attack: 'swing', shoot: 'aim',
```

with:

```ts
  fish: 'fish', cook: 'work', store: 'place', take: 'place', drop: 'place', attack: 'swing', shoot: 'aim',
  open_chest: 'place',  // L5: lifting the lid of an old chest
```

In `frontend/src/survival/cutaway.ts`, replace:

```ts
  'birch_leaves', 'spruce_leaves', 'birch_log', 'spruce_log', 'fence',  // L3
```

with:

```ts
  'birch_leaves', 'spruce_leaves', 'birch_log', 'spruce_log', 'fence',  // L3
  'warding_lantern',  // L5
```

- [ ] **Step 4: The frontier in the viewer's words and shapes**

Create `frontend/src/survival/frontier.ts`:

```ts
import { MAP_BLOCKS, toMap, type MapOrigin } from './overheadMap'
import type { Creature, RingView } from './types'

/**
 * The frontier in the viewer (L5): the danger ring Mimo stands in on the HUD, the rings shaded faintly
 * on the minimap around home, and the faint glow of an elder hostile. The rings are the server's
 * (backend/survival/rings.py): home ground under 48 blocks from home, the near wilds to 128, the far
 * wilds to 256, the frontier to 512 and the deep frontier beyond.
 */

/** Where each ring past home ground begins, in blocks from home (danger 1 to 4). */
export const RING_STARTS = [48, 128, 256, 512]
/** How strongly a band of danger 1 is shaded; each level adds as much again. */
export const BAND_ALPHA = 0.05
/** The faint violet an elder glows with, and how strongly (0..1). */
export const ELDER_GLOW: [number, number, number] = [0.55, 0.42, 0.95]
export const ELDER_STRENGTH = 0.35

/** "Far wilds · danger 2": the ring Mimo stands in, or null when the server sends none. */
export function ringLine(ring: RingView | null | undefined): string | null {
  return ring ? `${ring.name} · danger ${ring.level}` : null
}

/** How the ring line is drawn: plain at home ground and in the near wilds, amber farther out. */
export function ringTone(ring: RingView | null | undefined): 'calm' | 'wary' {
  return ring && ring.level >= 2 ? 'wary' : 'calm'
}

/** One shaded band of the minimap: its centre and radii in map blocks (from its top-left corner). */
export interface RingBand {
  px: number
  py: number
  inner: number
  /** The deep frontier has no outer edge: the map's diagonal stands in for it. */
  outer: number
  alpha: number
  level: number
}

/** The bands of danger 1 to 4 around home that reach onto the map, faintest first. */
export function ringBands(ring: RingView | null | undefined, origin: MapOrigin): RingBand[] {
  if (!ring) return []
  const { px, py } = toMap(ring.center.x, ring.center.z, origin)
  const far = Math.hypot(Math.max(Math.abs(px), Math.abs(px - MAP_BLOCKS)), Math.max(Math.abs(py), Math.abs(py - MAP_BLOCKS)))
  const near = Math.max(0, Math.hypot(Math.max(0, -px, px - MAP_BLOCKS), Math.max(0, -py, py - MAP_BLOCKS)))
  return RING_STARTS.map((inner, index) => ({
    px, py, inner, outer: RING_STARTS[index + 1] ?? Math.max(far, inner) + 1, alpha: BAND_ALPHA * (index + 1),
    level: index + 1,
  })).filter((band) => band.outer > near && band.inner < far)
}

/** How much a creature glows on its own (0..1): an elder faintly, anything else not at all. */
export function elderGlow(creature: Pick<Creature, 'elder'>): number {
  return creature.elder ? ELDER_STRENGTH : 0
}

/** The emissive color of a creature's material: the red flash of a blow over its own glow. */
export function emissiveOf(flash: number, glow: number): [number, number, number] {
  if (flash > 0) return [0.9 * flash, 0.12 * flash, 0.1 * flash]
  return [ELDER_GLOW[0] * glow, ELDER_GLOW[1] * glow, ELDER_GLOW[2] * glow]
}
```

- [ ] **Step 5: The thornback, drop colours, elders and amber armor**

In `frontend/src/survival/creatures.ts`, replace:

```ts
 * and the skitter, low and wide on eight legs with red eyes. Each model is two voxel lists, the
```

with:

```ts
 * and the skitter, low and wide on eight legs with red eyes, and (L5) the thornback, a low crawler under
a humped shell of thorny plates. Each model is two voxel lists, the
```

and replace:

```ts
const RED_EYE: Color = [226, 70, 62]
```

with:

```ts
const RED_EYE: Color = [226, 70, 62]
const THORN: Color = [96, 112, 74]
const THORN_DARK: Color = [64, 78, 50]
const THORN_TIP: Color = [214, 196, 132]
const AMBER_EYE: Color = [240, 176, 64]
```

and replace:

```ts
  skitter: 0.6 }
const HOPS: Record<string, number> = { rabbit: 0.25, chicken: 0.08, sheep: 0.06, cow: 0.04, fish: 0, gloomling: 0.03,
  skitter: 0.02 }
```

with:

```ts
  skitter: 0.6, thornback: 0.9 }
const HOPS: Record<string, number> = { rabbit: 0.25, chicken: 0.08, sheep: 0.06, cow: 0.04, fish: 0, gloomling: 0.03,
  skitter: 0.02, thornback: 0.01 }
```

and replace:

```ts
/** A plain grey block for a kind this viewer does not know yet. */
```

with:

```ts
/** L5, 9 voxels tall: a low, broad crawler under a humped shell of plates with pale thorns along its
 * ridge, four stubby legs and a blunt head with amber eyes. */
function thornback(): Omit<CreatureModel, 'scale' | 'height' | 'hop'> {
  const body = new Builder().box([-3, 3], [2, 5], [-4, 3], THORN).box([-2, 2], [6, 6], [-3, 2], THORN_DARK)
    .box([0, 0], [7, 8], [-2, -2], THORN_TIP).box([0, 0], [7, 8], [1, 1], THORN_TIP).box([0, 0], [7, 7], [-4, -4], THORN_TIP)
    .pair(3, [6, 6], [-1, -1], THORN_TIP).pair(3, [6, 6], [2, 2], THORN_TIP)
  for (const z of [-3, 2]) body.pair(2, [0, 1], [z, z], THORN_DARK)
  const head = new Builder().box([-2, 2], [2, 4], [4, 6], THORN_DARK).pair(1, [4, 4], [6, 6], AMBER_EYE)
    .box([-1, 1], [2, 2], [7, 7], THORN_TIP)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 3, z: 4 } }
}

/** A plain grey block for a kind this viewer does not know yet. */
```

and replace:

```ts
  rabbit, chicken, sheep, cow, fish, gloomling, skitter,
```

with:

```ts
  rabbit, chicken, sheep, cow, fish, gloomling, skitter, thornback,
```

and replace:

```ts
    gloom_dust: [132, 120, 176], string: [236, 236, 230] } as Record<string, Color>)[item] ?? [180, 180, 180]
```

with:

```ts
    gloom_dust: [132, 120, 176], string: [236, 236, 230],
    // L5: what a hostile born farther out may drop too.
    amber: [232, 156, 44], gold_nugget: [246, 206, 84], diamond: [120, 226, 232], flint: [70, 70, 76],
  } as Record<string, Color>)[item] ?? [180, 180, 180]
```

In `frontend/src/survival/SurvivalCreatures.tsx`, replace:

```tsx
import { puffBits } from './effects'
```

with:

```tsx
import { puffBits } from './effects'
import { elderGlow, emissiveOf } from './frontier'
```

and replace:

```tsx
function flashRed(material: THREE.MeshStandardMaterial | null, flash: number) {
  material?.emissive.setRGB(0.9 * flash, 0.12 * flash, 0.1 * flash)
```

with:

```tsx
/** A blow's red flash, or (L5) an elder's faint glow when there is none. */
function lightUp(material: THREE.MeshStandardMaterial | null, flash: number, glow: number) {
  material?.emissive.setRGB(...emissiveOf(flash, glow))
```

and replace:

```tsx
  const model = creatureModel(creature.kind)
```

with:

```tsx
  const model = creatureModel(creature.kind)
  const glow = elderGlow(creature)
```

and replace:

```tsx
    flashRed(bodyMaterial.current, look.flash)
    flashRed(headMaterial.current, look.flash)
```

with:

```tsx
    lightUp(bodyMaterial.current, look.flash, glow)
    lightUp(headMaterial.current, look.flash, glow)
```

In `frontend/src/survival/petGear.ts`, replace:

```ts
const RIVET: Color = [128, 135, 140]
```

with:

```ts
const RIVET: Color = [128, 135, 140]
const AMBER: Color = [222, 150, 52]  // L5: amber-studded, over the iron's rivets
```

and replace:

```ts
  const [main, trim] = worn === 'iron_tunic' ? [IRON, RIVET] : [LEATHER, STITCH]
```

with:

```ts
  const [main, trim] = worn === 'amber_tunic' ? [AMBER, RIVET] : worn === 'iron_tunic' ? [IRON, RIVET] : [LEATHER, STITCH]
```

and replace:

```ts
  const [main, trim] = worn === 'iron_cap' ? [IRON, RIVET] : [LEATHER, STITCH]
```

with:

```ts
  const [main, trim] = worn === 'amber_cap' ? [AMBER, RIVET] : worn === 'iron_cap' ? [IRON, RIVET] : [LEATHER, STITCH]
```

and replace:

```ts
/** L3: the tunic Mimo wears, iron over leather, or null when it carries neither. */
export function wornTunic(inventory: Record<string, number> | null | undefined): string | null {
  return ['iron_tunic', 'leather_tunic'].find((item) => (inventory?.[item] ?? 0) > 0) ?? null
}

/** L3: the cap Mimo wears, iron over leather, or null when it carries neither. */
export function wornCap(inventory: Record<string, number> | null | undefined): string | null {
  return ['iron_cap', 'leather_cap'].find((item) => (inventory?.[item] ?? 0) > 0) ?? null
```

with:

```ts
/** L3: the tunic Mimo wears, iron over leather (L5: amber over iron), or null when it carries none. */
export function wornTunic(inventory: Record<string, number> | null | undefined): string | null {
  return ['amber_tunic', 'iron_tunic', 'leather_tunic'].find((item) => (inventory?.[item] ?? 0) > 0) ?? null
}

/** L3: the cap Mimo wears, iron over leather (L5: amber over iron), or null when it carries none. */
export function wornCap(inventory: Record<string, number> | null | undefined): string | null {
  return ['amber_cap', 'iron_cap', 'leather_cap'].find((item) => (inventory?.[item] ?? 0) > 0) ?? null
```

- [ ] **Step 6: The ring on the HUD and the rings on the minimap**

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```tsx
} from './hud'
```

with:

```tsx
} from './hud'
import { ringLine, ringTone } from './frontier'
```

and replace:

```tsx
  const home = homeText(state.structures)
```

with:

```tsx
  const home = homeText(state.structures)
  const ring = ringLine(state.ring)
```

and replace:

```tsx
          {home && <p className="mt-0.5 truncate text-xs text-[#54726e]">{home}</p>}
```

with:

```tsx
          {home && <p className="mt-0.5 truncate text-xs text-[#54726e]">{home}</p>}
          {ring && (
            <p className={`mt-0.5 truncate text-xs ${ringTone(state.ring) === 'wary' ? 'font-semibold text-[#a8662c]' : 'text-[#54726e]'}`}
              title="The farther from home, the tougher the creatures and the richer the finds">{ring}</p>
          )}
```

In `frontend/src/survival/Minimap.tsx`, replace:

```tsx
import type { Built, Creature, ExploredPatch, Landmark, MimoAction, Point } from './types'
```

with:

```tsx
import { ringBands, type RingBand } from './frontier'
import type { Built, Creature, ExploredPatch, Landmark, MimoAction, Point, RingView } from './types'
```

and replace:

```tsx
/** A creature (L1): a small cream dot, blue for a fish and (L2) red for a hostile, about 4 CSS pixels
```

with:

```tsx
/** L5: a danger ring around home, shaded faintly, a little darker each level, with a fine edge. */
function drawBand(context: CanvasRenderingContext2D, band: RingBand, u: number): void {
  const x = band.px * MAP_SCALE, y = band.py * MAP_SCALE
  context.beginPath()
  context.arc(x, y, band.outer * MAP_SCALE, 0, Math.PI * 2)
  context.arc(x, y, band.inner * MAP_SCALE, 0, Math.PI * 2, true)
  context.fillStyle = `rgba(199, 70, 58, ${band.alpha})`
  context.fill()
  context.beginPath()
  context.arc(x, y, band.inner * MAP_SCALE, 0, Math.PI * 2)
  context.lineWidth = 0.8 * u
  context.strokeStyle = 'rgba(36, 62, 61, 0.35)'
  context.stroke()
}

/** A creature (L1): a small cream dot, blue for a fish and (L2) red for a hostile, about 4 CSS pixels
```

and replace:

```tsx
export default function Minimap({ store, position, explored, structures, landmarks, creatures, action, name, onHide }: {
```

with:

```tsx
export default function Minimap({ store, position, explored, structures, landmarks, creatures, ring, action, name, onHide }: {
```

and replace:

```tsx
  creatures?: readonly Creature[]
```

with:

```tsx
  creatures?: readonly Creature[]
  /** L5: the danger ring Mimo stands in, and home at its centre: the rings are shaded faintly. */
  ring?: RingView | null
```

and replace:

```tsx
    const u = SIZE / (canvas.current?.clientWidth || SHOWN)
```

with:

```tsx
    const u = SIZE / (canvas.current?.clientWidth || SHOWN)
    for (const band of ringBands(ring, origin)) drawBand(context, band, u)
```

and replace:

```tsx
  }, [cache, position, explored, structures, landmarks, creatures, action])
```

with:

```tsx
  }, [cache, position, explored, structures, landmarks, creatures, ring, action])
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
        landmarks={state.landmarks} creatures={state.creatures} action={state.action} name={state.life.name}
```

with:

```tsx
        landmarks={state.landmarks} creatures={state.creatures} ring={state.ring} action={state.action} name={state.life.name}
```

- [ ] **Step 7: Run the tests, the build and the linter**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  315 passed (315)` (5 new), the build succeeds, eslint prints nothing.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/survival/frontier.ts frontend/src/survival/frontier.test.ts frontend/src/survival/types.ts frontend/src/survival/hud.ts frontend/src/survival/animation.ts frontend/src/survival/cutaway.ts frontend/src/survival/creatures.ts frontend/src/survival/SurvivalCreatures.tsx frontend/src/survival/petGear.ts frontend/src/survival/SurvivalHud.tsx frontend/src/survival/Minimap.tsx frontend/src/survival/SurvivalWorld.tsx frontend/src/survival/creatures.test.ts frontend/src/survival/petGear.test.ts frontend/src/survival/hud.test.ts
git commit -m "feat: the viewer names the ring, shades the rings on the minimap, lights elders, draws the thornback and amber armor" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Manual check on the demo and the README

This task is for the controller. It rebuilds the demo image from the branch and restarts the demo stack on its own scratch volume: `mimo-l3demo-api` (:8011) and `mimo-l3demo-worker`, volume `mimo_l3demo`, at the natural pace (`MIMO_TIME_SCALE=1`, `MIMO_ACTION_SCALE=1`), with Jev's key handed to the worker by `--env-file .env` (Docker reads the file; nobody opens, cats or prints it). The owner's real stack (`pets-api-1`, `pets-mimo-worker-1`) and its volume `pets_mimo_data` are never touched. The owner watches the viewer on :3000 in the Browser pane: do not drive the pane; check the stream through `/api/mimo` and the snippets below, and ask the owner to look at the HUD and the minimap. A game day is an hour at the natural pace. If a check fails, fix the code in the task that owns it, re-run that task's tests, rebuild and repeat the check.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1177 tests` … `OK` (64 on top of the total once L4b is in)

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`, the same with `-p "test_survival_days.py"` and `-p "test_survival_frontier_run.py"`
Expected: `OK` each

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  315 passed (315)` (or 7 on top of the total once L4b is in), the build succeeds, eslint prints nothing.

- [ ] **Step 2: Rebuild the demo on the branch, with Jev**

```bash
docker build -f backend/Dockerfile -t mimo-l3demo .
docker rm -f mimo-l3demo-api mimo-l3demo-worker
docker run -d --name mimo-l3demo-api -p 127.0.0.1:8011:8000 -v mimo_l3demo:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 mimo-l3demo
docker run -d --name mimo-l3demo-worker -v mimo_l3demo:/data --env-file .env \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 -e MIMO_ACTION_SCALE=1 \
  -e MIMO_TICK_SECONDS=1 mimo-l3demo python -m backend.workers.mimo_worker
```

Expected: two container ids. L5 adds no table: the demo world reads as it is. On the worker's first tick the rings are tended: a life from before L5 takes its built home as the centre (or its oldest home place as its birthplace until one stands).

- [ ] **Step 3: Keep a frontier snippet and a nudge ready**

Save these in your scratchpad directory (not in the repo). `frontier.sh` prints the day, phase, purpose, goal and trip; the ring Mimo stands in, how far from home, the deepest ring reached and when it was last out there; the deepest ring it is ready for and what it lacks for the next; its weapons, armor and riches; the hostiles near with their ring, health and elder flag; the ruins it remembers with their ring and whether opened; the warding lanterns it hung; and the latest frontier events, oldest first:

```bash
docker exec -i mimo-l3demo-api python - <<'PY'
import time
import backend.survival.brain  # noqa: F401  (registers every L5 module)
from backend.survival.clock import clock_at, time_scale
from backend.survival.creatures.table import Herd
from backend.survival.memory import places
from backend.survival.registry import LifeRegistry
from backend.survival.rings import distance_home, ready_ring, ring_here, ring_name, short_of
from backend.survival.situation import from_db
from backend.survival.world import SurvivalWorld, read_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
now = time.time()
with world.connect() as db:
    state = read_state(db)
    s = from_db(db, state, now, time_scale())
    brain = state.get("brain") or {}
    clock = clock_at(state["born_at"], now, time_scale())
    print("day", clock["day_number"], clock["phase"], "| purpose", brain.get("purpose"), "| goal",
          (brain.get("goal") or {}).get("name"), "| trip", (brain.get("trip") or {}).get("reason"))
    frontier = state.get("frontier") or {}
    ring = ring_here(state)
    print("ring", ring, ring_name(ring), "|", round(distance_home(state)), "blocks from home | reached",
          frontier.get("reached"), "| far_at", frontier.get("far_at"))
    ready = ready_ring(s)
    print("ready for", ready, ring_name(ready), "| short of the next:", short_of(s, min(ready + 1, 4)))
    inventory = state["inventory"]
    print("gear", {item: inventory[item] for item in sorted(inventory) if item.endswith(("sword", "cap", "tunic"))
                   or item in ("bow", "arrow", "amber", "gold_nugget", "gold_ingot", "diamond", "gloom_dust",
                               "warding_lantern", "lantern")})
    position = state["position"]
    for creature in Herd(db).near(position["x"], position["z"], 48):
        if creature["state"].get("ring") or creature["kind"] == "thornback":
            print("  hostile", creature["kind"], "ring", creature["state"].get("ring"), "health",
                  round(creature["health"], 1), "of", creature["state"].get("most"), "elder" if creature["state"].get("elder") else "")
    for place in places(db, ("ruin",)):
        print("  ruin", (place["x"], place["y"], place["z"]), place["note"], "opened" if place["data"].get("opened") else "closed")
    print("wards", state.get("wards"))
for event in reversed(world.events(400)):
    if event["kind"] in ("found", "loot", "goal", "plan", "fight", "hurt") or "riches" in event["text"] \
            or "ruin" in event["text"] or "warding" in event["text"] or "hurried home" in event["text"]:
        print(event["kind"], "|", event["text"])
PY
```

`gear.sh` is a nudge for when the demo's pet is not geared for the far wilds by the evening of the first day: it gives Mimo what the far wilds take (a stone sword, a leather cap and tunic, a bow and 16 arrows, 4 bread) and nothing more, so its own goal choice and trips do the rest. Note it when you use it.

```bash
docker exec -i mimo-l3demo-api python - <<'PY'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    for item, count in {"stone_sword": 1, "leather_cap": 1, "leather_tunic": 1, "bow": 1, "arrow": 16, "bread": 4}.items():
        state["inventory"][item] = max(state["inventory"].get(item, 0), count)
    write_state(db, state)
print("geared for the far wilds")
PY
```

- [ ] **Step 4: The rings**

Within a minute of the worker's start, run `frontier.sh`. Confirm the ring is 0 or 1 near home, the centre is the built home (`curl -s http://127.0.0.1:8011/api/mimo | python3 -c 'import json,sys; print(json.load(sys.stdin)["ring"])'` prints `{"level": …, "name": …, "center": {"x": …, "z": …}}` with home's x and z), and that the owner sees the ring line under the home line on the HUD ("Home ground · danger 0") and faint rings on the minimap.

- [ ] **Step 5: Ruins**

Over the first game hour, confirm a ruin appears in `frontier.sh` as Mimo walks near one (an event `found | <Name> found an old ruin in the near wilds.` or farther), and, if it lies within 32 blocks and in a ring Mimo is ready for, that loot_ruin follows (`decided to loot an old ruin`), a `loot | <Name> opened an old chest in a ruin: …` event names food, arrows or iron for a near ruin, and the items land in its arms. Ask the owner to look at the ruin in the 3D view (stone-brick walls with mossy cobblestone, a chest in the middle).

- [ ] **Step 6: Riches farther out, only when geared**

While Mimo is not geared (no armor), confirm no event says `seek riches` and `ready for 1`. Once it is (by its own make_gear, or `gear.sh`), confirm at the next goal choice (dawn, or a goal reached) that "Riches farther out" can be set (`set a new goal: riches farther out`, by Jev when more than one goal is open), then `decided to explore to seek riches farther out … "Heading <way> to seek riches farther out. Old ruins stand out there, and I'm ready for the far wilds."`, `found | <Name> reached the far wilds for the first time.`, the ring line turning amber on the HUD ("Far wilds · danger 2"), a ruin found out there, its chest opened with gold nuggets or amber among the loot, and `goal | <Name> reached a goal: riches farther out.` once Mimo is back on home ground. Confirm `frontier.sh`'s hostiles out there show their ring and higher health (a gloomling 34, a skitter 20.4, a thornback 40.8 in the far wilds).

- [ ] **Step 7: Home before dark**

On a day Mimo is out past 128 blocks in the afternoon, note the time of `hurried home before dark`: it comes earlier than the usual window (3 game minutes before dusk) by about 0.45 game seconds a block from home plus a minute, and Mimo is on home ground at nightfall (`frontier.sh` at night: ring 0).

- [ ] **Step 8: Loot put to use**

If Mimo has 4 gloom dust and a lantern (or an iron ingot and a torch), confirm craft_tools makes a warding lantern and `ward_home` hangs it on a corner of home (`decided to hang a warding lantern`), `frontier.sh`'s `wards` lists its cell, and at night hostiles stop short of it (the owner can see them keep off the yard). If Mimo wears iron armor and carries amber, confirm craft_tools makes an amber cap or tunic and the pet model shows it in amber. If neither happens within the check, note it (both depend on what Mimo gathers).

- [ ] **Step 9: A quiet worker**

Confirm `docker logs mimo-l3demo-worker 2>&1 | grep -c "crashed"` prints `0` (or only lines from before the restart), and that the model calls today stay within `MIMO_MAX_DECISIONS_PER_DAY`. Leave the demo running on the new image for the owner.

- [ ] **Step 10: Describe the frontier in the README**

In `README.md`, replace:

```markdown
## Current world rules
```

with:

```markdown
## The frontier

- **Danger rings.** Distance from home sets a ring (`backend/survival/rings.py`): home ground (under 48 blocks, danger 0), the near wilds (48–128, 1), the far wilds (128–256, 2), the frontier (256–512, 3) and the deep frontier (4). Home is the home Mimo built, or where it hatched until one stands, and the rings move with it. Home ground plays as it always did. The HUD names the ring ("Far wilds · danger 2") and the minimap shades the rings faintly around home.
- **Harder enemies farther out.** A hostile born in a ring has 35 % more health a level and hits 1 harder every two levels; from the frontier on some gloomlings and skitters are elders, tougher still and glowing faintly (`creatures/ringed.py`). One more hostile may be about for each level. Out there Mimo runs sooner and stands its ground only when healthier. The thornback (`creatures/thornback.py`) walks the far wilds and beyond, by day too: slow, heavily armoured (a sword does 40 %), and hard-hitting; Mimo shoots it with the bow, or runs.
- **Better loot farther out** (`loot.py`). Hostiles born farther out drop more: gloom dust from the near wilds, gold nuggets and amber from the far wilds, now and then a diamond from the frontier. Mining an ore out there sometimes gives one more. Four gold nuggets make a gold ingot.
- **Ruins.** A small ruin (stone-brick walls with mossy cobblestone, an old chest) stands in some regions, placed by the world seed in the server's and the viewer's world alike. Mimo remembers the ruins it sees, and the first time it opens a chest the server rolls what is inside by the ruin's ring: food, arrows and iron near home, gold, amber and diamonds farther out (`ruins.py`).
- **Loot put to use** (`frontier_gear.py`). A lantern and 4 gloom dust make a warding lantern: it shines like a lantern and no hostile steps within six blocks of it; Mimo hangs up to two on the corners of home. Amber and iron make amber-studded armor, a step past iron (60 % off a blow with both pieces).
- **Risk against reward** (`frontier.py`). Once Mimo is armed and armored for the far wilds, "Riches farther out" is a goal it may take: it goes looking for an old ruin out there ("seek riches farther out"), never into a ring it is not ready for (the frontier takes iron, a bow and arrows), opens the chest and comes home. Far out, it starts home early enough to be back before dark. The model is told the ring Mimo stands in and what it would need for the next.

## Current world rules
```

- [ ] **Step 11: Commit**

```bash
git add README.md
git commit -m "docs: describe the frontier" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (L5 Frontier, the owner's morning note, Decisions, testing) | Where |
|---------------------------------|-------|
| The centre is home: the built home, or the birthplace until a home stands; distance sets a danger ring (the table) | Task 1 (`rings.RINGS`, `tend_frontier`, `center`, `ring_at`; resolution 3) |
| Rings move with home; home ground plays exactly as today | Task 1 (the centre follows the home place; test `test_rings_move_with_the_home_mimo_built`); Tasks 2–4 leave danger 0 untouched (`test_at_home_a_hostile_is_as_it_always_was`, drops and mining tests); resolution 19's near-home measure |
| Hostiles that spawn in a ring: +35 % health a level, +1 damage per two levels | Task 2 (`ringed.toughen`, `darkness.BIRTHS`, the ringed blow in `hostiles.strike_pet`) |
| The spawn cap grows by one per level | Task 2 (`darkness.cap`, `ringed.more_room`) |
| From danger 3, elder gloomlings and skitters: tougher, faintly glowing | Task 2 (`ELDER_CHANCE`, `view`'s `elder`), Task 10 (`elderGlow`, `emissiveOf`, `SurvivalCreatures`) |
| The thornback: danger 2+, slow, heavily armoured, hits hard, arrows its weakness; our own name and design | Task 3 (`thornback.py`, `Kind.shell`, `Kind.daylight`, `SPAWNERS`, `BOW_ONLY`; resolution 7), Task 10 (its model) |
| Drops improve by ring: gloom dust from 1, gold nuggets and amber from 2, rare diamonds from 3 | Task 4 (`loot.ring_drops`, `combat.EXTRA_DROPS`; resolution 8) |
| Mining in a ring: a small chance of an extra ore, rising per level | Task 4 (`loot.extra_ore`, `steps.MINED`; resolution 9) |
| Terrain never depends on home; worldgen a pure function of seed and cell; both ports identical | Task 5 (ruins by seed and region only; the regenerated fixture and both parity suites), the Global Constraints |
| Frontier ruins: stone-brick walls, mossy cobblestone, a chest; sometimes in a region; by worldgen in both ports | Task 5 (`region_ruin`, `ruin_column`, `regionRuin`, `ruinColumn`; resolution 10) |
| The server rolls a ruin chest's loot the first time Mimo opens it, by the ruin's ring; nearer: food, arrows, iron; farther: gold, amber, diamonds | Task 6 (`open_chest`, `ruin_loot`, `LOOT`; resolution 11) |
| Ruins are landmarks exploring can aim for | Task 6 (`notice_ruins`: a `"ruin"` place, a discovery; `loot_ruin`), Task 8 (the riches trip's spots and values aim for ruins) |
| Gloom dust with a lantern: a warding lantern, light 15, hostiles won't step within 6 | Task 7 (`frontier_gear`: the block, `BLOCK_LIGHT`, `acts.BARRIERS`, `state["wards"]`, `ward_home`; resolution 12) |
| Amber with iron: amber-studded armor, a step past iron | Task 7 (the recipes, `harm.ARMOR`, `MORE_ORDERS`; resolution 13), Task 10 (drawn in amber) |
| Diamonds and gold feed L3's tool ladder sooner | Task 4 (diamond drops, gold nuggets into ingots through `toolmaking.POOLED`), Task 6 (gold and diamonds in far ruins) |
| The Situation knows Mimo's ring and each target's | Task 1 (`ring_here`, `ring_at` on the state), Task 8 (`riches_value`, `danger_words`), Task 6 (`loot_facts`) |
| Frontier trips ("seek riches farther out") only when armed, armored and healthy enough for that ring | Task 1 (`READY`, `ready_ring`, `short_of`), Task 8 (`riches_wanted`, `riches_value` never past readiness, `frontier_valid` by gear, `trips.FENCES` for every trip; resolutions 4, 14, 15, 16a), Task 9 (the ungeared check) |
| Flee and fight thresholds account for the ring | Task 2 (`defense.CAUTION`, `flee_below`, `fight_from`; resolution 6), Task 3 (`BOW_ONLY`), Task 8 (the refuge within 128 blocks) |
| Mimo heads home before dark when far out | Task 8 (`purposes.HOMEWARD_LEADS`, `homeward_from`, `head_home_due`, `FAR_HOMES`; resolution 16), Task 9 (home ground at every nightfall) |
| Jev sees each option's ring and its gear readiness | Task 8 (`frontier` in the payload, the riches targets' ring and danger in `explore_reasons`), Task 6 (loot_ruin's facts; resolution 17) |
| The HUD names the ring; the minimap shades the rings; elders glow; the thornback's model; ruins and their chests drawn | Task 10 (`ringLine`, `ringBands`, `Minimap`, `SurvivalHud`, `elderGlow`, the thornback model), Task 5 (ruins in the worldgen port and on the minimap) |
| Tests: a pet near home lives as before | The existing headless runs stay green (Tasks 6, 8, 11), resolution 19's measure (deaths, health, busiest hour, rest) |
| Tests: a geared pet survives a trip to danger 2 and back with better loot | Task 9 (`test_a_geared_pet_goes_to_the_far_wilds_loots_a_ruin_and_is_home_by_nightfall`) |
| Tests: an ungeared pet is never offered a frontier trip | Task 9 (`test_an_ungeared_pet_is_never_offered_riches`), Task 8 (`test_an_ungeared_pet_is_never_offered_riches`) |
| Tests: ruin loot is deterministic from seed and ring | Task 6 (`test_the_same_chest_in_the_same_ring_always_holds_the_same`) |
| Tests: worldgen parity holds for ruins | Task 5 (the fixture's ruins, `FixtureTests`, the TS column test, the minimap test) |
| Decisions: creatures stay cheap; the 20 ms budget | Task 9 (the far-wilds budget check), Task 7 (the wards kept in the state, not read per step), Task 3 (the spawner's window check first) |
| Decisions: no model call inside the tick; crashes logged once; GETs read-only; no migration | Global Constraints; every hook guarded (Tasks 2–8); `/api/mimo`'s `ring` read from the state (Task 1) |

Spec gaps the plan fills or leaves (the controller ledgers them):
- The spec gives no numbers for readiness ("armed, armored and healthy enough"), elder chances, the thornback's stats and spawning, drop chances, the extra ore's chance, ruin density, size and loot, the warding lantern's recipe amounts, amber armor's cuts, or how much earlier Mimo heads home: resolutions 4–16 set them, measured where noted.
- "Gold nuggets": the game had no nugget; 4 make a gold ingot, a recipe of its own, and toolmaking uses it only when it has no gold ore to smelt (resolution 9).
- "A step past iron" for amber armor: separate pieces that do not use up the iron ones (resolution 13), so no older rule asks for iron armor again; Mimo carries both.
- "Hostiles won't step within 6 blocks": a hostile already inside (born before the lantern was hung, or chasing in from the far side) may step outward only; its blow still lands if Mimo stands in reach of it. The rule covers wandering and chasing; animals are not warded.
- The thornback walks by day as well as by night, and light does not keep it away: "walks the far wilds" read as a daytime danger, since hostiles otherwise spawn only in the dark and a day trip would meet none.
- The frontier goal: the spec names frontier trips, not a goal; with L4a every trip serves a goal or a need, so "Riches farther out" is the goal they serve (resolution 14), repeating, open only to a geared pet.
- Trips to the frontier (3) are offered only to a pet ready for it; the rules never send a pet to the deep frontier (4). L4b's expeditions (up to 200 blocks) are not gated by L5's readiness (resolution 22).
- Rings before a home stands centre on the birthplace; a young pet's early trips (L4a gives no reach limit without a home) can take it past 128 blocks of it, into the far wilds, where its hostiles are tougher. Measured: no deaths and no lower health in the four-day runs (resolution 19).
- Ruin chests' leftovers (what did not fit in Mimo's arms) sit in `state["chests"]` beside Mimo's own chests, so the HUD's chest line counts them too.
- Farm work is not a trip, so the fence (resolution 16a) does not cover it. L4a's final fix wave gated farm work to near home (`a439fea`) and reverted the gate (`2daead4`), so a pet may farm where a trip left it: measured on `38dc999` with L5, seed 3's geared pet, ready only for the far wilds, ended a wander near the far wilds' edge and farmed at 257 to 265 blocks, just inside the frontier (lowest health 92, home by every nightfall; its test checks pass). If the controller wants it closed, one line does it: `farming.farm_valid` false while `trips.fenced(s, s.here)`.
- Potions from gloom dust (an aside in L2's outline) are left for later.
- Found while measuring, not L5's: on `0c4a498` without any of this plan, seed 3's pet with a finished cottage by its hatching spot and a sword and food (the frontier runs' ungeared setup) got stuck 87 blocks from home on its first day, gave up going home ("no way there") dozens of times a day and starved on day 4. L4a's final fix wave cured it (on `38dc999` the same pet sleeps at home every night; with L5 its frontier runs pass); Task 9's slow runs still use seeds 8, 11 and 5, and seed 3's runs pass too.

## Dry-run measurements

### The dry run, task by task

The whole plan was dry-run task by task three times as the branch moved. The last full run with every check green is below, on `0c4a498`. On `2daead4` (L4a's final fix wave) it was rebased (three Task 8 anchors moved) and run again: every task applied, and the only failures were timing tests that failed on `2daead4` alone too at that load (load average 17 to 49); the slow sims after Task 6 caught the busiest-hour regression that resolution 11's loot room fixes. On `62a0e5a` (L4a's follow-ups) every task applies unchanged and the tree it makes matches, file for file, the tree the measurements below were taken on (with the regenerated fixture); a last task-by-task run on `62a0e5a` was under way when this plan was committed, and the controller re-runs it after L4b in any case.


On `0c4a498`, every task applied with `apply_plan.py` in order to a `git archive 0c4a498` copy (node_modules linked), with the checks the tasks name after each. Base: backend 1077 tests OK, frontend 308 passed (Task 6 then added 6 tests, before resolution 11 added its seventh). After Task 10 the tree matches, file for file, the branch the code was written and measured on (Task 11 adds the README section).

| Task | Applied | Backend | Frontend, build, lint | Worldgen parity | Slow runs |
|---|---|---|---|---|---|
| 1. Danger rings | yes | 1088 OK | – | – | – |
| 2. Harder enemies | yes | 1096 OK | – | – | – |
| 3. The thornback | yes | 1103 OK | – | – | – |
| 4. Better loot | yes | 1110 OK | – | – | – |
| 5. Ruins in worldgen | yes | 1114 OK | 310 passed, build ok, lint ok | Python 48 tests (27 s) OK; TypeScript 35 passed | – |
| 6. Ruins in the brain | yes | 1120 OK | – | – | sim 6 tests OK (195 s); days 3 tests OK (71 s) |
| 7. Warding lantern, amber armor | yes | 1126 OK | 310 passed, build ok, lint ok | – | – |
| 8. Risk against reward | yes | 1136 OK | – | – | sim 6 tests OK (212 s); days 3 tests OK (55 s) |
| 9. Headless checks | yes | 1139 OK | – | – | – |
| 10. The viewer | yes | 1139 OK | 315 passed, build ok, lint ok | – | – |
| 11. README (the manual check itself is the controller's) | yes | 1139 OK | – | – | – |

After all eleven tasks, in slow mode (`MIMO_SLOW_TESTS=1`, the load average 8 to 10 from other agents' runs): sim 6 tests OK (769 s); days 3 tests OK (187 s); frontier_run 3 tests OK (879 s).

No test failed anywhere in this run.

### Balance at 1x: near-home lives

Four-game-day lives left alone, L4a's sim setup (hatched by `hatch` with the seed, the rules' Chooser or the fake Jev, 15-second steps, nothing handed to the pet), on `2daead4` and on `2daead4` with all of this plan. "Busiest hour" counts every change of purpose in the busiest game hour (the sims' cap is 90). "Rest and sleep" is the share of ticks spent resting or asleep. None of the lives logged an error.

| Seed, picker | Deaths | Lowest health | Busiest hour, all changes | Rest and sleep | Blows taken | Deepest ring (L5) | Ruins seen, chests opened, riches trips (L5) | Goals reached (riches among them) |
|---|---|---|---|---|---|---|---|---|
| 3, rules | 0 → 0 | 100 → 100 | 52 → 59 | 47 % → 46 % | 0 → 0 | 2 | 1, 1, 0 | 4 → 3 (0) |
| 3, fake Jev | 0 → 0 | 90 → 90 | 60 → 60 | 42 % → 43 % | 0 → 0 | 2 | 7, 3, 4 | 8 → 10 (3) |
| 11, rules | 0 → 0 | 100 → 100 | 58 → 58 | 42 % → 43 % | 0 → 0 | 2 | 0, 0, 0 | 3 → 3 (0) |
| 11, fake Jev | 0 → 0 | 100 → 100 | 48 → 48 | 46 % → 46 % | 0 → 0 | 2 | 0, 0, 0 | 5 → 5 (0) |
| 5, rules | 0 → 0 | 100 → 100 | 52 → 53 | 50 % → 46 % | 0 → 0 | 2 | 3, 3, 0 | 6 → 6 (0) |
| 5, fake Jev | 0 → 0 | 98 → 98 | 74 → 59 | 43 % → 46 % | 1 → 1 | 2 | 5, 4, 1 | 12 → 5 (1) |
| 21, rules | 0 → 0 | 96 → 96 | 61 → 61 | 43 % → 43 % | 1 → 1 | 2 | 0, 0, 0 | 3 → 3 (0) |
| 21, fake Jev | 0 → 0 | 100 → 100 | 57 → 57 | 46 % → 46 % | 0 → 0 | 2 | 0, 0, 0 | 14 → 14 (0) |

A pet near home lives as before: no deaths, lowest health 90 to 100 in both columns, the same blows taken (2), the busiest hour 48 to 61 (was 48 to 74), rest and sleep 43 to 46 % (was 42 to 50 %). Since L4a's final fix wave every pet's wander reaches the far wilds (up to 240 blocks), so every life stands in ring 2 at some point, with or without gear. Two of the eight lives gear up on their own, take "Riches farther out" and reach it (seed 3 three times and seed 5 once, both with the fake Jev). Goals reached: 49 against 55. A change to the option list shifts the rules' random stream and the goal each seed happens to settle on (L4a's final fix wave says the same of its hunt check), so single seeds move either way: seed 5's fake-Jev pet reaches 5 goals against 12, seed 3's 10 against 8; the same code before the loot-room change (resolution 11) reached 58 against 55. Over twelve more seeds (1, 2, 4, 6 to 10, 12 to 15, the rules, four game days): 47 goals with L5 against 49; no deaths in either; lowest health 90 and 95; rest and sleep 45 % and 46 %; two of the twelve L5 pets make riches trips and reach the goal. The busiest hour is at most 66 there but for seed 9, at 87 (54 on the base): late on day 3 its pet swings between planting creature seeds, which fails every time ("gave up trying to plant creature seeds (no way there)"), and putting things away, 33 and 36 times in the hour. No L5 code is in that loop (L3's pens and L2's storage: a plant step that failed is tried again as soon as another purpose has run); L5 only changed which seed walks into it (see the notes).

### The frontier runs (Task 9, slow mode)

`MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_frontier_run.py"` on `2daead4` with L5: `Ran 3 tests in 1704s`, `OK` (at a load average of 20 to 49 from other agents' runs; 417 s on a quieter machine), four game days in 5-second steps, a finished cobblestone cottage with a bed by the hatching spot. Seed 3 is not in the test (resolution 18) and was run the same way on its own:

| Seed | Pet | Died | Lowest health | Deepest ring | At nightfall (ring, days 1–4) | Chests opened (loot) | Riches trips, goals reached | Riches while not geared |
|---|---|---|---|---|---|---|---|---|
| 8 | geared | no | 93 | 2 | 0, 0, 0, 0 | 3 (gold nuggets, iron ingots, arrows, bread) | 4, 2 | 0 |
| 11 | geared | no | 92 | 2 | 0, 0, 0, 0 | 1 (gold nuggets, amber, arrows, bread) | 8, 1 | 0 |
| 5 | geared | no | 100 | 2 | 0, 0, 0, 0 | 4 (gold nuggets, iron ingots, coal, arrows, bread) | 1, 1 | 0 |
| 3 | geared | no | 92 | 3 | 0, 0, 0, 0 | 6 or more (gold nuggets, amber, iron ingots, arrows, bread) | 2, 2 | 0 |
| 8 | ungeared | no | 86 | 2 | 0, 0, 0, 0 | 1 (bread) | 0, 0 | 0 |
| 11 | ungeared | no | 100 | 2 | 0, 0, 0, 0 | 0 | 3, 0 | 0 |
| 5 | ungeared | no | 100 | 2 | 0, 0, 0, 0 | 3 (iron, coal, bread, arrows) | 0, 0 | 0 |
| 3 | ungeared | no | 100 | 2 | 0, 0, 0, 0 | 1 (iron, bread, arrows) | 0, 0 | 0 |

The ungeared pets reach the far wilds on their own wanders (L4a's reach); seed 11's makes its own leather armor and then goes out for riches as a geared pet should. No riches trip ran while a pet was not armed and armored. Seed 3's geared pet, ready only for the far wilds, stood in the frontier (ring 3): it ended a wander near the far wilds' edge and farmed there, at 257 to 265 blocks (farm work is not a trip, so the fence does not hold it; see the spec gaps). Default mode (seed 8, one game day, 15-second steps) takes about half a minute.

### The slow sims' busiest hour

The dry run's slow `test_survival_sim.py` after Task 6 failed once: seed 5's fake-Jev pet changed purpose 94 times in its busiest game hour, over the cap of 90 (69 on `2daead4`). Resolution 11's loot room brought it to 88; the other seeds and pickers are at 63 to 76 (slow mode, two game days in 5-second steps, measured one by one with the sims' own `run_life`). 88 leaves little room: the controller's re-run after L4b should look at this number first.

### Budget

- The far-wilds check (Task 9): a geared pet 150 blocks from its birthplace early in the first night, a toughened gloomling, skitter and thornback beside it, the dark free to spawn: the creature hook's best mean over five 60-game-second transactions was 3 to 12 ms across runs (limit 20 ms).
- L2's darkness budget test (`test_a_gloomling_beside_mimo_at_night_still_costs_little_a_slice`) is sensitive to machine load: run alone, three times each and in turn at a load average of 8 to 10, its best mean was 6.9 to 7.3 ms on `0c4a498` and 7.2 to 7.5 ms with all of L5 (limit 20 ms); L4a's final fix wave did not touch the creatures. In one earlier dry run, with the load average near 18 from other agents' runs, it read 20.4 ms after Tasks 7 and 8 while the base read 17 to 35 ms at the same time; it passes when run again.

### Ruins

Around the hatching spots of `hatch(random.Random(seed))` for seeds 1 to 24, 23 % of the 96-block regions within five regions each way hold a ruin (`RUIN_ODDS` 2, then the land's checks: dry, flat within 2, no pool, cave mouth, tree or rock). Each spot has 2 to 11 ruins within 240 blocks, at least one of them in the far wilds (1 to 7); the nearest lies 15 to 212 blocks away. In the balance runs seed 21's pets, whose nearest ruin lies 192 blocks off, see none in four days; seed 11's (212 blocks) see one only with the fake Jev. The fixture gains the ruins' cells (43478 cells, was 39590).

### Notes for the controller

- Timing tests fail under heavy load, on `2daead4` alone as well: in the final dry run (load average 17 to 49 from other agents' runs) the base failed L2's darkness budget and the viewer's worldgen column test (5 s timeout), and some tasks also L2's `test_creatures_cost_well_under_twenty_milliseconds_a_slice_while_fleeing_two_hostiles`; `test_survival_creature_api` has failed the same way before. They pass alone on a quiet machine. If one fails in the controller's run, run it alone before looking further.
- On `0c4a498` alone, seed 3's pet with a finished cottage by its hatching spot and a sword and food (the ungeared setup of the frontier runs, no L5) was stuck 87 blocks from home from its first day, logged "gave up trying to go home (no way there)" dozens of times a day and starved on day 4. L4a's final fix wave cured it: on `38dc999` the same pet sleeps at home every night (5 blocks from home at every nightfall, lowest hunger 37).
- A loop outside L5, seen once in the balance runs (seed 9, the rules, day 3): plant_seeds fails with "no way there", put things away runs, plant_seeds is chosen again and fails again, 33 times in an hour. The step's failure is not remembered across the purpose in between (as `near_failure` now guards build_storage since L4a's fix round 2). Worth its own fix in L3's pens.
