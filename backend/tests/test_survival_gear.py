import sqlite3
import unittest

from backend.services.crafting import craft
from backend.survival import storage
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.carrying import valuable
from backend.survival.creatures.gear import gear_orders
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_storage import Home

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
GEAR = PURPOSES["make_gear"]
ARMOR = {"leather_cap": 1, "leather_tunic": 1}


def meadow(blocks=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    return grid


def situation(inventory, grid=None, clock=DAY, **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {"caution": 50}, "last_tick_at": 0.0, "brain": new_brain(0.0)}
    state.update(changes)
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state, grid or meadow(), clock, 100.0, db)


def plan(s):
    return GEAR.plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=s.db))


def crafts(steps):
    return [step["recipe"] for step in steps if step["kind"] == "craft"]


class GearTests(unittest.TestCase):
    def test_leather_armor_is_made_at_a_crafting_table_and_is_worth_carrying(self):
        self.assertEqual(craft({"rabbit_hide": 4}, "leather", set()), {"leather": 1})
        self.assertEqual(craft({"leather": 2}, "leather_cap", {"crafting_table"}), {"leather_cap": 1})
        self.assertEqual(craft({"leather": 3}, "leather_tunic", {"crafting_table"}), {"leather_tunic": 1})
        self.assertTrue(valuable("leather_cap") and valuable("leather_tunic"))

    def test_armor_first_then_a_bow_with_arrows_then_arrows_up_to_eight(self):
        self.assertEqual(gear_orders({"flint": 1}), [("leather_tunic", "leather_cap"), ("leather_tunic",),
                                                     ("leather_cap",), ("bow", "arrow"), ("bow",)])
        self.assertEqual(gear_orders({**ARMOR, "bow": 1, "arrow": 7}), [("arrow",)])
        self.assertEqual(gear_orders({**ARMOR, "bow": 1, "arrow": 8}), [])

    def test_no_bow_before_mimo_has_had_flint_for_its_arrows(self):
        # Final fix wave: before L3 nothing gathers gravel on purpose (flint is 1 in 8 from it), so
        # a bow made first stood unused. It is made once Mimo has flint, has put some away or
        # already carries arrows.
        self.assertEqual(gear_orders({}), [("leather_tunic", "leather_cap"), ("leather_tunic",), ("leather_cap",)])
        self.assertEqual(gear_orders(ARMOR), [])
        self.assertEqual(gear_orders(ARMOR, flint_seen=True), [("bow", "arrow"), ("bow",)])
        self.assertEqual(gear_orders({**ARMOR, "arrow": 2}), [("bow", "arrow"), ("bow",)])
        self.assertFalse(GEAR.valid(situation({**ARMOR, "sticks": 4, "string": 3, "planks": 4})))
        stored = situation({**ARMOR, "sticks": 4, "string": 3, "planks": 4}, chests={"2,1,2": {"flint": 1}})
        self.assertEqual(crafts(plan(stored)), ["crafting_table", "bow"])

    def test_both_pieces_of_armor_from_five_leather_at_a_table_it_places_and_takes_back(self):
        s = situation({"leather": 5, "planks": 4})
        self.assertTrue(GEAR.valid(s))
        self.assertEqual(GEAR.facts(s), "can make a leather tunic and a leather cap now; carrying 0 arrows")
        steps = plan(s)
        self.assertEqual(crafts(steps), ["crafting_table", "leather_tunic", "leather_cap"])
        placed = next(step for step in steps if step["kind"] == "place")
        self.assertEqual((placed["block"], steps[-1]), ("crafting_table", {"kind": "mine", "target": placed["target"],
                                                                           "keep": True}))
        self.assertEqual(crafts(plan(situation({"leather": 3, "planks": 4}))), ["crafting_table", "leather_tunic"])
        hides = situation({"leather": 3, "rabbit_hide": 8, "planks": 4})
        self.assertEqual(crafts(plan(hides)), ["crafting_table", "leather_tunic", "leather", "leather", "leather_cap"])

    def test_a_bow_and_its_first_arrows_then_more_arrows_at_a_table_already_there(self):
        table = meadow({(2, 1, 0): "crafting_table"})
        both = situation({**ARMOR, "sticks": 4, "string": 3, "flint": 1, "feather": 1}, table)
        self.assertEqual(plan(both), [{"kind": "craft", "recipe": "bow"}, {"kind": "craft", "recipe": "arrow"}])
        self.assertEqual(GEAR.facts(both), "can make a bow and 4 arrows now; carrying 0 arrows")
        more = situation({**ARMOR, "bow": 1, "arrow": 4, "sticks": 1, "flint": 1, "feather": 1}, table)
        self.assertEqual(plan(more), [{"kind": "craft", "recipe": "arrow"}])

    def test_nothing_at_night_or_without_the_materials(self):
        self.assertFalse(GEAR.valid(situation({"leather": 5, "planks": 4}, clock=NIGHT)))
        self.assertFalse(GEAR.valid(situation({"leather": 1, "planks": 4})))
        self.assertFalse(GEAR.valid(situation({**ARMOR, "sticks": 4, "string": 2, "planks": 4})))

    def test_it_matters_more_after_a_creature_hurt_mimo(self):
        self.assertEqual(GEAR.score(situation({"leather": 5})), 60.0)
        self.assertEqual(GEAR.score(situation({"leather": 5}, hurt_at=50.0)), 70.0)
        self.assertEqual(GEAR.score(situation({"leather": 5}, hurt_at=100.0 - 3600.0)), 60.0)

    def test_what_gear_takes_is_kept_on_hand_and_the_rest_put_away(self):
        home = Home({"leather": 9, "string": 5, "flint": 4, "feather": 4, "rabbit_hide": 8, "gloom_dust": 2}, chest={})
        self.assertEqual(storage.to_store(home.situation(), home.chest),
                         [("leather", 4), ("gloom_dust", 2), ("string", 2)])

    def test_once_the_gear_is_made_what_it_took_is_put_away_too(self):
        # Final fix wave: the gear materials were kept on hand for good, up to 5 stacks in Mimo's
        # arms after the armor, the bow and the arrows were made.
        made = {**ARMOR, "bow": 1, "arrow": 8}
        home = Home({**made, "leather": 5, "string": 3, "flint": 4, "feather": 4, "rabbit_hide": 8}, chest={})
        self.assertEqual(dict(storage.to_store(home.situation(), home.chest)),
                         {"leather": 5, "string": 3, "flint": 4, "feather": 4, "rabbit_hide": 8})
        short = Home({**ARMOR, "bow": 1, "arrow": 4, "leather": 5, "string": 3, "flint": 4, "feather": 4}, chest={})
        self.assertEqual(dict(storage.to_store(short.situation(), short.chest)), {"leather": 5, "string": 3})

    def test_iron_armor_covers_its_slot_so_the_leather_for_it_is_spare(self):
        """L4a final fix wave, C1: the leather cap and tunic are dropped once iron replaces them, so
        materials_wanted kept wanting leather and hides for good and a pet in iron armor carried them
        in two of its 16 stacks, with nothing left to give way to food."""
        iron = {"iron_cap": 1, "iron_tunic": 1, "bow": 1, "arrow": 8}
        home = Home({**iron, "leather": 3, "rabbit_hide": 4}, chest={})
        self.assertEqual(dict(storage.to_store(home.situation(), home.chest)), {"leather": 3, "rabbit_hide": 4})
        half = Home({"iron_cap": 1, "bow": 1, "arrow": 8, "leather": 3}, chest={})  # the tunic still wants leather
        self.assertEqual(dict(storage.to_store(half.situation(), half.chest)), {})


if __name__ == "__main__":
    unittest.main()
