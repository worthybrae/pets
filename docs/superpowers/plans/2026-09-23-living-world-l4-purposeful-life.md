# Living World L4a: Purposeful Life and a Curious Pet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Mimo's days a purpose: a registry of goals that last days (a home of its own, iron tools, armor, a full larder, a safe yard, a bigger stone home, a herd, the land mapped), each with a why, a validity check, progress from 0 to 1 read from Mimo's state and memory, the purposes that advance it and a mood reward; Jev choosing the goal at dawn or when one is reached or given up, from a small offered set with facts, and the rules picker when Jev is not there; purposes that advance the goal scoring 15 more while the rest step aside unless they meet a need, so rest and explore come only when nothing advances the goal or a need; exploring that always has a reason from the goal or a need (look for iron for the pickaxe, trees for wood, food, leather for armor, a creature seed for a pen, a site for a bigger home, the land to map), heads where the land likely holds it, remembers what it finds and ends early on a find, and says what for in its thought, its event, the HUD and the Jev payload; curiosity, an inner value that grows on known ground and falls with each discovery, lifting a restless pet's trips, sending a pet with nothing to do off to see something new rather than sit, and setting time aside to wander once its needs are met; goals that lift the gates that would stall them (iron armor before any blow, a single known diamond); discovery goals always on offer once home stands (new lands, a new creature, a cave, water, the far hills), pulling harder the more curious Mimo is; a day plan at dawn; a notable event and a mood boost when a goal is reached; the goal, the trip and curiosity in the model payload and in `/api/mimo`; the goal line with a progress bar, the day plan, the trip and a curiosity bar on the HUD, and the goals reached on the memorial; and headless checks that aimless changes of purpose fall well below today's, that no explore goes without a reason, and that once home stands every game day brings a discovery and Mimo rests or sleeps at most half the time. The knowledge journal and expeditions are L4b's (resolution 18).

**Architecture:** Everything registers into a registry. `backend/survival/goals.py` is the goal registry and its rules: milestones and progress, the brain's goal state, how purposes follow the goal (`toward`, `boosted`, and `ADVANCES` for a purpose that advances a goal only as it would be done now), the tick's side (`tend_goal`, called from `brain.notice_step`: progress, the day plan, a goal reached or given up) and the chooser's side (`offers`). `pickers.steer` applies the goal to the options, and `choosing.Chooser` answers a goal choice before a purpose choice, with Jev (a `"goal"` question in the same call shape) or the rules. `backend/survival/trips.py` is the registry of reasons to explore and the trip: a reason says why Mimo wants something, how likely the land around a spot holds it (terrain only, so the same land always scores the same), the spots worth heading for, what Mimo sees after each walk, and the work to do at each stop; explore goes only for a reason, to its best target, and the chooser stores the trip, with Jev picking the reason in the same call (an `"explore_reason"` question) or the rules. The goals and reasons themselves register from new modules: `scouting.py` (the needs: trees and food), `life_goals.py` (first shelter, iron tools, diamond tools, armor, a safe yard, a herd, the land mapped, and the trips for iron, leather, a creature seed and the map), `homes.py` (a bigger stone home, its `improve_home` purpose and the trip for a site), `larder.py` (a full larder, its `stock_larder` purpose and a hook in `foraging.food_need`) and `discovery.py` (the discovery goals and their trips). `curiosity.py` keeps the new inner value: the tick grows it and lowers it with each discovery (the first meeting with a biome, a kind of block or creature, a place, new ground), and it hooks into the goals (`URGES`, `PLAN_EXTRAS`) and the trips (`LIFTS`, `FINDS`, the "wander" trip). A milestone whose purposes are not registered, or whose items have no recipe yet, is skipped, so goals grow with the purposes other milestones add. The viewer gets a pure `goals.ts` module and draws the goal line, the day plan, the trip, the curiosity bar and the memorial's goals reached.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-living-world-design.md` (L4: the milestone table's row, the whole "L4 Purposeful life" outline, "Owner input, 2026-09-24 morning", "L4 addition: purposeful exploring", "L4 addition: a curious pet" (its curiosity drive, discovery goals, the day plan's time for curiosity, the viewer's curiosity bar and the discovery check; its journal and expeditions are L4b's), the Decisions' "Purposeful life" and "Cost", and "Error handling and testing"; "L5 Frontier" only for the hook resolution 17 leaves). It follows the shape of the L1 and L2 plans (`docs/superpowers/plans/2026-09-23-living-world-l1-animals.md`, `...-l2-danger.md`). The code on branch `worthy/23_09_2026/survival_core` at `bd765f2` is the "old" text every task edits: L2 with its final fix wave and all of L3 with its final fix wave (resolution 1). The dry run applied every task to a `git archive` of that commit.

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls: a fake Jev stands in where a test needs one. The rules picker's random nudge comes from the chooser's seeded `rng`; nothing reads `random` or the clock.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments, no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components. No stylesheet changes: the HUD uses Tailwind classes inline, as it does now.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. Read-only GETs never write. L4 adds no table and no column: the goal and the trip live in Mimo's state JSON (`state["brain"]["goal"]`, `goal_due`, `goal_penalties`, `goal_idle_at`, `trip`), the goals reached in `memory_knowledge` (fact `"goal"`), and the landmarks a trip finds in `memory_places` (kinds `grove`, `pasture`, `cave` and `site`, beside the `food`, `water` and `ore` places it also remembers), curiosity in `state["brain"]["curiosity"]`, and the biomes, kinds of block and kinds of creature Mimo met in `memory_knowledge` (facts `"biome"`, `"block"`, `"creature"`).
- **No model call inside the tick.** The tick reads progress, writes the day plan, reaches or gives up goals, picks an explore reason, scores its targets and looks after each walk, and grows and lowers curiosity, all by rules; goal choices and Jev's pick of a reason are answered in the worker's Chooser, outside the tick transaction, like purpose choices. Validity checks, milestone shares, reasons' wants, values and scores, facts and scores never write; a trip's look writes only the places it finds.
- A crashing milestone share, goal validity check, goal score, goal check, `ADVANCES` check, urge, day-plan extra, lift, find hook, any part of a reason (want, value, spots, look, work, score) or curiosity's tending never stops a tick or the worker: each is logged once (`once.log_once`) and counts as nothing.
- Values from the spec (L4 outline and Decisions): goals are a registry with a name, a why, validity, progress (0 to 1, from state and memory), the purposes that advance them and completion; examples: first shelter, then a better home (a bigger tier, stone walls); iron tools, then armor; a full larder (a chest with food); a safe yard (torches, a door, a fence); a herd (creature seeds and a pen); map the land (explore memory). Jev picks a goal at dawn, or when one completes or fails, from a small offered set with facts; the rules picker is the fallback; a goal lasts days, not minutes. Purposes that advance the active goal get +15 score; purposes that do not are capped in the leisure band unless they meet a need. A day plan at dawn lists the goal's next steps and is shown in the HUD. Completing a goal is a notable event with a mood boost. The HUD shows the goal and its progress bar; the memorial lists the goals reached; the Jev payload carries the goal context. Rest and explore are chosen only when nothing advances the goal or a need. Goal picks follow the same cost rules as purpose picks (the daily cap and the hourly budget; the owner raised Jev's hourly budget from the spec's 8 to `MIMO_JEV_CALLS_PER_HOUR`, default 60, since Jev is cheap).
- Values from the owner's morning note (spec, "L4 addition: purposeful exploring"): every trip has a reason from the active goal or a current need, never just the least-explored ground; targets are scored by how likely they hold what the reason needs, from explore memory, remembered places and landmarks, and the terrain's biome and height; a trip ends early on a find, which is remembered as a place or landmark, and the next purpose follows up; the reason shows in the thought, the event, the HUD and the Jev payload; the rules pick the reason when Jev is not used; a headless check counts explores without a reason, and that count must be 0.
- Values from the owner's day-17 note (spec, "L4 addition: a curious pet"): curiosity from 0 to 100 grows each game hour on known ground, faster once needs are met, and falls with each discovery (a new patch, biome, kind of block, kind of creature or landmark); high curiosity lifts exploring into the work band and steers goal choice toward discovery goals; the Jev payload carries it as a feeling; discovery goals are always on offer; once needs are met the day plan sets time aside for curiosity; a curiosity bar sits with the vitals; once a home exists, each game day in a headless run brings at least one discovery.
- L3's names, used by name and present at the base (L3's Tasks 7–12): purposes `build_pen` and `stock_pen`, items `fence`, `diamond_pickaxe`, `iron_cap` and `iron_tunic`, and `creatures.seeds.SEED` (`creature_seed`), which `life_goals.py` imports. If L3's last tasks rename any, only the strings in `backend/survival/life_goals.py` change (resolution 3).
- `MIMO_TIME_SCALE` and `MIMO_ACTION_SCALE` (both default 1) are for manual runs only. L4 adds no settings.
- Never run `docker` or `docker compose` in Tasks 1–12. Task 13 is the controller's manual check on the demo stack (`mimo-m5demo-api` on :8011 and `mimo-m5demo-worker`, volume `mimo_m5demo`); never touch, mount or migrate the owner's real volume `pets_mimo_data` or the real stack (`pets-api-1`, `pets-mimo-worker-1`). Never print `TYPESAFE_API_KEY` or any other key.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (937 pass at `bd765f2`)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_goals.py" -v`
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` (a few minutes) and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
- Frontend tests: `cd frontend && npm test` (296 pass at `bd765f2`)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint src/survival src/engine` (prints nothing when clean)

Each task says how many tests it adds. If the real starting totals differ, expect the same increases on top of them.

Transcription: every edit is a fenced block, either a whole new file ("Create `path`:"), a "replace: … with: …" pair in a named file ("In `path`, replace:", then "and replace:" for more pairs in the same file), a whole function replaced by name ("Then replace the whole `name` function with:", in the file named last), or a block added at the end of a file ("In `path`, append:"; such a block starts with the two blank lines that separate it from what is there). Old texts are kept short, so a task still applies when a neighbouring line changes. The dry run applied each task with the controller's apply script (`.superpowers/sdd/2026-09-23-living-world-l2-danger/apply_plan.py`) to a `git archive` copy of `bd765f2` and ran the task's checks after each one.

## Plan-level resolutions

The spec gives L4 as an outline. These are the details; every task follows them and the controller ledgers them.

1. **Base.** `bd765f2`: L2 with its final fix wave, and all of L3: Tasks 1–15 (new blocks and biomes, bigger caves and cave entrances, 2-wide passages, gold and diamond tools, iron armor and lanterns, ladders and fences, flint, creature seeds, pens, L2's review notes, the viewer's new blocks and purposes, its README section "A bigger world") with their fix waves and L3's final fix wave (a pet stranded in a cave pocket digs out and hunts no cave animals, logs and planks kept as one pool of any wood, a new shelter puts out only the animals in its own cells, `tame` in the creature view, lighter worldgen caches). L3 raised `PURPOSE_EVENTS_PER_HOUR` for slow mode, added its purposes' words under `make_gear` in `hud.ts`, the pen to `Built` and `tame` to `Creature` in `types.ts`, and made the headless runs' trap check `escape.way_out`; this plan's edits keep off those lines. The first plan for L4 (`fd89158`) was applied and checked at `983e2aa` and at `e22a29d`; this one replaces it, adds purposeful exploring, curiosity and discovery goals, the controller's L3 review (resolutions 21 and 22), and was dry-run at `bd765f2`, with every headless number measured there. If more lands on the branch first, the controller re-runs this plan's dry run on it and re-measures the headless numbers (resolutions 13, 14 and 22).
2. **Registries, not rewrites.** New modules: `goals.py` (the goal registry and its rules), `trips.py` (the registry of reasons to explore and the trip), `scouting.py` (the needs' reasons), `life_goals.py`, `homes.py` and `larder.py` (goals, their purposes and their trips, registered on import), and `frontend/src/survival/goals.ts`. The brain imports the goal and reason modules as it imports purpose modules; `snapshot.py` imports the brain so the API knows every goal's title. Existing modules gain small hooks: `pickers.steer` and `Option.reasons`, `goals.ADVANCES`, `foraging.MORE_FOOD`, `hunting.HUNT_FOR`, `brain.notice_step` calling `goals.tend_goal`, `brain.observe_step` calling `trips.look_after`, the explore purpose's four functions going through `trips`, and the Chooser's goal choice, stored trip and reason question.
3. **Goals name purposes.** A goal is a list of milestones: words, a share from 0 to 1 (a function of the Situation) and the purposes that work toward it, plus the items it needs a recipe for. A milestone none of whose purposes is registered, or with an item that has no recipe, is skipped: it counts toward nothing and the day plan leaves it out; a goal with no milestone left is never offered. At the base L3's `build_pen`, `stock_pen`, `fence`, `diamond_pickaxe`, `iron_cap` and `iron_tunic` exist, so the herd, diamond tools and armor's iron step count; the yard's fence waits for a `build_fence` purpose, which no plan adds yet. Progress is the mean of the counted milestones' shares; a goal is complete when all are whole, and reached once in a life (remembered in `memory_knowledge` as fact `"goal"`).
4. **The goals.** first_shelter, "A home of its own" (blocks for the walls, the walls and roof, a bed inside), before every other goal. iron_tools, "Iron tools" (a wooden and a stone pickaxe, iron ore found, 3 iron ore mined, an iron pickaxe: mine_ore only wants the iron a pickaxe takes, so the iron sword is not part of it). better_tools, "Diamond tools", after iron tools. armor_up, "Armor up", after iron tools, as the spec orders them (5 leather, a leather cap, a leather tunic, iron armor). full_larder, "A full larder" (a chest at home; 60 hunger of food in the chests, a day's worth). safe_yard, "A safe yard" (the home's corner torches, its door; a fence with a `build_fence` purpose). better_home, "A bigger stone home" (a site for it, the blocks, the walls and roof of a bigger tier with cobblestone walls, moving in). herd, "A herd of its own" (L3's pen, 3 animals in it). map_land, "Map the land" (60 % of the dry 8x8 patches within 64 blocks of home walked). The milestones a trip can serve name `explore` too (resolution 15). Each goal has a rules score from traits and needs (resolution 7) and a thought.
5. **Where the goal lives.** `state["brain"]["goal"]`: name, since, picker, progress, best progress and when it last rose, the day plan and when it was last checked; `goal_due` is a goal choice waiting (its id from the brain's `next_id`, as purpose choices have), `goal_penalties` the goals given up lately, `goal_idle_at` the last time no goal was open. Worlds from before L4 get these on first use (`goals.goal_state`).
6. **The tick's side** (`goals.tend_goal`, after every vitals step, from `brain.notice_step`): with no goal it asks for one at once, then every 600 game seconds while none is open, and at dawn. With a goal it reads the progress at most once a game minute (and at dawn): a complete goal is reached (a notable `goal` event, "Pip reached a goal: iron tools.", +15 mood, the goal remembered, a new goal and a new purpose asked for); a goal no longer open is given up, and so is one that has made no progress for a third of a game day of daylight while nothing that advances it would be on offer (`idle`: measured, a goal stuck like that, a safe yard with no coal for torches, otherwise held Mimo idle for a day and a half). At dawn it writes the day plan (the next 3 milestones, a routine `plan` event, "Pip's plan for today: find iron ore, mine 3 iron ore and make an iron pickaxe.") and asks for a goal choice; a goal whose progress has not risen for a game day is given up at dawn instead (a routine `plan` event) and not offered for a game day. A new goal gets its day plan at the next check. The plan's steps are ticked off as their milestones fill.
7. **Choosing a goal** (`goals.offers`, `choosing.prepare_goal`, `store_goal`). The offered set is the open goals not given up lately, best first by the rules score, at most 4 with the current goal among them; each carries facts ("40% done; next: find iron ore, mine 3 iron ore"). The rules score is the goal's own score, +20 when a purpose that advances it would be on offer now were it Mimo's goal (`workable`: improve_home, stock_larder and the goals' trips are offered only for their own goal), +100 for the current goal (it only goes by being reached or given up, so "a goal lasts days"). Jev chooses when it is configured, more than one goal is on offer and neither the daily cap nor its hourly budget is spent: the same call shape with a `"goal"` question and its own instructions ("…keep the current one unless it is stuck or another matters much more now…"). The call counts toward the daily cap and Jev's hourly budget, but it does not start the 60-second gap before the next model call, so the purpose choice that follows may still go to Jev. Luna never chooses goals. A rules answer is stored at once and the purpose choice follows in the same poll. A new goal is a routine `plan` event ("Pip set a new goal: iron tools. …") and asks for a new purpose; keeping the goal logs nothing.
8. **Purposes follow the goal** (`pickers.steer`). The options on offer that advance the goal are marked with its title and score +15, but not past 80 (the survival band stays first) and not late in the day or at night (going home and sleep come first). A purpose advances a goal when a milestone still to do names it, unless it has a check of its own in `goals.ADVANCES`: explore advances a goal only when a trip on offer serves it (a reason lists the goals it serves). While any option advances the goal or meets a need (a survival or needs purpose, `goals.NEEDS`, scoring 50 or more), only those are offered: the others, rest and explore among them, would be capped in the leisure band, and leaving them out also keeps Jev's pick on the goal. When nothing does, every option keeps its own score, as before. When nothing for the goal itself is on offer (the torches wait for the evening, a hunt for hides for its gap), the best other open goal that has something on offer is worked toward meanwhile, so Mimo does not idle while its goal waits.
9. **Jev and the goal.** The purpose question's instructions say to work toward the goal, the choices that do say "It works toward the goal: Iron tools.", and the payload gains `goal` (title, why, progress, the next steps, days on it); the goal question's payload adds `goals_reached`. With a goal, a purpose that ended in the ordinary way (`plan_done`, `idle`, `reflex_ended`) is chosen again by the rules picker, like the short purposes are today: Jev speaks at dawn, dusk, discoveries (a trip's find is one), new goals, failures, vital crossings and the like, and the goal carries the day between them. A purpose event says which goal it works toward ("Pip decided to gather stone, toward iron tools.").
10. **Goals that need a purpose of their own.** A bigger stone home needs `improve_home` (it designs a bigger tier with cobblestone walls near home, or at a site a trip found, and starts it once Mimo carries half the blocks; `build_shelter` goes on with the newest shelter, so it builds the rest and furnishes it, and home moves in when the roof is on). A full larder needs `stock_larder` (the chest in the shelter when there is none, then the food beyond a day's worth stored in it) and `larder.more_food`: while the larder is the goal and Mimo is not hungry, it wants up to 40 hunger more food on hand, so forage, fish, hunt and farm gather past a day's worth. Armor adds `life_goals.hides_wanted` to `hunting.HUNT_FOR`: while armor is the goal and leather is short, Mimo hunts though fed, at most once a sixth of a game day (measured: without the gap it killed a herd in eight minutes). Each of these, and each goal's trip, is offered only while its goal is Mimo's goal: a pet does not start a second house for the fun of it.
11. **What the viewer is told.** `/api/mimo` gains `goal`: name, title, why, progress, the day plan (`[{text, done}]`), who chose it and when (null without one); and `trip`: reason, words, why, direction and what it found, while Mimo explores (null otherwise). Life summaries and details (the memorial, `/api/lives/{id}`) gain `goals_reached`: `[{name, title, day}]`, none for the legacy life.
12. **Viewer.** Under the purpose line the HUD shows "Goal: Iron tools" with its percent and a progress bar, and up to 3 steps of today's plan, done ones ticked and struck through; the goal line's tooltip is the why and who chose it. While Mimo explores, the purpose line says what for ("Exploring to look for iron") and a line under it which way and why ("Heading north: my pickaxe needs it") or what it found. The memorial lists "Goals reached" with their day, and leaves the goal events out of its notable events so each goal shows once. The two new purposes get words ("Building a bigger home", "Stocking the larder").
13. **The headless runs.** Goals fill the day with work, and a trip that finds what it went for is a change to explore and a change to the purpose that follows up: measured over the headless runs' seeds and both pickers, changes of purpose rise (on average from 36.0 to 49.5 a game hour, and from 33.3 to 55.4 in slow mode; the busiest hour reached 55, and 75 in slow mode, against the flood guard's 52, and 55 in slow mode) while the ones toward no goal fall (at most 14 in an hour, and 31 in slow mode). So the flood guard, `PURPOSE_EVENTS_PER_HOUR`, now counts the changes that work toward no goal (an event without ", toward"), at its old value, and all changes get a cap of their own, `ALL_EVENTS_PER_HOUR = 90`. The days runs' home test allows a second home (the bigger one) and checks home is the newest one built.
14. **Fewer aimless loops** (Task 11). Changes of purpose to rest or explore that work toward no goal, per game hour, over every seed and both pickers: 4.5 before L4 (4.56 in slow mode), measured on `bd765f2`; with L4 0.0 (0.81). An explore that serves a need but no goal still counts, so the measure is the one taken before L4. The check requires at most three quarters of the old rate. The runs are made once and shared by the headless tests. The first plan's rates, on L2 and on L3's first tasks, are history now (resolution 1). If more of L3 lands before this plan runs, the controller re-measures the rate before L4 on that code (`git archive` of that commit, the same runs), sets `AIMLESS_BEFORE_GOALS` to it, and, should L4 no longer cut it by a quarter, looks at which goals stall (the `plan` events "set a goal aside") and which trips run toward no goal (`decided to explore to …` without ", toward") before touching the check.
15. **Every trip has a reason** (Tasks 4–6, the owner's morning note). A reason (`trips.Reason`) has a name, words ("look for iron"), `wanted(s)` (why, in words, or None), `value(s, x, z)` (how likely the land around a column holds it, 0 to 1, and what is there), `spots(s)` (columns to head for as they are), `look(s, context)` (after a walk: what Mimo finds, remembered as a place or landmark, and whether it is what the trip was for), `work(s)` (steps at each stop), the goals it serves, its score and its reach from home (60 blocks, as every trip; L5 will add longer ones). explore is offered only while some reason is wanted and has a target, and scores its best reason's score plus what lifts every trip (`trips.LIFTS`: curiosity, resolution 19). Targets are the reason's spots and the dry columns at 16 headings 32, 48 and 64 blocks away where its value is above 0, scored 3 × likelihood + 1 × how new the land around is (explore memory) + the old small bonus for distance and seeded jitter; the old safety rules hold (never in water, never near a step that just failed, never in the patch Mimo stands in or one visited less than a game day ago, spots excepted, and never beyond the reach from home unless nearer than Mimo is now). The rules pick the reason: one that serves Mimo's goal first, then the higher score. A trip is up to three walks, each whole, with the reason's work at each stop after the first; after each walk (`brain.observe_step` → `trips.look_after`) Mimo looks around, logs a find ("Pip found birch trees.": a notable `found` event when the place is new to it, else a routine `explore` one), and a find that is what it came for ends the trip and asks for a new choice (a discovery), so the purpose that follows up comes next. The reasons: trees ("look for trees": under 3 logs' worth of wood, or a started shelter waiting for blocks, and no tree within 24 blocks; trees within 12 blocks of a spot, 3 is sure; remembered groves; a tree in sight is the find, a `grove` landmark; 45 plus a fifth of curiosity, as explore scored with no tree in sight before; serves first shelter, iron tools and the bigger home), food ("look for food": less than half a day's food carried and no food work on offer; wild berries and mushrooms, then water, then grazing land; food work on offer again is the find; scores like food work; serves the larder), iron ("look for iron": mine_ore wants iron Mimo can mine and it remembers none within 48 blocks; cave mouths and sinkholes not looked into are sure, rocky outcrops likely, hills and mountain rock 0.3; openings within 64 blocks are spots; after a walk the openings within 16 blocks are looked into and remembered as `cave` landmarks, with the ore in their walls that Mimo could mine from the floor or the rim; iron among it is the find; 45 plus a tenth of curiosity; serves iron tools and armor), hides ("look for leather": armor the goal, hides wanted, no animal in range; cow land is sure, rabbit ground 0.4; remembered pastures; an animal in range is the find, a `pasture` landmark; serves armor), seed ("look for a creature seed": the herd the goal, no seed carried or in a chest and neither pen purpose on offer; tall grass, 12 within 8 blocks is sure; up to 10 tall grass broken at each stop, a seed dropping 1 in 60; a seed carried is the find; serves the herd), site ("scout for a building site": the bigger home the goal and no site near home fits; flat dry ground within 32 blocks of home; a site that fits where Mimo stands is the find, a `site` landmark the bigger home's design then uses; serves the bigger home) and map ("map the land": mapping the goal and not done; the least-explored spot, `exploring.explore_target`, the one reason that heads for new land as such; serves the map).
16. **The reason in the chooser, the payload and the viewer.** explore's option carries the offered reasons (`Option.reasons`, at most 4, the rules' pick first). Choosing explore stores the trip in the brain (`state["brain"]["trip"]`: reason, words, why, direction, since, picker, found, done; it stays until the next trip, so a walk still under way when another purpose is chosen keeps its reason, and the payload and `/api/mimo` show it only while Mimo explores), and its event and thought say what for: `Pip decided to explore to look for iron, toward iron tools. "Heading north to look for iron. My pickaxe needs it."`. When Jev answers a purpose choice and explore is offered for more than one reason, the same call asks a second question, `"explore_reason"`, whose choices are the reasons with why and where ("Go and look for iron: my pickaxe needs it. Now: north 40 blocks, a cave mouth; …"); a Jev pick of explore goes for Jev's reason, any other pick goes for the rules' (no extra call). The tick keeps to the stored trip, or picks by the rules when there is none, it is done, or its reason is no longer wanted as the trip starts; so no explore step runs without a reason. The payload gains `explore_reasons` (each reason with why and up to 3 directions with blocks and what lies there) and `trip`; the facts of explore's option name the same.
17. **L5's hook, not built.** L5 ("Frontier") comes after L4. `trips.Reason.reach` is where it hooks in: "seek riches farther out" will be a reason with a longer reach, offered only to a pet geared for the ring it leads into, with its own risk rules. L4 registers no such reason and changes nothing about danger or loot.
18. **The split.** The owner's day-17 note made L4 too big for one plan, so it splits as the spec says: this plan, L4a, covers goals, the day plan, purposeful exploring, curiosity and discovery goals (13 tasks); L4b (`docs/superpowers/plans/2026-09-23-living-world-l4b-curious-mind.md`) covers the knowledge journal (investigating first meetings, the facts they teach, knowledge that unlocks behaviour, Jev's journal lines, the journal panel) and expeditions (packing, travelling past the explored range for a day or two, camping, outposts, the HUD's expedition line), on top of this plan.
19. **Curiosity** (Task 8). `state["brain"]["curiosity"]` = {value 0–100, when it was last tended, the last discovery, the last one more than new ground, the discoveries so far, when the creatures near were last looked over}; a newborn starts at 40. It grows 2 points an hour of the day's clock (a 24th of a game day, as the HUD counts; `triggers.HOUR` is a whole game day of 3,600 game seconds), 1.5 times that once needs are met (hunger 60, energy 50, warmth 50 and health 60 or more, with a home it built). Discoveries lower it: new ground 3 (once a step), a new biome 30 (a notable `found` event, "Pip saw the taiga for the first time."), a new kind of block dug 6, a new kind of creature within 24 blocks 20 ("Pip met its first sheep.", looked over once a game minute), a new place 10 (each `found` or `discovered` event of the step, and each new place a trip finds). The biome it hatched in is known silently. Past 50, every trip scores 0.6 more a point (up to 30, into the work band); from 75 (restless) exploring meets a need, so goal work does not crowd it out (`goals.URGES`); the "wander" trip ("look for something new": a biome it has never seen is sure, a biome where creatures it never met live 0.7, a cave mouth it has not looked into 0.6, new ground 0.3 where the area is at least a quarter new, and new ground 72 blocks away as a spot; reaching 90 blocks from home) is on offer at any level once the tick tends curiosity ("there is always more to see", or how it feels from 60 on), ending on anything new but ground: whenever nothing for the goal or a need is on offer, Mimo goes to see something new rather than sit, worked toward a discovery goal meanwhile (resolution 22); from 40, once needs are met, the day plan adds "Take time to wander and see something new", ticked off by the next such discovery. The model and `/api/mimo` get `{"level", "feeling"}`, the feeling "content", "curious", "restless" or "very restless", then "nothing new for 3 hours", "for 2 game days", "just saw something new" or "nothing new yet".
20. **Discovery goals** (Task 9), always on offer once home stands. new_land ("See new lands": a biome it has never seen), new_creature ("Meet a new creature"), cave ("Look into a cave": a cave mouth or sinkhole it has not looked into), water ("Follow the water": a lake it does not know) and far_hills ("Map the far hills": 12 patches never walked, farther than 48 blocks from home; only with a home it built). Each is open while there is something of its kind within 90 blocks of home, after first_shelter, and repeats (`Goal.repeat`): it counts only what Mimo found after it was set, and is on offer again once reached; `goals.offers` always keeps the best repeating goal among its four. Their rules score is 30 + 0.7 × curiosity, +100 once restless, so a restless pet's dawn choice turns to a discovery even past the current goal's lead (+100). Each has a trip wanted only while it is the goal, reaching 90 blocks from home: "look for new land", "look for a creature it has never met", "look into a cave" (looking in as the iron trip does), "follow the water", "walk the far hills"; the wander trip serves them all. The spec's "reach the bottom of the sinkhole" and "follow the river" become looking into a cave mouth or sinkhole and finding a lake it does not know (spec gaps).
21. **Goals lift the gates that would stall them** (Task 5; the controller's measure over 32 game days on L3: no pet reached diamonds, iron armor or lanterns, since iron armor waited for a creature's blow and mine_ore for three known diamonds). While armor is Mimo's goal, iron armor is worth its ingots before any blow (`harm.ARMOR_WANTED`: craft_tools makes it and mine_ore digs the iron it takes); while diamond tools are, mine_ore goes for any diamond Mimo remembers (`work.EAGER`). Both hooks are lists, crash-guarded, and a goal adds itself to them from `life_goals.py`.
22. **Less rest** (Tasks 8 and 11; the controller's measure on L3: rest and sleep took 70–80 % of the ticks, the owner's "content with a routine"). The wander trip is always on offer (resolution 19), so a pet with nothing for its goal or a need goes to see something new, and a rest lasts two game minutes (`REST_LONGEST`, was ten) before Mimo looks again. Task 11 checks that once home stands Mimo rests or sleeps (its purpose rest or sleep, or asleep) at most half the ticks, over every seed and both pickers: 60 % at `bd765f2` (72 % in slow mode), 44 % with L4 (46 %). The night is a third of a game day, and dusk's wait at home for nightfall is sleep too, so half is near the floor for a pet that sleeps at home.
23. **Out of scope.** L3 itself, L4b and L5. Goals beyond the ones listed; goals or reasons chosen by Luna; a goal line on the archive browser; a trip for wool (nothing uses wool yet) or for one kind of wood (any wood does).

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/survival/goals.py` | Create | The goal registry and its rules: milestones and progress, the brain's goal, purposes following it (`ADVANCES`), the tick's side, the chooser's offers, the views |
| `backend/survival/trips.py` | Create | The registry of reasons to explore: targets, offers, the trip, looking after a walk, the words for the chooser, the model and the viewer |
| `backend/survival/scouting.py` | Create | The needs Mimo explores for (trees, food), the landmarks' reaches, explore's `ADVANCES` check |
| `backend/survival/life_goals.py` | Create | first shelter, iron tools, diamond tools, armor, a safe yard, a herd, the land mapped; `hides_wanted`; the trips for iron, leather, a creature seed and the map |
| `backend/survival/homes.py` | Create | The better_home goal, the `improve_home` purpose and the trip for a site |
| `backend/survival/larder.py` | Create | The full_larder goal, the `stock_larder` purpose and `more_food` |
| `backend/survival/curiosity.py` | Create | Curiosity: its growth and discoveries, its lift, urge and time to wander, the wander trip, how it feels |
| `backend/survival/discovery.py` | Create | The discovery goals and their trips |
| `backend/survival/purposes.py`, `exploring.py` | Modify | explore goes for a reason (`trips`); rest lasts two game minutes; the docstrings |
| `backend/survival/pickers.py`, `models.py` | Modify | `Option.goal`, `Option.reasons`, `steer`, the payload's `goal`, `explore_reasons` and `trip`; the goal question, `jev_answers` and the instructions |
| `backend/survival/choosing.py` | Modify | Goal choices in the Chooser; routine re-choices with a goal; the purpose event's goal; the trip stored, its words in the event and thought, Jev's reason question |
| `backend/survival/brain.py` | Modify | `tend_goal` and `tend_curiosity` in `notice_step`, `note_discoveries` and `look_after` in `observe_step`; import the goal and reason modules |
| `backend/survival/foraging.py`, `creatures/hunting.py`, `creatures/harm.py`, `work.py` | Modify | `MORE_FOOD`, `HUNT_FOR`, `ARMOR_WANTED` and `EAGER` hooks |
| `backend/survival/snapshot.py` | Modify | `goal`, `trip` and `curiosity` in the stream, `goals_reached` on lives |
| `backend/tests/test_survival_{goals,goal_tick,goal_choice,trips,scouting,life_goals,homes,larder,curiosity,discovery,goal_view}.py` | Create | One test file per new module or area |
| `backend/tests/test_survival_{choosing,pickers,purposes,exploring,sim,days}.py` | Modify | What L4 changes in them |
| `frontend/src/survival/goals.ts` (+ test) | Create | The goal line, the day plan, the trip, the curiosity bar and the goals reached in words |
| `frontend/src/survival/types.ts`, `hud.ts`, `SurvivalHud.tsx`, `Memorial.tsx` | Modify | The stream's new fields; the HUD's goal, plan, trip and curiosity; the memorial's goals |
| `README.md` | Modify | Purposeful life |

## Tasks

1. The goal registry, and purposes that follow the goal
2. Goals in the tick: progress, the day plan, reached and given up
3. Choosing a goal: Jev or the rules
4. Every trip has a reason
5. Mimo's goals
6. A bigger stone home
7. A full larder
8. Curiosity
9. Discovery goals
10. What the model and the viewer are told, and Jev's pick of the reason
11. Fewer aimless loops, no trip without a reason, a discovery every day, less rest: the headless checks
12. Viewer: the goal line, the day plan, the trip, curiosity and the goals reached
13. Manual check on the demo and the README

Tasks 1–11 are the backend and 12 the viewer. Tasks 1–3 build the goal machinery with test goals, so nothing Mimo does changes until Task 4, which makes explore go only for a reason (at first the two needs); Task 5 registers the first goals and their trips. Tasks 8 and 9 make Mimo curious. Task 12 needs only Task 10's stream fields.

---

### Task 1: The goal registry, and purposes that follow the goal

**Files:**
- Create: `backend/survival/goals.py` (its header, every import and constant the module uses, the registry, progress, the brain's goal and how purposes follow it; Tasks 2, 3 and 8 append the rest)
- Modify: `backend/survival/pickers.py` (`Option.goal`; `options` returns `steer(s, found)`), `backend/survival/models.py` (the instructions and the criteria name the goal)
- Test: `backend/tests/test_survival_goals.py`

**Interfaces:**
- Consumes: `purposes.PURPOSES`, `is_valid`, `late_day`; `situation.Situation`, `in_tick`; `memory.know`, `known`; `crafting.RECIPES`; `triggers.ensure_brain`, `mark_trigger`; `once.log_once`; `pickers.Option`, `options`.
- Produces:
  - `goals.Milestone(text, share, purposes, items=())` and `goals.Goal(name, title, why, milestones, score, thought, after=(), valid=always, reward=GOAL_MOOD, repeat=False)` (a goal that repeats is on offer again once reached: Task 9's discovery goals), both frozen dataclasses; `GOALS: dict[str, Goal]`; `register_goal(goal) -> Goal`.
  - Constants: `GOAL_BOOST = 15.0`, `GOAL_TOP = 80.0`, `NEED_FLOOR = 50.0`, `NEEDS` (sleep, go_home, eat, cook, forage, fish, hunt, build_shelter, light_up, build_storage, drop_items), `GOAL_MOOD = 15.0`, `CHECK_EVERY = 60.0`, `STALL = SET_ASIDE = DAY_SECONDS`, `IDLE = DAY_SECONDS / 3`, `IDLE_RETRY = 600.0`, `STICK = 100.0`, `WORKABLE = 20.0`, `OFFERED = 4`, `PLAN_STEPS = 3`, `NEXT_SHOWN = 2`, `REACHED = "goal"`.
  - `lower(text) -> str`; `counted(goal) -> list[(index, Milestone)]`; `share_of(s, milestone) -> float` (0..1, once per Situation, 0 when it crashes); `progress_of(s, goal) -> float`; `complete(s, goal) -> bool`; `ahead(s, goal) -> list[(index, Milestone)]`; `reached(s) -> tuple[str, ...]`; `settled(s, name) -> bool`; `is_open(s, goal) -> bool`.
  - `goal_state(state) -> dict` (the brain, with `goal`, `goal_due`, `goal_penalties`, `goal_idle_at`); `active(s) -> Goal | None`; `ask_for_goal(state, reason, at)`; `adopt_goal(state, name | None, picker, thought, at) -> bool` (True for a new goal; it marks a `"goal"` purpose trigger).
  - `ADVANCES: dict[str, Callable[[Situation, Goal], bool]]` (a purpose that advances a goal only as it would be done now registers its check here: Task 4's explore); `advances(s, name, goal) -> bool`; `advancing(s, goal) -> frozenset[str]`.
  - `goal_purposes(s) -> frozenset[str] | None`; `penalized(s, name) -> bool`; `own_score(s, goal) -> float | None`; `toward(s, offered_now: set[str]) -> (Goal, frozenset[str]) | None`; `boosted(s, score) -> float`; `URGES: dict[str, Callable[[Situation], bool]]` (a purpose that meets a need while Mimo feels its urge: Task 8's curiosity registers explore); `meets_need(s, name, score) -> bool`.
  - `pickers.Option` gains `goal: str = ""` (the title of the goal it works toward); `pickers.steer(s, found) -> list[Option]`; `options(s)` returns the steered list.
  - `models.criteria` adds " It works toward the goal: <title>." for such an option; `models.INSTRUCTIONS` says to work toward the goal after staying alive.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_goals.py`:

```python
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose)
from backend.survival.goals import (
    ADVANCES, GOALS, URGES, Goal, Milestone, adopt_goal, complete, counted, is_open, meets_need, progress_of,
    register_goal, toward,
)
from backend.survival.memory import know
from backend.survival.models import criteria
from backend.survival.pickers import Option, options
from backend.survival.situation import DUSK
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_pickers import DAY, TREE, situation

WOOD = Goal("woodpile", "A woodpile", "Wood makes everything else.",
            (Milestone("Carry 4 logs", lambda s: s.count("oak_log") / 4, ("gather_wood",)),
             Milestone("Make a pickaxe", lambda s: float(s.count("wooden_pickaxe") > 0), ("craft_tools",)),
             Milestone("Grow a forest", lambda s: 0.0, ("grow_forest",)),  # no such purpose: skipped
             Milestone("Make a moon pickaxe", lambda s: 0.0, ("craft_tools",), items=("moon_pickaxe",))),  # no recipe
            score=lambda s: 50.0, thought="Wood first.")
STONE = Goal("quarry", "A quarry", "Stone lasts.", (Milestone("Dig stone", lambda s: 0.0, ("gather_stone",)),),
             score=lambda s: 40.0, thought="Stone next.", after=("woodpile",))
LATER = Goal("later", "Later", "Some day.", (Milestone("Dig stone", lambda s: 0.0, ("gather_stone",)),),
             score=lambda s: 30.0, thought="Some day.")


@contextmanager
def only_goals(*goals):
    """The registry holds just these goals for the test."""
    saved = dict(GOALS)
    GOALS.clear()
    for goal in goals:
        register_goal(goal)
    try:
        yield
    finally:
        GOALS.clear()
        GOALS.update(saved)


def goal_situation(goal=None, **changes):
    s = situation(**changes)
    if goal is not None:
        adopt_goal(s.state, goal, "utility", "", 0.0)
    return s


class ProgressTests(unittest.TestCase):
    def test_only_milestones_with_a_registered_purpose_and_known_recipes_count(self):
        self.assertEqual([index for index, _ in counted(WOOD)], [0, 1])
        some = situation(inventory={"oak_log": 2})
        self.assertAlmostEqual(progress_of(some, WOOD), 0.25)
        self.assertFalse(complete(some, WOOD))
        done = situation(inventory={"oak_log": 9, "wooden_pickaxe": 1})
        self.assertEqual((progress_of(done, WOOD), complete(done, WOOD)), (1.0, True))  # a share stops at 1

    def test_a_crashing_milestone_counts_nothing_and_is_logged_once(self):
        broken = Goal("broken", "Broken", "It breaks.", (Milestone("Break", lambda s: 1 / 0, ("gather_wood",)),),
                      score=lambda s: 10.0, thought="Oops.")
        with self.assertLogs("backend.survival.goals", level="ERROR") as logs:
            self.assertEqual(progress_of(situation(), broken), 0.0)
            self.assertEqual(progress_of(situation(), broken), 0.0)
        self.assertEqual(len(logs.output), 1)

    def test_a_goal_opens_once_the_goals_before_it_are_settled_and_until_it_is_reached(self):
        with only_goals(WOOD, STONE):
            s = situation()
            self.assertEqual((is_open(s, WOOD), is_open(s, STONE)), (True, False))
            s = situation(inventory={"oak_log": 4, "wooden_pickaxe": 1})  # the woodpile is complete: settled
            self.assertEqual((is_open(s, WOOD), is_open(s, STONE)), (False, True))
            s = situation()
            know(s.db, "woodpile", "goal", 0.0)  # reached earlier in this life
            self.assertEqual((is_open(s, WOOD), is_open(s, STONE)), (False, True))

    def test_a_goal_that_repeats_is_on_offer_again_once_reached(self):
        again = Goal("again", "Again", "Once more.", WOOD.milestones, score=lambda s: 10.0, thought="", repeat=True)
        with only_goals(WOOD, again):
            s = situation()
            know(s.db, "woodpile", "goal", 0.0)
            know(s.db, "again", "goal", 0.0)
            self.assertEqual((is_open(s, WOOD), is_open(s, again)), (False, True))

    def test_a_new_goal_starts_from_nothing_and_asks_for_a_new_purpose(self):
        with only_goals(WOOD):
            s = situation()
            s.brain["pending"] = None
            state = s.state
            self.assertTrue(adopt_goal(state, "woodpile", "jev", "Wood first.", 10.0))
            brain = state["brain"]
            self.assertEqual({key: brain["goal"][key] for key in ("name", "since", "picker", "plan", "best_at")},
                             {"name": "woodpile", "since": 10.0, "picker": "jev", "plan": None, "best_at": 10.0})
            self.assertEqual((brain["pending"]["reasons"], brain["goal_due"], state["last_thought"]),
                             (["goal"], None, "Wood first."))
            self.assertFalse(adopt_goal(state, "woodpile", "utility", "Again.", 20.0))  # kept, not started over
            self.assertEqual((brain["goal"]["since"], brain["goal"]["picker"]), (10.0, "utility"))
            self.assertFalse(adopt_goal(state, None, "utility", "", 30.0))  # none open: the tick asks again later
            self.assertEqual((brain["goal"]["name"], brain["goal_idle_at"]), ("woodpile", 30.0))


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
@patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [TREE])
class SteerTests(unittest.TestCase):
    def test_without_a_goal_every_purpose_is_offered_at_its_own_score(self):
        with only_goals(WOOD):
            found = {option.name: option for option in options(goal_situation())}
        self.assertLessEqual({"gather_wood", "rest"}, set(found))
        self.assertEqual(found["gather_wood"].score, 72.5)
        self.assertFalse(any(option.goal for option in found.values()))

    def test_purposes_that_advance_the_goal_score_more_and_nothing_else_is_offered(self):
        with only_goals(WOOD):
            found = options(goal_situation("woodpile"))
        self.assertEqual([(option.name, option.score, option.goal) for option in found],
                         [("gather_wood", 80.0, "A woodpile")])  # 72.5 + 15, no higher than 80

    def test_a_need_is_still_offered_and_late_in_the_day_the_goal_waits(self):
        with only_goals(WOOD):
            hungry = goal_situation("woodpile", inventory={"berries": 2}, vitals={**START_VITALS, "hunger": 40.0})
            self.assertEqual({(option.name, option.score) for option in options(hungry)},
                             {("gather_wood", 80.0), ("eat", 60.0)})
            late = goal_situation("woodpile", clock={**DAY, "seconds_into_day": DUSK - 100.0})
            self.assertEqual([(option.name, option.score) for option in options(late)], [("gather_wood", 42.5)])

    def test_while_nothing_for_the_goal_is_on_offer_another_open_goal_is_worked_toward(self):
        with only_goals(WOOD, LATER):
            s = goal_situation("later")  # no pickaxe: nothing digs stone
            found = options(s)
            self.assertEqual([(option.name, option.goal) for option in found], [("gather_wood", "A woodpile")])
            self.assertEqual(toward(s, {"rest"}), None)

    def test_a_purpose_with_a_check_of_its_own_advances_the_goal_only_when_it_says_so(self):
        def boom(s, goal):
            raise RuntimeError("boom")

        with only_goals(WOOD):
            s = goal_situation("woodpile")
            with patch.dict(ADVANCES, {"gather_wood": lambda s, goal: False}):
                self.assertIsNone(toward(s, {"gather_wood"}))
            s = goal_situation("woodpile")
            with patch.dict(ADVANCES, {"gather_wood": boom}), \
                    self.assertLogs("backend.survival.goals", level="ERROR") as logs:
                self.assertIsNone(toward(s, {"gather_wood"}))
            self.assertEqual(len(logs.output), 1)
            self.assertEqual(toward(goal_situation("woodpile"), {"gather_wood"})[1], {"gather_wood"})

    def test_a_purpose_meets_a_need_while_mimo_feels_its_urge(self):
        def boom(s):
            raise RuntimeError("boom")

        s = situation()
        self.assertEqual((meets_need(s, "eat", 60.0), meets_need(s, "eat", 40.0), meets_need(s, "rest", 60.0)),
                         (True, False, False))
        with patch.dict(URGES, {"rest": lambda s: True}):
            self.assertEqual((meets_need(s, "rest", 60.0), meets_need(s, "rest", 40.0)), (True, False))
        with patch.dict(URGES, {"rest": boom}), self.assertLogs("backend.survival.goals", level="ERROR") as logs:
            self.assertFalse(meets_need(s, "rest", 60.0))
            self.assertFalse(meets_need(s, "rest", 60.0))
        self.assertEqual(len(logs.output), 1)

    def test_the_model_is_told_which_choices_work_toward_the_goal(self):
        told = criteria([Option("gather_wood", "gather wood", "Chop a tree.", "a tree near", 80.0, "A woodpile"),
                         Option("rest", "rest", "Rest a while.", "mood 70", 15.0)])
        self.assertEqual(told, {"gather_wood": "Chop a tree. Now: a tree near. It works toward the goal: A woodpile.",
                                "rest": "Rest a while. Now: mood 70."})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goals.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.goals'`

- [ ] **Step 3: The goal registry**

Create `backend/survival/goals.py`:

```python
"""Goals (L4): long projects above purposes, as a registry.

A Goal is something Mimo works toward for days: a home of its own, iron tools, a full larder. It
has a name, a title and a why (for the model and the HUD), the goals that must be settled first
(`after`: reached, or complete now), a validity check, a rules score and a thought. Its progress
is a list of Milestones, each with its words, a share from 0 to 1 read from Mimo's state and
memory, and the purposes that work toward it. A milestone none of whose purposes is registered,
or that needs an item with no recipe yet, is skipped: it counts for nothing and the day plan
leaves it out. So goals name purposes by name, and grow as other modules register those purposes.
A goal's progress is the mean of its counted milestones' shares; it is complete when every one is
whole. A goal is reached once in a life, unless it repeats (`repeat`: a discovery goal, measured
from when it was set, is on offer again once reached).

Modules register goals on import (backend.survival.life_goals registers the ones Mimo has).

The brain keeps its goal in state["brain"]:
- goal: {"name", "since", "picker", "progress", "best", "best_at", "plan", "plan_day",
  "checked_at"} or None. `plan` is the day plan, [{"text", "done", "step"}]: the next milestones
  toward the goal (step is the milestone's index), written at dawn and when a goal is chosen.
- goal_due: a goal choice Mimo waits for, {"id", "reasons", "since"}, or None (ids come from
  the brain's next_id, like pending purpose choices).
- goal_penalties: {goal: server time until which it is not offered, after it was given up}.
- goal_idle_at: when a goal choice last found no goal open.
The goals Mimo reached are remembered in its world (memory_knowledge, fact "goal").

The tick tends the goal (`tend_goal`, from brain.notice_step). At most once a game minute it
reads the goal's progress: a complete goal is reached (a notable "goal" event, the goal's mood
reward, and a new goal and a new purpose are asked for); a goal no longer open is given up, and so
is one whose progress has not risen for IDLE game seconds of daylight while nothing that advances
it is on offer (`workable`). At dawn it writes the day plan (a routine "plan" event) and asks for a
goal choice: Jev may keep the goal or pick another, the rules picker keeps it. A goal whose
progress has not risen for a game day is given up at dawn instead. A goal given up is not offered
again for a game day. With no goal, a goal choice is asked for at once, then every IDLE_RETRY game
seconds while none is open. The worker's Chooser answers goal choices (backend.survival.choosing).

Purposes follow the goal (`toward`, used by pickers.steer): the purposes on offer that advance
the goal score GOAL_BOOST more (`boosted`: not past GOAL_TOP, and not late in the day or at
night, so going home and sleep still come first). While anything advances the goal or meets a
need (a purpose in NEEDS, or one whose urge Mimo feels now, `URGES`, scoring NEED_FLOOR or more),
only those are offered: the others, rest and explore among them, would be capped in the leisure
band anyway, and leaving them out keeps a model's pick on the goal too. When nothing for the goal is on offer now (torches wait for the
evening, a hunt for hides for its gap), the best other open goal that has something on offer is
worked toward meanwhile. A purpose whose work depends on why it is done says for itself whether it
advances a goal right now (`ADVANCES`: an explore trip does when its reason serves the goal,
backend.survival.scouting); any other purpose a milestone still to do names advances its goal.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable

from backend.services.crafting import RECIPES
from backend.survival.clock import DAY_SECONDS
from backend.survival.memory import know, known
from backend.survival.once import log_once
from backend.survival.purposes import PURPOSES, is_valid, late_day
from backend.survival.situation import Situation, in_tick
from backend.survival.triggers import ensure_brain, mark_trigger

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

GOAL_BOOST = 15.0  # purposes that advance the goal score this much more...
GOAL_TOP = 80.0  # ...but never into the survival band (80 and up): staying alive comes first
NEED_FLOOR = 50.0  # a purpose in NEEDS meets a need when it scores at least this
# The survival and needs bands of purposes.py, and M5's keeping of home and arms.
NEEDS = frozenset({"sleep", "go_home", "eat", "cook", "forage", "fish", "hunt", "build_shelter", "light_up",
                   "build_storage", "drop_items"})
GOAL_MOOD = 15.0  # mood a reached goal gives, unless the goal says otherwise
CHECK_EVERY = 60.0  # game seconds between two readings of the goal's progress in the tick
STALL = DAY_SECONDS  # game seconds without progress after which a goal is given up at dawn
IDLE = DAY_SECONDS / 3  # by day, this long without progress and nothing on offer for it: given up
SET_ASIDE = DAY_SECONDS  # game seconds a goal given up is not offered again
IDLE_RETRY = 600.0  # game seconds between two goal choices while no goal is open
STICK = 100.0  # the rules picker keeps the current goal (a stalled one was given up before)...
WORKABLE = 20.0  # ...and otherwise prefers a goal something can be done for right now
OFFERED = 4  # goals offered at a choice, the current one among them
PLAN_STEPS = 3  # milestones on the day plan
NEXT_SHOWN = 2  # milestones named in a goal's facts
REACHED = "goal"  # the memory_knowledge fact for a goal Mimo reached


@dataclass(frozen=True)
class Milestone:
    text: str  # "Make an iron pickaxe"
    share: Callable[[Situation], float]  # how much of it is done, 0 to 1
    purposes: tuple[str, ...]  # the purposes that work toward it
    items: tuple[str, ...] = ()  # items it needs a recipe for (L3's): skipped while one has none


def always(s: Situation) -> bool:
    return True


@dataclass(frozen=True)
class Goal:
    name: str
    title: str  # "Iron tools"
    why: str  # one sentence for the model and the HUD
    milestones: tuple[Milestone, ...]
    score: Callable[[Situation], float]  # the rules picker's score
    thought: str  # what Mimo thinks when it sets out
    after: tuple[str, ...] = ()  # goals that must be settled first
    valid: Callable[[Situation], bool] = always
    reward: float = GOAL_MOOD
    repeat: bool = False  # on offer again once reached (its milestones count from when it was set)


GOALS: dict[str, Goal] = {}


def register_goal(goal: Goal) -> Goal:
    """Add a goal, or replace the one with the same name."""
    GOALS[goal.name] = goal
    return goal


def lower(text: str) -> str:
    return text[:1].lower() + text[1:]


# Progress --------------------------------------------------------------------------------------

def counted(goal: Goal) -> list[tuple[int, Milestone]]:
    """The goal's milestones that count, with their index: a purpose of theirs is registered and
    every item they need has a recipe."""
    return [(index, milestone) for index, milestone in enumerate(goal.milestones)
            if any(name in PURPOSES for name in milestone.purposes)
            and all(item in RECIPES for item in milestone.items)]


def share_of(s: Situation, milestone: Milestone) -> float:
    """A milestone's share, read once per Situation. One that crashes counts as 0 (logged once)."""
    def look() -> float:
        try:
            share = float(milestone.share(s))
        except Exception as error:
            log_once(logger, f"milestone {milestone.text!r}", error)
            return 0.0
        return min(1.0, max(0.0, share)) if math.isfinite(share) else 0.0
    return s.sensed(f"milestone {id(milestone)}", look)


def progress_of(s: Situation, goal: Goal) -> float:
    steps = counted(goal)
    return sum(share_of(s, milestone) for _, milestone in steps) / len(steps) if steps else 0.0


def complete(s: Situation, goal: Goal) -> bool:
    steps = counted(goal)
    return bool(steps) and all(share_of(s, milestone) >= 1.0 for _, milestone in steps)


def ahead(s: Situation, goal: Goal) -> list[tuple[int, Milestone]]:
    """The counted milestones still to do, in order."""
    return [(index, milestone) for index, milestone in counted(goal) if share_of(s, milestone) < 1.0]


def reached(s: Situation) -> tuple[str, ...]:
    """The goals Mimo reached in this life, first first."""
    return s.sensed("goals reached", lambda: tuple(known(s.db, REACHED)) if s.db is not None else ())


def settled(s: Situation, name: str) -> bool:
    goal = GOALS.get(name)
    return name in reached(s) or (goal is not None and complete(s, goal))


def is_open(s: Situation, goal: Goal) -> bool:
    """On offer: a milestone counts, the goals before it are settled, it is valid, not reached yet
    (unless it repeats) and not complete. A validity check that crashes counts as not valid (logged
    once)."""
    if not counted(goal) or (goal.name in reached(s) and not goal.repeat):
        return False
    if not all(settled(s, name) for name in goal.after):
        return False
    try:
        valid = bool(goal.valid(s))
    except Exception as error:
        log_once(logger, f"goal {goal.name} validity", error)
        return False
    return valid and not complete(s, goal)


# The brain's goal ------------------------------------------------------------------------------

def goal_state(state: dict) -> dict:
    """The brain, with the goal fields a world from before L4 lacks."""
    brain = ensure_brain(state)
    brain.setdefault("goal", None)
    brain.setdefault("goal_due", None)
    brain.setdefault("goal_penalties", {})
    brain.setdefault("goal_idle_at", None)
    return brain


def active(s: Situation) -> Goal | None:
    """The goal Mimo works toward now, or None."""
    goal = s.brain.get("goal")
    return GOALS.get(goal["name"]) if goal else None


def ask_for_goal(state: dict, reason: str, at: float) -> None:
    """Ask for a goal choice. A pending one keeps its id and gains the reason."""
    brain = goal_state(state)
    due = brain["goal_due"]
    if due is not None:
        if reason not in due["reasons"]:
            due["reasons"] = [*due["reasons"], reason]
        return
    brain["goal_due"] = {"id": brain["next_id"], "reasons": [reason], "since": at}
    brain["next_id"] += 1


def adopt_goal(state: dict, name: str | None, picker: str, thought: str, at: float) -> bool:
    """Answer the goal choice with `name` (None: no goal is open). True for a new goal: it starts
    from nothing, the next tick writes its day plan, and the purpose is chosen again under it."""
    brain = goal_state(state)
    brain["goal_due"] = None
    current = brain["goal"]
    if name is None or name not in GOALS:
        brain["goal_idle_at"] = at
        return False
    if current is not None and current["name"] == name:
        current["picker"] = picker
        return False
    brain["goal"] = {"name": name, "since": at, "picker": picker, "progress": 0.0, "best": -1.0, "best_at": at,
                     "plan": None, "plan_day": None, "checked_at": None}
    state["last_thought"] = thought
    mark_trigger(state, "goal", at)
    return True


# Purposes follow the goal ----------------------------------------------------------------------

# {purpose: check(s, goal)} for purposes that advance a goal only as they would be done now.
ADVANCES: dict[str, Callable[[Situation, Goal], bool]] = {}


def advances(s: Situation, name: str, goal: Goal) -> bool:
    """The purpose, named by a milestone of the goal still to do, would advance it now: always,
    unless it has a check of its own (ADVANCES). A check that crashes counts as no (logged once)."""
    check = ADVANCES.get(name)
    if check is None:
        return True
    try:
        return bool(check(s, goal))
    except Exception as error:
        log_once(logger, f"{name} advances {goal.name}", error)
        return False


def advancing(s: Situation, goal: Goal) -> frozenset[str]:
    """The registered purposes that would advance the goal now (the milestones still to do name them)."""
    return frozenset(name for _, milestone in ahead(s, goal) for name in milestone.purposes
                     if name in PURPOSES and advances(s, name, goal))


def goal_purposes(s: Situation) -> frozenset[str] | None:
    """The purposes that advance the goal now, or None without a goal."""
    goal = active(s)
    if goal is None:
        return None
    return s.sensed("goal purposes", lambda: advancing(s, goal))


def penalized(s: Situation, name: str) -> bool:
    return s.brain.get("goal_penalties", {}).get(name, -math.inf) > s.at


def own_score(s: Situation, goal: Goal) -> float | None:
    try:
        return float(goal.score(s))
    except Exception as error:
        log_once(logger, f"goal {goal.name} score", error)
        return None


def toward(s: Situation, offered_now: set[str]) -> tuple[Goal, frozenset[str]] | None:
    """The goal the options on offer work toward, with those that advance it: Mimo's goal when
    something for it is on offer; else the best other open goal (by its own score) that has
    something on offer, worked toward meanwhile. None without a goal, or with nothing on offer
    for any open goal."""
    current = active(s)
    if current is None:
        return None
    names = (goal_purposes(s) or frozenset()) & offered_now
    if names:
        return current, names
    best: tuple[float, Goal, frozenset[str]] | None = None
    for goal in GOALS.values():
        if goal.name == current.name or penalized(s, goal.name) or not is_open(s, goal):
            continue
        names = advancing(s, goal) & offered_now
        score = own_score(s, goal) if names else None
        if score is not None and (best is None or score > best[0]):
            best = (score, goal, names)
    return (best[1], best[2]) if best else None


def boosted(s: Situation, score: float) -> float:
    """The score of a purpose that advances a goal: GOAL_BOOST more, not past GOAL_TOP and never
    lower. Late in the day and at night the goal waits for tomorrow: no boost."""
    if s.night or late_day(s):
        return score
    return max(score, min(score + GOAL_BOOST, GOAL_TOP))


# {purpose: urge(s)}: a purpose that meets a need while Mimo feels its urge (L4's curiosity: explore).
URGES: dict[str, Callable[[Situation], bool]] = {}


def meets_need(s: Situation, name: str, score: float) -> bool:
    """The purpose meets a need: a survival or needs purpose, or one whose urge Mimo feels now, scoring
    NEED_FLOOR or more. An urge that crashes counts as not felt (logged once)."""
    if score < NEED_FLOOR:
        return False
    if name in NEEDS:
        return True
    urge = URGES.get(name)
    if urge is None:
        return False
    try:
        return bool(urge(s))
    except Exception as error:
        log_once(logger, f"{name} urge", error)
        return False
```

- [ ] **Step 4: Purposes follow the goal**

In `backend/survival/pickers.py`, replace:

```python
hostile creatures near it and what it can meet them with.
"""
```

with:

```python
hostile creatures near it and what it can meet them with. L4: the options follow Mimo's goal
(`steer`, with the rules in backend.survival.goals).
"""
```

and replace:

```python
from dataclasses import dataclass
```

with:

```python
from dataclasses import dataclass, replace
```

and replace:

```python
from backend.survival.exploring import exploration_payload
```

with:

```python
from backend.survival.exploring import exploration_payload
from backend.survival.goals import active, boosted, meets_need, toward
```

and replace:

```python
    facts: str
    score: float
```

with:

```python
    facts: str
    score: float
    goal: str = ""  # L4: the title of the goal it works toward, if any
```

and replace:

```python
        found.append(Option(purpose.name, purpose.phrase, purpose.description, facts, score))
    return found
```

with:

```python
        found.append(Option(purpose.name, purpose.phrase, purpose.description, facts, score))
    return steer(s, found)


def steer(s: Situation, found: list[Option]) -> list[Option]:
    """L4: the options with Mimo's goal in mind (backend.survival.goals). The ones that advance the goal
    (or, while it waits, another open goal: goals.toward) are marked with its title and score more
    (goals.boosted). While any option advances a goal or meets a need, only those are offered: the
    others, rest and explore among them, would be capped in the leisure band anyway, and leaving them
    out keeps a model's pick on the goal too. Otherwise every option keeps its own score. Without a
    goal, the options are as found."""
    if active(s) is None:
        return found
    aim = toward(s, {option.name for option in found})
    title, advancing = (aim[0].title, aim[1]) if aim else ("", frozenset())
    steered = [replace(option, score=boosted(s, option.score), goal=title) if option.name in advancing else option
               for option in found]
    focused = [option for option in steered if option.goal or meets_need(s, option.name, option.score)]
    return focused or steered
```

In `backend/survival/models.py`, replace:

```python
                "rest, shelter by night), then follow its traits. Choose only from the offered purposes.")
```

with:

```python
                "rest, shelter by night), then work toward its goal (the choices that say they do), then "
                "follow its traits. Choose only from the offered purposes.")
```

and replace:

```python
    return {option.name: f"{option.description} Now: {option.facts}." for option in choices}
```

with:

```python
    return {option.name: f"{option.description} Now: {option.facts}."
            + (f" It works toward the goal: {option.goal}." if option.goal else "") for option in choices}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goals.py"`
Expected: `Ran 12 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 949 tests` … `OK` (12 new). No goal is registered yet, so nothing Mimo does changes.

- [ ] **Step 6: Commit**

```bash
git add backend/survival/goals.py backend/survival/pickers.py backend/survival/models.py backend/tests/test_survival_goals.py
git commit -m "feat: a goal registry with milestones and progress, and purposes that follow the goal" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Goals in the tick: progress, the day plan, reached and given up

**Files:**
- Modify: `backend/survival/goals.py` (append the tick's side), `backend/survival/brain.py` (`notice_step` calls `tend_goal`)
- Test: `backend/tests/test_survival_goal_tick.py`

**Interfaces:**
- Consumes: Task 1's registry, `goal_state`, `ask_for_goal`, `counted`, `ahead`, `share_of`, `progress_of`, `complete`, `is_open`, `lower`, the constants; `actions.ActionContext` (`grid`, `clock_at`, `events`, `db`); `brain.notice_step`'s `phase` (`"dawn"`, `"dusk"` or None).
- Produces:
  - `goals.stalled(s) -> bool`; `as_goal(s, goal) -> Situation` (a copy with `goal` as Mimo's goal); `workable(s, goal) -> bool` (a purpose that advances it would be on offer, were it Mimo's goal); `idle(s, goal) -> bool` (by day, `IDLE` game seconds without progress and nothing workable); `PLAN_EXTRAS: list` of `(s, goal) -> dict | None` (a step the day also sets time aside for, with no milestone: Task 8's time to wander); `day_plan(s, goal) -> list[{"text", "done", "step"}]`; `plan_sentence(name, plan) -> str`; `reach_goal(state, context, goal, at)`; `give_up_goal(state, context, name, at, why, scale)`; `check_goal(state, context, at, dawn)`; `tend_goal(state, context, at, phase)` (never raises).
  - Events: `goal` (notable) "Pip reached a goal: a home of its own."; `plan` (routine) "Pip's plan for today: …." and "Pip set a goal aside for now: … (no progress for a day)." (at dawn), "(nothing to do for it now)" (idle) or "(it cannot be done now)".
  - `state["brain"]["goal_due"]["reasons"]` gains `"no_goal"`, `"dawn"`, `"reached"` or `"given_up"`; a reached or given-up goal also marks a `"goal"` purpose trigger.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_goal_tick.py`:

```python
import random
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from backend.survival.actions import ActionContext
from backend.survival.brain import BRAIN
from backend.survival.clock import DAY_SECONDS
from backend.survival.goals import (
    IDLE, IDLE_RETRY, Goal, Milestone, active, adopt_goal, as_goal, goal_state, tend_goal, workable,
)
from backend.survival.hatch import hatch
from backend.survival.memory import known
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES, Purpose
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.tests.test_survival_goals import LATER, STONE, WOOD, only_goals
from backend.tests.test_survival_pickers import DAY, forest, situation

BORN = 1_000_000.0
ONLY = Goal("only", "Only", "Its own work.", (Milestone("Do it", lambda s: 0.0, ("goal_only",)),),
            score=lambda s: 20.0, thought="Mine alone.")


@contextmanager
def goal_only_purpose():
    """A purpose offered only while ONLY is Mimo's goal, as improve_home is for a bigger home."""
    PURPOSES["goal_only"] = Purpose(
        "goal_only", "do it", "Only for its goal.", valid=lambda s: active(s) is not None and active(s).name == "only",
        facts=lambda s: "", score=lambda s: 50.0, plan=lambda s, context: [], thoughts=("Mine alone.",))
    try:
        yield
    finally:
        del PURPOSES["goal_only"]


class TendTests(unittest.TestCase):
    def setUp(self):
        self.s = situation()
        self.s.brain["pending"] = None
        self.state = self.s.state
        self.events = []
        self.context = ActionContext(grid=forest(), clock_at=lambda at: DAY, planner=lambda *args: [],
                                     events=self.events, db=self.s.db)

    def tend(self, at, phase=None):
        tend_goal(self.state, self.context, at, phase)
        return goal_state(self.state)

    def test_without_a_goal_one_is_asked_for_now_and_again_while_none_is_open(self):
        brain = self.tend(0.0)
        self.assertEqual(brain["goal_due"]["reasons"], ["no_goal"])
        adopt_goal(self.state, None, "utility", "", 5.0)  # nothing was open
        self.assertIsNone(self.tend(5.0 + IDLE_RETRY - 1)["goal_due"])
        self.assertEqual(self.tend(5.0 + IDLE_RETRY)["goal_due"]["reasons"], ["no_goal"])
        adopt_goal(self.state, None, "utility", "", 700.0)
        self.assertEqual(self.tend(701.0, "dawn")["goal_due"]["reasons"], ["dawn"])  # dawn asks at once

    def test_a_new_goal_gets_a_day_plan_and_its_progress_is_read_once_a_game_minute(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            brain = self.tend(1.0)
            self.assertEqual(brain["goal"]["plan"], [{"text": "Carry 4 logs", "done": False, "step": 0},
                                                     {"text": "Make a pickaxe", "done": False, "step": 1}])
            self.assertEqual(self.events[-1][1:], ("plan", "Pip's plan for today: carry 4 logs and make a pickaxe."))
            self.state["inventory"]["oak_log"] = 4
            self.assertEqual(self.tend(30.0)["goal"]["progress"], 0.0)  # read at most once a game minute
            brain = self.tend(61.0)
            self.assertEqual((brain["goal"]["progress"], brain["goal"]["plan"][0]["done"]), (0.5, True))
            self.assertEqual(len(self.events), 1)

    def test_the_day_plan_sets_time_aside_for_what_else_the_day_calls_for(self):
        extras = [lambda s, goal: {"text": "Take time to wander", "kind": "wander"}, lambda s, goal: None]
        with only_goals(WOOD), patch("backend.survival.goals.PLAN_EXTRAS", extras):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            plan = self.tend(1.0)["goal"]["plan"]
        self.assertEqual(plan[-1], {"text": "Take time to wander", "done": False, "step": None, "kind": "wander"})
        self.assertEqual(self.events[-1][2], "Pip's plan for today: carry 4 logs, make a pickaxe and take time to wander.")

    def test_a_complete_goal_is_reached_remembered_and_cheered(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.tend(1.0)
            self.state["inventory"].update(oak_log=4, wooden_pickaxe=1)
            mood = self.state["vitals"]["mood"]
            brain = self.tend(100.0)
            self.assertIsNone(brain["goal"])
            self.assertEqual(self.events[-1][1:], ("goal", "Pip reached a goal: a woodpile."))
            self.assertEqual(self.state["vitals"]["mood"], min(100.0, mood + 15.0))
            self.assertEqual(known(self.s.db, "goal"), ["woodpile"])
            self.assertEqual(brain["goal_due"]["reasons"], ["reached"])
            self.assertIn("goal", brain["pending"]["reasons"])

    def test_at_dawn_the_plan_is_written_again_and_a_goal_choice_is_asked_for(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.tend(1.0)
            self.state["inventory"]["oak_log"] = 4
            brain = self.tend(DAY_SECONDS - 10.0, "dawn")
            self.assertEqual(brain["goal"]["plan"], [{"text": "Make a pickaxe", "done": False, "step": 1}])
            self.assertEqual(brain["goal_due"]["reasons"], ["dawn"])

    def test_a_goal_without_progress_for_a_day_is_set_aside_at_dawn(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.tend(1.0)
            brain = self.tend(DAY_SECONDS + 5.0, "dawn")
            self.assertIsNone(brain["goal"])
            self.assertEqual(self.events[-1][1:],
                             ("plan", "Pip set a goal aside for now: a woodpile (no progress for a day)."))
            self.assertEqual((brain["goal_penalties"], brain["goal_due"]["reasons"]),
                             ({"woodpile": 2 * DAY_SECONDS + 5.0}, ["given_up"]))

    def test_by_day_a_goal_with_nothing_to_do_for_it_is_set_aside_once_it_idles(self):
        with only_goals(WOOD, LATER):
            adopt_goal(self.state, "later", "jev", "Some day.", 0.0)  # no pickaxe: nothing digs stone
            self.tend(1.0)
            self.assertIsNotNone(self.tend(IDLE - 10.0)["goal"])
            brain = self.tend(IDLE + 70.0)
            self.assertIsNone(brain["goal"])
            self.assertEqual(self.events[-1][2], "Pip set a goal aside for now: later (nothing to do for it now).")

    def test_whether_a_goal_is_workable_is_judged_as_if_it_were_mimos_goal(self):
        with only_goals(WOOD, ONLY), goal_only_purpose():
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.assertTrue(workable(self.s, ONLY))
            self.assertEqual(as_goal(self.s, ONLY).brain["goal"]["name"], "only")
            self.assertEqual(self.s.brain["goal"]["name"], "woodpile")  # the real state is untouched

    def test_a_goal_that_can_no_longer_be_done_is_set_aside(self):
        with only_goals(WOOD, STONE):
            adopt_goal(self.state, "quarry", "jev", "Stone next.", 0.0)  # the woodpile is not settled
            self.assertIsNone(self.tend(1.0)["goal"])
            self.assertEqual(self.events[-1][2], "Pip set a goal aside for now: a quarry (it cannot be done now).")

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        forget_logged()
        with only_goals(WOOD), patch("backend.survival.goals.check_goal", side_effect=RuntimeError("boom")):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            with self.assertLogs("backend.survival.goals", level="ERROR") as logs:
                self.tend(1.0)
                self.tend(2.0)
        self.assertEqual(len(logs.output), 1)


class BrainTests(unittest.TestCase):
    def test_the_brain_asks_for_a_goal_after_its_first_vitals_step(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            hatch(registry, random.Random(8), timestamp=BORN)
            state = tick_life(registry, BORN + 1, scale=1.0, mind=BRAIN)
        self.assertEqual(state["brain"]["goal_due"]["reasons"], ["no_goal"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goal_tick.py"`
Expected: ERROR: `ImportError: cannot import name 'as_goal' from 'backend.survival.goals'`

- [ ] **Step 3: The goal in the tick**

The block starts with the two blank lines that separate it from the section before.

In `backend/survival/goals.py`, append:

```python


# The goal in the tick --------------------------------------------------------------------------

def stalled(s: Situation) -> bool:
    """The goal's progress has not risen for STALL game seconds."""
    goal = s.brain.get("goal")
    return goal is not None and (s.at - goal["best_at"]) * s.scale >= STALL


def as_goal(s: Situation, goal: Goal) -> Situation:
    """`s` as if `goal` were Mimo's goal, on a copy of the state: some purposes are offered only for
    a goal of their own (improve_home, stock_larder, a hunt for hides)."""
    current = s.brain.get("goal")
    if current is not None and current["name"] == goal.name:
        return s
    return replace(s, state={**s.state, "brain": {**s.brain, "goal": {"name": goal.name}}}, memo={})


def workable(s: Situation, goal: Goal) -> bool:
    """Something that advances the goal would be on offer now, were it Mimo's goal."""
    t = as_goal(s, goal)
    return any(is_valid(PURPOSES[name], t) for name in advancing(t, goal))


def idle(s: Situation, goal: Goal) -> bool:
    """By day, the goal's progress has not risen for IDLE game seconds and nothing that advances it
    is on offer: there is nothing to do for it."""
    since = s.brain["goal"]["best_at"]
    return (not s.night and not late_day(s) and (s.at - since) * s.scale >= IDLE and not workable(s, goal))


# Functions of (Situation, Goal) giving a step the day plan also sets time aside for, or None (L4's
# curiosity adds time to wander once needs are met). Such a step has no milestone ("step": None).
PLAN_EXTRAS: list = []


def day_plan(s: Situation, goal: Goal) -> list[dict]:
    """The next PLAN_STEPS milestones toward the goal, then whatever else the day sets time aside for
    (PLAN_EXTRAS; one that crashes is left out, logged once)."""
    plan = [{"text": milestone.text, "done": False, "step": index} for index, milestone in ahead(s, goal)[:PLAN_STEPS]]
    for extra in PLAN_EXTRAS:
        try:
            entry = extra(s, goal)
        except Exception as error:
            log_once(logger, "day plan extra", error)
            continue
        if entry is not None:
            plan.append({"done": False, "step": None, **entry})
    return plan


def plan_sentence(name: str, plan: list[dict]) -> str:
    words = [lower(entry["text"]) for entry in plan]
    listed = words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"
    return f"{name}'s plan for today: {listed}."


def reach_goal(state: dict, context: ActionContext, goal: Goal, at: float) -> None:
    """A notable "goal" event, the goal's mood reward, the goal remembered, and new choices."""
    goal_state(state)["goal"] = None
    know(context.db, goal.name, REACHED, at)
    context.events.append((at, "goal", f"{state['name']} reached a goal: {lower(goal.title)}."))
    state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + goal.reward)
    state["last_thought"] = f"I did it: {lower(goal.title)}!"
    ask_for_goal(state, "reached", at)
    mark_trigger(state, "goal", at)


def give_up_goal(state: dict, context: ActionContext, name: str, at: float, why: str, scale: float) -> None:
    """A routine "plan" event, the goal set aside for SET_ASIDE game seconds, and new choices."""
    brain = goal_state(state)
    brain["goal"] = None
    brain["goal_penalties"][name] = at + SET_ASIDE / scale
    title = lower(GOALS[name].title) if name in GOALS else name.replace("_", " ")
    context.events.append((at, "plan", f"{state['name']} set a goal aside for now: {title} ({why})."))
    ask_for_goal(state, "given_up", at)
    mark_trigger(state, "goal", at)


def check_goal(state: dict, context: ActionContext, at: float, dawn: bool) -> None:
    brain = goal_state(state)
    current = brain["goal"]
    s = in_tick(state, context, at)
    goal = GOALS.get(current["name"])
    if goal is None or not counted(goal):
        give_up_goal(state, context, current["name"], at, "it is not known any more", s.scale)
        return
    current["checked_at"] = at
    if complete(s, goal):
        reach_goal(state, context, goal, at)
        return
    if not is_open(s, goal):
        give_up_goal(state, context, goal.name, at, "it cannot be done now", s.scale)
        return
    progress = progress_of(s, goal)
    current["progress"] = round(progress, 3)
    if progress > current["best"] + 1e-6:
        current.update(best=progress, best_at=at)
    if dawn and stalled(s):
        give_up_goal(state, context, goal.name, at, "no progress for a day", s.scale)
        return
    if not dawn and idle(s, goal):
        give_up_goal(state, context, goal.name, at, "nothing to do for it now", s.scale)
        return
    if dawn or current["plan"] is None:
        current["plan"] = day_plan(s, goal)
        current["plan_day"] = s.clock["day_number"]
        if current["plan"]:
            context.events.append((at, "plan", plan_sentence(state["name"], current["plan"])))
    else:
        for entry in current["plan"]:
            step = entry.get("step")
            if isinstance(step, int) and 0 <= step < len(goal.milestones):
                entry["done"] = share_of(s, goal.milestones[step]) >= 1.0
    if dawn:
        ask_for_goal(state, "dawn", at)


def tend_goal(state: dict, context: ActionContext, at: float, phase: str | None) -> None:
    """The goal after a vitals step (brain.notice_step): see the module docstring. A crash is
    logged once and the tick goes on."""
    if context.db is None or state.get("died_at") is not None:
        return
    try:
        brain = goal_state(state)
        scale = context.clock_at(at)["time_scale"]
        dawn = phase == "dawn"
        current = brain["goal"]
        if current is None:
            idle = brain["goal_idle_at"]
            if brain["goal_due"] is None and (dawn or idle is None or (at - idle) * scale >= IDLE_RETRY):
                ask_for_goal(state, "dawn" if dawn else "no_goal", at)
            return
        checked = current.get("checked_at")
        if dawn or current["plan"] is None or checked is None or (at - checked) * scale >= CHECK_EVERY:
            check_goal(state, context, at, dawn)
    except Exception as error:
        log_once(logger, "goals", error)
```

In `backend/survival/brain.py`, replace:

```python
First sightings (home, each ore material, water) are discoveries and ask for a new choice, and so
```

with:

```python
L4: `notice_step` also tends Mimo's goal (backend.survival.goals.tend_goal): its progress, the day
plan at dawn, a goal reached or given up.
First sightings (home, each ore material, water) are discoveries and ask for a new choice, and so
```

and replace:

```python
from backend.survival.exploring import note_ground
```

with:

```python
from backend.survival.exploring import note_ground
from backend.survival.goals import tend_goal
```

and replace:

```python
    if phase:
        mark_trigger(state, phase, at)
```

with:

```python
    if phase:
        mark_trigger(state, phase, at)
    tend_goal(state, context, at, phase)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goal_tick.py"`
Expected: `Ran 11 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 960 tests` … `OK` (11 new). The tick now asks for a goal, and nothing answers until Task 3.

- [ ] **Step 5: Commit**

```bash
git add backend/survival/goals.py backend/survival/brain.py backend/tests/test_survival_goal_tick.py
git commit -m "feat: the tick tends Mimo's goal: its progress, a day plan at dawn, and goals reached or set aside" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Choosing a goal: Jev or the rules

**Files:**
- Modify: `backend/survival/goals.py` (append the offers), `backend/survival/choosing.py` (the goal choice in the Chooser; routine re-choices with a goal; the purpose event's goal), `backend/survival/models.py` (the goal question and its instructions), `backend/tests/test_survival_sim.py` (the fake Jev answers either question)
- Test: `backend/tests/test_survival_goal_choice.py`

**Interfaces:**
- Consumes: Task 1's `GOALS`, `active`, `adopt_goal`, `goal_state`, `lower`, `is_open`, `penalized`, `own_score`, `ahead`, `progress_of`, `reached`; Task 2's `stalled` and `workable`; `choosing.Ask`, `Choice`, `decide`, `store_choice`, `calls_today`, `recent_calls`, `cap`, `DECISION_CAP`, `JEV_HOUR_CAP`; `pickers.Option`, `options`, `context_payload`, `utility_pick`, `thought_for`; `models.ask_jev`, `jev_configured`.
- Produces:
  - `goals.goal_facts(s, goal) -> str`; `rules_score(s, goal) -> float`; `offers(s) -> list[(Goal, facts, score)]`; `reached_titles(s) -> list[str]`.
  - `models.GOAL_INSTRUCTIONS`; `models.ask_jev(payload, choices, env, http=post_json, question="purpose", instructions=INSTRUCTIONS) -> str`.
  - `choosing.Ask` gains `kind: str = "purpose"` (or `"goal"`); `goal_route(brain, now, env, game_at, offered) -> str`; `prepare_goal(world, now, scale, env) -> Ask | None` (answers at once when no goal is open); `store_goal(world, ask, choice, now) -> str | None`; `answer_thought(ask, name, rng) -> str`; `routine(brain, steady=False)` and `route_for(brain, now, env, game_at, steady=False)`: with `steady` (a goal is active) every ordinary ending is routine. `Chooser.poll` answers a goal choice first; a rules answer is stored and the purpose choice follows in the same poll.
  - A purpose event names the goal its option works toward: `Pip decided to gather wood, toward a woodpile. "…"`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_goal_choice.py`:

```python
import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.choosing import (
    Ask, Choice, Chooser, InlineExecutor, prepare, prepare_goal, store_choice, store_goal,
)
from backend.survival.goals import Goal, adopt_goal, ask_for_goal, goal_state, offers
from backend.survival.hatch import hatch
from backend.survival.models import GOAL_INSTRUCTIONS, ask_jev
from backend.survival.once import forget_logged
from backend.survival.pickers import Option
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_choosing import JEV_URL, FakeHttp
from backend.tests.test_survival_goals import LATER, WOOD, goal_situation, only_goals

BORN = 1_000_000.0
JEV = {"TYPESAFE_API_KEY": "k"}
NO_CALLS = {"model": 0, "luna": 0, "reflections": 0}


class Recorder:
    """A model endpoint that gives one answer and keeps every request body."""

    def __init__(self, answer):
        self.answer, self.bodies = answer, []

    def __call__(self, url, headers, body, timeout):
        self.bodies.append(body)
        return self.answer


class GoalChoiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.path = self.registry.world_path(self.life)
        self.world = SurvivalWorld(self.path)
        self.name = self.life["name"]

    def tearDown(self):
        self.directory.cleanup()

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            change(state)
            write_state(db, state)

    def brain(self):
        return goal_state(self.world.state())

    def chooser(self, env=None, answers=None):
        return Chooser(env=env or {}, http=FakeHttp(answers or {}), executor=InlineExecutor(), rng=random.Random(1),
                       scale=1.0)

    def ask(self, env=None):
        return prepare_goal(SurvivalWorld(self.path, read_only=True), BORN + 5, 1.0, env or {})

    def test_nothing_is_asked_until_the_tick_asks_for_a_goal(self):
        with only_goals(WOOD, LATER):
            self.assertIsNone(self.ask(JEV))

    def test_jev_chooses_among_the_open_goals_and_the_call_counts(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            ask = self.ask(JEV)
            self.assertEqual((ask.kind, ask.route, [option.name for option in ask.options]),
                             ("goal", "jev", ["woodpile", "later"]))
            self.assertIn("goals_reached", ask.payload)
            http = FakeHttp({JEV_URL: {"answers": {"goal": {"choice": "later"}}}})
            chooser = Chooser(env=JEV, http=http, executor=InlineExecutor(), rng=random.Random(1), scale=1.0)
            self.assertEqual(chooser.poll(self.registry, BORN + 5), "later")
        brain = self.brain()
        self.assertEqual((brain["goal"]["name"], brain["goal"]["picker"], brain["goal_due"]), ("later", "jev", None))
        self.assertEqual((brain["calls"]["model"], len(brain["jev_calls"]), brain["last_call_at"]), (1, 1, None))
        self.assertEqual(self.world.events(1)[0]["text"], f'{self.name} set a new goal: later. "Some day."')

    def test_jev_is_asked_the_goal_question(self):
        http = Recorder({"answers": {"goal": {"choice": "later"}}})
        choices = [Option("woodpile", "A woodpile", "Wood.", "0% done", 70.0),
                   Option("later", "Later", "Some day.", "", 50.0)]
        self.assertEqual(ask_jev({}, choices, JEV, http, question="goal", instructions=GOAL_INSTRUCTIONS), "later")
        self.assertEqual(http.bodies[0]["questions"], {"goal": {
            "type": "choice", "instructions": GOAL_INSTRUCTIONS,
            "criteria": {"woodpile": "Wood. Now: 0% done.", "later": "Some day. Now: ."}}})

    def test_the_rules_pick_the_best_goal_and_then_the_purpose_in_the_same_poll(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            purpose = self.chooser().poll(self.registry, BORN + 5)
        brain = self.brain()
        self.assertEqual((brain["goal"]["name"], brain["goal"]["picker"]), ("woodpile", "utility"))
        self.assertEqual(purpose, brain["purpose"])
        self.assertIsNotNone(purpose)

    def test_a_goal_that_repeats_is_always_among_the_offers(self):
        many = [Goal(f"g{n}", f"G{n}", "", WOOD.milestones, score=lambda s, n=n: 60.0 + n, thought="") for n in range(5)]
        again = Goal("again", "Again", "", WOOD.milestones, score=lambda s: 1.0, thought="", repeat=True)
        with only_goals(*many, again):
            names = [goal.name for goal, _, _ in offers(goal_situation())]
        self.assertEqual(names, ["g4", "g3", "g2", "again"])  # L4's discovery goals are always on offer

    def test_a_single_open_goal_is_taken_without_a_model_call(self):
        with only_goals(WOOD):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            self.assertEqual(self.ask(JEV).route, "utility")

    def test_the_rules_keep_the_current_goal_at_dawn(self):
        with only_goals(WOOD, LATER):
            def keep_later(state):
                adopt_goal(state, "later", "jev", "Some day.", BORN)
                ask_for_goal(state, "dawn", BORN + 1)
            self.edit(keep_later)
            ask = self.ask()
            self.assertEqual(ask.options[0].name, "later")  # the current goal leads
            self.assertIn("(its goal now)", ask.options[0].facts)
            self.chooser().poll(self.registry, BORN + 5)
        brain = self.brain()
        self.assertEqual((brain["goal"]["name"], brain["goal"]["since"], brain["goal"]["picker"]),
                         ("later", BORN, "utility"))
        self.assertFalse(any("set a new goal" in event["text"] for event in self.world.events(100)))

    def test_a_stale_goal_answer_is_thrown_away(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            ask = self.ask()
            self.edit(lambda state: goal_state(state).update(goal_due={"id": 99, "reasons": ["dawn"], "since": BORN}))
            self.assertIsNone(store_goal(self.world, ask, Choice("later", "utility", "Some day.", NO_CALLS), BORN + 6))
        self.assertIsNone(self.brain()["goal"])

    def test_with_no_goal_open_the_ask_is_answered_at_once(self):
        with only_goals():
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            self.assertIsNone(self.ask())
        brain = self.brain()
        self.assertEqual((brain["goal"], brain["goal_due"], brain["goal_idle_at"]), (None, None, BORN + 5))

    def test_with_a_goal_a_purpose_that_ended_as_usual_is_rechosen_by_the_rules(self):
        with only_goals(WOOD, LATER):
            def ended(state):
                ensure_brain(state).update(last_chosen="gather_wood", pending=None)
                mark_trigger(state, "plan_done", BORN)
            self.edit(ended)
            self.assertEqual(prepare(SurvivalWorld(self.path, read_only=True), BORN + 90, 1.0, JEV).route, "jev")
            self.edit(lambda state: adopt_goal(state, "woodpile", "utility", "", BORN))
            self.edit(lambda state: ensure_brain(state).update(pending={"id": 50, "reasons": ["plan_done"],
                                                                        "since": BORN, "urgent": False}))
            self.assertEqual(prepare(SurvivalWorld(self.path, read_only=True), BORN + 90, 1.0, JEV).route, "utility")

    def test_a_purpose_toward_a_goal_says_which(self):
        forget_logged()
        self.edit(lambda state: ensure_brain(state).update(pending={"id": 7, "reasons": ["goal"], "since": BORN,
                                                                     "urgent": False}))
        ask = Ask(7, "utility", False, (Option("gather_wood", "gather wood", "Chop.", "", 80.0, "A woodpile"),), {},
                  BORN + 1)
        store_choice(self.world, ask, Choice("gather_wood", "utility", "Wood.", NO_CALLS), BORN + 1)
        self.assertEqual(self.world.events(1)[0]["text"],
                         f'{self.name} decided to gather wood, toward a woodpile. "Wood."')


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goal_choice.py"`
Expected: ERROR: `ImportError: cannot import name 'prepare_goal' from 'backend.survival.choosing'`

- [ ] **Step 3: Offering goals**

The block starts with the two blank lines that separate it from the section before.

In `backend/survival/goals.py`, append:

```python


# Offering goals --------------------------------------------------------------------------------

def goal_facts(s: Situation, goal: Goal) -> str:
    """Progress and the next milestones in words: "40% done; next: find iron ore, mine 3 iron ore"."""
    words = [lower(milestone.text) for _, milestone in ahead(s, goal)[:NEXT_SHOWN]]
    current = active(s)
    mine = " (its goal now)" if current is not None and current.name == goal.name else ""
    later = "" if workable(s, goal) else "; nothing to do for it right now"
    return f"{round(progress_of(s, goal) * 100)}% done{mine}; next: {', '.join(words) or 'nothing'}{later}"


def rules_score(s: Situation, goal: Goal) -> float:
    """The goal's own score, WORKABLE more when something can be done for it now, and STICK more
    for the current goal unless it stalled: the rules keep a goal for as long as it moves."""
    score = own_score(s, goal)
    if score is None:
        return 0.0
    if workable(s, goal):
        score += WORKABLE
    current = active(s)
    if current is not None and current.name == goal.name and not stalled(s):
        score += STICK
    return score


def offers(s: Situation) -> list[tuple[Goal, str, float]]:
    """The goals on offer as (goal, facts, rules score), best first: the current one while it is
    open, the best goal that repeats (L4's discovery goals are always on offer), and the best
    others, OFFERED in all. Goals given up lately are left out."""
    found = [(goal, goal_facts(s, goal), rules_score(s, goal)) for goal in GOALS.values()
             if is_open(s, goal) and not penalized(s, goal.name)]
    found.sort(key=lambda entry: -entry[2])
    current = active(s)
    kept = [entry for entry in found if current is not None and entry[0].name == current.name]
    if not any(entry[0].repeat for entry in kept):
        kept += [entry for entry in found if entry[0].repeat][:1]
    others = [entry for entry in found if entry not in kept]
    return sorted(kept + others[:OFFERED - len(kept)], key=lambda entry: -entry[2])


def reached_titles(s: Situation) -> list[str]:
    return [GOALS[name].title if name in GOALS else name.replace("_", " ") for name in reached(s)]
```

- [ ] **Step 4: The goal question**

In `backend/survival/models.py`, replace:

```python
function raises ModelError when anything goes wrong, and the caller falls back to the utility
picker.
"""
```

with:

```python
function raises ModelError when anything goes wrong, and the caller falls back to the utility
picker. L4: Jev also chooses goals, in the same call shape with a "goal" question and
GOAL_INSTRUCTIONS (backend.survival.choosing.prepare_goal).
"""
```

and replace:

```python
                "follow its traits. Choose only from the offered purposes.")
```

with:

```python
                "follow its traits. Choose only from the offered purposes.")
# L4: a goal is chosen at dawn, or when one is reached or given up, and lasts days.
GOAL_INSTRUCTIONS = ("Choose the goal this small survival pet works toward for the next few days. A goal lasts "
                     "days: keep the current one unless it is stuck or another matters much more now. Weigh its "
                     "traits, the dangers near it and what it lacks. Choose only from the offered goals.")
```

and replace:

```python
def ask_jev(payload: dict, choices: list[Option], env: Env, http: Http = post_json) -> str:
    """Jev's choice among `choices`."""
    body = {"model": env.get("TYPESAFE_MODEL") or "jev-latest", "state": payload,
            "questions": {"purpose": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": criteria(choices)}}}
```

with:

```python
def ask_jev(payload: dict, choices: list[Option], env: Env, http: Http = post_json, question: str = "purpose",
            instructions: str = INSTRUCTIONS) -> str:
    """Jev's choice among `choices`: a purpose, or (L4, question "goal") a goal."""
    asked = {"type": "choice", "instructions": instructions, "criteria": criteria(choices)}
    body = {"model": env.get("TYPESAFE_MODEL") or "jev-latest", "state": payload, "questions": {question: asked}}
```

and replace:

```python
        choice = answer["answers"]["purpose"]["choice"]
```

with:

```python
        choice = answer["answers"][question]["choice"]
```

- [ ] **Step 5: Goal choices in the Chooser**

In `backend/survival/choosing.py`, replace:

```python
While a choice is pending, the brain keeps Mimo on its current plan, or waiting.
"""
```

with:

```python
While a choice is pending, the brain keeps Mimo on its current plan, or waiting.

L4: goals. When the tick asks for a goal (backend.survival.goals: with none, at dawn, or when one
was reached or given up), `poll` answers that first. `prepare_goal` offers the open goals with
their facts and rules scores (goals.offers). Jev chooses when it is configured, more than one goal
is on offer and neither the daily cap nor its hourly budget is spent; a goal call counts toward
both, but it does not start the 60-second gap before the next model call, so the purpose choice
that follows a goal may still go to Jev. Otherwise the rules picker takes the best score (the
current goal keeps its lead). Luna never chooses goals. A rules answer is stored at once and the
purpose choice follows in the same poll; `store_goal` saves a goal unless the ask went stale, and
a new goal asks for the purpose again (goals.adopt_goal). With a goal, a purpose that ended in
the ordinary way is chosen again by the rules picker (`routine`): Jev speaks at the moments that
matter (dawn, dusk, discoveries, new goals, vital crossings and the like), and the goal carries
the day between them. A purpose that works toward a goal says so in its event.
"""
```

and replace:

```python
from backend.survival.clock import time_scale
```

with:

```python
from backend.survival.clock import time_scale
from backend.survival.goals import GOALS, active, adopt_goal, goal_state, lower, offers, reached_titles
```

and replace:

```python
    JEV_TIMEOUT, LUNA_TIMEOUT, Http, ModelError, ask_jev, ask_luna, jev_configured, luna_configured,
    luna_reflect, post_json,
```

with:

```python
    GOAL_INSTRUCTIONS, JEV_TIMEOUT, LUNA_TIMEOUT, Http, ModelError, ask_jev, ask_luna, jev_configured,
    luna_configured, luna_reflect, post_json,
```

and replace:

```python
    game_at: float = 0.0  # game seconds since the life began, when asked
```

with:

```python
    game_at: float = 0.0  # game seconds since the life began, when asked
    kind: str = "purpose"  # L4: or "goal"
```

and replace:

```python
def routine(brain: dict) -> bool:
    """A short purpose ended in the ordinary way, with nothing more significant waiting."""
    reasons = set(brain["pending"]["reasons"])
    return brain.get("last_chosen") in SHORT_PURPOSES and bool(reasons) and reasons <= ROUTINE_REASONS


def route_for(brain: dict, now: float, env: Env, game_at: float) -> str:
```

with:

```python
def routine(brain: dict, steady: bool = False) -> bool:
    """A short purpose ended in the ordinary way, with nothing more significant waiting. L4: with a
    goal (`steady`), any purpose that ended in the ordinary way: the rules picker carries the goal on
    between the moments that matter."""
    reasons = set(brain["pending"]["reasons"])
    short = steady or brain.get("last_chosen") in SHORT_PURPOSES
    return short and bool(reasons) and reasons <= ROUTINE_REASONS


def route_for(brain: dict, now: float, env: Env, game_at: float, steady: bool = False) -> str:
```

and replace:

```python
    if counters["model"] >= cap(env, DECISION_CAP) or routine(brain):
```

with:

```python
    if counters["model"] >= cap(env, DECISION_CAP) or routine(brain, steady):
```

and replace:

```python
        choices = options(s)
        payload = context_payload(s, recent_events(db, EVENTS_SHOWN))
```

with:

```python
        choices = options(s)
        payload = context_payload(s, recent_events(db, EVENTS_SHOWN))
        steady = active(s) is not None
```

and replace:

```python
    route = route_for(brain, now, env, game_at)
```

with:

```python
    route = route_for(brain, now, env, game_at, steady)
```

and replace:

```python
            purpose = (ask_jev if ask.route == "jev" else ask_luna)(ask.payload, choices, env, http)
```

with:

```python
            if ask.kind == "goal":
                purpose = ask_jev(ask.payload, choices, env, http, question="goal", instructions=GOAL_INSTRUCTIONS)
            else:
                purpose = (ask_jev if ask.route == "jev" else ask_luna)(ask.payload, choices, env, http)
```

and replace:

```python
    thought = thought_for(purpose, rng)
```

with:

```python
    thought = answer_thought(ask, purpose, rng)
```

and replace:

```python
def deadline(ask: Ask) -> float:
```

with:

```python
def answer_thought(ask: Ask, name: str, rng: random.Random) -> str:
    """What Mimo thinks of the answer: the goal's thought (L4), or one of the purpose's."""
    if ask.kind == "goal":
        return GOALS[name].thought if name in GOALS else f"I want {name.replace('_', ' ')}."
    return thought_for(name, rng)


def deadline(ask: Ask) -> float:
```

and replace:

```python
                log_event(db, now, "purpose", f'{state["name"]} decided to {phrase}. "{choice.thought}"')
```

with:

```python
                # L4: a purpose that works toward a goal says which.
                goal = next((option.goal for option in ask.options if option.name == choice.purpose), "")
                aim = f", toward {lower(goal)}" if goal else ""
                log_event(db, now, "purpose", f'{state["name"]} decided to {phrase}{aim}. "{choice.thought}"')
```

and replace:

```python
class InlineExecutor:
```

with:

```python
def goal_route(brain: dict, now: float, env: Env, game_at: float, offered: int) -> str:
    """Who chooses a goal (L4): Jev, when configured, more than one goal is on offer and neither the
    daily cap nor Jev's hourly budget is spent; else the rules picker ("utility")."""
    if offered < 2 or not jev_configured(env) or calls_today(brain, now)["model"] >= cap(env, DECISION_CAP):
        return "utility"
    if len(recent_calls(brain, "jev_calls", game_at)) >= cap(env, JEV_HOUR_CAP):
        return "utility"
    return "jev"


def prepare_goal(world: SurvivalWorld, now: float, scale: float, env: Env) -> Ask | None:
    """A read-only snapshot of the goal choice the tick asked for (L4), or None when none is due.
    With no goal open the ask is answered at once: no goal, and the tick asks again later."""
    with world.connect() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        ensure_actions(state)
        brain = goal_state(state)
        due = brain["goal_due"]
        if due is None:
            return None
        s = from_db(db, state, now, scale)
        found = offers(s)
        choices = tuple(Option(goal.name, goal.title, goal.why, facts, score) for goal, facts, score in found)
        payload = {**context_payload(s, recent_events(db, EVENTS_SHOWN)), "goals_reached": reached_titles(s)}
    game_at = max(0.0, now - state["born_at"]) * scale
    ask = Ask(due["id"], goal_route(brain, now, env, game_at, len(choices)), False, choices, payload, now, game_at,
              kind="goal")
    if not choices:
        store_goal(SurvivalWorld(world.path), ask, Choice("", "utility", "", {"model": 0, "luna": 0, "reflections": 0}),
                   now)
        return None
    return ask


def store_goal(world: SurvivalWorld, ask: Ask, choice: Choice, now: float) -> str | None:
    """Save a goal choice unless the life died or the ask went stale; count its model call. A new
    goal is logged as a routine "plan" event. Returns the goal stored."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        ensure_actions(state)
        brain = goal_state(state)
        counters = calls_today(brain, now)
        for key, count in choice.calls.items():
            counters[key] += count
        if choice.calls["model"]:
            brain["jev_calls"] = [*recent_calls(brain, "jev_calls", ask.game_at), ask.game_at]
        due = brain["goal_due"]
        fresh = due is not None and due["id"] == ask.pending_id
        if fresh and adopt_goal(state, choice.purpose or None, choice.picker, choice.thought, now):
            title = lower(GOALS[choice.purpose].title)
            log_event(db, now, "plan", f'{state["name"]} set a new goal: {title}. "{choice.thought}"')
        write_state(db, state)
        return (choice.purpose or None) if fresh else None


class InlineExecutor:
```

and replace:

```python
        ask = prepare(SurvivalWorld(path, read_only=True), now, scale, self.env)
```

with:

```python
        ask = prepare_goal(SurvivalWorld(path, read_only=True), now, scale, self.env)
        if ask is not None and ask.route == "utility":
            self.store(path, ask, decide(ask, self.env, self.http, self.rng), now)
            ask = None
        ask = ask or prepare(SurvivalWorld(path, read_only=True), now, scale, self.env)
```

and replace:

```python
        return self.store(path, ask, Choice(purpose, "utility", thought_for(purpose, self.rng), calls, error), now)
```

with:

```python
        thought = answer_thought(ask, purpose, self.rng)
        return self.store(path, ask, Choice(purpose, "utility", thought, calls, error), now)
```

and replace:

```python
        return store_choice(SurvivalWorld(path), ask, choice, now)
```

with:

```python
        if ask.kind == "goal":
            return store_goal(SurvivalWorld(path), ask, choice, now)
        return store_choice(SurvivalWorld(path), ask, choice, now)
```

- [ ] **Step 6: The headless runs' fake Jev answers each question it is asked**

In `backend/tests/test_survival_sim.py`, replace:

```python
    """Picks one of the offered purposes at random and notes the game time of every call."""
```

with:

```python
    """Picks one of the offered purposes (or goals) at random and notes the game time of every call."""
```

and replace:

```python
        offered = sorted(body["questions"]["purpose"]["criteria"])
        return {"answers": {"purpose": {"choice": self.rng.choice(offered)}}}
```

with:

```python
        # Every question it is asked gets a random pick among its choices.
        return {"answers": {question: {"choice": self.rng.choice(sorted(asked["criteria"]))}
                            for question, asked in body["questions"].items()}}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goal_choice.py"`
Expected: `Ran 11 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 971 tests` … `OK` (11 new). With no goal registered, every goal choice finds none open, and the tick asks again every 600 game seconds.

- [ ] **Step 8: Commit**

```bash
git add backend/survival/goals.py backend/survival/choosing.py backend/survival/models.py backend/tests/test_survival_sim.py backend/tests/test_survival_goal_choice.py
git commit -m "feat: Jev chooses Mimo's goal, the rules picker when Jev cannot, and the rules carry the goal between Jev's moments" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Every trip has a reason

The owner, the morning after L3's preview: "even exploring should be purposeful though." Until now explore walked to the ground Mimo had seen least, for no reason but novelty. From this task on explore goes only for a reason from a need or the goal, heads where the land likely holds what the reason needs, remembers what it finds as a place or landmark, ends early on a find, and says what for in its thought and event (resolution 15). This task builds the reasons' registry and the trip, and registers the two needs Mimo explores for: trees when it needs wood and none stands near, and food when it carries little and none is near. Task 5 adds the goals' reasons (iron, leather, a creature seed, the map), Task 6 a site for a bigger home, Task 8 curiosity's wander trip and Task 9 the discovery goals' trips, Task 10 Jev's pick of the reason and the payload, and Task 11 the headless check that no explore goes without a reason.

**Files:**
- Create: `backend/survival/trips.py` (the reasons' registry, targets, offers, the trip, looking after a walk, the words for the chooser, the model and the viewer), `backend/survival/scouting.py` (the trees and food reasons, the landmarks' `SAME_PLACE` reaches, explore's `goals.ADVANCES` check)
- Modify: `backend/survival/purposes.py` (explore goes by `trips`), `backend/survival/exploring.py` (docstring), `backend/survival/brain.py` (import scouting; `observe_step` calls `trips.look_after`), `backend/survival/pickers.py` (`Option.reasons`), `backend/survival/choosing.py` (`Choice.trip`; an explore choice stores its trip; its event and thought say what for)
- Modify tests: `backend/tests/test_survival_exploring.py`, `test_survival_purposes.py`, `test_survival_pickers.py` (what they said about aimless exploring)
- Test: `backend/tests/test_survival_trips.py`, `backend/tests/test_survival_scouting.py`

**Interfaces:**
- Consumes: Task 1's `goals.ADVANCES`, `advances`, `Goal`, `Milestone`, `adopt_goal`; `exploring.DISTANCES`, `FAR`, `HEADINGS`, `LEASH`, `DISTANCE_BONUS`, `JITTER`, `EXPLORE_ROLL`, `FOOD_WORDS`, `area_novelty`, `compass`, `dry_target`, `home_cell`, `lately`, `survey_text`; `nature.roll`; `senses.near_failure`, `natural_plants`, `trees_near`, `PICKABLE`, `TREE_SEARCH`; `work.logs_to_chop`, `wood`, `wood_goal`; `foraging.FOOD_WANTED`, `food_need`, `food_points`, `ripe_food`, `patches`, `fishing_spots`; `hunting.prey`; `creatures.kinds.land_kinds`; `creatures.moves.where`; `memory.SAME_PLACE`, `remember`, `update_place`, `patch_of`; `worldgen.tree_kind`, `biome_at`, `terrain_height`, `SEA_LEVEL`; `situation.in_tick`; `triggers.mark_trigger`.
- Produces:
  - `trips.Reason(name, words, wanted, value, score, goals=(), spots=no_spots, look=no_look, work=no_work, reach=LEASH)`: `wanted(s) -> str | None` (why, in words), `value(s, x, z) -> (float, str)` (likelihood 0..1 and what is there), `score(s) -> float`, `spots(s) -> [(x, z, words)]`, `look(s, context) -> Find | None`, `work(s) -> [steps]`; `REASONS`, `register_reason(reason)`; `LIFTS: list` of `(s) -> float` added to explore's score whatever the reason (Task 8's curiosity), `lift(s)`; `FINDS: list` of `(state, find, at)` told of every find (Task 8's curiosity).
  - `trips.Find(words, done, new=True)`; `Target(cell, score, what, direction, distance)`; `Offer(reason, words, why, score, targets)`; constants `LIKELY = 3.0`, `NEW = 1.0`, `SPOT_SLACK = 3`, `SHOWN = 3`, `OFFERED = 4`.
  - `trips.wanted_now(s, reason)`, `targets(s, reason) -> [Target]`, `offers(s) -> [Offer]` (goal-serving first, then score), `best_trip(s) -> Offer | None`, `serving(s, goal_name) -> bool`, `trip_thought(offer) -> str` ("Heading north to look for iron. My pickaxe needs it."), `start_trip(brain, offer, at, picker) -> dict`, `next_stop(s, walks) -> (work steps, cell) | None`, `look_after(state, step, context, at)`, `target_words(target)`, `trip_facts(s)`, `reasons_payload(s)`, `trip_view(brain)`.
  - `state["brain"]["trip"]`: `{"reason", "words", "why", "direction", "since", "picker", "found", "done"}`, the last trip (kept after it ends, so the walk still under way when another purpose is chosen keeps its reason; `trip_view` shows it only while Mimo explores), or None before the first.
  - Reasons `trees` ("look for trees": under 3 logs' worth of wood, or a started shelter waiting for blocks) and `food` ("look for food": under half a day's food); landmarks `grove` and `pasture` (and the reaches of Task 5's `cave` and Task 6's `site`) in `memory.SAME_PLACE`; `goals.ADVANCES["explore"]`.
  - `pickers.Option.reasons: tuple` (explore's offers, the rules' pick first); `choosing.Choice.trip: Offer | None`; `choosing.trip_for(ask, purpose) -> Offer | None`.
  - Explore's purpose event: `Pip decided to explore to look for trees[, toward <goal>]. "<thought>"`; a find: `found` event (a new place or landmark) or `explore` (known already), "Pip found birch trees.".

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_trips.py`:

```python
import random
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose and reason)
from backend.survival.choosing import Ask, Choice, decide, store_choice
from backend.survival.hatch import hatch
from backend.survival.pickers import options
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import ensure_brain
from backend.survival.trips import (
    REASONS, Find, Reason, best_trip, look_after, offers, register_reason, serving, targets, trip_facts, trip_thought,
    trip_view,
)
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_purposes import DAY, context, pet, situation

BORN = 1_000_000.0
NO_CALLS = {"model": 0, "luna": 0, "reflections": 0}

EAST = lambda s, x, z: (1.0, "east land") if x > 8 and abs(z) < 4 else (0.2, "other land")  # noqa: E731


def test_reason(name="things", wanted="I need them", value=EAST, score=50.0, **more):
    return Reason(name, f"look for {name}", lambda s: wanted, value, lambda s: score, **more)


@contextmanager
def only_reasons(*reasons):
    """The registry holds just these reasons for the test."""
    saved = dict(REASONS)
    REASONS.clear()
    for reason in reasons:
        register_reason(reason)
    try:
        yield
    finally:
        REASONS.clear()
        REASONS.update(saved)


def flat_ground(test):
    patcher = patch("backend.survival.exploring.terrain_height", lambda x, z, seed: 0)
    patcher.start()
    test.addCleanup(patcher.stop)


class ReasonTests(unittest.TestCase):
    def setUp(self):
        flat_ground(self)

    def test_explore_is_offered_only_for_a_reason_with_somewhere_to_go(self):
        with only_reasons(test_reason(wanted=None)):
            self.assertFalse(PURPOSES["explore"].valid(situation()))
        with only_reasons(test_reason(value=lambda s, x, z: (0.0, ""))):  # nowhere likely
            self.assertFalse(PURPOSES["explore"].valid(situation()))
        with only_reasons(test_reason(score=50.0)):
            s = situation()
            self.assertTrue(PURPOSES["explore"].valid(s))
            self.assertEqual(PURPOSES["explore"].score(s), 50.0)
            late = situation(clock={**DAY, "seconds_into_day": 2100.0})
            self.assertEqual(PURPOSES["explore"].score(late), 20.0)  # outdoor work late in the day
            with patch("backend.survival.trips.LIFTS", [lambda s: 12.5]):
                self.assertEqual(PURPOSES["explore"].score(situation()), 62.5)  # a lift, whatever the reason

    def test_targets_head_where_the_land_likely_holds_what_the_reason_needs(self):
        spot = test_reason("spots", value=lambda s, x, z: (0.0, ""), spots=lambda s: [(-40, 3, "the pond it found")])
        with only_reasons(test_reason(), spot):
            s = situation()
            best = targets(s, REASONS["things"])[0]
            self.assertGreater(best.cell[0], 8)
            self.assertEqual((best.what, best.direction, best.cell[1]), ("east land", "east", 1))
            self.assertEqual([(t.cell, t.what) for t in targets(s, REASONS["spots"])], [((-40, 1, 3), "the pond it found")])

    def test_targets_keep_within_the_reasons_reach_of_home(self):
        with only_reasons(test_reason(reach=20.0)):
            s = situation(places=[("home", (0, 1, 0))])
            self.assertEqual(targets(s, REASONS["things"]), [])  # every target is 32 or more away
        with only_reasons(test_reason(reach=40.0)):
            s = situation(places=[("home", (0, 1, 0))])
            self.assertLessEqual({t.distance for t in targets(s, REASONS["things"])}, {32, 33})  # none at 48 or 64

    def test_a_reason_that_serves_the_goal_comes_first_then_the_higher_score(self):
        wood = test_reason("wood", score=60.0)
        iron = test_reason("iron", score=45.0, goals=("iron_tools",))
        with only_reasons(wood, iron):
            s = situation()
            self.assertEqual([offer.reason for offer in offers(s)], ["wood", "iron"])
            self.assertEqual((serving(s, "iron_tools"), serving(s, "herd")), (True, False))  # explore could serve it
            state = pet()
            ensure_brain(state)["goal"] = {"name": "iron_tools"}  # the goal's name is all offers read
            s = situation(state)
            self.assertEqual([offer.reason for offer in offers(s)], ["iron", "wood"])

    def test_a_crashing_reason_is_left_out_and_logged_once(self):
        def boom(s):
            raise RuntimeError("boom")

        broken = Reason("broken", "break things", boom, EAST, lambda s: 90.0)
        with only_reasons(test_reason(), broken):
            with self.assertLogs("backend.survival.trips", level="ERROR") as logs:
                self.assertEqual([offer.reason for offer in offers(situation())], ["things"])
                offers(situation())
            self.assertEqual(len(logs.output), 1)

    def test_the_thought_and_facts_say_which_way_and_why(self):
        with only_reasons(test_reason()):
            s = situation()
            offer = best_trip(s)
            self.assertEqual(trip_thought(offer), "Heading east to look for things. I need them.")
            self.assertRegex(trip_facts(s), r"^to look for things \(I need them\): east 64 blocks, east land, then east "
                                            r"\d\d blocks, east land, then east \d\d blocks, east land; 0 trips so far; ")
            explore = next(option for option in options(s) if option.name == "explore")
            self.assertEqual([offer.reason for offer in explore.reasons], ["things"])


class TripTests(unittest.TestCase):
    def setUp(self):
        flat_ground(self)

    def test_a_trip_walks_whole_up_to_three_times_and_works_at_each_stop(self):
        grass = [{"kind": "mine", "target": [1, 1, 0]}]
        with only_reasons(test_reason(work=lambda s: grass)):
            s = situation()
            first = PURPOSES["explore"].plan(s, context())
            self.assertEqual(len(first), 1)
            self.assertEqual((first[0]["kind"], first[0]["reach"], first[0]["whole"]), ("walk", 3.0, True))
            self.assertGreater(first[0]["target"][0], 8)
            trip = s.brain["trip"]
            self.assertEqual({key: trip[key] for key in ("reason", "why", "direction", "picker", "done")},
                             {"reason": "things", "why": "I need them", "direction": "east", "picker": "rules",
                              "done": False})
            s.brain["batches"] = 1
            self.assertEqual(PURPOSES["explore"].plan(s, context())[:1], grass)
            s.brain["batches"] = 3
            self.assertEqual(PURPOSES["explore"].plan(s, context()), [])
            self.assertEqual(s.brain["explored"], 2)

    def test_a_trip_ends_when_its_reason_is_no_longer_wanted(self):
        with only_reasons(test_reason()):
            s = situation()
            PURPOSES["explore"].plan(s, context())
        with only_reasons(test_reason(wanted=None), test_reason("other")):
            s = situation(s.state)
            s.brain["batches"] = 1
            self.assertEqual(PURPOSES["explore"].plan(s, context()), [])

    def test_after_a_walk_mimo_looks_around_and_a_find_it_came_for_ends_the_trip(self):
        finds = iter([Find("a cave mouth", False), Find("iron ore", True, new=False)])
        heard = []
        with only_reasons(test_reason(look=lambda s, context: next(finds))), \
                patch("backend.survival.trips.FINDS", [lambda state, find, at: heard.append((find.words, at))]):
            s = situation()
            PURPOSES["explore"].plan(s, context())
            state, ctx = s.state, context()
            ctx.db = s.db
            walk = {"kind": "walk", "purpose": "explore", "path": [], "target": {"x": 40, "y": 1, "z": 0}}
            look_after(state, {**walk, "purpose": "rest"}, ctx, 5.0)  # not a trip: nothing is looked at
            look_after(state, walk, ctx, 10.0)
            look_after(state, walk, ctx, 20.0)
            look_after(state, walk, ctx, 30.0)  # the trip is done: no more looking
            self.assertEqual(heard, [("a cave mouth", 10.0), ("iron ore", 20.0)])  # every find is told of
            self.assertEqual(ctx.events, [(10.0, "found", "Pip found a cave mouth."),
                                          (20.0, "explore", "Pip found iron ore.")])
            self.assertEqual((state["brain"]["trip"]["found"], state["brain"]["trip"]["done"]), ("iron ore", True))
            self.assertIn("discovery", state["brain"]["pending"]["reasons"])
            s = situation(state)
            s.brain["batches"] = 1
            self.assertEqual(PURPOSES["explore"].plan(s, context()), [])

    def test_choosing_explore_goes_for_the_rules_reason_and_says_so(self):
        with only_reasons(test_reason("wood", score=60.0), test_reason("iron", score=45.0)):
            s = situation()
            found = tuple(option for option in options(s) if option.name == "explore")
        ask = Ask(1, "utility", False, found, {}, 0.0)
        choice = decide(ask, {}, lambda *args: {}, random.Random(1))
        self.assertEqual((choice.purpose, choice.trip.reason), ("explore", "wood"))
        self.assertEqual(choice.thought, "Heading east to look for wood. I need them.")


class StoreTests(unittest.TestCase):
    def setUp(self):
        flat_ground(self)
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        life = hatch(registry, random.Random(8), timestamp=BORN)
        self.world, self.name = SurvivalWorld(registry.world_path(life)), life["name"]

    def tearDown(self):
        self.directory.cleanup()

    def store(self, pending_id, choice, options_, at):
        """Store the choice for a pending ask; the purpose events it logged."""
        with self.world.transaction() as db:
            state = read_state(db)
            ensure_brain(state).update(pending={"id": pending_id, "reasons": ["plan_done"], "since": at,
                                                "urgent": False}, purpose=None)
            write_state(db, state)
        before = {event["id"] for event in self.world.events(50)}
        store_choice(self.world, Ask(pending_id, "utility", False, options_, {}, at), choice, at)
        return [event["text"] for event in self.world.events(50) if event["id"] not in before]

    def test_choosing_explore_stores_the_trip_and_its_event_says_what_for(self):
        with only_reasons(test_reason()):
            explore = tuple(option for option in options(situation()) if option.name == "explore")
        offer = explore[0].reasons[0]
        thought = trip_thought(offer)
        logged = self.store(3, Choice("explore", "utility", thought, NO_CALLS, trip=offer), explore, BORN + 1)
        self.assertEqual(logged, [f'{self.name} decided to explore to look for things. "Heading east to look for '
                                  f'things. I need them."'])
        trip = self.world.state()["brain"]["trip"]
        self.assertEqual((trip["reason"], trip["picker"], trip["since"]), ("things", "utility", BORN + 1))
        self.store(4, Choice("rest", "utility", "Hm.", NO_CALLS), (), BORN + 2)
        brain = self.world.state()["brain"]
        self.assertEqual((brain["trip"]["reason"], trip_view(brain)), ("things", None))  # kept, but not exploring


if __name__ == "__main__":
    unittest.main()
```

Create `backend/tests/test_survival_scouting.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose and reason)
from backend.survival.goals import Goal, Milestone, advances
from backend.survival.grid import Grid
from backend.survival.memory import places
from backend.survival.trips import REASONS, best_trip
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_purposes import context, pet, situation

TREES_EAST = lambda seed, x, z, radius: [(x, z, 0)] * 3 if x > 8 and abs(z) < 4 else []  # noqa: E731
BUSHES_EAST = lambda seed, x, z, radius, kinds: [(x, 1, z)] if x > 8 and abs(z) < 4 else []  # noqa: E731
FED = {"berries": 10}  # 80 hunger of food: no need to look for more


def with_cells(cells):
    """Stone at y <= 0 and air above, with `cells` overriding single cells."""
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("stone" if y <= 0 else "air"))


def shelter_goal(name):
    return Goal(name, name, "", (Milestone("Gather", lambda s: 0.0, ("explore",)),), score=lambda s: 50.0, thought="")


class TreesTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("backend.survival.exploring.terrain_height", lambda x, z, seed: 0),
                            ("backend.survival.scouting.trees_near", TREES_EAST)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_with_wood_wanted_and_no_tree_near_mimo_looks_for_trees_where_they_grow(self):
        s = situation(pet(inventory=dict(FED)))
        offer = best_trip(s)
        self.assertEqual((offer.reason, offer.why, offer.targets[0].direction),
                         ("trees", "I am out of wood and no tree stands near", "east"))
        self.assertEqual(offer.targets[0].what, "oak trees")
        self.assertIsNone(REASONS["trees"].wanted(situation(pet(inventory={**FED, "oak_log": 20}))))  # wood enough
        self.assertIsNone(REASONS["trees"].wanted(situation(pet(inventory={**FED, "oak_log": 5}))))  # not low
        tree = {(5, y, 0): "oak_log" for y in range(1, 5)}
        with patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [(5, 0, 0)]):
            self.assertIsNone(REASONS["trees"].wanted(situation(pet(inventory=dict(FED)), grid=with_cells(tree))))

    def test_trees_in_sight_after_a_walk_are_remembered_as_a_grove_and_end_the_trip(self):
        tree = {(5, y, 0): "oak_log" for y in range(1, 5)}
        with patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [(5, 0, 0)]):
            s = situation(pet(inventory=dict(FED)), grid=with_cells(tree))
            find = REASONS["trees"].look(s, context())
            self.assertEqual((find.words, find.done, find.new), ("oak trees", True, True))
            self.assertEqual([(place["x"], place["note"]) for place in places(s.db, ("grove",))], [(5, "oak")])
            self.assertFalse(REASONS["trees"].look(s, context()).new)  # the same wood: known already
        far = situation(pet(inventory=dict(FED)), places=[("grove", (-60, 1, 0))])
        self.assertEqual(REASONS["trees"].spots(far), [(-60, 0, "the oak trees it found")])

    def test_explore_for_trees_advances_the_goals_wood_is_for(self):
        s = situation(pet(inventory=dict(FED)))
        self.assertTrue(advances(s, "explore", shelter_goal("first_shelter")))
        self.assertFalse(advances(s, "explore", shelter_goal("herd")))
        self.assertTrue(advances(s, "gather_wood", shelter_goal("herd")))  # no check of its own


class FoodTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("backend.survival.exploring.terrain_height", lambda x, z, seed: 0),
                            ("backend.survival.scouting.natural_plants", BUSHES_EAST)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_short_of_food_with_none_near_mimo_looks_for_it_where_it_grows(self):
        wood = {"oak_log": 20}  # no need for trees
        offer = best_trip(situation(pet(inventory=dict(wood))))
        self.assertEqual((offer.reason, offer.why, offer.targets[0].what), ("food", "I carry little food and none is near", "berries"))
        self.assertEqual(offer.score, 30.0 + 60.0 / 3 + (100.0 - START_VITALS["hunger"]) / 3)
        hungry = situation(pet(inventory=dict(wood), vitals={**START_VITALS, "hunger": 30.0}))
        self.assertEqual(REASONS["food"].wanted(hungry), "I am hungry and no food is near")
        self.assertIsNone(REASONS["food"].wanted(situation(pet(inventory={**wood, **FED}))))

    def test_ripe_food_in_sight_after_a_walk_is_remembered_and_ends_the_trip(self):
        bush = (6, 1, 0)
        with patch("backend.survival.senses.natural_plants", lambda seed, x, z, radius, kinds: [bush]):
            s = situation(pet(), grid=with_cells({bush: "berry_bush_ripe"}))
            find = REASONS["food"].look(s, context())
        self.assertEqual((find.words, find.done, find.new), ("berries", True, True))
        food = places(s.db, ("food",))
        self.assertEqual([(place["x"], place["data"]["ripe"]) for place in food], [(6, 1)])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_trips.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.trips'`

- [ ] **Step 3: Reasons and trips**

Create `backend/survival/trips.py`:

```python
"""Explore trips with a reason (L4, from the owner: "even exploring should be purposeful").

Mimo never explores just to see the least-explored ground. Every trip has a reason, and the
reason comes from its goal or from a need: look for trees when none stands near and it needs
wood, look for food when there is none near, look for iron for its pickaxe, find leather for
armor or a creature seed for a pen, scout for flat ground for a bigger home, map the land.
Reasons are a registry: the module that knows the need registers its Reason
(backend.survival.scouting the needs; backend.survival.life_goals and backend.survival.homes
their goals'). A Reason has:
- `wanted(s)`: why Mimo wants it now, in words ("my pickaxe needs it"), or None;
- `value(s, x, z)`: how likely the land around a column holds it, from 0 to 1, and what is there
  in words ("a cave mouth"). Only the terrain is read (worldgen: biome, height, cave openings,
  rocks, trees and plants), so the same land always scores the same;
- `spots(s)`: columns to head for as they are, (x, z, words): remembered places and landmarks,
  things in sight, or the least-explored ground for the map;
- `look(s, context)`: after each walk of the trip, what Mimo sees where it stands. It remembers
  what it finds as a place or landmark and returns a Find: the words, whether it is what the trip
  was for, and whether the place is new to it;
- `work(s)`: steps to take at each stop before walking on (breaking tall grass for a seed);
- `goals`: the goals it serves; `score(s)`: explore's score with it, in the leisure band;
- `reach`: how far from home its targets may lie, LEASH (60) like every trip. L5's frontier
  hooks in here: its "seek riches farther out" will be a reason with a longer reach, offered only
  to a pet geared for the ring it leads into. L4 does not build it.

Targets (`targets`) are the reason's spots and the dry columns at 16 headings 32, 48 and 64 blocks
away whose land may hold what it needs. Each scores LIKELY times that likelihood (1 for a spot)
plus NEW times how new the land around it is (exploring.area_novelty, 0 to 1), plus exploring's
small bonus for distance and its seeded jitter. The rules that keep explore safe still hold: never
in water, never within 4 blocks of a step that just failed, never in the patch Mimo stands in, never
in one it visited less than a game day ago (spots excepted: they are where it means to go), and
with a home known, never beyond the reason's reach from it unless nearer than Mimo is now.

`offers` are the reasons wanted now that have a target, best first by the rules: a reason that
serves Mimo's goal first, then the higher score; at most OFFERED. explore (purposes.py) is on offer
only while there is one, and scores the first one's score. When explore is chosen the worker stores
the trip in the brain (backend.survival.choosing: the rules' reason, or Jev's pick among the
offers): state["brain"]["trip"] = {"reason", "words", "why", "direction", "since", "picker",
"found", "done"}, kept until the next trip (the viewer and the model see it only while Mimo
explores, `trip_view`). The tick's planner (`next_stop`) keeps to it, or picks by the rules itself
when there is none, it is done, or its reason is no longer wanted when the trip starts. Each batch
does the reason's work at a stop and walks to the best target; the walk goes all the way or not at
all. After each walk (`look_after`, from brain.observe_step) Mimo looks around. A find is logged
("Pip found birch trees.": a "found" event when the place is new to it, else a routine "explore"
one), and a find that is what the trip was for ends it (`done`) and asks for a new choice (a
"discovery"), so the purpose that follows up on it comes next: gather_wood for trees, mine_ore for
ore, hunt for animals, build_pen for a seed, improve_home for a site. A trip also ends when its
reason is no longer wanted or after three walks.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from backend.survival import nature
from backend.survival.exploring import (
    DISTANCE_BONUS, DISTANCES, EXPLORE_ROLL, FAR, HEADINGS, JITTER, LEASH, area_novelty, compass, dry_target,
    home_cell, lately, survey_text,
)
from backend.survival.grid import Cell
from backend.survival.memory import patch_of
from backend.survival.once import log_once
from backend.survival.senses import near_failure
from backend.survival.situation import Situation, in_tick
from backend.survival.triggers import ensure_brain, mark_trigger

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

LIKELY = 3.0  # a target scores this much for land sure to hold what the reason needs...
NEW = 1.0  # ...and this much for land Mimo never saw (area novelty over 9)
SPOT_SLACK = 3  # a spot's column may be this far from the dry cell Mimo stands on to see it
SHOWN = 3  # targets kept per offer: the facts and the model payload name them
OFFERED = 4  # reasons offered at a choice


@dataclass(frozen=True)
class Find:
    words: str  # "a cave mouth, with iron ore in its walls"
    done: bool  # it is what the trip was for
    new: bool = True  # a place or landmark Mimo did not know yet


def no_spots(s: Situation) -> list[tuple[int, int, str]]:
    return []


def no_look(s: Situation, context: ActionContext) -> Find | None:
    return None


def no_work(s: Situation) -> list[dict]:
    return []


@dataclass(frozen=True)
class Reason:
    name: str
    words: str  # completes "Pip went exploring to ...": "look for iron"
    wanted: Callable[[Situation], str | None]
    value: Callable[[Situation, int, int], tuple[float, str]]
    score: Callable[[Situation], float]
    goals: tuple[str, ...] = ()
    spots: Callable[[Situation], list[tuple[int, int, str]]] = no_spots
    look: Callable[[Situation, "ActionContext"], Find | None] = no_look
    work: Callable[[Situation], list[dict]] = no_work
    reach: float = LEASH


REASONS: dict[str, Reason] = {}
# Functions of the Situation that add to explore's score whatever its reason (L4's curiosity lifts a
# restless pet's trips into the work band).
LIFTS: list = []
# Functions of (state, Find, at) told of every find after it is logged (L4's curiosity: a place new
# to Mimo is a discovery).
FINDS: list = []


def register_reason(reason: Reason) -> Reason:
    """Add a reason, or replace the one with the same name."""
    REASONS[reason.name] = reason
    return reason


def lift(s: Situation) -> float:
    """What LIFTS add to explore's score now; one that crashes adds nothing (logged once)."""
    total = 0.0
    for extra in LIFTS:
        try:
            total += float(extra(s))
        except Exception as error:
            log_once(logger, "explore lift", error)
    return total


@dataclass(frozen=True)
class Target:
    cell: Cell
    score: float
    what: str  # "a cave mouth"
    direction: str  # "north"
    distance: int  # blocks from where Mimo stands


@dataclass(frozen=True)
class Offer:
    reason: str
    words: str
    why: str
    score: float
    targets: tuple[Target, ...]  # best first, at most SHOWN


def guarded(reason: Reason, part: str, call: Callable, fallback):
    """A reason's function; one that crashes counts as `fallback` (logged once)."""
    try:
        return call()
    except Exception as error:
        log_once(logger, f"trip reason {reason.name} {part}", error)
        return fallback


def wanted_now(s: Situation, reason: Reason) -> str | None:
    """Why Mimo wants what the reason looks for, read once per Situation; None when it does not."""
    return s.sensed(f"trip wanted {reason.name}", lambda: guarded(reason, "wanted", lambda: reason.wanted(s), None))


def beyond(s: Situation, reason: Reason, home: Cell | None, cell: Cell) -> bool:
    """Farther from home than the reason's reach, and no nearer to it than Mimo is now."""
    if home is None:
        return False
    away = math.hypot(cell[0] - home[0], cell[2] - home[2])
    return away > reason.reach and away >= math.hypot(s.here[0] - home[0], s.here[2] - home[2])


def stand_near(s: Situation, x: int, z: int) -> Cell | None:
    """A dry cell to stand on at the column, or the nearest one within SPOT_SLACK of it."""
    for dx, dz in sorted(((dx, dz) for dx in range(-SPOT_SLACK, SPOT_SLACK + 1)
                          for dz in range(-SPOT_SLACK, SPOT_SLACK + 1)), key=lambda d: (math.hypot(*d), d)):
        cell = dry_target(s.grid, s.seed, x + dx, z + dz)
        if cell is not None:
            return cell
    return None


def targets(s: Situation, reason: Reason) -> list[Target]:
    """Where the trip may head for this reason, best first (see the module docstring)."""
    def look() -> list[Target]:
        x, _, z = s.here
        here, home, turn = patch_of(x, z), home_cell(s), s.brain["explored"]
        found: dict[Cell, Target] = {}

        def add(cell: Cell, likely: float, what: str) -> None:
            distance = round(math.hypot(cell[0] - x, cell[2] - z))
            new = area_novelty(s, patch_of(cell[0], cell[2])) / 9
            jitter = JITTER * nature.roll(s.seed, (cell[0], 0, cell[2]), EXPLORE_ROLL, turn)
            score = LIKELY * min(1.0, likely) + NEW * new + DISTANCE_BONUS * distance / FAR + jitter
            if cell not in found or found[cell].score < score:
                found[cell] = Target(cell, score, what, compass(cell[0] - x, cell[2] - z), distance)

        for sx, sz, what in guarded(reason, "spots", lambda: reason.spots(s), []):
            cell = stand_near(s, sx, sz)
            if (cell is not None and patch_of(cell[0], cell[2]) != here and not near_failure(s.state, cell)
                    and not beyond(s, reason, home, cell)):
                add(cell, 1.0, what)
        for distance in (*DISTANCES, FAR):
            for heading in range(HEADINGS):
                angle = heading * 2 * math.pi / HEADINGS
                tx, tz = x + round(math.cos(angle) * distance), z + round(math.sin(angle) * distance)
                patch = patch_of(tx, tz)
                if patch == here or lately(s, patch):
                    continue
                likely, what = guarded(reason, "value", lambda: reason.value(s, tx, tz), (0.0, ""))
                if likely <= 0:
                    continue
                cell = dry_target(s.grid, s.seed, tx, tz)
                if cell is None or near_failure(s.state, cell) or beyond(s, reason, home, cell):
                    continue
                add(cell, likely, what)
        return sorted(found.values(), key=lambda target: (-target.score, target.cell))
    return s.sensed(f"trip targets {reason.name}", look)


def serves(reason: Reason, goal: str | None) -> bool:
    return goal is not None and goal in reason.goals


def offers(s: Situation) -> list[Offer]:
    """The reasons Mimo could explore for now, with their best targets, best first: one that serves
    its goal first, then the higher score."""
    def look() -> list[Offer]:
        goal = (s.brain.get("goal") or {}).get("name")
        found = []
        for reason in REASONS.values():
            why = wanted_now(s, reason)
            if why is None:
                continue
            aims = targets(s, reason)
            if aims:
                score = float(guarded(reason, "score", lambda: reason.score(s), 0.0))
                found.append(Offer(reason.name, reason.words, why, score, tuple(aims[:SHOWN])))
        found.sort(key=lambda offer: (not serves(REASONS[offer.reason], goal), -offer.score, offer.reason))
        return found[:OFFERED]
    return s.sensed("trip offers", look)


def best_trip(s: Situation) -> Offer | None:
    """The rules' reason to explore now, or None when Mimo has none (explore is not on offer)."""
    found = offers(s)
    return found[0] if found else None


def serving(s: Situation, goal: str) -> bool:
    """A trip on offer now would work toward `goal` (the goals' hook for explore: goals.ADVANCES)."""
    return any(serves(REASONS[offer.reason], goal) for offer in offers(s))


# The trip --------------------------------------------------------------------------------------

def sentence(words: str) -> str:
    return f"{words[:1].upper()}{words[1:]}."


def trip_thought(offer: Offer) -> str:
    """"Heading north to look for iron. My pickaxe needs it.\""""
    return f"Heading {offer.targets[0].direction} to {offer.words}. {sentence(offer.why)}"


def start_trip(brain: dict, offer: Offer, at: float, picker: str) -> dict:
    brain["trip"] = {"reason": offer.reason, "words": offer.words, "why": offer.why,
                     "direction": offer.targets[0].direction, "since": at, "picker": picker, "found": None,
                     "done": False}
    return brain["trip"]


def next_stop(s: Situation, walks: int) -> tuple[list[dict], Cell] | None:
    """The trip's next batch: the reason's work where Mimo stands (after the first walk) and the
    target to walk to; None when the trip is over (see the module docstring)."""
    brain = s.brain
    trip = brain.get("trip")
    reason = REASONS.get(trip["reason"]) if trip else None
    if brain["batches"] == 0 and (reason is None or trip.get("done") or wanted_now(s, reason) is None):
        offer = best_trip(s)
        if offer is None:
            return None
        trip, reason = start_trip(brain, offer, s.at, "rules"), REASONS[offer.reason]
    if reason is None or trip.get("done") or brain["batches"] >= walks or wanted_now(s, reason) is None:
        return None
    aims = targets(s, reason)
    if not aims:
        return None
    work = guarded(reason, "work", lambda: reason.work(s), []) if brain["batches"] > 0 else []
    brain["explored"] += 1
    trip["direction"] = aims[0].direction
    return work, aims[0].cell


def look_after(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After a walk of an explore trip: what Mimo sees there for the trip's reason (brain.observe_step)."""
    if step.get("purpose") != "explore" or step["kind"] not in ("walk", "swim") or context.db is None:
        return
    trip = ensure_brain(state).get("trip")
    reason = REASONS.get(trip["reason"]) if trip else None
    if reason is None or trip.get("done"):
        return
    find = guarded(reason, "look", lambda: reason.look(in_tick(state, context, at), context), None)
    if find is None:
        return
    trip["found"] = find.words
    context.events.append((at, "found" if find.new else "explore", f"{state['name']} found {find.words}."))
    for hook in FINDS:
        guarded(reason, "find hook", lambda: hook(state, find, at), None)
    if find.done:
        trip["done"] = True
        mark_trigger(state, "discovery", at)


# What the chooser, the model and the viewer are told ---------------------------------------------

def target_words(target: Target) -> str:
    return f"{target.direction} {target.distance} blocks, {target.what}"


def trip_facts(s: Situation) -> str:
    """explore's facts: each reason with why and its best targets, the trips so far and the survey."""
    reasons = "; or ".join(f"to {offer.words} ({offer.why}): {', then '.join(target_words(t) for t in offer.targets)}"
                           for offer in offers(s))
    return f"{reasons}; {s.brain['explored']} trips so far; {survey_text(s)}"


def reasons_payload(s: Situation) -> list[dict]:
    """The reasons to explore for a model: each with why and the directions it could head, with what
    lies there."""
    return [{"reason": offer.words, "why": offer.why,
             "directions": [{"direction": target.direction, "blocks": target.distance, "toward": target.what}
                            for target in offer.targets]} for offer in offers(s)]


def trip_view(brain: dict | None) -> dict | None:
    """The trip for /api/mimo while Mimo explores: reason, words, why, direction, what it found."""
    brain = brain or {}
    trip = brain.get("trip")
    if brain.get("purpose") != "explore" or not trip:
        return None
    return {"reason": trip.get("reason"), "words": trip.get("words"), "why": trip.get("why"),
            "direction": trip.get("direction"), "found": trip.get("found")}
```

Create `backend/survival/scouting.py`:

```python
"""The needs Mimo explores for (L4), registered in backend.survival.trips.

- trees, "look for trees": Mimo is low on wood (under 3 logs' worth, when gather_wood hurries), or
  its home needs wood (a shelter it started waits for blocks, or a home of its own or a bigger one
  is its goal), it carries less than work.wood_goal, and no tree stands within 24 blocks, so
  gather_wood is not on offer. The more trees worldgen grew within 12 blocks
  of a spot, the likelier (3 or more is sure); a wood it found before is a spot of its own. Found
  once a tree stands in sight: remembered as a "grove" landmark with its wood ("Pip found birch
  trees."), and gather_wood follows. 45 plus a fifth of curiosity, as explore scored with no tree
  in sight before L4. It serves the goals wood is for: a home, iron tools and a bigger home.
- food, "look for food": Mimo carries less than half a day's food and no food work is on offer: no
  ripe plant or food patch to go back to, no fishing spot, no animal to hunt. Wild berry bushes and
  mushrooms (worldgen's plants, 2 within 10 blocks is sure) are likeliest, then water with fish,
  then grazing land. Found once food work is on offer again: ripe food is remembered as a food
  place, water as a water place, an animal's ground as a "pasture" landmark. It scores like food
  work (30, plus a third of the food Mimo lacks and a third of its hunger) and serves the full
  larder.

The goals' own reasons register with their goals (backend.survival.life_goals: iron, hides, a
creature seed, the map; backend.survival.homes: a site for a bigger home). Landmarks are places
(memory_places): "grove", "pasture", "cave" and "site", each one per so many blocks
(memory.SAME_PLACE). This module also tells the goals when explore advances one
(goals.ADVANCES): when a trip on offer serves it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, biome_at, terrain_height, tree_kind
from backend.survival.creatures.hunting import prey
from backend.survival.creatures.kinds import land_kinds
from backend.survival.creatures.moves import where
from backend.survival.exploring import FOOD_WORDS
from backend.survival.foraging import FOOD_WANTED, fishing_spots, food_need, food_points, patches, ripe_food
from backend.survival.building import building_need
from backend.survival.goals import ADVANCES
from backend.survival.memory import SAME_PLACE, cell_of, remember, update_place
from backend.survival.senses import PICKABLE, TREE_SEARCH, natural_plants, trees_near
from backend.survival.situation import Situation
from backend.survival.steps import label
from backend.survival.trips import Find, Reason, register_reason, serving
from backend.survival.work import logs_to_chop, wood, wood_goal

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

GROVE = "grove"  # a landmark: trees Mimo found on a trip, the note says which wood
PASTURE = "pasture"  # a landmark: where Mimo found an animal, the note says which
SAME_PLACE.update({GROVE: (24.0, (GROVE,)), PASTURE: (24.0, (PASTURE,)), "cave": (16.0, ("cave",)),
                   "site": (16.0, ("site",))})
LOW_WOOD = 3.0  # logs' worth of wood below which Mimo goes looking for trees
HOME_GOALS = ("first_shelter", "better_home")  # goals whose blocks wood is
TREE_GROVE = 12  # blocks around a spot whose trees count
SURE_TREES = 3
FOOD_SHORT = FOOD_WANTED / 2  # hunger of food carried below which Mimo goes looking for more
PLANT_REACH = 10  # blocks around a spot whose wild food counts
SURE_PLANTS = 2
WATER_SAMPLES = ((0, 0), (8, 0), (-8, 0), (0, 8), (0, -8))


# trees -----------------------------------------------------------------------------------------

def trees_in_sight(s: Situation) -> bool:
    return s.sensed("trees in sight", lambda: bool(logs_to_chop(s)))


def trees_wanted(s: Situation) -> str | None:
    have = wood(s.inventory)
    if have >= wood_goal(s) or trees_in_sight(s):
        return None
    if have < LOW_WOOD:
        return "I am out of wood and no tree stands near"
    if building_need(s) > 0 or (s.brain.get("goal") or {}).get("name") in HOME_GOALS:
        return "my home needs wood and no tree stands near"
    return None


def trees_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    near = trees_near(s.seed, x, z, TREE_GROVE)
    if not near:
        return 0.0, ""
    return min(1.0, len(near) / SURE_TREES), f"{tree_kind(near[0][0], near[0][1], s.seed)} trees"


def grove_spots(s: Situation) -> list[tuple[int, int, str]]:
    return [(place["x"], place["z"], f"the {place['note'] or 'oak'} trees it found") for place in s.places
            if place["kind"] == GROVE and s.distance(cell_of(place)) > TREE_SEARCH]


def trees_look(s: Situation, context: ActionContext) -> Find | None:
    logs = logs_to_chop(s)
    if not logs:
        return None
    x, y, z = logs[0]
    kind = tree_kind(x, z, s.seed)
    return Find(f"{kind} trees", True, remember(s.db, GROVE, (x, y, z), s.at, kind))


register_reason(Reason(
    "trees", "look for trees", trees_wanted, trees_value, lambda s: 45.0 + s.trait("curiosity") / 5,
    goals=("first_shelter", "iron_tools", "better_home"), spots=grove_spots, look=trees_look))


# food ------------------------------------------------------------------------------------------

def food_work(s: Situation) -> bool:
    """Food work would be on offer: ripe food or a food patch to go back to, fish, an animal."""
    return bool(ripe_food(s) or patches(s) or fishing_spots(s) or prey(s))


def food_wanted(s: Situation) -> str | None:
    if food_points(s) >= FOOD_SHORT or food_need(s) <= 0 or food_work(s):
        return None
    if s.vitals["hunger"] < 50:
        return "I am hungry and no food is near"
    return "I carry little food and none is near"


def food_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    counts = {block: len(natural_plants(s.seed, x, z, PLANT_REACH, (block,))) for block in PICKABLE
              if block not in s.poisons}
    most = max(counts, key=lambda block: counts[block], default=None)
    if most is not None and counts[most] > 0:
        return min(1.0, sum(counts.values()) / SURE_PLANTS), FOOD_WORDS[most]
    if any(terrain_height(x + dx, z + dz, s.seed) < SEA_LEVEL for dx, dz in WATER_SAMPLES):
        return 0.5, "water with fish"
    if land_kinds(biome_at(x, z, s.seed)):
        return 0.3, "grazing land"
    return 0.0, ""


def food_look(s: Situation, context: ActionContext) -> Find | None:
    ripe = ripe_food(s)
    if ripe:
        new = remember(s.db, "food", ripe[0], s.at)
        if new:
            update_place(s.db, "food", ripe[0], {"ripe": len(ripe), "seen_at": s.at})
        return Find(FOOD_WORDS.get(s.grid.material(*ripe[0]), "wild food"), True, new)
    spots = fishing_spots(s)
    if spots:
        return Find("water with fish", True, remember(s.db, "water", spots[0][1], s.at))
    animals = prey(s)
    if animals:
        kind = animals[0]["kind"]
        new = remember(s.db, PASTURE, where(animals[0], s.at), s.at, kind)
        return Find(f"a {label(kind)} to hunt", True, new)
    return None


register_reason(Reason(
    "food", "look for food", food_wanted, food_value,
    lambda s: 30.0 + food_need(s) / 3 + (100.0 - s.vitals["hunger"]) / 3,
    goals=("full_larder",), look=food_look))


# explore and the goals -------------------------------------------------------------------------

ADVANCES["explore"] = lambda s, goal: serving(s, goal.name)
```

- [ ] **Step 4: Explore goes for a reason**

In `backend/survival/purposes.py`, replace:

```python
- leisure, 0-65: rest 10-40 and explore 0-65: 20-65 (45 and up with no tree in sight) less up to
  20 as the land within 64 blocks runs out of ground Mimo has not seen, and minus late, but
  never below 0.
```

with:

```python
- leisure, 0-65: rest 10-40, and explore, which L4 offers only for a reason (backend.survival.trips):
  it scores its reason's score, 30-65 (looking for food scores like food work), minus late, never
  below 0.
```

and replace:

```python
from backend.survival.beds import to_bed
from backend.survival.exploring import explore_target, survey, survey_text
```

with:

```python
from backend.survival.beds import to_bed
```

and replace:

```python
from backend.survival.senses import TREE_SEARCH, WATER_SIGHT, afloat, shores_near, trees_near
```

with:

```python
from backend.survival.senses import WATER_SIGHT, afloat, shores_near
```

and replace:

```python
from backend.survival.steps import FOOD, FOOD_HEALTH
```

with:

```python
from backend.survival.steps import FOOD, FOOD_HEALTH
from backend.survival.trips import best_trip, lift, next_stop, trip_facts
```

and replace:

```python
EXPLORE_REACH = 3.0
LITTLE_NEW_LAND = 20.0  # explore scores this much lower once every patch within 64 blocks was seen
```

with:

```python
EXPLORE_REACH = 3.0
```

Then replace the whole `explore_valid` function with:

```python
def explore_valid(s: Situation) -> bool:
    """By day, while Mimo has a reason to explore and somewhere to go for it (backend.survival.trips)."""
    return not s.night and s.phase != "dusk" and best_trip(s) is not None
```

Then replace the whole `explore_score` function with:

```python
def explore_score(s: Situation) -> float:
    """The score of the best reason to explore (trips.best_trip), plus what lifts every trip
    (trips.LIFTS), less the late-day penalty."""
    offer = best_trip(s)
    return 0.0 if offer is None else max(0.0, offer.score + lift(s) - late_penalty(s))
```

In `backend/survival/purposes.py`, replace:

```python
def explore_facts(s: Situation) -> str:
    x, _, z = s.here
    trees = len(trees_near(s.seed, x, z, TREE_SEARCH))
    return f"{trees} trees within {TREE_SEARCH} blocks, {s.brain['explored']} trips so far; {survey_text(s)}"


def plan_explore(s: Situation, context: ActionContext) -> list[dict]:
    """Up to three walks per choice, each to the dry spot Mimo has seen least (exploring.py). A
    walk goes all the way or fails at once, so it never ends in a pit or the water."""
    if s.brain["batches"] >= EXPLORE_WALKS:
        return []
    target = explore_target(s)
    if target is None:
        return []
    s.brain["explored"] += 1
    return [{**walk_to(target, EXPLORE_REACH), "whole": True}]
```

with:

```python
def plan_explore(s: Situation, context: ActionContext) -> list[dict]:
    """Up to three walks per choice, each to the best target for the trip's reason (trips.next_stop),
    after the reason's work where Mimo stands. A walk goes all the way or fails at once, so it
    never ends in a pit or the water."""
    stop = next_stop(s, EXPLORE_WALKS)
    if stop is None:
        return []
    work, target = stop
    return [*work, {**walk_to(target, EXPLORE_REACH), "whole": True}]
```

and replace:

```python
    "explore", "explore", "Walk to land it has not seen yet, up to three times, never into water.",
    valid=explore_valid, facts=explore_facts, score=explore_score, plan=plan_explore,
```

with:

```python
    "explore", "explore", "Go looking for something it needs, where the land likely holds it: up to three walks, "
    "never into water.",
    valid=explore_valid, facts=trip_facts, score=explore_score, plan=plan_explore,
```

In `backend/survival/exploring.py`, replace:

```python
explore (purposes.py) walks to `explore_target`: out of 16 headings at 32 and 48 blocks (and 64
too once all of those are well explored), the dry spot whose patch and its 8 neighbours Mimo has
seen least (few visits, long ago), with a small bonus for distance and a small seeded jitter, so
ties vary from trip to trip. A spot is never in water (natural or not: the Grid is asked), never
within 4 blocks of a step that just failed, never in the patch Mimo stands in or one it visited
less than a game day ago (so it does not pace between two spots), and with a home known never
farther than 60 blocks from it, so go_home (64 blocks) still finds its way back by dusk. With no
such spot there is nothing to explore.
```

with:

```python
`explore_target` is the least-explored spot: out of 16 headings at 32 and 48 blocks (and 64 too
once all of those are well explored), the dry spot whose patch and its 8 neighbours Mimo has seen
least (few visits, long ago), with a small bonus for distance and a small seeded jitter, so ties
vary from trip to trip. A spot is never in water (natural or not: the Grid is asked), never within
4 blocks of a step that just failed, never in the patch Mimo stands in or one it visited less than
a game day ago (so it does not pace between two spots), and with a home known never farther than
60 blocks from it, so go_home (64 blocks) still finds its way back by dusk. L4: explore goes only
for a reason (backend.survival.trips). Mapping the land heads for explore_target; every other
reason heads where the land likely holds what it needs, under the same rules.
```

and replace:

```python
it has not seen yet in each of the 8 compass directions (north is -z, east is +x). explore scores
lower with little new land near, and its facts and the model payload (`exploration_payload`) say
the same in words and numbers.
```

with:

```python
it has not seen yet in each of the 8 compass directions (north is -z, east is +x). explore's facts
end with it in words, and the model payload (`exploration_payload`) says the same in numbers.
```

- [ ] **Step 5: The brain looks around after each walk of a trip**

In `backend/survival/brain.py`, replace:

```python
event, one a step; it asks for a choice at most once a game hour).
"""
```

with:

```python
event, one a step; it asks for a choice at most once a game hour).
L4: after each walk of an explore trip Mimo looks around for what the trip is for
(backend.survival.trips.look_after); a find that is what it came for ends the trip.
"""
```

and replace:

```python
from backend.survival.creatures import defense, gear, hunting  # noqa: F401  (L1's hunt; L2's make_gear, fight, flee)
```

with:

```python
from backend.survival.creatures import defense, gear, hunting  # noqa: F401  (L1's hunt; L2's make_gear, fight, flee)
from backend.survival import scouting  # noqa: F401  (L4's trips)
```

and replace:

```python
from backend.survival.tick import Mind
```

with:

```python
from backend.survival.tick import Mind
from backend.survival.trips import look_after
```

and replace:

```python
        announce_find(state, step, context, at, *finds[0])  # one a step: the rest are remembered quietly
```

with:

```python
        announce_find(state, step, context, at, *finds[0])  # one a step: the rest are remembered quietly
    look_after(state, step, context, at)
```

- [ ] **Step 6: The chooser stores the trip and says what for**

In `backend/survival/pickers.py`, replace:

```python
(`steer`, with the rules in backend.survival.goals).
"""
```

with:

```python
(`steer`, with the rules in backend.survival.goals).
Explore's option carries its reasons to explore, the rules' pick first (backend.survival.trips).
"""
```

and replace:

```python
from backend.survival.situation import Situation
```

with:

```python
from backend.survival.situation import Situation
from backend.survival.trips import offers
```

and replace:

```python
    goal: str = ""  # L4: the title of the goal it works toward, if any
```

with:

```python
    goal: str = ""  # L4: the title of the goal it works toward, if any
    reasons: tuple = ()  # L4: explore's reasons (trips.Offer), the rules' pick first
```

and replace:

```python
        found.append(Option(purpose.name, purpose.phrase, purpose.description, facts, score))
```

with:

```python
        reasons = tuple(offers(s)) if purpose.name == "explore" else ()
        found.append(Option(purpose.name, purpose.phrase, purpose.description, facts, score, reasons=reasons))
```

In `backend/survival/choosing.py`, replace:

```python
the day between them. A purpose that works toward a goal says so in its event.
"""
```

with:

```python
the day between them. A purpose that works toward a goal says so in its event.
L4: explore always goes for a reason (backend.survival.trips). Its option carries the reasons on
offer, the rules' pick first, and choosing explore goes for that one: the trip is stored in the
brain, and its event and thought say what for ("Pip decided to explore to look for iron, toward
iron tools. \"Heading north to look for iron. My pickaxe needs it.\"").
"""
```

and replace:

```python
from backend.survival.triggers import HOUR, ensure_brain
```

with:

```python
from backend.survival.triggers import HOUR, ensure_brain
from backend.survival.trips import Offer, start_trip, trip_thought
```

and replace:

```python
    error: str | None = None
```

with:

```python
    error: str | None = None
    trip: Offer | None = None  # L4: explore's reason (trips.Offer)
```

and replace:

```python
    thought = answer_thought(ask, purpose, rng)
```

with:

```python
    trip = trip_for(ask, purpose)
    thought = trip_thought(trip) if trip is not None else answer_thought(ask, purpose, rng)
```

and replace:

```python
    return Choice(purpose, picker, thought, calls, "; ".join(errors) or None)


def answer_thought(
```

with:

```python
    return Choice(purpose, picker, thought, calls, "; ".join(errors) or None, trip)


def trip_for(ask: Ask, purpose: str) -> Offer | None:
    """L4: the reason an explore choice goes for: the rules' pick, the first offered."""
    option = next((option for option in ask.options if option.name == purpose), None)
    if ask.kind != "purpose" or purpose != "explore" or option is None or not option.reasons:
        return None
    return option.reasons[0]


def answer_thought(
```

and replace:

```python
            new_thought = choice.picker != "utility" and choice.thought != state.get("last_thought")
            apply_choice(state, choice, now)
            if new_purpose or new_thought:
                purpose = PURPOSES.get(choice.purpose)
                phrase = purpose.phrase if purpose else choice.purpose.replace("_", " ")
```

with:

```python
            new_thought = choice.picker != "utility" and choice.thought != state.get("last_thought")
            trip = brain.get("trip") or {}
            new_reason = choice.trip is not None and trip.get("reason") != choice.trip.reason
            fresh_trip = new_reason or brain["purpose"] != choice.purpose or trip.get("done")
            apply_choice(state, choice, now)
            if choice.trip is not None and fresh_trip:
                start_trip(brain, choice.trip, now, choice.picker)
            if new_purpose or new_thought or new_reason:
                purpose = PURPOSES.get(choice.purpose)
                phrase = purpose.phrase if purpose else choice.purpose.replace("_", " ")
                if choice.trip is not None:  # L4: explore says what for
                    phrase = f"{phrase} to {choice.trip.words}"
```

- [ ] **Step 7: The tests that knew explore as aimless**

The old explore tests scored explore by the trees in sight and the land left unseen, and planned it with no reason; now it scores and plans by its reason. `explore_target` stays, the least-explored spot, which Task 5's map reason heads for.

In `backend/tests/test_survival_exploring.py`, replace:

```python
from backend.survival.exploring import dry_target, explore_target
```

with:

```python
from backend.survival.exploring import dry_target, explore_target, survey_text
```

Then replace the whole `test_explore_walks_whole_to_dry_ground_and_never_into_the_lake` method with:

```python
    def test_the_least_explored_spot_is_dry_ground_and_never_in_the_lake(self):
        lake = lambda x, z: x >= 12  # noqa: E731
        grid = self.world(lake)
        state, visited, at = pet(), [], 0.0
        for trip in range(8):
            at += 100.0
            target = explore_target(Situation(state, grid, DAY, at, memory(visited=visited)))
            x, y, z = target
            self.assertFalse(lake(x, z), target)
            self.assertEqual(y, GROUND + 1)
            visited += line(HOME, target)
            ensure_brain(state)["explored"] += 1
```

In `backend/tests/test_survival_exploring.py`, replace:

```python
class ExploreScoreTests(unittest.TestCase):
    def setUp(self):
        height, self.grid = lake_world()
        for name in ("backend.survival.exploring.terrain_height",):
            patcher = patch(name, height)
            patcher.start()
            self.addCleanup(patcher.stop)
        trees = patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [(5, 0, 0)])
        trees.start()
        self.addCleanup(trees.stop)
```

with:

```python
class SurveyTests(unittest.TestCase):
    def setUp(self):
        height, self.grid = lake_world()
        patcher = patch("backend.survival.exploring.terrain_height", height)
        patcher.start()
        self.addCleanup(patcher.stop)
```

and replace:

```python
    def test_explore_scores_lower_with_little_new_land_near_and_higher_for_curious_pets(self):
        explore = PURPOSES["explore"]
        fresh = explore.score(Situation(pet(), self.grid, DAY, 100.0, memory()))
        seen = [(rx, rz) for rx in range(-9, 9) for rz in range(-9, 9)]
        explored = explore.score(Situation(pet(), self.grid, DAY, 100.0, memory(visited=seen, at=90.0)))
        self.assertEqual(fresh, 30.0)
        self.assertEqual(fresh - explored, 20.0)
        curious = explore.score(Situation(pet(traits={"curiosity": 100}), self.grid, DAY, 100.0, memory()))
        self.assertGreater(curious, fresh)

    def test_the_facts_say_which_way_is_unexplored_and_how_much_was_seen(self):
        # West and south of Mimo are known; north, east and the far corners are not.
        seen = [(rx, rz) for rx in range(-9, 1) for rz in range(-9, 9)] + \
               [(rx, rz) for rx in range(-9, 9) for rz in range(0, 9)]
        facts = PURPOSES["explore"].facts(Situation(pet(), self.grid, DAY, 100.0, memory(visited=seen, at=90.0)))
        self.assertRegex(facts, r"; northeast, (east and north|north and east) are unexplored; ")
        self.assertRegex(facts, r"; \d+% of the land within 64 blocks seen$")
        fresh = PURPOSES["explore"].facts(Situation(pet(), self.grid, DAY, 100.0, memory()))
        self.assertTrue(fresh.endswith("; land lies unexplored every way; 0% of the land within 64 blocks seen"),
                        fresh)
```

with:

```python
    def test_the_survey_says_which_way_is_unexplored_and_how_much_was_seen(self):
        # West and south of Mimo are known; north, east and the far corners are not.
        seen = [(rx, rz) for rx in range(-9, 1) for rz in range(-9, 9)] + \
               [(rx, rz) for rx in range(-9, 9) for rz in range(0, 9)]
        words = survey_text(Situation(pet(), self.grid, DAY, 100.0, memory(visited=seen, at=90.0)))
        self.assertRegex(words, r"^northeast, (east and north|north and east) are unexplored; ")
        self.assertRegex(words, r"; \d+% of the land within 64 blocks seen$")
        fresh = survey_text(Situation(pet(), self.grid, DAY, 100.0, memory()))
        self.assertEqual(fresh, "land lies unexplored every way; 0% of the land within 64 blocks seen")
```

In `backend/tests/test_survival_purposes.py`, replace:

```python
from backend.survival.actions import ActionContext, ensure_actions
```

with:

```python
from backend.survival import scouting  # noqa: F401  (L4: the needs explore goes for)
from backend.survival.actions import ActionContext, ensure_actions
```

and replace:

```python
        self.assertEqual(names(situation()), ["explore", "rest"])
```

with:

```python
        with patch("backend.survival.exploring.terrain_height", lambda x, z, seed: 0):
            self.assertEqual(names(situation()), ["explore", "rest"])  # L4: explore for wood and food
```

and replace:

```python
    def test_explore_scores_higher_with_no_trees_near(self):
        s = situation()
        with patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: []):
            lonely = PURPOSES["explore"].score(s)
        with patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [(5, 0, 0)]):
            wooded = PURPOSES["explore"].score(s)
        self.assertEqual(lonely - wooded, 25.0)

    def test_explore_never_scores_below_zero_late_in_the_day(self):
        late = {**DAY, "seconds_into_day": 2100.0}
        s = situation(pet(traits={"curiosity": 0}), clock=late)
        with patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [(5, 0, 0)]):
            self.assertEqual(PURPOSES["explore"].score(s), 0.0)
```

with:

```python
    def test_explore_needs_a_reason_and_scores_as_its_reason(self):
        # L4: no wood carried and no tree standing near is a reason: look for trees (backend.survival.scouting).
        fed = pet(inventory={"berries": 10}, traits={"curiosity": 0})
        late = {**DAY, "seconds_into_day": 2100.0}
        stocked = pet(inventory={"oak_log": 20, "berries": 10})  # wood and food enough: no reason to go
        with patch("backend.survival.exploring.terrain_height", lambda x, z, seed: 0), \
                patch("backend.survival.scouting.trees_near", lambda seed, x, z, radius: [(x, z, 0)]):
            self.assertEqual(PURPOSES["explore"].score(situation(fed)), 45.0)
            self.assertEqual(PURPOSES["explore"].score(situation(fed, clock=late)), 15.0)
            self.assertNotIn("explore", names(situation(stocked)))
```

In `backend/tests/test_survival_pickers.py`, replace:

```python
@patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [TREE])
@patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [TREE])
```

with:

```python
@patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [TREE])
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_trips.py"` and `python3 -m unittest discover -s backend/tests -p "test_survival_scouting.py"`
Expected: `Ran 11 tests` … `OK` and `Ran 5 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 985 tests` … `OK` (16 new, 2 old explore-score tests folded into 1 and 1 gone: 14 more in all).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 9: Commit**

```bash
git add backend/survival/trips.py backend/survival/scouting.py backend/survival/purposes.py backend/survival/exploring.py backend/survival/brain.py backend/survival/pickers.py backend/survival/choosing.py backend/tests/test_survival_trips.py backend/tests/test_survival_scouting.py backend/tests/test_survival_exploring.py backend/tests/test_survival_purposes.py backend/tests/test_survival_pickers.py
git commit -m "feat: every explore trip has a reason, heads where the land likely holds what it needs, and ends early on a find" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 5: Mimo's goals

**Files:**
- Create: `backend/survival/life_goals.py` (the goals, and the trips they need: iron, leather, a creature seed, the map)
- Modify: `backend/survival/creatures/hunting.py` (the `HUNT_FOR` hook), `backend/survival/creatures/harm.py` (the `ARMOR_WANTED` hook), `backend/survival/work.py` (the `EAGER` hook), `backend/survival/brain.py` (import the goals)
- Modify tests: `backend/tests/test_survival_choosing.py` (a hatched pet's Jev answer is one its first goal offers), `backend/tests/test_survival_sim.py` (the flood guard counts the changes toward no goal; all changes get their own cap), `backend/tests/test_survival_days.py` (goal events are notable too)
- Test: `backend/tests/test_survival_life_goals.py`

**Interfaces:**
- Consumes: Tasks 1–4 (Task 4's `trips.Reason`, `Find`, `register_reason`); `building.NOMINAL_BILL`, `START_SHARE`, `carried_blocks`; `blueprints.bill`; `structures.blueprint_of`, `todo`; `memory.BUILT`, `PATCH`, `cell_of`, `explored`, `patch_of`, `remember`, `structures`; `exploring.SURVEY`, `dry_blocks`, `explore_target`; `work.wood`, `wanted_ores`, `ORE_RANGE`, `ORE_REACH`; `crafting.TOOL_RANK`, `can_harvest`; `worldgen.region_openings`, `OPENING_REGION`, `rocks_in_chunk`, `terrain_height`, `biome_at`; `senses.ORES`, `grass_near`, `natural_plants`; `purposes.PURPOSES`, `is_valid`; `creatures.kinds.kind_of`, `land_kinds`, `creatures.table.dead`, `creatures.moves.where`, `creatures.seeds.SEED` (L3), `hunting.hunt_valid`, `prey`; `steps.REACH`, `label`; `test_survival_building.World`.
- Produces:
  - Goals `first_shelter`, `iron_tools`, `better_tools`, `armor_up`, `safe_yard`, `herd`, `map_land` (resolution 4). Their milestones that a trip can serve name `explore` too (walls' blocks and a wooden pickaxe: trees; iron found, mined, iron armor: iron; leather: hides; the pen and its animals: a seed; the land: the map), and explore advances a goal only when a trip on offer serves it (Task 4's `goals.ADVANCES` check). Raising the walls also names gather_wood and gather_stone (the blocks run out as it builds), and the corner torches gather_stone (digging turns up the coal they take), so a goal stuck for blocks or coal is still worked on.
  - Trips (resolution 15): `iron` ("look for iron", while mine_ore wants iron Mimo can mine and it remembers none within 48 blocks: cave mouths and sinkholes it has not looked into are sure, rocky outcrops likely, hills and mountain rock less so; after each walk the openings within 16 blocks are looked into, remembered as `cave` landmarks, and the ore in their walls Mimo could mine from the floor or the rim remembered; iron among it is the find), `hides` ("look for leather", armor the goal: cow land is sure, rabbit ground likely; an animal in range is the find, a `pasture` landmark), `seed` ("look for a creature seed", the herd the goal and no seed at hand: tall grass, broken at each stop, `GRASS_PER_STOP = 10`; a seed carried is the find), `map` ("map the land", mapping the goal: `exploring.explore_target`).
  - Helpers later tasks use: `life_goals.whole(done) -> float`, `all_structures(s)`, `shelters(s)`, `home_structure(s) -> dict | None` (the shelter whose inside cell is the home Mimo built), `first_home(s)`, `built_share(s, structure) -> float`, `home_parts_done(s, part) -> float`, `land_seen(s) -> float`, `hides_wanted(s) -> bool`; constants `HIDE_HUNT_GAP = DAY_SECONDS / 6`, `MAP_SHARE = 0.6`.
  - `hunting.HUNT_FOR: list` of `(Situation) -> bool`: any true makes hunt valid though Mimo lacks no food.
  - `harm.ARMOR_WANTED: list` of `(state) -> bool`: any true makes iron armor worth its ingots before a creature hurt Mimo (`armor_wanted`, which craft_tools and mine_ore read); life_goals adds `armor_the_goal`. `work.EAGER: list` of `(Situation, ore) -> bool`: any true lets mine_ore go for a single remembered ore of that kind (`enough_known`); life_goals adds `diamonds_wanted`. Both are crash-guarded (resolution 21).
  - `test_survival_life_goals.built(inventory=None) -> World` (a pet on a meadow that built and furnished its first shelter) and `shares(s, name) -> list[float]`, for Tasks 6 and 7.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_life_goals.py`:

```python
import unittest
from unittest.mock import patch

from backend.services.crafting import RECIPES
from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.creatures import hunting
from backend.survival.creatures.harm import armor_wanted
from backend.survival.goals import GOALS, adopt_goal, advances, complete, counted, is_open, progress_of, share_of
from backend.survival.life_goals import DAY_SECONDS, hides_wanted, land_seen
from backend.survival.memory import mark_explored, places, remember, structures
from backend.survival.trips import REASONS
from backend.survival.purposes import PURPOSES
from backend.survival.structures import blueprint_of
from backend.survival.work import wanted_ores
from backend.tests.test_survival_building import World


def shares(s, name):
    return [round(share_of(s, milestone), 2) for _, milestone in counted(GOALS[name])]


def built(inventory=None):
    """A pet that built its first shelter on a meadow and put a bed in it."""
    world = World({"cobblestone": 60, "planks": 20, "oak_log": 4, "sticks": 4})
    for _ in range(12):
        steps = world.plan()
        if not steps:
            break
        world.carry_out(steps)
    world.state["inventory"] = dict(inventory or {})
    return world


class FirstShelterTests(unittest.TestCase):
    def test_blocks_then_the_walls_and_roof_then_a_bed(self):
        world = World({"cobblestone": 10})
        self.assertEqual(shares(world.situation(), "first_shelter"), [0.53, 0.0, 0.0])  # 10 of the 19 to start with
        s = built().situation()
        self.assertEqual(shares(s, "first_shelter"), [1.0, 1.0, 1.0])
        self.assertTrue(complete(s, GOALS["first_shelter"]))

    def test_every_other_goal_waits_for_it(self):
        s = World().situation()
        self.assertEqual([name for name, goal in GOALS.items() if is_open(s, goal)], ["first_shelter"])
        s = built().situation()
        self.assertNotIn("first_shelter", [name for name, goal in GOALS.items() if is_open(s, goal)])
        self.assertTrue(is_open(s, GOALS["iron_tools"]))
        self.assertFalse(is_open(s, GOALS["armor_up"]))  # after iron tools


class ToolsAndArmorTests(unittest.TestCase):
    def test_iron_tools_climb_the_pickaxe_ladder_to_iron(self):
        world = built({"oak_log": 3})
        self.assertEqual(shares(world.situation(), "iron_tools"), [0.5, 0.0, 0.0, 0.0, 0.0])
        world.state["inventory"] = {"stone_pickaxe": 1, "iron_ore": 2}
        self.assertEqual(shares(world.situation(), "iron_tools"), [1.0, 1.0, 1.0, 0.67, 0.0])
        world.state["inventory"] = {"stone_pickaxe": 1}
        remember(world.db, "ore", (4, -6, 4), 0.0, "iron_ore")
        self.assertEqual(shares(world.situation(), "iron_tools")[2], 1.0)  # seen is found
        world.state["inventory"] = {"iron_pickaxe": 1}
        s = world.situation()
        self.assertTrue(complete(s, GOALS["iron_tools"]))
        self.assertTrue(is_open(s, GOALS["armor_up"]))

    def test_armor_counts_leather_and_the_pieces_and_iron_armor_once_its_recipes_exist(self):
        world = built({"iron_pickaxe": 1, "leather": 2, "rabbit_hide": 4})
        armor = GOALS["armor_up"]
        iron = "iron_cap" in RECIPES and "iron_tunic" in RECIPES
        self.assertEqual(len(counted(armor)), 4 if iron else 3)
        self.assertEqual(shares(world.situation(), "armor_up")[:3], [0.6, 0.0, 0.0])
        world.state["inventory"] = {"iron_pickaxe": 1, "leather_cap": 1, "leather_tunic": 1}
        self.assertEqual(shares(world.situation(), "armor_up")[:3], [1.0, 1.0, 1.0])
        self.assertEqual(complete(world.situation(), armor), not iron)

    def test_while_armor_is_the_goal_mimo_hunts_for_hides_a_few_times_a_day(self):
        self.assertIn(hides_wanted, hunting.HUNT_FOR)
        world = built({"iron_pickaxe": 1})
        self.assertFalse(hides_wanted(world.situation()))
        adopt_goal(world.state, "armor_up", "utility", "", 0.0)
        self.assertTrue(hides_wanted(world.situation()))
        world.state["hunted_at"] = -DAY_SECONDS / 6 + 1.0  # killed something less than a sixth of a day ago
        self.assertFalse(hides_wanted(world.situation()))
        world.state.update(hunted_at=None, inventory={"iron_pickaxe": 1, "leather": 5})
        self.assertFalse(hides_wanted(world.situation()))

    def test_with_armor_the_goal_iron_armor_is_worth_making_before_any_blow(self):
        world = built({"iron_pickaxe": 1, "coal": 8})
        self.assertFalse(armor_wanted(world.state))
        self.assertNotIn("iron_ore", wanted_ores(world.situation()))
        adopt_goal(world.state, "armor_up", "utility", "", 0.0)
        self.assertTrue(armor_wanted(world.state))
        self.assertIn("iron_ore", wanted_ores(world.situation()))  # the 13 ingots iron armor takes

    def test_with_diamond_tools_the_goal_mine_ore_goes_for_a_single_known_diamond(self):
        world = built({"iron_pickaxe": 1, "coal": 8})
        remember(world.db, "ore", (4, -6, 4), 0.0, "diamond_ore")
        self.assertNotIn("diamond_ore", wanted_ores(world.situation()))  # one of the 3 a pickaxe takes
        adopt_goal(world.state, "better_tools", "utility", "", 0.0)
        self.assertIn("diamond_ore", wanted_ores(world.situation()))

    def test_diamond_tools_wait_for_the_diamond_pickaxe_recipe(self):
        self.assertEqual(bool(counted(GOALS["better_tools"])), "diamond_pickaxe" in RECIPES)


class HomeGoalTests(unittest.TestCase):
    def test_a_safe_yard_counts_the_corner_torches_and_the_door(self):
        world = built()
        self.assertEqual(shares(world.situation(), "safe_yard")[:2], [0.0, 1.0])
        torches = [planned.cell for planned in blueprint_of(structures(world.db)[0]).parts("torch")]
        for cell in torches[:2]:
            world.grid.put(*cell, "torch")
        self.assertEqual(shares(world.situation(), "safe_yard")[0], round(2 / len(torches), 2))
        self.assertEqual(len(counted(GOALS["safe_yard"])), 2 + ("build_fence" in PURPOSES and "fence" in RECIPES))

    def test_a_herd_waits_for_the_pen_purposes(self):
        self.assertEqual(bool(counted(GOALS["herd"])), "build_pen" in PURPOSES and "fence" in RECIPES)

    def test_mapping_the_land_counts_the_dry_patches_walked_near_home(self):
        world = built()
        s = world.situation()
        self.assertEqual(land_seen(s), 0.0)
        mark_explored(world.db, [(rx, rz) for rx in range(-8, 9) for rz in range(-8, 9) if rx < 0], 0.0)
        s = world.situation()
        self.assertAlmostEqual(land_seen(s), 0.47, places=1)
        self.assertAlmostEqual(progress_of(s, GOALS["map_land"]), land_seen(s) / 0.6, places=3)


SINKHOLE = {(40 + dx, dz): (-2, 3) for dx in (-1, 0, 1) for dz in (-1, 0, 1)}  # a shaft of air from y -2 to 3


def one_sinkhole(rx, rz, seed):
    return ("sinkhole", SINKHOLE) if (rx, rz) == (0, 0) else ("", {})


class TripTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("backend.survival.life_goals.region_openings", one_sinkhole),
                            ("backend.survival.life_goals.terrain_height", lambda x, z, seed: 0),
                            ("backend.survival.exploring.terrain_height", lambda x, z, seed: 0)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_with_no_iron_known_mimo_looks_for_it_at_cave_mouths_and_sinkholes(self):
        world = built({"stone_pickaxe": 1})
        s = world.situation()
        iron = REASONS["iron"]
        self.assertEqual(iron.wanted(s), "my pickaxe needs it")
        self.assertEqual((iron.value(s, 36, 4), iron.value(s, -60, 0)), ((1.0, "a sinkhole"), (0.0, "")))
        self.assertEqual(iron.spots(s), [(40, 0, "a sinkhole")])
        self.assertTrue(advances(s, "explore", GOALS["iron_tools"]))
        self.assertFalse(advances(s, "explore", GOALS["map_land"]))
        remember(world.db, "cave", (40, 1, 0), 0.0, "sinkhole")  # looked into already
        s = world.situation()
        self.assertEqual((iron.value(s, 36, 4), iron.spots(s)), ((0.0, ""), []))
        remember(world.db, "ore", (30, -3, 0), 0.0, "iron_ore")
        self.assertIsNone(iron.wanted(world.situation()))  # iron known within reach: mine_ore goes for it

    def test_looking_into_a_sinkhole_remembers_it_and_the_ore_mimo_can_reach(self):
        world = built({"stone_pickaxe": 1})
        world.grid.put(42, 0, 0, "iron_ore")  # in the wall, 1 below the rim
        world.grid.put(41, -3, 0, "coal_ore")  # the floor, far down the shaft: out of reach from the rim
        world.state["position"] = {"x": 44.0, "y": 1.0, "z": 0.0}
        find = REASONS["iron"].look(world.situation(), world.context())
        self.assertEqual((find.words, find.done), ("a sinkhole with iron ore in its walls", True))
        self.assertEqual([(place["kind"], place["x"], place["note"]) for place in places(world.db, ("cave", "ore"))],
                         [("cave", 40, "sinkhole"), ("ore", 42, "iron_ore")])
        self.assertIsNone(REASONS["iron"].look(world.situation(), world.context()))  # nothing new to look into

    def test_armor_looks_for_leather_where_cows_graze(self):
        world = built({"iron_pickaxe": 1})
        hides = REASONS["hides"]
        self.assertIsNone(hides.wanted(world.situation()))
        adopt_goal(world.state, "armor_up", "utility", "", 0.0)
        s = world.situation()
        self.assertEqual(hides.wanted(s), "my armor needs leather and no animal is near")
        self.assertEqual(hides.value(s, 40, 0), (1.0, "grazing land for cows"))  # the meadow

    def test_a_herd_looks_for_a_creature_seed_in_the_tall_grass_breaking_it_at_each_stop(self):
        world = built()
        seed = REASONS["seed"]
        adopt_goal(world.state, "herd", "utility", "", 0.0)
        self.assertEqual(seed.wanted(world.situation()), "a pen of animals grows from creature seeds")
        grass = [(2, 1, 1), (3, 1, 1)]
        with patch("backend.survival.life_goals.grass_near", lambda grid, seed, here, radius: grass), \
                patch("backend.survival.life_goals.natural_plants", lambda seed, x, z, radius, kinds: [(x, 1, z)] * 6):
            s = world.situation()
            self.assertEqual(seed.work(s), [{"kind": "mine", "target": [2, 1, 1]}, {"kind": "mine", "target": [3, 1, 1]}])
            self.assertEqual(seed.value(s, 40, 0), (0.5, "tall grass"))
        world.state["inventory"] = {"creature_seed": 1}
        s = world.situation()
        self.assertIsNone(seed.wanted(s))
        self.assertEqual(seed.look(s, world.context()).words, "a creature seed")

    def test_mapping_the_land_heads_for_the_ground_it_has_seen_least(self):
        world = built()
        self.assertIsNone(REASONS["map"].wanted(world.situation()))
        adopt_goal(world.state, "map_land", "utility", "", 0.0)
        s = world.situation()
        self.assertEqual(REASONS["map"].wanted(s), "I want to know the land around home")
        [(x, z, words)] = REASONS["map"].spots(s)
        self.assertEqual(words, "land it has not seen")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_life_goals.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.life_goals'`

- [ ] **Step 3: The goals**

Create `backend/survival/life_goals.py`:

```python
"""The goals Mimo sets itself (L4), registered in backend.survival.goals.

- first_shelter, "A home of its own": gather blocks, raise the walls and roof (gathering more blocks
  as they run out), put a bed inside (M5's build_shelter). Every other goal comes after it.
- iron_tools, "Iron tools": a wooden and a stone pickaxe, iron ore found, 3 iron ore mined, an
  iron pickaxe.
- better_tools, "Diamond tools", after iron tools: diamonds found, 3 mined, a diamond pickaxe
  (every milestone needs L3's diamond_pickaxe recipe). While it is the goal, mine_ore goes for any
  diamond Mimo remembers, not only once it knows of 3 (work.EAGER).
- armor_up, "Armor up", after iron tools: 5 leather, a leather cap and a leather tunic (L2's
  make_gear), and iron armor (L3's iron_cap and iron_tunic recipes). While it is the goal, iron
  armor is worth making though no creature has hurt Mimo yet (harm.ARMOR_WANTED), and while
  leather is short Mimo also hunts for hides though fed (hunting.HUNT_FOR), at most once a sixth
  of a game day.
- safe_yard, "A safe yard": torches at the corners of home (mining coal for them, and digging for
  it when none is known), a door in its doorway, and a fence round the yard once a purpose named
  build_fence exists (none yet: L3 plans no yard fence).
- herd, "A herd of its own": a pen by home and 3 animals grown in it, with L3's build_pen and
  stock_pen (their milestones need L3's fence recipe too).
- map_land, "Map the land": set foot on MAP_SHARE of the dry land within 64 blocks of home.
backend.survival.homes adds better_home and backend.survival.larder full_larder.

Explore trips these goals need (backend.survival.trips; the milestones name explore, and a trip
advances a goal when its reason serves it):
- iron, "look for iron", while mine_ore wants iron Mimo can mine and it remembers none within 48
  blocks ("my pickaxe needs it", or its armor). A cave mouth or sinkhole (worldgen's openings)
  whose ground Mimo has not looked into is sure, a rocky outcrop likely, hills and mountain rock
  less so (mouths cut into hillsides); openings within 64 blocks are spots. After each walk Mimo
  looks into any opening within 16 blocks it has not seen: it is remembered as a "cave" landmark,
  and the ore in its walls that Mimo could reach from its floor or rim as ore places. Iron among
  them is the find: mine_ore follows. Serves iron tools and armor.
- hides, "look for leather", while armor is the goal and hides are wanted (hides_wanted) with no
  animal in range: land where cows graze is sure, rabbit ground likely; pastures found before are
  spots. An animal in range is the find ("pasture" landmark), and hunt follows.
- seed, "look for a creature seed", while the herd is the goal, no seed is carried or in a chest
  and neither pen purpose is on offer: tall grass (12 within 8 blocks is sure). At each stop Mimo
  breaks up to GRASS_PER_STOP tall grass within reach (a seed drops 1 in 60); a seed carried is the
  find, and build_pen or stock_pen follows.
- map, "map the land", while mapping is the goal and not done: the least-explored ground near
  (exploring.explore_target), the one reason that heads for new land as such.

Their rules scores (goals.rules_score adds WORKABLE and STICK): first_shelter 90; iron_tools 60
plus a tenth of diligence; better_tools 50 plus a tenth of diligence; armor_up 50 plus a tenth of
caution, 15 more when a creature hurt Mimo in the last game day; safe_yard 55 plus a tenth of
caution; herd 45 plus a tenth of patience; map_land 40 plus a tenth of curiosity.
"""

from __future__ import annotations

import math

from backend.services.crafting import TOOL_RANK, can_harvest
from backend.services.worldgen import OPENING_REGION, biome_at, region_openings, rocks_in_chunk, terrain_height
from backend.survival.blueprints import bill
from backend.survival.building import NOMINAL_BILL, START_SHARE, carried_blocks
from backend.survival.clock import DAY_SECONDS
from backend.survival import work
from backend.survival.creatures import harm, hunting
from backend.survival.creatures.hunting import prey
from backend.survival.creatures.kinds import kind_of, land_kinds
from backend.survival.creatures.moves import where
from backend.survival.creatures.seeds import SEED
from backend.survival.creatures.table import dead
from backend.survival.exploring import SURVEY, dry_blocks, explore_target
from backend.survival.goals import Goal, Milestone, register_goal
from backend.survival.memory import BUILT, PATCH, cell_of, explored, patch_of, remember, structures
from backend.survival.purposes import PURPOSES, is_valid
from backend.survival.senses import ORES, grass_near, natural_plants, near_failure
from backend.survival.situation import Situation
from backend.survival.steps import REACH, label
from backend.survival.structures import blueprint_of, todo
from backend.survival.trips import Find, Reason, register_reason
from backend.survival.work import ORE_RANGE, ORE_REACH, wanted_ores, wood

WOOD_FOR_A_PICKAXE = 3.0  # logs of wood: a crafting table, planks and sticks
IRON_WANTED = 3
DIAMONDS_WANTED = 3
LEATHER_WANTED = 5  # a cap takes 2, a tunic 3
HIDE_HUNT_GAP = DAY_SECONDS / 6  # game seconds between two hunts for hides
MAP_SHARE = 0.6  # of the dry land within SURVEY blocks of home
PEN_ANIMALS = 3
CAVE = "cave"  # a landmark: a cave mouth or sinkhole Mimo looked into, the note says which
OPENING_NEAR = 12  # blocks from a spot to an opening that makes it sure for iron
OPENING_SIGHT = 64  # openings this close to Mimo are spots
CAVE_LOOK = 16  # openings this close after a walk are looked into
HILLS = 9  # ground this high is hill country, where cave mouths cut in
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
AROUND = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
TALL_GRASS = 8  # blocks around a spot whose tall grass counts
SURE_GRASS = 12
GRASS_PER_STOP = 10


def whole(done: bool) -> float:
    return 1.0 if done else 0.0


# What Mimo built -------------------------------------------------------------------------------

def all_structures(s: Situation) -> list[dict]:
    """Everything Mimo started, oldest first, read once per Situation (the key building.py uses)."""
    return s.sensed("structures", lambda: structures(s.db) if s.db is not None else [])


def shelters(s: Situation) -> list[dict]:
    return [found for found in all_structures(s) if found["kind"] == "shelter"]


def home_structure(s: Situation) -> dict | None:
    """The shelter Mimo lives in: the one whose inside cell is the home it built."""
    home = next((place for place in s.places if place["kind"] == "home" and place["note"] == BUILT), None)
    if home is None:
        return None
    return next((found for found in reversed(shelters(s)) if (found["x"], found["y"], found["z"]) == cell_of(home)),
                None)


def first_home(s: Situation) -> dict | None:
    """The first shelter Mimo finished."""
    return next((found for found in shelters(s) if found["status"] == "done"), None)


def built_share(s: Situation, structure: dict | None) -> float:
    """How much of a shelter's floor, walls and roof stands (1 once it is done)."""
    if structure is None:
        return 0.0
    if structure["status"] == "done":
        return 1.0
    blueprint = blueprint_of(structure)
    total = bill(blueprint)
    return 1.0 - bill(blueprint, s.grid) / total if total else 1.0


def home_parts_done(s: Situation, part: str) -> float:
    """The share of a part (torch, door) of the home's design that is in place."""
    home = home_structure(s)
    if home is None:
        return 0.0
    blueprint = blueprint_of(home)
    planned = blueprint.parts(part)
    return 1.0 - len(todo(s.grid, blueprint, (part,))) / len(planned) if planned else 1.0


# first_shelter ---------------------------------------------------------------------------------

def shelter_now(s: Situation) -> dict | None:
    """The shelter Mimo lives in, else the newest one it started."""
    found = shelters(s)
    return home_structure(s) or (found[-1] if found else None)


def shelter_blocks(s: Situation) -> float:
    if shelters(s):
        return 1.0
    return carried_blocks(s) / (START_SHARE * NOMINAL_BILL)


def bed_in(s: Situation) -> float:
    structure = shelter_now(s)
    return whole(structure is not None and structure["status"] == "done"
                 and not todo(s.grid, blueprint_of(structure), ("bed",)))


register_goal(Goal(
    "first_shelter", "A home of its own",
    "Nights are cold and dark: a shelter of its own with a bed keeps Mimo warm and safe.",
    (Milestone("Gather blocks for the walls", shelter_blocks,
               ("gather_wood", "gather_stone", "craft_tools", "explore")),
     Milestone("Raise the walls and roof", lambda s: built_share(s, shelter_now(s)),
               ("build_shelter", "gather_wood", "gather_stone", "explore")),  # its blocks run out as it builds
     Milestone("Put a bed inside", bed_in, ("build_shelter",))),
    score=lambda s: 90.0, thought="First things first: a roof of my own."))


# iron_tools and better_tools --------------------------------------------------------------------

def pickaxe_rank(s: Situation) -> int:
    return max((TOOL_RANK[tool] for tool in TOOL_RANK if s.count(tool) > 0), default=0)


def has_iron_pickaxe(s: Situation) -> bool:
    return pickaxe_rank(s) >= TOOL_RANK["iron_pickaxe"]


def wooden_pickaxe(s: Situation) -> float:
    """Done with a pickaxe; the wood for one is half the way."""
    return 1.0 if pickaxe_rank(s) >= 1 else 0.5 * min(1.0, wood(s.inventory) / WOOD_FOR_A_PICKAXE)


def iron_mined(s: Situation) -> float:
    return 1.0 if has_iron_pickaxe(s) else s.count("iron_ore", "iron_ingot") / IRON_WANTED


def remembers(s: Situation, ore: str) -> bool:
    return any(place["kind"] == "ore" and place["note"] == ore for place in s.places)


register_goal(Goal(
    "iron_tools", "Iron tools",
    "Stone only goes so far: an iron pickaxe digs anything and opens the way to better gear.",
    (Milestone("Make a wooden pickaxe", wooden_pickaxe, ("gather_wood", "craft_tools", "explore")),
     Milestone("Make a stone pickaxe", lambda s: whole(pickaxe_rank(s) >= 2), ("gather_stone", "craft_tools")),
     Milestone("Find iron ore", lambda s: whole(has_iron_pickaxe(s) or s.count("iron_ore", "iron_ingot") > 0
                                                or remembers(s, "iron_ore")), ("gather_stone", "mine_ore", "explore")),
     Milestone("Mine 3 iron ore", iron_mined, ("mine_ore", "gather_stone", "explore")),
     Milestone("Make an iron pickaxe", lambda s: whole(has_iron_pickaxe(s)), ("craft_tools",))),
    score=lambda s: 60.0 + s.trait("diligence") / 10, thought="I want iron tools. Stone only goes so far.",
    after=("first_shelter",)))


# The trip for iron: cave mouths and sinkholes ----------------------------------------------------

def opening_of(rx: int, rz: int, seed: str) -> tuple[str, int, int] | None:
    """The cave entrance of a 64x64 region as (kind, x, z of its middle column), or None."""
    kind, spans = region_openings(rx, rz, seed)
    if not kind:
        return None
    columns = sorted(spans)
    x, z = columns[len(columns) // 2]
    return kind, x, z


def openings_near(seed: str, x: int, z: int, reach: float) -> list[tuple[str, int, int]]:
    """The cave entrances whose middle lies within `reach` blocks of (x, z), nearest first."""
    found = []
    for rx in range(math.floor((x - reach) / OPENING_REGION), math.floor((x + reach) / OPENING_REGION) + 1):
        for rz in range(math.floor((z - reach) / OPENING_REGION), math.floor((z + reach) / OPENING_REGION) + 1):
            opening = opening_of(rx, rz, seed)
            if opening is not None and math.hypot(opening[1] - x, opening[2] - z) <= reach:
                found.append(opening)
    return sorted(found, key=lambda opening: (math.hypot(opening[1] - x, opening[2] - z), opening))


def looked_into(s: Situation, x: int, z: int) -> bool:
    return any(place["kind"] == CAVE and math.hypot(place["x"] - x, place["z"] - z) <= CAVE_LOOK for place in s.places)


def opening_words(kind: str) -> str:
    return "a sinkhole" if kind == "sinkhole" else "a cave mouth"


def iron_wanted(s: Situation) -> str | None:
    """mine_ore wants iron Mimo can mine, and it remembers none within reach of mine_ore."""
    if "iron_ore" not in wanted_ores(s) or not can_harvest("iron_ore", s.inventory):
        return None
    if any(place["kind"] == "ore" and place["note"] == "iron_ore" and s.distance(cell_of(place)) <= ORE_RANGE
           for place in s.places):
        return None
    return "my armor needs it" if has_iron_pickaxe(s) else "my pickaxe needs it"


def iron_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    for kind, ox, oz in openings_near(s.seed, x, z, OPENING_NEAR):
        if not looked_into(s, ox, oz):
            return 1.0, opening_words(kind)
    for rx, rz, rock, _, _ in rocks_in_chunk(x // 16, z // 16, s.seed):
        if rock == "outcrop" and math.hypot(rx - x, rz - z) <= OPENING_NEAR:
            return 0.5, "a rocky outcrop"
    if terrain_height(x, z, s.seed) >= HILLS:
        return 0.3, "bare mountain rock" if biome_at(x, z, s.seed) == "alpine" else "hills"
    return 0.0, ""


def opening_spots(s: Situation) -> list[tuple[int, int, str]]:
    x, _, z = s.here
    return [(ox, oz, opening_words(kind)) for kind, ox, oz in openings_near(s.seed, x, z, OPENING_SIGHT)
            if not looked_into(s, ox, oz)]


def exposed_ores(s: Situation, kind: str, spans) -> list[tuple[tuple[int, int, int], str]]:
    """Ore in the walls of an opening that Mimo could mine from where it can stand: the opening's
    floor (a mouth's) or the ground round its rim."""
    air = {(x, y, z) for (x, z), (low, high) in spans.items() for y in range(low, high + 1)}
    stands = [(x, low, z) for (x, z), (low, _) in spans.items()] if kind == "mouth" else []
    stands += [(x + dx, terrain_height(x + dx, z + dz, s.seed) + 1, z + dz) for (x, z) in spans for dx, dz in SIDES
               if (x + dx, z + dz) not in spans]
    found = {}
    for x, y, z in air:
        for dx, dy, dz in AROUND:
            cell = (x + dx, y + dy, z + dz)
            if cell in air or cell in found:
                continue
            material = s.grid.material(*cell)
            if material in ORES and any(math.dist(cell, stand) <= ORE_REACH for stand in stands):
                found[cell] = material
    return sorted(found.items())


def iron_look(s: Situation, context) -> Find | None:
    """Look into the openings near that Mimo has not seen: remember each as a cave landmark and the
    ore in its walls as ore places. Iron among them is what the trip was for."""
    x, _, z = s.here
    words, iron = [], False
    for kind, ox, oz in openings_near(s.seed, x, z, CAVE_LOOK):
        if looked_into(s, ox, oz):
            continue
        spans = region_openings(ox // OPENING_REGION, oz // OPENING_REGION, s.seed)[1]
        ores = exposed_ores(s, kind, spans)
        remember(s.db, CAVE, (ox, terrain_height(ox, oz, s.seed) + 1, oz), s.at, kind)
        for cell, ore in ores:
            remember(s.db, "ore", cell, s.at, ore)
        seen = sorted({ore for _, ore in ores}, key=ORES.index)
        iron = iron or "iron_ore" in seen
        words.append(opening_words(kind) + (f" with {' and '.join(label(ore) for ore in seen)} in its walls"
                                           if seen else ""))
    return Find(" and ".join(words), iron) if words else None


register_reason(Reason(
    "iron", "look for iron", iron_wanted, iron_value, lambda s: 45.0 + s.trait("curiosity") / 10,
    goals=("iron_tools", "armor_up"), spots=opening_spots, look=iron_look))


def has_diamond_pickaxe(s: Situation) -> bool:
    return s.count("diamond_pickaxe") > 0


def diamonds_wanted(s: Situation, ore: str) -> bool:
    """With diamond tools the goal, mine_ore goes for any diamond Mimo remembers (work.EAGER)."""
    return ore == "diamond_ore" and (s.brain.get("goal") or {}).get("name") == "better_tools"


work.EAGER.append(diamonds_wanted)

register_goal(Goal(
    "better_tools", "Diamond tools",
    "Diamonds lie deep: a diamond pickaxe is the best tool there is.",
    (Milestone("Find diamonds", lambda s: whole(has_diamond_pickaxe(s) or s.count("diamond") > 0
                                                or remembers(s, "diamond_ore")),
               ("gather_stone", "mine_ore"), items=("diamond_pickaxe",)),
     Milestone("Mine 3 diamonds", lambda s: 1.0 if has_diamond_pickaxe(s) else s.count("diamond") / DIAMONDS_WANTED,
               ("mine_ore",), items=("diamond_pickaxe",)),
     Milestone("Make a diamond pickaxe", lambda s: whole(has_diamond_pickaxe(s)), ("craft_tools",),
               items=("diamond_pickaxe",))),
    score=lambda s: 50.0 + s.trait("diligence") / 10, thought="Diamonds are down there somewhere.",
    after=("first_shelter", "iron_tools")))


# armor_up --------------------------------------------------------------------------------------

def wears(s: Situation, *pieces: str) -> bool:
    return any(s.count(piece) > 0 for piece in pieces)


def leather_gathered(s: Situation) -> float:
    """Leather toward a cap and a tunic, counting what the pieces Mimo has took (4 hides make 1)."""
    cap = 2 if wears(s, "leather_cap", "iron_cap") else 0
    tunic = 3 if wears(s, "leather_tunic", "iron_tunic") else 0
    return (s.count("leather") + s.count("rabbit_hide") // 4 + cap + tunic) / LEATHER_WANTED


def hurt_lately(s: Situation) -> bool:
    hurt_at = s.state.get("hurt_at")
    return hurt_at is not None and (s.at - hurt_at) * s.scale < DAY_SECONDS


def hides_wanted(s: Situation) -> bool:
    """Armor is the goal, leather is short and Mimo killed nothing for HIDE_HUNT_GAP: it hunts for
    hides though fed, a few times a day, so the land is never emptied."""
    goal = s.brain.get("goal")
    hunted_at = s.state.get("hunted_at")
    rested = hunted_at is None or (s.at - hunted_at) * s.scale >= HIDE_HUNT_GAP
    return goal is not None and goal["name"] == "armor_up" and rested and leather_gathered(s) < 1.0


hunting.HUNT_FOR.append(hides_wanted)


def armor_the_goal(state: dict) -> bool:
    """With armor the goal, iron armor is worth its ingots before any creature hurt Mimo
    (harm.ARMOR_WANTED): craft_tools makes it and mine_ore digs the iron it takes."""
    return ((state.get("brain") or {}).get("goal") or {}).get("name") == "armor_up"


harm.ARMOR_WANTED.append(armor_the_goal)

register_goal(Goal(
    "armor_up", "Armor up",
    "Gloomlings hit hard at night: armor takes the edge off every blow.",
    (Milestone("Gather 5 leather", leather_gathered, ("hunt", "explore")),
     Milestone("Make a leather cap", lambda s: whole(wears(s, "leather_cap", "iron_cap")), ("make_gear",)),
     Milestone("Make a leather tunic", lambda s: whole(wears(s, "leather_tunic", "iron_tunic")), ("make_gear",)),
     Milestone("Make iron armor", lambda s: (wears(s, "iron_cap") + wears(s, "iron_tunic")) / 2,
               ("craft_tools", "mine_ore", "explore"), items=("iron_cap", "iron_tunic"))),
    score=lambda s: 50.0 + s.trait("caution") / 10 + (15.0 if hurt_lately(s) else 0.0),
    thought="Next time a gloomling swings at me, I'll be ready.", after=("first_shelter", "iron_tools")))


def hides_trip(s: Situation) -> str | None:
    if not hides_wanted(s) or prey(s):
        return None
    return "my armor needs leather and no animal is near"


def hides_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    kinds = {kind.name for kind in land_kinds(biome_at(x, z, s.seed))}
    if "cow" in kinds:
        return 1.0, "grazing land for cows"
    return (0.4, "rabbit ground") if "rabbit" in kinds else (0.0, "")


def pasture_spots(s: Situation) -> list[tuple[int, int, str]]:
    return [(place["x"], place["z"], f"where it saw a {label(place['note'] or 'rabbit')}") for place in s.places
            if place["kind"] == "pasture"]


def hides_look(s: Situation, context) -> Find | None:
    animals = prey(s)
    if not animals:
        return None
    kind = animals[0]["kind"]
    return Find(f"a {label(kind)} to hunt", True, remember(s.db, "pasture", where(animals[0], s.at), s.at, kind))


register_reason(Reason(
    "hides", "look for leather", hides_trip, hides_value, lambda s: 40.0 + s.trait("bravery") / 10,
    goals=("armor_up",), spots=pasture_spots, look=hides_look))


# safe_yard -------------------------------------------------------------------------------------

register_goal(Goal(
    "safe_yard", "A safe yard",
    "Light and a door keep gloomlings away from home at night.",
    (Milestone("Light torches at the corners of home", lambda s: home_parts_done(s, "torch"),
               ("light_up", "mine_ore", "gather_stone")),  # digging turns up the coal torches take
     Milestone("Hang a door in the doorway", lambda s: home_parts_done(s, "door"), ("build_shelter",)),
     Milestone("Put a fence round the yard", lambda s: 0.0, ("build_fence",), items=("fence",))),
    score=lambda s: 55.0 + s.trait("caution") / 10, thought="Lights and a good door. Let them try.",
    after=("first_shelter",), valid=lambda s: home_structure(s) is not None))


# herd ------------------------------------------------------------------------------------------

def finished_pen(s: Situation) -> dict | None:
    return next((found for found in all_structures(s) if found["kind"] == "pen" and found["status"] == "done"), None)


def animals_in_pen(s: Situation) -> int:
    """Living passive animals standing inside the finished pen."""
    pen, herd = finished_pen(s), s.grid.herd
    if pen is None or herd is None:
        return 0
    blueprint = blueprint_of(pen)
    inside = {(planned.cell[0], planned.cell[2]) for planned in blueprint.parts("pen")}
    x, _, z = blueprint.anchor
    count = 0
    for creature in herd.near(x, z, 4.0):
        kind = kind_of(creature["kind"])
        if not dead(creature) and kind is not None and not kind.hostile \
                and (round(creature["x"]), round(creature["z"])) in inside:
            count += 1
    return count


register_goal(Goal(
    "herd", "A herd of its own",
    "Animals grown from creature seeds in a pen by home give meat, wool and company.",
    (Milestone("Build a pen by home", lambda s: whole(finished_pen(s) is not None), ("build_pen", "explore"),
               items=("fence",)),
     Milestone("Grow 3 animals in the pen", lambda s: animals_in_pen(s) / PEN_ANIMALS, ("stock_pen", "explore"),
               items=("fence",))),
    score=lambda s: 45.0 + s.trait("patience") / 10, thought="A few animals of my own, safe in a pen.",
    after=("first_shelter",)))


def seed_trip(s: Situation) -> str | None:
    goal = s.brain.get("goal")
    if not goal or goal["name"] != "herd" or s.count(SEED) > 0:
        return None
    if any(chest.get(SEED, 0) > 0 for chest in s.state.get("chests", {}).values()):
        return None
    if any(name in PURPOSES and is_valid(PURPOSES[name], s) for name in ("build_pen", "stock_pen")):
        return None
    return "a pen of animals grows from creature seeds"


def seed_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    grass = natural_plants(s.seed, x, z, TALL_GRASS, ("tall_grass",))
    return (min(1.0, len(grass) / SURE_GRASS), "tall grass") if grass else (0.0, "")


def break_grass(s: Situation) -> list[dict]:
    """Tall grass within reach where Mimo stands, away from any step that just failed."""
    grass = [cell for cell in grass_near(s.grid, s.seed, s.here, REACH)
             if math.dist(cell, s.here) <= REACH and not near_failure(s.state, cell)]
    return [{"kind": "mine", "target": list(cell)} for cell in grass[:GRASS_PER_STOP]]


def seed_look(s: Situation, context) -> Find | None:
    return Find("a creature seed", True) if s.count(SEED) > 0 else None


register_reason(Reason(
    "seed", "look for a creature seed", seed_trip, seed_value, lambda s: 40.0 + s.trait("patience") / 10,
    goals=("herd",), look=seed_look, work=break_grass))


# map_land --------------------------------------------------------------------------------------

def home_cell(s: Situation):
    home = next((place for place in s.places if place["kind"] == "home"), None)
    return None if home is None else cell_of(home)


def land_seen(s: Situation) -> float:
    """The share of the dry 8x8 patches within 64 blocks of home that Mimo set foot on."""
    def look() -> float:
        center = home_cell(s)
        if center is None or s.db is None:
            return 0.0
        seen = explored(s.db, center, SURVEY)
        low_x, low_z = patch_of(center[0] - SURVEY, center[2] - SURVEY)
        high_x, high_z = patch_of(center[0] + SURVEY, center[2] + SURVEY)
        land = walked = 0
        for rx in range(low_x, high_x + 1):
            for rz in range(low_z, high_z + 1):
                dx, dz = rx * PATCH + PATCH / 2 - center[0], rz * PATCH + PATCH / 2 - center[2]
                if math.hypot(dx, dz) > SURVEY or dry_blocks(s.seed, rx, rz) == 0:
                    continue
                land += 1
                walked += (rx, rz) in seen
        return walked / land if land else 1.0
    return s.sensed("land seen", look)


register_goal(Goal(
    "map_land", "Map the land",
    "Knowing the land around home means knowing where the food, water and ore are.",
    (Milestone("Walk the land around home", lambda s: land_seen(s) / MAP_SHARE, ("explore",)),),
    score=lambda s: 40.0 + s.trait("curiosity") / 10, thought="I wonder what's out past the hills.",
    after=("first_shelter",), valid=lambda s: home_cell(s) is not None))


def map_trip(s: Situation) -> str | None:
    goal = s.brain.get("goal")
    if not goal or goal["name"] != "map_land" or land_seen(s) >= MAP_SHARE:
        return None
    return "I want to know the land around home"


def new_land(s: Situation) -> list[tuple[int, int, str]]:
    target = explore_target(s)
    return [] if target is None else [(target[0], target[2], "land it has not seen")]


register_reason(Reason(
    "map", "map the land", map_trip, lambda s, x, z: (0.0, ""), lambda s: 30.0 + s.trait("curiosity") / 5,
    goals=("map_land",), spots=new_land))
```

In `backend/survival/creatures/hunting.py`, replace:

```python
def hunt_valid(s: Situation) -> bool:
    return not s.night and (food_need(s) > 0 or not hunted_lately(s)) and bool(prey(s))
```

with:

```python
# L4: what else makes Mimo hunt though it lacks no food, as functions of the Situation
# (backend.survival.life_goals adds hides and leather while armor is its goal).
HUNT_FOR: list = []


def hunt_valid(s: Situation) -> bool:
    wanted = food_need(s) > 0 or not hunted_lately(s) or any(want(s) for want in HUNT_FOR)
    return not s.night and wanted and bool(prey(s))
```

Without a creature's blow, iron armor was never worth its ingots, and without three known diamonds mine_ore never went for one, so an armor or a diamond goal could stall for good (the controller's measure over 32 game days: no pet reached diamonds or iron armor; resolution 21). A goal lifts those gates while it is the goal.

In `backend/survival/creatures/harm.py`, replace:

```python
def armor_wanted(state: dict) -> bool:
    """Iron armor is worth its 13 ingots once a creature has hurt Mimo (L3)."""
    return state.get("hurt_at") is not None
```

with:

```python
# L4: functions of Mimo's state that make iron armor worth its ingots before any creature hurt it
# (armor as Mimo's goal, backend.survival.life_goals).
ARMOR_WANTED: list = []


def armor_wanted(state: dict) -> bool:
    """Iron armor is worth its 13 ingots once a creature has hurt Mimo (L3), or (L4) while one of
    ARMOR_WANTED says so; one that crashes counts as no (logged once)."""
    if state.get("hurt_at") is not None:
        return True
    for wants in ARMOR_WANTED:
        try:
            if wants(state):
                return True
        except Exception as error:
            log_once(logger, "armor wanted", error)
    return False
```

and replace:

```python
import sqlite3
from typing import TYPE_CHECKING
```

with:

```python
import logging
import sqlite3
from typing import TYPE_CHECKING
```

and replace:

```python
from backend.survival.memory import remember
```

with:

```python
from backend.survival.memory import remember
from backend.survival.once import log_once
```

and replace:

```python
if TYPE_CHECKING:
    from backend.survival.creatures.acts import Scene

ARMOR = {"leather_cap": 0.08, "leather_tunic": 0.12}  # the share of a blow each piece takes off
```

with:

```python
if TYPE_CHECKING:
    from backend.survival.creatures.acts import Scene

logger = logging.getLogger(__name__)

ARMOR = {"leather_cap": 0.08, "leather_tunic": 0.12}  # the share of a blow each piece takes off
```

In `backend/survival/work.py`, replace:

```python
def enough_known(s: Situation, ore: str, have: int, need: int = 3) -> bool:
    """Mimo has fewer than `need` of what `ore` gives, and with the ores of that kind it remembers it
    would have enough: one trip then gets them all (L3's gold and diamonds, needed 3 at a time)."""
    known = sum(1 for place in s.places if place["kind"] == "ore" and place["note"] == ore)
    return have < need <= have + known
```

with:

```python
# L4: functions of (Situation, ore) that let mine_ore go for any ore of that kind Mimo remembers,
# not only once it knows where enough lie (diamonds as Mimo's goal, backend.survival.life_goals).
EAGER: list = []


def eager(s: Situation, ore: str) -> bool:
    """One of EAGER wants `ore` now; one that crashes counts as no (logged once)."""
    for wants in EAGER:
        try:
            if wants(s, ore):
                return True
        except Exception as error:
            log_once(logger, "eager for ore", error)
    return False


def enough_known(s: Situation, ore: str, have: int, need: int = 3) -> bool:
    """Mimo has fewer than `need` of what `ore` gives, and with the ores of that kind it remembers it
    would have enough: one trip then gets them all (L3's gold and diamonds, needed 3 at a time).
    L4: while a goal wants the ore (EAGER), any one it remembers will do."""
    known = sum(1 for place in s.places if place["kind"] == "ore" and place["note"] == ore)
    if have < need and known >= 1 and eager(s, ore):
        return True
    return have < need <= have + known
```

and replace:

```python
import math
from typing import TYPE_CHECKING
```

with:

```python
import logging
import math
from typing import TYPE_CHECKING
```

and replace:

```python
from backend.survival.nature import SOIL
```

with:

```python
from backend.survival.nature import SOIL
from backend.survival.once import log_once
```

and replace:

```python
if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

WOOD_GOAL = 8.0
```

with:

```python
if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

WOOD_GOAL = 8.0
```

and replace:

```python
    and then, once a creature has hurt it, as much as the iron armor it lacks takes; with an iron
    pickaxe (L3), gold (until a gold pickaxe or better) and diamonds (until a diamond pickaxe), but
    only once it knows where enough lie for a pickaxe (`enough_known`)."""
```

with:

```python
    and then, once a creature has hurt it (L4: or while armor is its goal), as much as the iron
    armor it lacks takes; with an iron pickaxe (L3), gold (until a gold pickaxe or better) and
    diamonds (until a diamond pickaxe), but only once it knows where enough lie for a pickaxe
    (`enough_known`; L4: any one it knows while diamonds are its goal)."""
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import scouting  # noqa: F401  (L4's trips)
```

with:

```python
from backend.survival import life_goals, scouting  # noqa: F401  (L4's goals and trips)
```

- [ ] **Step 4: The tests that meet a hatched pet's first goal**

A newly hatched pet's goal is a home of its own, and while gathering wood advances it, rest is not offered (resolution 8): the two chooser tests whose fake Jev answered "rest" to a hatched pet answer "gather_wood" now.

In `backend/tests/test_survival_choosing.py`, replace:

```python
JEV_REST = {"answers": {"purpose": {"choice": "rest"}}}
```

with:

```python
JEV_REST = {"answers": {"purpose": {"choice": "rest"}}}
# L4: a hatched pet's first goal is a home of its own, and while wood advances it rest is not offered.
JEV_WOOD = {"answers": {"purpose": {"choice": "gather_wood"}}}
```

and replace:

```python
        chooser = self.chooser({"TYPESAFE_API_KEY": "k"}, {JEV_URL: JEV_REST}, held)
```

with:

```python
        chooser = self.chooser({"TYPESAFE_API_KEY": "k"}, {JEV_URL: JEV_WOOD}, held)
```

and replace:

```python
        self.assertEqual(chooser.poll(self.registry, BORN + 3), "rest")
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["picker"], brain["calls"]["model"], brain["last_call_at"]),
                         ("rest", "jev", 1, BORN + 1))
```

with:

```python
        self.assertEqual(chooser.poll(self.registry, BORN + 3), "gather_wood")
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["picker"], brain["calls"]["model"], brain["last_call_at"]),
                         ("gather_wood", "jev", 1, BORN + 1))
```

and replace:

```python
        chooser = Chooser(env={"TYPESAFE_API_KEY": "k"}, http=FakeHttp({JEV_URL: JEV_REST}), executor=stuck,
```

with:

```python
        chooser = Chooser(env={"TYPESAFE_API_KEY": "k"}, http=FakeHttp({JEV_URL: JEV_WOOD}), executor=stuck,
```

and replace:

```python
        self.assertEqual(chooser.poll(self.registry, BORN + 200), "rest")  # new work skips the stuck thread
```

with:

```python
        self.assertEqual(chooser.poll(self.registry, BORN + 200), "gather_wood")  # new work skips the stuck thread
```

- [ ] **Step 5: The flood guard counts what works toward no goal**

Measured over the headless runs (resolution 13): with this task's goals the busiest game hour reached 49 changes of purpose, and 62 in slow mode, while the changes toward no goal stayed at 28 at most, and 47 in slow mode; with all of L4 (after Task 10), 55 and 75, with 14 and 31 toward no goal.

`PURPOSE_EVENTS_PER_HOUR` keeps its value (52, and 55 in slow mode since L3) and now counts the changes toward no goal; the new `ALL_EVENTS_PER_HOUR` caps them all.

In `backend/tests/test_survival_sim.py`, replace:

```python
TRAPPED_AT_MOST = 180.0  # game seconds
```

with:

```python
TRAPPED_AT_MOST = 180.0  # game seconds
# L4: goals fill the day with work, and a change toward a goal (its event says ", toward ...") is
# that work, so the flood guard above now counts the other changes, and all changes get a looser
# cap of their own. Every explore trip has a reason and ends early on a find, so a trip is a change
# to explore and one to the purpose that follows up on the find (with all of L4 on L3, the busiest
# game hour reached 55, and 75 in slow mode, at most 31 of them toward no goal).
ALL_EVENTS_PER_HOUR = 90
```

and replace:

```python
            return {"state": world.state(), "calls": fake.calls, "trapped": trapped_longest, "homes": homes,
                    "purposes": [event["at"] - BORN for event in events if event["kind"] == "purpose"],
```

with:

```python
            purposes = [event for event in events if event["kind"] == "purpose"]
            return {"state": world.state(), "calls": fake.calls, "trapped": trapped_longest, "homes": homes,
                    "purposes": [event["at"] - BORN for event in purposes],
                    "free": [event["at"] - BORN for event in purposes if ", toward " not in event["text"]],
```

and replace:

```python
        self.assertLessEqual(most_in_an_hour(run["purposes"]), PURPOSE_EVENTS_PER_HOUR)
```

with:

```python
        self.assertLessEqual(most_in_an_hour(run["free"]), PURPOSE_EVENTS_PER_HOUR)
        self.assertLessEqual(most_in_an_hour(run["purposes"]), ALL_EVENTS_PER_HOUR)
```

- [ ] **Step 6: "built" is notable among goals**

A reached goal is a notable event, so on a busy life the shelter's "built" event can fall behind the newest few notable events (measured on L3's first five tasks: four goals and two finds were newer). The days runs' home test looks through all the notable events.

In `backend/tests/test_survival_days.py`, replace:

```python
        self.assertIn("built", [event["kind"] for event in notable(self.world.events(5000))])
```

with:

```python
        # L4: reached goals are notable too, so "built" may be older than the newest few notable events.
        self.assertIn("built", [event["kind"] for event in self.world.notable_events(5000)])
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_life_goals.py"`
Expected: `Ran 16 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1001 tests` … `OK` (16 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/survival/life_goals.py backend/survival/creatures/hunting.py backend/survival/creatures/harm.py backend/survival/work.py backend/survival/brain.py backend/tests/test_survival_life_goals.py backend/tests/test_survival_choosing.py backend/tests/test_survival_sim.py backend/tests/test_survival_days.py
git commit -m "feat: Mimo's goals: a home of its own, iron tools, armor, a safe yard, the land mapped, and L3's tools and herd when they come" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: A bigger stone home

**Files:**
- Create: `backend/survival/homes.py` (the goal, improve_home, and the trip for a site)
- Modify: `backend/survival/brain.py` (import it)
- Modify tests: `backend/tests/test_survival_days.py` (a second, bigger home may follow the first)
- Test: `backend/tests/test_survival_homes.py`

**Interfaces:**
- Consumes: Task 5's `life_goals.all_structures`, `built_share`, `first_home`, `home_structure`, `shelters`, `whole`, `test_survival_life_goals.built` and `shares`; Task 4's `trips.Reason`, `Find`, `register_reason`; `goals.Goal`, `Milestone`, `active`, `register_goal`; `blueprints.NAMES`, `TIERS`, `Blueprint`, `bill`, `find_site`, `shelter`, `style_for`; `building.START_SHARE`, `build_batch`, `carried_blocks`, `site_center`; `structures.start`; `memory.cell_of`, `remember`; `worldgen.terrain_height`, `SEA_LEVEL`; `purposes.Purpose`, `register`.
- Produces:
  - Purpose `improve_home` ("build a bigger home", 60 plus a tenth of creativity), offered only while `better_home` is the goal.
  - Goal `better_home`, "A bigger stone home" (after first_shelter; open while home can grow), its first milestone "Find a site for it"; raising its walls also names gather_stone and gather_wood.
  - `homes.rank(structure) -> int` (0, 1 or 2: the tier), `moved_up(s) -> bool`, `rising(s) -> dict | None`, `can_grow(s) -> bool`, `design_near(s, center) -> Blueprint | None`, `better_design(s) -> Blueprint | None` (near home or at a `site` Mimo found within 32 blocks of it; cobblestone walls; the largest bigger tier Mimo's blocks cover, else the next one; named "<Name>'s <Snug|Peaked|Round> Stone House"), `blocks_wanted(s) -> int`.
  - Trip `site` ("scout for a building site", resolution 15): while the better home is the goal and no site near home fits, flat dry ground within 32 blocks of home (1 block uneven is sure, 2 likely); after each walk Mimo tries the design where it stands, and a fit is remembered as a `site` landmark: the find.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_homes.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.blueprints import find_site
from backend.survival.goals import GOALS, adopt_goal, complete, is_open
from backend.survival.homes import better_design, blocks_wanted, moved_up, rising
from backend.survival.memory import places, structures
from backend.survival.purposes import PURPOSES
from backend.survival.trips import REASONS
from backend.tests.test_survival_life_goals import built, shares


def sites_east(grid, center, size, sides, roof):
    """Only the land 20 or more blocks east of home has room for a bigger home."""
    return find_site(grid, center, size, sides, roof) if center[0] >= 20 else None


class BetterHomeTests(unittest.TestCase):
    def test_once_mimo_has_a_home_a_bigger_stone_one_is_a_goal(self):
        world = built()
        s = world.situation()
        self.assertTrue(is_open(s, GOALS["better_home"]))
        design = better_design(s)
        self.assertEqual((design.style["size"], design.style["wall"], design.name),
                         ([4, 3], "cobblestone", "Pip's Snug Stone House"))  # the next tier up: it carries nothing

    def test_improve_home_is_offered_only_for_the_goal_and_with_half_the_blocks(self):
        world = built({"cobblestone": 64, "planks": 16})
        improve = PURPOSES["improve_home"]
        self.assertFalse(improve.valid(world.situation()))
        adopt_goal(world.state, "better_home", "utility", "", 0.0)
        s = world.situation()
        self.assertTrue(improve.valid(s))
        self.assertEqual((better_design(s).style["size"], blocks_wanted(s)), ([5, 4], 31))  # the biggest it covers
        world.state["inventory"] = {"cobblestone": 20}  # a 4x3 house takes 46: half is 23
        self.assertFalse(improve.valid(world.situation()))

    def test_it_starts_the_bigger_home_build_shelter_finishes_it_and_mimo_moves_in(self):
        world = built({"cobblestone": 64, "planks": 16})
        adopt_goal(world.state, "better_home", "utility", "", 0.0)
        world.carry_out(PURPOSES["improve_home"].plan(world.situation(), world.context()))
        s = world.situation()
        self.assertEqual(rising(s)["status"], "building")
        self.assertFalse(PURPOSES["improve_home"].valid(s))  # one at a time
        self.assertEqual(shares(s, "better_home")[0], 1.0)
        for _ in range(15):
            steps = PURPOSES["build_shelter"].plan(world.situation(), world.context())
            if not steps:
                break
            world.carry_out(steps)
        s = world.situation()
        self.assertEqual([row["status"] for row in structures(world.db)], ["done", "done"])
        home = places(world.db, ("home",))[0]
        self.assertEqual((home["x"], home["y"], home["z"]), tuple(structures(world.db)[1][axis] for axis in "xyz"))
        self.assertTrue(moved_up(s))
        self.assertTrue(complete(s, GOALS["better_home"]))


    def test_with_no_site_near_home_mimo_scouts_for_flat_ground_and_remembers_the_site(self):
        world = built()
        adopt_goal(world.state, "better_home", "utility", "", 0.0)
        site = REASONS["site"]
        with patch("backend.survival.homes.find_site", sites_east), \
                patch("backend.survival.homes.terrain_height", lambda x, z, seed: 3):
            s = world.situation()
            self.assertIsNone(better_design(s))
            self.assertTrue(is_open(s, GOALS["better_home"]))  # home can still grow: find a site first
            self.assertEqual(shares(s, "better_home")[0], 0.0)
            self.assertEqual(site.wanted(s), "no site near home fits a bigger home")
            self.assertEqual(site.value(s, 30, 0), (1.0, "flat ground"))
            self.assertIsNone(site.look(s, world.context()))  # no room here
            world.state["position"] = {"x": 24.0, "y": 1.0, "z": 1.0}
            find = site.look(world.situation(), world.context())
            self.assertEqual((find.words, find.done), ("flat ground for a bigger home", True))
            self.assertEqual([(place["x"], place["z"]) for place in places(world.db, ("site",))], [(24, 1)])
            world.state["position"] = {"x": 1.0, "y": 1.0, "z": 1.0}
            s = world.situation()
            self.assertIsNotNone(better_design(s))  # at the site it found
            self.assertIsNone(site.wanted(s))
            self.assertEqual(shares(s, "better_home")[0], 1.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_homes.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.homes'`

- [ ] **Step 3: The bigger home**

Create `backend/survival/homes.py`:

```python
"""A bigger stone home (L4): the better_home goal and its improve_home purpose.

The first shelter is as big as Mimo's materials and creativity allowed (blueprints.design_shelter).
Once it lives in one, a better home is a goal: a shelter of a bigger tier (4x3 or 5x4 inside) with
cobblestone walls, whatever Mimo's thrift. improve_home designs it near home (blueprints.find_site
keeps off everything already built): the largest bigger tier the blocks Mimo carries cover, else
the next tier up, named like "Pip's Peaked Stone House". It starts the shelter once Mimo carries
half the blocks, as build_shelter starts a first one, and places the first batch. From then on it
is the newest shelter near Mimo, so build_shelter goes on with it; when its last floor, wall or
roof block is down, home moves into it (building.finish_if_built) and build_shelter furnishes it.

improve_home is offered only while the better home is Mimo's goal, by day, with no bigger shelter
already rising: a pet does not start a second house for the fun of it. Work band: 60 plus a tenth
of creativity. The goal is open while home can grow (it is not the biggest tier yet) and is done
when Mimo lives in a stone home of a bigger tier than the first shelter it finished; its rules
score is 45 plus a tenth of creativity.

When no site fits near home, the goal's first milestone is to find one: the "site" trip
(backend.survival.trips), "scout for a building site", heads for flat dry ground (the terrain
within 3 blocks of a spot at most 1 block uneven is sure, 2 likely) within 32 blocks of home.
After each walk Mimo tries the bigger design where it stands; a site that fits is remembered as a
"site" landmark, better_design looks there too, and improve_home follows.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, terrain_height
from backend.survival.blueprints import NAMES, TIERS, Blueprint, bill, find_site, shelter, style_for
from backend.survival.building import START_SHARE, build_batch, carried_blocks, site_center
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.grid import Cell
from backend.survival.life_goals import all_structures, built_share, first_home, home_structure, shelters, whole
from backend.survival.memory import cell_of, remember
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.structures import start
from backend.survival.trips import Find, Reason, register_reason

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

STONE = "cobblestone"
GOAL = "better_home"
SITE = "site"  # a landmark: where a bigger home fits, found on a trip
SITE_REACH = 32.0  # blocks from home a site trip looks
FLAT = ((-3, -3), (-3, 0), (-3, 3), (0, -3), (0, 0), (0, 3), (3, -3), (3, 0), (3, 3))


def rank(structure: dict) -> int:
    """A shelter's tier: 0 for 3x3, 1 for 4x3, 2 for 5x4 inside."""
    size = tuple(structure["data"].get("style", {}).get("size") or TIERS[0])
    return TIERS.index(size) if size in TIERS else 0


def moved_up(s: Situation) -> bool:
    """Mimo lives in a stone home of a bigger tier than the first shelter it finished."""
    home, first = home_structure(s), first_home(s)
    return (home is not None and first is not None and rank(home) > rank(first)
            and home["data"].get("style", {}).get("wall") == STONE)


def rising(s: Situation) -> dict | None:
    """A bigger shelter Mimo started after the one it lives in and has not finished."""
    home = home_structure(s)
    if home is None:
        return None
    return next((found for found in reversed(shelters(s)) if found["id"] > home["id"] and found["status"] == "building"
                 and rank(found) > rank(home)), None)


def can_grow(s: Situation) -> bool:
    """Mimo lives in a shelter it built that is not the biggest tier."""
    home = home_structure(s)
    return home is not None and rank(home) < len(TIERS) - 1


def design_near(s: Situation, center: Cell) -> Blueprint | None:
    """A bigger stone home at the nearest site to `center`: the largest bigger tier the blocks Mimo
    carries cover, else the next tier up; None when none fits there."""
    home = home_structure(s)
    style = replace(style_for(s.state.get("traits", {}), s.seed, len(all_structures(s))), wall=STONE)
    have, bigger = carried_blocks(s), TIERS[rank(home) + 1:]
    for size in reversed(bigger):
        site = find_site(s.grid, center, size, style.doors, style.roof)
        if site is None:
            continue
        design = shelter(site, style, f"{s.state['name']}'s {NAMES[style.roof]} Stone House")
        if bill(design, s.grid) <= have or size == bigger[0]:
            return design
    return None


def better_design(s: Situation) -> Blueprint | None:
    """A bigger stone home near home or at a site Mimo found (looked for once per Situation), or None
    when home is as big as a shelter gets or no site fits."""
    def look() -> Blueprint | None:
        if not can_grow(s):
            return None
        home = site_center(s)
        centers = [home, *(cell_of(place) for place in s.places if place["kind"] == SITE
                           and math.hypot(place["x"] - home[0], place["z"] - home[2]) <= SITE_REACH)]
        return next((design for design in map(lambda center: design_near(s, center), centers) if design), None)
    return s.sensed("better_design", look)


def blocks_wanted(s: Situation) -> int:
    """The blocks Mimo carries before it starts the bigger home: half of what it takes."""
    design = better_design(s)
    return round(START_SHARE * bill(design, s.grid)) if design is not None else 0


def improving(s: Situation) -> bool:
    goal = active(s)
    return goal is not None and goal.name == GOAL


def improve_valid(s: Situation) -> bool:
    if s.night or not improving(s) or rising(s) is not None:
        return False
    return better_design(s) is not None and carried_blocks(s) >= blocks_wanted(s)


def improve_facts(s: Situation) -> str:
    design = better_design(s)
    size = "x".join(str(side) for side in design.style["size"])
    return (f"{design.name} ({size} inside, stone walls) would need {bill(design, s.grid)} blocks, "
            f"carrying {carried_blocks(s)}")


def plan_improve(s: Situation, context: ActionContext) -> list[dict]:
    """Start the bigger home and place its first blocks; build_shelter goes on with it."""
    if s.db is None or s.brain["batches"] > 0 or not improve_valid(s):
        return []
    design = better_design(s)
    start(s.db, s.grid, design, s.at)
    return build_batch(s, design)


register(Purpose(
    "improve_home", "build a bigger home",
    "Start a bigger home with stone walls near the old one; it moves in when the roof is on.",
    valid=improve_valid, facts=improve_facts, score=lambda s: 60.0 + s.trait("creativity") / 10, plan=plan_improve,
    thoughts=("A bigger home, with stone walls this time.", "Room to stretch out. Let's build it.")))


def home_blocks(s: Situation) -> float:
    if moved_up(s) or rising(s) is not None:
        return 1.0
    wanted = blocks_wanted(s)
    return carried_blocks(s) / wanted if wanted else 0.0


def site_known(s: Situation) -> float:
    return whole(moved_up(s) or rising(s) is not None or better_design(s) is not None)


register_goal(Goal(
    GOAL, "A bigger stone home",
    "The first shelter is small: a bigger home with stone walls is roomier, warmer and safer.",
    (Milestone("Find a site for it", site_known, ("improve_home", "explore")),
     Milestone("Gather blocks for a bigger home", home_blocks, ("gather_stone", "gather_wood", "improve_home")),
     Milestone("Raise its stone walls and roof", lambda s: 1.0 if moved_up(s) else built_share(s, rising(s)),
               ("build_shelter", "improve_home", "gather_stone", "gather_wood")),  # more blocks as they run out
     Milestone("Move in", lambda s: whole(moved_up(s)), ("build_shelter",))),
    score=lambda s: 45.0 + s.trait("creativity") / 10, thought="A bigger home, with stone walls this time.",
    after=("first_shelter",), valid=lambda s: rising(s) is not None or can_grow(s)))


# The trip for a site ---------------------------------------------------------------------------

def site_trip(s: Situation) -> str | None:
    if not improving(s) or rising(s) is not None or not can_grow(s) or better_design(s) is not None:
        return None
    return "no site near home fits a bigger home"


def site_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    heights = [terrain_height(x + dx, z + dz, s.seed) for dx, dz in FLAT]
    if min(heights) <= SEA_LEVEL:
        return 0.0, ""
    spread = max(heights) - min(heights)
    return (1.0, "flat ground") if spread <= 1 else (0.4, "gentle ground") if spread <= 2 else (0.0, "")


def site_look(s: Situation, context) -> Find | None:
    """Try the bigger design where Mimo stands (a trip's walk ends on the ground)."""
    if design_near(s, s.here) is None:
        return None
    return Find("flat ground for a bigger home", True, remember(s.db, SITE, s.here, s.at))


register_reason(Reason(
    "site", "scout for a building site", site_trip, site_value, lambda s: 40.0 + s.trait("creativity") / 10,
    goals=(GOAL,), look=site_look, reach=SITE_REACH))
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import life_goals, scouting  # noqa: F401  (L4's goals and trips)
```

with:

```python
from backend.survival import homes, life_goals, scouting  # noqa: F401  (L4's goals and trips)
```

- [ ] **Step 4: The days runs may see a second home**

With the better home a goal, the days runs' pet may move into a bigger stone home before the runs end, a second "moved in" event. The test takes either, and checks that home is the newest shelter built.

In `backend/tests/test_survival_days.py`, replace:

```python
        self.assertEqual(len(built), 1)
        self.assertLess(built[0]["at"], BORN + 60 + 40)  # before the second night falls
```

with:

```python
        self.assertIn(len(built), (1, 2))  # L4: a bigger stone home (the better_home goal) may follow the first
        self.assertLess(built[-1]["at"], BORN + 60 + 40)  # the first, before the second night falls
```

and replace:

```python
            shelter = blueprint_of(structures(db, ("shelter",))[0])
```

with:

```python
            shelter = blueprint_of([found for found in structures(db, ("shelter",)) if found["status"] == "done"][-1])
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_homes.py"`
Expected: `Ran 4 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1005 tests` … `OK` (4 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/survival/homes.py backend/survival/brain.py backend/tests/test_survival_homes.py backend/tests/test_survival_days.py
git commit -m "feat: a bigger stone home as a goal, a trip to scout a site when none fits near home, started by improve_home and finished by build_shelter" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: A full larder

**Files:**
- Create: `backend/survival/larder.py`
- Modify: `backend/survival/foraging.py` (the `MORE_FOOD` hook), `backend/survival/brain.py` (import it)
- Test: `backend/tests/test_survival_larder.py`

**Interfaces:**
- Consumes: Task 5's `life_goals.home_structure`, `whole`, `test_survival_life_goals.built` and `shares`; `goals.Goal`, `Milestone`, `active`, `register_goal`; `storage.chest_spot`, `chest_placed`, `chest_contents`, `spare_food`; `building.current_shelter`; `carrying.CHEST_STACKS`, `crafts_fit`, `room_for`; `cooking.made`; `structures.blueprint_of`, `clearing`; `foraging.whole_walk`, `food_need`; the `store` and `place` steps.
- Produces:
  - `foraging.MORE_FOOD: list` of `(Situation) -> float`: food a goal wants on hand beyond a day's worth, added to `food_need`.
  - Purpose `stock_larder` ("stock the larder", 55 plus a tenth of thrift), offered only while `full_larder` is the goal.
  - Goal `full_larder`, "A full larder" (after first_shelter, with a home Mimo built); its food milestone names `explore` too, for Task 4's food trip.
  - `larder.LARDER_FOOD = 60.0`, `LARDER_EXTRA = 40.0`, `FED = 50.0`; `chest_food(s) -> float`; `more_food(s) -> float`; `larder_moves(s)`, `chest_steps(s)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_larder.py`:

```python
import unittest

from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.foraging import MORE_FOOD, food_need
from backend.survival.goals import GOALS, adopt_goal, complete
from backend.survival.housework import chest_key
from backend.survival.larder import chest_food, more_food
from backend.survival.purposes import PURPOSES
from backend.survival.storage import chest_spot
from backend.tests.test_survival_life_goals import built, shares


def larder(inventory=None):
    """A pet with its first shelter built whose goal is a full larder."""
    world = built(inventory)
    adopt_goal(world.state, "full_larder", "utility", "", 0.0)
    return world


class MoreFoodTests(unittest.TestCase):
    def test_a_fed_pet_filling_its_larder_wants_more_food_on_hand(self):
        self.assertIn(more_food, MORE_FOOD)
        world = built({"cooked_fish": 1})
        self.assertEqual((more_food(world.situation()), food_need(world.situation())), (0.0, 30.0))
        adopt_goal(world.state, "full_larder", "utility", "", 0.0)
        self.assertEqual((more_food(world.situation()), food_need(world.situation())), (40.0, 70.0))
        cell = chest_spot(world.situation())
        world.state["chests"] = {chest_key(cell): {"cooked_beef": 1}}  # 35 of the 60 in the chest already
        self.assertEqual(more_food(world.situation()), 25.0)
        world.state["vitals"]["hunger"] = 40.0  # hungry: food for now comes first
        self.assertEqual(more_food(world.situation()), 0.0)


class StockLarderTests(unittest.TestCase):
    def test_it_puts_a_chest_in_first_then_stores_the_food_beyond_a_days_worth(self):
        stock = PURPOSES["stock_larder"]
        world = built({"planks": 8, "cooked_fish": 4})
        self.assertFalse(stock.valid(world.situation()))  # only for the goal
        world = larder({"planks": 8, "cooked_fish": 4})
        s = world.situation()
        self.assertTrue(stock.valid(s))
        steps = stock.plan(s, world.context())
        cell = list(chest_spot(s))
        self.assertEqual([step["kind"] for step in steps], ["craft", "place", "store"])
        self.assertEqual(steps[1:], [{"kind": "place", "target": cell, "block": "chest"},
                                     {"kind": "store", "target": cell, "item": "cooked_fish", "amount": 2}])

    def test_the_larder_is_full_with_a_days_food_in_the_chest(self):
        world = larder({"planks": 8, "cooked_fish": 4})
        s = world.situation()
        self.assertEqual(shares(s, "full_larder"), [0.0, 0.0])
        world.grid.put(*chest_spot(s), "chest")
        world.state["chests"] = {chest_key(chest_spot(s)): {"cooked_fish": 1, "red_mushroom": 5}}
        s = world.situation()
        self.assertEqual((chest_food(s), shares(s, "full_larder")), (60.0, [1.0, 1.0]))
        self.assertTrue(complete(s, GOALS["full_larder"]))
        self.assertFalse(PURPOSES["stock_larder"].valid(s))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_larder.py"`
Expected: ERROR: `ImportError: cannot import name 'MORE_FOOD' from 'backend.survival.foraging'`

- [ ] **Step 3: The larder**

In `backend/survival/foraging.py`, replace:

```python
def food_need(s: Situation) -> float:
    return max(0.0, FOOD_WANTED - food_points(s))
```

with:

```python
# L4: more food a goal wants on hand, as functions of the Situation (backend.survival.larder adds
# the larder's while a full larder is Mimo's goal).
MORE_FOOD: list = []


def food_need(s: Situation) -> float:
    return max(0.0, FOOD_WANTED + sum(more(s) for more in MORE_FOOD) - food_points(s))
```

Create `backend/survival/larder.py`:

```python
"""A full larder (L4): the full_larder goal and its stock_larder purpose.

Mimo carries a game day's worth of food (foraging.FOOD_WANTED, 60 hunger), and build_storage puts
away only what is beyond that, and only when its arms fill. While a full larder is its goal and it
is not hungry (hunger FED or more), Mimo wants up to LARDER_EXTRA more food on hand (`more_food`,
added to foraging.food_need), so forage, fish, hunt and farm gather past a day's worth.
stock_larder puts the chest in its corner of the shelter first when there is none (carried, or
made from 8 planks, as build_storage does), then carries the spare food home and stores it. The
larder is full when the chests hold LARDER_FOOD hunger of food Mimo would eat (not what it knows
is poisonous). build_storage still takes food out when Mimo runs short: that is what a larder is
for.

stock_larder is offered only while the full larder is Mimo's goal, by day, at the shelter Mimo
built: to put the chest in, or with spare food carried and room in the chest. Work band: 55 plus
a tenth of thrift. The goal's rules score is 45 plus a tenth of thrift, 15 more when Mimo is
hungry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival import foraging
from backend.survival.building import current_shelter
from backend.survival.carrying import CHEST_STACKS, crafts_fit, room_for
from backend.survival.cooking import made
from backend.survival.foraging import whole_walk
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.life_goals import home_structure, whole
from backend.survival.purposes import Purpose, foods, register
from backend.survival.situation import Situation
from backend.survival.steps import FOOD, REACH
from backend.survival.storage import chest_contents, chest_placed, chest_spot, spare_food
from backend.survival.structures import blueprint_of, clearing

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

GOAL = "full_larder"
LARDER_FOOD = 60.0  # hunger points of food in the chests that make a full larder: a day's worth
LARDER_EXTRA = 40.0  # at most this much more food Mimo wants on hand while it fills the larder
FED = 50.0  # hunger from which Mimo gathers for the larder


def chest_food(s: Situation) -> float:
    """Hunger points of the food in all of Mimo's chests, leaving out food it knows is poisonous."""
    return sum(FOOD[item] * chest[item] for chest in s.state.get("chests", {}).values()
               for item in foods(chest, s.poisons))


def filling(s: Situation) -> bool:
    goal = active(s)
    return goal is not None and goal.name == GOAL


def more_food(s: Situation) -> float:
    """Food beyond a day's worth Mimo wants on hand while it fills the larder and is not hungry."""
    if not filling(s) or s.vitals["hunger"] < FED:
        return 0.0
    return min(LARDER_EXTRA, max(0.0, LARDER_FOOD - chest_food(s)))


foraging.MORE_FOOD.append(more_food)


def larder_moves(s: Situation) -> list[tuple[str, int]]:
    """(food, amount) stock_larder would store: the spare food, as far as the chest has room."""
    chest = chest_contents(s, chest_spot(s))
    moves = []
    for item, amount in spare_food(s):
        amount = min(amount, room_for(chest, item, CHEST_STACKS))
        if amount > 0:
            chest[item] = chest.get(item, 0) + amount
            moves.append((item, amount))
    return moves


def chest_steps(s: Situation) -> list[dict] | None:
    """The steps that put a chest in its corner of the shelter: [] when one stands there, None when
    Mimo has none and cannot make one it has room to carry."""
    cell = chest_spot(s)
    if chest_placed(s, cell):
        return []
    crafting = [] if s.count("chest") > 0 else made(dict(s.inventory), "chest")
    if crafting is None or not crafts_fit(s.inventory, crafting):
        return None
    return crafting + clearing(s.grid, cell) + [{"kind": "place", "target": list(cell), "block": "chest"}]


def stock_valid(s: Situation) -> bool:
    if s.night or not filling(s) or chest_spot(s) is None or chest_food(s) >= LARDER_FOOD:
        return False
    steps = chest_steps(s)
    return steps is not None and (bool(steps) or bool(larder_moves(s)))


def plan_stock(s: Situation, context: ActionContext) -> list[dict]:
    """Walk home, put the chest in when there is none, and put the spare food in it."""
    if s.brain["batches"] > 0 or not stock_valid(s):
        return []
    cell = chest_spot(s)
    home = blueprint_of(current_shelter(s))
    steps = [] if s.distance(cell) <= REACH and s.here in home.stands else [whole_walk(home.anchor)]
    return steps + chest_steps(s) + [{"kind": "store", "target": list(cell), "item": item, "amount": amount}
                                     for item, amount in larder_moves(s)]


register(Purpose(
    "stock_larder", "stock the larder",
    "Carry spare food home and keep it in the chest, so a hungry day never turns into starving.",
    valid=stock_valid,
    facts=lambda s: f"{round(chest_food(s))} of {round(LARDER_FOOD)} hunger of food in the chest; "
                    f"{sum(amount for _, amount in larder_moves(s))} spare food carried",
    score=lambda s: 55.0 + s.trait("thrift") / 10, plan=plan_stock,
    thoughts=("Some for now, some for later.", "A full chest means no hungry nights.")))


def chest_at_home(s: Situation) -> float:
    home = home_structure(s)
    cell = blueprint_of(home).one("chest") if home is not None else None
    return whole(cell is not None and s.grid.material(*cell) == "chest")


register_goal(Goal(
    GOAL, "A full larder",
    "A chest of food at home means a hungry day or a long night never turns into starving.",
    (Milestone("Put a chest at home", chest_at_home, ("build_storage", "stock_larder")),
     Milestone("Store a day's food in it", lambda s: chest_food(s) / LARDER_FOOD,
               ("forage", "fish", "hunt", "farm", "cook", "stock_larder", "explore"))),
    score=lambda s: 45.0 + s.trait("thrift") / 10 + (15.0 if s.vitals["hunger"] < 50 else 0.0),
    thought="A full chest at home. Then no night is a hungry one.", after=("first_shelter",),
    valid=lambda s: home_structure(s) is not None))
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import homes, life_goals, scouting  # noqa: F401  (L4's goals and trips)
```

with:

```python
from backend.survival import homes, larder, life_goals, scouting  # noqa: F401  (L4's goals and trips)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_larder.py"`
Expected: `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1008 tests` … `OK` (3 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/larder.py backend/survival/foraging.py backend/survival/brain.py backend/tests/test_survival_larder.py
git commit -m "feat: a full larder as a goal: more food gathered, a chest put in and a day's food stored" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Curiosity

The owner, after watching the pet until day 17: "it seems like its getting content with a small house and a daily routine I want it to be more curious and constantly exploring and trying to undestand the world". This task gives Mimo curiosity, an inner value from 0 to 100 that grows while it lives on ground it knows and falls with each discovery, and lets it act on it: a restless pet's trips score higher and count as a need, whenever nothing for its goal or a need is to be done it goes to see something new rather than sit, and once its needs are met its day plan sets time aside to wander (resolution 19). Rest lasts two game minutes at a time, not ten, so a pet that sat down looks again soon for something to do (resolution 22). Task 9 adds the discovery goals it steers toward; Task 10 tells the model and the viewer how it feels.

**Files:**
- Create: `backend/survival/curiosity.py`
- Modify: `backend/survival/brain.py` (`observe_step` hands the step's events to `note_discoveries` before a trip looks around; `notice_step` calls `tend_curiosity`), `backend/survival/purposes.py` (rest lasts at most two game minutes)
- Test: `backend/tests/test_survival_curiosity.py`

**Interfaces:**
- Consumes: Task 1's `goals.URGES`, Task 2's `goals.PLAN_EXTRAS`, Task 4's `trips.LIFTS`, `FINDS`, `Find`, `Reason`, `register_reason`, Task 5's `life_goals.openings_near`, `looked_into`, `opening_words` and `test_survival_life_goals.built`; `exploring.area_novelty`; `memory.know`, `known`, `places`, `patch_of`, `BUILT`; `creatures.kinds.land_kinds`, `creatures.table.dead`; `worldgen.biome_at`; `clock.DAY_SECONDS`; `triggers.ensure_brain`.
- Produces:
  - `state["brain"]["curiosity"]`: `{"value", "at", "new_at", "noticed_at", "seen", "met_at"}`; constants `START = 40.0`, `CLOCK_HOUR = DAY_SECONDS / 24`, `GROWTH = 2.0` a clock hour, `NEEDS_MET = 1.5`, `NEW_GROUND = 3.0`, `NEW_BIOME = 30.0`, `NEW_BLOCK = 6.0`, `NEW_CREATURE = 20.0`, `NEW_PLACE = 10.0`, `LIFTED = 50.0`, `LIFT_RATE = 0.6`, `CURIOUS = 60.0`, `RESTLESS = 75.0`, `PLAN_FROM = 40.0`, `CREATURE_SIGHT = 24.0`, `MET_EVERY = 60.0`, `WANDER_REACH = 90.0`, `NEW_ENOUGH = 0.25`, `FAR_OUT = 72`; `wander_spots(s)` (new ground FAR_OUT blocks away at 16 headings, within WANDER_REACH of home, not visited lately).
  - `curiosity.curiosity_state(state, at)`, `value_of(brain)`, `needs_met(state, db)`, `discovered(state, at, drop, ground_only=False)`, `meet_creatures(state, context, at)`, `tend_curiosity(state, context, at)`, `note_discoveries(state, step, context, at, events)`, `lift(s)`, `feeling(brain, at, scale)`, `curiosity_view(brain, at, scale) -> {"level", "feeling"} | None`, `biome_words(biome)`, `seen(s, fact)`, `time_to_wander(s, goal)`.
  - Facts in memory_knowledge: `"biome"`, `"block"`, `"creature"`. Events: `found` "Pip saw the taiga for the first time." and "Pip met its first sheep.".
  - The `wander` trip ("look for something new", always once the tick tends curiosity, up to WANDER_REACH blocks from home; serves Task 9's discovery goals); `trips.LIFTS` gains `lift`, `trips.FINDS` a new place's discovery, `goals.URGES["explore"]` (from RESTLESS on), `goals.PLAN_EXTRAS` the time to wander.
  - `purposes.REST_LONGEST = 120.0` (was 600).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_curiosity.py`:

```python
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival import curiosity
from backend.survival.brain import BRAIN
from backend.survival.curiosity import (
    CLOCK_HOUR, NEW_BIOME, NEW_BLOCK, NEW_CREATURE, NEW_GROUND, NEW_PLACE, START, curiosity_state, curiosity_view,
    lift, note_discoveries, tend_curiosity, time_to_wander,
)
from backend.survival.goals import GOALS, URGES, Goal, adopt_goal, goal_state
from backend.survival.hatch import hatch
from backend.survival.memory import known
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.trips import REASONS
from backend.tests.test_survival_life_goals import built

BORN = 1_000_000.0
DAY = 3600.0


class Creatures:
    """A herd that only answers who is near."""

    def __init__(self, *kinds):
        self.kinds = kinds

    def near(self, x, z, reach):
        return [{"kind": kind, "state": {}} for kind in self.kinds]


class CuriosityTests(unittest.TestCase):
    def setUp(self):
        self.world = built()
        self.state = self.world.state
        self.context = self.world.context()
        self.context.events = []

    def value(self):
        return self.state["brain"]["curiosity"]["value"]

    def test_it_grows_on_known_ground_and_faster_once_needs_are_met(self):
        tend_curiosity(self.state, self.context, 0.0)  # a newborn's, at START; the home biome is known
        self.assertEqual(self.value(), START)
        self.assertEqual(len(known(self.world.db, "biome")), 1)
        self.state["vitals"]["hunger"] = 30.0  # hungry: needs not met
        tend_curiosity(self.state, self.context, 3 * CLOCK_HOUR)
        self.assertEqual(self.value(), START + 6.0)  # 2 an hour of the clock
        self.state["vitals"]["hunger"] = 100.0  # fed, rested, warm, well, with a home it built
        tend_curiosity(self.state, self.context, 5 * CLOCK_HOUR)
        self.assertEqual(self.value(), START + 12.0)  # 3 an hour
        tend_curiosity(self.state, self.context, 2 * DAY)
        self.assertEqual(self.value(), 100.0)

    def test_discoveries_lower_it_and_are_remembered(self):
        tend_curiosity(self.state, self.context, 0.0)
        curiosity_state(self.state, 0.0)["value"] = 90.0
        self.state["brain"]["new_ground_at"] = 5.0
        with patch("backend.survival.curiosity.biome_at", lambda x, z, seed: "taiga"):
            note_discoveries(self.state, {"kind": "mine", "block": "gravel"}, self.context, 5.0,
                             [(5.0, "found", "Pip spotted iron ore."), (5.0, "plan", "")])
        self.assertEqual(self.value(), 90.0 - NEW_PLACE - NEW_GROUND - NEW_BIOME - NEW_BLOCK)
        self.assertEqual(self.context.events, [(5.0, "found", "Pip saw the taiga for the first time.")])
        self.assertIn("gravel", known(self.world.db, "block"))
        self.assertEqual({key: self.state["brain"]["curiosity"][key] for key in ("new_at", "noticed_at", "seen")},
                         {"new_at": 5.0, "noticed_at": 5.0, "seen": 1})
        self.state["brain"]["new_ground_at"] = 9.0  # new ground alone: a discovery, but not a notable one
        note_discoveries(self.state, {"kind": "walk"}, self.context, 9.0, [])
        self.assertEqual({key: self.state["brain"]["curiosity"][key] for key in ("new_at", "noticed_at", "seen")},
                         {"new_at": 9.0, "noticed_at": 5.0, "seen": 2})

    def test_creatures_in_sight_are_met_once_a_game_minute(self):
        tend_curiosity(self.state, self.context, 0.0)
        self.world.grid.herd = Creatures("sheep", "cow")
        tend_curiosity(self.state, self.context, 30.0)  # looked over at 0.0 already
        self.assertEqual(known(self.world.db, "creature"), [])
        tend_curiosity(self.state, self.context, 61.0)
        self.assertEqual(sorted(known(self.world.db, "creature")), ["cow", "sheep"])
        self.assertEqual([text for _, _, text in self.context.events],
                         ["Pip met its first cow.", "Pip met its first sheep."])
        self.assertAlmostEqual(self.value(), START + 61.0 / CLOCK_HOUR * 3.0 - 2 * NEW_CREATURE)

    def test_high_curiosity_lifts_explore_makes_it_a_need_and_is_a_reason_to_wander(self):
        tend_curiosity(self.state, self.context, 0.0)
        levels = ((10.0, 0.0, False), (50.0, 0.0, False), (65.0, 9.0, False), (90.0, 24.0, True))
        for value, lifted, urge in levels:
            curiosity_state(self.state, 0.0)["value"] = value
            s = self.world.situation()
            self.assertEqual((lift(s), URGES["explore"](s)), (lifted, urge))
        self.assertEqual(REASONS["wander"].wanted(self.world.situation()), "I feel very restless; nothing new yet")
        curiosity_state(self.state, 0.0)["value"] = 10.0  # content, but there is always something new to see
        self.assertEqual(REASONS["wander"].wanted(self.world.situation()), "there is always more to see")
        del self.state["brain"]["curiosity"]
        self.assertIsNone(REASONS["wander"].wanted(self.world.situation()))  # not before the tick tends it

    def test_the_model_and_the_viewer_are_told_how_it_feels(self):
        brain = {"curiosity": {"value": 80.0, "new_at": 0.0}}
        self.assertEqual(curiosity_view(brain, 2 * CLOCK_HOUR + 5.0, 1.0),
                         {"level": 80, "feeling": "restless; nothing new for 2 hours"})
        self.assertEqual(curiosity_view(brain, 3 * DAY, 1.0)["feeling"], "restless; nothing new for 3 game days")
        self.assertEqual(curiosity_view({"curiosity": {"value": 10.0, "new_at": 0.0}}, 5.0, 1.0)["feeling"],
                         "content; just saw something new")
        self.assertIsNone(curiosity_view({}, 5.0, 1.0))

    def test_once_needs_are_met_the_day_sets_time_aside_to_wander_until_a_discovery(self):
        tend_curiosity(self.state, self.context, 0.0)
        adopt_goal(self.state, "iron_tools", "utility", "", 0.0)
        goal = goal_state(self.state)["goal"]
        self.assertEqual(time_to_wander(self.world.situation(), GOALS["iron_tools"]),
                         {"text": "Take time to wander and see something new", "kind": "wander"})
        wandering = Goal("wandering", "Wandering", "", GOALS["iron_tools"].milestones, score=lambda s: 1.0, thought="",
                         repeat=True)
        self.assertIsNone(time_to_wander(self.world.situation(), wandering))  # a discovery goal wanders already
        goal["plan"] = [{"text": "Take time to wander and see something new", "kind": "wander", "done": False,
                         "step": None}]
        curiosity.discovered(self.state, 5.0, NEW_PLACE)
        self.assertTrue(goal["plan"][0]["done"])
        curiosity_state(self.state, 0.0)["value"] = 20.0
        self.assertIsNone(time_to_wander(self.world.situation(), GOALS["iron_tools"]))

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        forget_logged()
        with patch("backend.survival.curiosity.needs_met", side_effect=RuntimeError("boom")), \
                self.assertLogs("backend.survival.curiosity", level="ERROR") as logs:
            tend_curiosity(self.state, self.context, 0.0)
            tend_curiosity(self.state, self.context, 5.0)
        self.assertEqual(len(logs.output), 1)


class BrainTests(unittest.TestCase):
    def test_the_brain_tends_curiosity_after_each_vitals_step(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            hatch(registry, random.Random(8), timestamp=BORN)
            state = tick_life(registry, BORN + 1, scale=1.0, mind=BRAIN)
        self.assertIn(state["brain"]["curiosity"]["value"], (START, START - NEW_GROUND))  # it may walk new ground


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_curiosity.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.curiosity'`

- [ ] **Step 3: Curiosity**

Create `backend/survival/curiosity.py`:

```python
"""Curiosity (L4, the owner's day-17 note: "it seems like its getting content with a small house and
a daily routine I want it to be more curious and constantly exploring and trying to undestand the
world").

Curiosity is an inner value from 0 to 100, kept in state["brain"]["curiosity"]: {"value", "at" (when
it was last tended), "new_at" (the last discovery), "noticed_at" (the last one more than new
ground), "seen" (discoveries so far), "met_at" (when Mimo last looked over the creatures near it)}.
A newborn starts at START.
- It grows while Mimo lives on ground it knows: GROWTH an hour of the day's clock (CLOCK_HOUR, a
  24th of a game day, as the HUD's clock counts), NEEDS_MET times that once its needs are met
  (`needs_met`: fed, rested, warm and healthy, with a home it built).
- Discoveries lower it (`discovered`): ground it never walked (NEW_GROUND, once a step), a biome it
  never saw (NEW_BIOME: "Pip saw the taiga for the first time."), a kind of block it never dug
  (NEW_BLOCK), a kind of creature it never met (NEW_CREATURE: "Pip met its first sheep."), and a
  place new to it (NEW_PLACE: each "found" or "discovered" event of the step, as first ores, water
  and home are, and each new place a trip finds, trips.FINDS). The biomes, blocks and creatures it
  met are remembered in memory_knowledge (facts "biome", "block" and "creature", with when). The
  biome it hatched in is known from the start, without a word.
- High curiosity lifts every explore trip (`lift`, trips.LIFTS): from LIFTED on, LIFT_RATE a point,
  up to 30 more at 100, into the work band. From RESTLESS on, exploring meets a need (goals.URGES),
  so goal work does not crowd it out. Curiosity is always a reason of its own, the "wander" trip
  ("look for something new": land it has never seen, a biome where creatures it never met live, a
  cave mouth it has not looked into, then new ground, near or FAR_OUT blocks away, up to
  WANDER_REACH blocks from home): when nothing for its goal or a need is on offer, Mimo goes to
  see something new rather than sit and rest (the trip serves the discovery goals, so it is worked
  toward one of them meanwhile). Once its needs are met and it is curious (PLAN_FROM), the day
  plan sets time aside to wander (goals.PLAN_EXTRAS), ticked off by the next discovery.
- The model is told how it feels (`feeling`, `curiosity_view`): "restless; nothing new for 2 game
  days".
The tick tends it (`tend_curiosity`, from brain.notice_step; the creatures in sight are looked over
there, once a game minute) and hears about each finished step (`note_discoveries`, from
brain.observe_step). A crash is logged once and the tick goes on.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.services.worldgen import biome_at
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.kinds import land_kinds
from backend.survival.creatures.table import dead
from backend.survival.exploring import HEADINGS, area_novelty, home_cell, lately
from backend.survival.goals import PLAN_EXTRAS, URGES
from backend.survival.life_goals import looked_into, opening_words, openings_near
from backend.survival.memory import BUILT, know, known, patch_of, places
from backend.survival.once import log_once
from backend.survival.situation import Situation
from backend.survival.steps import as_cell, label
from backend.survival.triggers import ensure_brain
from backend.survival.trips import FINDS, LIFTS, Find, Reason, register_reason

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

START = 40.0
CLOCK_HOUR = DAY_SECONDS / 24  # game seconds in an hour of the day's clock
GROWTH = 2.0  # points a clock hour
NEEDS_MET = 1.5  # times faster once needs are met
NEW_GROUND = 3.0
NEW_BIOME = 30.0
NEW_BLOCK = 6.0
NEW_CREATURE = 20.0
NEW_PLACE = 10.0
LIFTED = 50.0  # curiosity past this lifts explore...
LIFT_RATE = 0.6  # ...this much a point
CURIOUS = 60.0  # it feels restless from here on
WANDER_REACH = 90.0  # blocks from home a wander trip may go, as far as the discovery goals look
NEW_ENOUGH = 0.25  # ground this new (exploring.area_novelty over 9) is worth a wander
FAR_OUT = 72  # blocks away a wander also heads for new ground, past what explore's targets reach
RESTLESS = 75.0  # exploring meets a need
PLAN_FROM = 40.0  # the day plan sets time aside to wander
CREATURE_SIGHT = 24.0
MET_EVERY = 60.0  # game seconds between two looks over the creatures near
FED, RESTED, WARM, WELL = 60.0, 50.0, 50.0, 60.0
BIOME_WORDS = {"meadow": "a meadow", "forest": "a forest", "birch_forest": "a birch forest", "taiga": "the taiga",
               "swamp": "a swamp", "desert": "a desert", "alpine": "the mountains"}
OPENING_NEAR = 12


def biome_words(biome: str) -> str:
    return BIOME_WORDS.get(biome, f"the {label(biome)}")


def curiosity_state(state: dict, at: float) -> dict:
    """The brain's curiosity, started at START for a world from before it."""
    fresh = {"value": START, "at": at, "new_at": None, "noticed_at": None, "seen": 0, "met_at": None}
    return ensure_brain(state).setdefault("curiosity", fresh)


def value_of(brain: dict | None) -> float:
    return float(((brain or {}).get("curiosity") or {}).get("value", START))


def needs_met(state: dict, db) -> bool:
    """Fed, rested, warm and healthy, with a home it built."""
    vitals = state["vitals"]
    if vitals["hunger"] < FED or vitals["energy"] < RESTED or vitals["warmth"] < WARM or vitals["health"] < WELL:
        return False
    return any(place["note"] == BUILT for place in places(db, ("home",)))


def discovered(state: dict, at: float, drop: float, ground_only: bool = False) -> None:
    """A discovery: curiosity falls by `drop`, and the day's time to wander is ticked off (by more
    than new ground)."""
    curiosity = curiosity_state(state, at)
    curiosity["value"] = max(0.0, curiosity["value"] - drop)
    curiosity["new_at"] = at
    curiosity["seen"] += 1
    if ground_only:
        return
    curiosity["noticed_at"] = at
    goal = ensure_brain(state).get("goal") or {}
    for entry in goal.get("plan") or []:
        if entry.get("kind") == "wander":
            entry["done"] = True


def meet_creatures(state: dict, context: ActionContext, at: float) -> None:
    """Kinds of creatures in sight Mimo never met are met now: remembered and announced."""
    herd = context.grid.herd
    if herd is None or context.db is None:
        return
    x, _, z = as_cell(state["position"])
    kinds = {creature["kind"] for creature in herd.near(x, z, CREATURE_SIGHT) if not dead(creature)}
    for kind in sorted(kinds - set(known(context.db, "creature"))):
        know(context.db, kind, "creature", at)
        context.events.append((at, "found", f"{state['name']} met its first {label(kind)}."))
        discovered(state, at, NEW_CREATURE)


def tend_curiosity(state: dict, context: ActionContext, at: float) -> None:
    """After a vitals step (brain.notice_step): curiosity grows with the game time since it was last
    tended, and the creatures in sight are looked over once a game minute."""
    if context.db is None or state.get("died_at") is not None:
        return
    try:
        fresh = "curiosity" not in ensure_brain(state)
        curiosity = curiosity_state(state, at)
        if fresh:  # the biome Mimo hatched in is no discovery
            x, _, z = as_cell(state["position"])
            know(context.db, biome_at(x, z, state["world_seed"]), "biome", at)
        scale = context.clock_at(at)["time_scale"]
        rate = GROWTH * (NEEDS_MET if needs_met(state, context.db) else 1.0)
        hours = max(0.0, at - curiosity["at"]) * scale / CLOCK_HOUR
        curiosity["value"] = min(100.0, curiosity["value"] + rate * hours)
        curiosity["at"] = at
        met = curiosity.get("met_at")
        if met is None or (at - met) * scale >= MET_EVERY:
            curiosity["met_at"] = at
            meet_creatures(state, context, at)
    except Exception as error:
        log_once(logger, "curiosity", error)


def note_discoveries(state: dict, step: dict, context: ActionContext, at: float, events: list) -> None:
    """After a finished step (brain.observe_step), before a trip looks around: new ground, a new
    biome where Mimo stands, a new kind of block dug, and the places the step's events found."""
    db = context.db
    if db is None or "curiosity" not in ensure_brain(state):
        return
    try:
        drop = NEW_PLACE * sum(1 for event in events if event[1] in ("found", "discovered"))
        ground = NEW_GROUND if ensure_brain(state).get("new_ground_at") == at else 0.0
        x, _, z = as_cell(state["position"])
        biome = biome_at(x, z, state["world_seed"])
        if biome not in known(db, "biome"):
            know(db, biome, "biome", at)
            context.events.append((at, "found", f"{state['name']} saw {biome_words(biome)} for the first time."))
            drop += NEW_BIOME
        block = step.get("block") if step["kind"] == "mine" else None
        if block and block not in known(db, "block"):
            know(db, block, "block", at)
            drop += NEW_BLOCK
        if drop or ground:
            discovered(state, at, drop + ground, ground_only=not drop)
    except Exception as error:
        log_once(logger, "curiosity discoveries", error)


def place_found(state: dict, find: Find, at: float) -> None:
    if find.new:
        discovered(state, at, NEW_PLACE)


FINDS.append(place_found)


# What curiosity does ---------------------------------------------------------------------------

def lift(s: Situation) -> float:
    """What curiosity adds to explore's score: LIFT_RATE a point past LIFTED."""
    return max(0.0, value_of(s.brain) - LIFTED) * LIFT_RATE


LIFTS.append(lift)
URGES["explore"] = lambda s: value_of(s.brain) >= RESTLESS


def since_words(seconds: float | None) -> str:
    if seconds is None:
        return "nothing new yet"
    if seconds >= DAY_SECONDS:
        days = math.floor(seconds / DAY_SECONDS)
        return f"nothing new for {days} game day{'s' if days > 1 else ''}"
    if seconds >= CLOCK_HOUR:
        hours = math.floor(seconds / CLOCK_HOUR)
        return f"nothing new for {hours} hour{'s' if hours > 1 else ''}"
    return "just saw something new"


def feeling(brain: dict | None, at: float, scale: float) -> str:
    """"restless; nothing new for 2 game days"."""
    level = value_of(brain)
    mood = "content" if level < 30 else "curious" if level < CURIOUS else "restless" if level < 90 else "very restless"
    new_at = ((brain or {}).get("curiosity") or {}).get("new_at")
    return f"{mood}; {since_words(None if new_at is None else max(0.0, at - new_at) * scale)}"


def curiosity_view(brain: dict | None, at: float, scale: float) -> dict | None:
    """Curiosity for /api/mimo and the model: {"level", "feeling"}; None before it is tended."""
    if not (brain or {}).get("curiosity"):
        return None
    return {"level": round(value_of(brain)), "feeling": feeling(brain, at, scale)}


# The wander trip -------------------------------------------------------------------------------

def seen(s: Situation, fact: str) -> set[str]:
    return s.sensed(f"known {fact}", lambda: set(known(s.db, fact)) if s.db is not None else set())


def unmet_kinds(s: Situation, biome: str) -> list[str]:
    return [kind.name for kind in land_kinds(biome) if kind.name not in seen(s, "creature")]


def wander_wanted(s: Situation) -> str | None:
    """Always, once the tick tends curiosity: why, in words."""
    if not s.brain.get("curiosity"):
        return None
    if value_of(s.brain) < CURIOUS:
        return "there is always more to see"
    return f"I feel {feeling(s.brain, s.at, s.scale)}"


def wander_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    biome = biome_at(x, z, s.seed)
    if biome not in seen(s, "biome"):
        return 1.0, f"{biome_words(biome)}, which it has never seen"
    if unmet_kinds(s, biome):
        return 0.7, f"{biome_words(biome)}, where creatures it never met live"
    for kind, ox, oz in openings_near(s.seed, x, z, OPENING_NEAR):
        if not looked_into(s, ox, oz):
            return 0.6, opening_words(kind)
    new = area_novelty(s, patch_of(x, z)) / 9
    return (0.3, "new ground") if new >= NEW_ENOUGH else (0.0, "")


def wander_spots(s: Situation) -> list[tuple[int, int, str]]:
    """New ground farther out: columns FAR_OUT blocks away at 16 headings, within WANDER_REACH of
    home, in patches Mimo did not visit lately and whose area is new enough, so a pet that walked
    all the land near it lately still finds somewhere new to go."""
    home, (x, _, z) = home_cell(s), s.here
    found = []
    for heading in range(HEADINGS):
        angle = heading * 2 * math.pi / HEADINGS
        tx, tz = x + round(math.cos(angle) * FAR_OUT), z + round(math.sin(angle) * FAR_OUT)
        if home is not None and math.hypot(tx - home[0], tz - home[2]) > WANDER_REACH:
            continue
        patch = patch_of(tx, tz)
        if not lately(s, patch) and area_novelty(s, patch) / 9 >= NEW_ENOUGH:
            found.append((tx, tz, "new ground farther out"))
    return found


def wander_look(s: Situation, context: ActionContext) -> Find | None:
    """Anything new since the trip began, more than new ground, is what it came for."""
    noticed = (s.brain.get("curiosity") or {}).get("noticed_at")
    since = (s.brain.get("trip") or {}).get("since")
    if noticed is None or since is None or noticed < since:
        return None
    return Find("something new", True, new=False)


register_reason(Reason(
    "wander", "look for something new", wander_wanted, wander_value, lambda s: 35.0,
    goals=("new_land", "new_creature", "cave", "water", "far_hills"), spots=wander_spots, look=wander_look,
    reach=WANDER_REACH))


def time_to_wander(s: Situation, goal) -> dict | None:
    """Once needs are met and Mimo is curious, the day plan sets time aside to wander."""
    if value_of(s.brain) < PLAN_FROM or s.db is None or not needs_met(s.state, s.db) or goal.repeat:
        return None
    return {"text": "Take time to wander and see something new", "kind": "wander"}


PLAN_EXTRAS.append(time_to_wander)
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import homes, larder, life_goals, scouting  # noqa: F401  (L4's goals and trips)
```

with:

```python
from backend.survival import homes, larder, life_goals, scouting  # noqa: F401  (L4's goals and trips)
from backend.survival.curiosity import note_discoveries, tend_curiosity
```

and replace:

```python
(backend.survival.trips.look_after); a find that is what it came for ends the trip.
"""
```

with:

```python
(backend.survival.trips.look_after); a find that is what it came for ends the trip. Curiosity
(backend.survival.curiosity) grows after each vitals step and falls with each discovery a
finished step makes.
"""
```

and replace:

```python
    kind, name = step["kind"], state["name"]
    if kind == "mine":
```

with:

```python
    kind, name = step["kind"], state["name"]
    mark = len(context.events)  # L4: this step's events, for curiosity
    if kind == "mine":
```

and replace:

```python
    look_after(state, step, context, at)
```

with:

```python
    note_discoveries(state, step, context, at, context.events[mark:])
    look_after(state, step, context, at)
```

and replace:

```python
    tend_goal(state, context, at, phase)
```

with:

```python
    tend_goal(state, context, at, phase)
    tend_curiosity(state, context, at)
```

In `backend/survival/purposes.py`, replace:

```python
REST_LONGEST = 600.0  # game seconds
```

with:

```python
REST_LONGEST = 120.0  # game seconds (L4: two game minutes, then Mimo looks again for something to do)
```

and replace:

```python
    """Wait in short steps until a trigger other than idle is pending, at most 10 game minutes.
```

with:

```python
    """Wait in short steps until a trigger other than idle is pending, at most two game minutes (L4).
```

and replace:

```python
    "rest", "rest", "Stay put and rest until something happens, at most ten game minutes.",
```

with:

```python
    "rest", "rest", "Stay put and rest until something happens, at most two game minutes.",
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_curiosity.py"`
Expected: `Ran 8 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1016 tests` … `OK` (8 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/curiosity.py backend/survival/brain.py backend/survival/purposes.py backend/tests/test_survival_curiosity.py
git commit -m "feat: curiosity that grows on known ground and falls with each discovery, lifting a restless pet's trips and setting time aside to wander" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 9: Discovery goals

Something new to go and see is always on offer once Mimo has a home (resolution 20): see new lands, meet a new creature, look into a cave, follow the water, map the far hills. They repeat, count only what Mimo finds after they were set, pull harder the more curious Mimo is, and each has a trip of its own.

**Files:**
- Create: `backend/survival/discovery.py`
- Modify: `backend/survival/brain.py` (import it)
- Test: `backend/tests/test_survival_discovery.py`

**Interfaces:**
- Consumes: Task 1's `Goal(..., repeat=True)`, Task 3's `offers` (a repeating goal is always among them), Task 4's `trips`, Task 5's `life_goals.HILLS`, `iron_look`, `looked_into`, `opening_spots`, `opening_words`, `openings_near`, `whole` and `test_survival_life_goals.built`, `one_sinkhole`, Task 8's `curiosity.RESTLESS`, `biome_words`, `meet_creatures`, `seen`, `value_of`, `curiosity_state`; `foraging.fishing_spots`; `exploring.area_novelty`; `memory.know`, `mark_explored`, `remember`, `patch_of`, `PATCH`, `BUILT`; `worldgen.biome_at`, `terrain_height`, `SEA_LEVEL`; `creatures.kinds.land_kinds`; `test_survival_building.World`.
- Produces:
  - Goals `new_land`, `new_creature`, `cave`, `water`, `far_hills` (all `repeat=True`, after first_shelter), with their trips of the same names; constants `DISCOVERY_REACH = 90.0`, `SAMPLE_STEP = 16`, `RESTLESS_PULL = 100.0`, `FAR_FROM = 48.0`, `FAR_PATCHES = 12`, `WATER_NEAR = 16.0`.
  - `discovery.pull(s) -> float` (30 + 0.7 × curiosity, + RESTLESS_PULL once restless), `since(s, name)`, `learned_since(s, fact, at)`, `found_since(s, kind, at)`, `within_reach(s)`, `biomes_in_reach(s)`, `far_walked(s)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_discovery.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every goal and reason)
from backend.survival.curiosity import curiosity_state
from backend.survival.discovery import FAR_PATCHES, far_walked, pull
from backend.survival.goals import GOALS, adopt_goal, complete, is_open, progress_of
from backend.survival.memory import know, mark_explored, remember
from backend.survival.trips import REASONS
from backend.tests.test_survival_building import World
from backend.tests.test_survival_life_goals import built, one_sinkhole

TAIGA_EAST = lambda x, z, seed: "taiga" if x > 30 else "meadow"  # noqa: E731
DISCOVERY = ("new_land", "new_creature", "cave", "water", "far_hills")


def open_goals(s):
    return [name for name in DISCOVERY if is_open(s, GOALS[name])]


class DiscoveryGoalTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("backend.survival.discovery.biome_at", TAIGA_EAST),
                            ("backend.survival.curiosity.biome_at", TAIGA_EAST),
                            ("backend.survival.life_goals.region_openings", one_sinkhole),
                            ("backend.survival.life_goals.terrain_height", lambda x, z, seed: 3),
                            ("backend.survival.discovery.terrain_height", lambda x, z, seed: 1 if z > 40 else 3)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_they_open_once_mimo_has_a_home_and_repeat_once_reached(self):
        self.assertEqual(open_goals(World().situation()), [])  # no home yet
        world = built()
        know(world.db, "meadow", "biome", 0.0)
        self.assertEqual(open_goals(world.situation()), list(DISCOVERY))
        for name in DISCOVERY:
            know(world.db, name, "goal", 1.0)  # reached once
        self.assertEqual(open_goals(world.situation()), list(DISCOVERY))
        know(world.db, "taiga", "biome", 2.0)  # every land near seen now
        self.assertNotIn("new_land", open_goals(world.situation()))

    def test_their_pull_rises_with_curiosity_and_a_restless_pet_turns_to_them(self):
        world = built()
        for value, score in ((0.0, 30.0), (50.0, 65.0), (80.0, 186.0)):
            curiosity_state(world.state, 0.0)["value"] = value
            self.assertAlmostEqual(pull(world.situation()), score)

    def test_they_count_only_what_is_found_after_they_were_set(self):
        world = built()
        know(world.db, "meadow", "biome", 0.0)
        know(world.db, "forest", "biome", 5.0)  # before the goal
        adopt_goal(world.state, "new_land", "utility", "", 10.0)
        self.assertEqual(progress_of(world.situation(), GOALS["new_land"]), 0.0)
        know(world.db, "taiga", "biome", 20.0)
        self.assertTrue(complete(world.situation(), GOALS["new_land"]))
        adopt_goal(world.state, "cave", "utility", "", 30.0)
        remember(world.db, "cave", (40, 4, 0), 25.0, "sinkhole")
        self.assertEqual(progress_of(world.situation(), GOALS["cave"]), 0.0)
        remember(world.db, "water", (0, 2, 60), 31.0)
        adopt_goal(world.state, "water", "utility", "", 30.0)
        self.assertEqual(progress_of(world.situation(), GOALS["water"]), 1.0)

    def test_far_hills_count_new_patches_far_from_home(self):
        world = built()
        adopt_goal(world.state, "far_hills", "utility", "", 10.0)
        mark_explored(world.db, [(rx, 0) for rx in range(8, 8 + FAR_PATCHES)], 20.0)  # 64 blocks east and on
        mark_explored(world.db, [(1, 1), (2, 2)], 20.0)  # near home: not far
        self.assertEqual(far_walked(world.situation()), FAR_PATCHES)
        self.assertTrue(complete(world.situation(), GOALS["far_hills"]))

    def test_each_trip_goes_only_for_its_goal_where_its_find_is_likely(self):
        world = built()
        know(world.db, "meadow", "biome", 0.0)
        s = world.situation()
        self.assertEqual([REASONS[name].wanted(s) for name in DISCOVERY], [None] * 5)
        adopt_goal(world.state, "new_land", "utility", "", 10.0)
        s = world.situation()
        self.assertEqual(REASONS["new_land"].wanted(s), "I want to see land I have never seen")
        self.assertEqual((REASONS["new_land"].value(s, 40, 0), REASONS["new_land"].value(s, 0, 0)),
                         ((1.0, "the taiga, which it has never seen"), (0.0, "")))
        self.assertEqual(REASONS["cave"].value(s, 36, 4), (1.0, "a sinkhole"))
        self.assertEqual(REASONS["water"].value(s, 0, 50), (1.0, "a lake"))
        self.assertEqual(REASONS["far_hills"].value(s, 0, 0), (0.0, ""))  # home ground is not far
        world.state["brain"]["trip"] = {"reason": "new_land", "since": 15.0}
        self.assertIsNone(REASONS["new_land"].look(world.situation(), world.context()))
        know(world.db, "taiga", "biome", 16.0)
        self.assertEqual(REASONS["new_land"].look(world.situation(), world.context()).words, "the taiga")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_discovery.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.discovery'`

- [ ] **Step 3: The discovery goals**

Create `backend/survival/discovery.py`:

```python
"""Discovery goals (L4, the owner's "more curious"): something new to go and see is always on offer.

Once Mimo has a home of its own (after first_shelter), these goals are open whenever there is
something of their kind to find within DISCOVERY_REACH blocks of home. They repeat (goals.Goal
.repeat): each counts only what Mimo discovers after it was set, and is on offer again once
reached. Their rules score rises with curiosity (backend.survival.curiosity): 30 plus seven
tenths of it, and RESTLESS_PULL more once Mimo is restless, so a restless pet's dawn choice turns
from its routine to a discovery even past the current goal's lead.
- new_land, "See new lands": set foot in a biome it has never seen (memory_knowledge "biome").
- new_creature, "Meet a new creature": meet a kind of creature it has never met ("creature").
- cave, "Look into a cave": look into a cave mouth or sinkhole it has not seen (a "cave" landmark).
- water, "Follow the water": find a lake it does not know (a water place).
- far_hills, "Map the far hills": set foot on FAR_PATCHES patches of ground it never walked,
  farther than FAR_FROM blocks from home (needs a home it built, so go_home reaches it from there).

Each has a trip of its own (backend.survival.trips), wanted only while its goal is Mimo's goal,
reaching DISCOVERY_REACH blocks from home: "look for new land" (a biome it has never seen is
sure), "look for a creature it has never met" (a biome where one lives), "look into a cave" (the
cave mouths and sinkholes it has not looked into, as life_goals' iron trip looks into them),
"follow the water" (lake ground with no water it knows within 16 blocks) and "walk the far hills"
(new ground past FAR_FROM, hills first). A trip ends on the find its goal counts. The "wander"
trip (curiosity's) serves them all.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, biome_at, terrain_height
from backend.survival.creatures.kinds import land_kinds
from backend.survival.curiosity import RESTLESS, biome_words, meet_creatures, seen, value_of
from backend.survival.exploring import area_novelty
from backend.survival.foraging import fishing_spots
from backend.survival.goals import Goal, Milestone, register_goal
from backend.survival.life_goals import (
    HILLS, iron_look, looked_into, opening_spots, opening_words, openings_near, whole,
)
from backend.survival.memory import BUILT, PATCH, patch_of, remember
from backend.survival.situation import Situation
from backend.survival.steps import label
from backend.survival.trips import Find, Reason, register_reason

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

DISCOVERY_REACH = 90.0  # blocks from home the goals look and their trips go
SAMPLE_STEP = 16  # blocks between the columns sampled for biomes within reach
RESTLESS_PULL = 100.0
FAR_FROM = 48.0
FAR_PATCHES = 12
WATER_NEAR = 16.0
LAKE_SAMPLES = ((0, 0), (6, 0), (-6, 0), (0, 6), (0, -6))
GOAL_NAMES = ("new_land", "new_creature", "cave", "water", "far_hills")


def home_of(s: Situation) -> dict | None:
    return next((place for place in s.places if place["kind"] == "home"), None)


def built_home(s: Situation) -> bool:
    home = home_of(s)
    return home is not None and home["note"] == BUILT


def since(s: Situation, name: str) -> float | None:
    """When `name` became Mimo's goal, or None while it is not."""
    goal = s.brain.get("goal") or {}
    return goal.get("since") if goal.get("name") == name else None


def learned_since(s: Situation, fact: str, at: float | None) -> list[str]:
    if at is None or s.db is None:
        return []
    rows = s.db.execute("SELECT subject FROM memory_knowledge WHERE fact=? AND learned_at>=? ORDER BY learned_at",
                        (fact, at)).fetchall()
    return [row[0] for row in rows]


def found_since(s: Situation, kind: str, at: float | None) -> list[dict]:
    return [] if at is None else [place for place in s.places if place["kind"] == kind and place["found_at"] >= at]


def within_reach(s: Situation) -> list[tuple[int, int]]:
    """Columns every SAMPLE_STEP blocks within DISCOVERY_REACH of home (none without a home)."""
    def look() -> list[tuple[int, int]]:
        home = home_of(s)
        if home is None:
            return []
        reach = int(DISCOVERY_REACH)
        return [(home["x"] + dx, home["z"] + dz) for dx in range(-reach, reach + 1, SAMPLE_STEP)
                for dz in range(-reach, reach + 1, SAMPLE_STEP) if math.hypot(dx, dz) <= DISCOVERY_REACH]
    return s.sensed("discovery samples", look)


def biomes_in_reach(s: Situation) -> set[str]:
    return s.sensed("biomes in reach", lambda: {biome_at(x, z, s.seed) for x, z in within_reach(s)})


def pull(s: Situation) -> float:
    """A discovery goal's rules score: 30, seven tenths of curiosity, RESTLESS_PULL once restless."""
    curiosity = value_of(s.brain)
    return 30.0 + 0.7 * curiosity + (RESTLESS_PULL if curiosity >= RESTLESS else 0.0)


def goal_trip(name: str, why: str):
    """A trip wanted only while `name` is Mimo's goal."""
    def wanted(s: Situation) -> str | None:
        return why if since(s, name) is not None else None
    return wanted


def trip_found(s: Situation) -> float | None:
    return (s.brain.get("trip") or {}).get("since")


# new_land --------------------------------------------------------------------------------------

def unseen_biomes(s: Situation) -> set[str]:
    return biomes_in_reach(s) - seen(s, "biome")


register_goal(Goal(
    "new_land", "See new lands", "There is more to the world than home: land it has never seen lies near.",
    (Milestone("Set foot in a land it has never seen",
               lambda s: whole(bool(learned_since(s, "biome", since(s, "new_land")))), ("explore",)),),
    score=pull, thought="I wonder what the land looks like over there.", after=("first_shelter",),
    valid=lambda s: bool(unseen_biomes(s)), repeat=True))


def new_land_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    biome = biome_at(x, z, s.seed)
    return (1.0, f"{biome_words(biome)}, which it has never seen") if biome not in seen(s, "biome") else (0.0, "")


def new_land_look(s: Situation, context: ActionContext) -> Find | None:
    biomes = learned_since(s, "biome", trip_found(s))
    return Find(biome_words(biomes[-1]), True, new=False) if biomes else None


register_reason(Reason(
    "new_land", "look for new land", goal_trip("new_land", "I want to see land I have never seen"), new_land_value,
    lambda s: 50.0, goals=("new_land",), look=new_land_look, reach=DISCOVERY_REACH))


# new_creature ----------------------------------------------------------------------------------

def unmet(s: Situation, biome: str) -> list[str]:
    return [kind.name for kind in land_kinds(biome) if kind.name not in seen(s, "creature")]


register_goal(Goal(
    "new_creature", "Meet a new creature", "Other creatures live in other lands: meeting them is half the fun.",
    (Milestone("Meet a creature it has never met",
               lambda s: whole(bool(learned_since(s, "creature", since(s, "new_creature")))), ("explore",)),),
    score=pull, thought="Who else lives out there?", after=("first_shelter",),
    valid=lambda s: any(unmet(s, biome) for biome in biomes_in_reach(s)), repeat=True))


def new_creature_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    biome = biome_at(x, z, s.seed)
    kinds = unmet(s, biome)
    return (1.0, f"{biome_words(biome)}, where {label(kinds[0])}s live") if kinds else (0.0, "")


def new_creature_look(s: Situation, context: ActionContext) -> Find | None:
    meet_creatures(s.state, context, s.at)
    kinds = learned_since(s, "creature", trip_found(s))
    return Find(f"a {label(kinds[-1])}", True, new=False) if kinds else None


register_reason(Reason(
    "new_creature", "look for a creature it has never met",
    goal_trip("new_creature", "I want to meet a creature I have never met"), new_creature_value, lambda s: 50.0,
    goals=("new_creature",), look=new_creature_look, reach=DISCOVERY_REACH))


# cave ------------------------------------------------------------------------------------------

def unlooked_openings(s: Situation) -> list[tuple[str, int, int]]:
    home = home_of(s)
    if home is None:
        return []
    return [opening for opening in openings_near(s.seed, home["x"], home["z"], DISCOVERY_REACH)
            if not looked_into(s, opening[1], opening[2])]


register_goal(Goal(
    "cave", "Look into a cave", "Cave mouths and sinkholes lead under the world: what is down there?",
    (Milestone("Look into a cave mouth or sinkhole",
               lambda s: whole(bool(found_since(s, "cave", since(s, "cave")))), ("explore",)),),
    score=pull, thought="That dark hole in the hill... I have to see.", after=("first_shelter",),
    valid=lambda s: bool(unlooked_openings(s)), repeat=True))


def cave_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    for kind, ox, oz in openings_near(s.seed, x, z, 12):
        if not looked_into(s, ox, oz):
            return 1.0, opening_words(kind)
    return (0.3, "hills") if terrain_height(x, z, s.seed) >= HILLS else (0.0, "")


def cave_look(s: Situation, context: ActionContext) -> Find | None:
    find = iron_look(s, context)
    return None if find is None else Find(find.words, True, find.new)


register_reason(Reason(
    "cave", "look into a cave", goal_trip("cave", "I want to see what is under the world"), cave_value,
    lambda s: 50.0, goals=("cave",), spots=opening_spots, look=cave_look, reach=DISCOVERY_REACH))


# water -----------------------------------------------------------------------------------------

def lake_at(s: Situation, x: int, z: int) -> bool:
    return any(terrain_height(x + dx, z + dz, s.seed) < SEA_LEVEL for dx, dz in LAKE_SAMPLES)


def known_water(s: Situation, x: int, z: int) -> bool:
    return any(place["kind"] == "water" and math.hypot(place["x"] - x, place["z"] - z) <= WATER_NEAR
               for place in s.places)


register_goal(Goal(
    "water", "Follow the water", "Lakes and streams bring fish, reeds and new shores.",
    (Milestone("Find water it does not know",
               lambda s: whole(bool(found_since(s, "water", since(s, "water")))), ("explore",)),),
    score=pull, thought="I can hear water somewhere.", after=("first_shelter",),
    valid=lambda s: any(lake_at(s, x, z) and not known_water(s, x, z) for x, z in within_reach(s)), repeat=True))


def water_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    return (1.0, "a lake") if lake_at(s, x, z) and not known_water(s, x, z) else (0.0, "")


def water_look(s: Situation, context: ActionContext) -> Find | None:
    for stand, water in fishing_spots(s) or []:
        if not known_water(s, water[0], water[2]):
            return Find("water it did not know", True, remember(s.db, "water", water, s.at))
    return None


register_reason(Reason(
    "water", "follow the water", goal_trip("water", "I want to find water I do not know"), water_value,
    lambda s: 50.0, goals=("water",), look=water_look, reach=DISCOVERY_REACH))


# far_hills -------------------------------------------------------------------------------------

def far_walked(s: Situation) -> int:
    """Patches farther than FAR_FROM from home walked only since the goal was set."""
    at, home = since(s, "far_hills"), home_of(s)
    if at is None or home is None or s.db is None:
        return 0
    rows = s.db.execute("SELECT rx, rz FROM memory_explored WHERE visits=1 AND last_at>=?", (at,)).fetchall()
    return sum(1 for rx, rz in rows
               if math.hypot(rx * PATCH + PATCH / 2 - home["x"], rz * PATCH + PATCH / 2 - home["z"]) > FAR_FROM)


register_goal(Goal(
    "far_hills", "Map the far hills", "Past the land around home lie hills it has only seen from afar.",
    (Milestone(f"Walk {FAR_PATCHES} patches of far ground", lambda s: far_walked(s) / FAR_PATCHES, ("explore",)),),
    score=pull, thought="Those far hills are calling.", after=("first_shelter",), valid=built_home, repeat=True))


def far_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    home = home_of(s)
    if home is None or math.hypot(x - home["x"], z - home["z"]) <= FAR_FROM:
        return 0.0, ""
    new = area_novelty(s, patch_of(x, z)) / 9
    if new < 0.5:
        return 0.0, ""
    return (new, "far hills") if terrain_height(x, z, s.seed) >= HILLS else (new * 0.7, "far land")


register_reason(Reason(
    "far_hills", "walk the far hills", goal_trip("far_hills", "I want to see the land past the hills"), far_value,
    lambda s: 50.0, goals=("far_hills",), reach=DISCOVERY_REACH))
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival.curiosity import note_discoveries, tend_curiosity
```

with:

```python
from backend.survival import discovery  # noqa: F401  (L4's discovery goals)
from backend.survival.curiosity import note_discoveries, tend_curiosity
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_discovery.py"`
Expected: `Ran 5 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1021 tests` … `OK` (5 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/discovery.py backend/survival/brain.py backend/tests/test_survival_discovery.py
git commit -m "feat: discovery goals always on offer once home stands: new lands, new creatures, caves, water and the far hills" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 10: What the model and the viewer are told, and Jev's pick of the reason

**Files:**
- Modify: `backend/survival/goals.py` (append the views), `backend/survival/pickers.py` (the payload's `goal`, `explore_reasons`, `trip` and `curiosity`), `backend/survival/snapshot.py` (`goal`, `trip` and `curiosity` in the stream; `goals_reached` on lives), `backend/survival/models.py` (`jev_answers`: several questions in one call; `REASON_INSTRUCTIONS`), `backend/survival/choosing.py` (the `"explore_reason"` question)
- Modify tests: `backend/tests/test_survival_pickers.py` (the payload's keys)
- Test: `backend/tests/test_survival_goal_view.py`

**Interfaces:**
- Consumes: Tasks 1–9 (the goals' titles come from the registry: `snapshot.py` imports the brain, which imports every goal module); Task 4's `trips.reasons_payload`, `trip_view`, `target_words`, `best_trip`, `start_trip`, `Option.reasons`, `Choice.trip`, `trip_for`, and `test_survival_trips.flat_ground`, `only_reasons`, `test_reason`; Task 3's `test_survival_goal_choice.Recorder`; Task 8's `curiosity.curiosity_view`; `snapshot.brain_view`, `survival_view`, `life_detail`, `life_summary`; `clock.clock_at`.
- Produces:
  - `goals.goal_payload(s) -> dict | None`: `{"title", "why", "progress", "next_steps", "days_on_it"}`; `goal_view(brain) -> dict | None`: `{"name", "title", "why", "progress", "plan": [{"text", "done"}], "picker", "since"}`; `reached_rows(db) -> list[(name, at)]`.
  - `context_payload(s, events)["goal"]`, `["explore_reasons"]` (`[{"reason", "why", "directions": [{"direction", "blocks", "toward"}]}]`, from `trips.reasons_payload`) `["trip"]` (`trips.trip_view`) and `["curiosity"]` (`{"level", "feeling"}`); `/api/mimo`'s `goal` (null without one), `trip` (`{"reason", "words", "why", "direction", "found"}` while Mimo explores, else null) and `curiosity` (`{"level", "feeling"}`, null before its first tick); `snapshot.goals_reached(world, born_at, scale) -> list[{"name", "title", "day"}]`; `life_detail(...)["goals_reached"]` and `life_summary(...)["goals_reached"]` (`[]` for the legacy life).
  - `models.jev_answers(payload, {question: (choices, instructions)}, env, http) -> {question: choice}` (one call; a question answered badly raises `ModelError`); `ask_jev` asks its one question through it; `models.REASON_INSTRUCTIONS`.
  - `choosing.explore_option(ask)`, `reason_options(ask) -> list[Option]` (a reason's criteria read "Go and look for iron: my pickaxe needs it. Now: north 40 blocks, a cave mouth; …"), `trip_for(ask, purpose, reason=None)`: when Jev answers a purpose choice whose explore is offered for more than one reason, the same call asks `"explore_reason"` too, and a Jev pick of explore goes for Jev's reason (resolution 16).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_goal_view.py`:

```python
import hashlib
import os
import random
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api.lives import get_life, hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.choosing import Ask, decide
from backend.survival.goals import adopt_goal
from backend.survival.memory import know
from backend.survival.pickers import context_payload, options
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import ensure_brain
from backend.survival.trips import best_trip, start_trip
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_goal_choice import Recorder
from backend.tests.test_survival_goals import WOOD, goal_situation, only_goals
from backend.tests.test_survival_purposes import situation
from backend.tests.test_survival_trips import flat_ground, only_reasons, test_reason


class GoalPayloadTests(unittest.TestCase):
    def test_the_model_is_told_the_goal_its_progress_and_what_comes_next(self):
        with only_goals(WOOD):
            self.assertIsNone(context_payload(goal_situation(), [])["goal"])
            s = goal_situation("woodpile", inventory={"oak_log": 2})
            self.assertEqual(context_payload(s, [])["goal"], {
                "title": "A woodpile", "why": "Wood makes everything else.", "progress": 0.25,
                "next_steps": ["Carry 4 logs", "Make a pickaxe"], "days_on_it": 0})


class TripPayloadTests(unittest.TestCase):
    def setUp(self):
        flat_ground(self)

    def test_the_model_is_told_what_a_trip_would_look_for_where_and_why(self):
        with only_reasons(test_reason()):
            s = situation()
            payload = context_payload(s, [])
            self.assertIsNone(payload["trip"])
            [reason] = payload["explore_reasons"]
            self.assertEqual((reason["reason"], reason["why"], len(reason["directions"])), ("look for things", "I need them", 3))
            self.assertEqual(reason["directions"][0], {"direction": "east", "blocks": 64, "toward": "east land"})
            s.brain["purpose"] = "explore"
            start_trip(s.brain, best_trip(s), 5.0, "jev")
            self.assertEqual(context_payload(s, [])["trip"], {"reason": "things", "words": "look for things",
                                                               "why": "I need them", "direction": "east", "found": None})
            self.assertIsNone(payload["curiosity"])  # not tended yet
            s.brain["curiosity"] = {"value": 30.0, "new_at": None}
            self.assertEqual(context_payload(s, [])["curiosity"], {"level": 30, "feeling": "curious; nothing new yet"})

    def test_jev_picks_the_reason_in_the_same_call_as_the_purpose(self):
        with only_reasons(test_reason("wood", score=60.0), test_reason("iron", score=45.0)):
            s = situation()
            found = tuple(options(s))
        jev = Recorder({"answers": {"purpose": {"choice": "explore"}, "explore_reason": {"choice": "iron"}}})
        choice = decide(Ask(1, "jev", False, found, {}, 0.0), {"TYPESAFE_API_KEY": "k"}, jev, random.Random(1))
        self.assertEqual((choice.purpose, choice.picker, choice.trip.reason, choice.error), ("explore", "jev", "iron", None))
        self.assertEqual(choice.thought, "Heading east to look for iron. I need them.")
        [body] = jev.bodies
        asked = body["questions"]["explore_reason"]
        self.assertEqual(sorted(body["questions"]), ["explore_reason", "purpose"])
        self.assertRegex(asked["criteria"]["iron"], r"^Go and look for iron: I need them\. Now: east 64 blocks, east land; ")
        explore = tuple(option for option in found if option.name == "explore")
        rules = decide(Ask(2, "utility", False, explore, {}, 0.0), {}, jev, random.Random(1))
        self.assertEqual((rules.trip.reason, len(jev.bodies)), ("wood", 1))  # the rules' reason, and no call
        with only_reasons(test_reason("wood")):
            single = tuple(options(situation()))
        one = Recorder({"answers": {"purpose": {"choice": "explore"}}})
        self.assertEqual(decide(Ask(3, "jev", False, single, {}, 0.0), {"TYPESAFE_API_KEY": "k"}, one,
                                random.Random(1)).trip.reason, "wood")
        self.assertEqual(list(one.bodies[0]["questions"]), ["purpose"])  # one reason: nothing to ask


class GoalApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"),
                                           "MIMO_DB_PATH": str(root / "mimo.sqlite3"), "MIMO_TIME_SCALE": "1"})
        self.env.start()
        hatch_egg()
        registry = LifeRegistry()
        self.life = registry.active_life()
        self.world = SurvivalWorld(registry.world_path(self.life))

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_the_goal_and_its_day_plan_are_streamed_and_reading_them_writes_nothing(self):
        self.assertIsNone(get_mimo()["goal"])
        with self.world.transaction() as db:
            state = read_state(db)
            adopt_goal(state, "iron_tools", "jev", "I want iron tools.", 5.0)
            state["brain"]["goal"].update(progress=0.4, plan=[{"text": "Find iron ore", "done": True, "step": 2},
                                                              {"text": "Mine 3 iron ore", "done": False, "step": 3}])
            write_state(db, state)
        before = hashlib.sha256(self.world.path.read_bytes()).hexdigest()
        goal = get_mimo()["goal"]
        self.assertEqual(hashlib.sha256(self.world.path.read_bytes()).hexdigest(), before)
        self.assertEqual(goal, {"name": "iron_tools", "title": "Iron tools",
                                "why": "Stone only goes so far: an iron pickaxe digs anything and opens the way to "
                                       "better gear.",
                                "progress": 0.4, "picker": "jev", "since": 5.0,
                                "plan": [{"text": "Find iron ore", "done": True},
                                         {"text": "Mine 3 iron ore", "done": False}]})

    def test_curiosity_is_streamed_with_how_mimo_feels(self):
        self.assertIsNone(get_mimo()["curiosity"])  # not tended yet
        with self.world.transaction() as db:
            state = read_state(db)
            ensure_brain(state)["curiosity"] = {"value": 64.4, "at": 0.0, "new_at": None, "noticed_at": None,
                                                "seen": 0, "met_at": None}
            write_state(db, state)
        self.assertEqual(get_mimo()["curiosity"], {"level": 64, "feeling": "restless; nothing new yet"})

    def test_the_trip_is_streamed_while_mimo_explores(self):
        self.assertIsNone(get_mimo()["trip"])
        with self.world.transaction() as db:
            state = read_state(db)
            ensure_brain(state).update(purpose="explore", trip={"reason": "iron", "words": "look for iron",
                                                           "why": "my pickaxe needs it", "direction": "north",
                                                           "since": 1.0, "picker": "utility", "found": "a sinkhole",
                                                           "done": False})
            write_state(db, state)
        self.assertEqual(get_mimo()["trip"], {"reason": "iron", "words": "look for iron", "why": "my pickaxe needs it",
                                              "direction": "north", "found": "a sinkhole"})

    def test_the_memorial_lists_the_goals_reached_with_their_day(self):
        born = self.life["born_at"]
        with self.world.transaction() as db:
            know(db, "first_shelter", "goal", born + 100.0)
            know(db, "iron_tools", "goal", born + 3700.0)
            state = read_state(db)
            state.update(died_at=time.time(), cause="cold", status="dead")
            write_state(db, state)
        LifeRegistry().mark_dead(self.life["id"], time.time(), "cold")
        reached = [{"name": "first_shelter", "title": "A home of its own", "day": 1},
                   {"name": "iron_tools", "title": "Iron tools", "day": 2}]
        self.assertEqual(get_mimo()["last_life"]["goals_reached"], reached)
        self.assertEqual(get_life(self.life["id"])["goals_reached"], reached)
        self.assertEqual(get_life(1)["goals_reached"], [])  # the retired legacy life set none


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_pickers.py`, replace:

```python
                                        "threats", "defense"})
```

with:

```python
                                        "threats", "defense", "goal", "explore_reasons", "trip", "curiosity"})
        self.assertIsNone(payload["goal"])  # L4: no goal chosen yet
        self.assertIsNone(payload["trip"])  # L4: not exploring
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goal_view.py"`
Expected: `FAILED (failures=1, errors=6)`: `KeyError: 'goal'` and `KeyError: 'curiosity'` (neither the payload nor the stream has them yet), and `Tuples differ: ('explore', 'jev', 'wood', None) != ('explore', 'jev', 'iron', None)` (Jev is not asked for the reason yet, so the trip goes for the rules' pick)

- [ ] **Step 3: The goal and the trip for the model and the viewer**

The block starts with the two blank lines that separate it from the section before.

In `backend/survival/goals.py`, append:

```python


# What the model and the viewer are told ---------------------------------------------------------

def goal_payload(s: Situation) -> dict | None:
    """The goal for the model: its title, why, progress, next milestones and days on it; or None."""
    goal = active(s)
    if goal is None:
        return None
    since = s.brain["goal"]["since"]
    return {"title": goal.title, "why": goal.why, "progress": round(progress_of(s, goal), 2),
            "next_steps": [milestone.text for _, milestone in ahead(s, goal)[:PLAN_STEPS]],
            "days_on_it": math.floor(max(0.0, s.at - since) * s.scale / DAY_SECONDS)}


def goal_view(brain: dict | None) -> dict | None:
    """The goal for /api/mimo: name, title, why, progress (0 to 1), the day plan, who chose it and
    when; None without one."""
    current = (brain or {}).get("goal")
    if not current:
        return None
    goal = GOALS.get(current["name"])
    return {"name": current["name"], "title": goal.title if goal else current["name"].replace("_", " "),
            "why": goal.why if goal else "", "progress": round(float(current.get("progress") or 0.0), 2),
            "plan": [{"text": entry["text"], "done": bool(entry.get("done"))} for entry in current.get("plan") or []],
            "picker": current.get("picker"), "since": current.get("since")}


def reached_rows(db: sqlite3.Connection) -> list[tuple[str, float]]:
    """(goal, when) for every goal reached, first first. A world from before M3 reached none."""
    try:
        rows = db.execute("SELECT subject, learned_at FROM memory_knowledge WHERE fact=? ORDER BY learned_at, subject",
                          (REACHED,)).fetchall()
    except sqlite3.OperationalError as error:
        if "no such table" not in str(error):
            raise
        return []
    return [(row[0], row[1]) for row in rows]
```

In `backend/survival/pickers.py`, replace:

```python
(`steer`, with the rules in backend.survival.goals).
Explore's option carries its reasons to explore, the rules' pick first (backend.survival.trips).
"""
```

with:

```python
(`steer`, with the rules in backend.survival.goals), and the payload carries the goal.
Explore's option carries its reasons to explore, the rules' pick first (backend.survival.trips);
the payload says what a trip would look for and where, the trip Mimo is on, and how curious it is.
"""
```

and replace:

```python
from backend.survival.goals import active, boosted, meets_need, toward
```

with:

```python
from backend.survival.goals import active, boosted, goal_payload, meets_need, toward
```

and replace:

```python
from backend.survival.creatures.defense import threats_payload
```

with:

```python
from backend.survival.creatures.defense import threats_payload
from backend.survival.curiosity import curiosity_view
```

and replace:

```python
from backend.survival.trips import offers
```

with:

```python
from backend.survival.trips import offers, reasons_payload, trip_view
```

and replace:

```python
        # L2: the hostile creatures that could come after Mimo, and how it can meet them.
        **threats_payload(s),
```

with:

```python
        # L2: the hostile creatures that could come after Mimo, and how it can meet them.
        **threats_payload(s),
        # L4: the goal Mimo works toward, how far along it is and what comes next (or None).
        "goal": goal_payload(s),
        # L4: what an explore trip would go looking for, why, and which ways it could head (with what
        # lies there); and the trip Mimo is on, if it is exploring.
        "explore_reasons": reasons_payload(s),
        "trip": trip_view(s.brain),
        # L4: how curious Mimo is and how it feels about it ("restless; nothing new for 2 game days").
        "curiosity": curiosity_view(s.brain, s.at, s.scale),
```

In `backend/survival/snapshot.py`, replace:

```python
import sqlite3

from backend.services.block_table import blocks_seq
```

with:

```python
import sqlite3

import backend.survival.brain  # noqa: F401  (L4: every goal registered, for its title)
from backend.services.block_table import blocks_seq
```

and replace:

```python
from backend.survival.creatures.view import creatures_view
```

with:

```python
from backend.survival.creatures.view import creatures_view
from backend.survival.curiosity import curiosity_view
from backend.survival.goals import GOALS, goal_view, reached_rows
```

and replace:

```python
from backend.survival.registry import LifeRegistry
```

with:

```python
from backend.survival.registry import LifeRegistry
from backend.survival.trips import trip_view
```

and replace:

```python
    """What Mimo is up to: its purpose, a running reflex, who chose, and whether it is choosing.
    A world whose brain has not started yet is about to choose."""
    if brain is None:
        return {"purpose": None, "reflex": None, "picker": None, "choosing": True}
    return {"purpose": brain.get("purpose"), "reflex": brain.get("reflex"), "picker": brain.get("picker"),
            "choosing": brain.get("pending") is not None}
```

with:

```python
    """What Mimo is up to: its purpose, a running reflex, who chose, and whether it is choosing;
    (L4) its goal with the day plan, and while it explores, what for. A world whose brain has not
    started yet is about to choose."""
    if brain is None:
        return {"purpose": None, "reflex": None, "picker": None, "choosing": True, "goal": None, "trip": None}
    return {"purpose": brain.get("purpose"), "reflex": brain.get("reflex"), "picker": brain.get("picker"),
            "choosing": brain.get("pending") is not None, "goal": goal_view(brain), "trip": trip_view(brain)}
```

and replace:

```python
        "sheltered": indoors,
        **brain_view(state.get("brain")),
    }
```

with:

```python
        "sheltered": indoors,
        **brain_view(state.get("brain")),
        # L4: how curious Mimo is, and how it feels ({"level", "feeling"}; null before it is tended).
        "curiosity": curiosity_view(state.get("brain"), at, scale),
    }
```

and replace:

```python
def life_detail(registry: LifeRegistry, life: dict, scale: float, now: float) -> dict:
    """One life's row, notable events and final state (the legacy snapshot shape for life 1)."""
    archive = open_archive(registry, life)
    if isinstance(archive, MimoStore):
        state = archive.snapshot()
        events = notable(state["events"])
    else:
        state = survival_view(archive, now, scale)
        events = archive.notable_events(NOTABLE_LIMIT)
    return {"life": life_row(life, scale, now), "notable_events": events, "state": state}
```

with:

```python
def goals_reached(world: SurvivalWorld, born_at: float, scale: float) -> list[dict]:
    """L4: the goals a survival life reached, first first, as {name, title, day}."""
    with world.connect() as db:
        rows = reached_rows(db)
    return [{"name": name, "title": GOALS[name].title if name in GOALS else name.replace("_", " "),
             "day": clock_at(born_at, at, scale)["day_number"]} for name, at in rows]


def life_detail(registry: LifeRegistry, life: dict, scale: float, now: float) -> dict:
    """One life's row, notable events and final state (the legacy snapshot shape for life 1), and
    (L4) the goals it reached (none for the legacy life)."""
    archive = open_archive(registry, life)
    if isinstance(archive, MimoStore):
        state = archive.snapshot()
        events = notable(state["events"])
        goals = []
    else:
        state = survival_view(archive, now, scale)
        events = archive.notable_events(NOTABLE_LIMIT)
        goals = goals_reached(archive, life["born_at"], scale)
    return {"life": life_row(life, scale, now), "notable_events": events, "state": state, "goals_reached": goals}
```

and replace:

```python
    return {**detail["life"], "notable_events": detail["notable_events"]}
```

with:

```python
    return {**detail["life"], "notable_events": detail["notable_events"], "goals_reached": detail["goals_reached"]}
```

- [ ] **Step 4: Jev picks the reason in the same call**

In `backend/survival/models.py`, replace:

```python
GOAL_INSTRUCTIONS (backend.survival.choosing.prepare_goal).
"""
```

with:

```python
GOAL_INSTRUCTIONS (backend.survival.choosing.prepare_goal); and when explore is offered for more
than one reason, the purpose call asks a second question, "explore_reason", in the same call
(`jev_answers`, REASON_INSTRUCTIONS).
"""
```

and replace:

```python
                     "traits, the dangers near it and what it lacks. Choose only from the offered goals.")
```

with:

```python
                     "traits, the dangers near it and what it lacks. Choose only from the offered goals.")
# L4: why an explore trip goes, when there is more than one reason.
REASON_INSTRUCTIONS = ("If this small survival pet explores, choose what it goes looking for: what its goal needs "
                       "or what it lacks most. Choose only from the offered reasons.")
```

Then replace the whole `ask_jev` function with:

```python
def jev_answers(payload: dict, questions: dict[str, tuple[list[Option], str]], env: Env,
                http: Http = post_json) -> dict[str, str]:
    """Jev's choice for each question, {name: (choices, instructions)}, asked in one call."""
    asked = {name: {"type": "choice", "instructions": instructions, "criteria": criteria(choices)}
             for name, (choices, instructions) in questions.items()}
    body = {"model": env.get("TYPESAFE_MODEL") or "jev-latest", "state": payload, "questions": asked}
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "curl/8.7.1",
               "Authorization": f"Bearer {env.get('TYPESAFE_API_KEY', '')}"}
    answer = http(env.get("TYPESAFE_API_URL") or DEFAULT_JEV_URL, headers, body, JEV_TIMEOUT)
    chosen = {}
    for name, (choices, _) in questions.items():
        try:
            choice = answer["answers"][name]["choice"]
        except (KeyError, TypeError) as error:
            raise ModelError(f"Jev answered without a choice ({error!r})") from error
        if choice not in {option.name for option in choices}:
            raise ModelError(f"Jev chose {choice!r}, which was not offered")
        chosen[name] = choice
    return chosen


def ask_jev(payload: dict, choices: list[Option], env: Env, http: Http = post_json, question: str = "purpose",
            instructions: str = INSTRUCTIONS) -> str:
    """Jev's choice among `choices`: a purpose, or (L4, question "goal") a goal."""
    return jev_answers(payload, {question: (choices, instructions)}, env, http)[question]
```

In `backend/survival/choosing.py`, replace:

```python
offer, the rules' pick first, and choosing explore goes for that one: the trip is stored in the
brain, and its event and thought say what for ("Pip decided to explore to look for iron, toward
iron tools. \"Heading north to look for iron. My pickaxe needs it.\"").
```

with:

```python
offer, the rules' pick first. When Jev answers and explore is offered for more than one reason,
the same call asks a second question, "explore_reason", and a Jev pick of explore goes for the
reason Jev chose; otherwise (the rules, Luna) it goes for the rules' pick. Choosing explore
stores the trip in the brain, and its event and thought say what for ("Pip decided to explore to
look for iron, toward iron tools. \"Heading north to look for iron. My pickaxe needs it.\"").
```

and replace:

```python
    GOAL_INSTRUCTIONS, JEV_TIMEOUT, LUNA_TIMEOUT, Http, ModelError, ask_jev, ask_luna, jev_configured,
    luna_configured, luna_reflect, post_json,
```

with:

```python
    GOAL_INSTRUCTIONS, INSTRUCTIONS, JEV_TIMEOUT, LUNA_TIMEOUT, REASON_INSTRUCTIONS, Http, ModelError, ask_jev,
    ask_luna, jev_answers, jev_configured, luna_configured, luna_reflect, post_json,
```

and replace:

```python
from backend.survival.trips import Offer, start_trip, trip_thought
```

with:

```python
from backend.survival.trips import Offer, start_trip, target_words, trip_thought
```

and replace:

```python
    purpose, picker = None, "utility"
```

with:

```python
    purpose, picker, reason = None, "utility", None
    reasons = reason_options(ask)
```

and replace:

```python
                purpose = ask_jev(ask.payload, choices, env, http, question="goal", instructions=GOAL_INSTRUCTIONS)
            else:
```

with:

```python
                purpose = ask_jev(ask.payload, choices, env, http, question="goal", instructions=GOAL_INSTRUCTIONS)
            elif ask.route == "jev" and len(reasons) > 1:
                answers = jev_answers(ask.payload, {"purpose": (choices, INSTRUCTIONS),
                                                    "explore_reason": (reasons, REASON_INSTRUCTIONS)}, env, http)
                purpose, reason = answers["purpose"], answers["explore_reason"]
            else:
```

and replace:

```python
    trip = trip_for(ask, purpose)
```

with:

```python
    trip = trip_for(ask, purpose, reason)
```

Then replace the whole `trip_for` function with:

```python
def explore_option(ask: Ask) -> Option | None:
    return next((option for option in ask.options if option.name == "explore"), None) if ask.kind == "purpose" else None


def reason_options(ask: Ask) -> list[Option]:
    """L4: explore's reasons as choices for Jev's "explore_reason" question, with why and where."""
    option = explore_option(ask)
    return [Option(offer.reason, offer.words, f"Go and {offer.words}: {offer.why}.",
                   "; ".join(target_words(target) for target in offer.targets), offer.score)
            for offer in (option.reasons if option is not None else ())]


def trip_for(ask: Ask, purpose: str, reason: str | None = None) -> Offer | None:
    """L4: the reason an explore choice goes with: Jev's pick when it made one, else the rules' (the
    first offered)."""
    option = explore_option(ask)
    if purpose != "explore" or option is None or not option.reasons:
        return None
    return next((offer for offer in option.reasons if offer.reason == reason), option.reasons[0])
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goal_view.py"`
Expected: `Ran 7 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1028 tests` … `OK` (7 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 2 tests` … `OK` (the fake Jev answers the reason question too: it answers every question it is asked, Task 3)

- [ ] **Step 6: Commit**

```bash
git add backend/survival/goals.py backend/survival/pickers.py backend/survival/snapshot.py backend/survival/models.py backend/survival/choosing.py backend/tests/test_survival_goal_view.py backend/tests/test_survival_pickers.py
git commit -m "feat: the goal, the trip and curiosity in the model payload and in /api/mimo, Jev's pick of an explore reason, and the goals a life reached on its memorial" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 11: Fewer aimless loops, no trip without a reason, a discovery every day, less rest: the headless checks

The owner's words: "ideally though I want the actions of the pet to be purposeful", and "even exploring should be purposeful though". Before L4, Mimo picked a purpose moment to moment and, whenever nothing else was on offer, rested or explored the least-seen ground: rest, explore, rest. This task measures that on the headless runs and holds L4 to it (resolution 14). An aimless change is a change of purpose to rest or explore that works toward no goal: its event reads "decided to rest." or "decided to explore to …" without ", toward" (a change toward a goal reads "decided to explore to map the land, toward map the land."); an explore for a need but toward no goal still counts, so the measure stays the one taken before L4. Per game hour, over every seed and both pickers, before L4 (measured on `bd765f2` with this very test's runs): 4.5, and 4.56 in slow mode. With Tasks 1–10: 0.0, and 0.81 in slow mode. The check asks for at most three quarters of the old rate. The third check (the owner's "more curious"): once home stands, every game day of the runs brings at least one discovery (a new patch of ground, biome, kind of block or creature, or place: curiosity counts them, Task 8). The second check counts explores without a reason, which must be none: a change to explore whose event does not say what for, and a tick that ends with an explore step under way while the brain holds no trip reason. Before Task 4 every explore was such a one (10 changes to explore over the fast runs, 36 over the slow ones, at `bd765f2`). The fourth check (the controller's measure after the L3 review: rest and sleep took 70–80 % of the ticks): once home stands, Mimo rests or sleeps at most half the time, over every seed and both pickers (resolution 22). Measured on `bd765f2` with the same runs: 60 %, and 72 % in slow mode; with Tasks 1–10: 44 %, and 46 %. The night alone is a third of a game day. Changes of purpose as a whole rise, since goals fill the day with work and trips end early on a find (resolution 13); the flood guard from Task 5 still holds the changes toward no goal to the old caps.

**Files:**
- Modify tests: `backend/tests/test_survival_sim.py` (each run is made once and shared; the aimless check; the reason check; the discovery check; the rest check)

**Interfaces:**
- Consumes: Tasks 1–10 (every goal and every trip; Task 8's `state["brain"]["curiosity"]["seen"]`); the headless runs' `run_life`, `SEEDS`, `SLOW`, `HOUR`; Task 5's `"free"` list and `ALL_EVENTS_PER_HOUR`; Task 4's `state["brain"]["trip"]` and the explore event's "decided to explore to …".
- Produces: `run_life(seed, jev)` is cached (`functools.lru_cache`; call it with `jev=` as the tests do) and returns `"aimless"` (the game times of aimless changes), `"unreasoned"` (the texts of explore changes that do not say what for), `"unreasoned_walks"` (ticks that ended with an explore step under way and no trip reason), `"dull_days"` (the game days from the one home first stood in that brought no discovery), `"resting"` and `"lived"` (the ticks, once home stands, Mimo spent resting or asleep, and all of them) and `"hours"` (the game hours the run lasted); `aimless(text)`, `unreasoned(text)`, `dull_days(home_at, discoveries, end)`; `AIMLESS_BEFORE_GOALS`, `AIMLESS_SHARE = 0.75`, `AIMLESS`, `REST_AT_MOST = 0.5`, after Task 5's `ALL_EVENTS_PER_HOUR`.

- [ ] **Step 1: Write the checks**

In `backend/tests/test_survival_sim.py`, replace:

```python
Set MIMO_SLOW_TESTS=1 for longer runs on more seeds.
"""

import logging
```

with:

```python
Set MIMO_SLOW_TESTS=1 for longer runs on more seeds. L4: each run is made once and shared by the
tests, which also check that goals leave fewer aimless changes of purpose than before them, that
every explore goes for a reason, and that once home stands every game day brings a discovery and
Mimo rests or sleeps at most half the time.
"""

import functools
import logging
```

and replace:

```python
ALL_EVENTS_PER_HOUR = 90
```

with:

```python
ALL_EVENTS_PER_HOUR = 90
# L4: changes of purpose to rest or explore that work toward no goal, per game hour, over every
# seed and both pickers, measured on these runs before L4 (bd765f2): 4.5 (4.56 in slow mode).
# With goals they must fall by at least a quarter; measured with L4, 0.0 (0.81 in slow mode).
# An explore says what it goes for ("decided to explore to look for trees."), and one that serves no
# goal still counts here.
AIMLESS_BEFORE_GOALS = 4.56 if SLOW else 4.5
AIMLESS_SHARE = 0.75
AIMLESS = (" decided to rest.", " decided to explore")  # a change toward a goal says ", toward ..."
# L4: once home stands, the share of ticks Mimo spends resting or asleep (its purpose rest or sleep,
# or asleep), over every seed and both pickers: 70-80 % before L4 (the controller's measure), and
# the night alone is a third of a game day.
REST_AT_MOST = 0.5
```

and replace:

```python
def sample(world: SurvivalWorld) -> tuple[bool, bool | None]:
```

with:

```python
def aimless(text: str) -> bool:
    """L4: a change of purpose to rest or explore that works toward no goal."""
    return any(words in text for words in AIMLESS) and ", toward " not in text


def unreasoned(text: str) -> bool:
    """L4: a change of purpose to explore that does not say what for ("decided to explore to ...")."""
    return " decided to explore" in text and " decided to explore to " not in text


def dull_days(home_at: float | None, discoveries: list[float], end: float) -> list[int]:
    """L4: the game days, from the one home first stood in on, that brought no discovery."""
    if home_at is None:
        return []
    return [day for day in range(int(home_at // DAY), int(end // DAY) + (end % DAY > 0))
            if not any(max(home_at, day * DAY) <= at < (day + 1) * DAY for at in discoveries)]


def sample(world: SurvivalWorld) -> tuple[bool, bool | None]:
```

and replace:

```python
def run_life(seed: int, jev: bool) -> dict:
```

with:

```python
@functools.lru_cache(maxsize=None)
def run_life(seed: int, jev: bool) -> dict:
    """One headless run, made once per seed and picker and shared by the tests (call it with jev=...)."""
```

and replace:

```python
            t, trapped_since, trapped_longest, homes = 0.0, None, 0.0, []
```

with:

```python
            t, trapped_since, trapped_longest, homes, unreasoned_walks = 0.0, None, 0.0, [], 0
            home_at, seen, discoveries, resting, lived = None, 0, [], 0, 0
```

and replace:

```python
                if state is None or state["died_at"] is not None:
                    break
```

with:

```python
                if state is None or state["died_at"] is not None:
                    break
                action = state.get("action") or {}
                if action.get("purpose") == "explore" and not (state["brain"].get("trip") or {}).get("reason"):
                    unreasoned_walks += 1  # L4: an explore step under way with no reason in the brain
                if home_at is not None:
                    lived += 1
                    resting += state["brain"].get("purpose") in ("rest", "sleep") or action.get("kind") == "sleep"
                count = (state["brain"].get("curiosity") or {}).get("seen", 0)
                if count > seen:
                    seen = count
                    discoveries.append(t)  # L4: a discovery (curiosity counts them)
```

and replace:

```python
                    if home is not None:
                        homes.append(home)
```

with:

```python
                    if home is not None:
                        homes.append(home)
                        home_at = t if home_at is None else home_at
```

and replace:

```python
                    "free": [event["at"] - BORN for event in purposes if ", toward " not in event["text"]],
```

with:

```python
                    "free": [event["at"] - BORN for event in purposes if ", toward " not in event["text"]],
                    "aimless": [event["at"] - BORN for event in purposes if aimless(event["text"])],
                    "unreasoned": [event["text"] for event in purposes if unreasoned(event["text"])],
                    "unreasoned_walks": unreasoned_walks,
                    "dull_days": dull_days(home_at, discoveries, t),
                    "resting": resting, "lived": lived,
                    "hours": t / HOUR,
```

and replace:

```python
                self.assertLessEqual(most_in_an_hour(run["calls"]), cap({}, JEV_HOUR_CAP))
```

with:

```python
                self.assertLessEqual(most_in_an_hour(run["calls"]), cap({}, JEV_HOUR_CAP))

    def test_goals_leave_fewer_aimless_rests_and_explores_than_before_them(self):
        runs = [run_life(seed, jev=jev) for seed in SEEDS for jev in (False, True)]
        per_hour = sum(len(run["aimless"]) for run in runs) / sum(run["hours"] for run in runs)
        self.assertLessEqual(per_hour, AIMLESS_SHARE * AIMLESS_BEFORE_GOALS)

    def test_once_home_stands_every_game_day_brings_a_discovery(self):
        runs = [run_life(seed, jev=jev) for seed in SEEDS for jev in (False, True)]
        self.assertEqual([run["dull_days"] for run in runs], [[]] * len(runs))

    def test_once_home_stands_mimo_rests_and_sleeps_at_most_half_the_time(self):
        runs = [run_life(seed, jev=jev) for seed in SEEDS for jev in (False, True)]
        share = sum(run["resting"] for run in runs) / sum(run["lived"] for run in runs)
        self.assertLessEqual(share, REST_AT_MOST)

    def test_every_explore_goes_for_a_reason(self):
        runs = [run_life(seed, jev=jev) for seed in SEEDS for jev in (False, True)]
        self.assertEqual([text for run in runs for text in run["unreasoned"]], [])
        self.assertEqual(sum(run["unreasoned_walks"] for run in runs), 0)
```

- [ ] **Step 2: Run the checks**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_sim.py" -v`
Expected: `Ran 6 tests` … `OK`, the new `test_goals_leave_fewer_aimless_rests_and_explores_than_before_them`, `test_every_explore_goes_for_a_reason`, `test_once_home_stands_every_game_day_brings_a_discovery` and `test_once_home_stands_mimo_rests_and_sleeps_at_most_half_the_time` among them.

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 6 tests` … `OK`

To see that the checks would catch aimless loops and reasonless trips, set `AIMLESS_SHARE = 0.2` and run the first command again: the aimless test fails (`… not less than or equal to …`); set it back to 0.75. Then, in `backend/survival/choosing.py`'s `store_choice`, comment out the two lines that add ` to <words>` to explore's phrase and run it again: the reason test fails, listing explore events; restore them.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1032 tests` … `OK` (4 new).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_survival_sim.py
git commit -m "test: goals leave fewer aimless rests and explores than before them, no explore goes without a reason, every day brings a discovery and rest takes at most half the time, over the headless runs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 12: Viewer: the goal line, the day plan, the trip, curiosity and the goals reached

**Files:**
- Create: `frontend/src/survival/goals.ts`
- Modify: `frontend/src/survival/types.ts` (`goal`, `trip`, `curiosity`, `goals_reached`, `Goal`, `PlanStep`, `Trip`, `Curiosity`, `GoalReached`), `frontend/src/survival/hud.ts` (words for `improve_home` and `stock_larder`), `frontend/src/survival/SurvivalHud.tsx` (the goal line, its progress bar and today's plan; what an explore trip is for; the curiosity bar), `frontend/src/survival/Memorial.tsx` (the goals reached)
- Test: `frontend/src/survival/goals.test.ts`

**Interfaces:**
- Consumes: Task 10's `/api/mimo` `goal` (`{name, title, why, progress, plan: [{text, done}], picker, since}` or null) `trip` (`{reason, words, why, direction, found}` or null) and `curiosity` (`{level, feeling}` or null), and `goals_reached` on life summaries and details (`[{name, title, day}]`); `hud.purposeText`.
- Produces:
  - Types `PlanStep`, `Goal`, `Trip`, `Curiosity`, `GoalReached`; `SurvivalState.goal?: Goal | null`, `SurvivalState.trip?: Trip | null`, `SurvivalState.curiosity?: Curiosity | null`; `LifeSummary.goals_reached?` and `LifeDetail.goals_reached?: GoalReached[]`.
  - `goals.PLAN_SHOWN = 4` (three milestones and the time set aside to wander); `goalLine(goal) -> {label, percent} | null` ("Goal: Iron tools", 0..100); `goalHint(goal) -> string | undefined` (the why, and "Jev chose it." or "The rules chose it."); `planSteps(goal) -> PlanStep[]` (at most 3); `otherEvents(events) -> MimoEvent[]` (all but the `goal` events); `reachedLine(goal) -> string` ("A home of its own · day 2"); `tripLines(trip) -> {label, detail} | null` ("Exploring to look for iron", then "Heading north: my pickaxe needs it" or "Found a cave mouth"); `curiosityBar(curiosity) -> {percent, hint} | null`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/goals.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { curiosityBar, goalHint, goalLine, otherEvents, planSteps, reachedLine, tripLines } from './goals'
import { purposeText } from './hud'
import type { Goal, Trip } from './types'

const goal: Goal = {
  name: 'iron_tools', title: 'Iron tools', why: 'Stone only goes so far.', progress: 0.404, picker: 'jev', since: 10,
  plan: [
    { text: 'Find iron ore', done: true }, { text: 'Mine 3 iron ore', done: false },
    { text: 'Make an iron pickaxe', done: false }, { text: 'Take time to wander and see something new', done: false },
    { text: 'A fifth step', done: false },
  ],
}

describe('the goal line', () => {
  it('names the goal and its progress in whole percent', () => {
    expect(goalLine(goal)).toEqual({ label: 'Goal: Iron tools', percent: 40 })
    expect(goalLine({ ...goal, progress: 1.3 })?.percent).toBe(100)
    expect(goalLine({ ...goal, progress: -0.2 })?.percent).toBe(0)
  })

  it('is left out without a goal, or with an API from before goals', () => {
    expect(goalLine(null)).toBeNull()
    expect(goalLine(undefined)).toBeNull()
    expect(planSteps(undefined)).toEqual([])
    expect(goalHint(null)).toBeUndefined()
  })

  it('says why and who chose it', () => {
    expect(goalHint(goal)).toBe('Stone only goes so far. Jev chose it.')
    expect(goalHint({ ...goal, picker: 'utility' })).toBe('Stone only goes so far. The rules chose it.')
  })

  it("shows the first four steps of today's plan, the time to wander among them", () => {
    expect(planSteps(goal).map((step) => step.text))
      .toEqual(['Find iron ore', 'Mine 3 iron ore', 'Make an iron pickaxe', 'Take time to wander and see something new'])
  })

  it('names the purposes goals add', () => {
    expect(purposeText({ purpose: 'improve_home', reflex: null, choosing: false })).toBe('Building a bigger home')
    expect(purposeText({ purpose: 'stock_larder', reflex: null, choosing: false })).toBe('Stocking the larder')
  })
})

describe('goals reached', () => {
  it('lists each with the day it was reached', () => {
    expect(reachedLine({ name: 'first_shelter', title: 'A home of its own', day: 2 })).toBe('A home of its own · day 2')
  })

  it('leaves the goal events out of the notable ones, since the goals have a list of their own', () => {
    const events = [
      { id: 3, at: 30, kind: 'death', text: 'Pip died of the cold on day 4.' },
      { id: 2, at: 20, kind: 'goal', text: 'Pip reached a goal: iron tools.' },
      { id: 1, at: 10, kind: 'built', text: "Pip finished building Pip's Snug Cabin and moved in." },
    ]
    expect(otherEvents(events).map((event) => event.id)).toEqual([3, 1])
  })
})

describe('the explore trip', () => {
  const trip: Trip = { reason: 'iron', words: 'look for iron', why: 'my pickaxe needs it', direction: 'north', found: null }

  it('says what Mimo looks for, which way and why', () => {
    expect(tripLines(trip)).toEqual({ label: 'Exploring to look for iron', detail: 'Heading north: my pickaxe needs it' })
  })

  it('says what it found', () => {
    expect(tripLines({ ...trip, found: 'a cave mouth' })?.detail).toBe('Found a cave mouth')
  })

  it('is left out when Mimo is not exploring, or with an API from before trips', () => {
    expect(tripLines(null)).toBeNull()
    expect(tripLines(undefined)).toBeNull()
  })
})

describe('the curiosity bar', () => {
  it('shows the level in whole percent and how Mimo feels', () => {
    expect(curiosityBar({ level: 72.6, feeling: 'restless; nothing new for 2 game days' }))
      .toEqual({ percent: 73, hint: 'Restless; nothing new for 2 game days' })
    expect(curiosityBar({ level: 130, feeling: 'very restless; nothing new yet' })?.percent).toBe(100)
  })

  it('is left out before curiosity is tended, or with an API from before it', () => {
    expect(curiosityBar(null)).toBeNull()
    expect(curiosityBar(undefined)).toBeNull()
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/goals.test.ts`
Expected: FAIL: `Error: Cannot find module './goals'`

- [ ] **Step 3: The goal in the viewer's words**

In `frontend/src/survival/types.ts`, replace:

```typescript
export interface LifeSummary extends LifeRow {
  notable_events: MimoEvent[]
}
```

with:

```typescript
export interface LifeSummary extends LifeRow {
  notable_events: MimoEvent[]
  /** L4: the goals the life reached, first first (an older API sends none). */
  goals_reached?: GoalReached[]
}

/** One step of the day plan toward the goal (L4). */
export interface PlanStep {
  text: string
  done: boolean
}

/** The goal Mimo works toward for days (backend/survival/goals.py goal_view). */
export interface Goal {
  name: string
  title: string
  /** Why Mimo wants it, in one sentence. */
  why: string
  /** How far along it is, 0..1. */
  progress: number
  /** The next steps toward it, written at dawn and when the goal is chosen. */
  plan: PlanStep[]
  /** Who chose it: Jev, or the rules ("utility"). */
  picker: PickerName | null
  /** Server time it was chosen. */
  since: number
}

/** Why Mimo is exploring (L4, backend/survival/trips.py trip_view): every trip has a reason. */
export interface Trip {
  /** The reason's name, like "iron". */
  reason: string
  /** What it looks for, like "look for iron". */
  words: string
  /** Why, like "my pickaxe needs it". */
  why: string
  /** The way it is heading, like "north". */
  direction: string
  /** What it found on the way, if anything. */
  found: string | null
}

/** How curious Mimo is (L4, backend/survival/curiosity.py curiosity_view). */
export interface Curiosity {
  /** 0..100: it grows on known ground and falls with each discovery. */
  level: number
  /** How it feels, like "restless; nothing new for 2 game days". */
  feeling: string
}

/** A goal a life reached, and the game day it did. */
export interface GoalReached {
  name: string
  title: string
  day: number
}
```

and replace:

```typescript
  /** True while Mimo waits for its next choice. */
  choosing: boolean
}
```

with:

```typescript
  /** True while Mimo waits for its next choice. */
  choosing: boolean
  /** L4: the goal Mimo works toward for days, with today's plan; null without one (an older API sends none). */
  goal?: Goal | null
  /** L4: while Mimo explores, what for; null otherwise (an older API sends none). */
  trip?: Trip | null
  /** L4: how curious Mimo is and how it feels; null before its first tick (an older API sends none). */
  curiosity?: Curiosity | null
}
```

and replace:

```typescript
  notable_events: MimoEvent[]
  state: LegacyState | SurvivalState
}
```

with:

```typescript
  notable_events: MimoEvent[]
  state: LegacyState | SurvivalState
  /** L4: the goals the life reached (none for the legacy life; an older API sends none). */
  goals_reached?: GoalReached[]
}
```

Create `frontend/src/survival/goals.ts`:

```typescript
import type { Curiosity, Goal, GoalReached, MimoEvent, PlanStep, Trip } from './types'

/** How many steps of the day plan the HUD shows: three milestones and the time set aside to wander. */
export const PLAN_SHOWN = 4

/** The HUD's goal line (L4): "Goal: Iron tools" and its progress in whole percent, or null without a goal. */
export function goalLine(goal: Goal | null | undefined): { label: string; percent: number } | null {
  if (!goal) return null
  return { label: `Goal: ${goal.title}`, percent: Math.round(Math.min(1, Math.max(0, goal.progress)) * 100) }
}

/** Why Mimo wants the goal and who chose it, for the goal line's tooltip; undefined without a goal. */
export function goalHint(goal: Goal | null | undefined): string | undefined {
  if (!goal) return undefined
  const chooser = goal.picker === 'jev' ? ' Jev chose it.' : goal.picker === 'utility' ? ' The rules chose it.' : ''
  return `${goal.why}${chooser}`
}

/** Today's plan toward the goal: the first PLAN_SHOWN steps, as the server wrote them at dawn. */
export function planSteps(goal: Goal | null | undefined): PlanStep[] {
  return (goal?.plan ?? []).slice(0, PLAN_SHOWN)
}

/** The memorial's notable events but the goals reached, which it lists on their own. */
export function otherEvents(events: readonly MimoEvent[]): MimoEvent[] {
  return events.filter((event) => event.kind !== 'goal')
}

/** One goal a life reached, for the memorial: "A home of its own · day 2". */
export function reachedLine(goal: GoalReached): string {
  return `${goal.title} · day ${goal.day}`
}

/**
 * The HUD's lines for an explore trip (L4): what Mimo went looking for ("Exploring to look for iron"),
 * then which way and why ("Heading north: my pickaxe needs it"), or what it found. Null when it is not exploring.
 */
export function tripLines(trip: Trip | null | undefined): { label: string; detail: string } | null {
  if (!trip) return null
  const detail = trip.found ? `Found ${trip.found}` : `Heading ${trip.direction}: ${trip.why}`
  return { label: `Exploring to ${trip.words}`, detail }
}

/** The curiosity bar beside the vitals (L4): its level in whole percent, and how Mimo feels as the tooltip. */
export function curiosityBar(curiosity: Curiosity | null | undefined): { percent: number; hint: string } | null {
  if (!curiosity) return null
  const percent = Math.round(Math.min(100, Math.max(0, curiosity.level)))
  return { percent, hint: curiosity.feeling.charAt(0).toUpperCase() + curiosity.feeling.slice(1) }
}
```

In `frontend/src/survival/hud.ts`, replace:

```typescript
  rest: 'Resting', eat: 'Having a meal', escape: 'Digging out of a pit', forage: 'Foraging for food',
```

with:

```typescript
  rest: 'Resting', eat: 'Having a meal', escape: 'Digging out of a pit', forage: 'Foraging for food',
  improve_home: 'Building a bigger home', stock_larder: 'Stocking the larder',
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/survival/goals.test.ts`
Expected: `Tests  12 passed (12)`

- [ ] **Step 5: The goal line, its bar, today's plan and the trip on the HUD**

The goal sits under the purpose line (and the danger line, when there is one): "Goal: Iron tools" with its percent, a thin bar in a calm blue beside the vitals' greens, and up to three steps of today's plan, done ones ticked and struck through. Hovering it shows why Mimo wants it and who chose it. While Mimo explores (and no reflex has taken over), the purpose line says what for, "Exploring to look for iron", and a small line under it which way and why, "Heading north: my pickaxe needs it", or what it found. Beside the vitals, a curiosity bar in amber, its tooltip how Mimo feels ("Restless; nothing new for 2 game days").

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```typescript
import type { AliveResponse, CareKind } from './types'
```

with:

```typescript
import { curiosityBar, goalHint, goalLine, planSteps, tripLines } from './goals'
import type { AliveResponse, CareKind } from './types'
```

and replace:

```typescript
  const flash = hurtFlashDelay(state.hurt_at, state.server_time)
```

with:

```typescript
  const flash = hurtFlashDelay(state.hurt_at, state.server_time)
  const goal = goalLine(state.goal)
  const plan = planSteps(state.goal)
  const trip = state.reflex ? null : tripLines(state.trip)
  const curious = curiosityBar(state.curiosity)
```

and replace:

```typescript
          <p className="mt-2 text-sm font-medium leading-5 text-[#315e58]">{purposeText(state)}</p>
```

with:

```typescript
          <p className="mt-2 text-sm font-medium leading-5 text-[#315e58]">{trip ? trip.label : purposeText(state)}</p>
          {trip && <p className="truncate text-xs text-[#54726e]">{trip.detail}</p>}
```

and replace:

```typescript
          {danger && <p className="mt-0.5 text-sm font-semibold text-[#b5473a]" role="status">{danger}</p>}
```

with:

```typescript
          {danger && <p className="mt-0.5 text-sm font-semibold text-[#b5473a]" role="status">{danger}</p>}
          {goal && (
            <div className="mt-1.5" title={goalHint(state.goal)}>
              <div className="flex items-baseline justify-between gap-2 text-xs text-[#315e58]">
                <span className="truncate font-semibold">{goal.label}</span>
                <span className="tabular-nums">{goal.percent}%</span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#d9e8df]" role="progressbar"
                aria-valuenow={goal.percent} aria-valuemin={0} aria-valuemax={100} aria-label={goal.label}>
                <div className="h-full rounded-full bg-[#6b8fb5] transition-[width] duration-700" style={{ width: `${goal.percent}%` }} />
              </div>
              {plan.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-xs text-[#54726e]" aria-label="Today's plan">
                  {plan.map((step) => (
                    <li key={step.text} className={step.done ? 'text-[#8aa39d] line-through' : undefined}>
                      {step.done ? '✓' : '·'} {step.text}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
```

and replace:

```typescript
                <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${bar.value}%`, backgroundColor: LEVEL_COLORS[bar.level] }} />
              </div>
            </div>
          ))}
        </section>
```

with:

```typescript
                <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${bar.value}%`, backgroundColor: LEVEL_COLORS[bar.level] }} />
              </div>
            </div>
          ))}
          {curious && (
            <div title={curious.hint}>
              <div className="flex justify-between"><span>Curiosity</span><span className="tabular-nums">{curious.percent}</span></div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#d9e8df]" role="progressbar"
                aria-valuenow={curious.percent} aria-valuemin={0} aria-valuemax={100} aria-label="Curiosity">
                <div className="h-full rounded-full bg-[#b58a3c] transition-[width] duration-700" style={{ width: `${curious.percent}%` }} />
              </div>
            </div>
          )}
        </section>
```

- [ ] **Step 6: The goals reached on the memorial**

The memorial lists the goals a life reached under its notable events, and leaves the goal events out of those, so each goal shows once.

In `frontend/src/survival/Memorial.tsx`, replace:

```typescript
import { lifeLine } from './hud'
```

with:

```typescript
import { otherEvents, reachedLine } from './goals'
import { lifeLine } from './hud'
```

and replace:

```typescript
        {life.notable_events.length > 0 && (
```

with:

```typescript
        {otherEvents(life.notable_events).length > 0 && (
```

and replace:

```typescript
            {life.notable_events.map((event) => <li key={event.id}>{event.text}</li>)}
```

with:

```typescript
            {otherEvents(life.notable_events).map((event) => <li key={event.id}>{event.text}</li>)}
```

and replace:

```typescript
        <div className="mt-7 flex flex-col gap-2 sm:flex-row">
```

with:

```typescript
        {(life.goals_reached ?? []).length > 0 && (
          <div className="mt-5">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Goals reached</p>
            <ul className="mt-2 space-y-1 text-sm text-[#54726e]">
              {(life.goals_reached ?? []).map((goal) => <li key={goal.name}>{reachedLine(goal)}</li>)}
            </ul>
          </div>
        )}
        <div className="mt-7 flex flex-col gap-2 sm:flex-row">
```

- [ ] **Step 7: Run the tests, the build and the linter**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  308 passed (308)` (12 new), the build succeeds, eslint prints nothing.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1032 tests` … `OK`

- [ ] **Step 8: Commit**

```bash
git add frontend/src/survival/goals.ts frontend/src/survival/goals.test.ts frontend/src/survival/types.ts frontend/src/survival/hud.ts frontend/src/survival/SurvivalHud.tsx frontend/src/survival/Memorial.tsx
git commit -m "feat: the HUD shows Mimo's goal with a progress bar and today's plan, what an explore trip is for and how curious it is, and the memorial the goals it reached" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 13: Manual check on the demo and the README

This task is for the controller. It rebuilds the demo image from the branch and restarts the demo stack on its own scratch volume: `mimo-m5demo-api` (:8011) and `mimo-m5demo-worker`, volume `mimo_m5demo`, a copy of the owner's world at the natural pace (`MIMO_TIME_SCALE=1`, `MIMO_ACTION_SCALE=1`), this time with Jev's key so Jev chooses the goals and the reasons (the owner: Jev calls are cheap). The owner's real stack (`pets-api-1`, `pets-mimo-worker-1`) and its volume `pets_mimo_data` are never touched, and no key is printed. The viewer runs on :3000 (:5173 is the owner's dev server). A game day is an hour at the natural pace, so the dawn checks take up to an hour: note the time of dawn from the HUD's sky dial. If a check fails, fix the code in the task that owns it, re-run that task's tests, rebuild and repeat the check.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1032 tests` … `OK`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 6 tests` … `OK` and `Ran 3 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  308 passed (308)`, the build succeeds, eslint prints nothing.

- [ ] **Step 2: Rebuild the demo on the branch, with Jev**

The first line loads the owner's `.env` into this shell without printing anything; `-e TYPESAFE_API_KEY` hands the worker the key's value from the shell, so it never appears on a command line.

```bash
set -a; . ./.env; set +a
docker build -f backend/Dockerfile -t mimo-m5demo .
docker rm -f mimo-m5demo-api mimo-m5demo-worker
docker run -d --name mimo-m5demo-api -p 127.0.0.1:8011:8000 -v mimo_m5demo:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 mimo-m5demo
docker run -d --name mimo-m5demo-worker -v mimo_m5demo:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=1 -e MIMO_ACTION_SCALE=1 \
  -e MIMO_TICK_SECONDS=1 -e TYPESAFE_API_KEY mimo-m5demo python -m backend.workers.mimo_worker
```

Expected: two container ids. L4 adds no table: the demo world reads as it is, and its pet asks for its first goal on the worker's first tick.

Start the viewer against it (or, when a viewer already runs on :3000 against :8011, restart it so it picks up the branch's frontend) and open `http://localhost:3000/preview` in the Browser pane.

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8011 npm run dev -- --port 3000 --strictPort
```

- [ ] **Step 3: Keep a goal snippet, a trip snippet and a nudge ready**

Save these in your scratchpad directory (not in the repo). `goal.sh` prints the day, phase, purpose and mood; how curious Mimo is and how it feels; the goal with its progress and who chose it; today's plan with the steps done; a goal choice waiting and the goals set aside; the goals reached; the model calls today; and the latest goal, plan and purpose events, oldest first:

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
import time
import backend.survival.brain  # noqa: F401  (registers every goal)
from backend.survival.clock import clock_at, time_scale
from backend.survival.curiosity import curiosity_view
from backend.survival.goals import goal_view, reached_rows
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
state = world.state()
brain = state.get("brain") or {}
clock = clock_at(state["born_at"], time.time(), time_scale())
print("day", clock["day_number"], clock["phase"], "| purpose", brain.get("purpose"), "| mood",
      round(state["vitals"]["mood"]))
print("curiosity", curiosity_view(brain, time.time(), time_scale()))
view = goal_view(brain)
print("goal", None if view is None else f'{view["title"]}, {round(view["progress"] * 100)}%, chosen by {view["picker"]}')
for step in (view or {}).get("plan", []):
    print("  plan", "[x]" if step["done"] else "[ ]", step["text"])
print("goal due", brain.get("goal_due"), "| set aside", brain.get("goal_penalties"))
with world.connect() as db:
    print("reached", reached_rows(db))
print("model calls today", (brain.get("calls") or {}).get("model"))
for event in reversed(world.events(200)):
    if event["kind"] in ("goal", "plan", "purpose", "found"):
        print(event["kind"], "|", event["text"])
PY
```

`trip.sh` prints the trip Mimo is on (from the brain), what explore would go for right now and where (the same `explore_reasons` Jev is shown), the landmarks and ores it remembers, and the latest explore, found and purpose events that mention exploring, oldest first:

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
import time
import backend.survival.brain  # noqa: F401  (registers every goal and reason)
from backend.survival.clock import time_scale
from backend.survival.memory import places
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.trips import reasons_payload
from backend.survival.world import SurvivalWorld, read_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
with world.connect() as db:
    state = read_state(db)
    print("trip", (state.get("brain") or {}).get("trip"))
    for reason in reasons_payload(from_db(db, state, time.time(), time_scale())):
        print("  could", reason["reason"], "|", reason["why"], "|", reason["directions"])
    for place in places(db, ("grove", "pasture", "cave", "site", "ore")):
        print("  remembers", place["kind"], place["note"], (place["x"], place["y"], place["z"]))
for event in reversed(world.events(300)):
    if event["kind"] in ("explore", "found") or (event["kind"] == "purpose" and "explore" in event["text"]):
        print(event["kind"], "|", event["text"])
PY
```

`iron.sh` is a nudge for the goal-reached check when no goal is reached by the evening and iron tools is the goal: it gives Mimo what the goal's last steps take (3 iron ingots, a stone pickaxe, sticks and planks), so craft_tools makes the iron pickaxe and the goal is reached by Mimo's own work. Note it when you use it.

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    goal = ((state.get("brain") or {}).get("goal") or {}).get("name")
    if goal == "iron_tools":
        for item, count in {"iron_ingot": 3, "stone_pickaxe": 1, "sticks": 2, "planks": 8}.items():
            state["inventory"][item] = max(state["inventory"].get(item, 0), count)
        write_state(db, state)
    print("goal", goal, "| nudged" if goal == "iron_tools" else "| not iron tools: nothing given")
PY
```

- [ ] **Step 4: A goal chosen by Jev**

Within a minute of the worker's start, run `goal.sh`. Confirm: a goal, "chosen by jev" (when only one goal is open the rules take it without a call; then confirm Jev chooses at the next dawn), an event `plan | <Name> set a new goal: <title>. "<thought>"`, the model calls today up by one for it, and `goal due None`. In the viewer, confirm the HUD shows "Goal: <title>" with its percent and a blue bar under the purpose line, and that hovering it shows why and "Jev chose it."

- [ ] **Step 5: A day plan**

Confirm `goal.sh` prints up to 3 plan steps and an event `plan | <Name>'s plan for today: ….` right after the goal was set, and that the HUD lists the same steps under the goal line. At the next dawn, confirm a new `plan for today` event, that the goal is kept (the rules keep it; Jev may keep it or choose another, logged as `set a new goal`) and that the HUD's plan changes with it. As a step's milestone fills, confirm it is ticked and struck through on the HUD and `[x]` in `goal.sh`.

- [ ] **Step 6: Purposes follow the goal**

Over half an hour of daylight, confirm most purpose events read `decided to <purpose>, toward <goal>.` for purposes of the goal's next steps (or `toward` another open goal while its own waits, as torches wait for the evening), that the HUD's purpose line matches, and that `decided to rest.` and explores toward no goal appear only while nothing for the goal is to be done. Confirm the goal's percent rises on the HUD as the work goes on.

- [ ] **Step 7: Every trip has a reason**

Over the same half hour, run `trip.sh` a few times. Confirm every purpose event that decides to explore reads `decided to explore to <words>` (with `, toward <goal>` when its reason serves the goal) and its thought `Heading <direction> to <words>. <Why>.`; that whenever Mimo explores, `trip` names the reason, why and direction, and the HUD's purpose line reads "Exploring to <words>" with "Heading <direction>: <why>" under it; and that `could` lists the reasons with directions and what lies there. Wait for a trip that ends in a find (a `found` or `explore` event `<Name> found ….`, most often trees, a cave mouth or a sinkhole, or food): confirm the HUD's second line shows "Found …", the find appears under `remembers` (a grove, a cave with its ores, a pasture, a site, or a food or water place), and the next purpose event follows up on it (gather_wood, mine_ore, hunt, forage, build_pen, improve_home …) rather than exploring on. If no explore comes within the half hour (nothing Mimo needs lies out of sight), note it and look again after the next goal changes. Confirm no purpose event reads `decided to explore.` or `decided to explore, toward` without ` to `.

- [ ] **Step 8: A curious pet**

Confirm the HUD shows a curiosity bar in amber beside the vitals and that hovering it shows how Mimo feels ("Curious; nothing new for 3 hours" or the like), matching `goal.sh`'s `curiosity`. Over the hour, confirm first meetings appear as `found` events ("<Name> saw the taiga for the first time.", "<Name> met its first sheep.") and that `curiosity`'s level falls with them and rises again on known ground (about 2 an hour of the HUD's clock, 3 once fed, rested, warm and well with its home). Confirm a goal choice (`set a new goal`, at dawn or when one is reached) offers a discovery goal among its choices (in the worker log's Jev question, or by `goal.sh`'s goal once Mimo is restless): see new lands, meet a new creature, look into a cave, follow the water or map the far hills; and that once needs are met and curiosity is 40 or more, the day plan's last line reads "Take time to wander and see something new", ticked off by the next discovery. Whenever nothing for the goal or a need is to be done by day, confirm Mimo explores "to look for something new" (toward a discovery goal) rather than rest, and that a rest, when it comes, lasts two game minutes of the HUD's clock at most. If curiosity reaches 75, confirm explores keep coming though a goal is set and that a restless dawn turns the goal to a discovery goal.

- [ ] **Step 9: A goal reached**

Wait for an event `goal | <Name> reached a goal: <title>.`; if none comes by the evening and iron tools is the goal, run `iron.sh` once and note it. Confirm: the mood jumps by about 15 in `goal.sh`, the goal appears in `reached` with its time, the thought reads "I did it: …!" until the next goal's thought replaces it, a new goal is chosen at once (`set a new goal`, by Jev when more than one is open) with its own day plan, and the HUD's goal line switches to it. The event is notable: confirm it shows among the life's notable events: `curl -s http://127.0.0.1:8011/api/lives/<id>` (the id is the active life's) lists it under `notable_events` and the goal under `goals_reached` with its day, as the memorial will.

- [ ] **Step 10: A quiet worker**

Confirm the worker log stays quiet: `docker logs mimo-m5demo-worker 2>&1 | grep -c "crashed"` prints `0` (or only lines from before the restart), and that `goal.sh`'s model calls today stay within `MIMO_MAX_DECISIONS_PER_DAY` (2000). Leave the demo running on the new image for the owner.

- [ ] **Step 11: Describe purposeful life in the README**

In `README.md`, replace:

```markdown
## Current world rules
```

with:

```markdown
## Purposeful life

- **Goals.** Mimo works toward a goal for days: a home of its own first, then iron tools, diamond tools, armor, a full larder, a safe yard, a bigger stone home, a herd in a pen or the land around home mapped. A goal is a few milestones, each with its progress read from what Mimo carries, built and remembers, and the purposes that work toward it (`backend/survival/goals.py`, `life_goals.py`, `homes.py`, `larder.py`). A milestone whose purposes or recipes do not exist yet is left out until they do.
- **Choosing.** Jev chooses the goal when Mimo has none, at dawn, and when one is reached or set aside, from up to four open goals with their progress and next steps. Without Jev the rules keep the current goal and otherwise take the best, preferring one that something can be done for now. A goal whose progress has not risen for a game day is set aside at dawn for a day. Goal choices count toward the same daily cap and hourly budget as purpose choices.
- **Purposes follow it.** Purposes that advance the goal score 15 more, not past 80 and not late in the day or at night. While any purpose advances the goal or meets a need, only those are on offer, so Mimo rests or explores for nothing in particular only when nothing else is to be done; while its goal waits (torches wait for the evening), it works toward another open goal meanwhile. With a goal, a purpose that ended as usual is chosen again by the rules, and Jev speaks at the moments that matter. A purpose event says which goal it works toward: "Pip decided to gather stone, toward iron tools."
- **Every trip has a reason.** Mimo explores only to look for something its goal or a need calls for: trees when it needs wood and none stands near, food when it carries little and none is near, iron for its pickaxe or armor, leather for armor, a creature seed for a pen, flat ground for a bigger home, or the land around home to map (`backend/survival/trips.py`, `scouting.py`). It heads where the land likely holds it (trees where trees grow, iron at cave mouths, sinkholes and outcrops, food where berries and mushrooms grow), looks around after each walk, remembers what it finds as a place or landmark (a grove, a cave with the ore in its walls, a pasture, a site), and a find it came for ends the trip so the next purpose follows up. The rules pick the reason, the one that serves the goal first; Jev picks it in the same call when it chooses. The thought and the event say what for: "Pip decided to explore to look for iron, toward iron tools." "Heading north to look for iron. My pickaxe needs it."
- **A curious pet.** Curiosity (0–100, `backend/survival/curiosity.py`) grows while Mimo lives on ground it knows, faster once its needs are met, and falls with each discovery: new ground, a biome it never saw ("Pip saw the taiga for the first time."), a kind of block it never dug, a kind of creature it never met ("Pip met its first sheep."), a place new to it. Whenever nothing for its goal or a need is to be done, Mimo goes looking for something new (land, creatures or caves it never saw, then new ground, up to 90 blocks from home) rather than sit, and rest lasts two game minutes at a time; past 50 curiosity lifts every trip into the work band, and from 75 exploring counts as a need, so goal work does not crowd it out. Once its needs are met, the day plan sets time aside to wander. Discovery goals are always on offer once home stands (`discovery.py`: see new lands, meet a new creature, look into a cave, follow the water, map the far hills); they repeat, and pull harder the more curious Mimo is, so a restless pet's dawn turns from its routine to one. The HUD shows a curiosity bar, and the model is told how Mimo feels ("restless; nothing new for 2 game days"). L4b adds the knowledge journal and expeditions.
- **Goals that need their own work.** A bigger stone home: improve_home starts a bigger shelter with cobblestone walls near home (or at a site a trip found) once Mimo carries half its blocks, build_shelter finishes it and Mimo moves in. A full larder: while it is the goal, a fed Mimo gathers up to 40 hunger more food than a day's worth and stock_larder puts a chest in the shelter and stores the spare food, until the chest holds a day's food. Armor: Mimo hunts for hides though fed, a few times a day, and iron armor is worth its ingots before any blow. Diamond tools: mine_ore goes for any diamond Mimo knows of, not only once it knows of three.
- **A day plan.** At dawn, and when a goal is chosen, Mimo writes the next three steps toward it ("Pip's plan for today: find iron ore, mine 3 iron ore and make an iron pickaxe.") and ticks them off.
- **Reaching a goal** is a notable event ("Pip reached a goal: iron tools.") with a mood boost, and the memorial lists the goals a life reached.
- `/api/mimo` has `goal` (title, why, progress, today's plan, who chose it), `curiosity` (level and feeling) and, while Mimo explores, `trip` (what for, why, which way, what it found); lives have `goals_reached`; the model's payload has `goal`, `explore_reasons`, `trip` and `curiosity`. The HUD shows "Goal: Iron tools" with a progress bar and today's plan under the purpose line, and "Exploring to look for iron" with "Heading north: my pickaxe needs it" while Mimo explores.

## Current world rules
```

- [ ] **Step 12: Commit**

```bash
git add README.md
git commit -m "docs: describe purposeful life" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (L4 outline, Decisions and the owner's morning note) | Where |
|---------------------------------|-------|
| Goals are a registry: name, why, validity, progress (0–1 from state and memory), the purposes that advance them, completion | Task 1 (`goals.Goal`, `Milestone`, `register_goal`, `progress_of`, `complete`, `is_open`; resolution 3) |
| A mood reward | Task 1 (`Goal.reward`, `GOAL_MOOD`), Task 2 (`reach_goal`) |
| First shelter (M5), then a better home (a bigger tier, stone walls) | Task 5 (`first_shelter`), Task 6 (`better_home`, `improve_home`, the site trip; resolution 10) |
| Iron tools, then armor | Task 5 (`iron_tools`; `armor_up` after it, with iron armor) |
| A full larder: a chest with food | Task 7 (`full_larder`, `stock_larder`, `more_food`) |
| A safe yard: torches, a door, a fence | Task 5 (`safe_yard`; the fence waits for a `build_fence` purpose: see spec gaps) |
| A herd: creature seeds and a pen (optional until L3) | Task 5 (`herd`, with L3's `build_pen` and `stock_pen`, and the seed trip; resolution 3) |
| Map the land: explore memory | Task 5 (`map_land`, `land_seen` over `memory_explored`, the map trip) |
| Jev picks a goal at dawn, or when one completes or fails, from a small offered set with facts; the rules picker is the fallback | Task 2 (`tend_goal` asks at dawn, when reached or given up), Task 3 (`offers`, `prepare_goal`, `goal_route`, the `"goal"` question; resolution 7) |
| A goal lasts days, not minutes | Task 3 (the rules keep the current goal: `STICK`), Task 2 (given up only after a game day without progress; resolution 6) |
| Purposes that advance the active goal get +15; the others are capped in the leisure band unless they meet a need | Task 1 (`pickers.steer`, `goals.boosted`, `meets_need`, `ADVANCES`; resolution 8) |
| Rest and explore are chosen only when nothing advances the goal or a need | Task 1 (`steer` offers only goal and need purposes while any exist; `toward` works toward another goal while the goal waits), Task 4 (explore only with a reason), Task 11 (the headless check) |
| A day plan at dawn lists the goal's next steps, shown in the HUD | Task 2 (`day_plan`, the `plan` event), Task 10 (`goal_view`'s plan), Task 12 (the HUD's plan) |
| Completing a goal is a notable event with a mood boost | Task 2 (`reach_goal`: a `goal` event, not routine) |
| The HUD shows the goal and its progress bar | Task 12 (`goalLine`, `SurvivalHud`) |
| The memorial lists the goals reached | Task 10 (`goals_reached` on lives), Task 12 (`Memorial`, `reachedLine`) |
| The Jev (and Luna) payload carries the goal context | Task 10 (`context_payload`'s `goal`), Task 3 (the goal question's `goals_reached`), Task 1 (criteria and instructions name the goal) |
| `/api/mimo` gains `goal` | Task 10 (`brain_view`'s `goal`) |
| Every trip has a reason, from the active goal or a current need; never just the least-explored ground | Task 4 (`trips`: explore valid only with a reason; the needs' reasons trees and food), Task 5 (iron, hides, seed, map), Task 6 (site); resolution 15 |
| Examples: iron for armor or the pickaxe (unexplored stone, hills, cave mouths and sinkholes, remembered caves); birch or spruce wood, sheep for wool, a creature seed (biomes of the right kind); a better home site; map the land | Task 5 (iron: openings, outcrops, hills; seed: tall grass), Task 4 (trees: where trees grow, the grove's wood named), Task 6 (site), Task 5 (map); wool and one kind of wood: see spec gaps |
| Targets scored by how likely they hold what the reason needs, from explore memory, remembered places and landmarks, biome and height | Task 4 (`trips.targets`: likelihood × 3 + novelty from `memory_explored` + distance; spots from remembered places), the reasons' `value` in Tasks 4–6 (worldgen's trees, plants, water, biomes' animals, heights, openings, rocks) |
| A trip ends early on a find, remembered as a place or landmark; the next purpose follows up | Task 4 (`trips.look_after`, `Find.done`, the discovery trigger; `grove`, `pasture`, food and water places), Task 5 (`cave` and ore places), Task 6 (`site`, which `better_design` uses) |
| The reason is visible in the thought, the event, the HUD and the Jev payload | Task 4 (`trip_thought`, the purpose event's "to <words>"), Task 10 (`explore_reasons`, `trip`, the `"explore_reason"` criteria), Task 12 (`tripLines` on the HUD) |
| Rules pick the reason when Jev isn't used; Jev may pick it | Task 4 (`trips.offers`: goal first, then score; `next_stop` in the tick), Task 10 (the `"explore_reason"` question in the same call; resolution 16) |
| A headless check counts explores without a reason, and that count must be 0 | Task 11 (`test_every_explore_goes_for_a_reason`: purpose events and ticks) |
| L5: leave hooks, do not build | Task 4 (`trips.Reason.reach`; resolution 17) |
| Cost: no model calls inside the tick; goal picks follow the purpose picks' cost rules | Task 2 (the tick decides nothing by model), Task 3 (goal calls count toward the daily cap and Jev's hourly budget; resolutions 7, 9), Task 4 (trips are rules in the tick), Task 10 (the reason rides in the purpose call: no extra call) |
| Error handling: crashes logged once, the tick model-free, GETs read-only, migrations idempotent (none added), the headless sims green with the milestone's own sim check | Tasks 1–4 (`log_once` guards; `trips.guarded`), Task 10 (a GET writes nothing), Tasks 4–8 (slow sims), Task 11 (the aimless and reason checks) |
| Curiosity: 0–100, grows each game hour on known ground, faster once needs are met; discoveries (a new patch, biome, kind of block, kind of creature, landmark) lower it | Task 8 (`curiosity.tend_curiosity`, `note_discoveries`, `meet_creatures`, `trips.FINDS`; resolution 19) |
| High curiosity lifts exploring into the work band and steers goal choice toward discovery goals | Task 8 (`lift` in `trips.LIFTS`, `goals.URGES`, the wander trip), Task 9 (`discovery.pull`: 30 + 0.7 × curiosity, +100 once restless) |
| The Jev payload carries curiosity as a feeling | Task 10 (`context_payload`'s `curiosity`: "restless; nothing new for 2 game days") |
| Discovery goals are always on offer: see the taiga, reach the bottom of the sinkhole, follow the river, meet a new creature, map the far hills | Task 9 (`new_land`, `cave`, `water`, `new_creature`, `far_hills`, repeating; Task 3's `offers` always keeps one; resolution 20; the sinkhole and the river: see spec gaps) |
| Once needs are met, the day plan sets time aside for curiosity; a better home stops Mimo settling for its first hut | Task 8 (`time_to_wander` in `goals.PLAN_EXTRAS`), Task 6 (`better_home`) |
| A curiosity bar with the vitals | Task 10 (`/api/mimo`'s `curiosity`), Task 12 (`curiosityBar`, `SurvivalHud`) |
| Once a home exists, each game day in a headless run brings at least one discovery | Task 11 (`test_once_home_stands_every_game_day_brings_a_discovery`) |
| The knowledge journal and expeditions; the journal panel and the expedition line | L4b (resolution 18) |
| The controller's L3 review: goals such as diamond tools and armor must not stall on L3's gates (armor only after a blow, diamonds only with three known) | Task 5 (`harm.ARMOR_WANTED`, `work.EAGER`, added by the goals; resolution 21) |
| The controller's L3 review: rest and sleep took 70–80 % of the ticks; curiosity and the day plan should cut it, at most half once needs are met | Task 8 (the wander trip always on offer, two-minute rests), Task 11 (the rest check: 60 % → 44 %, 72 % → 46 % in slow mode; resolution 22) |
| Fewer aimless loops, measured as purpose changes per game hour against today's baseline | Task 11 (aimless changes per game hour: 4.5 → 0.0, 4.56 → 0.81 in slow mode; resolution 14) |

Spec gaps the plan fills or leaves (the controller ledgers them):
- The spec names no goal list beyond its examples, no progress formula, no day-plan length and no numbers for "a small offered set", "lasts days" or the mood boost: resolutions 3–7 set them (milestones and their mean, 3 steps, 4 goals, the current goal kept by the rules and given up after a game day without progress, +15 mood).
- "Capped in the leisure band": the spec gives no cap. While anything advances the goal or meets a need, the other purposes are left out of the choice altogether (below any cap), which also keeps Jev's pick on the goal; when nothing does, they keep their own scores (resolution 8).
- A safe yard's fence: L3 builds fences only as a pen's ring and has no yard fence, so the fence step waits for a `build_fence` purpose that no plan adds yet.
- Iron tools stop at the iron pickaxe: mine_ore wants only the iron a pickaxe takes (an iron sword would need its own change to `work.wanted_ores`).
- Goal choices use Jev only; Luna (capped and costly) never chooses goals or reasons.
- The owner's examples "find birch/spruce" and "find sheep for wool": no purpose needs one kind of wood (any log does) or wool (no recipe uses it), so there is no such reason; the trees reason names the wood it finds ("birch trees"), and a reason for wool can register when something needs wool.
- "Remembered cave entrances" as iron targets: Mimo looks into a cave mouth or sinkhole once, remembers it with the ore it could reach in its walls, and does not go back to look again; the remembered ore draws mine_ore instead. A cave already looked into scores nothing for iron. Mimo sees iron only where a cave entrance bares it or where it digs (as before); caves reached only by digging are gather_stone's.
- The seed reason breaks tall grass where it stops, and a creature seed drops 1 in 60 (L3's rate), so a trip for a seed often ends without one; a herd can stay a slow goal, and is set aside after a day without progress (resolution 6).
- "Find sheep for wool" aside, the reasons' likelihoods are the plan's (resolution 15): 3 trees, 2 wild plants, 12 tall grass make a spot sure; an opening not looked into within 12 blocks is sure, an outcrop 0.5, hills 0.3; cow land 1, rabbit ground 0.4; flat ground within 1 block 1, within 2 blocks 0.4.
- The owner's day-17 note splits L4 (resolution 18): the knowledge journal (investigating first meetings, facts, knowledge that unlocks behaviour, Jev's journal lines, the journal panel) and expeditions (packing, travelling a day or two past the explored range, camps and outposts, the expedition line) are L4b's plan.
- "Reach the bottom of the sinkhole" becomes looking into a cave mouth or sinkhole (Mimo cannot climb down a shaft deeper than 3 blocks; L4b's expeditions may dig down), and "follow the river" becomes finding a lake it does not know (worldgen has lakes and pools, no rivers).
- Curiosity's numbers are the plan's (resolution 19): the spec's "each game hour" is read as an hour of the HUD's clock (a 24th of a game day), since the code's `HOUR` is a whole game day.
- The spec's aimless measure predates reasons: resolution 14 keeps counting an explore toward no goal as aimless even when it serves a need, so the baseline stays comparable; Task 9's second check is the separate "explore without a reason" count.
