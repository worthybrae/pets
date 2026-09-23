# Survival M1: Lives and Vitals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire today's Mimo as the first archived life, let a new pet hatch from a server-rolled egg into a brand-new world, and give it a world clock, vitals, death, owner care, a HUD, day and night, and an archive browser.

**Architecture:** A new Python package `backend/survival/` holds small modules: pure rules (`clock`, `vitals`, `eggs`, `spawn`), storage (`world` on a block table shared with the legacy store, `registry` for `lives.sqlite3`), and the moving parts (`hatch`, `tick`, `care`, `snapshot`). The API serves the active life at `/api/mimo` and every life at `/api/lives`. The worker ticks only the active life, once a second, catching up in steps of at most 60 game seconds. The viewer's `/preview` page branches on `phase`: egg screen, living world with HUD and day/night (a daylight uniform on the terrain materials, with a per-vertex glow attribute so glowing blocks stay bright), memorial, and a read-only archive.

**Tech Stack:** Python 3.10+ (3.12 in Docker), FastAPI, SQLite, `unittest`; React 19, three.js 0.184, @react-three/fiber 9, Vite 8, TypeScript 6, Vitest 5, Tailwind 4.

**Spec:** `docs/superpowers/specs/2026-09-23-survival-core-design.md` (M1: sections 1, 2, 3, 4, 9 and the M1 parts of 10–13)

## Global Constraints

- Stay on branch `worthy/23_09_2026/survival_core`. Do not switch branches.
- Python must run on 3.10 locally and 3.12 in Docker. Every new Python module starts with `from __future__ import annotations`.
- Backend tests use `unittest`. Tests call FastAPI route functions directly (the image has no `httpx`, and `backend.main` needs `redis`, which is not installed locally). Never import `backend.main` in a test.
- TypeScript has `erasableSyntaxOnly`, `noUnusedLocals` and `noUnusedParameters`. No constructor parameter properties, no enums, no namespaces.
- React runs in StrictMode. `eslint-plugin-react-hooks` 7 is on: no `Date.now()` or ref reads during render, never mutate props or hook arguments (a ref passed as a prop counts), and no synchronous `setState` in an effect body.
- Vitest runs in the `node` environment and only picks up `src/**/*.test.ts`. Put viewer logic that needs tests in `.ts` modules, not in components.
- The legacy world file (`MIMO_DB_PATH`) is never written by survival code. Survival code opens it only through read-only connections. The legacy schema and the legacy code (`run_tick`, `MimoStore`) stay.
- `MIMO_DATA_DIR` (default `/data`) holds `lives.sqlite3` and `lives/<id>.sqlite3`.
- Values copied from the spec: one game day = 3,600 game seconds; phases dawn 0–180, day 180–2,220, dusk 2,220–2,400, night 2,400–3,420, pre-dawn 3,420–3,600; hunger −0.014/s idle, ×1.5 working; energy −0.008/s idle, −0.03/s working, +0.2/s sleeping, +0.35/s in a bed; warmth moves 0.5/s toward its target; air −10/s with the head in water, +25/s in air; starving −1 health per 30 s; freezing (warmth < 20) −1 per 15 s; drowning −2 per s; healing +1 per 20 s while hunger > 60 and warmth > 50; target warmth 100 by day, 30 at night, 40 alpine by day, −20 alpine at night, +45 sheltered, 100 within 4 blocks of a campfire or furnace; shelter = roof within 4 blocks overhead and enclosed on at least 3 sides; exhausted < 10; snack +30 hunger and bandage +25 health, one each per UTC day; spawn 3,000–6,000 blocks from the origin, dry grass or moss, meadow or forest, a tree within 24 blocks; coordinate limit ±30,000 for survival worlds; catch-up steps of at most 60 s.
- `MIMO_TIME_SCALE` (default 1) multiplies game seconds per real second for the clock and every rate. Tests pass time and scale in directly.
- Never touch, mount or migrate the owner's real Docker volume `pets_mimo_data`. The manual check uses a fresh scratch volume and `MIMO_TIME_SCALE=60`.
- `docs/` is in `.gitignore`. Add files under `docs/` with `git add -f`.
- End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the second `-m` in each commit command does this).

## Commands

- Backend tests, from the repo root: `python3 -m unittest discover -s backend/tests` (49 pass before this plan, 137 after Task 8)
- One backend test file: `python3 -m unittest discover -s backend/tests -p "test_survival_clock.py" -v`
- Frontend tests: `cd frontend && npm test` (79 pass before this plan, 106 after Task 12)
- Frontend build (type check + bundle): `cd frontend && npm run build`
- Lint touched files: `cd frontend && npx eslint <paths>`

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/services/blocks.py` | Modify | Add `is_solid` from the registry's `solid` flag |
| `backend/services/block_table.py` | Create | Shared block table: `open_db` (with read-only mode), `create_block_tables`, `write_block`, `read_blocks_since`, `resolve_block`, `material_in` |
| `backend/services/live_mimo.py` | Modify | `MimoStore` uses the shared block table and gains `read_only=True` |
| `backend/survival/__init__.py` | Create | Package marker |
| `backend/survival/clock.py` | Create | Day length, phases, `clock_at`, `time_scale` |
| `backend/survival/vitals.py` | Create | Rates, warmth target, mood target, `step_vitals`, shelter and fire checks |
| `backend/survival/eggs.py` | Create | Egg tiers and pools (port of `eggAttributes.ts`), trait floors, names |
| `backend/survival/spawn.py` | Create | Spawn rules and spiral search |
| `backend/survival/world.py` | Create | `SurvivalWorld`: one life's world DB, state row, events, hello, crafting help |
| `backend/survival/registry.py` | Create | `LifeRegistry`: `lives.sqlite3`, legacy retirement, pending egg, create life, death |
| `backend/survival/hatch.py` | Create | Hatch the pending egg into a new life |
| `backend/survival/tick.py` | Create | Surroundings, interim sleep rule, catch-up, death and archive |
| `backend/survival/care.py` | Create | Daily snack and bandage |
| `backend/survival/snapshot.py` | Create | API shapes: life rows, alive snapshot, life detail and summary |
| `backend/api/lives.py` | Create | `/api/lives`, `/api/lives/hatch`, `/api/lives/{id}`, `/api/lives/{id}/blocks` |
| `backend/api/mimo.py` | Rewrite | `/api/mimo` phases, blocks, hello, crafting help, care for the active life |
| `backend/main.py` | Modify | Include the lives router |
| `backend/workers/mimo_worker.py` | Rewrite | Tick the active life every `MIMO_TICK_SECONDS` (default 1) |
| `backend/scripts/worldgen_fixture.py` | Modify | Sample far cells (to ±30,000) for the parity fixture |
| `shared/worldgen-fixture.json` | Regenerate | Parity fixture with far cells |
| `docker-compose.yml`, `.env.example` | Modify | `MIMO_DATA_DIR`, `MIMO_TIME_SCALE`, tick default 1 |
| `backend/tests/test_survival_*.py` | Create | clock, vitals, eggs, spawn, world, lives, tick, care, api, worker |
| `backend/tests/test_blocks.py`, `test_worldgen.py`, `test_block_sync.py` | Modify | `is_solid`, far fixture cells, legacy blocks endpoint moves to `/api/lives/1/blocks` |
| `frontend/src/engine/mesher.ts`, `workerProtocol.ts` | Modify | Per-vertex `glows` buffer |
| `frontend/src/engine/columnRenderer.ts` | Modify | `applyDaylight`, shared daylight uniform, `setDaylight` |
| `frontend/src/engine/BlockWorld.tsx` | Modify | `daylight` callback prop |
| `frontend/src/survival/types.ts`, `api.ts` | Create | API shapes and fetch helpers |
| `frontend/src/survival/clock.ts`, `sky.ts`, `hud.ts`, `archive.ts` | Create | Pure viewer logic (tested) |
| `frontend/src/survival/FollowCamera.tsx` | Create | The camera that used to live in `WorldPreview.tsx` |
| `frontend/src/survival/DayNight.tsx` | Create | Sky, fog, lights and the pet's night glow |
| `frontend/src/survival/WorldCanvas.tsx` | Create | Canvas with terrain, pet and camera, shared by live and archive views |
| `frontend/src/survival/SurvivalHud.tsx`, `CraftingPanel.tsx`, `SurvivalWorld.tsx` | Create | The living world view |
| `frontend/src/survival/ArchiveBrowser.tsx`, `ArchiveWorld.tsx` | Create | Lives list and read-only worlds |
| `frontend/src/survival/EggHatch.tsx`, `Memorial.tsx` | Create | Egg screen and memorial card |
| `frontend/src/pages/WorldPreview.tsx` | Rewrite | Branch on `phase` |
| `README.md` | Rewrite | Lives, vitals, worker, checks |

---

### Task 1: Survival clock and vitals rules

**Files:**
- Create: `backend/survival/__init__.py`, `backend/survival/clock.py`, `backend/survival/vitals.py`
- Modify: `backend/services/blocks.py` (append `is_solid`)
- Test: `backend/tests/test_survival_clock.py`, `backend/tests/test_survival_vitals.py`, `backend/tests/test_blocks.py`

**Interfaces:**
- Produces (`backend.services.blocks`): `is_solid(material: str) -> bool`.
- Produces (`backend.survival.clock`): `DAY_SECONDS = 3600.0`, `PHASES`, `NIGHT_PHASES = {"night", "pre_dawn"}`, `time_scale() -> float`, `phase_at(seconds_into_day: float) -> str`, `is_night(phase: str) -> bool`, `clock_at(born_at: float, timestamp: float, scale: float = 1.0) -> dict` with keys `day_number`, `seconds_into_day`, `time_of_day`, `phase`, `day_seconds`, `time_scale`.
- Produces (`backend.survival.vitals`): `START_VITALS: dict`, `EXHAUSTED_BELOW = 10.0`, `FREEZING_BELOW = 20.0`, `FIRE_REACH = 4`, `WARM_BLOCKS = ("campfire", "furnace")`, `Surroundings(biome="meadow", sheltered=False, near_fire=False, head_in_water=False)` (frozen dataclass), `target_warmth(night, biome, sheltered, near_fire) -> float`, `mood_target(vitals, lonely) -> float`, `step_vitals(vitals: dict, seconds: float, *, night: bool, activity: str, surroundings: Surroundings, lonely: bool = False) -> tuple[dict, str | None]` (activity is `idle`, `working`, `sleeping` or `sleeping_in_bed`; the second value is a cause of death: `starvation`, `cold` or `drowning`), `is_sheltered(material_at: Callable[[int, int, int], str], x, y, z) -> bool`, `near_warm_block(placed: list[tuple[int, int, int, str]], x, y, z) -> bool`.

Rules the spec leaves open, decided here: dusk counts as day, and night plus pre-dawn make the 20 dark minutes; step conditions are read at the start of each step; health does not recover in a step that deals damage; the cause of death is the largest damage in the killing step (ties: drowning, cold, starvation); mood drifts 0.01 per second toward a target (60, +20 fed and warm, −30 starving, −25 freezing, −15 below 50 health, −10 lonely); shelter walls are looked for at Mimo's feet level; any placed furnace counts as lit until M4 adds a lit state.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_clock.py`:

```python
import os
import unittest
from unittest.mock import patch

from backend.survival.clock import DAY_SECONDS, clock_at, is_night, phase_at, time_scale


class ClockTests(unittest.TestCase):
    def test_a_life_starts_at_dawn_on_day_one(self):
        clock = clock_at(1000.0, 1000.0)
        self.assertEqual(clock["day_number"], 1)
        self.assertEqual(clock["phase"], "dawn")
        self.assertEqual(clock["time_of_day"], 0.0)
        self.assertEqual(clock["day_seconds"], 3600.0)

    def test_phase_boundaries_follow_the_spec(self):
        expected = [(0, "dawn"), (179.9, "dawn"), (180, "day"), (2219.9, "day"), (2220, "dusk"),
                    (2399.9, "dusk"), (2400, "night"), (3419.9, "night"), (3420, "pre_dawn"),
                    (3599.9, "pre_dawn"), (3600, "dawn")]
        for seconds, phase in expected:
            self.assertEqual(phase_at(seconds), phase, seconds)

    def test_night_lasts_twenty_minutes_including_pre_dawn(self):
        dark = sum(1 for second in range(int(DAY_SECONDS)) if is_night(phase_at(second)))
        self.assertEqual(dark, 1200)
        self.assertFalse(is_night("dusk"))

    def test_day_number_and_time_of_day_advance_with_real_time(self):
        self.assertEqual(clock_at(0, 3600)["day_number"], 2)
        later = clock_at(0, 2 * 3600 + 2700)
        self.assertEqual(later["day_number"], 3)
        self.assertEqual(later["phase"], "night")
        self.assertAlmostEqual(later["time_of_day"], 0.75)

    def test_time_scale_multiplies_game_time(self):
        self.assertEqual(clock_at(0, 40, scale=60)["phase"], "night")
        fast = clock_at(0, 61, scale=60)
        self.assertEqual(fast["day_number"], 2)
        self.assertAlmostEqual(fast["seconds_into_day"], 60)
        self.assertEqual(fast["time_scale"], 60)

    def test_times_before_birth_count_as_the_first_dawn(self):
        early = clock_at(500, 100)
        self.assertEqual(early["day_number"], 1)
        self.assertEqual(early["seconds_into_day"], 0)

    def test_time_scale_reads_the_environment(self):
        with patch.dict(os.environ, {"MIMO_TIME_SCALE": "60"}):
            self.assertEqual(time_scale(), 60.0)
        for bad in ("0", "-3", "fast", "inf", "nan"):
            with patch.dict(os.environ, {"MIMO_TIME_SCALE": bad}):
                self.assertEqual(time_scale(), 1.0, bad)
        with patch.dict(os.environ, {}):
            os.environ.pop("MIMO_TIME_SCALE", None)
            self.assertEqual(time_scale(), 1.0)


if __name__ == "__main__":
    unittest.main()
```

Create `backend/tests/test_survival_vitals.py`:

```python
import unittest

from backend.survival.vitals import (
    START_VITALS, Surroundings, is_sheltered, near_warm_block, step_vitals, target_warmth,
)

OPEN = Surroundings()


def vitals(**changes):
    return {**START_VITALS, **changes}


def world(cells):
    return lambda x, y, z: cells.get((x, y, z), "air")


class VitalRateTests(unittest.TestCase):
    def test_idle_hunger_and_energy_drain(self):
        after, cause = step_vitals(vitals(), 60, night=False, activity="idle", surroundings=OPEN)
        self.assertAlmostEqual(after["hunger"], 100 - 0.84)
        self.assertAlmostEqual(after["energy"], 100 - 0.48)
        self.assertIsNone(cause)

    def test_work_burns_food_and_energy_faster(self):
        after, _ = step_vitals(vitals(), 60, night=False, activity="working", surroundings=OPEN)
        self.assertAlmostEqual(after["hunger"], 100 - 0.84 * 1.5)
        self.assertAlmostEqual(after["energy"], 100 - 1.8)

    def test_sleep_restores_energy_and_a_bed_restores_more(self):
        tired = vitals(energy=20.0)
        slept, _ = step_vitals(tired, 60, night=True, activity="sleeping", surroundings=OPEN)
        in_bed, _ = step_vitals(tired, 60, night=True, activity="sleeping_in_bed", surroundings=OPEN)
        self.assertAlmostEqual(slept["energy"], 32.0)
        self.assertAlmostEqual(in_bed["energy"], 41.0)

    def test_values_stay_between_0_and_100(self):
        after, _ = step_vitals(vitals(hunger=0.1, energy=99.9), 60, night=False, activity="sleeping",
                               surroundings=OPEN)
        self.assertEqual(after["hunger"], 0.0)
        self.assertEqual(after["energy"], 100.0)

    def test_an_unfed_idle_pet_starves_in_about_two_game_days(self):
        state, elapsed, empty_at, cause = vitals(), 0, None, None
        while cause is None and elapsed < 20000:
            state, cause = step_vitals(state, 60, night=False, activity="idle", surroundings=OPEN)
            elapsed += 60
            if empty_at is None and state["hunger"] == 0:
                empty_at = elapsed
        self.assertEqual(cause, "starvation")
        self.assertTrue(7140 <= empty_at <= 7200, empty_at)
        self.assertTrue(10140 <= elapsed <= 10260, elapsed)

    def test_cold_hurts_and_can_kill(self):
        alpine = Surroundings(biome="alpine")
        after, cause = step_vitals(vitals(warmth=10.0), 60, night=True, activity="idle", surroundings=alpine)
        self.assertAlmostEqual(after["health"], 96.0)
        self.assertIsNone(cause)
        _, cause = step_vitals(vitals(warmth=10.0, health=3.0), 60, night=True, activity="idle", surroundings=alpine)
        self.assertEqual(cause, "cold")

    def test_air_drains_underwater_then_drowning_hurts(self):
        wet = Surroundings(head_in_water=True)
        after, _ = step_vitals(vitals(), 5, night=False, activity="idle", surroundings=wet)
        self.assertAlmostEqual(after["air"], 50.0)
        self.assertEqual(after["health"], 100.0)
        after, _ = step_vitals(vitals(air=0.0), 10, night=False, activity="idle", surroundings=wet)
        self.assertAlmostEqual(after["health"], 80.0)
        _, cause = step_vitals(vitals(air=0.0, health=5.0), 10, night=False, activity="idle", surroundings=wet)
        self.assertEqual(cause, "drowning")

    def test_air_recovers_in_open_air(self):
        after, _ = step_vitals(vitals(air=50.0), 1, night=False, activity="idle", surroundings=OPEN)
        self.assertAlmostEqual(after["air"], 75.0)

    def test_health_recovers_only_when_fed_and_warm(self):
        after, _ = step_vitals(vitals(health=50.0, hunger=70.0, warmth=60.0), 60, night=False, activity="idle",
                               surroundings=OPEN)
        self.assertAlmostEqual(after["health"], 53.0)
        after, _ = step_vitals(vitals(health=50.0, hunger=55.0), 60, night=False, activity="idle", surroundings=OPEN)
        self.assertEqual(after["health"], 50.0)

    def test_mood_drifts_toward_how_mimo_feels(self):
        content, _ = step_vitals(vitals(mood=50.0), 100, night=False, activity="idle", surroundings=OPEN)
        self.assertAlmostEqual(content["mood"], 51.0)
        miserable, _ = step_vitals(vitals(mood=50.0, hunger=0.0), 100, night=False, activity="idle",
                                   surroundings=OPEN, lonely=True)
        self.assertAlmostEqual(miserable["mood"], 49.0)

    def test_unknown_activity_is_rejected(self):
        with self.assertRaises(ValueError):
            step_vitals(vitals(), 1, night=False, activity="dancing", surroundings=OPEN)


class WarmthTests(unittest.TestCase):
    def test_target_warmth_by_time_place_shelter_and_fire(self):
        self.assertEqual(target_warmth(False, "meadow", False, False), 100)
        self.assertEqual(target_warmth(True, "meadow", False, False), 30)
        self.assertEqual(target_warmth(True, "forest", True, False), 75)
        self.assertEqual(target_warmth(True, "alpine", False, False), -20)
        self.assertEqual(target_warmth(False, "alpine", False, False), 40)
        self.assertEqual(target_warmth(False, "alpine", True, False), 85)
        self.assertEqual(target_warmth(False, "meadow", True, False), 100)
        self.assertEqual(target_warmth(True, "alpine", False, True), 100)

    def test_warmth_moves_half_a_point_per_second_toward_the_target(self):
        cooled, _ = step_vitals(vitals(), 60, night=True, activity="idle", surroundings=OPEN)
        self.assertAlmostEqual(cooled["warmth"], 70.0)
        warmed, _ = step_vitals(vitals(warmth=30.0), 20, night=False, activity="idle", surroundings=OPEN)
        self.assertAlmostEqual(warmed["warmth"], 40.0)
        settled, _ = step_vitals(vitals(warmth=31.0), 60, night=True, activity="idle", surroundings=OPEN)
        self.assertEqual(settled["warmth"], 30.0)
        frozen, _ = step_vitals(vitals(warmth=5.0), 60, night=True, activity="idle",
                                surroundings=Surroundings(biome="alpine"))
        self.assertEqual(frozen["warmth"], 0.0)


class ShelterTests(unittest.TestCase):
    def hut(self, roof_y=12, material="stone", sides=((2, 0), (-2, 0), (0, 2))):
        """Cells around Mimo standing at (0, 10, 0): a roof block and wall blocks at feet level."""
        cells = {(0, roof_y, 0): material}
        for dx, dz in sides:
            cells[(dx, 10, dz)] = material
        return cells

    def test_open_ground_is_not_shelter(self):
        self.assertFalse(is_sheltered(world({(0, 9, 0): "grass"}), 0, 10, 0))

    def test_roof_and_three_walls_make_a_shelter(self):
        self.assertTrue(is_sheltered(world(self.hut()), 0, 10, 0))

    def test_two_walls_are_not_enough(self):
        self.assertFalse(is_sheltered(world(self.hut(sides=((2, 0), (-2, 0)))), 0, 10, 0))

    def test_walls_without_a_roof_are_not_enough(self):
        cells = self.hut()
        del cells[(0, 12, 0)]
        self.assertFalse(is_sheltered(world(cells), 0, 10, 0))

    def test_roof_must_be_within_four_blocks(self):
        self.assertTrue(is_sheltered(world(self.hut(roof_y=14)), 0, 10, 0))
        self.assertFalse(is_sheltered(world(self.hut(roof_y=15)), 0, 10, 0))

    def test_walls_must_be_within_four_blocks(self):
        self.assertFalse(is_sheltered(world(self.hut(sides=((5, 0), (-2, 0), (0, 2)))), 0, 10, 0))

    def test_leaves_count_but_plants_do_not(self):
        self.assertTrue(is_sheltered(world(self.hut(material="leaves")), 0, 10, 0))
        self.assertFalse(is_sheltered(world(self.hut(material="tall_grass")), 0, 10, 0))

    def test_a_cave_counts_as_shelter(self):
        def cave(x, y, z):
            return "air" if (x, y, z) == (0, 10, 0) else "stone"
        self.assertTrue(is_sheltered(cave, 0, 10, 0))

    def test_a_furnace_within_four_blocks_is_warm(self):
        self.assertTrue(near_warm_block([(4, 10, -4, "furnace")], 0, 10, 0))
        self.assertFalse(near_warm_block([(5, 10, 0, "furnace")], 0, 10, 0))
        self.assertFalse(near_warm_block([(1, 10, 0, "lantern")], 0, 10, 0))


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_blocks.py`, change the import line to:

```python
from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, TILES, is_plant, is_replaceable, is_solid
```

and add this test at the end of `BlockRegistryTests`:

```python
    def test_is_solid_follows_the_registry(self):
        for name in ("stone", "leaves", "glass", "grass"):
            self.assertTrue(is_solid(name), name)
        for name in ("air", "water", "lava", "tall_grass", "not_a_block"):
            self.assertFalse(is_solid(name), name)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_*.py"`
Expected: 2 errors, `ModuleNotFoundError: No module named 'backend.survival'`.

Run: `python3 -m unittest discover -s backend/tests -p "test_blocks.py"`
Expected: `ImportError: cannot import name 'is_solid'`.

- [ ] **Step 3: Add `is_solid`**

Append to `backend/services/blocks.py`:

```python


def is_solid(material: str) -> bool:
    """True for blocks Mimo can stand on or shelter under (the registry's `solid`)."""
    index = BLOCK_IDS.get(material)
    return index is not None and bool(BLOCK_LIST[index].get("solid"))
```

- [ ] **Step 4: Create the package and the clock**

Create `backend/survival/__init__.py`:

```python
"""Survival lives for Mimo: clock, vitals, eggs, spawn, worlds, the life registry and care."""
```

Create `backend/survival/clock.py`:

```python
"""The world clock. One game day is 3,600 game seconds and starts at dawn when a life is born.

MIMO_TIME_SCALE (default 1) sets how many game seconds pass per real second. It exists for
manual testing; automated tests pass the scale in directly.
"""

from __future__ import annotations

import math
import os

DAY_SECONDS = 3600.0
PHASES: tuple[tuple[str, float, float], ...] = (
    ("dawn", 0.0, 180.0),
    ("day", 180.0, 2220.0),
    ("dusk", 2220.0, 2400.0),
    ("night", 2400.0, 3420.0),
    ("pre_dawn", 3420.0, 3600.0),
)
# Night and pre-dawn together are the 20 dark minutes. Dusk still counts as day.
NIGHT_PHASES = frozenset({"night", "pre_dawn"})


def time_scale() -> float:
    """Game seconds per real second from MIMO_TIME_SCALE. Missing or invalid values mean 1."""
    try:
        scale = float(os.environ.get("MIMO_TIME_SCALE", "1"))
    except ValueError:
        return 1.0
    return scale if math.isfinite(scale) and scale > 0 else 1.0


def phase_at(seconds_into_day: float) -> str:
    seconds = seconds_into_day % DAY_SECONDS
    for name, start, end in PHASES:
        if start <= seconds < end:
            return name
    return PHASES[-1][0]


def is_night(phase: str) -> bool:
    return phase in NIGHT_PHASES


def clock_at(born_at: float, timestamp: float, scale: float = 1.0) -> dict:
    """Day number (from 1), seconds into the day, time of day (0-1) and phase."""
    elapsed = max(0.0, timestamp - born_at) * scale
    seconds = elapsed % DAY_SECONDS
    return {
        "day_number": int(elapsed // DAY_SECONDS) + 1,
        "seconds_into_day": seconds,
        "time_of_day": seconds / DAY_SECONDS,
        "phase": phase_at(seconds),
        "day_seconds": DAY_SECONDS,
        "time_scale": scale,
    }
```

- [ ] **Step 5: Create the vitals rules**

Create `backend/survival/vitals.py`:

```python
"""Vitals: pure rules for how health, hunger, warmth, energy, air and mood change.

All values run 0-100 and every rate is per game second. `step_vitals` advances one step
(the tick module keeps steps at 60 game seconds or less) and reads its conditions at the
start of the step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.services.blocks import is_solid

VITAL_NAMES = ("health", "hunger", "warmth", "energy", "air", "mood")
START_VITALS = {"health": 100.0, "hunger": 100.0, "warmth": 100.0, "energy": 100.0, "air": 100.0, "mood": 70.0}

HUNGER_IDLE = 0.014
WORK_HUNGER_MULTIPLIER = 1.5
ENERGY_IDLE = 0.008
ENERGY_WORK = 0.03
ENERGY_SLEEP = 0.2
ENERGY_BED = 0.35
WARMTH_RATE = 0.5
AIR_DRAIN = 10.0
AIR_RECOVER = 25.0
STARVING_DAMAGE = 1 / 30
FREEZING_DAMAGE = 1 / 15
DROWNING_DAMAGE = 2.0
HEAL_RATE = 1 / 20
MOOD_RATE = 0.01
FREEZING_BELOW = 20.0
EXHAUSTED_BELOW = 10.0
SHELTER_BONUS = 45.0
SHELTER_REACH = 4
FIRE_REACH = 4
WARM_BLOCKS = ("campfire", "furnace")
ACTIVITIES = ("idle", "working", "sleeping", "sleeping_in_bed")
# When several kinds of damage land in the killing step, the largest wins; ties go to the first here.
CAUSE_ORDER = ("drowning", "cold", "starvation")
HORIZONTAL = ((1, 0), (-1, 0), (0, 1), (0, -1))

MaterialAt = Callable[[int, int, int], str]


@dataclass(frozen=True)
class Surroundings:
    """What the world around Mimo's cell says. The tick computes it once per tick."""

    biome: str = "meadow"
    sheltered: bool = False
    near_fire: bool = False
    head_in_water: bool = False


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def approach(value: float, target: float, max_change: float) -> float:
    if value < target:
        return min(target, value + max_change)
    return max(target, value - max_change)


def target_warmth(night: bool, biome: str, sheltered: bool, near_fire: bool) -> float:
    if near_fire:
        return 100.0
    if biome == "alpine":
        base = -20.0 if night else 40.0
    else:
        base = 30.0 if night else 100.0
    return min(100.0, base + (SHELTER_BONUS if sheltered else 0.0))


def mood_target(vitals: dict, lonely: bool) -> float:
    """Where mood drifts: up when fed and warm, down when starving, freezing, hurt or alone."""
    target = 60.0
    if vitals["hunger"] > 60 and vitals["warmth"] > 50:
        target += 20
    if vitals["hunger"] <= 0:
        target -= 30
    if vitals["warmth"] < FREEZING_BELOW:
        target -= 25
    if vitals["health"] < 50:
        target -= 15
    if lonely:
        target -= 10
    return clamp(target)


def step_vitals(vitals: dict, seconds: float, *, night: bool, activity: str,
                surroundings: Surroundings, lonely: bool = False) -> tuple[dict, str | None]:
    """Advance vitals by `seconds` game seconds. Returns the new vitals and a cause of death, if any."""
    if activity not in ACTIVITIES:
        raise ValueError(f"Unknown activity: {activity}")
    working = activity == "working"
    sleeping = activity in ("sleeping", "sleeping_in_bed")
    damage = {
        "starvation": STARVING_DAMAGE * seconds if vitals["hunger"] <= 0 else 0.0,
        "cold": FREEZING_DAMAGE * seconds if vitals["warmth"] < FREEZING_BELOW else 0.0,
        "drowning": DROWNING_DAMAGE * seconds if surroundings.head_in_water and vitals["air"] <= 0 else 0.0,
    }
    hurt = any(amount > 0 for amount in damage.values())
    healing = HEAL_RATE * seconds if vitals["hunger"] > 60 and vitals["warmth"] > 50 and not hurt else 0.0
    if sleeping:
        energy_change = (ENERGY_BED if activity == "sleeping_in_bed" else ENERGY_SLEEP) * seconds
    else:
        energy_change = -(ENERGY_WORK if working else ENERGY_IDLE) * seconds
    hunger_rate = HUNGER_IDLE * (WORK_HUNGER_MULTIPLIER if working else 1.0)
    air_change = -AIR_DRAIN * seconds if surroundings.head_in_water else AIR_RECOVER * seconds
    warmth_target = target_warmth(night, surroundings.biome, surroundings.sheltered, surroundings.near_fire)
    result = {
        "health": clamp(vitals["health"] + healing - sum(damage.values())),
        "hunger": clamp(vitals["hunger"] - hunger_rate * seconds),
        "warmth": clamp(approach(vitals["warmth"], warmth_target, WARMTH_RATE * seconds)),
        "energy": clamp(vitals["energy"] + energy_change),
        "air": clamp(vitals["air"] + air_change),
        "mood": clamp(approach(vitals["mood"], mood_target(vitals, lonely), MOOD_RATE * seconds)),
    }
    cause = None
    if result["health"] <= 0 and hurt:
        cause = max(CAUSE_ORDER, key=lambda name: (damage[name], -CAUSE_ORDER.index(name)))
    return result, cause


def is_sheltered(material_at: MaterialAt, x: int, y: int, z: int) -> bool:
    """A roof within 4 cells above Mimo's cell and a wall within 4 cells on at least 3 sides.

    (x, y, z) is the cell Mimo stands in. Natural overhangs and caves count.
    """
    if not any(is_solid(material_at(x, y + dy, z)) for dy in range(1, SHELTER_REACH + 1)):
        return False
    walls = sum(1 for dx, dz in HORIZONTAL
                if any(is_solid(material_at(x + dx * step, y, z + dz * step)) for step in range(1, SHELTER_REACH + 1)))
    return walls >= 3


def near_warm_block(placed: list[tuple[int, int, int, str]], x: int, y: int, z: int) -> bool:
    """True when a placed campfire or furnace is within 4 cells of Mimo's cell on every axis."""
    return any(material in WARM_BLOCKS and max(abs(bx - x), abs(by - y), abs(bz - z)) <= FIRE_REACH
               for bx, by, bz, material in placed)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_*.py"`
Expected: `Ran 29 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 79 tests` … `OK`

- [ ] **Step 7: Commit**

```bash
git add backend/survival/__init__.py backend/survival/clock.py backend/survival/vitals.py backend/services/blocks.py backend/tests/test_survival_clock.py backend/tests/test_survival_vitals.py backend/tests/test_blocks.py
git commit -m "feat: add the survival clock and vitals rules" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Egg roll, traits, names and spawn search

**Files:**
- Create: `backend/survival/eggs.py`, `backend/survival/spawn.py`
- Modify: `backend/scripts/worldgen_fixture.py`, `shared/worldgen-fixture.json` (regenerated)
- Test: `backend/tests/test_survival_eggs.py`, `backend/tests/test_survival_spawn.py`, `backend/tests/test_worldgen.py`

**Interfaces:**
- Produces (`backend.survival.eggs`): `TIER_POINTS`, `ATTRIBUTE_POOLS`, `TRAITS` (the 8 trait names), `NAMES`, `roll_tier(rng) -> str`, `rarity_for(total_points: float) -> str`, `egg_name(attributes: list[dict]) -> str`, `roll_egg(rng: random.Random) -> dict` with keys `attributes` (list of `{"category", "option": {"name", "tier", "value"}, "points"}` for shape, scales, color, size, mist), `name`, `totalPoints`, `rarity` (the viewer's `EggProfile` shape without `statRanges`), `trait_floors(egg) -> dict[str, int]`, `roll_traits(egg, rng) -> dict[str, int]`, `pick_name(rng, taken: set[str]) -> str`.
- Produces (`backend.survival.spawn`): `MIN_DISTANCE = 3000`, `MAX_DISTANCE = 6000`, `spawn_fits(x: int, z: int, seed: str) -> bool`, `ring_points(cx, cz, ring, step) -> Iterator[tuple[int, int]]`, `find_spawn(seed: str, rng: random.Random) -> dict` (`{"x", "y", "z"}`, `y` = ground height + 1, the cell Mimo stands in).

The spec lists egg attributes as "shape, scales, color, size, pattern, glow". The viewer's `eggAttributes.ts` (which `EggScene` draws) has shape, scales, color, size and mist, so the server ports exactly those five. Survival worlds reach ±30,000 blocks, so this task also adds far cells to the Python/TypeScript parity fixture.

- [ ] **Step 1: Write the failing egg tests**

Create `backend/tests/test_survival_eggs.py`:

```python
import random
import unittest
from collections import Counter

from backend.survival.eggs import (
    ATTRIBUTE_POOLS, NAMES, TIER_POINTS, TRAITS, egg_name, pick_name, rarity_for, roll_egg, roll_tier,
    roll_traits, trait_floors,
)


def egg_of_tier(tier):
    """An egg whose five attributes all come from one tier."""
    attributes = []
    for category, options in ATTRIBUTE_POOLS:
        name, _, value = next(option for option in options if option[1] == tier)
        attributes.append({"category": category, "option": {"name": name, "tier": tier, "value": value},
                           "points": TIER_POINTS[tier]})
    total = sum(attribute["points"] for attribute in attributes)
    return {"attributes": attributes, "name": egg_name(attributes), "totalPoints": total, "rarity": rarity_for(total)}


class EggTests(unittest.TestCase):
    def test_tiers_follow_the_viewer_probabilities(self):
        rng = random.Random(1)
        counts = Counter(roll_tier(rng) for _ in range(20000))
        for tier, share in (("common", 0.40), ("uncommon", 0.25), ("rare", 0.20), ("legendary", 0.14)):
            self.assertAlmostEqual(counts[tier] / 20000, share, delta=0.015, msg=tier)
        self.assertTrue(0.004 <= counts["mythic"] / 20000 <= 0.017)

    def test_an_egg_has_one_attribute_per_pool_in_the_viewer_shape(self):
        egg = roll_egg(random.Random(7))
        self.assertEqual([attribute["category"] for attribute in egg["attributes"]],
                         ["shape", "scales", "color", "size", "mist"])
        pools = dict(ATTRIBUTE_POOLS)
        for attribute in egg["attributes"]:
            option = attribute["option"]
            self.assertIn((option["name"], option["tier"], option["value"]), pools[attribute["category"]])
            self.assertEqual(attribute["points"], TIER_POINTS[option["tier"]])
        self.assertEqual(egg["totalPoints"], sum(attribute["points"] for attribute in egg["attributes"]))
        self.assertEqual(egg["rarity"], rarity_for(egg["totalPoints"]))
        self.assertEqual(egg["name"], egg_name(egg["attributes"]))

    def test_egg_names_read_like_the_viewer_names(self):
        self.assertEqual(egg_of_tier("uncommon")["name"], "Amber Hexscale Squat")
        self.assertEqual(egg_of_tier("mythic")["name"], "Colossal Iridescent Prismatic Spire")

    def test_rarity_thresholds(self):
        for points, rarity in ((0, "common"), (2, "common"), (2.5, "uncommon"), (4.5, "rare"),
                               (6.5, "legendary"), (8.5, "mythic"), (10, "mythic")):
            self.assertEqual(rarity_for(points), rarity, points)

    def test_the_same_random_state_gives_the_same_egg(self):
        self.assertEqual(roll_egg(random.Random(5)), roll_egg(random.Random(5)))

    def test_rarer_eggs_raise_trait_floors(self):
        common, mythic = trait_floors(egg_of_tier("common")), trait_floors(egg_of_tier("mythic"))
        self.assertEqual(set(common), set(TRAITS))
        self.assertEqual(set(common.values()), {10})
        self.assertEqual(mythic["bravery"], 90)
        self.assertEqual(mythic["creativity"], 90)
        self.assertEqual(mythic["patience"], 70)
        for trait in TRAITS:
            self.assertGreater(mythic[trait], common[trait], trait)

    def test_rolled_traits_respect_their_floors(self):
        rng = random.Random(3)
        for _ in range(200):
            egg = roll_egg(rng)
            traits = roll_traits(egg, rng)
            floors = trait_floors(egg)
            self.assertEqual(set(traits), set(TRAITS))
            for trait, value in traits.items():
                self.assertTrue(floors[trait] <= value <= 100, (trait, value, floors[trait]))

    def test_names_avoid_earlier_lives_until_all_are_used(self):
        rng = random.Random(2)
        self.assertEqual(pick_name(rng, set(NAMES[:-1])), NAMES[-1])
        self.assertIn(pick_name(rng, set(NAMES)), NAMES)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_eggs.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.eggs'`.

- [ ] **Step 3: Port the egg roll**

Create `backend/survival/eggs.py`:

```python
"""Server-side egg roll, ported from the viewer's frontend/src/components/hatch/eggAttributes.ts.

Eggs keep the viewer's EggProfile shape (attributes, name, totalPoints, rarity) so EggScene can
draw the egg the server rolled. Traits come from the egg: rarer eggs raise every trait's floor.
"""

from __future__ import annotations

import random

TIER_PROBABILITIES = (("common", 40), ("uncommon", 25), ("rare", 20), ("legendary", 14), ("mythic", 1))
TIER_POINTS = {"common": 0.0, "uncommon": 0.5, "rare": 1.0, "legendary": 1.5, "mythic": 2.0}
# (name, tier, shader value) per category, in the viewer's order.
ATTRIBUTE_POOLS = (
    ("shape", (("Round", "common", 0), ("Oval", "common", 1), ("Squat", "uncommon", 2),
               ("Elongated", "uncommon", 3), ("Teardrop", "rare", 4), ("Bulbous", "rare", 5),
               ("Gourd", "legendary", 6), ("Spire", "mythic", 7))),
    ("scales", (("Smooth", "common", 0), ("Stippled", "common", 1), ("Hexscale", "uncommon", 2),
                ("Diamond", "uncommon", 3), ("Spiral", "rare", 4), ("Cracked", "rare", 5),
                ("Runic", "legendary", 6), ("Prismatic", "mythic", 7))),
    ("color", (("Stone", "common", 0), ("Moss", "common", 1), ("Amber", "uncommon", 2),
               ("Cobalt", "uncommon", 3), ("Crimson", "rare", 4), ("Violet", "rare", 5),
               ("Obsidian", "legendary", 6), ("Iridescent", "mythic", 7))),
    ("size", (("Tiny", "common", 0), ("Small", "common", 1), ("Standard", "uncommon", 2),
              ("Large", "rare", 3), ("Massive", "legendary", 4), ("Colossal", "mythic", 5))),
    ("mist", (("None", "common", 0), ("Faint", "uncommon", 1), ("Wispy", "rare", 2),
              ("Radiant", "legendary", 3), ("Ethereal", "mythic", 4))),
)
TRAITS = ("curiosity", "creativity", "sociability", "patience", "bravery", "caution", "thrift", "diligence")
RARITY_FLOOR = {"common": 10, "uncommon": 20, "rare": 30, "legendary": 40, "mythic": 50}
# Each attribute nudges two traits, like the viewer's stat biases. Floors rise 10 per tier point.
TRAIT_BIASES = {
    "shape": ("bravery", "diligence"),
    "scales": ("patience", "caution"),
    "color": ("sociability", "creativity"),
    "size": ("bravery", "thrift"),
    "mist": ("curiosity", "creativity"),
}
BIAS_PER_POINT = 10
MAX_FLOOR = 90
NAMES = ("Pip", "Juniper", "Moss", "Tansy", "Bramble", "Fennel", "Clover", "Sorrel", "Wren", "Nettle",
         "Pebble", "Thistle", "Maple", "Hazel", "Quill", "Sprout", "Tuft", "Willow", "Yarrow", "Bean")


def roll_tier(rng: random.Random) -> str:
    roll = rng.random() * 100
    cumulative = 0
    for tier, probability in TIER_PROBABILITIES:
        cumulative += probability
        if roll < cumulative:
            return tier
    return "common"


def rarity_for(total_points: float) -> str:
    if total_points > 8:
        return "mythic"
    if total_points > 6:
        return "legendary"
    if total_points > 4:
        return "rare"
    if total_points > 2:
        return "uncommon"
    return "common"


def egg_name(attributes: list[dict]) -> str:
    """Size (unless Standard), color, scales and shape, as the viewer names eggs."""
    names = {attribute["category"]: attribute["option"]["name"] for attribute in attributes}
    parts = [] if names["size"] == "Standard" else [names["size"]]
    return " ".join([*parts, names["color"], names["scales"], names["shape"]])


def roll_egg(rng: random.Random) -> dict:
    attributes = []
    for category, options in ATTRIBUTE_POOLS:
        tier = roll_tier(rng)
        name, _, value = rng.choice([option for option in options if option[1] == tier])
        attributes.append({"category": category, "option": {"name": name, "tier": tier, "value": value},
                           "points": TIER_POINTS[tier]})
    total = sum(attribute["points"] for attribute in attributes)
    return {"attributes": attributes, "name": egg_name(attributes), "totalPoints": total, "rarity": rarity_for(total)}


def trait_floors(egg: dict) -> dict[str, int]:
    floors = {trait: RARITY_FLOOR[egg["rarity"]] for trait in TRAITS}
    for attribute in egg["attributes"]:
        for trait in TRAIT_BIASES[attribute["category"]]:
            floors[trait] += round(attribute["points"] * BIAS_PER_POINT)
    return {trait: min(MAX_FLOOR, floor) for trait, floor in floors.items()}


def roll_traits(egg: dict, rng: random.Random) -> dict[str, int]:
    return {trait: rng.randint(floor, 100) for trait, floor in trait_floors(egg).items()}


def pick_name(rng: random.Random, taken: set[str] | frozenset[str] = frozenset()) -> str:
    """A name no earlier life used, until every name has been used once."""
    fresh = [name for name in NAMES if name not in taken]
    return rng.choice(fresh or list(NAMES))
```

- [ ] **Step 4: Run the egg tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_eggs.py"`
Expected: `Ran 8 tests` … `OK`

- [ ] **Step 5: Write the failing spawn tests**

Create `backend/tests/test_survival_spawn.py`:

```python
import math
import random
import unittest

from backend.services.blocks import is_replaceable
from backend.services.worldgen import SEA_LEVEL, biome_at, block_at, surface_material, terrain_height, trees_in_chunk
from backend.survival.spawn import MAX_DISTANCE, MIN_DISTANCE, find_spawn, ring_points, spawn_fits

SEEDS = ("1", "123456789123456789", "987654321987654321")


def trees_within(x, z, seed, reach):
    found = []
    for cx in range((x - reach) // 16 - 1, (x + reach) // 16 + 2):
        for cz in range((z - reach) // 16 - 1, (z + reach) // 16 + 2):
            found += [tree for tree in trees_in_chunk(cx, cz, seed) if math.hypot(tree[0] - x, tree[1] - z) <= reach]
    return found


class SpawnTests(unittest.TestCase):
    def test_spawn_follows_every_rule(self):
        for index, seed in enumerate(SEEDS):
            spawn = find_spawn(seed, random.Random(index))
            x, y, z = spawn["x"], spawn["y"], spawn["z"]
            self.assertTrue(MIN_DISTANCE <= math.hypot(x, z) <= MAX_DISTANCE, spawn)
            self.assertIn(biome_at(x, z, seed), ("meadow", "forest"))
            self.assertIn(surface_material(x, z, seed), ("grass", "moss"))
            self.assertEqual(y, terrain_height(x, z, seed) + 1)
            self.assertGreaterEqual(y - 1, SEA_LEVEL)
            for cell_y in (y, y + 1):
                here = block_at(x, cell_y, z, seed)
                self.assertTrue(is_replaceable(here) and here != "water", (spawn, here))
            self.assertTrue(trees_within(x, z, seed, 24), f"no tree near {spawn}")

    def test_the_same_seed_and_random_state_give_the_same_spawn(self):
        self.assertEqual(find_spawn("42", random.Random(9)), find_spawn("42", random.Random(9)))

    def test_spawn_fits_rejects_the_home_region_deserts_and_water(self):
        seed = SEEDS[1]
        self.assertFalse(spawn_fits(100, 0, seed))
        desert = water = None
        for x in range(3100, 5900, 23):
            for z in range(-2000, 2000, 29):
                if not MIN_DISTANCE <= math.hypot(x, z) <= MAX_DISTANCE:
                    continue
                if desert is None and biome_at(x, z, seed) == "desert":
                    desert = (x, z)
                if water is None and terrain_height(x, z, seed) < SEA_LEVEL:
                    water = (x, z)
            if desert and water:
                break
        self.assertIsNotNone(desert)
        self.assertIsNotNone(water)
        self.assertFalse(spawn_fits(*desert, seed))
        self.assertFalse(spawn_fits(*water, seed))

    def test_ring_points_walk_the_square_perimeter(self):
        self.assertEqual(list(ring_points(0, 0, 0, 4)), [(0, 0)])
        ring = list(ring_points(10, 20, 1, 1))
        self.assertEqual(len(ring), 8)
        self.assertEqual(set(ring), {(10 + dx, 20 + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)} - {(10, 20)})
        wide = list(ring_points(0, 0, 2, 4))
        self.assertEqual(len(wide), 16)
        self.assertEqual(len(set(wide)), 16)
        self.assertTrue(all(max(abs(x), abs(z)) == 8 for x, z in wide))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 6: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_spawn.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.spawn'`.

- [ ] **Step 7: Write the spawn search**

Create `backend/survival/spawn.py`:

```python
"""Where a new life starts: 3,000-6,000 blocks from the origin, on dry grass or moss in a meadow
or forest, with a tree within 24 blocks. The search spirals outward from a random point."""

from __future__ import annotations

import math
import random
from typing import Iterator

from backend.services.blocks import is_replaceable
from backend.services.worldgen import SEA_LEVEL, biome_at, block_at, surface_material, terrain_height, trees_in_chunk

MIN_DISTANCE = 3000
MAX_DISTANCE = 6000
TREE_REACH = 24
SEARCH_STEP = 4
MAX_RINGS = 200
MAX_ATTEMPTS = 8
SPAWN_BIOMES = ("meadow", "forest")
SPAWN_SURFACES = ("grass", "moss")
CHUNK = 16


def tree_near(x: int, z: int, seed: str, reach: int = TREE_REACH) -> bool:
    for cx in range((x - reach) // CHUNK, (x + reach) // CHUNK + 1):
        for cz in range((z - reach) // CHUNK, (z + reach) // CHUNK + 1):
            if any(math.hypot(tx - x, tz - z) <= reach for tx, tz, _ in trees_in_chunk(cx, cz, seed)):
                return True
    return False


def spawn_fits(x: int, z: int, seed: str) -> bool:
    if not MIN_DISTANCE <= math.hypot(x, z) <= MAX_DISTANCE:
        return False
    height = terrain_height(x, z, seed)
    if height < SEA_LEVEL:
        return False
    if biome_at(x, z, seed) not in SPAWN_BIOMES or surface_material(x, z, seed) not in SPAWN_SURFACES:
        return False
    for y in (height + 1, height + 2):
        here = block_at(x, y, z, seed)
        if here == "water" or not is_replaceable(here):
            return False
    return tree_near(x, z, seed)


def ring_points(cx: int, cz: int, ring: int, step: int) -> Iterator[tuple[int, int]]:
    """Points on the square ring `ring` steps out from (cx, cz), each corner once."""
    if ring == 0:
        yield cx, cz
        return
    reach = ring * step
    for i in range(-ring, ring):
        yield cx + i * step, cz - reach
    for i in range(-ring, ring):
        yield cx + reach, cz + i * step
    for i in range(-ring, ring):
        yield cx - i * step, cz + reach
    for i in range(-ring, ring):
        yield cx - reach, cz - i * step


def find_spawn(seed: str, rng: random.Random) -> dict:
    """The cell Mimo stands in at birth: {"x", "y", "z"} with y one above the ground."""
    for _ in range(MAX_ATTEMPTS):
        angle = rng.uniform(0, 2 * math.pi)
        distance = rng.uniform(MIN_DISTANCE, MAX_DISTANCE)
        start_x, start_z = round(math.cos(angle) * distance), round(math.sin(angle) * distance)
        for ring in range(MAX_RINGS + 1):
            for x, z in ring_points(start_x, start_z, ring, SEARCH_STEP):
                if spawn_fits(x, z, seed):
                    return {"x": x, "y": terrain_height(x, z, seed) + 1, "z": z}
    raise RuntimeError("No spawn point fits this world seed")
```

- [ ] **Step 8: Run the spawn tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_spawn.py"`
Expected: `Ran 4 tests` … `OK` (each spawn search takes well under a second).

- [ ] **Step 9: Write the failing far-cell fixture test**

Add this test to `FixtureTests` in `backend/tests/test_worldgen.py`, after `test_fixture_covers_generated_trees_at_negative_x`:

```python
    def test_fixture_covers_far_survival_coordinates(self):
        fixture = json.loads(FIXTURE_PATH.read_text())
        oak_log = fixture["materials"].index("oak_log")
        far = [cell for cell in fixture["cells"] if max(abs(cell[1]), abs(cell[3])) >= 2500]
        self.assertGreater(len(far), 1000)
        self.assertTrue(any(cell[4] == oak_log for cell in far), "fixture has no far oak_log cells")
        self.assertTrue(any(max(abs(cell[1]), abs(cell[3])) >= 25000 for cell in far))
```

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen.py"`
Expected: 1 failure in `test_fixture_covers_far_survival_coordinates` (`AssertionError: 0 not greater than 1000`).

- [ ] **Step 10: Sample far cells in the fixture**

In `backend/scripts/worldgen_fixture.py`, replace:

```python
WILD_NEG_CHUNKS = [(cx, cz) for cz in range(-15, 15) for cx in range(-46, -16)]
```

with:

```python
WILD_NEG_CHUNKS = [(cx, cz) for cz in range(-15, 15) for cx in range(-46, -16)]
# Survival lives spawn 3,000-6,000 blocks out and may roam to the +/-30,000 limit.
FAR_CHUNKS = [(cx, cz) for cz in range(-8, 8) for cx in range(250, 270)]
FAR_LIMIT = 30000
```

and in `sample_cells`, replace:

```python
        for _ in range(1500):
            cells.add((seed, rng.randint(-700, 700), rng.randint(-8, 40), rng.randint(-700, 700)))
```

with (a separate random generator, so every existing cell stays the same):

```python
        for _ in range(1500):
            cells.add((seed, rng.randint(-700, 700), rng.randint(-8, 40), rng.randint(-700, 700)))
    far = random.Random(11)
    for seed in SEEDS:
        for tx, tz, base in _trees(seed, FAR_CHUNKS, 2):
            cells |= {(seed, tx + dx, base + dy, tz + dz)
                      for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 8)}
        for _ in range(600):
            x = far.choice((-1, 1)) * far.randint(2500, FAR_LIMIT)
            z = far.randint(-FAR_LIMIT, FAR_LIMIT)
            cells.add((seed, x, far.randint(-8, terrain_height(x, z, seed) + 8), z))
```

- [ ] **Step 11: Regenerate the fixture and check both languages**

Run: `python3 -m backend.scripts.worldgen_fixture`
Expected: `Wrote 18881 cells to …/shared/worldgen-fixture.json`

Run: `python3 -m unittest discover -s backend/tests -p "test_worldgen.py"`
Expected: `Ran 11 tests` … `OK`

Run: `cd frontend && npx vitest run src/engine/worldgen.test.ts`
Expected: `Tests  8 passed (8)`. The TypeScript worldgen agrees with Python at far coordinates. If it does not, stop and report: the viewer would draw different terrain from the one the server simulates.

- [ ] **Step 12: Run the whole backend suite**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 92 tests` … `OK`

- [ ] **Step 13: Commit**

```bash
git add backend/survival/eggs.py backend/survival/spawn.py backend/scripts/worldgen_fixture.py shared/worldgen-fixture.json backend/tests/test_survival_eggs.py backend/tests/test_survival_spawn.py backend/tests/test_worldgen.py
git commit -m "feat: roll eggs and find spawn points for survival lives" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Shared block table and the survival world store

**Files:**
- Create: `backend/services/block_table.py`, `backend/survival/world.py`
- Modify: `backend/services/live_mimo.py` (imports, `resolve_block`/`_material_in` move out, `MimoStore.__init__`, `connect`, `_write_block`, `initialize`, `snapshot`, `blocks_since`)
- Test: `backend/tests/test_survival_world.py` (every existing test must keep passing unchanged)

**Interfaces:**
- Consumes: `START_VITALS` (Task 1).
- Produces (`backend.services.block_table`): `open_db(path, read_only=False)` (context manager; read-only opens `file:…?mode=ro` and never writes), `create_block_tables(db)`, `write_block(db, x, y, z, material) -> int`, `blocks_seq(db) -> int`, `read_blocks_since(db, since, limit=5000) -> dict`, `resolve_block(x, y, z, seed, edits) -> str`, `material_in(db, x, y, z, seed) -> str`.
- Produces (`backend.services.live_mimo`): `MimoStore(path=None, read_only=False)`. With `read_only=True` it never creates, migrates or writes the file; `snapshot()`, `blocks_since()` and `material_at()` still work.
- Produces (`backend.survival.world`): `COORDINATE_LIMIT = 30_000`, `WorldMissing`, `LifeOver`, `new_survival_state(*, name, seed, spawn, born_at, traits) -> dict` (keys: `name`, `world_seed`, `born_at`, `traits`, `position`, `vitals`, `status`, `last_thought`, `inventory`, `last_tick_at`, `last_hello_at`, `care` `{"day", "snack", "bandage"}`, `died_at`, `cause`), `read_state(db)`, `write_state(db, state)`, `log_event(db, at, kind, text)`, `placed_near(db, position, reach, materials) -> list[tuple[int, int, int, str]]`, and `SurvivalWorld(path, read_only=False)` with `create(path, state)` (classmethod), `seed`, `connect()`, `transaction()` (context manager with `BEGIN IMMEDIATE`), `state()`, `events(limit=12)`, `blocks_seq()`, `blocks_since(since, limit=5000)`, `material_at(x, y, z)`, `put_block(x, y, z, material)`, `greet(timestamp) -> {"mood", "noticed_at"}`, `owner_action(action, item, timestamp) -> {"message", "inventory"}`.

A survival world database has the same `mimo_blocks`, `mimo_meta` and `mimo_events` tables as the legacy file, plus a one-row `survival_state` table. The legacy schema does not change: `create_block_tables` runs exactly the statements `MimoStore.initialize` ran before.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_world.py`:

```python
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.services.live_mimo import MimoStore
from backend.services.worldgen import block_at, terrain_height
from backend.survival.world import (
    LifeOver, SurvivalWorld, WorldMissing, new_survival_state, read_state, write_state,
)

SEED = "123456789123456789"
SPAWN = {"x": 3682, "y": 5, "z": 4143}


def file_fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest(), Path(path).stat().st_mtime_ns


class SurvivalWorldTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "lives" / "2.sqlite3"
        self.world = SurvivalWorld.create(self.path, new_survival_state(
            name="Pip", seed=SEED, spawn=SPAWN, born_at=1000.0, traits={"curiosity": 50}))

    def tearDown(self):
        self.directory.cleanup()

    def set_state(self, **changes):
        with self.world.transaction() as db:
            state = read_state(db)
            state.update(changes)
            write_state(db, state)

    def test_a_new_world_starts_with_full_vitals_and_a_birth_event(self):
        state = SurvivalWorld(self.path).state()
        self.assertEqual(state["name"], "Pip")
        self.assertEqual(state["position"], {"x": 3682.0, "y": 5.0, "z": 4143.0})
        self.assertEqual(state["vitals"]["health"], 100.0)
        self.assertEqual(state["status"], "idle")
        self.assertIsNone(state["died_at"])
        self.assertEqual(self.world.seed, SEED)
        self.assertEqual([event["kind"] for event in self.world.events()], ["birth"])
        self.assertEqual(self.world.blocks_seq(), 0)

    def test_creating_over_a_leftover_file_keeps_one_birth_event(self):
        again = SurvivalWorld.create(self.path, new_survival_state(
            name="Wren", seed=SEED, spawn=SPAWN, born_at=2000.0, traits={}))
        self.assertEqual(again.state()["name"], "Wren")
        self.assertEqual(len(again.events()), 1)

    def test_blocks_reach_thirty_thousand_and_are_numbered(self):
        self.world.put_block(29_999, 10, -29_999, "stone")
        self.world.put_block(3682, 6, 4143, "lantern")
        with self.assertRaises(ValueError):
            self.world.put_block(30_001, 10, 0, "stone")
        with self.assertRaises(ValueError):
            self.world.put_block(0, 10, 0, "not_a_block")
        page = self.world.blocks_since(0, limit=1)
        self.assertEqual(page["changes"], [{"x": 29_999, "y": 10, "z": -29_999, "material": "stone"}])
        self.assertTrue(page["more"])
        self.assertEqual(self.world.blocks_since(page["seq"])["changes"][0]["material"], "lantern")
        self.assertEqual(self.world.blocks_seq(), 2)

    def test_legacy_worlds_keep_their_old_limit(self):
        store = MimoStore(Path(self.directory.name) / "mimo.sqlite3")
        with self.assertRaises(ValueError):
            store.put_block(4097, 10, 0, "stone")

    def test_material_at_mixes_worldgen_and_edits(self):
        x, z = SPAWN["x"], SPAWN["z"]
        ground = terrain_height(x, z, SEED)
        self.assertEqual(self.world.material_at(x, ground, z), block_at(x, ground, z, SEED))
        self.world.put_block(x, ground, z, "air")
        self.assertEqual(self.world.material_at(x, ground, z), "air")

    def test_hello_lifts_mood_and_is_logged(self):
        self.set_state(vitals={**self.world.state()["vitals"], "mood": 97.0})
        result = self.world.greet(1500.0)
        self.assertEqual(result["mood"], 100.0)
        state = self.world.state()
        self.assertEqual(state["last_hello_at"], 1500.0)
        self.assertEqual(self.world.events()[0]["kind"], "hello")

    def test_owner_can_help_craft_and_place_machines(self):
        self.set_state(inventory={"oak_log": 2})
        self.world.owner_action("craft", "planks", 1500.0)
        self.world.owner_action("craft", "crafting_table", 1501.0)
        result = self.world.owner_action("place_machine", "crafting_table", 1502.0)
        self.assertNotIn("crafting_table", result["inventory"])
        changes = self.world.blocks_since(0)["changes"]
        self.assertEqual([change["material"] for change in changes], ["crafting_table"])
        self.assertLessEqual(abs(changes[0]["x"] - SPAWN["x"]) + abs(changes[0]["z"] - SPAWN["z"]), 3)
        self.assertEqual(self.world.events()[0]["kind"], "owner")
        with self.assertRaises(ValueError):
            self.world.owner_action("craft", "furnace", 1503.0)
        with self.assertRaises(ValueError):
            self.world.owner_action("juggle", "planks", 1504.0)

    def test_a_dead_pet_cannot_be_greeted_or_helped(self):
        self.set_state(died_at=1800.0, cause="starvation", status="dead")
        with self.assertRaises(LifeOver):
            self.world.greet(1900.0)
        with self.assertRaises(LifeOver):
            self.world.owner_action("craft", "planks", 1900.0)

    def test_a_missing_world_file_is_reported(self):
        with self.assertRaises(WorldMissing):
            SurvivalWorld(Path(self.directory.name) / "lives" / "99.sqlite3")

    def test_read_only_worlds_cannot_be_written(self):
        archive = SurvivalWorld(self.path, read_only=True)
        self.assertEqual(archive.state()["name"], "Pip")
        with self.assertRaises(sqlite3.OperationalError):
            archive.put_block(3682, 6, 4143, "stone")

    def test_read_only_legacy_store_leaves_the_file_untouched(self):
        legacy_path = Path(self.directory.name) / "legacy.sqlite3"
        MimoStore(legacy_path).put_block(80, 20, 0, "stone")
        before = file_fingerprint(legacy_path)
        archive = MimoStore(legacy_path, read_only=True)
        self.assertEqual(archive.snapshot()["plans"][0]["kind"], "station")
        self.assertEqual(archive.blocks_since(0)["changes"], [{"x": 80, "y": 20, "z": 0, "material": "stone"}])
        self.assertEqual(file_fingerprint(legacy_path), before)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_world.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.world'`.

- [ ] **Step 3: Create the shared block table**

Create `backend/services/block_table.py` (the SQL is moved verbatim from `MimoStore`):

```python
"""The block table every world database shares: one row per edited cell, numbered by `seq`.

The legacy world (live_mimo.MimoStore) and every survival world (backend.survival.world) keep
their block edits here, so the viewer can page changes the same way for any life.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.services.blocks import is_plant
from backend.services.worldgen import base_material


@contextmanager
def open_db(path: str | Path, read_only: bool = False) -> Iterator[sqlite3.Connection]:
    """A connection that commits when the block succeeds. Read-only connections never write the file."""
    if read_only:
        connection = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True, timeout=10)
    else:
        connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    if not read_only:
        connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=10000")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def create_block_tables(db: sqlite3.Connection) -> None:
    """Create or migrate mimo_blocks and mimo_meta. Run it inside the caller's BEGIN IMMEDIATE."""
    db.execute("CREATE TABLE IF NOT EXISTS mimo_blocks (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, material TEXT NOT NULL, seq INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(x,y,z))")
    db.execute("CREATE TABLE IF NOT EXISTS mimo_meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
    if "seq" not in {row["name"] for row in db.execute("PRAGMA table_info(mimo_blocks)")}:
        # Worlds saved before block sync get sequence numbers in row order.
        db.execute("ALTER TABLE mimo_blocks ADD COLUMN seq INTEGER NOT NULL DEFAULT 0")
        db.execute("UPDATE mimo_blocks SET seq = rowid")
    db.execute("CREATE INDEX IF NOT EXISTS mimo_blocks_by_seq ON mimo_blocks(seq)")
    db.execute("INSERT OR IGNORE INTO mimo_meta(key, value) VALUES('blocks_seq', 0)")
    db.execute("UPDATE mimo_meta SET value = MAX(value, (SELECT COALESCE(MAX(seq), 0) FROM mimo_blocks)) WHERE key='blocks_seq'")


def write_block(db: sqlite3.Connection, x: int, y: int, z: int, material: str) -> int:
    """Every block write goes through here so viewers can fetch changes by seq."""
    db.execute("UPDATE mimo_meta SET value = value + 1 WHERE key='blocks_seq'")
    seq = db.execute("SELECT value FROM mimo_meta WHERE key='blocks_seq'").fetchone()["value"]
    db.execute("INSERT INTO mimo_blocks(x,y,z,material,seq) VALUES(?,?,?,?,?) "
               "ON CONFLICT(x,y,z) DO UPDATE SET material=excluded.material, seq=excluded.seq",
               (x, y, z, material, seq))
    return seq


def blocks_seq(db: sqlite3.Connection) -> int:
    return db.execute("SELECT value FROM mimo_meta WHERE key='blocks_seq'").fetchone()["value"]


def read_blocks_since(db: sqlite3.Connection, since: int, limit: int = 5000) -> dict:
    """Block changes after `since`, oldest first. Removed blocks come back as air."""
    limit = max(1, min(limit, 5000))
    # Read the latest seq first so a write landing mid-query is fetched next time.
    latest = blocks_seq(db)
    rows = db.execute("SELECT x,y,z,material,seq FROM mimo_blocks WHERE seq > ? AND seq <= ? "
                      "ORDER BY seq LIMIT ?", (since, latest, limit + 1)).fetchall()
    more = len(rows) > limit
    rows = rows[:limit]
    return {"seq": rows[-1]["seq"] if more else latest,
            "changes": [{"x": row["x"], "y": row["y"], "z": row["z"], "material": row["material"]} for row in rows],
            "more": more}


def resolve_block(x: int, y: int, z: int, seed: str, edits: dict[tuple[int, int, int], str]) -> str:
    """The material at a cell: its edit if any, else the natural block, with a natural
    plant resolved to air once the cell below it has been edited (dug out or built on)."""
    edit = edits.get((x, y, z))
    if edit is not None:
        return edit
    natural = base_material(x, y, z, seed)
    if is_plant(natural) and (x, y - 1, z) in edits:
        return "air"
    return natural


def material_in(db: sqlite3.Connection, x: int, y: int, z: int, seed: str) -> str:
    """Material at a cell, reading it and the cell below in one query for the plant rule."""
    rows = db.execute("SELECT y, material FROM mimo_blocks WHERE x=? AND z=? AND y IN (?, ?)",
                      (x, z, y, y - 1)).fetchall()
    edits = {(x, row["y"], z): row["material"] for row in rows}
    return resolve_block(x, y, z, seed, edits)
```

- [ ] **Step 4: Point `MimoStore` at the shared block table**

In `backend/services/live_mimo.py`, replace the imports:

```python
from backend.services.blocks import is_plant, is_replaceable
from backend.services.crafting import BLOCKS, RECIPES, SMELTING, add_item, can_harvest, craft, smelt, take_items
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, SEA_LEVEL, WORLD_MAX_Y, WORLD_MIN_Y, base_material, terrain_height,
)
```

with:

```python
from backend.services.block_table import (
    blocks_seq, create_block_tables, material_in as _material_in, open_db, read_blocks_since, resolve_block, write_block,
)
from backend.services.blocks import is_replaceable
from backend.services.crafting import BLOCKS, RECIPES, SMELTING, add_item, can_harvest, craft, smelt, take_items
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, SEA_LEVEL, WORLD_MAX_Y, WORLD_MIN_Y, terrain_height,
)
```

Delete the two functions `resolve_block` and `_material_in` (between `LUNA_ACTION_SCHEMA` and `def now()`); they now come from `block_table`, and `step_loose_blocks`, `owner_action` and `observe_world` keep calling them by the same names.

Replace the start of `MimoStore`, from `def __init__` through the end of `_write_block`:

```python
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("MIMO_DB_PATH") or DEFAULT_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()
        with self.connect() as db:
            saved = json.loads(db.execute("SELECT data FROM mimo_state WHERE id=1").fetchone()["data"])
        self.world_seed = saved.get("world_seed", LEGACY_WORLD_SEED)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _write_block(db: sqlite3.Connection, x: int, y: int, z: int, material: str) -> int:
        """Every block write goes through here so viewers can fetch changes by seq."""
        db.execute("UPDATE mimo_meta SET value = value + 1 WHERE key='blocks_seq'")
        seq = db.execute("SELECT value FROM mimo_meta WHERE key='blocks_seq'").fetchone()["value"]
        db.execute("INSERT INTO mimo_blocks(x,y,z,material,seq) VALUES(?,?,?,?,?) "
                   "ON CONFLICT(x,y,z) DO UPDATE SET material=excluded.material, seq=excluded.seq",
                   (x, y, z, material, seq))
        return seq
```

with:

```python
    def __init__(self, path: str | Path | None = None, read_only: bool = False):
        """Open the legacy world. `read_only=True` never creates, migrates or writes the file."""
        self.path = Path(path or os.environ.get("MIMO_DB_PATH") or DEFAULT_DB)
        self.read_only = read_only
        if not read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.initialize()
        with self.connect() as db:
            saved = json.loads(db.execute("SELECT data FROM mimo_state WHERE id=1").fetchone()["data"])
        self.world_seed = saved.get("world_seed", LEGACY_WORLD_SEED)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with open_db(self.path, self.read_only) as connection:
            yield connection

    _write_block = staticmethod(write_block)
```

In `initialize`, replace these lines:

```python
            db.execute("CREATE TABLE IF NOT EXISTS mimo_blocks (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, material TEXT NOT NULL, seq INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(x,y,z))")
            db.execute("CREATE TABLE IF NOT EXISTS mimo_meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
            if "seq" not in {row["name"] for row in db.execute("PRAGMA table_info(mimo_blocks)")}:
                # Worlds saved before block sync get sequence numbers in row order.
                db.execute("ALTER TABLE mimo_blocks ADD COLUMN seq INTEGER NOT NULL DEFAULT 0")
                db.execute("UPDATE mimo_blocks SET seq = rowid")
            db.execute("CREATE INDEX IF NOT EXISTS mimo_blocks_by_seq ON mimo_blocks(seq)")
            db.execute("INSERT OR IGNORE INTO mimo_meta(key, value) VALUES('blocks_seq', 0)")
            db.execute("UPDATE mimo_meta SET value = MAX(value, (SELECT COALESCE(MAX(seq), 0) FROM mimo_blocks)) WHERE key='blocks_seq'")
```

with:

```python
            create_block_tables(db)
```

In `snapshot`, replace:

```python
            state["blocks_seq"] = db.execute("SELECT value FROM mimo_meta WHERE key='blocks_seq'").fetchone()["value"]
```

with:

```python
            state["blocks_seq"] = blocks_seq(db)
```

Replace the whole `blocks_since` method with:

```python
    def blocks_since(self, since: int, limit: int = 5000) -> dict:
        """Block changes after `since`, oldest first. Removed blocks come back as air."""
        with self.connect() as db:
            return read_blocks_since(db, since, limit)
```

`put_block` keeps its ±4,096 limit: the ±30,000 limit is for survival worlds only.

- [ ] **Step 5: Check the refactor on its own**

Run: `python3 -m unittest discover -s backend/tests -p "test_*.py" -k LiveMimo -k BlockSync`
Expected: `Ran 33 tests` … `OK`. The legacy store behaves exactly as before.

- [ ] **Step 6: Create the survival world store**

Create `backend/survival/world.py`:

```python
"""A survival life's world database: the shared block table, Mimo's state and its events.

Each survival life has its own file (MIMO_DATA_DIR/lives/<id>.sqlite3). The single
survival_state row holds position, vitals, inventory, care budget and death as JSON.
Writers use `transaction()` so the worker's tick and the owner's actions never overwrite
each other.
"""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.services.block_table import (
    blocks_seq, create_block_tables, material_in, open_db, read_blocks_since, write_block,
)
from backend.services.blocks import is_replaceable
from backend.services.crafting import BLOCKS, craft, smelt, take_items
from backend.services.worldgen import WORLD_MAX_Y, WORLD_MIN_Y, terrain_height
from backend.survival.vitals import START_VITALS

COORDINATE_LIMIT = 30_000
BLOCK_TYPES = set(BLOCKS) | {"air"}
STATION_REACH = 6
MACHINES = ("crafting_table", "furnace")
MACHINE_OFFSETS = ((2, 0), (0, 2), (-2, 0), (0, -2), (3, 0), (0, 3), (-3, 0), (0, -3))


class WorldMissing(RuntimeError):
    """The registry points at a world database file that does not exist."""


class LifeOver(RuntimeError):
    """The pet in this world has died, so it cannot be greeted, helped or cared for."""


def new_survival_state(*, name: str, seed: str, spawn: dict, born_at: float, traits: dict) -> dict:
    return {
        "name": name,
        "world_seed": seed,
        "born_at": born_at,
        "traits": traits,
        "position": {"x": float(spawn["x"]), "y": float(spawn["y"]), "z": float(spawn["z"])},
        "vitals": dict(START_VITALS),
        "status": "idle",
        "last_thought": "Everything is new. I wonder what is out there.",
        "inventory": {},
        "last_tick_at": born_at,
        "last_hello_at": None,
        "care": {"day": None, "snack": 0, "bandage": 0},
        "died_at": None,
        "cause": None,
    }


def create_world_tables(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS survival_state (id INTEGER PRIMARY KEY CHECK (id=1), data TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS mimo_events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL)")
    create_block_tables(db)


def read_state(db: sqlite3.Connection) -> dict:
    return json.loads(db.execute("SELECT data FROM survival_state WHERE id=1").fetchone()["data"])


def write_state(db: sqlite3.Connection, state: dict) -> None:
    db.execute("UPDATE survival_state SET data=? WHERE id=1", (json.dumps(state),))


def log_event(db: sqlite3.Connection, at: float, kind: str, text: str) -> None:
    db.execute("INSERT INTO mimo_events(at,kind,text) VALUES(?,?,?)", (at, kind, text))


def placed_near(db: sqlite3.Connection, position: dict, reach: float,
                materials: tuple[str, ...]) -> list[tuple[int, int, int, str]]:
    """Placed blocks of the given materials in the square column around `position`."""
    marks = ",".join("?" * len(materials))
    rows = db.execute(
        f"SELECT x,y,z,material FROM mimo_blocks WHERE material IN ({marks}) "
        "AND x BETWEEN ? AND ? AND z BETWEEN ? AND ?",
        (*materials, math.floor(position["x"] - reach), math.ceil(position["x"] + reach),
         math.floor(position["z"] - reach), math.ceil(position["z"] + reach))).fetchall()
    return [(row["x"], row["y"], row["z"], row["material"]) for row in rows]


class SurvivalWorld:
    def __init__(self, path: str | Path, read_only: bool = False):
        self.path = Path(path)
        self.read_only = read_only
        if not self.path.exists():
            raise WorldMissing(f"World database {self.path} is missing")
        if not read_only:
            with self.transaction() as db:
                create_world_tables(db)
        with self.connect() as db:
            self.seed = read_state(db)["world_seed"]

    @classmethod
    def create(cls, path: str | Path, state: dict) -> "SurvivalWorld":
        """Write a new world file. A leftover file from a failed hatch is taken over."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open_db(path) as db:
            db.execute("BEGIN IMMEDIATE")
            create_world_tables(db)
            db.execute("INSERT OR REPLACE INTO survival_state(id, data) VALUES (1, ?)", (json.dumps(state),))
            if db.execute("SELECT 1 FROM mimo_events LIMIT 1").fetchone() is None:
                log_event(db, state["born_at"], "birth", f"{state['name']} hatched into a brand-new world.")
        return cls(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with open_db(self.path, self.read_only) as connection:
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """One write transaction: read the state, change it and write it back, all or nothing."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def state(self) -> dict:
        with self.connect() as db:
            return read_state(db)

    def events(self, limit: int = 12) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,at,kind,text FROM mimo_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def blocks_seq(self) -> int:
        with self.connect() as db:
            return blocks_seq(db)

    def blocks_since(self, since: int, limit: int = 5000) -> dict:
        with self.connect() as db:
            return read_blocks_since(db, since, limit)

    def material_at(self, x: int, y: int, z: int) -> str:
        with self.connect() as db:
            return material_in(db, x, y, z, self.seed)

    def put_block(self, x: int, y: int, z: int, material: str) -> None:
        if (material not in BLOCK_TYPES or not WORLD_MIN_Y <= y <= WORLD_MAX_Y
                or abs(x) > COORDINATE_LIMIT or abs(z) > COORDINATE_LIMIT):
            raise ValueError("Invalid block position or material")
        with self.connect() as db:
            write_block(db, x, y, z, material)

    def greet(self, timestamp: float) -> dict:
        with self.transaction() as db:
            state = read_state(db)
            if state["died_at"] is not None:
                raise LifeOver(f"{state['name']} has died")
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + 5)
            state["last_hello_at"] = timestamp
            write_state(db, state)
            log_event(db, timestamp, "hello", f"You said hello to {state['name']}.")
            return {"mood": state["vitals"]["mood"], "noticed_at": timestamp}

    def owner_action(self, action: str, item: str, timestamp: float) -> dict:
        """The owner helps craft, place a workstation or smelt, with the legacy station rules."""
        with self.transaction() as db:
            state = read_state(db)
            if state["died_at"] is not None:
                raise LifeOver(f"{state['name']} has died")
            position = state["position"]
            stations = {material for x, _, z, material in placed_near(db, position, STATION_REACH, MACHINES)
                        if math.hypot(x - position["x"], z - position["z"]) <= STATION_REACH}
            if action == "craft":
                state["inventory"] = craft(state["inventory"], item, stations)
                message = f"You crafted {item.replace('_', ' ')} for {state['name']}."
            elif action == "place_machine":
                if item not in MACHINES:
                    raise ValueError("Only a crafting table or furnace can be placed here")
                inventory = take_items(state["inventory"], {item: 1})
                cell = self._machine_cell(db, position)
                write_block(db, *cell, item)
                state["inventory"] = inventory
                message = f"You placed {item.replace('_', ' ')} beside {state['name']}."
            elif action == "smelt":
                state["inventory"] = smelt(state["inventory"], item, stations)
                message = f"You smelted {item.replace('_', ' ')} for {state['name']}."
            else:
                raise ValueError("Unknown owner action")
            write_state(db, state)
            log_event(db, timestamp, "owner", message)
            return {"message": message, "inventory": state["inventory"]}

    def _machine_cell(self, db: sqlite3.Connection, position: dict) -> tuple[int, int, int]:
        px, pz = round(position["x"]), round(position["z"])
        for dx, dz in MACHINE_OFFSETS:
            x, z = px + dx, pz + dz
            y = terrain_height(x, z, self.seed) + 1
            here = material_in(db, x, y, z, self.seed)
            if is_replaceable(here) and here != "water":
                return x, y, z
        raise ValueError("No open block beside the pet for that machine")
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_world.py"`
Expected: `Ran 11 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 103 tests` … `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/services/block_table.py backend/services/live_mimo.py backend/survival/world.py backend/tests/test_survival_world.py
git commit -m "feat: add survival world stores on a shared block table" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Life registry, legacy retirement and hatching

**Files:**
- Create: `backend/survival/registry.py`, `backend/survival/hatch.py`
- Test: `backend/tests/test_survival_lives.py`

**Interfaces:**
- Consumes: `roll_egg`, `roll_traits`, `pick_name` (Task 2), `find_spawn` (Task 2), `SurvivalWorld`, `new_survival_state`, `open_db` (Task 3), `live_mimo.DEFAULT_DB`.
- Produces (`backend.survival.registry`): `LifeConflict`, `data_dir() -> Path` (`MIMO_DATA_DIR`, default `/data`), `legacy_db_path() -> Path` (`MIMO_DB_PATH`, default the old local path), `read_legacy_life(path) -> dict | None`, and `LifeRegistry(directory=None, legacy_path=None, timestamp=None)` with `path`, `directory`, `connect()`, `world_path(life) -> Path`, `list_lives()` (newest first), `get(life_id)`, `active_life()`, `last_life()`, `names() -> set[str]`, `pending_egg(rng, timestamp=None) -> dict`, `create_life(*, name, seed, spawn, born_at, egg, traits) -> dict`, `mark_dead(life_id, died_at, cause)`.
- A life dict has the spec's columns `id`, `name`, `kind`, `db_path`, `seed`, `spawn_x`, `spawn_z`, `born_at`, `died_at`, `cause`, `egg` (dict or None), `traits` (dict), plus `alive: bool`.
- Produces (`backend.survival.hatch`): `hatch(registry, rng=None, timestamp=None) -> dict` (the new life; raises `LifeConflict` while a pet is alive).

Decisions: the legacy life is registered as id 1 (kind `legacy`, cause `retired`, `died_at` = the moment the registry is first created) only when the registry is new and `MIMO_DB_PATH` holds a legacy state row; it is read through `open_db(..., read_only=True)` only. Survival `db_path` values are stored relative to `MIMO_DATA_DIR` (`lives/<id>.sqlite3`) so the data directory can move; the legacy path is stored absolute. The egg is rolled once, stored in a `pending_egg` table the first time anyone asks for it (the egg screen shows it before Hatch is pressed), and used up by `create_life`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_lives.py`:

```python
import hashlib
import math
import random
import tempfile
import unittest
from pathlib import Path

from backend.services.live_mimo import MimoStore
from backend.survival.eggs import TRAITS
from backend.survival.hatch import hatch
from backend.survival.registry import LifeConflict, LifeRegistry
from backend.survival.world import SurvivalWorld


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest(), Path(path).stat().st_mtime_ns


class LifeRegistryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.legacy_path = root / "mimo.sqlite3"
        legacy = MimoStore(self.legacy_path)
        legacy.put_block(80, 20, 0, "stone")
        self.legacy_seed = legacy.world_seed
        self.legacy_before = fingerprint(self.legacy_path)
        self.data = root / "data"
        self.registry = LifeRegistry(self.data, self.legacy_path, timestamp=5000.0)

    def tearDown(self):
        self.directory.cleanup()

    def test_the_legacy_world_becomes_retired_life_one_without_being_touched(self):
        lives = self.registry.list_lives()
        self.assertEqual(len(lives), 1)
        legacy = lives[0]
        self.assertEqual((legacy["id"], legacy["kind"], legacy["name"]), (1, "legacy", "Mimo"))
        self.assertEqual((legacy["died_at"], legacy["cause"]), (5000.0, "retired"))
        self.assertEqual(legacy["seed"], self.legacy_seed)
        self.assertEqual((legacy["spawn_x"], legacy["spawn_z"]), (73, 0))
        self.assertFalse(legacy["alive"])
        self.assertEqual(self.registry.world_path(legacy), self.legacy_path.resolve())
        LifeRegistry(self.data, self.legacy_path, timestamp=9000.0)
        self.assertEqual(len(self.registry.list_lives()), 1)
        MimoStore(self.legacy_path, read_only=True).snapshot()
        self.assertEqual(fingerprint(self.legacy_path), self.legacy_before)
        self.assertIsNone(self.registry.active_life())

    def test_without_a_legacy_file_there_is_no_legacy_life(self):
        empty = LifeRegistry(Path(self.directory.name) / "other", Path(self.directory.name) / "missing.sqlite3")
        self.assertEqual(empty.list_lives(), [])
        self.assertIsNone(empty.last_life())

    def test_the_pending_egg_is_rolled_once_and_kept(self):
        first = self.registry.pending_egg(random.Random(1))
        self.assertEqual(self.registry.pending_egg(random.Random(2)), first)
        self.assertEqual(len(first["attributes"]), 5)

    def test_hatching_creates_a_survival_life_with_its_own_world(self):
        egg = self.registry.pending_egg(random.Random(1))
        life = hatch(self.registry, random.Random(4), timestamp=6000.0)
        self.assertEqual((life["id"], life["kind"], life["born_at"]), (2, "survival", 6000.0))
        self.assertTrue(life["alive"])
        self.assertEqual(life["egg"], egg)
        self.assertEqual(set(life["traits"]), set(TRAITS))
        self.assertEqual(life["db_path"], str(Path("lives") / "2.sqlite3"))
        self.assertTrue(3000 <= math.hypot(life["spawn_x"], life["spawn_z"]) <= 6000)
        state = SurvivalWorld(self.registry.world_path(life)).state()
        self.assertEqual(state["name"], life["name"])
        self.assertEqual(state["world_seed"], life["seed"])
        self.assertEqual((state["position"]["x"], state["position"]["z"]), (life["spawn_x"], life["spawn_z"]))
        self.assertEqual(self.registry.active_life()["id"], 2)
        with self.registry.connect() as db:
            self.assertIsNone(db.execute("SELECT egg FROM pending_egg").fetchone())
        self.assertEqual(fingerprint(self.legacy_path), self.legacy_before)

    def test_an_egg_cannot_hatch_while_a_pet_is_alive(self):
        hatch(self.registry, random.Random(4), timestamp=6000.0)
        with self.assertRaises(LifeConflict):
            hatch(self.registry, random.Random(5), timestamp=6100.0)

    def test_death_is_recorded_once_and_frees_the_next_egg(self):
        first = hatch(self.registry, random.Random(4), timestamp=6000.0)
        self.registry.mark_dead(first["id"], 7000.0, "starvation")
        self.registry.mark_dead(first["id"], 8000.0, "cold")
        dead = self.registry.get(first["id"])
        self.assertEqual((dead["died_at"], dead["cause"], dead["alive"]), (7000.0, "starvation", False))
        self.assertIsNone(self.registry.active_life())
        self.assertEqual(self.registry.last_life()["id"], first["id"])
        second = hatch(self.registry, random.Random(5), timestamp=9000.0)
        self.assertEqual(second["id"], 3)
        self.assertNotEqual(second["name"], first["name"])
        self.assertNotEqual(second["seed"], first["seed"])
        self.assertEqual([life["id"] for life in self.registry.list_lives()], [3, 2, 1])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_lives.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.hatch'`.

- [ ] **Step 3: Create the registry**

Create `backend/survival/registry.py`:

```python
"""The life registry: one row per life in MIMO_DATA_DIR/lives.sqlite3 (default /data).

Life 1 is the legacy world at MIMO_DB_PATH. The first time the survival code starts it is
registered as retired. It is only ever read through read-only connections.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.services.block_table import open_db
from backend.services.live_mimo import DEFAULT_DB
from backend.services.worldgen import LEGACY_WORLD_SEED
from backend.survival.eggs import roll_egg
from backend.survival.world import SurvivalWorld, new_survival_state

LIFE_COLUMNS = ("id", "name", "kind", "db_path", "seed", "spawn_x", "spawn_z", "born_at", "died_at",
                "cause", "egg", "traits")


class LifeConflict(RuntimeError):
    """A pet is already alive, so no egg can hatch."""


def data_dir() -> Path:
    return Path(os.environ.get("MIMO_DATA_DIR") or "/data")


def legacy_db_path() -> Path:
    return Path(os.environ.get("MIMO_DB_PATH") or DEFAULT_DB)


def read_legacy_life(path: Path) -> dict | None:
    """Name, seed, position, birth and traits of the legacy world, read without writing to it."""
    if not path.exists():
        return None
    try:
        with open_db(path, read_only=True) as db:
            row = db.execute("SELECT data FROM mimo_state WHERE id=1").fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    state = json.loads(row["data"])
    return {"name": state.get("name", "Mimo"), "seed": state.get("world_seed", LEGACY_WORLD_SEED),
            "x": round(state["position"]["x"]), "z": round(state["position"]["z"]),
            "born_at": state["born_at"], "traits": state.get("personality", {})}


def _life(row: sqlite3.Row) -> dict:
    life = {key: row[key] for key in LIFE_COLUMNS}
    life["egg"] = json.loads(life["egg"]) if life["egg"] else None
    life["traits"] = json.loads(life["traits"]) if life["traits"] else {}
    life["alive"] = life["died_at"] is None
    return life


class LifeRegistry:
    def __init__(self, directory: str | Path | None = None, legacy_path: str | Path | None = None,
                 timestamp: float | None = None):
        self.directory = Path(directory) if directory is not None else data_dir()
        self.legacy_path = Path(legacy_path) if legacy_path is not None else legacy_db_path()
        self.path = self.directory / "lives.sqlite3"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.initialize(time.time() if timestamp is None else timestamp)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with open_db(self.path) as connection:
            yield connection

    def initialize(self, timestamp: float) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS lives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('legacy', 'survival')),
                db_path TEXT NOT NULL,
                seed TEXT NOT NULL,
                spawn_x INTEGER NOT NULL,
                spawn_z INTEGER NOT NULL,
                born_at REAL NOT NULL,
                died_at REAL,
                cause TEXT,
                egg TEXT,
                traits TEXT NOT NULL)""")
            db.execute("CREATE TABLE IF NOT EXISTS pending_egg (id INTEGER PRIMARY KEY CHECK (id=1), "
                       "egg TEXT NOT NULL, rolled_at REAL NOT NULL)")
            if db.execute("SELECT COUNT(*) AS count FROM lives").fetchone()["count"]:
                return
            legacy = read_legacy_life(self.legacy_path)
            if legacy:
                # Retire today's Mimo as life 1. Its file stays where it is and is never written.
                db.execute("INSERT INTO lives(id,name,kind,db_path,seed,spawn_x,spawn_z,born_at,died_at,cause,egg,traits) "
                           "VALUES (1,?,'legacy',?,?,?,?,?,?,'retired',NULL,?)",
                           (legacy["name"], str(self.legacy_path.resolve()), legacy["seed"], legacy["x"], legacy["z"],
                            legacy["born_at"], timestamp, json.dumps(legacy["traits"])))

    def world_path(self, life: dict) -> Path:
        """Survival worlds are stored relative to the data directory; the legacy path is absolute."""
        path = Path(life["db_path"])
        return path if path.is_absolute() else self.directory / path

    def list_lives(self) -> list[dict]:
        with self.connect() as db:
            return [_life(row) for row in db.execute("SELECT * FROM lives ORDER BY id DESC").fetchall()]

    def get(self, life_id: int) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM lives WHERE id=?", (life_id,)).fetchone()
        return _life(row) if row else None

    def active_life(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM lives WHERE kind='survival' AND died_at IS NULL "
                             "ORDER BY id DESC LIMIT 1").fetchone()
        return _life(row) if row else None

    def last_life(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM lives ORDER BY id DESC LIMIT 1").fetchone()
        return _life(row) if row else None

    def names(self) -> set[str]:
        with self.connect() as db:
            return {row["name"] for row in db.execute("SELECT name FROM lives").fetchall()}

    def pending_egg(self, rng: random.Random, timestamp: float | None = None) -> dict:
        """The egg waiting to hatch. It is rolled once, then kept until it hatches."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT egg FROM pending_egg WHERE id=1").fetchone()
            if row:
                return json.loads(row["egg"])
            egg = roll_egg(rng)
            db.execute("INSERT INTO pending_egg(id, egg, rolled_at) VALUES (1, ?, ?)",
                       (json.dumps(egg), time.time() if timestamp is None else timestamp))
            return egg

    def create_life(self, *, name: str, seed: str, spawn: dict, born_at: float, egg: dict, traits: dict) -> dict:
        """Add a survival life and its world in one step, and use up the pending egg."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM lives WHERE kind='survival' AND died_at IS NULL").fetchone():
                raise LifeConflict("A pet is already alive")
            life_id = db.execute(
                "INSERT INTO lives(name,kind,db_path,seed,spawn_x,spawn_z,born_at,egg,traits) "
                "VALUES (?,'survival','',?,?,?,?,?,?)",
                (name, seed, spawn["x"], spawn["z"], born_at, json.dumps(egg), json.dumps(traits))).lastrowid
            relative = Path("lives") / f"{life_id}.sqlite3"
            SurvivalWorld.create(self.directory / relative, new_survival_state(
                name=name, seed=seed, spawn=spawn, born_at=born_at, traits=traits))
            db.execute("UPDATE lives SET db_path=? WHERE id=?", (str(relative), life_id))
            db.execute("DELETE FROM pending_egg")
            return _life(db.execute("SELECT * FROM lives WHERE id=?", (life_id,)).fetchone())

    def mark_dead(self, life_id: int, died_at: float, cause: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE lives SET died_at=?, cause=? WHERE id=? AND died_at IS NULL", (died_at, cause, life_id))
```

- [ ] **Step 4: Create the hatch step**

Create `backend/survival/hatch.py`:

```python
"""Hatch the pending egg into a new life: new seed, spawn point, traits, name and world."""

from __future__ import annotations

import random
import time

from backend.survival.eggs import pick_name, roll_traits
from backend.survival.registry import LifeConflict, LifeRegistry
from backend.survival.spawn import find_spawn


def hatch(registry: LifeRegistry, rng: random.Random | None = None, timestamp: float | None = None) -> dict:
    rng = rng or random.Random()
    timestamp = time.time() if timestamp is None else timestamp
    if registry.active_life() is not None:
        raise LifeConflict("A pet is already alive")
    egg = registry.pending_egg(rng, timestamp)
    seed = str(rng.getrandbits(64))
    spawn = find_spawn(seed, rng)
    return registry.create_life(name=pick_name(rng, registry.names()), seed=seed, spawn=spawn,
                                born_at=timestamp, egg=egg, traits=roll_traits(egg, rng))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_lives.py"`
Expected: `Ran 6 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 109 tests` … `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/survival/registry.py backend/survival/hatch.py backend/tests/test_survival_lives.py
git commit -m "feat: add the life registry, retire the legacy world and hatch eggs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Survival tick with catch-up, interim sleep and death

**Files:**
- Create: `backend/survival/tick.py`
- Test: `backend/tests/test_survival_tick.py`

**Interfaces:**
- Consumes: `clock_at`, `is_night`, `time_scale`, `DAY_SECONDS` (Task 1); `step_vitals`, `Surroundings`, `is_sheltered`, `near_warm_block`, `EXHAUSTED_BELOW`, `FREEZING_BELOW`, `FIRE_REACH`, `WARM_BLOCKS` (Task 1); `SurvivalWorld`, `read_state`, `write_state`, `log_event`, `placed_near` (Task 3); `LifeRegistry.active_life`, `world_path`, `mark_dead` (Task 4); `material_in` (Task 3); `worldgen.biome_at`.
- Produces (`backend.survival.tick`): `MAX_STEP_SECONDS = 60.0`, `surroundings_at(db, seed, position) -> Surroundings`, `update_sleep(state, night, at, events)`, `note_crossings(state, before, at, events)`, `advance_world(world, timestamp, scale) -> dict` (the saved state), `tick_life(registry, timestamp=None, scale=None) -> dict | None` (None when no pet is alive).

The whole catch-up runs in one `BEGIN IMMEDIATE` transaction, so an owner's snack or hello that arrives during a tick is never lost. Surroundings are computed once per tick because Mimo does not move in M1. Each step reads the clock at its start, applies the interim sleep rule (sleep when energy < 10 or at night; wake when energy ≥ 95 and it is not night), advances vitals, and logs threshold crossings (hunger below 30, hunger at 0, warmth below 20). "Lonely" means no hello for one game day (3,600 game seconds, measured from birth before the first hello). A death stops the loop at that step's end time, logs `"<name> died of <cause> on day <n>."`, and `tick_life` marks the registry row dead so the worker stops ticking the world.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_tick.py`:

```python
import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.tick import advance_world, surroundings_at, tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0


class SurvivalTickTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def change(self, **vitals):
        with self.world.transaction() as db:
            state = read_state(db)
            state["vitals"].update(vitals)
            write_state(db, state)

    def kinds(self):
        return [event["kind"] for event in self.world.events(50)]

    def test_a_tick_drains_hunger_and_saves_the_time(self):
        state = tick_life(self.registry, BORN + 60, scale=1)
        self.assertAlmostEqual(state["vitals"]["hunger"], 100 - 0.84)
        self.assertEqual(state["last_tick_at"], BORN + 60)
        self.assertEqual(self.world.state()["status"], "idle")

    def test_time_scale_speeds_up_every_rate(self):
        state = tick_life(self.registry, BORN + 60, scale=60)
        self.assertAlmostEqual(state["vitals"]["hunger"], 100 - 0.014 * 3600)
        self.assertIn("sleep", self.kinds())

    def test_the_pet_sleeps_at_night_and_wakes_rested_after_dawn(self):
        self.assertEqual(tick_life(self.registry, BORN + 2450, scale=1)["status"], "sleeping")
        self.assertEqual(tick_life(self.registry, BORN + 3700, scale=1)["status"], "idle")
        self.assertEqual(self.kinds()[:2], ["wake", "sleep"])

    def test_an_exhausted_pet_sleeps_by_day_until_rested(self):
        self.change(energy=5.0)
        state = tick_life(self.registry, BORN + 60, scale=1)
        self.assertEqual(state["status"], "sleeping")
        self.assertAlmostEqual(state["vitals"]["energy"], 17.0)
        self.assertEqual(tick_life(self.registry, BORN + 600, scale=1)["status"], "idle")

    def test_a_long_gap_is_caught_up_and_an_unfed_pet_starves(self):
        state = tick_life(self.registry, BORN + 20_000, scale=1)
        self.assertEqual((state["status"], state["cause"]), ("dead", "starvation"))
        self.assertTrue(BORN + 10_100 <= state["died_at"] <= BORN + 10_300, state["died_at"] - BORN)
        self.assertEqual(state["last_tick_at"], state["died_at"])
        life = self.registry.get(self.life["id"])
        self.assertEqual((life["died_at"], life["cause"]), (state["died_at"], "starvation"))
        self.assertIsNone(self.registry.active_life())
        self.assertIsNone(tick_life(self.registry, BORN + 30_000, scale=1))
        self.assertIn(f"{self.life['name']} died of starvation on day 3.", self.world.events()[0]["text"])
        self.assertIn("hungry", self.kinds())
        self.assertIn("starving", self.kinds())

    def test_a_dead_world_is_never_advanced_again(self):
        dead = tick_life(self.registry, BORN + 20_000, scale=1)
        again = advance_world(self.world, BORN + 40_000, 1)
        self.assertEqual(again, dead)

    def test_cold_can_kill_and_archives_the_life(self):
        self.change(health=1.0, warmth=0.0)
        state = tick_life(self.registry, BORN + 60, scale=1)
        self.assertEqual(state["cause"], "cold")
        self.assertEqual(self.registry.get(self.life["id"])["cause"], "cold")

    def test_a_pet_with_its_head_in_water_drowns(self):
        position = self.world.state()["position"]
        self.world.put_block(round(position["x"]), round(position["y"]), round(position["z"]), "water")
        self.change(air=0.0, health=1.0)
        self.assertEqual(tick_life(self.registry, BORN + 60, scale=1)["cause"], "drowning")

    def test_hunger_crossing_thirty_is_logged_with_a_thought(self):
        self.change(hunger=30.5)
        state = tick_life(self.registry, BORN + 60, scale=1)
        self.assertEqual(state["last_thought"], "My tummy is rumbling. I need food.")
        self.assertEqual(self.kinds()[0], "hungry")

    def test_surroundings_see_shelter_fire_and_water(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["position"]["y"] = 100.0
            write_state(db, state)
        position = self.world.state()["position"]
        x, z = round(position["x"]), round(position["z"])
        with self.world.connect() as db:
            open_air = surroundings_at(db, self.world.seed, position)
        self.assertFalse(open_air.sheltered or open_air.near_fire or open_air.head_in_water)
        for cell in ((x, 102, z), (x + 2, 100, z), (x - 2, 100, z), (x, 100, z + 2)):
            self.world.put_block(*cell, "planks")
        self.world.put_block(x + 3, 100, z - 3, "furnace")
        with self.world.connect() as db:
            hut = surroundings_at(db, self.world.seed, position)
        self.assertTrue(hut.sheltered)
        self.assertTrue(hut.near_fire)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_tick.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.tick'`.

- [ ] **Step 3: Write the tick**

Create `backend/survival/tick.py`:

```python
"""One survival tick: bring the active life's world up to now.

The worker calls `tick_life` about once a second. A longer gap (a laptop that slept) is
caught up in steps of at most 60 game seconds, so a pet can starve while nobody watches.
Until the brain arrives (M3) Mimo stands where it hatched and only follows the interim
sleep rule: sleep when exhausted or at night, wake rested after dawn.
"""

from __future__ import annotations

import sqlite3
import time

from backend.services.block_table import material_in
from backend.services.worldgen import biome_at
from backend.survival.clock import DAY_SECONDS, clock_at, is_night, time_scale
from backend.survival.registry import LifeRegistry
from backend.survival.vitals import (
    EXHAUSTED_BELOW, FIRE_REACH, FREEZING_BELOW, WARM_BLOCKS, Surroundings, is_sheltered, near_warm_block,
    step_vitals,
)
from backend.survival.world import SurvivalWorld, log_event, placed_near, read_state, write_state

MAX_STEP_SECONDS = 60.0
WAKE_ENERGY = 95.0
HUNGRY_BELOW = 30.0
CAUSE_TEXT = {"starvation": "starvation", "cold": "the cold", "drowning": "drowning", "fall": "a fall"}

Event = tuple[float, str, str]


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


def update_sleep(state: dict, night: bool, at: float, events: list[Event]) -> None:
    """The interim rule: sleep when exhausted or at night; wake once rested and it is not night."""
    energy = state["vitals"]["energy"]
    if state["status"] == "sleeping":
        if energy >= WAKE_ENERGY and not night:
            state["status"] = "idle"
            state["last_thought"] = "Good morning. I feel rested."
            events.append((at, "wake", f"{state['name']} woke up."))
    elif night or energy < EXHAUSTED_BELOW:
        state["status"] = "sleeping"
        state["last_thought"] = ("It's dark. Time to curl up and sleep." if night
                                 else "I'm too tired to keep my eyes open.")
        events.append((at, "sleep", f"{state['name']} fell asleep."))


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


def advance_world(world: SurvivalWorld, timestamp: float, scale: float) -> dict:
    """Catch the world up to `timestamp` in one transaction and return the saved state."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None or timestamp <= state["last_tick_at"]:
            return state
        surroundings = surroundings_at(db, world.seed, state["position"])
        events: list[Event] = []
        cursor = state["last_tick_at"]
        remaining = (timestamp - cursor) * scale
        while remaining > 1e-9:
            step = min(MAX_STEP_SECONDS, remaining)
            night = is_night(clock_at(state["born_at"], cursor, scale)["phase"])
            update_sleep(state, night, cursor, events)
            last_hello = state["last_hello_at"] or state["born_at"]
            before = state["vitals"]
            state["vitals"], cause = step_vitals(
                before, step, night=night, activity="sleeping" if state["status"] == "sleeping" else "idle",
                surroundings=surroundings, lonely=(cursor - last_hello) * scale > DAY_SECONDS)
            cursor += step / scale
            remaining -= step
            note_crossings(state, before, cursor, events)
            if cause:
                day = clock_at(state["born_at"], cursor, scale)["day_number"]
                state.update(status="dead", died_at=cursor, cause=cause)
                events.append((cursor, "death", f"{state['name']} died of {CAUSE_TEXT[cause]} on day {day}."))
                break
        state["last_tick_at"] = state["died_at"] if state["died_at"] is not None else timestamp
        write_state(db, state)
        for at, kind, text in events:
            log_event(db, at, kind, text)
        return state


def tick_life(registry: LifeRegistry, timestamp: float | None = None, scale: float | None = None) -> dict | None:
    """Advance the active life and archive it if it died. Returns its state, or None if no pet is alive."""
    life = registry.active_life()
    if life is None:
        return None
    timestamp = time.time() if timestamp is None else timestamp
    scale = time_scale() if scale is None else scale
    state = advance_world(SurvivalWorld(registry.world_path(life)), timestamp, scale)
    if state["died_at"] is not None:
        registry.mark_dead(life["id"], state["died_at"], state["cause"])
    return state
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_tick.py"`
Expected: `Ran 10 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 119 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/tick.py backend/tests/test_survival_tick.py
git commit -m "feat: tick the active life with catch-up, sleep and death" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Owner care

**Files:**
- Create: `backend/survival/care.py`
- Test: `backend/tests/test_survival_care.py`

**Interfaces:**
- Consumes: `SurvivalWorld.transaction`, `read_state`, `write_state`, `log_event`, `LifeOver` (Task 3).
- Produces (`backend.survival.care`): `CareRefused`, `utc_day(timestamp) -> str`, `care_remaining(state, timestamp) -> {"snack": int, "bandage": int}`, `give_care(world, kind, timestamp) -> {"kind", "vitals", "remaining"}` (raises `ValueError` for an unknown kind, `LifeOver` for a dead pet, `CareRefused` when today's allowance is used).

The allowance resets at each real UTC midnight and does not follow `MIMO_TIME_SCALE`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_care.py`:

```python
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.survival.care import CareRefused, care_remaining, give_care
from backend.survival.world import LifeOver, SurvivalWorld, new_survival_state, read_state, write_state

NOON = datetime(2026, 9, 23, 12, tzinfo=timezone.utc).timestamp()
DAY = 86400.0


class CareTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.world = SurvivalWorld.create(Path(self.directory.name) / "2.sqlite3", new_survival_state(
            name="Pip", seed="1", spawn={"x": 3000, "y": 5, "z": 0}, born_at=NOON - 3600, traits={}))
        self.set_vitals(hunger=40.0, health=90.0)

    def tearDown(self):
        self.directory.cleanup()

    def set_vitals(self, **vitals):
        with self.world.transaction() as db:
            state = read_state(db)
            state["vitals"].update(vitals)
            write_state(db, state)

    def test_a_fresh_pet_has_one_snack_and_one_bandage_today(self):
        self.assertEqual(care_remaining(self.world.state(), NOON), {"snack": 1, "bandage": 1})

    def test_a_snack_adds_thirty_hunger_once_per_day(self):
        result = give_care(self.world, "snack", NOON)
        self.assertEqual(result["vitals"]["hunger"], 70.0)
        self.assertEqual(result["remaining"], {"snack": 0, "bandage": 1})
        self.assertEqual(self.world.events()[0]["text"], "You gave Pip a snack.")
        self.assertEqual(self.world.state()["last_thought"], "Yum! Thank you.")
        with self.assertRaises(CareRefused):
            give_care(self.world, "snack", NOON + 3600)

    def test_a_bandage_adds_twenty_five_health_capped_at_100(self):
        result = give_care(self.world, "bandage", NOON)
        self.assertEqual(result["vitals"]["health"], 100.0)
        self.assertEqual(result["remaining"], {"snack": 1, "bandage": 0})

    def test_the_allowance_resets_at_the_next_utc_day(self):
        give_care(self.world, "snack", NOON)
        self.assertEqual(care_remaining(self.world.state(), NOON + DAY)["snack"], 1)
        result = give_care(self.world, "snack", NOON + DAY)
        self.assertEqual(result["vitals"]["hunger"], 100.0)

    def test_a_dead_pet_cannot_receive_care(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state.update(died_at=NOON - 60, cause="starvation", status="dead")
            write_state(db, state)
        with self.assertRaises(LifeOver):
            give_care(self.world, "snack", NOON)

    def test_unknown_care_is_rejected(self):
        with self.assertRaises(ValueError):
            give_care(self.world, "massage", NOON)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_care.py"`
Expected: `ModuleNotFoundError: No module named 'backend.survival.care'`.

- [ ] **Step 3: Write the care rules**

Create `backend/survival/care.py`:

```python
"""Owner care: one snack (+30 hunger) and one bandage (+25 health) per real UTC day."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.survival.world import LifeOver, SurvivalWorld, log_event, read_state, write_state

CARE_EFFECTS = {"snack": ("hunger", 30.0), "bandage": ("health", 25.0)}
DAILY_ALLOWANCE = {"snack": 1, "bandage": 1}
CARE_EVENTS = {"snack": "You gave {name} a snack.", "bandage": "You bandaged {name}."}
CARE_THOUGHTS = {"snack": "Yum! Thank you.", "bandage": "That feels much better."}


class CareRefused(RuntimeError):
    """Today's allowance of that kind of care is used up."""


def utc_day(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()


def care_remaining(state: dict, timestamp: float) -> dict[str, int]:
    used = state["care"] if state["care"].get("day") == utc_day(timestamp) else {}
    return {kind: max(0, allowance - used.get(kind, 0)) for kind, allowance in DAILY_ALLOWANCE.items()}


def give_care(world: SurvivalWorld, kind: str, timestamp: float) -> dict:
    if kind not in CARE_EFFECTS:
        raise ValueError("Care must be a snack or a bandage")
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            raise LifeOver(f"{state['name']} has died and cannot receive care")
        if care_remaining(state, timestamp)[kind] <= 0:
            raise CareRefused(f"No {kind} left today. The owner gets a new one each UTC day.")
        today = utc_day(timestamp)
        if state["care"].get("day") != today:
            state["care"] = {"day": today, "snack": 0, "bandage": 0}
        state["care"][kind] += 1
        vital, amount = CARE_EFFECTS[kind]
        state["vitals"][vital] = min(100.0, state["vitals"][vital] + amount)
        state["last_thought"] = CARE_THOUGHTS[kind]
        write_state(db, state)
        log_event(db, timestamp, "care", CARE_EVENTS[kind].format(name=state["name"]))
        return {"kind": kind, "vitals": state["vitals"], "remaining": care_remaining(state, timestamp)}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_care.py"`
Expected: `Ran 6 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 125 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/survival/care.py backend/tests/test_survival_care.py
git commit -m "feat: add the owner's daily snack and bandage" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: API for lives, eggs and care

**Files:**
- Create: `backend/survival/snapshot.py`, `backend/api/lives.py`
- Rewrite: `backend/api/mimo.py`
- Modify: `backend/main.py`, `backend/tests/test_block_sync.py` (last test)
- Test: `backend/tests/test_survival_api.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6; `MimoStore(path, read_only=True)` (Task 3); `crafting.RECIPES`.
- Produces (`backend.survival.snapshot`): `life_row(life, scale, now) -> dict` (the life without `db_path`, plus `days`: the game day number for survival lives, whole real days for the legacy life), `notable(events) -> list[dict]` (up to 6, routine kinds removed), `open_archive(registry, life) -> MimoStore | SurvivalWorld` (read-only), `survival_view(world, now, scale) -> dict`, `alive_snapshot(life, world, now, scale) -> dict`, `life_detail(registry, life, scale, now) -> {"life", "notable_events", "state"}`, `life_summary(registry, life, scale, now) -> dict` (the life row plus `notable_events`).
- Produces (HTTP):
  - `GET /api/mimo` → `{"phase": "alive", "life", "clock", "vitals", "position", "status", "last_thought", "events", "inventory", "recipes", "blocks_seq", "care", "world_seed", "last_tick_at", "server_time", "died_at", "cause"}` or `{"phase": "egg", "egg", "last_life": summary | null, "server_time"}`.
  - `GET /api/mimo/blocks?since=&limit=`, `POST /api/mimo/hello`, `POST /api/mimo/action` (`{"action", "item"}`), `POST /api/mimo/care` (`{"kind": "snack" | "bandage"}`): active life only; 409 when no pet is alive or the pet died, 400 for invalid crafting, 409 when care is used up.
  - `POST /api/lives/hatch` → `{"life", "state"}`; 409 while a pet is alive.
  - `GET /api/lives` → life rows, newest first. `GET /api/lives/{id}` → `{"life", "notable_events", "state"}` where `state` is the legacy snapshot (with `plans`, `currentIndex`, `progress`) for life 1 and a survival view otherwise. `GET /api/lives/{id}/blocks?since=&limit=` → block pages. 404 for an unknown id.
  - 503 with a clear `detail` when the registry or a world file is unavailable.
- Produces (Python): route functions `get_mimo`, `get_mimo_blocks`, `greet_mimo`, `act_with_mimo`, `care_for_mimo`, models `OwnerAction`, `CareRequest` in `backend.api.mimo`; `list_lives`, `hatch_egg`, `get_life`, `get_life_blocks`, `open_registry`, `world_unavailable`, `UNAVAILABLE` in `backend.api.lives`.

`/api/mimo/blocks` now serves the active survival life, so the existing test that read the legacy store through it moves to `/api/lives/1/blocks`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_api.py`:

```python
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.api.lives import get_life, get_life_blocks, hatch_egg, list_lives
from backend.api.mimo import (
    CareRequest, OwnerAction, act_with_mimo, care_for_mimo, get_mimo, get_mimo_blocks, greet_mimo,
)
from backend.services.live_mimo import MimoStore
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state


class SurvivalApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        legacy = MimoStore(root / "mimo.sqlite3")
        legacy.put_block(80, 20, 0, "stone")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def status_of(self, call, *args, **kwargs):
        with self.assertRaises(HTTPException) as caught:
            call(*args, **kwargs)
        return caught.exception.status_code

    def active_world(self):
        registry = LifeRegistry()
        return SurvivalWorld(registry.world_path(registry.active_life()))

    def test_before_the_first_hatch_the_egg_waits_and_mimo_is_retired(self):
        first = get_mimo()
        self.assertEqual(first["phase"], "egg")
        self.assertEqual(len(first["egg"]["attributes"]), 5)
        self.assertEqual(get_mimo()["egg"], first["egg"])
        last = first["last_life"]
        self.assertEqual((last["id"], last["kind"], last["cause"]), (1, "legacy", "retired"))
        self.assertNotIn("db_path", last)
        self.assertEqual(last["days"], 1)
        self.assertEqual(last["notable_events"][0]["kind"], "birth")

    def test_hatching_starts_a_life_that_mimo_reports(self):
        egg = get_mimo()["egg"]
        hatched = hatch_egg()
        self.assertEqual(hatched["life"]["id"], 2)
        self.assertEqual(hatched["life"]["egg"], egg)
        state = get_mimo()
        self.assertEqual(state["phase"], "alive")
        for field in ("life", "clock", "vitals", "position", "status", "last_thought", "events", "inventory",
                      "recipes", "blocks_seq", "care", "server_time"):
            self.assertIn(field, state)
        self.assertEqual(state["clock"]["day_number"], 1)
        self.assertEqual(state["care"], {"snack": 1, "bandage": 1})
        self.assertNotIn("plans", state)
        self.assertEqual(self.status_of(hatch_egg), 409)

    def test_care_hello_and_crafting_help_reach_the_active_life(self):
        hatch_egg()
        self.assertEqual(care_for_mimo(CareRequest(kind="snack"))["remaining"]["snack"], 0)
        self.assertEqual(self.status_of(care_for_mimo, CareRequest(kind="snack")), 409)
        self.assertIn("mood", greet_mimo())
        self.assertEqual(self.status_of(act_with_mimo, OwnerAction(action="craft", item="planks")), 400)
        world = self.active_world()
        with world.transaction() as db:
            state = read_state(db)
            state["inventory"] = {"oak_log": 1}
            write_state(db, state)
        self.assertEqual(act_with_mimo(OwnerAction(action="craft", item="planks"))["inventory"], {"planks": 4})

    def test_without_a_live_pet_care_hello_and_blocks_are_refused(self):
        self.assertEqual(self.status_of(care_for_mimo, CareRequest(kind="bandage")), 409)
        self.assertEqual(self.status_of(greet_mimo), 409)
        self.assertEqual(self.status_of(get_mimo_blocks, since=0, limit=5000), 409)

    def test_block_changes_for_the_active_life_and_the_archives(self):
        hatch_egg()
        position = get_mimo()["position"]
        self.active_world().put_block(round(position["x"]) + 1, round(position["y"]), round(position["z"]), "lantern")
        active = get_mimo_blocks(since=0, limit=5000)
        self.assertEqual([change["material"] for change in active["changes"]], ["lantern"])
        self.assertEqual(get_life_blocks(2, since=0, limit=5000), active)
        self.assertEqual(get_life_blocks(1, since=0, limit=5000)["changes"],
                         [{"x": 80, "y": 20, "z": 0, "material": "stone"}])
        self.assertEqual(self.status_of(get_life_blocks, 99, since=0, limit=5000), 404)

    def test_lives_list_newest_first_with_both_state_shapes(self):
        hatch_egg()
        self.assertEqual([life["id"] for life in list_lives()], [2, 1])
        legacy = get_life(1)
        self.assertEqual(legacy["life"]["kind"], "legacy")
        for field in ("plans", "currentIndex", "progress", "world_seed", "blocks_seq"):
            self.assertIn(field, legacy["state"])
        survival = get_life(2)
        self.assertEqual(survival["life"]["kind"], "survival")
        self.assertIn("vitals", survival["state"])
        self.assertEqual(self.status_of(get_life, 99), 404)

    def test_after_death_the_memorial_data_comes_with_a_new_egg(self):
        born = hatch_egg()["life"]["born_at"]
        tick_life(LifeRegistry(), born + 20_000, scale=1)
        memorial = get_mimo()
        self.assertEqual(memorial["phase"], "egg")
        last = memorial["last_life"]
        self.assertEqual((last["id"], last["cause"], last["days"]), (2, "starvation", 3))
        self.assertEqual(last["notable_events"][0]["kind"], "death")
        self.assertEqual(get_life(2)["state"]["clock"]["day_number"], 3)
        self.assertEqual(self.status_of(care_for_mimo, CareRequest(kind="snack")), 409)

    def test_a_missing_world_file_answers_503(self):
        hatch_egg()
        registry = LifeRegistry()
        registry.world_path(registry.active_life()).unlink()
        self.assertEqual(self.status_of(get_mimo), 503)
        self.assertEqual(self.status_of(get_life, 2), 503)

    def test_an_unwritable_data_dir_answers_503(self):
        blocker = Path(self.directory.name) / "not-a-dir"
        blocker.write_text("x")
        with patch.dict(os.environ, {"MIMO_DATA_DIR": str(blocker / "data")}):
            self.assertEqual(self.status_of(get_mimo), 503)


if __name__ == "__main__":
    unittest.main()
```

In `backend/tests/test_block_sync.py`, replace the last test:

```python
    def test_blocks_endpoint_reads_the_configured_store(self):
        self.store.put_block(80, 20, 0, "stone")
        with patch.dict("os.environ", {"MIMO_DB_PATH": str(self.path)}):
            from backend.api.mimo import get_mimo_blocks
            result = get_mimo_blocks(since=0, limit=5000)
        self.assertEqual(result["changes"], [{"x": 80, "y": 20, "z": 0, "material": "stone"}])
```

with:

```python
    def test_legacy_blocks_endpoint_reads_the_configured_store(self):
        self.store.put_block(80, 20, 0, "stone")
        data_dir = Path(self.directory.name) / "data"
        with patch.dict("os.environ", {"MIMO_DB_PATH": str(self.path), "MIMO_DATA_DIR": str(data_dir)}):
            from backend.api.lives import get_life_blocks
            result = get_life_blocks(1, since=0, limit=5000)
        self.assertEqual(result["changes"], [{"x": 80, "y": 20, "z": 0, "material": "stone"}])
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_api.py"`
Expected: `ModuleNotFoundError: No module named 'backend.api.lives'`.

- [ ] **Step 3: Write the response shapes**

Create `backend/survival/snapshot.py`:

```python
"""The JSON shapes the API returns for lives."""

from __future__ import annotations

import math

from backend.services.crafting import RECIPES
from backend.services.live_mimo import MimoStore
from backend.survival.care import care_remaining
from backend.survival.clock import clock_at
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld

# Everyday events that a memorial or archive card leaves out.
ROUTINE_EVENTS = frozenset({"sleep", "wake", "hello", "error", "rest", "block", "craft", "smelt",
                            "explore", "owner", "plan"})
NOTABLE_LIMIT = 6


def life_row(life: dict, scale: float, now: float) -> dict:
    """A registry row for the viewer: no file path, plus days lived.

    Survival lives count game days (the clock's day number). The legacy life counts real days.
    """
    row = {key: value for key, value in life.items() if key != "db_path"}
    end = life["died_at"] if life["died_at"] is not None else now
    if life["kind"] == "legacy":
        row["days"] = max(1, math.ceil((end - life["born_at"]) / 86400))
    else:
        row["days"] = clock_at(life["born_at"], end, scale)["day_number"]
    return row


def notable(events: list[dict]) -> list[dict]:
    return [event for event in events if event["kind"] not in ROUTINE_EVENTS][:NOTABLE_LIMIT]


def open_archive(registry: LifeRegistry, life: dict) -> MimoStore | SurvivalWorld:
    """A read-only view of any life's world."""
    path = registry.world_path(life)
    if life["kind"] == "legacy":
        return MimoStore(path, read_only=True)
    return SurvivalWorld(path, read_only=True)


def survival_view(world: SurvivalWorld, now: float, scale: float) -> dict:
    """A survival world's state. A dead life's clock stops at its death."""
    state = world.state()
    at = state["died_at"] if state["died_at"] is not None else now
    return {
        "clock": clock_at(state["born_at"], at, scale),
        "vitals": {name: round(value, 2) for name, value in state["vitals"].items()},
        "position": state["position"],
        "status": state["status"],
        "last_thought": state["last_thought"],
        "events": world.events(12),
        "inventory": state["inventory"],
        "recipes": RECIPES,
        "blocks_seq": world.blocks_seq(),
        "care": care_remaining(state, now),
        "world_seed": state["world_seed"],
        "last_tick_at": state["last_tick_at"],
        "server_time": now,
        "died_at": state["died_at"],
        "cause": state["cause"],
    }


def alive_snapshot(life: dict, world: SurvivalWorld, now: float, scale: float) -> dict:
    return {"phase": "alive", "life": life_row(life, scale, now), **survival_view(world, now, scale)}


def life_detail(registry: LifeRegistry, life: dict, scale: float, now: float) -> dict:
    """One life's row, notable events and final state (the legacy snapshot shape for life 1)."""
    archive = open_archive(registry, life)
    if isinstance(archive, MimoStore):
        state = archive.snapshot()
        events = state["events"]
    else:
        state = survival_view(archive, now, scale)
        events = archive.events(40)
    return {"life": life_row(life, scale, now), "notable_events": notable(events), "state": state}


def life_summary(registry: LifeRegistry, life: dict, scale: float, now: float) -> dict:
    detail = life_detail(registry, life, scale, now)
    return {**detail["life"], "notable_events": detail["notable_events"]}
```

- [ ] **Step 4: Write the lives routes**

Create `backend/api/lives.py`:

```python
"""Lives: the registry, hatching and read-only archives of every world."""

from __future__ import annotations

import sqlite3
import time

from fastapi import APIRouter, HTTPException, Query

from backend.survival.clock import time_scale
from backend.survival.hatch import hatch
from backend.survival.registry import LifeConflict, LifeRegistry
from backend.survival.snapshot import alive_snapshot, life_detail, life_row, open_archive
from backend.survival.world import SurvivalWorld, WorldMissing

router = APIRouter()
UNAVAILABLE = (WorldMissing, OSError, sqlite3.Error)


def open_registry() -> LifeRegistry:
    try:
        return LifeRegistry()
    except (OSError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail=f"The life registry is unavailable: {error}") from error


def world_unavailable(life: dict, error: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"{life['name']}'s world is unavailable: {error}")


def find_life(registry: LifeRegistry, life_id: int) -> dict:
    life = registry.get(life_id)
    if life is None:
        raise HTTPException(status_code=404, detail="No life with that id")
    return life


@router.get("/lives")
def list_lives():
    registry, now = open_registry(), time.time()
    return [life_row(life, time_scale(), now) for life in registry.list_lives()]


@router.post("/lives/hatch")
def hatch_egg():
    registry = open_registry()
    try:
        life = hatch(registry)
        world = SurvivalWorld(registry.world_path(life))
    except LifeConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except UNAVAILABLE as error:
        raise HTTPException(status_code=503, detail=f"The new world could not be created: {error}") from error
    now, scale = time.time(), time_scale()
    return {"life": life_row(life, scale, now), "state": alive_snapshot(life, world, now, scale)}


@router.get("/lives/{life_id}")
def get_life(life_id: int):
    registry = open_registry()
    life = find_life(registry, life_id)
    try:
        return life_detail(registry, life, time_scale(), time.time())
    except UNAVAILABLE as error:
        raise world_unavailable(life, error) from error


@router.get("/lives/{life_id}/blocks")
def get_life_blocks(life_id: int, since: int = Query(0, ge=0), limit: int = Query(5000, ge=1, le=5000)):
    registry = open_registry()
    life = find_life(registry, life_id)
    try:
        return open_archive(registry, life).blocks_since(since, limit)
    except UNAVAILABLE as error:
        raise world_unavailable(life, error) from error
```

- [ ] **Step 5: Point `/api/mimo` at the active life**

Replace the whole of `backend/api/mimo.py` with:

```python
"""The active survival life: its state, block changes and the owner's interactions."""

from __future__ import annotations

import random
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.api.lives import UNAVAILABLE, open_registry, world_unavailable
from backend.survival.care import CareRefused, give_care
from backend.survival.clock import time_scale
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import alive_snapshot, life_summary
from backend.survival.world import LifeOver, SurvivalWorld

router = APIRouter()


class OwnerAction(BaseModel):
    action: str
    item: str


class CareRequest(BaseModel):
    kind: Literal["snack", "bandage"]


def active_world(registry: LifeRegistry) -> tuple[dict, SurvivalWorld]:
    life = registry.active_life()
    if life is None:
        raise HTTPException(status_code=409, detail="No pet is alive. Hatch the egg first.")
    try:
        return life, SurvivalWorld(registry.world_path(life))
    except UNAVAILABLE as error:
        raise world_unavailable(life, error) from error


@router.get("/mimo")
def get_mimo():
    registry, now, scale = open_registry(), time.time(), time_scale()
    if registry.active_life() is None:
        last = registry.last_life()
        try:
            summary = life_summary(registry, last, scale, now) if last else None
        except UNAVAILABLE as error:
            raise world_unavailable(last, error) from error
        return {"phase": "egg", "egg": registry.pending_egg(random.Random(), now),
                "last_life": summary, "server_time": now}
    life, world = active_world(registry)
    return alive_snapshot(life, world, now, scale)


@router.get("/mimo/blocks")
def get_mimo_blocks(since: int = Query(0, ge=0), limit: int = Query(5000, ge=1, le=5000)):
    _, world = active_world(open_registry())
    return world.blocks_since(since, limit)


@router.post("/mimo/hello")
def greet_mimo():
    _, world = active_world(open_registry())
    try:
        return world.greet(time.time())
    except LifeOver as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/mimo/action")
def act_with_mimo(request: OwnerAction):
    _, world = active_world(open_registry())
    try:
        return world.owner_action(request.action, request.item, time.time())
    except LifeOver as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/mimo/care")
def care_for_mimo(request: CareRequest):
    _, world = active_world(open_registry())
    try:
        return give_care(world, request.kind, time.time())
    except (LifeOver, CareRefused) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
```

- [ ] **Step 6: Register the lives router**

In `backend/main.py`, replace:

```python
from backend.api.mimo import router as mimo_router
```

with:

```python
from backend.api.lives import router as lives_router
from backend.api.mimo import router as mimo_router
```

and replace:

```python
app.include_router(mimo_router, prefix="/api")
```

with:

```python
app.include_router(mimo_router, prefix="/api")
app.include_router(lives_router, prefix="/api")
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_api.py"`
Expected: `Ran 9 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 134 tests` … `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/survival/snapshot.py backend/api/lives.py backend/api/mimo.py backend/main.py backend/tests/test_survival_api.py backend/tests/test_block_sync.py
git commit -m "feat: serve lives, eggs and care from the API" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Worker ticks only the active survival life

**Files:**
- Rewrite: `backend/workers/mimo_worker.py`
- Modify: `docker-compose.yml`, `.env.example`
- Test: `backend/tests/test_survival_worker.py`

**Interfaces:**
- Consumes: `tick_life` (Task 5), `LifeRegistry`, `data_dir` (Task 4), `WorldMissing` (Task 3).
- Produces (`backend.workers.mimo_worker`): `tick_seconds() -> float` (`MIMO_TICK_SECONDS`, default 1), `run_once(registry, previous, timestamp=None) -> str` (ticks once and logs the status line when it changes), `main()`.

The worker no longer calls the legacy `run_tick`. `load_dotenv()` and `logging.basicConfig()` move into `main()` so importing the module in a test does not load the developer's `.env` into the test process.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_survival_worker.py`:

```python
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.workers.mimo_worker import run_once, tick_seconds


class SurvivalWorkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")

    def tearDown(self):
        self.directory.cleanup()

    def test_without_a_pet_the_worker_waits_and_logs_once(self):
        with self.assertLogs("mimo_worker", level="INFO") as logs:
            line = run_once(self.registry, None)
            self.assertEqual(run_once(self.registry, line), line)
        self.assertEqual(logs.output, ["INFO:mimo_worker:No pet is alive. Waiting for the egg to hatch."])

    def test_the_worker_ticks_the_active_life(self):
        life = hatch(self.registry, random.Random(8), timestamp=1000.0)
        with patch.dict(os.environ, {"MIMO_TIME_SCALE": "1"}):
            line = run_once(self.registry, None, timestamp=1060.0)
            self.assertEqual(line, f"{life['name']} is idle: Everything is new. I wonder what is out there.")
            died = run_once(self.registry, line, timestamp=1000.0 + 20_000)
        self.assertEqual(died, f"{life['name']} died of starvation.")
        self.assertIsNone(self.registry.active_life())

    def test_tick_seconds_defaults_to_one(self):
        with patch.dict(os.environ, {"MIMO_TICK_SECONDS": "0.5"}):
            self.assertEqual(tick_seconds(), 0.5)
        for bad in ("0", "soon"):
            with patch.dict(os.environ, {"MIMO_TICK_SECONDS": bad}):
                self.assertEqual(tick_seconds(), 1.0)
        with patch.dict(os.environ, {}):
            os.environ.pop("MIMO_TICK_SECONDS", None)
            self.assertEqual(tick_seconds(), 1.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_worker.py"`
Expected: `ImportError: cannot import name 'run_once' from 'backend.workers.mimo_worker'`.

- [ ] **Step 3: Rewrite the worker**

Replace the whole of `backend/workers/mimo_worker.py` with:

```python
"""Run the active survival life independently of all browsers.

Run with: python -m backend.workers.mimo_worker
Keep exactly one worker running against a persistent MIMO_DATA_DIR. Each tick brings the
active life up to now (vitals, the interim sleep rule, death). The retired legacy world at
MIMO_DB_PATH is no longer ticked; live_mimo.run_tick stays only for reading old worlds.
"""

from __future__ import annotations

import logging
import os
import signal
import sqlite3
import time

from dotenv import load_dotenv

from backend.survival.registry import LifeRegistry, data_dir
from backend.survival.tick import tick_life
from backend.survival.world import WorldMissing

logger = logging.getLogger("mimo_worker")
stopping = False


def stop(_signum, _frame):
    global stopping
    stopping = True


def tick_seconds() -> float:
    try:
        seconds = float(os.environ.get("MIMO_TICK_SECONDS", "1"))
    except ValueError:
        return 1.0
    return seconds if seconds > 0 else 1.0


def run_once(registry: LifeRegistry, previous: str | None, timestamp: float | None = None) -> str:
    """Tick the active life once. Logs a line when the pet's status changes and returns it."""
    state = tick_life(registry, timestamp)
    if state is None:
        line = "No pet is alive. Waiting for the egg to hatch."
    elif state["died_at"] is not None:
        line = f"{state['name']} died of {state['cause']}."
    else:
        line = f"{state['name']} is {state['status']}: {state['last_thought']}"
    if line != previous:
        logger.info(line)
    return line


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    delay = tick_seconds()
    logger.info("Survival worker started, data dir %s, one tick every %.1f s", data_dir(), delay)
    registry: LifeRegistry | None = None
    previous: str | None = None
    while not stopping:
        try:
            if registry is None:
                registry = LifeRegistry()
            previous = run_once(registry, previous)
        except (WorldMissing, OSError, sqlite3.Error):
            logger.exception("Survival data is unavailable; waiting")
            registry = None
        except Exception:
            logger.exception("Survival tick failed")
        time.sleep(delay)
    logger.info("Survival worker stopped")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s backend/tests -p "test_survival_worker.py"`
Expected: `Ran 3 tests` … `OK`

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 137 tests` … `OK`

- [ ] **Step 5: Configure Compose and the example environment**

In `docker-compose.yml`, in the `api` service `environment`, replace:

```yaml
      MIMO_DB_PATH: /data/mimo.sqlite3
      MIMO_MODEL: ${MIMO_MODEL:-gpt-6-luna}
```

with:

```yaml
      MIMO_DB_PATH: /data/mimo.sqlite3
      MIMO_DATA_DIR: /data
      MIMO_TIME_SCALE: ${MIMO_TIME_SCALE:-1}
      MIMO_MODEL: ${MIMO_MODEL:-gpt-6-luna}
```

Make the same replacement in the `mimo-worker` service `environment` (it has the same two lines), and in `mimo-worker` replace:

```yaml
      MIMO_TICK_SECONDS: ${MIMO_TICK_SECONDS:-5}
```

with:

```yaml
      MIMO_TICK_SECONDS: ${MIMO_TICK_SECONDS:-1}
```

In `.env.example`, replace:

```
MIMO_TICK_SECONDS=5
MIMO_MAX_DECISIONS_PER_DAY=8000
MIMO_MAX_LUNA_DECISIONS_PER_DAY=64
```

with:

```
MIMO_TICK_SECONDS=1
MIMO_MAX_DECISIONS_PER_DAY=8000
MIMO_MAX_LUNA_DECISIONS_PER_DAY=64
# Survival lives. The worker ticks the active life every MIMO_TICK_SECONDS. MIMO_TIME_SCALE
# speeds the clock and every vital for manual tests only (60 makes a game day one real minute).
# The life registry and survival worlds live in MIMO_DATA_DIR (default /data).
MIMO_TIME_SCALE=1
```

Run: `docker compose config --quiet && echo compose-ok`
Expected: `compose-ok`. Do not run `docker compose up` here: that would retire the owner's real Mimo. The first real start is the owner's decision after this plan.

- [ ] **Step 6: Commit**

```bash
git add backend/workers/mimo_worker.py backend/tests/test_survival_worker.py docker-compose.yml .env.example
git commit -m "feat: make the worker tick only the active survival life" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Glow layer and daylight uniform in the engine

**Files:**
- Modify: `frontend/src/engine/mesher.ts`, `frontend/src/engine/workerProtocol.ts`, `frontend/src/engine/columnRenderer.ts`, `frontend/src/engine/BlockWorld.tsx`
- Test: `frontend/src/engine/mesher.test.ts`, `frontend/src/engine/columnRenderer.test.ts`

**Interfaces:**
- Produces (`mesher.ts`): `LayerBuffers.glows: Float32Array`, one value per vertex, 1 for vertices of glowing blocks (registry `glow`: lantern, furnace, lava, and later torches and campfires, in any layer), else 0.
- Produces (`columnRenderer.ts`): `interface DaylightUniform { value: number }`, `applyDaylight(material: THREE.Material, daylight: DaylightUniform): void`, `ColumnRenderer.setDaylight(value: number): void` (clamped to 0..1). Every terrain geometry gets a `glow` attribute.
- Produces (`BlockWorld.tsx`): optional prop `daylight?: () => number`, read every frame (omitted means 1).

The terrain uses `MeshBasicMaterial`, which ignores scene lights. `applyDaylight` patches the three terrain materials with `onBeforeCompile` so the fragment color is multiplied by `mix(uDaylight, 1.0, vGlow)`: one shared uniform darkens terrain at night, and glowing vertices keep full brightness. Fog is applied after this multiply, so the fog color still sets the distance tint.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/engine/mesher.test.ts`, add this test inside `describe('meshColumn', …)`, just before `it('keeps directional face shade on glowing blocks', …)`:

```ts
  it('marks the vertices of glowing blocks, and only those, with glow', () => {
    // Padded x 5, 9 and 12 are world x 4..5, 8..9 and 11..12.
    const result = mesh([[5, 10, 5, 'lantern'], [9, 10, 9, 'stone'], [12, 10, 12, 'lava']])
    const glowsAt = (buffers: LayerBuffers, xs: number[]) =>
      new Set(Array.from(buffers.glows).filter((_, v) => xs.includes(buffers.positions[v * 3])))
    expect(result.opaque.glows).toHaveLength(result.opaque.positions.length / 3)
    expect(result.translucent.glows).toHaveLength(result.translucent.positions.length / 3)
    expect(glowsAt(result.opaque, [4, 5])).toEqual(new Set([1]))
    expect(glowsAt(result.opaque, [8, 9])).toEqual(new Set([0]))
    expect(glowsAt(result.translucent, [11, 12])).toEqual(new Set([1]))
  })

```

In `frontend/src/engine/columnRenderer.test.ts`:

1. Change the import to `import { applyDaylight, ColumnRenderer, MAX_IN_FLIGHT } from './columnRenderer'`.
2. Replace the `empty` and `oneQuad` helpers with:

```ts
const empty = (): LayerBuffers => ({
  positions: new Float32Array(0), uvs: new Float32Array(0), colors: new Float32Array(0), glows: new Float32Array(0),
  indices: new Uint32Array(0),
})
const oneQuad = (): LayerBuffers => ({
  positions: new Float32Array(12), uvs: new Float32Array(8), colors: new Float32Array(12), glows: new Float32Array(4),
  indices: new Uint32Array([0, 1, 2, 0, 2, 3]),
})

/** Run a material's onBeforeCompile on three's own basic shader, as the renderer would. */
function compile(material: THREE.Material) {
  const shader = {
    uniforms: {} as Record<string, THREE.IUniform>,
    vertexShader: THREE.ShaderLib.basic.vertexShader,
    fragmentShader: THREE.ShaderLib.basic.fragmentShader,
  }
  material.onBeforeCompile(shader as unknown as THREE.WebGLProgramParametersWithUniforms, {} as THREE.WebGLRenderer)
  return shader
}
```

3. Add this block just before `describe('ColumnRenderer', …)`:

```ts
describe('applyDaylight', () => {
  it('darkens terrain color by daylight except where a vertex glows', () => {
    const daylight = { value: 0.35 }
    const material = new THREE.MeshBasicMaterial({ vertexColors: true })
    applyDaylight(material, daylight)
    const shader = compile(material)
    expect(shader.uniforms.uDaylight).toBe(daylight)
    expect(shader.vertexShader).toContain('attribute float glow;')
    expect(shader.vertexShader).toContain('vGlow = glow;')
    expect(shader.fragmentShader).toContain('uniform float uDaylight;')
    expect(shader.fragmentShader).toContain('diffuseColor.rgb *= mix(uDaylight, 1.0, vGlow);')
    expect(material.customProgramCacheKey()).toBe('terrain-daylight')
  })
})

```

4. Add this test inside `describe('ColumnRenderer', …)`, before `it('reports a worker crash and cleans up on dispose', …)`:

```ts
  it('installs the glow attribute and drives the terrain daylight uniform', () => {
    const { group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    worker.reply(meshed(worker.posted[0]))
    const mesh = group.children[0] as THREE.Mesh
    expect(mesh.geometry.getAttribute('glow').itemSize).toBe(1)
    renderer.setDaylight(0.35)
    const shader = compile(mesh.material as THREE.Material)
    expect(shader.uniforms.uDaylight.value).toBe(0.35)
    renderer.setDaylight(4)
    expect(shader.uniforms.uDaylight.value).toBe(1)
  })

```

The `compile` helper checks the anchors `#include <common>`, `#include <begin_vertex>` and `#include <color_fragment>` really exist in three's basic shader: if three renamed one, `toContain` fails.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/engine/mesher.test.ts src/engine/columnRenderer.test.ts`
Expected: 3 failures: the mesher has no `glows` buffer yet, `applyDaylight is not a function`, and the installed geometry has no `glow` attribute (`Cannot read properties of undefined (reading 'itemSize')`).

- [ ] **Step 3: Emit glow values from the mesher**

In `frontend/src/engine/mesher.ts`:

Replace the `LayerBuffers` interface with:

```ts
export interface LayerBuffers {
  positions: Float32Array
  uvs: Float32Array
  colors: Float32Array
  /** 1 for vertices of glowing blocks, which daylight must not darken; else 0. One per vertex. */
  glows: Float32Array
  indices: Uint32Array
}
```

Replace the `LayerBuilder` class with:

```ts
class LayerBuilder {
  positions: number[] = []
  uvs: number[] = []
  colors: number[] = []
  glows: number[] = []
  indices: number[] = []

  quad(corners: Vec3[], uv: [number, number, number, number], light: number[], flip: boolean, glow = 0): void {
    const base = this.positions.length / 3
    corners.forEach(([x, y, z], k) => {
      this.positions.push(x, y, z)
      this.uvs.push(CORNER_UV[k][0] ? uv[2] : uv[0], CORNER_UV[k][1] ? uv[3] : uv[1])
      const value = srgbToLinear(Math.min(1, light[k]))
      this.colors.push(value, value, value)
      this.glows.push(glow)
    })
    if (flip) this.indices.push(base + 1, base + 2, base + 3, base + 1, base + 3, base)
    else this.indices.push(base, base + 1, base + 2, base, base + 2, base + 3)
  }

  build(): LayerBuffers {
    return {
      positions: new Float32Array(this.positions),
      uvs: new Float32Array(this.uvs),
      colors: new Float32Array(this.colors),
      glows: new Float32Array(this.glows),
      indices: new Uint32Array(this.indices),
    }
  }
}
```

In `meshColumn`, replace:

```ts
        const wx = x0 + px, wy = WORLD_MIN_Y + layer, wz = z0 + pz
        const blockTint = tint(wx, wy, wz)

        if (kind === LAYER_CUTOUT) {
          const uv = tileUv(faceTiles[id * 6 + SIDE_FACE])
          for (const quad of CROSS) {
            cutout.quad(quad.map(([x, y, z]) => [wx + x, wy + y, wz + z] as Vec3), uv,
              [blockTint, blockTint, blockTint, blockTint], false)
          }
          continue
        }

        const builder = kind === LAYER_OPAQUE ? opaque : translucent
        const glow = GLOW_BY_ID[id] === 1
```

with:

```ts
        const wx = x0 + px, wy = WORLD_MIN_Y + layer, wz = z0 + pz
        const blockTint = tint(wx, wy, wz)
        const glow = GLOW_BY_ID[id] === 1

        if (kind === LAYER_CUTOUT) {
          const uv = tileUv(faceTiles[id * 6 + SIDE_FACE])
          for (const quad of CROSS) {
            cutout.quad(quad.map(([x, y, z]) => [wx + x, wy + y, wz + z] as Vec3), uv,
              [blockTint, blockTint, blockTint, blockTint], false, glow ? 1 : 0)
          }
          continue
        }

        const builder = kind === LAYER_OPAQUE ? opaque : translucent
```

and replace:

```ts
          builder.quad(corners, tileUv(faceTiles[id * 6 + faceIndex]), light, flip)
```

with:

```ts
          builder.quad(corners, tileUv(faceTiles[id * 6 + faceIndex]), light, flip, glow ? 1 : 0)
```

In `frontend/src/engine/workerProtocol.ts`, replace:

```ts
    layer.positions.buffer, layer.uvs.buffer, layer.colors.buffer, layer.indices.buffer,
```

with:

```ts
    layer.positions.buffer, layer.uvs.buffer, layer.colors.buffer, layer.glows.buffer, layer.indices.buffer,
```

- [ ] **Step 4: Add the daylight uniform to the renderer**

In `frontend/src/engine/columnRenderer.ts`, replace the start of `toGeometry`:

```ts
function toGeometry(buffers: LayerBuffers): THREE.BufferGeometry | null {
  if (buffers.indices.length === 0) return null
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(buffers.positions, 3))
  geometry.setAttribute('uv', new THREE.BufferAttribute(buffers.uvs, 2))
  geometry.setAttribute('color', new THREE.BufferAttribute(buffers.colors, 3))
```

with:

```ts
/** A shared uniform: 1 by day, down to 0.35 at night. */
export interface DaylightUniform {
  value: number
}

/**
 * Multiplies a terrain material's color by the daylight uniform. Vertices with the `glow`
 * attribute set to 1 (lanterns, furnaces, lava, later torches and campfires) keep full brightness.
 */
export function applyDaylight(material: THREE.Material, daylight: DaylightUniform): void {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uDaylight = daylight
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float glow;\nvarying float vGlow;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvGlow = glow;')
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform float uDaylight;\nvarying float vGlow;')
      .replace('#include <color_fragment>', '#include <color_fragment>\ndiffuseColor.rgb *= mix(uDaylight, 1.0, vGlow);')
  }
  material.customProgramCacheKey = () => 'terrain-daylight'
}

function toGeometry(buffers: LayerBuffers): THREE.BufferGeometry | null {
  if (buffers.indices.length === 0) return null
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(buffers.positions, 3))
  geometry.setAttribute('uv', new THREE.BufferAttribute(buffers.uvs, 2))
  geometry.setAttribute('color', new THREE.BufferAttribute(buffers.colors, 3))
  geometry.setAttribute('glow', new THREE.BufferAttribute(buffers.glows, 1))
```

In the class fields, replace:

```ts
  private readonly materials: Record<LayerName, THREE.MeshBasicMaterial>
```

with:

```ts
  private readonly materials: Record<LayerName, THREE.MeshBasicMaterial>
  private readonly daylight: DaylightUniform = { value: 1 }
```

In the constructor, right after the closing `}` of `this.materials = { … }`, add:

```ts
    for (const material of Object.values(this.materials)) applyDaylight(material, this.daylight)
```

Add this method just before `tick(delta: number): void {`:

```ts
  /** Terrain brightness: 1 by day, 0.35 at night. Glowing blocks ignore it. */
  setDaylight(value: number): void {
    this.daylight.value = Math.min(1, Math.max(0, value))
  }

```

- [ ] **Step 5: Let `BlockWorld` drive the daylight every frame**

In `frontend/src/engine/BlockWorld.tsx`, add to `BlockWorldProps`, after `viewDistance: number`:

```ts
  /** Called every frame for the terrain brightness (1 day, 0.35 night). Omit for full daylight. */
  daylight?: () => number
```

Change the component signature to:

```ts
export default function BlockWorld({ store, centerX, centerZ, viewDistance, daylight, onStats, onError }: BlockWorldProps) {
```

and in `useFrame`, replace:

```ts
    if (!current) return
    current.tick(delta)
```

with:

```ts
    if (!current) return
    current.setDaylight(daylight ? daylight() : 1)
    current.tick(delta)
```

- [ ] **Step 6: Run the tests, type check and lint**

Run: `cd frontend && npx vitest run src/engine/mesher.test.ts src/engine/columnRenderer.test.ts`
Expected: all pass.

Run: `cd frontend && npm test`
Expected: `Tests  82 passed (82)`

Run: `cd frontend && npm run build && npx eslint src/engine`
Expected: the build succeeds (the existing chunk-size warning is fine) and eslint prints nothing.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/engine/mesher.ts frontend/src/engine/workerProtocol.ts frontend/src/engine/columnRenderer.ts frontend/src/engine/BlockWorld.tsx frontend/src/engine/mesher.test.ts frontend/src/engine/columnRenderer.test.ts
git commit -m "feat: dim terrain at night while glowing blocks keep their light" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Viewer clock, sky, HUD and API helpers

**Files:**
- Create: `frontend/src/survival/types.ts`, `frontend/src/survival/api.ts`, `frontend/src/survival/clock.ts`, `frontend/src/survival/sky.ts`, `frontend/src/survival/hud.ts`
- Test: `frontend/src/survival/clock.test.ts`, `frontend/src/survival/sky.test.ts`, `frontend/src/survival/hud.test.ts`, `frontend/src/survival/api.test.ts`

**Interfaces:**
- Consumes: the HTTP shapes from Task 7.
- Produces (`types.ts`): `ClockPhase`, `VitalName`, `Vitals`, `CareKind`, `CareRemaining`, `Point`, `Clock`, `ServerEgg`, `MimoEvent`, `Recipe`, `LifeRow`, `LifeSummary`, `SurvivalState`, `AliveResponse`, `EggResponse`, `MimoResponse`, `LegacyState`, `LifeDetail`.
- Produces (`api.ts`): `API_URL`, `request<T>(path, init?)` (throws the server's `detail`), `blocksPath(lifeId: number | null, since) -> string`, `fetchMimo()`, `hatchEgg()`, `giveCare(kind)`, `sayHello()`, `helpMimo(action, item)`, `fetchLives()`, `fetchLife(id)`, `blocksFetcher(lifeId: number | null) -> (since) => Promise<BlocksPage>`.
- Produces (`clock.ts`): `DAY_SECONDS`, `PHASES`, `wrapDay(seconds)`, `phaseAt(secondsIntoDay) -> ClockPhase`, `interface LiveClock { dayNumber, secondsIntoDay, phase }`, `liveClock(clock: Clock, receivedAt: number, now: number) -> LiveClock`, `dialPosition(secondsIntoDay) -> { body: 'sun' | 'moon'; progress: number }`.
- Produces (`sky.ts`): `type Rgb`, `DAY_LIGHT = 1`, `NIGHT_LIGHT = 0.35`, `DAY_SKY`, `NIGHT_SKY`, `TWILIGHT_SKY`, `dayness(secondsIntoDay) -> number` (1 day, 0 night), `daylightFactor(secondsIntoDay) -> number` (1.0 day, 0.35 night), `mixRgb(a, b, t)`, `skyColor(secondsIntoDay) -> Rgb`, `rgbToHex(rgb) -> string`.
- Produces (`hud.ts`): `type VitalLevel`, `interface VitalBar { key, label, value, level }`, `HUD_VITALS`, `vitalBars(vitals, names?) -> VitalBar[]`, `dayLabel(dayNumber, phase)`, `clockTime(secondsIntoDay)` (dawn = 06:00), `statusText(status)`, `careLabel(kind, remaining)`, `causeText(cause)`, `daysText(days)`, `lifeLine(life)`, `workerOnline(serverTime, lastTickAt) -> boolean` (true when the last tick is under 10 s old).

Daylight is 1.0 from the end of dawn to the start of dusk, eases down to 0.35 across dusk (smoothstep), stays 0.35 through the night, and eases back up across pre-dawn and dawn as one 360-second sunrise.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/clock.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { dialPosition, liveClock, phaseAt } from './clock'
import type { Clock } from './types'

const clock = (seconds: number, day = 1, scale = 1): Clock => ({
  day_number: day, seconds_into_day: seconds, time_of_day: seconds / 3600, phase: phaseAt(seconds),
  day_seconds: 3600, time_scale: scale,
})

describe('phaseAt', () => {
  it('matches the server phases at every boundary', () => {
    const expected: [number, string][] = [[0, 'dawn'], [179.9, 'dawn'], [180, 'day'], [2219.9, 'day'], [2220, 'dusk'],
      [2400, 'night'], [3419.9, 'night'], [3420, 'pre_dawn'], [3599.9, 'pre_dawn'], [3600, 'dawn'], [-10, 'pre_dawn']]
    for (const [seconds, phase] of expected) expect(phaseAt(seconds), String(seconds)).toBe(phase)
  })
})

describe('liveClock', () => {
  it('moves the server clock forward by the real time since it arrived', () => {
    expect(liveClock(clock(1000), 50, 60)).toEqual({ dayNumber: 1, secondsIntoDay: 1010, phase: 'day' })
  })

  it('applies the time scale and rolls into the next day', () => {
    const next = liveClock(clock(3500, 2, 60), 100, 102)
    expect(next.dayNumber).toBe(3)
    expect(next.secondsIntoDay).toBeCloseTo(20)
    expect(next.phase).toBe('dawn')
  })

  it('never runs backwards when the local clock is behind', () => {
    expect(liveClock(clock(1000), 50, 40).secondsIntoDay).toBe(1000)
  })
})

describe('dialPosition', () => {
  it('shows the sun from dawn to the end of dusk and the moon through the night', () => {
    expect(dialPosition(0)).toEqual({ body: 'sun', progress: 0 })
    expect(dialPosition(1200)).toEqual({ body: 'sun', progress: 0.5 })
    expect(dialPosition(2400)).toEqual({ body: 'moon', progress: 0 })
    expect(dialPosition(3000)).toEqual({ body: 'moon', progress: 0.5 })
  })
})
```

Create `frontend/src/survival/sky.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { DAY_SKY, daylightFactor, mixRgb, NIGHT_SKY, rgbToHex, skyColor } from './sky'

describe('daylightFactor', () => {
  it('is 1.0 by day and 0.35 at night', () => {
    expect(daylightFactor(180)).toBe(1)
    expect(daylightFactor(1500)).toBe(1)
    expect(daylightFactor(2400)).toBeCloseTo(0.35)
    expect(daylightFactor(3000)).toBeCloseTo(0.35)
  })

  it('eases down through dusk', () => {
    expect(daylightFactor(2310)).toBeCloseTo(0.675)
    let previous = daylightFactor(2220)
    for (let s = 2230; s <= 2400; s += 10) {
      const next = daylightFactor(s)
      expect(next).toBeLessThanOrEqual(previous)
      previous = next
    }
  })

  it('eases up through pre-dawn and dawn without a jump at midnight of the game day', () => {
    expect(daylightFactor(3420)).toBeCloseTo(0.35)
    expect(daylightFactor(0)).toBeCloseTo(0.675)
    expect(daylightFactor(3599.99)).toBeCloseTo(daylightFactor(0), 3)
    const samples = [3420, 3480, 3540, 3599, 0, 60, 120, 179].map(daylightFactor)
    for (let i = 1; i < samples.length; i++) expect(samples[i]).toBeGreaterThanOrEqual(samples[i - 1])
  })
})

describe('skyColor', () => {
  it('is the day sky by day and the night sky at night', () => {
    expect(skyColor(1000)).toEqual(DAY_SKY)
    expect(skyColor(3000)).toEqual(NIGHT_SKY)
  })

  it('warms up in the middle of dusk', () => {
    expect(skyColor(2310)[0]).toBeGreaterThan(mixRgb(NIGHT_SKY, DAY_SKY, 0.5)[0])
  })

  it('formats colors as hex', () => {
    expect(rgbToHex(DAY_SKY)).toBe('#dce9eb')
    expect(rgbToHex([0, 15, 255])).toBe('#000fff')
  })
})
```

Create `frontend/src/survival/hud.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { careLabel, causeText, clockTime, dayLabel, lifeLine, statusText, vitalBars, workerOnline } from './hud'

const vitals = { health: 100, hunger: 14.6, warmth: 34, energy: 62.4, air: 100, mood: 70 }

describe('vitalBars', () => {
  it('lists the five HUD vitals, rounded, with a warning level', () => {
    expect(vitalBars(vitals)).toEqual([
      { key: 'health', label: 'Health', value: 100, level: 'ok' },
      { key: 'hunger', label: 'Hunger', value: 15, level: 'low' },
      { key: 'warmth', label: 'Warmth', value: 34, level: 'low' },
      { key: 'energy', label: 'Energy', value: 62, level: 'ok' },
      { key: 'air', label: 'Air', value: 100, level: 'ok' },
    ])
  })

  it('marks vitals past their danger line as critical and clamps to 0..100', () => {
    const bars = vitalBars({ ...vitals, hunger: 0, warmth: 19, health: -3 })
    expect(bars.find((bar) => bar.key === 'hunger')?.level).toBe('critical')
    expect(bars.find((bar) => bar.key === 'warmth')?.level).toBe('critical')
    expect(bars.find((bar) => bar.key === 'health')).toMatchObject({ value: 0, level: 'critical' })
  })
})

describe('HUD text', () => {
  it('names the day and phase', () => {
    expect(dayLabel(3, 'pre_dawn')).toBe('Day 3 · Before dawn')
    expect(dayLabel(1, 'day')).toBe('Day 1 · Day')
  })

  it('shows game time with dawn at 06:00', () => {
    expect(clockTime(0)).toBe('06:00')
    expect(clockTime(2400)).toBe('22:00')
    expect(clockTime(3450)).toBe('05:00')
  })

  it('describes status, care, causes and whether the worker is running', () => {
    expect(statusText('sleeping')).toBe('Sleeping')
    expect(statusText('waiting_for_food')).toBe('waiting for food')
    expect(careLabel('snack', 1)).toBe('Give snack · 1 left today')
    expect(careLabel('bandage', 0)).toBe('Bandage · 0 left today')
    expect(causeText('cold')).toBe('the cold')
    expect(causeText(null)).toBe('unknown causes')
    expect(workerOnline(1005, 1000)).toBe(true)
    expect(workerOnline(1030, 1000)).toBe(false)
  })

  it('sums up a life in one line', () => {
    expect(lifeLine({ kind: 'legacy', alive: false, days: 48, cause: 'retired' })).toBe('Retired after 48 days')
    expect(lifeLine({ kind: 'survival', alive: true, days: 2, cause: null })).toBe('Alive · day 2')
    expect(lifeLine({ kind: 'survival', alive: false, days: 1, cause: 'starvation' }))
      .toBe('Survived 1 day · died of starvation')
  })
})
```

Create `frontend/src/survival/api.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { blocksPath, request } from './api'

afterEach(() => { vi.unstubAllGlobals() })

describe('blocksPath', () => {
  it('pages the active life or an archived one', () => {
    expect(blocksPath(null, 12)).toBe('/api/mimo/blocks?since=12')
    expect(blocksPath(1, 0)).toBe('/api/lives/1/blocks?since=0')
  })
})

describe('request', () => {
  it('returns the JSON body', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ phase: 'egg' }), { status: 200 })))
    await expect(request('/api/mimo')).resolves.toEqual({ phase: 'egg' })
  })

  it("throws the server's detail message", async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'No snack left today.' }), { status: 409 })))
    await expect(request('/api/mimo/care')).rejects.toThrow('No snack left today.')
  })

  it('falls back to the status code when the body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('oops', { status: 503 })))
    await expect(request('/api/mimo')).rejects.toThrow('Server returned 503')
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/survival`
Expected: 4 failed files, each `Failed to resolve import` for `./clock`, `./sky`, `./hud` or `./api`.

- [ ] **Step 3: Write the API types**

Create `frontend/src/survival/types.ts`:

```ts
import type { WorldPlan } from '../components/world/worldPlanner'
import type { AttributeTier } from '../components/hatch/types'
import type { Rarity } from '../data/rarity'

/** Shapes of the survival API (backend/survival/snapshot.py and backend/api). */

export type ClockPhase = 'dawn' | 'day' | 'dusk' | 'night' | 'pre_dawn'
export type VitalName = 'health' | 'hunger' | 'warmth' | 'energy' | 'air' | 'mood'
export type Vitals = Record<VitalName, number>
export type CareKind = 'snack' | 'bandage'
export type CareRemaining = Record<CareKind, number>

export interface Point {
  x: number
  y: number
  z: number
}

export interface Clock {
  day_number: number
  seconds_into_day: number
  time_of_day: number
  phase: ClockPhase
  day_seconds: number
  time_scale: number
}

export interface ServerEgg {
  attributes: { category: string; option: { name: string; tier: AttributeTier; value: number }; points: number }[]
  name: string
  totalPoints: number
  rarity: Rarity
}

export interface MimoEvent {
  id: number
  at: number
  kind: string
  text: string
}

export interface Recipe {
  ingredients: Record<string, number>
  output: Record<string, number>
  station?: string
}

export interface LifeRow {
  id: number
  name: string
  kind: 'legacy' | 'survival'
  seed: string
  spawn_x: number
  spawn_z: number
  born_at: number
  died_at: number | null
  cause: string | null
  egg: ServerEgg | null
  traits: Record<string, number>
  alive: boolean
  /** Game days for survival lives, real days for the legacy life. */
  days: number
}

export interface LifeSummary extends LifeRow {
  notable_events: MimoEvent[]
}

export interface SurvivalState {
  clock: Clock
  vitals: Vitals
  position: Point
  status: string
  last_thought: string
  events: MimoEvent[]
  inventory: Record<string, number>
  recipes: Record<string, Recipe>
  blocks_seq: number
  care: CareRemaining
  world_seed: string
  last_tick_at: number
  server_time: number
  died_at: number | null
  cause: string | null
}

export interface AliveResponse extends SurvivalState {
  phase: 'alive'
  life: LifeRow
}

export interface EggResponse {
  phase: 'egg'
  egg: ServerEgg
  last_life: LifeSummary | null
  server_time: number
}

export type MimoResponse = AliveResponse | EggResponse

/** The retired legacy world's snapshot, as /api/lives/1 returns it. */
export interface LegacyState {
  name: string
  world_seed: string
  position: { x: number; y?: number; z: number }
  plans: WorldPlan[]
  currentIndex: number
  progress: number
  blocks_seq: number
  events: MimoEvent[]
  last_thought: string
}

export interface LifeDetail {
  life: LifeRow
  notable_events: MimoEvent[]
  state: LegacyState | SurvivalState
}
```

- [ ] **Step 4: Write the API helpers**

Create `frontend/src/survival/api.ts`:

```ts
import type { BlocksPage } from '../engine/blockSync'
import type { AliveResponse, CareKind, CareRemaining, LifeDetail, LifeRow, MimoResponse, Vitals } from './types'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/** Fetch JSON from the API. A failed request throws the server's `detail` message when it has one. */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    throw new Error(typeof detail === 'string' ? detail : `Server returned ${response.status}`)
  }
  return body as T
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

/** Block pages for the active life (lifeId null) or any archived life. */
export function blocksPath(lifeId: number | null, since: number): string {
  return lifeId === null ? `/api/mimo/blocks?since=${since}` : `/api/lives/${lifeId}/blocks?since=${since}`
}

export const fetchMimo = () => request<MimoResponse>('/api/mimo')
export const hatchEgg = () => post<{ life: LifeRow; state: AliveResponse }>('/api/lives/hatch')
export const giveCare = (kind: CareKind) =>
  post<{ kind: CareKind; vitals: Vitals; remaining: CareRemaining }>('/api/mimo/care', { kind })
export const sayHello = () => post<{ mood: number; noticed_at: number }>('/api/mimo/hello')
export const helpMimo = (action: string, item: string) =>
  post<{ message: string; inventory: Record<string, number> }>('/api/mimo/action', { action, item })
export const fetchLives = () => request<LifeRow[]>('/api/lives')
export const fetchLife = (id: number) => request<LifeDetail>(`/api/lives/${id}`)
export const blocksFetcher = (lifeId: number | null) => (since: number) => request<BlocksPage>(blocksPath(lifeId, since))
```

- [ ] **Step 5: Write the clock, sky and HUD modules**

Create `frontend/src/survival/clock.ts`:

```ts
import type { Clock, ClockPhase } from './types'

/** The game clock, matching backend/survival/clock.py. */
export const DAY_SECONDS = 3600
export const PHASES: readonly { name: ClockPhase; start: number; end: number }[] = [
  { name: 'dawn', start: 0, end: 180 },
  { name: 'day', start: 180, end: 2220 },
  { name: 'dusk', start: 2220, end: 2400 },
  { name: 'night', start: 2400, end: 3420 },
  { name: 'pre_dawn', start: 3420, end: 3600 },
]
/** The sun is up from dawn to the end of dusk; the moon from night to the end of pre-dawn. */
const SUNSET = 2400

export function wrapDay(seconds: number): number {
  return ((seconds % DAY_SECONDS) + DAY_SECONDS) % DAY_SECONDS
}

export function phaseAt(secondsIntoDay: number): ClockPhase {
  const seconds = wrapDay(secondsIntoDay)
  return PHASES.find((phase) => seconds >= phase.start && seconds < phase.end)?.name ?? 'pre_dawn'
}

export interface LiveClock {
  dayNumber: number
  secondsIntoDay: number
  phase: ClockPhase
}

/** The game clock now, moved forward from the last server clock by the real time since it arrived. */
export function liveClock(clock: Clock, receivedAt: number, now: number): LiveClock {
  const total = clock.seconds_into_day + Math.max(0, now - receivedAt) * clock.time_scale
  const secondsIntoDay = wrapDay(total)
  return { dayNumber: clock.day_number + Math.floor(total / DAY_SECONDS), secondsIntoDay, phase: phaseAt(secondsIntoDay) }
}

/** Where the sun (by day) or the moon (by night) sits on the HUD dial: 0 rising on the left, 1 setting on the right. */
export function dialPosition(secondsIntoDay: number): { body: 'sun' | 'moon'; progress: number } {
  const seconds = wrapDay(secondsIntoDay)
  if (seconds < SUNSET) return { body: 'sun', progress: seconds / SUNSET }
  return { body: 'moon', progress: (seconds - SUNSET) / (DAY_SECONDS - SUNSET) }
}
```

Create `frontend/src/survival/sky.ts`:

```ts
import { DAY_SECONDS, wrapDay } from './clock'

export type Rgb = [number, number, number]

export const DAY_LIGHT = 1
export const NIGHT_LIGHT = 0.35
/** Today's preview sky, a deep night blue, and a warm glow for dusk and dawn. */
export const DAY_SKY: Rgb = [0xdc, 0xe9, 0xeb]
export const NIGHT_SKY: Rgb = [0x1d, 0x26, 0x3b]
export const TWILIGHT_SKY: Rgb = [0xe8, 0xa8, 0x8c]
const DAY_START = 180
const DUSK_START = 2220
const NIGHT_START = 2400
const PRE_DAWN_START = 3420
/** Pre-dawn and dawn together make one 360-second sunrise. */
const SUNRISE_SECONDS = DAY_SECONDS - PRE_DAWN_START + DAY_START

function smoothstep(t: number): number {
  const c = Math.min(1, Math.max(0, t))
  return c * c * (3 - 2 * c)
}

/** 1 in full day, 0 in full night, easing through dusk and through the sunrise. */
export function dayness(secondsIntoDay: number): number {
  const s = wrapDay(secondsIntoDay)
  if (s >= DAY_START && s < DUSK_START) return 1
  if (s >= DUSK_START && s < NIGHT_START) return 1 - smoothstep((s - DUSK_START) / (NIGHT_START - DUSK_START))
  if (s >= NIGHT_START && s < PRE_DAWN_START) return 0
  const sinceSunriseStart = s >= PRE_DAWN_START ? s - PRE_DAWN_START : s + DAY_SECONDS - PRE_DAWN_START
  return smoothstep(sinceSunriseStart / SUNRISE_SECONDS)
}

/** Terrain brightness multiplier: 1.0 by day, 0.35 at night. */
export function daylightFactor(secondsIntoDay: number): number {
  return NIGHT_LIGHT + (DAY_LIGHT - NIGHT_LIGHT) * dayness(secondsIntoDay)
}

export function mixRgb(a: Rgb, b: Rgb, t: number): Rgb {
  return [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * t)) as Rgb
}

/** Sky and fog color: blue-grey by day, deep blue at night, warm in the middle of dusk and sunrise. */
export function skyColor(secondsIntoDay: number): Rgb {
  const light = dayness(secondsIntoDay)
  const twilight = 1 - Math.abs(light - 0.5) * 2
  return mixRgb(mixRgb(NIGHT_SKY, DAY_SKY, light), TWILIGHT_SKY, twilight * 0.45)
}

export function rgbToHex(rgb: Rgb): string {
  return `#${rgb.map((value) => value.toString(16).padStart(2, '0')).join('')}`
}
```

Create `frontend/src/survival/hud.ts`:

```ts
import type { CareKind, ClockPhase, LifeRow, VitalName, Vitals } from './types'

export type VitalLevel = 'ok' | 'low' | 'critical'

export interface VitalBar {
  key: VitalName
  label: string
  value: number
  level: VitalLevel
}

export const HUD_VITALS: VitalName[] = ['health', 'hunger', 'warmth', 'energy', 'air']
const LABELS: Record<VitalName, string> = {
  health: 'Health', hunger: 'Hunger', warmth: 'Warmth', energy: 'Energy', air: 'Air', mood: 'Mood',
}
/** Below `critical` the vital hurts Mimo or is about to; below `low` it needs attention soon. */
const THRESHOLDS: Record<VitalName, { low: number; critical: number }> = {
  health: { low: 50, critical: 25 },
  hunger: { low: 30, critical: 15 },
  warmth: { low: 35, critical: 20 },
  energy: { low: 25, critical: 10 },
  air: { low: 60, critical: 30 },
  mood: { low: 30, critical: 15 },
}
const PHASE_NAMES: Record<ClockPhase, string> = {
  dawn: 'Dawn', day: 'Day', dusk: 'Dusk', night: 'Night', pre_dawn: 'Before dawn',
}
const STATUS_TEXT: Record<string, string> = { idle: 'Standing still', sleeping: 'Sleeping', dead: 'Gone' }
const CAUSES: Record<string, string> = {
  starvation: 'starvation', cold: 'the cold', drowning: 'drowning', fall: 'a fall', creature: 'a creature',
}

export function vitalBars(vitals: Vitals, names: VitalName[] = HUD_VITALS): VitalBar[] {
  return names.map((key) => {
    const value = Math.round(Math.min(100, Math.max(0, vitals[key])))
    const { low, critical } = THRESHOLDS[key]
    return { key, label: LABELS[key], value, level: value < critical ? 'critical' : value < low ? 'low' : 'ok' }
  })
}

export function dayLabel(dayNumber: number, phase: ClockPhase): string {
  return `Day ${dayNumber} · ${PHASE_NAMES[phase]}`
}

/** A 24-hour game time where dawn starts at 06:00. */
export function clockTime(secondsIntoDay: number): string {
  const minutes = Math.floor((((secondsIntoDay / 3600) * 24 + 6) % 24) * 60)
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}

export function statusText(status: string): string {
  return STATUS_TEXT[status] ?? status.replaceAll('_', ' ')
}

export function careLabel(kind: CareKind, remaining: number): string {
  return `${kind === 'snack' ? 'Give snack' : 'Bandage'} · ${remaining} left today`
}

export function causeText(cause: string | null): string {
  return cause ? CAUSES[cause] ?? cause.replaceAll('_', ' ') : 'unknown causes'
}

export function daysText(days: number): string {
  return days === 1 ? '1 day' : `${days} days`
}

/** One line for the memorial and the archive list. */
export function lifeLine(life: Pick<LifeRow, 'kind' | 'alive' | 'days' | 'cause'>): string {
  if (life.kind === 'legacy') return `Retired after ${daysText(life.days)}`
  if (life.alive) return `Alive · day ${life.days}`
  return `Survived ${daysText(life.days)} · died of ${causeText(life.cause)}`
}

/** The worker ticks every second; a state older than 10 s means it stopped. */
export function workerOnline(serverTime: number, lastTickAt: number): boolean {
  return serverTime - lastTickAt < 10
}
```

- [ ] **Step 6: Run the tests, type check and lint**

Run: `cd frontend && npx vitest run src/survival`
Expected: `Test Files  4 passed (4)`, `Tests  21 passed (21)`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival`
Expected: `Tests  103 passed (103)`, the build succeeds, eslint prints nothing.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/survival/types.ts frontend/src/survival/api.ts frontend/src/survival/clock.ts frontend/src/survival/sky.ts frontend/src/survival/hud.ts frontend/src/survival/clock.test.ts frontend/src/survival/sky.test.ts frontend/src/survival/hud.test.ts frontend/src/survival/api.test.ts
git commit -m "feat: add viewer clock, sky, HUD and API helpers for survival" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: The living world with HUD, care and day and night

**Files:**
- Create: `frontend/src/survival/FollowCamera.tsx`, `frontend/src/survival/DayNight.tsx`, `frontend/src/survival/WorldCanvas.tsx`, `frontend/src/survival/SurvivalHud.tsx`, `frontend/src/survival/CraftingPanel.tsx`, `frontend/src/survival/SurvivalWorld.tsx`
- Rewrite: `frontend/src/pages/WorldPreview.tsx`

**Interfaces:**
- Consumes: `BlockWorld` `daylight` prop (Task 9); everything in Task 10; `PetEntity`, `previewPet`, `WorldStore`, `BlockSync`, `fogRange`, `BLOCKS`.
- Produces: `FollowCamera` (the old `BuildCamera` from `WorldPreview.tsx`, unchanged apart from its name); `DayNight({ seconds })` and `PetGlow({ seconds })`; `WorldCanvas({ store, position, seconds?, arrival?, following, onOrbit, onPetClick?, hopSignal? })` (with `seconds` the sky, lights, terrain daylight and pet glow follow the game clock; without it the scene stays in daylight; `arrival` starts the camera 80 blocks up so it flies down to the pet); `SurvivalHud({ state, online, busy, message, onCare, onHello, onFollow, onCrafting, onOpenLives? })`; `CraftingPanel({ name, inventory, recipes, stations, worldSeed, message, onAction, onClose })`; `SurvivalWorld({ state, receivedAt, arrival, connectionError, onChanged, onOpenLives? })`.

This task removes the legacy `LiveWorld` from `/preview`. Its blueprint overlay path comes back, read-only, in the archive (Task 12). The HUD's "current purpose" is the status in plain words until the brain milestone adds purposes. Visual checks of this view happen in Task 14.

- [ ] **Step 1: Move the camera into its own file**

Create `frontend/src/survival/FollowCamera.tsx`:

```tsx
import { useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import type { OrbitControls as OrbitControlsType } from 'three-stdlib'
import * as THREE from 'three'
import { fogRange } from '../engine/fog'

interface Focus {
  x: number
  z: number
}

/** Orbit controls that glide after a focus point, keep the fog past it and report chunk changes. */
export default function FollowCamera({ focus, focusY, initialFocus, initialFocusY, distance, follow, viewDistance, onOrbit, onChunkChange }: {
  focus: Focus
  focusY: number
  initialFocus: Focus
  initialFocusY: number
  distance: number
  follow: boolean
  viewDistance: number
  onOrbit: () => void
  onChunkChange: (x: number, z: number) => void
}) {
  const controlsRef = useRef<OrbitControlsType>(null)
  const lastChunk = useRef('')
  const { camera } = useThree()

  useFrame((state, delta) => {
    const controls = controlsRef.current
    if (!controls) return
    if (follow) {
      const desired = new THREE.Vector3(focus.x, focusY, focus.z)
      const movement = desired.sub(controls.target).multiplyScalar(1 - Math.exp(-3 * delta))
      controls.target.add(movement)
      camera.position.add(movement)
      const offset = camera.position.clone().sub(controls.target)
      const currentDistance = offset.length()
      camera.position.addScaledVector(offset.normalize(), (distance - currentDistance) * (1 - Math.exp(-2 * delta)))
      controls.update()
    }
    // Fog follows the live camera distance, so zooming out does not fade Mimo into fog early.
    const fog = state.scene.fog
    if (fog instanceof THREE.Fog) {
      const [near, far] = fogRange(viewDistance, camera.position.distanceTo(controls.target))
      fog.near = near
      fog.far = far
    }
    const cx = Math.floor(controls.target.x / 16)
    const cz = Math.floor(controls.target.z / 16)
    const key = `${cx},${cz}`
    if (key !== lastChunk.current) {
      lastChunk.current = key
      onChunkChange(cx, cz)
    }
  })

  return (
    <OrbitControls ref={controlsRef} target={[initialFocus.x, initialFocusY, initialFocus.z]}
      enableDamping dampingFactor={0.08} minDistance={11} maxDistance={130}
      maxPolarAngle={Math.PI / 2.04} onStart={onOrbit} />
  )
}
```

- [ ] **Step 2: Add day and night lighting**

Create `frontend/src/survival/DayNight.tsx`:

```tsx
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { dayness, rgbToHex, skyColor } from './sky'

/**
 * Lights that follow the game clock: sky and fog color and a sun and ambient light that dim at
 * night. Terrain dims through BlockWorld's daylight callback instead, because the terrain
 * materials ignore scene lights.
 */
export default function DayNight({ seconds }: { seconds: () => number }) {
  const ambient = useRef<THREE.AmbientLight>(null)
  const sun = useRef<THREE.DirectionalLight>(null)
  const color = useRef(new THREE.Color())

  useFrame((state) => {
    const now = seconds()
    const light = dayness(now)
    color.current.set(rgbToHex(skyColor(now)))
    if (state.scene.background instanceof THREE.Color) state.scene.background.copy(color.current)
    if (state.scene.fog instanceof THREE.Fog) state.scene.fog.color.copy(color.current)
    if (ambient.current) ambient.current.intensity = 0.3 + 0.5 * light
    if (sun.current) sun.current.intensity = 0.25 + 1.45 * light
  })

  return (
    <>
      <ambientLight ref={ambient} intensity={0.8} />
      <directionalLight ref={sun} position={[12, 24, 16]} intensity={1.7} />
      <directionalLight position={[-10, 8, -12]} intensity={0.35} color="#d5eaff" />
    </>
  )
}

/** A soft warm light above the pet that fades in after dusk, so the pet stays visible at night. */
export function PetGlow({ seconds }: { seconds: () => number }) {
  const light = useRef<THREE.PointLight>(null)
  useFrame(() => {
    if (light.current) light.current.intensity = 2.2 * (1 - dayness(seconds()))
  })
  // Local to the pet's group, which is scaled by 0.31: this sits about 2.5 blocks above the pet.
  return <pointLight ref={light} position={[0.5, 8, 0.5]} intensity={0} distance={9} decay={1} color="#ffd9a8" />
}
```

`PetGlow` owns its light and reads the clock itself. Passing a ref to `DayNight` and setting its intensity there would mutate a prop, which the React hooks lint rule rejects.

- [ ] **Step 3: Add the shared world canvas**

Create `frontend/src/survival/WorldCanvas.tsx`:

```tsx
import { useState } from 'react'
import { Canvas } from '@react-three/fiber'
import PetEntity from '../components/world/PetEntity'
import { previewPet } from '../components/world/previewWorld'
import BlockWorld, { type ViewStats } from '../engine/BlockWorld'
import { fogRange } from '../engine/fog'
import type { WorldStore } from '../engine/worldStore'
import DayNight, { PetGlow } from './DayNight'
import FollowCamera from './FollowCamera'
import { daylightFactor } from './sky'

const CAMERA_DISTANCE = 26
const DAY_SKY = '#dce9eb'

/** Phones and low-core devices draw fewer columns. */
function pickViewDistance(): number {
  const small = Math.min(window.innerWidth, window.innerHeight) < 600
  return small || (navigator.hardwareConcurrency ?? 8) <= 4 ? 4 : 6
}

/**
 * The 3D world around one pet: terrain from the store, the pet, and a camera that follows it.
 * With `seconds` (game seconds into the day) the sky, lights and terrain follow day and night;
 * without it the scene stays in daylight. `arrival` starts the camera high so it flies down.
 */
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0 }: {
  store: WorldStore
  position: { x: number; y: number; z: number }
  seconds?: () => number
  arrival?: boolean
  following: boolean
  onOrbit: () => void
  onPetClick?: () => void
  hopSignal?: number
}) {
  const [viewDistance] = useState(pickViewDistance)
  const [debug] = useState(() => new URLSearchParams(window.location.search).has('debug'))
  const [stats, setStats] = useState<ViewStats | null>(null)
  const [engineError, setEngineError] = useState('')
  const [engineKey, setEngineKey] = useState(0)
  const [initial] = useState(() => ({ ...position }))
  const [cameraChunk, setCameraChunk] = useState(() => ({ x: Math.floor(position.x / 16), z: Math.floor(position.z / 16) }))
  const [fogNear, fogFar] = fogRange(viewDistance, CAMERA_DISTANCE)
  const pet = { ...previewPet, position: { x: initial.x, y: initial.y, z: initial.z } }

  return (
    <>
      <div className="absolute inset-0">
        <Canvas camera={{ position: [initial.x + 18, initial.y + (arrival ? 80 : 13), initial.z + 18], fov: 48, near: 0.1, far: 320 }}
          gl={{ antialias: true }} dpr={[1, 2]}>
          <color attach="background" args={[DAY_SKY]} />
          <fog attach="fog" args={[DAY_SKY, fogNear, fogFar]} />
          {seconds ? <DayNight seconds={seconds} /> : (
            <>
              <ambientLight intensity={0.8} />
              <directionalLight position={[12, 24, 16]} intensity={1.7} />
              <directionalLight position={[-10, 8, -12]} intensity={0.35} color="#d5eaff" />
            </>
          )}
          <BlockWorld key={engineKey} store={store} centerX={cameraChunk.x * 16 + 8} centerZ={cameraChunk.z * 16 + 8}
            viewDistance={viewDistance} daylight={seconds ? () => daylightFactor(seconds()) : undefined}
            onStats={debug ? setStats : undefined} onError={setEngineError} />
          <PetEntity pet={pet} scale={0.31} destination={{ ...position, token: 0 }} onPetClick={onPetClick} hopSignal={hopSignal}>
            {[-0.25, 1.25].map((x) => (
              <mesh key={x} position={[x, 3.35, 2.08]}>
                <boxGeometry args={[0.34, 0.38, 0.16]} />
                <meshStandardMaterial color="#39454a" />
              </mesh>
            ))}
            <mesh position={[0.5, 2.58, 2.1]}>
              <boxGeometry args={[0.32, 0.25, 0.18]} />
              <meshStandardMaterial color="#cd8a84" />
            </mesh>
            {seconds && <PetGlow seconds={seconds} />}
          </PetEntity>
          <FollowCamera focus={position} focusY={position.y} initialFocus={initial} initialFocusY={initial.y}
            distance={CAMERA_DISTANCE} follow={following} viewDistance={viewDistance} onOrbit={onOrbit}
            onChunkChange={(x, z) => setCameraChunk((current) => current.x === x && current.z === z ? current : { x, z })} />
        </Canvas>
      </div>

      {debug && stats && (
        <div className="pointer-events-none absolute bottom-3 left-3 z-30 rounded-lg bg-black/70 px-3 py-2 font-mono text-[11px] leading-5 text-white">
          {stats.fps} fps · {stats.drawCalls} draws<br />
          {stats.columns} columns · {stats.pending} pending · mesh {stats.lastMeshMs.toFixed(1)} ms
        </div>
      )}

      {engineError && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-[#dce9eb]/90 px-6 text-center text-[#315e58]">
          <div>
            <p className="text-2xl font-semibold">The world stopped drawing</p>
            <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{engineError}</p>
            <button type="button" onClick={() => { setEngineError(''); setEngineKey((key) => key + 1) }}
              className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>
          </div>
        </div>
      )}
    </>
  )
}
```

- [ ] **Step 4: Add the HUD and the crafting panel**

Create `frontend/src/survival/SurvivalHud.tsx`:

```tsx
import { dialPosition } from './clock'
import { careLabel, clockTime, dayLabel, statusText, vitalBars, type VitalLevel } from './hud'
import type { AliveResponse, CareKind } from './types'

const LEVEL_COLORS: Record<VitalLevel, string> = { ok: '#4d8c77', low: '#d6a14a', critical: '#c76e5c' }
const PANEL = 'rounded-2xl border border-white/75 bg-[#f5faf7]/90 shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md'

/** A half-circle dial with the sun by day and the moon by night. */
function SkyDial({ secondsIntoDay }: { secondsIntoDay: number }) {
  const { body, progress } = dialPosition(secondsIntoDay)
  const angle = Math.PI * (1 - progress)
  const x = 30 + Math.cos(angle) * 24
  const y = 30 - Math.sin(angle) * 24
  return (
    <svg viewBox="0 0 60 34" className="h-9 w-16 shrink-0" role="img" aria-label={body === 'sun' ? 'Sun' : 'Moon'}>
      <path d="M6 30 A24 24 0 0 1 54 30" fill="none" stroke="#bfd5cd" strokeWidth="2" strokeDasharray="3 3" />
      <line x1="2" y1="30.5" x2="58" y2="30.5" stroke="#bfd5cd" strokeWidth="1.5" />
      <circle cx={x} cy={y} r="5" fill={body === 'sun' ? '#f5c46b' : '#c9d4f0'} stroke={body === 'sun' ? '#e0a23c' : '#8f9fc8'} />
    </svg>
  )
}

export default function SurvivalHud({ state, online, busy, message, onCare, onHello, onFollow, onCrafting, onOpenLives }: {
  state: AliveResponse
  online: boolean
  busy: boolean
  message: string
  onCare: (kind: CareKind) => void
  onHello: () => void
  onFollow: () => void
  onCrafting: () => void
  /** Shows a Lives button that opens the archive. */
  onOpenLives?: () => void
}) {
  const { clock, life } = state
  const careKinds: CareKind[] = ['snack', 'bandage']
  return (
    <>
      <div className="absolute inset-x-4 top-4 z-10 flex flex-col gap-3 sm:inset-x-8 sm:top-8 sm:flex-row sm:items-start sm:justify-between">
        <section className={`${PANEL} px-4 py-3 sm:w-80`} aria-label={`${life.name}'s day`}>
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-lg font-semibold leading-tight">{life.name}</p>
              <p className="text-xs text-[#54726e]">{dayLabel(clock.day_number, clock.phase)} · {clockTime(clock.seconds_into_day)}</p>
            </div>
            <SkyDial secondsIntoDay={clock.seconds_into_day} />
          </div>
          <p className="mt-2 text-xs text-[#54726e]">
            <span className={online ? 'text-[#3c9a73]' : 'text-[#c76e5c]'}>●</span> {online ? statusText(state.status) : 'Worker offline'}
          </p>
          <p className="mt-1 text-sm italic leading-5 text-[#315e58]">“{state.last_thought}”</p>
        </section>
        <section className={`${PANEL} grid grid-cols-2 gap-x-4 gap-y-2 px-4 py-3 text-xs sm:w-64 sm:grid-cols-1`} aria-label="Vitals">
          {vitalBars(state.vitals).map((bar) => (
            <div key={bar.key}>
              <div className="flex justify-between"><span>{bar.label}</span><span className="tabular-nums">{bar.value}</span></div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#d9e8df]" role="progressbar"
                aria-valuenow={bar.value} aria-valuemin={0} aria-valuemax={100} aria-label={bar.label}>
                <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${bar.value}%`, backgroundColor: LEVEL_COLORS[bar.level] }} />
              </div>
            </div>
          ))}
        </section>
      </div>

      <div className="absolute inset-x-4 bottom-4 z-10 flex flex-col gap-3 sm:inset-x-8 sm:bottom-8 sm:flex-row sm:items-end sm:justify-between">
        <section className={`${PANEL} px-4 py-3 sm:max-w-md`} aria-label="Care">
          <div className="flex flex-wrap gap-2">
            {careKinds.map((kind) => (
              <button key={kind} type="button" disabled={busy || state.care[kind] <= 0} onClick={() => onCare(kind)}
                className="rounded-xl bg-[#315e58] px-3 py-2 text-sm font-medium text-white hover:bg-[#244b47] disabled:cursor-not-allowed disabled:opacity-40">
                {careLabel(kind, state.care[kind])}
              </button>
            ))}
            <button type="button" disabled={busy} onClick={onHello}
              className="rounded-xl border border-[#bfd5cd] px-3 py-2 text-sm font-medium text-[#315e58] hover:bg-white disabled:opacity-40">Say hello</button>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm font-medium text-[#315e58]">
            <button type="button" onClick={onFollow} className="underline decoration-[#8cafa2] underline-offset-4">Follow {life.name}</button>
            <button type="button" onClick={onCrafting} className="underline decoration-[#8cafa2] underline-offset-4">Blocks & crafting</button>
            {onOpenLives && <button type="button" onClick={onOpenLives} className="underline decoration-[#8cafa2] underline-offset-4">Lives</button>}
          </div>
          {message && <p className="mt-2 text-xs text-[#a65b50]" role="status">{message}</p>}
        </section>
        <section className={`${PANEL} hidden w-64 px-4 py-3 text-xs md:block`} aria-label="Recent events">
          <p className="mb-2 font-semibold">What happened</p>
          <ul className="space-y-1.5 text-[#54726e]">
            {state.events.slice(0, 4).map((event) => <li key={event.id}>{event.text}</li>)}
          </ul>
        </section>
      </div>
    </>
  )
}
```

Create `frontend/src/survival/CraftingPanel.tsx` (the old "Blocks & crafting" dialog from `WorldPreview.tsx`, now for the active life):

```tsx
import { AIR, BLOCKS } from '../engine/blocks'
import type { Recipe } from './types'

const BLOCK_TYPES = BLOCKS.filter((block) => block.id !== AIR)

/** The owner's crafting help: the same rules and persistent inventory the pet uses. */
export default function CraftingPanel({ name, inventory, recipes, stations, worldSeed, message, onAction, onClose }: {
  name: string
  inventory: Record<string, number>
  recipes: Record<string, Recipe>
  stations: Set<string>
  worldSeed: string
  message: string
  onAction: (action: string, item: string) => void
  onClose: () => void
}) {
  const owned = Object.entries(inventory).filter(([, amount]) => amount > 0)
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={`${name}'s blocks and crafting`} onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">World systems</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight">Blocks & crafting</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close blocks and crafting" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
        </div>
        <p className="mt-3 max-w-xl text-sm leading-6 text-[#54726e]">You can help {name} craft with what it carries. Inventory and machines persist when you leave.</p>
        <p className="mt-2 text-xs text-[#54726e]">World seed: <code>{worldSeed}</code></p>
        <h3 className="mt-6 text-sm font-semibold">{name}'s inventory</h3>
        <div className="mt-2 flex flex-wrap gap-2 text-sm">
          {owned.length === 0 && <span className="text-[#65817b]">Nothing yet.</span>}
          {owned.map(([item, amount]) =>
            <span key={item} className="rounded-lg bg-[#e1eee7] px-3 py-1.5">{item.replaceAll('_', ' ')} ×{amount}</span>)}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" disabled={!inventory.crafting_table} onClick={() => onAction('place_machine', 'crafting_table')}
            className="rounded-lg bg-[#315e58] px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-35">Place crafting table</button>
          <button type="button" disabled={!inventory.furnace} onClick={() => onAction('place_machine', 'furnace')}
            className="rounded-lg bg-[#315e58] px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-35">Place furnace</button>
          <button type="button" disabled={!inventory.iron_ore || !stations.has('furnace') || !(inventory.coal || inventory.planks)}
            onClick={() => onAction('smelt', 'iron_ore')}
            className="rounded-lg border border-[#bfd5cd] px-3 py-2 text-xs font-medium text-[#315e58] disabled:cursor-not-allowed disabled:opacity-35">Smelt iron ore</button>
        </div>
        <p className="mt-2 text-xs text-[#65817b]">Smelting needs a placed furnace and coal or planks for fuel.</p>
        {message && <p className="mt-3 rounded-lg bg-[#e1eee7] px-3 py-2 text-xs text-[#315e58]" role="status">{message}</p>}
        <h3 className="mt-6 text-sm font-semibold">Recipes</h3>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {Object.entries(recipes).map(([recipeName, recipe]) => (
            <div key={recipeName} className="rounded-xl bg-[#e9f2eb] px-3 py-2 text-xs leading-5">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold">{recipeName.replaceAll('_', ' ')}</p>
                <button type="button" disabled={Boolean(recipe.station && !stations.has(recipe.station)) ||
                  Object.entries(recipe.ingredients).some(([item, amount]) => (inventory[item] || 0) < amount)}
                  onClick={() => onAction('craft', recipeName)}
                  className="rounded-md bg-[#315e58] px-2 py-1 font-medium text-white hover:bg-[#244b47] disabled:cursor-not-allowed disabled:opacity-35">Craft</button>
              </div>
              <p className="text-[#54726e]">{Object.entries(recipe.ingredients).map(([item, amount]) => `${amount} ${item.replaceAll('_', ' ')}`).join(' + ')}
                {recipe.station ? ` · needs placed ${recipe.station.replaceAll('_', ' ')}` : ''}</p>
            </div>
          ))}
        </div>
        <h3 className="mt-6 text-sm font-semibold">{BLOCK_TYPES.length} block types</h3>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {BLOCK_TYPES.map((block) => (
            <div key={block.name} className="flex items-center gap-2 rounded-lg border border-[#d6e5dc] px-2 py-1.5 text-xs">
              <span className="h-5 w-5 shrink-0 rounded-sm border border-black/10" style={{ backgroundColor: `rgb(${block.color.join(',')})` }} />
              {block.name.replaceAll('_', ' ')}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
```

- [ ] **Step 5: Add the living world view**

Create `frontend/src/survival/SurvivalWorld.tsx`:

```tsx
import { useCallback, useEffect, useMemo, useState } from 'react'
import { BlockSync } from '../engine/blockSync'
import { WorldStore } from '../engine/worldStore'
import { blocksFetcher, giveCare, helpMimo, sayHello } from './api'
import { liveClock } from './clock'
import CraftingPanel from './CraftingPanel'
import { workerOnline } from './hud'
import SurvivalHud from './SurvivalHud'
import type { AliveResponse, CareKind } from './types'
import WorldCanvas from './WorldCanvas'

/** The live survival world: terrain and blocks, the pet, day and night, the HUD and owner care. */
export default function SurvivalWorld({ state, receivedAt, arrival, connectionError, onChanged, onOpenLives }: {
  state: AliveResponse
  /** Local time (seconds) when `state` arrived, to run the clock between polls. */
  receivedAt: number
  arrival: boolean
  connectionError: string
  onChanged: () => Promise<void>
  onOpenLives?: () => void
}) {
  const store = useMemo(() => new WorldStore(state.world_seed), [state.world_seed])
  const sync = useMemo(() => new BlockSync(blocksFetcher(null), (changes, reset) => {
    store.applyServerChanges(changes, reset)
  }), [store])
  const [following, setFollowing] = useState(true)
  const [helloCount, setHelloCount] = useState(0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [syncError, setSyncError] = useState('')
  const [showCrafting, setShowCrafting] = useState(false)
  const [craftMessage, setCraftMessage] = useState('')

  // Poll-driven: receivedAt changes every second, so a failed delta is retried on the next poll.
  useEffect(() => {
    sync.syncTo(state.blocks_seq).then(
      () => setSyncError(''),
      () => setSyncError('Some block changes could not be loaded. Retrying.'),
    )
  }, [sync, state.blocks_seq, receivedAt])

  const seconds = useCallback(() => liveClock(state.clock, receivedAt, Date.now() / 1000).secondsIntoDay,
    [state.clock, receivedAt])
  const stations = useMemo(() => store.materialsNear(state.position.x, state.position.z, 6),
    // Re-read once per poll, after the block delta for that poll has been applied.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [store, receivedAt, state.position.x, state.position.z])

  const run = async (action: () => Promise<unknown>, done?: () => void) => {
    setBusy(true)
    setMessage('')
    try {
      await action()
      done?.()
      await onChanged()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'That did not work. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const care = (kind: CareKind) => { void run(() => giveCare(kind)) }
  const hello = () => { void run(sayHello, () => setHelloCount((count) => count + 1)) }
  const craft = async (action: string, item: string) => {
    try {
      setCraftMessage((await helpMimo(action, item)).message)
      await onChanged()
    } catch (error) {
      setCraftMessage(error instanceof Error ? error.message : 'That action could not be completed.')
    }
  }

  return (
    <main className="relative h-screen min-h-[540px] overflow-hidden bg-[#dce9eb] text-[#243e3d]">
      <WorldCanvas store={store} position={state.position} seconds={seconds} arrival={arrival}
        following={following} onOrbit={() => setFollowing(false)} onPetClick={hello} hopSignal={helloCount} />
      <SurvivalHud state={state} online={!connectionError && workerOnline(state.server_time, state.last_tick_at)}
        busy={busy} message={message || connectionError || syncError}
        onCare={care} onHello={hello} onFollow={() => setFollowing(true)}
        onCrafting={() => setShowCrafting(true)} onOpenLives={onOpenLives} />
      {showCrafting && (
        <CraftingPanel name={state.life.name} inventory={state.inventory} recipes={state.recipes} stations={stations}
          worldSeed={state.world_seed} message={craftMessage} onAction={(action, item) => { void craft(action, item) }}
          onClose={() => setShowCrafting(false)} />
      )}
    </main>
  )
}
```

- [ ] **Step 6: Point `/preview` at the living world**

Replace the whole of `frontend/src/pages/WorldPreview.tsx` with this version. Tasks 12 and 13 replace its simple egg-phase screen:

```tsx
import { useCallback, useEffect, useState } from 'react'
import { fetchMimo } from '../survival/api'
import SurvivalWorld from '../survival/SurvivalWorld'
import type { MimoResponse } from '../survival/types'

interface Received {
  data: MimoResponse
  /** Local time in seconds when the response arrived. */
  receivedAt: number
}

/** /preview: the living pet. The egg screen, memorial and archive arrive in later tasks. */
export default function WorldPreview() {
  const [received, setReceived] = useState<Received | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const data = await fetchMimo()
      setReceived({ data, receivedAt: Date.now() / 1000 })
      setError('')
    } catch (failure) {
      setError(failure instanceof Error && !failure.message.startsWith('Server returned')
        ? failure.message : 'The server is unavailable. The world will appear when it is running.')
    }
  }, [])

  useEffect(() => {
    const initial = window.setTimeout(() => { void refresh() }, 0)
    const timer = window.setInterval(() => { void refresh() }, 1000)
    return () => { window.clearTimeout(initial); window.clearInterval(timer) }
  }, [refresh])

  if (!received) return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <div><p className="text-2xl font-semibold">Connecting to Mimo’s world…</p>
        {error && <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{error}</p>}
        {error && <button type="button" onClick={() => { void refresh() }} className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>}
      </div>
    </main>
  )

  const { data, receivedAt } = received
  if (data.phase === 'alive') {
    return <SurvivalWorld key={data.life.id} state={data} receivedAt={receivedAt} arrival={false}
      connectionError={error} onChanged={refresh} />
  }
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <p className="max-w-sm text-xl font-semibold">No pet is alive yet. Hatch the egg with POST /api/lives/hatch.</p>
    </main>
  )
}
```

- [ ] **Step 7: Type check, lint and test**

Run: `cd frontend && npm run build`
Expected: the build succeeds.

Run: `cd frontend && npx eslint src/survival src/pages/WorldPreview.tsx src/engine`
Expected: no output.

Run: `cd frontend && npm test`
Expected: `Tests  103 passed (103)`

- [ ] **Step 8: Commit**

```bash
git add frontend/src/survival/FollowCamera.tsx frontend/src/survival/DayNight.tsx frontend/src/survival/WorldCanvas.tsx frontend/src/survival/SurvivalHud.tsx frontend/src/survival/CraftingPanel.tsx frontend/src/survival/SurvivalWorld.tsx frontend/src/pages/WorldPreview.tsx
git commit -m "feat: show the living pet with a HUD, care and day and night" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Archive browser and read-only worlds

**Files:**
- Create: `frontend/src/survival/archive.ts`, `frontend/src/survival/ArchiveBrowser.tsx`, `frontend/src/survival/ArchiveWorld.tsx`
- Rewrite: `frontend/src/pages/WorldPreview.tsx`
- Test: `frontend/src/survival/archive.test.ts`

**Interfaces:**
- Consumes: `fetchLives`, `fetchLife`, `blocksFetcher`, `lifeLine` (Task 10); `WorldCanvas` (Task 11); `compileWorldPlan`, `overlayBlocks`, `WorldPlan` from `components/world/worldPlanner`.
- Produces (`archive.ts`): `isLegacyState(state) -> state is LegacyState`, `legacyOverlay(plans: WorldPlan[], currentIndex: number, progress: number) -> PlacedBlock[]`.
- Produces: `ArchiveBrowser({ onOpen(lifeId), onClose })`, `ArchiveWorld({ lifeId, onBack })`.

Life 1 renders like the old preview: its server block edits plus the blueprint overlay compiled in the browser (finished plans in full, the plan in progress up to its saved progress). Survival lives render their server blocks only. Archives always show daylight.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/survival/archive.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { compileWorldPlan, type WorldPlan } from '../components/world/worldPlanner'
import { isLegacyState, legacyOverlay } from './archive'
import type { LegacyState, SurvivalState } from './types'

const plan = (kind: WorldPlan['kind'], x: number): WorldPlan => ({ kind, site: { x, z: 0 }, variant: 0, observation: '', clearance: 15 })
const station = plan('station', 48)
const plaza = plan('plaza', 200)

describe('legacyOverlay', () => {
  it('shows every block of finished plans', () => {
    expect(legacyOverlay([station], 0, 100)).toHaveLength(compileWorldPlan(station).blocks.length)
  })

  it('shows the plan in progress up to its saved progress', () => {
    const stationBlocks = compileWorldPlan(station).blocks.length
    const plazaBlocks = compileWorldPlan(plaza).blocks.length
    expect(legacyOverlay([station, plaza], 1, 0)).toHaveLength(stationBlocks)
    expect(legacyOverlay([station, plaza], 1, 50)).toHaveLength(stationBlocks + Math.floor(plazaBlocks / 2))
  })
})

describe('isLegacyState', () => {
  it('tells the legacy snapshot from a survival state', () => {
    const legacy = { plans: [station], currentIndex: 0, progress: 100 } as unknown as LegacyState
    const survival = { vitals: {}, clock: {} } as unknown as SurvivalState
    expect(isLegacyState(legacy)).toBe(true)
    expect(isLegacyState(survival)).toBe(false)
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/survival/archive.test.ts`
Expected: `Failed to resolve import "./archive"`.

- [ ] **Step 3: Write the archive helpers**

Create `frontend/src/survival/archive.ts`:

```ts
import { compileWorldPlan, overlayBlocks, type WorldPlan } from '../components/world/worldPlanner'
import type { PlacedBlock } from '../engine/worldStore'
import type { LegacyState, SurvivalState } from './types'

export function isLegacyState(state: LegacyState | SurvivalState): state is LegacyState {
  return 'plans' in state
}

/**
 * The retired legacy world's builds, compiled in the browser as before: every finished plan in
 * full and the plan in progress up to its saved progress.
 */
export function legacyOverlay(plans: WorldPlan[], currentIndex: number, progress: number): PlacedBlock[] {
  const current = plans[currentIndex]
  const placed = current ? Math.floor(compileWorldPlan(current).blocks.length * progress / 100) : 0
  return overlayBlocks(plans, currentIndex, placed)
}
```

Run: `cd frontend && npx vitest run src/survival/archive.test.ts`
Expected: `Tests  3 passed (3)`

- [ ] **Step 4: Write the lives list**

Create `frontend/src/survival/ArchiveBrowser.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { fetchLives } from './api'
import { lifeLine } from './hud'
import type { LifeRow } from './types'

/** Every life, newest first. Opening one shows its world read-only. */
export default function ArchiveBrowser({ onOpen, onClose }: {
  onOpen: (lifeId: number) => void
  onClose: () => void
}) {
  const [lives, setLives] = useState<LifeRow[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchLives().then(
      (rows) => { if (!cancelled) setLives(rows) },
      (failure: unknown) => { if (!cancelled) setError(failure instanceof Error ? failure.message : 'The lives could not be loaded.') },
    )
    return () => { cancelled = true }
  }, [])

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label="Lives" onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 text-[#243e3d] shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Archive</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight">Lives</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close lives" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
        </div>
        {error && <p className="mt-4 text-sm text-[#a65b50]" role="alert">{error}</p>}
        {!lives && !error && <p className="mt-4 text-sm text-[#54726e]">Loading…</p>}
        <ul className="mt-5 space-y-2">
          {lives?.map((life) => (
            <li key={life.id} className="flex items-center justify-between gap-3 rounded-2xl bg-[#e9f2eb] px-4 py-3">
              <div className="min-w-0">
                <p className="truncate font-semibold">{life.name} <span className="text-xs font-normal text-[#65817b]">#{life.id}</span></p>
                <p className="text-xs text-[#54726e]">{lifeLine(life)} · born {new Date(life.born_at * 1000).toLocaleDateString()}</p>
              </div>
              <button type="button" onClick={() => onOpen(life.id)}
                className="shrink-0 rounded-lg bg-[#315e58] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#244b47]">View world</button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
```

- [ ] **Step 5: Write the read-only world**

Create `frontend/src/survival/ArchiveWorld.tsx`:

```tsx
import { useEffect, useMemo, useState } from 'react'
import { BlockSync } from '../engine/blockSync'
import { WorldStore } from '../engine/worldStore'
import { blocksFetcher, fetchLife } from './api'
import { isLegacyState, legacyOverlay } from './archive'
import { lifeLine } from './hud'
import type { LifeDetail } from './types'
import WorldCanvas from './WorldCanvas'

const PANEL = 'rounded-2xl border border-white/75 bg-[#f5faf7]/90 shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md'

function ArchiveScene({ lifeId, detail, onBack }: { lifeId: number; detail: LifeDetail; onBack: () => void }) {
  const { life, state } = detail
  const store = useMemo(() => new WorldStore(state.world_seed), [state.world_seed])
  const [syncError, setSyncError] = useState('')
  const [following, setFollowing] = useState(true)
  const overlay = useMemo(() => isLegacyState(state) ? legacyOverlay(state.plans, state.currentIndex, state.progress) : [],
    [state])

  useEffect(() => {
    const sync = new BlockSync(blocksFetcher(lifeId), (changes, reset) => { store.applyServerChanges(changes, reset) })
    sync.syncTo(state.blocks_seq).catch(() => setSyncError('Some block changes could not be loaded.'))
  }, [store, lifeId, state.blocks_seq])
  useEffect(() => { store.setOverlay(overlay, 'legacy-builds') }, [store, overlay])

  const position = { x: state.position.x, y: state.position.y ?? 1, z: state.position.z }
  return (
    <main className="relative h-screen min-h-[540px] overflow-hidden bg-[#dce9eb] text-[#243e3d]">
      <WorldCanvas store={store} position={position} following={following} onOrbit={() => setFollowing(false)} />
      <section className={`${PANEL} absolute inset-x-4 top-4 z-10 px-4 py-3 sm:inset-x-auto sm:left-8 sm:top-8 sm:w-80`} aria-label={`${life.name}'s life`}>
        <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Archive · read only</p>
        <p className="mt-1 text-2xl font-semibold tracking-tight">{life.name}</p>
        <p className="mt-1 text-xs text-[#54726e]">{lifeLine(life)}</p>
        {detail.notable_events.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs text-[#54726e]">
            {detail.notable_events.slice(0, 4).map((event) => <li key={event.id}>{event.text}</li>)}
          </ul>
        )}
        {syncError && <p className="mt-2 text-xs text-[#a65b50]">{syncError}</p>}
        <div className="mt-3 flex gap-4 text-sm font-medium text-[#315e58]">
          <button type="button" onClick={onBack} className="underline decoration-[#8cafa2] underline-offset-4">Back</button>
          <button type="button" onClick={() => setFollowing(true)} className="underline decoration-[#8cafa2] underline-offset-4">Center on {life.name}</button>
        </div>
      </section>
    </main>
  )
}

/** One life's world, read only. The legacy life shows its builds through the blueprint overlay. */
export default function ArchiveWorld({ lifeId, onBack }: { lifeId: number; onBack: () => void }) {
  const [detail, setDetail] = useState<LifeDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchLife(lifeId).then(
      (loaded) => { if (!cancelled) setDetail(loaded) },
      (failure: unknown) => { if (!cancelled) setError(failure instanceof Error ? failure.message : 'This life could not be loaded.') },
    )
    return () => { cancelled = true }
  }, [lifeId])

  if (!detail) return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <div>
        <p className="text-2xl font-semibold">{error ? 'This world could not be opened' : 'Opening the archive…'}</p>
        {error && <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{error}</p>}
        <button type="button" onClick={onBack} className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Back</button>
      </div>
    </main>
  )
  return <ArchiveScene lifeId={lifeId} detail={detail} onBack={onBack} />
}
```

- [ ] **Step 6: Open the archive from `/preview`**

Replace the whole of `frontend/src/pages/WorldPreview.tsx` with this version. Task 13 replaces its simple egg-phase screen:

```tsx
import { useCallback, useEffect, useState } from 'react'
import { fetchMimo } from '../survival/api'
import ArchiveBrowser from '../survival/ArchiveBrowser'
import ArchiveWorld from '../survival/ArchiveWorld'
import SurvivalWorld from '../survival/SurvivalWorld'
import type { MimoResponse } from '../survival/types'

interface Received {
  data: MimoResponse
  /** Local time in seconds when the response arrived. */
  receivedAt: number
}

/** /preview: the living pet and the archive of every life. The egg screen arrives in the next task. */
export default function WorldPreview() {
  const [received, setReceived] = useState<Received | null>(null)
  const [error, setError] = useState('')
  const [showLives, setShowLives] = useState(false)
  const [openLife, setOpenLife] = useState<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await fetchMimo()
      setReceived({ data, receivedAt: Date.now() / 1000 })
      setError('')
    } catch (failure) {
      setError(failure instanceof Error && !failure.message.startsWith('Server returned')
        ? failure.message : 'The server is unavailable. The world will appear when it is running.')
    }
  }, [])

  useEffect(() => {
    const initial = window.setTimeout(() => { void refresh() }, 0)
    const timer = window.setInterval(() => { void refresh() }, 1000)
    return () => { window.clearTimeout(initial); window.clearInterval(timer) }
  }, [refresh])

  if (openLife !== null) return <ArchiveWorld key={openLife} lifeId={openLife} onBack={() => setOpenLife(null)} />

  if (!received) return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <div><p className="text-2xl font-semibold">Connecting to Mimo’s world…</p>
        {error && <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{error}</p>}
        {error && <button type="button" onClick={() => { void refresh() }} className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>}
      </div>
    </main>
  )

  const { data, receivedAt } = received
  const openLives = () => setShowLives(true)
  const screen = data.phase === 'alive'
    ? <SurvivalWorld key={data.life.id} state={data} receivedAt={receivedAt} arrival={false}
      connectionError={error} onChanged={refresh} onOpenLives={openLives} />
    : (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#dce9eb] px-6 text-center text-[#315e58]">
        <p className="max-w-sm text-xl font-semibold">No pet is alive yet. Hatch the egg with POST /api/lives/hatch.</p>
        <button type="button" onClick={openLives} className="rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Lives</button>
      </main>
    )
  return (
    <>
      {screen}
      {showLives && <ArchiveBrowser onClose={() => setShowLives(false)}
        onOpen={(lifeId) => { setShowLives(false); setOpenLife(lifeId) }} />}
    </>
  )
}
```

- [ ] **Step 7: Type check, lint and test**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/pages/WorldPreview.tsx`
Expected: `Tests  106 passed (106)`, the build succeeds, eslint prints nothing.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/survival/archive.ts frontend/src/survival/archive.test.ts frontend/src/survival/ArchiveBrowser.tsx frontend/src/survival/ArchiveWorld.tsx frontend/src/pages/WorldPreview.tsx
git commit -m "feat: browse every life and open archived worlds read-only" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Egg hatch screen and memorial

**Files:**
- Create: `frontend/src/survival/EggHatch.tsx`, `frontend/src/survival/Memorial.tsx`
- Rewrite: `frontend/src/pages/WorldPreview.tsx`

**Interfaces:**
- Consumes: `EggScene` and its `EggProfile`/`Phase` types (`components/hatch`), `rarityColors`, `hatchEgg`, `lifeLine` (Task 10), `ArchiveBrowser`, `ArchiveWorld` (Task 12), `SurvivalWorld` (Task 11).
- Produces: `EggHatch({ egg, lastLife, onHatched, onOpenLives })`, `Memorial({ life, onViewWorld, onNextEgg })`, and the final `WorldPreview`.

`/preview` now shows, in order: an archived world when one is open; the living world when `phase` is `alive`; the memorial when the last life was a survival life that died and the owner has not moved on in this page session; otherwise the egg. The egg comes from the server (`/api/mimo` in the egg phase), so every visitor sees the same egg, and the one that hatches is the one on screen. After hatching, `arrival` makes the camera fly down into the new world.

- [ ] **Step 1: Write the egg screen**

Create `frontend/src/survival/EggHatch.tsx`:

```tsx
import { useMemo, useState } from 'react'
import EggScene from '../components/hatch/EggScene'
import type { EggProfile, Phase } from '../components/hatch/types'
import { rarityColors } from '../data/rarity'
import { hatchEgg } from './api'
import type { LifeSummary, ServerEgg } from './types'

/** Long enough for EggScene's hatching glow to play before the world appears. */
const HATCH_ANIMATION_MS = 2200

/** The egg the server rolled, its attributes, and the Hatch button. */
export default function EggHatch({ egg, lastLife, onHatched, onOpenLives }: {
  egg: ServerEgg
  lastLife: LifeSummary | null
  onHatched: () => Promise<void>
  onOpenLives: () => void
}) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState('')
  // Every poll parses a new egg object. Key on its content so EggScene keeps its materials.
  const eggKey = JSON.stringify(egg)
  const profile = useMemo<EggProfile>(() => ({ ...(JSON.parse(eggKey) as ServerEgg), statRanges: {} }), [eggKey])

  const hatch = async () => {
    setError('')
    setPhase('hatching')
    try {
      await Promise.all([hatchEgg(), new Promise((resolve) => window.setTimeout(resolve, HATCH_ANIMATION_MS))])
      await onHatched()
    } catch (failure) {
      setPhase('idle')
      setError(failure instanceof Error ? failure.message : 'The egg did not hatch. Try again.')
    }
  }

  return (
    <main className="relative grid min-h-screen grid-cols-1 overflow-hidden bg-[#e5e5e5] lg:grid-cols-2">
      <div className="relative order-2 min-h-[50vh] lg:order-1 lg:min-h-screen">
        <div className="absolute inset-0">
          <EggScene phase={phase} egg={profile} revealProgress={0} voxels={[]} />
        </div>
      </div>
      <section className="relative z-10 order-1 flex flex-col justify-center px-6 py-10 sm:px-12 lg:order-2 lg:px-16" aria-label="The egg">
        {lastLife?.kind === 'legacy' && (
          <p className="mb-6 max-w-sm text-sm leading-6 text-neutral-600">
            {lastLife.name} has retired. Its world and everything it built stay in the archive.
          </p>
        )}
        <p className="text-xs font-semibold uppercase tracking-widest text-neutral-500">A new egg</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-neutral-900">{egg.name}</h1>
        <p className="mt-2 text-xs font-semibold uppercase tracking-wider" style={{ color: rarityColors[egg.rarity] }}>
          {egg.rarity} · {egg.totalPoints.toFixed(1)} / 10
        </p>
        <dl className="mt-6 max-w-xs divide-y divide-neutral-200 text-sm">
          {egg.attributes.map((attribute) => (
            <div key={attribute.category} className="flex items-center justify-between gap-3 py-1.5">
              <dt className="w-16 text-[11px] uppercase tracking-wider text-neutral-400">{attribute.category}</dt>
              <dd className="flex-1 font-medium text-neutral-800">{attribute.option.name}</dd>
              <dd className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: rarityColors[attribute.option.tier] }}>
                {attribute.option.tier}
              </dd>
            </div>
          ))}
        </dl>
        <div className="mt-8 flex flex-wrap items-center gap-4">
          <button type="button" disabled={phase !== 'idle'} onClick={() => { void hatch() }}
            className="rounded-xl bg-neutral-900 px-10 py-3.5 text-sm font-medium uppercase tracking-[0.15em] text-white shadow-[0_4px_24px_rgba(0,0,0,0.15)] hover:bg-neutral-800 disabled:opacity-60">
            {phase === 'idle' ? 'Hatch' : 'Hatching…'}
          </button>
          <button type="button" onClick={onOpenLives} className="text-sm font-medium text-neutral-600 underline underline-offset-4">Lives</button>
        </div>
        {error && <p className="mt-4 text-sm text-[#a65b50]" role="alert">{error}</p>}
      </section>
    </main>
  )
}
```

The poll parses a new `egg` object every second. `EggScene` builds shader materials from its `egg` prop, so the profile is memoized on the egg's JSON text to keep the same object while the egg is unchanged.

- [ ] **Step 2: Write the memorial**

Create `frontend/src/survival/Memorial.tsx`:

```tsx
import { lifeLine } from './hud'
import type { LifeSummary } from './types'

/** Shown after a pet dies, until the owner moves on to the next egg. */
export default function Memorial({ life, onViewWorld, onNextEgg }: {
  life: LifeSummary
  onViewWorld: () => void
  onNextEgg: () => void
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#1d263b] px-4 py-10 text-[#243e3d]">
      <section className="w-full max-w-md rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8" aria-label={`In memory of ${life.name}`}>
        <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">In memory of</p>
        <h1 className="mt-1 text-4xl font-semibold tracking-tight">{life.name}</h1>
        <p className="mt-3 text-sm text-[#54726e]">{lifeLine(life)}.</p>
        {life.notable_events.length > 0 && (
          <ul className="mt-5 space-y-2 border-l-2 border-[#d6e5dc] pl-4 text-sm text-[#54726e]">
            {life.notable_events.map((event) => <li key={event.id}>{event.text}</li>)}
          </ul>
        )}
        <div className="mt-7 flex flex-col gap-2 sm:flex-row">
          <button type="button" onClick={onViewWorld}
            className="flex-1 rounded-xl border border-[#bfd5cd] px-4 py-2.5 text-sm font-medium text-[#315e58] hover:bg-white">View {life.name}'s world</button>
          <button type="button" onClick={onNextEgg}
            className="flex-1 rounded-xl bg-[#315e58] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#244b47]">Hatch a new egg</button>
        </div>
      </section>
    </main>
  )
}
```

- [ ] **Step 3: Final `/preview`**

Replace the whole of `frontend/src/pages/WorldPreview.tsx` with:

```tsx
import { useCallback, useEffect, useState } from 'react'
import { fetchMimo } from '../survival/api'
import ArchiveBrowser from '../survival/ArchiveBrowser'
import ArchiveWorld from '../survival/ArchiveWorld'
import EggHatch from '../survival/EggHatch'
import Memorial from '../survival/Memorial'
import SurvivalWorld from '../survival/SurvivalWorld'
import type { MimoResponse } from '../survival/types'

interface Received {
  data: MimoResponse
  /** Local time in seconds when the response arrived. */
  receivedAt: number
}

/** /preview: the egg, the living pet, the memorial after a death, and the archive of every life. */
export default function WorldPreview() {
  const [received, setReceived] = useState<Received | null>(null)
  const [error, setError] = useState('')
  const [arrival, setArrival] = useState(false)
  const [memorialSeen, setMemorialSeen] = useState<number | null>(null)
  const [showLives, setShowLives] = useState(false)
  const [openLife, setOpenLife] = useState<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await fetchMimo()
      setReceived({ data, receivedAt: Date.now() / 1000 })
      setError('')
    } catch (failure) {
      setError(failure instanceof Error && !failure.message.startsWith('Server returned')
        ? failure.message : 'The server is unavailable. The world will appear when it is running.')
    }
  }, [])

  useEffect(() => {
    const initial = window.setTimeout(() => { void refresh() }, 0)
    const timer = window.setInterval(() => { void refresh() }, 1000)
    return () => { window.clearTimeout(initial); window.clearInterval(timer) }
  }, [refresh])

  if (openLife !== null) return <ArchiveWorld key={openLife} lifeId={openLife} onBack={() => setOpenLife(null)} />

  if (!received) return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <div><p className="text-2xl font-semibold">Connecting to Mimo’s world…</p>
        {error && <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{error}</p>}
        {error && <button type="button" onClick={() => { void refresh() }} className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>}
      </div>
    </main>
  )

  const { data, receivedAt } = received
  const openLives = () => setShowLives(true)
  const last = data.phase === 'egg' ? data.last_life : null
  let screen
  if (data.phase === 'alive') {
    screen = <SurvivalWorld key={data.life.id} state={data} receivedAt={receivedAt} arrival={arrival}
      connectionError={error} onChanged={refresh} onOpenLives={openLives} />
  } else if (last && last.kind === 'survival' && memorialSeen !== last.id) {
    screen = <Memorial life={last} onViewWorld={() => setOpenLife(last.id)} onNextEgg={() => setMemorialSeen(last.id)} />
  } else {
    screen = <EggHatch egg={data.egg} lastLife={last} onOpenLives={openLives}
      onHatched={async () => { setArrival(true); await refresh() }} />
  }
  return (
    <>
      {screen}
      {showLives && <ArchiveBrowser onClose={() => setShowLives(false)}
        onOpen={(lifeId) => { setShowLives(false); setOpenLife(lifeId) }} />}
    </>
  )
}
```

- [ ] **Step 4: Type check, lint and test**

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/pages/WorldPreview.tsx src/engine`
Expected: `Tests  106 passed (106)`, the build succeeds, eslint prints nothing.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/survival/EggHatch.tsx frontend/src/survival/Memorial.tsx frontend/src/pages/WorldPreview.tsx
git commit -m "feat: hatch the egg in the viewer and remember the dead" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Manual check at 60× and the README

**Files:**
- Rewrite: `README.md`

**Interfaces:**
- Consumes: everything above.

Every check runs against a scratch Docker volume and a separately tagged image. The real `pets_mimo_data` volume is never mounted. If a check fails, fix the code in the task that owns it, re-run that task's tests, and repeat the check.

- [ ] **Step 1: Run every automated check**

Run: `python3 -m unittest discover -s backend/tests`
Expected: `Ran 137 tests` … `OK`

Run: `cd frontend && npm test && npm run build && npx eslint src/survival src/engine src/pages/WorldPreview.tsx`
Expected: `Tests  106 passed (106)`, the build succeeds, eslint prints nothing.

- [ ] **Step 2: Build a scratch image and a scratch world**

```bash
docker build -f backend/Dockerfile -t mimo-survival-check .
docker run --rm mimo-survival-check python -c "from backend.main import app; print(sorted({r.path for r in app.routes if r.path.startswith(('/api/lives', '/api/mimo'))}))"
```

Expected: `['/api/lives', '/api/lives/hatch', '/api/lives/{life_id}', '/api/lives/{life_id}/blocks', '/api/mimo', '/api/mimo/action', '/api/mimo/blocks', '/api/mimo/care', '/api/mimo/hello']`

Create a scratch volume with a fresh legacy world in it (so life 1 exists), and note its checksum:

```bash
docker volume create mimo_survival_check
docker run --rm -v mimo_survival_check:/data -e MIMO_DB_PATH=/data/mimo.sqlite3 mimo-survival-check \
  python -c "from backend.services.live_mimo import MimoStore; MimoStore(); print('scratch legacy world ready')"
docker run --rm -v mimo_survival_check:/data mimo-survival-check sha256sum /data/mimo.sqlite3
```

Expected: `scratch legacy world ready`, then a checksum line. Write the checksum down for Step 9.

- [ ] **Step 3: Start the scratch API and worker at 60×**

```bash
docker run -d --name mimo-check-api -p 127.0.0.1:8001:8000 -v mimo_survival_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 mimo-survival-check
docker run -d --name mimo-check-worker -v mimo_survival_check:/data \
  -e MIMO_DATA_DIR=/data -e MIMO_DB_PATH=/data/mimo.sqlite3 -e MIMO_TIME_SCALE=60 -e MIMO_TICK_SECONDS=1 \
  mimo-survival-check python -m backend.workers.mimo_worker
```

After a few seconds:

```bash
curl -s http://127.0.0.1:8001/api/mimo | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['phase'], '|', d['egg']['name'], '|', d['last_life']['kind'], d['last_life']['cause'])"
curl -s http://127.0.0.1:8001/api/lives | python3 -c "import json,sys; print([(l['id'], l['kind'], l['cause']) for l in json.load(sys.stdin)])"
docker logs mimo-check-worker 2>&1 | tail -2
```

Expected: `egg | <egg name> | legacy retired`, then `[(1, 'legacy', 'retired')]`, then a log line ending in `No pet is alive. Waiting for the egg to hatch.`

- [ ] **Step 4: Start the viewer against the scratch API**

Stop any other dev server on port 5173 first (the API only allows CORS from port 5173).

```bash
cd frontend && VITE_API_URL=http://127.0.0.1:8001 npm run dev -- --port 5173 --strictPort
```

Open `http://127.0.0.1:5173/preview?debug` in the Browser pane.

- [ ] **Step 5: Check the egg and the hatch**

Take screenshots and confirm each item:

- The egg screen shows the note that Mimo has retired, the egg drawn by `EggScene`, its name (the same name curl printed), rarity, and five attributes with their tiers.
- **Lives** opens the list with life 1, "Retired after 1 day".
- **Hatch** turns into "Hatching…", the egg glows, then the world appears and the camera flies down from high above to the pet.
- The HUD shows the pet's name, `Day 1 · Dawn` or `Day 1 · Day` with a game time, the sun on the dial, five bars (Health, Hunger, Warmth, Energy, Air), "Standing still", a thought, and the buttons `Give snack · 1 left today` and `Bandage · 1 left today`.
- The world around the pet is new terrain (no station, no cottage) with a tree nearby. `curl -s http://127.0.0.1:8001/api/mimo | python3 -c "import json,sys,math; p=json.load(sys.stdin)['position']; print(round(math.hypot(p['x'], p['z'])))"` prints a number from 3000 to 6000.

- [ ] **Step 6: Watch a day, a night and a shelter**

At 60× a game day lasts 60 real seconds. Watch one full day and confirm:

- About 37 seconds after the hatch (dusk), the sky warms, then turns deep blue; the terrain dims smoothly to about a third of its brightness; the dial shows the moon; the status becomes "Sleeping"; a warm light appears on the pet; Warmth falls toward 30.
- About 60 seconds after the hatch (dawn), everything brightens smoothly again and the pet wakes ("Standing still").

Build a shelter and a lantern next to the pet, in the scratch world only:

```bash
docker exec -i mimo-check-api python - <<'EOF'
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld

registry = LifeRegistry()
world = SurvivalWorld(registry.world_path(registry.active_life()))
position = world.state()["position"]
x, y, z = round(position["x"]), round(position["y"]), round(position["z"])
for cell in ((x, y + 2, z), (x + 2, y, z), (x - 2, y, z), (x, y, z + 2)):
    world.put_block(*cell, "planks")
world.put_block(x, y, z - 2, "lantern")
print("shelter and lantern around", x, y, z)
EOF
```

Confirm the planks and the lantern appear in the viewer within a second or two. During the next night, confirm the lantern keeps its full brightness while the terrain around it dims, and Warmth settles near 75 instead of 30.

- [ ] **Step 7: Check care, hello and the phone layout**

- Click **Give snack**: Hunger rises by 30 (capped at 100), the button reads `Give snack · 0 left today` and is disabled, and "You gave <name> a snack." appears under "What happened".
- `curl -s -X POST -H 'Content-Type: application/json' -d '{"kind":"snack"}' http://127.0.0.1:8001/api/mimo/care` prints `{"detail":"No snack left today. The owner gets a new one each UTC day."}`.
- Click the pet or **Say hello**: the pet hops and "You said hello to <name>." appears.
- Resize the Browser pane to the mobile preset and reload: both HUD panels fit the width with no horizontal scroll, and the buttons wrap. Reset the viewport to desktop afterwards.

- [ ] **Step 8: Watch the death, the memorial and the archive**

Without further care the pet starves about 3.5 real minutes after the hatch (the snack adds about 36 seconds). Confirm:

- Before that, Hunger turns amber below 30 and red below 15, the thought changes to "My tummy is rumbling. I need food." and later "I'm starving...", and Health falls.
- `docker logs mimo-check-worker 2>&1 | grep "died of"` prints a line ending in `<name> died of starvation.`
- The page shows the memorial: "In memory of <name>", `Survived N days · died of starvation.` (N is 3 or 4), and notable events that include the death, starving, hunger and the snack.
- **View <name>'s world** opens the archive card ("Archive · read only") in daylight with the planks and lantern in place. **Back** returns to the memorial.
- **Hatch a new egg** shows the egg screen with a new egg. **Lives** lists #2 (`Survived N days · died of starvation`) and #1 (`Retired after 1 day`). **View world** on #1 shows the first world with the station and the home clearing drawn from the blueprint overlay. **Back**.
- **Hatch** again: life #3 starts in a different world.

- [ ] **Step 9: Confirm the legacy file was never written**

```bash
docker run --rm -v mimo_survival_check:/data mimo-survival-check sha256sum /data/mimo.sqlite3
curl -s http://127.0.0.1:8001/api/lives/1 | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['life']['kind'], len(d['state']['plans']), d['state']['plans'][0]['kind'])"
```

Expected: the same checksum as in Step 2, then `legacy 1 station`.

- [ ] **Step 10: Clean up the scratch run**

Stop the dev server (Ctrl+C), then remove only the scratch containers, volume and image this task created:

```bash
docker rm -f mimo-check-api mimo-check-worker
docker volume rm mimo_survival_check
docker image rm mimo-survival-check
```

- [ ] **Step 11: Rewrite the README**

Replace the whole of `README.md` with:

````markdown
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
````

- [ ] **Step 12: Run every check again and commit**

Run: `python3 -m unittest discover -s backend/tests && cd frontend && npm test && npm run build`
Expected: `Ran 137 tests` … `OK`, `Tests  106 passed (106)`, the build succeeds.

```bash
git add README.md
git commit -m "docs: describe lives, vitals and the survival worker" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Spec coverage

| Spec (M1) | Where |
|-----------|-------|
| §1 registry `lives.sqlite3`, columns, `MIMO_DATA_DIR`, survival worlds at `lives/<id>.sqlite3` | Task 4 |
| §1 legacy life 1 registered as retired, file never written | Tasks 3 (read-only store), 4, 14 Step 9 |
| §1 hatching: server egg roll, traits and floors, name, new seed, spawn rules, ±30,000 limit | Tasks 2, 3, 4, 7 |
| §1 death and archive, read-only `GET /api/lives`, `/api/lives/{id}`, `/api/lives/{id}/blocks` | Tasks 5, 7 |
| §2 world clock, phases, `server_time` | Tasks 1, 7, 10 |
| §3 vitals rates, warmth targets, shelter and fire checks, catch-up | Tasks 1, 5 |
| §4 snack and bandage per UTC day, hello, crafting help, no care for dead or unhatched pets | Tasks 3, 6, 7 |
| §9 HUD, day and night (sky, fog, daylight uniform, glow blocks, pet light), egg and hatch with camera fly-in, memorial, archive browser, care buttons | Tasks 9–13 |
| §10 API table (M1 rows), `plans` only for the legacy life | Task 7 |
| §11 worker ticks only the active life; no model calls in M1 | Task 8 |
| §12 registry or world missing → 503, worker logs and waits; clock jump catch-up | Tasks 5, 7, 8 |
| §13 simulation, lives, viewer unit tests; manual 60× run | Tasks 1–13 tests, Task 14 |

Out of scope here (later milestones): brain, pathfinding, timed actions and their animations, falls, food items and renewal, building.
