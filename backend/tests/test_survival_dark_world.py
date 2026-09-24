import unittest
from unittest.mock import patch

from backend.services.blocks import CANOPY, is_canopy
from backend.services.worldgen import (
    FEATURE_TOP, LAVA_LEVEL, block_at, lava_in_chunk, region_openings, surface_opened, terrain_height,
)
from backend.survival.creatures.acts import act
from backend.survival.creatures.darkness import spots
from backend.survival.creatures.hostiles import BORED, BORED_REST, SIGHT_LOST
from backend.survival.creatures.moves import steps
from backend.survival.grid import Grid
from backend.survival.light import SKY_SCAN, Lights, light_at, sky_open
from backend.survival.pathing import moves
from backend.survival.reflexes import plan_collapse
from backend.tests.test_survival_hostiles import hostile, pet, scene
from backend.tests.test_survival_hostiles import meadow as hunting_ground
from backend.tests.test_survival_purposes import NIGHT, context, flat, situation

SEED = "1"


def generated():
    return Grid(lambda x, y, z: block_at(x, y, z, SEED))


def meadow(blocks=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    return grid


def opening_of(kind):
    """The first cave entrance of `kind` in the world "1", east of the legacy clearing."""
    for rx in range(4, 40):
        for rz in range(-4, 4):
            found, spans = region_openings(rx, rz, SEED)
            if found == kind:
                return spans
    raise AssertionError(f"no {kind}")


class CanopyTests(unittest.TestCase):
    def test_every_kind_of_leaves_is_canopy_by_a_block_property(self):
        self.assertEqual(CANOPY, frozenset({"leaves", "birch_leaves", "spruce_leaves"}))
        self.assertTrue(is_canopy("spruce_leaves"))
        self.assertFalse(is_canopy("oak_log") or is_canopy("not_a_block"))

    @patch("backend.survival.light.terrain_height", lambda x, z, seed: 0)
    def test_the_sky_shines_through_birch_and_spruce_leaves(self):
        grid = meadow({(0, 5, 0): "birch_leaves", (0, 7, 0): "spruce_leaves", (2, 5, 0): "stone"})
        self.assertTrue(sky_open(grid, SEED, (0, 1, 0)))
        self.assertFalse(sky_open(grid, SEED, (2, 1, 0)))

    @patch("backend.survival.creatures.darkness.terrain_height", lambda x, z, seed: 0)
    def test_no_hostile_comes_out_on_any_kind_of_leaves(self):
        grid = Grid(lambda x, y, z: ("spruce_leaves" if x == 0 else "grass") if y == 0 else "dirt" if y < 0 else "air")
        self.assertEqual(spots(grid, SEED, 0, 0, 1), [])
        self.assertEqual(spots(grid, SEED, 1, 0, 1), [(1, 1, 0)])


class SkyScanTests(unittest.TestCase):
    def test_the_scan_reaches_over_the_highest_tree_and_rock(self):
        self.assertGreater(SKY_SCAN, FEATURE_TOP)

    def test_a_sinkhole_is_open_to_its_floor_and_a_mouth_until_its_roof(self):
        grid = generated()
        (x, z), (bottom, _) = next(iter(opening_of("sinkhole").items()))
        self.assertTrue(sky_open(grid, SEED, (x, bottom, z)))
        spans = opening_of("mouth")
        opened = [(x, low, z) for (x, z), (low, _) in spans.items() if surface_opened(x, z, SEED)]
        roofed = [(x, low, z) for (x, z), (low, high) in spans.items() if high + 1 < terrain_height(x, z, SEED)]
        self.assertTrue(opened and roofed)
        self.assertTrue(all(sky_open(grid, SEED, cell) for cell in opened))
        self.assertFalse(any(sky_open(grid, SEED, cell) for cell in roofed))


class LavaLightTests(unittest.TestCase):
    def test_lava_the_generator_made_lights_the_cave_round_it(self):
        lava = next(cell for cx in range(12, 60) for cell in lava_in_chunk(cx, 3, SEED))
        x, y, z = lava
        self.assertEqual((y, block_at(x, y, z, SEED)), (LAVA_LEVEL, "lava"))
        grid = generated()
        above = (x, y + 1, z)
        lights = Lights(grid, above, 0, SEED)
        self.assertEqual((lights.at(above), lights.at((x, y + 16, z))), (14, 0))
        self.assertGreaterEqual(light_at(grid, SEED, above, True), 14)
        self.assertEqual(Lights(grid, above, 0).at(above), 0)  # without the seed, placed blocks only (L2)
        for cx in range(x // 16 - 1, x // 16 + 2):  # lava covered over gives no light
            for cz in range(z // 16 - 1, z // 16 + 2):
                for cell in lava_in_chunk(cx, cz, SEED):
                    grid.put(*cell, "stone")
        self.assertEqual(Lights(grid, above, 0, SEED).at(above), 0)


class DeepSpawnTests(unittest.TestCase):
    @patch("backend.survival.creatures.darkness.terrain_height", lambda x, z, seed: 40)
    def test_hostiles_can_come_out_beside_mimo_however_deep_it_is(self):
        grid = Grid(lambda x, y, z: "air" if (x, z) == (5, 0) and y in (0, 1) else "stone" if y <= 40 else "air")
        self.assertEqual(spots(grid, SEED, 5, 0, 0), [(5, 0, 0)])  # 40 under the hilltop


class FixtureTests(unittest.TestCase):
    def test_no_creature_climbs_a_ladder_or_steps_into_one(self):
        grid = meadow({(1, 1, 0): "ladder", (1, 2, 0): "ladder"})
        self.assertIn((1, 1, 0), list(moves(grid, (0, 1, 0))))  # Mimo can
        self.assertNotIn((1, 1, 0), steps(grid, (0, 1, 0), False))
        self.assertIn((1, 2, 0), list(moves(grid, (1, 1, 0))))
        self.assertNotIn((1, 2, 0), steps(grid, (1, 1, 0), False))

    def test_a_fence_ring_holds_what_is_inside_and_keeps_the_rest_out(self):
        ring = {(x, 1, z): "fence" for x in range(-2, 3) for z in range(-2, 3) if max(abs(x), abs(z)) == 2}
        grid = meadow(ring)
        for start in ((0, 1, 0), (1, 1, 1), (-1, 1, 0)):
            found = steps(grid, start, False)
            self.assertTrue(found, start)
            self.assertTrue(all(max(abs(x), abs(z)) <= 1 for x, _, z in found), (start, found))
        outside = steps(grid, (3, 1, 0), False)
        self.assertTrue(outside)
        self.assertTrue(all(max(abs(x), abs(z)) >= 3 for x, _, z in outside), outside)


class LoseInterestTests(unittest.TestCase):
    def test_a_chase_that_lands_no_blow_ends_after_45_game_seconds_and_leaves_mimo_be(self):
        grid, state = hunting_ground(), pet()
        keen = hostile(grid, cell=(10, 1, 0), chasing=True, chase_since=0.0, seen_at=BORED - 3.0)
        self.assertEqual(act(keen, scene(grid, state, at=BORED - 1.0)), "chase")
        self.assertEqual(keen["state"]["seen_at"], BORED - 1.0)  # Mimo is in plain sight
        bored = hostile(grid, cell=(10, 1, 3), chasing=True, chase_since=0.0, seen_at=BORED + 1.0)
        self.assertEqual(act(bored, scene(grid, state, at=BORED + 1.0)), "prowl")
        self.assertEqual((bored["state"]["chasing"], bored["state"]["bored_at"]), (False, BORED + 1.0))
        self.assertEqual(act(bored, scene(grid, state, at=BORED + BORED_REST)), "prowl")  # a minute's peace
        bored["state"]["hurt_at"] = BORED + BORED_REST  # unless Mimo hurts it
        self.assertEqual(act(bored, scene(grid, state, at=BORED + BORED_REST)), "chase")

    def test_a_blow_keeps_the_chase_going_and_losing_sight_of_mimo_ends_it(self):
        grid, state = hunting_ground(), pet()
        striking = hostile(grid, cell=(10, 1, 0), chasing=True, chase_since=0.0, struck_at=40.0, seen_at=50.0)
        self.assertEqual(act(striking, scene(grid, state, at=50.0)), "chase")
        lost = hostile(grid, cell=(10, 1, 3), chasing=True, chase_since=0.0, seen_at=0.0)
        self.assertEqual(act(lost, scene(grid, state, at=SIGHT_LOST + 1.0)), "prowl")


class CollapseTests(unittest.TestCase):
    def test_an_exhausted_pet_afloat_swims_for_land_before_it_lies_down(self):
        afloat = situation(clock=NIGHT, grid=flat(cells={(0, 0, 0): "water"}), places=[("home", (5, 1, 0))])
        self.assertEqual(plan_collapse(afloat, context()),
                         [{"kind": "walk", "target": [5, 1, 0], "reach": 0.0}, {"kind": "sleep"}])
        self.assertEqual(plan_collapse(situation(clock=NIGHT), context()), [{"kind": "sleep"}])


if __name__ == "__main__":
    unittest.main()
