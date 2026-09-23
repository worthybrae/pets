# Survival M3: The Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the survival pet a brain: reflexes that take over in an emergency, purposes it chooses between (by Jev, Luna or a rule-based utility picker), a planner that turns each purpose into M2 steps, a memory of places and recipes, and a viewer that shows the purpose and thought and replays short steps.

**Architecture:** The tick stays model-free. New modules in `backend/survival/` plug into the M2 action engine through a `Mind` (planner, interrupt, observe and notice hooks): `brain` (purposes into batches of steps, re-plan once, reports, triggers, discoveries), `reflexes` (data-driven takeovers), `purposes` + `work` + `toolmaking` (the purpose registry and M3's purposes), `escape` (trapped detection and a staircase out), `memory` (places and recipes in the world database) and `triggers` (the brain's saved state). The worker ticks the world, then `choosing.Chooser` answers a pending trigger outside the write transaction: the utility picker at once, or Jev/Luna in a background thread with a timeout, then a short transaction stores the choice unless the state moved on. The viewer draws the pet 1.5 s behind server time from the current and finished steps.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`, `urllib`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-23-survival-core-design.md` (M3: section 5 including "Carried from the M2 review", and the M3 parts of sections 9–13). It builds on `docs/superpowers/plans/2026-09-23-survival-m2-physical-mimo.md`; the code on branch `worthy/23_09_2026/survival_core` at `aef431b` is the "old" text every task edits.

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest` and call functions directly. Never import `backend.main` in a test (it needs `redis`, which is not installed locally).
- Tests never make real network or model calls. Model code takes an injected `http` function; tests pass fakes. The worker's background thread is replaced in tests by `InlineExecutor`.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props, state or hook arguments (mutate three.js objects only through refs inside `useFrame`, effects or event handlers), no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Viewer logic that needs tests lives in `.ts` modules, not in components.
- SQLite: WAL, `BEGIN IMMEDIATE` for writes (`SurvivalWorld.transaction()`), `busy_timeout`. Read-only GETs never write. Schema setup runs at most once per process per path (`_ensure_world_schema`). The legacy world file is only ever opened read-only.
- **No model call inside the tick.** The tick only marks a pending trigger and turns the stored purpose into steps. The worker calls a picker outside the world's write transaction, then stores the choice in a short transaction, discarding it if the life died or the state moved on. While a choice is pending, the pet keeps doing its current plan, or waits.
- Planners and reflexes get the tick's `ActionContext` and count their own path searches against the same budget of 2 per tick (`take_search`).
- A crashing planner, reflex, hook or picker never stops a tick or the worker. Crashes are logged once per distinct error (`backend.survival.once.log_once`).
- Values copied from the spec: reflex triggers surface = air < 40, avoid drop = the next step would fall more than 3 blocks or into lava, eat now = hunger < 15 with food, warm up = warmth < 25, head home = dusk within 3 game minutes and outdoors with a known shelter within 64 blocks, collapse = energy < 10 (flee belongs to sub-project 3); purpose triggers = a plan finished or failed, a reflex ended, a vital crossed 50, 30 or 15, dawn or dusk, a new discovery, an owner hello, one game hour since the last choice; at least 60 real seconds between model calls except for vital crossings; Luna reflections at most 12 per real day; a failed step re-plans the purpose once and a second failure reports back as a trigger; a purpose that failed is scored lower for 10 game minutes; failure codes `no_path`, `out_of_reach`, `gone`, `missing_item`, `blocked`, `bad_step`; trapped = two walk failures in a row with no route out; the viewer draws Mimo about 1.5 s behind server time.
- `MIMO_TIME_SCALE` speeds the clock and vitals (M1). `MIMO_ACTION_SCALE` (default 1, test-only) divides step durations (Task 3). Both are for manual runs only.
- Never run `docker` or `docker compose` in Tasks 1–15. Task 16 is the controller's manual check on a scratch volume; never touch, mount or migrate the owner's real volume `pets_mimo_data`.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (227 pass at `aef431b`)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_brain.py" -v`
- Frontend tests: `cd frontend && npm test` (143 pass at `aef431b`)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint <paths>`

Each task says how many tests it adds. If the real starting totals differ, expect the same increases on top of them.

## Plan-level resolutions

The spec leaves these open or ambiguous. Every task follows them; the controller ledgers them.

1. **Game time units.** "Game minute" and "game hour" count game seconds (60 and 3,600), the same unit as the phase table. So "one game hour since the last choice" is 3,600 game seconds, "10 game minutes" is 600 and "dusk within 3 game minutes" is 180. This is the only reading that fits "3–8 calls per game hour" with a 60 s gap. The HUD's 24-hour dial is display only.
2. **Home before M5.** Home is a remembered sheltered cell. Whenever the tick's M1 shelter check finds Mimo sheltered, it remembers the cell: the first one is `home` (logged as a discovery), later ones are `shelter` (ignored within 8 blocks of a known one). `go_home` and head home walk to the nearest `home` or `shelter` within 64 blocks; with none known they are not offered. The staircase that `gather_stone` digs becomes a sheltered tunnel from its third stair, so most pets find a home on day 1.
3. **Eating.** `steps.FOOD` and the `eat` step exist, so the `eat` purpose and the eat-now reflex are registered. Nothing in the world yields food until M4, so they stay dormant; tests give Mimo berries.
4. **Not registered in M3:** `forage`, `fish`, `farm`, `cook`, `build_shelter`, `build_farm`, `build_storage`, `light_up` (their blocks and steps arrive in M4/M5), and the flee reflex (sub-project 3, priority 30 is left free for it). They add themselves later with `purposes.register` and `reflexes.register`.
5. **A purpose is a goal.** Its planner returns the next batch of steps; the brain asks again when a batch runs out, and `[]` means the purpose is finished (goal met or impossible), which is the "plan finished" trigger. `gather_wood` runs until 8 logs' worth of wood, `gather_stone` until 12 cobblestone (then on while prospecting for iron), `mine_ore` until no reachable coal or iron sighting is left, `craft_tools` until the next pickaxe is made, `explore`, `rest` and `eat` are one batch, `go_home` up to 3 batches, `sleep` until it is no longer valid.
6. **Choosing flow.** The tick marks `brain.pending`; after each tick the worker's `Chooser` answers it. With no model allowed it stores the utility choice at once. Otherwise it sends the model call to one background thread and keeps ticking; when the call returns (or fails, falling back to utility) it stores the result. While pending, the brain plans 1 s waits.
7. **The 60 s gap.** A trigger that arrives less than 60 real seconds after the last model call, and is not a vital crossing, is answered by the utility picker at once instead of waiting, so Mimo is never idle for the gap.
8. **Vital crossings** are health, hunger, warmth or energy falling past 50, 30 or 15. They are urgent: they bypass the gap and make an answer still in flight stale. Other triggers merge into a pending choice without making it stale.
9. **Stale choices.** A stored answer is discarded when the life died, nothing is pending any more, or the pending id changed (an urgent trigger came in). Its model calls still count toward the caps.
10. **Picker order.** Jev when `TYPESAFE_API_KEY` is set, else Luna when `MIMO_MODEL_API_KEY` or `OPENAI_API_KEY` is set, else utility. The utility picker also answers when a cap is spent, inside the gap, or when a call fails or returns a purpose that was not offered (logged once per distinct error).
11. **Caps.** `MIMO_MAX_DECISIONS_PER_DAY` (default 8000) counts Jev and Luna picks; `MIMO_MAX_LUNA_DECISIONS_PER_DAY` (default 64) counts every Luna call (picks and reflections). Counters live per life in `state["brain"]["calls"]` and reset each UTC day.
12. **Reflections.** At most 12 per UTC day, only for choices triggered by dawn, a hello or a discovery, only with a Luna key, and only when both caps allow. The reflection rides with its decision (the 60 s gap is between decisions). Otherwise the thought comes from the purpose's templates.
13. **Timeouts.** Jev 20 s, Luna 45 s, the same as the old brain in `live_mimo.py`. Request shapes, headers and env vars (`TYPESAFE_API_URL`, `TYPESAFE_MODEL`, `MIMO_MODEL`, `MIMO_MODEL_URL`) are the old ones; Luna's strict structured output uses `json_schema` with the purpose as an enum of the offered names.
14. **Reflex check points.** Before every step start, and at every advance while a walk, sleep or wait is running (the spec's "a walk snaps to the last cell it reached" needs walks to be interruptible). Mine, place, eat, craft and smelt last at most 5 s and finish first.
15. **Interrupted steps** are recorded with `result: "interrupted"` and `reason` = the reflex or hazard name. M2's hazard records (`failed`, `"interrupted: fall"`) change to (`interrupted`, `"fall"`). Interruptions are not failures and do not touch `last_failure`.
16. **Reflex takeover.** A reflex fires only when its trigger holds and its planner returns steps. It preempts only a less urgent running reflex. The first takeover sets the purpose's queue aside (a cut walk is re-queued toward its target); when the reflex's steps run out the set-aside steps come back and a `reflex_ended` trigger asks for a new choice. Each reflex has a cooldown (surface 3 s, eat now 5 s, warm up 30 s, head home 60 s, collapse 30 s, real seconds). `avoid_drop` is a veto, not a takeover of the plan: a queued mine of the block under Mimo that would drop it more than 3 blocks (or into lava) fails with code `blocked`; a running walk whose next cell lost its support over such a drop is cut and walked again toward the same target. A fresh path search never enters a cell that is not standable and never drops more than 3 or into lava, so the new route already has "that cell blocked". Both record a `danger` place.
17. **Surface.** M2's swim-straight-up hazard stays as the physical part. The surface reflex mines a ceiling that holds Mimo under water, or walks to the nearest shore cell once its head is above water.
18. **Warm up.** No campfire item exists before M4, but a furnace counts as a fire for warmth (M1). So warm up places a carried furnace beside Mimo, or walks to the nearest remembered home, shelter or placed furnace within 64 blocks. With neither it does not fire.
19. **Head home window:** from 180 game seconds before dusk (2,040 s into the day) until night (2,400 s), when Mimo is not sheltered, is more than 2 blocks from the nearest shelter within 64 blocks, and its purpose is not already `go_home` or `sleep`.
20. **Failure codes:** `no way there` → `no_path`; `out of reach` → `out_of_reach`; mined block changed → `gone`; missing item, material, food, pickaxe or station → `missing_item`; unmineable block, occupied cell, own cell, `path blocked` → `blocked`; everything else → `bad_step`. `state["last_failure"]` keeps code, reason, kind, cell, purpose and time.
21. **Re-plan once.** A failure in a batch re-plans the purpose once. A second failure first checks for a trap; if not trapped it reports (`plan_failed` trigger) and the purpose scores 30 lower for 600 game seconds.
22. **Trapped** = the last two recorded walks failed with `no_path` and a flood fill of Mimo's moves exhausts fewer than 256 cells (one search from the budget). The escape is a staircase up: mine the headroom and stair cells, place a carried block where a stair has no support (this is the spec's "pillar up with a block it carries"), up to 24 stairs, until Mimo stands above the natural surface. One try per 60 real seconds. There is no jump step, so a 1-wide shaft in rock Mimo cannot mine stays a trap.
23. **Portable stations.** `craft_tools` places a crafting table (and, for iron, a furnace) beside Mimo, crafts or smelts, then mines the station back into its inventory. No station memory is needed.
24. **Tool ladder:** wooden pickaxe → stone pickaxe → iron pickaxe (furnace and smelting three iron ore are part of the iron step). Only the next missing tool is offered.
25. **Gathering stone** digs a staircase down from where Mimo stands (2 blocks per stair) and turns into a level tunnel 10 blocks under the surface or at y −3. It stops at water, lava, bedrock, caves and blocks it cannot mine. With a stone pickaxe, iron still wanted and no iron ore seen, it stays on offer past 12 cobblestone (prospecting, a lower score), so Mimo can reach the iron pickaxe.
26. **Ores.** After every mine, Mimo looks at the 26 cells around the mined block and remembers ores it sees. `mine_ore` goes for coal and iron it can harvest within 48 blocks; copper is remembered but not mined yet.
27. **Discoveries that trigger a choice:** the first home, the first sighting of each ore material and the first water body. Other places are remembered silently. Typed events: `found` (ore), `discovered` (home, water), `trapped`, `purpose` (a choice with its thought), `reflex`.
28. **MIMO_ACTION_SCALE** divides walk and swim path times, mining, placing, eating, crafting and smelting. Waits (they time things against the clock), sleep (no fixed end) and falls (physics) are not scaled.
29. **Replay.** Finished walk, swim and fall entries keep their timed `path`; only the newest 4 recent entries keep it, to keep the saved state small. The viewer replays both the pet and its block effects 1.5 s behind server time; the HUD text is not delayed.
30. **API names.** §10 names no fields for the brain, so `/api/mimo` adds flat `purpose`, `reflex`, `picker` and `choosing` next to `last_thought` (the thought). `action` and `recent_actions` keep their M2 shapes; recent entries may now carry `path`, `code` and `purpose`, and `result` may be `"interrupted"`.
31. **Planner signature.** Planners become `(state, context, at)`, where `context` is the tick's `ActionContext` (grid, clock, events, search budget, db). `tick_life`, `advance_world` and `run_once` take a `mind` instead of a `planner`.
32. **Rest and waiting.** `rest` waits 60 game seconds (at least 1 real second). A pending choice waits 1 real second at a time. M1's `rest_plan` stays as the default mind and the crash fallback.
33. **Utility picker:** the highest score wins after adding `random.uniform(0, 6)`; scores come from each purpose (needs first, then traits: curiosity, diligence, bravery, caution, patience, thrift), minus 30 while penalized.
34. **The interim script goes.** `scripted_plan` and its tests are deleted once the worker runs the brain (Task 13); `trees_near` moves to `backend/survival/senses.py`.
35. **Unreachable home.** When `go_home` fails twice with `no_path`, the home or shelter it aimed for is forgotten, so the next sheltered spot Mimo finds becomes home. `sleep` sleeps where Mimo stands once its walk to a nearby shelter failed.
36. **Failure identity.** `last_failure` carries a `seq` counter, so two alike failures at the same moment still count as two (the re-plan-once rule depends on it).

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/survival/once.py` | Create | `log_once`: log a crash once per distinct error |
| `backend/survival/actions.py` | Modify | Planner signature `(state, context, at)`, `observe`/`interrupt` hooks, `take_search`, failure codes and `last_failure`, `interrupted` results, `purpose` tags, action scale, finished paths |
| `backend/survival/steps.py` | Modify | `StepFailed.code`, `failure_code`, `scale` on `start_step`, `avoid` cells on walks |
| `backend/survival/pathing.py` | Modify | `scale` on `timed_path`, `avoid` cells in `moves`/`find_path`/`route` |
| `backend/survival/clock.py` | Modify | `action_scale()` from `MIMO_ACTION_SCALE` |
| `backend/survival/tick.py` | Modify | `Mind` (plan, interrupt, observe, notice), `RESTING`, `mind` and `action_scale` parameters |
| `backend/survival/script.py` | Modify | `rest_plan` takes the context; `scripted_plan` deleted in Task 13 |
| `backend/survival/memory.py` | Create | Places and recipes in the world database |
| `backend/survival/triggers.py` | Create | The brain's saved state: `ensure_brain`, `mark_trigger`, crossings, phase and hour triggers |
| `backend/survival/world.py` | Modify | Memory tables in the schema; a hello marks a trigger |
| `backend/survival/situation.py` | Create | `Situation`: state, grid, clock, time and lazily read memory |
| `backend/survival/senses.py` | Create | Trees, standing logs, ore scan, shelter lookups, flood fill |
| `backend/survival/purposes.py` | Create | `Purpose`, the registry, `offered`, and rest, sleep, explore, go_home, eat |
| `backend/survival/work.py` | Create | gather_wood, gather_stone (staircase), mine_ore |
| `backend/survival/toolmaking.py` | Create | craft_tools: recipe chains, portable stations, smelting |
| `backend/survival/brain.py` | Create | `brain_plan`, failures and reports, `observe_step`, `notice_step`, `BRAIN` mind |
| `backend/survival/escape.py` | Create | Trapped detection and the staircase out |
| `backend/survival/reflexes.py` | Create | `Reflex`, the registry, six reflexes, `reflex_hook` |
| `backend/survival/pickers.py` | Create | Utility picker, thoughts, the model context payload |
| `backend/survival/models.py` | Create | Jev and Luna calls (injected HTTP), reflections |
| `backend/survival/choosing.py` | Create | `Chooser`: snapshot, route, background call, store the choice, counters |
| `backend/survival/snapshot.py` | Modify | `purpose`, `reflex`, `picker`, `choosing` in the survival view; routine events |
| `backend/workers/mimo_worker.py` | Modify | Runs `BRAIN` and a `Chooser` after each tick |
| `backend/tests/test_survival_*.py` | Create/Modify | One test file per new module, updates to existing ones |
| `frontend/src/survival/types.ts` | Modify | Brain fields, `interrupted`, finished paths |
| `frontend/src/survival/hud.ts` (+ test) | Modify | `purposeText` |
| `frontend/src/survival/replay.ts` (+ test) | Create | `REPLAY_DELAY`, `replayAt` |
| `frontend/src/survival/SurvivalPet.tsx`, `ActionEffects.tsx`, `WorldCanvas.tsx`, `SurvivalHud.tsx`, `SurvivalWorld.tsx` | Modify | Replay 1.5 s behind; purpose and thought in the HUD |
| `README.md`, `.env.example`, `docker-compose.yml` | Modify | The brain, `MIMO_ACTION_SCALE` |

## Tasks

1. The mind seam: planner signature, observe and notice hooks, crash logs once
2. Failure codes, interrupted results and purpose tags
3. Action speed scale and finished paths for replay
4. The interrupt hook
5. Memory and the brain's saved state
6. Situation, the purpose registry and the simple purposes
7. Gathering purposes: wood, stone and ore
8. Crafting tools with portable stations
9. The brain in the tick
10. Trapped: a staircase out
11. Reflexes
12. Pickers: utility, Jev and Luna
13. Choosing in the worker
14. Stream the brain from `/api/mimo`
15. Viewer: purpose, thought and replay
16. Manual check at 60× and the README

---

### Task 1: The mind seam: planner signature, observe and notice hooks, crash logs once

**Files:**
- Create: `backend/survival/once.py`
- Modify: `backend/survival/actions.py`, `backend/survival/tick.py`, `backend/survival/script.py`, `backend/workers/mimo_worker.py`
- Test: `backend/tests/test_survival_actions.py`, `backend/tests/test_survival_script.py`, `backend/tests/test_survival_tick_actions.py`

**Interfaces:**
- Consumes: M2's `ActionContext`, `advance_actions`, `advance_world`, `tick_life`, `run_once`, `rest_plan`, `scripted_plan`.
- Produces:
  - `backend.survival.once`: `log_once(logger: logging.Logger, where: str, error: BaseException) -> bool`, `forget_logged() -> None`.
  - `backend.survival.actions`: `Planner = Callable[[dict, ActionContext, float], list[dict]]`, `Observe = Callable[[dict, dict, ActionContext, float], None]` (state, finished step, context, time); `ActionContext` gains `observe: Observe | None = None` and `db: sqlite3.Connection | None = None`; `take_search(context: ActionContext) -> bool`; `safe_plan(context, state, at) -> list[dict]`.
  - `backend.survival.tick`: `Notice = Callable[[dict, ActionContext, dict, Surroundings, float, float], None]` (state, context, vitals before, surroundings, step start, step end); `@dataclass(frozen=True) class Mind` with `plan: Planner = rest_plan`, `observe: Observe | None = None`, `notice: Notice | None = None`; `RESTING = Mind()`; `advance_world(world, timestamp, scale, mind: Mind = RESTING) -> dict`; `tick_life(registry, timestamp=None, scale=None, mind: Mind = RESTING) -> dict | None`.
  - `backend.survival.script`: `rest_plan(state, context, at) -> list[dict]`, `scripted_plan(state, context, at) -> list[dict]`.
  - `backend.workers.mimo_worker`: `WORKER_MIND: Mind`, `run_once(registry, previous, timestamp=None, mind: Mind = RESTING) -> str`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_actions.py`, replace the imports:

```python
from backend.survival import steps as steps_module
from backend.survival.actions import ActionContext, activity_of, advance_actions, ensure_actions
from backend.survival.grid import Grid
from backend.survival.steps import start_step
from backend.survival.vitals import START_VITALS
```

with:

```python
import logging

from backend.survival import steps as steps_module
from backend.survival.actions import ActionContext, activity_of, advance_actions, ensure_actions, take_search
from backend.survival.grid import Grid
from backend.survival.once import forget_logged, log_once
from backend.survival.steps import start_step
from backend.survival.vitals import START_VITALS
```

Replace `Plans.__call__`:

```python
    def __call__(self, state, grid, at, clock):
```

with:

```python
    def __call__(self, state, context, at):
```

In `test_a_crashing_planner_falls_back_to_rest_and_the_tick_keeps_going`, replace:

```python
        def broken(state, grid, at, clock):
            raise RuntimeError("boom")

        state = pet()
```

with:

```python
        def broken(state, context, at):
            raise RuntimeError("boom")

        forget_logged()
        state = pet()
```

In `test_a_non_list_of_dicts_plan_falls_back_to_rest_too`, replace:

```python
            def bad_planner(state, grid, at, clock, result=bad_result):
```

with:

```python
            def bad_planner(state, context, at, result=bad_result):
```

Add these tests at the end of `ActionEngineTests`:

```python
    def test_observe_hears_every_step_that_finished_well(self):
        heard = []
        state = pet(inventory={"planks": 1})
        state["queue"] = [{"kind": "place", "target": [1, 1, 0], "block": "planks"},
                          {"kind": "mine", "target": [9, 1, 0]}]
        ctx = context(small_world())
        ctx.observe = lambda state, step, context, at: heard.append((step["kind"], at))
        advance_actions(state, ctx, 1.0)
        self.assertEqual(heard, [("place", 0.3)])  # the mine failed (out of reach), so it is not heard

    def test_a_crashing_observer_is_logged_once_and_the_steps_still_count(self):
        def broken(state, step, context, at):
            raise RuntimeError("boom")

        forget_logged()
        state = pet(inventory={"planks": 2})
        state["queue"] = [{"kind": "place", "target": [1, 1, 0], "block": "planks"},
                          {"kind": "place", "target": [0, 1, 1], "block": "planks"}]
        ctx = context(small_world())
        ctx.observe = broken
        with self.assertLogs("backend.survival.actions", level="ERROR") as logs:
            advance_actions(state, ctx, 1.0)
        self.assertEqual(len(logs.output), 1)
        self.assertEqual([entry["result"] for entry in state["recent_actions"]], ["done", "done"])

    def test_a_planner_that_keeps_crashing_is_logged_once(self):
        def broken(state, context, at):
            raise RuntimeError("boom")

        forget_logged()
        with self.assertLogs("backend.survival.actions", level="ERROR") as logs:
            for until in (1.0, 2.0, 3.0):
                advance_actions(pet(), context(small_world(), broken), until)
        self.assertEqual(len(logs.output), 1)

    def test_take_search_spends_the_shared_budget(self):
        ctx = context(small_world())
        self.assertEqual([take_search(ctx), take_search(ctx), take_search(ctx)], [True, True, False])
        self.assertEqual(ctx.searches_left, 0)


class OnceLogTests(unittest.TestCase):
    def test_each_distinct_error_is_logged_once(self):
        forget_logged()
        logger = logging.getLogger("once-test")
        with self.assertLogs("once-test", level="ERROR") as logs:
            self.assertTrue(log_once(logger, "planner", RuntimeError("boom")))
            self.assertFalse(log_once(logger, "planner", RuntimeError("boom")))
            self.assertTrue(log_once(logger, "planner", RuntimeError("bang")))
            self.assertTrue(log_once(logger, "observe", RuntimeError("boom")))
        self.assertEqual(len(logs.output), 3)
        self.assertTrue(logs.output[0].startswith("ERROR:once-test:planner crashed: boom"))
```

Replace the whole of `backend/tests/test_survival_script.py` with:

```python
import unittest
from unittest.mock import patch

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.script import rest_plan, scripted_plan
from backend.survival.vitals import START_VITALS

MORNING = {"phase": "day", "seconds_into_day": 1200.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}
TREE = (5, 0, 0)  # trunk x, trunk z, ground height: logs at y 1 to 4
NO_TREES_THOUGHT = "No trees here. I'll look further out."


def forest(cells=None):
    """Flat stone with one oak trunk at x=5, z=0 (logs at y 1 to 4), with `cells` overriding single cells."""
    cells = cells or {}

    def rule(x, y, z):
        if (x, y, z) in cells:
            return cells[(x, y, z)]
        if (x, z) == (5, 0) and 1 <= y <= 4:
            return "oak_log"
        return "stone" if y <= 0 else "air"

    return Grid(rule)


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def ctx(clock, grid=None):
    """An ActionContext frozen at `clock`, over `grid` (the forest when None)."""
    return ActionContext(grid=grid or forest(), clock_at=lambda at: clock, planner=rest_plan, events=[])


class RestPlanTests(unittest.TestCase):
    def test_sleeps_at_night_or_when_exhausted(self):
        self.assertEqual(rest_plan(pet(), ctx(NIGHT), 0.0),
                         [{"kind": "sleep", "thought": "It's dark. Time to curl up and sleep."}])
        tired = pet(vitals={**START_VITALS, "energy": 5.0})
        self.assertEqual(rest_plan(tired, ctx(MORNING), 0.0)[0]["thought"], "I'm too tired to keep my eyes open.")

    def test_waits_for_nightfall_at_most_a_minute_at_a_time(self):
        self.assertEqual(rest_plan(pet(), ctx(MORNING), 0.0), [{"kind": "wait", "seconds": 60.0}])
        dusk = {**MORNING, "phase": "dusk", "seconds_into_day": 2390.0}
        self.assertEqual(rest_plan(pet(), ctx(dusk), 0.0)[0]["seconds"], 10.0)
        fast = {**MORNING, "seconds_into_day": 2399.5, "time_scale": 60.0}
        self.assertEqual(rest_plan(pet(), ctx(fast), 0.0)[0]["seconds"], 1.0)


@patch("backend.survival.script.trees_near", lambda seed, x, z, radius: [TREE])
class ScriptedPlanTests(unittest.TestCase):
    def test_walks_to_the_nearest_tree_and_chops_it_bottom_up(self):
        plan = scripted_plan(pet(), ctx(MORNING), 0.0)
        self.assertEqual(plan[0], {"kind": "walk", "target": [5, 1, 0], "reach": 2.0,
                                   "thought": "That tree has good wood."})
        self.assertEqual([step["target"] for step in plan[1:]], [[5, 1, 0], [5, 2, 0], [5, 3, 0], [5, 4, 0]])
        self.assertEqual({step["kind"] for step in plan[1:]}, {"mine"})

    def test_logs_become_planks_before_more_chopping(self):
        plan = scripted_plan(pet(inventory={"oak_log": 2}), ctx(MORNING), 0.0)
        self.assertEqual(plan, [{"kind": "craft", "recipe": "planks", "thought": "Logs make good planks."}])

    def test_skips_chopped_logs_and_trees_where_a_step_failed(self):
        chopped = forest({(5, 1, 0): "air", (5, 2, 0): "air"})
        self.assertEqual([step["target"] for step in scripted_plan(pet(), ctx(MORNING, chopped), 0.0)[1:]],
                         [[5, 3, 0], [5, 4, 0]])
        failed = pet()
        failed["recent_actions"] = [{"kind": "walk", "started_at": 0.0, "ended_at": 0.0, "result": "failed",
                                     "target": {"x": 5, "y": 1, "z": 0}, "reason": "no way there"}]
        self.assertEqual(scripted_plan(failed, ctx(MORNING), 0.0)[0]["thought"], NO_TREES_THOUGHT)

    def test_sleep_comes_first_at_night(self):
        self.assertEqual(scripted_plan(pet(), ctx(NIGHT), 0.0)[0]["kind"], "sleep")

    def test_without_trees_it_walks_out_in_the_day_s_direction(self):
        with patch("backend.survival.script.trees_near", lambda seed, x, z, radius: []), \
                patch("backend.survival.script.terrain_height", lambda x, z, seed: 0):
            plan = scripted_plan(pet(), ctx({**MORNING, "day_number": 2}), 0.0)
        self.assertEqual(plan, [{"kind": "walk", "target": [-48, 1, 0], "reach": 3.0, "thought": NO_TREES_THOUGHT}])


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_tick_actions.py`, replace:

```python
from backend.survival.script import scripted_plan
from backend.survival.tick import tick_life
```

with:

```python
from backend.survival.once import forget_logged
from backend.survival.script import scripted_plan
from backend.survival.tick import Mind, tick_life
```

Replace:

```python
        state = tick_life(self.registry, BORN + 120, scale=1, planner=scripted_plan)
```

with:

```python
        state = tick_life(self.registry, BORN + 120, scale=1, mind=Mind(plan=scripted_plan))
```

Replace:

```python
    def test_the_worker_runs_the_interim_script(self):
        self.assertIs(mimo_worker.WORKER_PLANNER, scripted_plan)
```

with:

```python
    def test_the_worker_runs_the_interim_script(self):
        self.assertIs(mimo_worker.WORKER_MIND.plan, scripted_plan)
```

In `test_a_crashing_planner_never_freezes_the_life`, replace:

```python
        def broken(state, grid, at, clock):
            raise RuntimeError("boom")

        state = tick_life(self.registry, BORN + 5, scale=1, planner=broken)
        self.assertIsNone(state["died_at"])
        self.assertEqual(state["last_tick_at"], BORN + 5)
        again = tick_life(self.registry, BORN + 10, scale=1, planner=broken)
```

with:

```python
        def broken(state, context, at):
            raise RuntimeError("boom")

        state = tick_life(self.registry, BORN + 5, scale=1, mind=Mind(plan=broken))
        self.assertIsNone(state["died_at"])
        self.assertEqual(state["last_tick_at"], BORN + 5)
        again = tick_life(self.registry, BORN + 10, scale=1, mind=Mind(plan=broken))
```

Add these tests at the end of `TickActionTests`:

```python
    def test_a_mind_notices_every_vitals_step(self):
        seen = []

        def notice(state, context, before, surroundings, since, at):
            self.assertIsNotNone(context.db)
            seen.append((round(since - BORN), round(at - BORN), before["hunger"] > state["vitals"]["hunger"]))

        tick_life(self.registry, BORN + 150, scale=1, mind=Mind(notice=notice))
        self.assertEqual(seen, [(0, 60, True), (60, 120, True), (120, 150, True)])

    def test_a_crashing_notice_is_logged_once_and_never_freezes_the_life(self):
        def broken(*args):
            raise RuntimeError("boom")

        forget_logged()
        with self.assertLogs("backend.survival.tick", level="ERROR") as logs:
            state = tick_life(self.registry, BORN + 150, scale=1, mind=Mind(notice=broken))
        self.assertEqual(state["last_tick_at"], BORN + 150)
        self.assertEqual(len(logs.output), 1)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_*.py"`
Expected: errors, starting with `ModuleNotFoundError: No module named 'backend.survival.once'`.

- [ ] **Step 3: Add the log-once helper**

Create `backend/survival/once.py`:

```python
"""Log a crash once per distinct error instead of on every tick.

The worker ticks every second, so an error that repeats (a planner that keeps crashing on the
same state, a model endpoint that stays down) would otherwise fill the log. `log_once` writes the
traceback the first time each (where, error type, message) happens and stays quiet for repeats.
"""

from __future__ import annotations

import logging

SEEN_LIMIT = 256
_seen: dict[str, None] = {}


def log_once(logger: logging.Logger, where: str, error: BaseException) -> bool:
    """Log `error` with its traceback the first time it happens `where`. Returns True when it logged."""
    key = f"{where}|{type(error).__name__}: {error}"
    if key in _seen:
        return False
    _seen[key] = None
    if len(_seen) > SEEN_LIMIT:
        del _seen[next(iter(_seen))]
    logger.error("%s crashed: %s", where, error, exc_info=error)
    return True


def forget_logged() -> None:
    """Forget every logged error. Tests call it so one test's errors do not silence another's."""
    _seen.clear()
```

- [ ] **Step 4: Change the engine's planner signature and add the observer**

In `backend/survival/actions.py`, replace the module docstring's second paragraph:

```python
A crashing planner, or one returning something other than a list of dicts, is logged once and
replaced with rest_plan for that call; a step that fails to start or finish in some unexpected
```

with:

```python
A crashing planner, or one returning something other than a list of dicts, is logged once per
distinct error and replaced with rest_plan for that call; a step that fails to start or finish in some unexpected
```

Replace the imports:

```python
import logging
import math
from dataclasses import dataclass
from typing import Callable
```

with:

```python
import logging
import math
import sqlite3
from dataclasses import dataclass
from typing import Callable
```

and add after `from backend.survival.grid import Cell, Grid`:

```python
from backend.survival.once import log_once
```

Replace:

```python
Event = tuple[float, str, str]
Planner = Callable[[dict, Grid, float, dict], list[dict]]


@dataclass
class ActionContext:
    """What advance_actions needs besides the state: the world, the game clock, a planner, an event list.

    `searches_left` is one path-search budget shared by every advance_actions call made from the
    same advance_world call (it is created once per tick and mutated down as walks start), so a
    long catch-up cannot run more than MAX_SEARCHES_PER_TICK searches in one write transaction.
    """

    grid: Grid
    clock_at: Callable[[float], dict]
    planner: Planner
    events: list[Event]
    searches_left: int = MAX_SEARCHES_PER_TICK
```

with:

```python
Event = tuple[float, str, str]
# A planner gets the state, the tick's ActionContext and the time, and returns the next steps.
Planner = Callable[[dict, "ActionContext", float], list[dict]]
# An observer hears about each step that finished well: (state, finished step, context, time).
Observe = Callable[[dict, dict, "ActionContext", float], None]


@dataclass
class ActionContext:
    """What advance_actions needs besides the state: the world, the game clock, a planner, an event list.

    `searches_left` is one path-search budget shared by every advance_actions call made from the
    same advance_world call (it is created once per tick and mutated down as walks start), so a
    long catch-up cannot run more than MAX_SEARCHES_PER_TICK searches in one write transaction.
    Planners that search themselves spend it through `take_search`. `observe` hears about every
    step that finished well. `db` is the world's connection inside the tick's transaction, for
    minds that keep memory; tests without a database leave it None.
    """

    grid: Grid
    clock_at: Callable[[float], dict]
    planner: Planner
    events: list[Event]
    searches_left: int = MAX_SEARCHES_PER_TICK
    observe: Observe | None = None
    db: sqlite3.Connection | None = None


def take_search(context: ActionContext) -> bool:
    """Spend one path search from the tick's budget. False when none is left this tick."""
    if context.searches_left <= 0:
        return False
    context.searches_left -= 1
    return True
```

Replace the whole `finish` function:

```python
def finish(state: dict, step: dict, context: ActionContext, at: float) -> bool:
    """Apply a step that ended at `at`. Returns True when it killed Mimo."""
    grid, events = context.grid, context.events
    if step["kind"] == "fall":
        record(state, step, at, "done")
        return finish_fall(state, step, grid, at, events)
    if step["kind"] == "swim":
        state["position"] = position_of(step["path"][-1])
        record(state, step, at, "done")
        return False
    try:
        event = finish_step(step, state, grid, at)
    except (ValueError, KeyError) as error:
        fail(state, step, at, str(error))
        return False
    except Exception:
        logger.exception("finish_step crashed on %r", step)
        fail(state, step, at, "bad step")
        return False
```

(up to and including that `return False`) with:

```python
def notify(context: ActionContext, state: dict, step: dict, at: float) -> None:
    """Tell the observer about a step that finished well. A crashing observer is logged once."""
    if context.observe is None:
        return
    try:
        context.observe(state, step, context, at)
    except Exception as error:
        log_once(logger, "observe", error)


def finish(state: dict, step: dict, context: ActionContext, at: float) -> bool:
    """Apply a step that ended at `at`. Returns True when it killed Mimo."""
    grid, events = context.grid, context.events
    if step["kind"] == "fall":
        record(state, step, at, "done")
        return finish_fall(state, step, grid, at, events)
    if step["kind"] == "swim":
        state["position"] = position_of(step["path"][-1])
        record(state, step, at, "done")
        notify(context, state, step, at)
        return False
    try:
        event = finish_step(step, state, grid, at)
    except (ValueError, KeyError) as error:
        fail(state, step, at, str(error))
        return False
    except Exception as error:
        log_once(logger, "finish_step", error)
        fail(state, step, at, "bad step")
        return False
```

At the end of the same function, replace:

```python
    if step["kind"] == "walk" and not step["reached"]:
        target = step["target"]
        state["queue"].insert(0, {"kind": "walk", "target": [target["x"], target["y"], target["z"]],
                                  "reach": step["reach"], "segments": step["segments"] + 1})
    return False
```

with:

```python
    if step["kind"] == "walk" and not step["reached"]:
        target = step["target"]
        state["queue"].insert(0, {"kind": "walk", "target": [target["x"], target["y"], target["z"]],
                                  "reach": step["reach"], "segments": step["segments"] + 1})
    notify(context, state, step, at)
    return False
```

Replace the whole `safe_plan` function with:

```python
def safe_plan(context: ActionContext, state: dict, at: float) -> list[dict]:
    """Ask the planner for the next steps. A crash, or a result that is not a list of dicts, is
    logged once per distinct error and replaced with rest_plan: minds plug their planners in
    here, so this must be airtight against whatever one of them does wrong."""
    try:
        plan = context.planner(state, context, at)
    except Exception as error:
        log_once(logger, "planner", error)
        plan = None
    else:
        if not (isinstance(plan, list) and all(isinstance(spec, dict) for spec in plan)):
            log_once(logger, "planner", TypeError(f"planner returned {type(plan).__name__}, not a list of steps"))
            plan = None
    if plan is None:
        from backend.survival.script import rest_plan  # imported here to sidestep an import cycle
        plan = rest_plan(state, context, at)
    return list(plan)
```

In `advance_actions`, replace:

```python
            if not state["queue"]:
                state["queue"] = safe_plan(context, state, grid, at)
                if not state["queue"]:
                    break
            spec = state["queue"][0]
            if spec.get("kind") == "walk" and context.searches_left <= 0:
                break  # search budget spent this tick; try this walk again next advance_actions
            state["queue"].pop(0)
            if spec.get("kind") == "walk":
                context.searches_left -= 1
            try:
                state["action"] = start_step(spec, state, grid, at)
            except (ValueError, KeyError) as error:
                fail(state, as_started(spec, at), at, str(error))
                break  # plan again at the next advance, not in a tight loop
            except Exception:
                logger.exception("start_step crashed on %r", spec)
                fail(state, as_started(spec, at), at, "bad step")
                break
```

with:

```python
            if not state["queue"]:
                state["queue"] = safe_plan(context, state, at)
                if not state["queue"]:
                    break
            spec = state["queue"][0]
            if spec.get("kind") == "walk" and not take_search(context):
                break  # search budget spent this tick; try this walk again next advance_actions
            state["queue"].pop(0)
            try:
                state["action"] = start_step(spec, state, grid, at)
            except (ValueError, KeyError) as error:
                fail(state, as_started(spec, at), at, str(error))
                break  # plan again at the next advance, not in a tight loop
            except Exception as error:
                log_once(logger, "start_step", error)
                fail(state, as_started(spec, at), at, "bad step")
                break
```

- [ ] **Step 5: Give the interim planners the context**

In `backend/survival/script.py`, replace:

```python
from __future__ import annotations

import math

from backend.services.worldgen import terrain_height, trees_in_chunk
from backend.survival.clock import is_night
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.steps import as_cell
from backend.survival.vitals import EXHAUSTED_BELOW
```

with:

```python
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.worldgen import terrain_height, trees_in_chunk
from backend.survival.clock import is_night
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.steps import as_cell
from backend.survival.vitals import EXHAUSTED_BELOW

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext
```

Replace:

```python
def rest_plan(state: dict, grid: Grid, at: float, clock: dict) -> list[dict]:
    """Sleep at night or when exhausted; otherwise wait (at most a minute) for nightfall."""
    night = is_night(clock["phase"])
```

with:

```python
def rest_plan(state: dict, context: ActionContext, at: float) -> list[dict]:
    """Sleep at night or when exhausted; otherwise wait (at most a minute) for nightfall."""
    clock = context.clock_at(at)
    night = is_night(clock["phase"])
```

Replace:

```python
def scripted_plan(state: dict, grid: Grid, at: float, clock: dict) -> list[dict]:
    """By day: planks from logs, else chop the nearest tree, else look further out. Rest as rest_plan."""
    rest = rest_plan(state, grid, at, clock)
```

with:

```python
def scripted_plan(state: dict, context: ActionContext, at: float) -> list[dict]:
    """By day: planks from logs, else chop the nearest tree, else look further out. Rest as rest_plan."""
    grid, clock = context.grid, context.clock_at(at)
    rest = rest_plan(state, context, at)
```

- [ ] **Step 6: Add the Mind to the tick**

Replace the whole of `backend/survival/tick.py` with:

```python
"""One survival tick: bring the active life's world up to now.

The worker calls `tick_life` about once a second. A longer gap (a laptop that slept) is
caught up in steps of at most 60 game seconds, so a pet can starve while nobody watches.
Each step first runs Mimo's timed actions up to the step's start (backend.survival.actions),
then advances vitals with the activity and surroundings at that moment. A `Mind` decides the
steps: its `plan` fills an empty queue (M1's `rest_plan` in the default `RESTING` mind), and its
optional hooks let a brain (backend.survival.brain) hear about finished steps (`observe`) and
notice each vitals step (`notice`). Minds never call a model here: the tick holds the world's
write transaction.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Callable

from backend.services.block_table import material_in
from backend.services.worldgen import biome_at
from backend.survival.actions import ActionContext, Observe, Planner, activity_of, advance_actions, ensure_actions
from backend.survival.clock import DAY_SECONDS, clock_at, is_night, time_scale
from backend.survival.grid import world_grid
from backend.survival.once import log_once
from backend.survival.registry import LifeRegistry
from backend.survival.script import rest_plan
from backend.survival.vitals import (
    FIRE_REACH, FREEZING_BELOW, WARM_BLOCKS, Surroundings, is_sheltered, near_warm_block, step_vitals,
)
from backend.survival.world import SurvivalWorld, log_event, placed_near, read_state, write_state

logger = logging.getLogger(__name__)

MAX_STEP_SECONDS = 60.0
HUNGRY_BELOW = 30.0
CAUSE_TEXT = {"starvation": "starvation", "cold": "the cold", "drowning": "drowning", "fall": "a fall"}

Event = tuple[float, str, str]
# After each vitals step: (state, context, vitals before the step, surroundings, step start, step end).
Notice = Callable[[dict, ActionContext, dict, Surroundings, float, float], None]


@dataclass(frozen=True)
class Mind:
    """What runs Mimo inside a tick. `plan` fills an empty queue; the hooks are optional."""

    plan: Planner = rest_plan
    observe: Observe | None = None
    notice: Notice | None = None


RESTING = Mind()


def surroundings_at(db: sqlite3.Connection, seed: str, position: dict) -> Surroundings:
    x, y, z = round(position["x"]), round(position["y"]), round(position["z"])

    def material_at(cx: int, cy: int, cz: int) -> str:
        return material_in(db, cx, cy, cz, seed)

    return Surroundings(
        biome=biome_at(x, z, seed),
        sheltered=is_sheltered(material_at, x, y, z),
        near_fire=near_warm_block(placed_near(db, position, FIRE_REACH, WARM_BLOCKS), x, y, z),
        head_in_water=material_at(x, y, z) == "water",
    )


def note_crossings(state: dict, before: dict, at: float, events: list[Event]) -> None:
    after, name = state["vitals"], state["name"]
    if before["hunger"] >= HUNGRY_BELOW > after["hunger"]:
        state["last_thought"] = "My tummy is rumbling. I need food."
        events.append((at, "hungry", f"{name} is getting hungry."))
    if before["hunger"] > 0 >= after["hunger"]:
        state["last_thought"] = "I'm starving..."
        events.append((at, "starving", f"{name} is starving."))
    if before["warmth"] >= FREEZING_BELOW > after["warmth"]:
        state["last_thought"] = "I'm so cold."
        events.append((at, "freezing", f"{name} is freezing."))


def record_death(state: dict, cause: str, at: float, scale: float, events: list[Event]) -> None:
    """Mark Mimo dead at `at` and log it. The current step and the plan end with the life.

    A fatal fall can be discovered a catch-up step after the vitals (and any crossing, like
    "hungry") that already ran up to that step's cursor, so `at` can land before events already
    queued for it. Drop those: nothing should read as happening after Mimo died. Health already
    reads 0 by the time any cause is known (step_vitals or finish_fall got it there), so it is
    left alone.
    """
    events[:] = [event for event in events if event[0] <= at]
    day = clock_at(state["born_at"], at, scale)["day_number"]
    state.update(status="dead", died_at=at, cause=cause, action=None, queue=[])
    events.append((at, "death", f"{state['name']} died of {CAUSE_TEXT[cause]} on day {day}."))


def run_notice(mind: Mind, state: dict, context: ActionContext, before: dict, surroundings: Surroundings,
               since: float, at: float) -> None:
    """Call the mind's notice hook. A crashing hook is logged once and the tick goes on."""
    if mind.notice is None:
        return
    try:
        mind.notice(state, context, before, surroundings, since, at)
    except Exception as error:
        log_once(logger, "notice", error)


def advance_world(world: SurvivalWorld, timestamp: float, scale: float, mind: Mind = RESTING) -> dict:
    """Catch the world up to `timestamp` in one transaction and return the saved state."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None or timestamp <= state["last_tick_at"]:
            return state
        ensure_actions(state)
        events: list[Event] = []
        context = ActionContext(grid=world_grid(db, world.seed), planner=mind.plan, events=events,
                                clock_at=lambda at: clock_at(state["born_at"], at, scale),
                                observe=mind.observe, db=db)
        cursor = state["last_tick_at"]
        remaining = (timestamp - cursor) * scale
        while remaining > 1e-9:
            fell_at = advance_actions(state, context, cursor)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
                break
            step = min(MAX_STEP_SECONDS, remaining)
            night = is_night(clock_at(state["born_at"], cursor, scale)["phase"])
            last_hello = state["last_hello_at"] or state["born_at"]
            before = state["vitals"]
            surroundings = surroundings_at(db, world.seed, state["position"])
            state["vitals"], cause = step_vitals(
                before, step, night=night, activity=activity_of(state), surroundings=surroundings,
                lonely=(cursor - last_hello) * scale > DAY_SECONDS)
            since = cursor
            cursor += step / scale
            remaining -= step
            note_crossings(state, before, cursor, events)
            if cause:
                record_death(state, cause, cursor, scale, events)
                break
            run_notice(mind, state, context, before, surroundings, since, cursor)
        if state["died_at"] is None:
            fell_at = advance_actions(state, context, timestamp)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
        state["last_tick_at"] = state["died_at"] if state["died_at"] is not None else timestamp
        write_state(db, state)
        for at, kind, text in sorted(events, key=lambda event: event[0]):
            log_event(db, at, kind, text)
        return state


def tick_life(registry: LifeRegistry, timestamp: float | None = None, scale: float | None = None,
              mind: Mind = RESTING) -> dict | None:
    """Advance the active life and archive it if it died. Returns its state, or None if no pet is alive."""
    life = registry.active_life()
    if life is None:
        return None
    timestamp = time.time() if timestamp is None else timestamp
    scale = time_scale() if scale is None else scale
    state = advance_world(SurvivalWorld(registry.world_path(life)), timestamp, scale, mind)
    if state["died_at"] is not None:
        registry.mark_dead(life["id"], state["died_at"], state["cause"])
    return state
```

- [ ] **Step 7: Run the worker with a Mind**

In `backend/workers/mimo_worker.py`, replace:

```python
from backend.survival.actions import Planner
from backend.survival.registry import LifeRegistry, data_dir
from backend.survival.script import rest_plan, scripted_plan
from backend.survival.tick import tick_life
from backend.survival.world import WorldMissing

logger = logging.getLogger("mimo_worker")
stopping = False

# What the pet does between vitals. The brain milestone (M3) replaces this interim script.
WORKER_PLANNER: Planner = scripted_plan
```

with:

```python
from backend.survival.registry import LifeRegistry, data_dir
from backend.survival.script import scripted_plan
from backend.survival.tick import RESTING, Mind, tick_life
from backend.survival.world import WorldMissing

logger = logging.getLogger("mimo_worker")
stopping = False

# What runs the pet. The brain (M3 Task 13) replaces this interim script.
WORKER_MIND = Mind(plan=scripted_plan)
```

Replace:

```python
def run_once(registry: LifeRegistry, previous: str | None, timestamp: float | None = None,
             planner: Planner = rest_plan) -> str:
    """Tick the active life once. Logs a line when the pet's status changes and returns it.

    `planner` defaults to the plain sleep rule; `main` passes WORKER_PLANNER.
    """
    state = tick_life(registry, timestamp, planner=planner)
```

with:

```python
def run_once(registry: LifeRegistry, previous: str | None, timestamp: float | None = None,
             mind: Mind = RESTING) -> str:
    """Tick the active life once. Logs a line when the pet's status changes and returns it.

    `mind` defaults to the plain sleep rule; `main` passes WORKER_MIND.
    """
    state = tick_life(registry, timestamp, mind=mind)
```

Replace:

```python
            previous = run_once(registry, previous, planner=WORKER_PLANNER)
```

with:

```python
            previous = run_once(registry, previous, mind=WORKER_MIND)
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_*.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 234 tests` … `OK` (7 new).

- [ ] **Step 9: Commit**

```bash
git add backend/survival/once.py backend/survival/actions.py backend/survival/tick.py backend/survival/script.py backend/workers/mimo_worker.py backend/tests/test_survival_actions.py backend/tests/test_survival_script.py backend/tests/test_survival_tick_actions.py
git commit -m "feat: run the pet through a Mind with observe and notice hooks, and log crashes once" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Failure codes, interrupted results and purpose tags

**Files:**
- Modify: `backend/survival/steps.py`, `backend/survival/actions.py`
- Test: `backend/tests/test_survival_steps.py`, `backend/tests/test_survival_actions.py`

**Interfaces:**
- Consumes: Task 1's `actions.py`.
- Produces:
  - `backend.survival.steps`: `FAILURE_CODES = ("no_path", "out_of_reach", "gone", "missing_item", "blocked", "bad_step")`; `StepFailed(message: str, code: str = "bad_step")` with `.code`; `failure_code(error: Exception) -> str`.
  - `backend.survival.actions`: `record(state, step, ended_at, result, reason=None, code=None)`; `fail(state, step, at, reason, code="bad_step")` also sets `state["last_failure"] = {"code", "reason", "kind", "cell", "purpose", "at", "seq"}` (`cell` is the step's `target` point dict or None; `seq` counts failures so two alike failures at the same moment still differ); `ensure_actions` adds `last_failure: None`; recorded entries carry `code` (failures) and `purpose` (when the spec had one); the running step keeps its spec's `purpose`; hazards record the dropped step as `result: "interrupted"`, `reason: "fall"` or `"swim"`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_steps.py`, replace:

```python
from backend.survival.steps import FOOD, StepFailed, as_cell, finish_step, mine_seconds, start_step
```

with:

```python
from backend.survival.steps import FOOD, StepFailed, as_cell, failure_code, finish_step, mine_seconds, start_step
```

Add at the end of `StepTests`:

```python
    def test_failures_carry_a_code(self):
        grid = small_world({(1, 1, 0): "bedrock", (2, 1, 0): "stone"})
        cases = [({"kind": "mine", "target": [9, 1, 0]}, pet(), "out_of_reach"),
                 ({"kind": "mine", "target": [1, 1, 0]}, pet(), "blocked"),
                 ({"kind": "mine", "target": [2, 1, 0]}, pet(), "missing_item"),
                 ({"kind": "place", "target": [0, 2, 0], "block": "dirt"}, pet(), "missing_item"),
                 ({"kind": "place", "target": [1, 1, 0], "block": "dirt"}, pet(inventory={"dirt": 1}), "blocked"),
                 ({"kind": "place", "target": [0, 1, 0], "block": "dirt"}, pet(inventory={"dirt": 1}), "blocked"),
                 ({"kind": "eat", "item": "berries"}, pet(), "missing_item"),
                 ({"kind": "dance"}, pet(), "bad_step"),
                 ({"kind": "mine", "target": None}, pet(), "bad_step")]
        for spec, state, code in cases:
            with self.assertRaises(StepFailed, msg=spec) as caught:
                start_step(spec, state, grid, 0.0)
            self.assertEqual(caught.exception.code, code, msg=spec)
        walls = {(dx, dy, dz): "stone" for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)) for dy in (1, 2)}
        with self.assertRaises(StepFailed) as caught:
            start_step({"kind": "walk", "target": [3, 1, 0]}, pet(), small_world(walls), 0.0)
        self.assertEqual(caught.exception.code, "no_path")

    def test_a_block_that_changed_before_the_mine_ended_is_gone(self):
        grid, state = small_world({(1, 1, 0): "dirt"}), pet()
        step = start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 0.0)
        grid.put(1, 1, 0, "air")
        with self.assertRaises(StepFailed) as caught:
            finish_step(step, state, grid, 1.0)
        self.assertEqual(caught.exception.code, "gone")

    def test_crafting_errors_map_to_missing_item_or_bad_step(self):
        self.assertEqual(failure_code(ValueError("Missing materials: planks")), "missing_item")
        self.assertEqual(failure_code(ValueError("A placed crafting_table is required")), "missing_item")
        self.assertEqual(failure_code(ValueError("Unknown recipe")), "bad_step")
        self.assertEqual(failure_code(KeyError("recipe")), "bad_step")
        self.assertEqual(failure_code(StepFailed("the dirt is gone", "gone")), "gone")
```

In `backend/tests/test_survival_actions.py`, replace in `test_a_hazard_records_the_interrupted_plan_once`:

```python
        self.assertEqual(kinds, [("mine", "failed", "interrupted: fall"), ("fall", "done", None)])
        self.assertEqual(state["recent_actions"][0]["target"], {"x": 5, "y": 1, "z": 0})
        self.assertEqual(state["queue"], [])
```

with:

```python
        self.assertEqual(kinds, [("mine", "interrupted", "fall"), ("fall", "done", None)])
        self.assertEqual(state["recent_actions"][0]["target"], {"x": 5, "y": 1, "z": 0})
        self.assertEqual(state["queue"], [])
        self.assertIsNone(state["last_failure"])
```

In `test_a_walk_stops_where_its_path_became_blocked`, replace:

```python
        self.assertEqual(state["recent_actions"][-1]["reason"], "path blocked")
```

with:

```python
        self.assertEqual(state["recent_actions"][-1]["reason"], "path blocked")
        self.assertEqual(state["last_failure"]["code"], "blocked")
```

In `test_states_saved_before_actions_get_the_new_fields`, replace:

```python
        self.assertEqual(state, {"last_tick_at": 42.0, "action": None, "queue": [], "recent_actions": [],
                                 "actions_at": 42.0})
```

with:

```python
        self.assertEqual(state, {"last_tick_at": 42.0, "action": None, "queue": [], "recent_actions": [],
                                 "actions_at": 42.0, "last_failure": None})
```

In `test_a_malformed_queued_step_fails_clean_and_the_tick_keeps_going`, replace:

```python
            self.assertIn("bad step", failed["reason"], msg=spec)
```

with:

```python
            self.assertIn("bad step", failed["reason"], msg=spec)
            self.assertEqual(failed["code"], "bad_step", msg=spec)
```

Add at the end of `ActionEngineTests`:

```python
    def test_a_failure_is_kept_with_its_code_cell_and_purpose(self):
        state = pet()
        state["queue"] = [{"kind": "mine", "target": [9, 1, 0], "purpose": "gather_stone"}]
        advance_actions(state, context(small_world({(9, 1, 0): "dirt"})), 1.0)
        entry = state["recent_actions"][-1]
        self.assertEqual((entry["code"], entry["purpose"]), ("out_of_reach", "gather_stone"))
        self.assertEqual(state["last_failure"], {"code": "out_of_reach", "reason": "out of reach", "kind": "mine",
                                                 "cell": {"x": 9, "y": 1, "z": 0}, "purpose": "gather_stone",
                                                 "at": 0.0, "seq": 1})

    def test_a_running_step_keeps_the_purpose_that_planned_it(self):
        grid, state = small_world({(1, 1, 0): "dirt"}), pet()
        state["queue"] = [{"kind": "mine", "target": [1, 1, 0], "purpose": "gather_stone"}]
        ctx = context(grid)
        advance_actions(state, ctx, 0.1)
        self.assertEqual(state["action"]["purpose"], "gather_stone")
        advance_actions(state, ctx, 1.0)
        self.assertEqual((state["recent_actions"][-1]["result"], state["recent_actions"][-1]["purpose"]),
                         ("done", "gather_stone"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_steps.py"`
Expected: `ImportError: cannot import name 'failure_code'`.

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_actions.py"`
Expected: failures in the hazard, blocked-walk, new-fields, malformed-step and the two new tests (`KeyError: 'last_failure'`, `KeyError: 'code'`).

- [ ] **Step 3: Give every step failure a code**

In `backend/survival/steps.py`, replace:

```python
class StepFailed(ValueError):
    """A step cannot start or finish. The message says why."""
```

with:

```python
FAILURE_CODES = ("no_path", "out_of_reach", "gone", "missing_item", "blocked", "bad_step")


class StepFailed(ValueError):
    """A step cannot start or finish. The message says why; `code` (one of FAILURE_CODES) sorts
    it for the brain: no way there, out of reach, the block is gone, something is missing, the
    cell is blocked, or the step itself is malformed."""

    def __init__(self, message: str, code: str = "bad_step"):
        super().__init__(message)
        self.code = code


def failure_code(error: Exception) -> str:
    """The failure code of anything start_step or finish_step raised. Crafting and smelting raise
    plain ValueErrors: missing materials or a missing station mean something is missing."""
    if isinstance(error, StepFailed):
        return error.code
    if str(error).startswith(("Missing materials", "A placed")):
        return "missing_item"
    return "bad_step"
```

In `start_step`, replace:

```python
        if segments > MAX_SEGMENTS:
            raise StepFailed("no way there")
        cells, reached = route(grid, here, target, reach)
        if not cells and not reached:
            raise StepFailed("no way there")
```

with:

```python
        if segments > MAX_SEGMENTS:
            raise StepFailed("no way there", "no_path")
        cells, reached = route(grid, here, target, reach)
        if not cells and not reached:
            raise StepFailed("no way there", "no_path")
```

Replace:

```python
        if not in_reach(here, target):
            raise StepFailed("out of reach")
        material = grid.material(*target)
        seconds = mine_seconds(material, inventory)
        if seconds is None:
            raise StepFailed(f"{label(material)} cannot be mined")
        if not can_harvest(material, inventory):
            raise StepFailed(f"a stronger pickaxe is needed for {label(material)}")
```

with:

```python
        if not in_reach(here, target):
            raise StepFailed("out of reach", "out_of_reach")
        material = grid.material(*target)
        seconds = mine_seconds(material, inventory)
        if seconds is None:
            raise StepFailed(f"{label(material)} cannot be mined", "blocked")
        if not can_harvest(material, inventory):
            raise StepFailed(f"a stronger pickaxe is needed for {label(material)}", "missing_item")
```

Replace:

```python
        if inventory.get(block, 0) < 1:
            raise StepFailed(f"no {label(block)} to place")
        if block not in BLOCKS:
            raise StepFailed(f"{label(block)} is not a block")
        if not in_reach(here, target):
            raise StepFailed("out of reach")
        if target == here:
            raise StepFailed("that is where it stands")
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken")
```

with:

```python
        if inventory.get(block, 0) < 1:
            raise StepFailed(f"no {label(block)} to place", "missing_item")
        if block not in BLOCKS:
            raise StepFailed(f"{label(block)} is not a block")
        if not in_reach(here, target):
            raise StepFailed("out of reach", "out_of_reach")
        if target == here:
            raise StepFailed("that is where it stands", "blocked")
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken", "blocked")
```

Replace:

```python
        if inventory.get(item, 0) < 1:
            raise StepFailed(f"no {label(item)} to eat")
```

with:

```python
        if inventory.get(item, 0) < 1:
            raise StepFailed(f"no {label(item)} to eat", "missing_item")
```

In `finish_step`, replace:

```python
        if grid.material(*target) != step["block"]:
            raise StepFailed(f"the {label(step['block'])} is gone")
```

with:

```python
        if grid.material(*target) != step["block"]:
            raise StepFailed(f"the {label(step['block'])} is gone", "gone")
```

and replace:

```python
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken")
        state["inventory"] = take_items(state["inventory"], {step["block"]: 1})
```

with:

```python
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken", "blocked")
        state["inventory"] = take_items(state["inventory"], {step["block"]: 1})
```

- [ ] **Step 4: Keep the last failure, tag steps with their purpose, record interruptions**

In `backend/survival/actions.py`, replace the docstring sentences:

```python
is water (a fallback until the brain's surface reflex in M3). Either hazard drops the running
step or the queue it interrupts (recorded once, "interrupted: fall" or "interrupted: swim") so a
purpose layer can later tell its plan was abandoned.
```

with:

```python
is water (the physical half of the brain's surface reflex). Either hazard drops the running
step or the queue it interrupts (recorded once with result "interrupted" and reason "fall" or
"swim") so the brain can tell its plan was abandoned, not failed. A step that fails is recorded
with a failure code (steps.FAILURE_CODES) and kept as `state["last_failure"]` with its cell and
the purpose that planned it; queued steps carry that purpose as `purpose`.
```

Replace:

```python
from backend.survival.steps import as_cell, as_point, finish_step, position_of, start_step
```

with:

```python
from backend.survival.steps import as_cell, as_point, failure_code, finish_step, position_of, start_step
```

Replace:

```python
RECORDED_FIELDS = ("kind", "started_at", "target", "block", "item", "recipe")
```

with:

```python
RECORDED_FIELDS = ("kind", "started_at", "target", "block", "item", "recipe", "purpose")
```

Replace:

```python
    state.setdefault("actions_at", state["last_tick_at"])
```

with:

```python
    state.setdefault("actions_at", state["last_tick_at"])
    state.setdefault("last_failure", None)
```

Replace the `record` and `fail` functions with:

```python
def record(state: dict, step: dict, ended_at: float, result: str, reason: str | None = None,
           code: str | None = None) -> None:
    if step["kind"] in UNRECORDED:
        return
    entry = {key: step[key] for key in RECORDED_FIELDS if key in step}
    entry.update(ended_at=ended_at, result=result)
    if reason:
        entry["reason"] = reason
    if code:
        entry["code"] = code
    state["recent_actions"] = [*state["recent_actions"], entry][-RECENT_LIMIT:]


def fail(state: dict, step: dict, at: float, reason: str, code: str = "bad_step") -> None:
    """Record a failed step, keep it as the last failure and drop the rest of the plan, so the
    planner plans again. `seq` counts failures, so two alike failures at the same moment differ."""
    record(state, step, at, "failed", reason, code)
    seq = (state.get("last_failure") or {}).get("seq", 0) + 1
    state["last_failure"] = {"code": code, "reason": reason, "kind": step["kind"], "cell": step.get("target"),
                             "purpose": step.get("purpose"), "at": at, "seq": seq}
    state["action"] = None
    state["queue"] = []
```

In `as_started`, replace:

```python
    step = {key: spec[key] for key in ("block", "item", "recipe") if key in spec}
```

with:

```python
    step = {key: spec[key] for key in ("block", "item", "recipe", "purpose") if key in spec}
```

In `interrupt_plan`, replace:

```python
def interrupt_plan(state: dict, at: float, hazard: str) -> None:
    """Record the plan a fall or swim hazard is about to drop, once per hazard: the running step
    if there is one, else the first queued one. A wait, like any UNRECORDED kind, stays silent."""
    dropped = state["action"] or (state["queue"][0] if state["queue"] else None)
    if dropped is None:
        return
    step = dropped if dropped is state["action"] else as_started(dropped, at)
    record(state, step, at, "failed", f"interrupted: {hazard}")
```

with:

```python
def interrupt_plan(state: dict, at: float, hazard: str) -> None:
    """Record the plan a fall or swim hazard is about to drop, once per hazard: the running step
    if there is one, else the first queued one. A wait, like any UNRECORDED kind, stays silent."""
    dropped = state["action"] or (state["queue"][0] if state["queue"] else None)
    if dropped is None:
        return
    step = dropped if dropped is state["action"] else as_started(dropped, at)
    record(state, step, at, "interrupted", hazard)
```

In `finish`, replace:

```python
    except (ValueError, KeyError) as error:
        fail(state, step, at, str(error))
        return False
    except Exception as error:
        log_once(logger, "finish_step", error)
        fail(state, step, at, "bad step")
        return False
```

with:

```python
    except (ValueError, KeyError) as error:
        fail(state, step, at, str(error), failure_code(error))
        return False
    except Exception as error:
        log_once(logger, "finish_step", error)
        fail(state, step, at, "bad step", "bad_step")
        return False
```

In `advance_actions`, replace:

```python
            try:
                state["action"] = start_step(spec, state, grid, at)
            except (ValueError, KeyError) as error:
                fail(state, as_started(spec, at), at, str(error))
                break  # plan again at the next advance, not in a tight loop
            except Exception as error:
                log_once(logger, "start_step", error)
                fail(state, as_started(spec, at), at, "bad step")
                break
            begin(state, spec, at, context.events)
```

with:

```python
            try:
                state["action"] = start_step(spec, state, grid, at)
            except (ValueError, KeyError) as error:
                fail(state, as_started(spec, at), at, str(error), failure_code(error))
                break  # plan again at the next advance, not in a tight loop
            except Exception as error:
                log_once(logger, "start_step", error)
                fail(state, as_started(spec, at), at, "bad step", "bad_step")
                break
            if "purpose" in spec:
                state["action"]["purpose"] = spec["purpose"]
            begin(state, spec, at, context.events)
```

and replace:

```python
        if step["kind"] in ("walk", "swim") and not follow_path(state, step, grid, until):
            fail(state, step, until, "path blocked")
```

with:

```python
        if step["kind"] in ("walk", "swim") and not follow_path(state, step, grid, until):
            fail(state, step, until, "path blocked", "blocked")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_*.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 239 tests` … `OK` (5 new).

- [ ] **Step 6: Commit**

```bash
git add backend/survival/steps.py backend/survival/actions.py backend/tests/test_survival_steps.py backend/tests/test_survival_actions.py
git commit -m "feat: give step failures codes, keep the last failure and record interruptions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Action speed scale and finished paths for replay

**Files:**
- Modify: `backend/survival/clock.py`, `backend/survival/pathing.py`, `backend/survival/steps.py`, `backend/survival/actions.py`, `backend/survival/tick.py`
- Test: `backend/tests/test_survival_clock.py`, `backend/tests/test_survival_steps.py`, `backend/tests/test_survival_actions.py`, `backend/tests/test_survival_tick_actions.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces:
  - `backend.survival.clock.action_scale() -> float` (from `MIMO_ACTION_SCALE`; missing, invalid, non-finite or ≤ 0 means 1).
  - `backend.survival.pathing.timed_path(grid, start, cells, started_at, scale: float = 1.0)`.
  - `backend.survival.steps.start_step(spec, state, grid, at, scale: float = 1.0)`: walk, mine, place, eat, craft and smelt durations are divided by `scale`; wait and sleep are not.
  - `ActionContext.action_scale: float = 1.0`, passed to `start_step`.
  - `advance_world(world, timestamp, scale, mind=RESTING, action_scale: float = 1.0)`; `tick_life(..., mind=RESTING, action_scale: float | None = None)` (None reads `action_scale()`).
  - `actions.PATH_KEEP = 4`; recorded walk, swim and fall entries carry `path`; only the newest 4 recent entries keep it.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_clock.py`, replace:

```python
from backend.survival.clock import DAY_SECONDS, clock_at, is_night, phase_at, time_scale
```

with:

```python
from backend.survival.clock import DAY_SECONDS, action_scale, clock_at, is_night, phase_at, time_scale
```

and add this class before `if __name__ == "__main__":`:

```python
class ActionScaleTests(unittest.TestCase):
    def test_reads_mimo_action_scale_and_defaults_to_one(self):
        with patch.dict(os.environ, {"MIMO_ACTION_SCALE": "60"}):
            self.assertEqual(action_scale(), 60.0)
        for bad in ("0", "-2", "fast", "inf", "nan"):
            with patch.dict(os.environ, {"MIMO_ACTION_SCALE": bad}):
                self.assertEqual(action_scale(), 1.0, bad)
        with patch.dict(os.environ, {}):
            os.environ.pop("MIMO_ACTION_SCALE", None)
            self.assertEqual(action_scale(), 1.0)
```

In `backend/tests/test_survival_steps.py`, add at the end of `StepTests`:

```python
    def test_the_action_scale_divides_step_times_but_not_waits(self):
        grid, state = small_world({(1, 1, 0): "oak_log"}), pet()
        self.assertEqual(start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 100.0, scale=4.0)["ends_at"],
                         100.5)
        walk = start_step({"kind": "walk", "target": [3, 1, 0]}, state, small_world(), 10.0, scale=3.0)
        self.assertEqual([entry["at"] for entry in walk["path"]], [10.0, 10.1, 10.2, 10.3])
        self.assertEqual(start_step({"kind": "wait", "seconds": 5}, state, grid, 1.0, scale=4.0)["ends_at"], 6.0)
```

In `backend/tests/test_survival_actions.py`, add at the end of `ActionEngineTests`:

```python
    def test_the_newest_finished_paths_are_kept_for_replay(self):
        grid, state = small_world(), pet()
        state["queue"] = [{"kind": "walk", "target": [x, 1, 0]} for x in range(1, 7)]
        for until in range(1, 5):
            advance_actions(state, context(grid), float(until))  # a fresh budget each call, like a tick
        walks = state["recent_actions"]
        self.assertEqual(len(walks), 6)
        self.assertEqual(["path" in entry for entry in walks], [False, False, True, True, True, True])
        self.assertEqual(walks[-1]["path"][-1], {"x": 6, "y": 1, "z": 0, "at": walks[-1]["ended_at"]})

    def test_the_context_action_scale_speeds_up_steps(self):
        grid, state = small_world({(1, 1, 0): "oak_log"}), pet()
        state["queue"] = [{"kind": "mine", "target": [1, 1, 0]}]
        ctx = context(grid)
        ctx.action_scale = 60.0
        advance_actions(state, ctx, 0.1)
        self.assertEqual(state["recent_actions"][-1]["ended_at"], 0.033)
```

In `backend/tests/test_survival_tick_actions.py`, add at the end of `TickActionTests`:

```python
    def test_tick_life_passes_the_action_scale_to_the_steps(self):
        x, z = self.spawn_column()
        y = terrain_height(x, z, self.world.seed) + 1
        self.world.put_block(x + 1, y, z, "oak_log")
        self.edit(position={"x": float(x), "y": float(y), "z": float(z)}, action=None, recent_actions=[],
                  actions_at=BORN, queue=[{"kind": "mine", "target": [x + 1, y, z]}])
        state = tick_life(self.registry, BORN + 0.1, scale=1, action_scale=60)
        self.assertEqual(state["recent_actions"][-1]["ended_at"], round(BORN + 2.0 / 60, 3))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_*.py"`
Expected: `ImportError: cannot import name 'action_scale'` and `TypeError: ... unexpected keyword argument 'scale'`.

- [ ] **Step 3: Read MIMO_ACTION_SCALE**

In `backend/survival/clock.py`, replace:

```python
MIMO_TIME_SCALE (default 1) sets how many game seconds pass per real second. It exists for
manual testing; automated tests pass the scale in directly.
"""
```

with:

```python
MIMO_TIME_SCALE (default 1) sets how many game seconds pass per real second. MIMO_ACTION_SCALE
(default 1) makes Mimo's steps that many times shorter. Both exist for manual testing (at 60x the
clock runs fast, so without the action scale a fast run cannot show a whole day of purposes);
automated tests pass the scales in directly.
"""
```

and replace the whole `time_scale` function with:

```python
def _positive_setting(name: str) -> float:
    """A positive finite number from the environment. Missing or invalid values mean 1."""
    try:
        value = float(os.environ.get(name, "1"))
    except ValueError:
        return 1.0
    return value if math.isfinite(value) and value > 0 else 1.0


def time_scale() -> float:
    """Game seconds per real second from MIMO_TIME_SCALE. Missing or invalid values mean 1."""
    return _positive_setting("MIMO_TIME_SCALE")


def action_scale() -> float:
    """How many times shorter Mimo's steps are, from MIMO_ACTION_SCALE. Missing or invalid values mean 1."""
    return _positive_setting("MIMO_ACTION_SCALE")
```

- [ ] **Step 4: Divide step durations by the scale**

In `backend/survival/pathing.py`, replace the whole `timed_path` function with:

```python
def timed_path(grid: Grid, start: Cell, cells: list[Cell], started_at: float, scale: float = 1.0) -> list[dict]:
    """The start and each cell after it with the time Mimo gets there. Water-surface cells say so.
    `scale` (MIMO_ACTION_SCALE) makes every move that many times shorter."""
    at = started_at
    path = [{"x": start[0], "y": start[1], "z": start[2], "at": started_at}]
    for cell in cells:
        swim = grid.swimming(cell)
        at = round(at + (SWIM_SECONDS if swim else WALK_SECONDS) / scale, 3)
        entry = {"x": cell[0], "y": cell[1], "z": cell[2], "at": at}
        if swim:
            entry["swim"] = True
        path.append(entry)
    return path
```

In `backend/survival/steps.py`, replace:

```python
def start_step(spec: dict, state: dict, grid: Grid, at: float) -> dict:
    """Check a queued step against the world and return it running, from `at` to its end time."""
```

with:

```python
def start_step(spec: dict, state: dict, grid: Grid, at: float, scale: float = 1.0) -> dict:
    """Check a queued step against the world and return it running, from `at` to its end time.

    `scale` (MIMO_ACTION_SCALE, 1 outside manual tests) divides the duration of walks, mining,
    placing, eating, crafting and smelting. Waits time things against the clock and sleep has no
    fixed end, so neither is scaled.
    """
```

Replace:

```python
        path = timed_path(grid, here, cells, at)
```

with:

```python
        path = timed_path(grid, here, cells, at, scale)
```

Replace:

```python
        return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds, 3),
                "target": as_point(target), "block": material}
```

with:

```python
        return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds / scale, 3),
                "target": as_point(target), "block": material}
```

Replace:

```python
        return {"kind": "place", "started_at": at, "ends_at": round(at + PLACE_SECONDS, 3),
                "target": as_point(target), "block": block}
```

with:

```python
        return {"kind": "place", "started_at": at, "ends_at": round(at + PLACE_SECONDS / scale, 3),
                "target": as_point(target), "block": block}
```

Replace:

```python
        return {"kind": "eat", "started_at": at, "ends_at": round(at + EAT_SECONDS, 3), "item": item}
    if kind == "craft":
        craft(inventory, spec["recipe"], stations_near(grid, here))
        return {"kind": "craft", "started_at": at, "ends_at": round(at + CRAFT_SECONDS, 3), "recipe": spec["recipe"]}
    if kind == "smelt":
        smelt(inventory, spec["item"], stations_near(grid, here))
        return {"kind": "smelt", "started_at": at, "ends_at": round(at + SMELT_SECONDS, 3), "item": spec["item"]}
```

with:

```python
        return {"kind": "eat", "started_at": at, "ends_at": round(at + EAT_SECONDS / scale, 3), "item": item}
    if kind == "craft":
        craft(inventory, spec["recipe"], stations_near(grid, here))
        return {"kind": "craft", "started_at": at, "ends_at": round(at + CRAFT_SECONDS / scale, 3),
                "recipe": spec["recipe"]}
    if kind == "smelt":
        smelt(inventory, spec["item"], stations_near(grid, here))
        return {"kind": "smelt", "started_at": at, "ends_at": round(at + SMELT_SECONDS / scale, 3),
                "item": spec["item"]}
```

- [ ] **Step 5: Pass the scale through the engine and keep the newest paths**

In `backend/survival/actions.py`, replace:

```python
RECENT_LIMIT = 20
```

with:

```python
RECENT_LIMIT = 20
# Finished walks, swims and falls keep their timed path so the viewer can replay a short step it
# never saw running. Only the newest few entries keep it, so the saved state stays small.
PATH_KEEP = 4
```

Replace:

```python
RECORDED_FIELDS = ("kind", "started_at", "target", "block", "item", "recipe", "purpose")
```

with:

```python
RECORDED_FIELDS = ("kind", "started_at", "target", "block", "item", "recipe", "purpose", "path")
```

In `record`, replace:

```python
    state["recent_actions"] = [*state["recent_actions"], entry][-RECENT_LIMIT:]
```

with:

```python
    recent = [*state["recent_actions"], entry][-RECENT_LIMIT:]
    for older in recent[:-PATH_KEEP]:
        older.pop("path", None)
    state["recent_actions"] = recent
```

In `ActionContext`, replace:

```python
    observe: Observe | None = None
    db: sqlite3.Connection | None = None
```

with:

```python
    observe: Observe | None = None
    db: sqlite3.Connection | None = None
    action_scale: float = 1.0
```

In `advance_actions`, replace:

```python
                state["action"] = start_step(spec, state, grid, at)
```

with:

```python
                state["action"] = start_step(spec, state, grid, at, context.action_scale)
```

In `backend/survival/tick.py`, replace:

```python
from backend.survival.clock import DAY_SECONDS, clock_at, is_night, time_scale
```

with:

```python
from backend.survival.clock import DAY_SECONDS, action_scale as action_scale_setting, clock_at, is_night, time_scale
```

Replace:

```python
def advance_world(world: SurvivalWorld, timestamp: float, scale: float, mind: Mind = RESTING) -> dict:
    """Catch the world up to `timestamp` in one transaction and return the saved state."""
```

with:

```python
def advance_world(world: SurvivalWorld, timestamp: float, scale: float, mind: Mind = RESTING,
                  action_scale: float = 1.0) -> dict:
    """Catch the world up to `timestamp` in one transaction and return the saved state."""
```

Replace:

```python
                                observe=mind.observe, db=db)
```

with:

```python
                                observe=mind.observe, db=db, action_scale=action_scale)
```

Replace the whole `tick_life` function with:

```python
def tick_life(registry: LifeRegistry, timestamp: float | None = None, scale: float | None = None,
              mind: Mind = RESTING, action_scale: float | None = None) -> dict | None:
    """Advance the active life and archive it if it died. Returns its state, or None if no pet is alive."""
    life = registry.active_life()
    if life is None:
        return None
    timestamp = time.time() if timestamp is None else timestamp
    scale = time_scale() if scale is None else scale
    action_scale = action_scale_setting() if action_scale is None else action_scale
    state = advance_world(SurvivalWorld(registry.world_path(life)), timestamp, scale, mind, action_scale)
    if state["died_at"] is not None:
        registry.mark_dead(life["id"], state["died_at"], state["cause"])
    return state
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_*.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 244 tests` … `OK` (5 new).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/clock.py backend/survival/pathing.py backend/survival/steps.py backend/survival/actions.py backend/survival/tick.py backend/tests/test_survival_clock.py backend/tests/test_survival_steps.py backend/tests/test_survival_actions.py backend/tests/test_survival_tick_actions.py
git commit -m "feat: speed steps up with MIMO_ACTION_SCALE and keep the newest paths for replay" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The interrupt hook

**Files:**
- Modify: `backend/survival/actions.py`, `backend/survival/tick.py`
- Test: `backend/tests/test_survival_actions.py`, `backend/tests/test_survival_tick_actions.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `backend.survival.actions`: `Interrupt = Callable[[dict, ActionContext, float], str | None]`; `INTERRUPTIBLE = frozenset({"walk", "sleep", "wait"})`; `MAX_TAKEOVERS = 4` (per `advance_actions` call); `ActionContext.interrupt: Interrupt | None = None`; `interrupted(state, context, at) -> bool`.
  - The hook contract (Task 11's `reflex_hook` follows it): the hook sees the state with the running step still in `state["action"]` (a walk already moved to the last cell it reached by `at`). To take over, it puts its own steps in `state["queue"]` and returns a reason (the reflex name). The engine then records the running step as `interrupted` with that reason and clears it. Returning None (or crashing, logged once) means no takeover.
  - The hook is asked before every step start (after the fall/swim hazards) and at every advance while a walk, sleep or wait is still running.
  - `tick.Mind` gains `interrupt: Interrupt | None = None`, passed to the context.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_survival_actions.py`, add after the `context` helper:

```python
class Takeover:
    """An interrupt hook that takes over once, when `when(state, at)` holds, with `plan`."""

    def __init__(self, when, plan, reason="reflex"):
        self.when, self.plan, self.reason = when, plan, reason
        self.fired = False

    def __call__(self, state, context, at):
        if self.fired or not self.when(state, at):
            return None
        self.fired = True
        state["queue"] = [dict(spec) for spec in self.plan]
        return self.reason


def hooked(grid, hook, clock=None):
    ctx = context(grid, clock=clock)
    ctx.interrupt = hook
    return ctx
```

Add this class before `class OnceLogTests`:

```python
class InterruptTests(unittest.TestCase):
    def test_a_takeover_before_a_step_replaces_the_queue(self):
        grid, state = small_world(), pet(inventory={"planks": 1})
        state["queue"] = [{"kind": "wait", "seconds": 1}, {"kind": "mine", "target": [9, 1, 0]}]
        hook = Takeover(lambda state, at: at >= 1.0, [{"kind": "place", "target": [1, 1, 0], "block": "planks"}])
        advance_actions(state, hooked(grid, hook), 2.0)
        self.assertEqual(grid.material(1, 1, 0), "planks")
        self.assertEqual([(entry["kind"], entry["result"]) for entry in state["recent_actions"]], [("place", "done")])

    def test_a_takeover_cuts_a_walk_at_the_last_cell_it_reached(self):
        grid, state = small_world(), pet()
        state["queue"] = [{"kind": "walk", "target": [8, 1, 0], "purpose": "explore"}]
        ctx = hooked(grid, Takeover(lambda state, at: at >= 1.0, [{"kind": "wait", "seconds": 5}], "head_home"))
        advance_actions(state, ctx, 0.5)
        advance_actions(state, ctx, 1.0)
        self.assertEqual(state["position"], {"x": 3.0, "y": 1.0, "z": 0.0})
        cut = state["recent_actions"][-1]
        self.assertEqual((cut["kind"], cut["result"], cut["reason"], cut["ended_at"], cut["purpose"]),
                         ("walk", "interrupted", "head_home", 1.0, "explore"))
        self.assertIsNone(state["last_failure"])
        self.assertEqual((state["action"]["kind"], state["action"]["started_at"]), ("wait", 1.0))

    def test_sleep_can_be_cut(self):
        state = pet()
        state["vitals"]["energy"] = 50.0
        state["queue"] = [{"kind": "sleep"}]
        hook = Takeover(lambda state, at: state["vitals"]["air"] < 40, [{"kind": "wait", "seconds": 1}], "surface")
        ctx = hooked(small_world(), hook, clock=lambda at: NIGHT)
        advance_actions(state, ctx, 5.0)
        self.assertEqual(state["status"], "sleeping")
        state["vitals"]["air"] = 30.0
        advance_actions(state, ctx, 6.0)
        cut = state["recent_actions"][-1]
        self.assertEqual((cut["kind"], cut["result"], cut["reason"]), ("sleep", "interrupted", "surface"))
        self.assertEqual(state["action"]["kind"], "wait")

    def test_short_steps_finish_before_a_takeover(self):
        grid, state = small_world({(1, 1, 0): "oak_log"}), pet()
        state["queue"] = [{"kind": "mine", "target": [1, 1, 0]}]
        ctx = hooked(grid, Takeover(lambda state, at: at >= 0.5, [{"kind": "wait", "seconds": 1}]))
        advance_actions(state, ctx, 1.0)
        self.assertEqual(state["action"]["kind"], "mine")
        advance_actions(state, ctx, 3.0)
        self.assertEqual(state["recent_actions"][-1]["result"], "done")
        self.assertEqual(grid.material(1, 1, 0), "air")

    def test_a_crashing_hook_is_logged_once_and_ignored(self):
        def broken(state, context, at):
            raise RuntimeError("boom")

        forget_logged()
        state = pet(inventory={"planks": 1})
        state["queue"] = [{"kind": "place", "target": [1, 1, 0], "block": "planks"}]
        with self.assertLogs("backend.survival.actions", level="ERROR") as logs:
            advance_actions(state, hooked(small_world(), broken), 1.0)
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(state["recent_actions"][-1]["result"], "done")

    def test_a_hook_that_always_takes_over_cannot_spin(self):
        def greedy(state, context, at):
            state["queue"] = [{"kind": "wait", "seconds": 1}]
            return "greedy"

        state = pet()
        advance_actions(state, hooked(small_world(), greedy), 0.5)
        self.assertEqual(state["action"]["kind"], "wait")
        self.assertEqual(state["actions_at"], 0.5)
```

In `backend/tests/test_survival_tick_actions.py`, add at the end of `TickActionTests`:

```python
    def test_a_mind_can_interrupt_inside_the_tick(self):
        asked = []

        def hook(state, context, at):
            asked.append(at)
            return None

        tick_life(self.registry, BORN + 5, scale=1, mind=Mind(interrupt=hook))
        self.assertTrue(asked)
        self.assertTrue(all(BORN <= at <= BORN + 5 for at in asked))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_*.py"`
Expected: failures and errors in `InterruptTests` (the hook is never called) and `TypeError: Mind.__init__() got an unexpected keyword argument 'interrupt'`.

- [ ] **Step 3: Ask the hook before steps and during walks, sleep and waits**

In `backend/survival/actions.py`, add to the module docstring, after its last paragraph:

```python
A mind can take over through `context.interrupt` (the brain's reflexes). It is asked before every
step starts and at every advance while a walk, sleep or wait is still running; a cut walk has
already moved to the last cell it reached. The cut step is recorded as "interrupted" with the
hook's reason. At most MAX_TAKEOVERS takeovers happen per advance_actions call, so a hook that
always says yes cannot spin the tick.
```

Replace:

```python
# Waits tell the viewer nothing and would push real steps out of the recent list.
UNRECORDED = frozenset({"wait"})
```

with:

```python
# Waits tell the viewer nothing and would push real steps out of the recent list.
UNRECORDED = frozenset({"wait"})
# Running steps a takeover may cut short. The others last a few seconds at most and finish first.
INTERRUPTIBLE = frozenset({"walk", "sleep", "wait"})
MAX_TAKEOVERS = 4
```

Replace:

```python
# An observer hears about each step that finished well: (state, finished step, context, time).
Observe = Callable[[dict, dict, "ActionContext", float], None]
```

with:

```python
# An observer hears about each step that finished well: (state, finished step, context, time).
Observe = Callable[[dict, dict, "ActionContext", float], None]
# An interrupt hook may take over: it fills the queue with its own steps and returns a reason.
Interrupt = Callable[[dict, "ActionContext", float], "str | None"]
```

In `ActionContext`, replace:

```python
    observe: Observe | None = None
    db: sqlite3.Connection | None = None
    action_scale: float = 1.0
```

with:

```python
    observe: Observe | None = None
    db: sqlite3.Connection | None = None
    action_scale: float = 1.0
    interrupt: Interrupt | None = None
```

Add this function right before `def advance_actions`:

```python
def interrupted(state: dict, context: ActionContext, at: float) -> bool:
    """Ask the interrupt hook whether something takes over at `at`.

    The hook sees the running step (if any) and, to take over, fills the queue with its own steps
    and returns a reason. The running step is then recorded as interrupted and cleared. A
    crashing hook is logged once and counts as no takeover.
    """
    if context.interrupt is None:
        return False
    try:
        reason = context.interrupt(state, context, at)
    except Exception as error:
        log_once(logger, "interrupt", error)
        return False
    if not reason:
        return False
    step = state["action"]
    if step is not None:
        record(state, step, at, "interrupted", reason)
        state["action"] = None
    return True
```

Replace the start of `advance_actions` up to the first queued spec:

```python
    ensure_actions(state)
    grid = context.grid
    at = min(state["actions_at"], until)
    for _ in range(MAX_STEPS_PER_ADVANCE):
        step = state["action"]
        if step is None:
            if start_hazard(state, grid, at):
                continue
            if not state["queue"]:
                state["queue"] = safe_plan(context, state, at)
                if not state["queue"]:
                    break
            spec = state["queue"][0]
```

with:

```python
    ensure_actions(state)
    grid = context.grid
    at = min(state["actions_at"], until)
    takeovers = 0
    for _ in range(MAX_STEPS_PER_ADVANCE):
        step = state["action"]
        if step is None:
            if start_hazard(state, grid, at):
                continue
            if takeovers < MAX_TAKEOVERS and interrupted(state, context, at):
                takeovers += 1
                continue
            if not state["queue"]:
                state["queue"] = safe_plan(context, state, at)
                if not state["queue"]:
                    break
                if context.interrupt is not None:
                    continue  # a fresh plan gets the same takeover check before its first step
            spec = state["queue"][0]
```

Replace:

```python
        end = step_end(step, state, context, until)
        if end is None:
            break
```

with:

```python
        end = step_end(step, state, context, until)
        if end is None:
            if step["kind"] in INTERRUPTIBLE and takeovers < MAX_TAKEOVERS and interrupted(state, context, until):
                takeovers += 1
                at = until
                continue
            break
```

In `backend/survival/tick.py`, replace:

```python
from backend.survival.actions import ActionContext, Observe, Planner, activity_of, advance_actions, ensure_actions
```

with:

```python
from backend.survival.actions import (
    ActionContext, Interrupt, Observe, Planner, activity_of, advance_actions, ensure_actions,
)
```

Replace:

```python
    plan: Planner = rest_plan
    observe: Observe | None = None
    notice: Notice | None = None
```

with:

```python
    plan: Planner = rest_plan
    interrupt: Interrupt | None = None
    observe: Observe | None = None
    notice: Notice | None = None
```

Replace:

```python
                                observe=mind.observe, db=db, action_scale=action_scale)
```

with:

```python
                                observe=mind.observe, db=db, action_scale=action_scale,
                                interrupt=mind.interrupt)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_*.py"`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 251 tests` … `OK` (7 new).

- [ ] **Step 5: Commit**

```bash
git add backend/survival/actions.py backend/survival/tick.py backend/tests/test_survival_actions.py backend/tests/test_survival_tick_actions.py
git commit -m "feat: let a mind take over before steps and cut walks, sleep and waits" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Memory and the brain's saved state

**Files:**
- Create: `backend/survival/memory.py`, `backend/survival/triggers.py`
- Modify: `backend/survival/world.py`
- Test: `backend/tests/test_survival_memory.py`

**Interfaces:**
- Consumes: `SurvivalWorld`, `create_world_tables`, `greet` in `backend.survival.world`; `Cell` from `backend.survival.grid`.
- Produces:
  - `backend.survival.memory`: `SHELTER_KINDS = ("home", "shelter")`; `create_memory_tables(db)`; `places(db, kinds: tuple[str, ...] | None = None) -> list[dict]` (keys `kind, x, y, z, note, found_at, visited_at`, oldest first); `remember(db, kind: str, cell: Cell, at: float, note: str = "") -> bool` (True when new); `forget(db, kind, cell) -> None`; `visit(db, cell, at, reach: int = 2) -> None`; `learn(db, recipe: str, at: float) -> bool` (True the first time); `known_recipes(db) -> list[str]`; `cell_of(place: dict) -> Cell`; `nearest(found: list[dict], here: Cell, kinds: tuple[str, ...], max_distance: float = math.inf) -> dict | None` (horizontal distance).
  - `backend.survival.triggers`: `HOUR = 3600.0`; `new_brain(at) -> dict`; `ensure_brain(state) -> dict`; `mark_trigger(state, reason: str, at: float, urgent: bool = False) -> None`; `crossings(before: dict, after: dict) -> list[str]`; `phase_trigger(before: str, after: str) -> str | None`; `hour_passed(brain: dict, at: float, scale: float) -> bool`. The keys of `state["brain"]` are listed in the module docstring below; later tasks use exactly those names.
  - Every world database has `memory_places` and `memory_recipes` (older worlds get them on their first writable open). `SurvivalWorld.greet` marks a `hello` trigger.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_memory.py`:

```python
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival import world as world_module
from backend.survival.memory import (
    create_memory_tables, forget, known_recipes, learn, nearest, places, remember, visit,
)
from backend.survival.triggers import crossings, ensure_brain, hour_passed, mark_trigger, phase_trigger
from backend.survival.world import SurvivalWorld, new_survival_state, read_state, write_state

SEED = "123456789123456789"
SPAWN = {"x": 3682, "y": 5, "z": 4143}


def memory_db():
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return db


class MemoryTests(unittest.TestCase):
    def test_places_are_remembered_once_with_their_note(self):
        db = memory_db()
        self.assertTrue(remember(db, "ore", (1, -2, 3), 10.0, "iron_ore"))
        self.assertFalse(remember(db, "ore", (1, -2, 3), 11.0, "iron_ore"))
        self.assertTrue(remember(db, "ore", (2, -2, 3), 12.0, "coal_ore"))
        self.assertEqual([(p["kind"], p["x"], p["note"], p["found_at"], p["visited_at"]) for p in places(db)],
                         [("ore", 1, "iron_ore", 10.0, None), ("ore", 2, "coal_ore", 12.0, None)])

    def test_home_is_one_place_and_close_spots_are_the_same_place(self):
        db = memory_db()
        self.assertTrue(remember(db, "home", (0, 5, 0), 1.0))
        self.assertFalse(remember(db, "home", (50, 5, 0), 2.0))
        self.assertFalse(remember(db, "shelter", (5, 5, 0), 3.0))
        self.assertTrue(remember(db, "shelter", (20, 5, 0), 4.0))
        self.assertTrue(remember(db, "water", (30, 2, 10), 5.0))
        self.assertFalse(remember(db, "water", (40, 2, 10), 6.0))
        self.assertEqual([p["kind"] for p in places(db, ("home", "shelter"))], ["home", "shelter"])

    def test_forget_visit_and_nearest(self):
        db = memory_db()
        remember(db, "ore", (1, 0, 1), 1.0, "coal_ore")
        remember(db, "home", (10, 5, 0), 1.0)
        remember(db, "shelter", (40, 5, 0), 1.0)
        visit(db, (11, 5, 1), 9.0)
        found = places(db)
        self.assertEqual(nearest(found, (30, 5, 0), ("home", "shelter"))["x"], 40)
        self.assertEqual(nearest(found, (30, 5, 0), ("home",))["visited_at"], 9.0)
        self.assertIsNone(nearest(found, (100, 5, 0), ("home", "shelter"), max_distance=50))
        forget(db, "ore", (1, 0, 1))
        self.assertEqual([p["kind"] for p in places(db)], ["home", "shelter"])

    def test_recipes_are_learned_once_and_counted(self):
        db = memory_db()
        self.assertTrue(learn(db, "planks", 1.0))
        self.assertFalse(learn(db, "planks", 2.0))
        self.assertTrue(learn(db, "sticks", 3.0))
        self.assertEqual(known_recipes(db), ["planks", "sticks"])
        self.assertEqual(db.execute("SELECT uses FROM memory_recipes WHERE recipe='planks'").fetchone()[0], 2)


class WorldMemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "lives" / "2.sqlite3"
        self.world = SurvivalWorld.create(self.path, new_survival_state(
            name="Pip", seed=SEED, spawn=SPAWN, born_at=1000.0, traits={}))

    def tearDown(self):
        self.directory.cleanup()

    def test_a_new_world_starts_with_empty_memory(self):
        with self.world.connect() as db:
            self.assertEqual(places(db), [])
            self.assertEqual(known_recipes(db), [])

    def test_worlds_from_before_m3_get_the_memory_tables(self):
        with self.world.connect() as db:
            db.execute("DROP TABLE memory_places")
            db.execute("DROP TABLE memory_recipes")
        world_module._schema_ready.discard(self.path.resolve())
        with SurvivalWorld(self.path).connect() as db:
            self.assertEqual(places(db), [])
            self.assertEqual(known_recipes(db), [])

    def test_a_hello_asks_for_a_new_choice(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["last_tick_at"] = 1495.0
            write_state(db, state)
        self.world.greet(1500.0)
        self.assertIn("hello", self.world.state()["brain"]["pending"]["reasons"])


class TriggerTests(unittest.TestCase):
    def test_a_new_brain_waits_for_its_first_choice(self):
        state = {"last_tick_at": 50.0}
        brain = ensure_brain(state)
        self.assertEqual(brain["pending"], {"id": 1, "reasons": ["born"], "since": 50.0, "urgent": False})
        self.assertIsNone(brain["purpose"])
        self.assertIs(ensure_brain(state), brain)

    def test_triggers_merge_and_urgent_ones_get_a_new_id(self):
        state = {"last_tick_at": 0.0}
        brain = ensure_brain(state)
        brain["pending"] = None
        mark_trigger(state, "plan_done", 10.0)
        mark_trigger(state, "dusk", 11.0)
        mark_trigger(state, "dusk", 12.0)
        self.assertEqual(brain["pending"], {"id": 2, "reasons": ["plan_done", "dusk"], "since": 10.0, "urgent": False})
        mark_trigger(state, "hunger_30", 13.0, urgent=True)
        self.assertEqual(brain["pending"], {"id": 3, "reasons": ["plan_done", "dusk", "hunger_30"], "since": 10.0,
                                            "urgent": True})

    def test_crossings_phases_and_the_game_hour(self):
        before = {"health": 100.0, "hunger": 50.2, "warmth": 31.0, "energy": 16.0}
        after = {"health": 100.0, "hunger": 49.9, "warmth": 14.0, "energy": 15.0}
        self.assertEqual(crossings(before, after), ["hunger_50", "warmth_30", "warmth_15"])
        self.assertEqual([phase_trigger("pre_dawn", "dawn"), phase_trigger("day", "dusk"),
                          phase_trigger("dusk", "night"), phase_trigger("day", "day")], ["dawn", "dusk", None, None])
        brain = ensure_brain({"last_tick_at": 0.0})
        self.assertFalse(hour_passed(brain, 100.0, 60.0))
        brain["chosen_at"] = 0.0
        self.assertFalse(hour_passed(brain, 59.0, 60.0))
        self.assertTrue(hour_passed(brain, 60.0, 60.0))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_memory.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.memory'`.

- [ ] **Step 3: Write the memory module**

Create `backend/survival/memory.py`:

```python
"""What a life remembers, kept in its own world database: places and known recipes.

Places are cells worth coming back to, each with the time it was found and last visited:
- home: the first sheltered spot Mimo found (until M5 builds a real one); only ever one
- shelter: other sheltered spots (one per 8 blocks, counting home)
- ore: an ore block Mimo saw, with its material as the note (exact cells)
- danger: a drop or lava Mimo refused to step into, the note says which (one per 2 blocks)
- water: a body of water Mimo swam in (one per 16 blocks)
M4 and M5 add their own kinds (beds, chests, fires, food patches) the same way. Recipes are the
ones Mimo crafted or smelted successfully. A new life's world starts with empty tables: that
is what "fresh start" wipes.
"""

from __future__ import annotations

import math
import sqlite3

from backend.survival.grid import Cell

SHELTER_KINDS = ("home", "shelter")
# A new place this close to a known place of the listed kinds is that same place.
SAME_PLACE: dict[str, tuple[float, tuple[str, ...]]] = {
    "shelter": (8.0, SHELTER_KINDS),
    "danger": (2.0, ("danger",)),
    "water": (16.0, ("water",)),
}
PLACE_COLUMNS = ("kind", "x", "y", "z", "note", "found_at", "visited_at")


def create_memory_tables(db: sqlite3.Connection) -> None:
    """Create the memory tables. Run it inside the caller's BEGIN IMMEDIATE."""
    db.execute("CREATE TABLE IF NOT EXISTS memory_places (kind TEXT NOT NULL, x INTEGER NOT NULL, "
               "y INTEGER NOT NULL, z INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', found_at REAL NOT NULL, "
               "visited_at REAL, PRIMARY KEY (kind, x, y, z))")
    db.execute("CREATE TABLE IF NOT EXISTS memory_recipes (recipe TEXT PRIMARY KEY, learned_at REAL NOT NULL, "
               "uses INTEGER NOT NULL DEFAULT 1)")


def places(db: sqlite3.Connection, kinds: tuple[str, ...] | None = None) -> list[dict]:
    """Remembered places, oldest first, as dicts with kind, x, y, z, note, found_at and visited_at."""
    query = f"SELECT {','.join(PLACE_COLUMNS)} FROM memory_places"
    params: tuple = ()
    if kinds:
        query += f" WHERE kind IN ({','.join('?' * len(kinds))})"
        params = tuple(kinds)
    rows = db.execute(query + " ORDER BY found_at, rowid", params).fetchall()
    return [dict(zip(PLACE_COLUMNS, tuple(row))) for row in rows]


def remember(db: sqlite3.Connection, kind: str, cell: Cell, at: float, note: str = "") -> bool:
    """Remember a place. False when it is already known: home is only ever one place, and a spot
    close to a known one (SAME_PLACE) counts as that one."""
    x, y, z = cell
    if kind == "home":
        if db.execute("SELECT 1 FROM memory_places WHERE kind='home'").fetchone():
            return False
    elif kind in SAME_PLACE:
        reach, kinds = SAME_PLACE[kind]
        box = math.ceil(reach)
        rows = db.execute(f"SELECT x,y,z FROM memory_places WHERE kind IN ({','.join('?' * len(kinds))}) "
                          "AND x BETWEEN ? AND ? AND z BETWEEN ? AND ?",
                          (*kinds, x - box, x + box, z - box, z + box)).fetchall()
        if any(math.dist(tuple(row), cell) <= reach for row in rows):
            return False
    cursor = db.execute("INSERT OR IGNORE INTO memory_places(kind,x,y,z,note,found_at) VALUES (?,?,?,?,?,?)",
                        (kind, x, y, z, note, at))
    return cursor.rowcount == 1


def forget(db: sqlite3.Connection, kind: str, cell: Cell) -> None:
    db.execute("DELETE FROM memory_places WHERE kind=? AND x=? AND y=? AND z=?", (kind, *cell))


def visit(db: sqlite3.Connection, cell: Cell, at: float, reach: int = 2) -> None:
    """Mark every place within `reach` cells (on each axis) of `cell` as visited now."""
    x, y, z = cell
    db.execute("UPDATE memory_places SET visited_at=? WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? "
               "AND z BETWEEN ? AND ?", (at, x - reach, x + reach, y - reach, y + reach, z - reach, z + reach))


def learn(db: sqlite3.Connection, recipe: str, at: float) -> bool:
    """Count a recipe Mimo used successfully. True the first time."""
    cursor = db.execute("INSERT OR IGNORE INTO memory_recipes(recipe, learned_at) VALUES (?, ?)", (recipe, at))
    if cursor.rowcount == 1:
        return True
    db.execute("UPDATE memory_recipes SET uses = uses + 1 WHERE recipe=?", (recipe,))
    return False


def known_recipes(db: sqlite3.Connection) -> list[str]:
    return [row[0] for row in db.execute("SELECT recipe FROM memory_recipes ORDER BY learned_at, recipe").fetchall()]


def cell_of(place: dict) -> Cell:
    return place["x"], place["y"], place["z"]


def nearest(found: list[dict], here: Cell, kinds: tuple[str, ...], max_distance: float = math.inf) -> dict | None:
    """The closest remembered place of these kinds by horizontal distance, within `max_distance`."""
    best: tuple[float, dict] | None = None
    for place in found:
        if place["kind"] not in kinds:
            continue
        distance = math.hypot(place["x"] - here[0], place["z"] - here[2])
        if distance <= max_distance and (best is None or distance < best[0]):
            best = (distance, place)
    return best[1] if best else None
```

- [ ] **Step 4: Write the brain's saved state and triggers**

Create `backend/survival/triggers.py`:

```python
"""The brain's saved state and the triggers that ask Mimo to choose a new purpose.

Everything the brain keeps lives in state["brain"], saved as JSON with the rest of the state:

- purpose, picker, chosen_at: the current purpose (or None), who chose it ("jev", "luna" or
  "utility") and when (server time)
- batches, planned_at, replans, handled_failure: how many batches of steps the purpose finished
  well, when the last batch was planned, failures re-planned since a batch last finished well,
  and the last `state["last_failure"]` the brain already dealt with
- pending: a choice Mimo is waiting for, {"id", "reasons", "since", "urgent"}, or None; next_id
- penalties: {purpose: server time until which it scores lower, after it failed twice}
- reflex, set_aside, reflex_ends: the reflex running now (or None), the purpose's steps it set
  aside, and {reflex: server time it last ended} for cooldowns
- calls, last_call_at: today's model-call counters {"day", "model", "luna", "reflections"} and
  the server time of the last model call
- explored, escaped_at, dig_heading: explore walks so far (to vary the heading), the last
  dig-out of a pit, and the [dx, dz] heading gather_stone last dug in
- found: ore materials and "water" Mimo has discovered at least once (first sightings trigger a choice)

The tick marks triggers (backend.survival.brain); the worker's Chooser answers them
(backend.survival.choosing).
"""

from __future__ import annotations

HOUR = 3600.0  # one game hour, in game seconds
CROSSING_VITALS = ("health", "hunger", "warmth", "energy")
CROSSING_LEVELS = (50.0, 30.0, 15.0)
PHASE_TRIGGERS = ("dawn", "dusk")
REASON_LIMIT = 8


def new_brain(at: float) -> dict:
    """A brain with no purpose that waits for its first choice."""
    return {"purpose": None, "picker": None, "chosen_at": None, "batches": 0, "planned_at": None, "replans": 0,
            "handled_failure": None, "found": [],
            "pending": {"id": 1, "reasons": ["born"], "since": at, "urgent": False}, "next_id": 2,
            "penalties": {}, "reflex": None, "set_aside": [], "reflex_ends": {},
            "calls": {"day": None, "model": 0, "luna": 0, "reflections": 0}, "last_call_at": None,
            "explored": 0, "escaped_at": None, "dig_heading": None}


def ensure_brain(state: dict) -> dict:
    """The brain's state, created on first use (worlds from before M3 have none)."""
    brain = state.get("brain")
    if brain is None:
        brain = state["brain"] = new_brain(state.get("last_tick_at", 0.0))
    return brain


def mark_trigger(state: dict, reason: str, at: float, urgent: bool = False) -> None:
    """Ask for a new choice. A pending choice keeps its id and gains the reason. An urgent trigger
    (a vital crossing) gives it a new id instead, so an answer still being worked out for the old
    id is thrown away when it arrives: the state moved on."""
    brain = ensure_brain(state)
    pending = brain["pending"]
    if pending is not None and not urgent:
        if reason not in pending["reasons"]:
            pending["reasons"] = [*pending["reasons"], reason][-REASON_LIMIT:]
        return
    reasons = [] if pending is None else [known for known in pending["reasons"] if known != reason]
    brain["pending"] = {"id": brain["next_id"], "reasons": [*reasons, reason][-REASON_LIMIT:],
                        "since": at if pending is None else pending["since"],
                        "urgent": urgent or bool(pending and pending["urgent"])}
    brain["next_id"] += 1


def crossings(before: dict, after: dict) -> list[str]:
    """Vitals that fell past 50, 30 or 15 between two readings, as reasons like "hunger_30"."""
    return [f"{name}_{int(level)}" for name in CROSSING_VITALS for level in CROSSING_LEVELS
            if before[name] >= level > after[name]]


def phase_trigger(before: str, after: str) -> str | None:
    """"dawn" or "dusk" when the clock just entered that phase."""
    return after if after != before and after in PHASE_TRIGGERS else None


def hour_passed(brain: dict, at: float, scale: float) -> bool:
    """True once a game hour has passed since the last choice."""
    return brain["chosen_at"] is not None and (at - brain["chosen_at"]) * scale >= HOUR
```

- [ ] **Step 5: Add memory to the world schema and a trigger to hello**

In `backend/survival/world.py`, replace:

```python
from backend.services.worldgen import WORLD_MAX_Y, WORLD_MIN_Y, terrain_height
from backend.survival.vitals import START_VITALS
```

with:

```python
from backend.services.worldgen import WORLD_MAX_Y, WORLD_MIN_Y, terrain_height
from backend.survival.memory import create_memory_tables
from backend.survival.triggers import mark_trigger
from backend.survival.vitals import START_VITALS
```

Replace:

```python
    db.execute("CREATE TABLE IF NOT EXISTS mimo_events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL)")
    create_block_tables(db)
```

with:

```python
    db.execute("CREATE TABLE IF NOT EXISTS mimo_events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL)")
    create_block_tables(db)
    create_memory_tables(db)
```

In `greet`, replace:

```python
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + 5)
            state["last_hello_at"] = timestamp
            write_state(db, state)
```

with:

```python
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + 5)
            state["last_hello_at"] = timestamp
            mark_trigger(state, "hello", timestamp)
            write_state(db, state)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_memory.py" -v`
Expected: `Ran 10 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 261 tests` … `OK`.

- [ ] **Step 7: Commit**

```bash
git add backend/survival/memory.py backend/survival/triggers.py backend/survival/world.py backend/tests/test_survival_memory.py
git commit -m "feat: remember places and recipes per life and keep the brain's triggers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Situation, the purpose registry and the simple purposes

**Files:**
- Create: `backend/survival/situation.py`, `backend/survival/senses.py`, `backend/survival/purposes.py`
- Modify: `backend/survival/script.py` (import `trees_near` from `senses`)
- Test: `backend/tests/test_survival_purposes.py`

**Interfaces:**
- Consumes: Task 5's `memory` and `triggers`; `ActionContext` (Task 1); `steps.FOOD`, `steps.as_cell`; `clock.clock_at`, `clock.is_night`, `clock.DAY_SECONDS`; `grid.world_grid`.
- Produces:
  - `backend.survival.situation`: `DUSK = 2220.0`, `NIGHTFALL = 2400.0`; `@dataclass class Situation(state: dict, grid: Grid, clock: dict, at: float, db: sqlite3.Connection | None = None)` with cached `places: list[dict]` and `recipes: list[str]`, properties `here: Cell`, `vitals`, `inventory`, `brain` (via `ensure_brain`), `seed`, `phase`, `night: bool`, `scale: float`, and methods `trait(name) -> float` (50 when missing), `count(*items) -> int`, `distance(cell) -> float` (3D), `seconds_to(seconds_into_day) -> float` (game seconds); `in_tick(state, context, at) -> Situation`; `from_db(db, state, at, scale) -> Situation`.
  - `backend.survival.senses`: `TREE_SEARCH = 24`; `trees_near(seed, x, z, radius) -> list[tuple[int, int, int]]`.
  - `backend.survival.purposes`: `@dataclass(frozen=True) class Purpose(name, phrase, description, valid, facts, score, plan, thoughts)` where `valid(s) -> bool`, `facts(s) -> str`, `score(s) -> float`, `plan(s, context) -> list[dict]`, `thoughts: tuple[str, ...]`; `PURPOSES: dict[str, Purpose]`; `register(purpose) -> Purpose`; `is_valid(purpose, s) -> bool`; `offered(s) -> list[Purpose]`; `walk_to(cell, reach=0.0) -> dict`; `home_of(s) -> dict | None`; `at_home(s, reach=AT_HOME) -> bool`; `late_day(s) -> bool`; `foods(inventory) -> list[str]`; `meal(inventory, hunger, full=FULL) -> list[dict]`; constants `HOME_RANGE = 64.0`, `AT_HOME = 2.0`, `TIRED_BELOW = 30.0`. Registered: `rest`, `sleep`, `explore`, `go_home`, `eat`.
  - `brain["batches"]` counts batches that finished well (Task 9 keeps it). A planner returns `[]` when its purpose is finished.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_purposes.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, remember
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES, Purpose, meal, offered, register
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
DUSK = {**DAY, "phase": "dusk", "seconds_into_day": 2300.0}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
SIMPLE = ("rest", "sleep", "explore", "go_home", "eat")


def flat(cells=None):
    """Stone at y <= 0 and air above, with `cells` overriding single cells."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("stone" if y <= 0 else "air"))


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state=None, clock=DAY, grid=None, places=()):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    for kind, cell in places:
        remember(db, kind, cell, 0.0)
    return Situation(state or pet(), grid or flat(), clock, 0.0, db)


def context(grid=None):
    return ActionContext(grid=grid or flat(), clock_at=lambda at: DAY, planner=lambda *args: [], events=[])


def names(s):
    """The simple purposes on offer (other test modules may have registered more)."""
    return [purpose.name for purpose in offered(s) if purpose.name in SIMPLE]


class RegistryTests(unittest.TestCase):
    def test_registering_adds_a_purpose_and_a_crashing_check_is_not_offered(self):
        def boom(s):
            raise RuntimeError("boom")

        extra = Purpose("test_extra", "test", "A test purpose.", lambda s: True, lambda s: "", lambda s: 1.0,
                        lambda s, context: [], ("Hm.",))
        broken = Purpose("test_broken", "break", "A broken purpose.", boom, lambda s: "", lambda s: 1.0,
                         lambda s, context: [], ("Oops.",))
        forget_logged()
        try:
            register(extra)
            register(broken)
            with self.assertLogs("backend.survival.purposes", level="ERROR"):
                offered_names = [purpose.name for purpose in offered(situation())]
            self.assertIn("test_extra", offered_names)
            self.assertNotIn("test_broken", offered_names)
        finally:
            PURPOSES.pop("test_extra", None)
            PURPOSES.pop("test_broken", None)

    def test_m3_registers_the_simple_purposes(self):
        for name in SIMPLE:
            self.assertIn(name, PURPOSES)


class SimplePurposeTests(unittest.TestCase):
    def test_by_day_rest_and_explore_are_offered(self):
        self.assertEqual(names(situation()), ["rest", "explore"])

    def test_at_night_mimo_goes_home_then_sleeps(self):
        away = situation(clock=NIGHT, places=[("home", (20, 1, 0))])
        self.assertEqual(names(away), ["rest", "sleep", "go_home"])
        self.assertEqual(PURPOSES["go_home"].plan(away, context()), [{"kind": "walk", "target": [20, 1, 0], "reach": 0.0}])
        self.assertGreater(PURPOSES["go_home"].score(away), PURPOSES["sleep"].score(away))
        near = situation(clock=NIGHT, places=[("home", (5, 1, 0))])
        self.assertEqual(PURPOSES["sleep"].plan(near, context()),
                         [{"kind": "walk", "target": [5, 1, 0], "reach": 0.0}, {"kind": "sleep"}])
        near.state["last_failure"] = {"code": "no_path", "reason": "no way there", "kind": "walk",
                                      "cell": {"x": 5, "y": 1, "z": 0}, "purpose": "sleep", "at": 0.0, "seq": 1}
        self.assertEqual(PURPOSES["sleep"].plan(near, context()), [{"kind": "sleep"}])
        home = situation(clock=NIGHT, places=[("home", (1, 1, 0))])
        self.assertEqual(names(home), ["rest", "sleep"])
        self.assertEqual(PURPOSES["sleep"].plan(home, context()), [{"kind": "sleep"}])

    def test_at_dusk_mimo_waits_at_home_for_nightfall(self):
        home = situation(clock=DUSK, places=[("home", (1, 1, 0))])
        self.assertEqual(names(home), ["rest", "sleep"])
        self.assertEqual(PURPOSES["sleep"].plan(home, context()), [{"kind": "wait", "seconds": 60.0}])

    def test_rest_waits_a_game_minute_once(self):
        s = situation()
        self.assertEqual(PURPOSES["rest"].plan(s, context()), [{"kind": "wait", "seconds": 60.0}])
        fast = situation(clock={**DAY, "time_scale": 60.0})
        self.assertEqual(PURPOSES["rest"].plan(fast, context()), [{"kind": "wait", "seconds": 1.0}])
        s.brain["batches"] = 1
        self.assertEqual(PURPOSES["rest"].plan(s, context()), [])

    def test_explore_walks_out_in_a_new_direction_each_time(self):
        state = pet()
        with patch("backend.survival.purposes.terrain_height", lambda x, z, seed: 0):
            first = PURPOSES["explore"].plan(situation(state), context())
            second = PURPOSES["explore"].plan(situation(state), context())
        self.assertEqual(first, [{"kind": "walk", "target": [34, 1, 34], "reach": 3.0}])
        self.assertEqual(second, [{"kind": "walk", "target": [-48, 1, 0], "reach": 3.0}])
        self.assertEqual(state["brain"]["explored"], 2)

    def test_explore_scores_higher_with_no_trees_near(self):
        s = situation()
        with patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: []):
            lonely = PURPOSES["explore"].score(s)
        with patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [(5, 0, 0)]):
            wooded = PURPOSES["explore"].score(s)
        self.assertEqual(lonely - wooded, 25.0)

    def test_eat_is_offered_with_food_and_eats_the_best_first(self):
        hungry = pet(inventory={"berries": 3, "bread": 1}, vitals={**START_VITALS, "hunger": 50.0})
        self.assertIn("eat", names(situation(hungry)))
        self.assertNotIn("eat", names(situation(pet(inventory={"berries": 3}))))
        self.assertEqual(PURPOSES["eat"].plan(situation(hungry), context()),
                         [{"kind": "eat", "item": "bread"}, {"kind": "eat", "item": "berries"},
                          {"kind": "eat", "item": "berries"}])
        self.assertEqual(meal({"berries": 1}, 10.0), [{"kind": "eat", "item": "berries"}])


class SituationTests(unittest.TestCase):
    def test_memory_is_read_once_and_traits_default_to_fifty(self):
        s = situation(places=[("home", (3, 1, 0))])
        self.assertEqual(s.places[0]["kind"], "home")
        s.db.execute("DELETE FROM memory_places")
        self.assertEqual(len(s.places), 1)
        self.assertEqual((s.here, s.trait("curiosity"), s.night), ((0, 1, 0), 50.0, False))
        self.assertEqual(s.seconds_to(2400.0), 1400.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_purposes.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.purposes'`.

- [ ] **Step 3: Move `trees_near` into a senses module**

Create `backend/survival/senses.py`:

```python
"""Looking around: what the world near Mimo offers.

Trees come from worldgen (cheap, no block reads). Whether their logs still stand, ores and open
cells are read through a Grid, so Mimo's own edits count.
"""

from __future__ import annotations

import math

from backend.services.worldgen import trees_in_chunk
from backend.survival.grid import CHUNK

TREE_SEARCH = 24


def trees_near(seed: str, x: int, z: int, radius: int) -> list[tuple[int, int, int]]:
    """Generated trees (trunk x, trunk z, ground height) within `radius` blocks of (x, z)."""
    found = []
    for cx in range((x - radius) // CHUNK, (x + radius) // CHUNK + 1):
        for cz in range((z - radius) // CHUNK, (z + radius) // CHUNK + 1):
            found.extend(tree for tree in trees_in_chunk(cx, cz, seed)
                         if math.hypot(tree[0] - x, tree[1] - z) <= radius)
    return found
```

In `backend/survival/script.py`, replace:

```python
from backend.services.worldgen import terrain_height, trees_in_chunk
from backend.survival.clock import is_night
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.steps import as_cell
```

with:

```python
from backend.services.worldgen import terrain_height
from backend.survival.clock import is_night
from backend.survival.grid import Cell, Grid
from backend.survival.senses import trees_near
from backend.survival.steps import as_cell
```

and delete the whole `trees_near` function from `script.py` (the `def trees_near(...)` block and its body).

- [ ] **Step 4: Write the Situation**

Create `backend/survival/situation.py`:

```python
"""What Mimo knows at one moment: its state, the world around it, the clock and its memory.

Purposes and reflexes read a Situation instead of the raw state. The tick builds one inside its
transaction (`in_tick`); the worker builds one from a read-only connection when it offers
choices (`from_db`). Memory is read at most once per Situation, and only when asked for.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from backend.survival import memory
from backend.survival.clock import DAY_SECONDS, clock_at, is_night
from backend.survival.grid import Cell, Grid, world_grid
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

DUSK = 2220.0
NIGHTFALL = 2400.0


@dataclass
class Situation:
    state: dict
    grid: Grid
    clock: dict
    at: float
    db: sqlite3.Connection | None = None

    @cached_property
    def places(self) -> list[dict]:
        return memory.places(self.db) if self.db is not None else []

    @cached_property
    def recipes(self) -> list[str]:
        return memory.known_recipes(self.db) if self.db is not None else []

    @property
    def here(self) -> Cell:
        return as_cell(self.state["position"])

    @property
    def vitals(self) -> dict:
        return self.state["vitals"]

    @property
    def inventory(self) -> dict:
        return self.state["inventory"]

    @property
    def brain(self) -> dict:
        return ensure_brain(self.state)

    @property
    def seed(self) -> str:
        return self.state["world_seed"]

    @property
    def phase(self) -> str:
        return self.clock["phase"]

    @property
    def night(self) -> bool:
        return is_night(self.phase)

    @property
    def scale(self) -> float:
        return self.clock["time_scale"]

    def trait(self, name: str) -> float:
        """A trait from 0 to 100; 50 when the life has none (tests, older states)."""
        return float(self.state.get("traits", {}).get(name, 50))

    def count(self, *items: str) -> int:
        return sum(self.inventory.get(item, 0) for item in items)

    def distance(self, cell: Cell) -> float:
        return math.dist(self.here, cell)

    def seconds_to(self, seconds_into_day: float) -> float:
        """Game seconds until that time of day comes round (0 when it is now)."""
        return (seconds_into_day - self.clock["seconds_into_day"]) % DAY_SECONDS


def in_tick(state: dict, context: ActionContext, at: float) -> Situation:
    return Situation(state, context.grid, context.clock_at(at), at, context.db)


def from_db(db: sqlite3.Connection, state: dict, at: float, scale: float) -> Situation:
    return Situation(state, world_grid(db, state["world_seed"]), clock_at(state["born_at"], at, scale), at, db)
```

- [ ] **Step 5: Write the purpose registry and the simple purposes**

Create `backend/survival/purposes.py`:

```python
"""Purposes: the goals Mimo chooses between, as a registry.

A Purpose has a validity check (is it on offer right now?), facts for the chooser, a utility
score and a planner that turns it into the next batch of M2 steps. The planner returns [] when
the purpose is finished or cannot go on; the brain then asks for a new choice. Planners get the
tick's ActionContext and spend its path-search budget through actions.take_search if they search.

Modules register their purposes on import: this one registers rest, sleep, explore, go_home and
eat; backend.survival.work registers gather_wood, gather_stone and mine_ore; and
backend.survival.toolmaking registers craft_tools. backend.survival.brain imports them all.
M4 and M5 register forage, fish, farm, cook, build_* and light_up the same way; nothing here
changes for them.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from backend.services.worldgen import terrain_height
from backend.survival.memory import SHELTER_KINDS, cell_of, nearest
from backend.survival.once import log_once
from backend.survival.senses import TREE_SEARCH, trees_near
from backend.survival.situation import DUSK, NIGHTFALL, Situation
from backend.survival.steps import FOOD

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

REST_GAME_SECONDS = 60.0
AT_HOME = 2.0
HOME_RANGE = 64.0
SLEEP_HOME_REACH = 8.0
TIRED_BELOW = 30.0
GO_HOME_BATCHES = 3
EXPLORE_DISTANCE = 48
EXPLORE_REACH = 3.0
HEADINGS = 8
LATE_DAY = DUSK - 300.0  # 5 game minutes before dusk
EAT_BELOW = 70.0
FULL = 90.0


@dataclass(frozen=True)
class Purpose:
    name: str
    phrase: str  # completes "Pip chose to ...", for example "gather wood"
    description: str  # what it means, for the model chooser
    valid: Callable[[Situation], bool]
    facts: Callable[[Situation], str]
    score: Callable[[Situation], float]
    plan: Callable[[Situation, "ActionContext"], list[dict]]
    thoughts: tuple[str, ...]


PURPOSES: dict[str, Purpose] = {}


def register(purpose: Purpose) -> Purpose:
    """Add a purpose, or replace the one with the same name."""
    PURPOSES[purpose.name] = purpose
    return purpose


def is_valid(purpose: Purpose, situation: Situation) -> bool:
    """A purpose's validity check. One that crashes counts as not valid (logged once)."""
    try:
        return bool(purpose.valid(situation))
    except Exception as error:
        log_once(logger, f"{purpose.name} validity", error)
        return False


def offered(situation: Situation) -> list[Purpose]:
    """The purposes on offer right now, in registration order."""
    return [purpose for purpose in PURPOSES.values() if is_valid(purpose, situation)]


def walk_to(cell, reach: float = 0.0) -> dict:
    return {"kind": "walk", "target": [int(cell[0]), int(cell[1]), int(cell[2])], "reach": reach}


def home_of(s: Situation) -> dict | None:
    """The nearest remembered home or shelter within HOME_RANGE blocks."""
    return nearest(s.places, s.here, SHELTER_KINDS, HOME_RANGE)


def at_home(s: Situation, reach: float = AT_HOME) -> bool:
    home = home_of(s)
    return home is not None and s.distance(cell_of(home)) <= reach


def late_day(s: Situation) -> bool:
    """Dusk, or the last 5 game minutes of the day before it."""
    return s.phase == "dusk" or (s.phase == "day" and s.clock["seconds_into_day"] >= LATE_DAY)


def wait_for_nightfall(s: Situation) -> dict:
    return {"kind": "wait", "seconds": max(1.0, min(60.0, s.seconds_to(NIGHTFALL) / s.scale))}


def foods(inventory: dict) -> list[str]:
    """Food Mimo carries, best first."""
    return sorted((item for item in FOOD if inventory.get(item, 0) > 0), key=lambda item: -FOOD[item])


def meal(inventory: dict, hunger: float, full: float = FULL) -> list[dict]:
    """Eat steps, best food first, until hunger would reach `full` or the food runs out."""
    steps, left = [], dict(inventory)
    for item in foods(inventory):
        while left.get(item, 0) > 0 and hunger < full:
            steps.append({"kind": "eat", "item": item})
            left[item] -= 1
            hunger += FOOD[item]
    return steps


# rest ------------------------------------------------------------------------------------------

def rest_score(s: Situation) -> float:
    return 10.0 + s.trait("patience") / 10 + (20.0 if s.vitals["mood"] < 30 else 0.0)


def plan_rest(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return [{"kind": "wait", "seconds": max(1.0, REST_GAME_SECONDS / s.scale)}]


register(Purpose(
    "rest", "rest", "Stay put and rest for a game minute.",
    valid=lambda s: True,
    facts=lambda s: f"mood {round(s.vitals['mood'])}, energy {round(s.vitals['energy'])}",
    score=rest_score, plan=plan_rest,
    thoughts=("I'll sit here for a moment.", "A little rest won't hurt.")))


# sleep -----------------------------------------------------------------------------------------

def sleep_valid(s: Situation) -> bool:
    return s.night or s.vitals["energy"] < TIRED_BELOW or (s.phase == "dusk" and at_home(s))


def sleep_facts(s: Situation) -> str:
    home = home_of(s)
    where = f"a shelter {round(s.distance(cell_of(home)))} blocks away" if home else "no shelter known"
    return f"{s.phase}, energy {round(s.vitals['energy'])}, {where}"


def sleep_score(s: Situation) -> float:
    if s.night:
        return 90.0
    if s.vitals["energy"] < TIRED_BELOW:
        return 70.0 + (TIRED_BELOW - s.vitals["energy"])
    return 60.0


def plan_sleep(s: Situation, context: ActionContext) -> list[dict]:
    """Walk to a shelter within 8 blocks, then sleep; at dusk, wait there for nightfall. After a
    walk there failed, sleep where Mimo stands."""
    steps = []
    home = nearest(s.places, s.here, SHELTER_KINDS, SLEEP_HOME_REACH)
    tried = (s.state.get("last_failure") or {}).get("purpose") == "sleep"
    if home is not None and s.distance(cell_of(home)) > 1.0 and not tried:
        steps.append(walk_to(cell_of(home)))
    steps.append({"kind": "sleep"} if s.night or s.vitals["energy"] < TIRED_BELOW else wait_for_nightfall(s))
    return steps


register(Purpose(
    "sleep", "sleep", "Sleep until rested and it is day, in a shelter if one is close.",
    valid=sleep_valid, facts=sleep_facts, score=sleep_score, plan=plan_sleep,
    thoughts=("Time to curl up and sleep.", "My eyes are so heavy.")))


# explore ---------------------------------------------------------------------------------------

def explore_score(s: Situation) -> float:
    x, _, z = s.here
    score = 20.0 + s.trait("curiosity") / 5
    if not trees_near(s.seed, x, z, TREE_SEARCH):
        score += 25.0
    if late_day(s):
        score -= 30.0
    return score


def explore_facts(s: Situation) -> str:
    x, _, z = s.here
    trees = len(trees_near(s.seed, x, z, TREE_SEARCH))
    return f"{trees} trees within {TREE_SEARCH} blocks, {s.brain['explored']} trips so far"


def plan_explore(s: Situation, context: ActionContext) -> list[dict]:
    """One walk 48 blocks out, in a heading that changes with every trip and every day."""
    if s.brain["batches"] > 0:
        return []
    x, _, z = s.here
    turn = s.brain["explored"]
    s.brain["explored"] = turn + 1
    angle = ((turn * 3 + s.clock["day_number"]) % HEADINGS) * 2 * math.pi / HEADINGS
    tx, tz = x + round(math.cos(angle) * EXPLORE_DISTANCE), z + round(math.sin(angle) * EXPLORE_DISTANCE)
    return [walk_to((tx, terrain_height(tx, tz, s.seed) + 1, tz), EXPLORE_REACH)]


register(Purpose(
    "explore", "explore", "Walk out 48 blocks to see new land, trees and places.",
    valid=lambda s: not s.night and s.phase != "dusk",
    facts=explore_facts, score=explore_score, plan=plan_explore,
    thoughts=("I wonder what's over there.", "Let's see what lies beyond those hills.")))


# go_home ---------------------------------------------------------------------------------------

def go_home_valid(s: Situation) -> bool:
    home = home_of(s)
    return home is not None and s.distance(cell_of(home)) > AT_HOME


def go_home_score(s: Situation) -> float:
    if s.night or s.phase == "dusk":
        return 100.0  # beats sleep (90) by more than the utility picker's random nudge (6)
    if late_day(s):
        return 70.0 + s.trait("caution") / 10
    return 5.0 + (30.0 if s.vitals["warmth"] < 40 else 0.0)


def plan_go_home(s: Situation, context: ActionContext) -> list[dict]:
    home = home_of(s)
    if home is None or s.distance(cell_of(home)) <= AT_HOME or s.brain["batches"] >= GO_HOME_BATCHES:
        return []
    return [walk_to(cell_of(home))]


register(Purpose(
    "go_home", "go home", "Walk back to the nearest known shelter.",
    valid=go_home_valid,
    facts=lambda s: f"a shelter {round(s.distance(cell_of(home_of(s))))} blocks away",
    score=go_home_score, plan=plan_go_home,
    thoughts=("I should head back to my shelter.", "Home is the safest place to be.")))


# eat -------------------------------------------------------------------------------------------

def plan_eat(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return meal(s.inventory, s.vitals["hunger"])


register(Purpose(
    "eat", "eat", "Eat carried food, the best first.",
    valid=lambda s: bool(foods(s.inventory)) and s.vitals["hunger"] < EAT_BELOW,
    facts=lambda s: f"hunger {round(s.vitals['hunger'])}, carrying {s.count(*FOOD)} food",
    score=lambda s: 100.0 - s.vitals["hunger"], plan=plan_eat,
    thoughts=("Time for a snack.", "Food first, then everything else.")))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_purposes.py" -v`
Expected: `Ran 10 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 271 tests` … `OK` (the script tests still patch `backend.survival.script.trees_near`, which is now the imported name).

- [ ] **Step 7: Commit**

```bash
git add backend/survival/situation.py backend/survival/senses.py backend/survival/purposes.py backend/survival/script.py backend/tests/test_survival_purposes.py
git commit -m "feat: add the purpose registry with rest, sleep, explore, go home and eat" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Gathering purposes: wood, stone and ore

**Files:**
- Create: `backend/survival/work.py`
- Modify: `backend/survival/senses.py`
- Test: `backend/tests/test_survival_work.py`

**Interfaces:**
- Consumes: Task 6's `Purpose`, `register`, `walk_to`, `Situation`; Task 5's `memory.cell_of`, `memory.forget`; `crafting.BLOCKS`, `crafting.can_harvest`; `blocks.hardness`, `blocks.is_solid`; `steps.REACH`; `worldgen.terrain_height`.
- Produces:
  - `backend.survival.senses`: `TRUNK_HEIGHT = 4`, `LOG = "oak_log"`, `ORES = ("coal_ore", "iron_ore", "copper_ore")`; `failed_columns(state) -> set[tuple[int, int]]`; `standing_logs(grid, seed, here, skip=frozenset(), radius=TREE_SEARCH) -> list[Cell]`; `ores_around(grid, cell) -> list[tuple[Cell, str]]` (the 26 neighbours, in x, y, z loop order).
  - `backend.survival.work`: `WOOD_GOAL = 8.0`, `STONE_GOAL = 12`, `STAIRS_PER_BATCH = 4`, `TUNNEL_DEPTH = 10`, `LOWEST_FLOOR = -3`, `ORE_RANGE = 48.0`; `wood(inventory) -> float`; `has_pickaxe(inventory) -> bool`; `stair(grid, changed, at, heading, inventory, seed) -> tuple[list[dict], Cell, int] | None`; `dig_heading(s) -> tuple[int, int] | None`; `wanted_ores(s) -> tuple[str, ...]`; `prospecting(s) -> bool`; `wants_stone(s) -> bool`; `ore_targets(s) -> list[dict]`. Registered: `gather_wood`, `gather_stone`, `mine_ore`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_work.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, places, remember
from backend.survival.purposes import PURPOSES
from backend.survival.senses import ores_around
from backend.survival.situation import Situation
from backend.survival import work  # noqa: F401  (registers the gathering purposes)
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
TREE = (5, 0, 0)  # trunk x, trunk z, ground height: logs at y 1 to 4


def forest():
    """Flat stone with one oak trunk at x=5, z=0 (logs at y 1 to 4)."""
    return Grid(lambda x, y, z: "oak_log" if (x, z) == (5, 0) and 1 <= y <= 4 else ("stone" if y <= 0 else "air"))


def ground(cells=None):
    """Grass at y 0, dirt at y -1 and -2, stone to y -4, bedrock below; `cells` override single cells."""
    cells = cells or {}

    def rule(x, y, z):
        if (x, y, z) in cells:
            return cells[(x, y, z)]
        if y <= -5:
            return "bedrock"
        if y <= -3:
            return "stone"
        if y <= -1:
            return "dirt"
        return "grass" if y == 0 else "air"

    return Grid(rule)


def pet(position=(0, 1, 0), **changes):
    state = {"name": "Pip", "world_seed": "1", "inventory": {}, "vitals": dict(START_VITALS), "traits": {},
             "last_tick_at": 0.0, "position": {"x": float(position[0]), "y": float(position[1]), "z": float(position[2])}}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state, grid, places_seen=()):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    for kind, cell, note in places_seen:
        remember(db, kind, cell, 0.0, note)
    return Situation(state, grid, DAY, 0.0, db)


def context(grid):
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[])


def mine(x, y, z):
    return {"kind": "mine", "target": [x, y, z]}


def walk(x, y, z, reach=0.0):
    return {"kind": "walk", "target": [x, y, z], "reach": reach}


@patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [TREE])
class WoodTests(unittest.TestCase):
    def test_chops_the_nearest_tree_bottom_up_until_eight_logs_of_wood(self):
        s = situation(pet(), forest())
        wood = PURPOSES["gather_wood"]
        self.assertTrue(wood.valid(s))
        self.assertEqual(wood.plan(s, context(s.grid)),
                         [walk(5, 1, 0, 2.0), mine(5, 1, 0), mine(5, 2, 0), mine(5, 3, 0), mine(5, 4, 0)])
        full = situation(pet(inventory={"oak_log": 6, "planks": 8}), forest())
        self.assertFalse(wood.valid(full))
        self.assertEqual(wood.plan(full, context(full.grid)), [])

    def test_a_tree_where_a_step_failed_is_left_alone(self):
        state = pet()
        state["recent_actions"] = [{"kind": "walk", "started_at": 0.0, "ended_at": 0.0, "result": "failed",
                                    "target": {"x": 5, "y": 1, "z": 0}, "reason": "no way there", "code": "no_path"}]
        self.assertFalse(PURPOSES["gather_wood"].valid(situation(state, forest())))


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
class StoneTests(unittest.TestCase):
    def test_digs_a_staircase_down_two_blocks_per_stair(self):
        s = situation(pet(inventory={"wooden_pickaxe": 1}), ground())
        stone = PURPOSES["gather_stone"]
        self.assertTrue(stone.valid(s))
        self.assertEqual(stone.plan(s, context(s.grid)),
                         [mine(1, 0, 0), walk(1, 0, 0), mine(2, 0, 0), mine(2, -1, 0), walk(2, -1, 0),
                          mine(3, -1, 0), mine(3, -2, 0), walk(3, -2, 0), mine(4, -2, 0), mine(4, -3, 0), walk(4, -3, 0)])
        self.assertEqual(s.brain["dig_heading"], [1, 0])
        self.assertFalse(stone.valid(situation(pet(), ground())))

    def test_turns_into_a_level_tunnel_deep_down(self):
        s = situation(pet((4, -3, 0), inventory={"wooden_pickaxe": 1}), ground({(4, -3, 0): "air"}))
        s.brain["dig_heading"] = [1, 0]
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid)),
                         [mine(5, -3, 0), walk(5, -3, 0), mine(6, -3, 0), walk(6, -3, 0),
                          mine(7, -3, 0), walk(7, -3, 0), mine(8, -3, 0), walk(8, -3, 0)])

    def test_stops_at_the_goal(self):
        s = situation(pet((4, -3, 0), inventory={"wooden_pickaxe": 1, "cobblestone": 11}), ground({(4, -3, 0): "air"}))
        s.brain["dig_heading"] = [1, 0]
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid)), [mine(5, -3, 0), walk(5, -3, 0)])
        done = situation(pet(inventory={"wooden_pickaxe": 1, "cobblestone": 12}), ground())
        self.assertFalse(PURPOSES["gather_stone"].valid(done))

    def test_never_digs_into_water(self):
        s = situation(pet(inventory={"wooden_pickaxe": 1}), ground({(1, 0, 0): "water"}))
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid))[0], mine(0, 0, 1))

    def test_with_a_stone_pickaxe_it_digs_on_for_iron_until_it_sees_some(self):
        stocked = {"stone_pickaxe": 1, "cobblestone": 12}
        s = situation(pet(inventory=stocked), ground())
        self.assertTrue(PURPOSES["gather_stone"].valid(s))
        self.assertEqual(len(PURPOSES["gather_stone"].plan(s, context(s.grid))), 11)
        seen = situation(pet(inventory=stocked), ground(), [("ore", (9, -3, 9), "iron_ore")])
        self.assertFalse(PURPOSES["gather_stone"].valid(seen))


class OreTests(unittest.TestCase):
    def test_walks_close_to_a_remembered_ore_and_mines_it(self):
        grid = ground({(3, -3, 0): "iron_ore"})
        seen = [("ore", (3, -3, 0), "iron_ore")]
        ore = PURPOSES["mine_ore"]
        self.assertFalse(ore.valid(situation(pet(inventory={"wooden_pickaxe": 1}), grid, seen)))
        s = situation(pet(inventory={"stone_pickaxe": 1}), grid, seen)
        self.assertTrue(ore.valid(s))
        self.assertEqual(ore.plan(s, context(grid)), [walk(3, -3, 0, 3.0), mine(3, -3, 0)])

    def test_an_ore_that_is_gone_is_forgotten(self):
        s = situation(pet(inventory={"stone_pickaxe": 1}), ground(), [("ore", (3, -3, 0), "iron_ore")])
        self.assertEqual(PURPOSES["mine_ore"].plan(s, context(s.grid)), [])
        self.assertEqual(places(s.db), [])

    def test_only_ores_mimo_still_needs_are_wanted(self):
        grid = ground({(2, 0, 0): "coal_ore"})
        seen = [("ore", (2, 0, 0), "coal_ore")]
        self.assertTrue(PURPOSES["mine_ore"].valid(situation(pet(inventory={"wooden_pickaxe": 1}), grid, seen)))
        stocked = pet(inventory={"wooden_pickaxe": 1, "coal": 8})
        self.assertFalse(PURPOSES["mine_ore"].valid(situation(stocked, grid, seen)))


class SensesTests(unittest.TestCase):
    def test_ores_around_a_mined_block(self):
        grid = ground({(1, -3, 0): "coal_ore", (0, -2, 1): "iron_ore"})
        self.assertEqual(ores_around(grid, (0, -3, 0)), [((0, -2, 1), "iron_ore"), ((1, -3, 0), "coal_ore")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py"`
Expected: `ImportError: cannot import name 'ores_around' from 'backend.survival.senses'`.

- [ ] **Step 3: Add logs, failed columns and ores to the senses**

In `backend/survival/senses.py`, replace:

```python
from backend.services.worldgen import trees_in_chunk
from backend.survival.grid import CHUNK

TREE_SEARCH = 24
```

with:

```python
from backend.services.worldgen import trees_in_chunk
from backend.survival.grid import CHUNK, Cell, Grid

TREE_SEARCH = 24
TRUNK_HEIGHT = 4
LOG = "oak_log"
ORES = ("coal_ore", "iron_ore", "copper_ore")
```

and append:

```python


def failed_columns(state: dict) -> set[tuple[int, int]]:
    """Columns where a recent step failed. Their trees are left alone while the failure is recent."""
    columns = set()
    for entry in state.get("recent_actions", []):
        target = entry.get("target")
        if entry.get("result") == "failed" and isinstance(target, dict) and "x" in target and "z" in target:
            columns.add((target["x"], target["z"]))
    return columns


def standing_logs(grid: Grid, seed: str, here: Cell, skip: set[tuple[int, int]] | frozenset = frozenset(),
                  radius: int = TREE_SEARCH) -> list[Cell]:
    """The logs still standing in the nearest tree worth trying, lowest first; [] when there is none."""
    x, _, z = here
    best: tuple[float, list[Cell]] | None = None
    for tx, tz, base in trees_near(seed, x, z, radius):
        if (tx, tz) in skip:
            continue
        logs = [(tx, y, tz) for y in range(base + 1, base + TRUNK_HEIGHT + 1) if grid.material(tx, y, tz) == LOG]
        distance = math.hypot(tx - x, tz - z)
        if logs and (best is None or distance < best[0]):
            best = (distance, logs)
    return best[1] if best else []


def ores_around(grid: Grid, cell: Cell) -> list[tuple[Cell, str]]:
    """Ore blocks among the 26 cells around `cell`: what mining it uncovered."""
    x, y, z = cell
    found = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if dx == dy == dz == 0:
                    continue
                near = (x + dx, y + dy, z + dz)
                material = grid.material(*near)
                if material in ORES:
                    found.append((near, material))
    return found
```

- [ ] **Step 4: Write the gathering purposes**

Create `backend/survival/work.py`:

```python
"""Gathering purposes: wood from trees, stone from a staircase dug into the ground, and ores
Mimo has seen.

gather_wood chops the nearest standing tree within 24 blocks, lowest log first, until Mimo
carries 8 logs' worth of wood (craft_tools turns logs into planks). gather_stone needs a pickaxe:
it digs a staircase down from where Mimo stands, two blocks per stair, and turns into a level
tunnel 10 blocks under the surface (or at y -3), until Mimo carries 12 cobblestone; with a stone
pickaxe and no iron ore seen yet, it keeps digging to prospect for iron. It never digs into
water, lava, bedrock, a hole or a cave, or a block it cannot mine. The staircase stays
climbable, and from its third stair it is sheltered, so it often becomes Mimo's first home.
mine_ore walks to a remembered coal or iron ore Mimo can harvest and still needs, within 48
blocks, and mines it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.blocks import hardness, is_solid
from backend.services.crafting import BLOCKS, TOOL_RANK, can_harvest
from backend.services.worldgen import terrain_height
from backend.survival.grid import Cell, Grid
from backend.survival.memory import cell_of, forget
from backend.survival.purposes import Purpose, register, walk_to
from backend.survival.senses import failed_columns, standing_logs
from backend.survival.situation import Situation
from backend.survival.steps import REACH

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

WOOD_GOAL = 8.0
STAND_REACH = 2.0  # close enough to the lowest log that the top one (3 higher) stays within reach
STONE_GOAL = 12
STAIRS_PER_BATCH = 4
TUNNEL_DEPTH = 10
LOWEST_FLOOR = -3
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
FLUIDS = ("water", "lava")
ORE_RANGE = 48.0
ORE_REACH = 3.0


def wood(inventory: dict) -> float:
    """Wood carried, counted in logs: a log is 1, a plank a quarter, a stick an eighth."""
    return inventory.get("oak_log", 0) + inventory.get("planks", 0) / 4 + inventory.get("sticks", 0) / 8


def has_pickaxe(inventory: dict) -> bool:
    return any(inventory.get(tool, 0) > 0 for tool in TOOL_RANK)


# gather_wood -----------------------------------------------------------------------------------

def logs_to_chop(s: Situation) -> list[Cell]:
    return standing_logs(s.grid, s.seed, s.here, failed_columns(s.state))


def wood_score(s: Situation) -> float:
    base = 65.0 if wood(s.inventory) < 3 else 40.0
    return base + s.trait("diligence") / 10 + s.trait("thrift") / 20


def wood_facts(s: Situation) -> str:
    logs = logs_to_chop(s)
    tree = f"a tree {round(s.distance(logs[0]))} blocks away" if logs else "no tree near"
    return f"{wood(s.inventory):g} logs of wood carried, {tree}"


def plan_wood(s: Situation, context: ActionContext) -> list[dict]:
    if wood(s.inventory) >= WOOD_GOAL:
        return []
    logs = logs_to_chop(s)
    if not logs:
        return []
    return [walk_to(logs[0], STAND_REACH), *({"kind": "mine", "target": list(log)} for log in logs)]


register(Purpose(
    "gather_wood", "gather wood", "Chop the nearest tree for logs, the start of every tool.",
    valid=lambda s: wood(s.inventory) < WOOD_GOAL and bool(logs_to_chop(s)),
    facts=wood_facts, score=wood_score, plan=plan_wood,
    thoughts=("I need wood. That tree looks good.", "Wood first. Everything starts with wood.")))


# gather_stone ----------------------------------------------------------------------------------

def look(grid: Grid, changed: dict[Cell, str], cell: Cell) -> str:
    return changed.get(cell) or grid.material(*cell)


def stair(grid: Grid, changed: dict[Cell, str], at: Cell, heading: tuple[int, int], inventory: dict,
          seed: str) -> tuple[list[dict], Cell, int] | None:
    """One stair down (or, deep enough, one level tunnel step) from `at` toward `heading`.

    Returns the steps, where Mimo ends up and how many cobblestone the mining yields, or None
    when the way is blocked. `changed` holds the cells earlier stairs of the same plan opened.
    """
    x, y, z = at
    nx, nz = x + heading[0], z + heading[1]
    down = y - 1 >= max(LOWEST_FLOOR, terrain_height(nx, nz, seed) - TUNNEL_DEPTH)
    to = (nx, y - 1, nz) if down else (nx, y, nz)
    if not is_solid(look(grid, changed, (nx, to[1] - 1, nz))):
        return None  # a hole or a cave below: never dig into it
    steps, stones = [], 0
    for cell in ([(nx, y, nz), to] if down else [to]):
        material = look(grid, changed, cell)
        if material in FLUIDS:
            return None
        if not is_solid(material):
            continue
        if hardness(material) is None or not can_harvest(material, inventory):
            return None
        steps.append({"kind": "mine", "target": list(cell)})
        stones += 1 if BLOCKS.get(material, {}).get("drop") == "cobblestone" else 0
        changed[cell] = "air"
    steps.append(walk_to(to))
    return steps, to, stones


def dig_heading(s: Situation) -> tuple[int, int] | None:
    """Where to dig: the last heading if it still works, else toward the highest ground nearby."""
    x, _, z = s.here
    headings = sorted(DIRECTIONS, key=lambda d: -terrain_height(x + 3 * d[0], z + 3 * d[1], s.seed))
    last = s.brain.get("dig_heading")
    if last:
        headings = [tuple(last), *(heading for heading in headings if heading != tuple(last))]
    for heading in headings:
        if stair(s.grid, {}, s.here, heading, s.inventory, s.seed) is not None:
            return heading
    return None


def prospecting(s: Situation) -> bool:
    """Digging on for iron: Mimo has a stone pickaxe, still wants iron and has seen none."""
    return (s.count("stone_pickaxe") > 0 and "iron_ore" in wanted_ores(s)
            and not any(place["kind"] == "ore" and place["note"] == "iron_ore" for place in s.places))


def wants_stone(s: Situation) -> bool:
    return has_pickaxe(s.inventory) and (s.count("cobblestone") < STONE_GOAL or prospecting(s))


def stone_score(s: Situation) -> float:
    if s.count("cobblestone") >= STONE_GOAL:  # prospecting for iron
        return 40.0 + s.trait("curiosity") / 10
    return 50.0 + s.trait("diligence") / 10 + s.trait("thrift") / 20


def stone_facts(s: Situation) -> str:
    if s.count("cobblestone") >= STONE_GOAL:
        return f"{s.count('cobblestone')} cobblestone carried; digging on for iron ore, none seen yet"
    return f"{s.count('cobblestone')} cobblestone carried, a pickaxe in hand"


def plan_stone(s: Situation, context: ActionContext) -> list[dict]:
    cobblestone = s.count("cobblestone")
    if not wants_stone(s):
        return []
    goal = math.inf if prospecting(s) else STONE_GOAL
    heading = dig_heading(s)
    if heading is None:
        return []
    s.brain["dig_heading"] = list(heading)
    changed: dict[Cell, str] = {}
    steps, at = [], s.here
    for _ in range(STAIRS_PER_BATCH):
        result = stair(s.grid, changed, at, heading, s.inventory, s.seed)
        if result is None:
            break
        more, at, stones = result
        steps.extend(more)
        cobblestone += stones
        if cobblestone >= goal:
            break
    return steps


register(Purpose(
    "gather_stone", "gather stone", "Dig a staircase into the ground for cobblestone, and on for iron ore.",
    valid=lambda s: wants_stone(s) and dig_heading(s) is not None,
    facts=stone_facts, score=stone_score, plan=plan_stone,
    thoughts=("Time to dig for stone.", "Stone makes better tools than wood.")))


# mine_ore --------------------------------------------------------------------------------------

def wanted_ores(s: Situation) -> tuple[str, ...]:
    """Coal until Mimo carries 8; iron until it has 3 ore or ingots (or an iron pickaxe)."""
    wanted = []
    if s.count("coal") < 8:
        wanted.append("coal_ore")
    if s.count("iron_ore", "iron_ingot") < 3 and not s.count("iron_pickaxe"):
        wanted.append("iron_ore")
    return tuple(wanted)


def ore_targets(s: Situation) -> list[dict]:
    """Remembered, wanted ores Mimo can harvest within 48 blocks, nearest first."""
    wanted, (x, _, z) = wanted_ores(s), s.here
    found = [place for place in s.places
             if place["kind"] == "ore" and place["note"] in wanted and can_harvest(place["note"], s.inventory)
             and math.hypot(place["x"] - x, place["z"] - z) <= ORE_RANGE]
    return sorted(found, key=lambda place: s.distance(cell_of(place)))


def ore_score(s: Situation) -> float:
    iron = any(place["note"] == "iron_ore" for place in ore_targets(s))
    return 50.0 + s.trait("bravery") / 10 + s.trait("curiosity") / 20 + (15.0 if iron else 0.0)


def ore_facts(s: Situation) -> str:
    targets = ore_targets(s)
    nearest = targets[0]
    return (f"{len(targets)} ores remembered; the nearest is {nearest['note'].replace('_', ' ')} "
            f"{round(s.distance(cell_of(nearest)))} blocks away")


def plan_ore(s: Situation, context: ActionContext) -> list[dict]:
    """Walk within reach of the nearest wanted ore and mine it. Ores that are gone are forgotten."""
    for place in ore_targets(s):
        cell = cell_of(place)
        if s.grid.material(*cell) != place["note"]:
            if s.db is not None:
                forget(s.db, "ore", cell)
            continue
        steps = [] if s.distance(cell) <= REACH else [walk_to(cell, ORE_REACH)]
        return [*steps, {"kind": "mine", "target": list(cell)}]
    return []


register(Purpose(
    "mine_ore", "mine ore", "Go back to coal or iron ore seen while digging and mine it.",
    valid=lambda s: bool(ore_targets(s)), facts=ore_facts, score=ore_score, plan=plan_ore,
    thoughts=("I remember seeing ore down there.", "That ore will make something good.")))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_work.py" -v`
Expected: `Ran 11 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 282 tests` … `OK`.

- [ ] **Step 6: Commit**

```bash
git add backend/survival/senses.py backend/survival/work.py backend/tests/test_survival_work.py
git commit -m "feat: gather wood, dig a staircase for stone and mine remembered ore" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Crafting tools with portable stations

**Files:**
- Create: `backend/survival/toolmaking.py`
- Test: `backend/tests/test_survival_toolmaking.py`

**Interfaces:**
- Consumes: Task 6's `Purpose`, `register`, `Situation`; `crafting.RECIPES`, `crafting.SMELTING`, `crafting.TOOL_RANK`; `blocks.is_replaceable`; `steps.STATION_REACH`, `steps.WORKSTATIONS`; `Grid.placed_near`.
- Produces (`backend.survival.toolmaking`): `LADDER = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe")`; `class Short(Exception)`; `next_tool(inventory) -> str | None`; `make(inventory, item, amount, steps, depth=0) -> None` (raises `Short`); `free_cells(s) -> list[Cell]`; `tool_plan(s) -> list[dict] | None`. Registered: `craft_tools` (one tool per choice).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_toolmaking.py`:

```python
import unittest

from backend.survival.actions import ensure_actions
from backend.survival.grid import Grid
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.toolmaking import next_tool, tool_plan
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def flat(cells=None):
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("stone" if y <= 0 else "air"))


def situation(inventory, grid=None):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    return Situation(state, grid or flat(), DAY, 0.0)


def craft(recipe):
    return {"kind": "craft", "recipe": recipe}


class ToolmakingTests(unittest.TestCase):
    def test_three_logs_make_a_table_and_a_wooden_pickaxe_and_the_table_comes_back(self):
        s = situation({"oak_log": 3})
        self.assertEqual(next_tool(s.inventory), "wooden_pickaxe")
        self.assertTrue(PURPOSES["craft_tools"].valid(s))
        self.assertEqual(PURPOSES["craft_tools"].plan(s, None), [
            craft("planks"), craft("crafting_table"),
            {"kind": "place", "target": [1, 1, 0], "block": "crafting_table"},
            craft("planks"), craft("sticks"), craft("planks"), craft("wooden_pickaxe"),
            {"kind": "mine", "target": [1, 1, 0]}])
        self.assertEqual(s.inventory, {"oak_log": 3})

    def test_a_table_already_placed_nearby_is_used_and_left(self):
        grid = flat()
        grid.put(2, 1, 0, "crafting_table")
        s = situation({"wooden_pickaxe": 1, "cobblestone": 3, "sticks": 2}, grid)
        self.assertEqual(tool_plan(s), [craft("stone_pickaxe")])

    def test_iron_needs_a_furnace_and_three_smelted_ingots(self):
        s = situation({"stone_pickaxe": 1, "cobblestone": 8, "iron_ore": 3, "coal": 3, "sticks": 2,
                       "crafting_table": 1})
        self.assertEqual(tool_plan(s), [
            {"kind": "place", "target": [1, 1, 0], "block": "crafting_table"},
            craft("furnace"), {"kind": "place", "target": [-1, 1, 0], "block": "furnace"},
            {"kind": "smelt", "item": "iron_ore"}, {"kind": "smelt", "item": "iron_ore"},
            {"kind": "smelt", "item": "iron_ore"}, craft("iron_pickaxe"),
            {"kind": "mine", "target": [-1, 1, 0]}, {"kind": "mine", "target": [1, 1, 0]}])

    def test_not_enough_materials_or_nothing_left_to_make_is_not_offered(self):
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"oak_log": 2})))
        self.assertIsNone(next_tool({"iron_pickaxe": 1}))
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"iron_pickaxe": 1, "oak_log": 9})))

    def test_no_room_for_a_table_means_no_plan(self):
        walls = {cell: "stone" for cell in ((1, 1, 0), (-1, 1, 0), (0, 1, 1), (0, 1, -1), (0, 2, 0))}
        self.assertIsNone(tool_plan(situation({"oak_log": 3}, flat(walls))))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_toolmaking.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.toolmaking'`.

- [ ] **Step 3: Write the toolmaking purpose**

Create `backend/survival/toolmaking.py`:

```python
"""craft_tools: make the next pickaxe, with portable stations.

The ladder is wooden pickaxe, stone pickaxe, iron pickaxe. Only the next one Mimo lacks is on
offer, and only when everything it needs can be made from what Mimo carries. The planner works
the whole chain out on a copy of the inventory: logs into planks, planks into sticks, a crafting
table, and for iron a furnace and three smelted ingots (coal as fuel when Mimo has it, planks
otherwise, as crafting.smelt does). Stations are portable: Mimo places a table or furnace in an
open cell beside it (or above it), crafts or smelts, then mines the station back into its
inventory, so it never has to remember where it left one. A station already placed within
reach is used as it is and left there. One tool per choice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.blocks import is_replaceable
from backend.services.crafting import RECIPES, SMELTING, TOOL_RANK
from backend.survival.grid import Cell
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import STATION_REACH, WORKSTATIONS

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

LADDER = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe")
STATIONS = {"wooden_pickaxe": ("crafting_table",), "stone_pickaxe": ("crafting_table",),
            "iron_pickaxe": ("crafting_table", "furnace")}
SMELTED = {output: ore for ore, output in SMELTING.items()}
# Cells beside Mimo at its level, then the one above it.
NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0))
MAX_DEPTH = 12
RETRIES = 8


class Short(Exception):
    """Something the chain needs cannot be made from what Mimo carries."""


def next_tool(inventory: dict) -> str | None:
    """The next pickaxe up the ladder, or None when Mimo has the best one."""
    rank = max((TOOL_RANK[tool] for tool in TOOL_RANK if inventory.get(tool, 0) > 0), default=0)
    return LADDER[rank] if rank < len(LADDER) else None


def make(inventory: dict, item: str, amount: int, steps: list[dict], depth: int = 0) -> None:
    """Add craft and smelt steps until `inventory` holds `amount` of `item`, changing `inventory`
    the way the steps will. Raises Short when something is missing."""
    if depth > MAX_DEPTH:
        raise Short(item)
    while inventory.get(item, 0) < amount:
        recipe = RECIPES.get(item)
        if recipe is not None:
            # An ingredient made later can use up one made earlier (sticks are made from planks).
            for _ in range(RETRIES):
                short = [(name, count) for name, count in recipe["ingredients"].items()
                         if inventory.get(name, 0) < count]
                if not short:
                    break
                for name, count in short:
                    make(inventory, name, count, steps, depth + 1)
            else:
                raise Short(item)
            for name, count in recipe["ingredients"].items():
                inventory[name] -= count
            for name, count in recipe["output"].items():
                inventory[name] = inventory.get(name, 0) + count
            steps.append({"kind": "craft", "recipe": item})
        elif item in SMELTED:
            ore = SMELTED[item]
            if inventory.get(ore, 0) < 1:
                raise Short(ore)
            fuel = "coal" if inventory.get("coal", 0) else "planks"
            make(inventory, fuel, 1, steps, depth + 1)
            inventory[ore] -= 1
            inventory[fuel] -= 1
            inventory[item] = inventory.get(item, 0) + 1
            steps.append({"kind": "smelt", "item": ore})
        else:
            raise Short(item)


def free_cells(s: Situation) -> list[Cell]:
    """Open cells beside Mimo (or above it) where a station can stand."""
    x, y, z = s.here
    cells = []
    for dx, dy, dz in NEIGHBOURS:
        cell = (x + dx, y + dy, z + dz)
        material = s.grid.material(*cell)
        if material != "water" and is_replaceable(material):
            cells.append(cell)
    return cells


def tool_plan(s: Situation) -> list[dict] | None:
    """The steps that make the next pickaxe, or None when it cannot be made now."""
    tool = next_tool(s.inventory)
    if tool is None:
        return None
    inventory = dict(s.inventory)
    x, _, z = s.here
    near = s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS)
    free = free_cells(s)
    steps: list[dict] = []
    placed: list[Cell] = []
    try:
        for station in STATIONS[tool]:
            if station in near:
                continue
            make(inventory, station, 1, steps)
            if not free:
                raise Short(station)
            cell = free.pop(0)
            steps.append({"kind": "place", "target": list(cell), "block": station})
            inventory[station] -= 1
            placed.append(cell)
        make(inventory, tool, 1, steps)
    except Short:
        return None
    steps.extend({"kind": "mine", "target": list(cell)} for cell in reversed(placed))
    return steps


def plan_tools(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return tool_plan(s) or []


register(Purpose(
    "craft_tools", "craft tools", "Make the next pickaxe from carried materials with a portable crafting table.",
    valid=lambda s: tool_plan(s) is not None,
    facts=lambda s: f"can make a {next_tool(s.inventory).replace('_', ' ')} now",
    score=lambda s: 70.0 + s.trait("diligence") / 10,
    plan=plan_tools,
    thoughts=("I can make a better pickaxe now.", "Time to make a proper tool.")))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_toolmaking.py" -v`
Expected: `Ran 5 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 287 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/survival/toolmaking.py backend/tests/test_survival_toolmaking.py
git commit -m "feat: craft the next pickaxe with a portable crafting table and furnace" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The brain in the tick

**Files:**
- Create: `backend/survival/brain.py`
- Test: `backend/tests/test_survival_brain.py`

**Interfaces:**
- Consumes: `ActionContext` (Tasks 1–4), `tick.Mind` (Tasks 1, 4), `memory` and `triggers` (Task 5), `purposes`, `situation`, `senses` (Tasks 6–7), and the modules `work` and `toolmaking` (imported for their registrations).
- Produces (`backend.survival.brain`):
  - `PENDING_WAIT = 1.0`, `PENALTY_GAME_SECONDS = 600.0`.
  - `brain_plan(state, context, at) -> list[dict]` (the planner), `observe_step(state, step, context, at) -> None`, `notice_step(state, context, before, surroundings, since, at) -> None`.
  - Helpers later tasks call: `waiting(state, at) -> list[dict]`, `finish_purpose(state, at, reason) -> None`, `report(state, context, purpose_name, at, why) -> None`, `forget_unreachable_home(context, purpose_name, failure) -> None`, `new_failure(state, brain) -> dict | None`, `discover(state, context, at, what, kind, text) -> None`.
  - `BRAIN = Mind(plan=brain_plan, observe=observe_step, notice=notice_step)` (Task 11 adds `interrupt`).
  - Steps a purpose plans carry `"purpose": <name>`. Events: `plan` (gave up), `found` (first sighting of an ore material), `discovered` (home, water). Triggers: `plan_done`, `plan_failed`, `idle`, vital crossings (urgent), `dawn`, `dusk`, `hour`, `discovery`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_brain.py`:

```python
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.brain import BRAIN, brain_plan, notice_step, observe_step
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.memory import create_memory_tables, known_recipes, places, remember
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES, Purpose, register
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.triggers import ensure_brain
from backend.survival.vitals import START_VITALS, Surroundings
from backend.survival.world import SurvivalWorld, read_state, write_state

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
DUSK = {**DAY, "phase": "dusk", "seconds_into_day": 2230.0}
BORN = 1_000_000.0
WAIT = [{"kind": "wait", "seconds": 1.0}]


def flat(cells=None):
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("stone" if y <= 0 else "air"))


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def brainy(grid=None, clock=None):
    """A tick's context over `grid` with an in-memory world memory."""
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return ActionContext(grid=grid or flat(), clock_at=clock or (lambda at: DAY), planner=brain_plan, events=[], db=db)


def choose(state, purpose, at=0.0):
    ensure_brain(state).update(purpose=purpose, pending=None, chosen_at=at, batches=0, replans=0, planned_at=None)


def failure(at):
    return {"code": "no_path", "reason": "no way there", "kind": "walk", "cell": {"x": 9, "y": 1, "z": 0},
            "purpose": "explore", "at": at}


class BrainPlanTests(unittest.TestCase):
    def test_without_a_purpose_mimo_waits_for_a_choice(self):
        state = pet()
        self.assertEqual(brain_plan(state, brainy(), 0.0), WAIT)
        self.assertEqual(state["brain"]["pending"]["reasons"], ["born"])
        state["brain"]["pending"] = None
        brain_plan(state, brainy(), 5.0)
        self.assertEqual(state["brain"]["pending"]["reasons"], ["idle"])

    def test_a_purpose_plans_tagged_batches_until_it_is_done(self):
        state = pet()
        choose(state, "rest")
        ctx = brainy()
        self.assertEqual(brain_plan(state, ctx, 0.0), [{"kind": "wait", "seconds": 60.0, "purpose": "rest"}])
        self.assertEqual(brain_plan(state, ctx, 60.0), WAIT)
        brain = state["brain"]
        self.assertEqual((brain["purpose"], brain["batches"], brain["pending"]["reasons"]), (None, 0, ["plan_done"]))

    def test_a_failed_batch_is_planned_again_once_then_reported(self):
        state = pet()
        choose(state, "explore")
        ctx = brainy()
        first = brain_plan(state, ctx, 0.0)
        self.assertEqual(first[0]["purpose"], "explore")
        state["last_failure"] = failure(1.0)
        again = brain_plan(state, ctx, 1.0)
        self.assertEqual((again[0]["kind"], state["brain"]["replans"]), ("walk", 1))
        self.assertNotEqual(again[0]["target"], first[0]["target"])
        state["last_failure"] = failure(2.0)
        self.assertEqual(brain_plan(state, ctx, 2.0), WAIT)
        brain = state["brain"]
        self.assertEqual((brain["purpose"], brain["penalties"], brain["pending"]["reasons"]),
                         (None, {"explore": 602.0}, ["plan_failed"]))
        self.assertEqual(ctx.events[-1][1:], ("plan", "Pip gave up trying to explore (no way there)."))

    def test_a_home_that_cannot_be_reached_is_forgotten(self):
        state = pet()
        choose(state, "go_home")
        ctx = brainy()
        remember(ctx.db, "home", (20, 1, 0), 0.0)
        self.assertEqual(brain_plan(state, ctx, 0.0)[0]["target"], [20, 1, 0])
        for seq, at in ((1, 1.0), (2, 1.0)):
            state["last_failure"] = {"code": "no_path", "reason": "no way there", "kind": "walk",
                                     "cell": {"x": 20, "y": 1, "z": 0}, "purpose": "go_home", "at": at, "seq": seq}
            brain_plan(state, ctx, at)
        self.assertEqual(places(ctx.db), [])
        self.assertIn("go_home", state["brain"]["penalties"])

    def test_a_purpose_that_is_no_longer_valid_is_finished(self):
        state = pet()
        choose(state, "sleep")
        self.assertEqual(brain_plan(state, brainy(), 0.0), WAIT)
        self.assertEqual((state["brain"]["purpose"], state["brain"]["pending"]["reasons"]), (None, ["plan_done"]))

    def test_a_crashing_planner_is_logged_once_and_reported(self):
        def boom(s, context):
            raise RuntimeError("boom")

        register(Purpose("test_crash", "crash", "Crashes.", lambda s: True, lambda s: "", lambda s: 1.0, boom,
                         ("Oops.",)))
        forget_logged()
        try:
            state = pet()
            choose(state, "test_crash")
            with self.assertLogs("backend.survival.brain", level="ERROR"):
                self.assertEqual(brain_plan(state, brainy(), 0.0), WAIT)
            self.assertIn("test_crash", state["brain"]["penalties"])
            self.assertEqual(state["brain"]["pending"]["reasons"], ["plan_failed"])
        finally:
            PURPOSES.pop("test_crash", None)


class NoticeAndObserveTests(unittest.TestCase):
    def test_notice_marks_crossings_phases_and_the_game_hour(self):
        state = pet(vitals={**START_VITALS, "hunger": 29.0})
        ensure_brain(state)["pending"] = None
        ctx = brainy(clock=lambda at: DAY if at < 10 else DUSK)
        notice_step(state, ctx, {**START_VITALS, "hunger": 31.0}, Surroundings(), 5.0, 15.0)
        self.assertEqual(state["brain"]["pending"],
                         {"id": 2, "reasons": ["hunger_30", "dusk"], "since": 15.0, "urgent": True})
        state["brain"].update(pending=None, chosen_at=0.0)
        notice_step(state, brainy(), dict(state["vitals"]), Surroundings(), 3599.0, 3600.0)
        self.assertEqual(state["brain"]["pending"]["reasons"], ["hour"])

    def test_the_first_sheltered_spot_becomes_home(self):
        state = pet()
        ensure_brain(state)["pending"] = None
        ctx = brainy()
        notice_step(state, ctx, dict(state["vitals"]), Surroundings(sheltered=True), 0.0, 1.0)
        self.assertEqual([(place["kind"], place["x"]) for place in places(ctx.db)], [("home", 0)])
        self.assertEqual(ctx.events[-1][1:], ("discovered", "Pip found a sheltered spot and made it home."))
        self.assertEqual(state["brain"]["pending"]["reasons"], ["discovery"])
        state["position"]["x"] = 20.0
        notice_step(state, ctx, dict(state["vitals"]), Surroundings(sheltered=True), 1.0, 2.0)
        self.assertEqual([(place["kind"], place["x"]) for place in places(ctx.db)], [("home", 0), ("shelter", 20)])
        self.assertEqual(len(ctx.events), 1)

    def test_observe_remembers_ores_recipes_and_water_and_forgets_mined_ore(self):
        state = pet()
        ensure_brain(state)["pending"] = None
        ctx = brainy(flat({(2, 1, 0): "coal_ore", (0, 0, 5): "coal_ore"}))
        observe_step(state, {"kind": "mine", "target": {"x": 1, "y": 1, "z": 0}, "block": "dirt"}, ctx, 1.0)
        self.assertEqual([(place["kind"], place["x"], place["note"]) for place in places(ctx.db)],
                         [("ore", 2, "coal_ore")])
        self.assertEqual(ctx.events[-1][1:], ("found", "Pip spotted coal ore."))
        observe_step(state, {"kind": "mine", "target": {"x": 0, "y": 1, "z": 5}, "block": "dirt"}, ctx, 2.0)
        self.assertEqual(len(ctx.events), 1)
        observe_step(state, {"kind": "mine", "target": {"x": 2, "y": 1, "z": 0}, "block": "coal_ore"}, ctx, 3.0)
        self.assertEqual([place["z"] for place in places(ctx.db)], [5])
        observe_step(state, {"kind": "craft", "recipe": "planks"}, ctx, 4.0)
        observe_step(state, {"kind": "smelt", "item": "iron_ore"}, ctx, 5.0)
        self.assertEqual(known_recipes(ctx.db), ["planks", "smelt_iron_ore"])
        path = [{"x": 0, "y": 1, "z": 0, "at": 5.0}, {"x": 1, "y": 1, "z": 0, "at": 5.9, "swim": True}]
        observe_step(state, {"kind": "walk", "path": path}, ctx, 6.0)
        self.assertEqual(ctx.events[-1][1:], ("discovered", "Pip found water."))
        self.assertEqual(state["brain"]["found"], ["coal_ore", "water"])


class BrainTickTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            change(state)
            write_state(db, state)

    def test_the_tick_waits_for_a_choice_then_runs_the_chosen_purpose(self):
        state = tick_life(self.registry, BORN + 1, scale=1, mind=BRAIN)
        self.assertEqual((state["action"]["kind"], state["brain"]["pending"]["reasons"]), ("wait", ["born"]))

        def choose_rest(state):
            state["brain"].update(purpose="rest", pending=None, chosen_at=BORN + 1, picker="utility")
            state["action"] = None

        self.edit(choose_rest)
        state = tick_life(self.registry, BORN + 2, scale=1, mind=BRAIN)
        self.assertEqual((state["action"]["kind"], state["action"]["purpose"]), ("wait", "rest"))

    def test_a_vital_crossing_in_the_tick_asks_urgently(self):
        self.edit(lambda state: state["vitals"].update(hunger=30.5))
        state = tick_life(self.registry, BORN + 60, scale=1, mind=BRAIN)
        self.assertTrue(state["brain"]["pending"]["urgent"])
        self.assertIn("hunger_30", state["brain"]["pending"]["reasons"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_brain.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.brain'`.

- [ ] **Step 3: Write the brain**

Create `backend/survival/brain.py`:

```python
"""The brain inside the tick: purposes into steps, failures and reports, triggers and discoveries.

The tick never calls a model (it holds the world's write transaction). It asks `brain_plan` for
steps whenever Mimo's queue runs dry:

1. A batch that failed (a `state["last_failure"]` the brain has not dealt with yet) is planned
   again once. A second failure reports back: the purpose is dropped, scores 30 lower for 600
   game seconds, and a `plan_failed` trigger asks for a new choice.
2. Otherwise the last batch finished well and counts toward the purpose's `batches`.
3. The chosen purpose plans its next batch, each step tagged with the purpose's name. A purpose
   that is no longer valid, or has nothing left to do, is finished: `plan_done` asks for a new
   choice. A planner that crashes (or returns something other than a list of steps) is logged
   once and reported like a failure.
4. With no purpose (a choice is pending), Mimo waits a second at a time.

`observe_step` hears about finished steps: ores around a mined block, recipes learned, water swum
in, places visited. `notice_step` runs after each vitals step: vital crossings (urgent), dawn and
dusk, a game hour since the last choice, and shelter (the first sheltered spot becomes home).
First sightings (home, each ore material, water) are discoveries and ask for a new choice.
"""

from __future__ import annotations

import logging

from backend.survival import toolmaking, work  # noqa: F401  (they register their purposes)
from backend.survival.actions import ActionContext
from backend.survival.memory import SHELTER_KINDS, forget, learn, remember, visit
from backend.survival.once import log_once
from backend.survival.purposes import PURPOSES, Purpose, is_valid
from backend.survival.senses import ORES, ores_around
from backend.survival.situation import Situation, in_tick
from backend.survival.steps import as_cell, label
from backend.survival.tick import Mind
from backend.survival.triggers import crossings, ensure_brain, hour_passed, mark_trigger, phase_trigger
from backend.survival.vitals import Surroundings

logger = logging.getLogger(__name__)

PENDING_WAIT = 1.0
PENALTY_GAME_SECONDS = 600.0


def waiting(state: dict, at: float) -> list[dict]:
    """Wait a second for a choice, asking for one if nothing is pending."""
    if ensure_brain(state)["pending"] is None:
        mark_trigger(state, "idle", at)
    return [{"kind": "wait", "seconds": PENDING_WAIT}]


def finish_purpose(state: dict, at: float, reason: str) -> None:
    """Drop the current purpose and ask for a new choice."""
    ensure_brain(state).update(purpose=None, batches=0, replans=0, planned_at=None)
    mark_trigger(state, reason, at)


def report(state: dict, context: ActionContext, purpose_name: str, at: float, why: str) -> None:
    """Give up on a purpose: it scores lower for 10 game minutes and a new choice is asked for."""
    brain = ensure_brain(state)
    brain["penalties"][purpose_name] = at + PENALTY_GAME_SECONDS / context.clock_at(at)["time_scale"]
    purpose = PURPOSES.get(purpose_name)
    phrase = purpose.phrase if purpose else purpose_name.replace("_", " ")
    context.events.append((at, "plan", f"{state['name']} gave up trying to {phrase} ({why})."))
    finish_purpose(state, at, "plan_failed")


def forget_unreachable_home(context: ActionContext, purpose_name: str, failure: dict) -> None:
    """A shelter go_home failed twice to find a way to is forgotten, so the next sheltered spot
    Mimo finds can become home."""
    cell = failure.get("cell")
    if purpose_name != "go_home" or failure.get("code") != "no_path" or context.db is None or not isinstance(cell, dict):
        return
    for kind in SHELTER_KINDS:
        forget(context.db, kind, (cell["x"], cell["y"], cell["z"]))


def new_failure(state: dict, brain: dict) -> dict | None:
    """The last failure, unless the brain already dealt with it."""
    failure = state.get("last_failure")
    return failure if failure is not None and failure != brain["handled_failure"] else None


def plan_batch(purpose: Purpose, s: Situation, context: ActionContext) -> list[dict] | None:
    """The purpose's next batch: [] when it is finished, None when its planner broke."""
    if not is_valid(purpose, s):
        return []
    try:
        steps = purpose.plan(s, context)
        if not (isinstance(steps, list) and all(isinstance(step, dict) for step in steps)):
            raise TypeError(f"{purpose.name} planned {type(steps).__name__}, not a list of steps")
    except Exception as error:
        log_once(logger, f"{purpose.name} planner", error)
        return None
    return steps


def brain_plan(state: dict, context: ActionContext, at: float) -> list[dict]:
    """The next steps for Mimo's purpose. See the module docstring for the rules."""
    brain = ensure_brain(state)
    purpose = PURPOSES.get(brain["purpose"]) if brain["purpose"] else None
    if purpose is None:
        return waiting(state, at)
    failure = new_failure(state, brain)
    if failure is not None:
        brain["handled_failure"] = failure
        if brain["replans"] >= 1:
            forget_unreachable_home(context, purpose.name, failure)
            report(state, context, purpose.name, at, failure["reason"])
            return waiting(state, at)
        brain["replans"] += 1
    elif brain["planned_at"] is not None:
        brain["batches"] += 1
        brain["replans"] = 0
    steps = plan_batch(purpose, in_tick(state, context, at), context)
    if steps is None:
        report(state, context, purpose.name, at, "its plan broke")
        return waiting(state, at)
    if not steps:
        finish_purpose(state, at, "plan_done")
        return waiting(state, at)
    brain["planned_at"] = at
    return [{**step, "purpose": purpose.name} for step in steps]


def discover(state: dict, context: ActionContext, at: float, what: str, kind: str, text: str) -> None:
    """Log and announce the first discovery of `what`; later ones stay quiet."""
    brain = ensure_brain(state)
    if what in brain["found"]:
        return
    brain["found"].append(what)
    context.events.append((at, kind, text))
    mark_trigger(state, "discovery", at)


def observe_step(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """Remember what a finished step showed: ores, recipes, water and visited places."""
    db = context.db
    if db is None:
        return
    kind, name = step["kind"], state["name"]
    if kind == "mine":
        cell = as_cell(step["target"])
        if step.get("block") in ORES:
            forget(db, "ore", cell)
        for near, material in ores_around(context.grid, cell):
            if remember(db, "ore", near, at, material):
                discover(state, context, at, material, "found", f"{name} spotted {label(material)}.")
    elif kind == "craft":
        learn(db, step["recipe"], at)
    elif kind == "smelt":
        learn(db, f"smelt_{step['item']}", at)
    elif kind in ("walk", "swim"):
        water = next((entry for entry in step["path"] if entry.get("swim")), None)
        if water is not None and remember(db, "water", as_cell(water), at):
            discover(state, context, at, "water", "discovered", f"{name} found water.")
        visit(db, as_cell(state["position"]), at)


def notice_step(state: dict, context: ActionContext, before: dict, surroundings: Surroundings,
                since: float, at: float) -> None:
    """After a vitals step: ask for a choice on crossings, dawn, dusk or a quiet game hour, and
    remember sheltered spots."""
    brain = ensure_brain(state)
    for reason in crossings(before, state["vitals"]):
        mark_trigger(state, reason, at, urgent=True)
    clock = context.clock_at(at)
    phase = phase_trigger(context.clock_at(since)["phase"], clock["phase"])
    if phase:
        mark_trigger(state, phase, at)
    asleep = (state.get("action") or {}).get("kind") == "sleep"
    if brain["pending"] is None and not asleep and hour_passed(brain, at, clock["time_scale"]):
        mark_trigger(state, "hour", at)
    if surroundings.sheltered and context.db is not None:
        cell = as_cell(state["position"])
        if remember(context.db, "home", cell, at):
            discover(state, context, at, "home", "discovered", f"{state['name']} found a sheltered spot and made it home.")
        else:
            remember(context.db, "shelter", cell, at)


BRAIN = Mind(plan=brain_plan, observe=observe_step, notice=notice_step)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_brain.py" -v`
Expected: `Ran 11 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 298 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/survival/brain.py backend/tests/test_survival_brain.py
git commit -m "feat: turn the chosen purpose into steps, re-plan once, report failures and notice triggers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Trapped: a staircase out

**Files:**
- Create: `backend/survival/escape.py`
- Modify: `backend/survival/brain.py`
- Test: `backend/tests/test_survival_escape.py`

**Interfaces:**
- Consumes: `take_search` (Task 1), recorded failure `code`s (Task 2), `pathing.moves`, `purposes.walk_to`, `triggers.ensure_brain`, Task 9's `brain_plan`.
- Produces (`backend.survival.escape`): `TRAPPED_LIMIT = 256`, `MAX_STAIRS = 24`, `ESCAPE_RETRY = 60.0`, `PLACEABLE`; `walks_failed_twice(state) -> bool`; `reachable_count(grid, start, limit) -> int`; `staircase(grid, here, heading, inventory, seed) -> list[dict] | None`; `escape_plan(grid, here, inventory, seed) -> list[dict]`; `plan_escape(state, context, at) -> list[dict] | None` (steps tagged `"purpose": "escape"`; `[]` = not trapped or no way out; `None` = no search left this tick). `brain_plan` tries it on a second failure before reporting. Event `trapped`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_escape.py`:

```python
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.brain import brain_plan
from backend.survival.escape import escape_plan, reachable_count
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.triggers import ensure_brain
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def pit(wall="dirt", width=1):
    """Stone at y <= 0, `wall` from y 1 to 4 around an open pit (x 0 to width-1 at z 0), air from y 5."""
    def rule(x, y, z):
        if y <= 0:
            return "stone"
        if y >= 5:
            return "air"
        return "air" if z == 0 and 0 <= x < width else wall

    return Grid(rule)


def flat():
    return Grid(lambda x, y, z: "stone" if y <= 0 else "air")


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def brainy(grid):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=brain_plan, events=[], db=db)


def mine(x, y, z):
    return {"kind": "mine", "target": [x, y, z]}


def walk(x, y, z):
    return {"kind": "walk", "target": [x, y, z], "reach": 0.0}


def place(x, y, z, block="dirt"):
    return {"kind": "place", "target": [x, y, z], "block": block}


def stuck(**changes):
    """A pet exploring whose last two walks found no path, with the second failure not yet handled."""
    state = pet(**changes)
    state["recent_actions"] = [
        {"kind": "walk", "started_at": at, "ended_at": at, "result": "failed", "reason": "no way there",
         "code": "no_path", "target": {"x": 40, "y": 5, "z": 0}} for at in (1.0, 2.0)]
    state["last_failure"] = {"code": "no_path", "reason": "no way there", "kind": "walk",
                             "cell": {"x": 40, "y": 5, "z": 0}, "purpose": "explore", "at": 2.0}
    ensure_brain(state).update(purpose="explore", pending=None, chosen_at=0.0, replans=1, planned_at=1.0)
    return state


@patch("backend.survival.escape.terrain_height", lambda x, z, seed: 4)
class EscapeTests(unittest.TestCase):
    def test_a_pit_is_a_small_world(self):
        self.assertEqual(reachable_count(pit(), (0, 1, 0), 256), 1)
        self.assertEqual(reachable_count(pit(width=5), (0, 1, 0), 256), 5)
        self.assertEqual(reachable_count(flat(), (0, 1, 0), 256), 256)

    def test_digs_a_staircase_out_of_a_dirt_pit(self):
        self.assertEqual(escape_plan(pit(), (0, 1, 0), {}, "1"),
                         [mine(1, 2, 0), walk(1, 2, 0), mine(1, 3, 0), mine(2, 3, 0), walk(2, 3, 0),
                          mine(2, 4, 0), mine(3, 4, 0), walk(3, 4, 0), walk(4, 5, 0)])

    def test_stone_walls_need_a_pickaxe(self):
        self.assertEqual(escape_plan(pit("stone"), (0, 1, 0), {}, "1"), [])
        self.assertEqual(escape_plan(pit("stone"), (0, 1, 0), {"wooden_pickaxe": 1}, "1")[0], mine(1, 2, 0))

    def test_builds_stairs_from_carried_blocks_in_a_wide_pit(self):
        self.assertEqual(escape_plan(pit("stone", width=5), (0, 1, 0), {"dirt": 4}, "1"),
                         [place(1, 1, 0), walk(1, 2, 0), place(2, 2, 0), walk(2, 3, 0),
                          place(3, 3, 0), walk(3, 4, 0), place(4, 4, 0), walk(4, 5, 0)])
        self.assertEqual(escape_plan(pit("stone", width=5), (0, 1, 0), {"dirt": 3}, "1"), [])

    def test_the_brain_digs_out_after_two_failed_walks(self):
        state = stuck()
        ctx = brainy(pit())
        steps = brain_plan(state, ctx, 2.0)
        self.assertEqual(steps[0], {"kind": "mine", "target": [1, 2, 0], "purpose": "escape"})
        self.assertEqual(steps[-1], {"kind": "walk", "target": [4, 5, 0], "reach": 0.0, "purpose": "escape"})
        brain = state["brain"]
        self.assertEqual((brain["purpose"], brain["escaped_at"], brain["replans"], ctx.searches_left),
                         ("explore", 2.0, 0, 1))
        self.assertEqual(ctx.events[-1][1:], ("trapped", "Pip is stuck in a pit and starts digging out."))

    def test_with_no_search_left_the_check_waits_for_the_next_tick(self):
        state = stuck()
        ctx = brainy(pit())
        ctx.searches_left = 0
        self.assertEqual(brain_plan(state, ctx, 2.0), [{"kind": "wait", "seconds": 1.0}])
        self.assertIsNone(state["brain"]["handled_failure"])
        self.assertEqual(state["brain"]["purpose"], "explore")

    def test_a_pet_that_is_not_trapped_reports_the_failure(self):
        state = stuck()
        brain_plan(state, brainy(flat()), 2.0)
        self.assertIsNone(state["brain"]["purpose"])
        self.assertIn("explore", state["brain"]["penalties"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_escape.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.escape'`.

- [ ] **Step 3: Write the escape**

Create `backend/survival/escape.py`:

```python
"""Trapped: a staircase out of a pit Mimo cannot walk out of.

Routes can drop 3 blocks but climb only 1, so Mimo can walk into a pit it cannot leave. When the
last two walks it tried both failed with no path, the brain floods Mimo's moves from where it
stands (one search from the tick's budget): if fewer than 256 cells are reachable, Mimo is
trapped. The way out is a staircase up, one block up per step: mine the block over Mimo's head
and the stair cell when they are solid, and place a carried block where a stair has nothing to
stand on (mined dirt and stone go into the stock too). It tries the four directions and takes the
first staircase that brings Mimo above the natural surface within 24 stairs, at most once per 60
real seconds. There is no jump step, so a narrow shaft in rock Mimo cannot mine, with no blocks
to place, stays a trap.
"""

from __future__ import annotations

from backend.services.blocks import hardness, is_replaceable, is_solid
from backend.services.crafting import BLOCKS, can_harvest
from backend.services.worldgen import terrain_height
from backend.survival.actions import ActionContext, take_search
from backend.survival.grid import Cell, Grid
from backend.survival.pathing import moves
from backend.survival.purposes import walk_to
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain

TRAPPED_LIMIT = 256
MAX_STAIRS = 24
ESCAPE_RETRY = 60.0
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
FLUIDS = ("water", "lava")
# Blocks Mimo will place to stand on, cheapest first.
PLACEABLE = ("dirt", "cobblestone", "sand", "gravel", "clay", "planks", "oak_log")


def walks_failed_twice(state: dict) -> bool:
    """The last two walks Mimo tried both failed with no path."""
    walks = [entry for entry in state["recent_actions"] if entry.get("kind") == "walk"][-2:]
    return len(walks) == 2 and all(entry.get("result") == "failed" and entry.get("code") == "no_path"
                                   for entry in walks)


def reachable_count(grid: Grid, start: Cell, limit: int) -> int:
    """How many cells Mimo can walk to from `start` (itself included), counting up to `limit`."""
    seen, frontier = {start}, [start]
    while frontier and len(seen) < limit:
        for step in moves(grid, frontier.pop()):
            if step not in seen:
                seen.add(step)
                frontier.append(step)
    return min(len(seen), limit)


def look(grid: Grid, changed: dict[Cell, str], cell: Cell) -> str:
    return changed.get(cell) or grid.material(*cell)


def open_up(grid: Grid, changed: dict[Cell, str], cell: Cell, stock: dict, steps: list[dict]) -> bool:
    """Make `cell` open, mining it if it is solid. False for fluids and blocks Mimo cannot mine."""
    material = look(grid, changed, cell)
    if material in FLUIDS:
        return False
    if not is_solid(material):
        return True
    if hardness(material) is None or not can_harvest(material, stock):
        return False
    steps.append({"kind": "mine", "target": list(cell)})
    changed[cell] = "air"
    drop = BLOCKS.get(material, {}).get("drop")
    if drop:
        stock[drop] = stock.get(drop, 0) + 1
    return True


def staircase(grid: Grid, here: Cell, heading: tuple[int, int], inventory: dict, seed: str) -> list[dict] | None:
    """Stairs up from `here` toward `heading` until Mimo stands above the natural surface, or None."""
    changed: dict[Cell, str] = {}
    stock, steps = dict(inventory), []
    x, y, z = here
    dx, dz = heading
    for i in range(1, MAX_STAIRS + 1):
        below = (x + (i - 1) * dx, y + i - 1, z + (i - 1) * dz)
        stair = (x + i * dx, y + i, z + i * dz)
        headroom = (below[0], below[1] + 1, below[2])
        if not (open_up(grid, changed, headroom, stock, steps) and open_up(grid, changed, stair, stock, steps)):
            return None
        support = (stair[0], stair[1] - 1, stair[2])
        if not is_solid(look(grid, changed, support)):
            block = next((item for item in PLACEABLE if stock.get(item, 0) > 0), None)
            if block is None or not is_replaceable(look(grid, changed, support)):
                return None
            steps.append({"kind": "place", "target": list(support), "block": block})
            stock[block] -= 1
            changed[support] = block
        steps.append(walk_to(stair))
        if stair[1] > terrain_height(stair[0], stair[2], seed):
            return steps
    return None


def escape_plan(grid: Grid, here: Cell, inventory: dict, seed: str) -> list[dict]:
    """The first staircase out, trying the four directions in turn; [] when none works."""
    for heading in DIRECTIONS:
        steps = staircase(grid, here, heading, inventory, seed)
        if steps:
            return steps
    return []


def plan_escape(state: dict, context: ActionContext, at: float) -> list[dict] | None:
    """A staircase out when Mimo is trapped, its steps tagged "escape".

    [] when Mimo is not trapped, tried to escape less than a minute ago, or has no way out.
    None when the flood fill needs a path search and none is left this tick.
    """
    brain = ensure_brain(state)
    if not walks_failed_twice(state):
        return []
    if brain["escaped_at"] is not None and at - brain["escaped_at"] < ESCAPE_RETRY:
        return []
    if not take_search(context):
        return None
    here = as_cell(state["position"])
    if reachable_count(context.grid, here, TRAPPED_LIMIT) >= TRAPPED_LIMIT:
        return []
    steps = escape_plan(context.grid, here, state["inventory"], state["world_seed"])
    if not steps:
        return []
    brain.update(escaped_at=at, replans=0, planned_at=at)
    context.events.append((at, "trapped", f"{state['name']} is stuck in a pit and starts digging out."))
    return [{**step, "purpose": "escape"} for step in steps]
```

- [ ] **Step 4: Try the escape before reporting a second failure**

In `backend/survival/brain.py`, add to the module docstring's list item 1, right after "a `plan_failed` trigger asks for a new choice.":

```python
   Before reporting, the brain checks whether Mimo is trapped and digs a staircase out
   (backend.survival.escape).
```

Replace:

```python
from backend.survival.actions import ActionContext
from backend.survival.memory import SHELTER_KINDS, forget, learn, remember, visit
```

with:

```python
from backend.survival.actions import ActionContext
from backend.survival.escape import plan_escape
from backend.survival.memory import SHELTER_KINDS, forget, learn, remember, visit
```

In `brain_plan`, replace:

```python
    failure = new_failure(state, brain)
    if failure is not None:
        brain["handled_failure"] = failure
        if brain["replans"] >= 1:
            forget_unreachable_home(context, purpose.name, failure)
            report(state, context, purpose.name, at, failure["reason"])
            return waiting(state, at)
        brain["replans"] += 1
```

with:

```python
    failure = new_failure(state, brain)
    if failure is not None:
        if brain["replans"] >= 1:
            escape = plan_escape(state, context, at)
            if escape is None:
                return [{"kind": "wait", "seconds": PENDING_WAIT}]  # no search left this tick; look again next tick
            brain["handled_failure"] = failure
            if escape:
                return escape
            forget_unreachable_home(context, purpose.name, failure)
            report(state, context, purpose.name, at, failure["reason"])
            return waiting(state, at)
        brain["handled_failure"] = failure
        brain["replans"] += 1
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_escape.py" -v`
Expected: `Ran 7 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 305 tests` … `OK`.

- [ ] **Step 6: Commit**

```bash
git add backend/survival/escape.py backend/survival/brain.py backend/tests/test_survival_escape.py
git commit -m "feat: dig or build a staircase out when Mimo is trapped in a pit" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Reflexes

**Files:**
- Create: `backend/survival/reflexes.py`
- Modify: `backend/survival/grid.py` (`placed_cells`), `backend/survival/brain.py`
- Test: `backend/tests/test_survival_reflexes.py`

**Interfaces:**
- Consumes: Task 4's interrupt hook contract and `INTERRUPTIBLE`; `actions.fail`, `actions.as_started`, `actions.take_search`; `pathing.find_path`; `purposes.home_of`, `AT_HOME`, `HOME_RANGE`, `meal`, `foods`, `walk_to`; `toolmaking.free_cells`; `situation.in_tick`, `DUSK`, `NIGHTFALL`; `memory.remember`, `SHELTER_KINDS`, `nearest`, `cell_of`; `vitals.is_sheltered`, `EXHAUSTED_BELOW`; `actions.SAFE_FALL`; `triggers.ensure_brain`, `mark_trigger`.
- Produces:
  - `backend.survival.grid.Grid.placed_cells(x, z, reach, materials) -> list[tuple[Cell, str]]` (`placed_near` now uses it).
  - `backend.survival.reflexes`: `@dataclass(frozen=True) class Reflex(name, priority, trigger, plan, thought, event, cooldown=10.0, veto=False)` with `trigger(s) -> bool`, `plan(s, context) -> list[dict]`, `event` a template with `{name}`; `REFLEXES: list[Reflex]` (sorted by priority); `register(reflex) -> Reflex`; `reflex_hook(state, context, at) -> str | None` (the `Interrupt`); `end_reflex(state, at) -> list[dict]`; `set_aside(state) -> list[dict]`; `fall_depth(grid, cell, removed=None) -> tuple[int, bool]`; `too_far(grid, cell, removed=None) -> str | None` (`"drop"`, `"lava"` or None). Registered: `surface` 10, `avoid_drop` 20 (veto), `eat_now` 40, `warm_up` 50, `head_home` 60, `collapse` 70.
  - `brain.BRAIN` gains `interrupt=reflex_hook`; `brain_plan` ends a reflex whose steps ran out and resumes the set-aside steps. Events of kind `reflex`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_reflexes.py`:

```python
import sqlite3
import unittest

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.brain import brain_plan
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, places, remember
from backend.survival.reflexes import REFLEXES, reflex_hook
from backend.survival.triggers import ensure_brain
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
LATE = {**DAY, "seconds_into_day": 2100.0}  # within 3 game minutes of dusk


def flat(cells=None):
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("stone" if y <= 0 else "air"))


def holed(column, cells=None):
    """Flat stone with a hole 6 deep under the (x, z) column (air from y -6 to -1)."""
    cells = cells or {}

    def rule(x, y, z):
        if (x, y, z) in cells:
            return cells[(x, y, z)]
        if (x, z) == column and -6 <= y <= -1:
            return "air"
        return "stone" if y <= 0 else "air"

    return Grid(rule)


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def brainy(grid=None, clock=None):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return ActionContext(grid=grid or flat(), clock_at=clock or (lambda at: DAY), planner=brain_plan, events=[],
                         db=db, interrupt=reflex_hook)


def choose(state, purpose):
    ensure_brain(state).update(purpose=purpose, pending=None, chosen_at=0.0, batches=0, replans=0, planned_at=None)


def walk(x, y, z, purpose):
    return {"kind": "walk", "target": [x, y, z], "reach": 0.0, "purpose": purpose}


class ReflexTests(unittest.TestCase):
    def test_m3_reflexes_run_in_priority_order_with_room_for_flee(self):
        self.assertEqual([(reflex.name, reflex.priority) for reflex in REFLEXES][:6],
                         [("surface", 10), ("avoid_drop", 20), ("eat_now", 40), ("warm_up", 50),
                          ("head_home", 60), ("collapse", 70)])

    def test_collapse_sets_the_plan_aside_and_gives_it_back(self):
        state = pet(vitals={**START_VITALS, "energy": 5.0})
        choose(state, "explore")
        state["queue"] = [walk(9, 1, 0, "explore")]
        ctx = brainy()
        advance_actions(state, ctx, 1.0)
        brain = state["brain"]
        self.assertEqual((state["action"]["kind"], state["action"]["purpose"], brain["reflex"]),
                         ("sleep", "collapse", "collapse"))
        self.assertEqual(brain["set_aside"], [walk(9, 1, 0, "explore")])
        self.assertIn(("reflex", "Pip collapsed from exhaustion."), [event[1:] for event in ctx.events])
        state["vitals"]["energy"] = 96.0
        advance_actions(state, ctx, 2.0)
        self.assertEqual((state["action"]["kind"], state["action"]["purpose"]), ("walk", "explore"))
        self.assertIsNone(brain["reflex"])
        self.assertEqual(brain["reflex_ends"], {"collapse": 2.0})
        self.assertIn("reflex_ended", brain["pending"]["reasons"])

    def test_the_more_urgent_reflex_goes_first(self):
        state = pet(inventory={"berries": 1}, vitals={**START_VITALS, "energy": 5.0, "hunger": 10.0})
        choose(state, "explore")
        state["queue"] = [walk(9, 1, 0, "explore")]
        ctx = brainy()
        advance_actions(state, ctx, 1.0)
        self.assertEqual((state["action"]["kind"], state["brain"]["reflex"]), ("eat", "eat_now"))
        advance_actions(state, ctx, 3.0)
        self.assertEqual((state["action"]["kind"], state["brain"]["reflex"]), ("sleep", "collapse"))
        self.assertEqual(state["brain"]["set_aside"], [walk(9, 1, 0, "explore")])

    def test_head_home_near_dusk_cuts_a_walk_and_sets_it_aside(self):
        state = pet()
        choose(state, "gather_wood")
        state["queue"] = [walk(0, 1, 9, "gather_wood")]
        ctx = brainy(clock=lambda at: DAY if at < 1.0 else LATE)
        remember(ctx.db, "home", (20, 1, 0), 0.0)
        advance_actions(state, ctx, 0.5)
        advance_actions(state, ctx, 1.0)
        cut = state["recent_actions"][-1]
        self.assertEqual((cut["kind"], cut["result"], cut["reason"]), ("walk", "interrupted", "head_home"))
        self.assertEqual(state["position"], {"x": 0.0, "y": 1.0, "z": 3.0})
        self.assertEqual((state["action"]["target"], state["action"]["purpose"]),
                         ({"x": 20, "y": 1, "z": 0}, "head_home"))
        self.assertEqual(state["brain"]["set_aside"], [walk(0, 1, 9, "gather_wood")])
        self.assertEqual(state["last_thought"], "It's getting dark. Home, quickly.")

    def test_avoid_drop_vetoes_mining_the_block_under_mimo_over_a_deep_hole(self):
        state = pet()
        choose(state, "mine_ore")
        state["queue"] = [{"kind": "mine", "target": [0, 0, 0], "purpose": "mine_ore"}]
        grid = holed((0, 0), {(0, 0, 0): "coal_ore"})
        ctx = brainy(grid)
        advance_actions(state, ctx, 1.0)
        self.assertEqual(grid.material(0, 0, 0), "coal_ore")
        self.assertEqual(state["position"]["y"], 1.0)
        self.assertEqual((state["last_failure"]["code"], state["last_failure"]["reason"]),
                         ("blocked", "that would be a long fall"))
        self.assertEqual([(place["kind"], place["note"]) for place in places(ctx.db)], [("danger", "drop")])

    def test_avoid_drop_cuts_a_walk_whose_next_cell_lost_its_floor(self):
        state = pet()
        choose(state, "explore")
        state["queue"] = [walk(5, 1, 0, "explore")]
        grid = holed((2, 0))
        ctx = brainy(grid)
        advance_actions(state, ctx, 0.4)
        grid.put(2, 0, 0, "air")
        advance_actions(state, ctx, 0.5)
        cut = state["recent_actions"][-1]
        self.assertEqual((cut["kind"], cut["result"], cut["reason"]), ("walk", "interrupted", "avoid_drop"))
        path = [(entry["x"], entry["y"], entry["z"]) for entry in state["action"]["path"]]
        self.assertNotIn((2, 1, 0), path)
        self.assertEqual((path[-1], state["action"]["purpose"]), ((5, 1, 0), "explore"))

    def test_warm_up_places_a_carried_furnace_or_walks_home(self):
        cold = pet(inventory={"furnace": 1}, vitals={**START_VITALS, "warmth": 20.0})
        self.assertEqual(reflex_hook(cold, brainy(), 0.0), "warm_up")
        self.assertEqual(cold["queue"], [{"kind": "place", "target": [1, 1, 0], "block": "furnace", "purpose": "warm_up"}])
        homeward = pet(vitals={**START_VITALS, "warmth": 20.0})
        ctx = brainy()
        remember(ctx.db, "home", (30, 1, 0), 0.0)
        self.assertEqual(reflex_hook(homeward, ctx, 0.0), "warm_up")
        self.assertEqual(homeward["queue"], [walk(30, 1, 0, "warm_up")])
        self.assertIsNone(reflex_hook(pet(vitals={**START_VITALS, "warmth": 20.0}), brainy(), 0.0))

    def test_surface_mines_a_ceiling_or_heads_for_the_shore(self):
        under = pet(vitals={**START_VITALS, "air": 30.0})
        self.assertEqual(reflex_hook(under, brainy(flat({(0, 1, 0): "water", (0, 2, 0): "dirt"})), 0.0), "surface")
        self.assertEqual(under["queue"], [{"kind": "mine", "target": [0, 2, 0], "purpose": "surface"}])
        lake = Grid(lambda x, y, z: ("water" if x <= 2 else "stone") if y <= 0 else "air")
        floating = pet(vitals={**START_VITALS, "air": 30.0})
        self.assertEqual(reflex_hook(floating, brainy(lake), 0.0), "surface")
        self.assertEqual(floating["queue"], [walk(3, 1, 0, "surface")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_reflexes.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.reflexes'`.

- [ ] **Step 3: Let the grid list placed cells**

In `backend/survival/grid.py`, replace the whole `placed_near` method with:

```python
    def placed_cells(self, x: int, z: int, reach: float, materials: tuple[str, ...]) -> list[tuple[Cell, str]]:
        """Placed blocks of `materials` within `reach` blocks (horizontally) of (x, z), with their cells."""
        for cx in range(math.floor((x - reach) / CHUNK), math.floor((x + reach) / CHUNK) + 1):
            for cz in range(math.floor((z - reach) / CHUNK), math.floor((z + reach) / CHUNK) + 1):
                self._load(cx * CHUNK, cz * CHUNK)
        return [(cell, material) for cell, material in self.edits.items()
                if material in materials and math.hypot(cell[0] - x, cell[2] - z) <= reach]

    def placed_near(self, x: int, z: int, reach: float, materials: tuple[str, ...]) -> set[str]:
        """Which of `materials` have been placed within `reach` blocks (horizontally) of (x, z)."""
        return {material for _, material in self.placed_cells(x, z, reach, materials)}
```

- [ ] **Step 4: Write the reflexes**

Create `backend/survival/reflexes.py`:

```python
"""Reflexes: rules that take over at once, ahead of the purpose layer.

A Reflex is data: a name, a priority (lower is more urgent), a trigger, a planner, a thought, an
event line and a cooldown. The brain's interrupt hook (`reflex_hook`) checks them in priority
order before every step starts and while a walk, sleep or wait runs. The first whose trigger
holds and whose planner returns steps takes over:

- The first takeover sets the purpose's queue aside (a cut walk is queued again toward its
  target) and puts the reflex's steps in the queue, tagged with the reflex's name. A more urgent
  reflex can take over from a running one; a less urgent one waits.
- When the reflex's steps run out, `end_reflex` brings the set-aside steps back, starts the
  reflex's cooldown and asks for a new choice (`reflex_ended`).
- A veto reflex (avoid_drop) does not set anything aside: it fails or replaces only the step that
  would fall too far, even when it has no steps of its own.

M3 registers surface (10), avoid_drop (20), eat_now (40), warm_up (50), head_home (60) and
collapse (70). Priority 30 is left for sub-project 3's flee; creature reflexes register
themselves with `register`.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Callable

from backend.services.blocks import hardness, is_solid
from backend.services.crafting import can_harvest
from backend.services.worldgen import WORLD_MIN_Y
from backend.survival.actions import SAFE_FALL, ActionContext, as_started, fail, take_search
from backend.survival.grid import Cell, Grid
from backend.survival.memory import SHELTER_KINDS, cell_of, nearest, remember
from backend.survival.once import log_once
from backend.survival.pathing import find_path
from backend.survival.purposes import AT_HOME, HOME_RANGE, foods, home_of, meal, walk_to
from backend.survival.situation import DUSK, NIGHTFALL, Situation, in_tick
from backend.survival.steps import as_cell
from backend.survival.toolmaking import free_cells
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.vitals import EXHAUSTED_BELOW, is_sheltered

logger = logging.getLogger(__name__)

SURFACE_BELOW = 40.0
EAT_NOW_BELOW = 15.0
EAT_NOW_FULL = 40.0
WARM_UP_BELOW = 25.0
HEAD_HOME_LEAD = 180.0  # game seconds before dusk
SHORE_SEARCH = 2000
FIRE_STAND = 2.0


@dataclass(frozen=True)
class Reflex:
    name: str
    priority: int
    trigger: Callable[[Situation], bool]
    plan: Callable[[Situation, ActionContext], list[dict]]
    thought: str
    event: str  # "{name} ..." for the event log
    cooldown: float = 10.0  # real seconds before it may fire again after it ended
    veto: bool = False


REFLEXES: list[Reflex] = []


def register(reflex: Reflex) -> Reflex:
    """Add a reflex (or replace the one with the same name), keeping the list in priority order."""
    REFLEXES[:] = sorted([known for known in REFLEXES if known.name != reflex.name] + [reflex],
                         key=lambda known: known.priority)
    return reflex


def by_name(name: str | None) -> Reflex | None:
    return next((reflex for reflex in REFLEXES if reflex.name == name), None)


# The hook --------------------------------------------------------------------------------------

def set_aside(state: dict) -> list[dict]:
    """The purpose's steps to resume later: a running walk again toward its target, then the queue."""
    kept = []
    action = state["action"]
    if action is not None and action["kind"] == "walk":
        target = action["target"]
        spec = {"kind": "walk", "target": [target["x"], target["y"], target["z"]], "reach": action["reach"]}
        if "purpose" in action:
            spec["purpose"] = action["purpose"]
        kept.append(spec)
    return kept + [dict(spec) for spec in state["queue"]]


def take_over(state: dict, reflex: Reflex, steps: list[dict], context: ActionContext, at: float) -> None:
    brain = ensure_brain(state)
    if reflex.veto:
        state["queue"] = steps
    else:
        if brain["reflex"] is None:
            brain["set_aside"] = set_aside(state)
        state["queue"] = [{**step, "purpose": reflex.name} for step in steps]
        brain["reflex"] = reflex.name
    state["last_thought"] = reflex.thought
    context.events.append((at, "reflex", reflex.event.format(name=state["name"])))


def reflex_hook(state: dict, context: ActionContext, at: float) -> str | None:
    """The interrupt hook: the first reflex that fires takes over. Returns its name, or None."""
    brain = ensure_brain(state)
    running = by_name(brain["reflex"])
    s = in_tick(state, context, at)
    for reflex in REFLEXES:
        if running is not None and reflex.priority >= running.priority:
            break
        if at - brain["reflex_ends"].get(reflex.name, -math.inf) < reflex.cooldown:
            continue
        try:
            if not reflex.trigger(s):
                continue
            steps = reflex.plan(s, context)
        except Exception as error:
            log_once(logger, f"{reflex.name} reflex", error)
            continue
        if not steps and not reflex.veto:
            continue
        take_over(state, reflex, list(steps), context, at)
        return reflex.name
    return None


def end_reflex(state: dict, at: float) -> list[dict]:
    """The running reflex's steps ran out: start its cooldown, ask for a new choice and hand back
    the steps it set aside."""
    brain = ensure_brain(state)
    brain["reflex_ends"][brain["reflex"]] = at
    brain["reflex"] = None
    brain["handled_failure"] = state.get("last_failure")
    mark_trigger(state, "reflex_ended", at)
    resumed, brain["set_aside"] = brain["set_aside"], []
    return resumed


# surface ---------------------------------------------------------------------------------------

def plan_surface(s: Situation, context: ActionContext) -> list[dict]:
    """Mine a ceiling that holds Mimo under water, or swim to the nearest shore once afloat."""
    x, y, z = s.here
    if s.grid.water(s.here):
        ceiling = (x, y + 1, z)
        material = s.grid.material(*ceiling)
        if is_solid(material) and hardness(material) is not None and can_harvest(material, s.inventory):
            return [{"kind": "mine", "target": list(ceiling)}]
        return []  # open water above: the swim-up hazard already takes Mimo up
    if s.grid.swimming(s.here) and take_search(context):
        cells, found = find_path(s.grid, s.here, lambda cell: s.grid.standable(cell) and not s.grid.swimming(cell),
                                 s.here, max_nodes=SHORE_SEARCH)
        if found:
            return [walk_to(cells[-1])]
    return []


register(Reflex("surface", 10, trigger=lambda s: s.vitals["air"] < SURFACE_BELOW, plan=plan_surface,
                thought="I need air!", event="{name} swam for air.", cooldown=3.0))


# avoid_drop ------------------------------------------------------------------------------------

def fall_depth(grid: Grid, cell: Cell, removed: Cell | None = None) -> tuple[int, bool]:
    """How far Mimo would fall from `cell` (with `removed` gone), and whether it passes lava."""

    def holds(below: Cell) -> bool:
        if below == removed:
            return False
        material = grid.material(*below)
        return material == "water" or is_solid(material)

    x, y, z = cell
    lava = False
    while not holds((x, y - 1, z)) and y > WORLD_MIN_Y:
        y -= 1
        lava = lava or ((x, y, z) != removed and grid.material(x, y, z) == "lava")
    return cell[1] - y, lava


def too_far(grid: Grid, cell: Cell, removed: Cell | None = None) -> str | None:
    """"lava" or "drop" when falling from `cell` would hurt too much, else None."""
    blocks, lava = fall_depth(grid, cell, removed)
    if lava:
        return "lava"
    return "drop" if blocks > SAFE_FALL else None


def drop_ahead(s: Situation) -> tuple[str, Cell, str] | None:
    """("walk", cell, why) for the next cell of the running walk, or ("mine", cell, why) for a
    queued mine of the block under Mimo, when either would drop Mimo too far."""
    action = s.state["action"]
    if action is not None:
        if action["kind"] != "walk":
            return None
        upcoming = [entry for entry in action["path"] if entry["at"] > s.at]
        if not upcoming:
            return None
        cell = as_cell(upcoming[0])
        why = None if s.grid.supported(cell) else too_far(s.grid, cell)
        return ("walk", cell, why) if why else None
    if not s.state["queue"] or s.state["queue"][0].get("kind") != "mine":
        return None
    try:
        target = as_cell(s.state["queue"][0].get("target"))
    except ValueError:
        return None
    x, y, z = s.here
    if target != (x, y - 1, z):
        return None
    why = too_far(s.grid, s.here, removed=target)
    return ("mine", target, why) if why else None


def plan_avoid_drop(s: Situation, context: ActionContext) -> list[dict]:
    """Fail a mine that would drop Mimo too far, or walk again around a cell that lost its floor."""
    found = drop_ahead(s)
    if found is None:
        return []
    what, cell, why = found
    if context.db is not None:
        remember(context.db, "danger", cell, s.at, why)
    if what == "mine":
        spec = s.state["queue"][0]
        fail(s.state, as_started(spec, s.at), s.at, "that would be a long fall", "blocked")
        return []
    action = s.state["action"]
    target = action["target"]
    again = {"kind": "walk", "target": [target["x"], target["y"], target["z"]], "reach": action["reach"]}
    if "purpose" in action:
        again["purpose"] = action["purpose"]
    return [again, *s.state["queue"]]


register(Reflex("avoid_drop", 20, trigger=lambda s: drop_ahead(s) is not None, plan=plan_avoid_drop,
                thought="Whoa, that's a long way down.", event="{name} stopped at the edge of a long drop.",
                cooldown=0.0, veto=True))


# eat_now ---------------------------------------------------------------------------------------

register(Reflex("eat_now", 40,
                trigger=lambda s: s.vitals["hunger"] < EAT_NOW_BELOW and bool(foods(s.inventory)),
                plan=lambda s, context: meal(s.inventory, s.vitals["hunger"], EAT_NOW_FULL),
                thought="I'm starving. I have to eat now.", event="{name} ate in a hurry.", cooldown=5.0))


# warm_up ---------------------------------------------------------------------------------------

def plan_warm_up(s: Situation, context: ActionContext) -> list[dict]:
    """Place a carried furnace (it warms like a fire), else walk to the nearest known warm spot."""
    if s.inventory.get("furnace", 0) > 0:
        cells = free_cells(s)
        if cells:
            return [{"kind": "place", "target": list(cells[0]), "block": "furnace"}]
    x, _, z = s.here
    spots = []
    home = nearest(s.places, s.here, SHELTER_KINDS, HOME_RANGE)
    if home is not None:
        spots.append((s.distance(cell_of(home)), walk_to(cell_of(home))))
    for cell, _ in s.grid.placed_cells(x, z, HOME_RANGE, ("furnace",)):
        spots.append((s.distance(cell), walk_to(cell, FIRE_STAND)))
    spots = [spot for spot in spots if spot[0] > FIRE_STAND]
    return [min(spots, key=lambda spot: spot[0])[1]] if spots else []


register(Reflex("warm_up", 50, trigger=lambda s: s.vitals["warmth"] < WARM_UP_BELOW, plan=plan_warm_up,
                thought="Brr. I need to get warm.", event="{name} went to get warm.", cooldown=30.0))


# head_home -------------------------------------------------------------------------------------

def head_home_due(s: Situation) -> bool:
    if not DUSK - HEAD_HOME_LEAD <= s.clock["seconds_into_day"] < NIGHTFALL:
        return False
    if s.brain["purpose"] in ("go_home", "sleep"):
        return False
    home = home_of(s)
    if home is None or s.distance(cell_of(home)) <= AT_HOME:
        return False
    x, y, z = s.here
    return not is_sheltered(s.grid.material, x, y, z)


register(Reflex("head_home", 60, trigger=head_home_due,
                plan=lambda s, context: [walk_to(cell_of(home_of(s)))],
                thought="It's getting dark. Home, quickly.", event="{name} hurried home before dark.",
                cooldown=60.0))


# collapse --------------------------------------------------------------------------------------

register(Reflex("collapse", 70,
                trigger=lambda s: s.vitals["energy"] < EXHAUSTED_BELOW and (s.state["action"] or {}).get("kind") != "sleep",
                plan=lambda s, context: [{"kind": "sleep"}],
                thought="I can't keep my eyes open...", event="{name} collapsed from exhaustion.", cooldown=30.0))
```

- [ ] **Step 5: Wire the reflexes into the brain**

In `backend/survival/brain.py`, add to the module docstring, before "`observe_step` hears about":

```python
Reflexes (backend.survival.reflexes) take over through the interrupt hook. When a reflex's steps
run out, brain_plan ends it and resumes the purpose's steps it set aside.
```

Replace:

```python
from backend.survival.purposes import PURPOSES, Purpose, is_valid
```

with:

```python
from backend.survival.purposes import PURPOSES, Purpose, is_valid
from backend.survival.reflexes import end_reflex, reflex_hook
```

In `brain_plan`, replace:

```python
    brain = ensure_brain(state)
    purpose = PURPOSES.get(brain["purpose"]) if brain["purpose"] else None
```

with:

```python
    brain = ensure_brain(state)
    if brain["reflex"] is not None:
        resumed = end_reflex(state, at)
        if resumed and brain["purpose"] is not None:
            return resumed
    purpose = PURPOSES.get(brain["purpose"]) if brain["purpose"] else None
```

Replace:

```python
BRAIN = Mind(plan=brain_plan, observe=observe_step, notice=notice_step)
```

with:

```python
BRAIN = Mind(plan=brain_plan, interrupt=reflex_hook, observe=observe_step, notice=notice_step)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_reflexes.py" -v`
Expected: `Ran 8 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 313 tests` … `OK`.

- [ ] **Step 7: Commit**

```bash
git add backend/survival/grid.py backend/survival/reflexes.py backend/survival/brain.py backend/tests/test_survival_reflexes.py
git commit -m "feat: add reflexes that take over for air, drops, hunger, cold, dusk and exhaustion" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Pickers: utility, Jev and Luna

**Files:**
- Create: `backend/survival/pickers.py`, `backend/survival/models.py`
- Test: `backend/tests/test_survival_pickers.py`

**Interfaces:**
- Consumes: `purposes.offered`, `purposes.PURPOSES`, `Situation`, `memory.cell_of`, `once.log_once`; the old request shapes in `backend/services/live_mimo.py` (`_jev_decision`, `_model_decision`), copied, not imported.
- Produces:
  - `backend.survival.pickers`: `JITTER = 6.0`, `PENALTY = 30.0`; `@dataclass(frozen=True) class Option(name, phrase, description, facts, score)`; `options(s) -> list[Option]`; `utility_pick(choices, rng) -> str`; `thought_for(name, rng) -> str`; `context_payload(s, events) -> dict` (keys `name, traits, mood, vitals, phase, day, inventory, known_places, recent_events, trigger`).
  - `backend.survival.models`: `JEV_TIMEOUT = 20.0`, `LUNA_TIMEOUT = 45.0`, `REFLECTION_LIMIT = 160`; `Http = Callable[[str, dict, dict, float], dict]` (url, headers, body, timeout → parsed JSON); `class ModelError(RuntimeError)`; `post_json(url, headers, body, timeout) -> dict`; `jev_configured(env) -> bool`; `luna_configured(env) -> bool`; `ask_jev(payload, choices, env, http=post_json) -> str`; `ask_luna(payload, choices, env, http=post_json) -> str`; `luna_reflect(payload, option, env, http=post_json) -> str`. Every model function raises `ModelError` when anything goes wrong or the answer is not an offered purpose.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_pickers.py`:

```python
import json
import random
import sqlite3
import unittest
from unittest.mock import patch
from urllib.error import URLError

from backend.survival import brain  # noqa: F401  (registers every M3 purpose)
from backend.survival.actions import ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, remember
from backend.survival.models import ModelError, ask_jev, ask_luna, luna_reflect, post_json
from backend.survival.pickers import Option, context_payload, options, utility_pick
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
TREE = (5, 0, 0)
CHOICES = [Option("gather_wood", "gather wood", "Chop a tree.", "a tree 5 blocks away", 72.5),
           Option("rest", "rest", "Rest a while.", "mood 70", 15.0)]
PAYLOAD = {"name": "Pip", "traits": {"curiosity": 80}}


def forest():
    return Grid(lambda x, y, z: "oak_log" if (x, z) == (5, 0) and 1 <= y <= 4 else ("stone" if y <= 0 else "air"))


def situation(clock=DAY, places=(), **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    for kind, cell in places:
        remember(db, kind, cell, 0.0)
    return Situation(state, forest(), clock, 0.0, db)


def picks(s):
    """What the utility picker chooses for `s` under 20 different random seeds."""
    return {utility_pick(options(s), random.Random(seed)) for seed in range(20)}


class FakeHttp:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def luna_answer(content):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
@patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [TREE])
@patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [TREE])
class UtilityTests(unittest.TestCase):
    def test_a_day_goes_wood_then_tools_then_stone(self):
        self.assertEqual(picks(situation()), {"gather_wood"})
        self.assertEqual(picks(situation(inventory={"oak_log": 3})), {"craft_tools"})
        self.assertEqual(picks(situation(inventory={"oak_log": 4, "wooden_pickaxe": 1})), {"gather_stone"})

    def test_needs_come_first(self):
        self.assertEqual(picks(situation(NIGHT, places=[("home", (20, 1, 0))])), {"go_home"})
        self.assertEqual(picks(situation(NIGHT)), {"sleep"})
        hungry = situation(inventory={"berries": 2}, vitals={**START_VITALS, "hunger": 20.0})
        self.assertEqual(picks(hungry), {"eat"})

    def test_a_recent_failure_scores_thirty_lower(self):
        s = situation()
        before = {option.name: option.score for option in options(s)}
        s.brain["penalties"]["gather_wood"] = 100.0
        after = {option.name: option.score for option in options(s)}
        self.assertEqual(before["gather_wood"] - after["gather_wood"], 30.0)
        self.assertEqual(before["rest"], after["rest"])

    def test_the_model_payload_carries_needs_traits_places_and_events(self):
        s = situation(places=[("home", (3, 1, 4))], traits={"curiosity": 80})
        payload = context_payload(s, [{"text": f"event {n}"} for n in range(10)])
        self.assertEqual(set(payload), {"name", "traits", "mood", "vitals", "phase", "day", "inventory",
                                        "known_places", "recent_events", "trigger"})
        self.assertEqual(payload["known_places"], [{"kind": "home", "note": "", "distance": 5}])
        self.assertEqual(len(payload["recent_events"]), 8)
        self.assertEqual(payload["traits"], {"curiosity": 80})
        self.assertEqual(payload["trigger"], ["born"])


class JevTests(unittest.TestCase):
    def test_jev_gets_one_choice_question_over_the_offered_purposes(self):
        http = FakeHttp({"answers": {"purpose": {"choice": "gather_wood"}}})
        self.assertEqual(ask_jev(PAYLOAD, CHOICES, {"TYPESAFE_API_KEY": "k"}, http), "gather_wood")
        url, headers, body, timeout = http.calls[0]
        self.assertEqual((url, headers["Authorization"], timeout), ("https://api.typesafe.ai/v1/systemone", "Bearer k", 20.0))
        self.assertEqual((body["model"], body["state"]), ("jev-latest", PAYLOAD))
        question = body["questions"]["purpose"]
        self.assertEqual((question["type"], sorted(question["criteria"])), ("choice", ["gather_wood", "rest"]))
        self.assertIn("a tree 5 blocks away", question["criteria"]["gather_wood"])

    def test_jev_answers_outside_the_choices_or_failures_raise(self):
        env = {"TYPESAFE_API_KEY": "k", "TYPESAFE_MODEL": "jev-9", "TYPESAFE_API_URL": "http://jev.test"}
        for answer in ({"answers": {"purpose": {"choice": "build_shelter"}}}, {"answers": {}},
                       ModelError("request failed: boom")):
            with self.assertRaises(ModelError, msg=answer):
                ask_jev(PAYLOAD, CHOICES, env, FakeHttp(answer))
        http = FakeHttp({"answers": {"purpose": {"choice": "rest"}}})
        ask_jev(PAYLOAD, CHOICES, env, http)
        self.assertEqual((http.calls[0][0], http.calls[0][2]["model"]), ("http://jev.test", "jev-9"))


class LunaTests(unittest.TestCase):
    def test_luna_picks_with_structured_output_limited_to_the_choices(self):
        http = FakeHttp(luna_answer('{"purpose": "rest"}'))
        self.assertEqual(ask_luna(PAYLOAD, CHOICES, {"OPENAI_API_KEY": "sk"}, http), "rest")
        url, headers, body, timeout = http.calls[0]
        self.assertEqual((url, headers["Authorization"], timeout, body["model"]),
                         ("https://api.openai.com/v1/chat/completions", "Bearer sk", 45.0, "gpt-6-luna"))
        schema = body["response_format"]["json_schema"]
        self.assertTrue(schema["strict"])
        self.assertEqual(schema["schema"]["properties"]["purpose"]["enum"], ["gather_wood", "rest"])
        fenced = FakeHttp(luna_answer('```json\n{"purpose": "gather_wood"}\n```'))
        self.assertEqual(ask_luna(PAYLOAD, CHOICES, {"OPENAI_API_KEY": "sk"}, fenced), "gather_wood")

    def test_bad_luna_answers_raise_and_reflections_are_one_short_line(self):
        env = {"OPENAI_API_KEY": "sk"}
        for answer in (luna_answer('{"purpose": "fish"}'), luna_answer("not json"),
                       {"choices": [{"finish_reason": "length", "message": {"content": ""}}]}, {"oops": 1}):
            with self.assertRaises(ModelError, msg=answer):
                ask_luna(PAYLOAD, CHOICES, env, FakeHttp(answer))
        long = "What   a\nlovely tree. " * 20
        thought = luna_reflect(PAYLOAD, CHOICES[0], env, FakeHttp(luna_answer(json.dumps({"thought": long}))))
        self.assertEqual(len(thought), 160)
        self.assertTrue(thought.startswith("What a lovely tree. What a lovely tree."))
        with self.assertRaises(ModelError):
            luna_reflect(PAYLOAD, CHOICES[0], env, FakeHttp(luna_answer('{"thought": "  "}')))

    def test_post_json_turns_network_errors_into_model_errors(self):
        with patch("backend.survival.models.urlopen", side_effect=URLError("down")):
            with self.assertRaises(ModelError):
                post_json("http://example.test", {}, {}, 1.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_pickers.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.models'`.

- [ ] **Step 3: Write the utility picker, thoughts and payload**

Create `backend/survival/pickers.py`:

```python
"""Choosing a purpose: the utility picker, thoughts and what a model is told.

`options(s)` lists the purposes on offer with their facts and utility scores; a purpose that
failed twice in the last 10 game minutes scores 30 lower. The utility picker takes the best score
after a small random nudge (0 to 6), so Mimo does not always do the same thing. Thoughts come
from each purpose's templates. `context_payload(s, events)` is what Jev and Luna see: name,
traits, mood, vitals, phase, day, inventory, known places, the last 8 events and the trigger.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass

from backend.survival.memory import cell_of
from backend.survival.once import log_once
from backend.survival.purposes import PURPOSES, offered
from backend.survival.situation import Situation

logger = logging.getLogger(__name__)

JITTER = 6.0
PENALTY = 30.0
PLACES_SHOWN = 12
EVENTS_SHOWN = 8


@dataclass(frozen=True)
class Option:
    name: str
    phrase: str
    description: str
    facts: str
    score: float


def options(s: Situation) -> list[Option]:
    """Every purpose on offer with its facts and score. One whose facts or score crash is left out."""
    found = []
    for purpose in offered(s):
        try:
            facts, score = purpose.facts(s), float(purpose.score(s))
        except Exception as error:
            log_once(logger, f"{purpose.name} facts", error)
            continue
        if s.brain["penalties"].get(purpose.name, -math.inf) > s.at:
            score -= PENALTY
        found.append(Option(purpose.name, purpose.phrase, purpose.description, facts, score))
    return found


def utility_pick(choices: list[Option], rng: random.Random) -> str:
    """The best score after a random nudge of up to JITTER."""
    return max(choices, key=lambda option: option.score + rng.uniform(0, JITTER)).name


def thought_for(name: str, rng: random.Random) -> str:
    purpose = PURPOSES.get(name)
    if purpose is None or not purpose.thoughts:
        return f"Time to {name.replace('_', ' ')}."
    return rng.choice(purpose.thoughts)


def context_payload(s: Situation, events: list[dict]) -> dict:
    """What a model is told about Mimo when it chooses. `events` are newest first."""
    known = sorted(s.places, key=lambda place: math.dist(cell_of(place), s.here))[:PLACES_SHOWN]
    pending = s.brain["pending"]
    return {
        "name": s.state["name"],
        "traits": dict(s.state.get("traits", {})),
        "mood": round(s.vitals["mood"]),
        "vitals": {name: round(value) for name, value in s.vitals.items()},
        "phase": s.phase,
        "day": s.clock["day_number"],
        "inventory": dict(s.inventory),
        "known_places": [{"kind": place["kind"], "note": place["note"],
                          "distance": round(math.dist(cell_of(place), s.here))} for place in known],
        "recent_events": [event["text"] for event in events[:EVENTS_SHOWN]],
        "trigger": list(pending["reasons"]) if pending else [],
    }
```

- [ ] **Step 4: Write the model calls**

Create `backend/survival/models.py`:

```python
"""Asking Jev or Luna to choose a purpose, and Luna for a reflection.

The calls reuse the old brain's request shapes (backend/services/live_mimo.py): Jev gets one
"choice" question whose criteria are the offered purposes with their facts; Luna gets the same
context as a chat message, with strict structured output (the purpose is an enum of the offered
names) when it is gpt-6-luna on api.openai.com. Environment: TYPESAFE_API_KEY, TYPESAFE_MODEL,
TYPESAFE_API_URL for Jev; MIMO_MODEL_API_KEY or OPENAI_API_KEY, MIMO_MODEL, MIMO_MODEL_URL for
Luna. `http` is injected so tests never touch the network; `post_json` is the real one. Every
function raises ModelError when anything goes wrong, and the caller falls back to the utility
picker.
"""

from __future__ import annotations

import json
from typing import Callable, Mapping
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from backend.survival.pickers import Option

JEV_TIMEOUT = 20.0
LUNA_TIMEOUT = 45.0
DEFAULT_JEV_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_LUNA_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_LUNA_MODEL = "gpt-6-luna"
REFLECTION_LIMIT = 160
INSTRUCTIONS = ("Choose what this small survival pet should do next. Keep it alive first (food, warmth, "
                "rest, shelter by night), then follow its traits. Choose only from the offered purposes.")

Http = Callable[[str, dict, dict, float], dict]
Env = Mapping[str, str]


class ModelError(RuntimeError):
    """A model call failed or answered with something that cannot be used."""


def post_json(url: str, headers: dict, body: dict, timeout: float) -> dict:
    """POST `body` as JSON and parse the JSON answer."""
    try:
        with urlopen(Request(url, data=json.dumps(body).encode(), headers=headers), timeout=timeout) as response:
            return json.load(response)
    except (URLError, OSError, ValueError) as error:
        raise ModelError(f"request failed: {error}") from error


def jev_configured(env: Env) -> bool:
    return bool(env.get("TYPESAFE_API_KEY"))


def luna_key(env: Env) -> str | None:
    return env.get("MIMO_MODEL_API_KEY") or env.get("OPENAI_API_KEY") or None


def luna_configured(env: Env) -> bool:
    return luna_key(env) is not None


def criteria(choices: list[Option]) -> dict[str, str]:
    return {option.name: f"{option.description} Now: {option.facts}." for option in choices}


def ask_jev(payload: dict, choices: list[Option], env: Env, http: Http = post_json) -> str:
    """Jev's choice among `choices`."""
    body = {"model": env.get("TYPESAFE_MODEL") or "jev-latest", "state": payload,
            "questions": {"purpose": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": criteria(choices)}}}
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "curl/8.7.1",
               "Authorization": f"Bearer {env.get('TYPESAFE_API_KEY', '')}"}
    answer = http(env.get("TYPESAFE_API_URL") or DEFAULT_JEV_URL, headers, body, JEV_TIMEOUT)
    try:
        choice = answer["answers"]["purpose"]["choice"]
    except (KeyError, TypeError) as error:
        raise ModelError(f"Jev answered without a choice ({error!r})") from error
    if choice not in {option.name for option in choices}:
        raise ModelError(f"Jev chose {choice!r}, which was not offered")
    return choice


def luna_json(messages: list[dict], name: str, schema: dict, env: Env, http: Http) -> dict:
    """Ask Luna for one JSON object that follows `schema`."""
    url = env.get("MIMO_MODEL_URL") or DEFAULT_LUNA_URL
    model = env.get("MIMO_MODEL") or DEFAULT_LUNA_MODEL
    body: dict = {"model": model, "messages": messages}
    if model == DEFAULT_LUNA_MODEL and urlsplit(url).hostname == "api.openai.com":
        body.update({"reasoning_effort": "medium", "max_completion_tokens": 1024,
                     "response_format": {"type": "json_schema",
                                         "json_schema": {"name": name, "strict": True, "schema": schema}}})
    else:
        body.update({"temperature": 0.8, "max_tokens": 180})
    headers = {"Content-Type": "application/json"}
    key = luna_key(env)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    result = http(url, headers, body, LUNA_TIMEOUT)
    try:
        choice = result["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ModelError("Luna's answer was cut off")
        message = choice["message"]
        if message.get("refusal"):
            raise ModelError("Luna declined to answer")
        content = message.get("content")
        if not isinstance(content, str):
            raise ModelError("Luna returned no content")
        if content.startswith("```"):
            content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(content)
    except ModelError:
        raise
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ModelError(f"Luna answered in an unexpected shape ({error!r})") from error
    if not isinstance(parsed, dict):
        raise ModelError("Luna did not return a JSON object")
    return parsed


def ask_luna(payload: dict, choices: list[Option], env: Env, http: Http = post_json) -> str:
    """Luna's choice among `choices`."""
    names = [option.name for option in choices]
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"purpose": {"type": "string", "enum": names}}, "required": ["purpose"]}
    messages = [
        {"role": "system", "content": "You choose what one small survival pet does next. Return valid JSON only."},
        {"role": "user", "content": json.dumps({"pet": payload, "choices": criteria(choices),
                                                "instructions": INSTRUCTIONS + ' Answer {"purpose": "<choice>"}.'})},
    ]
    choice = luna_json(messages, "mimo_purpose", schema, env, http).get("purpose")
    if choice not in names:
        raise ModelError(f"Luna chose {choice!r}, which was not offered")
    return choice


def luna_reflect(payload: dict, option: Option, env: Env, http: Http = post_json) -> str:
    """One short first-person line from Luna about what Mimo is setting out to do."""
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"thought": {"type": "string"}}, "required": ["thought"]}
    messages = [
        {"role": "system", "content": f"You are {payload.get('name', 'Mimo')}, a small voxel pet surviving in a "
                                      "wild world. Speak as the pet. Return valid JSON only."},
        {"role": "user", "content": json.dumps({
            "pet": payload, "chosen": f"{option.phrase}: {option.facts}",
            "instructions": 'In one short first-person sentence (at most 120 characters), say what you think as '
                            'you set out to do this. Answer {"thought": "<sentence>"}.'})},
    ]
    thought = luna_json(messages, "mimo_thought", schema, env, http).get("thought")
    line = " ".join(thought.split()) if isinstance(thought, str) else ""
    if not line:
        raise ModelError("Luna gave no thought")
    return line[:REFLECTION_LIMIT]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_pickers.py" -v`
Expected: `Ran 9 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 322 tests` … `OK`.

- [ ] **Step 6: Commit**

```bash
git add backend/survival/pickers.py backend/survival/models.py backend/tests/test_survival_pickers.py
git commit -m "feat: pick purposes by utility, or ask Jev or Luna with fallbacks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Choosing in the worker

**Files:**
- Create: `backend/survival/choosing.py`
- Modify: `backend/workers/mimo_worker.py`, `backend/survival/script.py` (delete `scripted_plan`)
- Test: `backend/tests/test_survival_choosing.py`, `backend/tests/test_survival_script.py`, `backend/tests/test_survival_tick_actions.py`

**Interfaces:**
- Consumes: `SurvivalWorld` (read-only and writable), `read_state`, `write_state`, `log_event`; `situation.from_db`; `pickers.options`, `utility_pick`, `thought_for`, `context_payload`, `Option`; `models.ask_jev`, `ask_luna`, `luna_reflect`, `jev_configured`, `luna_configured`, `post_json`, `ModelError`, `Http`; `triggers.ensure_brain`; `care.utc_day`; `clock.time_scale`; `brain.BRAIN`.
- Produces (`backend.survival.choosing`): `MODEL_GAP = 60.0`, `REFLECTION_CAP = 12`, `REFLECT_ON = ("dawn", "hello", "discovery")`; `@dataclass(frozen=True) class Ask(pending_id: int, route: str, reflect: bool, options: tuple[Option, ...], payload: dict, asked_at: float)`; `@dataclass(frozen=True) class Choice(purpose: str, picker: str, thought: str, calls: dict, error: str | None = None)`; `calls_today(brain, now) -> dict`; `route_for(brain, now, env) -> str`; `reflect_for(brain, route, now, env) -> bool`; `prepare(world, now, scale, env) -> Ask | None`; `decide(ask, env, http, rng) -> Choice` (never raises); `apply_choice(state, choice, now) -> None`; `store_choice(world, ask, choice, now) -> str | None`; `class InlineExecutor`; `class Chooser(env=None, http=post_json, executor=None, rng=None, scale=None)` with `poll(registry, now=None) -> str | None` and `close()`.
- `backend.workers.mimo_worker`: `WORKER_MIND = BRAIN`; `run_once(registry, previous, timestamp=None, mind=RESTING, chooser: Chooser | None = None) -> str`.
- Event `purpose`: `<name> decided to <phrase>. "<thought>"`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_choosing.py`:

```python
import random
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import Choice, Chooser, InlineExecutor, prepare, store_choice
from backend.survival.hatch import hatch
from backend.survival.models import ModelError
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.workers.mimo_worker import run_once

BORN = 1_000_000.0
JEV_URL = "https://api.typesafe.ai/v1/systemone"
LUNA_URL = "https://api.openai.com/v1/chat/completions"
JEV_REST = {"answers": {"purpose": {"choice": "rest"}}}


class FakeHttp:
    """Answers by URL; an exception is raised instead of returned."""

    def __init__(self, answers):
        self.answers, self.urls = answers, []

    def __call__(self, url, headers, body, timeout):
        self.urls.append(url)
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


class HeldExecutor:
    """Keeps submitted work until the test runs it, like a slow model call."""

    def __init__(self):
        self.held = []

    def submit(self, fn, *args):
        future = Future()
        self.held.append((future, fn, args))
        return future

    def run(self):
        for future, fn, args in self.held:
            future.set_result(fn(*args))
        self.held.clear()


class ChoosingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.path = self.registry.world_path(self.life)
        self.world = SurvivalWorld(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            change(state)
            write_state(db, state)

    def brain(self):
        return self.world.state()["brain"]

    def chooser(self, env=None, answers=None, executor=None):
        return Chooser(env=env or {}, http=FakeHttp(answers or {}), executor=executor or InlineExecutor(),
                       rng=random.Random(1), scale=1.0)

    def ask(self, now, env):
        return prepare(SurvivalWorld(self.path, read_only=True), now, 1.0, env)

    def test_without_keys_the_utility_picker_answers_at_once(self):
        tick_life(self.registry, BORN + 1, scale=1, mind=BRAIN)
        purpose = self.chooser().poll(self.registry, BORN + 1)
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["picker"], brain["pending"]), (purpose, "utility", None))
        self.assertIn(self.world.state()["last_thought"], PURPOSES[purpose].thoughts)
        self.assertEqual(self.world.events(1)[0]["kind"], "purpose")
        self.assertEqual((brain["calls"]["model"], brain["last_call_at"]), (0, None))

    def test_jev_answers_in_the_background_and_the_answer_is_stored(self):
        tick_life(self.registry, BORN + 1, scale=1, mind=BRAIN)
        held = HeldExecutor()
        chooser = self.chooser({"TYPESAFE_API_KEY": "k"}, {JEV_URL: JEV_REST}, held)
        self.assertIsNone(chooser.poll(self.registry, BORN + 1))
        self.assertIsNotNone(self.brain()["pending"])
        held.run()
        self.assertEqual(chooser.poll(self.registry, BORN + 3), "rest")
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["picker"], brain["calls"]["model"], brain["last_call_at"]),
                         ("rest", "jev", 1, BORN + 1))

    def test_the_gap_and_the_daily_caps_send_choices_to_utility(self):
        now = BORN + 100
        env = {"TYPESAFE_API_KEY": "k"}
        self.edit(lambda state: ensure_brain(state).update(last_call_at=now - 30))
        self.assertEqual(self.ask(now, env).route, "utility")
        self.edit(lambda state: mark_trigger(state, "hunger_30", now, urgent=True))
        self.assertEqual(self.ask(now, env).route, "jev")
        self.edit(lambda state: ensure_brain(state).update(last_call_at=now - 90))
        self.assertEqual(self.ask(now, {**env, "MIMO_MAX_DECISIONS_PER_DAY": "0"}).route, "utility")
        self.assertEqual(self.ask(now, {"OPENAI_API_KEY": "sk"}).route, "luna")
        self.assertEqual(self.ask(now, {"OPENAI_API_KEY": "sk", "MIMO_MAX_LUNA_DECISIONS_PER_DAY": "0"}).route,
                         "utility")
        self.assertEqual(self.ask(now, {}).route, "utility")

    def test_a_failed_model_call_falls_back_to_utility_is_counted_and_logged_once(self):
        forget_logged()
        tick_life(self.registry, BORN + 1, scale=1, mind=BRAIN)
        chooser = self.chooser({"TYPESAFE_API_KEY": "k"}, {JEV_URL: ModelError("request failed: down")})
        with self.assertLogs("backend.survival.choosing", level="ERROR") as logs:
            self.assertIsNotNone(chooser.poll(self.registry, BORN + 1))
        self.assertEqual(len(logs.output), 1)
        brain = self.brain()
        self.assertEqual((brain["picker"], brain["calls"]["model"], brain["last_call_at"]), ("utility", 1, BORN + 1))

    def test_a_stale_answer_is_thrown_away_but_its_calls_count(self):
        ask = self.ask(BORN + 1, {"TYPESAFE_API_KEY": "k"})
        self.edit(lambda state: mark_trigger(state, "health_50", BORN + 2, urgent=True))
        choice = Choice("rest", "jev", "Hm.", {"model": 1, "luna": 0, "reflections": 0})
        self.assertIsNone(store_choice(self.world, ask, choice, BORN + 3))
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["calls"]["model"]), (None, 1))
        self.assertEqual(self.world.events(1)[0]["kind"], "birth")

    def test_a_dead_life_is_left_alone(self):
        ask = self.ask(BORN + 1, {})
        self.edit(lambda state: state.update(died_at=BORN + 2, cause="fall"))
        self.assertIsNone(self.ask(BORN + 3, {}))
        self.assertIsNone(store_choice(self.world, ask, Choice("rest", "utility", "Hm.", {"model": 0, "luna": 0,
                                                                                          "reflections": 0}), BORN + 3))

    def test_reflections_ride_with_hello_choices_up_to_twelve_a_day(self):
        env = {"TYPESAFE_API_KEY": "k", "OPENAI_API_KEY": "sk"}
        reflection = {"choices": [{"finish_reason": "stop", "message": {"content": '{"thought": "Hello, friend!"}'}}]}
        self.edit(lambda state: mark_trigger(state, "hello", BORN + 1))
        self.chooser(env, {JEV_URL: JEV_REST, LUNA_URL: reflection}).poll(self.registry, BORN + 1)
        brain = self.brain()
        self.assertEqual(self.world.state()["last_thought"], "Hello, friend!")
        self.assertEqual((brain["calls"]["model"], brain["calls"]["luna"], brain["calls"]["reflections"]), (1, 1, 1))

        def spent(state):
            mark_trigger(state, "hello", BORN + 100)
            state["brain"]["calls"]["reflections"] = 12

        self.edit(spent)
        self.chooser(env, {JEV_URL: JEV_REST, LUNA_URL: reflection}).poll(self.registry, BORN + 100)
        self.assertIn(self.world.state()["last_thought"], PURPOSES["rest"].thoughts)

    def test_a_new_purpose_clears_the_plan_and_stops_a_wait(self):
        def busy(state):
            ensure_brain(state).update(purpose="explore", pending={"id": 7, "reasons": ["hour"], "since": BORN,
                                                                    "urgent": False})
            state["queue"] = [{"kind": "walk", "target": [1, 2, 3], "purpose": "explore"}]
            state["action"] = {"kind": "wait", "started_at": BORN, "ends_at": BORN + 60}

        self.edit(busy)
        ask = self.ask(BORN + 1, {})
        self.assertEqual(store_choice(self.world, ask, Choice("rest", "utility", "Hm.",
                                                              {"model": 0, "luna": 0, "reflections": 0}), BORN + 1), "rest")
        state = self.world.state()
        self.assertEqual((state["queue"], state["action"], state["brain"]["purpose"]), ([], None, "rest"))

    def test_the_worker_ticks_the_brain_and_answers_its_triggers(self):
        line = run_once(self.registry, None, BORN + 1, mind=BRAIN, chooser=self.chooser())
        self.assertIn(self.life["name"], line)
        self.assertIsNotNone(self.brain()["purpose"])


if __name__ == "__main__":
    unittest.main()
```

Replace the whole of `backend/tests/test_survival_script.py` with:

```python
import unittest

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.script import rest_plan
from backend.survival.vitals import START_VITALS

MORNING = {"phase": "day", "seconds_into_day": 1200.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def ctx(clock):
    """An ActionContext frozen at `clock` over flat stone."""
    return ActionContext(grid=Grid(lambda x, y, z: "stone" if y <= 0 else "air"), clock_at=lambda at: clock,
                         planner=rest_plan, events=[])


class RestPlanTests(unittest.TestCase):
    def test_sleeps_at_night_or_when_exhausted(self):
        self.assertEqual(rest_plan(pet(), ctx(NIGHT), 0.0),
                         [{"kind": "sleep", "thought": "It's dark. Time to curl up and sleep."}])
        tired = pet(vitals={**START_VITALS, "energy": 5.0})
        self.assertEqual(rest_plan(tired, ctx(MORNING), 0.0)[0]["thought"], "I'm too tired to keep my eyes open.")

    def test_waits_for_nightfall_at_most_a_minute_at_a_time(self):
        self.assertEqual(rest_plan(pet(), ctx(MORNING), 0.0), [{"kind": "wait", "seconds": 60.0}])
        dusk = {**MORNING, "phase": "dusk", "seconds_into_day": 2390.0}
        self.assertEqual(rest_plan(pet(), ctx(dusk), 0.0)[0]["seconds"], 10.0)
        fast = {**MORNING, "seconds_into_day": 2399.5, "time_scale": 60.0}
        self.assertEqual(rest_plan(pet(), ctx(fast), 0.0)[0]["seconds"], 1.0)


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_survival_tick_actions.py`, replace:

```python
from backend.survival.once import forget_logged
from backend.survival.script import scripted_plan
from backend.survival.tick import Mind, tick_life
```

with:

```python
from backend.survival.brain import BRAIN
from backend.survival.once import forget_logged
from backend.survival.tick import Mind, tick_life
from backend.survival.triggers import new_brain
```

Replace:

```python
    def test_one_tick_can_walk_chop_and_craft(self):
        state = tick_life(self.registry, BORN + 120, scale=1, mind=Mind(plan=scripted_plan))
        self.assertIsNone(state["died_at"])
        self.assertGreaterEqual(state["inventory"].get("planks", 0), 4)
        self.assertIn("air", [change["material"] for change in self.world.blocks_since(0)["changes"]])
        self.assertIn("craft", [event["kind"] for event in self.world.events(50)])
```

with:

```python
    def test_one_tick_of_the_brain_can_walk_and_chop(self):
        self.edit(brain={**new_brain(BORN), "purpose": "gather_wood", "pending": None, "chosen_at": BORN})
        state = tick_life(self.registry, BORN + 120, scale=1, mind=BRAIN)
        self.assertIsNone(state["died_at"])
        self.assertGreaterEqual(state["inventory"].get("oak_log", 0), 1)
        self.assertIn("air", [change["material"] for change in self.world.blocks_since(0)["changes"]])
        self.assertIn("gather_wood", {entry.get("purpose") for entry in state["recent_actions"]})
```

Replace:

```python
    def test_the_worker_runs_the_interim_script(self):
        self.assertIs(mimo_worker.WORKER_MIND.plan, scripted_plan)
```

with:

```python
    def test_the_worker_runs_the_brain(self):
        self.assertIs(mimo_worker.WORKER_MIND, BRAIN)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_choosing.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.choosing'`.

- [ ] **Step 3: Write the chooser**

Create `backend/survival/choosing.py`:

```python
"""Choosing a purpose in the worker, outside the world's write transaction.

After each tick the worker calls `Chooser.poll`. When the active life has a pending trigger:

1. `prepare` reads a snapshot on a read-only connection: the purposes on offer with facts and
   scores, the model payload, and which picker may answer (the route): Jev when TYPESAFE_API_KEY
   is set, else Luna when MIMO_MODEL_API_KEY or OPENAI_API_KEY is set, else utility. Utility also
   answers when a daily cap is spent (MIMO_MAX_DECISIONS_PER_DAY counts Jev and Luna picks,
   MIMO_MAX_LUNA_DECISIONS_PER_DAY every Luna call), and when the last model call was less than
   60 real seconds ago and no vital crossing is waiting. A dawn, hello or discovery choice made by
   a model also gets a Luna reflection as its thought, at most 12 per UTC day.
2. A utility answer is decided and stored at once. A model answer is decided in one background
   thread while the worker keeps ticking; `decide` never raises: a failed call or an answer that
   was not offered falls back to utility, and the error is logged once.
3. `store_choice` saves the answer in a short transaction, unless the life died, nothing is
   pending any more or the pending id changed (the state moved on). Model calls count either way.

While a choice is pending, the brain keeps Mimo on its current plan, or waiting.
"""

from __future__ import annotations

import logging
import os
import random
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from backend.survival.actions import ensure_actions
from backend.survival.care import utc_day
from backend.survival.clock import time_scale
from backend.survival.models import (
    Http, ModelError, ask_jev, ask_luna, jev_configured, luna_configured, luna_reflect, post_json,
)
from backend.survival.once import log_once
from backend.survival.pickers import Option, context_payload, options, thought_for, utility_pick
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.triggers import ensure_brain
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

logger = logging.getLogger(__name__)

MODEL_GAP = 60.0
REFLECTION_CAP = 12
REFLECT_ON = ("dawn", "hello", "discovery")
DECISION_CAP = ("MIMO_MAX_DECISIONS_PER_DAY", 8000)
LUNA_CAP = ("MIMO_MAX_LUNA_DECISIONS_PER_DAY", 64)
EVENTS_SHOWN = 8

Env = Mapping[str, str]


@dataclass(frozen=True)
class Ask:
    pending_id: int
    route: str  # "jev", "luna" or "utility"
    reflect: bool
    options: tuple[Option, ...]
    payload: dict
    asked_at: float


@dataclass(frozen=True)
class Choice:
    purpose: str
    picker: str
    thought: str
    calls: dict  # {"model": n, "luna": n, "reflections": n}
    error: str | None = None


def cap(env: Env, setting: tuple[str, int]) -> int:
    name, default = setting
    try:
        return max(0, int(env.get(name, default)))
    except (TypeError, ValueError):
        return default


def calls_today(brain: dict, now: float) -> dict:
    """Today's model-call counters, starting over on a new UTC day."""
    today = utc_day(now)
    if brain["calls"].get("day") != today:
        brain["calls"] = {"day": today, "model": 0, "luna": 0, "reflections": 0}
    return brain["calls"]


def route_for(brain: dict, now: float, env: Env) -> str:
    """Who may answer the pending choice: "jev", "luna" or "utility"."""
    counters = calls_today(brain, now)
    if counters["model"] >= cap(env, DECISION_CAP):
        return "utility"
    if not brain["pending"]["urgent"] and brain["last_call_at"] is not None and now - brain["last_call_at"] < MODEL_GAP:
        return "utility"
    if jev_configured(env):
        return "jev"
    if luna_configured(env) and counters["luna"] < cap(env, LUNA_CAP):
        return "luna"
    return "utility"


def reflect_for(brain: dict, route: str, now: float, env: Env) -> bool:
    """Whether Luna adds a reflection to a model's choice: dawn, hello or discovery, within the caps."""
    if route == "utility" or not luna_configured(env):
        return False
    if not any(reason in REFLECT_ON for reason in brain["pending"]["reasons"]):
        return False
    counters = calls_today(brain, now)
    luna_after_pick = counters["luna"] + (1 if route == "luna" else 0)
    return counters["reflections"] < REFLECTION_CAP and luna_after_pick < cap(env, LUNA_CAP)


def prepare(world: SurvivalWorld, now: float, scale: float, env: Env) -> Ask | None:
    """A read-only snapshot of the pending choice, or None when nothing is pending."""
    with world.connect() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        ensure_actions(state)  # a world the worker has not ticked yet has no action fields
        brain = ensure_brain(state)
        if brain["pending"] is None:
            return None
        s = from_db(db, state, now, scale)
        choices = options(s)
        events = [{"text": row[0]} for row in
                  db.execute("SELECT text FROM mimo_events ORDER BY id DESC LIMIT ?", (EVENTS_SHOWN,)).fetchall()]
        payload = context_payload(s, events)
    if not choices:
        return None
    route = route_for(brain, now, env)
    return Ask(brain["pending"]["id"], route, reflect_for(brain, route, now, env), tuple(choices), payload, now)


def decide(ask: Ask, env: Env, http: Http, rng: random.Random) -> Choice:
    """Answer an Ask. Never raises: model failures fall back to the utility picker."""
    calls = {"model": 0, "luna": 0, "reflections": 0}
    choices, errors = list(ask.options), []
    purpose, picker = None, "utility"
    if ask.route in ("jev", "luna"):
        calls["model"] += 1
        if ask.route == "luna":
            calls["luna"] += 1
        try:
            purpose = (ask_jev if ask.route == "jev" else ask_luna)(ask.payload, choices, env, http)
            picker = ask.route
        except Exception as error:
            errors.append(f"{ask.route}: {error}")
    if purpose is None:
        purpose = utility_pick(choices, rng)
    thought = thought_for(purpose, rng)
    if ask.reflect and picker != "utility":
        calls["luna"] += 1
        calls["reflections"] += 1
        option = next(option for option in choices if option.name == purpose)
        try:
            thought = luna_reflect(ask.payload, option, env, http)
        except Exception as error:
            errors.append(f"reflection: {error}")
    return Choice(purpose, picker, thought, calls, "; ".join(errors) or None)


def apply_choice(state: dict, choice: Choice, now: float) -> None:
    """Make the choice the current purpose. A new purpose drops the old plan (or, during a reflex,
    the steps the reflex set aside) and ends a wait so the next tick plans at once."""
    brain = ensure_brain(state)
    changed = choice.purpose != brain["purpose"]
    brain.update(pending=None, picker=choice.picker, chosen_at=now)
    if changed:
        brain.update(purpose=choice.purpose, batches=0, replans=0, planned_at=None,
                     handled_failure=state.get("last_failure"))
        if brain["reflex"] is not None:
            brain["set_aside"] = []
        else:
            state["queue"] = []
            if (state.get("action") or {}).get("kind") == "wait":
                state["action"] = None
    state["last_thought"] = choice.thought


def store_choice(world: SurvivalWorld, ask: Ask, choice: Choice, now: float) -> str | None:
    """Save the choice unless the life died or the state moved on. Returns the purpose stored."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        brain = ensure_brain(state)
        counters = calls_today(brain, now)
        for key, count in choice.calls.items():
            counters[key] += count
        if choice.calls["model"] or choice.calls["luna"]:
            brain["last_call_at"] = ask.asked_at
        pending = brain["pending"]
        fresh = pending is not None and pending["id"] == ask.pending_id
        if fresh:
            apply_choice(state, choice, now)
            purpose = PURPOSES.get(choice.purpose)
            phrase = purpose.phrase if purpose else choice.purpose.replace("_", " ")
            log_event(db, now, "purpose", f'{state["name"]} decided to {phrase}. "{choice.thought}"')
        write_state(db, state)
        return choice.purpose if fresh else None


class InlineExecutor:
    """Runs submitted work at once in the calling thread (tests use it instead of a thread)."""

    def submit(self, fn: Callable, *args) -> Future:
        future: Future = Future()
        try:
            future.set_result(fn(*args))
        except BaseException as error:
            future.set_exception(error)
        return future

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        return None


class Chooser:
    """Answers the active life's pending choices, one model call at a time in a background thread."""

    def __init__(self, env: Env | None = None, http: Http = post_json, executor=None,
                 rng: random.Random | None = None, scale: float | None = None):
        self.env = os.environ if env is None else env
        self.http = http
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="mimo-chooser")
        self.rng = rng or random.Random()
        self.scale = scale
        self.future: Future | None = None
        self.asked: tuple[Path, Ask] | None = None

    def poll(self, registry: LifeRegistry, now: float | None = None) -> str | None:
        """Store a finished answer, or start answering a new pending choice. Returns the purpose stored."""
        now = time.time() if now is None else now
        if self.future is not None:
            return self.collect(now)
        life = registry.active_life()
        if life is None:
            return None
        path = registry.world_path(life)
        scale = time_scale() if self.scale is None else self.scale
        ask = prepare(SurvivalWorld(path, read_only=True), now, scale, self.env)
        if ask is None:
            return None
        if ask.route == "utility":
            return self.store(path, ask, decide(ask, self.env, self.http, self.rng), now)
        self.asked = (path, ask)
        self.future = self.executor.submit(decide, ask, self.env, self.http, self.rng)
        return self.collect(now)

    def collect(self, now: float) -> str | None:
        if self.future is None or self.asked is None or not self.future.done():
            return None
        (path, ask), future = self.asked, self.future
        self.future, self.asked = None, None
        return self.store(path, ask, future.result(), now)

    def store(self, path: Path, ask: Ask, choice: Choice, now: float) -> str | None:
        if choice.error:
            log_once(logger, "picker", ModelError(choice.error))
        return store_choice(SurvivalWorld(path), ask, choice, now)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
```

- [ ] **Step 4: Run the brain and the chooser in the worker**

Replace the whole of `backend/survival/script.py` with:

```python
"""M1's sleep rule as steps: the default mind's planner and the fallback when a planner crashes.

rest_plan sleeps at night or when exhausted, and otherwise waits (at most a minute) for
nightfall. The brain (backend.survival.brain) replaced M2's interim stand-in script.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival.clock import is_night
from backend.survival.vitals import EXHAUSTED_BELOW

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

NIGHTFALL = 2400.0
MAX_WAIT = 60.0


def rest_plan(state: dict, context: ActionContext, at: float) -> list[dict]:
    """Sleep at night or when exhausted; otherwise wait (at most a minute) for nightfall."""
    clock = context.clock_at(at)
    night = is_night(clock["phase"])
    if night or state["vitals"]["energy"] < EXHAUSTED_BELOW:
        thought = "It's dark. Time to curl up and sleep." if night else "I'm too tired to keep my eyes open."
        return [{"kind": "sleep", "thought": thought}]
    until_night = (NIGHTFALL - clock["seconds_into_day"]) / clock["time_scale"]
    return [{"kind": "wait", "seconds": max(1.0, min(MAX_WAIT, until_night))}]
```

In `backend/workers/mimo_worker.py`, replace the module docstring:

```python
"""Run the active survival life independently of all browsers.

Run with: python -m backend.workers.mimo_worker
Keep exactly one worker running against a persistent MIMO_DATA_DIR. Each tick brings the
active life up to now (timed actions, vitals, death). The retired legacy world at
MIMO_DB_PATH is no longer ticked; live_mimo.run_tick stays only for reading old worlds.
"""
```

with:

```python
"""Run the active survival life independently of all browsers.

Run with: python -m backend.workers.mimo_worker
Keep exactly one worker running against a persistent MIMO_DATA_DIR. Each tick brings the
active life up to now (timed actions, vitals, death) with the brain; then the Chooser answers a
pending purpose trigger outside the tick's transaction (backend.survival.choosing). The retired
legacy world at MIMO_DB_PATH is no longer ticked; live_mimo.run_tick stays only for reading old
worlds.
"""
```

Replace:

```python
from backend.survival.registry import LifeRegistry, data_dir
from backend.survival.script import scripted_plan
from backend.survival.tick import RESTING, Mind, tick_life
from backend.survival.world import WorldMissing

logger = logging.getLogger("mimo_worker")
stopping = False

# What runs the pet. The brain (M3 Task 13) replaces this interim script.
WORKER_MIND = Mind(plan=scripted_plan)
```

with:

```python
from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser
from backend.survival.registry import LifeRegistry, data_dir
from backend.survival.tick import RESTING, Mind, tick_life
from backend.survival.world import WorldMissing

logger = logging.getLogger("mimo_worker")
stopping = False

# What runs the pet: reflexes, purposes and the planner.
WORKER_MIND = BRAIN
```

Replace:

```python
def run_once(registry: LifeRegistry, previous: str | None, timestamp: float | None = None,
             mind: Mind = RESTING) -> str:
    """Tick the active life once. Logs a line when the pet's status changes and returns it.

    `mind` defaults to the plain sleep rule; `main` passes WORKER_MIND.
    """
    state = tick_life(registry, timestamp, mind=mind)
```

with:

```python
def run_once(registry: LifeRegistry, previous: str | None, timestamp: float | None = None,
             mind: Mind = RESTING, chooser: Chooser | None = None) -> str:
    """Tick the active life once, then let the chooser answer a pending purpose trigger. Logs a
    line when the pet's status changes and returns it.

    `mind` defaults to the plain sleep rule and `chooser` to none; `main` passes WORKER_MIND and
    a Chooser.
    """
    state = tick_life(registry, timestamp, mind=mind)
    if chooser is not None and state is not None and state["died_at"] is None:
        chooser.poll(registry, timestamp)
```

Replace:

```python
    registry: LifeRegistry | None = None
    previous: str | None = None
    last_data_error: str | None = None
    while not stopping:
        try:
            if registry is None:
                registry = LifeRegistry()
            previous = run_once(registry, previous, mind=WORKER_MIND)
```

with:

```python
    registry: LifeRegistry | None = None
    previous: str | None = None
    last_data_error: str | None = None
    chooser = Chooser()
    while not stopping:
        try:
            if registry is None:
                registry = LifeRegistry()
            previous = run_once(registry, previous, mind=WORKER_MIND, chooser=chooser)
```

and replace:

```python
        time.sleep(delay)
    logger.info("Survival worker stopped")
```

with:

```python
        time.sleep(delay)
    chooser.close()
    logger.info("Survival worker stopped")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_choosing.py" -v`
Expected: `Ran 9 tests` … `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 326 tests` … `OK` (9 new; the 5 `scripted_plan` tests are gone).

Run: `grep -rn "scripted_plan\|WORKER_PLANNER" backend`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add backend/survival/choosing.py backend/survival/script.py backend/workers/mimo_worker.py backend/tests/test_survival_choosing.py backend/tests/test_survival_script.py backend/tests/test_survival_tick_actions.py
git commit -m "feat: choose purposes in the worker outside the tick and retire the interim script" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Stream the brain from `/api/mimo`

**Files:**
- Modify: `backend/survival/snapshot.py`
- Test: `backend/tests/test_survival_api.py`

**Interfaces:**
- Consumes: `state["brain"]` (Task 5 keys), `triggers.new_brain`.
- Produces: `survival_view` (so `/api/mimo`, `/api/lives/{id}` and the memorial's last state) adds `purpose: str | None`, `reflex: str | None`, `picker: "jev" | "luna" | "utility" | None` and `choosing: bool` (True while a choice is pending, and for a world whose brain has not started yet). `action` and `recent_actions` keep their M2 shapes. `ROUTINE_EVENTS` gains `purpose` and `reflex`, so memorials list discoveries, falls and deaths rather than every choice.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_survival_api.py`, replace:

```python
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
```

with:

```python
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import notable
from backend.survival.tick import tick_life
from backend.survival.triggers import new_brain
```

and add at the end of `SurvivalApiTests`:

```python
    def test_the_brain_is_streamed(self):
        hatch_egg()
        fresh = get_mimo()
        self.assertEqual((fresh["purpose"], fresh["reflex"], fresh["picker"], fresh["choosing"]), (None, None, None, True))
        world = self.active_world()
        with world.transaction() as db:
            state = read_state(db)
            state["brain"] = {**new_brain(state["born_at"]), "purpose": "gather_wood", "picker": "jev",
                              "reflex": "head_home", "pending": None}
            write_state(db, state)
        mimo = get_mimo()
        self.assertEqual((mimo["purpose"], mimo["reflex"], mimo["picker"], mimo["choosing"]),
                         ("gather_wood", "head_home", "jev", False))

    def test_memorials_skip_choices_and_reflexes(self):
        events = [{"kind": kind, "text": kind} for kind in ("purpose", "reflex", "found", "discovered", "trapped")]
        self.assertEqual([event["kind"] for event in notable(events)], ["found", "discovered", "trapped"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_api.py"`
Expected: `KeyError: 'purpose'` and a failure in `test_memorials_skip_choices_and_reflexes`.

- [ ] **Step 3: Add the brain fields**

In `backend/survival/snapshot.py`, replace:

```python
ROUTINE_EVENTS = frozenset({"sleep", "wake", "hello", "error", "rest", "block", "craft", "smelt",
                            "explore", "owner", "plan"})
```

with:

```python
ROUTINE_EVENTS = frozenset({"sleep", "wake", "hello", "error", "rest", "block", "craft", "smelt",
                            "explore", "owner", "plan", "purpose", "reflex"})
```

Add this function after `action_view`:

```python
def brain_view(brain: dict | None) -> dict:
    """What Mimo is up to: its purpose, a running reflex, who chose, and whether it is choosing.
    A world whose brain has not started yet is about to choose."""
    if brain is None:
        return {"purpose": None, "reflex": None, "picker": None, "choosing": True}
    return {"purpose": brain.get("purpose"), "reflex": brain.get("reflex"), "picker": brain.get("picker"),
            "choosing": brain.get("pending") is not None}
```

In `survival_view`, replace:

```python
        "action": action_view(state.get("action")),
        "recent_actions": state.get("recent_actions", []),
    }
```

with:

```python
        "action": action_view(state.get("action")),
        "recent_actions": state.get("recent_actions", []),
        **brain_view(state.get("brain")),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_api.py" -v`
Expected: `OK`.

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 328 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/survival/snapshot.py backend/tests/test_survival_api.py
git commit -m "feat: stream Mimo's purpose, reflex and picker from /api/mimo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Viewer: purpose, thought and replay

**Files:**
- Create: `frontend/src/survival/replay.ts`, `frontend/src/survival/replay.test.ts`
- Modify: `frontend/src/survival/types.ts`, `frontend/src/survival/hud.ts`, `frontend/src/survival/hud.test.ts`, `frontend/src/survival/SurvivalHud.tsx`, `frontend/src/survival/SurvivalPet.tsx`, `frontend/src/survival/ActionEffects.tsx`, `frontend/src/survival/WorldCanvas.tsx`

**Interfaces:**
- Consumes: `/api/mimo` from Task 14 (`purpose`, `reflex`, `picker`, `choosing`; recent entries with `path`, `code`, `purpose`, `result: "interrupted"`); `poseAt`, `focusPoint`, `moveFor`, `crackStage` (M2).
- Produces:
  - `types.ts`: `PickerName = 'jev' | 'luna' | 'utility'`; `FinishedAction.result: 'done' | 'failed' | 'interrupted'`, `FinishedAction.path?: PathPoint[]`, `code?: string`, `purpose?: string`; `SurvivalState.purpose: string | null`, `reflex: string | null`, `picker: PickerName | null`, `choosing: boolean`.
  - `hud.ts`: `purposeText(state: Pick<SurvivalState, 'purpose' | 'reflex' | 'choosing'>): string`.
  - `replay.ts`: `REPLAY_DELAY = 1.5`; `interface Replay { step: MimoAction | null; rest: Point }`; `replayAt(action: MimoAction | null, recent: FinishedAction[], position: Point, t: number): Replay`.
  - `SurvivalPet` takes `recent?: FinishedAction[]`; `WorldCanvas` gives `SurvivalPet`, `ActionEffects` and the camera the replay time (server time − 1.5 s). The HUD shows the purpose line above the step line; the thought line is `last_thought` as before.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/replay.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { poseAt } from './motion'
import { REPLAY_DELAY, replayAt } from './replay'
import type { FinishedAction, MimoAction } from './types'

const server = { x: 9, y: 1, z: 9 }
const shortWalk: FinishedAction = {
  kind: 'walk', started_at: 10, ended_at: 10.6, result: 'done',
  path: [{ x: 0, y: 1, z: 0, at: 10 }, { x: 1, y: 1, z: 0, at: 10.3 }, { x: 2, y: 1, z: 0, at: 10.6 }],
}
const mine: MimoAction = { kind: 'mine', started_at: 11, ends_at: 13, target: { x: 3, y: 1, z: 0 }, block: 'oak_log' }

describe('replayAt', () => {
  it('draws Mimo a moment behind the server', () => {
    expect(REPLAY_DELAY).toBe(1.5)
  })

  it('replays a short walk that started and ended between two polls', () => {
    const { step, rest } = replayAt(mine, [shortWalk], server, 10.3)
    expect(step).toMatchObject({ kind: 'walk', started_at: 10, ends_at: 10.6 })
    expect(poseAt(step, rest, 10.45).x).toBeCloseTo(1.5)
  })

  it('stands where the last path ended between steps', () => {
    expect(replayAt(mine, [shortWalk], server, 10.8)).toEqual({ step: null, rest: { x: 2, y: 1, z: 0 } })
  })

  it('plays the current step once its time comes', () => {
    expect(replayAt(mine, [shortWalk], server, 11.5)).toEqual({ step: mine, rest: { x: 2, y: 1, z: 0 } })
  })

  it('waits on the first cell of a walk that has not started yet', () => {
    const walk: MimoAction = {
      kind: 'walk', started_at: 20, ends_at: 20.3,
      path: [{ x: 5, y: 2, z: 5, at: 20 }, { x: 6, y: 2, z: 5, at: 20.3 }],
    }
    expect(replayAt(walk, [], server, 19)).toEqual({ step: null, rest: { x: 5, y: 2, z: 5 } })
  })

  it('rests on the last cell an interrupted walk reached', () => {
    const cut: FinishedAction = { ...shortWalk, ended_at: 10.4, result: 'interrupted', reason: 'head_home' }
    expect(replayAt(null, [cut], server, 12).rest).toEqual({ x: 1, y: 1, z: 0 })
  })

  it('falls back to the server position when no path says', () => {
    const craft: FinishedAction = { kind: 'craft', started_at: 1, ended_at: 2, result: 'done', recipe: 'planks' }
    expect(replayAt(null, [craft], server, 5)).toEqual({ step: null, rest: server })
  })
})
```

In `frontend/src/survival/hud.test.ts`, replace:

```ts
import { actionText, careLabel, causeText, clockTime, dayLabel, lifeLine, statusText, vitalBars, workerOnline } from './hud'
```

with:

```ts
import {
  actionText, careLabel, causeText, clockTime, dayLabel, lifeLine, purposeText, statusText, vitalBars, workerOnline,
} from './hud'
```

and add at the end of the file:

```ts
describe('purposeText', () => {
  it('names a reflex first, then the purpose, then whether Mimo is choosing', () => {
    expect(purposeText({ purpose: 'gather_wood', reflex: 'head_home', choosing: false })).toBe('Hurrying home before dark')
    expect(purposeText({ purpose: 'gather_wood', reflex: null, choosing: true })).toBe('Gathering wood')
    expect(purposeText({ purpose: 'build_shelter', reflex: null, choosing: false })).toBe('Build shelter')
    expect(purposeText({ purpose: null, reflex: null, choosing: true })).toBe('Deciding what to do')
    expect(purposeText({ purpose: null, reflex: null, choosing: false })).toBe('Taking it easy')
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test`
Expected: failures: `Failed to resolve import "./replay"` and `purposeText is not a function`.

- [ ] **Step 3: Add the brain fields to the types**

In `frontend/src/survival/types.ts`, replace:

```ts
/** A step that finished, oldest first. Waits are left out. */
export interface FinishedAction {
  kind: ActionKind
  started_at: number
  ended_at: number
  result: 'done' | 'failed'
  target?: Point
  block?: string
  item?: string
  recipe?: string
  reason?: string
}
```

with:

```ts
/** A step that finished, oldest first. Waits are left out. */
export interface FinishedAction {
  kind: ActionKind
  started_at: number
  ended_at: number
  /** Interrupted: a reflex or a fall cut it short (`reason` names which). */
  result: 'done' | 'failed' | 'interrupted'
  target?: Point
  block?: string
  item?: string
  recipe?: string
  reason?: string
  /** Why it failed: no_path, out_of_reach, gone, missing_item, blocked or bad_step. */
  code?: string
  /** The purpose or reflex that planned it. */
  purpose?: string
  /** Walks, swims and falls keep their timed path (the newest few only), for replay. */
  path?: PathPoint[]
}

export type PickerName = 'jev' | 'luna' | 'utility'
```

Replace:

```ts
  action: MimoAction | null
  recent_actions: FinishedAction[]
}

export interface AliveResponse extends SurvivalState {
```

with:

```ts
  action: MimoAction | null
  recent_actions: FinishedAction[]
  /** The purpose Mimo is working on, like "gather_wood", or null. */
  purpose: string | null
  /** A reflex that took over, like "head_home", or null. */
  reflex: string | null
  /** Who chose the purpose. */
  picker: PickerName | null
  /** True while Mimo waits for its next choice. */
  choosing: boolean
}

export interface AliveResponse extends SurvivalState {
```

- [ ] **Step 4: Write the purpose line and the replay**

In `frontend/src/survival/hud.ts`, replace:

```ts
import type { ActionKind, CareKind, ClockPhase, LifeRow, MimoAction, VitalName, Vitals } from './types'
```

with:

```ts
import type { ActionKind, CareKind, ClockPhase, LifeRow, MimoAction, SurvivalState, VitalName, Vitals } from './types'
```

and add after the `actionText` function:

```ts
const PURPOSE_TEXT: Record<string, string> = {
  gather_wood: 'Gathering wood', gather_stone: 'Digging for stone', mine_ore: 'Mining ore',
  craft_tools: 'Making a tool', explore: 'Exploring', go_home: 'Going home', sleep: 'Settling down to sleep',
  rest: 'Resting', eat: 'Having a meal', escape: 'Digging out of a pit',
}
const REFLEX_TEXT: Record<string, string> = {
  surface: 'Swimming for air!', avoid_drop: 'Backing away from a drop', eat_now: 'Eating in a hurry',
  warm_up: 'Getting warm', head_home: 'Hurrying home before dark', collapse: 'Collapsed from exhaustion',
  flee: 'Running away!',
}

function sentence(name: string): string {
  const words = name.replaceAll('_', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** What Mimo is up to in plain words: a reflex first, then its purpose, or that it is choosing. */
export function purposeText(state: Pick<SurvivalState, 'purpose' | 'reflex' | 'choosing'>): string {
  if (state.reflex) return REFLEX_TEXT[state.reflex] ?? sentence(state.reflex)
  if (state.purpose) return PURPOSE_TEXT[state.purpose] ?? sentence(state.purpose)
  return state.choosing ? 'Deciding what to do' : 'Taking it easy'
}
```

Create `frontend/src/survival/replay.ts`:

```ts
import type { FinishedAction, MimoAction, PathPoint, Point } from './types'

/**
 * The viewer draws Mimo this many seconds behind server time. The server can start and finish a
 * short step between two polls; with the pet drawn a moment late, that step is still in
 * `recent_actions` when its time comes, so it plays out instead of Mimo jumping.
 */
export const REPLAY_DELAY = 1.5

export interface Replay {
  /** The step Mimo was doing at the replay time, or null between steps. */
  step: MimoAction | null
  /** Where Mimo stood when no path moves it. */
  rest: Point
}

function asStep(entry: FinishedAction): MimoAction {
  const step: MimoAction = { kind: entry.kind, started_at: entry.started_at, ends_at: entry.ended_at }
  if (entry.path) step.path = entry.path
  if (entry.target) step.target = entry.target
  if (entry.block) step.block = entry.block
  if (entry.item) step.item = entry.item
  if (entry.recipe) step.recipe = entry.recipe
  return step
}

function startOf(path: PathPoint[] | undefined): Point | null {
  return path && path.length > 0 ? { x: path[0].x, y: path[0].y, z: path[0].z } : null
}

/** The last cell a path reached by `end` (a cut walk stops partway). */
function reachedBy(path: PathPoint[], end: number): Point {
  let spot = path[0]
  for (const point of path) if (point.at <= end) spot = point
  return { x: spot.x, y: spot.y, z: spot.z }
}

/**
 * The step to draw at server time `t`, from the finished steps (oldest first) and the current
 * one, and where Mimo stood between steps: the end of the last path before `t`, else the start of
 * the next walk, else the server's `position`.
 */
export function replayAt(action: MimoAction | null, recent: FinishedAction[], position: Point, t: number): Replay {
  let rest: Point | null = null
  for (const entry of recent) {
    if (entry.started_at > t) return { step: null, rest: rest ?? startOf(entry.path) ?? position }
    if (t < entry.ended_at) return { step: asStep(entry), rest: rest ?? position }
    if (entry.path && entry.path.length > 0) rest = reachedBy(entry.path, entry.ended_at)
  }
  if (action && action.started_at <= t) return { step: action, rest: rest ?? position }
  return { step: null, rest: rest ?? startOf(action?.path) ?? position }
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test`
Expected: `Tests  151 passed (151)`.

- [ ] **Step 6: Draw the pet and its effects 1.5 s behind the server**

In `frontend/src/survival/SurvivalPet.tsx`, replace:

```tsx
import { poseAt, turnToward } from './motion'
import type { MimoAction, Point } from './types'
```

with:

```tsx
import { poseAt, turnToward } from './motion'
import { replayAt } from './replay'
import type { FinishedAction, MimoAction, Point } from './types'
```

Replace:

```tsx
const BAR: [number, number, number] = [0.24, 0.05, 0.05]
```

with:

```tsx
const BAR: [number, number, number] = [0.24, 0.05, 0.05]
const NO_STEPS: FinishedAction[] = []
```

Replace:

```tsx
/**
 * The survival pet, driven by the server's current step: it follows a walk's timed path, turns to
 * face where it goes or what it works on, and plays the step's animation. Cheap on phones: no
 * React state changes per frame, a handful of meshes, and all per-frame work in one useFrame.
 */
export default function SurvivalPet({ action, position, now, onPetClick, hopSignal = 0, children }: {
  action: MimoAction | null
  /** The server's position for the pet, used when the step has no path. */
  position: Point
  /** Server time now, in seconds. */
  now: () => number
```

with:

```tsx
/**
 * The survival pet, driven by the step it was doing at `now` (the current step or a finished one,
 * see replay.ts): it follows a walk's timed path, turns to face where it goes or what it works on,
 * and plays the step's animation. Cheap on phones: no React state changes per frame, a handful of
 * meshes, and all per-frame work in one useFrame.
 */
export default function SurvivalPet({ action, recent = NO_STEPS, position, now, onPetClick, hopSignal = 0, children }: {
  action: MimoAction | null
  /** Finished steps, oldest first, so short steps between polls still play out. */
  recent?: FinishedAction[]
  /** The server's position for the pet, used when no path says where it stands. */
  position: Point
  /** The time to draw, in server seconds (WorldCanvas passes server time minus REPLAY_DELAY). */
  now: () => number
```

Replace:

```tsx
    const t = now()
    const pose = poseAt(action, position, t)
    const move = moveFor(action, t, pose.swimming)
    const stepTime = action ? Math.max(0, t - action.started_at) : 0
```

with:

```tsx
    const t = now()
    const { step, rest } = replayAt(action, recent, position, t)
    const pose = poseAt(step, rest, t)
    const move = moveFor(step, t, pose.swimming)
    const stepTime = step ? Math.max(0, t - step.started_at) : 0
```

In `frontend/src/survival/ActionEffects.tsx`, replace:

```tsx
import { poseAt } from './motion'
```

with:

```tsx
import { poseAt } from './motion'
import { replayAt } from './replay'
```

Replace:

```tsx
  /** Server time now, in seconds. */
  now: () => number
}) {
  const effects = useMemo(() => blockEffects(action, recent), [action, recent])
```

with:

```tsx
  /** The time to draw, in server seconds (behind the server by REPLAY_DELAY, like the pet). */
  now: () => number
}) {
  const effects = useMemo(() => blockEffects(action, recent), [action, recent])
```

Replace:

```tsx
    const t = now()
    // Steps that ended before the page opened are not replayed.
    const since = (openedAt.current ??= t - 1)

    // Cracks grow on the block being mined until block sync removes it.
    const crackMesh = crack.current
    const crackMat = crackMaterial.current
    if (crackMesh && crackMat) {
      const stage = crackStage(action, t)
      const texture = textures.current[stage]
      const cell = action?.target
      const standing = action?.block !== undefined && cell !== undefined
        && store.getBlock(cell.x, cell.y, cell.z) === blockId(action.block)
```

with:

```tsx
    const t = now()
    // Steps that ended before the page opened are not replayed.
    const since = (openedAt.current ??= t - 1)
    const { step, rest } = replayAt(action, recent, position, t)

    // Cracks grow on the block being mined until block sync removes it.
    const crackMesh = crack.current
    const crackMat = crackMaterial.current
    if (crackMesh && crackMat) {
      const stage = crackStage(step, t)
      const texture = textures.current[stage]
      const cell = step?.target
      const standing = step?.block !== undefined && cell !== undefined
        && store.getBlock(cell.x, cell.y, cell.z) === blockId(step.block)
```

Replace:

```tsx
        const pet = poseAt(action, position, t)
```

with:

```tsx
        const pet = poseAt(step, rest, t)
```

In `frontend/src/survival/WorldCanvas.tsx`, replace:

```tsx
import { focusPoint } from './motion'
```

with:

```tsx
import { focusPoint } from './motion'
import { REPLAY_DELAY, replayAt } from './replay'
```

Replace:

```tsx
/** Without a server clock (archives) the pet has no step and stands still. */
const NO_TIME = () => 0
const NO_ACTIONS: FinishedAction[] = []
```

with:

```tsx
const NO_ACTIONS: FinishedAction[] = []
```

Replace:

```tsx
  // The same interpolated point SurvivalPet renders at, so the camera tracks the walk instead of
  // snapping only when the server's polled position changes.
  const focusAt = useCallback(() => focusPoint(action, position, serverTime ? serverTime() : 0),
    [action, position, serverTime])
```

with:

```tsx
  // The pet is drawn REPLAY_DELAY seconds behind the server, so a step that started and ended
  // between two polls still plays out. Without a server clock (archives) it stands still.
  const replayTime = useCallback(() => (serverTime ? serverTime() - REPLAY_DELAY : 0), [serverTime])
  // The same interpolated point SurvivalPet renders at, so the camera tracks the walk instead of
  // snapping only when the server's polled position changes.
  const focusAt = useCallback(() => {
    const t = replayTime()
    const { step, rest } = replayAt(action, recentActions, position, t)
    return focusPoint(step, rest, t)
  }, [action, recentActions, position, replayTime])
```

Replace:

```tsx
          <SurvivalPet action={action} position={position} now={serverTime ?? NO_TIME} onPetClick={onPetClick} hopSignal={hopSignal}>
```

with:

```tsx
          <SurvivalPet action={action} recent={recentActions} position={position} now={replayTime} onPetClick={onPetClick} hopSignal={hopSignal}>
```

Replace:

```tsx
          {serverTime && <ActionEffects store={store} action={action} recent={recentActions} position={position} now={serverTime} />}
```

with:

```tsx
          {serverTime && <ActionEffects store={store} action={action} recent={recentActions} position={position} now={replayTime} />}
```

- [ ] **Step 7: Show the purpose in the HUD**

In `frontend/src/survival/SurvivalHud.tsx`, replace:

```tsx
import { actionText, careLabel, clockTime, dayLabel, vitalBars, type VitalLevel } from './hud'
```

with:

```tsx
import { actionText, careLabel, clockTime, dayLabel, purposeText, vitalBars, type VitalLevel } from './hud'
```

Replace:

```tsx
          <p className="mt-2 text-xs text-[#54726e]">
            <span className={online ? 'text-[#3c9a73]' : 'text-[#c76e5c]'}>●</span> {online ? actionText(state.action, state.status) : 'Worker offline'}
          </p>
```

with:

```tsx
          <p className="mt-2 text-sm font-medium leading-5 text-[#315e58]">{purposeText(state)}</p>
          <p className="mt-0.5 text-xs text-[#54726e]">
            <span className={online ? 'text-[#3c9a73]' : 'text-[#c76e5c]'}>●</span> {online ? actionText(state.action, state.status) : 'Worker offline'}
          </p>
```

- [ ] **Step 8: Build, lint and test**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival`
Expected: `Tests  151 passed (151)`, the build succeeds, eslint prints nothing.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/survival/types.ts frontend/src/survival/hud.ts frontend/src/survival/hud.test.ts frontend/src/survival/replay.ts frontend/src/survival/replay.test.ts frontend/src/survival/SurvivalHud.tsx frontend/src/survival/SurvivalPet.tsx frontend/src/survival/ActionEffects.tsx frontend/src/survival/WorldCanvas.tsx
git commit -m "feat: show Mimo's purpose and replay its steps 1.5 s behind the server" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Manual check at 60× and the README

This task is for the controller. It runs Docker against a scratch volume and a separately tagged image; the real `pets_mimo_data` volume is never mounted. At `MIMO_TIME_SCALE=60` a game day lasts 60 real seconds (40 s of day, 20 s of night), and `MIMO_ACTION_SCALE=60` makes the steps 60 times shorter, so a day of purposes fits in that minute. If a check fails, fix the code in the task that owns it, re-run that task's tests, and repeat the check.

**Files:**
- Modify: `README.md`, `.env.example`, `docker-compose.yml`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 328 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival`
Expected: `Tests  151 passed (151)`, the build succeeds, eslint prints nothing.

- [ ] **Step 2: Build a scratch image and start a scratch world at 60×**

```bash
docker build -f backend/Dockerfile -t mimo-m3-check .
docker volume create mimo_m3_check
docker run --rm -v mimo_m3_check:/data -e MIMO_DB_PATH=/data/mimo.sqlite3 mimo-m3-check \
  python -c "from backend.services.live_mimo import MimoStore; MimoStore(); print('scratch legacy world ready')"
docker run -d --name mimo-m3-api -p 127.0.0.1:8001:8000 -v mimo_m3_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 mimo-m3-check
docker run -d --name mimo-m3-worker -v mimo_m3_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 -e MIMO_ACTION_SCALE=60 \
  -e MIMO_TICK_SECONDS=1 mimo-m3-check python -m backend.workers.mimo_worker
```

Expected: `scratch legacy world ready`, then two container ids. No model key is passed, so the utility picker chooses.

After a few seconds, hatch the egg:

```bash
curl -s -X POST http://127.0.0.1:8001/api/lives/hatch | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['life']['id'], d['life']['name'])"
```

Expected: `2 <name>`.

- [ ] **Step 3: Keep a feed snippet and a brain snippet ready**

Save these in your scratchpad directory (not in the repo). `feed.sh`, run whenever Hunger or Health gets low:

```bash
docker exec -i mimo-m3-api python - <<'EOF'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    state["vitals"].update(hunger=100.0, health=100.0, air=100.0)
    write_state(db, state)
print("fed")
EOF
```

`brain.sh`, which prints the brain's recent story and its current state:

```bash
docker exec -i mimo-m3-api python - <<'EOF'
from backend.survival.memory import places
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()), read_only=True)
for event in reversed(world.events(80)):
    if event["kind"] in ("purpose", "reflex", "found", "discovered", "trapped", "plan", "sleep", "wake", "craft"):
        print(event["kind"], "|", event["text"])
brain = world.state()["brain"]
print("now:", brain["purpose"], "| reflex:", brain["reflex"], "| picker:", brain["picker"], "| calls:", brain["calls"])
with world.connect() as db:
    print("places:", [(place["kind"], place["note"]) for place in places(db)][:12])
EOF
```

Expected: `fed`; the brain snippet prints event lines and a `now:` line.

- [ ] **Step 4: Start the viewer against the scratch API**

Stop any other dev server on port 5173 first (the API only allows CORS from port 5173).

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8001 npm run dev -- --port 5173 --strictPort
```

Open `http://127.0.0.1:5173/preview?debug` in the Browser pane.

- [ ] **Step 5: Check the API stream**

```bash
curl -s http://127.0.0.1:8001/api/mimo | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['purpose'], d['reflex'], d['picker'], d['choosing'], d['status'], d['last_thought'])"
```

Expected (by day): a purpose such as `gather_wood`, `None`, `utility`, `False`, a status such as `walking` or `mining`, and a thought from that purpose's templates.

- [ ] **Step 6: Watch the utility picker drive a day**

Watch two or three game days (2–3 real minutes), running `sh <scratchpad>/brain.sh` every 30 seconds and the feed snippet when needed. Confirm:

- The events go through `decided to gather wood`, `crafted planks`, `crafted crafting table`, `crafted wooden pickaxe` (a table appears beside the pet and is mined back), then `decided to gather stone`: the pet digs a staircase into the ground, two blocks per stair.
- Within the first day or two, `found a sheltered spot and made it home` appears (usually in the staircase), `spotted coal ore` or `spotted iron ore` appear, and `places:` lists `home` and `ore` entries.
- Later days show `craft tools` again (a stone pickaxe) and `mine ore` when ore was seen.
- Near dusk the pet goes home (`decided to go home`, or the reflex `hurried home before dark` if it was working outdoors) or rests, and at night `decided to sleep` and `fell asleep`; at dawn `woke up` and a new choice.
- The HUD shows the purpose line (for example `Gathering wood`) above the step line (`Mining oak log`) and the latest thought in italics.
- Short steps play out instead of jumping: the pet hops cell by cell through short walks and swings at each block, drawn about 1.5 s behind the server.
- `docker logs mimo-m3-worker 2>&1 | tail -5` shows status lines and no repeating tracebacks.

- [ ] **Step 7: A reflex interrupts a plan**

While the HUD shows `Walking` by day, run:

```bash
docker exec -i mimo-m3-api python - <<'EOF'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    state["vitals"]["energy"] = 5.0
    write_state(db, state)
print("exhausted")
EOF
```

Confirm: within a second or two the HUD reads `Collapsed from exhaustion` and the pet lies down with z's; `curl -s http://127.0.0.1:8001/api/mimo | python3 -c "import json,sys; print([(a['kind'], a['result'], a.get('reason')) for a in json.load(sys.stdin)['recent_actions'][-3:]])"` shows `('walk', 'interrupted', 'collapse')`; the brain snippet shows `reflex | <name> collapsed from exhaustion.`. When it wakes, the brain snippet shows a new `decided to ...` line and the pet carries on.

- [ ] **Step 8: A trapped pet digs out**

By day, run:

```bash
docker exec -i mimo-m3-api python - <<'EOF'
from backend.services.block_table import write_block
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import ensure_brain
from backend.survival.world import SurvivalWorld, read_state, write_state

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
with world.transaction() as db:
    state = read_state(db)
    x, y, z = (round(state["position"][key]) for key in ("x", "y", "z"))
    for dy in range(1, 5):
        write_block(db, x, y - dy, z, "air")
    state["position"]["y"] = float(y - 4)
    state["inventory"]["wooden_pickaxe"] = state["inventory"].get("wooden_pickaxe", 0) + 1
    state["action"], state["queue"] = None, []
    ensure_brain(state).update(purpose="explore", pending=None, batches=0, replans=0, planned_at=None)
    write_state(db, state)
print("pit at", x, y - 4, z)
EOF
```

Confirm: after two failed walks (`recent_actions` shows two `walk` entries with result `failed` and code `no_path`), the brain snippet shows `trapped | <name> is stuck in a pit and starts digging out.`, the HUD reads `Digging out of a pit`, and the pet mines a staircase up out of the shaft and walks away.

- [ ] **Step 9: A short, capped Jev check**

Skip this step if `TYPESAFE_API_KEY` is not set in your shell (say so in the report). The key is passed through from the environment, never written to a file. The cap stops Jev after 3 calls today.

```bash
docker rm -f mimo-m3-worker
docker run -d --name mimo-m3-worker -v mimo_m3_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 -e MIMO_ACTION_SCALE=60 \
  -e MIMO_TICK_SECONDS=1 -e TYPESAFE_API_KEY -e MIMO_MAX_DECISIONS_PER_DAY=3 -e MIMO_MAX_LUNA_DECISIONS_PER_DAY=0 \
  mimo-m3-check python -m backend.workers.mimo_worker
```

Wait about 4 minutes, running the brain snippet each minute. Confirm: at least one `now:` line shows `picker: jev`; `calls` never shows `model` above 3; choices between Jev calls (inside the 60 s gap) show `picker: utility`; the pet keeps moving while a call is in flight; and `docker logs mimo-m3-worker 2>&1 | grep -c "crashed"` stays small (one line per distinct error, not one per tick). Then put the utility-only worker back:

```bash
docker rm -f mimo-m3-worker
docker run -d --name mimo-m3-worker -v mimo_m3_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 -e MIMO_ACTION_SCALE=60 \
  -e MIMO_TICK_SECONDS=1 mimo-m3-check python -m backend.workers.mimo_worker
```

- [ ] **Step 10: Check the phone layout**

Resize the Browser pane to the mobile preset and reload. Confirm the HUD shows the purpose line, the step line and the thought without overlapping the vitals, and the pet still animates. Reset the viewport to desktop afterwards.

- [ ] **Step 11: Clean up the scratch run**

Stop the dev server (Ctrl+C), then remove only what this task created:

```bash
docker rm -f mimo-m3-api mimo-m3-worker
docker volume rm mimo_m3_check
docker image rm mimo-m3-check
```

- [ ] **Step 12: Describe the brain in the README and settings**

In `README.md`, replace:

```markdown
Model settings (`TYPESAFE_API_KEY`, `OPENAI_API_KEY`, `MIMO_MODEL`, `MIMO_MODEL_URL`, `MIMO_MAX_DECISIONS_PER_DAY`, `MIMO_MAX_LUNA_DECISIONS_PER_DAY`) are kept for the brain milestone. The survival worker does not call a model yet.
```

with:

```markdown
`MIMO_ACTION_SCALE` (default 1) makes every step that many times shorter. It is for manual tests only: at `MIMO_TIME_SCALE=60` the clock runs fast but the steps do not, so also set `MIMO_ACTION_SCALE=60` to see a whole day of purposes. Only the worker reads it.

Model settings: with `TYPESAFE_API_KEY` the worker asks Jev (`TYPESAFE_MODEL`, `TYPESAFE_API_URL`) to choose Mimo's purposes. With only `OPENAI_API_KEY` or `MIMO_MODEL_API_KEY` it asks Luna (`MIMO_MODEL`, `MIMO_MODEL_URL`). With neither, rules choose. `MIMO_MAX_DECISIONS_PER_DAY` and `MIMO_MAX_LUNA_DECISIONS_PER_DAY` cap the model calls per UTC day. See Brain.
```

Replace:

```markdown
- Until the brain milestone, a stand-in script runs the pet by day, and it sleeps at night or when exhausted. See Actions.
```

with:

```markdown
- A brain runs the pet: reflexes for emergencies, purposes it chooses, and a planner that turns a purpose into steps. See Brain.
```

Replace:

```markdown
- A block dug out from under Mimo makes it fall. A fall deals (blocks − 3) × 10 damage, and water breaks a fall. Air drains while Mimo's cell is water; until the brain milestone Mimo then swims straight up.
```

with:

```markdown
- A block dug out from under Mimo makes it fall. A fall deals (blocks − 3) × 10 damage, and water breaks a fall. Air drains while Mimo's cell is water; Mimo then swims straight up, and the surface reflex digs through a ceiling or heads for the shore.
```

Replace:

```markdown
- `/api/mimo` streams the current step (`action`: kind, start and end time, and a timed path or a target block) and `recent_actions`. The viewer moves the pet along the path by server time and animates each step: a hop per block, a swing and growing cracks while mining, particles and an item pop when a block breaks, a bounce when a block is placed, nibbling with crumbs, lying down with floating z's, bobbing in water and a quickening drop when falling.
- The stand-in script (`backend/survival/script.py`, replaced by the brain milestone): by day Mimo walks to the nearest tree within 24 blocks, chops its logs and crafts them into planks, and walks out to look for trees when none is near. `MIMO_TIME_SCALE` speeds the clock and the vitals, not the steps, so the animations stay watchable in a fast test run.
```

with:

```markdown
- `/api/mimo` streams the current step (`action`: kind, start and end time, and a timed path or a target block) and `recent_actions`. The viewer moves the pet along the path by server time and animates each step: a hop per block, a swing and growing cracks while mining, particles and an item pop when a block breaks, a bounce when a block is placed, nibbling with crumbs, lying down with floating z's, bobbing in water and a quickening drop when falling. The viewer draws the pet 1.5 s behind server time, and the newest finished walks keep their path in `recent_actions`, so a step that started and ended between two polls still plays out.
- `MIMO_TIME_SCALE` speeds the clock and the vitals, not the steps, so the animations stay watchable in a fast test run. `MIMO_ACTION_SCALE` shortens the steps for a fast manual run.

## Brain

The brain has three layers. It runs in the worker; the tick itself never waits for a model.

- **Reflexes** take over at once, most urgent first: surface (air below 40: dig through a ceiling or swim to shore), avoid drop (never mine the block under Mimo over a drop of more than 3 blocks or into lava, and walk around a cell that lost its floor), eat now (hunger below 15 with food), warm up (warmth below 25: place a carried furnace, or go to a known shelter or furnace), head home (from 3 game minutes before dusk until night, when a shelter is known within 64 blocks) and collapse (energy below 10: sleep on the spot). A reflex sets the current plan aside and gives it back when it is done. Walks, sleep and waits can be cut short; a cut walk stops on the last cell it reached.
- **Purposes** are goals in a registry (`backend/survival/purposes.py`): gather wood, gather stone (a staircase dug into the ground), mine ore (coal and iron Mimo has seen), craft tools (the next pickaxe, with a crafting table it places and then picks up again), explore, go home, sleep, rest and eat. Each has a validity check, facts for the chooser, a score and a planner. Food, farming and building purposes arrive with the next milestones.
- **Choosing.** Mimo chooses a new purpose when a plan finishes or fails, a reflex ends, a vital falls past 50, 30 or 15, at dawn and dusk, after a discovery, after a hello, and after a game hour without a choice. Jev chooses when `TYPESAFE_API_KEY` is set, else Luna when an OpenAI key is set, else rules (the utility picker: needs first, then traits, with a small random nudge). Rules also choose when a daily cap is spent, when a call fails, and when the last model call was less than 60 s ago (a falling vital does not wait). Model calls run in a background thread, so the pet keeps moving while a model thinks. Each choice gets a one-line thought; after a model's choice at dawn, after a hello or after a discovery, Luna may add a reflection instead (at most 12 a day).
- **Planner.** A purpose becomes batches of the timed steps above. A failed step (codes `no_path`, `out_of_reach`, `gone`, `missing_item`, `blocked`, `bad_step`) plans the purpose again once. A second failure drops the purpose, scores it lower for 10 game minutes and asks for a new choice. When the last two walks found no way and Mimo can reach almost nothing, it is trapped: it digs a staircase out, or builds one from blocks it carries.
- **Memory** lives in each world's database and starts empty: places (home, shelters, ore it saw, dangerous drops, water) and the recipes Mimo has used. Home is the first sheltered spot Mimo finds, often its own mine staircase.
- `/api/mimo` adds `purpose`, `reflex`, `picker` and `choosing`. The HUD shows the purpose, the step and the latest thought.
```

In `.env.example`, replace:

```bash
# Live Mimo worker. Jev runs with its TypeSafe key alone. When an OpenAI key is
# also set, Jev can choose a creative Luna decision. MIMO_MODEL must be a chat
# model available at MIMO_MODEL_URL. For a local compatible server, use its
# /v1/chat/completions endpoint and leave OPENAI_API_KEY blank if it needs no key.
```

with:

```bash
# Survival brain. With TYPESAFE_API_KEY, Jev chooses Mimo's purposes. With only an
# OpenAI key (OPENAI_API_KEY or MIMO_MODEL_API_KEY), Luna does; MIMO_MODEL must be a
# chat model at MIMO_MODEL_URL. With neither, rules choose. With both keys, Luna may
# add a short reflection (at most 12 a day). The caps count model calls per UTC day;
# when one is spent, rules take over.
```

and replace:

```bash
MIMO_TIME_SCALE=1
```

with:

```bash
MIMO_TIME_SCALE=1
# MIMO_ACTION_SCALE makes Mimo's steps that many times shorter, for manual tests only
# (use 60 with MIMO_TIME_SCALE=60 to watch a whole day of purposes). Only the worker reads it.
MIMO_ACTION_SCALE=1
```

In `docker-compose.yml`, in the `mimo-worker` service, replace:

```yaml
      MIMO_TIME_SCALE: ${MIMO_TIME_SCALE:-1}
      MIMO_MODEL: ${MIMO_MODEL:-gpt-6-luna}
      MIMO_MODEL_URL: ${MIMO_MODEL_URL:-https://api.openai.com/v1/chat/completions}
      MIMO_MODEL_API_KEY: ${MIMO_MODEL_API_KEY:-}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      TYPESAFE_API_KEY: ${TYPESAFE_API_KEY:-}
```

with:

```yaml
      MIMO_TIME_SCALE: ${MIMO_TIME_SCALE:-1}
      MIMO_ACTION_SCALE: ${MIMO_ACTION_SCALE:-1}
      MIMO_MODEL: ${MIMO_MODEL:-gpt-6-luna}
      MIMO_MODEL_URL: ${MIMO_MODEL_URL:-https://api.openai.com/v1/chat/completions}
      MIMO_MODEL_API_KEY: ${MIMO_MODEL_API_KEY:-}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      TYPESAFE_API_KEY: ${TYPESAFE_API_KEY:-}
```

- [ ] **Step 13: Run every check again and commit**

Run: `python3 -m unittest discover -s backend/tests && cd frontend && npm test && npm run build`
Expected: `Ran 328 tests` … `OK`, `Tests  151 passed (151)`, the build succeeds.

```bash
git add README.md .env.example docker-compose.yml
git commit -m "docs: describe Mimo's brain, its pickers and MIMO_ACTION_SCALE" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (M3) | Where |
|-----------|-------|
| §5 reflexes as data (trigger, priority, planner); the first match takes over and returns control | Task 11 (`Reflex`, `REFLEXES`, `reflex_hook`, `end_reflex`) |
| §5 surface, avoid drop, eat now, warm up, head home, collapse | Task 11; flee is left to sub-project 3 (priority 30 free, `register`) |
| §5 purposes: validity, facts, planner; a registry M4/M5 extend | Tasks 6 (`Purpose`, `register`, `offered`), 7, 8 |
| §5 core purposes available after M2 | Tasks 6 (rest, sleep, explore, go_home, eat), 7 (gather_wood, gather_stone, mine_ore), 8 (craft_tools); forage, fish, farm, cook, build_*, light_up wait for M4/M5 (resolution 4) |
| §5 triggers: plan done or failed, reflex ended, vitals 50/30/15, dawn/dusk, discovery, hello, game hour | Tasks 5 (`mark_trigger`, `crossings`, `phase_trigger`, `hour_passed`, hello), 9 (`plan_done`, `plan_failed`, `notice_step`, discoveries), 11 (`reflex_ended`) |
| §5 at least 60 s between model calls except vital crossings | Task 13 (`route_for`, `MODEL_GAP`) |
| §5 pickers: Jev, Luna, utility; fallbacks | Tasks 12 (`ask_jev`, `ask_luna`, `utility_pick`), 13 (`decide`, `route_for`) |
| §5 the choice and a one-line thought are logged; Luna reflections at most 12 a day | Tasks 12 (`thought_for`, `luna_reflect`), 13 (`purpose` event, `reflect_for`) |
| §5 planner: purpose → queue of M2 steps; re-plan once; a second failure reports | Tasks 9 (`brain_plan`), 10 |
| §5 memory: places, typed events, known recipes; a new life starts empty | Tasks 5 (`memory`), 9 (`observe_step`, `notice_step`) |
| §5 M2 review: no model call inside the tick | Tasks 9 (the tick only marks triggers), 13 (worker, background thread, short store transaction) |
| §5 M2 review: planners share the 2-per-tick search budget | Tasks 1 (`take_search`), 10 (flood fill), 11 (shore search) |
| §5 M2 review: interrupts, walk snaps, `interrupted`, the queue set aside, checks before steps and during sleep and waits | Tasks 2 (hazards as `interrupted`), 4 (hook), 11 (set aside and resume) |
| §5 M2 review: failure codes with cell and purpose, `last_failure` | Task 2 |
| §5 M2 review: trapped → dig a staircase or build one from carried blocks | Task 10 |
| §5 M2 review: the viewer draws 1.5 s behind; finished walks keep their path | Tasks 3 (`PATH_KEEP`), 15 (`replayAt`) |
| §5 M2 review: crash logs once per distinct error | Task 1 (`log_once`), used in Tasks 4, 6, 9, 11, 12, 13 |
| §5 M2 review: `MIMO_ACTION_SCALE` | Task 3; settings and README in Task 16 |
| §9 HUD: current purpose and step in plain words, the latest thought | Task 15 (`purposeText`, HUD) |
| §10 `/api/mimo` keeps the `action` shapes and adds the brain | Task 14 |
| §11 the caps stay, utility takes over when one is spent, playable without keys | Task 13 (`cap`, `calls_today`, `route_for`) |
| §12 a model call fails or returns an invalid purpose → utility, logged once | Tasks 12 (`ModelError`), 13 (`decide`, `Chooser.store`) |
| §12 the planner cannot find a path or material → re-plan once, report, scored lower for 10 game minutes | Tasks 9 (`report`, penalties), 12 (`PENALTY`) |
| §12 worker restart mid-action; clock-jump catch-up | Unchanged from M2. The brain's state (including `pending`) is saved with the world (Task 5), so a restarted worker answers the same pending choice |
| §13 brain tests: every reflex triggers and yields back; every purpose's validity; the utility picker's choices for scripted situations; Jev and Luna payloads with fake HTTP and their fallback | Tasks 6–8, 11, 12, 13 |
| §13 manual 60× run | Task 16 |

Out of scope here: food blocks, fishing, farming, cooking, leaf decay and regrowth (M4); shelters, farms, storage, lights and the building generator (M5); flee and creatures (sub-project 3); chat (sub-project 4); flowing water and falling sand (sub-project 5).
