"""W2: the seasons: the season day from the day and the offset, an old world's spring, warmth by season, the
turn of a season, autumn's warning and the sky in /api/mimo."""

import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.survival.brain import BRAIN
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival import sky_wild  # noqa: F401  (a wild pet names the seasons once it knows winter)
from backend.survival.sky import (
    SEASONS, UNNAMED, next_season_at, season_at, season_day_of, season_of, settle_sky, sky_view, tend_season,
)
from backend.survival.sky_news import season_news
from backend.survival.snapshot import survival_view
from backend.survival.tick import surroundings_at, tick_life
from backend.survival.ailments import CHILL_BELOW
from backend.survival.blueprints import Blueprint, Planned
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, know
from backend.survival.structures import start
from backend.survival.vitals import FREEZING_BELOW, HOME_FLOOR, target_warmth
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

    def test_the_next_first_dawn_of_a_season_counts_its_own_dawn(self):
        """Carried from W2's first task: at the very dawn of a season's first day, that dawn is the next one; a moment
        later the next is a year on."""
        state = {"born_at": BORN, "sky": {"offset": 0}}
        self.assertEqual(next_season_at(state, day_start(31), SCALE, "winter"), day_start(31))
        self.assertEqual(next_season_at(state, day_start(31) + 1 / SCALE, SCALE, "winter"), day_start(71))
        self.assertEqual(next_season_at(state, day_start(30) + 1 / SCALE, SCALE, "winter"), day_start(31))
        self.assertEqual(next_season_at(state, day_start(1), SCALE, "spring"), day_start(1))  # a newborn's own dawn

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

    def test_inside_the_home_it_built_a_pet_never_freezes_in_any_season_or_band(self):
        """Spec resolution 34 (W2's final review): sheltered in its home in the mountains, a pet's night was 15 in
        autumn and -15 in winter, under FREEZING_BELOW, so an alpine home froze its pet every night."""
        self.assertEqual(target_warmth(True, "alpine", True, False, "winter", at_home=True), HOME_FLOOR)
        self.assertEqual(target_warmth(True, "alpine", True, False, "autumn", at_home=True), HOME_FLOOR)
        self.assertEqual(target_warmth(True, "alpine", True, False, "winter"), -15.0)  # sheltered elsewhere: a cave
        self.assertEqual(target_warmth(True, "alpine", False, False, "winter", at_home=True), -60.0)  # outdoors
        self.assertEqual(target_warmth(True, "alpine", True, True, "winter", at_home=True), 100.0)  # by a hearth
        self.assertEqual(target_warmth(True, "meadow", True, False, "winter", at_home=True), 35.0)  # above it: as ever
        for season in SEASONS:
            for biome in ("meadow", "alpine"):
                for night in (False, True):
                    self.assertGreaterEqual(target_warmth(night, biome, True, False, season, at_home=True), HOME_FLOOR)
        self.assertTrue(FREEZING_BELOW < HOME_FLOOR < CHILL_BELOW)  # a winter night at home still chills

    def test_a_pet_in_a_room_of_the_shelter_it_built_is_at_home(self):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        room = Blueprint("shelter", "Pip's hut", (0, 1, 0), (Planned((0, 1, 0), "room", "air"),
                                                            Planned((0, 3, 0), "roof", "planks")))
        start(db, Grid(lambda x, y, z: "air"), room, 0.0)
        def hut(db, x, y, z, seed):  # a roof over the cell and its neighbours, walls two blocks off on four sides
            return "planks" if (y == 3 and abs(x) <= 1 and abs(z) <= 1) or (y == 1 and abs(x) + abs(z) == 2) else "air"

        felt = {}
        with patch("backend.survival.tick.material_in", hut), \
                patch("backend.survival.tick.placed_near", lambda db, position, reach, blocks: []):
            for name, cell in (("room", (0.0, 1.0, 0.0)), ("beside", (1.0, 1.0, 0.0))):
                felt[name] = surroundings_at(db, "1", dict(zip("xyz", cell)), {"sky": {"season": "winter"}})
        self.assertEqual([(felt[name].sheltered, felt[name].at_home) for name in ("room", "beside")],
                         [(True, True), (True, False)])


class TurnTests(unittest.TestCase):
    def tend(self, state, day, seconds, events, db=None):
        tend_season(state, SimpleNamespace(**{**vars(context(events)), "db": db}), day_start(day) + seconds / SCALE)

    def test_a_wild_pet_that_does_not_know_winter_meets_the_turns_without_their_names(self):
        """W2's final review: a wild pet that does not know `wild:winter` thought and posted "Winter has come." Its
        turns name no season, as the winter_food wonder names none, and winter's first day is news all the same."""
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        state, events = {"born_at": BORN, "sky": {"offset": 0}, "difficulty": "wild"}, []
        for day in (10, 11, 30, 31):
            self.tend(state, day, 0 if day % 10 == 1 else 3000, events, db)
        self.assertEqual([(kind, text) for _, kind, text in events],
                         [("season", "The days are long and warm now."), ("season", UNNAMED["winter"])])
        self.assertEqual(state["last_thought"], "The lakes are freezing and nothing grows any more.")
        self.assertFalse(any(name in text.lower() for _, _, text in events for name in SEASONS))
        with patch("backend.survival.sky_news.post_item") as posted:
            for _, kind, text in events:
                season_news(db, {"name": "Pip"}, {"kind": kind, "text": text, "at": BORN, "id": 1}, BORN, SCALE)
        self.assertEqual([call.args[3] for call in posted.call_args_list], [UNNAMED["winter"]])  # news, as named
        know(db, "wild:winter", "lesson", 0.0)
        self.tend(state, 40, 3000, events, db)
        self.tend(state, 41, 0, events, db)
        self.assertEqual(events[-1][1:], ("spring", "Spring! Things are growing again."))
        state["difficulty"] = "gentle"
        db.execute("DELETE FROM memory_knowledge")
        self.tend(state, 50, 3000, events, db)
        self.tend(state, 51, 0, events, db)
        self.assertEqual(events[-1][1:], ("season", "Summer has come."))  # a gentle pet knows them all

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
        # W2's final review: no year yet, so no season (it read as offset 0: day 20 was summer's last day)
        self.assertIsNone(survival_view(self.world, day_start(20), SCALE)["sky"])
        self.assertIsNone(sky_view({**self.world.state(), "sky": {"weather": "clear"}}, day_start(20), SCALE))
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
        # it died before any tick: a newborn's year (offset 0) is read, as its first tick would have set it
        self.assertEqual(sky_view(self.world.state(), BORN + 5, SCALE)["season"], "spring")
        self.assertIsNone(sky_view({**self.world.state(), "last_tick_at": BORN + 0.5}, BORN + 5, SCALE))  # it ticked


if __name__ == "__main__":
    unittest.main()
