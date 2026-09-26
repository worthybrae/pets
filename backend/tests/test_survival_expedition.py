import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every goal, purpose and reason)
from backend.survival import purposes, storage
from backend.survival.choosing import goal_route
from backend.survival.creatures.gear import GEAR_MATERIALS
from backend.survival.curiosity import curiosity_state
from backend.survival.exploring import COMPASS
from backend.survival.expedition import (
    PACK_FOOD, expedition_view, heading_of, home_built, observe_expedition, tend_expedition, torches_packed,
    trek_value,
)
from backend.survival.foraging import food_need
from backend.survival.goals import (
    GOALS, IDLE, STALL, adopt_goal, check_goal, complete, is_open, offers, progress_of,
)
from backend.survival.memory import know, mark_explored
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES, away
from backend.survival.reflexes import by_name
from backend.survival.storage import KEEP, chest_spot, kept, more_kept, to_store
from backend.survival.trips import REASONS, WANDER_PENALTY_SECONDS, cool_down, wanted_now
from backend.survival.work import ladder_ores
from backend.tests.test_survival_life_goals import built

DUSK = {"phase": "dusk", "seconds_into_day": 2250.0, "time_scale": 1.0, "day_number": 2}
NIGHT = {"phase": "night", "seconds_into_day": 2500.0, "time_scale": 1.0, "day_number": 2}
MORNING = {"phase": "day", "seconds_into_day": 400.0, "time_scale": 1.0, "day_number": 3}
PACKED = {"bread": 4, "torch": 4, "campfire": 1, "dirt": 4}  # bread restores 25 hunger: 100 in all
FLAT = lambda x, z, seed: 0  # noqa: E731
DRY = lambda x, z, seed: 10  # noqa: E731  (dry land, at or above SEA_LEVEL, so heading_of tells bearings apart)


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
        del pet.state["brain"]["expedition_at"]
        curiosity_state(pet.state, 0.0)["value"] = 45.0
        self.assertTrue(is_open(pet.situation(), expedition))  # fix round 1: 45 is enough -- the gate is 40, not 60
        curiosity_state(pet.state, 0.0)["value"] = 30.0
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

    def test_a_hurt_pet_packed_to_go_waits_until_it_is_well(self):
        # The final fix wave, (a): a packed pet at 30 health set out, turned home on its health at the
        # next tend and "came home from its expedition: 0 blocks out", reaching the goal.
        pet = Expedition()
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        pet.state["inventory"] = dict(PACKED)
        pet.state["vitals"]["health"] = 30.0
        with patch("backend.survival.expedition.terrain_height", FLAT):
            events = pet.tend(2.0).events + pet.tend(3.0).events
            self.assertEqual(pet.state["brain"]["expedition"]["phase"], "packing")
            self.assertEqual(events, [])
            self.assertFalse(complete(pet.situation(), GOALS["expedition"]))
            pet.state["vitals"]["health"] = 100.0
            context = pet.tend(4.0)
        self.assertEqual(pet.state["brain"]["expedition"]["phase"], "out")
        self.assertEqual(context.events, [(4.0, "expedition", "Pip set out on an expedition to the east.")])

    def test_while_it_packs_what_gives_way_to_food_goes_in_the_chest(self):
        # gold isn't a gear material, so it gives way to food like any other GIVES_WAY_TO_FOOD item.
        pet = Expedition({"gold_ore": 2, "gold_ingot": 1, "coal": 1})
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        pet.tend(2.0)
        s = pet.situation()
        self.assertEqual((kept(s, "gold_ore"), kept(s, "gold_ingot"), kept(s, "coal")), (0, 0, KEEP["coal"]))
        pet.state["brain"]["expedition"]["phase"] = "out"
        self.assertEqual(kept(pet.situation(), "gold_ore"), KEEP["gold_ore"])  # out on the trip: kept as ever

    def test_while_it_packs_the_gold_the_pickaxe_ladder_counts_is_kept(self):
        # The final fix wave, (b): from an iron pickaxe until a gold one, mine_ore counts the gold ore
        # and ingots Mimo carries toward the gold pickaxe (work.wanted_ores); packing put them in the
        # chest at home, and mine_ore then went after gold that lay in the chest.
        self.assertEqual(ladder_ores({"stone_pickaxe": 1}), set())
        self.assertEqual(ladder_ores({"iron_pickaxe": 1}), {"gold_ore", "gold_ingot"})
        self.assertEqual(ladder_ores({"iron_pickaxe": 1, "gold_pickaxe": 1}), set())
        self.assertEqual(ladder_ores({"diamond_pickaxe": 1}), set())
        pet = Expedition({"gold_ore": 2, "gold_ingot": 1, "iron_pickaxe": 1, "coal": 1})
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        pet.tend(2.0)
        s = pet.situation()
        self.assertEqual(pet.state["brain"]["expedition"]["phase"], "packing")
        self.assertEqual((kept(s, "gold_ore"), kept(s, "gold_ingot")), (KEEP["gold_ore"], KEEP["gold_ingot"]))
        pet.state["inventory"]["gold_pickaxe"] = 1  # the ladder is past gold: it gives way to food again
        s = pet.situation()
        self.assertEqual((kept(s, "gold_ore"), kept(s, "gold_ingot")), (0, 0))

    def test_while_it_packs_gear_materials_gear_still_wants_are_kept(self):
        # Fix round 1, Important 3: packing never gives away leather, hides, string, feathers or
        # flint that armor_up or the bow still wants (creatures.gear.materials_wanted); only what
        # gear does not want gives way to food.
        arms = {"leather": 3, "rabbit_hide": 8, "string": 2, "feather": 3, "flint": 3, "coal": 2,
                "sticks": 6, "oak_log": 4, "planks": 10, "cobblestone": 20, "bread": 2,
                "wooden_pickaxe": 1, "stone_pickaxe": 1, "crafting_table": 1}
        pet = Expedition(dict(arms))  # armor and bow still unmade: gear wants every one of these
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        pet.tend(2.0)
        s = pet.situation()
        self.assertEqual(pet.state["brain"]["expedition"]["phase"], "packing")
        cell = chest_spot(s)
        stored = {item for item, _ in to_store(s, cell)}
        self.assertFalse(stored & set(GEAR_MATERIALS))  # armor and bow materials still wanted: kept
        self.assertIn("cobblestone", stored)  # ordinary junk still goes in the chest

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
        # Fix round 1, Important 2: FLAT is below SEA_LEVEL, so every bearing used to score 0 and the
        # answer was always index 0 ("east") regardless of what was marked known. DRY is dry land, so
        # heading_of can actually tell an explored bearing from an unexplored one.
        with patch("backend.survival.expedition.terrain_height", DRY):
            pet.set_out()
        s = pet.situation()
        self.assertEqual(REASONS["expedition"].wanted(s), "I want to see what lies past the lands I know")
        self.assertEqual(pet.state["brain"]["expedition"]["direction"], "east")  # the untouched direction wins
        self.assertEqual(trek_value(s, 101, 1), (1.0, "land past what it knows"))
        self.assertEqual(trek_value(s, 1, 101), (0.5, "land past what it knows"))  # south: off the heading
        self.assertEqual(trek_value(s, -99, 1), (0.0, ""))
        self.assertEqual(trek_value(s, 31, 1), (0.4, "the way out"))

    def test_the_heading_avoids_ground_it_already_knows(self):
        # A separate pet: only the east is known this time, so the heading must not be "east".
        other = Expedition()
        home = home_built(other.situation())
        mark_explored(other.world.db, [(rx, 0) for rx in range(0, 14)], 1.0)  # the east is known ground
        with patch("backend.survival.expedition.terrain_height", DRY):
            heading = heading_of(other.world.db, other.state["world_seed"], home, 48.0)
        self.assertNotEqual(COMPASS[heading], "east")
        self.assertEqual(COMPASS[heading], "southeast")


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

    def test_an_early_turn_home_still_reaches_the_goal(self):
        # Fix round 1, Important 1: turning home short of the target or before any night still
        # completes the goal once Mimo is back (resolution 12: "within 6 blocks of home... either
        # way"). Health under LOW_HEALTH turns it home at once, by day, with no night camped.
        pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            pet.set_out()
        trek = pet.state["brain"]["expedition"]
        pet.go(60, 1)
        pet.state["vitals"]["health"] = 30.0
        pet.tend(10.0, MORNING)
        self.assertEqual(trek["phase"], "homeward")
        pet.go(2, 1)
        pet.tend(20.0, MORNING)
        self.assertEqual(trek["phase"], "home")
        s = pet.situation(MORNING)
        self.assertTrue(complete(s, GOALS["expedition"]))
        context = pet.context(MORNING)
        check_goal(pet.state, context, 21.0, False)
        self.assertEqual(context.events[-1][1:], ("goal", "Pip reached a goal: an expedition."))

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        pet = Expedition()
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        forget_logged()
        with patch("backend.survival.expedition.packed", side_effect=RuntimeError("boom")), \
                self.assertLogs("backend.survival.expedition", level="ERROR") as logs:
            pet.tend(2.0)
            pet.tend(3.0)
        self.assertEqual(len(logs.output), 1)


class HoldTests(unittest.TestCase):
    """L4b final fix wave, I2: every night out was followed by a dawn goal choice, and under Jev any
    goal on offer could replace the expedition 150-200 blocks from home (9 of 14 fake-Jev expeditions
    never came home as one); the idle rule set it aside too, out past its target by midday. From
    setting out until home the expedition holds (Goal.holds): it is offered alone, so the rules keep
    it and Jev is not asked, and it never idles; only the dawn stall ends it early."""

    def test_out_from_home_it_is_the_only_goal_on_offer_and_the_rules_keep_it(self):
        pet = Expedition()
        adopt_goal(pet.state, "expedition", "utility", "", 1.0)
        pet.tend(2.0)
        packing = [goal.name for goal, _, _ in offers(pet.situation())]
        self.assertIn("expedition", packing)
        self.assertGreater(len(packing), 1)  # packing at home: another goal may still be chosen
        pet.state["inventory"] = dict(PACKED)
        with patch("backend.survival.expedition.terrain_height", FLAT):
            pet.tend(3.0)
        pet.go(101, 1)
        for phase in ("out", "homeward"):
            pet.state["brain"]["expedition"]["phase"] = phase
            s = pet.situation(MORNING)
            found = offers(s)
            self.assertEqual([goal.name for goal, _, _ in found], ["expedition"])
            self.assertEqual(goal_route(s.brain, 10.0, {"TYPESAFE_API_KEY": "k"}, 10.0, len(found)), "utility")

    def test_out_past_its_target_with_nothing_to_do_it_never_idles_but_a_stall_still_ends_it(self):
        pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            pet.set_out()
        pet.go(101, 1)
        trek = pet.state["brain"]["expedition"]
        trek["far"] = trek["target"]
        check_goal(pet.state, pet.context(MORNING), 10.0, False)  # progress read: best_at 10
        with patch("backend.survival.goals.workable", return_value=False):  # the land around is walked out
            context = pet.context(MORNING)
            check_goal(pet.state, context, 10.0 + IDLE + 70.0, False)
            self.assertEqual(pet.state["brain"]["goal"]["name"], "expedition")
            self.assertEqual(context.events, [])
            trek["phase"] = "packing"  # not out from home: the same idling sets it aside
            check_goal(pet.state, context, 10.0 + IDLE + 140.0, False)
            self.assertIsNone(pet.state["brain"]["goal"])
        pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            pet.set_out()
        pet.go(101, 1)
        check_goal(pet.state, pet.context(MORNING), 10.0, True)
        context = pet.context(MORNING)
        check_goal(pet.state, context, 10.0 + STALL + 1.0, True)  # a day out with no progress at all
        self.assertIsNone(pet.state["brain"]["goal"])
        self.assertEqual(context.events[-1][2], "Pip set a goal aside for now: an expedition (no progress for a day).")


class CrashGuardTests(unittest.TestCase):
    """Fix round 1, minor: AWAY and KEEPS_MORE hooks crash-guard like tend_expedition itself
    (global-constraints.md: "a crash in ... an AWAY check or a KEEPS_MORE hook never stops a tick
    or the worker ... logged once")."""

    def test_a_crashing_away_hook_is_logged_once_and_go_home_still_works(self):
        pet = Expedition()
        pet.go(50, 1)  # away from home, but not on an expedition: the real hook says no
        forget_logged()

        def boom(s):
            raise RuntimeError("boom")

        purposes.AWAY.append(boom)
        try:
            with self.assertLogs("backend.survival.purposes", level="ERROR") as logs:
                s = pet.situation()
                self.assertFalse(away(s))  # a crashing hook counts as no
                self.assertFalse(away(s))  # the same error again: no new log
                self.assertTrue(PURPOSES["go_home"].valid(s))  # go_home still works
            self.assertEqual(len(logs.output), 1)
        finally:
            purposes.AWAY.remove(boom)

    def test_a_crashing_keeps_more_hook_is_logged_once_and_the_keep_is_unchanged(self):
        pet = Expedition()
        forget_logged()

        def boom(s, item):
            raise RuntimeError("boom")

        storage.KEEPS_MORE.append(boom)
        try:
            with self.assertLogs("backend.survival.storage", level="ERROR") as logs:
                s = pet.situation()
                self.assertEqual(more_kept(s, "torch"), 0.0)  # a crashing hook adds nothing
                self.assertEqual(more_kept(s, "food"), 0.0)  # the same error again: no new log
            self.assertEqual(len(logs.output), 1)
        finally:
            storage.KEEPS_MORE.remove(boom)


if __name__ == "__main__":
    unittest.main()
