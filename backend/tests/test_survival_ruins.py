import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.services.worldgen import block_at
from backend.survival import brain  # noqa: F401  (registers loot_ruin, the open_chest step and the observers)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.brain import observe_step
from backend.survival.goals import meets_need
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, places
from backend.survival.purposes import PURPOSES
from backend.survival.ruins import LOOT, RUIN, ruin_loot, ruins_near
from backend.survival.situation import Situation
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS
from backend.survival import bonding, minding  # noqa: F401  (the inbox's and Mind's writers register)
from backend.survival.curiosity import curiosity_state
from backend.survival.hatch import hatch
from backend.survival.housework import chest_key
from backend.survival.inbox import inbox_items
from backend.survival.journal import taught
from backend.survival.larder import chest_food
from backend.survival.registry import LifeRegistry
from backend.survival.ruins import find_manual, holds_manual, loot_words
from backend.survival.talker import run_chores
from backend.survival.tinker import SPARK
from backend.survival.world import SurvivalWorld, log_event
from backend.tests.test_survival_pickers import DAY

SEED = "123456789123456789"
CHEST = (3920, 9, 218)  # the chest of region (40, 2)'s ruin, on ground 8
GEARED = {"stone_sword": 1, "leather_cap": 1, "leather_tunic": 1, "bread": 2}


class Pet:
    """Mimo in the real generated world of SEED, with its memory, `offset` blocks east of the ruin's chest."""

    def __init__(self, offset=(2, 0), center=None, inventory=None):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = Grid(lambda x, y, z: block_at(x, y, z, SEED))
        x, z = CHEST[0] + offset[0], CHEST[2] + offset[1]
        self.state = {"name": "Pip", "world_seed": SEED, "position": {"x": float(x), "y": 9.0, "z": float(z)},
                      "inventory": dict(inventory or {}), "vitals": dict(START_VITALS), "traits": {},
                      "last_tick_at": 0.0, "frontier": {"center": list(center or (CHEST[0], CHEST[2]))}}
        ensure_actions(self.state)
        self.context = ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[],
                                     db=self.db)

    def situation(self):
        return Situation(self.state, self.grid, DAY, 0.0, self.db)

    def walked(self):
        observe_step(self.state, {"kind": "walk", "path": [], "target": dict(self.state["position"])}, self.context, 1.0)

    def run(self, spec):
        step = start_step(spec, self.state, self.grid, 1.0)
        return finish_step(step, self.state, self.grid, 2.0)


class LootTableTests(unittest.TestCase):
    def test_the_same_chest_in_the_same_ring_always_holds_the_same(self):
        self.assertEqual(ruin_loot(SEED, CHEST, 2), ruin_loot(SEED, CHEST, 2))
        self.assertNotEqual(ruin_loot(SEED, CHEST, 1), ruin_loot(SEED, CHEST, 3))

    def test_nearer_ruins_hold_food_arrows_and_iron_farther_ones_gold_amber_and_diamonds(self):
        chests = ruins_near(SEED, 4000, 0, 900)
        near = [ruin_loot(SEED, chest, 0) for chest in chests] + [ruin_loot(SEED, chest, 1) for chest in chests]
        far = [ruin_loot(SEED, chest, 3) for chest in chests] + [ruin_loot(SEED, chest, 4) for chest in chests]
        self.assertGreater(len(chests), 10)
        self.assertEqual(set().union(*near), {"bread", "arrow", "iron_ingot", "torch", "coal"})
        self.assertTrue({"gold_ingot", "amber", "diamond"} <= set().union(*far))
        self.assertFalse({"gold_ingot", "gold_nugget", "amber", "diamond"} & set().union(*near))
        self.assertEqual(sorted(LOOT), [0, 1, 2, 3, 4])


class RuinTests(unittest.TestCase):
    def test_a_ruin_in_sight_after_a_walk_is_remembered_once_and_notable(self):
        pet = Pet(offset=(20, 0), center=(CHEST[0] - 150, CHEST[2]))
        pet.walked()
        pet.walked()
        self.assertEqual([(place["kind"], place["note"]) for place in places(pet.db, (RUIN,))], [(RUIN, "far wilds")])
        self.assertEqual([text for _, kind, text in pet.context.events if kind == "found"],
                         ["Pip found an old ruin in the far wilds."])

    def test_opening_its_old_chest_rolls_the_loot_by_its_ring_once(self):
        pet = Pet(center=(CHEST[0] - 150, CHEST[2]))
        with self.assertRaises(StepFailed):
            Pet(offset=(10, 0)).run({"kind": "open_chest", "target": list(CHEST)})  # out of reach
        kind, text = pet.run({"kind": "open_chest", "target": list(CHEST)})
        self.assertEqual(pet.state["chests"]["3920,9,218"], ruin_loot(SEED, CHEST, 2))
        self.assertEqual(kind, "loot")
        self.assertTrue(text.startswith("Pip opened an old chest in a ruin: "))
        with self.assertRaises(StepFailed):
            pet.run({"kind": "open_chest", "target": list(CHEST)})  # open already
        with self.assertRaises(StepFailed):
            pet.run({"kind": "open_chest", "target": [CHEST[0] + 1, CHEST[1], CHEST[2]]})  # no chest there

    def test_loot_ruin_opens_the_chest_then_takes_what_fits(self):
        pet = Pet(offset=(12, 0))
        pet.walked()
        loot = PURPOSES["loot_ruin"]
        s = pet.situation()
        self.assertTrue(loot.valid(s))
        self.assertTrue(meets_need(s, "loot_ruin", loot.score(s)))  # an unopened chest in sight is an urge
        self.assertIn("its chest never opened", loot.facts(s))
        steps = loot.plan(s, pet.context)
        self.assertEqual([step["kind"] for step in steps], ["walk", "open_chest"])
        pet.state["position"] = {"x": float(CHEST[0] + 2), "y": 9.0, "z": float(CHEST[2])}
        pet.run(steps[-1])
        takes = loot.plan(pet.situation(), pet.context)
        self.assertEqual({step["item"]: step["amount"] for step in takes}, ruin_loot(SEED, CHEST, 0))
        for step in takes:
            pet.run(step)
        self.assertFalse(loot.valid(pet.situation()))  # nothing left in it

    def test_with_its_arms_nearly_full_it_takes_the_rarest_first_and_leaves_the_rest(self):
        blocks = ("dirt", "gravel", "sand", "clay", "moss", "basalt", "limestone", "sandstone", "cobblestone", "planks")
        pet = Pet(offset=(2, 0), inventory={block: 1 for block in blocks})  # 10 stacks: room for 2 below LOOT_ROOM
        pet.walked()
        pet.run({"kind": "open_chest", "target": list(CHEST)})
        takes = PURPOSES["loot_ruin"].plan(pet.situation(), pet.context)
        self.assertEqual({step["item"]: step["amount"] for step in takes}, {"iron_ingot": 2, "bread": 3})
        for step in takes:
            pet.run(step)
        self.assertEqual(pet.state["chests"][f"{CHEST[0]},{CHEST[1]},{CHEST[2]}"], {"arrow": 6, "torch": 3})
        self.assertFalse(PURPOSES["loot_ruin"].valid(pet.situation()))  # no room: the rest waits in the chest

    def test_a_pet_goes_to_a_ruin_only_in_a_ring_it_is_ready_for(self):
        far = Pet(offset=(12, 0), center=(CHEST[0] - 150, CHEST[2]))
        far.walked()
        self.assertFalse(PURPOSES["loot_ruin"].valid(far.situation()))
        far.state["inventory"] = dict(GEARED)
        self.assertTrue(PURPOSES["loot_ruin"].valid(far.situation()))


class PreflightTests(unittest.TestCase):
    """Pre-flight on eda93d4: Making's old manual (carry 4), Bond's and Mind's moments (carry 6)."""

    def test_an_old_chest_may_hold_an_old_manual_that_teaches_the_spark_once(self):
        chests = ruins_near(SEED, 4000, 0, 900)
        holding = [chest for chest in chests if holds_manual(SEED, chest)]
        self.assertTrue(2 <= len(holding) < len(chests), (len(holding), len(chests)))
        pet = Pet()
        curiosity_state(pet.state, 0.0)  # the journal is on once curiosity is tended
        find_manual(pet.state, {"kind": "open_chest", "target": list(holding[0])}, pet.context, 5.0)
        self.assertTrue(taught(pet.db, SPARK))
        self.assertIn((5.0, "found", "Pip found an old manual in the ruin's chest."), pet.context.events)
        pet.context.events.clear()
        find_manual(pet.state, {"kind": "open_chest", "target": list(holding[1])}, pet.context, 6.0)
        self.assertEqual(pet.context.events, [])  # known already: the next manual teaches nothing new
        other = Pet()
        curiosity_state(other.state, 0.0)
        empty = next(chest for chest in chests if not holds_manual(SEED, chest))
        find_manual(other.state, {"kind": "open_chest", "target": list(empty)}, other.context, 5.0)
        self.assertFalse(taught(other.db, SPARK))

    def test_food_left_in_an_old_chest_is_no_larder(self):
        pet = Pet()
        pet.state["chests"] = {chest_key(CHEST): {"bread": 3}}
        self.assertEqual(chest_food(pet.situation()), 0.0)
        pet.state["chests"]["0,1,0"] = {"bread": 2}  # a chest Mimo built
        self.assertEqual(chest_food(pet.situation()), 50.0)

    def test_with_its_arms_nearly_full_it_still_takes_the_riches(self):
        blocks = ("dirt", "gravel", "sand", "clay", "moss", "basalt", "limestone", "sandstone", "cobblestone", "planks",
                  "sticks", "coal", "seeds", "wheat")
        pet = Pet(offset=(2, 0), inventory={block: 1 for block in blocks})  # 14 stacks: past LOOT_ROOM
        pet.walked()
        pet.state.setdefault("chests", {})[chest_key(CHEST)] = {"gold_nugget": 4, "amber": 1, "iron_ingot": 2, "bread": 2}
        takes = PURPOSES["loot_ruin"].plan(pet.situation(), pet.context)
        self.assertEqual({step["item"]: step["amount"] for step in takes}, {"amber": 1, "gold_nugget": 4})

    def test_the_loot_is_told_in_words(self):
        self.assertEqual(loot_words({"arrow": 9, "bread": 4, "gold_nugget": 3, "torch": 2, "amber": 1}),
                         "9 arrows, 4 bread, 3 gold nuggets, 2 torches and 1 amber")

    def test_the_frontiers_firsts_and_an_old_chest_are_remembered_and_told(self):
        born = 1_000_000.0
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=born)
            world = SurvivalWorld(registry.world_path(life))
            name = life["name"]
            run_chores(world, born + 1, 1.0)  # the inbox and Mind's memory start
            events = [("found", f"{name} reached the far wilds for the first time."),
                      ("found", f"{name} met its first thornback."),
                      ("found", f"{name} found an old ruin in the far wilds."),
                      ("loot", f"{name} opened an old chest in a ruin: 4 gold nuggets and 2 amber."),
                      ("found", f"{name} found an old manual in the ruin's chest.")]
            with world.transaction() as db:
                for number, (kind, text) in enumerate(events):
                    log_event(db, born + 2 + number, kind, text)
            run_chores(world, born + 10, 1.0)
            with world.connect() as db:
                told = [item["text"] for item in inbox_items(db, 100)]
                remembered = [row[0] for row in db.execute("SELECT text FROM mind_memories")]
        mine = ["I reached the far wilds for the first time.", "I met my first thornback.",
                "I found an old ruin in the far wilds.", "I opened an old chest in a ruin: 4 gold nuggets and 2 amber.",
                "I found an old manual in the ruin's chest."]
        self.assertEqual(sorted(text for text in told if text in mine), sorted(mine))
        self.assertTrue(set(mine) <= set(remembered), set(mine) - set(remembered))


if __name__ == "__main__":
    unittest.main()
