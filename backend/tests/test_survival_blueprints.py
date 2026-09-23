import math
import unittest

from backend.services.blocks import is_solid
from backend.survival.blueprints import (
    DOOR_SIDES, FITTINGS, KEEP_OPEN, ROOFS, STRUCTURAL, TIERS, Style, bill, design_farm, design_shelter, find_site,
    from_data, pick_block, shelter, style_for, supplies,
)
from backend.survival.grid import Grid
from backend.survival.steps import REACH
from backend.survival.vitals import is_sheltered

SEED = "12345"


def meadow(cells=None):
    """Grass at y 0 (dirt below, air above), with `cells` placed the way Mimo placed them."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (cells or {}).items():
        grid.put(*cell, block)
    return grid


def built(grid, design):
    """Put every floor, wall and roof block and the bed of `design` into `grid`."""
    for planned in design.cells:
        if planned.part in STRUCTURAL and not is_solid(grid.material(*planned.cell)):
            grid.put(*planned.cell, "cobblestone")
        elif planned.part == "bed":
            grid.put(*planned.cell, "bed")
    return grid


def one_shelter(roof="flat", size=(3, 3), side="north", grid=None):
    grid = grid or meadow()
    site = find_site(grid, (1, 1, 1), size, (side,), roof, reach=0)
    return grid, shelter(site, Style(roof, "cobblestone", "planks", "sides", (side,)), "Pip's Hut")


class StyleTests(unittest.TestCase):
    def test_the_same_traits_and_seed_always_give_the_same_style(self):
        traits = {"creativity": 70, "thrift": 20}
        self.assertEqual(style_for(traits, SEED, 0), style_for(traits, SEED, 0))
        self.assertEqual(sorted(style_for(traits, SEED, 0).doors), sorted(DOOR_SIDES))

    def test_thrift_prefers_cobblestone_walls_and_creativity_fancier_roofs(self):
        self.assertEqual(style_for({"thrift": 80}, SEED).wall, "cobblestone")
        self.assertEqual(style_for({"thrift": 20}, SEED).wall, "planks")
        dull = [style_for({"creativity": 0}, str(seed)) for seed in range(40)]
        bold = [style_for({"creativity": 100}, str(seed)) for seed in range(40)]
        self.assertEqual({style.roof for style in dull}, {"flat"})
        self.assertEqual({style.windows for style in dull}, {"none"})
        self.assertEqual({style.roof for style in bold}, {"gable", "dome"})
        self.assertEqual({style.windows for style in bold}, {"sides"})

    def test_logs_count_as_planks_and_any_block_stands_in_for_a_missing_one(self):
        self.assertEqual(supplies({"oak_log": 4, "planks": 1, "dirt": 3, "berries": 5}), {"planks": 9, "dirt": 3})
        self.assertEqual(supplies({"oak_log": 2}), {})  # a campfire's worth of logs is kept
        self.assertEqual(pick_block("planks", {"planks": 2}), "planks")
        self.assertEqual(pick_block("planks", {"dirt": 2, "cobblestone": 1}), "cobblestone")
        self.assertIsNone(pick_block("planks", {}))


class ShelterTests(unittest.TestCase):
    def test_every_inside_cell_of_every_design_passes_the_shelter_check(self):
        for roof in ROOFS:
            for size in TIERS:
                for side in DOOR_SIDES:
                    grid, design = one_shelter(roof, size, side)
                    built(grid, design)
                    for stand in design.stands:
                        self.assertTrue(is_sheltered(grid.material, *stand), (roof, size, side, stand))
                    bed = design.one("bed")
                    self.assertTrue(is_sheltered(grid.material, bed[0], bed[1] + 1, bed[2]), (roof, size, side))

    def test_mimo_builds_everything_from_inside_without_scaffolding(self):
        for roof in ROOFS:
            for size in TIERS:
                _, design = one_shelter(roof, size)
                for planned in design.parts(*STRUCTURAL, "bed", "chest", "campfire"):
                    self.assertTrue(any(math.dist(stand, planned.cell) <= REACH for stand in design.stands),
                                    (roof, size, planned))

    def test_the_order_is_floor_walls_roof_then_fittings_with_the_door_and_way_in_left_open(self):
        _, design = one_shelter(size=(3, 3))
        parts = [planned.part for planned in design.cells if planned.part in STRUCTURAL + FITTINGS]
        self.assertEqual(parts[:28], ["wall"] * 28)  # 32 wall cells less the 2-block door and 2 windows
        self.assertEqual(parts[28:37], ["roof"] * 9)
        self.assertEqual(parts[37:], ["bed", "campfire", "chest", "torch", "torch", "torch", "torch"])
        self.assertEqual(design.anchor, (1, 1, 1))
        self.assertEqual(design.front, (1, 1, -2))
        self.assertEqual([planned.cell for planned in design.parts("door")], [(1, 1, -1), (1, 2, -1)])
        self.assertEqual([planned.cell for planned in design.parts(*KEEP_OPEN)],
                         [(1, 1, -1), (1, 2, -1), (1, 1, -2), (1, 2, -2), (1, 1, 0), (1, 1, 1)])
        self.assertEqual(bill(design), 37)

    def test_a_gable_roof_rises_to_a_ridge_and_closes_its_ends(self):
        grid, design = one_shelter("gable", (5, 4))  # inside x -1..3, z 0..3, floor 0
        heights = {planned.cell[0]: planned.cell[1] for planned in design.parts("roof")}
        self.assertEqual(heights, {-1: 3, 0: 4, 1: 5, 2: 4, 3: 3})
        ends = [planned.cell for planned in design.parts("wall") if planned.cell[1] >= 3]
        self.assertEqual(sorted(ends), [(0, 3, -1), (0, 3, 4), (1, 3, -1), (1, 3, 4), (1, 4, -1), (1, 4, 4),
                                        (2, 3, -1), (2, 3, 4)])

    def test_a_low_ring_column_gets_a_floor_block_and_a_bump_serves_as_wall(self):
        dug = meadow({(-1, 0, 2): "air"})  # dug out by Mimo under the west wall: not a site
        self.assertIsNone(find_site(dug, (1, 1, 1), (3, 3), ("north",), "flat", reach=0))
        natural = Grid(lambda x, y, z: "grass" if (y == 0 and (x, z) != (-1, 2)) or (y == -1 and (x, z) == (-1, 2))
                       or (y == 1 and (x, z) == (3, 0)) else "dirt" if y < 0 else "air")
        site = find_site(natural, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Hut")
        self.assertIn((-1, 0, 2), [planned.cell for planned in design.parts("floor")])
        self.assertIn(("wall", "natural"), [(planned.part, planned.block) for planned in design.cells
                                            if planned.cell == (3, 1, 0)])
        self.assertEqual(bill(design, natural), 30 + 9 + 1 - 1)  # walls less the door, roof, a floor block, the bump

    def test_sites_keep_off_farmland_saplings_water_stairs_and_what_mimo_built(self):
        for cells in ({(0, 0, 0): "farmland"}, {(2, 1, 1): "sapling"}, {(1, 1, 1): "water"},
                      {(3, 0, 0): "air"}, {(0, 1, 2): "cobblestone"}):
            grid = meadow(cells)
            self.assertIsNone(find_site(grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0), cells)
        claimed = meadow()
        claimed.claims.add((1, 1, 1))
        self.assertIsNone(find_site(claimed, (1, 1, 1), (3, 3), ("north",), "flat", reach=0))
        self.assertIsNotNone(find_site(meadow(), (1, 1, 1), (3, 3), ("north",), "flat", reach=0))

    def test_never_beside_a_dug_column_so_a_staircase_keeps_its_way_out(self):
        stair = meadow({(-2, 0, 1): "air", (-2, -1, 1): "air"})
        self.assertIsNone(find_site(stair, (1, 1, 1), (3, 3), ("north",), "flat", reach=0))
        site = find_site(stair, (1, 1, 1), (3, 3), ("north",), "flat", reach=3)
        self.assertIsNotNone(site)
        self.assertGreater(site.origin[0], -1)

    def test_a_design_is_deterministic_and_survives_json(self):
        traits = {"creativity": 90, "thrift": 30}
        first = design_shelter(meadow(), SEED, (1, 1, 1), traits, {"cobblestone": 90}, "Pip")
        again = design_shelter(meadow(), SEED, (1, 1, 1), traits, {"cobblestone": 90}, "Pip")
        self.assertEqual(first, again)
        self.assertEqual(from_data(first.to_data()), first)
        self.assertTrue(first.name.startswith("Pip's "))

    def test_the_tier_grows_with_creativity_and_the_blocks_carried(self):
        rich = {"cobblestone": 200}
        self.assertEqual(design_shelter(meadow(), SEED, (1, 1, 1), {"creativity": 90}, rich, "Pip").style["size"], [5, 4])
        self.assertEqual(design_shelter(meadow(), SEED, (1, 1, 1), {"creativity": 90}, {"dirt": 5}, "Pip").style["size"],
                         [3, 3])
        self.assertEqual(design_shelter(meadow(), SEED, (1, 1, 1), {"creativity": 10}, rich, "Pip").style["size"], [3, 3])


class FarmTests(unittest.TestCase):
    def test_a_new_farm_is_the_nearest_flat_tillable_square(self):
        design = design_farm(meadow({(0, 0, 0): "sand"}), (0, 0, 0), 3, "Pip")
        self.assertEqual(len(design.cells), 9)
        self.assertEqual({planned.part for planned in design.cells}, {"plot"})
        self.assertNotIn((0, 0, 0), [planned.cell for planned in design.cells])
        self.assertTrue(all(planned.cell[1] == 0 for planned in design.cells))

    def test_an_old_farm_grows_into_the_square_instead_of_a_second_farm(self):
        tilled = ((5, 0, 5), (6, 0, 5), (7, 0, 5))
        grid = meadow({cell: "farmland" for cell in tilled})
        design = design_farm(grid, (5, 0, 5), 3, "Pip", tilled)
        cells = [planned.cell for planned in design.cells]
        self.assertTrue(all(cell in cells for cell in tilled))


if __name__ == "__main__":
    unittest.main()
