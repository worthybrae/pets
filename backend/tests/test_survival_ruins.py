import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.worldgen import block_at
from backend.survival import brain  # noqa: F401  (registers loot_ruin, the open_chest step and the observers)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.brain import observe_step
from backend.survival.carrying import CARRY_STACKS, stacks
from backend.survival.frontier import opened_since, unopened_ruins
from backend.survival.goals import adopt_goal, meets_need
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, places
from backend.survival.purposes import PURPOSES
from backend.survival.ruins import LOOT, LOOT_BATCHES, RUIN, ruin_loot, ruins_near, takeable
from backend.survival.situation import Situation
from backend.survival.steps import OBSERVERS, StepFailed, finish_step, start_step
from backend.survival.trips import REASONS
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
from backend.tests.test_survival_pickers import DAY, NIGHT

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

    def test_open_chest_through_observe_step_marks_the_place_opened(self):
        # Task 6 review, M1: a test that runs open_chest, then observe_step, and checks the place's
        # opened flag (note_opened, one of steps.OBSERVERS) and the notable loot event.
        pet = Pet(offset=(2, 0), center=(CHEST[0] - 150, CHEST[2]))
        pet.walked()
        self.assertEqual(places(pet.db, (RUIN,))[0]["data"], {})
        pet.run({"kind": "open_chest", "target": list(CHEST)})
        observe_step(pet.state, {"kind": "open_chest", "target": list(CHEST)}, pet.context, 5.0)
        self.assertEqual(places(pet.db, (RUIN,))[0]["data"], {"opened": 5.0})

    def test_a_night_situation_makes_loot_ruin_invalid(self):
        # Task 6 review, M1: a test for loot_valid's own "not s.night" guard.
        pet = Pet(offset=(2, 0))
        pet.walked()
        self.assertTrue(PURPOSES["loot_ruin"].valid(pet.situation()))
        night = Situation(pet.state, pet.grid, NIGHT, 10.0, pet.db)
        self.assertFalse(PURPOSES["loot_ruin"].valid(night))

    def test_a_placed_chest_that_is_not_a_ruins_fails_as_gone(self):
        # Task 6 review, M1: a chest Mimo built (not a ruin's own) fails open_chest as "gone".
        built = (CHEST[0] + 5, CHEST[1], CHEST[2])
        pet = Pet(offset=(5, 0))
        pet.grid = Grid(lambda x, y, z: "chest" if (x, y, z) == built else block_at(x, y, z, SEED))
        with self.assertRaises(StepFailed) as caught:
            pet.run({"kind": "open_chest", "target": list(built)})
        self.assertEqual(caught.exception.code, "gone")

    def test_at_sixteen_stacks_takeable_is_empty(self):
        # Task 6 review, M1: at CARRY_STACKS (16) full there is no room for anything, riches included.
        pet = Pet(offset=(2, 0), inventory={f"item_{n}": 1 for n in range(CARRY_STACKS)})
        pet.state.setdefault("chests", {})[chest_key(CHEST)] = {"gold_nugget": 4, "amber": 2, "iron_ingot": 2}
        self.assertEqual(takeable(pet.situation(), CHEST), {})

    def test_plan_loot_stops_after_loot_batches(self):
        # Task 6 review, M1: plan_loot's own LOOT_BATCHES cap (at most 3 batches a choice).
        pet = Pet(offset=(2, 0))
        pet.walked()
        s = pet.situation()
        self.assertTrue(PURPOSES["loot_ruin"].plan(s, pet.context))  # a target stands: steps are planned
        s.brain["batches"] = LOOT_BATCHES
        self.assertEqual(PURPOSES["loot_ruin"].plan(s, pet.context), [])

    def test_a_crashing_observer_never_stops_the_tick(self):
        # Task 6 review, M1: OBSERVERS are each guarded (brain.observe_step); one crashing does not
        # stop the rest from running, nor the tick.
        def boom(state, step, context, at):
            raise RuntimeError("boom")

        pet = Pet(offset=(20, 0), center=(CHEST[0] - 150, CHEST[2]))
        OBSERVERS.insert(0, boom)
        try:
            pet.walked()
        finally:
            OBSERVERS.remove(boom)
        self.assertEqual([(place["kind"], place["note"]) for place in places(pet.db, (RUIN,))], [(RUIN, "far wilds")])

    def test_find_manual_does_nothing_before_the_journal_is_ready(self):
        # Task 6 review, M1: find_manual's own journal_ready guard (before the tick first tends
        # curiosity, or with no database, the journal does nothing yet).
        chests = ruins_near(SEED, 4000, 0, 900)
        holding = next(chest for chest in chests if holds_manual(SEED, chest))
        pet = Pet()  # curiosity_state was never called: the journal is not ready yet
        find_manual(pet.state, {"kind": "open_chest", "target": list(holding)}, pet.context, 5.0)
        self.assertFalse(taught(pet.db, SPARK))
        self.assertEqual(pet.context.events, [])

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

    def test_a_chest_with_no_path_is_not_retried_until_its_penalty_passes(self):
        # Task 6 review, M2: ruin_targets had no near_failure guard (storage.reachable_chests has
        # one), so a chest a step just failed to reach was tried again at once.
        pet = Pet(offset=(12, 0))
        pet.walked()
        self.assertTrue(PURPOSES["loot_ruin"].valid(pet.situation()))
        pet.state["recent_actions"] = [{"target": {"x": CHEST[0], "y": CHEST[1], "z": CHEST[2]}, "result": "failed"}]
        self.assertFalse(PURPOSES["loot_ruin"].valid(pet.situation()))
        pet.state["recent_actions"] = []  # the failure ages out of the window: worth trying again
        self.assertTrue(PURPOSES["loot_ruin"].valid(pet.situation()))
        # Already at the chest (within REACH): an unrelated failure near it does not block it.
        pet.state["position"] = {"x": float(CHEST[0] + 1), "y": 9.0, "z": float(CHEST[2])}
        pet.state["recent_actions"] = [{"target": {"x": CHEST[0], "y": CHEST[1], "z": CHEST[2]}, "result": "failed"}]
        self.assertTrue(PURPOSES["loot_ruin"].valid(pet.situation()))


FULL = {**GEARED, "dirt": 10, "cobblestone": 20, "coal": 8, "sticks": 4, "seeds": 3, "wheat": 2, "flint": 1,
        "string": 1, "feather": 1, "sapling": 1, "planks": 4}  # 15 stacks: RICHES_ROOM, no room for a new one


class RichesTests(unittest.TestCase):
    """The L5 final fix wave, I2: far riches come home. On the final review's gate 42 % of the gold and amber in far
    chests was still there on day 150: at 15 stacks nothing more fit, loot_ruin ended right after opening the
    chest, and nothing ever sent Mimo back for what was left."""

    def far_pet(self, inside, inventory=FULL):
        pet = Pet(offset=(2, 0), center=(CHEST[0] - 150, CHEST[2]), inventory=inventory)  # a far wilds ruin
        pet.walked()
        pet.state.setdefault("chests", {})[chest_key(CHEST)] = dict(inside)  # opened already
        return pet

    def test_at_fifteen_stacks_it_leaves_a_block_stack_behind_and_takes_the_gold(self):
        pet = self.far_pet({"gold_nugget": 3})
        self.assertEqual(stacks(pet.state["inventory"]), 15)
        self.assertEqual(takeable(pet.situation(), CHEST), {})  # as it is, no room
        self.assertTrue(PURPOSES["loot_ruin"].valid(pet.situation()))
        steps = PURPOSES["loot_ruin"].plan(pet.situation(), pet.context)
        self.assertEqual([(step["kind"], step["item"]) for step in steps], [("drop", "dirt"), ("take", "gold_nugget")])
        for step in steps:
            pet.run(step)
        self.assertEqual((pet.state["inventory"].get("gold_nugget"), pet.state["inventory"].get("dirt")), (3, None))
        self.assertEqual(pet.state["chests"][chest_key(CHEST)], {})

    def test_the_iron_its_armor_still_takes_comes_out_past_loot_room(self):
        # Willow on the fix wave's gate: 15 iron ingots sat in five old chests near home (loot_ruin takes all but
        # riches only below LOOT_ROOM, 12 stacks, and it carried 13 to 16), while its iron tunic waited on ore
        # it had not mined, 31 game days past the armor goal Making's gate set for it.
        full = {"iron_pickaxe": 1, "iron_cap": 1, "stone_sword": 1, "coal": 8, "sticks": 4, "seeds": 3, "wheat": 2,
                "flint": 1, "string": 1, "feather": 1, "sapling": 1, "planks": 4, "dirt": 10}  # 13 stacks
        pet = Pet(offset=(2, 0), inventory=dict(full))
        pet.walked()
        pet.state.setdefault("chests", {})[chest_key(CHEST)] = {"iron_ingot": 4, "bread": 3, "arrow": 6}
        self.assertEqual(takeable(pet.situation(), CHEST), {"iron_ingot": 4})  # the tunic takes 8: all of it
        tunic = Pet(offset=(2, 0), inventory={**full, "iron_cap": 0, "iron_tunic": 1, "iron_ore": 3})
        tunic.state.setdefault("chests", {})[chest_key(CHEST)] = {"iron_ingot": 4, "bread": 3}
        self.assertEqual(takeable(tunic.situation(), CHEST), {"iron_ingot": 2})  # the cap's 5, less 3 ore carried
        stone = Pet(offset=(2, 0), inventory={**full, "iron_pickaxe": 0, "stone_pickaxe": 1})
        stone.state.setdefault("chests", {})[chest_key(CHEST)] = {"iron_ingot": 4, "bread": 3}
        self.assertEqual(takeable(stone.situation(), CHEST), {})  # no iron armor before an iron pickaxe

    def test_with_nothing_it_may_leave_behind_the_riches_wait(self):
        pet = self.far_pet({"gold_nugget": 3}, {**{f"item_{n}": 1 for n in range(11)}, **GEARED})  # 15 stacks
        self.assertFalse(PURPOSES["loot_ruin"].valid(pet.situation()))

    def test_a_chest_opened_but_not_emptied_of_riches_stays_a_target(self):
        pet = self.far_pet({"gold_nugget": 3, "arrow": 6})
        s = pet.situation()
        self.assertIn(CHEST, unopened_ruins(s, 2))
        self.assertEqual(REASONS["riches"].value(s, CHEST[0] + 3, CHEST[2]), (1.0, "an old ruin in the far wilds, danger 2"))
        self.assertEqual([spot[:2] for spot in REASONS["riches"].spots(s)], [(CHEST[0], CHEST[2])])
        self.assertEqual(REASONS["riches"].look(s, pet.context).words, "an old ruin in the far wilds, danger 2")
        pet.state["chests"][chest_key(CHEST)] = {"arrow": 6}  # the riches are gone: arrows alone are no riches
        self.assertNotIn(CHEST, unopened_ruins(pet.situation(), 2))

    def test_taking_riches_from_an_old_chest_counts_as_opening_one_for_the_goal(self):
        pet = self.far_pet({"gold_nugget": 3}, dict(GEARED))
        adopt_goal(pet.state, "frontier", "utility", "", 50.0)  # set after the chest was opened
        self.assertFalse(opened_since(pet.situation()))
        pet.run({"kind": "take", "target": list(CHEST), "item": "gold_nugget", "amount": 3})
        observe_step(pet.state, {"kind": "take", "target": list(CHEST), "item": "gold_nugget", "amount": 3},
                     pet.context, 60.0)
        self.assertEqual(places(pet.db, (RUIN,))[0]["data"], {"looted": 60.0})
        self.assertTrue(opened_since(pet.situation()))
        observe_step(pet.state, {"kind": "take", "target": list(CHEST), "item": "arrow", "amount": 3}, pet.context, 70.0)
        self.assertEqual(places(pet.db, (RUIN,))[0]["data"], {"looted": 60.0})  # arrows are no riches


class PreflightTests(unittest.TestCase):
    """Pre-flight on eda93d4: Making's old manual (carry 4), Bond's and Mind's moments (carry 6)."""

    def test_the_ruin_manuals_found_event_is_logged_after_note_discoveries_like_the_copper_manual(self):
        # Task 6 review, M6: find_manual used to run inside OBSERVERS, before note_discoveries counted
        # the step's "found"/"discovered" events (NEW_PLACE each) for curiosity -- the copper seam's
        # manual (tinker.observe_tinker) runs after note_discoveries, so a ruin's manual used to cost
        # curiosity the copper one never does. The fix calls find_manual after note_discoveries too
        # (brain.observe_step), so note_discoveries never sees the manual's own "found" event.
        chests = ruins_near(SEED, 4000, 0, 900)
        holding = next(chest for chest in chests if holds_manual(SEED, chest))
        pet = Pet(offset=(holding[0] - CHEST[0], holding[2] - CHEST[2]))
        curiosity_state(pet.state, 0.0)  # the journal is on once curiosity is tended
        pet.run({"kind": "open_chest", "target": list(holding)})  # rolls the loot; the chest is open now
        seen = []
        real = brain.note_discoveries

        def spy(state, step, context, at, events):
            seen.append(list(events))
            return real(state, step, context, at, events)

        with patch("backend.survival.brain.note_discoveries", spy):
            observe_step(pet.state, {"kind": "open_chest", "target": list(holding)}, pet.context, 5.0)
        self.assertEqual(seen, [[]])  # no "found" event was in the window note_discoveries looked at
        self.assertIn((5.0, "found", "Pip found an old manual in the ruin's chest."), pet.context.events)

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
        steps = PURPOSES["loot_ruin"].plan(pet.situation(), pet.context)
        # Task 6 review, M3: riches used to fill the very last stack (CARRY_STACKS, 16), leaving no
        # room at all, so the next bit of food pushed out flint or leather instead of being carried
        # freely. The fix caps riches one stack short (CARRY_STACKS - 1). The L5 final fix wave (I2): the
        # gold nuggets, which would have been the 16th stack, no longer stay behind: the moss, the least
        # useful block Mimo carries, is left there to make room for them.
        self.assertEqual([(step["kind"], step["item"], step["amount"]) for step in steps],
                         [("drop", "moss", 1), ("take", "amber", 1), ("take", "gold_nugget", 4)])
        for step in steps:
            pet.run(step)
        self.assertLess(stacks(pet.state["inventory"]), CARRY_STACKS)  # a stack of room left for food

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
