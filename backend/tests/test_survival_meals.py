"""W1: what a wild pet eats: untried foods, the red berries it cannot tell apart, poison and raw meals."""

import unittest
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose registered)
from backend.survival.ailments import sickness
from backend.survival.carrying import eat_what_is_left
from backend.survival.meals import RAW_RISK, wild_meal
from backend.survival.memory import know
from backend.survival.purposes import PURPOSES, is_valid, meal_of
from backend.survival.reflexes import by_name
from backend.survival.senses import food_near
from backend.survival.steps import finish_step, start_step
from backend.survival.wild import SHUN, thing
from backend.tests.test_survival_cooking import meadow, situation

WILD = {"difficulty": "wild"}


def wild(inventory, hunger=100.0, *lessons, grid=None):
    s = situation(dict(inventory), grid, hunger)
    s.state.update(WILD)
    for name in lessons:
        know(s.db, thing(name), "lesson", 0.0)
    return s


def eat(s, item, **step):
    running = start_step({"kind": "eat", "item": item, **step}, s.state, s.grid, 0.0)
    return finish_step(running, s.state, s.grid, 1.6)  # the running step carries the meal's risk


def items(steps):
    return [step["item"] for step in steps]


class UntriedTests(unittest.TestCase):
    def test_red_berries_are_tasted_one_at_a_time_only_when_hungry_with_nothing_else(self):
        self.assertEqual(wild_meal(wild({"berries": 6}, 60.0)), [])
        self.assertEqual(items(wild_meal(wild({"berries": 6}, 45.0))), ["berries"])
        self.assertEqual(items(wild_meal(wild({"berries": 6, "raw_beef": 1}, 45.0))), ["raw_beef"])
        self.assertEqual(items(wild_meal(wild({"red_mushroom": 2}, 45.0))), ["red_mushroom"])

    def test_starving_it_tastes_at_once_through_eat_now(self):
        s = wild({"berries": 6, "raw_beef": 1}, 10.0)
        eat_now = by_name("eat_now")
        self.assertTrue(eat_now.trigger(s))
        self.assertEqual(items(eat_now.plan(s, None)), ["raw_beef", "berries"])

    def test_once_it_knows_berries_it_eats_them_and_eat_is_on_offer(self):
        self.assertFalse(is_valid(PURPOSES["eat"], wild({"berries": 6}, 60.0)))
        s = wild({"berries": 6}, 60.0, "berries")
        self.assertTrue(is_valid(PURPOSES["eat"], s))
        self.assertEqual(items(meal_of(s)), ["berries"] * 4)

    def test_sunleaf_is_never_a_meal(self):
        self.assertEqual(wild_meal(wild({"sunleaf": 2}, 10.0, "sunleaf")), [])


class LookalikeTests(unittest.TestCase):
    def test_an_untaught_meal_of_red_berries_eats_nightberries_at_their_share(self):
        eaten = []
        for at in range(200):
            s = wild({"berries": 30, "nightberries": 20}, 20.0, "berries")
            s.at = float(at * 97)
            eaten += items(wild_meal(s))
        share = eaten.count("nightberries") / len(eaten)
        self.assertTrue(0.3 < share < 0.5, share)

    def test_a_taught_pet_never_picks_eats_or_keeps_a_nightberry(self):
        grid = meadow({(2, 1, 0): "nightberry_bush_ripe", (3, 1, 0): "berry_bush_ripe"})
        untaught = wild({}, 60.0, grid=grid)
        self.assertEqual(food_near(grid, "1", (0, 1, 0), 8, untaught.poisons), [(2, 1, 0), (3, 1, 0)])
        taught = wild({"nightberries": 3, "berries": 3}, 60.0, "berries", "nightberries", grid=grid)
        self.assertEqual(food_near(grid, "1", (0, 1, 0), 8, taught.poisons), [(3, 1, 0)])
        self.assertEqual(items(meal_of(taught)), ["berries"] * 3)
        self.assertTrue(is_valid(PURPOSES["throw_out"], taught))
        self.assertEqual(PURPOSES["throw_out"].plan(taught, None), [{"kind": "drop", "item": "nightberries", "amount": 3}])

    def test_a_sickness_from_the_group_ends_the_meal_and_shuns_it_two_game_days(self):
        s = wild({"nightberries": 3, "berries": 1, "apple": 1}, 60.0, "berries")
        s.state["queue"] = [{"kind": "eat", "item": "berries"}, {"kind": "eat", "item": "nightberries"},
                            {"kind": "eat", "item": "apple"}]
        self.assertEqual(eat(s, "nightberries")[0], "sick")
        self.assertEqual(s.state["queue"], [{"kind": "eat", "item": "apple"}])  # the rest of the berries left uneaten
        self.assertEqual(s.state["last_thought"], "Berries made me sick. I'll leave them alone for a while.")
        later = wild({"berries": 3}, 60.0, "berries")
        later.state["wild"] = s.state["wild"]
        later.at = 1.0
        self.assertIn("berry_bush_ripe", later.poisons)
        self.assertEqual(meal_of(later), [])
        after = wild({"berries": 3}, 60.0, "berries")
        after.state["wild"] = s.state["wild"]
        after.at = SHUN + 2.0
        self.assertNotIn("berry_bush_ripe", after.poisons)


class NamingTests(unittest.TestCase):
    def test_a_nightberry_eaten_as_a_red_berry_is_named_red_berries(self):
        # Carried item 10: a pet that does not know nightberries names what it cannot tell apart as it sees it.
        s = wild({"nightberries": 3}, 40.0)
        [step] = wild_meal(s)
        self.assertEqual(step, {"kind": "eat", "item": "nightberries", "seen_as": "red berries"})
        running = start_step(step, s.state, s.grid, 0.0)
        self.assertEqual(finish_step(running, s.state, s.grid, 1.6), ("sick", "Pip ate red berries and felt sick."))


class EatingTests(unittest.TestCase):
    def test_a_poison_plant_takes_five_health_and_gives_a_tummy_ache(self):
        for item in ("nightberries", "red_mushroom"):
            s = wild({item: 1})
            self.assertEqual(eat(s, item), ("sick", f"Pip ate {item.replace('_', ' ')} and felt sick."))
            self.assertEqual((s.state["vitals"]["health"], sickness(s.state)["kind"]), (95.0, "tummy"))
            self.assertEqual(s.state["wild"]["lost"], 5.0)

    def test_a_raw_meal_rolls_once_at_the_highest_chance_of_its_raw_items(self):
        steps = wild_meal(wild({"raw_chicken": 1, "raw_fish": 2, "raw_beef": 1}, 20.0))
        self.assertEqual([step.get("risk") for step in steps], [0.5, None, None, None])
        s = wild({"raw_chicken": 1})
        with patch("backend.survival.meals.roll", return_value=0.45):
            self.assertEqual(eat(s, "raw_chicken", risk=0.5)[0], "sick")
        s = wild({"raw_chicken": 1})
        with patch("backend.survival.meals.roll", return_value=0.55):
            self.assertEqual(eat(s, "raw_chicken", risk=0.5)[0], "ate")
        self.assertIsNone(sickness(s.state))

    def test_a_pet_taught_cooking_leaves_raw_food_for_the_fire_only_when_it_can_cook_now(self):
        # The final fix wave (5): a true, partial answer (cooking without fire) never costs more than none
        # (spec resolution 6): with no way to cook, the raw beef is eaten with its risk, as an untaught pet eats it.
        steps = wild_meal(wild({"raw_beef": 2}, 40.0, "cooking"))
        self.assertEqual((items(steps), steps[0]["risk"]), (["raw_beef", "raw_beef"], RAW_RISK["raw_beef"]))
        fuel = wild({"raw_beef": 2, "oak_log": 2, "sticks": 3}, 40.0, "cooking", "fire")
        self.assertEqual(wild_meal(fuel), [])  # it can make a campfire: it cooks
        self.assertIn({"kind": "cook", "item": "raw_beef"}, PURPOSES["cook"].plan(fuel, None))
        lit = wild({"raw_beef": 2}, 40.0, "cooking", "fire", grid=meadow({(1, 1, 0): "campfire"}))
        self.assertEqual(wild_meal(lit), [])  # a campfire burns beside it
        starving = wild({"raw_beef": 2}, 10.0, "cooking", "fire", grid=meadow({(1, 1, 0): "campfire"}))
        self.assertEqual(items(wild_meal(starving)), ["raw_beef", "raw_beef"])

    def test_food_left_over_is_eaten_only_when_it_carries_no_risk_or_mimo_is_starving(self):
        state = {"name": "Pip", "vitals": {"hunger": 20.0}, **WILD}
        left = {"raw_beef": 2, "bread": 1}
        eat_what_is_left(state, left, 0.0, [])
        self.assertEqual(left, {"raw_beef": 2})
        # starving with full arms, the meat it hunts and cannot carry is eaten raw, and may make it sick
        starving = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                    "vitals": {"hunger": 5.0, "health": 100.0}, **WILD}
        left, events = {"raw_mutton": 3}, []
        with patch("backend.survival.meals.roll", return_value=0.3):
            eat_what_is_left(starving, left, 0.0, events)
        self.assertEqual((starving["vitals"]["hunger"], left), (29.0, {}))
        self.assertEqual(events, [(0.0, "ate", "Pip ate 3 raw mutton it had no room to carry."),
                                  (0.0, "sick", "Pip ate raw mutton and felt sick.")])
        self.assertEqual(sickness(starving)["kind"], "tummy")

    def test_a_starving_wild_pet_eats_raw_chicken_left_over_too(self):
        # Fix round A, Task 6: carrying.keeps_alive is gated on steps.FOOD_RISK, the old gentle rules'
        # own gamble food (raw chicken only), so a wild pet's raw chicken never passed it and was left
        # behind starving. A wild pet judges leftover food by its own rules (meals.RAW_RISK) instead.
        starving = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                    "vitals": {"hunger": 5.0, "health": 100.0}, **WILD}
        left, events = {"raw_chicken": 3}, []
        with patch("backend.survival.meals.roll", return_value=0.3):
            eat_what_is_left(starving, left, 0.0, events)
        self.assertEqual((starving["vitals"]["hunger"], left), (23.0, {}))
        self.assertEqual(events, [(0.0, "ate", "Pip ate 3 raw chicken it had no room to carry."),
                                  (0.0, "sick", "Pip ate raw chicken and felt sick.")])
        self.assertEqual(sickness(starving)["kind"], "tummy")


class GentleTests(unittest.TestCase):
    def test_a_gentle_pet_eats_as_ever_and_only_avoids_nightberries(self):
        s = situation({"berries": 3, "red_mushroom": 2}, None, 40.0)
        self.assertIsNone(wild_meal(s))
        self.assertEqual(items(meal_of(s)), ["berries", "berries", "berries", "red_mushroom"])
        self.assertEqual(s.poisons, ("nightberries", "nightberry_bush_ripe"))
        s.state["inventory"] = {"red_mushroom": 1}
        self.assertEqual(eat(s, "red_mushroom"), ("sick", "Pip ate red mushroom and felt sick."))
        self.assertEqual(s.state["vitals"]["health"], 90.0)  # today's rule
        self.assertIsNone(sickness(s.state))


if __name__ == "__main__":
    unittest.main()
