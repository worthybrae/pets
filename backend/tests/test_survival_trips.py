import random
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from backend.services.worldgen import SEA_LEVEL
from backend.survival import brain  # noqa: F401  (registers every purpose and reason)
from backend.survival.choosing import Ask, Choice, decide, store_choice
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.pickers import options
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.situation import Situation
from backend.survival.triggers import ensure_brain
from backend.survival.trips import (
    REASONS, Find, Offer, Reason, Target, best_trip, look_after, offers, register_reason, serving, stand_near,
    start_trip, targets, trip_facts, trip_thought, trip_view,
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

    def test_the_lift_never_pushes_explore_past_the_survival_band(self):
        # Task 8 fix round 1: lift() used to add straight onto the reason's own score with no
        # ceiling, so a settled, maxed-out pet's explore trip could outscore eating or sleeping,
        # and stayed that way for good (a settled pet sits at curiosity 100). Capped at
        # SURVIVAL_FLOOR (80), the same ceiling a goal's own boost respects (goals.boosted), it
        # stops there instead.
        with only_reasons(test_reason(score=65.0)), patch("backend.survival.trips.LIFTS", [lambda s: 30.0]):
            hungry = pet()
            hungry["vitals"]["hunger"] = 15.0
            s = situation(hungry)
            self.assertEqual(PURPOSES["explore"].score(s), 80.0)  # 65 + 30 uncapped would be 95
            self.assertGreater(PURPOSES["eat"].score(s), PURPOSES["explore"].score(s))
            tired = pet()
            tired["vitals"]["energy"] = 10.0
            s = situation(tired)
            self.assertEqual(PURPOSES["explore"].score(s), 80.0)
            self.assertGreater(PURPOSES["sleep"].score(s), PURPOSES["explore"].score(s))

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
            found = targets(s, REASONS["things"])
            self.assertTrue(found)  # fix round 1: this used to pass on an empty set too
            self.assertLessEqual({t.distance for t in found}, {32, 33})  # none at 48 or 64

    def test_targets_and_stand_near_never_pick_a_water_cell(self):
        # Fix round 1: there was no lake case for the trips tests. flat_ground (setUp) keeps every
        # column's ground at 0, so a lake here is just water sitting on top of it.
        lake = lambda x, z: x > 20  # noqa: E731

        def natural(x, y, z):
            if y < 0:
                return "stone"
            if y == 0:
                return "grass"
            return "water" if lake(x, z) and y <= SEA_LEVEL else "air"

        grid = Grid(natural)
        self.assertIsNone(stand_near(situation(grid=grid), 30, 0))  # only water within SPOT_SLACK
        with only_reasons(test_reason(value=lambda s, x, z: (1.0, "east land"))):
            found = targets(situation(grid=grid), REASONS["things"])
            self.assertTrue(found)  # dry land on the near side is still offered
            self.assertTrue(all(target.cell[0] <= 20 for target in found))  # never a target on the water

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

    def test_a_fresh_trip_resets_batches_even_when_the_old_one_used_up_its_walks(self):
        # Fix round 1: an explore -> explore choice that picks a new reason does not change
        # `purpose`, so apply_choice never resets batches on its own; without start_trip doing it,
        # a fresh trip inherited the old one's count and, once that had reached EXPLORE_WALKS,
        # ended at once with nothing tried ("fails at once").
        with only_reasons(test_reason()):
            offer = best_trip(situation())
        brain = ensure_brain({})
        brain["batches"] = 3
        start_trip(brain, offer, 0.0, "rules")
        self.assertEqual(brain["batches"], 0)

    def test_a_trip_that_finds_nothing_in_three_walks_cools_its_reason_down(self):
        # Fix round 1: nothing used to stop the same reason from being offered again at once after
        # a trip spent every walk without finding what it came for.
        with only_reasons(test_reason()):
            s = situation()
            PURPOSES["explore"].plan(s, context())
            s.brain["batches"] = 3
            self.assertEqual(PURPOSES["explore"].plan(s, context()), [])  # every walk spent, nothing found
            self.assertGreater(s.brain["trip_penalties"]["things"], s.at)
        with only_reasons(test_reason(), test_reason("other")):
            cooled = situation(s.state)
            self.assertEqual([offer.reason for offer in offers(cooled)], ["other"])  # not offered for a while
            later = Situation(s.state, s.grid, s.clock, 301.0, s.db)  # the 300-second cooldown has passed
            self.assertEqual([offer.reason for offer in offers(later)], ["other", "things"])  # cooled down, not gone

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
