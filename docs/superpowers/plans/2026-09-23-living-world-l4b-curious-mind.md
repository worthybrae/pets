# Living World L4b: A Curious Mind (the Knowledge Journal and Expeditions) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Mimo try to understand the world and go farther to see it (the owner, after watching the pet until day 17: "I want it to be more curious and constantly exploring and trying to undestand the world"). A knowledge journal: the first time Mimo meets a kind of block, plant, creature, biome or landmark with a lesson in a rules table, it studies it (what it digs, sees laid bare beside it or walks into it learns at once; what it only sees from a walk it goes back to: the new `investigate` purpose walks up, looks it over and takes a sample, mining one or watching it) and records the fact ("Pip learned that gravel sometimes hides flint."); knowledge unlocks behaviour (it digs gravel for flint only once it learned that gravel hides flint, and goes after gold and diamonds only once it has seen their ore); Jev chooses the line in Mimo's voice for each lesson, in the purpose call it makes anyway, never in the tick. Expeditions: a curious pet whose needs are met takes an expedition goal, packs food and torches, travels past the land it knows, digs in for the night by a campfire with torches, maps and studies what it finds, and comes home; its camps are remembered as outposts. The viewer gets a journal panel ("What Pebble has learned") and an expedition line on the HUD; `/api/mimo` and the model's payload get the journal and the expedition; and a headless run takes the days tests' pet on an expedition and back.

**Architecture:** L4a's registries carry it. `backend/survival/journal.py` holds the rules table of lessons (`LESSONS`), learning (`learn_lesson`, remembered in `memory_knowledge` as fact `"lesson"`), what Mimo notices after each finished step (`observe_journal`, from `brain.observe_step`: what it learns there and then, and "sight" places for what it sees to study later) and the `investigate` purpose; `Situation.lessons` is what the rest of the brain reads to gate work (`flint.flint_valid`, `work.wanted_ores`). Jev's line rides as a third question (`"journal_line"`) on a purpose call (`choosing.prepare`/`decide`/`store_choice`). `backend/survival/expedition.py` registers the expedition goal (its milestones: pack, travel, camp, map, come home), keeps the expedition in the brain and moves it on after each vitals step (`tend_expedition`), registers the `pack` and `come_home` purposes and the "expedition" trip (L4a's `trips.Reason`, with a longer reach), and tells the rest of the brain when Mimo means to stay out (`purposes.AWAY`: go_home, the head_home reflex and build_shelter's new home leave it be) and what it keeps on it (`storage.KEEPS_MORE`). `backend/survival/camp.py` registers the `camp` purpose (dig in, fire and torches, a roof), remembers outposts and takes the roof off in the morning (`leave_camp`, from `brain.brain_plan`). The viewer gets a pure `journal.ts` module, a `JournalPanel` and the expedition line.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-living-world-design.md`, "L4 addition: a curious pet" (the owner, 2026-09-24 midday): its knowledge journal, expeditions, the viewer's journal panel and expedition line, and its "Plans" split; the Decisions' "Cost" and "Error handling and testing". It builds on the L4a plan (`docs/superpowers/plans/2026-09-23-living-world-l4-purposeful-life.md`: goals, trips with reasons, curiosity, discovery goals) and follows its shape.

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls: a fake Jev stands in where a test needs one. Nothing reads `random` or the clock.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments, no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components. No stylesheet changes: Tailwind classes inline, as the HUD has them.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. Read-only GETs never write. L4b adds no table and no column: lessons live in `memory_knowledge` (fact `"lesson"`), sights and outposts in `memory_places` (kinds `"sight"`, noted with the thing, and `"outpost"`), the journal's state and the expedition in Mimo's state JSON (`state["brain"]["journal"]`, `["expedition"]`, `["expedition_at"]`).
- **No model call inside the tick.** The tick learns, notices sights, plans investigations, packs, travels, camps and comes home by rules. Jev chooses a journal line only in the worker's Chooser, in the purpose call it makes anyway, outside the tick transaction; without Jev the journal shows the fact. Validity checks, scores and facts never write; a planner writes only the journal's `studying` and the expedition's camp it plans.
- A crash in the journal's step hook, the expedition's tending or step hook, the camp's step hook, an `AWAY` check or a `KEEPS_MORE` hook never stops a tick or the worker: each is logged once (`once.log_once`) and counts as nothing. A failed Jev call leaves the lesson waiting and falls back to the rules for the purpose, as before.
- Values from the owner's day-17 note (spec, "L4 addition: a curious pet"): the first time Mimo meets a new block, plant, creature, biome or landmark it investigates it (walks up, looks, takes a sample: mines one, watches it or hunts it) and records a fact from a rules table ("gravel sometimes hides flint", "skitters come out of caves at night", "lava lights up caves"); knowledge unlocks behaviour (gravel dug for flint only once learned; gold only once gold ore was seen); Jev may phrase the journal line, never inside the tick or in tests; with high curiosity and its needs met Mimo can take an expedition goal: it packs food and torches, travels past its explored range for one or two game days, camps at night with a campfire and a small hut or dug-in shelter lit by torches, maps and samples as it goes and comes home with its finds; camps are remembered as outposts; a journal panel "What Pebble has learned" and an expedition line on the HUD.
- `MIMO_TIME_SCALE` and `MIMO_ACTION_SCALE` (both default 1) are for manual runs only. L4b adds no settings.
- Never run `docker` or `docker compose` in Tasks 1–9. Task 10 is the controller's manual check on the demo stack (`mimo-m5demo-api` on :8011 and `mimo-m5demo-worker`, volume `mimo_m5demo`); never touch, mount or migrate the owner's real volume `pets_mimo_data` or the real stack (`pets-api-1`, `pets-mimo-worker-1`). Never print `TYPESAFE_API_KEY` or any other key.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (1032 pass once L4a is in)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_journal.py" -v`
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` (a few minutes), the same with `-p "test_survival_days.py"`, and (from Task 8) `-p "test_survival_expedition_run.py"`
- Frontend tests: `cd frontend && npm test` (308 pass once L4a is in)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint src/survival src/engine` (prints nothing when clean)

Each task says how many tests it adds. If the real starting totals differ, expect the same increases on top of them.

Transcription: every edit is a fenced block, either a whole new file ("Create `path`:"), a "replace: … with: …" pair in a named file ("In `path`, replace:", then "and replace:" for more pairs in the same file), or a block added at the end of a file ("In `path`, append:"; such a block starts with the two blank lines that separate it from what is there). Old texts are kept short, so a task still applies when a neighbouring line changes. The dry run applied the L4a plan and then each task of this one with the controller's apply script (`.superpowers/sdd/2026-09-23-living-world-l2-danger/apply_plan.py`) to a `git archive` copy of `bd765f2`, and ran each task's checks after it.

## Plan-level resolutions

The spec gives L4b as a few bullets. These are the details; every task follows them and the controller ledgers them.

1. **Base.** This plan runs on top of the L4a plan (all 13 of its tasks), on branch `worthy/23_09_2026/survival_core` from `bd765f2` (L3 with its final fix wave). It uses L4a's registries and hooks by name: `goals.Goal` (with `repeat`), `Milestone`, `register_goal`, `active`, `URGES`, `meets_need`, `adopt_goal`, `ask_for_goal`; `trips.Reason`, `register_reason`; `curiosity.discovered`, `seen`, `value_of`, `needs_met`, `curiosity_state`, `CURIOUS`, `RESTLESS`; `foraging.MORE_FOOD`; L4a's test helpers `test_survival_life_goals.built` and `test_survival_goal_choice.Recorder`. If L4a's names change in review, only the imports here change.
2. **What a first meeting is** (Tasks 1 and 2). A thing has a lesson when `journal.LESSONS` has one for it: 10 blocks (gravel, sand, snow, mud, moss, coal ore, iron ore, gold ore, diamond ore, lava), 5 plants (sugar cane, pumpkin, melon, brown mushroom, cactus), 7 creatures (rabbit, chicken, sheep, cow, fish, gloomling, skitter), the 7 biomes and 3 landmarks (a cave mouth, a sinkhole, a lake). Each lesson has its kind, its words ("a skitter"), the fact, what it unlocks (in words, for gravel, gold and diamonds) and two more lines in Mimo's voice for Jev to choose among. The facts are true to the game (gravel's flint is one mined gravel in 8; a coal and a stick make 4 torches; lava lights caves; skitters come out of caves at night; cows give leather for L2's cap and tunic). Mimo learns at once what it meets right there: a kind of block it digs (the sample is in its arms), an ore or lava laid bare beside a block it digs (it sees it within reach), the biome it walks into (it looks around), and a cave mouth, sinkhole or lake it remembers within 8 blocks of where a walk ends (it walked up to it). What it only sees from a walk it studies later: after each walk it looks over every other column within 6 blocks for a surface block with a lesson and the plants within 8, and remembers the first of each kind as a `sight` place, noted with the thing; creatures it met (L4a's `"creature"` facts) are its other things to study.
3. **Learning.** A lesson is learned once (`memory_knowledge`, fact `"lesson"`, with when): a routine `learned` event ("Pip learned that gravel sometimes hides flint."; routine, so the memorial's notable events are not all lessons), a discovery for curiosity (5 points, `NEW_LESSON`), the thing's sights forgotten, and, for a lesson that unlocks something, a new choice asked for (a `discovery` trigger). The journal starts with curiosity: before the tick first tends curiosity the journal does nothing, so the older unit tests that feed steps to the brain by hand see no lesson events.
4. **investigate** (Task 2), "take a closer look". On offer by day while some sight within 32 blocks is still there and not learned, or a creature of a kind Mimo met and has not studied is within 24 blocks; the nearest first. The plan walks up (within reach of a block or plant, within 4 blocks of a creature), takes a sample (mines a block it can dig, with no water over it, that it neither built nor tends), and looks it over: a wait of 4 game seconds, or 8 watching a creature. When that wait ends the lesson is learned (`observe_journal`, told of the wait by its purpose), then the purpose is done. A walk or sample that fails leaves that thing alone for half a game day. Work band: 40 plus a quarter of curiosity (40 to 65), minus the late-day penalty; a curious pet studies before it rests. "Hunts it" (spec): hunting stays food and hides work (L1, L4a); a creature is watched.
5. **Knowledge unlocks work** (Task 3). `Situation.lessons` (the lessons learned, read once per Situation) is what the brain reads. gather_flint is on offer only once Mimo learned that gravel hides flint, and mine_ore wants gold and diamonds only once it learned about their ore, which it does the moment it sees one (resolution 2). The tests that give Mimo gravel or remembered gold and diamonds learn those lessons first; each gains a line that shows the gate.
6. **Jev's journal line** (Task 4). Jev's API answers choices, so Jev phrases a lesson by choosing among its lines: the plain fact first, then the two in Mimo's voice. While a lesson waits for its line (`journal["unphrased"]`, oldest first), a purpose call to Jev asks a third question, `"journal_line"`, in the same call (no extra call, the same cost rules), with `JOURNAL_INSTRUCTIONS` and the fact in the payload's `learned`; the line Jev chose is kept (`journal["words"]`) and the lesson no longer waits. A call that fails leaves it waiting; the rules and Luna leave it waiting too. Luna never phrases lines (it is capped and costly). The journal shows the fact until Jev has chosen.
7. **The expedition goal** (Task 5), "An expedition", after first_shelter, repeating. On offer with a home Mimo built, curiosity 60 or more, its needs met (L4a's `needs_met`: fed, rested, warm, well, with a home it built; all but hunger will do while it carries 30 hunger of food, as at dawn, when the goal is chosen and a pet is hungry with its breakfast in its pack) and two game days since the last one ended (`brain["expedition_at"]`); once it is Mimo's goal it stays open until reached or given up. With L4a's wander trip always on offer, a pet walked new ground near home all day and its curiosity never climbed to 60, so walking its own land now lowers curiosity by 1, not L4a's 3 (`curiosity.NEW_GROUND`); the other discoveries lower it as before. Measured over the days tests' world with hatch and chooser seeds 2, 3, 5, 7, 8, 9, 11, 13 and 21 for 8 game days: with 3, the strict needs and a campfire in hand, 2 of the 9 pets set out; with these changes and a campfire's makings counting as packed (resolution 8), 7 did, 5 of them home again by day 8. Rules score: 40 + 0.8 × curiosity, +110 once restless (75), so a restless pet whose needs are met sets out rather than wander near home (a discovery goal pulls 30 + 0.7 × curiosity + 100). Milestones: pack food and torches (pack, forage, fish, hunt, cook, gather_wood, mine_ore), travel past the lands it knows (explore), camp out for the night (camp, explore and investigate: until the first night the trip goes on), map new ground (explore, investigate), come home with its finds (come_home). Reward: 20 mood. Reaching it is L4a's notable `goal` event.
8. **Packing.** 90 hunger of food (a day and a half: `foraging.MORE_FOOD` asks the food purposes for 30 more than a day's worth while packing), 4 torches and a campfire, or the logs and sticks for one (a pet with full arms cannot craft it now; it makes it at camp, or camps without a fire when it still cannot). The `pack` purpose (60) crafts the torches (a coal and a stick make 4) and the campfire (logs and sticks) from what Mimo carries, as far as they fit in its arms; mine_ore brings coal and gather_wood logs. With no coal to be had (none carried, and no coal ore mine_ore could go back for), Mimo goes without torches rather than wait for good. From packing until it is home again, build_storage and drop_items keep the torches and the food on Mimo (`storage.KEEPS_MORE`), where they used to put a day's food beyond 60 and every torch home did not need away.
9. **Setting out.** Packed, by day (not late, not at night), Mimo sets out: a notable `expedition` event ("Pip set out on an expedition to the east."). The explored range is the distance from home within which nine in ten of the patches it visited lie (48 to 144 blocks); the target is that plus 48, at most 200 blocks from home; the heading is the compass way with the most dry land it never visited just past the range (three bearings 20° apart, three distances). The "expedition" trip ("travel past the lands it knows", 65) is wanted while the expedition is out: land past the range within 60° of the heading is sure, past the range within 100° half as good, land on the way out 0.4; its reach from home is 200 blocks (the L5 hook of L4a's resolution 17 is a reason with a longer reach: this is the first). Once past the target, land past the range is sure every way, so Mimo roams the far land, mapping it and studying what it finds, until it is time to camp.
10. **Staying out** (`expedition.away`, in `purposes.AWAY`). On the way out, and on the way back when dusk or night finds it farther than 48 blocks from home, Mimo means to stay out: go_home is not on offer, the head_home reflex leaves it be, and build_shelter starts no new home out there (with no shelter within 128 blocks it would otherwise design one).
11. **Camping** (Task 6). From late in the day (5 game minutes before dusk) and at night, while Mimo means to stay out, `camp` (85; 95 at dusk and at night) is on offer when it has somewhere to camp, and it meets a need (`goals.URGES["camp"]`), so goal work never crowds it out. It goes back to an outpost within 24 blocks whose hole is still open, or picks the nearest spot within 6 blocks (and 2 up or down) where it can dig in: natural ground it can dig, solid under and on all four sides of the hole, nothing it built or tends, no water or lava beside it, and a roof block (carried, or the one it digs out). The dug-in shelter is the spec's "dug-in shelter": Mimo is one block tall, so a hole one block deep with a block over it walls it in on six sides; a small hut would take a shelter's worth of blocks (spec gap). It puts the campfire (made from logs and sticks if it carries none) and 2 torches on the ground beside the hole, digs out the block it stands on and drops in, then puts a block over its head; the camp is remembered as an outpost (`memory_places` kind `outpost`, a notable `camp` event, "Pip dug in for the night and made a camp."). It waits there for nightfall; at night sleep takes over (the brain remembers the hole as a sheltered spot, so sleep lies down in it; the campfire keeps it warm, the torches keep hostiles from spawning around it, and nothing reaches it through six walls). In the morning the first batch any purpose plans inside the camp (but camp and sleep) takes the roof off first (`camp.leave_camp`), and Mimo climbs out.
12. **Turning home and coming home.** A night slept farther than 48 blocks from home counts (`nights`), camp or not; Mimo wakes up knowing whether it turns home: after a night out once it passed the target and walked onto new ground 8 times (`walks`, the "map" milestone), or after 2 nights, and at once (by day) when short of food (under 20 hunger carried and hungry) or health (under 40). Homeward, `come_home` (75) walks it back (up to 6 walks a choice), and it camps again should dusk catch it far out. Within 6 blocks of home, it logs what it found (a notable `expedition` event: "Pip came home from its expedition: 196 blocks out, 1 night camped, 3 new things learned.") and the goal is complete; the tick reaches it as any goal. An expedition given up (L4a's rules) ends there; either way `brain["expedition_at"]` says when, and the next is two game days away.
13. **What the model and the viewer are told** (Task 7). The payload gains `journal` (how many lessons, the newest fact, up to 3 things it could study near it) and `expedition` (null without one). `/api/mimo` gains `journal` (the lessons, newest first, at most 40: thing, kind, words, fact, line, unlocks, when) and `expedition` (phase, direction, how far out it got, the target, nights, whether it is making camp; null without one).
14. **Viewer** (Task 9). A "Journal (n)" link beside "Blocks & crafting" opens the journal panel, titled "What Pebble has learned" with the pet's name: each lesson in Mimo's voice, a label for its kind, the plain fact under Jev's line when they differ, and what it unlocks ("Now Pebble digs gravel for flint."). Under the goal the HUD shows the expedition line ("Expedition: packing food and torches", "Expedition east · 132 of 180 blocks out · 1 night out", "Expedition: making camp for the night", "Expedition: heading home"). The four new purposes get words.
15. **The headless checks** (Task 8). The default suite takes the days tests' pet (hatch seed 8, chooser seed 8, 60 real seconds a game day) through a real expedition: early on day 2, with its home built, it is made restless, fed, rested and packed and a goal choice is asked for; by the end of day 3 it has set out, dug in, come home with one night camped and reached the goal, in that order, its camp's roof is off and it has learned something. In slow mode the same pet, left alone for 7 game days, goes on an expedition of its own and comes home. L4a's headless checks still hold with L4b (measured: changes of purpose 47.5 a game hour on average, 53.8 in slow mode; the busiest hour 50 and 72 against `ALL_EVENTS_PER_HOUR` 90; at most 12 and 26 toward no goal against 52 and 55; aimless 0.0 and 0.31 a game hour; rest and sleep 43 % (45 % in slow mode) of the time once home stands).
16. **Out of scope.** L5 (danger by distance, ruins, loot); a small hut as a camp; outposts on the minimap; hunting as a way to study a creature; carrying samples home; Luna phrasing lines; lessons beyond the table.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/survival/journal.py` | Create | The lessons table, learning, sights, the `investigate` purpose, the journal for the viewer and the model |
| `backend/survival/expedition.py` | Create | The expedition goal and its state, packing, setting out, the expedition trip, staying out, turning and coming home, `pack` and `come_home`, the view |
| `backend/survival/camp.py` | Create | The `camp` purpose, outposts, leaving camp |
| `backend/survival/situation.py` | Modify | `Situation.lessons` |
| `backend/survival/world.py` | Modify | `learned` events are routine |
| `backend/survival/brain.py` | Modify | The journal's, the expedition's and the camp's hooks in `observe_step`, `notice_step` and `brain_plan` |
| `backend/survival/flint.py`, `work.py` | Modify | Knowledge gates flint, gold and diamonds |
| `backend/survival/models.py`, `choosing.py` | Modify | The `"journal_line"` question and keeping Jev's line |
| `backend/survival/purposes.py`, `reflexes.py`, `building.py` | Modify | `AWAY`: no going home and no new home while Mimo means to stay out |
| `backend/survival/storage.py` | Modify | `KEEPS_MORE`: an expedition keeps its torches and food |
| `backend/survival/curiosity.py` | Modify | New ground lowers curiosity by 1, not 3 |
| `backend/survival/pickers.py`, `snapshot.py` | Modify | `journal` and `expedition` in the payload and the stream |
| `backend/tests/test_survival_{journal,investigate,journal_lines,expedition,camp,journal_view,expedition_run}.py` | Create | One test file per new part |
| `backend/tests/test_survival_{flint,tiers,life_goals,pickers}.py` | Modify | The knowledge gates; the payload's new keys |
| `frontend/src/survival/journal.ts` (+ test), `JournalPanel.tsx` | Create | The journal's and the expedition's words; the journal panel |
| `frontend/src/survival/types.ts`, `hud.ts`, `SurvivalHud.tsx`, `SurvivalWorld.tsx` | Modify | The stream's new fields, the new purposes' words, the expedition line, the journal link and panel |
| `README.md` | Modify | A curious mind |

## Tasks

1. The knowledge journal: lessons learned at once, sights to study
2. Taking a closer look: the investigate purpose
3. Knowledge unlocks work: flint, gold and diamonds
4. Jev chooses the journal's lines
5. Expeditions: the goal, packing, setting out, staying out and coming home
6. Camping out: dug in by a campfire, outposts
7. What the model and the viewer are told
8. The headless checks: an expedition in the real world
9. Viewer: the journal panel and the expedition line
10. Manual check on the demo and the README

Tasks 1–8 are the backend and 9 the viewer. Tasks 1–4 are the journal and Tasks 5–6 expeditions; Task 7 streams both, and Task 9 needs only Task 7's fields.

---

### Task 1: The knowledge journal: lessons learned at once, sights to study

The rules table of lessons, and learning what Mimo meets right there: a kind of block it digs, ore or lava its digging lays bare, the biome it walks into, a cave mouth, sinkhole or lake it walks up to. What it only sees from a walk is remembered as a sight to study later (Task 2). Resolutions 2 and 3.

**Files:**
- Create: `backend/survival/journal.py` (its header with every constant, the lessons, learning and noticing; Tasks 2 and 7 append the rest)
- Modify: `backend/survival/situation.py` (`Situation.lessons`), `backend/survival/world.py` (`learned` events are routine), `backend/survival/brain.py` (`observe_step` feeds the journal)
- Test: `backend/tests/test_survival_journal.py`

**Interfaces:**
- Consumes: L4a's `curiosity.discovered` (and the tick's curiosity: the journal waits for it); `memory.know`, `places`, `remember`, `forget`, `cell_of`; `worldgen.biome_at`, `surface_material`, `terrain_height`, `SEA_LEVEL`; `senses.natural_plants`; `steps.as_cell`; `triggers.ensure_brain`, `mark_trigger`; `once.log_once`; `test_survival_building.World`.
- Produces:
  - `journal.Lesson(thing, kind, words, fact, unlocks="", lines=())` (frozen); `LESSONS: dict[str, Lesson]` (32 lessons, resolution 2), `teach(*lessons)`; `SURFACE` (the blocks with a lesson), `PLANTS`, `LANDMARKS` ({"mouth": "cave_mouth", "sinkhole": "sinkhole"}).
  - Constants: `FACT = "lesson"`, `NEW_LESSON = 5.0`, `INVESTIGATE_REACH = 32.0`, `CREATURE_SIGHT = 24.0`, `WATCH_REACH = 4.0`, `LOOK_SECONDS = 4.0`, `WATCH_SECONDS = 8.0`, `TRIED_FOR = DAY_SECONDS / 2`, `SIGHT_RADIUS = 6`, `PLANT_SIGHT = 8.0`, `LANDMARK_NEAR = 8.0`.
  - `journal_state(state) -> dict` (`state["brain"]["journal"]`: `studying`, `tried`, `words`, `unphrased`); `learned(db) -> list[(thing, at)]`; `learn_lesson(state, context, at, thing) -> bool`; `taught(db, thing) -> bool`; `note_sights(state, context, at)`; `observe_journal(state, step, context, at)` (from `brain.observe_step`; a `wait` of the `investigate` purpose ends a look: Task 2).
  - `Situation.lessons -> tuple[str, ...]` (read once per Situation). `world.ROUTINE_EVENTS` gains `"learned"`.
  - `test_survival_journal.Studying` (a test case: a pet on the flat meadow whose curiosity is tended, worldgen patched to put gravel at (6, 0, 0) and (7, 0, 0)), `MEADOW`, `FLAT`, `gravel_shore`, for Tasks 2 and 7.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_journal.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose)
from backend.survival.curiosity import curiosity_state
from backend.survival.journal import NEW_LESSON, journal_state, learn_lesson, observe_journal
from backend.survival.memory import known, places, remember
from backend.survival.once import forget_logged
from backend.tests.test_survival_building import World

MEADOW = lambda x, z, seed: "meadow"  # noqa: E731
FLAT = lambda x, z, seed: 0  # noqa: E731


def gravel_shore(x, z, seed):
    return "gravel" if 6 <= x <= 7 and z == 0 else "grass"


class Studying(unittest.TestCase):
    """A pet on the flat meadow whose curiosity the tick already tends, where worldgen would put
    gravel at (6, 0, 0) and (7, 0, 0)."""

    def setUp(self):
        for name, value in (("backend.survival.journal.biome_at", MEADOW),
                            ("backend.survival.journal.terrain_height", FLAT),
                            ("backend.survival.journal.surface_material", gravel_shore),
                            ("backend.survival.journal.natural_plants", lambda *args: []),
                            ("backend.survival.journal.SEA_LEVEL", 0)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.world = World({"stone_pickaxe": 1})
        self.context = self.world.context()
        curiosity_state(self.world.state, 0.0)


class JournalTests(Studying):
    def test_what_it_digs_or_lays_bare_it_learns_at_once(self):
        self.world.grid.put(3, -1, 1, "coal_ore")
        before = self.world.state["brain"]["curiosity"]["value"]
        observe_journal(self.world.state, {"kind": "mine", "target": {"x": 3, "y": 0, "z": 1}, "block": "gravel"},
                        self.context, 5.0)
        self.assertEqual(known(self.world.db, "lesson"), ["coal_ore", "gravel"])
        self.assertEqual([text for _, kind, text in self.context.events if kind == "learned"],
                         ["Pip learned that gravel sometimes hides flint.",
                          "Pip learned that coal burns: a coal and a stick make four torches."])
        self.assertEqual(self.world.state["brain"]["curiosity"]["value"], before - 2 * NEW_LESSON)
        self.assertEqual(journal_state(self.world.state)["unphrased"], ["gravel", "coal_ore"])
        self.assertEqual(self.world.situation().lessons, ("coal_ore", "gravel"))
        self.assertIn("discovery", self.world.state["brain"]["pending"]["reasons"])  # gravel unlocks flint
        self.assertFalse(learn_lesson(self.world.state, self.context, 6.0, "gravel"))  # once only
        self.assertFalse(learn_lesson(self.world.state, self.context, 6.0, "stone"))  # no lesson for stone

    def test_a_walk_teaches_the_biome_and_landmarks_and_notes_what_to_study_later(self):
        remember(self.world.db, "water", (4, 0, 4), 0.0)
        self.world.state["position"] = {"x": 0.0, "y": 1.0, "z": 0.0}
        observe_journal(self.world.state, {"kind": "walk", "path": []}, self.context, 5.0)
        self.assertEqual(known(self.world.db, "lesson"), ["lake", "meadow"])
        self.assertEqual(places(self.world.db, ("sight",)), [])  # the worldgen's gravel is not in this grid
        self.world.grid.put(6, 0, 0, "gravel")
        for at in (6.0, 7.0):
            observe_journal(self.world.state, {"kind": "walk", "path": []}, self.context, at)
        self.assertEqual([(place["note"], place["x"], place["z"]) for place in places(self.world.db, ("sight",))],
                         [("gravel", 6, 0)])  # one sight of each kind
        learn_lesson(self.world.state, self.context, 8.0, "gravel")
        self.assertEqual(places(self.world.db, ("sight",)), [])  # learned: no longer a sight

    def test_before_the_tick_tends_curiosity_the_journal_waits(self):
        del self.world.state["brain"]["curiosity"]
        observe_journal(self.world.state, {"kind": "walk", "path": []}, self.context, 5.0)
        self.assertEqual((known(self.world.db, "lesson"), self.context.events), ([], []))

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        forget_logged()
        with patch("backend.survival.journal.note_sights", side_effect=RuntimeError("boom")), \
                self.assertLogs("backend.survival.journal", level="ERROR") as logs:
            for at in (1.0, 2.0):
                observe_journal(self.world.state, {"kind": "walk", "path": []}, self.context, at)
        self.assertEqual(len(logs.output), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_journal.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.journal'`

- [ ] **Step 3: The journal**

Create `backend/survival/journal.py`:

```python
"""The knowledge journal (L4b, the owner's day-17 note: "I want it to be more curious and
constantly exploring and trying to undestand the world").

The first time Mimo meets a kind of block, plant, creature, biome or landmark that the rules table
(LESSONS) has a lesson for, it studies it and learns what it teaches: "gravel sometimes hides
flint", "skitters come out of caves at night". A lesson is remembered in memory_knowledge (fact
"lesson", with when), logged as a routine "learned" event ("Pip learned that gravel sometimes hides
flint.") and is a discovery for curiosity (NEW_LESSON); one that unlocks something asks for a new
choice. The journal starts with curiosity, once the tick first tends it (`observe_journal`, from
brain.observe_step, does nothing before). Studying takes one of three forms:
- Mimo learns at once what it meets right there: a kind of block it digs (the sample is in its
  arms), an ore or lava its digging lays bare beside it, the biome it walks into, and a cave mouth,
  sinkhole or lake it walks up to (a remembered cave or water place within LANDMARK_NEAR blocks).
- What it only sees from a walk it goes back to: after each walk it looks over the ground around
  it (every other column within SIGHT_RADIUS) for surface blocks with a lesson (gravel, sand, snow,
  mud, moss) and the plants too (sugar cane, pumpkins, melons, brown mushrooms, cactus), and
  remembers the first of each kind as a "sight" place, noted with what it is.
- The `investigate` purpose walks up to the nearest thing it has not learned about yet within
  INVESTIGATE_REACH blocks (a sight, or a creature of a kind it met, curiosity's "creature" facts,
  within CREATURE_SIGHT), looks it over and takes a sample: it mines a block it can dig (never
  something it built or tends, and never with water over it), or watches a creature for
  WATCH_SECONDS; a plant it looks over. The lesson is learned when the look (a wait of
  LOOK_SECONDS, or the watch) ends. A thing an investigation failed on is left alone for TRIED_FOR.
  investigate is day work in the work band: 40 plus a quarter of curiosity, minus late.

Knowledge unlocks behaviour, so learning has a purpose (Situation.lessons): gather_flint digs
gravel only once Mimo learned that gravel hides flint, and mine_ore goes after gold and diamonds
only once it has seen their ore.

Jev may phrase a lesson's journal line in Mimo's voice. Jev's API answers choices, so each lesson
carries a few phrasings (`lines`) and the worker asks Jev to choose the one that fits (never in the
tick or in tests without a fake; backend.survival.choosing). Until then the journal shows the fact.
The brain keeps state["brain"]["journal"]: {"studying": {"thing", "cell"} or None, "tried": {thing:
server time}, "words": {thing: the line Jev chose}, "unphrased": [things learned and not yet
phrased]}.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, biome_at, surface_material, terrain_height
from backend.survival.clock import DAY_SECONDS
from backend.survival.curiosity import discovered
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, forget, know, places, remember
from backend.survival.once import log_once
from backend.survival.senses import natural_plants
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain, mark_trigger

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

FACT = "lesson"  # the memory_knowledge fact for a lesson learned
NEW_LESSON = 5.0  # curiosity a lesson takes away
INVESTIGATE_REACH = 32.0
CREATURE_SIGHT = 24.0
WATCH_REACH = 4.0
LOOK_SECONDS = 4.0  # game seconds Mimo looks a thing over
WATCH_SECONDS = 8.0  # game seconds it watches a creature
TRIED_FOR = DAY_SECONDS / 2  # game seconds a thing an investigation failed on is left alone
SIGHT_RADIUS = 6  # columns this far around the end of a walk are looked over
PLANT_SIGHT = 8.0
LANDMARK_NEAR = 8.0


@dataclass(frozen=True)
class Lesson:
    thing: str  # a block, plant, creature or biome name, or a landmark ("cave_mouth", "sinkhole", "lake")
    kind: str  # "block", "plant", "creature", "biome" or "landmark"
    words: str  # "gravel", "a sheep"
    fact: str  # "Gravel sometimes hides flint."
    unlocks: str = ""  # what it lets Mimo do: "digs gravel for flint"
    lines: tuple[str, ...] = ()  # the journal line in Mimo's voice, for Jev to choose among


LESSONS: dict[str, Lesson] = {}


def teach(*lessons: Lesson) -> None:
    for lesson in lessons:
        LESSONS[lesson.thing] = lesson


teach(
    Lesson("gravel", "block", "gravel", "Gravel sometimes hides flint.", "digs gravel for flint",
           ("Dig enough gravel and a flint turns up. Arrows!", "Gravel crunches, and there was flint inside!")),
    Lesson("sand", "block", "sand", "Sand lies in the desert and under the lakes, and cactus grows on it.", "",
           ("Sand everywhere in the desert, and under the water too.", "Soft sand. Cactus likes it.")),
    Lesson("snow", "block", "snow", "Snow lies on the cold taiga and high in the mountains.", "",
           ("Cold, white and crunchy: snow.", "Snow only lies where it is cold.")),
    Lesson("mud", "block", "mud", "Mud lies wet in the swamp.", "",
           ("Squelch. The swamp is all mud.", "Mud, wet and sticky, all over the swamp.")),
    Lesson("moss", "block", "moss", "Moss grows on the forest floor.", "",
           ("Soft green moss under the trees.", "The forest floor is mossy in places.")),
    Lesson("coal_ore", "block", "coal ore", "Coal burns: a coal and a stick make four torches.", "",
           ("One coal and one stick: four torches!", "Coal is for light. I'll keep some.")),
    Lesson("iron_ore", "block", "iron ore", "Iron ore needs a stone pickaxe, and a furnace turns it into iron.", "",
           ("Iron! It needs a stone pickaxe and a hot furnace.", "Iron ore: dig it with stone, melt it in a furnace.")),
    Lesson("gold_ore", "block", "gold ore", "Gold lies deep, takes an iron pickaxe to dig and a furnace to melt.",
           "goes after gold",
           ("Gold, deep down! An iron pickaxe will get it.", "Shiny gold in the rock. I'll be back.")),
    Lesson("diamond_ore", "block", "diamond ore", "Diamonds lie deepest of all, and an iron pickaxe digs them.",
           "goes after diamonds",
           ("A diamond! The deepest treasure of all.", "Diamonds sparkle down here. Iron will dig them.")),
    Lesson("lava", "block", "lava", "Lava glows in the dark caves, and it burns whatever falls in.", "",
           ("Lava lights up the caves. Never, ever step in it.", "Glowing, bubbling lava. Stay well back.")),
    Lesson("sugar_cane", "plant", "sugar cane", "Sugar cane grows only beside water.", "",
           ("Sugar cane, right at the water's edge.", "Tall canes, and always by the water.")),
    Lesson("pumpkin", "plant", "a pumpkin", "Pumpkins grow wild in the grass.", "",
           ("A wild pumpkin, big and round!", "Pumpkins just grow here on their own.")),
    Lesson("melon", "plant", "a melon", "Melons grow wild in the grass.", "",
           ("A wild melon. Sweet!", "Melons grow on their own out here.")),
    Lesson("brown_mushroom", "plant", "a brown mushroom", "Brown mushrooms grow in the shade.", "",
           ("Brown mushrooms like the shade.", "Little brown mushrooms, hiding in the shadows.")),
    Lesson("cactus", "plant", "a cactus", "Cactus grows only on sand, and it pricks.", "",
           ("Ouch, prickly! Cactus only grows on sand.", "A cactus. Look, don't touch.")),
    Lesson("rabbit", "creature", "a rabbit", "Rabbits are quick, and four of their hides make leather.", "",
           ("Rabbits are so fast! Their hides make leather.", "A rabbit. Four hides and I'd have leather.")),
    Lesson("chicken", "creature", "a chicken",
           "Chickens drop feathers, and a feather, a flint and a stick make arrows.", "",
           ("Chickens drop feathers. Feathers make arrows fly!", "Feathers from chickens, for my arrows.")),
    Lesson("sheep", "creature", "a sheep", "Sheep give mutton and wool.", "",
           ("Sheep are fluffy: wool, and mutton too.", "Woolly sheep, grazing. Mutton for later.")),
    Lesson("cow", "creature", "a cow", "Cows give beef, and leather for a cap and a tunic.", "",
           ("Cows: beef, and leather for armor.", "A big cow. Leather would make a tunic.")),
    Lesson("fish", "creature", "a fish", "Fish swim in the lakes and rivers.", "",
           ("Fish, darting in the water!", "There are fish in the water here.")),
    Lesson("gloomling", "creature", "a gloomling",
           "Gloomlings come out in the dark and hit hard; light keeps them away.",
           "", ("Gloomlings hate the light. Torches keep them off.", "A gloomling! They come with the dark.")),
    Lesson("skitter", "creature", "a skitter", "Skitters come out of caves at night.", "",
           ("Skitters crawl out of the caves at night.", "Skitters live in the caves. Careful after dark.")),
    Lesson("meadow", "biome", "a meadow", "Meadows are open grass, easy to walk and to build on.", "",
           ("Open meadow, easy to walk, good to build on.", "A meadow: flat, grassy and wide.")),
    Lesson("forest", "biome", "a forest", "Forests are full of oak for wood.", "",
           ("Oaks everywhere! Plenty of wood.", "A forest: all the wood I could want.")),
    Lesson("birch_forest", "biome", "a birch forest", "Birch forests grow pale birch wood.", "",
           ("Pale birch trees, all in a row.", "Birch wood grows here, white and straight.")),
    Lesson("taiga", "biome", "the taiga", "The taiga is cold, with spruce, snow and gravel.", "",
           ("The taiga: cold, snowy, full of spruce.", "Spruce and snow and gravel. Brr, the taiga.")),
    Lesson("swamp", "biome", "a swamp", "Swamps are wet and muddy.", "",
           ("A swamp, all mud and puddles.", "Wet feet in the swamp.")),
    Lesson("desert", "biome", "a desert", "The desert is dry sand where cactus grows and little else.", "",
           ("Hot, dry desert. Not much to eat here.", "Sand and cactus as far as I can see.")),
    Lesson("alpine", "biome", "the mountains", "The mountains are high and cold, with gravel in their scree.", "",
           ("Up in the mountains, cold and high.", "Mountains! Snowy tops and gravel slopes.")),
    Lesson("cave_mouth", "landmark", "a cave mouth",
           "Cave mouths lead down into the dark, where ores show in the walls.",
           "", ("A cave mouth. Ores hide in the dark down there.", "The cave goes down and down.")),
    Lesson("sinkhole", "landmark", "a sinkhole", "Sinkholes drop straight down into the caves.", "",
           ("A sinkhole, straight down into the caves!", "Careful: this hole drops right into a cave.")),
    Lesson("lake", "landmark", "a lake", "Lakes hold fish, and gravel lines their beds.", "",
           ("A lake! Fish in it, gravel under it.", "Water, fish, and gravel on the bottom.")),
)
SURFACE = tuple(name for name, lesson in LESSONS.items() if lesson.kind == "block")
PLANTS = tuple(name for name, lesson in LESSONS.items() if lesson.kind == "plant")
LANDMARKS = {"mouth": "cave_mouth", "sinkhole": "sinkhole"}


def journal_state(state: dict) -> dict:
    """The brain's journal, with the fields a world from before L4b lacks."""
    journal = ensure_brain(state).setdefault("journal", {})
    journal.setdefault("studying", None)
    journal.setdefault("tried", {})
    journal.setdefault("words", {})
    journal.setdefault("unphrased", [])
    return journal


def learned(db) -> list[tuple[str, float]]:
    """The lessons Mimo learned, (thing, when), first first."""
    rows = db.execute("SELECT subject, learned_at FROM memory_knowledge WHERE fact=? ORDER BY learned_at, subject",
                      (FACT,)).fetchall()
    return [(row[0], row[1]) for row in rows]


def learn_lesson(state: dict, context: ActionContext, at: float, thing: str) -> bool:
    """Learn the lesson `thing` teaches, the first time: remembered, logged, a discovery for
    curiosity, and a new choice asked for when it unlocks something. True the first time."""
    lesson, db = LESSONS.get(thing), context.db
    if lesson is None or db is None or not know(db, thing, FACT, at):
        return False
    fact = lesson.fact
    context.events.append((at, "learned", f"{state['name']} learned that {fact[:1].lower()}{fact[1:]}"))
    journal = journal_state(state)
    journal["unphrased"] = [*journal["unphrased"], thing]
    for place in places(db, ("sight",)):
        if place["note"] == thing:
            forget(db, "sight", cell_of(place))
    discovered(state, at, NEW_LESSON)
    if lesson.unlocks:
        mark_trigger(state, "discovery", at)
    return True


# Meeting things --------------------------------------------------------------------------------

def taught(db, thing: str) -> bool:
    return thing in LESSONS and db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact=?",
                                           (thing, FACT)).fetchone() is not None


def note_sights(state: dict, context: ActionContext, at: float) -> None:
    """Look over the ground around Mimo after a walk: the first of each kind of surface block or
    plant with a lesson it has not learned is remembered as a sight."""
    db, seed = context.db, state["world_seed"]
    x, _, z = as_cell(state["position"])
    sighted = {place["note"] for place in places(db, ("sight",))}
    fresh: dict[str, Cell] = {}
    for dx in range(-SIGHT_RADIUS, SIGHT_RADIUS + 1, 2):
        for dz in range(-SIGHT_RADIUS, SIGHT_RADIUS + 1, 2):
            gx, gz = x + dx, z + dz
            height = terrain_height(gx, gz, seed)
            material = surface_material(gx, gz, seed) if height >= SEA_LEVEL else ""
            if material in SURFACE and context.grid.material(gx, height, gz) == material:
                fresh.setdefault(material, (gx, height, gz))
    for cell in natural_plants(seed, x, z, PLANT_SIGHT, PLANTS):
        material = context.grid.material(*cell)
        if material in PLANTS:
            fresh.setdefault(material, cell)
    for thing, cell in sorted(fresh.items()):
        if thing not in sighted and not taught(db, thing):
            remember(db, "sight", cell, at, thing)


def observe_journal(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After a finished step (brain.observe_step): what Mimo learns there and then, what it sees to
    study later, and the end of a look or a watch. The journal starts with curiosity, once the tick
    first tends it (curiosity.tend_curiosity)."""
    db = context.db
    if db is None or "curiosity" not in ensure_brain(state):
        return
    try:
        kind = step["kind"]
        journal = journal_state(state)
        if kind == "mine":
            cell = as_cell(step["target"])
            learn_lesson(state, context, at, step.get("block", ""))
            x, y, z = cell
            for near in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)):
                material = context.grid.material(*near)
                if material == "lava" or material.endswith("_ore"):
                    learn_lesson(state, context, at, material)
        elif kind in ("walk", "swim"):
            x, _, z = as_cell(state["position"])
            learn_lesson(state, context, at, biome_at(x, z, state["world_seed"]))
            for place in places(db, ("cave", "water"), around=(x, 0, z), reach=LANDMARK_NEAR):
                if math.hypot(place["x"] - x, place["z"] - z) <= LANDMARK_NEAR:
                    thing = "lake" if place["kind"] == "water" else LANDMARKS.get(place["note"], "")
                    learn_lesson(state, context, at, thing)
            note_sights(state, context, at)
        elif kind == "wait" and step.get("purpose") == "investigate" and journal["studying"]:
            learn_lesson(state, context, at, journal["studying"]["thing"])
            journal["studying"] = None
    except Exception as error:
        log_once(logger, "journal", error)
```

In `backend/survival/situation.py`, replace:

```python
        return tuple(memory.known(self.db, "poisonous")) if self.db is not None else ()
```

with:

```python
        return tuple(memory.known(self.db, "poisonous")) if self.db is not None else ()

    @cached_property
    def lessons(self) -> tuple[str, ...]:
        """L4b: the lessons Mimo learned (backend.survival.journal); what it knows unlocks work."""
        return tuple(memory.known(self.db, "lesson")) if self.db is not None else ()
```

In `backend/survival/world.py`, replace:

```python
                            "hunt", "hurt", "fight", "threat"})
```

with:

```python
                            "hunt", "hurt", "fight", "threat", "learned"})
```

In `backend/survival/brain.py`, replace:

```python
(backend.survival.curiosity) grows after each vitals step and falls with each discovery a
finished step makes.
"""
```

with:

```python
(backend.survival.curiosity) grows after each vitals step and falls with each discovery a
finished step makes.
L4b: each finished step also feeds the knowledge journal (backend.survival.journal): what Mimo
learns there and then, the things it sees to study later, and the end of a look.
"""
```

and replace:

```python
from backend.survival.curiosity import note_discoveries, tend_curiosity
```

with:

```python
from backend.survival.curiosity import note_discoveries, tend_curiosity
from backend.survival.journal import observe_journal
```

and replace:

```python
    look_after(state, step, context, at)
    learn_from_step(state, step, context, at)
```

with:

```python
    look_after(state, step, context, at)
    observe_journal(state, step, context, at)
    learn_from_step(state, step, context, at)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_journal.py"`
Expected: `Ran 4 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1036 tests` … `OK` (4 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 6 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/journal.py backend/survival/situation.py backend/survival/world.py backend/survival/brain.py backend/tests/test_survival_journal.py
git commit -m "feat: a knowledge journal: what Mimo digs, lays bare, walks into or walks up to it learns, and what it sees it notes to study" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Taking a closer look: the investigate purpose

What Mimo only saw from a walk, and the creatures it met, it goes back to: it walks up, takes a sample (mines a block it can dig, or watches a creature) and looks it over, and then it learns the lesson (resolution 4).

**Files:**
- Modify: `backend/survival/journal.py` (its imports; append the investigate section), `backend/survival/purposes.py` (its docstring's score bands)
- Test: `backend/tests/test_survival_investigate.py`

**Interfaces:**
- Consumes: Task 1 (`journal_state`, `LESSONS`, the constants, `observe_journal`'s end of a look, `Situation.lessons`, `test_survival_journal.Studying`); L4a's `curiosity.seen` (the kinds of creature Mimo met), `value_of`; `foraging.reach_steps`, `whole_walk`; `crafting.can_harvest`; `structures.reserved`; `senses.near_failure`; `creatures.table.dead`; `purposes.Purpose`, `register`, `late_penalty`.
- Produces:
  - `journal.Curio(thing, cell, creature=False)`; `curios(s) -> list[Curio]` (nearest first, once per Situation); `lessons_of(s) -> set[str]`; `tried_lately(s, thing) -> bool`; `note_failure(state, at)`; `diggable(s, cell) -> bool`.
  - The purpose `investigate` ("take a closer look"): valid by day with a curio; score 40 + curiosity / 4 − late; one batch.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_investigate.py`:

```python
import math
import unittest

from backend.survival.journal import curios, journal_state, observe_journal
from backend.survival.memory import know, known, places, remember
from backend.survival.purposes import PURPOSES
from backend.tests.test_survival_journal import Studying


class Herd:
    """Creatures that only answer who is near, where."""

    def __init__(self, *creatures):
        self.creatures = creatures

    def near(self, x, z, reach):
        return [{"kind": kind, "x": cx, "y": 1.0, "z": cz, "state": {}} for kind, cx, cz in self.creatures
                if math.hypot(cx - x, cz - z) <= reach]


class InvestigateTests(Studying):
    def test_it_walks_up_takes_a_sample_looks_it_over_and_then_learns(self):
        self.world.grid.put(6, 0, 0, "gravel")
        remember(self.world.db, "sight", (6, 0, 0), 0.0, "gravel")
        s = self.world.situation()
        investigate = PURPOSES["investigate"]
        self.assertTrue(investigate.valid(s))
        self.assertEqual(investigate.score(s), 50.0)  # 40 and a quarter of curiosity (40)
        self.assertIn("gravel 5 blocks away", investigate.facts(s))
        steps = investigate.plan(s, self.context)
        self.assertEqual(steps, [{"kind": "walk", "target": [6, 0, 0], "reach": 2.0, "whole": True},
                                 {"kind": "mine", "target": [6, 0, 0]}, {"kind": "wait", "seconds": 4.0}])
        self.assertEqual(journal_state(self.world.state)["studying"], {"thing": "gravel", "cell": [6, 0, 0]})
        observe_journal(self.world.state, {"kind": "wait", "purpose": "investigate"}, self.context, 9.0)
        self.assertEqual(known(self.world.db, "lesson"), ["gravel"])
        self.assertEqual(places(self.world.db, ("sight",)), [])
        self.assertFalse(investigate.valid(self.world.situation()))

    def test_a_sight_that_is_gone_is_not_worth_the_walk(self):
        remember(self.world.db, "sight", (6, 0, 0), 0.0, "gravel")  # the grid holds grass there
        self.assertEqual(curios(self.world.situation()), [])

    def test_creatures_it_met_are_watched_and_a_failed_look_leaves_the_thing_alone(self):
        self.world.grid.herd = Herd(("sheep", 12.0, 1.0), ("cow", 30.0, 1.0))
        know(self.world.db, "sheep", "creature", 0.0)
        know(self.world.db, "cow", "creature", 0.0)
        s = self.world.situation()
        self.assertEqual([(curio.thing, curio.cell) for curio in curios(s)], [("sheep", (12, 1, 1))])  # cow: too far
        self.assertEqual(PURPOSES["investigate"].plan(s, self.context),
                         [{"kind": "walk", "target": [12, 1, 1], "reach": 4.0, "whole": True},
                          {"kind": "wait", "seconds": 8.0}])
        self.world.state["brain"]["replans"] = 1  # the walk failed
        self.assertEqual(PURPOSES["investigate"].plan(self.world.situation(), self.context), [])
        self.assertEqual(curios(self.world.situation()), [])  # the sheep is left alone for half a day


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_investigate.py"`
Expected: ERROR: `ImportError: cannot import name 'curios' from 'backend.survival.journal'`

- [ ] **Step 3: investigate**

In `backend/survival/journal.py`, replace:

```python
import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, biome_at, surface_material, terrain_height
from backend.survival.clock import DAY_SECONDS
from backend.survival.curiosity import discovered
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, forget, know, places, remember
from backend.survival.once import log_once
from backend.survival.senses import natural_plants
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain, mark_trigger
```

with:

```python
import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.services.crafting import can_harvest
from backend.services.worldgen import SEA_LEVEL, biome_at, surface_material, terrain_height
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.table import dead
from backend.survival.curiosity import discovered, seen, value_of
from backend.survival.foraging import reach_steps, whole_walk
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, forget, know, places, remember
from backend.survival.once import log_once
from backend.survival.purposes import Purpose, late_penalty, register
from backend.survival.senses import natural_plants, near_failure
from backend.survival.situation import Situation
from backend.survival.steps import as_cell
from backend.survival.structures import reserved
from backend.survival.triggers import ensure_brain, mark_trigger
```

In `backend/survival/journal.py`, append:

```python


# investigate -----------------------------------------------------------------------------------

def note_failure(state: dict, at: float) -> None:
    """An investigation failed: what it was after is left alone for a while."""
    journal = journal_state(state)
    if journal["studying"]:
        journal["tried"] = {**journal["tried"], journal["studying"]["thing"]: at}
        journal["studying"] = None


@dataclass(frozen=True)
class Curio:
    thing: str
    cell: Cell
    creature: bool = False


def lessons_of(s: Situation) -> set[str]:
    return set(s.lessons)


def tried_lately(s: Situation, thing: str) -> bool:
    tried = (s.brain.get("journal") or {}).get("tried", {}).get(thing)
    return tried is not None and (s.at - tried) * s.scale < TRIED_FOR


def curios(s: Situation) -> list[Curio]:
    """What Mimo could go and study now, nearest first: sights within INVESTIGATE_REACH that are
    still there, and creatures of kinds it met but has not studied, within CREATURE_SIGHT."""
    def look() -> list[Curio]:
        known_now = lessons_of(s)
        found = []
        for place in s.places:
            thing, cell = place["note"], cell_of(place)
            if (place["kind"] != "sight" or thing not in LESSONS or thing in known_now or tried_lately(s, thing)
                    or s.distance(cell) > INVESTIGATE_REACH or s.grid.material(*cell) != thing
                    or near_failure(s.state, cell)):
                continue
            found.append(Curio(thing, cell))
        unmet = {kind for kind in seen(s, "creature") if kind in LESSONS and kind not in known_now
                 and not tried_lately(s, kind)}
        herd = s.grid.herd
        if unmet and herd is not None:
            x, _, z = s.here
            for creature in herd.near(x, z, CREATURE_SIGHT):
                if creature["kind"] in unmet and not dead(creature) and "x" in creature:
                    cell = (round(creature["x"]), round(creature.get("y", s.here[1])), round(creature["z"]))
                    found.append(Curio(creature["kind"], cell, creature=True))
                    unmet.discard(creature["kind"])
        return sorted(found, key=lambda curio: (s.distance(curio.cell), curio.thing))
    return s.sensed("curios", look)


def diggable(s: Situation, cell: Cell) -> bool:
    """A block Mimo may take a sample of: one it can harvest with what it carries, with no water
    over it, that it neither built nor tends."""
    x, y, z = cell
    material = s.grid.material(*cell)
    return (can_harvest(material, s.inventory) and s.grid.material(x, y + 1, z) != "water"
            and not reserved(s.grid, cell))


def investigate_valid(s: Situation) -> bool:
    return not s.night and bool(curios(s))


def investigate_score(s: Situation) -> float:
    return max(0.0, 40.0 + value_of(s.brain) / 4 - late_penalty(s))


def plan_investigate(s: Situation, context: ActionContext) -> list[dict]:
    """Walk up to the nearest curio, sample it and look it over. One batch: once it is done the
    lesson is learned (observe_journal) and the purpose ends."""
    if s.brain["replans"] > 0:  # the walk or the sample failed: leave that thing alone for a while
        note_failure(s.state, s.at)
        return []
    if s.brain["batches"] > 0 or not curios(s):
        return []
    curio = curios(s)[0]
    journal_state(s.state)["studying"] = {"thing": curio.thing, "cell": list(curio.cell)}
    if curio.creature:
        walk = [whole_walk(curio.cell, WATCH_REACH)] if s.distance(curio.cell) > WATCH_REACH else []
        return [*walk, {"kind": "wait", "seconds": max(1.0, WATCH_SECONDS / s.scale)}]
    look = {"kind": "wait", "seconds": max(1.0, LOOK_SECONDS / s.scale)}
    sample = [{"kind": "mine", "target": list(curio.cell)}] if LESSONS[curio.thing].kind == "block" and diggable(
        s, curio.cell) else []
    return reach_steps(s, [(curio.cell, [*sample, look])])


def investigate_facts(s: Situation) -> str:
    found = curios(s)
    nearest = found[0]
    return (f"{len(found)} things it has never studied nearby; the nearest is {LESSONS[nearest.thing].words} "
            f"{round(s.distance(nearest.cell))} blocks away; {len(lessons_of(s))} lessons learned")


register(Purpose(
    "investigate", "take a closer look",
    "Walk up to something new nearby, look it over and take a sample, to learn what it is good for.",
    valid=investigate_valid, facts=investigate_facts, score=investigate_score, plan=plan_investigate,
    thoughts=("What is that? I have to look closer.", "I've never seen one of those before.")))
```

In `backend/survival/purposes.py`, replace:

```python
- L2's make_gear sits in the work band: 55-75, 55 plus a tenth of caution and 10 more when a
  creature hurt Mimo in the last game day.
"""
```

with:

```python
- L2's make_gear sits in the work band: 55-75, 55 plus a tenth of caution and 10 more when a
  creature hurt Mimo in the last game day.
- L4b: investigate (backend.survival.journal) sits in the work band, 40-65 by curiosity, minus late.
"""
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_investigate.py"`
Expected: `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1039 tests` … `OK` (3 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 6 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/journal.py backend/survival/purposes.py backend/tests/test_survival_investigate.py
git commit -m "feat: investigate: Mimo walks up to what it has not studied, takes a sample, looks it over and learns" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Knowledge unlocks work: flint, gold and diamonds

Learning has a purpose (resolution 5): Mimo digs gravel for flint only once it learned that gravel hides flint, and goes after gold and diamonds only once it has seen their ore (which teaches it at once, Task 1).

**Files:**
- Modify: `backend/survival/flint.py` (`flint_valid`), `backend/survival/work.py` (`wanted_ores`)
- Modify tests: `backend/tests/test_survival_flint.py`, `backend/tests/test_survival_tiers.py`, `backend/tests/test_survival_life_goals.py` (they learn the lessons first, and show the gates)

**Interfaces:**
- Consumes: Task 1's `Situation.lessons`; `memory.know`.
- Produces: `flint_valid` needs `"gravel"` among the lessons; `wanted_ores` wants `"gold_ore"` and `"diamond_ore"` only with their lessons. `test_survival_flint.situation(..., learned=True)`; `test_survival_tiers.seeing(state, grid, places_seen=())` (a Situation in which Mimo learned about every ore it remembers).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_flint.py`, replace:

```python
from backend.survival.memory import create_memory_tables
```

with:

```python
from backend.survival.memory import create_memory_tables, know
```

and replace:

```python
def situation(inventory, clock=DAY, grid=None):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state, grid or shore(), clock, 0.0, db)
```

with:

```python
def situation(inventory, clock=DAY, grid=None, learned=True):
    """L4b: by default Mimo has learned that gravel hides flint (backend.survival.journal)."""
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    if learned:
        know(db, "gravel", "lesson", 0.0)
    return Situation(state, grid or shore(), clock, 0.0, db)
```

and replace:

```python
        self.assertFalse(flint_purpose.valid(situation({"bow": 1}, NIGHT)))
```

with:

```python
        self.assertFalse(flint_purpose.valid(situation({"bow": 1}, NIGHT)))
        self.assertFalse(flint_purpose.valid(situation({"bow": 1}, learned=False)))  # L4b: gravel's lesson first
```

In `backend/tests/test_survival_tiers.py`, replace:

```python
from backend.survival.grid import Grid
```

with:

```python
from backend.survival.grid import Grid
from backend.survival.memory import know
```

and replace:

```python
def craft_step(recipe):
    return {"kind": "craft", "recipe": recipe}
```

with:

```python
def craft_step(recipe):
    return {"kind": "craft", "recipe": recipe}


def seeing(state, grid, places_seen=()):
    """L4b: a Situation in which Mimo learned about every ore it remembers, by seeing it."""
    s = work_situation(state, grid, places_seen)
    for _, _, ore in places_seen:
        know(s.db, ore, "lesson", 0.0)
    return s
```

and replace:

```python
        want = lambda inventory, known=(): wanted_ores(work_situation(pet(inventory=inventory), ground(), known))
```

with:

```python
        want = lambda inventory, known=(): wanted_ores(seeing(pet(inventory=inventory), ground(), known))
```

and replace:

```python
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8}, both), ("gold_ore", "diamond_ore"))
```

with:

```python
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8}, both), ("gold_ore", "diamond_ore"))
        unseen = work_situation(pet(inventory={"iron_pickaxe": 1, "coal": 8}), ground(), both)
        self.assertEqual(wanted_ores(unseen), ())  # L4b: remembered, but never learned about
```

and replace:

```python
        self.assertFalse(PURPOSES["mine_ore"].valid(work_situation(pet(inventory={"stone_pickaxe": 1, "coal": 8}), grid, seen)))
        s = work_situation(pet(inventory={"iron_pickaxe": 1, "coal": 8, "diamond": 2}), grid, seen)
```

with:

```python
        self.assertFalse(PURPOSES["mine_ore"].valid(seeing(pet(inventory={"stone_pickaxe": 1, "coal": 8}), grid, seen)))
        s = seeing(pet(inventory={"iron_pickaxe": 1, "coal": 8, "diamond": 2}), grid, seen)
```

In `backend/tests/test_survival_life_goals.py`, replace:

```python
from backend.survival.memory import mark_explored, places, remember, structures
```

with:

```python
from backend.survival.memory import know, mark_explored, places, remember, structures
```

and replace:

```python
        remember(world.db, "ore", (4, -6, 4), 0.0, "diamond_ore")
        self.assertNotIn("diamond_ore", wanted_ores(world.situation()))  # one of the 3 a pickaxe takes
```

with:

```python
        remember(world.db, "ore", (4, -6, 4), 0.0, "diamond_ore")
        know(world.db, "diamond_ore", "lesson", 0.0)  # L4b: it has seen one
        self.assertNotIn("diamond_ore", wanted_ores(world.situation()))  # one of the 3 a pickaxe takes
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_flint.py"` and `python3 -m unittest discover -s backend/tests -p "test_survival_tiers.py"`
Expected: FAIL: `test_wanted_by_day_with_a_bow_or_its_string_and_little_flint` (`AssertionError: True is not false`) and `test_gold_and_diamond_are_noticed_and_wanted_once_mimo_has_an_iron_pickaxe` (`Tuples differ: ('gold_ore', 'diamond_ore') != ()`)

- [ ] **Step 3: The gates**

In `backend/survival/flint.py`, replace:

```python
def flint_valid(s: Situation) -> bool:
    return not s.night and wants_flint(s) and bool(gravel_near(s))
```

with:

```python
def flint_valid(s: Situation) -> bool:
    """L4b: only once Mimo learned that gravel hides flint (backend.survival.journal)."""
    return not s.night and "gravel" in s.lessons and wants_flint(s) and bool(gravel_near(s))
```

and replace:

```python
flint and fewer arrows than make_gear keeps (backend.survival.creatures.gear). Gravel lines lake and
```

with:

```python
flint and fewer arrows than make_gear keeps (backend.survival.creatures.gear), and (L4b) only once
it learned that gravel hides flint (backend.survival.journal). Gravel lines lake and
```

In `backend/survival/work.py`, replace:

```python
    if (TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["gold_pickaxe"]
            and enough_known(s, "gold_ore", s.count("gold_ore", "gold_ingot"))):
        wanted.append("gold_ore")
    if TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["diamond_pickaxe"] and enough_known(s, "diamond_ore", s.count("diamond")):
        wanted.append("diamond_ore")
```

with:

```python
    if (TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["gold_pickaxe"] and "gold_ore" in s.lessons
            and enough_known(s, "gold_ore", s.count("gold_ore", "gold_ingot"))):
        wanted.append("gold_ore")
    if (TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["diamond_pickaxe"] and "diamond_ore" in s.lessons
            and enough_known(s, "diamond_ore", s.count("diamond"))):
        wanted.append("diamond_ore")
```

and replace:

```python
    (`enough_known`; L4: any one it knows while diamonds are its goal)."""
```

with:

```python
    (`enough_known`; L4: any one it knows while diamonds are its goal) and (L4b) has learned about
    their ore by seeing it (backend.survival.journal)."""
```

and replace:

```python
lie for the pickaxe above it (L3).
```

with:

```python
lie for the pickaxe above it (L3), and has learned about their ore (L4b, backend.survival.journal).
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_flint.py"`, the same for `test_survival_tiers.py`, `test_survival_life_goals.py` and `test_survival_journal.py`
Expected: `OK` for each

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1039 tests` … `OK` (no new tests; three gain a line).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 6 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/flint.py backend/survival/work.py backend/tests/test_survival_flint.py backend/tests/test_survival_tiers.py backend/tests/test_survival_life_goals.py
git commit -m "feat: knowledge unlocks work: gravel is dug for flint once Mimo learned it hides flint, gold and diamonds once it saw their ore" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Jev chooses the journal's lines

Jev phrases each lesson in Mimo's voice by choosing among its lines, in the purpose call it makes anyway (resolution 6). Never in the tick; tests use a recording fake.

**Files:**
- Modify: `backend/survival/models.py` (`JOURNAL_INSTRUCTIONS`), `backend/survival/choosing.py` (the `"journal_line"` question, keeping the line)
- Test: `backend/tests/test_survival_journal_lines.py`

**Interfaces:**
- Consumes: Task 1's `journal.LESSONS`, `journal_state` (`unphrased`, `words`); L4a's `models.jev_answers`, `choosing.prepare`, `decide`, `store_choice`, `route_for`; `test_survival_goal_choice.Recorder`.
- Produces:
  - `models.JOURNAL_INSTRUCTIONS`.
  - `choosing.Ask` gains `lines: tuple[Option, ...] = ()` (the lesson's lines, `line_0` the fact) and `subject: str = ""` (the lesson); `Choice` gains `line: str | None = None` (Jev's pick); `journal_lines(state) -> (lines, subject)` (the oldest lesson waiting); `keep_line(state, ask, choice)`.
  - A purpose call to Jev with a lesson waiting asks `"journal_line"` too and carries `"learned"` (the fact) in its payload.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_journal_lines.py`:

```python
import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.journal import journal_state
from backend.survival.memory import know
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import mark_trigger
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_goal_choice import Recorder

BORN = 1_000_000.0


class JevLineTests(unittest.TestCase):
    """Jev phrases the journal in the purpose call it makes anyway, never in the tick."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(life))
        with self.world.transaction() as db:
            state = read_state(db)
            know(db, "skitter", "lesson", BORN)
            journal_state(state)["unphrased"] = ["skitter"]
            mark_trigger(state, "hello", BORN)
            write_state(db, state)

    def tearDown(self):
        self.directory.cleanup()

    def poll(self, env, http):
        chooser = Chooser(env=env, http=http, executor=InlineExecutor(), rng=random.Random(1), scale=1.0)
        chooser.poll(self.registry, BORN + 5)
        return journal_state(self.world.state())

    def test_a_purpose_call_to_jev_also_chooses_the_journal_line(self):
        jev = Recorder({"answers": {"purpose": {"choice": "rest"}, "journal_line": {"choice": "line_1"}}})
        journal = self.poll({"TYPESAFE_API_KEY": "k"}, jev)
        body = jev.bodies[0]
        self.assertEqual(set(body["questions"]), {"purpose", "journal_line"})
        self.assertEqual(sorted(body["questions"]["journal_line"]["criteria"]), ["line_0", "line_1", "line_2"])
        self.assertEqual(body["state"]["learned"], "Skitters come out of caves at night.")
        self.assertEqual((journal["words"], journal["unphrased"]),
                         ({"skitter": "Skitters crawl out of the caves at night."}, []))

    def test_a_failed_call_leaves_the_lesson_waiting(self):
        jev = Recorder({"answers": {"purpose": {"choice": "rest"}}})  # no line chosen: the call fails
        forget_logged()
        with self.assertLogs("backend.survival.choosing", level="ERROR"):
            journal = self.poll({"TYPESAFE_API_KEY": "k"}, jev)
        self.assertEqual((journal["words"], journal["unphrased"]), ({}, ["skitter"]))

    def test_without_jev_the_lesson_waits_for_its_line(self):
        nobody = Recorder({})
        journal = self.poll({}, nobody)
        self.assertEqual((nobody.bodies, journal["words"], journal["unphrased"]), ([], {}, ["skitter"]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_journal_lines.py"`
Expected: FAIL: `test_a_purpose_call_to_jev_also_chooses_the_journal_line` (`Items in the second set but not the first: 'journal_line'`) and `test_a_failed_call_leaves_the_lesson_waiting` (`no logs of level ERROR or higher triggered on backend.survival.choosing`: no question is asked for the line yet, so nothing fails)

- [ ] **Step 3: The journal line rides on the purpose call**

In `backend/survival/models.py`, replace:

```python
(`jev_answers`, REASON_INSTRUCTIONS).
"""
```

with:

```python
(`jev_answers`, REASON_INSTRUCTIONS). L4b: while a lesson waits for its journal line, a purpose call
to Jev also asks "journal_line" (JOURNAL_INSTRUCTIONS): which of the lesson's phrasings sounds most
like Mimo.
"""
```

and replace:

```python
                       "or what it lacks most. Choose only from the offered reasons.")
```

with:

```python
                       "or what it lacks most. Choose only from the offered reasons.")
# L4b: the line the pet writes in its journal about what it just learned.
JOURNAL_INSTRUCTIONS = ("Choose the line this small survival pet writes in its journal about what it just "
                        "learned (the payload's \"learned\"): the one that sounds most like it, given its traits, "
                        "mood and day. Choose only from the offered lines.")
```

In `backend/survival/choosing.py`, replace:

```python
look for iron, toward iron tools. \"Heading north to look for iron. My pickaxe needs it.\"").
"""
```

with:

```python
look for iron, toward iron tools. \"Heading north to look for iron. My pickaxe needs it.\"").
L4b: the journal. While a lesson Mimo learned waits for its line (backend.survival.journal), a
purpose call to Jev asks a third question, "journal_line": which of the lesson's phrasings, the
plain fact first, sounds most like Mimo. The line Jev chose is kept for the journal; the rules and
Luna leave the lesson waiting for the next Jev call (the journal shows the fact meanwhile). No
call is made for the journal alone.
"""
```

and replace:

```python
from backend.survival.models import (
    GOAL_INSTRUCTIONS, INSTRUCTIONS, JEV_TIMEOUT, LUNA_TIMEOUT, REASON_INSTRUCTIONS, Http, ModelError, ask_jev,
    ask_luna, jev_answers, jev_configured, luna_configured, luna_reflect, post_json,
)
```

with:

```python
from backend.survival.journal import LESSONS, journal_state
from backend.survival.models import (
    GOAL_INSTRUCTIONS, INSTRUCTIONS, JEV_TIMEOUT, JOURNAL_INSTRUCTIONS, LUNA_TIMEOUT, REASON_INSTRUCTIONS, Http,
    ModelError, ask_jev, ask_luna, jev_answers, jev_configured, luna_configured, luna_reflect, post_json,
)
```

and replace:

```python
    kind: str = "purpose"  # L4: or "goal"
```

with:

```python
    kind: str = "purpose"  # L4: or "goal"
    lines: tuple[Option, ...] = ()  # L4b: the journal lines Jev may choose among for `subject`'s lesson
    subject: str = ""
```

and replace:

```python
    trip: Offer | None = None  # L4: explore's reason (trips.Offer)
```

with:

```python
    trip: Offer | None = None  # L4: explore's reason (trips.Offer)
    line: str | None = None  # L4b: the journal line Jev chose (an option's name in Ask.lines)
```

and replace:

```python
    route = route_for(brain, now, env, game_at, steady)
    return Ask(brain["pending"]["id"], route, reflect_for(brain, route, now, env), tuple(choices), payload, now,
               game_at)
```

with:

```python
    route = route_for(brain, now, env, game_at, steady)
    lines, subject = journal_lines(state) if route == "jev" else ((), "")
    if lines:
        payload = {**payload, "learned": LESSONS[subject].fact}
    return Ask(brain["pending"]["id"], route, reflect_for(brain, route, now, env), tuple(choices), payload, now,
               game_at, lines=lines, subject=subject)


def journal_lines(state: dict) -> tuple[tuple[Option, ...], str]:
    """L4b: the phrasings of the oldest lesson still waiting for its journal line, and its name."""
    waiting = [thing for thing in journal_state(state)["unphrased"] if thing in LESSONS]
    if not waiting:
        return (), ""
    lesson = LESSONS[waiting[0]]
    return tuple(Option(f"line_{index}", line, line, lesson.words, 0.0)
                 for index, line in enumerate((lesson.fact, *lesson.lines))), lesson.thing
```

and replace:

```python
    purpose, picker, reason = None, "utility", None
```

with:

```python
    purpose, picker, reason, line = None, "utility", None, None
```

and replace:

```python
            elif ask.route == "jev" and len(reasons) > 1:
                answers = jev_answers(ask.payload, {"purpose": (choices, INSTRUCTIONS),
                                                    "explore_reason": (reasons, REASON_INSTRUCTIONS)}, env, http)
                purpose, reason = answers["purpose"], answers["explore_reason"]
            else:
                purpose = (ask_jev if ask.route == "jev" else ask_luna)(ask.payload, choices, env, http)
```

with:

```python
            elif ask.route == "jev":
                questions = {"purpose": (choices, INSTRUCTIONS)}
                if len(reasons) > 1:
                    questions["explore_reason"] = (reasons, REASON_INSTRUCTIONS)
                if ask.lines:
                    questions["journal_line"] = (list(ask.lines), JOURNAL_INSTRUCTIONS)
                answers = jev_answers(ask.payload, questions, env, http)
                purpose, reason, line = answers["purpose"], answers.get("explore_reason"), answers.get("journal_line")
            else:
                purpose = ask_luna(ask.payload, choices, env, http)
```

and replace:

```python
    return Choice(purpose, picker, thought, calls, "; ".join(errors) or None, trip)
```

with:

```python
    return Choice(purpose, picker, thought, calls, "; ".join(errors) or None, trip, line)
```

and replace:

```python
                log_event(db, now, "purpose", f'{state["name"]} decided to {phrase}{aim}. "{choice.thought}"')
        write_state(db, state)
        return choice.purpose if fresh else None
```

with:

```python
                log_event(db, now, "purpose", f'{state["name"]} decided to {phrase}{aim}. "{choice.thought}"')
        keep_line(state, ask, choice)
        write_state(db, state)
        return choice.purpose if fresh else None


def keep_line(state: dict, ask: Ask, choice: Choice) -> None:
    """L4b: the journal line Jev chose, kept for its lesson (once; a stale ask still counts)."""
    journal = journal_state(state)
    line = next((option.phrase for option in ask.lines if option.name == choice.line), None)
    if line is None or ask.subject not in journal["unphrased"]:
        return
    journal["unphrased"] = [thing for thing in journal["unphrased"] if thing != ask.subject]
    journal["words"] = {**journal["words"], ask.subject: line}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_journal_lines.py"`
Expected: `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1042 tests` … `OK` (3 new; the chooser's older tests, which ask Jev with no lesson waiting, send the same bodies as before).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 6 tests` … `OK` (its fake Jev answers every question it is asked, the journal's too, within the hourly budget).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/models.py backend/survival/choosing.py backend/tests/test_survival_journal_lines.py
git commit -m "feat: Jev chooses the journal's line for each lesson, in the purpose call it makes anyway" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Expeditions: the goal, packing, setting out, staying out and coming home

A curious pet whose needs are met takes an expedition goal: it packs food and torches, sets out past the land it knows along the way with the most new land, stays out for the night and comes home with what it found (resolutions 7–10 and 12). Task 6 digs its camp.

**Files:**
- Create: `backend/survival/expedition.py`
- Modify: `backend/survival/purposes.py` (`AWAY`, `away`, go_home; the docstring), `backend/survival/reflexes.py` (head_home leaves an expedition out), `backend/survival/building.py` (no new home while away), `backend/survival/storage.py` (`KEEPS_MORE`), `backend/survival/curiosity.py` (new ground lowers curiosity by 1), `backend/survival/brain.py` (`tend_expedition` in `notice_step`, `observe_expedition` in `observe_step`)
- Test: `backend/tests/test_survival_expedition.py`

**Interfaces:**
- Consumes: L4a's `goals.Goal`, `Milestone`, `register_goal`, `active`, `adopt_goal`; `trips.Reason`, `register_reason`; `curiosity.CURIOUS`, `RESTLESS`, `needs_met`, `value_of`, `curiosity_state`; `foraging.MORE_FOOD`, `FOOD_WANTED`, `food_points`; `exploring.COMPASS`; `memory.BUILT`, `PATCH`, `explored`, `patch_of`, `places`, `known`, `cell_of`; `work.ore_targets`; `toolmaking.make`, `Short`; `carrying.crafts_fit`; `worldgen.terrain_height`, `SEA_LEVEL`; `purposes.late_day`, `walk_to`, `AT_HOME`; `clock.DAY_SECONDS`; `test_survival_life_goals.built`.
- Produces:
  - The goal `expedition` ("An expedition", repeating), its state `state["brain"]["expedition"]` (resolution 12) and `brain["expedition_at"]`; constants `GOAL = "expedition"`, `REST_DAYS = 2.0`, `RESTLESS_PULL = 110.0`, `PACK_FOOD = 90.0`, `PACK_TORCHES = 4`, `RANGE_MIN, RANGE_MAX = 48.0, 144.0`, `PAST = 48.0`, `REACH_MAX = 200.0`, `FAR_FROM_HOME = 48.0`, `NIGHTS_OUT = 2`, `MAP_WALKS = 8`, `LOW_FOOD = 20.0`, `LOW_HEALTH = 40.0`, `HOME_REACH = 6.0`, `COME_HOME_BATCHES = 6`.
  - `expedition.built_home(db)`, `trek(s)`, `phase_of(s)`, `from_home(s, cell=None)`, `camp_time(s)`, `away(s)`, `explored_range(db, home)`, `heading_of(db, seed, home, reach)`, `ready(s)` (its needs met, or all but hunger with `READY_FOOD = 30.0` of food carried), `campfire_ready(s)` (a campfire or its makings), `packed(s)`, `tend_expedition(state, context, at)`, `should_turn(s, found)`, `observe_expedition(state, step, context, at)`, `trek_value(s, x, z)`, `expedition_view(brain)`; the purposes `pack` and `come_home`; the trip `expedition`.
  - `purposes.AWAY: list` of `(Situation) -> bool` and `purposes.away(s) -> bool`; `storage.KEEPS_MORE: list` of `(Situation, item) -> float` ("food" in hunger points) and `storage.more_kept(s, item)`.
  - `test_survival_expedition.Expedition` (a curious pet with the home `built()` gives it, its clock, `set_out()`, `go(x, z)`), `DUSK`, `NIGHT`, `MORNING`, `PACKED`, `FLAT`, for Task 6.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_expedition.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every goal, purpose and reason)
from backend.survival.curiosity import curiosity_state
from backend.survival.expedition import PACK_FOOD, expedition_view, observe_expedition, tend_expedition, trek_value
from backend.survival.foraging import food_need
from backend.survival.goals import GOALS, adopt_goal, complete, is_open, progress_of
from backend.survival.memory import know, mark_explored
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES
from backend.survival.reflexes import by_name
from backend.survival.storage import more_kept
from backend.survival.trips import REASONS
from backend.tests.test_survival_life_goals import built

DUSK = {"phase": "dusk", "seconds_into_day": 2250.0, "time_scale": 1.0, "day_number": 2}
NIGHT = {"phase": "night", "seconds_into_day": 2500.0, "time_scale": 1.0, "day_number": 2}
MORNING = {"phase": "day", "seconds_into_day": 400.0, "time_scale": 1.0, "day_number": 3}
PACKED = {"bread": 4, "torch": 4, "campfire": 1, "dirt": 4}  # bread restores 25 hunger: 100 in all
FLAT = lambda x, z, seed: 0  # noqa: E731


class Expedition:
    """A pet with a home it built, curious, fed and rested, and the clock it lives by."""

    def __init__(self, inventory=None):
        self.world = built(inventory)
        self.state = self.world.state
        curiosity_state(self.state, 0.0)["value"] = 70.0
        self.clock = self.world.situation().clock

    def situation(self, clock=None):
        return self.world.situation(clock or self.clock)

    def context(self, clock=None):
        context = self.world.context()
        context.clock_at = lambda at: clock or self.clock
        return context

    def tend(self, at, clock=None):
        context = self.context(clock)
        tend_expedition(self.state, context, at)
        return context

    def set_out(self):
        adopt_goal(self.state, "expedition", "utility", "", 1.0)
        self.state["inventory"] = dict(PACKED)
        return self.tend(2.0)

    def go(self, x, z):
        self.state["position"] = {"x": float(x), "y": 1.0, "z": float(z)}


class GoalTests(unittest.TestCase):
    def test_offered_to_a_curious_pet_whose_needs_are_met(self):
        pet = Expedition()
        expedition = GOALS["expedition"]
        self.assertTrue(is_open(pet.situation(), expedition))
        self.assertAlmostEqual(expedition.score(pet.situation()), 96.0)  # 40 and 0.8 of curiosity
        curiosity_state(pet.state, 0.0)["value"] = 80.0
        self.assertAlmostEqual(expedition.score(pet.situation()), 214.0)  # restless: 110 more
        pet.state["vitals"]["hunger"] = 30.0
        self.assertFalse(is_open(pet.situation(), expedition))  # hungry, with nothing to eat
        pet.state["inventory"]["bread"] = 2
        self.assertTrue(is_open(pet.situation(), expedition))  # hungry at dawn, its breakfast in its pack
        pet.state["vitals"]["hunger"] = 100.0
        pet.state["brain"]["expedition_at"] = 0.0  # just back from one
        self.assertFalse(is_open(pet.situation(), expedition))
        curiosity_state(pet.state, 0.0)["value"] = 50.0
        del pet.state["brain"]["expedition_at"]
        self.assertFalse(is_open(pet.situation(), expedition))  # not curious enough

    def test_it_packs_food_torches_and_a_campfire_then_sets_out(self):
        pet = Expedition({"coal": 1, "sticks": 4, "oak_log": 2})
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        pet.tend(2.0)
        self.assertEqual(pet.state["brain"]["expedition"]["phase"], "packing")
        s = pet.situation()
        self.assertEqual(food_need(s), PACK_FOOD)  # nothing carried: a day and a half's worth wanted
        self.assertEqual((more_kept(s, "torch"), more_kept(s, "food")), (4.0, 30.0))  # neither put away nor dropped
        self.assertEqual(PURPOSES["pack"].plan(s, pet.context()),
                         [{"kind": "craft", "recipe": "torch"}, {"kind": "craft", "recipe": "campfire"}])
        self.assertAlmostEqual(progress_of(s, GOALS["expedition"]), 1 / 15)  # only the makings of a campfire yet
        pet.state["inventory"] = dict(PACKED)
        with patch("backend.survival.expedition.terrain_height", FLAT):
            context = pet.tend(3.0)
        trek = pet.state["brain"]["expedition"]
        self.assertEqual((trek["phase"], trek["range"], trek["target"], trek["direction"]), ("out", 48, 96, "east"))
        self.assertEqual(context.events, [(3.0, "expedition", "Pip set out on an expedition to the east.")])
        self.assertAlmostEqual(progress_of(pet.situation(), GOALS["expedition"]), 0.2)  # packed

    def test_it_heads_past_the_lands_it_knows_along_its_heading(self):
        pet = Expedition()
        mark_explored(pet.world.db, [(rx, 0) for rx in range(-12, 0)], 1.0)  # the west is known ground
        with patch("backend.survival.expedition.terrain_height", FLAT):
            pet.set_out()
        s = pet.situation()
        self.assertEqual(REASONS["expedition"].wanted(s), "I want to see what lies past the lands I know")
        self.assertEqual(pet.state["brain"]["expedition"]["direction"], "east")
        self.assertEqual(trek_value(s, 101, 1), (1.0, "land past what it knows"))
        self.assertEqual(trek_value(s, 1, 101), (0.5, "land past what it knows"))  # south: off the heading
        self.assertEqual(trek_value(s, -99, 1), (0.0, ""))
        self.assertEqual(trek_value(s, 31, 1), (0.4, "the way out"))


class AwayTests(unittest.TestCase):
    def setUp(self):
        self.pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            self.pet.set_out()
        self.pet.go(101, 1)

    def test_out_there_it_neither_goes_home_nor_starts_a_home(self):
        s = self.pet.situation(DUSK)
        self.assertFalse(PURPOSES["go_home"].valid(s))
        self.assertFalse(by_name("head_home").trigger(s))
        self.pet.state["inventory"]["cobblestone"] = 60
        self.assertFalse(PURPOSES["build_shelter"].valid(self.pet.situation()))


class HomewardTests(unittest.TestCase):
    def test_after_a_night_out_it_turns_home_and_comes_home_with_its_finds(self):
        pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            pet.set_out()
        trek = pet.state["brain"]["expedition"]
        pet.go(101, 1)
        pet.tend(10.0, DUSK)
        self.assertEqual(trek["far"], 100.0)
        context = pet.context(NIGHT)
        observe_expedition(pet.state, {"kind": "sleep"}, context, 20.0)
        for at in range(21, 29):
            pet.state["brain"]["new_ground_at"] = float(at)
            observe_expedition(pet.state, {"kind": "walk"}, context, float(at))
        self.assertEqual((trek["nights"], trek["walks"]), (1, 8))
        pet.tend(30.0, MORNING)
        self.assertEqual(trek["phase"], "homeward")
        s = pet.situation(MORNING)
        self.assertTrue(PURPOSES["come_home"].valid(s))
        self.assertEqual(PURPOSES["come_home"].plan(s, pet.context(MORNING)),
                         [{"kind": "walk", "target": [1, 1, 1], "reach": 2.0}])
        self.assertTrue(PURPOSES["go_home"].valid(pet.situation(DUSK)) is False)  # caught far out at dusk: it camps
        know(pet.world.db, "gravel", "lesson", 25.0)
        pet.go(2, 1)
        context = pet.tend(40.0, MORNING)
        self.assertEqual(context.events, [(40.0, "expedition", "Pip came home from its expedition: 100 blocks out, "
                                                                "1 night camped, 1 new thing learned.")])
        self.assertTrue(complete(pet.situation(MORNING), GOALS["expedition"]))
        self.assertEqual(expedition_view(pet.state["brain"]),
                         {"phase": "home", "direction": "east", "far": 100, "target": 96, "nights": 1,
                          "camping": False})

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        pet = Expedition()
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        forget_logged()
        with patch("backend.survival.expedition.packed", side_effect=RuntimeError("boom")), \
                self.assertLogs("backend.survival.expedition", level="ERROR") as logs:
            pet.tend(2.0)
            pet.tend(3.0)
        self.assertEqual(len(logs.output), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_expedition.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.expedition'`

- [ ] **Step 3: Staying out, and keeping what it packed**

In `backend/survival/purposes.py`, replace:

```python
def at_home(s: Situation, reach: float = AT_HOME) -> bool:
```

with:

```python
# L4b: functions of the Situation that say Mimo means to stay out tonight (an expedition,
# backend.survival.expedition): go_home and the head_home reflex leave it be, and it builds no new home.
AWAY: list = []


def away(s: Situation) -> bool:
    """Mimo means to stay away from home (AWAY); one that crashes counts as no (logged once)."""
    for check in AWAY:
        try:
            if check(s):
                return True
        except Exception as error:
            log_once(logger, "away", error)
    return False


def at_home(s: Situation, reach: float = AT_HOME) -> bool:
```

and replace:

```python
def go_home_valid(s: Situation) -> bool:
    home = home_of(s)
    return home is not None and s.distance(cell_of(home)) > AT_HOME
```

with:

```python
def go_home_valid(s: Situation) -> bool:
    """Home is known and Mimo is not there, nor means to stay away (L4b: AWAY)."""
    home = home_of(s)
    return home is not None and s.distance(cell_of(home)) > AT_HOME and not away(s)
```

and replace:

```python
- L4b: investigate (backend.survival.journal) sits in the work band, 40-65 by curiosity, minus late.
"""
```

with:

```python
- L4b: investigate (backend.survival.journal) sits in the work band, 40-65 by curiosity, minus late.
- L4b: an expedition's pack is 60 and come_home 75 (backend.survival.expedition). While Mimo means
  to stay out (`AWAY`), go_home is not on offer.
"""
```

In `backend/survival/reflexes.py`, replace:

```python
from backend.survival.purposes import AT_HOME, HOME_RANGE, HOMEWARD, foods, home_of, land_refuge, meal, walk_to
```

with:

```python
from backend.survival.purposes import AT_HOME, HOME_RANGE, HOMEWARD, away, foods, home_of, land_refuge, meal, walk_to
```

and replace:

```python
    if s.brain["purpose"] in ("go_home", "sleep", *AT_HOME_WORK):
        return False
```

with:

```python
    if s.brain["purpose"] in ("go_home", "sleep", *AT_HOME_WORK) or away(s):  # L4b: an expedition stays out
        return False
```

In `backend/survival/building.py`, replace:

```python
from backend.survival.purposes import HOME_RANGE, Purpose, register
```

with:

```python
from backend.survival.purposes import HOME_RANGE, Purpose, away, register
```

and replace:

```python
        design = None if shelter_elsewhere(s) else shelter_design(s)
```

with:

```python
        design = None if shelter_elsewhere(s) or away(s) else shelter_design(s)  # L4b: no new home on an expedition
```

In `backend/survival/storage.py`, replace:

```python
forever. It scores low while Mimo has room and high when it is full.
```

with:

```python
forever. It scores low while Mimo has room and high when it is full.
L4b: an expedition keeps what it packed (`KEEPS_MORE`, backend.survival.expedition): its torches
and a day and a half of food stay with Mimo, neither put away nor dropped.
```

and replace:

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
from backend.survival.housework import chest_key
```

with:

```python
from backend.survival.housework import chest_key
from backend.survival.once import log_once
```

and replace:

```python
    from backend.survival.actions import ActionContext

STORE_FROM = 13
```

with:

```python
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

STORE_FROM = 13
```

and replace:

```python
def chest_spot(s: Situation) -> tuple[int, int, int] | None:
```

with:

```python
# L4b: functions of (Situation, item) giving how many more of an item Mimo keeps on it now, beyond
# what the rules below keep ("food" for hunger points of food): an expedition's torches and food.
KEEPS_MORE: list = []


def more_kept(s: Situation, item: str) -> float:
    """What KEEPS_MORE add for `item`; one that crashes adds nothing (logged once)."""
    total = 0.0
    for extra in KEEPS_MORE:
        try:
            total += float(extra(s, item))
        except Exception as error:
            log_once(logger, "keeps more", error)
    return total


def chest_spot(s: Situation) -> tuple[int, int, int] | None:
```

and replace:

```python
    kept, spare = 0.0, []
    for item in foods(s.inventory, s.poisons):
        if item in RAW_FOODS:
            continue
        count = s.inventory[item]
        keep = 0
        while keep < count and kept < FOOD_WANTED:
```

with:

```python
    kept, spare, wanted = 0.0, [], FOOD_WANTED + more_kept(s, "food")
    for item in foods(s.inventory, s.poisons):
        if item in RAW_FOODS:
            continue
        count = s.inventory[item]
        keep = 0
        while keep < count and kept < wanted:
```

and replace:

```python
    if item == "torch":
        return max(0, len(dark_corners(s)) - s.count("lantern"))
    if item in BUILDING and full(s.inventory):
        return 0
    if item in GEAR_MATERIALS and item not in materials_wanted(s.inventory):
        return 0
    pool = next((pool for pool in WOOD_POOLS if item in pool), None)
    return pooled(s, item, pool) if pool else KEEP[item]
```

with:

```python
    more = round(more_kept(s, item))
    if item == "torch":
        return max(0, len(dark_corners(s)) - s.count("lantern")) + more
    if item in BUILDING and full(s.inventory):
        return more
    if item in GEAR_MATERIALS and item not in materials_wanted(s.inventory):
        return more
    pool = next((pool for pool in WOOD_POOLS if item in pool), None)
    return (pooled(s, item, pool) if pool else KEEP[item]) + more
```

- [ ] **Step 4: The expedition**

With the wander trip always on offer (L4a), a pet walked new ground near home all day and its curiosity never reached 60, so no expedition was ever offered: walking its own land now lowers curiosity by 1, not 3 (resolution 7).

In `backend/survival/curiosity.py`, replace:

```python
NEW_GROUND = 3.0
```

with:

```python
NEW_GROUND = 1.0  # L4b (was 3): walking its own land is a small discovery, so a pet grows restless and sets out
```

Create `backend/survival/expedition.py`:

```python
"""Expeditions (L4b, the owner's day-17 note: "I want it to be more curious and constantly exploring").

When Mimo is curious (CURIOUS or more), its needs are met (`ready`: all but hunger will do when it
carries READY_FOOD of food, as at dawn) and it has rested REST_DAYS game days since the last one,
the expedition goal is on offer (after first_shelter; it repeats). Its rules score is 40 plus 0.8
of curiosity, RESTLESS_PULL more once restless, so a restless pet with its needs met sets out rather
than settle into its routine. An expedition goes:
1. Pack food and torches: PACK_FOOD hunger of food (foraging.MORE_FOOD asks the food purposes for
   the rest), PACK_TORCHES torches (none when there is no coal to be had: none carried and no coal
   ore mine_ore could go back for) and a campfire, or the logs and sticks for one (made at camp when
   Mimo's arms have no room for it now). The `pack` purpose makes the torches and the campfire from
   what Mimo carries (60, work band); mine_ore fetches coal and gather_wood logs. From packing until
   it is home again, build_storage and drop_items leave the torches and the food be
   (storage.KEEPS_MORE).
2. Travel past the lands it knows. Packed, by day, Mimo sets out (a notable "expedition" event):
   the explored range is the distance from home within which nine in ten of the patches it visited
   lie (RANGE_MIN to RANGE_MAX), the target that plus PAST (at most REACH_MAX from home), and the
   heading the compass way with the most dry land it never visited just past the range. The
   "expedition" trip (explore) heads out that way and beyond the range, up to REACH_MAX from home;
   once past the target it roams the land beyond the range every way, mapping and studying what it
   finds until it is time to camp (explore and investigate work toward the camp until the night).
3. Camp out for the night. On the way out, and on the way back when dusk finds it farther than
   FAR_FROM_HOME from home, Mimo stays out (`away`, in purposes.AWAY): go_home and the head_home
   reflex leave it be, and build_shelter starts no new home out there. It digs in for the night
   (backend.survival.camp). A night slept farther than FAR_FROM_HOME from home counts, camp or not,
   and Mimo wakes up knowing whether it turns home.
4. Map new ground: MAP_WALKS walks onto ground it never walked (the journal's investigate is on
   offer as ever, and works toward the expedition too).
5. Come home with its finds. By day, after a night out once it reached the target and mapped its
   walks, or after NIGHTS_OUT nights, or at once when short of food (under LOW_FOOD carried and
   hungry) or health (under LOW_HEALTH), it turns home; `come_home` (75) walks it back, and it
   camps again should dusk catch it far out. Home, it logs what it found (an "expedition" event:
   how far out, the nights camped, the new things learned) and the goal is reached.
The expedition is kept in state["brain"]["expedition"]: {"since" (the goal's), "phase" ("packing",
"out", "homeward", "home"), "home", "range", "target", "heading", "direction", "far", "nights",
"walks", "lessons", "left_at", "camp", "slept"}; it ends when the goal is reached or set aside
(brain["expedition_at"] then says when). `tend_expedition` (brain.notice_step) moves it on and
`observe_expedition` (brain.observe_step) counts its walks and nights; a crash in either is logged
once and the tick goes on.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, terrain_height
from backend.survival import foraging, purposes, storage
from backend.survival.clock import DAY_SECONDS
from backend.survival.carrying import crafts_fit
from backend.survival.curiosity import CURIOUS, RESTLESS, needs_met, value_of
from backend.survival.exploring import COMPASS
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.grid import Cell
from backend.survival.memory import BUILT, PATCH, cell_of, explored, known, patch_of, places
from backend.survival.once import log_once
from backend.survival.purposes import (
    AT_HOME, Purpose, late_day, register, walk_to,
)
from backend.survival.situation import Situation, in_tick
from backend.survival.steps import as_cell
from backend.survival.toolmaking import Short, make
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.trips import Reason, register_reason
from backend.survival.work import ore_targets

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

GOAL = "expedition"
REST_DAYS = 2.0  # game days between the end of one expedition and the offer of the next
RESTLESS_PULL = 110.0
PACK_FOOD = 90.0  # hunger points of food packed: a day and a half
PACK_TORCHES = 4
RANGE_MIN, RANGE_MAX = 48.0, 144.0
PAST = 48.0
REACH_MAX = 200.0
FAR_FROM_HOME = 48.0  # farther than this from home, dusk finds Mimo camping, not heading home
NIGHTS_OUT = 2
MAP_WALKS = 8
LOW_FOOD = 20.0
LOW_HEALTH = 40.0
HOME_REACH = 6.0
COME_HOME_BATCHES = 6
READY_FOOD = 30.0  # hunger of food carried that counts as fed enough to set out


# The expedition --------------------------------------------------------------------------------

def built_home(db) -> Cell | None:
    home = next((place for place in places(db, ("home",)) if place["note"] == BUILT), None)
    return None if home is None else cell_of(home)


def trek(s: Situation) -> dict | None:
    """The expedition under way: the brain's, while the expedition is Mimo's goal."""
    goal, found = s.brain.get("goal"), s.brain.get("expedition")
    if not goal or goal["name"] != GOAL or not found or found.get("since") != goal["since"]:
        return None
    return found


def phase_of(s: Situation) -> str | None:
    found = trek(s)
    return None if found is None else found["phase"]


def from_home(s: Situation, cell: Cell | None = None) -> float:
    found = trek(s)
    home = found["home"] if found else built_home(s.db) if s.db is not None else None
    if home is None:
        return 0.0
    x, _, z = cell or s.here
    return math.hypot(x - home[0], z - home[2])


def camp_time(s: Situation) -> bool:
    return s.night or late_day(s)


def away(s: Situation) -> bool:
    """Mimo means to stay out: on the way out, or caught far from home by dusk on the way back."""
    phase = phase_of(s)
    if phase == "out":
        return True
    return phase == "homeward" and camp_time(s) and from_home(s) > FAR_FROM_HOME


purposes.AWAY.append(away)


def explored_range(db, home: Cell) -> float:
    """The distance from home within which nine in ten of the patches Mimo visited lie."""
    found = explored(db, home, REACH_MAX)
    distances = sorted(math.hypot(rx * PATCH + PATCH / 2 - home[0], rz * PATCH + PATCH / 2 - home[2])
                       for rx, rz in found)
    if not distances:
        return RANGE_MIN
    return min(RANGE_MAX, max(RANGE_MIN, distances[int(0.9 * (len(distances) - 1))]))


def heading_of(db, seed: str, home: Cell, reach: float) -> int:
    """The compass way (an index into exploring.COMPASS) with the most dry land Mimo never visited
    just past `reach` from home."""
    found = explored(db, home, reach + PAST + PATCH)
    best = (-1, 0)
    for index in range(len(COMPASS)):
        new = 0
        for spread in (-0.35, 0.0, 0.35):
            angle = index * math.pi / 4 + spread
            for distance in (reach + 16, reach + 32, reach + PAST):
                x, z = home[0] + round(math.cos(angle) * distance), home[2] + round(math.sin(angle) * distance)
                new += patch_of(x, z) not in found and terrain_height(x, z, seed) >= SEA_LEVEL
        if new > best[0]:
            best = (new, index)
    return best[1]


def start_trek(s: Situation) -> dict:
    goal = s.brain["goal"]
    found = {"since": goal["since"], "phase": "packing", "home": None, "range": None, "target": None,
             "heading": None, "direction": None, "far": 0.0, "nights": 0, "walks": 0, "lessons": 0,
             "left_at": None, "camp": None, "slept": None}
    s.brain["expedition"] = found
    return found


def packed_food(s: Situation) -> float:
    return foraging.food_points(s)


def coal_known(s: Situation) -> bool:
    """Mimo carries coal, or remembers coal ore mine_ore could go back for: it can have torches."""
    return s.count("coal") > 0 or any(place["note"] == "coal_ore" for place in ore_targets(s))


def torches_packed(s: Situation) -> float:
    """How far along the torches are: PACK_TORCHES of them, or none at all when there is no coal to be had."""
    return 1.0 if not coal_known(s) else min(1.0, s.count("torch") / PACK_TORCHES)


def campfire_ready(s: Situation) -> bool:
    """A campfire carried, or what makes one (2 logs and 3 sticks, of any wood): Mimo makes it at camp
    when its arms have no room for it now."""
    if s.count("campfire") >= 1:
        return True
    try:
        make(dict(s.inventory), "campfire", 1, [])
    except Short:
        return False
    return True


def packed(s: Situation) -> bool:
    return packed_food(s) >= PACK_FOOD and torches_packed(s) >= 1.0 and campfire_ready(s)


def set_out(state: dict, s: Situation, found: dict, context: ActionContext, at: float) -> None:
    home = built_home(s.db)
    reach = explored_range(s.db, home)
    heading = heading_of(s.db, s.seed, home, reach)
    found.update(phase="out", home=list(home), range=round(reach), target=round(min(REACH_MAX, reach + PAST)),
                 heading=heading, direction=COMPASS[heading], left_at=at, lessons=len(known(s.db, "lesson")))
    context.events.append((at, "expedition", f"{state['name']} set out on an expedition to the {COMPASS[heading]}."))
    state["last_thought"] = f"Off to the {COMPASS[heading]}, past everything I know!"
    mark_trigger(state, "goal", at)


def homeward(state: dict, found: dict, at: float) -> None:
    found["phase"] = "homeward"
    state["last_thought"] = "Time to head home and tell... well, to remember it all."
    mark_trigger(state, "goal", at)


def come_home(state: dict, s: Situation, found: dict, context: ActionContext, at: float) -> None:
    found["phase"] = "home"
    learned = len(known(s.db, "lesson")) - found["lessons"]
    context.events.append((at, "expedition", f"{state['name']} came home from its expedition: {round(found['far'])} "
                           f"blocks out, {found['nights']} night{'s' if found['nights'] != 1 else ''} camped, "
                           f"{learned} new thing{'s' if learned != 1 else ''} learned."))
    ensure_brain(state)["expedition_at"] = at
    mark_trigger(state, "goal", at)


def tend_expedition(state: dict, context: ActionContext, at: float) -> None:
    """After a vitals step (brain.notice_step): start, move on or end the expedition."""
    if context.db is None or state.get("died_at") is not None:
        return
    try:
        s = in_tick(state, context, at)
        brain = s.brain
        goal = brain.get("goal")
        if not goal or goal["name"] != GOAL:
            if brain.get("expedition"):
                if brain["expedition"].get("phase") != "home":
                    brain["expedition_at"] = at
                brain.pop("expedition")
            return
        found = trek(s) or start_trek(s)
        phase = found["phase"]
        if phase == "packing" and packed(s) and not camp_time(s) and built_home(s.db) is not None:
            set_out(state, s, found, context, at)
        elif phase in ("out", "homeward"):
            found["far"] = max(found["far"], from_home(s))
            if phase == "out" and should_turn(s, found):
                homeward(state, found, at)
            elif phase == "homeward" and from_home(s) <= HOME_REACH:
                come_home(state, s, found, context, at)
    except Exception as error:
        log_once(logger, "expedition", error)


def should_turn(s: Situation, found: dict) -> bool:
    if packed_food(s) < LOW_FOOD and s.vitals["hunger"] < 50 or s.vitals["health"] < LOW_HEALTH:
        return True
    if camp_time(s):
        return False
    return found["nights"] >= NIGHTS_OUT or (found["nights"] >= 1 and found["far"] >= found["target"]
                                              and found["walks"] >= MAP_WALKS)


def observe_expedition(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After a finished step (brain.observe_step): walks onto new ground, nights slept out, and the
    camp's roof going on."""
    brain = ensure_brain(state)
    found = brain.get("expedition")
    goal = brain.get("goal")
    if not found or not goal or goal["name"] != GOAL or found.get("phase") not in ("out", "homeward"):
        return
    try:
        kind = step["kind"]
        if kind in ("walk", "swim") and brain.get("new_ground_at") == at:
            found["walks"] += 1
        elif kind == "sleep":
            home = found["home"]
            x, _, z = as_cell(state["position"])
            if math.hypot(x - home[0], z - home[2]) > FAR_FROM_HOME:
                found["nights"] += 1
                found["slept"] = at
                if found["phase"] == "out" and should_turn(in_tick(state, context, at), found):
                    homeward(state, found, at)  # at once, so the morning's first choice heads home
    except Exception as error:
        log_once(logger, "expedition steps", error)


# The goal --------------------------------------------------------------------------------------

def rested(s: Situation) -> bool:
    last = s.brain.get("expedition_at")
    return last is None or (s.at - last) * s.scale >= REST_DAYS * DAY_SECONDS


def expedition_valid(s: Situation) -> bool:
    if s.db is None or built_home(s.db) is None:
        return False
    current = active(s)
    if current is not None and current.name == GOAL:
        return True
    return value_of(s.brain) >= CURIOUS and ready(s) and rested(s)


def ready(s: Situation) -> bool:
    """Its needs are met (curiosity.needs_met), or would be but for hunger while it carries a meal's
    worth of food (READY_FOOD): at dawn a pet is often hungry with its breakfast in its pack."""
    if needs_met(s.state, s.db):
        return True
    fed = s.state["vitals"]["hunger"]
    return (packed_food(s) >= READY_FOOD and fed >= 25.0
            and needs_met({**s.state, "vitals": {**s.state["vitals"], "hunger": 100.0}}, s.db))


def expedition_score(s: Situation) -> float:
    curiosity = value_of(s.brain)
    return 40.0 + 0.8 * curiosity + (RESTLESS_PULL if curiosity >= RESTLESS else 0.0)


def pack_share(s: Situation) -> float:
    if phase_of(s) in ("out", "homeward", "home"):
        return 1.0
    return (min(1.0, packed_food(s) / PACK_FOOD) + torches_packed(s) + float(campfire_ready(s))) / 3


def travel_share(s: Situation) -> float:
    found = trek(s)
    if not found or not found["target"]:
        return 0.0
    return min(1.0, found["far"] / found["target"])


def camp_share(s: Situation) -> float:
    found = trek(s)
    return 1.0 if found and found["nights"] >= 1 else 0.0


def map_share(s: Situation) -> float:
    found = trek(s)
    return min(1.0, found["walks"] / MAP_WALKS) if found else 0.0


def home_share(s: Situation) -> float:
    return 1.0 if phase_of(s) == "home" else 0.0


register_goal(Goal(
    GOAL, "An expedition",
    "Pack food and torches, travel past the lands it knows, camp out and come home with what it found.",
    (Milestone("Pack food and torches", pack_share,
               ("pack", "forage", "fish", "hunt", "cook", "gather_wood", "mine_ore")),
     Milestone("Travel past the lands it knows", travel_share, ("explore",)),
     Milestone("Camp out for the night", camp_share, ("camp", "explore", "investigate")),
     Milestone("Map new ground", map_share, ("explore", "investigate")),
     Milestone("Come home with its finds", home_share, ("come_home",))),
    score=expedition_score, thought="I want to see what lies past the lands I know. Pack up, let's go!",
    after=("first_shelter",), valid=expedition_valid, reward=20.0, repeat=True))


def more_food(s: Situation) -> float:
    """While packing, Mimo wants PACK_FOOD of food on hand, not just a day's worth."""
    return max(0.0, PACK_FOOD - foraging.FOOD_WANTED) if phase_of(s) == "packing" else 0.0


foraging.MORE_FOOD.append(more_food)


def packed_kept(s: Situation, item: str) -> float:
    """What an expedition keeps on Mimo (storage.KEEPS_MORE): its torches and its food, from packing
    until it is home again."""
    if phase_of(s) not in ("packing", "out", "homeward"):
        return 0.0
    return {"torch": PACK_TORCHES, "food": PACK_FOOD - foraging.FOOD_WANTED}.get(item, 0.0)


storage.KEEPS_MORE.append(packed_kept)


# pack ------------------------------------------------------------------------------------------

def pack_steps(s: Situation) -> list[dict]:
    """Craft steps for the torches and the campfire an expedition takes, as far as Mimo can make them
    and has room to carry them (carrying.crafts_fit)."""
    trial, steps = dict(s.inventory), []
    wanted = [("torch", count) for count in range(s.count("torch") + 1, PACK_TORCHES + 1)]
    for item, count in wanted + ([("campfire", 1)] if s.count("campfire") < 1 else []):
        attempt, more = dict(trial), []
        if attempt.get(item, 0) >= count:
            continue
        try:
            make(attempt, item, count, more)
        except Short:
            continue
        if crafts_fit(s.inventory, steps + more):
            trial, steps = attempt, steps + more
    return steps


def pack_valid(s: Situation) -> bool:
    return phase_of(s) == "packing" and not s.night and bool(pack_steps(s))


register(Purpose(
    "pack", "pack for the expedition", "Make the torches and the campfire an expedition takes.",
    valid=pack_valid, facts=lambda s: (f"carrying {s.count('torch')} of {PACK_TORCHES} torches, "
                                       f"{s.count('campfire')} campfire, {round(packed_food(s))} of "
                                       f"{round(PACK_FOOD)} hunger of food"),
    score=lambda s: 60.0, plan=lambda s, context: [] if s.brain["batches"] > 0 else pack_steps(s),
    thoughts=("Torches, a campfire, food... what else?", "Packing up for the trip!")))


# The expedition trip ---------------------------------------------------------------------------

def heading_off(found: dict, x: int, z: int) -> float:
    """How far (radians) the column lies from the expedition's heading, seen from home."""
    home = found["home"]
    angle = math.atan2(z - home[2], x - home[0])
    return abs((angle - found["heading"] * math.pi / 4 + math.pi) % (2 * math.pi) - math.pi)


def trek_wanted(s: Situation) -> str | None:
    return "I want to see what lies past the lands I know" if phase_of(s) == "out" else None


def trek_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    found = trek(s)
    if found is None:
        return 0.0, ""
    away_now, there = from_home(s), from_home(s, (x, 0, z))
    off = heading_off(found, x, z)
    if there > found["range"] and (off <= 0.55 * math.pi or found["far"] >= found["target"]):
        return (1.0 if off <= math.pi / 3 or found["far"] >= found["target"] else 0.5), "land past what it knows"
    if there > away_now and off <= math.pi / 3:
        return 0.4, "the way out"
    return 0.0, ""


register_reason(Reason(
    "expedition", "travel past the lands it knows", trek_wanted, trek_value, lambda s: 65.0,
    goals=(GOAL,), reach=REACH_MAX))


# come_home -------------------------------------------------------------------------------------

def come_home_valid(s: Situation) -> bool:
    return phase_of(s) == "homeward" and not away(s) and from_home(s) > HOME_REACH


def plan_come_home(s: Situation, context: ActionContext) -> list[dict]:
    found = trek(s)
    if found is None or s.brain["batches"] >= COME_HOME_BATCHES or from_home(s) <= HOME_REACH:
        return []
    return [walk_to(tuple(found["home"]), AT_HOME)]


register(Purpose(
    "come_home", "come home from its expedition", "Walk back home from an expedition with what it found.",
    valid=come_home_valid, facts=lambda s: f"{round(from_home(s))} blocks from home",
    score=lambda s: 75.0, plan=plan_come_home,
    thoughts=("Home, with so much to remember.", "I can't wait to be home again.")))


# What the viewer and the model are told --------------------------------------------------------

def expedition_view(brain: dict | None) -> dict | None:
    """The expedition for /api/mimo while one is under way: {phase, direction, far, target, nights}."""
    brain = brain or {}
    found, goal = brain.get("expedition"), brain.get("goal")
    if not found or not goal or goal.get("name") != GOAL or found.get("since") != goal.get("since"):
        return None
    return {"phase": found["phase"], "direction": found.get("direction"), "far": round(found.get("far") or 0.0),
            "target": found.get("target"), "nights": found.get("nights", 0),
            "camping": brain.get("purpose") == "camp"}
```

In `backend/survival/brain.py`, replace:

```python
learns there and then, the things it sees to study later, and the end of a look.
"""
```

with:

```python
learns there and then, the things it sees to study later, and the end of a look; and an
expedition (backend.survival.expedition: its walks onto new ground and its nights out).
`notice_step` moves the expedition on.
"""
```

and replace:

```python
from backend.survival.journal import observe_journal
```

with:

```python
from backend.survival.journal import observe_journal
from backend.survival.expedition import observe_expedition, tend_expedition
```

and replace:

```python
    observe_journal(state, step, context, at)
```

with:

```python
    observe_journal(state, step, context, at)
    observe_expedition(state, step, context, at)
```

and replace:

```python
    tend_curiosity(state, context, at)
```

with:

```python
    tend_curiosity(state, context, at)
    tend_expedition(state, context, at)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_expedition.py"`
Expected: `Ran 6 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1048 tests` … `OK` (6 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 6 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/survival/expedition.py backend/survival/purposes.py backend/survival/reflexes.py backend/survival/building.py backend/survival/storage.py backend/survival/curiosity.py backend/survival/brain.py backend/tests/test_survival_expedition.py
git commit -m "feat: expeditions: a curious pet packs food and torches, sets out past the land it knows, stays out for the night and comes home" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Camping out: dug in by a campfire, outposts

Far from home at dusk, Mimo digs in for the night: a campfire and two torches on the ground beside a one-block hole it drops into and roofs over, remembered as an outpost; in the morning it takes the roof off and climbs out (resolution 11).

**Files:**
- Create: `backend/survival/camp.py`
- Modify: `backend/survival/purposes.py` (the docstring), `backend/survival/brain.py` (`observe_camp` in `observe_step`, `leave_camp` in `brain_plan`)
- Test: `backend/tests/test_survival_camp.py`

**Interfaces:**
- Consumes: Task 5's `expedition.away`, `camp_time`, `from_home`, `trek` (its `camp`), `test_survival_expedition.Expedition` and its clocks; L4a's `goals.URGES`, `meets_need`; `blueprints.BUILDING`; `crafting.BLOCKS`, `can_harvest`; `blocks.is_solid`; `cooking.made`; `structures.reserved`; `memory.remember`, `cell_of`; `purposes.walk_to`, `wait_for_nightfall`.
- Produces:
  - The purpose `camp` ("make camp"): valid while `away` and `camp_time`, with somewhere to camp, and not once dug in at night; 85, 95 at dusk and at night; `goals.URGES["camp"]` (always).
  - `camp.roof_block(s)`, `in_camp(s)`, `in_pit(s, cell)`, `camp_spot(s, cell)`, `outpost_near(s)`, `new_camp(s)`, `ground_spots(s, cell)`, `settled(s)`, `somewhere(s)`, `plan_camp(s, context)`, `leave_camp(s, steps) -> list[dict]`, `observe_camp(state, step, context, at)`; constants `OUTPOST_REUSE = 24.0`, `CAMP_SEARCH = 6`, `CAMP_TORCHES = 2`.
  - Memory places of kind `outpost` (note `camp`); a notable `camp` event.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_camp.py`:

```python
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every goal, purpose and reason)
from backend.survival.camp import leave_camp, observe_camp
from backend.survival.goals import meets_need
from backend.survival.memory import places, remember
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES
from backend.tests.test_survival_expedition import DUSK, FLAT, MORNING, NIGHT, Expedition

LATE = {"phase": "day", "seconds_into_day": 2000.0, "time_scale": 1.0, "day_number": 2}


class CampTests(unittest.TestCase):
    def setUp(self):
        self.pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            self.pet.set_out()
        self.pet.go(101, 1)

    def test_far_out_late_in_the_day_making_camp_is_a_need(self):
        camp = PURPOSES["camp"]
        self.assertFalse(camp.valid(self.pet.situation()))  # midday: travel on
        s = self.pet.situation(LATE)
        self.assertTrue(camp.valid(s))
        self.assertEqual(camp.score(s), 85.0)
        self.assertTrue(meets_need(s, "camp", camp.score(s)))
        self.assertEqual(camp.score(self.pet.situation(DUSK)), 95.0)

    def test_at_dusk_it_digs_in_by_a_campfire_with_torches_and_roofs_itself_over(self):
        camp = PURPOSES["camp"]
        steps = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.assertEqual(steps, [{"kind": "place", "target": [102, 1, 1], "block": "campfire"},
                                 {"kind": "place", "target": [100, 1, 1], "block": "torch"},
                                 {"kind": "place", "target": [101, 1, 2], "block": "torch"},
                                 {"kind": "mine", "target": [101, 0, 1]}])
        self.pet.world.carry_out(steps)
        self.pet.state["position"]["y"] = 0.0  # it dropped into the hole
        roof = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.assertEqual(roof, [{"kind": "place", "target": [101, 1, 1], "block": "dirt"}])
        self.pet.world.carry_out(roof)
        context = self.pet.context(DUSK)
        observe_camp(self.pet.state, {**roof[0], "purpose": "camp"}, context, 10.0)
        self.assertEqual([(place["x"], place["y"], place["z"]) for place in places(self.pet.world.db, ("outpost",))],
                         [(101, 0, 1)])
        self.assertEqual(context.events, [(10.0, "camp", "Pip dug in for the night and made a camp.")])
        self.assertEqual(camp.plan(self.pet.situation(DUSK), context)[0]["kind"], "wait")  # for nightfall
        self.assertFalse(camp.valid(self.pet.situation(NIGHT)))  # dug in: sleep takes over
        self.assertTrue(PURPOSES["sleep"].valid(self.pet.situation(NIGHT)))
        walk = [{"kind": "walk", "target": [120, 1, 1], "reach": 3.0}]
        self.assertEqual(leave_camp(self.pet.situation(NIGHT), walk), walk)  # a flight at night: the roof stays
        self.pet.state["brain"]["purpose"] = "gather_stone"
        dig = [{"kind": "mine", "target": [101, -1, 1]}]  # a staircase down from the hole
        self.assertEqual(leave_camp(self.pet.situation(MORNING), dig), [{"kind": "mine", "target": [101, 1, 1]}, *dig])

    def test_it_goes_back_to_an_outpost_near_it(self):
        self.pet.world.grid.put(110, 0, 1, "air")  # an old camp's hole, its roof off
        remember(self.pet.world.db, "outpost", (110, 0, 1), 0.0, "camp")
        self.assertEqual(PURPOSES["camp"].plan(self.pet.situation(DUSK), self.pet.context(DUSK)),
                         [{"kind": "walk", "target": [110, 1, 1], "reach": 1.0, "whole": True},
                          {"kind": "walk", "target": [110, 0, 1], "reach": 0.0}])
        self.assertEqual(self.pet.state["brain"]["expedition"]["camp"], [110, 0, 1])

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        forget_logged()
        self.pet.state["brain"]["expedition"]["camp"] = "not a cell"
        with self.assertLogs("backend.survival.camp", level="ERROR") as logs:
            for at in (1.0, 2.0):
                observe_camp(self.pet.state, {"kind": "place", "purpose": "camp", "target": [1, 1, 1], "block": "dirt"},
                             self.pet.context(), at)
        self.assertEqual(len(logs.output), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_camp.py"`
Expected: ERROR: `ModuleNotFoundError: No module named 'backend.survival.camp'`

- [ ] **Step 3: Camp**

Create `backend/survival/camp.py`:

```python
"""Camping out on an expedition (L4b): digging in for the night, far from home.

From late in the day (and at night), while Mimo means to stay out (expedition.away), the `camp`
purpose makes camp: 85 late in the day, 95 at dusk and at night, and it meets a need
(goals.URGES), so goal work never crowds it out. It goes back to an outpost within OUTPOST_REUSE
blocks whose hole is still open, or picks the nearest spot within CAMP_SEARCH blocks where it can
dig in: standing on natural ground it can dig, with solid ground under that and on all four sides,
nothing it built or tends, no water or lava beside it, and a block for the roof (carried, or the
one it digs out). There it puts the campfire (carried, or made from logs and sticks) and
CAMP_TORCHES torches on the ground beside it, then digs out the block it stands on and drops into
the hole, walled on four sides, and puts a block over its head (any building block: the one it dug
out will do). Then it waits there for nightfall and sleeps (sleep takes over once it is dug in at
night; the brain remembers the hole as a sheltered spot). With nowhere to dig in, camp is not on
offer and Mimo sleeps where it stands. The camp is remembered as an outpost (a memory place,
kind "outpost", note "camp"; a notable "camp" event) when its roof goes on (`observe_camp`, from
brain.observe_step). In the morning the first batch of any purpose takes the roof off first
(`leave_camp`, from brain.brain_plan), and Mimo climbs out.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.services.blocks import is_solid
from backend.services.crafting import BLOCKS, can_harvest
from backend.survival.blueprints import BUILDING
from backend.survival.cooking import made
from backend.survival.expedition import away, camp_time, from_home, trek
from backend.survival.goals import URGES
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, remember
from backend.survival.once import log_once
from backend.survival.purposes import Purpose, register, walk_to, wait_for_nightfall
from backend.survival.situation import Situation
from backend.survival.steps import as_cell
from backend.survival.structures import reserved
from backend.survival.triggers import ensure_brain

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

OUTPOST_REUSE = 24.0
CAMP_SEARCH = 6
CAMP_TORCHES = 2
SIDES = ((1, 0), (0, 1), (-1, 0), (0, -1))


def roof_block(s: Situation) -> str | None:
    """A building block Mimo carries for the roof."""
    return next((block for block in BUILDING if s.count(block) > 0), None)


def in_camp(s: Situation) -> bool:
    """Mimo stands in a camp dug in with its roof on: walled on four sides, a block over its head."""
    x, y, z = s.here
    return (is_solid(s.grid.material(x, y + 1, z)) and is_solid(s.grid.material(x, y - 1, z))
            and all(is_solid(s.grid.material(x + dx, y, z + dz)) for dx, dz in SIDES))


def in_pit(s: Situation, cell: Cell) -> bool:
    """Mimo stands in the hole at `cell` (dug, its roof still off)."""
    return s.here == tuple(cell)


def camp_spot(s: Situation, cell: Cell) -> bool:
    """Mimo can dig in standing at `cell`: on natural ground it can dig, with solid ground under it
    and on all four sides of the hole, nothing it built or tends, no water or lava beside it, and a
    block for the roof (one it carries, or the one it digs out)."""
    x, y, z = cell
    ground = (x, y - 1, z)
    material = s.grid.material(*ground)
    if not s.grid.standable(cell) or reserved(s.grid, ground) or not can_harvest(material, s.inventory):
        return False
    if roof_block(s) is None and BLOCKS.get(material, {}).get("drop") not in BUILDING:
        return False
    if not is_solid(material) or material in ("water", "lava") or not is_solid(s.grid.material(x, y - 2, z)):
        return False
    return all(is_solid(s.grid.material(x + dx, y - 1, z + dz))
               and s.grid.material(x + dx, y, z + dz) not in ("water", "lava") for dx, dz in SIDES)


def outpost_near(s: Situation) -> Cell | None:
    """An outpost within OUTPOST_REUSE blocks whose hole is still open and empty."""
    for place in sorted((place for place in s.places if place["kind"] == "outpost"),
                        key=lambda place: s.distance(cell_of(place))):
        cell = cell_of(place)
        if s.distance(cell) > OUTPOST_REUSE:
            break
        x, y, z = cell
        if s.grid.passable(cell) and s.grid.passable((x, y + 1, z)) and is_solid(s.grid.material(x, y - 1, z)):
            return cell
    return None


def new_camp(s: Situation) -> Cell | None:
    """The nearest spot within CAMP_SEARCH blocks (and a block or two up or down) to dig in at."""
    x, y, z = s.here
    spots = []
    for dx in range(-CAMP_SEARCH, CAMP_SEARCH + 1):
        for dz in range(-CAMP_SEARCH, CAMP_SEARCH + 1):
            column = [(x + dx, y + dy, z + dz) for dy in (0, 1, -1, 2, -2)]
            cell = next((cell for cell in column if s.grid.standable(cell)), None)
            if cell is not None and camp_spot(s, cell):
                spots.append(cell)
    return min(spots, key=lambda cell: (s.distance(cell), cell)) if spots else None


def ground_spots(s: Situation, cell: Cell) -> list[Cell]:
    """Cells beside the camp on the ground, where the campfire and torches go: nearest first."""
    x, y, z = cell
    found = [(x + dx, y, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))]
    return [spot for spot in found if s.grid.standable(spot) and not reserved(s.grid, spot)]


def settled(s: Situation) -> bool:
    """Dug in for the night: in the camp with its roof on, or in its hole with no block for a roof."""
    camp = (trek(s) or {}).get("camp")
    return in_camp(s) or (camp is not None and in_pit(s, camp) and roof_block(s) is None)


def somewhere(s: Situation) -> bool:
    """Mimo has somewhere to camp: its hole, an outpost near, or a spot to dig in."""
    camp = (trek(s) or {}).get("camp")
    return s.sensed("camp spot", lambda: (camp is not None and in_pit(s, camp)) or outpost_near(s) is not None
                    or new_camp(s) is not None)


def camp_valid(s: Situation) -> bool:
    """Far from home from late in the day on, with somewhere to camp; once dug in at night, sleep takes over."""
    return away(s) and camp_time(s) and not (s.night and settled(s)) and (settled(s) or somewhere(s))


def camp_score(s: Situation) -> float:
    return 95.0 if s.night or s.phase == "dusk" else 85.0


def plan_camp(s: Situation, context: ActionContext) -> list[dict]:
    """Dig in: to the camp, fire and torches beside it, the hole (Mimo drops in); then the roof;
    then wait for nightfall."""
    found = trek(s)
    if found is None:
        return []
    if settled(s):
        return [] if s.night else [wait_for_nightfall(s)]
    camp = found.get("camp")
    if camp is not None and in_pit(s, camp):
        block = roof_block(s)
        x, y, z = camp
        return [{"kind": "place", "target": [x, y + 1, z], "block": block}] if block else []
    reuse = outpost_near(s)
    if reuse is not None:
        found["camp"] = list(reuse)
        x, y, z = reuse
        return [{**walk_to((x, y + 1, z), 1.0), "whole": True}, walk_to(reuse)]
    spot = new_camp(s)
    if spot is None:
        return []
    x, y, z = spot
    found["camp"] = [x, y - 1, z]
    steps = [] if s.here == spot else [{**walk_to(spot), "whole": True}]
    inventory = dict(s.inventory)
    lights = ground_spots(s, spot)
    if inventory.get("campfire", 0) < 1:
        steps += made(inventory, "campfire") or []
    if lights and inventory.get("campfire", 0) > 0:
        steps.append({"kind": "place", "target": list(lights.pop(0)), "block": "campfire"})
    for cell in lights[:min(CAMP_TORCHES, inventory.get("torch", 0))]:
        steps.append({"kind": "place", "target": list(cell), "block": "torch"})
    return [*steps, {"kind": "mine", "target": [x, y - 1, z]}]


URGES["camp"] = lambda s: True  # making camp at dusk far from home is a need, like going home


register(Purpose(
    "camp", "make camp", "Far from home at dusk: dig in for the night by a campfire, with torches around.",
    valid=camp_valid, facts=lambda s: f"{round(from_home(s))} blocks from home; {s.phase}",
    score=camp_score, plan=plan_camp,
    thoughts=("Too far to go home tonight. I'll dig in here.", "A little camp, a little fire. Cosy.")))


def leave_camp(s: Situation, steps: list[dict]) -> list[dict]:
    """Once it is not time to camp, the first batch planned inside a dug-in camp (any purpose but
    camp and sleep) takes the roof off first, so Mimo can climb out."""
    if not steps or s.brain.get("purpose") in ("camp", "sleep") or camp_time(s) or not in_camp(s):
        return steps
    x, y, z = s.here
    if not any(place["kind"] == "outpost" and cell_of(place) == s.here for place in s.places):
        return steps
    return [{"kind": "mine", "target": [x, y + 1, z]}, *steps]


def observe_camp(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """The camp's roof went on (brain.observe_step): the camp is remembered as an outpost."""
    if step["kind"] != "place" or step.get("purpose") != "camp" or context.db is None:
        return
    try:
        found = ensure_brain(state).get("expedition") or {}
        camp = found.get("camp")
        if camp is None or as_cell(step["target"]) != (camp[0], camp[1] + 1, camp[2]):
            return
        if remember(context.db, "outpost", tuple(camp), at, "camp"):
            context.events.append((at, "camp", f"{state['name']} dug in for the night and made a camp."))
    except Exception as error:
        log_once(logger, "camp", error)
```

In `backend/survival/purposes.py`, replace:

```python
  to stay out (`AWAY`), go_home is not on offer.
"""
```

with:

```python
  to stay out (`AWAY`), go_home is not on offer.
- L4b: camp is 85 late in the day and 95 at dusk and at night (backend.survival.camp).
"""
```

In `backend/survival/brain.py`, replace:

```python
expedition (backend.survival.expedition: its walks onto new ground and its nights out).
`notice_step` moves the expedition on.
"""
```

with:

```python
expedition (backend.survival.expedition: its walks onto new ground and its nights out;
backend.survival.camp: a camp's roof going on). `notice_step` moves the expedition on, and by day
the first batch planned inside a dug-in camp takes the roof off first (camp.leave_camp).
"""
```

and replace:

```python
from backend.survival.expedition import observe_expedition, tend_expedition
```

with:

```python
from backend.survival.expedition import observe_expedition, tend_expedition
from backend.survival.camp import leave_camp, observe_camp
```

and replace:

```python
    observe_expedition(state, step, context, at)
```

with:

```python
    observe_expedition(state, step, context, at)
    observe_camp(state, step, context, at)
```

and replace:

```python
    steps = plan_batch(purpose, in_tick(state, context, at), context)
```

with:

```python
    s = in_tick(state, context, at)
    steps = plan_batch(purpose, s, context)
```

and replace:

```python
    brain["planned_at"] = at
    return [{**step, "purpose": purpose.name} for step in steps]
```

with:

```python
    brain["planned_at"] = at
    steps = leave_camp(s, steps)  # L4b: out of a dug-in camp, the roof comes off first
    return [{**step, "purpose": purpose.name} for step in steps]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_camp.py"`
Expected: `Ran 4 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1052 tests` … `OK` (4 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 6 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/camp.py backend/survival/purposes.py backend/survival/brain.py backend/tests/test_survival_camp.py
git commit -m "feat: camping out: far from home at dusk Mimo digs in by a campfire with torches, roofs itself over and remembers the camp as an outpost" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: What the model and the viewer are told

The model's payload and `/api/mimo` get the journal and the expedition (resolution 13).

**Files:**
- Modify: `backend/survival/journal.py` (append the views), `backend/survival/pickers.py` (the payload's `journal` and `expedition`), `backend/survival/snapshot.py` (`journal` and `expedition` in the stream)
- Modify tests: `backend/tests/test_survival_pickers.py` (the payload's keys)
- Test: `backend/tests/test_survival_journal_view.py`

**Interfaces:**
- Consumes: Tasks 1–6 (`journal.learned`, `LESSONS`, `curios`, `lessons_of`, `expedition.expedition_view`); `pickers.context_payload`; `snapshot.brain_view`, `survival_view`.
- Produces:
  - `journal.journal_view(db, brain, limit=40) -> list[dict]` (newest first: `thing`, `kind`, `words`, `fact`, `line`, `unlocks`, `at`; `[]` for an archive whose memory cannot be read) and `journal_payload(s) -> {"lessons", "newest", "could_study"}`.
  - The payload's `journal` and `expedition`; `/api/mimo`'s `journal` and `expedition` (`brain_view`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_journal_view.py`:

```python
import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.expedition import expedition_view
from backend.survival.hatch import hatch
from backend.survival.journal import LESSONS, journal_payload, journal_state, journal_view, learn_lesson
from backend.survival.memory import know, remember
from backend.survival.pickers import context_payload
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import survival_view
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_journal import Studying

BORN = 1_000_000.0


class JournalViewTests(Studying):
    def test_the_journal_newest_first_with_the_line_jev_chose(self):
        for at, thing in ((1.0, "gravel"), (2.0, "skitter")):
            learn_lesson(self.world.state, self.context, at, thing)
        journal_state(self.world.state)["words"]["skitter"] = LESSONS["skitter"].lines[0]
        view = journal_view(self.world.db, self.world.state["brain"])
        self.assertEqual([(entry["thing"], entry["line"]) for entry in view],
                         [("skitter", "Skitters crawl out of the caves at night."),
                          ("gravel", "Gravel sometimes hides flint.")])
        self.assertEqual({key: view[1][key] for key in ("kind", "words", "fact", "unlocks", "at")},
                         {"kind": "block", "words": "gravel", "fact": "Gravel sometimes hides flint.",
                          "unlocks": "digs gravel for flint", "at": 1.0})

    def test_the_model_is_told_what_mimo_learned_what_it_could_study_and_its_expedition(self):
        self.world.grid.put(6, 0, 0, "gravel")
        remember(self.world.db, "sight", (6, 0, 0), 0.0, "gravel")
        know(self.world.db, "skitter", "lesson", 1.0)
        payload = context_payload(self.world.situation(), [])
        self.assertEqual(payload["journal"], {"lessons": 1, "newest": "Skitters come out of caves at night.",
                                              "could_study": ["gravel"]})
        self.assertIsNone(payload["expedition"])
        self.assertEqual(journal_payload(self.world.situation())["could_study"], ["gravel"])
        self.assertIsNone(expedition_view({"goal": None, "expedition": {"since": 1.0}}))  # not the goal now


class StreamTests(unittest.TestCase):
    def test_api_mimo_streams_the_journal_and_the_expedition(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            fresh = survival_view(world, BORN + 1, 1.0)
            self.assertEqual((fresh["journal"], fresh["expedition"]), ([], None))
            with world.transaction() as db:
                state = read_state(db)
                know(db, "skitter", "lesson", BORN)
                journal_state(state)["words"]["skitter"] = LESSONS["skitter"].lines[1]
                state["brain"]["goal"] = {"name": "expedition", "since": BORN}
                state["brain"]["expedition"] = {"since": BORN, "phase": "out", "direction": "east", "far": 132.4,
                                                "target": 180, "nights": 1}
                write_state(db, state)
            view = survival_view(world, BORN + 2, 1.0)
        self.assertEqual(view["journal"][0]["line"], "Skitters live in the caves. Careful after dark.")
        self.assertEqual(view["expedition"], {"phase": "out", "direction": "east", "far": 132, "target": 180,
                                              "nights": 1, "camping": False})


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_pickers.py`, replace:

```python
                                        "threats", "defense", "goal", "explore_reasons", "trip", "curiosity"})
```

with:

```python
                                        "threats", "defense", "goal", "explore_reasons", "trip", "curiosity",
                                        "journal", "expedition"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_journal_view.py"`
Expected: ERROR: `ImportError: cannot import name 'journal_payload' from 'backend.survival.journal'`

- [ ] **Step 3: The views**

In `backend/survival/journal.py`, append:

```python


# What the model and the viewer are told --------------------------------------------------------

def journal_view(db, brain: dict | None, limit: int = 40) -> list[dict]:
    """The lessons Mimo learned, newest first: {thing, kind, fact, line (Jev's pick, or the fact),
    unlocks, at}. A world from before L3 read as an archive has learned nothing."""
    words = ((brain or {}).get("journal") or {}).get("words", {})
    try:
        rows = learned(db)
    except Exception:
        return []
    found = []
    for thing, at in reversed(rows):
        lesson = LESSONS.get(thing)
        if lesson is None:
            continue
        found.append({"thing": thing, "kind": lesson.kind, "words": lesson.words, "fact": lesson.fact,
                      "line": words.get(thing) or lesson.fact, "unlocks": lesson.unlocks, "at": at})
    return found[:limit]


def journal_payload(s: Situation) -> dict:
    """For the model: how many lessons Mimo learned, the newest, and what it could study near it."""
    known_now = sorted(lessons_of(s))
    newest = learned(s.db)[-1][0] if s.db is not None and known_now else None
    return {"lessons": len(known_now), "newest": LESSONS[newest].fact if newest in LESSONS else None,
            "could_study": [LESSONS[curio.thing].words for curio in curios(s)[:3]]}
```

In `backend/survival/pickers.py`, replace:

```python
the payload says what a trip would look for and where, the trip Mimo is on, and how curious it is.
"""
```

with:

```python
the payload says what a trip would look for and where, the trip Mimo is on, and how curious it is.
L4b: it also carries the journal (how many lessons Mimo learned, the newest, what it could study
near it) and the expedition under way.
"""
```

and replace:

```python
from backend.survival.exploring import exploration_payload
from backend.survival.goals import active, boosted, goal_payload, meets_need, toward
```

with:

```python
from backend.survival.expedition import expedition_view
from backend.survival.exploring import exploration_payload
from backend.survival.goals import active, boosted, goal_payload, meets_need, toward
from backend.survival.journal import journal_payload
```

and replace:

```python
        "curiosity": curiosity_view(s.brain, s.at, s.scale),
    }
```

with:

```python
        "curiosity": curiosity_view(s.brain, s.at, s.scale),
        # L4b: what Mimo learned and could study near it, and the expedition it is on (or None).
        "journal": journal_payload(s),
        "expedition": expedition_view(s.brain),
    }
```

In `backend/survival/snapshot.py`, replace:

```python
from backend.survival.goals import GOALS, goal_view, reached_rows
```

with:

```python
from backend.survival.expedition import expedition_view
from backend.survival.goals import GOALS, goal_view, reached_rows
from backend.survival.journal import journal_view
```

and replace:

```python
    (L4) its goal with the day plan, and while it explores, what for. A world whose brain has not
    started yet is about to choose."""
    if brain is None:
        return {"purpose": None, "reflex": None, "picker": None, "choosing": True, "goal": None, "trip": None}
    return {"purpose": brain.get("purpose"), "reflex": brain.get("reflex"), "picker": brain.get("picker"),
            "choosing": brain.get("pending") is not None, "goal": goal_view(brain), "trip": trip_view(brain)}
```

with:

```python
    (L4) its goal with the day plan, and while it explores, what for; (L4b) the expedition under
    way. A world whose brain has not started yet is about to choose."""
    if brain is None:
        return {"purpose": None, "reflex": None, "picker": None, "choosing": True, "goal": None, "trip": None,
                "expedition": None}
    return {"purpose": brain.get("purpose"), "reflex": brain.get("reflex"), "picker": brain.get("picker"),
            "choosing": brain.get("pending") is not None, "goal": goal_view(brain), "trip": trip_view(brain),
            "expedition": expedition_view(brain)}
```

and replace:

```python
        indoors = sheltered(db, here_of(state))
```

with:

```python
        indoors = sheltered(db, here_of(state))
        journal = journal_view(db, state.get("brain"))
```

and replace:

```python
        "curiosity": curiosity_view(state.get("brain"), at, scale),
    }
```

with:

```python
        "curiosity": curiosity_view(state.get("brain"), at, scale),
        # L4b: what Mimo learned, newest first ({thing, kind, words, fact, line, unlocks, at}).
        "journal": journal,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_journal_view.py"` and `python3 -m unittest discover -s backend/tests -p "test_survival_pickers.py"`
Expected: `Ran 3 tests` … `OK`, and `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1055 tests` … `OK` (3 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/journal.py backend/survival/pickers.py backend/survival/snapshot.py backend/tests/test_survival_journal_view.py backend/tests/test_survival_pickers.py
git commit -m "feat: the model and /api/mimo are told what Mimo learned and the expedition it is on" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The headless checks: an expedition in the real world

The days tests' pet goes on a real expedition and comes home: packed, it sets out, digs in, sleeps out, takes its roof off and comes home, in that order; in slow mode, left alone, it goes on one of its own (resolution 15). L4a's headless checks keep holding with the journal and expeditions in.

**Files:**
- Test: `backend/tests/test_survival_expedition_run.py`

**Interfaces:**
- Consumes: everything above; L4a's `goals.ask_for_goal`; `grid.world_grid`; the days tests' pace (`SCALE = 60`, a tick a real second).
- Produces: `ExpeditionRunTests` (one test in the default suite, about 10 seconds; one more with `MIMO_SLOW_TESTS=1`).

- [ ] **Step 1: Write the test**

Create `backend/tests/test_survival_expedition_run.py`:

```python
import os
import random
import tempfile
import unittest
from pathlib import Path

from backend.services.blocks import is_solid
from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.goals import ask_for_goal
from backend.survival.grid import world_grid
from backend.survival.hatch import hatch
from backend.survival.memory import known, places
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0
SCALE = 60.0  # a game day is 60 real seconds, as in the days tests
DAY = 60  # ticks in a game day at that pace


class ExpeditionRunTests(unittest.TestCase):
    """L4b, headless: the days tests' pet goes on an expedition and comes home, in the real world."""

    def run_life(self, hatch_seed, chooser_seed, days, nudge_at=None):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(hatch_seed), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(chooser_seed), scale=SCALE)
            for second in range(1, days * DAY + 1):
                state = tick_life(registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
                self.assertIsNone(state["died_at"], state["cause"])
                if second == nudge_at:
                    self.nudge(world, BORN + second)
                chooser.poll(registry, BORN + second)
            with world.connect() as db:
                state = read_state(db)
                grid = world_grid(db, state["world_seed"])
                outposts = places(db, ("outpost",))
                roofs = [grid.material(place["x"], place["y"] + 1, place["z"]) for place in outposts]
                lessons = known(db, "lesson")
            return world.events(5000), outposts, roofs, lessons

    def nudge(self, world, at):
        """Early on day 2, with home built: restless, fed, rested and packed; a goal choice is asked for."""
        with world.transaction() as db:
            state = read_state(db)
            state["brain"]["curiosity"]["value"] = 90.0
            state["vitals"].update(hunger=100.0, energy=100.0, warmth=100.0, health=100.0)
            for item, count in (("bread", 4), ("torch", 4), ("campfire", 1)):
                state["inventory"][item] = state["inventory"].get(item, 0) + count
            ask_for_goal(state, "test", at)
            write_state(db, state)

    def test_a_restless_pet_packs_sets_out_camps_and_comes_home(self):
        events, outposts, roofs, lessons = self.run_life(8, 8, 3, nudge_at=DAY + 5)
        texts = [event["text"] for event in reversed(events)]  # oldest first
        name = "Clover"
        steps = [f"{name} set out on an expedition", f"{name} dug in for the night and made a camp.",
                 f"{name} came home from its expedition", f"{name} reached a goal: an expedition."]
        found = [next((index for index, text in enumerate(texts) if text.startswith(step)), None) for step in steps]
        self.assertNotIn(None, found, [text for text in texts if "expedition" in text or "camp" in text])
        self.assertEqual(found, sorted(found))  # in that order
        self.assertGreaterEqual(len(outposts), 1)
        self.assertFalse(any(is_solid(roof) for roof in roofs))  # it took the roof off and climbed out
        self.assertIn("1 night camped", next(text for text in texts if text.startswith(steps[2])))
        self.assertTrue(lessons)

    @unittest.skipUnless(os.environ.get("MIMO_SLOW_TESTS"), "a slow run: set MIMO_SLOW_TESTS=1")
    def test_left_alone_a_curious_pet_goes_on_an_expedition_of_its_own(self):
        events, outposts, _, _ = self.run_life(8, 8, 7)
        texts = [event["text"] for event in events]
        self.assertTrue(any("set out on an expedition" in text for text in texts))
        self.assertTrue(any("came home from its expedition" in text for text in texts))
        self.assertGreaterEqual(len(outposts), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_expedition_run.py"`
Expected: `Ran 2 tests` … `OK (skipped=1)`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_expedition_run.py"`
Expected: `Ran 2 tests` … `OK`

If the first fails before "set out", print `[text for text in texts if "goal" in text or "plan" in text]`: the goal choice after the nudge must pick the expedition (its rules score, 40 + 0.8 × 90 + 110 = 222, beats any other goal's own score and the current goal's 100 lead). If it fails between "set out" and "dug in", the dusk choice must offer camp (resolution 11): check `camp_valid` at dusk from the brain's state (away, camp time, somewhere to camp).

- [ ] **Step 3: The whole suite and the slow runs**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1057 tests` … `OK (skipped=1)` (2 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 6 tests` … `OK` and `Ran 3 tests` … `OK`. With L4b the dry run measured 47.5 changes of purpose a game hour on average (53.8 in slow mode), the busiest hour 50 (72) against 90, at most 12 (26) toward no goal against 52 (55), 0.0 (0.31) aimless changes a game hour, and rest and sleep 43 % (45 % in slow mode) of the time once home stands (resolution 15).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_survival_expedition_run.py
git commit -m "test: the days tests' pet packs, sets out, digs in for the night and comes home from a real expedition" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Viewer: the journal panel and the expedition line

A "Journal (n)" link opens "What Pebble has learned"; the HUD shows the expedition under the goal (resolution 14).

**Files:**
- Create: `frontend/src/survival/journal.ts`, `frontend/src/survival/journal.test.ts`, `frontend/src/survival/JournalPanel.tsx`
- Modify: `frontend/src/survival/types.ts` (`JournalEntry`, `Expedition`, the state's `journal` and `expedition`), `frontend/src/survival/hud.ts` (the new purposes' words), `frontend/src/survival/SurvivalHud.tsx` (the expedition line, the journal link), `frontend/src/survival/SurvivalWorld.tsx` (the panel)

**Interfaces:**
- Consumes: Task 7's `journal` and `expedition` in `/api/mimo`; L4a's HUD (`goals.ts`, the goal block in `SurvivalHud`); `CraftingPanel`'s dialog shape.
- Produces: `journalTitle(name)`, `journalButton(journal)`, `journalEntries(journal, name)`, `expeditionLine(expedition)` in `journal.ts`; `JournalPanel({ name, journal, onClose })`; `SurvivalHud`'s `onJournal` prop.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/journal.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { expeditionLine, journalButton, journalEntries, journalTitle } from './journal'
import { purposeText } from './hud'
import type { Expedition, JournalEntry } from './types'

const journal: JournalEntry[] = [
  {
    thing: 'skitter', kind: 'creature', words: 'a skitter', fact: 'Skitters come out of caves at night.',
    line: 'Skitters crawl out of the caves at night.', unlocks: '', at: 20,
  },
  {
    thing: 'gravel', kind: 'block', words: 'gravel', fact: 'Gravel sometimes hides flint.',
    line: 'Gravel sometimes hides flint.', unlocks: 'digs gravel for flint', at: 10,
  },
]

const out: Expedition = { phase: 'out', direction: 'east', far: 132, target: 180, nights: 1, camping: false }

describe('the journal', () => {
  it('is titled for the pet and counts its lessons on the button', () => {
    expect(journalTitle('Pebble')).toBe('What Pebble has learned')
    expect(journalButton(journal)).toBe('Journal (2)')
    expect(journalButton([])).toBe('Journal')
    expect(journalButton(undefined)).toBe('Journal')
  })

  it('lists each lesson in Mimo\'s voice, with the plain fact when Jev phrased it and what it unlocks', () => {
    expect(journalEntries(journal, 'Pebble')).toEqual([
      { key: 'skitter', label: 'Creature', line: 'Skitters crawl out of the caves at night.',
        fact: 'Skitters come out of caves at night.', unlocks: null },
      { key: 'gravel', label: 'Block', line: 'Gravel sometimes hides flint.', fact: null,
        unlocks: 'Now Pebble digs gravel for flint.' },
    ])
    expect(journalEntries(undefined, 'Pebble')).toEqual([])
  })
})

describe('the expedition line', () => {
  it('follows the expedition from packing to home', () => {
    expect(expeditionLine({ ...out, phase: 'packing', direction: null, far: 0, target: null, nights: 0 }))
      .toBe('Expedition: packing food and torches')
    expect(expeditionLine({ ...out, nights: 0 })).toBe('Expedition east · 132 of 180 blocks out')
    expect(expeditionLine(out)).toBe('Expedition east · 132 of 180 blocks out · 1 night out')
    expect(expeditionLine({ ...out, camping: true })).toBe('Expedition: making camp for the night')
    expect(expeditionLine({ ...out, phase: 'homeward', nights: 2 })).toBe('Expedition: heading home · 2 nights out')
    expect(expeditionLine({ ...out, phase: 'home' })).toBe('Expedition: home again')
  })

  it('is left out without an expedition, or with an API from before them', () => {
    expect(expeditionLine(null)).toBeNull()
    expect(expeditionLine(undefined)).toBeNull()
  })

  it('names the purposes expeditions and the journal add', () => {
    expect(purposeText({ purpose: 'investigate', reflex: null, choosing: false })).toBe('Taking a closer look')
    expect(purposeText({ purpose: 'camp', reflex: null, choosing: false })).toBe('Making camp')
    expect(purposeText({ purpose: 'come_home', reflex: null, choosing: false })).toBe('Coming home from an expedition')
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/survival/journal.test.ts`
Expected: FAIL: `Failed to resolve import "./journal"`

- [ ] **Step 3: Types and words**

In `frontend/src/survival/types.ts`, replace:

```ts
/** How curious Mimo is (L4, backend/survival/curiosity.py curiosity_view). */
```

with:

```ts
/** A lesson Mimo learned (L4b, backend/survival/journal.py journal_view). */
export interface JournalEntry {
  /** What it learned about, like "gravel" or "skitter". */
  thing: string
  kind: 'block' | 'plant' | 'creature' | 'biome' | 'landmark'
  /** The thing in words, like "a skitter". */
  words: string
  /** What it teaches, like "Skitters come out of caves at night." */
  fact: string
  /** The line in Mimo's voice Jev chose for its journal, or the fact. */
  line: string
  /** What the lesson lets Mimo do, like "digs gravel for flint"; "" for most. */
  unlocks: string
  /** When it learned it (server time). */
  at: number
}

/** The expedition under way (L4b, backend/survival/expedition.py expedition_view). */
export interface Expedition {
  phase: 'packing' | 'out' | 'homeward' | 'home'
  /** Its heading, like "east"; null while it packs. */
  direction: string | null
  /** The farthest it got from home, in blocks. */
  far: number
  /** How far out it means to go; null while it packs. */
  target: number | null
  nights: number
  /** It is making camp right now. */
  camping: boolean
}

/** How curious Mimo is (L4, backend/survival/curiosity.py curiosity_view). */
```

and replace:

```ts
  curiosity?: Curiosity | null
}
```

with:

```ts
  curiosity?: Curiosity | null
  /** L4b: what Mimo learned, newest first (an older API sends none). */
  journal?: JournalEntry[]
  /** L4b: the expedition under way; null without one (an older API sends none). */
  expedition?: Expedition | null
}
```

In `frontend/src/survival/hud.ts`, replace:

```ts
  improve_home: 'Building a bigger home', stock_larder: 'Stocking the larder',
```

with:

```ts
  improve_home: 'Building a bigger home', stock_larder: 'Stocking the larder',
  investigate: 'Taking a closer look', pack: 'Packing for an expedition', camp: 'Making camp',
  come_home: 'Coming home from an expedition',
```

Create `frontend/src/survival/journal.ts`:

```ts
import type { Expedition, JournalEntry } from './types'

/** The journal panel's title (L4b): "What Pebble has learned". */
export function journalTitle(name: string): string {
  return `What ${name} has learned`
}

/** The HUD's button for the journal, with how many lessons it holds once there are any. */
export function journalButton(journal: readonly JournalEntry[] | null | undefined): string {
  const count = journal?.length ?? 0
  return count > 0 ? `Journal (${count})` : 'Journal'
}

const KIND_LABELS: Record<JournalEntry['kind'], string> = {
  block: 'Block', plant: 'Plant', creature: 'Creature', biome: 'Land', landmark: 'Landmark',
}

/**
 * The journal's entries as the panel lists them, newest first: a label for the kind of thing, the line in
 * Mimo's voice, the plain fact when the line is Jev's own phrasing, and what the lesson lets Mimo do.
 */
export function journalEntries(journal: readonly JournalEntry[] | null | undefined, name: string): {
  key: string; label: string; line: string; fact: string | null; unlocks: string | null
}[] {
  return (journal ?? []).map((entry) => ({
    key: entry.thing,
    label: KIND_LABELS[entry.kind] ?? 'Thing',
    line: entry.line,
    fact: entry.line === entry.fact ? null : entry.fact,
    unlocks: entry.unlocks ? `Now ${name} ${entry.unlocks}.` : null,
  }))
}

/**
 * The HUD's expedition line (L4b): "Expedition: packing food and torches", "Expedition east · 132 of 180
 * blocks out · 1 night", "Expedition: making camp for the night", "Expedition: heading home". Null without one.
 */
export function expeditionLine(expedition: Expedition | null | undefined): string | null {
  if (!expedition) return null
  if (expedition.camping) return 'Expedition: making camp for the night'
  const nights = expedition.nights > 0 ? ` · ${expedition.nights} night${expedition.nights === 1 ? '' : 's'} out` : ''
  const way = expedition.direction ? ` ${expedition.direction}` : ''
  switch (expedition.phase) {
    case 'packing': return 'Expedition: packing food and torches'
    case 'out': return `Expedition${way} · ${expedition.far} of ${expedition.target ?? '?'} blocks out${nights}`
    case 'homeward': return `Expedition: heading home${nights}`
    default: return 'Expedition: home again'
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/survival/journal.test.ts`
Expected: `Tests  5 passed (5)`

- [ ] **Step 5: The panel and the HUD**

Create `frontend/src/survival/JournalPanel.tsx`:

```tsx
import { journalEntries, journalTitle } from './journal'
import type { JournalEntry } from './types'

/** L4b: the knowledge journal, what Mimo learned about the world, newest first. */
export default function JournalPanel({ name, journal, onClose }: {
  name: string
  journal: readonly JournalEntry[] | undefined
  onClose: () => void
}) {
  const entries = journalEntries(journal, name)
  const title = journalTitle(name)
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Knowledge journal</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight">{title}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close the journal" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
        </div>
        <p className="mt-3 max-w-xl text-sm leading-6 text-[#54726e]">
          The first time {name} meets something new, it walks up, looks it over, takes a sample and writes down what it learned.
        </p>
        {entries.length === 0 && <p className="mt-6 text-sm text-[#65817b]">Nothing yet: {name} has not studied anything.</p>}
        <ul className="mt-6 space-y-3">
          {entries.map((entry) => (
            <li key={entry.key} className="rounded-xl bg-[#e9f2eb] px-4 py-3 text-sm leading-6">
              <span className="mr-2 rounded-md bg-white/70 px-2 py-0.5 text-xs font-semibold text-[#315e58]">{entry.label}</span>
              <span className="italic text-[#243e3d]">“{entry.line}”</span>
              {entry.fact && <p className="mt-1 text-xs text-[#54726e]">{entry.fact}</p>}
              {entry.unlocks && <p className="mt-1 text-xs font-semibold text-[#3c7a68]">{entry.unlocks}</p>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
```

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```tsx
import { curiosityBar, goalHint, goalLine, planSteps, tripLines } from './goals'
```

with:

```tsx
import { curiosityBar, goalHint, goalLine, planSteps, tripLines } from './goals'
import { expeditionLine, journalButton } from './journal'
```

and replace:

```tsx
export default function SurvivalHud({ state, online, busy, message, cameraMode, autoPick, minimap, onCameraMode, onCare, onHello, onFollow, onCrafting, onOpenLives }: {
```

with:

```tsx
export default function SurvivalHud({ state, online, busy, message, cameraMode, autoPick, minimap, onCameraMode, onCare, onHello, onFollow, onCrafting, onJournal, onOpenLives }: {
```

and replace:

```tsx
  onCrafting: () => void
  /** Shows a Lives button that opens the archive. */
```

with:

```tsx
  onCrafting: () => void
  /** L4b: opens the knowledge journal. */
  onJournal: () => void
  /** Shows a Lives button that opens the archive. */
```

and replace:

```tsx
  const curious = curiosityBar(state.curiosity)
```

with:

```tsx
  const curious = curiosityBar(state.curiosity)
  const expedition = expeditionLine(state.expedition)
```

and replace:

```tsx
          {home && <p className="mt-0.5 truncate text-xs text-[#54726e]">{home}</p>}
```

with:

```tsx
          {expedition && <p className="mt-1 truncate text-xs font-medium text-[#8a6a2f]">{expedition}</p>}
          {home && <p className="mt-0.5 truncate text-xs text-[#54726e]">{home}</p>}
```

and replace:

```tsx
            <button type="button" onClick={onCrafting} className="underline decoration-[#8cafa2] underline-offset-4">Blocks & crafting</button>
```

with:

```tsx
            <button type="button" onClick={onCrafting} className="underline decoration-[#8cafa2] underline-offset-4">Blocks & crafting</button>
            <button type="button" onClick={onJournal} className="underline decoration-[#8cafa2] underline-offset-4">{journalButton(state.journal)}</button>
```

In `frontend/src/survival/SurvivalWorld.tsx`, replace:

```tsx
import CraftingPanel from './CraftingPanel'
```

with:

```tsx
import CraftingPanel from './CraftingPanel'
import JournalPanel from './JournalPanel'
```

and replace:

```tsx
  const [showCrafting, setShowCrafting] = useState(false)
```

with:

```tsx
  const [showCrafting, setShowCrafting] = useState(false)
  const [showJournal, setShowJournal] = useState(false)
```

and replace:

```tsx
        onCrafting={() => setShowCrafting(true)} onOpenLives={onOpenLives} />
```

with:

```tsx
        onCrafting={() => setShowCrafting(true)} onJournal={() => setShowJournal(true)} onOpenLives={onOpenLives} />
```

and replace:

```tsx
          onClose={() => setShowCrafting(false)} />
      )}
```

with:

```tsx
          onClose={() => setShowCrafting(false)} />
      )}
      {showJournal && <JournalPanel name={state.life.name} journal={state.journal} onClose={() => setShowJournal(false)} />}
```

- [ ] **Step 6: Run the viewer's checks**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  313 passed (313)` (5 new), the build succeeds, eslint prints nothing.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1057 tests` … `OK (skipped=1)`

- [ ] **Step 7: Commit**

```bash
git add frontend/src/survival/journal.ts frontend/src/survival/journal.test.ts frontend/src/survival/JournalPanel.tsx frontend/src/survival/types.ts frontend/src/survival/hud.ts frontend/src/survival/SurvivalHud.tsx frontend/src/survival/SurvivalWorld.tsx
git commit -m "feat: the viewer's journal panel, What Pebble has learned, and the HUD's expedition line" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Manual check on the demo and the README

This task is for the controller. It rebuilds the demo image from the branch and restarts the demo stack on its own scratch volume: `mimo-m5demo-api` (:8011) and `mimo-m5demo-worker`, volume `mimo_m5demo`, at the natural pace (`MIMO_TIME_SCALE=1`, `MIMO_ACTION_SCALE=1`), with Jev's key so Jev chooses the journal's lines. The owner's real stack (`pets-api-1`, `pets-mimo-worker-1`) and its volume `pets_mimo_data` are never touched, and no key is printed. The viewer runs on :3000 (:5173 is the owner's dev server). A game day is an hour at the natural pace, so an expedition takes one to two hours: note the time of dawn and dusk from the HUD's sky dial. If a check fails, fix the code in the task that owns it, re-run that task's tests, rebuild and repeat the check.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above, and L4a's manual check (its demo commands and `goal.sh`).

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 1057 tests` … `OK (skipped=1)`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`, the same with `-p "test_survival_days.py"` and with `-p "test_survival_expedition_run.py"`
Expected: `Ran 6 tests` … `OK`, `Ran 3 tests` … `OK` and `Ran 2 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  313 passed (313)`, the build succeeds, eslint prints nothing.

- [ ] **Step 2: Rebuild the demo on the branch, with Jev**

As in L4a's manual check (the first line loads the owner's `.env` without printing anything; `-e TYPESAFE_API_KEY` hands the worker the key's value from the shell):

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

Expected: two container ids. L4b adds no table: the demo world reads as it is; its journal starts empty and fills from the first tick on.

Start the viewer against it (or restart the one on :3000) and open `http://localhost:3000/preview` in the Browser pane:

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8011 npm run dev -- --port 3000 --strictPort
```

- [ ] **Step 3: Keep a journal snippet and a nudge ready**

Save these in your scratchpad directory (not in the repo). `journal.sh` prints the day, phase and purpose, how curious Mimo is, the lessons (oldest first, with the line Jev chose), the lessons waiting for a line, what Mimo is studying and what it left alone, the sights it means to study, the expedition and how far from home Mimo is, the outposts, and the latest learned, expedition, camp and purpose events, oldest first:

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
import time
import backend.survival.brain  # noqa: F401  (registers every goal and purpose)
from backend.survival.clock import clock_at, time_scale
from backend.survival.curiosity import curiosity_view
from backend.survival.expedition import expedition_view, from_home
from backend.survival.journal import journal_view
from backend.survival.memory import places
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.world import SurvivalWorld, read_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
with world.connect() as db:
    state = read_state(db)
    brain = state.get("brain") or {}
    clock = clock_at(state["born_at"], time.time(), time_scale())
    print("day", clock["day_number"], clock["phase"], "| purpose", brain.get("purpose"), "| goal",
          (brain.get("goal") or {}).get("name"))
    print("curiosity", curiosity_view(brain, time.time(), time_scale()))
    for entry in reversed(journal_view(db, brain)):
        print("  learned", entry["thing"], "|", entry["line"])
    journal = brain.get("journal") or {}
    print("waiting for a line", journal.get("unphrased"), "| studying", journal.get("studying"),
          "| left alone", journal.get("tried"))
    print("sights", [(place["note"], place["x"], place["z"]) for place in places(db, ("sight",))])
    s = from_db(db, state, time.time(), time_scale())
    print("expedition", expedition_view(brain), "| from home", round(from_home(s)))
    print("outposts", [(place["x"], place["y"], place["z"]) for place in places(db, ("outpost",))])
for event in reversed(world.events(300)):
    if event["kind"] in ("learned", "expedition", "camp", "goal") or (
            event["kind"] == "purpose" and any(word in event["text"] for word in ("closer look", "camp", "expedition", "come home"))):
        print(event["kind"], "|", event["text"])
PY
```

`trek.sh` is a nudge for the expedition checks when none has started by the second morning of watching: it makes Mimo restless, fed, rested and warm, gives it what packing takes (4 bread, 4 torches, a campfire) and asks for a goal choice, so the choice itself, by Jev or the rules, sets the expedition. Run it only by day, well before dusk, and note that you used it.

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
import time
from backend.survival.goals import ask_for_goal
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    state["brain"]["curiosity"]["value"] = 90.0
    state["vitals"].update(hunger=100.0, energy=100.0, warmth=100.0, health=100.0)
    for item, count in (("bread", 4), ("torch", 4), ("campfire", 1)):
        state["inventory"][item] = state["inventory"].get(item, 0) + count
    ask_for_goal(state, "nudge", time.time())
    write_state(db, state)
print("nudged: restless, fed and packed; a goal choice is asked for")
PY
```

- [ ] **Step 4: The journal**

Over the first half hour, run `journal.sh` a few times. Confirm `learned` events arrive as Mimo walks and digs ("<Name> learned that …": the biome it stands in, the blocks it digs, a lake or cave it walks up to), that each appears under `learned` in `journal.sh`, and that `waiting for a line` empties as Jev answers purpose calls: the lesson then shows one of its lines in Mimo's voice (`journal_line` in the worker's Jev question, no extra call: `goal.sh`'s model calls rise no faster than before). In the viewer, confirm the "Journal (n)" link beside "Blocks & crafting" counts the lessons and opens "What <Name> has learned": each lesson with its kind, Jev's line, the plain fact under it where the line differs, and "Now <Name> digs gravel for flint." under gravel once learned.

- [ ] **Step 5: Taking a closer look**

Wait for `sights` to list something (gravel on a shore, sugar cane, a pumpkin) or for a creature Mimo met to come near. Confirm a purpose event `decided to take a closer look` (the HUD reads "Taking a closer look"), `studying` naming the thing, and within a minute a `learned` event for it; the sight then leaves `sights`. For a creature, confirm Mimo walks within a few blocks of it and waits there a moment before the lesson.

- [ ] **Step 6: Knowledge unlocks work**

In the worker's events, confirm no `decided to dig gravel for flint` comes before the `learned that gravel sometimes hides flint` event, and that once it is learned, with a bow and few arrows, Mimo digs gravel when there is some near. If Mimo has an iron pickaxe, confirm it goes after gold (`mine ore` with gold ore) only after a `learned that gold lies deep` event.

- [ ] **Step 7: An expedition**

If no `set out on an expedition` event has come by the second morning, run `trek.sh` in the morning and note it. Confirm, in order:
- the goal becomes "An expedition" (`set a new goal: an expedition`), and while Mimo lacks food, torches or a campfire the purposes follow it (`pack for the expedition`, `forage`, … `, toward an expedition`); the HUD reads "Expedition: packing food and torches";
- an event `expedition | <Name> set out on an expedition to the <direction>.`, explores `to travel past the lands it knows, toward an expedition`, the HUD's line "Expedition <direction> · <n> of <target> blocks out", and `journal.sh`'s `from home` growing past the target;
- late in the day it does not go home: no `hurried home before dark` and no `go home`; at dusk `decided to make camp`, the HUD "Expedition: making camp for the night", an event `camp | <Name> dug in for the night and made a camp.` and a new outpost. In the Browser pane, follow Mimo: a campfire and two torches on the ground beside a one-block hole, Mimo in it under a block;
- at night it sleeps there (the HUD's action line "Sleeping"; no hostile reaches it);
- in the morning the first step is a mine of the roof, then `decided to come home from its expedition` (the HUD "Expedition: heading home · 1 night out"), and back home an event `expedition | <Name> came home from its expedition: <n> blocks out, 1 night camped, <n> new things learned.` followed by `goal | <Name> reached a goal: an expedition.`

- [ ] **Step 8: A quiet worker**

Confirm the worker log stays quiet: `docker logs mimo-m5demo-worker 2>&1 | grep -c "crashed"` prints `0` (or only lines from before the restart), and that the model calls today stay within `MIMO_MAX_DECISIONS_PER_DAY` (2000). Leave the demo running on the new image for the owner.

- [ ] **Step 9: Describe the curious mind in the README**

In `README.md`, replace:

```markdown
("restless; nothing new for 2 game days"). L4b adds the knowledge journal and expeditions.
```

with:

```markdown
("restless; nothing new for 2 game days").
- **A knowledge journal.** The first time Mimo meets a kind of block, plant, creature, biome or landmark with a lesson (`backend/survival/journal.py`, 32 of them), it studies it and writes down what it learned ("Pip learned that gravel sometimes hides flint."). What it digs, sees laid bare beside it, walks into or walks up to it learns at once; what it only sees from a walk it goes back to: investigate walks up, takes a sample (mines one, or watches the creature) and looks it over. Learning unlocks work: Mimo digs gravel for flint only once it learned that gravel hides flint, and goes after gold and diamonds only once it has seen their ore. Jev chooses each lesson's line in Mimo's voice, in the purpose call it makes anyway; without Jev the journal shows the plain fact. The viewer's "Journal" link opens "What Pip has learned".
- **Expeditions.** Curious (60 or more), with its needs met and two game days after the last one, Mimo may set itself an expedition (`expedition.py`, `camp.py`): it packs 90 hunger of food, 4 torches and a campfire (build_storage leaves them be), sets out past the land it knows the way that has the most new land (up to 200 blocks from home), maps and studies the far land, and at dusk digs in instead of going home: a campfire and two torches on the ground, a one-block hole it drops into and roofs over, remembered as an outpost and used again. In the morning it takes the roof off, and after a night out (two at most, or at once when short of food or health) it walks home and says what it found ("Pip came home from its expedition: 196 blocks out, 1 night camped, 3 new things learned."). The HUD shows the expedition under the goal ("Expedition east · 132 of 180 blocks out · 1 night out").
```

and replace:

```markdown
the model's payload has `goal`, `explore_reasons`, `trip` and `curiosity`.
```

with:

```markdown
the model's payload has `goal`, `explore_reasons`, `trip` and `curiosity`, and (L4b) `journal` (how many lessons, the newest, what Mimo could study near it) and `expedition`; `/api/mimo` has `journal` (the lessons, newest first) and `expedition` too.
```

- [ ] **Step 10: Commit**

```bash
git add README.md
git commit -m "docs: describe the knowledge journal and expeditions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
## Spec coverage

| Spec ("L4 addition: a curious pet": its journal, expeditions, viewer and tests) | Where |
|---------------------------------|-------|
| The first time Mimo meets a new block, plant, creature, biome or landmark, that is a discovery, and it investigates it: walks up, looks, takes a sample (mines one, watches it, or hunts it) | Task 1 (learned at once where the sample or the look is already done: dug, laid bare, walked into, walked up to; sights), Task 2 (`investigate`: walk up, mine or watch, look), L4a's curiosity for the discovery itself; resolution 4 (hunting: see spec gaps) |
| It records a fact from a rules table of what each thing teaches ("gravel sometimes hides flint", "skitters come out of caves at night", "lava lights up caves") | Task 1 (`journal.LESSONS`, 32 lessons; `learn_lesson`, `memory_knowledge` fact `"lesson"`, the `learned` event) |
| Knowledge unlocks behaviour: flint only once gravel's lesson is learned; gold only once gold ore was seen | Task 3 (`Situation.lessons` in `flint_valid` and `wanted_ores`; diamonds too) |
| Jev may phrase the journal line; never inside the tick or in tests | Task 4 (the `"journal_line"` question on a purpose call; a recording fake in the tests; resolution 6) |
| With high curiosity and its needs met, Mimo can take an expedition goal | Task 5 (`expedition`: curiosity 60+, `ready`, two days' rest; 40 + 0.8 × curiosity, +110 restless; new ground lowers curiosity by 1 so a pet walking its own land still grows restless: resolution 7) |
| It packs food and torches | Task 5 (the pack milestone, `pack`, `MORE_FOOD`, `storage.KEEPS_MORE`) |
| It travels past its explored range for one or two game days | Task 5 (the explored range, the target past it, the heading, the `expedition` trip; turning home after one night once past the target, or two) |
| At night it camps with a campfire and a small hut or dug-in shelter, lit by torches | Task 5 (`purposes.AWAY`: no going home, no new home), Task 6 (`camp`: the dug-in hole, campfire, two torches, the roof; resolution 11; the hut: see spec gaps) |
| It maps and samples as it goes, then comes home with its finds | Task 5 (the map milestone's walks onto new ground, `come_home`, the homecoming event with what it found), Tasks 1–2 (lessons on the way) |
| Camps are remembered as outposts | Task 6 (`memory_places` kind `outpost`, reused within 24 blocks) |
| A curiosity bar sits with the vitals | L4a (Task 12) |
| A journal panel shows "What Pebble has learned" | Task 7 (`/api/mimo`'s `journal`), Task 9 (`JournalPanel`, `journalTitle`) |
| The HUD gets an expedition line | Task 7 (`expedition`), Task 9 (`expeditionLine`) |
| Once a home exists, each game day in a headless run brings at least one discovery | L4a (Task 11), still green with L4b (Task 8) |
| Plans: L4b covers the knowledge journal and expeditions | This plan (L4a's resolution 18) |
| Cost: no model calls inside the tick; Jev calls follow the cost rules | Tasks 1–6 (all rules in the tick), Task 4 (the line rides on a purpose call: no extra call) |
| Error handling: crashes logged once, the tick model-free, GETs read-only, no migration, the headless sims green with the milestone's own sim check | Tasks 1, 5, 6 (`log_once` guards; `AWAY`, `KEEPS_MORE` guarded), Task 7 (a GET writes nothing), Task 8 (the expedition run; L4a's checks) |

Spec gaps the plan fills or leaves (the controller ledgers them):
- "A small hut or dug-in shelter": the camp is always dug in. Mimo is one block tall, so a hole one block deep with a block over it walls it in on all sides for one block of cost; a hut would take a shelter's worth of blocks carried out.
- "Watches it, or hunts it": a creature is watched. Hunting stays L1's food work and L4a's hunt for hides; killing a creature to learn about it would empty the land of the ones it has not studied.
- "Jev may phrase the journal line": Jev's API answers choices, so Jev chooses among the lesson's lines (the fact and two in Mimo's voice) rather than writing free text; Luna, which could, is capped and costly and does not phrase lines.
- Knowledge gates cover the spec's examples (flint, gold) and diamonds; the other lessons are for the journal and the model.
- "Comes home with its finds": its finds are what it learned and the ground it mapped, told in the homecoming event; it carries nothing home on purpose.
- Outposts are remembered and used again by later camps, and the brain remembers each as a sheltered spot; the minimap does not draw them.
- "One or two game days": one night out once past the target and mapped, two at most.
