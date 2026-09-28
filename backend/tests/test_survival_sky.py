"""W2: the seasons: the season day from the day and the offset, an old world's spring, warmth by season, the
turn of a season, autumn's warning and the sky in /api/mimo."""

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.survival.brain import BRAIN
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.sky import (
    SEASONS, next_season_at, season_at, season_day_of, season_of, settle_sky, sky_view, tend_season,
)
from backend.survival.snapshot import survival_view
from backend.survival.tick import tick_life
from backend.survival.vitals import target_warmth
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0
SCALE = 60.0


def day_start(day: int) -> float:
    """Server time of the dawn that starts game day `day` (scale 60)."""
    return BORN + (day - 1) * DAY_SECONDS / SCALE


def context(events: list):
    return SimpleNamespace(events=events, clock_at=lambda at: clock_at(BORN, at, SCALE), db=None)


class Lives:
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")

    def hatch(self, seed=8):
        life = hatch(self.registry, random.Random(seed), timestamp=BORN)
        return life, SurvivalWorld(self.registry.world_path(life))


class SeasonTests(unittest.TestCase):
    def test_a_year_is_forty_days_of_four_seasons_from_the_day_and_the_offset(self):
        self.assertEqual([season_of(season_day_of(day, 0)) for day in (1, 10, 11, 21, 31, 40, 41)],
                         ["spring", "spring", "summer", "autumn", "winter", "winter", "spring"])
        self.assertEqual(season_day_of(31, 0), 30)
        self.assertEqual(season_day_of(20, 21), 0)
        self.assertEqual(SEASONS, ("spring", "summer", "autumn", "winter"))

    def test_an_old_worlds_first_tick_makes_its_day_spring_day_one_and_winter_comes_thirty_days_later(self):
        state = {"born_at": BORN}
        at = day_start(20) + 100 / SCALE
        settle_sky(state, at, SCALE)
        self.assertEqual(season_at(state, at, SCALE), ("spring", 0))
        self.assertEqual(next_season_at(state, at, SCALE, "winter"), day_start(50))
        settled = dict(state["sky"])
        settle_sky(state, day_start(30), SCALE)  # once only
        self.assertEqual(state["sky"], settled)

    def test_a_newborn_starts_on_spring_day_one(self):
        lives = Lives()
        self.addCleanup(lives.directory.cleanup)
        _, world = lives.hatch()
        tick_life(lives.registry, BORN + 2, scale=SCALE, mind=BRAIN, action_scale=SCALE)
        sky = world.state()["sky"]
        self.assertEqual((sky["offset"], sky["season"], sky["season_day"]), (0, "spring", 0))
        self.assertEqual(next_season_at(world.state(), BORN + 2, SCALE, "winter"), day_start(31))

    def test_warmth_outdoors_follows_the_season_and_shelter_cloak_and_fire_add_to_it(self):
        table = {season: (target_warmth(False, "meadow", False, False, season),
                          target_warmth(True, "meadow", False, False, season)) for season in SEASONS}
        self.assertEqual(table, {"spring": (100.0, 30.0), "summer": (100.0, 45.0), "autumn": (85.0, 20.0),
                                 "winter": (45.0, -10.0)})
        self.assertEqual(target_warmth(True, "meadow", False, False), 30.0)  # spring is today's
        self.assertEqual(target_warmth(False, "alpine", False, False), 40.0)
        self.assertEqual(target_warmth(True, "alpine", False, False, "winter"), -60.0)
        self.assertEqual(target_warmth(True, "meadow", True, False, "winter"), 35.0)
        self.assertEqual(target_warmth(True, "meadow", True, False, "winter", cloak=True), 55.0)
        self.assertEqual(target_warmth(True, "meadow", False, False, "winter", snowing=True), -20.0)
        self.assertEqual(target_warmth(True, "meadow", True, False, "winter", snowing=True), 35.0)  # snow outdoors only
        self.assertEqual(target_warmth(True, "meadow", False, True, "winter", snowing=True), 100.0)


class TurnTests(unittest.TestCase):
    def tend(self, state, day, seconds, events):
        tend_season(state, context(events), day_start(day) + seconds / SCALE)

    def test_a_season_turns_at_its_first_dawn_and_springs_turn_is_news(self):
        state, events = {"born_at": BORN, "sky": {"offset": 0}}, []
        self.tend(state, 10, 3000, events)
        self.tend(state, 11, 0, events)
        self.assertEqual([(kind, text) for _, kind, text in events], [("season", "Summer has come.")])
        self.tend(state, 31, 0, events)
        self.tend(state, 41, 0, events)
        self.assertEqual([(kind, text) for _, kind, text in events][1:],
                         [("season", "Winter has come."), ("spring", "Spring! Things are growing again.")])
        self.assertEqual(state["last_thought"], "Spring! Things are growing again.")

    def test_on_autumn_day_three_at_dusk_the_nights_are_getting_colder_once(self):
        state, events = {"born_at": BORN, "sky": {"offset": 0}}, []
        self.tend(state, 23, 2000, events)
        self.assertEqual(events, [])
        self.tend(state, 23, 2300, events)
        self.tend(state, 23, 2500, events)
        self.assertEqual([(kind, text) for _, kind, text in events], [("colder", "The nights are getting colder.")])
        self.assertEqual(state["sky"]["season"], "autumn")


class OldWorldTests(unittest.TestCase):
    def setUp(self):
        self.lives = Lives()
        _, self.world = self.lives.hatch()

    def tearDown(self):
        self.lives.directory.cleanup()

    def test_a_world_from_before_w2_reads_a_default_sky_and_its_first_tick_sets_spring(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state.pop("sky", None)
            state["last_tick_at"] = day_start(20)
            write_state(db, state)
        view = survival_view(self.world, day_start(20), SCALE)["sky"]
        self.assertEqual((view["weather"], view["snow"], view["frozen"], view["strikes"]), ("clear", 0.0, False, []))
        self.assertNotIn("sky", self.world.state())  # a GET never writes
        tick_life(self.lives.registry, day_start(20) + 1, scale=SCALE, mind=BRAIN, action_scale=SCALE)
        sky = self.world.state()["sky"]
        self.assertEqual((sky["offset"], sky["season"], sky["season_day"]), (21, "spring", 0))
        view = survival_view(self.world, day_start(20) + 1, SCALE)["sky"]
        self.assertEqual((view["season"], view["day"], view["to_next"]), ("spring", 1, 10))

    def test_a_dead_pets_world_is_never_written(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state.pop("sky", None)
            state.update(died_at=BORN + 0.5, cause="starvation")
            write_state(db, state)
        tick_life(self.lives.registry, BORN + 5, scale=SCALE, mind=BRAIN, action_scale=SCALE)
        self.assertNotIn("sky", self.world.state())
        self.assertEqual(sky_view(self.world.state(), BORN + 5, SCALE)["season"], "spring")


if __name__ == "__main__":
    unittest.main()
