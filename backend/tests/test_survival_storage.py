import sqlite3
import unittest

from backend.services.crafting import craft
from backend.survival import farming, storage  # noqa: F401  (register farm, build_storage and drop_items)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter, supplies
from backend.survival.carrying import stacks
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, finish_structure, know, set_home
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.structures import start
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
LOOSE = {"dirt": 40, "moss": 3, "gravel": 5, "sand": 5, "clay": 2, "basalt": 1, "limestone": 1, "sandstone": 1,
         "copper_ore": 2, "brick": 1, "glass": 1, "cobblestone": 20, "oak_log": 3}  # 14 stacks


def meadow():
    return Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")


class Home:
    """A pet at the door of a finished 3x3 shelter (inside x 0..2, z 0..2, chest corner (2, 1, 2))."""

    def __init__(self, inventory, chest=None, position=(1, 1, 1)):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = meadow()
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in design.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        set_home(self.db, design.anchor, 1.0)  # fix round 1: chest_spot now reads the home place
        self.chest = design.one("chest")
        self.torches = [planned.cell for planned in design.parts("torch")]
        self.state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                      "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        if chest is not None:
            self.grid.put(*self.chest, "chest")
            self.state["chests"] = {"2,1,2": dict(chest)}
        ensure_actions(self.state)

    def situation(self, clock=DAY):
        return Situation(self.state, self.grid, clock, 0.0, self.db)

    def plan(self, name):
        s = self.situation()
        return PURPOSES[name].plan(s, ActionContext(grid=self.grid, clock_at=lambda at: DAY,
                                                    planner=lambda *args: [], events=[], db=self.db))


def store(item, amount):
    return {"kind": "store", "target": [2, 1, 2], "item": item, "amount": amount}


class StorageTests(unittest.TestCase):
    def test_nearly_full_arms_make_a_chest_and_fill_it_with_what_mimo_does_not_need(self):
        home = Home({**LOOSE, "planks": 8})
        self.assertEqual(home.chest, (2, 1, 2))
        self.assertTrue(PURPOSES["build_storage"].valid(home.situation()))
        steps = home.plan("build_storage")
        self.assertEqual(steps[:2], [{"kind": "craft", "recipe": "chest"},
                                     {"kind": "place", "target": [2, 1, 2], "block": "chest"}])
        self.assertEqual(steps[2:6], [store("dirt", 40), store("gravel", 5), store("sand", 5), store("cobblestone", 4)])
        self.assertEqual(len(steps), 2 + 8)

    def test_a_mushroom_in_the_chest_corner_is_mined_first(self):
        home = Home({**LOOSE, "chest": 1})
        home.grid.put(2, 1, 2, "brown_mushroom")
        steps = home.plan("build_storage")
        self.assertEqual(steps[:2], [{"kind": "mine", "target": [2, 1, 2]},
                                     {"kind": "place", "target": [2, 1, 2], "block": "chest"}])

    def test_not_offered_with_room_to_spare_or_without_a_built_shelter(self):
        self.assertFalse(PURPOSES["build_storage"].valid(Home({"dirt": 40, "planks": 8}).situation()))
        self.assertFalse(PURPOSES["build_storage"].valid(Home({**LOOSE, "planks": 8}).situation(NIGHT)))
        home = Home({**LOOSE, "planks": 8})
        home.db.execute("DELETE FROM structures")
        self.assertFalse(PURPOSES["build_storage"].valid(home.situation()))

    def test_it_walks_home_first_and_takes_food_out_when_mimo_carries_little(self):
        home = Home({"cobblestone": 1}, chest={"bread": 4, "berries": 9}, position=(9, 1, 9))
        s = home.situation()
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        self.assertEqual(PURPOSES["build_storage"].score(s), 55.0)
        self.assertEqual(home.plan("build_storage"), [
            {"kind": "walk", "target": [1, 1, 1], "reach": 0.0, "whole": True},
            {"kind": "take", "target": [2, 1, 2], "item": "bread", "amount": 3}])

    def test_more_food_than_a_days_worth_goes_in_the_chest(self):
        home = Home({**LOOSE, "bread": 4, "berries": 10}, chest={})
        steps = home.plan("build_storage")
        self.assertIn(store("berries", 10), steps)
        self.assertNotIn("bread", [step.get("item") for step in steps])

    def test_with_full_arms_even_the_kept_building_blocks_go_in(self):
        """Fix wave I2(b): 16 cobblestone and 16 planks are what Mimo keeps on it, but when its arms
        are full they go into the chest whole."""
        filler = {f"item_{n}": 1 for n in range(14)}
        home = Home({**filler, "cobblestone": 16, "planks": 16}, chest={})  # 16 stacks
        self.assertTrue(PURPOSES["build_storage"].valid(home.situation()))
        self.assertEqual(home.plan("build_storage"), [store("cobblestone", 16), store("planks", 16)])
        roomy = Home({**filler, "cobblestone": 16, "planks": 16, "item_13": 0}, chest={})
        roomy.state["inventory"].pop("item_13")  # 15 stacks: they stay with Mimo
        self.assertFalse(PURPOSES["build_storage"].valid(roomy.situation()))

    def test_a_chest_that_would_not_fit_drops_a_low_value_stack_to_make_room(self):
        """Follow-up fix, item 2: making the chest from 20 planks at 16 stacks leaves 12 planks and
        a chest, 17 stacks, which would not fit. Fix wave I1 left build_storage not offered for it;
        now the plan drops one LOW_VALUE stack first (moss, the first LOOSE has) to clear the room,
        the same order carrying.settle pushes blocks out in."""
        home = Home({**LOOSE, "planks": 20, "seeds": 1})  # 16 stacks
        s = home.situation()
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        steps = home.plan("build_storage")
        self.assertEqual(steps[:3], [{"kind": "drop", "item": "moss", "amount": 3},
                                     {"kind": "craft", "recipe": "chest"},
                                     {"kind": "place", "target": [2, 1, 2], "block": "chest"}])
        self.assertTrue(PURPOSES["build_storage"].valid(Home({**LOOSE, "planks": 8, "seeds": 1}).situation()))

    def test_no_room_for_a_chest_is_the_reviewers_repro(self):
        """Follow-up fix, item 2: the 21-Jev pet at game day 0.106 had 16 stacks -- 2 planks, 8
        birch logs and 6 cobblestone among them -- and could not craft a chest: the planks it would
        make needed their own stack, nothing counted as junk so drop_items was never offered, and
        L3's cobblestone floor (work.STONE_GOAL) had removed the old way out of dropping stone. A
        dead end no purpose choice could get out of. Dropping the cobblestone it carries (chest_
        crafting's own one-time room-making, not drop_items' STONE_GOAL floor) gets it a chest."""
        base = {"apple": 1, "brown_mushroom": 3, "campfire": 1, "coal": 1, "cobblestone": 6, "cooked_beef": 2,
                "cooked_chicken": 1, "crafting_table": 1, "feather": 1, "planks": 2, "red_mushroom": 1,
                "sapling": 6, "sticks": 2, "wooden_pickaxe": 1, "wooden_sword": 1}
        home = Home({**base, "birch_log": 8})  # 16 stacks
        s = home.situation()
        self.assertEqual(stacks(s.inventory), 16)
        self.assertIsNone(storage.made(dict(s.inventory), "chest"))
        self.assertEqual(storage.junk(s), [])
        self.assertFalse(PURPOSES["drop_items"].valid(s))
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        self.assertEqual(home.plan("build_storage")[:2],
                         [{"kind": "drop", "item": "cobblestone", "amount": 6},
                          {"kind": "craft", "recipe": "birch_planks"}])

    def test_the_fuller_mimo_is_the_more_it_wants_to_tidy(self):
        score = PURPOSES["build_storage"].score
        self.assertEqual(score(Home({**LOOSE, "planks": 8}).situation()), 60.0)  # 15 stacks
        home = Home({**LOOSE, "planks": 8, "seeds": 9})  # 16 stacks, and something had to stay behind
        home.state["full_at"] = 5.0
        self.assertEqual(score(home.situation()), 70.0)

    def test_logs_and_planks_are_kept_as_one_pool_of_any_wood(self):
        """L3 final fix wave: KEEP held 8 logs and 16 planks of each wood, so a pet with oak and birch
        carried two log stacks for good and sat at 15-16 of 16 stacks. Mimo now keeps 8 logs and 16
        planks in all, of the wood it holds most (oak first on a tie, then birch, then spruce), and
        the rest goes in the chest."""
        home = Home({"birch_log": 8, "oak_log": 1, "planks": 10, "birch_planks": 10}, chest={})
        s = home.situation()
        self.assertEqual([storage.kept(s, item) for item in ("birch_log", "oak_log", "planks", "birch_planks")],
                         [8, 0, 10, 6])
        self.assertEqual(sorted(storage.to_store(s, home.chest)), [("birch_planks", 4), ("oak_log", 1)])
        mixed = Home({"oak_log": 3, "spruce_log": 7, "birch_log": 2}, chest={}).situation()
        self.assertEqual([storage.kept(mixed, item) for item in ("spruce_log", "oak_log", "birch_log")], [7, 1, 0])
        oak = Home({"oak_log": 12, "planks": 20}, chest={}).situation()  # one wood: the same as before
        self.assertEqual([storage.kept(oak, "oak_log"), storage.kept(oak, "planks")], [8, 16])

    def test_what_the_pool_keeps_still_crafts_and_builds(self):
        """L3 final fix wave: the pool can leave Mimo birch or spruce and no oak. Recipes that name
        oak take any wood (crafting.STAND_INS and paid), and a shelter takes any planks and logs
        (blueprints.supplies)."""
        home = Home({"birch_log": 11, "oak_log": 3, "spruce_planks": 20, "planks": 4, "sticks": 4}, chest={})
        s = home.situation()
        kept = {item: min(count, storage.kept(s, item)) for item, count in s.inventory.items()}
        self.assertEqual(kept, {"birch_log": 8, "oak_log": 0, "spruce_planks": 16, "planks": 0, "sticks": 4})
        kept = {item: count for item, count in kept.items() if count}
        tables = {"crafting_table"}
        for recipe in ("birch_planks", "sticks", "crafting_table", "chest", "fence", "campfire", "wooden_pickaxe"):
            self.assertIsInstance(craft(dict(kept), recipe, tables), dict, recipe)
        self.assertEqual(supplies(kept), {"spruce_planks": 16, "birch_planks": 24})

    def test_torch_keep_matches_the_shelters_own_dark_corners(self):
        """L3 fix round 1, item 1: KEEP held a flat 4 torches, so once light_up lit every corner a
        spare torch stayed in Mimo's arms instead of going in the chest (the root cause of the
        failing hunt test). It now keeps only as many torches as dark corners are left, and a
        carried lantern -- which fills a corner just as well -- counts against that too."""
        lit = Home({"torch": 1}, chest={})
        for cell in lit.torches:  # every corner lit
            lit.grid.put(*cell, "torch")
        s = lit.situation()
        self.assertEqual(storage.kept(s, "torch"), 0)
        self.assertIn(("torch", 1), storage.to_store(s, lit.chest))

        half_lit = Home({"torch": 5}, chest={})
        for cell in half_lit.torches[:2]:  # 2 of 4 corners lit, 2 still dark
            half_lit.grid.put(*cell, "torch")
        self.assertEqual(storage.kept(half_lit.situation(), "torch"), 2)

        with_lantern = Home({"torch": 5, "lantern": 1})  # every corner dark, but a lantern fills one first
        self.assertEqual(storage.kept(with_lantern.situation(), "torch"), 3)


class DropTests(unittest.TestCase):
    def test_known_poison_old_pickaxes_and_flowers_are_dropped(self):
        home = Home({"dirt": 40, "cobblestone": 20, "oak_log": 3, "planks": 5, "seeds": 3, "sticks": 2,
                     "red_mushroom": 3, "wooden_pickaxe": 1, "stone_pickaxe": 1, "flower_pink": 2})  # 11 stacks
        self.assertFalse(PURPOSES["drop_items"].valid(Home({"dirt": 1, "wooden_pickaxe": 1, "stone_pickaxe": 1}).situation()))
        know(home.db, "red_mushroom", "poisonous", 0.0)
        s = home.situation()
        self.assertTrue(PURPOSES["drop_items"].valid(s))
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "red_mushroom", "amount": 3},
                                                   {"kind": "drop", "item": "wooden_pickaxe", "amount": 1},
                                                   {"kind": "drop", "item": "flower_pink", "amount": 2}])
        self.assertEqual(PURPOSES["drop_items"].score(s), 38.0)

    def test_full_with_no_chest_the_least_useful_blocks_go_too(self):
        full = {**LOOSE, "seeds": 1, "wheat": 1}
        home = Home(full)
        self.assertEqual([step["item"] for step in home.plan("drop_items")], ["moss", "gravel", "sand", "clay"])
        with_chest = Home(full, chest={})
        self.assertFalse(PURPOSES["drop_items"].valid(with_chest.situation()))

    def test_a_spare_torch_is_dropped_without_waiting_for_a_chest(self):
        """L3 fix round 1: spare_torches lets drop_items shed a torch home's own dark corners no
        longer need directly, the same 'spare' pattern as spare_fences, instead of it sitting in
        Mimo's arms until build_storage next has a reason to walk home."""
        home = Home({**LOOSE, "torch": 2})  # 15 stacks; every corner lit, so both torches are spare
        for cell in home.torches:
            home.grid.put(*cell, "torch")
        s = home.situation()
        self.assertIn(("torch", 2), storage.junk(s))
        self.assertTrue(PURPOSES["drop_items"].valid(s))
        self.assertIn({"kind": "drop", "item": "torch", "amount": 2}, home.plan("drop_items"))


class DropWhenStuckTests(unittest.TestCase):
    """Fix wave I2(c): full, with no chest or a full one, Mimo drops dirt, and with no dirt,
    cobblestone, keeping what a started shelter still needs."""

    filler = {f"item_{n}": 1 for n in range(13)}
    FULL_CHEST = {f"thing_{n}": 32 for n in range(24)}

    def test_dirt_goes_with_no_chest_or_a_full_one(self):
        for chest in (None, self.FULL_CHEST):
            home = Home({**self.filler, "dirt": 40, "cobblestone": 20}, chest=chest)  # 16 stacks
            self.assertTrue(PURPOSES["drop_items"].valid(home.situation()), chest)
            self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "dirt", "amount": 40}])
        roomy = Home({**self.filler, "dirt": 40, "cobblestone": 20}, chest={})
        self.assertFalse(PURPOSES["drop_items"].valid(roomy.situation()))

    def test_with_no_dirt_cobblestone_goes_but_what_the_shelter_still_needs_stays(self):
        """Fix wave M5(f): cobblestone never drops below gather_stone's own goal (STONE_GOAL, 12),
        so drop_items and gather_stone stop alternating over the same stone."""
        carried = {**self.filler, "item_13": 1, "cobblestone": 40}  # 16 stacks
        self.assertEqual(Home(carried).plan("drop_items"), [{"kind": "drop", "item": "cobblestone", "amount": 28}])
        home = Home(carried)
        for cell in [(-1, 1, 0), (-1, 2, 0), (3, 1, 0), (3, 2, 0), (3, 1, 1)]:  # five wall blocks gone
            home.grid.put(*cell, "air")
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "cobblestone", "amount": 23}])
        dirt = Home({**self.filler, "item_13": 1, "dirt": 40})
        for cell in [(-1, 1, 0), (-1, 2, 0), (3, 1, 0)]:
            dirt.grid.put(*cell, "air")
        self.assertEqual(dirt.plan("drop_items"), [{"kind": "drop", "item": "dirt", "amount": 37}])


class CarriedChestTests(unittest.TestCase):
    """Fix wave M5(g): an unplaced chest Mimo carries still means build_storage can put it down and
    store what would otherwise be dropped, so drop_items leaves the shelter's dirt and cobblestone
    alone instead of throwing it away."""

    filler = {f"item_{n}": 1 for n in range(13)}

    def test_a_carried_chest_stores_instead_of_dropping_cobblestone(self):
        home = Home({**self.filler, "cobblestone": 40, "chest": 1})  # 16 stacks, chest not yet placed
        s = home.situation()
        self.assertTrue(storage.storage_valid(s))
        self.assertFalse(PURPOSES["drop_items"].valid(s))
        self.assertEqual(home.plan("drop_items"), [])
        # the same cobblestone is dropped as before when Mimo carries no chest to place
        without_chest = Home({**self.filler, "item_13": 1, "cobblestone": 40})
        self.assertEqual(without_chest.plan("drop_items"), [{"kind": "drop", "item": "cobblestone", "amount": 28}])


class FarmHarvestTests(unittest.TestCase):
    def test_ripe_crops_wait_in_the_field_while_mimo_carries_a_days_food(self):
        grid = meadow()
        grid.put(3, 0, 0, "farmland")
        grid.put(3, 1, 0, "wheat_3")
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)

        def situation(inventory):
            state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                     "inventory": inventory, "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
            ensure_actions(state)
            return Situation(state, grid, DAY, 0.0, db)

        context = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=db)
        hungry = PURPOSES["farm"].plan(situation({}), context)
        self.assertIn({"kind": "harvest", "target": [3, 1, 0]}, hungry)
        self.assertFalse(PURPOSES["farm"].valid(situation({"bread": 3})))


if __name__ == "__main__":
    unittest.main()
