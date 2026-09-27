import unittest

from backend.survival import brain  # noqa: F401  (registers the ringed hostiles' hooks)
from backend.survival.creatures.darkness import HOSTILE_CAP, born, cap
from backend.survival.creatures.defense import FIGHT_FROM, FLEE_BELOW, fight_from, flee_below, flee_due
from backend.survival.creatures.hostiles import strike_pet
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.ringed import ELDER_CHANCE, elder_roll
from backend.survival.creatures.view import creature_view
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_darkness import land, pet, scene
from backend.tests.test_survival_defense import meadow, pet as defended, situation


def far_out(x=0.0, center=(0, 0)):
    """Mimo standing at (x, 1, 0), with the rings centred on `center`."""
    state = pet()
    state["position"]["x"] = x
    state["frontier"] = {"center": list(center)}
    state["name"], state["vitals"] = "Pip", dict(START_VITALS)
    return state


class TougherTests(unittest.TestCase):
    def test_at_home_a_hostile_is_as_it_always_was(self):
        grid = land()
        creature = born(scene(grid, far_out()), KINDS["gloomling"], (20, 1, 0))
        self.assertEqual(creature["health"], 20.0)
        self.assertEqual({key: creature["state"].get(key) for key in ("ring", "most", "fiercer", "elder")},
                         {"ring": None, "most": None, "fiercer": None, "elder": None})

    def test_in_the_far_wilds_it_has_more_health_and_hits_harder(self):
        grid = land()
        creature = born(scene(grid, far_out(150.0)), KINDS["gloomling"], (170, 1, 0))
        self.assertEqual(creature["health"], 34.0)  # 20, and 35 % a level for 2 levels
        self.assertEqual((creature["state"]["ring"], creature["state"]["most"], creature["state"]["fiercer"]),
                         (2, 34.0, 1.0))
        skitter = born(scene(grid, far_out(60.0)), KINDS["skitter"], (80, 1, 0))
        self.assertEqual((skitter["health"], skitter["state"].get("fiercer")), (16.2, None))  # ring 1: health only

    def test_from_the_frontier_some_are_elders(self):
        grid = land()
        where = far_out(300.0)
        cells = [(320 + dx, 1, dz) for dx in range(6) for dz in range(6)]
        elders = [cell for cell in cells if elder_roll(scene(grid, where), cell) < ELDER_CHANCE[3]]
        self.assertTrue(0 < len(elders) < len(cells))
        creature = born(scene(grid, where), KINDS["gloomling"], elders[0])
        self.assertTrue(creature["state"]["elder"])
        self.assertEqual((creature["health"], creature["state"]["fiercer"]), (61.5, 2.0))  # 20 x 2.05 x 1.5
        view = creature_view(creature, 100.0)
        self.assertEqual((view["elder"], view["health"]), (True, 1.0))

    def test_its_blow_takes_the_extra_damage(self):
        grid = land()
        state = far_out(150.0)
        creature = born(scene(grid, state), KINDS["gloomling"], (151, 1, 0))
        strike_pet(creature, KINDS["gloomling"], scene(grid, state))
        self.assertEqual(state["vitals"]["health"], 96.0)  # 3 and 1 for the far wilds

    def test_the_health_bar_reads_the_hostile_s_own_full_health(self):
        grid = land()
        creature = born(scene(grid, far_out(150.0)), KINDS["gloomling"], (170, 1, 0))
        creature["health"] = 17.0
        self.assertEqual(creature_view(creature, 100.0)["health"], 0.5)

    def test_the_cap_grows_one_a_level_of_the_ring_mimo_stands_in(self):
        grid = land()
        self.assertEqual(cap(scene(grid, far_out())), HOSTILE_CAP)
        self.assertEqual(cap(scene(grid, far_out(150.0))), HOSTILE_CAP + 2)


class CautionTests(unittest.TestCase):
    def test_far_out_mimo_runs_sooner_and_fights_from_more_health(self):
        grid = meadow()
        home = defended(frontier={"center": [0, 0]})
        self.assertEqual((flee_below(situation(grid, home)), fight_from(situation(grid, home))), (FLEE_BELOW, FIGHT_FROM))
        far = defended(frontier={"center": [-150, 0]})
        self.assertEqual((flee_below(situation(grid, far)), fight_from(situation(grid, far))), (40.0, 55.0))
        deeper = defended(frontier={"center": [-300, 0]})
        self.assertEqual(flee_below(situation(grid, deeper)), 45.0)

    def test_at_38_health_a_threat_sends_mimo_running_in_the_far_wilds_only(self):
        grid = meadow()
        grid.herd.add("gloomling", (5, 1, 0), 20.0, 0.0, 0.0, {"home": [5, 1, 0], "chasing": True})
        home = defended(inventory={"stone_sword": 1}, frontier={"center": [0, 0]})
        home["vitals"]["health"] = 38.0
        self.assertFalse(flee_due(situation(grid, home)))
        far = defended(inventory={"stone_sword": 1}, frontier={"center": [-150, 0]})
        far["vitals"]["health"] = 38.0
        self.assertTrue(flee_due(situation(grid, far)))


if __name__ == "__main__":
    unittest.main()
