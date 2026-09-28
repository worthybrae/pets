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
sickness, a wound, a lot or a question, logged errors and model calls.

    python3 -m backend.scripts.wild_gate --seed 8 --days 3 --condition untaught --out DIR
    python3 -m backend.scripts.wild_gate --days 150 --conditions gentle,untaught,taught --parallel 6 --out DIR
    python3 -m backend.scripts.wild_gate --check W1 DIR
"""

from __future__ import annotations

import argparse
import json
import logging
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
CONDITIONS = ("gentle", "untaught", "taught", "liar")
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
MACHINES = ("lamp_lever", "auto_door", "night_light", "clock", "memory_cell", "counter", "computer")


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
        life = hatch(registry, random.Random(seed), timestamp=BORN, difficulty="gentle" if condition == "gentle" else "wild")
        world = SurvivalWorld(registry.world_path(life))
        model = http or NoModel()
        chooser = Chooser(env={}, http=model, executor=InlineExecutor(), rng=random.Random(seed), scale=SCALE)
        talker = Talker(env={}, http=model, scale=SCALE)
        answered: set = set()
        found = {"health": 0.0, "ticks": 0, "sick": 0, "sick_by_day": [], "lost_by_day": [], "wounds": 0,
                 "festering": 0, "near": set(),
                 "freezing": 0, "starving": 0, "open_most": 0, "ever": {"sick": False, "wound": False, "lots": False}}
        state = world.state()
        for minute in range(1, days * 60 + 1):
            now = BORN + minute
            state = tick_life(registry, now, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            if state is None or state["died_at"] is not None:
                break
            chooser.poll(registry, now)
            owner(world, condition, minute, now, answered)
            talker.poll(registry, now)
            sample(found, state, minute, world)
        talker.close()
        summary = summarize(world, found, seed, days, condition, time.time() - started)
    summary.update(errors=errors.records[:50], model_calls=len(getattr(model, "calls", [])))
    logging.getLogger("backend").removeHandler(errors)
    return summary


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
    if minute % 5 == 0:
        with world.connect() as db:
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
        asks = [(round((row[0] - BORN) / 60 + 1, 3), row[1]) for row in db.execute(
            "SELECT at, json_extract(data, '$.wonder') FROM mimo_inbox WHERE kind='ask' AND "
            "json_extract(data, '$.ask')='wonder' ORDER BY id")]
        machines = {}
        for structure in structures(db, ("machine",)):
            name = structure["data"].get("style", {}).get("machine")
            if structure["status"] == "done" and name and name not in machines:
                machines[name] = round((structure["built_at"] - BORN) / 60 + 1, 2)
        kinds = dict(db.execute("SELECT kind, COUNT(*) FROM mimo_events GROUP BY kind").fetchall())
        computer = db.execute("SELECT MIN(at) FROM mimo_events WHERE kind='computer'").fetchone()[0]
    met = {wonder_id: round((entry["met_at"] - BORN) / 60 + 1, 3)
           for wonder_id, entry in ((state.get("wild") or {}).get("wonders") or {}).items()}
    ticks = max(1, found["ticks"])
    return {"seed": seed, "days": days, "condition": condition, "wall": round(wall, 1), "difficulty": state.get("difficulty"),
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
    alone = {life["seed"]: sum(1 for entry in life["lessons"].values()
                               if entry["day"] is not None and entry["day"] <= 60 and entry["source"] == "figured")
             for life in u if alive_on(life, 60)}
    row("9 untaught: alive on day 60 knows 8 of 11 learned alone", all(count >= 8 for count in alone.values()),
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
    known = all(len(life["lessons"]) == 11 and all(entry["source"] == "from_start" for entry in life["lessons"].values())
                for life in g)
    row("13 gentle: all alive; no sickness, wound, lot or question; every lesson from the first tick",
        len(g) == 6 and all(alive_on(life, 150) for life in g) and clean and known,
        f"alive {sum(alive_on(life, 150) for life in g)}/{len(g)}; clean {clean}; known {known}")
    everyone = [life for group in lives.values() for life in group.values()]
    row("all: no model call and no logged error", all(not life["model_calls"] and not life["errors"] for life in everyone),
        f"calls {sum(life['model_calls'] for life in everyone)}; errors {sum(len(life['errors']) for life in everyone)}")
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int)
    parser.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    parser.add_argument("--days", type=int, default=150)
    parser.add_argument("--condition", choices=CONDITIONS)
    parser.add_argument("--conditions", default="gentle,untaught,taught")
    parser.add_argument("--parallel", type=int, default=0)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", nargs=2, metavar=("MILESTONE", "DIR"))
    args = parser.parse_args(argv)
    if args.check:
        if args.check[0] != "W1":
            raise SystemExit("only the W1 gate is written yet")
        rows = check_w1(Path(args.check[1]))
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
