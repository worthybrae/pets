# Living World L4: Purposeful Life Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Mimo's days a purpose: a registry of goals that last days (a home of its own, iron tools, armor, a full larder, a safe yard, a bigger stone home, a herd, the land mapped), each with a why, a validity check, progress from 0 to 1 read from Mimo's state and memory, the purposes that advance it and a mood reward; Jev choosing the goal at dawn or when one is reached or given up, from a small offered set with facts, and the rules picker when Jev is not there; purposes that advance the goal scoring 15 more while the rest step aside unless they meet a need, so rest and explore come only when nothing advances the goal or a need; a day plan at dawn; a notable event and a mood boost when a goal is reached; the goal in the model payload and in `/api/mimo`; the goal line with a progress bar and the day plan on the HUD, and the goals reached on the memorial; and a headless check that aimless changes of purpose fall well below today's.

**Architecture:** Everything registers into a registry. `backend/survival/goals.py` is the goal registry and its rules: milestones and progress, the brain's goal state, how purposes follow the goal (`toward`, `boosted`), the tick's side (`tend_goal`, called from `brain.notice_step`: progress, the day plan, a goal reached or given up) and the chooser's side (`offers`). `pickers.steer` applies the goal to the options, and `choosing.Chooser` answers a goal choice before a purpose choice, with Jev (a `"goal"` question in the same call shape) or the rules. The goals themselves register from new modules: `life_goals.py` (first shelter, iron tools, diamond tools, armor, a safe yard, a herd, the land mapped), `homes.py` (a bigger stone home and its `improve_home` purpose) and `larder.py` (a full larder, its `stock_larder` purpose and a hook in `foraging.food_need`). L3's purposes and items are named, not imported: a milestone whose purposes are not registered, or whose items have no recipe yet, is skipped, so L3's gold and diamond tools, iron armor and pens join the goals the day they land. The viewer gets a pure `goals.ts` module and draws the goal line, the day plan and the memorial's goals reached.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-living-world-design.md` (L4: the milestone table's row, the whole "L4 Purposeful life" outline, the Decisions' "Purposeful life" and "Cost", and "Error handling and testing"). It follows the shape of the L1 and L2 plans (`docs/superpowers/plans/2026-09-23-living-world-l1-animals.md`, `...-l2-danger.md`). L2 is complete with its final fix wave; L3 ("Bigger world") is being carried out alongside and its purposes are only named here (resolutions 1 and 3). The code on branch `worthy/23_09_2026/survival_core` at `983e2aa` is the "old" text every task edits; the dry run applied every task to that commit, and again to `e22a29d` (L3's first eleven tasks).

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls: a fake Jev stands in where a test needs one. The rules picker's random nudge comes from the chooser's seeded `rng`; nothing reads `random` or the clock.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments, no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components. No stylesheet changes: the HUD uses Tailwind classes inline, as it does now.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. Read-only GETs never write. L4 adds no table and no column: the goal lives in Mimo's state JSON (`state["brain"]["goal"]`, `goal_due`, `goal_penalties`, `goal_idle_at`) and the goals reached in `memory_knowledge` (fact `"goal"`).
- **No model call inside the tick.** The tick reads progress, writes the day plan and reaches or gives up goals by rules; goal choices are answered in the worker's Chooser, outside the tick transaction, like purpose choices. Validity checks, milestone shares, facts and scores never write.
- A crashing milestone share, goal validity check, goal score or goal check never stops a tick or the worker: each is logged once (`once.log_once`) and counts as nothing.
- Values from the spec (L4 outline and Decisions): goals are a registry with a name, a why, validity, progress (0 to 1, from state and memory), the purposes that advance them and completion; examples: first shelter, then a better home (a bigger tier, stone walls); iron tools, then armor; a full larder (a chest with food); a safe yard (torches, a door, a fence); a herd (creature seeds and a pen); map the land (explore memory). Jev picks a goal at dawn, or when one completes or fails, from a small offered set with facts; the rules picker is the fallback; a goal lasts days, not minutes. Purposes that advance the active goal get +15 score; purposes that do not are capped in the leisure band unless they meet a need. A day plan at dawn lists the goal's next steps and is shown in the HUD. Completing a goal is a notable event with a mood boost. The HUD shows the goal and its progress bar; the memorial lists the goals reached; the Jev payload carries the goal context. Rest and explore are chosen only when nothing advances the goal or a need. Goal picks follow the same cost rules as purpose picks (the daily cap and the hourly budget; the owner raised Jev's hourly budget from the spec's 8 to `MIMO_JEV_CALLS_PER_HOUR`, default 60, since Jev is cheap).
- L3's names, from L3's plan and used only by name: purposes `build_pen` and `stock_pen`, items `fence`, `diamond_pickaxe`, `iron_cap` and `iron_tunic`. If L3 lands with other names, only the strings in `backend/survival/life_goals.py` change (resolution 3).
- `MIMO_TIME_SCALE` and `MIMO_ACTION_SCALE` (both default 1) are for manual runs only. L4 adds no settings.
- Never run `docker` or `docker compose` in Tasks 1–9. Task 10 is the controller's manual check on the demo stack (`mimo-m5demo-api` on :8011 and `mimo-m5demo-worker`, volume `mimo_m5demo`); never touch, mount or migrate the owner's real volume `pets_mimo_data` or the real stack (`pets-api-1`, `pets-mimo-worker-1`). Never print `TYPESAFE_API_KEY` or any other key.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (797 pass at `983e2aa`)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_goals.py" -v`
- The slow headless runs: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` (about 3 minutes) and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
- Frontend tests: `cd frontend && npm test` (280 pass at `983e2aa`)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint src/survival src/engine` (prints nothing when clean)

Each task says how many tests it adds. If the real starting totals differ, expect the same increases on top of them.

Transcription: every edit is a fenced block, either a whole new file ("Create `path`:"), a "replace: … with: …" pair in a named file ("In `path`, replace:", then "and replace:" for more pairs in the same file), or a block added at the end of a file ("In `path`, append:"; such a block starts with the two blank lines that separate it from what is there). Old texts are kept short, so a task still applies when a neighbouring line changes. The dry run applied each task with the controller's apply script (`.superpowers/sdd/2026-09-23-living-world-l2-danger/apply_plan.py`) to a `git archive` copy of `983e2aa` and ran the task's checks after each one.

## Plan-level resolutions

The spec gives L4 as an outline. These are the details; every task follows them and the controller ledgers them.

1. **Base.** L2 with its final fix wave (`983e2aa`, the last commit before L3). L3's plan (`docs/superpowers/plans/2026-09-23-living-world-l3-bigger-world.md`, committed at `325fd95`) is being carried out on the same branch. This plan was also applied at `e22a29d` (L3's first eleven tasks): every task applied, and from Task 4 on every check is green, the slow headless runs and the aimless check included; Tasks 1–3 there inherit one days-run failure that `e22a29d` has without L4 (`test_left_alone_mimo_hunts_an_animal_and_cooks_its_meat`), which passes again from Task 4. L3's plan and this one touch six of the same files, never the same lines: `backend/survival/brain.py` (L3 edits the M5 purpose-module import line; L4 adds its own line under the L1/L2 one), `backend/survival/creatures/hunting.py` (L3 edits `prey`; L4 `hunt_valid`), `backend/tests/test_survival_sim.py` (L3 raises `PURPOSE_EVENTS_PER_HOUR` for slow mode; L4 leaves that line alone and adds its own cap under `TRAPPED_AT_MOST`), `frontend/src/survival/hud.ts` (L3 adds its purposes' words under `make_gear`; L4 under `forage`), `frontend/src/survival/types.ts` (L3 the `Built` kind; L4 the state, `LifeSummary` and `LifeDetail`) and `README.md` (each adds a section before "Current world rules"). So the two plans apply in either order. Once L3 has landed, the controller re-runs this plan's dry run and re-measures the headless numbers (resolutions 13 and 14).
2. **Registries, not rewrites.** New modules: `goals.py` (the goal registry and its rules), `life_goals.py`, `homes.py` and `larder.py` (goals and their purposes, registered on import), and `frontend/src/survival/goals.ts`. The brain imports the goal modules as it imports purpose modules; `snapshot.py` imports the brain so the API knows every goal's title. Existing modules gain small hooks: `pickers.steer`, `foraging.MORE_FOOD`, `hunting.HUNT_FOR`, `brain.notice_step` calling `goals.tend_goal`, and the Chooser's goal choice.
3. **Goals name purposes.** A goal is a list of milestones: words, a share from 0 to 1 (a function of the Situation) and the purposes that work toward it, plus the items it needs a recipe for. A milestone none of whose purposes is registered, or with an item that has no recipe, is skipped: it counts toward nothing and the day plan leaves it out; a goal with no milestone left is never offered. So the herd (L3's `build_pen`, `stock_pen`, `fence`), diamond tools (`diamond_pickaxe`), the iron-armor step of armor (`iron_cap`, `iron_tunic`) and the yard's fence (a `build_fence` purpose, which no plan has yet) wait for their purposes and recipes. The names come from L3's plan; if L3 lands with others, only those strings change. Progress is the mean of the counted milestones' shares; a goal is complete when all are whole, and reached once in a life (remembered in `memory_knowledge` as fact `"goal"`).
4. **The goals.** first_shelter, "A home of its own" (blocks for the walls, the walls and roof, a bed inside), before every other goal. iron_tools, "Iron tools" (a wooden and a stone pickaxe, iron ore found, 3 iron ore mined, an iron pickaxe: mine_ore only wants the iron a pickaxe takes, so the iron sword is not part of it). better_tools, "Diamond tools", after iron tools (L3). armor_up, "Armor up", after iron tools, as the spec orders them (5 leather, a leather cap, a leather tunic; iron armor with L3). full_larder, "A full larder" (a chest at home; 60 hunger of food in the chests, a day's worth). safe_yard, "A safe yard" (the home's corner torches, its door; a fence with a `build_fence` purpose). better_home, "A bigger stone home" (the blocks, the walls and roof of a bigger tier with cobblestone walls, moving in). herd, "A herd of its own" (L3's pen, 3 animals in it). map_land, "Map the land" (60 % of the dry 8x8 patches within 64 blocks of home walked). Each has a rules score from traits and needs (resolution 7) and a thought.
5. **Where the goal lives.** `state["brain"]["goal"]`: name, since, picker, progress, best progress and when it last rose, the day plan and when it was last checked; `goal_due` is a goal choice waiting (its id from the brain's `next_id`, as purpose choices have), `goal_penalties` the goals given up lately, `goal_idle_at` the last time no goal was open. Worlds from before L4 get these on first use (`goals.goal_state`).
6. **The tick's side** (`goals.tend_goal`, after every vitals step, from `brain.notice_step`): with no goal it asks for one at once, then every 600 game seconds while none is open, and at dawn. With a goal it reads the progress at most once a game minute (and at dawn): a complete goal is reached (a notable `goal` event, "Pip reached a goal: iron tools.", +15 mood, the goal remembered, a new goal and a new purpose asked for); a goal no longer open is given up, and so is one that has made no progress for a third of a game day of daylight while nothing that advances it would be on offer (`idle`: measured, a goal stuck like that, a safe yard with no coal for torches, otherwise held Mimo idle for a day and a half). At dawn it writes the day plan (the next 3 milestones, a routine `plan` event, "Pip's plan for today: find iron ore, mine 3 iron ore and make an iron pickaxe.") and asks for a goal choice; a goal whose progress has not risen for a game day is given up at dawn instead (a routine `plan` event) and not offered for a game day. A new goal gets its day plan at the next check. The plan's steps are ticked off as their milestones fill.
7. **Choosing a goal** (`goals.offers`, `choosing.prepare_goal`, `store_goal`). The offered set is the open goals not given up lately, best first by the rules score, at most 4 with the current goal among them; each carries facts ("40% done; next: find iron ore, mine 3 iron ore"). The rules score is the goal's own score, +20 when a purpose that advances it would be on offer now were it Mimo's goal (`workable`: improve_home and stock_larder are offered only for their own goal), +100 for the current goal (it only goes by being reached or given up, so "a goal lasts days"). Jev chooses when it is configured, more than one goal is on offer and neither the daily cap nor its hourly budget is spent: the same call shape with a `"goal"` question and its own instructions ("…keep the current one unless it is stuck or another matters much more now…"). The call counts toward the daily cap and Jev's hourly budget, but it does not start the 60-second gap before the next model call, so the purpose choice that follows may still go to Jev. Luna never chooses goals. A rules answer is stored at once and the purpose choice follows in the same poll. A new goal is a routine `plan` event ("Pip set a new goal: iron tools. …") and asks for a new purpose; keeping the goal logs nothing.
8. **Purposes follow the goal** (`pickers.steer`). The options on offer that advance the goal are marked with its title and score +15, but not past 80 (the survival band stays first) and not late in the day or at night (going home and sleep come first). While any option advances the goal or meets a need (a survival or needs purpose, `goals.NEEDS`, scoring 50 or more), only those are offered: the others, rest and explore among them, would be capped in the leisure band, and leaving them out also keeps Jev's pick on the goal. When nothing does, every option keeps its own score, as before. When nothing for the goal itself is on offer (the torches wait for the evening, a hunt for hides for its gap), the best other open goal that has something on offer is worked toward meanwhile, so Mimo does not idle while its goal waits.
9. **Jev and the goal.** The purpose question's instructions say to work toward the goal, the choices that do say "It works toward the goal: Iron tools.", and the payload gains `goal` (title, why, progress, the next steps, days on it); the goal question's payload adds `goals_reached`. With a goal, a purpose that ended in the ordinary way (`plan_done`, `idle`, `reflex_ended`) is chosen again by the rules picker, like the short purposes are today: Jev speaks at dawn, dusk, discoveries, new goals, failures, vital crossings and the like, and the goal carries the day between them. A purpose event says which goal it works toward ("Pip decided to gather stone, toward iron tools.").
10. **Goals that need a purpose of their own.** A bigger stone home needs `improve_home` (it designs a bigger tier with cobblestone walls near home and starts it once Mimo carries half the blocks; `build_shelter` goes on with the newest shelter, so it builds the rest and furnishes it, and home moves in when the roof is on). A full larder needs `stock_larder` (the chest in the shelter when there is none, then the food beyond a day's worth stored in it) and `larder.more_food`: while the larder is the goal and Mimo is not hungry, it wants up to 40 hunger more food on hand, so forage, fish, hunt and farm gather past a day's worth. Armor adds `life_goals.hides_wanted` to `hunting.HUNT_FOR`: while armor is the goal and leather is short, Mimo hunts though fed, at most once a sixth of a game day (measured: without the gap it killed a herd in eight minutes). Each of these is offered only while its goal is Mimo's goal: a pet does not start a second house for the fun of it.
11. **What the viewer is told.** `/api/mimo` gains `goal`: name, title, why, progress, the day plan (`[{text, done}]`), who chose it and when (null without one). Life summaries and details (the memorial, `/api/lives/{id}`) gain `goals_reached`: `[{name, title, day}]`, none for the legacy life.
12. **Viewer.** Under the purpose line the HUD shows "Goal: Iron tools" with its percent and a progress bar, and up to 3 steps of today's plan, done ones ticked and struck through; the goal line's tooltip is the why and who chose it. The memorial lists "Goals reached" with their day, and leaves the goal events out of its notable events so each goal shows once. The two new purposes get words ("Building a bigger home", "Stocking the larder").
13. **The headless runs.** Goals fill the day with work: measured over the headless runs' seeds and both pickers, changes of purpose rise (on average from 34 to 47 a game hour, and from 27 to 40 in slow mode; the fake Jev's busiest hour reached 55, and 65 in slow mode, against the old caps of 52 and 55) while the ones toward no goal fall (at most 21 in an hour, and 49 in slow mode). So the flood guard, `PURPOSE_EVENTS_PER_HOUR`, now counts the changes that work toward no goal (an event without ", toward"), at its old value, and all changes get a cap of their own, `ALL_EVENTS_PER_HOUR = 75`. With L3 on top the numbers move: the controller re-measures them when it re-runs the dry run. The days runs' home test allows a second home (the bigger one) and checks home is the newest one built.
14. **Fewer aimless loops** (Task 8). Changes of purpose to rest or explore that work toward no goal, per game hour, over every seed and both pickers: 4.25 before L4 (5.44 in slow mode), measured on `983e2aa`; with L4 1.5 (3.06). The new check requires at most three quarters of the old rate. The runs are made once and shared by the three headless tests. L3 changes the world under the check. On L3's first eleven tasks (`e22a29d`) the rate went from 4.5 to 1.5 (4.75 to 3.88 in slow mode): the check, still against the rate before L3, passes in both modes, but against L3's own rate the slow-mode cut is 18 %, short of a quarter. On its first five (`99710f7`) there was no cut: L3's bigger caves left gather_stone no stair to dig on some seeds, so iron tools stalled and armor, which comes after it, stayed shut. When L3 has landed, the controller re-measures both rates on L3's code (the goals-off rate is the same runs with `backend.survival.goals.GOALS` emptied, `patch.dict(GOALS, clear=True)`), sets `AIMLESS_BEFORE_GOALS` to L3's own goals-off rate, and, should goals no longer cut it by a quarter there, looks at which goals stall (the `plan` events "set a goal aside") before touching the check.
15. **Out of scope.** L3 (new blocks, biomes, caves, tiers, pens, seeds, lanterns). Goals that run beyond the ones listed; goals chosen by Luna; a goal line on the archive browser.

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/survival/goals.py` | Create | The goal registry and its rules: milestones and progress, the brain's goal, purposes following it, the tick's side, the chooser's offers, the views |
| `backend/survival/life_goals.py` | Create | first shelter, iron tools, diamond tools, armor, a safe yard, a herd, the land mapped; `hides_wanted` |
| `backend/survival/homes.py` | Create | The better_home goal and the `improve_home` purpose |
| `backend/survival/larder.py` | Create | The full_larder goal, the `stock_larder` purpose and `more_food` |
| `backend/survival/pickers.py`, `models.py` | Modify | `Option.goal`, `steer`, the payload's `goal`; the goal question and instructions |
| `backend/survival/choosing.py` | Modify | Goal choices in the Chooser; routine re-choices with a goal; the purpose event's goal |
| `backend/survival/brain.py` | Modify | `tend_goal` in `notice_step`; import the goal modules |
| `backend/survival/foraging.py`, `creatures/hunting.py` | Modify | `MORE_FOOD` and `HUNT_FOR` hooks |
| `backend/survival/snapshot.py` | Modify | `goal` in the stream, `goals_reached` on lives |
| `backend/tests/test_survival_{goals,goal_tick,goal_choice,life_goals,homes,larder,goal_view}.py` | Create | One test file per new module or area |
| `backend/tests/test_survival_{choosing,pickers,sim,days}.py` | Modify | What L4 changes in them |
| `frontend/src/survival/goals.ts` (+ test) | Create | The goal line, the day plan and the goals reached in words |
| `frontend/src/survival/types.ts`, `hud.ts`, `SurvivalHud.tsx`, `Memorial.tsx` | Modify | The stream's new fields; the HUD's goal and plan; the memorial's goals |
| `README.md` | Modify | Purposeful life |

## Tasks

1. The goal registry, and purposes that follow the goal
2. Goals in the tick: progress, the day plan, reached and given up
3. Choosing a goal: Jev or the rules
4. Mimo's goals
5. A bigger stone home
6. A full larder
7. What the model and the viewer are told
8. Fewer aimless loops: the headless check
9. Viewer: the goal line, the day plan and the goals reached
10. Manual check on the demo and the README

Tasks 1–8 are the backend and 9 the viewer. Nothing changes what Mimo does until Task 4 registers the first goals: Tasks 1–3 build the machinery with test goals. Task 9 needs only Task 7's stream fields.

---

### Task 1: The goal registry, and purposes that follow the goal

**Files:**
- Create: `backend/survival/goals.py` (its header, every import and constant the module uses, the registry, progress, the brain's goal and how purposes follow it; Tasks 2, 3 and 7 append the rest)
- Modify: `backend/survival/pickers.py` (`Option.goal`; `options` returns `steer(s, found)`), `backend/survival/models.py` (the instructions and the criteria name the goal)
- Test: `backend/tests/test_survival_goals.py`

**Interfaces:**
- Consumes: `purposes.PURPOSES`, `is_valid`, `late_day`; `situation.Situation`, `in_tick`; `memory.know`, `known`; `crafting.RECIPES`; `triggers.ensure_brain`, `mark_trigger`; `once.log_once`; `pickers.Option`, `options`.
- Produces:
  - `goals.Milestone(text, share, purposes, items=())` and `goals.Goal(name, title, why, milestones, score, thought, after=(), valid=always, reward=GOAL_MOOD)`, both frozen dataclasses; `GOALS: dict[str, Goal]`; `register_goal(goal) -> Goal`.
  - Constants: `GOAL_BOOST = 15.0`, `GOAL_TOP = 80.0`, `NEED_FLOOR = 50.0`, `NEEDS` (sleep, go_home, eat, cook, forage, fish, hunt, build_shelter, light_up, build_storage, drop_items), `GOAL_MOOD = 15.0`, `CHECK_EVERY = 60.0`, `STALL = SET_ASIDE = DAY_SECONDS`, `IDLE = DAY_SECONDS / 3`, `IDLE_RETRY = 600.0`, `STICK = 100.0`, `WORKABLE = 20.0`, `OFFERED = 4`, `PLAN_STEPS = 3`, `NEXT_SHOWN = 2`, `REACHED = "goal"`.
  - `lower(text) -> str`; `counted(goal) -> list[(index, Milestone)]`; `share_of(s, milestone) -> float` (0..1, once per Situation, 0 when it crashes); `progress_of(s, goal) -> float`; `complete(s, goal) -> bool`; `ahead(s, goal) -> list[(index, Milestone)]`; `reached(s) -> tuple[str, ...]`; `settled(s, name) -> bool`; `is_open(s, goal) -> bool`.
  - `goal_state(state) -> dict` (the brain, with `goal`, `goal_due`, `goal_penalties`, `goal_idle_at`); `active(s) -> Goal | None`; `ask_for_goal(state, reason, at)`; `adopt_goal(state, name | None, picker, thought, at) -> bool` (True for a new goal; it marks a `"goal"` purpose trigger).
  - `goal_purposes(s) -> frozenset[str] | None`; `penalized(s, name) -> bool`; `own_score(s, goal) -> float | None`; `toward(s, offered_now: set[str]) -> (Goal, frozenset[str]) | None`; `boosted(s, score) -> float`; `meets_need(name, score) -> bool`.
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
    GOALS, Goal, Milestone, adopt_goal, complete, counted, is_open, progress_of, register_goal, toward,
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
@patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [TREE])
@patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [TREE])
class SteerTests(unittest.TestCase):
    def test_without_a_goal_every_purpose_is_offered_at_its_own_score(self):
        with only_goals(WOOD):
            found = {option.name: option for option in options(goal_situation())}
        self.assertLessEqual({"gather_wood", "rest", "explore"}, set(found))
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
or that needs an item with no recipe yet (L3's diamond pickaxe, iron armor, fences), is skipped:
it counts for nothing and the day plan leaves it out. So goals name purposes by name, and grow
as other modules register those purposes. A goal's progress is the mean of its counted milestones'
shares; it is complete when every one is whole. A goal is reached once in a life.

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
need (a purpose in NEEDS scoring NEED_FLOOR or more), only those are offered: the others, rest
and explore among them, would be capped in the leisure band anyway, and leaving them out keeps a
model's pick on the goal too. When nothing for the goal is on offer now (torches wait for the
evening, a hunt for hides for its gap), the best other open goal that has something on offer is
worked toward meanwhile.
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
    and not complete. A validity check that crashes counts as not valid (logged once)."""
    if not counted(goal) or goal.name in reached(s) or not all(settled(s, name) for name in goal.after):
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

def goal_purposes(s: Situation) -> frozenset[str] | None:
    """The registered purposes that advance the goal now (those of its milestones still to do), or
    None without a goal."""
    goal = active(s)
    if goal is None:
        return None
    return s.sensed("goal purposes", lambda: frozenset(
        name for _, milestone in ahead(s, goal) for name in milestone.purposes if name in PURPOSES))


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
        names = frozenset(name for _, milestone in ahead(s, goal) for name in milestone.purposes if name in offered_now)
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


def meets_need(name: str, score: float) -> bool:
    return name in NEEDS and score >= NEED_FLOOR
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
    focused = [option for option in steered if option.goal or meets_need(option.name, option.score)]
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
Expected: `Ran 9 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 806 tests` … `OK` (9 new). No goal is registered yet, so nothing Mimo does changes.

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
  - `goals.stalled(s) -> bool`; `as_goal(s, goal) -> Situation` (a copy with `goal` as Mimo's goal); `workable(s, goal) -> bool` (a purpose that advances it would be on offer, were it Mimo's goal); `idle(s, goal) -> bool` (by day, `IDLE` game seconds without progress and nothing workable); `day_plan(s, goal) -> list[{"text", "done", "step"}]`; `plan_sentence(name, plan) -> str`; `reach_goal(state, context, goal, at)`; `give_up_goal(state, context, name, at, why, scale)`; `check_goal(state, context, at, dawn)`; `tend_goal(state, context, at, phase)` (never raises).
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
    return any(is_valid(PURPOSES[name], t) for _, milestone in ahead(t, goal) for name in milestone.purposes
               if name in PURPOSES)


def idle(s: Situation, goal: Goal) -> bool:
    """By day, the goal's progress has not risen for IDLE game seconds and nothing that advances it
    is on offer: there is nothing to do for it."""
    since = s.brain["goal"]["best_at"]
    return (not s.night and not late_day(s) and (s.at - since) * s.scale >= IDLE and not workable(s, goal))


def day_plan(s: Situation, goal: Goal) -> list[dict]:
    """The next PLAN_STEPS milestones toward the goal."""
    return [{"text": milestone.text, "done": False, "step": index} for index, milestone in ahead(s, goal)[:PLAN_STEPS]]


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
Expected: `Ran 10 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 816 tests` … `OK` (10 new). The tick now asks for a goal, and nothing answers until Task 3.

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
from backend.survival.goals import adopt_goal, ask_for_goal, goal_state
from backend.survival.hatch import hatch
from backend.survival.models import GOAL_INSTRUCTIONS, ask_jev
from backend.survival.once import forget_logged
from backend.survival.pickers import Option
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_choosing import JEV_URL, FakeHttp
from backend.tests.test_survival_goals import LATER, WOOD, only_goals

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
    open, and the best others, OFFERED in all. Goals given up lately are left out."""
    found = [(goal, goal_facts(s, goal), rules_score(s, goal)) for goal in GOALS.values()
             if is_open(s, goal) and not penalized(s, goal.name)]
    found.sort(key=lambda entry: -entry[2])
    current = active(s)
    kept = [entry for entry in found if current is not None and entry[0].name == current.name]
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

- [ ] **Step 6: The headless runs' fake Jev answers either question**

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
        (question, asked), = body["questions"].items()  # "purpose", or (L4) "goal"
        return {"answers": {question: {"choice": self.rng.choice(sorted(asked["criteria"]))}}}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goal_choice.py"`
Expected: `Ran 10 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 826 tests` … `OK` (10 new). With no goal registered, every goal choice finds none open, and the tick asks again every 600 game seconds.

- [ ] **Step 8: Commit**

```bash
git add backend/survival/goals.py backend/survival/choosing.py backend/survival/models.py backend/tests/test_survival_sim.py backend/tests/test_survival_goal_choice.py
git commit -m "feat: Jev chooses Mimo's goal, the rules picker when Jev cannot, and the rules carry the goal between Jev's moments" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Mimo's goals

**Files:**
- Create: `backend/survival/life_goals.py`
- Modify: `backend/survival/creatures/hunting.py` (the `HUNT_FOR` hook), `backend/survival/brain.py` (import the goals)
- Modify tests: `backend/tests/test_survival_choosing.py` (a hatched pet's Jev answer is one its first goal offers), `backend/tests/test_survival_sim.py` (the flood guard counts the changes toward no goal; all changes get their own cap), `backend/tests/test_survival_days.py` (goal events are notable too)
- Test: `backend/tests/test_survival_life_goals.py`

**Interfaces:**
- Consumes: Tasks 1–3; `building.NOMINAL_BILL`, `START_SHARE`, `carried_blocks`; `blueprints.bill`; `structures.blueprint_of`, `todo`; `memory.BUILT`, `PATCH`, `cell_of`, `explored`, `patch_of`, `structures`; `exploring.SURVEY`, `dry_blocks`; `work.wood`; `crafting.TOOL_RANK`; `creatures.kinds.kind_of`, `creatures.table.dead`, `hunting.hunt_valid`; `test_survival_building.World`.
- Produces:
  - Goals `first_shelter`, `iron_tools`, `better_tools`, `armor_up`, `safe_yard`, `herd`, `map_land` (resolution 4).
  - Helpers later tasks use: `life_goals.whole(done) -> float`, `all_structures(s)`, `shelters(s)`, `home_structure(s) -> dict | None` (the shelter whose inside cell is the home Mimo built), `first_home(s)`, `built_share(s, structure) -> float`, `home_parts_done(s, part) -> float`, `land_seen(s) -> float`, `hides_wanted(s) -> bool`; constants `HIDE_HUNT_GAP = DAY_SECONDS / 6`, `MAP_SHARE = 0.6`.
  - `hunting.HUNT_FOR: list` of `(Situation) -> bool`: any true makes hunt valid though Mimo lacks no food.
  - `test_survival_life_goals.built(inventory=None) -> World` (a pet on a meadow that built and furnished its first shelter) and `shares(s, name) -> list[float]`, for Tasks 5 and 6.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_life_goals.py`:

```python
import unittest

from backend.services.crafting import RECIPES
from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.creatures import hunting
from backend.survival.goals import GOALS, adopt_goal, complete, counted, is_open, progress_of, share_of
from backend.survival.life_goals import DAY_SECONDS, hides_wanted, land_seen
from backend.survival.memory import mark_explored, remember, structures
from backend.survival.purposes import PURPOSES
from backend.survival.structures import blueprint_of
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

- first_shelter, "A home of its own": gather blocks, raise the walls and roof, put a bed inside
  (M5's build_shelter). Every other goal comes after it.
- iron_tools, "Iron tools": a wooden and a stone pickaxe, iron ore found, 3 iron ore mined, an
  iron pickaxe.
- better_tools, "Diamond tools", after iron tools: diamonds found, 3 mined, a diamond pickaxe.
  Every milestone needs L3's diamond_pickaxe recipe, so it waits for L3.
- armor_up, "Armor up", after iron tools: 5 leather, a leather cap and a leather tunic (L2's
  make_gear), and iron armor once L3's iron_cap and iron_tunic recipes exist. While it is the goal
  and leather is short, Mimo also hunts for hides though fed (hunting.HUNT_FOR), at most once a
  sixth of a game day.
- safe_yard, "A safe yard": torches at the corners of home, a door in its doorway, and a fence
  round the yard once a purpose named build_fence exists (none yet: L3 plans no yard fence).
- herd, "A herd of its own": a pen by home and 3 animals grown in it, with L3's build_pen and
  stock_pen (their milestones need L3's fence recipe too).
- map_land, "Map the land": set foot on MAP_SHARE of the dry land within 64 blocks of home.
backend.survival.homes adds better_home and backend.survival.larder full_larder.

Their rules scores (goals.rules_score adds WORKABLE and STICK): first_shelter 90; iron_tools 60
plus a tenth of diligence; better_tools 50 plus a tenth of diligence; armor_up 50 plus a tenth of
caution, 15 more when a creature hurt Mimo in the last game day; safe_yard 55 plus a tenth of
caution; herd 45 plus a tenth of patience; map_land 40 plus a tenth of curiosity.
"""

from __future__ import annotations

import math

from backend.services.crafting import TOOL_RANK
from backend.survival.blueprints import bill
from backend.survival.building import NOMINAL_BILL, START_SHARE, carried_blocks
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures import hunting
from backend.survival.creatures.kinds import kind_of
from backend.survival.creatures.table import dead
from backend.survival.exploring import SURVEY, dry_blocks
from backend.survival.goals import Goal, Milestone, register_goal
from backend.survival.memory import BUILT, PATCH, cell_of, explored, patch_of, structures
from backend.survival.situation import Situation
from backend.survival.structures import blueprint_of, todo
from backend.survival.work import wood

WOOD_FOR_A_PICKAXE = 3.0  # logs of wood: a crafting table, planks and sticks
IRON_WANTED = 3
DIAMONDS_WANTED = 3
LEATHER_WANTED = 5  # a cap takes 2, a tunic 3
HIDE_HUNT_GAP = DAY_SECONDS / 6  # game seconds between two hunts for hides
MAP_SHARE = 0.6  # of the dry land within SURVEY blocks of home
PEN_ANIMALS = 3


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
    (Milestone("Gather blocks for the walls", shelter_blocks, ("gather_wood", "gather_stone", "craft_tools")),
     Milestone("Raise the walls and roof", lambda s: built_share(s, shelter_now(s)), ("build_shelter",)),
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
    (Milestone("Make a wooden pickaxe", wooden_pickaxe, ("gather_wood", "craft_tools")),
     Milestone("Make a stone pickaxe", lambda s: whole(pickaxe_rank(s) >= 2), ("gather_stone", "craft_tools")),
     Milestone("Find iron ore", lambda s: whole(has_iron_pickaxe(s) or s.count("iron_ore", "iron_ingot") > 0
                                                or remembers(s, "iron_ore")), ("gather_stone", "mine_ore")),
     Milestone("Mine 3 iron ore", iron_mined, ("mine_ore", "gather_stone")),
     Milestone("Make an iron pickaxe", lambda s: whole(has_iron_pickaxe(s)), ("craft_tools",))),
    score=lambda s: 60.0 + s.trait("diligence") / 10, thought="I want iron tools. Stone only goes so far.",
    after=("first_shelter",)))


def has_diamond_pickaxe(s: Situation) -> bool:
    return s.count("diamond_pickaxe") > 0


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

register_goal(Goal(
    "armor_up", "Armor up",
    "Gloomlings hit hard at night: armor takes the edge off every blow.",
    (Milestone("Gather 5 leather", leather_gathered, ("hunt",)),
     Milestone("Make a leather cap", lambda s: whole(wears(s, "leather_cap", "iron_cap")), ("make_gear",)),
     Milestone("Make a leather tunic", lambda s: whole(wears(s, "leather_tunic", "iron_tunic")), ("make_gear",)),
     Milestone("Make iron armor", lambda s: (wears(s, "iron_cap") + wears(s, "iron_tunic")) / 2,
               ("craft_tools", "mine_ore"), items=("iron_cap", "iron_tunic"))),
    score=lambda s: 50.0 + s.trait("caution") / 10 + (15.0 if hurt_lately(s) else 0.0),
    thought="Next time a gloomling swings at me, I'll be ready.", after=("first_shelter", "iron_tools")))


# safe_yard -------------------------------------------------------------------------------------

register_goal(Goal(
    "safe_yard", "A safe yard",
    "Light and a door keep gloomlings away from home at night.",
    (Milestone("Light torches at the corners of home", lambda s: home_parts_done(s, "torch"), ("light_up", "mine_ore")),
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
    (Milestone("Build a pen by home", lambda s: whole(finished_pen(s) is not None), ("build_pen",), items=("fence",)),
     Milestone("Grow 3 animals in the pen", lambda s: animals_in_pen(s) / PEN_ANIMALS, ("stock_pen",),
               items=("fence",))),
    score=lambda s: 45.0 + s.trait("patience") / 10, thought="A few animals of my own, safe in a pen.",
    after=("first_shelter",)))


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

In `backend/survival/brain.py`, replace:

```python
from backend.survival.creatures import defense, gear, hunting  # noqa: F401  (L1's hunt; L2's make_gear, fight, flee)
```

with:

```python
from backend.survival.creatures import defense, gear, hunting  # noqa: F401  (L1's hunt; L2's make_gear, fight, flee)
from backend.survival import life_goals  # noqa: F401  (L4's goals)
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

Measured over the headless runs (resolution 13): with this task's goals the fake Jev reached 48 changes of purpose in a game hour, and 63 in slow mode, over the old slow cap of 55, while the changes toward no goal stayed at 29 at most, and 47 in slow mode; with every L4 goal (after Task 7), 55 and 65, with 21 and 49 toward no goal.

`PURPOSE_EVENTS_PER_HOUR` keeps its value (L3 raises it for slow mode) and now counts the changes toward no goal; the new `ALL_EVENTS_PER_HOUR` caps them all.

In `backend/tests/test_survival_sim.py`, replace:

```python
TRAPPED_AT_MOST = 180.0  # game seconds
```

with:

```python
TRAPPED_AT_MOST = 180.0  # game seconds
# L4: goals fill the day with work, and a change toward a goal (its event says ", toward ...") is
# that work, so the flood guard above now counts the other changes, and all changes get a looser
# cap of their own (with L4 the fake Jev reached 55 in a game hour, and 65 in slow mode, at most 49
# of them toward no goal).
ALL_EVENTS_PER_HOUR = 75
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
Expected: `Ran 9 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 835 tests` … `OK` (9 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/survival/life_goals.py backend/survival/creatures/hunting.py backend/survival/brain.py backend/tests/test_survival_life_goals.py backend/tests/test_survival_choosing.py backend/tests/test_survival_sim.py backend/tests/test_survival_days.py
git commit -m "feat: Mimo's goals: a home of its own, iron tools, armor, a safe yard, the land mapped, and L3's tools and herd when they come" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: A bigger stone home

**Files:**
- Create: `backend/survival/homes.py`
- Modify: `backend/survival/brain.py` (import it)
- Modify tests: `backend/tests/test_survival_days.py` (a second, bigger home may follow the first)
- Test: `backend/tests/test_survival_homes.py`

**Interfaces:**
- Consumes: Task 4's `life_goals.all_structures`, `built_share`, `first_home`, `home_structure`, `shelters`, `whole`, `test_survival_life_goals.built` and `shares`; `goals.Goal`, `Milestone`, `active`, `register_goal`; `blueprints.NAMES`, `TIERS`, `Blueprint`, `bill`, `find_site`, `shelter`, `style_for`; `building.START_SHARE`, `build_batch`, `carried_blocks`, `site_center`; `structures.start`; `purposes.Purpose`, `register`.
- Produces:
  - Purpose `improve_home` ("build a bigger home", 60 plus a tenth of creativity), offered only while `better_home` is the goal.
  - Goal `better_home`, "A bigger stone home" (after first_shelter).
  - `homes.rank(structure) -> int` (0, 1 or 2: the tier), `moved_up(s) -> bool`, `rising(s) -> dict | None`, `better_design(s) -> Blueprint | None` (cobblestone walls; the largest bigger tier Mimo's blocks cover, else the next one; named "<Name>'s <Snug|Peaked|Round> Stone House"), `blocks_wanted(s) -> int`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_homes.py`:

```python
import unittest

from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.goals import GOALS, adopt_goal, complete, is_open
from backend.survival.homes import better_design, blocks_wanted, moved_up, rising
from backend.survival.memory import places, structures
from backend.survival.purposes import PURPOSES
from backend.tests.test_survival_life_goals import built, shares


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
of creativity. The goal is done when Mimo lives in a stone home of a bigger tier than the first
shelter it finished; its rules score is 45 plus a tenth of creativity.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.survival.blueprints import NAMES, TIERS, Blueprint, bill, find_site, shelter, style_for
from backend.survival.building import START_SHARE, build_batch, carried_blocks, site_center
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.life_goals import all_structures, built_share, first_home, home_structure, shelters, whole
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.structures import start

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

STONE = "cobblestone"
GOAL = "better_home"


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


def better_design(s: Situation) -> Blueprint | None:
    """A bigger stone home near home (looked for once per Situation), or None when home is as big
    as a shelter gets or no site fits."""
    def look() -> Blueprint | None:
        home = home_structure(s)
        if home is None or rank(home) >= len(TIERS) - 1:
            return None
        style = replace(style_for(s.state.get("traits", {}), s.seed, len(all_structures(s))), wall=STONE)
        have, bigger = carried_blocks(s), TIERS[rank(home) + 1:]
        for size in reversed(bigger):
            site = find_site(s.grid, site_center(s), size, style.doors, style.roof)
            if site is None:
                continue
            design = shelter(site, style, f"{s.state['name']}'s {NAMES[style.roof]} Stone House")
            if bill(design, s.grid) <= have or size == bigger[0]:
                return design
        return None
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


register_goal(Goal(
    GOAL, "A bigger stone home",
    "The first shelter is small: a bigger home with stone walls is roomier, warmer and safer.",
    (Milestone("Gather blocks for a bigger home", home_blocks, ("gather_stone", "gather_wood", "improve_home")),
     Milestone("Raise its stone walls and roof", lambda s: 1.0 if moved_up(s) else built_share(s, rising(s)),
               ("build_shelter", "improve_home")),
     Milestone("Move in", lambda s: whole(moved_up(s)), ("build_shelter",))),
    score=lambda s: 45.0 + s.trait("creativity") / 10, thought="A bigger home, with stone walls this time.",
    after=("first_shelter",), valid=lambda s: rising(s) is not None or better_design(s) is not None))
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import life_goals  # noqa: F401  (L4's goals)
```

with:

```python
from backend.survival import homes, life_goals  # noqa: F401  (L4's goals; improve_home)
```

- [ ] **Step 4: The days runs may see a second home**

Measured: with every L4 goal (after Task 6) the days runs' pet moves into a bigger stone home on its fourth day, a second "moved in" event; with this task's goals alone it has not by then. The test takes either, and checks that home is the newest shelter built.

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
Expected: `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 838 tests` … `OK` (3 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/survival/homes.py backend/survival/brain.py backend/tests/test_survival_homes.py backend/tests/test_survival_days.py
git commit -m "feat: a bigger stone home as a goal, started by improve_home and finished by build_shelter" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: A full larder

**Files:**
- Create: `backend/survival/larder.py`
- Modify: `backend/survival/foraging.py` (the `MORE_FOOD` hook), `backend/survival/brain.py` (import it)
- Test: `backend/tests/test_survival_larder.py`

**Interfaces:**
- Consumes: Task 4's `life_goals.home_structure`, `whole`, `test_survival_life_goals.built` and `shares`; `goals.Goal`, `Milestone`, `active`, `register_goal`; `storage.chest_spot`, `chest_placed`, `chest_contents`, `spare_food`; `building.current_shelter`; `carrying.CHEST_STACKS`, `crafts_fit`, `room_for`; `cooking.made`; `structures.blueprint_of`, `clearing`; `foraging.whole_walk`, `food_need`; the `store` and `place` steps.
- Produces:
  - `foraging.MORE_FOOD: list` of `(Situation) -> float`: food a goal wants on hand beyond a day's worth, added to `food_need`.
  - Purpose `stock_larder` ("stock the larder", 55 plus a tenth of thrift), offered only while `full_larder` is the goal.
  - Goal `full_larder`, "A full larder" (after first_shelter, with a home Mimo built).
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
               ("forage", "fish", "hunt", "farm", "cook", "stock_larder"))),
    score=lambda s: 45.0 + s.trait("thrift") / 10 + (15.0 if s.vitals["hunger"] < 50 else 0.0),
    thought="A full chest at home. Then no night is a hungry one.", after=("first_shelter",),
    valid=lambda s: home_structure(s) is not None))
```

In `backend/survival/brain.py`, replace:

```python
from backend.survival import homes, life_goals  # noqa: F401  (L4's goals; improve_home)
```

with:

```python
from backend.survival import homes, larder, life_goals  # noqa: F401  (L4's goals, improve_home, stock_larder)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_larder.py"`
Expected: `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 841 tests` … `OK` (3 new).

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 2 tests` … `OK` and `Ran 3 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/larder.py backend/survival/foraging.py backend/survival/brain.py backend/tests/test_survival_larder.py
git commit -m "feat: a full larder as a goal: more food gathered, a chest put in and a day's food stored" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: What the model and the viewer are told

**Files:**
- Modify: `backend/survival/goals.py` (append the views), `backend/survival/pickers.py` (the payload's `goal`), `backend/survival/snapshot.py` (`goal` in the stream; `goals_reached` on lives)
- Modify tests: `backend/tests/test_survival_pickers.py` (the payload's keys)
- Test: `backend/tests/test_survival_goal_view.py`

**Interfaces:**
- Consumes: Tasks 1–6 (the goals' titles come from the registry: `snapshot.py` imports the brain, which imports every goal module); `snapshot.brain_view`, `survival_view`, `life_detail`, `life_summary`; `clock.clock_at`.
- Produces:
  - `goals.goal_payload(s) -> dict | None`: `{"title", "why", "progress", "next_steps", "days_on_it"}`; `goal_view(brain) -> dict | None`: `{"name", "title", "why", "progress", "plan": [{"text", "done"}], "picker", "since"}`; `reached_rows(db) -> list[(name, at)]`.
  - `context_payload(s, events)["goal"]`; `/api/mimo`'s `goal` (null without one); `snapshot.goals_reached(world, born_at, scale) -> list[{"name", "title", "day"}]`; `life_detail(...)["goals_reached"]` and `life_summary(...)["goals_reached"]` (`[]` for the legacy life).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_goal_view.py`:

```python
import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api.lives import get_life, hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.goals import adopt_goal
from backend.survival.memory import know
from backend.survival.pickers import context_payload
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_goals import WOOD, goal_situation, only_goals


class GoalPayloadTests(unittest.TestCase):
    def test_the_model_is_told_the_goal_its_progress_and_what_comes_next(self):
        with only_goals(WOOD):
            self.assertIsNone(context_payload(goal_situation(), [])["goal"])
            s = goal_situation("woodpile", inventory={"oak_log": 2})
            self.assertEqual(context_payload(s, [])["goal"], {
                "title": "A woodpile", "why": "Wood makes everything else.", "progress": 0.25,
                "next_steps": ["Carry 4 logs", "Make a pickaxe"], "days_on_it": 0})


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
                                        "threats", "defense", "goal"})
        self.assertIsNone(payload["goal"])  # L4: no goal chosen yet
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goal_view.py"`
Expected: 3 errors: `KeyError: 'goal'` (the payload and the stream) and `KeyError: 'goals_reached'` (the memorial)

- [ ] **Step 3: The goal for the model and the viewer**

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
"""
```

with:

```python
(`steer`, with the rules in backend.survival.goals), and the payload carries the goal.
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
        # L2: the hostile creatures that could come after Mimo, and how it can meet them.
        **threats_payload(s),
```

with:

```python
        # L2: the hostile creatures that could come after Mimo, and how it can meet them.
        **threats_payload(s),
        # L4: the goal Mimo works toward, how far along it is and what comes next (or None).
        "goal": goal_payload(s),
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
from backend.survival.goals import GOALS, goal_view, reached_rows
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
    (L4) its goal with the day plan. A world whose brain has not started yet is about to choose."""
    if brain is None:
        return {"purpose": None, "reflex": None, "picker": None, "choosing": True, "goal": None}
    return {"purpose": brain.get("purpose"), "reflex": brain.get("reflex"), "picker": brain.get("picker"),
            "choosing": brain.get("pending") is not None, "goal": goal_view(brain)}
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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_goal_view.py"`
Expected: `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 844 tests` … `OK` (3 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/goals.py backend/survival/pickers.py backend/survival/snapshot.py backend/tests/test_survival_goal_view.py backend/tests/test_survival_pickers.py
git commit -m "feat: the goal in the model payload and in /api/mimo, and the goals a life reached on its memorial" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Fewer aimless loops: the headless check

The owner's words: "ideally though I want the actions of the pet to be purposeful". Before L4, Mimo picked a purpose moment to moment and, whenever nothing else was on offer, rested or explored: rest, explore, rest. This task measures that on the headless runs and holds L4 to it (resolution 14). An aimless change is a change of purpose to rest or explore that works toward no goal: its event reads "decided to rest." or "decided to explore." (a change toward a goal reads "decided to explore, toward map the land."). Per game hour, over every seed and both pickers, before L4 (measured on `983e2aa` with this very test's runs): 4.25, and 5.44 in slow mode. With Tasks 1–7: 1.5, and 3.06 in slow mode. The check asks for at most three quarters of the old rate. Changes of purpose as a whole rise, since goals fill the day with work (resolution 13); the flood guard from Task 4 still holds the changes toward no goal to the old caps. L3 changes the world under these runs: when it has landed, the controller re-measures the rate before goals on L3's code and updates `AIMLESS_BEFORE_GOALS` (resolution 14).

**Files:**
- Modify tests: `backend/tests/test_survival_sim.py` (each run is made once and shared; the aimless check)

**Interfaces:**
- Consumes: Tasks 1–7 (every goal); the headless runs' `run_life`, `SEEDS`, `SLOW`, `HOUR`; Task 4's `"free"` list.
- Produces: `run_life(seed, jev)` is cached (`functools.lru_cache`; call it with `jev=` as the tests do) and returns `"aimless"` (the game times of aimless changes) and `"hours"` (the game hours the run lasted); `AIMLESS_BEFORE_GOALS`, `AIMLESS_SHARE = 0.75`, `AIMLESS`, after Task 4's `ALL_EVENTS_PER_HOUR`.

- [ ] **Step 1: Write the check**

In `backend/tests/test_survival_sim.py`, replace:

```python
Set MIMO_SLOW_TESTS=1 for longer runs on more seeds.
"""

import logging
```

with:

```python
Set MIMO_SLOW_TESTS=1 for longer runs on more seeds. L4: each run is made once and shared by the
tests, which also check that goals leave fewer aimless changes of purpose than before them.
"""

import functools
import logging
```

and replace:

```python
ALL_EVENTS_PER_HOUR = 75
```

with:

```python
ALL_EVENTS_PER_HOUR = 75
# L4: changes of purpose to rest or explore that work toward no goal, per game hour, over every
# seed and both pickers, measured on these runs before goals (983e2aa): 4.25 (5.44 in slow mode).
# With goals they must fall by at least a quarter; measured with L4, 1.5 (3.06 in slow mode).
AIMLESS_BEFORE_GOALS = 5.44 if SLOW else 4.25
AIMLESS_SHARE = 0.75
AIMLESS = (" decided to rest.", " decided to explore.")  # a change toward a goal says ", toward ..."
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
                    "free": [event["at"] - BORN for event in purposes if ", toward " not in event["text"]],
```

with:

```python
                    "free": [event["at"] - BORN for event in purposes if ", toward " not in event["text"]],
                    "aimless": [event["at"] - BORN for event in purposes
                                if any(words in event["text"] for words in AIMLESS)],
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
```

- [ ] **Step 2: Run the check**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_sim.py" -v`
Expected: `Ran 3 tests` … `OK`, the new `test_goals_leave_fewer_aimless_rests_and_explores_than_before_them` among them.

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"`
Expected: `Ran 3 tests` … `OK`

To see that the check would catch aimless loops, set `AIMLESS_SHARE = 0.2` and run the first command again: the new test fails (`… not less than or equal to …`). Set it back to 0.75.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 845 tests` … `OK` (1 new).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_survival_sim.py
git commit -m "test: goals leave fewer aimless rests and explores than before them, over the headless runs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Viewer: the goal line, the day plan and the goals reached

**Files:**
- Create: `frontend/src/survival/goals.ts`
- Modify: `frontend/src/survival/types.ts` (`goal`, `goals_reached`, `Goal`, `PlanStep`, `GoalReached`), `frontend/src/survival/hud.ts` (words for `improve_home` and `stock_larder`), `frontend/src/survival/SurvivalHud.tsx` (the goal line, its progress bar and today's plan), `frontend/src/survival/Memorial.tsx` (the goals reached)
- Test: `frontend/src/survival/goals.test.ts`

**Interfaces:**
- Consumes: Task 7's `/api/mimo` `goal` (`{name, title, why, progress, plan: [{text, done}], picker, since}` or null) and `goals_reached` on life summaries and details (`[{name, title, day}]`); `hud.purposeText`.
- Produces:
  - Types `PlanStep`, `Goal`, `GoalReached`; `SurvivalState.goal?: Goal | null`; `LifeSummary.goals_reached?` and `LifeDetail.goals_reached?: GoalReached[]`.
  - `goals.PLAN_SHOWN = 3`; `goalLine(goal) -> {label, percent} | null` ("Goal: Iron tools", 0..100); `goalHint(goal) -> string | undefined` (the why, and "Jev chose it." or "The rules chose it."); `planSteps(goal) -> PlanStep[]` (at most 3); `otherEvents(events) -> MimoEvent[]` (all but the `goal` events); `reachedLine(goal) -> string` ("A home of its own · day 2").

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/goals.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { goalHint, goalLine, otherEvents, planSteps, reachedLine } from './goals'
import { purposeText } from './hud'
import type { Goal } from './types'

const goal: Goal = {
  name: 'iron_tools', title: 'Iron tools', why: 'Stone only goes so far.', progress: 0.404, picker: 'jev', since: 10,
  plan: [
    { text: 'Find iron ore', done: true }, { text: 'Mine 3 iron ore', done: false },
    { text: 'Make an iron pickaxe', done: false }, { text: 'A fourth step', done: false },
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

  it("shows the first three steps of today's plan", () => {
    expect(planSteps(goal).map((step) => step.text)).toEqual(['Find iron ore', 'Mine 3 iron ore', 'Make an iron pickaxe'])
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
import type { Goal, GoalReached, MimoEvent, PlanStep } from './types'

/** How many steps of the day plan the HUD shows. */
export const PLAN_SHOWN = 3

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
Expected: `Tests  7 passed (7)`

- [ ] **Step 5: The goal line, its bar and today's plan on the HUD**

The goal sits under the purpose line (and the danger line, when there is one): "Goal: Iron tools" with its percent, a thin bar in a calm blue beside the vitals' greens, and up to three steps of today's plan, done ones ticked and struck through. Hovering it shows why Mimo wants it and who chose it.

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```typescript
import type { AliveResponse, CareKind } from './types'
```

with:

```typescript
import { goalHint, goalLine, planSteps } from './goals'
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
Expected: `Tests  287 passed (287)` (7 new), the build succeeds, eslint prints nothing.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 845 tests` … `OK`

- [ ] **Step 8: Commit**

```bash
git add frontend/src/survival/goals.ts frontend/src/survival/goals.test.ts frontend/src/survival/types.ts frontend/src/survival/hud.ts frontend/src/survival/SurvivalHud.tsx frontend/src/survival/Memorial.tsx
git commit -m "feat: the HUD shows Mimo's goal with a progress bar and today's plan, and the memorial the goals it reached" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Manual check on the demo and the README

This task is for the controller. It rebuilds the demo image from the branch and restarts the demo stack on its own scratch volume: `mimo-m5demo-api` (:8011) and `mimo-m5demo-worker`, volume `mimo_m5demo`, a copy of the owner's world at the natural pace (`MIMO_TIME_SCALE=1`, `MIMO_ACTION_SCALE=1`), this time with Jev's key so Jev chooses the goals (the owner: Jev calls are cheap). The owner's real stack (`pets-api-1`, `pets-mimo-worker-1`) and its volume `pets_mimo_data` are never touched, and no key is printed. The viewer runs on :3000 (:5173 is the owner's dev server). A game day is an hour at the natural pace, so the dawn checks take up to an hour: note the time of dawn from the HUD's sky dial. If a check fails, fix the code in the task that owns it, re-run that task's tests, rebuild and repeat the check.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 845 tests` … `OK`

Run: `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_sim.py"` and `MIMO_SLOW_TESTS=1 python3 -m unittest discover -s backend/tests -p "test_survival_days.py"`
Expected: `Ran 3 tests` … `OK` and `Ran 3 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine`
Expected: `Tests  287 passed (287)`, the build succeeds, eslint prints nothing.

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

- [ ] **Step 3: Keep a goal snippet and a nudge ready**

Save these in your scratchpad directory (not in the repo). `goal.sh` prints the day, phase, purpose and mood; the goal with its progress and who chose it; today's plan with the steps done; a goal choice waiting and the goals set aside; the goals reached; the model calls today; and the latest goal, plan and purpose events, oldest first:

```bash
docker exec -i mimo-m5demo-api python - <<'PY'
import time
import backend.survival.brain  # noqa: F401  (registers every goal)
from backend.survival.clock import clock_at, time_scale
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
view = goal_view(brain)
print("goal", None if view is None else f'{view["title"]}, {round(view["progress"] * 100)}%, chosen by {view["picker"]}')
for step in (view or {}).get("plan", []):
    print("  plan", "[x]" if step["done"] else "[ ]", step["text"])
print("goal due", brain.get("goal_due"), "| set aside", brain.get("goal_penalties"))
with world.connect() as db:
    print("reached", reached_rows(db))
print("model calls today", (brain.get("calls") or {}).get("model"))
for event in reversed(world.events(200)):
    if event["kind"] in ("goal", "plan", "purpose"):
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

Over half an hour of daylight, confirm most purpose events read `decided to <purpose>, toward <goal>.` for purposes of the goal's next steps (or `toward` another open goal while its own waits, as torches wait for the evening), that the HUD's purpose line matches, and that `decided to rest.` or `decided to explore.` (with no ", toward") appear only while nothing else is to be done. Confirm the goal's percent rises on the HUD as the work goes on.

- [ ] **Step 7: A goal reached**

Wait for an event `goal | <Name> reached a goal: <title>.`; if none comes by the evening and iron tools is the goal, run `iron.sh` once and note it. Confirm: the mood jumps by about 15 in `goal.sh`, the goal appears in `reached` with its time, the thought reads "I did it: …!" until the next goal's thought replaces it, a new goal is chosen at once (`set a new goal`, by Jev when more than one is open) with its own day plan, and the HUD's goal line switches to it. The event is notable: confirm it shows among the life's notable events: `curl -s http://127.0.0.1:8011/api/lives/<id>` (the id is the active life's) lists it under `notable_events` and the goal under `goals_reached` with its day, as the memorial will.

- [ ] **Step 8: A quiet worker**

Confirm the worker log stays quiet: `docker logs mimo-m5demo-worker 2>&1 | grep -c "crashed"` prints `0` (or only lines from before the restart), and that `goal.sh`'s model calls today stay within `MIMO_MAX_DECISIONS_PER_DAY` (2000). Leave the demo running on the new image for the owner.

- [ ] **Step 9: Describe purposeful life in the README**

In `README.md`, replace:

```markdown
## Current world rules
```

with:

```markdown
## Purposeful life

- **Goals.** Mimo works toward a goal for days: a home of its own first, then iron tools, armor, a full larder, a safe yard, a bigger stone home or the land around home mapped (with L3's purposes and recipes: diamond tools and a herd in a pen). A goal is a few milestones, each with its progress read from what Mimo carries, built and remembers, and the purposes that work toward it (`backend/survival/goals.py`, `life_goals.py`, `homes.py`, `larder.py`). A milestone whose purposes or recipes do not exist yet is left out until they do.
- **Choosing.** Jev chooses the goal when Mimo has none, at dawn, and when one is reached or set aside, from up to four open goals with their progress and next steps. Without Jev the rules keep the current goal and otherwise take the best, preferring one that something can be done for now. A goal whose progress has not risen for a game day is set aside at dawn for a day. Goal choices count toward the same daily cap and hourly budget as purpose choices.
- **Purposes follow it.** Purposes that advance the goal score 15 more, not past 80 and not late in the day or at night. While any purpose advances the goal or meets a need, only those are on offer, so Mimo rests or explores only when nothing else is to be done; while its goal waits (torches wait for the evening), it works toward another open goal meanwhile. With a goal, a purpose that ended as usual is chosen again by the rules, and Jev speaks at the moments that matter. A purpose event says which goal it works toward: "Pip decided to gather stone, toward iron tools."
- **Goals that need their own work.** A bigger stone home: improve_home starts a bigger shelter with cobblestone walls near home once Mimo carries half its blocks, build_shelter finishes it and Mimo moves in. A full larder: while it is the goal, a fed Mimo gathers up to 40 hunger more food than a day's worth and stock_larder puts a chest in the shelter and stores the spare food, until the chest holds a day's food. Armor: Mimo hunts for hides though fed, a few times a day.
- **A day plan.** At dawn, and when a goal is chosen, Mimo writes the next three steps toward it ("Pip's plan for today: find iron ore, mine 3 iron ore and make an iron pickaxe.") and ticks them off.
- **Reaching a goal** is a notable event ("Pip reached a goal: iron tools.") with a mood boost, and the memorial lists the goals a life reached.
- `/api/mimo` has `goal` (title, why, progress, today's plan, who chose it); lives have `goals_reached`; the model's payload has `goal`. The HUD shows "Goal: Iron tools" with a progress bar and today's plan under the purpose line.

## Current world rules
```

- [ ] **Step 10: Commit**

```bash
git add README.md
git commit -m "docs: describe purposeful life" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (L4 outline and Decisions) | Where |
|---------------------------------|-------|
| Goals are a registry: name, why, validity, progress (0–1 from state and memory), the purposes that advance them, completion | Task 1 (`goals.Goal`, `Milestone`, `register_goal`, `progress_of`, `complete`, `is_open`; resolution 3) |
| A mood reward | Task 1 (`Goal.reward`, `GOAL_MOOD`), Task 2 (`reach_goal`) |
| First shelter (M5), then a better home (a bigger tier, stone walls) | Task 4 (`first_shelter`), Task 5 (`better_home`, `improve_home`; resolution 10) |
| Iron tools, then armor | Task 4 (`iron_tools`; `armor_up` after it; iron armor with L3's recipes) |
| A full larder: a chest with food | Task 6 (`full_larder`, `stock_larder`, `more_food`) |
| A safe yard: torches, a door, a fence | Task 4 (`safe_yard`; the fence waits for a `build_fence` purpose: see spec gaps) |
| A herd: creature seeds and a pen (optional until L3) | Task 4 (`herd`, with L3's `build_pen` and `stock_pen` and the `fence` recipe; resolution 3) |
| Map the land: explore memory | Task 4 (`map_land`, `land_seen` over `memory_explored`) |
| Jev picks a goal at dawn, or when one completes or fails, from a small offered set with facts; the rules picker is the fallback | Task 2 (`tend_goal` asks at dawn, when reached or given up), Task 3 (`offers`, `prepare_goal`, `goal_route`, the `"goal"` question; resolution 7) |
| A goal lasts days, not minutes | Task 3 (the rules keep the current goal: `STICK`), Task 2 (given up only after a game day without progress; resolution 6) |
| Purposes that advance the active goal get +15; the others are capped in the leisure band unless they meet a need | Task 1 (`pickers.steer`, `goals.boosted`, `meets_need`; resolution 8) |
| Rest and explore are chosen only when nothing advances the goal or a need | Task 1 (`steer` offers only goal and need purposes while any exist; `toward` works toward another goal while the goal waits), Task 8 (the headless check) |
| A day plan at dawn lists the goal's next steps, shown in the HUD | Task 2 (`day_plan`, the `plan` event), Task 7 (`goal_view`'s plan), Task 9 (the HUD's plan) |
| Completing a goal is a notable event with a mood boost | Task 2 (`reach_goal`: a `goal` event, not routine) |
| The HUD shows the goal and its progress bar | Task 9 (`goalLine`, `SurvivalHud`) |
| The memorial lists the goals reached | Task 7 (`goals_reached` on lives), Task 9 (`Memorial`, `reachedLine`) |
| The Jev (and Luna) payload carries the goal context | Task 7 (`context_payload`'s `goal`), Task 3 (the goal question's `goals_reached`), Task 1 (criteria and instructions name the goal) |
| `/api/mimo` gains `goal` | Task 7 (`brain_view`'s `goal`) |
| Cost: no model calls inside the tick; goal picks follow the purpose picks' cost rules | Task 2 (the tick decides nothing by model), Task 3 (goal calls count toward the daily cap and Jev's hourly budget; resolutions 7, 9) |
| Error handling: crashes logged once, the tick model-free, GETs read-only, migrations idempotent (none added), the headless sims green with the milestone's own sim check | Tasks 1–3 (`log_once` guards), Task 7 (a GET writes nothing), Tasks 4–6 (slow sims), Task 8 (the aimless check) |
| Fewer aimless loops, measured as purpose changes per game hour against today's baseline | Task 8 (aimless changes per game hour: 4.25 → 1.5, 5.44 → 3.06 in slow mode; resolution 14) |

Spec gaps the plan fills or leaves (the controller ledgers them):
- The spec names no goal list beyond its examples, no progress formula, no day-plan length and no numbers for "a small offered set", "lasts days" or the mood boost: resolutions 3–7 set them (milestones and their mean, 3 steps, 4 goals, the current goal kept by the rules and given up after a game day without progress, +15 mood).
- "Capped in the leisure band": the spec gives no cap. While anything advances the goal or meets a need, the other purposes are left out of the choice altogether (below any cap), which also keeps Jev's pick on the goal; when nothing does, they keep their own scores (resolution 8).
- A safe yard's fence: L3's draft plan builds fences only as a pen's ring and has no yard fence, so the fence step waits for a `build_fence` purpose that no plan adds yet.
- Iron tools stop at the iron pickaxe: mine_ore wants only the iron a pickaxe takes (an iron sword would need its own change to `work.wanted_ores`, which L3's draft also edits).
- Goal choices use Jev only; Luna (capped and costly) never chooses goals.
