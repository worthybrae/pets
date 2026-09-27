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
from backend.survival.rings import ring_at
from backend.survival.ruins import RUIN, notice_ruins, ruins_near
from backend.survival.situation import Situation
from backend.survival.trips import REASONS, beyond, offers, targets, wanted_now
from backend.tests.test_survival_pickers import DAY
from backend.survival.replies import Heard
from backend.survival.requests import NONE, lapse_words, rules_request, to_do
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

    def test_a_geared_pet_on_low_health_keeps_the_goal_open(self):
        # Task 8 review, Minor 1 (tests): frontier_valid weighs only gear (rings.gear_short_of), so
        # health or food short of a ring's own line never closes the goal early -- the trip itself
        # waits instead (rings.ready_ring, which riches_wanted reads).
        pet = at_home(dict(GEARED))
        pet.state["vitals"]["health"] = 50.0  # short of the far wilds' own 70, gear aside
        self.assertTrue(is_open(pet.situation(), GOALS["frontier"]))

    def test_the_last_milestone_says_it_honestly(self):
        # Task 8 review, Minor 2: the milestone only counts a chest opened (home_with_loot: opened
        # since and back on home ground), so its words say that, not "with the loot" in Mimo's arms.
        self.assertEqual(GOALS["frontier"].milestones[-1].text, "Come home from an old ruin")

    def test_a_ruin_in_the_near_wilds_never_advances_the_goal(self):
        # Task 8 review, Minor 1 (tests): looting_far (goals.ADVANCES["loot_ruin"]) only counts a ruin
        # past the near wilds; one closer never sends a pet working on another goal home for it.
        home = (CHEST[0] - 100, 9, CHEST[2])  # 100 blocks from the chest: the near wilds (ring 1)
        pet = Pet(offset=(10, 0), center=(home[0], home[2]))
        remember(pet.db, RUIN, CHEST, 20.0, "near wilds")
        self.assertEqual(ring_at(pet.state, CHEST[0], CHEST[2]), 1)
        self.assertFalse(advances(pet.situation(), "loot_ruin", GOALS["frontier"]))

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

    def test_at_60x_the_chooser_times_the_walk_home_as_the_tick_does(self):
        # Pre-flight: the Chooser's Situation (situation.from_db) has action_scale 1 whatever the worker runs at.
        far = at_home(dict(GEARED), offset=(200, 0), clock={**DAY, "time_scale": 60.0})
        self.assertAlmostEqual(homeward_from(far.situation()), HOMEWARD - (200 * 0.3 * 1.5 + 60.0))

    def test_far_from_home_a_flight_runs_from_the_threat_not_all_the_way_home(self):
        far = at_home(dict(GEARED), offset=(200, 0))
        x, z = HOME[0] + 200, HOME[2]
        threat = {"id": 1, "kind": "gloomling", "x": float(x + 3), "y": 9.0, "z": float(z), "state": {"chasing": True}}
        with patch("backend.survival.creatures.defense.flee_threat", lambda situation, found: threat), \
                patch("backend.survival.creatures.defense.threats", lambda situation: [threat]):
            steps = plan_flee(far.situation(), None)
        self.assertLess(math.dist(steps[0]["target"][::2], (x, z)), 20)


class RequestTests(unittest.TestCase):
    def test_the_owner_can_ask_for_riches(self):
        # Pre-flight (carry 6): Bond's requests know the frontier goal's words, and say it in Mimo's words.
        statuses = {name: "open" for name in GOALS}
        for line in ("could you go find some treasure?", "please look for riches farther out",
                     "can you find treasure in the far wilds?"):
            self.assertEqual(rules_request(Heard(line), statuses), "frontier", line)
        self.assertEqual(rules_request(Heard("could you walk the far hills?"), statuses), "far_hills")
        self.assertEqual(to_do(GOALS["frontier"]), "go looking for riches farther out")
        self.assertEqual(lapse_words(GOALS["frontier"], False),
                         "I couldn't go looking for riches farther out in time. Ask me again?")

    def test_a_move_verb_can_ask_for_the_ruins_too(self):
        # Task 8 review, Minor 3: frontier was missing from requests.PLACE_GOALS, so a move verb
        # ("visit", "head", "go") asking only for a place never named it, unlike "find" or "look for".
        statuses = {name: "open" for name in GOALS}
        for line in ("could you visit the ruins?", "please head to the ruins", "can you go to the frontier?"):
            self.assertEqual(rules_request(Heard(line), statuses), "frontier", line)
        # The 8.1 negatives keep reading as none.
        for line in ("map out your day", "follow up"):
            self.assertEqual(rules_request(Heard(line), statuses), NONE, line)


class PayloadTests(unittest.TestCase):
    def test_the_model_is_told_the_ring_and_how_ready_mimo_is(self):
        pet = at_home(dict(GEARED), offset=(60, 0))
        frontier = context_payload(pet.situation(), [])["frontier"]
        self.assertEqual((frontier["ring"], frontier["name"], frontier["ready_for"], frontier["ready_for_name"]),
                         (1, "Near wilds", 2, "Far wilds"))


if __name__ == "__main__":
    unittest.main()
