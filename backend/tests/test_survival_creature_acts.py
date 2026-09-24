import math
import sqlite3
import unittest

from backend.survival.creatures.acts import (
    CALM_SECONDS, CREATURE_ACTIONS, FLEE_BLOCKS, LEASH, CreatureAction, Scene, act, register_action, run_away,
)
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.moves import roll, steps, timed, where
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables
from backend.survival.grid import Grid

POND = {(x, z) for x in range(4, 7) for z in range(-1, 2)}


def meadow(blocks=None):
    """Grass at y 0 with a pond at x 4..6, z -1..1 (water at y 0), and `blocks` placed."""
    blocks = blocks or {}

    def natural(x, y, z):
        if (x, y, z) in blocks:
            return blocks[(x, y, z)]
        if y == 0:
            return "water" if (x, z) in POND else "grass"
        return "dirt" if y < 0 else "air"
    return Grid(natural)


def herd():
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    return Herd(db)


def pet(x=30, purpose=None):
    return {"name": "Pip", "position": {"x": float(x), "y": 1.0, "z": 0.0}, "brain": {"purpose": purpose}}


def scene(grid, creatures, at=0.0, **changes):
    return Scene(grid, creatures, "7", changes.pop("state", pet()), at, events=changes.pop("events", []), **changes)


def animal(creatures, kind="cow", cell=(0, 1, 0), **state):
    return creatures.add(kind, cell, KINDS[kind].health, 0.0, 0.0, {"home": list(cell), "turn": 0, **state})


class MoveTests(unittest.TestCase):
    def test_land_steps_follow_mimos_rules_and_never_go_onto_water(self):
        grid = meadow({(1, 1, 0): "stone", (0, 1, 1): "stone", (0, 2, 1): "stone"})
        self.assertEqual(sorted(steps(grid, (0, 1, 0), False)), [(-1, 1, 0), (0, 1, -1), (1, 2, 0)])
        self.assertNotIn((4, 1, 0), steps(grid, (3, 1, 0), False))  # the pond's surface
        self.assertEqual(sorted(steps(grid, (5, 0, 0), True)), [(4, 0, 0), (5, 0, -1), (5, 0, 1), (6, 0, 0)])

    def test_steps_keep_out_of_what_mimo_built_or_means_to(self):
        grid = meadow()
        grid.claims.update({(1, 1, 0), (0, 1, 1), (5, 0, 1)})  # a shelter's door, a wall to be, a claimed pond cell
        self.assertEqual(sorted(steps(grid, (0, 1, 0), False)), [(-1, 1, 0), (0, 1, -1)])
        self.assertEqual(sorted(steps(grid, (5, 0, 0), True)), [(4, 0, 0), (5, 0, -1), (6, 0, 0)])

    def test_steps_still_leave_ground_a_creature_already_stands_on_that_became_claimed(self):
        grid = meadow()
        # a shelter blueprint starts under the cow: its cell and every neighbour are claimed
        grid.claims.update({(0, 1, 0), (1, 1, 0), (-1, 1, 0), (0, 1, 1), (0, 1, -1)})
        self.assertEqual(sorted(steps(grid, (0, 1, 0), False)), [(-1, 1, 0), (0, 1, -1), (0, 1, 1), (1, 1, 0)])
        grid.claims.update({(5, 0, 0), (5, 0, -1), (5, 0, 1), (4, 0, 0), (6, 0, 0)})  # same, for a fish in the pond
        self.assertEqual(sorted(steps(grid, (5, 0, 0), True)), [(4, 0, 0), (5, 0, -1), (5, 0, 1), (6, 0, 0)])

    def test_a_move_is_a_timed_path_and_where_follows_it(self):
        path = timed((0, 1, 0), [(1, 1, 0), (2, 1, 0)], 10.0, 0.5)
        self.assertEqual([entry["at"] for entry in path], [10.0, 10.5, 11.0])
        creature = {"x": 2.0, "y": 1.0, "z": 0.0, "state": {"path": path}}
        self.assertEqual([where(creature, at) for at in (9.0, 10.2, 10.5, 12.0)],
                         [(0, 1, 0), (0, 1, 0), (1, 1, 0), (2, 1, 0)])
        self.assertEqual(where({"x": 3.0, "y": 1.0, "z": 3.0, "state": {}}, 0.0), (3, 1, 3))

    def test_rolls_are_fixed_by_the_seed_the_creature_its_turn_and_the_channel(self):
        self.assertEqual(roll("7", 4, 2, 40), roll("7", 4, 2, 40))
        self.assertEqual(len({roll("7", 4, 2, 40), roll("8", 4, 2, 40), roll("7", 5, 2, 40), roll("7", 4, 3, 40),
                              roll("7", 4, 2, 41)}), 5)


class ActTests(unittest.TestCase):
    def test_wandering_stays_standable_dry_and_within_twelve_blocks_of_home(self):
        grid, creatures = meadow({(2, 1, 2): "stone", (-3, 1, 1): "stone", (-3, 2, 1): "stone"}), herd()
        cow = animal(creatures)
        at, seen = 0.0, set()
        for _ in range(300):
            at = max(at, cow["next_at"])
            seen.add(act(cow, scene(grid, creatures, at)))
            for entry in cow["state"].get("path") or []:
                cell = (entry["x"], entry["y"], entry["z"])
                self.assertTrue(grid.standable(cell) and not grid.swimming(cell), cell)
                self.assertLessEqual(math.hypot(cell[0], cell[2]), LEASH)
        self.assertEqual(seen, {"graze", "wander", "idle"})
        self.assertEqual(cow["state"]["turn"], 300)

    def test_animals_never_wander_or_flee_into_a_shelter_mimo_is_building(self):
        grid, creatures = meadow(), herd()
        room = {(x, 1, z) for x in range(-3, 4) for z in range(2, 7)}  # room, door, passage and walls to be
        grid.claims.update(room)
        cow = animal(creatures, cell=(0, 1, 0))
        at = 0.0
        for turn in range(300):
            at = max(at, cow["next_at"])
            hunted = turn % 7 == 0
            act(cow, scene(grid, creatures, at, state=pet(0 if hunted else 30, "hunt" if hunted else None)))
            for entry in cow["state"].get("path") or []:
                self.assertNotIn((entry["x"], entry["y"], entry["z"]), room)

    def test_a_creature_inside_a_claimed_room_still_wanders_or_flees_out(self):
        grid, creatures = meadow(), herd()
        room = {(x, 1, z) for x in range(-2, 3) for z in range(-2, 3)}  # a shelter blueprint starts under the cow
        grid.claims.update(room)
        cow = animal(creatures, cell=(0, 1, 0))
        at, moved = 0.0, False
        for turn in range(300):
            at = max(at, cow["next_at"])
            hunted = turn % 7 == 0
            act(cow, scene(grid, creatures, at, state=pet(0 if hunted else 30, "hunt" if hunted else None)))
            if cow["state"].get("path"):
                moved = True
            if cell_of(cow) not in room:
                break
        self.assertTrue(moved)  # it was never stuck with no neighbours to step to
        self.assertNotIn(cell_of(cow), room)  # and it made it out

    def test_an_animal_that_strayed_past_its_leash_heads_home(self):
        grid, creatures = meadow(), herd()
        cow = animal(creatures, cell=(0, 1, 20), home=[0, 1, 0])
        for turn in range(40):
            cow["state"]["turn"] = turn
            act(cow, scene(grid, creatures, float(turn * 10)))
            if cow["state"].get("path"):
                break
        path = cow["state"]["path"]
        self.assertLess(math.hypot(path[-1]["x"], path[-1]["z"]), 20)

    def test_flee_runs_about_eight_blocks_away_at_double_speed_then_calms(self):
        grid, creatures = meadow(), herd()
        cow = animal(creatures, cell=(-10, 1, 0))
        run_away(cow, KINDS["cow"], scene(grid, creatures, 100.0), (-9, 1, 0))
        path = cow["state"]["path"]
        self.assertEqual(len(path), FLEE_BLOCKS + 1)
        distances = [math.hypot(entry["x"] + 9, entry["z"]) for entry in path]
        self.assertEqual(distances, sorted(distances))
        self.assertAlmostEqual(path[1]["at"] - path[0]["at"], KINDS["cow"].speed / 2)
        self.assertEqual((cell_of(cow), cow["state"]["pose"]), ((path[-1]["x"], 1, path[-1]["z"]), "fleeing"))
        self.assertAlmostEqual(cow["state"]["calm_until"], path[-1]["at"] + CALM_SECONDS)
        self.assertGreater(cow["next_at"], path[-1]["at"])

    def test_a_hunting_mimo_close_by_scares_animals_but_not_fish_and_not_twice_in_a_row(self):
        grid, creatures = meadow(), herd()
        cow, fish = animal(creatures, cell=(26, 1, 0)), animal(creatures, "fish", (5, 0, 0))
        self.assertNotEqual(act(dict(cow), scene(grid, creatures, 0.0)), "flee")  # Mimo is not hunting
        hunting = pet(30, "hunt")
        self.assertEqual(act(cow, scene(grid, creatures, 0.0, state=hunting)), "flee")
        self.assertNotEqual(act(cow, scene(grid, creatures, cow["next_at"], state=pet(cell_of(cow)[0] + 2, "hunt"))),
                            "flee")  # calm for a while
        self.assertEqual(act(fish, scene(grid, creatures, 0.0, state=pet(5, "hunt"))), "swim")

    def test_fish_only_swim_through_water(self):
        grid, creatures = meadow(), herd()
        fish = animal(creatures, "fish", (5, 0, 0))
        at = 0.0
        for _ in range(50):
            at = max(at, fish["next_at"])
            act(fish, scene(grid, creatures, at))
            self.assertEqual(fish["state"]["pose"], "swimming")
            for entry in fish["state"]["path"]:
                self.assertTrue(grid.water((entry["x"], entry["y"], entry["z"])))

    def test_the_same_world_does_the_same_thing_and_the_pace_shortens_every_wait(self):
        grid = meadow()
        runs = []
        for pace in (1.0, 1.0, 10.0):
            creatures = herd()
            cow = animal(creatures)
            for turn in range(20):
                act(cow, scene(grid, creatures, float(turn * 10), pace=pace))
            runs.append((cell_of(cow), cow["next_at"] - 190.0))
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[2][0], runs[0][0])
        self.assertAlmostEqual(runs[2][1], runs[0][1] / 10, places=2)

    def test_a_dead_creature_or_an_unknown_kind_does_nothing(self):
        grid, creatures = meadow(), herd()
        self.assertIsNone(act(animal(creatures, pose="dead"), scene(grid, creatures)))
        stranger = animal(creatures)
        stranger["kind"] = "dragon"
        self.assertIsNone(act(stranger, scene(grid, creatures)))

    def test_a_scene_always_says_where_its_events_go(self):
        with self.assertRaises(TypeError):
            Scene(meadow(), herd(), "7", pet(), 0.0)
        events = []
        self.assertIs(Scene(meadow(), herd(), "7", pet(), 0.0, 2.0, events=events).events, events)

    def test_a_new_action_registers_in_priority_order_and_comes_first(self):
        grid, creatures = meadow(), herd()
        sit = register_action(CreatureAction("test_sit", 0, lambda creature, kind, scene: True,
                                             lambda creature, kind, scene: creature["state"].update(pose="sitting")))
        try:
            self.assertEqual(CREATURE_ACTIONS[0], sit)
            cow = animal(creatures)
            self.assertEqual((act(cow, scene(grid, creatures)), cow["state"]["pose"]), ("test_sit", "sitting"))
        finally:
            CREATURE_ACTIONS.remove(sit)


if __name__ == "__main__":
    unittest.main()
