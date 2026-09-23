import random
import unittest
from collections import Counter

from backend.survival.eggs import (
    ATTRIBUTE_POOLS, NAMES, TIER_POINTS, TRAITS, egg_name, pick_name, rarity_for, roll_egg, roll_tier,
    roll_traits, trait_floors,
)


def egg_of_tier(tier):
    """An egg whose five attributes all come from one tier."""
    attributes = []
    for category, options in ATTRIBUTE_POOLS:
        name, _, value = next(option for option in options if option[1] == tier)
        attributes.append({"category": category, "option": {"name": name, "tier": tier, "value": value},
                           "points": TIER_POINTS[tier]})
    total = sum(attribute["points"] for attribute in attributes)
    return {"attributes": attributes, "name": egg_name(attributes), "totalPoints": total, "rarity": rarity_for(total)}


class EggTests(unittest.TestCase):
    def test_tiers_follow_the_viewer_probabilities(self):
        rng = random.Random(1)
        counts = Counter(roll_tier(rng) for _ in range(20000))
        for tier, share in (("common", 0.40), ("uncommon", 0.25), ("rare", 0.20), ("legendary", 0.14)):
            self.assertAlmostEqual(counts[tier] / 20000, share, delta=0.015, msg=tier)
        self.assertTrue(0.004 <= counts["mythic"] / 20000 <= 0.017)

    def test_an_egg_has_one_attribute_per_pool_in_the_viewer_shape(self):
        egg = roll_egg(random.Random(7))
        self.assertEqual([attribute["category"] for attribute in egg["attributes"]],
                         ["shape", "scales", "color", "size", "mist"])
        pools = dict(ATTRIBUTE_POOLS)
        for attribute in egg["attributes"]:
            option = attribute["option"]
            self.assertIn((option["name"], option["tier"], option["value"]), pools[attribute["category"]])
            self.assertEqual(attribute["points"], TIER_POINTS[option["tier"]])
        self.assertEqual(egg["totalPoints"], sum(attribute["points"] for attribute in egg["attributes"]))
        self.assertEqual(egg["rarity"], rarity_for(egg["totalPoints"]))
        self.assertEqual(egg["name"], egg_name(egg["attributes"]))

    def test_egg_names_read_like_the_viewer_names(self):
        self.assertEqual(egg_of_tier("uncommon")["name"], "Amber Hexscale Squat")
        self.assertEqual(egg_of_tier("mythic")["name"], "Colossal Iridescent Prismatic Spire")

    def test_rarity_thresholds(self):
        for points, rarity in ((0, "common"), (2, "common"), (2.5, "uncommon"), (4.5, "rare"),
                               (6.5, "legendary"), (8.5, "mythic"), (10, "mythic")):
            self.assertEqual(rarity_for(points), rarity, points)

    def test_the_same_random_state_gives_the_same_egg(self):
        self.assertEqual(roll_egg(random.Random(5)), roll_egg(random.Random(5)))

    def test_rarer_eggs_raise_trait_floors(self):
        common, mythic = trait_floors(egg_of_tier("common")), trait_floors(egg_of_tier("mythic"))
        self.assertEqual(set(common), set(TRAITS))
        self.assertEqual(set(common.values()), {10})
        self.assertEqual(mythic["bravery"], 90)
        self.assertEqual(mythic["creativity"], 90)
        self.assertEqual(mythic["patience"], 70)
        for trait in TRAITS:
            self.assertGreater(mythic[trait], common[trait], trait)

    def test_rolled_traits_respect_their_floors(self):
        rng = random.Random(3)
        for _ in range(200):
            egg = roll_egg(rng)
            traits = roll_traits(egg, rng)
            floors = trait_floors(egg)
            self.assertEqual(set(traits), set(TRAITS))
            for trait, value in traits.items():
                self.assertTrue(floors[trait] <= value <= 100, (trait, value, floors[trait]))

    def test_names_avoid_earlier_lives_until_all_are_used(self):
        rng = random.Random(2)
        self.assertEqual(pick_name(rng, set(NAMES[:-1])), NAMES[-1])
        self.assertIn(pick_name(rng, set(NAMES)), NAMES)


if __name__ == "__main__":
    unittest.main()
