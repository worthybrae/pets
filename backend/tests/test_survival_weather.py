"""W2: the weather: a pure function of the seed, the season and the segment; what rain, snow and fog do."""

import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

from backend.survival import weather  # noqa: F401  (registers the walk pace and the fog's room)
from backend.survival.weather import FOG_ROOM
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.creatures.acts import slowed
from backend.survival.creatures.darkness import HOSTILE_CAP, cap, spawn_hostiles
from backend.survival.creatures.hostiles import sunlit
from backend.survival.creatures.kinds import KINDS
from backend.survival.renewal import CROP_STAGE_DRY, CROP_STAGE_WET, rained, stage_seconds
from backend.survival.sky import (
    LOOK_BACK, SEASONS, SEGMENT, TABLE, segment_season, sky_state, tend_weather, weather_at, weather_of,
)
from backend.survival.steps import start_step
from backend.survival.tick import surroundings_at
from backend.tests.test_survival_cooking import meadow
from backend.tests.test_survival_darkness import DAY, land, pet, scene

BORN = 1_000_000.0
SCALE = 60.0
SEED = "11"


def segment_where(seed, weather, season="spring", offset=0):
    """The first segment of `season` in the first year with `weather`."""
    return next(segment for segment in range(40 * 6)
                if segment_season(offset, segment) == season and weather_at(seed, offset, segment) == weather)


def at_segment(segment):
    return BORN + segment * SEGMENT / SCALE


def context(events=None):
    return SimpleNamespace(events=[] if events is None else events, clock_at=lambda at: clock_at(BORN, at, SCALE),
                           db=None)


class WeatherTests(unittest.TestCase):
    def test_the_weather_is_a_pure_function_that_keeps_spells(self):
        first = [weather_at(SEED, 0, segment) for segment in range(600)]
        self.assertEqual(first, [weather_at(SEED, 0, segment) for segment in range(600)])
        spells, run = [], 1
        for before, after in zip(first, first[1:]):
            if before == after:
                run += 1
            else:
                spells.append(run)
                run = 1
        self.assertGreaterEqual(sum(spells) / len(spells), 2.0)  # 20 game minutes or more on average

    def test_each_season_follows_its_table_over_ten_thousand_segments(self):
        for season in SEASONS:
            counts, segments = Counter(), 0
            for segment in range(40 * 6 * 170):
                if segment_season(0, segment) != season:
                    continue
                counts[weather_at(SEED, 0, segment)] += 1
                segments += 1
                if segments == 10_000:
                    break
            self.assertEqual(segments, 10_000)
            for kind, share in TABLE[season]:
                self.assertAlmostEqual(counts[kind] / segments, share, delta=0.02, msg=(season, kind))
            self.assertEqual(set(counts) - {kind for kind, _ in TABLE[season]}, set())  # no rain in winter

    def test_the_look_back_stops_and_a_weather_the_season_lacks_rolls_fresh(self):
        calls = []
        with patch("backend.survival.sky.roll", lambda seed, cell, channel, salt=0: calls.append(cell) or 0.0):
            weather_at(SEED, 0, 100)  # every roll keeps: it looks back LOOK_BACK segments and no further
        self.assertEqual(min(cell[0] for cell in calls), 100 - LOOK_BACK + 1)
        first_winter = 30 * 6
        self.assertNotIn(weather_at(SEED, 0, first_winter), ("rain", "storm"))
        self.assertTrue(all(weather_at(seed, 0, first_winter + step) not in ("rain", "storm")
                            for seed in map(str, range(40)) for step in range(3)))

    def test_the_tick_stores_the_weather_until_it_changes_and_the_snow_cover(self):
        state = {"born_at": BORN, "world_seed": SEED, "sky": {"offset": 0}}
        segment = segment_where(SEED, "rain")
        tend_weather(state, context(), at_segment(segment) + 1 / SCALE)
        sky = state["sky"]
        self.assertEqual(sky["weather"], "rain")
        until = round((sky["weather_until"] - BORN) * SCALE / SEGMENT)
        self.assertTrue(all(weather_at(SEED, 0, later) == "rain" for later in range(segment, until)))
        self.assertNotEqual(weather_at(SEED, 0, until), "rain")
        self.assertEqual(weather_of(state, at_segment(segment), SCALE), "rain")
        snowy = segment_where(SEED, "snow", "winter")
        snow = {"born_at": BORN, "world_seed": SEED, "sky": {"offset": 0, "season": "winter"}}
        tend_weather(snow, context(), at_segment(snowy))
        tend_weather(snow, context(), at_segment(snowy) + 300 / SCALE)
        self.assertAlmostEqual(snow["sky"]["snow"], 0.5)
        thaw = {"born_at": BORN, "world_seed": SEED, "sky": {"offset": 0, "season": "spring", "snow": 1.0}}
        clear = segment_where(SEED, "clear")
        tend_weather(thaw, context(), at_segment(clear))
        tend_weather(thaw, context(), at_segment(clear) + 600 / SCALE)
        self.assertAlmostEqual(thaw["sky"]["snow"], 0.5)


class RainAndSnowTests(unittest.TestCase):
    def walk_seconds(self, weather, roof=False):
        grid = meadow({(x, 4, 0): "stone" for x in range(-1, 12)} if roof else None)
        state = {"world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "sky": {"weather": weather}}
        step = start_step({"kind": "walk", "target": [10, 1, 0]}, state, grid, 0.0)
        return step["ends_at"]

    def test_rain_and_snow_slow_a_walk_under_the_open_sky(self):
        clear = self.walk_seconds("clear")
        self.assertAlmostEqual(self.walk_seconds("rain"), clear * 1.15, places=2)
        self.assertAlmostEqual(self.walk_seconds("storm"), clear * 1.15, places=2)
        self.assertAlmostEqual(self.walk_seconds("snow"), clear * 1.3, places=2)
        self.assertAlmostEqual(self.walk_seconds("fog"), clear, places=3)
        self.assertAlmostEqual(self.walk_seconds("rain", roof=True), clear, places=3)

    def test_rain_and_snow_slow_a_creature_under_the_open_sky_as_they_slow_mimo(self):
        with patch("backend.survival.light.terrain_height", lambda x, z, seed: 0):
            grid, state = land({(x, 4, 0): "stone" for x in range(8, 13)}), pet()
            out = grid.herd.add("gloomling", (3, 1, 0), 20.0, 0.0, 0.0, {})
            roofed = grid.herd.add("gloomling", (10, 1, 0), 20.0, 0.0, 0.0, {})
            for weather_now, pace in (("clear", 1.0), ("rain", 1.15), ("storm", 1.15), ("snow", 1.3), ("fog", 1.0)):
                state["sky"] = {"weather": weather_now}
                self.assertAlmostEqual(slowed(scene(grid, state), out), pace)
                self.assertEqual(slowed(scene(grid, state), roofed), 1.0)

    def test_a_crop_stage_that_starts_in_the_rain_grows_at_the_watered_rate(self):
        grid = meadow({(0, 0, 0): "farmland", (0, 1, 0): "wheat_0"})
        self.assertEqual(stage_seconds(grid, (0, 1, 0)), CROP_STAGE_DRY)
        self.assertEqual(stage_seconds(grid, (0, 1, 0), rain=True), CROP_STAGE_WET)
        state = {"born_at": BORN, "world_seed": SEED, "sky": {"offset": 0}}
        self.assertTrue(rained(state, at_segment(segment_where(SEED, "rain")), SCALE))
        self.assertFalse(rained(state, at_segment(segment_where(SEED, "clear")), SCALE))
        self.assertFalse(rained({}, 0.0, SCALE))

    def test_falling_snow_is_felt_outdoors(self):
        state = {"sky": {"season": "winter", "weather": "snow"}}
        with patch("backend.survival.tick.material_in", lambda db, x, y, z, seed: "air"), \
                patch("backend.survival.tick.placed_near", lambda db, position, reach, blocks: []):
            felt = surroundings_at(None, "1", {"x": 0.0, "y": 1.0, "z": 0.0}, state)
        self.assertEqual((felt.season, felt.snowing), ("winter", True))


class FogTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.survival.creatures.darkness.terrain_height", "backend.survival.light.terrain_height"):
            patcher = patch(target, lambda x, z, seed: 0)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_in_fog_the_dark_creatures_come_out_by_day_and_the_sun_spares_them(self):
        clear, foggy = pet(), {**pet(), "sky": {"weather": "fog"}}
        self.assertEqual(spawn_hostiles(scene(land(), clear, clock=DAY)), [])
        born = spawn_hostiles(scene(land(), foggy, clock=DAY))
        self.assertEqual([creature["kind"] for creature in born], ["gloomling"])
        gloomling = {**born[0], "state": dict(born[0]["state"])}
        self.assertFalse(sunlit(gloomling, KINDS["gloomling"], scene(land(), foggy, clock=DAY)))
        self.assertTrue(sunlit(gloomling, KINDS["gloomling"], scene(land(), clear, clock=DAY)))
        self.assertEqual(cap(scene(land(), foggy, clock=DAY)) - cap(scene(land(), clear, clock=DAY)), FOG_ROOM)  # 0
        self.assertEqual(cap(scene(land(), clear, clock=DAY)), HOSTILE_CAP)

    def test_a_torch_still_keeps_the_fog_clear(self):
        torches = {(x, 1, z): "torch" for x in range(-44, 45, 4) for z in range(-44, 45, 4)}
        foggy = {**pet(), "sky": {"weather": "fog"}}
        self.assertEqual(spawn_hostiles(scene(land(torches), foggy, clock=DAY)), [])


class StateTests(unittest.TestCase):
    def test_sky_state_fills_every_field(self):
        sky = sky_state({})
        self.assertEqual((sky["weather"], sky["snow"], sky["frozen"], sky["fires"]), ("clear", 0.0, False, []))
        self.assertEqual(DAY_SECONDS / SEGMENT, 6)


if __name__ == "__main__":
    unittest.main()
