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
        self.assertAlmostEqual(after["health"], 51.0)  # 1 a game minute (L2)
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
