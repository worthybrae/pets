import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every goal, purpose and reason)
from backend.survival.curiosity import curiosity_state
from backend.survival.expedition import (
    PACK_FOOD, expedition_view, observe_expedition, tend_expedition, torches_packed, trek_value,
)
from backend.survival.foraging import food_need
from backend.survival.goals import GOALS, adopt_goal, complete, is_open, progress_of
from backend.survival.memory import know, mark_explored
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES
from backend.survival.reflexes import by_name
from backend.survival.storage import KEEP, kept, more_kept
from backend.survival.trips import REASONS, WANDER_PENALTY_SECONDS, cool_down, wanted_now
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
        curiosity_state(pet.state, 0.0)["value"] = 30.0
        del pet.state["brain"]["expedition_at"]
        self.assertFalse(is_open(pet.situation(), expedition))  # not curious enough: below CURIOUS_ENOUGH (40)

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

    def test_while_it_packs_what_gives_way_to_food_goes_in_the_chest(self):
        pet = Expedition({"leather": 2, "rabbit_hide": 3, "coal": 1})
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        pet.tend(2.0)
        s = pet.situation()
        self.assertEqual((kept(s, "leather"), kept(s, "rabbit_hide"), kept(s, "coal")), (0, 0, KEEP["coal"]))
        pet.state["brain"]["expedition"]["phase"] = "out"
        self.assertEqual(kept(pet.situation(), "leather"), KEEP["leather"])  # out on the trip: kept as ever

    def test_with_no_room_for_torches_and_nothing_to_put_away_it_goes_without(self):
        arms = {"coal": 1, "planks": 3, "crafting_table": 1, "furnace": 1, "bread": 4, "apple": 1, "cooked_beef": 1}
        arms.update({f"{rank}_{tool}": 1 for rank in ("wooden", "stone", "iron") for tool in ("pickaxe", "axe", "sword")})
        pet = Expedition(arms)  # 16 stacks, and no chest to put anything in
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        pet.tend(2.0)
        self.assertEqual(torches_packed(pet.situation()), 1.0)  # no room to make them: it goes without
        del pet.state["inventory"]["iron_axe"]
        self.assertEqual(torches_packed(pet.situation()), 0.0)  # a stack free: room to make them

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


class TripTests(unittest.TestCase):
    def test_its_trip_cools_down_like_any_other_but_never_out_past_its_range(self):
        pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            pet.set_out()
        reason = REASONS["expedition"]
        self.assertEqual(reason.cooldown, WANDER_PENALTY_SECONDS)
        cool_down(pet.state["brain"], "expedition", 2.0, 1.0)
        pet.go(30, 1)  # within its explored range (48 blocks): the cooldown holds
        self.assertIsNone(wanted_now(pet.situation(), reason))
        pet.go(60, 1)  # past it: it travels on
        self.assertEqual(wanted_now(pet.situation(), reason), "I want to see what lies past the lands I know")


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
