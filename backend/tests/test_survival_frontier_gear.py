import math
import sqlite3
import unittest

from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, TILES
from backend.services.crafting import RECIPES, craft
from backend.survival import brain  # noqa: F401  (registers the warding lantern, amber armor and ward_home)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.carrying import valuable
from backend.survival.creatures.gear import gear_wanted
from backend.survival.creatures.harm import armor_cut, armor_iron, worn
from backend.survival.creatures.hostiles import chase
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.moves import where
from backend.survival.frontier_gear import WARD_DUST, WARD_REACH, frontier_orders, note_wards
from backend.survival import storage
from backend.survival.goals import GOALS, meets_need
from backend.survival.journal import LESSONS
from backend.survival.grid import Grid
from backend.survival.lessons import claims
from backend.survival.light import Lights
from backend.survival.lighting import dark_corners
from backend.survival.memory import create_memory_tables, finish_structure, set_home
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.steps import finish_step, start_step
from backend.survival.storage import KEEP
from backend.survival.structures import start
from backend.survival.toolmaking import tool_choice, tool_orders
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_darkness import land, pet, scene
from backend.tests.test_survival_lighting import CORNERS, DAY
from backend.tests.test_survival_storage import Home


def chased(wards):
    """Where a gloomling 9 blocks east of Mimo stands after chasing it for a minute, with warding lanterns
    Mimo hung at `wards`."""
    grid = land({cell: "warding_lantern" for cell in wards})
    state = pet()
    state.update(name="Pip", position={"x": 0.0, "y": 1.0, "z": 1.0}, wards=[list(cell) for cell in wards])
    creature = grid.herd.add("gloomling", (9, 1, 1), 20.0, 0.0, 0.0, {"home": [9, 1, 1], "turn": 0})
    for turn in range(20):
        creature = grid.herd.get(creature["id"])
        at = 100.0 + turn * 3.0
        chase(creature, KINDS["gloomling"], scene(grid, state, at=at))
        grid.herd.save(creature)
    return where(grid.herd.get(creature["id"]), 200.0)


class WardTests(unittest.TestCase):
    def test_a_lantern_and_two_gloom_dust_make_a_warding_lantern_that_shines_like_a_lantern(self):
        # The L5 final fix wave, M2 (the controller's ruling): two gloom dust, not four. Gloomlings come out at
        # night, while Mimo is indoors or dug in, and no pet on the final review's gate ever held four at once.
        self.assertEqual(WARD_DUST, 2)
        self.assertEqual(craft({"lantern": 1, "gloom_dust": 2}, "warding_lantern", set()), {"warding_lantern": 1})
        grid = land({(0, 1, 5): "warding_lantern"})
        self.assertEqual(Lights(grid, (0, 1, 0), 16.0).at((0, 1, 5)), 15)
        self.assertTrue(valuable("warding_lantern"))

    def test_a_pet_with_two_gloom_dust_and_a_lantern_orders_one_and_makes_it(self):
        self.assertIn(("warding_lantern",), tool_orders({"iron_pickaxe": 1, "lantern": 1, "gloom_dust": 2}))
        state, grid = meadow_pet({"iron_pickaxe": 1, "stone_sword": 1, "lantern": 1, "gloom_dust": 2})
        tools, steps = tool_choice(Situation(state, grid, DAY, 0.0))
        self.assertEqual((tools, named(steps)), (("warding_lantern",), [("craft", "warding_lantern")]))
        run_steps(state, grid, steps)
        self.assertEqual((state["inventory"].get("warding_lantern"), state["inventory"].get("gloom_dust")), (1, None))

    def test_no_hostile_steps_within_six_blocks_of_one(self):
        self.assertLess(math.dist(chased([]), (0, 1, 1)), 2.0)  # without one it walks right up to Mimo
        stopped = chased([(0, 1, 0)])
        self.assertGreater(math.dist(stopped, (0, 1, 0)), WARD_REACH)

    def test_the_warding_lantern_is_the_last_block_after_makings_wiring(self):
        # Pre-flight (eda93d4): Making's blocks followed L3's after this plan was written, so L5's one
        # block goes after Making's last (the bell), and no older id moves.
        names = [block["name"] for block in BLOCK_LIST]
        self.assertEqual(names[-4], "warding_lantern")  # W1's three plants come after it (test_worldgen_wild)
        self.assertEqual(BLOCK_IDS["warding_lantern"], BLOCK_IDS["bell"] + 1)
        self.assertIn(BLOCK_LIST[BLOCK_IDS["warding_lantern"]]["textures"], TILES)
        self.assertLess(len(BLOCK_LIST), 255)

    def test_mimo_keeps_the_cells_of_the_wards_it_hangs_and_takes_down(self):
        state = {}
        note_wards(state, {"kind": "place", "block": "warding_lantern", "target": {"x": 1, "y": 2, "z": 3}}, None, 1.0)
        note_wards(state, {"kind": "place", "block": "torch", "target": {"x": 4, "y": 2, "z": 3}}, None, 1.0)
        self.assertEqual(state["wards"], [[1, 2, 3]])
        note_wards(state, {"kind": "mine", "block": "warding_lantern", "target": {"x": 1, "y": 2, "z": 3}}, None, 2.0)
        self.assertEqual(state["wards"], [])


class AmberTests(unittest.TestCase):
    def test_amber_studded_armor_is_a_step_past_iron(self):
        self.assertEqual(RECIPES["amber_cap"]["ingredients"], {"iron_ingot": 2, "amber": 2})
        self.assertAlmostEqual(armor_cut({"iron_cap": 1, "iron_tunic": 1}), 0.45)
        self.assertAlmostEqual(armor_cut({"iron_cap": 1, "iron_tunic": 1, "amber_cap": 1, "amber_tunic": 1}), 0.60)

    def test_craft_tools_studs_a_slot_mimo_wears_iron_on_once_it_carries_the_amber(self):
        self.assertEqual(frontier_orders({"iron_tunic": 1, "amber": 3}), [("amber_tunic",)])
        self.assertEqual(frontier_orders({"iron_tunic": 1, "iron_cap": 1, "amber": 2}), [("amber_cap",)])
        self.assertEqual(frontier_orders({"amber": 5}), [])  # no iron to stud
        self.assertIn(("amber_tunic",), tool_orders({"iron_pickaxe": 1, "iron_tunic": 1, "amber": 3}))
        self.assertIn(("warding_lantern",), tool_orders({"iron_pickaxe": 1, "lantern": 1, "gloom_dust": WARD_DUST}))

    def test_lantern_orders_counts_an_amber_piece_as_its_iron_one(self):
        # m4 (I3h): lantern_orders' own "done" check (worn on both iron pieces) already reads harm.worn,
        # which lets an amber piece stand for its iron one (I3) -- but nothing pinned it: a pet that
        # replaced both pieces with amber ones still gets the offer to make lanterns from spare iron.
        self.assertIn(("lantern",), tool_orders({"amber_cap": 1, "amber_tunic": 1, "iron_ingot": 1}))
        self.assertNotIn(("lantern",), tool_orders({"amber_cap": 1, "iron_ingot": 1}))  # only one slot covered

    def test_the_owner_can_teach_the_new_loot(self):
        # Pre-flight (carry 6): Mind's recipe lessons cover the amber pieces (they are armor), and the warding
        # lantern and gold nuggets get one of their own; each is written from the recipe, so it is true.
        self.assertEqual(LESSONS["recipe:amber_cap"].fact, "An amber cap takes two iron ingots and two amber, at a crafting table.")
        self.assertEqual(LESSONS["recipe:warding_lantern"].fact, "A warding lantern takes a lantern and two gloom dust.")
        self.assertEqual(LESSONS["recipe:gold_nuggets"].fact, "Four gold nuggets make a gold ingot.")
        for line, lesson in (("a warding lantern takes gloom dust and a lantern", "recipe:warding_lantern"),
                             ("gold nuggets make a gold ingot", "recipe:gold_nuggets"),
                             ("amber armor takes amber and iron ingots", "recipe:amber_tunic")):
            self.assertIn(lesson, claims(line).taught, line)


def meadow_pet(inventory):
    """Mimo on open grass at (1, 1, 1) with no station placed near it (seed "1": y 1 stands on the surface)."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 1.0, "y": 1.0, "z": 1.0},
             "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    return state, grid


def run_steps(state, grid, steps):
    """Run `steps` in turn, each started and finished at once, as the engine would; a step that cannot run raises."""
    for number, spec in enumerate(steps):
        finish_step(start_step(spec, state, grid, float(number)), state, grid, number + 0.5)


def named(steps):
    return [(step["kind"], step.get("block") or step.get("recipe") or step.get("item")) for step in steps]


class FurnaceTests(unittest.TestCase):
    """The L5 final fix wave, I1: an order whose ingots must be smelted from ore brings its own furnace. The amber
    pieces named only a crafting table and the warding lantern nothing, so their plans smelted with no furnace
    placed: the step failed ("A placed furnace is required") and craft_tools was chosen again, 432 times for one
    pet over 75 game days (the final review's gate, seed 8)."""

    def test_an_amber_cap_from_iron_ore_places_a_furnace_before_it_smelts_and_is_made(self):
        state, grid = meadow_pet({"iron_pickaxe": 1, "stone_sword": 1, "iron_cap": 1, "amber": 2, "iron_ore": 3,
                                  "coal": 3, "crafting_table": 1, "cobblestone": 16})
        tools, steps = tool_choice(Situation(state, grid, DAY, 0.0))
        self.assertEqual(tools, ("amber_cap",))
        kinds = named(steps)
        self.assertLess(kinds.index(("place", "furnace")), kinds.index(("smelt", "iron_ore")))
        run_steps(state, grid, steps)
        self.assertEqual(state["inventory"].get("amber_cap"), 1)
        self.assertEqual((state["inventory"].get("furnace"), state["inventory"].get("crafting_table")), (1, 1))

    def test_with_the_ingots_in_hand_no_furnace_is_made(self):
        state, grid = meadow_pet({"iron_pickaxe": 1, "stone_sword": 1, "iron_cap": 1, "amber": 2, "iron_ingot": 2,
                                  "crafting_table": 1, "cobblestone": 16})
        tools, steps = tool_choice(Situation(state, grid, DAY, 0.0))
        self.assertEqual(tools, ("amber_cap",))
        self.assertNotIn(("craft", "furnace"), named(steps))
        self.assertNotIn(("place", "furnace"), named(steps))

    def test_a_warding_lantern_from_iron_ore_brings_a_table_and_a_furnace(self):
        # Its lantern takes an iron ingot, smelted from ore; the furnace is crafted at a table placed first.
        state, grid = meadow_pet({"iron_pickaxe": 1, "stone_sword": 1, "gloom_dust": WARD_DUST, "torch": 1,
                                  "iron_ore": 1, "coal": 2, "cobblestone": 8, "crafting_table": 1})
        tools, steps = tool_choice(Situation(state, grid, DAY, 0.0))
        self.assertEqual(tools, ("warding_lantern",))
        kinds = named(steps)
        self.assertLess(kinds.index(("place", "crafting_table")), kinds.index(("craft", "furnace")))
        self.assertLess(kinds.index(("place", "furnace")), kinds.index(("smelt", "iron_ore")))
        run_steps(state, grid, steps)
        self.assertEqual(state["inventory"].get("warding_lantern"), 1)

    def test_with_nothing_to_make_a_furnace_from_the_order_waits(self):
        state, grid = meadow_pet({"iron_pickaxe": 1, "stone_sword": 1, "iron_cap": 1, "amber": 2, "iron_ore": 3,
                                  "coal": 3, "crafting_table": 1})
        self.assertIsNone(tool_choice(Situation(state, grid, DAY, 0.0)))


class ArmsTests(unittest.TestCase):
    """The L5 final fix wave, I3: the frontier's goods leave Mimo's arms. On the final review's gate amber, gold
    nuggets, diamonds and an iron cap an amber cap replaced held up to three of the sixteen stacks for good, and
    every pet that stalled on the way to its computer carried them."""

    def test_riches_go_in_the_chest_and_a_replaced_iron_cap_is_dropped(self):
        home = Home({"amber": 3, "gold_nugget": 7, "iron_cap": 1, "amber_cap": 1, "iron_pickaxe": 1}, chest={})
        s = home.situation()
        stored = dict(storage.to_store(s, home.chest))
        self.assertEqual((stored.get("amber"), stored.get("gold_nugget")), (3, 7))  # no iron tunic: no amber tunic
        self.assertIn(("iron_cap", 1), storage.junk(s))

    def test_a_leather_piece_under_an_amber_one_is_junk_with_no_iron_between(self):
        # m4 (I3r): replaced_pieces' other branch -- storage.junk's own iron-check compares a leather
        # piece only against the iron one it stands under, so with no iron cap in Mimo's arms (put away,
        # or an old one never made) a leftover leather cap under an amber one needed this branch instead.
        home = Home({"amber_cap": 1, "leather_cap": 1, "iron_pickaxe": 1}, chest={})
        self.assertIn(("leather_cap", 1), storage.junk(home.situation()))

    def test_the_amber_an_order_takes_stays_and_comes_back_out_of_the_chest(self):
        wearing = {"iron_cap": 1, "iron_pickaxe": 1, "iron_ingot": 2, "crafting_table": 1}
        home = Home({**wearing, "amber": 2}, chest={})
        self.assertNotIn("amber", dict(storage.to_store(home.situation(), home.chest)))
        stored = Home(dict(wearing), chest={"amber": 2})
        self.assertIn((stored.chest, "amber", 2), storage.to_take(stored.situation()))
        no_iron = Home({"iron_cap": 1, "iron_pickaxe": 1, "amber": 2, "crafting_table": 1}, chest={})
        self.assertEqual(dict(storage.to_store(no_iron.situation(), no_iron.chest)).get("amber"), 2)

    def test_amber_for_a_piece_it_cannot_make_now_waits_in_the_chest(self):
        # The gate's seed 42 on the first version of this fix: 58 game days at 15 and 16 stacks, 3 amber kept for a
        # tunic whose iron was ore and no cobblestone for the furnace to smelt it in.
        full = {"iron_cap": 1, "iron_tunic": 1, "iron_pickaxe": 1, "iron_ore": 3, "amber": 3, "crafting_table": 1}
        home = Home(dict(full), chest={})
        self.assertEqual(dict(storage.to_store(home.situation(), home.chest)).get("amber"), 3)
        furnace = Home({**full, "cobblestone": 8, "coal": 3}, chest={})  # with a furnace's stone it can smelt them
        self.assertNotIn("amber", dict(storage.to_store(furnace.situation(), furnace.chest)))

    def test_nothing_asks_for_an_iron_piece_an_amber_piece_replaced(self):
        inventory = {"amber_cap": 1, "iron_tunic": 1, "iron_pickaxe": 1, "iron_ingot": 5}
        self.assertNotIn(("iron_cap",), tool_orders(inventory, armor=True))
        self.assertEqual(armor_iron(inventory), 0)
        self.assertTrue(worn(inventory, "iron_cap") and worn(inventory, "leather_cap"))
        self.assertFalse(worn(inventory, "amber_tunic"))
        home = Home(dict(inventory), chest={})
        s = home.situation()
        self.assertNotIn("iron_ingot", gear_wanted(s))
        iron_armor = GOALS["armor_up"].milestones[-1]
        self.assertEqual(iron_armor.share(s), 1.0)

    def test_gloom_dust_waits_in_the_chest_until_a_warding_lantern_can_be_made(self):
        self.assertEqual(KEEP["gloom_dust"], 0)
        dust = Home({"gloom_dust": 2}, chest={})
        self.assertEqual(dict(storage.to_store(dust.situation(), dust.chest)).get("gloom_dust"), 2)
        lantern = Home({"gloom_dust": 3, "lantern": 1}, chest={})
        self.assertEqual(dict(storage.to_store(lantern.situation(), lantern.chest)).get("gloom_dust"), 1)
        stored = Home({"lantern": 1}, chest={"gloom_dust": 2})
        self.assertIn((stored.chest, "gloom_dust", 2), storage.to_take(stored.situation()))
        hung = Home({"gloom_dust": 2, "lantern": 1}, chest={})
        hung.state["wards"] = [[0, 2, 0], [2, 2, 0]]  # both warding lanterns already hang
        self.assertEqual(dict(storage.to_store(hung.situation(), hung.chest)).get("gloom_dust"), 2)

    def test_the_iron_for_a_wards_lantern_comes_out_of_the_chest_with_the_dust(self):
        # Hazel on the gate: 5 gloom dust in the chest, torches in hand, the iron for a lantern in the chest.
        home = Home({"torch": 2, "iron_pickaxe": 1, "iron_cap": 1, "iron_tunic": 1}, chest={"gloom_dust": 5, "iron_ingot": 4})
        takes = {item: amount for _, item, amount in storage.to_take(home.situation())}
        self.assertEqual((takes.get("gloom_dust"), takes.get("iron_ingot")), (2, 1))

    def test_diamonds_stay_for_the_next_diamond_tool_and_go_in_the_chest_after(self):
        ladder = Home({"iron_pickaxe": 1, "diamond": 2}, chest={})  # the diamond goal counts the ones carried
        self.assertNotIn("diamond", dict(storage.to_store(ladder.situation(), ladder.chest)))
        early = Home({"stone_pickaxe": 1, "diamond": 1}, chest={})  # no pickaxe that can use them yet
        self.assertEqual(dict(storage.to_store(early.situation(), early.chest)).get("diamond"), 1)
        done = Home({"diamond_pickaxe": 1, "diamond_sword": 1, "diamond": 3}, chest={})
        self.assertEqual(dict(storage.to_store(done.situation(), done.chest)).get("diamond"), 3)
        back = Home({"iron_pickaxe": 1, "diamond": 1, "sticks": 2, "crafting_table": 1}, chest={"diamond": 2})
        self.assertIn((back.chest, "diamond", 2), storage.to_take(back.situation()))  # enough for the pickaxe now
        sword = Home({"diamond_pickaxe": 1, "iron_sword": 1, "diamond": 2, "sticks": 1, "crafting_table": 1}, chest={})
        self.assertNotIn("diamond", dict(storage.to_store(sword.situation(), sword.chest)))
        crowded = Home({"diamond_pickaxe": 1, "iron_sword": 1, "diamond": 2, "oak_log": 2, "crafting_table": 1,
                        **{f"item_{n}": 1 for n in range(11)}}, chest={})  # 16 stacks: no room for its planks
        self.assertEqual(dict(storage.to_store(crowded.situation(), crowded.chest)).get("diamond"), 2)

    def test_gold_nuggets_stay_only_while_they_make_up_a_gold_pickaxe(self):
        makings = {"iron_pickaxe": 1, "sticks": 2, "crafting_table": 1, "cobblestone": 8}  # a gold pickaxe's furnace too
        short = Home({**makings, "gold_nugget": 7}, chest={})  # one ingot's worth short of three
        self.assertEqual(dict(storage.to_store(short.situation(), short.chest)).get("gold_nugget"), 7)
        enough = Home({**makings, "gold_nugget": 8, "gold_ingot": 1}, chest={})
        self.assertNotIn("gold_nugget", dict(storage.to_store(enough.situation(), enough.chest)))
        past = Home({"diamond_pickaxe": 1, "gold_nugget": 8, "gold_ingot": 1}, chest={})
        self.assertEqual(dict(storage.to_store(past.situation(), past.chest)).get("gold_nugget"), 8)

    def test_arrows_wait_in_the_chest_while_there_is_no_bow(self):
        # Old chests hold arrows; on the final review's gate a pet with no bow carried a stack of them for good.
        loose = Home({"arrow": 32}, chest={})
        self.assertEqual(dict(storage.to_store(loose.situation(), loose.chest)).get("arrow"), 32)
        bow = Home({"arrow": 32, "bow": 1}, chest={})
        self.assertNotIn("arrow", dict(storage.to_store(bow.situation(), bow.chest)))
        back = Home({"bow": 1, "arrow": 4}, chest={"arrow": 20})
        self.assertIn((back.chest, "arrow", 20), storage.to_take(back.situation()))


class WardHomeTests(unittest.TestCase):
    """A finished cottage at home on a meadow, as test_survival_lighting builds it."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in design.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        set_home(self.db, design.anchor, 1.0)

    def situation(self, inventory):
        state = {"name": "Pip", "world_seed": "1", "position": {"x": 1.0, "y": 1.0, "z": 1.0},
                 "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(state)
        return Situation(state, self.grid, DAY, 0.0, self.db)

    def test_ward_home_hangs_one_on_a_corner_in_place_of_its_torch(self):
        ward = PURPOSES["ward_home"]
        self.assertFalse(ward.valid(self.situation({"warding_lantern": 1})))  # no light on a corner yet
        self.grid.put(*CORNERS[0], "torch")
        s = self.situation({"warding_lantern": 1})
        self.assertTrue(ward.valid(s))
        self.assertTrue(meets_need(s, "ward_home", ward.score(s)))
        steps = ward.plan(s, ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                           events=[], db=self.db))
        self.assertEqual([step["kind"] for step in steps][-2:], ["mine", "place"])
        self.assertEqual((steps[-1]["target"], steps[-1]["block"]), (CORNERS[0], "warding_lantern"))
        self.grid.put(*CORNERS[0], "warding_lantern")
        self.assertNotIn(tuple(CORNERS[0]), [tuple(cell) for cell in dark_corners(self.situation({}))])


if __name__ == "__main__":
    unittest.main()
