import sqlite3
import unittest

from backend.services.crafting import craft
from backend.survival import brain, farming, storage  # noqa: F401  (register farm, build_storage and drop_items; and
# brain every other module, as the whole suite has them: making's, the workshop's and the cozy home's KEEPS_MORE and
# LATER keep the clay DropTests reads, and it failed when run alone)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter, supplies
from backend.survival.carrying import stacks
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, finish_structure, know, set_home
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.steps import finish_step, start_step
from backend.survival.structures import start
from backend.survival.vitals import START_VITALS
from backend.survival.wild import thing

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

    def test_w2_a_hungry_pet_with_full_arms_puts_things_away_and_takes_food_before_food_work(self):
        """W2 plan, resolution 23: on the W2 gate a taught pet with 16 full stacks fished and hunted for two days, ate
        its catches raw one at a time, never went to its chests of food, and starved."""
        from backend.survival.carrying import full
        from backend.survival.foraging import hunger_score
        home = Home({**LOOSE, "coal": 14, "string": 3}, chest={"bread": 4, "cooked_beef": 6})
        home.state["vitals"]["hunger"] = 20.0
        s = home.situation()
        self.assertTrue(full(s.inventory))
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        self.assertGreater(PURPOSES["build_storage"].score(s), hunger_score(s, 35.0))  # forage's base; hunt's is 30
        steps = home.plan("build_storage")
        self.assertIn("store", [step["kind"] for step in steps])
        self.assertEqual(steps[-1]["kind"], "take")  # food out, in the room the things put away left
        self.assertIn(steps[-1]["item"], ("bread", "cooked_beef"))
        home.state["vitals"]["hunger"] = 90.0  # not hungry: food work was never the question
        self.assertLessEqual(PURPOSES["build_storage"].score(home.situation()), 70.0)
        from backend.survival.storage import food_first
        stuck = Home({"iron_sword": 1, "iron_pickaxe": 1, "iron_axe": 1, "iron_shovel": 1, "iron_cap": 1, "iron_tunic": 1,
                      "crafting_table": 1, "furnace": 1, "campfire": 1, "wool_cloak": 1, "bucket": 1, "compass": 1,
                      "clock": 1, "shears": 1, "bow": 1, "arrow": 16, "coal": 14},
                     chest={"bread": 4})
        stuck.state["vitals"]["hunger"] = 10.0
        s = stuck.situation()
        self.assertTrue(full(s.inventory))
        # Putting away 6 of 14 coal frees no stack: not the chest all day for that. W2 fix T: the whole stack goes in
        # instead (storage.hungry_room), and the bread comes out in the room it leaves.
        self.assertEqual(storage.to_store_all(s), [((2, 1, 2), "coal", 6)])
        self.assertEqual(storage.hungry_room(s), [((2, 1, 2), "coal", 14)])
        self.assertTrue(food_first(s))
        self.assertEqual([(step["kind"], step["item"]) for step in stuck.plan("build_storage") if "item" in step],
                         [("store", "coal"), ("take", "bread")])

    def test_w2_fix_t_only_food_in_a_chest_puts_the_chest_before_food_work(self):
        """W2 fix T: on the W2 gate an untaught pet whose chest held no food, only the cobblestone its computer wanted
        (storage.TAKES_MORE), scored build_storage as food work, put 14 cobblestone away and took 16 out again for a
        day and a half, and starved."""
        from backend.survival.foraging import hunger_score
        from backend.survival.storage import TAKES_MORE, food_first

        def wants(s):
            return {"cobblestone": 16}
        home = Home({"cobblestone": 30, "iron_sword": 1}, chest={"cobblestone": 16, "dirt": 40})
        home.state["vitals"]["hunger"] = 20.0
        TAKES_MORE.append(wants)
        try:
            s = home.situation()
            self.assertEqual([item for _, item, _ in storage.to_take(s)], ["cobblestone"])  # the machine's, not food
            self.assertFalse(food_first(s))
            self.assertLess(PURPOSES["build_storage"].score(s), hunger_score(s, 35.0))  # forage's base
            home.state["chests"]["2,1,2"]["bread"] = 4
            self.assertTrue(food_first(home.situation()))
        finally:
            TAKES_MORE.remove(wants)

    def test_w2_fix_t_a_hungry_pet_whose_spare_frees_no_stack_puts_a_kept_stack_away(self):
        """W2 fix T: on the W2 gate (and on W1's own, day 119.9) an untaught pet carried 16 stacks its computer kept,
        fished and hunted for two days beside chests with room, left its catch behind and starved."""
        from backend.survival.storage import KEEPS_MORE, food_first, hungry_room

        def for_the_computer(s, item):
            return 16.0 if item == "copper_ore" else 0.0
        arms = {"iron_sword": 1, "iron_pickaxe": 1, "iron_cap": 1, "iron_tunic": 1, "crafting_table": 1, "furnace": 1,
                "bow": 1, "campfire": 1, "coal": 8, "seeds": 8, "sapling": 4, "oak_log": 8, "sticks": 8, "wheat": 6,
                "iron_ore": 3, "copper_ore": 16}  # 16 stacks, all of it kept
        home = Home(arms, chest={})
        home.state["vitals"]["hunger"] = 20.0
        KEEPS_MORE.append(for_the_computer)
        try:
            s = home.situation()
            self.assertEqual(storage.to_store_all(s), [])
            self.assertEqual(hungry_room(s), [((2, 1, 2), "copper_ore", 16)])  # what KEEP keeps least of, whole
            self.assertTrue(food_first(s))
            self.assertTrue(PURPOSES["build_storage"].valid(s))
            self.assertIn(store("copper_ore", 16), home.plan("build_storage"))
            home.state["vitals"]["hunger"] = 60.0  # not hungry: it stays on hand
            self.assertEqual(hungry_room(home.situation()), [])
        finally:
            KEEPS_MORE.remove(for_the_computer)

    def test_the_food_taken_out_is_never_the_spare_food_put_back(self):
        """Carried from W2's sixteenth task: food_first takes food out while Mimo carries less than TAKE_BELOW, and
        spare_food (SPARE_KEEPING's order too) puts away only what is beyond FOOD_WANTED, so no batch takes out what
        the next puts back, as long as TAKE_BELOW stays under FOOD_WANTED."""
        from backend.survival.foraging import FOOD_WANTED
        from backend.survival.storage import TAKE_BELOW, spare_food
        self.assertLess(TAKE_BELOW, FOOD_WANTED)
        self.assertEqual(spare_food(Home({"bread": 2}).situation()), [])  # 50 points carried: none of it spare

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

    def test_food_is_taken_out_only_as_far_as_it_fits(self):
        """The Making final fix wave's room cap on the food take (untested until Making wave 2, the re-review's
        Minor 5): at 15 stacks one stack of food fits, not two."""
        chest = {"bread": 1, "berries": 10}
        home = Home({f"item_{n}": 1 for n in range(14)}, chest=dict(chest))  # 14 stacks: both fit
        self.assertEqual([(item, amount) for _, item, amount in storage.to_take(home.situation())],
                         [("bread", 1), ("berries", 5)])
        home = Home({f"item_{n}": 1 for n in range(15)}, chest=dict(chest))  # 15 stacks
        self.assertEqual([(item, amount) for _, item, amount in storage.to_take(home.situation())], [("bread", 1)])

    def test_a_chest_with_no_path_is_not_retried_until_its_penalty_passes(self):
        # Fix round 2: the repeating "gave up trying to put things away (no way there)" bug -- a
        # step that just failed near home's anchor (1, 1, 1) is not retried at once, the same guard
        # every explore target gets (near_failure).
        home = Home({"cobblestone": 1}, chest={"bread": 4, "berries": 9}, position=(9, 1, 9))
        s = home.situation()
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        home.state["recent_actions"] = [{"target": {"x": 1, "y": 1, "z": 1}, "result": "failed"}]
        self.assertFalse(PURPOSES["build_storage"].valid(home.situation()))
        home.state["recent_actions"] = []  # the failure ages out of the window: worth trying again
        self.assertTrue(PURPOSES["build_storage"].valid(home.situation()))
        # Already at home (no walk needed): an unrelated failure near the anchor does not block it.
        home.state["position"] = {"x": 1.0, "y": 1.0, "z": 1.0}
        home.state["recent_actions"] = [{"target": {"x": 1, "y": 1, "z": 1}, "result": "failed"}]
        self.assertTrue(PURPOSES["build_storage"].valid(home.situation()))

    def test_full_arms_too_far_to_walk_home_in_one_go_do_not_pick_build_storage(self):
        """Follow-up fix, item 1: storage_valid stayed true 100-240 blocks from home (a day trip's
        range) with full arms, but whole_walk(home) always fails once home is more than
        pathing.MAX_RANGE (96) blocks away on either axis -- pathing.route only ever hands back one
        segment there. build_storage was chosen, failed within about a second, and farm was picked
        again: a phantom purpose that never gets Mimo home."""
        far = Home({**LOOSE, "planks": 8}, position=(151, 1, 1))
        self.assertFalse(PURPOSES["build_storage"].valid(far.situation()))
        near = Home({**LOOSE, "planks": 8}, position=(51, 1, 1))
        self.assertTrue(PURPOSES["build_storage"].valid(near.situation()))

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
    def test_w2_fix_t_a_hungry_wild_pet_with_no_chest_sheds_what_a_chest_would_take(self):
        """W2 fix T: on the W2 gate (and on W1's own) an untaught pet with no shelter, so no chest, carried 16 stacks of
        things it keeps, none of which gives way to food, fished for a day and a half, left its catch behind and
        starved."""
        from backend.survival.foraging import hunger_score
        from backend.survival.storage import WINTER_TAKE, junk
        arms = {"iron_sword": 1, "iron_pickaxe": 1, "iron_cap": 1, "iron_tunic": 1, "crafting_table": 1, "furnace": 1,
                "bow": 1, "coal": 8, "seeds": 16, "sapling": 4, "oak_log": 8, "sticks": 3, "wheat": 1, "iron_ore": 1,
                "creature_seed": 3, "copper_ore": 1}  # 16 stacks; the shelter's chest was never placed
        home = Home(arms)
        home.state["difficulty"] = "wild"
        home.state["vitals"]["hunger"] = 20.0
        s = home.situation()
        self.assertEqual(stacks(s.inventory), 16)
        self.assertTrue(PURPOSES["drop_items"].valid(s))
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "copper_ore", "amount": 1},
                                                   {"kind": "drop", "item": "creature_seed", "amount": 3}])
        self.assertGreaterEqual(PURPOSES["drop_items"].score(s), hunger_score(s, WINTER_TAKE))  # before food work
        home.state["vitals"]["hunger"] = 60.0  # not hungry: kept
        self.assertEqual(junk(home.situation()), [])
        home.state["vitals"]["hunger"] = 20.0
        home.state["difficulty"] = "gentle"  # a gentle pet is today's game
        self.assertEqual(junk(home.situation()), [])
        home.state["difficulty"] = "wild"
        home.grid.put(*home.chest, "chest")  # a chest built: it goes there instead
        home.state["chests"] = {"2,1,2": {}}
        self.assertEqual(junk(home.situation()), [])

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
        # The Making final fix wave: the clay stays while the workshop's kiln still wants it (making.saved).
        self.assertEqual([step["item"] for step in home.plan("drop_items")], ["moss", "gravel", "sand"])
        know(home.db, "workshop", "goal", 0.0)  # the workshop and the cozy home reached: nothing will want clay
        know(home.db, "cozy_home", "goal", 0.0)
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

    def test_the_dirt_mimo_keeps_stays(self):
        """Making wave 2, fix round 1 (the re-review's Minor 3): the dirt a started machine's yard is still to be
        filled in with (machines.yard_dirt, a KEEPS_MORE) is never dropped with full arms and a full chest."""
        yard = lambda s, item: 30.0 if item == "dirt" else 0.0  # noqa: E731
        storage.KEEPS_MORE.append(yard)
        self.addCleanup(storage.KEEPS_MORE.remove, yard)
        home = Home({**self.filler, "dirt": 40, "cobblestone": 20}, chest=self.FULL_CHEST)
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "dirt", "amount": 10}])

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


class ClearOutTests(unittest.TestCase):
    """Making wave 2: on the gate's route runs both of each pet's chests were full by day 150, of dirt (up to 128),
    seeds (up to 239) and berries, so nothing could be put away and a making goal's copper had no room."""

    CHEST = {"dirt": 96, "seeds": 60, "gravel": 3, "red_mushroom": 4, **{f"thing_{n}": 32 for n in range(17)}}  # 24

    def test_a_full_chest_is_cleared_of_rubble_and_spare_seeds_to_make_room(self):
        home = Home({"iron_ore": 20, "coal": 20, **{f"item_{n}": 1 for n in range(12)}}, chest=dict(self.CHEST))
        know(home.db, "red_mushroom", "poisonous", 0.0)
        s = home.situation()
        self.assertEqual(stacks(home.state["chests"]["2,1,2"]), 24)
        self.assertEqual(storage.to_store(s, (2, 1, 2)), [])  # no room as it stands...
        self.assertEqual(storage.to_clear(s), [((2, 1, 2), "dirt", 32), ((2, 1, 2), "dirt", 32),
                                               ((2, 1, 2), "gravel", 3), ((2, 1, 2), "red_mushroom", 4)])
        self.assertTrue(PURPOSES["build_storage"].valid(s))  # ...but some once the rubble is out
        steps = home.plan("build_storage")
        self.assertEqual(steps[:2], [{"kind": "take", "target": [2, 1, 2], "item": "dirt", "amount": 32, "away": True},
                                     {"kind": "take", "target": [2, 1, 2], "item": "dirt", "amount": 32, "away": True}])
        self.assertEqual([(step["kind"], step["item"]) for step in steps[4:]],
                         [("store", "coal"), ("store", "iron_ore")])
        # the take step leaves them behind at once: no room in Mimo's arms is needed
        home.state["inventory"].update({f"item_{n}": 1 for n in range(12, 14)})  # 16 stacks
        before = dict(home.state["inventory"])
        step = start_step(steps[0], home.state, home.grid, 0.0, 1.0)
        finish_step(step, home.state, home.grid, 1.0)
        self.assertEqual((home.state["chests"]["2,1,2"]["dirt"], home.state["inventory"]), (64, before))

    def test_a_wild_pet_never_throws_out_the_berries_it_only_shuns(self):
        # W1's final fix wave (11): the shun is "leave alone" for two game days, not "poison to throw away".
        chest = {**self.CHEST, "berries": 4}
        del chest["red_mushroom"]
        home = Home({"iron_ore": 20, "coal": 20, "berries": 6, **{f"item_{n}": 1 for n in range(12)}}, chest=chest)
        know(home.db, thing("berries"), "lesson", 0.0)
        home.state.update(difficulty="wild", wild={"shun": {"red_berries": 0.0}})
        s = home.situation()
        self.assertIn("berries", s.poisons)  # neither picked nor eaten while shunned...
        cleared = [item for _, item, _ in storage.to_clear(s)]
        self.assertEqual(cleared, ["dirt", "dirt", "gravel", "seeds"])  # ...nor cleared out of a full chest...
        self.assertNotIn("berries", [item for item, _ in storage.junk(s)])  # ...nor dropped

    def test_a_chest_with_room_or_nothing_to_put_away_is_left_as_it_is(self):
        home = Home({"iron_ore": 16, **{f"item_{n}": 1 for n in range(12)}}, chest=dict(self.CHEST))
        self.assertEqual(storage.to_clear(home.situation()), [])  # iron is kept: nothing to put away
        roomy = dict(self.CHEST)
        del roomy["thing_0"]
        home = Home({"iron_ore": 20, "coal": 20, **{f"item_{n}": 1 for n in range(12)}}, chest=roomy)
        self.assertEqual(storage.to_clear(home.situation()), [])  # the coal fits as it is


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
