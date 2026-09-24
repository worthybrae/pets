import sqlite3
import unittest

from backend.survival.creatures.acts import Scene, act
from backend.survival.creatures.combat import drops_of, strike
from backend.survival.creatures.harm import armor_cut, hurt_pet
from backend.survival.creatures.hostiles import BURN_SECONDS, CHASE_STEPS, LOITER, hostile_near
from backend.survival.creatures.kinds import KINDS, huntable, land_kinds
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables, dead
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, places
from backend.survival.steps import finish_step, start_step
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS

NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}
DAY = {**NIGHT, "phase": "day", "seconds_into_day": 1000.0}


def meadow(blocks=None):
    """Grass at y 0 with `blocks` placed, creatures and memory in one database."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    create_memory_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "died_at": None, "brain": new_brain(0.0), "last_thought": ""}
    state["brain"]["pending"] = None
    state.update(changes)
    return state


def scene(grid, state, at=10.0, clock=NIGHT):
    return Scene(grid, grid.herd, "5", state, at, 1.0, events=[], clock=clock)


def hostile(grid, kind="gloomling", cell=(5, 1, 0), **state):
    return grid.herd.add(kind, cell, KINDS[kind].health, 0.0, 0.0, {"home": list(cell), "turn": 0, "pose": "idle",
                                                                     **state})


class KindTests(unittest.TestCase):
    def test_gloomlings_and_skitters_are_hostile_and_never_hunted_or_spawned_in_herds(self):
        gloom, skitter = KINDS["gloomling"], KINDS["skitter"]
        self.assertEqual((gloom.health, gloom.damage, gloom.cooldown, gloom.burns), (20.0, 3.0, 1.2, True))
        self.assertEqual((skitter.health, skitter.damage, skitter.cooldown, skitter.burns), (12.0, 2.0, 1.0, False))
        self.assertLess(skitter.speed, gloom.speed)  # seconds per block: the skitter is fast
        self.assertEqual((gloom.drops, skitter.drops), ({"gloom_dust": (0, 2)}, {"string": (0, 2)}))
        for kind in (gloom, skitter):
            self.assertTrue(kind.hostile)
            self.assertFalse(kind.flee_when_hurt)
            self.assertFalse(huntable(kind))
            self.assertNotIn(kind, land_kinds("meadow"))


class ChaseTests(unittest.TestCase):
    def test_a_hostile_within_sixteen_blocks_comes_two_blocks_a_turn_and_raises_the_alarm_once(self):
        grid, state = meadow(), pet()
        gloom = hostile(grid, cell=(10, 1, 0))
        night = scene(grid, state)
        self.assertEqual(act(gloom, night), "chase")
        self.assertEqual((cell_of(gloom), gloom["state"]["pose"], gloom["state"]["chasing"]), ((8, 1, 0), "chasing", True))
        self.assertEqual(len(gloom["state"]["path"]), CHASE_STEPS + 1)
        self.assertAlmostEqual(gloom["next_at"], 10.0 + 2 * KINDS["gloomling"].speed)
        self.assertEqual(state["brain"]["pending"]["reasons"], ["threat"])
        self.assertTrue(state["brain"]["pending"]["urgent"])
        other = hostile(grid, "skitter", (0, 1, 12))
        self.assertEqual(act(other, night), "chase")
        self.assertEqual([event[1:] for event in night.events], [("threat", "Pip saw a gloomling coming.")])

    def test_hostile_near_and_the_alarm_agree_with_strike_that_a_claimed_door_is_not_safe(self):
        # Fix round 1, defect 4: a shelter's door is claimed (so nothing built there ever gets
        # dug up, and no creature ever steps into it), but it is not a room or passage cell, so a
        # blow still lands there (harm.sheltered); hostile_near and the alarm must agree.
        grid, state = meadow(), pet()
        grid.herd.db.execute("INSERT INTO structure_cells(x,y,z,structure,part,block) VALUES (0,1,0,1,'door','door')")
        grid.claims.add((0, 1, 0))
        gloom = hostile(grid, cell=(5, 1, 0))
        self.assertTrue(hostile_near(grid, grid.herd.db, state))
        self.assertEqual(act(gloom, scene(grid, state)), "chase")
        self.assertEqual(state["brain"]["pending"]["reasons"], ["threat"])

    def test_farther_than_sixteen_it_prowls_and_it_gives_up_a_chase_past_twenty_four(self):
        grid, state = meadow(), pet()
        self.assertEqual(act(hostile(grid, cell=(20, 1, 0)), scene(grid, state)), "prowl")
        self.assertEqual(act(hostile(grid, cell=(20, 1, 0), chasing=True), scene(grid, state)), "chase")
        gone = hostile(grid, cell=(30, 1, 0), chasing=True)
        self.assertEqual(act(gone, scene(grid, state)), "prowl")
        self.assertFalse(gone["state"]["chasing"])

    def test_what_lives_in_a_cave_under_mimo_leaves_it_be_and_fades_after_a_while(self):
        cave = {(x, y, 0): "air" for x in range(2, 6) for y in (-5, -4)}
        grid, state = meadow(cave), pet()
        below = hostile(grid, "skitter", (3, -5, 0))
        self.assertEqual(act(below, scene(grid, state)), "prowl")
        self.assertFalse(dead(below))
        act(below, scene(grid, state, at=LOITER + 1.0))
        self.assertTrue(dead(below))
        self.assertEqual(below["state"]["drops"], [])
        chaser = hostile(grid, cell=(10, 1, 0))
        act(chaser, scene(grid, state, at=LOITER + 1.0))  # coming after Mimo keeps it about
        self.assertFalse(dead(chaser))

    def test_a_hit_hostile_turns_on_mimo_from_farther_away(self):
        grid, state = meadow(), pet()
        gloom = hostile(grid, cell=(20, 1, 0))
        strike(scene(grid, state), gloom, 5.0, (0, 1, 0))
        self.assertEqual((gloom["health"], gloom["state"]["chasing"]), (15.0, True))
        self.assertEqual(act(gloom, scene(grid, state, at=11.0)), "chase")

    def test_a_gloomling_needs_two_cells_of_room_and_a_skitter_one(self):
        ceiling = {(x, 2, z): "planks" for x in (2, 3) for z in range(-3, 4)}
        grid, state = meadow(ceiling), pet()
        gloom, skitter = hostile(grid, cell=(4, 1, 0)), hostile(grid, "skitter", (4, 1, 1))
        self.assertEqual(act(gloom, scene(grid, state)), "chase")
        self.assertEqual((cell_of(gloom), gloom["state"]["pose"]), ((4, 1, 0), "idle"))
        self.assertEqual(act(skitter, scene(grid, state)), "chase")
        self.assertEqual(cell_of(skitter)[0], 2)

    def test_it_waits_at_a_door_it_cannot_pass(self):
        wall = {(2, y, z): "cobblestone" for y in (1, 2) for z in range(-4, 5)}
        grid, state = meadow({**wall, (2, 1, 0): "door", (2, 2, 0): "air"}), pet()
        gloom = hostile(grid, cell=(4, 1, 0))
        at = 10.0
        for _ in range(6):
            act(gloom, scene(grid, state, at))
            at = gloom["next_at"]
            self.assertGreater(cell_of(gloom)[0], 2)
        self.assertEqual(cell_of(gloom), (3, 1, 0))
        self.assertEqual(state["vitals"]["health"], 100.0)


class StrikeTests(unittest.TestCase):
    def test_a_hostile_in_reach_hits_mimo_once_a_cooldown_and_mimo_remembers_the_place(self):
        grid, state = meadow(), pet()
        gloom = hostile(grid, cell=(1, 1, 0))
        first = scene(grid, state, at=10.0)
        self.assertEqual(act(gloom, first), "strike")
        self.assertEqual((state["vitals"]["health"], state["hurt_at"], state["hurt_by"]), (97.0, 10.0, "gloomling"))
        self.assertEqual((gloom["state"]["pose"], gloom["state"]["struck_at"], gloom["next_at"]), ("attacking", 10.0, 11.2))
        self.assertEqual([event[1:] for event in first.events], [("hurt", "Pip was hit by a gloomling.")])
        self.assertEqual(act(gloom, scene(grid, state, at=10.5)), "chase")  # waits out its cooldown, in reach
        self.assertEqual((state["vitals"]["health"], gloom["state"]["pose"], gloom["next_at"]), (97.0, "attacking", 11.2))
        again = scene(grid, state, at=11.2)
        self.assertEqual(act(gloom, again), "strike")
        self.assertEqual((state["vitals"]["health"], again.events), (94.0, []))  # one hurt event in ten seconds
        danger = places(grid.herd.db, ("danger",))
        self.assertEqual([((place["x"], place["y"], place["z"]), place["note"]) for place in danger],
                         [((0, 1, 0), "gloomling")])

    def test_armor_takes_its_share_of_every_blow(self):
        self.assertEqual(armor_cut({}), 0.0)
        self.assertAlmostEqual(armor_cut({"leather_cap": 1}), 0.08)
        self.assertAlmostEqual(armor_cut({"leather_cap": 1, "leather_tunic": 1}), 0.2)
        grid, state = meadow(), pet(inventory={"leather_cap": 1, "leather_tunic": 1})
        self.assertAlmostEqual(hurt_pet(scene(grid, state), 3.0, "gloomling"), 2.4)
        self.assertAlmostEqual(state["vitals"]["health"], 97.6)

    def test_health_falling_past_fifty_asks_for_a_choice_at_once(self):
        grid, state = meadow(), pet(vitals={**START_VITALS, "health": 52.0})
        hurt_pet(scene(grid, state), 3.0, "skitter")
        self.assertEqual(state["brain"]["pending"]["reasons"], ["health_50"])
        self.assertTrue(state["brain"]["pending"]["urgent"])

    def test_no_blow_goes_through_a_wall_or_round_a_roofs_edge(self):
        grid, state = meadow({(1, 1, 0): "planks", (0, 2, 0): "planks"}), pet()
        gloom = hostile(grid, cell=(1, 2, 0))  # up on the wall, the roof's edge between it and Mimo
        self.assertEqual(act(gloom, scene(grid, state)), "chase")
        self.assertEqual((state["vitals"]["health"], gloom["state"]["pose"]), (100.0, "idle"))
        grid.put(0, 2, 0, "air")
        self.assertEqual(act(gloom, scene(grid, state, at=12.0)), "strike")
        self.assertEqual(state["vitals"]["health"], 97.0)

    def test_no_blow_reaches_mimo_inside_its_shelter(self):
        grid, state = meadow(), pet()
        grid.herd.db.execute("INSERT INTO structure_cells(x,y,z,structure,part,block) VALUES (0,1,0,1,'room','air')")
        gloom = hostile(grid, cell=(1, 1, 0))  # in a window gap, say
        self.assertEqual(act(gloom, scene(grid, state)), "chase")
        self.assertEqual(state["vitals"]["health"], 100.0)

    def test_a_dead_mimo_is_left_alone(self):
        grid, state = meadow(), pet(vitals={**START_VITALS, "health": 0.0})
        gloom = hostile(grid, cell=(1, 1, 0))
        self.assertEqual(act(gloom, scene(grid, state)), "prowl")
        self.assertEqual(state["vitals"]["health"], 0.0)


class SunlightTests(unittest.TestCase):
    def test_by_day_a_gloomling_under_the_sky_burns_then_goes_without_drops(self):
        grid, state = meadow(), pet()
        gloom = hostile(grid, cell=(1, 1, 0))
        self.assertEqual(act(gloom, scene(grid, state, clock=DAY)), "sunlit")
        self.assertEqual((gloom["state"]["pose"], gloom["state"]["burning_at"], gloom["next_at"]),
                         ("burning", 10.0, 10.0 + BURN_SECONDS))
        self.assertEqual(state["vitals"]["health"], 100.0)  # a burning gloomling strikes no more
        act(gloom, scene(grid, state, at=gloom["next_at"], clock=DAY))
        self.assertTrue(dead(gloom))
        self.assertEqual((gloom["health"], gloom["state"]["drops"], gloom["state"]["dead_at"]), (0.0, [], 13.0))

    def test_a_skitter_in_the_open_fades_at_once_and_a_roof_keeps_both_from_the_sun(self):
        grid, state = meadow({(5, 4, 0): "planks", (6, 4, 0): "planks"}), pet()
        skitter = hostile(grid, "skitter", (9, 1, 0))
        act(skitter, scene(grid, state, clock=DAY))
        self.assertTrue(dead(skitter))
        for kind, cell in (("skitter", (5, 1, 0)), ("gloomling", (6, 1, 0))):
            covered = hostile(grid, kind, cell)
            self.assertEqual(act(covered, scene(grid, state, clock=DAY)), "chase")
        self.assertNotEqual(act(hostile(grid, cell=(9, 1, 0)), scene(grid, state)), "sunlit")  # at night


class FightingBackTests(unittest.TestCase):
    def test_a_hostile_mimo_kills_leaves_its_drops_and_is_no_hunt(self):
        grid, state = meadow(), pet(inventory={"iron_sword": 1})
        skitter = hostile(grid, "skitter", (2, 1, 0))
        skitter["health"] = 5.0
        grid.herd.save(skitter)
        step = start_step({"kind": "attack", "creature": skitter["id"]}, state, grid, 10.0)
        self.assertEqual(finish_step(step, state, grid, 10.5), ("fight", "Pip fought off a skitter."))
        self.assertEqual(state["inventory"], {"iron_sword": 1, **drops_of("5", skitter, KINDS["skitter"])})
        self.assertNotIn("hunted_at", state)
        self.assertTrue(dead(grid.herd.get(skitter["id"])))


if __name__ == "__main__":
    unittest.main()
