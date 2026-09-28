"""Wild World's balance gate (docs/superpowers/specs/2026-09-27-wild-world-design.md, "Balance gates").

One life per process, headless, with no model: hatched with random.Random(seed) at BORN, gentle for the
`gentle` condition and wild for the others, ticked at scale 60 and action scale 60 (a tick per 60 game
seconds, like test_survival_days), with the worker's Chooser (the rules) and Talker (the rules) after every
tick. Their HTTP is a counting stand-in that refuses every call; any call fails the gate.

- `untaught`: nobody talks to Mimo.
- `taught`: the scripted owner says the first teaching-table line of each W1 lesson on day 1, one every
  OWNER_EVERY game minutes from minute 5 (talk.owner_says, the real chat), and answers each question Mimo asks
  within ANSWER_AFTER game minutes with its true chip (questions.answer_question, what the answer endpoint
  calls). It gives no care.
- `liar`: answers each question within ANSWER_AFTER game minutes with a false chip, or with the wonder's false
  claim in the chat when it has none. It teaches nothing else.

Each life writes a JSON summary to --out: its death day and cause, sick game minutes (and by day), the health
it lost to its hazards (`state["wild"]["lost"]`: a sickness's or a festering wound's drain, a poison plant; and
by day), wounds and festering minutes, near-death days (health under 20 at least once), the time-weighted health
mean, freezing and starving minutes, the lessons it knows with their sources and days, the wonders it met and the questions it
asked in its first 3 game days and the most open at once, the machines it built by day, whether it ever had a
sickness, a wound, a lot or a question, logged errors and model calls. The wonders and questions are recorded as
the life runs, each minute: by day 150 the inbox has pruned the early questions (Fix B).

    python3 -m backend.scripts.wild_gate --seed 8 --days 3 --condition untaught --out DIR
    python3 -m backend.scripts.wild_gate --days 150 --conditions gentle,untaught,taught --parallel 6 --out DIR
    python3 -m backend.scripts.wild_gate --check W1 DIR

The robustness check W1R (criterion 8R) runs 12 untaught lives on seeds outside the gate's six, for 30 game days:

    python3 -m backend.scripts.wild_gate --seeds 1,2,4,6,7,9,10,12,13,14,15,16 --days 30 --conditions untaught --parallel 4 --out DIR
    python3 -m backend.scripts.wild_gate --check W1R DIR

W2: the scripted owner says the first teaching-table line of each W2 lesson on day 2, the same way (TEACHES_W2).
Each life's summary gains its winters (`winters`: the health mean, freezing and starving game minutes of each,
days 31 to 40, 71 to 80 and 111 to 120 of a newborn), the food its chests hold for winter on each winter day 1
(`winter_food`: winter_prep.winter_food of the food still good that day, the controller's ruling on the W2 dry
run and its gate, the goal's own measure too), the strikes that hit it and the nearest a strike fell to the home it
built at that moment (`strike_home`, from storms.STRIKES: a home finished later in the same tick is not the one the
strike kept clear of), the fire cells that burned in a cell something it built claims (`fire_claimed`) and the
block edits in the legacy clearing (`clearing_edits`). The `upgrade` condition is spec criterion 9's world: a
gentle life ticked UPGRADE_DAY days as the code before W2 had it (no sky), then upgraded and ticked 45 more.
Each winter also counts its cold minutes (warmth under ailments.CHILL_BELOW) and hungry minutes (hunger under
HUNGRY_WINTER); criterion 6 reads the cold ones (restated by the controller's ruling on the W2 interim report).

    python3 -m backend.scripts.wild_gate --days 150 --conditions gentle,untaught,taught --parallel 4 --out DIR
    python3 -m backend.scripts.wild_gate --days 65 --conditions upgrade --parallel 4 --out DIR
    python3 -m backend.scripts.wild_gate --check W2 DIR
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BORN = 1_000_000.0
SCALE = 60.0
SEEDS = (3, 5, 8, 11, 21, 42)
# W1R (criterion 8R): the promise of criterion 8 on seeds outside the gate's own, untaught, for R_DAYS game days
R_SEEDS = (1, 2, 4, 6, 7, 9, 10, 12, 13, 14, 15, 16)
R_DAYS = 30
R_DEATHS_MOST = 4
CONDITIONS = ("gentle", "untaught", "taught", "liar")
UPGRADE = "upgrade"  # W2: a world made before W2 and upgraded (criterion 9)
OWNER_EVERY = 5  # game minutes between the scripted owner's lines on day 1
ANSWER_AFTER = 2  # game minutes after a question is asked that the owner answers it
NEAR_DEATH = 20.0
FIRST_MONTH = 30  # W1 criterion 6: a newborn's first month, game days 1 to 30
# The scripted owner's lines: the first line of the teaching table for each W1 lesson.
TEACHES = ("Red berries are safe to eat.", "Nightberries are the dark purple ones, and they are poison.",
           "Red mushrooms are poison.", "Sunleaf cures sickness and cleans wounds.",
           "A wool bandage stops a wound festering.", "Two logs and three sticks make a campfire.",
           "Cooked meat and fish are safe to eat.", "Food keeps twice as long in a chest.",
           "Torches keep the dark creatures away.", "A shelter with a roof and a door keeps you safe at night.",
           "Six planks make a bed.")
# W2: the first teaching-table line of each W2 lesson, said on day 2 the same way.
TEACHES_W2 = ("Fill a chest with food before winter.", "Five wool make a wool cloak.",
              "A stone hearth keeps the home warm.", "Smoked meat keeps all winter.",
              "Rain puts out a fire under the open sky.", "In a storm stay low and inside.",
              "Stay close to home in the fog.")
UPGRADE_DAY = 20  # criterion 9: the upgraded world's day when W2 comes


class Errors(logging.Handler):
    """Every warning or error the backend logs in a life."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(record.getMessage()[:300])


class NoModel:
    """A model stand-in that counts every call and refuses it."""

    def __init__(self):
        self.calls: list[str] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(url)
        raise RuntimeError("no model in the gate")


def true_chip(wonder, chips: list[str]) -> int:
    """The shown chip that teaches the most (the true answer)."""
    return max(range(len(chips)), key=lambda index: len(next(chip for chip in wonder.chips
                                                             if chip.words == chips[index]).teaches))


def false_chip(wonder, chips: list[str]) -> int | None:
    return next((index for index, words in enumerate(chips)
                 if next(chip for chip in wonder.chips if chip.words == words).false), None)


def owner(world, condition: str, minute: int, now: float, answered: set) -> None:
    """The scripted owner (taught) or the liar, at game minute `minute` of the life."""
    from backend.survival.questions import answer_question, questions_view
    from backend.survival.talk import owner_says
    from backend.survival.wonders import WONDERS
    if condition == "taught" and minute <= OWNER_EVERY * len(TEACHES) and minute % OWNER_EVERY == 0:
        owner_says(world, TEACHES[minute // OWNER_EVERY - 1], now, SCALE)
    later = minute - 60  # W2: day 2
    if condition == "taught" and 0 < later <= OWNER_EVERY * len(TEACHES_W2) and later % OWNER_EVERY == 0:
        owner_says(world, TEACHES_W2[later // OWNER_EVERY - 1], now, SCALE)
    if condition not in ("taught", "liar"):
        return
    with world.connect() as db:
        open_now = questions_view(db)
        asked = {row[0]: row[1] for row in db.execute("SELECT id, at FROM mimo_inbox WHERE kind='ask'")}
        wonders = {row[0]: row[1] for row in db.execute(
            "SELECT id, json_extract(data, '$.wonder') FROM mimo_inbox WHERE kind='ask'")}
    for question in open_now:
        if question["id"] in answered or (now - asked[question["id"]]) * SCALE < ANSWER_AFTER * 60:
            continue
        answered.add(question["id"])
        wonder = WONDERS[wonders[question["id"]]]
        if condition == "taught":
            answer_question(world, question["id"], true_chip(wonder, question["chips"]), now, SCALE)
        else:
            lie = false_chip(wonder, question["chips"])
            if lie is not None:
                answer_question(world, question["id"], lie, now, SCALE)
            elif wonder.lie:
                owner_says(world, wonder.lie, now, SCALE)


def live(seed: int, days: int, condition: str, http=None) -> dict:
    """One life; its summary. `http` stands in for every model call (a counting NoModel unless a test gives its own)."""
    from backend.survival import bonding, minding  # noqa: F401  (every Bond and Mind writer registers)
    from backend.survival.brain import BRAIN
    from backend.survival.choosing import Chooser, InlineExecutor
    from backend.survival.hatch import hatch
    from backend.survival.once import forget_logged
    from backend.survival.registry import LifeRegistry
    from backend.survival.talker import Talker
    from backend.survival.tick import tick_life
    from backend.survival.world import SurvivalWorld

    forget_logged()
    errors = Errors()
    logging.getLogger("backend").addHandler(errors)
    started = time.time()
    with tempfile.TemporaryDirectory() as root:
        registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
        life = hatch(registry, random.Random(seed), timestamp=BORN,
                     difficulty="gentle" if condition in ("gentle", UPGRADE) else "wild")
        world = SurvivalWorld(registry.world_path(life))
        model = http or NoModel()
        chooser = Chooser(env={}, http=model, executor=InlineExecutor(), rng=random.Random(seed), scale=SCALE)
        talker = Talker(env={}, http=model, scale=SCALE)
        answered: set = set()
        found = new_record()
        state = world.state()
        from backend.survival import storms
        seen = strike_seen(found)
        storms.STRIKES.append(seen)
        try:
            for minute in range(1, days * 60 + 1):
                now = BORN + minute
                if condition == UPGRADE and minute == UPGRADE_DAY * 60:
                    upgrade(world)  # W2 comes to a world that lived UPGRADE_DAY days without it
                with before_w2(condition == UPGRADE and minute < UPGRADE_DAY * 60):
                    state = tick_life(registry, now, scale=SCALE, mind=BRAIN, action_scale=SCALE)
                if state is None or state["died_at"] is not None:
                    break
                chooser.poll(registry, now)
                owner(world, condition, minute, now, answered)
                talker.poll(registry, now)
                sample(found, state, minute, world)
                sample_sky(found, state, minute, world)
        finally:
            storms.STRIKES.remove(seen)  # never left on the global list, even when a life crashes
        talker.close()
        summary = summarize(world, found, seed, days, condition, time.time() - started)
    summary.update(errors=errors.records[:50], model_calls=len(getattr(model, "calls", [])))
    logging.getLogger("backend").removeHandler(errors)
    return summary


def new_record() -> dict:
    """What `sample` keeps over a life, empty."""
    return {"health": 0.0, "ticks": 0, "sick": 0, "sick_by_day": [], "lost_by_day": [], "wounds": 0, "festering": 0,
            "near": set(), "freezing": 0, "starving": 0, "open_most": 0,
            "ever": {"sick": False, "wound": False, "lots": False}, "asked": {}, "met": {}}


def before_w2(active: bool):
    """While `active`, the tick runs as the code before W2 did: no sky at all (criterion 9's old world)."""
    from contextlib import ExitStack
    from unittest.mock import patch
    stack = ExitStack()
    if active:
        stack.enter_context(patch("backend.survival.tick.sky.advance", lambda state, context, at: None))
        stack.enter_context(patch("backend.survival.tick.sky.settle_sky", lambda state, at, scale: None))
    return stack


def upgrade(world) -> None:
    """The old world's state loses what W2 would have written (it had none): its next tick is its first W2 tick."""
    from backend.survival.world import read_state, write_state
    with world.transaction() as db:
        state = read_state(db)
        state.pop("sky", None)
        write_state(db, state)


HUNGRY_WINTER = 30.0  # a winter's hungry minutes: hunger under this


def winter_of(found: dict, state: dict, minute: int) -> int | None:
    """Which of the life's winters (1, 2, 3 ...) the game minute falls in, by its own seasons (an upgraded world's
    year starts on its upgrade day), or None outside winter."""
    from backend.survival.sky import YEAR_DAYS, season_at
    if "offset" not in (state.get("sky") or {}) or season_at(state, BORN + minute, SCALE)[0] != "winter":
        return None
    year = ((minute - 1) // 60 + state["sky"]["offset"]) // YEAR_DAYS
    seen = found.setdefault("winter_years", [])
    if year not in seen:
        seen.append(year)
    return seen.index(year) + 1


def sample_sky(found: dict, state: dict, minute: int, world) -> None:
    """W2: one tick's sample of the winters, the winter food, the strikes and the fires (see the module docstring)."""
    from backend.survival.ailments import CHILL_BELOW
    from backend.survival.situation import from_db
    from backend.survival.winter_prep import winter_food
    vitals = state["vitals"]
    winters = found.setdefault("winters", {})
    winter = winter_of(found, state, minute)
    if winter is not None:
        entry = winters.setdefault(str(winter), {"health": 0.0, "ticks": 0, "freezing": 0, "starving": 0, "cold": 0,
                                                 "hungry": 0})
        entry["health"] += vitals["health"]
        entry["ticks"] += 1
        entry["freezing"] += vitals["warmth"] < 20.0
        entry["starving"] += vitals["hunger"] <= 0.0
        entry["cold"] += vitals["warmth"] < CHILL_BELOW  # criterion 6's measures (the ruling on the interim report)
        entry["hungry"] += vitals["hunger"] < HUNGRY_WINTER
        food = found.setdefault("winter_food", {})
        if str(winter) not in food:  # the first tick of its winter day 1
            with world.connect() as db:
                food[str(winter)] = round(winter_food(from_db(db, state, BORN + minute, SCALE), good_until=0), 1)
    fires = (state.get("sky") or {}).get("fires", [])
    if fires:
        with world.connect() as db:
            for entry in fires:
                claimed = db.execute("SELECT 1 FROM structure_cells WHERE x=? AND y=? AND z=?",
                                     (entry["x"], entry["y"], entry["z"])).fetchone()
                found["fire_claimed"] = found.get("fire_claimed", 0) + (claimed is not None)


def strike_seen(found: dict):
    """A storms.STRIKES hook: how near each strike fell to the home Mimo built at that moment."""
    from backend.survival.storms import built_home

    def seen(state, context, cell, hit, at):
        home = built_home(context.db)
        if home is not None:
            found["strike_home"] = min(found.get("strike_home", math.inf), math.hypot(cell[0] - home[0], cell[2] - home[1]))
    return seen


def sample(found: dict, state: dict, minute: int, world) -> None:
    """One tick's sample (a game minute)."""
    vitals, ailments = state["vitals"], state.get("ailments") or {}
    found["ticks"] += 1
    found["health"] += vitals["health"]
    day = (minute - 1) // 60 + 1
    while len(found["sick_by_day"]) < day:
        found["sick_by_day"].append(found["sick"])
    while len(found["lost_by_day"]) < day:
        found["lost_by_day"].append(found["lost_by_day"][-1] if found["lost_by_day"] else 0.0)
    found["lost_by_day"][day - 1] = round(float((state.get("wild") or {}).get("lost", 0.0)), 2)
    if ailments.get("sick"):
        found["sick"] += 1
        found["ever"]["sick"] = True
    found["sick_by_day"][day - 1] = found["sick"]
    wound = ailments.get("wound")
    if wound:
        found["ever"]["wound"] = True
        found["festering"] += bool(wound.get("festering"))
        if wound.get("age", 0.0) <= 60.0:
            found["wounds"] += 1
    if state.get("lots") or any(state.get("chest_lots", {}).values()):
        found["ever"]["lots"] = True
    if vitals["health"] < NEAR_DEATH:
        found["near"].add(day)
    found["freezing"] += vitals["warmth"] < 20.0
    found["starving"] += vitals["hunger"] <= 0.0
    for wonder_id, entry in ((state.get("wild") or {}).get("wonders") or {}).items():
        if wonder_id not in found["met"] and entry.get("met_at") is not None:  # the first meeting, kept
            found["met"][wonder_id] = round((entry["met_at"] - BORN) / 60 + 1, 3)
    with world.connect() as db:
        record_questions(found, db)


def record_questions(found: dict, db) -> None:
    """The questions Mimo posted since the last sample, as they are posted, and the most open at once: the inbox
    prunes answered and closed questions long before a 150-day life ends, so criterion 10' reads this record,
    not the inbox at the end."""
    since = max(found["asked"], default=0)
    for item, at, wonder in db.execute(
            "SELECT id, at, json_extract(data, '$.wonder') FROM mimo_inbox WHERE kind='ask' AND "
            "json_extract(data, '$.ask')='wonder' AND id > ? ORDER BY id", (since,)):
        found["asked"][item] = [round((at - BORN) / 60 + 1, 3), wonder]
    open_now = db.execute("SELECT COUNT(*) FROM mimo_inbox WHERE kind='ask' AND json_extract(data, '$.ask')="
                          "'wonder' AND json_extract(data, '$.closed') IS NULL").fetchone()[0]
    found["open_most"] = max(found["open_most"], open_now)


def summarize(world, found: dict, seed: int, days: int, condition: str, wall: float) -> dict:
    from backend.survival.memory import structures
    state = world.state()
    died = state.get("died_at")
    with world.connect() as db:
        facts: dict[str, dict] = {}
        for subject, fact, at in db.execute("SELECT subject, fact, learned_at FROM memory_knowledge WHERE subject LIKE 'wild:%'"):
            entry = facts.setdefault(subject[5:], {"day": None, "source": "figured"})
            if fact == "lesson":
                entry["day"] = round((at - BORN) / 60 + 1, 2)
            elif fact in ("taught", "born_knowing"):
                entry["source"] = {"taught": "from_you", "born_knowing": "from_start"}[fact]
        machines = {}
        for structure in structures(db, ("machine",)):
            name = structure["data"].get("style", {}).get("machine")
            if structure["status"] == "done" and name and name not in machines:
                machines[name] = round((structure["built_at"] - BORN) / 60 + 1, 2)
        kinds = dict(db.execute("SELECT kind, COUNT(*) FROM mimo_events GROUP BY kind").fetchall())
        computer = db.execute("SELECT MIN(at) FROM mimo_events WHERE kind='computer'").fetchone()[0]
    # Recorded as the life ran (sample, record_questions): the inbox and the state may have dropped them by now.
    asks = [found["asked"][item] for item in sorted(found["asked"])]
    met = dict(found["met"])
    ticks = max(1, found["ticks"])
    winters = {winter: {"health_mean": round(entry["health"] / max(1, entry["ticks"]), 2), "ticks": entry["ticks"],
                        "freezing": entry["freezing"], "starving": entry["starving"], "cold": entry.get("cold", 0),
                        "hungry": entry.get("hungry", 0)}
               for winter, entry in found.get("winters", {}).items()}
    with world.connect() as db:
        from backend.services.worldgen import LEGACY_RADIUS
        clearing = db.execute("SELECT COUNT(*) FROM mimo_blocks WHERE x * x + z * z <= ?",
                              (LEGACY_RADIUS * LEGACY_RADIUS,)).fetchone()[0]
    sky = state.get("sky") or {}
    return {"winters": winters, "winter_food": found.get("winter_food", {}),  # W2
            "struck": kinds.get("struck", 0), "strike_home": found.get("strike_home"),
            "fire_claimed": found.get("fire_claimed", 0), "clearing_edits": clearing, "sky_offset": sky.get("offset"),
            "seed": seed, "days": days, "condition": condition, "wall": round(wall, 1), "difficulty": state.get("difficulty"),
            "died_day": None if died is None else round((died - BORN) / 60 + 1, 2), "cause": state.get("cause"),
            "lived_minutes": found["ticks"], "health_mean": round(found["health"] / ticks, 2),
            "sick_minutes": found["sick"], "sick_by_day": found["sick_by_day"],
            "hazard_lost": found["lost_by_day"][-1] if found["lost_by_day"] else 0.0,
            "lost_by_day": found["lost_by_day"], "wounds": found["wounds"],
            "festering_minutes": found["festering"], "near_death_days": sorted(found["near"]),
            "freezing_minutes": found["freezing"], "starving_minutes": found["starving"], "lessons": facts,
            "wonders_met": met, "questions": asks, "open_most": found["open_most"], "machines": machines,
            "computer_day": None if computer is None else round((computer - BORN) / 60 + 1, 2),
            "ever": found["ever"] | {"question": bool(asks)}, "events": kinds}


# Many lives at once ---------------------------------------------------------------------------------

def fan_out(seeds, days: int, conditions, parallel: int, out: Path) -> None:
    """Every (condition, seed) as its own process, `parallel` at a time."""
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(condition, seed) for condition in conditions for seed in seeds]

    def run(job):
        condition, seed = job
        command = [sys.executable, "-m", "backend.scripts.wild_gate", "--seed", str(seed), "--days", str(days),
                   "--condition", condition, "--out", str(out)]
        return subprocess.run(command, capture_output=True, text=True).returncode

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        codes = list(pool.map(run, jobs))
    print(f"{len(jobs)} lives, {sum(1 for code in codes if code)} failed to run")


# The W1 gate ----------------------------------------------------------------------------------------

def load(out: Path) -> dict:
    lives: dict = {}
    for path in sorted(out.glob("*.json")):
        life = json.loads(path.read_text())
        lives.setdefault(life["condition"], {})[life["seed"]] = life
    return lives


def alive_on(life: dict, day: int) -> bool:
    return life["died_day"] is None or life["died_day"] > day


def by_day(life: dict, key: str, day: int) -> float:
    """A life's running count `key` ("sick_by_day", "lost_by_day") at the end of game day `day` (its last, if it
    died before)."""
    counts = life[key]
    return counts[min(day, len(counts)) - 1] if counts else 0


def check_w1(out: Path) -> list[tuple[str, bool, str]]:
    """The W1 gate's criteria, each (name, passed, the measure)."""
    lives = load(out)
    gentle, untaught, taught, liar = (lives.get(name, {}) for name in CONDITIONS)
    rows: list[tuple[str, bool, str]] = []

    def row(name, passed, measure):
        rows.append((name, bool(passed), measure))

    t, u = list(taught.values()), list(untaught.values())
    row("1 taught: all 6 alive on day 150", len(t) == 6 and all(alive_on(life, 150) for life in t),
        f"alive {sum(alive_on(life, 150) for life in t)}/{len(t)}")
    row("2 taught: each health mean 75 or more", t and all(life["health_mean"] >= 75 for life in t),
        f"lowest {min((life['health_mean'] for life in t), default=0)}")
    row("3 taught: each at most 3 near-death days", t and all(len(life["near_death_days"]) <= 3 for life in t),
        f"most {max((len(life['near_death_days']) for life in t), default=0)}")
    row("4 taught: each at most 150 sick minutes", t and all(life["sick_minutes"] <= 150 for life in t),
        f"most {max((life['sick_minutes'] for life in t), default=0)}")
    lamps = sum(1 for life in t if "lamp_lever" in life["machines"])
    most_taught = max((len(life["machines"]) for life in t), default=0)
    most_gentle = max((len(life["machines"]) for life in gentle.values()), default=0)
    row("5 taught: 3 of 6 build a lamp on a lever; the furthest taught within one of gentle's",
        lamps >= 3 and most_taught >= most_gentle - 1, f"lamps {lamps}/6; machines taught {most_taught}, gentle {most_gentle}")
    def first_month(key: str, group: list) -> float:
        return sum(by_day(life, key, FIRST_MONTH) for life in group)

    sick_u30, sick_t30 = first_month("sick_by_day", u), first_month("sick_by_day", t)
    lost_u30, lost_t30 = first_month("lost_by_day", u), first_month("lost_by_day", t)
    row("6' untaught, first month: sick minutes 3x taught; health lost to hazards 3x taught and 100+ a life",
        u and t and sick_u30 >= 3 * sick_t30 and lost_u30 >= 3 * lost_t30 and lost_u30 / len(u) >= 100,
        f"sick {sick_u30} vs {sick_t30}; lost {lost_u30:.0f} vs {lost_t30:.0f}, {lost_u30 / max(1, len(u)):.0f} a life")
    sick_u, sick_t = sum(life["sick_minutes"] for life in u), sum(life["sick_minutes"] for life in t)
    died_u = sum(1 for life in u if not alive_on(life, 150))
    near_u = sum(len(life["near_death_days"]) for life in u)
    row("7' untaught, a life without the owner: sick minutes 5x taught; deaths and near-death days 6+",
        u and t and sick_u >= 5 * sick_t and died_u + near_u >= 6,
        f"sick {sick_u} vs {sick_t}; deaths {died_u} + near-death days {near_u}")
    deaths = [life for life in u if not alive_on(life, 150)]
    row("8 untaught: at most 3 of 6 die, none before day 5", len(deaths) <= 3 and all(alive_on(life, 5) for life in u),
        f"deaths {len(deaths)} on days {[life['died_day'] for life in deaths]}")
    from backend.survival.wild import SURVIVAL
    from backend.survival.knocks import OWNER_ONLY
    W1_ALONE = {lesson.name for lesson in SURVIVAL[:11]} - set(OWNER_ONLY)  # W2: leave W2's alone-learnable lessons out
    alone = {life["seed"]: sum(1 for name, entry in life["lessons"].items()
                               if entry["day"] is not None and entry["day"] <= 60 and entry["source"] == "figured"
                               and name in W1_ALONE)
             for life in u if alive_on(life, 60)}
    row("9 untaught: alive on day 60 knows 7 of the 9 it can learn alone", all(count >= 7 for count in alone.values()),
        f"learned alone by day 60 {alone}")
    early = {life["seed"]: (sum(1 for day in life["wonders_met"].values() if day <= 4),  # its first 3 game days:
                            sum(1 for day, _ in life["questions"] if day <= 4)) for life in u}  # born on day 1.0
    open_most = max((life["open_most"] for group in lives.values() for life in group.values()), default=0)
    row("10' untaught: 4 wonders met and 3 questions in 3 days; never more than 3 open",
        all(met >= 4 and asked >= 3 for met, asked in early.values()) and open_most <= 3,
        f"(met, asked) {early}; most open {open_most}")
    lied = [name for life in liar.values() for name, entry in life["lessons"].items() if entry["source"] == "from_you"]
    row("11 liar: no lesson learned from a false chip or claim", liar and not lied, f"taught by the liar {lied}")
    liar_deaths = sum(1 for life in liar.values() if not alive_on(life, 30))
    untaught_deaths = sum(1 for life in u if not alive_on(life, 30))
    worse = {seed: (life["sick_by_day"][min(29, len(life["sick_by_day"]) - 1)] if life["sick_by_day"] else 0,
                    untaught[seed]["sick_by_day"][min(29, len(untaught[seed]["sick_by_day"]) - 1)]
                    if seed in untaught and untaught[seed]["sick_by_day"] else 0)
             for seed, life in liar.items()}
    row("12 liar: deaths by day 30 no more than untaught; sick minutes at most untaught + 30",
        liar and liar_deaths <= untaught_deaths and all(mine <= theirs + 30 for mine, theirs in worse.values()),
        f"deaths {liar_deaths} vs {untaught_deaths}; (liar, untaught) sick minutes by day 30 {worse}")
    g = list(gentle.values())
    clean = all(not any(life["ever"].values()) for life in g)
    from backend.survival.wild import SURVIVAL  # W2: every landed milestone's lessons
    known = all(len(life["lessons"]) == len(SURVIVAL)
                and all(entry["source"] == "from_start" for entry in life["lessons"].values()) for life in g)
    row("13 gentle: all alive; no sickness, wound, lot or question; every lesson from the first tick",
        len(g) == 6 and all(alive_on(life, 150) for life in g) and clean and known,
        f"alive {sum(alive_on(life, 150) for life in g)}/{len(g)}; clean {clean}; known {known}")
    everyone = [life for group in lives.values() for life in group.values()]
    row("all: no model call and no logged error", all(not life["model_calls"] and not life["errors"] for life in everyone),
        f"calls {sum(life['model_calls'] for life in everyone)}; errors {sum(len(life['errors']) for life in everyone)}")
    return rows


def check_w1r(out: Path) -> list[tuple[str, bool, str]]:
    """Criterion 8R: the untaught lives on R_SEEDS, each run R_DAYS game days: none dies before day 5, and at most
    R_DEATHS_MOST die in those days. A seed missing or run short fails the first row."""
    lives = load(out).get("untaught", {})
    found = [lives[seed] for seed in R_SEEDS if seed in lives and lives[seed]["days"] >= R_DAYS]
    missing = [seed for seed in R_SEEDS if seed not in lives or lives[seed]["days"] < R_DAYS]
    early = {life["seed"]: life["died_day"] for life in found if not alive_on(life, 5)}
    deaths = {life["seed"]: life["died_day"] for life in found if life["died_day"] is not None}
    return [(f"8R untaught, other seeds: {len(R_SEEDS)} lives, none dead before day 5", not missing and not early,
             f"lives {len(found)}/{len(R_SEEDS)}{f', missing or short {missing}' if missing else ''}; "
             f"dead before day 5 {early}"),
            (f"8R untaught, other seeds: at most {R_DEATHS_MOST} of {len(R_SEEDS)} die in {R_DAYS} game days",
             not missing and len(deaths) <= R_DEATHS_MOST,
             f"deaths {len(deaths)}: {dict(sorted(deaths.items(), key=lambda item: item[1]))}")]


# The W2 gate ----------------------------------------------------------------------------------------

COST_TESTS = ("backend.tests.test_survival_storms.TickTests.test_a_storm_by_a_burning_forest_costs_the_sky_little_a_transaction",
              "backend.tests.test_survival_winter.IceTests.test_a_path_crosses_a_frozen_lake_and_the_overlay_costs_the_search_little")


def cost_rows() -> tuple[bool, str]:
    """Criterion 10: the sky hook's budget in a storm by a forest and a route across a frozen lake (the unit tests
    that measure them, run here)."""
    import unittest
    result = unittest.TextTestRunner(stream=open("/dev/null", "w"), verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromNames(COST_TESTS))
    return result.wasSuccessful(), f"{result.testsRun} budget tests, {len(result.failures) + len(result.errors)} failed"


def check_w2(out: Path, cost: bool = True) -> list[tuple[str, bool, str]]:
    """The W2 gate's criteria, each (name, passed, the measure)."""
    lives = load(out)
    gentle, untaught, taught = (list(lives.get(name, {}).values()) for name in ("gentle", "untaught", "taught"))
    upgraded = list(lives.get("upgrade", {}).values())
    rows: list[tuple[str, bool, str]] = []

    def row(name, passed, measure):
        rows.append((name, bool(passed), measure))

    kept = gentle + taught
    row("1 gentle and taught: all alive on day 150", len(kept) == 12 and all(alive_on(life, 150) for life in kept),
        f"alive {sum(alive_on(life, 150) for life in kept)}/{len(kept)}")
    worst = [(life["condition"], life["seed"], winter, entry) for life in kept
             for winter, entry in life.get("winters", {}).items()]
    bad = [(condition, seed, winter) for condition, seed, winter, entry in worst
           if entry["health_mean"] < 60 or entry["freezing"] > 10 or entry["starving"] > 10]
    row("2 gentle and taught: each winter health mean 60+, freezing and starving 10 game minutes at most",
        worst and not bad, f"lowest mean {min((entry['health_mean'] for *_, entry in worst), default=0)}; most freezing "
        f"{max((entry['freezing'] for *_, entry in worst), default=0)}; most starving "
        f"{max((entry['starving'] for *_, entry in worst), default=0)}; failing {bad}")
    from backend.survival.winter_prep import WINTER_FOOD
    stocked = {condition: [sum(1 for life in group if life.get("winter_food", {}).get(str(winter), 0) >= WINTER_FOOD)
                           for winter in (1, 2, 3)] for condition, group in (("gentle", gentle), ("taught", taught))}
    row("3 gentle and taught: WINTER_FOOD good on winter day 1 in the chests, 5 of 6 the first winter, 6 of 6 after",
        all(counts[0] >= 5 and counts[1] >= 6 and counts[2] >= 6 for counts in stocked.values()),
        f"stocked by winter {stocked}; food {[(life['condition'], life['seed'], life.get('winter_food')) for life in kept]}")
    row("4 gentle and taught: at most 1 strike on Mimo a life", all(life.get("struck", 0) <= 1 for life in kept),
        f"most {max((life.get('struck', 0) for life in kept), default=0)}")
    lamps = sum(1 for life in taught if "lamp_lever" in life["machines"])
    most_taught = max((len(life["machines"]) for life in taught), default=0)
    most_gentle = max((len(life["machines"]) for life in gentle), default=0)
    row("5 W1 criterion 5: 3 of 6 taught build a lamp on a lever; the furthest within one of gentle's",
        lamps >= 3 and most_taught >= most_gentle - 1, f"lamps {lamps}/6; machines taught {most_taught}, gentle {most_gentle}")
    # Restated by the controller's ruling on the W2 interim report (criterion 6, step 3): the cold game minutes
    # (warmth under CHILL_BELOW) of the winters each pet lived through (it ticked in them, so it was alive at their
    # start), untaught at least twice taught's, and some.
    lived = {name: [entry for life in group for entry in life.get("winters", {}).values() if entry["ticks"]]
             for name, group in (("untaught", untaught), ("taught", taught))}
    cold = {name: sum(entry.get("cold", 0) for entry in winters) for name, winters in lived.items()}
    row("6 untaught: cold minutes in the winters lived at least 2x taught's (and some), over the pets alive at each "
        "winter's start", untaught and taught and cold["untaught"] > 0 and cold["untaught"] >= 2 * cold["taught"],
        f"untaught {cold['untaught']} over {len(lived['untaught'])} winters lived, taught {cold['taught']} over "
        f"{len(lived['taught'])}")
    row("7 untaught: at least 2 of 6 alive on day 150, none dead before day 5",
        sum(alive_on(life, 150) for life in untaught) >= 2 and all(alive_on(life, 5) for life in untaught),
        f"alive {sum(alive_on(life, 150) for life in untaught)}/{len(untaught)}; deaths "
        f"{[(life['died_day'], life['cause']) for life in untaught if not alive_on(life, 150)]}")
    everyone = gentle + untaught + taught + upgraded
    near = [life["strike_home"] for life in everyone if life.get("strike_home") is not None]
    row("8 safety: no strike within 16 of a built home, no fire in a claimed cell, no edit in the legacy clearing",
        all(distance > 16 for distance in near) and not any(life.get("fire_claimed") for life in everyone)
        and not any(life.get("clearing_edits") for life in everyone),
        f"nearest strike to home {min(near, default=None)}; fire in claimed cells "
        f"{sum(life.get('fire_claimed', 0) for life in everyone)}; clearing edits "
        f"{sum(life.get('clearing_edits', 0) for life in everyone)}")
    first = [(life["seed"], life.get("sky_offset"), life.get("winters", {}).get("1")) for life in upgraded]
    row("9 upgrade: spring on its upgrade day, alive and gentle through its first winter",
        upgraded and all(offset == (1 - UPGRADE_DAY) % 40 and winter and winter["ticks"] >= 600
                         for _, offset, winter in first) and all(alive_on(life, UPGRADE_DAY + 45) for life in upgraded)
        and all(life["difficulty"] == "gentle" and not any(life["ever"].values()) for life in upgraded),
        f"(seed, offset, first winter) {first}")
    if cost:
        passed, measure = cost_rows()
        row("10 cost: the sky hook in a storm, a route across a frozen lake", passed, measure)
    everybody = [life for group in lives.values() for life in group.values()]
    row("all: no model call and no logged error", all(not life["model_calls"] and not life["errors"] for life in everybody),
        f"calls {sum(life['model_calls'] for life in everybody)}; errors {sum(len(life['errors']) for life in everybody)}")
    return rows


CHECKS = {"W1": check_w1, "W1R": check_w1r, "W2": check_w2}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int)
    parser.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    parser.add_argument("--days", type=int, default=150)
    parser.add_argument("--condition", choices=(*CONDITIONS, UPGRADE))
    parser.add_argument("--conditions", default="gentle,untaught,taught")
    parser.add_argument("--parallel", type=int, default=0)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", nargs=2, metavar=("MILESTONE", "DIR"))
    args = parser.parse_args(argv)
    if args.check:
        if args.check[0] not in CHECKS:
            raise SystemExit(f"only these checks are written yet: {', '.join(CHECKS)}")
        rows = CHECKS[args.check[0]](Path(args.check[1]))
        for name, passed, measure in rows:
            print(f"{'PASS' if passed else 'FAIL'}  {name}  ({measure})")
        return 0 if all(passed for _, passed, _ in rows) else 1
    if args.parallel:
        fan_out([int(seed) for seed in args.seeds.split(",")], args.days, args.conditions.split(","), args.parallel,
                args.out)
        return 0
    summary = live(args.seed, args.days, args.condition)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.condition}_{args.seed}.json").write_text(json.dumps(summary, indent=1))
    print(f"{args.condition} {args.seed}: died {summary['died_day']}, health {summary['health_mean']}, "
          f"sick {summary['sick_minutes']}, {summary['wall']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
