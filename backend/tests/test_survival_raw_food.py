import unittest

from backend.survival import storage
from backend.tests.test_survival_storage import Home


class RawFoodTests(unittest.TestCase):
    def test_raw_meat_and_fish_wait_for_the_fire_instead_of_the_chest(self):
        home = Home({"berries": 40, "raw_rabbit": 2, "raw_fish": 3})
        s = home.situation()
        spare = dict(storage.spare_food(s))
        self.assertIn("berries", spare)
        self.assertNotIn("raw_rabbit", spare)
        self.assertNotIn("raw_fish", spare)
        self.assertNotIn("raw_rabbit", dict(storage.to_store(s, home.chest)))


if __name__ == "__main__":
    unittest.main()
