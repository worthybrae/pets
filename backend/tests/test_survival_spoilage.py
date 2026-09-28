"""W1: food that spoils, in lots that follow every move, for a wild pet only."""

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose registered)
from backend.survival.actions import ActionContext
from backend.survival.ailments import sickness
from backend.survival.clock import DAY_SECONDS
from backend.survival.cooking import cook_score
from backend.survival.hatch import hatch
from backend.survival.meals import wild_meal
from backend.survival.memory import know, set_home
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.spoilage import age, observe_lots, settle_lots, take, went_bad
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

    def test_the_chests_lots_settle_once_a_game_minute_not_on_every_step(self):
        # Carried item 4 (Task 7's ruling): Mimo's own lots settle every step, its chests' with their aging.
        state, where = pet({"raw_beef": 1}, chests={"0,1,0": {"raw_beef": 2}}), context()
        observe_lots(state, {"kind": "walk", "path": []}, where, 0.0)
        age(state, where, 30.0, 0.5)
        self.assertEqual((state["lots"]["raw_beef"][0][0], state.get("chest_lots", {})), (1, {}))
        age(state, where, 30.0, 1.0)
        self.assertEqual(sum(count for count, _ in state["chest_lots"]["0,1,0"]["raw_beef"]), 2)

    def test_mimo_names_nightberries_that_went_bad_as_it_sees_them(self):
        # Carried item 10: "red berries" while it does not know nightberries, their name once it does.
        s = situation({}, None, 100.0)
        s.state["difficulty"] = "wild"
        where = SimpleNamespace(db=s.db, events=[])
        went_bad(s.state, where, {"nightberries": 2}, "arms", 1.0)
        know(s.db, thing("nightberries"), "lesson", 1.5)
        went_bad(s.state, where, {"nightberries": 1}, "chest", 2.0)
        self.assertEqual([text for _, kind, text in where.events if kind == "spoiled"],
                         ["Pip's red berries went bad.", "Pip's nightberries went bad."])

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

    def test_keeping_puts_spoiled_food_in_the_composter_at_home(self):
        # Carried item 4 (Task 7's ruling; the spec, Hazards 3): at home with a composter standing, it walks over
        # and puts the spoiled food in; away from home, or with none, it drops it where it is.
        s = self.wild({"spoiled_food": 2}, 90.0, "keeping", grid=meadow({(6, 1, 0): "composter"}))
        set_home(s.db, (0, 1, 0), 0.0)
        walk, drop = PURPOSES["throw_out"].plan(s, None)
        self.assertEqual((walk["kind"], walk["target"]), ("walk", [6, 1, 0]))
        self.assertEqual(drop, {"kind": "drop", "item": "spoiled_food", "amount": 2})
        away = self.wild({"spoiled_food": 2}, 90.0, "keeping", grid=meadow({(6, 1, 0): "composter"}))
        set_home(away.db, (60, 1, 0), 0.0)
        self.assertEqual(PURPOSES["throw_out"].plan(away, None), [drop])

    def wild(self, inventory, hunger, *lessons, grid=None):
        s = situation(inventory, grid, hunger)
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
