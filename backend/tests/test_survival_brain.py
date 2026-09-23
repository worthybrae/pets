import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.brain import BRAIN, brain_plan, notice_step, observe_step
from backend.survival.choosing import Choice, apply_choice
from backend.survival.clock import clock_at
from backend.survival.pickers import options, utility_pick
from backend.survival.reflexes import reflex_hook
from backend.survival.situation import in_tick
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
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
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

    def test_waiting_for_a_choice_at_night_is_sleeping(self):
        state = pet()
        plan = brain_plan(state, brainy(clock=lambda at: NIGHT), 0.0)
        self.assertEqual([step["kind"] for step in plan], ["sleep"])
        self.assertEqual(state["brain"]["pending"]["reasons"], ["born"])

    def test_a_purpose_plans_tagged_batches_until_it_is_done(self):
        state = pet()
        choose(state, "rest")
        ctx = brainy()
        self.assertEqual(brain_plan(state, ctx, 0.0), [{"kind": "wait", "seconds": 10.0, "purpose": "rest"}])
        self.assertEqual(brain_plan(state, ctx, 10.0), [{"kind": "wait", "seconds": 10.0, "purpose": "rest"}])
        state["brain"]["batches"] = 59
        self.assertEqual(brain_plan(state, ctx, 600.0), WAIT)
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

    def test_an_ore_that_cannot_be_reached_is_forgotten(self):
        state = pet(inventory={"stone_pickaxe": 1})
        choose(state, "mine_ore")
        ctx = brainy(flat({(20, -3, 0): "coal_ore"}))
        remember(ctx.db, "ore", (20, -3, 0), 0.0, "coal_ore")
        self.assertEqual(brain_plan(state, ctx, 0.0)[0]["target"], [20, -3, 0])
        for seq in (1, 2):
            state["last_failure"] = {"code": "no_path", "reason": "no way there", "kind": "walk",
                                     "cell": {"x": 20, "y": -3, "z": 0}, "purpose": "mine_ore", "at": 1.0, "seq": seq}
            brain_plan(state, ctx, 1.0)
        self.assertEqual(places(ctx.db), [])
        self.assertIn("mine_ore", state["brain"]["penalties"])

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


class DuskTests(unittest.TestCase):
    def test_a_pet_outdoors_near_dusk_goes_home_and_sleeps_without_going_back_out(self):
        """Exploring on open ground 40 minutes into the afternoon with a home 20 blocks away: the
        head_home reflex walks it home, and the utility picker, asked whenever a choice is
        pending, keeps it there until it sleeps at night."""
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        remember(db, "home", (20, 1, 0), 0.0)
        state = pet()
        choose(state, "explore")
        state["queue"] = [{"kind": "walk", "target": [0, 1, 40], "reach": 3.0, "purpose": "explore"}]
        grid, rng = flat(), random.Random(3)
        clock = lambda at: clock_at(0.0, 2000.0 + at)  # noqa: E731  (2,040 s into the day at 40)
        walks_after_home = set()
        for at in range(0, 440):
            ctx = ActionContext(grid=grid, clock_at=clock, planner=brain_plan, events=[], db=db,
                                interrupt=reflex_hook)
            advance_actions(state, ctx, float(at))
            if state["brain"]["pending"] is not None:
                pick = utility_pick(options(in_tick(state, ctx, float(at))), rng)
                apply_choice(state, Choice(pick, "utility", "Hm.", {"model": 0, "luna": 0, "reflections": 0}),
                             float(at))
            home_at = state["brain"]["reflex_ends"].get("head_home")
            if home_at is not None:
                walks_after_home |= {(entry["started_at"], entry.get("purpose")) for entry in state["recent_actions"]
                                     if entry["kind"] == "walk" and entry["ended_at"] > home_at
                                     and entry.get("purpose") not in ("head_home", "go_home")}
        self.assertEqual(clock(439.0)["phase"], "night")
        self.assertEqual((state["action"] or {}).get("kind"), "sleep")
        self.assertEqual(state["position"], {"x": 20.0, "y": 1.0, "z": 0.0})
        self.assertEqual(walks_after_home, set())
        self.assertIn("head_home", state["brain"]["reflex_ends"])


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
