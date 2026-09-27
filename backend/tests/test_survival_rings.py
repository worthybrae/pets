import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.actions import ActionContext
from backend.survival.brain import BRAIN
from backend.survival.hatch import hatch
from backend.survival.memory import BUILT, create_memory_tables, remember, set_home
from backend.survival.rings import (
    center, ready_ring, ring_at, ring_name, ring_of_distance, ring_payload, ring_view, short_of, tend_frontier,
)
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import survival_view
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld
from backend.tests.test_survival_pickers import DAY, situation

GEARED = {"stone_sword": 1, "leather_cap": 1, "leather_tunic": 1, "bread": 2}


def tended(position=(0.0, 1.0, 0.0), home=None, note=BUILT, state=None):
    """A state the tick tended once at `position`, with a home place at `home` (noted `note`)."""
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    if home is not None:
        set_home(db, home, 0.0, note)
    state = state or {"name": "Pip", "position": dict(zip("xyz", position))}
    context = ActionContext(grid=None, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=db)
    tend_frontier(state, context, 5.0)
    return state, context, db


class RingTests(unittest.TestCase):
    def test_distance_from_home_sets_the_ring(self):
        self.assertEqual([ring_of_distance(d) for d in (0, 47.9, 48, 127.9, 128, 255, 256, 511, 512, 9000)],
                         [0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
        self.assertEqual([ring_name(ring) for ring in range(5)],
                         ["Home ground", "Near wilds", "Far wilds", "Frontier", "Deep frontier"])

    def test_the_birthplace_is_the_centre_until_a_home_stands(self):
        state, context, db = tended(position=(10.0, 1.0, 20.0))
        self.assertEqual(state["frontier"]["birthplace"], [10, 20])
        self.assertEqual(center(state), (10.0, 20.0))
        self.assertEqual(ring_at(state, 10 + 130, 20), 2)
        remember(db, "home", (40, 1, 20), 1.0)  # a sheltered spot Mimo found is no home it built
        state["position"] = {"x": 40.0, "y": 1.0, "z": 20.0}
        tend_frontier(state, context, 6.0)
        self.assertEqual(center(state), (10.0, 20.0))

    def test_rings_move_with_the_home_mimo_built(self):
        state, context, db = tended(position=(300.0, 1.0, 0.0), home=(100, 1, 0))
        self.assertEqual((center(state), state["frontier"]["ring"]), ((100.0, 0.0), 2))
        set_home(db, (250, 1, 0), 7.0)  # a bigger home, farther out
        tend_frontier(state, context, 8.0)
        self.assertEqual((center(state), state["frontier"]["ring"]), ((250.0, 0.0), 1))

    def test_a_save_from_before_the_rings_takes_its_oldest_home_as_its_birthplace(self):
        state, _, _ = tended(position=(90.0, 1.0, 0.0), home=(30, 1, 0), note="")
        self.assertEqual(state["frontier"]["birthplace"], [30, 0])
        self.assertEqual(state["frontier"]["ring"], 1)

    def test_the_first_steps_into_the_far_wilds_and_beyond_are_notable(self):
        state, context, _ = tended(position=(60.0, 1.0, 0.0), home=(0, 1, 0))
        for x in (140.0, 60.0, 150.0, 300.0):
            state["position"]["x"] = x
            tend_frontier(state, context, 9.0)
        self.assertEqual([text for _, kind, text in context.events if kind == "found"],
                         ["Pip reached the far wilds for the first time.", "Pip reached the frontier for the first time."])
        self.assertEqual(state["frontier"]["reached"], 3)

    def test_the_viewer_is_told_the_ring_where_mimo_stands(self):
        state, _, _ = tended(position=(200.0, 1.0, 0.0), home=(0, 1, 0))
        self.assertEqual(ring_view(state), {"level": 2, "name": "Far wilds", "center": {"x": 0, "z": 0}})
        self.assertIsNone(ring_view({"position": {"x": 0.0, "y": 1.0, "z": 0.0}}))


class ReadinessTests(unittest.TestCase):
    def test_rings_zero_and_one_are_open_to_every_pet(self):
        s = situation()
        self.assertEqual(ready_ring(s), 1)
        self.assertEqual(short_of(s, 1), [])
        self.assertEqual(short_of(s, 2), ["a stone sword or better", "leather armor or better", "food for half a day"])

    def test_a_pet_armed_armored_well_and_fed_is_ready_for_the_far_wilds(self):
        self.assertEqual(ready_ring(situation(inventory=dict(GEARED))), 2)
        bow = {"bow": 1, "arrow": 8, "leather_cap": 1, "leather_tunic": 1, "bread": 2}
        self.assertEqual(ready_ring(situation(inventory=bow)), 2)
        hurt = situation(inventory=dict(GEARED))
        hurt.vitals["health"] = 60.0
        self.assertEqual((ready_ring(hurt), short_of(hurt, 2)), (1, ["70 health"]))

    def test_the_frontier_takes_iron_a_bow_and_arrows(self):
        iron = {"iron_sword": 1, "iron_cap": 1, "iron_tunic": 1, "bread": 2}
        self.assertEqual(ready_ring(situation(inventory=iron)), 2)
        self.assertEqual(short_of(situation(inventory=iron), 3), ["a bow and 8 arrows"])
        self.assertEqual(ready_ring(situation(inventory={**iron, "bow": 1, "arrow": 8})), 3)

    def test_the_model_is_told_the_ring_and_what_the_next_one_takes(self):
        s = situation(inventory=dict(GEARED))
        s.state["frontier"] = {"center": [0, 0]}
        s.state["position"]["x"] = 60.0
        self.assertEqual(ring_payload(s), {"ring": 1, "name": "Near wilds", "danger": 1, "blocks_from_home": 60,
                                           "ready_for": 2, "ready_for_name": "Far wilds",
                                           "short_of_next": ["an iron sword or better", "a bow and 8 arrows",
                                                             "iron armor or better"]})


class StreamTests(unittest.TestCase):
    def test_api_mimo_names_the_ring_once_the_tick_tended_it(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=1_000_000.0)
            world = SurvivalWorld(registry.world_path(life))
            tick_life(registry, 1_000_010.0, mind=BRAIN)
            view = survival_view(world, 1_000_010.0, 1.0)
        self.assertEqual(view["ring"]["level"], 0)
        self.assertEqual(view["ring"]["name"], "Home ground")


if __name__ == "__main__":
    unittest.main()
